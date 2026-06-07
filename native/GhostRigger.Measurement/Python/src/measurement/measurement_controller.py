"""Simple non-destructive viewport distance measurement tool."""

from __future__ import annotations

import math

from .measurement_formatter import MeasurementFormatter
from .unit_system import UnitSystem


Vec3 = tuple[float, float, float]


class MeasurementController:
    def __init__(self, unit_system: UnitSystem | None = None, precision: int = 3):
        self.unit_system = unit_system or UnitSystem()
        self.precision = max(0, min(int(precision), 6))
        self.point_a: Vec3 | None = None
        self.point_b: Vec3 | None = None
        self.preview_point: Vec3 | None = None
        self.active = False

    def configure(self, unit_system: UnitSystem, precision: int = 3) -> None:
        self.unit_system = unit_system
        self.precision = max(0, min(int(precision), 6))

    def begin_measurement(self, world_pos) -> None:
        self.point_a = self._vec3(world_pos)
        self.point_b = None
        self.preview_point = self.point_a
        self.active = True

    def update_preview(self, world_pos) -> None:
        if self.point_a is not None:
            self.preview_point = self._vec3(world_pos)

    def finish_measurement(self, world_pos) -> None:
        if self.point_a is None:
            self.begin_measurement(world_pos)
            return
        self.point_b = self._vec3(world_pos)
        self.preview_point = self.point_b
        self.active = False

    def clear_measurement(self) -> None:
        self.point_a = None
        self.point_b = None
        self.preview_point = None
        self.active = False

    def get_delta(self) -> Vec3 | None:
        a, b = self._active_segment()
        if a is None or b is None:
            return None
        return (b[0] - a[0], b[1] - a[1], b[2] - a[2])

    def get_distance(self) -> float | None:
        delta = self.get_delta()
        if delta is None:
            return None
        return math.sqrt(delta[0] * delta[0] + delta[1] * delta[1] + delta[2] * delta[2])

    def formatted_distance(self) -> str:
        distance = self.get_distance()
        if distance is None:
            return ""
        return MeasurementFormatter(self.unit_system, self.precision).distance(distance)

    def draw_overlay(self, draw, projector, width: int, height: int) -> None:
        a, b = self._active_segment()
        if a is None or b is None:
            return
        pa = projector(a[0], a[1], a[2], width, height)
        pb = projector(b[0], b[1], b[2], width, height)
        if pa is None or pb is None:
            return
        p1 = (int(pa[0]), int(pa[1]))
        p2 = (int(pb[0]), int(pb[1]))
        draw.line([p1, p2], fill=(255, 214, 80, 230), width=2)
        r = 4
        draw.ellipse([p1[0] - r, p1[1] - r, p1[0] + r, p1[1] + r], fill=(255, 214, 80, 235))
        draw.ellipse([p2[0] - r, p2[1] - r, p2[0] + r, p2[1] + r], fill=(255, 214, 80, 235))
        label = self.formatted_distance()
        if label:
            lx = int((p1[0] + p2[0]) * 0.5) + 8
            ly = int((p1[1] + p2[1]) * 0.5) - 18
            text_box = [lx - 4, ly - 3, lx + max(54, len(label) * 8), ly + 14]
            draw.rectangle(text_box, fill=(12, 14, 18, 190), outline=(255, 214, 80, 190))
            draw.text((lx, ly), label, fill=(255, 245, 210, 255))

    def _active_segment(self) -> tuple[Vec3 | None, Vec3 | None]:
        return self.point_a, self.point_b or self.preview_point

    @staticmethod
    def _vec3(value) -> Vec3:
        return (float(value[0]), float(value[1]), float(value[2]))
