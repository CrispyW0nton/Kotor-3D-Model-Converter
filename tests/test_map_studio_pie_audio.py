from __future__ import annotations

from io import BytesIO
import ast
import math
import os
from pathlib import Path
from types import SimpleNamespace
import wave

import pytest

from pykotor.common.misc import Game, ResRef
from pykotor.resource.generics.uts import UTS, bytes_uts
from pykotor.resource.type import ResourceType

from src.core.modules.map_studio_pie_audio import (
    MapStudioPIEAmbientSoundPlan,
    MapStudioPIEAmbientSoundSpec,
    build_map_studio_pie_ambient_sound_plan,
)


class _FakeResourceManager:
    def __init__(self, resources: dict[tuple[str, int], bytes]) -> None:
        self.resources = resources
        self.requests: list[tuple[str, int, str]] = []

    def get(self, resref: str, resource_type: int, game: str = "K2") -> bytes | None:
        self.requests.append((resref, resource_type, game))
        return self.resources.get((str(resref).lower(), int(resource_type)))


def _uts_bytes() -> bytes:
    uts = UTS()
    uts.active = True
    uts.continuous = True
    uts.looping = False
    uts.positional = True
    uts.random_pick = True
    uts.random_position = True
    uts.random_range_x = 2.0
    uts.random_range_y = 3.0
    uts.elevation = 1.5
    uts.min_distance = 2.0
    uts.max_distance = 12.0
    uts.volume = 96
    uts.volume_variation = 8
    uts.pitch_variation = 0.1
    uts.interval = 6000
    uts.interval_variation = 3000
    uts.priority = 5
    uts.sounds = [ResRef("amb_one"), ResRef("amb_two"), ResRef("amb_one")]
    return bytes_uts(uts, Game.K2)


def _spec(**overrides: object) -> MapStudioPIEAmbientSoundSpec:
    values: dict[str, object] = {
        "sound_id": "sound-1",
        "template_resref": "ambient",
        "tag": "ambient",
        "position": (0.0, 0.0, 0.0),
        "clip_resrefs": ("amb_one",),
        "active": True,
        "continuous": False,
        "looping": True,
        "positional": True,
        "random_pick": False,
        "random_position": False,
        "random_range_x": 0.0,
        "random_range_y": 0.0,
        "min_distance": 2.0,
        "max_distance": 12.0,
        "volume": 127,
        "volume_variation": 0,
        "pitch_variation": 0.0,
        "interval_seconds": 0.0,
        "interval_variation_seconds": 0.0,
        "priority": 0,
    }
    values.update(overrides)
    return MapStudioPIEAmbientSoundSpec(**values)  # type: ignore[arg-type]


def test_pie_audio_plan_parses_uts_into_stable_editor_specs() -> None:
    manager = _FakeResourceManager(
        {
            ("test_ambient", ResourceType.UTS.type_id): _uts_bytes(),
            ("amb_one", ResourceType.WAV.type_id): b"RIFF-one",
            ("amb_two", ResourceType.WAV.type_id): b"RIFF-two",
        }
    )
    placements = SimpleNamespace(
        sounds=(
            SimpleNamespace(
                template_resref="TEST_AMBIENT",
                instance_id="sound-guid",
                tag="room_tone",
                position=(4.0, 5.0, 6.0),
            ),
        )
    )

    plan = build_map_studio_pie_ambient_sound_plan(placements, manager, "k2")

    assert plan.warnings == ()
    assert len(plan.specs) == 1
    spec = plan.specs[0]
    assert spec.sound_id == "sound-guid"
    assert spec.template_resref == "test_ambient"
    assert spec.position == (4.0, 5.0, 7.5)
    assert spec.clip_resrefs == ("amb_one", "amb_two")
    assert spec.active and spec.continuous and spec.positional and spec.random_pick
    assert spec.random_position
    assert spec.random_range_x == 2.0 and spec.random_range_y == 3.0
    assert spec.interval_seconds == 6.0
    assert spec.interval_variation_seconds == 3.0
    assert spec.base_gain == pytest.approx(96.0 / 127.0)
    assert "approximation" in plan.approximation_note.lower()


def test_pie_audio_plan_reports_missing_templates_and_clips_without_crashing() -> None:
    manager = _FakeResourceManager({("valid", ResourceType.UTS.type_id): _uts_bytes()})
    placements = SimpleNamespace(
        sounds=(
            SimpleNamespace(template_resref="", tag="blank", position=(0.0, 0.0, 0.0)),
            SimpleNamespace(template_resref="missing", tag="gone", position=(0.0, 0.0, 0.0)),
            SimpleNamespace(template_resref="valid", tag="valid", position=(0.0, 0.0, 0.0)),
        )
    )

    plan = build_map_studio_pie_ambient_sound_plan(placements, manager, "K2")

    assert len(plan.specs) == 1
    codes = [warning.code for warning in plan.warnings]
    assert codes == ["missing_uts_resref", "missing_uts", "missing_wav", "missing_wav"]


def test_pie_audio_distance_gain_is_linear_and_nonpositional_is_global() -> None:
    from src.adapters.qt_audio.map_studio_pie_audio import map_studio_pie_distance_gain

    spec = _spec()
    assert map_studio_pie_distance_gain(spec, (0.0, 0.0, 0.0)) == 1.0
    assert map_studio_pie_distance_gain(spec, (2.0, 0.0, 0.0)) == 1.0
    assert map_studio_pie_distance_gain(spec, (7.0, 0.0, 0.0)) == pytest.approx(0.5)
    assert map_studio_pie_distance_gain(spec, (12.0, 0.0, 0.0)) == 0.0
    assert map_studio_pie_distance_gain(_spec(positional=False), (1000.0, 0.0, 0.0)) == 1.0


