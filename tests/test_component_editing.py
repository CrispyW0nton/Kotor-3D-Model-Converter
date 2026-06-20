from __future__ import annotations

import sys
from pathlib import Path


def _install_native_geometry_path() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Domain.Core.Geometry/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2601_component_edit_audit_marks_snap_as_geometry_change_not_topology() -> None:
    _install_native_geometry_path()

    from src.core.geometry import audit_component_edit_result, component_mesh, snap_vertex_to_vertex

    mesh = component_mesh(
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
    )

    audit = audit_component_edit_result(
        snap_vertex_to_vertex(mesh, 0, 1),
        component_kind="room vertex",
        affects_walkmesh=True,
    )

    assert audit.geometry_changed is True
    assert audit.topology_changed is False
    assert audit.walkmesh_review_required is True
    assert audit.export_candidate_stale is True
    assert audit.game_proof_stale is True
    assert audit.stale_outputs == ("MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod")
    assert audit.next_action == "Review WOK/walkability, regenerate affected runtime resources, then verify in game."
    assert "snap_vertex_to_vertex on room vertex: 1 vertex change(s)." == audit.summary
    assert "Re-run WOK/walkability preview if this edit affects traversal or doorway seams." in audit.validation_messages
    assert "Review WOK surface intent before exporting the module." in audit.validation_messages


def test_t2601_component_edit_audit_marks_weld_as_topology_change() -> None:
    _install_native_geometry_path()

    from src.core.geometry import audit_component_edit_result, component_mesh, weld_vertices

    mesh = component_mesh(
        vertices=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        faces=[(0, 1, 2), (0, 2, 3)],
    )

    audit = audit_component_edit_result(
        weld_vertices(mesh, (0, 1), target_index=0),
        component_kind="walkmesh seam",
        affects_walkmesh=True,
    )

    assert audit.geometry_changed is True
    assert audit.topology_changed is True
    assert audit.walkmesh_review_required is True
    assert audit.export_candidate_stale is True
    assert audit.game_proof_stale is True
    assert audit.stale_outputs == ("MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod")
    assert audit.next_action == "Regenerate room MDL/MDX/WOK, rebuild LYT/VIS/PTH, package the .mod, then verify in game."
    assert audit.metadata["removed_vertex_count"] == 1
    assert "Re-run MDL/MDX/WOK generation and inspect LYT/VIS/PTH readiness before packaging." in audit.validation_messages


def test_t2601_component_edit_audit_marks_bridge_as_topology_change() -> None:
    _install_native_geometry_path()

    from src.core.geometry import audit_component_edit_result, bridge_edges, component_mesh

    mesh = component_mesh(
        vertices=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0), (0.0, 2.0, 0.0)],
        faces=(),
    )

    audit = audit_component_edit_result(
        bridge_edges(mesh, (0, 1), (3, 2)),
        component_kind="room seam",
        affects_walkmesh=True,
    )

    assert audit.geometry_changed is True
    assert audit.topology_changed is True
    assert audit.walkmesh_review_required is True
    assert audit.stale_outputs == ("MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod")
    assert audit.summary == "bridge_edges on room seam: 1 added face(s)."
    assert audit.next_action == "Regenerate room MDL/MDX/WOK, rebuild LYT/VIS/PTH, package the .mod, then verify in game."


def test_t2601_bridge_edges_creates_conservative_quad_for_room_seams() -> None:
    _install_native_geometry_path()

    from src.core.geometry import bridge_edges, component_mesh

    mesh = component_mesh(
        vertices=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0), (0.0, 2.0, 0.0)],
        faces=(),
        metadata={"room": "grbridge"},
    )

    bridged = bridge_edges(mesh, (0, 1), (3, 2))

    assert bridged.mesh.faces == ((0, 1, 2, 3),)
    assert bridged.mesh.metadata["room"] == "grbridge"
    assert bridged.metadata["operation"] == "bridge_edges"
    assert bridged.metadata["added_face_count"] == 1
    assert bridged.metadata["first_edge"] == (0, 1)
    assert bridged.metadata["second_edge"] == (3, 2)


def test_t2601_bridge_edges_rejects_degenerate_or_shared_edges() -> None:
    _install_native_geometry_path()

    import pytest

    from src.core.geometry import bridge_edges, component_mesh

    mesh = component_mesh(vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)])

    with pytest.raises(ValueError, match="four unique vertices"):
        bridge_edges(mesh, (0, 1), (1, 2))
    with pytest.raises(ValueError, match="zero-length"):
        bridge_edges(mesh, (0, 0), (1, 2))


