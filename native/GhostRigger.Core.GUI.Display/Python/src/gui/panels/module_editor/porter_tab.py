"""Porter workflow tab."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class PorterTab(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)

    ACTIONS = ("Load Source Module", "Port K1 to K2", "Port K2 to K1", "Validate Port", "Generate Port Report")

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        for label in self.ACTIONS:
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self.actionRequested.emit(text))
            layout.addWidget(button)
        layout.addStretch(1)
