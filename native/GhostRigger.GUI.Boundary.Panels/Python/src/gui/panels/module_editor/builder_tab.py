"""Builder workflow tab."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class BuilderTab(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)
    primitivePresetRequested = QtCore.Signal(str, str)
    roomOperationRequested = QtCore.Signal(str, float, float, float, float, float)
    roomStyleRequested = QtCore.Signal(str, str)
    gameplayPlacementRequested = QtCore.Signal(str, str, str, float, float, float, float)

    ACTIONS = (
        "Create grdev01 Dev Room",
        "Generate Module Files",
        "Validate Module",
        "Open Output",
        "Build ERF/RIM Preview",
        "Build Loose Override Package",
        "Generate Manifest",
    )

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        primitive_box = QtWidgets.QGroupBox("Authored Room Primitive")
        primitive_layout = QtWidgets.QFormLayout(primitive_box)
        self.moduleRootLineEdit = QtWidgets.QLineEdit("grdev01")
        self.moduleRootLineEdit.setObjectName("mapStudioModuleRootLineEdit")
        self.moduleRootLineEdit.setPlaceholderText("module resref, e.g. grdev01")
        self.roomPrimitivePresetComboBox = QtWidgets.QComboBox()
        self.roomPrimitivePresetComboBox.setObjectName("mapStudioRoomPrimitivePresetComboBox")
        self.roomPrimitiveDescriptionLabel = QtWidgets.QLabel("Choose a primitive room preset to seed a new authored module.")
        self.roomPrimitiveDescriptionLabel.setObjectName("mapStudioRoomPrimitiveDescriptionLabel")
        self.roomPrimitiveDescriptionLabel.setWordWrap(True)
        self.createPrimitiveButton = QtWidgets.QPushButton("Create Authored Room Primitive")
        self.createPrimitiveButton.setObjectName("mapStudioCreatePrimitiveRoomButton")
        primitive_layout.addRow("Module:", self.moduleRootLineEdit)
        primitive_layout.addRow("Primitive:", self.roomPrimitivePresetComboBox)
        primitive_layout.addRow(self.roomPrimitiveDescriptionLabel)
        primitive_layout.addRow(self.createPrimitiveButton)
        layout.addWidget(primitive_box)
        operation_box = QtWidgets.QGroupBox("Shape Current Room")
        operation_layout = QtWidgets.QFormLayout(operation_box)
        self.roomOperationComboBox = QtWidgets.QComboBox()
        self.roomOperationComboBox.setObjectName("mapStudioRoomOperationComboBox")
        self.roomOperationComboBox.addItem("Bevel corners", "bevel")
        self.roomOperationComboBox.addItem("Inset footprint", "inset")
        self.roomOperationComboBox.addItem("Rectangular cut", "rectangular_cut")
        self.operationDistanceSpinBox = QtWidgets.QDoubleSpinBox()
        self.operationDistanceSpinBox.setObjectName("mapStudioRoomOperationDistanceSpinBox")
        self.operationDistanceSpinBox.setRange(0.05, 100.0)
        self.operationDistanceSpinBox.setSingleStep(0.05)
        self.operationDistanceSpinBox.setValue(0.25)
        self.operationDistanceSpinBox.setSuffix(" m")
        self.cutCenterXSpinBox = QtWidgets.QDoubleSpinBox()
        self.cutCenterXSpinBox.setObjectName("mapStudioRoomCutCenterXSpinBox")
        self.cutCenterYSpinBox = QtWidgets.QDoubleSpinBox()
        self.cutCenterYSpinBox.setObjectName("mapStudioRoomCutCenterYSpinBox")
        self.cutWidthSpinBox = QtWidgets.QDoubleSpinBox()
        self.cutWidthSpinBox.setObjectName("mapStudioRoomCutWidthSpinBox")
        self.cutDepthSpinBox = QtWidgets.QDoubleSpinBox()
        self.cutDepthSpinBox.setObjectName("mapStudioRoomCutDepthSpinBox")
        for spin in (self.cutCenterXSpinBox, self.cutCenterYSpinBox):
            spin.setRange(-100.0, 100.0)
            spin.setSingleStep(0.25)
            spin.setSuffix(" m")
        for spin in (self.cutWidthSpinBox, self.cutDepthSpinBox):
            spin.setRange(0.05, 100.0)
            spin.setSingleStep(0.25)
            spin.setValue(1.0)
            spin.setSuffix(" m")
        self.applyRoomOperationButton = QtWidgets.QPushButton("Apply Room Operation")
        self.applyRoomOperationButton.setObjectName("mapStudioApplyRoomOperationButton")
        operation_layout.addRow("Operation:", self.roomOperationComboBox)
        operation_layout.addRow("Distance:", self.operationDistanceSpinBox)
        operation_layout.addRow("Cut X:", self.cutCenterXSpinBox)
        operation_layout.addRow("Cut Y:", self.cutCenterYSpinBox)
        operation_layout.addRow("Cut Width:", self.cutWidthSpinBox)
        operation_layout.addRow("Cut Depth:", self.cutDepthSpinBox)
        operation_layout.addRow(self.applyRoomOperationButton)
        layout.addWidget(operation_box)
        style_box = QtWidgets.QGroupBox("Room Material + Walkmesh")
        style_layout = QtWidgets.QFormLayout(style_box)
        self.roomTextureLineEdit = QtWidgets.QLineEdit("CM_Baremetal")
        self.roomTextureLineEdit.setObjectName("mapStudioRoomTextureLineEdit")
        self.roomTextureLineEdit.setPlaceholderText("KOTOR texture resref, e.g. CM_Baremetal")
        self.roomSurfaceComboBox = QtWidgets.QComboBox()
        self.roomSurfaceComboBox.setObjectName("mapStudioRoomSurfaceComboBox")
        self.roomSurfaceHintLabel = QtWidgets.QLabel("Choose how the generated floor should behave in the KOTOR walkmesh.")
        self.roomSurfaceHintLabel.setObjectName("mapStudioRoomSurfaceHintLabel")
        self.roomSurfaceHintLabel.setWordWrap(True)
        self.applyRoomStyleButton = QtWidgets.QPushButton("Apply Room Material + Surface")
        self.applyRoomStyleButton.setObjectName("mapStudioApplyRoomStyleButton")
        style_layout.addRow("Texture:", self.roomTextureLineEdit)
        style_layout.addRow("WOK surface:", self.roomSurfaceComboBox)
        style_layout.addRow(self.roomSurfaceHintLabel)
        style_layout.addRow(self.applyRoomStyleButton)
        layout.addWidget(style_box)
        placement_box = QtWidgets.QGroupBox("Gameplay Placement")
        placement_layout = QtWidgets.QFormLayout(placement_box)
        self.gameplayPlacementKindComboBox = QtWidgets.QComboBox()
        self.gameplayPlacementKindComboBox.setObjectName("mapStudioGameplayPlacementKindComboBox")
        self.gameplayTemplateLineEdit = QtWidgets.QLineEdit("plc_bench")
        self.gameplayTemplateLineEdit.setObjectName("mapStudioGameplayTemplateLineEdit")
        self.gameplayTemplateLineEdit.setPlaceholderText("template resref, e.g. plc_bench or c_drdmkone")
        self.gameplayTagLineEdit = QtWidgets.QLineEdit("")
        self.gameplayTagLineEdit.setObjectName("mapStudioGameplayTagLineEdit")
        self.gameplayTagLineEdit.setPlaceholderText("optional in-module tag")
        self.gameplayPosXSpinBox = QtWidgets.QDoubleSpinBox()
        self.gameplayPosXSpinBox.setObjectName("mapStudioGameplayPosXSpinBox")
        self.gameplayPosYSpinBox = QtWidgets.QDoubleSpinBox()
        self.gameplayPosYSpinBox.setObjectName("mapStudioGameplayPosYSpinBox")
        self.gameplayPosZSpinBox = QtWidgets.QDoubleSpinBox()
        self.gameplayPosZSpinBox.setObjectName("mapStudioGameplayPosZSpinBox")
        for spin in (self.gameplayPosXSpinBox, self.gameplayPosYSpinBox, self.gameplayPosZSpinBox):
            spin.setRange(-1000.0, 1000.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.25)
            spin.setSuffix(" m")
        self.gameplayPosXSpinBox.setValue(1.75)
        self.gameplayPosYSpinBox.setValue(1.5)
        self.gameplayBearingSpinBox = QtWidgets.QDoubleSpinBox()
        self.gameplayBearingSpinBox.setObjectName("mapStudioGameplayBearingSpinBox")
        self.gameplayBearingSpinBox.setRange(-360.0, 360.0)
        self.gameplayBearingSpinBox.setDecimals(1)
        self.gameplayBearingSpinBox.setSingleStep(15.0)
        self.gameplayBearingSpinBox.setSuffix(" deg")
        self.addGameplayPlacementButton = QtWidgets.QPushButton("Add Gameplay Placement")
        self.addGameplayPlacementButton.setObjectName("mapStudioAddGameplayPlacementButton")
        placement_layout.addRow("Kind:", self.gameplayPlacementKindComboBox)
        placement_layout.addRow("Template:", self.gameplayTemplateLineEdit)
        placement_layout.addRow("Tag:", self.gameplayTagLineEdit)
        placement_layout.addRow("Pos X:", self.gameplayPosXSpinBox)
        placement_layout.addRow("Pos Y:", self.gameplayPosYSpinBox)
        placement_layout.addRow("Pos Z:", self.gameplayPosZSpinBox)
        placement_layout.addRow("Bearing:", self.gameplayBearingSpinBox)
        placement_layout.addRow(self.addGameplayPlacementButton)
        layout.addWidget(placement_box)
        for label in self.ACTIONS:
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self.actionRequested.emit(text))
            layout.addWidget(button)
        self.note = QtWidgets.QLabel("KOTOR archive writing is experimental; preview manifests are generated first.")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        layout.addStretch(1)
        self.roomPrimitivePresetComboBox.currentIndexChanged.connect(self._update_preset_description)
        self.createPrimitiveButton.clicked.connect(self._emit_primitive_preset)
        self.roomOperationComboBox.currentIndexChanged.connect(self._update_operation_controls)
        self.applyRoomOperationButton.clicked.connect(self._emit_room_operation)
        self.roomSurfaceComboBox.currentIndexChanged.connect(self._update_surface_hint)
        self.applyRoomStyleButton.clicked.connect(self._emit_room_style)
        self.addGameplayPlacementButton.clicked.connect(self._emit_gameplay_placement)
        self._update_operation_controls()
        self._update_surface_hint()

    def set_primitive_presets(self, presets) -> None:
        """Populate the primitive preset selector from the controller."""

        self.roomPrimitivePresetComboBox.clear()
        for preset in presets or ():
            preset_id = str(getattr(preset, "preset_id", "") or "")
            label = str(getattr(preset, "label", "") or preset_id)
            description = str(getattr(preset, "description", "") or "")
            self.roomPrimitivePresetComboBox.addItem(label, {"preset_id": preset_id, "description": description})
        self._update_preset_description()

    def _current_preset_data(self) -> dict:
        data = self.roomPrimitivePresetComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _update_preset_description(self) -> None:
        data = self._current_preset_data()
        description = data.get("description") or "Choose a primitive room preset to seed a new authored module."
        self.roomPrimitiveDescriptionLabel.setText(str(description))

    def _emit_primitive_preset(self) -> None:
        data = self._current_preset_data()
        preset_id = str(data.get("preset_id") or "").strip()
        module_root = self.moduleRootLineEdit.text().strip() or "grdev01"
        if preset_id:
            self.primitivePresetRequested.emit(preset_id, module_root)

    def set_walkmesh_surfaces(self, surfaces) -> None:
        """Populate the authored room WOK surface selector from the controller."""

        self.roomSurfaceComboBox.clear()
        for surface in surfaces or ():
            surface_id = str(getattr(surface, "surface_id", "") or "")
            name = str(getattr(surface, "name", "") or surface_id)
            authoring_name = str(getattr(surface, "authoring_name", "") or name).replace("_", " ")
            walkable = bool(getattr(surface, "walkable", False))
            description = str(getattr(surface, "description", "") or "")
            state = "walkable" if walkable else "not walkable"
            self.roomSurfaceComboBox.addItem(
                f"{surface_id} - {authoring_name.title()} ({state})",
                {
                    "surface_id": surface_id,
                    "name": name,
                    "walkable": walkable,
                    "description": description,
                },
            )
        if self.roomSurfaceComboBox.count() <= 0:
            self.roomSurfaceComboBox.addItem("4 - Stone (walkable)", {"surface_id": "4", "walkable": True, "description": "Walkable stone floor."})
        self._update_surface_hint()

    def _current_surface_data(self) -> dict:
        data = self.roomSurfaceComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _update_surface_hint(self) -> None:
        data = self._current_surface_data()
        description = data.get("description") or "Choose how the generated floor should behave in the KOTOR walkmesh."
        if data and not bool(data.get("walkable", False)):
            description = f"{description} This is not normally walkable."
        self.roomSurfaceHintLabel.setText(str(description))

    def _emit_room_style(self) -> None:
        texture = self.roomTextureLineEdit.text().strip()
        surface_id = str(self._current_surface_data().get("surface_id") or self.roomSurfaceComboBox.currentData() or "4")
        self.roomStyleRequested.emit(texture, surface_id)

    def set_gameplay_placement_kinds(self, kinds) -> None:
        """Populate the gameplay placement kind selector from the controller."""

        self.gameplayPlacementKindComboBox.clear()
        for kind in kinds or ():
            value = str(kind or "").strip()
            if value:
                self.gameplayPlacementKindComboBox.addItem(value.replace("_", " ").title(), value)
        if self.gameplayPlacementKindComboBox.count() <= 0:
            self.gameplayPlacementKindComboBox.addItem("Placeable", "placeable")

    def _emit_gameplay_placement(self) -> None:
        kind = str(self.gameplayPlacementKindComboBox.currentData() or "placeable")
        self.gameplayPlacementRequested.emit(
            kind,
            self.gameplayTemplateLineEdit.text().strip(),
            self.gameplayTagLineEdit.text().strip(),
            float(self.gameplayPosXSpinBox.value()),
            float(self.gameplayPosYSpinBox.value()),
            float(self.gameplayPosZSpinBox.value()),
            float(self.gameplayBearingSpinBox.value()),
        )

    def _update_operation_controls(self) -> None:
        operation = str(self.roomOperationComboBox.currentData() or "")
        is_cut = operation == "rectangular_cut"
        for widget in (self.cutCenterXSpinBox, self.cutCenterYSpinBox, self.cutWidthSpinBox, self.cutDepthSpinBox):
            widget.setEnabled(is_cut)
        self.operationDistanceSpinBox.setEnabled(operation in {"bevel", "inset"})

    def _emit_room_operation(self) -> None:
        operation = str(self.roomOperationComboBox.currentData() or "").strip()
        if operation:
            self.roomOperationRequested.emit(
                operation,
                float(self.operationDistanceSpinBox.value()),
                float(self.cutCenterXSpinBox.value()),
                float(self.cutCenterYSpinBox.value()),
                float(self.cutWidthSpinBox.value()),
                float(self.cutDepthSpinBox.value()),
            )
