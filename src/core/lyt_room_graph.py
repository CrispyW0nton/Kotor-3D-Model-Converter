"""Map Builder LYT room graph model.

T1601 converts KotOR LYT/VIS data into a headless graph that the Map Builder
can edit safely before any rendering or room-model loading happens.  LYT places
the AuroraBase transform for each room model; VIS adds visibility relationships.
This service keeps those two concerns explicit and round-trippable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, Optional


Matrix4 = tuple[
    float, float, float, float,
    float, float, float, float,
    float, float, float, float,
    float, float, float, float,
]


@dataclass(frozen=True)
class LYTRoomNode:
    """One room/model entry from a LYT layout."""

    index: int
    room_id: str
    model_resref: str
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    aurora_base_transform: Matrix4 = (
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    )
    visible_rooms: tuple[str, ...] = ()
    has_wok: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LYTDoorHookNode:
    """One door hook entry from a LYT layout."""

    index: int
    name: str
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_quat: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    nearest_room: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LYTRoomVisibilityEdge:
    """Directed VIS relationship between two rooms."""

    source: str
    target: str
    bidirectional: bool = False


@dataclass(frozen=True)
class LYTGraphIssue:
    """Actionable graph/modeling issue."""

    severity: str
    code: str
    message: str
    room_id: str = ""
    target_id: str = ""


@dataclass
class LYTRoomGraph:
    """Map Builder-ready room graph."""

    ok: bool = False
    module_root: str = ""
    rooms: list[LYTRoomNode] = field(default_factory=list)
    door_hooks: list[LYTDoorHookNode] = field(default_factory=list)
    visibility_edges: list[LYTRoomVisibilityEdge] = field(default_factory=list)
    issues: list[LYTGraphIssue] = field(default_factory=list)
    bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0)
    bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0)
    message: str = ""
    code: str = "not_built"


@dataclass
class LYTRoomEditResult:
    """Result of editing the headless graph/layout."""

    ok: bool = False
    graph: Optional[LYTRoomGraph] = None
    room: Optional[LYTRoomNode] = None
    message: str = ""
    code: str = "not_edited"


def _import_module_format():
    try:
        return import_module("core.module_format")
    except ImportError:
        return import_module("src.core.module_format")


def _normalise_resref(value: Any) -> str:
    return str(value or "").strip().lower()[:16]


def _module_from_input(value: Any) -> Any:
    return getattr(value, "module", value)


def _lyt_from_input(value: Any) -> Any:
    if hasattr(value, "rooms") and hasattr(value, "doorhooks"):
        return value
    module = _module_from_input(value)
    return getattr(module, "lyt", None)


def _vis_from_input(value: Any, vis: Any = None) -> Any:
    if vis is not None:
        return vis
    module = _module_from_input(value)
    return getattr(module, "vis", None)


def _room_wok_index(value: Any) -> set[str]:
    module = _module_from_input(value)
    room_woks = getattr(module, "room_woks", {}) or {}
    if isinstance(room_woks, dict):
        return {_normalise_resref(key) for key in room_woks}
    return set()


def _translation_matrix(position: tuple[float, float, float]) -> Matrix4:
    x, y, z = position
    return (
        1.0, 0.0, 0.0, x,
        0.0, 1.0, 0.0, y,
        0.0, 0.0, 1.0, z,
        0.0, 0.0, 0.0, 1.0,
    )


def _position_from_room(room: Any) -> tuple[float, float, float]:
    return (
        float(getattr(room, "x", 0.0)),
        float(getattr(room, "y", 0.0)),
        float(getattr(room, "z", 0.0)),
    )


def _position_from_hook(hook: Any) -> tuple[float, float, float]:
    return (
        float(getattr(hook, "x", 0.0)),
        float(getattr(hook, "y", 0.0)),
        float(getattr(hook, "z", 0.0)),
    )


def _room_distance(position: tuple[float, float, float], room: LYTRoomNode) -> float:
    dx = position[0] - room.position[0]
    dy = position[1] - room.position[1]
    dz = position[2] - room.position[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _nearest_room(position: tuple[float, float, float], rooms: list[LYTRoomNode]) -> str:
    if not rooms:
        return ""
    return min(rooms, key=lambda room: _room_distance(position, room)).room_id


def _visibility_dict(vis: Any) -> dict[str, list[str]]:
    visibility = getattr(vis, "visibility", None)
    if isinstance(visibility, dict):
        return {
            _normalise_resref(key): [_normalise_resref(item) for item in list(value or [])]
            for key, value in visibility.items()
        }
    return {}


def _bounds(rooms: list[LYTRoomNode]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    if not rooms:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    xs = [room.position[0] for room in rooms]
    ys = [room.position[1] for room in rooms]
    zs = [room.position[2] for room in rooms]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def build_lyt_room_graph(module_like: Any, *, vis: Any = None, module_root: str = "") -> LYTRoomGraph:
    """Build a Map Builder room graph from LYT and optional VIS data."""

    lyt = _lyt_from_input(module_like)
    vis_data = _vis_from_input(module_like, vis)
    module = _module_from_input(module_like)
    root = module_root or str(getattr(module_like, "module_root", "") or getattr(module, "name", "") or "")
    issues: list[LYTGraphIssue] = []

    if lyt is None:
        return LYTRoomGraph(
            ok=False,
            module_root=root,
            issues=[
                LYTGraphIssue(
                    severity="error",
                    code="NO_LYT",
                    message="No LYT layout is loaded; Map Builder needs room entries before snapping can start.",
                )
            ],
            message="No LYT layout is loaded.",
            code="no_lyt",
        )

    visibility = _visibility_dict(vis_data)
    wok_rooms = _room_wok_index(module_like)
    rooms: list[LYTRoomNode] = []
    seen: set[str] = set()
    for index, room in enumerate(list(getattr(lyt, "rooms", []) or [])):
        model = _normalise_resref(getattr(room, "model", ""))
        if not model or model == "null":
            issues.append(
                LYTGraphIssue(
                    severity="info",
                    code="SKIPPED_NULL_ROOM",
                    message=f"LYT room entry {index} is NULL/empty and was skipped.",
                )
            )
            continue
        if model in seen:
            issues.append(
                LYTGraphIssue(
                    severity="warning",
                    code="DUPLICATE_ROOM_MODEL",
                    message=f"Room model '{model}' appears more than once in LYT.",
                    room_id=model,
                )
            )
        seen.add(model)
        position = _position_from_room(room)
        rooms.append(
            LYTRoomNode(
                index=index,
                room_id=model,
                model_resref=model,
                position=position,
                aurora_base_transform=_translation_matrix(position),
                visible_rooms=tuple(visibility.get(model, [])),
                has_wok=model in wok_rooms,
                metadata={
                    "source": "lyt",
                    "lyt_index": index,
                    "has_vis_entry": model in visibility,
                },
            )
        )

    room_ids = {room.room_id for room in rooms}
    edges: list[LYTRoomVisibilityEdge] = []
    for source, targets in visibility.items():
        if source not in room_ids:
            issues.append(
                LYTGraphIssue(
                    severity="warning",
                    code="VIS_SOURCE_MISSING_ROOM",
                    message=f"VIS source room '{source}' is not present in the LYT room list.",
                    room_id=source,
                )
            )
        for target in targets:
            if target and target not in room_ids:
                issues.append(
                    LYTGraphIssue(
                        severity="warning",
                        code="VIS_TARGET_MISSING_ROOM",
                        message=f"VIS target room '{target}' referenced by '{source}' is not present in LYT.",
                        room_id=source,
                        target_id=target,
                    )
                )
            edges.append(
                LYTRoomVisibilityEdge(
                    source=source,
                    target=target,
                    bidirectional=source in visibility.get(target, []),
                )
            )

    if vis_data is None and len(rooms) > 1:
        issues.append(
            LYTGraphIssue(
                severity="info",
                code="NO_VIS",
                message="No VIS data is loaded; all rooms should be treated as visible until VIS is authored.",
            )
        )

    door_hooks: list[LYTDoorHookNode] = []
    for index, hook in enumerate(list(getattr(lyt, "doorhooks", []) or [])):
        position = _position_from_hook(hook)
        door_hooks.append(
            LYTDoorHookNode(
                index=index,
                name=_normalise_resref(getattr(hook, "name", "")),
                position=position,
                rotation_quat=(
                    float(getattr(hook, "qx", 0.0)),
                    float(getattr(hook, "qy", 0.0)),
                    float(getattr(hook, "qz", 0.0)),
                    float(getattr(hook, "qw", 1.0)),
                ),
                nearest_room=_nearest_room(position, rooms),
                metadata={"source": "lyt", "lyt_index": index},
            )
        )

    bmin, bmax = _bounds(rooms)
    blocking = [issue for issue in issues if issue.severity.lower() == "error"]
    return LYTRoomGraph(
        ok=bool(rooms) and not blocking,
        module_root=root,
        rooms=rooms,
        door_hooks=door_hooks,
        visibility_edges=edges,
        issues=issues,
        bounds_min=bmin,
        bounds_max=bmax,
        message=f"Built LYT room graph with {len(rooms)} room(s) and {len(door_hooks)} door hook(s).",
        code="built" if rooms and not blocking else "invalid",
    )


def create_lyt_layout(rooms: list[LYTRoomNode], door_hooks: list[LYTDoorHookNode] | None = None) -> Any:
    """Create a module_format.LYTLayout from graph nodes."""

    mf = _import_module_format()
    layout = mf.LYTLayout()
    for room in rooms:
        x, y, z = room.position
        layout.rooms.append(mf.LYTRoom(room.model_resref, x, y, z))
    for hook in list(door_hooks or []):
        x, y, z = hook.position
        qx, qy, qz, qw = hook.rotation_quat
        layout.doorhooks.append(mf.LYTDoorHook(hook.name, x, y, z, qx, qy, qz, qw))
    return layout


def add_room_to_lyt(module_like: Any, model_resref: str, position: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> LYTRoomEditResult:
    """Append a room entry to a loaded LYT layout."""

    lyt = _lyt_from_input(module_like)
    if lyt is None:
        return LYTRoomEditResult(message="No LYT layout is loaded.", code="no_lyt")
    model = _normalise_resref(model_resref)
    if not model:
        return LYTRoomEditResult(message="Room model resref is required.", code="missing_resref")
    mf = _import_module_format()
    x, y, z = position
    lyt.rooms.append(mf.LYTRoom(model, float(x), float(y), float(z)))
    graph = build_lyt_room_graph(module_like)
    room = next((item for item in graph.rooms if item.room_id == model and item.index == len(getattr(lyt, "rooms", [])) - 1), None)
    return LYTRoomEditResult(ok=True, graph=graph, room=room, message=f"Added room '{model}'.", code="room_added")


def move_room_in_lyt(module_like: Any, room_id: str, position: tuple[float, float, float]) -> LYTRoomEditResult:
    """Update a room's AuroraBase translation in the loaded LYT layout."""

    lyt = _lyt_from_input(module_like)
    if lyt is None:
        return LYTRoomEditResult(message="No LYT layout is loaded.", code="no_lyt")
    target = _normalise_resref(room_id)
    for room in list(getattr(lyt, "rooms", []) or []):
        if _normalise_resref(getattr(room, "model", "")) == target:
            room.x, room.y, room.z = float(position[0]), float(position[1]), float(position[2])
            graph = build_lyt_room_graph(module_like)
            moved = next((item for item in graph.rooms if item.room_id == target), None)
            return LYTRoomEditResult(ok=True, graph=graph, room=moved, message=f"Moved room '{target}'.", code="room_moved")
    return LYTRoomEditResult(message=f"Room '{target}' is not present in LYT.", code="room_missing")


__all__ = [
    "LYTRoomNode",
    "LYTDoorHookNode",
    "LYTRoomVisibilityEdge",
    "LYTGraphIssue",
    "LYTRoomGraph",
    "LYTRoomEditResult",
    "build_lyt_room_graph",
    "create_lyt_layout",
    "add_room_to_lyt",
    "move_room_in_lyt",
]
