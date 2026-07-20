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
        self.play_modes = []

    def play(self, name, loop=True, blend=False, **_kwargs):
        self.played.append(str(name).lower())
        self.play_modes.append((str(name).lower(), bool(loop)))
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


def test_seated_scene_uses_persistent_chair_loop() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_creatures import play_map_studio_pie_scene_animation

    engine = _FakeEngine(available=["animloop03", "animloop01", "pause1"])
    played = play_map_studio_pie_scene_animation(
        engine,
        ("animloop03", "animloop01"),
    )

    assert played == "animloop03"
    assert engine.play_modes == [("animloop03", True)]


def test_nonseated_scene_animation_remains_a_loop() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_creatures import play_map_studio_pie_scene_animation

    engine = _FakeEngine(available=["tlknorm", "pause1"])
    assert play_map_studio_pie_scene_animation(engine, ("tlknorm",)) == "tlknorm"
    assert engine.play_modes == [("tlknorm", True)]


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


def _project_with_creatures(*tags):
    return SimpleNamespace(
        game="K2",
        placements=SimpleNamespace(
            creatures=tuple(
                SimpleNamespace(
                    template_resref="c_test",
                    instance_id=f"i{index}",
                    tag=tag,
                    position=(float(index), 0.0, 0.0),
                    bearing=0.0,
                )
                for index, tag in enumerate(tags)
            ),
            metadata={},
        ),
    )


def _utc_with_tag(tag):
    from pykotor.common.misc import Game
    from pykotor.resource.generics.utc import UTC, bytes_utc

    utc = UTC()
    utc.tag = str(tag)
    return bytes_utc(utc, Game.K2)


def test_plan_assigns_scene_clips_to_matching_tag() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_creatures import build_map_studio_pie_creature_plan

    plan = build_map_studio_pie_creature_plan(
        _project_with_creature("SittingBith"),
        _Resolver(),
        game="K2",
        scene_animations={"sittingbith": ("animloop02", "animloop01")},
    )
    assert len(plan.specs) == 1
    # The matched creature carries the authored sit clips, not the idle default.
    assert plan.specs[0].render.animation_candidates == ("animloop02", "animloop01")
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


def test_duplicate_tags_match_getobjectbytag_occurrences_deterministically() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_creatures import build_map_studio_pie_creature_plan

    plan = build_map_studio_pie_creature_plan(
        _project_with_creatures("", ""),
        _Resolver(),
        game="K2",
        utc_reader=lambda resref, _game: _utc_with_tag("SittingCommMale") if resref == "c_test" else None,
        scene_animations={
            ("sittingcommmale", 0): ("animloop02", "animloop01"),
            ("sittingcommmale", 1): ("animloop03", "animloop01"),
        },
    )
    assert [spec.tag for spec in plan.specs] == ["SittingCommMale", "SittingCommMale"]
    assert plan.specs[0].render.animation_candidates[0] == "animloop02"
    assert plan.specs[1].render.animation_candidates[0] == "animloop03"
    assert any("matched 2 of 2 authored tag occurrence" in warning for warning in plan.warnings)


def test_plan_preserves_true_looping_chair_slot_from_onenter_constant() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_creatures import build_map_studio_pie_creature_plan
    from src.core.modules.map_studio_scene_animations import MapStudioSceneAnimationMap

    scene_map = MapStudioSceneAnimationMap(
        {("sittingalien", 0): ("animloop03", "animloop01")},
        intents={("sittingalien", 0): 38},
    )
    plan = build_map_studio_pie_creature_plan(
        _project_with_creature(""),
        _Resolver(),
        game="K2",
        utc_reader=lambda resref, _game: _utc_with_tag("SittingAlien") if resref == "c_test" else None,
        scene_animations=scene_map,
    )

    assert plan.specs[0].render.animation_candidates == ("animloop03", "animloop01")


def test_pie_pose_stamp_keeps_clip_identity_on_pose_for_detachable_heads() -> None:
    _configure_native_python_roots()
    from src.gui.windows.module_editor_window import _stamp_map_studio_pie_actor_pose

    source_model = SimpleNamespace(name="n_commf_twilek_f_pie_creature")
    actor = SimpleNamespace(actor_id="creature:29", source_model=source_model)
    pose = SimpleNamespace(nodes={}, time=2.0)

    assert _stamp_map_studio_pie_actor_pose(pose, actor, "animloop03") is pose
    assert pose._gr_animation_scene_object_id == "creature:29"
    assert pose._gr_animation_source_model_id == id(source_model)
    assert pose._gr_animation_source_model_name == source_model.name
    assert pose._gr_animation_name == "animloop03"


