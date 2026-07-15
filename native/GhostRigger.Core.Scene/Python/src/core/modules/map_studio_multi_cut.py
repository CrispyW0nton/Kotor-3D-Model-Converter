"""Headless, non-mutating Multi-Cut topology session for Map Studio.

The interactive viewport owns pointer capture and drawing.  This module owns
the durable modeling contract: stable source-component anchors, an immutable
before-state, deterministic preview evaluation, and one final mesh result plus
the one-to-many component remap needed by selection/undo.

The first production slice is intentionally narrower than Maya's full
Multi-Cut context.  It accepts exactly one two-anchor segment across one
connected, coplanar triangle patch.  Ambiguous overlaps, non-manifold paths,
creases, and a segment whose two ends both stop inside the same triangle are
refused instead of producing a plausible-looking but invalid KOTOR room mesh.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import math
import struct
from typing import Sequence

from src.core.geometry.mesh_topology import MeshTopology, normalize_edge

from .authored_imported_mesh import (
    MDL_MAX_VERTICES_PER_SURFACE,
    ImportedMeshRoomPrimitive,
    ImportedMeshSurface,
    imported_mesh_surface_index_for_role,
)


Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
Face = tuple[int, int, int]
RawEdge = tuple[int, int]


class MultiCutAnchorKind(str, Enum):
    """Stable source component used for one cut endpoint."""

    VERTEX = "vertex"
    EDGE = "edge"
    FACE = "face"


class MultiCutSessionState(str, Enum):
    INACTIVE = "inactive"
    ARMED_EMPTY = "armed_empty"
    BUILDING = "building"
    PREVIEW_VALID = "preview_valid"
    PREVIEW_INVALID = "preview_invalid"


@dataclass(frozen=True, slots=True)
class MultiCutAnchor:
    """A source-stable vertex, edge percentage, or face barycentric hit."""

    kind: MultiCutAnchorKind
    face_index: int
    vertex_index: int = -1
    edge_vertices: RawEdge = (-1, -1)
    edge_parameter: float = 0.0
    barycentric: tuple[float, float, float] = (0.0, 0.0, 0.0)

    @classmethod
    def vertex(cls, face_index: int, vertex_index: int) -> "MultiCutAnchor":
        return cls(MultiCutAnchorKind.VERTEX, int(face_index), vertex_index=int(vertex_index))

    @classmethod
    def edge(
        cls,
        face_index: int,
        edge_vertices: Sequence[int],
        parameter: float,
    ) -> "MultiCutAnchor":
        row = tuple(int(value) for value in edge_vertices)
        if len(row) != 2:
            raise ValueError("A Multi-Cut edge anchor requires exactly two ordered source vertices.")
        return cls(
            MultiCutAnchorKind.EDGE,
            int(face_index),
            edge_vertices=(row[0], row[1]),
            edge_parameter=float(parameter),
        )

    @classmethod
    def face(
        cls,
        face_index: int,
        barycentric: Sequence[float],
    ) -> "MultiCutAnchor":
        row = tuple(float(value) for value in barycentric)
        if len(row) != 3:
            raise ValueError("A Multi-Cut face anchor requires three barycentric weights.")
        return cls(MultiCutAnchorKind.FACE, int(face_index), barycentric=(row[0], row[1], row[2]))


@dataclass(frozen=True, slots=True)
class MultiCutSettings:
    """Validated options supported by the safe two-anchor implementation."""

    coplanar_angle_degrees: float = 0.5
    plane_tolerance: float = 1.0e-4
    boundary_tolerance: float = 1.0e-7

    def validated(self) -> "MultiCutSettings":
        angle = float(self.coplanar_angle_degrees)
        plane = float(self.plane_tolerance)
        boundary = float(self.boundary_tolerance)
        if not all(math.isfinite(value) for value in (angle, plane, boundary)):
            raise ValueError("Multi-Cut tolerances must be finite.")
        if not 0.0 <= angle <= 45.0:
            raise ValueError("Multi-Cut coplanar angle must be between 0 and 45 degrees.")
        if plane < 0.0 or boundary < 0.0:
            raise ValueError("Multi-Cut tolerances cannot be negative.")
        return replace(
            self,
            coplanar_angle_degrees=angle,
            plane_tolerance=plane,
            boundary_tolerance=boundary,
        )


@dataclass(frozen=True, slots=True)
class MultiCutTopologyRemap:
    """One-to-many source/result identity map for selection and undo."""

    old_vertex_to_new: tuple[tuple[int, ...], ...]
    new_vertex_to_old: tuple[tuple[int, ...], ...]
    old_face_to_new: tuple[tuple[int, ...], ...]
    new_face_to_old: tuple[int, ...]
    created_vertices: tuple[int, ...]
    created_faces: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MultiCutEvaluation:
    """A preview/commit candidate; invalid evaluations return the source mesh."""

    ok: bool
    primitive: ImportedMeshRoomPrimitive
    remap: MultiCutTopologyRemap | None
    diagnostics: tuple[str, ...]
    affected_faces: tuple[int, ...]
    cut_edges: tuple[RawEdge, ...]
    source_fingerprint: str
    result_fingerprint: str
    preview: bool


@dataclass(frozen=True, slots=True)
class _ResolvedAnchor:
    anchor: MultiCutAnchor
    point: Vec3
    source_vertices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _FaceInterval:
    face_index: int
    start: float
    end: float


@dataclass(frozen=True, slots=True)
class _CutPoint:
    index: int
    point: Vec3
    source_vertices: tuple[int, ...]
    interior: bool


def _sub(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _add(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))


def _scale(value: Sequence[float], amount: float) -> Vec3:
    return (float(value[0]) * amount, float(value[1]) * amount, float(value[2]) * amount)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(float(a[index]) * float(b[index]) for index in range(3))


def _cross(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return (
        (float(a[1]) * float(b[2])) - (float(a[2]) * float(b[1])),
        (float(a[2]) * float(b[0])) - (float(a[0]) * float(b[2])),
        (float(a[0]) * float(b[1])) - (float(a[1]) * float(b[0])),
    )


def _length(value: Sequence[float]) -> float:
    return math.sqrt(_dot(value, value))


def _normalized(value: Sequence[float], *, fallback: Vec3 = (0.0, 0.0, 1.0)) -> Vec3:
    magnitude = _length(value)
    if magnitude <= 1.0e-18:
        return fallback
    return _scale(value, 1.0 / magnitude)


def _lerp(a: Sequence[float], b: Sequence[float], amount: float) -> tuple[float, ...]:
    return tuple(float(a[index]) + ((float(b[index]) - float(a[index])) * amount) for index in range(len(a)))


def _face_normal(surface: ImportedMeshSurface, face_index: int) -> Vec3:
    face = surface.faces[int(face_index)]
    a, b, c = (surface.vertices[index] for index in face)
    return _normalized(_cross(_sub(b, a), _sub(c, a)), fallback=(0.0, 0.0, 0.0))


def _barycentric(surface: ImportedMeshSurface, face_index: int, point: Sequence[float]) -> tuple[float, float, float]:
    face = surface.faces[int(face_index)]
    a, b, c = (surface.vertices[index] for index in face)
    ab = _sub(b, a)
    ac = _sub(c, a)
    ap = _sub(point, a)
    dot00 = _dot(ab, ab)
    dot01 = _dot(ab, ac)
    dot11 = _dot(ac, ac)
    dot20 = _dot(ap, ab)
    dot21 = _dot(ap, ac)
    denominator = (dot00 * dot11) - (dot01 * dot01)
    if abs(denominator) <= 1.0e-18:
        raise ValueError(f"Multi-Cut cannot use degenerate source face {face_index}.")
    wb = ((dot11 * dot20) - (dot01 * dot21)) / denominator
    wc = ((dot00 * dot21) - (dot01 * dot20)) / denominator
    return (1.0 - wb - wc, wb, wc)


def _surface_for_role(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
) -> tuple[int, ImportedMeshSurface]:
    surface_index = imported_mesh_surface_index_for_role(primitive, mesh_role)
    if surface_index < 0:
        raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
    return surface_index, primitive.surfaces[surface_index]


def _validate_face(surface: ImportedMeshSurface, face_index: int) -> Face:
    index = int(face_index)
    if not 0 <= index < len(surface.faces):
        raise ValueError(f"Multi-Cut face {face_index} is outside the source surface.")
    face = tuple(int(value) for value in surface.faces[index])
    if len(face) != 3 or len(set(face)) != 3:
        raise ValueError("The safe Multi-Cut slice requires non-degenerate source triangles.")
    if any(value < 0 or value >= len(surface.vertices) for value in face):
        raise ValueError(f"Multi-Cut source face {face_index} contains an invalid vertex index.")
    if _length(_face_normal(surface, index)) <= 1.0e-12:
        raise ValueError(f"Multi-Cut source face {face_index} is degenerate.")
    return face  # type: ignore[return-value]


def _resolve_anchor(
    surface: ImportedMeshSurface,
    anchor: MultiCutAnchor,
    settings: MultiCutSettings,
) -> _ResolvedAnchor:
    face = _validate_face(surface, anchor.face_index)
    tolerance = max(settings.boundary_tolerance, 1.0e-9)
    if anchor.kind == MultiCutAnchorKind.VERTEX:
        vertex = int(anchor.vertex_index)
        if vertex not in face:
            raise ValueError("Multi-Cut vertex anchor no longer belongs to its source face.")
        return _ResolvedAnchor(anchor, tuple(surface.vertices[vertex]), (vertex,))
    if anchor.kind == MultiCutAnchorKind.EDGE:
        first, second = (int(value) for value in anchor.edge_vertices)
        if first == second or first not in face or second not in face:
            raise ValueError("Multi-Cut edge anchor no longer belongs to its source face.")
        boundary = {normalize_edge(face[index], face[(index + 1) % 3]) for index in range(3)}
        if normalize_edge(first, second) not in boundary:
            raise ValueError("Multi-Cut edge anchor must reference one source triangle boundary edge.")
        amount = float(anchor.edge_parameter)
        if not math.isfinite(amount) or not tolerance < amount < 1.0 - tolerance:
            raise ValueError("Multi-Cut edge percentage must lie strictly between its vertices; use a vertex anchor at an endpoint.")
        point = _lerp(surface.vertices[first], surface.vertices[second], amount)
        return _ResolvedAnchor(anchor, (point[0], point[1], point[2]), (first, second))
    if anchor.kind == MultiCutAnchorKind.FACE:
        weights = tuple(float(value) for value in anchor.barycentric)
        if not all(math.isfinite(value) for value in weights):
            raise ValueError("Multi-Cut face barycentric weights must be finite.")
        total = sum(weights)
        if abs(total - 1.0) > max(settings.boundary_tolerance * 4.0, 1.0e-6):
            raise ValueError("Multi-Cut face barycentric weights must sum to one.")
        if min(weights) <= tolerance or max(weights) >= 1.0 - tolerance:
            raise ValueError("Multi-Cut face anchors must lie inside the face; use an edge or vertex anchor on its boundary.")
        point = tuple(
            sum(float(surface.vertices[face[corner]][axis]) * weights[corner] for corner in range(3))
            for axis in range(3)
        )
        return _ResolvedAnchor(anchor, (point[0], point[1], point[2]), tuple(face))
    raise ValueError(f"Unsupported Multi-Cut anchor kind: {anchor.kind!r}")


def anchor_from_surface_hit(
    surface: ImportedMeshSurface,
    face_index: int,
    position: Sequence[float],
    *,
    snap_tolerance: float = 1.0e-5,
    plane_tolerance: float = 1.0e-4,
) -> MultiCutAnchor:
    """Convert a room-local face hit into a stable vertex/edge/face anchor."""

    face = _validate_face(surface, int(face_index))
    point = tuple(float(value) for value in tuple(position)[:3])
    if len(point) != 3 or not all(math.isfinite(value) for value in point):
        raise ValueError("Multi-Cut hit position must contain three finite coordinates.")
    normal = _face_normal(surface, int(face_index))
    plane_distance = _dot(_sub(point, surface.vertices[face[0]]), normal)
    if abs(plane_distance) > max(0.0, float(plane_tolerance)):
        raise ValueError("Multi-Cut hit is not on the selected source face plane.")
    projected = _sub(point, _scale(normal, plane_distance))
    weights = _barycentric(surface, int(face_index), projected)
    tolerance = max(0.0, float(snap_tolerance))
    if min(weights) < -tolerance or max(weights) > 1.0 + tolerance:
        raise ValueError("Multi-Cut hit lies outside the selected source triangle.")
    largest = max(range(3), key=lambda index: weights[index])
    if weights[largest] >= 1.0 - tolerance:
        return MultiCutAnchor.vertex(int(face_index), face[largest])
    smallest = min(range(3), key=lambda index: weights[index])
    if weights[smallest] <= tolerance:
        first_corner = (smallest + 1) % 3
        second_corner = (smallest + 2) % 3
        denominator = weights[first_corner] + weights[second_corner]
        if denominator <= 1.0e-18:
            raise ValueError("Multi-Cut could not derive a stable edge percentage from this hit.")
        return MultiCutAnchor.edge(
            int(face_index),
            (face[first_corner], face[second_corner]),
            weights[second_corner] / denominator,
        )
    total = sum(weights)
    normalized = tuple(value / total for value in weights)
    return MultiCutAnchor.face(int(face_index), normalized)


def multi_cut_mesh_fingerprint(primitive: ImportedMeshRoomPrimitive, mesh_role: str) -> str:
    """Return a deterministic selected-surface fingerprint for stale-preview checks."""

    _surface_index, surface = _surface_for_role(primitive, mesh_role)
    digest = hashlib.sha256()
    digest.update(str(mesh_role).encode("utf-8"))
    digest.update(str(surface.name).encode("utf-8"))
    for vertex in surface.vertices:
        digest.update(struct.pack("<3d", *(float(value) for value in vertex)))
    for face in surface.faces:
        digest.update(struct.pack("<3q", *(int(value) for value in face)))
    for channel, dimensions in ((surface.uvs, 2), (surface.normals, 3), (surface.uvs_lm, 2)):
        digest.update(struct.pack("<q", len(channel)))
        for value in channel:
            digest.update(struct.pack(f"<{dimensions}d", *(float(item) for item in value)))
    digest.update(struct.pack("<q", len(surface.face_mats)))
    for value in surface.face_mats:
        digest.update(struct.pack("<q", int(value)))
    return digest.hexdigest()


def _coplanar_component(
    surface: ImportedMeshSurface,
    start_face: int,
    settings: MultiCutSettings,
) -> set[int]:
    topology = MeshTopology.build(surface.vertices, surface.faces)
    if topology.invalid_faces:
        raise ValueError("Multi-Cut refuses a source surface with invalid face indices.")
    reference_normal = _face_normal(surface, start_face)
    reference_point = surface.vertices[surface.faces[start_face][0]]
    cosine = math.cos(math.radians(settings.coplanar_angle_degrees))

    def accepted(face_index: int) -> bool:
        normal = _face_normal(surface, face_index)
        if _dot(reference_normal, normal) < cosine:
            return False
        return all(
            abs(_dot(_sub(surface.vertices[vertex], reference_point), reference_normal)) <= settings.plane_tolerance
            for vertex in surface.faces[face_index]
        )

    component = {int(start_face)}
    pending = [int(start_face)]
    while pending:
        current = pending.pop()
        for neighbor in sorted(topology.geometric_face_to_faces.get(current, ())):
            neighbor = int(neighbor)
            if neighbor in component or not accepted(neighbor):
                continue
            component.add(neighbor)
            pending.append(neighbor)
    return component


def _clip_segment_to_face(
    surface: ImportedMeshSurface,
    face_index: int,
    start: Vec3,
    end: Vec3,
    tolerance: float,
) -> tuple[float, float] | None:
    start_weights = _barycentric(surface, face_index, start)
    end_weights = _barycentric(surface, face_index, end)
    lower, upper = 0.0, 1.0
    epsilon = max(tolerance, 1.0e-12)
    for at_start, at_end in zip(start_weights, end_weights):
        delta = at_end - at_start
        if abs(delta) <= epsilon:
            if at_start < -epsilon:
                return None
            continue
        crossing = -at_start / delta
        if delta > 0.0:
            lower = max(lower, crossing)
        else:
            upper = min(upper, crossing)
        if lower > upper + epsilon:
            return None
    lower = min(1.0, max(0.0, lower))
    upper = min(1.0, max(0.0, upper))
    if upper - lower <= epsilon:
        return None
    return lower, upper


def _trace_face_intervals(
    surface: ImportedMeshSurface,
    start_anchor: _ResolvedAnchor,
    end_anchor: _ResolvedAnchor,
    settings: MultiCutSettings,
) -> tuple[_FaceInterval, ...]:
    component = _coplanar_component(surface, start_anchor.anchor.face_index, settings)
    if end_anchor.anchor.face_index not in component:
        raise ValueError("Multi-Cut endpoints are not connected through one coplanar triangle patch.")
    intervals: list[_FaceInterval] = []
    for face_index in sorted(component):
        clipped = _clip_segment_to_face(
            surface,
            face_index,
            start_anchor.point,
            end_anchor.point,
            settings.boundary_tolerance,
        )
        if clipped is not None:
            intervals.append(_FaceInterval(face_index, clipped[0], clipped[1]))
    intervals.sort(key=lambda row: (row.start, row.end, row.face_index))
    if not intervals:
        raise ValueError("Multi-Cut segment does not cross a source triangle interior.")
    epsilon = max(settings.boundary_tolerance * 8.0, 1.0e-8)
    if intervals[0].face_index != start_anchor.anchor.face_index:
        raise ValueError(
            "Multi-Cut leaves its first boundary anchor through a different face; "
            "pick the intended side of that edge or vertex."
        )
    if intervals[-1].face_index != end_anchor.anchor.face_index:
        raise ValueError(
            "Multi-Cut reaches its final boundary anchor through a different face; "
            "pick the intended side of that edge or vertex."
        )
    if intervals[0].start > epsilon or intervals[-1].end < 1.0 - epsilon:
        raise ValueError("Multi-Cut could not trace the complete segment through the coplanar patch.")
    topology = MeshTopology.build(surface.vertices, surface.faces)

    def geometric_edges(face_index: int) -> set[RawEdge]:
        return {
            normalize_edge(row.geometric_origin, row.geometric_destination)
            for row in (
                topology.half_edges[index]
                for index in topology.face_to_half_edges.get(face_index, ())
            )
        }

    coverage = intervals[0].end
    for previous, current in zip(intervals, intervals[1:]):
        if current.start < previous.end - epsilon:
            raise ValueError("Multi-Cut segment crosses overlapping/coincident faces and is ambiguous.")
        if current.start > coverage + epsilon:
            raise ValueError("Multi-Cut segment leaves the connected triangle patch before its second anchor.")
        shared_edges = geometric_edges(previous.face_index) & geometric_edges(current.face_index)
        if len(shared_edges) != 1:
            raise ValueError(
                "Multi-Cut face transitions must cross one unambiguous shared edge; "
                "vertex-only or coincident transitions are refused."
            )
        shared_edge = next(iter(shared_edges))
        adjacent = tuple(topology.geometric_edge_to_faces.get(shared_edge, ()))
        if len(adjacent) != 2 or set(adjacent) != {previous.face_index, current.face_index}:
            raise ValueError("Multi-Cut path crosses a branched or non-manifold geometric edge.")
        coverage = max(coverage, current.end)
    return tuple(intervals)


def _classify_point(
    surface: ImportedMeshSurface,
    face_index: int,
    point: Vec3,
    tolerance: float,
) -> tuple[str, tuple[int, ...], tuple[float, float, float]]:
    face = surface.faces[face_index]
    weights = _barycentric(surface, face_index, point)
    epsilon = max(tolerance * 8.0, 1.0e-7)
    largest = max(range(3), key=lambda index: weights[index])
    if weights[largest] >= 1.0 - epsilon:
        return "vertex", (face[largest],), weights
    smallest = min(range(3), key=lambda index: weights[index])
    if weights[smallest] <= epsilon:
        return "edge", (face[(smallest + 1) % 3], face[(smallest + 2) % 3]), weights
    return "interior", tuple(face), weights


def _append_interpolated_vertex(
    surface: ImportedMeshSurface,
    vertices: list[Vec3],
    uvs: list[Vec2],
    normals: list[Vec3],
    uvs_lm: list[Vec2],
    face_index: int,
    point: Vec3,
    weights: tuple[float, float, float],
) -> int:
    face = surface.faces[face_index]
    index = len(vertices)
    vertices.append(point)

    def weighted(channel: Sequence[Sequence[float]], dimensions: int) -> tuple[float, ...]:
        return tuple(
            sum(float(channel[face[corner]][axis]) * weights[corner] for corner in range(3))
            for axis in range(dimensions)
        )

    if uvs:
        value = weighted(surface.uvs, 2)
        uvs.append((value[0], value[1]))
    if normals:
        value = _normalized(weighted(surface.normals, 3), fallback=_face_normal(surface, face_index))
        normals.append(value)
    if uvs_lm:
        value = weighted(surface.uvs_lm, 2)
        uvs_lm.append((value[0], value[1]))
    return index


def _triangle_area_along_normal(vertices: Sequence[Vec3], face: Sequence[int], normal: Vec3) -> float:
    a, b, c = (vertices[int(index)] for index in face)
    return _dot(_cross(_sub(b, a), _sub(c, a)), normal) * 0.5


def _oriented_triangle(
    vertices: Sequence[Vec3],
    row: Sequence[int],
    normal: Vec3,
    tolerance: float,
) -> Face | None:
    face = (int(row[0]), int(row[1]), int(row[2]))
    area = _triangle_area_along_normal(vertices, face, normal)
    if abs(area) <= tolerance:
        return None
    if area < 0.0:
        return (face[0], face[2], face[1])
    return face


def _triangulate_convex_polygon(
    vertices: Sequence[Vec3],
    polygon: Sequence[int],
    normal: Vec3,
    tolerance: float,
) -> list[Face]:
    ring = [int(value) for value in polygon]
    if len(ring) < 3:
        return []
    triangles: list[Face] = []
    while len(ring) > 3:
        ear = -1
        for index in range(len(ring)):
            candidate = (ring[(index - 1) % len(ring)], ring[index], ring[(index + 1) % len(ring)])
            if _triangle_area_along_normal(vertices, candidate, normal) > tolerance:
                ear = index
                triangles.append(candidate)
                break
        if ear < 0:
            raise ValueError("Multi-Cut could not triangulate a cut polygon without a degenerate face.")
        del ring[ear]
    final = _oriented_triangle(vertices, ring, normal, tolerance)
    if final is None:
        raise ValueError("Multi-Cut ended with a degenerate cut polygon.")
    triangles.append(final)
    return triangles


def _insert_boundary_points(
    face: Face,
    point_rows: Sequence[tuple[_CutPoint, tuple[int, ...]]],
) -> list[int]:
    ring: list[int] = []
    by_edge: dict[RawEdge, list[_CutPoint]] = {}
    for point, source in point_rows:
        if point.interior or len(source) != 2:
            continue
        by_edge.setdefault(normalize_edge(source[0], source[1]), []).append(point)
    for corner in range(3):
        first = face[corner]
        second = face[(corner + 1) % 3]
        ring.append(first)
        rows = by_edge.get(normalize_edge(first, second), [])
        if rows:
            # One straight segment can cross a triangle edge once.  More rows
            # indicate coincident/duplicated anchors and are ambiguous.
            unique = {row.index for row in rows}
            if len(unique) > 1:
                raise ValueError("Multi-Cut produced multiple points on one triangle edge.")
            point = rows[0]
            if point.index not in (first, second):
                ring.append(point.index)
    return ring


def _split_face_by_chord(
    surface: ImportedMeshSurface,
    vertices: Sequence[Vec3],
    face_index: int,
    first: _CutPoint,
    second: _CutPoint,
    tolerance: float,
) -> list[Face]:
    face = tuple(int(value) for value in surface.faces[face_index])
    normal = _face_normal(surface, face_index)
    if first.index == second.index:
        raise ValueError("Multi-Cut segment collapses to one source component.")
    if first.interior and second.interior:
        raise ValueError("This safe Multi-Cut slice does not cut between two interior points in one triangle.")
    rows = ((first, first.source_vertices), (second, second.source_vertices))
    boundary = _insert_boundary_points(face, rows)
    if first.interior or second.interior:
        interior = first if first.interior else second
        boundary_point = second if first.interior else first
        if boundary_point.index not in boundary:
            raise ValueError("Multi-Cut boundary endpoint was not found on its source triangle.")
        triangles: list[Face] = []
        for index, current in enumerate(boundary):
            following = boundary[(index + 1) % len(boundary)]
            row = _oriented_triangle(vertices, (interior.index, current, following), normal, tolerance)
            if row is not None:
                triangles.append(row)
        if len(triangles) < 3:
            raise ValueError("Multi-Cut interior endpoint did not produce a complete triangle fan.")
        return triangles
    if first.index not in boundary or second.index not in boundary:
        raise ValueError("Multi-Cut endpoints were not found on the triangle boundary.")
    first_at = boundary.index(first.index)
    second_at = boundary.index(second.index)
    if first_at == second_at:
        raise ValueError("Multi-Cut boundary endpoints resolve to the same point.")

    def path(start: int, end: int) -> list[int]:
        result = [boundary[start]]
        index = start
        while index != end:
            index = (index + 1) % len(boundary)
            result.append(boundary[index])
        return result

    first_polygon = path(first_at, second_at)
    second_polygon = path(second_at, first_at)
    if len(first_polygon) < 3 or len(second_polygon) < 3:
        raise ValueError("Multi-Cut segment lies on an existing triangle boundary and creates no new face.")
    return (
        _triangulate_convex_polygon(vertices, first_polygon, normal, tolerance)
        + _triangulate_convex_polygon(vertices, second_polygon, normal, tolerance)
    )


def _evaluate_valid_session(session: "MultiCutSession", *, preview: bool) -> MultiCutEvaluation:
    primitive = session.source_primitive
    surface_index, surface = _surface_for_role(primitive, session.mesh_role)
    settings = session.settings.validated()
    source_fingerprint = multi_cut_mesh_fingerprint(primitive, session.mesh_role)
    if source_fingerprint != session.source_fingerprint:
        raise ValueError("Multi-Cut source changed after the session began; cancel and start a new cut.")
    if len(session.anchors) != 2:
        raise ValueError("The safe Multi-Cut slice requires exactly two anchors before preview or commit.")
    first = _resolve_anchor(surface, session.anchors[0], settings)
    second = _resolve_anchor(surface, session.anchors[1], settings)
    if _length(_sub(first.point, second.point)) <= max(settings.boundary_tolerance, 1.0e-8):
        raise ValueError("Multi-Cut anchors are too close together to create a stable segment.")
    intervals = _trace_face_intervals(surface, first, second, settings)

    vertices = [tuple(value) for value in surface.vertices]
    uvs = [tuple(value) for value in surface.uvs] if len(surface.uvs) == len(surface.vertices) else []
    normals = [tuple(value) for value in surface.normals] if len(surface.normals) == len(surface.vertices) else []
    uvs_lm = [tuple(value) for value in surface.uvs_lm] if len(surface.uvs_lm) == len(surface.vertices) else []
    face_materials = list(surface.face_mats) if len(surface.face_mats) == len(surface.faces) else []
    edge_point_cache: dict[tuple[RawEdge, int], _CutPoint] = {}
    point_cache: dict[tuple[int, int], _CutPoint] = {}
    new_vertex_sources: list[tuple[int, ...]] = [(index,) for index in range(len(vertices))]
    segment = _sub(second.point, first.point)
    quantizer = 1.0 / max(settings.boundary_tolerance * 8.0, 1.0e-9)

    def cut_point(face_index: int, amount: float) -> _CutPoint:
        point = _add(first.point, _scale(segment, amount))
        kind, source_vertices, weights = _classify_point(
            surface,
            face_index,
            point,
            settings.boundary_tolerance,
        )
        if kind == "vertex":
            return _CutPoint(source_vertices[0], tuple(surface.vertices[source_vertices[0]]), source_vertices, False)
        quantized = int(round(amount * quantizer))
        key = (normalize_edge(*source_vertices), quantized) if kind == "edge" else (face_index, quantized)
        cache = edge_point_cache if kind == "edge" else point_cache
        cached = cache.get(key)
        if cached is not None:
            return cached
        index = _append_interpolated_vertex(
            surface,
            vertices,
            uvs,
            normals,
            uvs_lm,
            face_index,
            point,
            weights,
        )
        row = _CutPoint(index, point, tuple(int(value) for value in source_vertices), kind == "interior")
        cache[key] = row
        new_vertex_sources.append(row.source_vertices)
        return row

    replacements: dict[int, list[Face]] = {}
    cut_edges: list[RawEdge] = []
    area_tolerance = max(settings.boundary_tolerance * settings.boundary_tolerance, 1.0e-14)
    for interval in intervals:
        start_point = cut_point(interval.face_index, interval.start)
        end_point = cut_point(interval.face_index, interval.end)
        replacements[interval.face_index] = _split_face_by_chord(
            surface,
            vertices,
            interval.face_index,
            start_point,
            end_point,
            area_tolerance,
        )
        cut_edges.append(normalize_edge(start_point.index, end_point.index))
    if len(vertices) > MDL_MAX_VERTICES_PER_SURFACE:
        raise ValueError(
            f"Multi-Cut would exceed KOTOR's {MDL_MAX_VERTICES_PER_SURFACE}-vertex MDL surface limit."
        )

    faces: list[Face] = []
    mats: list[int] = []
    old_face_to_new: list[tuple[int, ...]] = []
    new_face_to_old: list[int] = []
    created_faces: list[int] = []
    for old_face, source_face in enumerate(surface.faces):
        generated = replacements.get(old_face, [tuple(int(value) for value in source_face)])
        mapped: list[int] = []
        for generated_face in generated:
            new_index = len(faces)
            faces.append(generated_face)
            mapped.append(new_index)
            new_face_to_old.append(old_face)
            if len(generated) != 1 or generated_face != tuple(source_face):
                created_faces.append(new_index)
            if face_materials:
                mats.append(int(face_materials[old_face]))
        old_face_to_new.append(tuple(mapped))

    rebuilt = replace(
        surface,
        vertices=tuple(vertices),
        faces=tuple(faces),
        face_mats=tuple(mats) if face_materials else (),
        uvs=tuple(uvs),
        normals=tuple(normals),
        uvs_lm=tuple(uvs_lm),
    )
    source_audit = MeshTopology.build(surface.vertices, surface.faces).validate_manifold_state()
    result_audit = MeshTopology.build(rebuilt.vertices, rebuilt.faces).validate_manifold_state()
    if result_audit.invalid_faces or result_audit.degenerate_faces or result_audit.non_manifold_edges:
        raise ValueError("Multi-Cut result failed topology validation (invalid, degenerate, or non-manifold faces).")
    if set(result_audit.duplicate_faces) - set(source_audit.duplicate_faces):
        raise ValueError("Multi-Cut result introduced duplicate faces.")
    if set(result_audit.inconsistent_winding_edges) - set(source_audit.inconsistent_winding_edges):
        raise ValueError("Multi-Cut result introduced inconsistent face winding.")

    old_vertex_to_new: list[list[int]] = [[index] for index in range(len(surface.vertices))]
    for new_index in range(len(surface.vertices), len(vertices)):
        for old_index in new_vertex_sources[new_index]:
            old_vertex_to_new[old_index].append(new_index)
    remap = MultiCutTopologyRemap(
        old_vertex_to_new=tuple(tuple(row) for row in old_vertex_to_new),
        new_vertex_to_old=tuple(tuple(row) for row in new_vertex_sources),
        old_face_to_new=tuple(old_face_to_new),
        new_face_to_old=tuple(new_face_to_old),
        created_vertices=tuple(range(len(surface.vertices), len(vertices))),
        created_faces=tuple(created_faces),
    )
    surfaces = list(primitive.surfaces)
    surfaces[surface_index] = rebuilt
    metadata = dict(primitive.metadata)
    metadata["last_topology_edit"] = {
        "operation": "multi_cut_segment",
        "mesh_role": session.mesh_role,
        "source_faces": [row.face_index for row in intervals],
        "created_vertex_count": len(remap.created_vertices),
        "created_face_count": len(remap.created_faces),
        "preview": bool(preview),
        "contract": "two_anchor_coplanar_triangle_patch_v1",
        "walkmesh_policy": "requires_review",
    }
    result = replace(primitive, surfaces=tuple(surfaces), metadata=metadata)
    result_fingerprint = multi_cut_mesh_fingerprint(result, session.mesh_role)
    return MultiCutEvaluation(
        ok=True,
        primitive=result,
        remap=remap,
        diagnostics=(
            "Multi-Cut evaluated one two-anchor segment across a connected coplanar triangle patch.",
            "Full Maya slicing, subdivisions, edge flow, and chained segments are not part of this safe slice.",
        ),
        affected_faces=tuple(row.face_index for row in intervals),
        cut_edges=tuple(cut_edges),
        source_fingerprint=source_fingerprint,
        result_fingerprint=result_fingerprint,
        preview=bool(preview),
    )


@dataclass(frozen=True, slots=True)
class MultiCutSession:
    """Persistent immutable Multi-Cut context with exact cancel semantics."""

    source_primitive: ImportedMeshRoomPrimitive
    mesh_role: str
    settings: MultiCutSettings = field(default_factory=MultiCutSettings)
    anchors: tuple[MultiCutAnchor, ...] = ()
    state: MultiCutSessionState = MultiCutSessionState.ARMED_EMPTY
    diagnostics: tuple[str, ...] = ()
    source_fingerprint: str = ""

    @classmethod
    def begin(
        cls,
        primitive: ImportedMeshRoomPrimitive,
        mesh_role: str,
        *,
        settings: MultiCutSettings | None = None,
    ) -> "MultiCutSession":
        snapshot = deepcopy(primitive)
        resolved_settings = (settings or MultiCutSettings()).validated()
        fingerprint = multi_cut_mesh_fingerprint(snapshot, mesh_role)
        return cls(
            source_primitive=snapshot,
            mesh_role=str(mesh_role),
            settings=resolved_settings,
            state=MultiCutSessionState.ARMED_EMPTY,
            source_fingerprint=fingerprint,
        )

    def add_anchor(self, anchor: MultiCutAnchor) -> "MultiCutSession":
        if self.state == MultiCutSessionState.INACTIVE:
            raise ValueError("Multi-Cut session is inactive; begin a new session first.")
        if len(self.anchors) >= 2:
            raise ValueError("This safe Multi-Cut slice accepts exactly two anchors; commit or clear the current segment.")
        anchors = self.anchors + (anchor,)
        if len(anchors) == 1:
            # Resolve immediately so a stale/invalid first component never
            # enters the pointer-preview loop.
            _surface_index, surface = _surface_for_role(self.source_primitive, self.mesh_role)
            _resolve_anchor(surface, anchor, self.settings)
            return replace(
                self,
                anchors=anchors,
                state=MultiCutSessionState.BUILDING,
                diagnostics=(),
            )
        candidate = replace(self, anchors=anchors, state=MultiCutSessionState.PREVIEW_VALID, diagnostics=())
        evaluation = candidate.preview()
        return replace(
            candidate,
            state=MultiCutSessionState.PREVIEW_VALID if evaluation.ok else MultiCutSessionState.PREVIEW_INVALID,
            diagnostics=evaluation.diagnostics if not evaluation.ok else (),
        )

    def pop_anchor(self) -> "MultiCutSession":
        if self.state == MultiCutSessionState.INACTIVE or not self.anchors:
            return self
        anchors = self.anchors[:-1]
        return replace(
            self,
            anchors=anchors,
            state=MultiCutSessionState.BUILDING if anchors else MultiCutSessionState.ARMED_EMPTY,
            diagnostics=(),
        )

    def clear(self) -> "MultiCutSession":
        if self.state == MultiCutSessionState.INACTIVE:
            return self
        return replace(self, anchors=(), state=MultiCutSessionState.ARMED_EMPTY, diagnostics=())

    def cancel(self) -> "MultiCutSession":
        return replace(self, anchors=(), state=MultiCutSessionState.INACTIVE, diagnostics=())

    def _evaluate(self, *, preview: bool) -> MultiCutEvaluation:
        try:
            return _evaluate_valid_session(self, preview=preview)
        except ValueError as exc:
            source = self.source_primitive
            fingerprint = multi_cut_mesh_fingerprint(source, self.mesh_role)
            return MultiCutEvaluation(
                ok=False,
                primitive=source,
                remap=None,
                diagnostics=(str(exc),),
                affected_faces=(),
                cut_edges=(),
                source_fingerprint=self.source_fingerprint,
                result_fingerprint=fingerprint,
                preview=bool(preview),
            )

    def preview(self) -> MultiCutEvaluation:
        """Evaluate against the immutable before-state without changing KMAP."""

        return self._evaluate(preview=True)

    def commit(self) -> MultiCutEvaluation:
        """Return the one-shot final primitive; the caller owns one undo command."""

        return self._evaluate(preview=False)


__all__ = [
    "MultiCutAnchor",
    "MultiCutAnchorKind",
    "MultiCutEvaluation",
    "MultiCutSession",
    "MultiCutSessionState",
    "MultiCutSettings",
    "MultiCutTopologyRemap",
    "anchor_from_surface_hit",
    "multi_cut_mesh_fingerprint",
]
