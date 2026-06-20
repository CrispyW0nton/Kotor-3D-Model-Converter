from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_t2600_map_studio_workflow_panel_surfaces_editor_spine() -> None:
    panel_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/workflow_panel.py"
    )

    assert "class MapStudioWorkflowPanel" in panel_source
    assert "mapStudioWorkflowProjectLabel" in panel_source
    assert "mapStudioWorkflowTargetGameLabel" in panel_source
    assert "mapStudioWorkflowCapabilityLabel" in panel_source
    assert "mapStudioWorkflowTestStateLabel" in panel_source
    assert "mapStudioWorkflowAuthoringLabel" in panel_source
    assert "mapStudioWorkflowActiveContextLabel" in panel_source
    assert "mapStudioWorkflowSelectionLabel" in panel_source
    assert "mapStudioWorkflowResourcesLabel" in panel_source
    assert "mapStudioWorkflowMissingResourcesLabel" in panel_source
    assert "mapStudioWorkflowGeometryLabel" in panel_source
    assert "mapStudioWorkflowWalkmeshLabel" in panel_source
    assert "mapStudioWorkflowLightingLabel" in panel_source
    assert "mapStudioWorkflowPlacementLabel" in panel_source
    assert "mapStudioWorkflowLayoutLabel" in panel_source
    assert "mapStudioWorkflowTransitionsLabel" in panel_source
    assert "mapStudioWorkflowScriptsLabel" in panel_source
    assert "mapStudioWorkflowValidationLabel" in panel_source
    assert "mapStudioWorkflowExportLabel" in panel_source
    assert "mapStudioWorkflowProofLabel" in panel_source
    assert "mapStudioWorkflowNewKmapButton" in panel_source
    assert "mapStudioWorkflowOpenKmapButton" in panel_source
    assert "mapStudioWorkflowSaveKmapButton" in panel_source
    assert "mapStudioWorkflowRenameSelectedButton" in panel_source
    assert "mapStudioWorkflowDuplicateSelectedButton" in panel_source
    assert "mapStudioWorkflowDeleteSelectedButton" in panel_source
    assert "mapStudioWorkflowFocusSelectedButton" in panel_source
    assert "mapStudioWorkflowOpenBuilderButton" in panel_source
    assert "mapStudioWorkflowGeometryToolsButton" in panel_source
    assert "mapStudioWorkflowStarterRoomButton" in panel_source
    assert "mapStudioWorkflowDoorwayBlockoutButton" in panel_source
    assert "mapStudioWorkflowCorridorButton" in panel_source
    assert "mapStudioWorkflowStarterTerrainButton" in panel_source
    assert "mapStudioWorkflowTerrainToolsButton" in panel_source
    assert "mapStudioWorkflowLightingToolsButton" in panel_source
    assert "mapStudioWorkflowPlacementToolsButton" in panel_source
    assert "mapStudioWorkflowScriptToolsButton" in panel_source
    assert "mapStudioWorkflowTestPlaceableButton" in panel_source
    assert "mapStudioWorkflowWalkmeshToolsButton" in panel_source
    assert "mapStudioWorkflowValidateButton" in panel_source
    assert "mapStudioWorkflowStageButton" in panel_source
    assert "mapStudioWorkflowInstallButton" in panel_source
    assert "mapStudioWorkflowLaunchHandoffButton" in panel_source
    assert "mapStudioWorkflowProofButton" in panel_source
    assert "newProjectRequested = QtCore.Signal()" in panel_source
    assert "openProjectRequested = QtCore.Signal()" in panel_source
    assert "saveProjectRequested = QtCore.Signal()" in panel_source
    assert "renameSelectedRequested = QtCore.Signal()" in panel_source
    assert "duplicateSelectedRequested = QtCore.Signal()" in panel_source
    assert "deleteSelectedRequested = QtCore.Signal()" in panel_source
    assert "focusSelectedRequested = QtCore.Signal()" in panel_source
    assert "builderRequested = QtCore.Signal()" in panel_source
    assert "geometryToolsRequested = QtCore.Signal()" in panel_source
    assert "starterRoomRequested = QtCore.Signal()" in panel_source
    assert "doorwayBlockoutRequested = QtCore.Signal()" in panel_source
    assert "corridorRequested = QtCore.Signal()" in panel_source
    assert "starterTerrainRequested = QtCore.Signal()" in panel_source
    assert "terrainToolsRequested = QtCore.Signal()" in panel_source
    assert "lightingToolsRequested = QtCore.Signal()" in panel_source
    assert "placementToolsRequested = QtCore.Signal()" in panel_source
    assert "scriptToolsRequested = QtCore.Signal()" in panel_source
    assert "testPlaceableRequested = QtCore.Signal()" in panel_source
    assert "walkmeshToolsRequested = QtCore.Signal()" in panel_source
    assert "validateRequested = QtCore.Signal()" in panel_source
    assert "stageRequested = QtCore.Signal()" in panel_source
    assert "installRequested = QtCore.Signal()" in panel_source
    assert "launchHandoffRequested = QtCore.Signal()" in panel_source
    assert "proofRequested = QtCore.Signal()" in panel_source
    assert "New KMAP" in panel_source
    assert "Open KMAP" in panel_source
    assert "Save KMAP" in panel_source
    assert "Rename Selected" in panel_source
    assert "Duplicate Selected" in panel_source
    assert "Delete Selected" in panel_source
    assert "Focus Selected" in panel_source
    assert "Open Geometry Tools" in panel_source
    assert "Create Starter Room" in panel_source
    assert "Create Doorway Blockout" in panel_source
    assert "Create Corridor" in panel_source
    assert "Create Terrain Patch" in panel_source
    assert "Open Terrain Tools" in panel_source
    assert "Open Lighting Tools" in panel_source
    assert "Open Placement Tools" in panel_source
    assert "Open Script Hooks" in panel_source
    assert "Add Test Placeable" in panel_source
    assert "Open Walkmesh Tools" in panel_source
    assert "Open Warp Test Handoff" in panel_source
    assert "Target game:" in panel_source
    assert "Test state:" in panel_source
    assert "Export candidate. Stage/install before in-game proof" in panel_source
    assert "Game-tested. Live warp proof is recorded" in panel_source
    assert "Not game-ready until a live KOTOR warp test is recorded" in panel_source
    assert "Capability: Export candidate" in panel_source
    assert "Capability: Installed test build" in panel_source
    assert "Capability: Staged test build" in panel_source
    assert "Capability: Game-tested" in panel_source
    assert "Required resources missing" in panel_source
    assert "generate or stage these module files before export/install" in panel_source
    assert "Geometry authoring" in panel_source
    assert "Walkmesh" in panel_source
    assert (
        'self.walkmesh_label,\n'
        '            readiness,\n'
        '            "Walkmesh",\n'
        '            "Walkmesh",\n'
        '            "Walkmesh status unavailable.",'
    ) in panel_source
    assert "Lighting/lightmaps:" in panel_source
    assert '"Lighting"' in panel_source


def test_t2600_map_studio_new_project_dialog_exposes_module_identity() -> None:
    panel_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/workflow_panel.py"
    )
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/"
        "module_editor_window.py"
    )
    controller_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    mirror_controller_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/core/modules/"
        "module_editor_controller.py"
    )

    assert "class _MapStudioNewProjectDialog" in window_source
    assert "New Map Studio KMAP" in window_source
    assert "mapStudioNewProjectHintLabel" in window_source
    assert "mapStudioNewProjectModuleRootLineEdit" in window_source
    assert "mapStudioNewProjectGameComboBox" in window_source
    assert "mapStudioNewProjectAuthorLineEdit" in window_source
    assert "Module root / KMAP name" in window_source
    assert "Knights of the Old Republic (K1)" in window_source
    assert "The Sith Lords (K2)" in window_source
    assert "dialog = _MapStudioNewProjectDialog" in window_source
    assert "project = self.controller.new_project(**dialog.values())" in window_source
    assert "Created Map Studio KMAP {project.name} for {project.game}." in window_source

    for source in (controller_source, mirror_controller_source):
        assert "authored_resref_blocking_issue" in source
        assert 'if game_key not in {"K1", "K2"}' in source
        assert "Map Studio projects must target K1 or K2." in source
        assert 'authored_resref_blocking_issue("Map Studio module root", name)' in source
        assert "Created new Map Studio KMAP project" in source
    assert "lightmap" in panel_source
    assert "Resource placement:" in panel_source
    assert '"Resource placement"' in panel_source
    assert "creatures, placeables, doors, triggers, encounters, cameras, sounds, merchants, and waypoints" in panel_source
    assert "placing KOTOR resources" in panel_source
    assert "Spawn/layout:" in panel_source
    assert "Gameplay layout" in panel_source
    assert "Transitions:" in panel_source
    assert '"Transitions"' in panel_source
    assert "doors, triggers, or waypoints" in panel_source
    assert "Scripts:" in panel_source
    assert '"Scripts"' in panel_source
    assert "script hooks" in panel_source
    assert "player start" in panel_source
    assert "Use Builder to create terrain, rooms, or a dev-test map" in panel_source
    assert "def set_active_authoring_context" in panel_source
    assert "Active tool:" in panel_source
    assert "def set_selection_context" in panel_source
    assert "Selected: none" in panel_source
    assert "def _test_state_text" in panel_source
    assert "ARE/GIT/IFO/LYT/VIS/PTH/WOK/MDL/MDX" in panel_source


