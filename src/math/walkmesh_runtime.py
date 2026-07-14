"""Deterministic, renderer-independent walkmesh and segment-collision math.

This module deliberately consumes duck-typed vertex/face sequences.  It owns
the spatial and movement math used by Map Studio's simulation without knowing
about Qt, KMAP projects, or renderer objects.

The surface tables are verified against the retail K1/K2 ``surfacemat.2da``
resources.  ``walk``, ``walkcheck``, and ``lineofsight`` are separate Odyssey
contracts and must not be collapsed into one generic "walkable" flag.
"""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
from typing import Any, Iterable, Sequence


Vec3 = tuple[float, float, float]

K1_WALKABLE_SURFACE_IDS = frozenset({1, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 18, 30})
K2_WALKABLE_SURFACE_IDS = frozenset((*K1_WALKABLE_SURFACE_IDS, 16))
KOTOR_WALKCHECK_SURFACE_IDS = frozenset({1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 30})
KOTOR_LINE_OF_SIGHT_SURFACE_IDS = frozenset({1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19})


def kotor_walkable_surface_ids(game: object) -> frozenset[int]:
    """Return the retail game's ``surfacemat.2da`` ``walk`` rows."""

    return K2_WALKABLE_SURFACE_IDS if str(game or "K1").strip().upper() == "K2" else K1_WALKABLE_SURFACE_IDS


@dataclass(frozen=True)
class WalkmeshSample:
    """One XY point projected onto a specific walkable WOK triangle."""

    position: Vec3
    face_index: int
    surface_id: int


@dataclass(frozen=True)
class WalkmeshMoveResult:
    """Result of one swept-disc move constrained to walkable triangles."""

    position: Vec3
    face_index: int
    moved: bool
    blocked: bool


@dataclass(frozen=True)
class CollisionTriangle:
    """One immutable world-space triangle used by segment collision."""

    a: Vec3
    b: Vec3
    c: Vec3
    source: str = ""


def _length_xy(x: float, y: float) -> float:
    return math.sqrt((x * x) + (y * y))


def _distance_sq(a: Vec3, b: Vec3) -> float:
    return sum((float(a[index]) - float(b[index])) ** 2 for index in range(3))


def _barycentric_xy(x: float, y: float, a: Vec3, b: Vec3, c: Vec3) -> tuple[float, float, float] | None:
    denominator = ((b[1] - c[1]) * (a[0] - c[0])) + ((c[0] - b[0]) * (a[1] - c[1]))
    if abs(denominator) <= 1.0e-12:
        return None
    wa = (((b[1] - c[1]) * (x - c[0])) + ((c[0] - b[0]) * (y - c[1]))) / denominator
    wb = (((c[1] - a[1]) * (x - c[0])) + ((a[0] - c[0]) * (y - c[1]))) / denominator
    wc = 1.0 - wa - wb
    if min(wa, wb, wc) < -1.0e-7:
        return None
    return (wa, wb, wc)


def _face_vertices(vertices: Sequence[Any], face: Any) -> tuple[Vec3, Vec3, Vec3] | None:
    try:
        points = tuple(
            tuple(float(value) for value in tuple(vertices[int(index)])[:3])
            for index in (face.v1, face.v2, face.v3)
        )
    except (AttributeError, IndexError, TypeError, ValueError):
        return None
    if any(len(point) < 3 for point in points):
        return None
    return points  # type: ignore[return-value]


def _quantized_vertex(point: Vec3, scale: float = 10_000.0) -> tuple[int, int, int]:
    return tuple(int(round(float(value) * scale)) for value in point)  # type: ignore[return-value]


