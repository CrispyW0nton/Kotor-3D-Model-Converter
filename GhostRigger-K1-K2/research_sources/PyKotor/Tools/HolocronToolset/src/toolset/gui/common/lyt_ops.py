"""Shared LYT element helpers used by Toolset editors and Blender integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Union, cast

from pykotor.resource.formats.lyt import LYTDoorHook, LYTObstacle, LYTRoom, LYTTrack

if TYPE_CHECKING:
    from typing_extensions import TypeAlias

    from pykotor.resource.formats.lyt import LYT
    from utility.common.geometry import Vector3


class LYTBlenderControllerLike(Protocol):
    def add_room(self, model: str, x: float, y: float, z: float) -> None: ...
    def add_door_hook(
        self,
        room: str,
        door: str,
        x: float,
        y: float,
        z: float,
        *,
        orientation: tuple[float, float, float, float],
    ) -> None: ...
    def add_track(self, model: str, x: float, y: float, z: float) -> None: ...
    def add_obstacle(self, model: str, x: float, y: float, z: float) -> None: ...


LYTElement: TypeAlias = Union[LYTRoom, LYTDoorHook, LYTTrack, LYTObstacle]

_BLENDER_TYPE_BY_ELEMENT: dict[type[LYTElement], str] = {
    LYTRoom: "room",
    LYTDoorHook: "door_hook",
    LYTTrack: "track",
    LYTObstacle: "obstacle",
}

_BLENDER_PREFIX_BY_ELEMENT: dict[type[LYTElement], str] = {
    LYTRoom: "Room",
    LYTDoorHook: "DoorHook",
    LYTTrack: "Track",
    LYTObstacle: "Obstacle",
}


def _lyt_element_target_list(lyt: LYT, element: LYTElement) -> list[LYTElement]:
    """Return owning LYT collection for a given element instance."""
    if isinstance(element, LYTRoom):
        return cast("list[LYTElement]", lyt.rooms)
    if isinstance(element, LYTDoorHook):
        return cast("list[LYTElement]", lyt.doorhooks)
    if isinstance(element, LYTTrack):
        return cast("list[LYTElement]", lyt.tracks)
    return cast("list[LYTElement]", lyt.obstacles)


def _lyt_element_name_for_object(element: LYTElement) -> str:
    """Return display/object name (door name for doorhooks, model otherwise)."""
    return cast("str", element.door if isinstance(element, LYTDoorHook) else element.model)


def _lyt_element_xyz(element: LYTElement) -> tuple[float, float, float]:
    """Extract XYZ position tuple from element."""
    return element.position.x, element.position.y, element.position.z


def lyt_element_name(element: LYTElement) -> str:
    """Return canonical element name used in list/detail UI."""
    return _lyt_element_name_for_object(element)


def lyt_element_kind_name(element: LYTElement) -> str:
    """Return simple runtime class name for element type."""
    return type(element).__name__


def duplicate_lyt_element_with_offset(lyt: LYT, element: LYTElement, offset: Vector3) -> LYTElement:
    """Duplicate a LYT element, append it to layout, and offset its position."""
    if isinstance(element, LYTRoom):
        new_element = LYTRoom(f"{element.model}_copy", element.position + offset)
        lyt.rooms.append(new_element)
        return new_element

    if isinstance(element, LYTDoorHook):
        new_element = LYTDoorHook(element.room, f"{element.door}_copy", element.position + offset, element.orientation)
        lyt.doorhooks.append(new_element)
        return new_element

    if isinstance(element, LYTTrack):
        new_element = LYTTrack(f"{element.model}_copy", element.position + offset)
        lyt.tracks.append(new_element)
        return new_element

    new_element = LYTObstacle(f"{element.model}_copy", element.position + offset)
    lyt.obstacles.append(new_element)
    return new_element


def remove_lyt_element(lyt: LYT, element: LYTElement) -> None:
    """Remove element from its owning collection inside layout."""
    _lyt_element_target_list(lyt, element).remove(element)


def lyt_element_blender_type(element: LYTElement) -> str:
    """Return blender element type label."""
    return _BLENDER_TYPE_BY_ELEMENT[type(element)]


def lyt_element_blender_object_name(element: LYTElement) -> str:
    """Return deterministic blender object name for element."""
    prefix = _BLENDER_PREFIX_BY_ELEMENT[type(element)]
    return f"{prefix}_{_lyt_element_name_for_object(element)}"


def add_lyt_element_to_blender(controller: LYTBlenderControllerLike, element: LYTElement) -> None:
    """Dispatch element creation to blender controller using element type."""
    x, y, z = _lyt_element_xyz(element)

    if isinstance(element, LYTRoom):
        controller.add_room(element.model, x, y, z)
        return

    if isinstance(element, LYTDoorHook):
        controller.add_door_hook(
            element.room,
            element.door,
            x,
            y,
            z,
            orientation=(element.orientation.x, element.orientation.y, element.orientation.z, element.orientation.w),
        )
        return

    if isinstance(element, LYTTrack):
        controller.add_track(element.model, x, y, z)
        return

    controller.add_obstacle(element.model, x, y, z)