def test_t2600_level_editor_wires_workflow_panel_to_readiness_contract() -> None:
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/"
        "module_editor_window.py"
    )
    init_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/__init__.py"
    )

    assert "from src.gui.panels.module_editor.workflow_panel import MapStudioWorkflowPanel" in window_source
    assert "self.workflow_panel = MapStudioWorkflowPanel(right)" in window_source
    assert "export_layout.addWidget(self.workflow_panel)" in window_source
    assert "readiness_result = self.controller.authored_module_readiness()" in window_source
    assert "self.workflow_panel.set_state(self.project, readiness_result.readiness)" in window_source
    assert "self.workflow_panel.newProjectRequested.connect(self.new_kmap)" in window_source
    assert "self.workflow_panel.openProjectRequested.connect(self.open_kmap)" in window_source
    assert "self.workflow_panel.saveProjectRequested.connect(self.save_kmap)" in window_source
    assert "self.workflow_panel.renameSelectedRequested.connect(self.rename_selected)" in window_source
    assert "self.workflow_panel.duplicateSelectedRequested.connect(self.duplicate_selected)" in window_source
    assert "self.workflow_panel.deleteSelectedRequested.connect(self.delete_selected)" in window_source
    assert "self.workflow_panel.focusSelectedRequested.connect(self.viewport_panel.focus_selected)" in window_source
    assert "self.workflow_panel.builderRequested.connect(self.show_map_studio_builder)" in window_source
    assert "self.workflow_panel.geometryToolsRequested.connect(self.show_map_studio_geometry_tools)" in window_source
    assert "self.validation_panel.set_issues(self.controller.validate())" in window_source
    assert "self.workflow_panel.starterRoomRequested.connect(self.create_map_studio_starter_room)" in window_source
    assert "self.workflow_panel.doorwayBlockoutRequested.connect(self.create_map_studio_doorway_blockout)" in window_source
    assert "self.workflow_panel.corridorRequested.connect(self.create_map_studio_corridor)" in window_source
    assert "self.workflow_panel.starterTerrainRequested.connect(self.create_map_studio_starter_terrain)" in window_source
    assert "self.workflow_panel.terrainToolsRequested.connect(self.show_map_studio_terrain_tools)" in window_source
    assert "self.workflow_panel.lightingToolsRequested.connect(self.show_map_studio_lighting_tools)" in window_source
    assert "self.workflow_panel.placementToolsRequested.connect(self.show_map_studio_placement_tools)" in window_source
    assert "self.workflow_panel.scriptToolsRequested.connect(self.show_map_studio_script_tools)" in window_source
    assert "self.workflow_panel.testPlaceableRequested.connect(self.add_map_studio_test_placeable)" in window_source
    assert "self.builder_tab.gameplayPlacementStatusChanged.connect(self.workflow_panel.set_active_authoring_context)" in window_source
    assert "self.workflow_panel.walkmeshToolsRequested.connect(self.show_map_studio_walkmesh_tools)" in window_source
    assert "self.workflow_panel.validateRequested.connect(self.validate_kmap)" in window_source
    assert "self.workflow_panel.stageRequested.connect(lambda: self.stage_authored_module" in window_source
    assert "self.workflow_panel.installRequested.connect(lambda: self.install_authored_module" in window_source
    assert "self.workflow_panel.launchHandoffRequested.connect(self.open_map_studio_launch_handoff)" in window_source
    assert "self.workflow_panel.proofRequested.connect(self.record_game_smoke_proof)" in window_source
    assert "self.workflow_panel.set_selection_context(self._selected_item_label(item_id))" in window_source
    assert "def _selected_item_label" in window_source
    assert 'self.workflow_panel.set_selection_context("")' in window_source
    assert "def show_map_studio_builder" in window_source
    assert "Builder: room, terrain, placement, lighting, and script authoring" in window_source
    assert "def show_map_studio_geometry_tools" in window_source
    assert "roomPrimitivePresetComboBox" in window_source
    assert "Geometry: primitive rooms, extrusion, bevel/inset, rectangular cuts, boolean union, and modular room pieces" in window_source
    assert "def create_map_studio_starter_room" in window_source
    assert "preset_id=\"rectangular_dev_room\"" in window_source
    assert "def create_map_studio_doorway_blockout" in window_source
    assert "preset_id=\"doorway_blockout\"" in window_source
    assert "def create_map_studio_corridor" in window_source
    assert "preset_id=\"wide_hall\"" in window_source
    assert "def create_map_studio_starter_terrain" in window_source
    assert "preset_id=\"terrain_heightfield\"" in window_source
    assert "def show_map_studio_terrain_tools" in window_source
    assert "terrainRoomComboBox" in window_source
    assert "Terrain: sculpt heightfield samples" in window_source
    assert "def show_map_studio_lighting_tools" in window_source
    assert "roomLightNameLineEdit" in window_source
    assert "Lighting: add authored room lights" in window_source
    assert "def show_map_studio_placement_tools" in window_source
    assert "gameplayPaletteSearchLineEdit" in window_source
    assert "Placement: choose a KOTOR resource template" in window_source
    assert "def show_map_studio_script_tools" in window_source
    assert "scriptHookResrefLineEdit" in window_source
    assert "Scripts: assign ARE/IFO script hook resrefs" in window_source
    assert "def show_map_studio_walkmesh_tools" in window_source
    assert "Walkmesh: inspect and paint walkable/non-walkable faces" in window_source
    assert "self.workflow_tabs.setCurrentWidget(self.walkmesh_tab)" in window_source
    assert "def add_map_studio_test_placeable" in window_source
    assert '"plc_bench"' in window_source
    assert "self.workflow_tabs.setCurrentWidget(self.builder_tab)" in window_source
    assert "MapStudioWorkflowPanel" in init_source


def test_t2600_level_editor_exposes_map_studio_workspace_switcher() -> None:
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/"
        "module_editor_window.py"
    )
    controller_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    mirror_controller_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    model_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "module_editor_model.py"
    )

    assert "class MapStudioWorkspaceMode" in model_source
    for source in (controller_source, mirror_controller_source):
        assert "def map_studio_workspace_modes" in source
        assert 'key="project"' in source
        assert 'label="Project"' in source
        assert 'key="geometry"' in source
        assert 'label="Room Geometry"' in source
        assert 'key="terrain"' in source
        assert 'label="Terrain Builder"' in source
        assert 'key="walkmesh"' in source
        assert 'label="Walkmesh"' in source
        assert 'key="placements"' in source
        assert 'label="Placements"' in source
        assert 'key="lighting"' in source
        assert 'label="Lighting"' in source
        assert 'key="scripts"' in source
        assert 'label="Scripts + Transitions"' in source
        assert 'key="export"' in source
        assert 'label="Export + Game Proof"' in source
        assert "creatures, placeables, doors, triggers, encounters, cameras, sounds, waypoints, and stores" in source
        assert "Validate first; only call the module game-ready after a staged install and recorded warp proof." in source

    assert "self.controller.map_studio_workspace_modes()" in window_source
    assert "mapStudioWorkspaceLabel" in window_source
    assert "mapStudioWorkspaceComboBox" in window_source
    assert "mapStudioWorkspaceGuideLabel" in window_source
    assert "mapStudioOpenWorkspaceButton" in window_source
    assert "mapStudioRightTabs" in window_source
    assert "self.map_studio_workspace_combo.currentIndexChanged.connect" in window_source
    assert "def _handle_map_studio_workspace_changed" in window_source
    assert "def _open_selected_map_studio_workspace" in window_source
    assert "self.show_map_studio_geometry_tools()" in window_source
    assert "self.show_map_studio_terrain_tools()" in window_source
    assert "self.show_map_studio_walkmesh_tools()" in window_source
    assert "self.show_map_studio_placement_tools()" in window_source
    assert "self.show_map_studio_lighting_tools()" in window_source
    assert "self.show_map_studio_script_tools()" in window_source
    assert "self.right_tabs.setCurrentWidget(self.map_studio_export_page)" in window_source
    assert "Export + Game Proof: validate, stage/install, warp test, then record proof" in window_source


