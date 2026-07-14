from __future__ import annotations

import json
from pathlib import Path

from src.core.scripting.quest import (
    QUEST_DOCUMENT_FORMAT,
    QuestDefinition,
    QuestScaffoldService,
)


def _legacy_quest_payload() -> dict[str, object]:
    return {
        "quest_id": "legacy_relic",
        "quest_name": "Legacy Relic",
        "description": "Recovered from GhostScripter",
        "target_game": "K2",
        "quest_type": "BRANCHING",
        "priority": 4,
        "repeatable": True,
        "conflicts_with": ["dark_relic"],
        "dependencies": ["intro_done"],
        "legacy_plugin": {"author": "café", "revision": 7},
        "variables": [
            {
                "variable_name": "LV_RELIC_STATE",
                "variable_type": "Number",
                "default_value": 0,
                "description": "Progress",
                "legacy_ui_order": 3,
            }
        ],
        "states": [
            {
                "id": 0,
                "state_name": "Not Started",
                "description": "Waiting",
                "entry_dialogue": "relic_intro",
                "entry_script": "relic_start",
                "spawned_npcs": ["relic_guide"],
                "spawned_placeables": ["relic_chest"],
                "available_objectives": ["Find the relic"],
                "legacy_camera": {"x": 1.25},
            },
            {"id": 1, "state_name": "Complete", "description": "Done", "end": True},
        ],
        "triggers": [
            {
                "type": "dialogue_complete",
                "condition": "GetIsObjectValid(oRelic)",
                "state": 1,
                "script": "relic_finish",
                "legacy_delay": 0.25,
            }
        ],
        "dialogues": ["relic_intro"],
        "scripts": ["relic_start", "relic_finish"],
    }


def test_legacy_quest_json_round_trips_without_losing_unknown_fields(tmp_path: Path) -> None:
    source = tmp_path / "legacy.quest.json"
    source.write_text(json.dumps(_legacy_quest_payload(), ensure_ascii=False), encoding="utf-8")

    quest = QuestDefinition.load(source)
    assert quest.quest_id == "legacy_relic"
    assert quest.name == "Legacy Relic"
    assert quest.variables[0].name == "LV_RELIC_STATE"
    assert quest.variables[0].default == 0
    assert quest.states[0].name == "Not Started"
    assert quest.states[0].objectives == ("Find the relic",)
    assert quest.states[0].spawned_npcs == ("relic_guide",)
    assert quest.triggers[0].target_state == 1
    quest.name = "Edited Legacy Relic"
    quest.states[0].description = "Edited safely"

    saved = quest.save(tmp_path / "edited.quest.json")
    first_bytes = saved.read_bytes()
    encoded = json.loads(first_bytes)
    assert "quest_name" not in encoded
    assert "state_name" not in encoded["states"][0]
    assert "available_objectives" not in encoded["states"][0]
    assert encoded["states"][0]["name"] == "Not Started"
    assert encoded["states"][0]["objectives"] == ["Find the relic"]
    reloaded = QuestDefinition.load(saved)
    assert reloaded.name == "Edited Legacy Relic"
    assert reloaded.extras["legacy_plugin"] == {"author": "café", "revision": 7}
    assert reloaded.variables[0].extras["legacy_ui_order"] == 3
    assert reloaded.states[0].extras["legacy_camera"] == {"x": 1.25}
    assert reloaded.triggers[0].extras["legacy_delay"] == 0.25
    assert reloaded.to_dict()["format"] == QUEST_DOCUMENT_FORMAT

    reloaded.save(saved)
    assert saved.read_bytes() == first_bytes


def test_preserved_templates_keep_legacy_state_and_global_semantics() -> None:
    simple = QuestScaffoldService.definition(
        quest_tag="relic", display_name="Relic", prefix="lv", template="simple"
    )
    branching = QuestScaffoldService.definition(
        quest_tag="relic", display_name="Relic", prefix="lv", template="branching"
    )
    companion = QuestScaffoldService.definition(
        quest_tag="relic", display_name="Relic", prefix="lv", template="companion"
    )

    assert [row.state_id for row in simple.states] == [0, 1, 2]
    assert [row.state_id for row in branching.states] == [0, 1, 2, 3, 4]
    assert [row.state_id for row in companion.states] == [0, 1, 2, 3]
    assert [row.name for row in branching.variables] == [
        "LV_RELIC",
        "LV_RELIC_STATE",
        "LV_RELIC_CHOICE",
    ]
    assert [row.name for row in companion.variables] == [
        "LV_RELIC_RECRUITED",
        "LV_RELIC_QUEST",
    ]
    assert not simple.validate()


def test_validation_catches_broken_relations_typed_defaults_and_trigger_targets() -> None:
    quest = QuestDefinition.from_dict(
        {
            "quest_id": "bad",
            "name": "Bad",
            "variables": [{"name": "FLAG", "type": "Boolean", "default": "maybe"}],
            "states": [{"id": 0, "name": "Only"}],
            "triggers": [{"type": "manual", "target_state": 99}],
            "dependencies": ["bad"],
        }
    )
    codes = {row.code for row in quest.validate()}
    assert {"quest.variable_default", "quest.trigger_state", "quest.self_relation"}.issubset(codes)
