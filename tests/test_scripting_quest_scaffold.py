from __future__ import annotations

from src.core.scripting.quest import QuestScaffoldService
from src.core.scripting.studio import ScriptingStudioService


def test_all_preserved_quest_templates_generate_journal_globals_and_scripts() -> None:
    compiler = ScriptingStudioService()
    expected = {
        "simple": (3, 2, (0, 1, 2)),
        "branching": (5, 3, (0, 1, 2, 3, 4)),
        "companion": (4, 2, (0, 1, 2, 3)),
    }
    for key, _label in QuestScaffoldService.template_names():
        result = QuestScaffoldService.scaffold(
            quest_tag="relic_hunt",
            display_name="The Lost Relic",
            prefix="lv",
            template=key,
        )
        state_count, global_count, state_ids = expected[key]
        assert len(result.journal_quest.entries) == state_count
        assert tuple(row.entry_id for row in result.journal_quest.entries) == state_ids
        assert {row.value_type for row in result.globals} == {"Boolean", "Number"}
        assert len(result.globals) == global_count
        assert len(result.scripts) == state_count
        assert len({row.resref for row in result.scripts}) == state_count
        assert all(len(row.resref) <= 16 for row in result.scripts)
        for script in result.scripts:
            document = compiler.script_from_bytes(
                script.source.encode("utf-8"), game="K1", resref=script.resref, origin="quest_scaffold"
            )
            assert compiler.compile_script(document).ok


def test_long_quest_names_get_stable_legal_script_resrefs() -> None:
    first = QuestScaffoldService.scaffold(
        quest_tag="companion_personal_quest_long",
        display_name="Companion Story",
        prefix="lordvadercw",
        template="companion",
    )
    second = QuestScaffoldService.scaffold(
        quest_tag="companion_personal_quest_long",
        display_name="Companion Story",
        prefix="lordvadercw",
        template="companion",
    )

    assert [row.resref for row in first.scripts] == [row.resref for row in second.scripts]
    assert all(len(row.resref) <= 16 for row in first.scripts)
