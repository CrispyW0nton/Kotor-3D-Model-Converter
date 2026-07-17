"""Focused raw-WOK engine-contract tests for indexed topology and AABB data."""

from __future__ import annotations

import os
from pathlib import Path
import struct
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def _same_centroid_wok():
    _configure_native_python_roots()
    from src.core.modules.module_format import WOKData, WOKFace

    # Both triangles have centroid (1, 1, 0).  A value-based partition used to
    # lose one face here; the serialized AABB must retain one leaf per face.
    return WOKData(
        name="samecentre",
        verts=[
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (1.0, 3.0, 0.0),
            (0.0, 2.0, 0.0),
            (2.0, 2.0, 0.0),
            (1.0, -1.0, 0.0),
        ],
        faces=[WOKFace(0, 1, 2, 4), WOKFace(3, 4, 5, 4)],
    )


def test_raw_contract_accepts_duplicate_coordinate_index_seams() -> None:
    """Coincident coordinates with distinct indices remain intentional seams."""

    _configure_native_python_roots()
    from src.core.modules.module_format import WOKData, WOKFace
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    wok = WOKData(
        name="seam",
        verts=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        faces=[WOKFace(0, 1, 2, 4), WOKFace(3, 4, 5, 4)],
    )

    fingerprint, report = inspect_raw_wok_structure("seam", wok.to_bytes())

    assert not report.has_errors
    assert fingerprint.adjacency_count == 2
    assert fingerprint.adjacency_mismatch_count == 0
    assert fingerprint.adjacency_nonreciprocal_count == 0
    assert fingerprint.non_manifold_edge_count == 0
    assert fingerprint.perimeter_count == 2
    assert fingerprint.closed_perimeter_count == 2


def test_raw_contract_blocks_poisoned_adjacency_with_mismatch_and_nonreciprocal_evidence() -> None:
    _configure_native_python_roots()
    from src.core.modules.module_format import WOKData, WOKFace
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    # Faces 0 and 1 share face-0 edge 1 / face-1 edge 0 by raw vertex index.
    wok = WOKData(
        name="poisoned",
        verts=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
        ],
        faces=[WOKFace(0, 1, 2, 4), WOKFace(2, 1, 3, 4)],
    )
    raw = bytearray(wok.to_bytes())
    adjacency_count, adjacency_offset = struct.unpack_from("<II", raw, 112)
    assert adjacency_count == 2
    assert struct.unpack_from("<i", raw, adjacency_offset + 4)[0] == 3
    assert struct.unpack_from("<i", raw, adjacency_offset + 12)[0] == 1

    # Remove only face 0's side of the link.  Face 1 still points back, so the
    # table is both geometrically wrong and explicitly non-reciprocal.
    struct.pack_into("<i", raw, adjacency_offset + 4, -1)
    fingerprint, report = inspect_raw_wok_structure("poisoned", bytes(raw))
    codes = {issue.code for issue in report.issues}

    assert report.has_errors
    assert fingerprint.adjacency_mismatch_count >= 1
    assert fingerprint.adjacency_nonreciprocal_count >= 1
    assert any("adjacency" in code and "mismatch" in code for code in codes)
    assert any("adjacency" in code and "nonreciprocal" in code for code in codes)


def test_raw_contract_fingerprints_complete_same_centroid_aabb_tree() -> None:
    _configure_native_python_roots()
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    fingerprint, report = inspect_raw_wok_structure("samecentre", _same_centroid_wok().to_bytes())

    assert not report.has_errors
    assert fingerprint.face_count == 2
    assert fingerprint.aabb_count == 3
    assert fingerprint.aabb_leaf_count == 2
    assert fingerprint.aabb_covered_face_count == 2
    assert fingerprint.aabb_missing_face_count == 0
    assert fingerprint.aabb_reachable_count == 3


def test_raw_contract_blocks_duplicate_aabb_leaf_and_missing_face() -> None:
    _configure_native_python_roots()
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    raw = bytearray(_same_centroid_wok().to_bytes())
    aabb_count, aabb_offset, aabb_root = struct.unpack_from("<III", raw, 100)
    assert (aabb_count, aabb_root) == (3, 0)
    leaf_offsets = [
        aabb_offset + index * 44
        for index in range(aabb_count)
        if struct.unpack_from("<I", raw, aabb_offset + index * 44 + 24)[0] != 0xFFFFFFFF
    ]
    assert len(leaf_offsets) == 2
    first_face = struct.unpack_from("<I", raw, leaf_offsets[0] + 24)[0]
    struct.pack_into("<I", raw, leaf_offsets[1] + 24, first_face)

    fingerprint, report = inspect_raw_wok_structure("brokenaabb", bytes(raw))
    codes = {issue.code for issue in report.issues}

    assert report.has_errors
    assert fingerprint.aabb_leaf_count == 2
    assert fingerprint.aabb_covered_face_count == 1
    assert fingerprint.aabb_missing_face_count == 1
    assert fingerprint.aabb_reachable_count == 3
    assert "map.engine.wok.aabb_face_coverage_incomplete" in codes
    assert "map.engine.wok.aabb_face_coverage_duplicate" in codes


