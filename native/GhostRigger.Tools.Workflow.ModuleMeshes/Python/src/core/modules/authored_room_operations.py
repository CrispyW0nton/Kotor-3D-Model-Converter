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
    triangulate_faces,
    weld_vertices,
)

from .authored_module_project import AuthoredModuleProject, AuthoredRoomSpec, authored_resref_blocking_issue, normalise_resref
from .authored_module_objects import AuthoredGameplayPlacement
from .authored_module_placements import add_authored_gameplay_placement, update_authored_gameplay_transition
from .authored_room_composition import AuthoredRoomComposition, PlacedRoomPrimitive, PrimitiveTransform
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
    flatten_terrain_heightfield,
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
        )
    elif op in {"shape_preset", "shape"}:
        updated_primitive = apply_terrain_shape_preset(
            primitive,
            preset_id=shape_preset_id,
            height=float(kwargs.get("height", 0.0)),
        )
    else:
        raise ValueError(f"Unsupported authored terrain operation: {operation}.")
    updated = replace(
        room,
        primitive=updated_primitive,
        composition=None,
        metadata={
            **dict(room.metadata),
            "primitive": "terrain_heightfield",
            "last_operation": f"terrain_{op}",
        },
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
    "AuthoredFloorPlanVertexSnapCandidate",
    "AuthoredFloorPlanRoomChoice",
    "AuthoredTerrainRoomChoice",
    "add_authored_floor_plan_opening_transition_marker",
    "add_authored_room_composition_primitive",
    "apply_authored_terrain_operation",
    "apply_authored_floor_plan_axis_split",
    "apply_authored_floor_plan_rectangular_union",
    "apply_authored_floor_plan_bevel",
    "apply_authored_floor_plan_edge_extrude",
    "apply_authored_floor_plan_inset",
    "apply_authored_floor_plan_operation",
    "apply_authored_floor_plan_rectangular_cut",
    "available_authored_composition_primitive_kinds",
    "authored_floor_plan_vertex_snap_candidates",
    "authored_floor_plan_room_choices",
    "authored_terrain_room_choices",
    "authored_room_composition_primitives",
    "bridge_authored_floor_plan_edges",
    "cleanup_authored_floor_plan_normals",
    "cleanup_authored_floor_plan_vertices",
    "fill_authored_floor_plan_face",
    "flatten_authored_floor_plan_vertices",
    "mirror_authored_floor_plan_vertices",
    "move_authored_floor_plan_point",
    "move_authored_room_composition_primitive",
    "remove_authored_room_composition_primitive",
    "separate_authored_room_composition_primitive",
    "set_authored_floor_plan_wall_opening",
    "set_authored_floor_plan_extrusion_settings",
    "set_authored_room_composition_primitive_dimensions",
    "set_authored_room_composition_primitive_style",
    "set_authored_room_composition_primitive_transform",
    "split_authored_floor_plan_face",
    "snap_authored_floor_plan_vertex_to_vertex",
    "triangulate_authored_floor_plan_face",
    "weld_authored_floor_plan_vertices",
]
