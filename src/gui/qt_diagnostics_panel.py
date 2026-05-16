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
            report = "No model loaded."
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


__all__ = ["QtDiagnosticsPanel"]
