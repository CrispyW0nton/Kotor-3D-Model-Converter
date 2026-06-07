"""Blueprint workflow tab."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class BlueprintsTab(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)

    ACTIONS = ("Open Blueprint", "Save Blueprint", "Add Blueprint", "Remove Blueprint", "Send to GModular", "Place Blueprint in Scene", "Validate Blueprint")

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(["Creature", "Placeable", "Door", "Trigger", "Waypoint", "Sound", "Encounter", "Merchant/Store", "Custom"])
        layout.addWidget(self.type_combo)
        for label in self.ACTIONS:
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self.actionRequested.emit(text))
            layout.addWidget(button)
        layout.addStretch(1)
