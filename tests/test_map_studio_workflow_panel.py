from __future__ import annotations

import os
import sys
from dataclasses import replace
from pathlib import Path
from time import perf_counter, sleep
from types import SimpleNamespace

import pytest


def test_t3002_direct_placement_workspace_and_viewport_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    display = root / "native" / "GhostRigger.Core.GUI.Display" / "Python" / "src" / "gui" / "panels" / "module_editor"
    placement_source = (display / "placement_tab.py").read_text(encoding="utf-8")
    viewport_source = (display / "module_editor_viewport_panel.py").read_text(encoding="utf-8")
    window_source = (
        root / "native" / "GhostRigger.Core.Tools" / "Python" / "src" / "gui" / "windows" / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    for token in (
        "mapStudioPlaceInViewportButton",
        "mapStudioPlacementSnapWalkmeshCheckBox",
        "mapStudioPlacementInstanceComboBox",
        "placementModeChanged",
        "transformRequested",
        "snap_to_walkmesh",
    ):
        assert token in placement_source
    for token in (
        "placementRequested = QtCore.Signal(object)",
        "set_placement_tool_context",
        "_place_from_viewport_event",
        "KOTOR GIT placements do not support arbitrary scale",
        "math.radians(delta_degrees)",
    ):
        assert token in viewport_source
    for token in (
        "self.placement_tab = PlacementTab()",
        '("Place", self.placement_tab)',
        "_place_authored_gameplay_from_viewport",
        "snap_authored_gameplay_placement_to_walkmesh",
    ):
        assert token in window_source


ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _install_native_payload_paths() -> None:
    for rel in reversed(
        (
            "native/GhostRigger.Core.Scene/Python",
            "native/GhostRigger.Core.Tools/Python",
            "native/GhostRigger.Core.Resources/Python",
            "native/GhostRigger.Core.Project/Python",
            "native/GhostRigger.Core.IO/Python",
            "native/GhostRigger.Core.Workflow/Python",
            "native/GhostRigger.Core.Math/Python",
            "native/GhostRigger.Core.Rendering/Python",
            ".",
        )
    ):
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2600_map_studio_workflow_panel_surfaces_editor_spine() -> None:
    panel_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/workflow_panel.py"
    )

    assert "class MapStudioWorkflowPanel" in panel_source
    assert "mapStudioWorkflowProjectLabel" in panel_source
    assert "mapStudioWorkflowTargetGameLabel" in panel_source
    assert "mapStudioWorkflowCapabilityLabel" in panel_source
    assert "mapStudioWorkflowTestStateLabel" in panel_source
    assert "mapStudioWorkflowAuthoringLabel" in panel_source
    assert "mapStudioWorkflowActiveContextLabel" in panel_source
    assert "mapStudioWorkflowModeLabel" in panel_source
    assert "mapStudioWorkflowEditingTargetLabel" in panel_source
    assert "mapStudioWorkflowSelectionLabel" in panel_source
    assert "mapStudioWorkflowResourcesLabel" in panel_source
    assert "mapStudioWorkflowMissingResourcesLabel" in panel_source
    assert "mapStudioWorkflowGeometryLabel" in panel_source
    assert "mapStudioWorkflowWalkmeshLabel" in panel_source
    assert "mapStudioWorkflowVisibilityLabel" in panel_source
    assert "mapStudioWorkflowLightingLabel" in panel_source
    assert "mapStudioWorkflowPlacementLabel" in panel_source
    assert "mapStudioWorkflowLayoutLabel" in panel_source
    assert "mapStudioWorkflowTransitionsLabel" in panel_source
    assert "mapStudioWorkflowScriptsLabel" in panel_source
    assert "mapStudioWorkflowValidationLabel" in panel_source
    assert "mapStudioWorkflowExportLabel" in panel_source
    assert "mapStudioWorkflowExportJobLabel" in panel_source
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
    assert "can_export_candidate" in panel_source
    assert "PTH/WOK pathing blocked" in panel_source
    assert "self.stage_button.setEnabled(bool(enabled and can_export))" in panel_source
    assert "self.install_button.setEnabled(bool(enabled and can_export))" in panel_source
    assert "Game-tested. Live warp proof is recorded" in panel_source
    assert "Not game-ready until a live KOTOR warp test is recorded" in panel_source
    assert "Capability: Export candidate" in panel_source
    assert "Capability: Installed test build" in panel_source
    assert "Capability: Staged test build" in panel_source
    assert "Capability: Game-tested" in panel_source
    assert "def _export_job_text" in panel_source
    assert "ExportJob: Ready to stage; no package transaction recorded yet." in panel_source
    assert "preflight ready" in panel_source
    assert "package written" in panel_source
    assert "readback OK" in panel_source
    assert "game smoke tested" in panel_source
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
    assert "VIS visibility:" in panel_source
    assert '"VIS visibility"' in panel_source
    assert (
        'self.visibility_label,\n'
        '            readiness,\n'
        '            "VIS visibility",\n'
        '            "VIS visibility",\n'
        '            "VIS status unavailable.",'
    ) in panel_source
    assert "Lighting/lightmaps:" in panel_source
    assert '"Lighting"' in panel_source


def test_t2600_map_studio_new_project_dialog_exposes_module_identity() -> None:
    panel_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/workflow_panel.py"
    )
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )
    controller_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    mirror_controller_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
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
    assert "def set_edit_mode_context" in panel_source
    assert "KOTOR rule:" in panel_source
    assert "Active tool:" in panel_source
    assert "def set_selection_context" in panel_source
    assert "Selected: none" in panel_source
    assert "def _test_state_text" in panel_source
    assert "ARE/GIT/IFO/LYT/VIS/PTH/WOK/MDL/MDX" in panel_source


def test_t2600_level_editor_wires_workflow_panel_to_readiness_contract() -> None:
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )
    init_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/__init__.py"
    )

    assert "from src.gui.panels.module_editor.workflow_panel import MapStudioWorkflowPanel" in window_source
    assert "self.workflow_panel = MapStudioWorkflowPanel(right)" in window_source
    assert "export_layout.addWidget(self.workflow_panel)" in window_source
    assert "readiness_result = self.controller.authored_module_readiness()" in window_source
    assert "self.workflow_panel.set_state(self.project, readiness_result.readiness)" in window_source
    assert "self.export_panel.set_readiness(readiness_result.readiness)" in window_source
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
    assert "self.export_panel.builderFixRequested.connect(self.show_map_studio_builder)" in window_source
    assert "self.export_panel.walkmeshFixRequested.connect(self.show_map_studio_walkmesh_tools)" in window_source
    assert "self.export_panel.placementFixRequested.connect(self.show_map_studio_placement_tools)" in window_source
    assert "self.export_panel.validateRequested.connect(self.validate_kmap)" in window_source
    assert "self.export_panel.selectFixTargetRequested.connect(self._select_map_studio_export_fix_target)" in window_source
    assert "def _select_map_studio_export_fix_target" in window_source
    assert "self._focus_map_studio_entry_point_controls()" in window_source
    assert "self.select_item(target)" in window_source
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


def test_map_studio_top_focus_button_routes_to_selected_scene_row() -> None:
    for rel in (
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py",
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py",
    ):
        source = _read(rel)
        assert "self.focus_button.clicked.connect(self.focus_selected)" in source


def test_t2600_level_editor_exposes_map_studio_workspace_switcher() -> None:
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )
    controller_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    mirror_controller_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    model_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
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
    assert "def _set_map_studio_workspace_combo_key" in window_source
    assert "def _set_map_studio_toolbar_edit_mode" in window_source
    assert "def _handle_map_studio_workspace_changed" in window_source
    assert "def _open_selected_map_studio_workspace" in window_source
    assert 'self._set_map_studio_workspace_combo_key("geometry")' in window_source
    assert 'self._set_map_studio_workspace_combo_key("terrain")' in window_source
    assert 'self._set_map_studio_workspace_combo_key("walkmesh")' in window_source
    assert 'self._set_map_studio_workspace_combo_key("placements")' in window_source
    assert 'self._set_map_studio_workspace_combo_key("lighting")' in window_source
    assert 'self._set_map_studio_workspace_combo_key("scripts")' in window_source
    assert 'self._set_map_studio_workspace_combo_key("export")' in window_source
    assert 'self._set_map_studio_toolbar_edit_mode("Terrain")' in window_source
    assert 'self._set_map_studio_toolbar_edit_mode("Walkmesh")' in window_source
    assert 'self._set_map_studio_toolbar_edit_mode("Placement")' in window_source
    assert 'self._set_map_studio_toolbar_edit_mode("Export")' in window_source
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
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    builder_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )
    controller_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    controller_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    tools_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "map_studio_modeling_tools.py"
    )
    tools_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
        "map_studio_modeling_tools.py"
    )
    preferences_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "map_studio_tool_belt_preferences.py"
    )
    preferences_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
        "map_studio_tool_belt_preferences.py"
    )
    export_objects_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "map_studio_export_objects.py"
    )
    export_objects_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
        "map_studio_export_objects.py"
    )
    readiness_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "authored_module_readiness.py"
    )
    readiness_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
        "authored_module_readiness.py"
    )
    readiness_panel_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/readiness_panel.py"
    )
    readiness_panel_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
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
        assert "def select_floor_plan_edge(self, room_resref: str, edge_index: int) -> bool" in source
        assert "Bridge, Wall Opening, and Edge Extrude now target this floor-plan edge." in source
        assert "self._select_combo_room_resref(self.floorPlanOpeningRoomComboBox, room)" in source
        assert "self._select_combo_room_resref(self.floorPlanBridgeFirstRoomComboBox, room)" in source
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
        assert "mapStudioFloorPlanOpeningMarkerTargetTypeComboBox" in source
        assert "mapStudioFloorPlanOpeningMarkerTransitionDestSpinBox" in source
        assert "mapStudioCreateOpeningTransitionMarkerButton" in source
        assert "def _emit_floor_plan_opening_marker" in source
        assert "Floor-Plan Vertex Tools" in source
        assert "floorPlanVertexSnapPreviewRequested = QtCore.Signal" in source
        assert "floorPlanVertexSnapRequested = QtCore.Signal" in source
        assert "floorPlanVertexWeldRequested = QtCore.Signal" in source
        assert "floorPlanVertexFlattenRequested = QtCore.Signal" in source
        assert "mapStudioFloorPlanVertexRoomComboBox" in source
        assert "mapStudioFloorPlanVertexTargetRoomComboBox" in source
        assert "mapStudioFloorPlanSelectedPointsLineEdit" in source
        assert "mapStudioSnapFloorPlanVertexButton" in source
        assert "mapStudioWeldFloorPlanVerticesButton" in source
        assert "mapStudioFlattenFloorPlanVerticesButton" in source
        assert "def set_floor_plan_vertex_snap_candidates" in source
        assert "Click Snap Vertex to commit; this preview does not weld topology." in source
        assert "mapStudioFloorPlanMirrorAxisComboBox" in source
        assert "mapStudioMirrorFloorPlanVerticesButton" in source
        assert "mapStudioFloorPlanCleanupToleranceSpinBox" in source
        assert "mapStudioCleanupFloorPlanVerticesButton" in source
        assert "floorPlanVertexCleanupRequested = QtCore.Signal" in source
        assert "floorPlanVertexMirrorRequested = QtCore.Signal" in source
        assert "floorPlanFaceFillRequested = QtCore.Signal" in source
        assert "floorPlanFaceSplitRequested = QtCore.Signal" in source
        assert "floorPlanFaceTriangulateRequested = QtCore.Signal" in source
        assert "floorPlanNormalsCleanupRequested = QtCore.Signal" in source
        assert "mapStudioFillFloorPlanFaceButton" in source
        assert "mapStudioSplitFloorPlanFaceButton" in source
        assert "mapStudioTriangulateFloorPlanFaceButton" in source
        assert "mapStudioCleanupFloorPlanNormalsButton" in source
        assert "Fill Selected Face Loop" in source
        assert "Split Face Between Points" in source
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
        assert 'self.buildSectionTabs.addTab(self.roomBuildingPage, "Room Building")' in source
        assert 'self.buildSectionTabs.addTab(self.terrainBuildingPage, "Terrain Building")' in source
        assert 'self.buildSectionTabs.addTab(self.skyboxBuildingPage, "Skybox")' in source
        assert "mapStudioMagneticRoomAssemblyGroup" in source
        assert "mapStudioCreateTerrainSurfaceButton" in source
        assert "mapStudioTerrainViewportSculptCheckBox" in source
        assert "mapStudioTerrainDressingGroup" in source
        assert "def adopt_skybox_tools" in source

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
        assert "MapStudioToolCommandSearchResult" in source
        assert "map_studio_tool_command_search" in source
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
        assert '"sculpt_erase"' in source
        assert '"sculpt_plateau"' in source
        assert '"sculpt_ramp"' in source
        assert '"sculpt_slope"' in source
        assert "optional X/Y symmetry" in source
        assert '"sculpt_terrace"' in source
        assert '"sculpt_pinch"' in source
        assert '"sculpt_erode"' in source
        assert '"sculpt_noise"' in source
        assert '"combine"' in source
        assert '"Combine"' in source
        assert '"Combine compatible rectangular floor-plan rooms through the supported room-union workflow; broader primitive/object combine is a future mesh-editing pass."' in source
        assert '"snap_vertices"' in source
        assert '"Snap Vertex"' in source
        assert "Snapping is not welding" in source
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
        assert '"arch"' in source
        assert '"Arch"' in source
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
        assert "map_studio_tool_command_search" in source
        assert "map_studio_tool_belt_preferences" in source
        assert "set_map_studio_tool_belt_preferences" in source
        assert "MAP_STUDIO_TOOL_BELT_SECTION" in source
        assert "def available_map_studio_tool_belt_actions" in source
        assert "def available_map_studio_tool_belt_presets" in source
        assert "def available_map_studio_terrain_brushes" in source
        assert "def map_studio_viewport_performance_policy" in source
        assert "def map_studio_tool_belt_actions_for_preset" in source
        assert "def map_studio_tool_command_search" in source
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
        assert "dcc_handoff_status" in source
        assert "dcc_handoff_reason" in source
        assert "resource_boundary_policy" in source
        assert "owns_walkmesh" in source
        assert "source_operation" in source
        assert "source_room_resrefs" in source
        assert '"ready_for_external_uv"' in source
        assert '"one_room_mdl_mdx_wok"' in source

    for source in (readiness_source, readiness_mirror_source):
        assert "map_studio_export_object_boundaries" in source
        assert '"export_object_boundaries"' in source
        assert '"uv_handoff_object_count"' in source
        assert "class AuthoredComponentEditReadiness" in source
        assert "def _component_edit_readiness" in source
        assert "component_edit: AuthoredComponentEditReadiness" in source
        assert '"component_edit"' in source
        assert "resource_impacts" in source
        assert "_component_edit_resource_impacts" in source
        assert "Walkmesh may no longer match the edited floor or openings." in source
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
        assert "Ready for DCC/UV handoff" in source
        assert "Needs WOK before DCC handoff" in source
        assert "source_operation" in source
        assert "owns WOK" in source
        assert "mapStudioReadinessComponentEditLabel" in source
        assert "mapStudioReadinessComponentEditResourceTable" in source
        assert "mapStudioReadinessDoorwayTransitionLabel" in source
        assert "def _set_doorway_transition_summary" in source
        assert "Doorway/transition intent: Not checked" in source
        assert "def _set_component_edit_summary" in source
        assert "def _set_component_edit_resource_rows" in source
        assert "Component edits: Not checked" in source
        assert "Fix before export" in source
        assert "No stale component-edit outputs" in source
        assert "Stale outputs:" in source
        assert "Next:" in source
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
    assert "Create grgold01 Golden Proof Module" in builder_source
    assert "Create grgold01 Golden Proof Module" in builder_mirror_source
    assert 'if action == "Create grgold01 Golden Proof Module":' in window_source
    assert "self.controller.create_golden_test_authored_module()" in window_source
    assert "door transition intent, and NPC" in window_source
    assert "def _focus_map_studio_entry_point_controls" in window_source
    assert "def _focus_map_studio_opening_marker_controls" in window_source
    assert "def _map_studio_export_dry_run_enabled" in window_source
    assert "def _ensure_map_studio_export_output_dir" in window_source
    assert "def _ensure_map_studio_game_modules_dir" in window_source
    assert "def _open_map_studio_package_wizard" in window_source
    assert "Map Studio package command canceled before any files were written." in window_source
    assert "def _map_studio_authored_module_root_for_install" in window_source
    assert "def _focus_map_studio_export_proof_workspace" in window_source
    assert "def set_authored_module_entry_point" in window_source
    assert '"entry_point",' in window_source
    assert "entry_area_resref=entry_area" in window_source
    assert "entry_position=(" in window_source
    assert "entry_facing=float(entry_facing.value())" in window_source
    assert 'if key == "opening_marker":' in window_source
    assert "floorPlanOpeningMarkerRoomComboBox" in window_source
    assert "Opening marker: create a KOTOR door, trigger, or waypoint" in window_source
    assert '"stage_module",' in window_source
    assert 'if action_key == "stage_module"' in window_source
    assert "execute_map_studio_tool_belt_action(self.controller, action_key, context)" in window_source
    assert "self._log_authored_module_stage_result(result)" in window_source
    assert "export_output_dir=str(getattr(self, \"_last_output_dir\", \"\") or \"\").strip()" in window_source
    assert "export_dry_run=self._map_studio_export_dry_run_enabled()" in window_source
    assert "export_game_modules_dir=str(getattr(self, \"_last_game_modules_dir\", \"\") or \"\").strip()" in window_source
    assert '"install_module",' in window_source
    assert 'if action_key == "install_module"' in window_source
    assert "self._last_game_modules_dir = str(route.command_kwargs.get(\"game_modules_dir\")" in window_source
    assert '"launch_handoff",' in window_source
    assert 'elif action_key == "launch_handoff":' in window_source
    assert "self._open_map_studio_launch_handoff_dialog_from_summary(result)" in window_source
    assert "self.controller.map_studio_launch_handoff()" in window_source
    assert '"record_proof",' in window_source
    assert 'elif action_key == "record_proof":' in window_source
    assert "self._record_game_smoke_proof_from_summary(result)" in window_source
    assert "self.controller.map_studio_game_proof_recording_handoff()" in window_source
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
    assert '"sculpt_erase": "erase"' in window_source
    assert '"sculpt_plateau": "plateau"' in window_source
    assert '"sculpt_ramp": "ramp"' in window_source
    assert '"sculpt_terrace": "terrace"' in window_source
    assert '"sculpt_pinch": "pinch"' in window_source
    assert '"sculpt_erode": "erode"' in window_source
    assert '"sculpt_noise": "noise"' in window_source
    assert "self.controller.map_studio_viewport_performance_policy()" in window_source
    assert "self._select_map_studio_terrain_brush(terrain_brush)" in window_source
    assert "Terrain brush: {label}. Live strokes update dirty terrain samples only" in window_source
    assert "Brush frames stay dirty-region scoped for low-latency sculpting." in window_source
    assert "def _select_map_studio_snap_mode" in window_source
    assert "def _focus_map_studio_vertex_workflow" in window_source
    assert '"vertex_snap": "snap_vertices"' in window_source
    assert '"vertex_snap": "vertex"' in window_source
    assert "Vertex snap: move one floor-plan point to another point" in window_source
    assert "not merge topology" in window_source
    assert "mapStudioToolBeltWidget" in window_source
    assert "mapStudioCustomizeToolBeltButton" in window_source
    assert "mapStudioToolBeltCustomizeSearchLineEdit" in window_source
    assert "mapStudioToolBeltCustomizeSummaryLabel" in window_source
    assert "mapStudioToolBeltCustomizeListWidget" in window_source
    assert "def _filter_actions" in window_source
    assert "def _update_selection_summary" in window_source
    assert "workspace_key" in window_source
    assert "usable" in window_source
    assert "planned" in window_source
    assert "def _connect_map_studio_tool_context_refresh_signals" in window_source
    assert "def _refresh_map_studio_tool_context" in window_source
    assert '"roomPrimitiveTransformComboBox",' in window_source
    assert '"primitiveSurfaceComboBox",' in window_source
    assert '"roomSurfaceComboBox",' in window_source
    assert "combo.currentIndexChanged.connect(lambda _index=0: self._refresh_map_studio_tool_context())" in window_source
    assert "def _refresh_map_studio_tool_belt" in window_source
    assert "self._update_map_studio_command_search_readiness()" in window_source
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
    assert '"arch": "arch"' in window_source
    assert '"sculpt_slope": "slope"' in window_source
    assert '"create_room",' in window_source
    assert '"corridor",' in window_source
    assert '"terrain_patch",' in window_source
    assert "resolve_map_studio_tool_belt_action(key, route_context)" in window_source
    assert "execute_map_studio_tool_belt_action(self.controller, action_key, context)" in window_source
    assert "module_root=str(getattr(module_root_line, \"text\", lambda: \"\")()).strip()" in window_source
    assert "def create_map_studio_corridor" in window_source
    assert "def create_map_studio_starter_terrain" in window_source
    assert '"fill"' in window_source
    assert '"triangulate"' in window_source
    assert '"normals"' in window_source
    assert "self._select_map_studio_modeling_tool(tool_key)" in window_source
    assert "self.add_authored_room_primitive(primitive_kind, \"\")" in window_source
    assert "floorPlanBridgeRequested.connect(self.bridge_authored_floor_plan_edges)" in window_source
    assert "floorPlanOpeningRequested.connect(self.set_authored_floor_plan_wall_opening)" in window_source
    assert "roomOutlineEdgeSelected.connect(self._select_authored_room_outline_edge)" in window_source
    assert "def _select_authored_room_outline_edge" in window_source
    assert 'getattr(self.builder_tab, "select_floor_plan_edge", None)' in window_source
    assert "Use Bridge, Wall Opening, or Edge Extrude for KOTOR room seams." in window_source
    assert "floorPlanOpeningMarkerRequested.connect(self.create_authored_opening_transition_marker)" in window_source
    assert "floorPlanVertexSnapPreviewRequested.connect(self.preview_authored_floor_plan_vertex_snap_candidates)" in window_source
    assert "def preview_authored_floor_plan_vertex_snap_candidates" in window_source
    assert "self.controller.authored_floor_plan_vertex_snap_candidates" in window_source
    assert "floorPlanVertexCleanupRequested.connect(self.cleanup_authored_floor_plan_vertices)" in window_source
    assert "floorPlanVertexMirrorRequested.connect(self.mirror_authored_floor_plan_vertices)" in window_source
    assert "floorPlanFaceFillRequested.connect(self.fill_authored_floor_plan_face)" in window_source
    assert "floorPlanFaceSplitRequested.connect(self.split_authored_floor_plan_face)" in window_source
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
    assert "def split_authored_floor_plan_face" in window_source
    assert "def triangulate_authored_floor_plan_face" in window_source
    assert "def cleanup_authored_floor_plan_normals" in window_source
    assert '"bridge"' in window_source
    assert '"cut"' in window_source
    assert '"opening"' in window_source
    assert '"mirror"' in window_source
    assert '"combine"' in window_source
    assert '"separate"' in window_source
    assert "floorPlanUnionFirstRoomComboBox" in window_source
    assert "Map Studio Combine focused. Current implementation unions compatible" in window_source
    assert "rectangular floor-plan rooms; arbitrary mesh-object combine remains a later" in window_source
    assert "roomPrimitiveSeparateRequested.connect(self.separate_authored_room_primitive)" in window_source
    assert "roomPrimitiveSeparateResultLineEdit" in window_source
    assert "Map Studio Separate focused. Choose a primitive" in window_source
    assert "distinct export boundary" in window_source
    assert "def separate_authored_room_primitive" in window_source
    assert '"cleanup"' in window_source
    assert "edge_index: int" in window_source
    assert "self.controller.map_studio_tool_belt_actions_for_preset" in window_source
    assert "self.map_studio_tool_belt_preset_combo.currentIndexChanged.connect" in window_source
    assert "self.map_studio_customize_tool_belt_button.clicked.connect" in window_source
    assert "mapStudioCommandSearchComboBox" in window_source
    assert "mapStudioCommandSearchRunButton" in window_source
    assert "mapStudioCommandSearchReadinessLabel" in window_source
    assert "mapStudioCommandSearchAction" in window_source
    assert 'QtGui.QKeySequence("Ctrl+K")' in window_source
    assert "self.controller.map_studio_tool_command_search" in window_source
    assert "def _run_selected_map_studio_command_search" in window_source
    assert "def _map_studio_command_search_tooltip" in window_source
    assert "def _map_studio_tool_route_tooltip" in window_source
    assert "def _map_studio_command_search_summary" in window_source
    assert "def _map_studio_command_search_route" in window_source
    assert "def _map_studio_command_search_context_tooltip" in window_source
    assert "resolve_map_studio_tool_belt_action(key, self._map_studio_tool_action_context(key))" in window_source
    assert "Not ready now: {reason}" in window_source
    assert "def _selected_map_studio_command_search_result" in window_source
    assert "def _update_map_studio_command_search_readiness" in window_source
    assert "capability_stage" in window_source
    assert "resource_impacts" in window_source
    assert "readiness_summary" in window_source
    assert "self._map_studio_tool_route_tooltip(action, route)" in window_source
    assert "affected KOTOR resources" in window_source
    assert "export/game-proof impact" in window_source
    assert "self._handle_map_studio_tool_belt_action(action)" in window_source
    assert "mapStudioToolContextMenu" in window_source
    assert "mapStudioToolContextMenuCommandSearchAction" in window_source
    assert "mapStudioToolContextMenuCustomizeAction" in window_source
    assert "mapStudioToolContextMenuCurrentBeltMenu" in window_source
    assert "mapStudioToolContextMenuSearchResultsMenu" in window_source
    assert "def _open_map_studio_tool_context_menu" in window_source
    assert "mapStudioModeMarkingMenu" in window_source
    assert "mapStudioModeMarkingButton_edit" in window_source
    assert "mapStudioModeMarkingButton_object" in window_source
    assert "mapStudioModeMarkingButton_terrain" in window_source
    assert "mapStudioModeMarkingButton_placement" in window_source
    assert "mapStudioToolMarkingMenu" in window_source
    assert "mapStudioToolMarkingQuickButton_extrude" in window_source
    assert "mapStudioToolMarkingQuickButton_bridge" in window_source
    assert "mapStudioToolMarkingQuickButton_cut" in window_source
    assert "mapStudioToolMarkingQuickButton_weld" in window_source
    assert "mapStudioToolMarkingQuickButton_fill_hole" in window_source
    assert "mapStudioToolMarkingQuickButton_bevel" in window_source
    assert "mapStudioToolMarkingTerrainBrushesMenu" in window_source
    assert "mapStudioToolMarkingUvMappingMenu" in window_source
    assert "mapStudioToolMarkingPlannedMenu" not in window_source
    assert "def _build_map_studio_mode_marking_menu" in window_source
    assert "def _build_map_studio_tool_marking_menu" in window_source
    assert "def _run_map_studio_mode_marking_action" in window_source
    assert "def _add_map_studio_context_menu_action" in window_source
    assert "self.map_studio_tool_belt_widget.customContextMenuRequested.connect" in window_source
    assert "self.map_studio_custom_tool_belt_widget.customContextMenuRequested.connect" in window_source
    assert "self.viewport_panel.customContextMenuRequested.connect" in window_source
    assert "resolve_map_studio_tool_belt_action(key, self._map_studio_tool_action_context(key))" in window_source
    assert "def _build_map_studio_tool_qaction" in window_source
    assert "QtGui.QAction(label, self)" in window_source
    assert "mapStudioToolBeltQAction_" in window_source
    assert "mapStudioToolContextAction_" in window_source
    assert "qaction.setData(key)" in window_source
    assert "qaction.setStatusTip(tooltip)" in window_source
    assert "button.setDefaultAction(qaction)" in window_source
    assert "menu.addAction(self._build_map_studio_tool_qaction(action, context_menu=True))" in window_source
    assert "qaction.triggered.connect(" in window_source


