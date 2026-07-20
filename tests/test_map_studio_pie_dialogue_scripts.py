"""Focused contracts for executing a dialogue node's literal action-script writes.

In KOTOR a DLG entry/reply carries a Script that fires when the line plays; the
common quest-advance pattern is a `SetGlobalNumber`/`SetGlobalBoolean` (or
`AddJournalQuestEntry`). With a compiled-NCS loader, PIE executes those bounded
literal writes into the shared condition state so a later branch reads them.
Anything the bounded reader cannot resolve stays honestly deferred. Editor-side
preview state only — never campaign state.
"""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO


def _compiled_setglobals() -> bytes:
    """A node action script: SetGlobalNumber('czerka_state',5); SetGlobalBoolean('met_npc',1)."""

    from pykotor.resource.formats.ncs import (
        NCS,
        NCSInstruction,
        NCSInstructionType as T,
        bytes_ncs,
    )

    ncs = NCS()
    ncs.instructions.append(NCSInstruction(T.CONSTS, ["czerka_state"]))
    ncs.instructions.append(NCSInstruction(T.CONSTI, [5]))
    ncs.instructions.append(NCSInstruction(T.ACTION, [581, 2]))   # SetGlobalNumber
    ncs.instructions.append(NCSInstruction(T.CONSTS, ["met_npc"]))
    ncs.instructions.append(NCSInstruction(T.CONSTI, [1]))
    ncs.instructions.append(NCSInstruction(T.ACTION, [579, 2]))   # SetGlobalBoolean
    ncs.instructions.append(NCSInstruction(T.RETN))
    return bytes_ncs(ncs)


def _dialogue_with_entry_script(script_resref: str) -> bytes:
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import Game
    from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink, bytes_dlg

    dialogue = DLG()
    entry = DLGEntry()
    entry.list_index = 0
    entry.text = LocalizedString.from_english("You're back. Czerka has business with you.")
    entry.script1 = script_resref
    dialogue.starters.append(DLGLink(entry))
    with redirect_stdout(StringIO()):
        return bytes_dlg(dialogue, Game.K2)


def test_evaluator_setters_mutate_state_casefolded() -> None:
    from src.core.modules.map_studio_pie_dialogue import MapStudioPIEDialogueContextEvaluator

    evaluator = MapStudioPIEDialogueContextEvaluator()
    assert evaluator.set_global_number("Czerka_State", 5) is True
    assert evaluator.set_global_number("czerka_state", 5) is False  # unchanged
    assert evaluator.set_global_boolean("MET_NPC", True) is True
    # Keys are casefolded to match evaluate()'s lookup.
    assert evaluator._global_numbers["czerka_state"] == 5
    assert evaluator._global_booleans["met_npc"] is True


def test_node_script_executes_literal_global_writes() -> None:
    from src.core.modules.map_studio_pie_dialogue import (
        MapStudioPIEDialogueContextEvaluator,
        MapStudioPIEDialogueSession,
    )

    evaluator = MapStudioPIEDialogueContextEvaluator()
    ncs = _compiled_setglobals()
    session = MapStudioPIEDialogueSession(
        _dialogue_with_entry_script("a_czerka_set"),
        game="K2",
        resref="207falt",
        condition_evaluator=evaluator,
        script_loader=lambda resref: ncs if resref == "a_czerka_set" else None,
        allow_unknown_starter_assumption=True,
    )
    snapshot = session.start()

    # The entry's action script advanced the shared condition state.
    assert evaluator._global_numbers["czerka_state"] == 5
    assert evaluator._global_booleans["met_npc"] is True
    executed = [e for e in snapshot.events if e.kind == "node_script_executed"]
    assert len(executed) == 1
    assert "czerka_state=5" in executed[0].message
    assert "a_czerka_set" in executed[0].resrefs
    # A real execution must not also report the same script as deferred.
    assert not any(
        e.kind == "node_scripts_deferred" and "a_czerka_set" in e.resrefs for e in snapshot.events
    )


def test_node_script_executes_global_string_write() -> None:
    from pykotor.resource.formats.ncs import (
        NCS,
        NCSInstruction,
        NCSInstructionType as T,
        bytes_ncs,
    )

    from src.core.modules.map_studio_pie_dialogue import (
        MapStudioPIEDialogueContextEvaluator,
        MapStudioPIEDialogueSession,
    )

    # A node action script: SetGlobalString("207_PlayerName", "Exile").
    ncs = NCS()
    ncs.instructions.append(NCSInstruction(T.CONSTS, ["207_PlayerName"]))
    ncs.instructions.append(NCSInstruction(T.CONSTS, ["Exile"]))
    ncs.instructions.append(NCSInstruction(T.ACTION, [160, 2]))  # SetGlobalString
    ncs.instructions.append(NCSInstruction(T.RETN))
    script_bytes = bytes_ncs(ncs)

    evaluator = MapStudioPIEDialogueContextEvaluator()
    session = MapStudioPIEDialogueSession(
        _dialogue_with_entry_script("a_name_set"),
        game="K2",
        resref="207falt",
        condition_evaluator=evaluator,
        script_loader=lambda resref: script_bytes if resref == "a_name_set" else None,
        allow_unknown_starter_assumption=True,
    )
    snapshot = session.start()

    _numbers, _booleans, strings = evaluator.global_state()
    assert strings["207_playername"] == "Exile"  # casefolded key, script-set value
    executed = [e for e in snapshot.events if e.kind == "node_script_executed"]
    assert len(executed) == 1
    assert "207_PlayerName" in executed[0].message


def test_node_script_without_loader_stays_deferred() -> None:
    from src.core.modules.map_studio_pie_dialogue import (
        MapStudioPIEDialogueContextEvaluator,
        MapStudioPIEDialogueSession,
    )

    evaluator = MapStudioPIEDialogueContextEvaluator()
    session = MapStudioPIEDialogueSession(
        _dialogue_with_entry_script("a_czerka_set"),
        game="K2",
        resref="207falt",
        condition_evaluator=evaluator,
        allow_unknown_starter_assumption=True,
    )
    snapshot = session.start()

    assert not evaluator._global_numbers  # nothing executed
    deferred = [e for e in snapshot.events if e.kind == "node_scripts_deferred"]
    assert len(deferred) == 1
    assert "a_czerka_set" in deferred[0].resrefs
    assert not any(e.kind == "node_script_executed" for e in snapshot.events)
