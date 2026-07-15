"""Focused regressions for Map Studio's atomic multi-edge bevel path."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
for rel in reversed(
    (
        "native/GhostRigger.Core.Scene/Python/src",
        "native/GhostRigger.Core.Resources/Python/src",
        "native/GhostRigger.Core.Project/Python/src",
        "native/GhostRigger.Core.IO/Python/src",
        "native/GhostRigger.Core.Workflow/Python/src",
        "native/GhostRigger.Core.Math/Python/src",
        "native/GhostRigger.Core.Rendering/Python/src",
        ".",
    )
):
    path = str((ROOT / rel).resolve())
    if path not in sys.path:
        sys.path.insert(0, path)

from core.geometry.mesh_topology import MeshTopology  # noqa: E402
from core.modules.authored_imported_mesh import (  # noqa: E402
    ImportedMeshRoomPrimitive,
    ImportedMeshSurface,
    bevel_imported_mesh_edges,
)
from core.modules.module_editor_controller import ModuleEditorController  # noqa: E402


def _surface(vertices, faces) -> ImportedMeshSurface:
    return ImportedMeshSurface(
        name="render",
        texture="lda_wall01",
        vertices=tuple(vertices),
        faces=tuple(faces),
        face_mats=tuple(10 + index for index in range(len(faces))),
        uvs=tuple((float(index) + 0.125, float(index) + 0.625) for index in range(len(vertices))),
        normals=tuple((0.0, 0.0, 1.0) for _ in vertices),
        lightmap="lda_wall01lm",
        texture_names=("lda_wall01", "lda_wall01lm"),
        tex_count=2,
        uvs_lm=tuple((0.05 + index * 0.01, 0.95 - index * 0.01) for index in range(len(vertices))),
    )


def _cube() -> ImportedMeshRoomPrimitive:
    surface = _surface(
        (
            (0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 4.0, 0.0), (0.0, 4.0, 0.0),
            (0.0, 0.0, 3.0), (4.0, 0.0, 3.0), (4.0, 4.0, 3.0), (0.0, 4.0, 3.0),
        ),
        (
            (0, 1, 2), (0, 2, 3),
            (4, 6, 5), (4, 7, 6),
            (0, 4, 5), (0, 5, 1),
            (1, 5, 6), (1, 6, 2),
            (2, 6, 7), (2, 7, 3),
            (3, 7, 4), (3, 4, 0),
        ),
    )
    return ImportedMeshRoomPrimitive(room_resref="grbevel", surfaces=(surface,), game="K2")


def _straight_crease_prism() -> ImportedMeshRoomPrimitive:
    surface = _surface(
        (
            (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (4.0, 0.0, 0.0),
            (0.0, 2.0, 0.0), (2.0, 2.0, 0.0), (4.0, 2.0, 0.0),
            (0.0, 0.0, 2.0), (2.0, 0.0, 2.0), (4.0, 0.0, 2.0),
            (0.0, 2.0, 2.0), (2.0, 2.0, 2.0), (4.0, 2.0, 2.0),
        ),
        (
            (0, 4, 1), (0, 3, 4), (1, 5, 2), (1, 4, 5),
            (6, 7, 10), (6, 10, 9), (7, 8, 11), (7, 11, 10),
            (0, 1, 7), (0, 7, 6), (1, 2, 8), (1, 8, 7),
            (3, 10, 4), (3, 9, 10), (4, 11, 5), (4, 10, 11),
            (2, 5, 11), (2, 11, 8), (0, 6, 9), (0, 9, 3),
        ),
    )
    return ImportedMeshRoomPrimitive(room_resref="grbevel", surfaces=(surface,), game="K2")


def _assert_valid_channels(result: ImportedMeshRoomPrimitive) -> None:
    surface = result.surfaces[0]
    assert len(surface.uvs) == len(surface.vertices)
    assert len(surface.uvs_lm) == len(surface.vertices)
    assert len(surface.normals) == len(surface.vertices)
    assert len(surface.face_mats) == len(surface.faces)
    audit = MeshTopology.build(surface.vertices, surface.faces).validate_manifold_state()
    assert not audit.degenerate_faces
    assert not audit.non_manifold_edges
    assert not audit.inconsistent_winding_edges


def test_atomic_bevel_handles_two_disconnected_edges_without_dropping_channels() -> None:
    primitive = _cube()
    result = bevel_imported_mesh_edges(
        primitive,
        "render",
        ((0, 1), (6, 7)),
        0.25,
        segments=3,
        profile=0.75,
        uv_mode="preserve",
    )

    _assert_valid_channels(result)
    edit = result.metadata["last_topology_edit"]
    assert edit["operation"] == "multi_edge_bevel"
    assert edit["source_edge_count"] == 2
    assert edit["component_count"] == 2
    assert edit["component_kinds"] == ["independent_edge", "independent_edge"]
    assert edit["atomic"] is True
    assert result.surfaces[0].face_mats[:12] == primitive.surfaces[0].face_mats


def test_atomic_bevel_shares_cross_sections_along_a_straight_crease_chain() -> None:
    primitive = _straight_crease_prism()
    result = bevel_imported_mesh_edges(
        primitive,
        "render",
        ((0, 1), (1, 2)),
        0.2,
        segments=2,
        profile=1.0,
    )

    _assert_valid_channels(result)
    edit = result.metadata["last_topology_edit"]
    assert edit["operation"] == "multi_edge_bevel"
    assert edit["component_kinds"] == ["continuous_crease_chain"]
    assert edit["source_edge_count"] == 2


def test_turning_edge_chain_is_rejected_without_mutating_the_source() -> None:
    primitive = _cube()
    source_surface = primitive.surfaces[0]

    with pytest.raises(ValueError, match="continuous straight crease"):
        bevel_imported_mesh_edges(primitive, "render", ((0, 1), (1, 2)), 0.25)

    assert primitive.surfaces[0] == source_surface
    assert primitive.metadata == {}


class _ControllerHarness:
    def __init__(self, primitive: ImportedMeshRoomPrimitive):
        self.primitive = primitive
        self.result = primitive
        self.apply_count = 0
        self.action_key = ""

    def _apply_imported_mesh_room_edit(self, *, room_resref, action_key, label, editor):
        assert room_resref == "grbevel"
        self.apply_count += 1
        self.action_key = action_key
        self.result = editor(self.primitive)
        return True, label


def test_controller_commits_multi_edge_bevel_as_one_undoable_edit() -> None:
    harness = _ControllerHarness(_cube())
    ok, message = ModuleEditorController.apply_imported_mesh_room_component_op(
        harness,
        room_resref="grbevel",
        op="multi_edge_bevel",
        mesh_role="render",
        face_index=-1,
        edge_vertex_indices=((0, 1), (6, 7)),
        amount=0.2,
        segments=2,
        profile=0.6,
    )

    assert ok is True
    assert harness.apply_count == 1
    assert harness.action_key == "map_studio.imported_mesh.multi_edge_bevel"
    assert "Bevel 2 edges" in message
    assert harness.result.metadata["last_topology_edit"]["atomic"] is True


def test_window_and_panel_route_all_selected_edges_instead_of_the_first() -> None:
    panel_source = (
        ROOT
        / "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py"
    ).read_text(encoding="utf-8")
    window_source = (
        ROOT / "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert '"kind": "multi_edge_bevel"' in panel_source
    assert '"edge_vertex_indices": multi_edges' in panel_source
    assert "len(selection) > 1" in panel_source
    assert 'op="multi_edge_bevel" if len(multi_edges) > 1 else "edge_bevel"' in window_source
    assert "edge_vertex_indices=multi_edges" in window_source
