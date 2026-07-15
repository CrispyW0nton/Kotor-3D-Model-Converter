from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest


def _install_math_payload() -> None:
    repo = Path(__file__).resolve().parents[1]
    path = str((repo / "native/GhostRigger.Core.Math/Python").resolve())
    if path not in sys.path:
        sys.path.insert(0, path)


_install_math_payload()

from src.core.geometry.mesh_topology import MeshTopology
from src.core.geometry.polygon_mesh_operations import AttributeChannel, IndexedPolygonMesh
from src.core.geometry.solid_boolean import difference_closed_solid_meshes


_CUBE_FACES = (
    (0, 2, 1),
    (0, 3, 2),
    (4, 5, 6),
    (4, 6, 7),
    (0, 1, 5),
    (0, 5, 4),
    (3, 7, 6),
    (3, 6, 2),
    (0, 4, 7),
    (0, 7, 3),
    (1, 2, 6),
    (1, 6, 5),
)


def _cube(*, size: float, center=(0.0, 0.0, 0.0), source: str) -> IndexedPolygonMesh:
    half = size * 0.5
    cx, cy, cz = center
    vertices = tuple(
        (cx + x * half, cy + y * half, cz + z * half)
        for x, y, z in (
            (-1, -1, -1),
            (1, -1, -1),
            (1, 1, -1),
            (-1, 1, -1),
            (-1, -1, 1),
            (1, -1, 1),
            (1, 1, 1),
            (-1, 1, 1),
        )
    )
    normals = []
    for x, y, z in vertices:
        direction = (x - cx, y - cy, z - cz)
        length = math.sqrt(sum(component * component for component in direction))
        normals.append(tuple(component / length for component in direction))
    uv0_rows = tuple(
        tuple(
            (
                ((vertices[index][0] - cx) / size) + 0.5,
                ((vertices[index][2] - cz) / size) + 0.5,
            )
            for index in face
        )
        for face in _CUBE_FACES
    )
    lightmap_uv = tuple(
        (((x - cx) / size) + 0.5, ((y - cy) / size) + 0.5)
        for x, y, _z in vertices
    )
    return IndexedPolygonMesh.build(
        vertices,
        _CUBE_FACES,
        vertex_channels={
            "normals": AttributeChannel.build(normals, semantic="normal"),
            "uvs_lm": AttributeChannel.build(lightmap_uv),
        },
        corner_channels={"uv0": AttributeChannel.build(uv0_rows)},
        face_channels={
            "material": AttributeChannel.build(
                (f"{source}_material" for _face in _CUBE_FACES),
                default="default_material",
            )
        },
        metadata={"source_id": source},
    )


def test_closed_cube_difference_is_deterministic_and_preserves_attributes() -> None:
    pytest.importorskip("manifold3d")
    target = _cube(size=2.0, source="target")
    cutter = _cube(size=1.0, source="cutter")

    first = difference_closed_solid_meshes(target, cutter)
    second = difference_closed_solid_meshes(target, cutter)

    assert first.ok is True
    assert first.mesh is not None
    assert first.mesh == second.mesh
    assert first.diagnostics.output_volume == pytest.approx(7.0)
    assert first.diagnostics.backend == "manifold3d"
    assert first.diagnostics.backend_version != "unavailable"
    assert first.diagnostics.dropped_channels == ()
    assert set(first.mesh.vertex_channels) == {"normals", "uv0", "uvs_lm"}
    assert set(first.mesh.face_channels["material"].values) == {
        "target_material",
        "cutter_material",
    }
    assert set(first.mesh.face_channels["boolean_source_operand"].values) == {"A", "B"}
    assert all(
        math.sqrt(sum(component * component for component in normal)) == pytest.approx(1.0)
        for normal in first.mesh.vertex_channels["normals"].values
    )
    assert len(first.mesh.vertex_channels["uv0"].values) == len(first.mesh.vertices)
    assert len(first.mesh.vertex_channels["uvs_lm"].values) == len(first.mesh.vertices)

    audit = MeshTopology.build(first.mesh.vertices, first.mesh.faces).validate_manifold_state()
    assert audit.border_edges == []
    assert audit.non_manifold_edges == []
    assert audit.inconsistent_winding_edges == []
    assert audit.degenerate_faces == []


def test_open_operand_is_rejected_without_mutating_either_input() -> None:
    target = _cube(size=2.0, source="target")
    closed_cutter = _cube(size=1.0, source="cutter")
    open_cutter = IndexedPolygonMesh.build(
        closed_cutter.vertices,
        closed_cutter.faces[:-1],
        vertex_channels=closed_cutter.vertex_channels,
        corner_channels={
            name: AttributeChannel.build(
                channel.values[:-1],
                semantic=channel.semantic,
                default=channel.default,
            )
            for name, channel in closed_cutter.corner_channels.items()
        },
        face_channels={
            name: AttributeChannel.build(
                channel.values[:-1],
                semantic=channel.semantic,
                default=channel.default,
            )
            for name, channel in closed_cutter.face_channels.items()
        },
        metadata=closed_cutter.metadata,
    )
    target_before = target
    cutter_before = open_cutter

    result = difference_closed_solid_meshes(target, open_cutter)

    assert result.ok is False
    assert result.mesh is None
    assert "open_boundary" in {issue.code for issue in result.diagnostics.errors}
    assert target == target_before
    assert open_cutter == cutter_before


def test_non_manifold_duplicate_face_is_rejected_atomically() -> None:
    target = _cube(size=2.0, source="target")
    cutter = _cube(size=1.0, source="cutter")
    invalid = IndexedPolygonMesh.build(
        cutter.vertices,
        (*cutter.faces, cutter.faces[0]),
    )

    result = difference_closed_solid_meshes(target, invalid)

    assert result.mesh is None
    codes = {issue.code for issue in result.diagnostics.errors}
    assert "non_manifold_edges" in codes
    assert "duplicate_faces" in codes


def test_inward_wound_operand_requires_reverse_before_difference() -> None:
    target = _cube(size=2.0, source="target")
    cutter = _cube(size=1.0, source="cutter")
    inward = IndexedPolygonMesh.build(
        cutter.vertices,
        (tuple(reversed(face)) for face in cutter.faces),
    )

    result = difference_closed_solid_meshes(target, inward)

    assert result.mesh is None
    assert "inward_winding" in {issue.code for issue in result.diagnostics.errors}


def test_output_triangle_budget_rejects_before_returning_replacement() -> None:
    pytest.importorskip("manifold3d")
    target = _cube(size=2.0, source="target")
    cutter = _cube(size=1.0, source="cutter")

    result = difference_closed_solid_meshes(target, cutter, max_output_triangles=12)

    assert result.mesh is None
    assert "output_triangle_limit" in {issue.code for issue in result.diagnostics.errors}
    assert result.diagnostics.output_triangles > 12


def test_missing_native_backend_returns_install_diagnostic(monkeypatch) -> None:
    import src.core.geometry.solid_boolean as solid_boolean

    target = _cube(size=2.0, source="target")
    cutter = _cube(size=1.0, source="cutter")

    def missing_backend():
        raise ImportError("test backend absence")

    monkeypatch.setattr(solid_boolean, "_import_manifold3d", missing_backend)
    result = solid_boolean.difference_closed_solid_meshes(target, cutter)

    assert result.mesh is None
    assert result.diagnostics.backend_version == "unavailable"
    assert "backend_unavailable" in {issue.code for issue in result.diagnostics.errors}
