"""Renderer-neutral facial performance clips and KOTOR LIP interpolation.

The Head Builder accepts several facial sources, but they all converge here:

* NVIDIA Audio2Face supplies audio-driven mouth and expression channels.
* MediaPipe/miniFACS supplies live face, eye, and head motion.
* openFACS supplies named action-unit edits and artist-authored offsets.
* NFR supplies an arbitrary-topology facial target/deformation layer.
* A learned facial deformer may approximate an already-approved rig.

This module deliberately has no Qt, renderer, PyKotor, or vendor imports.  It
owns the common clip, channel, viseme, and interpolation contracts.  Adapters
own vendor execution; the Head Builder owns orchestration and export choices.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, MutableMapping, Sequence


KOTOR_VISEME_NAMES: tuple[str, ...] = (
    "NEUTRAL",
    "EE",
    "EH",
    "AH",
    "OH",
    "OOH",
    "Y",
    "STS",
    "FV",
    "NG",
    "TH",
    "MPB",
    "TD",
    "SH",
    "L",
    "KG",
)

_PHONEME_TO_VISEME: dict[str, int] = {
    "AA": 3,
    "AE": 3,
    "AH": 3,
    "AO": 4,
    "AW": 3,
    "AY": 3,
    "B": 11,
    "CH": 13,
    "D": 12,
    "DH": 10,
    "EH": 2,
    "ER": 2,
    "EY": 1,
    "F": 8,
    "G": 15,
    "HH": 15,
    "IH": 1,
    "IY": 1,
    "JH": 13,
    "K": 15,
    "L": 14,
    "M": 11,
    "N": 9,
    "NG": 9,
    "OW": 4,
    "OY": 4,
    "P": 11,
    "R": 14,
    "S": 7,
    "SH": 13,
    "T": 12,
    "TH": 10,
    "UH": 5,
    "UW": 5,
    "V": 8,
    "W": 5,
    "Y": 6,
    "Z": 7,
    "ZH": 13,
    "": 0,
    " ": 0,
    "-": 0,
    "PAUSE": 0,
    "SIL": 0,
    "SILENCE": 0,
    "SP": 0,
}


CUSTOM_ANIMATION_PATCH_NOTICE = (
    "Custom Animation Patch required: full facial-performance curves are not "
    "a vanilla KOTOR head feature. Install the matching Custom Animation Patch "
    "with the exported head package. A 16-shape vanilla LIP fallback remains "
    "available without the patch."
)


class FacialSource(str, Enum):
    """Normalized producer identity for one facial clip."""

    KOTOR_LIP = "kotor_lip"
    AUDIO2FACE = "audio2face"
    MINIFACE_MEDIAPIPE = "miniface_mediapipe"
    OPENFACS = "openfacs"
    NFR = "nfr"
    MACHINE_LEARNING_DEFORMER = "machine_learning_deformer"
    MANUAL = "manual"
    COMPOSITE = "composite"


class FacialOutputMode(str, Enum):
    """Export/runtime contract chosen by the Head Builder."""

    VANILLA_LIP = "vanilla_lip"
    CUSTOM_PATCH_CURVES = "custom_patch_curves"


@dataclass(frozen=True)
class FacialModeProfile:
    """Truthful user-facing capabilities for one output mode."""

    mode: FacialOutputMode
    display_name: str
    export_kind: str
    channel_limit: int
    requires_custom_animation_patch: bool
    notice: str


_FACIAL_MODE_PROFILES: dict[FacialOutputMode, FacialModeProfile] = {
    FacialOutputMode.VANILLA_LIP: FacialModeProfile(
        mode=FacialOutputMode.VANILLA_LIP,
        display_name="Vanilla KOTOR LIP",
        export_kind="lip_v1",
        channel_limit=16,
        requires_custom_animation_patch=False,
        notice=(
            "Exports the stock 16 mouth shapes. It works without a runtime "
            "patch but cannot carry full brows, cheeks, gaze, or performance "
            "capture curves."
        ),
    ),
    FacialOutputMode.CUSTOM_PATCH_CURVES: FacialModeProfile(
        mode=FacialOutputMode.CUSTOM_PATCH_CURVES,
        display_name="Facial Performance Head",
        export_kind="custom_facial_curves",
        channel_limit=256,
        requires_custom_animation_patch=True,
        notice=CUSTOM_ANIMATION_PATCH_NOTICE,
    ),
}


def facial_mode_profile(
    mode: FacialOutputMode | str,
) -> FacialModeProfile:
    """Return the immutable capability record for *mode*."""

    try:
        resolved = mode if isinstance(mode, FacialOutputMode) else FacialOutputMode(mode)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Unknown facial output mode: {mode!r}") from exc
    return _FACIAL_MODE_PROFILES[resolved]


def phoneme_to_viseme(phoneme: str, *, default: int = 0) -> int:
    """Map ARPAbet/common silence tokens to KOTOR's actual LIP index."""

    key = str(phoneme or "").strip().upper()
    # Forced aligners commonly append lexical stress to vowels (AH0, IY1).
    while key and key[-1].isdigit():
        key = key[:-1]
    value = _PHONEME_TO_VISEME.get(key, int(default))
    return max(0, min(15, int(value)))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class VisemeBlend:
    """Two KOTOR shape slots and the direct interpolation factor."""

    left_shape: int
    right_shape: int
    factor: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "left_shape", max(0, min(15, int(self.left_shape))))
        object.__setattr__(self, "right_shape", max(0, min(15, int(self.right_shape))))
        object.__setattr__(self, "factor", _clamp01(self.factor))