def test_empty_wok_requires_explicit_visual_only_classification() -> None:
    _configure_native_python_roots()
    from src.core.modules.module_format import WOKData
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    raw = WOKData(name="emptyvisual").to_bytes()
    default_fingerprint, default_report = inspect_raw_wok_structure("emptyvisual", raw)
    visual_fingerprint, visual_report = inspect_raw_wok_structure(
        "emptyvisual",
        raw,
        allow_empty_visual=True,
    )

    assert default_report.has_errors
    assert "map.engine.wok.geometry_empty" in {issue.code for issue in default_report.issues}
    assert not visual_report.has_errors
    assert default_fingerprint.face_count == visual_fingerprint.face_count == 0
    assert visual_fingerprint.aabb_count == 0
    assert visual_fingerprint.adjacency_count == 0
    assert visual_fingerprint.perimeter_count == 0


def test_nonwalk_only_wok_requires_explicit_visual_only_classification() -> None:
    _configure_native_python_roots()
    from src.core.modules.module_format import WOKData, WOKFace
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    raw = WOKData(
        name="collisionvisual",
        verts=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 7)],
    ).to_bytes()
    _default_fingerprint, default_report = inspect_raw_wok_structure("collisionvisual", raw)
    visual_fingerprint, visual_report = inspect_raw_wok_structure(
        "collisionvisual",
        raw,
        allow_empty_visual=True,
    )

    assert default_report.has_errors
    assert "map.engine.wok.no_walkable_faces" in {issue.code for issue in default_report.issues}
    assert not visual_report.has_errors
    assert visual_fingerprint.face_count == 1
    assert visual_fingerprint.walkable_face_count == 0
    assert visual_fingerprint.aabb_leaf_count == 1
    assert visual_fingerprint.adjacency_count == 0
    assert visual_fingerprint.perimeter_count == 0


def test_vertex_touching_walkable_islands_serialize_as_separate_closed_loops() -> None:
    """A shared point must not merge two otherwise disconnected topology fans."""

    _configure_native_python_roots()
    from src.core.modules.module_format import WOKData, WOKFace
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    wok = WOKData(
        name="vertex_touch",
        verts=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (-1.0, 0.0, 0.0),
            (0.0, -1.0, 0.0),
        ],
        faces=[WOKFace(0, 1, 2, 4), WOKFace(0, 3, 4, 4)],
    )

    raw = wok.to_bytes()
    perimeter_count, perimeter_offset = struct.unpack_from("<II", raw, 128)
    endpoints = [
        struct.unpack_from("<I", raw, perimeter_offset + index * 4)[0]
        for index in range(perimeter_count)
    ]
    fingerprint, report = inspect_raw_wok_structure("vertex_touch", raw)

    assert endpoints == [3, 6]
    assert fingerprint.perimeter_count == 2
    assert fingerprint.closed_perimeter_count == 2
    assert fingerprint.adjacency_mismatch_count == 0
    assert not report.has_errors


def test_writer_rejects_same_direction_adjacent_walkable_faces() -> None:
    _configure_native_python_roots()
    from src.core.modules.module_format import WOKData, WOKFace

    # Both triangles own edge 0->1 rather than opposing 0->1 / 1->0.  That is
    # not a consistently wound two-manifold floor and cannot form valid loops.
    wok = WOKData(
        name="same_direction",
        verts=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, -1.0, 0.0),
        ],
        faces=[WOKFace(0, 1, 2, 4), WOKFace(0, 1, 3, 4)],
    )

    with pytest.raises(ValueError, match="same-direction owners"):
        wok.to_bytes()


