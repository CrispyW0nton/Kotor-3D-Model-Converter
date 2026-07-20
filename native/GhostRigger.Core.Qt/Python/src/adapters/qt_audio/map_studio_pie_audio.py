"""QtMultimedia playback for Map Studio's approximate PIE audio.

The ambient adapter consumes the headless UTS plan from
``src.core.modules.map_studio_pie_audio``.  It intentionally previews the
parts an editor can reproduce safely: active clips, deterministic random
selection, looping/intermittent scheduling, pitch/volume variation, and
listener-distance attenuation.  KOTOR still owns authoritative mixing,
occlusion, room acoustics, priority stealing, and script-triggered sounds.

The dialogue adapter owns two bounded one-shot channels for the Voice and
Sound ResRefs authored on a DLG node.  It shares the same read-only resource
resolution and PyKotor WAV decode boundary without claiming retail timing,
mixing, or lip-sync parity.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
import hashlib
from io import BytesIO
import math
import random
import wave
from typing import Any

from PySide6 import QtCore, QtMultimedia

from pykotor.resource.formats.wav import get_playable_bytes, read_wav
from pykotor.resource.type import ResourceType

from src.core.modules.map_studio_pie_audio import (
    MapStudioPIEAmbientSoundPlan,
    MapStudioPIEAmbientSoundSpec,
)


Vec3 = tuple[float, float, float]


def _playable_duration_seconds(payload: bytes) -> float | None:
    """Read a PCM WAV duration without depending on Qt's async metadata."""

    try:
        with wave.open(BytesIO(payload), "rb") as reader:
            rate = int(reader.getframerate())
            frames = int(reader.getnframes())
    except (EOFError, OSError, wave.Error):
        return None
    if rate <= 0 or frames < 0:
        return None
    result = frames / rate
    return result if math.isfinite(result) and result > 0.0 else None


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


@dataclass(slots=True)
class MapStudioPIEDialogueAudioDebugCounters:
    """Inspectable lifecycle totals for dialogue one-shot playback."""

    line_requests: int = 0
    resrefs_requested: int = 0
    duplicate_resrefs: int = 0
    clips_loaded: int = 0
    channels_started: int = 0
    missing_clips: int = 0
    decode_failures: int = 0
    playback_errors: int = 0
    stop_calls: int = 0
    finished_runs: int = 0


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


class _DialogueVoice(QtCore.QObject):
    """Own one bounded, non-looping dialogue playback channel."""

    def __init__(
        self,
        owner: "MapStudioPIEDialogueAudio",
        index: int,
        player_factory: Callable[[QtCore.QObject], Any] | None,
        audio_output_factory: Callable[[QtCore.QObject], Any] | None,
    ) -> None:
        super().__init__(owner)
        self.owner = owner
        self.index = int(index)
        self.player = (
            player_factory(self)
            if player_factory is not None
            else QtMultimedia.QMediaPlayer(self)
        )
        self.output = (
            audio_output_factory(self)
            if audio_output_factory is not None
            else QtMultimedia.QAudioOutput(self)
        )
        set_output = getattr(self.player, "setAudioOutput", None)
        if callable(set_output):
            set_output(self.output)
        set_volume = getattr(self.output, "setVolume", None)
        if callable(set_volume):
            set_volume(1.0)
        self._connect_player_signal("mediaStatusChanged", self._media_status_changed)
        self._connect_player_signal("playbackStateChanged", self._playback_state_changed)
        self._connect_player_signal("errorOccurred", self._playback_error)
        self.buffer: QtCore.QBuffer | None = None
        self.resref = ""
        self.roles: tuple[str, ...] = ()
        self.active = False
        self._duration_seconds: float | None = None

    @property
    def duration_seconds(self) -> float | None:
        duration = self._duration_seconds
        getter = getattr(self.player, "duration", None)
        if callable(getter):
            try:
                qt_duration = float(getter()) / 1000.0
            except (TypeError, ValueError, OverflowError):
                qt_duration = 0.0
            if math.isfinite(qt_duration) and qt_duration > 0.0:
                duration = max(float(duration or 0.0), qt_duration)
        return duration

    def _connect_player_signal(self, name: str, callback: Any) -> None:
        signal = getattr(self.player, name, None)
        connect = getattr(signal, "connect", None)
        if callable(connect):
            connect(callback)

    def start(self, playable: bytes, resref: str, roles: tuple[str, ...]) -> bool:
        self.stop()
        self.buffer = QtCore.QBuffer(self)
        self.buffer.setData(QtCore.QByteArray(playable))
        if not self.buffer.open(QtCore.QIODevice.ReadOnly):
            self._release_buffer()
            return False
        suffix = "wav" if playable.startswith(b"RIFF") else "mp3"
        try:
            self.player.setSourceDevice(
                self.buffer,
                QtCore.QUrl(f"memory://pie/dialogue/{resref}.{suffix}"),
            )
            self.resref = str(resref)
            self.roles = tuple(roles)
            self._duration_seconds = _playable_duration_seconds(playable)
            self.active = True
            self.player.play()
        except Exception:
            self.active = False
            self._reset_source()
            self._release_buffer()
            self.resref = ""
            self.roles = ()
            self._duration_seconds = None
            return False
        return True

    def stop(self) -> None:
        self.active = False
        try:
            stop = getattr(self.player, "stop", None)
            if callable(stop):
                stop()
            self._reset_source()
        finally:
            self._release_buffer()
            self.resref = ""
            self.roles = ()
            self._duration_seconds = None

    def _reset_source(self) -> None:
        set_source = getattr(self.player, "setSource", None)
        if callable(set_source):
            set_source(QtCore.QUrl())

    def _release_buffer(self) -> None:
        if self.buffer is None:
            return
        self.buffer.close()
        self.buffer.deleteLater()
        self.buffer = None

    def _media_status_changed(self, status: Any) -> None:
        if self.active and status == QtMultimedia.QMediaPlayer.EndOfMedia:
            self.owner._voice_finished(self)

    def _playback_state_changed(self, state: Any) -> None:
        if self.active and state == QtMultimedia.QMediaPlayer.StoppedState:
            self.owner._voice_finished(self)

    def _playback_error(self, error: Any, message: str = "") -> None:
        if not self.active or error == QtMultimedia.QMediaPlayer.NoError:
            return
        self.owner._voice_failed(
            self,
            str(message or getattr(error, "name", "") or "QtMultimedia playback failed."),
        )


