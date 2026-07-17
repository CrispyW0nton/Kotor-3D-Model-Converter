"""Read-only, full-census audit for KOTOR area walkmeshes and converted maps.

The Odyssey engine's BWM/WOK contract is stricter than "PyKotor can parse it".
This tool therefore decodes the binary tables directly and checks the
relationships the game consumes: index-stable adjacency, perimeter loops,
transition edges, and the AABB tree.  PyKotor is used only to locate resources;
Ghost Studio's :class:`WOKData` serializer is exercised as a second,
independent round-trip stage.

By default the command scans every WOK in the K1 and K2 ``chitin.key`` game
libraries, then every MOD/KMAP indexed by the converted-module status file.
It never writes to a game installation, converted artifact, MOD, or KMAP.  Its
only writes are the JSON and Markdown reports under
``Saved/Audits/walkmesh_library``.

Useful focused runs::

    py -3.14 scripts/audit_walkmesh_library.py --vanilla-only --game K2 \
        --resref 000trl --resref 001ebo9
    py -3.14 scripts/audit_walkmesh_library.py --converted-only --module undclb
    py -3.14 scripts/audit_walkmesh_library.py --no-roundtrip --limit 25

Structural agreement with vanilla is not retail-game proof.  A generated or
converted module still requires a manual K1/K2 warp and movement/camera test.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from concurrent.futures import ProcessPoolExecutor, as_completed
import contextlib
from dataclasses import dataclass
from datetime import datetime, timezone
import fnmatch
import hashlib
import io
import json
import logging
import math
from pathlib import Path
import re
import struct
import sys
import traceback
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Match the native embedded-Python resolution used by the application.  This
# gives the audit the actual Core.Scene WOKData implementation rather than a
# hand-copied test serializer.
from scripts.mcp.start_kotormcp_stdio import _python_roots

for _root in reversed(_python_roots(ROOT)):
    _text = str(_root)
    if _text not in sys.path:
        sys.path.insert(0, _text)

logging.disable(logging.CRITICAL)

from pykotor.extract.capsule import Capsule  # noqa: E402
from pykotor.extract.installation import Installation  # noqa: E402
from pykotor.resource.formats.gff import read_gff  # noqa: E402
from pykotor.resource.formats.lyt import read_lyt  # noqa: E402
from pykotor.resource.type import ResourceType  # noqa: E402


DEFAULT_GAMES = {
    "K1": Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"),
    "K2": Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"),
}
DEFAULT_STATUS = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\Modules\Converted\CONVERSION_STATUS.json"
)
DEFAULT_OUTPUT = ROOT / "Saved" / "Audits" / "walkmesh_library"

HEADER_SIZE = 136
AABB_NODE_SIZE = 44
UINT32_NONE = 0xFFFFFFFF
VALID_AABB_PLANES = {0, 1, 2, 4, 8, 16, 32}
WALKABLE_SURFACES = {1, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 18, 30}


@dataclass
class ParsedBwm:
    """Private binary tables retained while building a JSON-safe report."""

    data: bytes
    signature: str
    version: str
    walkmesh_type: int
    hooks: list[tuple[float, float, float]]
    vertices: list[tuple[float, float, float]]
    faces: list[tuple[int, int, int]]
    materials: list[int]
    normals: list[tuple[float, float, float]]
    plane_distances: list[float]
    adjacency: list[tuple[int, int, int]]
    edges: list[tuple[int, int]]
    perimeters: list[int]
    aabb_nodes: list[tuple[tuple[float, ...], int, int, int, int, int]]
    aabb_root: int
    section_offsets: dict[str, int]


class BwmParseError(ValueError):
    """Raised when a WOK cannot be decoded without reading outside its bytes."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _signed_u32(value: int) -> int:
    return -1 if value == UINT32_NONE else int(value)


def _finite_vector(value: Sequence[float]) -> bool:
    return len(value) == 3 and all(math.isfinite(float(item)) for item in value)


def _section(data: bytes, *, offset: int, count: int, stride: int, name: str) -> memoryview:
    if count < 0 or offset < 0 or stride < 0:
        raise BwmParseError(f"{name} has a negative count, offset, or stride.")
    size = count * stride
    if count and offset < HEADER_SIZE:
        raise BwmParseError(f"{name} starts inside the {HEADER_SIZE}-byte BWM header.")
    if offset + size > len(data):
        raise BwmParseError(
            f"{name} extends past EOF: offset={offset}, count={count}, "
            f"stride={stride}, size={len(data)}."
        )
    return memoryview(data)[offset : offset + size]


def parse_bwm(data: bytes) -> ParsedBwm:
    """Decode the area-BWM tables directly, without PyKotor regeneration."""

    if len(data) < HEADER_SIZE:
        raise BwmParseError(f"BWM is {len(data)} bytes; at least {HEADER_SIZE} are required.")
    signature = data[:4]
    version = data[4:8]
    if signature != b"BWM ":
        raise BwmParseError(f"Invalid BWM signature {signature!r}.")
    if version != b"V1.0":
        raise BwmParseError(f"Unsupported BWM version {version!r}.")

    walkmesh_type = struct.unpack_from("<I", data, 8)[0]
    hooks = [struct.unpack_from("<3f", data, offset) for offset in (12, 24, 36, 48, 60)]
    (
        vertex_count,
        vertex_offset,
        face_count,
        face_offset,
        material_offset,
        normal_offset,
        plane_offset,
        aabb_count,
        aabb_offset,
        aabb_root,
        adjacency_count,
        adjacency_offset,
        edge_count,
        edge_offset,
        perimeter_count,
        perimeter_offset,
    ) = struct.unpack_from("<16I", data, 72)

    # Bounds checks happen before any unpack operation.  Zero-length sections
    # are allowed to point at EOF, as the retail 136-byte visual-only WOKs do.
    _section(data, offset=vertex_offset, count=vertex_count, stride=12, name="vertices")
    _section(data, offset=face_offset, count=face_count, stride=12, name="faces")
    _section(data, offset=material_offset, count=face_count, stride=4, name="materials")
    _section(data, offset=normal_offset, count=face_count, stride=12, name="normals")
    _section(data, offset=plane_offset, count=face_count, stride=4, name="plane distances")
    _section(data, offset=aabb_offset, count=aabb_count, stride=AABB_NODE_SIZE, name="AABB nodes")
    _section(data, offset=adjacency_offset, count=adjacency_count, stride=12, name="adjacency")
    _section(data, offset=edge_offset, count=edge_count, stride=8, name="edge records")
    _section(data, offset=perimeter_offset, count=perimeter_count, stride=4, name="perimeters")

    vertices = [struct.unpack_from("<3f", data, vertex_offset + index * 12) for index in range(vertex_count)]
    faces = [struct.unpack_from("<3I", data, face_offset + index * 12) for index in range(face_count)]
    materials = [struct.unpack_from("<I", data, material_offset + index * 4)[0] for index in range(face_count)]
    normals = [struct.unpack_from("<3f", data, normal_offset + index * 12) for index in range(face_count)]
    plane_distances = [struct.unpack_from("<f", data, plane_offset + index * 4)[0] for index in range(face_count)]
    adjacency = [struct.unpack_from("<3i", data, adjacency_offset + index * 12) for index in range(adjacency_count)]
    edges = [struct.unpack_from("<2i", data, edge_offset + index * 8) for index in range(edge_count)]
    perimeters = [struct.unpack_from("<I", data, perimeter_offset + index * 4)[0] for index in range(perimeter_count)]
    aabb_nodes = []
    for index in range(aabb_count):
        offset = aabb_offset + index * AABB_NODE_SIZE
        bounds = struct.unpack_from("<6f", data, offset)
        face, unknown, plane, left, right = struct.unpack_from("<5I", data, offset + 24)
        aabb_nodes.append((bounds, face, unknown, plane, left, right))

    return ParsedBwm(
        data=data,
        signature=signature.decode("ascii", "replace"),
        version=version.decode("ascii", "replace"),
        walkmesh_type=walkmesh_type,
        hooks=[tuple(float(item) for item in value) for value in hooks],
        vertices=[tuple(float(item) for item in value) for value in vertices],
        faces=[tuple(int(item) for item in value) for value in faces],
        materials=[int(item) for item in materials],
        normals=[tuple(float(item) for item in value) for value in normals],
        plane_distances=[float(item) for item in plane_distances],
        adjacency=[tuple(int(item) for item in value) for value in adjacency],
        edges=[tuple(int(item) for item in value) for value in edges],
        perimeters=[int(item) for item in perimeters],
        aabb_nodes=aabb_nodes,
        aabb_root=int(aabb_root),
        section_offsets={
            "vertices": vertex_offset,
            "faces": face_offset,
            "materials": material_offset,
            "normals": normal_offset,
            "plane_distances": plane_offset,
            "aabb": aabb_offset,
            "adjacency": adjacency_offset,
            "edges": edge_offset,
            "perimeters": perimeter_offset,
        },
    )


