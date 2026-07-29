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
    ACTION_LABELS = {
        "Open Blueprint": "Open Blueprint Editor…",
        "Save Blueprint": "Save Blueprint As…",
        "Place Blueprint in Scene": "Place Selected Blueprint",
    }

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        self.workflow_label = QtWidgets.QLabel(
            "A blueprint is a reusable KOTOR template file—not a room layout. It defines what an NPC, door, "
            "placeable, trigger, or other resource is; the scene stores each placed instance's position."
        )
        self.workflow_label.setObjectName("mapStudioBlueprintWorkflowLabel")
        self.workflow_label.setWordWrap(True)
        self.resource_label = QtWidgets.QLabel(
            "Template types: UTC creatures, UTP placeables, UTD doors, UTT triggers, UTW waypoints, UTS sounds, UTE encounters, and UTM merchants/stores."
        )
        self.resource_label.setObjectName("mapStudioBlueprintResourceTypesLabel")
        self.resource_label.setWordWrap(True)
        self.placement_label = QtWidgets.QLabel(
            "More NPCs: Place automatically indexes every UTC in the configured target game, including Override "
            "and module templates. A similarly named MDL model is not a creature blueprint."
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
        self.type_description = QtWidgets.QLabel()
        self.type_description.setObjectName("mapStudioBlueprintTypeDescriptionLabel")
        self.type_description.setWordWrap(True)
        layout.addWidget(self.type_description)
        self.type_combo.currentTextChanged.connect(self._update_type_description)
        for label in self.ACTIONS:
            button = QtWidgets.QPushButton(self.ACTION_LABELS.get(label, label))
            button.setObjectName(self.ACTION_OBJECT_NAMES.get(label, ""))
            button.clicked.connect(lambda _checked=False, text=label: self.actionRequested.emit(text))
            layout.addWidget(button)
        layout.addStretch(1)
        self._update_type_description(self.type_combo.currentText())

    def _update_type_description(self, label: str) -> None:
        descriptions = {
            "Creature": "UTC · NPC identity, appearance, stats, faction, scripts, conversation, and inventory.",
            "Placeable": "UTP · interactive props, containers, terminals, usable objects, and their scripts.",
            "Door": "UTD · animated door behavior, locks, transitions, scripts, and appearance.",
            "Trigger": "UTT · invisible area volume that fires scripts or performs transitions.",
            "Waypoint": "UTW · named location used by scripts, transitions, and spawn logic.",
            "Sound": "UTS · positioned ambient or triggered audio behavior.",
            "Encounter": "UTE · creature spawn groups and activation geometry.",
            "Merchant/Store": "UTM · merchant inventory and pricing rules; stores have no viewport marker.",
            "Custom": "A supported template outside the common categories; validate its resource type before placement.",
        }
        self.type_description.setText(descriptions.get(str(label or ""), "Choose a template type."))

    def adopt_script_hook_tools(self, script_group: QtWidgets.QWidget) -> None:
        """Present ARE/IFO script-hook authoring in the Data workflow."""

        script_group.setParent(self)
        layout = self.layout()
        if isinstance(layout, QtWidgets.QVBoxLayout):
            layout.insertWidget(layout.count() - 1, script_group)
        script_group.show()
