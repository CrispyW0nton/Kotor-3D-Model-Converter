"""Qt module editor panel for GhostRigger."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from .qt_theme import heading


class QtModularModePanel(QtWidgets.QWidget):
    moduleActionRequested = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(heading("Module Editor"))
        self.tabs = QtWidgets.QTabWidget()
        root.addWidget(self.tabs, 1)
        for name, buttons in (
            ("Rooms", ["Load LYT", "Add Room", "Remove Room", "Save Layout"]),
            ("Walkmesh", ["Load WOK", "Generate Walls", "Paint Face", "Save WOK"]),
            ("Porter", ["Load Source Module", "Port K1 to K2", "Port K2 to K1"]),
            ("Builder", ["Generate Module Files", "Validate Module", "Open Output"]),
            ("Blueprints", ["Open Blueprint", "Save Blueprint", "Send to GModular"]),
        ):
            page = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(page)
            layout.setContentsMargins(6, 6, 6, 6)
            for button in buttons:
                btn = QtWidgets.QPushButton(button)
                btn.clicked.connect(lambda _checked=False, text=button: self._emit_action(text))
                layout.addWidget(btn)
            layout.addStretch(1)
            self.tabs.addTab(page, name)

        self.status_label = QtWidgets.QLabel("")
        root.addWidget(self.status_label)

    def _emit_action(self, action: str) -> None:
        self.status_label.setText(f"{action} requested.")
        self.moduleActionRequested.emit(action)
