"""Project-level room shaping operations for Map Studio.

The low-level floor-plan module owns polygon math.  This module owns the
authored-module operation policy: find a room in an ``AuthoredModuleProject``,
convert compatible starter primitives to floor-plan intent, apply the operation,
and return a new project that can be saved back into KMAP.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .authored_module_project import AuthoredModuleProject, AuthoredRoomSpec, normalise_resref
from .authored_module_objects import AuthoredGameplayPlacement
from .authored_room_composition import AuthoredRoomComposition, PlacedRoomPrimitive, PrimitiveTransform
from .authored_room_floorplan import (
    FloorPlanBevelOperation,
    FloorPlanInsetOperation,
    FloorPlanRectangularCutOperation,
    FloorPlanRoomPrimitive,
    apply_floor_plan_bevel,
    apply_floor_plan_inset,
    apply_floor_plan_rectangular_cut,
)
from .authored_room_geometry import RectangularRoomPrimitive
from .authored_room_primitives import PrimitiveMaterial


def _rectangular_to_floor_plan(primitive: RectangularRoomPrimitive, room_resref: str) -> FloorPlanRoomPrimitive:
    half_w = float(primitive.width) * 0.5
    half_d = float(primitive.depth) * 0.5
    return FloorPlanRoomPrimitive(
        room_resref=normalise_resref(room_resref or primitive.room_resref),
        points=((-half_w, -half_d), (half_w, -half_d), (half_w, half_d), (-half_w, half_d)),
        wall_height=float(primitive.wall_height),
        floor_surface_id=primitive.floor_surface_id,
        material=PrimitiveMaterial(
            texture=str(primitive.texture or "default"),
            metadata={
                "source": "map_studio:rectangular_conversion",
                "include_doorway_marker": bool(primitive.include_doorway_marker),
            },
        ),
        include_walls=True,
        metadata={
            "source": "map_studio:rectangular_conversion",
            "converted_from": "rectangular",
            "include_doorway_marker": bool(primitive.include_doorway_marker),
        },
    )


def _floor_plan_for_room(room: AuthoredRoomSpec) -> FloorPlanRoomPrimitive:
    primitive = room.primitive
    if isinstance(primitive, FloorPlanRoomPrimitive):
        return primitive
    if isinstance(primitive, RectangularRoomPrimitive):
        return _rectangular_to_floor_plan(primitive, room.room_resref)
    raise ValueError(f"Room {room.room_resref} does not have a floor-plan-compatible primitive.")


def _target_room_index(project: AuthoredModuleProject, room_resref: str = "") -> int:
    target = normalise_resref(room_resref)
    if not project.rooms:
        raise ValueError("Authored room operation requires at least one room.")
    if not target:
        return 0
    for index, room in enumerate(project.rooms):
        if normalise_resref(room.room_resref) == target:
            return index
    raise ValueError(f"Authored room operation could not find room '{room_resref}'.")


def _all_room_names(rooms: tuple[AuthoredRoomSpec, ...]) -> tuple[str, ...]:
    return tuple(normalise_resref(room.room_resref) for room in rooms if normalise_resref(room.room_resref))


def _replace_rooms(
    project: AuthoredModuleProject,
    rooms: tuple[AuthoredRoomSpec, ...],
    *,
    operation: str,
    placements: AuthoredGameplayPlacement | None = None,
) -> AuthoredModuleProject:
    return replace(
        project,
        rooms=rooms,
        placements=placements or project.placements,
        notes=tuple(project.notes)
        + (
            f"Applied Map Studio room operation: {operation}.",
        ),
        extra={
            **dict(project.extra),
            "last_room_operation": operation,
        },
    )


def _composition_for_room(room: AuthoredRoomSpec) -> AuthoredRoomComposition:
    if isinstance(room.primitive, AuthoredRoomComposition):
        return room.primitive
    if room.composition is not None:
        return room.composition
    raise ValueError(f"Room {room.room_resref} does not have an editable primitive composition.")


def _primitive_name(primitive: Any) -> str:
    if isinstance(primitive, PlacedRoomPrimitive):
        return str(primitive.name or getattr(primitive.primitive, "name", "") or "").strip()
    return str(getattr(primitive, "name", "") or "").strip()


def _vec3_or_existing(value: Any, existing: tuple[float, float, float]) -> tuple[float, float, float]:
    if value is None:
        return existing
    if isinstance(value, dict):
        value = (value.get("x"), value.get("y"), value.get("z"))
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        raise ValueError("Primitive transforms require three numeric X/Y/Z values.")
    return (float(value[0]), float(value[1]), float(value[2]))


def _updated_transform(
    existing: PrimitiveTransform,
    *,
    translation: Any = None,
    rotation_degrees_z: float | None = None,
    scale: Any = None,
    pivot: Any = None,
) -> PrimitiveTransform:
    next_scale = _vec3_or_existing(scale, existing.scale)
    if any(float(value) <= 0.0 for value in next_scale):
        raise ValueError("Primitive transform scale values must be positive.")
    return PrimitiveTransform(
        translation=_vec3_or_existing(translation, existing.translation),
        rotation_degrees_z=float(existing.rotation_degrees_z if rotation_degrees_z is None else rotation_degrees_z),
        scale=next_scale,
        pivot=_vec3_or_existing(pivot, existing.pivot),
    )


def _set_composition_primitive_transform(
    composition: AuthoredRoomComposition,
    *,
    primitive_name: str,
    translation: Any = None,
    rotation_degrees_z: float | None = None,
    scale: Any = None,
    pivot: Any = None,
) -> AuthoredRoomComposition:
    target = str(primitive_name or "").strip()
    if not target:
        raise ValueError("Primitive transform operation requires a primitive name.")
    updated_primitives = []
    found = False
    for primitive in tuple(composition.primitives or ()):
        name = _primitive_name(primitive)
        if name != target:
            updated_primitives.append(primitive)
            continue
        found = True
        if isinstance(primitive, PlacedRoomPrimitive):
            updated_primitives.append(
                replace(
                    primitive,
                    transform=_updated_transform(
                        primitive.transform,
                        translation=translation,
                        rotation_degrees_z=rotation_degrees_z,
                        scale=scale,
                        pivot=pivot,
                    ),
                )
            )
        else:
            updated_primitives.append(
                PlacedRoomPrimitive(
                    primitive=primitive,
                    name=name,
                    transform=_updated_transform(
                        PrimitiveTransform(),
                        translation=translation,
                        rotation_degrees_z=rotation_degrees_z,
                        scale=scale,
                        pivot=pivot,
                    ),
                )
            )
    if not found:
        known = ", ".join(_primitive_name(item) for item in tuple(composition.primitives or ()) if _primitive_name(item))
        raise ValueError(f"Room {composition.room_resref} has no primitive named '{primitive_name}'. Known primitives: {known or '(none)'}.")
    return replace(
        composition,
        primitives=tuple(updated_primitives),
        metadata={
            **dict(composition.metadata),
            "last_operation": "set_primitive_transform",
            "last_transformed_primitive": target,
        },
    )


def set_authored_room_composition_primitive_transform(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
    translation: Any = None,
    rotation_degrees_z: float | None = None,
    scale: Any = None,
    pivot: Any = None,
) -> AuthoredModuleProject:
    """Set one primitive instance transform inside an authored composition room."""

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    composition = _set_composition_primitive_transform(
        _composition_for_room(room),
        primitive_name=primitive_name,
        translation=translation,
        rotation_degrees_z=rotation_degrees_z,
        scale=scale,
        pivot=pivot,
    )
    updated = replace(
        room,
        primitive=composition,
        composition=None,
        metadata={
            **dict(room.metadata),
            "primitive": "authored_room_composition",
            "last_operation": "set_primitive_transform",
            "last_transformed_primitive": str(primitive_name or "").strip(),
        },
    )
    rooms = tuple(project.rooms[:index] + (updated,) + project.rooms[index + 1 :])
    return _replace_rooms(project, rooms, operation="set_primitive_transform")


def apply_authored_floor_plan_inset(
    project: AuthoredModuleProject,
    *,
    distance: float,
    room_resref: str = "",
) -> AuthoredModuleProject:
    """Inset one authored room footprint and return updated project intent."""

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    primitive = apply_floor_plan_inset(
        _floor_plan_for_room(room),
        FloorPlanInsetOperation(distance=float(distance), room_resref=room.room_resref, metadata={"source": "map_studio:project_operation"}),
    )
    updated = replace(room, primitive=primitive, composition=None, metadata={**dict(room.metadata), "last_operation": "inset"})
    rooms = tuple(project.rooms[:index] + (updated,) + project.rooms[index + 1 :])
    return _replace_rooms(project, rooms, operation="inset")


def apply_authored_floor_plan_bevel(
    project: AuthoredModuleProject,
    *,
    distance: float,
    room_resref: str = "",
) -> AuthoredModuleProject:
    """Bevel one authored room footprint and return updated project intent."""

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    primitive = apply_floor_plan_bevel(
        _floor_plan_for_room(room),
        FloorPlanBevelOperation(distance=float(distance), room_resref=room.room_resref, metadata={"source": "map_studio:project_operation"}),
    )
    updated = replace(room, primitive=primitive, composition=None, metadata={**dict(room.metadata), "last_operation": "bevel"})
    rooms = tuple(project.rooms[:index] + (updated,) + project.rooms[index + 1 :])
    return _replace_rooms(project, rooms, operation="bevel")


def _safe_anchor_for_piece(piece: FloorPlanRoomPrimitive) -> tuple[float, float, float]:
    xs = [float(point[0]) for point in piece.points]
    ys = [float(point[1]) for point in piece.points]
    return ((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, float(piece.z))


def _offset_anchor(anchor: tuple[float, float, float], dx: float, dy: float) -> tuple[float, float, float]:
    return (anchor[0] + float(dx), anchor[1] + float(dy), anchor[2])


def _placements_for_cut(project: AuthoredModuleProject, first_piece: FloorPlanRoomPrimitive) -> AuthoredGameplayPlacement:
    anchor = _safe_anchor_for_piece(first_piece)
    return replace(
        project.placements,
        entry_point=replace(project.placements.entry_point, position=anchor),
        placeables=tuple(replace(item, position=_offset_anchor(anchor, 0.5, 0.5)) for item in project.placements.placeables),
        waypoints=tuple(replace(item, position=anchor) for item in project.placements.waypoints),
        metadata={
            **dict(project.placements.metadata),
            "last_room_operation": "rectangular_cut",
            "placement_repaired_after_cut": True,
        },
    )


def apply_authored_floor_plan_rectangular_cut(
    project: AuthoredModuleProject,
    *,
    center: tuple[float, float],
    size: tuple[float, float],
    room_resref: str = "",
    room_resref_prefix: str | None = None,
) -> AuthoredModuleProject:
    """Apply a rectangular boolean difference and split the room into pieces."""

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    primitive = _floor_plan_for_room(room)
    prefix = room_resref_prefix or f"{normalise_resref(room.room_resref)}_cut"
    pieces = apply_floor_plan_rectangular_cut(
        primitive,
        FloorPlanRectangularCutOperation(
            center=(float(center[0]), float(center[1])),
            size=(float(size[0]), float(size[1])),
            room_resref_prefix=prefix,
            metadata={"source": "map_studio:project_operation"},
        ),
    )
    piece_rooms = tuple(
        replace(
            room,
            room_resref=piece.room_resref,
            primitive=piece,
            composition=None,
            visible_rooms=(),
            metadata={
                **dict(room.metadata),
                "last_operation": "rectangular_cut",
                "cut_piece_role": piece.metadata.get("piece_role", ""),
            },
        )
        for piece in pieces
    )
    rooms = tuple(project.rooms[:index] + piece_rooms + project.rooms[index + 1 :])
    visible = _all_room_names(rooms)
    rooms = tuple(replace(item, visible_rooms=visible) for item in rooms)
    return _replace_rooms(project, rooms, operation="rectangular_cut", placements=_placements_for_cut(project, pieces[0]))


def move_authored_floor_plan_point(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    point_index: int,
    world_position: tuple[float, float, float] | tuple[float, float],
) -> AuthoredModuleProject:
    """Move one editable floor-plan vertex using a world-space viewport point."""

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    primitive = _floor_plan_for_room(room)
    points = list(tuple(primitive.points or ()))
    vertex_index = int(point_index)
    if vertex_index < 0 or vertex_index >= len(points):
        raise ValueError(f"Room {room.room_resref} has no outline point {point_index}.")
    position = tuple(world_position)
    if len(position) < 2:
        raise ValueError("Map Studio room point edits require an X/Y position.")
    room_offset = tuple(room.position or (0.0, 0.0, 0.0))
    if len(room_offset) < 3:
        room_offset = (0.0, 0.0, 0.0)
    local_x = float(position[0]) - float(room_offset[0])
    local_y = float(position[1]) - float(room_offset[1])
    points[vertex_index] = (local_x, local_y)
    updated_primitive = replace(
        primitive,
        points=tuple(points),
        metadata={
            **dict(primitive.metadata),
            "last_vertex_edit": vertex_index,
            "source": "map_studio:viewport_outline_drag",
        },
    )
    updated_room = replace(
        room,
        primitive=updated_primitive,
        composition=None,
        metadata={
            **dict(room.metadata),
            "last_operation": "move_floor_plan_point",
            "last_vertex_edit": vertex_index,
        },
    )
    rooms = tuple(project.rooms[:index] + (updated_room,) + project.rooms[index + 1 :])
    return _replace_rooms(project, rooms, operation="move_floor_plan_point")


def apply_authored_floor_plan_operation(project: AuthoredModuleProject, operation: str, **kwargs: Any) -> AuthoredModuleProject:
    """Dispatch a named Map Studio room operation."""

    op = str(operation or "").strip().lower()
    if op == "inset":
        return apply_authored_floor_plan_inset(project, distance=float(kwargs.get("distance", 0.25)), room_resref=str(kwargs.get("room_resref", "")))
    if op == "bevel":
        return apply_authored_floor_plan_bevel(project, distance=float(kwargs.get("distance", 0.25)), room_resref=str(kwargs.get("room_resref", "")))
    if op in {"rectangular_cut", "cut"}:
        return apply_authored_floor_plan_rectangular_cut(
            project,
            center=tuple(kwargs.get("center", (0.0, 0.0))),  # type: ignore[arg-type]
            size=tuple(kwargs.get("size", (1.0, 1.0))),  # type: ignore[arg-type]
            room_resref=str(kwargs.get("room_resref", "")),
            room_resref_prefix=kwargs.get("room_resref_prefix"),
        )
    raise ValueError(f"Unsupported authored floor-plan operation: {operation}.")


__all__ = [
    "apply_authored_floor_plan_bevel",
    "apply_authored_floor_plan_inset",
    "apply_authored_floor_plan_operation",
    "apply_authored_floor_plan_rectangular_cut",
    "move_authored_floor_plan_point",
    "set_authored_room_composition_primitive_transform",
]
