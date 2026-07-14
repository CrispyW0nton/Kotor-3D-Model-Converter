"""Headless authored module layout compiler for Map Studio.

Map Studio rooms should compile to Odyssey LYT/VIS data through a reusable
service instead of each workflow assembling layout text by hand.  This module
keeps room placement and visibility policy Qt-free and testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .authored_module_project import AuthoredModuleProject, AuthoredRoomSpec, normalise_resref
from .authored_module_objects import normalise_resource_resref
from .authored_room_floorplan import FloorPlanRoomPrimitive, FloorPlanWallOpening, polygon_signed_area
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


@dataclass(frozen=True)
class AuthoredRoomConnectionHook:
    """One KMAP-persisted floor-plan opening usable as a room snap hook."""

    hook_id: str
    room_resref: str
    opening_name: str
    edge_index: int
    position: tuple[float, float, float]
    outward: tuple[float, float]
    width: float
    height: float
    bottom: float
    opening_kind: str = "door"
    external: bool = False
    connected_room_resref: str = ""
    connected_opening_name: str = ""

    @property
    def passable(self) -> bool:
        return self.bottom <= 1.0e-5 and self.opening_kind not in {"window", "backdrop", "view"}

    @property
    def label(self) -> str:
        name = self.opening_name or f"edge {self.edge_index}"
        return f"{self.room_resref} — {name}"


@dataclass(frozen=True)
class AuthoredRoomConnection:
    """A spatially aligned pair of authored room-opening hooks."""

    first_hook_id: str
    second_hook_id: str
    distance: float
    facing_dot: float
    explicit: bool = False


@dataclass(frozen=True)
class AuthoredRoomConnectionAudit:
    """Map Studio room-connection health without claiming WOK game proof."""

    hooks: tuple[AuthoredRoomConnectionHook, ...] = ()
    connections: tuple[AuthoredRoomConnection, ...] = ()
    unconnected_hook_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.unconnected_hook_ids

    @property
    def summary(self) -> str:
        if not self.hooks:
            return "No authored floor-plan openings. Add doorway openings in Builder to create room connection hooks."
        return (
            f"Room connections: {len(self.connections)} connected pair(s), "
            f"{len(self.unconnected_hook_ids)} unconnected passable opening(s), {len(self.hooks)} total hook(s)."
        )


@dataclass(frozen=True)
class AuthoredRoomConnectionUpdate:
    """Result of aligning and persistently linking two authored openings."""

    project: AuthoredModuleProject
    source_hook: AuthoredRoomConnectionHook
    target_hook: AuthoredRoomConnectionHook
    rotation_degrees: float
    translation: tuple[float, float, float]
    summary: str


def _floor_plan_room_primitive(room: AuthoredRoomSpec) -> FloorPlanRoomPrimitive | None:
    primitive = room.primitive
    return primitive if isinstance(primitive, FloorPlanRoomPrimitive) else None


def _opening_kind(opening: FloorPlanWallOpening) -> str:
    metadata = dict(opening.metadata or {})
    kind = str(metadata.get("opening_kind") or metadata.get("kind") or "").strip().lower()
    if kind:
        return kind
    return "window" if float(opening.bottom) > 1.0e-5 else "door"


def _opening_hook(room: AuthoredRoomSpec, primitive: FloorPlanRoomPrimitive, opening: FloorPlanWallOpening) -> AuthoredRoomConnectionHook | None:
    points = tuple((float(x), float(y)) for x, y in primitive.points)
    if len(points) < 2:
        return None
    edge_index = int(opening.edge_index)
    if edge_index < 0 or edge_index >= len(points):
        return None
    start = points[edge_index]
    end = points[(edge_index + 1) % len(points)]
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    length = math.hypot(dx, dy)
    if length <= 1.0e-7:
        return None
    center_fraction = min(1.0, max(0.0, float(opening.center_fraction)))
    local_x = float(start[0]) + dx * center_fraction
    local_y = float(start[1]) + dy * center_fraction
    room_x, room_y, room_z = (float(value) for value in room.position)
    # A CCW polygon has its interior on the left side of each directed edge,
    # so the right-hand normal points outward. Reverse that rule for CW input.
    if polygon_signed_area(points) >= 0.0:
        outward = (dy / length, -dx / length)
    else:
        outward = (-dy / length, dx / length)
    metadata = dict(opening.metadata or {})
    room_resref = _room_name(room)
    opening_name = str(opening.name or "").strip() or f"edge_{edge_index}"
    return AuthoredRoomConnectionHook(
        hook_id=f"{room_resref}:{edge_index}:{opening_name.lower()}",
        room_resref=room_resref,
        opening_name=opening_name,
        edge_index=edge_index,
        position=(local_x + room_x, local_y + room_y, float(primitive.z) + room_z + float(opening.bottom)),
        outward=outward,
        width=float(opening.width),
        height=float(opening.height),
        bottom=float(opening.bottom),
        opening_kind=_opening_kind(opening),
        external=bool(metadata.get("external") or metadata.get("cross_module") or metadata.get("backdrop")),
        connected_room_resref=normalise_resref(metadata.get("connected_room_resref") or metadata.get("connection_room")),
        connected_opening_name=str(metadata.get("connected_opening_name") or metadata.get("connection_opening") or "").strip(),
    )


def authored_room_connection_hooks(project: AuthoredModuleProject) -> tuple[AuthoredRoomConnectionHook, ...]:
    """Return stable world-space snap hooks for authored floor-plan openings."""

    hooks: list[AuthoredRoomConnectionHook] = []
    for room in project.rooms:
        primitive = _floor_plan_room_primitive(room)
        if primitive is None:
            continue
        for opening in primitive.openings:
            hook = _opening_hook(room, primitive, opening)
            if hook is not None:
                hooks.append(hook)
    return tuple(hooks)


def _hook_facing_dot(first: AuthoredRoomConnectionHook, second: AuthoredRoomConnectionHook) -> float:
    return (first.outward[0] * second.outward[0]) + (first.outward[1] * second.outward[1])


def _hook_distance(first: AuthoredRoomConnectionHook, second: AuthoredRoomConnectionHook) -> float:
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(first.position, second.position)))


def _hooks_compatible(first: AuthoredRoomConnectionHook, second: AuthoredRoomConnectionHook, *, distance_tolerance: float, facing_tolerance: float) -> bool:
    if first.room_resref == second.room_resref:
        return False
    if not first.passable or not second.passable:
        return False
    if _hook_distance(first, second) > float(distance_tolerance):
        return False
    if _hook_facing_dot(first, second) > float(facing_tolerance):
        return False
    width_tolerance = max(0.25, min(first.width, second.width) * 0.25)
    height_tolerance = max(0.25, min(first.height, second.height) * 0.25)
    return abs(first.width - second.width) <= width_tolerance and abs(first.height - second.height) <= height_tolerance


def audit_authored_room_connections(
    project: AuthoredModuleProject,
    *,
    distance_tolerance: float = 0.2,
    facing_tolerance: float = -0.8,
) -> AuthoredRoomConnectionAudit:
    """Audit opening alignment and persistent connection intent.

    This is a layout/VIS authoring signal only. It deliberately does not claim
    that KOTOR WOK transition edges, room links, or an in-game warp are proven.
    """

    hooks = authored_room_connection_hooks(project)
    by_room_and_name = {
        (hook.room_resref, hook.opening_name.strip().lower()): hook for hook in hooks
    }
    used: set[str] = set()
    connections: list[AuthoredRoomConnection] = []
    warnings: list[str] = []

    # Honor explicit KMAP links first so a later nearby hook cannot steal the
    # intended pair. Stale links remain visibly unconnected.
    for hook in hooks:
        if hook.hook_id in used or not hook.connected_room_resref:
            continue
        target = by_room_and_name.get((hook.connected_room_resref, hook.connected_opening_name.strip().lower()))
        if target is None:
            warnings.append(f"{hook.label} targets a missing room opening.")
            continue
        if target.hook_id in used:
            continue
        distance = _hook_distance(hook, target)
        facing_dot = _hook_facing_dot(hook, target)
        if not _hooks_compatible(
            hook,
            target,
            distance_tolerance=distance_tolerance,
            facing_tolerance=facing_tolerance,
        ):
            warnings.append(
                f"{hook.label} is linked to {target.label}, but the openings are no longer aligned or size-compatible."
            )
            continue
        used.update((hook.hook_id, target.hook_id))
        connections.append(
            AuthoredRoomConnection(
                first_hook_id=hook.hook_id,
                second_hook_id=target.hook_id,
                distance=distance,
                facing_dot=facing_dot,
                explicit=True,
            )
        )

    # Also recognize already aligned legacy openings even if older KMAP data
    # has no explicit connection metadata yet.
    candidates: list[tuple[float, AuthoredRoomConnectionHook, AuthoredRoomConnectionHook]] = []
    for index, first in enumerate(hooks):
        if first.hook_id in used:
            continue
        for second in hooks[index + 1:]:
            if second.hook_id in used:
                continue
            if _hooks_compatible(
                first,
                second,
                distance_tolerance=distance_tolerance,
                facing_tolerance=facing_tolerance,
            ):
                candidates.append((_hook_distance(first, second), first, second))
    for distance, first, second in sorted(candidates, key=lambda item: item[0]):
        if first.hook_id in used or second.hook_id in used:
            continue
        used.update((first.hook_id, second.hook_id))
        connections.append(
            AuthoredRoomConnection(
                first_hook_id=first.hook_id,
                second_hook_id=second.hook_id,
                distance=distance,
                facing_dot=_hook_facing_dot(first, second),
                explicit=False,
            )
        )

    unconnected = tuple(
        hook.hook_id
        for hook in hooks
        if hook.passable and not hook.external and hook.hook_id not in used
    )
    if unconnected:
        labels = {hook.hook_id: hook.label for hook in hooks}
        preview = ", ".join(labels[hook_id] for hook_id in unconnected[:4])
        suffix = f" and {len(unconnected) - 4} more" if len(unconnected) > 4 else ""
        warnings.append(
            f"Unconnected passable room openings: {preview}{suffix}. Connect them or mark intentional module exits as external."
        )
    return AuthoredRoomConnectionAudit(
        hooks=hooks,
        connections=tuple(connections),
        unconnected_hook_ids=unconnected,
        warnings=tuple(warnings),
    )


def _opening_with_connection(opening: FloorPlanWallOpening, target: AuthoredRoomConnectionHook) -> FloorPlanWallOpening:
    metadata = dict(opening.metadata or {})
    metadata.update(
        {
            "connected_room_resref": target.room_resref,
            "connected_opening_name": target.opening_name,
            "connection_state": "connected",
        }
    )
    return replace(opening, metadata=metadata)


def _replace_room_opening(
    room: AuthoredRoomSpec,
    *,
    edge_index: int,
    opening_name: str,
    target: AuthoredRoomConnectionHook,
) -> AuthoredRoomSpec:
    primitive = _floor_plan_room_primitive(room)
    if primitive is None:
        raise ValueError(f"Room {_room_name(room)} is not an authored floor-plan room.")
    matched = False
    openings: list[FloorPlanWallOpening] = []
    for opening in primitive.openings:
        same = int(opening.edge_index) == int(edge_index) and (
            str(opening.name or "").strip() or f"edge_{int(opening.edge_index)}"
        ).lower() == str(opening_name or "").strip().lower()
        if same:
            openings.append(_opening_with_connection(opening, target))
            matched = True
        else:
            openings.append(opening)
    if not matched:
        raise ValueError(f"Opening {opening_name or edge_index} no longer exists in room {_room_name(room)}.")
    return replace(room, primitive=replace(primitive, openings=tuple(openings)))


def connect_authored_room_openings(
    project: AuthoredModuleProject,
    source_hook_id: str,
    target_hook_id: str,
    *,
    align_source: bool = True,
) -> AuthoredRoomConnectionUpdate:
    """Align two floor-plan openings and persist their KMAP/VIS relationship."""

    hooks = {hook.hook_id: hook for hook in authored_room_connection_hooks(project)}
    source = hooks.get(str(source_hook_id or ""))
    target = hooks.get(str(target_hook_id or ""))
    if source is None or target is None:
        raise ValueError("Choose two existing authored floor-plan openings.")
    if source.room_resref == target.room_resref:
        raise ValueError("Room connections require openings from two different rooms.")
    if not source.passable or not target.passable:
        raise ValueError("Only floor-level passable openings can connect rooms; window/backdrop openings remain visual.")

    room_by_name = {_room_name(room): room for room in project.rooms}
    source_room = room_by_name[source.room_resref]
    target_room = room_by_name[target.room_resref]
    source_primitive = _floor_plan_room_primitive(source_room)
    if source_primitive is None:
        raise ValueError(f"Room {source.room_resref} is not an authored floor-plan room.")

    rotation_degrees = 0.0
    translation = (0.0, 0.0, 0.0)
    if align_source:
        source_angle = math.atan2(source.outward[1], source.outward[0])
        target_opposite_angle = math.atan2(-target.outward[1], -target.outward[0])
        delta = target_opposite_angle - source_angle
        delta = (delta + math.pi) % (2.0 * math.pi) - math.pi
        cos_a = math.cos(delta)
        sin_a = math.sin(delta)
        rotated_points = tuple(
            (
                float(x) * cos_a - float(y) * sin_a,
                float(x) * sin_a + float(y) * cos_a,
            )
            for x, y in source_primitive.points
        )
        rotated_primitive = replace(source_primitive, points=rotated_points)
        temporary_room = replace(source_room, primitive=rotated_primitive, position=(0.0, 0.0, 0.0))
        rotated_hook = _opening_hook(
            temporary_room,
            rotated_primitive,
            next(
                opening
                for opening in rotated_primitive.openings
                if int(opening.edge_index) == source.edge_index
                and (str(opening.name or "").strip() or f"edge_{int(opening.edge_index)}").lower()
                == source.opening_name.lower()
            ),
        )
        if rotated_hook is None:
            raise ValueError("Could not resolve the rotated source opening.")
        new_position = (
            float(target.position[0]) - float(rotated_hook.position[0]),
            float(target.position[1]) - float(rotated_hook.position[1]),
            float(target.position[2]) - float(rotated_hook.position[2]),
        )
        old_position = tuple(float(value) for value in source_room.position)
        translation = tuple(new_position[index] - old_position[index] for index in range(3))
        rotation_degrees = math.degrees(delta)
        source_room = replace(source_room, primitive=rotated_primitive, position=new_position)

    source_room = _replace_room_opening(
        source_room,
        edge_index=source.edge_index,
        opening_name=source.opening_name,
        target=target,
    )
    target_room = _replace_room_opening(
        target_room,
        edge_index=target.edge_index,
        opening_name=target.opening_name,
        target=source,
    )
    source_visible = tuple(dict.fromkeys((*source_room.visible_rooms, target.room_resref)))
    target_visible = tuple(dict.fromkeys((*target_room.visible_rooms, source.room_resref)))
    source_room = replace(source_room, visible_rooms=source_visible)
    target_room = replace(target_room, visible_rooms=target_visible)

    updated_rooms = tuple(
        source_room if _room_name(room) == source.room_resref
        else target_room if _room_name(room) == target.room_resref
        else room
        for room in project.rooms
    )
    updated_extra = dict(project.extra or {})
    pairs = {
        tuple(sorted((normalise_resref(pair[0]), normalise_resref(pair[1]))))
        for pair in list(updated_extra.get("vis_pairs") or ())
        if isinstance(pair, (list, tuple)) and len(pair) >= 2
    }
    pairs.add(tuple(sorted((source.room_resref, target.room_resref))))
    updated_extra["vis_pairs"] = [list(pair) for pair in sorted(pairs)]
    updated_extra["room_connection_source"] = "map_studio_authored_openings"
    updated = replace(project, rooms=updated_rooms, extra=updated_extra)
    summary = (
        f"Connected {source.label} to {target.label}; aligned the source room, "
        "persisted both opening links, and added symmetric VIS intent."
    )
    return AuthoredRoomConnectionUpdate(
        project=updated,
        source_hook=source,
        target_hook=target,
        rotation_degrees=rotation_degrees,
        translation=translation,
        summary=summary,
    )


def snap_authored_rooms_to_grid(
    project: AuthoredModuleProject,
    room_resrefs: tuple[str, ...] | list[str],
    *,
    grid_size: float = 1.0,
) -> AuthoredModuleProject:
    """Snap selected authored room layout positions to an XY meter grid."""

    size = float(grid_size)
    if not math.isfinite(size) or size <= 0.0:
        raise ValueError("Room layout grid size must be a positive finite value.")
    wanted = {normalise_resref(value) for value in room_resrefs if str(value or "").strip()}
    if not wanted:
        raise ValueError("Select one or more authored rooms to snap to the layout grid.")
    matched = False
    rooms: list[AuthoredRoomSpec] = []
    for room in project.rooms:
        if _room_name(room) not in wanted:
            rooms.append(room)
            continue
        x, y, z = (float(value) for value in room.position)
        rooms.append(replace(room, position=(round(x / size) * size, round(y / size) * size, z)))
        matched = True
    if not matched:
        raise ValueError("None of the selected room resrefs exist in the authored module.")
    return replace(project, rooms=tuple(rooms))


def _authored_room_local_xy_bounds(room: AuthoredRoomSpec) -> tuple[float, float, float, float]:
    """Return export-geometry bounds for geometry-aware room arrangement."""

    from .authored_module_project import compile_authored_room_spec

    geometry = compile_authored_room_spec(room)
    points: list[tuple[float, float]] = []
    meshes = (getattr(geometry, "room_mesh", None), *tuple(getattr(geometry, "helper_meshes", ()) or ()))
    for mesh in (item for item in meshes if item is not None):
        points.extend((float(vertex[0]), float(vertex[1])) for vertex in tuple(getattr(mesh, "vertices", ()) or ()))
    wok = getattr(geometry, "wok", None)
    if wok is not None:
        points.extend((float(vertex[0]), float(vertex[1])) for vertex in tuple(getattr(wok, "verts", ()) or ()))
    if not points:
        return (0.0, 0.0, 4.0, 4.0)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def auto_arrange_authored_rooms(
    project: AuthoredModuleProject,
    room_resrefs: tuple[str, ...] | list[str] = (),
    *,
    spacing: float = 1.0,
    columns: int | None = None,
) -> AuthoredModuleProject:
    """Arrange selected/all authored rooms into a non-overlapping XY grid."""

    gap = float(spacing)
    if not math.isfinite(gap) or gap < 0.0:
        raise ValueError("Room arrangement spacing must be a finite value at least zero.")
    wanted = {normalise_resref(value) for value in room_resrefs if str(value or "").strip()}
    selected = [room for room in project.rooms if not wanted or _room_name(room) in wanted]
    if not selected:
        raise ValueError("No authored rooms are available to arrange.")
    column_count = int(columns or math.ceil(math.sqrt(len(selected))))
    if column_count <= 0:
        raise ValueError("Room arrangement column count must be positive.")
    bounds = {_room_name(room): _authored_room_local_xy_bounds(room) for room in selected}
    rows: list[list[AuthoredRoomSpec]] = [
        selected[index:index + column_count] for index in range(0, len(selected), column_count)
    ]
    replacements: dict[str, AuthoredRoomSpec] = {}
    cursor_y = 0.0
    for row in rows:
        row_height = max(max(bounds[_room_name(room)][3] - bounds[_room_name(room)][1], 0.1) for room in row)
        cursor_x = 0.0
        for room in row:
            min_x, min_y, max_x, _max_y = bounds[_room_name(room)]
            width = max(max_x - min_x, 0.1)
            _old_x, _old_y, old_z = (float(value) for value in room.position)
            replacements[_room_name(room)] = replace(
                room,
                position=(cursor_x - min_x, cursor_y - min_y, old_z),
            )
            cursor_x += width + gap
        cursor_y += row_height + gap
    return replace(
        project,
        rooms=tuple(replacements.get(_room_name(room), room) for room in project.rooms),
    )


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
                # Imported custom modules routinely list VIS/room visibility to
                # rooms that are not editable in this project (skyboxes like
                # valsky, transition/reference rooms with no WOK). Drop the
                # dangling link with a warning rather than blocking the export;
                # VIS emission only writes links between rooms that exist here.
                warnings.append(
                    f"Room {name or index + 1} sees room {target_name}, which is not in this module; "
                    "the visibility link is dropped."
                )
    if len(room_set) > 1 and not any(room.visible_rooms for room in project.rooms):
        warnings.append("Multi-room layout has no explicit VIS links; each room will see only itself.")
    seen_door_hooks: set[str] = set()
    for index, door in enumerate(project.placements.doors):
        hook_name = _door_hook_name(door.template_resref, door.tag)
        if not hook_name:
            blocking.append(f"Door hook {index + 1} requires a template resref or tag.")
            continue
        if hook_name in seen_door_hooks:
            # Vanilla modules legitimately reuse one door model for several
            # doors (e.g. plcaa's man26aa_door05 x2); emission suffixes the
            # duplicates, so this is informational rather than blocking.
            warnings.append(f"Door hook name {hook_name} is reused; emitting a numbered duplicate.")
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
    connection_audit = audit_authored_room_connections(project)
    warnings.extend(connection_audit.warnings)
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
    room_set = {_room_name(room) for room in project.rooms if _room_name(room)}
    for room in project.rooms:
        room_name = _room_name(room)
        room_names.append(room_name)
        x, y, z = (float(value) for value in room.position)
        lyt.rooms.append(LYTRoom(room_name, x, y, z))
        # Rooms are implicitly visible to themselves: vanilla VIS never
        # self-references (tst_light: "r00_test 0"), and the engine's
        # room-by-name resolution crashed (NULL+0x84 at 0x0044b3a8, session
        # 20260708-121100) on our synthetic self-entry.
        # Drop links to rooms not present in this module (imported custom
        # modules see skyboxes / reference rooms we don't carry as authored
        # rooms) so the emitted VIS only references rooms that exist.
        visible = [
            normalise_resref(target)
            for target in room.visible_rooms
            if normalise_resref(target)
            and normalise_resref(target) != room_name
            and normalise_resref(target) in room_set
        ]
        visibility[room_name] = visible
    # KOTOR VIS is symmetric: if A can see B, then from B you can see A. Imported
    # custom modules frequently ship asymmetric VIS (a modder mistake the engine
    # tolerates but the base-game contract rejects). Mirror every link so the
    # emitted VIS is symmetric and valid.
    for source_room, targets in list(visibility.items()):
        for target in targets:
            if target in visibility and source_room not in visibility[target]:
                visibility[target].append(source_room)
    def _nearest_room(x: float, y: float) -> str:
        best_name = room_names[0] if room_names else "room"
        best_distance = None
        for entry in lyt.rooms:
            distance = ((float(entry.x) - x) ** 2) + ((float(entry.y) - y) ** 2)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_name = entry.model
        return best_name

    hook_counts: dict[str, int] = {}
    for door in project.placements.doors:
        qx, qy, qz, qw = _bearing_to_quaternion_z(float(door.bearing))
        hook_name = _door_hook_name(door.template_resref, door.tag)
        hook_counts[hook_name] = hook_counts.get(hook_name, 0) + 1
        if hook_counts[hook_name] > 1:
            hook_name = f"{hook_name}_{hook_counts[hook_name]}"
        lyt.doorhooks.append(
            LYTDoorHook(
                hook_name,
                float(door.position[0]),
                float(door.position[1]),
                float(door.position[2]),
                qx,
                qy,
                qz,
                qw,
                room=_nearest_room(float(door.position[0]), float(door.position[1])),
            )
        )
    connection_audit = audit_authored_room_connections(project)
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
            "room_connection_hook_count": len(connection_audit.hooks),
            "room_connection_count": len(connection_audit.connections),
            "unconnected_room_opening_count": len(connection_audit.unconnected_hook_ids),
        },
    )


__all__ = [
    "AuthoredRoomConnection",
    "AuthoredRoomConnectionAudit",
    "AuthoredRoomConnectionHook",
    "AuthoredRoomConnectionUpdate",
    "AuthoredModuleLayout",
    "AuthoredModuleLayoutValidation",
    "audit_authored_room_connections",
    "auto_arrange_authored_rooms",
    "authored_room_connection_hooks",
    "compile_authored_module_layout",
    "connect_authored_room_openings",
    "snap_authored_rooms_to_grid",
    "validate_authored_module_layout",
]
