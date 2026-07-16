"""Animated door actors: plan resolution and state-driven clip selection."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


class _Resolver:
    def door_model(self, utd_resref):
        return {"door_mal02": "T_DOOR14", "sw_door_ffieldsi": ""}.get(str(utd_resref).lower(), "")


def test_door_plan_resolves_models_and_ids() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_doors import build_map_studio_pie_door_plan

    placements = SimpleNamespace(
        doors=(
            SimpleNamespace(template_resref="door_mal02", tag="MalachorDoor02", instance_id="i_a", position=(1.0, 2.0, 3.0), bearing=1.5),
            SimpleNamespace(template_resref="sw_door_ffieldsi", tag="Force Field Sith", instance_id="i_b", position=(4.0, 5.0, 6.0), bearing=0.0),
        )
    )
    specs = build_map_studio_pie_door_plan(placements, _Resolver())
    assert len(specs) == 2
    assert specs[0].door_id == "authored:door:i_a"
    assert specs[0].model_resref == "t_door14"
    assert specs[0].position == (1.0, 2.0, 3.0)
    assert specs[0].can_build_actor is True
    # Unresolved model -> no actor (keeps its static preview).
    assert specs[1].can_build_actor is False


def test_state_clip_candidates_pick_transition_or_hold() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_doors import door_state_clip_candidates

    assert door_state_clip_candidates(is_open=True, transitioning=True)[0] == "opening1"
    assert door_state_clip_candidates(is_open=True, transitioning=False)[0] == "opened1"
    assert door_state_clip_candidates(is_open=False, transitioning=True)[0] == "closing1"
    assert door_state_clip_candidates(is_open=False, transitioning=False)[0] == "closed"


class _FakeEngine:
    def __init__(self, available):
        self._available = {a.lower() for a in available}
        self.current_animation = None

    def play(self, name, loop=True, blend=False, **_):
        if str(name).lower() in self._available:
            self.current_animation = SimpleNamespace(name=str(name).lower())
            return True
        return False


def test_play_door_clip_uses_first_available() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_doors import door_state_clip_candidates, play_map_studio_pie_door_clip

    # Model names its held-open clip "opened" (not "opened1").
    engine = _FakeEngine(available=["opened", "closed"])
    played = play_map_studio_pie_door_clip(engine, door_state_clip_candidates(is_open=True, transitioning=False), loop=True)
    assert played == "opened"
    # Nothing resolves -> empty (caller keeps the current pose).
    bare = _FakeEngine(available=[])
    assert play_map_studio_pie_door_clip(bare, ("opening1", "open"), loop=False) == ""
