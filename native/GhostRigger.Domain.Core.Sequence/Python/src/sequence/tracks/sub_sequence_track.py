"""Sub-sequence track."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from ..sequence_track import SequenceTrack, register_track


@dataclass
class SubSequenceSection:
    section_id: str = field(default_factory=lambda: f"subseq-{uuid4().hex}")
    sequence_asset_path: str = ""
    sequence_id: str = ""
    start_frame: int = 0
    end_frame: int = 120
    child_start_frame: int = 0
    muted: bool = False
    display_name: str = "Sub Sequence"

    def contains(self, frame: int) -> bool:
        return int(self.start_frame) <= int(frame) < int(self.end_frame)

    def child_frame_for(self, parent_frame: int) -> int:
        return int(self.child_start_frame) + (int(parent_frame) - int(self.start_frame))

    def serialize(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "SubSequenceSection":
        payload = dict(data or {})
        return cls(
            section_id=str(payload.get("section_id") or f"subseq-{uuid4().hex}"),
            sequence_asset_path=str(payload.get("sequence_asset_path") or ""),
            sequence_id=str(payload.get("sequence_id") or ""),
            start_frame=int(payload.get("start_frame", 0) or 0),
            end_frame=int(payload.get("end_frame", 120) or 120),
            child_start_frame=int(payload.get("child_start_frame", 0) or 0),
            muted=bool(payload.get("muted", False)),
            display_name=str(payload.get("display_name") or "Sub Sequence"),
        )


@register_track
@dataclass
class SubSequenceTrack(SequenceTrack):
    TRACK_TYPE = "Sub Sequence"
    sections: list[SubSequenceSection] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.track_type = self.TRACK_TYPE
        if not self.name or self.name == "Track":
            self.name = "Sub Sequences"
        super().__post_init__()
        self.sections = [section if isinstance(section, SubSequenceSection) else SubSequenceSection.deserialize(section) for section in (self.sections or self.metadata.get("sections", []) or [])]

    def serialize(self) -> dict[str, Any]:
        data = super().serialize()
        data["sections"] = [section.serialize() for section in self.sections]
        data["metadata"]["sections"] = data["sections"]
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "SubSequenceTrack":
        payload = dict(data or {})
        sections = payload.get("sections", dict(payload.get("metadata", {}) or {}).get("sections", []))
        return cls(
            track_id=str(payload.get("track_id") or ""),
            name=str(payload.get("name") or "Sub Sequences"),
            track_type=cls.TRACK_TYPE,
            enabled=bool(payload.get("enabled", True)),
            muted=bool(payload.get("muted", False)),
            locked=bool(payload.get("locked", False)),
            expanded=bool(payload.get("expanded", True)),
            color=str(payload.get("color") or "#7A9A88"),
            keyframes=payload.get("keyframes", []) or [],
            parent_binding_id=str(payload.get("parent_binding_id") or ""),
            metadata=dict(payload.get("metadata", {}) or {}),
            sections=[SubSequenceSection.deserialize(item) for item in sections or []],
        )
