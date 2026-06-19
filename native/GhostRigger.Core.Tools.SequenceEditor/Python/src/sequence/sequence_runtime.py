"""Runtime-only sequence animation state.

The persistent sequence asset stores clip references and keyed values. These
objects describe evaluated, mutable playback state and must never be serialized
back into source animation clips.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ViewportInterpolationState:
    character_instance_id: str
    sequence_frame: int = 0
    sequence_time_seconds: float = 0.0
    pose_revision: int = 0
    pose: Any = None
    root_transform: Any = None
    active_clip_instance_ids: tuple[str, ...] = ()

    def update(
        self,
        *,
        frame: int,
        time_seconds: float,
        pose: Any,
        root_transform: Any,
        active_clip_instance_ids: tuple[str, ...],
    ) -> None:
        self.sequence_frame = int(frame)
        self.sequence_time_seconds = float(time_seconds)
        self.pose = pose
        self.root_transform = root_transform
        self.active_clip_instance_ids = tuple(active_clip_instance_ids)
        self.pose_revision += 1


@dataclass
class CharacterSequenceRuntimeState:
    character_instance_id: str
    binding_id: str = ""
    target_object_id: str = ""
    skeleton_instance_id: str = ""
    animation_state: dict[str, Any] = field(default_factory=dict)
    evaluation_cache: dict[str, Any] = field(default_factory=dict)
    viewport_interpolation: ViewportInterpolationState | None = None

    def interpolation_state(self) -> ViewportInterpolationState:
        if self.viewport_interpolation is None:
            self.viewport_interpolation = ViewportInterpolationState(self.character_instance_id)
        return self.viewport_interpolation


@dataclass
class RootTransformController:
    character_instance_id: str
    transform: Any = None
    source: str = "sequence"

