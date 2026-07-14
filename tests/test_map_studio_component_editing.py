from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEOMETRY_PYTHON = ROOT / "native" / "GhostRigger.Domain.Core.Geometry" / "Python"
if str(GEOMETRY_PYTHON) not in sys.path:
    sys.path.insert(0, str(GEOMETRY_PYTHON))

from src.core.geometry.component_editing import (  # noqa: E402
    bridge_edges,
    cleanup_degenerate_faces,
    cleanup_face_normals,
    component_mesh,
    fill_face,
    flatten_vertices,
    mirror_vertices,
    split_face_with_edge,
    snap_vertex_to_vertex,
    snap_vertices_to_grid,
    triangulate_faces,
    weld_vertices,
)


def test_t2601_snap_vertex_to_vertex_moves_source_without_losing_faces() -> None:
    mesh = component_mesh(
        [(0.1, 0.0, 0.0), (1.0, 2.0, 3.0), (0.0, 1.0, 0.0)],
        [(0, 1, 2)],
        metadata={"room": "grdev01"},
    )

    result = snap_vertex_to_vertex(mesh, 0, 1)

    assert result.changed_vertex_count == 1
    assert result.mesh.vertices[0] == (1.0, 2.0, 3.0)
    assert result.mesh.vertices[1] == (1.0, 2.0, 3.0)
    assert result.mesh.faces == ((0, 1, 2),)
    assert result.mesh.metadata["room"] == "grdev01"


def test_t2601_weld_vertices_compacts_mesh_and_removes_degenerate_faces() -> None:
    mesh = component_mesh(
        [(0.0, 0.0, 0.0), (0.01, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        [(0, 1, 2), (0, 2, 3)],
    )

    result = weld_vertices(mesh, (0, 1), target_index=0)

    assert result.changed_vertex_count == 2
    assert result.removed_face_count == 1
    assert result.mesh.vertices == ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    assert result.mesh.faces == ((0, 1, 2),)
    assert result.warnings == ("Removed 1 degenerate face(s) after weld.",)


def test_t2601_flatten_and_grid_snap_support_map_studio_component_cleanup() -> None:
    mesh = component_mesh([(0.12, 0.24, 0.9), (0.37, 0.52, 1.3), (1.0, 1.0, 2.0)])

    flattened = flatten_vertices(mesh, (0, 1), axis="z")
    snapped = snap_vertices_to_grid(flattened.mesh, (0, 1), grid_size=0.25, axes=("x", "y"))

    assert flattened.mesh.vertices[0][2] == flattened.mesh.vertices[1][2] == 1.1
    assert snapped.mesh.vertices[0] == (0.0, 0.25, 1.1)
    assert snapped.mesh.vertices[1] == (0.25, 0.5, 1.1)
    assert snapped.mesh.vertices[2] == (1.0, 1.0, 2.0)


def test_t2601_mirror_vertices_reflects_selected_axis_around_center() -> None:
    mesh = component_mesh([(-2.0, 0.0, 0.0), (4.0, 0.0, 0.0), (1.0, 2.0, 0.0)])

    result = mirror_vertices(mesh, (0, 1), axis="x")

    assert result.changed_vertex_count == 2
    assert result.mesh.vertices[0] == (4.0, 0.0, 0.0)
    assert result.mesh.vertices[1] == (-2.0, 0.0, 0.0)
    assert result.mesh.vertices[2] == (1.0, 2.0, 0.0)
    assert result.metadata["axis"] == "x"
    assert result.metadata["center"] == 1.0


def test_t2601_triangulate_and_cleanup_degenerate_faces() -> None:
    mesh = component_mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)],
        [(0, 1, 2, 3), (0, 0, 1)],
    )

    cleaned = cleanup_degenerate_faces(mesh)
    triangulated = triangulate_faces(cleaned.mesh)

    assert cleaned.removed_face_count == 1
    assert triangulated.mesh.faces == ((0, 1, 2), (0, 2, 3))