def test_t2908_map_studio_exposes_component_vertex_tools_and_customizable_belt() -> None:
    builder_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    builder_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/"
        "module_editor_window.py"
    )
    controller_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    controller_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    tools_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "map_studio_modeling_tools.py"
    )
    tools_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/core/modules/"
        "map_studio_modeling_tools.py"
    )
    preferences_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "map_studio_tool_belt_preferences.py"
    )
    preferences_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/core/modules/"
        "map_studio_tool_belt_preferences.py"
    )
    export_objects_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "map_studio_export_objects.py"
    )
    export_objects_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/core/modules/"
        "map_studio_export_objects.py"
    )
    readiness_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "authored_module_readiness.py"
    )
    readiness_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/core/modules/"
        "authored_module_readiness.py"
    )
    readiness_panel_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/readiness_panel.py"
    )
    readiness_panel_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/readiness_panel.py"
    )

    for source in (builder_source, builder_mirror_source):
        assert 'roomOperationRequested = QtCore.Signal(str, float, int, float, float, float, float)' in source
        assert '"Extrude edge", "edge_extrude"' in source
        assert '"Split room on X", "split_x"' in source
        assert '"Split room on Y", "split_y"' in source
        assert "mapStudioRoomOperationEdgeIndexSpinBox" in source
        assert "floorPlanBridgeRequested = QtCore.Signal" in source
        assert "Bridge Floor-Plan Edges" in source
        assert "mapStudioFloorPlanBridgeFirstRoomComboBox" in source
        assert "mapStudioFloorPlanBridgeFirstEdgeSpinBox" in source
        assert "mapStudioFloorPlanBridgeSecondRoomComboBox" in source
        assert "mapStudioFloorPlanBridgeSecondEdgeSpinBox" in source
        assert "mapStudioBridgeFloorPlanEdgesButton" in source
        assert "floorPlanOpeningRequested = QtCore.Signal" in source
        assert "floorPlanOpeningMarkerRequested = QtCore.Signal" in source
        assert "Floor-Plan Wall Opening" in source
        assert "mapStudioFloorPlanOpeningRoomComboBox" in source
        assert "mapStudioFloorPlanOpeningEdgeSpinBox" in source
        assert "mapStudioFloorPlanOpeningCenterSpinBox" in source
        assert "mapStudioApplyFloorPlanOpeningButton" in source
        assert "def _emit_floor_plan_opening" in source
        assert "Opening Transition Marker" in source
        assert "mapStudioFloorPlanOpeningMarkerRoomComboBox" in source
        assert "mapStudioFloorPlanOpeningMarkerNameComboBox" in source
        assert "mapStudioFloorPlanOpeningMarkerKindComboBox" in source
        assert "mapStudioFloorPlanOpeningMarkerTransitionDestSpinBox" in source
        assert "mapStudioCreateOpeningTransitionMarkerButton" in source
        assert "def _emit_floor_plan_opening_marker" in source
        assert "Floor-Plan Vertex Tools" in source
        assert "floorPlanVertexSnapRequested = QtCore.Signal" in source
        assert "floorPlanVertexWeldRequested = QtCore.Signal" in source
        assert "floorPlanVertexFlattenRequested = QtCore.Signal" in source
        assert "mapStudioFloorPlanVertexRoomComboBox" in source
        assert "mapStudioFloorPlanVertexTargetRoomComboBox" in source
        assert "mapStudioFloorPlanSelectedPointsLineEdit" in source
        assert "mapStudioSnapFloorPlanVertexButton" in source
        assert "mapStudioWeldFloorPlanVerticesButton" in source
        assert "mapStudioFlattenFloorPlanVerticesButton" in source
        assert "mapStudioFloorPlanMirrorAxisComboBox" in source
        assert "mapStudioMirrorFloorPlanVerticesButton" in source
        assert "mapStudioFloorPlanCleanupToleranceSpinBox" in source
        assert "mapStudioCleanupFloorPlanVerticesButton" in source
        assert "floorPlanVertexCleanupRequested = QtCore.Signal" in source
        assert "floorPlanVertexMirrorRequested = QtCore.Signal" in source
        assert "floorPlanFaceFillRequested = QtCore.Signal" in source
        assert "floorPlanFaceTriangulateRequested = QtCore.Signal" in source
        assert "floorPlanNormalsCleanupRequested = QtCore.Signal" in source
        assert "mapStudioFillFloorPlanFaceButton" in source
        assert "mapStudioTriangulateFloorPlanFaceButton" in source
        assert "mapStudioCleanupFloorPlanNormalsButton" in source
        assert "Fill Selected Face Loop" in source
        assert "Triangulate Footprint" in source
        assert "Cleanup Face Normals" in source
        assert "planes, walls, ramps, stairs, arches, cubes, and cylinders" in source
        assert "moduleEntryPointRequested = QtCore.Signal(str, float, float, float, float)" in source
        assert "Module Entry Point" in source
        assert "mapStudioEntryPointAreaLineEdit" in source
        assert "mapStudioEntryPointPosXSpinBox" in source
        assert "mapStudioEntryPointFacingSpinBox" in source
        assert "mapStudioApplyEntryPointButton" in source
        assert "def set_module_entry_point" in source
        assert "def _emit_module_entry_point" in source
        assert "mapStudioTerrainBrushComboBox" in source
        assert "mapStudioTerrainBrushStatusLabel" in source
        assert "mapStudioApplyTerrainBrushButton" in source
        assert "def set_terrain_brushes" in source
        assert "def _emit_selected_terrain_brush" in source

    for source in (tools_source, tools_mirror_source):
        assert "class MapStudioToolBeltAction" in source
        assert "class MapStudioToolBeltPreset" in source
        assert "class MapStudioTerrainBrush" in source
        assert "class MapStudioViewportPerformancePolicy" in source
        assert "available_map_studio_terrain_brushes" in source
        assert "map_studio_viewport_performance_policy" in source
        assert "target_frame_ms=8.33" in source
        assert "terrain_brush_budget_ms=4.0" in source
        assert "drop stale stroke frames" in source
        assert "available_map_studio_tool_belt_actions" in source
        assert "available_map_studio_tool_belt_presets" in source
        assert "map_studio_tool_belt_actions_for_preset" in source
        assert '"blockout"' in source
        assert '"component"' in source
        assert '"terrain"' in source
        assert '"gameplay"' in source
        assert '"custom"' in source
        assert '"corridor"' in source
        assert '"Corridor"' in source
        assert '"terrain_patch"' in source
        assert '"Terrain Patch"' in source
        assert '"sculpt_raise"' in source
        assert '"sculpt_lower"' in source
        assert '"sculpt_smooth"' in source
        assert '"sculpt_flatten"' in source
        assert '"sculpt_plateau"' in source
        assert '"sculpt_ramp"' in source
        assert '"sculpt_terrace"' in source
        assert '"sculpt_pinch"' in source
        assert '"sculpt_erode"' in source
        assert '"sculpt_noise"' in source
        assert '"combine"' in source
        assert '"Combine"' in source
        assert '"separate"' in source
        assert '"Separate"' in source
        assert '"Split a selected authored primitive into its own exportable KMAP room/object boundary."' in source
        assert '"plane"' in source
        assert '"Plane"' in source
        assert '"cube"' in source
        assert '"wall"' in source
        assert '"ramp"' in source
        assert '"stairs"' in source
        assert '"cylinder"' in source
        assert '"door_frame"' in source
        assert '"Door Frame"' in source
        assert '"extrude"' in source
        assert '"bridge"' in source
        assert '"cut"' in source
        assert '"knife_split"' in source
        assert '"opening"' in source
        assert '"wall_opening"' in source
        assert '"Wall Opening"' in source
        assert '"opening_marker"' in source
        assert '"Opening Marker"' in source
        assert '"opening_transition_marker"' in source
        assert "TransitionDestin" in source
        assert '"fill"' in source
        assert '"fill_face"' in source
        assert '"vertex_snap"' in source
        assert '"weld"' in source
        assert '"flatten"' in source
        assert '"mirror"' in source
        assert '"mirror_footprint"' in source
        assert '"cleanup"' in source
        assert '"cleanup_footprint"' in source
        assert '"triangulate"' in source
        assert '"normals"' in source
        assert '"cleanup_normals"' in source
        assert '"entry_point"' in source
        assert '"Entry Point"' in source
        assert '"placeable"' in source
        assert '"Placeable"' in source
        assert '"creature"' in source
        assert '"Creature"' in source
        assert '"door"' in source
        assert '"Door"' in source
        assert '"waypoint"' in source
        assert '"Waypoint"' in source
        assert '"trigger"' in source
        assert '"Trigger"' in source
        assert '"encounter"' in source
        assert '"Encounter"' in source
        assert '"sound"' in source
        assert '"Sound"' in source
        assert '"camera"' in source
        assert '"Camera"' in source
        assert '"store"' in source
        assert '"Store"' in source
        assert '"stage_module"' in source
        assert '"Stage .mod"' in source
        assert '"install_module"' in source
        assert '"Install Test"' in source
        assert '"launch_handoff"' in source
        assert '"Launch Handoff"' in source
        assert '"record_proof"' in source
        assert '"Record Proof"' in source
        assert "Staging creates an export candidate" in source
        assert "real in-game evidence" in source

    for source in (controller_source, controller_mirror_source):
        assert "available_map_studio_tool_belt_actions" in source
        assert "available_map_studio_tool_belt_presets" in source
        assert "available_map_studio_terrain_brushes" in source
        assert "map_studio_viewport_performance_policy" in source
        assert "map_studio_tool_belt_actions_for_preset" in source
        assert "map_studio_tool_belt_preferences" in source
        assert "set_map_studio_tool_belt_preferences" in source
        assert "MAP_STUDIO_TOOL_BELT_SECTION" in source
        assert "def available_map_studio_tool_belt_actions" in source
        assert "def available_map_studio_tool_belt_presets" in source
        assert "def available_map_studio_terrain_brushes" in source
        assert "def map_studio_viewport_performance_policy" in source
        assert "def map_studio_tool_belt_actions_for_preset" in source
        assert "bridge_authored_floor_plan_edges" in source
        assert "cleanup_authored_floor_plan_vertices" in source
        assert "fill_authored_floor_plan_face" in source
        assert "triangulate_authored_floor_plan_face" in source
        assert "cleanup_authored_floor_plan_normals" in source
        assert "mirror_authored_floor_plan_vertices" in source
        assert "authored_module_entry_point" in source
        assert "set_authored_module_entry_point" in source
        assert "update_authored_module_entry_point" in source
        assert "separate_authored_room_composition_primitive" in source
        assert "def separate_authored_room_primitive" in source
        assert "map_studio_export_object_boundaries" in source
        assert "def map_studio_export_object_boundaries" in source

    for source in (export_objects_source, export_objects_mirror_source):
        assert "class MapStudioExportObjectBoundary" in source
        assert "def map_studio_export_object_boundaries" in source
        assert '"separated_primitive_object"' in source
        assert "uv_handoff_recommended" in source

    for source in (readiness_source, readiness_mirror_source):
        assert "map_studio_export_object_boundaries" in source
        assert '"export_object_boundaries"' in source
        assert '"uv_handoff_object_count"' in source
        assert "class AuthoredComponentEditReadiness" in source
        assert "def _component_edit_readiness" in source
        assert "component_edit: AuthoredComponentEditReadiness" in source
        assert '"component_edit"' in source
        assert '"Component edit audit"' in source
        assert '"Needs WOK/export review"' in source
        assert "class AuthoredFloorPlanGeometryReadiness" in source
        assert "class AuthoredDoorwayTransitionReadiness" in source
        assert "def _doorway_transition_readiness" in source
        assert "def _floor_plan_geometry_readiness" in source
        assert "geometry_validation: AuthoredFloorPlanGeometryReadiness" in source
        assert "doorway_transition: AuthoredDoorwayTransitionReadiness" in source
        assert '"geometry_validation"' in source
        assert '"doorway_transition"' in source
        assert "opening_count: int = 0" in source
        assert '"opening_count": geometry_validation.opening_count' in source
        assert '"transition_marker_count": doorway_transition.transition_marker_count' in source
        assert "Doorway/transition intent" in source
        assert '"Floor-plan validation"' in source

    for source in (readiness_panel_source, readiness_panel_mirror_source):
        assert "mapStudioReadinessExportObjectsLabel" in source
        assert "mapStudioReadinessExportObjectsTable" in source
        assert "def _set_export_object_rows" in source
        assert "DCC/UV handoff candidate" in source
        assert "mapStudioReadinessComponentEditLabel" in source
        assert "mapStudioReadinessDoorwayTransitionLabel" in source
        assert "def _set_doorway_transition_summary" in source
        assert "Doorway/transition intent: Not checked" in source
        assert "def _set_component_edit_summary" in source
        assert "Component edits: Not checked" in source
        assert "Review WOK/MDL/MDX/PTH output before export" in source
        assert 'geometry_validation.get("opening_count"' in source
        assert 'metadata.get("doorway_transition"' in source
        assert 'doorway_transition.get("transition_marker_count"' in source
        assert "opening(s)" in source

    for source in (preferences_source, preferences_mirror_source):
        assert "MAP_STUDIO_TOOL_BELT_SECTION" in source
        assert "MapStudioToolBeltPreferences" in source
        assert "normalise_map_studio_tool_belt_preferences" in source
        assert "to_kmap_section" in source

    assert "class _MapStudioToolBeltCustomizeDialog" in window_source
    assert "mapStudioToolBeltLabel" in window_source
    assert "mapStudioToolBeltPresetComboBox" in window_source
    assert "self.builder_tab.moduleEntryPointRequested.connect(self.set_authored_module_entry_point)" in window_source
    assert "self.builder_tab.set_module_entry_point(self.controller.authored_module_entry_point())" in window_source
    assert "self.builder_tab.set_terrain_brushes(self.controller.available_map_studio_terrain_brushes())" in window_source
    assert "def _focus_map_studio_entry_point_controls" in window_source
    assert "def _focus_map_studio_opening_marker_controls" in window_source
    assert "def _map_studio_export_dry_run_enabled" in window_source
    assert "def _focus_map_studio_export_proof_workspace" in window_source
    assert "def set_authored_module_entry_point" in window_source
    assert 'if key == "entry_point":' in window_source
    assert 'if key == "opening_marker":' in window_source
    assert "floorPlanOpeningMarkerRoomComboBox" in window_source
    assert "Opening marker: create a KOTOR door, trigger, or waypoint" in window_source
    assert 'if key == "stage_module":' in window_source
    assert "self.stage_authored_module(self._map_studio_export_dry_run_enabled())" in window_source
    assert 'if key == "install_module":' in window_source
    assert "self.install_authored_module(self._map_studio_export_dry_run_enabled())" in window_source
    assert 'if key == "launch_handoff":' in window_source
    assert "self.open_map_studio_launch_handoff()" in window_source
    assert 'if key == "record_proof":' in window_source
    assert "self.record_game_smoke_proof()" in window_source
    assert "def _map_studio_belt_placement_kind" in window_source
    assert "def _map_studio_belt_terrain_brush" in window_source
    assert "def _select_map_studio_gameplay_kind" in window_source
    assert "def _select_map_studio_terrain_brush" in window_source
    assert '"placeable": "placeable"' in window_source
    assert '"creature": "creature"' in window_source
    assert '"door": "door"' in window_source
    assert '"waypoint": "waypoint"' in window_source
    assert '"trigger": "trigger"' in window_source
    assert '"encounter": "encounter"' in window_source
    assert '"sound": "sound"' in window_source
    assert '"camera": "camera"' in window_source
    assert '"store": "store"' in window_source
    assert "self.show_map_studio_placement_tools()" in window_source
    assert "self._select_map_studio_gameplay_kind(placement_kind)" in window_source
    assert '"sculpt_raise": "raise"' in window_source
    assert '"sculpt_lower": "lower"' in window_source
    assert '"sculpt_smooth": "smooth"' in window_source
    assert '"sculpt_flatten": "flatten"' in window_source
    assert '"sculpt_plateau": "plateau"' in window_source
    assert '"sculpt_ramp": "ramp"' in window_source
    assert '"sculpt_terrace": "terrace"' in window_source
    assert '"sculpt_pinch": "pinch"' in window_source
    assert '"sculpt_erode": "erode"' in window_source
    assert '"sculpt_noise": "noise"' in window_source
    assert "self.controller.map_studio_viewport_performance_policy()" in window_source
    assert "self._select_map_studio_terrain_brush(terrain_brush)" in window_source
    assert "mapStudioToolBeltWidget" in window_source
    assert "mapStudioCustomizeToolBeltButton" in window_source
    assert "mapStudioToolBeltCustomizeListWidget" in window_source
    assert "def _refresh_map_studio_tool_belt" in window_source
    assert "def _apply_map_studio_tool_belt_preferences_from_project" in window_source
    assert "def _persist_map_studio_tool_belt_preferences" in window_source
    assert "def _handle_map_studio_tool_belt_preset_changed" in window_source
    assert "def _customize_map_studio_tool_belt" in window_source
    assert "def _handle_map_studio_tool_belt_action" in window_source
    assert "self.controller.set_map_studio_tool_belt_preferences" in window_source
    assert "self.controller.map_studio_tool_belt_preferences" in window_source
    assert "Map Studio custom tool belt saved in this KMAP." in window_source
    assert 'operation_combo.findData("edge_extrude")' in window_source
    assert 'operation_combo.findData("split_x")' in window_source
    assert 'operation_combo.findData("rectangular_cut")' in window_source
    assert 'operation in {"split_x", "split_y"}' in window_source
    assert "def _map_studio_belt_primitive_kind" in window_source
    assert "def _select_map_studio_modeling_tool" in window_source
    assert '"door_frame": "door_frame"' in window_source
    assert 'if key == "corridor":' in window_source
    assert "self.create_map_studio_corridor()" in window_source
    assert 'if key == "terrain_patch":' in window_source
    assert "self.create_map_studio_starter_terrain()" in window_source
    assert '"fill"' in window_source
    assert '"triangulate"' in window_source
    assert '"normals"' in window_source
    assert "self._select_map_studio_modeling_tool(tool_key)" in window_source
    assert "self.add_authored_room_primitive(primitive_kind, \"\")" in window_source
    assert "floorPlanBridgeRequested.connect(self.bridge_authored_floor_plan_edges)" in window_source
    assert "floorPlanOpeningRequested.connect(self.set_authored_floor_plan_wall_opening)" in window_source
    assert "floorPlanOpeningMarkerRequested.connect(self.create_authored_opening_transition_marker)" in window_source
    assert "floorPlanVertexCleanupRequested.connect(self.cleanup_authored_floor_plan_vertices)" in window_source
    assert "floorPlanVertexMirrorRequested.connect(self.mirror_authored_floor_plan_vertices)" in window_source
    assert "floorPlanFaceFillRequested.connect(self.fill_authored_floor_plan_face)" in window_source
    assert "floorPlanFaceTriangulateRequested.connect(self.triangulate_authored_floor_plan_face)" in window_source
    assert "floorPlanNormalsCleanupRequested.connect(self.cleanup_authored_floor_plan_normals)" in window_source
    assert "def bridge_authored_floor_plan_edges" in window_source
    assert "def set_authored_floor_plan_wall_opening" in window_source
    assert 'operation="wall_opening"' in window_source
    assert "def create_authored_opening_transition_marker" in window_source
    assert 'operation="opening_transition_marker"' in window_source
    assert "def cleanup_authored_floor_plan_vertices" in window_source
    assert "def mirror_authored_floor_plan_vertices" in window_source
    assert "def fill_authored_floor_plan_face" in window_source
    assert "def triangulate_authored_floor_plan_face" in window_source
    assert "def cleanup_authored_floor_plan_normals" in window_source
    assert '"bridge"' in window_source
    assert '"cut"' in window_source
    assert '"opening"' in window_source
    assert '"mirror"' in window_source
    assert '"combine"' in window_source
    assert '"separate"' in window_source
    assert "floorPlanUnionFirstRoomComboBox" in window_source
    assert "roomPrimitiveSeparateRequested.connect(self.separate_authored_room_primitive)" in window_source
    assert "roomPrimitiveSeparateResultLineEdit" in window_source
    assert "def separate_authored_room_primitive" in window_source
    assert '"cleanup"' in window_source
    assert "edge_index: int" in window_source
    assert "self.controller.map_studio_tool_belt_actions_for_preset" in window_source
    assert "self.map_studio_tool_belt_preset_combo.currentIndexChanged.connect" in window_source
    assert "self.map_studio_customize_tool_belt_button.clicked.connect" in window_source


