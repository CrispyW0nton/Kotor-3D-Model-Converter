"""Modder-facing walkmesh status summaries for authored Map Studio modules."""

from __future__ import annotations

from dataclasses import dataclass

from .authored_module_project import AuthoredModuleProject, compile_authored_room_spec
from .authored_room_composition import AuthoredRoomComposition, PlacedRoomPrimitive
from .authored_room_floorplan import FloorPlanRoomPrimitive
from .authored_room_geometry import RectangularRoomPrimitive
from .authored_terrain_builder import TerrainHeightfieldPrimitive
from .authored_terrain_walkability_overlay import authored_terrain_walkability_overlay_for_project
from .authored_walkmesh_audit import AuthoredWalkmeshAudit, audit_authored_wok
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
    walkable_component_count: int = 0
    disconnected_walkmesh_room_count: int = 0
    invalid_face_count: int = 0
    degenerate_face_count: int = 0
    non_manifold_edge_count: int = 0
    open_edge_count: int = 0
    steep_walkable_face_count: int = 0
    summary: str = "Walkmesh: no authored module loaded."
    next_action: str = "Create a starter room or terrain patch before inspecting walkmesh."
    warnings: tuple[str, ...] = ()
    blocking_messages: tuple[str, ...] = ()


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
        floor = primitive.floor.primitive if isinstance(primitive.floor, PlacedRoomPrimitive) else primitive.floor
        return ("composed room", str(floor.material.texture or ""), resolve_walkmesh_surface_id(floor.surface_id))
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


def _room_walkmesh_audits(project: AuthoredModuleProject) -> tuple[AuthoredWalkmeshAudit, ...]:
    audits: list[AuthoredWalkmeshAudit] = []
    for room in tuple(project.rooms or ()):
        resref = room.normalised_resref()
        try:
            geometry = compile_authored_room_spec(room)
        except Exception as exc:
            audits.append(
                AuthoredWalkmeshAudit(
                    room_resref=resref,
                    ready=False,
                    blocking_messages=(f"Room {resref or '(unnamed room)'} generated WOK could not compile: {exc}",),
                )
            )
            continue
        audits.append(audit_authored_wok(resref, geometry.wok))
    return tuple(audits)


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
    audits = _room_walkmesh_audits(project)
    walkable = sum(audit.walkable_face_count for audit in audits)
    non_walk = sum(audit.non_walk_face_count for audit in audits)
    component_count = sum(audit.walkable_component_count for audit in audits)
    disconnected_rooms = sum(1 for audit in audits if audit.walkable_component_count > 1)
    invalid_faces = sum(audit.invalid_face_count for audit in audits)
    degenerate_faces = sum(audit.degenerate_face_count for audit in audits)
    non_manifold_edges = sum(audit.non_manifold_edge_count for audit in audits)
    open_edges = sum(audit.open_edge_count for audit in audits)
    steep_walkable_faces = sum(audit.steep_walkable_face_count for audit in audits)
    max_audit_slope = max((float(audit.max_walkable_slope_degrees) for audit in audits), default=0.0)
    audit_warnings = tuple(warning for audit in audits for warning in audit.warnings)
    audit_blocking = tuple(message for audit in audits for message in audit.blocking_messages)
    overlay = authored_terrain_walkability_overlay_for_project(project)
    overlay_blocking = tuple(
        validation.message
        for validation in tuple(getattr(overlay, "room_validations", ()) or ())
        if str(getattr(validation, "state", "") or "") == "invalid"
    )
    if terrain_room_count > 0:
        total = walkable + non_walk
        ready = total > 0 and walkable > 0 and not audit_blocking and not overlay_blocking
        if ready:
            next_action = "Inspect the green validated WOK overlay, fix steep samples if needed, then stage for game proof."
        else:
            next_action = "Fix the red WOK overlay blockers, disconnected islands, invalid faces, missing perimeter, or terrain samples before staging."
        return AuthoredWalkmeshStatus(
            ready=ready,
            room_count=room_count,
            terrain_room_count=terrain_room_count,
            walkable_triangle_count=walkable,
            non_walk_triangle_count=non_walk,
            max_slope_degrees=float(overlay.max_slope_degrees),
            walkable_component_count=component_count,
            disconnected_walkmesh_room_count=disconnected_rooms,
            invalid_face_count=invalid_faces,
            degenerate_face_count=degenerate_faces,
            non_manifold_edge_count=non_manifold_edges,
            open_edge_count=open_edges,
            steep_walkable_face_count=steep_walkable_faces,
            summary=(
                f"Walkmesh: {terrain_room_count} terrain room(s), {walkable} walkable triangle(s), "
                f"{non_walk} blocked triangle(s), {component_count} walkable island(s), "
                f"max slope {float(overlay.max_slope_degrees):.1f} deg."
            ),
            next_action=next_action,
            warnings=tuple(overlay.warnings) + audit_warnings,
            blocking_messages=audit_blocking + overlay_blocking,
        )

    ready = walkable > 0 and not audit_blocking
    return AuthoredWalkmeshStatus(
        ready=ready,
        room_count=room_count,
        terrain_room_count=0,
        walkable_triangle_count=walkable,
        non_walk_triangle_count=non_walk,
        max_slope_degrees=max_audit_slope,
        walkable_component_count=component_count,
        disconnected_walkmesh_room_count=disconnected_rooms,
        invalid_face_count=invalid_faces,
        degenerate_face_count=degenerate_faces,
        non_manifold_edge_count=non_manifold_edges,
        open_edge_count=open_edges,
        steep_walkable_face_count=steep_walkable_faces,
        summary=(
            f"Walkmesh: {room_count} authored flat/composition room(s), {walkable} walkable triangle(s), "
            f"{component_count} walkable island(s). Use Room Material + Walkmesh or Primitive Material + Surface "
            "to assign face behavior."
        ),
        next_action=(
            "Validate the module to confirm player start, placements, doors, and triggers sit on walkable faces."
            if ready
            else "Fix disconnected, degenerate, non-manifold, or missing WOK faces before export/game proof."
        ),
        warnings=audit_warnings,
        blocking_messages=audit_blocking,
    )


__all__ = [
    "AuthoredWalkmeshRoomSurfaceChoice",
    "AuthoredWalkmeshStatus",
    "authored_walkmesh_room_surface_choices",
    "authored_walkmesh_status_for_project",
]
