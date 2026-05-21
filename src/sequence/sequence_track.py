"""Base sequence track model and registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar
from uuid import uuid4

from .sequence_interpolation import evaluate_keyframes
from .sequence_keyframe import InterpolationMode, SequenceKeyframe


TRACK_REGISTRY: dict[str, type["SequenceTrack"]] = {}


def register_track(cls: type["SequenceTrack"]) -> type["SequenceTrack"]:
    TRACK_REGISTRY[str(cls.TRACK_TYPE)] = cls
    return cls


@dataclass
class SequenceTrack:
    TRACK_TYPE: ClassVar[str] = "Generic"

    track_id: str = field(default_factory=lambda: f"track-{uuid4().hex}")
    name: str = "Track"
    track_type: str = "Generic"
    enabled: bool = True
    muted: bool = False
    locked: bool = False
    expanded: bool = True
    color: str = "#00D7B5"
    keyframes: list[SequenceKeyframe] = field(default_factory=list)
    parent_binding_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.track_id:
            self.track_id = f"track-{uuid4().hex}"
        self.track_type = str(self.track_type or self.TRACK_TYPE)
        self.keyframes = [
            key if isinstance(key, SequenceKeyframe) else SequenceKeyframe.deserialize(key)
            for key in (self.keyframes or [])
        ]
        self.keyframes.sort(key=lambda key: key.frame)

    @property
    def supports_duplicate_frames(self) -> bool:
        return False

    def add_keyframe(
        self,
        frame: int,
        value: Any,
        interpolation: InterpolationMode | str | None = None,
        *,
        select: bool = False,
    ) -> SequenceKeyframe:
        frame = int(round(float(frame)))
        if not self.supports_duplicate_frames:
            existing = next((key for key in self.keyframes if int(key.frame) == frame), None)
            if existing is not None:
                if not existing.locked:
                    existing.value = value
                    if interpolation is not None:
                        existing.interpolation = interpolation
                    existing.selected = bool(select)
                    existing.__post_init__()
                return existing
        key = SequenceKeyframe(frame=frame, value=value, interpolation=interpolation or self.default_interpolation(), selected=select)
        self.keyframes.append(key)
        self.keyframes.sort(key=lambda item: item.frame)
        return key

    def default_interpolation(self) -> InterpolationMode:
        return InterpolationMode.LINEAR

    def remove_keyframe(self, key_id: str) -> bool:
        before = len(self.keyframes)
        self.keyframes = [key for key in self.keyframes if key.key_id != key_id or key.locked]
        return len(self.keyframes) != before

    def delete_selected_keyframes(self) -> int:
        before = len(self.keyframes)
        self.keyframes = [key for key in self.keyframes if not key.selected or key.locked]
        return before - len(self.keyframes)

    def get_keyframes(self) -> list[SequenceKeyframe]:
        return list(self.keyframes)

    def selected_keyframes(self) -> list[SequenceKeyframe]:
        return [key for key in self.keyframes if key.selected]

    def clear_selection(self) -> None:
        for key in self.keyframes:
            key.selected = False

    def move_selected_keys(self, frame_delta: int) -> None:
        for key in self.keyframes:
            if key.selected and not key.locked:
                key.frame = int(key.frame) + int(frame_delta)
        self.keyframes.sort(key=lambda item: item.frame)

    def evaluate(self, frame: int) -> Any:
        if not self.enabled or self.muted:
            return None
        return evaluate_keyframes(self.keyframes, int(frame), None)

    def duplicate(self) -> "SequenceTrack":
        data = self.serialize()
        data["track_id"] = f"track-{uuid4().hex}"
        data["name"] = f"{self.name} Copy"
        data["keyframes"] = [dict(key, key_id=f"key-{uuid4().hex}") for key in data.get("keyframes", [])]
        return self.deserialize(data)

    def serialize(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "name": self.name,
            "track_type": self.track_type,
            "enabled": bool(self.enabled),
            "muted": bool(self.muted),
            "locked": bool(self.locked),
            "expanded": bool(self.expanded),
            "color": self.color,
            "keyframes": [key.serialize() for key in self.keyframes],
            "parent_binding_id": self.parent_binding_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "SequenceTrack":
        payload = dict(data or {})
        track_type = str(payload.get("track_type") or cls.TRACK_TYPE)
        if track_type not in TRACK_REGISTRY:
            try:
                from . import tracks as _tracks  # noqa: F401
            except Exception:
                pass
        target_cls = TRACK_REGISTRY.get(track_type, cls)
        if target_cls is not cls:
            return target_cls.deserialize(payload)
        return cls.deserialize_base(payload)

    @classmethod
    def deserialize_base(cls, data: dict[str, Any] | None) -> "SequenceTrack":
        payload = dict(data or {})
        track_type = str(payload.get("track_type") or cls.TRACK_TYPE)
        return cls(
            track_id=str(payload.get("track_id") or f"track-{uuid4().hex}"),
            name=str(payload.get("name") or "Track"),
            track_type=track_type,
            enabled=bool(payload.get("enabled", True)),
            muted=bool(payload.get("muted", False)),
            locked=bool(payload.get("locked", False)),
            expanded=bool(payload.get("expanded", True)),
            color=str(payload.get("color") or "#00D7B5"),
            keyframes=[SequenceKeyframe.deserialize(item) for item in payload.get("keyframes", []) or []],
            parent_binding_id=str(payload.get("parent_binding_id") or ""),
            metadata=dict(payload.get("metadata", {}) or {}),
        )
