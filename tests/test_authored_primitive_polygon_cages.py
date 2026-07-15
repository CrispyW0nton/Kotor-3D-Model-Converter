"""Focused Maya-oracle contracts for connected primitive construction cages."""

from __future__ import annotations

from dataclasses import replace
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for relative in (
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Resources/Python",
    "native/GhostRigger.Core.IO/Python",
    "native/GhostRigger.Core.Math/Python",
    ".",
):
    path = str((ROOT / relative).resolve())
    if path not in sys.path:
        sys.path.insert(0, path)


from src.core.geometry.mesh_topology import MeshTopology  # noqa: E402
from src.core.modules.authored_primitive_polygon_cages import (  # noqa: E402
    build_authored_primitive_polygon_cage,
    build_cone_polygon_cage,
    build_cube_polygon_cage,
    build_cylinder_polygon_cage,
    build_plane_polygon_cage,
    build_sphere_polygon_cage,
    build_torus_polygon_cage,
    logical_topology_counts,
)
from src.core.modules.authored_room_primitives import (  # noqa: E402
    ConePrimitive,
    CubePrimitive,
    CylinderPrimitive,
    FloorPrimitive,
    SpherePrimitive,
    TorusPrimitive,
)
from src.core.modules.authored_room_composition import (  # noqa: E402
    PlacedRoomPrimitive,
    PrimitiveTransform,
    primitive_to_mesh,
)


def _assert_one_clean_shell(mesh, *, closed: bool) -> None:
    audit = MeshTopology.build(mesh.vertices, mesh.faces).validate_manifold_state()
    assert not audit.has_errors
    assert not audit.inconsistent_winding_edges
    assert not audit.degenerate_faces
    assert len(audit.components) == 1
    assert audit.components[0].closed is closed


def _assert_faces_follow_corner_normals(mesh) -> None:
    normal_rows = mesh.corner_channels["normal"].values
    for face_index, face in enumerate(mesh.faces):
        p0, p1, p2 = (mesh.vertices[index] for index in face[:3])
        edge1 = tuple(p1[index] - p0[index] for index in range(3))
        edge2 = tuple(p2[index] - p0[index] for index in range(3))
        cross = (
            edge1[1] * edge2[2] - edge1[2] * edge2[1],
            edge1[2] * edge2[0] - edge1[0] * edge2[2],
            edge1[0] * edge2[1] - edge1[1] * edge2[0],
        )
        average_normal = tuple(
            sum(normal[index] for normal in normal_rows[face_index])
            for index in range(3)
        )
        assert sum(cross[index] * average_normal[index] for index in range(3)) > 1.0e-10


def test_maya_probe_topology_formulas_match_connected_logical_cages() -> None:
    plane = build_plane_polygon_cage(
        FloorPrimitive("polyPlane1", subdivisions_width=4, subdivisions_depth=3)
    )
    cube = build_cube_polygon_cage(
        CubePrimitive(
            "polyCube1",
            subdivisions_x=2,
            subdivisions_y=3,
            subdivisions_z=4,
        )
    )
    sphere = build_sphere_polygon_cage(
        SpherePrimitive("polySphere1", subdivisions_axis=12, subdivisions_height=8)
    )
    torus = build_torus_polygon_cage(
        TorusPrimitive("polyTorus1", subdivisions_axis=16, subdivisions_height=8)
    )

    assert logical_topology_counts(plane) == (20, 31, 12)
    assert logical_topology_counts(cube) == (54, 104, 52)
    assert logical_topology_counts(sphere) == (86, 180, 96)
    assert logical_topology_counts(torus) == (128, 256, 128)
    _assert_one_clean_shell(plane, closed=False)
    for mesh in (cube, sphere, torus):
        _assert_one_clean_shell(mesh, closed=True)
    for mesh in (plane, cube, sphere, torus):
        _assert_faces_follow_corner_normals(mesh)


def test_maya_cylinder_and_cone_cap_subdivision_counts_are_exact() -> None:
    cylinder_counts = {
        0: (16, 24, 10),
        1: (18, 40, 24),
        2: (34, 72, 40),
    }
    cone_counts = {
        0: (9, 16, 9),
        1: (10, 24, 16),
        2: (18, 40, 24),
    }
    for subdivisions_caps, expected in cylinder_counts.items():
        mesh = build_cylinder_polygon_cage(
            CylinderPrimitive(
                "polyCylinder1",
                segments=8,
                subdivisions_height=1,
                subdivisions_caps=subdivisions_caps,
            )
        )
        assert logical_topology_counts(mesh) == expected
        _assert_one_clean_shell(mesh, closed=True)
        _assert_faces_follow_corner_normals(mesh)
    for subdivisions_caps, expected in cone_counts.items():
        mesh = build_cone_polygon_cage(
            ConePrimitive(
                "polyCone1",
                subdivisions_axis=8,
                subdivisions_height=1,
                subdivisions_caps=subdivisions_caps,
            )
        )
        assert logical_topology_counts(mesh) == expected
        _assert_one_clean_shell(mesh, closed=True)
        _assert_faces_follow_corner_normals(mesh)


