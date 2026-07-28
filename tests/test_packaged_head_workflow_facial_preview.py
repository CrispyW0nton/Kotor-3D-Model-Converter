"""Head Workflow must send selected visemes to the real viewport contract."""

from __future__ import annotations

import importlib.util
import sys
from enum import IntEnum
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "native"
    / "GhostRigger.Core.Workflow"
    / "Python"
    / "src"
    / "core"
    / "characters"
    / "head_workflow.py"
)


def _load_head_workflow():
    name = "ghostrigger_packaged_head_workflow_facial_under_test"
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _Shapes(IntEnum):
    NEUTRAL = 0
    EE = 1
    EH = 2
    AH = 3
    OH = 4
    OOH = 5
    Y = 6
    STS = 7
    FV = 8
    NG = 9
    TH = 10
    MPB = 11
    TD = 12
    SH = 13
    L = 14
    KG = 15


def test_apply_viseme_persists_preview_pose_and_updates_viewport(monkeypatch) -> None:
    workflow = _load_head_workflow()
    head = SimpleNamespace(name="p_xariah")
    pose = SimpleNamespace(time=3.0 / 30.0, nodes={"f_jaw_g": object()})

    class _Playback:
        def load_talk_animation(self, model) -> bool:
            return model is head

        def animation_pose_for_viseme(self, index):
            assert index == 3
            return pose

    viewport_calls = []
    viewport = SimpleNamespace(
        set_animation_pose=lambda *args, **kwargs: viewport_calls.append(
            (args, kwargs)
        )
    )
    scene = SimpleNamespace()
    monkeypatch.setattr(workflow, "_get_head_model", lambda _scene: head)
    monkeypatch.setattr(
        workflow,
        "_import_lip_reader",
        lambda: SimpleNamespace(LIPShape=_Shapes),
    )
    monkeypatch.setattr(
        workflow,
        "_import_character_builder",
        lambda: SimpleNamespace(LIPPlayback=_Playback),
    )

    ok, message = workflow.apply_viseme(scene, 3, viewport=viewport)

    assert ok is True
    assert "AH" in message
    assert scene.head_facial_preview_pose is pose
    assert viewport_calls == [
        (
            (pose,),
            {"name": "talk:AH", "time": 3.0 / 30.0, "length": 0.5},
        )
    ]


def test_phoneme_defaults_match_kotor_lip_shape_contract() -> None:
    workflow = _load_head_workflow()
    by_label = dict(workflow.PHONEME_POSES)

    assert by_label["AH (open vowel)"] == 3
    assert by_label["MM (closed labial)"] == 11
    assert by_label["FV (labiodental)"] == 8
    assert by_label["TH (interdental)"] == 10
    assert by_label["SS (sibilant)"] == 7
