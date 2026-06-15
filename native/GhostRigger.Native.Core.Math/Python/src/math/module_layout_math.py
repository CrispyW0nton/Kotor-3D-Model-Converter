"""Module layout placement helpers."""

from __future__ import annotations

from typing import Iterable


def module_anchor_relative_position(
    room_lyt_position: Iterable[float],
    anchor_lyt_position: Iterable[float],
    anchor_scene_position: Iterable[float],
) -> tuple[float, float, float]:
    """Place a room from its LYT delta relative to the scene anchor."""

    room = tuple(float(v) for v in tuple(room_lyt_position)[:3])
    anchor_lyt = tuple(float(v) for v in tuple(anchor_lyt_position)[:3])
    anchor_scene = tuple(float(v) for v in tuple(anchor_scene_position)[:3])
    if len(room) != 3 or len(anchor_lyt) != 3 or len(anchor_scene) != 3:
        raise ValueError("Module placement positions must contain three coordinates.")
    return tuple(anchor_scene[index] + (room[index] - anchor_lyt[index]) for index in range(3))


__all__ = ("module_anchor_relative_position",)