def test_t2600_map_studio_builder_exposes_script_hook_controls() -> None:
    builder_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    builder_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
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
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    builder_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    controller_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    controller_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    policy_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "map_studio_modeling_tools.py"
    )
    policy_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
        "map_studio_modeling_tools.py"
    )
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    for source in (policy_source, policy_mirror_source):
        assert "class MapStudioComponentMode" in source
        assert "class MapStudioModelingTool" in source
        assert "class MapStudioSnapMode" in source
        assert '"vertex"' in source
        assert '"edge"' in source
        assert '"face"' in source
        assert '"terrain"' in source
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
        assert "Object, Vertex, Edge, Face, Terrain, and Walkmesh" in source
        assert "snap vertices" in source

    for source in (builder_source, builder_mirror_source):
        assert "Modeling Mode + Snap" in source
        assert "Object, Vertex, Edge, Face, Terrain, and Walkmesh" in source
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


def test_t2908_component_modes_include_terrain_as_visible_authoring_mode() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_modeling_tools import available_map_studio_component_modes

    modes = available_map_studio_component_modes()
    assert tuple(mode.label for mode in modes) == ("Object", "Vertex", "Edge", "Face", "Terrain", "Walkmesh")
    assert tuple(mode.key for mode in modes) == ("object", "vertex", "edge", "face", "terrain", "walkmesh")
    terrain = next(mode for mode in modes if mode.key == "terrain")
    assert "heightfield" in terrain.description.lower()
    assert "WOK" in terrain.kotor_guardrail


def test_t2605_map_studio_toolbar_exposes_goal_aligned_edit_modes() -> None:
    toolbar_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/module_editor_toolbar.py"
    )
    toolbar_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/module_editor_toolbar.py"
    )
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    for source in (toolbar_source, toolbar_mirror_source):
        assert "EDIT_MODES" in source
        assert "mapStudioToolbarEditModeComboBox" in source
        assert "mapStudioToolbarViewModeComboBox" in source
        assert '("generate_module_files", "Generate Module Files")' in source
        assert 'button.setObjectName(f"mapStudioToolbarActionButton_{key}")' in source
        for mode in ("Object", "Vertex", "Edge", "Face", "Walkmesh", "Placement", "Terrain", "Export"):
            assert f'"{mode}"' in source
        assert "snap, weld, flatten, mirror, and cleanup" in source
        assert "stage, install, hand off, warp-test, and record game proof" in source
        assert "MAP_STUDIO_TOOL_BELT_ACTIONS" in source
        assert "universal_transform" in source
        assert "grid_snap" in source
        assert "Grid Snap" in source
        assert "transform_snap_level" in source
        assert "Ctrl+T" in source
        assert "Hold J" in source
        assert "mapStudioMainToolbarModelingLabel" in source
        assert "mapStudioMainToolBeltButton_" in source
        assert "self.actionRequested.emit(f\"tool_belt:{name}\")" in source
        assert "self.selection_mode.currentTextChanged.connect(self.selectionModeChanged.emit)" in source

    assert "mapStudioToolBeltTabs" in window_source
    assert "mapStudioToolBeltDefaultTab" in window_source
    assert "mapStudioToolBeltCustomTab" in window_source
    assert "mapStudioCustomToolComboBox" in window_source
    assert "mapStudioCustomToolAddButton" in window_source
    assert "mapStudioCustomToolBeltWidget" in window_source
    assert "mapStudioUniversalTransformShortcut" in window_source
    assert 'QtGui.QKeySequence("Ctrl+T")' in window_source
    assert "def _activate_map_studio_universal_transform_shortcut" in window_source
    assert "def _focus_map_studio_universal_transform" in window_source
    assert "Universal Manipulator: Ctrl+T displays selected component bounds" in window_source
    assert "mapStudioVertexSnapShortcut" in window_source
    assert "mapStudioTransformLevelSnapShortcut" in window_source
    assert 'QtGui.QKeySequence("V")' in window_source
    assert 'QtGui.QKeySequence("J")' in window_source
    assert 'qaction.setProperty("mapStudioShortcutSequence", shortcut_sequence)' in window_source
    assert 'qaction.setProperty("mapStudioShortcutBehavior", shortcut_behavior)' in window_source
    assert "qaction.setShortcut(QtGui.QKeySequence(shortcut_sequence))" in window_source
    assert "QtCore.Qt.WidgetWithChildrenShortcut" in window_source
    assert 'self._activate_map_studio_modifier_shortcut("vertex_snap")' in window_source
    assert 'self._activate_map_studio_modifier_shortcut("transform_snap_level")' in window_source
    assert "def _activate_map_studio_modifier_shortcut" in window_source
    assert "Hold V: vertex snap mode focused" in window_source
    assert "Hold J: transform level snap focused" in window_source
    assert "def _refresh_map_studio_tool_index" in window_source
    assert "def _add_selected_map_studio_custom_tool" in window_source
    assert "str(action or \"\").startswith(\"tool_belt:\")" in window_source
    assert '"generate_module_files": self.build_module_files' in window_source
    assert "self.toolbar.selectionModeChanged.connect(self._handle_map_studio_edit_mode_changed)" in window_source
    assert "def _handle_map_studio_edit_mode_changed" in window_source
    assert "def _sync_map_studio_tool_belt_preset_for_edit_mode" in window_source
    assert 'current_preset == "custom"' in window_source
    assert '"vertex": "component"' in window_source
    assert '"edge": "component"' in window_source
    assert '"face": "component"' in window_source
    assert '"walkmesh": "component"' in window_source
    assert '"placement": "gameplay"' in window_source
    assert '"terrain": "terrain"' in window_source
    assert '"export": "export"' in window_source
    assert "self._sync_map_studio_tool_belt_preset_for_edit_mode(label)" in window_source
    assert "def _focus_map_studio_edit_mode_workspace" in window_source
    assert "def _sync_map_studio_edit_mode_context" in window_source
    assert "self.controller.map_studio_edit_mode_context(label)" in window_source
    assert "self.workflow_panel.set_edit_mode_context" in window_source
    assert 'self._select_map_studio_component_mode("vertex")' in window_source
    assert 'self._select_map_studio_modeling_tool("weld_vertices")' in window_source
    assert 'self._select_map_studio_modeling_tool("bridge")' in window_source
    assert 'self._select_map_studio_modeling_tool("fill_face")' in window_source
    assert 'self._select_map_studio_component_mode("walkmesh")' in window_source
    assert 'self._select_map_studio_modeling_tool("paint_wok")' in window_source
    assert 'primitive_surface_data = self._map_studio_combo_data("primitiveSurfaceComboBox")' in window_source
    assert 'room_surface_data = self._map_studio_combo_data("roomSurfaceComboBox")' in window_source
    assert 'metadata["supports_walkmesh_surface"] = bool(primitive_data.get("supports_walkmesh_surface"))' in window_source
    assert 'metadata["surface_id"] = surface_id' in window_source
    assert 'self._select_map_studio_modeling_tool("terrain_sculpt")' in window_source
    assert "self._focus_map_studio_export_proof_workspace()" in window_source
    assert 'context = f"{label} mode:' in window_source
    assert '"Vertex": "edit room and walkmesh vertices' in window_source
    assert '"Terrain": "sculpt terrain heightfields' in window_source
    assert "self._focus_map_studio_edit_mode_workspace(label)" in window_source
    assert "self.workflow_panel.set_active_authoring_context(context)" in window_source
    assert 'self._log(f"Map Studio edit mode changed: {context}")' in window_source


