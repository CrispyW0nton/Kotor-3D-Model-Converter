"""Optional retained-mode pygfx/WGPU viewport renderer."""

from __future__ import annotations

import importlib
import logging
import time
from importlib import util as importlib_util
from typing import Any, ClassVar

import numpy as np
from PIL import Image

from src.core.ports import ViewportRendererPort
from src.core.rendering.renderer_backend import RendererBackend
from src.core.rendering.renderer_capabilities import RendererCapabilities, WGPU_DISPLAY_MODES, WGPU_FALLBACK_DISPLAY_MODES
from src.core.rendering.renderer_settings import RendererSettings

from .backend_env import PygfxBackendEnvStatus, gpu_runtime_imported, prepare_pygfx_wgpu_environment
from .mesh_cache import PygfxMeshCache
from .scene_bridge import PygfxSceneBridge

log = logging.getLogger(__name__)


class PygfxViewportRenderer(ViewportRendererPort):
    """ViewportRendererPort adapter around pygfx.WgpuRenderer."""

    name = "pygfx / WGPU"
    backend_id = RendererBackend.PYGFX_WGPU.value
    _probe_cache: ClassVar[RendererCapabilities | None] = None
    _device_created: ClassVar[bool] = False

    def __init__(self, settings: RendererSettings | None = None) -> None:
        self.settings = settings or RendererSettings()
        self.canvas = None
        self.renderer = None
        self.scene = None
        self.camera = None
        self.mesh_cache = PygfxMeshCache()
        self.scene_bridge = None
        self.initialized = False
        self.live_surface = False
        self.last_error = ""
        self.last_display_mode_warning = ""
        self.adapter_info: dict[str, object] = {}
        self.backend_env_status: PygfxBackendEnvStatus | None = None
        self.surface_host_diagnostics: dict[str, object] = {}
        self.viewport_frame_governor_diagnostics: dict[str, object] = {}
        self.viewport_overlay_diagnostics: dict[str, object] = {}
        self._last_frame_ms = 0.0
        self._frame_count = 0
        self._gfx = None
        self._draw_callback_installed = False
        self._first_model_frame_logged = False
        self._active_model_id = 0
        self._last_dirty_flags: dict[str, bool] = {}
        self._background = None
        self._grid_helper = None
        self.show_grid = True
        self.show_solid = True
        self.show_wireframe = False
        self.show_texture = True
        self.show_lightmap_map = True
        self.render_mode = "realistic"
        self.display_options = None
        self.use_native_gizmo_overlay = False

    @staticmethod
    def _optional_module(name: str):
        return importlib.import_module(name)

    @classmethod
    def probe_availability(cls) -> RendererCapabilities:
        if cls._probe_cache is not None:
            return cls._probe_cache
        missing: list[str] = []
        for module_name in ("pygfx", "wgpu", "rendercanvas", "pylinalg"):
            if importlib_util.find_spec(module_name) is None:
                missing.append(module_name)
        available = not missing
        cls._probe_cache = RendererCapabilities(
            backend_id=RendererBackend.PYGFX_WGPU.value,
            name="pygfx / WGPU",
            available=available,
            reason="" if available else f"Missing optional dependency: {', '.join(missing)}",
            api="pygfx/WGPU",
            supports_scene_meshes=available,
            supports_textures=available,
            supports_grid=True,
            supports_overlays=True,
            supports_hot_switch=True,
            requires_restart=False,
            supported_display_modes=WGPU_DISPLAY_MODES,
            supported_display_options=("show_grid", "show_wire_overlay", "show_textures", "show_lightmaps"),
            fallback_display_modes=dict(WGPU_FALLBACK_DISPLAY_MODES),
            supports_object_picking=True,
            supports_cpu_ray_picking=True,
            supports_gpu_id_picking=False,
            supports_selection_highlight=True,
            supports_gizmo_drawing=False,
            supports_gizmo_interaction=True,
            skeleton_overlay_supported=True,
            joint_dot_overlay_supported=True,
            bone_selection_supported=True,
            skinned_mesh_supported=True,
            cpu_skinning_fallback_supported=True,
            animation_preview_supported=True,
            supports_texture_streaming=True,
            details={"retained_scene": True, "optional_dependencies": ("pygfx", "wgpu", "rendercanvas", "pylinalg")},
        )
        return cls._probe_cache

    def is_available(self) -> bool:
        return bool(self.get_capabilities().available)

    def get_capabilities(self) -> RendererCapabilities:
        return self.probe_availability()

    def create_surface_widget(self, parent=None):
        if self.canvas is not None:
            return self.canvas
        self._prepare_backend_environment()
        try:
            from PySide6 import QtCore, QtWidgets  # noqa: F401
            from rendercanvas.qt import QRenderWidget
        except Exception as exc:
            self.last_error = f"failed to create pygfx Qt surface: {exc}"
            raise RuntimeError(self.last_error) from exc
        widget = QRenderWidget(parent)
        widget.setObjectName("PygfxViewportSurface")
        widget.setAttribute(QtCore.Qt.WA_StyledBackground, False)
        widget.setAutoFillBackground(False)
        widget.setFocusPolicy(QtCore.Qt.StrongFocus)
        widget.setMouseTracking(True)
        self.canvas = widget
        return widget

    def _prepare_backend_environment(self) -> None:
        self.backend_env_status = prepare_pygfx_wgpu_environment(
            device_created=PygfxViewportRenderer._device_created,
            runtime_imported=gpu_runtime_imported(),
        )
        if self.backend_env_status.restart_required:
            self.last_error = self.backend_env_status.reason
            raise RuntimeError(self.last_error)

    def initialize(self, viewport_widget=None, scene_context=None) -> None:
        if self.initialized:
            return
        if not self.is_available():
            self.last_error = self.get_capabilities().reason
            raise RuntimeError(self.last_error)
        self._prepare_backend_environment()
        try:
            gfx = self._optional_module("pygfx")
            if viewport_widget is None:
                viewport_widget = self.canvas or self.create_surface_widget(None)
            self.canvas = viewport_widget
            self._gfx = gfx
            self.scene = gfx.Scene()
            self.camera = gfx.PerspectiveCamera(45.0, 1.0, depth_range=(0.01, 1000.0))
            self._configure_camera_up()
            self._install_empty_scene_helpers(gfx)
            self.renderer = gfx.WgpuRenderer(
                self.canvas,
                show_fps=bool(getattr(self.settings, "show_renderer_diagnostics", False)),
            )
            self.scene_bridge = PygfxSceneBridge(gfx, self.scene, self.mesh_cache)
            request_draw = getattr(self.canvas, "request_draw", None)
            if callable(request_draw):
                request_draw(self._draw_canvas_frame)
                self._draw_callback_installed = True
            PygfxViewportRenderer._device_created = True
            self.initialized = True
            self.live_surface = True
            self._capture_adapter_info()
            log.info("PygfxViewportRenderer: initialized %s", self.adapter_info)
        except Exception as exc:
            self.last_error = str(exc)
            self.initialized = False
            raise

    def resize(self, width: int, height: int, device_pixel_ratio: float = 1.0) -> None:
        if self.canvas is not None and width > 0 and height > 0:
            try:
                self.canvas.resize(int(width), int(height))
            except Exception:
                pass
            try:
                self.canvas._size_info.set_physical_size(
                    max(1, int(round(width * float(device_pixel_ratio or 1.0)))),
                    max(1, int(round(height * float(device_pixel_ratio or 1.0)))),
                    float(device_pixel_ratio or 1.0),
                )
            except Exception:
                pass
        if self.camera is not None:
            try:
                self.camera.aspect = max(1.0e-6, float(width) / max(1.0, float(height)))
            except Exception:
                pass
            try:
                self.camera.width = float(max(1, int(width)))
                self.camera.height = float(max(1, int(height)))
            except Exception:
                pass

    def render(self, scene, camera, W: int, H: int, *args, **kwargs):
        if not self.initialized:
            self.initialize(self.canvas, None)
        start = time.perf_counter()
        self.resize(W, H)
        self._update_camera(camera, W, H)
        self._apply_view_state()
        assert self.scene_bridge is not None
        selected_nodes = kwargs.get("selected_nodes") or [
            getattr(self, "selected_node", None),
            *(getattr(self, "selected_nodes", []) or []),
        ]
        dirty_flags = dict(kwargs.get("dirty_flags") or {})
        self._last_dirty_flags = dirty_flags
        model_id = id(scene) if scene is not None else 0
        needs_full_sync = self._needs_full_scene_sync(model_id, dirty_flags)
        if needs_full_sync:
            log_first_model_frame = bool(scene is not None and not self._first_model_frame_logged)
            if log_first_model_frame:
                log.info("PygfxViewportRenderer: first model frame update starting")
            self.scene_bridge.update_scene(
                scene,
                textures=kwargs.get("textures") or {},
                selected_nodes=selected_nodes,
                hovered_node=kwargs.get("hovered_node"),
                anim_pose=kwargs.get("anim_pose"),
                anim_base_pose=kwargs.get("anim_base_pose"),
                lighting_render_data=kwargs.get("lighting_render_data"),
            )
            self._active_model_id = model_id
            if log_first_model_frame:
                self._first_model_frame_logged = True
                log.info("PygfxViewportRenderer: first model frame update finished: %s", self.scene_bridge.diagnostics())
        else:
            if dirty_flags.get("transform") or dirty_flags.get("gizmo"):
                self.scene_bridge.update_dirty_transforms()
            if dirty_flags.get("selection"):
                self.scene_bridge.update_selection(selected_nodes, kwargs.get("hovered_node"))
            if dirty_flags.get("visibility"):
                self.scene_bridge.update_visibility()
            if dirty_flags.get("lighting"):
                self.scene_bridge.update_lighting(kwargs.get("lighting_render_data"))
        self.scene_bridge.apply_view_style(
            show_solid=bool(getattr(self, "show_solid", True)),
            show_wireframe=bool(getattr(self, "show_wireframe", False)),
            show_texture=bool(getattr(self, "show_texture", True)),
            render_mode=str(getattr(self, "render_mode", "realistic") or "realistic"),
            xray=bool(getattr(getattr(self, "display_options", None), "xray", False)),
        )
        self.scene_bridge.update_overlays(
            gizmo_render_data=kwargs.get("gizmo_render_data") if bool(getattr(self, "use_native_gizmo_overlay", False)) else None,
            skeleton_render_data=kwargs.get("skeleton_render_data"),
            lighting_render_data=kwargs.get("lighting_render_data"),
        )
        request_draw = getattr(self.canvas, "request_draw", None)
        if callable(request_draw):
            if self._draw_callback_installed:
                request_draw()
            else:
                request_draw(self._draw_canvas_frame)
                self._draw_callback_installed = True
        else:
            self._draw_canvas_frame()
        self._last_frame_ms = (time.perf_counter() - start) * 1000.0
        self._frame_count += 1
        return Image.new("RGBA", (max(1, int(W)), max(1, int(H))), (0, 0, 0, 0))

    def _install_empty_scene_helpers(self, gfx) -> None:
        if self.scene is None:
            return
        try:
            self._background = gfx.Background.from_color((0.035, 0.04, 0.045, 1.0))
            self.scene.add(self._background)
        except Exception:
            self._background = None
        try:
            self._grid_helper = self._create_z_up_grid(gfx, size=100.0, divisions=40)
            self.scene.add(self._grid_helper)
        except Exception:
            self._grid_helper = None

    def _apply_view_state(self) -> None:
        if self._grid_helper is not None:
            try:
                self._grid_helper.visible = bool(getattr(self, "show_grid", True))
            except Exception:
                pass

    def _create_z_up_grid(self, gfx, *, size: float, divisions: int):
        half = float(size) * 0.5
        divisions = max(2, min(80, int(divisions)))
        step = float(size) / float(divisions)
        points: list[tuple[float, float, float]] = []
        for index in range(divisions + 1):
            coord = -half + index * step
            points.extend(((-half, coord, 0.0), (half, coord, 0.0)))
            points.extend(((coord, -half, 0.0), (coord, half, 0.0)))
        geometry = gfx.Geometry(positions=np.asarray(points, dtype=np.float32))
        material = gfx.LineSegmentMaterial(
            color=(0.16, 0.20, 0.24, 1.0),
            thickness=1.0,
            thickness_space="screen",
        )
        return gfx.Line(geometry, material, render_order=-50, name="pygfx-z-up-grid")

    def _needs_full_scene_sync(self, model_id: int, dirty_flags: dict[str, bool]) -> bool:
        if model_id != self._active_model_id:
            return True
        if not self.mesh_cache.records and model_id:
            return True
        if not dirty_flags:
            return True
        return any(
            bool(dirty_flags.get(name))
            for name in ("scene", "resources", "geometry", "material")
        )

    def _draw_canvas_frame(self) -> None:
        if not self.initialized or self.renderer is None or self.scene is None or self.camera is None:
            return
        try:
            self.renderer.render(self.scene, self.camera, flush=True, clear=True)
        except Exception as exc:
            self.last_error = str(exc)
            log.info("PygfxViewportRenderer: rendercanvas draw failed: %s", exc)

    def pick(self, request, scene=None, camera=None):
        return None

    def shutdown(self) -> None:
        self.initialized = False
        self.live_surface = False
        self.renderer = None
        self.scene = None
        self.camera = None
        self.scene_bridge = None
        self.mesh_cache.clear()
        self._active_model_id = 0
        self._draw_callback_installed = False
        self._background = None
        self._grid_helper = None

    def clear_caches(self) -> None:
        if self.scene_bridge is not None:
            self.scene_bridge.clear()
        else:
            self.mesh_cache.clear()
        self._active_model_id = 0

    def invalidate_node(self, node) -> None:
        if node is None:
            return
        self.mesh_cache.mark_geometry_dirty(node)

    def invalidate_node_cache(self) -> None:
        self.clear_caches()

    def invalidate_transform_cache(self, reason: str = "transforms changed", node=None) -> None:
        self.mesh_cache.mark_transform_dirty(node)

    def invalidate_all(self) -> None:
        self.clear_caches()

    def get_diagnostics(self) -> dict:
        caps = self.get_capabilities()
        bridge_diag = self.scene_bridge.diagnostics() if self.scene_bridge is not None else self.mesh_cache.diagnostics()
        env = self.backend_env_status
        return {
            "name": self.name,
            "backend_id": self.backend_id,
            "available": caps.available,
            "reason": self.last_error or caps.reason,
            "api": "pygfx/WGPU",
            "initialized": self.initialized,
            "live_surface": self.live_surface,
            "visible_surface_type": type(self.canvas).__name__ if self.canvas is not None else "",
            "adapter": dict(self.adapter_info),
            "backend": (env.selected_backend if env is not None else "unknown"),
            "d3d12_requested": bool(env.d3d12_requested) if env is not None else False,
            "d3d12_selected": str(env.selected_backend).upper() == "D3D12" if env is not None else False,
            "d3d12_fallback": bool(env.d3d12_requested and str(env.selected_backend).upper() != "D3D12") if env is not None else False,
            "restart_required": bool(env.restart_required) if env is not None else False,
            "fps_source": "pygfx frame timing",
            "frame_time_ms": round(float(self._last_frame_ms), 3),
            "frame_count": int(self._frame_count),
            "supports_scene_lighting": True,
            "supports_textures": True,
            "supports_texture_streaming": True,
            "supports_light_helpers": True,
            "supports_light_volumes": True,
            "supports_gizmo_drawing": False,
            "supports_selection_highlight": True,
            "supports_gpu_id_picking": False,
            "last_display_mode_warning": self.last_display_mode_warning,
            "surface_host": dict(self.surface_host_diagnostics),
            "frame_governor": dict(self.viewport_frame_governor_diagnostics),
            "overlay": dict(self.viewport_overlay_diagnostics),
            "native_surface_passthrough": True,
            **bridge_diag,
        }

    def set_theme_colors(self, theme) -> None:
        try:
            bg = getattr(theme, "viewport_background", None) or getattr(theme, "background", None)
            if bg is not None:
                self.viewport_background = tuple(float(c) for c in bg[:3])
        except Exception:
            pass

    def set_native_palette_colors(self, *, base, text, highlight) -> None:
        try:
            self.viewport_background = tuple(float(c) / 255.0 for c in base[:3])
        except Exception:
            pass

    def _update_camera(self, source_camera, width: int, height: int) -> None:
        if self.camera is None or source_camera is None:
            return
        try:
            self._configure_camera_up()
            eye = tuple(float(v) for v in source_camera.eye()[:3])
            target = tuple(float(v) for v in getattr(source_camera, "target", (0.0, 0.0, 0.0))[:3])
            self.camera.fov = float(getattr(source_camera, "fov", 45.0) or 45.0)
            self.camera.aspect = max(1.0e-6, float(width) / max(1.0, float(height)))
            self.camera.depth_range = (
                max(0.001, float(getattr(source_camera, "_near", 0.01) or 0.01)),
                max(1.0, float(getattr(source_camera, "_far", 1000.0) or 1000.0)),
            )
            self.camera.local.position = eye
            self.camera.look_at(target)
        except Exception:
            pass

    def _configure_camera_up(self) -> None:
        if self.camera is None:
            return
        try:
            self.camera.local.reference_up = (0.0, 0.0, 1.0)
        except Exception:
            pass

    def _capture_adapter_info(self) -> None:
        try:
            shared = getattr(getattr(self.renderer, "_shared", None), "device", None)
            adapter = getattr(shared, "adapter", None) or getattr(shared, "_adapter", None)
            info = getattr(adapter, "info", None)
            self.adapter_info = dict(info or {})
        except Exception:
            self.adapter_info = {}
