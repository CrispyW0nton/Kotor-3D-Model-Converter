"""Bridge KMAP project sections to authored Map Studio module readiness.

KMAP is the scene/project container.  The from-scratch module authoring contract
lives in ``AuthoredModuleProject``.  This bridge keeps the conversion headless
so Qt windows can display readiness without owning parsing or validation rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .authored_module_objects import (
    AuthoredCameraInstance,
    AuthoredCreatureInstance,
    AuthoredDoorInstance,
    AuthoredEncounterInstance,
    AuthoredGameplayPlacement,
    AuthoredPlaceableInstance,
    AuthoredSoundInstance,
    AuthoredStoreInstance,
    AuthoredTriggerInstance,
    AuthoredWaypointInstance,
    ModuleEntryPoint,
)
from .authored_module_lighting import (
    AuthoredRoomLight,
    authored_room_light_payload,
    normalise_authored_room_light,
)
from .authored_module_project import (
    AuthoredModuleMetadata,
    AuthoredModuleProject,
    AuthoredRoomSpec,
    create_single_room_project,
    normalise_resref,
)
from .authored_module_readiness import AuthoredModuleReadiness, build_authored_module_readiness
from .authored_room_composition import AuthoredRoomComposition, PlacedRoomPrimitive, PrimitiveTransform
from .authored_room_materials import DEFAULT_AUTHORED_ROOM_TEXTURE, normalize_authored_room_texture
from .authored_room_floorplan import FloorPlanRoomPrimitive, FloorPlanWallOpening
from .authored_room_geometry import RectangularRoomPrimitive
from .authored_room_primitives import (
    ArchPrimitive,
    CubePrimitive,
    CylinderPrimitive,
    FloorPrimitive,
    PrimitiveMaterial,
    RampPrimitive,
    StairsPrimitive,
    WallPrimitive,
)


@dataclass(frozen=True)
class AuthoredModuleKMapBridgeResult:
    """Authored module data found in a KMAP project, if any."""

    project: AuthoredModuleProject | None = None
    readiness: AuthoredModuleReadiness | None = None
    runtime_resources: tuple[tuple[str, str], ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_messages: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _vec2(value: Any) -> tuple[float, float] | None:
    if isinstance(value, dict):
        value = (value.get("x"), value.get("y"))
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (_float(value[0], 0.0), _float(value[1], 0.0))
    return None


def _vec3(value: Any, default: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> tuple[float, float, float]:
    if isinstance(value, dict):
        value = (value.get("x"), value.get("y"), value.get("z"))
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (_float(value[0], default[0]), _float(value[1], default[1]), _float(value[2], default[2]))
    return default


def _vec4(value: Any, default: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)) -> tuple[float, float, float, float]:
    if isinstance(value, dict):
        value = (value.get("x"), value.get("y"), value.get("z"), value.get("w"))
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        return (_float(value[0], default[0]), _float(value[1], default[1]), _float(value[2], default[2]), _float(value[3], default[3]))
    return default


def _material(data: Any) -> PrimitiveMaterial:
    source = _dict(data)
    return PrimitiveMaterial(
        texture=str(source.get("texture") or "default"),
        diffuse=_vec3(source.get("diffuse"), (0.8, 0.8, 0.8)),
        ambient=_vec3(source.get("ambient"), (0.35, 0.35, 0.35)),
        metadata=_dict(source.get("metadata")),
    )


def _transform(data: Any) -> PrimitiveTransform:
    source = _dict(data)
    return PrimitiveTransform(
        translation=_vec3(source.get("translation")),
        rotation_degrees_z=_float(source.get("rotation_degrees_z"), 0.0),
        scale=_vec3(source.get("scale"), (1.0, 1.0, 1.0)),
        pivot=_vec3(source.get("pivot")),
    )


def _opening(data: Any) -> FloorPlanWallOpening:
    source = _dict(data)
    return FloorPlanWallOpening(
        name=str(source.get("name") or ""),
        edge_index=int(_float(source.get("edge_index"), 0.0)),
        center_fraction=_float(source.get("center_fraction"), 0.5),
        width=_float(source.get("width"), 1.5),
        height=_float(source.get("height"), 2.1),
        bottom=_float(source.get("bottom"), 0.0),
        metadata=_dict(source.get("metadata")),
    )


def _floor_primitive(data: Any, room_resref: str) -> FloorPrimitive:
    source = _dict(data)
    return FloorPrimitive(
        name=str(source.get("name") or f"{room_resref}_floor"),
        width=_float(source.get("width"), 10.0),
        depth=_float(source.get("depth"), 10.0),
        z=_float(source.get("z"), 0.0),
        surface_id=source.get("surface_id", source.get("floor_surface_id", 4)),
        material=_material(source.get("material")),
    )


def _base_room_primitive(data: Any, room_resref: str) -> WallPrimitive | CubePrimitive | RampPrimitive | StairsPrimitive | CylinderPrimitive | ArchPrimitive:
    source = _dict(data)
    primitive_type = str(source.get("type") or source.get("primitive") or "").strip().lower()
    name = str(source.get("name") or f"{room_resref}_{primitive_type or 'primitive'}")
    material = _material(source.get("material"))
    if primitive_type == "wall":
        return WallPrimitive(
            name=name,
            width=_float(source.get("width"), 4.0),
            height=_float(source.get("height"), 3.0),
            thickness=_float(source.get("thickness"), 0.15),
            axis=str(source.get("axis") or "x"),
            center=_vec3(source.get("center"), (0.0, 0.0, 1.5)),
            material=material,
        )
    if primitive_type == "cube":
        return CubePrimitive(
            name=name,
            size=_vec3(source.get("size"), (1.0, 1.0, 1.0)),
            center=_vec3(source.get("center"), (0.0, 0.0, 0.5)),
            material=material,
        )
    if primitive_type == "ramp":
        return RampPrimitive(
            name=name,
            width=_float(source.get("width"), 2.0),
            length=_float(source.get("length"), 4.0),
            height=_float(source.get("height"), 1.0),
            center=_vec3(source.get("center")),
            surface_id=source.get("surface_id", 4),
            material=material,
        )
    if primitive_type == "stairs":
        return StairsPrimitive(
            name=name,
            width=_float(source.get("width"), 2.0),
            depth=_float(source.get("depth"), 4.0),
            height=_float(source.get("height"), 1.0),
            steps=int(_float(source.get("steps"), 4.0)),
            surface_id=source.get("surface_id", 4),
            material=material,
        )
    if primitive_type == "cylinder":
        return CylinderPrimitive(
            name=name,
            radius=_float(source.get("radius"), 0.5),
            height=_float(source.get("height"), 1.0),
            segments=int(_float(source.get("segments"), 16.0)),
            center=_vec3(source.get("center"), (0.0, 0.0, 0.5)),
            material=material,
        )
    if primitive_type == "arch":
        return ArchPrimitive(
            name=name,
            width=_float(source.get("width"), 2.0),
            height=_float(source.get("height"), 3.0),
            frame_thickness=_float(source.get("frame_thickness"), 0.25),
            depth=_float(source.get("depth"), 0.25),
            segments=int(_float(source.get("segments"), 12.0)),
            center=_vec3(source.get("center"), (0.0, 0.0, 1.5)),
            material=material,
        )
    raise ValueError(f"Unsupported authored room composition primitive type: {primitive_type or '(missing)'}")


def _composition_primitive(data: dict[str, Any], room_resref: str) -> AuthoredRoomComposition:
    primitive = _dict(data.get("primitive"))
    floor = _floor_primitive(primitive.get("floor"), room_resref)
    primitives = []
    for raw in primitive.get("primitives", ()) or ():
        source = _dict(raw)
        base = _base_room_primitive(source, room_resref)
        transform_payload = source.get("transform")
        if transform_payload is None:
            primitives.append(base)
        else:
            primitives.append(
                PlacedRoomPrimitive(
                    primitive=base,
                    transform=_transform(transform_payload),
                    name=str(source.get("instance_name") or source.get("name") or getattr(base, "name", "")),
                )
            )
    return AuthoredRoomComposition(
        room_resref=normalise_resref(primitive.get("room_resref") or room_resref),
        floor=floor,
        primitives=tuple(primitives),
        metadata=_dict(primitive.get("metadata")),
    )


def _room_primitive(data: dict[str, Any], room_resref: str) -> RectangularRoomPrimitive | FloorPlanRoomPrimitive | AuthoredRoomComposition:
    primitive = _dict(data.get("primitive"))
    primitive_type = str(primitive.get("type") or primitive.get("primitive") or data.get("primitive_type") or "rectangular").lower()
    if primitive_type in {"composition", "authored_room_composition"}:
        return _composition_primitive(data, room_resref)
    if primitive_type in {"floor_plan", "floorplan", "floor_plan_extrusion"}:
        points = tuple(point for point in (_vec2(item) for item in primitive.get("points", ()) or ()) if point is not None)
        return FloorPlanRoomPrimitive(
            room_resref=normalise_resref(primitive.get("room_resref") or room_resref),
            points=points,
            z=_float(primitive.get("z"), 0.0),
            wall_height=_float(primitive.get("wall_height"), 3.0),
            floor_surface_id=primitive.get("floor_surface_id", 4),
            material=_material(primitive.get("material")),
            include_walls=bool(primitive.get("include_walls", True)),
            openings=tuple(_opening(item) for item in primitive.get("openings", ()) or ()),
            metadata=_dict(primitive.get("metadata")),
        )
    return RectangularRoomPrimitive(
        room_resref=normalise_resref(primitive.get("room_resref") or room_resref),
        width=_float(primitive.get("width"), 10.0),
        depth=_float(primitive.get("depth"), 10.0),
        wall_height=_float(primitive.get("wall_height"), 3.0),
        floor_surface_id=primitive.get("floor_surface_id", 4),
        texture=str(primitive.get("texture") or "default"),
        include_doorway_marker=bool(primitive.get("include_doorway_marker", True)),
    )


def _placement(data: Any, module_root: str) -> AuthoredGameplayPlacement:
    source = _dict(data)
    entry = _dict(source.get("entry_point"))
    creatures = tuple(
        AuthoredCreatureInstance(
            template_resref=normalise_resref(item.get("template_resref") or item.get("resref") or ""),
            tag=str(item.get("tag") or ""),
            position=_vec3(item.get("position")),
            bearing=_float(item.get("bearing"), 0.0),
        )
        for item in (_dict(raw) for raw in source.get("creatures", ()) or ())
    )
    doors = tuple(
        AuthoredDoorInstance(
            template_resref=normalise_resref(item.get("template_resref") or item.get("resref") or ""),
            tag=str(item.get("tag") or ""),
            position=_vec3(item.get("position")),
            bearing=_float(item.get("bearing"), 0.0),
            linked_to=str(item.get("linked_to") or ""),
            linked_to_module=str(item.get("linked_to_module") or ""),
            transition_destination=int(_float(item.get("transition_destination"), 0.0)),
        )
        for item in (_dict(raw) for raw in source.get("doors", ()) or ())
    )
    triggers = tuple(
        AuthoredTriggerInstance(
            template_resref=normalise_resref(item.get("template_resref") or item.get("resref") or ""),
            tag=str(item.get("tag") or ""),
            position=_vec3(item.get("position")),
            geometry=tuple(_vec3(point) for point in item.get("geometry", ()) or ()),
            linked_to=str(item.get("linked_to") or ""),
            linked_to_module=str(item.get("linked_to_module") or ""),
            transition_destination=int(_float(item.get("transition_destination"), 0.0)),
        )
        for item in (_dict(raw) for raw in source.get("triggers", ()) or ())
    )
    encounters = tuple(
        AuthoredEncounterInstance(
            template_resref=normalise_resref(item.get("template_resref") or item.get("resref") or ""),
            tag=str(item.get("tag") or ""),
            position=_vec3(item.get("position")),
        )
        for item in (_dict(raw) for raw in source.get("encounters", ()) or ())
    )
    sounds = tuple(
        AuthoredSoundInstance(
            template_resref=normalise_resref(item.get("template_resref") or item.get("resref") or ""),
            tag=str(item.get("tag") or ""),
            position=_vec3(item.get("position")),
        )
        for item in (_dict(raw) for raw in source.get("sounds", ()) or ())
    )
    cameras = tuple(
        AuthoredCameraInstance(
            camera_id=item.get("camera_id", item.get("id", 0)),
            position=_vec3(item.get("position")),
            orientation=_vec4(item.get("orientation")),
            field_of_view=_float(item.get("field_of_view"), 45.0),
            height=_float(item.get("height"), 0.0),
            mic_range=_float(item.get("mic_range"), 0.0),
            pitch=_float(item.get("pitch"), 0.0),
        )
        for item in (_dict(raw) for raw in source.get("cameras", ()) or ())
    )
    stores = tuple(
        AuthoredStoreInstance(
            template_resref=normalise_resref(item.get("template_resref") or item.get("resref") or ""),
            tag=str(item.get("tag") or ""),
        )
        for item in (_dict(raw) for raw in source.get("stores", ()) or ())
    )
    placeables = tuple(
        AuthoredPlaceableInstance(
            template_resref=normalise_resref(item.get("template_resref") or item.get("resref") or ""),
            tag=str(item.get("tag") or ""),
            position=_vec3(item.get("position")),
            bearing=_float(item.get("bearing"), 0.0),
        )
        for item in (_dict(raw) for raw in source.get("placeables", ()) or ())
    )
    waypoints = tuple(
        AuthoredWaypointInstance(
            template_resref=normalise_resref(item.get("template_resref") or item.get("resref") or ""),
            tag=str(item.get("tag") or ""),
            position=_vec3(item.get("position")),
            bearing=_float(item.get("bearing"), 0.0),
            linked_to=str(item.get("linked_to") or ""),
        )
        for item in (_dict(raw) for raw in source.get("waypoints", ()) or ())
    )
    return AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(
            area_resref=normalise_resref(entry.get("area_resref") or module_root),
            position=_vec3(entry.get("position")),
            facing=_float(entry.get("facing"), 0.0),
        ),
        creatures=creatures,
        doors=doors,
        triggers=triggers,
        encounters=encounters,
        sounds=sounds,
        cameras=cameras,
        stores=stores,
        placeables=placeables,
        waypoints=waypoints,
        metadata=_dict(source.get("metadata")),
    )


def _lights(data: Any) -> tuple[AuthoredRoomLight, ...]:
    return tuple(normalise_authored_room_light(item) for item in (data or ()))


def _runtime_resources(data: Any) -> tuple[tuple[str, str], ...]:
    keys: set[tuple[str, str]] = set()
    for item in data or ():
        if isinstance(item, str):
            stem, dot, ext = item.rpartition(".")
            if dot:
                keys.add((normalise_resref(stem), ext.strip().lower().lstrip(".")))
            continue
        source = _dict(item)
        resref = normalise_resref(source.get("resref") or source.get("name") or "")
        restype = str(source.get("restype") or source.get("type") or "").strip().lower().lstrip(".")
        if resref and restype:
            keys.add((resref, restype))
    return tuple(sorted(keys))


def _vec3_payload(value: tuple[float, float, float]) -> list[float]:
    return [float(value[0]), float(value[1]), float(value[2])]


def _material_payload(material: PrimitiveMaterial) -> dict[str, Any]:
    return {
        "texture": material.texture,
        "diffuse": _vec3_payload(material.diffuse),
        "ambient": _vec3_payload(material.ambient),
        "metadata": dict(material.metadata),
    }


def _transform_payload(transform: PrimitiveTransform) -> dict[str, Any]:
    return {
        "translation": _vec3_payload(transform.translation),
        "rotation_degrees_z": float(transform.rotation_degrees_z),
        "scale": _vec3_payload(transform.scale),
        "pivot": _vec3_payload(transform.pivot),
    }


def _base_primitive_payload(primitive: WallPrimitive | CubePrimitive | RampPrimitive | StairsPrimitive | CylinderPrimitive | ArchPrimitive | PlacedRoomPrimitive) -> dict[str, Any]:
    transform: PrimitiveTransform | None = None
    instance_name = ""
    if isinstance(primitive, PlacedRoomPrimitive):
        transform = primitive.transform
        instance_name = primitive.name
        primitive = primitive.primitive
    payload: dict[str, Any]
    if isinstance(primitive, WallPrimitive):
        payload = {
            "type": "wall",
            "name": primitive.name,
            "width": float(primitive.width),
            "height": float(primitive.height),
            "thickness": float(primitive.thickness),
            "axis": primitive.axis,
            "center": _vec3_payload(primitive.center),
            "material": _material_payload(primitive.material),
        }
    elif isinstance(primitive, CubePrimitive):
        payload = {
            "type": "cube",
            "name": primitive.name,
            "size": _vec3_payload(primitive.size),
            "center": _vec3_payload(primitive.center),
            "material": _material_payload(primitive.material),
        }
    elif isinstance(primitive, RampPrimitive):
        payload = {
            "type": "ramp",
            "name": primitive.name,
            "width": float(primitive.width),
            "length": float(primitive.length),
            "height": float(primitive.height),
            "center": _vec3_payload(primitive.center),
            "surface_id": primitive.surface_id,
            "material": _material_payload(primitive.material),
        }
    elif isinstance(primitive, StairsPrimitive):
        payload = {
            "type": "stairs",
            "name": primitive.name,
            "width": float(primitive.width),
            "depth": float(primitive.depth),
            "height": float(primitive.height),
            "steps": int(primitive.steps),
            "surface_id": primitive.surface_id,
            "material": _material_payload(primitive.material),
        }
    elif isinstance(primitive, CylinderPrimitive):
        payload = {
            "type": "cylinder",
            "name": primitive.name,
            "radius": float(primitive.radius),
            "height": float(primitive.height),
            "segments": int(primitive.segments),
            "center": _vec3_payload(primitive.center),
            "material": _material_payload(primitive.material),
        }
    elif isinstance(primitive, ArchPrimitive):
        payload = {
            "type": "arch",
            "name": primitive.name,
            "width": float(primitive.width),
            "height": float(primitive.height),
            "frame_thickness": float(primitive.frame_thickness),
            "depth": float(primitive.depth),
            "segments": int(primitive.segments),
            "center": _vec3_payload(primitive.center),
            "material": _material_payload(primitive.material),
        }
    else:
        raise TypeError(f"Unsupported authored room composition primitive: {type(primitive)!r}")
    if transform is not None:
        payload["transform"] = _transform_payload(transform)
        if instance_name:
            payload["instance_name"] = instance_name
    return payload


def _composition_payload(composition: AuthoredRoomComposition) -> dict[str, Any]:
    return {
        "type": "composition",
        "room_resref": composition.room_resref,
        "floor": {
            "type": "floor",
            "name": composition.floor.name,
            "width": float(composition.floor.width),
            "depth": float(composition.floor.depth),
            "z": float(composition.floor.z),
            "surface_id": composition.floor.surface_id,
            "material": _material_payload(composition.floor.material),
        },
        "primitives": [_base_primitive_payload(item) for item in composition.primitives],
        "metadata": dict(composition.metadata),
    }


def _primitive_payload(primitive: RectangularRoomPrimitive | FloorPlanRoomPrimitive | AuthoredRoomComposition) -> dict[str, Any]:
    if isinstance(primitive, AuthoredRoomComposition):
        return _composition_payload(primitive)
    if isinstance(primitive, FloorPlanRoomPrimitive):
        return {
            "type": "floor_plan",
            "room_resref": primitive.room_resref,
            "points": [[float(x), float(y)] for x, y in primitive.points],
            "z": float(primitive.z),
            "wall_height": float(primitive.wall_height),
            "floor_surface_id": primitive.floor_surface_id,
            "material": _material_payload(primitive.material),
            "include_walls": bool(primitive.include_walls),
            "openings": [
                {
                    "name": opening.name,
                    "edge_index": int(opening.edge_index),
                    "center_fraction": float(opening.center_fraction),
                    "width": float(opening.width),
                    "height": float(opening.height),
                    "bottom": float(opening.bottom),
                    "metadata": dict(opening.metadata),
                }
                for opening in primitive.openings
            ],
            "metadata": dict(primitive.metadata),
        }
    return {
        "type": "rectangular",
        "room_resref": primitive.room_resref,
        "width": float(primitive.width),
        "depth": float(primitive.depth),
        "wall_height": float(primitive.wall_height),
        "floor_surface_id": primitive.floor_surface_id,
        "texture": primitive.texture,
        "include_doorway_marker": bool(primitive.include_doorway_marker),
    }


def _placement_payload(placement: AuthoredGameplayPlacement) -> dict[str, Any]:
    return {
        "entry_point": {
            "area_resref": placement.entry_point.area_resref,
            "position": _vec3_payload(placement.entry_point.position),
            "facing": float(placement.entry_point.facing),
        },
        "creatures": [
            {
                "template_resref": item.template_resref,
                "tag": item.tag,
                "position": _vec3_payload(item.position),
                "bearing": float(item.bearing),
            }
            for item in placement.creatures
        ],
        "doors": [
            {
                "template_resref": item.template_resref,
                "tag": item.tag,
                "position": _vec3_payload(item.position),
                "bearing": float(item.bearing),
                "linked_to": item.linked_to,
                "linked_to_module": item.linked_to_module,
                "transition_destination": int(item.transition_destination),
            }
            for item in placement.doors
        ],
        "triggers": [
            {
                "template_resref": item.template_resref,
                "tag": item.tag,
                "position": _vec3_payload(item.position),
                "geometry": [_vec3_payload(point) for point in item.geometry],
                "linked_to": item.linked_to,
                "linked_to_module": item.linked_to_module,
                "transition_destination": int(item.transition_destination),
            }
            for item in placement.triggers
        ],
        "encounters": [
            {
                "template_resref": item.template_resref,
                "tag": item.tag,
                "position": _vec3_payload(item.position),
            }
            for item in placement.encounters
        ],
        "sounds": [
            {
                "template_resref": item.template_resref,
                "tag": item.tag,
                "position": _vec3_payload(item.position),
            }
            for item in placement.sounds
        ],
        "cameras": [
            {
                "camera_id": item.camera_id,
                "position": _vec3_payload(item.position),
                "orientation": [float(value) for value in item.orientation],
                "field_of_view": float(item.field_of_view),
                "height": float(item.height),
                "mic_range": float(item.mic_range),
                "pitch": float(item.pitch),
            }
            for item in placement.cameras
        ],
        "stores": [
            {
                "template_resref": item.template_resref,
                "tag": item.tag,
            }
            for item in placement.stores
        ],
        "placeables": [
            {
                "template_resref": item.template_resref,
                "tag": item.tag,
                "position": _vec3_payload(item.position),
                "bearing": float(item.bearing),
            }
            for item in placement.placeables
        ],
        "waypoints": [
            {
                "template_resref": item.template_resref,
                "tag": item.tag,
                "position": _vec3_payload(item.position),
                "bearing": float(item.bearing),
                "linked_to": item.linked_to,
            }
            for item in placement.waypoints
        ],
        "metadata": dict(placement.metadata),
    }


def authored_project_to_kmap_payload(
    project: AuthoredModuleProject,
    *,
    runtime_resources: tuple[str, ...] = (),
    game_tested: bool = False,
) -> dict[str, Any]:
    """Convert an authored module project to the serializable KMAP section."""

    return {
        "module_root": project.metadata.module_root,
        "game": project.game,
        "display_name": project.metadata.display_name,
        "tag": project.metadata.tag,
        "description": project.metadata.description,
        "capability_stage": project.metadata.capability_stage,
        "metadata": dict(project.metadata.metadata),
        "rooms": [
            {
                "room_resref": room.room_resref,
                "primitive": _primitive_payload(room.primitive),
                "position": _vec3_payload(room.position),
                "visible_rooms": list(room.visible_rooms),
                "metadata": dict(room.metadata),
            }
            for room in project.rooms
        ],
        "placements": _placement_payload(project.placements),
        "lights": [authored_room_light_payload(light) for light in project.lights],
        "notes": list(project.notes),
        "extra": dict(project.extra),
        "runtime_resources": list(runtime_resources),
        "game_tested": bool(game_tested),
    }


def create_dev_test_authored_module_payload(*, module_root: str = "grdev01", game: str = "K1") -> dict[str, Any]:
    """Create the first editable from-scratch Map Studio KMAP payload."""

    root = normalise_resref(module_root)
    room_resref = normalise_resref(f"{root}_room01")
    project = create_single_room_project(
        module_root=root,
        game=game,
        display_name="GhostRigger Dev Test",
        room_primitive=RectangularRoomPrimitive(
            room_resref=room_resref,
            width=10.0,
            depth=10.0,
            wall_height=3.0,
            floor_surface_id=4,
            texture=normalize_authored_room_texture(DEFAULT_AUTHORED_ROOM_TEXTURE),
            include_doorway_marker=True,
        ),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref=root, position=(0.0, -3.0, 0.0)),
            placeables=(
                AuthoredPlaceableInstance(
                    template_resref="plc_bench",
                    tag="grdev01_test_placeable",
                    position=(1.75, 1.5, 0.0),
                ),
            ),
            waypoints=(
                AuthoredWaypointInstance(
                    template_resref="sw_startloc001",
                    tag="start",
                    position=(0.0, -3.0, 0.0),
                ),
            ),
            metadata={
                "source": "map_studio:kmap_authored_module",
                "player_start_is_module_entry": True,
            },
        ),
        notes=(
            "T2601 from-scratch smoke module.",
            "Editable KMAP-authored primitive room with player start and test placeable.",
        ),
        metadata={
            "task": "T2601",
            "source": "map_studio:kmap_authored_module",
            "room_geometry_mode": "rectangular_composition",
        },
    )
    return authored_project_to_kmap_payload(project)


def authored_project_from_kmap_payload(payload: Any, *, fallback_name: str = "new_level", fallback_game: str = "K1") -> AuthoredModuleProject:
    """Convert a serializable KMAP ``authored_module`` section to core intent."""

    data = _dict(payload)
    module_root = normalise_resref(data.get("module_root") or data.get("resref") or fallback_name)
    rooms: list[AuthoredRoomSpec] = []
    for index, room_data in enumerate(data.get("rooms", ()) or ()):
        room_source = _dict(room_data)
        room_resref = normalise_resref(room_source.get("room_resref") or room_source.get("resref") or f"{module_root}_r{index + 1}")
        rooms.append(
            AuthoredRoomSpec(
                room_resref=room_resref,
                primitive=_room_primitive(room_source, room_resref),
                position=_vec3(room_source.get("position")),
                visible_rooms=tuple(normalise_resref(item) for item in room_source.get("visible_rooms", ()) or ()),
                metadata=_dict(room_source.get("metadata")),
            )
        )
    return AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(
            module_root=module_root,
            game=str(data.get("game") or fallback_game or "K1").upper(),
            display_name=str(data.get("display_name") or fallback_name or module_root),
            tag=str(data.get("tag") or module_root),
            description=str(data.get("description") or ""),
            capability_stage=str(data.get("capability_stage") or "export_candidate"),
            metadata=_dict(data.get("metadata")),
        ),
        rooms=tuple(rooms),
        placements=_placement(data.get("placements"), module_root),
        lights=_lights(data.get("lights")),
        notes=tuple(str(item) for item in data.get("notes", ()) or ()),
        extra=_dict(data.get("extra")),
    )


def build_kmap_authored_module_readiness(kmap_project: Any) -> AuthoredModuleKMapBridgeResult:
    """Return authored-module readiness for a KMAP project when present."""

    extra = _dict(getattr(kmap_project, "extra_sections", {}))
    metadata = _dict(getattr(kmap_project, "metadata", {}))
    payload = extra.get("authored_module") or metadata.get("authored_module")
    if payload is None:
        return AuthoredModuleKMapBridgeResult(
            warnings=("No authored Map Studio module section is stored in this KMAP yet.",),
            metadata={"source": "src.core.modules.authored_module_kmap_bridge", "has_payload": False},
        )
    try:
        project = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(kmap_project, "name", "") or "new_level"),
            fallback_game=str(getattr(kmap_project, "game", "") or "K1"),
        )
    except Exception as exc:
        return AuthoredModuleKMapBridgeResult(
            blocking_messages=(f"Authored module section could not be parsed: {exc}",),
            metadata={"source": "src.core.modules.authored_module_kmap_bridge", "has_payload": True},
        )
    payload_dict = _dict(payload)
    resources = _runtime_resources(payload_dict.get("runtime_resources"))
    proof_metadata = {
        key: payload_dict.get(key)
        for key in (
            "proof_manifest_path",
            "checklist_path",
            "installed_module_path",
            "backup_module_path",
            "resolved_modules_dir",
            "resolved_game_root_dir",
            "launch_helper_command",
            "elevated_launch_script_path",
            "proof_recording_script_path",
            "in_game_proof_evidence_path",
        )
        if payload_dict.get(key)
    }
    readiness = build_authored_module_readiness(
        project,
        packaged_resources=resources,
        game_tested=bool(payload_dict.get("game_tested", False)),
        proof_metadata=proof_metadata,
    )
    return AuthoredModuleKMapBridgeResult(
        project=project,
        readiness=readiness,
        runtime_resources=resources,
        metadata={"source": "src.core.modules.authored_module_kmap_bridge", "has_payload": True},
    )


__all__ = [
    "AuthoredModuleKMapBridgeResult",
    "authored_project_from_kmap_payload",
    "authored_project_to_kmap_payload",
    "build_kmap_authored_module_readiness",
    "create_dev_test_authored_module_payload",
]