def test_t2605_map_studio_edit_mode_context_is_headless_policy() -> None:
    model_tools_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "map_studio_modeling_tools.py"
    )
    model_tools_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
        "map_studio_modeling_tools.py"
    )
    controller_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    controller_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
        "module_editor_controller.py"
    )

    for source in (model_tools_source, model_tools_mirror_source):
        assert "class MapStudioEditModeContext" in source
        assert "Universal Manipulator" in source
        assert "Transform Snap Level" in source
        assert '"level", "Transform Level"' in source
        assert "Hold J" in source
        assert "_EDIT_MODE_CONTEXTS" in source
        assert "available_map_studio_edit_mode_contexts" in source
        assert "def map_studio_edit_mode_context" in source
        assert "room mesh vertices and WOK vertices" in source
        assert "ARE/GIT/IFO/LYT/VIS/PTH/WOK/MDL/MDX and staged .mod proof" in source
        assert "live KOTOR warp proof" in source
        for key in (
            "boolean_a_minus_b",
            "boolean_b_minus_a",
            "insert_edge_loop",
            "cut_slice_insert_edges",
            "fill_hole",
            "merge_components",
            "lattice",
            "shrink_wrap",
            "reverse_normals",
            "soften_edges",
            "harden_edges",
            "duplicate_special",
            "curve_tool",
            "bend_tool",
        ):
            assert f'"{key}"' in source

    for source in (controller_source, controller_mirror_source):
        assert "available_map_studio_edit_mode_contexts" in source
        assert "map_studio_edit_mode_context" in source
        assert "def available_map_studio_edit_mode_contexts" in source
        assert "def map_studio_edit_mode_context" in source

def test_t2606_map_studio_duplicate_special_parameters_are_visible_and_routed() -> None:
    builder_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    builder_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    for source in (builder_source, builder_mirror_source):
        assert "Duplicate Special" in source
        assert "mapStudioDuplicateSpecialCountSpinBox" in source
        assert "mapStudioDuplicateSpecialOffsetXSpinBox" in source
        assert "mapStudioDuplicateSpecialOffsetYSpinBox" in source
        assert "mapStudioDuplicateSpecialOffsetZSpinBox" in source
        assert "mapStudioDuplicateSpecialRotationZSpinBox" in source
        assert "mapStudioDuplicateSpecialScaleXSpinBox" in source
        assert "mapStudioDuplicateSpecialScaleYSpinBox" in source
        assert "mapStudioDuplicateSpecialScaleZSpinBox" in source
        assert "Repeat the selected primitive" in source

    assert '"duplicateSpecialCountSpinBox"' in window_source
    assert "duplicate_count=int(duplicate_count.value())" in window_source
    assert "duplicate_translation_offset=(" in window_source
    assert "duplicate_rotation_offset_degrees_z=float(duplicate_rotation_z.value())" in window_source
    assert "duplicate_scale_multiplier=(" in window_source
    assert '"duplicateSpecialScaleZSpinBox"' in window_source


def test_t2606_map_studio_curve_tool_parameters_are_visible_and_routed() -> None:
    builder_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    builder_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    for source in (builder_source, builder_mirror_source):
        assert "Construction Curve Guide" in source
        assert "mapStudioCurveGuideNameLineEdit" in source
        assert "mapStudioCurveGuidePurposeComboBox" in source
        assert "mapStudioCurveGuidePoint1XSpinBox" in source
        assert "mapStudioCurveGuidePoint2YSpinBox" in source
        assert "mapStudioCurveGuidePoint3ZSpinBox" in source
        assert "Points are stored in KMAP world space" in source
        assert '"pth_planning"' in source
        assert '"terrain_ridge"' in source

    assert '"curveGuidePurposeComboBox"' in window_source
    assert '"curveGuideNameLineEdit"' in window_source
    assert "if key == \"curve_tool\":" in window_source
    assert 'metadata["curve_name"]' in window_source
    assert 'metadata["curve_purpose"]' in window_source
    assert 'metadata["coordinate_space"] = "kmap_world"' in window_source
    assert 'metadata["points"] = (' in window_source
    assert '"curveGuidePoint3ZSpinBox"' in window_source


def test_t2603_map_studio_exposes_live_terrain_sculpt_frame_contract() -> None:
    builder_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    builder_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/builder_tab.py"
    )
    controller_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    controller_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    sculpt_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "map_studio_terrain_sculpt_session.py"
    )
    sculpt_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
        "map_studio_terrain_sculpt_session.py"
    )
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )
    viewport_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/module_editor_viewport_panel.py"
    )
    viewport_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/module_editor_viewport_panel.py"
    )
    event_navigation_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/"
        "viewport_core/widgets/event_navigation.py"
    )
    overlay_layers_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/"
        "viewport_core/widgets/overlay_layers.py"
    )
    scene_models_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/"
        "viewport_core/widgets/scene_models.py"
    )
    rendering_pipeline_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/"
        "viewport_core/widgets/rendering_pipeline.py"
    )
    viewport_widget_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/"
        "viewport_core/widgets/viewport_widget.py"
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
        assert "never serialize per frame" in source
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
        assert "roomOutlinePointSnapPreviewRequested = QtCore.Signal(str, int)" in source
        assert "roomOutlinePointSnapped = QtCore.Signal(str, int, int, str)" in source
        assert "roomOutlineEdgeSelected = QtCore.Signal(str, int)" in source
        assert "def _room_outline_edge_at_event" in source
        assert "def _select_room_outline_edge" in source
        assert "self.roomOutlineEdgeSelected.emit(room, edge)" in source
        assert "QtCore.Qt.Key_V" in source
        assert "def active_map_studio_modifier" in source
        assert "def set_map_studio_modifier_active" in source
        assert 'self.set_map_studio_modifier_active("vertex_snap"' in source
        assert 'self.set_map_studio_modifier_active("transform_snap_level"' in source
        assert "set_room_outline_vertex_snap_candidates" in source
        assert "set_map_studio_room_outline_snap_highlight" in source
        assert "clear_map_studio_room_outline_snap_highlight" in source
        assert "_set_room_outline_snap_highlight_for_candidate" in source
        assert "_clear_room_outline_snap_highlight" in source
        assert "pending_snap_candidate" in source
        assert "Release while holding V to commit" in source
        assert "terrainBrushFrameRequested = QtCore.Signal(str, str, object)" in source
        assert "terrainBrushStrokeCommitted = QtCore.Signal(str, str)" in source
        assert "terrainBrushOptionsChanged = QtCore.Signal(int, float)" in source
        assert "modeMarkingMenuRequested = QtCore.Signal(QtCore.QPoint)" in source
        assert "toolMarkingMenuRequested = QtCore.Signal(QtCore.QPoint)" in source
        assert "roomPrimitiveRotated = QtCore.Signal(str, str, float)" in source
        assert "roomPrimitiveScaled = QtCore.Signal(str, str, object)" in source
        assert "transformGizmoModeChanged = QtCore.Signal(str)" in source
        assert "undoShortcutRequested = QtCore.Signal()" in source
        assert "redoShortcutRequested = QtCore.Signal()" in source
        assert "deleteShortcutRequested = QtCore.Signal()" in source
        assert "mapStudioViewportTranslateGizmoButton" in source
        assert "mapStudioViewportRotateGizmoButton" in source
        assert "mapStudioViewportScaleGizmoButton" in source
        assert "def set_transform_gizmo_mode" in source
        assert "def _handle_map_studio_shortcut_key" in source
        assert "QtCore.Qt.Key_W" in source
        assert "QtCore.Qt.Key_E" in source
        assert "QtCore.Qt.Key_R" in source
        assert "QtCore.Qt.Key_Z" in source
        assert "QtCore.Qt.Key_Delete" in source
        assert "QtCore.Qt.ShiftModifier" in source
        assert "self.toolMarkingMenuRequested.emit" in source
        assert "self.modeMarkingMenuRequested.emit" in source
        assert "_gr_map_studio_viewport_input_handler" in source
        assert "def _handle_map_studio_viewport_input_event" in source
        assert "mapStudioViewportTerrainBrushCheckBox" in source
        assert "def set_terrain_brush_interaction" in source
        assert "def _terrain_sample_at_event" in source
        assert "def _terrain_world_at_screen" in source
        assert "def _begin_terrain_brush_drag" in source
        assert "def _update_terrain_brush_drag" in source
        assert "def _finish_terrain_brush_drag" in source
        assert "def _begin_terrain_brush_option_drag" in source
        assert "def _update_terrain_brush_option_drag" in source
        assert "QtCore.Qt.AltModifier" in source
        assert "_gr_map_studio_clean_viewport" in source
        assert "def _sync_clean_viewport_presentation" in source
        assert '"clean_display": True' in source
        assert '"subtle_room_outlines": True' in source
        assert '"show_room_guides": room_edit_active' in source
        assert '"show_transform_dimensions": primitive_drag_active or self.transform_gizmo_mode() == "scale"' in source
        assert '"show_terrain_brush": terrain_active' in source

    assert "terrainLiveBrushFrameRequested.connect(self.preview_map_studio_terrain_sculpt_frame)" in window_source
    assert "roomOutlinePointSnapPreviewRequested.connect(self.preview_authored_floor_plan_vertex_snap_candidates)" in window_source
    assert "active_map_studio_modifier" in window_source
    assert 'metadata["active_modifier_action"]' in window_source
    assert 'metadata["active_modifier_behavior"] = "hold_modifier"' in window_source
    assert 'metadata["active_modifier_source"] = "map_studio_viewport"' in window_source
    assert 'metadata["active_modifier_coordinate_space"] = "viewport_interaction"' in window_source
    assert "roomOutlinePointSnapped.connect(self.snap_authored_floor_plan_vertex)" in window_source
    assert "terrainBrushFrameRequested.connect(self.apply_map_studio_viewport_terrain_brush_frame)" in window_source
    assert "terrainBrushStrokeCommitted.connect(self.commit_map_studio_viewport_terrain_brush_stroke)" in window_source
    assert "terrainBrushOptionsChanged.connect(self._set_map_studio_terrain_brush_options)" in window_source
    assert "mapStudioUndoAction" in window_source
    assert 'QtGui.QKeySequence("Ctrl+Z")' in window_source
    assert "mapStudioRedoAction" in window_source
    assert 'QtGui.QKeySequence("Ctrl+R")' in window_source
    assert "mapStudioTranslateGizmoShortcut" in window_source
    assert "mapStudioRotateGizmoShortcut" in window_source
    assert "mapStudioScaleGizmoShortcut" in window_source
    assert "mapStudioDeleteSelectionShortcut" in window_source
    assert "roomPrimitiveRotated.connect(self._rotate_authored_room_primitive)" in window_source
    assert "roomPrimitiveScaled.connect(self._scale_authored_room_primitive)" in window_source
    assert "transformGizmoModeChanged.connect(self._handle_map_studio_transform_gizmo_mode_changed)" in window_source
    assert "undoShortcutRequested.connect(self.undo_map_studio_command)" in window_source
    assert "redoShortcutRequested.connect(self.redo_map_studio_command)" in window_source
    assert "deleteShortcutRequested.connect(self.delete_map_studio_current_selection)" in window_source
    assert "def delete_map_studio_current_selection" in window_source
    assert "def _refresh_map_studio_selected_primitive_transform_overlay" in window_source
    assert "def _handle_map_studio_transform_gizmo_mode_changed" in window_source
    assert "modeMarkingMenuRequested.connect(self._open_map_studio_mode_marking_menu)" in window_source
    assert "toolMarkingMenuRequested.connect(self._open_map_studio_tool_marking_menu)" in window_source
    assert "_gr_map_studio_viewport_input_handler" in event_navigation_source
    assert "map_studio_handler(event, obj)" in event_navigation_source
    assert "QtCore.QEvent.KeyPress" in event_navigation_source
    assert "_map_studio_transform_gizmo_mode" in overlay_layers_source
    assert 'mode == "rotate"' in overlay_layers_source
    assert 'mode == "scale"' in overlay_layers_source
    assert "def _map_studio_clean_viewport_enabled" in overlay_layers_source
    assert "def _map_studio_presentation_flag" in overlay_layers_source
    assert '"show_room_guides"' in overlay_layers_source
    assert '"show_room_vertex_handles"' in overlay_layers_source
    assert '"show_transform_dimensions"' in overlay_layers_source
    assert '"show_terrain_walkability"' in overlay_layers_source
    assert '"show_terrain_brush"' in overlay_layers_source
    assert '"show_placement_guides"' in overlay_layers_source
    assert "subtle_primitive_handles" in overlay_layers_source
    assert "_gr_suppress_renderer_diagnostics" in overlay_layers_source
    assert "set_map_studio_viewport_presentation" in scene_models_source
    assert "def _map_studio_should_hide_empty_scene_label" in scene_models_source
    assert 'self.canvas.setText("" if self._map_studio_should_hide_empty_scene_label() else "Empty Scene")' in scene_models_source
    assert "setText(\"\")" in scene_models_source
    assert "_map_studio_viewport_presentation" in viewport_widget_source
    assert "_map_studio_universal_transform_overlay = None" in viewport_widget_source
    assert "_gr_suppress_renderer_diagnostics" in rendering_pipeline_source
    assert "self._renderer._draw_stats(draw, w, h)" in rendering_pipeline_source
    assert "self._draw_renderer_statistics_overlay(draw, w, h)" in rendering_pipeline_source
    assert "def _sync_map_studio_terrain_brush_context" in window_source
    assert "def _set_map_studio_terrain_brush_options" in window_source
    assert "def apply_map_studio_viewport_terrain_brush_frame" in window_source
    live_apply_source = window_source[
        window_source.index("def apply_map_studio_viewport_terrain_brush_frame") :
        window_source.index("def commit_map_studio_viewport_terrain_brush_stroke")
    ]
    assert "apply_map_studio_terrain_sculpt_frame" in live_apply_source
    assert "apply_terrain_height_patch" in live_apply_source
    assert "Release to create one undo step and refresh slope checks" in live_apply_source
    assert "_refresh_all" not in live_apply_source
    commit_source = window_source[
        window_source.index("def commit_map_studio_viewport_terrain_brush_stroke") :
        window_source.index("def merge_authored_floor_plan_rooms")
    ]
    assert "_refresh_map_studio_geometry_change(" in commit_source
    assert "rebuild_viewport_model=False" in commit_source
    assert "refresh_scene_tree=False" in commit_source
    assert "validation_delay_ms=250" in commit_source
    assert "set_terrain_walkability_overlay(None)" not in commit_source
    assert "Keep the existing overlay as the XY hit-test proxy" in commit_source
    assert "self.controller.authored_terrain_walkability_overlay()" not in commit_source
    assert "_refresh_all" not in commit_source
    assert "def preview_map_studio_terrain_sculpt_frame" in window_source
    assert "full MDL/WOK rebuild deferred" in window_source


def test_t2600_map_studio_export_panel_explains_safe_stage_install_and_game_proof() -> None:
    export_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/export_panel.py"
    )
    export_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/export_panel.py"
    )

    for source in (export_source, export_mirror_source):
        assert "mapStudioExportScopeLabel" in source
        assert "mapStudioExportSafetyLabel" in source
        assert "mapStudioExportDryRunCheckBox" in source
        assert "mapStudioExportDryRunHintLabel" in source
        assert "mapStudioExportReadinessGateLabel" in source
        assert "mapStudioExportBlockerTable" in source
        assert "mapStudioExportFixActionLabel" in source
        assert "mapStudioExportFixBuilderButton" in source
        assert "mapStudioExportFixWalkmeshButton" in source
        assert "mapStudioExportFixPlacementButton" in source
        assert "mapStudioExportFixSelectTargetButton" in source
        assert "mapStudioExportFixValidateButton" in source
        assert "builderFixRequested = QtCore.Signal()" in source
        assert "walkmeshFixRequested = QtCore.Signal()" in source
        assert "placementFixRequested = QtCore.Signal()" in source
        assert "selectFixTargetRequested = QtCore.Signal(str)" in source
        assert "validateRequested = QtCore.Signal()" in source
        assert "self.export_blocker_table.itemDoubleClicked.connect(self._emit_blocker_target)" in source
        assert 'setHorizontalHeaderLabels(("Blocker", "KOTOR export impact", "Next fix"))' in source
        assert "def set_readiness" in source
        assert "can_export_candidate" in source
        assert 'pathing.get("blocking_messages"' in source
        assert 'pathing.get("blocking_targets"' in source
        assert "walkmesh/pathing needs attention" in source
        assert "Blocks authored .mod package, stage, and install actions." in source
        assert "def _set_fix_action_state" in source
        assert "def _emit_fix_target" in source
        assert "def _emit_blocker_target" in source
        assert "def _first_fix_target_id" in source
        assert "def _fix_hint_for_target" in source
        assert "def _target_id_for_blocker" in source
        assert "item.setData(QtCore.Qt.UserRole, target_id)" in source
        assert "Fix action: No blocker action needed" in source
        assert "mapStudioExportActionGuideLabel" in source
        assert "mapStudioExportActionGuideTable" in source
        assert 'setHorizontalHeaderLabels(("Action", "Writes", "Use when", "Game proof"))' in source
        assert "current KMAP as a complete KOTOR .mod package" in source
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


