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


def _mesh_uvs(
    points: tuple[Vec2, ...],
    *,
    repeat_metres: float | None = None,
) -> tuple[Vec2, ...]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x = min(xs)
    min_y = min(ys)
    if repeat_metres is not None:
        repeat = float(repeat_metres)
        if not math.isfinite(repeat) or repeat <= 1.0e-7:
            raise ValueError("Floor-plan UV repeat distance must be a positive finite value.")
        return tuple(((x - min_x) / repeat, (y - min_y) / repeat) for x, y in points)
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


_VANILLA_ARCHITECTURE_UV_METRES: dict[str, float] = {
    # Median world-metres per UV repeat measured from the serialized K1
    # Korriban tomb corpus.  Keeping these values here prevents authored walls
    # from stretching one 256/512 px stock texture over an entire room.
    "lko_flr01": 3.0,
    "lko_flr03": 3.0,
    "lko_rocks": 7.071,
    "lko_tirm01": 4.591,
    "lko_wal07": 3.0,
    "lko_wal08": 3.0,
    "lko_wal09": 2.709,
    # K2's Secret Tomb reuses the same Odyssey modelling grid under renamed
    # textures; the K1 measurements are therefore the correct repeat scale.
    "kor_flr01": 3.0,
    "kor_flr03": 3.0,
    "kor_rocks": 7.071,
    "kor_tr01": 4.591,
    "kor_wal06": 3.0,
    "kor_wal07a": 3.0,
    "kor_wal08": 3.0,
    "kor_wal09": 2.709,
}


def _planar_uvs(
    vertices: tuple[Vec3, ...],
    *,
    repeat_metres: float | None = None,
) -> tuple[Vec2, ...]:
    """Project one planar helper mesh onto its two widest local axes.

    ``repeat_metres`` preserves retail texel density by allowing UVs beyond
    0..1.  The Odyssey material sampler repeats those coordinates, exactly as
    it does for the stock Korriban room meshes.
    """

    spans = []
    for axis in range(3):
        values = [float(vertex[axis]) for vertex in vertices]
        spans.append((max(values) - min(values), axis))
    axes = [axis for _span, axis in sorted(spans, reverse=True)[:2]]
    first = [float(vertex[axes[0]]) for vertex in vertices]
    second = [float(vertex[axes[1]]) for vertex in vertices]
    min_first, min_second = min(first), min(second)
    first_span = max(max(first) - min_first, 1.0e-7)
    second_span = max(max(second) - min_second, 1.0e-7)
    scale = float(repeat_metres or 0.0)
    tiled = math.isfinite(scale) and scale > 1.0e-7
    return tuple(
        (
            (value_first - min_first) / scale if tiled else (value_first - min_first) / first_span,
            (value_second - min_second) / scale if tiled else (value_second - min_second) / second_span,
        )
        for value_first, value_second in zip(first, second)
    )


def _planar_surface_mesh(
    *,
    name: str,
    vertices: tuple[Vec3, ...],
    faces: tuple[Face, ...],
    material: PrimitiveMaterial,
    metadata: dict[str, Any],
) -> PrimitiveMesh:
    """Build one flat-shaded roof panel with a geometry-derived normal."""

    if not faces or len(vertices) < 3:
        raise ValueError("A roof surface requires at least one triangle.")
    first_face = faces[0]
    a, b, c = (vertices[index] for index in first_face)
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    normal = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    length = math.sqrt(sum(component * component for component in normal))
    if length <= 1.0e-9:
        raise ValueError(f"{name} cannot contain a degenerate triangle.")
    unit = tuple(component / length for component in normal)
    texture = str(material.texture or "").strip().lower()
    repeat_metres = (
        _VANILLA_ARCHITECTURE_UV_METRES.get(texture, 3.0)
        if bool(metadata.get("vanilla_derived"))
        else None
    )
    return PrimitiveMesh(
        name=name,
        vertices=vertices,
        faces=faces,
        normals=(unit,) * len(vertices),
        uvs=_planar_uvs(vertices, repeat_metres=repeat_metres),
        texture=material.texture,
        diffuse=material.diffuse,
        ambient=material.ambient,
        metadata=metadata,
    )


def _roof_type(primitive: FloorPlanRoomPrimitive) -> str:
    return str(primitive.metadata.get("building_roof_type", "none") or "none").strip().lower()


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
    roof_type = _roof_type(primitive)
    if roof_type not in {"none", "flat", "hip", "gable"}:
        blocking.append(f"Unsupported building roof preset: {roof_type}.")
    if roof_type == "gable" and _rect_bounds(points) is None:
        blocking.append("Gable roofs currently require a rectangular room footprint.")
    if roof_type != "none":
        try:
            roof_pitch = float(primitive.metadata.get("building_roof_pitch_degrees", 30.0) or 30.0)
            roof_overhang = float(primitive.metadata.get("building_roof_overhang", 0.25) or 0.0)
        except (TypeError, ValueError):
            blocking.append("Roof pitch and overhang must be numeric.")
        else:
            if not math.isfinite(roof_pitch) or roof_pitch < 5.0 or roof_pitch > 70.0:
                blocking.append("Roof pitch must be between 5 and 70 degrees.")
            if not math.isfinite(roof_overhang) or roof_overhang < 0.0 or roof_overhang > 5.0:
                blocking.append("Roof overhang must be between 0 and 5 metres.")
    openings_by_edge: dict[int, list[FloorPlanWallOpening]] = {}
    for opening in primitive.openings:
        opening_name = str(opening.name or "").strip() or f"edge {opening.edge_index}"
        edge_index = int(opening.edge_index)
        if edge_index < 0 or edge_index >= max(len(points), 1):
            blocking.append(f"Opening {opening_name} references missing wall edge {edge_index}.")
            continue
        openings_by_edge.setdefault(edge_index, []).append(opening)
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
    for edge_index, edge_openings in openings_by_edge.items():
        if edge_index < 0 or edge_index >= len(points):
            continue
        edge_len = _edge_length(points[edge_index], points[(edge_index + 1) % len(points)])
        for opening_index, first in enumerate(edge_openings):
            first_start, first_end = _opening_span(first, edge_len)
            first_bottom = float(first.bottom)
            first_top = first_bottom + float(first.height)
            for second in edge_openings[opening_index + 1 :]:
                second_start, second_end = _opening_span(second, edge_len)
                second_bottom = float(second.bottom)
                second_top = second_bottom + float(second.height)
                horizontal_overlap = min(first_end, second_end) - max(first_start, second_start)
                vertical_overlap = min(first_top, second_top) - max(first_bottom, second_bottom)
                if horizontal_overlap > 1.0e-7 and vertical_overlap > 1.0e-7:
                    blocking.append(
                        f"Openings {str(first.name or 'opening')} and {str(second.name or 'opening')} overlap on wall edge {edge_index}."
                    )
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
    floor_texture = str(primitive.material.texture or "").strip().lower()
    floor_repeat_metres = _VANILLA_ARCHITECTURE_UV_METRES.get(floor_texture, 3.0)
    return PrimitiveMesh(
        name=f"{room_resref}_floor",
        vertices=vertices,
        faces=triangulate_floor_plan_points(points),
        normals=((0.0, 0.0, 1.0),) * len(vertices),
        uvs=_mesh_uvs(points, repeat_metres=floor_repeat_metres),
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
            "uv_projection": "world_xy_tiled",
            "uv_repeat_metres": floor_repeat_metres,
            "texture_stretching_prevented": True,
            **dict(primitive.material.metadata),
        },
    )