def test_t2600_map_studio_builder_exposes_script_hook_controls() -> None:
    builder_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    builder_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    for source in (builder_source, builder_mirror_source):
        assert "mapStudioBuilderGuideLabel" in source
        assert "flat test room, doorway blockout, corridor, or terrain patch" in source
        assert "mapStudioRoomGeometryWorkflowLabel" in source
        assert "Starter Room, Doorway Blockout, and Corridor" in source
        assert "Shape it with bevel/inset/cuts, add primitives, then assign material and WOK surface" in source
        assert "mapStudioRoomOperationHintLabel" in source
        assert "rectangular cut creates openings or blockout detail before WOK validation" in source
        assert "mapStudioTerrainWorkflowLabel" in source
        assert "sculpt with raise/lower/smooth/flatten/plateau/ramp/terrace/pinch/erode/noise brushes" in source
        assert "Validate WOK slopes and walkability before export" in source
        assert "scriptHookRequested = QtCore.Signal(str, str, str)" in source
        assert "gameplayPlacementStatusChanged = QtCore.Signal(str)" in source
        assert "Script Hooks" in source
        assert "mapStudioScriptHookScopeComboBox" in source
        assert "mapStudioScriptHookFieldComboBox" in source
        assert "mapStudioScriptHookResrefLineEdit" in source
        assert "mapStudioAssignScriptHookButton" in source
        assert "mapStudioClearScriptHookButton" in source
        assert "set_script_hook_fields" in source
        assert "set_script_hooks" in source
        assert "_emit_assign_script_hook" in source
        assert "mapStudioGameplaySupportedKindsLabel" in source
        assert "Placement types:" in source
        assert "stores/merchants are module-level" in source
        assert "_update_gameplay_supported_kinds_label" in source
        assert "Scan the Game Library to search for creatures, placeables, doors, triggers, encounters, cameras, sounds, waypoints, and stores/merchants." in source
        assert "mapStudioGameplayKindDetailLabel" in source
        assert "_update_gameplay_kind_detail_label" in source
        assert "UTP template" in source
        assert "UTC template" in source
        assert "UTD template" in source
        assert "UTT template" in source
        assert "UTE template" in source
        assert "UTS template" in source
        assert "UTM template" in source
        assert "can be configured as a transition" in source
        assert "without a viewport marker" in source
        assert "mapStudioGameplaySpatialHintLabel" in source
        assert "_update_gameplay_spatial_controls" in source
        assert "Stores/merchants are module-level resources" in source
        assert "_emit_gameplay_placement_status" in source
        assert "placing {kind}" in source

    assert "self.builder_tab.set_script_hook_fields(self.controller.authored_script_hook_field_choices())" in window_source
    assert "self.builder_tab.set_script_hooks(self.controller.authored_script_hooks())" in window_source
    assert "self.builder_tab.scriptHookRequested.connect(self.set_authored_script_hook)" in window_source
    assert "def set_authored_script_hook" in window_source


