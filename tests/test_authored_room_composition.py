from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Domain.Core.Modules/Python",
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


def test_t2603_rectangular_room_composition_compiles_to_floor_walls_and_wok() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import (
        compile_authored_room_composition,
        create_rectangular_room_composition,
        validate_authored_room_composition,
    )
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive

    composition = create_rectangular_room_composition(
        RectangularRoomPrimitive(
            room_resref="grdev01_room01",
            width=10.0,
            depth=8.0,
            wall_height=3.25,
            floor_surface_id=4,
            texture="metal_floor",
            include_doorway_marker=True,
        )
    )

    validation = validate_authored_room_composition(composition)
    geometry = compile_authored_room_composition(composition)

    assert validation.ok is True
    assert geometry.room_resref == "grdev01_room01"
    assert geometry.room_mesh.name == "grdev01_room01_mesh"
    assert geometry.room_mesh.texture == "metal_floor"
    assert geometry.room_mesh.metadata["primitive"] == "floor"
    assert geometry.wok.walkable_face_count() == 2
    assert geometry.metadata["primitive"] == "authored_room_composition"
    assert geometry.metadata["primitive_count"] == 4
    assert geometry.metadata["compiled_mesh_count"] == 6
    helper_names = {mesh.name for mesh in geometry.helper_meshes}
    assert {
        "grdev01_room01_wall_n",
        "grdev01_room01_wall_s",
        "grdev01_room01_wall_e",
        "grdev01_room01_wall_w",
        "grdev01_room01_door_marker",
    } <= helper_names


def test_t2603_composition_validation_rejects_duplicate_primitive_names() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import AuthoredRoomComposition, validate_authored_room_composition
    from src.core.modules.authored_room_primitives import FloorPrimitive, WallPrimitive

    composition = AuthoredRoomComposition(
        room_resref="badroom",
        floor=FloorPrimitive(name="duplicate"),
        primitives=(WallPrimitive(name="duplicate"),),
    )

    validation = validate_authored_room_composition(composition)

    assert validation.ok is False
    assert "Duplicate authored room primitive name: duplicate" in validation.blocking_issues


def test_t2604_composition_validation_rejects_non_walk_floor_surface() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import AuthoredRoomComposition, validate_authored_room_composition
    from src.core.modules.authored_room_primitives import FloorPrimitive

    composition = AuthoredRoomComposition(
        room_resref="blocked",
        floor=FloorPrimitive(name="blocked_floor", surface_id="non_walk"),
    )

    validation = validate_authored_room_composition(composition)

    assert validation.ok is False
    assert "blocked floor surface 7 (NON_WALK) is not walkable." in validation.blocking_issues
