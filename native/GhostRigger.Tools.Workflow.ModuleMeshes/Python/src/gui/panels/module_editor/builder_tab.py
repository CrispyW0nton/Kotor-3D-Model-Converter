"""Builder workflow tab."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class BuilderTab(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)
    primitivePresetRequested = QtCore.Signal(str, str)
    roomOperationRequested = QtCore.Signal(str, float, float, float, float, float)
    terrainOperationRequested = QtCore.Signal(str, str, int, int, float, float, int, int, float)
    roomRectangularUnionRequested = QtCore.Signal(str, str, str)
    roomStyleRequested = QtCore.Signal(str, str)
    roomPrimitiveAddRequested = QtCore.Signal(str, str)
    roomPrimitiveTransformRequested = QtCore.Signal(str, str, float, float, float, float, float, float, float, float, float, float)
    roomPrimitiveDimensionsRequested = QtCore.Signal(str, str, object)
    roomPrimitiveStyleRequested = QtCore.Signal(str, str, str, str)
    roomPrimitiveRemoveRequested = QtCore.Signal(str, str)
    gameplayPlacementRequested = QtCore.Signal(str, str, str, float, float, float, float)
    gameplayPlacementStatusChanged = QtCore.Signal(str)
    roomLightRequested = QtCore.Signal(str, str, float, float, float, float, float, float, float, float, str)
    scriptHookRequested = QtCore.Signal(str, str, str)

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
        terrain_box = QtWidgets.QGroupBox("Terrain Heightfield")
        terrain_layout = QtWidgets.QFormLayout(terrain_box)
        self.terrainRoomComboBox = QtWidgets.QComboBox()
        self.terrainRoomComboBox.setObjectName("mapStudioTerrainRoomComboBox")
        self.terrainShapePresetComboBox = QtWidgets.QComboBox()
        self.terrainShapePresetComboBox.setObjectName("mapStudioTerrainShapePresetComboBox")
        self.terrainShapeHeightSpinBox = self._make_transform_spin("mapStudioTerrainShapeHeightSpinBox", -1000.0, 1000.0, " m", value=0.5, step=0.05)
        self.terrainRowSpinBox = QtWidgets.QSpinBox()
        self.terrainRowSpinBox.setObjectName("mapStudioTerrainRowSpinBox")
        self.terrainColumnSpinBox = QtWidgets.QSpinBox()
        self.terrainColumnSpinBox.setObjectName("mapStudioTerrainColumnSpinBox")
        self.terrainHeightSpinBox = self._make_transform_spin("mapStudioTerrainHeightSpinBox", -1000.0, 1000.0, " m", step=0.05)
        self.terrainDeltaSpinBox = self._make_transform_spin("mapStudioTerrainDeltaSpinBox", 0.01, 100.0, " m", value=0.1, step=0.05)
        self.terrainRadiusSpinBox = QtWidgets.QSpinBox()
        self.terrainRadiusSpinBox.setObjectName("mapStudioTerrainRadiusSpinBox")
        self.terrainRadiusSpinBox.setRange(0, 64)
        self.terrainSmoothIterationsSpinBox = QtWidgets.QSpinBox()
        self.terrainSmoothIterationsSpinBox.setObjectName("mapStudioTerrainSmoothIterationsSpinBox")
        self.terrainSmoothIterationsSpinBox.setRange(1, 32)
        self.terrainSmoothIterationsSpinBox.setValue(1)
        self.terrainSmoothStrengthSpinBox = self._make_transform_spin("mapStudioTerrainSmoothStrengthSpinBox", 0.0, 1.0, "", value=0.5, step=0.1)
        self.terrainHintLabel = QtWidgets.QLabel("Create a terrain heightfield preset to sculpt terrain samples.")
        self.terrainHintLabel.setObjectName("mapStudioTerrainHintLabel")
        self.terrainHintLabel.setWordWrap(True)
        self.setTerrainHeightButton = QtWidgets.QPushButton("Set Sample Height")
        self.setTerrainHeightButton.setObjectName("mapStudioSetTerrainHeightButton")
        self.raiseTerrainButton = QtWidgets.QPushButton("Raise Sample")
        self.raiseTerrainButton.setObjectName("mapStudioRaiseTerrainButton")
        self.lowerTerrainButton = QtWidgets.QPushButton("Lower Sample")
        self.lowerTerrainButton.setObjectName("mapStudioLowerTerrainButton")
        self.smoothTerrainButton = QtWidgets.QPushButton("Smooth Terrain")
        self.smoothTerrainButton.setObjectName("mapStudioSmoothTerrainButton")
        self.flattenTerrainButton = QtWidgets.QPushButton("Flatten Terrain")
        self.flattenTerrainButton.setObjectName("mapStudioFlattenTerrainButton")
        self.applyTerrainShapeButton = QtWidgets.QPushButton("Apply Terrain Shape")
        self.applyTerrainShapeButton.setObjectName("mapStudioApplyTerrainShapePresetButton")
        terrain_layout.addRow("Terrain:", self.terrainRoomComboBox)
        terrain_layout.addRow("Shape:", self.terrainShapePresetComboBox)
        terrain_layout.addRow("Shape height:", self.terrainShapeHeightSpinBox)
        terrain_layout.addRow("Row:", self.terrainRowSpinBox)
        terrain_layout.addRow("Column:", self.terrainColumnSpinBox)
        terrain_layout.addRow("Height:", self.terrainHeightSpinBox)
        terrain_layout.addRow("Delta:", self.terrainDeltaSpinBox)
        terrain_layout.addRow("Radius:", self.terrainRadiusSpinBox)
        terrain_layout.addRow("Smooth passes:", self.terrainSmoothIterationsSpinBox)
        terrain_layout.addRow("Smooth strength:", self.terrainSmoothStrengthSpinBox)
        terrain_layout.addRow(self.terrainHintLabel)
        terrain_layout.addRow(self.setTerrainHeightButton)
        terrain_layout.addRow(self.raiseTerrainButton)
        terrain_layout.addRow(self.lowerTerrainButton)
        terrain_layout.addRow(self.smoothTerrainButton)
        terrain_layout.addRow(self.flattenTerrainButton)
        terrain_layout.addRow(self.applyTerrainShapeButton)
        layout.addWidget(terrain_box)
        union_box = QtWidgets.QGroupBox("Boolean Union Rooms")
        union_layout = QtWidgets.QFormLayout(union_box)
        self.floorPlanUnionFirstRoomComboBox = QtWidgets.QComboBox()
        self.floorPlanUnionFirstRoomComboBox.setObjectName("floorPlanUnionFirstRoomComboBox")
        self.floorPlanUnionSecondRoomComboBox = QtWidgets.QComboBox()
        self.floorPlanUnionSecondRoomComboBox.setObjectName("floorPlanUnionSecondRoomComboBox")
        self.floorPlanUnionResultRoomLineEdit = QtWidgets.QLineEdit()
        self.floorPlanUnionResultRoomLineEdit.setObjectName("floorPlanUnionResultRoomLineEdit")
        self.floorPlanUnionResultRoomLineEdit.setPlaceholderText("optional result room resref")
        self.mapStudioRectangularUnionHintLabel = QtWidgets.QLabel(
            "Union two compatible rectangular floor-plan rooms into one exportable room."
        )
        self.mapStudioRectangularUnionHintLabel.setObjectName("mapStudioRectangularUnionHintLabel")
        self.mapStudioRectangularUnionHintLabel.setWordWrap(True)
        self.mapStudioApplyRectangularUnionButton = QtWidgets.QPushButton("Union Rectangular Rooms")
        self.mapStudioApplyRectangularUnionButton.setObjectName("mapStudioApplyRectangularUnionButton")
        union_layout.addRow("First room:", self.floorPlanUnionFirstRoomComboBox)
        union_layout.addRow("Second room:", self.floorPlanUnionSecondRoomComboBox)
        union_layout.addRow("Result:", self.floorPlanUnionResultRoomLineEdit)
        union_layout.addRow(self.mapStudioRectangularUnionHintLabel)
        union_layout.addRow(self.mapStudioApplyRectangularUnionButton)
        layout.addWidget(union_box)
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
        self.removePrimitiveButton = QtWidgets.QPushButton("Remove Selected Primitive")
        self.removePrimitiveButton.setObjectName("mapStudioRemoveCompositionPrimitiveButton")
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
        transform_layout.addRow(self.removePrimitiveButton)
        layout.addWidget(transform_box)
        dimensions_box = QtWidgets.QGroupBox("Primitive Dimensions")
        dimensions_layout = QtWidgets.QFormLayout(dimensions_box)
        self.primitiveDimensionHintLabel = QtWidgets.QLabel("Select an authored primitive to edit its dimensions.")
        self.primitiveDimensionHintLabel.setObjectName("mapStudioPrimitiveDimensionHintLabel")
        self.primitiveDimensionHintLabel.setWordWrap(True)
        dimensions_layout.addRow(self.primitiveDimensionHintLabel)
        self._primitive_dimension_controls: list[tuple[QtWidgets.QLabel, QtWidgets.QDoubleSpinBox]] = []
        for index in range(5):
            label = QtWidgets.QLabel(f"Dimension {index + 1}:")
            label.setObjectName(f"mapStudioPrimitiveDimension{index + 1}Label")
            spin = self._make_transform_spin(
                f"mapStudioPrimitiveDimension{index + 1}SpinBox",
                0.001,
                1000.0,
                " m",
                value=0.0,
                step=0.1,
            )
            self._primitive_dimension_controls.append((label, spin))
            dimensions_layout.addRow(label, spin)
        self.applyPrimitiveDimensionsButton = QtWidgets.QPushButton("Apply Primitive Dimensions")
        self.applyPrimitiveDimensionsButton.setObjectName("mapStudioApplyPrimitiveDimensionsButton")
        dimensions_layout.addRow(self.applyPrimitiveDimensionsButton)
        layout.addWidget(dimensions_box)
        primitive_style_box = QtWidgets.QGroupBox("Primitive Material + Walkmesh")
        primitive_style_layout = QtWidgets.QFormLayout(primitive_style_box)
        self.primitiveTextureLineEdit = QtWidgets.QLineEdit()
        self.primitiveTextureLineEdit.setObjectName("mapStudioPrimitiveTextureLineEdit")
        self.primitiveTextureLineEdit.setPlaceholderText("KOTOR texture resref for selected primitive")
        self.primitiveSurfaceComboBox = QtWidgets.QComboBox()
        self.primitiveSurfaceComboBox.setObjectName("mapStudioPrimitiveSurfaceComboBox")
        self.primitiveSurfaceHintLabel = QtWidgets.QLabel("Select a primitive that contributes WOK faces to edit its walkmesh surface.")
        self.primitiveSurfaceHintLabel.setObjectName("mapStudioPrimitiveSurfaceHintLabel")
        self.primitiveSurfaceHintLabel.setWordWrap(True)
        self.applyPrimitiveStyleButton = QtWidgets.QPushButton("Apply Primitive Material + Surface")
        self.applyPrimitiveStyleButton.setObjectName("mapStudioApplyPrimitiveStyleButton")
        primitive_style_layout.addRow("Texture:", self.primitiveTextureLineEdit)
        primitive_style_layout.addRow("WOK surface:", self.primitiveSurfaceComboBox)
        primitive_style_layout.addRow(self.primitiveSurfaceHintLabel)
        primitive_style_layout.addRow(self.applyPrimitiveStyleButton)
        layout.addWidget(primitive_style_box)
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
        light_box = QtWidgets.QGroupBox("Room Lighting")
        light_layout = QtWidgets.QFormLayout(light_box)
        self.roomLightRoomLineEdit = QtWidgets.QLineEdit()
        self.roomLightRoomLineEdit.setObjectName("mapStudioRoomLightRoomLineEdit")
        self.roomLightRoomLineEdit.setPlaceholderText("optional room resref; blank uses first room")
        self.roomLightNameLineEdit = QtWidgets.QLineEdit("key_light")
        self.roomLightNameLineEdit.setObjectName("mapStudioRoomLightNameLineEdit")
        self.roomLightTypeComboBox = QtWidgets.QComboBox()
        self.roomLightTypeComboBox.setObjectName("mapStudioRoomLightTypeComboBox")
        self.roomLightTypeComboBox.addItem("Point", "point")
        self.roomLightTypeComboBox.addItem("Spot", "spot")
        self.roomLightTypeComboBox.addItem("Ambient", "ambient")
        self.roomLightPosXSpinBox = self._make_transform_spin("mapStudioRoomLightPosXSpinBox", -1000.0, 1000.0, " m", value=0.0)
        self.roomLightPosYSpinBox = self._make_transform_spin("mapStudioRoomLightPosYSpinBox", -1000.0, 1000.0, " m", value=0.0)
        self.roomLightPosZSpinBox = self._make_transform_spin("mapStudioRoomLightPosZSpinBox", -1000.0, 1000.0, " m", value=2.25)
        self.roomLightColorRSpinBox = self._make_transform_spin("mapStudioRoomLightColorRSpinBox", 0.0, 1.0, "", value=1.0, step=0.05)
        self.roomLightColorGSpinBox = self._make_transform_spin("mapStudioRoomLightColorGSpinBox", 0.0, 1.0, "", value=0.92, step=0.05)
        self.roomLightColorBSpinBox = self._make_transform_spin("mapStudioRoomLightColorBSpinBox", 0.0, 1.0, "", value=0.78, step=0.05)
        self.roomLightRadiusSpinBox = self._make_transform_spin("mapStudioRoomLightRadiusSpinBox", 0.1, 1000.0, " m", value=8.0)
        self.roomLightIntensitySpinBox = self._make_transform_spin("mapStudioRoomLightIntensitySpinBox", 0.0, 1000.0, "", value=1.0, step=0.1)
        self.addRoomLightButton = QtWidgets.QPushButton("Add Room Light")
        self.addRoomLightButton.setObjectName("mapStudioAddRoomLightButton")
        light_layout.addRow("Room:", self.roomLightRoomLineEdit)
        light_layout.addRow("Name:", self.roomLightNameLineEdit)
        light_layout.addRow("Type:", self.roomLightTypeComboBox)
        light_layout.addRow("Pos X:", self.roomLightPosXSpinBox)
        light_layout.addRow("Pos Y:", self.roomLightPosYSpinBox)
        light_layout.addRow("Pos Z:", self.roomLightPosZSpinBox)
        light_layout.addRow("Color R:", self.roomLightColorRSpinBox)
        light_layout.addRow("Color G:", self.roomLightColorGSpinBox)
        light_layout.addRow("Color B:", self.roomLightColorBSpinBox)
        light_layout.addRow("Radius:", self.roomLightRadiusSpinBox)
        light_layout.addRow("Intensity:", self.roomLightIntensitySpinBox)
        light_layout.addRow(self.addRoomLightButton)
        layout.addWidget(light_box)
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
        self.gameplaySpatialHintLabel = QtWidgets.QLabel("Spatial resources are placed in the viewport and can be moved after creation.")
        self.gameplaySpatialHintLabel.setObjectName("mapStudioGameplaySpatialHintLabel")
        self.gameplaySpatialHintLabel.setWordWrap(True)
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
        placement_layout.addRow(self.gameplaySpatialHintLabel)
        placement_layout.addRow("Pos X:", self.gameplayPosXSpinBox)
        placement_layout.addRow("Pos Y:", self.gameplayPosYSpinBox)
        placement_layout.addRow("Pos Z:", self.gameplayPosZSpinBox)
        placement_layout.addRow("Bearing:", self.gameplayBearingSpinBox)
        placement_layout.addRow(self.addGameplayPlacementButton)
        layout.addWidget(placement_box)
        script_box = QtWidgets.QGroupBox("Script Hooks")
        script_layout = QtWidgets.QFormLayout(script_box)
        self._script_hook_fields: dict[str, tuple[str, ...]] = {"area": (), "module": ()}
        self._script_hooks: dict[str, dict[str, str]] = {"area": {}, "module": {}}
        self.scriptHookScopeComboBox = QtWidgets.QComboBox()
        self.scriptHookScopeComboBox.setObjectName("mapStudioScriptHookScopeComboBox")
        self.scriptHookScopeComboBox.addItem("Area / ARE", "area")
        self.scriptHookScopeComboBox.addItem("Module / IFO", "module")
        self.scriptHookFieldComboBox = QtWidgets.QComboBox()
        self.scriptHookFieldComboBox.setObjectName("mapStudioScriptHookFieldComboBox")
        self.scriptHookResrefLineEdit = QtWidgets.QLineEdit()
        self.scriptHookResrefLineEdit.setObjectName("mapStudioScriptHookResrefLineEdit")
        self.scriptHookResrefLineEdit.setPlaceholderText("script resref, e.g. gr_onenter")
        self.scriptHookHintLabel = QtWidgets.QLabel(
            "Assign optional KOTOR script hooks. Referenced .ncs files must resolve from the module package, Override, or base game."
        )
        self.scriptHookHintLabel.setObjectName("mapStudioScriptHookHintLabel")
        self.scriptHookHintLabel.setWordWrap(True)
        self.assignScriptHookButton = QtWidgets.QPushButton("Assign Script Hook")
        self.assignScriptHookButton.setObjectName("mapStudioAssignScriptHookButton")
        self.clearScriptHookButton = QtWidgets.QPushButton("Clear Script Hook")
        self.clearScriptHookButton.setObjectName("mapStudioClearScriptHookButton")
        script_layout.addRow("Scope:", self.scriptHookScopeComboBox)
        script_layout.addRow("Field:", self.scriptHookFieldComboBox)
        script_layout.addRow("Script:", self.scriptHookResrefLineEdit)
        script_layout.addRow(self.scriptHookHintLabel)
        script_layout.addRow(self.assignScriptHookButton)
        script_layout.addRow(self.clearScriptHookButton)
        layout.addWidget(script_box)
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
        self.terrainRoomComboBox.currentIndexChanged.connect(self._update_terrain_controls)
        self.terrainShapePresetComboBox.currentIndexChanged.connect(self._update_terrain_shape_controls)
        self.setTerrainHeightButton.clicked.connect(lambda: self._emit_terrain_operation("set_height"))
        self.raiseTerrainButton.clicked.connect(lambda: self._emit_terrain_operation("raise"))
        self.lowerTerrainButton.clicked.connect(lambda: self._emit_terrain_operation("lower"))
        self.smoothTerrainButton.clicked.connect(lambda: self._emit_terrain_operation("smooth"))
        self.flattenTerrainButton.clicked.connect(lambda: self._emit_terrain_operation("flatten"))
        self.applyTerrainShapeButton.clicked.connect(self._emit_terrain_shape_preset)
        self.floorPlanUnionFirstRoomComboBox.currentIndexChanged.connect(self._update_rectangular_union_controls)
        self.floorPlanUnionSecondRoomComboBox.currentIndexChanged.connect(self._update_rectangular_union_controls)
        self.mapStudioApplyRectangularUnionButton.clicked.connect(self._emit_rectangular_union)
        self.compositionPrimitiveKindComboBox.currentIndexChanged.connect(self._update_composition_primitive_kind_hint)
        self.addCompositionPrimitiveButton.clicked.connect(self._emit_add_composition_primitive)
        self.roomPrimitiveTransformComboBox.currentIndexChanged.connect(self._update_primitive_transform_controls)
        self.applyPrimitiveTransformButton.clicked.connect(self._emit_primitive_transform)
        self.applyPrimitiveDimensionsButton.clicked.connect(self._emit_primitive_dimensions)
        self.primitiveSurfaceComboBox.currentIndexChanged.connect(self._update_primitive_surface_hint)
        self.applyPrimitiveStyleButton.clicked.connect(self._emit_primitive_style)
        self.removePrimitiveButton.clicked.connect(self._emit_remove_composition_primitive)
        self.roomSurfaceComboBox.currentIndexChanged.connect(self._update_surface_hint)
        self.applyRoomStyleButton.clicked.connect(self._emit_room_style)
        self.addRoomLightButton.clicked.connect(self._emit_room_light)
        self.gameplayPlacementKindComboBox.currentIndexChanged.connect(self._apply_gameplay_palette_filter)
        self.gameplayPlacementKindComboBox.currentIndexChanged.connect(self._update_gameplay_spatial_controls)
        self.gameplayPlacementKindComboBox.currentIndexChanged.connect(self._emit_gameplay_placement_status)
        self.gameplayPaletteSearchLineEdit.textChanged.connect(self._apply_gameplay_palette_filter)
        self.gameplayTemplateLineEdit.textChanged.connect(self._emit_gameplay_placement_status)
        self.gameplayTagLineEdit.textChanged.connect(self._emit_gameplay_placement_status)
        self.gameplayPaletteComboBox.currentIndexChanged.connect(self._update_gameplay_palette_hint)
        self.useGameplayPaletteButton.clicked.connect(self._use_selected_gameplay_palette_entry)
        self.addGameplayPlacementButton.clicked.connect(self._emit_gameplay_placement)
        self.scriptHookScopeComboBox.currentIndexChanged.connect(self._update_script_hook_field_choices)
        self.scriptHookFieldComboBox.currentIndexChanged.connect(self._update_script_hook_value)
        self.assignScriptHookButton.clicked.connect(self._emit_assign_script_hook)
        self.clearScriptHookButton.clicked.connect(self._emit_clear_script_hook)
        self._update_operation_controls()
        self.set_terrain_room_choices(())
        self.set_terrain_shape_presets(())
        self.set_floor_plan_room_choices(())
        self._update_composition_primitive_kind_hint()
        self._update_primitive_transform_controls()
        self._update_primitive_dimension_controls()
        self._update_primitive_style_controls()
        self._update_surface_hint()
        self._update_script_hook_field_choices()
        self._update_gameplay_spatial_controls()

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

    def set_terrain_room_choices(self, rooms) -> None:
        """Populate terrain heightfield choices for Builder sculpt operations."""

        current = self._current_terrain_room_resref()
        self.terrainRoomComboBox.blockSignals(True)
        self.terrainRoomComboBox.clear()
        restore_index = -1
        for choice in tuple(rooms or ()):
            resref = str(getattr(choice, "room_resref", "") or "")
            label = str(getattr(choice, "label", "") or resref)
            data = {
                "room_resref": resref,
                "row_count": int(getattr(choice, "row_count", 0) or 0),
                "column_count": int(getattr(choice, "column_count", 0) or 0),
                "min_height": float(getattr(choice, "min_height", 0.0) or 0.0),
                "max_height": float(getattr(choice, "max_height", 0.0) or 0.0),
                "max_slope_degrees": float(getattr(choice, "max_slope_degrees", 0.0) or 0.0),
                "walkable_triangle_count": int(getattr(choice, "walkable_triangle_count", 0) or 0),
                "non_walk_triangle_count": int(getattr(choice, "non_walk_triangle_count", 0) or 0),
                "warnings": tuple(getattr(choice, "warnings", ()) or ()),
                "room_index": int(getattr(choice, "room_index", 0) or 0),
            }
            self.terrainRoomComboBox.addItem(label, data)
            if resref == current:
                restore_index = self.terrainRoomComboBox.count() - 1
        if self.terrainRoomComboBox.count() <= 0:
            self.terrainRoomComboBox.addItem("No terrain heightfield rooms", None)
        elif restore_index >= 0:
            self.terrainRoomComboBox.setCurrentIndex(restore_index)
        self.terrainRoomComboBox.blockSignals(False)
        self._update_terrain_controls()

    def set_terrain_shape_presets(self, presets) -> None:
        """Populate named terrain shape presets for non-technical terrain authoring."""

        self.terrainShapePresetComboBox.blockSignals(True)
        self.terrainShapePresetComboBox.clear()
        for preset in tuple(presets or ()):
            preset_id = str(getattr(preset, "preset_id", "") or "")
            label = str(getattr(preset, "label", "") or preset_id)
            description = str(getattr(preset, "description", "") or "")
            default_height = float(getattr(preset, "default_height", 0.0) or 0.0)
            self.terrainShapePresetComboBox.addItem(
                label,
                {
                    "preset_id": preset_id,
                    "description": description,
                    "default_height": default_height,
                },
            )
        if self.terrainShapePresetComboBox.count() <= 0:
            self.terrainShapePresetComboBox.addItem("No terrain shapes", None)
        self.terrainShapePresetComboBox.blockSignals(False)
        self._update_terrain_shape_controls()

    def _current_terrain_data(self) -> dict:
        data = self.terrainRoomComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _current_terrain_shape_data(self) -> dict:
        data = self.terrainShapePresetComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _current_terrain_room_resref(self) -> str:
        return str(self._current_terrain_data().get("room_resref") or "").strip()

    def _update_terrain_shape_controls(self) -> None:
        data = self._current_terrain_shape_data()
        if not data:
            return
        self.terrainShapeHeightSpinBox.setValue(float(data.get("default_height", 0.0) or 0.0))
        description = str(data.get("description") or "").strip()
        if description and self._current_terrain_data():
            self.terrainHintLabel.setText(description)

    def _update_terrain_controls(self) -> None:
        data = self._current_terrain_data()
        enabled = bool(data)
        row_count = max(0, int(data.get("row_count", 0) or 0))
        column_count = max(0, int(data.get("column_count", 0) or 0))
        self.terrainRowSpinBox.setRange(0, max(0, row_count - 1))
        self.terrainColumnSpinBox.setRange(0, max(0, column_count - 1))
        for widget in (
            self.terrainRoomComboBox,
            self.terrainShapePresetComboBox,
            self.terrainShapeHeightSpinBox,
            self.terrainRowSpinBox,
            self.terrainColumnSpinBox,
            self.terrainHeightSpinBox,
            self.terrainDeltaSpinBox,
            self.terrainRadiusSpinBox,
            self.terrainSmoothIterationsSpinBox,
            self.terrainSmoothStrengthSpinBox,
            self.setTerrainHeightButton,
            self.raiseTerrainButton,
            self.lowerTerrainButton,
            self.smoothTerrainButton,
            self.flattenTerrainButton,
            self.applyTerrainShapeButton,
        ):
            widget.setEnabled(enabled)
        if not enabled:
            self.terrainHintLabel.setText("Create a terrain heightfield preset to sculpt terrain samples.")
            return
        blocked = int(data.get("non_walk_triangle_count", 0) or 0)
        warnings = tuple(data.get("warnings", ()) or ())
        hint = (
            f"Editing {data.get('room_resref')}: {row_count}x{column_count} samples, "
            f"height {data.get('min_height', 0.0):.2f}..{data.get('max_height', 0.0):.2f} m. "
            f"WOK: {int(data.get('walkable_triangle_count', 0) or 0)} walkable / {blocked} blocked, "
            f"max slope {float(data.get('max_slope_degrees', 0.0) or 0.0):.1f} deg."
        )
        if blocked:
            hint += " Blocked triangles export as NON_WALK; smooth or flatten slopes before game proof."
        if warnings:
            hint += f" Warning: {warnings[0]}"
        self.terrainHintLabel.setText(hint)

    def _emit_terrain_shape_preset(self) -> None:
        shape = self._current_terrain_shape_data()
        preset_id = str(shape.get("preset_id") or "").strip()
        room = self._current_terrain_room_resref()
        if not room or not preset_id:
            return
        self.terrainOperationRequested.emit(
            f"shape_preset:{preset_id}",
            room,
            int(self.terrainRowSpinBox.value()),
            int(self.terrainColumnSpinBox.value()),
            float(self.terrainShapeHeightSpinBox.value()),
            float(self.terrainDeltaSpinBox.value()),
            int(self.terrainRadiusSpinBox.value()),
            int(self.terrainSmoothIterationsSpinBox.value()),
            float(self.terrainSmoothStrengthSpinBox.value()),
        )

    def _emit_terrain_operation(self, operation: str) -> None:
        room = self._current_terrain_room_resref()
        if not room:
            return
        self.terrainOperationRequested.emit(
            operation,
            room,
            int(self.terrainRowSpinBox.value()),
            int(self.terrainColumnSpinBox.value()),
            float(self.terrainHeightSpinBox.value()),
            float(self.terrainDeltaSpinBox.value()),
            int(self.terrainRadiusSpinBox.value()),
            int(self.terrainSmoothIterationsSpinBox.value()),
            float(self.terrainSmoothStrengthSpinBox.value()),
        )

    @staticmethod
    def _current_combo_resref(combo: QtWidgets.QComboBox) -> str:
        data = combo.currentData()
        if isinstance(data, dict):
            return str(data.get("room_resref") or "").strip()
        return ""

    def set_floor_plan_room_choices(self, rooms) -> None:
        """Populate floor-plan room choices for Builder boolean operations."""

        first_current = self._current_combo_resref(self.floorPlanUnionFirstRoomComboBox)
        second_current = self._current_combo_resref(self.floorPlanUnionSecondRoomComboBox)
        choices = tuple(rooms or ())
        for combo, current in (
            (self.floorPlanUnionFirstRoomComboBox, first_current),
            (self.floorPlanUnionSecondRoomComboBox, second_current),
        ):
            combo.blockSignals(True)
            combo.clear()
            restore_index = -1
            for choice in choices:
                resref = str(getattr(choice, "room_resref", "") or "")
                label = str(getattr(choice, "label", "") or resref)
                data = {
                    "room_resref": resref,
                    "point_count": int(getattr(choice, "point_count", 0) or 0),
                    "room_index": int(getattr(choice, "room_index", 0) or 0),
                }
                combo.addItem(label, data)
                if resref == current:
                    restore_index = combo.count() - 1
            if combo.count() <= 0:
                combo.addItem("No compatible floor-plan rooms", None)
            elif restore_index >= 0:
                combo.setCurrentIndex(restore_index)
            combo.blockSignals(False)
        if self.floorPlanUnionSecondRoomComboBox.count() > 1 and self.floorPlanUnionSecondRoomComboBox.currentIndex() == self.floorPlanUnionFirstRoomComboBox.currentIndex():
            self.floorPlanUnionSecondRoomComboBox.setCurrentIndex(1)
        self._update_rectangular_union_controls()

    def _update_rectangular_union_controls(self) -> None:
        first = self._current_combo_resref(self.floorPlanUnionFirstRoomComboBox)
        second = self._current_combo_resref(self.floorPlanUnionSecondRoomComboBox)
        ready = bool(first and second and first != second)
        count = max(self.floorPlanUnionFirstRoomComboBox.count(), self.floorPlanUnionSecondRoomComboBox.count())
        self.floorPlanUnionFirstRoomComboBox.setEnabled(count >= 2)
        self.floorPlanUnionSecondRoomComboBox.setEnabled(count >= 2)
        self.floorPlanUnionResultRoomLineEdit.setEnabled(ready)
        self.mapStudioApplyRectangularUnionButton.setEnabled(ready)
        if count < 2:
            self.mapStudioRectangularUnionHintLabel.setText(
                "Create or split at least two compatible floor-plan rooms before using room union."
            )
        elif not ready:
            self.mapStudioRectangularUnionHintLabel.setText(
                "Choose two different compatible rooms. They must share position, material, wall height, and elevation, and form one rectangle."
            )
        else:
            self.mapStudioRectangularUnionHintLabel.setText(
                "Ready to merge these rooms into one generated MDL/WOK room. Previous export and game-proof status will become stale."
            )

    def _emit_rectangular_union(self) -> None:
        first = self._current_combo_resref(self.floorPlanUnionFirstRoomComboBox)
        second = self._current_combo_resref(self.floorPlanUnionSecondRoomComboBox)
        if not first or not second or first == second:
            return
        self.roomRectangularUnionRequested.emit(first, second, self.floorPlanUnionResultRoomLineEdit.text().strip())

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
                "texture": str(getattr(primitive, "texture", "") or ""),
                "surface_id": "" if getattr(primitive, "surface_id", None) is None else str(getattr(primitive, "surface_id")),
                "surface_name": str(getattr(primitive, "surface_name", "") or ""),
                "supports_walkmesh_surface": bool(getattr(primitive, "supports_walkmesh_surface", False)),
                "dimensions": tuple(
                    {
                        "key": str(getattr(dimension, "key", "") or ""),
                        "label": str(getattr(dimension, "label", "") or ""),
                        "value": float(getattr(dimension, "value", 0.0)),
                        "minimum": float(getattr(dimension, "minimum", 0.001)),
                        "maximum": float(getattr(dimension, "maximum", 1000.0)),
                        "step": float(getattr(dimension, "step", 0.1)),
                        "suffix": str(getattr(dimension, "suffix", " m") or ""),
                        "integer": bool(getattr(dimension, "integer", False)),
                    }
                    for dimension in getattr(primitive, "dimensions", ()) or ()
                ),
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

    def select_room_primitive(self, room_resref: str, primitive_name: str) -> bool:
        """Select an authored composition primitive in the editor controls."""

        wanted = f"{str(room_resref or '').strip()}:{str(primitive_name or '').strip()}"
        if wanted == ":":
            return False
        for index in range(self.roomPrimitiveTransformComboBox.count()):
            data = self.roomPrimitiveTransformComboBox.itemData(index)
            if not isinstance(data, dict):
                continue
            key = f"{data.get('room_resref', '')}:{data.get('primitive_name', '')}"
            if key == wanted:
                self.roomPrimitiveTransformComboBox.setCurrentIndex(index)
                self._update_primitive_transform_controls()
                return True
        return False

    def set_walkmesh_surfaces(self, surfaces) -> None:
        """Populate the authored room WOK surface selector from the controller."""

        self._authored_walkmesh_surfaces = tuple(surfaces or ())
        self._fill_surface_combo(self.roomSurfaceComboBox, self._authored_walkmesh_surfaces)
        self._fill_surface_combo(self.primitiveSurfaceComboBox, self._authored_walkmesh_surfaces)
        self._update_surface_hint()
        self._update_primitive_style_controls()

    def _fill_surface_combo(self, combo: QtWidgets.QComboBox, surfaces) -> None:
        combo.clear()
        for surface in surfaces or ():
            surface_id = str(getattr(surface, "surface_id", "") or "")
            name = str(getattr(surface, "name", "") or surface_id)
            authoring_name = str(getattr(surface, "authoring_name", "") or name).replace("_", " ")
            walkable = bool(getattr(surface, "walkable", False))
            description = str(getattr(surface, "description", "") or "")
            state = "walkable" if walkable else "not walkable"
            combo.addItem(
                f"{surface_id} - {authoring_name.title()} ({state})",
                {
                    "surface_id": surface_id,
                    "name": name,
                    "walkable": walkable,
                    "description": description,
                },
            )
        if combo.count() <= 0:
            combo.addItem("4 - Stone (walkable)", {"surface_id": "4", "walkable": True, "description": "Walkable stone floor."})

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

    def _current_primitive_surface_data(self) -> dict:
        data = self.primitiveSurfaceComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _select_surface_combo_value(self, combo: QtWidgets.QComboBox, surface_id: str) -> None:
        wanted = str(surface_id or "").strip()
        if not wanted:
            return
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and str(data.get("surface_id") or "") == wanted:
                combo.blockSignals(True)
                combo.setCurrentIndex(index)
                combo.blockSignals(False)
                return

    def _update_primitive_surface_hint(self) -> None:
        data = self._current_primitive_transform_data()
        if not data:
            self.primitiveSurfaceHintLabel.setText("Select a primitive to edit its material.")
            return
        if not bool(data.get("supports_walkmesh_surface", False)):
            self.primitiveSurfaceHintLabel.setText("This primitive is visual-only; texture changes are allowed, but it does not create WOK faces.")
            return
        surface = self._current_primitive_surface_data()
        description = surface.get("description") or "Choose how this primitive's generated WOK faces should behave in-game."
        if surface and not bool(surface.get("walkable", False)):
            description = f"{description} This is not normally walkable."
        self.primitiveSurfaceHintLabel.setText(str(description))

    def _update_primitive_style_controls(self, data: dict | None = None) -> None:
        current = self._current_primitive_transform_data() if data is None else data
        enabled = bool(current)
        supports_surface = bool(current and current.get("supports_walkmesh_surface", False))
        for widget in (self.primitiveTextureLineEdit, self.applyPrimitiveStyleButton):
            widget.setEnabled(enabled)
        self.primitiveSurfaceComboBox.setEnabled(enabled and supports_surface)
        self.primitiveTextureLineEdit.blockSignals(True)
        self.primitiveTextureLineEdit.setText(str(current.get("texture") or "") if current else "")
        self.primitiveTextureLineEdit.blockSignals(False)
        if current:
            self._select_surface_combo_value(self.primitiveSurfaceComboBox, str(current.get("surface_id") or ""))
        self._update_primitive_surface_hint()

    def _emit_primitive_style(self) -> None:
        data = self._current_primitive_transform_data()
        if not data:
            return
        surface_id = ""
        if bool(data.get("supports_walkmesh_surface", False)):
            surface_id = str(self._current_primitive_surface_data().get("surface_id") or "")
        self.roomPrimitiveStyleRequested.emit(
            str(data.get("room_resref") or ""),
            str(data.get("primitive_name") or ""),
            self.primitiveTextureLineEdit.text().strip(),
            surface_id,
        )

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
        self._update_primitive_dimension_controls(data)
        self._update_primitive_style_controls(data)
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
            self.removePrimitiveButton,
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

    def _update_primitive_dimension_controls(self, data: dict | None = None) -> None:
        current = self._current_primitive_transform_data() if data is None else data
        dimensions = tuple(current.get("dimensions") or ()) if current else ()
        for index, (label, spin) in enumerate(self._primitive_dimension_controls):
            enabled = index < len(dimensions)
            if not enabled:
                label.setText(f"Dimension {index + 1}:")
                spin.setProperty("dimensionKey", "")
                spin.setProperty("dimensionInteger", False)
                spin.setEnabled(False)
                label.setEnabled(False)
                continue
            dimension = dict(dimensions[index])
            label.setText(f"{dimension.get('label') or dimension.get('key')}:")
            label.setEnabled(True)
            spin.blockSignals(True)
            spin.setProperty("dimensionKey", str(dimension.get("key") or ""))
            spin.setProperty("dimensionInteger", bool(dimension.get("integer", False)))
            spin.setRange(float(dimension.get("minimum", 0.001)), float(dimension.get("maximum", 1000.0)))
            spin.setDecimals(0 if bool(dimension.get("integer", False)) else 3)
            spin.setSingleStep(float(dimension.get("step", 0.1)))
            spin.setSuffix(str(dimension.get("suffix", " m") or ""))
            spin.setValue(float(dimension.get("value", 0.0)))
            spin.setEnabled(True)
            spin.blockSignals(False)
        self.applyPrimitiveDimensionsButton.setEnabled(bool(current and dimensions))
        if not current:
            self.primitiveDimensionHintLabel.setText("Select an authored primitive to edit its dimensions.")
        elif not dimensions:
            self.primitiveDimensionHintLabel.setText("This primitive has no editable dimensions.")
        else:
            self.primitiveDimensionHintLabel.setText("Dimension edits rebuild the room mesh and any generated WOK faces for this primitive.")

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

    def _emit_primitive_dimensions(self) -> None:
        data = self._current_primitive_transform_data()
        if not data:
            return
        values = {}
        for _label, spin in self._primitive_dimension_controls:
            key = str(spin.property("dimensionKey") or "")
            if not key:
                continue
            if bool(spin.property("dimensionInteger")):
                values[key] = int(round(float(spin.value())))
            else:
                values[key] = float(spin.value())
        if values:
            self.roomPrimitiveDimensionsRequested.emit(
                str(data.get("room_resref") or ""),
                str(data.get("primitive_name") or ""),
                values,
            )

    def _emit_remove_composition_primitive(self) -> None:
        data = self._current_primitive_transform_data()
        if not data:
            return
        self.roomPrimitiveRemoveRequested.emit(
            str(data.get("room_resref") or ""),
            str(data.get("primitive_name") or ""),
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
        self._update_gameplay_spatial_controls()

    def _is_current_gameplay_kind_spatial(self) -> bool:
        kind = str(self.gameplayPlacementKindComboBox.currentData() or "").strip().lower()
        return kind not in {"store", "merchant"}

    def _update_gameplay_spatial_controls(self) -> None:
        if not hasattr(self, "gameplaySpatialHintLabel"):
            return
        spatial = self._is_current_gameplay_kind_spatial()
        for widget in (
            self.gameplayPosXSpinBox,
            self.gameplayPosYSpinBox,
            self.gameplayPosZSpinBox,
            self.gameplayBearingSpinBox,
        ):
            widget.setEnabled(spatial)
        if spatial:
            self.gameplaySpatialHintLabel.setText("Spatial resources are placed in the viewport and can be moved after creation.")
        else:
            self.gameplaySpatialHintLabel.setText("Stores/merchants are module-level resources. They appear in the outliner and export to the GIT StoreList, but they do not get viewport markers.")
        self._emit_gameplay_placement_status()

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
        self._emit_gameplay_placement_status()

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

    def _emit_gameplay_placement_status(self) -> None:
        if not hasattr(self, "gameplayPlacementKindComboBox"):
            return
        kind = str(self.gameplayPlacementKindComboBox.currentData() or "placeable").replace("_", " ")
        template = self.gameplayTemplateLineEdit.text().strip() or "(template not selected)"
        tag = self.gameplayTagLineEdit.text().strip()
        scope = "viewport marker" if self._is_current_gameplay_kind_spatial() else "module-level resource"
        suffix = f", tag {tag}" if tag else ""
        self.gameplayPlacementStatusChanged.emit(f"placing {kind}: {template}{suffix} ({scope})")

    def set_script_hook_fields(self, choices) -> None:
        """Populate script hook field choices from the controller/core policy."""

        data = dict(choices or {})
        self._script_hook_fields = {
            "area": tuple(str(item) for item in data.get("area", ()) or ()),
            "module": tuple(str(item) for item in data.get("module", ()) or ()),
        }
        self._update_script_hook_field_choices()

    def set_script_hooks(self, hooks) -> None:
        """Show current authored script hooks in the editor controls."""

        data = dict(hooks or {})
        self._script_hooks = {
            "area": {str(key): str(value) for key, value in dict(data.get("area") or {}).items()},
            "module": {str(key): str(value) for key, value in dict(data.get("module") or {}).items()},
        }
        self._update_script_hook_value()

    def _current_script_hook_scope(self) -> str:
        return str(self.scriptHookScopeComboBox.currentData() or "area")

    def _current_script_hook_field(self) -> str:
        return str(self.scriptHookFieldComboBox.currentData() or self.scriptHookFieldComboBox.currentText() or "").strip()

    def _update_script_hook_field_choices(self) -> None:
        scope = self._current_script_hook_scope()
        current = self._current_script_hook_field()
        fields = tuple(self._script_hook_fields.get(scope, ()) or ())
        self.scriptHookFieldComboBox.blockSignals(True)
        self.scriptHookFieldComboBox.clear()
        restore_index = -1
        for field_name in fields:
            self.scriptHookFieldComboBox.addItem(field_name, field_name)
            if field_name == current:
                restore_index = self.scriptHookFieldComboBox.count() - 1
        if self.scriptHookFieldComboBox.count() <= 0:
            self.scriptHookFieldComboBox.addItem("No script hook fields available", "")
        if restore_index >= 0:
            self.scriptHookFieldComboBox.setCurrentIndex(restore_index)
        self.scriptHookFieldComboBox.blockSignals(False)
        self._update_script_hook_value()

    def _update_script_hook_value(self) -> None:
        scope = self._current_script_hook_scope()
        field_name = self._current_script_hook_field()
        script = str(dict(self._script_hooks.get(scope) or {}).get(field_name, ""))
        self.scriptHookResrefLineEdit.blockSignals(True)
        self.scriptHookResrefLineEdit.setText(script)
        self.scriptHookResrefLineEdit.blockSignals(False)
        has_field = bool(field_name)
        self.scriptHookResrefLineEdit.setEnabled(has_field)
        self.assignScriptHookButton.setEnabled(has_field)
        self.clearScriptHookButton.setEnabled(bool(has_field and script))
        if script:
            self.scriptHookHintLabel.setText(f"{scope.title()} hook {field_name} is assigned to {script}.ncs.")
        else:
            self.scriptHookHintLabel.setText(
                "Assign optional KOTOR script hooks. Referenced .ncs files must resolve from the module package, Override, or base game."
            )

    def _emit_assign_script_hook(self) -> None:
        field_name = self._current_script_hook_field()
        if field_name:
            self.scriptHookRequested.emit(self._current_script_hook_scope(), field_name, self.scriptHookResrefLineEdit.text().strip())

    def _emit_clear_script_hook(self) -> None:
        field_name = self._current_script_hook_field()
        if field_name:
            self.scriptHookRequested.emit(self._current_script_hook_scope(), field_name, "")

    def _emit_room_light(self) -> None:
        self.roomLightRequested.emit(
            self.roomLightRoomLineEdit.text().strip(),
            self.roomLightNameLineEdit.text().strip(),
            float(self.roomLightPosXSpinBox.value()),
            float(self.roomLightPosYSpinBox.value()),
            float(self.roomLightPosZSpinBox.value()),
            float(self.roomLightColorRSpinBox.value()),
            float(self.roomLightColorGSpinBox.value()),
            float(self.roomLightColorBSpinBox.value()),
            float(self.roomLightRadiusSpinBox.value()),
            float(self.roomLightIntensitySpinBox.value()),
            str(self.roomLightTypeComboBox.currentData() or "point"),
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
