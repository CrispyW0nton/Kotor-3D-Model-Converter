"""Builder workflow tab."""

from __future__ import annotations

import math

from PySide6 import QtCore, QtGui, QtWidgets

from .map_studio_modeling_shelf import map_studio_modeling_icon


class BuilderTab(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)
    primitivePresetRequested = QtCore.Signal(str, str)
    roomOperationRequested = QtCore.Signal(str, float, int, float, float, float, float)
    floorPlanExtrusionRequested = QtCore.Signal(str, float, float, bool, str)
    floorPlanOpeningRequested = QtCore.Signal(str, str, int, float, float, float, float)
    floorPlanOpeningMarkerRequested = QtCore.Signal(str, str, str, str, str, str, str, int, int)
    floorPlanVertexSnapPreviewRequested = QtCore.Signal(str, int)
    floorPlanVertexSnapRequested = QtCore.Signal(str, int, int, str)
    floorPlanVertexWeldRequested = QtCore.Signal(str, object, int, str)
    floorPlanVertexFlattenRequested = QtCore.Signal(str, object, str, object)
    floorPlanVertexCleanupRequested = QtCore.Signal(str, float)
    floorPlanVertexMirrorRequested = QtCore.Signal(str, str)
    floorPlanFaceFillRequested = QtCore.Signal(str, object)
    floorPlanFaceSplitRequested = QtCore.Signal(str, object)
    floorPlanFaceTriangulateRequested = QtCore.Signal(str)
    floorPlanNormalsCleanupRequested = QtCore.Signal(str)
    terrainOperationRequested = QtCore.Signal(str, str, int, int, float, float, int, int, float)
    terrainLiveBrushFrameRequested = QtCore.Signal(str, str, int, int, float, float, int, int, float)
    roomRectangularUnionRequested = QtCore.Signal(str, str, str)
    floorPlanBridgeRequested = QtCore.Signal(str, int, str, int, str)
    roomStyleRequested = QtCore.Signal(str, str)
    roomPrimitiveAddRequested = QtCore.Signal(str, str)
    roomPrimitiveTransformRequested = QtCore.Signal(str, str, float, float, float, float, float, float, float, float, float, float)
    roomPrimitiveDimensionsRequested = QtCore.Signal(str, str, object)
    roomPrimitiveDimensionsPreviewRequested = QtCore.Signal(str, str, object)
    roomPrimitiveDimensionsPreviewCancelled = QtCore.Signal(str, str)
    roomPrimitiveStyleRequested = QtCore.Signal(str, str, str, str)
    roomPrimitiveRemoveRequested = QtCore.Signal(str, str)
    roomPrimitiveSeparateRequested = QtCore.Signal(str, str, str)
    moduleEntryPointRequested = QtCore.Signal(str, float, float, float, float)
    gameplayPlacementRequested = QtCore.Signal(str, str, str, float, float, float, float)
    gameplayPlacementStatusChanged = QtCore.Signal(str)
    roomLightRequested = QtCore.Signal(str, str, float, float, float, float, float, float, float, float, str)
    scriptHookRequested = QtCore.Signal(str, str, str)
    scriptEditorRequested = QtCore.Signal(str, str, str)
    modelingContextChanged = QtCore.Signal(str)
    buildSectionChanged = QtCore.Signal(str)
    terrainCreateRequested = QtCore.Signal()
    terrainDressingRequested = QtCore.Signal()
    terrainPaintRequested = QtCore.Signal()
    snapRoomsAtDoorwayRequested = QtCore.Signal()
    snapRoomsToGridRequested = QtCore.Signal()
    buildingToolChanged = QtCore.Signal(str)
    buildingSettingsChanged = QtCore.Signal(object)
    buildingStyleChanged = QtCore.Signal(str, str)
    buildingLevelCreateRequested = QtCore.Signal(object)
    buildingLevelViewChanged = QtCore.Signal(object)
    browseVanillaRoomKitsRequested = QtCore.Signal()
    spatialPlanVisibilityChanged = QtCore.Signal(bool)
    spatialPlanAuditRequested = QtCore.Signal()

    ACTIONS = (
        "Create grdev01 Dev Room",
        "Create grgold01 Golden Proof Module",
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
        self._gameplay_palette_page_limit = 192
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.buildSectionTabs = QtWidgets.QTabWidget(self)
        self.buildSectionTabs.setObjectName("mapStudioBuildSectionTabs")
        self.buildSectionTabs.setDocumentMode(True)

        self.roomBuildingPage = QtWidgets.QWidget(self.buildSectionTabs)
        self.roomBuildingPage.setObjectName("mapStudioRoomBuildingPage")
        room_page_layout = QtWidgets.QVBoxLayout(self.roomBuildingPage)
        room_page_layout.setContentsMargins(6, 6, 6, 6)
        self._roomPrimaryContainer = QtWidgets.QWidget(self.roomBuildingPage)
        self._roomPrimaryLayout = QtWidgets.QVBoxLayout(self._roomPrimaryContainer)
        self._roomPrimaryLayout.setContentsMargins(0, 0, 0, 0)
        room_page_layout.addWidget(self._roomPrimaryContainer)
        self.roomAdvancedToggle = QtWidgets.QToolButton(self.roomBuildingPage)
        self.roomAdvancedToggle.setObjectName("mapStudioRoomAdvancedToolsButton")
        self.roomAdvancedToggle.setText("Advanced room geometry")
        self.roomAdvancedToggle.setCheckable(True)
        self.roomAdvancedToggle.setChecked(False)
        self.roomAdvancedToggle.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.roomAdvancedToggle.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        room_page_layout.addWidget(self.roomAdvancedToggle)
        self._roomAdvancedContainer = QtWidgets.QWidget(self.roomBuildingPage)
        self._roomAdvancedContainer.setObjectName("mapStudioRoomAdvancedTools")
        self._roomAdvancedLayout = QtWidgets.QVBoxLayout(self._roomAdvancedContainer)
        self._roomAdvancedLayout.setContentsMargins(0, 0, 0, 0)
        self._roomAdvancedContainer.setVisible(False)
        room_page_layout.addWidget(self._roomAdvancedContainer)
        room_page_layout.addStretch(1)

        self.terrainBuildingPage = QtWidgets.QWidget(self.buildSectionTabs)
        self.terrainBuildingPage.setObjectName("mapStudioTerrainBuildingPage")
        self._terrainBuildingLayout = QtWidgets.QVBoxLayout(self.terrainBuildingPage)
        self._terrainBuildingLayout.setContentsMargins(6, 6, 6, 6)
        self._terrainBuildingLayout.addStretch(1)

        self.skyboxBuildingPage = QtWidgets.QWidget(self.buildSectionTabs)
        self.skyboxBuildingPage.setObjectName("mapStudioSkyboxBuildingPage")
        self._skyboxBuildingLayout = QtWidgets.QVBoxLayout(self.skyboxBuildingPage)
        self._skyboxBuildingLayout.setContentsMargins(6, 6, 6, 6)
        self.skyboxBuildGuideLabel = QtWidgets.QLabel(
            "Build a KOTOR visual-only sky dome from five engine textures, or convert an HDR/panorama into the required texture set."
        )
        self.skyboxBuildGuideLabel.setObjectName("mapStudioSkyboxBuildGuideLabel")
        self.skyboxBuildGuideLabel.setWordWrap(True)
        self._skyboxBuildingLayout.addWidget(self.skyboxBuildGuideLabel)
        self._skyboxBuildingLayout.addStretch(1)

        self.buildSectionTabs.addTab(self.roomBuildingPage, "Room Building")
        self.buildSectionTabs.addTab(self.terrainBuildingPage, "Terrain Building")
        self.buildSectionTabs.addTab(self.skyboxBuildingPage, "Skybox")
        layout.addWidget(self.buildSectionTabs, 1)

        self._legacyToolsContainer = QtWidgets.QWidget(self)
        self._legacyToolsContainer.setObjectName("mapStudioLegacyBuilderTools")
        self._legacyToolsLayout = QtWidgets.QVBoxLayout(self._legacyToolsContainer)
        self._legacyToolsLayout.setContentsMargins(0, 0, 0, 0)
        self._legacyToolsContainer.setVisible(False)
        self.builderGuideLabel = QtWidgets.QLabel(
            "Build is organized around room assembly, terrain sculpting and dressing, and KOTOR skybox authoring."
        )
        self.builderGuideLabel.setObjectName("mapStudioBuilderGuideLabel")
        self.builderGuideLabel.setWordWrap(True)
        self.builderGuideLabel.setToolTip(self.builderGuideLabel.text())
        self.builderGuideLabel.setVisible(False)
        self._legacyToolsLayout.addWidget(self.builderGuideLabel)
        building_box = QtWidgets.QGroupBox("Vanilla Environment Builder")
        building_box.setObjectName("mapStudioDirectBuildingGroup")
        building_layout = QtWidgets.QVBoxLayout(building_box)
        self.buildingGuideLabel = QtWidgets.QLabel(
            "Choose an area kit, draw a room or open courtyard, then drag matching vanilla rooms, buildings, and props from the shelf. "
            "Doorway magnets create the opening, transition door, and continuous walkmesh."
        )
        self.buildingGuideLabel.setObjectName("mapStudioDirectBuildingGuide")
        self.buildingGuideLabel.setWordWrap(True)
        building_layout.addWidget(self.buildingGuideLabel)
        self.buildingWorkflowStepsLabel = QtWidgets.QLabel(
            "1  Choose Interior or Exterior     2  Pick the area style     3  Draw, connect, then dress"
        )
        self.buildingWorkflowStepsLabel.setObjectName("mapStudioBuildingWorkflowSteps")
        self.buildingWorkflowStepsLabel.setWordWrap(True)
        self.buildingWorkflowStepsLabel.setAccessibleName("Environment builder workflow")
        building_layout.addWidget(self.buildingWorkflowStepsLabel)
        tool_row = QtWidgets.QHBoxLayout()
        tool_row.setContentsMargins(0, 4, 0, 4)
        self.buildingToolButtonGroup = QtWidgets.QButtonGroup(self)
        self.buildingToolButtonGroup.setExclusive(True)
        self.buildingToolButtons: dict[str, QtWidgets.QToolButton] = {}
        for label, key, icon_key, description in (
            (
                "Select",
                "select",
                "select_quads",
                "Select and transform rooms, buildings, props, and openings.",
            ),
            (
                "Draw Room",
                "walls",
                "quad_draw",
                "Click successive floor points; click the first point to close and build the room.",
            ),
            (
                "Add Door",
                "door",
                "make_hole",
                "Click a wall to add a style-correct transition opening and door.",
            ),
            (
                "Add Window",
                "window",
                "extrude",
                "Click a wall to add a framed window opening.",
            ),
        ):
            button = QtWidgets.QToolButton(building_box)
            button.setText(label)
            button.setIcon(map_studio_modeling_icon(icon_key, button.palette(), 28))
            button.setIconSize(QtCore.QSize(28, 28))
            button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setCheckable(True)
            button.setAutoRaise(False)
            button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
            button.setObjectName(f"mapStudioBuilding{key.title()}ToolButton")
            button.setAccessibleName(label)
            button.setAccessibleDescription(description)
            button.setToolTip(description)
            self.buildingToolButtonGroup.addButton(button)
            self.buildingToolButtons[key] = button
            tool_row.addWidget(button, 1)
        self.buildingToolButtons["select"].setChecked(True)
        building_layout.addLayout(tool_row)
        building_form = QtWidgets.QFormLayout()
        self.buildingLevelComboBox = QtWidgets.QComboBox(building_box)
        self.buildingLevelComboBox.setObjectName("mapStudioBuildingLevelComboBox")
        self.buildingLevelComboBox.addItem("Level 1 (0.00 m)", {"index": 0, "name": "Level 1", "floor_z": 0.0})
        self.addBuildingLevelButton = QtWidgets.QPushButton("Add Level", building_box)
        self.addBuildingLevelButton.setObjectName("mapStudioAddBuildingLevelButton")
        self.addBuildingLevelButton.setToolTip(
            "Create a persistent level directly above the selected level using the current floor-to-floor height."
        )
        level_row = QtWidgets.QWidget(building_box)
        level_row_layout = QtWidgets.QHBoxLayout(level_row)
        level_row_layout.setContentsMargins(0, 0, 0, 0)
        level_row_layout.addWidget(self.buildingLevelComboBox, 1)
        level_row_layout.addWidget(self.addBuildingLevelButton)
        self.buildingLevelViewComboBox = QtWidgets.QComboBox(building_box)
        self.buildingLevelViewComboBox.setObjectName("mapStudioBuildingLevelViewComboBox")
        self.buildingLevelViewComboBox.addItem("Stacked", "stacked")
        self.buildingLevelViewComboBox.addItem("Exploded", "exploded")
        self.buildingLevelViewComboBox.addItem("Solo active level", "solo")
        self.buildingLevelViewComboBox.setToolTip(
            "Stacked shows true elevations. Exploded adds a temporary visual gap. Solo hides other levels for precise editing."
        )
        self.buildingStyleComboBox = QtWidgets.QComboBox(building_box)
        self.buildingStyleComboBox.setObjectName("mapStudioBuildingStyleComboBox")
        self.buildingStyleComboBox.setEditable(True)
        self.buildingStyleComboBox.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.buildingStyleComboBox.setMaxVisibleItems(18)
        self.buildingStyleComboBox.setPlaceholderText("Type a planet, ship, or module…")
        self.buildingStyleComboBox.setToolTip(
            "Search by a familiar location such as Dantooine, Telos, Dxun, Manaan, or Ebon Hawk."
        )
        self.buildingStyleComboBox.completer().setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
        self.buildingStyleComboBox.completer().setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self.buildingStyleComboBox.addItem("PLCaa Neutral Blockout", {"style_id": "plcaa_graybox"})
        self._buildingStyleRows: list[dict[str, object]] = []
        self._lastAppliedBuildingStyleId = ""
        self._lastAppliedBuildingArchetypeKey = ""
        self.buildingArchetypeComboBox = QtWidgets.QComboBox(building_box)
        self.buildingArchetypeComboBox.setObjectName("mapStudioBuildingArchetypeComboBox")
        self.buildingArchetypeComboBox.addItem(
            "Default room contour",
            {"archetype_id": "", "label": "Default room contour", "shell_profile": ""},
        )
        self.buildingArchetypeComboBox.setToolTip(
            "Choose a measured room contour within the selected module style. "
            "For example, a Korriban reliquary chamber is not a stretched tomb corridor."
        )
        self.buildingKindComboBox = QtWidgets.QComboBox(building_box)
        self.buildingKindComboBox.setObjectName("mapStudioBuildingKindComboBox")
        self.buildingKindComboBox.addItem("Interior — enclosed rooms", "interior")
        self.buildingKindComboBox.addItem("Exterior — open courtyards", "exterior")
        self.buildingKindComboBox.addItem("All environment kits", "")
        self.buildingKindComboBox.setToolTip(
            "Interior kits create ceilings. Exterior kits create open courtyards and expose matching freestanding buildings."
        )
        self.browseVanillaRoomKitsButton = QtWidgets.QPushButton("Browse Vanilla Room Kits…", building_box)
        self.browseVanillaRoomKitsButton.setObjectName("mapStudioBrowseVanillaRoomKitsButton")
        self.browseVanillaRoomKitsButton.setToolTip(
            "Browse complete retail room geometry when a palette-driven wall layout is not enough."
        )
        self.browseVanillaRoomKitsButton.setVisible(False)
        self.browseVanillaRoomKitsButton.clicked.connect(lambda _checked=False: self.browseVanillaRoomKitsRequested.emit())
        self.buildingWallHeightSpinBox = self._make_transform_spin(
            "mapStudioBuildingWallHeightSpinBox", 0.25, 50.0, " m", value=3.0, step=0.25
        )
        self.buildingFloorZSpinBox = self._make_transform_spin(
            "mapStudioBuildingFloorZSpinBox", -1000.0, 1000.0, " m", value=0.0, step=0.25
        )
        self.buildingFloorToFloorSpinBox = self._make_transform_spin(
            "mapStudioBuildingFloorToFloorSpinBox", 0.25, 50.0, " m", value=3.0, step=0.25
        )
        self.buildingExplodedGapSpinBox = self._make_transform_spin(
            "mapStudioBuildingExplodedGapSpinBox", 0.25, 25.0, " m", value=1.5, step=0.25
        )
        self.buildingGridSizeSpinBox = self._make_transform_spin(
            "mapStudioBuildingGridSizeSpinBox", 0.05, 10.0, " m", value=0.25, step=0.05
        )
        self.buildingSnapCheckBox = QtWidgets.QCheckBox("Snap wall corners to grid", building_box)
        self.buildingSnapCheckBox.setObjectName("mapStudioBuildingSnapCheckBox")
        self.buildingSnapCheckBox.setChecked(True)
        self.buildingCeilingCheckBox = QtWidgets.QCheckBox("Create ceiling", building_box)
        self.buildingCeilingCheckBox.setObjectName("mapStudioBuildingCeilingCheckBox")
        self.buildingCeilingCheckBox.setChecked(True)
        self.buildingRoofTypeComboBox = QtWidgets.QComboBox(building_box)
        self.buildingRoofTypeComboBox.setObjectName("mapStudioBuildingRoofTypeComboBox")
        self.buildingRoofTypeComboBox.addItem("No exterior roof", "none")
        self.buildingRoofTypeComboBox.addItem("Flat roof", "flat")
        self.buildingRoofTypeComboBox.addItem("Pitched / hip roof", "hip")
        self.buildingRoofTypeComboBox.addItem("Gable roof", "gable")
        self.buildingRoofTypeComboBox.setToolTip(
            "Exterior mode defaults to an engine-safe pitched roof for any closed footprint. Gable is available for rectangular rooms."
        )
        self.buildingRoofPitchSpinBox = self._make_transform_spin(
            "mapStudioBuildingRoofPitchSpinBox", 5.0, 70.0, "°", value=30.0, step=1.0
        )
        self.buildingRoofOverhangSpinBox = self._make_transform_spin(
            "mapStudioBuildingRoofOverhangSpinBox", 0.0, 5.0, " m", value=0.25, step=0.05
        )
        self.buildingOpeningWidthSpinBox = self._make_transform_spin(
            "mapStudioBuildingOpeningWidthSpinBox", 0.25, 20.0, " m", value=1.25, step=0.05
        )
        self.buildingOpeningHeightSpinBox = self._make_transform_spin(
            "mapStudioBuildingOpeningHeightSpinBox", 0.25, 20.0, " m", value=2.2, step=0.05
        )
        self.buildingWindowHeightSpinBox = self._make_transform_spin(
            "mapStudioBuildingWindowHeightSpinBox", 0.25, 20.0, " m", value=1.2, step=0.05
        )
        self.buildingWindowSillSpinBox = self._make_transform_spin(
            "mapStudioBuildingWindowSillSpinBox", 0.0, 20.0, " m", value=1.0, step=0.05
        )
        building_form.addRow("Level:", level_row)
        building_form.addRow("Level view:", self.buildingLevelViewComboBox)
        building_form.addRow("Environment:", self.buildingKindComboBox)
        building_form.addRow("Area style:", self.buildingStyleComboBox)
        building_form.addRow("Architecture:", self.buildingArchetypeComboBox)
        building_layout.addLayout(building_form)
        self.buildingStyleSummaryLabel = QtWidgets.QLabel("Neutral Blockout · interior/exterior preview palette", building_box)
        self.buildingStyleSummaryLabel.setObjectName("mapStudioBuildingStyleSummaryLabel")
        self.buildingStyleSummaryLabel.setWordWrap(True)
        building_layout.addWidget(self.buildingStyleSummaryLabel)
        self.buildingSettingsToggle = QtWidgets.QToolButton(building_box)
        self.buildingSettingsToggle.setObjectName("mapStudioPascalBuildingSettingsToggle")
        self.buildingSettingsToggle.setText("Building settings")
        self.buildingSettingsToggle.setCheckable(True)
        self.buildingSettingsToggle.setChecked(False)
        self.buildingSettingsToggle.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.buildingSettingsToggle.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        building_layout.addWidget(self.buildingSettingsToggle)
        self.buildingSettingsContainer = QtWidgets.QWidget(building_box)
        self.buildingSettingsContainer.setObjectName("mapStudioPascalBuildingSettingsContainer")
        building_settings_form = QtWidgets.QFormLayout(self.buildingSettingsContainer)
        building_settings_form.setContentsMargins(0, 0, 0, 0)
        building_settings_form.addRow("Wall height:", self.buildingWallHeightSpinBox)
        building_settings_form.addRow("Floor elevation:", self.buildingFloorZSpinBox)
        building_settings_form.addRow("Floor-to-floor:", self.buildingFloorToFloorSpinBox)
        building_settings_form.addRow("Exploded gap:", self.buildingExplodedGapSpinBox)
        building_settings_form.addRow("Grid:", self.buildingGridSizeSpinBox)
        building_settings_form.addRow(self.buildingSnapCheckBox)
        building_settings_form.addRow(self.buildingCeilingCheckBox)
        building_settings_form.addRow("Exterior roof:", self.buildingRoofTypeComboBox)
        building_settings_form.addRow("Roof pitch:", self.buildingRoofPitchSpinBox)
        building_settings_form.addRow("Roof overhang:", self.buildingRoofOverhangSpinBox)
        building_settings_form.addRow("Opening width:", self.buildingOpeningWidthSpinBox)
        building_settings_form.addRow("Door height:", self.buildingOpeningHeightSpinBox)
        building_settings_form.addRow("Window height:", self.buildingWindowHeightSpinBox)
        building_settings_form.addRow("Window sill:", self.buildingWindowSillSpinBox)
        self.buildingSettingsContainer.setVisible(False)
        building_layout.addWidget(self.buildingSettingsContainer)
        self.buildingStatusLabel = QtWidgets.QLabel(
            "Choose Draw Room and close a footprint, or drag a matching vanilla room or building from the shelf below."
        )
        self.buildingStatusLabel.setObjectName("mapStudioBuildingStatusLabel")
        self.buildingStatusLabel.setWordWrap(True)
        building_layout.addWidget(self.buildingStatusLabel)
        spatial_box = QtWidgets.QGroupBox("Spatial Intent", building_box)
        spatial_box.setObjectName("mapStudioSpatialIntentGroup")
        spatial_layout = QtWidgets.QVBoxLayout(spatial_box)
        self.spatialDesignSummaryLabel = QtWidgets.QLabel(
            "No spatial plan yet · define districts, routes, landmarks, and why each object belongs where it is.",
            spatial_box,
        )
        self.spatialDesignSummaryLabel.setObjectName("mapStudioSpatialDesignSummaryLabel")
        self.spatialDesignSummaryLabel.setWordWrap(True)
        self.spatialDesignSummaryLabel.setAccessibleName("Spatial design status")
        spatial_layout.addWidget(self.spatialDesignSummaryLabel)
        spatial_controls = QtWidgets.QHBoxLayout()
        self.spatialDesignOverlayCheckBox = QtWidgets.QCheckBox("Show plan on grid", spatial_box)
        self.spatialDesignOverlayCheckBox.setObjectName("mapStudioSpatialDesignOverlayCheckBox")
        self.spatialDesignOverlayCheckBox.setChecked(True)
        self.spatialDesignOverlayCheckBox.setToolTip(
            "Show named zones, circulation routes, landmarks, and planned object footprints in the viewport."
        )
        self.auditSpatialDesignButton = QtWidgets.QPushButton("Audit Layout", spatial_box)
        self.auditSpatialDesignButton.setObjectName("mapStudioAuditSpatialDesignButton")
        self.auditSpatialDesignButton.setToolTip(
            "Check player clearance, grid alignment, zone membership, overlapping props, and unexplained placement."
        )
        spatial_controls.addWidget(self.spatialDesignOverlayCheckBox)
        spatial_controls.addStretch(1)
        spatial_controls.addWidget(self.auditSpatialDesignButton)
        spatial_layout.addLayout(spatial_controls)
        self.spatialDesignLedger = QtWidgets.QTreeWidget(spatial_box)
        self.spatialDesignLedger.setObjectName("mapStudioSpatialDesignLedger")
        self.spatialDesignLedger.setHeaderLabels(("Object", "Grid position", "Zone", "Purpose"))
        self.spatialDesignLedger.setRootIsDecorated(False)
        self.spatialDesignLedger.setAlternatingRowColors(True)
        self.spatialDesignLedger.setUniformRowHeights(True)
        self.spatialDesignLedger.setToolTip(
            "Exact placement ledger: every object has a coordinate, district, purpose, and location rationale."
        )
        spatial_layout.addWidget(self.spatialDesignLedger)
        building_layout.addWidget(spatial_box)
        self.spatialDesignOverlayCheckBox.toggled.connect(self.spatialPlanVisibilityChanged.emit)
        self.auditSpatialDesignButton.clicked.connect(
            lambda _checked=False: self.spatialPlanAuditRequested.emit()
        )
        self.buildingSettingsToggle.toggled.connect(
            lambda visible: (
                self.buildingSettingsContainer.setVisible(bool(visible)),
                self.buildingSettingsToggle.setArrowType(
                    QtCore.Qt.ArrowType.DownArrow if visible else QtCore.Qt.ArrowType.RightArrow
                ),
            )
        )
        self._roomPrimaryLayout.addWidget(building_box)
        modeling_box = QtWidgets.QGroupBox("Modeling Mode + Snap")
        modeling_layout = QtWidgets.QFormLayout(modeling_box)
        self.modelingModeGuideLabel = QtWidgets.QLabel(
            "Manual modeling workspace: switch between Object, Vertex, Edge, Face, Terrain, and Walkmesh editing. "
            "Use these controls to choose the tool intent before editing primitives, terrain, or WOK surfaces; "
            "Ctrl+T shows Universal Manipulator dimensions, Hold V snaps vertices, and Hold J aligns transforms to one level."
        )
        self.modelingModeGuideLabel.setObjectName("mapStudioModelingModeGuideLabel")
        self.modelingModeGuideLabel.setWordWrap(True)
        self.modelingModeGuideLabel.setToolTip(self.modelingModeGuideLabel.text())
        self.modelingModeGuideLabel.setVisible(False)
        self.componentModeComboBox = QtWidgets.QComboBox()
        self.componentModeComboBox.setObjectName("mapStudioComponentModeComboBox")
        self.modelingToolComboBox = QtWidgets.QComboBox()
        self.modelingToolComboBox.setObjectName("mapStudioModelingToolComboBox")
        self.snapModeComboBox = QtWidgets.QComboBox()
        self.snapModeComboBox.setObjectName("mapStudioSnapModeComboBox")
        self.modelingToolHintLabel = QtWidgets.QLabel(
            "Choose a component mode and a KOTOR-aware modeling tool. Planned tools stay visible so the roadmap is honest."
        )
        self.modelingToolHintLabel.setObjectName("mapStudioModelingToolHintLabel")
        self.modelingToolHintLabel.setWordWrap(True)
        self.modelingToolHintLabel.setToolTip(self.modelingToolHintLabel.text())
        self.modelingToolHintLabel.setVisible(False)
        self.modelingStatusLabel = QtWidgets.QLabel("Modeling: Object mode / Grid snap")
        self.modelingStatusLabel.setObjectName("mapStudioModelingStatusLabel")
        self.modelingStatusLabel.setWordWrap(True)
        modeling_layout.addRow(self.modelingModeGuideLabel)
        modeling_layout.addRow("Component:", self.componentModeComboBox)
        modeling_layout.addRow("Tool:", self.modelingToolComboBox)
        modeling_layout.addRow("Snap:", self.snapModeComboBox)
        modeling_layout.addRow(self.modelingToolHintLabel)
        modeling_layout.addRow(self.modelingStatusLabel)
        self._roomAdvancedLayout.addWidget(modeling_box)
        primitive_box = QtWidgets.QGroupBox("Authored Room Primitive")
        primitive_layout = QtWidgets.QFormLayout(primitive_box)
        self.roomGeometryWorkflowLabel = QtWidgets.QLabel(
            "Room geometry: choose a preset here or use the workflow shortcuts for Starter Room, Doorway Blockout, and Corridor. Shape it with bevel/inset/cuts, add primitives, then assign material and WOK surface."
        )
        self.roomGeometryWorkflowLabel.setObjectName("mapStudioRoomGeometryWorkflowLabel")
        self.roomGeometryWorkflowLabel.setWordWrap(True)
        self.roomGeometryWorkflowLabel.setToolTip(self.roomGeometryWorkflowLabel.text())
        self.roomGeometryWorkflowLabel.setVisible(False)
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
        primitive_layout.addRow(self.roomGeometryWorkflowLabel)
        primitive_layout.addRow("Module:", self.moduleRootLineEdit)
        primitive_layout.addRow("Primitive:", self.roomPrimitivePresetComboBox)
        primitive_layout.addRow(self.roomPrimitiveDescriptionLabel)
        primitive_layout.addRow(self.createPrimitiveButton)
        self._roomAdvancedLayout.addWidget(primitive_box)
        magnetic_box = QtWidgets.QGroupBox("Magnetic Room Assembly")
        magnetic_box.setObjectName("mapStudioMagneticRoomAssemblyGroup")
        magnetic_layout = QtWidgets.QVBoxLayout(magnetic_box)
        magnetic_hint = QtWidgets.QLabel(
            "Place room pieces, then snap matching doorway seams or selected pieces to the construction grid. "
            "Hold V for corner/vertex snapping and J for same-level alignment while transforming."
        )
        magnetic_hint.setObjectName("mapStudioMagneticRoomAssemblyHint")
        magnetic_hint.setWordWrap(True)
        self.snapRoomsAtDoorwayButton = QtWidgets.QPushButton("Snap Rooms at Doorway...")
        self.snapRoomsAtDoorwayButton.setObjectName("mapStudioSnapRoomsAtDoorwayButton")
        self.snapRoomsToGridButton = QtWidgets.QPushButton("Snap Selected Rooms to Grid")
        self.snapRoomsToGridButton.setObjectName("mapStudioSnapSelectedRoomsToGridButton")
        magnetic_layout.addWidget(magnetic_hint)
        magnetic_layout.addWidget(self.snapRoomsAtDoorwayButton)
        magnetic_layout.addWidget(self.snapRoomsToGridButton)
        self._roomAdvancedLayout.addWidget(magnetic_box)
        operation_box = QtWidgets.QGroupBox("Shape Current Room")
        operation_layout = QtWidgets.QFormLayout(operation_box)
        self.roomOperationHintLabel = QtWidgets.QLabel(
            "Shape operations modify generated room geometry. Bevel/inset affect the footprint; rectangular cut creates openings or blockout detail before WOK validation."
        )
        self.roomOperationHintLabel.setObjectName("mapStudioRoomOperationHintLabel")
        self.roomOperationHintLabel.setWordWrap(True)
        self.roomOperationComboBox = QtWidgets.QComboBox()
        self.roomOperationComboBox.setObjectName("mapStudioRoomOperationComboBox")
        self.roomOperationComboBox.addItem("Bevel corners", "bevel")
        self.roomOperationComboBox.addItem("Inset footprint", "inset")
        self.roomOperationComboBox.addItem("Extrude edge", "edge_extrude")
        self.roomOperationComboBox.addItem("Split room on X", "split_x")
        self.roomOperationComboBox.addItem("Split room on Y", "split_y")
        self.roomOperationComboBox.addItem("Rectangular cut", "rectangular_cut")
        self.operationDistanceSpinBox = QtWidgets.QDoubleSpinBox()
        self.operationDistanceSpinBox.setObjectName("mapStudioRoomOperationDistanceSpinBox")
        self.operationDistanceSpinBox.setRange(0.05, 100.0)
        self.operationDistanceSpinBox.setSingleStep(0.05)
        self.operationDistanceSpinBox.setValue(0.25)
        self.operationDistanceSpinBox.setSuffix(" m")
        self.operationEdgeIndexSpinBox = QtWidgets.QSpinBox()
        self.operationEdgeIndexSpinBox.setObjectName("mapStudioRoomOperationEdgeIndexSpinBox")
        self.operationEdgeIndexSpinBox.setRange(0, 999)
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
        operation_layout.addRow(self.roomOperationHintLabel)
        operation_layout.addRow("Operation:", self.roomOperationComboBox)
        operation_layout.addRow("Distance:", self.operationDistanceSpinBox)
        operation_layout.addRow("Edge:", self.operationEdgeIndexSpinBox)
        operation_layout.addRow("Cut X:", self.cutCenterXSpinBox)
        operation_layout.addRow("Cut Y:", self.cutCenterYSpinBox)
        operation_layout.addRow("Cut Width:", self.cutWidthSpinBox)
        operation_layout.addRow("Cut Depth:", self.cutDepthSpinBox)
        operation_layout.addRow(self.applyRoomOperationButton)
        self._roomAdvancedLayout.addWidget(operation_box)
        extrusion_box = QtWidgets.QGroupBox("Floor-Plan Extrusion")
        extrusion_layout = QtWidgets.QFormLayout(extrusion_box)
        self.floorPlanExtrusionHintLabel = QtWidgets.QLabel(
            "Extrusion turns a 2D footprint into an exportable KOTOR room: floor, WOK surface, optional walls, and wall height."
        )
        self.floorPlanExtrusionHintLabel.setObjectName("mapStudioFloorPlanExtrusionHintLabel")
        self.floorPlanExtrusionHintLabel.setWordWrap(True)
        self.floorPlanExtrusionRoomComboBox = QtWidgets.QComboBox()
        self.floorPlanExtrusionRoomComboBox.setObjectName("mapStudioFloorPlanExtrusionRoomComboBox")
        self.floorPlanWallHeightSpinBox = self._make_transform_spin("mapStudioFloorPlanWallHeightSpinBox", 0.05, 1000.0, " m", value=3.0, step=0.1)
        self.floorPlanFloorZSpinBox = self._make_transform_spin("mapStudioFloorPlanFloorZSpinBox", -1000.0, 1000.0, " m", value=0.0, step=0.1)
        self.floorPlanIncludeWallsCheckBox = QtWidgets.QCheckBox("Generate wall meshes")
        self.floorPlanIncludeWallsCheckBox.setObjectName("mapStudioFloorPlanIncludeWallsCheckBox")
        self.floorPlanIncludeWallsCheckBox.setChecked(True)
        self.floorPlanSurfaceComboBox = QtWidgets.QComboBox()
        self.floorPlanSurfaceComboBox.setObjectName("mapStudioFloorPlanSurfaceComboBox")
        self.applyFloorPlanExtrusionButton = QtWidgets.QPushButton("Apply Extrusion Settings")
        self.applyFloorPlanExtrusionButton.setObjectName("mapStudioApplyFloorPlanExtrusionButton")
        extrusion_layout.addRow(self.floorPlanExtrusionHintLabel)
        extrusion_layout.addRow("Room:", self.floorPlanExtrusionRoomComboBox)
        extrusion_layout.addRow("Wall height:", self.floorPlanWallHeightSpinBox)
        extrusion_layout.addRow("Floor Z:", self.floorPlanFloorZSpinBox)
        extrusion_layout.addRow(self.floorPlanIncludeWallsCheckBox)
        extrusion_layout.addRow("WOK surface:", self.floorPlanSurfaceComboBox)
        extrusion_layout.addRow(self.applyFloorPlanExtrusionButton)
        self._roomAdvancedLayout.addWidget(extrusion_box)
        opening_box = QtWidgets.QGroupBox("Floor-Plan Wall Opening")
        opening_layout = QtWidgets.QFormLayout(opening_box)
        self.floorPlanOpeningHintLabel = QtWidgets.QLabel(
            "Cut a doorway/window-style opening in one generated wall edge. Use this for KOTOR door frames, transition seams, and clean portal blockouts."
        )
        self.floorPlanOpeningHintLabel.setObjectName("mapStudioFloorPlanOpeningHintLabel")
        self.floorPlanOpeningHintLabel.setWordWrap(True)
        self.floorPlanOpeningRoomComboBox = QtWidgets.QComboBox()
        self.floorPlanOpeningRoomComboBox.setObjectName("mapStudioFloorPlanOpeningRoomComboBox")
        self.floorPlanOpeningNameLineEdit = QtWidgets.QLineEdit("doorway_opening")
        self.floorPlanOpeningNameLineEdit.setObjectName("mapStudioFloorPlanOpeningNameLineEdit")
        self.floorPlanOpeningEdgeSpinBox = QtWidgets.QSpinBox()
        self.floorPlanOpeningEdgeSpinBox.setObjectName("mapStudioFloorPlanOpeningEdgeSpinBox")
        self.floorPlanOpeningEdgeSpinBox.setRange(0, 999)
        self.floorPlanOpeningCenterSpinBox = self._make_transform_spin("mapStudioFloorPlanOpeningCenterSpinBox", 0.01, 0.99, "", value=0.5, step=0.05)
        self.floorPlanOpeningWidthSpinBox = self._make_transform_spin("mapStudioFloorPlanOpeningWidthSpinBox", 0.05, 100.0, " m", value=1.5, step=0.1)
        self.floorPlanOpeningHeightSpinBox = self._make_transform_spin("mapStudioFloorPlanOpeningHeightSpinBox", 0.05, 100.0, " m", value=2.1, step=0.1)
        self.floorPlanOpeningBottomSpinBox = self._make_transform_spin("mapStudioFloorPlanOpeningBottomSpinBox", 0.0, 100.0, " m", value=0.0, step=0.1)
        self.applyFloorPlanOpeningButton = QtWidgets.QPushButton("Apply Wall Opening")
        self.applyFloorPlanOpeningButton.setObjectName("mapStudioApplyFloorPlanOpeningButton")
        opening_layout.addRow(self.floorPlanOpeningHintLabel)
        opening_layout.addRow("Room:", self.floorPlanOpeningRoomComboBox)
        opening_layout.addRow("Name:", self.floorPlanOpeningNameLineEdit)
        opening_layout.addRow("Edge:", self.floorPlanOpeningEdgeSpinBox)
        opening_layout.addRow("Center:", self.floorPlanOpeningCenterSpinBox)
        opening_layout.addRow("Width:", self.floorPlanOpeningWidthSpinBox)
        opening_layout.addRow("Height:", self.floorPlanOpeningHeightSpinBox)
        opening_layout.addRow("Bottom:", self.floorPlanOpeningBottomSpinBox)
        opening_layout.addRow(self.applyFloorPlanOpeningButton)
        self._roomAdvancedLayout.addWidget(opening_box)
        marker_box = QtWidgets.QGroupBox("Opening Transition Marker")
        marker_layout = QtWidgets.QFormLayout(marker_box)
        self.floorPlanOpeningMarkerLayout = marker_layout
        self.floorPlanOpeningMarkerHintLabel = QtWidgets.QLabel(
            "Create a door/trigger transition source or a waypoint destination at an authored wall opening."
        )
        self.floorPlanOpeningMarkerHintLabel.setObjectName("mapStudioFloorPlanOpeningMarkerHintLabel")
        self.floorPlanOpeningMarkerHintLabel.setWordWrap(True)
        self.floorPlanOpeningMarkerRoomComboBox = QtWidgets.QComboBox()
        self.floorPlanOpeningMarkerRoomComboBox.setObjectName("mapStudioFloorPlanOpeningMarkerRoomComboBox")
        self.floorPlanOpeningMarkerNameComboBox = QtWidgets.QComboBox()
        self.floorPlanOpeningMarkerNameComboBox.setObjectName("mapStudioFloorPlanOpeningMarkerNameComboBox")
        self.floorPlanOpeningMarkerNameComboBox.setEditable(True)
        self.floorPlanOpeningMarkerKindComboBox = QtWidgets.QComboBox()
        self.floorPlanOpeningMarkerKindComboBox.setObjectName("mapStudioFloorPlanOpeningMarkerKindComboBox")
        self.floorPlanOpeningMarkerKindComboBox.addItem("Door marker (UTD)", "door")
        self.floorPlanOpeningMarkerKindComboBox.addItem("Trigger marker (UTT)", "trigger")
        self.floorPlanOpeningMarkerKindComboBox.addItem("Waypoint destination (UTW)", "waypoint")
        self.floorPlanOpeningMarkerTemplateLineEdit = QtWidgets.QLineEdit()
        self.floorPlanOpeningMarkerTemplateLineEdit.setObjectName("mapStudioFloorPlanOpeningMarkerTemplateLineEdit")
        self.floorPlanOpeningMarkerTemplateLineEdit.setPlaceholderText("door/trigger/waypoint template resref")
        self.floorPlanOpeningMarkerTagLineEdit = QtWidgets.QLineEdit("opening_transition")
        self.floorPlanOpeningMarkerTagLineEdit.setObjectName("mapStudioFloorPlanOpeningMarkerTagLineEdit")
        self.floorPlanOpeningMarkerLinkedToLineEdit = QtWidgets.QLineEdit()
        self.floorPlanOpeningMarkerLinkedToLineEdit.setObjectName("mapStudioFloorPlanOpeningMarkerLinkedToLineEdit")
        self.floorPlanOpeningMarkerLinkedToLineEdit.setPlaceholderText("destination tag or waypoint")
        self.floorPlanOpeningMarkerLinkedModuleLineEdit = QtWidgets.QLineEdit()
        self.floorPlanOpeningMarkerLinkedModuleLineEdit.setObjectName("mapStudioFloorPlanOpeningMarkerLinkedModuleLineEdit")
        self.floorPlanOpeningMarkerLinkedModuleLineEdit.setPlaceholderText("destination module resref")
        self.floorPlanOpeningMarkerTargetTypeComboBox = QtWidgets.QComboBox()
        self.floorPlanOpeningMarkerTargetTypeComboBox.setObjectName("mapStudioFloorPlanOpeningMarkerTargetTypeComboBox")
        self.floorPlanOpeningMarkerTargetTypeComboBox.addItem("No engine link", 0)
        self.floorPlanOpeningMarkerTargetTypeComboBox.addItem("Destination door", 1)
        self.floorPlanOpeningMarkerTargetTypeComboBox.addItem("Destination waypoint", 2)
        self.floorPlanOpeningMarkerTargetTypeComboBox.setCurrentIndex(2)
        self.floorPlanOpeningMarkerTargetTypeComboBox.setToolTip(
            "KOTOR LinkedToFlags: choose whether the destination tag names a door (1) or waypoint (2)."
        )
        self.floorPlanOpeningMarkerTransitionDestSpinBox = QtWidgets.QSpinBox()
        self.floorPlanOpeningMarkerTransitionDestSpinBox.setObjectName("mapStudioFloorPlanOpeningMarkerTransitionDestSpinBox")
        self.floorPlanOpeningMarkerTransitionDestSpinBox.setRange(0, 2147483647)
        self.floorPlanOpeningMarkerTransitionDestSpinBox.setSpecialValueText("Use area name")
        self.floorPlanOpeningMarkerTransitionDestSpinBox.setToolTip(
            "Optional dialog.tlk StringRef displayed as the destination name; this is not a destination type or index."
        )
        self.createFloorPlanOpeningMarkerButton = QtWidgets.QPushButton("Create Opening Marker")
        self.createFloorPlanOpeningMarkerButton.setObjectName("mapStudioCreateOpeningTransitionMarkerButton")
        marker_layout.addRow(self.floorPlanOpeningMarkerHintLabel)
        marker_layout.addRow("Room:", self.floorPlanOpeningMarkerRoomComboBox)
        marker_layout.addRow("Opening:", self.floorPlanOpeningMarkerNameComboBox)
        marker_layout.addRow("Marker:", self.floorPlanOpeningMarkerKindComboBox)
        marker_layout.addRow("Template:", self.floorPlanOpeningMarkerTemplateLineEdit)
        marker_layout.addRow("Tag:", self.floorPlanOpeningMarkerTagLineEdit)
        marker_layout.addRow("Links to:", self.floorPlanOpeningMarkerLinkedToLineEdit)
        marker_layout.addRow("Module:", self.floorPlanOpeningMarkerLinkedModuleLineEdit)
        marker_layout.addRow("Target type:", self.floorPlanOpeningMarkerTargetTypeComboBox)
        marker_layout.addRow("Destination name StringRef:", self.floorPlanOpeningMarkerTransitionDestSpinBox)
        marker_layout.addRow(self.createFloorPlanOpeningMarkerButton)
        self._roomAdvancedLayout.addWidget(marker_box)
        vertex_box = QtWidgets.QGroupBox("Floor-Plan Vertex Tools")
        vertex_layout = QtWidgets.QFormLayout(vertex_box)
        self.floorPlanVertexHintLabel = QtWidgets.QLabel(
            "Component edits for authored floor-plan rooms. Snap one point to another, weld selected points, or flatten points to align walls and doorway seams before WOK validation."
        )
        self.floorPlanVertexHintLabel.setObjectName("mapStudioFloorPlanVertexHintLabel")
        self.floorPlanVertexHintLabel.setWordWrap(True)
        self.floorPlanVertexRoomComboBox = QtWidgets.QComboBox()
        self.floorPlanVertexRoomComboBox.setObjectName("mapStudioFloorPlanVertexRoomComboBox")
        self.floorPlanVertexTargetRoomComboBox = QtWidgets.QComboBox()
        self.floorPlanVertexTargetRoomComboBox.setObjectName("mapStudioFloorPlanVertexTargetRoomComboBox")
        self.floorPlanSourcePointSpinBox = QtWidgets.QSpinBox()
        self.floorPlanSourcePointSpinBox.setObjectName("mapStudioFloorPlanSourcePointSpinBox")
        self.floorPlanSourcePointSpinBox.setRange(0, 0)
        self.floorPlanTargetPointSpinBox = QtWidgets.QSpinBox()
        self.floorPlanTargetPointSpinBox.setObjectName("mapStudioFloorPlanTargetPointSpinBox")
        self.floorPlanTargetPointSpinBox.setRange(0, 0)
        self.floorPlanSelectedPointsLineEdit = QtWidgets.QLineEdit("0,2")
        self.floorPlanSelectedPointsLineEdit.setObjectName("mapStudioFloorPlanSelectedPointsLineEdit")
        self.floorPlanSelectedPointsLineEdit.setPlaceholderText("point indices, e.g. 0,1,2")
        self.floorPlanWeldPolicyComboBox = QtWidgets.QComboBox()
        self.floorPlanWeldPolicyComboBox.setObjectName("mapStudioFloorPlanWeldPolicyComboBox")
        self.floorPlanWeldPolicyComboBox.addItem("Target point", "target")
        self.floorPlanWeldPolicyComboBox.addItem("Selection center", "center")
        self.floorPlanFlattenAxisComboBox = QtWidgets.QComboBox()
        self.floorPlanFlattenAxisComboBox.setObjectName("mapStudioFloorPlanFlattenAxisComboBox")
        self.floorPlanFlattenAxisComboBox.addItem("Local X", "x")
        self.floorPlanFlattenAxisComboBox.addItem("Local Y", "y")
        self.floorPlanMirrorAxisComboBox = QtWidgets.QComboBox()
        self.floorPlanMirrorAxisComboBox.setObjectName("mapStudioFloorPlanMirrorAxisComboBox")
        self.floorPlanMirrorAxisComboBox.addItem("Mirror X coordinates", "x")
        self.floorPlanMirrorAxisComboBox.addItem("Mirror Y coordinates", "y")
        self.floorPlanCleanupToleranceSpinBox = self._make_transform_spin(
            "mapStudioFloorPlanCleanupToleranceSpinBox",
            0.000001,
            10.0,
            " m",
            value=0.001,
            step=0.001,
            decimals=6,
        )
        self.snapFloorPlanVertexButton = QtWidgets.QPushButton("Snap Vertex to Vertex")
        self.snapFloorPlanVertexButton.setObjectName("mapStudioSnapFloorPlanVertexButton")
        self.weldFloorPlanVerticesButton = QtWidgets.QPushButton("Weld Selected Vertices")
        self.weldFloorPlanVerticesButton.setObjectName("mapStudioWeldFloorPlanVerticesButton")
        self.flattenFloorPlanVerticesButton = QtWidgets.QPushButton("Flatten Selected Vertices")
        self.flattenFloorPlanVerticesButton.setObjectName("mapStudioFlattenFloorPlanVerticesButton")
        self.mirrorFloorPlanVerticesButton = QtWidgets.QPushButton("Mirror Footprint")
        self.mirrorFloorPlanVerticesButton.setObjectName("mapStudioMirrorFloorPlanVerticesButton")
        self.cleanupFloorPlanVerticesButton = QtWidgets.QPushButton("Cleanup Footprint")
        self.cleanupFloorPlanVerticesButton.setObjectName("mapStudioCleanupFloorPlanVerticesButton")
        self.fillFloorPlanFaceButton = QtWidgets.QPushButton("Fill Selected Face Loop")
        self.fillFloorPlanFaceButton.setObjectName("mapStudioFillFloorPlanFaceButton")
        self.splitFloorPlanFaceButton = QtWidgets.QPushButton("Split Face Between Points")
        self.splitFloorPlanFaceButton.setObjectName("mapStudioSplitFloorPlanFaceButton")
        self.triangulateFloorPlanFaceButton = QtWidgets.QPushButton("Triangulate Footprint")
        self.triangulateFloorPlanFaceButton.setObjectName("mapStudioTriangulateFloorPlanFaceButton")
        self.cleanupFloorPlanNormalsButton = QtWidgets.QPushButton("Cleanup Face Normals")
        self.cleanupFloorPlanNormalsButton.setObjectName("mapStudioCleanupFloorPlanNormalsButton")
        vertex_layout.addRow(self.floorPlanVertexHintLabel)
        vertex_layout.addRow("Room:", self.floorPlanVertexRoomComboBox)
        vertex_layout.addRow("Source point:", self.floorPlanSourcePointSpinBox)
        vertex_layout.addRow("Target room:", self.floorPlanVertexTargetRoomComboBox)
        vertex_layout.addRow("Target point:", self.floorPlanTargetPointSpinBox)
        vertex_layout.addRow(self.snapFloorPlanVertexButton)
        vertex_layout.addRow("Selected points:", self.floorPlanSelectedPointsLineEdit)
        vertex_layout.addRow("Weld:", self.floorPlanWeldPolicyComboBox)
        vertex_layout.addRow(self.weldFloorPlanVerticesButton)
        vertex_layout.addRow("Flatten axis:", self.floorPlanFlattenAxisComboBox)
        vertex_layout.addRow(self.flattenFloorPlanVerticesButton)
        vertex_layout.addRow("Mirror:", self.floorPlanMirrorAxisComboBox)
        vertex_layout.addRow(self.mirrorFloorPlanVerticesButton)
        vertex_layout.addRow("Cleanup tolerance:", self.floorPlanCleanupToleranceSpinBox)
        vertex_layout.addRow(self.cleanupFloorPlanVerticesButton)
        vertex_layout.addRow(self.fillFloorPlanFaceButton)
        vertex_layout.addRow(self.splitFloorPlanFaceButton)
        vertex_layout.addRow(self.triangulateFloorPlanFaceButton)
        vertex_layout.addRow(self.cleanupFloorPlanNormalsButton)
        self._roomAdvancedLayout.addWidget(vertex_box)
        terrain_box = QtWidgets.QGroupBox("Sculpt Terrain")
        terrain_box.setObjectName("mapStudioTerrainSculptGroup")
        terrain_layout = QtWidgets.QVBoxLayout(terrain_box)
        self.terrainWorkflowLabel = QtWidgets.QLabel(
            "Create or select a terrain surface. Sculpt Mode then opens a compact brush shelf above the viewport so the common tools stay beside your terrain."
        )
        self.terrainWorkflowLabel.setObjectName("mapStudioTerrainWorkflowLabel")
        self.terrainWorkflowLabel.setWordWrap(True)
        self.createTerrainSurfaceButton = QtWidgets.QPushButton("Create Terrain Surface")
        self.createTerrainSurfaceButton.setObjectName("mapStudioCreateTerrainSurfaceButton")
        self.createTerrainSurfaceButton.setToolTip("Create a walkable terrain heightfield and immediately enable viewport sculpting.")
        self.terrainRoomComboBox = QtWidgets.QComboBox()
        self.terrainRoomComboBox.setObjectName("mapStudioTerrainRoomComboBox")
        self.terrainBrushComboBox = QtWidgets.QComboBox()
        self.terrainBrushComboBox.setObjectName("mapStudioTerrainBrushComboBox")
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
        self.terrainRadiusSpinBox.setValue(3)
        self.terrainRadiusSpinBox.setSuffix(" cells")
        self.terrainSmoothIterationsSpinBox = QtWidgets.QSpinBox()
        self.terrainSmoothIterationsSpinBox.setObjectName("mapStudioTerrainSmoothIterationsSpinBox")
        self.terrainSmoothIterationsSpinBox.setRange(1, 32)
        self.terrainSmoothIterationsSpinBox.setValue(1)
        self.terrainSmoothStrengthSpinBox = self._make_transform_spin("mapStudioTerrainSmoothStrengthSpinBox", 0.0, 1.0, "", value=0.5, step=0.1)
        self.terrainHardnessSpinBox = self._make_transform_spin(
            "mapStudioTerrainHardnessSpinBox", 0.0, 1.0, "", value=0.5, step=0.05
        )
        self.terrainHardnessSpinBox.setToolTip(
            "Inner brush hardness: 0 gives a soft eased falloff; 1 applies full strength across the radius."
        )
        self.terrainSculptEnabledCheckBox = QtWidgets.QCheckBox("Enable viewport Sculpt Mode")
        self.terrainSculptEnabledCheckBox.setObjectName("mapStudioTerrainViewportSculptCheckBox")
        self.terrainSculptEnabledCheckBox.setChecked(True)
        self.terrainSculptEnabledCheckBox.setToolTip(
            "Left-drag sculpts, Shift+left-drag temporarily lowers, Shift+wheel resizes, right-drag orbits, "
            "and Alt+right-drag adjusts size horizontally and hardness vertically."
        )
        self.terrainHintLabel = QtWidgets.QLabel(
            "Tip: shape with the clean surface view, then enable Slope / WOK overlay in the viewport shelf before export."
        )
        self.terrainHintLabel.setObjectName("mapStudioTerrainHintLabel")
        self.terrainHintLabel.setWordWrap(True)
        self.terrainBrushStatusLabel = QtWidgets.QLabel(
            "Choose a brush here or from the viewport shelf. Each mouse drag is one undoable terrain stroke."
        )
        self.terrainBrushStatusLabel.setObjectName("mapStudioTerrainBrushStatusLabel")
        self.terrainBrushStatusLabel.setWordWrap(True)
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
        self.carveTerrainHoleButton = QtWidgets.QPushButton("Carve Hole")
        self.carveTerrainHoleButton.setObjectName("mapStudioCarveTerrainHoleButton")
        self.carveTerrainHoleButton.setToolTip(
            "Remove the floor cells around Row/Column (Radius in cells). Holed cells emit no render or WOK faces; the exported walkmesh perimeter gains an interior loop."
        )
        self.fillTerrainHoleButton = QtWidgets.QPushButton("Fill Hole")
        self.fillTerrainHoleButton.setObjectName("mapStudioFillTerrainHoleButton")
        self.fillTerrainHoleButton.setToolTip("Restore previously carved floor cells around Row/Column (Radius in cells).")
        self.applyTerrainBrushButton = QtWidgets.QPushButton("Apply Sculpt Brush")
        self.applyTerrainBrushButton.setObjectName("mapStudioApplyTerrainBrushButton")
        self.checkLiveTerrainBrushFrameButton = QtWidgets.QPushButton("Check Live Brush Frame")
        self.checkLiveTerrainBrushFrameButton.setObjectName("mapStudioCheckLiveTerrainBrushFrameButton")
        self.applyTerrainShapeButton = QtWidgets.QPushButton("Apply Terrain Shape")
        self.applyTerrainShapeButton.setObjectName("mapStudioApplyTerrainShapePresetButton")
        terrain_layout.addWidget(self.terrainWorkflowLabel)
        terrain_layout.addWidget(self.createTerrainSurfaceButton)
        terrain_brush_form = QtWidgets.QFormLayout()
        terrain_brush_form.addRow("Terrain:", self.terrainRoomComboBox)
        terrain_brush_form.addRow("Brush:", self.terrainBrushComboBox)
        terrain_brush_form.addRow("Brush size:", self.terrainRadiusSpinBox)
        terrain_brush_form.addRow("Falloff hardness:", self.terrainHardnessSpinBox)
        terrain_brush_form.addRow("Strength:", self.terrainSmoothStrengthSpinBox)
        terrain_brush_form.addRow("Height change:", self.terrainDeltaSpinBox)
        terrain_brush_form.addRow(self.terrainSculptEnabledCheckBox)
        terrain_layout.addLayout(terrain_brush_form)
        terrain_layout.addWidget(self.terrainHintLabel)
        terrain_layout.addWidget(self.terrainBrushStatusLabel)

        self.terrainAdvancedToggle = QtWidgets.QToolButton(terrain_box)
        self.terrainAdvancedToggle.setObjectName("mapStudioTerrainAdvancedToolsButton")
        self.terrainAdvancedToggle.setText("Advanced heightfield tools")
        self.terrainAdvancedToggle.setCheckable(True)
        self.terrainAdvancedToggle.setChecked(False)
        self.terrainAdvancedToggle.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.terrainAdvancedToggle.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        terrain_layout.addWidget(self.terrainAdvancedToggle)
        self.terrainAdvancedWidget = QtWidgets.QWidget(terrain_box)
        self.terrainAdvancedWidget.setObjectName("mapStudioTerrainAdvancedTools")
        terrain_advanced_form = QtWidgets.QFormLayout(self.terrainAdvancedWidget)
        terrain_advanced_form.setContentsMargins(0, 0, 0, 0)
        terrain_advanced_form.addRow("Shape:", self.terrainShapePresetComboBox)
        terrain_advanced_form.addRow("Shape height:", self.terrainShapeHeightSpinBox)
        terrain_advanced_form.addRow("Row:", self.terrainRowSpinBox)
        terrain_advanced_form.addRow("Column:", self.terrainColumnSpinBox)
        terrain_advanced_form.addRow("Exact height:", self.terrainHeightSpinBox)
        terrain_advanced_form.addRow("Smooth passes:", self.terrainSmoothIterationsSpinBox)
        terrain_advanced_form.addRow(self.checkLiveTerrainBrushFrameButton)
        terrain_advanced_form.addRow(self.applyTerrainBrushButton)
        terrain_advanced_form.addRow(self.setTerrainHeightButton)
        terrain_advanced_form.addRow(self.raiseTerrainButton)
        terrain_advanced_form.addRow(self.lowerTerrainButton)
        terrain_advanced_form.addRow(self.smoothTerrainButton)
        terrain_advanced_form.addRow(self.flattenTerrainButton)
        terrain_advanced_form.addRow(self.carveTerrainHoleButton)
        terrain_advanced_form.addRow(self.fillTerrainHoleButton)
        terrain_advanced_form.addRow(self.applyTerrainShapeButton)
        self.terrainAdvancedWidget.setVisible(False)
        terrain_layout.addWidget(self.terrainAdvancedWidget)
        self._terrainBuildingLayout.insertWidget(self._terrainBuildingLayout.count() - 1, terrain_box)

        terrain_dressing_box = QtWidgets.QGroupBox("Terrain Dressing and Surface Painting")
        terrain_dressing_box.setObjectName("mapStudioTerrainDressingGroup")
        terrain_dressing_layout = QtWidgets.QVBoxLayout(terrain_dressing_box)
        terrain_dressing_hint = QtWidgets.QLabel(
            "Drag rocks, foliage, and other placeables from the Content Browser onto the terrain; they floor-snap at the drop point. Paintable planes and terrain textures use Surface Painting."
        )
        terrain_dressing_hint.setObjectName("mapStudioTerrainDressingHint")
        terrain_dressing_hint.setWordWrap(True)
        self.browseTerrainDressingButton = QtWidgets.QPushButton("Browse Rocks & Foliage...")
        self.browseTerrainDressingButton.setObjectName("mapStudioBrowseTerrainDressingButton")
        self.openTerrainPaintingButton = QtWidgets.QPushButton("Open Surface Painting")
        self.openTerrainPaintingButton.setObjectName("mapStudioOpenTerrainPaintingButton")
        terrain_dressing_layout.addWidget(terrain_dressing_hint)
        terrain_dressing_layout.addWidget(self.browseTerrainDressingButton)
        terrain_dressing_layout.addWidget(self.openTerrainPaintingButton)
        self._terrainBuildingLayout.insertWidget(self._terrainBuildingLayout.count() - 1, terrain_dressing_box)
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
        self._roomAdvancedLayout.addWidget(union_box)
        bridge_box = QtWidgets.QGroupBox("Bridge Floor-Plan Edges")
        bridge_layout = QtWidgets.QFormLayout(bridge_box)
        self.floorPlanBridgeFirstRoomComboBox = QtWidgets.QComboBox()
        self.floorPlanBridgeFirstRoomComboBox.setObjectName("mapStudioFloorPlanBridgeFirstRoomComboBox")
        self.floorPlanBridgeFirstEdgeSpinBox = QtWidgets.QSpinBox()
        self.floorPlanBridgeFirstEdgeSpinBox.setObjectName("mapStudioFloorPlanBridgeFirstEdgeSpinBox")
        self.floorPlanBridgeFirstEdgeSpinBox.setRange(0, 999)
        self.floorPlanBridgeSecondRoomComboBox = QtWidgets.QComboBox()
        self.floorPlanBridgeSecondRoomComboBox.setObjectName("mapStudioFloorPlanBridgeSecondRoomComboBox")
        self.floorPlanBridgeSecondEdgeSpinBox = QtWidgets.QSpinBox()
        self.floorPlanBridgeSecondEdgeSpinBox.setObjectName("mapStudioFloorPlanBridgeSecondEdgeSpinBox")
        self.floorPlanBridgeSecondEdgeSpinBox.setRange(0, 999)
        self.floorPlanBridgeResultRoomLineEdit = QtWidgets.QLineEdit()
        self.floorPlanBridgeResultRoomLineEdit.setObjectName("mapStudioFloorPlanBridgeResultRoomLineEdit")
        self.floorPlanBridgeResultRoomLineEdit.setPlaceholderText("optional connector room resref")
        self.floorPlanBridgeHintLabel = QtWidgets.QLabel(
            "Bridge creates a new connector room between two compatible floor-plan edges. Use it for corridors, room seams, and simple KOTOR-safe connections."
        )
        self.floorPlanBridgeHintLabel.setObjectName("mapStudioFloorPlanBridgeHintLabel")
        self.floorPlanBridgeHintLabel.setWordWrap(True)
        self.bridgeFloorPlanEdgesButton = QtWidgets.QPushButton("Bridge Floor-Plan Edges")
        self.bridgeFloorPlanEdgesButton.setObjectName("mapStudioBridgeFloorPlanEdgesButton")
        bridge_layout.addRow("First room:", self.floorPlanBridgeFirstRoomComboBox)
        bridge_layout.addRow("First edge:", self.floorPlanBridgeFirstEdgeSpinBox)
        bridge_layout.addRow("Second room:", self.floorPlanBridgeSecondRoomComboBox)
        bridge_layout.addRow("Second edge:", self.floorPlanBridgeSecondEdgeSpinBox)
        bridge_layout.addRow("Connector:", self.floorPlanBridgeResultRoomLineEdit)
        bridge_layout.addRow(self.floorPlanBridgeHintLabel)
        bridge_layout.addRow(self.bridgeFloorPlanEdgesButton)
        self._roomAdvancedLayout.addWidget(bridge_box)
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
        self._roomAdvancedLayout.addWidget(add_primitive_box)
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
        self.roomPrimitiveSeparateResultLineEdit = QtWidgets.QLineEdit()
        self.roomPrimitiveSeparateResultLineEdit.setObjectName("mapStudioSeparatePrimitiveResultRoomLineEdit")
        self.roomPrimitiveSeparateResultLineEdit.setPlaceholderText("optional extracted export-room resref")
        self.separatePrimitiveButton = QtWidgets.QPushButton("Extract to Export Room")
        self.separatePrimitiveButton.setToolTip(
            "Move the selected authored primitive into a separate KOTOR room/export boundary. "
            "This is not polygon Separate Shells; use the Modeling > Separate Shells command for that."
        )
        self.separatePrimitiveButton.setObjectName("mapStudioSeparateCompositionPrimitiveButton")
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
        transform_layout.addRow("Extract as:", self.roomPrimitiveSeparateResultLineEdit)
        transform_layout.addRow(self.separatePrimitiveButton)
        transform_layout.addRow(self.removePrimitiveButton)
        self._roomAdvancedLayout.addWidget(transform_box)
        duplicate_box = QtWidgets.QGroupBox("Duplicate Special")
        duplicate_layout = QtWidgets.QFormLayout(duplicate_box)
        self.duplicateSpecialHintLabel = QtWidgets.QLabel(
            "Repeat the selected primitive with per-copy move, rotate, and scale offsets."
        )
        self.duplicateSpecialHintLabel.setObjectName("mapStudioDuplicateSpecialHintLabel")
        self.duplicateSpecialHintLabel.setWordWrap(True)
        self.duplicateSpecialCountSpinBox = QtWidgets.QSpinBox()
        self.duplicateSpecialCountSpinBox.setObjectName("mapStudioDuplicateSpecialCountSpinBox")
        self.duplicateSpecialCountSpinBox.setRange(1, 64)
        self.duplicateSpecialCountSpinBox.setValue(1)
        self.duplicateSpecialOffsetXSpinBox = self._make_transform_spin(
            "mapStudioDuplicateSpecialOffsetXSpinBox",
            -1000.0,
            1000.0,
            " m",
            value=1.0,
        )
        self.duplicateSpecialOffsetYSpinBox = self._make_transform_spin(
            "mapStudioDuplicateSpecialOffsetYSpinBox",
            -1000.0,
            1000.0,
            " m",
        )
        self.duplicateSpecialOffsetZSpinBox = self._make_transform_spin(
            "mapStudioDuplicateSpecialOffsetZSpinBox",
            -1000.0,
            1000.0,
            " m",
        )
        self.duplicateSpecialRotationZSpinBox = self._make_transform_spin(
            "mapStudioDuplicateSpecialRotationZSpinBox",
            -360.0,
            360.0,
            " deg",
            decimals=1,
            step=15.0,
        )
        self.duplicateSpecialScaleXSpinBox = self._make_transform_spin(
            "mapStudioDuplicateSpecialScaleXSpinBox",
            0.01,
            100.0,
            "",
            value=1.0,
        )
        self.duplicateSpecialScaleYSpinBox = self._make_transform_spin(
            "mapStudioDuplicateSpecialScaleYSpinBox",
            0.01,
            100.0,
            "",
            value=1.0,
        )
        self.duplicateSpecialScaleZSpinBox = self._make_transform_spin(
            "mapStudioDuplicateSpecialScaleZSpinBox",
            0.01,
            100.0,
            "",
            value=1.0,
        )
        duplicate_layout.addRow(self.duplicateSpecialHintLabel)
        duplicate_layout.addRow("Copies:", self.duplicateSpecialCountSpinBox)
        duplicate_layout.addRow("Offset X:", self.duplicateSpecialOffsetXSpinBox)
        duplicate_layout.addRow("Offset Y:", self.duplicateSpecialOffsetYSpinBox)
        duplicate_layout.addRow("Offset Z:", self.duplicateSpecialOffsetZSpinBox)
        duplicate_layout.addRow("Rotate Z:", self.duplicateSpecialRotationZSpinBox)
        duplicate_layout.addRow("Scale X:", self.duplicateSpecialScaleXSpinBox)
        duplicate_layout.addRow("Scale Y:", self.duplicateSpecialScaleYSpinBox)
        duplicate_layout.addRow("Scale Z:", self.duplicateSpecialScaleZSpinBox)
        self._roomAdvancedLayout.addWidget(duplicate_box)
        dimensions_box = QtWidgets.QGroupBox("Primitive Construction History")
        dimensions_box.setObjectName("mapStudioPrimitiveConstructionHistoryGroupBox")
        dimensions_layout = QtWidgets.QFormLayout(dimensions_box)
        self.primitiveDimensionHintLabel = QtWidgets.QLabel("Select an authored primitive to edit its dimensions.")
        self.primitiveDimensionHintLabel.setObjectName("mapStudioPrimitiveDimensionHintLabel")
        self.primitiveDimensionHintLabel.setWordWrap(True)
        dimensions_layout.addRow(self.primitiveDimensionHintLabel)
        self.primitivePropertyRowsWidget = QtWidgets.QWidget()
        self.primitivePropertyRowsWidget.setObjectName("mapStudioPrimitivePropertyRowsWidget")
        self.primitivePropertyRowsLayout = QtWidgets.QFormLayout(self.primitivePropertyRowsWidget)
        self.primitivePropertyRowsLayout.setContentsMargins(0, 0, 0, 0)
        dimensions_layout.addRow(self.primitivePropertyRowsWidget)
        self._primitive_property_controls: list[dict[str, object]] = []
        # Kept as a public-ish compatibility surface for older UI contracts. The
        # rows are now allocated from the selected generator schema, not capped.
        self._primitive_dimension_controls: list[tuple[QtWidgets.QLabel, QtWidgets.QWidget]] = []
        self._primitive_property_baseline: dict[str, object] = {}
        self._primitive_preview_identity: tuple[str, str] | None = None
        self._primitive_property_preview_timer = QtCore.QTimer(self)
        self._primitive_property_preview_timer.setSingleShot(True)
        self._primitive_property_preview_timer.setInterval(45)
        self._primitive_property_preview_timer.timeout.connect(self._emit_primitive_dimensions_preview)
        self.applyPrimitiveDimensionsButton = QtWidgets.QPushButton("Apply Topology Properties")
        self.applyPrimitiveDimensionsButton.setObjectName("mapStudioApplyPrimitiveDimensionsButton")
        self.applyPrimitiveDimensionsButton.setToolTip(
            "Commit all edited construction inputs as one topology rebuild and one undo step."
        )
        self.resetPrimitiveDimensionsButton = QtWidgets.QPushButton("Reset Defaults")
        self.resetPrimitiveDimensionsButton.setObjectName("mapStudioResetPrimitiveDimensionsButton")
        self.resetPrimitiveDimensionsButton.setToolTip("Restore generator defaults without committing them.")
        self.cancelPrimitiveDimensionsButton = QtWidgets.QPushButton("Cancel Changes")
        self.cancelPrimitiveDimensionsButton.setObjectName("mapStudioCancelPrimitiveDimensionsButton")
        self.cancelPrimitiveDimensionsButton.setToolTip("Discard unapplied construction-input changes (Esc).")
        primitive_property_buttons = QtWidgets.QWidget()
        primitive_property_buttons.setObjectName("mapStudioPrimitivePropertyButtonsWidget")
        primitive_property_buttons_layout = QtWidgets.QGridLayout(primitive_property_buttons)
        primitive_property_buttons_layout.setContentsMargins(0, 0, 0, 0)
        primitive_property_buttons_layout.addWidget(self.resetPrimitiveDimensionsButton, 0, 0)
        primitive_property_buttons_layout.addWidget(self.cancelPrimitiveDimensionsButton, 0, 1)
        primitive_property_buttons_layout.addWidget(self.applyPrimitiveDimensionsButton, 1, 0, 1, 2)
        primitive_property_buttons_layout.setColumnStretch(0, 1)
        primitive_property_buttons_layout.setColumnStretch(1, 1)
        dimensions_layout.addRow(primitive_property_buttons)
        self.cancelPrimitivePropertiesShortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Escape),
            dimensions_box,
        )
        self.cancelPrimitivePropertiesShortcut.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.cancelPrimitivePropertiesShortcut.setEnabled(False)
        self._roomAdvancedLayout.addWidget(dimensions_box)
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
        self._roomAdvancedLayout.addWidget(primitive_style_box)
        style_box = QtWidgets.QGroupBox("Room Material + Walkmesh")
        style_layout = QtWidgets.QFormLayout(style_box)
        self.roomTextureLineEdit = QtWidgets.QLineEdit("ruler01")
        self.roomTextureLineEdit.setObjectName("mapStudioRoomTextureLineEdit")
        self.roomTextureLineEdit.setPlaceholderText("KOTOR diffuse texture resref, e.g. ruler01")
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
        self._roomAdvancedLayout.addWidget(style_box)
        curve_box = QtWidgets.QGroupBox("Construction Curve Guide")
        curve_layout = QtWidgets.QFormLayout(curve_box)
        self.curveGuideHintLabel = QtWidgets.QLabel(
            "Add a guide curve for paths, terrain ridges, roads, placement arcs, or future PTH planning. Points are stored in KMAP world space."
        )
        self.curveGuideHintLabel.setObjectName("mapStudioCurveGuideHintLabel")
        self.curveGuideHintLabel.setWordWrap(True)
        self.curveGuideNameLineEdit = QtWidgets.QLineEdit("main_path")
        self.curveGuideNameLineEdit.setObjectName("mapStudioCurveGuideNameLineEdit")
        self.curveGuideNameLineEdit.setPlaceholderText("stable guide name")
        self.curveGuidePurposeComboBox = QtWidgets.QComboBox()
        self.curveGuidePurposeComboBox.setObjectName("mapStudioCurveGuidePurposeComboBox")
        self.curveGuidePurposeComboBox.addItem("Path Guide", "path_guide")
        self.curveGuidePurposeComboBox.addItem("PTH Planning", "pth_planning")
        self.curveGuidePurposeComboBox.addItem("Terrain Ridge", "terrain_ridge")
        self.curveGuidePurposeComboBox.addItem("Road Centerline", "road_centerline")
        self.curveGuidePurposeComboBox.addItem("Placement Arc", "placement_arc")
        self.curveGuidePoint1XSpinBox = self._make_transform_spin("mapStudioCurveGuidePoint1XSpinBox", -1000.0, 1000.0, " m")
        self.curveGuidePoint1YSpinBox = self._make_transform_spin("mapStudioCurveGuidePoint1YSpinBox", -1000.0, 1000.0, " m")
        self.curveGuidePoint1ZSpinBox = self._make_transform_spin("mapStudioCurveGuidePoint1ZSpinBox", -1000.0, 1000.0, " m")
        self.curveGuidePoint2XSpinBox = self._make_transform_spin("mapStudioCurveGuidePoint2XSpinBox", -1000.0, 1000.0, " m", value=1.0)
        self.curveGuidePoint2YSpinBox = self._make_transform_spin("mapStudioCurveGuidePoint2YSpinBox", -1000.0, 1000.0, " m", value=0.5)
        self.curveGuidePoint2ZSpinBox = self._make_transform_spin("mapStudioCurveGuidePoint2ZSpinBox", -1000.0, 1000.0, " m")
        self.curveGuidePoint3XSpinBox = self._make_transform_spin("mapStudioCurveGuidePoint3XSpinBox", -1000.0, 1000.0, " m", value=2.0)
        self.curveGuidePoint3YSpinBox = self._make_transform_spin("mapStudioCurveGuidePoint3YSpinBox", -1000.0, 1000.0, " m", value=0.5)
        self.curveGuidePoint3ZSpinBox = self._make_transform_spin("mapStudioCurveGuidePoint3ZSpinBox", -1000.0, 1000.0, " m")
        curve_layout.addRow(self.curveGuideHintLabel)
        curve_layout.addRow("Name:", self.curveGuideNameLineEdit)
        curve_layout.addRow("Purpose:", self.curveGuidePurposeComboBox)
        curve_layout.addRow("P1 X:", self.curveGuidePoint1XSpinBox)
        curve_layout.addRow("P1 Y:", self.curveGuidePoint1YSpinBox)
        curve_layout.addRow("P1 Z:", self.curveGuidePoint1ZSpinBox)
        curve_layout.addRow("P2 X:", self.curveGuidePoint2XSpinBox)
        curve_layout.addRow("P2 Y:", self.curveGuidePoint2YSpinBox)
        curve_layout.addRow("P2 Z:", self.curveGuidePoint2ZSpinBox)
        curve_layout.addRow("P3 X:", self.curveGuidePoint3XSpinBox)
        curve_layout.addRow("P3 Y:", self.curveGuidePoint3YSpinBox)
        curve_layout.addRow("P3 Z:", self.curveGuidePoint3ZSpinBox)
        self._roomAdvancedLayout.addWidget(curve_box)
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
        self.roomLightingGroup = light_box
        self._legacyToolsLayout.addWidget(light_box)
        entry_box = QtWidgets.QGroupBox("Module Entry Point")
        entry_layout = QtWidgets.QFormLayout(entry_box)
        self.entryPointGuideLabel = QtWidgets.QLabel(
            "Player start: choose the area resref and position/facing written to the module IFO. "
            "Keep it inside the current room on walkable WOK before staging or game proof."
        )
        self.entryPointGuideLabel.setObjectName("mapStudioEntryPointGuideLabel")
        self.entryPointGuideLabel.setWordWrap(True)
        self.entryPointAreaLineEdit = QtWidgets.QLineEdit()
        self.entryPointAreaLineEdit.setObjectName("mapStudioEntryPointAreaLineEdit")
        self.entryPointAreaLineEdit.setPlaceholderText("area resref, usually the module root")
        self.entryPointPosXSpinBox = self._make_transform_spin("mapStudioEntryPointPosXSpinBox", -1000.0, 1000.0, " m")
        self.entryPointPosYSpinBox = self._make_transform_spin("mapStudioEntryPointPosYSpinBox", -1000.0, 1000.0, " m")
        self.entryPointPosZSpinBox = self._make_transform_spin("mapStudioEntryPointPosZSpinBox", -1000.0, 1000.0, " m")
        self.entryPointFacingSpinBox = self._make_transform_spin("mapStudioEntryPointFacingSpinBox", -360.0, 360.0, " deg", decimals=1, step=15.0)
        self.entryPointStatusLabel = QtWidgets.QLabel("Entry point: create or load an authored module first.")
        self.entryPointStatusLabel.setObjectName("mapStudioEntryPointStatusLabel")
        self.entryPointStatusLabel.setWordWrap(True)
        self.applyEntryPointButton = QtWidgets.QPushButton("Apply Module Entry Point")
        self.applyEntryPointButton.setObjectName("mapStudioApplyEntryPointButton")
        entry_layout.addRow(self.entryPointGuideLabel)
        entry_layout.addRow("Area:", self.entryPointAreaLineEdit)
        entry_layout.addRow("Pos X:", self.entryPointPosXSpinBox)
        entry_layout.addRow("Pos Y:", self.entryPointPosYSpinBox)
        entry_layout.addRow("Pos Z:", self.entryPointPosZSpinBox)
        entry_layout.addRow("Facing:", self.entryPointFacingSpinBox)
        entry_layout.addRow(self.entryPointStatusLabel)
        entry_layout.addRow(self.applyEntryPointButton)
        self._legacyToolsLayout.addWidget(entry_box)
        placement_box = QtWidgets.QGroupBox("Gameplay Placement")
        placement_layout = QtWidgets.QFormLayout(placement_box)
        self.gameplayPlacementKindComboBox = QtWidgets.QComboBox()
        self.gameplayPlacementKindComboBox.setObjectName("mapStudioGameplayPlacementKindComboBox")
        self.gameplaySupportedKindsLabel = QtWidgets.QLabel("Placement types: loading KOTOR resource kinds.")
        self.gameplaySupportedKindsLabel.setObjectName("mapStudioGameplaySupportedKindsLabel")
        self.gameplaySupportedKindsLabel.setWordWrap(True)
        self.gameplayKindDetailLabel = QtWidgets.QLabel("Choose a KOTOR resource kind to see how it exports.")
        self.gameplayKindDetailLabel.setObjectName("mapStudioGameplayKindDetailLabel")
        self.gameplayKindDetailLabel.setWordWrap(True)
        self.gameplayTemplateLineEdit = QtWidgets.QLineEdit("plc_bench")
        self.gameplayTemplateLineEdit.setObjectName("mapStudioGameplayTemplateLineEdit")
        self.gameplayTemplateLineEdit.setPlaceholderText("template resref, e.g. plc_bench or c_drdmkone")
        self.gameplayPaletteSearchLineEdit = QtWidgets.QLineEdit()
        self.gameplayPaletteSearchLineEdit.setObjectName("mapStudioGameplayPaletteSearchLineEdit")
        self.gameplayPaletteSearchLineEdit.setPlaceholderText("Search game-library templates or models")
        self.gameplayPaletteResultLabel = QtWidgets.QLabel()
        self.gameplayPaletteResultLabel.setObjectName("mapStudioGameplayPaletteResultLabel")
        self.gameplayPaletteResultLabel.setWordWrap(True)
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
        placement_layout.addRow(self.gameplaySupportedKindsLabel)
        placement_layout.addRow("Kind:", self.gameplayPlacementKindComboBox)
        placement_layout.addRow(self.gameplayKindDetailLabel)
        placement_layout.addRow("Search:", self.gameplayPaletteSearchLineEdit)
        placement_layout.addRow(self.gameplayPaletteResultLabel)
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
        self._legacyToolsLayout.addWidget(placement_box)
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
        self.editScriptHookButton = QtWidgets.QPushButton("Edit Script…")
        self.editScriptHookButton.setObjectName("mapStudioEditScriptHookButton")
        self.editScriptHookButton.setToolTip(
            "Open this ARE/IFO hook in GhostStudio's Scripting Suite."
        )
        script_layout.addRow("Scope:", self.scriptHookScopeComboBox)
        script_layout.addRow("Field:", self.scriptHookFieldComboBox)
        script_layout.addRow("Script:", self.scriptHookResrefLineEdit)
        script_layout.addRow(self.scriptHookHintLabel)
        script_layout.addRow(self.assignScriptHookButton)
        script_layout.addRow(self.clearScriptHookButton)
        script_layout.addRow(self.editScriptHookButton)
        self.scriptHooksGroup = script_box
        self._legacyToolsLayout.addWidget(script_box)
        for label in self.ACTIONS:
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self.actionRequested.emit(text))
            self._legacyToolsLayout.addWidget(button)
        self.note = QtWidgets.QLabel("KOTOR archive writing is experimental; preview manifests are generated first.")
        self.note.setWordWrap(True)
        self._legacyToolsLayout.addWidget(self.note)
        self.roomAdvancedToggle.toggled.connect(
            lambda visible: self._set_advanced_container_visible(
                self.roomAdvancedToggle, self._roomAdvancedContainer, visible
            )
        )
        self.terrainAdvancedToggle.toggled.connect(
            lambda visible: self._set_advanced_container_visible(
                self.terrainAdvancedToggle, self.terrainAdvancedWidget, visible
            )
        )
        self.buildSectionTabs.currentChanged.connect(self._emit_build_section_changed)
        self.createTerrainSurfaceButton.clicked.connect(lambda _checked=False: self.terrainCreateRequested.emit())
        self.browseTerrainDressingButton.clicked.connect(lambda _checked=False: self.terrainDressingRequested.emit())
        self.openTerrainPaintingButton.clicked.connect(lambda _checked=False: self.terrainPaintRequested.emit())
        self.snapRoomsAtDoorwayButton.clicked.connect(lambda _checked=False: self.snapRoomsAtDoorwayRequested.emit())
        self.snapRoomsToGridButton.clicked.connect(lambda _checked=False: self.snapRoomsToGridRequested.emit())
        for key, button in self.buildingToolButtons.items():
            button.clicked.connect(lambda _checked=False, tool=key: self._emit_building_tool(tool))
        self.addBuildingLevelButton.clicked.connect(self._add_building_level)
        self.buildingLevelComboBox.currentIndexChanged.connect(self._on_building_level_changed)
        self.buildingLevelViewComboBox.currentIndexChanged.connect(self._emit_building_level_view)
        self.buildingExplodedGapSpinBox.valueChanged.connect(self._emit_building_level_view)
        self.buildingKindComboBox.currentIndexChanged.connect(self._on_building_kind_changed)
        self.buildingStyleComboBox.currentIndexChanged.connect(self._on_building_style_changed)
        self.buildingArchetypeComboBox.currentIndexChanged.connect(self._on_building_style_changed)
        self.buildingRoofTypeComboBox.currentIndexChanged.connect(self._update_building_roof_controls)
        for control in (
            self.buildingStyleComboBox,
            self.buildingArchetypeComboBox,
            self.buildingWallHeightSpinBox,
            self.buildingFloorZSpinBox,
            self.buildingFloorToFloorSpinBox,
            self.buildingGridSizeSpinBox,
            self.buildingSnapCheckBox,
            self.buildingCeilingCheckBox,
            self.buildingRoofTypeComboBox,
            self.buildingRoofPitchSpinBox,
            self.buildingRoofOverhangSpinBox,
            self.buildingOpeningWidthSpinBox,
            self.buildingOpeningHeightSpinBox,
            self.buildingWindowHeightSpinBox,
            self.buildingWindowSillSpinBox,
        ):
            signal = getattr(control, "valueChanged", None) or getattr(control, "currentIndexChanged", None) or getattr(control, "toggled", None)
            if signal is not None:
                signal.connect(lambda _value=None: self._emit_building_settings())
        self.roomPrimitivePresetComboBox.currentIndexChanged.connect(self._update_preset_description)
        self.componentModeComboBox.currentIndexChanged.connect(self._update_modeling_tool_hint)
        self.modelingToolComboBox.currentIndexChanged.connect(self._update_modeling_tool_hint)
        self.snapModeComboBox.currentIndexChanged.connect(self._update_modeling_tool_hint)
        self.createPrimitiveButton.clicked.connect(self._emit_primitive_preset)
        self.roomOperationComboBox.currentIndexChanged.connect(self._update_operation_controls)
        self.applyRoomOperationButton.clicked.connect(self._emit_room_operation)
        self.floorPlanExtrusionRoomComboBox.currentIndexChanged.connect(self._update_floor_plan_extrusion_controls)
        self.floorPlanWallHeightSpinBox.valueChanged.connect(lambda _value: self._update_floor_plan_extrusion_hint())
        self.floorPlanFloorZSpinBox.valueChanged.connect(lambda _value: self._update_floor_plan_extrusion_hint())
        self.floorPlanIncludeWallsCheckBox.stateChanged.connect(lambda _value: self._update_floor_plan_extrusion_hint())
        self.floorPlanSurfaceComboBox.currentIndexChanged.connect(self._update_floor_plan_extrusion_hint)
        self.applyFloorPlanExtrusionButton.clicked.connect(self._emit_floor_plan_extrusion)
        self.floorPlanOpeningRoomComboBox.currentIndexChanged.connect(self._update_floor_plan_opening_controls)
        self.applyFloorPlanOpeningButton.clicked.connect(self._emit_floor_plan_opening)
        self.floorPlanOpeningMarkerRoomComboBox.currentIndexChanged.connect(self._update_floor_plan_opening_marker_controls)
        self.floorPlanOpeningMarkerKindComboBox.currentIndexChanged.connect(self._update_floor_plan_opening_marker_controls)
        self.createFloorPlanOpeningMarkerButton.clicked.connect(self._emit_floor_plan_opening_marker)
        self.floorPlanVertexRoomComboBox.currentIndexChanged.connect(self._update_floor_plan_vertex_controls)
        self.floorPlanVertexTargetRoomComboBox.currentIndexChanged.connect(self._update_floor_plan_vertex_controls)
        self.floorPlanSourcePointSpinBox.valueChanged.connect(lambda _value=0: self._emit_floor_plan_vertex_snap_preview())
        self.floorPlanSelectedPointsLineEdit.textChanged.connect(self._update_floor_plan_vertex_controls)
        self.snapFloorPlanVertexButton.clicked.connect(self._emit_floor_plan_vertex_snap)
        self.weldFloorPlanVerticesButton.clicked.connect(self._emit_floor_plan_vertex_weld)
        self.flattenFloorPlanVerticesButton.clicked.connect(self._emit_floor_plan_vertex_flatten)
        self.mirrorFloorPlanVerticesButton.clicked.connect(self._emit_floor_plan_vertex_mirror)
        self.cleanupFloorPlanVerticesButton.clicked.connect(self._emit_floor_plan_vertex_cleanup)
        self.fillFloorPlanFaceButton.clicked.connect(self._emit_floor_plan_face_fill)
        self.splitFloorPlanFaceButton.clicked.connect(self._emit_floor_plan_face_split)
        self.triangulateFloorPlanFaceButton.clicked.connect(self._emit_floor_plan_face_triangulate)
        self.cleanupFloorPlanNormalsButton.clicked.connect(self._emit_floor_plan_normals_cleanup)
        self.terrainRoomComboBox.currentIndexChanged.connect(self._update_terrain_controls)
        self.terrainBrushComboBox.currentIndexChanged.connect(self._update_terrain_brush_controls)
        self.terrainShapePresetComboBox.currentIndexChanged.connect(self._update_terrain_shape_controls)
        self.setTerrainHeightButton.clicked.connect(lambda: self._emit_terrain_operation("set_height"))
        self.raiseTerrainButton.clicked.connect(lambda: self._emit_terrain_operation("raise"))
        self.lowerTerrainButton.clicked.connect(lambda: self._emit_terrain_operation("lower"))
        self.smoothTerrainButton.clicked.connect(lambda: self._emit_terrain_operation("smooth"))
        self.flattenTerrainButton.clicked.connect(lambda: self._emit_terrain_operation("flatten"))
        self.carveTerrainHoleButton.clicked.connect(lambda: self._emit_terrain_operation("carve_hole"))
        self.fillTerrainHoleButton.clicked.connect(lambda: self._emit_terrain_operation("fill_hole"))
        self.checkLiveTerrainBrushFrameButton.clicked.connect(self._emit_live_terrain_brush_frame)
        self.applyTerrainBrushButton.clicked.connect(self._emit_selected_terrain_brush)
        self.applyTerrainShapeButton.clicked.connect(self._emit_terrain_shape_preset)
        self.floorPlanUnionFirstRoomComboBox.currentIndexChanged.connect(self._update_rectangular_union_controls)
        self.floorPlanUnionSecondRoomComboBox.currentIndexChanged.connect(self._update_rectangular_union_controls)
        self.mapStudioApplyRectangularUnionButton.clicked.connect(self._emit_rectangular_union)
        self.floorPlanBridgeFirstRoomComboBox.currentIndexChanged.connect(self._update_floor_plan_bridge_controls)
        self.floorPlanBridgeSecondRoomComboBox.currentIndexChanged.connect(self._update_floor_plan_bridge_controls)
        self.floorPlanBridgeFirstEdgeSpinBox.valueChanged.connect(lambda _value: self._update_floor_plan_bridge_controls())
        self.floorPlanBridgeSecondEdgeSpinBox.valueChanged.connect(lambda _value: self._update_floor_plan_bridge_controls())
        self.bridgeFloorPlanEdgesButton.clicked.connect(self._emit_floor_plan_bridge)
        self.compositionPrimitiveKindComboBox.currentIndexChanged.connect(self._update_composition_primitive_kind_hint)
        self.addCompositionPrimitiveButton.clicked.connect(self._emit_add_composition_primitive)
        self.roomPrimitiveTransformComboBox.currentIndexChanged.connect(self._on_primitive_selection_changed)
        self.applyPrimitiveTransformButton.clicked.connect(self._emit_primitive_transform)
        self.applyPrimitiveDimensionsButton.clicked.connect(self._emit_primitive_dimensions)
        self.resetPrimitiveDimensionsButton.clicked.connect(self._reset_primitive_properties_to_defaults)
        self.cancelPrimitiveDimensionsButton.clicked.connect(self._cancel_primitive_property_changes)
        self.cancelPrimitivePropertiesShortcut.activated.connect(self._cancel_primitive_property_changes)
        self.primitiveSurfaceComboBox.currentIndexChanged.connect(self._update_primitive_surface_hint)
        self.applyPrimitiveStyleButton.clicked.connect(self._emit_primitive_style)
        self.removePrimitiveButton.clicked.connect(self._emit_remove_composition_primitive)
        self.separatePrimitiveButton.clicked.connect(self._emit_separate_composition_primitive)
        self.roomSurfaceComboBox.currentIndexChanged.connect(self._update_surface_hint)
        self.applyRoomStyleButton.clicked.connect(self._emit_room_style)
        self.addRoomLightButton.clicked.connect(self._emit_room_light)
        self.applyEntryPointButton.clicked.connect(self._emit_module_entry_point)
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
        self.editScriptHookButton.clicked.connect(self._emit_edit_script_hook)
        self._update_operation_controls()
        self._update_building_roof_controls()
        self._update_modeling_tool_hint()
        self.set_terrain_room_choices(())
        self.set_terrain_shape_presets(())
        self.set_floor_plan_room_choices(())
        self._update_floor_plan_extrusion_controls()
        self._update_floor_plan_vertex_controls()
        self._update_composition_primitive_kind_hint()
        self._update_primitive_transform_controls()
        self._update_primitive_dimension_controls()
        self._update_primitive_style_controls()
        self._update_surface_hint()
        self._update_script_hook_field_choices()
        self._update_gameplay_spatial_controls()
        self.set_module_entry_point(None)

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

    @staticmethod
    def _set_advanced_container_visible(
        toggle: QtWidgets.QToolButton,
        container: QtWidgets.QWidget,
        visible: bool,
    ) -> None:
        container.setVisible(bool(visible))
        toggle.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if visible else QtCore.Qt.ArrowType.RightArrow
        )

    def _emit_build_section_changed(self, index: int) -> None:
        keys = ("room", "terrain", "skybox")
        key = keys[index] if 0 <= int(index) < len(keys) else "room"
        self.buildSectionChanged.emit(key)

    def _building_settings(self) -> dict[str, object]:
        level = dict(self.buildingLevelComboBox.currentData() or {})
        style = dict(self.buildingStyleComboBox.currentData() or {})
        archetype = dict(self.buildingArchetypeComboBox.currentData() or {})
        return {
            "level_index": int(level.get("index", max(0, self.buildingLevelComboBox.currentIndex()))),
            "level_name": str(level.get("name") or self.buildingLevelComboBox.currentText().split(" (")[0]),
            "floor_z": float(self.buildingFloorZSpinBox.value()),
            "floor_to_floor_height": float(self.buildingFloorToFloorSpinBox.value()),
            "level_view_mode": str(self.buildingLevelViewComboBox.currentData() or "stacked"),
            "exploded_gap": float(self.buildingExplodedGapSpinBox.value()),
            "wall_height": float(self.buildingWallHeightSpinBox.value()),
            "grid_size": float(self.buildingGridSizeSpinBox.value()),
            "snap_to_grid": bool(self.buildingSnapCheckBox.isChecked()),
            "include_ceiling": bool(self.buildingCeilingCheckBox.isChecked()),
            "building_kind": str(self.buildingKindComboBox.currentData() or "interior"),
            "roof_type": str(self.buildingRoofTypeComboBox.currentData() or "none"),
            "roof_pitch_degrees": float(self.buildingRoofPitchSpinBox.value()),
            "roof_overhang": float(self.buildingRoofOverhangSpinBox.value()),
            "style_id": str(style.get("style_id") or "plcaa_graybox"),
            "architecture_archetype": str(archetype.get("archetype_id") or ""),
            "opening_width": float(self.buildingOpeningWidthSpinBox.value()),
            "opening_height": float(self.buildingOpeningHeightSpinBox.value()),
            "window_height": float(self.buildingWindowHeightSpinBox.value()),
            "window_sill": float(self.buildingWindowSillSpinBox.value()),
        }

    def _emit_building_settings(self) -> None:
        self.buildingSettingsChanged.emit(self._building_settings())

    def _emit_building_tool(self, tool: str) -> None:
        key = str(tool or "select").strip().lower()
        if key != "select" and str(self.buildingLevelViewComboBox.currentData() or "stacked") == "exploded":
            solo_index = self.buildingLevelViewComboBox.findData("solo")
            if solo_index >= 0:
                self.buildingLevelViewComboBox.setCurrentIndex(solo_index)
        self.buildingStatusLabel.setText(
            "Click successive floor points; click the first point to close and build the room. Esc cancels, Backspace removes the last point."
            if key == "walls"
            else "Click the wall where the opening should be placed."
            if key in {"door", "window"}
            else "Normal selection is active."
        )
        self.buildingToolChanged.emit(key)
        self._emit_building_settings()

    def _on_building_level_changed(self, _index: int = -1) -> None:
        level = dict(self.buildingLevelComboBox.currentData() or {})
        self.buildingFloorZSpinBox.blockSignals(True)
        self.buildingFloorZSpinBox.setValue(float(level.get("floor_z", 0.0) or 0.0))
        self.buildingFloorZSpinBox.blockSignals(False)
        self.buildingFloorToFloorSpinBox.blockSignals(True)
        self.buildingFloorToFloorSpinBox.setValue(float(level.get("floor_to_floor_height", 3.0) or 3.0))
        self.buildingFloorToFloorSpinBox.blockSignals(False)
        self._emit_building_settings()
        self._emit_building_level_view()

    def building_level_presentation(self) -> dict[str, object]:
        level = dict(self.buildingLevelComboBox.currentData() or {})
        return {
            "active_level_index": int(level.get("index", max(0, self.buildingLevelComboBox.currentIndex()))),
            "mode": str(self.buildingLevelViewComboBox.currentData() or "stacked"),
            "exploded_gap": float(self.buildingExplodedGapSpinBox.value()),
        }

    def _emit_building_level_view(self, _value: object = None) -> None:
        payload = self.building_level_presentation()
        mode = str(payload["mode"])
        active = int(payload["active_level_index"])
        self.buildingLevelViewChanged.emit(payload)
        if mode == "exploded":
            self.buildingStatusLabel.setText(
                "Exploded view is a temporary spacing preview; choosing a construction tool switches to Solo for exact editing."
            )
        elif mode == "solo":
            self.buildingStatusLabel.setText(f"Solo: editing Level {active + 1} at its true authored elevation.")

    def _apply_default_roof_for_kind(self, kind: str) -> None:
        roof_type = "hip" if str(kind or "").strip().lower() == "exterior" else "none"
        roof_index = self.buildingRoofTypeComboBox.findData(roof_type)
        if roof_index >= 0:
            self.buildingRoofTypeComboBox.blockSignals(True)
            self.buildingRoofTypeComboBox.setCurrentIndex(roof_index)
            self.buildingRoofTypeComboBox.blockSignals(False)
        self._update_building_roof_controls()

    def _update_building_roof_controls(self, _index: int = -1) -> None:
        pitched = str(self.buildingRoofTypeComboBox.currentData() or "none") in {"hip", "gable"}
        self.buildingRoofPitchSpinBox.setEnabled(pitched)
        self.buildingRoofOverhangSpinBox.setEnabled(pitched)

    def _on_building_kind_changed(self, index: int = -1) -> None:
        kind = str(self.buildingKindComboBox.itemData(index) if index >= 0 else self.buildingKindComboBox.currentData() or "")
        self._apply_default_roof_for_kind(kind)
        self._rebuild_building_style_choices(index)

    def _add_building_level(self) -> None:
        next_index = max(
            (int(dict(self.buildingLevelComboBox.itemData(index) or {}).get("index", index)) for index in range(self.buildingLevelComboBox.count())),
            default=-1,
        ) + 1
        floor_z = float(self.buildingFloorZSpinBox.value()) + float(self.buildingFloorToFloorSpinBox.value())
        name = f"Level {next_index + 1}"
        self.buildingLevelCreateRequested.emit(
            {
                "level_index": next_index,
                "name": name,
                "floor_z": floor_z,
                "floor_to_floor_height": float(self.buildingFloorToFloorSpinBox.value()),
            }
        )
        self.buildingStatusLabel.setText(f"Adding {name} at {floor_z:.2f} m…")

    def spatial_plan_overlay_enabled(self) -> bool:
        return bool(self.spatialDesignOverlayCheckBox.isChecked())

    def set_spatial_design_context(self, audit, placement_ledger) -> None:
        """Show the shared scene audit and exact placement ledger."""

        summary = str(getattr(audit, "summary", lambda: "")() or "")
        blocking = tuple(getattr(audit, "blocking_issues", ()) or ())
        warnings = tuple(getattr(audit, "warnings", ()) or ())
        if not summary:
            summary = "No spatial plan yet · define districts, routes, landmarks, and placement purpose."
        self.spatialDesignSummaryLabel.setText(summary)
        details = tuple(blocking) + tuple(warnings)
        self.spatialDesignSummaryLabel.setToolTip("\n".join(details) if details else summary)
        self.auditSpatialDesignButton.setText("Layout Ready" if bool(getattr(audit, "ok", False)) else "Audit Layout")
        self.spatialDesignLedger.clear()
        for row in tuple(placement_ledger or ()):
            values = dict(row or {})
            position = tuple(values.get("position") or (0.0, 0.0, 0.0))
            position_text = (
                f"{float(position[0]):.2f}, {float(position[1]):.2f}, {float(position[2]):.2f}"
            )
            item = QtWidgets.QTreeWidgetItem(
                (
                    str(values.get("label") or values.get("asset_ref") or ""),
                    position_text,
                    str(values.get("zone") or ""),
                    str(values.get("purpose") or ""),
                )
            )
            item.setToolTip(
                0,
                (
                    f"Asset: {str(values.get('asset_ref') or '')}\n"
                    f"Facing: {float(values.get('bearing') or 0.0):.2f} rad\n"
                    f"Why here: {str(values.get('rationale') or '')}"
                ),
            )
            if bool(values.get("landmark", False)):
                item.setText(0, f"★ {item.text(0)}")
            self.spatialDesignLedger.addTopLevelItem(item)
        header = self.spatialDesignLedger.header()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)

    def set_building_styles(self, styles) -> None:
        preserve = bool(self._buildingStyleRows)
        current = str(dict(self.buildingStyleComboBox.currentData() or {}).get("style_id", "")) if preserve else ""
        self._buildingStyleRows = [dict(style or {}) for style in tuple(styles or ())]
        self._lastAppliedBuildingStyleId = ""
        self._rebuild_building_style_choices(preferred_style_id=current)

    def _rebuild_building_archetype_choices(self, style: dict[str, object]) -> None:
        rows = [dict(row or {}) for row in tuple(style.get("architecture_archetypes") or ())]
        self.buildingArchetypeComboBox.blockSignals(True)
        self.buildingArchetypeComboBox.clear()
        for row in rows:
            archetype_id = str(row.get("archetype_id") or "")
            if not archetype_id:
                continue
            self.buildingArchetypeComboBox.addItem(
                str(row.get("label") or archetype_id.replace("_", " ").title()),
                row,
            )
            index = self.buildingArchetypeComboBox.count() - 1
            self.buildingArchetypeComboBox.setItemData(
                index,
                (
                    f"{str(row.get('description') or 'Measured room contour')}\n"
                    f"Contour: {str(row.get('shell_profile') or '').replace('_', ' ').title()} · "
                    f"height {float(row.get('recommended_wall_height_m') or 3.0):.2f} m · "
                    f"trained from {len(tuple(row.get('evidence_rooms') or ()))} retail room(s)"
                ),
                QtCore.Qt.ItemDataRole.ToolTipRole,
            )
        if self.buildingArchetypeComboBox.count() <= 0:
            self.buildingArchetypeComboBox.addItem(
                "Default room contour",
                {
                    "archetype_id": "",
                    "label": "Default room contour",
                    "shell_profile": str(style.get("architecture_shell_profile") or ""),
                    "recommended_wall_height_m": float(style.get("recommended_wall_height_m") or 3.0),
                    "recommended_floor_to_floor_m": float(
                        style.get("recommended_floor_to_floor_m")
                        or style.get("recommended_wall_height_m")
                        or 3.0
                    ),
                },
            )
        self.buildingArchetypeComboBox.setEnabled(bool(rows))
        self.buildingArchetypeComboBox.setCurrentIndex(0)
        self.buildingArchetypeComboBox.blockSignals(False)
        self._lastAppliedBuildingArchetypeKey = ""

    def _rebuild_building_style_choices(
        self,
        _index: int = -1,
        *,
        preferred_style_id: str = "",
    ) -> None:
        current = preferred_style_id or str(dict(self.buildingStyleComboBox.currentData() or {}).get("style_id", ""))
        wanted_kind = str(self.buildingKindComboBox.currentData() or "").lower()
        rows = [
            row for row in self._buildingStyleRows
            if not wanted_kind or str(row.get("environment_kind") or "both").lower() in {wanted_kind, "both"}
        ]
        rows.sort(
            key=lambda row: (
                0
                if str(row.get("architecture_profile") or "")
                else 1
                if str(row.get("style_id") or "") == "plcaa_graybox"
                else 2,
                1 if str(row.get("environment_kind") or "both").lower() == "both" else 0,
                str(row.get("world_label") or "").lower(),
                str(row.get("source_module") or "").lower(),
                str(row.get("label") or "").lower(),
            )
        )
        self.buildingStyleComboBox.blockSignals(True)
        self.buildingStyleComboBox.clear()
        for row in rows:
            style_id = str(row.get("style_id") or "")
            if style_id:
                self.buildingStyleComboBox.addItem(str(row.get("label") or style_id), row)
                item_index = self.buildingStyleComboBox.count() - 1
                self.buildingStyleComboBox.setItemData(
                    item_index,
                    (
                        f"{str(row.get('world_label') or 'Vanilla KOTOR')} · "
                        f"{str(row.get('environment_kind') or 'both').title()} · {str(row.get('source_module') or 'PLCaa')}\n"
                        + (
                            f"Geometry profile: {str(row.get('architecture_profile')).replace('_', ' ').title()} · "
                            f"trained from {len(tuple(row.get('evidence_rooms') or ()))} retail rooms\n"
                            if str(row.get("architecture_profile") or "")
                            else ""
                        )
                        + (
                            f"Structural contour: {str(row.get('architecture_shell_profile')).replace('_', ' ').title()}\n"
                            if str(row.get("architecture_shell_profile") or "")
                            else ""
                        )
                        + (
                            f"Measured wall height: {float(row.get('recommended_wall_height_m') or 3.0):.3f} m · "
                            f"floor-to-floor: {float(row.get('recommended_floor_to_floor_m') or 3.0):.3f} m\n"
                            f"Door opening: {float(row.get('recommended_door_width_m') or 1.25):.2f} × "
                            f"{float(row.get('recommended_door_height_m') or 2.2):.2f} m\n"
                            if str(row.get("architecture_profile") or "")
                            else ""
                        )
                        + f"Floor {str(row.get('floor_texture') or 'ruler01')} · "
                        f"Walls {str(row.get('wall_texture') or 'ruler01')} · "
                        f"Ceiling/Roof {str(row.get('ceiling_texture') or 'ruler01')}"
                    ),
                    QtCore.Qt.ItemDataRole.ToolTipRole,
                )
        if self.buildingStyleComboBox.count() <= 0:
            self.buildingStyleComboBox.addItem("PLCaa Neutral Blockout", {"style_id": "plcaa_graybox"})
        index = self.buildingStyleComboBox.findData(current, role=QtCore.Qt.ItemDataRole.UserRole)
        if index < 0:
            for candidate in range(self.buildingStyleComboBox.count()):
                if str(dict(self.buildingStyleComboBox.itemData(candidate) or {}).get("style_id", "")) == current:
                    index = candidate
                    break
        self.buildingStyleComboBox.setCurrentIndex(max(0, index))
        self.buildingStyleComboBox.blockSignals(False)
        self._on_building_style_changed()

    def select_building_style(self, style_id: str, environment_kind: str = "") -> bool:
        wanted = str(style_id or "").strip().lower()
        row = next(
            (candidate for candidate in self._buildingStyleRows if str(candidate.get("style_id") or "").lower() == wanted),
            None,
        )
        if row is None:
            return False
        kind = str(environment_kind or row.get("environment_kind") or "").lower()
        kind_index = self.buildingKindComboBox.findData(kind)
        if kind_index >= 0:
            self.buildingKindComboBox.blockSignals(True)
            self.buildingKindComboBox.setCurrentIndex(kind_index)
            self.buildingKindComboBox.blockSignals(False)
            self._apply_default_roof_for_kind(kind)
        self._rebuild_building_style_choices(preferred_style_id=wanted)
        return True

    def _on_building_style_changed(self, _index: int = -1) -> None:
        row = dict(self.buildingStyleComboBox.currentData() or {})
        style_id = str(row.get("style_id") or "plcaa_graybox")
        kind = str(row.get("environment_kind") or self.buildingKindComboBox.currentData() or "both")
        source = str(row.get("source_module") or "PLCaa")
        world = str(row.get("world_label") or "Neutral Blockout")
        kind_label = "Exterior" if kind == "exterior" else "Interior" if kind == "interior" else "Interior / Exterior"
        architecture_profile = str(row.get("architecture_profile") or "")
        if style_id != self._lastAppliedBuildingStyleId:
            self._lastAppliedBuildingStyleId = style_id
            self._rebuild_building_archetype_choices(row)
        archetype = dict(self.buildingArchetypeComboBox.currentData() or {})
        archetype_id = str(archetype.get("archetype_id") or "")
        archetype_label = str(archetype.get("label") or self.buildingArchetypeComboBox.currentText())
        shell_profile = str(archetype.get("shell_profile") or row.get("architecture_shell_profile") or "")
        archetype_key = f"{style_id}:{archetype_id}"
        if archetype_key != self._lastAppliedBuildingArchetypeKey:
            self._lastAppliedBuildingArchetypeKey = archetype_key
            recommended_wall = float(
                archetype.get("recommended_wall_height_m")
                or row.get("recommended_wall_height_m")
                or 3.0
            )
            recommended_floor = float(
                archetype.get("recommended_floor_to_floor_m")
                or row.get("recommended_floor_to_floor_m")
                or recommended_wall
            )
            self.buildingWallHeightSpinBox.setValue(recommended_wall)
            self.buildingFloorToFloorSpinBox.setValue(recommended_floor)
            self.buildingOpeningWidthSpinBox.setValue(float(row.get("recommended_door_width_m") or 1.25))
            self.buildingOpeningHeightSpinBox.setValue(float(row.get("recommended_door_height_m") or 2.2))
            if architecture_profile in {"shadowlands", "onderon_city", "onderon_sky_ramp"}:
                self.buildingCeilingCheckBox.setChecked(False)
                roof_index = self.buildingRoofTypeComboBox.findData("none")
                if roof_index >= 0:
                    self.buildingRoofTypeComboBox.setCurrentIndex(roof_index)
            elif architecture_profile in {"onderon_cantina", "onderon_palace"}:
                self.buildingCeilingCheckBox.setChecked(True)
                roof_index = self.buildingRoofTypeComboBox.findData("none")
                if roof_index >= 0:
                    self.buildingRoofTypeComboBox.setCurrentIndex(roof_index)
        self.buildingStyleSummaryLabel.setText(
            f"{world} · {kind_label} · {source}   |   "
            + (f"GEOMETRY KIT: {architecture_profile.replace('_', ' ').title()}   |   " if architecture_profile else "")
            + (f"ROOM SHAPE: {archetype_label}   |   " if archetype_id else "")
            + (f"CONTOUR: {shell_profile.replace('_', ' ').title()}   |   " if shell_profile else "")
            + (
                f"Measured height: {float(archetype.get('recommended_wall_height_m') or row.get('recommended_wall_height_m') or 3.0):.3f} m   |   "
                if architecture_profile
                else ""
            )
            + f"Floor: {str(row.get('floor_texture') or 'ruler01')}   "
            f"Walls: {str(row.get('wall_texture') or 'ruler01')}   "
            f"Ceiling/Roof: {str(row.get('ceiling_texture') or 'ruler01')}"
        )
        self.buildingStatusLabel.setText(
            (
                f"{world} organic terrain kit selected. Draw a clearing or path boundary; Ghost Studio builds irregular earth strata, ancient-root buttresses, and hanging vegetation from {source} evidence, while the terrain shelf exposes Upper and Lower Shadowlands pieces; "
                if architecture_profile == "shadowlands"
                else f"{world} open-city kit selected. Draw Room creates a roofless {archetype_label.lower()} with beveled Iziz wall sections; the matching shelf exposes complete vanilla buildings, street pieces, props, and magnet-ready rooms; "
                if architecture_profile in {"onderon_city", "onderon_sky_ramp"}
                else f"{world} interior kit selected. Draw Room creates a fully enclosed {archetype_label.lower()} with measured relief, trim, columns, and ceiling contour; the shelf exposes matching vanilla rooms and individual environment props; "
                if architecture_profile in {"onderon_cantina", "onderon_palace"}
                else f"{world} {archetype_label.lower()} selected. Draw Room sweeps the {shell_profile.replace('_', ' ')} contour, then adds measured bays, supports, relief, trims, and openings from {source} evidence; "
                if archetype_id
                else f"{world} architecture kit selected. Draw Room sweeps the {shell_profile.replace('_', ' ')} room contour, then adds bays, ribs, trims, and lights from {source} evidence; "
                if shell_profile
                else f"{world} architecture kit selected. Draw Room generates profiled bays, ribs, trims, and lights from {source} evidence; "
                if architecture_profile
                else f"{world} {kind_label.lower()} style selected. Draw Room uses the {source} palette; "
            )
            + (
                f"the closed footprint will include a {str(self.buildingRoofTypeComboBox.currentText()).lower()}."
                if str(self.buildingRoofTypeComboBox.currentData() or "none") != "none"
                else "the kit browser shows matching pieces."
            )
        )
        self.buildingStyleChanged.emit(style_id, kind)
        self._emit_building_settings()

    def set_building_levels(self, levels) -> None:
        current = int(dict(self.buildingLevelComboBox.currentData() or {}).get("index", 0))
        rows = tuple(levels or ())
        if not rows:
            return
        self.buildingLevelComboBox.blockSignals(True)
        self.buildingLevelComboBox.clear()
        selected = 0
        for offset, level in enumerate(rows):
            index = int(getattr(level, "level_index", offset))
            name = str(getattr(level, "name", "") or f"Level {index + 1}")
            floor_z = float(getattr(level, "floor_z", 0.0) or 0.0)
            floor_to_floor = float(getattr(level, "floor_to_floor_height", 3.0) or 3.0)
            room_count = len(tuple(getattr(level, "room_resrefs", ()) or ()))
            room_label = f" · {room_count} room{'s' if room_count != 1 else ''}" if room_count else " · empty"
            self.buildingLevelComboBox.addItem(
                f"{name} ({floor_z:.2f} m){room_label}",
                {
                    "index": index,
                    "name": name,
                    "floor_z": floor_z,
                    "floor_to_floor_height": floor_to_floor,
                    "room_count": room_count,
                },
            )
            if index == current:
                selected = offset
        self.buildingLevelComboBox.setCurrentIndex(selected)
        self.buildingLevelComboBox.blockSignals(False)
        self._on_building_level_changed(selected)

    def select_building_level(self, level_index: int) -> None:
        for offset in range(self.buildingLevelComboBox.count()):
            if int(dict(self.buildingLevelComboBox.itemData(offset) or {}).get("index", offset)) == int(level_index):
                self.buildingLevelComboBox.setCurrentIndex(offset)
                return

    def focus_build_section(self, section: str) -> None:
        """Show one of the three task-oriented Build sections."""

        index = {"room": 0, "terrain": 1, "skybox": 2}.get(str(section or "").strip().lower(), 0)
        self.buildSectionTabs.setCurrentIndex(index)

    def adopt_terrain_kit_browser(self, browser: QtWidgets.QWidget) -> None:
        """Place the terrain asset browser at the top of Terrain Building."""

        if browser is None:
            return
        browser.setParent(self.terrainBuildingPage)
        self._terrainBuildingLayout.insertWidget(0, browser, 1)

    def adopt_environment_kit_browser(self, browser: QtWidgets.QWidget) -> None:
        """Place the visual module-kit content browser in Room Building."""

        if browser is None:
            return
        browser.setParent(self.roomBuildingPage)
        self._roomPrimaryLayout.addWidget(browser, 1)

    def adopt_skybox_tools(
        self,
        sky_group: QtWidgets.QWidget,
        sky_traffic_group: QtWidgets.QWidget,
    ) -> None:
        """Present Environment-owned sky authoring controls in Build / Skybox."""

        for group in (sky_group, sky_traffic_group):
            group.setParent(self.skyboxBuildingPage)
            self._skyboxBuildingLayout.insertWidget(
                self._skyboxBuildingLayout.count() - 1,
                group,
            )
            group.show()
        self.skyboxBuildGuideLabel.setText(
            "Choose a measured vanilla sky style for a one-click KOTOR dome, enter five existing engine textures, "
            "or import an HDR/panorama and let Ghost Studio project and tone-map the game-compatible texture set."
        )

    def set_modeling_component_modes(self, modes) -> None:
        """Populate object/component mode choices for manual Map Studio modeling."""

        self.componentModeComboBox.blockSignals(True)
        self.componentModeComboBox.clear()
        for mode in modes or ():
            key = str(getattr(mode, "key", "") or "")
            label = str(getattr(mode, "label", "") or key)
            description = str(getattr(mode, "description", "") or "")
            guardrail = str(getattr(mode, "kotor_guardrail", "") or "")
            if key:
                self.componentModeComboBox.addItem(
                    label,
                    {
                        "key": key,
                        "label": label,
                        "description": description,
                        "guardrail": guardrail,
                    },
                )
        if self.componentModeComboBox.count() <= 0:
            self.componentModeComboBox.addItem(
                "Object",
                {
                    "key": "object",
                    "label": "Object",
                    "description": "Select and transform authored map objects.",
                    "guardrail": "Object edits mark staged exports and game proof stale.",
                },
            )
        self.componentModeComboBox.blockSignals(False)
        self._update_modeling_tool_hint()

    def set_modeling_tools(self, tools) -> None:
        """Populate Maya-like, KOTOR-aware modeling tools from core policy."""

        self.modelingToolComboBox.blockSignals(True)
        self.modelingToolComboBox.clear()
        for tool in tools or ():
            key = str(getattr(tool, "key", "") or "")
            label = str(getattr(tool, "label", "") or key)
            category = str(getattr(tool, "category", "") or "")
            description = str(getattr(tool, "description", "") or "")
            guardrail = str(getattr(tool, "kotor_guardrail", "") or "")
            modes = tuple(str(item) for item in getattr(tool, "component_modes", ()) or ())
            implemented = bool(getattr(tool, "implemented", False))
            if key:
                state = "usable" if implemented else "planned"
                self.modelingToolComboBox.addItem(
                    f"{label} ({state})",
                    {
                        "key": key,
                        "label": label,
                        "category": category,
                        "description": description,
                        "guardrail": guardrail,
                        "component_modes": modes,
                        "implemented": implemented,
                    },
                )
        if self.modelingToolComboBox.count() <= 0:
            self.modelingToolComboBox.addItem(
                "Create Primitive Room (usable)",
                {
                    "key": "primitive_room",
                    "label": "Create Primitive Room",
                    "category": "Primitives",
                    "description": "Seed a Map Studio room.",
                    "guardrail": "Validate generated module resources before export.",
                    "component_modes": ("object",),
                    "implemented": True,
                },
            )
        self.modelingToolComboBox.blockSignals(False)
        self._update_modeling_tool_hint()

    def set_modeling_snap_modes(self, snap_modes) -> None:
        """Populate snap modes including vertex snapping for Map Studio editing."""

        self.snapModeComboBox.blockSignals(True)
        self.snapModeComboBox.clear()
        for snap in snap_modes or ():
            key = str(getattr(snap, "key", "") or "")
            label = str(getattr(snap, "label", "") or key)
            description = str(getattr(snap, "description", "") or "")
            hotkey = str(getattr(snap, "hotkey", "") or "")
            if key:
                suffix = f" - {hotkey}" if hotkey else ""
                self.snapModeComboBox.addItem(
                    f"{label}{suffix}",
                    {
                        "key": key,
                        "label": label,
                        "description": description,
                        "hotkey": hotkey,
                    },
                )
        if self.snapModeComboBox.count() <= 0:
            self.snapModeComboBox.addItem(
                "Grid",
                {
                    "key": "grid",
                    "label": "Grid",
                    "description": "Snap edits to the Map Studio grid.",
                    "hotkey": "",
                },
            )
        self.snapModeComboBox.blockSignals(False)
        self._update_modeling_tool_hint()

    def _current_modeling_mode_data(self) -> dict:
        data = self.componentModeComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _current_modeling_tool_data(self) -> dict:
        data = self.modelingToolComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _current_snap_mode_data(self) -> dict:
        data = self.snapModeComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _update_modeling_tool_hint(self) -> None:
        mode = self._current_modeling_mode_data()
        tool = self._current_modeling_tool_data()
        snap = self._current_snap_mode_data()
        mode_label = str(mode.get("label") or "Object")
        mode_key = str(mode.get("key") or "object")
        tool_label = str(tool.get("label") or "Create Primitive Room")
        snap_label = str(snap.get("label") or "Grid")
        snap_hotkey = str(snap.get("hotkey") or "")
        implemented = bool(tool.get("implemented", False))
        compatible = mode_key in tuple(tool.get("component_modes") or ()) if tool else True
        description = str(tool.get("description") or mode.get("description") or "Choose a Map Studio modeling tool.")
        guardrail = str(tool.get("guardrail") or mode.get("guardrail") or "")
        state = "usable now" if implemented else "planned; validation-first"
        if not compatible:
            state = f"{state}; switch component mode for best fit"
        snap_text = f"{snap_label} snap"
        if snap_hotkey:
            snap_text = f"{snap_text} ({snap_hotkey})"
        self.modelingToolHintLabel.setText(f"{description} KOTOR guardrail: {guardrail}")
        summary = f"Modeling: {mode_label} / {tool_label} / {snap_text} - {state}"
        self.modelingStatusLabel.setText(summary)
        self.modelingContextChanged.emit(summary)

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

    def set_terrain_brushes(self, brushes) -> None:
        """Populate named terrain sculpt brushes for Map Studio."""

        self.terrainBrushComboBox.blockSignals(True)
        self.terrainBrushComboBox.clear()
        for brush in tuple(brushes or ()):
            key = str(getattr(brush, "key", "") or "")
            label = str(getattr(brush, "label", "") or key)
            operation = str(getattr(brush, "operation", "") or key)
            description = str(getattr(brush, "description", "") or "")
            guardrail = str(getattr(brush, "kotor_guardrail", "") or "")
            implemented = bool(getattr(brush, "implemented", False))
            continuous = bool(getattr(brush, "continuous_preview", True))
            self.terrainBrushComboBox.addItem(
                label,
                {
                    "key": key,
                    "operation": operation,
                    "description": description,
                    "guardrail": guardrail,
                    "implemented": implemented,
                    "continuous": continuous,
                },
            )
        if self.terrainBrushComboBox.count() <= 0:
            self.terrainBrushComboBox.addItem("No terrain brushes", None)
        self.terrainBrushComboBox.blockSignals(False)
        self._update_terrain_brush_controls()

    def _current_terrain_data(self) -> dict:
        data = self.terrainRoomComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _current_terrain_shape_data(self) -> dict:
        data = self.terrainShapePresetComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _current_terrain_brush_data(self) -> dict:
        data = self.terrainBrushComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _current_terrain_room_resref(self) -> str:
        return str(self._current_terrain_data().get("room_resref") or "").strip()

    def current_terrain_brush_context(self) -> dict:
        """Return the selected terrain brush context for viewport sculpting."""

        terrain = self._current_terrain_data()
        brush = self._current_terrain_brush_data()
        operation = str(brush.get("operation") or "").strip()
        return {
            "enabled": (
                self.terrainSculptEnabledCheckBox.isChecked()
                and bool(terrain)
                and bool(operation)
                and bool(brush.get("implemented"))
            ),
            "room_resref": str(terrain.get("room_resref") or "").strip(),
            "row_count": int(terrain.get("row_count", 0) or 0),
            "column_count": int(terrain.get("column_count", 0) or 0),
            "brush": operation,
            "height": float(self.terrainHeightSpinBox.value()),
            "delta": float(self.terrainDeltaSpinBox.value()),
            "radius": int(self.terrainRadiusSpinBox.value()),
            "iterations": int(self.terrainSmoothIterationsSpinBox.value()),
            "strength": float(self.terrainSmoothStrengthSpinBox.value()),
            "hardness": float(self.terrainHardnessSpinBox.value()),
        }

    def _update_terrain_shape_controls(self) -> None:
        data = self._current_terrain_shape_data()
        if not data:
            return
        self.terrainShapeHeightSpinBox.setValue(float(data.get("default_height", 0.0) or 0.0))
        description = str(data.get("description") or "").strip()
        if description and self._current_terrain_data():
            self.terrainHintLabel.setText(description)

    def _update_terrain_brush_controls(self) -> None:
        brush = self._current_terrain_brush_data()
        if not brush:
            self.terrainBrushStatusLabel.setText("Brush: no terrain brush is available.")
            self.applyTerrainBrushButton.setEnabled(False)
            self.checkLiveTerrainBrushFrameButton.setEnabled(False)
            return
        state = "ready" if brush.get("implemented") else "planned"
        continuous = "continuous preview" if brush.get("continuous") else "commit-only"
        description = str(brush.get("description") or "").strip()
        guardrail = str(brush.get("guardrail") or "").strip()
        label = str(brush.get("label") or brush.get("key") or "Brush")
        text = f"{label}: {state}, {continuous}."
        if description:
            text += f" {description}"
        if guardrail and brush.get("implemented"):
            text += " Check Slope / WOK overlay before export."
        self.terrainBrushStatusLabel.setText(text)
        enabled = bool(brush.get("implemented")) and bool(self._current_terrain_data())
        self.applyTerrainBrushButton.setEnabled(enabled)
        self.checkLiveTerrainBrushFrameButton.setEnabled(enabled)

    def _update_terrain_controls(self) -> None:
        data = self._current_terrain_data()
        enabled = bool(data)
        row_count = max(0, int(data.get("row_count", 0) or 0))
        column_count = max(0, int(data.get("column_count", 0) or 0))
        self.terrainRowSpinBox.setRange(0, max(0, row_count - 1))
        self.terrainColumnSpinBox.setRange(0, max(0, column_count - 1))
        for widget in (
            self.terrainRoomComboBox,
            self.terrainBrushComboBox,
            self.terrainShapePresetComboBox,
            self.terrainShapeHeightSpinBox,
            self.terrainRowSpinBox,
            self.terrainColumnSpinBox,
            self.terrainHeightSpinBox,
            self.terrainDeltaSpinBox,
            self.terrainRadiusSpinBox,
            self.terrainSmoothIterationsSpinBox,
            self.terrainSmoothStrengthSpinBox,
            self.terrainHardnessSpinBox,
            self.terrainSculptEnabledCheckBox,
            self.setTerrainHeightButton,
            self.raiseTerrainButton,
            self.lowerTerrainButton,
            self.smoothTerrainButton,
            self.flattenTerrainButton,
            self.carveTerrainHoleButton,
            self.fillTerrainHoleButton,
            self.applyTerrainBrushButton,
            self.checkLiveTerrainBrushFrameButton,
            self.applyTerrainShapeButton,
        ):
            widget.setEnabled(enabled)
        if not enabled:
            self.terrainHintLabel.setText("Create a terrain surface, then drag on it in the viewport to sculpt.")
            self.terrainBrushStatusLabel.setText("No terrain surface selected.")
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
        self._update_terrain_brush_controls()

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

    def _emit_selected_terrain_brush(self) -> None:
        brush = self._current_terrain_brush_data()
        operation = str(brush.get("operation") or "").strip()
        if not operation or not brush.get("implemented"):
            return
        self._emit_terrain_operation(f"brush_stroke:{operation}")

    def _emit_live_terrain_brush_frame(self) -> None:
        brush = self._current_terrain_brush_data()
        operation = str(brush.get("operation") or "").strip()
        room = self._current_terrain_room_resref()
        if not room or not operation or not brush.get("implemented"):
            return
        self.terrainLiveBrushFrameRequested.emit(
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

    @staticmethod
    def _select_combo_room_resref(combo: QtWidgets.QComboBox, room_resref: str) -> bool:
        room = str(room_resref or "").strip()
        if not room:
            return False
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and str(data.get("room_resref") or "").strip() == room:
                combo.setCurrentIndex(index)
                return True
        return False

    @staticmethod
    def _set_spinbox_clamped(spinbox: QtWidgets.QSpinBox, value: int) -> None:
        spinbox.setValue(max(int(spinbox.minimum()), min(int(value), int(spinbox.maximum()))))

    def select_floor_plan_edge(self, room_resref: str, edge_index: int) -> bool:
        """Select a floor-plan edge across bridge, opening, and edge-extrude tools."""

        room = str(room_resref or "").strip()
        edge = int(edge_index)
        if not room or edge < 0:
            return False

        opening_selected = self._select_combo_room_resref(self.floorPlanOpeningRoomComboBox, room)
        bridge_selected = self._select_combo_room_resref(self.floorPlanBridgeFirstRoomComboBox, room)
        operation_index = self.roomOperationComboBox.findData("edge_extrude")
        operation_selected = operation_index >= 0
        if operation_selected:
            self.roomOperationComboBox.setCurrentIndex(operation_index)

        self._update_floor_plan_opening_controls()
        self._update_floor_plan_bridge_controls()
        self._update_operation_controls()
        self._set_spinbox_clamped(self.floorPlanOpeningEdgeSpinBox, edge)
        self._set_spinbox_clamped(self.floorPlanBridgeFirstEdgeSpinBox, edge)
        self._set_spinbox_clamped(self.operationEdgeIndexSpinBox, edge)
        self._update_floor_plan_opening_controls()
        self._update_floor_plan_bridge_controls()
        self._update_operation_controls()

        message = (
            f"Selected edge {edge} in {room}. Bridge, Wall Opening, and Edge Extrude now target this floor-plan edge."
        )
        self.modelingStatusLabel.setText(message)
        self.modelingContextChanged.emit(
            f"Edge mode: selected {room} edge {edge} for bridge/opening/extrude workflows."
        )
        return bool(opening_selected or bridge_selected or operation_selected)

    def set_floor_plan_room_choices(self, rooms) -> None:
        """Populate floor-plan room choices for Builder boolean operations."""

        extrusion_current = self._current_combo_resref(self.floorPlanExtrusionRoomComboBox)
        opening_current = self._current_combo_resref(self.floorPlanOpeningRoomComboBox)
        marker_current = self._current_combo_resref(self.floorPlanOpeningMarkerRoomComboBox)
        marker_opening_current = self.floorPlanOpeningMarkerNameComboBox.currentText().strip()
        first_current = self._current_combo_resref(self.floorPlanUnionFirstRoomComboBox)
        second_current = self._current_combo_resref(self.floorPlanUnionSecondRoomComboBox)
        bridge_first_current = self._current_combo_resref(self.floorPlanBridgeFirstRoomComboBox)
        bridge_second_current = self._current_combo_resref(self.floorPlanBridgeSecondRoomComboBox)
        vertex_current = self._current_combo_resref(self.floorPlanVertexRoomComboBox)
        vertex_target_current = self._current_combo_resref(self.floorPlanVertexTargetRoomComboBox)
        choices = tuple(rooms or ())
        for combo, current in (
            (self.floorPlanExtrusionRoomComboBox, extrusion_current),
            (self.floorPlanOpeningRoomComboBox, opening_current),
            (self.floorPlanOpeningMarkerRoomComboBox, marker_current),
            (self.floorPlanUnionFirstRoomComboBox, first_current),
            (self.floorPlanUnionSecondRoomComboBox, second_current),
            (self.floorPlanBridgeFirstRoomComboBox, bridge_first_current),
            (self.floorPlanBridgeSecondRoomComboBox, bridge_second_current),
            (self.floorPlanVertexRoomComboBox, vertex_current),
            (self.floorPlanVertexTargetRoomComboBox, vertex_target_current),
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
                    "z": float(getattr(choice, "z", 0.0) or 0.0),
                    "wall_height": float(getattr(choice, "wall_height", 3.0) or 3.0),
                    "include_walls": bool(getattr(choice, "include_walls", True)),
                    "floor_surface_id": str(getattr(choice, "floor_surface_id", "4") or "4"),
                    "floor_surface_name": str(getattr(choice, "floor_surface_name", "") or ""),
                    "opening_count": int(getattr(choice, "opening_count", 0) or 0),
                    "opening_names": tuple(getattr(choice, "opening_names", ()) or ()),
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
        if self.floorPlanBridgeSecondRoomComboBox.count() > 1 and self.floorPlanBridgeSecondRoomComboBox.currentIndex() == self.floorPlanBridgeFirstRoomComboBox.currentIndex():
            self.floorPlanBridgeSecondRoomComboBox.setCurrentIndex(1)
        self._choose_default_floor_plan_bridge_edges()
        self._update_floor_plan_extrusion_controls()
        self._update_floor_plan_opening_controls()
        self._update_floor_plan_opening_marker_controls(marker_opening_current)
        self._update_floor_plan_vertex_controls()
        self._update_rectangular_union_controls()
        self._update_floor_plan_bridge_controls()

    def _choose_default_floor_plan_bridge_edges(self) -> None:
        first_data = self._current_floor_plan_bridge_first_data()
        second_data = self._current_floor_plan_bridge_second_data()
        first = str(first_data.get("room_resref") or "").strip()
        second = str(second_data.get("room_resref") or "").strip()
        second_count = int(second_data.get("point_count", 0) or 0)
        if (
            first
            and second
            and first != second
            and second_count >= 3
            and int(self.floorPlanBridgeFirstEdgeSpinBox.value()) == 0
            and int(self.floorPlanBridgeSecondEdgeSpinBox.value()) == 0
        ):
            self._set_spinbox_clamped(self.floorPlanBridgeSecondEdgeSpinBox, min(1, second_count - 1))

    def _current_floor_plan_extrusion_data(self) -> dict:
        data = self.floorPlanExtrusionRoomComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _current_floor_plan_surface_data(self) -> dict:
        data = self.floorPlanSurfaceComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _update_floor_plan_extrusion_controls(self) -> None:
        data = self._current_floor_plan_extrusion_data()
        enabled = bool(data)
        for widget in (
            self.floorPlanExtrusionRoomComboBox,
            self.floorPlanWallHeightSpinBox,
            self.floorPlanFloorZSpinBox,
            self.floorPlanIncludeWallsCheckBox,
            self.floorPlanSurfaceComboBox,
            self.applyFloorPlanExtrusionButton,
        ):
            widget.setEnabled(enabled)
        if enabled:
            self.floorPlanWallHeightSpinBox.blockSignals(True)
            self.floorPlanWallHeightSpinBox.setValue(float(data.get("wall_height", 3.0) or 3.0))
            self.floorPlanWallHeightSpinBox.blockSignals(False)
            self.floorPlanFloorZSpinBox.blockSignals(True)
            self.floorPlanFloorZSpinBox.setValue(float(data.get("z", 0.0) or 0.0))
            self.floorPlanFloorZSpinBox.blockSignals(False)
            self.floorPlanIncludeWallsCheckBox.blockSignals(True)
            self.floorPlanIncludeWallsCheckBox.setChecked(bool(data.get("include_walls", True)))
            self.floorPlanIncludeWallsCheckBox.blockSignals(False)
            self._select_surface_combo_value(self.floorPlanSurfaceComboBox, str(data.get("floor_surface_id") or "4"))
        self._update_floor_plan_extrusion_hint()

    def _update_floor_plan_extrusion_hint(self) -> None:
        data = self._current_floor_plan_extrusion_data()
        if not data:
            self.floorPlanExtrusionHintLabel.setText(
                "Create a floor-plan or rectangular room preset before setting extrusion height, floor elevation, walls, and WOK surface."
            )
            return
        surface = self._current_floor_plan_surface_data()
        surface_name = surface.get("name") or data.get("floor_surface_name") or data.get("floor_surface_id") or "4"
        walkable = bool(surface.get("walkable", True))
        walkable_note = "walkable" if walkable else "not normally walkable"
        self.floorPlanExtrusionHintLabel.setText(
            f"Editing {data.get('room_resref')}: {int(data.get('point_count', 0) or 0)} footprint points, "
            f"{float(self.floorPlanWallHeightSpinBox.value()):.2f} m walls, floor Z {float(self.floorPlanFloorZSpinBox.value()):.2f} m, "
            f"WOK surface {surface_name} ({walkable_note})."
        )

    def _emit_floor_plan_extrusion(self) -> None:
        data = self._current_floor_plan_extrusion_data()
        room = str(data.get("room_resref") or "").strip()
        if not room:
            return
        surface_id = str(self._current_floor_plan_surface_data().get("surface_id") or data.get("floor_surface_id") or "4")
        self.floorPlanExtrusionRequested.emit(
            room,
            float(self.floorPlanFloorZSpinBox.value()),
            float(self.floorPlanWallHeightSpinBox.value()),
            bool(self.floorPlanIncludeWallsCheckBox.isChecked()),
            surface_id,
        )

    def _current_floor_plan_opening_data(self) -> dict:
        data = self.floorPlanOpeningRoomComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _update_floor_plan_opening_controls(self) -> None:
        data = self._current_floor_plan_opening_data()
        point_count = int(data.get("point_count", 0) or 0)
        enabled = bool(data and point_count >= 3)
        for widget in (
            self.floorPlanOpeningRoomComboBox,
            self.floorPlanOpeningNameLineEdit,
            self.floorPlanOpeningEdgeSpinBox,
            self.floorPlanOpeningCenterSpinBox,
            self.floorPlanOpeningWidthSpinBox,
            self.floorPlanOpeningHeightSpinBox,
            self.floorPlanOpeningBottomSpinBox,
            self.applyFloorPlanOpeningButton,
        ):
            widget.setEnabled(enabled)
        self.floorPlanOpeningEdgeSpinBox.setRange(0, max(point_count - 1, 0))
        wall_height = max(float(data.get("wall_height", 3.0) or 3.0), 0.1)
        self.floorPlanOpeningHeightSpinBox.setMaximum(max(wall_height - 0.05, 0.05))
        self.floorPlanOpeningBottomSpinBox.setMaximum(max(wall_height - 0.05, 0.0))
        if enabled:
            self.floorPlanOpeningHintLabel.setText(
                f"Editing {data.get('room_resref')}: choose one wall edge from 0..{point_count - 1}. "
                "Existing openings on the same edge are replaced so the generated wall remains KOTOR-safe."
            )
        else:
            self.floorPlanOpeningHintLabel.setText(
                "Create a floor-plan room with generated walls before adding a doorway or window opening."
            )

    def _emit_floor_plan_opening(self) -> None:
        data = self._current_floor_plan_opening_data()
        room = str(data.get("room_resref") or "").strip()
        if not room:
            return
        self.floorPlanOpeningRequested.emit(
            room,
            self.floorPlanOpeningNameLineEdit.text().strip(),
            int(self.floorPlanOpeningEdgeSpinBox.value()),
            float(self.floorPlanOpeningCenterSpinBox.value()),
            float(self.floorPlanOpeningWidthSpinBox.value()),
            float(self.floorPlanOpeningHeightSpinBox.value()),
            float(self.floorPlanOpeningBottomSpinBox.value()),
        )

    def _current_floor_plan_opening_marker_data(self) -> dict:
        data = self.floorPlanOpeningMarkerRoomComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _update_floor_plan_opening_marker_controls(self, selected_opening: str = "") -> None:
        data = self._current_floor_plan_opening_marker_data()
        opening_names = tuple(str(name).strip() for name in tuple(data.get("opening_names", ()) or ()) if str(name).strip())
        enabled = bool(data and opening_names)
        previous = str(selected_opening or self.floorPlanOpeningMarkerNameComboBox.currentText() or "").strip()
        self.floorPlanOpeningMarkerNameComboBox.blockSignals(True)
        self.floorPlanOpeningMarkerNameComboBox.clear()
        if opening_names:
            for name in opening_names:
                self.floorPlanOpeningMarkerNameComboBox.addItem(name, name)
            match = self.floorPlanOpeningMarkerNameComboBox.findText(previous)
            self.floorPlanOpeningMarkerNameComboBox.setCurrentIndex(match if match >= 0 else 0)
        else:
            self.floorPlanOpeningMarkerNameComboBox.addItem("No authored openings yet", "")
        self.floorPlanOpeningMarkerNameComboBox.blockSignals(False)
        for widget in (
            self.floorPlanOpeningMarkerRoomComboBox,
            self.floorPlanOpeningMarkerNameComboBox,
            self.floorPlanOpeningMarkerKindComboBox,
            self.floorPlanOpeningMarkerTemplateLineEdit,
            self.floorPlanOpeningMarkerTagLineEdit,
            self.floorPlanOpeningMarkerLinkedToLineEdit,
            self.floorPlanOpeningMarkerLinkedModuleLineEdit,
            self.floorPlanOpeningMarkerTargetTypeComboBox,
            self.floorPlanOpeningMarkerTransitionDestSpinBox,
            self.createFloorPlanOpeningMarkerButton,
        ):
            widget.setEnabled(enabled)
        kind = str(self.floorPlanOpeningMarkerKindComboBox.currentData() or "door")
        if kind == "door":
            self.floorPlanOpeningMarkerTemplateLineEdit.setPlaceholderText("UTD template resref, e.g. door_t01")
        elif kind == "trigger":
            self.floorPlanOpeningMarkerTemplateLineEdit.setPlaceholderText("UTT template resref, e.g. tr_transition")
        else:
            self.floorPlanOpeningMarkerTemplateLineEdit.setPlaceholderText("UTW template resref, e.g. wp_transition")
        is_transition_source = kind in {"door", "trigger"}
        for widget in (
            self.floorPlanOpeningMarkerLinkedToLineEdit,
            self.floorPlanOpeningMarkerLinkedModuleLineEdit,
            self.floorPlanOpeningMarkerTargetTypeComboBox,
            self.floorPlanOpeningMarkerTransitionDestSpinBox,
        ):
            widget.setEnabled(enabled and is_transition_source)
            widget.setVisible(is_transition_source)
            label = self.floorPlanOpeningMarkerLayout.labelForField(widget)
            if label is not None:
                label.setVisible(is_transition_source)
        if enabled:
            if is_transition_source:
                self.floorPlanOpeningMarkerHintLabel.setText(
                    f"Editing {data.get('room_resref')}: create a {kind} transition source from one authored opening. "
                    "Linked To names a destination door or waypoint; Module is blank for a local link."
                )
            else:
                self.floorPlanOpeningMarkerHintLabel.setText(
                    f"Editing {data.get('room_resref')}: create a waypoint destination from one authored opening. "
                    "Doors and triggers link to this waypoint tag; waypoints do not initiate transitions."
                )
        else:
            self.floorPlanOpeningMarkerHintLabel.setText(
                "Add a floor-plan wall opening before creating a KOTOR door, trigger, or waypoint marker from it."
            )

    def _emit_floor_plan_opening_marker(self) -> None:
        data = self._current_floor_plan_opening_marker_data()
        room = str(data.get("room_resref") or "").strip()
        opening = str(self.floorPlanOpeningMarkerNameComboBox.currentData() or self.floorPlanOpeningMarkerNameComboBox.currentText() or "").strip()
        if not room or not opening:
            return
        kind = str(self.floorPlanOpeningMarkerKindComboBox.currentData() or "door")
        linked_to = self.floorPlanOpeningMarkerLinkedToLineEdit.text().strip() if kind in {"door", "trigger"} else ""
        linked_module = self.floorPlanOpeningMarkerLinkedModuleLineEdit.text().strip() if kind in {"door", "trigger"} else ""
        target_type = int(self.floorPlanOpeningMarkerTargetTypeComboBox.currentData() or 0) if linked_to else 0
        destination_name_sref = int(self.floorPlanOpeningMarkerTransitionDestSpinBox.value()) if kind in {"door", "trigger"} else 0
        self.floorPlanOpeningMarkerRequested.emit(
            room,
            opening,
            kind,
            self.floorPlanOpeningMarkerTemplateLineEdit.text().strip(),
            self.floorPlanOpeningMarkerTagLineEdit.text().strip(),
            linked_to,
            linked_module,
            target_type,
            destination_name_sref,
        )

    def _current_floor_plan_vertex_room_data(self) -> dict:
        data = self.floorPlanVertexRoomComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _current_floor_plan_vertex_target_room_data(self) -> dict:
        data = self.floorPlanVertexTargetRoomComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _parse_floor_plan_point_indices(self) -> tuple[int, ...]:
        text = self.floorPlanSelectedPointsLineEdit.text().strip()
        if not text:
            return ()
        values: list[int] = []
        for part in text.replace(";", ",").split(","):
            item = part.strip()
            if not item:
                continue
            values.append(int(item))
        return tuple(dict.fromkeys(values))

    def _update_floor_plan_vertex_controls(self) -> None:
        room = self._current_floor_plan_vertex_room_data()
        target_room = self._current_floor_plan_vertex_target_room_data()
        point_count = int(room.get("point_count", 0) or 0)
        target_point_count = int(target_room.get("point_count", 0) or 0)
        enabled = bool(room and point_count > 0)
        target_enabled = bool(target_room and target_point_count > 0)
        self.floorPlanVertexRoomComboBox.setEnabled(enabled)
        self.floorPlanVertexTargetRoomComboBox.setEnabled(enabled and target_enabled)
        self.floorPlanSourcePointSpinBox.setEnabled(enabled)
        self.floorPlanTargetPointSpinBox.setEnabled(enabled and target_enabled)
        self.floorPlanSelectedPointsLineEdit.setEnabled(enabled)
        self.floorPlanWeldPolicyComboBox.setEnabled(enabled)
        self.floorPlanFlattenAxisComboBox.setEnabled(enabled)
        self.floorPlanMirrorAxisComboBox.setEnabled(enabled)
        self.floorPlanCleanupToleranceSpinBox.setEnabled(enabled)
        self.snapFloorPlanVertexButton.setEnabled(enabled and target_enabled and point_count >= 2)
        try:
            selected = self._parse_floor_plan_point_indices()
        except ValueError:
            selected = ()
        self.weldFloorPlanVerticesButton.setEnabled(enabled and len(selected) >= 2)
        self.flattenFloorPlanVerticesButton.setEnabled(enabled and len(selected) >= 1)
        self.mirrorFloorPlanVerticesButton.setEnabled(enabled and point_count >= 3)
        self.cleanupFloorPlanVerticesButton.setEnabled(enabled and point_count >= 3)
        self.fillFloorPlanFaceButton.setEnabled(enabled and len(selected) >= 3)
        self.splitFloorPlanFaceButton.setEnabled(enabled and len(selected) == 2 and point_count >= 4)
        self.triangulateFloorPlanFaceButton.setEnabled(enabled and point_count >= 3)
        self.cleanupFloorPlanNormalsButton.setEnabled(enabled and point_count >= 3)
        self.floorPlanSourcePointSpinBox.setRange(0, max(point_count - 1, 0))
        self.floorPlanTargetPointSpinBox.setRange(0, max(target_point_count - 1, 0))
        if not enabled:
            self.floorPlanVertexHintLabel.setText(
                "Create a floor-plan room before using vertex snap, weld, flatten, or cleanup tools."
            )
        elif not selected:
            self.floorPlanVertexHintLabel.setText(
                f"Editing {room.get('room_resref')}: {point_count} points. Enter point indices to weld, flatten, split between two non-adjacent points, or fill a face loop; snap one source point, mirror the footprint, triangulate it, or cleanup redundant points/normals."
            )
        else:
            self.floorPlanVertexHintLabel.setText(
                f"Editing {room.get('room_resref')}: selected points {', '.join(str(item) for item in selected)}. "
                "These component edits can repair face loops, triangulation, or normals and will mark export/game proof stale when geometry changes."
            )
        if enabled:
            self._emit_floor_plan_vertex_snap_preview()

    def _emit_floor_plan_vertex_snap_preview(self) -> None:
        room = str(self._current_floor_plan_vertex_room_data().get("room_resref") or "").strip()
        if room:
            self.floorPlanVertexSnapPreviewRequested.emit(room, int(self.floorPlanSourcePointSpinBox.value()))

    def request_floor_plan_vertex_snap_preview(self) -> None:
        """Ask the controller/window to refresh the non-mutating snap target preview."""

        self._emit_floor_plan_vertex_snap_preview()

    def set_floor_plan_vertex_snap_candidates(self, candidates) -> None:
        """Display nearest snap target candidates returned by the headless controller."""

        room = str(self._current_floor_plan_vertex_room_data().get("room_resref") or "").strip()
        if not room:
            return
        items = tuple(candidates or ())
        source_point = int(self.floorPlanSourcePointSpinBox.value())
        if not items:
            self.floorPlanVertexHintLabel.setText(
                f"Editing {room}: source point {source_point}. No snap target is available yet. "
                "Choose another point or room, or create another floor-plan room to align seams."
            )
            return
        nearest = items[0]
        target_room = str(getattr(nearest, "room_resref", "") or "")
        target_point = int(getattr(nearest, "point_index", 0) or 0)
        distance = float(getattr(nearest, "distance", 0.0) or 0.0)
        same_room = bool(getattr(nearest, "same_room", False))
        scope = "same room" if same_room else "cross-room"
        self.floorPlanVertexHintLabel.setText(
            f"Editing {room}: source point {source_point}. Nearest snap target is {target_room} point {target_point} "
            f"at {distance:.3f} m ({scope}). Click Snap Vertex to commit; this preview does not weld topology."
        )

    def _emit_floor_plan_vertex_snap(self) -> None:
        room = str(self._current_floor_plan_vertex_room_data().get("room_resref") or "").strip()
        target_room = str(self._current_floor_plan_vertex_target_room_data().get("room_resref") or "").strip()
        if room:
            self.floorPlanVertexSnapRequested.emit(
                room,
                int(self.floorPlanSourcePointSpinBox.value()),
                int(self.floorPlanTargetPointSpinBox.value()),
                target_room,
            )

    def _emit_floor_plan_vertex_weld(self) -> None:
        room = str(self._current_floor_plan_vertex_room_data().get("room_resref") or "").strip()
        if not room:
            return
        try:
            selected = self._parse_floor_plan_point_indices()
        except ValueError:
            self.floorPlanVertexHintLabel.setText("Point indices must be comma-separated integers, e.g. 0,1,2.")
            return
        policy = str(self.floorPlanWeldPolicyComboBox.currentData() or "target")
        self.floorPlanVertexWeldRequested.emit(room, selected, int(self.floorPlanTargetPointSpinBox.value()), policy)

    def _emit_floor_plan_vertex_flatten(self) -> None:
        room = str(self._current_floor_plan_vertex_room_data().get("room_resref") or "").strip()
        if not room:
            return
        try:
            selected = self._parse_floor_plan_point_indices()
        except ValueError:
            self.floorPlanVertexHintLabel.setText("Point indices must be comma-separated integers, e.g. 0,1,2.")
            return
        axis = str(self.floorPlanFlattenAxisComboBox.currentData() or "x")
        self.floorPlanVertexFlattenRequested.emit(room, selected, axis, None)

    def _emit_floor_plan_vertex_cleanup(self) -> None:
        room = str(self._current_floor_plan_vertex_room_data().get("room_resref") or "").strip()
        if room:
            self.floorPlanVertexCleanupRequested.emit(room, float(self.floorPlanCleanupToleranceSpinBox.value()))

    def _emit_floor_plan_vertex_mirror(self) -> None:
        room = str(self._current_floor_plan_vertex_room_data().get("room_resref") or "").strip()
        axis = str(self.floorPlanMirrorAxisComboBox.currentData() or "x")
        if room:
            self.floorPlanVertexMirrorRequested.emit(room, axis)

    def _emit_floor_plan_face_fill(self) -> None:
        room = str(self._current_floor_plan_vertex_room_data().get("room_resref") or "").strip()
        if not room:
            return
        try:
            selected = self._parse_floor_plan_point_indices()
        except ValueError:
            self.floorPlanVertexHintLabel.setText("Point indices must be comma-separated integers, e.g. 0,1,2.")
            return
        self.floorPlanFaceFillRequested.emit(room, selected)

    def _emit_floor_plan_face_split(self) -> None:
        room = str(self._current_floor_plan_vertex_room_data().get("room_resref") or "").strip()
        if not room:
            return
        try:
            selected = self._parse_floor_plan_point_indices()
        except ValueError:
            self.floorPlanVertexHintLabel.setText("Point indices must be comma-separated integers, e.g. 0,2.")
            return
        if len(selected) != 2:
            self.floorPlanVertexHintLabel.setText(
                "Face split requires exactly two non-adjacent point indices, e.g. 0,2."
            )
            return
        self.floorPlanFaceSplitRequested.emit(room, selected)

    def _emit_floor_plan_face_triangulate(self) -> None:
        room = str(self._current_floor_plan_vertex_room_data().get("room_resref") or "").strip()
        if room:
            self.floorPlanFaceTriangulateRequested.emit(room)

    def _emit_floor_plan_normals_cleanup(self) -> None:
        room = str(self._current_floor_plan_vertex_room_data().get("room_resref") or "").strip()
        if room:
            self.floorPlanNormalsCleanupRequested.emit(room)

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

    def _current_floor_plan_bridge_first_data(self) -> dict:
        data = self.floorPlanBridgeFirstRoomComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _current_floor_plan_bridge_second_data(self) -> dict:
        data = self.floorPlanBridgeSecondRoomComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _update_floor_plan_bridge_controls(self) -> None:
        first_data = self._current_floor_plan_bridge_first_data()
        second_data = self._current_floor_plan_bridge_second_data()
        first = str(first_data.get("room_resref") or "").strip()
        second = str(second_data.get("room_resref") or "").strip()
        first_count = int(first_data.get("point_count", 0) or 0)
        second_count = int(second_data.get("point_count", 0) or 0)
        ready = bool(first and second and first != second and first_count >= 3 and second_count >= 3)
        count = max(self.floorPlanBridgeFirstRoomComboBox.count(), self.floorPlanBridgeSecondRoomComboBox.count())
        self.floorPlanBridgeFirstRoomComboBox.setEnabled(count >= 2)
        self.floorPlanBridgeSecondRoomComboBox.setEnabled(count >= 2)
        self.floorPlanBridgeFirstEdgeSpinBox.setEnabled(bool(first_data and first_count >= 3))
        self.floorPlanBridgeSecondEdgeSpinBox.setEnabled(bool(second_data and second_count >= 3))
        self.floorPlanBridgeFirstEdgeSpinBox.setRange(0, max(first_count - 1, 0))
        self.floorPlanBridgeSecondEdgeSpinBox.setRange(0, max(second_count - 1, 0))
        self.floorPlanBridgeResultRoomLineEdit.setEnabled(ready)
        self.bridgeFloorPlanEdgesButton.setEnabled(ready)
        if count < 2:
            self.floorPlanBridgeHintLabel.setText(
                "Create at least two compatible floor-plan rooms before bridging edges into a connector room."
            )
        elif not ready:
            self.floorPlanBridgeHintLabel.setText(
                "Choose two different floor-plan rooms and edge indices. Bridge requires matching floor elevation, WOK surface, material, and wall settings."
            )
        else:
            self.floorPlanBridgeHintLabel.setText(
                f"Ready to bridge edge {int(self.floorPlanBridgeFirstEdgeSpinBox.value())} in {first} "
                f"to edge {int(self.floorPlanBridgeSecondEdgeSpinBox.value())} in {second}. This creates a new connector room."
            )

    def _emit_floor_plan_bridge(self) -> None:
        first = self._current_combo_resref(self.floorPlanBridgeFirstRoomComboBox)
        second = self._current_combo_resref(self.floorPlanBridgeSecondRoomComboBox)
        if not first or not second or first == second:
            return
        self.floorPlanBridgeRequested.emit(
            first,
            int(self.floorPlanBridgeFirstEdgeSpinBox.value()),
            second,
            int(self.floorPlanBridgeSecondEdgeSpinBox.value()),
            self.floorPlanBridgeResultRoomLineEdit.text().strip(),
        )

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

    @staticmethod
    def _primitive_property_field(source: object, name: str, default: object = None) -> object:
        if isinstance(source, dict):
            return source.get(name, default)
        return getattr(source, name, default)

    @staticmethod
    def _coerce_primitive_property_value(kind: str, value: object) -> object:
        normalized_kind = str(kind or "float").strip().lower()
        if normalized_kind == "bool":
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
            return bool(value)
        if normalized_kind == "int":
            try:
                return int(round(float(value)))
            except (TypeError, ValueError):
                return 0
        if normalized_kind == "vector3":
            source = tuple(value or ()) if isinstance(value, (tuple, list)) else ()
            if len(source) < 3:
                source = (0.0, 0.0, 0.0)
            try:
                return tuple(float(component) for component in source[:3])
            except (TypeError, ValueError):
                return (0.0, 0.0, 0.0)
        if normalized_kind == "choice":
            return value
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _primitive_property_payload(cls, source: object) -> dict[str, object]:
        """Normalize legacy dimensions and typed construction properties for the inspector."""

        value = cls._primitive_property_field(source, "value", 0.0)
        choices = cls._primitive_property_field(source, "choices", None)
        if choices is None:
            choices = cls._primitive_property_field(source, "options", ())
        raw_kind = str(
            cls._primitive_property_field(
                source,
                "kind",
                cls._primitive_property_field(source, "value_type", cls._primitive_property_field(source, "type", "")),
            )
            or ""
        ).strip().lower()
        aliases = {
            "boolean": "bool",
            "double": "float",
            "number": "float",
            "integer": "int",
            "enum": "choice",
            "select": "choice",
            "vector": "vector3",
            "vec3": "vector3",
            "double3": "vector3",
            "axis": "vector3",
        }
        kind = aliases.get(raw_kind, raw_kind)
        if bool(cls._primitive_property_field(source, "integer", False)):
            kind = "int"
        elif not kind and choices:
            kind = "choice"
        elif not kind and isinstance(value, bool):
            kind = "bool"
        elif not kind and isinstance(value, (tuple, list)) and len(value) == 3:
            kind = "vector3"
        elif not kind:
            kind = "float"
        if kind not in {"float", "int", "bool", "vector3", "choice"}:
            kind = "float"

        default_names = ("default", "default_value", "defaultValue")
        explicit_has_default = cls._primitive_property_field(source, "has_default", None)
        if explicit_has_default is not None:
            has_default = bool(explicit_has_default)
        elif isinstance(source, dict):
            has_default = any(name in source for name in default_names)
        else:
            has_default = any(hasattr(source, name) for name in default_names)
        default_value: object = None
        if has_default:
            for name in default_names:
                marker = object()
                candidate = cls._primitive_property_field(source, name, marker)
                if candidate is not marker:
                    default_value = cls._coerce_primitive_property_value(kind, candidate)
                    break

        default_suffix = " m" if kind == "float" else ""
        return {
            "key": str(cls._primitive_property_field(source, "key", "") or ""),
            "label": str(cls._primitive_property_field(source, "label", "") or ""),
            "group": str(cls._primitive_property_field(source, "group", "Construction") or "Construction"),
            "kind": kind,
            "value": cls._coerce_primitive_property_value(kind, value),
            "minimum": cls._primitive_property_field(source, "minimum", 0.001),
            "maximum": cls._primitive_property_field(source, "maximum", 1000.0),
            "step": cls._primitive_property_field(source, "step", 0.1),
            "suffix": str(cls._primitive_property_field(source, "suffix", default_suffix) or ""),
            "integer": kind == "int",
            "choices": choices,
            "component_labels": tuple(cls._primitive_property_field(source, "component_labels", ("X", "Y", "Z")) or ("X", "Y", "Z")),
            "description": str(
                cls._primitive_property_field(
                    source,
                    "description",
                    cls._primitive_property_field(
                        source,
                        "tooltip",
                        cls._primitive_property_field(source, "implementation_note", ""),
                    ),
                )
                or ""
            ),
            "read_only": bool(cls._primitive_property_field(source, "read_only", False)),
            "affects_topology": bool(cls._primitive_property_field(source, "affects_topology", False)),
            "affects_uvs": bool(cls._primitive_property_field(source, "affects_uvs", False)),
            "soft_minimum": cls._primitive_property_field(source, "soft_minimum", None),
            "soft_maximum": cls._primitive_property_field(source, "soft_maximum", None),
            "decimals": int(cls._primitive_property_field(source, "decimals", 3) or 0),
            "has_default": has_default,
            "default": default_value,
        }

    def set_room_primitives(self, primitives) -> None:
        """Populate editable primitive transform choices from the controller."""

        self._cancel_active_primitive_dimensions_preview()
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
            property_source = getattr(primitive, "properties", None)
            if property_source is None:
                property_source = getattr(primitive, "dimensions", ())
            properties = tuple(self._primitive_property_payload(item) for item in property_source or ())
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
                "properties": properties,
                "dimensions": properties,
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
        self._fill_surface_combo(self.floorPlanSurfaceComboBox, self._authored_walkmesh_surfaces)
        self._update_floor_plan_extrusion_controls()
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
            self.primitiveTransformHintLabel.setText("Create a composition room preset to edit planes, walls, ramps, stairs, arches, cubes, and cylinders.")
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

    @staticmethod
    def _primitive_numeric_component(value: object, index: int, fallback: float) -> float:
        source = value
        if isinstance(source, (tuple, list)):
            source = source[index] if index < len(source) else fallback
        try:
            return float(source)
        except (TypeError, ValueError):
            return float(fallback)

    @classmethod
    def _primitive_choice_entries(cls, choices: object) -> tuple[tuple[str, object], ...]:
        if isinstance(choices, dict):
            return tuple((str(label), value) for label, value in choices.items())
        entries: list[tuple[str, object]] = []
        for choice in choices or ():
            if isinstance(choice, dict):
                value = choice.get("value", choice.get("id", choice.get("key")))
                label = choice.get("label", choice.get("name", value))
            elif isinstance(choice, (tuple, list)) and len(choice) >= 2:
                label, value = choice[0], choice[1]
            else:
                value = choice
                label = choice
            entries.append((str(label), value))
        return tuple(entries)

    @staticmethod
    def _primitive_property_token(key: str, index: int) -> str:
        token = "".join(character if character.isalnum() else "_" for character in str(key or ""))
        return token.strip("_") or f"Property{index + 1}"

    def _clear_primitive_property_controls(self) -> None:
        self._primitive_property_preview_timer.stop()
        while self.primitivePropertyRowsLayout.count():
            item = self.primitivePropertyRowsLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._primitive_property_controls.clear()
        self._primitive_dimension_controls.clear()
        self._primitive_property_baseline.clear()

    def _make_primitive_numeric_editor(
        self,
        property_data: dict[str, object],
        index: int,
        component_index: int | None = None,
    ) -> QtWidgets.QAbstractSpinBox:
        kind = str(property_data.get("kind") or "float")
        integer = kind == "int"
        raw_minimum = property_data.get("minimum")
        raw_maximum = property_data.get("maximum")
        # Missing hard bounds are intentional for signed construction inputs
        # such as primitive axes.  Soft bounds guide scrubbing; they must not
        # clamp zero/negative typed values or change the retained recipe.
        minimum = self._primitive_numeric_component(
            raw_minimum,
            component_index or 0,
            -2147483647.0 if raw_minimum is None else 0.001,
        )
        maximum = self._primitive_numeric_component(
            raw_maximum,
            component_index or 0,
            2147483647.0 if raw_maximum is None else 1000.0,
        )
        step = self._primitive_numeric_component(property_data.get("step"), component_index or 0, 1.0 if integer else 0.1)
        if maximum < minimum:
            minimum, maximum = maximum, minimum
        if integer:
            editor = QtWidgets.QSpinBox()
            editor.setRange(max(-2147483647, int(round(minimum))), min(2147483647, int(round(maximum))))
            editor.setSingleStep(max(1, int(round(step))))
        else:
            editor = QtWidgets.QDoubleSpinBox()
            editor.setRange(minimum, maximum)
            editor.setDecimals(max(0, min(9, int(property_data.get("decimals", 3) or 0))))
            editor.setSingleStep(max(0.000001, step))
        suffix = str(property_data.get("suffix") or "")
        editor.setSuffix(suffix)
        editor.setAccelerated(True)
        editor.setKeyboardTracking(False)
        if component_index is None:
            editor.setObjectName(f"mapStudioPrimitiveDimension{index + 1}SpinBox")
        else:
            axis = "XYZ"[component_index]
            editor.setObjectName(f"mapStudioPrimitiveProperty{index + 1}{axis}SpinBox")
        editor.setProperty("dimensionKey", str(property_data.get("key") or ""))
        editor.setProperty("dimensionInteger", integer)
        editor.setProperty("primitivePropertyKind", kind)
        editor.valueChanged.connect(self._on_primitive_property_edited)
        return editor

    def _create_primitive_property_editor(
        self,
        property_data: dict[str, object],
        index: int,
    ) -> tuple[QtWidgets.QWidget, tuple[QtWidgets.QWidget, ...]]:
        kind = str(property_data.get("kind") or "float")
        key = str(property_data.get("key") or "")
        if kind == "bool":
            editor = QtWidgets.QCheckBox()
            editor.setObjectName(f"mapStudioPrimitiveProperty{index + 1}CheckBox")
            editor.setProperty("dimensionKey", key)
            editor.setProperty("primitivePropertyKind", kind)
            editor.toggled.connect(self._on_primitive_property_edited)
            return editor, (editor,)
        if kind == "choice":
            editor = QtWidgets.QComboBox()
            editor.setObjectName(f"mapStudioPrimitiveProperty{index + 1}ComboBox")
            editor.setProperty("dimensionKey", key)
            editor.setProperty("primitivePropertyKind", kind)
            for label, value in self._primitive_choice_entries(property_data.get("choices")):
                editor.addItem(label, value)
            if editor.count() <= 0:
                editor.addItem(str(property_data.get("value") or ""), property_data.get("value"))
            editor.currentIndexChanged.connect(self._on_primitive_property_edited)
            return editor, (editor,)
        if kind == "vector3":
            editor = QtWidgets.QWidget()
            editor.setObjectName(f"mapStudioPrimitiveProperty{index + 1}Vector3Widget")
            editor.setProperty("dimensionKey", key)
            editor.setProperty("primitivePropertyKind", kind)
            row = QtWidgets.QHBoxLayout(editor)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            component_labels = tuple(property_data.get("component_labels") or ("X", "Y", "Z"))
            components: list[QtWidgets.QWidget] = []
            for component_index in range(3):
                component_label = QtWidgets.QLabel(
                    str(component_labels[component_index] if component_index < len(component_labels) else "XYZ"[component_index])
                )
                component_label.setObjectName(f"mapStudioPrimitiveProperty{index + 1}ComponentLabel{component_index + 1}")
                component = self._make_primitive_numeric_editor(property_data, index, component_index)
                row.addWidget(component_label)
                row.addWidget(component, 1)
                components.append(component)
            return editor, tuple(components)
        editor = self._make_primitive_numeric_editor(property_data, index)
        return editor, (editor,)

    def _set_primitive_property_control_value(self, control: dict[str, object], value: object) -> None:
        kind = str(control.get("kind") or "float")
        widgets = tuple(control.get("widgets") or ())
        if kind == "vector3":
            source = self._coerce_primitive_property_value(kind, value)
            for widget, component in zip(widgets, tuple(source)):
                widget.blockSignals(True)
                widget.setValue(float(component))
                widget.blockSignals(False)
            return
        if not widgets:
            return
        widget = widgets[0]
        widget.blockSignals(True)
        if kind == "bool":
            widget.setChecked(bool(value))
        elif kind == "choice":
            wanted_index = widget.findData(value)
            if wanted_index < 0:
                wanted_index = widget.findText(str(value))
            widget.setCurrentIndex(max(0, wanted_index))
        elif kind == "int":
            widget.setValue(int(round(float(value))))
        else:
            widget.setValue(float(value))
        widget.blockSignals(False)

    def _primitive_property_control_value(self, control: dict[str, object]) -> object:
        kind = str(control.get("kind") or "float")
        widgets = tuple(control.get("widgets") or ())
        if kind == "vector3":
            return tuple(float(widget.value()) for widget in widgets[:3])
        if not widgets:
            return None
        widget = widgets[0]
        if kind == "bool":
            return bool(widget.isChecked())
        if kind == "choice":
            return widget.currentData()
        if kind == "int":
            return int(widget.value())
        return float(widget.value())

    def _current_primitive_property_values(self) -> dict[str, object]:
        return {
            str(control.get("key") or ""): self._primitive_property_control_value(control)
            for control in self._primitive_property_controls
            if str(control.get("key") or "")
        }

    def _rebuild_primitive_property_controls(self, properties: tuple[dict[str, object], ...]) -> None:
        self._clear_primitive_property_controls()
        previous_group = ""
        for index, source in enumerate(properties):
            property_data = self._primitive_property_payload(source)
            key = str(property_data.get("key") or "")
            group = str(property_data.get("group") or "Construction")
            if group != previous_group:
                group_label = QtWidgets.QLabel(group)
                group_label.setObjectName(
                    f"mapStudioPrimitivePropertyGroup{self._primitive_property_token(group, index)}Label"
                )
                group_label.setProperty("uiRole", "sectionHeader")
                self.primitivePropertyRowsLayout.addRow(group_label)
                previous_group = group
            label_text = str(property_data.get("label") or key or f"Property {index + 1}")
            label = QtWidgets.QLabel(f"{label_text}:")
            label.setObjectName(f"mapStudioPrimitiveProperty{self._primitive_property_token(key, index)}Label")
            editor, widgets = self._create_primitive_property_editor(property_data, index)
            description = str(property_data.get("description") or "")
            if description:
                label.setToolTip(description)
                editor.setToolTip(description)
                for widget in widgets:
                    widget.setToolTip(description)
            editor.setProperty("softMinimum", property_data.get("soft_minimum"))
            editor.setProperty("softMaximum", property_data.get("soft_maximum"))
            editor.setProperty("affectsTopology", bool(property_data.get("affects_topology", False)))
            editor.setProperty("affectsUvs", bool(property_data.get("affects_uvs", False)))
            read_only = bool(property_data.get("read_only", False))
            label.setEnabled(not read_only)
            editor.setEnabled(not read_only)
            control = {
                "key": key,
                "kind": str(property_data.get("kind") or "float"),
                "label": label,
                "editor": editor,
                "widgets": widgets,
                "has_default": bool(property_data.get("has_default", False)),
                "default": property_data.get("default"),
                "read_only": read_only,
            }
            self._primitive_property_controls.append(control)
            self._primitive_dimension_controls.append((label, widgets[0] if widgets else editor))
            self.primitivePropertyRowsLayout.addRow(label, editor)
            self._set_primitive_property_control_value(control, property_data.get("value"))
        self._primitive_property_baseline = self._current_primitive_property_values()
        self._update_primitive_property_dirty_state()

    def _update_primitive_property_dirty_state(self) -> bool:
        values = self._current_primitive_property_values()
        dirty = bool(values) and values != self._primitive_property_baseline
        has_editable = any(not bool(control.get("read_only", False)) for control in self._primitive_property_controls)
        has_defaults = any(
            bool(control.get("has_default", False)) and not bool(control.get("read_only", False))
            for control in self._primitive_property_controls
        )
        self.applyPrimitiveDimensionsButton.setEnabled(dirty and has_editable)
        self.cancelPrimitiveDimensionsButton.setEnabled(dirty)
        self.resetPrimitiveDimensionsButton.setEnabled(has_defaults)
        self.cancelPrimitivePropertiesShortcut.setEnabled(dirty)
        return dirty

    def _on_primitive_property_edited(self, *_args) -> None:
        if self._update_primitive_property_dirty_state():
            self._primitive_property_preview_timer.start()
        else:
            self._cancel_active_primitive_dimensions_preview()

    def _emit_primitive_dimensions_preview(self) -> None:
        data = self._current_primitive_transform_data()
        values = self._current_primitive_property_values()
        if not data or not values or values == self._primitive_property_baseline:
            return
        identity = (
            str(data.get("room_resref") or ""),
            str(data.get("primitive_name") or ""),
        )
        self._primitive_preview_identity = identity
        self.roomPrimitiveDimensionsPreviewRequested.emit(identity[0], identity[1], values)

    def _cancel_active_primitive_dimensions_preview(self) -> None:
        self._primitive_property_preview_timer.stop()
        identity = self._primitive_preview_identity
        self._primitive_preview_identity = None
        if identity is not None:
            self.roomPrimitiveDimensionsPreviewCancelled.emit(identity[0], identity[1])

    def _reset_primitive_properties_to_defaults(self) -> None:
        self._cancel_active_primitive_dimensions_preview()
        for control in self._primitive_property_controls:
            if bool(control.get("has_default", False)) and not bool(control.get("read_only", False)):
                self._set_primitive_property_control_value(control, control.get("default"))
        if self._update_primitive_property_dirty_state():
            self._primitive_property_preview_timer.start()

    def _cancel_primitive_property_changes(self) -> None:
        self._cancel_active_primitive_dimensions_preview()
        for control in self._primitive_property_controls:
            key = str(control.get("key") or "")
            if key in self._primitive_property_baseline:
                self._set_primitive_property_control_value(control, self._primitive_property_baseline[key])
        self._update_primitive_property_dirty_state()

    def _on_primitive_selection_changed(self, *_args) -> None:
        self._cancel_active_primitive_dimensions_preview()
        self._update_primitive_transform_controls()

    def _update_primitive_dimension_controls(self, data: dict | None = None) -> None:
        current = self._current_primitive_transform_data() if data is None else data
        properties = tuple(current.get("properties") or current.get("dimensions") or ()) if current else ()
        self._rebuild_primitive_property_controls(tuple(dict(item) for item in properties))
        if not current:
            self.primitiveDimensionHintLabel.setText("Select an authored primitive to edit its construction inputs.")
        elif not properties:
            self.primitiveDimensionHintLabel.setText("This primitive has no editable construction inputs.")
        else:
            self.primitiveDimensionHintLabel.setText(
                f"{len(properties)} construction input(s). Changes preview after a short pause; "
                "Apply commits one topology rebuild. Cancel or Esc discards unapplied changes."
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

    def _emit_primitive_dimensions(self) -> None:
        data = self._current_primitive_transform_data()
        if not data:
            return
        values = self._current_primitive_property_values()
        if values:
            self._primitive_property_preview_timer.stop()
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

    def _emit_separate_composition_primitive(self) -> None:
        data = self._current_primitive_transform_data()
        if not data:
            return
        self.roomPrimitiveSeparateRequested.emit(
            str(data.get("room_resref") or ""),
            str(data.get("primitive_name") or ""),
            self.roomPrimitiveSeparateResultLineEdit.text().strip(),
        )

    def set_gameplay_placement_kinds(self, kinds) -> None:
        """Populate the gameplay placement kind selector from the controller."""

        self.gameplayPlacementKindComboBox.clear()
        for kind in kinds or ():
            value = str(kind or "").strip()
            if value:
                label = {
                    "placeable": "Placeables + Animated Doors",
                    "door": "Doors (UTD)",
                }.get(value.lower(), value.replace("_", " ").title())
                self.gameplayPlacementKindComboBox.addItem(label, value)
        if self.gameplayPlacementKindComboBox.count() <= 0:
            self.gameplayPlacementKindComboBox.addItem("Placeable", "placeable")
        self._update_gameplay_supported_kinds_label()
        self._apply_gameplay_palette_filter()

    def set_module_entry_point(self, entry) -> None:
        """Show the current authored module IFO player start."""

        enabled = entry is not None
        for widget in (
            self.entryPointAreaLineEdit,
            self.entryPointPosXSpinBox,
            self.entryPointPosYSpinBox,
            self.entryPointPosZSpinBox,
            self.entryPointFacingSpinBox,
            self.applyEntryPointButton,
        ):
            widget.setEnabled(enabled)
        if not enabled:
            self.entryPointAreaLineEdit.blockSignals(True)
            self.entryPointAreaLineEdit.setText("")
            self.entryPointAreaLineEdit.blockSignals(False)
            self._fill_vec3(
                (self.entryPointPosXSpinBox, self.entryPointPosYSpinBox, self.entryPointPosZSpinBox),
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 0.0),
            )
            self.entryPointFacingSpinBox.blockSignals(True)
            self.entryPointFacingSpinBox.setValue(0.0)
            self.entryPointFacingSpinBox.blockSignals(False)
            self.entryPointStatusLabel.setText("Entry point: create or load an authored module first.")
            return
        area = str(getattr(entry, "area_resref", "") or "")
        position = tuple(getattr(entry, "position", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))
        facing = float(getattr(entry, "facing", 0.0) or 0.0)
        facing_degrees = math.degrees(facing)
        self.entryPointAreaLineEdit.blockSignals(True)
        self.entryPointAreaLineEdit.setText(area)
        self.entryPointAreaLineEdit.blockSignals(False)
        self._fill_vec3(
            (self.entryPointPosXSpinBox, self.entryPointPosYSpinBox, self.entryPointPosZSpinBox),
            position,
            (0.0, 0.0, 0.0),
        )
        self.entryPointFacingSpinBox.blockSignals(True)
        self.entryPointFacingSpinBox.setValue(facing_degrees)
        self.entryPointFacingSpinBox.blockSignals(False)
        self.entryPointStatusLabel.setText(
            f"Entry point: {area or '(area not set)'} at {position[:3]}, facing {facing_degrees:.1f} deg."
        )

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
        matches: list[object] = []
        for entry in self._gameplay_palette_entries:
            entry_kind = self._entry_value(entry, "kind").lower()
            entry_family = self._entry_value(entry, "authoring_family", entry_kind).lower()
            haystack = " ".join(
                self._entry_value(entry, key)
                for key in ("template_resref", "label", "category", "source")
            ).lower()
            if kind and entry_kind != kind and entry_family != kind:
                continue
            if needle and needle not in haystack:
                continue
            matches.append(entry)
        visible_matches = matches[: self._gameplay_palette_page_limit]
        for entry in visible_matches:
            label = self._entry_value(entry, "label") or self._entry_value(entry, "template_resref")
            self.gameplayPaletteComboBox.addItem(label, entry)
        if not visible_matches:
            self.gameplayPaletteComboBox.addItem("No compatible game-library resources", None)
        self.gameplayPaletteComboBox.blockSignals(False)
        if len(matches) > len(visible_matches):
            self.gameplayPaletteResultLabel.setText(
                f"Showing {len(visible_matches):,} of {len(matches):,} matches. "
                "Type a name or resref to narrow the list."
            )
        else:
            self.gameplayPaletteResultLabel.setText(
                f"{len(matches):,} matching asset{'s' if len(matches) != 1 else ''}."
            )
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
        self._update_gameplay_kind_detail_label()
        self._emit_gameplay_placement_status()

    @staticmethod
    def _gameplay_kind_label(value: str) -> str:
        labels = {
            "placeable": "placeables",
            "creature": "creatures",
            "door": "doors",
            "waypoint": "waypoints",
            "trigger": "triggers",
            "encounter": "encounters",
            "sound": "sounds",
            "camera": "cameras",
            "store": "stores/merchants",
            "merchant": "stores/merchants",
        }
        return labels.get(str(value or "").strip().lower(), str(value or "").replace("_", " "))

    def _update_gameplay_supported_kinds_label(self) -> None:
        if not hasattr(self, "gameplaySupportedKindsLabel"):
            return
        labels: list[str] = []
        for index in range(self.gameplayPlacementKindComboBox.count()):
            kind = str(self.gameplayPlacementKindComboBox.itemData(index) or "").strip().lower()
            label = self._gameplay_kind_label(kind)
            if label and label not in labels:
                labels.append(label)
        if not labels:
            labels = ["placeables"]
        text = ", ".join(labels)
        self.gameplaySupportedKindsLabel.setText(
            f"Placement types: {text}. Spatial resources appear as viewport markers; stores/merchants are module-level."
        )

    def _update_gameplay_kind_detail_label(self) -> None:
        if not hasattr(self, "gameplayKindDetailLabel"):
            return
        kind = str(self.gameplayPlacementKindComboBox.currentData() or "").strip().lower()
        details = {
            "placeable": "Placeables: UTP objects and animated UTD doors share the staging palette. Resolved assets render their actual model; unresolved assets keep an honest marker.",
            "creature": "Creature: uses a UTC template, creates a viewport marker, and exports into the module GIT Creature List.",
            "door": "Animated door: uses a UTD template, resolves genericdoors.2da model geometry for staging, and remains a GIT Door List object with transition controls.",
            "waypoint": "Waypoint: creates a named navigation/start marker and can be used for transitions or spawn/layout checks.",
            "trigger": "Trigger: uses a UTT template, creates generated trigger geometry, and can be configured as a transition.",
            "encounter": "Encounter: uses a UTE template and creates a spatial encounter marker in the module.",
            "sound": "Sound: uses a UTS template and creates a spatial ambient/audio marker in the module.",
            "camera": "Camera: creates a camera marker; the template field can stay empty.",
            "store": "Store/merchant: uses a UTM template and exports as a module-level store without a viewport marker.",
            "merchant": "Store/merchant: uses a UTM template and exports as a module-level store without a viewport marker.",
        }
        self.gameplayKindDetailLabel.setText(
            details.get(kind, "Choose a KOTOR resource kind, then select or type a template resref before adding it.")
        )

    def _update_gameplay_palette_hint(self) -> None:
        entry = self._current_palette_entry()
        if entry is None:
            if self._gameplay_palette_entries:
                self.gameplayPaletteHintLabel.setText("No matching resources for the current kind/search. You can still type a template resref manually.")
            else:
                self.gameplayPaletteHintLabel.setText("Scan the Game Library to search for creatures, placeables, doors, triggers, encounters, cameras, sounds, waypoints, and stores/merchants.")
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
            math.radians(float(self.gameplayBearingSpinBox.value())),
        )

    def _emit_module_entry_point(self) -> None:
        self.moduleEntryPointRequested.emit(
            self.entryPointAreaLineEdit.text().strip(),
            float(self.entryPointPosXSpinBox.value()),
            float(self.entryPointPosYSpinBox.value()),
            float(self.entryPointPosZSpinBox.value()),
            math.radians(float(self.entryPointFacingSpinBox.value())),
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
        self.editScriptHookButton.setEnabled(has_field)
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

    def _emit_edit_script_hook(self) -> None:
        """Open the selected hook without coupling this presentation panel to a studio window."""

        field_name = self._current_script_hook_field()
        if field_name:
            self.scriptEditorRequested.emit(
                self._current_script_hook_scope(),
                field_name,
                self.scriptHookResrefLineEdit.text().strip(),
            )

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
        is_split_x = operation == "split_x"
        is_split_y = operation == "split_y"
        self.cutCenterXSpinBox.setEnabled(is_cut or is_split_x)
        self.cutCenterYSpinBox.setEnabled(is_cut or is_split_y)
        self.cutWidthSpinBox.setEnabled(is_cut)
        self.cutDepthSpinBox.setEnabled(is_cut)
        self.operationDistanceSpinBox.setEnabled(operation in {"bevel", "inset", "edge_extrude"})
        self.operationEdgeIndexSpinBox.setEnabled(operation == "edge_extrude")

    def _emit_room_operation(self) -> None:
        operation = str(self.roomOperationComboBox.currentData() or "").strip()
        if operation:
            self.roomOperationRequested.emit(
                operation,
                float(self.operationDistanceSpinBox.value()),
                int(self.operationEdgeIndexSpinBox.value()),
                float(self.cutCenterXSpinBox.value()),
                float(self.cutCenterYSpinBox.value()),
                float(self.cutWidthSpinBox.value()),
                float(self.cutDepthSpinBox.value()),
            )
