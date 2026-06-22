"""Project-level room shaping operations for Map Studio.

The low-level floor-plan module owns polygon math.  This module owns the
authored-module operation policy: find a room in an ``AuthoredModuleProject``,
convert compatible starter primitives to floor-plan intent, apply the operation,
and return a new project that can be saved back into KMAP.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from src.core.geometry.component_editing import (
    ComponentEditAudit,
    ComponentEditResult,
    audit_component_edit_result,
    bridge_edges,
    cleanup_face_normals,
    component_mesh,
    fill_face,
    flatten_vertices,
    mirror_vertices,
    split_face_with_edge,
    snap_vertex_to_vertex,
    snap_vertices_to_grid,
    transform_snap_vertices_to_level,
    triangulate_faces,
    weld_vertices,
)

from .authored_module_project import AuthoredModuleProject, AuthoredRoomSpec, authored_resref_blocking_issue, normalise_resref
from .authored_module_objects import AuthoredGameplayPlacement
from .authored_module_placements import add_authored_gameplay_placement, update_authored_gameplay_transition
from .authored_room_composition import AuthoredRoomComposition, PlacedRoomPrimitive, PrimitiveTransform, primitive_to_mesh
from .authored_room_floorplan import (
    FloorPlanAxisSplitOperation,
    FloorPlanBevelOperation,
    FloorPlanEdgeExtrudeOperation,
    FloorPlanInsetOperation,
    FloorPlanRectangularCutOperation,
    FloorPlanRectangularUnionOperation,
    FloorPlanRoomPrimitive,
    FloorPlanWallOpening,
    apply_floor_plan_axis_split,
    apply_floor_plan_bevel,
    apply_floor_plan_edge_extrude,
    apply_floor_plan_inset,
    apply_floor_plan_rectangular_cut,
    apply_floor_plan_rectangular_union,
    polygon_signed_area,
    validate_floor_plan_room_primitive,
)
from .authored_room_geometry import RectangularRoomPrimitive
from .authored_room_materials import compile_authored_room_material_preflight
from .authored_terrain_builder import (
    TerrainHeightfieldPrimitive,
    analyse_terrain_slopes,
    apply_terrain_brush_stroke,
    apply_terrain_shape_preset,
    bend_terrain_heightfield,
    flatten_terrain_heightfield,
    lattice_terrain_heightfield,
    mirror_terrain_heightfield_z,
    offset_terrain_heightfield_samples,
    sample_terrain_height,
    set_terrain_heightfield_sample,
    smooth_terrain_heightfield,
    terrain_height_range,
)
from .authored_room_primitives import (
    ArchPrimitive,
    CubePrimitive,
    CylinderPrimitive,
    DoorFramePrimitive,
    FloorPrimitive,
    RampPrimitive,
    StairsPrimitive,
    WallPrimitive,
    PrimitiveMaterial,
)
from .authored_walkmesh_surfaces import resolve_walkmesh_surface_id, walkmesh_surface_name


@dataclass(frozen=True)
class AuthoredCompositionPrimitiveTransform:
    """UI-ready transform row for one primitive in an authored room composition."""

    room_resref: str
    primitive_name: str
    primitive_type: str
    translation: tuple[float, float, float]
    rotation_degrees_z: float
    scale: tuple[float, float, float]
    pivot: tuple[float, float, float]
    texture: str = ""
    surface_id: int | None = None
    surface_name: str = ""
    supports_walkmesh_surface: bool = False
    dimensions: tuple["AuthoredCompositionPrimitiveDimension", ...] = ()


@dataclass(frozen=True)
class AuthoredUniversalTransformSelection:
    """Exact selected-primitive bounds for the Map Studio Universal Manipulator."""

    room_resref: str
    primitive_name: str
    primitive_type: str
    coordinate_space: str
    bounds_min: tuple[float, float, float]
    bounds_max: tuple[float, float, float]
    center: tuple[float, float, float]
    dimensions: tuple[float, float, float]
    translation: tuple[float, float, float]
    rotation_degrees_z: float
    scale: tuple[float, float, float]
    pivot: tuple[float, float, float]
    vertex_count: int
    face_count: int
    texture: str = ""
    surface_id: int | None = None
    surface_name: str = ""
    committed_edit_stale_outputs: tuple[str, ...] = ("MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod")
    readiness_impact: str = (
        "Committing transform or dimension edits invalidates Map Studio validation, export, install handoff, and game proof."
    )
    metadata: dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


@dataclass(frozen=True)
class AuthoredCompositionPrimitiveDimension:
    """UI-ready editable dimension for one authored composition primitive."""

    key: str
    label: str
    value: float
    minimum: float = 0.001
    maximum: float = 1000.0
    step: float = 0.1
    suffix: str = " m"
    integer: bool = False


@dataclass(frozen=True)
class AuthoredCompositionPrimitiveKind:
    """UI-ready palette entry for adding one primitive to a composition room."""

    kind: str
    label: str
    description: str
    creates_walkmesh: bool = False


@dataclass(frozen=True)
class AuthoredFloorPlanRoomChoice:
    """UI-ready floor-plan room choice for room-shaping operations."""

    room_resref: str
    label: str
    point_count: int
    room_index: int
    z: float = 0.0
    wall_height: float = 3.0
    include_walls: bool = True
    floor_surface_id: int | str = 4
    floor_surface_name: str = ""
    opening_count: int = 0
    opening_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuthoredFloorPlanVertexSnapCandidate:
    """UI-ready candidate for Maya-style vertex snapping in Map Studio."""

    room_resref: str
    point_index: int
    world_position: tuple[float, float, float]
    distance: float
    same_room: bool
    label: str


@dataclass(frozen=True)
class AuthoredPrimitiveVertexSnapCandidate:
    """UI-ready target for object-level primitive vertex snapping."""

    room_resref: str
    primitive_name: str
    vertex_index: int
    composition_position: tuple[float, float, float]
    distance: float
    label: str


@dataclass(frozen=True)
class AuthoredTerrainRoomChoice:
    """UI-ready terrain room choice for heightfield sculpt operations."""

    room_resref: str
    label: str
    row_count: int
    column_count: int
    min_height: float
    max_height: float
    max_slope_degrees: float
    walkable_triangle_count: int
    non_walk_triangle_count: int
    room_index: int
    warnings: tuple[str, ...] = ()


_COMPOSITION_PRIMITIVE_KINDS: tuple[AuthoredCompositionPrimitiveKind, ...] = (
    AuthoredCompositionPrimitiveKind("plane", "Plane", "A flat walkable floor/platform patch that contributes WOK faces.", creates_walkmesh=True),
    AuthoredCompositionPrimitiveKind("wall", "Wall", "A rectangular wall/blockout slab."),
    AuthoredCompositionPrimitiveKind("cube", "Cube", "A simple box primitive for room dressing or massing."),
    AuthoredCompositionPrimitiveKind("ramp", "Ramp", "A sloped walkable ramp that contributes WOK faces.", creates_walkmesh=True),
    AuthoredCompositionPrimitiveKind("stairs", "Stairs", "A visual staircase with a walkable ramp-style WOK proxy.", creates_walkmesh=True),
    AuthoredCompositionPrimitiveKind("cylinder", "Cylinder", "A round column or pedestal primitive."),
    AuthoredCompositionPrimitiveKind("door_frame", "Door Frame", "A rectangular doorway frame primitive for transition and portal blockout."),
    AuthoredCompositionPrimitiveKind("arch", "Arch", "A curved arch primitive for room entrances and visual portal silhouettes."),
)


def available_authored_composition_primitive_kinds() -> tuple[AuthoredCompositionPrimitiveKind, ...]:
    """Return primitive kinds the Builder can add to a composition room."""

    return _COMPOSITION_PRIMITIVE_KINDS


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


def _terrain_for_room(room: AuthoredRoomSpec) -> TerrainHeightfieldPrimitive:
    primitive = room.primitive
    if isinstance(primitive, TerrainHeightfieldPrimitive):
        return primitive
    raise ValueError(f"Room {room.room_resref} does not have an editable terrain heightfield.")


def authored_floor_plan_room_choices(project: AuthoredModuleProject) -> tuple[AuthoredFloorPlanRoomChoice, ...]:
    """Return floor-plan-compatible authored rooms for Builder operations."""

    choices: list[AuthoredFloorPlanRoomChoice] = []
    for index, room in enumerate(tuple(project.rooms or ())):
        try:
            primitive = _floor_plan_for_room(room)
        except ValueError:
            continue
        resref = normalise_resref(room.room_resref)
        if not resref:
            continue
        floor_surface_id = primitive.floor_surface_id
        try:
            floor_surface_name = walkmesh_surface_name(resolve_walkmesh_surface_id(floor_surface_id))
        except Exception:
            floor_surface_name = str(floor_surface_id or "")
        choices.append(
            AuthoredFloorPlanRoomChoice(
                room_resref=resref,
                label=f"{resref} ({len(tuple(primitive.points or ()))} points, {float(primitive.wall_height):.2f} m walls)",
                point_count=len(tuple(primitive.points or ())),
                room_index=index,
                z=float(primitive.z),
                wall_height=float(primitive.wall_height),
                include_walls=bool(primitive.include_walls),
                floor_surface_id=floor_surface_id,
                floor_surface_name=floor_surface_name,
                opening_count=len(tuple(primitive.openings or ())),
                opening_names=tuple(str(opening.name or "").strip() for opening in tuple(primitive.openings or ()) if str(opening.name or "").strip()),
            )
        )
    return tuple(choices)


def authored_terrain_room_choices(project: AuthoredModuleProject) -> tuple[AuthoredTerrainRoomChoice, ...]:
    """Return authored terrain rooms for Builder heightfield operations."""

    choices: list[AuthoredTerrainRoomChoice] = []
    for index, room in enumerate(tuple(project.rooms or ())):
        try:
            primitive = _terrain_for_room(room)
        except ValueError:
            continue
        resref = normalise_resref(room.room_resref)
        if not resref:
            continue
        rows = tuple(tuple(item) for item in primitive.heights or ())
        row_count = len(rows)
        column_count = len(rows[0]) if rows else 0
        min_height, max_height = terrain_height_range(primitive)
        report = analyse_terrain_slopes(primitive)
        choices.append(
            AuthoredTerrainRoomChoice(
                room_resref=resref,
                label=(
                    f"{resref} ({row_count}x{column_count}, {min_height:.2f}..{max_height:.2f} m, "
                    f"{report.walkable_triangle_count} walk / {report.non_walk_triangle_count} blocked)"
                ),
                row_count=row_count,
                column_count=column_count,
                min_height=float(min_height),
                max_height=float(max_height),
                max_slope_degrees=float(report.max_slope_degrees),
                walkable_triangle_count=int(report.walkable_triangle_count),
                non_walk_triangle_count=int(report.non_walk_triangle_count),
                warnings=tuple(report.warnings),
                room_index=index,
            )
        )
    return tuple(choices)


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


def _room_offset(room: AuthoredRoomSpec) -> tuple[float, float, float]:
    offset = tuple(room.position or (0.0, 0.0, 0.0))
    if len(offset) < 3:
        return (0.0, 0.0, 0.0)
    return (float(offset[0]), float(offset[1]), float(offset[2]))


def _floor_plan_component_mesh(primitive: FloorPlanRoomPrimitive):
    return component_mesh(
        ((float(x), float(y), float(primitive.z)) for x, y in tuple(primitive.points or ())),
        metadata={"room_resref": normalise_resref(primitive.room_resref), "source": "floor_plan"},
    )


def _floor_plan_point_world_position(
    room: AuthoredRoomSpec,
    primitive: FloorPlanRoomPrimitive,
    point: tuple[float, float],
) -> tuple[float, float, float]:
    offset = _room_offset(room)
    x, y = point
    return (float(x) + offset[0], float(y) + offset[1], float(primitive.z) + offset[2])


def _floor_plan_component_mesh_with_face(primitive: FloorPlanRoomPrimitive):
    points = tuple(primitive.points or ())
    return component_mesh(
        ((float(x), float(y), float(primitive.z)) for x, y in points),
        (tuple(range(len(points))),) if len(points) >= 3 else (),
        metadata={"room_resref": normalise_resref(primitive.room_resref), "source": "floor_plan"},
    )


def _floor_plan_points_from_component_vertices(vertices: tuple[tuple[float, float, float], ...]) -> tuple[tuple[float, float], ...]:
    return tuple((float(vertex[0]), float(vertex[1])) for vertex in vertices)


def _component_edit_audit_payload(audit: ComponentEditAudit) -> dict[str, Any]:
    return {
        "operation": audit.operation,
        "component_kind": audit.component_kind,
        "geometry_changed": audit.geometry_changed,
        "topology_changed": audit.topology_changed,
        "walkmesh_review_required": audit.walkmesh_review_required,
        "export_candidate_stale": audit.export_candidate_stale,
        "game_proof_stale": audit.game_proof_stale,
        "stale_outputs": list(audit.stale_outputs),
        "next_action": audit.next_action,
        "summary": audit.summary,
        "validation_messages": list(audit.validation_messages),
        "metadata": dict(audit.metadata),
    }


def _points_close(a: tuple[float, float], b: tuple[float, float], tolerance: float) -> bool:
    dx = float(a[0]) - float(b[0])
    dy = float(a[1]) - float(b[1])
    return (dx * dx + dy * dy) <= (float(tolerance) * float(tolerance))


def _is_collinear_point(
    previous: tuple[float, float],
    current: tuple[float, float],
    next_point: tuple[float, float],
    tolerance: float,
) -> bool:
    abx = float(current[0]) - float(previous[0])
    aby = float(current[1]) - float(previous[1])
    bcx = float(next_point[0]) - float(current[0])
    bcy = float(next_point[1]) - float(current[1])
    cross = abs((abx * bcy) - (aby * bcx))
    scale = max((abx * abx + aby * aby) ** 0.5, (bcx * bcx + bcy * bcy) ** 0.5, 1.0)
    return cross <= float(tolerance) * scale


def _clean_floor_plan_points(
    points: tuple[tuple[float, float], ...],
    *,
    tolerance: float,
) -> tuple[tuple[float, float], ...]:
    cleaned: list[tuple[float, float]] = []
    for point in tuple(points or ()):
        normalized = (float(point[0]), float(point[1]))
        if cleaned and _points_close(cleaned[-1], normalized, tolerance):
            continue
        cleaned.append(normalized)
    if len(cleaned) > 1 and _points_close(cleaned[0], cleaned[-1], tolerance):
        cleaned.pop()
    changed = True
    while changed and len(cleaned) >= 3:
        changed = False
        next_points: list[tuple[float, float]] = []
        count = len(cleaned)
        for index, point in enumerate(cleaned):
            previous = cleaned[index - 1]
            next_point = cleaned[(index + 1) % count]
            if _is_collinear_point(previous, point, next_point, tolerance):
                changed = True
                continue
            next_points.append(point)
        cleaned = next_points
    return tuple(cleaned)


def _preserve_floor_plan_winding(
    original_points: tuple[tuple[float, float], ...],
    updated_points: tuple[tuple[float, float], ...],
) -> tuple[tuple[float, float], ...]:
    if len(original_points) < 3 or len(updated_points) < 3:
        return updated_points
    original_area = polygon_signed_area(original_points)
    updated_area = polygon_signed_area(updated_points)
    if original_area and updated_area and ((original_area > 0.0) != (updated_area > 0.0)):
        return tuple(reversed(updated_points))
    return updated_points


def _validated_floor_plan_primitive(primitive: FloorPlanRoomPrimitive, *, operation: str) -> FloorPlanRoomPrimitive:
    report = validate_floor_plan_room_primitive(primitive)
    if report.blocking_issues:
        joined = " ".join(str(issue) for issue in report.blocking_issues)
        raise ValueError(f"Map Studio {operation} would create invalid floor-plan geometry. {joined}")
    return primitive


def _replace_floor_plan_room(
    project: AuthoredModuleProject,
    room_index: int,
    primitive: FloorPlanRoomPrimitive,
    *,
    operation: str,
    room_metadata: dict[str, Any] | None = None,
) -> AuthoredModuleProject:
    room = project.rooms[room_index]
    updated_room = replace(
        room,
        primitive=_validated_floor_plan_primitive(primitive, operation=operation),
        composition=None,
        metadata={
            **dict(room.metadata),
            "primitive": "floor_plan_extrusion",
            "last_operation": operation,
            **dict(room_metadata or {}),
        },
    )
    rooms = tuple(project.rooms[:room_index] + (updated_room,) + project.rooms[room_index + 1 :])
    return _replace_rooms(project, rooms, operation=operation)


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


def _primitive_transform(primitive: Any) -> PrimitiveTransform:
    return primitive.transform if isinstance(primitive, PlacedRoomPrimitive) else PrimitiveTransform()


def _primitive_type(primitive: Any) -> str:
    base = primitive.primitive if isinstance(primitive, PlacedRoomPrimitive) else primitive
    if isinstance(base, FloorPrimitive):
        return "plane"
    if isinstance(base, DoorFramePrimitive):
        return "door_frame"
    name = type(base).__name__
    return name[:-9].lower() if name.endswith("Primitive") else name.lower()


def _base_primitive(primitive: Any) -> Any:
    return primitive.primitive if isinstance(primitive, PlacedRoomPrimitive) else primitive


def _edge_index_values(edge_indices: Any) -> list[int]:
    if edge_indices is None:
        return []
    if isinstance(edge_indices, (str, bytes)):
        text = edge_indices.decode("utf-8", errors="ignore") if isinstance(edge_indices, bytes) else edge_indices
        values = [part.strip() for part in text.split(",") if part.strip()]
        return [int(value) for value in values]
    try:
        return [int(index) for index in tuple(edge_indices)]
    except TypeError:
        return [int(edge_indices)]


def _primitive_mesh_edge_count(primitive: Any) -> int:
    mesh = primitive_to_mesh(primitive)
    edges: set[tuple[int, int]] = set()
    for face in tuple(mesh.faces or ()):
        indices = tuple(int(index) for index in face)
        if len(indices) < 2:
            continue
        for left, right in zip(indices, indices[1:] + indices[:1]):
            edge = (left, right) if left <= right else (right, left)
            edges.add(edge)
    return len(edges)


def _validate_edge_indices(indices: list[int], *, edge_count: int, label: str) -> None:
    if not indices:
        return
    if edge_count <= 0:
        raise ValueError(f"{label} has no editable edges.")
    invalid = [index for index in indices if index < 0 or index >= edge_count]
    if invalid:
        high = edge_count - 1
        raise ValueError(
            f"Selected edge index {invalid[0]} is outside {label}'s editable edge range 0..{high}."
        )


def _dimension(
    key: str,
    label: str,
    value: Any,
    *,
    minimum: float = 0.001,
    maximum: float = 1000.0,
    step: float = 0.1,
    suffix: str = " m",
    integer: bool = False,
) -> AuthoredCompositionPrimitiveDimension:
    return AuthoredCompositionPrimitiveDimension(
        key=key,
        label=label,
        value=float(value),
        minimum=float(minimum),
        maximum=float(maximum),
        step=float(step),
        suffix=suffix,
        integer=integer,
    )


def _primitive_dimensions(primitive: Any) -> tuple[AuthoredCompositionPrimitiveDimension, ...]:
    base = _base_primitive(primitive)
    if isinstance(base, FloorPrimitive):
        return (
            _dimension("width", "Width", base.width),
            _dimension("depth", "Depth", base.depth),
        )
    if isinstance(base, WallPrimitive):
        return (
            _dimension("width", "Width", base.width),
            _dimension("height", "Height", base.height),
            _dimension("thickness", "Thickness", base.thickness, minimum=0.01, step=0.01),
        )
    if isinstance(base, CubePrimitive):
        return (
            _dimension("size_x", "Size X", base.size[0]),
            _dimension("size_y", "Size Y", base.size[1]),
            _dimension("size_z", "Size Z", base.size[2]),
        )
    if isinstance(base, RampPrimitive):
        return (
            _dimension("width", "Width", base.width),
            _dimension("length", "Length", base.length),
            _dimension("height", "Height", base.height),
        )
    if isinstance(base, StairsPrimitive):
        return (
            _dimension("width", "Width", base.width),
            _dimension("depth", "Depth", base.depth),
            _dimension("height", "Height", base.height),
            _dimension("steps", "Steps", base.steps, minimum=1.0, maximum=64.0, step=1.0, suffix="", integer=True),
        )
    if isinstance(base, CylinderPrimitive):
        return (
            _dimension("radius", "Radius", base.radius),
            _dimension("height", "Height", base.height),
            _dimension("segments", "Segments", base.segments, minimum=3.0, maximum=128.0, step=1.0, suffix="", integer=True),
        )
    if isinstance(base, DoorFramePrimitive):
        return (
            _dimension("width", "Width", base.width),
            _dimension("height", "Height", base.height),
            _dimension("jamb_width", "Jamb", base.jamb_width, minimum=0.01, step=0.01),
            _dimension("lintel_height", "Lintel", base.lintel_height, minimum=0.01, step=0.01),
            _dimension("depth", "Depth", base.depth, minimum=0.01, step=0.01),
        )
    if isinstance(base, ArchPrimitive):
        return (
            _dimension("width", "Width", base.width),
            _dimension("height", "Height", base.height),
            _dimension("frame_thickness", "Frame", base.frame_thickness, minimum=0.01, step=0.01),
            _dimension("depth", "Depth", base.depth, minimum=0.01, step=0.01),
            _dimension("segments", "Segments", base.segments, minimum=3.0, maximum=64.0, step=1.0, suffix="", integer=True),
        )
    return ()


def _primitive_material_value(primitive: Any) -> PrimitiveMaterial:
    return getattr(_base_primitive(primitive), "material", PrimitiveMaterial())


def _primitive_surface_id(primitive: Any) -> int | None:
    base = _base_primitive(primitive)
    if isinstance(base, (FloorPrimitive, RampPrimitive, StairsPrimitive)):
        return resolve_walkmesh_surface_id(base.surface_id)
    return None


def _primitive_supports_walkmesh_surface(primitive: Any) -> bool:
    return _primitive_surface_id(primitive) is not None


def _primitive_world_vertices(room: AuthoredRoomSpec, primitive: Any) -> tuple[tuple[float, float, float], ...]:
    mesh = primitive_to_mesh(primitive)
    offset = _room_offset(room)
    return tuple(
        (
            float(vertex[0]) + offset[0],
            float(vertex[1]) + offset[1],
            float(vertex[2]) + offset[2],
        )
        for vertex in tuple(mesh.vertices or ())
    )


def _vec_bounds(vertices: tuple[tuple[float, float, float], ...]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    if not vertices:
        raise ValueError("Universal Manipulator needs a selected primitive with renderable vertices.")
    xs = tuple(float(vertex[0]) for vertex in vertices)
    ys = tuple(float(vertex[1]) for vertex in vertices)
    zs = tuple(float(vertex[2]) for vertex in vertices)
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _vec_center(
    bounds_min: tuple[float, float, float],
    bounds_max: tuple[float, float, float],
) -> tuple[float, float, float]:
    return tuple((float(bounds_min[index]) + float(bounds_max[index])) * 0.5 for index in range(3))  # type: ignore[return-value]


def _vec_dimensions(
    bounds_min: tuple[float, float, float],
    bounds_max: tuple[float, float, float],
) -> tuple[float, float, float]:
    return tuple(max(0.0, float(bounds_max[index]) - float(bounds_min[index])) for index in range(3))  # type: ignore[return-value]


def authored_room_composition_primitive_universal_transform(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
) -> AuthoredUniversalTransformSelection:
    """Return exact KMAP-world bounds for one selected composition primitive.

    This is the headless contract behind Ctrl+T / Universal Manipulator.  The
    UI draws handles and dimension labels from this data; transform and
    dimension edits still commit through the existing authored-room commands.
    """

    room_index = _target_room_index(project, room_resref)
    room = project.rooms[room_index]
    composition = _composition_for_room(room)
    target = str(primitive_name or "").strip()
    if not target:
        raise ValueError("Universal Manipulator needs a selected authored primitive.")
    for primitive in tuple(composition.primitives or ()):
        if _primitive_name(primitive) != target:
            continue
        mesh = primitive_to_mesh(primitive)
        vertices = _primitive_world_vertices(room, primitive)
        bounds_min, bounds_max = _vec_bounds(vertices)
        transform = _primitive_transform(primitive)
        surface_id = _primitive_surface_id(primitive)
        material = _primitive_material_value(primitive)
        return AuthoredUniversalTransformSelection(
            room_resref=normalise_resref(room.room_resref),
            primitive_name=target,
            primitive_type=_primitive_type(primitive),
            coordinate_space="kmap_world",
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            center=_vec_center(bounds_min, bounds_max),
            dimensions=_vec_dimensions(bounds_min, bounds_max),
            translation=tuple(float(value) for value in transform.translation),
            rotation_degrees_z=float(transform.rotation_degrees_z),
            scale=tuple(float(value) for value in transform.scale),
            pivot=tuple(float(value) for value in transform.pivot),
            vertex_count=len(tuple(mesh.vertices or ())),
            face_count=len(tuple(mesh.faces or ())),
            texture=str(material.texture or ""),
            surface_id=surface_id,
            surface_name=walkmesh_surface_name(surface_id) if surface_id is not None else "",
            metadata={
                "source": "map_studio:universal_transform",
                "selection_space": "authored_room_composition_primitive",
                "room_offset": list(_room_offset(room)),
            },
        )
    raise ValueError(f"Room {room.room_resref} has no primitive named '{primitive_name}'.")


def _primitive_kind(value: Any) -> str:
    kind = str(value or "").strip().lower().replace(" ", "_")
    aliases = {
        "box": "cube",
        "column": "cylinder",
        "floor": "plane",
        "platform": "plane",
        "stair": "stairs",
        "step": "stairs",
        "doorframe": "door_frame",
        "door_frame": "door_frame",
        "doorway": "door_frame",
        "doorway_frame": "door_frame",
        "door_arch": "arch",
    }
    kind = aliases.get(kind, kind)
    known = {item.kind for item in _COMPOSITION_PRIMITIVE_KINDS}
    if kind not in known:
        raise ValueError(f"Unsupported authored room primitive kind '{value}'. Known kinds: {', '.join(sorted(known))}.")
    return kind


def _unique_primitive_name(composition: AuthoredRoomComposition, kind: str, requested_name: str = "") -> str:
    used = {_primitive_name(primitive).lower() for primitive in composition.primitives if _primitive_name(primitive)}
    base = str(requested_name or "").strip()
    if not base:
        base = f"{normalise_resref(composition.room_resref)}_{kind}"
    candidate = base
    index = 2
    while candidate.lower() in used:
        candidate = f"{base}_{index}"
        index += 1
    return candidate


def _safe_room_resref_seed(value: Any, fallback: str) -> str:
    text = str(value or "").strip() or str(fallback or "").strip()
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in text)
    safe = safe.strip("_") or "room"
    return normalise_resref(safe)


def _unique_room_resref(project: AuthoredModuleProject, requested: str, fallback: str) -> str:
    used = {normalise_resref(room.room_resref) for room in tuple(project.rooms or ())}
    base = _safe_room_resref_seed(requested, fallback)
    issue = authored_resref_blocking_issue("Separated room", base)
    if issue:
        raise ValueError(issue)
    if base not in used:
        return base
    for index in range(2, 1000):
        suffix = f"_{index}"
        candidate = normalise_resref(f"{base[: max(1, 16 - len(suffix))]}{suffix}")
        if candidate not in used:
            return candidate
    raise ValueError(f"Could not create a unique room resref from '{requested or fallback}'.")


def _primitive_material(composition: AuthoredRoomComposition, texture: str = "") -> PrimitiveMaterial:
    material = composition.floor.material
    if texture:
        return PrimitiveMaterial(
            texture=str(texture),
            diffuse=material.diffuse,
            ambient=material.ambient,
            metadata={**dict(material.metadata), "source": "map_studio:add_composition_primitive"},
        )
    return material


def _default_primitive_for_kind(kind: str, name: str, material: PrimitiveMaterial, floor_surface: Any) -> Any:
    if kind == "plane":
        return FloorPrimitive(name=name, width=3.0, depth=3.0, z=0.0, surface_id=floor_surface, material=material)
    if kind == "wall":
        return WallPrimitive(name=name, width=4.0, height=3.0, thickness=0.15, center=(0.0, 0.0, 1.5), material=material)
    if kind == "cube":
        return CubePrimitive(name=name, size=(1.0, 1.0, 1.0), center=(0.0, 0.0, 0.5), material=material)
    if kind == "ramp":
        return RampPrimitive(name=name, width=2.0, length=3.0, height=1.0, surface_id=floor_surface, material=material)
    if kind == "stairs":
        return StairsPrimitive(name=name, width=2.0, depth=3.0, height=1.0, steps=4, surface_id=floor_surface, material=material)
    if kind == "cylinder":
        return CylinderPrimitive(name=name, radius=0.5, height=1.0, segments=16, center=(0.0, 0.0, 0.5), material=material)
    if kind == "door_frame":
        return DoorFramePrimitive(name=name, width=2.2, height=3.0, jamb_width=0.22, lintel_height=0.28, depth=0.25, center=(0.0, 0.0, 1.5), material=material)
    if kind == "arch":
        return ArchPrimitive(name=name, width=2.4, height=3.0, frame_thickness=0.3, depth=0.35, center=(0.0, 0.0, 1.5), material=material)
    raise ValueError(f"Unsupported authored room primitive kind '{kind}'.")


def _dimension_values(values: Any) -> dict[str, Any]:
    if values is None:
        return {}
    if isinstance(values, dict):
        return {str(key): value for key, value in values.items()}
    raise ValueError("Primitive dimension edits require a dictionary of dimension key/value pairs.")


def _dimension_float(values: dict[str, Any], key: str, current: float, *, minimum: float = 0.001) -> float:
    if key not in values or values[key] in (None, ""):
        return float(current)
    value = float(values[key])
    if value < minimum:
        raise ValueError(f"Primitive dimension '{key}' must be at least {minimum}.")
    return value


def _dimension_int(values: dict[str, Any], key: str, current: int, *, minimum: int = 1) -> int:
    if key not in values or values[key] in (None, ""):
        return int(current)
    value = int(round(float(values[key])))
    if value < minimum:
        raise ValueError(f"Primitive dimension '{key}' must be at least {minimum}.")
    return value


def _reject_unknown_dimensions(values: dict[str, Any], allowed: set[str], primitive_name: str) -> None:
    unknown = sorted(key for key in values if key not in allowed)
    if unknown:
        raise ValueError(f"Primitive {primitive_name} does not support dimension(s): {', '.join(unknown)}.")


def _updated_base_primitive_dimensions(base: Any, dimensions: Any) -> Any:
    values = _dimension_values(dimensions)
    if isinstance(base, FloorPrimitive):
        allowed = {"width", "depth"}
        _reject_unknown_dimensions(values, allowed, base.name)
        return replace(
            base,
            width=_dimension_float(values, "width", base.width),
            depth=_dimension_float(values, "depth", base.depth),
        )
    if isinstance(base, WallPrimitive):
        allowed = {"width", "height", "thickness"}
        _reject_unknown_dimensions(values, allowed, base.name)
        return replace(
            base,
            width=_dimension_float(values, "width", base.width),
            height=_dimension_float(values, "height", base.height),
            thickness=_dimension_float(values, "thickness", base.thickness, minimum=0.01),
        )
    if isinstance(base, CubePrimitive):
        allowed = {"size_x", "size_y", "size_z"}
        _reject_unknown_dimensions(values, allowed, base.name)
        return replace(
            base,
            size=(
                _dimension_float(values, "size_x", base.size[0]),
                _dimension_float(values, "size_y", base.size[1]),
                _dimension_float(values, "size_z", base.size[2]),
            ),
        )
    if isinstance(base, RampPrimitive):
        allowed = {"width", "length", "height"}
        _reject_unknown_dimensions(values, allowed, base.name)
        return replace(
            base,
            width=_dimension_float(values, "width", base.width),
            length=_dimension_float(values, "length", base.length),
            height=_dimension_float(values, "height", base.height),
        )
    if isinstance(base, StairsPrimitive):
        allowed = {"width", "depth", "height", "steps"}
        _reject_unknown_dimensions(values, allowed, base.name)
        return replace(
            base,
            width=_dimension_float(values, "width", base.width),
            depth=_dimension_float(values, "depth", base.depth),
            height=_dimension_float(values, "height", base.height),
            steps=_dimension_int(values, "steps", base.steps, minimum=1),
        )
    if isinstance(base, CylinderPrimitive):
        allowed = {"radius", "height", "segments"}
        _reject_unknown_dimensions(values, allowed, base.name)
        return replace(
            base,
            radius=_dimension_float(values, "radius", base.radius),
            height=_dimension_float(values, "height", base.height),
            segments=_dimension_int(values, "segments", base.segments, minimum=3),
        )
    if isinstance(base, DoorFramePrimitive):
        allowed = {"width", "height", "jamb_width", "lintel_height", "depth"}
        _reject_unknown_dimensions(values, allowed, base.name)
        return replace(
            base,
            width=_dimension_float(values, "width", base.width),
            height=_dimension_float(values, "height", base.height),
            jamb_width=_dimension_float(values, "jamb_width", base.jamb_width, minimum=0.01),
            lintel_height=_dimension_float(values, "lintel_height", base.lintel_height, minimum=0.01),
            depth=_dimension_float(values, "depth", base.depth, minimum=0.01),
        )
    if isinstance(base, ArchPrimitive):
        allowed = {"width", "height", "frame_thickness", "depth", "segments"}
        _reject_unknown_dimensions(values, allowed, base.name)
        return replace(
            base,
            width=_dimension_float(values, "width", base.width),
            height=_dimension_float(values, "height", base.height),
            frame_thickness=_dimension_float(values, "frame_thickness", base.frame_thickness, minimum=0.01),
            depth=_dimension_float(values, "depth", base.depth, minimum=0.01),
            segments=_dimension_int(values, "segments", base.segments, minimum=3),
        )
    raise ValueError(f"Primitive {getattr(base, 'name', '(unnamed)')} does not expose editable dimensions.")


def _style_metadata(texture: str, surface_id: int | None = None) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "source": "map_studio:composition_primitive_style_update",
        "texture": texture,
    }
    if surface_id is not None:
        metadata["surface_id"] = int(surface_id)
        metadata["surface_name"] = walkmesh_surface_name(surface_id)
    return metadata


def _updated_base_primitive_style(base: Any, *, texture: Any = "", surface_id: Any = None) -> Any:
    material_preflight = compile_authored_room_material_preflight(texture or getattr(getattr(base, "material", None), "texture", "default"))
    if material_preflight.blocking_issues:
        raise ValueError(material_preflight.blocking_issues[0])
    current_material = getattr(base, "material", PrimitiveMaterial())
    next_surface_id = None
    if isinstance(base, (FloorPrimitive, RampPrimitive, StairsPrimitive)):
        next_surface_id = resolve_walkmesh_surface_id(base.surface_id if surface_id in (None, "") else surface_id)
    elif surface_id not in (None, ""):
        raise ValueError(f"Primitive {getattr(base, 'name', '(unnamed)')} does not contribute walkmesh faces, so it cannot have a WOK surface.")
    material = replace(
        current_material,
        texture=material_preflight.texture,
        metadata={
            **dict(current_material.metadata),
            **_style_metadata(material_preflight.texture, next_surface_id),
        },
    )
    if isinstance(base, (FloorPrimitive, RampPrimitive, StairsPrimitive)):
        return replace(base, material=material, surface_id=next_surface_id)
    return replace(base, material=material)


def authored_room_composition_primitives(
    project: AuthoredModuleProject,
    *,
    room_resref: str = "",
) -> tuple[AuthoredCompositionPrimitiveTransform, ...]:
    """Return editable primitive transform rows for authored composition rooms."""

    rows: list[AuthoredCompositionPrimitiveTransform] = []
    rooms = tuple(project.rooms or ())
    target = normalise_resref(room_resref)
    for room in rooms:
        room_name = normalise_resref(room.room_resref)
        if target and room_name != target:
            continue
        try:
            composition = _composition_for_room(room)
        except ValueError:
            continue
        for primitive in tuple(composition.primitives or ()):
            name = _primitive_name(primitive)
            if not name:
                continue
            transform = _primitive_transform(primitive)
            material = _primitive_material_value(primitive)
            surface_id = _primitive_surface_id(primitive)
            rows.append(
                AuthoredCompositionPrimitiveTransform(
                    room_resref=room_name,
                    primitive_name=name,
                    primitive_type=_primitive_type(primitive),
                    translation=tuple(float(value) for value in transform.translation),
                    rotation_degrees_z=float(transform.rotation_degrees_z),
                    scale=tuple(float(value) for value in transform.scale),
                    pivot=tuple(float(value) for value in transform.pivot),
                    texture=str(material.texture or ""),
                    surface_id=surface_id,
                    surface_name=walkmesh_surface_name(surface_id) if surface_id is not None else "",
                    supports_walkmesh_surface=_primitive_supports_walkmesh_surface(primitive),
                    dimensions=_primitive_dimensions(primitive),
                )
            )
    return tuple(rows)


def add_authored_room_composition_primitive(
    project: AuthoredModuleProject,
    *,
    primitive_kind: str,
    room_resref: str = "",
    primitive_name: str = "",
    translation: Any = None,
    rotation_degrees_z: float | None = None,
    scale: Any = None,
    pivot: Any = None,
    texture: str = "",
    floor_surface: Any = None,
) -> AuthoredModuleProject:
    """Append a new editable primitive instance to a composition room."""

    room_index = _target_room_index(project, room_resref)
    rooms = list(project.rooms)
    room = rooms[room_index]
    composition = _composition_for_room(room)
    kind = _primitive_kind(primitive_kind)
    name = _unique_primitive_name(composition, kind, primitive_name)
    surface = floor_surface if floor_surface is not None else composition.floor.surface_id
    material = _primitive_material(composition, texture)
    base = _default_primitive_for_kind(kind, name, material, surface)
    transform = _updated_transform(
        PrimitiveTransform(),
        translation=translation,
        rotation_degrees_z=rotation_degrees_z,
        scale=scale,
        pivot=pivot,
    )
    updated_composition = replace(
        composition,
        primitives=tuple(composition.primitives)
        + (
            PlacedRoomPrimitive(
                primitive=base,
                transform=transform,
                name=name,
            ),
        ),
        metadata={
            **dict(composition.metadata),
            "last_added_primitive": name,
            "last_added_primitive_kind": kind,
        },
    )
    rooms[room_index] = replace(
        room,
        primitive=updated_composition if isinstance(room.primitive, AuthoredRoomComposition) else room.primitive,
        composition=updated_composition if room.composition is not None else room.composition,
        metadata={
            **dict(room.metadata),
            "last_operation": "add_composition_primitive",
            "last_added_primitive": name,
        },
    )
    return _replace_rooms(
        project,
        tuple(rooms),
        operation=f"add_composition_primitive:{kind}:{name}",
    )


def set_authored_room_composition_primitive_dimensions(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
    dimensions: Any,
) -> AuthoredModuleProject:
    """Update editable dimensions for a named composition primitive."""

    room_index = _target_room_index(project, room_resref)
    rooms = list(project.rooms)
    room = rooms[room_index]
    composition = _composition_for_room(room)
    target = str(primitive_name or "").strip()
    if not target:
        raise ValueError("Primitive dimension edits require a primitive name.")
    primitives = list(composition.primitives)
    for index, primitive in enumerate(primitives):
        if _primitive_name(primitive) != target:
            continue
        base = _base_primitive(primitive)
        updated_base = _updated_base_primitive_dimensions(base, dimensions)
        if isinstance(primitive, PlacedRoomPrimitive):
            primitives[index] = replace(primitive, primitive=updated_base)
        else:
            primitives[index] = updated_base
        updated_composition = replace(
            composition,
            primitives=tuple(primitives),
            metadata={
                **dict(composition.metadata),
                "last_dimension_edit": target,
            },
        )
        rooms[room_index] = replace(
            room,
            primitive=updated_composition if isinstance(room.primitive, AuthoredRoomComposition) else room.primitive,
            composition=updated_composition if room.composition is not None else room.composition,
            metadata={
                **dict(room.metadata),
                "last_operation": "set_composition_primitive_dimensions",
                "last_dimension_edit": target,
            },
        )
        return _replace_rooms(
            project,
            tuple(rooms),
            operation=f"set_composition_primitive_dimensions:{target}",
        )
    raise ValueError(f"Room {room.room_resref} has no primitive named '{primitive_name}'.")


def set_authored_room_composition_primitive_style(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
    texture: Any = "",
    surface_id: Any = None,
) -> AuthoredModuleProject:
    """Update material and optional WOK surface for a named composition primitive."""

    room_index = _target_room_index(project, room_resref)
    rooms = list(project.rooms)
    room = rooms[room_index]
    composition = _composition_for_room(room)
    target = str(primitive_name or "").strip()
    if not target:
        raise ValueError("Primitive style edits require a primitive name.")
    primitives = list(composition.primitives)
    for index, primitive in enumerate(primitives):
        if _primitive_name(primitive) != target:
            continue
        base = _base_primitive(primitive)
        updated_base = _updated_base_primitive_style(base, texture=texture, surface_id=surface_id)
        if isinstance(primitive, PlacedRoomPrimitive):
            primitives[index] = replace(primitive, primitive=updated_base)
        else:
            primitives[index] = updated_base
        updated_composition = replace(
            composition,
            primitives=tuple(primitives),
            metadata={
                **dict(composition.metadata),
                "last_style_edit": target,
            },
        )
        rooms[room_index] = replace(
            room,
            primitive=updated_composition if isinstance(room.primitive, AuthoredRoomComposition) else room.primitive,
            composition=updated_composition if room.composition is not None else room.composition,
            metadata={
                **dict(room.metadata),
                "last_operation": "set_composition_primitive_style",
                "last_style_edit": target,
            },
        )
        return _replace_rooms(
            project,
            tuple(rooms),
            operation=f"set_composition_primitive_style:{target}",
        )
    raise ValueError(f"Room {room.room_resref} has no primitive named '{primitive_name}'.")


def _edge_normal_policy_payload(
    *,
    policy: str,
    primitive_name: str = "",
    edge_indices: Any = None,
    edge_count: int | None = None,
    coordinate_space: str = "",
) -> dict[str, Any]:
    raw_policy = str(policy or "").strip().lower()
    aliases = {
        "soft": "soft",
        "soften": "soft",
        "soften_edges": "soft",
        "smooth": "soft",
        "hard": "hard",
        "harden": "hard",
        "harden_edges": "hard",
        "flat": "hard",
    }
    normal_policy = aliases.get(raw_policy)
    if normal_policy is None:
        raise ValueError("Edge normal policy must be 'soft' or 'hard'.")
    target = str(primitive_name or "").strip()
    indices = _edge_index_values(edge_indices)
    scope = "selected_edges" if indices else ("primitive" if target else "all")
    operation = "soften_edges" if normal_policy == "soft" else "harden_edges"
    payload = {
        "edge_normal_policy": normal_policy,
        "edge_normal_policy_operation": operation,
        "edge_normal_policy_scope": scope,
        "edge_normal_policy_target": target or "all",
        "edge_normal_policy_edges": indices,
        "edge_normal_policy_source": "map_studio_tool_belt",
    }
    if edge_count is not None:
        payload["edge_normal_policy_edge_count"] = int(edge_count)
    if coordinate_space:
        payload["edge_normal_policy_coordinate_space"] = str(coordinate_space)
    return payload


def set_authored_room_edge_normal_policy(
    project: AuthoredModuleProject,
    *,
    room_resref: str = "",
    policy: str,
    primitive_name: str = "",
    edge_indices: Any = None,
) -> AuthoredModuleProject:
    """Record soft/hard visual edge-normal intent for authored room geometry.

    This is an authored policy command, not a renderer-only toggle.  Later MDL
    export and viewport-normal baking can consume this metadata while WOK
    traversal remains validated separately.
    """

    room_index = _target_room_index(project, room_resref)
    rooms = list(project.rooms)
    room = rooms[room_index]
    indices = _edge_index_values(edge_indices)

    if isinstance(room.primitive, AuthoredRoomComposition) or room.composition is not None:
        composition = _composition_for_room(room)
        target_name = str(primitive_name or "").strip()
        if indices and not target_name:
            raise ValueError(
                "Selected edge normal edits for primitive-composition rooms require a primitive name "
                "so edge indices are unambiguous."
            )
        edge_count = 0
        coordinate_space = "authored_room_composition_all_primitive_edges"
        if target_name:
            selected = next((item for item in tuple(composition.primitives or ()) if _primitive_name(item) == target_name), None)
            if selected is None:
                known = ", ".join(_primitive_name(item) for item in tuple(composition.primitives or ()) if _primitive_name(item))
                raise ValueError(f"Room {room.room_resref} has no primitive named '{primitive_name}'. Known primitives: {known or '(none)'}.")
            edge_count = _primitive_mesh_edge_count(selected)
            _validate_edge_indices(indices, edge_count=edge_count, label=f"Primitive {target_name}")
            coordinate_space = "authored_room_composition_primitive_edges"
        else:
            edge_count = sum(_primitive_mesh_edge_count(item) for item in tuple(composition.primitives or ()))
        payload = _edge_normal_policy_payload(
            policy=policy,
            primitive_name=target_name,
            edge_indices=indices,
            edge_count=edge_count,
            coordinate_space=coordinate_space,
        )
        operation = str(payload["edge_normal_policy_operation"])
        target = str(payload["edge_normal_policy_target"])
        by_target = dict(composition.metadata.get("edge_normal_policy_by_target") or {})
        by_target[target] = dict(payload)
        updated_composition = replace(
            composition,
            metadata={
                **dict(composition.metadata),
                **payload,
                "edge_normal_policy_by_target": by_target,
                "last_operation": operation,
            },
        )
        rooms[room_index] = replace(
            room,
            primitive=updated_composition if isinstance(room.primitive, AuthoredRoomComposition) else room.primitive,
            composition=updated_composition if room.composition is not None else room.composition,
            metadata={
                **dict(room.metadata),
                **payload,
                "last_operation": operation,
            },
        )
        return _replace_rooms(project, tuple(rooms), operation=f"{operation}:{target}")

    try:
        primitive = _floor_plan_for_room(room)
    except ValueError as exc:
        raise ValueError(
            "Edge normal policy currently supports authored floor-plan and primitive-composition rooms; "
            "terrain normals are derived from the heightfield brush pipeline."
        ) from exc
    edge_count = len(tuple(primitive.points or ()))
    _validate_edge_indices(indices, edge_count=edge_count, label=f"Floor-plan room {room.room_resref}")
    payload = _edge_normal_policy_payload(
        policy=policy,
        primitive_name=primitive_name,
        edge_indices=indices,
        edge_count=edge_count,
        coordinate_space="authored_floor_plan_loop_edges",
    )
    operation = str(payload["edge_normal_policy_operation"])
    target = str(payload["edge_normal_policy_target"])

    updated_primitive = replace(
        primitive,
        metadata={
            **dict(primitive.metadata),
            **payload,
            "last_operation": operation,
        },
    )
    rooms[room_index] = replace(
        room,
        primitive=updated_primitive,
        composition=None,
        metadata={
            **dict(room.metadata),
            "primitive": "floor_plan_extrusion",
            **payload,
            "last_operation": operation,
        },
    )
    return _replace_rooms(project, tuple(rooms), operation=f"{operation}:{target}")


def remove_authored_room_composition_primitive(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
) -> AuthoredModuleProject:
    """Remove a named editable primitive from a composition room."""

    room_index = _target_room_index(project, room_resref)
    rooms = list(project.rooms)
    room = rooms[room_index]
    composition = _composition_for_room(room)
    target = str(primitive_name or "").strip()
    if not target:
        raise ValueError("Removing a composition primitive requires a primitive name.")
    primitives = [primitive for primitive in composition.primitives if _primitive_name(primitive) != target]
    if len(primitives) == len(tuple(composition.primitives)):
        raise ValueError(f"Room {room.room_resref} has no primitive named '{primitive_name}'.")
    updated_composition = replace(
        composition,
        primitives=tuple(primitives),
        metadata={
            **dict(composition.metadata),
            "last_removed_primitive": target,
        },
    )
    rooms[room_index] = replace(
        room,
        primitive=updated_composition if isinstance(room.primitive, AuthoredRoomComposition) else room.primitive,
        composition=updated_composition if room.composition is not None else room.composition,
        metadata={
            **dict(room.metadata),
            "last_operation": "remove_composition_primitive",
            "last_removed_primitive": target,
        },
    )
    return _replace_rooms(
        project,
        tuple(rooms),
        operation=f"remove_composition_primitive:{target}",
    )


def separate_authored_room_composition_primitive(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
    result_room_resref: str = "",
) -> AuthoredModuleProject:
    """Move one composition primitive into a new exportable authored room boundary."""

    source_index = _target_room_index(project, room_resref)
    rooms = list(project.rooms)
    source_room = rooms[source_index]
    source_composition = _composition_for_room(source_room)
    target = str(primitive_name or "").strip()
    if not target:
        raise ValueError("Separating a composition primitive requires a primitive name.")
    primitives = list(tuple(source_composition.primitives or ()))
    selected: Any | None = None
    remaining: list[Any] = []
    for primitive in primitives:
        if _primitive_name(primitive) == target and selected is None:
            selected = primitive
            continue
        remaining.append(primitive)
    if selected is None:
        raise ValueError(f"Room {source_room.room_resref} has no primitive named '{primitive_name}'.")
    new_room_resref = _unique_room_resref(project, result_room_resref, target)
    new_floor = replace(
        source_composition.floor,
        name=f"{new_room_resref}_mesh",
        material=source_composition.floor.material,
    )
    separated_composition = AuthoredRoomComposition(
        room_resref=new_room_resref,
        floor=new_floor,
        primitives=(selected,),
        helper_meshes=(),
        metadata={
            **dict(source_composition.metadata),
            "last_operation": "separate_composition_primitive",
            "separated_from_room": normalise_resref(source_room.room_resref),
            "separated_primitive": target,
            "source": "src.core.modules.authored_room_operations",
        },
    )
    updated_source_composition = replace(
        source_composition,
        primitives=tuple(remaining),
        metadata={
            **dict(source_composition.metadata),
            "last_operation": "separate_composition_primitive",
            "last_separated_primitive": target,
            "last_separated_room": new_room_resref,
        },
    )
    rooms[source_index] = replace(
        source_room,
        primitive=updated_source_composition if isinstance(source_room.primitive, AuthoredRoomComposition) else source_room.primitive,
        composition=updated_source_composition if source_room.composition is not None else source_room.composition,
        metadata={
            **dict(source_room.metadata),
            "last_operation": "separate_composition_primitive",
            "last_separated_primitive": target,
            "last_separated_room": new_room_resref,
        },
    )
    new_room = AuthoredRoomSpec(
        room_resref=new_room_resref,
        primitive=separated_composition,
        composition=None,
        position=tuple(source_room.position or (0.0, 0.0, 0.0)),
        visible_rooms=(),
        metadata={
            "primitive": "authored_room_composition",
            "source": "src.core.modules.authored_room_operations",
            "last_operation": "separate_composition_primitive",
            "separated_from_room": normalise_resref(source_room.room_resref),
            "separated_primitive": target,
        },
    )
    rooms.append(new_room)
    room_tuple = tuple(rooms)
    visible = _all_room_names(room_tuple)
    room_tuple = tuple(replace(room, visible_rooms=visible) for room in room_tuple)
    return _replace_rooms(
        project,
        room_tuple,
        operation=f"separate_composition_primitive:{target}:{new_room_resref}",
    )


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


def move_authored_room_composition_primitive(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
    world_delta: Any,
) -> AuthoredModuleProject:
    """Move one authored composition primitive by a viewport-authored world delta."""

    delta = _vec3_or_existing(world_delta, (0.0, 0.0, 0.0))
    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    composition = _composition_for_room(room)
    target = str(primitive_name or "").strip()
    if not target:
        raise ValueError("Primitive move operation requires a primitive name.")
    for primitive in tuple(composition.primitives or ()):
        if _primitive_name(primitive) != target:
            continue
        transform = _primitive_transform(primitive)
        translation = tuple(float(transform.translation[i]) + float(delta[i]) for i in range(3))
        return set_authored_room_composition_primitive_transform(
            project,
            room_resref=room_resref,
            primitive_name=primitive_name,
            translation=translation,
            rotation_degrees_z=transform.rotation_degrees_z,
            scale=transform.scale,
            pivot=transform.pivot,
        )
    raise ValueError(f"Room {room.room_resref} has no primitive named '{primitive_name}'.")


def _snap_scalar_to_grid(value: float, grid_size: float) -> float:
    return round(float(value) / float(grid_size)) * float(grid_size)


def grid_snap_authored_room_composition_primitive(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
    grid_size: float = 0.1,
    axes: tuple[str, ...] | list[str] = ("x", "y", "z"),
) -> AuthoredModuleProject:
    """Snap a selected primitive pivot to the authored Map Studio grid.

    This is an object-placement command in KMAP/world space.  It deliberately
    does not weld or rewrite primitive topology; it moves the primitive by
    updating transform translation so the local pivot lands on the grid.
    """

    safe_grid = float(grid_size)
    if safe_grid <= 0.0:
        raise ValueError("Object Grid Snap size must be greater than zero.")
    axes_tuple = tuple(str(axis or "").strip().lower() for axis in tuple(axes or ("x", "y", "z")))
    axes_xyz = tuple(axis for axis in axes_tuple if axis in {"x", "y", "z"}) or ("x", "y", "z")
    axis_indices = {"x": 0, "y": 1, "z": 2}

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    composition = _composition_for_room(room)
    target = str(primitive_name or "").strip()
    if not target:
        raise ValueError("Object Grid Snap requires a selected authored primitive.")

    updated_primitives = []
    found = False
    old_translation: tuple[float, float, float] | None = None
    new_translation: tuple[float, float, float] | None = None
    snapped_pivot: tuple[float, float, float] | None = None
    for primitive in tuple(composition.primitives or ()):
        name = _primitive_name(primitive)
        if name != target:
            updated_primitives.append(primitive)
            continue
        found = True
        transform = _primitive_transform(primitive)
        old_translation = tuple(float(value) for value in transform.translation)
        pivot = tuple(float(value) for value in transform.pivot)
        world_pivot = tuple(pivot[i] + old_translation[i] for i in range(3))
        next_world_pivot = list(world_pivot)
        next_translation = list(old_translation)
        for axis in axes_xyz:
            component = axis_indices[axis]
            next_world_pivot[component] = _snap_scalar_to_grid(world_pivot[component], safe_grid)
            next_translation[component] = float(next_world_pivot[component]) - pivot[component]
        snapped_pivot = tuple(float(value) for value in next_world_pivot)
        new_translation = tuple(float(value) for value in next_translation)
        snapped_transform = PrimitiveTransform(
            translation=new_translation,
            rotation_degrees_z=float(transform.rotation_degrees_z),
            scale=tuple(float(value) for value in transform.scale),
            pivot=pivot,
        )
        if isinstance(primitive, PlacedRoomPrimitive):
            updated_primitives.append(replace(primitive, transform=snapped_transform))
        else:
            updated_primitives.append(PlacedRoomPrimitive(primitive=primitive, name=name, transform=snapped_transform))

    if not found:
        known = ", ".join(_primitive_name(item) for item in tuple(composition.primitives or ()) if _primitive_name(item))
        raise ValueError(f"Room {room.room_resref} has no primitive named '{primitive_name}'. Known primitives: {known or '(none)'}.")

    updated_composition = replace(
        composition,
        primitives=tuple(updated_primitives),
        metadata={
            **dict(composition.metadata),
            "last_operation": "object_grid_snap_primitive",
            "last_grid_snapped_primitive": target,
            "object_grid_snap_coordinate_space": "kmap_world_pivot",
            "object_grid_snap_size": safe_grid,
            "object_grid_snap_axes": list(axes_xyz),
            "old_translation": list(old_translation or (0.0, 0.0, 0.0)),
            "new_translation": list(new_translation or (0.0, 0.0, 0.0)),
            "snapped_world_pivot": list(snapped_pivot or (0.0, 0.0, 0.0)),
        },
    )
    updated = replace(
        room,
        primitive=updated_composition,
        composition=None,
        metadata={
            **dict(room.metadata),
            "primitive": "authored_room_composition",
            "last_operation": "object_grid_snap_primitive",
            "last_grid_snapped_primitive": target,
        },
    )
    rooms = tuple(project.rooms[:index] + (updated,) + project.rooms[index + 1 :])
    return _replace_rooms(project, rooms, operation="object_grid_snap_primitive")


def authored_room_composition_primitive_vertex_snap_candidates(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
    target_primitive_name: str = "",
    max_results: int = 8,
    distance_limit: float | None = None,
) -> tuple[AuthoredPrimitiveVertexSnapCandidate, ...]:
    """Return nearest transformed primitive vertices for object-level V snapping."""

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    composition = _composition_for_room(room)
    source_name = str(primitive_name or "").strip()
    target_filter = str(target_primitive_name or "").strip()
    if not source_name:
        raise ValueError("Primitive vertex snap candidates require a selected authored primitive.")
    primitives = tuple(composition.primitives or ())
    source_primitive = next((item for item in primitives if _primitive_name(item) == source_name), None)
    if source_primitive is None:
        known = ", ".join(_primitive_name(item) for item in primitives if _primitive_name(item))
        raise ValueError(f"Room {room.room_resref} has no primitive named '{primitive_name}'. Known primitives: {known or '(none)'}.")

    source_transform = _primitive_transform(source_primitive)
    source_pivot = tuple(float(value) for value in source_transform.pivot)
    source_translation = tuple(float(value) for value in source_transform.translation)
    source_position = tuple(source_pivot[i] + source_translation[i] for i in range(3))
    limit = None if distance_limit is None else float(distance_limit)
    count = max(1, int(max_results))
    candidates: list[AuthoredPrimitiveVertexSnapCandidate] = []
    for primitive in primitives:
        name = _primitive_name(primitive)
        if not name or name == source_name:
            continue
        if target_filter and name != target_filter:
            continue
        for vertex_index, vertex in enumerate(tuple(primitive_to_mesh(primitive).vertices or ())):
            position = tuple(float(value) for value in vertex)
            distance = math.sqrt(sum((position[i] - source_position[i]) ** 2 for i in range(3)))
            if limit is not None and distance > limit:
                continue
            candidates.append(
                AuthoredPrimitiveVertexSnapCandidate(
                    room_resref=room.room_resref,
                    primitive_name=name,
                    vertex_index=int(vertex_index),
                    composition_position=position,
                    distance=float(distance),
                    label=f"{name} vertex {vertex_index} ({distance:.3f} m)",
                )
            )
    candidates.sort(key=lambda item: (item.distance, item.primitive_name, item.vertex_index))
    return tuple(candidates[:count])


def snap_authored_room_composition_primitive_pivot_to_vertex(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
    target_primitive_name: str = "",
    target_vertex_index: int | None = None,
) -> AuthoredModuleProject:
    """Snap one primitive object's pivot onto a target primitive vertex.

    This is the headless form of Maya-style object vertex snapping for authored
    primitives.  It moves the selected primitive by transform translation only;
    it does not weld vertices or rewrite topology.  If no target is provided,
    the closest vertex on another primitive in the room is selected.
    """

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    composition = _composition_for_room(room)
    source_name = str(primitive_name or "").strip()
    target_name = str(target_primitive_name or "").strip()
    if not source_name:
        raise ValueError("Object Vertex Snap requires a selected authored primitive.")

    primitives = tuple(composition.primitives or ())
    source_primitive = next((item for item in primitives if _primitive_name(item) == source_name), None)
    known = ", ".join(_primitive_name(item) for item in primitives if _primitive_name(item))
    if source_primitive is None:
        raise ValueError(f"Room {room.room_resref} has no primitive named '{primitive_name}'. Known primitives: {known or '(none)'}.")

    if not target_name or target_vertex_index is None:
        candidates = authored_room_composition_primitive_vertex_snap_candidates(
            project,
            room_resref=room_resref,
            primitive_name=source_name,
            target_primitive_name=target_name,
            max_results=1,
        )
        if not candidates:
            if target_name:
                raise ValueError(f"Target primitive '{target_name}' has no vertices to snap to.")
            raise ValueError("Object Vertex Snap needs another authored primitive with vertices in the selected room.")
        chosen = candidates[0]
        target_name = chosen.primitive_name
        target_vertex_index = chosen.vertex_index

    target_primitive = next((item for item in primitives if _primitive_name(item) == target_name), None)
    if target_primitive is None:
        raise ValueError(f"Room {room.room_resref} has no target primitive named '{target_primitive_name}'. Known primitives: {known or '(none)'}.")

    vertices = tuple(primitive_to_mesh(target_primitive).vertices or ())
    if not vertices:
        raise ValueError(f"Target primitive '{target_name}' has no vertices to snap to.")
    vertex_index = int(target_vertex_index)
    if vertex_index < 0 or vertex_index >= len(vertices):
        raise ValueError(
            f"Target primitive '{target_name}' vertex index {vertex_index} is outside 0..{len(vertices) - 1}."
        )

    target_vertex = tuple(float(value) for value in vertices[vertex_index])
    source_transform = _primitive_transform(source_primitive)
    old_translation = tuple(float(value) for value in source_transform.translation)
    source_pivot = tuple(float(value) for value in source_transform.pivot)
    new_translation = tuple(target_vertex[i] - source_pivot[i] for i in range(3))
    snapped_transform = PrimitiveTransform(
        translation=new_translation,
        rotation_degrees_z=float(source_transform.rotation_degrees_z),
        scale=tuple(float(value) for value in source_transform.scale),
        pivot=source_pivot,
    )

    updated_primitives = []
    for primitive in primitives:
        if _primitive_name(primitive) != source_name:
            updated_primitives.append(primitive)
            continue
        if isinstance(primitive, PlacedRoomPrimitive):
            updated_primitives.append(replace(primitive, transform=snapped_transform))
        else:
            updated_primitives.append(PlacedRoomPrimitive(primitive=primitive, name=source_name, transform=snapped_transform))

    updated_composition = replace(
        composition,
        primitives=tuple(updated_primitives),
        metadata={
            **dict(composition.metadata),
            "last_operation": "object_vertex_snap_primitive",
            "last_vertex_snapped_primitive": source_name,
            "object_vertex_snap_coordinate_space": "authored_room_composition_mesh_space",
            "target_primitive": target_name,
            "target_vertex_index": vertex_index,
            "target_vertex": list(target_vertex),
            "old_translation": list(old_translation),
            "new_translation": list(new_translation),
            "snapped_pivot": list(target_vertex),
        },
    )
    updated = replace(
        room,
        primitive=updated_composition,
        composition=None,
        metadata={
            **dict(room.metadata),
            "primitive": "authored_room_composition",
            "last_operation": "object_vertex_snap_primitive",
            "last_vertex_snapped_primitive": source_name,
        },
    )
    rooms = tuple(project.rooms[:index] + (updated,) + project.rooms[index + 1 :])
    return _replace_rooms(project, rooms, operation="object_vertex_snap_primitive")


def transform_snap_authored_room_composition_primitive_level(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
    axis: str = "z",
    target_primitive_name: str = "",
    target_vertex_index: int | None = None,
    value: float | None = None,
) -> AuthoredModuleProject:
    """Align a primitive pivot component to a target vertex/value level.

    This is the object-placement form of hold-J transform snapping.  It only
    changes the selected primitive translation on one named axis, preserving
    primitive topology, rotation, scale, and pivot intent.
    """

    axis_key = str(axis or "z").strip().lower()
    if axis_key not in {"x", "y", "z"}:
        raise ValueError("Object transform level snap supports X, Y, or Z axes.")
    axis_index = {"x": 0, "y": 1, "z": 2}[axis_key]

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    composition = _composition_for_room(room)
    source_name = str(primitive_name or "").strip()
    target_name = str(target_primitive_name or "").strip()
    if not source_name:
        raise ValueError("Object Transform Level Snap requires a selected authored primitive.")
    primitives = tuple(composition.primitives or ())
    source_primitive = next((item for item in primitives if _primitive_name(item) == source_name), None)
    known = ", ".join(_primitive_name(item) for item in primitives if _primitive_name(item))
    if source_primitive is None:
        raise ValueError(f"Room {room.room_resref} has no primitive named '{primitive_name}'. Known primitives: {known or '(none)'}.")

    target_value = None if value is None else float(value)
    resolved_target_name = target_name
    resolved_target_vertex_index = None if target_vertex_index is None else int(target_vertex_index)
    if target_value is None:
        if resolved_target_name or resolved_target_vertex_index is not None:
            if not resolved_target_name:
                raise ValueError("Object Transform Level Snap needs a target primitive when a target vertex index is supplied.")
            target_primitive = next((item for item in primitives if _primitive_name(item) == resolved_target_name), None)
            if target_primitive is None:
                raise ValueError(f"Room {room.room_resref} has no target primitive named '{target_primitive_name}'. Known primitives: {known or '(none)'}.")
            vertices = tuple(primitive_to_mesh(target_primitive).vertices or ())
            if resolved_target_vertex_index is None:
                candidates = authored_room_composition_primitive_vertex_snap_candidates(
                    project,
                    room_resref=room_resref,
                    primitive_name=source_name,
                    target_primitive_name=resolved_target_name,
                    max_results=1,
                )
                if not candidates:
                    raise ValueError(f"Target primitive '{resolved_target_name}' has no vertices to snap to.")
                chosen = candidates[0]
                resolved_target_vertex_index = chosen.vertex_index
                target_value = chosen.composition_position[axis_index]
            else:
                if resolved_target_vertex_index < 0 or resolved_target_vertex_index >= len(vertices):
                    raise ValueError(
                        f"Target primitive '{resolved_target_name}' vertex index {resolved_target_vertex_index} is outside 0..{len(vertices) - 1}."
                    )
                target_value = float(vertices[resolved_target_vertex_index][axis_index])
        else:
            candidates = authored_room_composition_primitive_vertex_snap_candidates(
                project,
                room_resref=room_resref,
                primitive_name=source_name,
                max_results=1,
            )
            if not candidates:
                raise ValueError("Object Transform Level Snap needs another authored primitive with vertices in the selected room.")
            chosen = candidates[0]
            resolved_target_name = chosen.primitive_name
            resolved_target_vertex_index = chosen.vertex_index
            target_value = float(chosen.composition_position[axis_index])

    transform = _primitive_transform(source_primitive)
    old_translation = tuple(float(component) for component in transform.translation)
    pivot = tuple(float(component) for component in transform.pivot)
    old_pivot_level = pivot[axis_index] + old_translation[axis_index]
    new_translation = list(old_translation)
    new_translation[axis_index] = float(target_value) - pivot[axis_index]
    snapped_transform = PrimitiveTransform(
        translation=tuple(float(component) for component in new_translation),
        rotation_degrees_z=float(transform.rotation_degrees_z),
        scale=tuple(float(component) for component in transform.scale),
        pivot=pivot,
    )
    updated_primitives = []
    for primitive in primitives:
        if _primitive_name(primitive) != source_name:
            updated_primitives.append(primitive)
            continue
        if isinstance(primitive, PlacedRoomPrimitive):
            updated_primitives.append(replace(primitive, transform=snapped_transform))
        else:
            updated_primitives.append(PlacedRoomPrimitive(primitive=primitive, name=source_name, transform=snapped_transform))

    updated_composition = replace(
        composition,
        primitives=tuple(updated_primitives),
        metadata={
            **dict(composition.metadata),
            "last_operation": "object_transform_snap_level",
            "last_transform_snapped_primitive": source_name,
            "object_transform_snap_coordinate_space": "authored_room_composition_mesh_space",
            "object_transform_snap_axis": axis_key,
            "object_transform_snap_value": float(target_value),
            "object_transform_snap_old_pivot_level": float(old_pivot_level),
            "target_primitive": resolved_target_name,
            "target_vertex_index": resolved_target_vertex_index,
            "old_translation": list(old_translation),
            "new_translation": [float(component) for component in new_translation],
        },
    )
    updated = replace(
        room,
        primitive=updated_composition,
        composition=None,
        metadata={
            **dict(room.metadata),
            "primitive": "authored_room_composition",
            "last_operation": "object_transform_snap_level",
            "last_transform_snapped_primitive": source_name,
        },
    )
    rooms = tuple(project.rooms[:index] + (updated,) + project.rooms[index + 1 :])
    return _replace_rooms(project, rooms, operation="object_transform_snap_level")


def shrink_wrap_authored_room_composition_primitive_to_terrain(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
    terrain_room_resref: str = "",
) -> AuthoredModuleProject:
    """Drop a selected authored primitive so its lowest vertex lands on terrain.

    This is the object-placement form of Shrink Wrap. It preserves topology,
    dimensions, pivot, rotation, and scale; only the object's Z translation is
    adjusted. The terrain sample is taken at the primitive pivot's X/Y.
    """

    object_index = _target_room_index(project, room_resref)
    terrain_index = _target_terrain_room_index(project, terrain_room_resref)
    object_room = project.rooms[object_index]
    terrain_room = project.rooms[terrain_index]
    terrain = _terrain_for_room(terrain_room)
    composition = _composition_for_room(object_room)
    source_name = str(primitive_name or "").strip()
    if not source_name:
        raise ValueError("Object Shrink Wrap requires a selected authored primitive.")

    primitives = tuple(composition.primitives or ())
    source_primitive = next((item for item in primitives if _primitive_name(item) == source_name), None)
    known = ", ".join(_primitive_name(item) for item in primitives if _primitive_name(item))
    if source_primitive is None:
        raise ValueError(f"Room {object_room.room_resref} has no primitive named '{primitive_name}'. Known primitives: {known or '(none)'}.")

    transform = _primitive_transform(source_primitive)
    old_translation = tuple(float(component) for component in transform.translation)
    pivot = tuple(float(component) for component in transform.pivot)
    pivot_position = tuple(old_translation[index] + pivot[index] for index in range(3))
    vertices = tuple(primitive_to_mesh(source_primitive).vertices or ())
    if not vertices:
        raise ValueError(f"Primitive '{source_name}' has no vertices to shrink-wrap.")
    old_bottom_z = min(float(vertex[2]) for vertex in vertices)
    terrain_position = _terrain_room_position(terrain_room)
    surface_position = _snap_position_to_terrain(terrain, terrain_position, pivot_position)
    target_surface_z = float(surface_position[2])
    delta_z = target_surface_z - float(old_bottom_z)
    new_translation = (old_translation[0], old_translation[1], old_translation[2] + delta_z)
    wrapped_transform = PrimitiveTransform(
        translation=new_translation,
        rotation_degrees_z=float(transform.rotation_degrees_z),
        scale=tuple(float(component) for component in transform.scale),
        pivot=pivot,
    )

    updated_primitives = []
    for primitive in primitives:
        if _primitive_name(primitive) != source_name:
            updated_primitives.append(primitive)
            continue
        if isinstance(primitive, PlacedRoomPrimitive):
            updated_primitives.append(replace(primitive, transform=wrapped_transform))
        else:
            updated_primitives.append(PlacedRoomPrimitive(primitive=primitive, name=source_name, transform=wrapped_transform))

    updated_composition = replace(
        composition,
        primitives=tuple(updated_primitives),
        metadata={
            **dict(composition.metadata),
            "last_operation": "object_shrink_wrap_to_terrain",
            "last_shrink_wrapped_primitive": source_name,
            "object_shrink_wrap_coordinate_space": "authored_room_composition_mesh_space",
            "terrain_room_resref": normalise_resref(terrain_room.room_resref),
            "terrain_sample_position": [float(surface_position[0]), float(surface_position[1]), target_surface_z],
            "old_bottom_z": float(old_bottom_z),
            "target_surface_z": target_surface_z,
            "delta_z": float(delta_z),
            "old_translation": list(old_translation),
            "new_translation": list(new_translation),
            "source": "map_studio:object_terrain_shrink_wrap",
        },
    )
    updated_room = replace(
        object_room,
        primitive=updated_composition,
        composition=None,
        metadata={
            **dict(object_room.metadata),
            "primitive": "authored_room_composition",
            "last_operation": "object_shrink_wrap_to_terrain",
            "last_shrink_wrapped_primitive": source_name,
            "terrain_room_resref": normalise_resref(terrain_room.room_resref),
        },
    )
    rooms = tuple(project.rooms[:object_index] + (updated_room,) + project.rooms[object_index + 1 :])
    return _replace_rooms(project, rooms, operation="object_shrink_wrap_to_terrain")


def _mirrored_yaw_degrees(rotation_degrees_z: float, axis: str) -> float:
    angle = float(rotation_degrees_z)
    if axis == "x":
        mirrored = 180.0 - angle
    elif axis == "y":
        mirrored = -angle
    else:
        mirrored = angle
    return ((mirrored + 180.0) % 360.0) - 180.0


def mirror_authored_room_composition_primitive_transform(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
    axis: str = "x",
    center: float = 0.0,
) -> AuthoredModuleProject:
    """Reflect a selected authored primitive placement across a coordinate plane.

    This is an object-layout mirror command, not arbitrary baked mesh mirroring.
    It reflects the primitive pivot position across X/Y/Z in authored-room
    composition mesh space and adjusts yaw for X/Y mirrors while preserving
    topology, dimensions, scale, and pivot intent.
    """

    axis_key = str(axis or "x").strip().lower()
    if axis_key not in {"x", "y", "z"}:
        raise ValueError("Object Mirror supports X, Y, or Z axes.")
    axis_index = {"x": 0, "y": 1, "z": 2}[axis_key]
    mirror_center = float(center)

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    composition = _composition_for_room(room)
    source_name = str(primitive_name or "").strip()
    if not source_name:
        raise ValueError("Object Mirror requires a selected authored primitive.")

    primitives = tuple(composition.primitives or ())
    source_primitive = next((item for item in primitives if _primitive_name(item) == source_name), None)
    known = ", ".join(_primitive_name(item) for item in primitives if _primitive_name(item))
    if source_primitive is None:
        raise ValueError(f"Room {room.room_resref} has no primitive named '{primitive_name}'. Known primitives: {known or '(none)'}.")

    transform = _primitive_transform(source_primitive)
    old_translation = tuple(float(component) for component in transform.translation)
    pivot = tuple(float(component) for component in transform.pivot)
    old_pivot_position = tuple(old_translation[component] + pivot[component] for component in range(3))
    mirrored_pivot_position = list(old_pivot_position)
    mirrored_pivot_position[axis_index] = (2.0 * mirror_center) - old_pivot_position[axis_index]
    new_translation = list(old_translation)
    new_translation[axis_index] = mirrored_pivot_position[axis_index] - pivot[axis_index]
    new_rotation = _mirrored_yaw_degrees(float(transform.rotation_degrees_z), axis_key)
    mirrored_transform = PrimitiveTransform(
        translation=tuple(float(component) for component in new_translation),
        rotation_degrees_z=float(new_rotation),
        scale=tuple(float(component) for component in transform.scale),
        pivot=pivot,
    )

    updated_primitives = []
    for primitive in primitives:
        if _primitive_name(primitive) != source_name:
            updated_primitives.append(primitive)
            continue
        if isinstance(primitive, PlacedRoomPrimitive):
            updated_primitives.append(replace(primitive, transform=mirrored_transform))
        else:
            updated_primitives.append(PlacedRoomPrimitive(primitive=primitive, name=source_name, transform=mirrored_transform))

    updated_composition = replace(
        composition,
        primitives=tuple(updated_primitives),
        metadata={
            **dict(composition.metadata),
            "last_operation": "object_mirror_primitive",
            "last_mirrored_primitive": source_name,
            "object_mirror_coordinate_space": "authored_room_composition_mesh_space",
            "object_mirror_axis": axis_key,
            "object_mirror_center": mirror_center,
            "old_pivot_position": list(old_pivot_position),
            "new_pivot_position": [float(component) for component in mirrored_pivot_position],
            "old_rotation_degrees_z": float(transform.rotation_degrees_z),
            "new_rotation_degrees_z": float(new_rotation),
            "old_translation": list(old_translation),
            "new_translation": [float(component) for component in new_translation],
            "source": "map_studio:object_mirror",
        },
    )
    updated_room = replace(
        room,
        primitive=updated_composition,
        composition=None,
        metadata={
            **dict(room.metadata),
            "primitive": "authored_room_composition",
            "last_operation": "object_mirror_primitive",
            "last_mirrored_primitive": source_name,
            "object_mirror_axis": axis_key,
        },
    )
    rooms = tuple(project.rooms[:index] + (updated_room,) + project.rooms[index + 1 :])
    return _replace_rooms(project, rooms, operation="object_mirror_primitive")


def _linear_transform_vector(
    vector: tuple[float, float, float],
    transform: PrimitiveTransform,
) -> tuple[float, float, float]:
    sx, sy, sz = (float(value) for value in transform.scale)
    x = float(vector[0]) * sx
    y = float(vector[1]) * sy
    z = float(vector[2]) * sz
    angle = math.radians(float(transform.rotation_degrees_z))
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return (x * cos_a - y * sin_a, x * sin_a + y * cos_a, z)


def _centered_local_pivot(primitive: Any) -> tuple[float, float, float]:
    mesh = primitive_to_mesh(_base_primitive(primitive))
    bounds_min, bounds_max = _vec_bounds(tuple(mesh.vertices or ()))
    return _vec_center(bounds_min, bounds_max)


def _translation_for_recentered_pivot(
    transform: PrimitiveTransform,
    new_pivot: tuple[float, float, float],
) -> tuple[float, float, float]:
    old_pivot = tuple(float(value) for value in transform.pivot)
    old_linear = _linear_transform_vector(old_pivot, transform)
    new_linear = _linear_transform_vector(new_pivot, transform)
    return tuple(
        float(transform.translation[index])
        + old_pivot[index]
        - old_linear[index]
        - float(new_pivot[index])
        + new_linear[index]
        for index in range(3)
    )  # type: ignore[return-value]


def center_authored_room_composition_primitive_pivot(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
) -> AuthoredModuleProject:
    """Center one primitive pivot in local space while preserving visible geometry."""

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    composition = _composition_for_room(room)
    target = str(primitive_name or "").strip()
    if not target:
        raise ValueError("Center Pivot requires a selected authored primitive.")
    updated_primitives = []
    found = False
    old_pivot: tuple[float, float, float] | None = None
    next_pivot: tuple[float, float, float] | None = None
    for primitive in tuple(composition.primitives or ()):
        name = _primitive_name(primitive)
        if name != target:
            updated_primitives.append(primitive)
            continue
        found = True
        transform = _primitive_transform(primitive)
        old_pivot = tuple(float(value) for value in transform.pivot)
        next_pivot = _centered_local_pivot(primitive)
        centered_transform = PrimitiveTransform(
            translation=_translation_for_recentered_pivot(transform, next_pivot),
            rotation_degrees_z=float(transform.rotation_degrees_z),
            scale=tuple(float(value) for value in transform.scale),
            pivot=next_pivot,
        )
        if isinstance(primitive, PlacedRoomPrimitive):
            updated_primitives.append(replace(primitive, transform=centered_transform))
        else:
            updated_primitives.append(PlacedRoomPrimitive(primitive=primitive, name=name, transform=centered_transform))
    if not found:
        known = ", ".join(_primitive_name(item) for item in tuple(composition.primitives or ()) if _primitive_name(item))
        raise ValueError(f"Room {room.room_resref} has no primitive named '{primitive_name}'. Known primitives: {known or '(none)'}.")
    updated_composition = replace(
        composition,
        primitives=tuple(updated_primitives),
        metadata={
            **dict(composition.metadata),
            "last_operation": "center_primitive_pivot",
            "last_centered_pivot_primitive": target,
            "center_pivot_space": "primitive_local_preserve_world_geometry",
            "old_pivot": list(old_pivot or (0.0, 0.0, 0.0)),
            "new_pivot": list(next_pivot or (0.0, 0.0, 0.0)),
        },
    )
    updated = replace(
        room,
        primitive=updated_composition,
        composition=None,
        metadata={
            **dict(room.metadata),
            "primitive": "authored_room_composition",
            "last_operation": "center_primitive_pivot",
            "last_centered_pivot_primitive": target,
        },
    )
    rooms = tuple(project.rooms[:index] + (updated,) + project.rooms[index + 1 :])
    return _replace_rooms(project, rooms, operation="center_primitive_pivot")


def _transform_local_point(
    point: tuple[float, float, float],
    transform: PrimitiveTransform,
) -> tuple[float, float, float]:
    px, py, pz = (float(value) for value in transform.pivot)
    sx, sy, sz = (float(value) for value in transform.scale)
    tx, ty, tz = (float(value) for value in transform.translation)
    return (
        (float(point[0]) - px) * sx + px + tx,
        (float(point[1]) - py) * sy + py + ty,
        (float(point[2]) - pz) * sz + pz + tz,
    )


def _nearly_equal(left: float, right: float, *, tolerance: float = 1.0e-6) -> bool:
    return abs(float(left) - float(right)) <= tolerance


def _freeze_transform_into_parametric_primitive(
    primitive: Any,
    transform: PrimitiveTransform,
) -> Any:
    """Bake an unrotated primitive transform into editable primitive fields.

    This intentionally does not pretend to be a full mesh bake.  Rotated
    primitives and primitives without an editable X/Y center need the future
    topology-backed mesh primitive before their transform can be frozen without
    changing visible output.
    """

    rotation = float(transform.rotation_degrees_z)
    if not _nearly_equal(rotation, 0.0):
        raise ValueError(
            "Freeze Transform currently supports unrotated authored primitives only. "
            "Keep the rotation as a transform or convert the primitive through a future baked-mesh workflow."
        )

    sx, sy, sz = (float(value) for value in transform.scale)
    if any(value <= 0.0 for value in (sx, sy, sz)):
        raise ValueError("Freeze Transform requires positive primitive scale values.")

    base = _base_primitive(primitive)
    if isinstance(base, CubePrimitive):
        return replace(
            base,
            size=(float(base.size[0]) * sx, float(base.size[1]) * sy, float(base.size[2]) * sz),
            center=_transform_local_point(tuple(base.center), transform),
        )
    if isinstance(base, WallPrimitive):
        axis = str(base.axis or "x").lower()
        width_scale = sy if axis == "y" else sx
        thickness_scale = sx if axis == "y" else sy
        return replace(
            base,
            width=float(base.width) * width_scale,
            height=float(base.height) * sz,
            thickness=float(base.thickness) * thickness_scale,
            center=_transform_local_point(tuple(base.center), transform),
        )
    if isinstance(base, RampPrimitive):
        return replace(
            base,
            width=float(base.width) * sx,
            length=float(base.length) * sy,
            height=float(base.height) * sz,
            center=_transform_local_point(tuple(base.center), transform),
        )
    if isinstance(base, CylinderPrimitive):
        if not _nearly_equal(sx, sy):
            raise ValueError(
                "Freeze Transform cannot bake non-uniform X/Y scale into a cylinder because it would become an ellipse. "
                "Keep the scale as a transform until generic baked mesh primitives are available."
            )
        return replace(
            base,
            radius=float(base.radius) * sx,
            height=float(base.height) * sz,
            center=_transform_local_point(tuple(base.center), transform),
        )
    if isinstance(base, DoorFramePrimitive):
        return replace(
            base,
            width=float(base.width) * sx,
            height=float(base.height) * sz,
            jamb_width=float(base.jamb_width) * sx,
            lintel_height=float(base.lintel_height) * sz,
            depth=float(base.depth) * sy,
            center=_transform_local_point(tuple(base.center), transform),
        )
    if isinstance(base, ArchPrimitive):
        return replace(
            base,
            width=float(base.width) * sx,
            height=float(base.height) * sz,
            frame_thickness=float(base.frame_thickness) * sx,
            depth=float(base.depth) * sy,
            center=_transform_local_point(tuple(base.center), transform),
        )

    raise ValueError(
        f"Freeze Transform cannot safely bake {type(base).__name__} yet because that primitive lacks enough editable "
        "center/shape fields to preserve visible geometry. Use Center Pivot/Transform for now."
    )


def freeze_authored_room_composition_primitive_transform(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
) -> AuthoredModuleProject:
    """Bake a selected primitive's supported transform into its authored shape."""

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    composition = _composition_for_room(room)
    target = str(primitive_name or "").strip()
    if not target:
        raise ValueError("Freeze Transform requires a selected authored primitive.")

    updated_primitives = []
    found = False
    frozen_type = ""
    old_transform: PrimitiveTransform | None = None
    for primitive in tuple(composition.primitives or ()):
        name = _primitive_name(primitive)
        if name != target:
            updated_primitives.append(primitive)
            continue
        found = True
        transform = _primitive_transform(primitive)
        old_transform = transform
        frozen_base = _freeze_transform_into_parametric_primitive(primitive, transform)
        frozen_type = type(frozen_base).__name__
        updated_primitives.append(
            PlacedRoomPrimitive(
                primitive=frozen_base,
                name=name,
                transform=PrimitiveTransform(),
            )
        )

    if not found:
        known = ", ".join(_primitive_name(item) for item in tuple(composition.primitives or ()) if _primitive_name(item))
        raise ValueError(f"Room {room.room_resref} has no primitive named '{primitive_name}'. Known primitives: {known or '(none)'}.")

    transform_payload = {
        "translation": list(tuple(old_transform.translation if old_transform is not None else (0.0, 0.0, 0.0))),
        "rotation_degrees_z": float(old_transform.rotation_degrees_z if old_transform is not None else 0.0),
        "scale": list(tuple(old_transform.scale if old_transform is not None else (1.0, 1.0, 1.0))),
        "pivot": list(tuple(old_transform.pivot if old_transform is not None else (0.0, 0.0, 0.0))),
    }
    updated_composition = replace(
        composition,
        primitives=tuple(updated_primitives),
        metadata={
            **dict(composition.metadata),
            "last_operation": "freeze_primitive_transform",
            "last_frozen_transform_primitive": target,
            "freeze_transform_space": "primitive_local_parametric_unrotated",
            "freeze_transform_primitive_type": frozen_type,
            "frozen_transform": transform_payload,
        },
    )
    updated = replace(
        room,
        primitive=updated_composition,
        composition=None,
        metadata={
            **dict(room.metadata),
            "primitive": "authored_room_composition",
            "last_operation": "freeze_primitive_transform",
            "last_frozen_transform_primitive": target,
        },
    )
    rooms = tuple(project.rooms[:index] + (updated,) + project.rooms[index + 1 :])
    return _replace_rooms(project, rooms, operation="freeze_primitive_transform")


