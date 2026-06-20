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
    assert audit.metadata["removed_vertex_count"] == 1
    assert "Re-run MDL/MDX/WOK generation and inspect LYT/VIS/PTH readiness before packaging." in audit.validation_messages


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
    assert audit.summary == "component_edit on room vertex: no geometry changes."
    assert audit.validation_messages == ("Select at least two vertices to weld.",)
