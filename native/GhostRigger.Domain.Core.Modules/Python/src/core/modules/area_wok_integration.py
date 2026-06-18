"""Map Builder area WOK integration checks.

T1604 lifts room-level WOK validation into the Map Builder.  It combines the
LYT room graph with loaded WOK/DWK/PWK data so authors can see per-room
walkmesh coverage, face winding/material issues, transition counts, and rough
seam gaps between connected rooms before packaging a module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, Optional


@dataclass(frozen=True)
class AreaWOKIssue:
    """Actionable area-walkmesh issue."""

    severity: str
    code: str
    message: str
    room_id: str = ""
    target_room_id: str = ""
    face_index: int = -1


@dataclass(frozen=True)
class RoomWOKSummary:
    """Map Builder summary for one room's walkmesh."""

    room_id: str
    has_wok: bool = False
    vertex_count: int = 0
    face_count: int = 0
    walkable_face_count: int = 0
    non_walk_face_count: int = 0
    perimeter_edge_count: int = 0
    transition_face_count: int = 0
    invalid_material_faces: tuple[int, ...] = ()
    reversed_faces: tuple[int, ...] = ()
    degenerate_faces: tuple[int, ...] = ()
    bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0)
    bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class WOKFaceOverlay:
    """Viewport-ready annotation for one WOK face."""

    room_id: str
    face_index: int
    vertices: tuple[tuple[float, float, float], ...]
    surface_id: int
    surface_name: str
    walkable: bool
    issue_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class WOKEdgeOverlay:
    """Viewport-ready annotation for one WOK boundary/blocking edge."""

    room_id: str
    face_index: int
    edge_index: int
    start: tuple[float, float, float]
    end: tuple[float, float, float]
    kind: str = "boundary"
    issue_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoomWOKOverlay:
    """Overlay geometry a Map Studio viewport can draw for WOK diagnostics."""

    room_id: str
    faces: tuple[WOKFaceOverlay, ...] = ()
    edges: tuple[WOKEdgeOverlay, ...] = ()


@dataclass(frozen=True)
class WOKSeamReport:
    """Approximate walkmesh seam relationship between two rooms."""

    source_room: str
    target_room: str
    ok: bool = False
    min_boundary_distance: float = 0.0
    source_edge_count: int = 0
    target_edge_count: int = 0
    message: str = ""
    code: str = "not_checked"


@dataclass
class AreaWOKIntegrationReport:
    """Area-level walkmesh report for Map Builder."""

    ok: bool = False
    rooms: list[RoomWOKSummary] = field(default_factory=list)
    overlays: list[RoomWOKOverlay] = field(default_factory=list)
    seams: list[WOKSeamReport] = field(default_factory=list)
    issues: list[AreaWOKIssue] = field(default_factory=list)
    walkable_face_count: int = 0
    perimeter_edge_count: int = 0
    transition_face_count: int = 0
    message: str = ""
    code: str = "not_checked"


def _import_lyt_room_graph():
    for name in (
        "src.core.scene.lyt_room_graph",
        "core.scene.lyt_room_graph",
        "core.lyt_room_graph",
        "src.core.lyt_room_graph",
    ):
        try:
            return import_module(name)
        except ImportError:
            continue
    return import_module("src.core.scene.lyt_room_graph")


def _import_walkmesh_editor():
    for name in (
        "src.core.walkmesh.walkmesh_editor",
        "core.walkmesh.walkmesh_editor",
        "core.walkmesh_editor",
        "src.core.walkmesh_editor",
    ):
        try:
            return import_module(name)
        except ImportError:
            continue
    return import_module("src.core.walkmesh.walkmesh_editor")


def _normalise_resref(value: Any) -> str:
    return str(value or "").strip().lower()[:16]


def _module_from_input(value: Any) -> Any:
    return getattr(value, "module", value)


def _build_graph(module_like: Any) -> Any:
    if hasattr(module_like, "rooms") and hasattr(module_like, "visibility_edges"):
        return module_like
    return _import_lyt_room_graph().build_lyt_room_graph(module_like)


def _room_woks(module_like: Any) -> dict[str, Any]:
    module = _module_from_input(module_like)
    room_woks = getattr(module, "room_woks", {}) or {}
    if isinstance(room_woks, dict):
        return {_normalise_resref(key): value for key, value in room_woks.items()}
    return {}


def _wok_for_room(module_like: Any, room_id: str) -> Any:
    return _room_woks(module_like).get(_normalise_resref(room_id))


def _verts(wok: Any) -> list[tuple[float, float, float]]:
    return [tuple(v) for v in list(getattr(wok, "verts", []) or [])]


def _faces(wok: Any) -> list[Any]:
    return list(getattr(wok, "faces", []) or [])


