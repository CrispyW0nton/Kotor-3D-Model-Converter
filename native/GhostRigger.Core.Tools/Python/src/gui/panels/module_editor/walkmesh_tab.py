"""Walkmesh workflow tab."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class WalkmeshTab(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)
    roomSurfaceRequested = QtCore.Signal(str, str)

    ACTIONS = ("Load WOK", "Save WOK", "Generate Walkmesh", "Generate Walls", "Fill Floor Faces", "Paint Face", "Assign Face Type", "Validate Walkmesh", "Show Face Types", "Show Walkable/Non-walkable", "Show Edges", "Show Normals")
    ACTION_OBJECT_NAMES = {
        "Load WOK": "mapStudioWalkmeshLoadWokButton",
        "Save WOK": "mapStudioWalkmeshSaveWokButton",
        "Generate Walkmesh": "mapStudioWalkmeshGenerateButton",
        "Generate Walls": "mapStudioWalkmeshGenerateWallsButton",
        "Fill Floor Faces": "mapStudioWalkmeshFillFloorFacesButton",
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
        assignment_box = QtWidgets.QGroupBox("Room WOK Surface Assignment")
        assignment_layout = QtWidgets.QFormLayout(assignment_box)
        self.room_choice = QtWidgets.QComboBox()
        self.room_choice.setObjectName("mapStudioWalkmeshRoomComboBox")
        self.surface_choice = QtWidgets.QComboBox()
        self.surface_choice.setObjectName("mapStudioWalkmeshSurfaceComboBox")
        self.surface_assignment_label = QtWidgets.QLabel(
            "Choose an authored room and assign the WOK surface its generated floor should export with."
        )
        self.surface_assignment_label.setObjectName("mapStudioWalkmeshSurfaceAssignmentLabel")
        self.surface_assignment_label.setWordWrap(True)
        self.apply_surface_button = QtWidgets.QPushButton("Apply Room WOK Surface")
        self.apply_surface_button.setObjectName("mapStudioWalkmeshApplySurfaceButton")
        assignment_layout.addRow("Room:", self.room_choice)
        assignment_layout.addRow("Surface:", self.surface_choice)
        assignment_layout.addRow(self.surface_assignment_label)
        assignment_layout.addRow(self.apply_surface_button)
        layout.addWidget(assignment_box)
        for label in self.ACTIONS:
            button = QtWidgets.QPushButton(label)
            button.setObjectName(self.ACTION_OBJECT_NAMES.get(label, ""))
            button.clicked.connect(lambda _checked=False, text=label: self.actionRequested.emit(text))
            layout.addWidget(button)
        layout.addStretch(1)
        self.room_choice.currentIndexChanged.connect(self._update_surface_assignment_controls)
        self.surface_choice.currentIndexChanged.connect(self._update_surface_assignment_label)
        self.apply_surface_button.clicked.connect(self._emit_room_surface)

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

    def set_walkmesh_surfaces(self, surfaces) -> None:
        """Populate the room WOK surface selector from the core surface palette."""

        self.surface_choice.blockSignals(True)
        self.surface_choice.clear()
        for surface in tuple(surfaces or ()):
            surface_id = str(getattr(surface, "surface_id", "") or "")
            authoring_name = str(getattr(surface, "authoring_name", "") or getattr(surface, "name", "") or surface_id).replace("_", " ")
            walkable = bool(getattr(surface, "walkable", False))
            description = str(getattr(surface, "description", "") or "")
            state = "walkable" if walkable else "not walkable"
            self.surface_choice.addItem(
                f"{surface_id} - {authoring_name.title()} ({state})",
                {
                    "surface_id": surface_id,
                    "walkable": walkable,
                    "description": description,
                    "name": str(getattr(surface, "name", "") or surface_id),
                },
            )
        if self.surface_choice.count() <= 0:
            self.surface_choice.addItem("4 - Stone (walkable)", {"surface_id": "4", "walkable": True, "description": "Walkable stone floor.", "name": "STONE"})
        self.surface_choice.blockSignals(False)
        self._update_surface_assignment_controls()

    def set_room_surface_choices(self, rooms) -> None:
        """Populate authored room choices whose generated WOK surface can be edited."""

        current = self._current_room_resref()
        self.room_choice.blockSignals(True)
        self.room_choice.clear()
        restore_index = -1
        for choice in tuple(rooms or ()):
            resref = str(getattr(choice, "room_resref", "") or "")
            label = str(getattr(choice, "label", "") or resref)
            data = {
                "room_resref": resref,
                "primitive_type": str(getattr(choice, "primitive_type", "") or ""),
                "texture": str(getattr(choice, "texture", "") or ""),
                "floor_surface_id": str(getattr(choice, "floor_surface_id", "4") or "4"),
                "floor_surface_name": str(getattr(choice, "floor_surface_name", "") or ""),
                "walkable": bool(getattr(choice, "walkable", False)),
            }
            self.room_choice.addItem(label, data)
            if resref == current:
                restore_index = self.room_choice.count() - 1
        if self.room_choice.count() <= 0:
            self.room_choice.addItem("No generated room WOK surfaces", None)
        elif restore_index >= 0:
            self.room_choice.setCurrentIndex(restore_index)
        self.room_choice.blockSignals(False)
        self._update_surface_assignment_controls()

    def _current_room_data(self) -> dict:
        data = self.room_choice.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _current_surface_data(self) -> dict:
        data = self.surface_choice.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _current_room_resref(self) -> str:
        return str(self._current_room_data().get("room_resref") or "").strip()

    def _select_surface(self, surface_id: str) -> None:
        wanted = str(surface_id or "").strip()
        if not wanted:
            return
        for index in range(self.surface_choice.count()):
            data = self.surface_choice.itemData(index)
            if isinstance(data, dict) and str(data.get("surface_id") or "") == wanted:
                self.surface_choice.blockSignals(True)
                self.surface_choice.setCurrentIndex(index)
                self.surface_choice.blockSignals(False)
                return

    def _update_surface_assignment_controls(self) -> None:
        room = self._current_room_data()
        enabled = bool(room)
        self.room_choice.setEnabled(enabled)
        self.surface_choice.setEnabled(enabled)
        self.apply_surface_button.setEnabled(enabled)
        if enabled:
            self._select_surface(str(room.get("floor_surface_id") or "4"))
        self._update_surface_assignment_label()

    def _update_surface_assignment_label(self) -> None:
        room = self._current_room_data()
        if not room:
            self.surface_assignment_label.setText(
                "Create authored room geometry before assigning room WOK surfaces."
            )
            return
        surface = self._current_surface_data()
        current_name = str(room.get("floor_surface_name") or room.get("floor_surface_id") or "")
        next_name = str(surface.get("name") or surface.get("surface_id") or "")
        walkable = bool(surface.get("walkable", False))
        walkable_note = "walkable for normal traversal" if walkable else "not normal walkable traversal"
        self.surface_assignment_label.setText(
            f"{room.get('room_resref')} currently exports as {room.get('floor_surface_id')} {current_name}. "
            f"Apply {surface.get('surface_id')} {next_name} to make its generated WOK floor {walkable_note}. "
            "Use DOOR only for doorway/transition surfaces."
        )

    def _emit_room_surface(self) -> None:
        room = self._current_room_resref()
        surface = str(self._current_surface_data().get("surface_id") or "").strip()
        if room and surface:
            self.roomSurfaceRequested.emit(room, surface)
