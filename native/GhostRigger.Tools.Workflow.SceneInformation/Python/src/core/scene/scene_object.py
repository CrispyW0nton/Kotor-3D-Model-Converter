"""Common scene object primitives for KMAX."""

from __future__ import annotations

from dataclasses import dataclass, field
import ctypes
import math
from typing import Any

from src.core.scene._native import native_scene


_Double3 = ctypes.c_double * 3


def _python_vec3(values: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
    try:
        seq = list(values)
        result = (float(seq[0]), float(seq[1]), float(seq[2]))
        if all(math.isfinite(v) for v in result):
            return result
    except Exception:
        pass
    return default


def _vec3(values: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
    dll = native_scene()
    if dll is not None:
        try:
            seq = list(values)
            source = _Double3(float(seq[0]), float(seq[1]), float(seq[2]))
            fallback = _Double3(*default)
            out = _Double3()
            if dll.gr_scene_sanitize_vec3(source, fallback, out):
                return (out[0], out[1], out[2])
        except (OSError, TypeError, ValueError, IndexError):
            pass
    return _python_vec3(values, default)


def _transform_defaults() -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    dll = native_scene()
    if dll is not None:
        try:
            position = _Double3()
            rotation = _Double3()
            scale = _Double3()
            if dll.gr_scene_transform_defaults(position, rotation, scale):
                return ((position[0], position[1], position[2]), (rotation[0], rotation[1], rotation[2]), (scale[0], scale[1], scale[2]))
        except OSError:
            pass
    return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 1.0, 1.0))


def _pivot_defaults() -> tuple[tuple[float, float, float], tuple[float, float, float], bool]:
    dll = native_scene()
    if dll is not None:
        try:
            position = _Double3()
            rotation = _Double3()
            enabled = ctypes.c_int()
            if dll.gr_scene_pivot_defaults(position, rotation, ctypes.byref(enabled)):
                return ((position[0], position[1], position[2]), (rotation[0], rotation[1], rotation[2]), bool(enabled.value))
        except OSError:
            pass
    return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), True)


@dataclass
class Transform:
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)

    def to_dict(self) -> dict[str, list[float]]:
        return {
            "position": [float(v) for v in self.position],
            "rotation": [float(v) for v in self.rotation],
            "scale": [float(v) for v in self.scale],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Transform":
        payload = data or {}
        default_position, default_rotation, default_scale = _transform_defaults()
        return cls(
            position=_vec3(payload.get("position"), default_position),
            rotation=_vec3(payload.get("rotation"), default_rotation),
            scale=_vec3(payload.get("scale"), default_scale),
        )


@dataclass
class PivotData:
    """Editable local pivot data persisted with each KMAX scene object."""

    position_local: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_local: tuple[float, float, float] = (0.0, 0.0, 0.0)
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def position(self) -> tuple[float, float, float]:
        return self.position_local

    @position.setter
    def position(self, value: Any) -> None:
        self.position_local = _vec3(value, (0.0, 0.0, 0.0))

    @property
    def rotation(self) -> tuple[float, float, float]:
        return self.rotation_local

    @rotation.setter
    def rotation(self, value: Any) -> None:
        self.rotation_local = _vec3(value, (0.0, 0.0, 0.0))

    def is_valid(self) -> bool:
        dll = native_scene()
        if dll is not None:
            try:
                return bool(dll.gr_scene_pivot_values_are_valid(_Double3(*self.position_local), _Double3(*self.rotation_local)))
            except (OSError, TypeError, ValueError):
                pass
        values = (*self.position_local, *self.rotation_local)
        return all(math.isfinite(float(v)) for v in values)

    def sanitized(self) -> "PivotData":
        if self.is_valid():
            return self
        return PivotData(metadata={"warning": "Invalid pivot values were reset to defaults."})

    def to_dict(self) -> dict[str, Any]:
        pivot = self.sanitized()
        return {
            "position_local": [float(v) for v in pivot.position_local],
            "rotation_local": [float(v) for v in pivot.rotation_local],
            "enabled": bool(pivot.enabled),
            "metadata": dict(pivot.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PivotData":
        payload = data or {}
        default_position, default_rotation, default_enabled = _pivot_defaults()
        pivot = cls(
            position_local=_vec3(
                payload.get("position_local", payload.get("position")),
                default_position,
            ),
            rotation_local=_vec3(
                payload.get("rotation_local", payload.get("rotation")),
                default_rotation,
            ),
            enabled=bool(payload.get("enabled", default_enabled)),
            metadata=dict(payload.get("metadata") or {}),
        )
        return pivot.sanitized()


@dataclass
class SceneObject:
    id: str
    name: str
    object_type: str = "model"
    visible: bool = True
    locked: bool = False
    selected: bool = False
    group_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
