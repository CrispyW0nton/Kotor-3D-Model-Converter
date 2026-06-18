"""Headless authored gameplay object placement for Map Studio.

Future Map Studio panels should edit these objects, then compile them into
Odyssey GIT/IFO resources.  Keeping this Qt-free lets tests and exporters prove
module-placement behavior without constructing the UI.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


Vec3 = tuple[float, float, float]
Vec4 = tuple[float, float, float, float]


@dataclass(frozen=True)
class ModuleEntryPoint:
    """Player start data written to IFO module entry fields."""

    area_resref: str
    position: Vec3 = (0.0, 0.0, 0.0)
    facing: float = 0.0


@dataclass(frozen=True)
class AuthoredPlaceableInstance:
    """Authored UTP-backed placeable instance for a GIT Placeable List entry."""

    template_resref: str
    tag: str = ""
    position: Vec3 = (0.0, 0.0, 0.0)
    bearing: float = 0.0


@dataclass(frozen=True)
class AuthoredCreatureInstance:
    """Authored UTC-backed creature instance for a GIT Creature List entry."""

    template_resref: str
    tag: str = ""
    position: Vec3 = (0.0, 0.0, 0.0)
    bearing: float = 0.0


@dataclass(frozen=True)
class AuthoredDoorInstance:
    """Authored UTD-backed door instance for a GIT Door List entry."""

    template_resref: str
    tag: str = ""
    position: Vec3 = (0.0, 0.0, 0.0)
    bearing: float = 0.0
    linked_to: str = ""
    linked_to_module: str = ""
    transition_destination: int = 0


@dataclass(frozen=True)
class AuthoredWaypointInstance:
    """Authored waypoint/start marker for a GIT WaypointList entry."""

    template_resref: str
    tag: str = ""
    position: Vec3 = (0.0, 0.0, 0.0)
    bearing: float = 0.0
    linked_to: str = ""


@dataclass(frozen=True)
class AuthoredTriggerInstance:
    """Authored UTT-backed trigger instance for a GIT TriggerList entry."""

    template_resref: str
    tag: str = ""
    position: Vec3 = (0.0, 0.0, 0.0)
    geometry: tuple[Vec3, ...] = ()
    linked_to: str = ""
    linked_to_module: str = ""
    transition_destination: int = 0


@dataclass(frozen=True)
class AuthoredEncounterInstance:
    """Authored UTE-backed encounter instance for a GIT Encounter List entry."""

    template_resref: str
    tag: str = ""
    position: Vec3 = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class AuthoredSoundInstance:
    """Authored UTS-backed sound instance for a GIT SoundList entry."""

    template_resref: str
    tag: str = ""
    position: Vec3 = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class AuthoredCameraInstance:
    """Authored area camera placement for a GIT CameraList entry."""

    camera_id: int | str
    position: Vec3 = (0.0, 0.0, 0.0)
    orientation: Vec4 = (0.0, 0.0, 0.0, 1.0)
    field_of_view: float = 45.0
    height: float = 0.0
    mic_range: float = 0.0
    pitch: float = 0.0


@dataclass(frozen=True)
class AuthoredStoreInstance:
    """Authored UTM-backed store instance for a GIT StoreList entry."""

    template_resref: str
    tag: str = ""


@dataclass(frozen=True)
class AuthoredGameplayPlacement:
    """Compiled gameplay placements for one authored module."""

    entry_point: ModuleEntryPoint
    creatures: tuple[AuthoredCreatureInstance, ...] = ()
    doors: tuple[AuthoredDoorInstance, ...] = ()
    triggers: tuple[AuthoredTriggerInstance, ...] = ()
    encounters: tuple[AuthoredEncounterInstance, ...] = ()
    sounds: tuple[AuthoredSoundInstance, ...] = ()
    cameras: tuple[AuthoredCameraInstance, ...] = ()
    stores: tuple[AuthoredStoreInstance, ...] = ()
    placeables: tuple[AuthoredPlaceableInstance, ...] = ()
    waypoints: tuple[AuthoredWaypointInstance, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthoredGameplayPlacementValidation:
    """Validation summary for authored GIT/IFO placement intent."""

    ok: bool
    warnings: tuple[str, ...] = ()
    blocking_issues: tuple[str, ...] = ()


def normalise_resource_resref(value: Any) -> str:
    """Return a KOTOR-style lowercase resref fragment for placed resources."""

    text = str(value or "").strip().lower()
    if "." in text:
        text = text.rsplit(".", 1)[0]
    return text[:16]


def _position_ok(position: Vec3) -> bool:
    return len(position) == 3 and all(math.isfinite(float(value)) for value in position)


def _orientation_ok(orientation: Vec4) -> bool:
    if len(orientation) != 4:
        return False
    if not all(math.isfinite(float(value)) for value in orientation):
        return False
    return sum(float(value) * float(value) for value in orientation) > 1.0e-12


def _camera_id_value(camera_id: int | str) -> int | None:
    try:
        value = int(str(camera_id).strip(), 10)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _validate_template(kind: str, template_resref: str, blocking: list[str]) -> None:
    if not normalise_resource_resref(template_resref):
        blocking.append(f"{kind} placement requires a template resref.")


def validate_authored_gameplay_placement(placement: AuthoredGameplayPlacement) -> AuthoredGameplayPlacementValidation:
    """Validate authored placement intent before compiling GIT/IFO bytes."""

    warnings: list[str] = []
    blocking: list[str] = []
    if not normalise_resource_resref(placement.entry_point.area_resref):
        blocking.append("Module entry point requires an area resref.")
    if not _position_ok(placement.entry_point.position):
        blocking.append("Module entry point position must contain finite XYZ values.")
    for creature in placement.creatures:
        _validate_template("Creature", creature.template_resref, blocking)
        if not _position_ok(creature.position):
            blocking.append(f"Creature {creature.template_resref or '(missing)'} has an invalid position.")
    for door in placement.doors:
        _validate_template("Door", door.template_resref, blocking)
        if not _position_ok(door.position):
            blocking.append(f"Door {door.template_resref or '(missing)'} has an invalid position.")
    for trigger in placement.triggers:
        _validate_template("Trigger", trigger.template_resref, blocking)
        if not _position_ok(trigger.position):
            blocking.append(f"Trigger {trigger.template_resref or '(missing)'} has an invalid position.")
        if not trigger.geometry:
            warnings.append(f"Trigger {trigger.template_resref or trigger.tag or '(unnamed)'} has no polygon geometry yet.")
        for point in trigger.geometry:
            if not _position_ok(point):
                blocking.append(f"Trigger {trigger.template_resref or '(missing)'} has invalid polygon geometry.")
                break
    for placeable in placement.placeables:
        _validate_template("Placeable", placeable.template_resref, blocking)
        if not _position_ok(placeable.position):
            blocking.append(f"Placeable {placeable.template_resref or '(missing)'} has an invalid position.")
    for waypoint in placement.waypoints:
        _validate_template("Waypoint", waypoint.template_resref, blocking)
        if not _position_ok(waypoint.position):
            blocking.append(f"Waypoint {waypoint.template_resref or '(missing)'} has an invalid position.")
    for encounter in placement.encounters:
        _validate_template("Encounter", encounter.template_resref, blocking)
        if not _position_ok(encounter.position):
            blocking.append(f"Encounter {encounter.template_resref or '(missing)'} has an invalid position.")
    for sound in placement.sounds:
        _validate_template("Sound", sound.template_resref, blocking)
        if not _position_ok(sound.position):
            blocking.append(f"Sound {sound.template_resref or '(missing)'} has an invalid position.")
    for camera in placement.cameras:
        if _camera_id_value(camera.camera_id) is None:
            blocking.append("Camera placement requires a non-negative numeric camera id.")
        if not _position_ok(camera.position):
            blocking.append(f"Camera {camera.camera_id or '(missing)'} has an invalid position.")
        if not _orientation_ok(camera.orientation):
            blocking.append(f"Camera {camera.camera_id or '(missing)'} has an invalid orientation quaternion.")
        if not math.isfinite(float(camera.field_of_view)) or float(camera.field_of_view) < 0.0:
            blocking.append(f"Camera {camera.camera_id or '(missing)'} has an invalid field of view.")
        if not math.isfinite(float(camera.height)):
            blocking.append(f"Camera {camera.camera_id or '(missing)'} has an invalid height.")
        if not math.isfinite(float(camera.mic_range)):
            blocking.append(f"Camera {camera.camera_id or '(missing)'} has an invalid mic range.")
        if not math.isfinite(float(camera.pitch)):
            blocking.append(f"Camera {camera.camera_id or '(missing)'} has an invalid pitch.")
    for store in placement.stores:
        _validate_template("Store", store.template_resref, blocking)
    return AuthoredGameplayPlacementValidation(
        ok=not blocking,
        warnings=tuple(warnings),
        blocking_issues=tuple(blocking),
    )


def _empty_gff_list() -> Any:
    from pykotor.resource.formats.gff.gff_data import GFFList

    return GFFList()


def _new_gff(content_name: str) -> Any:
    from pykotor.resource.formats.gff import GFF
    from pykotor.resource.formats.gff.gff_data import GFFContent

    return GFF(getattr(GFFContent, content_name))


def _bytes_gff(gff: Any) -> bytes:
    from pykotor.resource.formats.gff import bytes_gff

    return bytes_gff(gff)


def apply_entry_point_to_ifo(root: Any, entry: ModuleEntryPoint) -> None:
    """Write authored player start data to an IFO root struct."""

    root.set_resref("Mod_Entry_Area", entry.area_resref)
    root.set_single("Mod_Entry_X", float(entry.position[0]))
    root.set_single("Mod_Entry_Y", float(entry.position[1]))
    root.set_single("Mod_Entry_Z", float(entry.position[2]))
    root.set_single("Mod_Entry_Dir_X", math.cos(float(entry.facing)))
    root.set_single("Mod_Entry_Dir_Y", math.sin(float(entry.facing)))


def _add_placeable(list_value: Any, index: int, placeable: AuthoredPlaceableInstance) -> None:
    item = list_value.add(index)
    resref = normalise_resource_resref(placeable.template_resref)
    item.set_resref("TemplateResRef", resref)
    item.set_string("Tag", placeable.tag or resref)
    item.set_single("X", float(placeable.position[0]))
    item.set_single("Y", float(placeable.position[1]))
    item.set_single("Z", float(placeable.position[2]))
    item.set_single("Bearing", float(placeable.bearing))


def _add_creature(list_value: Any, index: int, creature: AuthoredCreatureInstance) -> None:
    item = list_value.add(index)
    resref = normalise_resource_resref(creature.template_resref)
    item.set_resref("TemplateResRef", resref)
    item.set_string("Tag", creature.tag or resref)
    item.set_single("XPosition", float(creature.position[0]))
    item.set_single("YPosition", float(creature.position[1]))
    item.set_single("ZPosition", float(creature.position[2]))
    item.set_single("XOrientation", float(creature.bearing))
    item.set_single("Bearing", float(creature.bearing))


def _add_door(list_value: Any, index: int, door: AuthoredDoorInstance) -> None:
    item = list_value.add(index)
    resref = normalise_resource_resref(door.template_resref)
    item.set_resref("TemplateResRef", resref)
    item.set_string("Tag", door.tag or resref)
    item.set_single("X", float(door.position[0]))
    item.set_single("Y", float(door.position[1]))
    item.set_single("Z", float(door.position[2]))
    item.set_single("Bearing", float(door.bearing))
    item.set_string("LinkedTo", door.linked_to)
    item.set_string("LinkedToModule", door.linked_to_module)
    item.set_int32("TransitionDestin", int(door.transition_destination))


def _add_trigger_geometry(list_value: Any, points: tuple[Vec3, ...]) -> None:
    for index, point in enumerate(points):
        item = list_value.add(index)
        item.set_single("PointX", float(point[0]))
        item.set_single("PointY", float(point[1]))
        item.set_single("PointZ", float(point[2]))


def _add_trigger(list_value: Any, index: int, trigger: AuthoredTriggerInstance) -> None:
    item = list_value.add(index)
    resref = normalise_resource_resref(trigger.template_resref)
    item.set_resref("TemplateResRef", resref)
    item.set_string("Tag", trigger.tag or resref)
    item.set_single("XPosition", float(trigger.position[0]))
    item.set_single("YPosition", float(trigger.position[1]))
    item.set_single("ZPosition", float(trigger.position[2]))
    item.set_string("LinkedTo", trigger.linked_to)
    item.set_string("LinkedToModule", trigger.linked_to_module)
    item.set_int32("TransitionDestin", int(trigger.transition_destination))
    geometry = _empty_gff_list()
    _add_trigger_geometry(geometry, trigger.geometry)
    item.set_list("Geometry", geometry)


def _add_waypoint(list_value: Any, index: int, waypoint: AuthoredWaypointInstance) -> None:
    item = list_value.add(index)
    resref = normalise_resource_resref(waypoint.template_resref)
    item.set_resref("TemplateResRef", resref)
    item.set_string("Tag", waypoint.tag or resref)
    item.set_string("LinkedTo", waypoint.linked_to)
    item.set_single("XPosition", float(waypoint.position[0]))
    item.set_single("YPosition", float(waypoint.position[1]))
    item.set_single("ZPosition", float(waypoint.position[2]))
    item.set_single("XOrientation", float(waypoint.bearing))
    item.set_single("Bearing", float(waypoint.bearing))


def _add_encounter(list_value: Any, index: int, encounter: AuthoredEncounterInstance) -> None:
    item = list_value.add(index)
    resref = normalise_resource_resref(encounter.template_resref)
    item.set_resref("TemplateResRef", resref)
    item.set_string("Tag", encounter.tag or resref)
    item.set_single("XPosition", float(encounter.position[0]))
    item.set_single("YPosition", float(encounter.position[1]))
    item.set_single("ZPosition", float(encounter.position[2]))


def _add_sound(list_value: Any, index: int, sound: AuthoredSoundInstance) -> None:
    item = list_value.add(index)
    resref = normalise_resource_resref(sound.template_resref)
    item.set_resref("TemplateResRef", resref)
    item.set_string("Tag", sound.tag or resref)
    item.set_single("XPosition", float(sound.position[0]))
    item.set_single("YPosition", float(sound.position[1]))
    item.set_single("ZPosition", float(sound.position[2]))


def _add_camera(list_value: Any, index: int, camera: AuthoredCameraInstance) -> None:
    from utility.common.geometry import Vector3, Vector4

    item = list_value.add(index)
    item.set_int32("CameraID", _camera_id_value(camera.camera_id) or 0)
    item.set_single("FieldOfView", float(camera.field_of_view))
    item.set_single("Height", float(camera.height))
    item.set_single("MicRange", float(camera.mic_range))
    item.set_vector4("Orientation", Vector4(*camera.orientation))
    item.set_vector3("Position", Vector3(*camera.position))
    item.set_single("Pitch", float(camera.pitch))


def _add_store(list_value: Any, index: int, store: AuthoredStoreInstance) -> None:
    item = list_value.add(index)
    resref = normalise_resource_resref(store.template_resref)
    item.set_resref("TemplateResRef", resref)
    item.set_string("Tag", store.tag or resref)


def build_git_gff(placement: AuthoredGameplayPlacement) -> Any:
    """Compile authored gameplay placements into a GIT GFF."""

    validation = validate_authored_gameplay_placement(placement)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    gff = _new_gff("GIT")
    root = gff.root
    root.set_uint8("UseTemplates", 1)

    cameras = _empty_gff_list()
    for index, camera in enumerate(placement.cameras):
        _add_camera(cameras, index, camera)
    root.set_list("CameraList", cameras)

    creatures = _empty_gff_list()
    for index, creature in enumerate(placement.creatures):
        _add_creature(creatures, index, creature)
    root.set_list("Creature List", creatures)

    doors = _empty_gff_list()
    for index, door in enumerate(placement.doors):
        _add_door(doors, index, door)
    root.set_list("Door List", doors)

    triggers = _empty_gff_list()
    for index, trigger in enumerate(placement.triggers):
        _add_trigger(triggers, index, trigger)
    root.set_list("TriggerList", triggers)

    encounters = _empty_gff_list()
    for index, encounter in enumerate(placement.encounters):
        _add_encounter(encounters, index, encounter)
    root.set_list("Encounter List", encounters)

    sounds = _empty_gff_list()
    for index, sound in enumerate(placement.sounds):
        _add_sound(sounds, index, sound)
    root.set_list("SoundList", sounds)

    stores = _empty_gff_list()
    for index, store in enumerate(placement.stores):
        _add_store(stores, index, store)
    root.set_list("StoreList", stores)

    placeables = _empty_gff_list()
    for index, placeable in enumerate(placement.placeables):
        _add_placeable(placeables, index, placeable)
    root.set_list("Placeable List", placeables)

    waypoints = _empty_gff_list()
    for index, waypoint in enumerate(placement.waypoints):
        _add_waypoint(waypoints, index, waypoint)
    root.set_list("WaypointList", waypoints)
    return gff


def build_git_bytes(placement: AuthoredGameplayPlacement) -> bytes:
    """Compile authored gameplay placements into serialized GIT bytes."""

    return _bytes_gff(build_git_gff(placement))


__all__ = [
    "AuthoredCameraInstance",
    "AuthoredCreatureInstance",
    "AuthoredDoorInstance",
    "AuthoredEncounterInstance",
    "AuthoredGameplayPlacement",
    "AuthoredGameplayPlacementValidation",
    "AuthoredPlaceableInstance",
    "AuthoredSoundInstance",
    "AuthoredStoreInstance",
    "AuthoredTriggerInstance",
    "AuthoredWaypointInstance",
    "ModuleEntryPoint",
    "apply_entry_point_to_ifo",
    "build_git_bytes",
    "build_git_gff",
    "normalise_resource_resref",
    "validate_authored_gameplay_placement",
]
