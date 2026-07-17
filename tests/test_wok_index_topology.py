"""Index-topology contracts for serialized Odyssey area walkmeshes."""

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


def _raw_tables(data: bytes) -> tuple[list[tuple[int, int, int]], list[int]]:
    adjacency_count, adjacency_offset = struct.unpack_from("<II", data, 112)
    perimeter_count, perimeter_offset = struct.unpack_from("<II", data, 128)
    adjacency = [
        struct.unpack_from("<iii", data, adjacency_offset + index * 12)
        for index in range(adjacency_count)
    ]
    perimeters = [
        struct.unpack_from("<I", data, perimeter_offset + index * 4)[0]
        for index in range(perimeter_count)
    ]
    return adjacency, perimeters


def test_writer_keeps_duplicate_coordinate_vertices_as_intentional_seams() -> None:
    """Coincident coordinates do not imply shared Odyssey topology."""

    _configure_native_python_roots()
    from src.core.modules.module_format import WOKData, WOKFace
    from src.core.modules.authored_walkmesh_audit import audit_authored_wok
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    # The triangles touch geometrically along (1,0)-(0,1), but use distinct
    # vertex indices on purpose. This pattern occurs in vanilla room WOKs.
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

    raw = wok.to_bytes()
    adjacency, perimeters = _raw_tables(raw)
    fingerprint, report = inspect_raw_wok_structure("seam", raw)

    assert adjacency == [(-1, -1, -1), (-1, -1, -1)]
    assert perimeters == [3, 6]
    assert fingerprint.perimeter_count == 2
    assert fingerprint.closed_perimeter_count == 2
    assert not report.has_errors
    audit = audit_authored_wok("seam", wok)
    assert audit.walkable_component_count == 2
    assert audit.open_edge_count == 6


def test_writer_serializes_outer_boundary_and_hole_as_two_closed_perimeters() -> None:
    _configure_native_python_roots()
    from src.core.modules.module_format import WOKData, WOKFace
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    # Eight triangles form a square ring. The outside boundary is CCW and the
    # hole boundary is CW, exactly as emitted by an up-facing floor mesh.
    wok = WOKData(
        name="ring",
        verts=[
            (0.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
            (4.0, 4.0, 0.0),
            (0.0, 4.0, 0.0),
            (1.0, 1.0, 0.0),
            (3.0, 1.0, 0.0),
            (3.0, 3.0, 0.0),
            (1.0, 3.0, 0.0),
        ],
        faces=[
            WOKFace(0, 1, 5, 4), WOKFace(0, 5, 4, 4),
            WOKFace(1, 2, 6, 4), WOKFace(1, 6, 5, 4),
            WOKFace(2, 3, 7, 4), WOKFace(2, 7, 6, 4),
            WOKFace(3, 0, 4, 4), WOKFace(3, 4, 7, 4),
        ],
    )

    raw = wok.to_bytes()
    _adjacency, perimeters = _raw_tables(raw)
    fingerprint, report = inspect_raw_wok_structure("ring", raw)

    assert len(perimeters) == 2
    assert perimeters[-1] == fingerprint.edge_count
    assert fingerprint.closed_perimeter_count == 2
    assert not report.has_errors


def test_writer_refuses_non_manifold_walkable_edge() -> None:
    _configure_native_python_roots()
    from src.core.modules.module_format import WOKData, WOKFace

    wok = WOKData(
        name="branch",
        verts=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, -1.0, 0.0),
            (0.5, 1.0, 0.0),
        ],
        faces=[
            WOKFace(0, 1, 2, 4),
            WOKFace(1, 0, 3, 4),
            WOKFace(0, 1, 4, 4),
        ],
    )

    with pytest.raises(ValueError, match="at most two"):
        wok.to_bytes()


def test_wok_header_vectors_survive_binary_and_kmap_payload_roundtrips() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import (
        ImportedMeshRoomPrimitive,
        imported_mesh_primitive_from_payload,
        imported_mesh_primitive_payload,
    )
    from src.core.modules.module_format import WOKData, WOKFace

    source = WOKData(
        name="header",
        verts=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 4)],
        relative_hook1=(1.0, 2.0, 3.0),
        relative_hook2=(4.0, 5.0, 6.0),
        absolute_hook1=(7.0, 8.0, 9.0),
        absolute_hook2=(10.0, 11.0, 12.0),
        position=(13.0, 14.0, 15.0),
        adjacency_domain_count=1,
    )

    reopened = WOKData.from_bytes(source.to_bytes())
    assert reopened.relative_hook1 == pytest.approx(source.relative_hook1)
    assert reopened.relative_hook2 == pytest.approx(source.relative_hook2)
    assert reopened.absolute_hook1 == pytest.approx(source.absolute_hook1)
    assert reopened.absolute_hook2 == pytest.approx(source.absolute_hook2)
    assert reopened.position == pytest.approx(source.position)
    assert reopened.adjacency_domain_count == 1

    primitive = ImportedMeshRoomPrimitive(room_resref="header", surfaces=(), wok=source)
    payload_reopened = imported_mesh_primitive_from_payload(
        imported_mesh_primitive_payload(primitive),
        "header",
    )
    assert payload_reopened.wok is not None
    assert payload_reopened.wok.relative_hook1 == source.relative_hook1
    assert payload_reopened.wok.relative_hook2 == source.relative_hook2
    assert payload_reopened.wok.absolute_hook1 == source.absolute_hook1
    assert payload_reopened.wok.absolute_hook2 == source.absolute_hook2
    assert payload_reopened.wok.position == source.position
    assert payload_reopened.wok.adjacency_domain_count == 1


