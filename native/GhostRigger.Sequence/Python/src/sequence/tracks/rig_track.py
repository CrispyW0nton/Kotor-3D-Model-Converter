"""Rig-control extension track stubs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..sequence_track import SequenceTrack, register_track


@register_track
@dataclass
class RigTrack(SequenceTrack):
    TRACK_TYPE = "Rig Control"

    def __post_init__(self) -> None:
        self.track_type = self.TRACK_TYPE
        self.metadata.setdefault("implementation_status", "Basic rig-control key storage; bone/controller evaluation plugs in when skeletal editing is available.")
        if not self.name or self.name == "Track":
            self.name = "Rig Control"
        super().__post_init__()

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "RigTrack":
        payload = dict(data or {})
        return cls(
            track_id=str(payload.get("track_id") or ""),
            name=str(payload.get("name") or "Rig Control"),
            track_type=cls.TRACK_TYPE,
            enabled=bool(payload.get("enabled", True)),
            muted=bool(payload.get("muted", False)),
            locked=bool(payload.get("locked", False)),
            expanded=bool(payload.get("expanded", True)),
            color=str(payload.get("color") or "#00FF7A"),
            keyframes=payload.get("keyframes", []) or [],
            parent_binding_id=str(payload.get("parent_binding_id") or ""),
            metadata=dict(payload.get("metadata", {}) or {}),
        )