def test_t2601_map_studio_builder_exposes_modeling_mode_and_snap_palette() -> None:
    builder_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    builder_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    controller_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    controller_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    policy_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "map_studio_modeling_tools.py"
    )
    policy_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/core/modules/"
        "map_studio_modeling_tools.py"
    )
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    for source in (policy_source, policy_mirror_source):
        assert "class MapStudioComponentMode" in source
        assert "class MapStudioModelingTool" in source
        assert "class MapStudioSnapMode" in source
        assert '"vertex"' in source
        assert '"edge"' in source
        assert '"face"' in source
        assert '"walkmesh"' in source
        assert "Weld Vertices" in source
        assert "Bridge" in source
        assert "Extrude" in source
        assert "Fill Face" in source
        assert "Boolean" in source
        assert "Triangulate" in source
        assert "Cleanup Normals" in source
        assert "Terrain Sculpt" in source
        assert "Paint WOK Surface" in source
        assert "Hold V" in source
        assert "KOTOR guardrail" not in source

    for source in (controller_source, controller_mirror_source):
        assert "available_map_studio_component_modes" in source
        assert "available_map_studio_modeling_tools" in source
        assert "available_map_studio_snap_modes" in source
        assert "map_studio_modeling_tool_summary" in source
        assert "Object, Vertex, Edge, Face, and Walkmesh" in source
        assert "snap vertices" in source

    for source in (builder_source, builder_mirror_source):
        assert "Modeling Mode + Snap" in source
        assert "mapStudioModelingModeGuideLabel" in source
        assert "mapStudioComponentModeComboBox" in source
        assert "mapStudioModelingToolComboBox" in source
        assert "mapStudioSnapModeComboBox" in source
        assert "mapStudioModelingToolHintLabel" in source
        assert "mapStudioModelingStatusLabel" in source
        assert "modelingContextChanged = QtCore.Signal(str)" in source
        assert "set_modeling_component_modes" in source
        assert "set_modeling_tools" in source
        assert "set_modeling_snap_modes" in source
        assert "KOTOR guardrail:" in source
        assert "planned; validation-first" in source
        assert "Hold V" in source

    assert "self.builder_tab.set_modeling_component_modes(self.controller.available_map_studio_component_modes())" in window_source
    assert "self.builder_tab.set_modeling_tools(self.controller.available_map_studio_modeling_tools())" in window_source
    assert "self.builder_tab.set_modeling_snap_modes(self.controller.available_map_studio_snap_modes())" in window_source
    assert "self.builder_tab.modelingContextChanged.connect(self.workflow_panel.set_active_authoring_context)" in window_source


def test_t2605_map_studio_toolbar_exposes_goal_aligned_edit_modes() -> None:
    toolbar_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/module_editor_toolbar.py"
    )
    toolbar_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/module_editor_toolbar.py"
    )
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    for source in (toolbar_source, toolbar_mirror_source):
        assert "EDIT_MODES" in source
        assert "mapStudioToolbarEditModeComboBox" in source
        assert "mapStudioToolbarViewModeComboBox" in source
        for mode in ("Object", "Vertex", "Edge", "Face", "Walkmesh", "Placement", "Terrain", "Export"):
            assert f'"{mode}"' in source
        assert "snap, weld, flatten, mirror, and cleanup" in source
        assert "stage, install, hand off, warp-test, and record game proof" in source
        assert "self.selection_mode.currentTextChanged.connect(self.selectionModeChanged.emit)" in source

    assert "self.toolbar.selectionModeChanged.connect(self._handle_map_studio_edit_mode_changed)" in window_source
    assert "def _handle_map_studio_edit_mode_changed" in window_source
    assert 'context = f"{label} mode:' in window_source
    assert '"Vertex": "edit room and walkmesh vertices' in window_source
    assert '"Terrain": "sculpt terrain heightfields' in window_source
    assert "self.workflow_panel.set_active_authoring_context(context)" in window_source
    assert 'self._log(f"Map Studio edit mode changed: {context}")' in window_source


