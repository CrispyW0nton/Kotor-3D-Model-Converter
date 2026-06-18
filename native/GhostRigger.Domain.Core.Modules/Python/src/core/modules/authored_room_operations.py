"""Project-level room shaping operations for Map Studio.

The low-level floor-plan module owns polygon math.  This module owns the
authored-module operation policy: find a room in an ``AuthoredModuleProject``,
convert compatible starter primitives to floor-plan intent, apply the operation,
and return a new project that can be saved back into KMAP.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .authored_module_project import AuthoredModuleProject, AuthoredRoomSpec, normalise_resref
from .authored_module_objects import AuthoredGameplayPlacement
from .authored_room_composition import AuthoredRoomComposition, PlacedRoomPrimitive, PrimitiveTransform
from .authored_room_floorplan import (
    FloorPlanBevelOperation,
    FloorPlanInsetOperation,
    FloorPlanRectangularCutOperation,
    FloorPlanRectangularUnionOperation,
    FloorPlanRoomPrimitive,
    apply_floor_plan_bevel,
    apply_floor_plan_inset,
    apply_floor_plan_rectangular_cut,
    apply_floor_plan_rectangular_union,
)
from .authored_room_geometry import RectangularRoomPrimitive
from .authored_room_materials import compile_authored_room_material_preflight
from .authored_terrain_builder import (
    TerrainHeightfieldPrimitive,
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


@dataclass(frozen=True)
class AuthoredTerrainRoomChoice:
    """UI-ready terrain room choice for heightfield sculpt operations."""

    room_resref: str
    label: str
    row_count: int
    column_count: int
    min_height: float
    max_height: float
    room_index: int


_COMPOSITION_PRIMITIVE_KINDS: tuple[AuthoredCompositionPrimitiveKind, ...] = (
    AuthoredCompositionPrimitiveKind("wall", "Wall", "A rectangular wall/blockout slab."),
    AuthoredCompositionPrimitiveKind("cube", "Cube", "A simple box primitive for room dressing or massing."),
    AuthoredCompositionPrimitiveKind("ramp", "Ramp", "A sloped walkable ramp that contributes WOK faces.", creates_walkmesh=True),
    AuthoredCompositionPrimitiveKind("stairs", "Stairs", "A visual staircase with a walkable ramp-style WOK proxy.", creates_walkmesh=True),
    AuthoredCompositionPrimitiveKind("cylinder", "Cylinder", "A round column or pedestal primitive."),
    AuthoredCompositionPrimitiveKind("arch", "Arch", "A doorway arch frame for blockout and portal tests."),
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
        choices.append(
            AuthoredFloorPlanRoomChoice(
                room_resref=resref,
                label=f"{resref} ({len(tuple(primitive.points or ()))} points)",
                point_count=len(tuple(primitive.points or ())),
                room_index=index,
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
        choices.append(
            AuthoredTerrainRoomChoice(
                room_resref=resref,
                label=f"{resref} ({row_count}x{column_count}, {min_height:.2f}..{max_height:.2f} m)",
                row_count=row_count,
                column_count=column_count,
                min_height=float(min_height),
                max_height=float(max_height),
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
    if isinstance(base, (RampPrimitive, StairsPrimitive)):
        return resolve_walkmesh_surface_id(base.surface_id)
    return None


def _primitive_supports_walkmesh_surface(primitive: Any) -> bool:
    return _primitive_surface_id(primitive) is not None


def _primitive_kind(value: Any) -> str:
    kind = str(value or "").strip().lower().replace(" ", "_")
    aliases = {
        "box": "cube",
        "column": "cylinder",
        "stair": "stairs",
        "step": "stairs",
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
    if isinstance(base, (RampPrimitive, StairsPrimitive)):
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
    if isinstance(base, (RampPrimitive, StairsPrimitive)):
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


def _safe_anchor_for_piece(piece: FloorPlanRoomPrimitive) -> tuple[float, float, float]:
    xs = [float(point[0]) for point in piece.points]
    ys = [float(point[1]) for point in piece.points]
    return ((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, float(piece.z))


def _offset_anchor(anchor: tuple[float, float, float], dx: float, dy: float) -> tuple[float, float, float]:
    return (anchor[0] + float(dx), anchor[1] + float(dy), anchor[2])


def _placements_for_cut(project: AuthoredModuleProject, first_piece: FloorPlanRoomPrimitive) -> AuthoredGameplayPlacement:
    anchor = _safe_anchor_for_piece(first_piece)
    return replace(
        project.placements,
        entry_point=replace(project.placements.entry_point, position=anchor),
        placeables=tuple(replace(item, position=_offset_anchor(anchor, 0.5, 0.5)) for item in project.placements.placeables),
        waypoints=tuple(replace(item, position=anchor) for item in project.placements.waypoints),
        metadata={
            **dict(project.placements.metadata),
            "last_room_operation": "rectangular_cut",
            "placement_repaired_after_cut": True,
        },
    )


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


def apply_authored_floor_plan_operation(project: AuthoredModuleProject, operation: str, **kwargs: Any) -> AuthoredModuleProject:
    """Dispatch a named Map Studio room operation."""

    op = str(operation or "").strip().lower()
    if op == "inset":
        return apply_authored_floor_plan_inset(project, distance=float(kwargs.get("distance", 0.25)), room_resref=str(kwargs.get("room_resref", "")))
    if op == "bevel":
        return apply_authored_floor_plan_bevel(project, distance=float(kwargs.get("distance", 0.25)), room_resref=str(kwargs.get("room_resref", "")))
    if op in {"rectangular_cut", "cut"}:
        return apply_authored_floor_plan_rectangular_cut(
            project,
            center=tuple(kwargs.get("center", (0.0, 0.0))),  # type: ignore[arg-type]
            size=tuple(kwargs.get("size", (1.0, 1.0))),  # type: ignore[arg-type]
            room_resref=str(kwargs.get("room_resref", "")),
            room_resref_prefix=kwargs.get("room_resref_prefix"),
        )
    raise ValueError(f"Unsupported authored floor-plan operation: {operation}.")


def apply_authored_terrain_operation(project: AuthoredModuleProject, operation: str, **kwargs: Any) -> AuthoredModuleProject:
    """Dispatch a named Map Studio terrain heightfield operation."""

    op = str(operation or "").strip().lower()
    shape_preset_id = str(kwargs.get("preset_id", "") or "").strip().lower()
    if op.startswith("shape_preset:"):
        shape_preset_id = op.split(":", 1)[1].strip().lower()
        op = "shape_preset"
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
    "AuthoredFloorPlanRoomChoice",
    "AuthoredTerrainRoomChoice",
    "add_authored_room_composition_primitive",
    "apply_authored_terrain_operation",
    "apply_authored_floor_plan_rectangular_union",
    "apply_authored_floor_plan_bevel",
    "apply_authored_floor_plan_inset",
    "apply_authored_floor_plan_operation",
    "apply_authored_floor_plan_rectangular_cut",
    "available_authored_composition_primitive_kinds",
    "authored_floor_plan_room_choices",
    "authored_terrain_room_choices",
    "authored_room_composition_primitives",
    "move_authored_floor_plan_point",
    "move_authored_room_composition_primitive",
    "remove_authored_room_composition_primitive",
    "set_authored_room_composition_primitive_dimensions",
    "set_authored_room_composition_primitive_style",
    "set_authored_room_composition_primitive_transform",
]
