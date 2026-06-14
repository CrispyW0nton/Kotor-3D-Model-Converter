"""Boolean visibility track."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..sequence_keyframe import InterpolationMode
from ..sequence_track import SequenceTrack, register_track


@register_track
@dataclass
class VisibilityTrack(SequenceTrack):
    TRACK_TYPE = "Visibility"

    def __post_init__(self) -> None:
        self.track_type = self.TRACK_TYPE
        if not self.name or self.name == "Track":
            self.name = "Visibility"
        super().__post_init__()

    def default_interpolation(self) -> InterpolationMode:
        return InterpolationMode.CONSTANT

    def evaluate(self, frame: int) -> bool | None:
        value = super().evaluate(frame)
        return None if value is None else bool(value)

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "VisibilityTrack":
        payload = dict(data or {})
        return cls(
            track_id=str(payload.get("track_id") or ""),
            name=str(payload.get("name") or "Visibility"),
            track_type=cls.TRACK_TYPE,
            enabled=bool(payload.get("enabled", True)),
            muted=bool(payload.get("muted", False)),
            locked=bool(payload.get("locked", False)),
            expanded=bool(payload.get("expanded", True)),
            color=str(payload.get("color") or "#FFAA00"),
            keyframes=payload.get("keyframes", []) or [],
            parent_binding_id=str(payload.get("parent_binding_id") or ""),
            metadata=dict(payload.get("metadata", {}) or {}),
        )
