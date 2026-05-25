"""Qt-only diagnostics panel for the main GhostRigger shell."""

from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6 import QtCore, QtWidgets


class QtDiagnosticsPanel(QtWidgets.QWidget):
    """Small model diagnostics view used by ``QtMainWindow``.

    The panel intentionally stays lightweight: it is safe to import during
    Tk-free startup checks and it never touches legacy UI code.
    """

    def __init__(
        self,
        model_getter: Optional[Callable[[], Any]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._model_getter = model_getter
        self._diagnostics_service = None
        self._tool_registry = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.run_button = QtWidgets.QPushButton("Run Diagnostics")
        self.run_button.clicked.connect(lambda: self.run_diagnostics(None))
        layout.addWidget(self.run_button)

        self.text = QtWidgets.QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.text.setPlainText("No diagnostics run yet.")
        layout.addWidget(self.text, 1)

    def set_integration_services(self, *, diagnostics_service: Any = None, registry: Any = None) -> None:
        self._diagnostics_service = diagnostics_service
        self._tool_registry = registry

    @QtCore.Slot(object)
    def run_diagnostics(self, model: Any = None) -> str:
        """Render a concise diagnostics report for *model*."""
        if model is None and self._model_getter is not None:
            try:
                model = self._model_getter()
            except Exception as exc:
                report = f"Diagnostics unavailable: model getter failed: {exc}"
                self.text.setPlainText(report)
                return report

        if model is None:
            lines = ["No model loaded."]
            integration_lines = self._integration_report_lines()
            if integration_lines:
                lines.extend(["", "Module Integration / Tool Compatibility", *integration_lines])
            report = "\n".join(lines)
            self.text.setPlainText(report)
            return report

        lines = [
            f"Model: {getattr(model, 'name', '<unnamed>')}",
            f"Supermodel: {getattr(model, 'supermodel', '') or 'NULL'}",
            f"Classification: {getattr(model, 'model_type', getattr(model, 'classification', ''))}",
        ]

        nodes = self._safe_list(model, "all_nodes")
        meshes = self._safe_list(model, "mesh_nodes")
        animations = list(getattr(model, "animations", []) or [])
        lines.extend([
            f"Nodes: {len(nodes)}",
            f"Meshes: {len(meshes)}",
            f"Animations: {len(animations)}",
        ])

        root = getattr(model, "root_node", None)
        if root is not None:
            lines.append(f"Root: {getattr(root, 'name', '<unnamed>')}")

        hook_names = [
            str(getattr(node, "name", "") or "")
            for node in nodes
            if "hook" in str(getattr(node, "name", "") or "").lower()
        ]
        if hook_names:
            lines.append("Hooks: " + ", ".join(sorted(hook_names, key=str.lower)))

        integration_lines = self._integration_report_lines()
        if integration_lines:
            lines.extend(["", "Module Integration / Tool Compatibility", *integration_lines])

        report = "\n".join(lines)
        self.text.setPlainText(report)
        return report

    @staticmethod
    def _safe_list(model: Any, method_name: str) -> list[Any]:
        method = getattr(model, method_name, None)
        if not callable(method):
            return []
        try:
            return list(method() or [])
        except Exception:
            return []

    def _integration_report_lines(self) -> list[str]:
        lines: list[str] = []
        service = self._diagnostics_service
        if service is not None:
            try:
                snapshot = service.snapshot()
                renderer = snapshot.renderer_diagnostics
                lines.extend(
                    [
                        f"Active viewport: {snapshot.active_viewport}",
                        f"Active renderer: {snapshot.active_renderer}",
                        f"Renderer backend: {renderer.get('backend_id', '') or 'unknown'}",
                        f"Registered tools/panels: {snapshot.registered_tools}",
                        f"Last tool action: {snapshot.last_tool_action or 'none'}",
                        f"Last scene update source: {snapshot.last_scene_update_source or 'none'}",
                        f"Last cache invalidation: {snapshot.last_cache_invalidation_reason or 'none'}",
                        f"Last redraw reason: {snapshot.last_renderer_redraw_reason or 'none'}",
                    ]
                )
                if snapshot.unsupported_active_feature_warnings:
                    lines.append(f"Unsupported feature warning: {snapshot.unsupported_active_feature_warnings}")
            except Exception as exc:
                lines.append(f"Integration diagnostics unavailable: {exc}")
        registry = self._tool_registry
        if registry is not None:
            try:
                for info in registry.all_tools():
                    wgpu = "WGPU yes" if info.wgpu_supported else "WGPU no"
                    null = "Null yes" if info.null_supported else "Null no"
                    limitation = f" - {info.known_limitations}" if info.known_limitations else ""
                    lines.append(f"- {info.menu_name}: {info.class_name} ({wgpu}, {null}){limitation}")
            except Exception as exc:
                lines.append(f"Tool registry unavailable: {exc}")
        return lines


class QtDiagnosticsWindow(QtWidgets.QMainWindow):
    """Standalone diagnostics utility window."""

    def __init__(
        self,
        model_getter: Optional[Callable[[], Any]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("GhostRigger Diagnostics")
        self.setWindowFlag(QtCore.Qt.Window, True)
        self.resize(760, 560)
        self.panel = QtDiagnosticsPanel(model_getter, self)
        self.setCentralWidget(self.panel)

    def run_diagnostics(self, model: Any = None) -> str:
        return self.panel.run_diagnostics(model)


__all__ = ["QtDiagnosticsPanel", "QtDiagnosticsWindow"]