def lip_duration(lip_data: Any) -> float:
    """Read either modern ``duration`` or legacy ``sound_length`` safely."""

    if lip_data is None:
        return 0.0
    raw = getattr(lip_data, "duration", None)
    if raw is None:
        raw = getattr(lip_data, "sound_length", 0.0)
    try:
        return max(0.0, float(raw or 0.0))
    except (TypeError, ValueError):
        return 0.0


def sample_lip_blend(lip_data: Any, time_seconds: float) -> VisemeBlend:
    """Return the exact surrounding LIP shapes at *time_seconds*."""

    if lip_data is None:
        return VisemeBlend(0, 0, 0.0)
    sampler = getattr(lip_data, "get_shapes", None)
    if callable(sampler):
        sampled = sampler(max(0.0, float(time_seconds)))
        if sampled is not None:
            left, right, factor = sampled
            return VisemeBlend(int(left), int(right), float(factor))
    nearest = getattr(lip_data, "get_shape_at_time", None)
    if callable(nearest):
        shape = int(nearest(max(0.0, float(time_seconds))))
        return VisemeBlend(shape, shape, 0.0)
    return VisemeBlend(0, 0, 0.0)


def lerp_values(
    left: Sequence[float],
    right: Sequence[float],
    factor: float,
) -> tuple[float, ...]:
    """Linearly interpolate matching numeric components."""

    alpha = _clamp01(factor)
    count = min(len(left), len(right))
    return tuple(
        float(left[index])
        + (float(right[index]) - float(left[index])) * alpha
        for index in range(count)
    )


def _normalized_quaternion(
    value: Sequence[float],
) -> tuple[float, float, float, float]:
    if len(value) < 4:
        return (0.0, 0.0, 0.0, 1.0)
    x, y, z, w = (float(value[0]), float(value[1]), float(value[2]), float(value[3]))
    magnitude = math.sqrt(x * x + y * y + z * z + w * w)
    if magnitude <= 1.0e-12:
        return (0.0, 0.0, 0.0, 1.0)
    return (x / magnitude, y / magnitude, z / magnitude, w / magnitude)


def slerp_quaternion(
    left: Sequence[float],
    right: Sequence[float],
    factor: float,
) -> tuple[float, float, float, float]:
    """Shortest-path spherical interpolation for XYZW quaternions."""

    alpha = _clamp01(factor)
    x1, y1, z1, w1 = _normalized_quaternion(left)
    x2, y2, z2, w2 = _normalized_quaternion(right)
    dot = x1 * x2 + y1 * y2 + z1 * z2 + w1 * w2
    if dot < 0.0:
        x2, y2, z2, w2 = -x2, -y2, -z2, -w2
        dot = -dot
    dot = max(-1.0, min(1.0, dot))
    if dot > 0.9995:
        return _normalized_quaternion(
            (
                x1 + (x2 - x1) * alpha,
                y1 + (y2 - y1) * alpha,
                z1 + (z2 - z1) * alpha,
                w1 + (w2 - w1) * alpha,
            )
        )
    theta_0 = math.acos(dot)
    sin_theta_0 = math.sin(theta_0)
    if abs(sin_theta_0) <= 1.0e-12:
        return (x1, y1, z1, w1)
    theta = theta_0 * alpha
    sin_theta = math.sin(theta)
    left_scale = math.cos(theta) - dot * sin_theta / sin_theta_0
    right_scale = sin_theta / sin_theta_0
    return _normalized_quaternion(
        (
            left_scale * x1 + right_scale * x2,
            left_scale * y1 + right_scale * y2,
            left_scale * z1 + right_scale * z2,
            left_scale * w1 + right_scale * w2,
        )
    )


