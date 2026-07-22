"""Deterministic planar wall graph for Map Studio's Pascal-style builder.

The editable room polygons remain the current Odyssey compile target.  This
module planarizes their shared wall network at T-junctions/intersections and
stores a compact stable-ID graph in KMAP, giving later 2D/3D tools one semantic
source of truth without persisting derived render meshes.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import replace
from typing import Any

from .authored_module_project import AuthoredModuleProject, AuthoredRoomSpec, normalise_resref
from .authored_room_floorplan import FloorPlanRoomPrimitive, FloorPlanWallOpening


Vec2 = tuple[float, float]


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "|".join(str(part) for part in parts).encode("utf-8", errors="replace")
    return f"{prefix}_{hashlib.sha1(payload).hexdigest()[:12]}"


def _room_offset(room: AuthoredRoomSpec) -> tuple[float, float, float]:
    values = tuple(room.position or (0.0, 0.0, 0.0))
    return tuple(float(values[index]) if index < len(values) else 0.0 for index in range(3))


def _world_points(room: AuthoredRoomSpec, primitive: FloorPlanRoomPrimitive) -> tuple[Vec2, ...]:
    offset = _room_offset(room)
    return tuple((float(x) + offset[0], float(y) + offset[1]) for x, y in primitive.points)


def _level_z(room: AuthoredRoomSpec, primitive: FloorPlanRoomPrimitive) -> float:
    return float(primitive.z) + _room_offset(room)[2]


def _point_fraction_on_segment(point: Vec2, start: Vec2, end: Vec2, tolerance: float) -> float | None:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= tolerance * tolerance:
        return None
    fraction = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq
    endpoint_margin = tolerance / max(math.sqrt(length_sq), tolerance)
    if fraction <= endpoint_margin or fraction >= 1.0 - endpoint_margin:
        return None
    closest = (start[0] + dx * fraction, start[1] + dy * fraction)
    if math.hypot(point[0] - closest[0], point[1] - closest[1]) > tolerance:
        return None
    return fraction


def _proper_segment_intersection(a0: Vec2, a1: Vec2, b0: Vec2, b1: Vec2, tolerance: float) -> tuple[float, float] | None:
    adx, ady = a1[0] - a0[0], a1[1] - a0[1]
    bdx, bdy = b1[0] - b0[0], b1[1] - b0[1]
    denominator = adx * bdy - ady * bdx
    scale = max(math.hypot(adx, ady) * math.hypot(bdx, bdy), 1.0)
    if abs(denominator) <= tolerance * scale:
        return None
    dx, dy = b0[0] - a0[0], b0[1] - a0[1]
    first = (dx * bdy - dy * bdx) / denominator
    second = (dx * ady - dy * adx) / denominator
    first_margin = tolerance / max(math.hypot(adx, ady), tolerance)
    second_margin = tolerance / max(math.hypot(bdx, bdy), tolerance)
    if not (first_margin < first < 1.0 - first_margin and second_margin < second < 1.0 - second_margin):
        return None
    return first, second


def _floor_plan_rows(project: AuthoredModuleProject) -> tuple[tuple[int, AuthoredRoomSpec, FloorPlanRoomPrimitive], ...]:
    return tuple(
        (index, room, room.primitive)
        for index, room in enumerate(project.rooms)
        if isinstance(room.primitive, FloorPlanRoomPrimitive)
    )


def _collect_wall_splits(
    project: AuthoredModuleProject,
    *,
    tolerance: float,
) -> dict[tuple[int, int], set[float]]:
    edges: list[tuple[int, int, float, Vec2, Vec2]] = []
    for room_index, room, primitive in _floor_plan_rows(project):
        points = _world_points(room, primitive)
        level = _level_z(room, primitive)
        for edge_index, start in enumerate(points):
            edges.append((room_index, edge_index, level, start, points[(edge_index + 1) % len(points)]))
    splits: dict[tuple[int, int], set[float]] = {}
    for first_index, first in enumerate(edges):
        first_room, first_edge, first_level, a0, a1 = first
        for second in edges[first_index + 1 :]:
            second_room, second_edge, second_level, b0, b1 = second
            if first_room == second_room or abs(first_level - second_level) > tolerance:
                continue
            for point in (b0, b1):
                fraction = _point_fraction_on_segment(point, a0, a1, tolerance)
                if fraction is not None:
                    splits.setdefault((first_room, first_edge), set()).add(fraction)
            for point in (a0, a1):
                fraction = _point_fraction_on_segment(point, b0, b1, tolerance)
                if fraction is not None:
                    splits.setdefault((second_room, second_edge), set()).add(fraction)
            intersection = _proper_segment_intersection(a0, a1, b0, b1, tolerance)
            if intersection is not None:
                splits.setdefault((first_room, first_edge), set()).add(intersection[0])
                splits.setdefault((second_room, second_edge), set()).add(intersection[1])
    return splits


def _migrate_opening(
    opening: FloorPlanWallOpening,
    *,
    old_edge_index: int,
    old_edge_length: float,
    segment_bounds: tuple[tuple[float, float, int], ...],
    tolerance: float,
) -> FloorPlanWallOpening:
    half = float(opening.width) * 0.5 / max(old_edge_length, tolerance)
    opening_start = float(opening.center_fraction) - half
    opening_end = float(opening.center_fraction) + half
    margin = max(tolerance / max(old_edge_length, tolerance), 1.0e-7)
    for segment_start, segment_end, new_edge_index in segment_bounds:
        if opening_start > segment_start + margin and opening_end < segment_end - margin:
            local_fraction = (float(opening.center_fraction) - segment_start) / (segment_end - segment_start)
            return replace(
                opening,
                edge_index=new_edge_index,
                center_fraction=local_fraction,
                metadata={
                    **dict(opening.metadata),
                    "pascal_split_from_edge_index": int(old_edge_index),
                    "pascal_split_segment": [float(segment_start), float(segment_end)],
                },
            )
    label = str(opening.name or f"edge {old_edge_index}").replace("_", " ")
    raise ValueError(f"A new wall junction would cross or touch hosted opening {label}; move the opening or junction first.")


def _split_floor_plan_room(
    room_index: int,
    room: AuthoredRoomSpec,
    primitive: FloorPlanRoomPrimitive,
    splits: dict[tuple[int, int], set[float]],
    *,
    tolerance: float,
) -> tuple[AuthoredRoomSpec, int]:
    source_points = tuple((float(x), float(y)) for x, y in primitive.points)
    new_points: list[Vec2] = []
    edge_segments: dict[int, tuple[tuple[float, float, int], ...]] = {}
    inserted = 0
    for edge_index, start in enumerate(source_points):
        end = source_points[(edge_index + 1) % len(source_points)]
        fractions = sorted(
            fraction
            for fraction in splits.get((room_index, edge_index), ())
            if tolerance < fraction < 1.0 - tolerance
        )
        base_edge_index = len(new_points)
        new_points.append(start)
        for fraction in fractions:
            new_points.append(
                (start[0] + (end[0] - start[0]) * fraction, start[1] + (end[1] - start[1]) * fraction)
            )
        bounds = (0.0, *fractions, 1.0)
        edge_segments[edge_index] = tuple(
            (bounds[index], bounds[index + 1], base_edge_index + index)
            for index in range(len(bounds) - 1)
        )
        inserted += len(fractions)
    if inserted <= 0:
        return room, 0
    openings: list[FloorPlanWallOpening] = []
    for opening in primitive.openings:
        old_edge = int(opening.edge_index)
        start = source_points[old_edge]
        end = source_points[(old_edge + 1) % len(source_points)]
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        openings.append(
            _migrate_opening(
                opening,
                old_edge_index=old_edge,
                old_edge_length=length,
                segment_bounds=edge_segments[old_edge],
                tolerance=tolerance,
            )
        )
    updated_primitive = replace(
        primitive,
        points=tuple(new_points),
        openings=tuple(openings),
        metadata={
            **dict(primitive.metadata),
            "pascal_graph_planarized": True,
            "pascal_graph_inserted_vertex_count": inserted,
        },
    )
    return (
        replace(
            room,
            primitive=updated_primitive,
            composition=None,
            metadata={
                **dict(room.metadata),
                "pascal_graph_planarized": True,
                "pascal_graph_inserted_vertex_count": inserted,
            },
        ),
        inserted,
    )


def _vertex_key(level: float, point: Vec2, tolerance: float) -> tuple[int, int, int]:
    scale = 1.0 / max(tolerance, 1.0e-7)
    return round(level * scale), round(point[0] * scale), round(point[1] * scale)


def build_pascal_wall_graph(project: AuthoredModuleProject, *, tolerance: float = 0.001) -> dict[str, Any]:
    """Derive stable semantic vertices, shared walls, faces, and openings."""

    vertex_rows: dict[tuple[int, int, int], dict[str, Any]] = {}
    wall_rows: dict[tuple[str, str], dict[str, Any]] = {}
    face_rows: list[dict[str, Any]] = []
    for _room_index, room, primitive in _floor_plan_rows(project):
        room_resref = normalise_resref(room.room_resref)
        points = _world_points(room, primitive)
        level = _level_z(room, primitive)
        vertex_ids: list[str] = []
        for point in points:
            key = _vertex_key(level, point, tolerance)
            row = vertex_rows.get(key)
            if row is None:
                vertex_id = _stable_id("pgv", key[0], key[1], key[2])
                row = {
                    "vertex_id": vertex_id,
                    "position": [float(point[0]), float(point[1]), float(level)],
                }
                vertex_rows[key] = row
            vertex_ids.append(str(row["vertex_id"]))
        face_wall_ids: list[str] = []
        for edge_index, start_vertex_id in enumerate(vertex_ids):
            end_vertex_id = vertex_ids[(edge_index + 1) % len(vertex_ids)]
            wall_key = tuple(sorted((start_vertex_id, end_vertex_id)))
            wall = wall_rows.get(wall_key)
            if wall is None:
                wall_id = _stable_id("pgw", *wall_key)
                wall = {
                    "wall_id": wall_id,
                    "start_vertex_id": start_vertex_id,
                    "end_vertex_id": end_vertex_id,
                    "room_edges": [],
                    "openings": [],
                }
                wall_rows[wall_key] = wall
            wall["room_edges"].append({"room_resref": room_resref, "edge_index": edge_index})
            for opening in primitive.openings:
                if int(opening.edge_index) != edge_index:
                    continue
                wall["openings"].append(
                    {
                        "room_resref": room_resref,
                        "name": str(opening.name or ""),
                        "kind": str(opening.metadata.get("opening_kind", "opening") or "opening"),
                        "center_fraction": float(opening.center_fraction),
                        "width": float(opening.width),
                        "height": float(opening.height),
                        "bottom": float(opening.bottom),
                    }
                )
            face_wall_ids.append(str(wall["wall_id"]))
        face_rows.append(
            {
                "face_id": _stable_id("pgf", room_resref),
                "room_resref": room_resref,
                "level_index": int(primitive.metadata.get("building_level_index", 0) or 0),
                "wall_ids": face_wall_ids,
            }
        )
    degree: dict[str, int] = {}
    for wall in wall_rows.values():
        for vertex_id in (wall["start_vertex_id"], wall["end_vertex_id"]):
            degree[vertex_id] = degree.get(vertex_id, 0) + 1
    vertices = sorted(vertex_rows.values(), key=lambda row: str(row["vertex_id"]))
    walls = sorted(wall_rows.values(), key=lambda row: str(row["wall_id"]))
    return {
        "schema_version": 1,
        "source": "map_studio:pascal_wall_graph",
        "vertices": vertices,
        "walls": walls,
        "faces": sorted(face_rows, key=lambda row: str(row["face_id"])),
        "junction_vertex_ids": sorted(vertex_id for vertex_id, count in degree.items() if count >= 3),
        "vertex_count": len(vertices),
        "wall_count": len(walls),
        "face_count": len(face_rows),
    }


def refresh_pascal_wall_graph(project: AuthoredModuleProject, *, tolerance: float = 0.001) -> AuthoredModuleProject:
    graph = build_pascal_wall_graph(project, tolerance=tolerance)
    return replace(project, extra={**dict(project.extra), "pascal_wall_graph": graph})


def planarize_pascal_building_rooms(project: AuthoredModuleProject, *, tolerance: float = 0.001) -> AuthoredModuleProject:
    """Split shared walls at T/cross junctions and preserve hosted openings."""

    clean_tolerance = max(float(tolerance), 1.0e-6)
    splits = _collect_wall_splits(project, tolerance=clean_tolerance)
    rooms = list(project.rooms)
    inserted_total = 0
    for room_index, room, primitive in _floor_plan_rows(project):
        rooms[room_index], inserted = _split_floor_plan_room(
            room_index,
            room,
            primitive,
            splits,
            tolerance=clean_tolerance,
        )
        inserted_total += inserted
    updated = replace(project, rooms=tuple(rooms))
    graph = build_pascal_wall_graph(updated, tolerance=clean_tolerance)
    graph["inserted_vertex_count"] = inserted_total
    return replace(updated, extra={**dict(updated.extra), "pascal_wall_graph": graph})


__all__ = [
    "build_pascal_wall_graph",
    "planarize_pascal_building_rooms",
    "refresh_pascal_wall_graph",
]
