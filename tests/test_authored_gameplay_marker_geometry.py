from __future__ import annotations

import math
import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Domain.Core.Modules/Python",
        "native/GhostRigger.Domain.Core.Level/Python",
        "native/GhostRigger.Domain.Core.Game/Python",
        "native/GhostRigger.Domain.Core.Scene/Python",
        "native/GhostRigger.Domain.Core.Walkmesh/Python",
        "native/GhostRigger.Domain.Core.Geometry/Python",
        "native/GhostRigger.Domain.Core.Camera/Python",
        "native/GhostRigger.Domain.Core.Math/Python",
        "native/GhostRigger.Domain.Core.Lighting/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2659_marker_geometry_adds_footprints_facing_and_height_guides() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_gameplay_marker_geometry import authored_gameplay_marker_geometry
    from src.core.modules.authored_gameplay_preview import authored_gameplay_preview_markers
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grgeo01",
        game="K1",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="creature",
        template_resref="c_drdmkone",
        tag="grgeo_guard",
        position=(1.0, 2.0, 0.25),
        bearing=math.pi / 2.0,
    ).project
    project = add_authored_gameplay_placement(
        project,
        kind="trigger",
        template_resref="trg_test",
        tag="grgeo_trigger",
        position=(0.0, 0.0, 0.0),
    ).project

    markers = authored_gameplay_preview_markers(project)
    geometry = authored_gameplay_marker_geometry(markers)
    creature_marker = next(marker for marker in markers if marker.placement_id == "authored:creature:0")
    creature_footprint = next(footprint for footprint in geometry.footprints if footprint.placement_id == "authored:creature:0")
    creature_facing = next(line for line in geometry.lines if line.placement_id == "authored:creature:0" and line.role == "facing")
    creature_height = next(line for line in geometry.lines if line.placement_id == "authored:creature:0" and line.role == "height")

    assert geometry.marker_count == len(markers)
    assert len(creature_footprint.points) == 4
    assert creature_footprint.color == creature_marker.color
    assert creature_facing.start == creature_marker.position
    assert creature_facing.end == creature_marker.forward_endpoint
    assert creature_height.end[2] > creature_height.start[2]
    assert any("approximate volume" in warning for warning in geometry.warnings)


def test_t2659_controller_exposes_empty_and_authored_marker_geometry() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    empty_geometry = controller.authored_gameplay_marker_geometry()

    assert empty_geometry.marker_count == 0
    assert empty_geometry.lines == ()
    assert empty_geometry.footprints == ()

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grgeoctl")
    controller.add_authored_gameplay_placement(
        kind="door",
        template_resref="door_t01",
        tag="grgeoctl_door",
        position=(0.0, 3.0, 0.0),
        bearing=0.5,
    )
    geometry = controller.authored_gameplay_marker_geometry()

    assert geometry.marker_count == 3
    assert len(geometry.footprints) == 3
    assert len([line for line in geometry.lines if line.role == "facing"]) == 3
    assert any(line.role == "height" for line in geometry.lines)


def test_t2659_module_editor_passes_marker_geometry_to_viewport_panel() -> None:
    repo = Path(__file__).resolve().parents[1]
    viewport_source = (
        repo
        / "native"
        / "GhostRigger.GUI.Boundary.Panels"
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
        / "GhostRigger.Domain.Core.Modules"
        / "Python"
        / "src"
        / "core"
        / "modules"
        / "module_editor_controller.py"
    ).read_text(encoding="utf-8")

    assert "authored_gameplay_marker_geometry" in controller_source
    assert "authored_marker_geometry = self.controller.authored_gameplay_marker_geometry()" in window_source
    assert "authored_marker_geometry" in window_source
    assert "authored_gameplay_marker_geometry" in viewport_source
    assert "footprint(s)" in viewport_source
    assert "guide line(s)" in viewport_source
