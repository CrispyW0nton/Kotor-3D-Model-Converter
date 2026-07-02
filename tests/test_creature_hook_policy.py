"""T2519 regression: creature rigs are not judged by humanoid hook expectations.

The Check Model table warned HOOK_MISSING for chestconjure / handconjure /
impact_bolt on every Drexl session — those are humanoid cutscene/item
attachment hooks that creature skeletons (vanilla c_drexlf included) simply do
not have.  Policy now:

- CREATURE mode: the humanoid required/expected hook lists are skipped.
- native_template_final rigs with a donor snapshot: the snapshot's hooks are
  the COMPLETE contract (required = snapshot hooks, expected = nothing).
- Humanoid/headless-body mode: unchanged — the warnings still fire.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.core.diagnostics.validation_service import ValidationService
from src.core.geometry.model_data import CharacterMode, PartSlot


_HUMANOID_EXPECTED = ("chestconjure", "handconjure", "impact_bolt")


class _FakeNode:
    def __init__(self, name):
        self.name = name
        self.children: list = []
        self.parent = None
        self.vertices: list = []
        self.skin_data: list = []
        self.bone_map: list = []


class _FakeModel:
    def __init__(self, node_names, metadata=None):
        self._nodes = [_FakeNode(n) for n in node_names]
        self.metadata = dict(metadata or {})
        self.supermodel = "NULL"
        self.game_version = "K2"

    def all_nodes(self):
        return list(self._nodes)


def _scene(model, mode):
    entry = SimpleNamespace(
        model=model, resref="x", game_version="K2", supermodel="NULL"
    )
    return SimpleNamespace(
        slots={PartSlot.HEADLESS_BODY: entry},
        game_version="K2",
        mode=mode,
        mode_locked=True,
    )


def _hook_issue_nodes(issues):
    return {
        str(getattr(i, "node", "") or "").lower()
        for i in issues
        if getattr(i, "code", "") == "HOOK_MISSING"
    }


def test_creature_mode_skips_humanoid_hook_expectations() -> None:
    model = _FakeModel(["rootdummy", "pelvis_g", "Lhand_g", "Rhand_g", "camerahook"])
    issues = ValidationService(_scene(model, CharacterMode.CREATURE), strict=True).validate()
    hook_nodes = _hook_issue_nodes(issues)
    for hook in _HUMANOID_EXPECTED:
        assert hook not in hook_nodes, (hook, hook_nodes)
    assert "headhook" not in hook_nodes  # humanoid required hook not demanded


def test_headless_body_mode_still_warns_on_missing_expected_hooks() -> None:
    model = _FakeModel(["rootdummy", "pelvis_g", "headhook", "rhand"])
    issues = ValidationService(
        _scene(model, CharacterMode.HEADLESS_BODY), strict=True
    ).validate()
    hook_nodes = _hook_issue_nodes(issues)
    for hook in _HUMANOID_EXPECTED:
        assert hook in hook_nodes, (hook, hook_nodes)


def test_native_template_snapshot_defines_complete_hook_contract() -> None:
    metadata = {
        "character_builder_rig_state": {
            "state": "native_template_final",
            "native_snapshot_present": True,
        },
        "native_skeleton_snapshot": {
            "hook_names": ["Lhand_g", "Rhand_g", "camerahook"],
        },
    }
    model = _FakeModel(
        ["rootdummy", "Lhand_g", "Rhand_g", "camerahook"], metadata=metadata
    )
    issues = ValidationService(
        _scene(model, CharacterMode.CREATURE), strict=True
    ).validate()
    hook_nodes = _hook_issue_nodes(issues)
    assert not hook_nodes, hook_nodes  # donor hooks all present; nothing extra expected


def test_native_template_snapshot_missing_donor_hook_still_errors() -> None:
    metadata = {
        "character_builder_rig_state": {
            "state": "native_template_final",
            "native_snapshot_present": True,
        },
        "native_skeleton_snapshot": {
            "hook_names": ["Lhand_g", "Rhand_g", "camerahook"],
        },
    }
    model = _FakeModel(["rootdummy", "Lhand_g", "Rhand_g"], metadata=metadata)
    issues = ValidationService(
        _scene(model, CharacterMode.CREATURE), strict=True
    ).validate()
    assert "camerahook" in _hook_issue_nodes(issues)
