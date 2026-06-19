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
    assert "mapStudioWorkflowCapabilityLabel" in panel_source
    assert "mapStudioWorkflowAuthoringLabel" in panel_source
    assert "mapStudioWorkflowActiveContextLabel" in panel_source
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
    assert "mapStudioWorkflowOpenBuilderButton" in panel_source
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
    assert "builderRequested = QtCore.Signal()" in panel_source
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
    assert "Not game-ready until a live KOTOR warp test is recorded" in panel_source
    assert "Capability: Export candidate" in panel_source
    assert "Capability: Installed test build" in panel_source
    assert "Capability: Staged test build" in panel_source
    assert "Capability: Game-tested" in panel_source
    assert "Required resources missing" in panel_source
    assert "generate or stage these module files before export/install" in panel_source
    assert "Geometry authoring" in panel_source
    assert "Walkmesh" in panel_source
    assert "Lighting/lightmaps:" in panel_source
    assert '"Lighting"' in panel_source
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
    assert "self.workflow_panel.builderRequested.connect(self.show_map_studio_builder)" in window_source
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
    assert "def show_map_studio_builder" in window_source
    assert "Builder: room, terrain, placement, lighting, and script authoring" in window_source
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
        assert "mapStudioGameplaySpatialHintLabel" in source
        assert "_update_gameplay_spatial_controls" in source
        assert "Stores/merchants are module-level resources" in source
        assert "_emit_gameplay_placement_status" in source
        assert "placing {kind}" in source

    assert "self.builder_tab.set_script_hook_fields(self.controller.authored_script_hook_field_choices())" in window_source
    assert "self.builder_tab.set_script_hooks(self.controller.authored_script_hooks())" in window_source
    assert "self.builder_tab.scriptHookRequested.connect(self.set_authored_script_hook)" in window_source
    assert "def set_authored_script_hook" in window_source


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
    assert "mapStudioWorkflowCapabilityLabel" in mirror_source
    assert "mapStudioWorkflowActiveContextLabel" in mirror_source
    assert "mapStudioWorkflowNewKmapButton" in mirror_source
    assert "mapStudioWorkflowOpenKmapButton" in mirror_source
    assert "mapStudioWorkflowSaveKmapButton" in mirror_source
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
    assert "builderRequested = QtCore.Signal()" in mirror_source
    assert "starterRoomRequested = QtCore.Signal()" in mirror_source
    assert "doorwayBlockoutRequested = QtCore.Signal()" in mirror_source
    assert "corridorRequested = QtCore.Signal()" in mirror_source
    assert "starterTerrainRequested = QtCore.Signal()" in mirror_source
    assert "placementToolsRequested = QtCore.Signal()" in mirror_source
    assert "testPlaceableRequested = QtCore.Signal()" in mirror_source
    assert "walkmeshToolsRequested = QtCore.Signal()" in mirror_source
    assert "launchHandoffRequested = QtCore.Signal()" in mirror_source
    assert "Capability: Export candidate" in mirror_source
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
    assert "MapStudioWorkflowPanel" in mirror_init


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
        assert "Suggested" not in text

    for text in (controller_source, controller_mirror):
        assert "from .authored_module_validation_projection import authored_module_readiness_validation_issues" in text
        assert "issues.extend(" in text
        assert "bridge_warnings=readiness_result.warnings" in text
