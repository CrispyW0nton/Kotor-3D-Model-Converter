"""UI formatting helpers for measurement values."""

from __future__ import annotations

import math

from .unit_system import UnitSystem


class MeasurementFormatter:
    def __init__(self, unit_system: UnitSystem, precision: int = 3):
        self.unit_system = unit_system
        self.precision = max(0, min(int(precision), 6))

    def distance(self, value_in_system_units: float) -> str:
        return self.unit_system.format_distance(value_in_system_units, self.precision)

    def angle_degrees(self, value: float, precision: int = 2) -> str:
        precision = max(0, min(int(precision), 4))
        if precision == 0:
            text = str(int(round(float(value))))
        else:
            text = f"{float(value):.{precision}f}".rstrip("0").rstrip(".")
        return f"{text} deg"

    def scale(self, value: float) -> str:
        if not math.isfinite(float(value)):
            return "unavailable"
        return f"{float(value):.3f}".rstrip("0").rstrip(".")
