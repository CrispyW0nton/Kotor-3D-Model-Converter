"""wgpu-py renderer backend for the Qt viewport.

This backend uses rendercanvas' Qt widget as the WGPU presentation surface.
ModernGL remains GhostRigger's complete scene renderer; WGPU currently provides
live-surface clear/grid plus basic untextured mesh rendering.
"""

from __future__ import annotations

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
from src.gui.rendering.renderer_capabilities import RendererCapabilities

log = logging.getLogger(__name__)

_WGPU_BACKEND_ENV = "WGPU_BACKEND_TYPE"
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
    vertex_count: int
    index_count: int
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
        self.textures: dict[str, WgpuTextureResource] = {}
        self.materials: dict[str, WgpuMaterialResource] = {}
        self.uploaded_vertex_count = 0
        self.uploaded_index_count = 0
        self.texture_memory_bytes = 0
        self.fallback_texture_count = 0
        self.missing_texture_count = 0
        self.lightmap_texture_count = 0
        self.last_texture_upload_error = ""
        self.last_material_binding_error = ""
        self._white_diffuse: WgpuTextureResource | None = None
        self._white_lightmap: WgpuTextureResource | None = None
        self._missing_checker: WgpuTextureResource | None = None

    def get_or_upload_mesh(self, mesh_data) -> WgpuMeshResource | None:
        mesh_id = int(mesh_data.mesh_id)
        cached = self.meshes.get(mesh_id)
        if cached is not None and cached.source_revision == mesh_data.source_revision:
            return cached
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
        packed = np.ascontiguousarray(np.column_stack((positions, normals, uvs0, uvs1)), dtype=np.float32)
        vertex_buffer = device.create_buffer_with_data(data=packed, usage=wgpu.BufferUsage.VERTEX)
        index_buffer = None
        index_count = 0
        if mesh_data.indices is not None and len(mesh_data.indices):
            indices = np.ascontiguousarray(mesh_data.indices, dtype=np.uint32)
            index_buffer = device.create_buffer_with_data(data=indices, usage=wgpu.BufferUsage.INDEX)
            index_count = int(len(indices))
        mins = positions.min(axis=0)
        maxs = positions.max(axis=0)
        resource = WgpuMeshResource(
            vertex_buffer=vertex_buffer,
            index_buffer=index_buffer,
            vertex_count=int(len(positions)),
            index_count=index_count,
            vertex_stride=40,
            bounds=(tuple(float(v) for v in mins), tuple(float(v) for v in maxs)),
            source_revision=mesh_data.source_revision,
        )
        self.meshes[int(mesh_id)] = resource
        self._recount()
        return resource

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
            return cached
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
            return cached
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
        texture = device.create_texture(
            label=label,
            size=(int(width), int(height), 1),
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
            dimension=wgpu.TextureDimension.d2,
            format=wgpu.TextureFormat.rgba8unorm,
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
            format="rgba8unorm",
            source_id=texture_id,
            source_revision=source_revision,
            label=label,
            byte_size=int(width) * int(height) * 4,
            fallback=fallback,
            lightmap=lightmap,
        )

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
                self._missing_checker = self._upload_rgba8_texture(
                    "__fallback_missing_checker__",
                    bytes([255, 0, 255, 255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 0, 255, 255]),
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
        self._recount()

    def invalidate_texture(self, texture_id: str) -> None:
        self.textures.pop(str(texture_id), None)
        self._recount()

    def invalidate_material(self, material_id: str) -> None:
        self.materials.pop(str(material_id), None)

    def invalidate_all(self) -> None:
        self.meshes.clear()
        self.textures.clear()
        self.materials.clear()
        self.uploaded_vertex_count = 0
        self.uploaded_index_count = 0
        self.texture_memory_bytes = 0
        self.fallback_texture_count = 0
        self.missing_texture_count = 0
        self.lightmap_texture_count = 0
        self.last_texture_upload_error = ""
        self.last_material_binding_error = ""
        self._white_diffuse = None
        self._white_lightmap = None
        self._missing_checker = None

    def _recount(self) -> None:
        self.uploaded_vertex_count = sum(int(item.vertex_count) for item in self.meshes.values())
        self.uploaded_index_count = sum(int(item.index_count) for item in self.meshes.values())
        self.texture_memory_bytes = sum(int(item.byte_size) for item in self.textures.values())
        self.lightmap_texture_count = sum(1 for item in self.textures.values() if item.lightmap)


class WgpuRenderer(NullDiagnosticRenderer):
    """Conservative WGPU renderer: Qt surface, clear pass, and grid pass."""

    _probe_cache: ClassVar[dict[RendererBackend, RendererCapabilities]] = {}
    _device_created: ClassVar[bool] = False

    def __init__(self, backend: RendererBackend = RendererBackend.WGPU_AUTO):
        super().__init__()
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
        self.mesh_pipeline_layout = None
        self.mesh_bind_group_layout = None
        self.texture_bind_group_layout = None
        self.mesh_bind_group = None
        self.mesh_uniform_buffer = None
        self.resource_cache = WgpuResourceCache(self)
        self.initialized = False
        self.live_surface = False
        self.textured_mesh_pipeline_status = "not created"
        self.alpha_pipeline_status = "not created"
        self.mesh_pipeline_status = "not created"
        self.grid_pipeline_status = "not created"
        self.last_error = ""
        self._last_size = (0, 0, 1.0)
        self._last_capabilities: RendererCapabilities | None = None
        self._clear_logged = False
        self._active_scene = None
        self._active_camera = None
        self._active_anim_pose = None
        self._active_textures: dict = {}
        self.surface_host_diagnostics: dict[str, object] = {}
        self.perf = {"last_frame_ms": 0.0, "backend": self.backend_id, "tri_count": 0}
        self.show_grid = True
        self.show_texture = True
        self.show_diffuse_map = True
        self.show_lightmap_map = True
        self.show_missing_texture_checker = False
        self.debug_texture_uploads = False
        self.force_untextured = False
        self.disable_lightmaps = False
        self.disable_alpha_blend = False
        self._last_render_counts = {"opaque": 0, "cutout": 0, "blended": 0}
        self.grid_minor_color = (58 / 255.0, 64 / 255.0, 72 / 255.0)
        self.grid_major_color = (82 / 255.0, 90 / 255.0, 102 / 255.0)
        self.grid_x_axis_color = (118 / 255.0, 54 / 255.0, 54 / 255.0)
        self.grid_y_axis_color = (62 / 255.0, 112 / 255.0, 68 / 255.0)

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

    def _create_grid_pipeline(self) -> None:
        import numpy as np
        import wgpu

        extent = 60
        major_every = 5
        rows: list[tuple[float, float, float, float, float, float]] = []
        for i in range(-extent, extent + 1):
            color = self.grid_x_axis_color if i == 0 else (self.grid_major_color if i % major_every == 0 else self.grid_minor_color)
            rows.append((-extent, i, 0.0, *color))
            rows.append((extent, i, 0.0, *color))
        for i in range(-extent, extent + 1):
            color = self.grid_y_axis_color if i == 0 else (self.grid_major_color if i % major_every == 0 else self.grid_minor_color)
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
        self.mesh_bind_group_layout = self.device.create_bind_group_layout(
            entries=[
                {
                    "binding": 0,
                    "visibility": wgpu.ShaderStage.VERTEX | wgpu.ShaderStage.FRAGMENT,
                    "buffer": {"type": wgpu.BufferBindingType.uniform},
                }
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
        self.mesh_bind_group = self.device.create_bind_group(
            layout=self.mesh_bind_group_layout,
            entries=[
                {
                    "binding": 0,
                    "resource": {"buffer": self.mesh_uniform_buffer, "offset": 0, "size": 112},
                }
            ],
        )
        self.mesh_pipeline_layout = self.device.create_pipeline_layout(
            bind_group_layouts=[self.mesh_bind_group_layout, self.texture_bind_group_layout]
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
        log.info("WgpuRenderer: textured mesh pipeline created")

    def _create_textured_pipeline(self, shader, *, blend: bool, depth_write: bool, alpha_label: str):
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
            layout=self.mesh_pipeline_layout,
            vertex={
                "module": shader,
                "entry_point": "vs_main",
                "buffers": [
                    {
                        "array_stride": 40,
                        "step_mode": wgpu.VertexStepMode.vertex,
                        "attributes": [
                            {"format": wgpu.VertexFormat.float32x3, "offset": 0, "shader_location": 0},
                            {"format": wgpu.VertexFormat.float32x3, "offset": 12, "shader_location": 1},
                            {"format": wgpu.VertexFormat.float32x2, "offset": 24, "shader_location": 2},
                            {"format": wgpu.VertexFormat.float32x2, "offset": 32, "shader_location": 3},
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
                    "clear_value": (*tuple(self.viewport_background[:3]), 1.0),
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
        self._draw_meshes(render_pass, width, height)
        render_pass.end()
        self.queue.submit([encoder.finish()])

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

        mvp = self._camera_mvp_matrix(self._active_camera, width, height)
        tri_count = 0
        draw_items = []
        for mesh_data in iter_mesh_render_data(
            self._active_scene,
            anim_pose=self._active_anim_pose,
            textures=self._active_textures,
        ):
            material_data = getattr(mesh_data, "material", None)
            if material_data is None:
                continue
            alpha_mode = str(getattr(material_data, "alpha_mode", "OPAQUE") or "OPAQUE").upper()
            if bool(getattr(self, "disable_alpha_blend", False)) and alpha_mode == "BLEND":
                alpha_mode = "OPAQUE"
            if bool(getattr(self, "force_untextured", False)):
                material_data = self._untextured_material(material_data)
                alpha_mode = str(getattr(material_data, "alpha_mode", "OPAQUE") or "OPAQUE").upper()
            sort_depth = 0.0
            if alpha_mode == "BLEND":
                sort_depth = self._mesh_sort_depth(mesh_data, self._active_camera)
            draw_items.append((alpha_mode, sort_depth, mesh_data, material_data))

        opaque = [item for item in draw_items if item[0] == "OPAQUE"]
        cutout = [item for item in draw_items if item[0] in {"MASK", "CUTOUT"}]
        blended = [item for item in draw_items if item[0] == "BLEND"]
        blended.sort(key=lambda item: item[1], reverse=True)
        counts = {"opaque": 0, "cutout": 0, "blended": 0}

        for pass_name, items, pipeline in (
            ("opaque", opaque, self.pipeline_mesh),
            ("cutout", cutout, self.pipeline_mesh_cutout or self.pipeline_mesh),
            ("blended", blended, self.pipeline_mesh_blend or self.pipeline_mesh),
        ):
            for _alpha_mode, _depth, mesh_data, material_data in items:
                tri_count += self._draw_mesh_item(render_pass, pipeline, mesh_data, material_data, mvp, pass_name)
                counts[pass_name] += 1
        self.perf["tri_count"] = int(tri_count)
        self._last_render_counts = counts
        if bool(getattr(self, "debug_texture_uploads", False)):
            log.info(
                "WgpuRenderer: rendered opaque=%s cutout=%s blended=%s",
                counts["opaque"],
                counts["cutout"],
                counts["blended"],
            )

    def _draw_mesh_item(self, render_pass, pipeline, mesh_data, material_data, mvp, pass_name: str) -> int:
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
            uniform = self._mesh_uniform_bytes(
                mvp,
                getattr(material_data, "base_color_rgba", mesh_data.material_color),
                material,
            )
            self.queue.write_buffer(self.mesh_uniform_buffer, 0, uniform)
            render_pass.set_pipeline(pipeline)
            render_pass.set_bind_group(0, self.mesh_bind_group)
            render_pass.set_bind_group(1, material.bind_group)
            render_pass.set_vertex_buffer(0, resource.vertex_buffer)
            if resource.index_buffer is not None and resource.index_count > 0:
                render_pass.set_index_buffer(resource.index_buffer, wgpu.IndexFormat.uint32)
                render_pass.draw_indexed(resource.index_count, 1, 0, 0, 0)
                return resource.index_count // 3
            render_pass.draw(resource.vertex_count, 1, 0, 0)
            return resource.vertex_count // 3
        except Exception as exc:
            log.warning("WgpuRenderer: skipped mesh %s: %s", getattr(mesh_data.source, "name", mesh_data.mesh_id), exc)
            return 0

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

    def _mesh_uniform_bytes(self, mvp, color: tuple[float, float, float, float], material) -> bytes:
        import numpy as np

        alpha_mode = str(getattr(material, "alpha_mode", "OPAQUE") or "OPAQUE").upper()
        alpha_mode_value = 1.0 if alpha_mode in {"MASK", "CUTOUT"} else 2.0 if alpha_mode == "BLEND" else 0.0
        flags = np.asarray(
            (
                1.0 if getattr(material, "diffuse_texture_resource", None) is not None else 0.0,
                1.0 if bool(getattr(material, "has_lightmap", False)) and not bool(getattr(self, "disable_lightmaps", False)) else 0.0,
                alpha_mode_value,
                float(getattr(material, "alpha_cutoff", 0.5) or 0.5),
            ),
            dtype=np.float32,
        )
        params = np.asarray((2.0, 0.0, 0.0, 0.0), dtype=np.float32)
        return (
            np.asarray(mvp, dtype=np.float32).reshape(4, 4).T.tobytes()
            + np.asarray(color, dtype=np.float32).tobytes()
            + flags.tobytes()
            + params.tobytes()
        )

    def render(self, scene, camera, W: int, H: int, *args, **kwargs):
        if W <= 0 or H <= 0:
            return None
        t0 = time.perf_counter()
        try:
            from PIL import Image

            self._active_camera = camera
            self._active_scene = scene
            self._active_anim_pose = kwargs.get("anim_pose")
            self._active_textures = dict(kwargs.get("textures") or {})
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
            if not self._clear_logged:
                log.info("WgpuRenderer: clear/grid pass OK")
                self._clear_logged = True
            self.last_error = ""
            return img.copy()
        except Exception as exc:
            self.last_error = str(exc)
            log.info("WgpuRenderer: render failed: %s", exc)
            return None

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
        self.mesh_pipeline_layout = None
        self.mesh_bind_group_layout = None
        self.texture_bind_group_layout = None
        self.mesh_bind_group = None
        self.mesh_uniform_buffer = None
        self.depth_texture = None
        self.depth_view = None
        self._depth_size = (0, 0)
        self.initialized = False
        self.live_surface = False
        self.resource_cache.invalidate_all()

    def clear_caches(self) -> None:
        self.resource_cache.invalidate_all()

    def invalidate_node(self, node) -> None:
        if node is not None:
            self.resource_cache.release_mesh(id(node))

    def invalidate_node_cache(self) -> None:
        self.resource_cache.invalidate_all()

    def invalidate_all(self) -> None:
        self.resource_cache.invalidate_all()

    def set_theme_colors(self, theme) -> None:
        self.viewport_background = _hex_to_rgb_float(theme.color("viewport.background"), self.viewport_background)
        self.grid_minor_color = _hex_to_rgb_float(theme.color("viewport.gridMinor"), self.grid_minor_color)
        self.grid_major_color = _hex_to_rgb_float(theme.color("viewport.gridMajor"), self.grid_major_color)
        self.grid_x_axis_color = _hex_to_rgb_float(theme.color("error"), self.grid_x_axis_color)
        self.grid_y_axis_color = _hex_to_rgb_float(theme.color("success"), self.grid_y_axis_color)
        if self.initialized:
            self._create_grid_pipeline()

    def set_native_palette_colors(self, *, base, text, highlight) -> None:
        self.viewport_background = tuple(max(0.0, min(1.0, float(v) / 255.0)) for v in base[:3])

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
            "grid_pipeline_status": self.grid_pipeline_status,
            "mesh_pipeline_status": self.mesh_pipeline_status,
            "textured_mesh_pipeline_status": self.textured_mesh_pipeline_status,
            "opaque_pipeline_status": "ready" if self.pipeline_mesh is not None else "not created",
            "alpha_cutout_pipeline_status": "ready" if self.pipeline_mesh_cutout is not None else "not created",
            "alpha_pipeline_status": self.alpha_pipeline_status,
            "uploaded_mesh_count": len(self.resource_cache.meshes),
            "uploaded_material_count": len(self.resource_cache.materials),
            "uploaded_texture_count": len(self.resource_cache.textures),
            "uploaded_vertex_count": self.resource_cache.uploaded_vertex_count,
            "uploaded_index_count": self.resource_cache.uploaded_index_count,
            "texture_memory_estimate_bytes": self.resource_cache.texture_memory_bytes,
            "fallback_texture_count": self.resource_cache.fallback_texture_count,
            "missing_texture_count": self.resource_cache.missing_texture_count,
            "lightmap_texture_count": self.resource_cache.lightmap_texture_count,
            "alpha_material_count": sum(
                1 for item in self.resource_cache.materials.values() if item.alpha_mode in {"MASK", "CUTOUT", "BLEND"}
            ),
            "last_texture_upload_error": self.resource_cache.last_texture_upload_error,
            "last_material_binding_error": self.resource_cache.last_material_binding_error,
            "last_render_counts": dict(self._last_render_counts),
            "surface_host": dict(getattr(self, "surface_host_diagnostics", {}) or {}),
            "last_error": self.last_error,
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
    var out_color = vec4<f32>(diffuse_sample.rgb * locals.color.rgb, diffuse_sample.a * locals.color.a);
    if (locals.flags.y > 0.5) {
        let lightmap_sample = textureSample(lightmap_tex, lightmap_sampler, input.uv1);
        out_color = vec4<f32>(out_color.rgb * lightmap_sample.rgb * locals.params.x, out_color.a);
    }
    if (locals.flags.z > 0.5 && locals.flags.z < 1.5 && out_color.a < locals.flags.w) {
        discard;
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
