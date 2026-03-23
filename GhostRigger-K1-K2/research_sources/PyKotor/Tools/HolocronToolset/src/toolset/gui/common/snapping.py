"""Snap values, Vector3, and angles to a grid step for level/indoor editing."""

from __future__ import annotations

import math

from utility.common.geometry import Vector3


def snap_value(value: float, step: float | None, *, enabled: bool = True) -> float:
    if not enabled or step is None or step <= 0:
        return value
    return round(value / step) * step


def snap_vector3(
    value: Vector3,
    step: float | None,
    *,
    enabled: bool = True,
    snap_x: bool = True,
    snap_y: bool = True,
    snap_z: bool = True,
) -> Vector3:
    if not enabled or step is None or step <= 0:
        return Vector3(value.x, value.y, value.z)

    return Vector3(
        snap_value(value.x, step, enabled=snap_x),
        snap_value(value.y, step, enabled=snap_y),
        snap_value(value.z, step, enabled=snap_z),
    )


def snap_radians(angle_radians: float, step_degrees: float | None, *, enabled: bool = True) -> float:
    if not enabled or step_degrees is None or step_degrees <= 0:
        return angle_radians

    step_radians = math.radians(step_degrees)
    if step_radians <= 0:
        return angle_radians
    return round(angle_radians / step_radians) * step_radians


def snap_degrees(angle_degrees: float, step_degrees: float | None, *, enabled: bool = True) -> float:
    if not enabled or step_degrees is None or step_degrees <= 0:
        return angle_degrees
    return round(angle_degrees / step_degrees) * step_degrees
