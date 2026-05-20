"""Viewport grid measurement helpers."""

from __future__ import annotations

import math

from .measurement_formatter import MeasurementFormatter
from .unit_system import UnitSystem


class GridMeasurement:
    def __init__(
        self,
        unit_system: UnitSystem | None = None,
        *,
        minor_spacing: float = 10.0,
        major_spacing: float = 100.0,
        show_labels: bool = True,
        precision: int = 3,
    ):
        self.unit_system = unit_system or UnitSystem()
        self.minor_spacing = max(1e-6, float(minor_spacing))
        self.major_spacing = max(self.minor_spacing, float(major_spacing))
        self.show_labels = bool(show_labels)
        self.precision = max(0, min(int(precision), 6))

    @property
    def major_every(self) -> int:
        return max(1, int(round(self.major_spacing / self.minor_spacing)))

    def update(
        self,
        *,
        unit_system: UnitSystem | None = None,
        minor_spacing: float | None = None,
        major_spacing: float | None = None,
        show_labels: bool | None = None,
        precision: int | None = None,
    ) -> None:
        if unit_system is not None:
            self.unit_system = unit_system
        if minor_spacing is not None:
            self.minor_spacing = max(1e-6, float(minor_spacing))
        if major_spacing is not None:
            self.major_spacing = max(self.minor_spacing, float(major_spacing))
        if show_labels is not None:
            self.show_labels = bool(show_labels)
        if precision is not None:
            self.precision = max(0, min(int(precision), 6))

    def format_label(self, value_in_system_units: float) -> str:
        return MeasurementFormatter(self.unit_system, self.precision).distance(value_in_system_units)

    def label_stride(self, projected_major_px: float, max_labels: int = 10) -> int:
        if projected_major_px <= 1e-6:
            return 4
        stride = 1
        while projected_major_px * stride < 72.0:
            stride *= 2
        return max(1, min(stride, max(1, int(max_labels))))

    def extent_for_bounds(self, bounds) -> float:
        extent = self.major_spacing * 8.0
        try:
            bb_min, bb_max = bounds
            size_x = abs(float(bb_max[0]) - float(bb_min[0]))
            size_y = abs(float(bb_max[1]) - float(bb_min[1]))
            centre_x = (float(bb_min[0]) + float(bb_max[0])) * 0.5
            centre_y = (float(bb_min[1]) + float(bb_max[1])) * 0.5
            radius = max(
                size_x,
                size_y,
                abs(centre_x) + size_x * 0.5,
                abs(centre_y) + size_y * 0.5,
                self.major_spacing * 4.0,
            ) * 1.5
            major = self.major_spacing
            extent = max(major * 4.0, min(major * 80.0, math.ceil(radius / major) * major))
        except Exception:
            pass
        return extent