def build_floor_plan_wok(primitive: FloorPlanRoomPrimitive) -> WOKData:
    """Derive a WOK from the same triangulated floor footprint."""

    validation = validate_floor_plan_room_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    points = _ccw_points(_normalise_points(primitive.points))
    floor_z = float(primitive.z)
    openings_by_edge: dict[int, list[FloorPlanWallOpening]] = {}
    for opening in tuple(primitive.openings or ()):
        metadata = dict(opening.metadata or {})
        kind = str(metadata.get("opening_kind") or metadata.get("kind") or "door").strip().lower()
        if float(opening.bottom) > 1.0e-5 or kind in {"window", "backdrop", "view"}:
            continue
        if not (
            metadata.get("connected_room_resref")
            or metadata.get("connection_room")
            or metadata.get("walkmesh_portal")
        ):
            continue
        openings_by_edge.setdefault(int(opening.edge_index), []).append(opening)

    # A vanilla room doorway transition edge often sits a few centimetres
    # inside the adjoining generated room rather than on the visible wall
    # plane.  Carve that narrow threshold notch directly into the generated
    # floor WOK so the two reciprocal perimeter edges occupy the same module-
    # space segment.  The render floor remains uncut and the stock threshold
    # geometry covers the overlap, matching the retail construction pattern.
    outline: list[Vec2] = []
    zero_depth_portals: list[tuple[Vec2, Vec2]] = []
    for edge_index, start in enumerate(points):
        end = points[(edge_index + 1) % len(points)]
        if not outline or math.dist(outline[-1], start) > 1.0e-8:
            outline.append(start)
        dx = float(end[0]) - float(start[0])
        dy = float(end[1]) - float(start[1])
        edge_length = math.hypot(dx, dy)
        if edge_length <= 1.0e-8:
            continue
        inward = (-dy / edge_length, dx / edge_length)
        rows = sorted(
            openings_by_edge.get(edge_index, ()),
            key=lambda item: float(item.center_fraction),
        )
        for opening in rows:
            metadata = dict(opening.metadata or {})
            portal_width = min(
                max(0.02, float(metadata.get("walkmesh_portal_width_m", opening.width) or opening.width)),
                max(0.02, edge_length - 0.02),
            )
            center = max(0.0, min(edge_length, float(opening.center_fraction) * edge_length))
            half = portal_width * 0.5
            start_distance = max(0.01, min(edge_length - 0.01, center - half))
            end_distance = max(start_distance + 0.01, min(edge_length - 0.01, center + half))
            wall_start = (
                float(start[0]) + (dx / edge_length) * start_distance,
                float(start[1]) + (dy / edge_length) * start_distance,
            )
            wall_end = (
                float(start[0]) + (dx / edge_length) * end_distance,
                float(start[1]) + (dy / edge_length) * end_distance,
            )
            inset = max(0.0, float(metadata.get("walkmesh_portal_inset_m", 0.0) or 0.0))
            if inset <= 1.0e-7:
                zero_depth_portals.append((wall_start, wall_end))
                continue
            if math.dist(outline[-1], wall_start) > 1.0e-8:
                outline.append(wall_start)
            outline.extend(
                (
                    (wall_start[0] + inward[0] * inset, wall_start[1] + inward[1] * inset),
                    (wall_end[0] + inward[0] * inset, wall_end[1] + inward[1] * inset),
                    wall_end,
                )
            )

    vertices: list[Vec3] = [(x, y, floor_z) for x, y in outline]
    surface_id = resolve_walkmesh_surface_id(primitive.floor_surface_id)
    triangles = list(triangulate_floor_plan_points(tuple(outline)))

    def split_boundary_at(portal_start: Vec2, portal_end: Vec2) -> None:
        """Insert one exact portal segment into the current boundary fan."""

        edge_counts: dict[tuple[int, int], int] = {}
        owners: dict[tuple[int, int], tuple[int, int]] = {}
        for face_index, face in enumerate(triangles):
            for local_edge, pair in enumerate(((face[0], face[1]), (face[1], face[2]), (face[2], face[0]))):
                key = tuple(sorted(pair))
                edge_counts[key] = edge_counts.get(key, 0) + 1
                owners[key] = (face_index, local_edge)
        candidate: tuple[int, int] | None = None
        for key, count in edge_counts.items():
            if count != 1:
                continue
            face_index, local_edge = owners[key]
            face = triangles[face_index]
            first = face[local_edge]
            second = face[(local_edge + 1) % 3]
            a = (vertices[first][0], vertices[first][1])
            b = (vertices[second][0], vertices[second][1])
            if _point_on_segment(portal_start, a, b) and _point_on_segment(portal_end, a, b):
                candidate = (face_index, local_edge)
                break
        if candidate is None:
            raise ValueError("Connected doorway could not be inserted into the generated WOK perimeter.")
        face_index, local_edge = candidate
        face = triangles[face_index]
        first = face[local_edge]
        second = face[(local_edge + 1) % 3]
        third = face[(local_edge + 2) % 3]
        a = (vertices[first][0], vertices[first][1])
        b = (vertices[second][0], vertices[second][1])
        length_squared = max(1.0e-16, (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)

        def parameter(point: Vec2) -> float:
            return ((point[0] - a[0]) * (b[0] - a[0]) + (point[1] - a[1]) * (b[1] - a[1])) / length_squared

        inserts = sorted(((parameter(portal_start), portal_start), (parameter(portal_end), portal_end)))
        sequence = [first]
        for value, point in inserts:
            if value <= 1.0e-8 or value >= 1.0 - 1.0e-8:
                continue
            existing = next(
                (
                    index
                    for index, vertex in enumerate(vertices)
                    if math.dist((vertex[0], vertex[1]), point) <= 1.0e-8
                ),
                None,
            )
            if existing is None:
                existing = len(vertices)
                vertices.append((point[0], point[1], floor_z))
            if sequence[-1] != existing:
                sequence.append(existing)
        if sequence[-1] != second:
            sequence.append(second)
        replacement = [
            (sequence[index], sequence[index + 1], third)
            for index in range(len(sequence) - 1)
            if sequence[index] != sequence[index + 1]
        ]
        triangles[face_index : face_index + 1] = replacement

    for portal_start, portal_end in zero_depth_portals:
        split_boundary_at(portal_start, portal_end)

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
    return WOKData(verts=vertices, faces=faces, adjacency_domain_count=len(faces))


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
    openings_by_edge: dict[int, list[FloorPlanWallOpening]] = {}
    for opening in primitive.openings:
        openings_by_edge.setdefault(int(opening.edge_index), []).append(opening)
    meshes: list[PrimitiveMesh] = []
    for index, (x0, y0) in enumerate(points):
        x1, y1 = points[(index + 1) % len(points)]
        edge_openings = sorted(
            openings_by_edge.get(index, ()),
            key=lambda item: (float(item.center_fraction), float(item.bottom), str(item.name or "")),
        )
        base_metadata = {
            "primitive": "floor_plan_wall",
            "source": "map_studio:t2611",
            "edge_index": index,
            "wall_height": float(primitive.wall_height),
            **dict(primitive.material.metadata),
        }
        if not edge_openings:
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
        if len(edge_openings) > 1:
            # Split the wall plane at every opening boundary. Each resulting
            # vertical strip is filled only outside active opening intervals,
            # producing any number of non-overlapping rectangular cut-outs.
            horizontal_bounds = {0.0, 1.0}
            spans: list[tuple[FloorPlanWallOpening, float, float, float, float]] = []
            for item in edge_openings:
                start_fraction, end_fraction = _opening_span(item, edge_len)
                horizontal_bounds.update((start_fraction, end_fraction))
                spans.append(
                    (
                        item,
                        start_fraction,
                        end_fraction,
                        float(item.bottom),
                        float(item.bottom) + float(item.height),
                    )
                )
            ordered_x = sorted(horizontal_bounds)
            panel_ordinal = 0
            for start_fraction, end_fraction in zip(ordered_x, ordered_x[1:]):
                if end_fraction - start_fraction <= 1.0e-8:
                    continue
                midpoint = (start_fraction + end_fraction) * 0.5
                active = [span for span in spans if span[1] < midpoint < span[2]]
                blocked_z = sorted((span[3], span[4]) for span in active)
                visible_z: list[tuple[float, float]] = []
                cursor_z = 0.0
                for blocked_bottom, blocked_top in blocked_z:
                    if blocked_bottom > cursor_z + 1.0e-8:
                        visible_z.append((cursor_z, blocked_bottom))
                    cursor_z = max(cursor_z, blocked_top)
                if cursor_z < float(primitive.wall_height) - 1.0e-8:
                    visible_z.append((cursor_z, float(primitive.wall_height)))
                start = _lerp_point((x0, y0), (x1, y1), start_fraction)
                end = _lerp_point((x0, y0), (x1, y1), end_fraction)
                for lower, upper in visible_z:
                    if upper - lower <= 1.0e-8:
                        continue
                    panel_ordinal += 1
                    meshes.append(
                        _quad_mesh(
                            name=f"{room_resref}_wall_{index + 1:02d}_panel_{panel_ordinal:02d}",
                            vertices=(
                                (start[0], start[1], z + lower),
                                (end[0], end[1], z + lower),
                                (end[0], end[1], z + upper),
                                (start[0], start[1], z + upper),
                            ),
                            material=wall_material,
                            metadata={
                                **base_metadata,
                                "wall_panel": "multi_opening_fill",
                                "opening_names": tuple(str(span[0].name or "") for span in active),
                            },
                        )
                    )
            continue
        opening = edge_openings[0]
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


def _architecture_material(texture: str, *, luminous: bool = False) -> PrimitiveMaterial:
    """Build one material used by a vanilla-derived architecture profile."""

    metadata: dict[str, Any] = {
        "surface_role": "architectural_detail",
        "vanilla_derived": True,
    }
    if luminous:
        metadata.update({"selfillum": (0.7, 0.82, 1.0), "has_shadow": False})
    return PrimitiveMaterial(
        texture=str(texture or "default").strip().lower(),
        diffuse=(1.0, 1.0, 1.0),
        ambient=(0.5, 0.5, 0.5),
        metadata=metadata,
    )


def _subtract_interval(
    intervals: list[tuple[float, float]],
    blocked_start: float,
    blocked_end: float,
) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for start, end in intervals:
        if blocked_end <= start + 1.0e-8 or blocked_start >= end - 1.0e-8:
            result.append((start, end))
            continue
        if blocked_start > start + 1.0e-8:
            result.append((start, min(end, blocked_start)))
        if blocked_end < end - 1.0e-8:
            result.append((max(start, blocked_end), end))
    return result


def _architecture_visible_intervals(
    edge_length: float,
    openings: tuple[FloorPlanWallOpening, ...],
    *,
    z0: float,
    z1: float,
) -> tuple[tuple[float, float], ...]:
    """Return wall-local spans not occupied by a door/window at this height."""

    intervals = [(0.0, float(edge_length))]
    for opening in openings:
        opening_bottom = float(opening.bottom)
        opening_top = opening_bottom + float(opening.height)
        if opening_top <= z0 + 1.0e-8 or opening_bottom >= z1 - 1.0e-8:
            continue
        center = float(opening.center_fraction) * float(edge_length)
        half = float(opening.width) * 0.5
        intervals = _subtract_interval(intervals, max(0.0, center - half), min(edge_length, center + half))
    return tuple((start, end) for start, end in intervals if end - start > 0.015)


def _architecture_intersections(
    first: tuple[tuple[float, float], ...],
    second: tuple[float, float],
) -> tuple[tuple[float, float], ...]:
    start, end = second
    return tuple(
        (max(a, start), min(b, end))
        for a, b in first
        if min(b, end) - max(a, start) > 0.015
    )


def _architecture_wall_mesh(
    *,
    name: str,
    start: Vec2,
    end: Vec2,
    span_bottom: tuple[float, float],
    span_top: tuple[float, float] | None,
    depth_bottom: float,
    depth_top: float,
    z_bottom: float,
    z_top: float,
    material: PrimitiveMaterial,
    metadata: dict[str, Any],
) -> PrimitiveMesh:
    """Create one flat wall-local panel, including trapezoids and coves."""

    length = _edge_length(start, end)
    tx = (end[0] - start[0]) / max(length, 1.0e-8)
    ty = (end[1] - start[1]) / max(length, 1.0e-8)
    # Footprints are CCW, so their interior lies to the left of each edge.
    nx, ny = -ty, tx
    top_span = span_bottom if span_top is None else span_top

    def point(distance: float, depth: float, z: float) -> Vec3:
        return (
            start[0] + tx * distance + nx * depth,
            start[1] + ty * distance + ny * depth,
            z,
        )

    vertices = (
        point(span_bottom[0], depth_bottom, z_bottom),
        point(span_bottom[1], depth_bottom, z_bottom),
        point(top_span[1], depth_top, z_top),
        point(top_span[0], depth_top, z_top),
    )
    return _planar_surface_mesh(
        name=name,
        vertices=vertices,
        faces=((0, 1, 2), (0, 2, 3)),
        material=material,
        metadata={**dict(material.metadata), **metadata},
    )


def _architecture_closed_wall_prism_meshes(
    *,
    name: str,
    start: Vec2,
    end: Vec2,
    span: tuple[float, float],
    depth_back: float,
    depth_front: float,
    z_bottom: float,
    z_top: float,
    material: PrimitiveMaterial,
    metadata: dict[str, Any],
) -> tuple[PrimitiveMesh, ...]:
    """Build a closed wall-local prism with world-tiled UVs on every face."""

    length = _edge_length(start, end)
    if length <= 1.0e-8 or span[1] - span[0] <= 0.015:
        return ()
    if depth_front - depth_back <= 0.015 or z_top - z_bottom <= 0.015:
        return ()
    tx = (end[0] - start[0]) / length
    ty = (end[1] - start[1]) / length
    nx, ny = -ty, tx

    def point(distance: float, depth: float, z: float) -> Vec3:
        return (
            start[0] + tx * distance + nx * depth,
            start[1] + ty * distance + ny * depth,
            z,
        )

    back_bottom_start = point(span[0], depth_back, z_bottom)
    back_bottom_end = point(span[1], depth_back, z_bottom)
    back_top_start = point(span[0], depth_back, z_top)
    back_top_end = point(span[1], depth_back, z_top)
    front_bottom_start = point(span[0], depth_front, z_bottom)
    front_bottom_end = point(span[1], depth_front, z_bottom)
    front_top_start = point(span[0], depth_front, z_top)
    front_top_end = point(span[1], depth_front, z_top)
    faces = {
        "front": (front_bottom_start, front_bottom_end, front_top_end, front_top_start),
        "back": (back_bottom_end, back_bottom_start, back_top_start, back_top_end),
        "bottom": (back_bottom_start, back_bottom_end, front_bottom_end, front_bottom_start),
        "top": (back_top_start, front_top_start, front_top_end, back_top_end),
        "start": (back_bottom_start, front_bottom_start, front_top_start, back_top_start),
        "end": (front_bottom_end, back_bottom_end, back_top_end, front_top_end),
    }
    common = {**dict(material.metadata), **metadata, "closed_geometry": True}
    return tuple(
        _planar_surface_mesh(
            name=f"{name}_{part}",
            vertices=vertices,
            faces=((0, 1, 2), (0, 2, 3)),
            material=material,
            metadata={**common, "prism_part": part},
        )
        for part, vertices in faces.items()
    )


def _korriban_chamber_corner_buttress_meshes(
    *,
    room_resref: str,
    points: tuple[Vec2, ...],
    floor_z: float,
    wall_height: float,
    base_material: PrimitiveMaterial,
    capital_material: PrimitiveMaterial,
    common: dict[str, Any],
    base_role: str = "sith_chamber_corner_buttress",
    capital_role: str = "sith_chamber_vault_capital",
    base_height_fraction: float = 3.6375 / 10.35,
    maximum_base_width: float = 3.45,
    maximum_capital_width: float = 4.20,
    source_measurement: str = "m39aa_07",
) -> tuple[PrimitiveMesh, ...]:
    """Build the massive two-stage corner supports measured in m39aa_07.

    The stock chamber uses 3.45 m lower corner blocks followed by larger
    corbelled capitals that carry the high vault.  The authored version keeps
    that measured maximum but scales down for smaller legal chamber footprints;
    it never stretches one texture island over the generated support.
    """

    span_x = max(point[0] for point in points) - min(point[0] for point in points)
    span_y = max(point[1] for point in points) - min(point[1] for point in points)
    minimum_span = min(span_x, span_y)
    base_width = min(maximum_base_width, max(1.35, minimum_span * 0.16))
    base_top = floor_z + wall_height * base_height_fraction
    capital_top = floor_z + wall_height
    layers = (
        (
            base_role,
            floor_z,
            base_top,
            base_width,
            base_material,
            f"{source_measurement} lower corner support",
            maximum_base_width,
        ),
        (
            capital_role,
            base_top - min(0.08, wall_height * 0.01),
            capital_top,
            min(maximum_capital_width, base_width * 1.28),
            capital_material,
            f"{source_measurement} upper corner capital",
            maximum_capital_width,
        ),
    )
    meshes: list[PrimitiveMesh] = []
    for corner_index, point in enumerate(points):
        previous = points[(corner_index - 1) % len(points)]
        following = points[(corner_index + 1) % len(points)]
        previous_length = max(_edge_length(point, previous), 1.0e-8)
        following_length = max(_edge_length(point, following), 1.0e-8)
        to_previous = (
            (previous[0] - point[0]) / previous_length,
            (previous[1] - point[1]) / previous_length,
        )
        to_following = (
            (following[0] - point[0]) / following_length,
            (following[1] - point[1]) / following_length,
        )
        for role, z_bottom, z_top, width, material, source_label, measured_width in layers:
            chamfer = width * 0.35
            base_points = (
                point,
                (
                    point[0] + to_following[0] * width,
                    point[1] + to_following[1] * width,
                ),
                (
                    point[0] + to_following[0] * width + to_previous[0] * chamfer,
                    point[1] + to_following[1] * width + to_previous[1] * chamfer,
                ),
                (
                    point[0] + to_following[0] * chamfer + to_previous[0] * width,
                    point[1] + to_following[1] * chamfer + to_previous[1] * width,
                ),
                (
                    point[0] + to_previous[0] * width,
                    point[1] + to_previous[1] * width,
                ),
            )
            bottom = tuple((x, y, z_bottom) for x, y in base_points)
            top = tuple((x, y, z_top) for x, y in base_points)
            metadata = {
                **dict(material.metadata),
                **common,
                "architecture_role": role,
                "surface_role": "wall",
                "corner_index": corner_index,
                "beveled_geometry": True,
                "source_measurement": source_label,
                "measured_maximum_width_m": measured_width,
            }
            cap_faces = tuple((0, index, index + 1) for index in range(1, len(base_points) - 1))
            meshes.append(
                _planar_surface_mesh(
                    name=f"{room_resref}_{role}_c{corner_index + 1:02d}_top",
                    vertices=top,
                    faces=cap_faces,
                    material=material,
                    metadata={**metadata, "buttress_part": "top"},
                )
            )
            meshes.append(
                _planar_surface_mesh(
                    name=f"{room_resref}_{role}_c{corner_index + 1:02d}_bottom",
                    vertices=bottom,
                    faces=tuple((c, b, a) for a, b, c in cap_faces),
                    material=material,
                    metadata={**metadata, "buttress_part": "bottom"},
                )
            )
            for face_index in range(len(base_points)):
                next_index = (face_index + 1) % len(base_points)
                meshes.append(
                    _planar_surface_mesh(
                        name=f"{room_resref}_{role}_c{corner_index + 1:02d}_side{face_index + 1:02d}",
                        vertices=(
                            bottom[face_index],
                            bottom[next_index],
                            top[next_index],
                            top[face_index],
                        ),
                        faces=((0, 1, 2), (0, 2, 3)),
                        material=material,
                        metadata={**metadata, "buttress_part": "side", "buttress_face": face_index},
                    )
                )
    return tuple(meshes)


def _korriban_burial_niche_meshes(
    *,
    room_resref: str,
    points: tuple[Vec2, ...],
    openings_by_edge: dict[int, tuple[FloorPlanWallOpening, ...]],
    floor_z: float,
    wall_height: float,
    wall_material: PrimitiveMaterial,
    accent_material: PrimitiveMaterial,
    trim_material: PrimitiveMaterial,
    common: dict[str, Any],
) -> tuple[PrimitiveMesh, ...]:
    """Build opening-aware burial niches and sarcophagus plinths."""

    meshes: list[PrimitiveMesh] = []
    z0 = floor_z
    niche_top = floor_z + min(wall_height - 0.5, 5.15)
    for edge_index, start in enumerate(points):
        end = points[(edge_index + 1) % len(points)]
        edge_length = _edge_length(start, end)
        if edge_length < 2.0:
            continue
        openings = openings_by_edge.get(edge_index, ())
        bay_count = max(1, int(math.ceil(edge_length / 4.5)))
        bay_width = edge_length / bay_count
        for bay_index in range(bay_count):
            bay_start = bay_index * bay_width + min(0.35, bay_width * 0.10)
            bay_end = (bay_index + 1) * bay_width - min(0.35, bay_width * 0.10)
            if bay_end - bay_start < 1.2:
                continue
            if any(
                max(bay_start, float(opening.center_fraction) * edge_length - float(opening.width) * 0.5)
                < min(bay_end, float(opening.center_fraction) * edge_length + float(opening.width) * 0.5)
                and float(opening.bottom) < 5.2
                and float(opening.bottom) + float(opening.height) > 0.5
                for opening in openings
            ):
                continue
            width = bay_end - bay_start
            jamb = min(0.28, width * 0.10)
            niche_metadata = {
                **common,
                "edge_index": edge_index,
                "burial_bay": bay_index,
                "beveled_geometry": True,
                "source_measurement": "m38aa_11 3 m relief/dead-end burial cadence",
            }
            meshes.append(
                _architecture_wall_mesh(
                    name=f"{room_resref}_burial_niche_back_e{edge_index + 1:02d}_b{bay_index + 1:02d}",
                    start=start,
                    end=end,
                    span_bottom=(bay_start + jamb, bay_end - jamb),
                    span_top=None,
                    depth_bottom=0.76,
                    depth_top=0.82,
                    z_bottom=z0 + 0.72,
                    z_top=niche_top - 0.38,
                    material=accent_material,
                    metadata={**niche_metadata, "architecture_role": "burial_niche_back"},
                )
            )
            for side, span in (
                ("left", (bay_start, bay_start + jamb)),
                ("right", (bay_end - jamb, bay_end)),
            ):
                meshes.extend(
                    _architecture_closed_wall_prism_meshes(
                        name=f"{room_resref}_burial_niche_{side}_e{edge_index + 1:02d}_b{bay_index + 1:02d}",
                        start=start,
                        end=end,
                        span=span,
                        depth_back=0.72,
                        depth_front=1.08,
                        z_bottom=z0 + 0.58,
                        z_top=niche_top,
                        material=trim_material,
                        metadata={**niche_metadata, "architecture_role": "burial_niche_jamb"},
                    )
                )
            meshes.extend(
                _architecture_closed_wall_prism_meshes(
                    name=f"{room_resref}_burial_niche_lintel_e{edge_index + 1:02d}_b{bay_index + 1:02d}",
                    start=start,
                    end=end,
                    span=(bay_start, bay_end),
                    depth_back=0.70,
                    depth_front=1.12,
                    z_bottom=niche_top - 0.42,
                    z_top=niche_top,
                    material=trim_material,
                    metadata={**niche_metadata, "architecture_role": "burial_niche_lintel"},
                )
            )
            plinth_margin = width * 0.18
            meshes.extend(
                _architecture_closed_wall_prism_meshes(
                    name=f"{room_resref}_burial_plinth_e{edge_index + 1:02d}_b{bay_index + 1:02d}",
                    start=start,
                    end=end,
                    span=(bay_start + plinth_margin, bay_end - plinth_margin),
                    depth_back=0.70,
                    depth_front=1.55,
                    z_bottom=z0 + 0.16,
                    z_top=z0 + 0.68,
                    material=wall_material,
                    metadata={**niche_metadata, "architecture_role": "burial_sarcophagus_plinth"},
                )
            )
    return tuple(meshes)


def _korriban_monumental_pylon_meshes(
    *,
    room_resref: str,
    points: tuple[Vec2, ...],
    openings_by_edge: dict[int, tuple[FloorPlanWallOpening, ...]],
    floor_z: float,
    wall_height: float,
    wall_material: PrimitiveMaterial,
    accent_material: PrimitiveMaterial,
    common: dict[str, Any],
) -> tuple[PrimitiveMesh, ...]:
    """Build the giant 10.5 m-cadence wall pylons measured in m39aa_07."""

    meshes: list[PrimitiveMesh] = []
    for edge_index, start in enumerate(points):
        end = points[(edge_index + 1) % len(points)]
        edge_length = _edge_length(start, end)
        openings = openings_by_edge.get(edge_index, ())
        bay_count = max(1, int(math.ceil(edge_length / 10.5)))
        bay_width = edge_length / bay_count
        for bay_index in range(bay_count):
            center = (bay_index + 0.5) * bay_width
            half = min(1.20, bay_width * 0.16)
            span = (max(0.0, center - half), min(edge_length, center + half))
            if any(
                max(span[0], float(opening.center_fraction) * edge_length - float(opening.width) * 0.5)
                < min(span[1], float(opening.center_fraction) * edge_length + float(opening.width) * 0.5)
                for opening in openings
            ):
                continue
            pylon_metadata = {
                **common,
                "edge_index": edge_index,
                "monumental_bay": bay_index,
                "beveled_geometry": True,
                "source_measurement": "m39aa_07 10.5 m wall module and 22.08 m vault rise",
            }
            meshes.extend(
                _architecture_closed_wall_prism_meshes(
                    name=f"{room_resref}_monumental_pylon_e{edge_index + 1:02d}_b{bay_index + 1:02d}",
                    start=start,
                    end=end,
                    span=span,
                    depth_back=0.80,
                    depth_front=2.80,
                    z_bottom=floor_z + 0.22,
                    z_top=floor_z + wall_height * 0.56,
                    material=accent_material,
                    metadata={**pylon_metadata, "architecture_role": "monumental_tomb_pylon"},
                )
            )
            capital_half = min(2.10, bay_width * 0.28)
            meshes.extend(
                _architecture_closed_wall_prism_meshes(
                    name=f"{room_resref}_monumental_capital_e{edge_index + 1:02d}_b{bay_index + 1:02d}",
                    start=start,
                    end=end,
                    span=(max(0.0, center - capital_half), min(edge_length, center + capital_half)),
                    depth_back=1.20,
                    depth_front=4.20,
                    z_bottom=floor_z + wall_height * 0.56,
                    z_top=floor_z + wall_height * 0.82,
                    material=wall_material,
                    metadata={**pylon_metadata, "architecture_role": "monumental_corbel_capital"},
                )
            )
    return tuple(meshes)


def _korriban_junction_crown_meshes(
    *,
    room_resref: str,
    points: tuple[Vec2, ...],
    floor_z: float,
    wall_height: float,
    material: PrimitiveMaterial,
    common: dict[str, Any],
) -> tuple[PrimitiveMesh, ...]:
    """Add a recessed cross-vault crown above three- and four-way junctions."""

    minimum_span = min(
        max(point[0] for point in points) - min(point[0] for point in points),
        max(point[1] for point in points) - min(point[1] for point in points),
    )
    outer_depth = min(1.10, minimum_span * 0.08)
    inner_depth = min(2.40, minimum_span * 0.18)
    rings, _scale = _architecture_profile_rings(points, (outer_depth, inner_depth))
    meshes: list[PrimitiveMesh] = []
    for edge_index, start in enumerate(points):
        end = points[(edge_index + 1) % len(points)]
        edge_length = _edge_length(start, end)
        meshes.append(
            _architecture_profile_segment_mesh(
                name=f"{room_resref}_junction_cross_vault_e{edge_index + 1:02d}",
                bottom_ring=rings[outer_depth],
                top_ring=rings[inner_depth],
                edge_index=edge_index,
                span=(0.0, edge_length),
                source_start=start,
                source_end=end,
                edge_length=edge_length,
                z_bottom=floor_z + wall_height - 1.35,
                z_top=floor_z + wall_height - 0.20,
                material=material,
                metadata={
                    **common,
                    "architecture_role": "junction_cross_vault_keystone",
                    "edge_index": edge_index,
                    "beveled_geometry": True,
                    "source_measurement": "m38aa_06/m38aa_08 central cross-vault",
                },
            )
        )
    cap_points = rings[inner_depth]
    vertices = tuple((x, y, floor_z + wall_height - 0.20) for x, y in cap_points)
    meshes.append(
        _planar_surface_mesh(
            name=f"{room_resref}_junction_cross_vault_cap",
            vertices=vertices,
            faces=tuple((c, b, a) for a, b, c in triangulate_floor_plan_points(cap_points)),
            material=material,
            metadata={
                **common,
                "architecture_role": "junction_cross_vault_cap",
                "surface_role": "ceiling",
                "beveled_geometry": True,
            },
        )
    )
    return tuple(meshes)


def _architecture_door_transition_meshes(
    *,
    room_resref: str,
    profile: str,
    edge_index: int,
    start: Vec2,
    end: Vec2,
    edge_length: float,
    floor_z: float,
    wall_height: float,
    openings: tuple[FloorPlanWallOpening, ...],
    infill_material: PrimitiveMaterial,
    trim_material: PrimitiveMaterial,
    light_material: PrimitiveMaterial,
    common: dict[str, Any],
) -> tuple[PrimitiveMesh, ...]:
    """Blend a generated wall into the authentic DOR_LHR01 outer frame."""

    meshes: list[PrimitiveMesh] = []
    for opening in openings:
        metadata = dict(opening.metadata or {})
        door_model = str(metadata.get("door_model_resref") or "").strip().lower()
        if door_model == "dor_lko04":
            # K1/K2 tomb rooms supply a deep carved surround around the
            # DOR_LKO04 actor. The door model is only the moving assembly; a
            # bare boolean cut therefore exposes every profiled-wall course as
            # a row of jagged ends when the panels retract. Rebuild the
            # measured 6.802 m outer frame as three stepped stone tiers plus a
            # closed reveal and threshold. These are visual surfaces only:
            # the exact retail WOK threshold remains the room portal.
            center = max(0.0, min(edge_length, float(opening.center_fraction) * edge_length))
            half_width = min(edge_length * 0.5, float(opening.width) * 0.5)
            inner_start = max(0.0, center - half_width)
            inner_end = min(edge_length, center + half_width)
            requested_outer_width = float(
                metadata.get("door_outer_width_m")
                or metadata.get("door_frame_width_m")
                or (float(opening.width) + 1.552)
            )
            outer_half = min(edge_length * 0.5, max(half_width + 0.24, requested_outer_width * 0.5))
            outer_start = max(0.0, center - outer_half)
            outer_end = min(edge_length, center + outer_half)
            opening_bottom = max(0.0, float(opening.bottom))
            opening_top = min(wall_height - 0.01, opening_bottom + float(opening.height))
            requested_outer_height = float(
                metadata.get("door_outer_height_m")
                or metadata.get("door_frame_height_m")
                or wall_height
            )
            outer_top = min(
                wall_height - 0.005,
                max(opening_top + 0.08, requested_outer_height),
            )
            jamb_width = max(0.0, min(inner_start - outer_start, outer_end - inner_end))
            frame_metadata = {
                **common,
                "opening_name": str(opening.name or ""),
                "door_model_resref": "dor_lko04",
                "door_aperture_width_m": float(opening.width),
                "door_outer_width_m": (outer_end - outer_start),
                "architecture_role": "korriban_door_frame",
                "surface_role": "architectural_detail",
                "vanilla_measurement_source": "DOR_LKO04 + m38aa_02 WOK threshold",
            }
            tiers = (
                ("outer", 0.835, trim_material),
                ("middle", 0.935, infill_material),
                ("inner", 1.035, trim_material),
            )
            for tier_index, (tier_name, depth, material) in enumerate(tiers):
                lateral_inset = min(jamb_width * 0.58, jamb_width * 0.22 * tier_index)
                tier_start = min(inner_start, outer_start + lateral_inset)
                tier_end = max(inner_end, outer_end - lateral_inset)
                tier_top = max(
                    opening_top + 0.025,
                    outer_top - min(0.075, lateral_inset * 0.16),
                )
                parts = (
                    ("left", (tier_start, inner_start), floor_z + opening_bottom, floor_z + tier_top),
                    ("right", (inner_end, tier_end), floor_z + opening_bottom, floor_z + tier_top),
                    ("lintel", (tier_start, tier_end), floor_z + opening_top, floor_z + tier_top),
                )
                for part, span, z0, z1 in parts:
                    if span[1] - span[0] <= 0.012 or z1 - z0 <= 0.012:
                        continue
                    meshes.append(
                        _architecture_wall_mesh(
                            name=(
                                f"{room_resref}_{profile}_e{edge_index + 1:02d}_"
                                f"korriban_door_{tier_name}_{part}"
                            ),
                            start=start,
                            end=end,
                            span_bottom=span,
                            span_top=None,
                            depth_bottom=depth,
                            depth_top=depth,
                            z_bottom=z0,
                            z_top=z1,
                            material=material,
                            metadata={
                                **frame_metadata,
                                "architecture_role": f"korriban_door_frame_{tier_name}",
                                "door_frame_tier": tier_index,
                                "door_frame_part": part,
                                "beveled_geometry": True,
                            },
                        )
                    )

            tx = (float(end[0]) - float(start[0])) / max(edge_length, 1.0e-8)
            ty = (float(end[1]) - float(start[1])) / max(edge_length, 1.0e-8)
            nx, ny = -ty, tx

            def portal_point(distance: float, depth: float, z_value: float) -> Vec3:
                return (
                    float(start[0]) + tx * float(distance) + nx * float(depth),
                    float(start[1]) + ty * float(distance) + ny * float(depth),
                    float(z_value),
                )

            reveal_depth = tiers[-1][1]
            reveal_rows = (
                (
                    "left",
                    (
                        portal_point(inner_start, 0.0, floor_z + opening_bottom),
                        portal_point(inner_start, reveal_depth, floor_z + opening_bottom),
                        portal_point(inner_start, reveal_depth, floor_z + opening_top),
                        portal_point(inner_start, 0.0, floor_z + opening_top),
                    ),
                ),
                (
                    "right",
                    (
                        portal_point(inner_end, 0.0, floor_z + opening_bottom),
                        portal_point(inner_end, 0.0, floor_z + opening_top),
                        portal_point(inner_end, reveal_depth, floor_z + opening_top),
                        portal_point(inner_end, reveal_depth, floor_z + opening_bottom),
                    ),
                ),
                (
                    "lintel",
                    (
                        portal_point(inner_start, 0.0, floor_z + opening_top),
                        portal_point(inner_start, reveal_depth, floor_z + opening_top),
                        portal_point(inner_end, reveal_depth, floor_z + opening_top),
                        portal_point(inner_end, 0.0, floor_z + opening_top),
                    ),
                ),
                (
                    "threshold",
                    (
                        portal_point(inner_start, 0.0, floor_z + opening_bottom + 0.012),
                        portal_point(inner_end, 0.0, floor_z + opening_bottom + 0.012),
                        portal_point(inner_end, reveal_depth, floor_z + opening_bottom + 0.012),
                        portal_point(inner_start, reveal_depth, floor_z + opening_bottom + 0.012),
                    ),
                ),
            )
            for reveal, vertices in reveal_rows:
                meshes.append(
                    _planar_surface_mesh(
                        name=(
                            f"{room_resref}_{profile}_e{edge_index + 1:02d}_"
                            f"korriban_door_reveal_{reveal}"
                        ),
                        vertices=vertices,
                        faces=((0, 1, 2), (0, 2, 3), (2, 1, 0), (3, 2, 0)),
                        material=trim_material,
                        metadata={
                            **frame_metadata,
                            "architecture_role": "korriban_door_transition_reveal",
                            "door_frame_part": reveal,
                            "sealed_transition_reveal": True,
                        },
                    )
                )
            continue
        if door_model != "dor_lhr01":
            continue
        center = max(0.0, min(edge_length, float(opening.center_fraction) * edge_length))
        half_width = min(edge_length * 0.5, float(opening.width) * 0.5)
        inner_start = max(0.0, center - half_width)
        inner_end = min(edge_length, center + half_width)
        trim_width = min(0.22, max(0.12, edge_length * 0.025))
        outer_start = max(0.0, inner_start - trim_width)
        outer_end = min(edge_length, inner_end + trim_width)
        opening_bottom = max(0.0, float(opening.bottom))
        opening_top = min(wall_height - 0.015, opening_bottom + float(opening.height))
        outer_top = min(wall_height - 0.015, opening_top + trim_width)
        frame_metadata = {
            **common,
            "opening_name": str(opening.name or ""),
            "door_model_resref": "dor_lhr01",
            "architecture_role": "endar_door_frame",
            "surface_role": "architectural_detail",
        }
        parts = (
            ("left", (outer_start, inner_start), floor_z + opening_bottom, floor_z + outer_top),
            ("right", (inner_end, outer_end), floor_z + opening_bottom, floor_z + outer_top),
            ("lintel", (outer_start, outer_end), floor_z + opening_top, floor_z + outer_top),
        )
        for part, span, z0, z1 in parts:
            if span[1] - span[0] <= 0.015 or z1 - z0 <= 0.015:
                continue
            meshes.append(
                _architecture_wall_mesh(
                    name=f"{room_resref}_{profile}_e{edge_index + 1:02d}_door_frame_{part}",
                    start=start,
                    end=end,
                    span_bottom=span,
                    span_top=None,
                    depth_bottom=0.145,
                    depth_top=0.145,
                    z_bottom=z0,
                    z_top=z1,
                    material=trim_material,
                    metadata={**frame_metadata, "door_frame_part": part},
                )
            )
        # DOR_LHR01 is an octagonal/rounded portal inside a rectangular MDL
        # transition envelope. A plain rectangular boolean cut leaves the
        # four corner voids visible from the authored-room side. Fill those
        # corners and close the reveal depth so this side reads like the
        # vanilla LHR transition shell instead of a ring pasted over a hole.
        tx = (float(end[0]) - float(start[0])) / max(edge_length, 1.0e-8)
        ty = (float(end[1]) - float(start[1])) / max(edge_length, 1.0e-8)
        nx, ny = -ty, tx

        def portal_point(distance: float, depth: float, z_value: float) -> Vec3:
            return (
                float(start[0]) + tx * float(distance) + nx * float(depth),
                float(start[1]) + ty * float(distance) + ny * float(depth),
                float(z_value),
            )

        face_depth = 0.142
        chamfer = min(0.62, max(0.28, float(opening.height) * 0.17), float(opening.width) * 0.14)
        corner_rows = (
            (
                "upper_left",
                (
                    portal_point(inner_start, face_depth, floor_z + opening_top),
                    portal_point(inner_start + chamfer, face_depth, floor_z + opening_top),
                    portal_point(inner_start, face_depth, floor_z + opening_top - chamfer),
                ),
            ),
            (
                "upper_right",
                (
                    portal_point(inner_end, face_depth, floor_z + opening_top),
                    portal_point(inner_end, face_depth, floor_z + opening_top - chamfer),
                    portal_point(inner_end - chamfer, face_depth, floor_z + opening_top),
                ),
            ),
            (
                "lower_left",
                (
                    portal_point(inner_start, face_depth, floor_z + opening_bottom),
                    portal_point(inner_start, face_depth, floor_z + opening_bottom + chamfer),
                    portal_point(inner_start + chamfer, face_depth, floor_z + opening_bottom),
                ),
            ),
            (
                "lower_right",
                (
                    portal_point(inner_end, face_depth, floor_z + opening_bottom),
                    portal_point(inner_end - chamfer, face_depth, floor_z + opening_bottom),
                    portal_point(inner_end, face_depth, floor_z + opening_bottom + chamfer),
                ),
            ),
        )
        for corner, vertices in corner_rows:
            meshes.append(
                _planar_surface_mesh(
                    name=f"{room_resref}_{profile}_e{edge_index + 1:02d}_door_transition_{corner}",
                    vertices=vertices,
                    faces=((0, 1, 2), (2, 1, 0)),
                    material=infill_material,
                    metadata={
                        **frame_metadata,
                        "architecture_role": "endar_door_transition_infill",
                        "door_frame_part": corner,
                        "sealed_transition_corner": True,
                    },
                )
            )

        reveal_depth = 0.165
        reveal_rows = (
            (
                "left",
                (
                    portal_point(inner_start, 0.0, floor_z + opening_bottom),
                    portal_point(inner_start, reveal_depth, floor_z + opening_bottom),
                    portal_point(inner_start, reveal_depth, floor_z + opening_top),
                    portal_point(inner_start, 0.0, floor_z + opening_top),
                ),
            ),
            (
                "right",
                (
                    portal_point(inner_end, 0.0, floor_z + opening_bottom),
                    portal_point(inner_end, 0.0, floor_z + opening_top),
                    portal_point(inner_end, reveal_depth, floor_z + opening_top),
                    portal_point(inner_end, reveal_depth, floor_z + opening_bottom),
                ),
            ),
            (
                "lintel",
                (
                    portal_point(inner_start, 0.0, floor_z + opening_top),
                    portal_point(inner_start, reveal_depth, floor_z + opening_top),
                    portal_point(inner_end, reveal_depth, floor_z + opening_top),
                    portal_point(inner_end, 0.0, floor_z + opening_top),
                ),
            ),
        )
        for reveal, vertices in reveal_rows:
            meshes.append(
                _planar_surface_mesh(
                    name=f"{room_resref}_{profile}_e{edge_index + 1:02d}_door_reveal_{reveal}",
                    vertices=vertices,
                    faces=((0, 1, 2), (0, 2, 3), (2, 1, 0), (3, 2, 0)),
                    material=trim_material,
                    metadata={
                        **frame_metadata,
                        "architecture_role": "endar_door_transition_reveal",
                        "door_frame_part": reveal,
                        "sealed_transition_reveal": True,
                    },
                )
            )
        light_width = min(0.055, trim_width * 0.33)
        for side, edge_distance in (("left", inner_start), ("right", inner_end)):
            span = (
                max(outer_start, edge_distance - light_width)
                if side == "left"
                else edge_distance,
                edge_distance
                if side == "left"
                else min(outer_end, edge_distance + light_width),
            )
            if span[1] - span[0] <= 0.012:
                continue
            meshes.append(
                _architecture_wall_mesh(
                    name=f"{room_resref}_{profile}_e{edge_index + 1:02d}_door_frame_light_{side}",
                    start=start,
                    end=end,
                    span_bottom=span,
                    span_top=None,
                    depth_bottom=0.158,
                    depth_top=0.158,
                    z_bottom=floor_z + opening_bottom + 0.06,
                    z_top=floor_z + opening_top - 0.06,
                    material=light_material,
                    metadata={
                        **frame_metadata,
                        "architecture_role": "endar_door_frame_light",
                        "door_frame_part": side,
                    },
                )
            )
    return tuple(meshes)


def architecture_shell_profile(primitive: FloorPlanRoomPrimitive) -> str:
    """Return the structural cross-section used by an architecture recipe."""

    explicit = str(primitive.metadata.get("architecture_shell_profile", "") or "").strip().lower()
    if explicit:
        return explicit
    architecture = str(primitive.metadata.get("architecture_profile", "") or "").strip().lower()
    if architecture == "endar_spire":
        return "endar_corridor"
    if architecture == "harbinger":
        return "harbinger_corridor"
    if architecture == "taris_apartments":
        return "taris_apartment"
    if architecture == "shadowlands":
        return "shadowlands_root_wall"
    if architecture == "korriban_tombs":
        return "korriban_tomb"
    if architecture == "korriban_tombs_k2":
        return "korriban_tomb_ruined"
    if architecture in {"korriban_caves_k1", "korriban_caves_k2"}:
        return "korriban_cave"
    return ""


def _architecture_profile_rings(
    points: tuple[Vec2, ...],
    depths: tuple[float, ...],
) -> tuple[dict[float, tuple[Vec2, ...]], float]:
    """Inset a convex footprint at every cross-section depth.

    Narrow rooms scale the complete profile uniformly instead of allowing one
    band to fold through another.  This keeps the silhouette recognisable while
    preserving valid, consistently wound topology for arbitrary convex plans.
    """

    unique = tuple(sorted({max(0.0, float(depth)) for depth in depths}))
    scale = 1.0
    while scale >= 0.18:
        try:
            rings = {
                depth: points if depth <= 1.0e-8 else inset_floor_plan_points(points, depth * scale)
                for depth in unique
            }
            return rings, scale
        except ValueError:
            scale *= 0.75
    raise ValueError("This room is too narrow for the selected architecture contour.")


def _architecture_profile_segment_mesh(
    *,
    name: str,
    bottom_ring: tuple[Vec2, ...],
    top_ring: tuple[Vec2, ...],
    edge_index: int,
    span: tuple[float, float],
    source_start: Vec2,
    source_end: Vec2,
    edge_length: float,
    z_bottom: float,
    z_top: float,
    material: PrimitiveMaterial,
    metadata: dict[str, Any],
    floor_facing: bool = False,
) -> PrimitiveMesh:
    """Create one opening-aware quad between two inset footprint rings."""

    next_index = (edge_index + 1) % len(bottom_ring)
    tx = (source_end[0] - source_start[0]) / max(edge_length, 1.0e-8)
    ty = (source_end[1] - source_start[1]) / max(edge_length, 1.0e-8)

    def ring_point(ring: tuple[Vec2, ...], distance: float) -> Vec2:
        if distance <= 1.0e-8:
            return ring[edge_index]
        if distance >= edge_length - 1.0e-8:
            return ring[next_index]
        ring_start = ring[edge_index]
        start_shift = (ring_start[0] - source_start[0]) * tx + (ring_start[1] - source_start[1]) * ty
        along = distance - start_shift
        return (ring_start[0] + tx * along, ring_start[1] + ty * along)

    bottom_start = ring_point(bottom_ring, span[0])
    bottom_end = ring_point(bottom_ring, span[1])
    top_start = ring_point(top_ring, span[0])
    top_end = ring_point(top_ring, span[1])
    if floor_facing:
        vertices = (
            (bottom_start[0], bottom_start[1], z_bottom),
            (bottom_end[0], bottom_end[1], z_bottom),
            (top_end[0], top_end[1], z_top),
            (top_start[0], top_start[1], z_top),
        )
    else:
        # With a CCW footprint, bottom -> top -> top-next winds toward the
        # room interior.  The floor shoulder uses the opposite winding so its
        # normal remains predominantly upward.
        vertices = (
            (bottom_start[0], bottom_start[1], z_bottom),
            (top_start[0], top_start[1], z_top),
            (top_end[0], top_end[1], z_top),
            (bottom_end[0], bottom_end[1], z_bottom),
        )
    return _planar_surface_mesh(
        name=name,
        vertices=vertices,
        faces=((0, 1, 2), (0, 2, 3)),
        material=material,
        metadata={**dict(material.metadata), **metadata},
    )


def build_floor_plan_profiled_shell_meshes(primitive: FloorPlanRoomPrimitive) -> tuple[PrimitiveMesh, ...]:
    """Compile the actual room envelope for a vanilla architecture profile.

    Endar corridors are a faceted tunnel, not a decorated box. Taris apartment
    rooms use their own lower service plinth, low wall-panel field, illuminated
    utility belt, inset ceiling shoulder, and recessed 2.55 m ceiling. The
    selected measured cross-section is swept around the user's convex
    footprint, and modular ribs follow the same contour so the style remains
    readable with neutral materials.
    """

    shell_profile = architecture_shell_profile(primitive)
    if shell_profile not in {
        "endar_corridor",
        "harbinger_corridor",
        "taris_apartment",
        "korriban_tomb",
        "korriban_tomb_chamber",
        "korriban_tomb_junction",
        "korriban_tomb_burial",
        "korriban_tomb_monumental",
        "korriban_tomb_ruined",
    } or not primitive.include_walls:
        return ()
    validation = validate_floor_plan_room_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    height = float(primitive.wall_height)
    minimum_height = {
        "taris_apartment": 2.10,
        "korriban_tomb": 3.85,
        "korriban_tomb_chamber": 9.75,
        "korriban_tomb_junction": 9.75,
        "korriban_tomb_burial": 9.75,
        "korriban_tomb_monumental": 20.0,
        "korriban_tomb_ruined": 5.25,
    }.get(shell_profile, 2.35)
    if height < minimum_height:
        label = (
            "Taris apartment"
            if shell_profile == "taris_apartment"
            else "Korriban monumental tomb hall"
            if shell_profile == "korriban_tomb_monumental"
            else "Korriban tomb room"
            if shell_profile
            in {
                "korriban_tomb_chamber",
                "korriban_tomb_junction",
                "korriban_tomb_burial",
            }
            else "Korriban tomb"
            if shell_profile in {"korriban_tomb", "korriban_tomb_ruined"}
            else "Republic-warship corridor"
        )
        raise ValueError(f"The {label} contour requires a wall height of at least {minimum_height:.2f} m.")
    points = _ccw_points(_normalise_points(primitive.points))
    room_resref = _normalise_resref(primitive.room_resref)
    floor_z = float(primitive.z)
    accents = tuple(
        str(value or "").strip().lower()
        for value in tuple(primitive.metadata.get("architecture_accent_textures") or ())
        if str(value or "").strip()
    )
    architecture_profile = str(primitive.metadata.get("architecture_profile", "") or "").strip().lower()
    if architecture_profile == "harbinger":
        defaults = ("har_wl01", "har_tr02", "har_lt01", "har_wl09")
    elif architecture_profile == "taris_apartments":
        defaults = ("lts_pwall04", "lts_trim01", "lts_lite08", "lts_gwall01")
    elif architecture_profile == "korriban_tombs":
        defaults = ("lko_wal09", "lko_wal08", "lko_rocks", "lko_wal07")
    elif architecture_profile == "korriban_tombs_k2":
        defaults = ("kor_wal09", "kor_tr01", "kor_rocks", "kor_wal07a")
    else:
        defaults = ("lhr_red02", "lhr_trim01", "lhr_lit01", "lhr_wall06")
    textures = tuple((accents + defaults)[:4])
    if len(textures) < 4:
        textures = defaults
    floor_edge_texture = (
        "har_fl01"
        if architecture_profile == "harbinger"
        else "lts_floor01"
        if architecture_profile == "taris_apartments"
        else "lko_flr03"
        if architecture_profile == "korriban_tombs"
        else "kor_flr03"
        if architecture_profile == "korriban_tombs_k2"
        else "lhr_flr02"
    )
    floor_edge_material = _architecture_material(floor_edge_texture)
    accent_material = _architecture_material(textures[0])
    trim_material = _architecture_material(textures[1])
    light_material = _architecture_material(textures[2], luminous=True)
    utility_material = _architecture_material(textures[3])
    wall_material = primitive.wall_material or primitive.material
    ceiling_material = primitive.ceiling_material or wall_material

    korriban_profiles = {
        "korriban_tomb",
        "korriban_tomb_chamber",
        "korriban_tomb_junction",
        "korriban_tomb_burial",
        "korriban_tomb_monumental",
        "korriban_tomb_ruined",
    }
    if shell_profile in korriban_profiles:
        is_ruined = shell_profile == "korriban_tomb_ruined"
        if shell_profile == "korriban_tomb_chamber":
            # The playable chambers in m37aa_12/m38aa_08 are roughly
            # 27.266 × 30.0 m with a 10.35 m floor-to-vault rise. m38aa_11
            # confirms a 3.0 m relief cadence, while m39aa_07 contributes
            # 3.45 m corner supports and the corbelled high-vault silhouette.
            span_x = max(point[0] for point in points) - min(point[0] for point in points)
            span_y = max(point[1] for point in points) - min(point[1] for point in points)
            if min(span_x, span_y) < 9.0 or abs(polygon_signed_area(points)) < 81.0:
                raise ValueError(
                    "The Korriban reliquary chamber contour needs a footprint at least "
                    "9 m wide and 81 m²; choose Carved tomb corridor for narrower plans."
                )
            nominal_height = 10.35
            wall_material = _architecture_material("lko_wal07")
            accent_material = _architecture_material("lko_wal09")
            trim_material = _architecture_material("lko_wal08")
            ceiling_material = _architecture_material("lko_rocks")
            levels = (
                (0.00, 0.000 / nominal_height, "", floor_edge_material, True),
                (0.08, 0.180 / nominal_height, "chamber_floor_plinth", floor_edge_material, False),
                (0.22, 0.750 / nominal_height, "chamber_lower_masonry", wall_material, False),
                (0.38, 1.875 / nominal_height, "chamber_relief_dado", accent_material, False),
                (0.55, 5.100 / nominal_height, "chamber_relief_wall", accent_material, False),
                (0.82, 6.300 / nominal_height, "chamber_corbel_course", trim_material, True),
                (1.15, 7.800 / nominal_height, "chamber_vault_shoulder", wall_material, False),
                (1.60, 9.150 / nominal_height, "chamber_upper_vault", accent_material, False),
                (2.10, 1.000, "chamber_ceiling_transition", ceiling_material, False),
            )
            rib_projection = 0.30
            bay_target = 3.00
            rib_role = "sith_chamber_relief_pilaster"
        elif shell_profile == "korriban_tomb_junction":
            span_x = max(point[0] for point in points) - min(point[0] for point in points)
            span_y = max(point[1] for point in points) - min(point[1] for point in points)
            if min(span_x, span_y) < 10.0 or abs(polygon_signed_area(points)) < 100.0:
                raise ValueError(
                    "The Korriban cross-vault junction contour needs a footprint at least "
                    "10 m wide and 100 m²."
                )
            # m38aa_06 measures 10.239 m from its 6.043 m floor to the
            # 16.282 m cross-vault crown. Its major wall blocks repeat at 4.5 m.
            nominal_height = 10.24
            wall_material = _architecture_material("lko_wal07")
            accent_material = _architecture_material("lko_wal09")
            trim_material = _architecture_material("lko_wal08")
            ceiling_material = _architecture_material("lko_rocks")
            levels = (
                (0.00, 0.000 / nominal_height, "", floor_edge_material, True),
                (0.10, 0.180 / nominal_height, "junction_floor_plinth", floor_edge_material, False),
                (0.26, 0.750 / nominal_height, "junction_lower_masonry", wall_material, False),
                (0.46, 2.100 / nominal_height, "junction_pier_base", accent_material, False),
                (0.72, 5.250 / nominal_height, "junction_relief_wall", accent_material, False),
                (1.05, 6.900 / nominal_height, "junction_vault_spring", trim_material, True),
                (1.55, 8.850 / nominal_height, "junction_cross_vault_shoulder", wall_material, False),
                (2.25, 1.000, "junction_ceiling_transition", ceiling_material, False),
            )
            rib_projection = 0.36
            bay_target = 4.50
            rib_role = "sith_junction_vault_pier"
        elif shell_profile == "korriban_tomb_burial":
            span_x = max(point[0] for point in points) - min(point[0] for point in points)
            span_y = max(point[1] for point in points) - min(point[1] for point in points)
            if min(span_x, span_y) < 8.0 or abs(polygon_signed_area(points)) < 64.0:
                raise ValueError(
                    "The Korriban burial alcove contour needs a footprint at least "
                    "8 m wide and 64 m²."
                )
            # m38aa_11 measures 10.275 m from the 0.750 m floor to its
            # 11.025 m vault and uses compact 3 m relief/niche stations.
            nominal_height = 10.275
            wall_material = _architecture_material("lko_wal07")
            accent_material = _architecture_material("lko_wal09")
            trim_material = _architecture_material("lko_wal08")
            ceiling_material = _architecture_material("lko_rocks")
            levels = (
                (0.00, 0.000 / nominal_height, "", floor_edge_material, True),
                (0.08, 0.180 / nominal_height, "burial_floor_plinth", floor_edge_material, False),
                (0.22, 0.750 / nominal_height, "burial_lower_masonry", wall_material, False),
                (0.42, 1.500 / nominal_height, "burial_niche_dado", trim_material, False),
                (0.60, 5.400 / nominal_height, "burial_niche_wall", accent_material, False),
                (0.90, 6.600 / nominal_height, "burial_corbel_course", trim_material, True),
                (1.25, 8.700 / nominal_height, "burial_vault_shoulder", wall_material, False),
                (1.80, 1.000, "burial_ceiling_transition", ceiling_material, False),
            )
            rib_projection = 0.26
            bay_target = 3.00
            rib_role = "sith_burial_niche_pier"
        elif shell_profile == "korriban_tomb_monumental":
            span_x = max(point[0] for point in points) - min(point[0] for point in points)
            span_y = max(point[1] for point in points) - min(point[1] for point in points)
            if min(span_x, span_y) < 18.0 or abs(polygon_signed_area(points)) < 324.0:
                raise ValueError(
                    "The Korriban monumental tomb hall contour needs a footprint at least "
                    "18 m wide and 324 m²."
                )
            # m39aa_07 measures a 42.0 × 31.5 m principal floor and a
            # 22.080 m floor-to-vault rise, with 10.5 m wall modules.
            nominal_height = 22.08
            wall_material = _architecture_material("lko_wal07")
            accent_material = _architecture_material("lko_wal09")
            trim_material = _architecture_material("lko_wal08")
            ceiling_material = _architecture_material("lko_rocks")
            levels = (
                (0.00, 0.000 / nominal_height, "", floor_edge_material, True),
                (0.15, 0.180 / nominal_height, "monumental_floor_plinth", floor_edge_material, False),
                (0.40, 0.750 / nominal_height, "monumental_lower_masonry", wall_material, False),
                (0.75, 3.000 / nominal_height, "monumental_pylon_base", accent_material, False),
                (1.30, 8.000 / nominal_height, "monumental_relief_wall", accent_material, False),
                (2.00, 12.000 / nominal_height, "monumental_corbel_course", trim_material, True),
                (3.20, 16.500 / nominal_height, "monumental_upper_pylon", wall_material, False),
                (4.20, 19.800 / nominal_height, "monumental_vault_shoulder", accent_material, False),
                (5.40, 1.000, "monumental_ceiling_transition", ceiling_material, False),
            )
            rib_projection = 0.65
            bay_target = 10.50
            rib_role = "sith_monumental_section_pier"
        elif not is_ruined:
            # Object1806/Object1753 in m37aa_02 contain the repeated K1 tomb
            # corridor section.  Their *outside* mesh reaches 10.35 m, but the
            # walkable interior aperture is only 3.900 m high and 5.400 m
            # across, with exact lower stations at 0.675 and 1.1625 m.  The
            # previous shell used the outside rock-cap bounds as headroom,
            # producing the oversized box reported in visible testing.
            nominal_height = 3.90
            wall_material = _architecture_material("lko_wal07")
            accent_material = _architecture_material("lko_wal09")
            trim_material = _architecture_material("lko_wal08")
            ceiling_material = _architecture_material("lko_wal07")
            levels = (
                (0.00, 0.000 / nominal_height, "", floor_edge_material, True),
                (0.05, 0.180 / nominal_height, "tomb_floor_plinth", floor_edge_material, False),
                (0.18, 0.180 / nominal_height, "tomb_floor_plinth_cap", trim_material, True),
                (0.18, 0.675 / nominal_height, "lower_tomb_masonry", wall_material, False),
                (0.32, 0.675 / nominal_height, "lower_tomb_step", trim_material, True),
                (0.32, 1.1625 / nominal_height, "sith_relief_base", accent_material, False),
                (0.46, 1.1625 / nominal_height, "sith_relief_shelf", trim_material, True),
                (0.46, 3.300 / nominal_height, "sith_relief_wall", accent_material, False),
                (0.64, 3.300 / nominal_height, "upper_tomb_step", trim_material, True),
                (0.64, 3.750 / nominal_height, "upper_tomb_masonry", wall_material, False),
                (0.82, 3.750 / nominal_height, "tomb_door_crown", trim_material, True),
                (0.82, 1.000, "recessed_tomb_ceiling_transition", ceiling_material, False),
            )
            rib_projection = 0.16
            # The retail corridor shell repeats on a 1.5 m modelling grid.
            bay_target = 1.50
            rib_role = "sith_tomb_section_rib"
        else:
            # 711KOR is a larger ruined chamber family.  Its usable interiors
            # cluster around a 6.25 m floor-to-crown range; the much taller
            # bounds belong to buried rock shells and cloud backdrops.
            nominal_height = 6.25
            wall_material = _architecture_material("kor_wal07a")
            accent_material = _architecture_material("kor_wal09")
            trim_material = _architecture_material("kor_tr01")
            ceiling_material = _architecture_material("kor_wal07a")
            levels = (
                (0.00, 0.000 / nominal_height, "", floor_edge_material, True),
                (0.10, 0.220 / nominal_height, "ruined_floor_plinth", floor_edge_material, False),
                (0.24, 0.220 / nominal_height, "broken_floor_course", trim_material, True),
                (0.24, 0.850 / nominal_height, "ruined_lower_masonry", wall_material, False),
                (0.42, 0.850 / nominal_height, "ruined_relief_step", trim_material, True),
                (0.42, 3.900 / nominal_height, "eroded_sith_relief", accent_material, False),
                (0.72, 3.900 / nominal_height, "broken_vault_shelf", trim_material, True),
                (0.72, 5.250 / nominal_height, "broken_vault_shoulder", wall_material, False),
                (1.10, 5.250 / nominal_height, "eroded_sith_crown", accent_material, True),
                (1.10, 1.000, "ruined_tomb_ceiling_transition", ceiling_material, False),
            )
            rib_projection = 0.22
            bay_target = 3.00
            rib_role = "ruined_sith_tomb_pilaster"
    elif shell_profile == "taris_apartment":
        # Repeated m02aa_03a/m02aa_06a and m02ad counterparts establish the
        # Taris apartment interior stations: 0.187 m skirting, 0.45 m lower
        # service return, 1.35..1.50 m luminous belt, 1.65 m upper panel datum,
        # 1.95/2.10 m shoulder, 2.396 m cove, and 2.55 m inner ceiling. The
        # surrounding stock shell rises to 2.896..3.075 m, which is retained as
        # the recommended floor-to-floor dimension rather than wasted interior
        # headroom. Scaling the station ratios keeps edited heights coherent.
        nominal_height = 2.55
        levels = (
            (0.00, 0.000 / nominal_height, "", floor_edge_material, True),
            (0.05, 0.187 / nominal_height, "taris_floor_edge", floor_edge_material, True),
            (0.02, 0.450 / nominal_height, "taris_lower_service_plinth", utility_material, False),
            (0.02, 1.350 / nominal_height, "taris_wall_panel_zone", wall_material, False),
            (0.05, 1.500 / nominal_height, "integrated_light", light_material, False),
            (0.02, 1.650 / nominal_height, "taris_utility_light_return", accent_material, False),
            (0.03, 1.950 / nominal_height, "taris_upper_wall_panel", wall_material, False),
            (0.14, 2.100 / nominal_height, "taris_upper_shoulder", trim_material, False),
            (0.32, 2.396 / nominal_height, "taris_ceiling_cove", ceiling_material, False),
            (0.32, 1.000, "recessed_ceiling_transition", ceiling_material, False),
        )
        rib_projection = 0.055
        bay_target = 2.40
        rib_role = "structural_rib"
    else:
        # The vertical stations are measured from the repeated Endar/Harbinger
        # corridor shell (m01aa_06a, m01ab_09a, 151har02). 151har02 repeats the
        # same 0.000..3.655 m stations, proving this is a Republic-warship module
        # dimension rather than a one-off screenshot estimate.
        nominal_height = 3.655
        levels = (
            (0.00, 0.00, "", floor_edge_material, True),
            (0.50, 0.176 / nominal_height, "raised_floor_edge", floor_edge_material, True),
            (0.68, 0.695 / nominal_height, "red_inset_panel", accent_material, False),
            (0.52, 0.945 / nominal_height, "lower_bulkhead_return", utility_material, False),
            (0.47, 1.177 / nominal_height, "integrated_light", light_material, False),
            (0.52, 1.472 / nominal_height, "mid_bulkhead", wall_material, False),
            (0.76, 2.242 / nominal_height, "canted_upper_bulkhead", accent_material, False),
            (0.97, 2.676 / nominal_height, "arched_shoulder", trim_material, False),
            (1.10, 2.971 / nominal_height, "ceiling_light_coffer", light_material, False),
            (1.13, 3.221 / nominal_height, "faceted_ceiling_cove", ceiling_material, False),
            (1.13, 1.00, "recessed_ceiling_transition", ceiling_material, False),
        )
        rib_projection = 0.075
        bay_target = 2.55
        rib_role = "arched_rib"
    depths = tuple(level[0] for level in levels) + tuple(level[0] + rib_projection for level in levels)
    rings, depth_scale = _architecture_profile_rings(points, depths)
    openings_by_edge: dict[int, tuple[FloorPlanWallOpening, ...]] = {
        edge_index: tuple(opening for opening in primitive.openings if int(opening.edge_index) == edge_index)
        for edge_index in range(len(points))
    }
    common = {
        "primitive": "floor_plan_profiled_shell",
        "architecture_profile": architecture_profile,
        "architecture_shell_profile": shell_profile,
        "profile_depth_scale": depth_scale,
        "source_module": str(primitive.metadata.get("style_source_module", "") or ""),
        "source_rooms": tuple(primitive.metadata.get("architecture_evidence_rooms") or ()),
    }
    meshes: list[PrimitiveMesh] = []

    for edge_index, start in enumerate(points):
        end = points[(edge_index + 1) % len(points)]
        edge_length = _edge_length(start, end)
        openings = openings_by_edge.get(edge_index, ())
        if edge_length <= 0.05:
            continue
        for band_index in range(1, len(levels)):
            bottom_depth, bottom_fraction, _previous_role, _previous_material, _previous_floor = levels[band_index - 1]
            top_depth, top_fraction, role, material, floor_facing = levels[band_index]
            z_bottom = height * bottom_fraction
            z_top = height * top_fraction
            visible = _architecture_visible_intervals(edge_length, openings, z0=z_bottom, z1=z_top)
            for ordinal, span in enumerate(visible, 1):
                meshes.append(
                    _architecture_profile_segment_mesh(
                        name=f"{room_resref}_{shell_profile}_e{edge_index + 1:02d}_b{band_index:02d}_{ordinal:02d}",
                        bottom_ring=rings[bottom_depth],
                        top_ring=rings[top_depth],
                        edge_index=edge_index,
                        span=span,
                        source_start=start,
                        source_end=end,
                        edge_length=edge_length,
                        z_bottom=floor_z + z_bottom,
                        z_top=floor_z + z_top,
                        material=material,
                        metadata={
                            **common,
                            "edge_index": edge_index,
                            "architecture_role": role,
                            "contour_band": band_index,
                            "surface_role": "ceiling" if "ceiling" in role or role == "faceted_ceiling_cove" else "wall",
                        },
                        floor_facing=floor_facing,
                    )
                )

        # Retail corridor ribs are not vertical pilasters: they wrap the lower
        # wall, upper cant, and ceiling shoulder as one continuous frame.
        bay_count = max(1, int(math.ceil(edge_length / bay_target)))
        bay_width = edge_length / bay_count
        rib_half = (
            min(0.80, bay_width * 0.12)
            if shell_profile == "korriban_tomb_monumental"
            else
            min(0.375, bay_width * 0.18)
            if shell_profile
            in {
                "korriban_tomb_chamber",
                "korriban_tomb_junction",
                "korriban_tomb_burial",
            }
            else min(0.075, bay_width * 0.045)
        )
        # Interior bay boundaries are safe swept strips. Footprint corners are
        # already mitered by the ring topology; adding an edge-local strip at
        # distance zero would collapse against that miter on narrow bands.
        for rib_index in range(1, bay_count):
            center = min(edge_length, rib_index * bay_width)
            rib_span = (max(0.0, center - rib_half), min(edge_length, center + rib_half))
            for band_index in range(1, len(levels)):
                bottom_depth, bottom_fraction, _previous_role, _previous_material, _previous_floor = levels[band_index - 1]
                top_depth, top_fraction, contour_role, _material, floor_facing = levels[band_index]
                z_bottom = height * bottom_fraction
                z_top = height * top_fraction
                visible = _architecture_intersections(
                    _architecture_visible_intervals(edge_length, openings, z0=z_bottom, z1=z_top),
                    rib_span,
                )
                for ordinal, span in enumerate(visible, 1):
                    meshes.append(
                        _architecture_profile_segment_mesh(
                            name=f"{room_resref}_{shell_profile}_e{edge_index + 1:02d}_rib{rib_index + 1:02d}_b{band_index:02d}_{ordinal:02d}",
                            bottom_ring=rings[bottom_depth + rib_projection],
                            top_ring=rings[top_depth + rib_projection],
                            edge_index=edge_index,
                            span=span,
                            source_start=start,
                            source_end=end,
                            edge_length=edge_length,
                            z_bottom=min(floor_z + height, floor_z + z_bottom + 0.012),
                            z_top=min(floor_z + height, floor_z + z_top + 0.012),
                            material=trim_material,
                            metadata={
                                **common,
                                "edge_index": edge_index,
                                "architecture_role": rib_role,
                                "contour_role": contour_role,
                                "contour_band": band_index,
                                "rib_index": rib_index - 1,
                            },
                            floor_facing=floor_facing,
                        )
                    )

        if shell_profile in korriban_profiles:
            # The stock K1 corridor reads as carved masonry because four
            # bevelled relief ledges run continuously between its 1.5 m
            # structural sections.  Baking these as real sloped faces (rather
            # than trusting the diffuse texture to fake the depth) keeps the
            # silhouette recognizable under Map Studio lighting and avoids a
            # flat box even when the wall is viewed at a grazing angle.
            relief_rows = (
                (1.30, 1.44, 0.68, 0.76),
                (1.76, 1.90, 0.70, 0.78),
                (2.22, 2.36, 0.72, 0.80),
                (2.68, 2.82, 0.74, 0.82),
            )
            if shell_profile == "korriban_tomb_ruined":
                relief_rows = (
                    (1.38, 1.54, 0.64, 0.76),
                    (2.12, 2.28, 0.70, 0.84),
                    (3.05, 3.23, 0.76, 0.92),
                    (4.08, 4.26, 0.82, 0.98),
                )
            elif shell_profile == "korriban_tomb_chamber":
                relief_rows = (
                    (1.35, 1.55, 0.66, 0.80),
                    (2.25, 2.45, 0.70, 0.85),
                    (3.15, 3.35, 0.74, 0.90),
                    (4.05, 4.25, 0.78, 0.95),
                    (4.95, 5.15, 0.82, 1.00),
                )
            elif shell_profile == "korriban_tomb_junction":
                relief_rows = (
                    (1.40, 1.62, 0.72, 0.90),
                    (2.80, 3.02, 0.78, 0.98),
                    (4.20, 4.42, 0.84, 1.06),
                    (5.60, 5.82, 0.90, 1.14),
                )
            elif shell_profile == "korriban_tomb_burial":
                relief_rows = (
                    (1.28, 1.48, 0.68, 0.82),
                    (2.30, 2.50, 0.72, 0.88),
                    (3.32, 3.52, 0.76, 0.94),
                    (4.34, 4.54, 0.80, 1.00),
                )
            elif shell_profile == "korriban_tomb_monumental":
                relief_rows = (
                    (2.20, 2.52, 1.02, 1.36),
                    (4.40, 4.72, 1.12, 1.52),
                    (6.60, 6.92, 1.22, 1.68),
                    (8.80, 9.12, 1.32, 1.84),
                )

            def backing_depth_at(local_z: float) -> float:
                """Interpolate the measured shell depth behind one relief edge."""

                for level_index in range(1, len(levels)):
                    lower_depth, lower_fraction = levels[level_index - 1][:2]
                    upper_depth, upper_fraction = levels[level_index][:2]
                    lower_z = height * lower_fraction
                    upper_z = height * upper_fraction
                    if upper_z - lower_z <= 1.0e-8:
                        continue
                    if lower_z - 1.0e-8 <= local_z <= upper_z + 1.0e-8:
                        ratio = max(0.0, min(1.0, (local_z - lower_z) / (upper_z - lower_z)))
                        return (lower_depth + (upper_depth - lower_depth) * ratio) * depth_scale
                return float(levels[-1][0]) * depth_scale

            tx = (end[0] - start[0]) / max(edge_length, 1.0e-8)
            ty = (end[1] - start[1]) / max(edge_length, 1.0e-8)
            nx, ny = -ty, tx

            def relief_point(distance: float, depth: float, z: float) -> Vec3:
                return (
                    start[0] + tx * distance + nx * depth,
                    start[1] + ty * distance + ny * depth,
                    floor_z + z,
                )

            for relief_index, (z0, z1, depth0, depth1) in enumerate(relief_rows, 1):
                if z0 >= height - 0.02:
                    continue
                z1 = min(z1, height - 0.02)
                visible = _architecture_visible_intervals(edge_length, openings, z0=z0, z1=z1)
                for ordinal, span in enumerate(visible, 1):
                    relief_material = trim_material if relief_index % 2 else accent_material
                    relief_role = (
                        "broken_sith_relief_ledge"
                        if shell_profile == "korriban_tomb_ruined"
                        else "beveled_sith_chamber_relief_ledge"
                        if shell_profile == "korriban_tomb_chamber"
                        else f"beveled_{shell_profile.removeprefix('korriban_tomb_')}_relief_ledge"
                        if shell_profile
                        in {
                            "korriban_tomb_junction",
                            "korriban_tomb_burial",
                            "korriban_tomb_monumental",
                        }
                        else "beveled_sith_relief_ledge"
                    )
                    relief_metadata = {
                        **common,
                        "edge_index": edge_index,
                        "architecture_role": relief_role,
                        "relief_row": relief_index - 1,
                        "beveled_geometry": True,
                    }
                    front_depth0 = depth0 * depth_scale
                    front_depth1 = depth1 * depth_scale
                    meshes.append(
                        _architecture_wall_mesh(
                            name=(
                                f"{room_resref}_{shell_profile}_e{edge_index + 1:02d}_"
                                f"relief{relief_index:02d}_{ordinal:02d}"
                            ),
                            start=start,
                            end=end,
                            span_bottom=span,
                            span_top=None,
                            depth_bottom=front_depth0,
                            depth_top=front_depth1,
                            z_bottom=floor_z + z0,
                            z_top=floor_z + z1,
                            material=relief_material,
                            metadata=relief_metadata,
                        )
                    )
                    # Close the relief extrusion against the measured backing
                    # shell. A front quad alone reads as a floating strip and
                    # exposes black slits at grazing angles and doorway cuts.
                    # These four bevel/cap faces make every row a closed,
                    # manifold visual course without altering the room WOK.
                    span_start, span_end = span
                    back_depth0 = backing_depth_at(z0)
                    back_depth1 = backing_depth_at(z1)
                    cap_vertices = {
                        "lower": (
                            relief_point(span_start, back_depth0, z0),
                            relief_point(span_start, front_depth0, z0),
                            relief_point(span_end, front_depth0, z0),
                            relief_point(span_end, back_depth0, z0),
                        ),
                        "upper": (
                            relief_point(span_start, back_depth1, z1),
                            relief_point(span_end, back_depth1, z1),
                            relief_point(span_end, front_depth1, z1),
                            relief_point(span_start, front_depth1, z1),
                        ),
                        "start": (
                            relief_point(span_start, back_depth0, z0),
                            relief_point(span_start, back_depth1, z1),
                            relief_point(span_start, front_depth1, z1),
                            relief_point(span_start, front_depth0, z0),
                        ),
                        "end": (
                            relief_point(span_end, back_depth0, z0),
                            relief_point(span_end, front_depth0, z0),
                            relief_point(span_end, front_depth1, z1),
                            relief_point(span_end, back_depth1, z1),
                        ),
                    }
                    for cap_name, vertices in cap_vertices.items():
                        meshes.append(
                            _planar_surface_mesh(
                                name=(
                                    f"{room_resref}_{shell_profile}_e{edge_index + 1:02d}_"
                                    f"relief{relief_index:02d}_{ordinal:02d}_{cap_name}"
                                ),
                                vertices=vertices,
                                faces=((0, 1, 2), (0, 2, 3)),
                                material=relief_material,
                                metadata={
                                    **relief_metadata,
                                    "architecture_role": f"{relief_role}_cap",
                                    "relief_cap": cap_name,
                                },
                            )
                        )

        if shell_profile in korriban_profiles:
            meshes.extend(
                _architecture_door_transition_meshes(
                    room_resref=room_resref,
                    profile=architecture_profile,
                    edge_index=edge_index,
                    start=start,
                    end=end,
                    edge_length=edge_length,
                    floor_z=floor_z,
                    wall_height=height,
                    openings=openings,
                    infill_material=accent_material,
                    trim_material=trim_material,
                    light_material=light_material,
                    common=common,
                )
            )

    if shell_profile == "korriban_tomb_chamber":
        meshes.extend(
            _korriban_chamber_corner_buttress_meshes(
                room_resref=room_resref,
                points=points,
                floor_z=floor_z,
                wall_height=height,
                base_material=accent_material,
                capital_material=wall_material,
                common=common,
            )
        )
    elif shell_profile == "korriban_tomb_junction":
        meshes.extend(
            _korriban_chamber_corner_buttress_meshes(
                room_resref=room_resref,
                points=points,
                floor_z=floor_z,
                wall_height=height,
                base_material=accent_material,
                capital_material=wall_material,
                common=common,
                base_role="sith_junction_cross_pier",
                capital_role="sith_junction_vault_capital",
                base_height_fraction=0.42,
                maximum_base_width=2.40,
                maximum_capital_width=3.30,
                source_measurement="m38aa_06/m38aa_08",
            )
        )
        meshes.extend(
            _korriban_junction_crown_meshes(
                room_resref=room_resref,
                points=points,
                floor_z=floor_z,
                wall_height=height,
                material=trim_material,
                common=common,
            )
        )
    elif shell_profile == "korriban_tomb_burial":
        meshes.extend(
            _korriban_burial_niche_meshes(
                room_resref=room_resref,
                points=points,
                openings_by_edge=openings_by_edge,
                floor_z=floor_z,
                wall_height=height,
                wall_material=wall_material,
                accent_material=accent_material,
                trim_material=trim_material,
                common=common,
            )
        )
    elif shell_profile == "korriban_tomb_monumental":
        meshes.extend(
            _korriban_chamber_corner_buttress_meshes(
                room_resref=room_resref,
                points=points,
                floor_z=floor_z,
                wall_height=height,
                base_material=accent_material,
                capital_material=wall_material,
                common=common,
                base_role="sith_monumental_corner_pylon",
                capital_role="sith_monumental_vault_capital",
                base_height_fraction=0.36,
                maximum_base_width=5.81,
                maximum_capital_width=7.20,
                source_measurement="m39aa_07",
            )
        )
        meshes.extend(
            _korriban_monumental_pylon_meshes(
                room_resref=room_resref,
                points=points,
                openings_by_edge=openings_by_edge,
                floor_z=floor_z,
                wall_height=height,
                wall_material=wall_material,
                accent_material=accent_material,
                common=common,
            )
        )

    if primitive.include_ceiling:
        final_depth, final_fraction, _role, _material, _floor_facing = levels[-1]
        ceiling_points = rings[final_depth]
        ceiling_z = floor_z + height * final_fraction
        vertices: tuple[Vec3, ...] = tuple((x, y, ceiling_z) for x, y in ceiling_points)
        faces = tuple((c, b, a) for a, b, c in triangulate_floor_plan_points(ceiling_points))
        ceiling_role = {
            "korriban_tomb_chamber": "reliquary_vault_ceiling",
            "korriban_tomb_junction": "junction_vault_ceiling",
            "korriban_tomb_burial": "burial_vault_ceiling",
            "korriban_tomb_monumental": "monumental_vault_ceiling",
        }.get(shell_profile, "recessed_ceiling")
        meshes.append(
            PrimitiveMesh(
                name=f"{room_resref}_{shell_profile}_recessed_ceiling",
                vertices=vertices,
                faces=faces,
                normals=((0.0, 0.0, -1.0),) * len(vertices),
                uvs=_planar_uvs(
                    vertices,
                    repeat_metres=_VANILLA_ARCHITECTURE_UV_METRES.get(
                        str(ceiling_material.texture or "").strip().lower(),
                        3.0,
                    ),
                ),
                texture=ceiling_material.texture,
                diffuse=ceiling_material.diffuse,
                ambient=ceiling_material.ambient,
                metadata={
                    **dict(ceiling_material.metadata),
                    **common,
                    "architecture_role": ceiling_role,
                    "surface_role": "ceiling",
                },
            )
        )
    return tuple(meshes)


def _faceted_quad_surface_mesh(
    *,
    name: str,
    corners: tuple[Vec3, Vec3, Vec3, Vec3],
    material: PrimitiveMaterial,
    metadata: dict[str, Any],
    terrain_uv_scale: float | None = None,
) -> PrimitiveMesh:
    """Build a non-planar organic quad as two independently shaded facets.

    ``terrain_uv_scale`` deliberately projects from world XY instead of giving
    every triangulated patch its own 0..1 island.  Organic terrain needs this
    mode: resetting the UV island per facet turns a broad dirt bank into large,
    visibly triangular texture patches.  KOTOR diffuse textures repeat by
    default, so the projected coordinates retain a continuous, game-valid
    ground scale across adjacent berm segments.
    """

    source_faces = ((corners[0], corners[1], corners[2]), (corners[0], corners[2], corners[3]))
    vertices: list[Vec3] = []
    normals: list[Vec3] = []
    uvs: list[Vec2] = []
    for face_index, triangle in enumerate(source_faces):
        a, b, c = triangle
        ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        cross = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        length = math.sqrt(sum(component * component for component in cross))
        if length <= 1.0e-9:
            raise ValueError(f"{name} cannot contain a degenerate organic facet.")
        normal = tuple(component / length for component in cross)
        vertices.extend(triangle)
        normals.extend((normal, normal, normal))
        if terrain_uv_scale is not None:
            scale = float(terrain_uv_scale)
            if not math.isfinite(scale) or scale <= 0.0:
                raise ValueError("terrain_uv_scale must be a positive finite value.")
            abs_normal = tuple(abs(component) for component in normal)
            if abs_normal[2] >= abs_normal[0] and abs_normal[2] >= abs_normal[1]:
                # Horizontal-ish dirt floors use the usual top-down projection.
                uvs.extend(tuple((float(vertex[0]) * scale, float(vertex[1]) * scale) for vertex in triangle))
            elif abs_normal[0] >= abs_normal[1]:
                # East/west wall banks should climb through V by height; using
                # only XY is what made Shadowlands mud smear into long stripes.
                uvs.extend(tuple((float(vertex[1]) * scale, float(vertex[2]) * scale) for vertex in triangle))
            else:
                uvs.extend(tuple((float(vertex[0]) * scale, float(vertex[2]) * scale) for vertex in triangle))
        else:
            uvs.extend(
                ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0))
                if face_index == 0
                else ((0.0, 0.0), (1.0, 1.0), (0.0, 1.0))
            )
    return PrimitiveMesh(
        name=name,
        vertices=tuple(vertices),
        faces=((0, 1, 2), (3, 4, 5)),
        normals=tuple(normals),
        uvs=tuple(uvs),
        texture=material.texture,
        diffuse=material.diffuse,
        ambient=material.ambient,
        metadata={**dict(material.metadata), **metadata},
    )


