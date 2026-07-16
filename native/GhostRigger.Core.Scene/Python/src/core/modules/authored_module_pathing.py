"""Headless authored PTH/path graph compiler for Map Studio.

KOTOR module PTH files are GFF resources used by the engine's pathfinding
loader.  Map Studio should author this as editable path intent first, then
compile it to the Odyssey ``Path_Points`` / ``Path_Conections`` fields through
a reusable Qt-free service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil, hypot, isfinite
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
        for face_index in self._buckets.get((self._col(x), self._row(y)), ()):
            if _face_contains_xy(self._verts, self._faces[face_index], float(x), float(y), epsilon=epsilon):
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


def _walkable_components(wok: Any) -> tuple[tuple[int, ...], ...]:
    faces = list(getattr(wok, "faces", ()) or ())
    verts = list(getattr(wok, "verts", ()) or ())
    walkable: set[int] = set()
    edge_faces: dict[tuple[tuple[float, float, float], tuple[float, float, float]], list[int]] = {}
    for face_index, face in enumerate(faces):
        if int(getattr(face, "surface", -1)) not in WALKABLE_SURFACE_IDS:
            continue
        indices = _face_indices(face)
        if any(index < 0 or index >= len(verts) for index in indices):
            continue
        walkable.add(face_index)
        for left, right in ((indices[0], indices[1]), (indices[1], indices[2]), (indices[2], indices[0])):
            a = tuple(round(float(value), 5) for value in verts[left])
            b = tuple(round(float(value), 5) for value in verts[right])
            key = (a, b) if a <= b else (b, a)
            edge_faces.setdefault(key, []).append(face_index)

    adjacency: dict[int, set[int]] = {face_index: set() for face_index in walkable}
    for linked in edge_faces.values():
        unique = sorted(set(linked))
        for left in unique:
            for right in unique:
                if left != right:
                    adjacency[left].add(right)
    for face_index in walkable:
        face = faces[face_index]
        for adjacent in (int(getattr(face, "adj1", -1)), int(getattr(face, "adj2", -1)), int(getattr(face, "adj3", -1))):
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
    return tuple(sorted(components, key=lambda item: (-len(item), item[0] if item else -1)))


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
                },
            )
        )
        seen.add(key)

    connections: list[AuthoredPathConnection] = []
    for source in range(len(points)):
        for target in range(len(points)):
            if source != target:
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


__all__ = [
    "AuthoredPathAnchor",
    "AuthoredPathConnection",
    "AuthoredPathGraph",
    "AuthoredPathPoint",
    "AuthoredPathingValidation",
    "CompiledAuthoredPathing",
    "build_authored_path_graph_from_walkmesh",
    "build_authored_pth_bytes",
    "compile_authored_pathing_for_module",
    "validate_authored_path_graph",
]
