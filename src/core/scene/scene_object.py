"""Common scene object primitives for KMAX."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _vec3(values: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
    try:
        seq = list(values)
        return (float(seq[0]), float(seq[1]), float(seq[2]))
    except Exception:
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
class SceneObject:
    id: str
    name: str
    object_type: str = "model"
    visible: bool = True
    locked: bool = False
    selected: bool = False
    group_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