def _faceted_triangle_surface_mesh(
    *,
    name: str,
    corners: tuple[Vec3, Vec3, Vec3],
    material: PrimitiveMaterial,
    metadata: dict[str, Any],
    terrain_uv_scale: float | None = None,
) -> PrimitiveMesh:
    """Build one non-degenerate terrain triangle with the same UV policy as a quad."""

    a, b, c = corners
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    length = math.sqrt(sum(component * component for component in cross))
    if length <= 1.0e-9:
        raise ValueError(f"{name} cannot contain a degenerate organic facet.")
    normal = tuple(component / length for component in cross)
    if terrain_uv_scale is not None:
        scale = float(terrain_uv_scale)
        if not math.isfinite(scale) or scale <= 0.0:
            raise ValueError("terrain_uv_scale must be a positive finite value.")
        abs_normal = tuple(abs(component) for component in normal)
        if abs_normal[2] >= abs_normal[0] and abs_normal[2] >= abs_normal[1]:
            uvs = tuple((float(vertex[0]) * scale, float(vertex[1]) * scale) for vertex in corners)
        elif abs_normal[0] >= abs_normal[1]:
            uvs = tuple((float(vertex[1]) * scale, float(vertex[2]) * scale) for vertex in corners)
        else:
            uvs = tuple((float(vertex[0]) * scale, float(vertex[2]) * scale) for vertex in corners)
    else:
        uvs = ((0.0, 0.0), (1.0, 0.0), (0.5, 1.0))
    return PrimitiveMesh(
        name=name,
        vertices=corners,
        faces=((0, 1, 2),),
        normals=(normal, normal, normal),
        uvs=uvs,
        texture=material.texture,
        diffuse=material.diffuse,
        ambient=material.ambient,
        metadata={**dict(material.metadata), **metadata},
    )


