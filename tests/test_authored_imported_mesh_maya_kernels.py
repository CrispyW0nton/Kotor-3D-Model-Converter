"""Focused topology/channel contracts for Map Studio's Maya-style kernels."""

from __future__ import annotations

import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for source in (
    ROOT / "native" / "GhostRigger.Core.Math" / "Python" / "src",
    ROOT / "native" / "GhostRigger.Core.Scene" / "Python" / "src",
):
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))

from core.geometry.mesh_topology import MeshTopology  # noqa: E402
from core.modules.authored_imported_mesh import (  # noqa: E402
    ImportedMeshRoomPrimitive,
    ImportedMeshSurface,
    connect_imported_mesh_vertices,
    fill_imported_mesh_boundary_loop,
    harden_imported_mesh_edges,
    merge_imported_mesh_components,
    soften_imported_mesh_edges,
    split_imported_mesh_face_at_point,
    weld_imported_mesh_vertices,
)


def _surface(
    vertices,
    faces,
    *,
    name: str = "mesh",
    face_mats=(),
    normals=(),
) -> ImportedMeshSurface:
    count = len(vertices)
    return ImportedMeshSurface(
        name=name,
        texture="lda_floor01",
        vertices=tuple(vertices),
        faces=tuple(faces),
        face_mats=tuple(face_mats),
        uvs=tuple((index / max(1, count - 1), (index * 0.25) % 1.0) for index in range(count)),
        normals=tuple(normals) if normals else ((1.0, 0.0, 0.0),) * count,
        lightmap="lda_floor01lm",
        texture_names=("lda_floor01", "lda_floor01lm"),
        tex_count=2,
        uvs_lm=tuple((0.05 + (index * 0.05), 0.95 - (index * 0.05)) for index in range(count)),
    )


def _assert_channels(surface: ImportedMeshSurface) -> None:
    assert len(surface.uvs) == len(surface.vertices)
    assert len(surface.normals) == len(surface.vertices)
    assert len(surface.uvs_lm) == len(surface.vertices)
    assert len(surface.face_mats) == len(surface.faces)


def test_explicit_target_weld_moves_all_seam_copies_and_preserves_channels() -> None:
    render = _surface(
        (
            (0.0, 0.0, 0.0),  # selected source
            (2.0, 0.0, 0.0),  # explicit target
            (0.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 0.0, 0.0),  # UV seam copy of source
            (0.0, 2.0, 0.0),
            (1.0, 2.0, 0.0),
        ),
        ((0, 2, 3), (4, 5, 6), (1, 3, 6)),
        face_mats=(3, 5, 7),
    )
    detail = _surface(
        ((0.0, 0.0, 0.0), (3.0, 0.0, 0.0), (3.0, 1.0, 0.0)),
        ((0, 1, 2),),
        name="detail",
        face_mats=(11,),
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="grweld", surfaces=(render, detail))

    welded = weld_imported_mesh_vertices(primitive, "render", 0, 1)

    assert welded.surfaces[0].vertices[0] == (2.0, 0.0, 0.0)
    assert welded.surfaces[0].vertices[4] == (2.0, 0.0, 0.0)
    assert welded.surfaces[1].vertices[0] == (2.0, 0.0, 0.0)
    assert welded.surfaces[0].uvs == render.uvs
    assert welded.surfaces[0].uvs_lm == render.uvs_lm
    assert welded.surfaces[0].face_mats == render.face_mats
    assert welded.surfaces[1].face_mats == detail.face_mats
    assert welded.metadata["last_topology_edit"]["operation"] == "target_weld"
    for surface in welded.surfaces:
        _assert_channels(surface)

    positioned = weld_imported_mesh_vertices(
        primitive,
        "render",
        0,
        target_position=(4.0, 0.0, 0.0),
    )
    assert positioned.surfaces[0].vertices[0] == (4.0, 0.0, 0.0)
    assert positioned.surfaces[0].vertices[4] == (4.0, 0.0, 0.0)
    assert positioned.surfaces[1].vertices[0] == (4.0, 0.0, 0.0)
    assert positioned.metadata["last_topology_edit"]["target_vertex"] == -1


