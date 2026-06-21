"""Map Builder snap and alignment tools.

T1602 adds headless snapping primitives on top of the LYT room graph.  These
tools do not load room MDLs or infer mesh seams; they operate on known authoring
handles: room AuroraBase positions, LYT door hooks, grid spacing, and GIT-style
placed object dictionaries.  Mesh/WOK-aware seam validation arrives in T1604.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Optional


OBJECT_SPECS: dict[str, tuple[tuple[str, ...], tuple[str, str, str]]] = {
    "creature": (("Creature List", "CreatureList"), ("XPosition", "YPosition", "ZPosition")),
    "door": (("Door List", "DoorList"), ("X", "Y", "Z")),
    "placeable": (("Placeable List", "PlaceableList"), ("X", "Y", "Z")),
    "trigger": (("TriggerList", "Trigger List"), ("XPosition", "YPosition", "ZPosition")),
    "encounter": (("Encounter List", "EncounterList"), ("XPosition", "YPosition", "ZPosition")),
    "waypoint": (("WaypointList", "Waypoint List"), ("XPosition", "YPosition", "ZPosition")),
    "sound": (("SoundList", "Sound List"), ("XPosition", "YPosition", "ZPosition")),
    "store": (("StoreList", "Store List"), ("XPosition", "YPosition", "ZPosition")),
}


@dataclass(frozen=True)
class MapSnapAnchor:
    """A room or doorway handle usable for snap operations."""

    anchor_id: str
    kind: str
    room_id: str
    name: str
    world_position: tuple[float, float, float]
    local_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_quat: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    source: str = ""


@dataclass(frozen=True)
class MapSnapCandidate:
    """A possible snap between two anchors."""

    moving_anchor: MapSnapAnchor
    target_anchor: MapSnapAnchor
    delta: tuple[float, float, float]
    distance: float
    score: float


@dataclass
class MapSnapResult:
    """Result of snapping a room."""

    ok: bool = False
    graph: Any = None
    moving_room_id: str = ""
    old_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    new_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    delta: tuple[float, float, float] = (0.0, 0.0, 0.0)
    candidate: Optional[MapSnapCandidate] = None
    message: str = ""
    code: str = "not_snapped"


@dataclass
class ObjectAlignmentResult:
    """Result of aligning a GIT-placed object."""

    ok: bool = False
    graph: Any = None
    object_type: str = ""
    index: int = -1
    room_id: str = ""
    old_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    new_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    message: str = ""
    code: str = "not_aligned"


def _import_lyt_room_graph():
    try:
        return import_module("core.lyt_room_graph")
    except ImportError:
        return import_module("src.core.lyt_room_graph")


def _normalise_resref(value: Any) -> str:
    return str(value or "").strip().lower()[:16]


def _module_from_input(value: Any) -> Any:
    return getattr(value, "module", value)


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _round_to_grid(value: float, grid_size: float) -> float:
    if grid_size <= 0:
        raise ValueError("grid_size must be greater than zero")
    return round(value / grid_size) * grid_size


def _snap_position_to_grid(
    position: tuple[float, float, float],
    grid_size: float,
    axes: tuple[str, ...] = ("x", "y"),
) -> tuple[float, float, float]:
    x, y, z = position
    axes_set = {axis.lower() for axis in axes}
    return (
        _round_to_grid(x, grid_size) if "x" in axes_set else x,
        _round_to_grid(y, grid_size) if "y" in axes_set else y,
        _round_to_grid(z, grid_size) if "z" in axes_set else z,
    )


def _build_graph(module_like: Any):
    return _import_lyt_room_graph().build_lyt_room_graph(module_like)


def _room_by_id(graph: Any, room_id: str) -> Any:
    target = _normalise_resref(room_id)
    for room in list(getattr(graph, "rooms", []) or []):
        if _normalise_resref(getattr(room, "room_id", "")) == target:
            return room
    return None


def _set_room_position(module_like: Any, room_id: str, position: tuple[float, float, float]) -> MapSnapResult:
    lg = _import_lyt_room_graph()
    edit = lg.move_room_in_lyt(module_like, room_id, position)
    if not getattr(edit, "ok", False):
        return MapSnapResult(message=getattr(edit, "message", "Room move failed."), code=getattr(edit, "code", "room_move_failed"))
    return MapSnapResult(ok=True, graph=edit.graph, moving_room_id=_normalise_resref(room_id), new_position=position, code="room_moved")


def build_snap_anchors(graph: Any) -> list[MapSnapAnchor]:
    """Build room-origin and door-hook anchors from a LYT room graph."""

    rooms = list(getattr(graph, "rooms", []) or [])
    anchors: list[MapSnapAnchor] = []
    room_by_id = {_normalise_resref(getattr(room, "room_id", "")): room for room in rooms}
    for room in rooms:
        room_id = _normalise_resref(getattr(room, "room_id", ""))
        position = tuple(getattr(room, "position", (0.0, 0.0, 0.0)))
        anchors.append(
            MapSnapAnchor(
                anchor_id=f"room:{room_id}:origin",
                kind="room_origin",
                room_id=room_id,
                name=f"{room_id} origin",
                world_position=position,
                local_position=(0.0, 0.0, 0.0),
                source="lyt_room",
            )
        )

    for hook in list(getattr(graph, "door_hooks", []) or []):
        room_id = _normalise_resref(getattr(hook, "nearest_room", ""))
        if not room_id:
            continue
        room = room_by_id.get(room_id)
        world = tuple(getattr(hook, "position", (0.0, 0.0, 0.0)))
        room_pos = tuple(getattr(room, "position", (0.0, 0.0, 0.0))) if room is not None else (0.0, 0.0, 0.0)
        name = _normalise_resref(getattr(hook, "name", "doorhook"))
        anchors.append(
            MapSnapAnchor(
                anchor_id=f"door:{room_id}:{name}:{getattr(hook, 'index', len(anchors))}",
                kind="doorhook",
                room_id=room_id,
                name=name,
                world_position=world,
                local_position=_sub(world, room_pos),
                rotation_quat=tuple(getattr(hook, "rotation_quat", (0.0, 0.0, 0.0, 1.0))),
                source="lyt_doorhook",
            )
        )
    return anchors


def find_snap_candidates(
    graph: Any,
    moving_room_id: str,
    *,
    max_distance: float = 5.0,
    kinds: tuple[str, ...] = ("doorhook",),
) -> list[MapSnapCandidate]:
    """Find target anchors close enough to snap a moving room."""

    moving = _normalise_resref(moving_room_id)
    kinds_set = {kind.lower() for kind in kinds}
    anchors = [anchor for anchor in build_snap_anchors(graph) if anchor.kind.lower() in kinds_set]
    moving_anchors = [anchor for anchor in anchors if anchor.room_id == moving]
    target_anchors = [anchor for anchor in anchors if anchor.room_id != moving]
    candidates: list[MapSnapCandidate] = []
    for moving_anchor in moving_anchors:
        for target_anchor in target_anchors:
            delta = _sub(target_anchor.world_position, moving_anchor.world_position)
            distance = _distance(target_anchor.world_position, moving_anchor.world_position)
            if distance <= max_distance:
                candidates.append(
                    MapSnapCandidate(
                        moving_anchor=moving_anchor,
                        target_anchor=target_anchor,
                        delta=delta,
                        distance=distance,
                        score=1.0 / (1.0 + distance),
                    )
                )
    return sorted(candidates, key=lambda candidate: (candidate.distance, candidate.moving_anchor.anchor_id, candidate.target_anchor.anchor_id))


def snap_room_to_anchor(
    module_like: Any,
    moving_room_id: str,
    moving_anchor_id: str,
    target_anchor_id: str,
) -> MapSnapResult:
    """Move a room so one of its anchors lands on a target anchor."""

    graph = _build_graph(module_like)
    if not getattr(graph, "ok", False):
        return MapSnapResult(graph=graph, moving_room_id=_normalise_resref(moving_room_id), message=getattr(graph, "message", "Invalid graph."), code=getattr(graph, "code", "invalid_graph"))
    room = _room_by_id(graph, moving_room_id)
    if room is None:
        return MapSnapResult(graph=graph, moving_room_id=_normalise_resref(moving_room_id), message=f"Room '{moving_room_id}' is not present in LYT.", code="room_missing")

    anchors = {anchor.anchor_id: anchor for anchor in build_snap_anchors(graph)}
    moving_anchor = anchors.get(moving_anchor_id)
    target_anchor = anchors.get(target_anchor_id)
    if moving_anchor is None or target_anchor is None:
        return MapSnapResult(graph=graph, moving_room_id=_normalise_resref(moving_room_id), message="Moving or target snap anchor was not found.", code="anchor_missing")
    if moving_anchor.room_id != _normalise_resref(moving_room_id):
        return MapSnapResult(graph=graph, moving_room_id=_normalise_resref(moving_room_id), message="Moving anchor does not belong to the moving room.", code="anchor_room_mismatch")

    old_position = tuple(getattr(room, "position", (0.0, 0.0, 0.0)))
    new_position = _sub(target_anchor.world_position, moving_anchor.local_position)
    delta = _sub(new_position, old_position)
    move = _set_room_position(module_like, moving_room_id, new_position)
    candidate = MapSnapCandidate(
        moving_anchor=moving_anchor,
        target_anchor=target_anchor,
        delta=delta,
        distance=_distance(moving_anchor.world_position, target_anchor.world_position),
        score=1.0 / (1.0 + _distance(moving_anchor.world_position, target_anchor.world_position)),
    )
    move.old_position = old_position
    move.delta = delta
    move.candidate = candidate
    move.message = f"Snapped room '{_normalise_resref(moving_room_id)}' to anchor '{target_anchor.anchor_id}'."
    move.code = "room_snapped"
    return move


def snap_room_to_nearest_anchor(
    module_like: Any,
    moving_room_id: str,
    *,
    max_distance: float = 5.0,
    kinds: tuple[str, ...] = ("doorhook",),
) -> MapSnapResult:
    """Snap a room to the nearest compatible anchor within max_distance."""

    graph = _build_graph(module_like)
    candidates = find_snap_candidates(graph, moving_room_id, max_distance=max_distance, kinds=kinds)
    if not candidates:
        return MapSnapResult(graph=graph, moving_room_id=_normalise_resref(moving_room_id), message="No compatible snap anchors were close enough.", code="no_candidate")
    candidate = candidates[0]
    result = snap_room_to_anchor(module_like, moving_room_id, candidate.moving_anchor.anchor_id, candidate.target_anchor.anchor_id)
    if result.ok:
        result.candidate = candidate
    return result


def snap_room_to_grid(
    module_like: Any,
    room_id: str,
    *,
    grid_size: float = 5.0,
    axes: tuple[str, ...] = ("x", "y"),
) -> MapSnapResult:
    """Round a room's LYT translation to a grid."""

    graph = _build_graph(module_like)
    room = _room_by_id(graph, room_id)
    if room is None:
        return MapSnapResult(graph=graph, moving_room_id=_normalise_resref(room_id), message=f"Room '{room_id}' is not present in LYT.", code="room_missing")
    old_position = tuple(getattr(room, "position", (0.0, 0.0, 0.0)))
    new_position = _snap_position_to_grid(old_position, grid_size, axes)
    move = _set_room_position(module_like, room_id, new_position)
    move.old_position = old_position
    move.delta = _sub(new_position, old_position)
    move.message = f"Snapped room '{_normalise_resref(room_id)}' to {grid_size:g}m grid."
    move.code = "room_grid_snapped"
    return move


