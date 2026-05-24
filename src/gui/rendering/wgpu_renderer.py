"""wgpu-py renderer backend for the Qt viewport.

This backend uses rendercanvas' Qt widget as the WGPU presentation surface while
preserving GhostRigger's current viewport contract of returning a PIL image to
the Qt overlay compositor.  The first pass is intentionally conservative:
background clear plus a WGPU grid, with ModernGL kept as the full scene fallback.
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

    def __init__(self) -> None:
        self.meshes: dict[int, object] = {}
        self.textures: dict[int, object] = {}

    def upload_mesh(self, mesh_id: int, mesh_data) -> None:
        self.meshes[int(mesh_id)] = mesh_data

    def get_mesh_resource(self, mesh_id: int):
        return self.meshes.get(int(mesh_id))

    def release_mesh(self, mesh_id: int) -> None:
        self.meshes.pop(int(mesh_id), None)

    def upload_texture(self, texture_id: int, texture_data) -> None:
        self.textures[int(texture_id)] = texture_data

    def invalidate_all(self) -> None:
        self.meshes.clear()
        self.textures.clear()


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
        self.pipeline_grid = None
        self.grid_bind_group = None
        self.grid_uniform_buffer = None
        self.grid_vertex_buffer = None
        self.grid_vertex_count = 0
        self.resource_cache = WgpuResourceCache()
        self.initialized = False
        self.last_error = ""
        self._last_size = (0, 0, 1.0)
        self._last_capabilities: RendererCapabilities | None = None
        self._clear_logged = False
        self.perf = {"last_frame_ms": 0.0, "backend": self.backend_id, "tri_count": 0}
        self.show_grid = True
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
                supports_scene_meshes=False,
                supports_textures=False,
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
            self._create_grid_pipeline()
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
                # shown.  GhostRigger's current renderer contract still renders
                # through an internal widget and returns a PIL frame, so seed the
                # rendercanvas size record for that hidden surface.
                self.canvas._size_info.set_physical_size(
                    max(1, int(round(width * device_pixel_ratio))),
                    max(1, int(round(height * device_pixel_ratio))),
                    float(device_pixel_ratio or 1.0),
                )
            except Exception:
                pass

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
            depth_stencil=None,
            multisample=None,
            fragment={
                "module": shader,
                "entry_point": "fs_main",
                "targets": [{"format": self.format}],
            },
        )

    def _camera_mvp(self, camera, width: int, height: int) -> bytes:
        import numpy as np

        eye_attr = getattr(camera, "eye", (0.0, 5.0, 3.0))
        eye = tuple(eye_attr() if callable(eye_attr) else eye_attr)
        target_attr = getattr(camera, "target", (0.0, 0.0, 0.0))
        target = tuple(target_attr() if callable(target_attr) else target_attr)
        up_attr = getattr(camera, "up", None)
        up = tuple(up_attr() if callable(up_attr) else up_attr) if up_attr is not None else (0.0, 0.0, 1.0)
        fov = float(getattr(camera, "fov", 45.0))
        near = float(getattr(camera, "near", getattr(camera, "_near", 0.01)))
        far = float(getattr(camera, "far", getattr(camera, "_far", 2000.0)))
        proj = _mat4_perspective_wgpu(math.radians(fov), width / max(1, height), near, far)
        view = _mat4_lookat(eye, target, up)
        mvp = (proj @ view @ np.eye(4, dtype=np.float32)).astype(np.float32)
        return _mat4_tobytes(mvp)

    def _draw_to_canvas(self) -> None:
        import wgpu

        if self.context is None or self.device is None:
            return
        width, height = self.canvas.get_physical_size()
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
            ]
        )
        if self.show_grid and self.pipeline_grid is not None and self.grid_vertex_buffer is not None:
            self.queue.write_buffer(self.grid_uniform_buffer, 0, self._camera_mvp(self._active_camera, width, height))
            render_pass.set_pipeline(self.pipeline_grid)
            render_pass.set_bind_group(0, self.grid_bind_group)
            render_pass.set_vertex_buffer(0, self.grid_vertex_buffer)
            render_pass.draw(self.grid_vertex_count, 1, 0, 0)
        render_pass.end()
        self.queue.submit([encoder.finish()])

    def render(self, scene, camera, W: int, H: int, *args, **kwargs):
        if W <= 0 or H <= 0:
            return None
        t0 = time.perf_counter()
        try:
            from PIL import Image

            self._active_camera = camera
            if not self.initialized:
                self.initialize()
            self.resize(int(W), int(H), 1.0)
            self.canvas.request_draw(self._draw_to_canvas)
            self.canvas.force_draw()
            payload = getattr(self.canvas, "_last_image", None)
            if not payload:
                raise RuntimeError("WGPU render pass presented without bitmap readback")
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
        self.initialized = False
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
            "adapter": adapter_info,
            "initialized": self.initialized,
            "supports_grid": True,
            "supports_scene_meshes": False,
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
