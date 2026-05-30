"""Status bar and editor-integration services for the main window."""

from __future__ import annotations

try:
    from PySide6 import QtCore, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.qt_lib.integration.editor_services import (
    ActiveViewportService,
    DiagnosticsService,
    EditorIntegrationEventBus,
    RendererService,
    SceneService,
    SelectionService,
)
from src.gui.qt_lib.integration.tool_integration_registry import build_default_tool_integration_registry


class EditorServicesMixin:
    """Status text and renderer-aware integration services."""

    def _build_statusbar(self):
        status = self.statusBar()
        self.viewport_render_state_label = QtWidgets.QLabel(self)
        self.viewport_render_state_label.setObjectName("ViewportRenderStateStatus")
        self.viewport_render_state_label.setMinimumWidth(280)
        self.viewport_render_state_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.viewport_render_state_label.setToolTip("Active viewport renderer and display mode")
        status.addPermanentWidget(self.viewport_render_state_label, 0)
        self._on_viewport_render_state_changed(
            self.viewport.render_state_status_text() if hasattr(self, "viewport") else "Renderer: Unknown | Display: Unknown"
        )
        status.showMessage("Ready")

    def _install_editor_integration_services(self) -> None:
        """Install renderer-aware services for existing Qt tools and panels."""

        self.tool_integration_registry = build_default_tool_integration_registry()
        self.integration_event_bus = EditorIntegrationEventBus(self)
        self.active_viewport_service = ActiveViewportService(
            lambda: getattr(self, "viewport", None),
            scene_getter=lambda: getattr(getattr(self, "scene_manager", None), "active_scene", None),
            event_bus=self.integration_event_bus,
            parent=self,
        )
        self.renderer_service = RendererService(
            self.active_viewport_service,
            event_bus=self.integration_event_bus,
            parent=self,
        )
        self.scene_service = SceneService(
            lambda: getattr(getattr(self, "scene_manager", None), "active_scene", None),
            event_bus=self.integration_event_bus,
        )
        self.selection_service = SelectionService(
            self.active_viewport_service,
            event_bus=self.integration_event_bus,
        )
        self.diagnostics_service = DiagnosticsService(
            self.active_viewport_service,
            self.renderer_service,
            self.tool_integration_registry,
            event_bus=self.integration_event_bus,
        )
        viewport = getattr(self, "viewport", None)
        if viewport is not None:
            viewport.active_viewport_service = self.active_viewport_service
            viewport.renderer_service = self.renderer_service
            viewport.selection_service = self.selection_service
            viewport.scene_service = self.scene_service
            viewport.integration_event_bus = self.integration_event_bus
        diagnostics_panel = getattr(self, "diagnostics_panel", None)
        if diagnostics_panel is not None and hasattr(diagnostics_panel, "set_integration_services"):
            diagnostics_panel.set_integration_services(
                diagnostics_service=self.diagnostics_service,
                registry=self.tool_integration_registry,
            )

    def _record_renderer_tool_action(self, tool_id: str, action: str) -> None:
        bus = getattr(self, "integration_event_bus", None)
        if bus is not None:
            bus.record_tool_action(tool_id, action)

    def _invalidate_renderer_resources(self, reason: str) -> None:
        service = getattr(self, "renderer_service", None)
        if service is not None:
            service.request_resource_invalidation(reason)

    def _record_transform_event(self, node) -> None:
        bus = getattr(self, "integration_event_bus", None)
        if bus is not None:
            bus.transformChanged.emit(node)
            bus.record_scene_update("transform changed", node)

    def _record_pivot_event(self, node) -> None:
        bus = getattr(self, "integration_event_bus", None)
        if bus is not None:
            bus.pivotChanged.emit(node)
            bus.record_scene_update("pivot changed", node)

    def _record_camera_event(self, camera) -> None:
        bus = getattr(self, "integration_event_bus", None)
        if bus is not None:
            bus.cameraChanged.emit(camera)
            bus.record_scene_update("camera changed", camera)

    def _record_lighting_event(self, payload) -> None:
        bus = getattr(self, "integration_event_bus", None)
        if bus is not None:
            bus.lightingUpdated.emit(payload)
            bus.record_scene_update("lighting changed", payload)
        service = getattr(self, "renderer_service", None)
        if service is not None:
            service.request_resource_invalidation("lighting changed")

    @QtCore.Slot(str)
    def _on_renderer_backend_status_changed(self, text: str) -> None:
        bus = getattr(self, "integration_event_bus", None)
        service = getattr(self, "renderer_service", None)
        if bus is None or service is None:
            return
        backend = ""
        try:
            backend = service.get_diagnostics().get("backend_id", "") or ""
        except Exception:
            backend = ""
        if backend:
            bus.rendererBackendChanged.emit(str(backend))
        if "fallback" in str(text or "").lower():
            bus.rendererFallbackOccurred.emit(str(text))

    @QtCore.Slot(str)
    def _on_viewport_render_state_changed(self, text: str) -> None:
        label = getattr(self, "viewport_render_state_label", None)
        if label is not None:
            value = str(text or "Renderer: Unknown | Display: Unknown")
            label.setText(value)
            label.setToolTip(value)
