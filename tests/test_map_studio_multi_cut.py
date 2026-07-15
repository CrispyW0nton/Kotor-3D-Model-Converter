"""Focused contracts for the non-mutating Map Studio Multi-Cut core."""

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
    ImportedMeshRoomPrimitive,
    ImportedMeshSurface,
)
from core.modules.map_studio_multi_cut import (  # noqa: E402
    MultiCutAnchor,
    MultiCutAnchorKind,
    MultiCutSession,
    MultiCutSessionState,
    anchor_from_surface_hit,
)


def _strip() -> ImportedMeshRoomPrimitive:
    vertices = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (1.0, 1.0, 0.0),
        (2.0, 1.0, 0.0),
    )
    surface = ImportedMeshSurface(
        name="quad_strip",
        texture="lda_floor01",
        vertices=vertices,
        faces=((0, 1, 4), (0, 4, 3), (1, 2, 5), (1, 5, 4)),
        face_mats=(7, 7, 9, 9),
        uvs=tuple((point[0] * 0.5, point[1]) for point in vertices),
        normals=((0.0, 0.0, 1.0),) * len(vertices),
        lightmap="lda_floor01lm",
        texture_names=("lda_floor01", "lda_floor01lm"),
        tex_count=2,
        uvs_lm=tuple((0.1 + point[0] * 0.2, 0.2 + point[1] * 0.2) for point in vertices),
    )
    return ImportedMeshRoomPrimitive(
        room_resref="gr_multicut",
        surfaces=(surface,),
        game="K2",
        metadata={"author_note": "source remains unchanged"},
    )


def _triangle_area(vertices: tuple[tuple[float, float, float], ...], face: tuple[int, int, int]) -> float:
    a, b, c = (vertices[index] for index in face)
    return abs(
        ((b[0] - a[0]) * (c[1] - a[1]))
        - ((b[1] - a[1]) * (c[0] - a[0]))
    ) * 0.5


def _valid_strip_session() -> MultiCutSession:
    primitive = _strip()
    surface = primitive.surfaces[0]
    first = anchor_from_surface_hit(surface, 1, (0.25, 0.5, 0.0))
    second = anchor_from_surface_hit(surface, 2, (1.75, 0.5, 0.0))
    return MultiCutSession.begin(primitive, "render").add_anchor(first).add_anchor(second)


def test_two_anchor_preview_is_non_mutating_and_commit_is_deterministic() -> None:
    primitive = _strip()
    source_surface = primitive.surfaces[0]
    first = anchor_from_surface_hit(source_surface, 1, (0.25, 0.5, 0.0))
    second = anchor_from_surface_hit(source_surface, 2, (1.75, 0.5, 0.0))
    session = MultiCutSession.begin(primitive, "render").add_anchor(first).add_anchor(second)

    assert session.state == MultiCutSessionState.PREVIEW_VALID
    preview = session.preview()
    committed = session.commit()
    assert preview.ok and committed.ok
    assert preview.preview is True and committed.preview is False
    assert preview.result_fingerprint == committed.result_fingerprint
    assert preview.primitive.surfaces == committed.primitive.surfaces
    assert primitive.surfaces[0] == source_surface
    assert primitive.metadata == {"author_note": "source remains unchanged"}
    assert session.source_primitive.metadata == {"author_note": "source remains unchanged"}


def test_cut_preserves_area_channels_materials_and_manifold_state() -> None:
    source = _strip().surfaces[0]
    evaluation = _valid_strip_session().commit()
    assert evaluation.ok
    result = evaluation.primitive.surfaces[0]

    assert len(result.vertices) > len(source.vertices)
    assert len(result.faces) > len(source.faces)
    assert len(result.uvs) == len(result.vertices)
    assert len(result.normals) == len(result.vertices)
    assert len(result.uvs_lm) == len(result.vertices)
    assert len(result.face_mats) == len(result.faces)
    assert set(result.face_mats) == {7, 9}
    assert sum(_triangle_area(source.vertices, face) for face in source.faces) == pytest.approx(
        sum(_triangle_area(result.vertices, face) for face in result.faces)
    )
    audit = MeshTopology.build(result.vertices, result.faces).validate_manifold_state()
    assert not audit.invalid_faces
    assert not audit.degenerate_faces
    assert not audit.non_manifold_edges
    assert not audit.inconsistent_winding_edges