def test_t2601_extrude_face_creates_side_faces_and_cap() -> None:
    _install_native_geometry_path()

    from src.core.geometry import component_mesh, extrude_face

    mesh = component_mesh(
        vertices=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0), (0.0, 2.0, 0.0)],
        faces=[(0, 1, 2, 3)],
        metadata={"room": "grextrude"},
    )

    extruded = extrude_face(mesh, 0, distance=2.0, direction=(0.0, 0.0, 1.0))

    assert extruded.removed_face_count == 1
    assert extruded.mesh.metadata["room"] == "grextrude"
    assert extruded.mesh.vertices[4:] == (
        (0.0, 0.0, 2.0),
        (2.0, 0.0, 2.0),
        (2.0, 2.0, 2.0),
        (0.0, 2.0, 2.0),
    )
    assert extruded.mesh.faces == (
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
        (4, 5, 6, 7),
    )
    assert extruded.metadata["operation"] == "extrude_face"
    assert extruded.metadata["added_vertex_count"] == 4
    assert extruded.metadata["added_face_count"] == 5


def test_t2601_component_edit_audit_marks_extrude_as_topology_change() -> None:
    _install_native_geometry_path()

    from src.core.geometry import audit_component_edit_result, component_mesh, extrude_face

    mesh = component_mesh(
        vertices=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0), (0.0, 2.0, 0.0)],
        faces=[(0, 1, 2, 3)],
    )

    audit = audit_component_edit_result(
        extrude_face(mesh, 0, distance=1.0),
        component_kind="room face",
        affects_walkmesh=True,
    )

    assert audit.geometry_changed is True
    assert audit.topology_changed is True
    assert audit.metadata["added_vertex_count"] == 4
    assert audit.metadata["added_face_count"] == 5
    assert audit.summary == "extrude_face on room face: 4 added vertex(s), 5 added face(s), 1 removed face(s)."
    assert audit.next_action == "Regenerate room MDL/MDX/WOK, rebuild LYT/VIS/PTH, package the .mod, then verify in game."


def test_t2601_component_edit_audit_reports_degenerate_triangulation_cleanup() -> None:
    _install_native_geometry_path()

    from src.core.geometry import audit_component_edit_result, component_mesh, triangulate_faces

    mesh = component_mesh(
        vertices=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        faces=[(0, 1, 2, 3, 4), (0, 0, 1)],
    )

    audit = audit_component_edit_result(
        triangulate_faces(mesh),
        component_kind="wok face",
        affects_walkmesh=True,
    )

    assert audit.geometry_changed is True
    assert audit.topology_changed is True
    assert audit.metadata["triangulated_face_count"] == 1
    assert audit.metadata["skipped_triangle_count"] == 1
    assert audit.summary == (
        "triangulate_faces on wok face: 1 removed face(s), "
        "1 triangulated face set(s), 1 skipped degenerate triangle(s)."
    )
    assert "Some fan triangles collapsed during triangulation; inspect topology before export." in audit.validation_messages
    assert audit.next_action == "Regenerate room MDL/MDX/WOK, rebuild LYT/VIS/PTH, package the .mod, then verify in game."


def test_t2601_extrude_face_rejects_invalid_or_degenerate_faces() -> None:
    _install_native_geometry_path()

    import pytest

    from src.core.geometry import component_mesh, extrude_face

    mesh = component_mesh(
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        faces=[(0, 1, 2)],
    )

    with pytest.raises(ValueError, match="distance must be positive"):
        extrude_face(mesh, 0, distance=0.0)
    with pytest.raises(ValueError, match="normal cannot be zero-length"):
        extrude_face(mesh, 0, distance=1.0)
    with pytest.raises(ValueError, match="missing face"):
        extrude_face(mesh, 9, distance=1.0, direction=(0.0, 0.0, 1.0))


def test_t2601_component_edit_audit_keeps_noop_from_invalidating_export() -> None:
    _install_native_geometry_path()

    from src.core.geometry import audit_component_edit_result, component_mesh, weld_vertices

    mesh = component_mesh(vertices=[(0.0, 0.0, 0.0)], faces=())

    audit = audit_component_edit_result(
        weld_vertices(mesh, (0,)),
        component_kind="room vertex",
        affects_walkmesh=True,
    )

    assert audit.geometry_changed is False
    assert audit.topology_changed is False
    assert audit.walkmesh_review_required is False
    assert audit.export_candidate_stale is False
    assert audit.game_proof_stale is False
    assert audit.stale_outputs == ()
    assert audit.next_action == "No export action required."
    assert audit.summary == "component_edit on room vertex: no geometry changes."
    assert audit.validation_messages == ("Select at least two vertices to weld.",)
