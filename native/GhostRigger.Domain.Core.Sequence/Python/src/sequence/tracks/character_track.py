"""Animated model pose extension track."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..sequence_keyframe import InterpolationMode, SequenceKeyframe
from ..sequence_track import SequenceTrack, register_track


@register_track
@dataclass
class CharacterTrack(SequenceTrack):
    TRACK_TYPE = "Character"

    def __post_init__(self) -> None:
        self.track_type = self.TRACK_TYPE
        self.metadata.setdefault("implementation_status", "Animation slot keys drive viewport pose evaluation for animated actors.")
        if not self.name or self.name == "Track":
            self.name = "Animation"
        super().__post_init__()

    def default_interpolation(self) -> InterpolationMode:
        return InterpolationMode.CONSTANT

    def add_animation_key(
        self,
        frame: int,
        animation_name: str,
        *,
        source: str = "",
        source_type: str = "",
        source_model_name: str = "",
        length: float = 0.0,
        duration_frames: float = 0.0,
        loop: bool = True,
        blend_mode: str = "auto",
        weight: float = 1.0,
        fade_in_frames: float = 6.0,
        fade_out_frames: float = 6.0,
        mask: str = "auto",
        priority: int = 0,
        select: bool = True,
    ) -> SequenceKeyframe:
        name = str(animation_name or "").strip()
        value = {
            "animation": name,
            "source": str(source or ""),
            "source_type": str(source_type or ""),
            "source_model_name": str(source_model_name or ""),
            "length": float(length or 0.0),
            "duration_frames": float(duration_frames or 0.0),
            "loop": bool(loop),
            "blend_mode": str(blend_mode or "auto"),
            "weight": float(weight if weight is not None else 1.0),
            "fade_in_frames": float(fade_in_frames or 0.0),
            "fade_out_frames": float(fade_out_frames or 0.0),
            "mask": str(mask or "auto"),
            "priority": int(priority or 0),
        }
        key = self.add_keyframe(frame, value, InterpolationMode.CONSTANT, select=select)
        self.metadata["last_animation"] = name
        return key

    def active_animation_keys(self, frame: int) -> list[SequenceKeyframe]:
        active: list[SequenceKeyframe] = []
        for key in sorted([item for item in self.keyframes if not item.locked], key=lambda item: item.frame):
            if int(key.frame) > int(frame) or not isinstance(key.value, dict):
                continue
            duration = float(key.value.get("duration_frames", 0.0) or 0.0)
            if duration > 0.0 and float(frame) > float(key.frame) + duration:
                continue
            active.append(key)
        return active

    def active_animation_key(self, frame: int) -> SequenceKeyframe | None:
        keys = self.active_animation_keys(frame)
        return keys[-1] if keys else None

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "CharacterTrack":
        payload = dict(data or {})
        return cls(
            track_id=str(payload.get("track_id") or ""),
            name=str(payload.get("name") or "Animation"),
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
