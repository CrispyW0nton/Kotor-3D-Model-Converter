"""Common scene object primitives for KMAX."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any


def _vec3(values: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
    try:
        seq = list(values)
        result = (float(seq[0]), float(seq[1]), float(seq[2]))
        if all(math.isfinite(v) for v in result):
            return result
    except Exception:
        pass
    return default


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
        return cls(
            position=_vec3(payload.get("position"), (0.0, 0.0, 0.0)),
            rotation=_vec3(payload.get("rotation"), (0.0, 0.0, 0.0)),
            scale=_vec3(payload.get("scale"), (1.0, 1.0, 1.0)),
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
        pivot = cls(
            position_local=_vec3(
                payload.get("position_local", payload.get("position")),
                (0.0, 0.0, 0.0),
            ),
            rotation_local=_vec3(
                payload.get("rotation_local", payload.get("rotation")),
                (0.0, 0.0, 0.0),
            ),
            enabled=bool(payload.get("enabled", True)),
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
