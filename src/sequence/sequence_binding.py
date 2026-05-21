"""Stable scene-object bindings for sequence tracks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

from .sequence_track import SequenceTrack


class SequenceTargetType(str, Enum):
    MESH = "Mesh"
    CAMERA = "Camera"
    LIGHT = "Light"
    CHARACTER = "Character"
    RIG = "Rig"
    PROP = "Prop"
    HELPER = "Helper"
    GROUP = "Group"
    UNKNOWN = "Unknown"


class SequenceBindingType(str, Enum):
    POSSESSABLE = "Possessable"
    SPAWNABLE = "Spawnable"
    GENERATED = "Generated"


@dataclass
class SequenceBinding:
    binding_id: str = field(default_factory=lambda: f"binding-{uuid4().hex}")
    display_name: str = "Binding"
    target_object_id: str = ""
    target_object_name: str = ""
    target_type: SequenceTargetType | str = SequenceTargetType.UNKNOWN
    binding_type: SequenceBindingType | str = SequenceBindingType.POSSESSABLE
    tracks: list[SequenceTrack] = field(default_factory=list)
    active: bool = True
    locked: bool = False
    color: str = "#7A9A88"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.target_type, SequenceTargetType):
            try:
                self.target_type = SequenceTargetType(str(self.target_type))
            except ValueError:
                self.target_type = SequenceTargetType.UNKNOWN
        if not isinstance(self.binding_type, SequenceBindingType):
            try:
                self.binding_type = SequenceBindingType(str(self.binding_type))
            except ValueError:
                self.binding_type = SequenceBindingType.POSSESSABLE
        self.tracks = [
            track if isinstance(track, SequenceTrack) else SequenceTrack.deserialize(track)
            for track in (self.tracks or [])
        ]
        for track in self.tracks:
            track.parent_binding_id = self.binding_id

    @property
    def missing(self) -> bool:
        return bool(self.metadata.get("missing", False))

    def add_track(self, track: SequenceTrack) -> SequenceTrack:
        track.parent_binding_id = self.binding_id
        self.tracks.append(track)
        return track

    def remove_track(self, track_id: str) -> bool:
        before = len(self.tracks)
        self.tracks = [track for track in self.tracks if track.track_id != track_id]
        return len(self.tracks) != before

    def serialize(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "display_name": self.display_name,
            "target_object_id": self.target_object_id,
            "target_object_name": self.target_object_name,
            "target_type": self.target_type.value if isinstance(self.target_type, SequenceTargetType) else str(self.target_type),
            "binding_type": self.binding_type.value if isinstance(self.binding_type, SequenceBindingType) else str(self.binding_type),
            "tracks": [track.serialize() for track in self.tracks],
            "active": bool(self.active),
            "locked": bool(self.locked),
            "color": self.color,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "SequenceBinding":
        payload = dict(data or {})
        return cls(
            binding_id=str(payload.get("binding_id") or f"binding-{uuid4().hex}"),
            display_name=str(payload.get("display_name") or payload.get("target_object_name") or "Binding"),
            target_object_id=str(payload.get("target_object_id") or ""),
            target_object_name=str(payload.get("target_object_name") or ""),
            target_type=payload.get("target_type", SequenceTargetType.UNKNOWN.value),
            binding_type=payload.get("binding_type", SequenceBindingType.POSSESSABLE.value),
            tracks=[SequenceTrack.deserialize(item) for item in payload.get("tracks", []) or []],
            active=bool(payload.get("active", True)),
            locked=bool(payload.get("locked", False)),
            color=str(payload.get("color") or "#7A9A88"),
            metadata=dict(payload.get("metadata", {}) or {}),
        )