def _short_pcm_wave() -> bytes:
    stream = BytesIO()
    with wave.open(stream, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8000)
        writer.writeframes(b"\x00\x00" * 160)
    return stream.getvalue()


def test_qt_pie_audio_adapter_decodes_updates_listener_and_cleans_up() -> None:
    pytest.importorskip("PySide6.QtMultimedia")
    from PySide6 import QtCore
    from src.adapters.qt_audio.map_studio_pie_audio import MapStudioPIEAmbientAudio

    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    manager = _FakeResourceManager({("amb_one", ResourceType.WAV.type_id): _short_pcm_wave()})
    audio = MapStudioPIEAmbientAudio(manager, "K2", seed=7)
    plan = MapStudioPIEAmbientSoundPlan((_spec(looping=False),), ())

    audio.start(plan, listener_position=(100.0, 0.0, 0.0))
    # Startup schedules bounded slices; it does not synchronously read/decode
    # every StreamSounds clip on the Qt call stack.
    assert manager.requests == []
    app.processEvents()
    snapshot = audio.debug_snapshot()
    assert snapshot["voices_created"] == 1
    assert snapshot["clips_loaded"] == 1
    assert snapshot["clips_started"] == 1
    assert snapshot["voice_ids"] == ("sound-1",)
    assert "KOTOR remains" in snapshot["approximation"]

    audio.set_listener_position((0.0, 0.0, 0.0))
    assert audio.counters.listener_updates == 1
    audio.stop()
    app.processEvents()
    assert audio.debug_snapshot()["voice_ids"] == ()
    assert audio.counters.active_players == 0
    audio.close()


def test_qt_pie_audio_random_choice_and_continuous_restart_are_deterministic() -> None:
    pytest.importorskip("PySide6.QtMultimedia")
    from PySide6 import QtCore, QtMultimedia
    from src.adapters.qt_audio.map_studio_pie_audio import MapStudioPIEAmbientAudio

    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    resources = {
        ("amb_one", ResourceType.WAV.type_id): _short_pcm_wave(),
        ("amb_two", ResourceType.WAV.type_id): _short_pcm_wave(),
    }
    plan = MapStudioPIEAmbientSoundPlan(
        (
            _spec(
                clip_resrefs=("amb_one", "amb_two"),
                random_pick=True,
                looping=False,
                continuous=True,
                interval_seconds=6.0,
                interval_variation_seconds=0.0,
            ),
        ),
        (),
    )
    first = MapStudioPIEAmbientAudio(_FakeResourceManager(resources), "K2", seed=41)
    second = MapStudioPIEAmbientAudio(_FakeResourceManager(resources), "K2", seed=41)
    first.start(plan)
    second.start(plan)
    app.processEvents()

    assert first.debug_snapshot()["current_clips"] == second.debug_snapshot()["current_clips"]
    voice = first._voices["sound-1"]
    voice._media_status_changed(QtMultimedia.QMediaPlayer.EndOfMedia)
    assert voice.timer.isActive()
    assert voice.timer.remainingTime() == pytest.approx(6000, abs=25)
    assert first.counters.scheduled_restarts == 1

    first.close()
    second.close()


def test_207tel_actual_uts_templates_build_a_pie_audio_plan_when_k2_is_installed() -> None:
    candidates = [
        Path(os.environ.get("K2_PATH", "")),
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"),
    ]
    k2 = next((path for path in candidates if path.is_dir()), None)
    if k2 is None:
        pytest.skip("KOTOR 2 installation is not available")

    from pykotor.extract.capsule import LazyCapsule
    from pykotor.resource.generics.git import read_git
    from src.core.assets.resource_manager import ResourceManager

    git_capsule = k2 / "Modules" / "207TEL.rim"
    if not git_capsule.is_file():
        pytest.skip("207TEL.rim is not available")

    manager = ResourceManager()
    assert manager.set_k2_dir(str(k2))
    git_resource = next(
        resource for resource in LazyCapsule(git_capsule) if resource.restype() is ResourceType.GIT
    )
    git = read_git(git_resource.data())

    plan = build_map_studio_pie_ambient_sound_plan(git, manager, "K2", check_clip_resources=False)

    assert len(plan.specs) >= 10
    templates = {spec.template_resref: spec for spec in plan.specs}
    assert "cantinasingles" in templates
    assert templates["cantinasingles"].interval_seconds == 6.0
    assert templates["cantinasingles"].continuous
    assert templates["cantinasingles"].random_pick
    assert all(math.isfinite(axis) for spec in plan.specs for axis in spec.position)


def test_module_editor_pie_wires_audio_start_throttled_listener_and_stop() -> None:
    source_path = (
        Path(__file__).parents[1]
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    window = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ModuleEditorWindow"
    )
    methods = {
        node.name: ast.unparse(node)
        for node in window.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "_start_map_studio_pie_ambient_audio" in methods["_start_map_studio_pie"]
    assert "_stop_map_studio_pie_ambient_audio" in methods["_stop_map_studio_pie"]
    assert "_update_map_studio_pie_ambient_audio" in methods["_tick_map_studio_pie"]
    listener_method = methods["_update_map_studio_pie_ambient_audio"]
    assert "frame.simulation_time" in listener_method and "* 5.0" in listener_method
    assert "set_listener_position" in listener_method
