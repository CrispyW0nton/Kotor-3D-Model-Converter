"""wgpu-py renderer backend for the Qt viewport.

This backend uses rendercanvas' Qt widget as the WGPU presentation surface.
ModernGL remains GhostRigger's complete scene renderer; WGPU currently provides
live-surface clear/grid plus basic untextured mesh rendering.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from importlib import util as importlib_util
from pathlib import Path
from typing import ClassVar

from src.gui.rendering.null_renderer import NullDiagnosticRenderer
from src.gui.rendering.renderer_backend import RendererBackend
from src.gui.rendering.renderer_capabilities import (
    WGPU_DISPLAY_MODES,
    WGPU_FALLBACK_DISPLAY_MODES,
    RendererCapabilities,
)
from src.gui.rendering.renderer_performance import (
    TextureResidencyInfo,
    bounds_intersects_frustum,
    extract_frustum_planes,
    group_render_batches,
    instancing_summary,
    texture_array_groups,
)
from src.gui.rendering.renderer_profiler import RendererProfiler
from src.gui.rendering.renderer_settings import RendererSettings
from src.gui.rendering.picking import PickHit
from src.gui.rendering.viewport_display import ViewportDisplayMode, ViewportDisplayOptions, normalize_display_mode
from src.gui.lighting.light_gizmo_renderer import LIGHT_HELPER_COLORS

log = logging.getLogger(__name__)

_WGPU_BACKEND_ENV = "WGPU_BACKEND_TYPE"
SELECTION_YELLOW = (1.0, 210 / 255.0, 63 / 255.0)
_WGPU_BACKENDS = {
    RendererBackend.WGPU_D3D12: "D3D12",
    RendererBackend.WGPU_VULKAN: "Vulkan",
    RendererBackend.WGPU_OPENGL: "OpenGL",
}


@dataclass(frozen=True)
class _WgpuBackendSpec:
    backend: RendererBackend
    name: str
    wgpu_backend_type: str


@dataclass
class WgpuMeshResource:
    vertex_buffer: object
    index_buffer: object | None
    edge_index_buffer: object | None
    vertex_count: int
    index_count: int
    edge_index_count: int
    vertex_stride: int
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]]
    source_revision: tuple[int, int, int]


@dataclass
class WgpuTextureResource:
    texture: object
    texture_view: object
    sampler: object
    width: int
    height: int
    format: str
    source_id: str
    source_revision: tuple[int, int, int]
    label: str
    byte_size: int
    fallback: bool = False
    lightmap: bool = False


@dataclass
class WgpuMaterialResource:
    bind_group: object
    diffuse_texture_resource: WgpuTextureResource
    lightmap_texture_resource: WgpuTextureResource
    alpha_mode: str
    alpha_cutoff: float
    double_sided: bool
    has_lightmap: bool
    source_revision: tuple[int, int, int, int]


@dataclass
class WgpuSkeletonResource:
    line_vertex_buffer: object | None
    joint_marker_vertex_buffer: object | None
    selected_line_vertex_buffer: object | None
    selected_marker_vertex_buffer: object | None
    line_vertex_count: int
    joint_marker_vertex_count: int
    selected_line_vertex_count: int
    selected_marker_vertex_count: int
    bone_count: int
    joint_count: int
    revision: int


@dataclass
class WgpuSkinResource:
    palette_buffer: object
    bind_group: object
    uploader: object
    source_revision: tuple
    pose_revision: int
    matrix_count: int
    max_bones: int
    byte_size: int


@dataclass
class WgpuPickResources:
    width: int
    height: int
    pick_texture: object
    depth_texture: object
    read_buffer: object


@dataclass
class WgpuLightResource:
    light_buffer: object | None
    lighting_uniform_buffer: object | None
    revision: int
    light_count: int
    uploaded_light_count: int
    max_lights: int
    helper_batches: list[tuple[tuple[float, float, float, float], object, int]]
    volume_batches: list[tuple[tuple[float, float, float, float], object, int]]
    selected_light_id: int
    unsupported_light_types: int
    upload_time_ms: float


def _hex_to_rgb_float(value: str, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    raw = str(value or "").strip().lstrip("#")
    if len(raw) != 6:
        return fallback
    try:
        return (
            int(raw[0:2], 16) / 255.0,
            int(raw[2:4], 16) / 255.0,
            int(raw[4:6], 16) / 255.0,
        )
    except ValueError:
        return fallback


def _rgb_float(color: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple(max(0.0, min(1.0, float(v) / 255.0)) for v in color[:3])


def _blend_rgb(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, float(t)))
    return tuple(int(round(float(a[i]) * (1.0 - t) + float(b[i]) * t)) for i in range(3))


def _relative_luma(color: tuple[int, int, int]) -> float:
    r, g, b = (max(0, min(255, int(v))) / 255.0 for v in color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _rgba8(color: tuple[float, float, float], alpha: int = 255) -> bytes:
    return bytes([*(max(0, min(255, int(round(c * 255.0)))) for c in color[:3]), max(0, min(255, int(alpha)))])


def _point_distance(a, b) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def _joint_marker_segments(point, *, selected: bool = False) -> list[tuple[float, float, float]]:
    x, y, z = (float(v) for v in tuple(point)[:3])
    r = 0.045 if selected else 0.030
    return [
        (x - r, y, z),
        (x + r, y, z),
        (x, y - r, z),
        (x, y + r, z),
        (x, y, z - r),
        (x, y, z + r),
    ]


def _srgb_channel_to_linear(value: float) -> float:
    value = max(0.0, min(1.0, float(value)))
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _srgb_to_linear(color: tuple[float, ...]) -> tuple[float, ...]:
    converted = tuple(_srgb_channel_to_linear(float(channel)) for channel in color[:3])
    if len(color) >= 4:
        return (*converted, float(color[3]))
    return converted


def _format_is_srgb(format_name: object) -> bool:
    return "srgb" in str(format_name or "").lower()


def _mat4_perspective_wgpu(fov_y: float, aspect: float, near: float, far: float):
    import numpy as np

    f = 1.0 / math.tan(fov_y * 0.5)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / max(aspect, 1e-6)
    m[1, 1] = f
    m[2, 2] = far / (near - far)
    m[2, 3] = (far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def _mat4_lookat(eye, center, up):
    import numpy as np

    eye = np.array(eye, dtype=np.float64)
    center = np.array(center, dtype=np.float64)
    up = np.array(up, dtype=np.float64)
    f = center - eye
    f_norm = np.linalg.norm(f)
    if f_norm <= 1e-9:
        f = np.array((0.0, 0.0, -1.0), dtype=np.float64)
    else:
        f /= f_norm
    s = np.cross(f, up)
    s_norm = np.linalg.norm(s)
    if s_norm <= 1e-9:
        s = np.cross(f, np.array((0.0, 1.0, 0.0), dtype=np.float64))
        s_norm = max(np.linalg.norm(s), 1e-9)
    s /= s_norm
    u = np.cross(s, f)
    m = np.eye(4, dtype=np.float32)
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    m[0, 3] = -np.dot(s, eye)
    m[1, 3] = -np.dot(u, eye)
    m[2, 3] = np.dot(f, eye)
    return m


def _mat4_tobytes(m) -> bytes:
    import numpy as np

    return np.asarray(m, dtype=np.float32).reshape(4, 4).T.tobytes()


def _load_mesh_shader() -> str:
    shader_path = Path(__file__).resolve().parent / "shaders" / "wgpu_mesh_textured.wgsl"
    try:
        return shader_path.read_text(encoding="utf-8")
    except Exception:
        return _MESH_TEXTURED_WGSL


def _load_skinned_mesh_shader() -> str:
    shader_path = Path(__file__).resolve().parent / "shaders" / "wgpu_mesh_skinned.wgsl"
    return shader_path.read_text(encoding="utf-8")


def _adapter_info_dict(adapter) -> dict[str, object]:
    info = getattr(adapter, "info", None)
    if info is None:
        return {}
    keys = ("vendor", "device", "description", "adapter_type", "backend_type")
    return {key: getattr(info, key, None) for key in keys if getattr(info, key, None)}


def _probe_script() -> str:
    return r'''
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtWidgets
    from rendercanvas.qt import QRenderWidget
    import wgpu
except Exception as exc:
    print(json.dumps({"available": False, "reason": f"import failed: {exc}"}))
    raise SystemExit(0)

try:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    canvas = QRenderWidget()
    canvas.resize(64, 64)
    context = canvas.get_context("wgpu")
    adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
    if adapter is None:
        raise RuntimeError("no suitable WGPU adapter found")
    device = adapter.request_device_sync(required_features=[], required_limits={})
    fmt = context.get_preferred_format(adapter)
    context.configure(device=device, format=fmt)

    def draw():
        view = context.get_current_texture().create_view()
        encoder = device.create_command_encoder()
        render_pass = encoder.begin_render_pass(color_attachments=[{
            "view": view,
            "resolve_target": None,
            "clear_value": (0.05, 0.06, 0.07, 1.0),
            "load_op": wgpu.LoadOp.clear,
            "store_op": wgpu.StoreOp.store,
        }])
        render_pass.end()
        device.queue.submit([encoder.finish()])

    canvas.request_draw(draw)
    canvas.force_draw()
    app.processEvents()
    info = getattr(adapter, "info", None)
    print(json.dumps({
        "available": True,
        "reason": "",
        "format": fmt,
        "adapter": {
            "vendor": getattr(info, "vendor", None),
            "device": getattr(info, "device", None),
            "description": getattr(info, "description", None),
            "adapter_type": getattr(info, "adapter_type", None),
            "backend_type": getattr(info, "backend_type", None),
        },
    }))
except Exception as exc:
    print(json.dumps({"available": False, "reason": str(exc)}))
finally:
    try:
        canvas.close()
        canvas.deleteLater()
        app.processEvents()
    except Exception:
        pass
'''


class WgpuResourceCache:
    """Renderer-owned WGPU resources keyed by GhostRigger object identity."""

    def __init__(self, renderer: "WgpuRenderer") -> None:
        self._renderer = renderer
        self.meshes: dict[int, WgpuMeshResource] = {}
        self.skins: dict[int, WgpuSkinResource] = {}
        self.textures: dict[str, WgpuTextureResource] = {}
        self.materials: dict[str, WgpuMaterialResource] = {}
        self.uploaded_vertex_count = 0
        self.uploaded_index_count = 0
        self.uploaded_edge_index_count = 0
        self.texture_memory_bytes = 0
        self.fallback_texture_count = 0
        self.missing_texture_count = 0
        self.lightmap_texture_count = 0
        self.last_texture_upload_error = ""
        self.last_material_binding_error = ""
        self.last_skinning_error = ""
        self.uploaded_bone_matrix_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.mesh_upload_count = 0
        self.texture_upload_count = 0
        self.buffer_upload_count = 0
        self.bind_group_creation_count = 0
        self.last_invalidation_reason = ""
        self._white_diffuse: WgpuTextureResource | None = None
        self._white_lightmap: WgpuTextureResource | None = None
        self._missing_checker: WgpuTextureResource | None = None

    def get_or_upload_mesh(self, mesh_data) -> WgpuMeshResource | None:
        mesh_id = int(mesh_data.mesh_id)
        cached = self.meshes.get(mesh_id)
        if cached is not None and cached.source_revision == mesh_data.source_revision:
            self.cache_hits += 1
            return cached
        self.cache_misses += 1
        return self.upload_mesh(mesh_id, mesh_data)

    def upload_mesh(self, mesh_id: int, mesh_data) -> WgpuMeshResource | None:
        import numpy as np
        import wgpu

        device = self._renderer.device
        if device is None:
            return None
        positions = np.asarray(mesh_data.positions, dtype=np.float32)
        if positions.ndim != 2 or positions.shape[1] != 3 or len(positions) == 0:
            return None
        normals = mesh_data.normals
        if normals is None:
            normals = np.zeros_like(positions, dtype=np.float32)
            normals[:, 2] = 1.0
        normals = np.asarray(normals, dtype=np.float32)
        if normals.shape != positions.shape:
            fixed = np.zeros_like(positions, dtype=np.float32)
            fixed[:, 2] = 1.0
            rows = min(len(fixed), len(normals))
            if rows:
                fixed[:rows, :] = normals[:rows, :3]
            normals = fixed
        uvs0 = self._coerce_uvs(getattr(mesh_data, "uvs0", None), len(positions))
        uvs1 = self._coerce_uvs(getattr(mesh_data, "uvs1", None), len(positions))
        bone_indices = self._coerce_bone_indices(getattr(mesh_data, "bone_indices", None), len(positions))
        bone_weights = self._coerce_bone_weights(getattr(mesh_data, "bone_weights", None), len(positions))
        packed_dtype = np.dtype(
            [
                ("position", "<f4", 3),
                ("normal", "<f4", 3),
                ("uv0", "<f4", 2),
                ("uv1", "<f4", 2),
                ("bone_indices", "<u4", 4),
                ("bone_weights", "<f4", 4),
            ]
        )
        packed = np.empty(len(positions), dtype=packed_dtype)
        packed["position"] = positions
        packed["normal"] = normals
        packed["uv0"] = uvs0
        packed["uv1"] = uvs1
        packed["bone_indices"] = bone_indices
        packed["bone_weights"] = bone_weights
        vertex_buffer = device.create_buffer_with_data(data=packed.tobytes(), usage=wgpu.BufferUsage.VERTEX)
        self.buffer_upload_count += 1
        index_buffer = None
        index_count = 0
        edge_index_buffer = None
        edge_index_count = 0
        if mesh_data.indices is not None and len(mesh_data.indices):
            indices = np.ascontiguousarray(mesh_data.indices, dtype=np.uint32)
            index_buffer = device.create_buffer_with_data(data=indices, usage=wgpu.BufferUsage.INDEX)
            self.buffer_upload_count += 1
            index_count = int(len(indices))
            edge_indices = self._build_edge_indices(indices, len(positions))
        else:
            edge_indices = self._build_edge_indices(None, len(positions))
        if edge_indices is not None and len(edge_indices):
            edge_index_buffer = device.create_buffer_with_data(data=edge_indices, usage=wgpu.BufferUsage.INDEX)
            self.buffer_upload_count += 1
            edge_index_count = int(len(edge_indices))
        mins = positions.min(axis=0)
        maxs = positions.max(axis=0)
        resource = WgpuMeshResource(
            vertex_buffer=vertex_buffer,
            index_buffer=index_buffer,
            edge_index_buffer=edge_index_buffer,
            vertex_count=int(len(positions)),
            index_count=index_count,
            edge_index_count=edge_index_count,
            vertex_stride=72,
            bounds=(tuple(float(v) for v in mins), tuple(float(v) for v in maxs)),
            source_revision=mesh_data.source_revision,
        )
        self.meshes[int(mesh_id)] = resource
        self.mesh_upload_count += 1
        self._recount()
        return resource

    def get_or_update_skin_palette(self, mesh_data, anim_pose, model) -> WgpuSkinResource | None:
        import wgpu

        if not bool(getattr(mesh_data, "is_skinned", False)) or anim_pose is None:
            return None
        device = self._renderer.device
        layout = getattr(self._renderer, "skin_bind_group_layout", None)
        if device is None or layout is None:
            self.last_skinning_error = "WGPU skin bind group layout is not ready"
            return None
        try:
            from src.core.animation.gpu_skinning import MatrixPaletteUploader, MAX_BONES
        except Exception as exc:
            self.last_skinning_error = f"WGPU palette builder unavailable: {exc}"
            return None

        mesh_id = int(mesh_data.mesh_id)
        source_revision = tuple(getattr(mesh_data, "source_revision", ()) or ())
        cached = self.skins.get(mesh_id)
        if cached is None or cached.source_revision != source_revision:
            self.cache_misses += 1
            max_bones = int(MAX_BONES)
            byte_size = max_bones * 16 * 4
            palette_buffer = device.create_buffer(
                label=f"WGPU skin palette {getattr(mesh_data.source, 'name', mesh_id)}",
                size=byte_size,
                usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST,
            )
            bind_group = device.create_bind_group(
                layout=layout,
                entries=[
                    {
                        "binding": 0,
                        "resource": {"buffer": palette_buffer, "offset": 0, "size": byte_size},
                    }
                ],
            )
            self.bind_group_creation_count += 1
            uploader = MatrixPaletteUploader(max_bones=max_bones)
            uploader.build_inverse_bind_pose(model)
            cached = WgpuSkinResource(
                palette_buffer=palette_buffer,
                bind_group=bind_group,
                uploader=uploader,
                source_revision=source_revision,
                pose_revision=-1,
                matrix_count=0,
                max_bones=max_bones,
                byte_size=byte_size,
            )
            self.skins[mesh_id] = cached

        pose_revision = self._pose_revision(anim_pose, mesh_data)
        if cached.pose_revision != pose_revision:
            started = time.perf_counter()
            palette = cached.uploader.compute_skin_node_palette(mesh_data.source, anim_pose)
            payload = cached.uploader.as_flat_bytes()
            if not payload:
                self.last_skinning_error = f"empty WGPU skin palette for {getattr(mesh_data.source, 'name', mesh_id)}"
                return None
            self._renderer.queue.write_buffer(cached.palette_buffer, 0, payload[: cached.byte_size])
            self.buffer_upload_count += 1
            cached.pose_revision = pose_revision
            cached.matrix_count = min(len(palette), cached.max_bones)
            self.uploaded_bone_matrix_count = max(self.uploaded_bone_matrix_count, int(cached.matrix_count))
            profiler = getattr(self._renderer, "profiler", None)
            if profiler is not None:
                profiler.add("skeleton_pose_upload_count", 1)
                if bool(getattr(profiler, "enabled", False)):
                    profiler.current.animation_pose_upload_ms += (time.perf_counter() - started) * 1000.0
        else:
            self.cache_hits += 1
        return cached

    def _build_edge_indices(self, indices, vertex_count: int):
        import numpy as np

        if vertex_count <= 1:
            return None
        if indices is None:
            tri_indices = np.arange(vertex_count, dtype=np.uint32)
        else:
            tri_indices = np.asarray(indices, dtype=np.uint32).reshape(-1)
        if len(tri_indices) < 3:
            return None
        edge_set: set[tuple[int, int]] = set()
        out: list[int] = []
        usable = len(tri_indices) - (len(tri_indices) % 3)
        for i in range(0, usable, 3):
            tri = [int(tri_indices[i]), int(tri_indices[i + 1]), int(tri_indices[i + 2])]
            if any(v < 0 or v >= vertex_count for v in tri):
                continue
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                key = (a, b) if a <= b else (b, a)
                if key in edge_set:
                    continue
                edge_set.add(key)
                out.extend((a, b))
        if not out:
            return None
        return np.ascontiguousarray(out, dtype=np.uint32)

    def _coerce_uvs(self, values, count: int):
        import numpy as np

        fixed = np.full((count, 2), 0.5, dtype=np.float32)
        if values is None:
            return fixed
        try:
            arr = np.asarray(values, dtype=np.float32)
            if arr.ndim != 2 or arr.shape[1] < 2:
                return fixed
            rows = min(count, len(arr))
            if rows:
                fixed[:rows, :] = arr[:rows, :2]
        except Exception:
            return fixed
        return fixed

    def _coerce_bone_indices(self, values, count: int):
        import numpy as np

        fixed = np.zeros((count, 4), dtype=np.uint32)
        if values is None:
            return fixed
        try:
            arr = np.asarray(values, dtype=np.uint32)
            if arr.ndim != 2 or arr.shape[1] < 4:
                return fixed
            rows = min(count, len(arr))
            if rows:
                fixed[:rows, :] = np.clip(arr[:rows, :4], 0, 127).astype(np.uint32)
        except Exception:
            return fixed
        return fixed

    def _coerce_bone_weights(self, values, count: int):
        import numpy as np

        fixed = np.zeros((count, 4), dtype=np.float32)
        fixed[:, 0] = 1.0
        if values is None:
            return fixed
        try:
            arr = np.asarray(values, dtype=np.float32)
            if arr.ndim != 2 or arr.shape[1] < 4:
                return fixed
            rows = min(count, len(arr))
            if rows:
                fixed[:rows, :] = arr[:rows, :4]
                sub = fixed[:rows, :]
                sums = sub.sum(axis=1)
                valid = sums > 1e-8
                sub[valid] = sub[valid] / sums[valid, None]
                sub[~valid] = (1.0, 0.0, 0.0, 0.0)
        except Exception:
            return fixed
        return fixed

    def _pose_revision(self, anim_pose, mesh_data) -> int:
        return hash(
            (
                id(anim_pose),
                int(round(float(getattr(anim_pose, "time", 0.0) or 0.0) * 100000.0)),
                int(getattr(mesh_data, "skin_revision", 0) or 0),
                int(mesh_data.mesh_id),
            )
        ) & 0x7FFFFFFF

    def get_mesh_resource(self, mesh_id: int):
        return self.meshes.get(int(mesh_id))

    def get_or_upload_texture(
        self,
        texture_data,
        *,
        fallback_kind: str = "diffuse",
        lightmap: bool = False,
    ) -> WgpuTextureResource:
        texture_id = str(getattr(texture_data, "texture_id", "") or "")
        source_revision = tuple(getattr(texture_data, "source_revision", (0, 0, 0)) or (0, 0, 0))
        if not texture_id or texture_data is None or getattr(texture_data, "source", None) is None:
            self.missing_texture_count += 1
            log.debug("WgpuResourceCache: using fallback texture for %s", texture_id or fallback_kind)
            return self._fallback_texture("lightmap" if lightmap else fallback_kind, lightmap=lightmap)
        cached = self.textures.get(texture_id)
        if cached is not None and cached.source_revision == source_revision:
            self.cache_hits += 1
            return cached
        self.cache_misses += 1
        try:
            from src.gui.rendering.mesh_render_data import texture_image_to_rgba8

            converted = texture_image_to_rgba8(texture_data)
            if converted is None:
                raise ValueError("texture adapter returned no RGBA8 data")
            width, height, rgba = converted
            resource = self._upload_rgba8_texture(
                texture_id,
                rgba,
                width,
                height,
                source_revision=source_revision,
                label=str(getattr(texture_data, "name", texture_id) or texture_id),
                lightmap=lightmap,
            )
            self.textures[texture_id] = resource
            self._recount()
            if bool(getattr(self._renderer, "debug_texture_uploads", False)):
                log.info("WgpuResourceCache: uploaded texture %s %sx%s rgba8", texture_id, width, height)
            return resource
        except Exception as exc:
            self.last_texture_upload_error = f"{texture_id}: {exc}"
            log.warning("WgpuResourceCache: using fallback texture for %s: %s", texture_id, exc)
            return self._fallback_texture("lightmap" if lightmap else fallback_kind, lightmap=lightmap)

    def get_or_create_material(self, material_data) -> WgpuMaterialResource | None:
        material_id = str(getattr(material_data, "material_id", "") or id(material_data))
        source_revision = tuple(getattr(material_data, "source_revision", (0, 0, 0, 0)) or (0, 0, 0, 0))
        cached = self.materials.get(material_id)
        if cached is not None and cached.source_revision == source_revision:
            self.cache_hits += 1
            return cached
        self.cache_misses += 1
        try:
            diffuse_data = getattr(material_data, "diffuse_texture_data", None)
            diffuse = self.get_or_upload_texture(
                diffuse_data,
                fallback_kind="diffuse",
                lightmap=False,
            ) if diffuse_data is not None else self._fallback_texture("diffuse")
            lightmap_data = getattr(material_data, "lightmap_texture_data", None)
            has_lightmap = lightmap_data is not None and getattr(lightmap_data, "source", None) is not None
            lightmap = (
                self.get_or_upload_texture(lightmap_data, fallback_kind="lightmap", lightmap=True)
                if has_lightmap
                else self._fallback_texture("lightmap", lightmap=True)
            )
            layout = self._renderer.texture_bind_group_layout
            if layout is None:
                raise RuntimeError("texture bind group layout is not ready")
            bind_group = self._renderer.device.create_bind_group(
                layout=layout,
                entries=[
                    {"binding": 0, "resource": diffuse.texture_view},
                    {"binding": 1, "resource": diffuse.sampler},
                    {"binding": 2, "resource": lightmap.texture_view},
                    {"binding": 3, "resource": lightmap.sampler},
                ],
            )
            self.bind_group_creation_count += 1
            resource = WgpuMaterialResource(
                bind_group=bind_group,
                diffuse_texture_resource=diffuse,
                lightmap_texture_resource=lightmap,
                alpha_mode=str(getattr(material_data, "alpha_mode", "OPAQUE") or "OPAQUE"),
                alpha_cutoff=float(getattr(material_data, "alpha_cutoff", 0.5) or 0.5),
                double_sided=bool(getattr(material_data, "double_sided", False)),
                has_lightmap=has_lightmap,
                source_revision=source_revision,
            )
            self.materials[material_id] = resource
            return resource
        except Exception as exc:
            self.last_material_binding_error = f"{material_id}: {exc}"
            log.warning("WgpuResourceCache: material bind failed for %s: %s", material_id, exc)
            return None

    def _upload_rgba8_texture(
        self,
        texture_id: str,
        rgba: bytes,
        width: int,
        height: int,
        *,
        source_revision: tuple[int, int, int],
        label: str,
        lightmap: bool = False,
        fallback: bool = False,
    ) -> WgpuTextureResource:
        import wgpu

        device = self._renderer.device
        if device is None:
            raise RuntimeError("WGPU device is not ready")
        texture_format = self._texture_format(lightmap=lightmap)
        texture = device.create_texture(
            label=label,
            size=(int(width), int(height), 1),
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
            dimension=wgpu.TextureDimension.d2,
            format=texture_format,
            mip_level_count=1,
            sample_count=1,
        )
        row_bytes = int(width) * 4
        aligned_row_bytes = ((row_bytes + 255) // 256) * 256
        upload_row_bytes = aligned_row_bytes if int(height) > 1 else row_bytes
        upload_bytes = rgba
        if int(height) > 1 and aligned_row_bytes != row_bytes:
            padded = bytearray(aligned_row_bytes * int(height))
            for row in range(int(height)):
                src0 = row * row_bytes
                dst0 = row * aligned_row_bytes
                padded[dst0 : dst0 + row_bytes] = rgba[src0 : src0 + row_bytes]
            upload_bytes = bytes(padded)
        device.queue.write_texture(
            {"texture": texture, "mip_level": 0, "origin": (0, 0, 0)},
            upload_bytes,
            {"offset": 0, "bytes_per_row": upload_row_bytes, "rows_per_image": int(height)},
            (int(width), int(height), 1),
        )
        self.texture_upload_count += 1
        sampler = device.create_sampler(
            address_mode_u=wgpu.AddressMode.clamp_to_edge if lightmap else wgpu.AddressMode.repeat,
            address_mode_v=wgpu.AddressMode.clamp_to_edge if lightmap else wgpu.AddressMode.repeat,
            address_mode_w=wgpu.AddressMode.clamp_to_edge,
            mag_filter=wgpu.FilterMode.linear,
            min_filter=wgpu.FilterMode.linear,
            mipmap_filter=wgpu.MipmapFilterMode.nearest,
        )
        return WgpuTextureResource(
            texture=texture,
            texture_view=texture.create_view(),
            sampler=sampler,
            width=int(width),
            height=int(height),
            format=str(texture_format),
            source_id=texture_id,
            source_revision=source_revision,
            label=label,
            byte_size=int(width) * int(height) * 4,
            fallback=fallback,
            lightmap=lightmap,
        )

    @staticmethod
    def _texture_format(*, lightmap: bool):
        import wgpu

        if lightmap:
            return wgpu.TextureFormat.rgba8unorm
        return getattr(wgpu.TextureFormat, "rgba8unorm_srgb", "rgba8unorm-srgb")

    def _fallback_texture(self, kind: str, *, lightmap: bool = False) -> WgpuTextureResource:
        if kind == "lightmap":
            if self._white_lightmap is None:
                self._white_lightmap = self._upload_rgba8_texture(
                    "__fallback_lightmap__",
                    bytes([255, 255, 255, 255]),
                    1,
                    1,
                    source_revision=(0, 1, 1),
                    label="WGPU white lightmap fallback",
                    lightmap=True,
                    fallback=True,
                )
                self.fallback_texture_count += 1
            return self._white_lightmap
        if kind == "missing_checker" or bool(getattr(self._renderer, "show_missing_texture_checker", False)):
            if self._missing_checker is None:
                a = _rgba8(getattr(self._renderer, "missing_texture_color_a", (1.0, 0.0, 1.0)))
                b = _rgba8(getattr(self._renderer, "missing_texture_color_b", (0.0, 0.0, 0.0)))
                self._missing_checker = self._upload_rgba8_texture(
                    "__fallback_missing_checker__",
                    a + b + b + a,
                    2,
                    2,
                    source_revision=(0, 2, 2),
                    label="WGPU missing texture checker",
                    fallback=True,
                )
                self.fallback_texture_count += 1
            return self._missing_checker
        if self._white_diffuse is None:
            self._white_diffuse = self._upload_rgba8_texture(
                "__fallback_diffuse__",
                bytes([255, 255, 255, 255]),
                1,
                1,
                source_revision=(0, 1, 1),
                label="WGPU white diffuse fallback",
                fallback=True,
            )
            self.fallback_texture_count += 1
        return self._white_diffuse

    def release_mesh(self, mesh_id: int) -> None:
        self.meshes.pop(int(mesh_id), None)
        self.skins.pop(int(mesh_id), None)
        self.last_invalidation_reason = f"mesh released: {mesh_id}"
        self._recount()

    def invalidate_texture(self, texture_id: str) -> None:
        self.textures.pop(str(texture_id), None)
        self.last_invalidation_reason = f"texture invalidated: {texture_id}"
        self._recount()

    def invalidate_material(self, material_id: str) -> None:
        self.materials.pop(str(material_id), None)
        self.last_invalidation_reason = f"material invalidated: {material_id}"

    def invalidate_all(self, reason: str = "all renderer resources invalidated") -> None:
        self.meshes.clear()
        self.skins.clear()
        self.textures.clear()
        self.materials.clear()
        self.uploaded_vertex_count = 0
        self.uploaded_index_count = 0
        self.uploaded_edge_index_count = 0
        self.texture_memory_bytes = 0
        self.fallback_texture_count = 0
        self.missing_texture_count = 0
        self.lightmap_texture_count = 0
        self.last_texture_upload_error = ""
        self.last_material_binding_error = ""
        self.last_skinning_error = ""
        self.uploaded_bone_matrix_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.mesh_upload_count = 0
        self.texture_upload_count = 0
        self.buffer_upload_count = 0
        self.bind_group_creation_count = 0
        self.last_invalidation_reason = str(reason or "all renderer resources invalidated")
        self._white_diffuse = None
        self._white_lightmap = None
        self._missing_checker = None

    def _recount(self) -> None:
        self.uploaded_vertex_count = sum(int(item.vertex_count) for item in self.meshes.values())
        self.uploaded_index_count = sum(int(item.index_count) for item in self.meshes.values())
        self.uploaded_edge_index_count = sum(int(item.edge_index_count) for item in self.meshes.values())
        self.texture_memory_bytes = sum(int(item.byte_size) for item in self.textures.values())
        self.lightmap_texture_count = sum(1 for item in self.textures.values() if item.lightmap)
        self.uploaded_bone_matrix_count = max((int(item.matrix_count) for item in self.skins.values()), default=0)


class WgpuRenderer(NullDiagnosticRenderer):
    """Conservative WGPU renderer: Qt surface, clear pass, and grid pass."""

    _probe_cache: ClassVar[dict[RendererBackend, RendererCapabilities]] = {}
    _device_created: ClassVar[bool] = False

    def __init__(self, backend: RendererBackend = RendererBackend.WGPU_AUTO, settings: RendererSettings | None = None):
        super().__init__()
        settings = settings or RendererSettings()
        self._spec = _WgpuBackendSpec(
            backend=backend,
            name={
                RendererBackend.WGPU_D3D12: "WGPU Direct3D 12",
                RendererBackend.WGPU_VULKAN: "WGPU Vulkan",
                RendererBackend.WGPU_OPENGL: "WGPU OpenGL",
            }.get(backend, "WGPU Auto"),
            wgpu_backend_type=_WGPU_BACKENDS.get(backend, ""),
        )
        self.name = self._spec.name
        self.backend_id = self._spec.backend.value
        self.canvas = None
        self.adapter = None
        self.device = None
        self.queue = None
        self.context = None
        self.format = None
        self.depth_format = "depth24plus"
        self.depth_texture = None
        self.depth_view = None
        self._depth_size = (0, 0)
        self.pipeline_grid = None
        self.grid_bind_group = None
        self.grid_uniform_buffer = None
        self.grid_vertex_buffer = None
        self.grid_vertex_count = 0
        self.pipeline_mesh = None
        self.pipeline_mesh_cutout = None
        self.pipeline_mesh_blend = None
        self.pipeline_mesh_skinned = None
        self.pipeline_mesh_skinned_cutout = None
        self.pipeline_mesh_skinned_blend = None
        self.pipeline_lines = None
        self.pipeline_gizmo_lines = None
        self.pipeline_pick = None
        self.skeleton_resource: WgpuSkeletonResource | None = None
        self.mesh_pipeline_layout = None
        self.skinned_mesh_pipeline_layout = None
        self.line_bind_group_layout = None
        self.line_bind_group = None
        self.line_uniform_buffer = None
        self.mesh_bind_group_layout = None
        self.skin_bind_group_layout = None
        self.texture_bind_group_layout = None
        self.mesh_bind_group = None
        self.mesh_uniform_buffer = None
        self.light_buffer = None
        self.lighting_uniform_buffer = None
        self.light_resource: WgpuLightResource | None = None
        self._light_resource_revision_key = 0
        self.max_wgpu_lights = 64
        self.resource_cache = WgpuResourceCache(self)
        self.profiler = RendererProfiler(enabled=bool(settings.wgpu_profile_frames))
        self.enable_batching = bool(settings.wgpu_enable_batching)
        self.enable_instancing = bool(settings.wgpu_enable_instancing)
        self.enable_frustum_culling = bool(settings.wgpu_enable_frustum_culling)
        self.enable_lazy_upload = bool(settings.wgpu_enable_lazy_upload)
        self.enable_texture_arrays = bool(settings.wgpu_enable_texture_arrays)
        self.enable_texture_atlas = bool(settings.wgpu_enable_texture_atlas)
        self.enable_dynamic_quality = bool(settings.wgpu_dynamic_quality)
        self.max_texture_memory_mb = int(settings.wgpu_max_texture_memory_mb)
        self.max_uploads_per_frame = int(settings.wgpu_max_uploads_per_frame)
        self.dynamic_quality_large_scene_threshold = int(settings.dynamic_quality_large_scene_threshold)
        self.dynamic_quality_simplify_while_navigating = bool(settings.dynamic_quality_simplify_while_navigating)
        self.initialized = False
        self.live_surface = False
        self.textured_mesh_pipeline_status = "not created"
        self.alpha_pipeline_status = "not created"
        self.mesh_pipeline_status = "not created"
        self.line_pipeline_status = "not created"
        self.gizmo_pipeline_status = "not created"
        self.pick_pipeline_status = "not created"
        self.last_pick_diagnostics: dict[str, object] = {}
        self.grid_pipeline_status = "not created"
        self.last_error = ""
        self.last_display_mode_warning = ""
        self._last_size = (0, 0, 1.0)
        self._last_capabilities: RendererCapabilities | None = None
        self._clear_logged = False
        self._active_scene = None
        self._active_camera = None
        self._active_anim_pose = None
        self._active_anim_base_pose = None
        self._active_skeleton_render_data = None
        self._active_textures: dict = {}
        self._active_display_options = ViewportDisplayOptions()
        self._effective_display_options = self._active_display_options
        self._active_gizmo_render_data = None
        self._active_lighting_render_data = None
        self._active_picking_diagnostics: dict[str, object] = {}
        self._display_mode_downgrade = ""
        self.surface_host_diagnostics: dict[str, object] = {}
        self.perf = {"last_frame_ms": 0.0, "backend": self.backend_id, "tri_count": 0}
        self.performance_audit = {
            "bottlenecks": [
                "mesh adapter iteration happens on the Python render path",
                "per-mesh uniform writes remain necessary until instance buffers are active",
                "transparent meshes are sorted at mesh level only",
                "general KotOR textures remain individual sampled textures",
            ],
            "stage9_status": "profiling, batching order, culling, cache stats, pick reuse, and gizmo buffer reuse enabled",
        }
        self.show_grid = True
        self.show_texture = True
        self.show_diffuse_map = True
        self.show_lightmap_map = True
        self.show_light_gizmos = True
        self.show_light_radius_volumes = False
        self.selected_node = None
        self.selected_nodes = []
        self.hovered_node = None
        self.show_mesh_hover = True
        self.show_mesh_hover_edges = False
        self.scene_ambient = 0.06
        self.lighting_mode = "scene"
        self.shader_complexity_mode = "basic"
        self.lightmap_intensity = 0.55
        self.lightmap_mode = "baked"
        self.show_missing_texture_checker = False
        self.debug_texture_uploads = False
        self.force_untextured = False
        self.disable_lightmaps = False
        self.disable_alpha_blend = False
        self._last_render_counts = {
            "opaque": 0,
            "cutout": 0,
            "blended": 0,
            "edges": 0,
            "hovered_edges": 0,
            "selected_edges": 0,
            "skeleton_lines": 0,
            "joint_markers": 0,
            "light_helper_lines": 0,
            "light_volume_lines": 0,
            "gizmo_lines": 0,
        }
        self.skeleton_overlay_pipeline_status = "not created"
        self.skinned_mesh_pipeline_status = "not created"
        self.gpu_skinning_status = "not created"
        self.last_skinning_error = ""
        self.last_animation_error = ""
        self._active_skinned_mesh_count = 0
        self._active_cpu_skinned_mesh_count = 0
        self._active_total_mesh_count = 0
        self._active_visible_mesh_count = 0
        self._active_culled_mesh_count = 0
        self._last_batch_count = 0
        self._last_material_group_count = 0
        self._last_instance_group_count = 0
        self._last_instance_count = 0
        self._last_alpha_sort_ms = 0.0
        self._last_alpha_object_count = 0
        self._last_pipeline_switch_count = 0
        self._last_texture_array_eligible_groups = 0
        self._last_texture_array_eligible_textures = 0
        self._pending_uploads_count = 0
        self._last_upload_error = ""
        self._last_lighting_invalidation_reason = ""
        self._last_lighting_error = ""
        self._last_lighting_upload_time_ms = 0.0
        self._last_light_shader_active = False
        self._gizmo_line_cache: dict[tuple, tuple[object, int]] = {}
        self._frame_line_uniform_refs: list[tuple[object, object]] = []
        self._frame_mesh_uniform_refs: list[tuple[object, object]] = []
        self._pick_resources: WgpuPickResources | None = None
        self.grid_minor_color = (58 / 255.0, 64 / 255.0, 72 / 255.0)
        self.grid_major_color = (82 / 255.0, 90 / 255.0, 102 / 255.0)
        self.grid_x_axis_color = (118 / 255.0, 54 / 255.0, 54 / 255.0)
        self.grid_y_axis_color = (62 / 255.0, 112 / 255.0, 68 / 255.0)
        self.wire_color = (0.18, 0.62, 0.95)
        self.hidden_line_color = (0.02, 0.025, 0.03)
        self.hovered_edge_color = (0.0, 215 / 255.0, 181 / 255.0)
        self.hovered_edge_alpha = 0.45
        self.selected_edge_color = SELECTION_YELLOW
        self.null_helper_color = (0.64, 0.72, 0.82)
        self.light_helper_palette = dict(LIGHT_HELPER_COLORS)
        self.light_helper_palette["light"] = LIGHT_HELPER_COLORS["point"]
        self.missing_texture_color_a = (1.0, 0.0, 1.0)
        self.missing_texture_color_b = (0.0, 0.0, 0.0)

    @staticmethod
    def probe_availability(backend: RendererBackend = RendererBackend.WGPU_AUTO) -> RendererCapabilities:
        cached = WgpuRenderer._probe_cache.get(backend)
        if cached is not None:
            return cached

        spec = _WgpuBackendSpec(
            backend=backend,
            name={
                RendererBackend.WGPU_D3D12: "WGPU Direct3D 12",
                RendererBackend.WGPU_VULKAN: "WGPU Vulkan",
                RendererBackend.WGPU_OPENGL: "WGPU OpenGL",
            }.get(backend, "WGPU Auto"),
            wgpu_backend_type=_WGPU_BACKENDS.get(backend, ""),
        )

        if importlib_util.find_spec("wgpu") is None:
            caps = WgpuRenderer._capabilities_unavailable(spec, "wgpu is not installed")
            WgpuRenderer._probe_cache[backend] = caps
            return caps
        if importlib_util.find_spec("rendercanvas") is None:
            caps = WgpuRenderer._capabilities_unavailable(spec, "rendercanvas is not installed")
            WgpuRenderer._probe_cache[backend] = caps
            return caps
        if backend == RendererBackend.WGPU_D3D12 and os.name != "nt":
            caps = WgpuRenderer._capabilities_unavailable(spec, "WGPU Direct3D 12 is available on Windows only")
            WgpuRenderer._probe_cache[backend] = caps
            return caps

        env = os.environ.copy()
        env.setdefault("PYTHONPATH", os.getcwd())
        if spec.wgpu_backend_type:
            env[_WGPU_BACKEND_ENV] = spec.wgpu_backend_type
        else:
            env.pop(_WGPU_BACKEND_ENV, None)
        try:
            completed = subprocess.run(
                [sys.executable, "-c", _probe_script()],
                capture_output=True,
                text=True,
                timeout=10.0,
                env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as exc:
            caps = WgpuRenderer._capabilities_unavailable(spec, f"failed to probe WGPU surface: {exc}")
            WgpuRenderer._probe_cache[backend] = caps
            return caps

        payload = {}
        for line in reversed((completed.stdout or "").splitlines()):
            try:
                payload = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
        if completed.returncode != 0 and not payload:
            reason = (completed.stderr or completed.stdout or "WGPU probe failed").strip().splitlines()[-1]
            caps = WgpuRenderer._capabilities_unavailable(spec, reason)
        elif not bool(payload.get("available")):
            caps = WgpuRenderer._capabilities_unavailable(
                spec,
                str(payload.get("reason") or "failed to create WGPU Qt surface/device"),
                details=payload,
            )
        else:
            details = {
                "wgpu_installed": True,
                "rendercanvas_installed": True,
                "requested_backend_type": spec.wgpu_backend_type or "auto",
                "format": payload.get("format"),
                "adapter": payload.get("adapter") or {},
                "env_var": _WGPU_BACKEND_ENV,
            }
            caps = RendererCapabilities(
                backend_id=backend.value,
                name=spec.name,
                available=True,
                reason="",
                api="WGPU",
                supports_scene_meshes=True,
                supports_textures=True,
                supports_grid=True,
                supports_overlays=True,
                supports_hot_switch=True,
                requires_restart=True,
                diagnostic_only=False,
                supports_object_picking=True,
                supports_cpu_ray_picking=True,
                supports_gpu_id_picking=True,
                supports_selection_highlight=True,
                supports_gizmo_drawing=True,
                supports_gizmo_interaction=True,
                skeleton_overlay_supported=True,
                joint_dot_overlay_supported=True,
                bone_selection_supported=True,
                skinned_mesh_supported=True,
                gpu_skinning_supported=True,
                cpu_skinning_fallback_supported=False,
                animation_preview_supported=True,
                skin_weight_heatmap_supported=False,
                max_supported_bones=128,
                bone_matrix_buffer_type="storage-buffer",
                skinned_shader_status="available",
                supports_marquee_selection=True,
                supports_subobject_selection=True,
                supports_batching=True,
                supports_instancing=True,
                supports_texture_streaming=True,
                supports_texture_arrays=False,
                supports_atlas=False,
                supports_frustum_culling=True,
                supports_gpu_timing=False,
                supports_dynamic_quality=True,
                supported_display_modes=WGPU_DISPLAY_MODES,
                supported_display_options=(
                    "show_grid",
                    "show_wire_overlay",
                    "show_edged_faces",
                    "show_textures",
                    "show_lightmaps",
                    "show_material_colour",
                    "show_alpha",
                    "two_sided",
                    "force_unlit",
                    "force_flat_colour",
                ),
                fallback_display_modes=WGPU_FALLBACK_DISPLAY_MODES,
                details=details,
            )
        WgpuRenderer._probe_cache[backend] = caps
        return caps

    @staticmethod
    def _capabilities_unavailable(
        spec: _WgpuBackendSpec,
        reason: str,
        *,
        details: dict[str, object] | None = None,
    ) -> RendererCapabilities:
        details = dict(details or {})
        details.setdefault("wgpu_installed", importlib_util.find_spec("wgpu") is not None)
        details.setdefault("rendercanvas_installed", importlib_util.find_spec("rendercanvas") is not None)
        details.setdefault("requested_backend_type", spec.wgpu_backend_type or "auto")
        details.setdefault("env_var", _WGPU_BACKEND_ENV)
        return RendererCapabilities(
            backend_id=spec.backend.value,
            name=spec.name,
            available=False,
            reason=reason,
            api="WGPU",
            supports_scene_meshes=False,
            supports_textures=False,
            supports_grid=False,
            supports_overlays=True,
            supports_hot_switch=True,
            requires_restart=True,
            diagnostic_only=False,
            supports_object_picking=False,
            supports_cpu_ray_picking=False,
            supports_gpu_id_picking=False,
            supports_selection_highlight=False,
            supports_gizmo_drawing=False,
            supports_gizmo_interaction=False,
            skeleton_overlay_supported=False,
            joint_dot_overlay_supported=False,
            bone_selection_supported=False,
            skinned_mesh_supported=False,
            gpu_skinning_supported=False,
            cpu_skinning_fallback_supported=False,
            animation_preview_supported=False,
            skin_weight_heatmap_supported=False,
            max_supported_bones=0,
            bone_matrix_buffer_type="",
            skinned_shader_status="unavailable",
            supports_marquee_selection=False,
            supports_subobject_selection=False,
            supports_batching=False,
            supports_instancing=False,
            supports_texture_streaming=False,
            supports_texture_arrays=False,
            supports_atlas=False,
            supports_frustum_culling=False,
            supports_gpu_timing=False,
            supports_dynamic_quality=False,
            supported_display_modes=(),
            supported_display_options=(),
            fallback_display_modes=WGPU_FALLBACK_DISPLAY_MODES,
            details=details,
        )

    def is_available(self) -> bool:
        caps = self.get_capabilities()
        return bool(caps.available)

    def get_capabilities(self) -> RendererCapabilities:
        caps = self._last_capabilities or self.probe_availability(self._spec.backend)
        self._last_capabilities = caps
        return caps

    def create_viewport_widget(self, parent=None):
        try:
            from PySide6 import QtCore, QtWidgets  # noqa: F401 - selects the Qt binding for rendercanvas
            from rendercanvas.qt import QRenderWidget
        except Exception as exc:
            self.last_error = str(exc)
            raise RuntimeError(f"failed to create WGPU Qt surface: {exc}") from exc
        widget = QRenderWidget(parent)
        widget.setObjectName("WgpuViewportSurface")
        widget.setFocusPolicy(QtCore.Qt.StrongFocus)
        widget.setMouseTracking(True)
        log.info("WgpuRenderer: rendercanvas QRenderWidget created")
        return widget

    def create_surface_widget(self, parent=None):
        self.canvas = self.create_viewport_widget(parent)
        return self.canvas

    def _ensure_backend_env(self) -> None:
        if self.initialized or not self._spec.wgpu_backend_type:
            return
        current = os.environ.get(_WGPU_BACKEND_ENV)
        if current != self._spec.wgpu_backend_type:
            if WgpuRenderer._device_created:
                raise RuntimeError(
                    f"{_WGPU_BACKEND_ENV} must be set before the first WGPU device is created; "
                    "restart GhostRigger to switch WGPU backend"
                )
            os.environ[_WGPU_BACKEND_ENV] = self._spec.wgpu_backend_type
            log.info("WgpuRenderer: %s=%s", _WGPU_BACKEND_ENV, self._spec.wgpu_backend_type)

    def initialize(self, viewport_widget=None, scene_context=None) -> None:
        if self.initialized:
            return
        self._ensure_backend_env()
        try:
            import wgpu

            if viewport_widget is None and self.canvas is not None:
                viewport_widget = self.canvas
            if viewport_widget is None:
                viewport_widget = self.create_viewport_widget(None)
            self.canvas = viewport_widget
            self.context = self.canvas.get_context("wgpu")
            self.adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
            if self.adapter is None:
                raise RuntimeError("no suitable WGPU adapter found")
            log.info("WgpuRenderer: adapter selected: %s", _adapter_info_dict(self.adapter))
            self.device = self.adapter.request_device_sync(required_features=[], required_limits={})
            WgpuRenderer._device_created = True
            self.queue = self.device.queue
            self.format = self.context.get_preferred_format(self.adapter)
            self.context.configure(device=self.device, format=self.format)
            log.info("WgpuRenderer: device created")
            log.info("WgpuRenderer: canvas/context configured")
            self.live_surface = viewport_widget is not None
            self._create_grid_pipeline()
            self._create_mesh_pipeline()
            try:
                self._create_line_pipeline()
            except Exception as exc:
                self.pipeline_lines = None
                self.line_pipeline_status = f"unavailable: {exc}"
                self.last_display_mode_warning = f"WGPU line pipeline unavailable: {exc}"
                log.warning("WgpuRenderer: line pipeline unavailable: %s", exc)
            try:
                self._create_gizmo_line_pipeline()
            except Exception as exc:
                self.pipeline_gizmo_lines = None
                self.gizmo_pipeline_status = f"unavailable: {exc}"
                log.warning("WgpuRenderer: gizmo line pipeline unavailable: %s", exc)
            try:
                self._create_pick_pipeline()
            except Exception as exc:
                self.pipeline_pick = None
                self.pick_pipeline_status = f"unavailable: {exc}"
                log.warning("WgpuRenderer: pick pipeline unavailable: %s", exc)
            self.canvas.request_draw(self._draw_to_canvas)
            self.initialized = True
        except Exception as exc:
            self.last_error = str(exc)
            self.initialized = False
            raise RuntimeError(f"failed to create WGPU adapter/device/context: {exc}") from exc

    def resize(self, width: int, height: int, device_pixel_ratio: float = 1.0) -> None:
        if width <= 0 or height <= 0:
            return
        self._last_size = (int(width), int(height), float(device_pixel_ratio or 1.0))
        if self.canvas is not None:
            try:
                self.canvas.resize(int(width), int(height))
            except Exception:
                pass
            try:
                # A QRenderWidget only receives a real physical size after it is
                # shown. Seed rendercanvas for offscreen/early resize calls.
                self.canvas._size_info.set_physical_size(
                    max(1, int(round(width * device_pixel_ratio))),
                    max(1, int(round(height * device_pixel_ratio))),
                    float(device_pixel_ratio or 1.0),
                )
            except Exception:
                pass
        self._ensure_depth_texture(
            max(1, int(round(width * float(device_pixel_ratio or 1.0)))),
            max(1, int(round(height * float(device_pixel_ratio or 1.0)))),
        )

    def _ensure_depth_texture(self, width: int, height: int) -> None:
        import wgpu

        if self.device is None or width <= 0 or height <= 0:
            return
        size = (int(width), int(height))
        if self.depth_texture is not None and self._depth_size == size:
            return
        self.depth_texture = self.device.create_texture(
            size=(size[0], size[1], 1),
            usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
            dimension=wgpu.TextureDimension.d2,
            format=self.depth_format,
            mip_level_count=1,
            sample_count=1,
        )
        self.depth_view = self.depth_texture.create_view()
        self._depth_size = size

    def _target_rgb(self, color: tuple[float, ...]) -> tuple[float, float, float]:
        rgb = tuple(max(0.0, min(1.0, float(channel))) for channel in color[:3])
        return _srgb_to_linear(rgb) if _format_is_srgb(self.format) else rgb

    def _target_rgba(self, color: tuple[float, ...]) -> tuple[float, float, float, float]:
        rgb = self._target_rgb(color)
        alpha = float(color[3]) if len(color) >= 4 else 1.0
        return (*rgb, max(0.0, min(1.0, alpha)))

    def _create_grid_pipeline(self) -> None:
        import numpy as np
        import wgpu

        extent = 60
        major_every = 5
        rows: list[tuple[float, float, float, float, float, float]] = []
        for i in range(-extent, extent + 1):
            color = self.grid_x_axis_color if i == 0 else (self.grid_major_color if i % major_every == 0 else self.grid_minor_color)
            color = self._target_rgb(color)
            rows.append((-extent, i, 0.0, *color))
            rows.append((extent, i, 0.0, *color))
        for i in range(-extent, extent + 1):
            color = self.grid_y_axis_color if i == 0 else (self.grid_major_color if i % major_every == 0 else self.grid_minor_color)
            color = self._target_rgb(color)
            rows.append((i, -extent, 0.0, *color))
            rows.append((i, extent, 0.0, *color))

        data = np.asarray(rows, dtype=np.float32)
        self.grid_vertex_count = int(data.shape[0])
        self.grid_vertex_buffer = self.device.create_buffer_with_data(data=data, usage=wgpu.BufferUsage.VERTEX)
        self.grid_uniform_buffer = self.device.create_buffer(size=64, usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST)
        bind_group_layout = self.device.create_bind_group_layout(
            entries=[
                {
                    "binding": 0,
                    "visibility": wgpu.ShaderStage.VERTEX,
                    "buffer": {"type": wgpu.BufferBindingType.uniform},
                }
            ]
        )
        self.grid_bind_group = self.device.create_bind_group(
            layout=bind_group_layout,
            entries=[
                {
                    "binding": 0,
                    "resource": {"buffer": self.grid_uniform_buffer, "offset": 0, "size": 64},
                }
            ],
        )
        pipeline_layout = self.device.create_pipeline_layout(bind_group_layouts=[bind_group_layout])
        shader = self.device.create_shader_module(code=_GRID_WGSL)
        self.pipeline_grid = self.device.create_render_pipeline(
            layout=pipeline_layout,
            vertex={
                "module": shader,
                "entry_point": "vs_main",
                "buffers": [
                    {
                        "array_stride": 24,
                        "step_mode": wgpu.VertexStepMode.vertex,
                        "attributes": [
                            {"format": wgpu.VertexFormat.float32x3, "offset": 0, "shader_location": 0},
                            {"format": wgpu.VertexFormat.float32x3, "offset": 12, "shader_location": 1},
                        ],
                    }
                ],
            },
            primitive={"topology": wgpu.PrimitiveTopology.line_list},
            depth_stencil={
                "format": self.depth_format,
                "depth_write_enabled": False,
                "depth_compare": wgpu.CompareFunction.less_equal,
            },
            multisample=None,
            fragment={
                "module": shader,
                "entry_point": "fs_main",
                "targets": [{"format": self.format}],
            },
        )
        self.grid_pipeline_status = "ready"

    def _create_mesh_pipeline(self) -> None:
        import wgpu

        self.mesh_uniform_buffer = self.device.create_buffer(
            size=112,
            usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST,
        )
        self.light_buffer = self.device.create_buffer(
            size=int(self.max_wgpu_lights) * 64,
            usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST,
        )
        self.lighting_uniform_buffer = self.device.create_buffer(
            size=32,
            usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST,
        )
        self.mesh_bind_group_layout = self.device.create_bind_group_layout(
            entries=[
                {
                    "binding": 0,
                    "visibility": wgpu.ShaderStage.VERTEX | wgpu.ShaderStage.FRAGMENT,
                    "buffer": {"type": wgpu.BufferBindingType.uniform},
                },
                {
                    "binding": 1,
                    "visibility": wgpu.ShaderStage.FRAGMENT,
                    "buffer": {"type": wgpu.BufferBindingType.read_only_storage},
                },
                {
                    "binding": 2,
                    "visibility": wgpu.ShaderStage.FRAGMENT,
                    "buffer": {"type": wgpu.BufferBindingType.uniform},
                },
            ]
        )
        self.texture_bind_group_layout = self.device.create_bind_group_layout(
            entries=[
                {
                    "binding": 0,
                    "visibility": wgpu.ShaderStage.FRAGMENT,
                    "texture": {"sample_type": wgpu.TextureSampleType.float, "view_dimension": wgpu.TextureViewDimension.d2},
                },
                {
                    "binding": 1,
                    "visibility": wgpu.ShaderStage.FRAGMENT,
                    "sampler": {"type": wgpu.SamplerBindingType.filtering},
                },
                {
                    "binding": 2,
                    "visibility": wgpu.ShaderStage.FRAGMENT,
                    "texture": {"sample_type": wgpu.TextureSampleType.float, "view_dimension": wgpu.TextureViewDimension.d2},
                },
                {
                    "binding": 3,
                    "visibility": wgpu.ShaderStage.FRAGMENT,
                    "sampler": {"type": wgpu.SamplerBindingType.filtering},
                },
            ]
        )
        self.skin_bind_group_layout = self.device.create_bind_group_layout(
            entries=[
                {
                    "binding": 0,
                    "visibility": wgpu.ShaderStage.VERTEX,
                    "buffer": {"type": wgpu.BufferBindingType.read_only_storage},
                }
            ]
        )
        self.mesh_bind_group = self.device.create_bind_group(
            layout=self.mesh_bind_group_layout,
            entries=[
                {
                    "binding": 0,
                    "resource": {"buffer": self.mesh_uniform_buffer, "offset": 0, "size": 112},
                },
                {
                    "binding": 1,
                    "resource": {"buffer": self.light_buffer, "offset": 0, "size": int(self.max_wgpu_lights) * 64},
                },
                {
                    "binding": 2,
                    "resource": {"buffer": self.lighting_uniform_buffer, "offset": 0, "size": 32},
                },
            ],
        )
        self.mesh_pipeline_layout = self.device.create_pipeline_layout(
            bind_group_layouts=[self.mesh_bind_group_layout, self.texture_bind_group_layout]
        )
        self.skinned_mesh_pipeline_layout = self.device.create_pipeline_layout(
            bind_group_layouts=[self.mesh_bind_group_layout, self.texture_bind_group_layout, self.skin_bind_group_layout]
        )
        shader = self.device.create_shader_module(code=_load_mesh_shader())
        self.pipeline_mesh = self._create_textured_pipeline(
            shader,
            blend=False,
            depth_write=True,
            alpha_label="opaque",
        )
        self.pipeline_mesh_cutout = self._create_textured_pipeline(
            shader,
            blend=False,
            depth_write=True,
            alpha_label="cutout",
        )
        self.pipeline_mesh_blend = self._create_textured_pipeline(
            shader,
            blend=True,
            depth_write=False,
            alpha_label="blend",
        )
        self.mesh_pipeline_status = "ready"
        self.textured_mesh_pipeline_status = "ready"
        self.alpha_pipeline_status = "ready"
        try:
            skinned_shader = self.device.create_shader_module(code=_load_skinned_mesh_shader())
            self.pipeline_mesh_skinned = self._create_textured_pipeline(
                skinned_shader,
                blend=False,
                depth_write=True,
                alpha_label="skinned opaque",
                skinned=True,
            )
            self.pipeline_mesh_skinned_cutout = self._create_textured_pipeline(
                skinned_shader,
                blend=False,
                depth_write=True,
                alpha_label="skinned cutout",
                skinned=True,
            )
            self.pipeline_mesh_skinned_blend = self._create_textured_pipeline(
                skinned_shader,
                blend=True,
                depth_write=False,
                alpha_label="skinned blend",
                skinned=True,
            )
            self.skinned_mesh_pipeline_status = "ready"
            self.gpu_skinning_status = "ready"
        except Exception as exc:
            self.pipeline_mesh_skinned = None
            self.pipeline_mesh_skinned_cutout = None
            self.pipeline_mesh_skinned_blend = None
            self.skinned_mesh_pipeline_status = f"unavailable: {exc}"
            self.gpu_skinning_status = "unavailable"
            self.last_skinning_error = f"WGPU skinned shader unavailable: {exc}"
            log.warning("WgpuRenderer: skinned mesh pipeline unavailable: %s", exc)
        log.info("WgpuRenderer: textured mesh pipeline created")

    def _create_textured_pipeline(self, shader, *, blend: bool, depth_write: bool, alpha_label: str, skinned: bool = False):
        import wgpu

        target = {"format": self.format}
        if blend:
            target["blend"] = {
                "color": {
                    "src_factor": wgpu.BlendFactor.src_alpha,
                    "dst_factor": wgpu.BlendFactor.one_minus_src_alpha,
                    "operation": wgpu.BlendOperation.add,
                },
                "alpha": {
                    "src_factor": wgpu.BlendFactor.one,
                    "dst_factor": wgpu.BlendFactor.one_minus_src_alpha,
                    "operation": wgpu.BlendOperation.add,
                },
            }
            target["write_mask"] = wgpu.ColorWrite.ALL
        return self.device.create_render_pipeline(
            label=f"WGPU textured mesh {alpha_label}",
            layout=self.skinned_mesh_pipeline_layout if skinned else self.mesh_pipeline_layout,
            vertex={
                "module": shader,
                "entry_point": "vs_main",
                "buffers": [
                    {
                        "array_stride": 72,
                        "step_mode": wgpu.VertexStepMode.vertex,
                        "attributes": [
                            {"format": wgpu.VertexFormat.float32x3, "offset": 0, "shader_location": 0},
                            {"format": wgpu.VertexFormat.float32x3, "offset": 12, "shader_location": 1},
                            {"format": wgpu.VertexFormat.float32x2, "offset": 24, "shader_location": 2},
                            {"format": wgpu.VertexFormat.float32x2, "offset": 32, "shader_location": 3},
                            *(
                                [
                                    {"format": wgpu.VertexFormat.uint32x4, "offset": 40, "shader_location": 4},
                                    {"format": wgpu.VertexFormat.float32x4, "offset": 56, "shader_location": 5},
                                ]
                                if skinned
                                else []
                            ),
                        ],
                    }
                ],
            },
            primitive={
                "topology": wgpu.PrimitiveTopology.triangle_list,
                "front_face": wgpu.FrontFace.cw,
                "cull_mode": wgpu.CullMode.none,
            },
            depth_stencil={
                "format": self.depth_format,
                "depth_write_enabled": bool(depth_write),
                "depth_compare": wgpu.CompareFunction.less_equal,
            },
            multisample=None,
            fragment={
                "module": shader,
                "entry_point": "fs_main",
                "targets": [target],
            },
        )

    def _create_line_pipeline(self) -> None:
        import wgpu

        self.line_uniform_buffer = self.device.create_buffer(
            size=80,
            usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST,
        )
        self.line_bind_group_layout = self.device.create_bind_group_layout(
            entries=[
                {
                    "binding": 0,
                    "visibility": wgpu.ShaderStage.VERTEX | wgpu.ShaderStage.FRAGMENT,
                    "buffer": {"type": wgpu.BufferBindingType.uniform},
                }
            ]
        )
        self.line_bind_group = self.device.create_bind_group(
            layout=self.line_bind_group_layout,
            entries=[
                {
                    "binding": 0,
                    "resource": {"buffer": self.line_uniform_buffer, "offset": 0, "size": 80},
                }
            ],
        )
        pipeline_layout = self.device.create_pipeline_layout(bind_group_layouts=[self.line_bind_group_layout])
        shader = self.device.create_shader_module(code=_LINE_WGSL)
        self.pipeline_lines = self.device.create_render_pipeline(
            label="WGPU mesh edge lines",
            layout=pipeline_layout,
            vertex={
                "module": shader,
                "entry_point": "vs_main",
                "buffers": [
                    {
                        "array_stride": 72,
                        "step_mode": wgpu.VertexStepMode.vertex,
                        "attributes": [
                            {"format": wgpu.VertexFormat.float32x3, "offset": 0, "shader_location": 0},
                        ],
                    }
                ],
            },
            primitive={"topology": wgpu.PrimitiveTopology.line_list},
            depth_stencil={
                "format": self.depth_format,
                "depth_write_enabled": False,
                "depth_compare": wgpu.CompareFunction.less_equal,
            },
            multisample=None,
            fragment={
                "module": shader,
                "entry_point": "fs_main",
                "targets": [
                    {
                        "format": self.format,
                        "blend": {
                            "color": {
                                "src_factor": wgpu.BlendFactor.src_alpha,
                                "dst_factor": wgpu.BlendFactor.one_minus_src_alpha,
                                "operation": wgpu.BlendOperation.add,
                            },
                            "alpha": {
                                "src_factor": wgpu.BlendFactor.one,
                                "dst_factor": wgpu.BlendFactor.one_minus_src_alpha,
                                "operation": wgpu.BlendOperation.add,
                            },
                        },
                    }
                ],
            },
        )
        self.line_pipeline_status = "ready"

    def _create_gizmo_line_pipeline(self) -> None:
        import wgpu

        if self.line_bind_group_layout is None:
            self._create_line_pipeline()
        pipeline_layout = self.device.create_pipeline_layout(bind_group_layouts=[self.line_bind_group_layout])
        shader = self.device.create_shader_module(code=_LINE_WGSL)
        self.pipeline_gizmo_lines = self.device.create_render_pipeline(
            label="WGPU gizmo overlay lines",
            layout=pipeline_layout,
            vertex={
                "module": shader,
                "entry_point": "vs_main",
                "buffers": [
                    {
                        "array_stride": 12,
                        "step_mode": wgpu.VertexStepMode.vertex,
                        "attributes": [
                            {"format": wgpu.VertexFormat.float32x3, "offset": 0, "shader_location": 0},
                        ],
                    }
                ],
            },
            primitive={"topology": wgpu.PrimitiveTopology.line_list},
            depth_stencil={
                "format": self.depth_format,
                "depth_write_enabled": False,
                "depth_compare": wgpu.CompareFunction.always,
            },
            multisample=None,
            fragment={
                "module": shader,
                "entry_point": "fs_main",
                "targets": [{"format": self.format}],
            },
        )
        self.gizmo_pipeline_status = "ready"

    def _create_pick_pipeline(self) -> None:
        import wgpu

        if self.line_bind_group_layout is None:
            self._create_line_pipeline()
        pipeline_layout = self.device.create_pipeline_layout(bind_group_layouts=[self.line_bind_group_layout])
        shader = self.device.create_shader_module(code=_PICK_WGSL)
        self.pipeline_pick = self.device.create_render_pipeline(
            label="WGPU object ID picking",
            layout=pipeline_layout,
            vertex={
                "module": shader,
                "entry_point": "vs_main",
                "buffers": [
                    {
                        "array_stride": 72,
                        "step_mode": wgpu.VertexStepMode.vertex,
                        "attributes": [
                            {"format": wgpu.VertexFormat.float32x3, "offset": 0, "shader_location": 0},
                        ],
                    }
                ],
            },
            primitive={"topology": wgpu.PrimitiveTopology.triangle_list},
            depth_stencil={
                "format": self.depth_format,
                "depth_write_enabled": True,
                "depth_compare": wgpu.CompareFunction.less_equal,
            },
            multisample=None,
            fragment={
                "module": shader,
                "entry_point": "fs_main",
                "targets": [{"format": "rgba8unorm"}],
            },
        )
        self.pick_pipeline_status = "ready"

    def _camera_mvp(self, camera, width: int, height: int) -> bytes:
        return _mat4_tobytes(self._camera_mvp_matrix(camera, width, height))

    def _draw_to_canvas(self) -> None:
        import wgpu

        if self.context is None or self.device is None:
            return
        width, height = self.canvas.get_physical_size()
        self._ensure_depth_texture(int(width), int(height))
        view = self.context.get_current_texture().create_view()
        encoder = self.device.create_command_encoder()
        render_pass = encoder.begin_render_pass(
            color_attachments=[
                {
                    "view": view,
                    "resolve_target": None,
                    "clear_value": self._target_rgba((*tuple(self.viewport_background[:3]), 1.0)),
                    "load_op": wgpu.LoadOp.clear,
                    "store_op": wgpu.StoreOp.store,
                }
            ],
            depth_stencil_attachment={
                "view": self.depth_view,
                "depth_clear_value": 1.0,
                "depth_load_op": wgpu.LoadOp.clear,
                "depth_store_op": wgpu.StoreOp.store,
            }
            if self.depth_view is not None
            else None,
        )
        if self.show_grid and self.pipeline_grid is not None and self.grid_vertex_buffer is not None:
            self.queue.write_buffer(self.grid_uniform_buffer, 0, self._camera_mvp(self._active_camera, width, height))
            render_pass.set_pipeline(self.pipeline_grid)
            render_pass.set_bind_group(0, self.grid_bind_group)
            render_pass.set_vertex_buffer(0, self.grid_vertex_buffer)
            render_pass.draw(self.grid_vertex_count, 1, 0, 0)
            self.profiler.add("draw_calls", 1)
        with self.profiler.section("cpu_prepare"):
            self._draw_meshes(render_pass, width, height)
        with self.profiler.section("skeleton"):
            skeleton_counts = self._draw_skeleton_overlay(render_pass, width, height)
        self._last_render_counts["skeleton_lines"] = skeleton_counts[0]
        self._last_render_counts["joint_markers"] = skeleton_counts[1]
        with self.profiler.section("lights"):
            light_counts = self._draw_light_overlays(render_pass, width, height)
        self._last_render_counts["light_helper_lines"] = light_counts[0]
        self._last_render_counts["light_volume_lines"] = light_counts[1]
        with self.profiler.section("gizmo"):
            self._last_render_counts["gizmo_lines"] = self._draw_gizmo_lines(render_pass, width, height)
        render_pass.end()
        with self.profiler.section("gpu_submit"):
            self.queue.submit([encoder.finish()])

    def _display_options_from_legacy_flags(self) -> ViewportDisplayOptions:
        if bool(getattr(self, "show_wireframe", False)) and not bool(getattr(self, "show_solid", True)):
            mode = ViewportDisplayMode.WIREFRAME
        else:
            render_mode = str(getattr(self, "render_mode", "realistic") or "realistic").lower()
            if render_mode == "flat":
                mode = ViewportDisplayMode.SOLID
            elif render_mode == "shaded":
                mode = ViewportDisplayMode.SHADED
            elif bool(getattr(self, "show_texture", True)) and bool(getattr(self, "show_lightmap_map", True)):
                mode = ViewportDisplayMode.TEXTURED_LIGHTMAPPED
            elif bool(getattr(self, "show_texture", True)):
                mode = ViewportDisplayMode.TEXTURED
            else:
                mode = ViewportDisplayMode.SOLID
        return ViewportDisplayOptions(
            display_mode=mode,
            show_grid=bool(getattr(self, "show_grid", True)),
            show_wire_overlay=bool(getattr(self, "show_wireframe", False) and getattr(self, "show_solid", True)),
            show_edged_faces=bool(getattr(self, "show_wireframe", False) and getattr(self, "show_solid", True)),
            show_textures=bool(getattr(self, "show_texture", True)),
            show_lightmaps=bool(getattr(self, "show_lightmap_map", True)),
            show_alpha=not bool(getattr(self, "disable_alpha_blend", False)),
            two_sided=not bool(getattr(self, "cull_faces", False)),
            force_flat_colour=str(getattr(self, "render_mode", "") or "").lower() == "flat",
        )

    def _coerce_display_options(self, options: ViewportDisplayOptions) -> ViewportDisplayOptions:
        mode = normalize_display_mode(options.display_mode)
        warning = ""
        if mode is ViewportDisplayMode.FULL_MATERIAL:
            mode = ViewportDisplayMode.TEXTURED_LIGHTMAPPED
            warning = "WGPU uses basic material mode; advanced TXI/env/specular effects remain ModernGL-only."
        elif mode in {ViewportDisplayMode.NORMALS_DEBUG, ViewportDisplayMode.UV_DEBUG}:
            mode = ViewportDisplayMode.SHADED if mode is ViewportDisplayMode.NORMALS_DEBUG else ViewportDisplayMode.TEXTURED
            warning = f"WGPU debug mode is deferred; using {mode.value}."
        elif mode is ViewportDisplayMode.BOUNDING_BOX:
            mode = ViewportDisplayMode.SOLID
            warning = "WGPU bounding-box display is deferred; using solid mode."
        coerced = options.with_changes(display_mode=mode)
        self._display_mode_downgrade = "" if coerced.display_mode is options.display_mode else f"{options.display_mode.value}->{coerced.display_mode.value}"
        self.last_display_mode_warning = warning
        return coerced

    def _draw_meshes(self, render_pass, width: int, height: int) -> None:
        import wgpu

        if self.pipeline_mesh is None or self.mesh_uniform_buffer is None or self.mesh_bind_group is None:
            return
        if self._active_scene is None:
            self.perf["tri_count"] = 0
            return
        try:
            from src.gui.rendering.mesh_render_data import iter_mesh_render_data
        except Exception as exc:
            self.last_error = f"mesh adapter unavailable: {exc}"
            return

        display_options = self._coerce_display_options(self._active_display_options)
        self._effective_display_options = display_options
        self._ensure_light_resource()
        mode = display_options.display_mode
        draw_surface = mode is not ViewportDisplayMode.WIREFRAME
        edge_only = mode is ViewportDisplayMode.WIREFRAME
        edge_overlay = bool(
            edge_only
            or mode is ViewportDisplayMode.HIDDEN_LINE
            or display_options.show_wire_overlay
            or display_options.show_edged_faces
        )
        force_untextured = (
            bool(getattr(self, "force_untextured", False))
            or not display_options.show_textures
            or mode is ViewportDisplayMode.HIDDEN_LINE
        )
        force_no_lightmaps = (
            bool(getattr(self, "disable_lightmaps", False))
            or not display_options.show_lightmaps
            or mode not in {ViewportDisplayMode.TEXTURED_LIGHTMAPPED, ViewportDisplayMode.FULL_MATERIAL}
        )
        mvp = self._camera_mvp_matrix(self._active_camera, width, height)
        frustum_planes = None
        if bool(getattr(self, "enable_frustum_culling", True)):
            try:
                frustum_planes = extract_frustum_planes(mvp)
            except Exception as exc:
                self.last_display_mode_warning = f"WGPU frustum culling disabled for this frame: {exc}"
                frustum_planes = None
        tri_count = 0
        skinned_mesh_count = 0
        cpu_skinned_mesh_count = 0
        total_mesh_count = 0
        visible_mesh_count = 0
        culled_mesh_count = 0
        draw_items = []
        edge_items = []
        for mesh_data in iter_mesh_render_data(
            self._active_scene,
            anim_pose=self._active_anim_pose,
            anim_base_pose=self._active_anim_base_pose,
            textures=self._active_textures,
            allow_cpu_skinning=False,
        ):
            total_mesh_count += 1
            if frustum_planes is not None and self._mesh_data_outside_frustum(mesh_data, frustum_planes):
                culled_mesh_count += 1
                continue
            visible_mesh_count += 1
            material_data = getattr(mesh_data, "material", None)
            if material_data is None:
                continue
            if bool(getattr(mesh_data, "is_skinned", False)):
                skinned_mesh_count += 1
                if bool(getattr(mesh_data, "skinning_cpu_fallback", False)):
                    cpu_skinned_mesh_count += 1
                warning = str(getattr(mesh_data, "skinning_warning", "") or "")
                if warning:
                    self.last_skinning_error = warning
            alpha_mode = str(getattr(material_data, "alpha_mode", "OPAQUE") or "OPAQUE").upper()
            if (bool(getattr(self, "disable_alpha_blend", False)) or not display_options.show_alpha) and alpha_mode == "BLEND":
                alpha_mode = "OPAQUE"
            if force_untextured:
                material_data = self._untextured_material(material_data)
                alpha_mode = str(getattr(material_data, "alpha_mode", "OPAQUE") or "OPAQUE").upper()
            elif force_no_lightmaps:
                material_data = self._without_lightmap_material(material_data)
            sort_depth = 0.0
            if alpha_mode == "BLEND":
                sort_depth = self._mesh_sort_depth(mesh_data, self._active_camera)
            draw_items.append((alpha_mode, sort_depth, mesh_data, material_data))
            edge_items.append(mesh_data)

        opaque = [item for item in draw_items if item[0] == "OPAQUE"]
        cutout = [item for item in draw_items if item[0] in {"MASK", "CUTOUT"}]
        blended = [item for item in draw_items if item[0] == "BLEND"]
        alpha_sort_started = time.perf_counter()
        blended.sort(key=lambda item: item[1], reverse=True)
        self._last_alpha_sort_ms = (time.perf_counter() - alpha_sort_started) * 1000.0
        self._last_alpha_object_count = len(blended)
        instance_stats = instancing_summary(draw_items) if bool(getattr(self, "enable_instancing", True)) else {"instance_group_count": 0, "instance_count": 0}
        counts = {
            "opaque": 0,
            "cutout": 0,
            "blended": 0,
            "edges": 0,
            "hovered_edges": 0,
            "selected_edges": 0,
            "skeleton_lines": 0,
            "joint_markers": 0,
            "gizmo_lines": 0,
        }
        batch_count = 0
        material_group_keys: set[str] = set()
        pipeline_switch_count = 0
        last_pipeline_key = None

        def draw_pass(pass_name: str, items: list, pipeline) -> None:
            nonlocal tri_count, batch_count, pipeline_switch_count, last_pipeline_key
            if not items:
                return
            pipeline_key = pass_name
            if bool(getattr(self, "enable_batching", True)) and pass_name != "blended":
                batches = group_render_batches(items, pipeline_key=pipeline_key, category=pass_name)
                batch_count += len(batches)
                ordered_items = [row for batch in batches for row in batch.items]
            else:
                batch_count += len(items)
                ordered_items = items
            if last_pipeline_key != pipeline_key:
                pipeline_switch_count += 1
                last_pipeline_key = pipeline_key
            for _alpha_mode, _depth, mesh_data, material_data in ordered_items:
                material_group_keys.add(str(getattr(material_data, "material_id", "") or id(material_data)))
                tri_count += self._draw_mesh_item(render_pass, pipeline, mesh_data, material_data, mvp, pass_name, display_options)
                counts[pass_name] += 1

        if draw_surface:
            draw_pass("opaque", opaque, self.pipeline_mesh)
            draw_pass("cutout", cutout, self.pipeline_mesh_cutout or self.pipeline_mesh)
            draw_pass("blended", blended, self.pipeline_mesh_blend or self.pipeline_mesh)
        if edge_overlay:
            counts["edges"] = self._draw_edge_items(render_pass, edge_items, mvp, mode)
        hovered_edge_items = [
            item for item in edge_items
            if bool(getattr(self, "show_mesh_hover_edges", False)) and self._is_hovered_mesh_data(item)
        ]
        if hovered_edge_items:
            counts["hovered_edges"] = self._draw_edge_items(
                render_pass,
                hovered_edge_items,
                mvp,
                mode,
                color=(*tuple(self.hovered_edge_color[:3]), float(getattr(self, "hovered_edge_alpha", 0.45))),
            )
        selected_edge_items = [item for item in edge_items if self._is_selected_mesh_data(item)]
        if selected_edge_items:
            counts["selected_edges"] = self._draw_edge_items(
                render_pass,
                selected_edge_items,
                mvp,
                mode,
                color=(*tuple(self.selected_edge_color[:3]), 1.0),
            )
        self.perf["tri_count"] = int(tri_count)
        self._active_skinned_mesh_count = int(skinned_mesh_count)
        self._active_cpu_skinned_mesh_count = int(cpu_skinned_mesh_count)
        self._active_total_mesh_count = int(total_mesh_count)
        self._active_visible_mesh_count = int(visible_mesh_count)
        self._active_culled_mesh_count = int(culled_mesh_count)
        self._last_batch_count = int(batch_count)
        self._last_material_group_count = len(material_group_keys)
        self._last_instance_group_count = int(instance_stats.get("instance_group_count", 0))
        self._last_instance_count = int(instance_stats.get("instance_count", 0))
        self._last_pipeline_switch_count = int(pipeline_switch_count)
        self._update_texture_residency_diagnostics()
        self.profiler.set("mesh_count", total_mesh_count)
        self.profiler.set("visible_mesh_count", visible_mesh_count)
        self.profiler.set("culled_mesh_count", culled_mesh_count)
        self.profiler.set("batch_count", batch_count)
        self.profiler.set("material_group_count", len(material_group_keys))
        self.profiler.set("pipeline_switch_count", pipeline_switch_count)
        self.profiler.set("instance_group_count", self._last_instance_group_count)
        self.profiler.set("instance_count", self._last_instance_count)
        self.profiler.set("alpha_object_count", self._last_alpha_object_count)
        self.profiler.set("alpha_sort_ms", self._last_alpha_sort_ms)
        self._last_render_counts.update(counts)
        if bool(getattr(self, "debug_texture_uploads", False)):
            log.info(
                "WgpuRenderer: rendered opaque=%s cutout=%s blended=%s",
                counts["opaque"],
                counts["cutout"],
                counts["blended"],
            )

    def _draw_mesh_item(self, render_pass, pipeline, mesh_data, material_data, mvp, pass_name: str, display_options: ViewportDisplayOptions) -> int:
        import wgpu

        if pipeline is None:
            return 0
        try:
            resource = self.resource_cache.get_or_upload_mesh(mesh_data)
            if resource is None:
                return 0
            material = self.resource_cache.get_or_create_material(material_data)
            if material is None:
                return 0
            skin_resource = None
            if bool(getattr(mesh_data, "is_skinned", False)) and self._active_anim_pose is not None:
                skinned_pipeline = self._skinned_pipeline_for_pass(pass_name)
                if skinned_pipeline is not None:
                    try:
                        skin_resource = self.resource_cache.get_or_update_skin_palette(
                            mesh_data,
                            self._active_anim_pose,
                            self._active_scene,
                        )
                    except Exception as exc:
                        self.last_skinning_error = f"WGPU skin palette upload failed: {exc}"
                        self.gpu_skinning_status = "palette upload failed"
                        skin_resource = None
                    if skin_resource is not None:
                        pipeline = skinned_pipeline
                        self.gpu_skinning_status = "ready"
                    else:
                        self.last_skinning_error = self.last_skinning_error or "WGPU skin palette unavailable; drawing bind pose"
                else:
                    self.last_skinning_error = self.skinned_mesh_pipeline_status or "WGPU skinned pipeline unavailable; drawing bind pose"
            uniform = self._mesh_uniform_bytes(
                mvp,
                getattr(material_data, "base_color_rgba", mesh_data.material_color),
                material,
                display_options,
                selected=self._is_selected_mesh_data(mesh_data),
            )
            render_pass.set_pipeline(pipeline)
            self._set_mesh_uniform(render_pass, uniform)
            render_pass.set_bind_group(1, material.bind_group)
            self.profiler.add("texture_bind_count", 1)
            if skin_resource is not None:
                render_pass.set_bind_group(2, skin_resource.bind_group)
            render_pass.set_vertex_buffer(0, resource.vertex_buffer)
            if resource.index_buffer is not None and resource.index_count > 0:
                render_pass.set_index_buffer(resource.index_buffer, wgpu.IndexFormat.uint32)
                render_pass.draw_indexed(resource.index_count, 1, 0, 0, 0)
                self.profiler.add("draw_calls", 1)
                return resource.index_count // 3
            render_pass.draw(resource.vertex_count, 1, 0, 0)
            self.profiler.add("draw_calls", 1)
            return resource.vertex_count // 3
        except Exception as exc:
            log.warning("WgpuRenderer: skipped mesh %s: %s", getattr(mesh_data.source, "name", mesh_data.mesh_id), exc)
            return 0

    def _skinned_pipeline_for_pass(self, pass_name: str):
        if str(pass_name).lower() == "cutout":
            return self.pipeline_mesh_skinned_cutout or self.pipeline_mesh_skinned
        if str(pass_name).lower() == "blended":
            return self.pipeline_mesh_skinned_blend or self.pipeline_mesh_skinned
        return self.pipeline_mesh_skinned

    def _is_selected_mesh_data(self, mesh_data) -> bool:
        node = getattr(mesh_data, "source", None)
        selected_ids = {id(item) for item in (getattr(self, "selected_nodes", []) or [])}
        selected = getattr(self, "selected_node", None)
        return bool(node is selected or id(node) in selected_ids or getattr(node, "_gr_selected", False))

    def _is_hovered_mesh_data(self, mesh_data) -> bool:
        if not bool(getattr(self, "show_mesh_hover", True)):
            return False
        node = getattr(mesh_data, "source", None)
        if node is None or bool(getattr(node, "_gr_hidden", False)):
            return False
        return node is getattr(self, "hovered_node", None)

    def _draw_edge_items(self, render_pass, mesh_items, mvp, mode: ViewportDisplayMode, *, color=None) -> int:
        import wgpu

        if self.pipeline_lines is None or self.line_uniform_buffer is None or self.line_bind_group is None:
            self.last_display_mode_warning = "WGPU line pipeline unavailable; edge overlay skipped."
            return 0
        color = color or (
            (*tuple(self.hidden_line_color[:3]), 1.0)
            if mode is ViewportDisplayMode.HIDDEN_LINE
            else (*tuple(self.wire_color[:3]), 1.0)
        )
        render_pass.set_pipeline(self.pipeline_lines)
        self._set_line_uniform(render_pass, mvp, color)
        drawn = 0
        for mesh_data in mesh_items:
            try:
                resource = self.resource_cache.get_or_upload_mesh(mesh_data)
                if resource is None or resource.edge_index_buffer is None or resource.edge_index_count <= 0:
                    continue
                render_pass.set_vertex_buffer(0, resource.vertex_buffer)
                render_pass.set_index_buffer(resource.edge_index_buffer, wgpu.IndexFormat.uint32)
                render_pass.draw_indexed(resource.edge_index_count, 1, 0, 0, 0)
                self.profiler.add("draw_calls", 1)
                drawn += resource.edge_index_count // 2
            except Exception as exc:
                self.last_display_mode_warning = f"WGPU edge overlay skipped: {exc}"
                log.warning("WgpuRenderer: skipped edge overlay: %s", exc)
        return drawn

    def _ensure_light_resource(self) -> WgpuLightResource | None:
        import numpy as np
        import wgpu

        if self.device is None or self.queue is None or self.light_buffer is None or self.lighting_uniform_buffer is None:
            return None
        lighting = self._active_lighting_render_data
        if lighting is None:
            try:
                from src.gui.lighting.render_data import build_scene_lighting_render_data

                lighting = build_scene_lighting_render_data(
                    self._active_scene,
                    selected_node=getattr(self, "selected_node", None),
                    ambient_color_rgb=float(getattr(self, "scene_ambient", 0.06)),
                    mode=str(getattr(self, "lighting_mode", "scene") or "scene"),
                    complexity=str(getattr(self, "shader_complexity_mode", "basic") or "basic"),
                    show_helpers=bool(getattr(self, "show_light_gizmos", True)),
                    show_volumes=bool(getattr(self, "show_light_radius_volumes", False)),
                    diffuse_enabled=bool(getattr(self, "show_diffuse_map", True)),
                    specular_enabled=bool(getattr(self, "show_specular_map", True)),
                    normal_enabled=bool(getattr(self, "show_normal_map", True)),
                    environment_enabled=bool(getattr(self, "show_environment_map", True)),
                    lightmap_enabled=bool(getattr(self, "show_lightmap_map", True)),
                    lm_intensity=float(getattr(self, "lightmap_intensity", 0.55)),
                    lm_mode=str(getattr(self, "lightmap_mode", "baked") or "baked"),
                    helper_palette=getattr(self, "light_helper_palette", None),
                )
                self._active_lighting_render_data = lighting
            except Exception as exc:
                self._last_lighting_error = f"lighting snapshot failed: {exc}"
                return None
        if lighting is not None and not getattr(lighting, "helper_palette", None):
            try:
                helper_palette = getattr(self, "light_helper_palette", None) or {}
                palette_revision = hash(
                    tuple(sorted((str(k), tuple(round(float(c), 5) for c in v[:3])) for k, v in helper_palette.items()))
                ) & 0x7FFFFFFF
                lighting = dataclasses.replace(
                    lighting,
                    helper_palette=helper_palette,
                    revision=(int(getattr(lighting, "revision", 0) or 0) ^ palette_revision) & 0x7FFFFFFF,
                )
                self._active_lighting_render_data = lighting
            except Exception:
                pass
        revision = int(getattr(lighting, "revision", 0) or 0)
        display_options = self._effective_display_options or self._active_display_options
        display_revision = hash(
            (
                str(getattr(getattr(display_options, "display_mode", None), "value", getattr(display_options, "display_mode", ""))),
                bool(getattr(display_options, "force_flat_colour", False)),
                bool(getattr(display_options, "force_unlit", False)),
                bool(getattr(display_options, "show_textures", True)),
                bool(getattr(display_options, "show_lightmaps", False)),
            )
        ) & 0x7FFFFFFF
        revision = (revision ^ display_revision) & 0x7FFFFFFF
        if self.light_resource is not None and self._light_resource_revision_key == revision:
            return self.light_resource

        started = time.perf_counter()
        try:
            from src.gui.lighting.render_data import (
                build_light_helper_line_batches,
                build_light_volume_line_batches,
                light_kind_int,
            )

            all_lights = list(getattr(lighting, "lights", ()) or ())
            visible_lights = [light for light in all_lights if bool(getattr(light, "visible", True))]

            def score(light) -> float:
                selected_bonus = 100000.0 if bool(getattr(light, "selected", False)) else 0.0
                enabled_bonus = 1000.0 if bool(getattr(light, "enabled", True)) else 0.0
                return selected_bonus + enabled_bonus + float(getattr(light, "radius", 0.0) or 0.0) * max(0.01, float(getattr(light, "intensity", 0.0) or 0.0))

            visible_lights.sort(key=score, reverse=True)
            max_lights = int(self.max_wgpu_lights)
            upload_lights = visible_lights[:max_lights]
            light_rows = np.zeros((max_lights, 16), dtype=np.float32)
            unsupported = 0
            selected_light_id = 0
            for idx, light in enumerate(upload_lights):
                kind = light_kind_int(str(getattr(light, "light_type", "point") or "point"))
                if kind == 0 and "unknown" in str(getattr(light, "light_type", "") or "").lower():
                    unsupported += 1
                if bool(getattr(light, "active_selected", False)) or (selected_light_id == 0 and bool(getattr(light, "selected", False))):
                    selected_light_id = int(getattr(light, "light_id", idx + 1) or (idx + 1))
                px, py, pz = tuple(getattr(light, "position", (0.0, 0.0, 0.0)))[:3]
                dx, dy, dz = tuple(getattr(light, "direction", (0.0, 0.0, -1.0)))[:3]
                cr, cg, cb = tuple(getattr(light, "color_rgb", (1.0, 1.0, 1.0)))[:3]
                cone = math.cos(math.radians(float(getattr(light, "cone_angle_degrees", 45.0) or 45.0) * 0.5))
                light_rows[idx, 0:4] = (float(px), float(py), float(pz), max(0.001, float(getattr(light, "radius", 5.0) or 5.0)))
                light_rows[idx, 4:8] = (float(dx), float(dy), float(dz), float(cone))
                light_rows[idx, 8:12] = (max(0.0, float(cr)), max(0.0, float(cg)), max(0.0, float(cb)), max(0.0, float(getattr(light, "intensity", 1.0) or 0.0)))
                light_rows[idx, 12:16] = (
                    1.0 if bool(getattr(light, "enabled", True)) else 0.0,
                    float(kind),
                    1.0 if bool(getattr(light, "ambient_only", False)) else 0.0,
                    float(getattr(light, "area_size", 1.0) or 0.0),
                )
            self.queue.write_buffer(self.light_buffer, 0, light_rows.tobytes())

            ambient = tuple(float(v) for v in tuple(getattr(lighting, "ambient_color_rgb", (0.06, 0.06, 0.06)))[:3])
            scene_enabled = 1.0 if self._scene_lighting_enabled(lighting, self._effective_display_options) else 0.0
            diffuse_enabled = 1.0 if bool(getattr(lighting, "diffuse_enabled", True)) else 0.0
            specular_enabled = 1.0 if bool(getattr(lighting, "specular_enabled", True)) else 0.0
            uniform = np.asarray(
                (
                    max(0.0, ambient[0]),
                    max(0.0, ambient[1]),
                    max(0.0, ambient[2]),
                    max(0.0, float(getattr(lighting, "global_intensity", 1.0) or 1.0)),
                    float(len(upload_lights)),
                    scene_enabled,
                    diffuse_enabled,
                    specular_enabled,
                ),
                dtype=np.float32,
            )
            self.queue.write_buffer(self.lighting_uniform_buffer, 0, uniform.tobytes())

            helper_batches = self._upload_light_line_batches(build_light_helper_line_batches(lighting))
            volume_batches = self._upload_light_line_batches(build_light_volume_line_batches(lighting))
            upload_ms = (time.perf_counter() - started) * 1000.0
            resource = WgpuLightResource(
                light_buffer=self.light_buffer,
                lighting_uniform_buffer=self.lighting_uniform_buffer,
                revision=revision,
                light_count=len(all_lights),
                uploaded_light_count=len(upload_lights),
                max_lights=max_lights,
                helper_batches=helper_batches,
                volume_batches=volume_batches,
                selected_light_id=selected_light_id,
                unsupported_light_types=unsupported + max(0, len(visible_lights) - max_lights),
                upload_time_ms=upload_ms,
            )
            self.light_resource = resource
            self._light_resource_revision_key = revision
            self._last_lighting_upload_time_ms = upload_ms
            self._last_lighting_error = ""
            self._last_light_shader_active = bool(scene_enabled)
            self.profiler.add("light_buffer_updates", 1)
            return resource
        except Exception as exc:
            self._last_lighting_error = str(exc)
            log.warning("WgpuRenderer: lighting upload failed: %s", exc)
            return None

    def _upload_light_line_batches(self, batches) -> list[tuple[tuple[float, float, float, float], object, int]]:
        import wgpu

        uploaded: list[tuple[tuple[float, float, float, float], object, int]] = []
        for color, vertices in batches or []:
            if not vertices:
                continue
            buffer, count = self._position_line_buffer(vertices, usage=wgpu.BufferUsage.VERTEX)
            if buffer is None or count <= 0:
                continue
            rgba = (*tuple(float(v) for v in color[:3]), 1.0)
            uploaded.append((rgba, buffer, count))
            self.resource_cache.buffer_upload_count += 1
        return uploaded

    def _position_line_buffer(self, vertices, *, usage):
        import numpy as np

        if self.device is None or not vertices:
            return None, 0
        data = np.asarray(vertices, dtype=np.float32).reshape(-1, 3)
        return self.device.create_buffer_with_data(data=data, usage=usage), int(len(vertices))

    def _draw_light_overlays(self, render_pass, width: int, height: int) -> tuple[int, int]:
        if self.pipeline_gizmo_lines is None or self.line_uniform_buffer is None or self.line_bind_group is None:
            return (0, 0)
        resource = self._ensure_light_resource()
        if resource is None:
            return (0, 0)
        mvp = self._camera_mvp_matrix(self._active_camera, width, height)
        render_pass.set_pipeline(self.pipeline_gizmo_lines)

        def draw_batches(batches) -> int:
            drawn = 0
            for color, buffer, vertex_count in batches:
                if buffer is None or vertex_count <= 0:
                    continue
                self._set_line_uniform(render_pass, mvp, color)
                render_pass.set_vertex_buffer(0, buffer)
                render_pass.draw(int(vertex_count), 1, 0, 0)
                self.profiler.add("draw_calls", 1)
                drawn += int(vertex_count // 2)
            return drawn

        helper_lines = draw_batches(resource.helper_batches)
        volume_lines = draw_batches(resource.volume_batches)
        return (helper_lines, volume_lines)

    def _scene_lighting_enabled(self, lighting, display_options: ViewportDisplayOptions | None) -> bool:
        mode = str(getattr(lighting, "mode", getattr(self, "lighting_mode", "scene")) or "scene").lower()
        if mode in {"unlit", "fullbright", "diffuse_only", "normal_only", "specular_only", "environment_only", "lightmap_preview", "shader_complexity"}:
            return False
        if display_options is not None:
            if bool(getattr(display_options, "force_flat_colour", False)) or bool(getattr(display_options, "force_unlit", False)):
                return False
            base_mode = normalize_display_mode(getattr(display_options, "display_mode", ViewportDisplayMode.FULL_MATERIAL))
            if base_mode in {
                ViewportDisplayMode.SOLID,
                ViewportDisplayMode.SHADED,
                ViewportDisplayMode.SMOOTH_SHADED,
                ViewportDisplayMode.WIREFRAME,
                ViewportDisplayMode.HIDDEN_LINE,
            }:
                return False
        return bool(getattr(lighting, "diffuse_enabled", True))

    def _draw_gizmo_lines(self, render_pass, width: int, height: int) -> int:
        import numpy as np

        if self.pipeline_gizmo_lines is None or self.line_uniform_buffer is None or self.line_bind_group is None:
            if self._active_gizmo_render_data is not None:
                self.gizmo_pipeline_status = self.gizmo_pipeline_status or "not created"
            return 0
        render_data = self._active_gizmo_render_data
        commands = tuple(getattr(render_data, "commands", ()) or ())
        if not commands:
            return 0
        try:
            import wgpu

            mvp = self._camera_mvp_matrix(self._active_camera, width, height)
            render_pass.set_pipeline(self.pipeline_gizmo_lines)
            render_pass.set_bind_group(0, self.line_bind_group)
            drawn = 0
            for command in commands:
                cache_key = self._gizmo_command_cache_key(command)
                cached = self._gizmo_line_cache.get(cache_key)
                if cached is None:
                    vertices = self._line_vertices_from_gizmo_command(command)
                    if not vertices:
                        continue
                    data = np.asarray(vertices, dtype=np.float32).reshape(-1, 3)
                    vertex_buffer = self.device.create_buffer_with_data(data=data, usage=wgpu.BufferUsage.VERTEX)
                    cached = (vertex_buffer, int(len(data)))
                    if len(self._gizmo_line_cache) > 256:
                        self._gizmo_line_cache.clear()
                    self._gizmo_line_cache[cache_key] = cached
                    self.resource_cache.buffer_upload_count += 1
                vertex_buffer, vertex_count = cached
                if vertex_count <= 0:
                    continue
                color = tuple(float(v) for v in getattr(command, "colour", (1.0, 1.0, 1.0, 1.0))[:4])
                uniform = self._line_uniform_bytes(mvp, color)
                self.queue.write_buffer(self.line_uniform_buffer, 0, uniform)
                render_pass.set_vertex_buffer(0, vertex_buffer)
                render_pass.draw(int(vertex_count), 1, 0, 0)
                self.profiler.add("draw_calls", 1)
                drawn += int(vertex_count // 2)
            self.gizmo_pipeline_status = "ready"
            return drawn
        except Exception as exc:
            self.gizmo_pipeline_status = f"draw failed: {exc}"
            self.last_display_mode_warning = f"WGPU gizmo overlay skipped: {exc}"
            log.warning("WgpuRenderer: skipped gizmo overlay: %s", exc)
            return 0

    def _draw_skeleton_overlay(self, render_pass, width: int, height: int) -> tuple[int, int]:
        if self.pipeline_gizmo_lines is None or self.line_uniform_buffer is None or self.line_bind_group is None:
            if self._active_skeleton_render_data is not None:
                self.skeleton_overlay_pipeline_status = self.gizmo_pipeline_status or "not created"
            return (0, 0)
        skeleton = self._active_skeleton_render_data
        if skeleton is None or not tuple(getattr(skeleton, "bones", ()) or ()):
            return (0, 0)
        try:
            import wgpu

            resource = self._get_or_upload_skeleton_resource(skeleton)
            if resource is None:
                return (0, 0)
            mvp = self._camera_mvp_matrix(self._active_camera, width, height)
            render_pass.set_pipeline(self.pipeline_gizmo_lines)
            render_pass.set_bind_group(0, self.line_bind_group)
            line_count = 0
            marker_count = 0

            def draw_buffer(buffer, vertex_count: int, color: tuple[float, float, float, float]) -> int:
                if buffer is None or vertex_count <= 0:
                    return 0
                self.queue.write_buffer(self.line_uniform_buffer, 0, self._line_uniform_bytes(mvp, color))
                render_pass.set_vertex_buffer(0, buffer)
                render_pass.draw(int(vertex_count), 1, 0, 0)
                self.profiler.add("draw_calls", 1)
                return int(vertex_count // 2)

            line_count += draw_buffer(resource.line_vertex_buffer, resource.line_vertex_count, (0.52, 0.60, 0.70, 0.86))
            line_count += draw_buffer(resource.selected_line_vertex_buffer, resource.selected_line_vertex_count, (1.0, 0.82, 0.12, 1.0))
            marker_count += draw_buffer(resource.joint_marker_vertex_buffer, resource.joint_marker_vertex_count, (0.66, 0.72, 0.80, 0.92))
            marker_count += draw_buffer(resource.selected_marker_vertex_buffer, resource.selected_marker_vertex_count, (1.0, 0.88, 0.14, 1.0))
            self.skeleton_overlay_pipeline_status = "ready"
            return (line_count, marker_count)
        except Exception as exc:
            self.skeleton_overlay_pipeline_status = f"draw failed: {exc}"
            self.last_display_mode_warning = f"WGPU skeleton overlay skipped: {exc}"
            log.warning("WgpuRenderer: skipped skeleton overlay: %s", exc)
            return (0, 0)

    def _get_or_upload_skeleton_resource(self, skeleton) -> WgpuSkeletonResource | None:
        import numpy as np
        import wgpu

        revision = int(getattr(skeleton, "revision", 0) or 0)
        cached = self.skeleton_resource
        if cached is not None and cached.revision == revision:
            return cached
        if self.device is None:
            return None

        lines: list[tuple[float, float, float]] = []
        joints: list[tuple[float, float, float]] = []
        selected_lines: list[tuple[float, float, float]] = []
        selected_joints: list[tuple[float, float, float]] = []
        show_links = bool(getattr(skeleton, "show_links", True))
        show_dots = bool(getattr(skeleton, "show_dots", True))
        for bone in tuple(getattr(skeleton, "bones", ()) or ()):
            if not bool(getattr(bone, "visible", True)):
                continue
            head = tuple(float(v) for v in tuple(getattr(bone, "head_position", (0.0, 0.0, 0.0)))[:3])
            tail = tuple(float(v) for v in tuple(getattr(bone, "tail_position", head))[:3])
            target_lines = selected_lines if (bool(getattr(bone, "selected", False)) or bool(getattr(bone, "hovered", False))) else lines
            target_joints = selected_joints if (bool(getattr(bone, "selected", False)) or bool(getattr(bone, "hovered", False))) else joints
            if show_links and _point_distance(head, tail) > 1e-5:
                target_lines.extend((tail, head))
            if show_dots:
                target_joints.extend(_joint_marker_segments(head, selected=target_joints is selected_joints))

        def make_buffer(vertices):
            if not vertices:
                return None, 0
            data = np.asarray(vertices, dtype=np.float32).reshape(-1, 3)
            return self.device.create_buffer_with_data(data=data, usage=wgpu.BufferUsage.VERTEX), int(len(data))

        line_buffer, line_count = make_buffer(lines)
        joint_buffer, joint_count = make_buffer(joints)
        selected_line_buffer, selected_line_count = make_buffer(selected_lines)
        selected_marker_buffer, selected_marker_count = make_buffer(selected_joints)
        resource = WgpuSkeletonResource(
            line_vertex_buffer=line_buffer,
            joint_marker_vertex_buffer=joint_buffer,
            selected_line_vertex_buffer=selected_line_buffer,
            selected_marker_vertex_buffer=selected_marker_buffer,
            line_vertex_count=line_count,
            joint_marker_vertex_count=joint_count,
            selected_line_vertex_count=selected_line_count,
            selected_marker_vertex_count=selected_marker_count,
            bone_count=len(tuple(getattr(skeleton, "bones", ()) or ())),
            joint_count=(joint_count + selected_marker_count) // 6,
            revision=revision,
        )
        self.skeleton_resource = resource
        return resource

    @staticmethod
    def _line_vertices_from_gizmo_command(command) -> list[tuple[float, float, float]]:
        points = [tuple(float(v) for v in tuple(point)[:3]) for point in (getattr(command, "points", ()) or ())]
        if len(points) < 2:
            return []
        kind = str(getattr(command, "kind", "line") or "line").lower()
        if kind == "polyline":
            out: list[tuple[float, float, float]] = []
            for a, b in zip(points, points[1:]):
                out.extend((a, b))
            return out
        return [points[0], points[1]]

    @staticmethod
    def _gizmo_command_cache_key(command) -> tuple:
        points = tuple(tuple(round(float(v), 6) for v in tuple(point)[:3]) for point in (getattr(command, "points", ()) or ()))
        return (str(getattr(command, "kind", "line") or "line").lower(), points)

    def pick(self, request, scene=None, camera=None) -> PickHit:
        """GPU object-ID picking for WGPU surfaces.

        The viewport owns selection policy; this method only renders an
        offscreen ID pass and returns the node hit by the requested pixel.
        """

        import numpy as np
        import wgpu
        pick_started = time.perf_counter()

        scene = scene if scene is not None else self._active_scene
        camera = camera if camera is not None else getattr(request, "camera", None) or self._active_camera
        width = max(1, int(getattr(request, "viewport_width", 0) or self._last_size[0] or 1))
        height = max(1, int(getattr(request, "viewport_height", 0) or self._last_size[1] or 1))
        x = max(0, min(width - 1, int(getattr(request, "x", 0) or 0)))
        y = max(0, min(height - 1, int(getattr(request, "y", 0) or 0)))
        diagnostic = {
            "method": "WGPU GPU ID",
            "x": x,
            "y": y,
            "viewport_size": (width, height),
            "device_pixel_ratio": float(getattr(request, "device_pixel_ratio", 1.0) or 1.0),
            "pipeline_status": self.pick_pipeline_status,
        }
        if scene is None or camera is None:
            diagnostic["result"] = "unavailable"
            diagnostic["reason"] = "missing scene or camera"
            self.last_pick_diagnostics = diagnostic
            return PickHit(renderer_backend=self.backend_id, diagnostic=diagnostic)
        if self.device is None or self.queue is None or not self.initialized:
            diagnostic["result"] = "unavailable"
            diagnostic["reason"] = "WGPU renderer is not initialized"
            self.last_pick_diagnostics = diagnostic
            return PickHit(renderer_backend=self.backend_id, diagnostic=diagnostic)
        if self.pipeline_pick is None or self.line_uniform_buffer is None or self.line_bind_group is None:
            diagnostic["result"] = "unavailable"
            diagnostic["reason"] = self.pick_pipeline_status or "pick pipeline unavailable"
            self.last_pick_diagnostics = diagnostic
            return PickHit(renderer_backend=self.backend_id, diagnostic=diagnostic)

        try:
            from src.gui.rendering.mesh_render_data import iter_mesh_render_data
        except Exception as exc:
            diagnostic["result"] = "unavailable"
            diagnostic["reason"] = f"mesh adapter unavailable: {exc}"
            self.last_pick_diagnostics = diagnostic
            return PickHit(renderer_backend=self.backend_id, diagnostic=diagnostic)

        id_to_mesh: dict[int, object] = {}
        mesh_rows = []
        next_id = 1
        for mesh_data in iter_mesh_render_data(
            scene,
            anim_pose=self._active_anim_pose,
            anim_base_pose=self._active_anim_base_pose,
            textures={},
            allow_cpu_skinning=False,
        ):
            node = getattr(mesh_data, "source", None)
            if node is None:
                continue
            if not bool(getattr(request, "include_hidden", False)) and bool(getattr(node, "_gr_hidden", False)):
                continue
            if not bool(getattr(request, "include_locked", False)) and bool(getattr(node, "_gr_scene_object_locked", False)):
                continue
            if next_id > 0xFFFFFF:
                break
            id_to_mesh[next_id] = mesh_data
            mesh_rows.append((next_id, mesh_data))
            next_id += 1
        diagnostic["candidate_count"] = len(mesh_rows)
        if not mesh_rows:
            diagnostic["result"] = "miss"
            self.last_pick_diagnostics = diagnostic
            return PickHit(renderer_backend=self.backend_id, diagnostic=diagnostic)

        resources = self._ensure_pick_resources(width, height)
        pick_texture = resources.pick_texture
        depth_texture = resources.depth_texture
        read_buffer = resources.read_buffer
        encoder = self.device.create_command_encoder()
        render_pass = encoder.begin_render_pass(
            color_attachments=[
                {
                    "view": pick_texture.create_view(),
                    "resolve_target": None,
                    "clear_value": (0.0, 0.0, 0.0, 1.0),
                    "load_op": wgpu.LoadOp.clear,
                    "store_op": wgpu.StoreOp.store,
                }
            ],
            depth_stencil_attachment={
                "view": depth_texture.create_view(),
                "depth_clear_value": 1.0,
                "depth_load_op": wgpu.LoadOp.clear,
                "depth_store_op": wgpu.StoreOp.store,
            },
        )
        mvp = self._camera_mvp_matrix(camera, width, height)
        render_pass.set_pipeline(self.pipeline_pick)
        render_pass.set_bind_group(0, self.line_bind_group)
        drawn = 0
        for pick_id, mesh_data in mesh_rows:
            try:
                resource = self.resource_cache.get_or_upload_mesh(mesh_data)
                if resource is None:
                    continue
                color = self._pick_id_to_color(pick_id)
                self.queue.write_buffer(self.line_uniform_buffer, 0, self._line_uniform_bytes(mvp, color, target_color=False))
                render_pass.set_vertex_buffer(0, resource.vertex_buffer)
                if resource.index_buffer is not None and resource.index_count > 0:
                    render_pass.set_index_buffer(resource.index_buffer, wgpu.IndexFormat.uint32)
                    render_pass.draw_indexed(resource.index_count, 1, 0, 0, 0)
                    drawn += resource.index_count // 3
                else:
                    render_pass.draw(resource.vertex_count, 1, 0, 0)
                    drawn += resource.vertex_count // 3
            except Exception as exc:
                diagnostic.setdefault("skipped", []).append(str(exc))
                continue
        render_pass.end()
        encoder.copy_texture_to_buffer(
            {"texture": pick_texture, "origin": (x, y, 0)},
            {"buffer": read_buffer, "offset": 0, "bytes_per_row": 256, "rows_per_image": 1},
            (1, 1, 1),
        )
        self.queue.submit([encoder.finish()])
        read_buffer.map_sync(wgpu.MapMode.READ, 0, 256)
        try:
            pixel = bytes(read_buffer.read_mapped(0, 4, copy=True))
        finally:
            read_buffer.unmap()
        pick_id = self._pick_id_from_rgba(pixel)
        pick_ms = (time.perf_counter() - pick_started) * 1000.0
        diagnostic["drawn_triangles"] = drawn
        diagnostic["pick_pass_ms"] = round(pick_ms, 3)
        diagnostic["raw_rgba"] = tuple(int(v) for v in pixel[:4])
        diagnostic["pick_id"] = int(pick_id)
        mesh_data = id_to_mesh.get(pick_id)
        if mesh_data is None:
            diagnostic["result"] = "miss"
            diagnostic["reason"] = "raw ID did not decode to a WGPU mesh pick row"
            self.last_pick_diagnostics = diagnostic
            self.profiler.last.pick_pass_ms = pick_ms
            return PickHit(
                renderer_backend=self.backend_id,
                source_backend=self.backend_id,
                raw_id=int(pick_id),
                diagnostic_reason=str(diagnostic["reason"]),
                screen_position=(x, y),
                diagnostic=diagnostic,
            )
        node = getattr(mesh_data, "source", None)
        diagnostic["result"] = str(getattr(node, "name", id(node)))
        diagnostic["hit_kind"] = "mesh"
        self.last_pick_diagnostics = diagnostic
        self.profiler.last.pick_pass_ms = pick_ms
        return PickHit(
            hit=True,
            kind="mesh",
            object_id=id(node),
            object_ref=node,
            mesh_id=id(node),
            node_id=getattr(node, "name", id(node)),
            screen_position=(x, y),
            hit_kind="mesh",
            source_backend=self.backend_id,
            raw_id=int(pick_id),
            renderer_backend=self.backend_id,
            diagnostic=diagnostic,
        )

    def _ensure_pick_resources(self, width: int, height: int) -> WgpuPickResources:
        import wgpu

        cached = self._pick_resources
        if cached is not None and cached.width == int(width) and cached.height == int(height):
            return cached
        if self.device is None:
            raise RuntimeError("WGPU device is not ready")
        pick_texture = self.device.create_texture(
            size=(int(width), int(height), 1),
            usage=wgpu.TextureUsage.RENDER_ATTACHMENT | wgpu.TextureUsage.COPY_SRC,
            dimension=wgpu.TextureDimension.d2,
            format="rgba8unorm",
            mip_level_count=1,
            sample_count=1,
        )
        depth_texture = self.device.create_texture(
            size=(int(width), int(height), 1),
            usage=wgpu.TextureUsage.RENDER_ATTACHMENT,
            dimension=wgpu.TextureDimension.d2,
            format=self.depth_format,
            mip_level_count=1,
            sample_count=1,
        )
        read_buffer = self.device.create_buffer(
            size=256,
            usage=wgpu.BufferUsage.COPY_DST | wgpu.BufferUsage.MAP_READ,
        )
        self._pick_resources = WgpuPickResources(int(width), int(height), pick_texture, depth_texture, read_buffer)
        return self._pick_resources

    @staticmethod
    def _pick_id_to_color(pick_id: int) -> tuple[float, float, float, float]:
        value = max(0, min(0xFFFFFF, int(pick_id)))
        return (
            float(value & 0xFF) / 255.0,
            float((value >> 8) & 0xFF) / 255.0,
            float((value >> 16) & 0xFF) / 255.0,
            1.0,
        )

    @staticmethod
    def _pick_id_from_rgba(pixel: bytes | bytearray | memoryview) -> int:
        raw = bytes(pixel)
        if len(raw) < 3:
            return 0
        return int(raw[0]) | (int(raw[1]) << 8) | (int(raw[2]) << 16)

    def _mesh_sort_depth(self, mesh_data, camera) -> float:
        try:
            import numpy as np

            pos = np.asarray(mesh_data.positions, dtype=np.float32)
            center = pos.mean(axis=0)
            eye_attr = getattr(camera, "eye", (0.0, 5.0, 3.0)) if camera is not None else (0.0, 5.0, 3.0)
            eye = np.asarray(tuple(eye_attr() if callable(eye_attr) else eye_attr), dtype=np.float32)
            return float(np.linalg.norm(center - eye))
        except Exception:
            return 0.0

    def _mesh_data_outside_frustum(self, mesh_data, frustum_planes) -> bool:
        try:
            import numpy as np

            positions = np.asarray(getattr(mesh_data, "positions", None), dtype=np.float32)
            if positions.ndim != 2 or positions.shape[1] < 3 or len(positions) <= 0:
                return False
            mins = tuple(float(v) for v in positions[:, :3].min(axis=0))
            maxs = tuple(float(v) for v in positions[:, :3].max(axis=0))
            return not bounds_intersects_frustum((mins, maxs), frustum_planes)
        except Exception:
            return False

    def _update_texture_residency_diagnostics(self) -> None:
        textures = [
            TextureResidencyInfo(
                texture_id=str(resource.source_id),
                width=int(resource.width),
                height=int(resource.height),
                format=str(resource.format),
                byte_size=int(resource.byte_size),
                resident=True,
                lightmap=bool(resource.lightmap),
            )
            for resource in self.resource_cache.textures.values()
        ]
        groups = texture_array_groups(textures)
        eligible = [texture for group in groups.values() for texture in group]
        self._last_texture_array_eligible_groups = sum(1 for group in groups.values() if len(group) > 1)
        self._last_texture_array_eligible_textures = len(eligible)

    def _untextured_material(self, material_data):
        from dataclasses import replace

        return replace(
            material_data,
            diffuse_texture_data=None,
            lightmap_texture_data=None,
            diffuse_texture_id="",
            lightmap_texture_id="",
            source_revision=(material_data.source_revision[0], 0, 0, material_data.source_revision[3]),
        )

    def _without_lightmap_material(self, material_data):
        from dataclasses import replace

        return replace(
            material_data,
            lightmap_texture_data=None,
            lightmap_texture_id="",
            source_revision=(material_data.source_revision[0], material_data.source_revision[1], 0, material_data.source_revision[3]),
        )

    def _camera_mvp_matrix(self, camera, width: int, height: int):
        import numpy as np

        eye_attr = getattr(camera, "eye", (0.0, 5.0, 3.0)) if camera is not None else (0.0, 5.0, 3.0)
        eye = tuple(eye_attr() if callable(eye_attr) else eye_attr)
        target_attr = getattr(camera, "target", (0.0, 0.0, 0.0)) if camera is not None else (0.0, 0.0, 0.0)
        target = tuple(target_attr() if callable(target_attr) else target_attr)
        up_attr = getattr(camera, "up", None) if camera is not None else None
        up = tuple(up_attr() if callable(up_attr) else up_attr) if up_attr is not None else (0.0, 0.0, 1.0)
        fov = float(getattr(camera, "fov", 45.0)) if camera is not None else 45.0
        near = float(getattr(camera, "near", getattr(camera, "_near", 0.01))) if camera is not None else 0.01
        far = float(getattr(camera, "far", getattr(camera, "_far", 2000.0))) if camera is not None else 2000.0
        proj = _mat4_perspective_wgpu(math.radians(fov), width / max(1, height), near, far)
        view = _mat4_lookat(eye, target, up)
        return (proj @ view @ np.eye(4, dtype=np.float32)).astype(np.float32)

    def _mesh_uniform_bytes(
        self,
        mvp,
        color: tuple[float, float, float, float],
        material,
        display_options: ViewportDisplayOptions,
        *,
        selected: bool = False,
    ) -> bytes:
        import numpy as np

        alpha_mode = str(getattr(material, "alpha_mode", "OPAQUE") or "OPAQUE").upper()
        alpha_mode_value = 1.0 if alpha_mode in {"MASK", "CUTOUT"} else 2.0 if alpha_mode == "BLEND" else 0.0
        mode = display_options.display_mode
        use_diffuse = bool(
            display_options.show_textures
            and bool(getattr(self, "show_diffuse_map", True))
            and mode in {
                ViewportDisplayMode.SOLID,
                ViewportDisplayMode.SHADED,
                ViewportDisplayMode.SMOOTH_SHADED,
                ViewportDisplayMode.TEXTURED,
                ViewportDisplayMode.TEXTURED_LIGHTMAPPED,
                ViewportDisplayMode.FULL_MATERIAL,
            }
            and getattr(material, "diffuse_texture_resource", None) is not None
        )
        use_lightmap = bool(
            display_options.show_lightmaps
            and mode in {ViewportDisplayMode.TEXTURED_LIGHTMAPPED, ViewportDisplayMode.FULL_MATERIAL}
            and bool(getattr(material, "has_lightmap", False))
            and not bool(getattr(self, "disable_lightmaps", False))
            and str(getattr(self._active_lighting_render_data, "lm_mode", getattr(self, "lightmap_mode", "baked")) or "baked").lower() != "disabled"
            and bool(getattr(self._active_lighting_render_data, "lightmap_enabled", getattr(self, "show_lightmap_map", True)))
        )
        flags = np.asarray(
            (
                1.0 if use_diffuse else 0.0,
                1.0 if use_lightmap else 0.0,
                alpha_mode_value,
                float(getattr(material, "alpha_cutoff", 0.5) or 0.5),
            ),
            dtype=np.float32,
        )
        shade_mode = 1.0 if display_options.force_flat_colour else 2.0 if mode in {ViewportDisplayMode.SHADED, ViewportDisplayMode.SMOOTH_SHADED} else 0.0
        lm_mode_name = str(getattr(self._active_lighting_render_data, "lm_mode", getattr(self, "lightmap_mode", "baked")) or "baked").lower()
        lm_mode = {"baked": 0.0, "dynamic_preview": 1.0, "hybrid": 2.0, "debug": 3.0, "phong": 1.0, "emissive": 2.0}.get(lm_mode_name, 0.0)
        lm_intensity = max(0.0, min(4.0, float(getattr(self._active_lighting_render_data, "lm_intensity", getattr(self, "lightmap_intensity", 0.55)) or 0.0)))
        params = np.asarray((lm_intensity, shade_mode, lm_mode, 1.0 if selected else 0.0), dtype=np.float32)
        return (
            np.asarray(mvp, dtype=np.float32).reshape(4, 4).T.tobytes()
            + np.asarray(color, dtype=np.float32).tobytes()
            + flags.tobytes()
            + params.tobytes()
        )

    def _line_uniform_bytes(self, mvp, color: tuple[float, float, float, float], *, target_color: bool = True) -> bytes:
        import numpy as np

        color = self._target_rgba(color) if target_color else tuple(float(v) for v in color[:4])
        return (
            np.asarray(mvp, dtype=np.float32).reshape(4, 4).T.tobytes()
            + np.asarray(color, dtype=np.float32).tobytes()
        )

    def _set_mesh_uniform(self, render_pass, uniform: bytes) -> None:
        try:
            import numpy as np
            import wgpu

            if (
                self.device is None
                or self.mesh_bind_group_layout is None
                or self.light_buffer is None
                or self.lighting_uniform_buffer is None
            ):
                raise RuntimeError("mesh uniform layout unavailable")
            buffer = self.device.create_buffer_with_data(
                data=np.frombuffer(uniform, dtype=np.uint8),
                usage=wgpu.BufferUsage.UNIFORM,
            )
            bind_group = self.device.create_bind_group(
                layout=self.mesh_bind_group_layout,
                entries=[
                    {
                        "binding": 0,
                        "resource": {"buffer": buffer, "offset": 0, "size": 112},
                    },
                    {
                        "binding": 1,
                        "resource": {"buffer": self.light_buffer, "offset": 0, "size": int(self.max_wgpu_lights) * 64},
                    },
                    {
                        "binding": 2,
                        "resource": {"buffer": self.lighting_uniform_buffer, "offset": 0, "size": 32},
                    },
                ],
            )
            self._frame_mesh_uniform_refs.append((buffer, bind_group))
            render_pass.set_bind_group(0, bind_group)
        except Exception:
            self.queue.write_buffer(self.mesh_uniform_buffer, 0, uniform)
            render_pass.set_bind_group(0, self.mesh_bind_group)

    def _set_line_uniform(self, render_pass, mvp, color: tuple[float, float, float, float], *, target_color: bool = True) -> None:
        uniform = self._line_uniform_bytes(mvp, color, target_color=target_color)
        try:
            import numpy as np
            import wgpu

            if self.device is None or self.line_bind_group_layout is None:
                raise RuntimeError("line uniform layout unavailable")
            buffer = self.device.create_buffer_with_data(
                data=np.frombuffer(uniform, dtype=np.uint8),
                usage=wgpu.BufferUsage.UNIFORM,
            )
            bind_group = self.device.create_bind_group(
                layout=self.line_bind_group_layout,
                entries=[
                    {
                        "binding": 0,
                        "resource": {"buffer": buffer, "offset": 0, "size": 80},
                    }
                ],
            )
            self._frame_line_uniform_refs.append((buffer, bind_group))
            render_pass.set_bind_group(0, bind_group)
        except Exception:
            self.queue.write_buffer(self.line_uniform_buffer, 0, uniform)
            render_pass.set_bind_group(0, self.line_bind_group)

    def render(self, scene, camera, W: int, H: int, *args, **kwargs):
        if W <= 0 or H <= 0:
            return None
        t0 = time.perf_counter()
        self.profiler.begin_frame()
        self._frame_line_uniform_refs = []
        self._frame_mesh_uniform_refs = []
        try:
            from PIL import Image

            self._active_camera = camera
            self._active_scene = scene
            self._active_anim_pose = kwargs.get("anim_pose")
            self._active_anim_base_pose = kwargs.get("anim_base_pose")
            self._active_skeleton_render_data = kwargs.get("skeleton_render_data")
            if self._active_skeleton_render_data is None and bool(getattr(self, "show_bones", False)):
                try:
                    from src.gui.rendering.skeleton_render_data import build_skeleton_render_data

                    self._active_skeleton_render_data = build_skeleton_render_data(
                        scene,
                        anim_pose=self._active_anim_pose,
                        selected_node=getattr(self, "selected_node", None),
                        selected_nodes=getattr(self, "selected_nodes", None),
                        hovered_node=getattr(self, "_hovered_bone", None),
                        show_dots=bool(getattr(self, "show_joint_dots", True)),
                        show_links=True,
                    )
                except Exception as exc:
                    self._active_skeleton_render_data = None
                    self.last_animation_error = str(exc)
            self._active_textures = dict(kwargs.get("textures") or {})
            raw_options = kwargs.get("display_options", None)
            self._active_display_options = raw_options if isinstance(raw_options, ViewportDisplayOptions) else self._display_options_from_legacy_flags()
            self._active_gizmo_render_data = kwargs.get("gizmo_render_data")
            self._active_lighting_render_data = kwargs.get("lighting_render_data")
            self._active_picking_diagnostics = dict(kwargs.get("picking_diagnostics") or {})
            self.hovered_node = kwargs.get("hovered_node")
            self.show_mesh_hover = bool(kwargs.get("show_mesh_hover", getattr(self, "show_mesh_hover", True)))
            self.show_grid = bool(self._active_display_options.show_grid)
            if not self.initialized:
                self.initialize()
            self.resize(int(W), int(H), 1.0)
            self.canvas.request_draw(self._draw_to_canvas)
            self.canvas.force_draw()
            payload = getattr(self.canvas, "_last_image", None)
            if not payload:
                img = Image.new("RGBA", (int(W), int(H)), (0, 0, 0, 0))
                self.perf["last_frame_ms"] = (time.perf_counter() - t0) * 1000.0
                self.perf["backend"] = self.backend_id
                self._finalize_profiler_frame()
                self.last_error = ""
                if not self._clear_logged:
                    log.info("WgpuRenderer: live clear/grid/mesh pass OK")
                    self._clear_logged = True
                return img
            _qimage, data = payload
            img = Image.fromarray(data)
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            self.perf["last_frame_ms"] = (time.perf_counter() - t0) * 1000.0
            self.perf["backend"] = self.backend_id
            self._finalize_profiler_frame()
            if not self._clear_logged:
                log.info("WgpuRenderer: clear/grid pass OK")
                self._clear_logged = True
            self.last_error = ""
            return img.copy()
        except Exception as exc:
            self.last_error = str(exc)
            self._finalize_profiler_frame()
            log.info("WgpuRenderer: render failed: %s", exc)
            return None

    def _finalize_profiler_frame(self) -> None:
        vertex_index_bytes = int(self.resource_cache.uploaded_vertex_count) * 72 + int(self.resource_cache.uploaded_index_count + self.resource_cache.uploaded_edge_index_count) * 4
        texture_bytes = int(self.resource_cache.texture_memory_bytes)
        self.profiler.set("buffer_upload_count", self.resource_cache.buffer_upload_count)
        self.profiler.set("texture_upload_count", self.resource_cache.texture_upload_count)
        self.profiler.set("bind_group_creation_count", self.resource_cache.bind_group_creation_count)
        self.profiler.set("pending_uploads", self._pending_uploads_count)
        self.profiler.set("cache_hits", self.resource_cache.cache_hits)
        self.profiler.set("cache_misses", self.resource_cache.cache_misses)
        self.profiler.set("estimated_texture_memory_bytes", texture_bytes)
        self.profiler.set("estimated_vertex_index_memory_bytes", vertex_index_bytes)
        self.profiler.set("estimated_gpu_memory_bytes", texture_bytes + vertex_index_bytes)
        self.profiler.end_frame(fallback_frame_ms=float(self.perf.get("last_frame_ms", 0.0) or 0.0))

    def render_overlay(self, overlay_context) -> None:
        return None

    def shutdown(self) -> None:
        try:
            if self.context is not None:
                self.context.unconfigure()
        except Exception:
            pass
        try:
            if self.canvas is not None:
                self.canvas.close()
                self.canvas.deleteLater()
        except Exception:
            pass
        self.canvas = None
        self.context = None
        self.device = None
        self.queue = None
        self.adapter = None
        self.pipeline_grid = None
        self.grid_bind_group = None
        self.grid_uniform_buffer = None
        self.grid_vertex_buffer = None
        self.pipeline_mesh = None
        self.pipeline_mesh_cutout = None
        self.pipeline_mesh_blend = None
        self.pipeline_mesh_skinned = None
        self.pipeline_mesh_skinned_cutout = None
        self.pipeline_mesh_skinned_blend = None
        self.pipeline_lines = None
        self.pipeline_gizmo_lines = None
        self.pipeline_pick = None
        self.skeleton_resource = None
        self.mesh_pipeline_layout = None
        self.skinned_mesh_pipeline_layout = None
        self.line_bind_group_layout = None
        self.line_bind_group = None
        self.line_uniform_buffer = None
        self.mesh_bind_group_layout = None
        self.skin_bind_group_layout = None
        self.texture_bind_group_layout = None
        self.mesh_bind_group = None
        self.mesh_uniform_buffer = None
        self.light_buffer = None
        self.lighting_uniform_buffer = None
        self.light_resource = None
        self._light_resource_revision_key = 0
        self.depth_texture = None
        self.depth_view = None
        self._pick_resources = None
        self._gizmo_line_cache.clear()
        self._depth_size = (0, 0)
        self.initialized = False
        self.live_surface = False
        self.resource_cache.invalidate_all("renderer shutdown")

    def clear_caches(self) -> None:
        self.resource_cache.invalidate_all("manual cache clear")
        self._gizmo_line_cache.clear()

    def invalidate_lighting(self, reason: str = "lighting changed") -> None:
        self.light_resource = None
        self._light_resource_revision_key = 0
        self._last_lighting_invalidation_reason = str(reason or "lighting changed")

    def invalidate_node(self, node) -> None:
        if node is not None:
            self.resource_cache.release_mesh(id(node))

    def invalidate_node_cache(self) -> None:
        self.resource_cache.invalidate_all("node cache invalidated")
        self.light_resource = None
        self._light_resource_revision_key = 0
        self._gizmo_line_cache.clear()

    def invalidate_all(self) -> None:
        self.resource_cache.invalidate_all("renderer invalidate_all")
        self.light_resource = None
        self._light_resource_revision_key = 0
        self._gizmo_line_cache.clear()

    def _refresh_themed_resources(self) -> None:
        self.resource_cache._missing_checker = None
        if self.initialized:
            self._create_grid_pipeline()

    def set_theme_colors(self, theme) -> None:
        self.viewport_background = _hex_to_rgb_float(theme.color("viewport.background"), self.viewport_background)
        self.grid_minor_color = _hex_to_rgb_float(theme.color("viewport.gridMinor"), self.grid_minor_color)
        self.grid_major_color = _hex_to_rgb_float(theme.color("viewport.gridMajor"), self.grid_major_color)
        self.grid_x_axis_color = _hex_to_rgb_float(theme.color("error"), self.grid_x_axis_color)
        self.grid_y_axis_color = _hex_to_rgb_float(theme.color("success"), self.grid_y_axis_color)
        self.wire_color = _hex_to_rgb_float(theme.color("accent.primary"), self.wire_color)
        self.hovered_edge_color = _hex_to_rgb_float(
            theme.color("viewport.helper.meshHover", theme.color("accent.secondary", "#00D7B5")),
            self.hovered_edge_color,
        )
        selection_color = theme.color("viewport.selection", "#FFD23F")
        self.selected_edge_color = _hex_to_rgb_float(selection_color, self.selected_edge_color)
        self.hidden_line_color = _hex_to_rgb_float(
            theme.color("viewport.border", theme.color("panel.border", theme.color("text.secondary"))),
            self.hidden_line_color,
        )
        self.null_helper_color = _hex_to_rgb_float(
            theme.color("viewport.helper.null", theme.color("viewport.text")),
            self.null_helper_color,
        )
        light_color = _hex_to_rgb_float(
            theme.color("viewport.helper.light", theme.color("warning")),
            self.light_helper_palette.get("light", (1.0, 0.82, 0.10)),
        )
        light_selected = _hex_to_rgb_float(selection_color, self.selected_edge_color)
        self.light_helper_palette = {
            **LIGHT_HELPER_COLORS,
            "light": light_color,
            "selected": light_selected,
        }
        self.light_resource = None
        self._light_resource_revision_key = 0
        self.missing_texture_color_a = _hex_to_rgb_float(
            theme.color("accent.secondary", theme.color("accent.primary")),
            self.missing_texture_color_a,
        )
        self.missing_texture_color_b = _hex_to_rgb_float(theme.color("viewport.background"), self.missing_texture_color_b)
        self._refresh_themed_resources()

    def reset_theme_colors(self) -> None:
        self.viewport_background = (23 / 255.0, 25 / 255.0, 28 / 255.0)
        self.grid_minor_color = (58 / 255.0, 64 / 255.0, 72 / 255.0)
        self.grid_major_color = (82 / 255.0, 90 / 255.0, 102 / 255.0)
        self.grid_x_axis_color = (118 / 255.0, 54 / 255.0, 54 / 255.0)
        self.grid_y_axis_color = (62 / 255.0, 112 / 255.0, 68 / 255.0)
        self.wire_color = (0.18, 0.62, 0.95)
        self.hidden_line_color = (0.02, 0.025, 0.03)
        self.hovered_edge_color = (0.0, 215 / 255.0, 181 / 255.0)
        self.hovered_edge_alpha = 0.45
        self.selected_edge_color = SELECTION_YELLOW
        self.null_helper_color = (0.64, 0.72, 0.82)
        self.light_helper_palette = {**LIGHT_HELPER_COLORS, "light": LIGHT_HELPER_COLORS["point"]}
        self.light_resource = None
        self._light_resource_revision_key = 0
        self.missing_texture_color_a = (1.0, 0.0, 1.0)
        self.missing_texture_color_b = (0.0, 0.0, 0.0)
        self._refresh_themed_resources()

    def set_native_palette_colors(self, *, base, text, highlight) -> None:
        bg = tuple(int(v) for v in base[:3])
        fg = tuple(int(v) for v in text[:3])
        hi = tuple(int(v) for v in highlight[:3])
        is_dark = _relative_luma(bg) < 0.45
        self.viewport_background = _rgb_float(bg)
        self.grid_minor_color = _rgb_float(_blend_rgb(bg, fg, 0.12 if is_dark else 0.18))
        self.grid_major_color = _rgb_float(_blend_rgb(bg, fg, 0.22 if is_dark else 0.30))
        self.grid_x_axis_color = _rgb_float((210, 70, 70) if is_dark else (160, 30, 30))
        self.grid_y_axis_color = _rgb_float((70, 180, 90) if is_dark else (40, 130, 55))
        self.wire_color = _rgb_float(hi)
        self.hovered_edge_color = (0.0, 215 / 255.0, 181 / 255.0)
        self.hovered_edge_alpha = 0.45
        self.selected_edge_color = SELECTION_YELLOW
        self.hidden_line_color = _rgb_float(_blend_rgb(bg, fg, 0.32 if is_dark else 0.40))
        self.null_helper_color = _rgb_float(_blend_rgb(bg, fg, 0.70 if is_dark else 0.55))
        light_color = _rgb_float((255, 210, 64))
        self.light_helper_palette = {**LIGHT_HELPER_COLORS, "light": light_color}
        self.light_resource = None
        self._light_resource_revision_key = 0
        self.missing_texture_color_a = _rgb_float(hi)
        self.missing_texture_color_b = _rgb_float(bg)
        self._refresh_themed_resources()

    def get_diagnostics(self) -> dict:
        caps = self.get_capabilities()
        adapter_info = _adapter_info_dict(self.adapter) if self.adapter is not None else dict(caps.details.get("adapter") or {})
        return {
            "name": self.name,
            "backend_id": self.backend_id,
            "available": caps.available,
            "api": "WGPU",
            "backend": self._spec.wgpu_backend_type or "auto",
            "format": self.format or caps.details.get("format"),
            "surface_format": self.format or caps.details.get("format"),
            "depth_format": self.depth_format,
            "adapter": adapter_info,
            "initialized": self.initialized,
            "visible_surface_type": type(self.canvas).__name__ if self.canvas is not None else "",
            "live_surface": self.live_surface,
            "supports_grid": True,
            "supports_scene_meshes": True,
            "supports_textures": True,
            "supports_object_picking": True,
            "supports_cpu_ray_picking": True,
            "supports_gpu_id_picking": True,
            "supports_selection_highlight": True,
            "supports_gizmo_drawing": True,
            "supports_gizmo_interaction": True,
            "supports_scene_lighting": True,
            "supports_light_helpers": True,
            "supports_light_volumes": True,
            "supports_batching": True,
            "supports_instancing": True,
            "supports_texture_streaming": True,
            "supports_texture_arrays": False,
            "supports_atlas": False,
            "supports_frustum_culling": True,
            "supports_gpu_timing": False,
            "supports_dynamic_quality": True,
            "performance_settings": {
                "enable_batching": bool(self.enable_batching),
                "enable_instancing": bool(self.enable_instancing),
                "enable_frustum_culling": bool(self.enable_frustum_culling),
                "enable_lazy_upload": bool(self.enable_lazy_upload),
                "enable_texture_arrays": bool(self.enable_texture_arrays),
                "enable_texture_atlas": bool(self.enable_texture_atlas),
                "profile_frames": bool(self.profiler.enabled),
                "dynamic_quality": bool(self.enable_dynamic_quality),
                "max_texture_memory_mb": int(self.max_texture_memory_mb),
                "max_uploads_per_frame": int(self.max_uploads_per_frame),
            },
            "performance": self.profiler.diagnostics(),
            "performance_audit": dict(self.performance_audit),
            "lighting": self._lighting_diagnostics(),
            "skeleton_overlay_supported": True,
            "joint_dot_overlay_supported": True,
            "bone_selection_supported": True,
            "skinned_mesh_supported": True,
            "gpu_skinning_supported": True,
            "cpu_skinning_fallback_supported": False,
            "animation_preview_supported": True,
            "skin_weight_heatmap_supported": False,
            "max_supported_bones": 128,
            "bone_matrix_buffer_type": "storage-buffer",
            "skinned_shader_status": self.skinned_mesh_pipeline_status,
            "supported_display_modes": WGPU_DISPLAY_MODES,
            "fallback_display_modes": dict(WGPU_FALLBACK_DISPLAY_MODES),
            "viewport_display": self._active_display_options.diagnostics(),
            "effective_viewport_display": self._effective_display_options.diagnostics(),
            "viewport_theme_colors": {
                "background": tuple(self.viewport_background),
                "grid_minor": tuple(self.grid_minor_color),
                "grid_major": tuple(self.grid_major_color),
                "grid_x_axis": tuple(self.grid_x_axis_color),
                "grid_y_axis": tuple(self.grid_y_axis_color),
                "wire": tuple(self.wire_color),
                "hidden_line": tuple(self.hidden_line_color),
                "hover": tuple(self.hovered_edge_color),
                "hover_alpha": float(getattr(self, "hovered_edge_alpha", 0.45)),
                "selection": tuple(self.selected_edge_color),
                "light_helper": tuple(self.light_helper_palette.get("point", self.light_helper_palette.get("light", LIGHT_HELPER_COLORS["point"]))),
                "null_helper": tuple(self.null_helper_color),
                "missing_texture_a": tuple(self.missing_texture_color_a),
                "missing_texture_b": tuple(self.missing_texture_color_b),
            },
            "viewport_render_colors": {
                "target_color_space": "srgb" if _format_is_srgb(self.format) else "linear",
                "background": tuple(self._target_rgb(self.viewport_background)),
                "grid_minor": tuple(self._target_rgb(self.grid_minor_color)),
                "grid_major": tuple(self._target_rgb(self.grid_major_color)),
                "wire": tuple(self._target_rgb(self.wire_color)),
                "hidden_line": tuple(self._target_rgb(self.hidden_line_color)),
                "hover": tuple(self._target_rgb(self.hovered_edge_color)),
                "selection": tuple(self._target_rgb(self.selected_edge_color)),
                "light_helper": tuple(self._target_rgb(self.light_helper_palette.get("point", self.light_helper_palette.get("light", LIGHT_HELPER_COLORS["point"])))),
                "null_helper": tuple(self._target_rgb(self.null_helper_color)),
            },
            "display_mode_downgrade": self._display_mode_downgrade,
            "last_display_mode_warning": self.last_display_mode_warning,
            "picking_provider_active": bool(self._active_picking_diagnostics.get("picking_provider_active", False)),
            "picking_method": self._active_picking_diagnostics.get("picking_method", "WGPU GPU ID"),
            "last_pick": dict(self.last_pick_diagnostics or self._active_picking_diagnostics.get("last_pick", {}) or {}),
            "gpu_pick_pipeline_status": self.pick_pipeline_status,
            "selected_object_count": int(self._active_picking_diagnostics.get("selected_object_count", 0) or 0),
            "selected_node_count": int(self._active_picking_diagnostics.get("selected_node_count", 0) or 0),
            "selection_highlight_pipeline_status": "ready" if self.pipeline_lines is not None else self.line_pipeline_status,
            "gizmo_render_pipeline_status": self.gizmo_pipeline_status,
            "skeleton_overlay_pipeline_status": self.skeleton_overlay_pipeline_status,
            "skinned_mesh_pipeline_status": self.skinned_mesh_pipeline_status,
            "gpu_skinning_status": self.gpu_skinning_status,
            "gizmo_hover_target": self._active_picking_diagnostics.get("gizmo_hover_target"),
            "active_gizmo_tool": self._active_picking_diagnostics.get("active_gizmo_tool"),
            "active_axis_mode": self._active_picking_diagnostics.get("active_axis_mode"),
            "device_pixel_ratio": self._active_picking_diagnostics.get(
                "device_pixel_ratio",
                (getattr(self, "surface_host_diagnostics", {}) or {}).get("device_pixel_ratio", 1.0),
            ),
            "surface_widget_class": self._active_picking_diagnostics.get(
                "surface_widget_class",
                (getattr(self, "surface_host_diagnostics", {}) or {}).get("current_surface_widget_class", ""),
            ),
            "input_bridge_installed": self._active_picking_diagnostics.get(
                "input_bridge_installed",
                (getattr(self, "surface_host_diagnostics", {}) or {}).get("input_bridge_installed", False),
            ),
            "grid_pipeline_status": self.grid_pipeline_status,
            "mesh_pipeline_status": self.mesh_pipeline_status,
            "textured_mesh_pipeline_status": self.textured_mesh_pipeline_status,
            "solid_pipeline_status": self.mesh_pipeline_status,
            "line_pipeline_status": self.line_pipeline_status,
            "gizmo_pipeline_status": self.gizmo_pipeline_status,
            "edge_overlay_status": "ready" if self.pipeline_lines is not None else self.line_pipeline_status,
            "opaque_pipeline_status": "ready" if self.pipeline_mesh is not None else "not created",
            "alpha_cutout_pipeline_status": "ready" if self.pipeline_mesh_cutout is not None else "not created",
            "alpha_pipeline_status": self.alpha_pipeline_status,
            "active_animation_clip": str(getattr(self._active_skeleton_render_data, "active_clip_name", "") or getattr(self, "_active_anim_name", "")),
            "animation_time": float(getattr(self._active_anim_pose, "time", 0.0) or 0.0) if self._active_anim_pose is not None else 0.0,
            "animation_playing": bool(self._active_anim_pose is not None),
            "skeleton_count": 1 if self._active_skeleton_render_data is not None else 0,
            "bone_count": len(tuple(getattr(self._active_skeleton_render_data, "bones", ()) or ())) if self._active_skeleton_render_data is not None else 0,
            "selected_bone_count": len(tuple(getattr(self._active_skeleton_render_data, "selected_bone_ids", ()) or ())) if self._active_skeleton_render_data is not None else 0,
            "skinned_mesh_count": int(self._active_skinned_mesh_count),
            "cpu_skinned_mesh_count": int(self._active_cpu_skinned_mesh_count),
            "uploaded_bone_matrix_count": int(self.resource_cache.uploaded_bone_matrix_count),
            "max_bone_matrices_supported": 128,
            "pose_revision": int(getattr(self._active_skeleton_render_data, "revision", 0) or 0) if self._active_skeleton_render_data is not None else 0,
            "last_skinning_error": self.last_skinning_error,
            "last_animation_error": self.last_animation_error,
            "uploaded_mesh_count": len(self.resource_cache.meshes),
            "uploaded_material_count": len(self.resource_cache.materials),
            "uploaded_texture_count": len(self.resource_cache.textures),
            "uploaded_vertex_count": self.resource_cache.uploaded_vertex_count,
            "uploaded_index_count": self.resource_cache.uploaded_index_count,
            "uploaded_edge_index_count": self.resource_cache.uploaded_edge_index_count,
            "texture_memory_estimate_bytes": self.resource_cache.texture_memory_bytes,
            "vertex_index_memory_estimate_bytes": int(self.resource_cache.uploaded_vertex_count) * 72
            + int(self.resource_cache.uploaded_index_count + self.resource_cache.uploaded_edge_index_count) * 4,
            "estimated_gpu_memory_bytes": int(self.resource_cache.texture_memory_bytes)
            + int(self.resource_cache.uploaded_vertex_count) * 72
            + int(self.resource_cache.uploaded_index_count + self.resource_cache.uploaded_edge_index_count) * 4,
            "fallback_texture_count": self.resource_cache.fallback_texture_count,
            "missing_texture_count": self.resource_cache.missing_texture_count,
            "lightmap_texture_count": self.resource_cache.lightmap_texture_count,
            "resource_cache_hits": self.resource_cache.cache_hits,
            "resource_cache_misses": self.resource_cache.cache_misses,
            "mesh_upload_count": self.resource_cache.mesh_upload_count,
            "texture_upload_count": self.resource_cache.texture_upload_count,
            "buffer_upload_count": self.resource_cache.buffer_upload_count,
            "bind_group_creation_count": self.resource_cache.bind_group_creation_count,
            "last_cache_invalidation_reason": self.resource_cache.last_invalidation_reason,
            "total_mesh_count": int(self._active_total_mesh_count),
            "visible_mesh_count": int(self._active_visible_mesh_count),
            "culled_mesh_count": int(self._active_culled_mesh_count),
            "batch_count": int(self._last_batch_count),
            "material_group_count": int(self._last_material_group_count),
            "instance_group_count": int(self._last_instance_group_count),
            "instance_count": int(self._last_instance_count),
            "pipeline_switch_count": int(self._last_pipeline_switch_count),
            "pending_uploads": int(self._pending_uploads_count),
            "alpha_object_count": int(self._last_alpha_object_count),
            "alpha_sort_time_ms": round(float(self._last_alpha_sort_ms), 3),
            "alpha_sort_mode": "mesh-depth stable descending",
            "texture_array_status": "prepared; disabled by default" if not self.enable_texture_arrays else "eligible groups tracked",
            "texture_array_eligible_groups": int(self._last_texture_array_eligible_groups),
            "texture_array_eligible_textures": int(self._last_texture_array_eligible_textures),
            "texture_atlas_status": "prepared; disabled by default",
            "instancing_status": "prepared; conservative grouping diagnostics active",
            "batching_status": "enabled" if self.enable_batching else "disabled",
            "frustum_culling_status": "enabled" if self.enable_frustum_culling else "disabled",
            "lazy_upload_status": "visible resources uploaded on first draw; hidden/off-frustum resources deferred",
            "gizmo_buffer_cache_size": len(self._gizmo_line_cache),
            "pick_resource_size": (self._pick_resources.width, self._pick_resources.height) if self._pick_resources is not None else (0, 0),
            "alpha_material_count": sum(
                1 for item in self.resource_cache.materials.values() if item.alpha_mode in {"MASK", "CUTOUT", "BLEND"}
            ),
            "last_texture_upload_error": self.resource_cache.last_texture_upload_error,
            "last_material_binding_error": self.resource_cache.last_material_binding_error,
            "last_render_counts": dict(self._last_render_counts),
            "mesh_hover_enabled": bool(getattr(self, "show_mesh_hover", True)),
            "hovered_mesh": str(getattr(getattr(self, "hovered_node", None), "name", "") or ""),
            "surface_host": dict(getattr(self, "surface_host_diagnostics", {}) or {}),
            "last_error": self.last_error,
        }

    def _lighting_diagnostics(self) -> dict[str, object]:
        lighting = self._active_lighting_render_data
        resource = self.light_resource
        perf = self.profiler.diagnostics()
        selected = ""
        if lighting is not None:
            for light in tuple(getattr(lighting, "lights", ()) or ()):
                if bool(getattr(light, "selected", False)):
                    selected = str(getattr(light, "name", "") or getattr(light, "node_id", "") or "")
                    break
        return {
            "mode": str(getattr(lighting, "mode", getattr(self, "lighting_mode", "scene")) or "scene"),
            "complexity": str(getattr(lighting, "complexity", getattr(self, "shader_complexity_mode", "basic")) or "basic"),
            "rig": str(getattr(lighting, "rig", "kotor_original") or "kotor_original"),
            "total_scene_lights": len(tuple(getattr(lighting, "lights", ()) or ())) if lighting is not None else 0,
            "enabled_lights": len(tuple(getattr(lighting, "enabled_lights", ()) or ())) if lighting is not None else 0,
            "uploaded_lights": int(getattr(resource, "uploaded_light_count", 0) or 0),
            "max_wgpu_lights": int(self.max_wgpu_lights),
            "helpers_visible": bool(getattr(lighting, "show_helpers", getattr(self, "show_light_gizmos", True))),
            "volumes_visible": bool(getattr(lighting, "show_volumes", getattr(self, "show_light_radius_volumes", False))),
            "selected_light": selected,
            "selected_light_id": int(getattr(resource, "selected_light_id", 0) or 0),
            "light_buffer_revision": int(getattr(resource, "revision", 0) or 0),
            "light_buffer_upload_time_ms": round(float(getattr(resource, "upload_time_ms", self._last_lighting_upload_time_ms) or 0.0), 3),
            "wgpu_light_shader_status": "active" if self._last_light_shader_active else "inactive",
            "unsupported_light_types_count": int(getattr(resource, "unsupported_light_types", 0) or 0),
            "last_lighting_error": self._last_lighting_error,
            "last_redraw_reason": self._last_lighting_invalidation_reason,
            "helper_draw_calls": len(tuple(getattr(resource, "helper_batches", ()) or ())),
            "volume_draw_calls": len(tuple(getattr(resource, "volume_batches", ()) or ())),
            "lighting_shader_active": bool(self._last_light_shader_active),
            "light_buffer_updates": int(perf.get("light_buffer_updates", 0) or 0) if isinstance(perf, dict) else 0,
            "diffuse_enabled": bool(getattr(lighting, "diffuse_enabled", getattr(self, "show_diffuse_map", True))),
            "specular_enabled": bool(getattr(lighting, "specular_enabled", getattr(self, "show_specular_map", True))),
            "normal_enabled": bool(getattr(lighting, "normal_enabled", getattr(self, "show_normal_map", True))),
            "environment_enabled": bool(getattr(lighting, "environment_enabled", getattr(self, "show_environment_map", True))),
            "lightmap_enabled": bool(getattr(lighting, "lightmap_enabled", getattr(self, "show_lightmap_map", True))),
            "lm_intensity": float(getattr(lighting, "lm_intensity", getattr(self, "lightmap_intensity", 0.55)) or 0.0),
            "lm_mode": str(getattr(lighting, "lm_mode", getattr(self, "lightmap_mode", "baked")) or "baked"),
        }


_GRID_WGSL = """
struct Locals {
    mvp: mat4x4<f32>,
};

