from __future__ import annotations

import math
import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Modules/Python",
        "native/GhostRigger.Core.Level/Python",
        "native/GhostRigger.Core.Game/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Walkmesh/Python",
        "native/GhostRigger.Core.Geometry/Python",
        "native/GhostRigger.Core.Camera/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Lighting/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2657_preview_markers_describe_spatial_gameplay_placements() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_gameplay_preview import authored_gameplay_preview_markers
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grmark01",
        game="K1",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="creature",
        template_resref="c_drdmkone",
        tag="grmark_guard",
        position=(1.0, 2.0, 0.0),
        bearing=math.pi / 2.0,
    ).project
    project = add_authored_gameplay_placement(
        project,
        kind="placeable",
        template_resref="plc_bench",
        tag="grmark_bench",
        position=(-1.0, 0.5, 0.0),
    ).project
    project = add_authored_gameplay_placement(
        project,
        kind="store",
        template_resref="stm_shop",
        tag="grmark_store",
    ).project

    markers = authored_gameplay_preview_markers(project)
    by_id = {marker.placement_id: marker for marker in markers}

    assert {"authored:creature:0", "authored:placeable:0", "authored:placeable:1", "authored:waypoint:0"} == set(by_id)
    assert by_id["authored:creature:0"].shape == "diamond"
    assert by_id["authored:placeable:1"].shape == "cube"
    assert by_id["authored:creature:0"].color == "#ff5c5c"
    assert by_id["authored:creature:0"].forward_endpoint[1] > by_id["authored:creature:0"].position[1]
    assert by_id["authored:creature:0"].metadata["runtime_kind"] == "creature"


def test_t2657_controller_exposes_authored_gameplay_preview_markers() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    assert controller.authored_gameplay_preview_markers() == ()

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grctlmk")
    controller.add_authored_gameplay_placement(
        kind="door",
        template_resref="door_t01",
        tag="grctlmk_door",
        position=(0.0, 3.0, 0.0),
        bearing=0.5,
    )

    markers = controller.authored_gameplay_preview_markers()

    assert len(markers) == 3
    assert {marker.kind for marker in markers} == {"placeable", "door", "waypoint"}
    assert any(marker.shape == "doorway" and marker.label == "grctlmk_door" for marker in markers)


def test_t2657_module_editor_uses_marker_contract_in_viewport_panel() -> None:
    repo = Path(__file__).resolve().parents[1]
    viewport_source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Panels"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "module_editor_viewport_panel.py"
    ).read_text(encoding="utf-8")
    window_source = (
        repo
        / "native"
        / "GhostRigger.Windows.Editor.Level"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")
    controller_source = (
        repo
        / "native"
        / "GhostRigger.Core.Modules"
        / "Python"
        / "src"
        / "core"
        / "modules"
        / "module_editor_controller.py"
    ).read_text(encoding="utf-8")

    assert "mapStudioPlacementMarkerSummaryLabel" in viewport_source
    assert "authored_gameplay_markers" in viewport_source
    assert '"Marker"' in viewport_source
    assert '"Facing"' in viewport_source
    assert "marker.shape" in viewport_source or 'getattr(marker, "shape"' in viewport_source
    assert "self.controller.authored_gameplay_preview_markers()" in window_source
    assert "authored_marker_geometry = self.controller.authored_gameplay_marker_geometry()" in window_source
    assert "self.viewport_panel.set_project(self.project, authored_placements, authored_markers, authored_marker_geometry)" in window_source
    assert "authored_gameplay_preview_markers" in controller_source