def _duplicate_primitive_name(existing: set[str], source_name: str, duplicate_index: int) -> str:
    base = str(source_name or "primitive").strip() or "primitive"
    for suffix_index in range(duplicate_index, duplicate_index + 1000):
        suffix = f"_dup_{suffix_index:02d}"
        candidate = f"{base[: max(1, 32 - len(suffix))]}{suffix}"[:32]
        if candidate not in existing:
            existing.add(candidate)
            return candidate
    raise ValueError(f"Could not create a unique duplicate name for primitive '{source_name}'.")


def duplicate_authored_room_composition_primitive(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_name: str,
    duplicate_count: int = 1,
    translation_offset: Any = (1.0, 0.0, 0.0),
    rotation_offset_degrees_z: float = 0.0,
    scale_multiplier: Any = (1.0, 1.0, 1.0),
) -> AuthoredModuleProject:
    """Duplicate one authored composition primitive with repeatable transform offsets."""

    count = int(duplicate_count)
    if count <= 0:
        raise ValueError("Duplicate Special requires at least one duplicate.")
    if count > 64:
        raise ValueError("Duplicate Special is limited to 64 duplicates per command to keep Map Studio responsive.")
    offset = _vec3_or_existing(translation_offset, (1.0, 0.0, 0.0))
    multiplier = _vec3_or_existing(scale_multiplier, (1.0, 1.0, 1.0))
    if any(float(value) <= 0.0 for value in multiplier):
        raise ValueError("Duplicate Special scale multipliers must be positive.")
    target = str(primitive_name or "").strip()
    if not target:
        raise ValueError("Duplicate Special requires a selected authored composition primitive.")
    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    composition = _composition_for_room(room)
    existing_names = {
        _primitive_name(item)
        for item in tuple(composition.primitives or ())
        if _primitive_name(item)
    }
    source = None
    for primitive in tuple(composition.primitives or ()):
        if _primitive_name(primitive) == target:
            source = primitive
            break
    if source is None:
        known = ", ".join(sorted(existing_names))
        raise ValueError(f"Room {room.room_resref} has no primitive named '{primitive_name}'. Known primitives: {known or '(none)'}.")
    source_transform = _primitive_transform(source)
    source_base = source.primitive if isinstance(source, PlacedRoomPrimitive) else source
    duplicates: list[PlacedRoomPrimitive] = []
    for step in range(1, count + 1):
        scale = tuple(float(source_transform.scale[i]) * (float(multiplier[i]) ** step) for i in range(3))
        if any(float(value) <= 0.0 for value in scale):
            raise ValueError("Duplicate Special would create a primitive with non-positive scale.")
        duplicates.append(
            PlacedRoomPrimitive(
                primitive=source_base,
                name=_duplicate_primitive_name(existing_names, target, step),
                transform=PrimitiveTransform(
                    translation=tuple(float(source_transform.translation[i]) + (float(offset[i]) * step) for i in range(3)),
                    rotation_degrees_z=float(source_transform.rotation_degrees_z) + (float(rotation_offset_degrees_z) * step),
                    scale=scale,
                    pivot=source_transform.pivot,
                ),
            )
        )
    updated_composition = replace(
        composition,
        primitives=tuple(composition.primitives or ()) + tuple(duplicates),
        metadata={
            **dict(composition.metadata),
            "last_operation": "duplicate_special",
            "last_duplicated_primitive": target,
            "duplicate_count": count,
        },
    )
    updated = replace(
        room,
        primitive=updated_composition,
        composition=None,
        metadata={
            **dict(room.metadata),
            "primitive": "authored_room_composition",
            "last_operation": "duplicate_special",
            "last_duplicated_primitive": target,
        },
    )
    rooms = tuple(project.rooms[:index] + (updated,) + project.rooms[index + 1 :])
    return _replace_rooms(project, rooms, operation="duplicate_special")