class WalkmeshRuntimeIndex:
    """Spatial index, adjacency graph, and swept-disc movement for one WOK.

    The index is built once when simulation starts.  Frame updates therefore
    avoid recompiling KMAP data or scanning every WOK face, including on large
    stock modules such as 207TEL.
    """

    def __init__(
        self,
        wok: Any,
        *,
        game: str = "K1",
        player_radius: float = 0.24,
        cell_size: float | None = None,
    ) -> None:
        self.vertices: tuple[Vec3, ...] = tuple(
            tuple(float(value) for value in tuple(vertex)[:3])  # type: ignore[misc]
            for vertex in tuple(getattr(wok, "verts", ()) or ())
        )
        self.faces: tuple[Any, ...] = tuple(getattr(wok, "faces", ()) or ())
        self.game = str(game or "K1").strip().upper()
        self.walkable_surface_ids = kotor_walkable_surface_ids(self.game)
        self.player_radius = max(0.01, float(player_radius))
        self.walkable_faces = tuple(
            index
            for index, face in enumerate(self.faces)
            if int(getattr(face, "surface", -1)) in self.walkable_surface_ids
            and _face_vertices(self.vertices, face) is not None
        )
        self._face_points: dict[int, tuple[Vec3, Vec3, Vec3]] = {
            index: points
            for index in self.walkable_faces
            if (points := _face_vertices(self.vertices, self.faces[index])) is not None
        }
        self._centroids: dict[int, Vec3] = {
            index: tuple(sum(point[axis] for point in points) / 3.0 for axis in range(3))  # type: ignore[misc]
            for index, points in self._face_points.items()
        }
        self._cell_size = self._choose_cell_size(cell_size)
        self._grid: dict[tuple[int, int], list[int]] = {}
        self._large_faces: list[int] = []
        self._build_grid()
        self._adjacency, self._portal_midpoints = self._build_adjacency()

    def _choose_cell_size(self, requested: float | None) -> float:
        if requested is not None:
            return max(0.1, float(requested))
        if not self._face_points:
            return 1.0
        xs = [point[0] for points in self._face_points.values() for point in points]
        ys = [point[1] for points in self._face_points.values() for point in points]
        area = max(0.01, (max(xs) - min(xs)) * (max(ys) - min(ys)))
        typical = math.sqrt(area / max(1, len(self._face_points))) * 1.75
        return max(0.5, min(4.0, typical))

    def _cell(self, x: float, y: float) -> tuple[int, int]:
        return (math.floor(float(x) / self._cell_size), math.floor(float(y) / self._cell_size))

    def _build_grid(self) -> None:
        for face_index, points in self._face_points.items():
            min_cell = self._cell(min(point[0] for point in points), min(point[1] for point in points))
            max_cell = self._cell(max(point[0] for point in points), max(point[1] for point in points))
            cell_count = (max_cell[0] - min_cell[0] + 1) * (max_cell[1] - min_cell[1] + 1)
            if cell_count > 4096:
                self._large_faces.append(face_index)
                continue
            for ix in range(min_cell[0], max_cell[0] + 1):
                for iy in range(min_cell[1], max_cell[1] + 1):
                    self._grid.setdefault((ix, iy), []).append(face_index)

    def _candidate_faces(self, x: float, y: float, preferred_face: int = -1) -> tuple[int, ...]:
        candidates: list[int] = []
        if preferred_face in self._face_points:
            candidates.append(int(preferred_face))
        for face_index in self._grid.get(self._cell(x, y), ()):
            if face_index not in candidates:
                candidates.append(face_index)
        for face_index in self._large_faces:
            if face_index not in candidates:
                candidates.append(face_index)
        return tuple(candidates)

    def sample_at(
        self,
        x: float,
        y: float,
        reference_z: float,
        *,
        preferred_face: int = -1,
        max_step_up: float = math.inf,
        max_step_down: float = math.inf,
    ) -> WalkmeshSample | None:
        """Project XY onto the closest valid floor near ``reference_z``.

        ``preferred_face`` preserves the current layer on stacked walkmeshes.
        Step limits prevent a horizontal move from teleporting between floors.
        """

        best: tuple[tuple[float, int], WalkmeshSample] | None = None
        for face_index in self._candidate_faces(float(x), float(y), int(preferred_face)):
            points = self._face_points.get(face_index)
            if points is None:
                continue
            weights = _barycentric_xy(float(x), float(y), *points)
            if weights is None:
                continue
            z = sum(points[index][2] * weights[index] for index in range(3))
            delta = z - float(reference_z)
            if delta > float(max_step_up) + 1.0e-7 or -delta > float(max_step_down) + 1.0e-7:
                continue
            sample = WalkmeshSample(
                position=(float(x), float(y), float(z)),
                face_index=face_index,
                surface_id=int(getattr(self.faces[face_index], "surface", -1)),
            )
            score = (abs(delta), 0 if face_index == preferred_face else 1)
            if best is None or score < best[0]:
                best = (score, sample)
        return best[1] if best is not None else None

    def validate_disc(
        self,
        position: Vec3,
        *,
        preferred_face: int = -1,
        radius: float | None = None,
        max_step_up: float = 0.45,
        max_step_down: float = 0.75,
    ) -> WalkmeshSample | None:
        """Return the centre floor when the whole player footprint is valid."""

        x, y, z = (float(value) for value in position)
        centre = self.sample_at(
            x,
            y,
            z,
            preferred_face=preferred_face,
            max_step_up=max_step_up,
            max_step_down=max_step_down,
        )
        if centre is None:
            return None
        footprint_radius = self.player_radius if radius is None else max(0.0, float(radius))
        if footprint_radius <= 1.0e-7:
            return centre
        # An eight-point disc is a stable, inexpensive capsule-footprint proxy.
        # Slightly inset samples avoid rejecting exact shared edges due to float
        # representation while keeping a real clearance boundary.
        probe_radius = footprint_radius * 0.98
        for index in range(8):
            angle = (math.tau * index) / 8.0
            probe = self.sample_at(
                centre.position[0] + math.cos(angle) * probe_radius,
                centre.position[1] + math.sin(angle) * probe_radius,
                centre.position[2],
                preferred_face=centre.face_index,
                max_step_up=max_step_up,
                max_step_down=max_step_down,
            )
            if probe is None:
                return None
        return centre

    def move_disc(
        self,
        position: Vec3,
        face_index: int,
        delta_xy: tuple[float, float],
        *,
        radius: float | None = None,
        max_step_up: float = 0.45,
        max_step_down: float = 0.75,
    ) -> WalkmeshMoveResult:
        """Sweep a player disc through the WOK and slide at boundaries."""

        start = tuple(float(value) for value in position[:3])
        dx, dy = float(delta_xy[0]), float(delta_xy[1])
        distance = _length_xy(dx, dy)
        if distance <= 1.0e-10:
            return WalkmeshMoveResult(start, int(face_index), False, False)
        footprint_radius = self.player_radius if radius is None else max(0.01, float(radius))
        max_segment = max(0.025, footprint_radius * 0.45)
        segment_count = max(1, int(math.ceil(distance / max_segment)))
        step_x, step_y = dx / segment_count, dy / segment_count
        current = start
        current_face = int(face_index)
        moved = False
        blocked = False
        for _index in range(segment_count):
            target = (current[0] + step_x, current[1] + step_y, current[2])
            sample = self.validate_disc(
                target,
                preferred_face=current_face,
                radius=footprint_radius,
                max_step_up=max_step_up,
                max_step_down=max_step_down,
            )
            if sample is not None:
                current, current_face, moved = sample.position, sample.face_index, True
                continue
            # Cheap deterministic slide: test both orthogonal components and
            # retain the candidate that advances farther.  Repeated substeps
            # approximate a tangent slide without ever leaving valid WOK.
            slide_candidates: list[WalkmeshSample] = []
            for slide in ((current[0] + step_x, current[1], current[2]), (current[0], current[1] + step_y, current[2])):
                candidate = self.validate_disc(
                    slide,
                    preferred_face=current_face,
                    radius=footprint_radius,
                    max_step_up=max_step_up,
                    max_step_down=max_step_down,
                )
                if candidate is not None:
                    slide_candidates.append(candidate)
            if slide_candidates:
                chosen = max(slide_candidates, key=lambda candidate: _distance_sq(current, candidate.position))
                current, current_face, moved = chosen.position, chosen.face_index, True
                blocked = True
                continue
            blocked = True
            break
        return WalkmeshMoveResult(current, current_face, moved, blocked)

    def _build_adjacency(self) -> tuple[dict[int, set[int]], dict[tuple[int, int], Vec3]]:
        adjacency = {face_index: set() for face_index in self.walkable_faces}
        portals: dict[tuple[int, int], Vec3] = {}
        edge_faces: dict[tuple[tuple[int, int, int], tuple[int, int, int]], list[tuple[int, Vec3]]] = {}
        for face_index, points in self._face_points.items():
            face = self.faces[face_index]
            for adjacent in (
                int(getattr(face, "adj1", -1)),
                int(getattr(face, "adj2", -1)),
                int(getattr(face, "adj3", -1)),
            ):
                if adjacent in adjacency:
                    adjacency[face_index].add(adjacent)
            for start, end in ((points[0], points[1]), (points[1], points[2]), (points[2], points[0])):
                qa, qb = _quantized_vertex(start), _quantized_vertex(end)
                key = (qa, qb) if qa <= qb else (qb, qa)
                midpoint = tuple((start[axis] + end[axis]) * 0.5 for axis in range(3))  # type: ignore[misc]
                edge_faces.setdefault(key, []).append((face_index, midpoint))
        for rows in edge_faces.values():
            if len(rows) < 2:
                continue
            for left_index in range(len(rows)):
                for right_index in range(left_index + 1, len(rows)):
                    left, right = rows[left_index][0], rows[right_index][0]
                    adjacency[left].add(right)
                    adjacency[right].add(left)
                    midpoint = tuple(
                        (rows[left_index][1][axis] + rows[right_index][1][axis]) * 0.5
                        for axis in range(3)
                    )
                    portals[(left, right)] = midpoint  # type: ignore[assignment]
                    portals[(right, left)] = midpoint  # type: ignore[assignment]
        return adjacency, portals

    def route(self, start_face: int, end_face: int, destination: Vec3) -> tuple[Vec3, ...]:
        """A* over directed/geometry-welded walkable face adjacency."""

        start, goal = int(start_face), int(end_face)
        if start not in self._adjacency or goal not in self._adjacency:
            return ()
        if start == goal:
            return (tuple(float(value) for value in destination[:3]),)
        open_rows: list[tuple[float, float, int]] = [(0.0, 0.0, start)]
        parent: dict[int, int] = {}
        cost = {start: 0.0}
        visited: set[int] = set()
        while open_rows:
            _estimated, current_cost, current = heapq.heappop(open_rows)
            if current in visited:
                continue
            visited.add(current)
            if current == goal:
                break
            for neighbour in self._adjacency.get(current, ()):
                new_cost = current_cost + math.sqrt(_distance_sq(self._centroids[current], self._centroids[neighbour]))
                if new_cost + 1.0e-9 >= cost.get(neighbour, math.inf):
                    continue
                cost[neighbour] = new_cost
                parent[neighbour] = current
                heuristic = math.sqrt(_distance_sq(self._centroids[neighbour], self._centroids[goal]))
                heapq.heappush(open_rows, (new_cost + heuristic, new_cost, neighbour))
        if goal not in parent:
            return ()
        faces = [goal]
        while faces[-1] != start:
            faces.append(parent[faces[-1]])
        faces.reverse()
        route: list[Vec3] = []
        for left, right in zip(faces, faces[1:]):
            point = self._portal_midpoints.get((left, right), self._centroids[right])
            if not route or _distance_sq(route[-1], point) > 1.0e-8:
                route.append(point)
        destination_point = tuple(float(value) for value in destination[:3])
        if not route or _distance_sq(route[-1], destination_point) > 1.0e-8:
            route.append(destination_point)  # type: ignore[arg-type]
        return tuple(route)

    def connected(self, start_face: int, end_face: int) -> bool:
        return bool(self.route(start_face, end_face, self._centroids.get(end_face, (0.0, 0.0, 0.0))))