@group(0) @binding(0)
var<uniform> locals: Locals;

struct VertexInput {
    @location(0) position: vec3<f32>,
    @location(1) color: vec3<f32>,
};

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) color: vec3<f32>,
};

@vertex
fn vs_main(input: VertexInput) -> VertexOutput {
    var out: VertexOutput;
    out.position = locals.mvp * vec4<f32>(input.position, 1.0);
    out.color = input.color;
    return out;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    return vec4<f32>(input.color, 1.0);
}
"""


_LINE_WGSL = """
struct Locals {
    mvp: mat4x4<f32>,
    color: vec4<f32>,
};

@group(0) @binding(0)
var<uniform> locals: Locals;

struct VertexInput {
    @location(0) position: vec3<f32>,
};

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
};

@vertex
fn vs_main(input: VertexInput) -> VertexOutput {
    var out: VertexOutput;
    out.position = locals.mvp * vec4<f32>(input.position, 1.0);
    return out;
}

@fragment
fn fs_main(_input: VertexOutput) -> @location(0) vec4<f32> {
    return locals.color;
}
"""


_PICK_WGSL = """
struct Locals {
    mvp: mat4x4<f32>,
    color: vec4<f32>,
};

@group(0) @binding(0)
var<uniform> locals: Locals;

struct VertexInput {
    @location(0) position: vec3<f32>,
};

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
};

