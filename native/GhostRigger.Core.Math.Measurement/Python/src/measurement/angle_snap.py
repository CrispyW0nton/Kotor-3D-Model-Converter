"""Angle snapping for viewport rotation tools."""

from __future__ import annotations

import math
from typing import Iterable


class AngleSnap:
    def __init__(self, enabled: bool = False, increment_degrees: float = 15.0):
        self.enabled = bool(enabled)
        self.increment_degrees = 15.0
        self.set_increment_degrees(increment_degrees)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def set_increment_degrees(self, value: float) -> None:
        self.increment_degrees = max(1e-6, min(float(value), 360.0))

    def snap_degrees(self, angle: float) -> float:
        if not self.enabled:
            return float(angle)
        inc = self.increment_degrees
        # Nearest-increment rounding also handles negative values correctly.
        return round(float(angle) / inc) * inc

    def snap_radians(self, angle: float) -> float:
        if not self.enabled:
            return float(angle)
        return math.radians(self.snap_degrees(math.degrees(float(angle))))

    def apply_to_euler(self, euler_angles: Iterable[float]):
        return tuple(self.snap_degrees(float(angle)) for angle in euler_angles)

    def apply_delta(self, delta_angle: float) -> float:
        return self.snap_degrees(float(delta_angle))
