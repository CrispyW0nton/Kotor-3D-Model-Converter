"""Authored floor-plan extrusion primitives for Map Studio.

This module is the headless contract for drawing a room footprint and turning
it into exportable room geometry.  The first pass intentionally supports
convex floor plans: that gives Map Studio a deterministic primitive for simple
rooms now, while leaving concave decomposition and boolean tools as explicit
future operations instead of hidden guesses.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .authored_room_geometry import AuthoredRoomGeometry, Face, PrimitiveMesh, Vec2, Vec3
from .authored_room_primitives import PrimitiveMaterial
from .authored_walkmesh_surfaces import require_walkable_walkmesh_surface, resolve_walkmesh_surface_id, walkmesh_surface_name
from .module_format import WOKData, WOKFace


@dataclass(frozen=True)
class FloorPlanWallOpening:
    """Door/window-like opening cut into one generated floor-plan wall edge."""

    name: str
    edge_index: int
    center_fraction: float = 0.5
    width: float = 1.5
    height: float = 2.1
    bottom: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FloorPlanRoomPrimitive:
    """Editable intent for one extruded room footprint."""

    room_resref: str
    points: tuple[Vec2, ...]
    z: float = 0.0
    wall_height: float = 3.0
    floor_surface_id: int | str = 4
    material: PrimitiveMaterial = field(default_factory=PrimitiveMaterial)
    wall_material: PrimitiveMaterial | None = None
    ceiling_material: PrimitiveMaterial | None = None
    include_walls: bool = True
    include_ceiling: bool = False
    openings: tuple[FloorPlanWallOpening, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FloorPlanInsetOperation:
    """Inward offset operation for a convex authored floor-plan footprint."""

    distance: float
    room_resref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FloorPlanBevelOperation:
    """Corner chamfer operation for a convex authored floor-plan footprint."""

    distance: float
    room_resref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FloorPlanEdgeExtrudeOperation:
    """Outward pull operation for one convex floor-plan edge."""

    edge_index: int
    distance: float
    room_resref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FloorPlanRectangularCutOperation:
    """Boolean difference cut for an axis-aligned rectangular floor plan."""

    center: Vec2
    size: Vec2
    room_resref_prefix: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FloorPlanAxisSplitOperation:
    """Split an axis-aligned rectangular floor plan into two exportable rooms."""

    axis: str
    coordinate: float
    room_resref_prefix: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FloorPlanRectangularUnionOperation:
    """Boolean union for rectangular floor plans that remain one rectangle."""

    room_resref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FloorPlanRoomValidation:
    """Validation result for a floor-plan room primitive."""

    ok: bool
    area: float = 0.0
    warnings: tuple[str, ...] = ()
    blocking_issues: tuple[str, ...] = ()


def _normalise_resref(value: Any) -> str:
    return str(value or "").strip().lower()[:16]


def _normalise_points(points: tuple[Vec2, ...]) -> tuple[Vec2, ...]:
    return tuple((float(x), float(y)) for x, y in points)


def polygon_signed_area(points: tuple[Vec2, ...]) -> float:
    """Return signed XY area; positive means counter-clockwise."""

    if len(points) < 3:
        return 0.0
    area = 0.0
    for index, (x0, y0) in enumerate(points):
        x1, y1 = points[(index + 1) % len(points)]
        area += (x0 * y1) - (x1 * y0)
    return area * 0.5


def _cross_z(a: Vec2, b: Vec2, c: Vec2) -> float:
    abx = b[0] - a[0]
    aby = b[1] - a[1]
    bcx = c[0] - b[0]
    bcy = c[1] - b[1]
    return (abx * bcy) - (aby * bcx)


def _is_convex(points: tuple[Vec2, ...]) -> bool:
    if len(points) < 4:
        return True
    sign = 0
    for index in range(len(points)):
        cross = _cross_z(points[index - 1], points[index], points[(index + 1) % len(points)])
        if abs(cross) <= 1.0e-7:
            continue
        current = 1 if cross > 0 else -1
        if sign and current != sign:
            return False
        sign = current
    return True


def _has_duplicate_or_zero_edges(points: tuple[Vec2, ...]) -> bool:
    seen: set[Vec2] = set()
    for index, point in enumerate(points):
        if point in seen:
            return True
        seen.add(point)
        next_point = points[(index + 1) % len(points)]
        if abs(point[0] - next_point[0]) <= 1.0e-7 and abs(point[1] - next_point[1]) <= 1.0e-7:
            return True
    return False


def _ccw_points(points: tuple[Vec2, ...]) -> tuple[Vec2, ...]:
    return points if polygon_signed_area(points) > 0.0 else tuple(reversed(points))


def _fan_faces(point_count: int) -> tuple[Face, ...]:
    return tuple((0, index, index + 1) for index in range(1, point_count - 1))


def _orientation(a: Vec2, b: Vec2, c: Vec2) -> float:
    return ((b[0] - a[0]) * (c[1] - a[1])) - ((b[1] - a[1]) * (c[0] - a[0]))


def _point_on_segment(point: Vec2, start: Vec2, end: Vec2) -> bool:
    if abs(_orientation(start, end, point)) > 1.0e-8:
        return False
    return (
        min(start[0], end[0]) - 1.0e-8 <= point[0] <= max(start[0], end[0]) + 1.0e-8
        and min(start[1], end[1]) - 1.0e-8 <= point[1] <= max(start[1], end[1]) + 1.0e-8
    )


def _segments_intersect(first_a: Vec2, first_b: Vec2, second_a: Vec2, second_b: Vec2) -> bool:
    o1 = _orientation(first_a, first_b, second_a)
    o2 = _orientation(first_a, first_b, second_b)
    o3 = _orientation(second_a, second_b, first_a)
    o4 = _orientation(second_a, second_b, first_b)
    if ((o1 > 1.0e-8 and o2 < -1.0e-8) or (o1 < -1.0e-8 and o2 > 1.0e-8)) and (
        (o3 > 1.0e-8 and o4 < -1.0e-8) or (o3 < -1.0e-8 and o4 > 1.0e-8)
    ):
        return True
    return any(
        (
            abs(value) <= 1.0e-8
            and _point_on_segment(point, start, end)
        )
        for value, point, start, end in (
            (o1, second_a, first_a, first_b),
            (o2, second_b, first_a, first_b),
            (o3, first_a, second_a, second_b),
            (o4, first_b, second_a, second_b),
        )
    )


def _has_self_intersections(points: tuple[Vec2, ...]) -> bool:
    count = len(points)
    for first_index in range(count):
        first_next = (first_index + 1) % count
        for second_index in range(first_index + 1, count):
            second_next = (second_index + 1) % count
            if first_index in {second_index, second_next} or first_next in {second_index, second_next}:
                continue
            if _segments_intersect(
                points[first_index],
                points[first_next],
                points[second_index],
                points[second_next],
            ):
                return True
    return False


def _point_in_triangle(point: Vec2, a: Vec2, b: Vec2, c: Vec2) -> bool:
    first = _orientation(a, b, point)
    second = _orientation(b, c, point)
    third = _orientation(c, a, point)
    return first >= -1.0e-8 and second >= -1.0e-8 and third >= -1.0e-8


def triangulate_floor_plan_points(points: tuple[Vec2, ...]) -> tuple[Face, ...]:
    """Ear-clip one simple footprint into engine-safe floor triangles."""

    source = _ccw_points(_normalise_points(points))
    if len(source) < 3:
        return ()
    remaining = list(range(len(source)))
    faces: list[Face] = []
    guard = len(source) * len(source)
    while len(remaining) > 3 and guard > 0:
        guard -= 1
        clipped = False
        for offset, current in enumerate(tuple(remaining)):
            previous = remaining[(offset - 1) % len(remaining)]
            following = remaining[(offset + 1) % len(remaining)]
            a, b, c = source[previous], source[current], source[following]
            if _orientation(a, b, c) <= 1.0e-8:
                continue
            if any(
                _point_in_triangle(source[candidate], a, b, c)
                for candidate in remaining
                if candidate not in {previous, current, following}
            ):
                continue
            faces.append((previous, current, following))
            remaining.pop(offset)
            clipped = True
            break
        if not clipped:
            raise ValueError("Floor-plan footprint could not be triangulated; remove crossing or overlapping wall segments.")
    if len(remaining) == 3:
        faces.append((remaining[0], remaining[1], remaining[2]))
    return tuple(faces)


def _mesh_uvs(points: tuple[Vec2, ...]) -> tuple[Vec2, ...]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x = min(xs)
    min_y = min(ys)
    width = max(max(xs) - min_x, 1.0e-7)
    depth = max(max(ys) - min_y, 1.0e-7)
    return tuple(((x - min_x) / width, (y - min_y) / depth) for x, y in points)


def _rect_bounds(points: tuple[Vec2, ...]) -> tuple[float, float, float, float] | None:
    if len(points) != 4:
        return None
    xs = sorted({round(float(point[0]), 9) for point in points})
    ys = sorted({round(float(point[1]), 9) for point in points})
    if len(xs) != 2 or len(ys) != 2:
        return None
    expected = {(xs[0], ys[0]), (xs[1], ys[0]), (xs[1], ys[1]), (xs[0], ys[1])}
    actual = {(round(float(x), 9), round(float(y), 9)) for x, y in points}
    if actual != expected:
        return None
    return xs[0], ys[0], xs[1], ys[1]


def _edge_length(a: Vec2, b: Vec2) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return (dx * dx + dy * dy) ** 0.5


def _line_intersection(point_a: Vec2, dir_a: Vec2, point_b: Vec2, dir_b: Vec2) -> Vec2 | None:
    cross = dir_a[0] * dir_b[1] - dir_a[1] * dir_b[0]
    if abs(cross) <= 1.0e-9:
        return None
    delta_x = point_b[0] - point_a[0]
    delta_y = point_b[1] - point_a[1]
    t = (delta_x * dir_b[1] - delta_y * dir_b[0]) / cross
    return (point_a[0] + dir_a[0] * t, point_a[1] + dir_a[1] * t)


def _lerp_point(a: Vec2, b: Vec2, fraction: float) -> Vec2:
    return (a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction)


def _quad_mesh(
    *,
    name: str,
    vertices: tuple[Vec3, Vec3, Vec3, Vec3],
    material: PrimitiveMaterial,
    metadata: dict[str, Any],
) -> PrimitiveMesh:
    return PrimitiveMesh(
        name=name,
        vertices=vertices,
        faces=((0, 1, 2), (0, 2, 3)),
        normals=((0.0, 0.0, 1.0),) * 4,
        uvs=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        texture=material.texture,
        diffuse=material.diffuse,
        ambient=material.ambient,
        metadata=metadata,
    )


def _opening_span(opening: FloorPlanWallOpening, edge_length: float) -> tuple[float, float]:
    half_fraction = (float(opening.width) * 0.5) / max(edge_length, 1.0e-7)
    center = float(opening.center_fraction)
    return center - half_fraction, center + half_fraction


def validate_floor_plan_room_primitive(primitive: FloorPlanRoomPrimitive) -> FloorPlanRoomValidation:
    """Validate an authored floor plan before compiling meshes or WOK data."""

    warnings: list[str] = []
    blocking: list[str] = []
    points = _normalise_points(primitive.points)
    if not _normalise_resref(primitive.room_resref):
        blocking.append("Floor-plan room requires a room resref.")
    if len(points) < 3:
        blocking.append("Floor-plan room requires at least three footprint points.")
    if _has_duplicate_or_zero_edges(points):
        blocking.append("Floor-plan room footprint cannot contain duplicate points or zero-length edges.")
    area = abs(polygon_signed_area(points))
    if area <= 1.0e-7:
        blocking.append("Floor-plan room footprint must have non-zero area.")
    if len(points) >= 4 and _has_self_intersections(points):
        blocking.append("Floor-plan walls cannot cross or overlap; move the crossing corner before closing the room.")
    elif len(points) >= 3:
        try:
            triangulate_floor_plan_points(points)
        except ValueError as exc:
            blocking.append(str(exc))
    if float(primitive.wall_height) <= 0.0:
        blocking.append("Floor-plan room wall height must be positive.")
    openings_by_edge: set[int] = set()
    for opening in primitive.openings:
        opening_name = str(opening.name or "").strip() or f"edge {opening.edge_index}"
        edge_index = int(opening.edge_index)
        if edge_index < 0 or edge_index >= max(len(points), 1):
            blocking.append(f"Opening {opening_name} references missing wall edge {edge_index}.")
            continue
        if edge_index in openings_by_edge:
            blocking.append(f"Only one floor-plan opening per wall edge is supported for now: edge {edge_index}.")
        openings_by_edge.add(edge_index)
        if float(opening.width) <= 0.0:
            blocking.append(f"Opening {opening_name} width must be positive.")
        if float(opening.height) <= 0.0:
            blocking.append(f"Opening {opening_name} height must be positive.")
        if float(opening.bottom) < 0.0:
            blocking.append(f"Opening {opening_name} bottom must not be below the room floor.")
        if float(opening.bottom) + float(opening.height) >= float(primitive.wall_height):
            blocking.append(f"Opening {opening_name} must leave wall geometry above it.")
        if len(points) >= 3 and edge_index < len(points):
            edge_len = _edge_length(points[edge_index], points[(edge_index + 1) % len(points)])
            start_fraction, end_fraction = _opening_span(opening, edge_len)
            if start_fraction <= 0.0 or end_fraction >= 1.0:
                blocking.append(f"Opening {opening_name} does not fit within wall edge {edge_index}.")
    try:
        require_walkable_walkmesh_surface(primitive.floor_surface_id, context=f"{primitive.room_resref} floor plan")
    except ValueError as exc:
        blocking.append(str(exc))
    if not primitive.include_walls:
        warnings.append("Floor-plan room has no generated walls; it will export as a walkable floor only.")
        if primitive.openings:
            warnings.append("Floor-plan wall openings are ignored because wall generation is disabled.")
    return FloorPlanRoomValidation(
        ok=not blocking,
        area=area,
        warnings=tuple(warnings),
        blocking_issues=tuple(blocking),
    )


def inset_floor_plan_points(points: tuple[Vec2, ...], distance: float) -> tuple[Vec2, ...]:
    """Inset a convex footprint by offsetting each edge inward."""

    source = _normalise_points(points)
    if len(source) < 3:
        raise ValueError("Floor-plan inset requires at least three footprint points.")
    if float(distance) <= 0.0:
        raise ValueError("Floor-plan inset distance must be positive.")
    if _has_duplicate_or_zero_edges(source):
        raise ValueError("Floor-plan inset cannot use duplicate points or zero-length edges.")
    if not _is_convex(source):
        raise ValueError("Floor-plan inset currently supports convex footprints only.")
    ccw = _ccw_points(source)
    lines: list[tuple[Vec2, Vec2]] = []
    for index, point in enumerate(ccw):
        next_point = ccw[(index + 1) % len(ccw)]
        dx = next_point[0] - point[0]
        dy = next_point[1] - point[1]
        length = (dx * dx + dy * dy) ** 0.5
        if length <= 1.0e-9:
            raise ValueError("Floor-plan inset cannot use zero-length edges.")
        inward = (-dy / length, dx / length)
        offset_point = (point[0] + inward[0] * float(distance), point[1] + inward[1] * float(distance))
        lines.append((offset_point, (dx, dy)))
    inset: list[Vec2] = []
    for index, (line_point, line_dir) in enumerate(lines):
        prev_point, prev_dir = lines[index - 1]
        intersection = _line_intersection(prev_point, prev_dir, line_point, line_dir)
        if intersection is None:
            raise ValueError("Floor-plan inset cannot resolve parallel adjacent edges.")
        inset.append(intersection)
    if abs(polygon_signed_area(tuple(inset))) <= 1.0e-7:
        raise ValueError("Floor-plan inset distance collapses the footprint.")
    if not _is_convex(tuple(inset)):
        raise ValueError("Floor-plan inset distance produced a non-convex footprint.")
    return tuple(inset)


def apply_floor_plan_inset(primitive: FloorPlanRoomPrimitive, operation: FloorPlanInsetOperation) -> FloorPlanRoomPrimitive:
    """Return a new floor-plan primitive with its footprint inset."""

    points = inset_floor_plan_points(primitive.points, operation.distance)
    metadata = {
        **dict(primitive.metadata),
        "operation": "inset",
        "inset_distance": float(operation.distance),
        **dict(operation.metadata),
    }
    return FloorPlanRoomPrimitive(
        room_resref=_normalise_resref(operation.room_resref) or primitive.room_resref,
        points=points,
        z=primitive.z,
        wall_height=primitive.wall_height,
        floor_surface_id=primitive.floor_surface_id,
        material=primitive.material,
        wall_material=primitive.wall_material,
        ceiling_material=primitive.ceiling_material,
        include_walls=primitive.include_walls,
        include_ceiling=primitive.include_ceiling,
        openings=(),
        metadata=metadata,
    )


def bevel_floor_plan_points(points: tuple[Vec2, ...], distance: float) -> tuple[Vec2, ...]:
    """Bevel every convex footprint corner by cutting along adjacent edges."""

    source = _normalise_points(points)
    if len(source) < 3:
        raise ValueError("Floor-plan bevel requires at least three footprint points.")
    if float(distance) <= 0.0:
        raise ValueError("Floor-plan bevel distance must be positive.")
    if _has_duplicate_or_zero_edges(source):
        raise ValueError("Floor-plan bevel cannot use duplicate points or zero-length edges.")
    if not _is_convex(source):
        raise ValueError("Floor-plan bevel currently supports convex footprints only.")
    ccw = _ccw_points(source)
    distance_value = float(distance)
    edge_lengths = [_edge_length(ccw[index], ccw[(index + 1) % len(ccw)]) for index in range(len(ccw))]
    for edge_index, length in enumerate(edge_lengths):
        if distance_value * 2.0 >= length:
            raise ValueError(f"Floor-plan bevel distance overlaps edge {edge_index}.")
    bevelled: list[Vec2] = []
    for index, vertex in enumerate(ccw):
        prev_vertex = ccw[index - 1]
        next_vertex = ccw[(index + 1) % len(ccw)]
        prev_length = edge_lengths[index - 1]
        next_length = edge_lengths[index]
        incoming = (
            vertex[0] + ((prev_vertex[0] - vertex[0]) / prev_length) * distance_value,
            vertex[1] + ((prev_vertex[1] - vertex[1]) / prev_length) * distance_value,
        )
        outgoing = (
            vertex[0] + ((next_vertex[0] - vertex[0]) / next_length) * distance_value,
            vertex[1] + ((next_vertex[1] - vertex[1]) / next_length) * distance_value,
        )
        bevelled.extend((incoming, outgoing))
    result = tuple(bevelled)
    if abs(polygon_signed_area(result)) <= 1.0e-7:
        raise ValueError("Floor-plan bevel distance collapses the footprint.")
    if not _is_convex(result):
        raise ValueError("Floor-plan bevel distance produced a non-convex footprint.")
    return result


def apply_floor_plan_bevel(primitive: FloorPlanRoomPrimitive, operation: FloorPlanBevelOperation) -> FloorPlanRoomPrimitive:
    """Return a new floor-plan primitive with all footprint corners bevelled."""

    points = bevel_floor_plan_points(primitive.points, operation.distance)
    metadata = {
        **dict(primitive.metadata),
        "operation": "bevel",
        "bevel_distance": float(operation.distance),
        **dict(operation.metadata),
    }
    return FloorPlanRoomPrimitive(
        room_resref=_normalise_resref(operation.room_resref) or primitive.room_resref,
        points=points,
        z=primitive.z,
        wall_height=primitive.wall_height,
        floor_surface_id=primitive.floor_surface_id,
        material=primitive.material,
        wall_material=primitive.wall_material,
        ceiling_material=primitive.ceiling_material,
        include_walls=primitive.include_walls,
        include_ceiling=primitive.include_ceiling,
        openings=(),
        metadata=metadata,
    )


def extrude_floor_plan_edge_points(points: tuple[Vec2, ...], edge_index: int, distance: float) -> tuple[Vec2, ...]:
    """Pull one footprint edge outward while preserving a convex outline."""

    source = _normalise_points(points)
    if len(source) < 3:
        raise ValueError("Floor-plan edge extrusion requires at least three footprint points.")
    distance_value = float(distance)
    if distance_value <= 0.0:
        raise ValueError("Floor-plan edge extrusion distance must be positive.")
    if _has_duplicate_or_zero_edges(source):
        raise ValueError("Floor-plan edge extrusion cannot use duplicate points or zero-length edges.")
    if not _is_convex(source):
        raise ValueError("Floor-plan edge extrusion currently supports convex footprints only.")
    edge = int(edge_index)
    if edge < 0 or edge >= len(source):
        raise ValueError(f"Floor-plan edge extrusion references missing edge {edge_index}.")
    start = source[edge]
    end = source[(edge + 1) % len(source)]
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length <= 1.0e-9:
        raise ValueError("Floor-plan edge extrusion cannot use a zero-length edge.")
    sign = 1.0 if polygon_signed_area(source) > 0.0 else -1.0
    outward = (sign * dy / length, -sign * dx / length)
    extruded_start = (start[0] + outward[0] * distance_value, start[1] + outward[1] * distance_value)
    extruded_end = (end[0] + outward[0] * distance_value, end[1] + outward[1] * distance_value)
    result: list[Vec2] = []
    for index, point in enumerate(source):
        result.append(point)
        if index == edge:
            result.extend((extruded_start, extruded_end))
    updated = tuple(result)
    if abs(polygon_signed_area(updated)) <= 1.0e-7:
        raise ValueError("Floor-plan edge extrusion collapses the footprint.")
    if _has_duplicate_or_zero_edges(updated):
        raise ValueError("Floor-plan edge extrusion produced duplicate points or zero-length edges.")
    if not _is_convex(updated):
        raise ValueError("Floor-plan edge extrusion produced a non-convex footprint; split it into multiple rooms.")
    return updated


def apply_floor_plan_edge_extrude(
    primitive: FloorPlanRoomPrimitive,
    operation: FloorPlanEdgeExtrudeOperation,
) -> FloorPlanRoomPrimitive:
    """Return a new floor-plan primitive with one wall edge pulled outward."""

    points = extrude_floor_plan_edge_points(primitive.points, operation.edge_index, operation.distance)
    metadata = {
        **dict(primitive.metadata),
        "operation": "edge_extrude",
        "edge_index": int(operation.edge_index),
        "edge_extrude_distance": float(operation.distance),
        **dict(operation.metadata),
    }
    return FloorPlanRoomPrimitive(
        room_resref=_normalise_resref(operation.room_resref) or primitive.room_resref,
        points=points,
        z=primitive.z,
        wall_height=primitive.wall_height,
        floor_surface_id=primitive.floor_surface_id,
        material=primitive.material,
        wall_material=primitive.wall_material,
        ceiling_material=primitive.ceiling_material,
        include_walls=primitive.include_walls,
        include_ceiling=primitive.include_ceiling,
        openings=(),
        metadata=metadata,
    )


def _piece_resref(prefix: str, role: str, index: int) -> str:
    suffix = f"_{role[:1]}{index}"
    return f"{prefix[: max(1, 16 - len(suffix))]}{suffix}"[:16]


def _rectangle_points(x0: float, y0: float, x1: float, y1: float) -> tuple[Vec2, Vec2, Vec2, Vec2]:
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _rect_area(bounds: tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = bounds
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _rect_intersection_area(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    x0 = max(first[0], second[0])
    y0 = max(first[1], second[1])
    x1 = min(first[2], second[2])
    y1 = min(first[3], second[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _require_union_compatible_primitives(first: FloorPlanRoomPrimitive, second: FloorPlanRoomPrimitive) -> None:
    if abs(float(first.z) - float(second.z)) > 1.0e-7:
        raise ValueError("Floor-plan rectangular union requires matching floor elevations.")
    if abs(float(first.wall_height) - float(second.wall_height)) > 1.0e-7:
        raise ValueError("Floor-plan rectangular union requires matching wall heights.")
    if resolve_walkmesh_surface_id(first.floor_surface_id) != resolve_walkmesh_surface_id(second.floor_surface_id):
        raise ValueError("Floor-plan rectangular union requires matching walkmesh surface types.")
    if first.material != second.material:
        raise ValueError("Floor-plan rectangular union requires matching room materials.")
    if first.wall_material != second.wall_material or first.ceiling_material != second.ceiling_material:
        raise ValueError("Floor-plan rectangular union requires matching wall and ceiling materials.")
    if bool(first.include_walls) != bool(second.include_walls):
        raise ValueError("Floor-plan rectangular union requires matching wall generation settings.")
    if bool(first.include_ceiling) != bool(second.include_ceiling):
        raise ValueError("Floor-plan rectangular union requires matching ceiling generation settings.")


def apply_floor_plan_rectangular_union(
    first: FloorPlanRoomPrimitive,
    second: FloorPlanRoomPrimitive,
    operation: FloorPlanRectangularUnionOperation | None = None,
) -> FloorPlanRoomPrimitive:
    """Union two rectangular floor plans when the result is one safe rectangle."""

    union_operation = operation or FloorPlanRectangularUnionOperation()
    first_bounds = _rect_bounds(_normalise_points(first.points))
    second_bounds = _rect_bounds(_normalise_points(second.points))
    if first_bounds is None or second_bounds is None:
        raise ValueError("Floor-plan rectangular union currently requires axis-aligned rectangular footprints.")
    _require_union_compatible_primitives(first, second)

    min_x = min(first_bounds[0], second_bounds[0])
    min_y = min(first_bounds[1], second_bounds[1])
    max_x = max(first_bounds[2], second_bounds[2])
    max_y = max(first_bounds[3], second_bounds[3])
    combined_bounds = (min_x, min_y, max_x, max_y)
    combined_area = _rect_area(combined_bounds)
    source_area = _rect_area(first_bounds) + _rect_area(second_bounds) - _rect_intersection_area(first_bounds, second_bounds)
    if combined_area <= 1.0e-7:
        raise ValueError("Floor-plan rectangular union would create an empty footprint.")
    if abs(combined_area - source_area) > 1.0e-7:
        raise ValueError("Floor-plan rectangular union would produce a non-rectangular or disconnected footprint.")

    metadata = {
        **dict(first.metadata),
        "operation": "rectangular_union",
        "source_room_resrefs": [first.room_resref, second.room_resref],
        "source_bounds": [list(first_bounds), list(second_bounds)],
        "combined_bounds": list(combined_bounds),
        **dict(union_operation.metadata),
    }
    return FloorPlanRoomPrimitive(
        room_resref=_normalise_resref(union_operation.room_resref) or _normalise_resref(first.room_resref),
        points=_rectangle_points(*combined_bounds),
        z=first.z,
        wall_height=first.wall_height,
        floor_surface_id=first.floor_surface_id,
        material=first.material,
        wall_material=first.wall_material,
        ceiling_material=first.ceiling_material,
        include_walls=first.include_walls,
        include_ceiling=first.include_ceiling,
        openings=(),
        metadata=metadata,
    )


def apply_floor_plan_rectangular_cut(
    primitive: FloorPlanRoomPrimitive,
    operation: FloorPlanRectangularCutOperation,
) -> tuple[FloorPlanRoomPrimitive, ...]:
    """Subtract an axis-aligned rectangle and return convex exportable pieces.

    This first-pass boolean operation deliberately returns multiple rectangular
    floor-plan primitives instead of creating a concave or holed polygon that
    the current MDL/WOK exporter cannot safely serialize yet.
    """

    source = _normalise_points(primitive.points)
    source_bounds = _rect_bounds(source)
    if source_bounds is None:
        raise ValueError("Floor-plan rectangular cut currently requires an axis-aligned rectangular source footprint.")
    cut_width = float(operation.size[0])
    cut_depth = float(operation.size[1])
    if cut_width <= 0.0 or cut_depth <= 0.0:
        raise ValueError("Floor-plan rectangular cut size must be positive.")
    if not all(math.isfinite(float(value)) for value in (*operation.center, *operation.size)):
        raise ValueError("Floor-plan rectangular cut center and size must contain finite values.")
    sx0, sy0, sx1, sy1 = source_bounds
    cx, cy = operation.center
    cx = float(cx)
    cy = float(cy)
    cut_x0 = cx - cut_width * 0.5
    cut_x1 = cx + cut_width * 0.5
    cut_y0 = cy - cut_depth * 0.5
    cut_y1 = cy + cut_depth * 0.5
    ix0 = max(sx0, cut_x0)
    ix1 = min(sx1, cut_x1)
    iy0 = max(sy0, cut_y0)
    iy1 = min(sy1, cut_y1)
    if ix1 - ix0 <= 1.0e-7 or iy1 - iy0 <= 1.0e-7:
        raise ValueError("Floor-plan rectangular cut does not overlap the source footprint.")
    if ix0 <= sx0 + 1.0e-7 and ix1 >= sx1 - 1.0e-7 and iy0 <= sy0 + 1.0e-7 and iy1 >= sy1 - 1.0e-7:
        raise ValueError("Floor-plan rectangular cut would remove the entire source footprint.")

    prefix = _normalise_resref(operation.room_resref_prefix) or _normalise_resref(primitive.room_resref)
    pieces: list[FloorPlanRoomPrimitive] = []
    spans = (
        ("left", (sx0, sy0, ix0, sy1)),
        ("right", (ix1, sy0, sx1, sy1)),
        ("bottom", (ix0, sy0, ix1, iy0)),
        ("top", (ix0, iy1, ix1, sy1)),
    )
    piece_index = 1
    for role, (x0, y0, x1, y1) in spans:
        if x1 - x0 <= 1.0e-7 or y1 - y0 <= 1.0e-7:
            continue
        metadata = {
            **dict(primitive.metadata),
            "operation": "rectangular_cut_difference",
            "cut_center": [cx, cy],
            "cut_size": [cut_width, cut_depth],
            "cut_intersection": [ix0, iy0, ix1, iy1],
            "source_room_resref": primitive.room_resref,
            "piece_role": role,
            "piece_index": piece_index,
            **dict(operation.metadata),
        }
        pieces.append(
            FloorPlanRoomPrimitive(
                room_resref=_piece_resref(prefix, role, piece_index),
                points=_rectangle_points(x0, y0, x1, y1),
                z=primitive.z,
                wall_height=primitive.wall_height,
                floor_surface_id=primitive.floor_surface_id,
                material=primitive.material,
                wall_material=primitive.wall_material,
                ceiling_material=primitive.ceiling_material,
                include_walls=primitive.include_walls,
                include_ceiling=primitive.include_ceiling,
                openings=(),
                metadata=metadata,
            )
        )
        piece_index += 1
    if not pieces:
        raise ValueError("Floor-plan rectangular cut did not leave any exportable pieces.")
    return tuple(pieces)


def apply_floor_plan_axis_split(
    primitive: FloorPlanRoomPrimitive,
    operation: FloorPlanAxisSplitOperation,
) -> tuple[FloorPlanRoomPrimitive, FloorPlanRoomPrimitive]:
    """Split an axis-aligned rectangle into two room primitives.

    Unlike rectangular cut, this operation preserves all floor area. It is the
    safe "knife split" primitive Map Studio can use when a blockout room needs
    to become separate KOTOR room MDL/MDX/WOK exports.
    """

    source = _normalise_points(primitive.points)
    source_bounds = _rect_bounds(source)
    if source_bounds is None:
        raise ValueError("Floor-plan axis split currently requires an axis-aligned rectangular source footprint.")
    axis = str(operation.axis or "").strip().lower()
    if axis not in {"x", "y"}:
        raise ValueError("Floor-plan axis split axis must be 'x' or 'y'.")
    coordinate = float(operation.coordinate)
    if not math.isfinite(coordinate):
        raise ValueError("Floor-plan axis split coordinate must be finite.")
    sx0, sy0, sx1, sy1 = source_bounds
    if axis == "x":
        if coordinate <= sx0 + 1.0e-7 or coordinate >= sx1 - 1.0e-7:
            raise ValueError("Floor-plan X split coordinate must be inside the source footprint.")
        spans = (
            ("left", (sx0, sy0, coordinate, sy1)),
            ("right", (coordinate, sy0, sx1, sy1)),
        )
    else:
        if coordinate <= sy0 + 1.0e-7 or coordinate >= sy1 - 1.0e-7:
            raise ValueError("Floor-plan Y split coordinate must be inside the source footprint.")
        spans = (
            ("bottom", (sx0, sy0, sx1, coordinate)),
            ("top", (sx0, coordinate, sx1, sy1)),
        )

    prefix = _normalise_resref(operation.room_resref_prefix) or _normalise_resref(primitive.room_resref)
    pieces: list[FloorPlanRoomPrimitive] = []
    for piece_index, (role, (x0, y0, x1, y1)) in enumerate(spans, start=1):
        metadata = {
            **dict(primitive.metadata),
            "operation": "axis_split",
            "split_axis": axis,
            "split_coordinate": coordinate,
            "source_room_resref": primitive.room_resref,
            "piece_role": role,
            "piece_index": piece_index,
            **dict(operation.metadata),
        }
        pieces.append(
            FloorPlanRoomPrimitive(
                room_resref=_piece_resref(prefix, role, piece_index),
                points=_rectangle_points(x0, y0, x1, y1),
                z=primitive.z,
                wall_height=primitive.wall_height,
                floor_surface_id=primitive.floor_surface_id,
                material=primitive.material,
                wall_material=primitive.wall_material,
                ceiling_material=primitive.ceiling_material,
                include_walls=primitive.include_walls,
                include_ceiling=primitive.include_ceiling,
                openings=(),
                metadata=metadata,
            )
        )
    return pieces[0], pieces[1]


def build_floor_plan_floor_mesh(primitive: FloorPlanRoomPrimitive) -> PrimitiveMesh:
    """Build a triangulated floor mesh from a simple floor-plan footprint."""

    validation = validate_floor_plan_room_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    points = _ccw_points(_normalise_points(primitive.points))
    z = float(primitive.z)
    vertices: tuple[Vec3, ...] = tuple((x, y, z) for x, y in points)
    surface_id = resolve_walkmesh_surface_id(primitive.floor_surface_id)
    room_resref = _normalise_resref(primitive.room_resref)
    return PrimitiveMesh(
        name=f"{room_resref}_floor",
        vertices=vertices,
        faces=triangulate_floor_plan_points(points),
        normals=((0.0, 0.0, 1.0),) * len(vertices),
        uvs=_mesh_uvs(points),
        texture=primitive.material.texture,
        diffuse=primitive.material.diffuse,
        ambient=primitive.material.ambient,
        metadata={
            "primitive": "floor_plan_floor",
            "source": "map_studio:t2611",
            "surface_id": surface_id,
            "surface_name": walkmesh_surface_name(surface_id),
            "polygon_area": validation.area,
            "point_count": len(points),
            **dict(primitive.material.metadata),
        },
    )


def build_floor_plan_wok(primitive: FloorPlanRoomPrimitive) -> WOKData:
    """Derive a WOK from the same triangulated floor footprint."""

    validation = validate_floor_plan_room_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    points = _ccw_points(_normalise_points(primitive.points))
    vertices: list[Vec3] = [(x, y, float(primitive.z)) for x, y in points]
    surface_id = resolve_walkmesh_surface_id(primitive.floor_surface_id)
    triangles = triangulate_floor_plan_points(points)
    adjacency = [[-1, -1, -1] for _face in triangles]
    edge_owners: dict[tuple[int, int], tuple[int, int]] = {}
    for face_index, (a, b, c) in enumerate(triangles):
        for edge_index, edge in enumerate(((a, b), (b, c), (c, a))):
            key = tuple(sorted(edge))
            previous = edge_owners.get(key)
            if previous is None:
                edge_owners[key] = (face_index, edge_index)
                continue
            other_face, other_edge = previous
            adjacency[face_index][edge_index] = other_face
            adjacency[other_face][other_edge] = face_index
    faces = [
        WOKFace(
            a,
            b,
            c,
            surface=surface_id,
            adj1=adjacency[index][0],
            adj2=adjacency[index][1],
            adj3=adjacency[index][2],
        )
        for index, (a, b, c) in enumerate(triangles)
    ]
    return WOKData(verts=vertices, faces=faces)


def build_floor_plan_wall_meshes(primitive: FloorPlanRoomPrimitive) -> tuple[PrimitiveMesh, ...]:
    """Extrude each footprint edge into a vertical wall helper mesh."""

    validation = validate_floor_plan_room_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    if not primitive.include_walls:
        return ()
    points = _ccw_points(_normalise_points(primitive.points))
    room_resref = _normalise_resref(primitive.room_resref)
    z = float(primitive.z)
    top_z = z + float(primitive.wall_height)
    wall_material = primitive.wall_material or primitive.material
    openings_by_edge = {int(opening.edge_index): opening for opening in primitive.openings}
    meshes: list[PrimitiveMesh] = []
    for index, (x0, y0) in enumerate(points):
        x1, y1 = points[(index + 1) % len(points)]
        opening = openings_by_edge.get(index)
        base_metadata = {
            "primitive": "floor_plan_wall",
            "source": "map_studio:t2611",
            "edge_index": index,
            "wall_height": float(primitive.wall_height),
            **dict(primitive.material.metadata),
        }
        if opening is None:
            meshes.append(
                _quad_mesh(
                    name=f"{room_resref}_wall_{index + 1:02d}",
                    vertices=((x0, y0, z), (x1, y1, z), (x1, y1, top_z), (x0, y0, top_z)),
                    material=wall_material,
                    metadata=base_metadata,
                )
            )
            continue
        edge_len = _edge_length((x0, y0), (x1, y1))
        start_fraction, end_fraction = _opening_span(opening, edge_len)
        start = _lerp_point((x0, y0), (x1, y1), start_fraction)
        end = _lerp_point((x0, y0), (x1, y1), end_fraction)
        opening_bottom = z + float(opening.bottom)
        opening_top = opening_bottom + float(opening.height)
        opening_metadata = {
            **base_metadata,
            "opening_name": str(opening.name or "").strip(),
            "opening_center_fraction": float(opening.center_fraction),
            "opening_width": float(opening.width),
            "opening_height": float(opening.height),
            "opening_bottom": float(opening.bottom),
            **dict(opening.metadata),
        }
        if start_fraction > 1.0e-7:
            meshes.append(
                _quad_mesh(
                    name=f"{room_resref}_wall_{index + 1:02d}_left",
                    vertices=((x0, y0, z), (start[0], start[1], z), (start[0], start[1], top_z), (x0, y0, top_z)),
                    material=wall_material,
                    metadata={**opening_metadata, "wall_panel": "opening_left"},
                )
            )
        if float(opening.bottom) > 1.0e-7:
            meshes.append(
                _quad_mesh(
                    name=f"{room_resref}_wall_{index + 1:02d}_sill",
                    vertices=((start[0], start[1], z), (end[0], end[1], z), (end[0], end[1], opening_bottom), (start[0], start[1], opening_bottom)),
                    material=wall_material,
                    metadata={**opening_metadata, "wall_panel": "opening_sill"},
                )
            )
        meshes.append(
            _quad_mesh(
                name=f"{room_resref}_wall_{index + 1:02d}_lintel",
                vertices=((start[0], start[1], opening_top), (end[0], end[1], opening_top), (end[0], end[1], top_z), (start[0], start[1], top_z)),
                material=wall_material,
                metadata={**opening_metadata, "wall_panel": "opening_lintel"},
            )
        )
        if end_fraction < 1.0 - 1.0e-7:
            meshes.append(
                _quad_mesh(
                    name=f"{room_resref}_wall_{index + 1:02d}_right",
                    vertices=((end[0], end[1], z), (x1, y1, z), (x1, y1, top_z), (end[0], end[1], top_z)),
                    material=wall_material,
                    metadata={**opening_metadata, "wall_panel": "opening_right"},
                )
            )
    return tuple(meshes)


def build_floor_plan_ceiling_mesh(primitive: FloorPlanRoomPrimitive) -> PrimitiveMesh | None:
    """Build an optional inward-facing ceiling for closed interior rooms."""

    if not primitive.include_ceiling:
        return None
    validation = validate_floor_plan_room_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    points = _ccw_points(_normalise_points(primitive.points))
    top_z = float(primitive.z) + float(primitive.wall_height)
    vertices: tuple[Vec3, ...] = tuple((x, y, top_z) for x, y in points)
    material = primitive.ceiling_material or primitive.wall_material or primitive.material
    faces = tuple((c, b, a) for a, b, c in triangulate_floor_plan_points(points))
    return PrimitiveMesh(
        name=f"{_normalise_resref(primitive.room_resref)}_ceiling",
        vertices=vertices,
        faces=faces,
        normals=((0.0, 0.0, -1.0),) * len(vertices),
        uvs=_mesh_uvs(points),
        texture=material.texture,
        diffuse=material.diffuse,
        ambient=material.ambient,
        metadata={
            "primitive": "floor_plan_ceiling",
            "source": "map_studio:pascal_building",
            **dict(material.metadata),
        },
    )


def compile_floor_plan_room_geometry(primitive: FloorPlanRoomPrimitive) -> AuthoredRoomGeometry:
    """Compile a floor-plan room into render/export meshes plus WOK."""

    validation = validate_floor_plan_room_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    floor_mesh = build_floor_plan_floor_mesh(primitive)
    wall_meshes = build_floor_plan_wall_meshes(primitive)
    helper_meshes = wall_meshes
    ceiling = build_floor_plan_ceiling_mesh(primitive)
    if ceiling is not None:
        helper_meshes = helper_meshes + (ceiling,)
    surface_id = resolve_walkmesh_surface_id(primitive.floor_surface_id)
    room_resref = _normalise_resref(primitive.room_resref)
    return AuthoredRoomGeometry(
        room_resref=room_resref,
        room_mesh=floor_mesh,
        helper_meshes=helper_meshes,
        wok=build_floor_plan_wok(primitive),
        metadata={
            **dict(primitive.metadata),
            "primitive": "floor_plan_extrusion",
            "source": "src.core.modules.authored_room_floorplan",
            "point_count": len(_normalise_points(primitive.points)),
            "wall_count": len(wall_meshes),
            "opening_count": len(primitive.openings),
            "has_ceiling": bool(ceiling is not None),
            "wall_height": float(primitive.wall_height),
            "polygon_area": validation.area,
            "floor_surface_id": surface_id,
            "floor_surface_name": walkmesh_surface_name(surface_id),
            "warnings": list(validation.warnings),
        },
    )


__all__ = [
    "FloorPlanAxisSplitOperation",
    "FloorPlanBevelOperation",
    "FloorPlanEdgeExtrudeOperation",
    "FloorPlanInsetOperation",
    "FloorPlanRectangularCutOperation",
    "FloorPlanRectangularUnionOperation",
    "FloorPlanRoomPrimitive",
    "FloorPlanRoomValidation",
    "FloorPlanWallOpening",
    "apply_floor_plan_axis_split",
    "apply_floor_plan_bevel",
    "apply_floor_plan_edge_extrude",
    "apply_floor_plan_inset",
    "apply_floor_plan_rectangular_cut",
    "apply_floor_plan_rectangular_union",
    "bevel_floor_plan_points",
    "build_floor_plan_floor_mesh",
    "build_floor_plan_ceiling_mesh",
    "build_floor_plan_wall_meshes",
    "build_floor_plan_wok",
    "compile_floor_plan_room_geometry",
    "extrude_floor_plan_edge_points",
    "inset_floor_plan_points",
    "triangulate_floor_plan_points",
    "polygon_signed_area",
    "validate_floor_plan_room_primitive",
]
