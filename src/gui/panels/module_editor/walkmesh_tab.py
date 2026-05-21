"""Walkmesh workflow tab."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class WalkmeshTab(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)

    ACTIONS = ("Load WOK", "Save WOK", "Generate Walkmesh", "Generate Walls", "Paint Face", "Assign Face Type", "Validate Walkmesh", "Show Face Types", "Show Walkable/Non-walkable", "Show Edges", "Show Normals")

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        self.face_type = QtWidgets.QComboBox()
        self.face_type.addItems(["1 WALK", "7 NON_WALK", "18 DOOR", "23 WATER"])
        layout.addWidget(self.face_type)
        for label in self.ACTIONS:
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self.actionRequested.emit(text))
            layout.addWidget(button)
        layout.addStretch(1)