def _unique_primitive_group_name(composition: AuthoredRoomComposition, requested_name: str = "") -> str:
    groups = tuple(dict(item) for item in tuple(dict(composition.metadata).get("combined_primitive_groups") or ()))
    used = {str(group.get("name") or "").strip() for group in groups if str(group.get("name") or "").strip()}
    base = str(requested_name or "").strip() or "combined_primitive_group"
    base = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in base)[:32] or "combined_primitive_group"
    if base not in used:
        return base
    for index in range(1, 1000):
        suffix = f"_{index:02d}"
        candidate = f"{base[: max(1, 32 - len(suffix))]}{suffix}"[:32]
        if candidate not in used:
            return candidate
    raise ValueError(f"Could not create a unique primitive group name for '{requested_name}'.")


def _primitive_name_values(primitive_names: Any) -> tuple[str, ...]:
    if primitive_names is None:
        return ()
    if isinstance(primitive_names, (str, bytes)):
        text = primitive_names.decode("utf-8", errors="ignore") if isinstance(primitive_names, bytes) else primitive_names
        values = [part.strip() for part in text.split(",") if part.strip()]
    else:
        values = [str(name or "").strip() for name in tuple(primitive_names or ()) if str(name or "").strip()]
    return tuple(dict.fromkeys(values))


