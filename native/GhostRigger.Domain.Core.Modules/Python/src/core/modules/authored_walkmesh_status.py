"""Modder-facing walkmesh status summaries for authored Map Studio modules."""

from __future__ import annotations

from dataclasses import dataclass

from .authored_module_project import AuthoredModuleProject
from .authored_room_composition import AuthoredRoomComposition
from .authored_room_floorplan import FloorPlanRoomPrimitive
from .authored_room_geometry import RectangularRoomPrimitive
from .authored_terrain_builder import TerrainHeightfieldPrimitive
from .authored_terrain_walkability_overlay import authored_terrain_walkability_overlay_for_project
from .authored_walkmesh_surfaces import is_walkable_walkmesh_surface, resolve_walkmesh_surface_id, walkmesh_surface_name


@dataclass(frozen=True)
class AuthoredWalkmeshStatus:
    """Read-only status for the Map Studio Walkmesh tab."""

    ready: bool
    room_count: int = 0
    terrain_room_count: int = 0
    walkable_triangle_count: int = 0
    non_walk_triangle_count: int = 0
    max_slope_degrees: float = 0.0
    summary: str = "Walkmesh: no authored module loaded."
    next_action: str = "Create a starter room or terrain patch before inspecting walkmesh."
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuthoredWalkmeshRoomSurfaceChoice:
    """UI-ready room surface row for the Map Studio Walkmesh tab."""

    room_resref: str
    label: str
    primitive_type: str
    texture: str
    floor_surface_id: int
    floor_surface_name: str
    walkable: bool
    room_index: int


def _room_surface_payload(primitive: object) -> tuple[str, str, int] | None:
    if isinstance(primitive, FloorPlanRoomPrimitive):
        return ("floor-plan extrusion", str(primitive.material.texture or ""), resolve_walkmesh_surface_id(primitive.floor_surface_id))
    if isinstance(primitive, RectangularRoomPrimitive):
        return ("rectangular room", str(primitive.texture or ""), resolve_walkmesh_surface_id(primitive.floor_surface_id))
    if isinstance(primitive, TerrainHeightfieldPrimitive):
        return ("terrain heightfield", str(primitive.material.texture or ""), resolve_walkmesh_surface_id(primitive.floor_surface_id))
    if isinstance(primitive, AuthoredRoomComposition):
        return ("composed room", str(primitive.floor.material.texture or ""), resolve_walkmesh_surface_id(primitive.floor.surface_id))
    return None


def authored_walkmesh_room_surface_choices(project: AuthoredModuleProject) -> tuple[AuthoredWalkmeshRoomSurfaceChoice, ...]:
    """Return authored rooms whose generated WOK floor surface can be edited."""

    choices: list[AuthoredWalkmeshRoomSurfaceChoice] = []
    for index, room in enumerate(tuple(project.rooms or ())):
        payload = _room_surface_payload(room.primitive)
        if payload is None:
            continue
        primitive_type, texture, surface_id = payload
        name = walkmesh_surface_name(surface_id)
        walkable = is_walkable_walkmesh_surface(surface_id)
        resref = room.normalised_resref()
        state = "walkable" if walkable else "not walkable"
        choices.append(
            AuthoredWalkmeshRoomSurfaceChoice(
                room_resref=resref,
                label=f"{resref} - {primitive_type} - {surface_id} {name} ({state})",
                primitive_type=primitive_type,
                texture=texture,
                floor_surface_id=surface_id,
                floor_surface_name=name,
                walkable=walkable,
                room_index=index,
            )
        )
    return tuple(choices)


def authored_walkmesh_status_for_project(project: AuthoredModuleProject) -> AuthoredWalkmeshStatus:
    """Build a concise walkmesh readiness summary from authored module intent."""

    rooms = tuple(project.rooms or ())
    room_count = len(rooms)
    if room_count <= 0:
        return AuthoredWalkmeshStatus(
            ready=False,
            summary="Walkmesh: no authored rooms exist yet.",
            next_action="Create a starter room, corridor, blockout, or terrain patch before generating WOK output.",
        )

    terrain_room_count = sum(1 for room in rooms if isinstance(room.primitive, TerrainHeightfieldPrimitive))
    overlay = authored_terrain_walkability_overlay_for_project(project)
    if terrain_room_count > 0:
        walkable = int(overlay.walkable_triangle_count)
        non_walk = int(overlay.non_walk_triangle_count)
        total = walkable + non_walk
        ready = total > 0 and walkable > 0
        if ready:
            next_action = "Inspect green/orange terrain overlay, fix steep samples if needed, then validate before staging."
        else:
            next_action = "Adjust terrain dimensions or samples so the generated terrain WOK has walkable faces."
        return AuthoredWalkmeshStatus(
            ready=ready,
            room_count=room_count,
            terrain_room_count=terrain_room_count,
            walkable_triangle_count=walkable,
            non_walk_triangle_count=non_walk,
            max_slope_degrees=float(overlay.max_slope_degrees),
            summary=(
                f"Walkmesh: {terrain_room_count} terrain room(s), {walkable} walkable triangle(s), "
                f"{non_walk} blocked triangle(s), max slope {float(overlay.max_slope_degrees):.1f} deg."
            ),
            next_action=next_action,
            warnings=tuple(overlay.warnings),
        )

    return AuthoredWalkmeshStatus(
        ready=True,
        room_count=room_count,
        terrain_room_count=0,
        summary=(
            f"Walkmesh: {room_count} authored flat/composition room(s) have generated WOK intent. "
            "Use Room Material + Walkmesh or Primitive Material + Surface to assign face behavior."
        ),
        next_action="Validate the module to confirm player start, placements, doors, and triggers sit on walkable faces.",
    )


__all__ = [
    "AuthoredWalkmeshRoomSurfaceChoice",
    "AuthoredWalkmeshStatus",
    "authored_walkmesh_room_surface_choices",
    "authored_walkmesh_status_for_project",
]
