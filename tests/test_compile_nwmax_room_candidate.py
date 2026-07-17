from __future__ import annotations

import pytest

from scripts.compile_nwmax_room_candidate import merge_render_ascii_models, prepare_room_ascii


_RENDER_ASCII = """\
newmodel old_room
setsupermodel old_room NULL
classification Other
beginmodelgeom old_room
node dummy old_room
  parent NULL
endnode
node trimesh floor_visual
  parent old_room
  position 0 0 0
  orientation 1 0 0 0
  bitmap floor
  verts 3
    0 0 0
    1 0 0
    0 1 0
  faces 1
    0 1 2 1 0 0 0 1
  tverts 1
    0 0 0
endnode
endmodelgeom old_room
donemodel old_room
"""


_AABB_ASCII = """\
newmodel old_collision
setsupermodel old_collision NULL
classification Other
beginmodelgeom old_collision
node dummy old_collision
  parent NULL
endnode
node aabb old_collision_wg
  parent old_collision
  position 0 0 0
  orientation 1 0 0 0
  verts 8
    0 0 0
    1 0 0
    1 1 0
    0 1 0
    0 0 2
    1 0 2
    1 1 2
    0 1 2
  faces 4
    0 1 2 1 0 0 0 1
    0 2 3 1 0 0 0 1
    0 4 5 1 0 0 0 1
    0 5 1 1 0 0 0 1
endnode
endmodelgeom old_collision
donemodel old_collision
"""


def test_prepare_room_ascii_keeps_floor_and_removes_vertical_aabb_faces() -> None:
    prepared, wok, metadata = prepare_room_ascii(
        _RENDER_ASCII,
        _AABB_ASCII,
        room="test_room",
        max_slope_degrees=45.0,
    )

    assert len(wok.faces) == 2
    assert len(wok.verts) == 4
    assert metadata["walkmesh"]["rejected_steep_face_count"] == 2
    assert metadata["walkmesh"]["rejected_degenerate_face_count"] == 0
    assert prepared.lower().count("node aabb ") == 1
    assert "newmodel test_room" in prepared
    assert "parent test_room" in prepared
    assert "faces 2" in prepared


def test_prepare_room_ascii_rejects_transformed_aabb() -> None:
    transformed = _AABB_ASCII.replace("orientation 1 0 0 0", "orientation 0 0 1 1.570796")
    with pytest.raises(ValueError, match="non-identity rotation"):
        prepare_room_ascii(_RENDER_ASCII, transformed, room="test_room")


@pytest.mark.parametrize("slope", [float("nan"), -0.1, 90.0, float("inf")])
def test_prepare_room_ascii_rejects_invalid_slope(slope: float) -> None:
    with pytest.raises(ValueError, match="finite.*range"):
        prepare_room_ascii(
            _RENDER_ASCII,
            _AABB_ASCII,
            room="test_room",
            max_slope_degrees=slope,
        )


def test_prepare_room_ascii_rejects_explicit_source_without_aabb() -> None:
    with pytest.raises(ValueError, match="Explicit walkmesh ASCII"):
        prepare_room_ascii(_RENDER_ASCII, _RENDER_ASCII, room="test_room")


def test_prepare_room_ascii_rejects_transformed_aabb_parent() -> None:
    transformed = _AABB_ASCII.replace(
        "node dummy old_collision\n  parent NULL",
        "node dummy old_collision\n  parent NULL\n  position 2 0 0",
    )
    with pytest.raises(ValueError, match="ancestor.*non-identity transform"):
        prepare_room_ascii(_RENDER_ASCII, transformed, room="test_room")


def test_prepare_room_ascii_removes_stacked_nonwalk_ceiling() -> None:
    ceiling = _AABB_ASCII.replace(
        "faces 4\n",
        "faces 6\n",
    ).replace(
        "    0 5 1 1 0 0 0 1\n",
        "    0 5 1 1 0 0 0 1\n"
        "    4 5 6 1 0 0 0 7\n"
        "    4 6 7 1 0 0 0 7\n",
    )
    _prepared, wok, metadata = prepare_room_ascii(
        _RENDER_ASCII,
        ceiling,
        room="test_room",
    )
    assert len(wok.faces) == 2
    assert metadata["walkmesh"]["rejected_stacked_face_count"] == 2


def test_merge_render_ascii_models_reparents_disjoint_shell() -> None:
    exterior = _RENDER_ASCII.replace("old_room", "exterior_room").replace(
        "floor_visual", "lava_shell"
    )

    merged = merge_render_ascii_models(
        (_RENDER_ASCII, exterior),
        room="test_room",
    )

    assert merged.lower().count("newmodel ") == 1
    assert merged.lower().count("node dummy test_room") == 1
    assert "node trimesh floor_visual" in merged
    assert "node trimesh lava_shell" in merged
    assert "parent test_room" in merged


def test_merge_render_ascii_models_rejects_duplicate_node_names() -> None:
    exterior = _RENDER_ASCII.replace("old_room", "exterior_room")

    with pytest.raises(ValueError, match="duplicates node name 'floor_visual'"):
        merge_render_ascii_models((_RENDER_ASCII, exterior), room="test_room")