def test_cages_keep_stable_component_provenance_and_face_corner_channels() -> None:
    primitive = CubePrimitive(
        "historyCube",
        subdivisions_x=2,
        subdivisions_y=2,
        subdivisions_z=2,
    )
    first = build_authored_primitive_polygon_cage(primitive)
    second = build_authored_primitive_polygon_cage(primitive)
    assert first == second
    assert first.metadata["logical_polygon_cage"] is True
    assert first.metadata["topology_contract"] == "maya_2025_polygon_primitive"
    vertex_ids = first.vertex_channels["provenance.vertex_id"].values
    face_ids = first.face_channels["provenance.face_id"].values
    corner_ids = first.corner_channels["provenance.corner_id"].values
    assert len(set(vertex_ids)) == len(first.vertices)
    assert len(set(face_ids)) == len(first.faces)
    assert len({value for row in corner_ids for value in row}) == sum(map(len, first.faces))
    assert "normal" in first.corner_channels
    assert "uv0" in first.corner_channels
    assert all(
        len(first.corner_channels[name].values[face_index]) == len(face)
        for name in ("normal", "uv0", "provenance.corner_id")
        for face_index, face in enumerate(first.faces)
    )


def test_production_cage_namespaces_identity_and_evaluates_placed_freeze_stages() -> None:
    node_id = "27c54c4e-8489-55ac-9c8f-2f1f5aac49c2"
    base = CubePrimitive(
        "historyCube",
        size=(1.0, 2.0, 3.0),
        center=(0.0, 0.0, 0.0),
        construction_node_id=node_id,
    )
    placed = PlacedRoomPrimitive(
        primitive=base,
        name="historyCube",
        evaluation_transforms=(
            PrimitiveTransform(translation=(2.0, 0.0, 0.0), scale=(2.0, 1.0, 1.0)),
        ),
        transform=PrimitiveTransform(
            translation=(0.0, 3.0, 1.0),
            rotation_degrees_z=90.0,
        ),
    )

    local_cage = build_authored_primitive_polygon_cage(base, room_resref="recipe_room")
    placed_cage = build_authored_primitive_polygon_cage(placed, room_resref="recipe_room")
    render_mesh = primitive_to_mesh(placed)

    def positions(values):
        return {tuple(round(component, 8) for component in value) for value in values}

    assert positions(placed_cage.vertices) == positions(render_mesh.vertices)
    assert placed_cage.metadata["construction_node_id"] == node_id
    assert placed_cage.metadata["transform_stage_count"] == 2
    assert placed_cage.metadata["construction_recipe_preserved_through_freeze"] is True
    assert placed_cage.vertex_channels["provenance.vertex_id"].values == local_cage.vertex_channels["provenance.vertex_id"].values
    assert all(
        str(value).startswith(f"construction:{node_id}/vertex:")
        for value in placed_cage.vertex_channels["provenance.vertex_id"].values
    )

    resized = build_authored_primitive_polygon_cage(
        replace(base, size=(4.0, 5.0, 6.0)),
        room_resref="recipe_room",
    )
    assert resized.vertex_channels["provenance.vertex_id"].values == local_cage.vertex_channels["provenance.vertex_id"].values
    assert resized.face_channels["provenance.face_id"].values == local_cage.face_channels["provenance.face_id"].values

    other = build_authored_primitive_polygon_cage(
        replace(base, construction_node_id="3d8ca2a6-a99f-5d02-9f4a-8b193709071a"),
        room_resref="recipe_room",
    )
    assert set(other.vertex_channels["provenance.vertex_id"].values).isdisjoint(
        local_cage.vertex_channels["provenance.vertex_id"].values
    )


def test_axis_baseline_uv_twist_and_round_cap_inputs_re_evaluate_without_topology_drift() -> None:
    cylinder = build_cylinder_polygon_cage(
        CylinderPrimitive(
            "axisCylinder",
            radius=1.0,
            height=2.0,
            segments=8,
            axis=(1.0, 0.0, 0.0),
            height_baseline=-1.0,
            create_uvs=0,
        )
    )
    xs = [vertex[0] for vertex in cylinder.vertices]
    assert math.isclose(min(xs), 0.0, abs_tol=1.0e-9)
    assert math.isclose(max(xs), 2.0, abs_tol=1.0e-9)
    assert "uv0" not in cylinder.corner_channels

    flat = build_cylinder_polygon_cage(
        CylinderPrimitive("flat", radius=1.0, height=2.0, segments=8, subdivisions_caps=2)
    )
    rounded = build_cylinder_polygon_cage(
        CylinderPrimitive(
            "rounded",
            radius=1.0,
            height=2.0,
            segments=8,
            subdivisions_caps=2,
            round_cap=True,
        )
    )
    assert logical_topology_counts(flat) == logical_topology_counts(rounded)
    assert max(vertex[2] for vertex in rounded.vertices) - min(vertex[2] for vertex in rounded.vertices) == 4.0
    assert max(vertex[2] for vertex in flat.vertices) - min(vertex[2] for vertex in flat.vertices) == 2.0

    untwisted = build_torus_polygon_cage(
        TorusPrimitive("torus", subdivisions_axis=12, subdivisions_height=6, twist=0.0)
    )
    twisted = build_torus_polygon_cage(
        TorusPrimitive("torus", subdivisions_axis=12, subdivisions_height=6, twist=120.0)
    )
    assert logical_topology_counts(untwisted) == logical_topology_counts(twisted)
    assert untwisted.vertices != twisted.vertices
    _assert_one_clean_shell(twisted, closed=True)


def test_scene_and_tools_polygon_cage_payloads_remain_byte_identical() -> None:
    scene = ROOT / "native/GhostRigger.Core.Scene/Python/src/core/modules/authored_primitive_polygon_cages.py"
    tools = ROOT / "native/GhostRigger.Core.Tools/Python/src/core/modules/authored_primitive_polygon_cages.py"
    assert scene.read_bytes() == tools.read_bytes()
