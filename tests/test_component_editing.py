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