def _triangle_bounds(triangle: CollisionTriangle) -> tuple[Vec3, Vec3]:
    return (
        tuple(min(triangle.a[axis], triangle.b[axis], triangle.c[axis]) for axis in range(3)),  # type: ignore[misc]
        tuple(max(triangle.a[axis], triangle.b[axis], triangle.c[axis]) for axis in range(3)),  # type: ignore[misc]
    )


def _merge_bounds(rows: Iterable[tuple[Vec3, Vec3]]) -> tuple[Vec3, Vec3]:
    bounds = tuple(rows)
    if not bounds:
        return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    return (
        tuple(min(row[0][axis] for row in bounds) for axis in range(3)),  # type: ignore[misc]
        tuple(max(row[1][axis] for row in bounds) for axis in range(3)),  # type: ignore[misc]
    )


@dataclass(frozen=True)
class _CollisionNode:
    bounds: tuple[Vec3, Vec3]
    left: "_CollisionNode | None" = None
    right: "_CollisionNode | None" = None
    indices: tuple[int, ...] = ()


def _segment_aabb(start: Vec3, delta: Vec3, bounds: tuple[Vec3, Vec3], maximum_t: float) -> bool:
    minimum_t = 0.0
    limit = min(1.0, float(maximum_t))
    for axis in range(3):
        origin = start[axis]
        direction = delta[axis]
        low, high = bounds[0][axis], bounds[1][axis]
        if abs(direction) <= 1.0e-12:
            if origin < low or origin > high:
                return False
            continue
        inverse = 1.0 / direction
        first, second = (low - origin) * inverse, (high - origin) * inverse
        if first > second:
            first, second = second, first
        minimum_t = max(minimum_t, first)
        limit = min(limit, second)
        if minimum_t > limit:
            return False
    return True


