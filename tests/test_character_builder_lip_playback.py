"""Regression tests for the packaged Character Builder LIP runtime."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "native"
    / "GhostRigger.Core.Workflow"
    / "Python"
    / "src"
    / "core"
    / "characters"
    / "character_builder.py"
)


def _load_character_builder():
    name = "ghostrigger_character_builder_lip_under_test"
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _FakeAnimationEngine:
    def __init__(self, model) -> None:
        self.model = model
        self.current_animation = SimpleNamespace(
            name="talk",
            length=0.5,
            nodes=[
                SimpleNamespace(
                    controllers=[
                        {
                            "type": 8,
                            "times": [index / 30.0 for index in range(16)],
                            "values": [[float(index), 0.0, 0.0] for index in range(16)],
                        }
                    ]
                )
            ],
        )

    def play(self, name, **_kwargs) -> bool:
        return str(name).casefold() == "talk"

    def evaluate(self, time_seconds):
        shape = float(time_seconds) * 30.0
        return SimpleNamespace(
            time=float(time_seconds),
            nodes={
                "f_jaw_g": SimpleNamespace(
                    name="f_jaw_g",
                    position=(shape, 0.0, 0.0),
                    rotation=(0.0, 0.0, 0.0, 1.0),
                    scale=1.0,
                    alpha=None,
                    selfillum=None,
                )
            },
        )


def _engine_module():
    return SimpleNamespace(
        AnimationEngine=_FakeAnimationEngine,
        AnimPose=lambda time=0.0: SimpleNamespace(time=time, nodes={}),
        NodePose=lambda **values: SimpleNamespace(**values),
    )


def test_inherited_talk_pose_uses_shape_slots_and_direct_interpolation(
    monkeypatch,
) -> None:
    cb = _load_character_builder()
    monkeypatch.setattr(cb, "_import_animation_engine", _engine_module)
    playback = cb.LIPPlayback()

    assert playback.load_talk_animation(SimpleNamespace(name="p_xariah"))

    # A direct 25% blend from AH (3) to MPB (11) must land at 5.0. It must
    # not snap to either shape.
    pose = playback.animation_pose_for_shapes(3, 11, 0.25)

    assert pose.nodes["f_jaw_g"].position == pytest.approx((5.0, 0.0, 0.0))


def test_update_uses_get_shapes_and_real_duration(monkeypatch) -> None:
    cb = _load_character_builder()
    monkeypatch.setattr(cb, "_import_animation_engine", _engine_module)
    lip = SimpleNamespace(
        duration=1.0,
        get_shapes=lambda _time: (3, 11, 0.5),
    )
    playback = cb.LIPPlayback()
    playback.load_talk_animation(SimpleNamespace(name="p_xariah"))
    playback.load_lip(lip)
    playback.play()

    result = playback.update(0.2)

    assert result["f_jaw_g"]["position"] == pytest.approx((7.0, 0.0, 0.0))
    assert playback.duration == pytest.approx(1.0)


def test_playback_stops_after_duration(monkeypatch) -> None:
    cb = _load_character_builder()
    monkeypatch.setattr(cb, "_import_animation_engine", _engine_module)
    playback = cb.LIPPlayback()
    playback.load_talk_animation(SimpleNamespace(name="p_xariah"))
    playback.load_lip(
        SimpleNamespace(
            duration=0.1,
            get_shapes=lambda _time: (0, 0, 0.0),
        )
    )
    playback.play()

    assert playback.update(0.2) is None
    assert playback.is_playing is False
