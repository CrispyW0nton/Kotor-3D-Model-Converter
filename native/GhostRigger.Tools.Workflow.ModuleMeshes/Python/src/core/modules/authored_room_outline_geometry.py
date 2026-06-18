"""Renderable outline geometry for authored Map Studio rooms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .authored_module_project import AuthoredModuleProject, AuthoredRoomSpec, normalise_resref
from .authored_room_floorplan import FloorPlanRoomPrimitive
from .authored_room_geometry import RectangularRoomPrimitive


Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class AuthoredRoomOutlinePolygon:
    """One projected room outline polygon for viewport overlays."""

    room_resref: str
    label: str
    points: tuple[Vec3, ...]
    color: str
    role: str = "floor"


@dataclass(frozen=True)
class AuthoredRoomOutlineLine:
    """One room guide line, such as a wall height or doorway span."""

    room_resref: str
    label: str
    start: Vec3
    end: Vec3
    color: str
    role: str


@dataclass(frozen=True)
class AuthoredRoomOutlineGeometry:
    """UI/renderer-ready room outline data for authored Map Studio rooms."""

    room_count: int = 0
    polygons: tuple[AuthoredRoomOutlinePolygon, ...] = ()
    lines: tuple[AuthoredRoomOutlineLine, ...] = ()
    warnings: tuple[str, ...] = ()


def _room_offset(room: AuthoredRoomSpec) -> Vec3:
    value = tuple(room.position or (0.0, 0.0, 0.0))
    if len(value) < 3:
        return (0.0, 0.0, 0.0)
    return (float(value[0]), float(value[1]), float(value[2]))


def _offset_point(point: tuple[float, float], z: float, offset: Vec3) -> Vec3:
    return (float(point[0]) + offset[0], float(point[1]) + offset[1], float(z) + offset[2])


def _rectangular_points(primitive: RectangularRoomPrimitive, offset: Vec3) -> tuple[Vec3, ...]:
    half_w = float(primitive.width) * 0.5
    half_d = float(primitive.depth) * 0.5
    return (
        (-half_w + offset[0], -half_d + offset[1], offset[2]),
        (half_w + offset[0], -half_d + offset[1], offset[2]),
        (half_w + offset[0], half_d + offset[1], offset[2]),
        (-half_w + offset[0], half_d + offset[1], offset[2]),
    )


def _floor_plan_points(primitive: FloorPlanRoomPrimitive, offset: Vec3) -> tuple[Vec3, ...]:
    return tuple(_offset_point((float(x), float(y)), float(primitive.z), offset) for x, y in tuple(primitive.points or ()))


def _wall_height(primitive: Any) -> float:
    return max(0.0, float(getattr(primitive, "wall_height", 0.0) or 0.0))


def _top_points(points: tuple[Vec3, ...], wall_height: float) -> tuple[Vec3, ...]:
    return tuple((float(x), float(y), float(z) + wall_height) for x, y, z in points)


def _wall_lines(room_resref: str, label: str, points: tuple[Vec3, ...], wall_height: float, color: str) -> tuple[AuthoredRoomOutlineLine, ...]:
    if wall_height <= 0.0:
        return ()
    return tuple(
        AuthoredRoomOutlineLine(
            room_resref=room_resref,
            label=label,
            start=point,
            end=(point[0], point[1], point[2] + wall_height),
            color=color,
            role="wall_height",
        )
        for point in points
    )


def _opening_lines(room: AuthoredRoomSpec, primitive: FloorPlanRoomPrimitive, points: tuple[Vec3, ...]) -> tuple[AuthoredRoomOutlineLine, ...]:
    room_resref = normalise_resref(room.room_resref)
    label = room_resref or "room"
    lines: list[AuthoredRoomOutlineLine] = []
    for opening in tuple(primitive.openings or ()):
        edge_index = int(opening.edge_index)
        if edge_index < 0 or edge_index >= len(points):
            continue
        start = points[edge_index]
        end = points[(edge_index + 1) % len(points)]
        edge_x = end[0] - start[0]
        edge_y = end[1] - start[1]
        edge_len = max((edge_x * edge_x + edge_y * edge_y) ** 0.5, 1.0e-7)
        half_fraction = (float(opening.width) * 0.5) / edge_len
        center = float(opening.center_fraction)
        a = max(0.0, min(1.0, center - half_fraction))
        b = max(0.0, min(1.0, center + half_fraction))
        z = float(start[2]) + float(opening.bottom)
        lines.append(
            AuthoredRoomOutlineLine(
                room_resref=room_resref,
                label=str(opening.name or label),
                start=(start[0] + edge_x * a, start[1] + edge_y * a, z),
                end=(start[0] + edge_x * b, start[1] + edge_y * b, z),
                color="#ffcf40",
                role="opening",
            )
        )
    return tuple(lines)


def authored_room_outline_geometry_for_project(project: AuthoredModuleProject) -> AuthoredRoomOutlineGeometry:
    """Return viewport overlay outlines for authored rooms."""

    polygons: list[AuthoredRoomOutlinePolygon] = []
    lines: list[AuthoredRoomOutlineLine] = []
    warnings: list[str] = []
    for room in tuple(project.rooms or ()):
        room_resref = normalise_resref(room.room_resref)
        label = room_resref or "room"
        primitive = room.primitive
        offset = _room_offset(room)
        color = "#42d9ff"
        if isinstance(primitive, FloorPlanRoomPrimitive):
            points = _floor_plan_points(primitive, offset)
            color = "#52ff7a"
        elif isinstance(primitive, RectangularRoomPrimitive):
            points = _rectangular_points(primitive, offset)
        else:
            warnings.append(f"Room {label} has no viewport outline for primitive type {type(primitive).__name__}.")
            continue
        if len(points) < 3:
            warnings.append(f"Room {label} needs at least three outline points.")
            continue
        polygons.append(AuthoredRoomOutlinePolygon(room_resref=room_resref, label=label, points=points, color=color, role="floor"))
        wall_height = _wall_height(primitive)
        if wall_height > 0.0:
            polygons.append(
                AuthoredRoomOutlinePolygon(
                    room_resref=room_resref,
                    label=label,
                    points=_top_points(points, wall_height),
                    color="#8be9fd",
                    role="ceiling",
                )
            )
            lines.extend(_wall_lines(room_resref, label, points, wall_height, "#8be9fd"))
        if isinstance(primitive, FloorPlanRoomPrimitive):
            lines.extend(_opening_lines(room, primitive, points))
    return AuthoredRoomOutlineGeometry(
        room_count=len(tuple(project.rooms or ())),
        polygons=tuple(polygons),
        lines=tuple(lines),
        warnings=tuple(warnings),
    )


__all__ = [
    "AuthoredRoomOutlineGeometry",
    "AuthoredRoomOutlineLine",
    "AuthoredRoomOutlinePolygon",
    "authored_room_outline_geometry_for_project",
]
