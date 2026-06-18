"""Builder workflow tab."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class BuilderTab(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)
    primitivePresetRequested = QtCore.Signal(str, str)
    roomOperationRequested = QtCore.Signal(str, float, float, float, float, float)
    roomStyleRequested = QtCore.Signal(str, str)
    roomPrimitiveAddRequested = QtCore.Signal(str, str)
    roomPrimitiveTransformRequested = QtCore.Signal(str, str, float, float, float, float, float, float, float, float, float, float)
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
        self._gameplay_palette_entries: list[object] = []
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
        add_primitive_box = QtWidgets.QGroupBox("Add Room Primitive")
        add_primitive_layout = QtWidgets.QFormLayout(add_primitive_box)
        self.compositionPrimitiveKindComboBox = QtWidgets.QComboBox()
        self.compositionPrimitiveKindComboBox.setObjectName("mapStudioCompositionPrimitiveKindComboBox")
        self.compositionPrimitiveNameLineEdit = QtWidgets.QLineEdit()
        self.compositionPrimitiveNameLineEdit.setObjectName("mapStudioCompositionPrimitiveNameLineEdit")
        self.compositionPrimitiveNameLineEdit.setPlaceholderText("optional stable primitive name")
        self.compositionPrimitiveKindHintLabel = QtWidgets.QLabel("Add a primitive to the current composition room, then transform it below.")
        self.compositionPrimitiveKindHintLabel.setObjectName("mapStudioCompositionPrimitiveKindHintLabel")
        self.compositionPrimitiveKindHintLabel.setWordWrap(True)
        self.addCompositionPrimitiveButton = QtWidgets.QPushButton("Add Primitive to Room")
        self.addCompositionPrimitiveButton.setObjectName("mapStudioAddCompositionPrimitiveButton")
        add_primitive_layout.addRow("Kind:", self.compositionPrimitiveKindComboBox)
        add_primitive_layout.addRow("Name:", self.compositionPrimitiveNameLineEdit)
        add_primitive_layout.addRow(self.compositionPrimitiveKindHintLabel)
        add_primitive_layout.addRow(self.addCompositionPrimitiveButton)
        layout.addWidget(add_primitive_box)
        transform_box = QtWidgets.QGroupBox("Transform Room Primitive")
        transform_layout = QtWidgets.QFormLayout(transform_box)
        self.roomPrimitiveTransformComboBox = QtWidgets.QComboBox()
        self.roomPrimitiveTransformComboBox.setObjectName("mapStudioRoomPrimitiveTransformComboBox")
        self.primitiveTransformHintLabel = QtWidgets.QLabel("Create a composition room preset to edit walls, ramps, stairs, arches, cubes, and cylinders.")
        self.primitiveTransformHintLabel.setObjectName("mapStudioPrimitiveTransformHintLabel")
        self.primitiveTransformHintLabel.setWordWrap(True)
        self.primitiveTranslateXSpinBox = self._make_transform_spin("mapStudioPrimitiveTranslateXSpinBox", -1000.0, 1000.0, " m")
        self.primitiveTranslateYSpinBox = self._make_transform_spin("mapStudioPrimitiveTranslateYSpinBox", -1000.0, 1000.0, " m")
        self.primitiveTranslateZSpinBox = self._make_transform_spin("mapStudioPrimitiveTranslateZSpinBox", -1000.0, 1000.0, " m")
        self.primitiveRotateZSpinBox = self._make_transform_spin("mapStudioPrimitiveRotateZSpinBox", -360.0, 360.0, " deg", decimals=1, step=15.0)
        self.primitiveScaleXSpinBox = self._make_transform_spin("mapStudioPrimitiveScaleXSpinBox", 0.01, 100.0, "", value=1.0)
        self.primitiveScaleYSpinBox = self._make_transform_spin("mapStudioPrimitiveScaleYSpinBox", 0.01, 100.0, "", value=1.0)
        self.primitiveScaleZSpinBox = self._make_transform_spin("mapStudioPrimitiveScaleZSpinBox", 0.01, 100.0, "", value=1.0)
        self.primitivePivotXSpinBox = self._make_transform_spin("mapStudioPrimitivePivotXSpinBox", -1000.0, 1000.0, " m")
        self.primitivePivotYSpinBox = self._make_transform_spin("mapStudioPrimitivePivotYSpinBox", -1000.0, 1000.0, " m")
        self.primitivePivotZSpinBox = self._make_transform_spin("mapStudioPrimitivePivotZSpinBox", -1000.0, 1000.0, " m")
        self.applyPrimitiveTransformButton = QtWidgets.QPushButton("Apply Primitive Transform")
        self.applyPrimitiveTransformButton.setObjectName("mapStudioApplyPrimitiveTransformButton")
        transform_layout.addRow("Primitive:", self.roomPrimitiveTransformComboBox)
        transform_layout.addRow(self.primitiveTransformHintLabel)
        transform_layout.addRow("Move X:", self.primitiveTranslateXSpinBox)
        transform_layout.addRow("Move Y:", self.primitiveTranslateYSpinBox)
        transform_layout.addRow("Move Z:", self.primitiveTranslateZSpinBox)
        transform_layout.addRow("Rotate Z:", self.primitiveRotateZSpinBox)
        transform_layout.addRow("Scale X:", self.primitiveScaleXSpinBox)
        transform_layout.addRow("Scale Y:", self.primitiveScaleYSpinBox)
        transform_layout.addRow("Scale Z:", self.primitiveScaleZSpinBox)
        transform_layout.addRow("Pivot X:", self.primitivePivotXSpinBox)
        transform_layout.addRow("Pivot Y:", self.primitivePivotYSpinBox)
        transform_layout.addRow("Pivot Z:", self.primitivePivotZSpinBox)
        transform_layout.addRow(self.applyPrimitiveTransformButton)
        layout.addWidget(transform_box)
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
        self.gameplayPaletteSearchLineEdit = QtWidgets.QLineEdit()
        self.gameplayPaletteSearchLineEdit.setObjectName("mapStudioGameplayPaletteSearchLineEdit")
        self.gameplayPaletteSearchLineEdit.setPlaceholderText("Search game-library templates or models")
        self.gameplayPaletteComboBox = QtWidgets.QComboBox()
        self.gameplayPaletteComboBox.setObjectName("mapStudioGameplayPaletteComboBox")
        self.gameplayPaletteComboBox.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.useGameplayPaletteButton = QtWidgets.QPushButton("Use Selected Resource")
        self.useGameplayPaletteButton.setObjectName("mapStudioUseGameplayPaletteButton")
        self.gameplayPaletteHintLabel = QtWidgets.QLabel("Scan the Game Library to search for creature, placeable, door, and template resources.")
        self.gameplayPaletteHintLabel.setObjectName("mapStudioGameplayPaletteHintLabel")
        self.gameplayPaletteHintLabel.setWordWrap(True)
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
        placement_layout.addRow("Search:", self.gameplayPaletteSearchLineEdit)
        placement_layout.addRow("Library:", self.gameplayPaletteComboBox)
        placement_layout.addRow(self.useGameplayPaletteButton)
        placement_layout.addRow(self.gameplayPaletteHintLabel)
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
        self.compositionPrimitiveKindComboBox.currentIndexChanged.connect(self._update_composition_primitive_kind_hint)
        self.addCompositionPrimitiveButton.clicked.connect(self._emit_add_composition_primitive)
        self.roomPrimitiveTransformComboBox.currentIndexChanged.connect(self._update_primitive_transform_controls)
        self.applyPrimitiveTransformButton.clicked.connect(self._emit_primitive_transform)
        self.roomSurfaceComboBox.currentIndexChanged.connect(self._update_surface_hint)
        self.applyRoomStyleButton.clicked.connect(self._emit_room_style)
        self.gameplayPlacementKindComboBox.currentIndexChanged.connect(self._apply_gameplay_palette_filter)
        self.gameplayPaletteSearchLineEdit.textChanged.connect(self._apply_gameplay_palette_filter)
        self.gameplayPaletteComboBox.currentIndexChanged.connect(self._update_gameplay_palette_hint)
        self.useGameplayPaletteButton.clicked.connect(self._use_selected_gameplay_palette_entry)
        self.addGameplayPlacementButton.clicked.connect(self._emit_gameplay_placement)
        self._update_operation_controls()
        self._update_composition_primitive_kind_hint()
        self._update_primitive_transform_controls()
        self._update_surface_hint()

    @staticmethod
    def _make_transform_spin(
        object_name: str,
        minimum: float,
        maximum: float,
        suffix: str,
        *,
        value: float = 0.0,
        decimals: int = 3,
        step: float = 0.25,
    ) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setObjectName(object_name)
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.setValue(value)
        spin.setSuffix(suffix)
        return spin

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

    def set_composition_primitive_kinds(self, kinds) -> None:
        """Populate the add-primitive palette from the controller."""

        self.compositionPrimitiveKindComboBox.clear()
        for kind in kinds or ():
            kind_id = str(getattr(kind, "kind", "") or "")
            label = str(getattr(kind, "label", "") or kind_id)
            description = str(getattr(kind, "description", "") or "")
            creates_walkmesh = bool(getattr(kind, "creates_walkmesh", False))
            self.compositionPrimitiveKindComboBox.addItem(
                label,
                {
                    "kind": kind_id,
                    "description": description,
                    "creates_walkmesh": creates_walkmesh,
                },
            )
        if self.compositionPrimitiveKindComboBox.count() <= 0:
            self.compositionPrimitiveKindComboBox.addItem("Cube", {"kind": "cube", "description": "A simple box primitive.", "creates_walkmesh": False})
        self._update_composition_primitive_kind_hint()

    def _current_composition_primitive_kind_data(self) -> dict:
        data = self.compositionPrimitiveKindComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _update_composition_primitive_kind_hint(self) -> None:
        data = self._current_composition_primitive_kind_data()
        description = data.get("description") or "Add a primitive to the current composition room, then transform it below."
        if data.get("creates_walkmesh"):
            description = f"{description} This primitive contributes generated walkmesh faces."
        self.compositionPrimitiveKindHintLabel.setText(str(description))

    def _emit_add_composition_primitive(self) -> None:
        kind = str(self._current_composition_primitive_kind_data().get("kind") or "").strip()
        name = self.compositionPrimitiveNameLineEdit.text().strip()
        if kind:
            self.roomPrimitiveAddRequested.emit(kind, name)

    def set_room_primitives(self, primitives) -> None:
        """Populate editable primitive transform choices from the controller."""

        current_key = ""
        current = self.roomPrimitiveTransformComboBox.currentData()
        if isinstance(current, dict):
            current_key = f"{current.get('room_resref', '')}:{current.get('primitive_name', '')}"
        self.roomPrimitiveTransformComboBox.blockSignals(True)
        self.roomPrimitiveTransformComboBox.clear()
        restore_index = -1
        for primitive in primitives or ():
            room = str(getattr(primitive, "room_resref", "") or "")
            name = str(getattr(primitive, "primitive_name", "") or "")
            primitive_type = str(getattr(primitive, "primitive_type", "") or "primitive")
            key = f"{room}:{name}"
            data = {
                "room_resref": room,
                "primitive_name": name,
                "primitive_type": primitive_type,
                "translation": tuple(getattr(primitive, "translation", (0.0, 0.0, 0.0))),
                "rotation_degrees_z": float(getattr(primitive, "rotation_degrees_z", 0.0)),
                "scale": tuple(getattr(primitive, "scale", (1.0, 1.0, 1.0))),
                "pivot": tuple(getattr(primitive, "pivot", (0.0, 0.0, 0.0))),
            }
            self.roomPrimitiveTransformComboBox.addItem(f"{room} / {primitive_type} / {name}", data)
            if key == current_key:
                restore_index = self.roomPrimitiveTransformComboBox.count() - 1
        if self.roomPrimitiveTransformComboBox.count() <= 0:
            self.roomPrimitiveTransformComboBox.addItem("No editable composition primitives", None)
        if restore_index >= 0:
            self.roomPrimitiveTransformComboBox.setCurrentIndex(restore_index)
        self.roomPrimitiveTransformComboBox.blockSignals(False)
        self._update_primitive_transform_controls()

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

    def _current_primitive_transform_data(self) -> dict:
        data = self.roomPrimitiveTransformComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    @staticmethod
    def _fill_vec3(spins, values, default: tuple[float, float, float]) -> None:
        source = tuple(values or default)
        if len(source) < 3:
            source = default
        for spin, value in zip(spins, source):
            spin.blockSignals(True)
            spin.setValue(float(value))
            spin.blockSignals(False)

    def _update_primitive_transform_controls(self) -> None:
        data = self._current_primitive_transform_data()
        enabled = bool(data)
        for widget in (
            self.primitiveTranslateXSpinBox,
            self.primitiveTranslateYSpinBox,
            self.primitiveTranslateZSpinBox,
            self.primitiveRotateZSpinBox,
            self.primitiveScaleXSpinBox,
            self.primitiveScaleYSpinBox,
            self.primitiveScaleZSpinBox,
            self.primitivePivotXSpinBox,
            self.primitivePivotYSpinBox,
            self.primitivePivotZSpinBox,
            self.applyPrimitiveTransformButton,
        ):
            widget.setEnabled(enabled)
        if not enabled:
            self.primitiveTransformHintLabel.setText("Create a composition room preset to edit walls, ramps, stairs, arches, cubes, and cylinders.")
            return
        self._fill_vec3(
            (self.primitiveTranslateXSpinBox, self.primitiveTranslateYSpinBox, self.primitiveTranslateZSpinBox),
            data.get("translation"),
            (0.0, 0.0, 0.0),
        )
        self.primitiveRotateZSpinBox.blockSignals(True)
        self.primitiveRotateZSpinBox.setValue(float(data.get("rotation_degrees_z", 0.0)))
        self.primitiveRotateZSpinBox.blockSignals(False)
        self._fill_vec3(
            (self.primitiveScaleXSpinBox, self.primitiveScaleYSpinBox, self.primitiveScaleZSpinBox),
            data.get("scale"),
            (1.0, 1.0, 1.0),
        )
        self._fill_vec3(
            (self.primitivePivotXSpinBox, self.primitivePivotYSpinBox, self.primitivePivotZSpinBox),
            data.get("pivot"),
            (0.0, 0.0, 0.0),
        )
        self.primitiveTransformHintLabel.setText(
            f"Editing {data.get('primitive_type', 'primitive')} {data.get('primitive_name', '')}; mesh and WOK will be regenerated together."
        )

    def _emit_primitive_transform(self) -> None:
        data = self._current_primitive_transform_data()
        if not data:
            return
        self.roomPrimitiveTransformRequested.emit(
            str(data.get("room_resref") or ""),
            str(data.get("primitive_name") or ""),
            float(self.primitiveTranslateXSpinBox.value()),
            float(self.primitiveTranslateYSpinBox.value()),
            float(self.primitiveTranslateZSpinBox.value()),
            float(self.primitiveRotateZSpinBox.value()),
            float(self.primitiveScaleXSpinBox.value()),
            float(self.primitiveScaleYSpinBox.value()),
            float(self.primitiveScaleZSpinBox.value()),
            float(self.primitivePivotXSpinBox.value()),
            float(self.primitivePivotYSpinBox.value()),
            float(self.primitivePivotZSpinBox.value()),
        )

    def set_gameplay_placement_kinds(self, kinds) -> None:
        """Populate the gameplay placement kind selector from the controller."""

        self.gameplayPlacementKindComboBox.clear()
        for kind in kinds or ():
            value = str(kind or "").strip()
            if value:
                self.gameplayPlacementKindComboBox.addItem(value.replace("_", " ").title(), value)
        if self.gameplayPlacementKindComboBox.count() <= 0:
            self.gameplayPlacementKindComboBox.addItem("Placeable", "placeable")
        self._apply_gameplay_palette_filter()

    def set_gameplay_palette_entries(self, entries) -> None:
        """Populate searchable gameplay-placement resource choices."""

        self._gameplay_palette_entries = list(entries or ())
        self._apply_gameplay_palette_filter()

    @staticmethod
    def _entry_value(entry, key: str, default: str = "") -> str:
        if isinstance(entry, dict):
            value = entry.get(key, default)
        else:
            value = getattr(entry, key, default)
        return str(value if value is not None else default)

    def _current_palette_entry(self):
        entry = self.gameplayPaletteComboBox.currentData()
        return entry if entry not in (None, "") else None

    def _apply_gameplay_palette_filter(self) -> None:
        if not hasattr(self, "gameplayPaletteComboBox"):
            return
        kind = str(self.gameplayPlacementKindComboBox.currentData() or "").strip().lower()
        needle = self.gameplayPaletteSearchLineEdit.text().strip().lower()
        self.gameplayPaletteComboBox.blockSignals(True)
        self.gameplayPaletteComboBox.clear()
        count = 0
        for entry in self._gameplay_palette_entries:
            entry_kind = self._entry_value(entry, "kind").lower()
            haystack = " ".join(
                self._entry_value(entry, key)
                for key in ("template_resref", "label", "category", "source")
            ).lower()
            if kind and entry_kind != kind:
                continue
            if needle and needle not in haystack:
                continue
            label = self._entry_value(entry, "label") or self._entry_value(entry, "template_resref")
            self.gameplayPaletteComboBox.addItem(label, entry)
            count += 1
        if count <= 0:
            self.gameplayPaletteComboBox.addItem("No compatible game-library resources", None)
        self.gameplayPaletteComboBox.blockSignals(False)
        self._update_gameplay_palette_hint()

    def _update_gameplay_palette_hint(self) -> None:
        entry = self._current_palette_entry()
        if entry is None:
            if self._gameplay_palette_entries:
                self.gameplayPaletteHintLabel.setText("No matching resources for the current kind/search. You can still type a template resref manually.")
            else:
                self.gameplayPaletteHintLabel.setText("Scan the Game Library to search for creature, placeable, door, and template resources.")
            return
        warning = self._entry_value(entry, "warning")
        confidence = self._entry_value(entry, "confidence")
        template = self._entry_value(entry, "template_resref")
        if warning:
            self.gameplayPaletteHintLabel.setText(warning)
        else:
            self.gameplayPaletteHintLabel.setText(f"Ready to place template {template} ({confidence}).")

    def _use_selected_gameplay_palette_entry(self) -> None:
        entry = self._current_palette_entry()
        if entry is None:
            return
        kind = self._entry_value(entry, "kind")
        template = self._entry_value(entry, "template_resref")
        tag = template[:32]
        for index in range(self.gameplayPlacementKindComboBox.count()):
            if str(self.gameplayPlacementKindComboBox.itemData(index) or "") == kind:
                self.gameplayPlacementKindComboBox.setCurrentIndex(index)
                break
        self.gameplayTemplateLineEdit.setText(template)
        if not self.gameplayTagLineEdit.text().strip():
            self.gameplayTagLineEdit.setText(tag)
        self._update_gameplay_palette_hint()

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
