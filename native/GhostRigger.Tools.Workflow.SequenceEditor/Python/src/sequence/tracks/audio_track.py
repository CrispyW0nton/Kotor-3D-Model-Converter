"""Audio cue track placeholder for cinematic timing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..sequence_track import SequenceTrack, register_track


@register_track
@dataclass
class AudioTrack(SequenceTrack):
    TRACK_TYPE = "Audio"

    def __post_init__(self) -> None:
        self.track_type = self.TRACK_TYPE
        if not self.name or self.name == "Track":
            self.name = "Audio"
        super().__post_init__()

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "AudioTrack":
        payload = dict(data or {})
        return cls(
            track_id=str(payload.get("track_id") or ""),
            name=str(payload.get("name") or "Audio"),
            track_type=cls.TRACK_TYPE,
            enabled=bool(payload.get("enabled", True)),
            muted=bool(payload.get("muted", False)),
            locked=bool(payload.get("locked", False)),
            expanded=bool(payload.get("expanded", True)),
            color=str(payload.get("color") or "#D8C66A"),
            keyframes=payload.get("keyframes", []) or [],
            parent_binding_id=str(payload.get("parent_binding_id") or ""),
            metadata=dict(payload.get("metadata", {}) or {}),
        )
