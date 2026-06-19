"""Walkmesh workflow tab."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class WalkmeshTab(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)

    ACTIONS = ("Load WOK", "Save WOK", "Generate Walkmesh", "Generate Walls", "Paint Face", "Assign Face Type", "Validate Walkmesh", "Show Face Types", "Show Walkable/Non-walkable", "Show Edges", "Show Normals")
    ACTION_OBJECT_NAMES = {
        "Load WOK": "mapStudioWalkmeshLoadWokButton",
        "Save WOK": "mapStudioWalkmeshSaveWokButton",
        "Generate Walkmesh": "mapStudioWalkmeshGenerateButton",
        "Generate Walls": "mapStudioWalkmeshGenerateWallsButton",
        "Paint Face": "mapStudioWalkmeshPaintFaceButton",
        "Assign Face Type": "mapStudioWalkmeshAssignFaceTypeButton",
        "Validate Walkmesh": "mapStudioWalkmeshValidateButton",
        "Show Face Types": "mapStudioWalkmeshShowFaceTypesButton",
        "Show Walkable/Non-walkable": "mapStudioWalkmeshShowWalkableButton",
        "Show Edges": "mapStudioWalkmeshShowEdgesButton",
        "Show Normals": "mapStudioWalkmeshShowNormalsButton",
    }

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        self.workflow_label = QtWidgets.QLabel(
            "Walkmesh workflow: create or load room geometry, generate WOK faces, paint surface types, validate, then use Walkmesh Preview before staging."
        )
        self.workflow_label.setObjectName("mapStudioWalkmeshWorkflowLabel")
        self.workflow_label.setWordWrap(True)
        self.surface_label = QtWidgets.QLabel(
            "KOTOR WOK face types: 1 WALK for reachable floors, 7 NON_WALK for walls/blockers, 18 DOOR for doorway portals, 23 WATER for water surfaces."
        )
        self.surface_label.setObjectName("mapStudioWalkmeshSurfaceLabel")
        self.surface_label.setWordWrap(True)
        self.validation_label = QtWidgets.QLabel(
            "Validation should confirm player start, doors, triggers, waypoints, creatures, and placeables sit on walkable faces before export/install."
        )
        self.validation_label.setObjectName("mapStudioWalkmeshValidationHintLabel")
        self.validation_label.setWordWrap(True)
        self.status_label = QtWidgets.QLabel("Walkmesh status: no authored module loaded.")
        self.status_label.setObjectName("mapStudioWalkmeshStatusLabel")
        self.status_label.setWordWrap(True)
        self.next_action_label = QtWidgets.QLabel("Next: create a starter room or terrain patch.")
        self.next_action_label.setObjectName("mapStudioWalkmeshNextActionLabel")
        self.next_action_label.setWordWrap(True)
        layout.addWidget(self.workflow_label)
        layout.addWidget(self.surface_label)
        layout.addWidget(self.validation_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.next_action_label)
        self.face_type = QtWidgets.QComboBox()
        self.face_type.setObjectName("mapStudioWalkmeshFaceTypeComboBox")
        self.face_type.addItems(["1 WALK", "7 NON_WALK", "18 DOOR", "23 WATER"])
        layout.addWidget(self.face_type)
        for label in self.ACTIONS:
            button = QtWidgets.QPushButton(label)
            button.setObjectName(self.ACTION_OBJECT_NAMES.get(label, ""))
            button.clicked.connect(lambda _checked=False, text=label: self.actionRequested.emit(text))
            layout.addWidget(button)
        layout.addStretch(1)

    def set_walkmesh_status(self, status) -> None:
        """Display core-authored walkmesh status without mutating the project."""

        if status is None:
            self.status_label.setText("Walkmesh status: no authored module loaded.")
            self.next_action_label.setText("Next: create a starter room or terrain patch.")
            return
        summary = str(getattr(status, "summary", "") or "Walkmesh status unavailable.")
        next_action = str(getattr(status, "next_action", "") or "Validate walkmesh before staging.")
        warnings = tuple(getattr(status, "warnings", ()) or ())
        warning_suffix = f" Warning: {warnings[0]}" if warnings else ""
        self.status_label.setText(f"{summary}{warning_suffix}")
        self.next_action_label.setText(f"Next: {next_action}")