def test_t2600_map_studio_export_uses_progressive_disclosure_without_horizontal_overflow() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()

    from PySide6 import QtCore, QtWidgets
    from src.gui.panels.module_editor.export_panel import ModuleExportPanel
    from src.gui.panels.module_editor.workflow_panel import MapStudioWorkflowPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    workflow = MapStudioWorkflowPanel()
    export = ModuleExportPanel()
    try:
        workflow.show()
        export.show()
        app.processEvents()

        assert workflow.advanced_details_toggle.isChecked() is False
        assert workflow.smoke_test_recipe_table.isHidden()
        assert workflow.resources_label.isHidden()
        assert workflow.secondary_actions_widget.isHidden()
        assert workflow.next_action_label.isHidden() is False
        assert (
            workflow.smoke_test_recipe_table.horizontalScrollBarPolicy()
            == QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        workflow.advanced_details_toggle.setChecked(True)
        app.processEvents()
        assert workflow.smoke_test_recipe_table.isVisible()
        assert workflow.resources_label.isVisible()
        assert workflow.secondary_actions_widget.isVisible()

        assert export.details_toggle.isChecked() is False
        assert export.export_blocker_table.isHidden()
        assert export.blocker_summary_label.isHidden()
        assert export.action_guide_toggle.isHidden()
        assert export.action_guide_table.isHidden()
        assert export.export_button.isHidden()
        assert export.dev_test_button.isHidden()
        assert export.authored_stage_button.isHidden()
        assert export.dry_run.isChecked() is False
        assert export.authored_module_button.text() == "Export .mod Package..."
        assert export.authored_install_button.text() == "Install .mod for Game Test..."
        assert (
            export.export_blocker_table.horizontalScrollBarPolicy()
            == QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        assert (
            export.action_guide_table.horizontalScrollBarPolicy()
            == QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        export.details_toggle.setChecked(True)
        app.processEvents()
        assert export.export_blocker_table.isHidden()
        assert export.blocker_summary_label.isVisible()
        assert export.action_guide_toggle.isVisible()
        assert export.action_guide_table.isHidden()
        export.action_guide_toggle.setChecked(True)
        app.processEvents()
        assert export.action_guide_label.isVisible()
        assert export.action_guide_table.isHidden()
    finally:
        workflow.close()
        export.close()


def test_t2907_build_workspace_has_three_task_sections_and_direct_terrain_sculpting() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.gui.panels.module_editor.builder_tab import BuilderTab
    from src.gui.panels.module_editor.environment_tab import MapStudioEnvironmentTab

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    environment = MapStudioEnvironmentTab()
    builder = BuilderTab()
    try:
        labels = tuple(builder.buildSectionTabs.tabText(index) for index in range(builder.buildSectionTabs.count()))
        assert labels == ("Room Building", "Terrain Building", "Skybox")
        assert builder.roomAdvancedToggle.isChecked() is False
        assert builder._roomAdvancedContainer.isHidden()
        assert builder.terrainAdvancedToggle.isChecked() is False
        assert builder.terrainAdvancedWidget.isHidden()
        assert builder.terrainRadiusSpinBox.value() == 3
        assert builder.terrainSculptEnabledCheckBox.isChecked() is True

        create_requests: list[bool] = []
        builder.terrainCreateRequested.connect(lambda: create_requests.append(True))
        builder.createTerrainSurfaceButton.click()
        assert create_requests == [True]

        builder.adopt_skybox_tools(environment.sky_group, environment.sky_traffic_group)
        environment.adopt_room_lighting_tools(builder.roomLightingGroup)
        assert environment.sky_group.parentWidget() is builder.skyboxBuildingPage
        assert environment.sky_traffic_group.parentWidget() is builder.skyboxBuildingPage
        assert builder.roomLightingGroup.parentWidget() is environment
        assert environment.world_group.title() == "Lighting, Weather and Fog (ARE)"
    finally:
        builder.close()
        environment.close()
        app.processEvents()

    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"
    )
    assert "mapStudioExportDiagnosticsButton" in window_source
    assert "self.readiness_panel.setVisible(False)" in window_source
    assert "self.workflow_panel.setVisible(False)" in window_source
    assert "self.right_tabs_scroll.setHorizontalScrollBarPolicy" in window_source


def test_t3104_package_wizard_reviews_template_and_script_dependencies() -> None:
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    assert "mapStudioPackageWizardResourceReviewTable" in window_source
    assert 'setHorizontalHeaderLabels(("Resource or reference", "Status", "Why it matters"))' in window_source
    assert "mapStudioPackageWizardProofGateTable" in window_source
    assert 'setHorizontalHeaderLabels(("Live KOTOR proof check", "Package gate status"))' in window_source
    assert "def _populate_proof_gate_table" in window_source
    assert 'test_plan.get("acceptance_checks")' in window_source
    assert 'test_plan.get("missing_acceptance_checks")' in window_source
    assert "Required after staging; cannot be satisfied by package build alone" in window_source
    assert "Transitions and PTH pathing behave sanely" in window_source
    assert "No inherited vanilla geometry or scripted movers appear" in window_source
    assert "def _reference_rows_from_metadata" in window_source
    assert 'metadata.get("gameplay_template_references")' in window_source
    assert 'metadata.get("script_references")' in window_source
    assert 'metadata.get("dialog_references")' in window_source
    assert 'label = f"{kind}:{resref}.{restype}"' in window_source
    assert 'label = f"script:{script}.ncs"' in window_source
    assert 'label = f"dialog:{dialog}.dlg"' in window_source
    assert "external_or_base_game" in window_source
    assert "external_or_override" in window_source
    assert "Gameplay template dependency that must resolve during the in-game smoke test." in window_source
    assert "ARE/IFO script hook dependency that must resolve during the in-game smoke test." in window_source
    assert "Dialog/conversation dependency that must resolve during the in-game smoke test." in window_source


def test_t2600_map_studio_asset_browser_explains_library_import_scope() -> None:
    asset_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/module_editor_asset_browser.py"
    )
    asset_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
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
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/readiness_panel.py"
    )
    readiness_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/readiness_panel.py"
    )

    for source in (readiness_source, readiness_mirror_source):
        assert "mapStudioReadinessPathingLabel" in source
        assert "mapStudioReadinessPathingExportGateLabel" in source
        assert "mapStudioReadinessVisibilityLabel" in source
        assert "mapStudioReadinessLightingLabel" in source
        assert "mapStudioReadinessPathingBlockerTable" in source
        assert 'setHorizontalHeaderLabels(("PTH / WOK issue", "Export impact", "Fix"))' in source
        assert "def _set_pathing_summary" in source
        assert "def _set_visibility_summary" in source
        assert "def _set_lighting_summary" in source
        assert "def _set_pathing_blocker_rows" in source
        assert "PTH path graph readiness" in source
        assert "VIS room-link readiness" in source
        assert "viewport-light, lightmap, and game-proof lighting status" in source
        assert "metadata.get(\"visibility\"" in source
        assert "metadata.get(\"lighting\"" in source
        assert "VIS visibility:" in source
        assert "Lighting/lightmaps:" in source
        assert "Blocks export:" in source
        assert "lightmap {lightmap_status}" in source
        assert "proof: {proof}" in source
        assert "Pathing export gate: Blocked until the module entry point" in source
        assert "transition_surface_gate" in source
        assert "Blocked until linked doors/triggers have WOK DOOR surface 18 evidence" in source
        assert "Blocks export candidate and .mod game-test packaging" in source
        assert "anchors: {anchor_text}" in source
        assert "mapStudioReadinessFloorPlanGeometryLabel" in source
        assert "def _set_floor_plan_geometry_summary" in source
        assert "Floor-plan geometry:" in source
        assert "geometry_validation" in source
        assert "mapStudioReadinessComponentEditLabel" in source
        assert "mapStudioReadinessComponentEditResourceTable" in source
        assert "def _set_component_edit_summary" in source
        assert "def _set_component_edit_resource_rows" in source
        assert "Component edits:" in source
        assert "mapStudioReadinessExportProofInvalidationLabel" in source
        assert "def _set_export_proof_invalidation_summary" in source
        assert "metadata.get(\"export_proof_invalidation\"" in source
        assert "Export/proof freshness:" in source
        assert "invalidates_previous_export" in source
        assert "invalidates_game_proof" in source
        assert "game proof stale" in source
        assert "Fix before export" in source
        assert "Stale outputs:" in source
        assert "Next:" in source
        assert "mapStudioReadinessRuntimeResourceTable" in source
        assert 'setHorizontalHeaderLabels(("Resource", "Status", "Fix / meaning"))' in source
        assert "mapStudioReadinessPackageInventoryLabel" in source
        assert "def _package_inventory_summary" in source
        assert "package_resource_inventory" in source
        assert "Package inventory:" in source
        assert "archive readback resource(s)" in source
        assert "build/stage the authored .mod before recording game proof" in source
        assert "def _set_runtime_resource_rows" in source
        assert "runtime_output_status" in source
        assert "def _normalise_stale_output" in source
        assert "stale_outputs" in source
        assert 'resource_status = "Stale"' in source
        assert "Regenerate this resource before packaging/installing the module." in source
        assert "expected_runtime_resources" in source
        assert "present_runtime_resources" in source
        assert "missing_runtime_resources" in source
        assert "Generate or stage this runtime file before export/install." in source
        assert "ARE/GIT/IFO/LYT/VIS/PTH/WOK/MDL/MDX readiness" in source
        assert "mapStudioReadinessAuthoredSourceLabel" in source
        assert "source_identity" in source
        assert "expected_absent_runtime_observations" in source
        assert "Original Map Studio KMAP" in source
        assert "not PLCaa/Taris/fallback base-game content" in source
        assert "no scripted moving base-game test objects are present" in source
        assert "modder_test_plan" in source
        assert "acceptance check(s) still need live KOTOR evidence" in source
        assert "mapStudioReadinessProofAcceptanceTable" in source
        assert 'setHorizontalHeaderLabels(("Live KOTOR proof check", "Evidence status"))' in source
        assert "def _set_proof_acceptance_rows" in source
        assert "def _proof_check_label" in source
        assert "def _proof_check_status" in source
        assert 'test_plan.get("acceptance_checks")' in source
        assert 'test_plan.get("missing_acceptance_checks")' in source
        assert "Required after staging; cannot be satisfied by package build alone" in source
        assert "Accepted in recorded proof" in source
        assert "Transitions and PTH pathing behave sanely" in source
        assert "No inherited vanilla geometry or scripted movers appear" in source
        assert "Screenshot or video evidence is attached" in source


def test_t2600_map_studio_readiness_panel_lists_gameplay_template_references() -> None:
    readiness_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/readiness_panel.py"
    )
    readiness_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
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
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/readiness_panel.py"
    )
    readiness_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/readiness_panel.py"
    )

    for source in (readiness_source, readiness_mirror_source):
        assert "mapStudioReadinessTransitionReferencesLabel" in source
        assert "mapStudioReadinessTransitionReferenceTable" in source
        assert "mapStudioReadinessScriptReferencesLabel" in source
        assert "mapStudioReadinessScriptReferenceTable" in source
        assert "mapStudioReadinessDialogReferencesLabel" in source
        assert "mapStudioReadinessDialogReferenceTable" in source
        assert 'setHorizontalHeaderLabels(("Kind", "Tag", "Destination", "Status / fix"))' in source
        assert 'setHorizontalHeaderLabels(("Scope", "Field", "Script", "Status / fix"))' in source
        assert 'setHorizontalHeaderLabels(("Source", "Field", "Dialog", "Status / fix"))' in source
        assert "transition_references" in source
        assert "script_references" in source
        assert "dialog_references" in source
        assert "transition_incomplete_count" in source
        assert "script_external_count" in source
        assert "dialog_external_count" in source
        assert "def _set_transition_reference_rows" in source
        assert "def _set_script_reference_rows" in source
        assert "def _set_dialog_reference_rows" in source
        assert "Add a door, trigger, or waypoint transition when this module needs area links." in source
        assert "Assign ARE/IFO script hooks only when this module needs custom runtime behavior." in source
        assert "Add dialog/conversation refs only when this module needs conversations." in source


def test_t2600_map_studio_walkmesh_tab_explains_wok_workflow() -> None:
    walkmesh_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/walkmesh_tab.py"
    )
    walkmesh_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/walkmesh_tab.py"
    )
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )
    controller_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    mirror_controller_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
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
        assert "mapStudioWalkmeshGenerateSelectedFloorButton" in source
        assert "mapStudioWalkmeshAssignFaceTypeButton" in source
        assert "mapStudioWalkmeshValidateButton" in source
        assert "mapStudioWalkmeshShowWalkableButton" in source
        assert "select only the real floor faces" in source
    assert "authored_walkmesh_status = self.controller.authored_walkmesh_status()" in window_source
    assert "authored_walkmesh_room_surfaces = self.controller.authored_walkmesh_room_surface_choices()" in window_source
    assert "self.walkmesh_tab.set_walkmesh_status(authored_walkmesh_status)" in window_source
    assert "self.walkmesh_tab.set_room_surface_choices(authored_walkmesh_room_surfaces)" in window_source
    assert "self.walkmesh_tab.set_walkmesh_surfaces(self.controller.available_authored_walkmesh_surfaces())" in window_source
    assert "self.walkmesh_tab.roomSurfaceRequested.connect(self.apply_authored_walkmesh_surface)" in window_source
    assert "self.controller.set_authored_room_walkmesh_surface" in window_source
    assert 'if action == "Generate from Selected Floor Faces"' in window_source
    assert "map_studio_component_selection" in window_source
    assert "imported_mesh_surface_index_for_role" in window_source
    assert "prepare_imported_room_walkmesh_generation_intent" in window_source
    assert "already has an authoritative source WOK. It was not replaced" in window_source
    assert "auto_generate_map_studio_walkmesh" in window_source
    assert "Walkmesh Boundary Rules" in window_source
    assert "Do not bake vertical wall or ceiling triangles into the WOK" in window_source
    for source in (controller_source, mirror_controller_source):
        assert "AuthoredWalkmeshStatus" in source
        assert "authored_walkmesh_status_for_project" in source
        assert "def authored_walkmesh_status(self)" in source
        assert "authored_walkmesh_room_surface_choices" in source
        assert "def set_authored_room_walkmesh_surface" in source


def test_t2600_map_studio_rooms_tab_explains_room_graph_workflow() -> None:
    rooms_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/rooms_tab.py"
    )
    rooms_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/rooms_tab.py"
    )

    for source in (rooms_source, rooms_mirror_source):
        # 2026-07-07 UI cleanup: workflow guidance moved from three body
        # paragraphs into the tab tooltip so the dock shows controls, not prose.
        assert "mapStudioRoomsWorkflowLabel" in source
        assert "mapStudioRoomsLayoutHintLabel" in source
        assert "mapStudioRoomsAuthoringHintLabel" in source
        assert "load or author room layout, arrange room positions" in source
        assert "validate LYT/VIS links before packaging" in source
        assert "LYT stores room models and transforms" in source
        assert "VIS controls which rooms can see each other" in source
        assert "Keep room resrefs stable" in source
        assert "Use Builder for new geometry" in source
        assert "mapStudioRoomsLoadLytButton" in source
        assert "mapStudioRoomsAddRoomButton" in source
        assert "mapStudioRoomsRemoveRoomButton" in source
        assert "mapStudioRoomsDuplicateRoomButton" in source
        assert "mapStudioRoomsConnectOpeningsButton" in source
        assert "mapStudioRoomsAuditConnectionsButton" in source
        assert "def set_connection_audit" in source
        assert "WOK transition edges and in-game traversal" in source
        assert "mapStudioRoomsSaveLayoutButton" in source
        assert "mapStudioRoomsFocusSelectedButton" in source
        assert "mapStudioRoomsAutoArrangeButton" in source
        assert "mapStudioRoomsSnapToGridButton" in source


def test_t2600_map_studio_blueprints_tab_explains_template_workflow() -> None:
    blueprints_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/blueprints_tab.py"
    )
    blueprints_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
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
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/validation_panel.py"
    )
    validation_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
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
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/module_editor_outliner.py"
    )
    outliner_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/module_editor_outliner.py"
    )
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    for source in (outliner_source, outliner_mirror_source):
        assert "Map Studio project outliner" in source
        assert "Maya-style scene objects plus modules, rooms, walkmeshes, authored placements, lights, blueprints, and resources" in source
        assert "Outliner workflow: select scene objects" in source
        assert "double-click to rename" in source
        assert 'self.setHeaderLabels(["Scene Object", "Type"])' in source
        assert "Scene Objects" in source
        assert "Authored Rooms" in source
        assert 'f"viewport_camera:{camera_name}"' in source
        assert "authored_room_primitives" in source
        assert "authored_primitive_item_id" in source
        assert "itemRenamed = QtCore.Signal(str, str)" in source
        assert "mapStudioOutlinerContextMenu" in source
        assert "mapStudioOutlinerRenameAction" in source
        assert '("Rename", "rename", "mapStudioOutlinerRenameAction")' in source
        assert "mapStudioOutlinerDuplicateAction" in source
        assert "mapStudioOutlinerDeleteAction" in source
        assert "mapStudioOutlinerFocusViewportAction" in source
        assert "mapStudioOutlinerValidateSelectedAction" in source
        assert "Right-click for Rename, Duplicate, Delete, Focus, and Validate actions" in source
    assert "self.outliner.itemRenamed.connect(self._rename_outliner_item_inline)" in window_source
    assert "self.outliner.set_project(self.project, authored_placements, authored_room_lights, authored_room_primitives)" in window_source
    assert "def _parse_map_studio_primitive_outliner_id" in window_source
    assert "def rename_map_studio_authored_primitive" in window_source


def test_t2600_map_studio_outliner_add_camera_and_light_are_wired_to_services() -> None:
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
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


def test_coordinate_placeable_placement_resolves_preview_resources_immediately() -> None:
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    start = window_source.index("    def add_authored_gameplay_placement(")
    end = window_source.index("    def _set_map_studio_placement_mode(", start)
    method_source = window_source[start:end]
    assert 'if kind in {"placeable", "door"}:' in method_source
    assert "self._sync_placeable_library_resources_for_export()" in method_source
    assert "real model/effects appear" in method_source


def test_t2600_map_studio_properties_exposes_transition_controls() -> None:
    properties_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/module_editor_properties.py"
    )
    properties_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/module_editor_properties.py"
    )
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    for source in (properties_source, properties_mirror_source):
        assert "transitionChanged = QtCore.Signal(str, str, str, int, int)" in source
        assert "mapStudioTransitionPropertiesGroup" in source
        assert "mapStudioTransitionLinkedToLineEdit" in source
        assert "mapStudioTransitionLinkedModuleLineEdit" in source
        assert "mapStudioTransitionTargetTypeComboBox" in source
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
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/module_editor_properties.py"
    )
    properties_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/module_editor_properties.py"
    )
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    for source in (properties_source, properties_mirror_source):
        assert "roomLightChanged = QtCore.Signal(str, object)" in source
        assert "mapStudioRoomLightPropertiesGroup" in source
        assert "mapStudioRoomLightTypeComboBox" in source
        assert "mapStudioRoomLightColorRSpinBox" in source
        assert "mapStudioRoomLightColorGSpinBox" in source
        assert "mapStudioRoomLightColorBSpinBox" in source
        assert "mapStudioRoomLightRadiusSpinBox" in source
        assert "mapStudioRoomLightIntensitySpinBox" in source
        assert "mapStudioRoomLightEnabledCheckBox" in source
        assert "mapStudioRoomLightCastsShadowsCheckBox" in source
        assert "mapStudioRoomLightAffectsDiffuseCheckBox" in source
        assert "mapStudioRoomLightAffectsLightmapCheckBox" in source
        assert "mapStudioRoomLightDirection{axis}SpinBox" in source
        assert "mapStudioRoomLightConeAngleSpinBox" in source
        assert "mapStudioRoomLightBakeGroupLineEdit" in source
        assert "self.room_light_group.setVisible(True)" in source
        assert "def _room_light_changed" in source

    assert "self.properties.roomLightChanged.connect(self._set_authored_room_light_properties)" in window_source
    assert "def _set_authored_room_light_properties" in window_source
    assert "self.controller.set_authored_room_light_properties" in window_source
    assert "Updated authored room light properties." in window_source


