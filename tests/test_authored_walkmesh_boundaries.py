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


def test_t2704_authored_walkmesh_boundary_walls_are_editor_only_and_game_wok_stays_floor_only() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive, build_rectangular_room_wok
    from src.core.modules.authored_walkmesh_boundaries import add_authored_walkmesh_boundary_walls

    source = build_rectangular_room_wok(RectangularRoomPrimitive(room_resref="grdev01_room01"))
    faces_before = len(source.faces)
    non_walk_before = source.non_walk_face_count()
    walkable_before = source.walkable_face_count()

    result = add_authored_walkmesh_boundary_walls(source, wall_height=2.75)

    # The source/external WOK is never mutated. One two-triangle helper quad is
    # reported per perimeter edge, but those vertical faces stay out of the
    # game-facing WOK.
    assert len(source.faces) == faces_before
    assert source.non_walk_face_count() == non_walk_before
    assert result.wok is source
    assert result.enabled is True
    assert result.wall_height == 2.75
    assert result.source_boundary_edge_count > 0
    assert result.helper_segment_count == result.source_boundary_edge_count
    assert result.helper_face_count == result.source_boundary_edge_count * 2
    assert result.added_vertex_count == 0
    assert result.added_face_count == 0
    assert result.non_walk_face_count == non_walk_before
    assert result.wok.walkable_face_count() == walkable_before
    assert result.wok.non_walk_face_count() == non_walk_before
    assert len(result.wok.faces) == faces_before
    assert result.metadata["source"] == "src.core.modules.authored_walkmesh_boundaries"
    assert result.metadata["editor_helper_face_count"] == result.helper_face_count
    assert result.metadata["added_face_count"] == 0
    assert result.metadata["game_wok_face_policy"] == "floor_only"
    assert result.metadata["game_wok_mutated"] is False


def test_t2704_boundary_policy_can_be_disabled_for_floor_only_authoring() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive, build_rectangular_room_wok
    from src.core.modules.authored_walkmesh_boundaries import add_authored_walkmesh_boundary_walls

    source = build_rectangular_room_wok(RectangularRoomPrimitive(room_resref="grdev01_room01"))
    result = add_authored_walkmesh_boundary_walls(source, enabled=False)

    assert result.enabled is False
    assert result.wok is source
    assert result.helper_segment_count == 0
    assert result.helper_face_count == 0
    assert result.added_face_count == 0
    assert result.non_walk_face_count == 0


def test_t2704_legacy_generate_walls_action_cannot_mutate_an_imported_external_wok() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_format import WOKData, WOKFace
    from src.core.modules.module_walkmesh_service import ModuleWalkmeshService

    imported = WOKData(
        name="vanilla_room",
        verts=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 4)],
    )
    before = imported.to_bytes()

    output = ModuleWalkmeshService().generate_walls(imported)

    assert output is imported
    assert output.to_bytes() == before
    assert output.walkable_face_count() == 1
    assert output.non_walk_face_count() == 0