def test_t2603_map_studio_exposes_live_terrain_sculpt_frame_contract() -> None:
    builder_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    builder_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    controller_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    controller_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    sculpt_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "map_studio_terrain_sculpt_session.py"
    )
    sculpt_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/core/modules/"
        "map_studio_terrain_sculpt_session.py"
    )
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/"
        "module_editor_window.py"
    )
    viewport_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/module_editor_viewport_panel.py"
    )
    viewport_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/module_editor_viewport_panel.py"
    )

    for source in (sculpt_source, sculpt_mirror_source):
        assert "class MapStudioTerrainSculptFrame" in source
        assert "class MapStudioTerrainSculptApplyResult" in source
        assert "coalesce_terrain_sculpt_points" in source
        assert "prepare_terrain_sculpt_frame_for_project" in source
        assert "raw_sample_count" in source
        assert "defer_full_rebuild" in source

    for source in (controller_source, controller_mirror_source):
        assert "prepare_map_studio_terrain_sculpt_frame" in source
        assert "apply_map_studio_terrain_sculpt_frame" in source
        assert "MapStudioTerrainSculptApplyResult" in source
        assert "full MDL/WOK rebuild deferred" in source
        assert "return self.authored_module_readiness()" not in source[
            source.index("def apply_map_studio_terrain_sculpt_frame") : source.index("def merge_authored_floor_plan_rooms")
        ]

    for source in (builder_source, builder_mirror_source):
        assert "terrainLiveBrushFrameRequested = QtCore.Signal" in source
        assert "mapStudioCheckLiveTerrainBrushFrameButton" in source
        assert "Check Live Brush Frame" in source
        assert "def current_terrain_brush_context" in source
        assert "def _emit_live_terrain_brush_frame" in source

    for source in (viewport_source, viewport_mirror_source):
        assert "terrainBrushFrameRequested = QtCore.Signal(str, str, object)" in source
        assert "terrainBrushStrokeCommitted = QtCore.Signal(str, str)" in source
        assert "mapStudioViewportTerrainBrushCheckBox" in source
        assert "def set_terrain_brush_interaction" in source
        assert "def _terrain_sample_at_event" in source
        assert "def _terrain_world_at_screen" in source
        assert "def _begin_terrain_brush_drag" in source
        assert "def _update_terrain_brush_drag" in source
        assert "def _finish_terrain_brush_drag" in source

    assert "terrainLiveBrushFrameRequested.connect(self.preview_map_studio_terrain_sculpt_frame)" in window_source
    assert "terrainBrushFrameRequested.connect(self.apply_map_studio_viewport_terrain_brush_frame)" in window_source
    assert "terrainBrushStrokeCommitted.connect(self.commit_map_studio_viewport_terrain_brush_stroke)" in window_source
    assert "def _sync_map_studio_terrain_brush_context" in window_source
    assert "def apply_map_studio_viewport_terrain_brush_frame" in window_source
    live_apply_source = window_source[
        window_source.index("def apply_map_studio_viewport_terrain_brush_frame") :
        window_source.index("def commit_map_studio_viewport_terrain_brush_stroke")
    ]
    assert "apply_map_studio_terrain_sculpt_frame" in live_apply_source
    assert "authored_terrain_walkability_overlay" in live_apply_source
    assert "_refresh_all" not in live_apply_source
    commit_source = window_source[
        window_source.index("def commit_map_studio_viewport_terrain_brush_stroke") :
        window_source.index("def merge_authored_floor_plan_rooms")
    ]
    assert "_refresh_all(message)" in commit_source
    assert "def preview_map_studio_terrain_sculpt_frame" in window_source
    assert "full MDL/WOK rebuild deferred" in window_source


def test_t2600_map_studio_export_panel_explains_safe_stage_install_and_game_proof() -> None:
    export_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/export_panel.py"
    )
    export_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/export_panel.py"
    )

    for source in (export_source, export_mirror_source):
        assert "mapStudioExportScopeLabel" in source
        assert "mapStudioExportSafetyLabel" in source
        assert "mapStudioExportDryRunCheckBox" in source
        assert "mapStudioExportDryRunHintLabel" in source
        assert "mapStudioExportActionGuideLabel" in source
        assert "mapStudioExportActionGuideTable" in source
        assert 'setHorizontalHeaderLabels(("Action", "Writes", "Use when", "Game proof"))' in source
        assert "authored KMAP module as a KOTOR .mod package" in source
        assert "install to a chosen Modules folder with backup" in source
        assert "not game-ready until a live warp test is recorded" in source
        assert "Preview the export/install action without writing final files" in source
        assert "Clear it only when you are ready to write staged files or install for testing" in source
        assert "External FBX scene handoff" in source
        assert "it is not a KOTOR-playable module package" in source
        assert "Staged KOTOR .mod package" in source
        assert ".mod, checklist, proof manifest" in source
        assert ".mod copied to selected Modules folder with backup" in source
        assert "Requires live warp test and recorded evidence." in source


def test_t2600_map_studio_asset_browser_explains_library_import_scope() -> None:
    asset_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/module_editor_asset_browser.py"
    )
    asset_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/module_editor_asset_browser.py"
    )

    for source in (asset_source, asset_mirror_source):
        assert "Library-backed asset browser for the Map Studio Level Editor" in source
        assert "mapStudioAssetBrowserGuideLabel" in source
        assert "Game Library assets: module and tile models import as room references" in source
        assert "creatures, placeables, doors, items, and templates import as reusable blueprints" in source
        assert "Use Builder placement tools when you need a live GIT placement with coordinates" in source
        assert "mapStudioAssetSearchLabel" in source
        assert "Search indexed KOTOR assets" in source
        assert "mapStudioAssetSearchLineEdit" in source
        assert "resref, model name, source, or area" in source
        assert "mapStudioAssetCategoryComboBox" in source
        assert "mapStudioAssetListWidget" in source
        assert "mapStudioAssetDetailLabel" in source
        assert "mapStudioImportSelectedAssetButton" in source
        assert "Import Selected to Level" in source


def test_t2600_map_studio_readiness_panel_lists_runtime_resources() -> None:
    readiness_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/readiness_panel.py"
    )
    readiness_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/readiness_panel.py"
    )

    for source in (readiness_source, readiness_mirror_source):
        assert "mapStudioReadinessPathingLabel" in source
        assert "def _set_pathing_summary" in source
        assert "PTH path graph readiness" in source
        assert "anchors: {anchor_text}" in source
        assert "mapStudioReadinessFloorPlanGeometryLabel" in source
        assert "def _set_floor_plan_geometry_summary" in source
        assert "Floor-plan geometry:" in source
        assert "geometry_validation" in source
        assert "mapStudioReadinessComponentEditLabel" in source
        assert "def _set_component_edit_summary" in source
        assert "Component edits:" in source
        assert "mapStudioReadinessRuntimeResourceTable" in source
        assert 'setHorizontalHeaderLabels(("Resource", "Status", "Fix / meaning"))' in source
        assert "def _set_runtime_resource_rows" in source
        assert "expected_runtime_resources" in source
        assert "present_runtime_resources" in source
        assert "missing_runtime_resources" in source
        assert "Generate or stage this runtime file before export/install." in source
        assert "ARE/GIT/IFO/LYT/VIS/PTH/WOK/MDL/MDX readiness" in source


def test_t2600_map_studio_readiness_panel_lists_gameplay_template_references() -> None:
    readiness_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/readiness_panel.py"
    )
    readiness_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/readiness_panel.py"
    )

    for source in (readiness_source, readiness_mirror_source):
        assert "mapStudioReadinessTemplateReferencesLabel" in source
        assert "mapStudioReadinessTemplateReferenceTable" in source
        assert 'setHorizontalHeaderLabels(("Kind", "Template", "Tag", "Status / fix"))' in source
        assert "gameplay_template_references" in source
        assert "gameplay_template_reference_count" in source
        assert "gameplay_packaged_template_count" in source
        assert "gameplay_external_template_count" in source
        assert "def _set_template_reference_rows" in source
        assert "Template must resolve from the base game, Override, or another installed mod." in source
        assert "Place creatures, placeables, doors, triggers, waypoints, sounds, encounters, cameras, or stores" in source


def test_t2600_map_studio_readiness_panel_lists_transition_and_script_references() -> None:
    readiness_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/readiness_panel.py"
    )
    readiness_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/readiness_panel.py"
    )

    for source in (readiness_source, readiness_mirror_source):
        assert "mapStudioReadinessTransitionReferencesLabel" in source
        assert "mapStudioReadinessTransitionReferenceTable" in source
        assert "mapStudioReadinessScriptReferencesLabel" in source
        assert "mapStudioReadinessScriptReferenceTable" in source
        assert 'setHorizontalHeaderLabels(("Kind", "Tag", "Destination", "Status / fix"))' in source
        assert 'setHorizontalHeaderLabels(("Scope", "Field", "Script", "Status / fix"))' in source
        assert "transition_references" in source
        assert "script_references" in source
        assert "transition_incomplete_count" in source
        assert "script_external_count" in source
        assert "def _set_transition_reference_rows" in source
        assert "def _set_script_reference_rows" in source
        assert "Add a door, trigger, or waypoint transition when this module needs area links." in source
        assert "Assign ARE/IFO script hooks only when this module needs custom runtime behavior." in source


