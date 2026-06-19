"""Headless authored module layout compiler for Map Studio.

Map Studio rooms should compile to Odyssey LYT/VIS data through a reusable
service instead of each workflow assembling layout text by hand.  This module
keeps room placement and visibility policy Qt-free and testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .authored_module_project import AuthoredModuleProject, AuthoredRoomSpec, normalise_resref
from .authored_module_objects import normalise_resource_resref
from .module_format import LYTLayout, LYTDoorHook, LYTRoom, VISData


@dataclass(frozen=True)
class AuthoredModuleLayoutValidation:
    """Validation summary for authored room layout intent."""

    ok: bool
    warnings: tuple[str, ...] = ()
    blocking_issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuthoredModuleLayout:
    """Compiled LYT/VIS plus provenance for an authored module layout."""

    lyt: LYTLayout
    vis: VISData
    room_resrefs: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    metadata: dict[str, object] | None = None


def _room_name(room: AuthoredRoomSpec) -> str:
    return normalise_resref(room.room_resref)


def _door_hook_name(template_resref: str, tag: str) -> str:
    return normalise_resource_resref(tag) or normalise_resource_resref(template_resref)


def _bearing_to_quaternion_z(bearing: float) -> tuple[float, float, float, float]:
    half = float(bearing) * 0.5
    return (0.0, 0.0, math.sin(half), math.cos(half))


def validate_authored_module_layout(project: AuthoredModuleProject) -> AuthoredModuleLayoutValidation:
    """Validate room resrefs, positions, and VIS references."""

    warnings: list[str] = []
    blocking: list[str] = []
    room_names = [_room_name(room) for room in project.rooms]
    room_set = {name for name in room_names if name}
    if not room_names:
        blocking.append("Authored module layout requires at least one room.")
    if len(room_set) != len([name for name in room_names if name]):
        blocking.append("Authored module layout contains duplicate room resrefs.")
    for index, room in enumerate(project.rooms):
        name = _room_name(room)
        if not name:
            blocking.append(f"Room {index + 1} has no valid room resref.")
        if len(room.position) != 3:
            blocking.append(f"Room {name or index + 1} requires an XYZ layout position.")
            continue
        try:
            tuple(float(value) for value in room.position)
        except Exception:
            blocking.append(f"Room {name or index + 1} has a non-numeric layout position.")
        for target in room.visible_rooms:
            target_name = normalise_resref(target)
            if not target_name:
                continue
            if target_name not in room_set:
                blocking.append(f"Room {name or index + 1} references missing visible room {target_name}.")
    if len(room_set) > 1 and not any(room.visible_rooms for room in project.rooms):
        warnings.append("Multi-room layout has no explicit VIS links; each room will see only itself.")
    seen_door_hooks: set[str] = set()
    for index, door in enumerate(project.placements.doors):
        hook_name = _door_hook_name(door.template_resref, door.tag)
        if not hook_name:
            blocking.append(f"Door hook {index + 1} requires a template resref or tag.")
            continue
        if hook_name in seen_door_hooks:
            blocking.append(f"Duplicate authored door hook name: {hook_name}")
        seen_door_hooks.add(hook_name)
        if len(door.position) != 3:
            blocking.append(f"Door hook {hook_name} requires an XYZ layout position.")
        else:
            try:
                tuple(float(value) for value in door.position)
            except Exception:
                blocking.append(f"Door hook {hook_name} has a non-numeric layout position.")
        try:
            bearing = float(door.bearing)
        except Exception:
            blocking.append(f"Door hook {hook_name} has a non-numeric bearing.")
            continue
        if not math.isfinite(bearing):
            blocking.append(f"Door hook {hook_name} has a non-finite bearing.")
    return AuthoredModuleLayoutValidation(
        ok=not blocking,
        warnings=tuple(warnings),
        blocking_issues=tuple(blocking),
    )


def compile_authored_module_layout(project: AuthoredModuleProject) -> AuthoredModuleLayout:
    """Compile authored room specs into LYT and VIS data."""

    validation = validate_authored_module_layout(project)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    lyt = LYTLayout()
    visibility: dict[str, list[str]] = {}
    room_names: list[str] = []
    for room in project.rooms:
        room_name = _room_name(room)
        room_names.append(room_name)
        x, y, z = (float(value) for value in room.position)
        lyt.rooms.append(LYTRoom(room_name, x, y, z))
        visible = [normalise_resref(target) for target in room.visible_rooms if normalise_resref(target)]
        visibility[room_name] = visible or [room_name]
    for door in project.placements.doors:
        qx, qy, qz, qw = _bearing_to_quaternion_z(float(door.bearing))
        lyt.doorhooks.append(
            LYTDoorHook(
                _door_hook_name(door.template_resref, door.tag),
                float(door.position[0]),
                float(door.position[1]),
                float(door.position[2]),
                qx,
                qy,
                qz,
                qw,
            )
        )
    return AuthoredModuleLayout(
        lyt=lyt,
        vis=VISData(visibility=visibility),
        room_resrefs=tuple(room_names),
        warnings=validation.warnings,
        metadata={
            "source": "src.core.modules.authored_module_layout",
            "room_count": len(room_names),
            "door_hook_count": len(lyt.doorhooks),
            "vis_entry_count": len(visibility),
        },
    )


__all__ = [
    "AuthoredModuleLayout",
    "AuthoredModuleLayoutValidation",
    "compile_authored_module_layout",
    "validate_authored_module_layout",
]