def _segment_triangle_t(start: Vec3, delta: Vec3, triangle: CollisionTriangle) -> float | None:
    edge1 = tuple(triangle.b[index] - triangle.a[index] for index in range(3))
    edge2 = tuple(triangle.c[index] - triangle.a[index] for index in range(3))
    px = delta[1] * edge2[2] - delta[2] * edge2[1]
    py = delta[2] * edge2[0] - delta[0] * edge2[2]
    pz = delta[0] * edge2[1] - delta[1] * edge2[0]
    determinant = edge1[0] * px + edge1[1] * py + edge1[2] * pz
    if abs(determinant) <= 1.0e-10:
        return None
    inverse = 1.0 / determinant
    tx, ty, tz = (start[index] - triangle.a[index] for index in range(3))
    u = (tx * px + ty * py + tz * pz) * inverse
    if u < -1.0e-8 or u > 1.0 + 1.0e-8:
        return None
    qx = ty * edge1[2] - tz * edge1[1]
    qy = tz * edge1[0] - tx * edge1[2]
    qz = tx * edge1[1] - ty * edge1[0]
    v = (delta[0] * qx + delta[1] * qy + delta[2] * qz) * inverse
    if v < -1.0e-8 or u + v > 1.0 + 1.0e-8:
        return None
    t = (edge2[0] * qx + edge2[1] * qy + edge2[2] * qz) * inverse
    return t if 1.0e-6 < t <= 1.0 + 1.0e-8 else None


