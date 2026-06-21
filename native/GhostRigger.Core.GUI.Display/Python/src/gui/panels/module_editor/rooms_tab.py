"""Rooms workflow tab."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class RoomsTab(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)

    ACTIONS = ("Load LYT", "Add Room", "Remove Room", "Duplicate Room", "Save Layout", "Focus Selected Room", "Auto Arrange", "Snap Room to Grid")
    ACTION_OBJECT_NAMES = {
        "Load LYT": "mapStudioRoomsLoadLytButton",
        "Add Room": "mapStudioRoomsAddRoomButton",
        "Remove Room": "mapStudioRoomsRemoveRoomButton",
        "Duplicate Room": "mapStudioRoomsDuplicateRoomButton",
        "Save Layout": "mapStudioRoomsSaveLayoutButton",
        "Focus Selected Room": "mapStudioRoomsFocusSelectedButton",
        "Auto Arrange": "mapStudioRoomsAutoArrangeButton",
        "Snap Room to Grid": "mapStudioRoomsSnapToGridButton",
    }

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        self.workflow_label = QtWidgets.QLabel(
            "Rooms workflow: load or author room layout, arrange room positions, then validate LYT/VIS links before packaging."
        )
        self.workflow_label.setObjectName("mapStudioRoomsWorkflowLabel")
        self.workflow_label.setWordWrap(True)
        self.layout_label = QtWidgets.QLabel(
            "KOTOR room graph: LYT stores room models and transforms; VIS controls which rooms can see each other. Keep room resrefs stable for WOK, MDL/MDX, and placed resources."
        )
        self.layout_label.setObjectName("mapStudioRoomsLayoutHintLabel")
        self.layout_label.setWordWrap(True)
        self.authoring_label = QtWidgets.QLabel(
            "Use Builder for new geometry, then use Rooms to place, duplicate, focus, snap, and save the module room layout."
        )
        self.authoring_label.setObjectName("mapStudioRoomsAuthoringHintLabel")
        self.authoring_label.setWordWrap(True)
        layout.addWidget(self.workflow_label)
        layout.addWidget(self.layout_label)
        layout.addWidget(self.authoring_label)
        for label in self.ACTIONS:
            button = QtWidgets.QPushButton(label)
            button.setObjectName(self.ACTION_OBJECT_NAMES.get(label, ""))
            button.clicked.connect(lambda _checked=False, text=label: self.actionRequested.emit(text))
            layout.addWidget(button)
        layout.addStretch(1)
