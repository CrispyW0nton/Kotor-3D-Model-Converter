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
            "Blueprint workflow: edit KOTOR resource templates, validate them, then place instances through Place. "
            "A Blueprint is reusable object data, not a room: for example a UTC creature, UTP placeable, or UTD door. "
            "Rooms and terrain are level geometry built in Builder."
        )
        self.workflow_label.setObjectName("mapStudioBlueprintWorkflowLabel")
        self.workflow_label.setWordWrap(True)
        self.resource_label = QtWidgets.QLabel(
            "Template types: UTC creatures, UTP placeables, UTD doors, UTT triggers, UTW waypoints, UTS sounds, UTE encounters, and UTM merchants/stores. "
            "Import a custom NPC with Place → Import custom creature UTC; an MDL appearance alone is not a placeable NPC."
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

    def adopt_script_hook_tools(self, script_group: QtWidgets.QWidget) -> None:
        """Present ARE/IFO script-hook authoring in the Data workflow."""

        script_group.setParent(self)
        layout = self.layout()
        if isinstance(layout, QtWidgets.QVBoxLayout):
            layout.insertWidget(layout.count() - 1, script_group)
        script_group.show()
