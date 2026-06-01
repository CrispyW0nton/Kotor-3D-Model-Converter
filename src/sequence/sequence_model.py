"""GhostRigger Level Sequence asset model and frame-time helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .sequence_binding import SequenceBinding
from .sequence_track import SequenceTrack


SUPPORTED_FRAME_RATES = (12, 15, 23.976, 24, 25, 29.97, 30, 48, 50, 59.94, 60)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class SequenceTime:
    start_frame: int = 0
    end_frame: int = 240
    frame_rate: float = 24.0
    current_frame: int = 0

    def __post_init__(self) -> None:
        self.start_frame = int(self.start_frame)
        self.end_frame = max(int(self.start_frame), int(self.end_frame))
        self.frame_rate = validate_frame_rate(self.frame_rate)
        self.current_frame = self.clamp_frame(self.current_frame)

    def frame_to_seconds(self, frame: int) -> float:
        return (int(frame) - int(self.start_frame)) / float(self.frame_rate)

    def seconds_to_frame(self, seconds: float) -> int:
        return self.clamp_frame(int(round(float(seconds) * float(self.frame_rate))) + int(self.start_frame))

    def clamp_frame(self, frame: int) -> int:
        return max(int(self.start_frame), min(int(self.end_frame), int(round(float(frame)))))

    def set_current_frame(self, frame: int) -> int:
        self.current_frame = self.clamp_frame(frame)
        return self.current_frame

    def get_current_frame(self) -> int:
        return int(self.current_frame)

    def get_duration_frames(self) -> int:
        return max(0, int(self.end_frame) - int(self.start_frame))

    def get_duration_seconds(self) -> float:
        return self.get_duration_frames() / float(self.frame_rate)


def validate_frame_rate(value: float | int) -> float:
    try:
        rate = float(value)
    except (TypeError, ValueError):
        rate = 24.0
    if not any(abs(rate - float(allowed)) < 0.001 for allowed in SUPPORTED_FRAME_RATES):
        nearest = min(SUPPORTED_FRAME_RATES, key=lambda allowed: abs(float(allowed) - rate))
        rate = float(nearest)
    return float(rate)


@dataclass
class SequenceMarker:
    frame: int = 0
    name: str = "Marker"
    color: str = "#D8C66A"
    notes: str = ""

    def serialize(self) -> dict[str, Any]:
        return {"frame": int(self.frame), "name": self.name, "color": self.color, "notes": self.notes}

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "SequenceMarker":
        payload = dict(data or {})
        return cls(
            frame=int(round(float(payload.get("frame", 0) or 0))),
            name=str(payload.get("name") or "Marker"),
            color=str(payload.get("color") or "#D8C66A"),
            notes=str(payload.get("notes") or ""),
        )


@dataclass
class GhostRiggerLevelSequence:
    file_version: int = 1
    id: str = field(default_factory=lambda: f"sequence-{uuid4().hex}")
    name: str = "New Sequence"
    description: str = ""
    asset_path: str = ""
    scene_module_name: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    modified_at: str = field(default_factory=utc_now_iso)
    start_frame: int = 0
    end_frame: int = 240
    frame_rate: float = 24.0
    display_rate: float = 24.0
    playback_start_frame: int = 0
    playback_end_frame: int = 240
    current_frame: int = 0
    bindings: list[SequenceBinding] = field(default_factory=list)
    master_tracks: list[SequenceTrack] = field(default_factory=list)
    sub_sequences: list[dict[str, Any]] = field(default_factory=list)
    markers: list[SequenceMarker] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.start_frame = int(self.start_frame)
        self.end_frame = max(self.start_frame, int(self.end_frame))
        self.frame_rate = validate_frame_rate(self.frame_rate)
        self.display_rate = validate_frame_rate(self.display_rate)
        self.playback_start_frame = max(self.start_frame, int(self.playback_start_frame))
        self.playback_end_frame = min(self.end_frame, max(self.playback_start_frame, int(self.playback_end_frame)))
        self.current_frame = self.clamp_frame(self.current_frame)
        self.bindings = [
            binding if isinstance(binding, SequenceBinding) else SequenceBinding.deserialize(binding)
            for binding in (self.bindings or [])
        ]
        self.master_tracks = [
            track if isinstance(track, SequenceTrack) else SequenceTrack.deserialize(track)
            for track in (self.master_tracks or [])
        ]
        self.markers = [
            marker if isinstance(marker, SequenceMarker) else SequenceMarker.deserialize(marker)
            for marker in (self.markers or [])
        ]

    @property
    def duration_seconds(self) -> float:
        return self.time.get_duration_seconds()

    @property
    def time(self) -> SequenceTime:
        return SequenceTime(self.start_frame, self.end_frame, self.frame_rate, self.current_frame)

    def frame_to_seconds(self, frame: int) -> float:
        return self.time.frame_to_seconds(frame)

    def seconds_to_frame(self, seconds: float) -> int:
        return self.time.seconds_to_frame(seconds)

    def clamp_frame(self, frame: int) -> int:
        return SequenceTime(self.start_frame, self.end_frame, self.frame_rate, self.current_frame).clamp_frame(frame)

    def set_current_frame(self, frame: int) -> int:
        self.current_frame = self.clamp_frame(frame)
        return self.current_frame

    def set_frame_range(self, start_frame: int, end_frame: int) -> tuple[int, int]:
        old_start = int(self.start_frame)
        old_end = int(self.end_frame)
        old_playback_start = int(self.playback_start_frame)
        old_playback_end = int(self.playback_end_frame)
        new_start = int(start_frame)
        new_end = max(new_start, int(end_frame))
        playback_start_tracks_range = old_playback_start <= old_start
        playback_end_tracks_range = old_playback_end >= old_end
        self.start_frame = new_start
        self.end_frame = new_end
        if playback_start_tracks_range or old_playback_start < new_start or old_playback_start > new_end:
            self.playback_start_frame = new_start
        else:
            self.playback_start_frame = old_playback_start
        if old_playback_end < self.playback_start_frame:
            self.playback_end_frame = self.playback_start_frame
        elif playback_end_tracks_range or old_playback_end > new_end:
            self.playback_end_frame = new_end
        else:
            self.playback_end_frame = old_playback_end
        self.playback_end_frame = max(self.playback_start_frame, min(new_end, int(self.playback_end_frame)))
        self.set_current_frame(self.current_frame)
        return self.start_frame, self.end_frame

    def get_current_frame(self) -> int:
        return int(self.current_frame)

    def get_duration_frames(self) -> int:
        return max(0, self.end_frame - self.start_frame)

    def get_duration_seconds(self) -> float:
        return self.duration_seconds

    def touch(self) -> None:
        self.modified_at = utc_now_iso()

    def add_binding(self, binding: SequenceBinding) -> SequenceBinding:
        self.bindings.append(binding)
        self.touch()
        return binding

    def remove_binding(self, binding_id: str) -> bool:
        before = len(self.bindings)
        self.bindings = [binding for binding in self.bindings if binding.binding_id != binding_id]
        changed = len(self.bindings) != before
        if changed:
            self.touch()
        return changed

    def binding_by_id(self, binding_id: str) -> SequenceBinding | None:
        return next((binding for binding in self.bindings if binding.binding_id == binding_id), None)

    def all_tracks(self) -> list[SequenceTrack]:
        tracks = list(self.master_tracks)
        for binding in self.bindings:
            tracks.extend(binding.tracks)
        return tracks

    def serialize(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "file_version": int(self.file_version),
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "asset_path": self.asset_path,
            "scene_module_name": self.scene_module_name,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "start_frame": int(self.start_frame),
            "end_frame": int(self.end_frame),
            "frame_rate": float(self.frame_rate),
            "display_rate": float(self.display_rate),
            "playback_start_frame": int(self.playback_start_frame),
            "playback_end_frame": int(self.playback_end_frame),
            "current_frame": int(self.current_frame),
            "duration_seconds": self.duration_seconds,
            "bindings": [binding.serialize() for binding in self.bindings],
            "master_tracks": [track.serialize() for track in self.master_tracks],
            "sub_sequences": list(self.sub_sequences),
            "markers": [marker.serialize() for marker in self.markers],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "GhostRiggerLevelSequence":
        payload = dict(data or {})
        sequence = cls(
            file_version=int(payload.get("file_version", 1) or 1),
            id=str(payload.get("id") or f"sequence-{uuid4().hex}"),
            name=str(payload.get("name") or "New Sequence"),
            description=str(payload.get("description") or ""),
            asset_path=str(payload.get("asset_path") or ""),
            scene_module_name=str(payload.get("scene_module_name") or ""),
            created_at=str(payload.get("created_at") or utc_now_iso()),
            modified_at=str(payload.get("modified_at") or utc_now_iso()),
            start_frame=int(payload.get("start_frame", 0) or 0),
            end_frame=int(payload.get("end_frame", 240) or 240),
            frame_rate=float(payload.get("frame_rate", 24) or 24),
            display_rate=float(payload.get("display_rate", payload.get("frame_rate", 24)) or 24),
            playback_start_frame=int(payload.get("playback_start_frame", payload.get("start_frame", 0)) or 0),
            playback_end_frame=int(payload.get("playback_end_frame", payload.get("end_frame", 240)) or 240),
            current_frame=int(payload.get("current_frame", 0) or 0),
            bindings=[SequenceBinding.deserialize(item) for item in payload.get("bindings", []) or []],
            master_tracks=[SequenceTrack.deserialize(item) for item in payload.get("master_tracks", []) or []],
            sub_sequences=list(payload.get("sub_sequences", []) or []),
            markers=[SequenceMarker.deserialize(item) for item in payload.get("markers", []) or []],
            metadata=dict(payload.get("metadata", {}) or {}),
        )
        if sequence.file_version > 1:
            sequence.metadata.setdefault("warnings", []).append("File version newer than this editor; unsupported fields were preserved where possible.")
        return sequence
