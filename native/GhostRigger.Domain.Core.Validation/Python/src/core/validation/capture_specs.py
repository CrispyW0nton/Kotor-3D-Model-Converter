"""Dataclasses for Ghost Rigger viewport validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class CameraPreset(str, Enum):
    """Standard camera angles for validation captures."""

    FRONT_ORTHO = "front_ortho"
    THREE_QUARTER = "three_quarter"
    SIDE_LEFT = "side_left"
    SIDE_RIGHT = "side_right"
    TOP_DOWN = "top_down"
    BACK = "back"


class TrustLevel(str, Enum):
    """Calibration trust level for viewport versus in-game comparison."""

    CANONICAL = "canonical"
    APPROXIMATE = "approximate"
    INDICATIVE = "indicative"


@dataclass
class ViewportCaptureSpec:
    """Specifies what to capture from the viewport."""

    frames: List[int]
    animation_name: Optional[str] = None
    resolution: Tuple[int, int] = (512, 512)
    camera_preset: CameraPreset = CameraPreset.FRONT_ORTHO
    background_color: Tuple[float, float, float, float] = (0.1, 0.1, 0.1, 1.0)
    fps: float = 30.0

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("frames cannot be empty")
        if any(frame < 0 for frame in self.frames):
            raise ValueError("frame indices must be non-negative")
        if self.resolution[0] <= 0 or self.resolution[1] <= 0:
            raise ValueError("resolution must be positive")
        if self.fps <= 0:
            raise ValueError("fps must be positive")
        if not isinstance(self.camera_preset, CameraPreset):
            self.camera_preset = CameraPreset(self.camera_preset)


@dataclass
class BonePosition:
    """World-space bone transform at a specific frame."""

    name: str
    world_position: Tuple[float, float, float]
    world_rotation_quat: Tuple[float, float, float, float]


@dataclass
class FrameCapture:
    """Single frame capture result."""

    frame_index: int
    png_path: Path
    bone_positions: List[BonePosition] = field(default_factory=list)
    render_time_ms: float = 0.0


@dataclass
class ViewportValidationResult:
    """Complete validation output."""

    success: bool
    mdl_path: Path
    mdl_sha256: str
    node_count: int
    mesh_count: int
    animation_count: int
    animation_names: List[str] = field(default_factory=list)
    captures: List[FrameCapture] = field(default_factory=list)
    ssim_scores: Dict[int, float] = field(default_factory=dict)
    trust_level: Optional[TrustLevel] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    total_render_time_ms: float = 0.0

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""

        return {
            "success": self.success,
            "mdl_path": str(self.mdl_path),
            "mdl_sha256": self.mdl_sha256,
            "node_count": self.node_count,
            "mesh_count": self.mesh_count,
            "animation_count": self.animation_count,
            "animation_names": list(self.animation_names),
            "captures": [
                {
                    "frame_index": capture.frame_index,
                    "png_path": str(capture.png_path),
                    "bone_positions": [
                        {
                            "name": bone.name,
                            "world_position": list(bone.world_position),
                            "world_rotation_quat": list(bone.world_rotation_quat),
                        }
                        for bone in capture.bone_positions
                    ],
                    "render_time_ms": capture.render_time_ms,
                }
                for capture in self.captures
            ],
            "ssim_scores": {
                str(frame): score for frame, score in self.ssim_scores.items()
            },
            "trust_level": self.trust_level.value if self.trust_level else None,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "total_render_time_ms": self.total_render_time_ms,
        }
