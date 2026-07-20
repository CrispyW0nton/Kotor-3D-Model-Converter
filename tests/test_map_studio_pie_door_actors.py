"""Animated door actors: plan resolution and state-driven clip selection."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

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
        if isinstance(available, dict):
            self._available = {str(name).lower(): float(length) for name, length in available.items()}
        else:
            self._available = {str(name).lower(): 1.0 for name in available}
        self.current_animation = None
        self.current_time = 0.0
        self._loop = False

    def play(self, name, loop=True, blend=False, **_):
        clean = str(name).lower()
        if clean in self._available:
            self.current_animation = SimpleNamespace(name=clean, length=self._available[clean])
            self.current_time = 0.0
            self._loop = bool(loop)
            return True
        return False

    def advance(self, delta_time):
        if self.current_animation is None:
            return False
        self.current_time += float(delta_time)
        if self._loop:
            self.current_time %= max(0.001, self.current_animation.length)
            return True
        if self.current_time >= self.current_animation.length:
            self.current_time = self.current_animation.length
            return False
        return True


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


def test_door_transition_honors_actual_one_second_clip_length() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_doors import advance_map_studio_pie_door_animation

    engine = _FakeEngine({"opening1": 1.0, "opened1": 2.0, "closed": 2.0})
    state = advance_map_studio_pie_door_animation(
        engine,
        wanted_open=True,
        current_open=False,
        transitioning=False,
        delta_time=0.35,
    )
    assert state.animation_name == "opening1"
    assert state.transitioning is True
    state = advance_map_studio_pie_door_animation(
        engine,
        wanted_open=True,
        current_open=state.is_open,
        transitioning=state.transitioning,
        delta_time=0.35,
    )
    assert state.animation_name == "opening1"
    assert state.transitioning is True
    state = advance_map_studio_pie_door_animation(
        engine,
        wanted_open=True,
        current_open=state.is_open,
        transitioning=state.transitioning,
        delta_time=0.35,
    )
    assert state.animation_name == "opening1"
    assert state.transitioning is True
    state = advance_map_studio_pie_door_animation(
        engine,
        wanted_open=True,
        current_open=state.is_open,
        transitioning=state.transitioning,
        delta_time=0.35,
    )
    assert state.animation_name == "opened1"
    assert state.transitioning is False


def test_door_actor_can_use_authored_bearing_without_character_quarter_turn() -> None:
    _configure_native_python_roots()
    from src.core.geometry.model_data import ModelNode, NodeFlags
    from src.core.modules.map_studio_pie import attach_map_studio_pie_actor

    preview = SimpleNamespace(
        root_node=ModelNode(name="preview", flags=int(NodeFlags.HEADER)),
        compute_bounds=lambda: None,
    )
    actor_model = SimpleNamespace(
        root_node=ModelNode(name="door", flags=int(NodeFlags.HEADER)),
    )
    bearing = 1.25
    attachment = attach_map_studio_pie_actor(
        preview,
        actor_model,
        position=(1.0, 2.0, 3.0),
        facing_radians=bearing,
        append_to_preview=False,
        model_yaw_offset_radians=0.0,
    )
    assert attachment is not None
    assert attachment.root_node.rotation[2] == pytest.approx(math.sin(bearing * 0.5))
    assert attachment.root_node.rotation[3] == pytest.approx(math.cos(bearing * 0.5))


def test_window_door_swap_contract_is_transactional_and_restorable() -> None:
    source = (
        ROOT
        / "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"
    ).read_text(encoding="utf-8")
    setup = source[source.index("    def _create_map_studio_pie_door_actors"):source.index("    def _update_map_studio_pie_door_actors")]
    cleanup = source[source.index("    def _remove_map_studio_pie_runtime_actors"):source.index("    def _handle_map_studio_pie_camera_input")]
    assert "original_children = list" in setup
    assert "append_to_preview=False" in setup
    assert "model_yaw_offset_radians=0.0" in setup
    assert "root.children = original_children" in setup
    assert "_map_studio_pie_hidden_door_groups" in setup
    assert "for original_index, group in self._map_studio_pie_hidden_door_groups" in cleanup


def test_window_door_runtime_skips_unchanged_held_poses() -> None:
    source = (
        ROOT
        / "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"
    ).read_text(encoding="utf-8")
    update = source[
        source.index("    def _update_map_studio_pie_door_actors"):
        source.index("    def _remove_map_studio_pie_runtime_actors")
    ]
    steady_guard = "if bool(wanted_open) == current_open and not transitioning:"
    assert steady_guard in update
    assert update.index(steady_guard) < update.index("advance_map_studio_pie_door_animation(")
    assert "current_open=current_open" in update
    assert "transitioning=transitioning" in update