def combine_authored_room_composition_primitives(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    primitive_names: Any,
    group_name: str = "",
) -> AuthoredModuleProject:
    """Record a combined object group for authored composition primitives.

    This is a KMAP object-boundary command, not arbitrary mesh baking.  It lets
    Map Studio preserve individual primitive topology while declaring that a
    selected set should be treated as one modular object for selection,
    readiness, DCC handoff, and later export policy.
    """

    selected_names = _primitive_name_values(primitive_names)
    if len(selected_names) < 2:
        raise ValueError("Combining authored primitives requires at least two primitive names.")
    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    composition = _composition_for_room(room)
    primitives = tuple(composition.primitives or ())
    by_name = {_primitive_name(primitive): primitive for primitive in primitives if _primitive_name(primitive)}
    missing = [name for name in selected_names if name not in by_name]
    if missing:
        known = ", ".join(sorted(by_name))
        raise ValueError(f"Room {room.room_resref} has no primitive named '{missing[0]}'. Known primitives: {known or '(none)'}.")
    selected = tuple(by_name[name] for name in selected_names)
    vertex_count = 0
    face_count = 0
    primitive_types: list[str] = []
    world_vertices: list[tuple[float, float, float]] = []
    for primitive in selected:
        mesh = primitive_to_mesh(primitive)
        vertex_count += len(tuple(mesh.vertices or ()))
        face_count += len(tuple(mesh.faces or ()))
        primitive_types.append(_primitive_type(primitive))
        world_vertices.extend(_primitive_world_vertices(room, primitive))
    bounds_min, bounds_max = _vec_bounds(tuple(world_vertices))
    center = _vec_center(bounds_min, bounds_max)
    dimensions = _vec_dimensions(bounds_min, bounds_max)
    group_id = _unique_primitive_group_name(composition, group_name)
    group_payload = {
        "name": group_id,
        "primitive_names": list(selected_names),
        "primitive_types": primitive_types,
        "operation": "combine_primitives",
        "coordinate_space": "authored_room_composition_mesh_space",
        "bounds_coordinate_space": "kmap_world",
        "bounds_min": [float(value) for value in bounds_min],
        "bounds_max": [float(value) for value in bounds_max],
        "center": [float(value) for value in center],
        "dimensions": [float(value) for value in dimensions],
        "topology_policy": "preserve_authored_primitives_no_mesh_bake",
        "baked_mesh_combine": "planned",
        "vertex_count": vertex_count,
        "face_count": face_count,
        "source": "map_studio:primitive_combine",
    }
    groups = [dict(item) for item in tuple(dict(composition.metadata).get("combined_primitive_groups") or ())]
    groups.append(group_payload)
    by_primitive = dict(dict(composition.metadata).get("combined_primitive_group_by_name") or {})
    for name in selected_names:
        by_primitive[name] = group_id
    updated_composition = replace(
        composition,
        metadata={
            **dict(composition.metadata),
            "last_operation": "combine_primitives",
            "last_combined_primitive_group": group_id,
            "combined_primitive_groups": groups,
            "combined_primitive_group_by_name": by_primitive,
            "combined_primitive_group_count": len(groups),
        },
    )
    updated = replace(
        room,
        primitive=updated_composition,
        composition=None,
        metadata={
            **dict(room.metadata),
            "primitive": "authored_room_composition",
            "last_operation": "combine_primitives",
            "last_combined_primitive_group": group_id,
            "combined_primitive_group_count": len(groups),
        },
    )
    rooms = tuple(project.rooms[:index] + (updated,) + project.rooms[index + 1 :])
    return _replace_rooms(project, rooms, operation="combine_primitives")


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