def _shadowlands_depth(
    edge_index: int,
    distance: float,
    *,
    base: float,
    amplitude: float,
    channel: float,
) -> float:
    """Return deterministic smooth variation without persisting random state."""

    phase = ((edge_index + 1) * 1.61803398875) + (float(distance) * 0.731) + (channel * 2.417)
    wave = (math.sin(phase) * 0.62) + (math.sin(phase * 1.913 + 0.71) * 0.38)
    return max(0.0, float(base) + float(amplitude) * wave)


def _shadowlands_opening_half_width(opening: FloorPlanWallOpening, z_value: float) -> float:
    """Return the clear half-width of one organic cave opening at ``z_value``.

    Retail Shadowlands transitions are cut through soil and roots, not through
    a rectangular interior doorway.  The lower opening is vertical enough for
    the player, then resolves into a rounded earthen arch.  Sampling this
    profile at each berm strip keeps the opening genuinely open instead of
    placing a decorative arch over a rectangular hole.
    """

    bottom = float(opening.bottom)
    top = bottom + float(opening.height)
    half_width = max(0.01, float(opening.width) * 0.5)
    if z_value < bottom - 1.0e-8 or z_value > top + 1.0e-8:
        return 0.0
    radius = min(half_width, max(0.18, float(opening.height) * 0.48))
    spring = max(bottom, top - radius)
    if z_value <= spring:
        return half_width
    height_over_spring = max(0.0, min(radius, z_value - spring))
    # Retain a tiny, intentional apex rather than producing a degenerate
    # zero-area strip on the final arch segment.
    return max(0.015, math.sqrt(max(0.0, radius * radius - height_over_spring * height_over_spring)))