def test_matched_unsupported_constant_is_reported_not_called_idle_intent() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_creatures import build_map_studio_pie_creature_plan

    plan = build_map_studio_pie_creature_plan(
        _project_with_creature(""),
        _Resolver(),
        game="K2",
        utc_reader=lambda resref, _game: _utc_with_tag("SittingBith") if resref == "c_test" else None,
        scene_animations={("sittingbith", 0): ()},
    )
    # Rendering remains safe, while diagnostics retain that the authored
    # constant was unsupported rather than interpreting it as an idle command.
    assert plan.specs[0].render.animation_candidates == ("pause1", "walk", "run")
    assert any("not portable creature clips" in warning for warning in plan.warnings)


def test_blank_git_tags_match_actual_like_207tel_utc_tags_only() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_creatures import build_map_studio_pie_creature_plan

    templates = {
        "n_fatcomf001": _utc_with_tag("SittingSwoopganger"),
        "n_commm001": _utc_with_tag("SittingAlien"),
        "n_commm002": _utc_with_tag("SittingAlien2"),
        # The actual 207TEL Bith blueprint does not carry the script's
        # SittingBith tag, so its unsupported placeable-loop intent stays
        # unmatched rather than being guessed onto the creature.
        "207tel_bith1": _utc_with_tag("207tel_bith1"),
    }
    project = SimpleNamespace(
        game="K2",
        placements=SimpleNamespace(
            creatures=tuple(
                SimpleNamespace(
                    template_resref=resref,
                    instance_id=f"i{index}",
                    tag="",
                    position=(float(index), 0.0, 0.0),
                    bearing=0.0,
                )
                for index, resref in enumerate(templates)
            ),
            metadata={},
        ),
    )
    source_map = {
        ("sittingalien2", 0): ("animloop03", "animloop01"),
        ("sittingrodian", 0): ("animloop02", "animloop01"),
        ("sittingalien", 0): ("animloop03", "animloop01"),
        ("sittingswoopganger", 0): ("animloop02", "animloop01"),
        ("sittingcommmale", 0): ("animloop02", "animloop01"),
        ("sittingbith", 0): (),
        ("sittingcommfemale", 0): ("animloop02", "animloop01"),
        ("sittingcommmale", 1): ("animloop02", "animloop01"),
        ("sittingwalrusman", 0): ("animloop03", "animloop01"),
        ("sittingcommfemale", 1): ("animloop02", "animloop01"),
    }

    plan = build_map_studio_pie_creature_plan(
        project,
        _Resolver(),
        game="K2",
        utc_reader=lambda resref, _game: templates.get(resref),
        scene_animations=source_map,
    )

    assert [spec.tag for spec in plan.specs] == [
        "SittingSwoopganger",
        "SittingAlien",
        "SittingAlien2",
        "207tel_bith1",
    ]
    assert [spec.render.animation_candidates[0] for spec in plan.specs[:3]] == [
        "animloop02",
        "animloop03",
        "animloop03",
    ]
    assert plan.specs[3].render.animation_candidates == ("pause1", "walk", "run")
    assert any("matched 3 of 10 authored tag occurrence" in warning for warning in plan.warnings)
    assert any("7 authored target(s) had no matching" in warning for warning in plan.warnings)