def apply_authored_floor_plan_edge_extrude(
    project: AuthoredModuleProject,
    *,
    edge_index: int,
    distance: float,
    room_resref: str = "",
) -> AuthoredModuleProject:
    """Pull one authored floor-plan edge outward and return updated project intent."""

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    primitive = apply_floor_plan_edge_extrude(
        _floor_plan_for_room(room),
        FloorPlanEdgeExtrudeOperation(
            edge_index=int(edge_index),
            distance=float(distance),
            room_resref=room.room_resref,
            metadata={"source": "map_studio:project_operation"},
        ),
    )
    updated = replace(
        room,
        primitive=primitive,
        composition=None,
        metadata={
            **dict(room.metadata),
            "last_operation": "edge_extrude",
            "edge_index": int(edge_index),
        },
    )
    rooms = tuple(project.rooms[:index] + (updated,) + project.rooms[index + 1 :])
    return _replace_rooms(project, rooms, operation="edge_extrude")


def _world_floor_plan_edge(
    room: AuthoredRoomSpec,
    primitive: FloorPlanRoomPrimitive,
    edge_index: int,
) -> tuple[tuple[float, float], tuple[float, float]]:
    points = tuple(primitive.points or ())
    if len(points) < 3:
        raise ValueError(f"Room {room.room_resref} needs at least three floor-plan points before bridging.")
    edge = int(edge_index)
    if edge < 0 or edge >= len(points):
        raise ValueError(f"Room {room.room_resref} has no floor-plan edge {edge_index}.")
    offset = _room_offset(room)
    start = points[edge]
    end = points[(edge + 1) % len(points)]
    return (
        (float(start[0]) + offset[0], float(start[1]) + offset[1]),
        (float(end[0]) + offset[0], float(end[1]) + offset[1]),
    )


def _require_bridge_compatible_floor_plans(
    first_room: AuthoredRoomSpec,
    first: FloorPlanRoomPrimitive,
    second_room: AuthoredRoomSpec,
    second: FloorPlanRoomPrimitive,
) -> float:
    first_position = _room_offset(first_room)
    second_position = _room_offset(second_room)
    first_world_z = first_position[2] + float(first.z)
    second_world_z = second_position[2] + float(second.z)
    if abs(first_world_z - second_world_z) > 1.0e-7:
        raise ValueError("Floor-plan bridge requires matching world floor elevations.")
    if abs(float(first.wall_height) - float(second.wall_height)) > 1.0e-7:
        raise ValueError("Floor-plan bridge requires matching wall heights.")
    if resolve_walkmesh_surface_id(first.floor_surface_id) != resolve_walkmesh_surface_id(second.floor_surface_id):
        raise ValueError("Floor-plan bridge requires matching WOK floor surface types.")
    if first.material != second.material:
        raise ValueError("Floor-plan bridge requires matching room materials.")
    if bool(first.include_walls) != bool(second.include_walls):
        raise ValueError("Floor-plan bridge requires matching wall generation settings.")
    return first_world_z


def _unique_bridge_resref(project: AuthoredModuleProject, first_room_resref: str, second_room_resref: str, requested: str = "") -> str:
    existing = {normalise_resref(room.room_resref) for room in tuple(project.rooms or ())}
    base = normalise_resref(requested)
    if not base:
        first = normalise_resref(first_room_resref) or "rooma"
        second = normalise_resref(second_room_resref) or "roomb"
        base = normalise_resref(f"{first[:6]}_{second[:6]}_br") or "bridge_room"
    if base not in existing:
        return base
    stem = base[:16]
    for index in range(1, 100):
        suffix = f"_{index}"
        candidate = f"{stem[: max(1, 16 - len(suffix))]}{suffix}"[:16]
        if candidate not in existing:
            return candidate
    raise ValueError(f"Could not create a unique bridge room resref from '{base}'.")


def _bridge_floor_plan_points(
    first_edge: tuple[tuple[float, float], tuple[float, float]],
    second_edge: tuple[tuple[float, float], tuple[float, float]],
) -> tuple[tuple[tuple[float, float], ...], ComponentEditResult]:
    a0, a1 = first_edge
    b0, b1 = second_edge
    mesh = component_mesh(
        ((a0[0], a0[1], 0.0), (a1[0], a1[1], 0.0), (b0[0], b0[1], 0.0), (b1[0], b1[1], 0.0)),
        metadata={"source": "floor_plan_bridge"},
    )
    blocking_messages: list[str] = []
    for flip_second in (True, False):
        result = bridge_edges(mesh, (0, 1), (2, 3), flip_second=flip_second)
        face = result.mesh.faces[-1]
        points = tuple((float(result.mesh.vertices[index][0]), float(result.mesh.vertices[index][1])) for index in face)
        candidate = FloorPlanRoomPrimitive(room_resref="bridge_preview", points=tuple(points))
        validation = validate_floor_plan_room_primitive(candidate)
        if validation.ok and abs(float(validation.area)) > 1.0e-7:
            return (tuple((float(x), float(y)) for x, y in points), result)
        blocking_messages.extend(str(item) for item in validation.blocking_issues)
    detail = f" {' '.join(blocking_messages)}" if blocking_messages else ""
    raise ValueError(f"Bridge edges do not form one valid convex connector room.{detail}")