def test_connect_opposite_quad_vertices_replaces_only_the_diagonal() -> None:
    surface = _surface(
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0), (0.0, 2.0, 0.0)),
        ((0, 1, 2), (0, 2, 3)),
        face_mats=(4, 4),
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="grconnect", surfaces=(surface,))

    connected = connect_imported_mesh_vertices(primitive, "render", 1, 3)
    result = connected.surfaces[0]
    edges = {
        tuple(sorted((face[index], face[(index + 1) % 3])))
        for face in result.faces
        for index in range(3)
    }
    assert (1, 3) in edges
    assert (0, 2) not in edges
    assert result.uvs == surface.uvs
    assert result.uvs_lm == surface.uvs_lm
    assert result.face_mats == (4, 4)
    assert connected.metadata["last_topology_edit"]["operation"] == "connect_vertices"
    _assert_channels(result)


def test_connect_vertices_recovers_one_edge_across_a_coplanar_triangle_patch() -> None:
    surface = _surface(
        (
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0),
            (0.0, 1.0, 0.0), (1.0, 1.0, 0.0), (2.0, 1.0, 0.0),
        ),
        ((0, 1, 4), (0, 4, 3), (1, 2, 5), (1, 5, 4)),
        face_mats=(4, 4, 7, 7),
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="grconnect", surfaces=(surface,))

    connected = connect_imported_mesh_vertices(primitive, "render", 0, 5)
    result = connected.surfaces[0]
    edit = connected.metadata["last_topology_edit"]

    assert edit["operation"] == "connect_vertices"
    assert edit["topology_contract"] == "connected_coplanar_patch_via_multi_cut"
    assert edit["affected_faces"] == [0, 3]
    assert len(result.faces) > len(surface.faces)
    assert set(result.face_mats) == {4, 7}
    _assert_channels(result)
    audit = MeshTopology.build(result.vertices, result.faces).validate_manifold_state()
    assert not audit.degenerate_faces
    assert not audit.non_manifold_edges
    assert not audit.inconsistent_winding_edges


def test_merge_vertices_uses_deterministic_centroid_and_preserves_seam_channels() -> None:
    render = _surface(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.05, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2), (0, 2, 3)),
        face_mats=(5, 7),
    )
    detail = _surface(
        ((1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, -1.0, 0.0)),
        ((0, 1, 2),),
        name="detail",
        face_mats=(11,),
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="grmerge", surfaces=(render, detail))

    merged = merge_imported_mesh_components(primitive, "render", (2, 1), threshold=0.1)
    result, seam_surface = merged.surfaces
    edit = merged.metadata["last_topology_edit"]

    assert result.vertices == ((0.0, 0.0, 0.0), (1.0, 0.025, 0.0), (0.0, 1.0, 0.0))
    assert result.faces == ((0, 1, 2),)
    assert result.face_mats == (7,)
    assert seam_surface.vertices[0] == (1.0, 0.025, 0.0)
    assert seam_surface.uvs == detail.uvs
    assert seam_surface.uvs_lm == detail.uvs_lm
    assert seam_surface.normals == detail.normals
    assert seam_surface.face_mats == detail.face_mats
    assert edit["operation"] == "merge_components"
    assert edit["mode"] == "vertices"
    assert edit["selected"] == [1, 2]
    assert edit["merged_groups"][0]["centroid"] == [1.0, 0.025, 0.0]
    assert edit["dropped_faces_by_mesh_role"] == {"render": 1, "imported_srf_1": 0}
    assert edit["seam_policy"] == "positions_merged_uv_lightmap_normal_records_preserved"
    _assert_channels(result)
    _assert_channels(seam_surface)


