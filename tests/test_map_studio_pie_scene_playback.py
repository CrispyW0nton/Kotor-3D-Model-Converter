"""PIE plays each creature's authored scene animation, matched by tag.

The scene-animation map (from the OnEnter NCS) flows into the creature plan:
a creature whose tag matches gets its sit/talk clip candidates, and the
actor-prep plays the first clip the model actually contains (falling back to
a neutral idle). Unmatched creatures keep the idle.
"""

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


class _FakeEngine:
    """Plays only the clip names it was told the model contains."""

    def __init__(self, available):
        self._available = {str(a).lower() for a in available}
        self.current_animation = None
        self.played = []

    def play(self, name, loop=True, blend=False, **_kwargs):
        self.played.append(str(name).lower())
        if str(name).lower() in self._available:
            self.current_animation = SimpleNamespace(name=str(name).lower())
            return True
        return False


def test_scene_animation_plays_first_available_clip() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_creatures import play_map_studio_pie_scene_animation

    # Model has "sit" but not "cesit"; candidates prefer cesit then sit.
    engine = _FakeEngine(available=["sit", "pause1"])
    played = play_map_studio_pie_scene_animation(engine, ("cesit", "sit", "sitcross"))
    assert played == "sit"
    assert engine.current_animation.name == "sit"


def test_scene_animation_falls_back_to_idle_when_none_resolve() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_creatures import play_map_studio_pie_scene_animation

    engine = _FakeEngine(available=["pause1"])  # no sit clips
    played = play_map_studio_pie_scene_animation(engine, ("sit", "sitcross"))
    assert played == "pause1"  # neutral safe idle


class _Resolver:
    def creature_model(self, resref):
        return "n_seated" if resref else ""

    def creature_head_model(self, resref):
        return ""


def _project_with_creature(tag):
    return SimpleNamespace(
        game="K2",
        placements=SimpleNamespace(
            creatures=(SimpleNamespace(template_resref="c_test", instance_id="i1", tag=tag, position=(0.0, 0.0, 0.0), bearing=0.0),),
            metadata={},
        ),
    )


def test_plan_assigns_scene_clips_to_matching_tag() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_creatures import build_map_studio_pie_creature_plan

    plan = build_map_studio_pie_creature_plan(
        _project_with_creature("SittingBith"),
        _Resolver(),
        game="K2",
        scene_animations={"sittingbith": ("sit", "sitdrink")},
    )
    assert len(plan.specs) == 1
    # The matched creature carries the authored sit clips, not the idle default.
    assert plan.specs[0].render.animation_candidates == ("sit", "sitdrink")
    assert any("matched 1 of 1" in w for w in plan.warnings)


def test_plan_leaves_unmatched_creature_on_idle_default() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_creatures import build_map_studio_pie_creature_plan

    plan = build_map_studio_pie_creature_plan(
        _project_with_creature("SomeOtherNpc"),
        _Resolver(),
        game="K2",
        scene_animations={"sittingbith": ("sit",)},
    )
    assert plan.specs[0].render.animation_candidates == ("pause1", "walk", "run")
    assert any("matched 0 of 1" in w for w in plan.warnings)
