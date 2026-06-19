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
    assert "mapStudioWorkflowResourcesLabel" in panel_source
    assert "mapStudioWorkflowMissingResourcesLabel" in panel_source
    assert "mapStudioWorkflowGeometryLabel" in panel_source
    assert "mapStudioWorkflowWalkmeshLabel" in panel_source
    assert "mapStudioWorkflowLayoutLabel" in panel_source
    assert "mapStudioWorkflowValidationLabel" in panel_source
    assert "mapStudioWorkflowExportLabel" in panel_source
    assert "mapStudioWorkflowProofLabel" in panel_source
    assert "mapStudioWorkflowOpenBuilderButton" in panel_source
    assert "mapStudioWorkflowStarterRoomButton" in panel_source
    assert "mapStudioWorkflowDoorwayBlockoutButton" in panel_source
    assert "mapStudioWorkflowCorridorButton" in panel_source
    assert "mapStudioWorkflowStarterTerrainButton" in panel_source
    assert "mapStudioWorkflowPlacementToolsButton" in panel_source
    assert "mapStudioWorkflowTestPlaceableButton" in panel_source
    assert "mapStudioWorkflowWalkmeshToolsButton" in panel_source
    assert "mapStudioWorkflowValidateButton" in panel_source
    assert "mapStudioWorkflowStageButton" in panel_source
    assert "mapStudioWorkflowInstallButton" in panel_source
    assert "mapStudioWorkflowLaunchHandoffButton" in panel_source
    assert "mapStudioWorkflowProofButton" in panel_source
    assert "builderRequested = QtCore.Signal()" in panel_source
    assert "starterRoomRequested = QtCore.Signal()" in panel_source
    assert "doorwayBlockoutRequested = QtCore.Signal()" in panel_source
    assert "corridorRequested = QtCore.Signal()" in panel_source
    assert "starterTerrainRequested = QtCore.Signal()" in panel_source
    assert "placementToolsRequested = QtCore.Signal()" in panel_source
    assert "testPlaceableRequested = QtCore.Signal()" in panel_source
    assert "walkmeshToolsRequested = QtCore.Signal()" in panel_source
    assert "validateRequested = QtCore.Signal()" in panel_source
    assert "stageRequested = QtCore.Signal()" in panel_source
    assert "installRequested = QtCore.Signal()" in panel_source
    assert "launchHandoffRequested = QtCore.Signal()" in panel_source
    assert "proofRequested = QtCore.Signal()" in panel_source
    assert "Create Starter Room" in panel_source
    assert "Create Doorway Blockout" in panel_source
    assert "Create Corridor" in panel_source
    assert "Create Terrain Patch" in panel_source
    assert "Open Placement Tools" in panel_source
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
    assert "Spawn/layout:" in panel_source
    assert "Gameplay layout" in panel_source
    assert "player start" in panel_source
    assert "Use Builder to create terrain, rooms, or a dev-test map" in panel_source
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
    assert "self.workflow_panel.builderRequested.connect(self.show_map_studio_builder)" in window_source
    assert "self.workflow_panel.starterRoomRequested.connect(self.create_map_studio_starter_room)" in window_source
    assert "self.workflow_panel.doorwayBlockoutRequested.connect(self.create_map_studio_doorway_blockout)" in window_source
    assert "self.workflow_panel.corridorRequested.connect(self.create_map_studio_corridor)" in window_source
    assert "self.workflow_panel.starterTerrainRequested.connect(self.create_map_studio_starter_terrain)" in window_source
    assert "self.workflow_panel.placementToolsRequested.connect(self.show_map_studio_placement_tools)" in window_source
    assert "self.workflow_panel.testPlaceableRequested.connect(self.add_map_studio_test_placeable)" in window_source
    assert "self.workflow_panel.walkmeshToolsRequested.connect(self.show_map_studio_walkmesh_tools)" in window_source
    assert "self.workflow_panel.validateRequested.connect(self.validate_kmap)" in window_source
    assert "self.workflow_panel.stageRequested.connect(lambda: self.stage_authored_module" in window_source
    assert "self.workflow_panel.installRequested.connect(lambda: self.install_authored_module" in window_source
    assert "self.workflow_panel.launchHandoffRequested.connect(self.open_map_studio_launch_handoff)" in window_source
    assert "self.workflow_panel.proofRequested.connect(self.record_game_smoke_proof)" in window_source
    assert "def show_map_studio_builder" in window_source
    assert "def create_map_studio_starter_room" in window_source
    assert "preset_id=\"rectangular_dev_room\"" in window_source
    assert "def create_map_studio_doorway_blockout" in window_source
    assert "preset_id=\"doorway_blockout\"" in window_source
    assert "def create_map_studio_corridor" in window_source
    assert "preset_id=\"wide_hall\"" in window_source
    assert "def create_map_studio_starter_terrain" in window_source
    assert "preset_id=\"terrain_heightfield\"" in window_source
    assert "def show_map_studio_placement_tools" in window_source
    assert "gameplayPaletteSearchLineEdit" in window_source
    assert "def show_map_studio_walkmesh_tools" in window_source
    assert "self.workflow_tabs.setCurrentWidget(self.walkmesh_tab)" in window_source
    assert "def add_map_studio_test_placeable" in window_source
    assert '"plc_bench"' in window_source
    assert "self.workflow_tabs.setCurrentWidget(self.builder_tab)" in window_source
    assert "MapStudioWorkflowPanel" in init_source


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
    assert "mapStudioWorkflowMissingResourcesLabel" in mirror_source
    assert "mapStudioWorkflowGeometryLabel" in mirror_source
    assert "mapStudioWorkflowWalkmeshLabel" in mirror_source
    assert "mapStudioWorkflowLayoutLabel" in mirror_source
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
    assert "Gameplay layout" in mirror_source
    assert "MapStudioWorkflowPanel" in mirror_init
