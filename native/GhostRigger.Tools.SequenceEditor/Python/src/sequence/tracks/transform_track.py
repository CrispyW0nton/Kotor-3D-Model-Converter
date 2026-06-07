"""Transform animation track."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..sequence_keyframe import InterpolationMode
from ..sequence_track import SequenceTrack, register_track


def transform_value(
    location=(0.0, 0.0, 0.0),
    rotation=(0.0, 0.0, 0.0),
    scale=(1.0, 1.0, 1.0),
) -> dict[str, tuple[float, float, float]]:
    return {
        "location": tuple(float(v) for v in location[:3]),
        "rotation": tuple(float(v) for v in rotation[:3]),
        "scale": tuple(float(v) for v in scale[:3]),
    }


@register_track
@dataclass
class TransformTrack(SequenceTrack):
    TRACK_TYPE = "Transform"

    def __post_init__(self) -> None:
        self.track_type = self.TRACK_TYPE
        if not self.name or self.name == "Track":
            self.name = "Transform"
        super().__post_init__()

    def add_transform_key(
        self,
        frame: int,
        *,
        location=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
        scale=(1.0, 1.0, 1.0),
        select: bool = False,
    ):
        return self.add_keyframe(frame, transform_value(location, rotation, scale), InterpolationMode.LINEAR, select=select)

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "TransformTrack":
        payload = dict(data or {})
        return cls(
            track_id=str(payload.get("track_id") or ""),
            name=str(payload.get("name") or "Transform"),
            track_type=cls.TRACK_TYPE,
            enabled=bool(payload.get("enabled", True)),
            muted=bool(payload.get("muted", False)),
            locked=bool(payload.get("locked", False)),
            expanded=bool(payload.get("expanded", True)),
            color=str(payload.get("color") or "#00D7B5"),
            keyframes=payload.get("keyframes", []) or [],
            parent_binding_id=str(payload.get("parent_binding_id") or ""),
            metadata=dict(payload.get("metadata", {}) or {}),
        )