def test_explicit_adjacency_domain_preserves_retail_nonstandard_material() -> None:
    _configure_native_python_roots()
    from src.core.modules.module_format import WOKData, WOKFace
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    wok = WOKData(
        name="explicitdomain",
        verts=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 16)],
        adjacency_domain_count=1,
    )
    raw = wok.to_bytes()
    adjacency_count = struct.unpack_from("<I", raw, 112)[0]
    fingerprint, report = inspect_raw_wok_structure("explicitdomain", raw)

    assert adjacency_count == 1
    assert fingerprint.adjacency_count == 1
    assert fingerprint.closed_perimeter_count == 1
    assert not report.has_errors


def test_writer_keeps_one_aabb_leaf_per_same_centroid_face() -> None:
    _configure_native_python_roots()
    from src.core.modules.module_format import WOKData, WOKFace

    # Both triangles have centroid (1, 1, 0). PyKotor's fallback historically
    # emitted one leaf and silently lost the other collision face.
    wok = WOKData(
        name="samecentre",
        verts=[
            (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, 3.0, 0.0),
            (0.0, 2.0, 0.0), (2.0, 2.0, 0.0), (1.0, -1.0, 0.0),
        ],
        faces=[WOKFace(0, 1, 2, 4), WOKFace(3, 4, 5, 4)],
    )

    raw = wok.to_bytes()
    face_count = struct.unpack_from("<I", raw, 80)[0]
    aabb_count, aabb_offset, aabb_root = struct.unpack_from("<III", raw, 100)
    leaves = [
        struct.unpack_from("<I", raw, aabb_offset + index * 44 + 24)[0]
        for index in range(aabb_count)
    ]
    leaves = [value for value in leaves if value != 0xFFFFFFFF]

    assert aabb_root == 0
    assert aabb_count == 2 * face_count - 1
    assert sorted(leaves) == [0, 1]


def test_raw_fast_path_rejects_coincident_vertex_index_redirect() -> None:
    """A coordinate-identical topology edit must survive serialization."""

    _configure_native_python_roots()
    from src.core.modules.module_format import WOKData, WOKFace

    source = WOKData(
        name="indexredirect",
        verts=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 4)],
    )
    source_raw = source.to_bytes()
    edited = WOKData.from_bytes(source_raw)

    duplicate_index = len(edited.verts)
    edited.verts.append(edited.verts[0])
    edited.faces[0].v1 = duplicate_index
    edited_raw = edited.to_bytes()

    assert edited_raw != source_raw
    assert struct.unpack_from("<I", edited_raw, 72)[0] == 4
    face_offset = struct.unpack_from("<I", edited_raw, 84)[0]
    assert struct.unpack_from("<III", edited_raw, face_offset) == (duplicate_index, 1, 2)
    reopened = WOKData.from_bytes(edited_raw)
    assert len(reopened.verts) == 4
    assert (reopened.faces[0].v1, reopened.faces[0].v2, reopened.faces[0].v3) == (
        duplicate_index,
        1,
        2,
    )


def test_raw_fast_path_requires_exact_adjacency_domain_and_rows() -> None:
    _configure_native_python_roots()
    from src.core.modules.module_format import WOKData, WOKFace, _wok_semantically_matches_raw

    source = WOKData(
        name="adjacencyidentity",
        verts=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 4), WOKFace(0, 2, 3, 4)],
    )
    raw = source.to_bytes()
    unchanged = WOKData.from_bytes(raw)
    assert _wok_semantically_matches_raw(unchanged, raw)

    changed_row = WOKData.from_bytes(raw)
    changed_row.faces[0].adj3 = -1
    assert not _wok_semantically_matches_raw(changed_row, raw)

    changed_domain = WOKData.from_bytes(raw)
    changed_domain.adjacency_domain_count = 1
    assert not _wok_semantically_matches_raw(changed_domain, raw)
