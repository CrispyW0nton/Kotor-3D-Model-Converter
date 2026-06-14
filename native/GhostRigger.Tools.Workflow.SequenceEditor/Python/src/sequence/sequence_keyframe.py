"""Keyframe primitives for GhostRigger Level Sequences."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class InterpolationMode(str, Enum):
    CONSTANT = "Constant"
    LINEAR = "Linear"
    EASE_IN = "Ease In"
    EASE_OUT = "Ease Out"
    EASE_IN_OUT = "Ease In Out"
    CUBIC = "Cubic"


@dataclass
class SequenceKeyframe:
    key_id: str = field(default_factory=lambda: f"key-{uuid4().hex}")
    frame: int = 0
    value: Any = None
    interpolation: InterpolationMode | str = InterpolationMode.LINEAR
    tangent_in: Any = None
    tangent_out: Any = None
    selected: bool = False
    locked: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.frame = int(round(float(self.frame)))
        if not isinstance(self.interpolation, InterpolationMode):
            try:
                self.interpolation = InterpolationMode(str(self.interpolation))
            except ValueError:
                self.interpolation = InterpolationMode.LINEAR

    def serialize(self) -> dict[str, Any]:
        return {
            "key_id": self.key_id,
            "frame": int(self.frame),
            "value": self.value,
            "interpolation": self.interpolation.value if isinstance(self.interpolation, InterpolationMode) else str(self.interpolation),
            "tangent_in": self.tangent_in,
            "tangent_out": self.tangent_out,
            "selected": bool(self.selected),
            "locked": bool(self.locked),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "SequenceKeyframe":
        payload = dict(data or {})
        return cls(
            key_id=str(payload.get("key_id") or f"key-{uuid4().hex}"),
            frame=int(round(float(payload.get("frame", 0) or 0))),
            value=payload.get("value"),
            interpolation=payload.get("interpolation", InterpolationMode.LINEAR.value),
            tangent_in=payload.get("tangent_in"),
            tangent_out=payload.get("tangent_out"),
            selected=bool(payload.get("selected", False)),
            locked=bool(payload.get("locked", False)),
            metadata=dict(payload.get("metadata", {}) or {}),
        )

    def duplicate(self, *, frame_offset: int = 0, selected: bool | None = None) -> "SequenceKeyframe":
        data = self.serialize()
        data["key_id"] = f"key-{uuid4().hex}"
        data["frame"] = int(self.frame) + int(frame_offset)
        if selected is not None:
            data["selected"] = bool(selected)
        return SequenceKeyframe.deserialize(data)
