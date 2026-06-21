from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2664_doorway_room_outline_includes_floor_ceiling_walls_and_opening_guides() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_outline_geometry import authored_room_outline_geometry_for_project
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="doorway_blockout",
        module_root="grdoorol",
        game="K1",
    )
    geometry = authored_room_outline_geometry_for_project(project)

    floor = next(polygon for polygon in geometry.polygons if polygon.role == "floor")
    ceiling = next(polygon for polygon in geometry.polygons if polygon.role == "ceiling")
    wall_guides = [line for line in geometry.lines if line.role == "wall_height"]
    opening_guides = [line for line in geometry.lines if line.role == "opening"]

    assert geometry.room_count == 1
    assert geometry.warnings == ()
    assert floor.room_resref == "grdoorol_room01"
    assert floor.color == "#52ff7a"
    assert len(floor.points) == 4
    assert len(ceiling.points) == len(floor.points)
    assert all(top[2] > bottom[2] for bottom, top in zip(floor.points, ceiling.points))
    assert len(wall_guides) == len(floor.points)
    assert opening_guides
    assert any(line.label == "south_doorway" for line in opening_guides)


def test_t2664_controller_exposes_empty_and_authored_room_outline_geometry() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")

    empty = controller.authored_room_outline_geometry()
    assert empty.room_count == 0
    assert empty.polygons == ()
    assert empty.lines == ()

    controller.create_authored_room_preset_module(preset_id="octagonal_room", module_root="groctl")
    geometry = controller.authored_room_outline_geometry()

    assert geometry.room_count == 1
    assert len([polygon for polygon in geometry.polygons if polygon.role == "floor"]) == 1
    assert len([polygon for polygon in geometry.polygons if polygon.role == "ceiling"]) == 1
    assert len([line for line in geometry.lines if line.role == "wall_height"]) == 8


def test_t2669_elevation_composition_outline_includes_walkable_primitive_guides() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_outline_geometry import authored_room_outline_geometry_for_project
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="elevation_test_room",
        module_root="grelevol",
        game="K1",
    )
    geometry = authored_room_outline_geometry_for_project(project)

    floor = next(polygon for polygon in geometry.polygons if polygon.role == "floor")
    ceiling = next(polygon for polygon in geometry.polygons if polygon.role == "ceiling")
    wall_guides = [line for line in geometry.lines if line.role == "wall_height"]
    walkable_guides = [polygon for polygon in geometry.polygons if polygon.role == "walkmesh_primitive"]

    assert geometry.room_count == 1
    assert geometry.warnings == ()
    assert floor.room_resref == "grelevol_room01"
    assert floor.color == "#7cffa8"
    assert len(floor.points) == 4
    assert len(ceiling.points) == len(floor.points)
    assert len(wall_guides) == len(floor.points)
    assert len(walkable_guides) == 4
    assert any(point[2] > 0.0 for polygon in walkable_guides for point in polygon.points)


def test_t2677_elevation_composition_outline_exposes_draggable_primitive_handles() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_outline_geometry import authored_room_outline_geometry_for_project
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="elevation_test_room",
        module_root="grhandle",
        game="K1",
    )
    geometry = authored_room_outline_geometry_for_project(project)
    handles = {handle.primitive_name: handle for handle in geometry.primitive_handles}

    assert len(handles) >= 7
    assert "grhandle_room01_ramp" in handles
    assert handles["grhandle_room01_ramp"].room_resref == "grhandle_room01"
    assert handles["grhandle_room01_ramp"].primitive_type == "ramp"
    assert len(handles["grhandle_room01_ramp"].footprint) == 4
    assert handles["grhandle_room01_ramp"].center[0] < 0.0


def test_t2664_rectangular_cut_outline_tracks_split_authored_rooms() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_operations import apply_authored_floor_plan_operation
    from src.core.modules.authored_room_outline_geometry import authored_room_outline_geometry_for_project
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grcutol",
        game="K1",
    )
    cut = apply_authored_floor_plan_operation(
        project,
        "rectangular_cut",
        center=(0.0, 0.0),
        size=(2.0, 1.0),
        room_resref_prefix="grcutpiece",
    )
    geometry = authored_room_outline_geometry_for_project(cut)

    floor_polygons = [polygon for polygon in geometry.polygons if polygon.role == "floor"]
    assert geometry.room_count == 4
    assert len(floor_polygons) == 4
    assert {room.metadata["cut_piece_role"] for room in cut.rooms} == {"left", "right", "bottom", "top"}
    assert all(polygon.room_resref.startswith("grcutpiece_") for polygon in floor_polygons)
