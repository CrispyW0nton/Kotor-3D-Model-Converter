"""Master camera cut track."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from ..sequence_track import SequenceTrack, register_track


@dataclass
class CameraCut:
    cut_id: str = field(default_factory=lambda: f"cut-{uuid4().hex}")
    camera_binding_id: str = ""
    start_frame: int = 0
    end_frame: int = 120
    display_name: str = "Camera Cut"
    color: str = "#3A96FF"

    def contains(self, frame: int) -> bool:
        return int(self.start_frame) <= int(frame) < int(self.end_frame)

    def serialize(self) -> dict[str, Any]:
        return {
            "cut_id": self.cut_id,
            "camera_binding_id": self.camera_binding_id,
            "start_frame": int(self.start_frame),
            "end_frame": int(self.end_frame),
            "display_name": self.display_name,
            "color": self.color,
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "CameraCut":
        payload = dict(data or {})
        return cls(
            cut_id=str(payload.get("cut_id") or f"cut-{uuid4().hex}"),
            camera_binding_id=str(payload.get("camera_binding_id") or ""),
            start_frame=int(payload.get("start_frame", 0) or 0),
            end_frame=int(payload.get("end_frame", 120) or 120),
            display_name=str(payload.get("display_name") or "Camera Cut"),
            color=str(payload.get("color") or "#3A96FF"),
        )


@register_track
@dataclass
class CameraCutTrack(SequenceTrack):
    TRACK_TYPE = "Camera Cut"
    cuts: list[CameraCut] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.track_type = self.TRACK_TYPE
        if not self.name or self.name == "Track":
            self.name = "Camera Cuts"
        super().__post_init__()
        self.cuts = [cut if isinstance(cut, CameraCut) else CameraCut.deserialize(cut) for cut in (self.cuts or self.metadata.get("cuts", []) or [])]
        self.cuts.sort(key=lambda cut: (cut.start_frame, cut.end_frame))

    def add_cut(self, camera_binding_id: str, start_frame: int, end_frame: int, display_name: str = "") -> CameraCut:
        cut = CameraCut(
            camera_binding_id=str(camera_binding_id),
            start_frame=int(start_frame),
            end_frame=max(int(start_frame) + 1, int(end_frame)),
            display_name=display_name or "Camera Cut",
        )
        self.cuts.append(cut)
        self.cuts.sort(key=lambda item: (item.start_frame, item.end_frame))
        return cut

    def active_cut(self, frame: int) -> CameraCut | None:
        if not self.enabled or self.muted:
            return None
        return next((cut for cut in self.cuts if cut.contains(frame)), None)

    def split_cut(self, cut_id: str, frame: int) -> CameraCut | None:
        cut = next((item for item in self.cuts if item.cut_id == cut_id), None)
        if cut is None or not (cut.start_frame < int(frame) < cut.end_frame):
            return None
        new_cut = CameraCut(
            camera_binding_id=cut.camera_binding_id,
            start_frame=int(frame),
            end_frame=cut.end_frame,
            display_name=cut.display_name,
            color=cut.color,
        )
        cut.end_frame = int(frame)
        self.cuts.append(new_cut)
        self.cuts.sort(key=lambda item: (item.start_frame, item.end_frame))
        return new_cut

    def serialize(self) -> dict[str, Any]:
        data = super().serialize()
        data["cuts"] = [cut.serialize() for cut in self.cuts]
        data["metadata"] = dict(data.get("metadata", {}))
        data["metadata"]["cuts"] = data["cuts"]
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "CameraCutTrack":
        payload = dict(data or {})
        cuts = payload.get("cuts", None)
        if cuts is None:
            cuts = dict(payload.get("metadata", {}) or {}).get("cuts", [])
        return cls(
            track_id=str(payload.get("track_id") or ""),
            name=str(payload.get("name") or "Camera Cuts"),
            track_type=cls.TRACK_TYPE,
            enabled=bool(payload.get("enabled", True)),
            muted=bool(payload.get("muted", False)),
            locked=bool(payload.get("locked", False)),
            expanded=bool(payload.get("expanded", True)),
            color=str(payload.get("color") or "#3A96FF"),
            keyframes=payload.get("keyframes", []) or [],
            parent_binding_id=str(payload.get("parent_binding_id") or ""),
            metadata=dict(payload.get("metadata", {}) or {}),
            cuts=[CameraCut.deserialize(item) for item in cuts or []],
        )
