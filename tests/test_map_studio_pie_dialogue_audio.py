from __future__ import annotations

from io import BytesIO
import os
import wave


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _application():
    from PySide6 import QtCore

    return QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])


def _pcm_wave() -> bytes:
    stream = BytesIO()
    with wave.open(stream, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8000)
        writer.writeframes(b"\x00\x00" * 160)
    return stream.getvalue()


class _Signal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)

    def emit(self, *args) -> None:
        for callback in tuple(self.callbacks):
            callback(*args)


class _FakePlayer:
    def __init__(self) -> None:
        self.mediaStatusChanged = _Signal()
        self.playbackStateChanged = _Signal()
        self.errorOccurred = _Signal()
        self.output = None
        self.device = None
        self.url = None
        self.play_calls = 0
        self.stop_calls = 0
        self.source_resets = 0

    def setAudioOutput(self, output) -> None:
        self.output = output

    def setSourceDevice(self, device, url) -> None:
        self.device = device
        self.url = url

    def setSource(self, _url) -> None:
        self.source_resets += 1
        self.device = None

    def play(self) -> None:
        self.play_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1


class _FakeOutput:
    def __init__(self) -> None:
        self.volume = None

    def setVolume(self, value: float) -> None:
        self.volume = float(value)


class _FakeResourceManager:
    def __init__(self, resources: dict[str, bytes]) -> None:
        self.resources = {str(name).lower(): data for name, data in resources.items()}
        self.requests: list[tuple[str, int, str]] = []

    def get_strict(self, resref: str, restype: int, game: str) -> bytes | None:
        self.requests.append((str(resref), int(restype), str(game)))
        return self.resources.get(str(resref).lower())


def _dialogue_audio(manager):
    from src.adapters.qt_audio.map_studio_pie_audio import MapStudioPIEDialogueAudio

    players = []
    outputs = []

    def player_factory(_parent):
        player = _FakePlayer()
        players.append(player)
        return player

    def output_factory(_parent):
        output = _FakeOutput()
        outputs.append(output)
        return output

    audio = MapStudioPIEDialogueAudio(
        manager,
        "K2",
        player_factory=player_factory,
        audio_output_factory=output_factory,
    )
    return audio, players, outputs


def test_dialogue_audio_plays_voice_and_sound_concurrently_and_finishes_once() -> None:
    from PySide6 import QtMultimedia
    from pykotor.resource.type import ResourceType

    app = _application()
    manager = _FakeResourceManager({"vo_line": _pcm_wave(), "line_sound": _pcm_wave()})
    audio, players, outputs = _dialogue_audio(manager)
    warnings = []
    finished = []
    audio.warningRaised.connect(warnings.append)
    audio.finished.connect(lambda: finished.append(True))

    assert audio.play_line("VO_LINE", "LINE_SOUND")
    assert manager.requests == [
        ("vo_line", ResourceType.WAV.type_id, "K2"),
        ("line_sound", ResourceType.WAV.type_id, "K2"),
    ]
    assert audio.current_resrefs == ("vo_line", "line_sound")
    assert audio.current_voice_resref == "vo_line"
    assert audio.current_sound_resref == "line_sound"
    assert audio.current_duration_seconds is not None
    assert abs(audio.current_duration_seconds - 0.02) < 1.0e-6
    snapshot = audio.debug_snapshot()
    assert snapshot["max_channels"] == 2
    assert len(snapshot["channels"]) == 2
    assert abs(snapshot["duration_seconds"] - 0.02) < 1.0e-6
    assert all(channel["buffer_open"] for channel in snapshot["channels"])
    assert [player.play_calls for player in players] == [1, 1]
    assert [output.volume for output in outputs] == [1.0, 1.0]
    assert warnings == []

    players[0].mediaStatusChanged.emit(QtMultimedia.QMediaPlayer.EndOfMedia)
    assert audio.current_resrefs == ("line_sound",)
    assert finished == []
    players[1].playbackStateChanged.emit(QtMultimedia.QMediaPlayer.StoppedState)
    app.processEvents()

    assert finished == [True]
    assert not audio.active
    assert audio.current_resrefs == ()
    assert audio.current_duration_seconds == 0.02
    assert all(voice.buffer is None for voice in audio._voices)
    assert audio.counters.finished_runs == 1
    audio.close()


def test_dialogue_audio_deduplicates_matching_voice_and_sound_and_stops_cleanly() -> None:
    app = _application()
    manager = _FakeResourceManager({"shared_line": _pcm_wave()})
    audio, players, _outputs = _dialogue_audio(manager)
    finished = []
    audio.finished.connect(lambda: finished.append(True))

    assert audio.play_line("SHARED_LINE", "shared_line")
    assert len(manager.requests) == 1
    assert audio.current_resrefs == ("shared_line",)
    assert audio.current_voice_resref == "shared_line"
    assert audio.current_sound_resref == "shared_line"
    assert sum(player.play_calls for player in players) == 1
    assert audio.counters.duplicate_resrefs == 1
    assert audio.counters.channels_started == 1

    audio.stop()
    app.processEvents()
    assert finished == []
    assert audio.current_resrefs == ()
    assert all(voice.buffer is None for voice in audio._voices)
    assert all(player.device is None for player in players)
    audio.close()


def test_dialogue_audio_reports_missing_and_invalid_wavs_then_finishes() -> None:
    _application()
    manager = _FakeResourceManager({"invalid_line": b"not-a-kotor-wave"})
    audio, _players, _outputs = _dialogue_audio(manager)
    warnings = []
    finished = []
    audio.warningRaised.connect(warnings.append)
    audio.finished.connect(lambda: finished.append(True))

    assert not audio.play_line("missing_line", "INVALID_LINE")
    assert len(warnings) == 2
    assert "could not be resolved" in warnings[0]
    assert "could not be decoded" in warnings[1]
    assert finished == [True]
    snapshot = audio.debug_snapshot()
    assert snapshot["missing_clips"] == 1
    assert snapshot["decode_failures"] == 1
    assert snapshot["channels_started"] == 0
    assert not snapshot["active"]
    assert "retail KOTOR" in snapshot["approximation"]
    audio.close()


def test_dialogue_audio_playback_error_warns_releases_buffer_and_finishes() -> None:
    from PySide6 import QtMultimedia

    app = _application()
    manager = _FakeResourceManager({"failing_line": _pcm_wave()})
    audio, players, _outputs = _dialogue_audio(manager)
    warnings = []
    finished = []
    audio.warningRaised.connect(warnings.append)
    audio.finished.connect(lambda: finished.append(True))

    assert audio.play_line("failing_line")
    players[0].errorOccurred.emit(QtMultimedia.QMediaPlayer.ResourceError, "backend failed")
    app.processEvents()

    assert warnings == [
        "Dialogue WAV resource 'failing_line' playback failed: backend failed"
    ]
    assert finished == [True]
    assert audio.counters.playback_errors == 1
    assert not audio.active
    assert all(voice.buffer is None for voice in audio._voices)
    audio.close()


def test_qt_audio_package_exports_dialogue_adapter() -> None:
    from src.adapters import qt_audio

    assert qt_audio.MapStudioPIEDialogueAudio.__name__ == "MapStudioPIEDialogueAudio"
    assert (
        qt_audio.MapStudioPIEDialogueAudioDebugCounters.__name__
        == "MapStudioPIEDialogueAudioDebugCounters"
    )
