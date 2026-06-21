"""Blueprint workflow tab."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class BlueprintsTab(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)

    ACTIONS = ("Open Blueprint", "Save Blueprint", "Add Blueprint", "Remove Blueprint", "Send to GModular", "Place Blueprint in Scene", "Validate Blueprint")
    ACTION_OBJECT_NAMES = {
        "Open Blueprint": "mapStudioBlueprintOpenButton",
        "Save Blueprint": "mapStudioBlueprintSaveButton",
        "Add Blueprint": "mapStudioBlueprintAddButton",
        "Remove Blueprint": "mapStudioBlueprintRemoveButton",
        "Send to GModular": "mapStudioBlueprintSendToGModularButton",
        "Place Blueprint in Scene": "mapStudioBlueprintPlaceInSceneButton",
        "Validate Blueprint": "mapStudioBlueprintValidateButton",
    }

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        self.workflow_label = QtWidgets.QLabel(
            "Blueprint workflow: edit KOTOR resource templates, validate them, then place instances into the module through Map Studio placement tools."
        )
        self.workflow_label.setObjectName("mapStudioBlueprintWorkflowLabel")
        self.workflow_label.setWordWrap(True)
        self.resource_label = QtWidgets.QLabel(
            "Template types: UTC creatures, UTP placeables, UTD doors, UTT triggers, UTW waypoints, UTS sounds, UTE encounters, and UTM merchants/stores."
        )
        self.resource_label.setObjectName("mapStudioBlueprintResourceTypesLabel")
        self.resource_label.setWordWrap(True)
        self.placement_label = QtWidgets.QLabel(
            "Blueprints define reusable resources; placed instances still need position, bearing, transition/script fields, and walkmesh validation before export."
        )
        self.placement_label.setObjectName("mapStudioBlueprintPlacementHintLabel")
        self.placement_label.setWordWrap(True)
        layout.addWidget(self.workflow_label)
        layout.addWidget(self.resource_label)
        layout.addWidget(self.placement_label)
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.setObjectName("mapStudioBlueprintTypeComboBox")
        self.type_combo.addItems(["Creature", "Placeable", "Door", "Trigger", "Waypoint", "Sound", "Encounter", "Merchant/Store", "Custom"])
        layout.addWidget(self.type_combo)
        for label in self.ACTIONS:
            button = QtWidgets.QPushButton(label)
            button.setObjectName(self.ACTION_OBJECT_NAMES.get(label, ""))
            button.clicked.connect(lambda _checked=False, text=label: self.actionRequested.emit(text))
            layout.addWidget(button)
        layout.addStretch(1)
