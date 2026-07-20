"""Focused contracts for the PIE party follow-formation core.

KOTOR fields a player-controlled leader plus up to two trailing companions; the
party roster is campaign state, so PIE takes a configurable roster and places
followers behind the leader on walkable ground. The formation offsets are
clean-room approximations; these tests assert the structural contract (trailing,
staggered, facing-aware, walkmesh-snapped). Editor-side only.
"""

from __future__ import annotations

import math

import pytest


def test_roster_caps_at_two_and_dedupes() -> None:
    from src.core.modules.map_studio_pie_party import normalize_party_roster

    roster = normalize_party_roster(["Atton", "atton", "", "Kreia", "Bao-Dur"])
    assert [m.resref for m in roster] == ["atton", "kreia"]  # deduped, capped at 2
    assert [m.slot for m in roster] == [1, 2]
    assert all(m.is_valid for m in roster)
    assert normalize_party_roster([]) == ()


def test_zero_followers_returns_no_slots() -> None:
    from src.core.modules.map_studio_pie_party import party_follow_positions

    assert party_follow_positions((0.0, 0.0, 0.0), 0.0, 0) == ()


def test_single_follower_tucks_directly_behind_the_leader() -> None:
    from src.core.modules.map_studio_pie_party import party_follow_positions

    # Facing +X (east); "behind" is -X (west), no lateral offset for a lone follower.
    positions = party_follow_positions((10.0, 5.0, 2.0), 0.0, 1, rank_spacing=1.8)
    assert len(positions) == 1
    x, y, z = positions[0]
    assert x == pytest.approx(10.0 - 1.8)
    assert y == pytest.approx(5.0)
    assert z == pytest.approx(2.0)


def test_two_followers_stagger_left_and_right_behind_leader() -> None:
    from src.core.modules.map_studio_pie_party import party_follow_positions

    positions = party_follow_positions((0.0, 0.0, 0.0), 0.0, 2, rank_spacing=1.8, side_spacing=1.1)
    assert len(positions) == 2
    # Both behind the leader (x < 0 facing east).
    assert positions[0][0] < 0.0 and positions[1][0] < 0.0
    # Facing +X, right-hand perpendicular is -Y; slot 1 (odd) goes left (+Y), slot 2 (even) right (-Y).
    assert positions[0][1] == pytest.approx(1.1)
    assert positions[1][1] == pytest.approx(-1.1)


def test_formation_rotates_with_leader_facing() -> None:
    from src.core.modules.map_studio_pie_party import party_follow_positions

    # Facing +Y (north, pi/2); "behind" is -Y (south).
    positions = party_follow_positions((0.0, 0.0, 0.0), math.pi / 2.0, 1, rank_spacing=2.0)
    x, y, _z = positions[0]
    assert x == pytest.approx(0.0, abs=1e-9)
    assert y == pytest.approx(-2.0)


def test_party_actor_plan_resolves_roster_models() -> None:
    from src.core.modules.map_studio_pie_party import build_map_studio_pie_party_plan

    # "kreia" intentionally has no resolvable model; the roster still caps at 2.
    models = {"atton": ("p_attonbb", "p_attonh")}
    plan = build_map_studio_pie_party_plan(
        ["Atton", "Kreia", "Ghost"],
        model_resolver=lambda resref: models.get(resref),
    )
    assert [s.resref for s in plan] == ["atton", "kreia"]  # capped at two companions
    assert [s.slot for s in plan] == [1, 2]
    assert plan[0].body_model_resref == "p_attonbb" and plan[0].head_model_resref == "p_attonh"
    assert plan[0].can_build_actor is True
    # "kreia" is unresolved -> no model, cannot build an actor, but is not dropped.
    assert plan[1].body_model_resref == "" and plan[1].can_build_actor is False


def test_window_companion_actor_subsystem_is_wired_and_isolated() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"
    ).read_text(encoding="utf-8")
    # The companion actors are a separate retained-actor list, created at Play,
    # updated each tick, and torn down with the other runtime actors.
    assert "self._map_studio_pie_party_actors" in source
    assert "def _create_map_studio_pie_party_actors" in source
    assert "def _update_map_studio_pie_party_actors" in source
    assert "self._create_map_studio_pie_party_actors(session, preview_model, game)" in source
    assert "self._update_map_studio_pie_party_actors(delta_time)" in source
    # Body model comes from the same appearance path creatures use, and it never
    # joins the creature staggered-animation cohort.
    assert "resolve_body = getattr(resolver, \"creature_model\", None)" in source
    assert "attach_map_studio_pie_actor(" in source
    teardown = source[
        source.index("    def _remove_map_studio_pie_runtime_actors"):
        source.index("    def _handle_map_studio_pie_camera_input")
    ]
    assert "party_entries" in teardown and "self._map_studio_pie_party_actors = []" in teardown


def test_controller_normalizes_persisted_party_roster() -> None:
    from types import SimpleNamespace

    from src.core.modules.module_editor_controller import ModuleEditorController

    shim = SimpleNamespace(
        project=SimpleNamespace(
            extra_sections={
                "map_studio_pie_context": {
                    "player_role": "normal_pc",
                    "party_roster": ["Atton", "atton", "Kreia", "Bao-Dur"],
                }
            }
        )
    )
    settings = ModuleEditorController.map_studio_pie_context_settings.__get__(shim)()
    # De-duplicated, lowercased, capped at two companions.
    assert settings["party_roster"] == ("atton", "kreia")

    empty = SimpleNamespace(project=SimpleNamespace(extra_sections={}))
    assert ModuleEditorController.map_studio_pie_context_settings.__get__(empty)()["party_roster"] == ()


def test_party_actor_plan_is_resilient_to_resolver_errors() -> None:
    from src.core.modules.map_studio_pie_party import build_map_studio_pie_party_plan

    def boom(_resref):
        raise RuntimeError("resolver exploded")

    plan = build_map_studio_pie_party_plan(["atton"], model_resolver=boom)
    assert len(plan) == 1 and plan[0].can_build_actor is False


def test_walkmesh_sampler_snaps_each_slot() -> None:
    from src.core.modules.map_studio_pie_party import party_follow_positions

    def sampler(point):
        return (point[0], point[1], 7.5)  # snap every slot onto z=7.5

    positions = party_follow_positions((0.0, 0.0, 0.0), 0.0, 2, walkmesh_sampler=sampler)
    assert all(p[2] == pytest.approx(7.5) for p in positions)

    # A sampler that rejects a slot leaves the raw position.
    positions_raw = party_follow_positions((0.0, 0.0, 3.0), 0.0, 1, walkmesh_sampler=lambda _p: None)
    assert positions_raw[0][2] == pytest.approx(3.0)