def _git_raw(module_like: Any) -> dict[str, Any]:
    module = _module_from_input(module_like)
    git = getattr(module, "git", None)
    raw = getattr(git, "_raw", None)
    return raw if isinstance(raw, dict) else {}


def _raw_list(raw: dict[str, Any], labels: tuple[str, ...]) -> tuple[str, list[Any]]:
    for label in labels:
        value = raw.get(label)
        if isinstance(value, list):
            return label, value
    return labels[0], []


def _object_row(module_like: Any, object_type: str, index: int) -> tuple[dict[str, Any], tuple[str, str, str]]:
    spec = OBJECT_SPECS.get(object_type.lower())
    if spec is None:
        return {}, ("XPosition", "YPosition", "ZPosition")
    _, rows = _raw_list(_git_raw(module_like), spec[0])
    if index < 0 or index >= len(rows) or not isinstance(rows[index], dict):
        return {}, spec[1]
    return rows[index], spec[1]


def _object_position(row: dict[str, Any], keys: tuple[str, str, str]) -> tuple[float, float, float]:
    x_key, y_key, z_key = keys
    return (
        float(row.get(x_key, 0.0) or 0.0),
        float(row.get(y_key, 0.0) or 0.0),
        float(row.get(z_key, 0.0) or 0.0),
    )