def _shadowlands_visible_intervals(
    edge_length: float,
    openings: tuple[FloorPlanWallOpening, ...],
    *,
    z_value: float,
) -> tuple[tuple[float, float], ...]:
    """Return wall spans after subtracting round, walkable cave apertures."""

    intervals = [(0.0, float(edge_length))]
    for opening in openings:
        half = _shadowlands_opening_half_width(opening, z_value)
        if half <= 0.0:
            continue
        center = float(opening.center_fraction) * float(edge_length)
        intervals = _subtract_interval(
            intervals,
            max(0.0, center - half),
            min(float(edge_length), center + half),
        )
    return tuple((start, end) for start, end in intervals if end - start > 0.015)


def _shadowlands_profile_depth(
    edge_index: int,
    distance: float,
    *,
    berm_width: float,
    depth_factor: float,
    amplitude_factor: float,
    profile_level: float,
) -> float:
    """Return one shared bank-ring depth.

    Adjacent vertical strips must ask for the *same* ring value at their
    common height.  The old per-band channel differed on each side of a seam,
    which opened the visible triangular gaps reported in the viewport.
    """

    return _shadowlands_depth(
        edge_index,
        distance,
        base=float(berm_width) * float(depth_factor),
        amplitude=float(berm_width) * float(amplitude_factor),
        channel=float(profile_level) + 0.23,
    )


