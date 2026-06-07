"""Percent snapping for scale tools."""

from __future__ import annotations

from typing import Iterable


class PercentSnap:
    def __init__(self, enabled: bool = False, increment_percent: float = 10.0):
        self.enabled = bool(enabled)
        self.increment_percent = 10.0
        self.set_increment_percent(increment_percent)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def set_increment_percent(self, value: float) -> None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 10.0
        self.increment_percent = max(1e-6, min(numeric, 1000.0))

    def snap_percent(self, value: float) -> float:
        if not self.enabled:
            return float(value)
        inc = self.increment_percent
        return round(float(value) / inc) * inc

    def snap_scale_factor(self, scale_factor: float) -> float:
        if not self.enabled:
            return max(0.001, float(scale_factor))
        percent = max(0.001, float(scale_factor)) * 100.0
        return max(0.001, self.snap_percent(percent) / 100.0)

    def apply_to_scale(self, scale_vector: Iterable[float]):
        return tuple(self.snap_scale_factor(float(value)) for value in scale_vector)
