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

        button_row = QtWidgets.QHBoxLayout()
        self.run_button = QtWidgets.QPushButton("Run Diagnostics")
        self.run_button.clicked.connect(lambda: self.run_diagnostics(None))
        button_row.addWidget(self.run_button)
        self.copy_renderer_button = QtWidgets.QPushButton("Copy Renderer Diagnostics")
        self.copy_renderer_button.clicked.connect(self.copy_renderer_diagnostics)
        button_row.addWidget(self.copy_renderer_button)
        self.copy_performance_button = QtWidgets.QPushButton("Copy Performance Report")
        self.copy_performance_button.clicked.connect(self.copy_performance_report)
        button_row.addWidget(self.copy_performance_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

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
                performance_lines = self._performance_report_lines(renderer)
                if performance_lines:
                    lines.extend(["", "Performance / Resources", *performance_lines])
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

    @QtCore.Slot()
    def copy_renderer_diagnostics(self) -> None:
        report = self._renderer_report()
        QtWidgets.QApplication.clipboard().setText(report)

    @QtCore.Slot()
    def copy_performance_report(self) -> None:
        renderer = self._renderer_diagnostics()
        report = "\n".join(["Performance / Resources", *self._performance_report_lines(renderer)])
        QtWidgets.QApplication.clipboard().setText(report)

    def _renderer_diagnostics(self) -> dict[str, Any]:
        service = self._diagnostics_service
        if service is None:
            return {}
        try:
            return dict(service.snapshot().renderer_diagnostics or {})
        except Exception as exc:
            return {"error": str(exc)}

    def _renderer_report(self) -> str:
        renderer = self._renderer_diagnostics()
        lines = ["Renderer Diagnostics"]
        for key in sorted(renderer):
            value = renderer.get(key)
            if isinstance(value, dict):
                lines.append(f"{key}:")
                for sub_key in sorted(value):
                    lines.append(f"  {sub_key}: {value.get(sub_key)}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)

    @staticmethod
    def _performance_report_lines(renderer: dict[str, Any]) -> list[str]:
        perf = dict(renderer.get("performance") or {})
        lines = [
            f"Active renderer: {renderer.get('name') or renderer.get('backend_id') or 'unknown'}",
            f"Frame time: {perf.get('frame_time_ms', 0.0)} ms ({perf.get('fps_estimate', 0.0)} FPS)",
            f"Draw calls: {perf.get('draw_calls', renderer.get('draw_calls', 0))}",
            f"Batches: {renderer.get('batch_count', perf.get('batch_count', 0))}",
            f"Instances: {renderer.get('instance_count', perf.get('instance_count', 0))}",
            f"Visible meshes / total meshes: {renderer.get('visible_mesh_count', perf.get('visible_mesh_count', 0))} / {renderer.get('total_mesh_count', perf.get('mesh_count', 0))}",
            f"Culled meshes: {renderer.get('culled_mesh_count', perf.get('culled_mesh_count', 0))}",
            f"Uploaded meshes: {renderer.get('uploaded_mesh_count', 0)}",
            f"Uploaded textures: {renderer.get('uploaded_texture_count', 0)}",
            f"Texture memory estimate: {QtDiagnosticsPanel._bytes_with_mb(renderer.get('texture_memory_estimate_bytes', perf.get('estimated_texture_memory_bytes', 0)))}",
            f"Vertex/index memory estimate: {QtDiagnosticsPanel._bytes_with_mb(renderer.get('vertex_index_memory_estimate_bytes', perf.get('estimated_vertex_index_memory_bytes', 0)))}",
            f"Cache hits/misses: {renderer.get('resource_cache_hits', perf.get('cache_hits', 0))} / {renderer.get('resource_cache_misses', perf.get('cache_misses', 0))}",
            f"Pending uploads: {renderer.get('pending_uploads', perf.get('pending_uploads', 0))}",
            f"Last upload error: {renderer.get('last_texture_upload_error') or renderer.get('last_upload_error') or 'none'}",
            f"Pick pass time: {perf.get('pick_pass_ms', 0.0)} ms",
            f"Alpha sort count/time: {renderer.get('alpha_object_count', perf.get('alpha_object_count', 0))} / {renderer.get('alpha_sort_time_ms', perf.get('alpha_sort_ms', 0.0))} ms",
            f"Skeleton pose uploads/time: {perf.get('skeleton_pose_upload_count', 0)} / {perf.get('animation_pose_upload_ms', 0.0)} ms",
            f"Fallback reason: {renderer.get('reason') or renderer.get('last_display_mode_warning') or 'none'}",
        ]
        return lines

    @staticmethod
    def _bytes_with_mb(value: Any) -> str:
        try:
            byte_count = int(value or 0)
        except Exception:
            byte_count = 0
        mb = byte_count / (1024.0 * 1024.0)
        return f"{byte_count} bytes ({mb:.2f} MB)"


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