def test_t2601_fill_face_then_triangulate_for_room_patch() -> None:
    mesh = component_mesh(
        [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0), (0.0, 2.0, 0.0)],
        metadata={"room": "grpatch"},
    )

    filled = fill_face(mesh, (0, 1, 2, 3))
    triangulated = triangulate_faces(filled.mesh)

    assert filled.mesh.faces == ((0, 1, 2, 3),)
    assert filled.metadata["operation"] == "fill_face"
    assert filled.metadata["face_vertex_count"] == 4
    assert triangulated.mesh.faces == ((0, 1, 2), (0, 2, 3))
    assert triangulated.mesh.metadata["room"] == "grpatch"


def test_t2601_triangulate_skips_degenerate_fan_triangles_for_wok_safety() -> None:
    mesh = component_mesh(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        [(0, 1, 2, 3, 4), (0, 0, 1), (0, 1, 2)],
        metadata={"room": "grwok_safe"},
    )

    triangulated = triangulate_faces(mesh)

    assert triangulated.mesh.faces == ((0, 2, 3), (0, 3, 4))
    assert triangulated.removed_face_count == 2
    assert triangulated.metadata["skipped_triangle_count"] == 1
    assert triangulated.warnings == (
        "Skipped 1 degenerate fan triangle(s) during triangulation.",
        "Removed 2 degenerate face(s) during triangulation.",
    )
    assert triangulated.mesh.metadata["room"] == "grwok_safe"


def test_t2601_bridge_edges_creates_auditable_room_or_terrain_seam() -> None:
    mesh = component_mesh(
        [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0), (0.0, 2.0, 0.0)],
        metadata={"room": "grbridge"},
    )

    bridged = bridge_edges(mesh, (0, 1), (3, 2))

    assert bridged.mesh.faces == ((0, 1, 2, 3),)
    assert bridged.mesh.metadata["room"] == "grbridge"
    assert bridged.metadata["operation"] == "bridge_edges"
    assert bridged.metadata["added_face_count"] == 1
    assert bridged.metadata["first_edge"] == (0, 1)
    assert bridged.metadata["second_edge"] == (3, 2)


def test_t2601_bridge_edges_rejects_degenerate_shared_edges() -> None:
    import pytest

    mesh = component_mesh([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)])

    with pytest.raises(ValueError, match="four unique vertices"):
        bridge_edges(mesh, (0, 1), (1, 2))
    with pytest.raises(ValueError, match="zero-length"):
        bridge_edges(mesh, (0, 0), (1, 2))


def test_t2601_split_face_with_edge_creates_auditable_room_cut_loop() -> None:
    mesh = component_mesh(
        [
            (0.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
            (4.0, 3.0, 0.0),
            (2.0, 4.0, 0.0),
            (0.0, 3.0, 0.0),
        ],
        [(0, 1, 2, 3, 4)],
        metadata={"room": "grknife"},
    )

    split = split_face_with_edge(mesh, 0, 1, 4)

    assert split.mesh.faces == ((1, 2, 3, 4), (4, 0, 1))
    assert split.mesh.vertices == mesh.vertices
    assert split.mesh.metadata["room"] == "grknife"
    assert split.removed_face_count == 1
    assert split.metadata["operation"] == "split_face_with_edge"
    assert split.metadata["added_face_count"] == 2
    assert split.metadata["split_vertices"] == (1, 4)
    assert split.metadata["new_face_vertex_counts"] == (4, 3)


def test_t2601_split_face_with_edge_rejects_noop_or_invalid_cuts() -> None:
    import pytest

    mesh = component_mesh(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
            (2.0, 2.0, 0.0),
        ],
        [(0, 1, 2, 3)],
    )

    with pytest.raises(ValueError, match="non-adjacent"):
        split_face_with_edge(mesh, 0, 0, 1)
    with pytest.raises(ValueError, match="selected face"):
        split_face_with_edge(mesh, 0, 0, 4)
    with pytest.raises(ValueError, match="outside vertex range"):
        split_face_with_edge(mesh, 0, 0, 2_000)


def test_t2601_cleanup_face_normals_flips_faces_to_reference_axis() -> None:
    mesh = component_mesh(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)],
        [(3, 2, 1, 0)],
    )

    cleaned = cleanup_face_normals(mesh, reference_axis="z", positive=True)

    assert cleaned.mesh.faces == ((0, 1, 2, 3),)
    assert cleaned.metadata["operation"] == "cleanup_face_normals"
    assert cleaned.metadata["flipped_face_count"] == 1