def _set_object_position(row: dict[str, Any], keys: tuple[str, str, str], position: tuple[float, float, float]) -> None:
    x_key, y_key, z_key = keys
    row[x_key] = float(position[0])
    row[y_key] = float(position[1])
    row[z_key] = float(position[2])


def _nearest_room_id(graph: Any, position: tuple[float, float, float]) -> str:
    rooms = list(getattr(graph, "rooms", []) or [])
    if not rooms:
        return ""
    return min(rooms, key=lambda room: _distance(position, tuple(getattr(room, "position", (0.0, 0.0, 0.0))))).room_id


def align_object_to_room(
    module_like: Any,
    object_type: str,
    index: int,
    *,
    room_id: str = "",
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
    grid_size: Optional[float] = None,
    grid_axes: tuple[str, ...] = ("x", "y"),
) -> ObjectAlignmentResult:
    """Place a GIT object relative to a room origin, optionally grid-snapped."""

    graph = _build_graph(module_like)
    row, keys = _object_row(module_like, object_type, index)
    if not row:
        return ObjectAlignmentResult(graph=graph, object_type=object_type, index=index, message=f"No {object_type} object at index {index}.", code="object_missing")
    old_position = _object_position(row, keys)
    target_room_id = _normalise_resref(room_id) or _nearest_room_id(graph, old_position)
    room = _room_by_id(graph, target_room_id)
    if room is None:
        return ObjectAlignmentResult(graph=graph, object_type=object_type, index=index, room_id=target_room_id, old_position=old_position, message=f"Room '{target_room_id}' is not present in LYT.", code="room_missing")
    new_position = _add(tuple(getattr(room, "position", (0.0, 0.0, 0.0))), offset)
    if grid_size is not None:
        new_position = _snap_position_to_grid(new_position, grid_size, grid_axes)
    _set_object_position(row, keys, new_position)
    return ObjectAlignmentResult(
        ok=True,
        graph=graph,
        object_type=object_type.lower(),
        index=index,
        room_id=target_room_id,
        old_position=old_position,
        new_position=new_position,
        message=f"Aligned {object_type}.{index} to room '{target_room_id}'.",
        code="object_aligned",
    )