def test_t2600_map_studio_walkmesh_tab_explains_wok_workflow() -> None:
    walkmesh_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/walkmesh_tab.py"
    )
    walkmesh_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/walkmesh_tab.py"
    )
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/"
        "module_editor_window.py"
    )
    controller_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    mirror_controller_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/core/modules/"
        "module_editor_controller.py"
    )

    for source in (walkmesh_source, walkmesh_mirror_source):
        assert "mapStudioWalkmeshWorkflowLabel" in source
        assert "mapStudioWalkmeshSurfaceLabel" in source
        assert "mapStudioWalkmeshValidationHintLabel" in source
        assert "mapStudioWalkmeshStatusLabel" in source
        assert "mapStudioWalkmeshNextActionLabel" in source
        assert "mapStudioWalkmeshFaceTypeComboBox" in source
        assert "mapStudioWalkmeshRoomComboBox" in source
        assert "mapStudioWalkmeshSurfaceComboBox" in source
        assert "mapStudioWalkmeshSurfaceAssignmentLabel" in source
        assert "mapStudioWalkmeshApplySurfaceButton" in source
        assert "roomSurfaceRequested" in source
        assert "def set_room_surface_choices" in source
        assert "def set_walkmesh_surfaces" in source
        assert "def set_walkmesh_status" in source
        assert "Walkmesh status unavailable" in source
        assert "create or load room geometry, generate WOK faces" in source
        assert "1 WALK for reachable floors" in source
        assert "7 NON_WALK for walls/blockers" in source
        assert "18 DOOR for doorway portals" in source
        assert "23 WATER for water surfaces" in source
        assert "Use DOOR only for doorway/transition surfaces." in source
        assert "player start, doors, triggers, waypoints, creatures, and placeables sit on walkable faces" in source
        assert "mapStudioWalkmeshGenerateButton" in source
        assert "mapStudioWalkmeshAssignFaceTypeButton" in source
        assert "mapStudioWalkmeshValidateButton" in source
        assert "mapStudioWalkmeshShowWalkableButton" in source
    assert "authored_walkmesh_status = self.controller.authored_walkmesh_status()" in window_source
    assert "authored_walkmesh_room_surfaces = self.controller.authored_walkmesh_room_surface_choices()" in window_source
    assert "self.walkmesh_tab.set_walkmesh_status(authored_walkmesh_status)" in window_source
    assert "self.walkmesh_tab.set_room_surface_choices(authored_walkmesh_room_surfaces)" in window_source
    assert "self.walkmesh_tab.set_walkmesh_surfaces(self.controller.available_authored_walkmesh_surfaces())" in window_source
    assert "self.walkmesh_tab.roomSurfaceRequested.connect(self.apply_authored_walkmesh_surface)" in window_source
    assert "self.controller.set_authored_room_walkmesh_surface" in window_source
    for source in (controller_source, mirror_controller_source):
        assert "AuthoredWalkmeshStatus" in source
        assert "authored_walkmesh_status_for_project" in source
        assert "def authored_walkmesh_status(self)" in source
        assert "authored_walkmesh_room_surface_choices" in source
        assert "def set_authored_room_walkmesh_surface" in source


def test_t2600_map_studio_rooms_tab_explains_room_graph_workflow() -> None:
    rooms_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/rooms_tab.py"
    )
    rooms_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/rooms_tab.py"
    )

    for source in (rooms_source, rooms_mirror_source):
        assert "mapStudioRoomsWorkflowLabel" in source
        assert "mapStudioRoomsLayoutHintLabel" in source
        assert "mapStudioRoomsAuthoringHintLabel" in source
        assert "load or author room layout, arrange room positions" in source
        assert "validate LYT/VIS links before packaging" in source
        assert "LYT stores room models and transforms" in source
        assert "VIS controls which rooms can see each other" in source
        assert "Keep room resrefs stable for WOK, MDL/MDX, and placed resources" in source
        assert "Use Builder for new geometry" in source
        assert "mapStudioRoomsLoadLytButton" in source
        assert "mapStudioRoomsAddRoomButton" in source
        assert "mapStudioRoomsRemoveRoomButton" in source
        assert "mapStudioRoomsDuplicateRoomButton" in source
        assert "mapStudioRoomsSaveLayoutButton" in source
        assert "mapStudioRoomsFocusSelectedButton" in source
        assert "mapStudioRoomsAutoArrangeButton" in source
        assert "mapStudioRoomsSnapToGridButton" in source


def test_t2600_map_studio_blueprints_tab_explains_template_workflow() -> None:
    blueprints_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/blueprints_tab.py"
    )
    blueprints_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/blueprints_tab.py"
    )

    for source in (blueprints_source, blueprints_mirror_source):
        assert "mapStudioBlueprintWorkflowLabel" in source
        assert "mapStudioBlueprintResourceTypesLabel" in source
        assert "mapStudioBlueprintPlacementHintLabel" in source
        assert "edit KOTOR resource templates, validate them, then place instances" in source
        assert "UTC creatures, UTP placeables, UTD doors, UTT triggers" in source
        assert "UTW waypoints, UTS sounds, UTE encounters, and UTM merchants/stores" in source
        assert "position, bearing, transition/script fields, and walkmesh validation" in source
        assert "mapStudioBlueprintTypeComboBox" in source
        assert "mapStudioBlueprintOpenButton" in source
        assert "mapStudioBlueprintSaveButton" in source
        assert "mapStudioBlueprintAddButton" in source
        assert "mapStudioBlueprintRemoveButton" in source
        assert "mapStudioBlueprintSendToGModularButton" in source
        assert "mapStudioBlueprintPlaceInSceneButton" in source
        assert "mapStudioBlueprintValidateButton" in source


def test_t2600_map_studio_validation_panel_explains_actionable_fixes() -> None:
    validation_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/validation_panel.py"
    )
    validation_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/validation_panel.py"
    )

    for source in (validation_source, validation_mirror_source):
        assert "Map Studio validation issues" in source
        assert "Shows blocking issues, warnings, affected items, and suggested fixes" in source
        assert "Validation workflow: fix blocking issues first" in source
        assert "Double-click an issue to focus its item" in source
        assert "No validation issues are currently listed" in source
        assert "export/install still requires staged output and in-game proof" in source
        assert "Validate again after edits" in source
        assert "NoEditTriggers" in source
        assert "_add_empty_state_row" in source
        assert "_issue_tooltip" in source
        assert "Fix:" in source


def test_t2600_map_studio_outliner_explains_selection_editing_workflow() -> None:
    outliner_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/module_editor_outliner.py"
    )
    outliner_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/module_editor_outliner.py"
    )

    for source in (outliner_source, outliner_mirror_source):
        assert "Map Studio project outliner" in source
        assert "modules, rooms, walkmeshes, authored placements, lights, blueprints, and resources" in source
        assert "Outliner workflow: select resources" in source
        assert "double-click or use Rename" in source
        assert "KMAP Project / Resources" in source
        assert "mapStudioOutlinerContextMenu" in source
        assert "mapStudioOutlinerRenameAction" in source
        assert '("Rename", "rename", "mapStudioOutlinerRenameAction")' in source
        assert "mapStudioOutlinerDuplicateAction" in source
        assert "mapStudioOutlinerDeleteAction" in source
        assert "mapStudioOutlinerFocusViewportAction" in source
        assert "mapStudioOutlinerValidateSelectedAction" in source
        assert "Right-click for Rename, Duplicate, Delete, Focus, and Validate actions" in source


def test_t2600_map_studio_outliner_add_camera_and_light_are_wired_to_services() -> None:
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    assert "def add_map_studio_camera" in window_source
    assert "def add_map_studio_room_light" in window_source
    assert '"add_camera": "Add Camera"' in window_source
    assert '"add_light": "Add Light"' in window_source
    assert 'if action == "Add Camera":' in window_source
    assert 'self.add_map_studio_camera()' in window_source
    assert 'if action == "Add Light":' in window_source
    assert 'self.add_map_studio_room_light()' in window_source
    assert 'self.add_authored_gameplay_placement(' in window_source
    assert '"camera",' in window_source
    assert "self.add_authored_room_light(" in window_source
    assert "Camera: authored camera marker added" in window_source
    assert "Lighting: authored room light added" in window_source


def test_t2600_map_studio_properties_exposes_transition_controls() -> None:
    properties_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/module_editor_properties.py"
    )
    properties_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/module_editor_properties.py"
    )
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    for source in (properties_source, properties_mirror_source):
        assert "transitionChanged = QtCore.Signal(str, str, str, int)" in source
        assert "mapStudioTransitionPropertiesGroup" in source
        assert "mapStudioTransitionLinkedToLineEdit" in source
        assert "mapStudioTransitionLinkedModuleLineEdit" in source
        assert "mapStudioTransitionDestinationSpinBox" in source
        assert "transition_capable" in source
        assert "self.transition_group.setVisible(transition_capable)" in source
        assert "def _transition_changed" in source
        assert "is_spatial" in source
        assert "module-level resource" in source

    assert "self.properties.transitionChanged.connect(self._set_authored_gameplay_transition)" in window_source
    assert "def _set_authored_gameplay_transition" in window_source
    assert "self.controller.set_authored_gameplay_transition" in window_source


def test_t2600_map_studio_properties_exposes_selected_room_light_controls() -> None:
    properties_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/module_editor_properties.py"
    )
    properties_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/module_editor_properties.py"
    )
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    for source in (properties_source, properties_mirror_source):
        assert "roomLightChanged = QtCore.Signal(str, str, object, float, float)" in source
        assert "mapStudioRoomLightPropertiesGroup" in source
        assert "mapStudioRoomLightTypeComboBox" in source
        assert "mapStudioRoomLightColorRSpinBox" in source
        assert "mapStudioRoomLightColorGSpinBox" in source
        assert "mapStudioRoomLightColorBSpinBox" in source
        assert "mapStudioRoomLightRadiusSpinBox" in source
        assert "mapStudioRoomLightIntensitySpinBox" in source
        assert "self.room_light_group.setVisible(True)" in source
        assert "def _room_light_changed" in source

    assert "self.properties.roomLightChanged.connect(self._set_authored_room_light_properties)" in window_source
    assert "def _set_authored_room_light_properties" in window_source
    assert "self.controller.set_authored_room_light_properties" in window_source
    assert "Updated authored room light properties." in window_source