def test_stale_sitting_tags_reconcile_only_complete_utc_template_families() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_creatures import build_map_studio_pie_creature_plan

    # Mirrors the identity shape of the user's source module. Eight table
    # sitters form complete target/blueprint families. The named story Rodian
    # has no Rodian identity token, while three Bith musicians compete for one
    # stale target, so neither family may be guessed.
    rows = (
        ("n_commf001", "CommF"),
        ("n_fatcomm001", "FatComM"),
        ("n_walrusman001", "Walrusman"),
        ("n_fatcomf001", "SittingSwoopganger"),
        ("n_commm001", "SittingAlien"),
        ("n_commm002", "SittingAlien2"),
        ("n_commf002", "CommF"),
        ("n_fatcomm002", "FatComM"),
        ("g_exthgr", "207_matu"),
        ("202tel_bith1", "207tel_bith1"),
        ("202tel_bith3", "207tel_bith3"),
        ("202tel_bith4", "207tel_bith4"),
    )
    templates = {resref: _utc_with_tag(tag) for resref, tag in rows}
    project = SimpleNamespace(
        game="K2",
        placements=SimpleNamespace(
            creatures=tuple(
                SimpleNamespace(
                    template_resref=resref,
                    instance_id=f"i{index}",
                    tag="",
                    position=(float(index), 0.0, 0.0),
                    bearing=0.0,
                )
                for index, (resref, _tag) in enumerate(rows)
            ),
            metadata={},
        ),
    )
    source_map = {
        ("sittingalien2", 0): ("animloop03", "animloop01"),
        ("sittingrodian", 0): ("animloop02", "animloop01"),
        ("sittingalien", 0): ("animloop03", "animloop01"),
        ("sittingswoopganger", 0): ("animloop02", "animloop01"),
        ("sittingcommmale", 0): ("animloop02", "animloop01"),
        ("sittingbith", 0): (),
        ("sittingcommfemale", 0): ("animloop02", "animloop01"),
        ("sittingcommmale", 1): ("animloop02", "animloop01"),
        ("sittingwalrusman", 0): ("animloop03", "animloop01"),
        ("sittingcommfemale", 1): ("animloop02", "animloop01"),
    }

    plan = build_map_studio_pie_creature_plan(
        project,
        _Resolver(),
        game="K2",
        utc_reader=lambda resref, _game: templates.get(resref),
        scene_animations=source_map,
    )
    by_template = {spec.runtime_template_resref: spec for spec in plan.specs}

    for resref in ("n_commf001", "n_commf002", "n_fatcomm001", "n_fatcomm002"):
        assert by_template[resref].render.animation_candidates[0] == "animloop02"
    assert by_template["n_walrusman001"].render.animation_candidates[0] == "animloop03"
    assert by_template["g_exthgr"].render.animation_candidates == ("pause1", "walk", "run")
    for resref in ("202tel_bith1", "202tel_bith3", "202tel_bith4"):
        assert by_template[resref].render.animation_candidates == ("pause1", "walk", "run")

    assert any("semantic reconciliation matched 5" in warning for warning in plan.warnings)
    assert any("commonfemale=2" in warning for warning in plan.warnings)
    assert any("commonmale=2" in warning for warning in plan.warnings)
    assert any("walrusman=1" in warning for warning in plan.warnings)
    assert any("family 'bith' has 1 target" in warning for warning in plan.warnings)
    assert any("but 3 unmatched" in warning for warning in plan.warnings)
    assert any("matched 8 of 10" in warning for warning in plan.warnings)


def test_specific_talk_clip_precedes_short_generic_alias() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_creatures import play_map_studio_pie_scene_animation
    from src.core.modules.map_studio_scene_animations import scene_animation_clip_candidates

    engine = _FakeEngine(available=["talk", "tlknorm", "pause1"])
    played = play_map_studio_pie_scene_animation(engine, scene_animation_clip_candidates(5))
    assert played == "tlknorm"


def test_partial_source_scene_reports_authored_coverage_not_creature_count() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_creatures import build_map_studio_pie_creature_plan

    source_map = {
        ("sittingalien2", 0): ("animloop03", "animloop01"),
        ("sittingrodian", 0): ("animloop02", "animloop01"),
        ("sittingalien", 0): ("animloop03", "animloop01"),
        ("sittingswoopganger", 0): ("animloop02", "animloop01"),
        ("sittingcommmale", 0): ("animloop02", "animloop01"),
        ("sittingbith", 0): (),
        ("sittingcommfemale", 0): ("animloop02", "animloop01"),
        ("sittingcommmale", 1): ("animloop02", "animloop01"),
        ("sittingwalrusman", 0): ("animloop03", "animloop01"),
        ("sittingcommfemale", 1): ("animloop02", "animloop01"),
    }
    plan = build_map_studio_pie_creature_plan(
        _project_with_creatures("SittingSwoopganger", "SittingAlien", "SittingAlien2"),
        _Resolver(),
        game="K2",
        scene_animations=source_map,
    )
    assert any("matched 3 of 10 authored tag occurrence" in warning for warning in plan.warnings)
    assert any("7 authored target(s) had no matching" in warning for warning in plan.warnings)
