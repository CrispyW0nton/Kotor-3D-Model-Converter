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


Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
WALKABLE_SURFACE_IDS = frozenset({1, 3, 4, 5, 9, 10, 11, 12, 13, 14, 19, 20, 21})


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


def _point_on_walkmesh(wok: Any, x: float, y: float) -> tuple[bool, int]:
    face_at_point = getattr(wok, "face_at_point", None)
    if not callable(face_at_point):
        return True, -1
    face_index = int(face_at_point(float(x), float(y)))
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
) -> tuple[bool, tuple[float, float, int] | None]:
    distance = hypot(float(target.x) - float(source.x), float(target.y) - float(source.y))
    if distance <= 1.0e-7:
        return True, None
    steps = max(1, int(ceil(distance / sample_interval)))
    for step in range(1, steps):
        fraction = step / steps
        x = float(source.x) + (float(target.x) - float(source.x)) * fraction
        y = float(source.y) + (float(target.y) - float(source.y)) * fraction
        ok, _face_index = _point_on_walkmesh(wok, x, y)
        if not ok:
            return False, (x, y, step)
    return True, None


def build_authored_path_graph_from_walkmesh(
    wok: Any,
    *,
    anchors: tuple[AuthoredPathAnchor, ...] = (),
) -> AuthoredPathGraph:
    """Build a compact initial path graph from a WOK and gameplay anchors."""

    min_x, min_y, max_x, max_y = _walkmesh_bounds(wok)
    center = ((min_x + max_x) * 0.5, (min_y + max_y) * 0.5)
    points: list[AuthoredPathPoint] = [
        AuthoredPathPoint(
            label="walkmesh_center",
            x=center[0],
            y=center[1],
            metadata={"source": "walkmesh_bounds"},
        )
    ]
    seen = {_xy_key(center[0], center[1])}
    anchor_labels: list[str] = []
    for anchor in anchors:
        x = float(anchor.position[0])
        y = float(anchor.position[1])
        key = _xy_key(x, y)
        anchor_labels.append(anchor.label)
        if key in seen:
            continue
        ok, face_index = _point_on_walkmesh(wok, x, y)
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
                connections.append(AuthoredPathConnection(source=source, target=target))
    return AuthoredPathGraph(
        points=tuple(points),
        connections=tuple(connections),
        metadata={
            "source": "src.core.modules.authored_module_pathing",
            "generated_from": "walkmesh_and_gameplay_anchors",
            "walkmesh_bounds": [min_x, min_y, max_x, max_y],
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
            ok, _face_index = _point_on_walkmesh(wok, float(point.x), float(point.y))
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
            )
            if not ok and failed_sample is not None:
                x, y, step = failed_sample
                blocking.append(
                    f"Path connection {edge.source}->{edge.target} leaves the generated walkmesh near sample {step} "
                    f"({x:.3f}, {y:.3f})."
                )
    if len(graph.points) > 1 and not graph.connections:
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
