"""Rooms workflow tab."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class RoomsTab(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)

    ACTIONS = ("Load LYT", "Add Room", "Remove Room", "Duplicate Room", "Save Layout", "Focus Selected Room", "Auto Arrange", "Snap Room to Grid")

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        for label in self.ACTIONS:
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self.actionRequested.emit(text))
            layout.addWidget(button)
        layout.addStretch(1)
