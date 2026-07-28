"""Normalize Audio2Face and MediaPipe ARKit-compatible facial channels.

NVIDIA Audio2Face and MediaPipe can both produce the conventional 52 ARKit
blendshape coefficients.  This adapter accepts matrix or JSON exports and
converts them into GhostRigger's renderer-neutral facial clip.  Vendor
execution remains outside this module, so importing a saved performance does
not require CUDA, TensorRT, MediaPipe, or a network service.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.core.animation.facial_performance import (
    FacialChannelFrame,
    FacialPerformanceClip,
    FacialSource,
    channel_clip,
)


ARKIT_BLENDSHAPE_NAMES: tuple[str, ...] = (
    "browDownLeft",
    "browDownRight",
    "browInnerUp",
    "browOuterUpLeft",
    "browOuterUpRight",
    "cheekPuff",
    "cheekSquintLeft",
    "cheekSquintRight",
    "eyeBlinkLeft",
    "eyeBlinkRight",
    "eyeLookDownLeft",
    "eyeLookDownRight",
    "eyeLookInLeft",
    "eyeLookInRight",
    "eyeLookOutLeft",
    "eyeLookOutRight",
    "eyeLookUpLeft",
    "eyeLookUpRight",
    "eyeSquintLeft",
    "eyeSquintRight",
    "eyeWideLeft",
    "eyeWideRight",
    "jawForward",
    "jawLeft",
    "jawOpen",
    "jawRight",
    "mouthClose",
    "mouthDimpleLeft",
    "mouthDimpleRight",
    "mouthFrownLeft",
    "mouthFrownRight",
    "mouthFunnel",
    "mouthLeft",
    "mouthLowerDownLeft",
    "mouthLowerDownRight",
    "mouthPressLeft",
    "mouthPressRight",
    "mouthPucker",
    "mouthRight",
    "mouthRollLower",
    "mouthRollUpper",
    "mouthShrugLower",
    "mouthShrugUpper",
    "mouthSmileLeft",
    "mouthSmileRight",
    "mouthStretchLeft",
    "mouthStretchRight",
    "mouthUpperUpLeft",
    "mouthUpperUpRight",
    "noseSneerLeft",
    "noseSneerRight",
    "tongueOut",
)


def _channel_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


_CHANNEL_ALIASES: dict[str, str] = {
    _channel_key(name): name for name in ARKIT_BLENDSHAPE_NAMES
}
for _side in ("Left", "Right"):
    _short = "L" if _side == "Left" else "R"
    for _name in ARKIT_BLENDSHAPE_NAMES:
        if _name.endswith(_side):
            _base = _name[: -len(_side)]
            _CHANNEL_ALIASES[_channel_key(f"{_base}_{_short}")] = _name
            _CHANNEL_ALIASES[_channel_key(f"{_short}_{_base}")] = _name


def normalize_arkit_name(value: object) -> str:
    """Return the canonical ARKit spelling when a known alias is supplied."""

    text = str(value or "").strip()
    return _CHANNEL_ALIASES.get(_channel_key(text), text)


def _weight(value: object) -> float:
    try:
        resolved = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(resolved):
        return 0.0
    return max(0.0, min(1.0, resolved))


def clip_from_blendshape_frames(
    channel_names: Sequence[str],
    weights: Iterable[Sequence[float] | Mapping[str, float]],
    *,
    frame_rate: float = 60.0,
    timestamps: Sequence[float] | None = None,
    source: FacialSource | str = FacialSource.AUDIO2FACE,
    metadata: Mapping[str, Any] | None = None,
) -> FacialPerformanceClip:
    """Build a canonical facial clip from a channel matrix or frame mappings."""

    names = tuple(normalize_arkit_name(name) for name in channel_names)
    rows = tuple(weights)
    rate = max(1.0e-6, float(frame_rate or 60.0))
    if timestamps is not None and len(timestamps) != len(rows):
        raise ValueError("timestamps and facial frame counts differ")
    frames: list[FacialChannelFrame] = []
    for index, row in enumerate(rows):
        time_value = (
            max(0.0, float(timestamps[index]))
            if timestamps is not None
            else index / rate
        )
        if isinstance(row, Mapping):
            channels = {
                normalize_arkit_name(name): _weight(value)
                for name, value in row.items()
                if str(name)
            }
        else:
            if len(row) != len(names):
                raise ValueError(
                    f"facial frame {index} has {len(row)} weights; "
                    f"expected {len(names)}"
                )
            channels = {
                name: _weight(value)
                for name, value in zip(names, row)
            }
        frames.append(FacialChannelFrame(time_value, channels))
    clip_metadata = dict(metadata or {})
    clip_metadata.setdefault("frame_rate", rate)
    clip_metadata.setdefault("channel_standard", "ARKit-52")
    duration = frames[-1].time if frames else 0.0
    return channel_clip(
        source,
        frames,
        duration=duration,
        metadata=clip_metadata,
    )


def _first(mapping: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


def load_audio2face_json(
    source: str | Path | Mapping[str, Any],
) -> FacialPerformanceClip:
    """Load common Audio2Face ARKit JSON export shapes without its runtime."""

    if isinstance(source, Mapping):
        payload = dict(source)
        source_label = "<mapping>"
    else:
        target = Path(source)
        payload = json.loads(target.read_text(encoding="utf-8"))
        source_label = str(target)
    if not isinstance(payload, Mapping):
        raise ValueError("Audio2Face JSON root must be an object")
    names = _first(
        payload,
        "blendShapeNames",
        "blendshapeNames",
        "blend_shapes",
        "shapeNames",
        "channelNames",
    )
    rows = _first(payload, "weights", "weightMat", "frames", "samples")
    timestamps = _first(payload, "timestamps", "times", "timeCodes")
    frame_rate = _first(payload, "frameRate", "fps", "exportFps") or 60.0
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("Audio2Face JSON contains no facial frame array")

    if rows and isinstance(rows[0], Mapping):
        records = tuple(dict(record) for record in rows)
        inferred_times: list[float] = []
        mapped_rows: list[Mapping[str, float] | Sequence[float]] = []
        for index, record in enumerate(records):
            row = _first(record, "weights", "values", "channels")
            if row is None:
                row = {
                    key: value
                    for key, value in record.items()
                    if key not in {"time", "timestamp", "frame"}
                }
            mapped_rows.append(row)
            raw_time = _first(record, "time", "timestamp")
            inferred_times.append(
                float(raw_time) if raw_time is not None else index / float(frame_rate)
            )
        rows = mapped_rows
        if timestamps is None:
            timestamps = inferred_times
        if names is None and mapped_rows and isinstance(mapped_rows[0], Mapping):
            names = tuple(mapped_rows[0])
    if names is None:
        names = ARKIT_BLENDSHAPE_NAMES
    if not isinstance(names, Sequence) or isinstance(names, (str, bytes)):
        raise ValueError("Audio2Face JSON contains no blendshape name array")
    return clip_from_blendshape_frames(
        tuple(str(name) for name in names),
        rows,
        frame_rate=float(frame_rate),
        timestamps=timestamps,
        source=FacialSource.AUDIO2FACE,
        metadata={
            "adapter": "audio2face_arkit_json",
            "source_path": source_label,
        },
    )


def arkit_to_kotor_weights(
    channels: Mapping[str, float],
) -> tuple[float, ...]:
    """Project exterior ARKit mouth intent onto KOTOR's 16 fallback slots.

    Full ARKit curves remain the preferred Custom Animation Patch output.
    This projection is deliberately a compatibility fallback and cannot infer
    every tongue/internal phoneme from visible exterior coefficients alone.
    """

    values = {
        normalize_arkit_name(name): _weight(value)
        for name, value in channels.items()
    }

    def pair(base: str) -> float:
        return (
            values.get(f"{base}Left", 0.0)
            + values.get(f"{base}Right", 0.0)
        ) * 0.5

    jaw = values.get("jawOpen", 0.0)
    funnel = values.get("mouthFunnel", 0.0)
    pucker = values.get("mouthPucker", 0.0)
    close = values.get("mouthClose", 0.0)
    press = pair("mouthPress")
    stretch = pair("mouthStretch")
    smile = pair("mouthSmile")
    lower = pair("mouthLowerDown")
    upper = pair("mouthUpperUp")
    roll_lower = values.get("mouthRollLower", 0.0)
    tongue = values.get("tongueOut", 0.0)
    scores = [0.0] * 16
    scores[0] = max(0.0, 1.0 - max(jaw, funnel, pucker, close, press))
    scores[1] = max(stretch, smile * 0.8) * (1.0 - jaw * 0.4)
    scores[2] = jaw * 0.35 + stretch * 0.45
    scores[3] = jaw * (1.0 - funnel * 0.35 - pucker * 0.35)
    scores[4] = funnel * 0.75 + jaw * 0.4
    scores[5] = pucker * 0.9 + funnel * 0.35
    scores[6] = smile * 0.85 + stretch * 0.35
    scores[7] = close * 0.45 + stretch * 0.4
    scores[8] = roll_lower * 0.8 + lower * 0.25
    scores[9] = close * 0.25 + upper * 0.2
    scores[10] = tongue
    scores[11] = close + press * 0.8
    scores[12] = close * 0.35 + upper * 0.25
    scores[13] = funnel * 0.4 + pucker * 0.35
    scores[14] = tongue * 0.7 + jaw * 0.2
    scores[15] = close * 0.2 + jaw * 0.15
    peak = max(scores)
    if peak <= 1.0e-9:
        scores[0] = 1.0
        return tuple(scores)
    return tuple(max(0.0, min(1.0, score / peak)) for score in scores)


def best_kotor_viseme(weights: Sequence[float]) -> int:
    """Return the strongest KOTOR fallback shape index."""

    if not weights:
        return 0
    return max(range(min(16, len(weights))), key=lambda index: float(weights[index]))


__all__ = [
    "ARKIT_BLENDSHAPE_NAMES",
    "arkit_to_kotor_weights",
    "best_kotor_viseme",
    "clip_from_blendshape_frames",
    "load_audio2face_json",
    "normalize_arkit_name",
]