@vertex
fn vs_main(input: VertexInput) -> VertexOutput {
    var out: VertexOutput;
    out.position = locals.mvp * vec4<f32>(input.position, 1.0);
    return out;
}

@fragment
fn fs_main(_input: VertexOutput) -> @location(0) vec4<f32> {
    return locals.color;
}
"""


_MESH_TEXTURED_WGSL = """
struct Locals {
    mvp: mat4x4<f32>,
    color: vec4<f32>,
    flags: vec4<f32>,
    params: vec4<f32>,
};

@group(0) @binding(0)
var<uniform> locals: Locals;

@group(1) @binding(0)
var diffuse_tex: texture_2d<f32>;
@group(1) @binding(1)
var diffuse_sampler: sampler;
@group(1) @binding(2)
var lightmap_tex: texture_2d<f32>;
@group(1) @binding(3)
var lightmap_sampler: sampler;

struct VertexInput {
    @location(0) position: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) uv0: vec2<f32>,
    @location(3) uv1: vec2<f32>,
};

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) uv0: vec2<f32>,
    @location(1) uv1: vec2<f32>,
};

@vertex
fn vs_main(input: VertexInput) -> VertexOutput {
    var out: VertexOutput;
    out.position = locals.mvp * vec4<f32>(input.position, 1.0);
    out.uv0 = vec2<f32>(input.uv0.x, 1.0 - input.uv0.y);
    out.uv1 = vec2<f32>(input.uv1.x, 1.0 - input.uv1.y);
    return out;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    let diffuse_sample = textureSample(diffuse_tex, diffuse_sampler, input.uv0);
    var sampled = diffuse_sample;
    if (locals.flags.x < 0.5) {
        sampled = vec4<f32>(1.0, 1.0, 1.0, 1.0);
    }
    var out_color = vec4<f32>(sampled.rgb * locals.color.rgb, sampled.a * locals.color.a);
    if (locals.params.y > 1.5) {
        let n = normalize(input.normal);
        let light = normalize(vec3<f32>(0.45, 0.35, 0.82));
        let ndotl = max(dot(n, light), 0.0);
        out_color = vec4<f32>(out_color.rgb * (0.45 + ndotl * 0.55), out_color.a);
    }
    if (locals.flags.y > 0.5) {
        let lightmap_sample = textureSample(lightmap_tex, lightmap_sampler, input.uv1);
        out_color = vec4<f32>(out_color.rgb * lightmap_sample.rgb * locals.params.x, out_color.a);
    }
    if (locals.flags.z > 0.5 && locals.flags.z < 1.5 && out_color.a < locals.flags.w) {
        discard;
    }
    if (locals.params.w > 0.5) {
        out_color = vec4<f32>(mix(out_color.rgb, vec3<f32>(1.0, 0.78, 0.12), 0.45), out_color.a);
    }
    return out_color;
}
"""


_MESH_BASIC_WGSL = """
struct Locals {
    mvp: mat4x4<f32>,
    color: vec4<f32>,
};

@group(0) @binding(0)
var<uniform> locals: Locals;

struct VertexInput {
    @location(0) position: vec3<f32>,
    @location(1) normal: vec3<f32>,
};

struct VertexOutput {
    @builtin(position) position: vec4<f32>,
    @location(0) normal: vec3<f32>,
};

@vertex
fn vs_main(input: VertexInput) -> VertexOutput {
    var out: VertexOutput;
    out.position = locals.mvp * vec4<f32>(input.position, 1.0);
    out.normal = normalize(input.normal);
    return out;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    let light_dir = normalize(vec3<f32>(0.35, 0.55, 0.75));
    let ndotl = max(dot(normalize(input.normal), light_dir), 0.0);
    let shade = 0.38 + ndotl * 0.62;
    return vec4<f32>(locals.color.rgb * shade, locals.color.a);
}
"""
