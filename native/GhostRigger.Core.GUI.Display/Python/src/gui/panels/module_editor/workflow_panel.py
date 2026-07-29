"""Map Studio workflow checklist panel.

This widget is presentation-only. It displays project/readiness state produced
by the Level Editor controller and keeps module authoring policy in core.
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtWidgets


class MapStudioWorkflowPanel(QtWidgets.QWidget):
    """Compact workflow spine for the Map Studio Level Editor."""

    newProjectRequested = QtCore.Signal()
    openProjectRequested = QtCore.Signal()
    saveProjectRequested = QtCore.Signal()
    renameSelectedRequested = QtCore.Signal()
    duplicateSelectedRequested = QtCore.Signal()
    deleteSelectedRequested = QtCore.Signal()
    focusSelectedRequested = QtCore.Signal()
    builderRequested = QtCore.Signal()
    geometryToolsRequested = QtCore.Signal()
    starterRoomRequested = QtCore.Signal()
    doorwayBlockoutRequested = QtCore.Signal()
    corridorRequested = QtCore.Signal()
    starterTerrainRequested = QtCore.Signal()
    terrainToolsRequested = QtCore.Signal()
    lightingToolsRequested = QtCore.Signal()
    placementToolsRequested = QtCore.Signal()
    scriptToolsRequested = QtCore.Signal()
    testPlaceableRequested = QtCore.Signal()
    walkmeshToolsRequested = QtCore.Signal()
    validateRequested = QtCore.Signal()
    stageRequested = QtCore.Signal()
    installRequested = QtCore.Signal()
    launchHandoffRequested = QtCore.Signal()
    proofRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MapStudioWorkflowPanel")
        self.setMinimumWidth(0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(5)

        self.header_label = QtWidgets.QLabel("Build & test")
        self.header_label.setObjectName("mapStudioWorkflowHeaderLabel")
        self.header_label.setWordWrap(True)
        root.addWidget(self.header_label)

        self.project_label = QtWidgets.QLabel("Project: No KMAP open")
        self.project_label.setObjectName("mapStudioWorkflowProjectLabel")
        self.project_label.setWordWrap(True)
        root.addWidget(self.project_label)

        self.target_game_label = QtWidgets.QLabel("Target game: not selected")
        self.target_game_label.setObjectName("mapStudioWorkflowTargetGameLabel")
        self.target_game_label.setWordWrap(True)
        root.addWidget(self.target_game_label)

        self.capability_label = QtWidgets.QLabel("Capability: Draft")
        self.capability_label.setObjectName("mapStudioWorkflowCapabilityLabel")
        self.capability_label.setWordWrap(True)
        root.addWidget(self.capability_label)

        self.test_state_label = QtWidgets.QLabel("Test state: Not staged")
        self.test_state_label.setObjectName("mapStudioWorkflowTestStateLabel")
        self.test_state_label.setWordWrap(True)
        root.addWidget(self.test_state_label)

        self.purpose_label = QtWidgets.QLabel(
            "The white/gray grid is editor workspace, not usable floor. Start with an interior Room or an exterior Terrain Surface; both generate matching WOK automatically."
        )
        self.purpose_label.setObjectName("mapStudioWorkflowPurposeLabel")
        self.purpose_label.setWordWrap(True)
        root.addWidget(self.purpose_label)

        self.start_here_group = QtWidgets.QGroupBox("Start here: choose the kind of level")
        self.start_here_group.setObjectName("mapStudioWorkflowStartHereGroup")
        start_here_layout = QtWidgets.QVBoxLayout(self.start_here_group)
        self.start_here_label = QtWidgets.QLabel(
            "Interior rooms include floor, walls, and WOK. Exterior terrain includes visible ground and WOK. "
            "Add doors to rooms and drag another room or vanilla module to the doorway magnet to connect them."
        )
        self.start_here_label.setObjectName("mapStudioWorkflowStartHereLabel")
        self.start_here_label.setWordWrap(True)
        start_here_layout.addWidget(self.start_here_label)
        start_here_buttons = QtWidgets.QHBoxLayout()
        self.starter_room_button = QtWidgets.QPushButton("Interior: Create Room")
        self.starter_room_button.setObjectName("mapStudioWorkflowStarterRoomButton")
        self.starter_room_button.setToolTip(
            "Create a usable interior room with a generated floor and matching walkmesh."
        )
        self.starter_terrain_button = QtWidgets.QPushButton("Exterior: Create Terrain")
        self.starter_terrain_button.setObjectName("mapStudioWorkflowStarterTerrainButton")
        self.starter_terrain_button.setToolTip(
            "Create actual exterior ground with a matching generated walkmesh. Drag matching terrain edges together to weld them."
        )
        self.starter_room_button.clicked.connect(self.starterRoomRequested.emit)
        self.starter_terrain_button.clicked.connect(self.starterTerrainRequested.emit)
        start_here_buttons.addWidget(self.starter_room_button)
        start_here_buttons.addWidget(self.starter_terrain_button)
        start_here_layout.addLayout(start_here_buttons)
        root.addWidget(self.start_here_group)

        self.advanced_details_toggle = QtWidgets.QToolButton(self)
        self.advanced_details_toggle.setObjectName("mapStudioWorkflowAdvancedDetailsButton")
        self.advanced_details_toggle.setText("Advanced workflow details")
        self.advanced_details_toggle.setCheckable(True)
        self.advanced_details_toggle.setChecked(False)
        self.advanced_details_toggle.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.advanced_details_toggle.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        root.addWidget(self.advanced_details_toggle)

        self.smoke_test_label = QtWidgets.QLabel(
            "First playable map smoke test: start with one small KMAP module, one starter room, "
            "one test placeable, validation, staged install, warp test, and recorded proof. "
            "Treat larger maps as experimental until this path passes in-game."
        )
        self.smoke_test_label.setObjectName("mapStudioWorkflowSmokeTestLabel")
        self.smoke_test_label.setWordWrap(True)
        root.addWidget(self.smoke_test_label)

        self.smoke_test_recipe_table = QtWidgets.QTableWidget(0, 3)
        self.smoke_test_recipe_table.setObjectName("mapStudioWorkflowSmokeTestRecipeTable")
        self.smoke_test_recipe_table.setHorizontalHeaderLabels(("Step", "Action", "Proof"))
        self.smoke_test_recipe_table.verticalHeader().setVisible(False)
        self.smoke_test_recipe_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.smoke_test_recipe_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.smoke_test_recipe_table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.smoke_test_recipe_table.setWordWrap(True)
        self.smoke_test_recipe_table.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._set_smoke_test_recipe(
            (
                (
                    "Project",
                    "New KMAP",
                    "K1/K2 target game and module root are selected.",
                ),
                (
                    "Geometry",
                    "Create Room or Terrain Surface",
                    "Usable geometry and its matching WOK exist before resource placement.",
                ),
                (
                    "Gameplay",
                    "Add Test Placeable",
                    "At least one authored placement is visible and selectable.",
                ),
                (
                    "Validation",
                    "Validate",
                    "Blocking fixes are shown before export/install.",
                ),
                (
                    "Install",
                    "Stage or Install for Game Test",
                    "A safe staged package and warp handoff are produced.",
                ),
                (
                    "Game proof",
                    "warp <module> and Record Proof",
                    "Only then call it game-tested.",
                ),
            )
        )
        root.addWidget(self.smoke_test_recipe_table)

        self.authoring_label = QtWidgets.QLabel("Authoring: Start in Builder")
        self.authoring_label.setObjectName("mapStudioWorkflowAuthoringLabel")
        self.authoring_label.setWordWrap(True)
        root.addWidget(self.authoring_label)

        self.active_context_label = QtWidgets.QLabel("Active tool: none selected")
        self.active_context_label.setObjectName("mapStudioWorkflowActiveContextLabel")
        self.active_context_label.setWordWrap(True)
        root.addWidget(self.active_context_label)

        self.mode_label = QtWidgets.QLabel("Mode: Object")
        self.mode_label.setObjectName("mapStudioWorkflowModeLabel")
        self.mode_label.setWordWrap(True)
        root.addWidget(self.mode_label)

        self.editing_target_label = QtWidgets.QLabel("Editing: rooms, placements, and module objects")
        self.editing_target_label.setObjectName("mapStudioWorkflowEditingTargetLabel")
        self.editing_target_label.setWordWrap(True)
        root.addWidget(self.editing_target_label)

        self.selection_label = QtWidgets.QLabel("Selected: none")
        self.selection_label.setObjectName("mapStudioWorkflowSelectionLabel")
        self.selection_label.setWordWrap(True)
        root.addWidget(self.selection_label)

        self.resources_label = QtWidgets.QLabel("Runtime resources: ARE/GIT/IFO/LYT/VIS/PTH/WOK/MDL/MDX")
        self.resources_label.setObjectName("mapStudioWorkflowResourcesLabel")
        self.resources_label.setWordWrap(True)
        root.addWidget(self.resources_label)

        self.missing_resources_label = QtWidgets.QLabel("Required resources: Not checked")
        self.missing_resources_label.setObjectName("mapStudioWorkflowMissingResourcesLabel")
        self.missing_resources_label.setWordWrap(True)
        root.addWidget(self.missing_resources_label)

        self.geometry_label = QtWidgets.QLabel("Geometry: Not checked")
        self.geometry_label.setObjectName("mapStudioWorkflowGeometryLabel")
        self.geometry_label.setWordWrap(True)
        root.addWidget(self.geometry_label)

        self.walkmesh_label = QtWidgets.QLabel("Walkmesh: Not checked")
        self.walkmesh_label.setObjectName("mapStudioWorkflowWalkmeshLabel")
        self.walkmesh_label.setWordWrap(True)
        root.addWidget(self.walkmesh_label)

        self.visibility_label = QtWidgets.QLabel("VIS visibility: Not checked")
        self.visibility_label.setObjectName("mapStudioWorkflowVisibilityLabel")
        self.visibility_label.setWordWrap(True)
        root.addWidget(self.visibility_label)

        self.lighting_label = QtWidgets.QLabel("Lighting/lightmaps: Not checked")
        self.lighting_label.setObjectName("mapStudioWorkflowLightingLabel")
        self.lighting_label.setWordWrap(True)
        root.addWidget(self.lighting_label)

        self.placement_label = QtWidgets.QLabel("Resource placement: Not checked")
        self.placement_label.setObjectName("mapStudioWorkflowPlacementLabel")
        self.placement_label.setWordWrap(True)
        root.addWidget(self.placement_label)

        self.layout_label = QtWidgets.QLabel("Spawn/layout: Not checked")
        self.layout_label.setObjectName("mapStudioWorkflowLayoutLabel")
        self.layout_label.setWordWrap(True)
        root.addWidget(self.layout_label)

        self.transitions_label = QtWidgets.QLabel("Transitions: Not checked")
        self.transitions_label.setObjectName("mapStudioWorkflowTransitionsLabel")
        self.transitions_label.setWordWrap(True)
        root.addWidget(self.transitions_label)

        self.scripts_label = QtWidgets.QLabel("Scripts: Not checked")
        self.scripts_label.setObjectName("mapStudioWorkflowScriptsLabel")
        self.scripts_label.setWordWrap(True)
        root.addWidget(self.scripts_label)

        self.validation_label = QtWidgets.QLabel("Validation: Not checked")
        self.validation_label.setObjectName("mapStudioWorkflowValidationLabel")
        self.validation_label.setWordWrap(True)
        root.addWidget(self.validation_label)

        self.export_label = QtWidgets.QLabel("Export/install: Not ready")
        self.export_label.setObjectName("mapStudioWorkflowExportLabel")
        self.export_label.setWordWrap(True)
        root.addWidget(self.export_label)

        self.export_job_label = QtWidgets.QLabel("ExportJob: No package transaction recorded")
        self.export_job_label.setObjectName("mapStudioWorkflowExportJobLabel")
        self.export_job_label.setWordWrap(True)
        root.addWidget(self.export_job_label)

        self.proof_label = QtWidgets.QLabel("Game proof: Required before game-ready")
        self.proof_label.setObjectName("mapStudioWorkflowProofLabel")
        self.proof_label.setWordWrap(True)
        root.addWidget(self.proof_label)

        self.next_action_label = QtWidgets.QLabel("")
        self.next_action_label.setObjectName("mapStudioWorkflowNextActionLabel")
        self.next_action_label.setWordWrap(True)
        root.addWidget(self.next_action_label)

        project_actions = QtWidgets.QHBoxLayout()
        project_actions.setContentsMargins(0, 4, 0, 0)
        project_actions.setSpacing(4)
        self.new_kmap_button = QtWidgets.QPushButton("New KMAP")
        self.new_kmap_button.setObjectName("mapStudioWorkflowNewKmapButton")
        self.open_kmap_button = QtWidgets.QPushButton("Open KMAP")
        self.open_kmap_button.setObjectName("mapStudioWorkflowOpenKmapButton")
        self.save_kmap_button = QtWidgets.QPushButton("Save KMAP")
        self.save_kmap_button.setObjectName("mapStudioWorkflowSaveKmapButton")
        self.new_kmap_button.clicked.connect(self.newProjectRequested.emit)
        self.open_kmap_button.clicked.connect(self.openProjectRequested.emit)
        self.save_kmap_button.clicked.connect(self.saveProjectRequested.emit)
        project_actions.addWidget(self.new_kmap_button)
        project_actions.addWidget(self.open_kmap_button)
        project_actions.addWidget(self.save_kmap_button)
        root.addLayout(project_actions)

        self.selection_actions_widget = QtWidgets.QWidget(self)
        selection_actions = QtWidgets.QHBoxLayout(self.selection_actions_widget)
        selection_actions.setContentsMargins(0, 0, 0, 0)
        selection_actions.setSpacing(4)
        self.rename_selected_button = QtWidgets.QPushButton("Rename Selected")
        self.rename_selected_button.setObjectName("mapStudioWorkflowRenameSelectedButton")
        self.duplicate_selected_button = QtWidgets.QPushButton("Duplicate Selected")
        self.duplicate_selected_button.setObjectName("mapStudioWorkflowDuplicateSelectedButton")
        self.delete_selected_button = QtWidgets.QPushButton("Delete Selected")
        self.delete_selected_button.setObjectName("mapStudioWorkflowDeleteSelectedButton")
        self.focus_selected_button = QtWidgets.QPushButton("Focus Selected")
        self.focus_selected_button.setObjectName("mapStudioWorkflowFocusSelectedButton")
        self.rename_selected_button.clicked.connect(self.renameSelectedRequested.emit)
        self.duplicate_selected_button.clicked.connect(self.duplicateSelectedRequested.emit)
        self.delete_selected_button.clicked.connect(self.deleteSelectedRequested.emit)
        self.focus_selected_button.clicked.connect(self.focusSelectedRequested.emit)
        selection_actions.addWidget(self.rename_selected_button)
        selection_actions.addWidget(self.duplicate_selected_button)
        selection_actions.addWidget(self.delete_selected_button)
        selection_actions.addWidget(self.focus_selected_button)
        root.addWidget(self.selection_actions_widget)
        self.set_selection_context("")

        primary_actions = QtWidgets.QGridLayout()
        primary_actions.setContentsMargins(0, 4, 0, 0)
        primary_actions.setHorizontalSpacing(4)
        primary_actions.setVerticalSpacing(4)
        self.secondary_actions_widget = QtWidgets.QWidget(self)
        actions = QtWidgets.QGridLayout(self.secondary_actions_widget)
        actions.setContentsMargins(0, 4, 0, 0)
        actions.setHorizontalSpacing(4)
        actions.setVerticalSpacing(4)
        self.open_builder_button = QtWidgets.QPushButton("Open Builder")
        self.open_builder_button.setObjectName("mapStudioWorkflowOpenBuilderButton")
        self.geometry_tools_button = QtWidgets.QPushButton("Open Geometry Tools")
        self.geometry_tools_button.setObjectName("mapStudioWorkflowGeometryToolsButton")
        self.doorway_blockout_button = QtWidgets.QPushButton("Create Doorway Blockout")
        self.doorway_blockout_button.setObjectName("mapStudioWorkflowDoorwayBlockoutButton")
        self.corridor_button = QtWidgets.QPushButton("Create Corridor")
        self.corridor_button.setObjectName("mapStudioWorkflowCorridorButton")
        self.terrain_tools_button = QtWidgets.QPushButton("Open Terrain Tools")
        self.terrain_tools_button.setObjectName("mapStudioWorkflowTerrainToolsButton")
        self.lighting_tools_button = QtWidgets.QPushButton("Open Lighting Tools")
        self.lighting_tools_button.setObjectName("mapStudioWorkflowLightingToolsButton")
        self.placement_tools_button = QtWidgets.QPushButton("Open Placement Tools")
        self.placement_tools_button.setObjectName("mapStudioWorkflowPlacementToolsButton")
        self.script_tools_button = QtWidgets.QPushButton("Open Script Hooks")
        self.script_tools_button.setObjectName("mapStudioWorkflowScriptToolsButton")
        self.test_placeable_button = QtWidgets.QPushButton("Add Test Placeable")
        self.test_placeable_button.setObjectName("mapStudioWorkflowTestPlaceableButton")
        self.walkmesh_tools_button = QtWidgets.QPushButton("Open Walkmesh Tools")
        self.walkmesh_tools_button.setObjectName("mapStudioWorkflowWalkmeshToolsButton")
        self.validate_button = QtWidgets.QPushButton("Validate")
        self.validate_button.setObjectName("mapStudioWorkflowValidateButton")
        self.stage_button = QtWidgets.QPushButton("Stage for Game Test")
        self.stage_button.setObjectName("mapStudioWorkflowStageButton")
        self.install_button = QtWidgets.QPushButton("Install for Game Test")
        self.install_button.setObjectName("mapStudioWorkflowInstallButton")
        self.launch_handoff_button = QtWidgets.QPushButton("Open Warp Test Handoff")
        self.launch_handoff_button.setObjectName("mapStudioWorkflowLaunchHandoffButton")
        self.proof_button = QtWidgets.QPushButton("Record Proof")
        self.proof_button.setObjectName("mapStudioWorkflowProofButton")
        self.open_builder_button.clicked.connect(self.builderRequested.emit)
        self.geometry_tools_button.clicked.connect(self.geometryToolsRequested.emit)
        self.doorway_blockout_button.clicked.connect(self.doorwayBlockoutRequested.emit)
        self.corridor_button.clicked.connect(self.corridorRequested.emit)
        self.terrain_tools_button.clicked.connect(self.terrainToolsRequested.emit)
        self.lighting_tools_button.clicked.connect(self.lightingToolsRequested.emit)
        self.placement_tools_button.clicked.connect(self.placementToolsRequested.emit)
        self.script_tools_button.clicked.connect(self.scriptToolsRequested.emit)
        self.test_placeable_button.clicked.connect(self.testPlaceableRequested.emit)
        self.walkmesh_tools_button.clicked.connect(self.walkmeshToolsRequested.emit)
        self.validate_button.clicked.connect(self.validateRequested.emit)
        self.stage_button.clicked.connect(self.stageRequested.emit)
        self.install_button.clicked.connect(self.installRequested.emit)
        self.launch_handoff_button.clicked.connect(self.launchHandoffRequested.emit)
        self.proof_button.clicked.connect(self.proofRequested.emit)
        primary_actions.addWidget(self.open_builder_button, 0, 0)
        primary_actions.addWidget(self.placement_tools_button, 0, 1)
        primary_actions.addWidget(self.validate_button, 1, 0)
        primary_actions.addWidget(self.stage_button, 1, 1)
        primary_actions.addWidget(self.install_button, 2, 0)
        primary_actions.addWidget(self.launch_handoff_button, 2, 1)
        primary_actions.addWidget(self.proof_button, 3, 0, 1, 2)
        root.addLayout(primary_actions)

        actions.addWidget(self.geometry_tools_button, 0, 0)
        actions.addWidget(self.doorway_blockout_button, 1, 0)
        actions.addWidget(self.corridor_button, 1, 1)
        actions.addWidget(self.terrain_tools_button, 2, 1)
        actions.addWidget(self.lighting_tools_button, 3, 0)
        actions.addWidget(self.script_tools_button, 3, 1)
        actions.addWidget(self.walkmesh_tools_button, 4, 0)
        actions.addWidget(self.test_placeable_button, 4, 1)
        root.addWidget(self.secondary_actions_widget)

        self._advanced_detail_widgets = (
            self.smoke_test_label,
            self.smoke_test_recipe_table,
            self.authoring_label,
            self.active_context_label,
            self.mode_label,
            self.editing_target_label,
            self.selection_label,
            self.resources_label,
            self.missing_resources_label,
            self.geometry_label,
            self.walkmesh_label,
            self.visibility_label,
            self.lighting_label,
            self.placement_label,
            self.layout_label,
            self.transitions_label,
            self.scripts_label,
            self.validation_label,
            self.export_label,
            self.export_job_label,
            self.proof_label,
            self.selection_actions_widget,
            self.secondary_actions_widget,
            self.install_button,
            self.launch_handoff_button,
            self.proof_button,
        )
        for button in self.findChildren(QtWidgets.QPushButton):
            button.setMinimumWidth(0)
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Ignored,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
        self.advanced_details_toggle.toggled.connect(self._set_advanced_details_visible)
        self._set_advanced_details_visible(False)

    def _set_advanced_details_visible(self, visible: bool) -> None:
        """Keep expert diagnostics available without overwhelming the default workflow."""

        for widget in self._advanced_detail_widgets:
            widget.setVisible(bool(visible))
        self.advanced_details_toggle.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if visible else QtCore.Qt.ArrowType.RightArrow
        )

    def _set_smoke_test_recipe(self, rows: tuple[tuple[str, str, str], ...]) -> None:
        self.smoke_test_recipe_table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column_index, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
                self.smoke_test_recipe_table.setItem(row_index, column_index, item)
        header = self.smoke_test_recipe_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.smoke_test_recipe_table.verticalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.smoke_test_recipe_table.resizeRowsToContents()

    def set_state(self, project: Any | None, readiness: Any | None) -> None:
        """Render workflow state without mutating the project."""

        self.new_kmap_button.setEnabled(True)
        self.open_kmap_button.setEnabled(True)
        self.save_kmap_button.setEnabled(project is not None)

        if project is None:
            self._set_action_enabled(False, can_place=False, can_export=False, can_proof=False)
            self.project_label.setText("Project: No KMAP open")
            self.target_game_label.setText("Target game: not selected")
            self.capability_label.setText("Capability: Draft. Create or open a KMAP before authoring.")
            self.test_state_label.setText("Test state: Not staged. Create or open a KMAP before export testing.")
            self.authoring_label.setText("Authoring: Create or open a KMAP, then use Builder to add terrain or rooms.")
            self.active_context_label.setText("Active tool: none selected")
            self.resources_label.setText("Runtime resources: ARE/GIT/IFO/LYT/VIS/PTH/WOK/MDL/MDX")
            self.missing_resources_label.setText("Required resources: open a KMAP before checking module files.")
            self.geometry_label.setText("Geometry: Create or open a KMAP before authoring rooms.")
            self.walkmesh_label.setText("Walkmesh: Create authored rooms before generating walkable WOK faces.")
            self.visibility_label.setText("VIS visibility: Create authored rooms before connecting room visibility.")
            self.lighting_label.setText("Lighting/lightmaps: Create authored rooms before planning room lights or lightmaps.")
            self.placement_label.setText("Resource placement: Create authored geometry before placing KOTOR resources.")
            self.layout_label.setText("Spawn/layout: Create authored geometry before placing the player start or gameplay objects.")
            self.transitions_label.setText("Transitions: Add doors, triggers, or waypoints when this map needs exits.")
            self.scripts_label.setText("Scripts: Add module or area script hooks when this map needs scripted behavior.")
            self.validation_label.setText("Validation: Not checked")
            self.export_label.setText("Export/install: Not ready")
            self.export_job_label.setText("ExportJob: No package transaction recorded")
            self.proof_label.setText("Game proof: Required before game-ready")
            self.next_action_label.setText("Next: create or open a KMAP project.")
            return

        self._set_action_enabled(True, can_place=False, can_export=False, can_proof=False)
        project_name = str(getattr(project, "name", "") or "(unnamed)")
        game = str(getattr(project, "game", "") or "(game not selected)")
        dirty = " *" if bool(getattr(project, "dirty", False)) else ""
        self.project_label.setText(f"Project: {project_name}{dirty} ({game})")
        self.target_game_label.setText(f"Target game: {game}")
        self.capability_label.setText("Capability: Draft. Validate authored content before staging.")
        self.test_state_label.setText("Test state: Editing draft. Validate and stage before calling this game-ready.")

        extra_sections = dict(getattr(project, "extra_sections", {}) or {})
        has_authored_module = "authored_module" in extra_sections
        if has_authored_module:
            self.authoring_label.setText("Authoring: Authored Map Studio module stored in this KMAP.")
            self.resources_label.setText("Runtime resources: ARE/GIT/IFO/LYT/VIS/PTH plus room WOK/MDL/MDX are tracked for export.")
            self.missing_resources_label.setText("Required resources: waiting for readiness check.")
            self.geometry_label.setText("Geometry: Waiting for readiness check.")
            self.walkmesh_label.setText("Walkmesh: Waiting for readiness check.")
            self.visibility_label.setText("VIS visibility: Waiting for readiness check.")
            self.lighting_label.setText("Lighting/lightmaps: Waiting for readiness check.")
            self.placement_label.setText("Resource placement: Waiting for readiness check.")
            self.layout_label.setText("Spawn/layout: Waiting for readiness check.")
            self.transitions_label.setText("Transitions: Waiting for readiness check.")
            self.scripts_label.setText("Scripts: Waiting for readiness check.")
        else:
            self.authoring_label.setText("Authoring: No authored module yet. Use Builder to create terrain, rooms, or a dev-test map.")
            self.resources_label.setText("Runtime resources: create authored terrain or rooms before packaging ARE/GIT/IFO/LYT/VIS/PTH/WOK/MDL/MDX.")
            self.missing_resources_label.setText("Required resources: no authored room resources yet.")
            self.geometry_label.setText("Geometry: Use Builder to create room, corridor, doorway, or terrain geometry.")
            self.walkmesh_label.setText("Walkmesh: No authored room yet. Create geometry before checking walkability.")
            self.visibility_label.setText("VIS visibility: No authored room yet. Add rooms before authoring LYT/VIS visibility.")
            self.lighting_label.setText("Lighting/lightmaps: No authored room yet. Create geometry before planning room lights.")
            self.placement_label.setText("Resource placement: Use authored placement tools for creatures, placeables, doors, triggers, encounters, cameras, sounds, merchants, and waypoints.")
            self.layout_label.setText("Spawn/layout: Create an authored module, then place the player start and gameplay objects.")
            self.transitions_label.setText("Transitions: Add doors, triggers, or waypoints when this map needs exits.")
            self.scripts_label.setText("Scripts: Add module or area script hooks when this map needs scripted behavior.")

        if readiness is None:
            self._set_action_enabled(True, can_place=has_authored_module, can_export=False, can_proof=False)
            self.validation_label.setText("Validation: Not checked")
            self.export_label.setText("Export/install: Not ready")
            self.export_job_label.setText("ExportJob: Waiting for authored content and validation")
            self.proof_label.setText("Game proof: Required before game-ready")
            self.next_action_label.setText("Next: create authored content in Builder.")
            return

        stage = str(getattr(readiness, "capability_stage", "blocked") or "blocked").replace("_", " ")
        preview_status = str(getattr(readiness, "preview_status", "Not ready") or "Not ready")
        export_status = str(getattr(readiness, "export_status", "Not ready") or "Not ready")
        next_action = str(getattr(readiness, "next_action", "") or "")
        game_tested = bool(getattr(readiness, "game_tested", False))
        ready_for_game_test = bool(getattr(readiness, "ready_for_game_test", False))
        can_export_candidate = bool(getattr(readiness, "can_export_candidate", False))
        metadata = dict(getattr(readiness, "metadata", {}) or {})
        pathing = dict(metadata.get("pathing") or {})
        pathing_blockers = tuple(pathing.get("blockers", ()) or ())
        export_job = dict(metadata.get("export_job") or {})
        installed_path = str(metadata.get("installed_module_path") or "")
        proof_manifest = str(metadata.get("proof_manifest_path") or "")
        readiness_game = str(getattr(readiness, "game", "") or game)
        self.target_game_label.setText(f"Target game: {readiness_game}")
        self._set_action_enabled(
            True,
            can_place=has_authored_module,
            can_export=can_export_candidate,
            can_launch=bool(proof_manifest or installed_path or ready_for_game_test),
            can_proof=bool(proof_manifest or installed_path or ready_for_game_test),
        )

        self.capability_label.setText(
            self._capability_text(
                stage=stage,
                game_tested=game_tested,
                ready_for_game_test=ready_for_game_test,
                proof_manifest=proof_manifest,
                installed_path=installed_path,
            )
        )
        self.test_state_label.setText(
            self._test_state_text(
                stage=stage,
                game_tested=game_tested,
                ready_for_game_test=ready_for_game_test,
                proof_manifest=proof_manifest,
                installed_path=installed_path,
            )
        )
        missing_resources = tuple(getattr(readiness, "missing_runtime_resources", ()) or ())
        self.missing_resources_label.setText(self._missing_resources_text(missing_resources))
        self.validation_label.setText(f"Validation: {preview_status}. Stage: {stage}.")
        self._set_toolchain_label(
            self.geometry_label,
            readiness,
            "Geometry",
            "Geometry authoring",
            "Room geometry status unavailable.",
        )
        self._set_toolchain_label(
            self.walkmesh_label,
            readiness,
            "Walkmesh",
            "Walkmesh",
            "Walkmesh status unavailable.",
        )
        self._set_toolchain_label(
            self.visibility_label,
            readiness,
            "VIS visibility",
            "VIS visibility",
            "VIS status unavailable.",
        )
        self._set_toolchain_label(
            self.lighting_label,
            readiness,
            "Lighting/lightmaps",
            "Lighting",
            "Lighting/lightmap status unavailable.",
        )
        self._set_toolchain_label(
            self.placement_label,
            readiness,
            "Resource placement",
            "Resource placement",
            "Resource placement status unavailable.",
        )
        layout_status = self._toolchain_status(readiness, "Gameplay layout")
        if layout_status is not None:
            status = str(getattr(layout_status, "status", "Not checked") or "Not checked")
            value = str(getattr(layout_status, "value_label", "") or "")
            fix = str(getattr(layout_status, "fix_hint", "") or "")
            suffix = f" {value}" if value else ""
            self.layout_label.setText(f"Spawn/layout: {status}.{suffix}" + (f" Fix: {fix}" if not bool(getattr(layout_status, "ready", False)) and fix else ""))
        else:
            gameplay_count = int(metadata.get("gameplay_placement_count", 0) or 0)
            self.layout_label.setText(f"Spawn/layout: {gameplay_count} gameplay placement(s); entry point status unavailable.")
        self._set_toolchain_label(
            self.transitions_label,
            readiness,
            "Transitions",
            "Transitions",
            "Transition status unavailable.",
        )
        self._set_toolchain_label(
            self.scripts_label,
            readiness,
            "Scripts",
            "Scripts",
            "Script hook status unavailable.",
        )
        if installed_path:
            self.export_label.setText(f"Export/install: Installed for warp test. {installed_path}")
        elif proof_manifest:
            self.export_label.setText(f"Export/install: Staged for game test. {export_status}.")
        elif pathing_blockers:
            self.export_label.setText(
                f"Export/install: PTH/WOK pathing blocked. Fix {len(pathing_blockers)} path anchor issue(s) before staging."
            )
        else:
            self.export_label.setText(f"Export/install: {export_status}.")
        self.export_job_label.setText(
            self._export_job_text(
                export_job,
                can_export_candidate=can_export_candidate,
                game_tested=game_tested,
            )
        )
        if game_tested:
            self.proof_label.setText("Game proof: Recorded from a live KOTOR warp test.")
        else:
            self.proof_label.setText("Game proof: Not game-ready until a live KOTOR warp test is recorded.")
        self.next_action_label.setText(f"Next: {next_action}" if next_action else "")

    def _set_action_enabled(
        self,
        enabled: bool,
        *,
        can_place: bool,
        can_export: bool,
        can_proof: bool,
        can_launch: bool = False,
    ) -> None:
        for button in (
            self.open_builder_button,
            self.geometry_tools_button,
            self.starter_room_button,
            self.doorway_blockout_button,
            self.corridor_button,
            self.starter_terrain_button,
            self.terrain_tools_button,
            self.lighting_tools_button,
            self.placement_tools_button,
            self.script_tools_button,
            self.walkmesh_tools_button,
            self.validate_button,
        ):
            button.setEnabled(enabled)
        self.test_placeable_button.setEnabled(bool(enabled and can_place))
        self.stage_button.setEnabled(bool(enabled and can_export))
        self.install_button.setEnabled(bool(enabled and can_export))
        self.launch_handoff_button.setEnabled(bool(enabled and can_launch))
        self.proof_button.setEnabled(bool(can_proof))

    def set_active_authoring_context(self, text: str) -> None:
        """Show what Map Studio workflow the modder is currently editing."""

        value = str(text or "").strip()
        self.active_context_label.setText(f"Active tool: {value}" if value else "Active tool: none selected")

    def set_edit_mode_context(
        self,
        *,
        mode_label: str,
        editing_target: str = "",
        kotor_guardrail: str = "",
        next_action: str = "",
    ) -> None:
        """Show the current Map Studio mode, target, safety rule, and next action."""

        mode = str(mode_label or "Object").strip() or "Object"
        target = str(editing_target or "rooms, placements, and module objects").strip()
        guardrail = str(kotor_guardrail or "").strip()
        action = str(next_action or "").strip()
        self.mode_label.setText(f"Mode: {mode}")
        details = f"Editing: {target}"
        if guardrail:
            details = f"{details}. KOTOR rule: {guardrail}"
        if action:
            details = f"{details} Next: {action}"
        self.editing_target_label.setText(details)

    def set_selection_context(self, text: str) -> None:
        """Show and enable actions for the current Map Studio selection."""

        value = str(text or "").strip()
        has_selection = bool(value)
        self.selection_label.setText(f"Selected: {value}" if has_selection else "Selected: none")
        for button in (
            self.rename_selected_button,
            self.duplicate_selected_button,
            self.delete_selected_button,
            self.focus_selected_button,
        ):
            button.setEnabled(has_selection)

    @staticmethod
    def _capability_text(
        *,
        stage: str,
        game_tested: bool,
        ready_for_game_test: bool,
        proof_manifest: str,
        installed_path: str,
    ) -> str:
        stage_label = str(stage or "blocked").replace("_", " ").title()
        if game_tested:
            return "Capability: Game-tested. Live warp proof has been recorded."
        if installed_path:
            return "Capability: Installed test build. Warp in KOTOR and record proof before game-ready."
        if proof_manifest:
            return "Capability: Staged test build. Install/copy it, warp in KOTOR, then record proof."
        if ready_for_game_test or stage_label.lower() == "export candidate":
            return "Capability: Export candidate. Not game-ready until staged, installed, and warp-tested."
        if stage_label.lower() == "previewable":
            return "Capability: Previewable draft. Generate required resources before staging."
        return f"Capability: {stage_label}. Fix blocking issues before export."

    @staticmethod
    def _test_state_text(
        *,
        stage: str,
        game_tested: bool,
        ready_for_game_test: bool,
        proof_manifest: str,
        installed_path: str,
    ) -> str:
        if game_tested:
            return "Test state: Game-tested. Live warp proof is recorded."
        if installed_path:
            return "Test state: Installed for testing. Warp in-game, then record proof."
        if proof_manifest:
            return "Test state: Staged for testing. Install/copy the module, then run the warp test."
        if ready_for_game_test:
            return "Test state: Export candidate. Stage/install before in-game proof."
        stage_label = str(stage or "blocked").replace("_", " ").title()
        if stage_label.lower() == "previewable":
            return "Test state: Previewable only. Generate missing runtime resources before staging."
        return f"Test state: {stage_label}. Resolve blockers before game testing."

    @staticmethod
    def _export_job_text(
        export_job: dict[str, Any],
        *,
        can_export_candidate: bool,
        game_tested: bool,
    ) -> str:
        if not export_job:
            if can_export_candidate:
                return "ExportJob: Ready to stage; no package transaction recorded yet."
            return "ExportJob: Waiting for preflight, package, readback, and proof handoff."

        status = str(export_job.get("status") or "not_run").replace("_", " ")
        preflight = dict(export_job.get("preflight") or {})
        package = dict(export_job.get("package") or {})
        readback = dict(export_job.get("readback") or {})
        proof = dict(export_job.get("proof_handoff") or {})

        blocking_count = int(preflight.get("blocking_issue_count") or 0)
        preflight_text = "preflight ready" if preflight.get("ready") else f"preflight blocked ({blocking_count})"
        package_text = "package written" if package.get("ok") else "package not written"
        readback_text = "readback OK" if readback.get("ok") else "readback pending"
        proof_state = str(proof.get("state") or ("game_smoke_tested" if game_tested else "requires_live_warp_proof"))
        proof_text = proof_state.replace("_", " ")
        if game_tested:
            proof_text = "game smoke tested"
        return f"ExportJob: {status}; {preflight_text}; {package_text}; {readback_text}; proof {proof_text}."

    @staticmethod
    def _format_resource_key(resource: Any) -> str:
        if isinstance(resource, tuple) and len(resource) >= 2:
            return f"{resource[0]}.{resource[1]}"
        return str(resource)

    def _missing_resources_text(self, missing_resources: tuple[Any, ...]) -> str:
        if not missing_resources:
            return "Required resources: present for current export candidate."
        names = [self._format_resource_key(resource) for resource in missing_resources[:6]]
        suffix = f" plus {len(missing_resources) - 6} more" if len(missing_resources) > 6 else ""
        return (
            "Required resources missing: "
            + ", ".join(names)
            + suffix
            + ". Fix: generate or stage these module files before export/install."
        )

    @staticmethod
    def _toolchain_status(readiness: Any, name: str) -> Any | None:
        wanted = str(name or "").strip().lower()
        for item in tuple(getattr(readiness, "toolchain", ()) or ()):
            if str(getattr(item, "name", "") or "").strip().lower() == wanted:
                return item
        return None

    def _set_toolchain_label(
        self,
        label: QtWidgets.QLabel,
        readiness: Any,
        title: str,
        toolchain_name: str,
        fallback: str,
    ) -> None:
        status = self._toolchain_status(readiness, toolchain_name)
        if status is None:
            label.setText(f"{title}: {fallback}")
            return
        text = f"{title}: {str(getattr(status, 'status', 'Not checked') or 'Not checked')}."
        value = str(getattr(status, "value_label", "") or "")
        if value:
            text = f"{text} {value}"
        fix = str(getattr(status, "fix_hint", "") or "")
        if not bool(getattr(status, "ready", False)) and fix:
            text = f"{text} Fix: {fix}"
        label.setText(text)