def test_merge_two_border_edges_chooses_nearest_pairing_and_stitches_manifold_shells() -> None:
    surface = _surface(
        (
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
            (0.0, -0.05, 0.0), (1.0, -0.05, 0.0), (1.0, -1.0, 0.0),
        ),
        ((0, 1, 2), (4, 3, 5)),
        face_mats=(3, 9),
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="gredge", surfaces=(surface,))

    merged = merge_imported_mesh_components(
        primitive,
        "render",
        border_edges=((3, 4), (1, 0)),
        threshold=0.1,
    )
    result = merged.surfaces[0]
    edit = merged.metadata["last_topology_edit"]
    topology = MeshTopology.build(result.vertices, result.faces)
    audit = topology.validate_manifold_state()

    assert result.vertices[0] == result.vertices[3] == (0.0, -0.025, 0.0)
    assert result.vertices[1] == result.vertices[4] == (1.0, -0.025, 0.0)
    assert result.uvs == surface.uvs
    assert result.uvs_lm == surface.uvs_lm
    assert result.normals == surface.normals
    assert result.face_mats == surface.face_mats
    assert edit["mode"] == "border_edges"
    assert edit["selected"] == [[0, 1], [3, 4]]
    assert not audit.non_manifold_edges
    assert not audit.inconsistent_winding_edges
    assert not audit.branched_boundaries
    shared = tuple(sorted((topology.raw_to_geometric_vertex[0], topology.raw_to_geometric_vertex[1])))
    assert len(topology.geometric_edge_to_faces[shared]) == 2
    _assert_channels(result)


def test_merge_refuses_threshold_miss_and_non_manifold_result_atomically() -> None:
    border_surface = _surface(
        (
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
            (0.0, -0.05, 0.0), (1.0, -0.05, 0.0), (1.0, -1.0, 0.0),
        ),
        ((0, 1, 2), (4, 3, 5)),
        face_mats=(3, 9),
    )
    border_primitive = ImportedMeshRoomPrimitive(room_resref="gredge", surfaces=(border_surface,))
    try:
        merge_imported_mesh_components(
            border_primitive,
            "render",
            border_edges=((0, 1), (3, 4)),
            threshold=0.01,
        )
    except ValueError as exc:
        assert "exceeds the Merge threshold" in str(exc)
    else:
        raise AssertionError("Merge must refuse border edges beyond its threshold")
    assert border_primitive.surfaces[0] is border_surface

    non_manifold_source = _surface(
        (
            (0.0, 0.0, 0.0), (0.0, 0.05, 0.0), (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0), (1.0, 1.0, 0.0), (1.0, -1.0, 0.0),
        ),
        ((0, 2, 3), (1, 4, 2), (2, 0, 5)),
        face_mats=(2, 4, 6),
    )
    non_manifold_primitive = ImportedMeshRoomPrimitive(
        room_resref="grreject",
        surfaces=(non_manifold_source,),
    )
    try:
        merge_imported_mesh_components(non_manifold_primitive, "render", (0, 1), threshold=0.1)
    except ValueError as exc:
        assert "non-manifold" in str(exc)
    else:
        raise AssertionError("Merge must refuse output with a three-face edge")
    assert non_manifold_primitive.surfaces[0] is non_manifold_source


