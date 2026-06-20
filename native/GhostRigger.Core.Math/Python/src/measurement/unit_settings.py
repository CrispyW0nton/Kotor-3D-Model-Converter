"""Persistent measurement settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from .unit_system import normalize_unit


@dataclass
class MeasurementSettings:
    system_unit: str = "centimetres"
    display_unit: str = "centimetres"
    distance_precision: int = 3
    show_grid_measurements: bool = True
    show_selected_object_dimensions: bool = True
    snap_enabled: bool = False
    angle_snap_enabled: bool = False
    angle_snap_increment_degrees: float = 15.0
    percent_snap_enabled: bool = False
    percent_snap_increment_percent: float = 10.0
    minor_grid_spacing: float = 10.0
    major_grid_spacing: float = 100.0

    @classmethod
    def from_dict(cls, values: dict | None) -> "MeasurementSettings":
        data = dict(values or {})
        settings = cls()
        settings.system_unit = normalize_unit(data.get("system_unit", settings.system_unit))
        settings.display_unit = normalize_unit(data.get("display_unit", settings.display_unit))
        settings.distance_precision = max(0, min(int(data.get("distance_precision", 3)), 6))
        settings.show_grid_measurements = bool(data.get("show_grid_measurements", True))
        settings.show_selected_object_dimensions = bool(
            data.get("show_selected_object_dimensions", True)
        )
        settings.snap_enabled = bool(data.get("snap_enabled", False))
        settings.angle_snap_enabled = bool(data.get("angle_snap_enabled", False))
        settings.angle_snap_increment_degrees = max(
            1e-6,
            min(float(data.get("angle_snap_increment_degrees", 15.0)), 360.0),
        )
        settings.percent_snap_enabled = bool(data.get("percent_snap_enabled", False))
        settings.percent_snap_increment_percent = max(
            1e-6,
            min(float(data.get("percent_snap_increment_percent", 10.0)), 1000.0),
        )
        settings.minor_grid_spacing = max(1e-6, float(data.get("minor_grid_spacing", 10.0)))
        settings.major_grid_spacing = max(
            settings.minor_grid_spacing,
            float(data.get("major_grid_spacing", 100.0)),
        )
        return settings

    def to_dict(self) -> dict:
        return {
            "system_unit": self.system_unit,
            "display_unit": self.display_unit,
            "distance_precision": int(self.distance_precision),
            "show_grid_measurements": bool(self.show_grid_measurements),
            "show_selected_object_dimensions": bool(self.show_selected_object_dimensions),
            "snap_enabled": bool(self.snap_enabled),
            "angle_snap_enabled": bool(self.angle_snap_enabled),
            "angle_snap_increment_degrees": float(self.angle_snap_increment_degrees),
            "percent_snap_enabled": bool(self.percent_snap_enabled),
            "percent_snap_increment_percent": float(self.percent_snap_increment_percent),
            "minor_grid_spacing": float(self.minor_grid_spacing),
            "major_grid_spacing": float(self.major_grid_spacing),
        }


def load_measurement_settings(path: Path) -> MeasurementSettings:
    try:
        if path.exists():
            return MeasurementSettings.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        pass
    return MeasurementSettings()


def save_measurement_settings(path: Path, settings: MeasurementSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")
