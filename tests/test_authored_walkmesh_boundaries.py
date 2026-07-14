from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
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


def test_t2704_authored_walkmesh_boundary_walls_are_added_without_mutating_source() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive, build_rectangular_room_wok
    from src.core.modules.authored_walkmesh_boundaries import add_authored_walkmesh_boundary_walls

    source = build_rectangular_room_wok(RectangularRoomPrimitive(room_resref="grdev01_room01"))
    faces_before = len(source.faces)
    non_walk_before = source.non_walk_face_count()
    walkable_before = source.walkable_face_count()

    result = add_authored_walkmesh_boundary_walls(source, wall_height=2.75)

    # The source WOK is never mutated; walls are added on the copy, one quad
    # (two faces) per boundary edge, all non-walk.
    assert len(source.faces) == faces_before
    assert source.non_walk_face_count() == non_walk_before
    assert result.enabled is True
    assert result.wall_height == 2.75
    assert result.source_boundary_edge_count > 0
    assert result.added_face_count == result.source_boundary_edge_count * 2
    assert result.non_walk_face_count == result.added_face_count
    assert result.wok.walkable_face_count() == walkable_before
    assert result.wok.non_walk_face_count() == non_walk_before + result.added_face_count
    assert result.metadata["source"] == "src.core.modules.authored_walkmesh_boundaries"
    assert result.metadata["added_face_count"] == result.added_face_count


def test_t2704_boundary_policy_can_be_disabled_for_floor_only_authoring() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive, build_rectangular_room_wok
    from src.core.modules.authored_walkmesh_boundaries import add_authored_walkmesh_boundary_walls

    source = build_rectangular_room_wok(RectangularRoomPrimitive(room_resref="grdev01_room01"))
    result = add_authored_walkmesh_boundary_walls(source, enabled=False)

    assert result.enabled is False
    assert result.wok is source
    assert result.added_face_count == 0
    assert result.non_walk_face_count == 0