def test_auto_generator_keeps_floor_and_drops_render_walls_and_ceiling() -> None:
    """A render shell must compile to its walkable floor topology, not a cage."""

    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import (
        ImportedMeshRoomPrimitive,
        ImportedMeshSurface,
        generate_room_walkmesh_from_geometry,
    )
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    shell = ImportedMeshSurface(
        name="render_shell",
        texture="shell01",
        vertices=(
            # Up-facing two-triangle floor.
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
            # Vertical wall along the north edge.
            (0.0, 2.0, 0.0),
            (2.0, 2.0, 0.0),
            (2.0, 2.0, 3.0),
            (0.0, 2.0, 3.0),
            # Down-facing two-triangle ceiling.
            (0.0, 0.0, 3.0),
            (2.0, 0.0, 3.0),
            (2.0, 2.0, 3.0),
            (0.0, 2.0, 3.0),
        ),
        faces=(
            (0, 1, 2),
            (0, 2, 3),
            (4, 5, 6),
            (4, 6, 7),
            (8, 10, 9),
            (8, 11, 10),
        ),
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="floor_only", surfaces=(shell,))

    generated, generation = generate_room_walkmesh_from_geometry(primitive)

    assert generated is not primitive
    assert generated.wok is not None
    assert generation["floor_faces"] == 2
    assert generation["wall_faces"] == 2
    assert generation["dropped_wall_faces"] == 2
    assert generation["dropped_ceiling_faces"] == 2
    assert generation["total_faces"] == 2
    assert len(generated.wok.faces) == 2
    assert all(int(face.surface) == 4 for face in generated.wok.faces)
    assert all(abs(generated.wok.verts[index][2]) < 1.0e-9 for face in generated.wok.faces for index in (face.v1, face.v2, face.v3))
    fingerprint, report = inspect_raw_wok_structure("floor_only", generated.wok.to_bytes())
    assert fingerprint.face_count == 2
    assert fingerprint.walkable_face_count == 2
    assert fingerprint.closed_perimeter_count == 1
    assert not report.has_errors


def test_auto_generator_filters_repeated_index_and_zero_area_render_triangles() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import (
        ImportedMeshRoomPrimitive,
        ImportedMeshSurface,
        generate_room_walkmesh_from_geometry,
    )
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    surface = ImportedMeshSurface(
        name="floor_with_bad_faces",
        texture="floor01",
        vertices=(
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
            (3.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
            (5.0, 0.0, 0.0),
        ),
        faces=(
            (0, 1, 2),
            (0, 2, 3),
            (0, 0, 1),  # repeated-index zero-area triangle
            (4, 5, 6),  # distinct indices, but collinear and zero-area
        ),
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="filtered_bad", surfaces=(surface,))

    generated, generation = generate_room_walkmesh_from_geometry(primitive)

    assert generated.wok is not None
    assert generation["degenerate_faces"] == 2
    assert generation["total_faces"] == 2
    assert len(generated.wok.faces) == 2
    assert all(len({face.v1, face.v2, face.v3}) == 3 for face in generated.wok.faces)
    fingerprint, report = inspect_raw_wok_structure("filtered_bad", generated.wok.to_bytes())
    assert fingerprint.face_count == 2
    assert not report.has_errors


def test_writer_rejects_repeated_index_walkable_triangle() -> None:
    _configure_native_python_roots()
    from src.core.modules.module_format import WOKData, WOKFace

    wok = WOKData(
        name="repeated_index",
        verts=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
        faces=[WOKFace(0, 0, 1, 4)],
    )

    with pytest.raises(ValueError, match="no traceable raw-index boundary"):
        wok.to_bytes()


def test_auto_generator_rejects_triangle_that_collapses_during_vertex_welding() -> None:
    """Degeneracy must be checked again after applying the WOK weld epsilon."""

    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import (
        ImportedMeshRoomPrimitive,
        ImportedMeshSurface,
        generate_room_walkmesh_from_geometry,
    )

    surface = ImportedMeshSurface(
        name="near_weld_collapse",
        texture="floor01",
        vertices=(
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
            # This face has positive source area, but its first two points map
            # to one WOK vertex with the default 0.0001-unit weld epsilon.
            (3.0, 0.0, 0.0),
            (3.00005, 0.0, 0.0),
            (3.0, 1.0, 0.0),
        ),
        faces=((0, 1, 2), (0, 2, 3), (4, 5, 6)),
    )
    primitive = ImportedMeshRoomPrimitive(room_resref="near_weld", surfaces=(surface,))

    generated, generation = generate_room_walkmesh_from_geometry(primitive)

    assert generated.wok is not None
    assert generation["degenerate_faces"] == 1
    assert generation["total_faces"] == 2
    assert len(generated.wok.faces) == 2
    assert all(len({face.v1, face.v2, face.v3}) == 3 for face in generated.wok.faces)