class MapStudioPIEDialogueAudio(QtCore.QObject):
    """Play one authored PIE dialogue line through at most two Qt channels.

    KOTOR dialogue nodes may name both a voice-over and a sound effect.  The
    adapter resolves those WAV ResRefs against the selected game, decodes the
    Odyssey wrapper through PyKotor, and starts the distinct clips together.
    Repeated ResRefs are deliberately collapsed to one channel so a node that
    uses the same value for Sound and Voice does not double its gain.
    """

    warningRaised = QtCore.Signal(str)
    finished = QtCore.Signal()

    _MAX_CHANNELS = 2

    def __init__(
        self,
        resource_manager: Any,
        game: str,
        parent: QtCore.QObject | None = None,
        *,
        player_factory: Callable[[QtCore.QObject], Any] | None = None,
        audio_output_factory: Callable[[QtCore.QObject], Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.resource_manager = resource_manager
        self.game = str(game or "K1").strip().upper()
        self._voices = tuple(
            _DialogueVoice(self, index, player_factory, audio_output_factory)
            for index in range(self._MAX_CHANNELS)
        )
        self._clip_cache: dict[str, bytes | None] = {}
        self._runtime_warnings: list[str] = []
        self._runtime_warning_set: set[str] = set()
        self._counters = MapStudioPIEDialogueAudioDebugCounters()
        self._run_active = False
        self._line_duration_seconds: float | None = None

    @property
    def approximation_note(self) -> str:
        return (
            "PIE plays authored dialogue WAVs as an editor preview; retail KOTOR "
            "remains authoritative for mixing, lip sync, timing, and script-driven audio."
        )

    @property
    def active(self) -> bool:
        return any(voice.active for voice in self._voices)

    @property
    def current_resrefs(self) -> tuple[str, ...]:
        return tuple(voice.resref for voice in self._voices if voice.active and voice.resref)

    @property
    def current_voice_resref(self) -> str:
        return self._current_resref_for_role("voice")

    @property
    def current_sound_resref(self) -> str:
        return self._current_resref_for_role("sound")

    @property
    def current_duration_seconds(self) -> float | None:
        """Longest active line channel duration known to WAV/Qt metadata."""

        durations = tuple(
            value
            for voice in self._voices
            if voice.active and (value := voice.duration_seconds) is not None
        )
        return max(durations) if durations else self._line_duration_seconds

    @property
    def runtime_warnings(self) -> tuple[str, ...]:
        return tuple(self._runtime_warnings)

    @property
    def counters(self) -> MapStudioPIEDialogueAudioDebugCounters:
        return MapStudioPIEDialogueAudioDebugCounters(**asdict(self._counters))

    def debug_snapshot(self) -> dict[str, Any]:
        return {
            **asdict(self._counters),
            "game": self.game,
            "active": self.active,
            "max_channels": self._MAX_CHANNELS,
            "current_resrefs": self.current_resrefs,
            "voice_resref": self.current_voice_resref,
            "sound_resref": self.current_sound_resref,
            "duration_seconds": self.current_duration_seconds,
            "channels": tuple(
                {
                    "index": voice.index,
                    "active": voice.active,
                    "resref": voice.resref,
                    "roles": voice.roles,
                    "buffer_open": bool(voice.buffer is not None and voice.buffer.isOpen()),
                }
                for voice in self._voices
            ),
            "cached_clips": len(self._clip_cache),
            "runtime_warnings": self.runtime_warnings,
            "approximation": self.approximation_note,
        }

    def set_resource_source(self, resource_manager: Any, game: str | None = None) -> None:
        """Retarget a later PIE run and invalidate source-dependent decode state."""

        self.stop()
        self.resource_manager = resource_manager
        if game is not None:
            self.game = str(game or "K1").strip().upper()
        self._clip_cache.clear()
        self._runtime_warnings.clear()
        self._runtime_warning_set.clear()

    def play_line(self, voice_resref: str = "", sound_resref: str = "") -> bool:
        """Start the distinct audio authored on one dialogue node together."""

        self.stop()
        requested = (
            ("voice", str(voice_resref or "").strip().lower()),
            ("sound", str(sound_resref or "").strip().lower()),
        )
        requested = tuple((role, resref) for role, resref in requested if resref)
        if not requested:
            return False
        self._counters.line_requests += 1
        self._counters.resrefs_requested += len(requested)
        if QtCore.QCoreApplication.instance() is None:
            self._add_runtime_warning("PIE dialogue audio requires an active GhostStudio Qt session.")
            self._counters.finished_runs += 1
            self.finished.emit()
            return False

        distinct: dict[str, list[str]] = {}
        for role, resref in requested:
            roles = distinct.setdefault(resref, [])
            if roles:
                self._counters.duplicate_resrefs += 1
            roles.append(role)

        self._run_active = True
        started = 0
        for voice, (resref, roles) in zip(self._voices, distinct.items(), strict=False):
            playable = self._playable_clip(resref)
            if not playable:
                continue
            if not voice.start(playable, resref, tuple(roles)):
                self._counters.playback_errors += 1
                self._add_runtime_warning(
                    f"Dialogue WAV resource {resref!r} could not start in QtMultimedia."
                )
                continue
            started += 1
            self._counters.channels_started += 1

        if not started:
            self._finish_run()
            return False
        durations = tuple(
            value for voice in self._voices if (value := voice.duration_seconds) is not None
        )
        self._line_duration_seconds = max(durations) if durations else None
        return True

    def stop(self) -> None:
        self._counters.stop_calls += 1
        self._run_active = False
        self._line_duration_seconds = None
        for voice in self._voices:
            voice.stop()

    def close(self) -> None:
        self.stop()
        self._clip_cache.clear()

    def _current_resref_for_role(self, role: str) -> str:
        for voice in self._voices:
            if voice.active and role in voice.roles:
                return voice.resref
        return ""

    def _playable_clip(self, resref: str) -> bytes | None:
        if resref in self._clip_cache:
            return self._clip_cache[resref]
        raw = _resource_bytes(self.resource_manager, resref, self.game)
        if not raw:
            self._clip_cache[resref] = None
            self._counters.missing_clips += 1
            self._add_runtime_warning(
                f"Dialogue WAV resource {resref!r} could not be resolved for {self.game}."
            )
            return None
        try:
            playable = bytes(get_playable_bytes(read_wav(raw)))
        except Exception as exc:
            self._clip_cache[resref] = None
            self._counters.decode_failures += 1
            self._add_runtime_warning(
                f"Dialogue WAV resource {resref!r} could not be decoded: {exc}"
            )
            return None
        if not playable:
            self._clip_cache[resref] = None
            self._counters.decode_failures += 1
            self._add_runtime_warning(
                f"Dialogue WAV resource {resref!r} decoded to no playable bytes."
            )
            return None
        self._clip_cache[resref] = playable
        self._counters.clips_loaded += 1
        return playable

    def _voice_finished(self, voice: _DialogueVoice) -> None:
        if not voice.active:
            return
        voice.stop()
        if not self.active:
            self._finish_run()

    def _voice_failed(self, voice: _DialogueVoice, message: str) -> None:
        if not voice.active:
            return
        resref = voice.resref
        self._counters.playback_errors += 1
        self._add_runtime_warning(
            f"Dialogue WAV resource {resref!r} playback failed: {message}"
        )
        self._voice_finished(voice)

    def _finish_run(self) -> None:
        if not self._run_active:
            return
        self._run_active = False
        self._counters.finished_runs += 1
        self.finished.emit()

    def _add_runtime_warning(self, message: str) -> None:
        text = str(message or "").strip()
        if not text or text in self._runtime_warning_set:
            return
        self._runtime_warning_set.add(text)
        self._runtime_warnings.append(text)
        self.warningRaised.emit(text)


__all__ = [
    "MapStudioPIEAmbientAudio",
    "MapStudioPIEAudioDebugCounters",
    "MapStudioPIEDialogueAudio",
    "MapStudioPIEDialogueAudioDebugCounters",
    "map_studio_pie_distance_gain",
]
