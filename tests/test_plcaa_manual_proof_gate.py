"""Focused contracts for the custom PLCaa manual acceptance gate."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def test_plcaa_requires_the_complete_user_driven_editor_to_game_proof() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_export import _authored_acceptance_checks

    generic = _authored_acceptance_checks(module_root="grterrain")
    plcaa = _authored_acceptance_checks(module_root="PLCaa")

    assert plcaa[: len(generic)] == generic
    assert plcaa[len(generic) :] == [
        "texture_paint_visible_in_game",
        "terrain_sculpt_and_generated_walkmesh_work_in_game",
        "placed_assets_match_editor_staging",
        "enemy_spawns_hostile",
        "npc_spawns_and_free_roams",
        "terminal_operates",
        "container_opens_with_inventory",
        "puzzle_sequence_unlocks_door",
        "animated_door_operates",
        "configured_transition_operates",
        "player_start_position_and_facing_match",
    ]


def test_plcaa_interaction_checks_are_false_until_the_user_records_them() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_export import (
        AuthoredModuleGameProofRequest,
        _proof_request_checks,
    )

    request = AuthoredModuleGameProofRequest(
        proof_manifest_path="candidate.json",
        evidence_path="",
        module_loads_in_game=True,
    )
    checks = _proof_request_checks(request)

    assert checks["module_loads_in_game"] is True
    for key in (
        "texture_paint_visible_in_game",
        "terrain_sculpt_and_generated_walkmesh_work_in_game",
        "placed_assets_match_editor_staging",
        "enemy_spawns_hostile",
        "npc_spawns_and_free_roams",
        "terminal_operates",
        "container_opens_with_inventory",
        "puzzle_sequence_unlocks_door",
        "animated_door_operates",
        "configured_transition_operates",
        "player_start_position_and_facing_match",
    ):
        assert checks[key] is False