def test_t2600_map_studio_properties_exposes_selected_camera_controls() -> None:
    properties_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/module_editor_properties.py"
    )
    properties_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/module_editor_properties.py"
    )
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )
    controller_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    placement_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
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
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/module_editor_viewport_panel.py"
    )
    viewport_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/module_editor_viewport_panel.py"
    )
    preview_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "authored_gameplay_preview.py"
    )
    preview_mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
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
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/workflow_panel.py"
    )
    mirror_init = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
        "module_editor/__init__.py"
    )

    assert "class MapStudioWorkflowPanel" in mirror_source
    assert "mapStudioWorkflowResourcesLabel" in mirror_source
    assert "mapStudioWorkflowTargetGameLabel" in mirror_source
    assert "mapStudioWorkflowCapabilityLabel" in mirror_source
    assert "mapStudioWorkflowTestStateLabel" in mirror_source
    assert "mapStudioWorkflowActiveContextLabel" in mirror_source
    assert "mapStudioWorkflowModeLabel" in mirror_source
    assert "mapStudioWorkflowEditingTargetLabel" in mirror_source
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
    assert "mapStudioWorkflowVisibilityLabel" in mirror_source
    assert "mapStudioWorkflowLightingLabel" in mirror_source
    assert "mapStudioWorkflowTerrainToolsButton" in mirror_source
    assert "mapStudioWorkflowLightingToolsButton" in mirror_source
    assert "mapStudioWorkflowPlacementLabel" in mirror_source
    assert "mapStudioWorkflowScriptToolsButton" in mirror_source
    assert "def set_active_authoring_context" in mirror_source
    assert "mapStudioWorkflowLayoutLabel" in mirror_source
    assert "mapStudioWorkflowTransitionsLabel" in mirror_source
    assert "mapStudioWorkflowScriptsLabel" in mirror_source
    assert "mapStudioWorkflowExportJobLabel" in mirror_source
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
    assert "def _export_job_text" in mirror_source
    assert "preflight ready" in mirror_source
    assert "package written" in mirror_source
    assert "readback OK" in mirror_source
    assert "can_export_candidate" in mirror_source
    assert "PTH/WOK pathing blocked" in mirror_source
    assert "self.stage_button.setEnabled(bool(enabled and can_export))" in mirror_source
    assert "self.install_button.setEnabled(bool(enabled and can_export))" in mirror_source
    assert "Target game:" in mirror_source
    assert "Test state:" in mirror_source
    assert "def _test_state_text" in mirror_source
    assert "Required resources missing" in mirror_source
    assert "Geometry authoring" in mirror_source
    assert "Walkmesh" in mirror_source
    assert "VIS visibility:" in mirror_source
    assert '"VIS visibility"' in mirror_source
    assert "Lighting/lightmaps:" in mirror_source
    assert '"Lighting"' in mirror_source
    assert "Resource placement:" in mirror_source
    assert '"Resource placement"' in mirror_source
    assert "creatures, placeables, doors, triggers, encounters, cameras, sounds, merchants, and waypoints" in mirror_source
    assert "Gameplay layout" in mirror_source
    assert "Transitions:" in mirror_source
    assert "Scripts:" in mirror_source
    assert "def set_edit_mode_context" in mirror_source
    assert "def set_selection_context" in mirror_source
    assert "MapStudioWorkflowPanel" in mirror_init


def test_t2600_map_studio_workflow_panel_guides_first_playable_smoke_test() -> None:
    panel_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/workflow_panel.py"
    )
    mirror_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/"
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
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "authored_module_validation_projection.py"
    )
    mirror = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
        "authored_module_validation_projection.py"
    )
    controller_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/"
        "module_editor_controller.py"
    )
    controller_mirror = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/modules/"
        "module_editor_controller.py"
    )

    for text in (source, mirror):
        assert "authored_module_readiness_validation_issues" in text
        assert "MAP_STUDIO_RUNTIME_RESOURCE_MISSING" in text
        assert "MAP_STUDIO_GAME_PROOF_REQUIRED" in text
        assert "MAP_STUDIO_FLOOR_PLAN_GEOMETRY_BLOCKER" in text
        assert "MAP_STUDIO_FLOOR_PLAN_GEOMETRY_WARNING" in text
        assert "MAP_STUDIO_VISIBILITY_BLOCKER" in text
        assert "MAP_STUDIO_VISIBILITY_WARNING" in text
        assert "MAP_STUDIO_TRANSITION_WOK_SURFACE_BLOCKER" in text
        assert "MAP_STUDIO_TRANSITION_WOK_SURFACE_WARNING" in text
        assert "MAP_STUDIO_LIGHTING_WARNING" in text
        assert "geometry_validation" in text
        assert "visibility" in text
        assert "lighting" in text
        assert "Suggested" not in text

    for text in (controller_source, controller_mirror):
        assert "from .authored_module_validation_projection import authored_module_readiness_validation_issues" in text
        assert "issues.extend(" in text
        assert "bridge_warnings=readiness_result.warnings" in text