def test_fill_planar_boundary_closes_open_cube_with_valid_winding() -> None:
    vertices = (
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0), (0.0, 1.0, 1.0),
    )
    faces = (
        (0, 2, 1), (0, 3, 2),  # bottom, outward -Z
        (0, 5, 4), (0, 1, 5),  # front, outward -Y
        (1, 6, 5), (1, 2, 6),  # right, outward +X
        (2, 7, 6), (2, 3, 7),  # back, outward +Y
        (3, 4, 7), (3, 0, 4),  # left, outward -X
    )
    surface = _surface(vertices, faces, face_mats=(2,) * len(faces))
    primitive = ImportedMeshRoomPrimitive(room_resref="grfill", surfaces=(surface,))

    filled = fill_imported_mesh_boundary_loop(primitive, "render", (4, 5, 6, 7))
    result = filled.surfaces[0]
    audit = MeshTopology.build(result.vertices, result.faces).validate_manifold_state()
    assert len(result.faces) == len(faces) + 2
    assert not audit.border_edges
    assert not audit.degenerate_faces
    assert not audit.non_manifold_edges
    assert not audit.inconsistent_winding_edges
    assert result.face_mats[-2:] == (2, 2)
    assert filled.metadata["last_topology_edit"]["operation"] == "fill_boundary_loop"
    _assert_channels(result)


def _normal_at(surface: ImportedMeshSurface, face_index: int, point) -> tuple[float, float, float]:
    for raw in surface.faces[face_index]:
        if surface.vertices[raw] == point:
            return surface.normals[raw]
    raise AssertionError(f"point {point!r} is not on face {face_index}")


def test_soften_and_harden_edges_write_distinct_real_corner_normals() -> None:
    vertices = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    faces = ((0, 1, 2), (1, 0, 3))
    surface = _surface(vertices, faces, face_mats=(6, 6))
    primitive = ImportedMeshRoomPrimitive(room_resref="grnorm", surfaces=(surface,))

    hardened = harden_imported_mesh_edges(primitive, "render", (0, 1)).surfaces[0]
    hard_first = _normal_at(hardened, 0, (0.0, 0.0, 0.0))
    hard_second = _normal_at(hardened, 1, (0.0, 0.0, 0.0))
    assert hard_first == (0.0, 0.0, 1.0)
    assert hard_second == (0.0, 1.0, 0.0)

    softened = soften_imported_mesh_edges(primitive, "render", (0, 1)).surfaces[0]
    soft_first = _normal_at(softened, 0, (0.0, 0.0, 0.0))
    soft_second = _normal_at(softened, 1, (0.0, 0.0, 0.0))
    assert all(abs(first - second) < 1.0e-9 for first, second in zip(soft_first, soft_second))
    assert abs(soft_first[1] - (1.0 / math.sqrt(2.0))) < 1.0e-9
    assert abs(soft_first[2] - (1.0 / math.sqrt(2.0))) < 1.0e-9
    assert hardened.normals != surface.normals
    assert softened.normals != surface.normals
    _assert_channels(hardened)
    _assert_channels(softened)


def test_arbitrary_face_split_projects_and_interpolates_every_channel() -> None:
    surface = ImportedMeshSurface(
        name="triangle",
        texture="lda_floor01",
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        faces=((0, 1, 2),),
        face_mats=(7,),
        uvs=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        normals=((0.0, 0.0, 1.0),) * 3,
        lightmap="lda_floor01lm",
        uvs_lm=((0.1, 0.1), (0.9, 0.1), (0.1, 0.9)),
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="grcut", surfaces=(surface,))

    split = split_imported_mesh_face_at_point(primitive, "render", 0, (0.25, 0.25, 2.0))
    result = split.surfaces[0]
    inserted = result.vertices.index((0.25, 0.25, 0.0))
    assert result.uvs[inserted] == (0.25, 0.25)
    assert all(abs(value - expected) < 1.0e-9 for value, expected in zip(result.uvs_lm[inserted], (0.3, 0.3)))
    assert result.normals[inserted] == (0.0, 0.0, 1.0)
    assert result.face_mats == (7, 7, 7)
    assert split.metadata["last_topology_edit"]["barycentric"] == [0.5, 0.25, 0.25]
    _assert_channels(result)

    try:
        split_imported_mesh_face_at_point(primitive, "render", 0, (0.5, 0.0, 0.0))
    except ValueError as exc:
        assert "edge or vertex" in str(exc)
    else:
        raise AssertionError("an edge hit must not create a one-face T-junction")