def test_t2600_map_studio_properties_exposes_selected_camera_controls() -> None:
    properties_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/module_editor_properties.py"
    )
    properties_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/module_editor_properties.py"
    )
    window_source = _read(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/"
        "module_editor_window.py"
    )
    controller_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    placement_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "authored_module_placements.py"
    )

    for source in (properties_source, properties_mirror_source):
        assert "cameraChanged = QtCore.Signal(str, int, float, float, float, float)" in source
        assert "mapStudioCameraPropertiesGroup" in source
        assert "mapStudioCameraIdSpinBox" in source
        assert "mapStudioCameraFieldOfViewSpinBox" in source
        assert "mapStudioCameraHeightSpinBox" in source
        assert "mapStudioCameraMicRangeSpinBox" in source
        assert "mapStudioCameraPitchSpinBox" in source
        assert "self.camera_group.setVisible(True)" in source
        assert "Camera exports to the module GIT CameraList" in source
        assert "def _camera_changed" in source

    assert "self.properties.cameraChanged.connect(self._set_authored_gameplay_camera_properties)" in window_source
    assert "def _set_authored_gameplay_camera_properties" in window_source
    assert "self.controller.set_authored_gameplay_camera_properties" in window_source
    assert "Updated authored camera properties." in window_source
    assert "def set_authored_gameplay_camera_properties" in controller_source
    assert "update_authored_gameplay_camera_properties" in controller_source
    assert "last_gameplay_camera_properties" in placement_source


def test_t2600_map_studio_viewport_skips_non_spatial_store_rows() -> None:
    viewport_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/module_editor_viewport_panel.py"
    )
    viewport_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/module_editor_viewport_panel.py"
    )
    preview_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "authored_gameplay_preview.py"
    )
    preview_mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/core/modules/"
        "authored_gameplay_preview.py"
    )

    for source in (viewport_source, viewport_mirror_source):
        assert 'if not bool(getattr(placement, "is_spatial", True))' in source
        assert "continue" in source

    for source in (preview_source, preview_mirror_source):
        assert 'if not bool(getattr(row, "is_spatial", True))' in source
        assert "return None" in source


def test_t2600_workflow_panel_is_mirrored_for_module_meshes_package() -> None:
    mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/workflow_panel.py"
    )
    mirror_init = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/__init__.py"
    )

    assert "class MapStudioWorkflowPanel" in mirror_source
    assert "mapStudioWorkflowResourcesLabel" in mirror_source
    assert "mapStudioWorkflowTargetGameLabel" in mirror_source
    assert "mapStudioWorkflowCapabilityLabel" in mirror_source
    assert "mapStudioWorkflowTestStateLabel" in mirror_source
    assert "mapStudioWorkflowActiveContextLabel" in mirror_source
    assert "mapStudioWorkflowSelectionLabel" in mirror_source
    assert "mapStudioWorkflowNewKmapButton" in mirror_source
    assert "mapStudioWorkflowOpenKmapButton" in mirror_source
    assert "mapStudioWorkflowSaveKmapButton" in mirror_source
    assert "mapStudioWorkflowRenameSelectedButton" in mirror_source
    assert "mapStudioWorkflowDuplicateSelectedButton" in mirror_source
    assert "mapStudioWorkflowDeleteSelectedButton" in mirror_source
    assert "mapStudioWorkflowFocusSelectedButton" in mirror_source
    assert "mapStudioWorkflowGeometryToolsButton" in mirror_source
    assert "mapStudioWorkflowMissingResourcesLabel" in mirror_source
    assert "mapStudioWorkflowGeometryLabel" in mirror_source
    assert "mapStudioWorkflowWalkmeshLabel" in mirror_source
    assert "mapStudioWorkflowLightingLabel" in mirror_source
    assert "mapStudioWorkflowTerrainToolsButton" in mirror_source
    assert "mapStudioWorkflowLightingToolsButton" in mirror_source
    assert "mapStudioWorkflowPlacementLabel" in mirror_source
    assert "mapStudioWorkflowScriptToolsButton" in mirror_source
    assert "def set_active_authoring_context" in mirror_source
    assert "mapStudioWorkflowLayoutLabel" in mirror_source
    assert "mapStudioWorkflowTransitionsLabel" in mirror_source
    assert "mapStudioWorkflowScriptsLabel" in mirror_source
    assert "mapStudioWorkflowProofLabel" in mirror_source
    assert "mapStudioWorkflowStarterRoomButton" in mirror_source
    assert "mapStudioWorkflowDoorwayBlockoutButton" in mirror_source
    assert "mapStudioWorkflowCorridorButton" in mirror_source
    assert "mapStudioWorkflowStarterTerrainButton" in mirror_source
    assert "mapStudioWorkflowPlacementToolsButton" in mirror_source
    assert "mapStudioWorkflowTestPlaceableButton" in mirror_source
    assert "mapStudioWorkflowWalkmeshToolsButton" in mirror_source
    assert "mapStudioWorkflowStageButton" in mirror_source
    assert "mapStudioWorkflowLaunchHandoffButton" in mirror_source
    assert "newProjectRequested = QtCore.Signal()" in mirror_source
    assert "openProjectRequested = QtCore.Signal()" in mirror_source
    assert "saveProjectRequested = QtCore.Signal()" in mirror_source
    assert "renameSelectedRequested = QtCore.Signal()" in mirror_source
    assert "duplicateSelectedRequested = QtCore.Signal()" in mirror_source
    assert "deleteSelectedRequested = QtCore.Signal()" in mirror_source
    assert "focusSelectedRequested = QtCore.Signal()" in mirror_source
    assert "builderRequested = QtCore.Signal()" in mirror_source
    assert "geometryToolsRequested = QtCore.Signal()" in mirror_source
    assert "starterRoomRequested = QtCore.Signal()" in mirror_source
    assert "doorwayBlockoutRequested = QtCore.Signal()" in mirror_source
    assert "corridorRequested = QtCore.Signal()" in mirror_source
    assert "starterTerrainRequested = QtCore.Signal()" in mirror_source
    assert "placementToolsRequested = QtCore.Signal()" in mirror_source
    assert "testPlaceableRequested = QtCore.Signal()" in mirror_source
    assert "walkmeshToolsRequested = QtCore.Signal()" in mirror_source
    assert "launchHandoffRequested = QtCore.Signal()" in mirror_source
    assert "Capability: Export candidate" in mirror_source
    assert "Target game:" in mirror_source
    assert "Test state:" in mirror_source
    assert "def _test_state_text" in mirror_source
    assert "Required resources missing" in mirror_source
    assert "Geometry authoring" in mirror_source
    assert "Walkmesh" in mirror_source
    assert "Lighting/lightmaps:" in mirror_source
    assert '"Lighting"' in mirror_source
    assert "Resource placement:" in mirror_source
    assert '"Resource placement"' in mirror_source
    assert "creatures, placeables, doors, triggers, encounters, cameras, sounds, merchants, and waypoints" in mirror_source
    assert "Gameplay layout" in mirror_source
    assert "Transitions:" in mirror_source
    assert "Scripts:" in mirror_source
    assert "def set_selection_context" in mirror_source
    assert "MapStudioWorkflowPanel" in mirror_init


def test_t2600_map_studio_workflow_panel_guides_first_playable_smoke_test() -> None:
    panel_source = _read(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/"
        "module_editor/workflow_panel.py"
    )
    mirror_source = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/"
        "module_editor/workflow_panel.py"
    )

    for source in (panel_source, mirror_source):
        assert "mapStudioWorkflowSmokeTestLabel" in source
        assert "mapStudioWorkflowSmokeTestRecipeTable" in source
        assert 'setHorizontalHeaderLabels(("Step", "Action", "Proof"))' in source
        assert "First playable map smoke test" in source
        assert "one starter room" in source
        assert "one test placeable" in source
        assert "Treat larger maps as experimental until this path passes in-game." in source
        assert "New KMAP" in source
        assert "Create Starter Room" in source
        assert "Add Test Placeable" in source
        assert "Validate" in source
        assert "Stage or Install for Game Test" in source
        assert "warp <module> and Record Proof" in source
        assert "Only then call it game-tested." in source
        assert "A safe staged package and warp handoff are produced." in source


def test_t2600_map_studio_readiness_validation_projection_is_mirrored() -> None:
    source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "authored_module_validation_projection.py"
    )
    mirror = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/core/modules/"
        "authored_module_validation_projection.py"
    )
    controller_source = _read(
        "native/GhostRigger.Domain.Core.Modules/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    controller_mirror = _read(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/core/modules/"
        "module_editor_controller.py"
    )

    for text in (source, mirror):
        assert "authored_module_readiness_validation_issues" in text
        assert "MAP_STUDIO_RUNTIME_RESOURCE_MISSING" in text
        assert "MAP_STUDIO_GAME_PROOF_REQUIRED" in text
        assert "MAP_STUDIO_FLOOR_PLAN_GEOMETRY_BLOCKER" in text
        assert "MAP_STUDIO_FLOOR_PLAN_GEOMETRY_WARNING" in text
        assert "geometry_validation" in text
        assert "Suggested" not in text

    for text in (controller_source, controller_mirror):
        assert "from .authored_module_validation_projection import authored_module_readiness_validation_issues" in text
        assert "issues.extend(" in text
        assert "bridge_warnings=readiness_result.warnings" in text
