"""Headless ambient-sound planning for Map Studio Play In Editor.

The KOTOR engine remains the final audio oracle.  This module deliberately
builds a small, deterministic preview plan from authored GIT sound placements
and their UTS templates; it does not claim to reproduce Odyssey's mixer,
occlusion, room acoustics, priority stealing, or script-driven sound calls.

Qt playback belongs to :mod:`src.adapters.qt_audio.map_studio_pie_audio`.
Keeping UTS parsing here lets validation and tests inspect the same plan
without constructing Qt objects.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable

from pykotor.resource.generics.uts import read_uts
from pykotor.resource.type import ResourceType


Vec3 = tuple[float, float, float]

PIE_AUDIO_APPROXIMATION_NOTE = (
    "PIE ambient audio is an editor approximation. Final timing, mixing, "
    "occlusion, room acoustics, priority, and script-driven playback must be "
    "verified in KOTOR."
)


@dataclass(frozen=True, slots=True)
class MapStudioPIEAmbientSoundSpec:
    """One stable, renderer-independent UTS playback specification."""

    sound_id: str
    template_resref: str
    tag: str
    position: Vec3
    clip_resrefs: tuple[str, ...]
    active: bool
    continuous: bool
    looping: bool
    positional: bool
    random_pick: bool
    random_position: bool
    random_range_x: float
    random_range_y: float
    min_distance: float
    max_distance: float
    volume: int
    volume_variation: int
    pitch_variation: float
    interval_seconds: float
    interval_variation_seconds: float
    priority: int

    @property
    def base_gain(self) -> float:
        """Return the UTS volume as a normalized editor gain.

        Shipped KOTOR UTS assets use the 0..127 range.  Values outside that
        range are clamped so malformed community templates cannot overdrive
        the Qt output.
        """

        return max(0.0, min(1.0, float(self.volume) / 127.0))


@dataclass(frozen=True, slots=True)
class MapStudioPIEAudioWarning:
    """Stable, machine-readable warning emitted while constructing a plan."""

    code: str
    sound_id: str
    message: str


@dataclass(frozen=True, slots=True)
class MapStudioPIEAmbientSoundPlan:
    """Deterministically ordered ambient-sound inputs for one PIE session."""

    specs: tuple[MapStudioPIEAmbientSoundSpec, ...]
    warnings: tuple[MapStudioPIEAudioWarning, ...]
    approximation_note: str = PIE_AUDIO_APPROXIMATION_NOTE

    @property
    def active_specs(self) -> tuple[MapStudioPIEAmbientSoundSpec, ...]:
        return tuple(spec for spec in self.specs if spec.active and spec.clip_resrefs)


def _resref_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    # Some resource wrappers stringify as ``ResRef(foo)`` rather than ``foo``.
    if text.startswith("resref(") and text.endswith(")"):
        text = text[7:-1].strip()
    return text


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def _position3(value: Any) -> Vec3:
    if value is None:
        return (0.0, 0.0, 0.0)
    if all(hasattr(value, axis) for axis in ("x", "y", "z")):
        return (
            _finite_float(getattr(value, "x")),
            _finite_float(getattr(value, "y")),
            _finite_float(getattr(value, "z")),
        )
    try:
        items = tuple(value)
    except TypeError:
        return (0.0, 0.0, 0.0)
    if len(items) < 3:
        return (0.0, 0.0, 0.0)
    return (_finite_float(items[0]), _finite_float(items[1]), _finite_float(items[2]))


def _resource_bytes(
    resource_manager: Any,
    resref: str,
    resource_type: ResourceType,
    game: str,
) -> bytes | None:
    getter = getattr(resource_manager, "get_strict", None)
    if not callable(getter):
        getter = getattr(resource_manager, "get", None)
    if not callable(getter):
        return None
    try:
        value = getter(resref, resource_type.type_id, game)
    except TypeError:
        try:
            value = getter(resref, resource_type.type_id)
        except Exception:
            return None
    except Exception:
        return None
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    data = getattr(value, "data", None)
    if callable(data):
        try:
            data = data()
        except Exception:
            return None
    if isinstance(data, (bytes, bytearray, memoryview)):
        return bytes(data)
    return None


def _stable_sound_id(sound: Any, template_resref: str, index: int, used: set[str]) -> str:
    explicit = str(getattr(sound, "instance_id", "") or "").strip()
    tag = str(getattr(sound, "tag", "") or "").strip()
    candidate = explicit or tag or f"sound:{template_resref or 'missing'}:{index:04d}"
    if candidate not in used:
        used.add(candidate)
        return candidate
    candidate = f"{candidate}:{index:04d}"
    suffix = 2
    while candidate in used:
        candidate = f"{candidate}:{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _placement_sounds(placements: Any) -> Iterable[Any]:
    sounds = getattr(placements, "sounds", ())
    return tuple(sounds or ())


def build_map_studio_pie_ambient_sound_plan(
    placements: Any,
    resource_manager: Any,
    game: str,
    *,
    check_clip_resources: bool = True,
) -> MapStudioPIEAmbientSoundPlan:
    """Parse authored/GIT sound placements and their UTS templates.

    ``placements`` is intentionally duck-typed.  It may be an
    ``AuthoredGameplayPlacement`` (``template_resref``/``instance_id``) or a
    PyKotor ``GIT`` object (``resref``).  Resource access follows GhostRigger's
    ``ResourceManager.get(resref, type_id, game)`` contract.

    UTS ``Interval`` and ``IntervalVrtn`` are stored in milliseconds in the
    shipped KOTOR assets, despite older third-party docs describing seconds.
    The plan exposes seconds for a playback adapter.
    """

    game_tag = str(game or "K1").strip().upper()
    if game_tag not in {"K1", "K2"}:
        game_tag = "K1"

    specs: list[MapStudioPIEAmbientSoundSpec] = []
    warnings: list[MapStudioPIEAudioWarning] = []
    used_ids: set[str] = set()

    for index, sound in enumerate(_placement_sounds(placements)):
        template = _resref_text(
            getattr(sound, "template_resref", None) or getattr(sound, "resref", None)
        )
        sound_id = _stable_sound_id(sound, template, index, used_ids)
        if not template:
            warnings.append(
                MapStudioPIEAudioWarning(
                    "missing_uts_resref",
                    sound_id,
                    f"Sound {sound_id!r} has no UTS template resref.",
                )
            )
            continue

        uts_bytes = _resource_bytes(resource_manager, template, ResourceType.UTS, game_tag)
        if not uts_bytes:
            warnings.append(
                MapStudioPIEAudioWarning(
                    "missing_uts",
                    sound_id,
                    f"UTS template {template!r} could not be resolved for {game_tag}.",
                )
            )
            continue
        try:
            uts = read_uts(uts_bytes)
        except Exception as exc:
            warnings.append(
                MapStudioPIEAudioWarning(
                    "invalid_uts",
                    sound_id,
                    f"UTS template {template!r} could not be parsed: {exc}",
                )
            )
            continue

        clips: list[str] = []
        seen_clips: set[str] = set()
        for raw_clip in tuple(getattr(uts, "sounds", ()) or ()):
            clip = _resref_text(raw_clip)
            if clip and clip not in seen_clips:
                clips.append(clip)
                seen_clips.add(clip)

        if not clips:
            warnings.append(
                MapStudioPIEAudioWarning(
                    "empty_uts",
                    sound_id,
                    f"UTS template {template!r} contains no sound clips.",
                )
            )
        elif check_clip_resources:
            for clip in clips:
                if _resource_bytes(resource_manager, clip, ResourceType.WAV, game_tag) is None:
                    warnings.append(
                        MapStudioPIEAudioWarning(
                            "missing_wav",
                            sound_id,
                            f"WAV resource {clip!r} referenced by {template!r} could not be resolved.",
                        )
                    )

        position = _position3(getattr(sound, "position", None))
        position = (position[0], position[1], position[2] + _finite_float(getattr(uts, "elevation", 0.0)))
        min_distance = max(0.0, _finite_float(getattr(uts, "min_distance", 0.0)))
        max_distance = max(0.0, _finite_float(getattr(uts, "max_distance", 0.0)))
        if bool(getattr(uts, "positional", False)) and max_distance > 0.0 and max_distance < min_distance:
            warnings.append(
                MapStudioPIEAudioWarning(
                    "invalid_distance_range",
                    sound_id,
                    f"UTS template {template!r} has MaxDistance below MinDistance; PIE clamps the preview range.",
                )
            )
            max_distance = min_distance

        specs.append(
            MapStudioPIEAmbientSoundSpec(
                sound_id=sound_id,
                template_resref=template,
                tag=str(getattr(sound, "tag", "") or getattr(uts, "tag", "") or ""),
                position=position,
                clip_resrefs=tuple(clips),
                active=bool(getattr(uts, "active", False)),
                continuous=bool(getattr(uts, "continuous", False)),
                looping=bool(getattr(uts, "looping", False)),
                positional=bool(getattr(uts, "positional", False)),
                random_pick=bool(getattr(uts, "random_pick", False)),
                random_position=bool(getattr(uts, "random_position", False)),
                random_range_x=max(0.0, _finite_float(getattr(uts, "random_range_x", 0.0))),
                random_range_y=max(0.0, _finite_float(getattr(uts, "random_range_y", 0.0))),
                min_distance=min_distance,
                max_distance=max_distance,
                volume=max(0, int(getattr(uts, "volume", 0) or 0)),
                volume_variation=max(0, int(getattr(uts, "volume_variation", 0) or 0)),
                pitch_variation=max(0.0, _finite_float(getattr(uts, "pitch_variation", 0.0))),
                interval_seconds=max(0.0, _finite_float(getattr(uts, "interval", 0)) / 1000.0),
                interval_variation_seconds=max(
                    0.0,
                    _finite_float(getattr(uts, "interval_variation", 0)) / 1000.0,
                ),
                priority=int(getattr(uts, "priority", 0) or 0),
            )
        )

    return MapStudioPIEAmbientSoundPlan(tuple(specs), tuple(warnings))


__all__ = [
    "PIE_AUDIO_APPROXIMATION_NOTE",
    "MapStudioPIEAmbientSoundPlan",
    "MapStudioPIEAmbientSoundSpec",
    "MapStudioPIEAudioWarning",
    "build_map_studio_pie_ambient_sound_plan",
]