def _shadowlands_connected_cave_connector_meshes(
    *,
    room_resref: str,
    edge_index: int,
    start: Vec2,
    tangent: tuple[float, float],
    inward_normal: tuple[float, float],
    edge_length: float,
    opening: FloorPlanWallOpening,
    floor_z: float,
    berm_width: float,
    material: PrimitiveMaterial,
    common: dict[str, Any],
    architecture_role: str = "shadowlands_cave_connector",
    source_modules: tuple[str, ...] = ("m24aa", "m25aa"),
) -> tuple[PrimitiveMesh, ...]:
    """Build the sealed visual throat for one snapped Shadowlands room join.

    A WOK transition makes movement continuous, but it does not create render
    geometry between an authored dirt bank and a reused retail room.  Leaving
    that volume open is what exposed the editor background at the connection.
    This small, double-sided earthen tube is built *inside* the authored
    clearing.  The connected retail room is clipped at the shared portal
    plane, so neither half overlaps the other while the player corridor stays
    clear and the visual seam is closed from either side.
    """

    opening_metadata = dict(opening.metadata or {})
    target_room = str(opening_metadata.get("connected_room_resref") or "").strip().lower()
    if not target_room:
        return ()
    half_width = max(0.28, float(opening.width) * 0.5 + 0.30)
    crown_radius = min(half_width, max(0.28, float(opening.height) * 0.48))
    spring_height = max(0.0, float(opening.height) - crown_radius)
    # The connector clears the full berm on the authored side of the threshold
    # and intentionally overlaps a short distance into the clipped retail side.
    # Shadowlands modules have irregular soil shells; a razor-thin join leaves
    # sky-colored slivers whenever the vanilla shell bows away from its WOK
    # threshold.  The overlap is visual-only and does not change WOK portals.
    connector_depth = min(4.60, max(1.65, float(berm_width) * 0.95))
    connector_overlap = min(1.10, max(0.55, float(opening.width) * 0.12))
    center_distance = max(0.0, min(float(edge_length), float(opening.center_fraction) * float(edge_length)))
    # Traverse the inside profile from lower-left, up the wall and around the
    # crown, then down to lower-right.  There is no bottom cap: the two WOK
    # floors are the continuous, player-walkable surface.
    profile: list[tuple[float, float]] = [(-half_width, 0.0), (-half_width, spring_height)]
    arc_segments = 7
    for sample_index in range(1, arc_segments + 1):
        angle = math.pi - (math.pi * float(sample_index) / float(arc_segments))
        profile.append((math.cos(angle) * crown_radius, spring_height + math.sin(angle) * crown_radius))
    profile.append((half_width, 0.0))

    def profile_point(lateral: float, height: float, depth: float) -> Vec3:
        return (
            float(start[0]) + float(tangent[0]) * (center_distance + lateral) + float(inward_normal[0]) * depth,
            float(start[1]) + float(tangent[1]) * (center_distance + lateral) + float(inward_normal[1]) * depth,
            float(floor_z) + float(opening.bottom) + height,
        )

    meshes: list[PrimitiveMesh] = []
    for profile_index, (first, second) in enumerate(zip(profile, profile[1:]), 1):
        inner_first = profile_point(first[0], first[1], -connector_overlap)
        inner_second = profile_point(second[0], second[1], -connector_overlap)
        outer_first = profile_point(first[0], first[1], connector_depth)
        outer_second = profile_point(second[0], second[1], connector_depth)
        metadata = {
            **common,
            "edge_index": edge_index,
            "architecture_role": str(architecture_role or "cave_connector"),
            "surface_role": "terrain_cave_connector",
            "opening_name": str(opening.name or ""),
            "connected_room_resref": target_room,
            "connector_depth_m": connector_depth,
            "connector_overlap_m": connector_overlap,
            "connector_direction": "authored_clearing_interior",
            "connector_profile_segment": profile_index,
            "welded_terrain_boundary": True,
            "source_modules": tuple(source_modules),
        }
        # Keep both windings.  KOTOR room geometry is normally culled, and a
        # join must stay opaque whether it is viewed from the authored clearing
        # or from the attached vanilla room.
        meshes.append(
            _faceted_quad_surface_mesh(
                name=f"{room_resref}_shadowlands_e{edge_index + 1:02d}_cave_connector_{profile_index:02d}_in",
                corners=(inner_first, outer_first, outer_second, inner_second),
                material=material,
                metadata=metadata,
                terrain_uv_scale=0.30,
            )
        )
        meshes.append(
            _faceted_quad_surface_mesh(
                name=f"{room_resref}_shadowlands_e{edge_index + 1:02d}_cave_connector_{profile_index:02d}_out",
                corners=(inner_second, outer_second, outer_first, inner_first),
                material=material,
                metadata=metadata,
                terrain_uv_scale=0.30,
            )
        )
    return tuple(meshes)


def build_floor_plan_shadowlands_meshes(primitive: FloorPlanRoomPrimitive) -> tuple[PrimitiveMesh, ...]:
    """Compile an open-air Shadowlands clearing from measured organic forms.

    Upper/Lower Shadowlands floors vary by roughly 10-17 m across 67-131 m
    tiles.  Their playable clearings resolve into broad, weathered dirt banks
    rather than a perimeter of vertical timber walls.  The authored recipe
    therefore uses irregular, walk-up earthen berms as the default boundary;
    retail roots, trunks, and canopy forms are staged explicitly from the
    Shadowlands terrain shelf where their real silhouette can be retained.
    """

    if not primitive.include_walls:
        return ()
    validation = validate_floor_plan_room_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    height = float(primitive.wall_height)
    if height < 2.5:
        raise ValueError("The Shadowlands root-wall contour requires a height of at least 2.50 m.")
    points = _ccw_points(_normalise_points(primitive.points))
    room_resref = _normalise_resref(primitive.room_resref)
    floor_z = float(primitive.z)
    # Use the measured mud/plant palette for the *built* boundary.  Bark is a
    # deliberately sparse accent only: covering every edge with bark made an
    # exterior clearing read as a square, indoor room.
    earth_material = _architecture_material("lka_mud02")
    root_material = _architecture_material("lka_bark06")
    openings_by_edge: dict[int, tuple[FloorPlanWallOpening, ...]] = {
        edge_index: tuple(opening for opening in primitive.openings if int(opening.edge_index) == edge_index)
        for edge_index in range(len(points))
    }
    common = {
        "primitive": "floor_plan_shadowlands_shell",
        "architecture_profile": "shadowlands",
        "architecture_shell_profile": "shadowlands_root_wall",
        "source_module": str(primitive.metadata.get("style_source_module", "") or ""),
        "source_rooms": tuple(primitive.metadata.get("architecture_evidence_rooms") or ()),
        "open_air": True,
    }
    meshes: list[PrimitiveMesh] = []
    min_x = min(float(point[0]) for point in points)
    max_x = max(float(point[0]) for point in points)
    min_y = min(float(point[1]) for point in points)
    max_y = max(float(point[1]) for point in points)
    # A wide bank is the visual contract: it must visibly slope away from the
    # clearing instead of reading as a textured vertical wall.  Limit it for
    # compact footprints so a small encounter space remains usable.
    berm_width = min(4.80, max(1.85, min(max_x - min_x, max_y - min_y) * 0.19))
    # Closed height/depth rings.  Every vertical strip samples these shared
    # values, and the corner caps below stitch adjacent polygon edges.  This
    # is the topology contract that prevents a procedural outdoor boundary
    # from exposing the editor grid through a crack.
    profile_levels = (
        # The first ring is the exact authored floor outline.  Starting it at
        # a positive berm offset left a real slit between terrain and floor;
        # fog merely made that seam harder to notice instead of closing it.
        (0.00, 0.00, 0.000, "earthen_toe"),
        (0.11, 0.24, 0.055, "earthen_toe"),
        (0.42, 0.64, 0.100, "dirt_mound_slope"),
        (0.69, 0.91, 0.130, "weathered_dirt_ridge"),
        (0.90, 1.00, 0.075, "mossy_berm_crown"),
        (1.00, 0.96, 0.040, "mossy_berm_crown"),
    )
    # Three strips per profile band makes the circular cave aperture read as
    # an actual dirt arch rather than a stepped rectangular cutout.
    vertical_subdivisions = 3
    for edge_index, start in enumerate(points):
        end = points[(edge_index + 1) % len(points)]
        edge_length = _edge_length(start, end)
        if edge_length <= 0.05:
            continue
        tx = (end[0] - start[0]) / edge_length
        ty = (end[1] - start[1]) / edge_length
        nx, ny = -ty, tx
        openings = openings_by_edge.get(edge_index, ())
        segment_count = max(1, int(math.ceil(edge_length / 3.40)))
        segment_width = edge_length / segment_count

        def point(distance: float, depth: float, z_value: float) -> Vec3:
            # ``nx, ny`` is the inward normal of the CCW clearing outline.
            # A Shadowlands berm belongs beyond the walkable clearing, not in
            # it: retaining the old inward offset made the ridge read as an
            # indoor ceiling at player height.
            return (
                start[0] + tx * distance - nx * depth,
                start[1] + ty * distance - ny * depth,
                floor_z + z_value,
            )

        for band_index in range(len(profile_levels) - 1):
            z0f, d0f, a0f, role = profile_levels[band_index]
            z1f, d1f, a1f, _next_role = profile_levels[band_index + 1]
            for strip_index in range(vertical_subdivisions):
                strip_lower = float(strip_index) / float(vertical_subdivisions)
                strip_upper = float(strip_index + 1) / float(vertical_subdivisions)
                # Never allow an individual surface to cross a cave aperture
                # breakpoint.  A span pair would otherwise change from two
                # side panels to one full-width panel at the apex, bridging
                # straight across the walkable opening.
                split_fractions = [strip_lower, strip_upper]
                for opening in openings:
                    radius = min(float(opening.width) * 0.5, max(0.18, float(opening.height) * 0.48))
                    for split_z in (
                        float(opening.bottom),
                        max(float(opening.bottom), float(opening.bottom) + float(opening.height) - radius),
                        float(opening.bottom) + float(opening.height),
                    ):
                        normalized = (float(split_z) / height - z0f) / max(1.0e-8, z1f - z0f)
                        if strip_lower + 1.0e-7 < normalized < strip_upper - 1.0e-7:
                            split_fractions.append(normalized)
                split_fractions = sorted(set(split_fractions))
                for substrip_index, (lower_fraction, upper_fraction) in enumerate(
                    zip(split_fractions, split_fractions[1:]),
                    1,
                ):
                    lower_zf = z0f + (z1f - z0f) * lower_fraction
                    upper_zf = z0f + (z1f - z0f) * upper_fraction
                    lower_df = d0f + (d1f - d0f) * lower_fraction
                    upper_df = d0f + (d1f - d0f) * upper_fraction
                    lower_af = a0f + (a1f - a0f) * lower_fraction
                    upper_af = a0f + (a1f - a0f) * upper_fraction
                    z0, z1 = height * lower_zf, height * upper_zf
                    # Sample just inside the strip endpoints so an arch apex
                    # becomes a valid sloped cap instead of a zero-area face.
                    lower_visible = _shadowlands_visible_intervals(edge_length, openings, z_value=z0 + 1.0e-5)
                    upper_visible = _shadowlands_visible_intervals(edge_length, openings, z_value=z1 - 1.0e-5)
                    span_pairs = zip(lower_visible, upper_visible)
                    for fragment_index, (bottom_span, top_span) in enumerate(span_pairs, 1):
                        # A cave arch can narrow as it rises.  Each paired span is
                        # a tapered, fully welded surface rather than two pieces
                        # that leave triangular slits at the opening shoulders.
                        a0, b0 = bottom_span
                        a1, b1 = top_span
                        meshes.append(
                            _faceted_quad_surface_mesh(
                                name=(
                                    f"{room_resref}_shadowlands_e{edge_index + 1:02d}_"
                                    f"{role}_{band_index + 1:02d}_{strip_index + 1:02d}_{substrip_index:02d}_{fragment_index:02d}"
                                ),
                                corners=(
                                    point(a0, _shadowlands_profile_depth(edge_index, a0, berm_width=berm_width, depth_factor=lower_df, amplitude_factor=lower_af, profile_level=band_index + lower_fraction), z0),
                                    point(b0, _shadowlands_profile_depth(edge_index, b0, berm_width=berm_width, depth_factor=lower_df, amplitude_factor=lower_af, profile_level=band_index + lower_fraction), z0),
                                    point(b1, _shadowlands_profile_depth(edge_index, b1, berm_width=berm_width, depth_factor=upper_df, amplitude_factor=upper_af, profile_level=band_index + upper_fraction), z1),
                                    point(a1, _shadowlands_profile_depth(edge_index, a1, berm_width=berm_width, depth_factor=upper_df, amplitude_factor=upper_af, profile_level=band_index + upper_fraction), z1),
                                ),
                                material=earth_material,
                                metadata={
                                    **common,
                                    "edge_index": edge_index,
                                    "architecture_role": role,
                                    "contour_band": band_index,
                                    "vertical_strip": strip_index,
                                    "cave_substrip": substrip_index,
                                    "surface_role": "terrain_wall",
                                    "welded_terrain_boundary": True,
                                    "cave_portal_profile": bool(openings),
                                },
                                terrain_uv_scale=0.30,
                            )
                        )

        # A few exposed roots keep the bank grounded in Kashyyyk without
        # turning every perimeter segment into a vertical tree-trunk fence.
        for boundary_index in range(1, segment_count, 3):
            center = min(edge_length, (boundary_index + 0.42) * segment_width)
            half_bottom = min(0.52, segment_width * 0.20)
            bottom_span = (max(0.0, center - half_bottom), min(edge_length, center + half_bottom))
            visible = _architecture_intersections(
                _shadowlands_visible_intervals(edge_length, openings, z_value=height * 0.31),
                bottom_span,
            )
            for fragment_index, span in enumerate(visible, 1):
                midpoint = (span[0] + span[1]) * 0.5
                half_top = min((span[1] - span[0]) * 0.36, 0.18)
                top_span = (midpoint - half_top, midpoint + half_top)
                meshes.append(
                    _architecture_wall_mesh(
                        name=f"{room_resref}_shadowlands_e{edge_index + 1:02d}_exposed_root_{boundary_index + 1:02d}_{fragment_index:02d}",
                        start=start,
                        end=end,
                        span_bottom=span,
                        span_top=top_span,
                        depth_bottom=_shadowlands_depth(edge_index, center, base=berm_width * 0.30, amplitude=berm_width * 0.05, channel=5.0),
                        depth_top=_shadowlands_depth(edge_index, center, base=berm_width * 0.56, amplitude=berm_width * 0.06, channel=6.0),
                        z_bottom=floor_z + height * 0.08,
                        z_top=floor_z + height * 0.53,
                        material=root_material,
                        metadata={
                            **common,
                            "edge_index": edge_index,
                            "architecture_role": "exposed_root_run",
                            "organic_segment": boundary_index,
                            "surface_role": "terrain_wall",
                        },
                    )
                )

        for opening_index, opening in enumerate(openings):
            meshes.append(
                _architecture_wall_mesh(
                    name=f"{room_resref}_shadowlands_e{edge_index + 1:02d}_cave_portal_lip_{opening_index + 1:02d}",
                    start=start,
                    end=end,
                    span_bottom=(
                        max(0.0, float(opening.center_fraction) * edge_length - float(opening.width) * 0.5 - 0.12),
                        min(edge_length, float(opening.center_fraction) * edge_length + float(opening.width) * 0.5 + 0.12),
                    ),
                    span_top=None,
                    depth_bottom=berm_width * 0.42,
                    depth_top=berm_width * 0.57,
                    # The lip begins *above* the arch apex.  Starting it at
                    # the spring line would turn the opening back into a
                    # rectangular lintel and block the cave silhouette.
                    z_bottom=floor_z + min(height, float(opening.bottom) + float(opening.height)),
                    z_top=floor_z + min(height, float(opening.bottom) + float(opening.height) + 0.18),
                    material=root_material,
                    metadata={
                        **common,
                        "edge_index": edge_index,
                        "architecture_role": "shadowlands_cave_portal_lip",
                        "opening_name": str(opening.name or ""),
                        "source_modules": ("m24aa", "m25aa"),
                        "surface_role": "terrain_wall",
                    },
                )
            )
            meshes.extend(
                _shadowlands_connected_cave_connector_meshes(
                    room_resref=room_resref,
                    edge_index=edge_index,
                    start=start,
                    tangent=(tx, ty),
                    inward_normal=(nx, ny),
                    edge_length=edge_length,
                    opening=opening,
                    floor_z=floor_z,
                    berm_width=berm_width,
                    material=earth_material,
                    common=common,
                )
            )

    # Stitch the wedges created by each outward edge offset.  The cap shares
    # the precise edge-ring vertices on both sides, so it closes polygon
    # corners without a post-process that might alter authored boundaries.
    for corner_index, corner in enumerate(points):
        previous_index = (corner_index - 1) % len(points)
        previous_start = points[previous_index]
        previous_end = corner
        next_start = corner
        next_end = points[(corner_index + 1) % len(points)]
        previous_length = _edge_length(previous_start, previous_end)
        next_length = _edge_length(next_start, next_end)
        if previous_length <= 0.05 or next_length <= 0.05:
            continue
        previous_tx = (previous_end[0] - previous_start[0]) / previous_length
        previous_ty = (previous_end[1] - previous_start[1]) / previous_length
        next_tx = (next_end[0] - next_start[0]) / next_length
        next_ty = (next_end[1] - next_start[1]) / next_length
        previous_normal = (-previous_ty, previous_tx)
        next_normal = (-next_ty, next_tx)

        def corner_point(tangent: tuple[float, float], normal: tuple[float, float], depth: float, z_value: float) -> Vec3:
            del tangent
            return (corner[0] - normal[0] * depth, corner[1] - normal[1] * depth, floor_z + z_value)

        for band_index in range(len(profile_levels) - 1):
            z0f, d0f, a0f, role = profile_levels[band_index]
            z1f, d1f, a1f, _next_role = profile_levels[band_index + 1]
            for strip_index in range(vertical_subdivisions):
                lower_fraction = float(strip_index) / float(vertical_subdivisions)
                upper_fraction = float(strip_index + 1) / float(vertical_subdivisions)
                lower_zf = z0f + (z1f - z0f) * lower_fraction
                upper_zf = z0f + (z1f - z0f) * upper_fraction
                lower_df = d0f + (d1f - d0f) * lower_fraction
                upper_df = d0f + (d1f - d0f) * upper_fraction
                lower_af = a0f + (a1f - a0f) * lower_fraction
                upper_af = a0f + (a1f - a0f) * upper_fraction
                previous_lower = _shadowlands_profile_depth(previous_index, previous_length, berm_width=berm_width, depth_factor=lower_df, amplitude_factor=lower_af, profile_level=band_index + lower_fraction)
                next_lower = _shadowlands_profile_depth(corner_index, 0.0, berm_width=berm_width, depth_factor=lower_df, amplitude_factor=lower_af, profile_level=band_index + lower_fraction)
                previous_upper = _shadowlands_profile_depth(previous_index, previous_length, berm_width=berm_width, depth_factor=upper_df, amplitude_factor=upper_af, profile_level=band_index + upper_fraction)
                next_upper = _shadowlands_profile_depth(corner_index, 0.0, berm_width=berm_width, depth_factor=upper_df, amplitude_factor=upper_af, profile_level=band_index + upper_fraction)
                lower_previous = corner_point((previous_tx, previous_ty), previous_normal, previous_lower, height * lower_zf)
                lower_next = corner_point((next_tx, next_ty), next_normal, next_lower, height * lower_zf)
                upper_next = corner_point((next_tx, next_ty), next_normal, next_upper, height * upper_zf)
                upper_previous = corner_point((previous_tx, previous_ty), previous_normal, previous_upper, height * upper_zf)
                corner_name = f"{room_resref}_shadowlands_corner_{corner_index + 1:02d}_{band_index + 1:02d}_{strip_index + 1:02d}"
                corner_metadata = {
                    **common,
                    "architecture_role": role,
                    "surface_role": "terrain_corner_weld",
                    "corner_index": corner_index,
                    "welded_terrain_boundary": True,
                }
                if math.dist(lower_previous, lower_next) <= 1.0e-8:
                    # The floor-weld ring intentionally collapses at every
                    # footprint corner.  Fill that zero-width lower edge with
                    # one triangle instead of manufacturing a degenerate quad.
                    meshes.append(
                        _faceted_triangle_surface_mesh(
                            name=corner_name,
                            corners=(lower_previous, upper_next, upper_previous),
                            material=earth_material,
                            metadata={**corner_metadata, "corner_topology": "triangle_fan"},
                            terrain_uv_scale=0.30,
                        )
                    )
                else:
                    meshes.append(
                        _faceted_quad_surface_mesh(
                            name=corner_name,
                            corners=(lower_previous, lower_next, upper_next, upper_previous),
                            material=earth_material,
                            metadata=corner_metadata,
                            terrain_uv_scale=0.30,
                        )
                    )
    return tuple(meshes)


