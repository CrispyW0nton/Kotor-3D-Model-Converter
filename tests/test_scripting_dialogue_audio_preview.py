from __future__ import annotations

from io import BytesIO
import importlib.util
import os
from pathlib import Path
import sys
import wave


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
_APP = None


def _application():
    from PySide6 import QtWidgets

    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def _load_canonical(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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
        self.positionChanged = _Signal()
        self.durationChanged = _Signal()
        self.errorOccurred = _Signal()
        self.output = None
        self.device = None
        self.url = None
        self.play_calls = 0
        self.stop_calls = 0
        self.source_resets = 0
        self._duration = 2000
        self._position = 0

    def setAudioOutput(self, output) -> None:
        self.output = output

    def setSourceDevice(self, device, url) -> None:
        self.device = device
        self.url = url

    def setSource(self, _url) -> None:
        self.source_resets += 1

    def play(self) -> None:
        self.play_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1

    def duration(self) -> int:
        return self._duration

    def position(self) -> int:
        return self._position


class _FakeOutput:
    pass


def test_narrative_preview_resolves_target_game_decodes_and_keeps_buffer_alive() -> None:
    from pykotor.resource.type import ResourceType
    from src.adapters.qt_audio.narrative_audio_preview import NarrativeAudioPreview

    app = _application()

    class Manager:
        def __init__(self) -> None:
            self.requests = []

        def get_strict(self, resref, restype, game):
            self.requests.append((resref, restype, game))
            return _pcm_wave() if (resref, game) == ("dlg_line_01", "K2") else None

    manager = Manager()
    player = _FakePlayer()
    output = _FakeOutput()
    preview = NarrativeAudioPreview(manager, "K2", player=player, audio_output=output)
    starts = []
    progress = []
    preview.previewStarted.connect(starts.append)
    preview.progressChanged.connect(lambda position, duration: progress.append((position, duration)))

    assert preview.play_resref("DLG_LINE_01", "K2")
    assert manager.requests == [("dlg_line_01", ResourceType.WAV.type_id, "K2")]
    assert player.output is output
    assert player.play_calls == 1
    assert player.device is preview._buffer
    assert preview._buffer is not None and preview._buffer.isOpen()
    assert starts == ["dlg_line_01.wav"]
    assert "Retail KOTOR remains" in preview.preview_note

    player.positionChanged.emit(750)
    assert progress[-1] == (750, 2000)
    preview.stop()
    app.processEvents()
    assert preview._buffer is None
    assert not preview.active


def test_narrative_preview_reports_missing_resref_without_claiming_runtime_proof() -> None:
    from src.adapters.qt_audio.narrative_audio_preview import NarrativeAudioPreview

    _application()

    class MissingManager:
        def get_strict(self, *_args):
            return None

    preview = NarrativeAudioPreview(
        MissingManager(),
        "K1",
        player=_FakePlayer(),
        audio_output=_FakeOutput(),
    )
    failures = []
    preview.previewFailed.connect(failures.append)

    assert not preview.play_resref("missing_vo", "K1")
    assert failures == ["Audio resource 'missing_vo' could not be resolved for K1."]
    assert not preview.active


def test_narrative_preview_falls_back_to_loose_mp3_without_aliasing_it_as_wav() -> None:
    from pykotor.resource.type import ResourceType
    from src.adapters.qt_audio.narrative_audio_preview import NarrativeAudioPreview

    _application()
    raw_mp3 = b"ID3\x04\x00\x00\x00\x00\x00\x00" + (b"\x00" * 32)

    class Manager:
        def __init__(self) -> None:
            self.requests = []

        def get_strict(self, resref, restype, game):
            self.requests.append((resref, restype, game))
            if restype == ResourceType.MP3.type_id:
                return raw_mp3
            return None

    manager = Manager()
    player = _FakePlayer()
    preview = NarrativeAudioPreview(manager, "K2", player=player, audio_output=_FakeOutput())

    assert preview.play_resref("VO_MP3", "K2")
    assert manager.requests == [
        ("vo_mp3", ResourceType.WAV.type_id, "K2"),
        ("vo_mp3", ResourceType.MP3.type_id, "K2"),
    ]
    assert preview.source_label == "vo_mp3.mp3"
    assert bytes(preview._buffer.data()) == raw_mp3


def test_dialogue_audio_play_stop_and_browse_intents_reach_controller(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from PySide6 import QtCore, QtWidgets
    import src.adapters.qt_audio.narrative_audio_preview as audio_module

    window_module = _load_canonical(
        "ghoststudio_audio_test_dialogue_window",
        "src/gui/windows/qt_scripting_dialogue_studio.py",
    )
    controller_module = _load_canonical(
        "ghoststudio_audio_test_dialogue_controller",
        "src/gui/controllers/scripting_studio_controller.py",
    )
    DialogueEditorPage = window_module.DialogueEditorPage
    QtScriptingDialogueStudioWindow = window_module.QtScriptingDialogueStudioWindow
    ScriptingStudioController = controller_module.ScriptingStudioController

    app = _application()

    class FakePreview(QtCore.QObject):
        previewStarted = QtCore.Signal(str)
        previewStopped = QtCore.Signal()
        previewFailed = QtCore.Signal(str)
        progressChanged = QtCore.Signal(int, int)

        def __init__(self, source=None, game="K2", parent=None):
            super().__init__(parent)
            self.source = source
            self.game = game
            self.calls = []
            self.active = False
            self.source_label = ""

        def set_resource_source(self, source, game=None):
            self.source = source
            self.game = game or self.game

        def play_resref(self, resref, game=None):
            self.calls.append(("resref", resref, game))
            self.active = True
            self.source_label = f"{resref}.wav"
            self.previewStarted.emit(self.source_label)
            return True

        def play_file(self, path):
            self.calls.append(("file", Path(path)))
            self.active = True
            self.source_label = Path(path).name
            self.previewStarted.emit(self.source_label)
            return True

        def stop(self):
            if self.active:
                self.active = False
                self.previewStopped.emit()

    monkeypatch.setattr(audio_module, "NarrativeAudioPreview", FakePreview)
    local_audio = tmp_path / "custom_dialogue_voice.wav"
    local_audio.write_bytes(_pcm_wave())

    window = QtScriptingDialogueStudioWindow()
    controller = ScriptingStudioController(window, resource_manager=object(), output_root=tmp_path)
    try:
        document_id = controller.new_dialogue("K2", "audio_test")
        page = window.page_for_document(document_id)
        assert isinstance(page, DialogueEditorPage)

        page.sound_edit.setText("dlg_sound")
        page.sound_audio_play_button.click()
        assert controller._audio_preview.calls[-1] == ("resref", "dlg_sound", "K2")
        assert page.sound_audio_status_label.text() == "Playing dlg_sound.wav (editor preview)"
        assert page.sound_audio_stop_button.isEnabled()

        page.sound_audio_stop_button.click()
        assert page.sound_audio_status_label.text() == "Preview stopped"
        assert not page.sound_audio_stop_button.isEnabled()

        monkeypatch.setattr(
            QtWidgets.QFileDialog,
            "getOpenFileName",
            lambda *_args, **_kwargs: (str(local_audio), "KOTOR audio"),
        )
        page.voice_audio_browse_button.click()
        assert page.voice_edit.text() == "custom_dialogue_"
        assert "not staged or packaged" in page.voice_audio_status_label.text()

        page.voice_audio_play_button.click()
        assert controller._audio_preview.calls[-1] == ("file", local_audio)
        assert "editor preview" in page.voice_audio_status_label.text()
    finally:
        controller.stop_dialogue_audio()
        window.deleteLater()
        app.processEvents()


def test_dialogue_audio_controls_state_their_non_runtime_scope() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/gui/windows/qt_scripting_dialogue_studio.py").read_text(encoding="utf-8")
    assert "It does not stage the file or prove retail KOTOR playback." in source
    assert "dialogueAudioPreviewRequested" in source
    assert "dialogueAudioBrowseRequested" in source
    assert "dialogueAudioStopRequested" in source
