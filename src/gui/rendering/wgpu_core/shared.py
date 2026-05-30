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
    RenderQueueCache,
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
from src.gui.viewports.viewport_display import ViewportDisplayMode, ViewportDisplayOptions, normalize_display_mode
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
    mip_level_count: int
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
    blend_mode: str
    sprite_alpha_source: int
    sprite_glow: float
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



__all__ = tuple(name for name in globals() if not name.startswith("__"))