def build_floor_plan_korriban_cave_meshes(primitive: FloorPlanRoomPrimitive) -> tuple[PrimitiveMesh, ...]:
    """Compile a sealed, irregular Shyrack-cave passage around a footprint.

    K1 m34aa and K2 710KOR largely share the same cave topology: a continuous
    walkable stone floor, faceted cliff walls, a rounded inward crown, and WOK
    transition mouths without architectural door hooks.  This generator keeps
    that vocabulary while leaving the large retail caverns available as
    draggable room tiles.
    """

    if not primitive.include_walls:
        return ()
    validation = validate_floor_plan_room_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    height = float(primitive.wall_height)
    if height < 4.50:
        raise ValueError("The Shyrack cave contour requires a height of at least 4.50 m.")
    points = _ccw_points(_normalise_points(primitive.points))
    room_resref = _normalise_resref(primitive.room_resref)
    floor_z = float(primitive.z)
    profile = str(primitive.metadata.get("architecture_profile", "") or "").strip().lower()
    is_k2 = profile == "korriban_caves_k2"
    cliff_texture = "kor_cliff01" if is_k2 else "lko_cliff01"
    cliff_material = primitive.wall_material or _architecture_material(cliff_texture)
    ceiling_material = primitive.ceiling_material or cliff_material
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    maximum_depth = min(1.85, max(0.72, min(max_x - min_x, max_y - min_y) * 0.18))
    profile_levels = (
        (0.00, 0.00, 0.000, "cave_floor_weld"),
        (0.14, 0.06, 0.050, "weathered_cave_toe"),
        (0.40, 0.18, 0.110, "shyrack_cliff_wall"),
        (0.69, 0.43, 0.160, "eroded_cave_wall"),
        (0.88, 0.76, 0.190, "canted_rock_shoulders"),
        (1.00, 1.00, 0.130, "faceted_cave_crown"),
    )
    depths = tuple(maximum_depth * level[1] for level in profile_levels)
    rings, depth_scale = _architecture_profile_rings(points, depths)
    ring_cache = dict(rings)

    def profile_ring(depth_factor: float) -> tuple[Vec2, ...]:
        depth = maximum_depth * float(depth_factor)
        cached = ring_cache.get(depth)
        if cached is None:
            cached = points if depth <= 1.0e-8 else inset_floor_plan_points(points, depth * depth_scale)
            ring_cache[depth] = cached
        return cached
    openings_by_edge: dict[int, tuple[FloorPlanWallOpening, ...]] = {
        edge_index: tuple(opening for opening in primitive.openings if int(opening.edge_index) == edge_index)
        for edge_index in range(len(points))
    }
    common = {
        "primitive": "floor_plan_korriban_cave_shell",
        "architecture_profile": profile,
        "architecture_shell_profile": "korriban_cave",
        "profile_depth_scale": depth_scale,
        "source_module": "710kor" if is_k2 else "m34aa",
        "source_rooms": tuple(primitive.metadata.get("architecture_evidence_rooms") or ()),
        "source_geometry_family": "K2 710KOR" if is_k2 else "K1 m34aa",
        "sealed_cave_shell": True,
    }
    meshes: list[PrimitiveMesh] = []

    for edge_index, start in enumerate(points):
        end = points[(edge_index + 1) % len(points)]
        edge_length = _edge_length(start, end)
        if edge_length <= 0.05:
            continue
        tx = (end[0] - start[0]) / edge_length
        ty = (end[1] - start[1]) / edge_length
        nx, ny = -ty, tx
        openings = openings_by_edge.get(edge_index, ())

        def ring_point(ring: tuple[Vec2, ...], distance: float) -> Vec2:
            next_index = (edge_index + 1) % len(ring)
            if distance <= 1.0e-8:
                return ring[edge_index]
            if distance >= edge_length - 1.0e-8:
                return ring[next_index]
            ring_start = ring[edge_index]
            start_shift = (ring_start[0] - start[0]) * tx + (ring_start[1] - start[1]) * ty
            along = distance - start_shift
            return (ring_start[0] + tx * along, ring_start[1] + ty * along)

        def cave_point(
            ring: tuple[Vec2, ...],
            distance: float,
            z_value: float,
            amplitude_factor: float,
            profile_fraction: float,
        ) -> Vec3:
            base = ring_point(ring, distance)
            window = math.sin(math.pi * max(0.0, min(1.0, distance / edge_length))) ** 2
            amplitude = maximum_depth * float(amplitude_factor)
            varied = _shadowlands_depth(
                edge_index,
                distance,
                base=amplitude,
                amplitude=amplitude * 0.72,
                channel=11.0 + profile_fraction * 6.0,
            ) - amplitude
            return (
                base[0] + nx * varied * window,
                base[1] + ny * varied * window,
                floor_z + z_value,
            )

        for band_index in range(len(profile_levels) - 1):
            z0f, d0f, a0f, role = profile_levels[band_index]
            z1f, d1f, a1f, _next_role = profile_levels[band_index + 1]
            strip_breaks = [0.0, 0.5, 1.0]
            for opening in openings:
                radius = min(float(opening.width) * 0.5, max(0.18, float(opening.height) * 0.48))
                for split_z in (
                    float(opening.bottom),
                    max(float(opening.bottom), float(opening.bottom) + float(opening.height) - radius),
                    float(opening.bottom) + float(opening.height),
                ):
                    normalized = (split_z / height - z0f) / max(1.0e-8, z1f - z0f)
                    if 1.0e-7 < normalized < 1.0 - 1.0e-7:
                        strip_breaks.append(normalized)
            strip_breaks = sorted(set(strip_breaks))
            for strip_index, (lower_fraction, upper_fraction) in enumerate(zip(strip_breaks, strip_breaks[1:]), 1):
                lower_zf = z0f + (z1f - z0f) * lower_fraction
                upper_zf = z0f + (z1f - z0f) * upper_fraction
                lower_df = d0f + (d1f - d0f) * lower_fraction
                upper_df = d0f + (d1f - d0f) * upper_fraction
                lower_af = a0f + (a1f - a0f) * lower_fraction
                upper_af = a0f + (a1f - a0f) * upper_fraction
                z0 = height * lower_zf
                z1 = height * upper_zf
                lower_visible = _shadowlands_visible_intervals(edge_length, openings, z_value=z0 + 1.0e-5)
                upper_visible = _shadowlands_visible_intervals(edge_length, openings, z_value=z1 - 1.0e-5)
                for fragment_index, (bottom_span, top_span) in enumerate(zip(lower_visible, upper_visible), 1):
                    subdivisions = max(
                        1,
                        int(
                            math.ceil(
                                max(bottom_span[1] - bottom_span[0], top_span[1] - top_span[0]) / 2.35
                            )
                        ),
                    )
                    for segment_index in range(subdivisions):
                        first = float(segment_index) / float(subdivisions)
                        second = float(segment_index + 1) / float(subdivisions)
                        b0 = bottom_span[0] + (bottom_span[1] - bottom_span[0]) * first
                        b1 = bottom_span[0] + (bottom_span[1] - bottom_span[0]) * second
                        t0 = top_span[0] + (top_span[1] - top_span[0]) * first
                        t1 = top_span[0] + (top_span[1] - top_span[0]) * second
                        meshes.append(
                            _faceted_quad_surface_mesh(
                                name=(
                                    f"{room_resref}_korriban_cave_e{edge_index + 1:02d}_"
                                    f"{role}_{band_index + 1:02d}_{strip_index:02d}_{fragment_index:02d}_{segment_index + 1:02d}"
                                ),
                                # Reverse the ordinary exterior-wall winding so
                                # the faceted normals face into the cave.
                                corners=(
                                    cave_point(profile_ring(lower_df), b0, z0, lower_af, lower_zf),
                                    cave_point(profile_ring(upper_df), t0, z1, upper_af, upper_zf),
                                    cave_point(profile_ring(upper_df), t1, z1, upper_af, upper_zf),
                                    cave_point(profile_ring(lower_df), b1, z0, lower_af, lower_zf),
                                ),
                                material=cliff_material,
                                metadata={
                                    **common,
                                    "edge_index": edge_index,
                                    "architecture_role": role,
                                    "surface_role": "cave_wall",
                                    "contour_band": band_index,
                                    "vertical_strip": strip_index,
                                    "cave_segment": segment_index,
                                    "rounded_opening_profile": bool(openings),
                                },
                                terrain_uv_scale=0.30,
                            )
                        )

        for opening in openings:
            meshes.extend(
                _shadowlands_connected_cave_connector_meshes(
                    room_resref=room_resref,
                    edge_index=edge_index,
                    start=start,
                    tangent=(tx, ty),
                    inward_normal=(nx, ny),
                    edge_length=edge_length,
                    opening=opening,
                    floor_z=floor_z,
                    berm_width=maximum_depth,
                    material=cliff_material,
                    common=common,
                    architecture_role="korriban_cave_connector",
                    source_modules=("710kor",) if is_k2 else ("m34aa",),
                )
            )

    if primitive.include_ceiling:
        crown_ring = profile_ring(1.0)
        center_x = sum(point[0] for point in crown_ring) / len(crown_ring)
        center_y = sum(point[1] for point in crown_ring) / len(crown_ring)
        for edge_index, first in enumerate(crown_ring):
            second = crown_ring[(edge_index + 1) % len(crown_ring)]
            center_rise = 0.16 + 0.10 * math.sin((edge_index + 1) * 1.713)
            meshes.append(
                _faceted_triangle_surface_mesh(
                    name=f"{room_resref}_korriban_cave_crown_{edge_index + 1:02d}",
                    corners=(
                        (first[0], first[1], floor_z + height),
                        (center_x, center_y, floor_z + height + center_rise),
                        (second[0], second[1], floor_z + height),
                    ),
                    material=ceiling_material,
                    metadata={
                        **common,
                        "architecture_role": "faceted_cave_ceiling",
                        "surface_role": "cave_ceiling",
                        "ceiling_facet": edge_index,
                    },
                    terrain_uv_scale=0.30,
                )
            )
    return tuple(meshes)


