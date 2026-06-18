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
class AuthoredWaypointInstance:
    """Authored waypoint/start marker for a GIT WaypointList entry."""

    template_resref: str
    tag: str = ""
    position: Vec3 = (0.0, 0.0, 0.0)
    bearing: float = 0.0
    linked_to: str = ""


@dataclass(frozen=True)
class AuthoredGameplayPlacement:
    """Compiled gameplay placements for one authored module."""

    entry_point: ModuleEntryPoint
    placeables: tuple[AuthoredPlaceableInstance, ...] = ()
    waypoints: tuple[AuthoredWaypointInstance, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


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
    item.set_resref("TemplateResRef", placeable.template_resref)
    item.set_string("Tag", placeable.tag or placeable.template_resref)
    item.set_single("X", float(placeable.position[0]))
    item.set_single("Y", float(placeable.position[1]))
    item.set_single("Z", float(placeable.position[2]))
    item.set_single("Bearing", float(placeable.bearing))


def _add_waypoint(list_value: Any, index: int, waypoint: AuthoredWaypointInstance) -> None:
    item = list_value.add(index)
    item.set_resref("TemplateResRef", waypoint.template_resref)
    item.set_string("Tag", waypoint.tag or waypoint.template_resref)
    item.set_string("LinkedTo", waypoint.linked_to)
    item.set_single("XPosition", float(waypoint.position[0]))
    item.set_single("YPosition", float(waypoint.position[1]))
    item.set_single("ZPosition", float(waypoint.position[2]))
    item.set_single("XOrientation", float(waypoint.bearing))
    item.set_single("Bearing", float(waypoint.bearing))


def build_git_gff(placement: AuthoredGameplayPlacement) -> Any:
    """Compile authored gameplay placements into a GIT GFF."""

    gff = _new_gff("GIT")
    root = gff.root
    root.set_uint8("UseTemplates", 1)
    for label in (
        "Creature List",
        "Door List",
        "Encounter List",
        "SoundList",
        "StoreList",
        "TriggerList",
    ):
        root.set_list(label, _empty_gff_list())

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
    "AuthoredGameplayPlacement",
    "AuthoredPlaceableInstance",
    "AuthoredWaypointInstance",
    "ModuleEntryPoint",
    "apply_entry_point_to_ifo",
    "build_git_bytes",
    "build_git_gff",
]