def bridge_authored_floor_plan_edges(
    project: AuthoredModuleProject,
    *,
    first_room_resref: str,
    first_edge_index: int,
    second_room_resref: str,
    second_edge_index: int,
    result_room_resref: str = "",
) -> AuthoredModuleProject:
    """Create an exportable connector room between two compatible floor-plan edges."""

    first_index = _target_room_index(project, first_room_resref)
    second_index = _target_room_index(project, second_room_resref)
    if first_index == second_index:
        raise ValueError("Floor-plan bridge requires two different rooms.")
    first_room = project.rooms[first_index]
    second_room = project.rooms[second_index]
    first_primitive = _floor_plan_for_room(first_room)
    second_primitive = _floor_plan_for_room(second_room)
    world_z = _require_bridge_compatible_floor_plans(first_room, first_primitive, second_room, second_primitive)
    first_edge = _world_floor_plan_edge(first_room, first_primitive, int(first_edge_index))
    second_edge = _world_floor_plan_edge(second_room, second_primitive, int(second_edge_index))
    points, bridge_result = _bridge_floor_plan_points(first_edge, second_edge)
    audit = audit_component_edit_result(bridge_result, component_kind="floor_plan_edge", affects_walkmesh=True)
    target_resref = _unique_bridge_resref(project, first_room.room_resref, second_room.room_resref, result_room_resref)
    primitive = FloorPlanRoomPrimitive(
        room_resref=target_resref,
        points=points,
        z=world_z,
        wall_height=first_primitive.wall_height,
        floor_surface_id=first_primitive.floor_surface_id,
        material=first_primitive.material,
        include_walls=first_primitive.include_walls,
        openings=(),
        metadata={
            **dict(first_primitive.metadata),
            "operation": "bridge_edges",
            "source": "map_studio:floor_plan_bridge",
            "first_room_resref": normalise_resref(first_room.room_resref),
            "first_edge_index": int(first_edge_index),
            "second_room_resref": normalise_resref(second_room.room_resref),
            "second_edge_index": int(second_edge_index),
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )
    connector_room = AuthoredRoomSpec(
        room_resref=target_resref,
        primitive=primitive,
        composition=None,
        position=(0.0, 0.0, 0.0),
        visible_rooms=(),
        metadata={
            "primitive": "floor_plan_extrusion",
            "last_operation": "bridge_edges",
            "bridge_first_room": normalise_resref(first_room.room_resref),
            "bridge_second_room": normalise_resref(second_room.room_resref),
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )
    rooms = tuple(project.rooms or ()) + (connector_room,)
    visible = _all_room_names(rooms)
    rooms = tuple(replace(room, visible_rooms=visible) for room in rooms)
    return _replace_rooms(project, rooms, operation="bridge_edges")


def set_authored_floor_plan_extrusion_settings(
    project: AuthoredModuleProject,
    *,
    room_resref: str = "",
    z: float | None = None,
    wall_height: float | None = None,
    include_walls: bool | None = None,
    floor_surface_id: int | str | None = None,
) -> AuthoredModuleProject:
    """Set the explicit extrusion parameters for one authored floor-plan room."""

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    primitive = _floor_plan_for_room(room)
    next_z = float(primitive.z if z is None else z)
    next_wall_height = float(primitive.wall_height if wall_height is None else wall_height)
    if not math.isfinite(next_z):
        raise ValueError("Floor-plan extrusion elevation must be a finite number.")
    if not math.isfinite(next_wall_height) or next_wall_height <= 0.0:
        raise ValueError("Floor-plan extrusion wall height must be greater than zero.")
    next_surface_id = primitive.floor_surface_id
    if floor_surface_id is not None and str(floor_surface_id).strip():
        next_surface_id = resolve_walkmesh_surface_id(floor_surface_id)
    updated_primitive = replace(
        primitive,
        z=next_z,
        wall_height=next_wall_height,
        include_walls=bool(primitive.include_walls if include_walls is None else include_walls),
        floor_surface_id=next_surface_id,
        metadata={
            **dict(primitive.metadata),
            "source": "map_studio:floor_plan_extrusion_settings",
            "last_operation": "floor_plan_extrusion_settings",
        },
    )
    updated = replace(
        room,
        primitive=updated_primitive,
        composition=None,
        metadata={
            **dict(room.metadata),
            "primitive": "floor_plan_extrusion",
            "last_operation": "floor_plan_extrusion_settings",
        },
    )
    rooms = tuple(project.rooms[:index] + (updated,) + project.rooms[index + 1 :])
    return _replace_rooms(project, rooms, operation="floor_plan_extrusion_settings")


def _safe_anchor_for_piece(piece: FloorPlanRoomPrimitive) -> tuple[float, float, float]:
    xs = [float(point[0]) for point in piece.points]
    ys = [float(point[1]) for point in piece.points]
    return ((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, float(piece.z))


def _offset_anchor(anchor: tuple[float, float, float], dx: float, dy: float) -> tuple[float, float, float]:
    return (anchor[0] + float(dx), anchor[1] + float(dy), anchor[2])


def _placements_for_floor_plan_piece(
    project: AuthoredModuleProject,
    first_piece: FloorPlanRoomPrimitive,
    *,
    operation: str,
) -> AuthoredGameplayPlacement:
    anchor = _safe_anchor_for_piece(first_piece)
    return replace(
        project.placements,
        entry_point=replace(project.placements.entry_point, position=anchor),
        placeables=tuple(replace(item, position=_offset_anchor(anchor, 0.5, 0.5)) for item in project.placements.placeables),
        waypoints=tuple(replace(item, position=anchor) for item in project.placements.waypoints),
        metadata={
            **dict(project.placements.metadata),
            "last_room_operation": operation,
            f"placement_repaired_after_{operation}": True,
        },
    )


def _placements_for_cut(project: AuthoredModuleProject, first_piece: FloorPlanRoomPrimitive) -> AuthoredGameplayPlacement:
    return _placements_for_floor_plan_piece(project, first_piece, operation="rectangular_cut")


def _terrain_room_position(room: AuthoredRoomSpec) -> tuple[float, float, float]:
    position = tuple(room.position or (0.0, 0.0, 0.0))
    if len(position) < 3:
        return (0.0, 0.0, 0.0)
    return (float(position[0]), float(position[1]), float(position[2]))


def _snap_position_to_terrain(
    terrain: TerrainHeightfieldPrimitive,
    room_position: tuple[float, float, float],
    position: Any,
) -> tuple[float, float, float]:
    source = tuple(position or (0.0, 0.0, 0.0))
    if len(source) < 3:
        source = (0.0, 0.0, 0.0)
    x = float(source[0])
    y = float(source[1])
    local_x = x - room_position[0]
    local_y = y - room_position[1]
    z = room_position[2] + sample_terrain_height(terrain, x=local_x, y=local_y)
    return (x, y, z)


def _repair_placements_for_terrain(
    placements: AuthoredGameplayPlacement,
    *,
    terrain: TerrainHeightfieldPrimitive,
    room: AuthoredRoomSpec,
    operation: str,
) -> AuthoredGameplayPlacement:
    room_position = _terrain_room_position(room)
    snap = lambda position: _snap_position_to_terrain(terrain, room_position, position)
    return replace(
        placements,
        entry_point=replace(placements.entry_point, position=snap(placements.entry_point.position)),
        creatures=tuple(replace(item, position=snap(item.position)) for item in placements.creatures),
        doors=tuple(replace(item, position=snap(item.position)) for item in placements.doors),
        triggers=tuple(replace(item, position=snap(item.position)) for item in placements.triggers),
        encounters=tuple(replace(item, position=snap(item.position)) for item in placements.encounters),
        sounds=tuple(replace(item, position=snap(item.position)) for item in placements.sounds),
        placeables=tuple(replace(item, position=snap(item.position)) for item in placements.placeables),
        waypoints=tuple(replace(item, position=snap(item.position)) for item in placements.waypoints),
        metadata={
            **dict(placements.metadata),
            "terrain_height_repaired_after_operation": operation,
        },
    )


def _target_terrain_room_index(project: AuthoredModuleProject, room_resref: str = "") -> int:
    target = normalise_resref(room_resref)
    if target:
        index = _target_room_index(project, target)
        _terrain_for_room(project.rooms[index])
        return index
    for index, room in enumerate(tuple(project.rooms or ())):
        try:
            _terrain_for_room(room)
        except ValueError:
            continue
        return index
    raise ValueError("Shrink Wrap needs an authored terrain heightfield room.")


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


def _floor_plan_rect_bounds(primitive: FloorPlanRoomPrimitive) -> tuple[float, float, float, float]:
    points = tuple(primitive.points or ())
    if len(points) != 4:
        raise ValueError("Boolean Difference currently requires axis-aligned rectangular floor-plan rooms.")
    xs = sorted({round(float(point[0]), 9) for point in points})
    ys = sorted({round(float(point[1]), 9) for point in points})
    if len(xs) != 2 or len(ys) != 2:
        raise ValueError("Boolean Difference currently requires axis-aligned rectangular floor-plan rooms.")
    expected = {(xs[0], ys[0]), (xs[1], ys[0]), (xs[1], ys[1]), (xs[0], ys[1])}
    actual = {(round(float(x), 9), round(float(y), 9)) for x, y in points}
    if actual != expected:
        raise ValueError("Boolean Difference currently requires axis-aligned rectangular floor-plan rooms.")
    return (xs[0], ys[0], xs[1], ys[1])


def _room_position_3(room: AuthoredRoomSpec) -> tuple[float, float, float]:
    position = tuple(room.position or (0.0, 0.0, 0.0))
    if len(position) < 3:
        return (0.0, 0.0, 0.0)
    return (float(position[0]), float(position[1]), float(position[2]))


def _floor_plan_world_rect_bounds(
    room: AuthoredRoomSpec,
    primitive: FloorPlanRoomPrimitive,
) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = _floor_plan_rect_bounds(primitive)
    px, py, _pz = _room_position_3(room)
    return (x0 + px, y0 + py, x1 + px, y1 + py)


def _boolean_cut_from_room_bounds(
    *,
    minuend_room: AuthoredRoomSpec,
    minuend: FloorPlanRoomPrimitive,
    cutter_room: AuthoredRoomSpec,
    cutter: FloorPlanRoomPrimitive,
) -> tuple[tuple[float, float], tuple[float, float]]:
    minuend_z = _room_position_3(minuend_room)[2] + float(minuend.z)
    cutter_z = _room_position_3(cutter_room)[2] + float(cutter.z)
    if abs(minuend_z - cutter_z) > 1.0e-7:
        raise ValueError("Boolean Difference requires floor-plan rooms on the same floor plane.")
    cx0, cy0, cx1, cy1 = _floor_plan_world_rect_bounds(cutter_room, cutter)
    mx, my, _mz = _room_position_3(minuend_room)
    local_x0 = cx0 - mx
    local_x1 = cx1 - mx
    local_y0 = cy0 - my
    local_y1 = cy1 - my
    return (
        ((local_x0 + local_x1) * 0.5, (local_y0 + local_y1) * 0.5),
        (max(local_x1 - local_x0, 0.0), max(local_y1 - local_y0, 0.0)),
    )


def apply_authored_floor_plan_boolean_difference(
    project: AuthoredModuleProject,
    *,
    first_room_resref: str,
    second_room_resref: str,
    result_room_resref: str = "",
) -> AuthoredModuleProject:
    """Subtract the second rectangular floor-plan room from the first room.

    This first-pass boolean consumes the cutter operand and emits the remaining
    A-B pieces as separate rectangular room/export boundaries.  That keeps MDL
    and WOK output deterministic while arbitrary mesh booleans remain planned.
    """

    first_index = _target_room_index(project, first_room_resref)
    second_index = _target_room_index(project, second_room_resref)
    if first_index == second_index:
        raise ValueError("Boolean Difference requires two different floor-plan rooms.")
    first_room = project.rooms[first_index]
    second_room = project.rooms[second_index]
    first_primitive = _floor_plan_for_room(first_room)
    second_primitive = _floor_plan_for_room(second_room)
    center, size = _boolean_cut_from_room_bounds(
        minuend_room=first_room,
        minuend=first_primitive,
        cutter_room=second_room,
        cutter=second_primitive,
    )
    prefix = normalise_resref(result_room_resref) or normalise_resref(
        f"{normalise_resref(first_room.room_resref)}_minus_{normalise_resref(second_room.room_resref)}"
    )
    pieces = apply_floor_plan_rectangular_cut(
        first_primitive,
        FloorPlanRectangularCutOperation(
            center=center,
            size=size,
            room_resref_prefix=prefix,
            metadata={
                "source": "map_studio:project_operation",
                "operation": "boolean_difference",
                "boolean_minuend_room_resref": normalise_resref(first_room.room_resref),
                "boolean_cutter_room_resref": normalise_resref(second_room.room_resref),
                "boolean_cutter_consumed": True,
            },
        ),
    )
    piece_rooms = tuple(
        replace(
            first_room,
            room_resref=piece.room_resref,
            primitive=piece,
            composition=None,
            visible_rooms=(),
            metadata={
                **dict(first_room.metadata),
                "last_operation": "boolean_difference",
                "boolean_minuend_room_resref": normalise_resref(first_room.room_resref),
                "boolean_cutter_room_resref": normalise_resref(second_room.room_resref),
                "boolean_cutter_consumed": True,
                "cut_piece_role": piece.metadata.get("piece_role", ""),
            },
        )
        for piece in pieces
    )
    rooms: list[AuthoredRoomSpec] = []
    for index, room in enumerate(project.rooms):
        if index == first_index:
            rooms.extend(piece_rooms)
        elif index == second_index:
            continue
        else:
            rooms.append(room)
    room_tuple = tuple(rooms)
    visible = _all_room_names(room_tuple)
    room_tuple = tuple(replace(item, visible_rooms=visible) for item in room_tuple)
    return _replace_rooms(
        project,
        room_tuple,
        operation="boolean_difference",
        placements=_placements_for_floor_plan_piece(project, pieces[0], operation="boolean_difference"),
    )


def apply_authored_floor_plan_axis_split(
    project: AuthoredModuleProject,
    *,
    axis: str,
    coordinate: float,
    room_resref: str = "",
    room_resref_prefix: str | None = None,
) -> AuthoredModuleProject:
    """Split a rectangular floor-plan room into two exportable KOTOR rooms."""

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    primitive = _floor_plan_for_room(room)
    prefix = room_resref_prefix or f"{normalise_resref(room.room_resref)}_split"
    pieces = apply_floor_plan_axis_split(
        primitive,
        FloorPlanAxisSplitOperation(
            axis=axis,
            coordinate=float(coordinate),
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
                "last_operation": "axis_split",
                "split_axis": piece.metadata.get("split_axis", ""),
                "split_coordinate": piece.metadata.get("split_coordinate", 0.0),
                "split_piece_role": piece.metadata.get("piece_role", ""),
            },
        )
        for piece in pieces
    )
    rooms = tuple(project.rooms[:index] + piece_rooms + project.rooms[index + 1 :])
    visible = _all_room_names(rooms)
    rooms = tuple(replace(item, visible_rooms=visible) for item in rooms)
    return _replace_rooms(
        project,
        rooms,
        operation="axis_split",
        placements=_placements_for_floor_plan_piece(project, pieces[0], operation="axis_split"),
    )


def set_authored_floor_plan_wall_opening(
    project: AuthoredModuleProject,
    *,
    room_resref: str = "",
    name: str = "",
    edge_index: int = 0,
    center_fraction: float = 0.5,
    width: float = 1.5,
    height: float = 2.1,
    bottom: float = 0.0,
) -> AuthoredModuleProject:
    """Add or replace one wall opening on a floor-plan room edge."""

    room_index = _target_room_index(project, room_resref)
    room = project.rooms[room_index]
    primitive = _floor_plan_for_room(room)
    edge = int(edge_index)
    points = tuple(primitive.points or ())
    if edge < 0 or edge >= len(points):
        raise ValueError(f"Floor-plan wall opening edge {edge_index} does not exist in room {room.room_resref}.")
    center = float(center_fraction)
    opening_width = float(width)
    opening_height = float(height)
    opening_bottom = float(bottom)
    if not all(math.isfinite(value) for value in (center, opening_width, opening_height, opening_bottom)):
        raise ValueError("Floor-plan wall opening values must be finite.")
    opening_name = str(name or "").strip() or f"opening_edge_{edge}"
    opening = FloorPlanWallOpening(
        name=opening_name,
        edge_index=edge,
        center_fraction=center,
        width=opening_width,
        height=opening_height,
        bottom=opening_bottom,
        metadata={
            "source": "map_studio:wall_opening",
            "operation": "set_wall_opening",
        },
    )
    openings = tuple(item for item in tuple(primitive.openings or ()) if int(item.edge_index) != edge and str(item.name or "").strip() != opening_name)
    updated_primitive = replace(
        primitive,
        openings=openings + (opening,),
        include_walls=True,
        metadata={
            **dict(primitive.metadata),
            "last_operation": "set_wall_opening",
            "last_opening_name": opening_name,
            "last_opening_edge_index": edge,
        },
    )
    return _replace_floor_plan_room(
        project,
        room_index,
        updated_primitive,
        operation="set_wall_opening",
        room_metadata={
            "last_opening_name": opening_name,
            "last_opening_edge_index": edge,
        },
    )


def _find_floor_plan_wall_opening(
    primitive: FloorPlanRoomPrimitive,
    *,
    opening_name: str = "",
    edge_index: int | None = None,
) -> FloorPlanWallOpening:
    openings = tuple(primitive.openings or ())
    if not openings:
        raise ValueError(f"Room {primitive.room_resref} has no authored wall openings yet.")
    target_name = str(opening_name or "").strip()
    if target_name:
        for opening in openings:
            if str(opening.name or "").strip() == target_name:
                return opening
        raise ValueError(f"Room {primitive.room_resref} has no wall opening named '{target_name}'.")
    if edge_index is not None:
        edge = int(edge_index)
        for opening in openings:
            if int(opening.edge_index) == edge:
                return opening
        raise ValueError(f"Room {primitive.room_resref} has no wall opening on edge {edge}.")
    return openings[0]


def _floor_plan_wall_opening_marker_pose(
    room: AuthoredRoomSpec,
    primitive: FloorPlanRoomPrimitive,
    opening: FloorPlanWallOpening,
) -> tuple[tuple[float, float, float], float]:
    points = tuple(primitive.points or ())
    edge = int(opening.edge_index)
    if edge < 0 or edge >= len(points):
        raise ValueError(f"Opening {opening.name or edge} references missing wall edge {edge}.")
    start = points[edge]
    end = points[(edge + 1) % len(points)]
    fraction = float(opening.center_fraction)
    room_offset = _room_offset(room)
    x = float(start[0]) + ((float(end[0]) - float(start[0])) * fraction) + room_offset[0]
    y = float(start[1]) + ((float(end[1]) - float(start[1])) * fraction) + room_offset[1]
    z = float(primitive.z) + float(opening.bottom) + room_offset[2]
    bearing = math.atan2(float(end[1]) - float(start[1]), float(end[0]) - float(start[0]))
    return (x, y, z), bearing


def add_authored_floor_plan_opening_transition_marker(
    project: AuthoredModuleProject,
    *,
    room_resref: str = "",
    opening_name: str = "",
    edge_index: int | None = None,
    marker_kind: str = "door",
    template_resref: str = "",
    tag: str = "",
    linked_to: str = "",
    linked_to_module: str = "",
    transition_destination: int = 0,
) -> AuthoredModuleProject:
    """Create a KOTOR door/trigger/waypoint marker from a wall opening."""

    room_index = _target_room_index(project, room_resref)
    room = project.rooms[room_index]
    primitive = _floor_plan_for_room(room)
    opening = _find_floor_plan_wall_opening(primitive, opening_name=opening_name, edge_index=edge_index)
    kind = str(marker_kind or "door").strip().lower()
    if kind not in {"door", "trigger", "waypoint"}:
        raise ValueError("Opening transition markers must be authored as a door, trigger, or waypoint.")
    position, bearing = _floor_plan_wall_opening_marker_pose(room, primitive, opening)
    opening_label = str(opening.name or "").strip() or f"edge_{int(opening.edge_index)}"
    placement_tag = str(tag or "").strip() or f"{normalise_resref(opening_label)}_{kind}"
    update = add_authored_gameplay_placement(
        project,
        kind=kind,
        template_resref=template_resref,
        tag=placement_tag,
        position=position,
        bearing=bearing,
        linked_to=linked_to,
        linked_to_module=linked_to_module,
        trigger_size=max(float(opening.width), 0.5),
    )
    try:
        destination = int(transition_destination or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("Opening transition marker destination must be an integer.") from exc
    updated_project = update.project
    if destination or str(linked_to or "").strip() or str(linked_to_module or "").strip():
        updated_project = update_authored_gameplay_transition(
            updated_project,
            update.placement_id,
            linked_to=linked_to,
            linked_to_module=linked_to_module,
            transition_destination=destination,
        ).project
    metadata = {
        "room_resref": normalise_resref(room.room_resref),
        "opening_name": opening_label,
        "edge_index": int(opening.edge_index),
        "marker_kind": update.kind,
        "template_resref": update.template_resref,
        "tag": update.tag,
        "placement_id": str(update.placement_id),
        "position": [float(position[0]), float(position[1]), float(position[2])],
        "bearing": float(bearing),
        "linked_to": str(linked_to or "").strip(),
        "linked_to_module": normalise_resref(linked_to_module),
        "transition_destination": destination,
        "source": "map_studio:opening_transition_marker",
    }
    placements = replace(
        updated_project.placements,
        metadata={
            **dict(updated_project.placements.metadata),
            "last_opening_transition_marker": metadata,
        },
    )
    return replace(
        updated_project,
        placements=placements,
        notes=tuple(updated_project.notes)
        + (
            f"Created Map Studio {update.kind} marker {update.tag} from opening {opening_label}.",
        ),
        extra={
            **dict(updated_project.extra),
            "last_opening_transition_marker": metadata,
            "last_room_operation": "opening_transition_marker",
        },
    )


def apply_authored_floor_plan_rectangular_union(
    project: AuthoredModuleProject,
    *,
    first_room_resref: str,
    second_room_resref: str,
    result_room_resref: str = "",
) -> AuthoredModuleProject:
    """Union two compatible rectangular floor-plan rooms into one room."""

    first_index = _target_room_index(project, first_room_resref)
    second_index = _target_room_index(project, second_room_resref)
    if first_index == second_index:
        raise ValueError("Floor-plan rectangular union requires two different rooms.")
    first_room = project.rooms[first_index]
    second_room = project.rooms[second_index]
    first_position = tuple(first_room.position or (0.0, 0.0, 0.0))
    second_position = tuple(second_room.position or (0.0, 0.0, 0.0))
    if len(first_position) < 3:
        first_position = (0.0, 0.0, 0.0)
    if len(second_position) < 3:
        second_position = (0.0, 0.0, 0.0)
    if any(abs(float(a) - float(b)) > 1.0e-7 for a, b in zip(first_position[:3], second_position[:3])):
        raise ValueError("Floor-plan rectangular union requires rooms with matching room positions.")
    target_resref = normalise_resref(result_room_resref) or normalise_resref(first_room.room_resref)
    remaining_resrefs = {
        normalise_resref(room.room_resref)
        for index, room in enumerate(project.rooms)
        if index not in {first_index, second_index}
    }
    if target_resref in remaining_resrefs:
        raise ValueError(f"Floor-plan rectangular union result room resref '{target_resref}' already exists.")
    merged = apply_floor_plan_rectangular_union(
        _floor_plan_for_room(first_room),
        _floor_plan_for_room(second_room),
        FloorPlanRectangularUnionOperation(
            room_resref=target_resref,
            metadata={
                "source": "map_studio:project_operation",
                "operation": "rectangular_union",
            },
        ),
    )
    updated_room = replace(
        first_room,
        room_resref=merged.room_resref,
        primitive=merged,
        composition=None,
        visible_rooms=(),
        metadata={
            **dict(first_room.metadata),
            "last_operation": "rectangular_union",
            "merged_room_resrefs": [normalise_resref(first_room.room_resref), normalise_resref(second_room.room_resref)],
        },
    )
    rooms: list[AuthoredRoomSpec] = []
    for index, room in enumerate(project.rooms):
        if index == first_index:
            rooms.append(updated_room)
        elif index == second_index:
            continue
        else:
            rooms.append(room)
    room_tuple = tuple(rooms)
    visible = _all_room_names(room_tuple)
    room_tuple = tuple(replace(item, visible_rooms=visible) for item in room_tuple)
    return _replace_rooms(project, room_tuple, operation="rectangular_union")


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


def authored_floor_plan_vertex_snap_candidates(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    point_index: int,
    max_distance: float | None = None,
    include_same_room: bool = True,
    include_cross_room: bool = True,
    limit: int = 8,
) -> tuple[AuthoredFloorPlanVertexSnapCandidate, ...]:
    """Return nearest snap targets for one authored floor-plan vertex.

    This query is intentionally non-mutating so viewport Hold-V snapping can
    preview a target before committing a move/snap operation into the KMAP.
    """

    source_room_index = _target_room_index(project, room_resref)
    source_room = project.rooms[source_room_index]
    source_primitive = _floor_plan_for_room(source_room)
    source_points = tuple(source_primitive.points or ())
    source_vertex_index = int(point_index)
    if source_vertex_index < 0 or source_vertex_index >= len(source_points):
        raise ValueError(f"Room {source_room.room_resref} has no outline point {point_index}.")

    max_results = int(limit)
    if max_results <= 0:
        return ()
    distance_limit = None if max_distance is None else float(max_distance)
    if distance_limit is not None and distance_limit < 0:
        raise ValueError("Floor-plan vertex snap max_distance must be zero or greater.")

    source_world = _floor_plan_point_world_position(source_room, source_primitive, source_points[source_vertex_index])
    candidates: list[AuthoredFloorPlanVertexSnapCandidate] = []
    for candidate_room_index, candidate_room in enumerate(tuple(project.rooms or ())):
        try:
            candidate_primitive = _floor_plan_for_room(candidate_room)
        except ValueError:
            continue
        same_room = candidate_room_index == source_room_index
        if same_room and not include_same_room:
            continue
        if not same_room and not include_cross_room:
            continue
        candidate_resref = normalise_resref(candidate_room.room_resref)
        for candidate_point_index, candidate_point in enumerate(tuple(candidate_primitive.points or ())):
            if same_room and candidate_point_index == source_vertex_index:
                continue
            world_position = _floor_plan_point_world_position(candidate_room, candidate_primitive, candidate_point)
            distance = math.sqrt(
                (world_position[0] - source_world[0]) ** 2
                + (world_position[1] - source_world[1]) ** 2
                + (world_position[2] - source_world[2]) ** 2
            )
            if distance_limit is not None and distance > distance_limit:
                continue
            candidates.append(
                AuthoredFloorPlanVertexSnapCandidate(
                    room_resref=candidate_resref,
                    point_index=int(candidate_point_index),
                    world_position=world_position,
                    distance=float(distance),
                    same_room=bool(same_room),
                    label=f"{candidate_resref} point {candidate_point_index} ({distance:.3f} m)",
                )
            )
    candidates.sort(key=lambda item: (item.distance, item.room_resref, item.point_index))
    return tuple(candidates[:max_results])


def snap_authored_floor_plan_vertex_to_vertex(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    point_index: int,
    target_point_index: int,
    target_room_resref: str = "",
) -> AuthoredModuleProject:
    """Snap one authored floor-plan vertex exactly onto another vertex.

    The target may live in the same room or another authored room.  Cross-room
    snapping is stored in the source room's local coordinates so the KMAP room
    transform remains the source of truth.
    """

    source_room_index = _target_room_index(project, room_resref)
    source_room = project.rooms[source_room_index]
    source_primitive = _floor_plan_for_room(source_room)
    source_points = tuple(source_primitive.points or ())
    source_vertex_index = int(point_index)
    if source_vertex_index < 0 or source_vertex_index >= len(source_points):
        raise ValueError(f"Room {source_room.room_resref} has no outline point {point_index}.")

    target_room_index = _target_room_index(project, target_room_resref or room_resref)
    target_room = project.rooms[target_room_index]
    target_primitive = _floor_plan_for_room(target_room)
    target_points = tuple(target_primitive.points or ())
    target_vertex_index = int(target_point_index)
    if target_vertex_index < 0 or target_vertex_index >= len(target_points):
        raise ValueError(f"Room {target_room.room_resref} has no outline point {target_point_index}.")

    if source_room_index == target_room_index:
        result = snap_vertex_to_vertex(_floor_plan_component_mesh(source_primitive), source_vertex_index, target_vertex_index)
        updated_points = _floor_plan_points_from_component_vertices(result.mesh.vertices)
    else:
        source_offset = _room_offset(source_room)
        target_offset = _room_offset(target_room)
        target_x, target_y = target_points[target_vertex_index]
        target_world = (float(target_x) + target_offset[0], float(target_y) + target_offset[1])
        updated_points_list = list(source_points)
        updated_points_list[source_vertex_index] = (target_world[0] - source_offset[0], target_world[1] - source_offset[1])
        updated_points = tuple((float(x), float(y)) for x, y in updated_points_list)
        result = ComponentEditResult(
            mesh=_floor_plan_component_mesh(replace(source_primitive, points=updated_points)),
            changed_vertex_count=1,
            metadata={"operation": "snap_floor_plan_vertex", "source_index": source_vertex_index, "target_index": target_vertex_index},
        )
    audit = audit_component_edit_result(result, component_kind="floor_plan_vertex", affects_walkmesh=True)

    updated_primitive = replace(
        source_primitive,
        points=updated_points,
        metadata={
            **dict(source_primitive.metadata),
            "last_operation": "snap_floor_plan_vertex",
            "last_vertex_edit": source_vertex_index,
            "snap_target_room": normalise_resref(target_room.room_resref),
            "snap_target_index": target_vertex_index,
            "source": "map_studio:floor_plan_vertex_snap",
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )
    return _replace_floor_plan_room(
        project,
        source_room_index,
        updated_primitive,
        operation="snap_floor_plan_vertex",
        room_metadata={
            "last_vertex_edit": source_vertex_index,
            "snap_target_room": normalise_resref(target_room.room_resref),
            "snap_target_index": target_vertex_index,
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )


def grid_snap_authored_floor_plan_vertices(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    point_indices: tuple[int, ...] | list[int],
    grid_size: float = 0.1,
    axes: tuple[str, ...] | list[str] = ("x", "y"),
) -> AuthoredModuleProject:
    """Snap selected floor-plan vertices to the authored Map Studio grid.

    Floor-plan vertices are authored in local X/Y room space, so this command
    intentionally ignores Z even if a caller passes it.  Welding remains a
    separate topology-changing operation.
    """

    room_index = _target_room_index(project, room_resref)
    room = project.rooms[room_index]
    primitive = _floor_plan_for_room(room)
    selected = tuple(dict.fromkeys(int(index) for index in point_indices))
    if len(selected) < 1:
        raise ValueError("Grid snap requires at least one floor-plan point index.")
    safe_grid = float(grid_size)
    if safe_grid <= 0:
        raise ValueError("Grid snap size must be greater than zero.")
    axes_tuple = tuple(str(axis or "").strip().lower() for axis in tuple(axes or ("x", "y")))
    axes_xy = tuple(axis for axis in axes_tuple if axis in {"x", "y"}) or ("x", "y")
    result = snap_vertices_to_grid(
        _floor_plan_component_mesh(primitive),
        selected,
        grid_size=safe_grid,
        axes=axes_xy,
    )
    audit = audit_component_edit_result(result, component_kind="floor_plan_vertex", affects_walkmesh=True)
    updated_primitive = replace(
        primitive,
        points=_floor_plan_points_from_component_vertices(result.mesh.vertices),
        metadata={
            **dict(primitive.metadata),
            "last_operation": "grid_snap_floor_plan_vertices",
            "grid_snap_vertices": list(selected),
            "grid_snap_size": safe_grid,
            "grid_snap_axes": list(axes_xy),
            "source": "map_studio:floor_plan_grid_snap",
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )
    return _replace_floor_plan_room(
        project,
        room_index,
        updated_primitive,
        operation="grid_snap_floor_plan_vertices",
        room_metadata={
            "grid_snap_vertices": list(selected),
            "grid_snap_size": safe_grid,
            "grid_snap_axes": list(axes_xy),
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )


def weld_authored_floor_plan_vertices(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    point_indices: tuple[int, ...] | list[int],
    target_point_index: int | None = None,
    position_policy: str = "target",
) -> AuthoredModuleProject:
    """Weld selected floor-plan vertices into one KOTOR-safe footprint point."""

    room_index = _target_room_index(project, room_resref)
    room = project.rooms[room_index]
    primitive = _floor_plan_for_room(room)
    selected = tuple(dict.fromkeys(int(index) for index in point_indices))
    if len(selected) < 2:
        raise ValueError("Weld floor-plan vertices requires at least two point indices.")
    result = weld_vertices(
        _floor_plan_component_mesh(primitive),
        selected,
        target_index=target_point_index,
        position_policy=str(position_policy or "target").strip().lower() or "target",
    )
    audit = audit_component_edit_result(result, component_kind="floor_plan_vertex", affects_walkmesh=True)
    updated_points = _floor_plan_points_from_component_vertices(result.mesh.vertices)
    if len(updated_points) < 3:
        raise ValueError("Weld floor-plan vertices would leave fewer than three footprint points.")
    updated_primitive = replace(
        primitive,
        points=updated_points,
        metadata={
            **dict(primitive.metadata),
            "last_operation": "weld_floor_plan_vertices",
            "welded_vertices": list(selected),
            "weld_policy": str(position_policy or "target").strip().lower() or "target",
            "source": "map_studio:floor_plan_vertex_weld",
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )
    return _replace_floor_plan_room(
        project,
        room_index,
        updated_primitive,
        operation="weld_floor_plan_vertices",
        room_metadata={"welded_vertices": list(selected), "last_component_edit_audit": _component_edit_audit_payload(audit)},
    )


def flatten_authored_floor_plan_vertices(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    point_indices: tuple[int, ...] | list[int],
    axis: str = "x",
    value: float | None = None,
) -> AuthoredModuleProject:
    """Flatten selected floor-plan vertices along the local X or Y axis."""

    room_index = _target_room_index(project, room_resref)
    room = project.rooms[room_index]
    primitive = _floor_plan_for_room(room)
    selected = tuple(dict.fromkeys(int(index) for index in point_indices))
    if len(selected) < 1:
        raise ValueError("Flatten floor-plan vertices requires at least one point index.")
    axis_key = str(axis or "x").strip().lower()
    if axis_key not in {"x", "y"}:
        raise ValueError("Floor-plan vertex flattening supports local X or Y only; use extrusion controls for floor Z.")
    result = flatten_vertices(
        _floor_plan_component_mesh(primitive),
        selected,
        axis=axis_key,
        value=value,
    )
    updated_primitive = replace(
        primitive,
        points=_floor_plan_points_from_component_vertices(result.mesh.vertices),
        metadata={
            **dict(primitive.metadata),
            "last_operation": "flatten_floor_plan_vertices",
            "flattened_vertices": list(selected),
            "flatten_axis": axis_key,
            "flatten_value": result.metadata.get("value"),
            "source": "map_studio:floor_plan_vertex_flatten",
        },
    )
    return _replace_floor_plan_room(
        project,
        room_index,
        updated_primitive,
        operation="flatten_floor_plan_vertices",
        room_metadata={"flattened_vertices": list(selected), "flatten_axis": axis_key},
    )


def transform_snap_authored_floor_plan_vertices(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    point_indices: tuple[int, ...] | list[int],
    axis: str = "x",
    target_point_index: int | None = None,
    value: float | None = None,
    level_policy: str = "average",
) -> AuthoredModuleProject:
    """Apply Maya-style hold-J level snapping to floor-plan vertices.

    This is intentionally distinct from generic flattening so KMAP metadata,
    undo labels, readiness reports, and future direct-manipulation UI can tell
    that the user performed a transform snapping gesture. Current floor-plan
    editing is 2D, so only local X/Y levels are valid here.
    """

    room_index = _target_room_index(project, room_resref)
    room = project.rooms[room_index]
    primitive = _floor_plan_for_room(room)
    selected = tuple(dict.fromkeys(int(index) for index in point_indices))
    if len(selected) < 1:
        raise ValueError("Transform level snap requires at least one floor-plan point index.")
    axis_key = str(axis or "x").strip().lower()
    if axis_key not in {"x", "y"}:
        raise ValueError("Floor-plan transform level snapping supports local X or Y only; use terrain tools for Z.")
    policy = str(level_policy or "average").strip().lower() or "average"
    target_index = None if target_point_index is None else int(target_point_index)
    result = transform_snap_vertices_to_level(
        _floor_plan_component_mesh(primitive),
        selected,
        axis=axis_key,
        target_value=value,
        target_index=target_index,
        level_policy=policy,
    )
    audit = audit_component_edit_result(result, component_kind="floor_plan_vertex", affects_walkmesh=True)
    updated_primitive = replace(
        primitive,
        points=_floor_plan_points_from_component_vertices(result.mesh.vertices),
        metadata={
            **dict(primitive.metadata),
            "last_operation": "transform_snap_floor_plan_vertices",
            "transform_snap_vertices": list(selected),
            "transform_snap_axis": axis_key,
            "transform_snap_value": result.metadata.get("value"),
            "transform_snap_policy": result.metadata.get("level_policy"),
            "transform_snap_target_index": target_index,
            "source": "map_studio:floor_plan_transform_level_snap",
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )
    return _replace_floor_plan_room(
        project,
        room_index,
        updated_primitive,
        operation="transform_snap_floor_plan_vertices",
        room_metadata={
            "transform_snap_vertices": list(selected),
            "transform_snap_axis": axis_key,
            "transform_snap_policy": result.metadata.get("level_policy"),
            "transform_snap_target_index": target_index,
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )


def mirror_authored_floor_plan_vertices(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    axis: str = "x",
) -> AuthoredModuleProject:
    """Mirror an entire floor-plan footprint around its local centerline."""

    room_index = _target_room_index(project, room_resref)
    room = project.rooms[room_index]
    primitive = _floor_plan_for_room(room)
    source_points = tuple((float(x), float(y)) for x, y in tuple(primitive.points or ()))
    if len(source_points) < 3:
        raise ValueError("Mirror floor-plan footprint requires at least three points.")
    axis_key = str(axis or "x").strip().lower()
    if axis_key not in {"x", "y"}:
        raise ValueError("Floor-plan mirroring supports local X or Y only.")
    result = mirror_vertices(
        _floor_plan_component_mesh(primitive),
        range(len(source_points)),
        axis=axis_key,
    )
    mirrored_points = _floor_plan_points_from_component_vertices(result.mesh.vertices)
    mirrored_points = _preserve_floor_plan_winding(source_points, mirrored_points)
    updated_primitive = replace(
        primitive,
        points=mirrored_points,
        metadata={
            **dict(primitive.metadata),
            "last_operation": "mirror_floor_plan_vertices",
            "mirror_axis": axis_key,
            "mirror_center": result.metadata.get("center"),
            "source": "map_studio:floor_plan_vertex_mirror",
        },
    )
    return _replace_floor_plan_room(
        project,
        room_index,
        updated_primitive,
        operation="mirror_floor_plan_vertices",
        room_metadata={
            "mirror_axis": axis_key,
            "mirror_center": result.metadata.get("center"),
        },
    )


def fill_authored_floor_plan_face(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    point_indices: tuple[int, ...] | list[int],
) -> AuthoredModuleProject:
    """Record a filled floor-plan face loop for KOTOR room/WOK repair workflows."""

    room_index = _target_room_index(project, room_resref)
    room = project.rooms[room_index]
    primitive = _floor_plan_for_room(room)
    selected = tuple(dict.fromkeys(int(index) for index in point_indices))
    if len(selected) < 3:
        raise ValueError("Fill floor-plan face requires at least three ordered point indices.")
    result = fill_face(_floor_plan_component_mesh(primitive), selected)
    audit = audit_component_edit_result(result, component_kind="floor_plan_face", affects_walkmesh=True)
    updated_primitive = replace(
        primitive,
        metadata={
            **dict(primitive.metadata),
            "last_operation": "fill_floor_plan_face",
            "filled_face_indices": list(selected),
            "source": "map_studio:floor_plan_face_fill",
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )
    return _replace_floor_plan_room(
        project,
        room_index,
        updated_primitive,
        operation="fill_floor_plan_face",
        room_metadata={"filled_face_indices": list(selected), "last_component_edit_audit": _component_edit_audit_payload(audit)},
    )


def triangulate_authored_floor_plan_face(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
) -> AuthoredModuleProject:
    """Precompute deterministic floor-plan fan triangles for export/readiness review."""

    room_index = _target_room_index(project, room_resref)
    room = project.rooms[room_index]
    primitive = _floor_plan_for_room(room)
    if len(tuple(primitive.points or ())) < 3:
        raise ValueError("Triangulate floor-plan face requires at least three footprint points.")
    result = triangulate_faces(_floor_plan_component_mesh_with_face(primitive))
    audit = audit_component_edit_result(result, component_kind="floor_plan_face", affects_walkmesh=True)
    triangles = [list(face) for face in result.mesh.faces]
    updated_primitive = replace(
        primitive,
        metadata={
            **dict(primitive.metadata),
            "last_operation": "triangulate_floor_plan_face",
            "triangulated_faces": triangles,
            "source": "map_studio:floor_plan_face_triangulate",
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )
    return _replace_floor_plan_room(
        project,
        room_index,
        updated_primitive,
        operation="triangulate_floor_plan_face",
        room_metadata={
            "triangulated_faces": triangles,
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )


def cleanup_authored_floor_plan_normals(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    positive_z: bool = True,
) -> AuthoredModuleProject:
    """Orient the floor-plan footprint winding so generated room/WOK normals are predictable."""

    room_index = _target_room_index(project, room_resref)
    room = project.rooms[room_index]
    primitive = _floor_plan_for_room(room)
    source_points = tuple((float(x), float(y)) for x, y in tuple(primitive.points or ()))
    if len(source_points) < 3:
        raise ValueError("Cleanup floor-plan normals requires at least three footprint points.")
    result = cleanup_face_normals(
        _floor_plan_component_mesh_with_face(primitive),
        reference_axis="z",
        positive=bool(positive_z),
    )
    audit = audit_component_edit_result(result, component_kind="floor_plan_face", affects_walkmesh=True)
    ordered_face = result.mesh.faces[0] if result.mesh.faces else tuple(range(len(source_points)))
    updated_points = tuple(source_points[index] for index in ordered_face)
    updated_primitive = replace(
        primitive,
        points=updated_points,
        metadata={
            **dict(primitive.metadata),
            "last_operation": "cleanup_floor_plan_normals",
            "normal_cleanup_positive_z": bool(positive_z),
            "normal_cleanup_flipped_faces": result.metadata.get("flipped_face_count", 0),
            "source": "map_studio:floor_plan_normal_cleanup",
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )
    return _replace_floor_plan_room(
        project,
        room_index,
        updated_primitive,
        operation="cleanup_floor_plan_normals",
        room_metadata={
            "normal_cleanup_positive_z": bool(positive_z),
            "normal_cleanup_flipped_faces": result.metadata.get("flipped_face_count", 0),
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )


def split_authored_floor_plan_face(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    point_indices: tuple[int, int] | list[int],
) -> AuthoredModuleProject:
    """Record a selected-vertex floor-plan face split for KOTOR room/WOK review.

    A floor-plan room currently owns one footprint loop, so this records the
    deterministic split loops and component-edit audit without silently
    converting the room into multiple generated rooms. Export/readiness can then
    warn accurately until a later room-boundary split consumes the recorded
    loops.
    """

    room_index = _target_room_index(project, room_resref)
    room = project.rooms[room_index]
    primitive = _floor_plan_for_room(room)
    selected = tuple(dict.fromkeys(int(index) for index in tuple(point_indices or ())))
    if len(selected) != 2:
        raise ValueError("Split floor-plan face requires exactly two point indices.")
    result = split_face_with_edge(_floor_plan_component_mesh_with_face(primitive), 0, selected[0], selected[1])
    audit = audit_component_edit_result(result, component_kind="floor_plan_face", affects_walkmesh=True)
    split_faces = [list(face) for face in result.mesh.faces]
    updated_primitive = replace(
        primitive,
        metadata={
            **dict(primitive.metadata),
            "last_operation": "split_floor_plan_face",
            "split_face_indices": list(selected),
            "split_faces": split_faces,
            "source": "map_studio:floor_plan_face_split",
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )
    return _replace_floor_plan_room(
        project,
        room_index,
        updated_primitive,
        operation="split_floor_plan_face",
        room_metadata={
            "split_face_indices": list(selected),
            "split_faces": split_faces,
            "last_component_edit_audit": _component_edit_audit_payload(audit),
        },
    )


def cleanup_authored_floor_plan_vertices(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    tolerance: float = 0.001,
) -> AuthoredModuleProject:
    """Remove redundant floor-plan points before MDL/WOK export.

    This is footprint cleanup, not generic mesh cleanup: it removes duplicate,
    sequential, closing, and collinear points that would create tiny room
    edges, sliver walls, or fragile WOK triangles.
    """

    room_index = _target_room_index(project, room_resref)
    room = project.rooms[room_index]
    primitive = _floor_plan_for_room(room)
    clean_tolerance = max(float(tolerance), 0.000001)
    old_points = tuple((float(x), float(y)) for x, y in tuple(primitive.points or ()))
    updated_points = _clean_floor_plan_points(old_points, tolerance=clean_tolerance)
    if len(updated_points) < 3:
        raise ValueError("Cleanup floor-plan vertices would leave fewer than three footprint points.")
    removed_count = max(len(old_points) - len(updated_points), 0)
    updated_primitive = replace(
        primitive,
        points=updated_points,
        metadata={
            **dict(primitive.metadata),
            "last_operation": "cleanup_floor_plan_vertices",
            "cleanup_removed_point_count": removed_count,
            "cleanup_tolerance": clean_tolerance,
            "source": "map_studio:floor_plan_vertex_cleanup",
        },
    )
    return _replace_floor_plan_room(
        project,
        room_index,
        updated_primitive,
        operation="cleanup_floor_plan_vertices",
        room_metadata={
            "cleanup_removed_point_count": removed_count,
            "cleanup_tolerance": clean_tolerance,
        },
    )


def apply_authored_floor_plan_operation(project: AuthoredModuleProject, operation: str, **kwargs: Any) -> AuthoredModuleProject:
    """Dispatch a named Map Studio room operation."""

    op = str(operation or "").strip().lower()
    if op == "inset":
        return apply_authored_floor_plan_inset(project, distance=float(kwargs.get("distance", 0.25)), room_resref=str(kwargs.get("room_resref", "")))
    if op == "bevel":
        return apply_authored_floor_plan_bevel(project, distance=float(kwargs.get("distance", 0.25)), room_resref=str(kwargs.get("room_resref", "")))
    if op in {"edge_extrude", "extrude"}:
        return apply_authored_floor_plan_edge_extrude(
            project,
            edge_index=int(kwargs.get("edge_index", 0)),
            distance=float(kwargs.get("distance", 0.25)),
            room_resref=str(kwargs.get("room_resref", "")),
        )
    if op in {"cleanup", "cleanup_vertices", "cleanup_floor_plan_vertices"}:
        return cleanup_authored_floor_plan_vertices(
            project,
            room_resref=str(kwargs.get("room_resref", "")),
            tolerance=float(kwargs.get("tolerance", 0.001)),
        )
    if op in {"fill", "fill_face", "fill_floor_plan_face"}:
        return fill_authored_floor_plan_face(
            project,
            room_resref=str(kwargs.get("room_resref", "")),
            point_indices=tuple(kwargs.get("point_indices", ()) or ()),
        )
    if op in {"triangulate", "triangulate_face", "triangulate_floor_plan_face"}:
        return triangulate_authored_floor_plan_face(
            project,
            room_resref=str(kwargs.get("room_resref", "")),
        )
    if op in {"normals", "cleanup_normals", "cleanup_floor_plan_normals"}:
        return cleanup_authored_floor_plan_normals(
            project,
            room_resref=str(kwargs.get("room_resref", "")),
            positive_z=bool(kwargs.get("positive_z", True)),
        )
    if op in {"face_split", "split_face", "split_floor_plan_face"} or (
        op == "knife_split" and tuple(kwargs.get("point_indices", ()) or ())
    ):
        return split_authored_floor_plan_face(
            project,
            room_resref=str(kwargs.get("room_resref", "")),
            point_indices=tuple(kwargs.get("point_indices", ()) or ()),
        )
    if op in {"mirror", "mirror_vertices", "mirror_floor_plan_vertices"}:
        return mirror_authored_floor_plan_vertices(
            project,
            room_resref=str(kwargs.get("room_resref", "")),
            axis=str(kwargs.get("axis", "x")),
        )
    if op in {"rectangular_cut", "cut"}:
        return apply_authored_floor_plan_rectangular_cut(
            project,
            center=tuple(kwargs.get("center", (0.0, 0.0))),  # type: ignore[arg-type]
            size=tuple(kwargs.get("size", (1.0, 1.0))),  # type: ignore[arg-type]
            room_resref=str(kwargs.get("room_resref", "")),
            room_resref_prefix=kwargs.get("room_resref_prefix"),
        )
    if op in {"boolean_difference", "boolean_a_minus_b", "boolean_subtract"}:
        return apply_authored_floor_plan_boolean_difference(
            project,
            first_room_resref=str(kwargs.get("first_room_resref", kwargs.get("room_resref", ""))),
            second_room_resref=str(kwargs.get("second_room_resref", kwargs.get("target_room_resref", ""))),
            result_room_resref=str(kwargs.get("result_room_resref", "")),
        )
    if op in {"axis_split", "split", "knife_split", "split_x", "split_y"}:
        axis = str(kwargs.get("axis", "") or "").strip().lower()
        if op == "split_x":
            axis = "x"
        elif op == "split_y":
            axis = "y"
        if not axis:
            axis = "x"
        coordinate = kwargs.get("coordinate", kwargs.get("split_coordinate", 0.0))
        return apply_authored_floor_plan_axis_split(
            project,
            axis=axis,
            coordinate=float(coordinate),
            room_resref=str(kwargs.get("room_resref", "")),
            room_resref_prefix=kwargs.get("room_resref_prefix"),
        )
    if op in {"wall_opening", "doorway_opening", "opening", "set_wall_opening"}:
        return set_authored_floor_plan_wall_opening(
            project,
            room_resref=str(kwargs.get("room_resref", "")),
            name=str(kwargs.get("name", kwargs.get("opening_name", ""))),
            edge_index=int(kwargs.get("edge_index", 0)),
            center_fraction=float(kwargs.get("center_fraction", 0.5)),
            width=float(kwargs.get("width", 1.5)),
            height=float(kwargs.get("height", 2.1)),
            bottom=float(kwargs.get("bottom", 0.0)),
        )
    if op in {"opening_transition_marker", "doorway_marker", "transition_marker", "opening_marker"}:
        raw_edge = kwargs.get("edge_index", None)
        edge_index = None if raw_edge is None or str(raw_edge).strip() == "" else int(raw_edge)
        return add_authored_floor_plan_opening_transition_marker(
            project,
            room_resref=str(kwargs.get("room_resref", "")),
            opening_name=str(kwargs.get("opening_name", kwargs.get("name", ""))),
            edge_index=edge_index,
            marker_kind=str(kwargs.get("marker_kind", kwargs.get("kind", "door"))),
            template_resref=str(kwargs.get("template_resref", "")),
            tag=str(kwargs.get("tag", "")),
            linked_to=str(kwargs.get("linked_to", "")),
            linked_to_module=str(kwargs.get("linked_to_module", "")),
            transition_destination=int(kwargs.get("transition_destination", 0)),
        )
    raise ValueError(f"Unsupported authored floor-plan operation: {operation}.")


def apply_authored_terrain_operation(project: AuthoredModuleProject, operation: str, **kwargs: Any) -> AuthoredModuleProject:
    """Dispatch a named Map Studio terrain heightfield operation."""

    op = str(operation or "").strip().lower()
    shrink_wrap_ops = {"shrink_wrap", "shrink_wrap_to_terrain", "snap_placements_to_terrain"}
    shape_preset_id = str(kwargs.get("preset_id", "") or "").strip().lower()
    brush_name = str(kwargs.get("brush", "") or "").strip().lower()
    if op.startswith("shape_preset:"):
        shape_preset_id = op.split(":", 1)[1].strip().lower()
        op = "shape_preset"
    if op.startswith("brush_stroke:"):
        brush_name = op.split(":", 1)[1].strip().lower()
        op = "brush_stroke"
    index = _target_room_index(project, str(kwargs.get("room_resref", "")))
    room = project.rooms[index]
    primitive = _terrain_for_room(room)
    if op in {"set_height", "set_sample", "sample"}:
        updated_primitive = set_terrain_heightfield_sample(
            primitive,
            row_index=int(kwargs.get("row_index", 0)),
            column_index=int(kwargs.get("column_index", 0)),
            height=float(kwargs.get("height", 0.0)),
        )
    elif op in {"raise", "lower", "offset"}:
        delta = float(kwargs.get("delta", 0.0))
        if op == "lower":
            delta = -abs(delta)
        elif op == "raise":
            delta = abs(delta)
        updated_primitive = offset_terrain_heightfield_samples(
            primitive,
            row_index=int(kwargs.get("row_index", 0)),
            column_index=int(kwargs.get("column_index", 0)),
            delta=delta,
            radius=int(kwargs.get("radius", 0)),
        )
    elif op == "flatten":
        updated_primitive = flatten_terrain_heightfield(primitive, height=float(kwargs.get("height", 0.0)))
    elif op == "smooth":
        updated_primitive = smooth_terrain_heightfield(
            primitive,
            iterations=int(kwargs.get("iterations", 1)),
            strength=float(kwargs.get("strength", 0.5)),
            preserve_boundary=bool(kwargs.get("preserve_boundary", True)),
        )
    elif op in {"mirror_z", "vertical_mirror"}:
        center_height = kwargs.get("center_height", kwargs.get("height", None))
        updated_primitive = mirror_terrain_heightfield_z(
            primitive,
            center_height=None if center_height is None else float(center_height),
        )
    elif op in {"bend", "bend_terrain", "terrain_bend"}:
        center = kwargs.get("center", None)
        span = kwargs.get("span", None)
        updated_primitive = bend_terrain_heightfield(
            primitive,
            axis=str(kwargs.get("axis", "x")),
            amplitude=float(kwargs.get("amplitude", kwargs.get("distance", 0.25))),
            center=None if center is None else float(center),
            span=None if span is None else float(span),
        )
    elif op in {"lattice", "terrain_lattice", "lattice_terrain"}:
        updated_primitive = lattice_terrain_heightfield(
            primitive,
            control_deltas=kwargs.get("control_deltas", ((0.0, 0.0), (0.0, kwargs.get("amplitude", kwargs.get("distance", 0.25))))),
            strength=float(kwargs.get("strength", 1.0)),
        )
    elif op in {"brush_stroke", "terrain_brush_stroke"}:
        updated_primitive = apply_terrain_brush_stroke(
            primitive,
            brush=brush_name or "raise",
            points=kwargs.get("points") or ((int(kwargs.get("row_index", 0)), int(kwargs.get("column_index", 0)), 1.0),),
            delta=float(kwargs.get("delta", 0.1)),
            radius=int(kwargs.get("radius", 0)),
            height=float(kwargs.get("height", 0.0)),
            iterations=int(kwargs.get("iterations", 1)),
            strength=float(kwargs.get("strength", 0.5)),
            preserve_boundary=bool(kwargs.get("preserve_boundary", True)),
            symmetry_axis=str(kwargs.get("symmetry_axis", kwargs.get("mirror_axis", ""))),
        )
    elif op in {"shape_preset", "shape"}:
        updated_primitive = apply_terrain_shape_preset(
            primitive,
            preset_id=shape_preset_id,
            height=float(kwargs.get("height", 0.0)),
        )
    elif op in shrink_wrap_ops:
        updated_primitive = replace(
            primitive,
            metadata={
                **dict(primitive.metadata),
                "last_operation": "terrain_shrink_wrap",
                "shrink_wrap_target": "authored_gameplay_placements",
                "shrink_wrap_surface": "terrain_heightfield",
                "source": "map_studio:terrain_shrink_wrap",
            },
        )
    else:
        raise ValueError(f"Unsupported authored terrain operation: {operation}.")
    room_metadata = {
        **dict(room.metadata),
        "primitive": "terrain_heightfield",
        "last_operation": f"terrain_{op}",
    }
    if op in shrink_wrap_ops:
        room_metadata.update(
            {
                "shrink_wrap_target": "authored_gameplay_placements",
                "shrink_wrap_surface": "terrain_heightfield",
            }
        )
    updated = replace(
        room,
        primitive=updated_primitive,
        composition=None,
        metadata=room_metadata,
    )
    rooms = tuple(project.rooms[:index] + (updated,) + project.rooms[index + 1 :])
    placements = _repair_placements_for_terrain(
        project.placements,
        terrain=updated_primitive,
        room=updated,
        operation=f"terrain_{op}",
    )
    return _replace_rooms(project, rooms, operation=f"terrain_{op}", placements=placements)


__all__ = [
    "AuthoredCompositionPrimitiveKind",
    "AuthoredCompositionPrimitiveDimension",
    "AuthoredCompositionPrimitiveTransform",
    "AuthoredUniversalTransformSelection",
    "AuthoredFloorPlanVertexSnapCandidate",
    "AuthoredPrimitiveVertexSnapCandidate",
    "AuthoredFloorPlanRoomChoice",
    "AuthoredTerrainRoomChoice",
    "add_authored_floor_plan_opening_transition_marker",
    "add_authored_room_composition_primitive",
    "apply_authored_terrain_operation",
    "apply_authored_floor_plan_axis_split",
    "apply_authored_floor_plan_boolean_difference",
    "apply_authored_floor_plan_rectangular_union",
    "apply_authored_floor_plan_bevel",
    "apply_authored_floor_plan_edge_extrude",
    "apply_authored_floor_plan_inset",
    "apply_authored_floor_plan_operation",
    "apply_authored_floor_plan_rectangular_cut",
    "available_authored_composition_primitive_kinds",
    "authored_floor_plan_vertex_snap_candidates",
    "authored_room_composition_primitive_vertex_snap_candidates",
    "authored_floor_plan_room_choices",
    "authored_terrain_room_choices",
    "authored_room_composition_primitives",
    "authored_room_composition_primitive_universal_transform",
    "bridge_authored_floor_plan_edges",
    "center_authored_room_composition_primitive_pivot",
    "cleanup_authored_floor_plan_normals",
    "cleanup_authored_floor_plan_vertices",
    "combine_authored_room_composition_primitives",
    "duplicate_authored_room_composition_primitive",
    "fill_authored_floor_plan_face",
    "freeze_authored_room_composition_primitive_transform",
    "flatten_authored_floor_plan_vertices",
    "grid_snap_authored_floor_plan_vertices",
    "grid_snap_authored_room_composition_primitive",
    "mirror_authored_room_composition_primitive_transform",
    "mirror_authored_floor_plan_vertices",
    "move_authored_floor_plan_point",
    "move_authored_room_composition_primitive",
    "remove_authored_room_composition_primitive",
    "separate_authored_room_composition_primitive",
    "set_authored_floor_plan_wall_opening",
    "set_authored_floor_plan_extrusion_settings",
    "set_authored_room_composition_primitive_dimensions",
    "set_authored_room_edge_normal_policy",
    "set_authored_room_composition_primitive_style",
    "set_authored_room_composition_primitive_transform",
    "split_authored_floor_plan_face",
    "shrink_wrap_authored_room_composition_primitive_to_terrain",
    "snap_authored_room_composition_primitive_pivot_to_vertex",
    "snap_authored_floor_plan_vertex_to_vertex",
    "transform_snap_authored_room_composition_primitive_level",
    "transform_snap_authored_floor_plan_vertices",
    "triangulate_authored_floor_plan_face",
    "weld_authored_floor_plan_vertices",
]
