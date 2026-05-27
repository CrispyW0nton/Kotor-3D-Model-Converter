"""Shared editor services that keep tools away from renderer internals."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Callable

from PySide6 import QtCore

from src.gui.rendering.renderer_backend import RendererBackend, normalize_renderer_backend
from src.gui.rendering.renderer_capabilities import (
    DIAGNOSTIC_DISPLAY_MODES,
    MODERNGL_DISPLAY_MODES,
    WGPU_DISPLAY_MODES,
    WGPU_FALLBACK_DISPLAY_MODES,
    RendererCapabilities,
)


def _safe_call(target: Any, name: str, *args, **kwargs) -> Any:
    method = getattr(target, name, None)
    if not callable(method):
        return None
    try:
        return method(*args, **kwargs)
    except Exception:
        return None


class EditorIntegrationEventBus(QtCore.QObject):
    """Qt signal hub for renderer-neutral editor state changes."""

    activeViewportChanged = QtCore.Signal(object)
    rendererBackendChanged = QtCore.Signal(str)
    rendererCapabilitiesChanged = QtCore.Signal(object)
    rendererFallbackOccurred = QtCore.Signal(str)
    sceneLoaded = QtCore.Signal(object)
    sceneCleared = QtCore.Signal()
    modelImported = QtCore.Signal(object)
    modelRemoved = QtCore.Signal(object)
    meshUpdated = QtCore.Signal(object)
    materialUpdated = QtCore.Signal(object)
    textureUpdated = QtCore.Signal(object)
    lightingUpdated = QtCore.Signal(object)
    cameraChanged = QtCore.Signal(object)
    selectionChanged = QtCore.Signal(object)
    transformChanged = QtCore.Signal(object)
    pivotChanged = QtCore.Signal(object)
    animationChanged = QtCore.Signal(object)
    displayModeChanged = QtCore.Signal(str)
    resourceCacheInvalidated = QtCore.Signal(str)
    rendererRedrawRequested = QtCore.Signal(str)
    toolAction = QtCore.Signal(str, str)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.last_tool_action = ""
        self.last_tool_id = ""
        self.last_scene_update_source = ""
        self.last_cache_invalidation_reason = ""
        self.last_renderer_redraw_reason = ""
        self.last_unsupported_feature_warning = ""

    def record_tool_action(self, tool_id: str, action: str) -> None:
        self.last_tool_id = str(tool_id or "")
        self.last_tool_action = str(action or "")
        self.toolAction.emit(self.last_tool_id, self.last_tool_action)

    def record_scene_update(self, source: str, payload: Any = None) -> None:
        self.last_scene_update_source = str(source or "")
        if source == "scene_loaded":
            self.sceneLoaded.emit(payload)
        elif source == "scene_cleared":
            self.sceneCleared.emit()
        elif source == "model_imported":
            self.modelImported.emit(payload)
        elif source == "model_removed":
            self.modelRemoved.emit(payload)

    def record_cache_invalidation(self, reason: str) -> None:
        self.last_cache_invalidation_reason = str(reason or "")
        self.resourceCacheInvalidated.emit(self.last_cache_invalidation_reason)

    def record_redraw(self, reason: str) -> None:
        self.last_renderer_redraw_reason = str(reason or "")
        self.rendererRedrawRequested.emit(self.last_renderer_redraw_reason)

    def warn_unsupported(self, message: str) -> None:
        self.last_unsupported_feature_warning = str(message or "")


class ActiveViewportService(QtCore.QObject):
    """Safe access to the currently active viewport and its shared state."""

    def __init__(
        self,
        viewport_getter: Callable[[], Any],
        *,
        scene_getter: Callable[[], Any] | None = None,
        event_bus: EditorIntegrationEventBus | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._viewport_getter = viewport_getter
        self._scene_getter = scene_getter
        self.event_bus = event_bus or EditorIntegrationEventBus(self)

    def get_active_viewport(self) -> Any:
        viewport = self._viewport_getter()
        self.event_bus.activeViewportChanged.emit(viewport)
        return viewport

    def get_active_renderer(self) -> Any:
        viewport = self.get_active_viewport()
        if viewport is None:
            return None
        return getattr(viewport, "_gpu_renderer", None) or getattr(viewport, "_renderer", None)

    def get_active_renderer_backend(self) -> str:
        viewport = self.get_active_viewport()
        if viewport is None:
            return ""
        backend_fn = getattr(viewport, "_active_renderer_backend_id", None)
        if callable(backend_fn):
            try:
                return str(backend_fn() or "")
            except Exception:
                return ""
        settings = getattr(viewport, "_renderer_settings", None)
        backend = getattr(settings, "backend", None)
        return str(getattr(backend, "value", backend) or "")

    def get_display_options(self) -> Any:
        viewport = self.get_active_viewport()
        return getattr(viewport, "display_options", None) if viewport is not None else None

    def request_redraw(self, reason: str = "") -> None:
        viewport = self.get_active_viewport()
        if viewport is not None:
            refresh = getattr(viewport, "refresh_view", None)
            if callable(refresh):
                refresh()
            else:
                _safe_call(viewport, "_request_render")
        self.event_bus.record_redraw(reason or "viewport redraw requested")

    def get_camera(self) -> Any:
        viewport = self.get_active_viewport()
        return getattr(viewport, "camera", None) if viewport is not None else None

    def get_scene(self) -> Any:
        if self._scene_getter is not None:
            try:
                return self._scene_getter()
            except Exception:
                return None
        viewport = self.get_active_viewport()
        return getattr(viewport, "_scene_instances", None) if viewport is not None else None

    def get_selection(self) -> Any:
        viewport = self.get_active_viewport()
        if viewport is None:
            return None
        meshes = _safe_call(viewport, "get_selected_meshes")
        if meshes:
            return list(meshes)
        renderer = getattr(viewport, "_renderer", None)
        return getattr(renderer, "selected_node", None)


class RendererService(QtCore.QObject):
    """Renderer capability and cache operations for panels and tools."""

    def __init__(
        self,
        viewport_service: ActiveViewportService,
        event_bus: EditorIntegrationEventBus | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.viewport_service = viewport_service
        self.event_bus = event_bus or viewport_service.event_bus

    def get_capabilities(self) -> RendererCapabilities:
        renderer = self.viewport_service.get_active_renderer()
        caps_fn = getattr(renderer, "get_capabilities", None)
        if callable(caps_fn):
            try:
                caps = caps_fn()
                if caps is not None:
                    self.event_bus.rendererCapabilitiesChanged.emit(caps)
                    return caps
            except Exception as exc:
                self.event_bus.warn_unsupported(f"Renderer capabilities unavailable: {exc}")
        caps = self._fallback_capabilities()
        self.event_bus.rendererCapabilitiesChanged.emit(caps)
        return caps

    def get_diagnostics(self) -> dict[str, Any]:
        renderer = self.viewport_service.get_active_renderer()
        diagnostics_fn = getattr(renderer, "get_diagnostics", None)
        if callable(diagnostics_fn):
            try:
                diagnostics = dict(diagnostics_fn() or {})
            except Exception as exc:
                diagnostics = {"error": str(exc)}
        else:
            diagnostics = {}
        caps = self.get_capabilities()
        diagnostics.setdefault("name", caps.name)
        diagnostics.setdefault("backend_id", caps.backend_id)
        diagnostics.setdefault("available", caps.available)
        diagnostics.setdefault("reason", caps.reason)
        diagnostics.setdefault("diagnostic_only", caps.diagnostic_only)
        return diagnostics

    def supports(self, feature_name: str) -> bool:
        caps = self.get_capabilities()
        key = str(feature_name or "").strip()
        if not key:
            return False
        return bool(getattr(caps, key, False))

    def request_mode(self, mode: str) -> None:
        viewport = self.viewport_service.get_active_viewport()
        if viewport is None:
            return
        if hasattr(viewport, "set_display_mode"):
            _safe_call(viewport, "set_display_mode", mode)
        elif hasattr(viewport, "set_render_mode"):
            _safe_call(viewport, "set_render_mode", mode)
        self.event_bus.displayModeChanged.emit(str(mode or ""))
        self.viewport_service.request_redraw(f"display mode changed: {mode}")

    def request_surface_refresh(self) -> None:
        viewport = self.viewport_service.get_active_viewport()
        if viewport is not None:
            _safe_call(viewport, "_sync_renderer_surface", force=True)
        self.viewport_service.request_redraw("renderer surface refresh")

    def request_resource_invalidation(self, reason: str = "") -> None:
        viewport = self.viewport_service.get_active_viewport()
        reason = reason or "resource invalidation requested"
        if viewport is not None:
            gpu = getattr(viewport, "_gpu_renderer", None)
            if gpu is not None:
                for method in ("invalidate_all", "clear_caches", "invalidate_node_cache"):
                    fn = getattr(gpu, method, None)
                    if callable(fn):
                        fn()
                        break
            renderer = getattr(viewport, "_renderer", None)
            if renderer is not None:
                cache = getattr(renderer, "_wt_cache", None)
                if hasattr(cache, "clear"):
                    cache.clear()
            refresh = getattr(viewport, "refresh_view", None)
            if callable(refresh):
                refresh()
        self.event_bus.record_cache_invalidation(reason)

    def _fallback_capabilities(self) -> RendererCapabilities:
        backend_id = self.viewport_service.get_active_renderer_backend() or RendererBackend.MODERNGL_GL330.value
        backend = normalize_renderer_backend(backend_id)
        if backend is RendererBackend.NULL_DIAGNOSTIC:
            return RendererCapabilities(
                backend_id=backend.value,
                name="Null Diagnostic",
                available=True,
                api="diagnostic",
                diagnostic_only=True,
                supported_display_modes=DIAGNOSTIC_DISPLAY_MODES,
                supports_hot_switch=True,
            )
        if str(backend.value).startswith("wgpu"):
            return RendererCapabilities(
                backend_id=backend.value,
                name="WGPU",
                available=True,
                api="wgpu",
                supports_scene_meshes=True,
                supports_textures=True,
                supports_grid=True,
                supports_hot_switch=True,
                supported_display_modes=WGPU_DISPLAY_MODES,
                fallback_display_modes=WGPU_FALLBACK_DISPLAY_MODES,
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
                animation_preview_supported=True,
                supports_batching=True,
                supports_instancing=True,
                supports_texture_streaming=True,
                supports_frustum_culling=True,
                supports_dynamic_quality=True,
            )
        return RendererCapabilities(
            backend_id=RendererBackend.MODERNGL_GL330.value,
            name="ModernGL / OpenGL 3.3",
            available=True,
            api="opengl",
            supports_scene_meshes=True,
            supports_textures=True,
            supports_grid=True,
            supports_hot_switch=True,
            supported_display_modes=MODERNGL_DISPLAY_MODES,
            supports_object_picking=True,
            supports_cpu_ray_picking=True,
            supports_selection_highlight=True,
            supports_gizmo_drawing=True,
            supports_gizmo_interaction=True,
            skeleton_overlay_supported=True,
            joint_dot_overlay_supported=True,
            bone_selection_supported=True,
            skinned_mesh_supported=True,
            animation_preview_supported=True,
            skin_weight_heatmap_supported=True,
        )


class SelectionService(QtCore.QObject):
    def __init__(self, viewport_service: ActiveViewportService, event_bus: EditorIntegrationEventBus | None = None) -> None:
        super().__init__()
        self.viewport_service = viewport_service
        self.event_bus = event_bus or viewport_service.event_bus

    def current(self) -> Any:
        return self.viewport_service.get_selection()

    def select_node(self, node: Any, *, source: str = "selection_service") -> None:
        viewport = self.viewport_service.get_active_viewport()
        if viewport is not None:
            _safe_call(viewport, "set_selected_node", node)
        self.event_bus.selectionChanged.emit(node)
        self.event_bus.record_tool_action(source, "selection changed")

    def select_meshes(self, nodes: list[Any], *, source: str = "selection_service") -> None:
        viewport = self.viewport_service.get_active_viewport()
        if viewport is not None:
            _safe_call(viewport, "set_selected_meshes", nodes)
        self.event_bus.selectionChanged.emit(list(nodes or []))
        self.event_bus.record_tool_action(source, "mesh selection changed")


class SceneService(QtCore.QObject):
    def __init__(self, scene_getter: Callable[[], Any], event_bus: EditorIntegrationEventBus | None = None) -> None:
        super().__init__()
        self._scene_getter = scene_getter
        self.event_bus = event_bus or EditorIntegrationEventBus(self)

    def get_scene(self) -> Any:
        try:
            return self._scene_getter()
        except Exception:
            return None


@dataclass
class DiagnosticsSnapshot:
    active_viewport: str = ""
    active_renderer: str = ""
    registered_tools: int = 0
    last_tool_action: str = ""
    last_scene_update_source: str = ""
    last_cache_invalidation_reason: str = ""
    last_renderer_redraw_reason: str = ""
    unsupported_active_feature_warnings: str = ""
    renderer_diagnostics: dict[str, Any] = field(default_factory=dict)


class DiagnosticsService(QtCore.QObject):
    def __init__(
        self,
        viewport_service: ActiveViewportService,
        renderer_service: RendererService,
        registry: Any = None,
        event_bus: EditorIntegrationEventBus | None = None,
    ) -> None:
        super().__init__()
        self.viewport_service = viewport_service
        self.renderer_service = renderer_service
        self.registry = registry
        self.event_bus = event_bus or viewport_service.event_bus
        self._snapshot_cache: DiagnosticsSnapshot | None = None
        self._snapshot_cache_time = 0.0
        self.diagnostics_hz = 2.0

    def snapshot(self, *, force: bool = False) -> DiagnosticsSnapshot:
        now = time.perf_counter()
        min_interval = 1.0 / max(0.1, float(getattr(self, "diagnostics_hz", 2.0) or 2.0))
        if not force and self._snapshot_cache is not None and now - self._snapshot_cache_time < min_interval:
            return self._snapshot_cache
        viewport = self.viewport_service.get_active_viewport()
        renderer_diag = self.renderer_service.get_diagnostics()
        snapshot = DiagnosticsSnapshot(
            active_viewport=type(viewport).__name__ if viewport is not None else "None",
            active_renderer=str(renderer_diag.get("name") or renderer_diag.get("backend_id") or "Unknown"),
            registered_tools=len(getattr(self.registry, "tools", {}) or {}),
            last_tool_action=self.event_bus.last_tool_action,
            last_scene_update_source=self.event_bus.last_scene_update_source,
            last_cache_invalidation_reason=self.event_bus.last_cache_invalidation_reason,
            last_renderer_redraw_reason=self.event_bus.last_renderer_redraw_reason,
            unsupported_active_feature_warnings=self.event_bus.last_unsupported_feature_warning,
            renderer_diagnostics=renderer_diag,
        )
        self._snapshot_cache = snapshot
        self._snapshot_cache_time = now
        return snapshot
