"""QtMultimedia playback for Map Studio's approximate PIE ambient audio.

This adapter consumes the headless UTS plan from
``src.core.modules.map_studio_pie_audio``.  It intentionally previews the
parts an editor can reproduce safely: active clips, deterministic random
selection, looping/intermittent scheduling, pitch/volume variation, and
listener-distance attenuation.  KOTOR still owns authoritative mixing,
occlusion, room acoustics, priority stealing, and script-triggered sounds.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
import random
from typing import Any

from PySide6 import QtCore, QtMultimedia

from pykotor.resource.formats.wav import get_playable_bytes, read_wav
from pykotor.resource.type import ResourceType

from src.core.modules.map_studio_pie_audio import (
    MapStudioPIEAmbientSoundPlan,
    MapStudioPIEAmbientSoundSpec,
)


Vec3 = tuple[float, float, float]


@dataclass(slots=True)
class MapStudioPIEAudioDebugCounters:
    """Low-cost counters exposed for the PIE status/debug surfaces."""

    starts: int = 0
    stop_calls: int = 0
    specs_received: int = 0
    active_specs: int = 0
    voices_created: int = 0
    voices_truncated: int = 0
    clips_loaded: int = 0
    clips_started: int = 0
    scheduled_restarts: int = 0
    missing_clips: int = 0
    decode_failures: int = 0
    playback_errors: int = 0
    listener_updates: int = 0
    volume_updates: int = 0
    active_players: int = 0


def _position3(value: Any) -> Vec3:
    try:
        values = tuple(value)
    except TypeError:
        values = ()
    if len(values) < 3:
        return (0.0, 0.0, 0.0)
    result: list[float] = []
    for item in values[:3]:
        try:
            number = float(item)
        except (TypeError, ValueError, OverflowError):
            number = 0.0
        result.append(number if math.isfinite(number) else 0.0)
    return (result[0], result[1], result[2])


def map_studio_pie_distance_gain(spec: MapStudioPIEAmbientSoundSpec, listener_position: Vec3) -> float:
    """Return linear editor attenuation for a listener and sound spec.

    This is intentionally described as editor attenuation, not Odyssey's
    exact rolloff curve.  A non-positive MaxDistance means the template does
    not provide a usable cutoff, so PIE leaves its gain unchanged.
    """

    if not spec.positional:
        return 1.0
    return _distance_gain(spec, listener_position, spec.position)


def _distance_gain(
    spec: MapStudioPIEAmbientSoundSpec,
    listener_position: Vec3,
    source_position: Vec3,
) -> float:
    if not spec.positional:
        return 1.0
    listener = _position3(listener_position)
    dx = listener[0] - source_position[0]
    dy = listener[1] - source_position[1]
    dz = listener[2] - source_position[2]
    distance = math.sqrt(dx * dx + dy * dy + dz * dz)
    minimum = max(0.0, float(spec.min_distance))
    maximum = max(0.0, float(spec.max_distance))
    if maximum <= 0.0 or distance <= minimum:
        return 1.0
    if distance >= maximum:
        return 0.0
    span = max(1.0e-6, maximum - minimum)
    return max(0.0, min(1.0, 1.0 - ((distance - minimum) / span)))


def _resource_bytes(resource_manager: Any, resref: str, game: str) -> bytes | None:
    getter = getattr(resource_manager, "get_strict", None)
    if not callable(getter):
        getter = getattr(resource_manager, "get", None)
    if not callable(getter):
        return None
    try:
        value = getter(resref, ResourceType.WAV.type_id, game)
    except TypeError:
        try:
            value = getter(resref, ResourceType.WAV.type_id)
        except Exception:
            return None
    except Exception:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    data = getattr(value, "data", None)
    if callable(data):
        try:
            data = data()
        except Exception:
            return None
    return bytes(data) if isinstance(data, (bytes, bytearray, memoryview)) else None


class _AmbientVoice(QtCore.QObject):
    def __init__(
        self,
        owner: "MapStudioPIEAmbientAudio",
        spec: MapStudioPIEAmbientSoundSpec,
        seed: int,
    ) -> None:
        super().__init__(owner)
        self.owner = owner
        self.spec = spec
        digest = hashlib.sha256(f"{seed}:{spec.sound_id}".encode("utf-8")).digest()
        self.rng = random.Random(int.from_bytes(digest[:8], "little"))
        self.player = QtMultimedia.QMediaPlayer(self)
        self.output = QtMultimedia.QAudioOutput(self)
        self.player.setAudioOutput(self.output)
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._play_next)
        self.player.mediaStatusChanged.connect(self._media_status_changed)
        self.player.errorOccurred.connect(self._playback_error)
        self.player.playbackStateChanged.connect(self.owner._refresh_active_player_count)
        self.buffer: QtCore.QBuffer | None = None
        self.listener_position: Vec3 = (0.0, 0.0, 0.0)
        self.random_position_offset: Vec3 = self._make_random_position_offset()
        self.source_position: Vec3 = (
            self.spec.position[0] + self.random_position_offset[0],
            self.spec.position[1] + self.random_position_offset[1],
            self.spec.position[2],
        )
        self.play_gain = 1.0
        self.current_clip = ""
        self.stopped = False

    def _make_random_position_offset(self) -> Vec3:
        if not self.spec.random_position:
            return (0.0, 0.0, 0.0)
        return (
            self.rng.uniform(-self.spec.random_range_x, self.spec.random_range_x),
            self.rng.uniform(-self.spec.random_range_y, self.spec.random_range_y),
            0.0,
        )

    def start(self, listener_position: Vec3) -> None:
        self.listener_position = _position3(listener_position)
        self._play_next()

    def set_listener_position(self, listener_position: Vec3) -> None:
        self.listener_position = _position3(listener_position)
        self._apply_volume()

    def _candidate_clips(self) -> tuple[str, ...]:
        clips = self.spec.clip_resrefs
        if not clips:
            return ()
        if self.spec.random_pick:
            start = self.rng.randrange(len(clips))
            return clips[start:] + clips[:start]
        return clips

    def _play_next(self) -> None:
        if self.stopped:
            return
        playable: bytes | None = None
        chosen = ""
        for clip in self._candidate_clips():
            playable = self.owner._playable_clip(clip, self.spec.sound_id)
            if playable:
                chosen = clip
                break
        if not playable:
            return

        self.player.stop()
        self.player.setLoops(
            QtMultimedia.QMediaPlayer.Infinite
            if self.spec.looping and len(self.spec.clip_resrefs) == 1
            else QtMultimedia.QMediaPlayer.Once
        )
        if self.buffer is not None:
            self.player.setSource(QtCore.QUrl())
            self.buffer.close()
            self.buffer.deleteLater()
        self.buffer = QtCore.QBuffer(self)
        self.buffer.setData(QtCore.QByteArray(playable))
        self.buffer.open(QtCore.QIODevice.ReadOnly)
        suffix = "mp3" if not playable.startswith(b"RIFF") else "wav"
        self.player.setSourceDevice(self.buffer, QtCore.QUrl(f"memory://pie/{chosen}.{suffix}"))
        self.current_clip = chosen

        variation = min(127, max(0, int(self.spec.volume_variation))) / 127.0
        self.play_gain = max(0.0, 1.0 + self.rng.uniform(-variation, variation))
        pitch = max(0.0, float(self.spec.pitch_variation))
        self.player.setPlaybackRate(max(0.5, min(2.0, 1.0 + self.rng.uniform(-pitch, pitch))))
        self._apply_volume()
        self.player.play()
        self.owner._counters.clips_started += 1

    def _apply_volume(self) -> None:
        distance_gain = _distance_gain(
            self.spec,
            self.listener_position,
            self.source_position,
        )
        gain = max(0.0, min(1.0, self.spec.base_gain * self.play_gain * distance_gain))
        if abs(float(self.output.volume()) - gain) > 0.001:
            self.output.setVolume(gain)
            self.owner._counters.volume_updates += 1

    def _media_status_changed(self, status: QtMultimedia.QMediaPlayer.MediaStatus) -> None:
        if self.stopped or status != QtMultimedia.QMediaPlayer.EndOfMedia:
            return
        if self.spec.looping:
            # Multi-clip loop sets use manual restarts so deterministic random
            # selection can choose another clip. Single clips use Qt Infinite.
            self._schedule_restart(0.0)
        elif self.spec.continuous:
            base = max(0.0, self.spec.interval_seconds)
            variation = max(0.0, self.spec.interval_variation_seconds)
            self._schedule_restart(max(0.0, base + self.rng.uniform(-variation, variation)))

    def _schedule_restart(self, delay_seconds: float) -> None:
        if self.stopped:
            return
        self.timer.start(max(0, int(round(float(delay_seconds) * 1000.0))))
        self.owner._counters.scheduled_restarts += 1

    def _playback_error(self, error: QtMultimedia.QMediaPlayer.Error, message: str) -> None:
        if self.stopped or error == QtMultimedia.QMediaPlayer.NoError:
            return
        self.owner._counters.playback_errors += 1
        self.owner._add_runtime_warning(
            f"{self.spec.sound_id}: QtMultimedia playback error: {message or error.name}"
        )

    def stop(self) -> None:
        if self.stopped:
            return
        self.stopped = True
        self.timer.stop()
        self.player.stop()
        self.player.setSource(QtCore.QUrl())
        self.output.setVolume(0.0)
        if self.buffer is not None:
            self.buffer.close()
            self.buffer.deleteLater()
            self.buffer = None


class MapStudioPIEAmbientAudio(QtCore.QObject):
    """Own and cleanly stop the ambient voices for one Map Studio PIE run."""

    warningRaised = QtCore.Signal(str)

    def __init__(
        self,
        resource_manager: Any,
        game: str,
        parent: QtCore.QObject | None = None,
        *,
        seed: int = 0,
        max_voices: int = 64,
        startup_stagger_ms: int = 12,
    ) -> None:
        super().__init__(parent)
        self.resource_manager = resource_manager
        self.game = str(game or "K1").strip().upper()
        self.seed = int(seed)
        self.max_voices = max(1, int(max_voices))
        self.startup_stagger_ms = max(0, int(startup_stagger_ms))
        self._start_generation = 0
        self._voices: dict[str, _AmbientVoice] = {}
        self._clip_cache: dict[str, bytes | None] = {}
        self._runtime_warnings: list[str] = []
        self._runtime_warning_set: set[str] = set()
        self._plan_warnings: tuple[Any, ...] = ()
        self._counters = MapStudioPIEAudioDebugCounters()
        self._listener_position: Vec3 = (0.0, 0.0, 0.0)

    @property
    def approximation_note(self) -> str:
        return (
            "PIE ambient audio approximates UTS playback; KOTOR remains the "
            "authority for final timing, mixing, occlusion, rooms, priority, and scripts."
        )

    @property
    def runtime_warnings(self) -> tuple[str, ...]:
        return tuple(self._runtime_warnings)

    @property
    def plan_warnings(self) -> tuple[Any, ...]:
        return self._plan_warnings

    @property
    def counters(self) -> MapStudioPIEAudioDebugCounters:
        return MapStudioPIEAudioDebugCounters(**asdict(self._counters))

    def debug_snapshot(self) -> dict[str, Any]:
        return {
            **asdict(self._counters),
            "voice_ids": tuple(self._voices),
            "current_clips": {sound_id: voice.current_clip for sound_id, voice in self._voices.items()},
            "cached_clips": len(self._clip_cache),
            "runtime_warnings": self.runtime_warnings,
            "approximation": self.approximation_note,
        }

    def start(
        self,
        plan: MapStudioPIEAmbientSoundPlan,
        listener_position: Vec3 = (0.0, 0.0, 0.0),
    ) -> None:
        if QtCore.QCoreApplication.instance() is None:
            raise RuntimeError("MapStudioPIEAmbientAudio requires an active Qt application.")
        self.stop()
        # A new PIE run may follow a module-overlay or custom-WAV edit. Do not
        # carry decoded bytes or warnings across that authoring boundary.
        self._clip_cache.clear()
        self._runtime_warnings.clear()
        self._runtime_warning_set.clear()
        self._counters.starts += 1
        self._counters.specs_received += len(plan.specs)
        self._plan_warnings = tuple(plan.warnings)
        self._listener_position = _position3(listener_position)
        active = tuple(spec for spec in plan.specs if spec.active and spec.clip_resrefs)
        self._counters.active_specs += len(active)
        generation = self._start_generation
        for index, spec in enumerate(active[: self.max_voices]):
            # Construct and decode one voice per event-loop slice. Cold custom
            # StreamSounds can be large; synchronously creating/decoding all 32
            # voices made PIE activation appear frozen.
            QtCore.QTimer.singleShot(
                index * self.startup_stagger_ms,
                lambda value=spec, token=generation: self._start_voice(token, value),
            )
        truncated = max(0, len(active) - self.max_voices)
        if truncated:
            self._counters.voices_truncated += truncated
            self._add_runtime_warning(
                f"PIE ambient preview limited to {self.max_voices} voices; {truncated} lower-order sounds were skipped."
            )
        self._refresh_active_player_count()

    def _start_voice(self, generation: int, spec: MapStudioPIEAmbientSoundSpec) -> None:
        """Create one scheduled voice unless this PIE audio run was stopped."""

        if generation != self._start_generation or spec.sound_id in self._voices:
            return
        voice = _AmbientVoice(self, spec, self.seed)
        self._voices[spec.sound_id] = voice
        self._counters.voices_created += 1
        voice.start(self._listener_position)
        self._refresh_active_player_count()

    def set_listener_position(self, listener_position: Vec3) -> None:
        self._listener_position = _position3(listener_position)
        self._counters.listener_updates += 1
        for voice in tuple(self._voices.values()):
            voice.set_listener_position(self._listener_position)

    def stop(self) -> None:
        # Invalidates scheduled startup callbacks before releasing live voices.
        self._start_generation += 1
        self._counters.stop_calls += 1
        voices = tuple(self._voices.values())
        self._voices.clear()
        for voice in voices:
            voice.stop()
            voice.deleteLater()
        self._counters.active_players = 0

    def _playable_clip(self, resref: str, sound_id: str) -> bytes | None:
        if resref in self._clip_cache:
            return self._clip_cache[resref]
        raw = _resource_bytes(self.resource_manager, resref, self.game)
        if not raw:
            self._clip_cache[resref] = None
            self._counters.missing_clips += 1
            self._add_runtime_warning(f"{sound_id}: WAV resource {resref!r} could not be resolved.")
            return None
        try:
            playable = bytes(get_playable_bytes(read_wav(raw)))
        except Exception as exc:
            self._clip_cache[resref] = None
            self._counters.decode_failures += 1
            self._add_runtime_warning(f"{sound_id}: WAV resource {resref!r} could not be decoded: {exc}")
            return None
        if not playable:
            self._clip_cache[resref] = None
            self._counters.decode_failures += 1
            self._add_runtime_warning(f"{sound_id}: WAV resource {resref!r} decoded to no playable bytes.")
            return None
        self._clip_cache[resref] = playable
        self._counters.clips_loaded += 1
        return playable

    @QtCore.Slot()
    def _refresh_active_player_count(self, *_args: Any) -> None:
        playing = QtMultimedia.QMediaPlayer.PlayingState
        self._counters.active_players = sum(
            1 for voice in self._voices.values() if voice.player.playbackState() == playing
        )

    def _add_runtime_warning(self, message: str) -> None:
        text = str(message).strip()
        if not text or text in self._runtime_warning_set:
            return
        self._runtime_warning_set.add(text)
        self._runtime_warnings.append(text)
        self.warningRaised.emit(text)

    def close(self) -> None:
        self.stop()
        self._clip_cache.clear()


__all__ = [
    "MapStudioPIEAmbientAudio",
    "MapStudioPIEAudioDebugCounters",
    "map_studio_pie_distance_gain",
]
