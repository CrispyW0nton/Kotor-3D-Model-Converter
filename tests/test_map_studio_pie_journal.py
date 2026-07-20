"""Focused contracts for PIE journal/quest reporting from dialogue nodes.

KOTOR DLG entry nodes carry Quest (a plot tag) and QuestEntry (its state index);
the retail engine calls AddJournalQuestEntry when the line plays. PIE cannot
mutate campaign quest state, so it reports the update as an event and exposes the
quest tag/entry on the snapshot. Editor-side reporting only.
"""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace


def _dialogue_with_quest(*, quest: str, quest_entry: int) -> bytes:
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import Game
    from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink, bytes_dlg

    dialogue = DLG()
    entry = DLGEntry()
    entry.list_index = 0
    entry.text = LocalizedString.from_english("The plot advances.")
    entry.quest = quest
    entry.quest_entry = quest_entry
    dialogue.starters.append(DLGLink(entry))
    with redirect_stdout(StringIO()):
        return bytes_dlg(dialogue, Game.K2)


def _dialogue_without_quest() -> bytes:
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import Game
    from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink, bytes_dlg

    dialogue = DLG()
    entry = DLGEntry()
    entry.list_index = 0
    entry.text = LocalizedString.from_english("Just chatting.")
    dialogue.starters.append(DLGLink(entry))
    with redirect_stdout(StringIO()):
        return bytes_dlg(dialogue, Game.K2)


def test_snapshot_exposes_quest_tag_and_entry_and_emits_journal_event() -> None:
    from src.core.modules.map_studio_pie_dialogue import MapStudioPIEDialogueSession

    session = MapStudioPIEDialogueSession(
        _dialogue_with_quest(quest="czerkamain", quest_entry=20),
        game="K2",
        resref="207falt",
    )
    snapshot = session.start()

    assert snapshot.quest_tag == "czerkamain"
    assert snapshot.quest_entry == 20
    journal = [event for event in snapshot.events if event.kind == "journal_updated"]
    assert len(journal) == 1
    assert journal[0].value == "czerkamain:20"
    assert "czerkamain" in journal[0].message


def test_node_without_quest_reports_no_journal_update() -> None:
    from src.core.modules.map_studio_pie_dialogue import MapStudioPIEDialogueSession

    snapshot = MapStudioPIEDialogueSession(_dialogue_without_quest(), game="K2", resref="chat").start()
    assert snapshot.quest_tag == ""
    assert snapshot.quest_entry == 0
    assert not any(event.kind == "journal_updated" for event in snapshot.events)


def test_extract_dialogue_quest_references_lists_distinct_touchpoints() -> None:
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import Game
    from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink, bytes_dlg

    from src.core.modules.map_studio_pie_dialogue import extract_dialogue_quest_references

    dialogue = DLG()
    for index, (quest, entry_no) in enumerate([("czerkamain", 20), ("falt", 10), ("czerkamain", 20), ("", 0)]):
        entry = DLGEntry()
        entry.list_index = index
        entry.text = LocalizedString.from_english(f"line {index}")
        if quest:
            entry.quest = quest
            entry.quest_entry = entry_no
        dialogue.starters.append(DLGLink(entry))
    with redirect_stdout(StringIO()):
        payload = bytes_dlg(dialogue, Game.K2)

    refs = extract_dialogue_quest_references(payload)
    assert ("czerkamain", 20) in refs
    assert ("falt", 10) in refs
    assert refs.count(("czerkamain", 20)) == 1  # distinct
    assert all(quest for quest, _ in refs)  # no blank-quest entries
    assert extract_dialogue_quest_references(b"") == ()


def test_journal_state_is_monotonic_and_seedable() -> None:
    from src.core.modules.map_studio_pie_journal import MapStudioPIEJournalState

    # Seed accepts (tag, entry) pairs and "tag:entry" strings.
    state = MapStudioPIEJournalState(seed=[("czerkamain", 10), "faltquest:5"])
    assert state.as_dict() == {"czerkamain": 10, "faltquest": 5}

    assert state.record("czerkamain", 20) is True   # advances
    assert state.record("czerkamain", 15) is False   # lower entry ignored
    assert state.record("czerkamain", 20) is False   # equal entry ignored
    assert state.record_value("newquest:1") is True
    assert state.record_value("garbage") is False     # no ":" -> ignored

    entries = state.entries()
    assert [(q.quest_tag, q.entry) for q in entries] == [
        ("czerkamain", 20),
        ("faltquest", 5),
        ("newquest", 1),
    ]  # sorted by tag, highest entry per plot


def test_gameplay_runtime_accumulates_journal_into_snapshot() -> None:
    from src.core.modules.map_studio_pie_entities import PIEEntity, PIEEntityRegistry
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    player = PIEEntity(
        entity_id="pie:player", kind="player", tag="player", display_name="Player",
        template_resref="", position=(0.0, 0.0, 0.0), faction="player",
        focusable=False, interactive=False,
    )
    npc = PIEEntity(
        entity_id="authored:creature:falt", kind="creature", tag="Falt", display_name="Corrun Falt",
        template_resref="", position=(1.0, 0.0, 0.0), faction="friendly",
        focusable=True, interactive=True, interaction="dialogue", actions=("talk",),
        conversation="207falt",
    )
    registry = PIEEntityRegistry((player, npc))
    payload = _dialogue_with_quest(quest="faltquest", quest_entry=10)
    runtime = MapStudioPIEGameplayRuntime(
        registry,
        game="K2",
        dialogue_loader=lambda resref: payload if resref == "207falt" else None,
        journal_seed=[("czerkamain", 5)],  # OnEnter AddJournalQuestEntry seed
    )
    runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))

    # Seeded quest is present before any dialogue.
    assert {q.quest_tag: q.entry for q in runtime.snapshot().journal} == {"czerkamain": 5}
    assert {q.quest_tag: q.entry for q in runtime.journal_entries()} == {"czerkamain": 5}

    runtime.activate_entity("authored:creature:falt", "talk")
    journal = {q.quest_tag: q.entry for q in runtime.snapshot().journal}
    assert journal == {"czerkamain": 5, "faltquest": 10}  # dialogue advanced the log


def test_gameplay_runtime_surfaces_journal_updated_event() -> None:
    from src.core.modules.map_studio_pie_entities import PIEEntity, PIEEntityRegistry
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    player = PIEEntity(
        entity_id="pie:player", kind="player", tag="player", display_name="Player",
        template_resref="", position=(0.0, 0.0, 0.0), faction="player",
        focusable=False, interactive=False,
    )
    npc = PIEEntity(
        entity_id="authored:creature:falt", kind="creature", tag="Falt", display_name="Corrun Falt",
        template_resref="", position=(1.0, 0.0, 0.0), faction="friendly",
        focusable=True, interactive=True, interaction="dialogue", actions=("talk",),
        conversation="207falt",
    )
    registry = PIEEntityRegistry((player, npc))
    payload = _dialogue_with_quest(quest="falt", quest_entry=10)
    runtime = MapStudioPIEGameplayRuntime(
        registry, game="K2", dialogue_loader=lambda resref: payload if resref == "207falt" else None
    )
    runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
    runtime.drain_events()

    result = runtime.activate_entity("authored:creature:falt", "talk")
    assert result.executed
    journal = [event for event in runtime.drain_events() if event.kind == "journal_updated"]
    assert len(journal) == 1
    assert journal[0].value == "falt:10"
    assert journal[0].entity_id == "authored:creature:falt"