def snap_object_to_grid(
    module_like: Any,
    object_type: str,
    index: int,
    *,
    grid_size: float = 1.0,
    axes: tuple[str, ...] = ("x", "y"),
) -> ObjectAlignmentResult:
    """Round a placed object's coordinates to a grid."""

    graph = _build_graph(module_like)
    row, keys = _object_row(module_like, object_type, index)
    if not row:
        return ObjectAlignmentResult(graph=graph, object_type=object_type, index=index, message=f"No {object_type} object at index {index}.", code="object_missing")
    old_position = _object_position(row, keys)
    new_position = _snap_position_to_grid(old_position, grid_size, axes)
    _set_object_position(row, keys, new_position)
    return ObjectAlignmentResult(
        ok=True,
        graph=graph,
        object_type=object_type.lower(),
        index=index,
        room_id=_nearest_room_id(graph, new_position),
        old_position=old_position,
        new_position=new_position,
        message=f"Snapped {object_type}.{index} to {grid_size:g}m grid.",
        code="object_grid_snapped",
    )


__all__ = [
    "MapSnapAnchor",
    "MapSnapCandidate",
    "MapSnapResult",
    "ObjectAlignmentResult",
    "build_snap_anchors",
    "find_snap_candidates",
    "snap_room_to_anchor",
    "snap_room_to_nearest_anchor",
    "snap_room_to_grid",
    "align_object_to_room",
    "snap_object_to_grid",
]