def test_t2905_gmodeler_hover_uses_stable_mesh_component_identity() -> None:
    _install_native_payload_paths()
    from src.core.modules.map_studio_hover_context import (
        MapStudioHoverCandidateFace,
        pick_map_studio_hover_context,
    )
    from src.core.modules.map_studio_marking_menu_registry import available_map_studio_marking_menu_trees

    first = MapStudioHoverCandidateFace(
        room_resref="grhover01",
        mesh_role="render",
        face_index=4,
        screen_points=((0.0, 0.0), (100.0, 0.0), (100.0, 100.0)),
        world_points=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)),
        vertex_indices=(10, 11, 12),
    )
    second = MapStudioHoverCandidateFace(
        room_resref="grhover01",
        mesh_role="render",
        face_index=9,
        screen_points=((0.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
        world_points=((0.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)),
        vertex_indices=(10, 12, 13),
    )

    edge = pick_map_studio_hover_context((first, second), 50.0, 50.0)
    assert edge.component_type == "edge"
    assert edge.mesh_edge_indices == (10, 12)
    assert edge.adjacent_face_indices == (4, 9)
    assert edge.is_border is False

    face = pick_map_studio_hover_context((first, second), 50.0, 20.0)
    assert face.component_type == "face"
    assert face.selector_edge_corners == (0, 1)
    assert face.selector_world_point == (0.5, 0.0, 0.0)
    for tree in available_map_studio_marking_menu_trees():
        assert len(tree.action_keys) == len(set(tree.action_keys))


def test_t2907_live_terrain_sculpt_interpolates_segments_and_exposes_hardness() -> None:
    _install_native_payload_paths()
    from src.core.modules.map_studio_terrain_sculpt_session import (
        interpolate_terrain_sculpt_segment,
        terrain_sculpt_brush_is_deferred,
    )

    points = interpolate_terrain_sculpt_segment((2, 1, 0.25), (2, 6, 1.0), include_start=True)
    assert [(point.row_index, point.column_index) for point in points] == [
        (2, 1),
        (2, 2),
        (2, 3),
        (2, 4),
        (2, 5),
        (2, 6),
    ]
    assert terrain_sculpt_brush_is_deferred("ramp") is True
    assert terrain_sculpt_brush_is_deferred("raise") is False

    builder = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/builder_tab.py"
    )
    viewport = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    assert "mapStudioTerrainHardnessSpinBox" in builder
    assert 'terrain_brush_form.addRow("Falloff hardness:"' in builder
    assert "key == QtCore.Qt.Key_Space" in viewport
    assert "tuple(segment[start_index : start_index + 8])" in viewport


def test_t2603_imported_face_extrude_promotes_resident_mesh_without_renderer_reset(monkeypatch) -> None:
    """A topology commit replaces one mesh, not the combined module model."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()

    import moderngl
    from PySide6 import QtWidgets

    monkeypatch.setattr(moderngl.VertexArray, "render", lambda self, *args, **kwargs: None)

    from scripts.gmodeler_tool_matrix import _cube_surfaces
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
    )
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import (
        AuthoredModuleMetadata,
        AuthoredModuleProject,
        AuthoredRoomSpec,
    )
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    room_resref = "perfroom"
    source_face_mats = tuple(index % 2 for index in range(len(_cube_surfaces()[0].faces)))
    base = replace(_cube_surfaces()[0], face_mats=source_face_mats)
    neighbor = replace(
        base,
        name="neighbor_cube",
        vertices=tuple((vertex[0] + 4.0, vertex[1], vertex[2]) for vertex in base.vertices),
    )
    authored = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(
            module_root="perfmod",
            game="K1",
            display_name="Topology Commit Performance",
            tag="perfmod",
        ),
        rooms=(
            AuthoredRoomSpec(
                room_resref=room_resref,
                primitive=ImportedMeshRoomPrimitive(
                    room_resref=room_resref,
                    surfaces=(base, neighbor),
                    game="K1",
                ),
            ),
        ),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="perfmod")),
    )

    window = ModuleEditorWindow()
    try:
        window.controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(authored)
        window._refresh_all("topology performance fixture")
        app.processEvents()

        viewport = window.viewport_panel.viewport
        resident_model = viewport.model
        nodes = {
            str(getattr(node, "_gr_map_studio_mesh_role", "") or ""): node
            for _room_node, node in window.viewport_panel._iter_room_preview_mesh_nodes(room_resref)
        }
        target = nodes["render"]
        neighbor_node = nodes["imported_srf_1"]
        target_faces_before = len(target.faces)
        load_model_calls: list[object] = []
        original_load_model = viewport.load_model

        def tracked_load_model(*args, **kwargs):
            load_model_calls.append(args[0] if args else None)
            return original_load_model(*args, **kwargs)

        viewport.load_model = tracked_load_model
        payload = {
            "kind": "face",
            "room_resref": room_resref,
            "mesh_role": "render",
            "face_indices": (0,),
            "distance": 0.5,
            "axis_mode": "normal",
            "axis": (0.0, 0.0, 1.0),
        }
        window._preview_map_studio_component_extrude(payload)
        prepared = window._map_studio_prepared_topology_preview
        assert prepared is not None
        assert prepared[1].prepared_sample_count == 2
        preview_at_035 = dict(payload, distance=0.35)
        window._preview_map_studio_component_extrude(preview_at_035)
        assert window._map_studio_prepared_topology_preview[1] is prepared[1]
        assert window._last_map_studio_topology_preview_ms < 10.0
        assert viewport.model is resident_model
        assert nodes["render"] is target
        assert nodes["imported_srf_1"] is neighbor_node
        assert load_model_calls == []
        # Return to the release value. The commit below still re-evaluates the
        # authoritative controller operator and patches that exact surface
        # before promoting the resident preview.
        window._preview_map_studio_component_extrude(payload)
        window._commit_map_studio_component_extrude(payload)

        assert load_model_calls == []
        assert viewport.model is resident_model
        assert nodes["render"] is target
        assert nodes["imported_srf_1"] is neighbor_node
        assert len(target.faces) > target_faces_before
        assert len(target.face_mats) == len(target.faces)
        assert set(target.face_mats) == {0, 1}
        assert window.viewport_panel._component_mesh_preview_baselines == {}
        assert window._map_studio_prepared_topology_preview is None
        assert window.viewport_panel._room_preview_model_key.startswith("resident-topology:perfroom:render:")
        assert window._last_map_studio_geometry_refresh_ms < 10.0

        committed = authored_project_from_kmap_payload(
            window.controller.project.extra_sections["authored_module"],
            fallback_name="perfmod",
            fallback_game="K1",
        )
        committed_surface = committed.rooms[0].primitive.surfaces[0]
        assert len(committed_surface.faces) == len(target.faces)
        assert tuple(target.face_mats) == committed_surface.face_mats
        assert window.controller.command_history.undo_label.startswith("Extrude 1 face(s)")

        generation = int(window._map_studio_geometry_refresh_generation)
        started = perf_counter()
        window._refresh_map_studio_geometry_validation(generation)
        assert perf_counter() - started < 0.1
        deadline = perf_counter() + 10.0
        while (
            getattr(window, "_map_studio_geometry_validation_future", None) is not None
            and perf_counter() < deadline
        ):
            app.processEvents()
            sleep(0.005)
        app.processEvents()
        assert getattr(window, "_map_studio_geometry_validation_future", None) is None
        assert window._last_map_studio_geometry_validation_ms > 0.0

        window.undo_map_studio_command()
        assert len(load_model_calls) == 1
    finally:
        window.controller.project.dirty = False
        window.close()
        app.processEvents()


def test_t2907_visible_extrude_and_bevel_controls_arm_live_component_tools() -> None:
    _install_native_payload_paths()

    from src.gui.windows.module_editor_window import ModuleEditorWindow

    armed: list[str] = []
    messages: list[str] = []
    panel = SimpleNamespace(
        _hover_component_mode="face",
        map_studio_component_selection=lambda: [{"component_type": "face"}],
        arm_component_extrude=lambda: armed.append("extrude") or True,
        arm_component_bevel=lambda: armed.append("bevel") or True,
    )
    window = SimpleNamespace(
        viewport_panel=panel,
        statusBar=lambda: SimpleNamespace(showMessage=lambda message, _duration=0: messages.append(message)),
    )

    assert ModuleEditorWindow._try_arm_map_studio_component_tool(window, "extrude") is True
    assert ModuleEditorWindow._try_arm_map_studio_component_tool(window, "bevel") is True
    assert armed == ["extrude", "bevel"]
    assert messages[0].startswith("Extrude armed")
    assert messages[1].startswith("Bevel armed")


def test_t2907_bevel_width_frames_reuse_prepared_resident_topology() -> None:
    _install_native_payload_paths()

    from scripts.gmodeler_tool_matrix import _cube_surfaces
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    source = ImportedMeshRoomPrimitive(
        room_resref="bevelperf",
        surfaces=(_cube_surfaces()[0],),
        game="K1",
    )
    shown: list[ImportedMeshRoomPrimitive] = []
    messages: list[str] = []
    window = SimpleNamespace(
        _map_studio_prepared_topology_preview=None,
        _map_studio_live_topology_source=lambda _payload: source,
        _show_live_imported_surface=lambda primitive, _room, _role: shown.append(primitive) or True,
        statusBar=lambda: SimpleNamespace(showMessage=lambda message, _duration=0: messages.append(message)),
    )
    window._map_studio_prepared_topology_session = lambda primitive, payload, operation: (
        ModuleEditorWindow._map_studio_prepared_topology_session(window, primitive, payload, operation)
    )
    payload = {
        "kind": "edge_bevel",
        "room_resref": "bevelperf",
        "mesh_role": "render",
        "face_index": 0,
        "edge_corners": (0, 1),
        "amount": 0.1,
        "segments": 3,
        "profile": 0.75,
        "miter": "patch",
        "smoothing_angle_degrees": 60.0,
        "uv_mode": "preserve",
        "clamp_overlap": True,
    }

    ModuleEditorWindow._preview_map_studio_component_bevel(window, payload)
    prepared = window._map_studio_prepared_topology_preview
    assert prepared is not None
    ModuleEditorWindow._preview_map_studio_component_bevel(window, dict(payload, amount=0.3))

    assert window._map_studio_prepared_topology_preview[1] is prepared[1]
    assert len(shown) == 2
    assert shown[0].surfaces[0].faces is shown[1].surfaces[0].faces
    assert shown[0].surfaces[0].face_mats is shown[1].surfaces[0].face_mats
    assert window._last_map_studio_topology_preview_ms < 10.0
    assert messages == []


def test_t2907_edge_extrude_distance_frames_reuse_prepared_resident_topology() -> None:
    _install_native_payload_paths()

    from scripts.gmodeler_tool_matrix import _cube_surfaces
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    source = ImportedMeshRoomPrimitive(
        room_resref="edgeperf",
        surfaces=(_cube_surfaces()[0],),
        game="K1",
    )
    shown: list[ImportedMeshRoomPrimitive] = []
    messages: list[str] = []
    window = SimpleNamespace(
        _map_studio_prepared_topology_preview=None,
        _map_studio_live_topology_source=lambda _payload: source,
        _show_live_imported_surface=lambda primitive, _room, _role: shown.append(primitive) or True,
        statusBar=lambda: SimpleNamespace(showMessage=lambda message, _duration=0: messages.append(message)),
    )
    window._map_studio_prepared_topology_session = lambda primitive, payload, operation: (
        ModuleEditorWindow._map_studio_prepared_topology_session(window, primitive, payload, operation)
    )
    payload = {
        "kind": "edge",
        "room_resref": "edgeperf",
        "mesh_role": "render",
        "face_index": 0,
        "edge_corners": (0, 1),
        "distance": 0.2,
        "axis": (0.0, 0.0, 1.0),
    }

    ModuleEditorWindow._preview_map_studio_component_extrude(window, payload)
    prepared = window._map_studio_prepared_topology_preview
    assert prepared is not None
    assert prepared[1].identity.operation == "edge_extrude"
    ModuleEditorWindow._preview_map_studio_component_extrude(window, dict(payload, distance=-0.35))

    assert window._map_studio_prepared_topology_preview[1] is prepared[1]
    assert len(shown) == 2
    assert shown[0].surfaces[0].faces is shown[1].surfaces[0].faces
    assert shown[0].surfaces[0].face_mats is shown[1].surfaces[0].face_mats
    assert shown[0].surfaces[0].uvs_lm is shown[1].surfaces[0].uvs_lm
    assert window._last_map_studio_topology_preview_ms < 10.0
    assert messages == []


def test_t2603_topology_refresh_defers_validation_and_keeps_structural_fallback(monkeypatch) -> None:
    _install_native_payload_paths()

    from concurrent.futures import Future

    from PySide6 import QtCore
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    scheduled: list[tuple[int, object]] = []
    monkeypatch.setattr(
        QtCore.QTimer,
        "singleShot",
        lambda delay, callback: scheduled.append((int(delay), callback)),
    )
    live_drag_window = SimpleNamespace(
        _map_studio_geometry_refresh_generation=4,
        viewport_panel=SimpleNamespace(_component_extrude_drag={"active": True}),
    )
    ModuleEditorWindow._refresh_map_studio_geometry_validation(live_drag_window, 4)
    assert len(scheduled) == 1
    assert scheduled[0][0] == 100

    stale_future: Future = Future()
    stale_future.set_result({})
    replaced_project_window = SimpleNamespace(
        _map_studio_geometry_validation_future_generation=3,
        _map_studio_geometry_validation_future=stale_future,
        _map_studio_geometry_refresh_generation=4,
        _map_studio_geometry_validation_requested_generation=-1,
        _refresh_map_studio_geometry_validation=lambda _generation: (_ for _ in ()).throw(
            AssertionError("a broad refresh already supplied current readiness")
        ),
    )
    ModuleEditorWindow._poll_map_studio_geometry_validation(replaced_project_window, 3)
    assert replaced_project_window._map_studio_geometry_validation_future is None

    refresh_calls: list[dict[str, object]] = []
    room_spec = SimpleNamespace(primitive=SimpleNamespace(surfaces=(object(),)))
    controller = SimpleNamespace(
        last_committed_imported_mesh_room=lambda _room: room_spec,
        imported_mesh_room=lambda _room: room_spec,
    )
    panel = SimpleNamespace(
        _iter_room_preview_mesh_nodes=lambda _room: iter(((object(), object()), (object(), object()))),
        promote_component_mesh_preview=lambda *_args: (_ for _ in ()).throw(
            AssertionError("mismatched surface layout must not promote")
        ),
    )
    fallback_window = SimpleNamespace(
        controller=controller,
        viewport_panel=panel,
        _show_live_imported_surface=lambda *_args: (_ for _ in ()).throw(
            AssertionError("mismatched surface layout must not patch a node")
        ),
        _refresh_map_studio_geometry_change=lambda _message, **kwargs: refresh_calls.append(kwargs),
    )
    promoted = ModuleEditorWindow._refresh_map_studio_imported_mesh_change(
        fallback_window,
        "deleted a whole material surface",
        "perfroom",
        "render",
    )
    assert promoted is False
    assert refresh_calls == [{"rebuild_viewport_model": True, "refresh_scene_tree": True}]

    source = _read("native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py")
    assert "rebuild_viewport_model=not promoted" in source
    assert "refresh_scene_tree=not promoted" in source
    assert "QtCore.QTimer.singleShot(75" in source
    assert "_MAP_STUDIO_VALIDATION_EXECUTOR.submit" in source
    assert "def _poll_map_studio_geometry_validation" in source


def test_map_studio_generate_walkmesh_action_recompiles_without_broad_refresh_or_kmap_mutation() -> None:
    _install_native_payload_paths()

    from src.gui.windows.module_editor_window import ModuleEditorWindow

    status = SimpleNamespace(
        ready=True,
        room_count=1,
        terrain_room_count=1,
        walkable_triangle_count=32,
        non_walk_triangle_count=0,
        max_slope_degrees=4.9,
        blocking_messages=(),
        next_action="Validate before staging.",
    )
    overlay = object()
    calls: dict[str, object] = {}
    window = SimpleNamespace(
        controller=SimpleNamespace(
            authored_walkmesh_status=lambda: status,
            authored_walkmesh_room_surface_choices=lambda: ("room-surface",),
            authored_terrain_walkability_overlay=lambda: overlay,
        ),
        walkmesh_tab=SimpleNamespace(
            set_walkmesh_status=lambda value: calls.setdefault("status", value),
            set_room_surface_choices=lambda value: calls.setdefault("surfaces", value),
        ),
        viewport_panel=SimpleNamespace(
            set_terrain_walkability_overlay=lambda value: calls.setdefault("overlay", value),
        ),
        workflow_panel=SimpleNamespace(
            set_active_authoring_context=lambda value: calls.setdefault("context", value),
        ),
        _select_map_studio_component_mode=lambda value: calls.setdefault("mode", value),
        _log=lambda value: calls.setdefault("log", value),
        statusBar=lambda: SimpleNamespace(showMessage=lambda value, _timeout: calls.setdefault("message", value)),
        _refresh_all=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Generate Walkmesh must not reset the resident renderer")
        ),
    )

    ModuleEditorWindow._handle_tab_action(window, "Generate Walkmesh")

    assert calls["status"] is status
    assert calls["surfaces"] == ("room-surface",)
    assert calls["overlay"] is overlay
    assert calls["mode"] == "walkmesh"
    assert "Regenerated derived WOK" in str(calls["message"])
    assert "32 walkable triangle(s)" in str(calls["message"])
    assert "experimental" not in str(calls["log"]).lower()

    source = _read("native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py")
    assert 'if action in {"Generate Walkmesh", "Validate Walkmesh"}:' in source
    assert "self.workflow_tabs.currentChanged.connect(self._reset_map_studio_workflow_scroll)" in source
    assert "def _reset_map_studio_workflow_scroll" in source


def test_map_studio_texture_paint_ui_and_nearest_uv_streaming_contract() -> None:
    paint_display = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/texture_paint_tab.py"
    )
    paint_tools = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/texture_paint_tab.py"
    )
    viewport_display = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    viewport_tools = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    )
    window = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"
    )

    assert paint_display == paint_tools
    assert viewport_display == viewport_tools
    for token in (
        "mapStudioTexturePaintTargetComboBox",
        "mapStudioTexturePaintBrushSourceButton",
        "mapStudioTexturePaintSizeSpinBox",
        "mapStudioTexturePaintOpacitySpinBox",
        "mapStudioTexturePaintFlowSpinBox",
        "mapStudioTexturePaintHardnessSpinBox",
        "mapStudioTexturePaintSpacingSpinBox",
        "mapStudioTexturePaintEnableButton",
    ):
        assert token in paint_display
    for token in (
        "texturePaintStrokeBegan",
        "texturePaintSampleRequested",
        "set_texture_paint_interaction",
        'getattr(context, "uv"',
        'face_uvs = getattr(mesh_node, "face_uvs", ()) or ()',
        "_map_studio_face_uv_points(mesh_node, face_index, face_vertex_indices)",
    ):
        assert token in viewport_display
    assert "update_texture_regions" in window
    assert '("Paint", self.texture_paint_tab)' in window
    assert "commit_project_texture_paint" in window
    assert "def _show_map_studio_texture_paint_workflow" in window
    assert 'if action_key == "texture_paint":' in window


def test_map_studio_texture_paint_hover_uses_seam_expanded_per_corner_uvs() -> None:
    import pytest

    _install_native_payload_paths()
    from src.core.modules.map_studio_hover_context import pick_map_studio_hover_context
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    mesh = SimpleNamespace(
        faces=((0, 1, 2),),
        # The first triangle is the misleading geometry-vertex fallback.  The
        # asymmetric second triangle is the face's rendered seam mapping.
        uvs=(
            (0.02, 0.03),
            (0.11, 0.07),
            (0.09, 0.19),
            (0.61, 0.17),
            (0.94, 0.23),
            (0.72, 0.91),
        ),
        face_uvs=((3, 4, 5),),
    )
    uv_points = ModuleEditorViewportPanel._map_studio_face_uv_points(mesh, 0, (0, 1, 2))
    assert tuple(uv_points[0]) == pytest.approx((0.61, 0.17))
    assert tuple(uv_points[1]) == pytest.approx((0.94, 0.23))
    assert tuple(uv_points[2]) == pytest.approx((0.72, 0.91))

    owner = SimpleNamespace(_map_studio_face_normal=lambda _points: (0.0, 0.0, 1.0))
    candidate = ModuleEditorViewportPanel._map_studio_projected_candidate(
        owner,
        lambda x, y, z, _width, _height: (x, y, z),
        640,
        480,
        ((0.0, 0.0, 1.0), (100.0, 0.0, 2.0), (0.0, 100.0, 2.0)),
        room_resref="koq200_01f",
        mesh_role="stock_room_0",
        material="asym_seam",
        face_index=0,
        walkable=None,
        vertex_indices=(0, 1, 2),
        uv_points=uv_points,
    )
    hit = pick_map_studio_hover_context((candidate,), 25.0, 25.0, tolerance_px=0.0)
    # Perspective weights are (2/3, 1/6, 1/6); the fallback UV triangle would
    # produce (0.0467, 0.0633), making this an asymmetric orientation check too.
    assert hit.uv == pytest.approx((0.6833333333, 0.3033333333))

    invalid_corner_mesh = SimpleNamespace(
        faces=((0, 1, 2),),
        uvs=mesh.uvs,
        face_uvs=((3, 999, 5),),
    )
    fallback = ModuleEditorViewportPanel._map_studio_face_uv_points(invalid_corner_mesh, 0, (0, 1, 2))
    assert tuple(fallback[0]) == pytest.approx((0.61, 0.17))
    assert tuple(fallback[1]) == pytest.approx((0.11, 0.07))
    assert tuple(fallback[2]) == pytest.approx((0.72, 0.91))


def test_map_studio_texture_paint_cursor_maps_texel_radius_and_hardness_to_uv_surface() -> None:
    _install_native_payload_paths()
    from src.core.modules.map_studio_hover_context import MapStudioHoverCandidateFace
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    captured = []
    owner = SimpleNamespace(
        _texture_paint_enabled=True,
        _texture_paint_brush_context={
            "radius_px": 100.0,
            "hardness": 0.5,
            "pressure_size": False,
            "texture_size": (1000, 1000),
            "resref": "paint_wall",
        },
        viewport=SimpleNamespace(set_map_studio_texture_paint_cursor=lambda payload: captured.append(payload)),
    )
    candidate = MapStudioHoverCandidateFace(
        room_resref="room01",
        mesh_role="render",
        face_index=0,
        screen_points=((0.0, 0.0), (100.0, 0.0), (0.0, 100.0)),
        world_points=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        uv_points=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        material="paint_wall",
    )
    context = SimpleNamespace(
        component_type="face",
        room_resref="room01",
        mesh_role="render",
        face_index=0,
        uv=(0.5, 0.5),
        material="paint_wall",
    )

    ModuleEditorViewportPanel._set_texture_paint_cursor_at_screen(
        owner,
        context,
        (candidate,),
        (50.0, 50.0),
    )

    payload = captured[-1]
    assert payload["valid"] is True
    assert len(payload["outer"]) == 40
    outer_radius = max(((x - 50.0) ** 2 + (y - 50.0) ** 2) ** 0.5 for x, y in payload["outer"])
    inner_radius = max(((x - 50.0) ** 2 + (y - 50.0) ** 2) ** 0.5 for x, y in payload["inner"])
    assert outer_radius == pytest.approx(10.0)
    assert inner_radius == pytest.approx(5.0)


def test_map_studio_texture_paint_targets_only_writable_project_sidecars() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.gui.panels.module_editor.texture_paint_tab import MapStudioTexturePaintTab

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    tab = MapStudioTexturePaintTab()
    try:
        project = SimpleNamespace(
            textures=(
                SimpleNamespace(texture_id="stock", resref="lda_wall01", path=""),
                SimpleNamespace(texture_id="project", resref="paint_wall", path="map_assets/textures/paint_wall.tga"),
                SimpleNamespace(
                    texture_id="project_detail",
                    resref="paint_detail",
                    path="map_assets/textures/paint_detail.tga",
                ),
                SimpleNamespace(
                    texture_id="lightmap",
                    resref="lm_paint",
                    path="map_assets/textures/lm_paint.tpc",
                    metadata={"asset_kind": "map_studio_lightmap", "format": "tpc"},
                ),
            ),
            extra_sections={
                "authored_module": {
                    "texture_paint_dirty": True,
                    "texture_paint_unapplied": True,
                    "texture_paint_pending_resrefs": ["paint_wall"],
                }
            },
        )
        emitted = []
        tab.applyRequested.connect(lambda: emitted.append(True))
        tab.set_project(project)
        oversized = [
            (type(widget).__name__, widget.objectName(), widget.minimumSizeHint().width())
            for widget in tab.findChildren(QtWidgets.QWidget)
            if widget.minimumSizeHint().width() > 260
        ]
        assert tab.minimumSizeHint().width() <= 300, oversized
        assert tab.target_combo.count() == 2
        assert tab.selected_texture_id() == "project"
        assert tab.selected_resref() == "paint_wall"
        assert tab.apply_button.text() == "Apply Textures (1)"
        assert tab.apply_button.isEnabled() is True
        assert tab.has_unapplied_changes() is True
        assert "before export" in tab.status_label.text()
        selected_targets = []
        tab.targetChanged.connect(selected_targets.append)
        tab.set_material_inventory(("paint_wall", "paint_detail", "game_floor", "lm_paint"), project)
        assert tab.material_list.count() == 3
        assert "Editable" in tab.material_list.item(0).text() or "Painted" in tab.material_list.item(0).text()
        assert "Editable" in tab.material_list.item(1).text()
        assert "read-only" in tab.material_list.item(2).text()
        assert tab.make_used_editable_button.isEnabled() is True
        tab.material_list.itemClicked.emit(tab.material_list.item(1))
        assert tab.selected_texture_id() == "project_detail"
        assert selected_targets[-1] == "project_detail"
        assert "paint_detail is the paint target" in tab.status_label.text()
        tab.material_list.itemActivated.emit(tab.material_list.item(2))
        assert tab.selected_texture_id() == "project_detail"
        assert "read-only game room diffuse" in tab.status_label.text()
        tab.preset_combo.setCurrentIndex(tab.preset_combo.findData("soft"))
        assert tab.current_brush().radius_px == 96.0
        assert tab.current_brush().opacity == pytest.approx(0.45)
        tab.advanced_button.setChecked(True)
        assert tab.advanced_widget.isHidden() is False
        tab.paint_button.setChecked(True)
        assert tab.apply_button.isEnabled() is False
        tab.stop_painting()
        assert tab.apply_button.isEnabled() is True
        tab.apply_button.click()
        assert emitted == [True]
        project.extra_sections["authored_module"]["texture_paint_dirty"] = False
        project.extra_sections["authored_module"]["texture_paint_unapplied"] = False
        tab.set_project(project)
        assert tab.apply_button.isEnabled() is True
        assert tab.has_unapplied_changes() is False
        tab.set_apply_state(True, ("paint_detail",))
        assert tab.apply_button.text() == "Apply Textures (1)"
        assert "need Apply Textures" in tab.status_label.text()
    finally:
        tab.close()
        app.processEvents()


def test_map_studio_texture_preview_renderer_contract_reports_once_without_retry() -> None:
    _install_native_payload_paths()
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    calls = []
    messages = []
    logs = []

    def failing_update(*args, **kwargs):
        calls.append((args, kwargs))
        raise TypeError("renderer adapter is missing the finalize contract")

    owner = SimpleNamespace(
        viewport_panel=SimpleNamespace(viewport=SimpleNamespace(update_texture_regions=failing_update)),
        _texture_paint_resref="paint_wall",
        _texture_paint_preview_error="",
        texture_paint_tab=SimpleNamespace(set_status=messages.append),
        statusBar=lambda: SimpleNamespace(showMessage=lambda message, _timeout: messages.append(message)),
        _log=logs.append,
    )

    ok = ModuleEditorWindow._publish_map_studio_texture_paint_preview(
        owner,
        object(),
        ((0, 0, 16, 16),),
        finalize=False,
    )

    assert ok is False
    assert len(calls) == 1
    assert calls[0][1] == {"finalize": False}
    assert "tile upload failed" in owner._texture_paint_preview_error
    assert any("fix the renderer before trusting the preview" in message for message in messages)
    assert logs and "renderer adapter is missing" in logs[-1]

    source = _read("native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py")
    publish_body = source.split("def _publish_map_studio_texture_paint_preview", 1)[1].split(
        "def _apply_map_studio_texture_paint_tiles", 1
    )[0]
    assert "except TypeError" not in publish_body
    assert publish_body.count("updater(") == 1


def test_map_studio_room_texture_batch_shows_progress_and_cancels_cleanly() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()

    from threading import get_ident

    from PySide6 import QtCore, QtWidgets
    from src.core.modules.module_editor_controller import MapStudioTextureCloneCancelled
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    statuses = []
    logs = []
    observed_progress = []
    worker_threads = []
    gui_thread = get_ident()

    class CancellingController:
        def clone_game_textures_for_paint(
            self,
            resrefs,
            *,
            resource_manager,
            progress_callback,
            cancel_requested,
        ):
            assert tuple(resrefs) == ("room_wall", "room_floor")
            assert resource_manager is not None
            worker_threads.append(get_ident())
            progress_callback(1, 2, "room_wall")
            for _index in range(200):
                if cancel_requested():
                    raise MapStudioTextureCloneCancelled("cancelled by test")
                sleep(0.005)
            raise AssertionError("GUI-thread Cancel did not reach the texture worker")

    owner = QtWidgets.QMainWindow()
    owner.project = SimpleNamespace(path="C:/saved/test.kmap", textures=())
    owner.resource_manager = object()
    owner.viewport_panel = SimpleNamespace(
        _room_preview_model=SimpleNamespace(
            all_nodes=lambda: (
                SimpleNamespace(is_mesh=True, _gr_map_studio_mesh_role="stock_room_0", texture="room_wall"),
                SimpleNamespace(is_mesh=True, _gr_map_studio_mesh_role="stock_room_1", texture="room_floor"),
                SimpleNamespace(is_mesh=True, _gr_map_studio_mesh_role="stock_creature_0", texture="npc_body"),
            )
        ),
        set_project_texture_paths=lambda _project: None,
    )
    owner.texture_paint_tab = SimpleNamespace(
        set_status=statuses.append,
        set_project=lambda _project: None,
        set_material_inventory=lambda _resrefs, _project: None,
    )
    owner.controller = CancellingController()
    owner.save_kmap_as = lambda: None
    owner._used_map_diffuse_resrefs = ModuleEditorWindow._used_map_diffuse_resrefs
    owner._log = logs.append
    owner._update_map_studio_undo_redo_actions = lambda: None

    def cancel_from_gui_thread() -> None:
        dialog = next(
            widget
            for widget in app.topLevelWidgets()
            if widget.objectName() == "mapStudioRoomTextureCloneProgressDialog"
        )
        observed_progress.append((dialog.value(), dialog.maximum(), dialog.labelText()))
        dialog.cancel()

    try:
        QtCore.QTimer.singleShot(120, cancel_from_gui_thread)
        ModuleEditorWindow._make_used_map_textures_editable(owner)
        app.processEvents()
        assert observed_progress == [(1, 2, "Made 1 of 2 room diffuse textures editable\nroom_wall")]
        assert worker_threads and worker_threads[0] != gui_thread
        assert statuses[-1] == (
            "Making room diffuse textures editable was cancelled; no project textures were changed."
        )
        assert logs[-1] == statuses[-1]
    finally:
        owner.close()
        owner.deleteLater()
        app.processEvents()


def _map_studio_texture_apply_draft_project(tmp_path: Path):
    from src.core.level import TextureReference, new_kmap_project
    from src.core.modules.authored_module_kmap_bridge import create_dev_test_authored_module_payload
    from src.core.modules.map_studio_texture_paint import encode_tga_rgba

    project = new_kmap_project(name="grapply", game="K2")
    project.path = str(tmp_path / "grapply.kmap")
    sidecar = tmp_path / "grapply_assets" / "textures" / "paint_wall.tga"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_bytes(encode_tga_rgba(4, 4, bytes((30, 60, 90, 255)) * 16))
    texture = TextureReference(
        resref="paint_wall",
        path="grapply_assets/textures/paint_wall.tga",
        source="map_studio:texture_paint_commit",
        metadata={
            "format": "tga",
            "width": 4,
            "height": 4,
            "paint_revision": 3,
            "paint_unapplied": True,
            "diffuse_uv_channel": 0,
            "lightmap_untouched": True,
        },
    )
    project.textures.append(texture)
    payload = create_dev_test_authored_module_payload(module_root="grapply", game="K2")
    payload["texture_paint_dirty"] = True
    payload["texture_paint_unapplied"] = True
    payload["texture_paint_resref"] = "paint_wall"
    payload["texture_paint_pending_resrefs"] = ["paint_wall"]
    project.extra_sections["authored_module"] = payload
    return project, texture


def test_map_studio_texture_apply_is_an_undoable_headless_export_gate(tmp_path: Path, monkeypatch) -> None:
    _install_native_payload_paths()
    from src.core.modules.authored_module_kmap_bridge import (
        TEXTURE_PAINT_UNAPPLIED_BLOCKER,
        build_kmap_authored_module_readiness,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController
    import src.core.modules.module_editor_controller as controller_module

    project, texture = _map_studio_texture_apply_draft_project(tmp_path)
    controller = ModuleEditorController()
    controller.model.set_project(project)
    export_calls = []

    def fake_export(request):
        export_calls.append(request)
        return SimpleNamespace(resources=(), message="dry-run export accepted")

    monkeypatch.setattr(controller_module, "export_authored_module_project", fake_export)
    readiness = build_kmap_authored_module_readiness(project).readiness
    assert readiness is not None
    assert readiness.can_export_candidate is False
    assert TEXTURE_PAINT_UNAPPLIED_BLOCKER in readiness.blocking_messages
    assert readiness.metadata["texture_paint_apply"] == {
        "unapplied": True,
        "pending_resrefs": ["paint_wall"],
        "export_blocked": True,
    }
    with pytest.raises(ValueError, match="Apply Texture Changes"):
        controller.export_authored_module(tmp_path / "blocked", dry_run=True)
    assert export_calls == []

    result = controller.apply_project_texture_changes()
    payload = project.extra_sections["authored_module"]
    assert result["applied"] is True
    assert result["resrefs"] == ("paint_wall",)
    assert payload["texture_paint_dirty"] is False
    assert payload["texture_paint_unapplied"] is False
    assert payload["texture_paint_pending_resrefs"] == []
    assert payload["texture_paint_applied_revision"] == 1
    assert payload["texture_paint_applied_resources"][0]["restype"] == "tga"
    assert len(payload["texture_paint_applied_resources"][0]["sha256"]) == 64
    assert texture.metadata["paint_applied_revision"] == 3
    assert texture.metadata["paint_unapplied"] is False
    assert texture.metadata["diffuse_uv_channel"] == 0
    assert texture.metadata["lightmap_untouched"] is True

    accepted = controller.export_authored_module(tmp_path / "accepted", dry_run=True)
    assert accepted.message == "dry-run export accepted"
    assert len(export_calls) == 1
    assert any(item[:2] == ("paint_wall", "tga") for item in export_calls[0].extra_resources)
    sidecar = tmp_path / "grapply_assets" / "textures" / "paint_wall.tga"
    sidecar.write_bytes(sidecar.read_bytes()[:-1] + bytes((sidecar.read_bytes()[-1] ^ 0x01,)))
    with pytest.raises(ValueError, match="changed after Apply Texture Changes"):
        controller.export_authored_module(tmp_path / "externally_changed", dry_run=True)
    assert len(export_calls) == 1
    applied_readiness = build_kmap_authored_module_readiness(project).readiness
    assert applied_readiness is not None
    assert TEXTURE_PAINT_UNAPPLIED_BLOCKER not in applied_readiness.blocking_messages
    assert controller.undo_map_studio_command() is not None
    assert controller.has_unapplied_project_texture_changes() is True
    assert controller.redo_map_studio_command() is not None
    assert controller.has_unapplied_project_texture_changes() is False


def test_texture_apply_merges_resources_and_recovers_later_txi_hash_drift(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_native_payload_paths()
    import hashlib

    from src.core.level import TextureReference
    from src.core.modules.map_studio_texture_paint import encode_tga_rgba
    from src.core.modules.module_editor_controller import ModuleEditorController
    import src.core.modules.module_editor_controller as controller_module

    project, texture_a = _map_studio_texture_apply_draft_project(tmp_path)
    texture_a.metadata["txi_path"] = "grapply_assets/textures/paint_wall.txi"
    txi_a = tmp_path / "grapply_assets" / "textures" / "paint_wall.txi"
    txi_a.write_text("mipmap 1\n", encoding="utf-8")
    controller = ModuleEditorController()
    controller.model.set_project(project)

    first = controller.apply_project_texture_changes()
    assert first["resrefs"] == ("paint_wall",)
    assert first["resource_count"] == 2
    first_manifest = {
        (item["resref"], item["restype"]): item["sha256"]
        for item in controller.project.extra_sections["authored_module"]["texture_paint_applied_resources"]
    }
    assert set(first_manifest) == {("paint_wall", "tga"), ("paint_wall", "txi")}

    texture_dir = tmp_path / "grapply_assets" / "textures"
    sidecar_b = texture_dir / "paint_floor.tga"
    sidecar_b.write_bytes(encode_tga_rgba(4, 4, bytes((90, 60, 30, 255)) * 16))
    txi_b = texture_dir / "paint_floor.txi"
    txi_b.write_text("mipmap 2\n", encoding="utf-8")
    controller.project.textures.append(
        TextureReference(
            resref="paint_floor",
            path="grapply_assets/textures/paint_floor.tga",
            source="map_studio:texture_paint_commit",
            metadata={
                "format": "tga",
                "width": 4,
                "height": 4,
                "paint_revision": 1,
                "paint_unapplied": True,
                "txi_path": "grapply_assets/textures/paint_floor.txi",
            },
        )
    )
    payload = controller.project.extra_sections["authored_module"]
    payload["texture_paint_dirty"] = True
    payload["texture_paint_unapplied"] = True
    payload["texture_paint_pending_resrefs"] = ["paint_floor"]

    second = controller.apply_project_texture_changes()
    assert second["resrefs"] == ("paint_floor",)
    assert second["resource_count"] == 2
    second_manifest = {
        (item["resref"], item["restype"]): item["sha256"]
        for item in controller.project.extra_sections["authored_module"]["texture_paint_applied_resources"]
    }
    assert set(second_manifest) == {
        ("paint_wall", "tga"),
        ("paint_wall", "txi"),
        ("paint_floor", "tga"),
        ("paint_floor", "txi"),
    }
    assert second_manifest[("paint_wall", "tga")] == first_manifest[("paint_wall", "tga")]
    assert second_manifest[("paint_wall", "txi")] == first_manifest[("paint_wall", "txi")]

    txi_a.write_text("mipmap 3\nfilter nearest\n", encoding="utf-8")
    assert controller.has_unapplied_project_texture_changes() is False
    assert controller.project_texture_reapply_resrefs() == ("paint_wall",)
    assert controller.project_texture_apply_pending_resrefs() == ("paint_wall",)
    assert controller.project_texture_apply_required() is True

    export_calls = []

    def fake_export(request):
        export_calls.append(request)
        return SimpleNamespace(resources=(), message="dry-run export accepted")

    monkeypatch.setattr(controller_module, "export_authored_module_project", fake_export)
    with pytest.raises(ValueError, match="changed after Apply Texture Changes"):
        controller.export_authored_module(tmp_path / "drift_blocked", dry_run=True)
    assert export_calls == []

    reapplied = controller.apply_project_texture_changes()
    assert reapplied["resrefs"] == ("paint_wall",)
    assert reapplied["resource_count"] == 2
    recovered_manifest = {
        (item["resref"], item["restype"]): item["sha256"]
        for item in controller.project.extra_sections["authored_module"]["texture_paint_applied_resources"]
    }
    assert set(recovered_manifest) == set(second_manifest)
    assert recovered_manifest[("paint_floor", "tga")] == second_manifest[("paint_floor", "tga")]
    assert recovered_manifest[("paint_floor", "txi")] == second_manifest[("paint_floor", "txi")]
    assert recovered_manifest[("paint_wall", "txi")] == hashlib.sha256(txi_a.read_bytes()).hexdigest()
    assert recovered_manifest[("paint_wall", "txi")] != second_manifest[("paint_wall", "txi")]
    assert controller.project_texture_apply_required() is False
    assert controller.export_authored_module(tmp_path / "recovered", dry_run=True).message == "dry-run export accepted"
    assert len(export_calls) == 1


def test_map_studio_window_routes_apply_texture_changes_to_readiness(tmp_path: Path, monkeypatch) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()
    import moderngl
    from PySide6 import QtWidgets

    monkeypatch.setattr(moderngl.VertexArray, "render", lambda self, *args, **kwargs: None)
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    project, _texture = _map_studio_texture_apply_draft_project(tmp_path)
    window = ModuleEditorWindow()
    try:
        window.controller.model.set_project(project)
        window.texture_paint_tab.set_project(project)
        assert window.texture_paint_tab.apply_button.isEnabled() is True
        build_warnings = []
        monkeypatch.setattr(
            QtWidgets.QFileDialog,
            "getExistingDirectory",
            lambda *_args, **_kwargs: str(tmp_path / "blocked_build"),
        )
        monkeypatch.setattr(
            QtWidgets.QMessageBox,
            "warning",
            lambda _parent, title, message: build_warnings.append((title, message)),
        )
        window.build_module_files()
        assert build_warnings
        assert build_warnings[-1][0] == "Build Module"
        assert "Apply Texture Changes" in build_warnings[-1][1]
        assert window.controller.project.extra_sections["authored_module"]["texture_paint_unapplied"] is True
        window.texture_paint_tab.apply_button.click()
        app.processEvents()
        payload = window.controller.project.extra_sections["authored_module"]
        assert payload["texture_paint_unapplied"] is False
        assert window.texture_paint_tab.apply_button.isEnabled() is True
        assert "eligible for module export" in window.texture_paint_tab.status_label.text()
        assert window.controller.command_history.undo_label == "Apply Texture Changes"
        readiness = window.controller.authored_module_readiness().readiness
        assert readiness is not None
        assert not any("unapplied live changes" in message for message in readiness.blocking_messages)
    finally:
        window.controller.project.dirty = False
        window.close()
        app.processEvents()


def test_map_studio_texture_browser_combines_project_and_game_resrefs(tmp_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()
    from PySide6 import QtWidgets

    from src.core.level import TextureReference, new_kmap_project
    from src.gui.panels.module_editor.texture_browser_dialog import MapStudioTextureBrowserDialog

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    project = new_kmap_project(name="paintlib", game="K2")
    project.path = str(tmp_path / "paintlib.kmap")
    project.textures.append(TextureReference(resref="shared_wall", path="paintlib_assets/textures/shared_wall.tga"))

    class FakeManager:
        def list_textures(self, game="all"):
            assert game == "K2"
            return [("shared_wall", "K2"), ("game_floor", "K2")]

        def load_texture_image(self, _name, _game="K2"):
            return None

    dialog = MapStudioTextureBrowserDialog(FakeManager(), project=project, game="K2")
    try:
        rows = {name: (source, path) for name, source, path in dialog._all_textures}
        assert rows["shared_wall"][0] == "Project"
        assert rows["game_floor"][0] == "K2"
        assert all(not name.startswith("(") for name in rows)
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_map_studio_texture_paint_drag_updates_only_dirty_regions_and_undoes_as_one_step(
    tmp_path: Path,
    monkeypatch,
) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()

    import moderngl
    from PySide6 import QtWidgets

    monkeypatch.setattr(moderngl.VertexArray, "render", lambda self, *args, **kwargs: None)

    from src.core.modules.map_studio_texture_paint import encode_tga_rgba
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    source = tmp_path / "paint_target.tga"
    source.write_bytes(encode_tga_rgba(64, 64, bytes((20, 30, 40, 255)) * (64 * 64)))
    window = ModuleEditorWindow()
    try:
        window.controller.new_project(name="grpaint2", game="K2")
        window.controller.save_project(tmp_path / "grpaint2.kmap")
        window.controller.create_dev_test_authored_module()
        asset = window.controller.import_project_texture(source)
        window.texture_paint_tab.set_project(window.project)
        assert window._execute_map_studio_tool_belt_command("texture_paint") is True
        assert window.workflow_tabs.currentWidget() is window.texture_paint_tab

        region_updates: list[tuple[tuple[int, int, int, int], ...]] = []
        texture_updates: list[tuple[str, object]] = []

        def capture_regions(_name, _image, regions=None, *, finalize=False):
            region_updates.append(tuple(regions or ()))
            texture_updates.append((str(_name), _image))
            return _image, tuple(regions or ())

        window.viewport_panel.viewport.update_texture_regions = capture_regions
        session = window._load_map_studio_texture_paint_session(asset.texture_id)
        region_updates.clear()
        target = Path(asset.path)
        before = target.read_bytes()
        context = SimpleNamespace(material=asset.resref, component_type="face")
        payload = {"context": context, "uv": (0.5, 0.5), "pressure": 1.0}

        window._begin_map_studio_texture_paint_stroke(payload)
        window._append_map_studio_texture_paint_sample(payload)
        window._commit_map_studio_texture_paint_stroke()

        assert target.read_bytes() != before
        assert region_updates
        assert all(width <= 64 and height <= 64 for update in region_updates for _x, _y, width, height in update)
        texture = window._project_texture_for_id(asset.texture_id)
        assert int(texture.metadata["paint_revision"]) == 1
        assert window.project.extra_sections["authored_module"]["texture_paint_dirty"] is True
        assert window.project.extra_sections["authored_module"]["texture_paint_unapplied"] is True
        assert window.project.extra_sections["authored_module"]["texture_paint_pending_resrefs"] == [asset.resref]
        assert window.texture_paint_tab.has_unapplied_changes() is True

        painted = target.read_bytes()
        window._begin_map_studio_texture_paint_stroke(payload)
        window._append_map_studio_texture_paint_sample(payload)
        assert session.stroke_active is True
        window.undo_map_studio_command()
        assert session.stroke_active is False
        assert target.read_bytes() == painted
        assert window.controller.command_history.undo_label.startswith("Texture Paint Stroke")

        window.texture_paint_tab.stop_painting()
        assert window.texture_paint_tab.paint_button.isChecked() is False
        assert session.can_undo is True
        texture_updates.clear()
        window.undo_map_studio_command()
        assert target.read_bytes() == before
        assert texture_updates
        restored_name, restored_image = texture_updates[-1]
        assert restored_name == asset.resref
        assert getattr(restored_image, "_gr_gpu_uv_v_flip") is False
        assert set(restored_image.get_flattened_data()) == {(20, 30, 40, 255)}
        texture_updates.clear()
        window.redo_map_studio_command()
        assert target.read_bytes() != before
        assert texture_updates and texture_updates[-1][0] == asset.resref
    finally:
        window.controller.project.dirty = False
        window.close()
        app.processEvents()


def test_map_studio_texture_paint_live_image_has_explicit_asymmetric_orientation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()

    import moderngl
    from PySide6 import QtWidgets

    monkeypatch.setattr(moderngl.VertexArray, "render", lambda self, *args, **kwargs: None)
    from src.core.modules.map_studio_texture_paint import encode_tga_rgba
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    # Top-down source rows: red/green, then blue/yellow.  The live renderer
    # image is deliberately bottom-up and marked as already converted.
    rgba = bytes(
        (
            255, 0, 0, 255,
            0, 255, 0, 255,
            0, 0, 255, 255,
            255, 255, 0, 255,
        )
    )
    source = tmp_path / "orientation.tga"
    source.write_bytes(encode_tga_rgba(2, 2, rgba))
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    try:
        window.controller.new_project(name="grorient", game="K2")
        window.controller.save_project(tmp_path / "grorient.kmap")
        asset = window.controller.import_project_texture(source, resref="orient_tex")
        window.texture_paint_tab.set_project(window.project)
        window._load_map_studio_texture_paint_session(asset.texture_id)
        image = window._texture_paint_view_image
        assert getattr(image, "_gr_gpu_uv_v_flip") is False
        assert tuple(image.get_flattened_data()) == (
            (0, 0, 255, 255),
            (255, 255, 0, 255),
            (255, 0, 0, 255),
            (0, 255, 0, 255),
        )
    finally:
        window.controller.project.dirty = False
        window.close()
        app.processEvents()


def test_placeable_library_asset_is_searchable_and_resolved_for_map_studio_export(
    tmp_path: Path,
) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()

    from PySide6 import QtWidgets

    from src.core.project.placeable_asset import PlaceableAsset, save_placeable_asset
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    library_root = tmp_path / "PlaceableLibrary"
    asset = PlaceableAsset(
        game="K2",
        template_resref="pb_crate",
        tag="pb_crate",
        display_name="Supply Crate",
        category="container",
        appearance_id=4,
    )
    save_placeable_asset(asset, library_root / "pb_crate.ghostplaceable.json")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    try:
        window.controller.new_project(name="grpbmap", game="K2")
        window.controller.create_dev_test_authored_module(module_root="grpbmap")
        payload = dict(window.project.extra_sections["authored_module"])
        placements = dict(payload.get("placements") or {})
        placements["placeables"] = [
            {
                "template_resref": "pb_crate",
                "tag": "pb_crate_instance",
                "position": [1.75, 1.5, 0.0],
                "bearing": 0.0,
            }
        ]
        payload["placements"] = placements
        window.project.extra_sections["authored_module"] = payload
        window.set_placeable_library_root(library_root)
        window.set_library_rows([])

        authored_row = next(row for row in window._library_rows if row.get("resref") == "pb_crate")
        assert authored_row["source"] == "placeable_builder"
        assert authored_row["restype"] == "utp"
        palette = window.controller.authored_gameplay_palette_entries(window._library_rows, kind="placeable")
        assert any(entry.template_resref == "pb_crate" for entry in palette)

        window._sync_placeable_library_resources_for_export()
        resources = window.controller.authored_project_extra_resources()
        assert any(resref == "pb_crate" and restype == "utp" for resref, restype, _data in resources)
    finally:
        window.controller.project.dirty = False
        window.close()
        app.processEvents()


def test_map_studio_ui_sync_bundles_non_core_utp_utd_and_scripts_into_mod(tmp_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from pykotor.common.misc import ResRef
    from pykotor.resource.generics.utd import UTD, bytes_utd
    from pykotor.resource.generics.utp import UTP, bytes_utp
    from src.core.project.resource_address import ResourceAddress
    from src.core.resources.game_resource_provider import (
        GameResourceRecord,
        InMemoryGameResourceProvider,
    )
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    def record(resref: str, restype: str, data: bytes):
        return (
            GameResourceRecord(
                address=ResourceAddress(
                    scheme="module_resource",
                    game="K2",
                    module_id="source_s",
                    resref=resref,
                    restype=restype,
                    layer="module",
                ),
                source="module:source_s.rim",
                priority=80,
                size=len(data),
            ),
            data,
        )

    terminal = UTP()
    terminal.resref = ResRef("plcaa_terminal")
    terminal.tag = "plcaa_terminal"
    terminal.appearance_id = 1
    terminal.on_used = ResRef("plcaa_term_use")
    door = UTD()
    door.resref = ResRef("plcaa_door")
    door.tag = "plcaa_door"
    door.appearance_id = 1
    door.on_open = ResRef("plcaa_door_open")
    provider = InMemoryGameResourceProvider(
        (
            record("plcaa_terminal", "UTP", bytes_utp(terminal)),
            record("plcaa_door", "UTD", bytes_utd(door)),
            record("plcaa_term_use", "NCS", b"terminal-script"),
            record("plcaa_door_open", "NCS", b"door-script"),
        )
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    try:
        window.controller.new_project(name="plcaa", game="K2")
        window.controller.create_dev_test_authored_module(module_root="plcaa")
        payload = dict(window.project.extra_sections["authored_module"])
        placements = dict(payload.get("placements") or {})
        placements["placeables"] = [
            {"template_resref": "plcaa_terminal", "tag": "plcaa_terminal", "position": [1.0, 1.0, 0.0]}
        ]
        placements["doors"] = [
            {"template_resref": "plcaa_door", "tag": "plcaa_door", "position": [2.0, 1.0, 0.0]}
        ]
        payload["placements"] = placements
        window.project.extra_sections["authored_module"] = payload
        window.set_placeable_library_root("", provider=provider)

        window._sync_placeable_library_resources_for_export()
        result = window.controller.export_authored_module(tmp_path / "plcaa_export")

        keys = {(item.resref, item.restype) for item in result.package_verification.resources}
        assert {
            ("plcaa_terminal", "utp"),
            ("plcaa_door", "utd"),
            ("plcaa_term_use", "ncs"),
            ("plcaa_door_open", "ncs"),
        } <= keys
        assert not any(
            str(getattr(issue, "severity", "")).lower() == "blocking"
            for issue in window.controller.authored_placeable_resource_issues()
        )
    finally:
        window.controller.project.dirty = False
        window.close()
        app.processEvents()


def test_map_studio_terrain_release_keeps_resident_mesh_and_defers_wok_validation() -> None:
    _install_native_payload_paths()
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    calls: dict[str, object] = {}

    class Controller:
        def commit_map_studio_terrain_sculpt_stroke(self, **kwargs):
            calls["commit"] = dict(kwargs)
            return SimpleNamespace(frame_count=1)

        def authored_terrain_walkability_overlay(self):
            raise AssertionError("terrain mouse release must not serialize a WOK overlay synchronously")

    target = SimpleNamespace(
        controller=Controller(),
        viewport_panel=SimpleNamespace(
            set_terrain_walkability_overlay=lambda value: calls.setdefault("overlay", value),
        ),
        _refresh_map_studio_geometry_change=lambda message, **kwargs: calls.setdefault(
            "refresh", (message, dict(kwargs))
        ),
        _sync_map_studio_terrain_brush_context=lambda: calls.setdefault("context_synced", True),
        _log=lambda message: calls.setdefault("log", message),
    )

    ModuleEditorWindow.commit_map_studio_viewport_terrain_brush_stroke(
        target,
        "raise",
        "grresident_terrain",
    )

    assert calls["commit"] == {"brush": "raise", "room_resref": "grresident_terrain"}
    assert calls["overlay"] is None
    message, refresh_kwargs = calls["refresh"]
    assert "background" in message
    assert refresh_kwargs == {
        "rebuild_viewport_model": False,
        "refresh_scene_tree": False,
        "validation_delay_ms": 250,
    }
    assert calls["context_synced"] is True
    assert target._last_map_studio_terrain_release_ms >= 0.0


def test_map_studio_live_terrain_stroke_redoes_the_same_kmap_heights() -> None:
    _install_native_payload_paths()
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grterrainredo", game="K1")
    room_resref = controller.create_terrain_patch(resolution=9)
    before = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    ).rooms[0].primitive.heights
    controller.apply_map_studio_terrain_sculpt_frame(
        room_resref=room_resref,
        brush="raise",
        points=((4, 4, 1.0),),
        delta=0.5,
        radius=2,
        force=True,
    )
    controller.commit_map_studio_terrain_sculpt_stroke(
        brush="raise",
        room_resref=room_resref,
    )
    after = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    ).rooms[0].primitive.heights
    assert after != before

    assert controller.undo_map_studio_command() is not None
    assert authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    ).rooms[0].primitive.heights == before
    assert controller.redo_map_studio_command() is not None
    assert authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    ).rooms[0].primitive.heights == after


def test_map_studio_terrain_sculpt_workspace_is_viewport_local_and_kotor_safe() -> None:
    """The terrain UX exposes paint-mode gestures without promising unsupported runtime terrain."""

    shelf_sources = (
        _read("native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/terrain_sculpt_shelf.py"),
        _read("native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/terrain_sculpt_shelf.py"),
    )
    viewport_sources = (
        _read("native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"),
        _read("native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"),
    )
    window_source = _read("native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py")
    overlay_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/overlay_layers.py"
    )
    rendering_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/rendering_pipeline.py"
    )
    navigation_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/event_navigation.py"
    )

    for source in shelf_sources:
        assert "class TerrainSculptShelf" in source
        assert "mapStudioTerrainSculptShelf" in source
        assert "mapStudioTerrainSlopeOverlayCheckBox" in source
        assert "Shift+wheel resize" in source
        assert "RMB orbit" in source
        assert "Alt+MMB pan" in source
        assert "KOTOR-safe static heightfield" in source
        for brush in ("raise", "lower", "smooth", "flatten", "plateau", "ramp", "terrace", "erode", "noise"):
            assert f'(\"{brush}\",' in source

    for source in viewport_sources:
        assert "TerrainSculptShelf" in source
        assert "terrainBrushSelected = QtCore.Signal(str)" in source
        assert "def _resize_terrain_brush_from_wheel" in source
        assert "def _begin_terrain_camera_drag" in source
        assert 'navigation="pan"' in source
        assert "camera.pan(dx, dy, viewport_height)" in source
        assert "def _set_terrain_camera_top" in source
        assert "def _set_terrain_camera_angled" in source
        assert 'set_selected(None, source="terrain sculpt")' in source
        assert 'set_selected(previous, source="terrain sculpt exit")' in source
        assert "ShiftModifier" in source
        assert 'brush = "lower"' in source
        assert "terrain_sculpt_shelf.walkability_box.isChecked()" in source
        assert "set_map_studio_terrain_sculpt_input_lock" in source

    assert "terrainBrushSelected.connect(self._select_map_studio_terrain_brush)" in window_source
    assert "terrainSculptModeChanged.connect(self._set_map_studio_terrain_sculpt_enabled)" in window_source
    assert "strength=float(context.get" in window_source
    assert "delta=float(context.get" in window_source
    assert "inner_radius = max(4.0, radius * hardness)" in overlay_source
    # All editor feedback shares one disposable layer.  This prevents brushes,
    # placement ghosts, selections, gizmos, and future kit previews from being
    # painted into a renderer-owned frame that a retained backend may reuse.
    gpu_overlay_source = rendering_source[
        rendering_source.index("def _draw_gpu_viewport_overlays") :
        rendering_source.index("def _draw_renderer_statistics_overlay")
    ]
    assert 'overlay_img = Image.new("RGBA", scene_img.size, (0, 0, 0, 0))' in gpu_overlay_source
    assert 'draw = ImageDraw.Draw(overlay_img, "RGBA")' in gpu_overlay_source
    assert "return Image.alpha_composite(scene_img, overlay_img)" in gpu_overlay_source
    assert "ImageDraw.Draw(scene_img" not in gpu_overlay_source
    # The protection is deliberately asset-agnostic: every current editor
    # visual is routed through the same disposable compositor.  New room or
    # terrain assets therefore cannot opt out and paint into a retained frame.
    for transient_overlay in (
        "_draw_map_studio_terrain_brush_cursor",
        "_draw_map_studio_texture_paint_cursor",
        "_draw_map_studio_building_preview",
        "_draw_map_studio_universal_transform_overlay",
        "_draw_map_studio_placement_markers",
        "_draw_map_studio_terrain_walkability",
        "_draw_map_studio_component_selection",
        "_draw_map_studio_hover_highlight",
        "_draw_wgpu_helper_markers",
        "_draw_transform_gizmo",
        "_draw_selected_model_outline",
        "_draw_mesh_subobject_selection",
        "_draw_measurement_overlay",
        "_draw_active_camera_overlays",
    ):
        assert f"self.{transient_overlay}" in gpu_overlay_source
    assert "def _consume_map_studio_terrain_navigation_event" in navigation_source
    assert "QtCore.Qt.LeftButton | QtCore.Qt.MiddleButton | QtCore.Qt.RightButton" in navigation_source
    cursor_source = overlay_source[
        overlay_source.index("def _draw_map_studio_terrain_brush_cursor") :
        overlay_source.index("def _draw_map_studio_texture_paint_cursor")
    ]
    assert "room_resref" not in cursor_source
    assert "[{int(sample" not in cursor_source


def test_t2907_direct_building_replaces_primary_room_wall_of_controls() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.gui.panels.module_editor.builder_tab import BuilderTab

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    builder = BuilderTab()
    try:
        assert builder.findChild(QtWidgets.QGroupBox, "mapStudioDirectBuildingGroup") is not None
        assert builder._roomAdvancedContainer.isAncestorOf(builder.componentModeComboBox)
        assert builder._roomAdvancedContainer.isAncestorOf(builder.roomPrimitivePresetComboBox)
        assert builder._roomPrimaryContainer.isAncestorOf(builder.buildingToolButtons["walls"])
        assert builder.roomAdvancedToggle.isChecked() is False

        tools: list[str] = []
        settings: list[dict[str, object]] = []
        level_requests: list[dict[str, object]] = []
        level_views: list[dict[str, object]] = []
        builder.buildingToolChanged.connect(tools.append)
        builder.buildingSettingsChanged.connect(lambda value: settings.append(dict(value)))
        builder.buildingLevelCreateRequested.connect(lambda value: level_requests.append(dict(value)))
        builder.buildingLevelViewChanged.connect(lambda value: level_views.append(dict(value)))
        builder.buildingToolButtons["walls"].click()
        builder.buildingWallHeightSpinBox.setValue(3.5)
        builder.buildingFloorToFloorSpinBox.setValue(3.5)
        builder.addBuildingLevelButton.click()
        assert level_requests == [
            {
                "level_index": 1,
                "name": "Level 2",
                "floor_z": 3.5,
                "floor_to_floor_height": 3.5,
            }
        ]
        builder.set_building_levels(
            (
                SimpleNamespace(level_index=0, name="Level 1", floor_z=0.0, floor_to_floor_height=3.5, room_resrefs=()),
                SimpleNamespace(level_index=1, name="Level 2", floor_z=3.5, floor_to_floor_height=3.5, room_resrefs=()),
            )
        )
        builder.select_building_level(1)

        assert tools == ["walls"]
        assert settings[-1]["level_index"] == 1
        assert settings[-1]["floor_z"] == 3.5
        assert settings[-1]["wall_height"] == 3.5
        assert settings[-1]["opening_height"] == 2.2
        assert settings[-1]["window_height"] == 1.2
        assert settings[-1]["building_kind"] == "interior"
        assert settings[-1]["roof_type"] == "none"
        assert settings[-1]["style_id"] == "plcaa_graybox"
        assert settings[-1]["floor_to_floor_height"] == 3.5

        exploded_index = builder.buildingLevelViewComboBox.findData("exploded")
        builder.buildingLevelViewComboBox.setCurrentIndex(exploded_index)
        assert level_views[-1]["mode"] == "exploded"
        builder.buildingToolButtons["select"].click()
        builder.buildingToolButtons["walls"].click()
        assert builder.buildingLevelViewComboBox.currentData() == "solo"
        assert level_views[-1]["active_level_index"] == 1

        exterior_index = builder.buildingKindComboBox.findData("exterior")
        builder.buildingKindComboBox.setCurrentIndex(exterior_index)
        assert builder._building_settings()["building_kind"] == "exterior"
        assert builder._building_settings()["roof_type"] == "hip"
        assert builder._building_settings()["roof_pitch_degrees"] == 30.0
        assert builder._building_settings()["roof_overhang"] == 0.25
    finally:
        builder.close()
        app.processEvents()


def test_t2907_direct_building_uses_level_plane_snap_and_universal_transient_overlay() -> None:
    viewport_sources = (
        _read("native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"),
        _read("native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"),
    )
    overlay_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/overlay_layers.py"
    )
    rendering_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/rendering_pipeline.py"
    )
    window_source = _read("native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py")

    for source in viewport_sources:
        for token in (
            "buildingRoomRequested = QtCore.Signal(object)",
            "buildingOpeningRequested = QtCore.Signal(object)",
            "buildingOpeningPreviewRequested = QtCore.Signal(object)",
            "def set_pascal_building_level_presentation",
            "def set_pascal_building_tool",
            "def set_pascal_building_opening_preview",
            "def _building_world_at_event",
            "def _building_wall_snap_from_geometry",
            "def _building_wall_point_at_event",
            "def _room_outline_edge_from_current_geometry",
            '"window_height" if kind == "window" else "opening_height"',
            "ray_from_mouse",
            "snap_to_grid",
            "Click the first corner to close",
            "Shift-click adds, Alt-click removes",
            "Key_Backspace",
            "Key_Escape",
        ):
            assert token in source
    assert "def _draw_map_studio_building_preview" in overlay_source
    assert "def _map_studio_level_room_presentation" in overlay_source
    assert 'mode == "solo"' in overlay_source
    assert 'mode == "exploded"' in overlay_source
    compositor = rendering_source[
        rendering_source.index("def _draw_gpu_viewport_overlays") :
        rendering_source.index("def _draw_renderer_statistics_overlay")
    ]
    assert "self._draw_map_studio_building_preview(draw, w, h)" in compositor
    assert "return Image.alpha_composite(scene_img, overlay_img)" in compositor
    assert "buildingRoomRequested.connect(self._build_map_studio_room_from_viewport)" in window_source
    assert "buildingOpeningPreviewRequested.connect(" in window_source
    assert "def _preview_map_studio_opening_from_viewport" in window_source
    assert "buildingOpeningRequested.connect(self._build_map_studio_opening_from_viewport)" in window_source
    assert "buildingLevelCreateRequested.connect(self._add_map_studio_building_level)" in window_source
    assert "buildingLevelViewChanged.connect(self._apply_map_studio_level_presentation)" in window_source
    assert "mapStudioOutlinerDeleteSelectionShortcut" in window_source
    assert 'preserve_multi_delete = action == "delete"' in window_source
    assert "Click to place" in overlay_source
    assert 'snap_label = str(preview.get("snap_label") or "")' in overlay_source
    assert "multi_opening_fill" in _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/authored_room_floorplan.py"
    )
    floorplan_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/authored_room_floorplan.py"
    )
    assert "def build_floor_plan_roof_meshes" in floorplan_source
    assert '"Gable roofs currently require a rectangular room footprint."' in floorplan_source
    graph_source = _read(
        "native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_pascal_graph.py"
    )
    assert "def planarize_pascal_building_rooms" in graph_source
    assert '"junction_vertex_ids"' in graph_source