def test_evaluation_exposes_one_to_many_component_remap_and_cut_chain() -> None:
    source = _strip().surfaces[0]
    evaluation = _valid_strip_session().preview()
    assert evaluation.ok and evaluation.remap is not None
    remap = evaluation.remap

    assert len(remap.old_vertex_to_new) == len(source.vertices)
    assert len(remap.new_vertex_to_old) == len(evaluation.primitive.surfaces[0].vertices)
    assert len(remap.old_face_to_new) == len(source.faces)
    assert len(remap.new_face_to_old) == len(evaluation.primitive.surfaces[0].faces)
    assert all(len(new_faces) > 1 for new_faces in remap.old_face_to_new)
    assert remap.created_vertices
    assert remap.created_faces
    assert evaluation.affected_faces == (1, 0, 3, 2)
    assert len(evaluation.cut_edges) == len(evaluation.affected_faces)
    assert any(len(descendants) > 1 for descendants in remap.old_vertex_to_new)


def test_hit_conversion_produces_stable_vertex_edge_and_face_anchors() -> None:
    surface = _strip().surfaces[0]
    vertex = anchor_from_surface_hit(surface, 0, (0.0, 0.0, 0.0))
    edge = anchor_from_surface_hit(surface, 0, (0.5, 0.0, 0.0))
    face = anchor_from_surface_hit(surface, 0, (0.75, 0.25, 0.0))

    assert vertex.kind == MultiCutAnchorKind.VERTEX
    assert vertex.vertex_index == 0
    assert edge.kind == MultiCutAnchorKind.EDGE
    assert set(edge.edge_vertices) == {0, 1}
    assert edge.edge_parameter == pytest.approx(0.5)
    assert face.kind == MultiCutAnchorKind.FACE
    assert sum(face.barycentric) == pytest.approx(1.0)


def test_backspace_clear_and_escape_restore_exact_before_state() -> None:
    primitive = _strip()
    first = anchor_from_surface_hit(primitive.surfaces[0], 1, (0.25, 0.5, 0.0))
    session = MultiCutSession.begin(primitive, "render").add_anchor(first)

    assert session.state == MultiCutSessionState.BUILDING
    assert session.pop_anchor().state == MultiCutSessionState.ARMED_EMPTY
    assert session.clear().anchors == ()
    cancelled = session.cancel()
    assert cancelled.state == MultiCutSessionState.INACTIVE
    assert cancelled.anchors == ()
    assert cancelled.source_primitive == primitive


def test_invalid_paths_are_diagnostic_and_never_return_changed_geometry() -> None:
    primitive = _strip()
    surface = primitive.surfaces[0]
    first = anchor_from_surface_hit(surface, 0, (0.75, 0.15, 0.0))
    second = anchor_from_surface_hit(surface, 0, (0.70, 0.25, 0.0))
    session = MultiCutSession.begin(primitive, "render").add_anchor(first).add_anchor(second)

    assert session.state == MultiCutSessionState.PREVIEW_INVALID
    evaluation = session.preview()
    assert not evaluation.ok
    assert evaluation.remap is None
    assert evaluation.primitive == session.source_primitive
    assert "two interior points" in evaluation.diagnostics[0]


def test_non_coplanar_connected_faces_are_refused() -> None:
    surface = ImportedMeshSurface(
        name="crease",
        texture="lda_wall01",
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 1.0)),
        faces=((0, 1, 2), (1, 3, 2)),
        uvs=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)),
        normals=((0.0, 0.0, 1.0),) * 4,
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="crease", surfaces=(surface,))
    first = MultiCutAnchor.face(0, (0.6, 0.2, 0.2))
    second = MultiCutAnchor.face(1, (0.2, 0.6, 0.2))
    session = MultiCutSession.begin(primitive, "render").add_anchor(first).add_anchor(second)

    assert session.state == MultiCutSessionState.PREVIEW_INVALID
    evaluation = session.commit()
    assert not evaluation.ok
    assert evaluation.primitive.surfaces[0] == surface
    assert "coplanar" in evaluation.diagnostics[0]
