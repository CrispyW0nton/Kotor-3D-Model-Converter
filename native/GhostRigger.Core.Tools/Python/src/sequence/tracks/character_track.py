"""Animated model pose extension track."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

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

    @property
    def supports_duplicate_frames(self) -> bool:
        return True

    def add_animation_key(
        self,
        frame: int,
        animation_name: str,
        *,
        character_instance_id: str = "",
        source_clip_id: str = "",
        source: str = "",
        source_type: str = "",
        source_model_name: str = "",
        length: float = 0.0,
        duration_frames: float = 0.0,
        source_in_seconds: float = 0.0,
        source_out_seconds: float | None = None,
        time_scale: float = 1.0,
        playback_speed: float = 1.0,
        loop: bool = True,
        loop_mode: str = "",
        blend_mode: str = "auto",
        layer_mode: str = "",
        weight: float = 1.0,
        fade_in_frames: float = 6.0,
        fade_out_frames: float = 6.0,
        blend_in_frames: float | None = None,
        blend_out_frames: float | None = None,
        mask: str = "auto",
        priority: int = 0,
        additive_reference_pose: str = "",
        muted: bool = False,
        solo: bool = False,
        select: bool = True,
    ) -> SequenceKeyframe:
        name = str(animation_name or "").strip()
        clip_id = str(source_clip_id or source or name).strip()
        clip_length = float(length or 0.0)
        source_in = max(0.0, float(source_in_seconds or 0.0))
        if source_out_seconds is None:
            source_out = clip_length if clip_length > 0.0 else 0.0
        else:
            source_out = max(source_in, float(source_out_seconds or 0.0))
        duration = float(duration_frames or 0.0)
        end_frame = float(frame) + duration if duration > 0.0 else float(frame)
        blend_in = fade_in_frames if blend_in_frames is None else blend_in_frames
        blend_out = fade_out_frames if blend_out_frames is None else blend_out_frames
        layer = str(layer_mode or blend_mode or "auto")
        loop_value = str(loop_mode or ("loop" if loop else "once")).strip().lower()
        value = {
            "clip_instance_id": f"clip-{uuid4().hex}",
            "source_clip_id": clip_id,
            "character_instance_id": str(character_instance_id or ""),
            "track_id": self.track_id,
            "animation": name,
            "source": str(source or ""),
            "source_type": str(source_type or ""),
            "source_model_name": str(source_model_name or ""),
            "clip_start_frame": int(frame),
            "clip_end_frame": end_frame,
            "source_in_seconds": source_in,
            "source_out_seconds": source_out,
            "time_scale": max(0.001, float(time_scale or 1.0)),
            "playback_speed": float(playback_speed if playback_speed is not None else 1.0),
            "length": clip_length,
            "duration_frames": duration,
            "loop": bool(loop),
            "loop_mode": loop_value,
            "blend_mode": str(blend_mode or "auto"),
            "layer_mode": layer,
            "weight": float(weight if weight is not None else 1.0),
            "fade_in_frames": float(fade_in_frames or 0.0),
            "fade_out_frames": float(fade_out_frames or 0.0),
            "blend_in_frames": float(blend_in or 0.0),
            "blend_out_frames": float(blend_out or 0.0),
            "mask": str(mask or "auto"),
            "priority": int(priority or 0),
            "additive_reference_pose": str(additive_reference_pose or ""),
            "muted": bool(muted),
            "solo": bool(solo),
        }
        key = self.add_keyframe(frame, value, InterpolationMode.CONSTANT, select=select)
        self.metadata["last_animation"] = name
        return key

    def move_selected_keys(self, frame_delta: int) -> None:
        delta = int(frame_delta)
        for key in self.keyframes:
            if not key.selected or key.locked:
                continue
            old_frame = int(key.frame)
            key.frame = old_frame + delta
            if isinstance(key.value, dict):
                duration = float(key.value.get("duration_frames", 0.0) or 0.0)
                try:
                    duration = max(duration, float(key.value.get("clip_end_frame", old_frame + duration)) - float(old_frame))
                except (TypeError, ValueError):
                    pass
                key.value["clip_start_frame"] = int(key.frame)
                if duration > 0.0:
                    key.value["clip_end_frame"] = float(key.frame) + duration
                    key.value["duration_frames"] = duration
        self.keyframes.sort(key=lambda item: item.frame)

    def active_animation_keys(self, frame: int) -> list[SequenceKeyframe]:
        active: list[SequenceKeyframe] = []
        for key in sorted([item for item in self.keyframes if not item.locked], key=lambda item: item.frame):
            if int(key.frame) > int(frame) or not isinstance(key.value, dict):
                continue
            if bool(key.value.get("muted", False)):
                continue
            duration = float(key.value.get("duration_frames", 0.0) or 0.0)
            end_frame = key.value.get("clip_end_frame")
            if end_frame is not None:
                try:
                    duration = max(duration, float(end_frame) - float(key.frame))
                except (TypeError, ValueError):
                    pass
            if duration > 0.0 and float(frame) > float(key.frame) + duration:
                continue
            active.append(key)
        solo_keys = [key for key in active if isinstance(key.value, dict) and bool(key.value.get("solo", False))]
        if solo_keys:
            return solo_keys
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
