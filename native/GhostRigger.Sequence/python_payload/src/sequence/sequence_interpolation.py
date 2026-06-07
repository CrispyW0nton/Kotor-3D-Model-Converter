"""Frame-based value interpolation helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .sequence_keyframe import InterpolationMode, SequenceKeyframe


def _ease(t: float, mode: InterpolationMode) -> float:
    t = max(0.0, min(1.0, float(t)))
    if mode == InterpolationMode.EASE_IN:
        return t * t
    if mode == InterpolationMode.EASE_OUT:
        return 1.0 - (1.0 - t) * (1.0 - t)
    if mode in {InterpolationMode.EASE_IN_OUT, InterpolationMode.CUBIC}:
        return t * t * (3.0 - 2.0 * t)
    return t


def _lerp_number(a: Any, b: Any, t: float) -> float:
    return float(a) + (float(b) - float(a)) * t


def interpolate_values(a: Any, b: Any, t: float, mode: InterpolationMode | str = InterpolationMode.LINEAR) -> Any:
    try:
        interp = mode if isinstance(mode, InterpolationMode) else InterpolationMode(str(mode))
    except ValueError:
        interp = InterpolationMode.LINEAR
    if interp == InterpolationMode.CONSTANT:
        return a
    t = _ease(t, interp)
    if isinstance(a, bool) or isinstance(b, bool):
        return a if t < 1.0 else b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return _lerp_number(a, b, t)
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        result: dict[str, Any] = {}
        for key in set(a.keys()) | set(b.keys()):
            if key in a and key in b:
                result[key] = interpolate_values(a[key], b[key], t, interp)
            elif key in a:
                result[key] = a[key]
            else:
                result[key] = b[key]
        return result
    if (
        isinstance(a, Sequence)
        and isinstance(b, Sequence)
        and not isinstance(a, (str, bytes, bytearray))
        and not isinstance(b, (str, bytes, bytearray))
    ):
        if len(a) == len(b) and all(isinstance(v, (int, float)) for v in list(a) + list(b)):
            return tuple(_lerp_number(x, y, t) for x, y in zip(a, b))
    return a if t < 1.0 else b


def evaluate_keyframes(keyframes: list[SequenceKeyframe], frame: int, default: Any = None) -> Any:
    keys = sorted([key for key in keyframes if not key.locked], key=lambda item: item.frame)
    if not keys:
        return default
    frame = int(frame)
    if frame <= keys[0].frame:
        return keys[0].value
    if frame >= keys[-1].frame:
        return keys[-1].value
    for index, left in enumerate(keys[:-1]):
        right = keys[index + 1]
        if left.frame <= frame <= right.frame:
            span = max(1, int(right.frame) - int(left.frame))
            t = (int(frame) - int(left.frame)) / span
            return interpolate_values(left.value, right.value, t, left.interpolation)
    return keys[-1].value