def _pose_record(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {
        key: getattr(value, key)
        for key in (
            "name",
            "position",
            "rotation",
            "scale",
            "alpha",
            "selfillum",
        )
        if hasattr(value, key)
    }


def pose_to_mapping(pose: Any) -> dict[str, dict[str, Any]]:
    """Convert an AnimPose-shaped object to plain, dependency-free records."""

    nodes = getattr(pose, "nodes", pose)
    if not isinstance(nodes, Mapping):
        return {}
    return {
        str(name).casefold(): _pose_record(value)
        for name, value in nodes.items()
    }


def blend_pose_mappings(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    factor: float,
) -> dict[str, dict[str, Any]]:
    """Blend direct facial poses without walking through intervening shapes."""

    alpha = _clamp01(factor)
    left_records = {
        str(name).casefold(): _pose_record(value)
        for name, value in left.items()
    }
    right_records = {
        str(name).casefold(): _pose_record(value)
        for name, value in right.items()
    }
    output: dict[str, dict[str, Any]] = {}
    for name in sorted(set(left_records) | set(right_records)):
        before = left_records.get(name)
        after = right_records.get(name)
        if before is None:
            output[name] = dict(after or {})
            continue
        if after is None:
            output[name] = dict(before)
            continue
        record: dict[str, Any] = {}
        record["name"] = str(after.get("name") or before.get("name") or name)
        left_position = before.get("position")
        right_position = after.get("position")
        if left_position is not None and right_position is not None:
            record["position"] = lerp_values(left_position, right_position, alpha)
        elif right_position is not None:
            record["position"] = tuple(right_position)
        elif left_position is not None:
            record["position"] = tuple(left_position)
        left_rotation = before.get("rotation")
        right_rotation = after.get("rotation")
        if left_rotation is not None and right_rotation is not None:
            record["rotation"] = slerp_quaternion(
                left_rotation,
                right_rotation,
                alpha,
            )
        elif right_rotation is not None:
            record["rotation"] = _normalized_quaternion(right_rotation)
        elif left_rotation is not None:
            record["rotation"] = _normalized_quaternion(left_rotation)
        for scalar_name in ("scale", "alpha"):
            left_scalar = before.get(scalar_name)
            right_scalar = after.get(scalar_name)
            if left_scalar is not None and right_scalar is not None:
                record[scalar_name] = (
                    float(left_scalar)
                    + (float(right_scalar) - float(left_scalar)) * alpha
                )
            elif right_scalar is not None:
                record[scalar_name] = right_scalar
            elif left_scalar is not None:
                record[scalar_name] = left_scalar
        left_color = before.get("selfillum")
        right_color = after.get("selfillum")
        if left_color is not None and right_color is not None:
            record["selfillum"] = lerp_values(left_color, right_color, alpha)
        elif right_color is not None:
            record["selfillum"] = tuple(right_color)
        elif left_color is not None:
            record["selfillum"] = tuple(left_color)
        output[name] = record
    return output


def blend_animation_poses(
    left_pose: Any,
    right_pose: Any,
    factor: float,
    *,
    animation_module: Any,
    time_seconds: float,
) -> Any:
    """Build a native AnimPose from two evaluated shape poses."""

    records = blend_pose_mappings(
        pose_to_mapping(left_pose),
        pose_to_mapping(right_pose),
        factor,
    )
    output = animation_module.AnimPose(time=float(time_seconds))
    for name, record in records.items():
        output.nodes[name] = animation_module.NodePose(
            name=str(record.get("name") or name),
            position=tuple(record.get("position") or (0.0, 0.0, 0.0)),
            rotation=tuple(record.get("rotation") or (0.0, 0.0, 0.0, 1.0)),
            scale=float(record.get("scale", 1.0) or 1.0),
            alpha=record.get("alpha"),
            selfillum=record.get("selfillum"),
        )
    for attr in (
        "_gr_animation",
        "_gr_animation_source_model_id",
        "_gr_animation_source_model_name",
        "_gr_animation_name",
    ):
        value = getattr(left_pose, attr, None)
        if value is not None:
            setattr(output, attr, value)
    return output


@dataclass(frozen=True)
class FacialChannelFrame:
    """One time-stamped set of normalized facial control values."""

    time: float
    channels: Mapping[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "time", max(0.0, float(self.time)))
        object.__setattr__(
            self,
            "channels",
            {
                str(name): float(value)
                for name, value in self.channels.items()
                if str(name)
                and math.isfinite(float(value))
            },
        )


@dataclass
class FacialPerformanceClip:
    """Canonical, source-agnostic facial animation clip."""

    duration: float
    source: FacialSource
    frames: tuple[FacialChannelFrame, ...] = ()
    metadata: MutableMapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.duration = max(0.0, float(self.duration))
        if not isinstance(self.source, FacialSource):
            self.source = FacialSource(self.source)
        self.frames = tuple(sorted(self.frames, key=lambda frame: frame.time))
        if self.frames:
            self.duration = max(self.duration, self.frames[-1].time)

    @property
    def channel_names(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    name
                    for frame in self.frames
                    for name in frame.channels
                }
            )
        )

    def sample(self, time_seconds: float) -> dict[str, float]:
        """Linearly sample every channel, holding missing values at zero."""

        if not self.frames:
            return {}
        time_value = max(0.0, min(float(time_seconds), self.duration))
        if time_value <= self.frames[0].time:
            return dict(self.frames[0].channels)
        if time_value >= self.frames[-1].time:
            return dict(self.frames[-1].channels)
        left = self.frames[0]
        right = self.frames[-1]
        for index in range(1, len(self.frames)):
            candidate = self.frames[index]
            if candidate.time >= time_value:
                left = self.frames[index - 1]
                right = candidate
                break
        span = max(1.0e-9, right.time - left.time)
        alpha = _clamp01((time_value - left.time) / span)
        output: dict[str, float] = {}
        for name in set(left.channels) | set(right.channels):
            before = float(left.channels.get(name, 0.0))
            after = float(right.channels.get(name, 0.0))
            output[name] = before + (after - before) * alpha
        return output

    @classmethod
    def compose(
        cls,
        *,
        audio: "FacialPerformanceClip | None" = None,
        capture: "FacialPerformanceClip | None" = None,
        manual: "FacialPerformanceClip | None" = None,
        sample_rate: float = 60.0,
    ) -> "FacialPerformanceClip":
        """Compose mouth, capture, and artist layers into one sampled clip.

        Layers are deliberately ordered. Audio establishes the performance,
        capture may replace/add live channels, and manual openFACS edits are
        the final art-directed override.
        """

        layers = tuple(layer for layer in (audio, capture, manual) if layer)
        if not layers:
            return cls(0.0, FacialSource.COMPOSITE)
        duration = max(layer.duration for layer in layers)
        rate = max(1.0, float(sample_rate))
        sample_count = max(1, int(math.ceil(duration * rate)))
        times = [index / rate for index in range(sample_count + 1)]
        if times[-1] < duration:
            times.append(duration)
        else:
            times[-1] = duration
        frames: list[FacialChannelFrame] = []
        for time_value in times:
            channels: dict[str, float] = {}
            for layer in layers:
                channels.update(layer.sample(time_value))
            frames.append(FacialChannelFrame(time_value, channels))
        return cls(
            duration=duration,
            source=FacialSource.COMPOSITE,
            frames=tuple(frames),
            metadata={
                "composition": {
                    "audio": audio.source.value if audio else "",
                    "capture": capture.source.value if capture else "",
                    "manual": manual.source.value if manual else "",
                    "sample_rate": rate,
                }
            },
        )


def channel_clip(
    source: FacialSource | str,
    frames: Iterable[FacialChannelFrame],
    *,
    duration: float = 0.0,
    metadata: Mapping[str, Any] | None = None,
) -> FacialPerformanceClip:
    """Convenience constructor used by external-source adapters."""

    return FacialPerformanceClip(
        duration=duration,
        source=FacialSource(source),
        frames=tuple(frames),
        metadata=dict(metadata or {}),
    )


__all__ = [
    "CUSTOM_ANIMATION_PATCH_NOTICE",
    "FacialChannelFrame",
    "FacialModeProfile",
    "FacialOutputMode",
    "FacialPerformanceClip",
    "FacialSource",
    "KOTOR_VISEME_NAMES",
    "VisemeBlend",
    "blend_animation_poses",
    "blend_pose_mappings",
    "channel_clip",
    "facial_mode_profile",
    "lerp_values",
    "lip_duration",
    "phoneme_to_viseme",
    "pose_to_mapping",
    "sample_lip_blend",
    "slerp_quaternion",
]