def _triangle_geometry(
    parsed: ParsedBwm,
    face: tuple[int, int, int],
) -> tuple[float, tuple[float, float, float]] | None:
    if any(index >= len(parsed.vertices) for index in face):
        return None
    a, b, c = (parsed.vertices[index] for index in face)
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    length = math.sqrt(sum(item * item for item in cross))
    if length <= 1.0e-12:
        return 0.0, (0.0, 0.0, 0.0)
    return length * 0.5, tuple(item / length for item in cross)


def _semantic_hash(parsed: ParsedBwm) -> str:
    """Hash authored geometry independent of harmless vertex-table numbering.

    PyKotor reconstructs its vertex table from face references, so an otherwise
    exact room can receive different raw vertex indices and can drop an
    unreferenced legacy vertex.  Canonicalize each directed triangle to its
    lexicographically smallest cyclic rotation and sort the face/material rows.
    Do not include the standalone vertex table: the face rows already contain
    every referenced coordinate, while the separate vertex-count,
    ``face_indices`` fingerprint, and raw-index adjacency/perimeter metrics
    still expose topology changes.
    """

    rounded_vertices = [tuple(round(item, 6) for item in row) for row in parsed.vertices]
    face_rows: list[tuple[Any, ...]] = []
    for index, face in enumerate(parsed.faces):
        if any(vertex >= len(rounded_vertices) for vertex in face):
            corners: tuple[Any, ...] = tuple(("invalid", vertex) for vertex in face)
        else:
            raw = tuple(rounded_vertices[vertex] for vertex in face)
            rotations = (raw, (raw[1], raw[2], raw[0]), (raw[2], raw[0], raw[1]))
            corners = min(rotations)
        material = parsed.materials[index] if index < len(parsed.materials) else -1
        face_rows.append((material, *corners))

    payload = {
        "hooks": [[round(item, 6) for item in row] for row in parsed.hooks],
        "face_geometry_and_material": sorted(face_rows),
    }
    return _sha256_bytes(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _edge_owners(parsed: ParsedBwm) -> dict[tuple[int, int], list[tuple[int, int, int, int]]]:
    owners: dict[tuple[int, int], list[tuple[int, int, int, int]]] = defaultdict(list)
    for face_index, face in enumerate(parsed.faces[: len(parsed.adjacency)]):
        for local_edge in range(3):
            start, end = face[local_edge], face[(local_edge + 1) % 3]
            owners[tuple(sorted((start, end)))].append((face_index, local_edge, start, end))
    return owners


def _component_count(parsed: ParsedBwm, owners: dict[tuple[int, int], list[tuple[int, int, int, int]]]) -> int:
    count = len(parsed.adjacency)
    if not count:
        return 0
    graph: list[set[int]] = [set() for _ in range(count)]
    for rows in owners.values():
        if len(rows) == 2:
            a, b = rows[0][0], rows[1][0]
            if a != b:
                graph[a].add(b)
                graph[b].add(a)
    seen: set[int] = set()
    components = 0
    for start in range(count):
        if start in seen:
            continue
        components += 1
        queue = [start]
        seen.add(start)
        while queue:
            current = queue.pop()
            for neighbour in graph[current]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    queue.append(neighbour)
    return components


def _audit_adjacency(parsed: ParsedBwm) -> dict[str, Any]:
    owners = _edge_owners(parsed)
    mismatches = 0
    nonreciprocal = 0
    invalid_targets = 0
    nonmanifold = 0
    degenerate_slots = 0
    expected_boundary: set[int] = set()
    nonmanifold_keys = {key for key, rows in owners.items() if len(rows) > 2}

    for key, rows in owners.items():
        if any(start == end for _face, _edge, start, end in rows):
            degenerate_slots += len(rows)
            # K1 m38aa_11 contains two retail self-edge boundary records.
            # They are not a generator target, but they are part of the known-
            # loadable serialized perimeter and must not become a false raw
            # structure failure in the vanilla census.
            for face_index, local_edge, _start, _end in rows:
                if parsed.adjacency[face_index][local_edge] == -1:
                    expected_boundary.add(face_index * 3 + local_edge)
            continue
        if len(rows) == 2 and rows[0][0] == rows[1][0]:
            # The other two edges of K1 m38aa_11's repeated-index face are
            # opposite half-edges on the same face.  Retail deliberately keeps
            # both as perimeter rows with -1 adjacency instead of linking the
            # face to itself.
            degenerate_slots += len(rows)
            for face_index, local_edge, _start, _end in rows:
                if parsed.adjacency[face_index][local_edge] == -1:
                    expected_boundary.add(face_index * 3 + local_edge)
            continue
        if len(rows) > 2:
            nonmanifold += 1
            continue
        if len(rows) == 1:
            expected_boundary.add(rows[0][0] * 3 + rows[0][1])
        for face_index, local_edge, _start, _end in rows:
            actual = parsed.adjacency[face_index][local_edge]
            expected = -1
            if len(rows) == 2:
                other = rows[1] if rows[0][0:2] == (face_index, local_edge) else rows[0]
                expected = other[0] * 3 + other[1]
            if actual != expected:
                mismatches += 1

    for face_index, row in enumerate(parsed.adjacency):
        for local_edge, target in enumerate(row):
            source_face = parsed.faces[face_index]
            source_pair = (source_face[local_edge], source_face[(local_edge + 1) % 3])
            if tuple(sorted(source_pair)) in nonmanifold_keys:
                # K1 m38aa_03 and K2 403dxne prove that retail can carry an
                # unrepresentable four-owner edge with intentionally partial,
                # non-reciprocal links.  Record the non-manifold warning above
                # but do not misclassify the known-loadable source as corrupt.
                continue
            if target < 0:
                continue
            target_face, target_edge = divmod(target, 3)
            if target_face >= len(parsed.adjacency) or target_edge >= 3:
                invalid_targets += 1
                continue
            destination_face = parsed.faces[target_face]
            destination_pair = (
                destination_face[target_edge],
                destination_face[(target_edge + 1) % 3],
            )
            if destination_pair != (source_pair[1], source_pair[0]):
                nonreciprocal += 1
                continue
            if parsed.adjacency[target_face][target_edge] != face_index * 3 + local_edge:
                nonreciprocal += 1

    return {
        "raw_index_mismatch_count": mismatches,
        "nonreciprocal_count": nonreciprocal,
        "invalid_target_count": invalid_targets,
        "nonmanifold_edge_count": nonmanifold,
        "degenerate_edge_slot_count": degenerate_slots,
        "geometric_boundary_edge_count": len(expected_boundary),
        "component_count": _component_count(parsed, owners),
        "expected_boundary_edge_ids": expected_boundary,
    }


def _edge_vertices(parsed: ParsedBwm, edge_id: int) -> tuple[int, int] | None:
    face_index, local_edge = divmod(edge_id, 3)
    if face_index >= len(parsed.adjacency) or local_edge >= 3:
        return None
    face = parsed.faces[face_index]
    return face[local_edge], face[(local_edge + 1) % 3]


def _audit_perimeters(parsed: ParsedBwm, expected_boundary: set[int]) -> dict[str, Any]:
    invalid_edge_ids = sum(_edge_vertices(parsed, edge_id) is None for edge_id, _transition in parsed.edges)
    transition_count = sum(transition >= 0 for _edge_id, transition in parsed.edges)
    cumulative_valid = True
    previous = 0
    for value in parsed.perimeters:
        if value <= previous or value > len(parsed.edges):
            cumulative_valid = False
        previous = value
    perimeter_edge_count = parsed.perimeters[-1] if parsed.perimeters and cumulative_valid else 0
    perimeter_edge_ids = {
        edge_id
        for edge_id, _transition in parsed.edges[:perimeter_edge_count]
        if _edge_vertices(parsed, edge_id) is not None
    }
    missing = sorted(expected_boundary - perimeter_edge_ids)
    unexpected = sorted(perimeter_edge_ids - expected_boundary)

    closed = 0
    open_loops = 0
    signed_areas: list[float] = []
    start = 0
    if cumulative_valid:
        for stop in parsed.perimeters:
            rows = parsed.edges[start:stop]
            directed = [_edge_vertices(parsed, edge_id) for edge_id, _transition in rows]
            is_closed = bool(directed) and all(item is not None for item in directed)
            if is_closed:
                for index, edge in enumerate(directed):
                    next_edge = directed[(index + 1) % len(directed)]
                    if edge is None or next_edge is None or edge[1] != next_edge[0]:
                        is_closed = False
                        break
            if is_closed:
                closed += 1
                area = 0.0
                for edge in directed:
                    assert edge is not None
                    a = parsed.vertices[edge[0]]
                    b = parsed.vertices[edge[1]]
                    area += a[0] * b[1] - b[0] * a[1]
                signed_areas.append(area * 0.5)
            else:
                open_loops += 1
            start = stop

    return {
        "serialized_edge_count": len(parsed.edges),
        "perimeter_edge_count": perimeter_edge_count,
        "perimeter_loop_count": len(parsed.perimeters),
        "closed_loop_count": closed,
        "open_loop_count": open_loops,
        "cumulative_records_valid": cumulative_valid,
        "invalid_edge_id_count": invalid_edge_ids,
        "missing_boundary_edge_count": len(missing),
        "unexpected_perimeter_edge_count": len(unexpected),
        "transition_record_count": transition_count,
        "positive_xy_loop_count": sum(area > 1.0e-8 for area in signed_areas),
        "negative_xy_loop_count": sum(area < -1.0e-8 for area in signed_areas),
        "zero_xy_loop_count": sum(abs(area) <= 1.0e-8 for area in signed_areas),
        "boundary_edge_id_hash": _sha256_bytes(
            b"".join(struct.pack("<i", value) for value in sorted(perimeter_edge_ids))
        ),
    }


def _audit_aabb(parsed: ParsedBwm) -> dict[str, Any]:
    nodes = parsed.aabb_nodes
    invalid_bounds = 0
    invalid_unknown = 0
    invalid_planes = 0
    invalid_children = 0
    invalid_leaf_faces = 0
    leaf_bound_mismatches = 0
    leaf_faces: list[int] = []
    children_by_index: dict[int, tuple[int, int]] = {}

    for index, (bounds, face, unknown, plane, left, right) in enumerate(nodes):
        if not all(math.isfinite(value) for value in bounds) or any(bounds[axis] > bounds[axis + 3] for axis in range(3)):
            invalid_bounds += 1
        if unknown != 4:
            invalid_unknown += 1
        if plane not in VALID_AABB_PLANES:
            invalid_planes += 1
        signed_face = _signed_u32(face)
        signed_left = _signed_u32(left)
        signed_right = _signed_u32(right)
        if signed_face >= 0:
            leaf_faces.append(signed_face)
            if signed_face >= len(parsed.faces):
                invalid_leaf_faces += 1
            else:
                corners = [parsed.vertices[vertex] for vertex in parsed.faces[signed_face] if vertex < len(parsed.vertices)]
                if len(corners) != 3 or any(
                    corner[axis] < bounds[axis] - 1.0e-4 or corner[axis] > bounds[axis + 3] + 1.0e-4
                    for corner in corners
                    for axis in range(3)
                ):
                    leaf_bound_mismatches += 1
            if signed_left >= 0 or signed_right >= 0:
                invalid_children += 1
        else:
            children_by_index[index] = (signed_left, signed_right)
            if signed_left < 0 or signed_right < 0 or signed_left >= len(nodes) or signed_right >= len(nodes):
                invalid_children += 1

    reachable: set[int] = set()
    cycle_count = 0
    if nodes and parsed.aabb_root < len(nodes):
        queue = deque([parsed.aabb_root])
        queued: set[int] = {parsed.aabb_root}
        while queue:
            index = queue.popleft()
            queued.discard(index)
            if index in reachable:
                cycle_count += 1
                continue
            reachable.add(index)
            for child in children_by_index.get(index, ()):
                if child < 0 or child >= len(nodes):
                    continue
                if child in reachable or child in queued:
                    cycle_count += 1
                else:
                    queue.append(child)
                    queued.add(child)
    elif nodes:
        invalid_children += 1

    covered = {face for face in leaf_faces if 0 <= face < len(parsed.faces)}
    missing = set(range(len(parsed.faces))) - covered
    duplicate_leaf_count = len(leaf_faces) - len(set(leaf_faces))
    expected_node_count = max(0, len(parsed.faces) * 2 - 1)
    return {
        "node_count": len(nodes),
        "expected_full_node_count": expected_node_count,
        "root_index": parsed.aabb_root,
        "reachable_node_count": len(reachable),
        "unreachable_node_count": len(nodes) - len(reachable),
        "leaf_count": len(leaf_faces),
        "covered_face_count": len(covered),
        "missing_face_count": len(missing),
        "duplicate_leaf_count": duplicate_leaf_count,
        "invalid_bounds_count": invalid_bounds,
        "invalid_unknown_count": invalid_unknown,
        "invalid_plane_count": invalid_planes,
        "invalid_child_count": invalid_children,
        "invalid_leaf_face_count": invalid_leaf_faces,
        "leaf_bound_mismatch_count": leaf_bound_mismatches,
        "cycle_or_duplicate_path_count": cycle_count,
        "complete_one_leaf_per_face": bool(
            len(nodes) == expected_node_count
            and len(reachable) == len(nodes)
            and len(leaf_faces) == len(parsed.faces)
            and not missing
            and not duplicate_leaf_count
            and not invalid_bounds
            and not invalid_unknown
            and not invalid_planes
            and not invalid_children
            and not invalid_leaf_faces
            and not leaf_bound_mismatches
            and not cycle_count
        ),
    }


def audit_parsed_bwm(parsed: ParsedBwm, *, source: str, resref: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if parsed.walkmesh_type != 1:
        errors.append(f"Area WOK type is {parsed.walkmesh_type}; expected 1.")
    if any(not _finite_vector(value) for value in parsed.hooks):
        errors.append("One or more BWM hook/position vectors contain non-finite values.")
    nonfinite_vertices = sum(not _finite_vector(value) for value in parsed.vertices)
    nonfinite_normals = sum(not _finite_vector(value) for value in parsed.normals)
    nonfinite_planes = sum(not math.isfinite(value) for value in parsed.plane_distances)
    invalid_face_indices = sum(any(vertex >= len(parsed.vertices) for vertex in face) for face in parsed.faces)
    if nonfinite_vertices:
        errors.append(f"{nonfinite_vertices} vertices contain non-finite values.")
    if nonfinite_normals or nonfinite_planes:
        errors.append(f"Derived face planes contain {nonfinite_normals} non-finite normals and {nonfinite_planes} distances.")
    if invalid_face_indices:
        errors.append(f"{invalid_face_indices} faces reference vertices outside the vertex table.")
    if len(parsed.adjacency) > len(parsed.faces):
        errors.append("Adjacency domain is larger than the face table.")

    adjacency = _audit_adjacency(parsed) if len(parsed.adjacency) <= len(parsed.faces) else {
        "raw_index_mismatch_count": 0,
        "nonreciprocal_count": 0,
        "invalid_target_count": 0,
        "nonmanifold_edge_count": 0,
        "degenerate_edge_slot_count": 0,
        "geometric_boundary_edge_count": 0,
        "component_count": 0,
        "expected_boundary_edge_ids": set(),
    }
    perimeters = _audit_perimeters(parsed, adjacency.pop("expected_boundary_edge_ids"))
    aabb = _audit_aabb(parsed)
    if adjacency["raw_index_mismatch_count"]:
        errors.append(f"{adjacency['raw_index_mismatch_count']} adjacency slots contradict raw vertex-index topology.")
    if adjacency["invalid_target_count"] or adjacency["nonreciprocal_count"]:
        errors.append(
            f"Adjacency has {adjacency['invalid_target_count']} invalid targets and "
            f"{adjacency['nonreciprocal_count']} non-reciprocal/reversed-edge failures."
        )
    if adjacency["nonmanifold_edge_count"]:
        warnings.append(f"{adjacency['nonmanifold_edge_count']} raw-index edges have more than two face owners.")
    if adjacency["degenerate_edge_slot_count"]:
        warnings.append(f"{adjacency['degenerate_edge_slot_count']} adjacency-domain edge slots are degenerate.")
    if not perimeters["cumulative_records_valid"] or perimeters["open_loop_count"]:
        errors.append("Perimeter records are out of range/non-increasing or contain an open loop.")
    if perimeters["missing_boundary_edge_count"] or perimeters["unexpected_perimeter_edge_count"]:
        errors.append(
            f"Perimeter coverage misses {perimeters['missing_boundary_edge_count']} geometric boundary edges "
            f"and includes {perimeters['unexpected_perimeter_edge_count']} non-boundary edges."
        )
    if perimeters["invalid_edge_id_count"]:
        errors.append(f"{perimeters['invalid_edge_id_count']} serialized edge IDs are outside the adjacency domain.")
    if parsed.faces and not aabb["complete_one_leaf_per_face"]:
        warnings.append(
            "AABB is not the ordinary full 2F-1 one-leaf-per-face tree "
            f"({aabb['covered_face_count']}/{len(parsed.faces)} faces covered)."
        )

    areas: list[float] = []
    normal_z: list[float] = []
    for face in parsed.faces[: len(parsed.adjacency)]:
        geometry = _triangle_geometry(parsed, face)
        if geometry is None:
            continue
        area, normal = geometry
        areas.append(area)
        normal_z.append(normal[2])
    zero_area = sum(area <= 1.0e-12 for area in areas)
    slopes = [math.degrees(math.acos(min(1.0, max(0.0, abs(value))))) for value in normal_z if abs(value) <= 1.0]
    if zero_area:
        warnings.append(f"{zero_area} adjacency-domain faces have zero geometric area.")

    material_distribution = Counter(parsed.materials)
    position = parsed.hooks[4]
    topology_bytes = b"".join(struct.pack("<3I", *face) for face in parsed.faces)
    material_bytes = b"".join(struct.pack("<I", material) for material in parsed.materials)
    report = {
        "source": source,
        "resref": resref.lower(),
        "byte_size": len(parsed.data),
        "sha256": _sha256_bytes(parsed.data),
        "signature": parsed.signature,
        "version": parsed.version,
        "walkmesh_type": parsed.walkmesh_type,
        "header_vectors": {
            "relative_hook1": parsed.hooks[0],
            "relative_hook2": parsed.hooks[1],
            "absolute_hook1": parsed.hooks[2],
            "absolute_hook2": parsed.hooks[3],
            "position": position,
            "position_nonzero": any(abs(value) > 1.0e-8 for value in position),
        },
        "counts": {
            "vertices": len(parsed.vertices),
            "faces": len(parsed.faces),
            "walkable_material_faces": sum(material in WALKABLE_SURFACES for material in parsed.materials),
            "nonwalk_material_faces": sum(material not in WALKABLE_SURFACES for material in parsed.materials),
            "adjacency_domain_faces": len(parsed.adjacency),
            "adjacency_domain_nonwalk_material_faces": sum(
                material not in WALKABLE_SURFACES for material in parsed.materials[: len(parsed.adjacency)]
            ),
        },
        "surface_distribution": {str(key): value for key, value in sorted(material_distribution.items())},
        "geometry": {
            "zero_area_face_count": zero_area,
            "negative_normal_z_count": sum(value < -1.0e-8 for value in normal_z),
            "slope_over_45_count": sum(value > 45.0 + 1.0e-6 for value in slopes),
            "slope_over_80_count": sum(value > 80.0 + 1.0e-6 for value in slopes),
            "max_absolute_slope_degrees": round(max(slopes, default=0.0), 6),
        },
        "adjacency": adjacency,
        "perimeters": perimeters,
        "aabb": aabb,
        "section_offsets": parsed.section_offsets,
        "fingerprints": {
            "semantic": _semantic_hash(parsed),
            "face_indices": _sha256_bytes(topology_bytes),
            "material_order": _sha256_bytes(material_bytes),
            "adjacency": _sha256_bytes(b"".join(struct.pack("<3i", *row) for row in parsed.adjacency)),
            "transition_records": _sha256_bytes(
                b"".join(struct.pack("<2i", *row) for row in parsed.edges if row[1] >= 0)
            ),
        },
        "errors": errors,
        "warnings": warnings,
        "raw_structure_valid": not errors,
    }
    return report


def audit_bwm_bytes(data: bytes, *, source: str, resref: str) -> tuple[ParsedBwm | None, dict[str, Any]]:
    try:
        parsed = parse_bwm(data)
        return parsed, audit_parsed_bwm(parsed, source=source, resref=resref)
    except Exception as exc:
        return None, {
            "source": source,
            "resref": resref.lower(),
            "byte_size": len(data),
            "sha256": _sha256_bytes(data),
            "raw_structure_valid": False,
            "errors": [f"{type(exc).__name__}: {exc}"],
            "warnings": [],
        }


def _compare_roundtrip(source: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    comparisons = {
        "semantic_hash": (
            source.get("fingerprints", {}).get("semantic"),
            output.get("fingerprints", {}).get("semantic"),
        ),
        "face_index_hash": (
            source.get("fingerprints", {}).get("face_indices"),
            output.get("fingerprints", {}).get("face_indices"),
        ),
        "material_order_hash": (
            source.get("fingerprints", {}).get("material_order"),
            output.get("fingerprints", {}).get("material_order"),
        ),
        "vertex_count": (source.get("counts", {}).get("vertices"), output.get("counts", {}).get("vertices")),
        "face_count": (source.get("counts", {}).get("faces"), output.get("counts", {}).get("faces")),
        "adjacency_domain": (
            source.get("counts", {}).get("adjacency_domain_faces"),
            output.get("counts", {}).get("adjacency_domain_faces"),
        ),
        "boundary_edges": (
            source.get("adjacency", {}).get("geometric_boundary_edge_count"),
            output.get("adjacency", {}).get("geometric_boundary_edge_count"),
        ),
        "perimeter_loops": (
            source.get("perimeters", {}).get("perimeter_loop_count"),
            output.get("perimeters", {}).get("perimeter_loop_count"),
        ),
        "transition_records": (
            source.get("perimeters", {}).get("transition_record_count"),
            output.get("perimeters", {}).get("transition_record_count"),
        ),
    }
    mismatches = {
        key: {"source": before, "output": after}
        for key, (before, after) in comparisons.items()
        if before != after
    }
    # Raw index and material-order fingerprints remain important diagnostics,
    # but are not semantic failures when canonical face geometry/material and
    # all derived topology metrics still agree.
    # A standalone, unreferenced legacy vertex is not collision geometry.
    # PyKotor rebuilds the vertex table from face references and legitimately
    # omits such rows (774qgm_01a and cor_m56ag are converted examples).  Keep
    # the count mismatch visible, but let the canonical referenced-face hash
    # decide semantic equivalence.
    primary = {"semantic_hash", "face_count"}
    derived = {"adjacency_domain", "boundary_edges", "perimeter_loops", "transition_records"}
    return {
        "attempted": True,
        "serialized": True,
        "semantic_match": not any(key in primary for key in mismatches),
        "derived_tables_match": not any(key in derived for key in mismatches),
        "index_order_match": not any(key in {"face_index_hash", "material_order_hash"} for key in mismatches),
        "mismatches": mismatches,
        "output_raw_structure_valid": bool(output.get("raw_structure_valid")),
        "output_summary": {
            "byte_size": output.get("byte_size", 0),
            "sha256": output.get("sha256", ""),
            "counts": output.get("counts", {}),
            "adjacency": output.get("adjacency", {}),
            "perimeters": output.get("perimeters", {}),
            "aabb": output.get("aabb", {}),
            "errors": output.get("errors", []),
            "warnings": output.get("warnings", []),
        },
    }


def exercise_wokdata_roundtrip(data: bytes, source_report: dict[str, Any], *, resref: str) -> dict[str, Any]:
    """Serialize in memory only; never promote or write the generated bytes."""

    try:
        from core.modules.module_format import WOKData

        wok = WOKData.from_bytes(data)
        output_data = wok.to_bytes()
        _parsed, output = audit_bwm_bytes(output_data, source="Ghost Studio WOKData round-trip", resref=resref)
        return _compare_roundtrip(source_report, output)
    except Exception as exc:
        return {
            "attempted": True,
            "serialized": False,
            "semantic_match": False,
            "derived_tables_match": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _matches(value: str, patterns: Sequence[str]) -> bool:
    if not patterns:
        return True
    lowered = value.lower()
    return any(fnmatch.fnmatchcase(lowered, pattern.lower()) for pattern in patterns)


def _audit_vanilla_payload(payload: tuple[str, str, bytes, str, bool]) -> dict[str, Any]:
    """Process-safe worker for one in-memory chitin WOK payload."""

    game, resref, data, source, roundtrip = payload
    parsed, report = audit_bwm_bytes(data, source=source, resref=resref)
    report["game"] = game
    if roundtrip and parsed is not None:
        report["roundtrip"] = exercise_wokdata_roundtrip(data, report, resref=resref)
    return report


def audit_vanilla_game(
    game: str,
    root: Path,
    *,
    patterns: Sequence[str],
    regex: re.Pattern[str] | None,
    limit: int,
    roundtrip: bool,
    progress_every: int,
    jobs: int,
) -> dict[str, Any]:
    installation = Installation(root)
    resources = [
        resource
        for resource in installation.chitin_resources()
        if resource.restype() == ResourceType.WOK
        and _matches(str(resource.resname()), patterns)
        and (regex is None or regex.search(str(resource.resname())))
    ]
    resources.sort(key=lambda item: str(item.resname()).lower())
    if limit > 0:
        resources = resources[:limit]
    payloads = [
        (
            game,
            str(resource.resname()).lower(),
            bytes(resource.data()),
            f"{game} chitin:{resource.filepath()}",
            roundtrip,
        )
        for resource in resources
    ]
    rows: list[dict[str, Any]] = []
    worker_count = max(1, int(jobs))
    if worker_count == 1 or len(payloads) <= 1:
        for index, report in enumerate(map(_audit_vanilla_payload, payloads), 1):
            rows.append(report)
            if progress_every > 0 and (index % progress_every == 0 or index == len(payloads)):
                print(f"{game}: audited {index}/{len(payloads)} WOKs", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=min(worker_count, len(payloads))) as executor:
            futures = [executor.submit(_audit_vanilla_payload, payload) for payload in payloads]
            for index, future in enumerate(as_completed(futures), 1):
                rows.append(future.result())
                if progress_every > 0 and (index % progress_every == 0 or index == len(payloads)):
                    print(f"{game}: audited {index}/{len(payloads)} WOKs", flush=True)
        rows.sort(key=lambda row: str(row.get("resref", "")))
    return {
        "game": game,
        "installation": str(root),
        "resource_count": len(rows),
        "walkmeshes": rows,
        "summary": summarize_walkmeshes(rows),
    }


def _resource_name(resource: Any) -> str:
    return str(resource.resname()).strip().lower()


def _resource_extension(resource: Any) -> str:
    return str(resource.restype().extension).strip().lower()


def _lyt_rows(data: bytes) -> list[dict[str, Any]]:
    lyt = read_lyt(data)
    rows = []
    for room in lyt.rooms:
        position = getattr(room, "position", None)
        rows.append(
            {
                "resref": str(room.model).strip().lower(),
                "position": (
                    float(getattr(position, "x", 0.0)),
                    float(getattr(position, "y", 0.0)),
                    float(getattr(position, "z", 0.0)),
                ),
            }
        )
    return rows


def _entry_from_ifo(data: bytes) -> tuple[float, float, float] | None:
    try:
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            root = read_gff(data).root
            entry = (
                float(root.acquire("Mod_Entry_X", 0.0)),
                float(root.acquire("Mod_Entry_Y", 0.0)),
                float(root.acquire("Mod_Entry_Z", 0.0)),
            )
        return entry
    except Exception:
        return None


def _point_on_walkmesh(
    point: tuple[float, float, float],
    rooms: Iterable[tuple[ParsedBwm, tuple[float, float, float]]],
    *,
    z_tolerance: float = 1.5,
) -> dict[str, Any]:
    px, py, pz = point
    nearest_delta: float | None = None
    matched = False
    for parsed, offset in rooms:
        # Odyssey room WOK vertices imported from retail modules are already in
        # module/area space.  The fifth BWM header vector is retained engine
        # metadata, not an instruction to translate the vertex table, and LYT
        # positions must likewise not be added to a module-space WOK.  Authored
        # room-local WOKs pass their explicit LYT-derived offset from the KMAP
        # coordinate-space resolver below.
        for index, face in enumerate(parsed.faces[: len(parsed.adjacency)]):
            if index >= len(parsed.materials) or parsed.materials[index] not in WALKABLE_SURFACES:
                continue
            if any(vertex >= len(parsed.vertices) for vertex in face):
                continue
            a, b, c = [
                (
                    parsed.vertices[vertex][0] + offset[0],
                    parsed.vertices[vertex][1] + offset[1],
                    parsed.vertices[vertex][2] + offset[2],
                )
                for vertex in face
            ]
            denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(denominator) <= 1.0e-12:
                continue
            u = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / denominator
            v = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / denominator
            w = 1.0 - u - v
            if min(u, v, w) < -1.0e-6:
                continue
            floor_z = u * a[2] + v * b[2] + w * c[2]
            delta = abs(pz - floor_z)
            nearest_delta = delta if nearest_delta is None else min(nearest_delta, delta)
            if delta <= z_tolerance:
                matched = True
    return {
        "position": point,
        "on_walkable_face": matched,
        "nearest_vertical_delta": None if nearest_delta is None else round(nearest_delta, 6),
        "z_tolerance": z_tolerance,
    }


def audit_mod(path: Path, *, module: str, game: str, roundtrip: bool) -> dict[str, Any]:
    row: dict[str, Any] = {
        "kind": "MOD",
        "module": module,
        "game": game,
        "path": str(path),
        "exists": path.is_file(),
        "walkmeshes": [],
        "errors": [],
    }
    if not path.is_file():
        row["errors"].append("Indexed MOD does not exist.")
        return row
    row["byte_size"] = path.stat().st_size
    row["sha256"] = _sha256_file(path)
    try:
        resources = list(Capsule(path))
        by_key = {(_resource_name(item), _resource_extension(item)): bytes(item.data()) for item in resources}
        lyt_candidates = [(name, data) for (name, ext), data in by_key.items() if ext == "lyt"]
        lyt_rooms: list[dict[str, Any]] = []
        if lyt_candidates:
            lyt_rooms = _lyt_rows(lyt_candidates[0][1])
        else:
            row["errors"].append("MOD contains no LYT resource.")

        parsed_rooms: dict[str, ParsedBwm] = {}
        for (resref, extension), data in sorted(by_key.items()):
            if extension != "wok":
                continue
            parsed, report = audit_bwm_bytes(data, source=str(path), resref=resref)
            report["game"] = game
            if roundtrip and parsed is not None:
                report["roundtrip"] = exercise_wokdata_roundtrip(data, report, resref=resref)
            row["walkmeshes"].append(report)
            if parsed is not None:
                parsed_rooms[resref] = parsed
        declared = {item["resref"] for item in lyt_rooms}
        present = set(parsed_rooms)
        row["lyt_room_count"] = len(lyt_rooms)
        row["wok_resource_count"] = len(row["walkmeshes"])
        row["lyt_rooms_missing_wok"] = sorted(declared - present)
        row["woks_not_declared_in_lyt"] = sorted(present - declared)
        if row["lyt_rooms_missing_wok"]:
            row["errors"].append(f"{len(row['lyt_rooms_missing_wok'])} LYT rooms have no packaged WOK.")

        ifo_data = next((data for (_name, ext), data in by_key.items() if ext == "ifo"), None)
        entry = _entry_from_ifo(ifo_data) if ifo_data is not None else None
        if entry is not None:
            module_space_entry = _point_on_walkmesh(
                entry,
                (
                    # Packaged room WOKs are stored in module coordinates.  LYT
                    # remains relevant for room render placement, but is not a
                    # second WOK translation.
                    (parsed, (0.0, 0.0, 0.0))
                    for resref, parsed in parsed_rooms.items()
                ),
            )
            row["entry_point"] = module_space_entry
            row["entry_point"]["coordinate_space"] = "module"
            if not module_space_entry["on_walkable_face"]:
                room_positions = {item["resref"]: tuple(item["position"]) for item in lyt_rooms}
                room_local_entry = _point_on_walkmesh(
                    entry,
                    (
                        (parsed, room_positions.get(resref, (0.0, 0.0, 0.0)))
                        for resref, parsed in parsed_rooms.items()
                    ),
                )
                if room_local_entry["on_walkable_face"]:
                    room_local_entry["coordinate_space"] = "room_local_via_lyt"
                    row["entry_point"] = room_local_entry
                    row.setdefault("warnings", []).append(
                        "Entry point resolves only when the room LYT position is applied to a room-local WOK."
                    )
            if not row["entry_point"]["on_walkable_face"]:
                row["errors"].append("IFO entry point is not on a recognized walkable WOK face.")
        else:
            row["errors"].append("MOD contains no readable IFO entry point.")
        row["walkmesh_summary"] = summarize_walkmeshes(row["walkmeshes"])
        row["openable"] = True
    except Exception:
        row["errors"].append(traceback.format_exc())
    row["audit_pass"] = bool(
        row.get("openable")
        and not row["errors"]
        and all(item.get("raw_structure_valid") for item in row["walkmeshes"])
        and not row.get("lyt_rooms_missing_wok")
    )
    return row


def audit_kmap(path: Path, *, module: str, game: str, roundtrip: bool) -> dict[str, Any]:
    row: dict[str, Any] = {
        "kind": "KMAP",
        "module": module,
        "game": game,
        "path": str(path),
        "exists": path.is_file(),
        "walkmeshes": [],
        "errors": [],
    }
    if not path.is_file():
        row["errors"].append("Indexed KMAP does not exist.")
        return row
    row["byte_size"] = path.stat().st_size
    row["sha256"] = _sha256_file(path)
    try:
        from src.core.level.kmap_serializer import KMapSerializer
        from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
        from src.core.modules.authored_module_project import compile_authored_room_spec
        from src.core.modules.authored_module_walkmesh import resolve_room_wok_module_offset

        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            project_file = KMapSerializer.load(path)
        payload = project_file.extra_sections.get("authored_module")
        if not isinstance(payload, dict):
            row["errors"].append("KMAP has no authored_module section.")
            return row
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            project = authored_project_from_kmap_payload(
                payload,
                fallback_name=module,
                fallback_game=game,
            )
        parsed_rooms: list[tuple[ParsedBwm, tuple[float, float, float]]] = []
        for room in project.rooms:
            resref = room.normalised_resref()
            try:
                geometry = compile_authored_room_spec(room)
                data = geometry.wok.to_bytes()
                parsed, report = audit_bwm_bytes(data, source=str(path), resref=resref)
                report["game"] = game
                report["kmap_room_position"] = tuple(float(item) for item in room.position)
                if roundtrip and parsed is not None:
                    report["roundtrip"] = exercise_wokdata_roundtrip(data, report, resref=resref)
                row["walkmeshes"].append(report)
                if parsed is not None:
                    offset, alignment_warning = resolve_room_wok_module_offset(room, geometry.wok)
                    parsed_rooms.append((parsed, tuple(float(item) for item in offset)))
                    if alignment_warning:
                        report["warnings"].append(alignment_warning)
            except Exception as exc:
                row["walkmeshes"].append(
                    {
                        "source": str(path),
                        "resref": resref,
                        "game": game,
                        "raw_structure_valid": False,
                        "errors": [f"KMAP room compile failed: {type(exc).__name__}: {exc}"],
                        "warnings": [],
                    }
                )
        row["room_count"] = len(project.rooms)
        row["wok_resource_count"] = len(row["walkmeshes"])
        entry = project.placements.entry_point
        row["entry_point"] = _point_on_walkmesh(tuple(float(item) for item in entry.position), parsed_rooms)
        if not row["entry_point"]["on_walkable_face"]:
            row["errors"].append("KMAP entry point is not on a recognized walkable WOK face.")
        row["walkmesh_summary"] = summarize_walkmeshes(row["walkmeshes"])
        row["openable"] = True
    except Exception:
        row["errors"].append(traceback.format_exc())
    row["audit_pass"] = bool(
        row.get("openable")
        and not row["errors"]
        and row.get("room_count", 0) == row.get("wok_resource_count", -1)
        and all(item.get("raw_structure_valid") for item in row["walkmeshes"])
    )
    return row


def compare_mod_kmap_walkmeshes(
    mod_report: dict[str, Any],
    kmap_report: dict[str, Any],
) -> dict[str, Any]:
    """Compare packaged MOD collision with the WOKs compiled from its KMAP.

    An independently valid MOD and KMAP can still disagree.  In particular,
    an imported empty visual-partition WOK used to become a bounds-derived
    NON_WALK rectangle when the KMAP was reopened.  Both binaries parsed, but
    the KMAP was no longer a safe editing/export round-trip.  Compare semantic
    geometry/material fingerprints and the engine-derived topology tables per
    room so that drift cannot hide behind two green standalone audits.
    """

    mod_by_room = {
        str(item.get("resref", "") or "").strip().lower(): item
        for item in tuple(mod_report.get("walkmeshes", ()) or ())
        if str(item.get("resref", "") or "").strip()
    }
    kmap_by_room = {
        str(item.get("resref", "") or "").strip().lower(): item
        for item in tuple(kmap_report.get("walkmeshes", ()) or ())
        if str(item.get("resref", "") or "").strip()
    }
    mod_rooms = set(mod_by_room)
    kmap_rooms = set(kmap_by_room)
    comparisons: list[dict[str, Any]] = []
    for room in sorted(mod_rooms & kmap_rooms):
        packaged = mod_by_room[room]
        editable = kmap_by_room[room]
        packaged_counts = dict(packaged.get("counts", {}) or {})
        editable_counts = dict(editable.get("counts", {}) or {})
        count_fields = (
            "faces",
            "walkable_material_faces",
            "nonwalk_material_faces",
            "adjacency_domain_faces",
        )
        # Vertex-count drift alone is diagnostic, not blocking: a source WOK
        # may carry an unreferenced legacy vertex that no face, adjacency row,
        # perimeter, or transition ever touches (774qgm_01a, cor_m56ag). The
        # semantic hash and derived tables still gate real geometry drift.
        diagnostic_count_fields = ("vertices",)
        count_mismatches = {
            field: {
                "mod": packaged_counts.get(field),
                "kmap": editable_counts.get(field),
            }
            for field in count_fields
            if packaged_counts.get(field) != editable_counts.get(field)
        }
        diagnostic_count_mismatches = {
            field: {
                "mod": packaged_counts.get(field),
                "kmap": editable_counts.get(field),
            }
            for field in diagnostic_count_fields
            if packaged_counts.get(field) != editable_counts.get(field)
        }
        semantic_match = (
            packaged.get("fingerprints", {}).get("semantic")
            == editable.get("fingerprints", {}).get("semantic")
        )
        derived_fields = {
            "adjacency": (
                packaged.get("fingerprints", {}).get("adjacency"),
                editable.get("fingerprints", {}).get("adjacency"),
            ),
            "boundary_edges": (
                packaged.get("perimeters", {}).get("boundary_edge_id_hash"),
                editable.get("perimeters", {}).get("boundary_edge_id_hash"),
            ),
            "perimeter_loops": (
                packaged.get("perimeters", {}).get("perimeter_loop_count"),
                editable.get("perimeters", {}).get("perimeter_loop_count"),
            ),
            "transition_records": (
                packaged.get("fingerprints", {}).get("transition_records"),
                editable.get("fingerprints", {}).get("transition_records"),
            ),
        }
        derived_mismatches = {
            field: {"mod": before, "kmap": after}
            for field, (before, after) in derived_fields.items()
            if before != after
        }
        surface_match = dict(packaged.get("surface_distribution", {}) or {}) == dict(
            editable.get("surface_distribution", {}) or {}
        )
        comparisons.append(
            {
                "resref": room,
                "semantic_match": semantic_match,
                "surface_distribution_match": surface_match,
                "derived_tables_match": not derived_mismatches,
                "count_mismatches": count_mismatches,
                "diagnostic_count_mismatches": diagnostic_count_mismatches,
                "derived_mismatches": derived_mismatches,
                "match": bool(
                    semantic_match
                    and surface_match
                    and not count_mismatches
                    and not derived_mismatches
                ),
            }
        )
    missing_in_kmap = sorted(mod_rooms - kmap_rooms)
    extra_in_kmap = sorted(kmap_rooms - mod_rooms)
    return {
        "attempted": True,
        "mod_audit_pass": bool(mod_report.get("audit_pass")),
        "kmap_audit_pass": bool(kmap_report.get("audit_pass")),
        "missing_in_kmap": missing_in_kmap,
        "extra_in_kmap": extra_in_kmap,
        "room_comparisons": comparisons,
        "mismatch_rooms": [item["resref"] for item in comparisons if not item["match"]],
        "all_match": bool(
            mod_report.get("audit_pass")
            and kmap_report.get("audit_pass")
            and not missing_in_kmap
            and not extra_in_kmap
            and all(item["match"] for item in comparisons)
        ),
    }


def audit_converted_library(
    status_path: Path,
    *,
    module_patterns: Sequence[str],
    games: set[str],
    roundtrip: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status_path": str(status_path),
        "status_exists": status_path.is_file(),
        "artifacts": [],
        "artifact_pairs": [],
        "errors": [],
    }
    if not status_path.is_file():
        result["errors"].append("Converted-module status file does not exist.")
        return result
    result["status_sha256"] = _sha256_file(status_path)
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        for candidate in status.get("candidates", []):
            module = str(candidate.get("module", "")).strip().lower()
            if not _matches(module, module_patterns):
                continue
            for game, output in sorted(dict(candidate.get("outputs") or {}).items()):
                game = str(game).upper()
                if game not in games or not isinstance(output, dict):
                    continue
                mod_report: dict[str, Any] | None = None
                kmap_report: dict[str, Any] | None = None
                if output.get("mod"):
                    mod_report = audit_mod(
                        Path(str(output["mod"])), module=module, game=game, roundtrip=roundtrip
                    )
                    result["artifacts"].append(mod_report)
                if output.get("kmap"):
                    kmap_report = audit_kmap(
                        Path(str(output["kmap"])), module=module, game=game, roundtrip=roundtrip
                    )
                    result["artifacts"].append(kmap_report)
                if mod_report is not None and kmap_report is not None:
                    result["artifact_pairs"].append(
                        {
                            "module": module,
                            "game": game,
                            "mod_path": mod_report.get("path", ""),
                            "kmap_path": kmap_report.get("path", ""),
                            "walkmesh_parity": compare_mod_kmap_walkmeshes(mod_report, kmap_report),
                        }
                    )
    except Exception:
        result["errors"].append(traceback.format_exc())
    result["summary"] = {
        "artifact_count": len(result["artifacts"]),
        "mod_count": sum(item.get("kind") == "MOD" for item in result["artifacts"]),
        "kmap_count": sum(item.get("kind") == "KMAP" for item in result["artifacts"]),
        "audit_pass_count": sum(bool(item.get("audit_pass")) for item in result["artifacts"]),
        "missing_artifact_count": sum(not item.get("exists") for item in result["artifacts"]),
        "entry_on_walkmesh_count": sum(
            bool(item.get("entry_point", {}).get("on_walkable_face")) for item in result["artifacts"]
        ),
        "walkmesh_resource_count": sum(len(item.get("walkmeshes", [])) for item in result["artifacts"]),
        "artifact_pair_count": len(result["artifact_pairs"]),
        "artifact_pair_pass_count": sum(
            bool(item.get("walkmesh_parity", {}).get("all_match"))
            for item in result["artifact_pairs"]
        ),
    }
    return result


def summarize_walkmeshes(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    surface_distribution: Counter[int] = Counter()
    for row in rows:
        for key, value in row.get("surface_distribution", {}).items():
            surface_distribution[int(key)] += int(value)
    return {
        "resource_count": len(rows),
        "raw_structure_valid_count": sum(bool(row.get("raw_structure_valid")) for row in rows),
        "raw_structure_error_count": sum(not bool(row.get("raw_structure_valid")) for row in rows),
        "warning_resource_count": sum(bool(row.get("warnings")) for row in rows),
        "vertex_count": sum(int(row.get("counts", {}).get("vertices", 0)) for row in rows),
        "face_count": sum(int(row.get("counts", {}).get("faces", 0)) for row in rows),
        "walkable_material_face_count": sum(
            int(row.get("counts", {}).get("walkable_material_faces", 0)) for row in rows
        ),
        "adjacency_domain_face_count": sum(
            int(row.get("counts", {}).get("adjacency_domain_faces", 0)) for row in rows
        ),
        "adjacency_mismatch_count": sum(
            int(row.get("adjacency", {}).get("raw_index_mismatch_count", 0)) for row in rows
        ),
        "nonreciprocal_adjacency_count": sum(
            int(row.get("adjacency", {}).get("nonreciprocal_count", 0)) for row in rows
        ),
        "nonmanifold_edge_count": sum(
            int(row.get("adjacency", {}).get("nonmanifold_edge_count", 0)) for row in rows
        ),
        "geometric_boundary_edge_count": sum(
            int(row.get("adjacency", {}).get("geometric_boundary_edge_count", 0)) for row in rows
        ),
        "perimeter_loop_count": sum(
            int(row.get("perimeters", {}).get("perimeter_loop_count", 0)) for row in rows
        ),
        "multi_loop_resource_count": sum(
            int(row.get("perimeters", {}).get("perimeter_loop_count", 0)) > 1 for row in rows
        ),
        "multi_component_resource_count": sum(
            int(row.get("adjacency", {}).get("component_count", 0)) > 1 for row in rows
        ),
        "open_perimeter_loop_count": sum(
            int(row.get("perimeters", {}).get("open_loop_count", 0)) for row in rows
        ),
        "transition_record_count": sum(
            int(row.get("perimeters", {}).get("transition_record_count", 0)) for row in rows
        ),
        "complete_aabb_count": sum(bool(row.get("aabb", {}).get("complete_one_leaf_per_face")) for row in rows),
        "incomplete_aabb_count": sum(
            bool(row.get("counts", {}).get("faces"))
            and not bool(row.get("aabb", {}).get("complete_one_leaf_per_face"))
            for row in rows
        ),
        "zero_area_face_count": sum(int(row.get("geometry", {}).get("zero_area_face_count", 0)) for row in rows),
        "slope_over_45_face_count": sum(int(row.get("geometry", {}).get("slope_over_45_count", 0)) for row in rows),
        "nonzero_position_count": sum(bool(row.get("header_vectors", {}).get("position_nonzero")) for row in rows),
        "roundtrip_attempt_count": sum(bool(row.get("roundtrip", {}).get("attempted")) for row in rows),
        "roundtrip_serialize_failure_count": sum(
            bool(row.get("roundtrip", {}).get("attempted")) and not bool(row.get("roundtrip", {}).get("serialized"))
            for row in rows
        ),
        "roundtrip_semantic_mismatch_count": sum(
            bool(row.get("roundtrip", {}).get("serialized")) and not bool(row.get("roundtrip", {}).get("semantic_match"))
            for row in rows
        ),
        "roundtrip_derived_mismatch_count": sum(
            bool(row.get("roundtrip", {}).get("serialized"))
            and not bool(row.get("roundtrip", {}).get("derived_tables_match"))
            for row in rows
        ),
        "roundtrip_output_invalid_count": sum(
            bool(row.get("roundtrip", {}).get("serialized"))
            and not bool(row.get("roundtrip", {}).get("output_raw_structure_valid"))
            for row in rows
        ),
        "surface_distribution": {str(key): value for key, value in sorted(surface_distribution.items())},
    }


def _aggregate_report(vanilla: Sequence[dict[str, Any]], converted: dict[str, Any] | None) -> dict[str, Any]:
    vanilla_rows = [row for game in vanilla for row in game.get("walkmeshes", [])]
    converted_rows = [
        row
        for artifact in (converted or {}).get("artifacts", [])
        for row in artifact.get("walkmeshes", [])
    ]
    return {
        "vanilla": summarize_walkmeshes(vanilla_rows),
        "converted": summarize_walkmeshes(converted_rows),
        "converted_artifacts": (converted or {}).get("summary", {}),
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    summary = report["summary"]
    lines = [
        "# Ghost Studio walkmesh-library audit",
        "",
        f"Generated: `{report['generated_utc']}`",
        "",
        "This is a read-only byte-structural and Ghost Studio round-trip audit. "
        "It is **not** retail KOTOR proof; converted packages still require a "
        "manual warp plus player-movement and camera-collision test.",
        "",
        "## Vanilla census",
        "",
        "| Scope | WOKs | Faces | Raw valid | Adj mismatches | Loops | Incomplete AABB | Round-trip failures |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for game in report.get("vanilla", []):
        item = game["summary"]
        lines.append(
            f"| {game['game']} | {item['resource_count']} | {item['face_count']} | "
            f"{item['raw_structure_valid_count']} | {item['adjacency_mismatch_count']} | "
            f"{item['perimeter_loop_count']} | {item['incomplete_aabb_count']} | "
            f"{item['roundtrip_serialize_failure_count']} |"
        )
    if not report.get("vanilla"):
        lines.append("| skipped | 0 | 0 | 0 | 0 | 0 | 0 | 0 |")

    converted = report.get("converted")
    lines.extend(["", "## Converted artifacts", ""])
    if not converted:
        lines.append("Converted audit was skipped.")
    else:
        item = converted.get("summary", {})
        lines.extend(
            [
                f"- Artifacts audited: **{item.get('artifact_count', 0)}**",
                f"- Artifact walkmesh gates passed: **{item.get('audit_pass_count', 0)}/{item.get('artifact_count', 0)}**",
                f"- MOD/KMAP walkmesh parity passed: **{item.get('artifact_pair_pass_count', 0)}/{item.get('artifact_pair_count', 0)}**",
                f"- WOK resources audited: **{item.get('walkmesh_resource_count', 0)}**",
                f"- Entry points on a recognized walkable face: **{item.get('entry_on_walkmesh_count', 0)}**",
                "",
                "| Module | Game | Kind | Rooms/WOKs | Raw errors | Entry on WOK | Result |",
                "|---|---|---|---:|---:|---:|---|",
            ]
        )
        for artifact in converted.get("artifacts", []):
            walkmesh_summary = artifact.get("walkmesh_summary", {})
            lines.append(
                f"| {artifact.get('module', '')} | {artifact.get('game', '')} | {artifact.get('kind', '')} | "
                f"{len(artifact.get('walkmeshes', []))} | {walkmesh_summary.get('raw_structure_error_count', 0)} | "
                f"{'yes' if artifact.get('entry_point', {}).get('on_walkable_face') else 'no'} | "
                f"{'pass' if artifact.get('audit_pass') else 'REVIEW'} |"
            )
        if converted.get("artifact_pairs"):
            lines.extend(
                [
                    "",
                    "### MOD to editable-KMAP collision parity",
                    "",
                    "| Module | Game | Compared rooms | Mismatch rooms | Result |",
                    "|---|---|---:|---|---|",
                ]
            )
            for pair in converted.get("artifact_pairs", []):
                parity = pair.get("walkmesh_parity", {})
                mismatches = ", ".join(parity.get("mismatch_rooms", [])) or "—"
                lines.append(
                    f"| {pair.get('module', '')} | {pair.get('game', '')} | "
                    f"{len(parity.get('room_comparisons', []))} | {mismatches} | "
                    f"{'pass' if parity.get('all_match') else 'REVIEW'} |"
                )

    findings: list[tuple[str, str, str]] = []
    for game in report.get("vanilla", []):
        for row in game.get("walkmeshes", []):
            if row.get("errors") or row.get("roundtrip", {}).get("error") or (
                row.get("roundtrip", {}).get("serialized") and not row.get("roundtrip", {}).get("semantic_match")
            ) or (
                row.get("roundtrip", {}).get("serialized") and not row.get("roundtrip", {}).get("derived_tables_match")
            ):
                detail = "; ".join(row.get("errors", [])) or str(row.get("roundtrip", {}).get("error", "round-trip mismatch"))
                findings.append((game["game"], row.get("resref", ""), detail))
    lines.extend(["", "## Vanilla exceptions and failures", ""])
    if not findings:
        lines.append("No raw-structure or semantic round-trip failures were found in the selected vanilla scope.")
    else:
        for game, resref, detail in findings[:100]:
            lines.append(f"- `{game}:{resref}` — {detail}")
        if len(findings) > 100:
            lines.append(f"- … {len(findings) - 100} additional rows are preserved in the JSON report.")

    lines.extend(
        [
            "",
            "## Interpretation rules",
            "",
            "- Vertex indices, not coordinate equality, define adjacency and intentional collision seams.",
            "- The serialized adjacency count defines its face domain; surface material alone does not.",
            "- Multiple closed perimeter loops and disconnected components are legal retail patterns.",
            "- A 45-degree slope is an authoring default, not a universal retail classifier.",
            "- Retail degeneracies and non-manifold exceptions are evidence to preserve on import, not valid generated output.",
            "- A generated area WOK should use a reachable full AABB tree with one leaf per face.",
            "",
            f"JSON detail: `{report['report_paths']['json']}`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--vanilla-only", action="store_true", help="Skip Converted/CONVERSION_STATUS.json.")
    scope.add_argument("--converted-only", action="store_true", help="Skip the vanilla chitin WOK census.")
    parser.add_argument(
        "--game",
        action="append",
        choices=("K1", "K2"),
        help="Game to scan; repeat for both. Defaults to K1 and K2.",
    )
    parser.add_argument(
        "--resref",
        action="append",
        default=[],
        help="Vanilla WOK resref or shell wildcard; repeatable.",
    )
    parser.add_argument("--match", help="Additional regular-expression filter for vanilla WOK resrefs.")
    parser.add_argument(
        "--module",
        action="append",
        default=[],
        help="Converted module root or shell wildcard; repeatable.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum vanilla WOKs per game after filtering (0 = all).")
    parser.add_argument("--no-roundtrip", action="store_true", help="Skip the in-memory Ghost Studio WOKData round-trip.")
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS, help="Converted CONVERSION_STATUS.json path.")
    parser.add_argument("--k1-root", type=Path, default=DEFAULT_GAMES["K1"])
    parser.add_argument("--k2-root", type=Path, default=DEFAULT_GAMES["K2"])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report-stem", default="walkmesh_library_audit")
    parser.add_argument("--progress-every", type=int, default=100)
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        help="Parallel vanilla audit worker processes (default: 4; use 1 for deterministic profiling).",
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Return exit code 1 for raw invalidity, round-trip failure, or converted artifact review rows.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    games = set(args.game or ("K1", "K2"))
    game_roots = {"K1": args.k1_root.expanduser().resolve(), "K2": args.k2_root.expanduser().resolve()}
    regex = re.compile(args.match, re.IGNORECASE) if args.match else None
    vanilla: list[dict[str, Any]] = []
    if not args.converted_only:
        for game in ("K1", "K2"):
            if game not in games:
                continue
            if not game_roots[game].is_dir():
                vanilla.append(
                    {
                        "game": game,
                        "installation": str(game_roots[game]),
                        "resource_count": 0,
                        "walkmeshes": [],
                        "summary": summarize_walkmeshes([]),
                        "errors": ["Game installation does not exist."],
                    }
                )
                continue
            vanilla.append(
                audit_vanilla_game(
                    game,
                    game_roots[game],
                    patterns=args.resref,
                    regex=regex,
                    limit=max(0, args.limit),
                    roundtrip=not args.no_roundtrip,
                    progress_every=max(0, args.progress_every),
                    jobs=max(1, args.jobs),
                )
            )

    converted = None
    if not args.vanilla_only:
        converted = audit_converted_library(
            args.status.expanduser().resolve(),
            module_patterns=args.module,
            games=games,
            roundtrip=not args.no_roundtrip,
        )

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{args.report_stem}.json"
    markdown_path = output_dir / f"{args.report_stem}.md"
    report = {
        "schema": "ghoststudio.walkmesh-library-audit.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "proof_scope": "read-only raw BWM structure + Ghost Studio in-memory round-trip; not retail game proof",
        "options": {
            "games": sorted(games),
            "resref_patterns": list(args.resref),
            "regex": args.match or "",
            "module_patterns": list(args.module),
            "limit_per_game": max(0, args.limit),
            "roundtrip": not args.no_roundtrip,
            "jobs": max(1, args.jobs),
            "vanilla_scanned": not args.converted_only,
            "converted_scanned": not args.vanilla_only,
        },
        "vanilla": vanilla,
        "converted": converted,
        "summary": _aggregate_report(vanilla, converted),
        "report_paths": {"json": str(json_path), "markdown": str(markdown_path)},
    }
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(report, markdown_path)
    print(json.dumps(report["summary"], indent=2, sort_keys=True), flush=True)
    print(f"JSON: {json_path}", flush=True)
    print(f"Markdown: {markdown_path}", flush=True)

    if not args.fail_on_findings:
        return 0
    vanilla_summary = report["summary"]["vanilla"]
    converted_summary = report["summary"]["converted_artifacts"]
    failed = bool(
        vanilla_summary["raw_structure_error_count"]
        or vanilla_summary["roundtrip_serialize_failure_count"]
        or vanilla_summary["roundtrip_semantic_mismatch_count"]
        or vanilla_summary["roundtrip_derived_mismatch_count"]
        or vanilla_summary["roundtrip_output_invalid_count"]
        or (
            converted_summary
            and converted_summary.get("audit_pass_count", 0) != converted_summary.get("artifact_count", 0)
        )
        or (
            converted_summary
            and converted_summary.get("artifact_pair_pass_count", 0)
            != converted_summary.get("artifact_pair_count", 0)
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
