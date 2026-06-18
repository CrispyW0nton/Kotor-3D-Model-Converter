"""Authored floor-plan extrusion primitives for Map Studio.

This module is the headless contract for drawing a room footprint and turning
it into exportable room geometry.  The first pass intentionally supports
convex floor plans: that gives Map Studio a deterministic primitive for simple
rooms now, while leaving concave decomposition and boolean tools as explicit
future operations instead of hidden guesses.
"""

from __future__ import annotations

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
    include_walls: bool = True
    openings: tuple[FloorPlanWallOpening, ...] = ()
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


def _mesh_uvs(points: tuple[Vec2, ...]) -> tuple[Vec2, ...]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x = min(xs)
    min_y = min(ys)
    width = max(max(xs) - min_x, 1.0e-7)
    depth = max(max(ys) - min_y, 1.0e-7)
    return tuple(((x - min_x) / width, (y - min_y) / depth) for x, y in points)


def _edge_length(a: Vec2, b: Vec2) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return (dx * dx + dy * dy) ** 0.5


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
    if points and not _is_convex(points):
        blocking.append("Floor-plan room currently supports convex footprints only; split concave rooms into multiple primitives.")
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


def build_floor_plan_floor_mesh(primitive: FloorPlanRoomPrimitive) -> PrimitiveMesh:
    """Build a triangulated floor mesh from a convex floor-plan footprint."""

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
        faces=_fan_faces(len(points)),
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
    faces: list[WOKFace] = []
    triangle_count = len(points) - 2
    for index in range(triangle_count):
        prev_adj = index - 1 if index > 0 else -1
        next_adj = index + 1 if index < triangle_count - 1 else -1
        faces.append(WOKFace(0, index + 1, index + 2, surface=surface_id, adj1=prev_adj, adj2=-1, adj3=next_adj))
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
                    material=primitive.material,
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
                    material=primitive.material,
                    metadata={**opening_metadata, "wall_panel": "opening_left"},
                )
            )
        if float(opening.bottom) > 1.0e-7:
            meshes.append(
                _quad_mesh(
                    name=f"{room_resref}_wall_{index + 1:02d}_sill",
                    vertices=((start[0], start[1], z), (end[0], end[1], z), (end[0], end[1], opening_bottom), (start[0], start[1], opening_bottom)),
                    material=primitive.material,
                    metadata={**opening_metadata, "wall_panel": "opening_sill"},
                )
            )
        meshes.append(
            _quad_mesh(
                name=f"{room_resref}_wall_{index + 1:02d}_lintel",
                vertices=((start[0], start[1], opening_top), (end[0], end[1], opening_top), (end[0], end[1], top_z), (start[0], start[1], top_z)),
                material=primitive.material,
                metadata={**opening_metadata, "wall_panel": "opening_lintel"},
            )
        )
        if end_fraction < 1.0 - 1.0e-7:
            meshes.append(
                _quad_mesh(
                    name=f"{room_resref}_wall_{index + 1:02d}_right",
                    vertices=((end[0], end[1], z), (x1, y1, z), (x1, y1, top_z), (end[0], end[1], top_z)),
                    material=primitive.material,
                    metadata={**opening_metadata, "wall_panel": "opening_right"},
                )
            )
    return tuple(meshes)


def compile_floor_plan_room_geometry(primitive: FloorPlanRoomPrimitive) -> AuthoredRoomGeometry:
    """Compile a floor-plan room into render/export meshes plus WOK."""

    validation = validate_floor_plan_room_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    floor_mesh = build_floor_plan_floor_mesh(primitive)
    helper_meshes = build_floor_plan_wall_meshes(primitive)
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
            "wall_count": len(helper_meshes),
            "opening_count": len(primitive.openings),
            "polygon_area": validation.area,
            "floor_surface_id": surface_id,
            "floor_surface_name": walkmesh_surface_name(surface_id),
            "warnings": list(validation.warnings),
        },
    )


__all__ = [
    "FloorPlanRoomPrimitive",
    "FloorPlanRoomValidation",
    "FloorPlanWallOpening",
    "build_floor_plan_floor_mesh",
    "build_floor_plan_wall_meshes",
    "build_floor_plan_wok",
    "compile_floor_plan_room_geometry",
    "polygon_signed_area",
    "validate_floor_plan_room_primitive",
]
