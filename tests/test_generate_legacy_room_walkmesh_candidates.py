from __future__ import annotations

import pytest
from src.core.geometry.model_data import ModelNode, NodeFlags
from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
from src.core.modules.module_format import WOKData, WOKFace

from scripts.generate_legacy_room_walkmesh_candidates import (
    ExplicitFloorSelection,
    _build_embedded_aabb_node,
    _compare_node_inventories,
    _quaternion_delta,
    build_explicit_floor_wok,
)


def _surface(
    name: str,
    texture: str,
    vertices: tuple[tuple[float, float, float], ...],
    faces: tuple[tuple[int, int, int], ...],
) -> ImportedMeshSurface:
    return ImportedMeshSurface(
        name=name,
        texture=texture,
        vertices=vertices,
        faces=faces,
    )


def _primitive(*surfaces: ImportedMeshSurface) -> ImportedMeshRoomPrimitive:
    return ImportedMeshRoomPrimitive(room_resref="proof_01a", surfaces=tuple(surfaces), game="K2")


def test_explicit_floor_selection_normalizes_downward_render_winding() -> None:
    floor = _surface(
        "ReviewedFloor",
        "floor_tex",
        ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
        ((0, 1, 2), (0, 2, 3)),
    )
    ignored = _surface(
        "UnreviewedFloor",
        "floor_tex",
        ((10.0, 0.0, 0.0), (10.0, 1.0, 0.0), (11.0, 0.0, 0.0)),
        ((0, 1, 2),),
    )
    selection = ExplicitFloorSelection(
        room_resref="proof_01a",
        selected_node_names=("ReviewedFloor",),
        expected_texture="floor_tex",
    )

    wok, metadata = build_explicit_floor_wok(_primitive(floor, ignored), selection)

    assert len(wok.verts) == 4
    assert len(wok.faces) == 2
    assert metadata["component_count"] == 1
    assert [row["name"] for row in metadata["selected_nodes"]] == ["ReviewedFloor"]
    for face in wok.faces:
        a, b, c = (wok.verts[index] for index in (face.v1, face.v2, face.v3))
        assert ((b[0] - a[0]) * (c[1] - a[1])) - ((b[1] - a[1]) * (c[0] - a[0])) > 0.0


def test_explicit_floor_selection_rejects_wrong_texture_and_steep_geometry() -> None:
    wrong_texture = _surface(
        "ReviewedFloor",
        "wall_tex",
        ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
        ((0, 1, 2),),
    )
    selection = ExplicitFloorSelection(
        room_resref="proof_01a",
        selected_node_names=("ReviewedFloor",),
        expected_texture="floor_tex",
    )
    with pytest.raises(ValueError, match="expected 'floor_tex'"):
        build_explicit_floor_wok(_primitive(wrong_texture), selection)

    steep = _surface(
        "ReviewedFloor",
        "floor_tex",
        ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0, 1, 2),),
    )
    with pytest.raises(ValueError, match="slope gate"):
        build_explicit_floor_wok(_primitive(steep), selection)


def test_explicit_floor_selection_rejects_disconnected_allowlisted_islands() -> None:
    first = _surface(
        "FloorA",
        "floor_tex",
        ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
        ((0, 1, 2),),
    )
    second = _surface(
        "FloorB",
        "floor_tex",
        ((10.0, 0.0, 0.0), (10.0, 1.0, 0.0), (11.0, 0.0, 0.0)),
        ((0, 1, 2),),
    )
    selection = ExplicitFloorSelection(
        room_resref="proof_01a",
        selected_node_names=("FloorA", "FloorB"),
        expected_texture="floor_tex",
    )

    with pytest.raises(ValueError, match="2 disconnected components"):
        build_explicit_floor_wok(_primitive(first, second), selection)


def _inventory_row(
    name: str,
    *,
    parent: str = "room_01a",
    kinds: str = "MESH",
    face_count: int = 4,
    vertex_count: int = 6,
    texture: str = "floor_tex",
    lightmap: str = "",
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
) -> dict:
    return {
        "name": name,
        "parent": parent,
        "kinds": kinds,
        "face_count": face_count,
        "vertex_count": vertex_count,
        "texture": texture,
        "lightmap": lightmap,
        "position": position,
        "rotation": rotation,
    }


def test_quaternion_delta_is_sign_invariant() -> None:
    quaternion = (0.1, 0.2, 0.3, 0.9273618495495704)
    negated = tuple(-value for value in quaternion)
    assert _quaternion_delta(quaternion, quaternion) == 0.0
    assert _quaternion_delta(quaternion, negated) == 0.0
    assert _quaternion_delta(quaternion, (0.1, 0.2, 0.3, 0.8)) > 1.0e-3


def test_compare_node_inventories_accepts_root_rename_only() -> None:
    source = [
        _inventory_row("Gra999_01a", parent="", kinds="dummy", face_count=0, vertex_count=0, texture=""),
        _inventory_row("Cylinder01", parent="Gra999_01a"),
        _inventory_row("Cylinder01", parent="Gra999_01a", texture="lko_dor01", face_count=176, vertex_count=420),
    ]
    output = [
        _inventory_row("gra999_01a", parent="", kinds="dummy", face_count=0, vertex_count=0, texture=""),
        _inventory_row("Cylinder01", parent="gra999_01a"),
        _inventory_row("Cylinder01", parent="gra999_01a", texture="lko_dor01", face_count=176, vertex_count=420),
    ]
    mismatches = _compare_node_inventories(
        source,
        output,
        renamed_root=("Gra999_01a", "gra999_01a"),
    )
    assert mismatches == []


def test_compare_node_inventories_blocks_dropped_duplicate_named_node() -> None:
    source = [
        _inventory_row("gra999_01a", parent="", kinds="dummy", face_count=0, vertex_count=0, texture=""),
        _inventory_row("Cylinder01"),
        _inventory_row("Cylinder01", texture="lko_dor01", face_count=176, vertex_count=420),
    ]
    dropped = source[:2]
    mismatches = _compare_node_inventories(
        source,
        dropped,
        renamed_root=("gra999_01a", "gra999_01a"),
    )
    assert mismatches and "node count changed" in mismatches[0]

    retextured = [dict(row) for row in source]
    retextured[2]["texture"] = "wrong_tex"
    mismatches = _compare_node_inventories(
        source,
        retextured,
        renamed_root=("gra999_01a", "gra999_01a"),
    )
    assert any("texture" in item for item in mismatches)


def test_build_embedded_aabb_node_mirrors_external_wok() -> None:
    wok = WOKData(
        name="room_01a",
        verts=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 3), WOKFace(1, 3, 2, 7)],
    )
    root = ModelNode()
    root.name = "room_01a"

    node = _build_embedded_aabb_node("room_01a", wok, root)

    assert node.name == "room_01a_wg"
    assert node.flags == int(NodeFlags.HEADER | NodeFlags.AABB)
    assert node.rotation == (0.0, 0.0, 0.0, 1.0)
    assert node.render is False and node.has_shadow is False
    assert node.faces == [(0, 1, 2), (1, 3, 2)]
    assert node.face_mats == [3, 7]
    assert node.vertices == [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0)]
    assert root.children[-1] is node and node.parent is root
