"""Safe named-event track."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..sequence_keyframe import InterpolationMode
from ..sequence_track import SequenceTrack, register_track


@register_track
@dataclass
class EventTrack(SequenceTrack):
    TRACK_TYPE = "Event"

    @property
    def supports_duplicate_frames(self) -> bool:
        return True

    def __post_init__(self) -> None:
        self.track_type = self.TRACK_TYPE
        if not self.name or self.name == "Track":
            self.name = "Events"
        super().__post_init__()

    def default_interpolation(self) -> InterpolationMode:
        return InterpolationMode.CONSTANT

    def add_event_key(
        self,
        frame: int,
        event_name: str,
        parameters: dict[str, Any] | None = None,
        *,
        fire_during_scrub: bool = False,
        enabled: bool = True,
    ):
        return self.add_keyframe(
            frame,
            {
                "event_name": str(event_name or "Event"),
                "frame": int(frame),
                "parameters": dict(parameters or {}),
                "fire_during_scrub": bool(fire_during_scrub),
                "enabled": bool(enabled),
            },
            InterpolationMode.CONSTANT,
        )

    def events_between(self, previous_frame: int, current_frame: int, *, scrubbing: bool = False) -> list[dict[str, Any]]:
        lo, hi = sorted((int(previous_frame), int(current_frame)))
        events: list[dict[str, Any]] = []
        for key in self.keyframes:
            if lo < int(key.frame) <= hi:
                value = dict(key.value or {})
                if not value.get("enabled", True):
                    continue
                if scrubbing and not value.get("fire_during_scrub", False):
                    continue
                events.append(value)
        return events

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "EventTrack":
        payload = dict(data or {})
        return cls(
            track_id=str(payload.get("track_id") or ""),
            name=str(payload.get("name") or "Events"),
            track_type=cls.TRACK_TYPE,
            enabled=bool(payload.get("enabled", True)),
            muted=bool(payload.get("muted", False)),
            locked=bool(payload.get("locked", False)),
            expanded=bool(payload.get("expanded", True)),
            color=str(payload.get("color") or "#FF8040"),
            keyframes=payload.get("keyframes", []) or [],
            parent_binding_id=str(payload.get("parent_binding_id") or ""),
            metadata=dict(payload.get("metadata", {}) or {}),
        )
