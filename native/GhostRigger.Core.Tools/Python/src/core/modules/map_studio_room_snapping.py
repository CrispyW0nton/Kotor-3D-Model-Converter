"""Doorway snapping for imported Map Studio rooms (modular maps Phase 3).

Rooms added from the catalog carry their LYT door hooks (room-local position
plus orientation). Snapping translates one room so a chosen door hook lines
up exactly with a chosen door hook on another room, so entrances meet. KOTOR
LYT rooms have no rotation, so this is a translation-only align — the hooks
should already face opposite directions for the doorway to read correctly,
which the report flags when they do not.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

Vec3 = tuple[float, float, float]
Vec4 = tuple[float, float, float, float]


@dataclass(frozen=True)
class RoomDoorHook:
    """One room's doorway hook resolved into module/world coordinates."""

    room_resref: str
    door: str
    world_position: Vec3
    facing_radians: float
    local_position: Vec3
    orientation: Vec4


@dataclass(frozen=True)
class RoomSnapResult:
    """Outcome of aligning one room's door hook onto another's."""

    project: Any
    translation: Vec3
    source_hook: RoomDoorHook
    target_hook: RoomDoorHook
    facing_delta_degrees: float
    opposed: bool
    warnings: tuple[str, ...] = ()


def _room_position(room: Any) -> Vec3:
    values = tuple(getattr(room, "position", ()) or ())
    if len(values) < 3:
        return (0.0, 0.0, 0.0)
    return (float(values[0]), float(values[1]), float(values[2]))


def _facing_from_quaternion(orientation: Any) -> float:
    values = tuple(float(v) for v in tuple(orientation or ())[:4]) or (0.0, 0.0, 0.0, 1.0)
    if len(values) < 4:
        values = (0.0, 0.0, 0.0, 1.0)
    x, y, z, w = values
    siny_cosp = 2.0 * ((w * z) + (x * y))
    cosy_cosp = 1.0 - 2.0 * ((y * y) + (z * z))
    return math.atan2(siny_cosp, cosy_cosp)


def authored_room_door_hooks(room: Any) -> tuple[RoomDoorHook, ...]:
    """Return a room's stored door hooks in module/world coordinates."""

    normalise = getattr(room, "normalised_resref", None)
    room_resref = str(normalise() if callable(normalise) else getattr(room, "room_resref", "") or "")
    metadata = dict(getattr(room, "metadata", {}) or {})
    stored = metadata.get("connection_points") or []
    origin = _room_position(room)
    hooks: list[RoomDoorHook] = []
    for entry in stored:
        if not isinstance(entry, dict):
            continue
        local = tuple(float(v) for v in tuple(entry.get("local_position", (0.0, 0.0, 0.0)))[:3])
        if len(local) < 3:
            continue
        orientation = tuple(float(v) for v in tuple(entry.get("orientation", (0.0, 0.0, 0.0, 1.0)))[:4])
        if len(orientation) < 4:
            orientation = (0.0, 0.0, 0.0, 1.0)
        hooks.append(
            RoomDoorHook(
                room_resref=room_resref,
                door=str(entry.get("door", "") or ""),
                world_position=(origin[0] + local[0], origin[1] + local[1], origin[2] + local[2]),
                facing_radians=_facing_from_quaternion(orientation),
                local_position=local,  # type: ignore[arg-type]
                orientation=orientation,  # type: ignore[arg-type]
            )
        )
    return tuple(hooks)


def _find_room(project: Any, resref: str) -> Any | None:
    wanted = str(resref or "").strip().lower()
    for room in tuple(getattr(project, "rooms", ()) or ()):
        normalise = getattr(room, "normalised_resref", None)
        current = str(normalise() if callable(normalise) else getattr(room, "room_resref", "") or "").strip().lower()
        if current == wanted:
            return room
    return None


def _hook_named(hooks: tuple[RoomDoorHook, ...], door: str) -> RoomDoorHook | None:
    wanted = str(door or "").strip().lower()
    for hook in hooks:
        if hook.door.strip().lower() == wanted:
            return hook
    return hooks[0] if hooks and not wanted else None


def snap_authored_room_to_room(
    project: Any,
    *,
    source_room_resref: str,
    source_door: str,
    target_room_resref: str,
    target_door: str,
) -> RoomSnapResult:
    """Translate the source room so its door hook meets the target's.

    Returns a :class:`RoomSnapResult` with the applied translation and a
    facing check. Raises ``ValueError`` when a room or hook is missing.
    """

    if str(source_room_resref).strip().lower() == str(target_room_resref).strip().lower():
        raise ValueError("Choose two different rooms to snap together.")
    source_room = _find_room(project, source_room_resref)
    target_room = _find_room(project, target_room_resref)
    if source_room is None or target_room is None:
        raise ValueError("Both rooms must exist in the current module.")
    source_hooks = authored_room_door_hooks(source_room)
    target_hooks = authored_room_door_hooks(target_room)
    if not source_hooks:
        raise ValueError(f"Room {source_room_resref} has no recorded doorway hooks to snap from.")
    if not target_hooks:
        raise ValueError(f"Room {target_room_resref} has no recorded doorway hooks to snap to.")
    source_hook = _hook_named(source_hooks, source_door)
    target_hook = _hook_named(target_hooks, target_door)
    if source_hook is None:
        raise ValueError(f"Room {source_room_resref} has no door hook named {source_door!r}.")
    if target_hook is None:
        raise ValueError(f"Room {target_room_resref} has no door hook named {target_door!r}.")

    translation = (
        target_hook.world_position[0] - source_hook.world_position[0],
        target_hook.world_position[1] - source_hook.world_position[1],
        target_hook.world_position[2] - source_hook.world_position[2],
    )
    origin = _room_position(source_room)
    moved_room = replace(source_room, position=(origin[0] + translation[0], origin[1] + translation[1], origin[2] + translation[2]))
    rooms = tuple(moved_room if room is source_room else room for room in tuple(project.rooms or ()))
    updated_project = replace(project, rooms=rooms)

    # Doorways read correctly when the two hooks face opposite directions.
    delta = math.degrees(abs(math.atan2(
        math.sin(source_hook.facing_radians - target_hook.facing_radians),
        math.cos(source_hook.facing_radians - target_hook.facing_radians),
    )))
    opposed = abs(delta - 180.0) <= 20.0
    warnings: list[str] = []
    if not opposed:
        warnings.append(
            f"Door hooks meet at the same point but face {delta:.0f} deg apart (KOTOR rooms cannot be rotated); "
            "the doorways may not line up visually. Pick hooks that face each other."
        )
    return RoomSnapResult(
        project=updated_project,
        translation=translation,
        source_hook=source_hook,
        target_hook=target_hook,
        facing_delta_degrees=delta,
        opposed=opposed,
        warnings=tuple(warnings),
    )


__all__ = [
    "RoomDoorHook",
    "RoomSnapResult",
    "authored_room_door_hooks",
    "snap_authored_room_to_room",
]
