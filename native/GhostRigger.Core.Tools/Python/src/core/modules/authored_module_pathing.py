"""Headless authored PTH/path graph compiler for Map Studio.

KOTOR module PTH files are GFF resources used by the engine's pathfinding
loader.  Map Studio should author this as editable path intent first, then
compile it to the Odyssey ``Path_Points`` / ``Path_Conections`` fields through
a reusable Qt-free service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
from math import ceil, hypot, isfinite, sqrt
from typing import Any

from .module_format import WALKABLE_IDS
from .authored_walkmesh_sampling import (
    POINT_IN_TRIANGLE_EPSILON,
    _face_contains_xy,
    walkmesh_face_at_xy,
)


Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
WALKABLE_SURFACE_IDS = frozenset(WALKABLE_IDS)


@dataclass(frozen=True)
class AuthoredPathAnchor:
    """Gameplay anchor that should be represented in the path graph."""

    label: str
    position: Vec3
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthoredPathingRoom:
    """One LYT-ordered room participating in module PTH generation.

    ``position`` is the translation required to put the room WOK into module
    coordinates.  Retail WOKs can already be module-space, so callers must
    pass ``(0, 0, 0)`` for that coordinate policy rather than blindly adding
    the LYT row again.  Transition destinations are indices into this exact
    room tuple, matching Odyssey's LYT-order contract.
    """

    room_resref: str
    wok: Any
    position: Vec3 = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class AuthoredPathPoint:
    """Editable path point before PTH serialization."""

    label: str
    x: float
    y: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthoredPathConnection:
    """Directed path edge between authored path point indices."""

    source: int
    target: int


@dataclass(frozen=True)
class AuthoredPathGraph:
    """Editable path graph for a single authored module area."""

    points: tuple[AuthoredPathPoint, ...]
    connections: tuple[AuthoredPathConnection, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthoredPathingValidation:
    ok: bool
    warnings: tuple[str, ...] = ()
    blocking_issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompiledAuthoredPathing:
    """Serialized PTH output plus graph, validation, and provenance."""

    pth_bytes: bytes
    graph: AuthoredPathGraph
    validation: AuthoredPathingValidation
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _TransitionEdge:
    source_room: int
    target_room: int
    face_index: int
    local_edge: int
    midpoint: Vec3
    inward_point: Vec2
    component_index: int


@dataclass
class _TranslatedWalkmesh:
    """Minimal WOK-shaped view with vertices translated to module space."""

    verts: list[Vec3]
    faces: list[Any]


def _xy_key(x: float, y: float) -> tuple[int, int]:
    return (round(float(x) * 1000), round(float(y) * 1000))


def _walkmesh_bounds(wok: Any) -> tuple[float, float, float, float]:
    vertices = list(getattr(wok, "verts", ()) or ())
    if not vertices:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [float(vertex[0]) for vertex in vertices]
    ys = [float(vertex[1]) for vertex in vertices]
    return (min(xs), min(ys), max(xs), max(ys))


class _WalkmeshFaceGrid:
    """XY bucket grid over WOK faces for O(faces-per-cell) point queries.

    The path-graph builder samples every candidate connection at 0.5-unit
    intervals and tests each sample against the walkmesh.  The default
    ``face_at_point`` is a linear scan over all faces, so a dense walkmesh
    (a floor-filled converted room can reach thousands of faces) made pathing
    O(connections x samples x faces) and stalled export for many minutes.
    Bucketing faces once makes each sample query touch only its own cell.
    """

    __slots__ = ("_faces", "_verts", "_cell", "_min_x", "_min_y", "_buckets", "_ready")

    def __init__(self, wok: Any, *, target_cells_across: int = 128) -> None:
        self._faces = list(getattr(wok, "faces", ()) or ())
        self._verts = list(getattr(wok, "verts", ()) or ())
        self._buckets: dict[tuple[int, int], list[int]] = {}
        self._ready = False
        if not self._faces or not self._verts:
            self._cell = 1.0
            self._min_x = self._min_y = 0.0
            return
        xs = [float(v[0]) for v in self._verts]
        ys = [float(v[1]) for v in self._verts]
        self._min_x, self._min_y = min(xs), min(ys)
        span = max(max(xs) - self._min_x, max(ys) - self._min_y, 1.0)
        self._cell = max(1.0, span / max(1, int(target_cells_across)))
        for face_index, face in enumerate(self._faces):
            indices = _face_indices(face)
            if any(index < 0 or index >= len(self._verts) for index in indices):
                continue
            fxs = [float(self._verts[i][0]) for i in indices]
            fys = [float(self._verts[i][1]) for i in indices]
            for col in range(self._col(min(fxs)), self._col(max(fxs)) + 1):
                for row in range(self._row(min(fys)), self._row(max(fys)) + 1):
                    self._buckets.setdefault((col, row), []).append(face_index)
        self._ready = True

    def _col(self, x: float) -> int:
        return int((float(x) - self._min_x) // self._cell)

    def _row(self, y: float) -> int:
        return int((float(y) - self._min_y) // self._cell)

    def face_at(self, x: float, y: float, *, epsilon: float = POINT_IN_TRIANGLE_EPSILON) -> int:
        if not self._ready:
            return -1
        x = float(x)
        y = float(y)
        if not (isfinite(x) and isfinite(y)):
            return -1
        col = self._col(x)
        row = self._row(y)
        # Point-in-triangle admits a small epsilon outside a triangle.  Query
        # neighboring cells too so a sample just across a bucket boundary has
        # the same first-face result as the canonical linear scan.
        candidates: set[int] = set()
        for col_offset in (-1, 0, 1):
            for row_offset in (-1, 0, 1):
                candidates.update(self._buckets.get((col + col_offset, row + row_offset), ()))
        for face_index in sorted(candidates):
            if _face_contains_xy(self._verts, self._faces[face_index], x, y, epsilon=epsilon):
                return face_index
        return -1


def _point_on_walkmesh(wok: Any, x: float, y: float, *, grid: _WalkmeshFaceGrid | None = None) -> tuple[bool, int]:
    if grid is not None:
        face_index = grid.face_at(float(x), float(y))
    else:
        face_index = walkmesh_face_at_xy(wok, float(x), float(y))
    if face_index < 0:
        return False, face_index
    faces = list(getattr(wok, "faces", ()) or ())
    if face_index < len(faces):
        surface = getattr(faces[face_index], "surface", None)
        if surface is not None and int(surface) not in WALKABLE_SURFACE_IDS:
            return False, face_index
    return True, face_index


def _connection_on_walkmesh(
    wok: Any,
    source: AuthoredPathPoint,
    target: AuthoredPathPoint,
    *,
    sample_interval: float,
    grid: _WalkmeshFaceGrid | None = None,
) -> tuple[bool, tuple[float, float, int] | None]:
    distance = hypot(float(target.x) - float(source.x), float(target.y) - float(source.y))
    if distance <= 1.0e-7:
        return True, None
    steps = max(1, int(ceil(distance / sample_interval)))
    for step in range(1, steps):
        fraction = step / steps
        x = float(source.x) + (float(target.x) - float(source.x)) * fraction
        y = float(source.y) + (float(target.y) - float(source.y)) * fraction
        ok, _face_index = _point_on_walkmesh(wok, x, y, grid=grid)
        if not ok:
            return False, (x, y, step)
    return True, None


def _face_indices(face: Any) -> tuple[int, int, int]:
    return int(getattr(face, "v1", -1)), int(getattr(face, "v2", -1)), int(getattr(face, "v3", -1))


def _face_centroid(wok: Any, face_index: int) -> tuple[float, float] | None:
    # WOKData exposes indexable lists.  Copying both complete arrays for every
    # centroid made this helper quadratic (32,768 copies of a 32,768-face list
    # for a 129x129 terrain) and dominated terrain readiness on stroke release.
    faces = getattr(wok, "faces", ()) or ()
    verts = getattr(wok, "verts", ()) or ()
    if face_index < 0 or face_index >= len(faces):
        return None
    indices = _face_indices(faces[face_index])
    if any(index < 0 or index >= len(verts) for index in indices):
        return None
    return (
        sum(float(verts[index][0]) for index in indices) / 3.0,
        sum(float(verts[index][1]) for index in indices) / 3.0,
    )


def _walkable_topology(
    wok: Any,
) -> tuple[tuple[tuple[int, ...], ...], dict[int, set[int]], dict[int, int]]:
    """Return raw-index walkable components, face adjacency, and membership."""

    faces = list(getattr(wok, "faces", ()) or ())
    verts = list(getattr(wok, "verts", ()) or ())
    walkable: set[int] = set()
    # Odyssey topology is defined by vertex indices.  Retail WOKs often keep
    # duplicate-coordinate vertices to form intentional collision seams; a
    # coordinate-rounded key falsely welds those seams and produces one PTH
    # component spanning two disconnected regions.
    edge_faces: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for face_index, face in enumerate(faces):
        if int(getattr(face, "surface", -1)) not in WALKABLE_SURFACE_IDS:
            continue
        indices = _face_indices(face)
        if any(index < 0 or index >= len(verts) for index in indices):
            continue
        walkable.add(face_index)
        for local_edge, (left, right) in enumerate(
            ((indices[0], indices[1]), (indices[1], indices[2]), (indices[2], indices[0]))
        ):
            key = (left, right) if left <= right else (right, left)
            edge_faces.setdefault(key, []).append((face_index, local_edge))

    adjacency: dict[int, set[int]] = {face_index: set() for face_index in walkable}
    for owners in edge_faces.values():
        unique = sorted({face_index for face_index, _local_edge in owners})
        for left in unique:
            for right in unique:
                if left != right:
                    adjacency[left].add(right)

    # Honour an imported/serialized adjacency row only when it agrees with the
    # exact indexed edge.  This retains valid BWM adjacency while refusing a
    # stale coordinate-welded row that would bridge a deliberate index seam.
    for face_index in walkable:
        face = faces[face_index]
        indices = _face_indices(face)
        for local_edge, adjacent_value in enumerate(
            (int(getattr(face, "adj1", -1)), int(getattr(face, "adj2", -1)), int(getattr(face, "adj3", -1)))
        ):
            if adjacent_value < 0:
                continue
            edge = tuple(sorted((indices[local_edge], indices[(local_edge + 1) % 3])))
            owners = edge_faces.get(edge, ())
            owner_faces = {owner_face for owner_face, _owner_edge in owners if owner_face != face_index}
            # WOKData normally stores adjacent face indices.  Its fallback raw
            # parser can expose Odyssey's face*3+edge row, so accept that form
            # too, but only after the shared raw-index edge proves the link.
            candidates = (adjacent_value, adjacent_value // 3)
            adjacent = next((candidate for candidate in candidates if candidate in owner_faces), -1)
            if adjacent in walkable:
                adjacency[face_index].add(adjacent)
                adjacency[adjacent].add(face_index)

    components: list[tuple[int, ...]] = []
    remaining = set(walkable)
    while remaining:
        start = remaining.pop()
        stack = [start]
        component = [start]
        while stack:
            current = stack.pop()
            for neighbor in adjacency.get(current, ()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.append(neighbor)
                    stack.append(neighbor)
        components.append(tuple(sorted(component)))
    ordered = tuple(sorted(components, key=lambda item: (-len(item), item[0] if item else -1)))
    component_by_face = {
        face_index: component_index
        for component_index, component in enumerate(ordered)
        for face_index in component
    }
    return ordered, adjacency, component_by_face


def _walkable_components(wok: Any) -> tuple[tuple[int, ...], ...]:
    return _walkable_topology(wok)[0]


def _translated_walkmesh(room: AuthoredPathingRoom) -> _TranslatedWalkmesh:
    px, py, pz = (float(value) for value in room.position)
    return _TranslatedWalkmesh(
        verts=[
            (float(vertex[0]) + px, float(vertex[1]) + py, float(vertex[2]) + pz)
            for vertex in (getattr(room.wok, "verts", ()) or ())
        ],
        faces=list(getattr(room.wok, "faces", ()) or ()),
    )


def _edge_vertices(face: Any, local_edge: int) -> tuple[int, int]:
    indices = _face_indices(face)
    return indices[local_edge], indices[(local_edge + 1) % 3]


def _transition_edges_for_room(
    room_index: int,
    wok: Any,
    component_by_face: dict[int, int],
) -> tuple[_TransitionEdge, ...]:
    faces = list(getattr(wok, "faces", ()) or ())
    verts = list(getattr(wok, "verts", ()) or ())
    rows: list[_TransitionEdge] = []
    for face_index, face in enumerate(faces):
        transitions = (
            int(getattr(face, "trans1", -1)),
            int(getattr(face, "trans2", -1)),
            int(getattr(face, "trans3", -1)),
        )
        for local_edge, target_room in enumerate(transitions):
            if target_room < 0:
                continue
            left, right = _edge_vertices(face, local_edge)
            if left < 0 or right < 0 or left >= len(verts) or right >= len(verts):
                midpoint = (float("nan"), float("nan"), float("nan"))
                inward = (float("nan"), float("nan"))
            else:
                midpoint = tuple(
                    (float(verts[left][axis]) + float(verts[right][axis])) * 0.5
                    for axis in range(3)
                )
                centroid = _face_centroid(wok, face_index)
                if centroid is None:
                    inward = (float("nan"), float("nan"))
                else:
                    # Stay strictly inside the source triangle while retaining
                    # exact provenance from the transition boundary edge.
                    inward = (
                        float(midpoint[0]) + (float(centroid[0]) - float(midpoint[0])) * 0.20,
                        float(midpoint[1]) + (float(centroid[1]) - float(midpoint[1])) * 0.20,
                    )
            rows.append(
                _TransitionEdge(
                    source_room=room_index,
                    target_room=target_room,
                    face_index=face_index,
                    local_edge=local_edge,
                    midpoint=(float(midpoint[0]), float(midpoint[1]), float(midpoint[2])),
                    inward_point=(float(inward[0]), float(inward[1])),
                    component_index=component_by_face.get(face_index, -1),
                )
            )
    return tuple(rows)


def _transition_distance(left: _TransitionEdge, right: _TransitionEdge) -> float:
    return sqrt(sum((float(left.midpoint[axis]) - float(right.midpoint[axis])) ** 2 for axis in range(3)))


def _shortest_face_path(
    adjacency: dict[int, set[int]],
    start: int,
    target: int,
    allowed: set[int],
) -> tuple[int, ...]:
    if start == target:
        return (start,)
    queue: deque[int] = deque((start,))
    previous: dict[int, int | None] = {start: None}
    while queue:
        current = queue.popleft()
        for neighbor in sorted(adjacency.get(current, ())):
            if neighbor not in allowed or neighbor in previous:
                continue
            previous[neighbor] = current
            if neighbor == target:
                path = [target]
                cursor = current
                while cursor is not None:
                    path.append(cursor)
                    cursor = previous[cursor]
                return tuple(reversed(path))
            queue.append(neighbor)
    return ()


def _shared_edge_midpoint(wok: Any, left_face: int, right_face: int) -> Vec2 | None:
    faces = list(getattr(wok, "faces", ()) or ())
    verts = list(getattr(wok, "verts", ()) or ())
    if left_face < 0 or right_face < 0 or left_face >= len(faces) or right_face >= len(faces):
        return None
    shared = sorted(set(_face_indices(faces[left_face])) & set(_face_indices(faces[right_face])))
    if len(shared) != 2 or any(index < 0 or index >= len(verts) for index in shared):
        return None
    return (
        (float(verts[shared[0]][0]) + float(verts[shared[1]][0])) * 0.5,
        (float(verts[shared[0]][1]) + float(verts[shared[1]][1])) * 0.5,
    )


def _component_center_face(wok: Any, component: tuple[int, ...]) -> int | None:
    centers = [(face_index, _face_centroid(wok, face_index)) for face_index in component]
    valid = [(face_index, center) for face_index, center in centers if center is not None]
    if not valid:
        return None
    average_x = sum(center[0] for _face, center in valid) / len(valid)
    average_y = sum(center[1] for _face, center in valid) / len(valid)
    return min(
        valid,
        key=lambda row: (row[1][0] - average_x) ** 2 + (row[1][1] - average_y) ** 2,
    )[0]


def _simplify_room_route(
    wok: Any,
    points: list[Vec2],
    *,
    grid: _WalkmeshFaceGrid,
) -> tuple[Vec2, ...]:
    """Line-of-sight compact a face-adjacent route without leaving the room."""

    if len(points) <= 2:
        return tuple(points)
    result = [points[0]]
    cursor = 0
    while cursor < len(points) - 1:
        furthest = cursor + 1
        source = AuthoredPathPoint(label="route_source", x=points[cursor][0], y=points[cursor][1])
        for candidate in range(len(points) - 1, cursor, -1):
            target = AuthoredPathPoint(label="route_target", x=points[candidate][0], y=points[candidate][1])
            ok, _failed = _connection_on_walkmesh(wok, source, target, sample_interval=0.25, grid=grid)
            if ok:
                furthest = candidate
                break
        result.append(points[furthest])
        cursor = furthest
    return tuple(result)


def build_authored_path_graph_from_walkmesh(
    wok: Any,
    *,
    anchors: tuple[AuthoredPathAnchor, ...] = (),
) -> AuthoredPathGraph:
    """Build a compact initial path graph from a WOK and gameplay anchors."""

    min_x, min_y, max_x, max_y = _walkmesh_bounds(wok)
    grid = _WalkmeshFaceGrid(wok)
    points: list[AuthoredPathPoint] = []
    seen: set[tuple[int, int]] = set()
    components = _walkable_components(wok)
    component_by_face = {
        face_index: component_index
        for component_index, component in enumerate(components)
        for face_index in component
    }
    for component_index, component in enumerate(components):
        centers = [_face_centroid(wok, face_index) for face_index in component]
        valid_centers = [center for center in centers if center is not None]
        if not valid_centers:
            continue
        avg = (
            sum(item[0] for item in valid_centers) / len(valid_centers),
            sum(item[1] for item in valid_centers) / len(valid_centers),
        )
        # The mean of face centroids can land in a concavity OUTSIDE the
        # walkable region (curved canyons, L-shaped rooms), which then fails
        # the "path point is outside the walkmesh" check. Snap to the real
        # face centroid nearest the mean -- guaranteed to be on a walkable face.
        center = min(valid_centers, key=lambda c: (c[0] - avg[0]) ** 2 + (c[1] - avg[1]) ** 2)
        key = _xy_key(center[0], center[1])
        if key in seen:
            continue
        points.append(
            AuthoredPathPoint(
                label="walkmesh_center" if component_index == 0 else f"walkmesh_center_{component_index + 1}",
                x=center[0],
                y=center[1],
                metadata={"source": "walkmesh_component", "component_index": component_index, "face_count": len(component)},
            )
        )
        seen.add(key)
    if not points:
        center = ((min_x + max_x) * 0.5, (min_y + max_y) * 0.5)
        points.append(
            AuthoredPathPoint(
                label="walkmesh_center",
                x=center[0],
                y=center[1],
                metadata={"source": "walkmesh_bounds"},
            )
        )
        seen.add(_xy_key(center[0], center[1]))
    anchor_labels: list[str] = []
    for anchor in anchors:
        x = float(anchor.position[0])
        y = float(anchor.position[1])
        key = _xy_key(x, y)
        anchor_labels.append(anchor.label)
        if key in seen:
            continue
        ok, face_index = _point_on_walkmesh(wok, x, y, grid=grid)
        points.append(
            AuthoredPathPoint(
                label=anchor.label,
                x=x,
                y=y,
                metadata={
                    "source": "gameplay_anchor",
                    "anchor_label": anchor.label,
                    "walkmesh_face": face_index,
                    "on_walkmesh": ok,
                    **dict(anchor.metadata),
                    "component_index": component_by_face.get(face_index, -1),
                },
            )
        )
        seen.add(key)

    connections: list[AuthoredPathConnection] = []
    for source in range(len(points)):
        for target in range(len(points)):
            if source != target:
                source_component = int(points[source].metadata.get("component_index", -1))
                target_component = int(points[target].metadata.get("component_index", -1))
                if source_component >= 0 and target_component >= 0 and source_component != target_component:
                    continue
                ok, _failed = _connection_on_walkmesh(wok, points[source], points[target], sample_interval=0.5, grid=grid)
                if ok:
                    connections.append(AuthoredPathConnection(source=source, target=target))
    return AuthoredPathGraph(
        points=tuple(points),
        connections=tuple(connections),
        metadata={
            "source": "src.core.modules.authored_module_pathing",
            "generated_from": "walkmesh_and_gameplay_anchors",
            "walkmesh_bounds": [min_x, min_y, max_x, max_y],
            "walkmesh_component_count": len(components),
            "anchor_labels": anchor_labels,
        },
    )


def build_authored_path_graph_from_rooms(
    rooms: tuple[AuthoredPathingRoom, ...],
    *,
    anchors: tuple[AuthoredPathAnchor, ...] = (),
    transition_match_tolerance: float = 0.01,
) -> AuthoredPathGraph:
    """Build a module PTH graph from LYT-ordered room WOKs and transitions.

    Room-local routes follow exact raw-index face adjacency.  Cross-room links
    are created only for reciprocal transition destinations whose actual
    directed boundary-edge midpoints match in module coordinates.  A one-way
    transition is therefore preserved as one-way metadata, never guessed into
    a traversable seam, and a room with no valid seam stays disconnected.
    """

    if not isfinite(float(transition_match_tolerance)) or float(transition_match_tolerance) <= 0.0:
        raise ValueError("Transition edge match tolerance must be positive.")

    translated = tuple(_translated_walkmesh(room) for room in rooms)
    topologies = tuple(_walkable_topology(wok) for wok in translated)
    grids = tuple(_WalkmeshFaceGrid(wok) for wok in translated)
    transition_rows: list[_TransitionEdge] = []
    transition_issues: list[str] = []
    for room_index, (room, wok, topology) in enumerate(zip(rooms, translated, topologies)):
        _components, _adjacency, component_by_face = topology
        for edge in _transition_edges_for_room(room_index, wok, component_by_face):
            if edge.target_room >= len(rooms):
                transition_issues.append(
                    f"Room {room_index} ({room.room_resref}) transition face {edge.face_index} edge "
                    f"{edge.local_edge} targets missing LYT room index {edge.target_room}."
                )
                continue
            if edge.target_room == room_index:
                transition_issues.append(
                    f"Room {room_index} ({room.room_resref}) transition face {edge.face_index} edge "
                    f"{edge.local_edge} targets its own LYT room index."
                )
                continue
            if edge.component_index < 0:
                transition_issues.append(
                    f"Room {room_index} ({room.room_resref}) transition face {edge.face_index} is not walkable."
                )
                continue
            if not all(isfinite(value) for value in (*edge.midpoint, *edge.inward_point)):
                transition_issues.append(
                    f"Room {room_index} ({room.room_resref}) transition face {edge.face_index} edge "
                    f"{edge.local_edge} has invalid geometry."
                )
                continue
            transition_rows.append(edge)

    directed: dict[tuple[int, int], list[_TransitionEdge]] = {}
    for edge in transition_rows:
        directed.setdefault((edge.source_room, edge.target_room), []).append(edge)

    reciprocal_pairs: list[dict[str, Any]] = []
    matched_portals: list[tuple[_TransitionEdge, _TransitionEdge, float, int]] = []
    reciprocal_room_pairs = sorted(
        {
            tuple(sorted((source, target)))
            for source, target in directed
            if source < target and (target, source) in directed
        }
    )
    for left_room, right_room in reciprocal_room_pairs:
        left_edges = directed[(left_room, right_room)]
        right_edges = directed[(right_room, left_room)]
        candidates = sorted(
            (
                (_transition_distance(left, right), left_index, right_index)
                for left_index, left in enumerate(left_edges)
                for right_index, right in enumerate(right_edges)
            ),
            key=lambda row: (row[0], row[1], row[2]),
        )
        used_left: set[int] = set()
        used_right: set[int] = set()
        pair_portal_ids: list[int] = []
        closest_gap = candidates[0][0] if candidates else float("inf")
        for distance, left_index, right_index in candidates:
            if distance > float(transition_match_tolerance):
                break
            if left_index in used_left or right_index in used_right:
                continue
            used_left.add(left_index)
            used_right.add(right_index)
            portal_id = len(matched_portals)
            matched_portals.append((left_edges[left_index], right_edges[right_index], distance, portal_id))
            pair_portal_ids.append(portal_id)
        if not pair_portal_ids:
            transition_issues.append(
                f"Reciprocal transition rooms {left_room} ({rooms[left_room].room_resref}) and "
                f"{right_room} ({rooms[right_room].room_resref}) have no boundary-edge midpoint match "
                f"within {float(transition_match_tolerance):.3f} m (closest {closest_gap:.6f} m)."
            )
        reciprocal_pairs.append(
            {
                "room_a": left_room,
                "room_a_resref": rooms[left_room].room_resref,
                "room_b": right_room,
                "room_b_resref": rooms[right_room].room_resref,
                "room_a_transition_edge_count": len(left_edges),
                "room_b_transition_edge_count": len(right_edges),
                "closest_midpoint_gap": closest_gap,
                "portal_ids": pair_portal_ids,
                "generated_portal_link_count": len(pair_portal_ids),
            }
        )

    reciprocal_orders = {
        (left, right)
        for left, right in reciprocal_room_pairs
    } | {
        (right, left)
        for left, right in reciprocal_room_pairs
    }
    one_way_rows = [
        edge
        for edge in transition_rows
        if (edge.source_room, edge.target_room) not in reciprocal_orders
    ]

    terminals_by_room: dict[int, list[dict[str, Any]]] = {index: [] for index in range(len(rooms))}
    for left, right, distance, portal_id in matched_portals:
        terminals_by_room[left.source_room].append(
            {"kind": "portal", "edge": left, "portal_id": portal_id, "side": "a", "distance": distance}
        )
        terminals_by_room[right.source_room].append(
            {"kind": "portal", "edge": right, "portal_id": portal_id, "side": "b", "distance": distance}
        )

    anchor_labels: list[str] = []
    for anchor in anchors:
        anchor_labels.append(anchor.label)
        assigned = False
        for room_index, (wok, grid, topology) in enumerate(zip(translated, grids, topologies)):
            ok, face_index = _point_on_walkmesh(
                wok,
                float(anchor.position[0]),
                float(anchor.position[1]),
                grid=grid,
            )
            if not ok:
                continue
            component_index = topology[2].get(face_index, -1)
            terminals_by_room[room_index].append(
                {
                    "kind": "anchor",
                    "anchor": anchor,
                    "face_index": face_index,
                    "component_index": component_index,
                }
            )
            assigned = True
            break
        if not assigned:
            transition_issues.append(f"Gameplay anchor {anchor.label!r} is outside every retained room walkmesh.")

    points: list[AuthoredPathPoint] = []
    edges: set[tuple[int, int]] = set()
    point_lookup: dict[tuple[int, int, int, int], int] = {}
    portal_point_indices: dict[tuple[int, str], int] = {}

    def add_point(
        room_index: int,
        component_index: int,
        label: str,
        xy: Vec2,
        metadata: dict[str, Any],
    ) -> int:
        key = (
            room_index,
            component_index,
            round(float(xy[0]) * 1_000_000),
            round(float(xy[1]) * 1_000_000),
        )
        if key in point_lookup:
            index = point_lookup[key]
            existing = points[index]
            if metadata.get("source") in {"reciprocal_transition_edge", "gameplay_anchor"}:
                points[index] = AuthoredPathPoint(
                    label=label,
                    x=existing.x,
                    y=existing.y,
                    metadata={**dict(existing.metadata), **metadata},
                )
            return index
        index = len(points)
        point_lookup[key] = index
        points.append(
            AuthoredPathPoint(
                label=label,
                x=float(xy[0]),
                y=float(xy[1]),
                metadata={
                    "room_index": room_index,
                    "room_resref": rooms[room_index].room_resref,
                    "component_index": component_index,
                    **metadata,
                },
            )
        )
        return index

    def connect_bidirectional(left: int, right: int) -> None:
        if left == right:
            return
        edges.add((left, right))
        edges.add((right, left))

    for room_index, (room, wok, grid, topology) in enumerate(zip(rooms, translated, grids, topologies)):
        components, adjacency, _component_by_face = topology
        room_terminals = terminals_by_room.get(room_index, ())
        for component_index, component in enumerate(components):
            center_face = _component_center_face(wok, component)
            if center_face is None:
                continue
            center_xy = _face_centroid(wok, center_face)
            if center_xy is None:
                continue
            center_index = add_point(
                room_index,
                component_index,
                f"{room.room_resref}_center_{component_index + 1}",
                center_xy,
                {
                    "source": "walkmesh_component",
                    "center_face": center_face,
                    "face_count": len(component),
                },
            )
            for terminal in room_terminals:
                if terminal["kind"] == "portal":
                    transition = terminal["edge"]
                    terminal_face = transition.face_index
                    terminal_component = transition.component_index
                    terminal_xy = transition.inward_point
                    terminal_metadata = {
                        "source": "reciprocal_transition_edge",
                        "portal_id": int(terminal["portal_id"]),
                        "portal_side": terminal["side"],
                        "transition_face": terminal_face,
                        "transition_local_edge": transition.local_edge,
                        "target_room_index": transition.target_room,
                        "target_room_resref": rooms[transition.target_room].room_resref,
                        "transition_edge_midpoint": list(transition.midpoint),
                    }
                    terminal_label = (
                        f"{room.room_resref}_to_{rooms[transition.target_room].room_resref}_portal_"
                        f"{int(terminal['portal_id']) + 1}"
                    )
                else:
                    anchor = terminal["anchor"]
                    terminal_face = int(terminal["face_index"])
                    terminal_component = int(terminal["component_index"])
                    terminal_xy = (float(anchor.position[0]), float(anchor.position[1]))
                    terminal_metadata = {
                        "source": "gameplay_anchor",
                        "anchor_label": anchor.label,
                        "walkmesh_face": terminal_face,
                        **dict(anchor.metadata),
                    }
                    terminal_label = anchor.label
                if terminal_component != component_index:
                    continue
                face_path = _shortest_face_path(adjacency, center_face, terminal_face, set(component))
                if not face_path:
                    transition_issues.append(
                        f"Room {room_index} ({room.room_resref}) has no indexed-face route from component "
                        f"center {center_face} to terminal face {terminal_face}."
                    )
                    continue
                route: list[Vec2] = [center_xy]
                for path_index, face_index in enumerate(face_path[1:], start=1):
                    # Adjacent triangle centroids do not necessarily see one
                    # another through their finite shared edge when the union
                    # is sharply concave.  Route through the exact indexed-edge
                    # midpoint first; each half-segment then lies inside one
                    # of the two walkable triangles and the simplifier may
                    # still remove it when a direct line is valid.
                    shared_midpoint = _shared_edge_midpoint(
                        wok,
                        face_path[path_index - 1],
                        face_index,
                    )
                    if shared_midpoint is None:
                        transition_issues.append(
                            f"Room {room_index} ({room.room_resref}) face route "
                            f"{face_path[path_index - 1]}->{face_index} lacks an exact shared indexed edge."
                        )
                        continue
                    route.append(shared_midpoint)
                    centroid = _face_centroid(wok, face_index)
                    if centroid is not None:
                        route.append(centroid)
                if not route or hypot(route[-1][0] - terminal_xy[0], route[-1][1] - terminal_xy[1]) > 1.0e-7:
                    route.append(terminal_xy)
                compact_route = _simplify_room_route(wok, route, grid=grid)
                previous_index = center_index
                for route_index, xy in enumerate(compact_route[1:], start=1):
                    is_terminal = route_index == len(compact_route) - 1
                    point_index = add_point(
                        room_index,
                        component_index,
                        terminal_label if is_terminal else f"{room.room_resref}_route_{terminal_face}_{route_index}",
                        xy,
                        terminal_metadata if is_terminal else {"source": "walkmesh_face_route"},
                    )
                    connect_bidirectional(previous_index, point_index)
                    previous_index = point_index
                if terminal["kind"] == "portal":
                    portal_point_indices[(int(terminal["portal_id"]), str(terminal["side"]))] = previous_index

    portal_links: list[dict[str, Any]] = []
    for left, right, distance, portal_id in matched_portals:
        left_index = portal_point_indices.get((portal_id, "a"))
        right_index = portal_point_indices.get((portal_id, "b"))
        generated = left_index is not None and right_index is not None and left_index != right_index
        if generated:
            connect_bidirectional(left_index, right_index)
        else:
            transition_issues.append(
                f"Reciprocal transition portal {portal_id} between rooms {left.source_room} and "
                f"{right.source_room} did not produce two PTH endpoints."
            )
        portal_links.append(
            {
                "portal_id": portal_id,
                "room_a": left.source_room,
                "room_a_resref": rooms[left.source_room].room_resref,
                "room_a_face": left.face_index,
                "room_a_local_edge": left.local_edge,
                "room_a_midpoint": list(left.midpoint),
                "room_a_point": left_index,
                "room_b": right.source_room,
                "room_b_resref": rooms[right.source_room].room_resref,
                "room_b_face": right.face_index,
                "room_b_local_edge": right.local_edge,
                "room_b_midpoint": list(right.midpoint),
                "room_b_point": right_index,
                "midpoint_gap": distance,
                "bidirectional_bridge": bool(
                    generated
                    and (left_index, right_index) in edges
                    and (right_index, left_index) in edges
                ),
            }
        )

    for pair in reciprocal_pairs:
        pair["bidirectional_bridge_count"] = sum(
            1
            for portal_id in pair["portal_ids"]
            if portal_id < len(portal_links) and portal_links[portal_id]["bidirectional_bridge"]
        )
        if pair["bidirectional_bridge_count"] < 1:
            transition_issues.append(
                f"Reciprocal transition rooms {pair['room_a']} ({pair['room_a_resref']}) and "
                f"{pair['room_b']} ({pair['room_b_resref']}) lack a bidirectional PTH bridge."
            )

    weak_adjacency: dict[int, set[int]] = {index: set() for index in range(len(points))}
    for source, target in edges:
        weak_adjacency[source].add(target)
        weak_adjacency[target].add(source)
    remaining = set(weak_adjacency)
    graph_component_count = 0
    while remaining:
        graph_component_count += 1
        stack = [remaining.pop()]
        while stack:
            current = stack.pop()
            for neighbor in weak_adjacency[current]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)

    all_components = sum(len(topology[0]) for topology in topologies)
    all_bounds = [_walkmesh_bounds(wok) for wok in translated if getattr(wok, "verts", ())]
    if all_bounds:
        module_bounds = [
            min(row[0] for row in all_bounds),
            min(row[1] for row in all_bounds),
            max(row[2] for row in all_bounds),
            max(row[3] for row in all_bounds),
        ]
    else:
        module_bounds = [0.0, 0.0, 0.0, 0.0]
    return AuthoredPathGraph(
        points=tuple(points),
        connections=tuple(AuthoredPathConnection(source, target) for source, target in sorted(edges)),
        metadata={
            "source": "src.core.modules.authored_module_pathing",
            "generated_from": "lyt_ordered_room_walkmeshes_and_reciprocal_transitions",
            "room_resrefs": [room.room_resref for room in rooms],
            "room_count": len(rooms),
            "walkmesh_bounds": module_bounds,
            "walkmesh_component_count": all_components,
            "path_graph_component_count": graph_component_count,
            "anchor_labels": anchor_labels,
            "transition_match_tolerance": float(transition_match_tolerance),
            "transition_record_count": len(transition_rows),
            "one_way_transition_count": len(one_way_rows),
            "one_way_transitions": [
                {
                    "source_room": edge.source_room,
                    "source_room_resref": rooms[edge.source_room].room_resref,
                    "target_room": edge.target_room,
                    "target_room_resref": rooms[edge.target_room].room_resref,
                    "face": edge.face_index,
                    "local_edge": edge.local_edge,
                }
                for edge in one_way_rows
            ],
            "reciprocal_transition_pairs": reciprocal_pairs,
            "reciprocal_transition_pair_count": len(reciprocal_pairs),
            "portal_links": portal_links,
            "generated_portal_link_count": sum(1 for row in portal_links if row["bidirectional_bridge"]),
            "transition_issues": transition_issues,
        },
    )


def validate_authored_path_graph(
    graph: AuthoredPathGraph,
    *,
    wok: Any | None = None,
    connection_sample_interval: float = 0.5,
) -> AuthoredPathingValidation:
    """Validate authored path graph indices and walkmesh placement."""

    warnings: list[str] = []
    blocking: list[str] = []
    grid = _WalkmeshFaceGrid(wok) if wok is not None else None
    if not isfinite(float(connection_sample_interval)) or float(connection_sample_interval) <= 0.0:
        blocking.append("Path connection sample interval must be positive.")
    if not graph.points:
        blocking.append("Authored path graph requires at least one path point.")
    for index, point in enumerate(graph.points):
        if not point.label:
            warnings.append(f"Path point {index} has no label.")
        if not (isfinite(float(point.x)) and isfinite(float(point.y))):
            blocking.append(f"Path point {index} has non-finite coordinates.")
        if wok is not None:
            ok, _face_index = _point_on_walkmesh(wok, float(point.x), float(point.y), grid=grid)
            if not ok:
                blocking.append(f"Path point {index} ({point.label}) is outside the generated walkmesh.")
    seen_edges: set[tuple[int, int]] = set()
    for edge in graph.connections:
        edge_indices_ok = True
        if edge.source < 0 or edge.source >= len(graph.points):
            blocking.append(f"Path connection has invalid source index {edge.source}.")
            edge_indices_ok = False
        if edge.target < 0 or edge.target >= len(graph.points):
            blocking.append(f"Path connection has invalid target index {edge.target}.")
            edge_indices_ok = False
        if edge.source == edge.target:
            blocking.append(f"Path connection {edge.source}->{edge.target} loops to itself.")
            edge_indices_ok = False
        key = (edge.source, edge.target)
        if key in seen_edges:
            blocking.append(f"Duplicate path connection {edge.source}->{edge.target}.")
        seen_edges.add(key)
        if wok is not None and edge_indices_ok and isfinite(float(connection_sample_interval)) and float(connection_sample_interval) > 0.0:
            ok, failed_sample = _connection_on_walkmesh(
                wok,
                graph.points[edge.source],
                graph.points[edge.target],
                sample_interval=float(connection_sample_interval),
                grid=grid,
            )
            if not ok and failed_sample is not None:
                x, y, step = failed_sample
                blocking.append(
                    f"Path connection {edge.source}->{edge.target} leaves the generated walkmesh near sample {step} "
                    f"({x:.3f}, {y:.3f})."
                )
    if len(graph.points) > 1 and not graph.connections:
        component_count = int(graph.metadata.get("walkmesh_component_count", 0) or 0)
        if component_count > 1:
            warnings.append(
                f"Authored path graph has {component_count} disconnected walkmesh island(s); "
                "Map Studio will not create PTH links through non-walkable gaps."
            )
        else:
            blocking.append("Authored path graph with multiple points requires path connections.")
    return AuthoredPathingValidation(
        ok=not blocking,
        warnings=tuple(warnings),
        blocking_issues=tuple(blocking),
    )


def validate_authored_room_path_graph(
    graph: AuthoredPathGraph,
    rooms: tuple[AuthoredPathingRoom, ...],
    *,
    connection_sample_interval: float = 0.25,
) -> AuthoredPathingValidation:
    """Validate room-local routes and reciprocal portal bridges independently."""

    base = validate_authored_path_graph(
        graph,
        wok=None,
        connection_sample_interval=connection_sample_interval,
    )
    warnings = list(base.warnings)
    blocking = list(base.blocking_issues)
    blocking.extend(str(issue) for issue in graph.metadata.get("transition_issues", ()))
    translated = tuple(_translated_walkmesh(room) for room in rooms)
    grids = tuple(_WalkmeshFaceGrid(wok) for wok in translated)
    for point_index, point in enumerate(graph.points):
        room_index = int(point.metadata.get("room_index", -1))
        if room_index < 0 or room_index >= len(rooms):
            blocking.append(f"Path point {point_index} ({point.label}) has invalid room index {room_index}.")
            continue
        ok, _face_index = _point_on_walkmesh(
            translated[room_index],
            float(point.x),
            float(point.y),
            grid=grids[room_index],
        )
        if not ok:
            blocking.append(
                f"Path point {point_index} ({point.label}) is outside room {room_index} "
                f"({rooms[room_index].room_resref}) walkmesh."
            )

    portal_directed_edges: set[tuple[int, int]] = set()
    for portal in graph.metadata.get("portal_links", ()):
        left = portal.get("room_a_point")
        right = portal.get("room_b_point")
        if isinstance(left, int) and isinstance(right, int):
            portal_directed_edges.add((left, right))
            portal_directed_edges.add((right, left))
        if not bool(portal.get("bidirectional_bridge", False)):
            blocking.append(
                f"Portal {portal.get('portal_id', '?')} between rooms {portal.get('room_a', '?')} and "
                f"{portal.get('room_b', '?')} lacks a bidirectional PTH bridge."
            )

    for connection in graph.connections:
        if not (0 <= connection.source < len(graph.points) and 0 <= connection.target < len(graph.points)):
            continue
        source = graph.points[connection.source]
        target = graph.points[connection.target]
        source_room = int(source.metadata.get("room_index", -1))
        target_room = int(target.metadata.get("room_index", -1))
        if source_room != target_room:
            if (connection.source, connection.target) not in portal_directed_edges:
                blocking.append(
                    f"Cross-room path connection {connection.source}->{connection.target} is not an exact "
                    "reciprocal transition portal bridge."
                )
            continue
        if source_room < 0 or source_room >= len(rooms):
            continue
        ok, failed_sample = _connection_on_walkmesh(
            translated[source_room],
            source,
            target,
            sample_interval=float(connection_sample_interval),
            grid=grids[source_room],
        )
        if not ok and failed_sample is not None:
            x, y, step = failed_sample
            blocking.append(
                f"Room-local path connection {connection.source}->{connection.target} leaves room "
                f"{source_room} ({rooms[source_room].room_resref}) near sample {step} ({x:.3f}, {y:.3f})."
            )

    graph_edges = {(edge.source, edge.target) for edge in graph.connections}
    for pair in graph.metadata.get("reciprocal_transition_pairs", ()):
        portal_ids = set(int(value) for value in pair.get("portal_ids", ()))
        pair_portals = [
            portal
            for portal in graph.metadata.get("portal_links", ())
            if int(portal.get("portal_id", -1)) in portal_ids
        ]
        valid = any(
            isinstance(portal.get("room_a_point"), int)
            and isinstance(portal.get("room_b_point"), int)
            and (portal["room_a_point"], portal["room_b_point"]) in graph_edges
            and (portal["room_b_point"], portal["room_a_point"]) in graph_edges
            for portal in pair_portals
        )
        if not valid:
            blocking.append(
                f"Reciprocal transition rooms {pair.get('room_a', '?')} ({pair.get('room_a_resref', '?')}) "
                f"and {pair.get('room_b', '?')} ({pair.get('room_b_resref', '?')}) have no bidirectional "
                "PTH bridge."
            )
    one_way_count = int(graph.metadata.get("one_way_transition_count", 0) or 0)
    if one_way_count:
        warnings.append(
            f"Preserved {one_way_count} one-way WOK transition record(s) without inventing PTH bridges."
        )
    graph_components = int(graph.metadata.get("path_graph_component_count", 0) or 0)
    if graph_components > 1:
        warnings.append(
            f"Authored path graph preserves {graph_components} disconnected walkable network(s)."
        )
    # Keep diagnostics deterministic and avoid duplicated compound failures.
    warnings = list(dict.fromkeys(warnings))
    blocking = list(dict.fromkeys(blocking))
    return AuthoredPathingValidation(
        ok=not blocking,
        warnings=tuple(warnings),
        blocking_issues=tuple(blocking),
    )


def build_authored_pth_bytes(graph: AuthoredPathGraph) -> bytes:
    """Serialize authored path graph to a KOTOR PTH GFF byte stream."""

    from pykotor.resource.generics.pth import PTH, bytes_pth

    pth = PTH()
    for point in graph.points:
        pth.add(float(point.x), float(point.y))
    for edge in graph.connections:
        pth.connect(int(edge.source), int(edge.target))
    return bytes_pth(pth)


def compile_authored_pathing_for_module(
    wok: Any,
    *,
    anchors: tuple[AuthoredPathAnchor, ...] = (),
) -> CompiledAuthoredPathing:
    """Compile walkmesh/gameplay anchors into a serialized module PTH."""

    graph = build_authored_path_graph_from_walkmesh(wok, anchors=anchors)
    validation = validate_authored_path_graph(graph, wok=wok)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    return CompiledAuthoredPathing(
        pth_bytes=build_authored_pth_bytes(graph),
        graph=graph,
        validation=validation,
        metadata={
            "source": "src.core.modules.authored_module_pathing",
            "point_count": len(graph.points),
            "connection_count": len(graph.connections),
            "anchor_labels": list(graph.metadata.get("anchor_labels", [])),
            "walkmesh_bounds": list(graph.metadata.get("walkmesh_bounds", [])),
            "walkmesh_component_count": int(graph.metadata.get("walkmesh_component_count", 0) or 0),
        },
    )


def compile_authored_pathing_for_rooms(
    rooms: tuple[AuthoredPathingRoom, ...],
    *,
    anchors: tuple[AuthoredPathAnchor, ...] = (),
    transition_match_tolerance: float = 0.01,
) -> CompiledAuthoredPathing:
    """Compile an LYT-ordered, transition-aware room set to module PTH."""

    graph = build_authored_path_graph_from_rooms(
        rooms,
        anchors=anchors,
        transition_match_tolerance=transition_match_tolerance,
    )
    validation = validate_authored_room_path_graph(graph, rooms)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    return CompiledAuthoredPathing(
        pth_bytes=build_authored_pth_bytes(graph),
        graph=graph,
        validation=validation,
        metadata={
            "source": "src.core.modules.authored_module_pathing",
            "point_count": len(graph.points),
            "connection_count": len(graph.connections),
            "anchor_labels": list(graph.metadata.get("anchor_labels", [])),
            "walkmesh_bounds": list(graph.metadata.get("walkmesh_bounds", [])),
            "walkmesh_component_count": int(graph.metadata.get("walkmesh_component_count", 0) or 0),
            "path_graph_component_count": int(graph.metadata.get("path_graph_component_count", 0) or 0),
            "reciprocal_transition_pair_count": int(
                graph.metadata.get("reciprocal_transition_pair_count", 0) or 0
            ),
            "generated_portal_link_count": int(graph.metadata.get("generated_portal_link_count", 0) or 0),
            "reciprocal_transition_pairs": list(graph.metadata.get("reciprocal_transition_pairs", [])),
            "portal_links": list(graph.metadata.get("portal_links", [])),
            "one_way_transition_count": int(graph.metadata.get("one_way_transition_count", 0) or 0),
        },
    )


__all__ = [
    "AuthoredPathAnchor",
    "AuthoredPathConnection",
    "AuthoredPathGraph",
    "AuthoredPathPoint",
    "AuthoredPathingRoom",
    "AuthoredPathingValidation",
    "CompiledAuthoredPathing",
    "build_authored_path_graph_from_walkmesh",
    "build_authored_path_graph_from_rooms",
    "build_authored_pth_bytes",
    "compile_authored_pathing_for_module",
    "compile_authored_pathing_for_rooms",
    "validate_authored_path_graph",
    "validate_authored_room_path_graph",
]
