"""Headless authored module layout compiler for Map Studio.

Map Studio rooms should compile to Odyssey LYT/VIS data through a reusable
service instead of each workflow assembling layout text by hand.  This module
keeps room placement and visibility policy Qt-free and testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

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
    intent: str = "connectable"
    external: bool = False
    sealed_door_placement_id: str = ""
    connected_room_resref: str = ""
    connected_opening_name: str = ""

    @property
    def passable(self) -> bool:
        return (
            self.bottom <= 1.0e-5
            and self.intent != "sealed"
            and self.opening_kind not in {"window", "backdrop", "view", "sealed"}
        )

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


@dataclass(frozen=True)
class AuthoredRoomOpeningIntentUpdate:
    """One durable user decision for an unconnected room-opening hook."""

    project: AuthoredModuleProject
    hook_id: str
    room_resref: str
    opening_name: str
    intent: str
    sealed_door_placement_id: str = ""
    summary: str = ""


@dataclass(frozen=True)
class AuthoredRoomDragSnapPreview:
    """Disposable doorway or terrain-edge solution for one whole-room drag."""

    magnet_snapped: bool
    source_room_resref: str
    target_room_resref: str = ""
    source_hook_id: str = ""
    target_hook_id: str = ""
    source_edge_index: int = -1
    target_edge_index: int = -1
    source_opening_name: str = ""
    auto_cut_source: bool = False
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    world_delta: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_degrees_z: float = 0.0
    snap_distance: float = math.inf
    opening_width: float = 0.0
    opening_height: float = 0.0
    target_label: str = ""
    reason: str = ""
    snap_kind: str = "doorway"
    source_terrain_edge: str = ""
    target_terrain_edge: str = ""

    def as_payload(self) -> dict[str, object]:
        return {
            "magnet_snapped": bool(self.magnet_snapped),
            "source_room_resref": self.source_room_resref,
            "target_room_resref": self.target_room_resref,
            "source_hook_id": self.source_hook_id,
            "target_hook_id": self.target_hook_id,
            "source_edge_index": int(self.source_edge_index),
            "target_edge_index": int(self.target_edge_index),
            "source_opening_name": self.source_opening_name,
            "auto_cut_source": bool(self.auto_cut_source),
            "position": tuple(self.position),
            "world_delta": tuple(self.world_delta),
            "rotation_degrees_z": float(self.rotation_degrees_z),
            "snap_distance": float(self.snap_distance),
            "opening_width": float(self.opening_width),
            "opening_height": float(self.opening_height),
            "target_label": self.target_label,
            "reason": self.reason,
            "snap_kind": self.snap_kind,
            "source_terrain_edge": self.source_terrain_edge,
            "target_terrain_edge": self.target_terrain_edge,
        }


def _floor_plan_room_primitive(room: AuthoredRoomSpec) -> FloorPlanRoomPrimitive | None:
    primitive = room.primitive
    return primitive if isinstance(primitive, FloorPlanRoomPrimitive) else None


def _terrain_room_primitive(room: AuthoredRoomSpec) -> Any | None:
    from .authored_terrain_builder import TerrainHeightfieldPrimitive

    primitive = room.primitive
    return primitive if isinstance(primitive, TerrainHeightfieldPrimitive) else None


_TERRAIN_EDGE_PAIRS = (
    ("left", "right"),
    ("right", "left"),
    ("bottom", "top"),
    ("top", "bottom"),
)


def _terrain_edge_sample_count(primitive: Any, edge: str) -> int:
    rows = tuple(tuple(float(value) for value in row) for row in tuple(primitive.heights or ()))
    if not rows:
        return 0
    return len(rows) if edge in {"left", "right"} else len(rows[0])


def _terrain_edge_length(primitive: Any, edge: str) -> float:
    return float(primitive.depth if edge in {"left", "right"} else primitive.width)


def _terrain_edge_midpoint_local(primitive: Any, edge: str) -> tuple[float, float, float]:
    rows = tuple(tuple(float(value) for value in row) for row in tuple(primitive.heights or ()))
    if edge == "left":
        heights = tuple(row[0] for row in rows)
        return (-float(primitive.width) * 0.5, 0.0, sum(heights) / len(heights))
    if edge == "right":
        heights = tuple(row[-1] for row in rows)
        return (float(primitive.width) * 0.5, 0.0, sum(heights) / len(heights))
    heights = rows[0] if edge == "bottom" else rows[-1]
    return (
        0.0,
        (-1.0 if edge == "bottom" else 1.0) * float(primitive.depth) * 0.5,
        sum(heights) / len(heights),
    )


def _preview_terrain_room_drag_snap(
    project: AuthoredModuleProject,
    *,
    source_room: AuthoredRoomSpec,
    world_delta: tuple[float, float, float],
    snap_distance: float,
    target_room_resref: str,
) -> AuthoredRoomDragSnapPreview:
    source_primitive = _terrain_room_primitive(source_room)
    source_name = _room_name(source_room)
    source_origin = tuple(float(value) for value in source_room.position)
    proposed = tuple(source_origin[index] + world_delta[index] for index in range(3))
    wanted_target = normalise_resref(target_room_resref)
    best: AuthoredRoomDragSnapPreview | None = None
    incompatible = False
    for target_room in project.rooms:
        target_name = _room_name(target_room)
        target_primitive = _terrain_room_primitive(target_room)
        if (
            target_name == source_name
            or target_primitive is None
            or (wanted_target and target_name != wanted_target)
        ):
            continue
        target_origin = tuple(float(value) for value in target_room.position)
        for source_edge, target_edge in _TERRAIN_EDGE_PAIRS:
            source_count = _terrain_edge_sample_count(source_primitive, source_edge)
            target_count = _terrain_edge_sample_count(target_primitive, target_edge)
            if (
                source_count != target_count
                or source_count < 2
                or not math.isclose(
                    _terrain_edge_length(source_primitive, source_edge),
                    _terrain_edge_length(target_primitive, target_edge),
                    abs_tol=1.0e-5,
                )
            ):
                incompatible = True
                continue
            snapped = [proposed[0], proposed[1], proposed[2]]
            if source_edge == "left":
                snapped[0] = target_origin[0] + float(target_primitive.width) * 0.5 + float(source_primitive.width) * 0.5
                snapped[1] = target_origin[1]
            elif source_edge == "right":
                snapped[0] = target_origin[0] - float(target_primitive.width) * 0.5 - float(source_primitive.width) * 0.5
                snapped[1] = target_origin[1]
            elif source_edge == "bottom":
                snapped[0] = target_origin[0]
                snapped[1] = target_origin[1] + float(target_primitive.depth) * 0.5 + float(source_primitive.depth) * 0.5
            else:
                snapped[0] = target_origin[0]
                snapped[1] = target_origin[1] - float(target_primitive.depth) * 0.5 - float(source_primitive.depth) * 0.5
            distance = math.hypot(snapped[0] - proposed[0], snapped[1] - proposed[1])
            within = distance <= max(0.05, float(snap_distance))
            candidate = AuthoredRoomDragSnapPreview(
                magnet_snapped=within,
                source_room_resref=source_name,
                target_room_resref=target_name,
                source_opening_name=f"terrain_{source_edge}",
                position=tuple(snapped),
                world_delta=tuple(snapped[index] - source_origin[index] for index in range(3)),
                snap_distance=distance,
                opening_width=_terrain_edge_length(source_primitive, source_edge) / float(source_count - 1),
                opening_height=0.0,
                target_label=f"{target_name} — {target_edge} terrain edge",
                reason=(
                    f"Release to weld the {source_edge} edge to {target_name}'s {target_edge} edge; matching WOK traversal is automatic."
                    if within
                    else "Move the terrain patch closer to a compatible edge."
                ),
                snap_kind="terrain_seam",
                source_terrain_edge=source_edge,
                target_terrain_edge=target_edge,
            )
            if best is None or candidate.snap_distance < best.snap_distance:
                best = candidate
    if best is None:
        reason = (
            "Terrain edges need the same physical length and sample count before they can be welded safely."
            if incompatible
            else "Create another terrain surface, then move this patch near one of its edges."
        )
        return AuthoredRoomDragSnapPreview(
            False,
            source_name,
            position=proposed,
            world_delta=world_delta,
            reason=reason,
            snap_kind="terrain_seam",
        )
    if best.magnet_snapped:
        return best
    return replace(best, position=proposed, world_delta=world_delta)


def _terrain_edge_values(primitive: Any, edge: str) -> tuple[float, ...]:
    rows = tuple(tuple(float(value) for value in row) for row in tuple(primitive.heights or ()))
    if edge == "left":
        return tuple(row[0] for row in rows)
    if edge == "right":
        return tuple(row[-1] for row in rows)
    return tuple(rows[0] if edge == "bottom" else rows[-1])


def _replace_terrain_edge_values(primitive: Any, edge: str, values: tuple[float, ...]) -> Any:
    rows = [list(float(value) for value in row) for row in tuple(primitive.heights or ())]
    if edge in {"left", "right"}:
        column = 0 if edge == "left" else -1
        for index, value in enumerate(values):
            rows[index][column] = float(value)
    else:
        row = 0 if edge == "bottom" else -1
        rows[row] = [float(value) for value in values]
    return replace(primitive, heights=tuple(tuple(row) for row in rows))


def _terrain_edge_portal_metadata(primitive: Any, edge: str, magnet_id: str) -> dict[str, Any]:
    rows = tuple(tuple(float(value) for value in row) for row in tuple(primitive.heights or ()))
    sample_count = _terrain_edge_sample_count(primitive, edge)
    segment = max(0, min(sample_count - 2, (sample_count - 1) // 2))
    if edge in {"left", "right"}:
        x = (-1.0 if edge == "left" else 1.0) * float(primitive.width) * 0.5
        step = float(primitive.depth) / float(sample_count - 1)
        y0 = -float(primitive.depth) * 0.5 + step * segment
        start = (x, y0, rows[segment][0 if edge == "left" else -1])
        end = (x, y0 + step, rows[segment + 1][0 if edge == "left" else -1])
    else:
        y = (-1.0 if edge == "bottom" else 1.0) * float(primitive.depth) * 0.5
        step = float(primitive.width) / float(sample_count - 1)
        x0 = -float(primitive.width) * 0.5 + step * segment
        row = rows[0 if edge == "bottom" else -1]
        start = (x0, y, row[segment])
        end = (x0 + step, y, row[segment + 1])
    midpoint = tuple((start[index] + end[index]) * 0.5 for index in range(3))
    return {
        "magnet_id": magnet_id,
        "start": list(start),
        "end": list(end),
        "midpoint": list(midpoint),
        "width_m": math.dist(start, end),
        "terrain_edge": edge,
        "auto_generated": True,
    }


def _terrain_connection_point(edge: str, portal: dict[str, Any], magnet_id: str) -> dict[str, Any]:
    angle = {"left": math.pi, "right": 0.0, "bottom": -math.pi * 0.5, "top": math.pi * 0.5}[edge]
    return {
        "door": magnet_id,
        "local_position": list(portal["midpoint"]),
        "orientation": [0.0, 0.0, math.sin(angle * 0.5), math.cos(angle * 0.5)],
        "opening_kind": "terrain_seam",
        "auto_generated": True,
    }


def _replace_named_metadata_row(rows: Any, key: str, value: str, row: dict[str, Any]) -> list[dict[str, Any]]:
    wanted = str(value or "").strip().lower()
    kept = [
        dict(existing or {})
        for existing in tuple(rows or ())
        if str(dict(existing or {}).get(key) or "").strip().lower() != wanted
    ]
    kept.append(row)
    return kept


def _connect_terrain_room_drag_snap(
    project: AuthoredModuleProject,
    values: dict[str, Any],
) -> AuthoredRoomConnectionUpdate:
    source_name = normalise_resref(values.get("source_room_resref"))
    target_name = normalise_resref(values.get("target_room_resref"))
    source_edge = str(values.get("source_terrain_edge") or "").strip().lower()
    target_edge = str(values.get("target_terrain_edge") or "").strip().lower()
    source_room = next((room for room in project.rooms if _room_name(room) == source_name), None)
    target_room = next((room for room in project.rooms if _room_name(room) == target_name), None)
    source_primitive = _terrain_room_primitive(source_room) if source_room is not None else None
    target_primitive = _terrain_room_primitive(target_room) if target_room is not None else None
    if (
        source_primitive is None
        or target_primitive is None
        or (source_edge, target_edge) not in _TERRAIN_EDGE_PAIRS
    ):
        raise ValueError("The terrain seam changed before the patch was released.")
    if (
        _terrain_edge_sample_count(source_primitive, source_edge)
        != _terrain_edge_sample_count(target_primitive, target_edge)
        or not math.isclose(
            _terrain_edge_length(source_primitive, source_edge),
            _terrain_edge_length(target_primitive, target_edge),
            abs_tol=1.0e-5,
        )
    ):
        raise ValueError("Terrain seams require matching edge length and sample count.")
    position = tuple(float(value) for value in tuple(values.get("position") or ())[:3])
    if len(position) != 3:
        raise ValueError("The snapped terrain position is incomplete.")
    target_world_heights = tuple(
        float(value) + float(target_room.position[2])
        for value in _terrain_edge_values(target_primitive, target_edge)
    )
    source_local_heights = tuple(value - position[2] for value in target_world_heights)
    source_primitive = _replace_terrain_edge_values(source_primitive, source_edge, source_local_heights)
    source_magnet = f"terrain_{source_edge}"
    target_magnet = f"terrain_{target_edge}"
    source_portal = _terrain_edge_portal_metadata(source_primitive, source_edge, source_magnet)
    target_portal = _terrain_edge_portal_metadata(target_primitive, target_edge, target_magnet)
    source_primitive_metadata = dict(source_primitive.metadata or {})
    source_primitive_metadata["walkmesh_portals"] = _replace_named_metadata_row(
        source_primitive_metadata.get("walkmesh_portals"), "magnet_id", source_magnet, source_portal
    )
    source_primitive_metadata["terrain_seams_auto_welded"] = True
    source_primitive = replace(source_primitive, metadata=source_primitive_metadata)
    target_primitive_metadata = dict(target_primitive.metadata or {})
    target_primitive_metadata["walkmesh_portals"] = _replace_named_metadata_row(
        target_primitive_metadata.get("walkmesh_portals"), "magnet_id", target_magnet, target_portal
    )
    target_primitive_metadata["terrain_seams_auto_welded"] = True
    target_primitive = replace(target_primitive, metadata=target_primitive_metadata)
    source_room_metadata = dict(source_room.metadata or {})
    source_room_metadata["connection_points"] = _replace_named_metadata_row(
        source_room_metadata.get("connection_points"),
        "door",
        source_magnet,
        _terrain_connection_point(source_edge, source_portal, source_magnet),
    )
    target_room_metadata = dict(target_room.metadata or {})
    target_room_metadata["connection_points"] = _replace_named_metadata_row(
        target_room_metadata.get("connection_points"),
        "door",
        target_magnet,
        _terrain_connection_point(target_edge, target_portal, target_magnet),
    )
    rooms = []
    for room in project.rooms:
        room_name = _room_name(room)
        if room_name == source_name:
            rooms.append(
                replace(
                    room,
                    primitive=source_primitive,
                    position=position,
                    visible_rooms=tuple(
                        dict.fromkeys((*tuple(room.visible_rooms or ()), source_name, target_name))
                    ),
                    metadata=source_room_metadata,
                )
            )
        elif room_name == target_name:
            rooms.append(
                replace(
                    room,
                    primitive=target_primitive,
                    visible_rooms=tuple(
                        dict.fromkeys((*tuple(room.visible_rooms or ()), target_name, source_name))
                    ),
                    metadata=target_room_metadata,
                )
            )
        else:
            rooms.append(room)
    updated = replace(project, rooms=tuple(rooms))
    from .authored_module_walkmesh import (
        compile_authored_room_connection_walkmeshes,
        upsert_authored_walkmesh_room_connection,
    )

    updated = upsert_authored_walkmesh_room_connection(
        updated,
        source_room_resref=source_name,
        source_hook_name=source_magnet,
        target_room_resref=target_name,
        target_hook_name=target_magnet,
        connection_source="map_studio_terrain_edge_snap",
    )
    build = compile_authored_room_connection_walkmeshes(updated)
    if not build.ready:
        raise ValueError(" ".join(build.blocking_issues))
    extra = dict(updated.extra or {})
    extra["last_walkmesh_build"] = {
        "operation": "connect_terrain_edges",
        "auto_generated": True,
        "portal_count": len(build.portals),
        "room_face_counts": {
            room_resref: len(tuple(wok.faces or ())) for room_resref, wok in build.room_woks.items()
        },
        "midpoint_gaps_m": [float(portal.midpoint_gap) for portal in build.portals],
        "ready": True,
    }
    updated = replace(updated, extra=extra)
    hooks = {
        (hook.room_resref, hook.opening_name.lower()): hook
        for hook in authored_room_connection_hooks(updated)
    }
    source_hook = hooks[(source_name, source_magnet)]
    target_hook = hooks[(target_name, target_magnet)]
    translation = tuple(position[index] - float(source_room.position[index]) for index in range(3))
    return AuthoredRoomConnectionUpdate(
        project=updated,
        source_hook=source_hook,
        target_hook=target_hook,
        rotation_degrees=0.0,
        translation=translation,
        summary=(
            f"Welded {source_name}'s {source_edge} terrain edge to {target_name}'s {target_edge} edge "
            "and generated a reciprocal WOK portal."
        ),
    )


def _opening_kind(opening: FloorPlanWallOpening) -> str:
    metadata = dict(opening.metadata or {})
    kind = str(metadata.get("opening_kind") or metadata.get("kind") or "").strip().lower()
    if kind:
        return kind
    return "window" if float(opening.bottom) > 1.0e-5 else "door"


def _opening_intent(metadata: dict[str, Any]) -> str:
    value = str(metadata.get("opening_intent") or metadata.get("intent") or "").strip().lower()
    if value in {"sealed", "closed", "blocked"} or bool(metadata.get("sealed")):
        return "sealed"
    if value in {"external", "module_exit", "cross_module"} or bool(
        metadata.get("external") or metadata.get("cross_module") or metadata.get("backdrop")
    ):
        return "external"
    return "connectable"


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
    intent = _opening_intent(metadata)
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
        opening_kind="sealed" if intent == "sealed" else _opening_kind(opening),
        intent=intent,
        external=intent == "external",
        sealed_door_placement_id=str(metadata.get("sealed_door_placement_id") or "").strip(),
        connected_room_resref=normalise_resref(metadata.get("connected_room_resref") or metadata.get("connection_room")),
        connected_opening_name=str(metadata.get("connected_opening_name") or metadata.get("connection_opening") or "").strip(),
    )


def authored_room_connection_hooks(project: AuthoredModuleProject) -> tuple[AuthoredRoomConnectionHook, ...]:
    """Return stable world-space hooks for floor-plan and vanilla-kit doors."""

    hooks: list[AuthoredRoomConnectionHook] = []
    connection_rows = tuple(dict(project.extra or {}).get("walkmesh_room_connections") or ())
    for room in project.rooms:
        primitive = _floor_plan_room_primitive(room)
        if primitive is not None:
            for opening in primitive.openings:
                hook = _opening_hook(room, primitive, opening)
                if hook is not None:
                    hooks.append(hook)
            continue

        # Reusable vanilla room tiles keep their LYT connection points rather
        # than synthesizing a second floor-plan opening. Promote those points
        # into the same audit contract so a styled room -> stock room LEGO join
        # is not incorrectly reported as an unconnected doorway.
        room_name = _room_name(room)
        room_metadata = dict(getattr(room, "metadata", {}) or {})
        primitive_metadata = dict(getattr(getattr(room, "primitive", None), "metadata", {}) or {})
        connection_point_rows = {
            str(dict(row or {}).get("door") or "").strip().lower(): dict(row or {})
            for row in tuple(room_metadata.get("connection_points") or ())
            if str(dict(row or {}).get("door") or "").strip()
        }
        walkmesh_portals = {
            str(dict(row or {}).get("magnet_id") or "").strip().lower(): dict(row or {})
            for row in tuple(primitive_metadata.get("walkmesh_portals") or ())
            if str(dict(row or {}).get("magnet_id") or "").strip()
        }
        try:
            from .map_studio_room_snapping import authored_room_door_hooks

            imported_hooks = authored_room_door_hooks(room)
        except Exception:
            imported_hooks = ()
        for imported in imported_hooks:
            door_name = str(imported.door or "").strip()
            if not door_name:
                continue
            connected_room = ""
            connected_opening = ""
            for raw in connection_rows:
                row = dict(raw or {})
                source_room = normalise_resref(row.get("source_room_resref"))
                target_room = normalise_resref(row.get("target_room_resref"))
                source_hook = str(row.get("source_hook_name") or "").strip()
                target_hook = str(row.get("target_hook_name") or "").strip()
                if source_room == room_name and source_hook.lower() == door_name.lower():
                    connected_room, connected_opening = target_room, target_hook
                    break
                if target_room == room_name and target_hook.lower() == door_name.lower():
                    connected_room, connected_opening = source_room, source_hook
                    break
            facing = float(imported.facing_radians)
            point_metadata = connection_point_rows.get(door_name.lower(), {})
            portal_metadata = walkmesh_portals.get(door_name.lower(), {})
            local_midpoint = tuple(portal_metadata.get("midpoint") or ())
            if len(local_midpoint) >= 3:
                position = tuple(
                    float(room.position[axis]) + float(local_midpoint[axis])
                    for axis in range(3)
                )
            else:
                position = tuple(float(value) for value in imported.world_position)
            portal_width = float(
                portal_metadata.get("width_m")
                or room_metadata.get("environment_kit_opening_width", 1.8)
                or 1.8
            )
            # LYT door-hook orientation is only an approximate placement hint.
            # The imported WOK portal is the authoritative seam: its ordered
            # boundary edge gives the exact tangent and therefore the outward
            # normal.  Using the LYT bearing here can align only the portal
            # midpoint while leaving the two full edges crossed at an angle,
            # producing a visible wedge and a player-radius WOK gap.
            portal_start = tuple(portal_metadata.get("start") or ())
            portal_end = tuple(portal_metadata.get("end") or ())
            outward = (math.cos(facing), math.sin(facing))
            if len(portal_start) >= 2 and len(portal_end) >= 2:
                portal_dx = float(portal_end[0]) - float(portal_start[0])
                portal_dy = float(portal_end[1]) - float(portal_start[1])
                portal_length = math.hypot(portal_dx, portal_dy)
                if portal_length > 1.0e-7:
                    # Walkable WOK faces use upward winding, so their interior
                    # lies to the left of an ordered boundary edge and the
                    # right-hand normal points out of the room.
                    outward = (portal_dy / portal_length, -portal_dx / portal_length)
            intent = _opening_intent(point_metadata)
            hooks.append(
                AuthoredRoomConnectionHook(
                    hook_id=f"{room_name}:-1:{door_name.lower()}",
                    room_resref=room_name,
                    opening_name=door_name,
                    edge_index=-1,
                    position=position,
                    outward=outward,
                    width=max(0.05, portal_width),
                    height=max(0.05, float(room_metadata.get("environment_kit_opening_height", 2.4) or 2.4)),
                    bottom=0.0,
                    opening_kind="sealed" if intent == "sealed" else "door",
                    intent=intent,
                    external=intent == "external",
                    sealed_door_placement_id=str(
                        point_metadata.get("sealed_door_placement_id") or ""
                    ).strip(),
                    connected_room_resref=connected_room,
                    connected_opening_name=connected_opening,
                )
            )
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
        # Explicit authored links are later compiled against the actual WOK
        # perimeter edges, which is the authoritative passability gate.
        # Retail LYT hook facing and nominal doorway dimensions are often
        # approximate (and can disagree with the WOK aperture), so rejecting a
        # co-located explicit pair here creates false layout warnings for
        # otherwise exact stock/authored joins.
        if distance > float(distance_tolerance):
            warnings.append(
                f"{hook.label} is linked to {target.label}, but the opening centers are no longer aligned."
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
            "walkmesh_portal": True,
            "walkmesh_portal_inset_m": 0.0,
            "walkmesh_portal_width_m": min(float(opening.width), float(target.width)),
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


def _replace_stock_room_opening(
    room: AuthoredRoomSpec,
    *,
    hook: AuthoredRoomConnectionHook,
    target: AuthoredRoomConnectionHook,
) -> AuthoredRoomSpec:
    """Persist a floor-plan connection on one imported room magnet."""

    room_metadata = dict(getattr(room, "metadata", {}) or {})
    rows: list[dict[str, Any]] = []
    matched = False
    for raw in tuple(room_metadata.get("connection_points") or ()):
        entry = dict(raw or {})
        if str(entry.get("door") or "").strip().lower() == hook.opening_name.lower():
            entry.update(
                {
                    "connected_room_resref": target.room_resref,
                    "connected_opening_name": target.opening_name,
                    "connection_state": "connected",
                    "walkmesh_portal": True,
                    "walkmesh_portal_inset_m": 0.0,
                    "walkmesh_portal_width_m": min(float(hook.width), float(target.width)),
                }
            )
            matched = True
        rows.append(entry)
    if not matched:
        raise ValueError(f"Opening {hook.opening_name} no longer exists in room {_room_name(room)}.")
    room_metadata["connection_points"] = rows
    return replace(room, metadata=room_metadata)


def _room_opening_for_hook(
    project: AuthoredModuleProject,
    hook: AuthoredRoomConnectionHook,
) -> tuple[AuthoredRoomSpec, FloorPlanWallOpening]:
    room = next((item for item in project.rooms if _room_name(item) == hook.room_resref), None)
    primitive = _floor_plan_room_primitive(room) if room is not None else None
    if room is None or primitive is None:
        raise ValueError(f"Room {hook.room_resref} is no longer an authored floor-plan room.")
    for opening in primitive.openings:
        opening_name = str(opening.name or "").strip() or f"edge_{int(opening.edge_index)}"
        if int(opening.edge_index) == int(hook.edge_index) and opening_name.lower() == hook.opening_name.lower():
            return room, opening
    raise ValueError(f"Opening {hook.opening_name} no longer exists in room {hook.room_resref}.")


def _replace_opening_metadata(
    project: AuthoredModuleProject,
    hook: AuthoredRoomConnectionHook,
    metadata: dict[str, Any],
) -> AuthoredModuleProject:
    rooms: list[AuthoredRoomSpec] = []
    matched = False
    for room in project.rooms:
        if _room_name(room) != hook.room_resref:
            rooms.append(room)
            continue
        primitive = _floor_plan_room_primitive(room)
        if primitive is None:
            rooms.append(room)
            continue
        openings: list[FloorPlanWallOpening] = []
        for opening in primitive.openings:
            opening_name = str(opening.name or "").strip() or f"edge_{int(opening.edge_index)}"
            if int(opening.edge_index) == int(hook.edge_index) and opening_name.lower() == hook.opening_name.lower():
                opening = replace(opening, metadata=dict(metadata))
                matched = True
            openings.append(opening)
        rooms.append(replace(room, primitive=replace(primitive, openings=tuple(openings))))
    if not matched:
        raise ValueError(f"Opening {hook.opening_name} no longer exists in room {hook.room_resref}.")
    return replace(project, rooms=tuple(rooms))


def _stock_opening_metadata(
    project: AuthoredModuleProject,
    hook: AuthoredRoomConnectionHook,
) -> dict[str, Any]:
    room = next((item for item in project.rooms if _room_name(item) == hook.room_resref), None)
    if room is None:
        raise ValueError(f"Room {hook.room_resref} no longer exists.")
    for row in tuple(dict(getattr(room, "metadata", {}) or {}).get("connection_points") or ()):
        entry = dict(row or {})
        if str(entry.get("door") or "").strip().lower() == hook.opening_name.lower():
            return entry
    raise ValueError(f"Opening {hook.opening_name} no longer exists in room {hook.room_resref}.")


def _replace_stock_opening_metadata(
    project: AuthoredModuleProject,
    hook: AuthoredRoomConnectionHook,
    metadata: dict[str, Any],
) -> AuthoredModuleProject:
    rooms: list[AuthoredRoomSpec] = []
    matched = False
    for room in project.rooms:
        if _room_name(room) != hook.room_resref:
            rooms.append(room)
            continue
        room_metadata = dict(getattr(room, "metadata", {}) or {})
        connection_points: list[dict[str, Any]] = []
        for raw in tuple(room_metadata.get("connection_points") or ()):
            entry = dict(raw or {})
            if str(entry.get("door") or "").strip().lower() == hook.opening_name.lower():
                entry = dict(metadata)
                matched = True
            connection_points.append(entry)
        room_metadata["connection_points"] = connection_points
        rooms.append(replace(room, metadata=room_metadata))
    if not matched:
        raise ValueError(f"Opening {hook.opening_name} no longer exists in room {hook.room_resref}.")
    return replace(project, rooms=tuple(rooms))


def _opening_metadata_for_hook(
    project: AuthoredModuleProject,
    hook: AuthoredRoomConnectionHook,
) -> dict[str, Any]:
    if hook.edge_index >= 0:
        _room, opening = _room_opening_for_hook(project, hook)
        return dict(opening.metadata or {})
    return _stock_opening_metadata(project, hook)


def _replace_hook_metadata(
    project: AuthoredModuleProject,
    hook: AuthoredRoomConnectionHook,
    metadata: dict[str, Any],
) -> AuthoredModuleProject:
    if hook.edge_index >= 0:
        return _replace_opening_metadata(project, hook, metadata)
    return _replace_stock_opening_metadata(project, hook, metadata)


def _suppress_open_transition_door(
    project: AuthoredModuleProject,
    hook: AuthoredRoomConnectionHook,
) -> AuthoredModuleProject:
    """Convert one connected hook into an open visual-transition portal."""

    metadata = _opening_metadata_for_hook(project, hook)
    placement_ids = {
        str(metadata.get("door_placement_id") or "").strip(),
        str(metadata.get("shared_door_placement_id") or "").strip(),
        str(metadata.get("sealed_door_placement_id") or "").strip(),
    }
    updated = project
    for placement_id in sorted(value for value in placement_ids if value):
        try:
            from .authored_module_placements import remove_authored_gameplay_placement

            updated = remove_authored_gameplay_placement(updated, placement_id).project
        except ValueError:
            pass
    metadata = {
        key: value
        for key, value in metadata.items()
        if key
        not in {
            "door_placement_id",
            "shared_door_placement_id",
            "sealed_door_placement_id",
            "sealed_door_template_resref",
            "door_template_resref",
            "door_model_resref",
            "door_appearance_id",
            "door_aperture_width_m",
            "door_aperture_height_m",
            "door_outer_width_m",
            "door_outer_height_m",
            "cross_style_transition_actor",
            "shared_connection_door",
        }
    }
    metadata.update(
        {
            "open_module_transition": True,
            "cave_archway_transition": True,
            "suppress_door_actor": True,
            "opening_kind": "door",
            "walkmesh_portal": True,
            "shared_connection_door": False,
        }
    )
    return _replace_hook_metadata(updated, hook, metadata)


def _sealed_door_pose(
    project: AuthoredModuleProject,
    hook: AuthoredRoomConnectionHook,
) -> tuple[tuple[float, float, float], float]:
    """Return the exact threshold midpoint and wall-tangent bearing."""

    room = next((item for item in project.rooms if _room_name(item) == hook.room_resref), None)
    if room is None:
        raise ValueError(f"Room {hook.room_resref} no longer exists.")
    primitive = _floor_plan_room_primitive(room)
    if primitive is not None and 0 <= hook.edge_index < len(primitive.points):
        start = primitive.points[hook.edge_index]
        end = primitive.points[(hook.edge_index + 1) % len(primitive.points)]
        bearing = math.atan2(float(end[1]) - float(start[1]), float(end[0]) - float(start[0]))
        return hook.position, bearing

    primitive_metadata = dict(getattr(getattr(room, "primitive", None), "metadata", {}) or {})
    for raw in tuple(primitive_metadata.get("walkmesh_portals") or ()):
        portal = dict(raw or {})
        if str(portal.get("magnet_id") or "").strip().lower() != hook.opening_name.lower():
            continue
        start = tuple(float(value) for value in tuple(portal.get("start") or ())[:3])
        end = tuple(float(value) for value in tuple(portal.get("end") or ())[:3])
        if len(start) == 3 and len(end) == 3:
            bearing = math.atan2(end[1] - start[1], end[0] - start[0])
            return hook.position, bearing
    return hook.position, math.atan2(hook.outward[1], hook.outward[0]) + (math.pi * 0.5)


def set_authored_room_opening_intent(
    project: AuthoredModuleProject,
    hook_id: str,
    intent: str,
) -> AuthoredRoomOpeningIntentUpdate:
    """Mark an opening connectable, external, or sealed with its authentic door."""

    resolved_intent = str(intent or "").strip().lower()
    if resolved_intent not in {"connectable", "external", "sealed"}:
        raise ValueError("Opening intent must be connectable, external, or sealed.")
    hook = next(
        (candidate for candidate in authored_room_connection_hooks(project) if candidate.hook_id == str(hook_id)),
        None,
    )
    if hook is None:
        raise ValueError("The selected room opening no longer exists.")
    if hook.connected_room_resref and resolved_intent != "connectable":
        raise ValueError("Disconnect this room opening before marking it external or sealed.")

    metadata = _opening_metadata_for_hook(project, hook)
    previous_sealed_placement = str(metadata.get("sealed_door_placement_id") or "").strip()
    updated = project
    if previous_sealed_placement:
        from .authored_module_placements import remove_authored_gameplay_placement

        try:
            updated = remove_authored_gameplay_placement(updated, previous_sealed_placement).project
        except ValueError:
            pass
    metadata["opening_intent"] = resolved_intent
    metadata["external"] = resolved_intent == "external"
    metadata["sealed"] = resolved_intent == "sealed"
    metadata.pop("sealed_door_placement_id", None)
    metadata.pop("sealed_door_template_resref", None)
    updated = _replace_hook_metadata(updated, hook, metadata)

    sealed_placement_id = ""
    if resolved_intent == "sealed":
        from .map_studio_pascal_building import add_pascal_sealed_door

        position, bearing = _sealed_door_pose(updated, hook)
        placement = add_pascal_sealed_door(
            updated,
            room_resref=hook.room_resref,
            opening_name=hook.opening_name,
            position=position,
            bearing=bearing,
        )
        updated = placement.project
        sealed_placement_id = placement.placement_id
        metadata["sealed_door_placement_id"] = sealed_placement_id
        metadata["sealed_door_template_resref"] = placement.template_resref
        updated = _replace_hook_metadata(updated, hook, metadata)

    summary = {
        "connectable": f"{hook.label} is available for room snapping.",
        "external": f"{hook.label} is an intentional module exit.",
        "sealed": f"{hook.label} is closed by a locked area-style door.",
    }[resolved_intent]
    updated = replace(
        updated,
        extra={
            **dict(updated.extra or {}),
            "last_room_opening_intent": {
                "hook_id": hook.hook_id,
                "room_resref": hook.room_resref,
                "opening_name": hook.opening_name,
                "intent": resolved_intent,
                "sealed_door_placement_id": sealed_placement_id,
            },
        },
    )
    return AuthoredRoomOpeningIntentUpdate(
        project=updated,
        hook_id=hook.hook_id,
        room_resref=hook.room_resref,
        opening_name=hook.opening_name,
        intent=resolved_intent,
        sealed_door_placement_id=sealed_placement_id,
        summary=summary,
    )


def _append_drag_snap_opening(
    project: AuthoredModuleProject,
    *,
    source_room_resref: str,
    edge_index: int,
    opening_name: str,
    target: AuthoredRoomConnectionHook,
) -> tuple[AuthoredModuleProject, AuthoredRoomConnectionHook]:
    """Cut a matching source-side opening without spawning a duplicate door actor."""

    target_metadata = _opening_metadata_for_hook(project, target)
    rooms: list[AuthoredRoomSpec] = []
    added = False
    for room in project.rooms:
        if _room_name(room) != normalise_resref(source_room_resref):
            rooms.append(room)
            continue
        primitive = _floor_plan_room_primitive(room)
        if primitive is None:
            raise ValueError(f"Room {source_room_resref} is not an authored floor-plan room.")
        edge = int(edge_index)
        points = tuple(primitive.points or ())
        if edge < 0 or edge >= len(points):
            raise ValueError(f"Wall {edge + 1} no longer exists in room {source_room_resref}.")
        start = points[edge]
        end = points[(edge + 1) % len(points)]
        edge_length = math.hypot(float(end[0]) - float(start[0]), float(end[1]) - float(start[1]))
        if edge_length <= float(target.width) + 0.02:
            raise ValueError(f"The matching {target.width:.2f} m doorway is wider than source wall {edge + 1}.")
        if float(target.bottom) < 0.0 or float(target.bottom) + float(target.height) >= float(primitive.wall_height) - 0.01:
            raise ValueError(f"The matching {target.height:.2f} m doorway does not fit below the source wall top.")
        metadata = {
            key: value
            for key, value in target_metadata.items()
            if key
            not in {
                "door_placement_id",
                "connected_room_resref",
                "connected_opening_name",
                "connection_room",
                "connection_opening",
                "connection_state",
                "module_transition_asset_id",
                "module_transition_target_profile",
                "module_transition_owner",
            }
        }
        target_door = str(target_metadata.get("door_placement_id") or "").strip()
        target_is_open_transition = bool(
            target_metadata.get("suppress_door_actor")
            or target_metadata.get("open_module_transition")
            or target_metadata.get("cave_archway_transition")
        )
        metadata.update(
            {
                "source": "map_studio:room_drag_snap",
                "operation": "auto_cut_room_connection",
                "opening_kind": "door",
                "shared_connection_door": bool(target_door),
                "shared_door_placement_id": target_door,
            }
        )
        from .map_studio_pascal_building import (
            pascal_architecture_door_spec,
            pascal_architecture_profile_for_room,
        )

        source_profile = pascal_architecture_profile_for_room(project, source_room_resref)
        target_profile = pascal_architecture_profile_for_room(project, target.room_resref)
        source_door_spec = pascal_architecture_door_spec(project.game, source_profile)
        target_door_spec = pascal_architecture_door_spec(project.game, target_profile)
        door_spec = source_door_spec or target_door_spec
        cave_profiles = {"korriban_caves_k1", "korriban_caves_k2"}
        if source_profile in cave_profiles or target_profile in cave_profiles:
            target_is_open_transition = True
            metadata.update(
                {
                    "open_module_transition": True,
                    "cave_archway_transition": True,
                    "suppress_door_actor": True,
                }
            )
            # The visual shell is selected once the reciprocal connection is
            # committed.  Assigning it here and again on the destination
            # opening stacks two full cave entrances at the same portal.
        if door_spec is not None and not target_door and not target_is_open_transition:
            metadata.update(
                {
                    "door_template_resref": str(door_spec["template_resref"]),
                    "door_model_resref": str(door_spec["model_resref"]),
                    "door_appearance_id": int(door_spec["appearance_id"]),
                    "door_aperture_width_m": float(door_spec["opening_width_m"]),
                    "door_aperture_height_m": float(door_spec["opening_height_m"]),
                    "door_outer_width_m": float(
                        door_spec.get("frame_width_m", door_spec["opening_width_m"])
                    ),
                    "door_outer_height_m": float(
                        door_spec.get("frame_height_m", door_spec["opening_height_m"])
                    ),
                    "cross_style_transition": source_profile != target_profile,
                    "cross_style_source_profile": source_profile,
                    "cross_style_target_profile": target_profile,
                }
            )
        opening = FloorPlanWallOpening(
            name=str(opening_name),
            edge_index=edge,
            center_fraction=0.5,
            width=float(target.width),
            height=float(target.height),
            bottom=float(target.bottom),
            metadata=metadata,
        )
        rooms.append(
            replace(
                room,
                primitive=replace(
                    primitive,
                    openings=tuple(primitive.openings or ()) + (opening,),
                    include_walls=True,
                    metadata={
                        **dict(primitive.metadata or {}),
                        "last_operation": "auto_cut_room_connection",
                        "last_opening_name": str(opening_name),
                        "last_opening_edge_index": edge,
                    },
                ),
                metadata={
                    **dict(room.metadata or {}),
                    "last_opening_name": str(opening_name),
                    "last_opening_edge_index": edge,
                },
            )
        )
        added = True
    if not added:
        raise ValueError(f"Room {source_room_resref} no longer exists.")
    updated = replace(project, rooms=tuple(rooms))
    hook_id = f"{normalise_resref(source_room_resref)}:{int(edge_index)}:{str(opening_name).lower()}"
    hook = next((item for item in authored_room_connection_hooks(updated) if item.hook_id == hook_id), None)
    if hook is None:
        raise ValueError("The matching source doorway could not be created.")
    return updated, hook


def _source_edge_snap_candidates(
    project: AuthoredModuleProject,
    source_room: AuthoredRoomSpec,
    target: AuthoredRoomConnectionHook,
) -> tuple[tuple[AuthoredModuleProject, AuthoredRoomConnectionHook, bool], ...]:
    """Return existing openings first, then legal auto-cut wall candidates."""

    source_resref = _room_name(source_room)
    existing = tuple(
        hook
        for hook in authored_room_connection_hooks(project)
        if hook.room_resref == source_resref
        and hook.passable
        and not hook.connected_room_resref
        and abs(float(hook.width) - float(target.width)) <= max(0.25, min(hook.width, target.width) * 0.25)
        and abs(float(hook.height) - float(target.height)) <= max(0.25, min(hook.height, target.height) * 0.25)
    )
    rows: list[tuple[AuthoredModuleProject, AuthoredRoomConnectionHook, bool]] = [
        (project, hook, False) for hook in existing
    ]
    primitive = _floor_plan_room_primitive(source_room)
    if primitive is None:
        return tuple(rows)
    used_edges = {int(hook.edge_index) for hook in existing}
    for edge_index in range(len(tuple(primitive.points or ()))):
        if edge_index in used_edges:
            continue
        name = f"door_snap_{edge_index}_{target.room_resref}_{target.edge_index}"
        try:
            candidate_project, candidate_hook = _append_drag_snap_opening(
                project,
                source_room_resref=source_resref,
                edge_index=edge_index,
                opening_name=name,
                target=target,
            )
        except ValueError:
            continue
        rows.append((candidate_project, candidate_hook, True))
    return tuple(rows)


def preview_authored_room_drag_snap(
    project: AuthoredModuleProject,
    *,
    source_room_resref: str,
    world_delta: tuple[float, float, float] | list[float],
    snap_distance: float = 2.5,
    target_room_resref: str = "",
    target_edge_index: int = -1,
    target_opening_name: str = "",
) -> AuthoredRoomDragSnapPreview:
    """Solve the closest exact doorway or terrain-edge connection for a room drag."""

    clean_source = normalise_resref(source_room_resref)
    source_room = next((room for room in project.rooms if _room_name(room) == clean_source), None)
    delta_values = tuple(float(value) for value in tuple(world_delta or ())[:3])
    if source_room is not None and _terrain_room_primitive(source_room) is not None and len(delta_values) == 3:
        return _preview_terrain_room_drag_snap(
            project,
            source_room=source_room,
            world_delta=delta_values,
            snap_distance=float(snap_distance),
            target_room_resref=target_room_resref,
        )
    if source_room is None or _floor_plan_room_primitive(source_room) is None or len(delta_values) != 3:
        return AuthoredRoomDragSnapPreview(False, clean_source, reason="Only one authored floor-plan room can doorway-snap at a time.")
    source_origin = tuple(float(value) for value in source_room.position)
    proposed_origin = tuple(source_origin[index] + delta_values[index] for index in range(3))
    clean_target = normalise_resref(target_room_resref)
    wanted_edge = int(target_edge_index)
    wanted_opening = str(target_opening_name or "").strip().lower()
    target_hooks = tuple(
        hook
        for hook in authored_room_connection_hooks(project)
        if hook.room_resref != clean_source and hook.passable and not hook.external and not hook.connected_room_resref
        and (not clean_target or hook.room_resref == clean_target)
        and (
            not wanted_opening
            or str(hook.opening_name or "").strip().lower() == wanted_opening
        )
        and (
            bool(wanted_opening)
            or wanted_edge < 0
            or int(hook.edge_index) == wanted_edge
        )
    )
    if not target_hooks:
        return AuthoredRoomDragSnapPreview(
            False,
            clean_source,
            position=proposed_origin,
            world_delta=delta_values,
            reason="Draw a doorway on the destination room to create a snap target.",
        )
    best: AuthoredRoomDragSnapPreview | None = None
    for target in target_hooks:
        for candidate_project, source_hook, auto_cut in _source_edge_snap_candidates(project, source_room, target):
            try:
                solution = connect_authored_room_openings(
                    candidate_project,
                    source_hook.hook_id,
                    target.hook_id,
                    align_source=True,
                )
            except ValueError:
                continue
            # A doorway has two mathematically aligned source-wall choices.
            # Only the one whose room body remains outside every occupied room
            # is a valid Lego-style placement. Cursor distance alone can pick
            # the mirrored solution and place an entire room through the
            # destination wall.
            from .map_studio_environment_kits import (
                audit_environment_kit_room_occupancy,
            )

            solved_source = next(
                room
                for room in solution.project.rooms
                if _room_name(room) == clean_source
            )
            occupancy = audit_environment_kit_room_occupancy(
                solved_source.primitive,
                position=tuple(float(value) for value in solved_source.position),
                rooms=tuple(
                    room
                    for room in solution.project.rooms
                    if _room_name(room) != clean_source
                ),
                # The destination room necessarily shares a narrow portal
                # throat with the aligned source room. Its overlap is sealed by
                # trim_environment_kit_connection_overlap after commit, so it
                # must not be treated as a room-body collision here.
                ignored_room_resrefs=(target.room_resref,),
            )
            if not bool(occupancy.get("ok", False)):
                continue
            snapped_origin = tuple(source_origin[index] + float(solution.translation[index]) for index in range(3))
            distance = math.sqrt(sum((snapped_origin[index] - proposed_origin[index]) ** 2 for index in range(3)))
            preview = AuthoredRoomDragSnapPreview(
                magnet_snapped=distance <= max(0.05, float(snap_distance)),
                source_room_resref=clean_source,
                target_room_resref=target.room_resref,
                source_hook_id=source_hook.hook_id,
                target_hook_id=target.hook_id,
                source_edge_index=int(source_hook.edge_index),
                target_edge_index=int(target.edge_index),
                source_opening_name=source_hook.opening_name,
                auto_cut_source=auto_cut,
                position=snapped_origin,
                world_delta=tuple(float(value) for value in solution.translation),
                rotation_degrees_z=float(solution.rotation_degrees),
                snap_distance=distance,
                opening_width=float(target.width),
                opening_height=float(target.height),
                target_label=target.label,
                reason=(
                    f"Release to snap wall {source_hook.edge_index + 1} to {target.label}."
                    if distance <= max(0.05, float(snap_distance))
                    else "Move the room closer to a compatible doorway."
                ),
            )
            if best is None or preview.snap_distance < best.snap_distance:
                best = preview
    if best is None:
        return AuthoredRoomDragSnapPreview(
            False,
            clean_source,
            position=proposed_origin,
            world_delta=delta_values,
            reason="No source wall is large enough for the destination doorway.",
        )
    if best.magnet_snapped:
        return best
    return replace(best, position=proposed_origin, world_delta=delta_values)


def connect_authored_room_drag_snap(
    project: AuthoredModuleProject,
    preview: AuthoredRoomDragSnapPreview | dict[str, Any],
) -> AuthoredRoomConnectionUpdate:
    """Commit the exact previewed doorway magnet or terrain edge weld."""

    values = preview.as_payload() if isinstance(preview, AuthoredRoomDragSnapPreview) else dict(preview or {})
    if not bool(values.get("magnet_snapped", False)):
        raise ValueError("Move the room close enough for a doorway magnet before releasing it.")
    if str(values.get("snap_kind") or "doorway").strip().lower() == "terrain_seam":
        return _connect_terrain_room_drag_snap(project, values)
    working = project
    source_hook_id = str(values.get("source_hook_id") or "")
    target_hook_id = str(values.get("target_hook_id") or "")
    if bool(values.get("auto_cut_source", False)):
        hooks = {hook.hook_id: hook for hook in authored_room_connection_hooks(working)}
        target = hooks.get(target_hook_id)
        if target is None:
            raise ValueError("The destination doorway changed before the room was released.")
        working, source_hook = _append_drag_snap_opening(
            working,
            source_room_resref=str(values.get("source_room_resref") or ""),
            edge_index=int(values.get("source_edge_index", -1)),
            opening_name=str(values.get("source_opening_name") or "door_snap"),
            target=target,
        )
        source_hook_id = source_hook.hook_id
    update = connect_authored_room_openings(
        working,
        source_hook_id,
        target_hook_id,
        align_source=True,
    )
    from .map_studio_pascal_graph import refresh_pascal_wall_graph
    from .authored_module_project import compile_authored_room_spec
    from .authored_walkmesh_surfaces import is_walkable_walkmesh_surface

    connected_hooks = {
        (hook.room_resref, hook.opening_name.lower()): hook
        for hook in authored_room_connection_hooks(update.project)
    }
    source_connected = connected_hooks.get((update.source_hook.room_resref, update.source_hook.opening_name.lower()))
    target_connected = connected_hooks.get((update.target_hook.room_resref, update.target_hook.opening_name.lower()))
    if source_connected is None or target_connected is None:
        raise ValueError("The snapped doorway hooks could not be regenerated after alignment.")
    if _hook_distance(source_connected, target_connected) > 1.0e-5 or _hook_facing_dot(source_connected, target_connected) > -0.999:
        raise ValueError("The room doorway seam did not align exactly enough for automatic walkmesh traversal.")
    connected_project = update.project
    try:
        from .map_studio_pascal_building import pascal_architecture_profile_for_room
        from .map_studio_terrain_kit import module_transition_asset_for_profiles

        source_profile = pascal_architecture_profile_for_room(
            connected_project,
            source_connected.room_resref,
        )
        target_profile = pascal_architecture_profile_for_room(
            connected_project,
            target_connected.room_resref,
        )
        source_transition_asset = module_transition_asset_for_profiles(
            source_profile,
            target_profile,
        )
        target_transition_asset = module_transition_asset_for_profiles(
            target_profile,
            source_profile,
        )
        open_transition_asset = source_transition_asset or target_transition_asset
    except Exception:
        source_profile = ""
        target_profile = ""
        source_transition_asset = ""
        target_transition_asset = ""
        open_transition_asset = ""
    if open_transition_asset and (
        source_profile in {"korriban_caves_k1", "korriban_caves_k2"}
        or target_profile in {"korriban_caves_k1", "korriban_caves_k2"}
    ):
        connected_project = _suppress_open_transition_door(connected_project, source_connected)
        refreshed_hooks = {
            (hook.room_resref, hook.opening_name.lower()): hook
            for hook in authored_room_connection_hooks(connected_project)
        }
        source_connected = refreshed_hooks.get(
            (source_connected.room_resref, source_connected.opening_name.lower()),
            source_connected,
        )
        target_connected = refreshed_hooks.get(
            (target_connected.room_resref, target_connected.opening_name.lower()),
            target_connected,
        )
        connected_project = _suppress_open_transition_door(connected_project, target_connected)
        transition_candidates = (
            (
                target_connected,
                source_profile,
                "authored_target_room",
                target_transition_asset,
            ),
            (
                source_connected,
                target_profile,
                "authored_source_room",
                source_transition_asset,
            ),
        )
        selected_transition = next(
            (
                candidate
                for candidate in transition_candidates
                if int(candidate[0].edge_index) >= 0 and candidate[3]
            ),
            None,
        )
        for hook in (source_connected, target_connected):
            if int(hook.edge_index) < 0:
                continue
            _room, opening = _room_opening_for_hook(connected_project, hook)
            metadata = dict(opening.metadata or {})
            for key in (
                "module_transition_asset_id",
                "module_transition_target_profile",
                "module_transition_owner",
            ):
                metadata.pop(key, None)
            if selected_transition is not None and hook.hook_id == selected_transition[0].hook_id:
                _selected_hook, target_profile_value, owner, transition_asset = selected_transition
                metadata.update(
                    {
                        "module_transition_asset_id": transition_asset,
                        "module_transition_target_profile": target_profile_value,
                        "module_transition_floor_required": True,
                        "module_transition_owner": owner,
                    }
                )
            connected_project = _replace_opening_metadata(
                connected_project,
                hook,
                metadata,
            )
        update = replace(update, project=connected_project)
    _room, connected_source_opening = _room_opening_for_hook(connected_project, source_connected)
    connected_source_metadata = dict(connected_source_opening.metadata or {})
    door_template = str(connected_source_metadata.get("door_template_resref") or "").strip().lower()
    has_connection_door = bool(
        connected_source_metadata.get("door_placement_id")
        or connected_source_metadata.get("shared_door_placement_id")
    )
    if door_template and not has_connection_door:
        from .authored_module_placements import add_authored_gameplay_placement

        door_position, door_bearing = _sealed_door_pose(connected_project, source_connected)
        door_update = add_authored_gameplay_placement(
            connected_project,
            kind="door",
            template_resref=door_template,
            tag=f"{source_connected.room_resref}_{source_connected.opening_name}"[:32],
            position=door_position,
            bearing=door_bearing,
        )
        connected_project = door_update.project
        _room, connected_source_opening = _room_opening_for_hook(
            connected_project,
            source_connected,
        )
        connected_source_metadata = dict(connected_source_opening.metadata or {})
        connected_source_metadata.update(
            {
                "door_placement_id": door_update.placement_id,
                "cross_style_transition_actor": bool(
                    connected_source_metadata.get("cross_style_transition")
                ),
            }
        )
        connected_project = _replace_opening_metadata(
            connected_project,
            source_connected,
            connected_source_metadata,
        )
        update = replace(update, project=connected_project)
    walkable_counts: dict[str, int] = {}
    for room_resref in (source_connected.room_resref, target_connected.room_resref):
        room = next(item for item in update.project.rooms if _room_name(item) == room_resref)
        geometry = compile_authored_room_spec(room)
        count = sum(
            1
            for face in tuple(getattr(getattr(geometry, "wok", None), "faces", ()) or ())
            if is_walkable_walkmesh_surface(int(getattr(face, "surface", -1)))
        )
        if count <= 0:
            raise ValueError(f"Room {room_resref} generated no WOK faces at the snapped doorway.")
        walkable_counts[room_resref] = count
    connected_project = update.project
    connected_extra = dict(connected_project.extra or {})
    connected_extra["last_room_connection"] = {
        "source_room_resref": source_connected.room_resref,
        "target_room_resref": target_connected.room_resref,
        "source_opening_name": source_connected.opening_name,
        "target_opening_name": target_connected.opening_name,
        "portal_position": [float(value) for value in source_connected.position],
        "opening_width": float(source_connected.width),
        "opening_height": float(source_connected.height),
        "walkmesh_auto_generated": True,
        "walkmesh_portal_validated": True,
        "walkable_face_counts": walkable_counts,
        "assembly_mode": "seamless_room_lego",
    }
    connected_project = refresh_pascal_wall_graph(replace(connected_project, extra=connected_extra))
    return replace(update, project=connected_project)


def _reconcile_connected_door_placements(
    before: AuthoredModuleProject,
    after: AuthoredModuleProject,
    *,
    source: AuthoredRoomConnectionHook,
    target: AuthoredRoomConnectionHook,
    old_source_position: tuple[float, float, float],
    new_source_position: tuple[float, float, float],
    rotation_degrees: float,
) -> AuthoredModuleProject:
    """Keep a room-owned door with its wall and prevent doubled seam actors."""

    source_metadata = _opening_metadata_for_hook(before, source)
    target_metadata = _opening_metadata_for_hook(before, target)
    source_door_id = str(source_metadata.get("door_placement_id") or "").strip()
    target_door_id = str(target_metadata.get("door_placement_id") or "").strip()
    updated = after
    if target_door_id and not source_door_id:
        _room, connected_opening = _room_opening_for_hook(updated, source)
        metadata = dict(connected_opening.metadata or {})
        metadata.update(
            {
                "shared_connection_door": True,
                "shared_door_placement_id": target_door_id,
            }
        )
        return _replace_opening_metadata(updated, source, metadata)
    if not source_door_id:
        return updated

    from .authored_module_placements import (
        authored_gameplay_placement_rows,
        remove_authored_gameplay_placement,
        update_authored_gameplay_placement_transform,
    )

    if target_door_id and target_door_id != source_door_id:
        updated = remove_authored_gameplay_placement(updated, source_door_id).project
        _room, connected_opening = _room_opening_for_hook(updated, source)
        metadata = dict(connected_opening.metadata or {})
        metadata.pop("door_placement_id", None)
        metadata.update(
            {
                "shared_connection_door": True,
                "shared_door_placement_id": target_door_id,
                "deduplicated_source_door": source_door_id,
            }
        )
        return _replace_opening_metadata(updated, source, metadata)

    row = next(
        (item for item in authored_gameplay_placement_rows(before) if item.placement_id == source_door_id),
        None,
    )
    if row is None:
        return updated
    radians = math.radians(float(rotation_degrees))
    cos_a = math.cos(radians)
    sin_a = math.sin(radians)
    local_x = float(row.position[0]) - float(old_source_position[0])
    local_y = float(row.position[1]) - float(old_source_position[1])
    local_z = float(row.position[2]) - float(old_source_position[2])
    position = (
        float(new_source_position[0]) + local_x * cos_a - local_y * sin_a,
        float(new_source_position[1]) + local_x * sin_a + local_y * cos_a,
        float(new_source_position[2]) + local_z,
    )
    return update_authored_gameplay_placement_transform(
        updated,
        source_door_id,
        position=position,
        bearing=float(row.bearing) + radians,
    ).project


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
    source_room_before = source_room
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
    if target.edge_index >= 0:
        target_room = _replace_room_opening(
            target_room,
            edge_index=target.edge_index,
            opening_name=target.opening_name,
            target=source,
        )
    else:
        target_room = _replace_stock_room_opening(
            target_room,
            hook=target,
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
    updated = _reconcile_connected_door_placements(
        project,
        updated,
        source=source,
        target=target,
        old_source_position=tuple(float(value) for value in source_room_before.position),
        new_source_position=tuple(float(value) for value in source_room.position),
        rotation_degrees=rotation_degrees,
    )
    # A module transition is owned by exactly one side of the reciprocal
    # portal. Keeping the mirrored visual shell on the dragged/source room
    # avoids coplanar duplicates while the two generated WOKs continue to own
    # traversal and collision.
    from .map_studio_pascal_building import pascal_architecture_profile_for_room
    from .map_studio_terrain_kit import module_transition_asset_for_profiles

    source_profile = pascal_architecture_profile_for_room(updated, source.room_resref)
    target_profile = pascal_architecture_profile_for_room(updated, target.room_resref)
    transition_asset_id = module_transition_asset_for_profiles(source_profile, target_profile)
    if transition_asset_id:
        _room, connected_source_opening = _room_opening_for_hook(updated, source)
        source_metadata = dict(connected_source_opening.metadata or {})
        source_metadata.update(
            {
                "module_transition_asset_id": transition_asset_id,
                "module_transition_target_profile": target_profile,
                "module_transition_floor_required": True,
                "module_transition_owner": "source_room",
            }
        )
        updated = _replace_opening_metadata(updated, source, source_metadata)
        target_metadata = _opening_metadata_for_hook(updated, target)
        for key in (
            "module_transition_asset_id",
            "module_transition_target_profile",
            "module_transition_floor_required",
            "module_transition_owner",
        ):
            target_metadata.pop(key, None)
        updated = _replace_hook_metadata(updated, target, target_metadata)
    from .authored_module_walkmesh import (
        compile_authored_room_connection_walkmeshes,
        upsert_authored_walkmesh_room_connection,
    )

    updated = upsert_authored_walkmesh_room_connection(
        updated,
        source_room_resref=source.room_resref,
        source_hook_name=source.opening_name,
        target_room_resref=target.room_resref,
        target_hook_name=target.opening_name,
        connection_source="map_studio_authored_openings",
    )
    walkmesh_build = compile_authored_room_connection_walkmeshes(updated)
    if not walkmesh_build.ready:
        raise ValueError(" ".join(walkmesh_build.blocking_issues))
    updated_extra = dict(updated.extra or {})
    updated_extra["last_walkmesh_build"] = {
        "operation": "connect_authored_room_openings",
        "auto_generated": True,
        "portal_count": len(walkmesh_build.portals),
        "room_face_counts": {
            room_resref: len(tuple(wok.faces or ()))
            for room_resref, wok in walkmesh_build.room_woks.items()
        },
        "midpoint_gaps_m": [float(portal.midpoint_gap) for portal in walkmesh_build.portals],
        "ready": True,
    }
    updated = replace(updated, extra=updated_extra)
    summary = (
        f"Connected {source.label} to {target.label}; aligned the source room, "
        "persisted both opening links, added symmetric VIS intent, and generated reciprocal WOK portals."
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
    "AuthoredRoomOpeningIntentUpdate",
    "AuthoredRoomDragSnapPreview",
    "AuthoredModuleLayout",
    "AuthoredModuleLayoutValidation",
    "audit_authored_room_connections",
    "auto_arrange_authored_rooms",
    "authored_room_connection_hooks",
    "compile_authored_module_layout",
    "connect_authored_room_openings",
    "connect_authored_room_drag_snap",
    "preview_authored_room_drag_snap",
    "set_authored_room_opening_intent",
    "snap_authored_rooms_to_grid",
    "validate_authored_module_layout",
]