def build_floor_plan_architecture_meshes(primitive: FloorPlanRoomPrimitive) -> tuple[PrimitiveMesh, ...]:
    """Dress a footprint with a measured vanilla architecture profile.

    Unlike the old palette-only styles, these profiles change the silhouette:
    wall bays are recessed, structural ribs project into the room, Endar Spire
    walls meet the ceiling through an angled cove, and Taris apartment walls
    receive their characteristic framed panels, skirting, and utility lights.
    The result remains ordinary Odyssey triangle meshes and exports through the
    same MDL/MDX/WOK path as other authored geometry.
    """

    profile = str(primitive.metadata.get("architecture_profile", "") or "").strip().lower()
    if profile not in {
        "endar_spire",
        "harbinger",
        "taris_apartments",
        "shadowlands",
        "korriban_tombs",
        "korriban_tombs_k2",
        "korriban_caves_k1",
        "korriban_caves_k2",
    } or not primitive.include_walls:
        return ()
    if profile == "shadowlands":
        return build_floor_plan_shadowlands_meshes(primitive)
    if profile in {"korriban_caves_k1", "korriban_caves_k2"}:
        return build_floor_plan_korriban_cave_meshes(primitive)
    if profile in {"korriban_tombs", "korriban_tombs_k2"}:
        return build_floor_plan_profiled_shell_meshes(primitive)
    height = float(primitive.wall_height)
    if height < 1.8:
        return ()
    points = _ccw_points(_normalise_points(primitive.points))
    room_resref = _normalise_resref(primitive.room_resref)
    floor_z = float(primitive.z)
    accents = tuple(
        str(value or "").strip().lower()
        for value in tuple(primitive.metadata.get("architecture_accent_textures") or ())
        if str(value or "").strip()
    )
    if profile == "endar_spire":
        defaults = ("lhr_red02", "lhr_trim01", "lhr_lit01", "lhr_wall06")
        bay_target = 2.55
    elif profile == "harbinger":
        defaults = ("har_wl01", "har_tr02", "har_lt01", "har_wl09")
        bay_target = 2.55
    else:
        defaults = ("lts_pwall04", "lts_trim01", "lts_lite08", "lts_gwall01")
        bay_target = 2.40
    textures = tuple((accents + defaults)[:4])
    if len(textures) < 4:
        textures = defaults
    accent_material = _architecture_material(textures[0])
    trim_material = _architecture_material(textures[1])
    light_material = _architecture_material(textures[2], luminous=True)
    utility_material = _architecture_material(textures[3])
    wall_material = primitive.wall_material or primitive.material
    ceiling_material = primitive.ceiling_material or wall_material
    shell_profile = architecture_shell_profile(primitive)
    meshes: list[PrimitiveMesh] = list(build_floor_plan_profiled_shell_meshes(primitive))
    openings_by_edge: dict[int, tuple[FloorPlanWallOpening, ...]] = {
        edge_index: tuple(opening for opening in primitive.openings if int(opening.edge_index) == edge_index)
        for edge_index in range(len(points))
    }

    for edge_index, start in enumerate(points):
        end = points[(edge_index + 1) % len(points)]
        edge_length = _edge_length(start, end)
        if edge_length <= 0.05:
            continue
        openings = openings_by_edge.get(edge_index, ())
        bay_count = max(1, int(math.ceil(edge_length / bay_target)))
        bay_width = edge_length / bay_count
        common = {
            "primitive": "floor_plan_architecture",
            "architecture_profile": profile,
            "edge_index": edge_index,
            "source_module": str(primitive.metadata.get("style_source_module", "") or ""),
            "source_rooms": tuple(primitive.metadata.get("architecture_evidence_rooms") or ()),
        }

        # Continuous base and head bands make every arbitrary footprint read as
        # one designed kit rather than unrelated textured rectangles.
        for role, z0, z1, depth, material in (
            ("skirting", 0.06, 0.30, 0.075, utility_material),
            ("cornice", height - 0.30, height - 0.08, 0.085, trim_material),
        ):
            visible = _architecture_visible_intervals(edge_length, openings, z0=z0, z1=z1)
            for ordinal, span in enumerate(visible, 1):
                meshes.append(
                    _architecture_wall_mesh(
                        name=f"{room_resref}_{profile}_e{edge_index + 1:02d}_{role}_{ordinal:02d}",
                        start=start,
                        end=end,
                        span_bottom=span,
                        span_top=None,
                        depth_bottom=depth,
                        depth_top=depth,
                        z_bottom=floor_z + z0,
                        z_top=floor_z + z1,
                        material=material,
                        metadata={**common, "architecture_role": role},
                    )
                )

        if profile in {"endar_spire", "harbinger"} and shell_profile not in {
            "endar_corridor",
            "harbinger_corridor",
        }:
            # The retail LHR rooms use a faceted upper shell rather than a
            # ninety-degree wall/ceiling seam.  This sloped cove is the key
            # silhouette cue visible in the Endar Spire corridors.
            cove_bottom = max(1.25, height - 0.78)
            visible = _architecture_visible_intervals(edge_length, openings, z0=cove_bottom, z1=height - 0.04)
            for ordinal, span in enumerate(visible, 1):
                meshes.append(
                    _architecture_wall_mesh(
                        name=f"{room_resref}_{profile}_e{edge_index + 1:02d}_cove_{ordinal:02d}",
                        start=start,
                        end=end,
                        span_bottom=span,
                        span_top=span,
                        depth_bottom=0.035,
                        depth_top=min(0.46, max(0.18, height * 0.14)),
                        z_bottom=floor_z + cove_bottom,
                        z_top=floor_z + height - 0.04,
                        material=ceiling_material,
                        metadata={**common, "architecture_role": "faceted_ceiling_cove"},
                    )
                )

        for bay_index in range(bay_count):
            bay_start = bay_index * bay_width
            bay_end = (bay_index + 1) * bay_width
            margin = min(0.18, bay_width * 0.09)
            bay_span = (bay_start + margin, bay_end - margin)
            if bay_span[1] - bay_span[0] <= 0.08:
                continue
            panel_bottom = 0.34 if profile == "endar_spire" else 0.36
            panel_top = max(panel_bottom + 0.25, height - (0.82 if profile == "endar_spire" else 0.44))
            visible = _architecture_intersections(
                _architecture_visible_intervals(edge_length, openings, z0=panel_bottom, z1=panel_top),
                bay_span,
            )
            for segment_index, span in enumerate(visible, 1):
                meshes.append(
                    _architecture_wall_mesh(
                        name=f"{room_resref}_{profile}_e{edge_index + 1:02d}_bay_{bay_index + 1:02d}_{segment_index:02d}",
                        start=start,
                        end=end,
                        span_bottom=span,
                        span_top=None,
                        depth_bottom=0.028,
                        depth_top=0.028,
                        z_bottom=floor_z + panel_bottom,
                        z_top=floor_z + panel_top,
                        material=utility_material if profile == "endar_spire" else accent_material,
                        metadata={**common, "architecture_role": "wall_bay"},
                    )
                )

            center = (bay_start + bay_end) * 0.5
            if profile == "endar_spire":
                red_span = (max(bay_span[0], center - bay_width * 0.28), min(bay_span[1], center + bay_width * 0.28))
                red_bottom, red_top = 0.62, min(1.52, panel_top - 0.12)
                red_visible = _architecture_intersections(
                    _architecture_visible_intervals(edge_length, openings, z0=red_bottom, z1=red_top),
                    red_span,
                )
                for ordinal, span in enumerate(red_visible, 1):
                    meshes.append(
                        _architecture_wall_mesh(
                            name=f"{room_resref}_{profile}_e{edge_index + 1:02d}_red_{bay_index + 1:02d}_{ordinal:02d}",
                            start=start,
                            end=end,
                            span_bottom=span,
                            span_top=None,
                            depth_bottom=0.065,
                            depth_top=0.065,
                            z_bottom=floor_z + red_bottom,
                            z_top=floor_z + red_top,
                            material=accent_material,
                            metadata={**common, "architecture_role": "red_inset_panel"},
                        )
                    )
                upper_bottom = max(1.52, panel_bottom + 0.45)
                upper_top = max(upper_bottom + 0.12, panel_top - 0.03)
                upper_span = (bay_span[0] + bay_width * 0.08, bay_span[1] - bay_width * 0.08)
                top_span = (upper_span[0] + bay_width * 0.10, upper_span[1] - bay_width * 0.10)
                if top_span[1] > top_span[0] and not any(
                    max(upper_span[0], float(opening.center_fraction) * edge_length - float(opening.width) * 0.5)
                    < min(upper_span[1], float(opening.center_fraction) * edge_length + float(opening.width) * 0.5)
                    and float(opening.bottom) < upper_top
                    and float(opening.bottom) + float(opening.height) > upper_bottom
                    for opening in openings
                ):
                    meshes.append(
                        _architecture_wall_mesh(
                            name=f"{room_resref}_{profile}_e{edge_index + 1:02d}_angled_{bay_index + 1:02d}",
                            start=start,
                            end=end,
                            span_bottom=upper_span,
                            span_top=top_span,
                            depth_bottom=0.055,
                            depth_top=0.072,
                            z_bottom=floor_z + upper_bottom,
                            z_top=floor_z + upper_top,
                            material=wall_material,
                            metadata={**common, "architecture_role": "angled_upper_panel"},
                        )
                    )
                light_bottom = max(0.45, height - 0.64)
                light_top = min(height - 0.34, light_bottom + 0.16)
                light_span = (max(bay_span[0], center - 0.20), min(bay_span[1], center + 0.20))
            else:
                inset_bottom, inset_top = 0.58, max(0.82, panel_top - 0.22)
                inset_span = (bay_span[0] + min(0.16, bay_width * 0.08), bay_span[1] - min(0.16, bay_width * 0.08))
                inset_visible = _architecture_intersections(
                    _architecture_visible_intervals(edge_length, openings, z0=inset_bottom, z1=inset_top),
                    inset_span,
                )
                for ordinal, span in enumerate(inset_visible, 1):
                    meshes.append(
                        _architecture_wall_mesh(
                            name=f"{room_resref}_{profile}_e{edge_index + 1:02d}_recess_{bay_index + 1:02d}_{ordinal:02d}",
                            start=start,
                            end=end,
                            span_bottom=span,
                            span_top=None,
                            depth_bottom=0.052,
                            depth_top=0.052,
                            z_bottom=floor_z + inset_bottom,
                            z_top=floor_z + inset_top,
                            material=wall_material,
                            metadata={**common, "architecture_role": "apartment_recess"},
                        )
                    )
                rail_bottom = min(1.02, panel_top - 0.22)
                rail_top = min(panel_top - 0.06, rail_bottom + 0.11)
                rail_visible = _architecture_intersections(
                    _architecture_visible_intervals(edge_length, openings, z0=rail_bottom, z1=rail_top),
                    bay_span,
                )
                for ordinal, span in enumerate(rail_visible, 1):
                    meshes.append(
                        _architecture_wall_mesh(
                            name=f"{room_resref}_{profile}_e{edge_index + 1:02d}_rail_{bay_index + 1:02d}_{ordinal:02d}",
                            start=start,
                            end=end,
                            span_bottom=span,
                            span_top=None,
                            depth_bottom=0.084,
                            depth_top=0.084,
                            z_bottom=floor_z + rail_bottom,
                            z_top=floor_z + rail_top,
                            material=trim_material,
                            metadata={**common, "architecture_role": "utility_rail"},
                        )
                    )
                light_bottom = max(0.55, height - 0.55)
                light_top = min(height - 0.25, light_bottom + 0.12)
                light_span = (max(bay_span[0], center - 0.24), min(bay_span[1], center + 0.24))

            light_visible = _architecture_intersections(
                _architecture_visible_intervals(edge_length, openings, z0=light_bottom, z1=light_top),
                light_span,
            )
            for ordinal, span in enumerate(light_visible, 1):
                meshes.append(
                    _architecture_wall_mesh(
                        name=f"{room_resref}_{profile}_e{edge_index + 1:02d}_light_{bay_index + 1:02d}_{ordinal:02d}",
                        start=start,
                        end=end,
                        span_bottom=span,
                        span_top=None,
                        depth_bottom=0.105,
                        depth_top=0.105,
                        z_bottom=floor_z + light_bottom,
                        z_top=floor_z + light_top,
                        material=light_material,
                        metadata={**common, "architecture_role": "integrated_light"},
                    )
                )

        meshes.extend(
            _architecture_door_transition_meshes(
                room_resref=room_resref,
                profile=profile,
                edge_index=edge_index,
                start=start,
                end=end,
                edge_length=edge_length,
                floor_z=floor_z,
                wall_height=height,
                openings=openings,
                infill_material=accent_material,
                trim_material=trim_material,
                light_material=light_material,
                common=common,
            )
        )

        # Projected pilasters are the snap rhythm of both kits.  The Endar
        # version continues into the cove, making a readable arch rib.
        if shell_profile:
            continue
        rib_half = 0.055 if profile == "endar_spire" else 0.075
        rib_top = height - (0.72 if profile == "endar_spire" else 0.28)
        for rib_index in range(bay_count + 1):
            center = min(edge_length, rib_index * bay_width)
            rib_span = (max(0.0, center - rib_half), min(edge_length, center + rib_half))
            visible = _architecture_intersections(
                _architecture_visible_intervals(edge_length, openings, z0=0.08, z1=rib_top),
                rib_span,
            )
            for ordinal, span in enumerate(visible, 1):
                meshes.append(
                    _architecture_wall_mesh(
                        name=f"{room_resref}_{profile}_e{edge_index + 1:02d}_rib_{rib_index + 1:02d}_{ordinal:02d}",
                        start=start,
                        end=end,
                        span_bottom=span,
                        span_top=None,
                        depth_bottom=0.125,
                        depth_top=0.125,
                        z_bottom=floor_z + 0.08,
                        z_top=floor_z + rib_top,
                        material=trim_material,
                        metadata={**common, "architecture_role": "structural_rib"},
                    )
                )
            if profile == "endar_spire" and rib_span[1] - rib_span[0] > 0.015:
                meshes.append(
                    _architecture_wall_mesh(
                        name=f"{room_resref}_{profile}_e{edge_index + 1:02d}_arch_{rib_index + 1:02d}",
                        start=start,
                        end=end,
                        span_bottom=rib_span,
                        span_top=rib_span,
                        depth_bottom=0.125,
                        depth_top=min(0.53, max(0.22, height * 0.16)),
                        z_bottom=floor_z + rib_top,
                        z_top=floor_z + height - 0.025,
                        material=trim_material,
                        metadata={**common, "architecture_role": "arched_rib"},
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
    ceiling_texture = str(material.texture or "").strip().lower()
    ceiling_repeat_metres = _VANILLA_ARCHITECTURE_UV_METRES.get(ceiling_texture, 3.0)
    return PrimitiveMesh(
        name=f"{_normalise_resref(primitive.room_resref)}_ceiling",
        vertices=vertices,
        faces=faces,
        normals=((0.0, 0.0, -1.0),) * len(vertices),
        uvs=_mesh_uvs(points, repeat_metres=ceiling_repeat_metres),
        texture=material.texture,
        diffuse=material.diffuse,
        ambient=material.ambient,
        metadata={
            "primitive": "floor_plan_ceiling",
            "source": "map_studio:pascal_building",
            "uv_projection": "world_xy_tiled",
            "uv_repeat_metres": ceiling_repeat_metres,
            "texture_stretching_prevented": True,
            **dict(material.metadata),
        },
    )


def build_floor_plan_roof_meshes(primitive: FloorPlanRoomPrimitive) -> tuple[PrimitiveMesh, ...]:
    """Compile a lightweight exterior roof that remains part of the room.

    Flat roofs support every valid footprint. Gable roofs deliberately require
    an axis-aligned rectangle so the authoring result stays predictable and
    engine-budget safe rather than guessing at arbitrary residential CSG.
    """

    roof_type = _roof_type(primitive)
    if roof_type == "none":
        return ()
    validation = validate_floor_plan_room_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    points = _ccw_points(_normalise_points(primitive.points))
    top_z = float(primitive.z) + float(primitive.wall_height)
    roof_material = primitive.ceiling_material or primitive.wall_material or primitive.material
    metadata = {
        **dict(roof_material.metadata),
        "primitive": "floor_plan_roof",
        "roof_type": roof_type,
        "source": "map_studio:pascal_building",
        "surface_role": "roof",
    }
    room_resref = _normalise_resref(primitive.room_resref)
    meshes: list[PrimitiveMesh] = []
    if roof_type == "flat":
        vertices: tuple[Vec3, ...] = tuple((x, y, top_z) for x, y in points)
        return (
            _planar_surface_mesh(
                name=f"{room_resref}_roof_flat",
                vertices=vertices,
                faces=triangulate_floor_plan_points(points),
                material=roof_material,
                metadata=metadata,
            ),
        )

    if roof_type == "hip":
        center_x = sum(point[0] for point in points) / len(points)
        center_y = sum(point[1] for point in points) / len(points)
        overhang = float(primitive.metadata.get("building_roof_overhang", 0.25) or 0.0)
        expanded: list[Vec2] = []
        distances: list[float] = []
        for x, y in points:
            dx, dy = x - center_x, y - center_y
            distance = math.hypot(dx, dy)
            distances.append(distance)
            scale = (distance + overhang) / max(distance, 1.0e-7)
            expanded.append((center_x + dx * scale, center_y + dy * scale))
        pitch = math.radians(float(primitive.metadata.get("building_roof_pitch_degrees", 30.0) or 30.0))
        rise = max(0.05, (sum(distances) / max(len(distances), 1)) * 0.5 * math.tan(pitch))
        apex = (center_x, center_y, top_z + rise)
        for index, start in enumerate(expanded):
            end = expanded[(index + 1) % len(expanded)]
            meshes.append(
                _planar_surface_mesh(
                    name=f"{room_resref}_roof_hip_{index + 1:02d}",
                    vertices=((start[0], start[1], top_z), (end[0], end[1], top_z), apex),
                    faces=((0, 1, 2),),
                    material=roof_material,
                    metadata={**metadata, "roof_panel": f"hip_{index + 1:02d}"},
                )
            )
        return tuple(meshes)

    bounds = _rect_bounds(points)
    if bounds is None:  # Kept defensive for callers that skip validation.
        raise ValueError("Gable roofs currently require a rectangular room footprint.")
    min_x, min_y, max_x, max_y = bounds
    overhang = float(primitive.metadata.get("building_roof_overhang", 0.25) or 0.0)
    pitch = math.radians(float(primitive.metadata.get("building_roof_pitch_degrees", 30.0) or 30.0))
    width, depth = max_x - min_x, max_y - min_y
    if width >= depth:
        ridge_y = (min_y + max_y) * 0.5
        ridge_z = top_z + max(0.05, depth * 0.5 * math.tan(pitch))
        panels = (
            (
                "south",
                ((min_x - overhang, min_y - overhang, top_z), (max_x + overhang, min_y - overhang, top_z), (max_x + overhang, ridge_y, ridge_z), (min_x - overhang, ridge_y, ridge_z)),
                ((0, 1, 2), (0, 2, 3)),
            ),
            (
                "north",
                ((min_x - overhang, ridge_y, ridge_z), (max_x + overhang, ridge_y, ridge_z), (max_x + overhang, max_y + overhang, top_z), (min_x - overhang, max_y + overhang, top_z)),
                ((0, 1, 2), (0, 2, 3)),
            ),
            ("west_gable", ((min_x, min_y, top_z), (min_x, ridge_y, ridge_z), (min_x, max_y, top_z)), ((0, 1, 2),)),
            ("east_gable", ((max_x, min_y, top_z), (max_x, max_y, top_z), (max_x, ridge_y, ridge_z)), ((0, 1, 2),)),
        )
    else:
        ridge_x = (min_x + max_x) * 0.5
        ridge_z = top_z + max(0.05, width * 0.5 * math.tan(pitch))
        panels = (
            (
                "west",
                ((min_x - overhang, min_y - overhang, top_z), (ridge_x, min_y - overhang, ridge_z), (ridge_x, max_y + overhang, ridge_z), (min_x - overhang, max_y + overhang, top_z)),
                ((0, 1, 2), (0, 2, 3)),
            ),
            (
                "east",
                ((ridge_x, min_y - overhang, ridge_z), (max_x + overhang, min_y - overhang, top_z), (max_x + overhang, max_y + overhang, top_z), (ridge_x, max_y + overhang, ridge_z)),
                ((0, 1, 2), (0, 2, 3)),
            ),
            ("south_gable", ((min_x, min_y, top_z), (max_x, min_y, top_z), (ridge_x, min_y, ridge_z)), ((0, 1, 2),)),
            ("north_gable", ((min_x, max_y, top_z), (ridge_x, max_y, ridge_z), (max_x, max_y, top_z)), ((0, 1, 2),)),
        )
    for label, vertices, faces in panels:
        meshes.append(
            _planar_surface_mesh(
                name=f"{room_resref}_roof_{label}",
                vertices=vertices,
                faces=faces,
                material=roof_material if "gable" not in label else (primitive.wall_material or roof_material),
                metadata={**metadata, "roof_panel": label},
            )
        )
    return tuple(meshes)


def compile_floor_plan_room_geometry(primitive: FloorPlanRoomPrimitive) -> AuthoredRoomGeometry:
    """Compile a floor-plan room into render/export meshes plus WOK."""

    validation = validate_floor_plan_room_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    floor_mesh = build_floor_plan_floor_mesh(primitive)
    shell_profile = architecture_shell_profile(primitive)
    wall_meshes = () if shell_profile else build_floor_plan_wall_meshes(primitive)
    architecture_meshes = build_floor_plan_architecture_meshes(primitive)
    helper_meshes = wall_meshes + architecture_meshes
    ceiling = None if shell_profile else build_floor_plan_ceiling_mesh(primitive)
    if ceiling is not None:
        helper_meshes = helper_meshes + (ceiling,)
    roof_meshes = build_floor_plan_roof_meshes(primitive)
    helper_meshes = helper_meshes + roof_meshes
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
            "architecture_profile": str(primitive.metadata.get("architecture_profile", "") or ""),
            "architecture_shell_profile": shell_profile,
            "architecture_mesh_count": len(architecture_meshes),
            "opening_count": len(primitive.openings),
            "has_ceiling": bool(
                primitive.include_ceiling
                and (
                    ceiling is not None
                    or shell_profile
                    in {
                        "endar_corridor",
                        "harbinger_corridor",
                        "taris_apartment",
                        "korriban_tomb",
                        "korriban_tomb_chamber",
                        "korriban_tomb_junction",
                        "korriban_tomb_burial",
                        "korriban_tomb_monumental",
                        "korriban_tomb_ruined",
                        "korriban_cave",
                    }
                )
            ),
            "has_roof": bool(roof_meshes),
            "roof_type": _roof_type(primitive),
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
    "build_floor_plan_architecture_meshes",
    "build_floor_plan_korriban_cave_meshes",
    "build_floor_plan_roof_meshes",
    "build_floor_plan_shadowlands_meshes",
    "build_floor_plan_wall_meshes",
    "build_floor_plan_wok",
    "compile_floor_plan_room_geometry",
    "extrude_floor_plan_edge_points",
    "inset_floor_plan_points",
    "triangulate_floor_plan_points",
    "polygon_signed_area",
    "validate_floor_plan_room_primitive",
]