class SegmentCollisionIndex:
    """Immutable BVH for nearest two-sided segment/triangle obstruction."""

    def __init__(self, triangles: Sequence[CollisionTriangle] | Iterable[CollisionTriangle]) -> None:
        self.triangles = tuple(triangles or ())
        self._bounds = tuple(_triangle_bounds(triangle) for triangle in self.triangles)
        self._root = self._build(tuple(range(len(self.triangles)))) if self.triangles else None

    def _build(self, indices: tuple[int, ...]) -> _CollisionNode:
        bounds = _merge_bounds(self._bounds[index] for index in indices)
        if len(indices) <= 12:
            return _CollisionNode(bounds=bounds, indices=indices)
        extents = tuple(bounds[1][axis] - bounds[0][axis] for axis in range(3))
        axis = max(range(3), key=lambda value: extents[value])
        ordered = tuple(
            sorted(
                indices,
                key=lambda index: (self._bounds[index][0][axis] + self._bounds[index][1][axis]) * 0.5,
            )
        )
        middle = len(ordered) // 2
        return _CollisionNode(
            bounds=bounds,
            left=self._build(ordered[:middle]),
            right=self._build(ordered[middle:]),
        )

    def nearest_hit_fraction(self, start: Vec3, end: Vec3) -> tuple[float, CollisionTriangle] | None:
        if self._root is None:
            return None
        origin = tuple(float(value) for value in start[:3])
        target = tuple(float(value) for value in end[:3])
        delta = tuple(target[index] - origin[index] for index in range(3))
        if sum(value * value for value in delta) <= 1.0e-16:
            return None
        best_t = 1.0 + 1.0e-8
        best_index = -1
        stack = [self._root]
        while stack:
            node = stack.pop()
            if not _segment_aabb(origin, delta, node.bounds, best_t):
                continue
            if node.indices:
                for index in node.indices:
                    t = _segment_triangle_t(origin, delta, self.triangles[index])
                    if t is not None and t < best_t:
                        best_t, best_index = t, index
                continue
            if node.left is not None:
                stack.append(node.left)
            if node.right is not None:
                stack.append(node.right)
        if best_index < 0:
            return None
        return (best_t, self.triangles[best_index])

    def clipped_distance(
        self,
        start: Vec3,
        desired_end: Vec3,
        *,
        padding: float = 0.12,
        minimum_distance: float = 0.35,
    ) -> float:
        delta = tuple(float(desired_end[index]) - float(start[index]) for index in range(3))
        desired_distance = math.sqrt(sum(value * value for value in delta))
        if desired_distance <= 1.0e-9:
            return 0.0
        hit = self.nearest_hit_fraction(start, desired_end)
        if hit is None:
            return desired_distance
        return max(
            min(float(minimum_distance), desired_distance),
            min(desired_distance, (hit[0] * desired_distance) - max(0.0, float(padding))),
        )


__all__ = [
    "CollisionTriangle",
    "K1_WALKABLE_SURFACE_IDS",
    "K2_WALKABLE_SURFACE_IDS",
    "KOTOR_LINE_OF_SIGHT_SURFACE_IDS",
    "KOTOR_WALKCHECK_SURFACE_IDS",
    "SegmentCollisionIndex",
    "WalkmeshMoveResult",
    "WalkmeshRuntimeIndex",
    "WalkmeshSample",
    "kotor_walkable_surface_ids",
]
