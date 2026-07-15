"""Trusted Quad Draw provenance and Maya-style edge-loop regressions."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
for source in (
    ROOT / "native" / "GhostRigger.Core.Math" / "Python" / "src",
    ROOT / "native" / "GhostRigger.Core.Scene" / "Python" / "src",
):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from core.geometry.mesh_topology import MeshTopology  # noqa: E402
from core.modules.authored_imported_mesh import (  # noqa: E402
    LOGICAL_QUAD_PROVENANCE_KEY,
    ImportedMeshRoomPrimitive,
    ImportedMeshSurface,
    append_imported_mesh_quad,
    imported_mesh_primitive_from_payload,
    imported_mesh_primitive_payload,
    insert_imported_mesh_edge_loop,
)


def _quad_strip() -> ImportedMeshRoomPrimitive:
    primitive = ImportedMeshRoomPrimitive(room_resref="grquad", surfaces=(), game="K2")
    primitive = append_imported_mesh_quad(
        primitive,
        "retopo",
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)),
        texture="gr_floor",
        lightmap="gr_floorlm",
        material=9,
    )
    return append_imported_mesh_quad(
        primitive,
        "render",
        ((1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 1.0, 0.0), (1.0, 1.0, 0.0)),
        material=9,
    )


def test_quad_draw_persists_adjacent_auto_welded_logical_quad_provenance() -> None:
    primitive = _quad_strip()
    provenance = primitive.metadata[LOGICAL_QUAD_PROVENANCE_KEY]

    assert provenance["version"] == 1
    assert provenance["quads_by_role"] == {
        "render": [[0, 1, 2, 3], [1, 4, 5, 2]],
    }
    # The two ordered quads share the same raw (not merely positional) edge.
    assert set(provenance["quads_by_role"]["render"][0]) & set(
        provenance["quads_by_role"]["render"][1]
    ) == {1, 2}

    restored = imported_mesh_primitive_from_payload(
        imported_mesh_primitive_payload(primitive),
        primitive.room_resref,
    )
    assert restored.metadata[LOGICAL_QUAD_PROVENANCE_KEY] == provenance


def test_insert_edge_loop_traverses_multi_quad_strip_and_interpolates_all_channels() -> None:
    primitive = _quad_strip()
    source = primitive.surfaces[0]

    # Ordered top-to-bottom, so 0.25 lands at Y=.75.  This proves the operator
    # preserves the selected-edge direction rather than sorting endpoints.
    edited = insert_imported_mesh_edge_loop(primitive, "render", (3, 0), 0.25)
    surface = edited.surfaces[0]

    assert len(surface.vertices) == 9
    assert len(surface.faces) == 8
    assert len(surface.face_mats) == len(surface.faces)
    assert set(surface.face_mats) == {9}
    assert len(surface.uvs) == len(surface.vertices)
    assert len(surface.normals) == len(surface.vertices)
    assert len(surface.uvs_lm) == len(surface.vertices)
    for actual, expected in zip(
        surface.vertices[6:],
        ((0.0, 0.75, 0.0), (1.0, 0.75, 0.0), (2.0, 0.75, 0.0)),
    ):
        assert actual == pytest.approx(expected)
    assert surface.uvs[6] == pytest.approx(
        (
            source.uvs[3][0] + ((source.uvs[0][0] - source.uvs[3][0]) * 0.25),
            source.uvs[3][1] + ((source.uvs[0][1] - source.uvs[3][1]) * 0.25),
        )
    )
    assert surface.uvs_lm[6] == pytest.approx(
        (
            source.uvs_lm[3][0] + ((source.uvs_lm[0][0] - source.uvs_lm[3][0]) * 0.25),
            source.uvs_lm[3][1] + ((source.uvs_lm[0][1] - source.uvs_lm[3][1]) * 0.25),
        )
    )
    assert surface.normals[6] == pytest.approx((0.0, 0.0, 1.0))

    provenance = edited.metadata[LOGICAL_QUAD_PROVENANCE_KEY]["quads_by_role"]["render"]
    assert len(provenance) == 4
    assert all(len(quad) == 4 and len(set(quad)) == 4 for quad in provenance)
    assert edited.metadata["last_topology_edit"] == {
        "operation": "insert_edge_loop",
        "mesh_role": "render",
        "selected_edge": [3, 0],
        "position": 0.25,
        "affected_quad_indices": [0, 1],
        "affected_quad_count": 2,
        "inserted_vertex_count": 3,
        "generated_face_start": 0,
        "generated_face_count": 8,
        "logical_quad_count": 4,
        "logical_quad_provenance_version": 1,
        "uv_policy": "linear_edge_interpolation",
        "normal_policy": "spherical_edge_interpolation",
        "lightmap_uv_policy": "linear_edge_interpolation",
        "walkmesh_policy": "requires_review",
    }
    audit = MeshTopology.build(surface.vertices, surface.faces).validate_manifold_state()
    assert not audit.degenerate_faces
    assert not audit.duplicate_faces
    assert not audit.non_manifold_edges
    assert not audit.inconsistent_winding_edges


def test_insert_edge_loop_refuses_stock_triangle_pairs_without_quad_provenance() -> None:
    surface = ImportedMeshSurface(
        name="stock_triangulation",
        texture="lda_floor",
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)),
        faces=((0, 1, 2), (0, 2, 3)),
        face_mats=(4, 4),
        uvs=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        normals=((0.0, 0.0, 1.0),) * 4,
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="stock", surfaces=(surface,), game="K2")

    with pytest.raises(ValueError, match="requires logical Quad Draw provenance"):
        insert_imported_mesh_edge_loop(primitive, "render", (0, 1))


def test_insert_edge_loop_from_shared_edge_traverses_both_strip_directions() -> None:
    primitive = _quad_strip()

    edited = insert_imported_mesh_edge_loop(primitive, "render", (1, 2), 0.25)
    inserted = edited.surfaces[0].vertices[6:]

    assert len(inserted) == 3
    assert {tuple(round(value, 6) for value in point) for point in inserted} == {
        (0.0, 0.25, 0.0),
        (1.0, 0.25, 0.0),
        (2.0, 0.25, 0.0),
    }
    assert edited.metadata["last_topology_edit"]["affected_quad_indices"] == [0, 1]


def test_insert_edge_loop_refuses_stale_provenance_instead_of_guessing() -> None:
    primitive = _quad_strip()
    metadata = dict(primitive.metadata)
    metadata[LOGICAL_QUAD_PROVENANCE_KEY] = {
        "version": 1,
        "quads_by_role": {"render": [[0, 1, 2, 99]]},
    }
    stale = ImportedMeshRoomPrimitive(
        room_resref=primitive.room_resref,
        surfaces=primitive.surfaces,
        source_model=primitive.source_model,
        game=primitive.game,
        wok=primitive.wok,
        metadata=metadata,
    )

    with pytest.raises(ValueError, match="malformed or out of range"):
        insert_imported_mesh_edge_loop(stale, "render", (0, 1))
