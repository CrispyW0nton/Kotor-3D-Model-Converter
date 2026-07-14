"""QtMultimedia preview for KOTOR dialogue voice and sound resources.

This adapter owns only the editor playback boundary.  It resolves WAV and MP3
resources by ResRef through the resource source supplied by GhostStudio, asks
PyKotor to remove KOTOR's WAV/MP3 wrapping where present, and keeps the
in-memory device alive for the duration of Qt playback.  A successful preview
is not evidence that the resource has been staged, packaged, or played by
retail KOTOR.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtMultimedia

from pykotor.resource.formats.wav import get_playable_bytes, read_wav
from pykotor.resource.type import ResourceType


def _game_key(value: object) -> str:
    text = str(value or "K2").strip().upper()
    return "K1" if text in {"K1", "1", "KOTOR", "KOTOR1"} else "K2"


def _resource_payload(value: object) -> bytes | None:
    """Return bytes from the common GhostStudio/PyKotor resource wrappers."""

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


def _resolve_narrative_resource_bytes(
    resource_source: Any,
    resref: str,
    game: str,
    restype: ResourceType,
) -> bytes | None:
    """Resolve one target-game audio resource without mutating the installation.

    The small protocol intentionally accepts both GhostStudio's resource
    manager and its provider adapter.  Strict target-game lookup is attempted
    first so a missing K2 voice cannot be hidden by an accidental K1 fallback.
    """

    if resource_source is None:
        return None
    name = str(resref or "").strip().lower()
    if not name:
        return None
    target_game = _game_key(game)
    restype_id = restype.type_id

    for method_name in ("get_strict", "get_resource_data", "get"):
        getter = getattr(resource_source, method_name, None)
        if not callable(getter):
            continue
        for args in ((name, restype_id, target_game), (name, restype_id)):
            try:
                payload = _resource_payload(getter(*args))
            except (KeyError, LookupError, OSError, TypeError, ValueError):
                payload = None
            except Exception:
                payload = None
            if payload:
                return payload

    reader = getattr(resource_source, "read_bytes", None)
    if callable(reader):
        queries = (
            {"game": target_game, "resref": name, "restype": restype.name},
            {"game": target_game, "resref": name, "restype": restype_id},
        )
        for query in queries:
            try:
                payload = _resource_payload(reader(query))
            except Exception:
                payload = None
            if payload:
                return payload

    resource = getattr(resource_source, "resource", None)
    if callable(resource):
        for resource_type in (restype, restype_id):
            try:
                payload = _resource_payload(resource(name, resource_type))
            except Exception:
                payload = None
            if payload:
                return payload
    return None


def resolve_narrative_wav_bytes(resource_source: Any, resref: str, game: str) -> bytes | None:
    """Resolve one target-game WAV without mutating the source installation."""

    return _resolve_narrative_resource_bytes(resource_source, resref, game, ResourceType.WAV)


def resolve_narrative_audio_bytes(
    resource_source: Any,
    resref: str,
    game: str,
) -> tuple[bytes, ResourceType] | None:
    """Resolve a narrative WAV first, then a genuine loose MP3 resource."""

    for restype in (ResourceType.WAV, ResourceType.MP3):
        payload = _resolve_narrative_resource_bytes(resource_source, resref, game, restype)
        if payload:
            return payload, restype
    return None


class NarrativeAudioPreview(QtCore.QObject):
    """Own one non-looping dialogue audio preview at a time."""

    previewStarted = QtCore.Signal(str)
    previewStopped = QtCore.Signal()
    previewFailed = QtCore.Signal(str)
    progressChanged = QtCore.Signal(int, int)

    def __init__(
        self,
        resource_source: Any = None,
        game: str = "K2",
        parent: QtCore.QObject | None = None,
        *,
        player: Any | None = None,
        audio_output: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self.resource_source = resource_source
        self.game = _game_key(game)
        self.player = player if player is not None else QtMultimedia.QMediaPlayer(self)
        self.audio_output = audio_output if audio_output is not None else QtMultimedia.QAudioOutput(self)
        set_output = getattr(self.player, "setAudioOutput", None)
        if callable(set_output):
            set_output(self.audio_output)
        self._buffer: QtCore.QBuffer | None = None
        self._active = False
        self._source_label = ""
        self._connect_player_signal("mediaStatusChanged", self._media_status_changed)
        self._connect_player_signal("playbackStateChanged", self._playback_state_changed)
        self._connect_player_signal("positionChanged", self._position_changed)
        self._connect_player_signal("durationChanged", self._duration_changed)
        self._connect_player_signal("errorOccurred", self._playback_error)

    @property
    def active(self) -> bool:
        return self._active

    @property
    def source_label(self) -> str:
        return self._source_label

    @property
    def preview_note(self) -> str:
        return (
            "Editor-only audio preview. Retail KOTOR remains the authority for "
            "resource lookup, dialogue timing, volume, and in-game playback."
        )

    def set_resource_source(self, resource_source: Any, game: str | None = None) -> None:
        self.stop()
        self.resource_source = resource_source
        if game is not None:
            self.game = _game_key(game)

    def play_resref(self, resref: str, game: str | None = None) -> bool:
        name = str(resref or "").strip().lower()
        target_game = _game_key(game or self.game)
        if not name:
            return self._fail("Enter a Sound or Voice-over ResRef before previewing audio.")
        resolved = resolve_narrative_audio_bytes(self.resource_source, name, target_game)
        if resolved is None:
            return self._fail(f"Audio resource {name!r} could not be resolved for {target_game}.")
        raw, restype = resolved
        suffix = "mp3" if restype is ResourceType.MP3 else "wav"
        try:
            playable = bytes(get_playable_bytes(read_wav(raw)))
        except Exception as exc:
            if restype is not ResourceType.MP3:
                return self._fail(f"WAV resource {name!r} could not be decoded: {exc}")
            # StreamVoice/StreamSounds may contain ordinary MP3 payloads rather
            # than KOTOR's wrapped WAV form. QtMultimedia owns that decode.
            playable = raw
        if not playable:
            return self._fail(f"Audio resource {name!r} decoded to no playable audio.")
        self.game = target_game
        return self._play_bytes(playable, f"{name}.{suffix}")

    def play_file(self, path: str | Path) -> bool:
        target = Path(path)
        try:
            raw = target.read_bytes()
        except OSError as exc:
            return self._fail(f"Could not read audio file {target}: {exc}")
        try:
            playable = bytes(get_playable_bytes(read_wav(raw)))
        except Exception:
            # QtMultimedia can preview ordinary MP3/OGG/FLAC files selected by
            # the user even though they are not KOTOR WAV resources.  This is
            # deliberately a local preview path and makes no packaging claim.
            if target.suffix.lower() not in {".mp3", ".ogg", ".flac"}:
                return self._fail(f"Audio file {target.name!r} is not a playable KOTOR WAV resource.")
            playable = raw
        if not playable:
            return self._fail(f"Audio file {target.name!r} contains no playable bytes.")
        return self._play_bytes(playable, target.name)

    def _play_bytes(self, playable: bytes, source_label: str) -> bool:
        if QtCore.QCoreApplication.instance() is None:
            return self._fail("Audio preview requires an active GhostStudio Qt session.")
        self.stop(emit_signal=False)
        self._buffer = QtCore.QBuffer(self)
        self._buffer.setData(QtCore.QByteArray(playable))
        if not self._buffer.open(QtCore.QIODevice.ReadOnly):
            self._release_buffer()
            return self._fail("GhostStudio could not open the in-memory audio preview buffer.")
        suffix = Path(source_label).suffix.lower().lstrip(".")
        if not suffix:
            suffix = "wav" if playable.startswith(b"RIFF") else "mp3"
        try:
            self.player.setSourceDevice(
                self._buffer,
                QtCore.QUrl(f"memory://scripting-suite/{Path(source_label).stem}.{suffix}"),
            )
            self._source_label = str(source_label)
            self._active = True
            self.player.play()
        except Exception as exc:
            self._active = False
            self._release_buffer()
            return self._fail(f"QtMultimedia could not start audio preview: {exc}")
        self.previewStarted.emit(self._source_label)
        return True

    def stop(self, *, emit_signal: bool = True) -> None:
        was_active = self._active
        self._active = False
        try:
            self.player.stop()
            set_source = getattr(self.player, "setSource", None)
            if callable(set_source):
                set_source(QtCore.QUrl())
        finally:
            self._release_buffer()
            self._source_label = ""
        if emit_signal and was_active:
            self.previewStopped.emit()

    def close(self) -> None:
        self.stop()

    def _connect_player_signal(self, name: str, callback: Any) -> None:
        signal = getattr(self.player, name, None)
        connect = getattr(signal, "connect", None)
        if callable(connect):
            connect(callback)

    def _release_buffer(self) -> None:
        if self._buffer is None:
            return
        self._buffer.close()
        self._buffer.deleteLater()
        self._buffer = None

    def _media_status_changed(self, status: Any) -> None:
        if status == QtMultimedia.QMediaPlayer.EndOfMedia:
            self.stop()

    def _playback_state_changed(self, state: Any) -> None:
        if state == QtMultimedia.QMediaPlayer.StoppedState and self._active:
            self.stop()

    def _position_changed(self, position_ms: int) -> None:
        duration = getattr(self.player, "duration", lambda: 0)()
        self.progressChanged.emit(max(0, int(position_ms)), max(0, int(duration or 0)))

    def _duration_changed(self, duration_ms: int) -> None:
        position = getattr(self.player, "position", lambda: 0)()
        self.progressChanged.emit(max(0, int(position or 0)), max(0, int(duration_ms)))

    def _playback_error(self, error: Any, message: str = "") -> None:
        if error == QtMultimedia.QMediaPlayer.NoError:
            return
        text = str(message or getattr(error, "name", "") or "QtMultimedia playback failed.")
        self._active = False
        self._release_buffer()
        self.previewFailed.emit(text)

    def _fail(self, message: str) -> bool:
        self.stop(emit_signal=False)
        self.previewFailed.emit(str(message or "Audio preview failed."))
        return False


__all__ = [
    "NarrativeAudioPreview",
    "resolve_narrative_audio_bytes",
    "resolve_narrative_wav_bytes",
]