def _face_indices(face: Any) -> tuple[int, int, int]:
    return (int(getattr(face, "v1", -1)), int(getattr(face, "v2", -1)), int(getattr(face, "v3", -1)))


def _face_surface(face: Any) -> int:
    return int(getattr(face, "surface", 0))


def _world_vertex(vertex: tuple[float, float, float], offset: tuple[float, float, float]) -> tuple[float, float, float]:
    return (float(vertex[0]) + offset[0], float(vertex[1]) + offset[1], float(vertex[2]) + offset[2])


def _world_vertices(wok: Any, offset: tuple[float, float, float]) -> list[tuple[float, float, float]]:
    return [_world_vertex(vertex, offset) for vertex in _verts(wok)]


def _triangle_area_xy(points: list[tuple[float, float, float]]) -> float:
    if len(points) != 3:
        return 0.0
    a, b, c = points
    return 0.5 * ((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]))


def _bounds(points: list[tuple[float, float, float]]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    if not points:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    return (
        (min(p[0] for p in points), min(p[1] for p in points), min(p[2] for p in points)),
        (max(p[0] for p in points), max(p[1] for p in points), max(p[2] for p in points)),
    )


def _surface_names() -> dict[int, str]:
    we = _import_walkmesh_editor()
    try:
        return dict(we._surface_names())  # type: ignore[attr-defined]
    except Exception:
        return {}


def _walkable_ids() -> set[int]:
    we = _import_walkmesh_editor()
    try:
        return set(we._walkable_ids())  # type: ignore[attr-defined]
    except Exception:
        return set()


def _boundary_edges(wok: Any) -> list[tuple[int, int, int, int]]:
    if hasattr(wok, "boundary_edges"):
        return list(wok.boundary_edges())
    return []


def _midpoint(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5)


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _boundary_midpoints(wok: Any, offset: tuple[float, float, float]) -> list[tuple[float, float, float]]:
    world = _world_vertices(wok, offset)
    points: list[tuple[float, float, float]] = []
    for va, vb, _face_index, _edge_index in _boundary_edges(wok):
        if 0 <= va < len(world) and 0 <= vb < len(world):
            points.append(_midpoint(world[va], world[vb]))
    return points


def _count_walkable_faces(wok: Any) -> int:
    if hasattr(wok, "walkable_face_count"):
        return int(wok.walkable_face_count())
    walkable = _walkable_ids()
    return sum(1 for face in _faces(wok) if _face_surface(face) in walkable)


def _count_non_walk_faces(wok: Any) -> int:
    if hasattr(wok, "non_walk_face_count"):
        return int(wok.non_walk_face_count())
    return sum(1 for face in _faces(wok) if _face_surface(face) == 7)


def _transition_count(wok: Any) -> int:
    return sum(1 for face in _faces(wok) if _face_surface(face) == 18)


def _room_summary(room: Any, wok: Any, *, winding_epsilon: float) -> RoomWOKSummary:
    room_id = _normalise_resref(getattr(room, "room_id", ""))
    if wok is None:
        return RoomWOKSummary(room_id=room_id, has_wok=False)
    offset = tuple(getattr(room, "position", (0.0, 0.0, 0.0)))
    world = _world_vertices(wok, offset)
    known_surfaces = _surface_names()
    invalid: list[int] = []
    reversed_faces: list[int] = []
    degenerate: list[int] = []
    for face_index, face in enumerate(_faces(wok)):
        indices = _face_indices(face)
        if any(index < 0 or index >= len(world) for index in indices):
            degenerate.append(face_index)
            continue
        points = [world[index] for index in indices]
        area = _triangle_area_xy(points)
        if abs(area) <= winding_epsilon:
            degenerate.append(face_index)
        elif area < 0:
            reversed_faces.append(face_index)
        if _face_surface(face) not in known_surfaces:
            invalid.append(face_index)
    bmin, bmax = _bounds(world)
    return RoomWOKSummary(
        room_id=room_id,
        has_wok=True,
        vertex_count=len(world),
        face_count=len(_faces(wok)),
        walkable_face_count=_count_walkable_faces(wok),
        non_walk_face_count=_count_non_walk_faces(wok),
        perimeter_edge_count=len(_boundary_edges(wok)),
        transition_face_count=_transition_count(wok),
        invalid_material_faces=tuple(invalid),
        reversed_faces=tuple(reversed_faces),
        degenerate_faces=tuple(degenerate),
        bounds_min=bmin,
        bounds_max=bmax,
    )


def _edge_vertices(face: Any, edge_index: int) -> tuple[int, int]:
    indices = _face_indices(face)
    return indices[edge_index], indices[(edge_index + 1) % 3]


def _edge_adjacent(face: Any, edge_index: int) -> int:
    return (int(getattr(face, "adj1", -1)), int(getattr(face, "adj2", -1)), int(getattr(face, "adj3", -1)))[edge_index]


def _room_overlay(room: Any, wok: Any, *, winding_epsilon: float) -> RoomWOKOverlay:
    room_id = _normalise_resref(getattr(room, "room_id", ""))
    if wok is None:
        return RoomWOKOverlay(room_id=room_id)
    offset = tuple(getattr(room, "position", (0.0, 0.0, 0.0)))
    world = _world_vertices(wok, offset)
    known_surfaces = _surface_names()
    walkable = _walkable_ids()
    face_overlays: list[WOKFaceOverlay] = []
    edge_overlays: list[WOKEdgeOverlay] = []
    faces = _faces(wok)
    for face_index, face in enumerate(faces):
        indices = _face_indices(face)
        valid_indices = all(0 <= index < len(world) for index in indices)
        points = tuple(world[index] for index in indices) if valid_indices else ()
        area = _triangle_area_xy(list(points)) if len(points) == 3 else 0.0
        surface_id = _face_surface(face)
        issue_codes: list[str] = []
        if surface_id not in known_surfaces:
            issue_codes.append("INVALID_WOK_MATERIAL")
        if not valid_indices or abs(area) <= winding_epsilon:
            issue_codes.append("DEGENERATE_FACE")
        elif area < 0:
            issue_codes.append("REVERSED_FACE_WINDING")
        face_overlays.append(
            WOKFaceOverlay(
                room_id=room_id,
                face_index=face_index,
                vertices=points,
                surface_id=surface_id,
                surface_name=str(known_surfaces.get(surface_id, f"SURFACE_{surface_id}")),
                walkable=surface_id in walkable,
                issue_codes=tuple(issue_codes),
            )
        )
        if surface_id not in walkable or not valid_indices:
            continue
        for edge_index in range(3):
            adjacent = _edge_adjacent(face, edge_index)
            if adjacent >= 0 and adjacent < len(faces) and _face_surface(faces[adjacent]) in walkable:
                continue
            va, vb = _edge_vertices(face, edge_index)
            if not (0 <= va < len(world) and 0 <= vb < len(world)):
                continue
            kind = "blocked" if adjacent >= 0 and adjacent < len(faces) else "boundary"
            edge_overlays.append(
                WOKEdgeOverlay(
                    room_id=room_id,
                    face_index=face_index,
                    edge_index=edge_index,
                    start=world[va],
                    end=world[vb],
                    kind=kind,
                    issue_codes=("BLOCKED_EDGE",) if kind == "blocked" else ("BOUNDARY_EDGE",),
                )
            )
    return RoomWOKOverlay(room_id=room_id, faces=tuple(face_overlays), edges=tuple(edge_overlays))


def _seam_report(
    source: Any,
    target: Any,
    source_wok: Any,
    target_wok: Any,
    *,
    tolerance: float,
) -> WOKSeamReport:
    source_id = _normalise_resref(getattr(source, "room_id", ""))
    target_id = _normalise_resref(getattr(target, "room_id", ""))
    if source_wok is None or target_wok is None:
        return WOKSeamReport(
            source_room=source_id,
            target_room=target_id,
            ok=False,
            message="One or both connected rooms have no WOK loaded.",
            code="missing_wok",
        )
    source_points = _boundary_midpoints(source_wok, tuple(getattr(source, "position", (0.0, 0.0, 0.0))))
    target_points = _boundary_midpoints(target_wok, tuple(getattr(target, "position", (0.0, 0.0, 0.0))))
    if not source_points or not target_points:
        return WOKSeamReport(
            source_room=source_id,
            target_room=target_id,
            ok=False,
            source_edge_count=len(source_points),
            target_edge_count=len(target_points),
            message="Connected room seam cannot be checked because one room has no perimeter edges.",
            code="missing_perimeter",
        )
    best = min(_distance(a, b) for a in source_points for b in target_points)
    ok = best <= tolerance
    return WOKSeamReport(
        source_room=source_id,
        target_room=target_id,
        ok=ok,
        min_boundary_distance=best,
        source_edge_count=len(source_points),
        target_edge_count=len(target_points),
        message=(
            f"Connected room boundaries are within {best:.3f}m."
            if ok else
            f"Connected room boundaries are {best:.3f}m apart; review seam coverage."
        ),
        code="seam_ok" if ok else "seam_gap",
    )


def validate_area_woks(
    module_like: Any,
    *,
    seam_tolerance: float = 0.25,
    winding_epsilon: float = 1e-6,
) -> AreaWOKIntegrationReport:
    """Validate WOK coverage and seam readiness for a Map Builder area."""

    graph = _build_graph(module_like)
    issues: list[AreaWOKIssue] = []
    if not getattr(graph, "rooms", None):
        return AreaWOKIntegrationReport(
            ok=False,
            issues=[
                AreaWOKIssue(
                    severity="error",
                    code="NO_ROOMS",
                    message="No LYT rooms are available for area WOK validation.",
                )
            ],
            message="No rooms are available for area WOK validation.",
            code="no_rooms",
        )

    room_by_id = {_normalise_resref(getattr(room, "room_id", "")): room for room in graph.rooms}
    summaries: list[RoomWOKSummary] = []
    overlays: list[RoomWOKOverlay] = []
    for room in graph.rooms:
        room_id = _normalise_resref(getattr(room, "room_id", ""))
        wok = _wok_for_room(module_like, room_id)
        summary = _room_summary(room, wok, winding_epsilon=winding_epsilon)
        summaries.append(summary)
        overlays.append(_room_overlay(room, wok, winding_epsilon=winding_epsilon))
        if not summary.has_wok:
            issues.append(
                AreaWOKIssue(
                    severity="error",
                    code="ROOM_WOK_MISSING",
                    message=f"Room '{room_id}' has no WOK loaded; creatures cannot path through it.",
                    room_id=room_id,
                )
            )
            continue
        if summary.walkable_face_count == 0:
            issues.append(
                AreaWOKIssue(
                    severity="error",
                    code="NO_WALKABLE_FACES",
                    message=f"Room '{room_id}' has no walkable faces.",
                    room_id=room_id,
                )
            )
        for face_index in summary.invalid_material_faces:
            issues.append(
                AreaWOKIssue(
                    severity="warning",
                    code="INVALID_WOK_MATERIAL",
                    message=f"Room '{room_id}' face {face_index} uses an unknown WOK material.",
                    room_id=room_id,
                    face_index=face_index,
                )
            )
        for face_index in summary.reversed_faces:
            issues.append(
                AreaWOKIssue(
                    severity="warning",
                    code="REVERSED_FACE_WINDING",
                    message=f"Room '{room_id}' face {face_index} has negative XY winding.",
                    room_id=room_id,
                    face_index=face_index,
                )
            )
        for face_index in summary.degenerate_faces:
            issues.append(
                AreaWOKIssue(
                    severity="warning",
                    code="DEGENERATE_FACE",
                    message=f"Room '{room_id}' face {face_index} is degenerate or references missing vertices.",
                    room_id=room_id,
                    face_index=face_index,
                )
            )

    seams: list[WOKSeamReport] = []
    seen_pairs: set[tuple[str, str]] = set()
    for edge in list(getattr(graph, "visibility_edges", []) or []):
        source_id = _normalise_resref(getattr(edge, "source", ""))
        target_id = _normalise_resref(getattr(edge, "target", ""))
        if not source_id or not target_id:
            continue
        pair = tuple(sorted((source_id, target_id)))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        source_room = room_by_id.get(source_id)
        target_room = room_by_id.get(target_id)
        if source_room is None or target_room is None:
            continue
        report = _seam_report(
            source_room,
            target_room,
            _wok_for_room(module_like, source_id),
            _wok_for_room(module_like, target_id),
            tolerance=seam_tolerance,
        )
        seams.append(report)
        if report.code == "seam_gap":
            issues.append(
                AreaWOKIssue(
                    severity="warning",
                    code="WOK_SEAM_GAP",
                    message=report.message,
                    room_id=source_id,
                    target_room_id=target_id,
                )
            )
        elif report.code in {"missing_wok", "missing_perimeter"}:
            issues.append(
                AreaWOKIssue(
                    severity="warning",
                    code=report.code.upper(),
                    message=report.message,
                    room_id=source_id,
                    target_room_id=target_id,
                )
            )

    has_errors = any(issue.severity.lower() == "error" for issue in issues)
    return AreaWOKIntegrationReport(
        ok=not has_errors,
        rooms=summaries,
        overlays=overlays,
        seams=seams,
        issues=issues,
        walkable_face_count=sum(summary.walkable_face_count for summary in summaries),
        perimeter_edge_count=sum(summary.perimeter_edge_count for summary in summaries),
        transition_face_count=sum(summary.transition_face_count for summary in summaries),
        message=(
            f"Area WOK validation passed for {len(summaries)} room(s)."
            if not has_errors else
            f"Area WOK validation found {sum(1 for issue in issues if issue.severity.lower() == 'error')} blocking issue(s)."
        ),
        code="valid" if not has_errors else "invalid",
    )


__all__ = [
    "AreaWOKIssue",
    "RoomWOKOverlay",
    "RoomWOKSummary",
    "WOKEdgeOverlay",
    "WOKFaceOverlay",
    "WOKSeamReport",
    "AreaWOKIntegrationReport",
    "validate_area_woks",
]
