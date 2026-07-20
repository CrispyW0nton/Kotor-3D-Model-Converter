"""Focused contracts for the bounded NCS global-state effect reader.

PIE runs no general NWScript VM, but module OnEnter scripts commonly set globals
with literal arguments — ``SetGlobalNumber("207TEL_B-4D4_PC", 1)`` — which
compile to CONST pushes followed by the routine ACTION. This slice recovers those
literal writes so PIE can *execute* them into its global sandbox (which dialogue
Active conditions already read) rather than only reporting them. Non-literal or
branching writes are intentionally skipped, not guessed. Editor-side only.
"""

from __future__ import annotations

from types import SimpleNamespace


def _ins(name, *args):
    """A minimal stand-in for a PyKotor NCS instruction row."""

    return SimpleNamespace(ins_type=SimpleNamespace(name=name), args=list(args))


def _compiled_ncs(rows):
    """Serialize literal (routine, name, value) writes into real NCS bytecode."""

    from pykotor.resource.formats.ncs import (
        NCS,
        NCSInstruction,
        NCSInstructionType as T,
        bytes_ncs,
    )

    ncs = NCS()
    for routine, name, value in rows:
        ncs.instructions.append(NCSInstruction(T.CONSTS, [name]))
        ncs.instructions.append(NCSInstruction(T.CONSTI, [value]))
        ncs.instructions.append(NCSInstruction(T.ACTION, [routine, 2]))
    ncs.instructions.append(NCSInstruction(T.RETN))
    return bytes_ncs(ncs)


def test_extracts_literal_globals_from_real_ncs_bytecode() -> None:
    from src.core.modules.map_studio_pie_scripting import extract_ncs_global_effects

    data = _compiled_ncs(
        [
            (581, "207TEL_B-4D4_PC", 1),   # SetGlobalNumber
            (579, "207_MET_B4", 1),        # SetGlobalBoolean
            (367, "czerkamain", 20),       # AddJournalQuestEntry
        ]
    )
    effects = extract_ncs_global_effects(data)

    kinds = {(e.kind, e.name, e.value) for e in effects}
    assert ("global_number", "207TEL_B-4D4_PC", 1) in kinds
    assert ("global_boolean", "207_MET_B4", 1) in kinds
    assert ("journal", "czerkamain", 20) in kinds
    assert len(effects) == 3


def test_extracts_literal_global_string_two_string_args() -> None:
    from pykotor.resource.formats.ncs import (
        NCS,
        NCSInstruction,
        NCSInstructionType as T,
        bytes_ncs,
    )

    from src.core.modules.map_studio_pie_scripting import extract_ncs_global_effects

    # SetGlobalString(sName, sValue) compiles to two CONSTS then ACTION 160.
    ncs = NCS()
    ncs.instructions.append(NCSInstruction(T.CONSTS, ["207_LastName"]))
    ncs.instructions.append(NCSInstruction(T.CONSTS, ["Onasi"]))
    ncs.instructions.append(NCSInstruction(T.ACTION, [160, 2]))
    ncs.instructions.append(NCSInstruction(T.RETN))

    effects = extract_ncs_global_effects(bytes_ncs(ncs))
    assert [(e.kind, e.name, e.value) for e in effects] == [
        ("global_string", "207_LastName", "Onasi"),
    ]


def test_ignores_unrelated_routines_and_empty_input() -> None:
    from src.core.modules.map_studio_pie_scripting import (
        extract_ncs_global_effects,
        extract_ncs_global_effects_from_instructions,
    )

    # GetGlobalNumber (580) reads state; it is not a write and must be skipped.
    rows = [
        _ins("CONSTS", "some_var"),
        _ins("ACTION", 580, 1),
        _ins("CONSTS", "other_var"),
        _ins("CONSTI", 3),
        _ins("ACTION", 581, 2),
    ]
    effects = extract_ncs_global_effects_from_instructions(rows)
    assert [(e.kind, e.name, e.value) for e in effects] == [("global_number", "other_var", 3)]
    assert extract_ncs_global_effects(b"") == ()
    assert extract_ncs_global_effects(b"not-an-ncs") == ()


def test_skips_writes_without_adjacent_literal_arguments() -> None:
    from src.core.modules.map_studio_pie_scripting import (
        extract_ncs_global_effects_from_instructions,
    )

    # A computed value (no CONSTI before the ACTION) must not be guessed.
    rows = [
        _ins("CONSTS", "computed_var"),
        _ins("RSADDI"),        # a non-const push standing in for a computed int
        _ins("ACTION", 581, 2),
    ]
    assert extract_ncs_global_effects_from_instructions(rows) == ()


def test_apply_folds_writes_and_last_write_wins() -> None:
    from src.core.modules.map_studio_pie_scripting import (
        NCSGlobalEffect,
        apply_ncs_global_effects,
    )

    effects = (
        NCSGlobalEffect("global_number", "count", 1),
        NCSGlobalEffect("global_number", "count", 5),   # later write wins
        NCSGlobalEffect("global_boolean", "met", 1),
        NCSGlobalEffect("global_string", "name", "Atton"),
        NCSGlobalEffect("journal", "czerkamain", 20),
    )
    numbers, booleans, strings, journal = apply_ncs_global_effects(
        effects, global_numbers={"count": 0, "seed": 9}, global_booleans={}
    )

    assert numbers == {"count": 5, "seed": 9}
    assert booleans == {"met": True}
    assert strings == {"name": "Atton"}
    assert [(j.name, j.value) for j in journal] == [("czerkamain", 20)]


def test_extracts_area_music_day_and_night_tracks() -> None:
    from src.core.modules.map_studio_pie_scripting import (
        extract_ncs_area_music_from_instructions,
    )

    # MusicBackgroundChangeDay(oArea, nTrack, nStreamingMusic): args push
    # right-to-left, so nTrack is the CONSTI nearest the ACTION (after the
    # streaming bool, before the object push).
    rows = [
        _ins("CONSTI", 0), _ins("CONSTI", 18), _ins("CPTOPSP", -4, 4), _ins("ACTION", 428, 3),
        _ins("CONSTI", 0), _ins("CONSTI", 5), _ins("CPTOPSP", -4, 4), _ins("ACTION", 429, 3),
        _ins("CONSTI", 12), _ins("CPTOPSP", -4, 4), _ins("ACTION", 432, 2),   # MusicBattleChange
    ]
    music = extract_ncs_area_music_from_instructions(rows)
    assert music.day_track == 18
    assert music.night_track == 5
    assert music.battle_track == 12


def test_area_music_later_call_wins_and_absent_track_is_none() -> None:
    from src.core.modules.map_studio_pie_scripting import (
        extract_ncs_area_music_from_instructions,
    )

    rows = [
        _ins("CONSTI", 16), _ins("CPTOPSP", -4, 4), _ins("ACTION", 428, 3),   # ChangeDay 16
        _ins("CONSTI", 18), _ins("CPTOPSP", -4, 4), _ins("ACTION", 428, 3),   # ChangeDay 18 (wins)
    ]
    music = extract_ncs_area_music_from_instructions(rows)
    assert music.day_track == 18       # sequential: later call wins
    assert music.night_track is None    # no ChangeNight call


def _compiled_setlocalbool(tag: str, index: int, value: int, *, literal_object: bool = True):
    from pykotor.resource.formats.ncs import (
        NCS,
        NCSInstruction,
        NCSInstructionType as T,
        bytes_ncs,
    )

    ncs = NCS()
    ncs.instructions.append(NCSInstruction(T.CONSTI, [value]))   # nValue
    ncs.instructions.append(NCSInstruction(T.CONSTI, [index]))   # nIndex
    if literal_object:
        ncs.instructions.append(NCSInstruction(T.CONSTS, [tag]))     # sTag
        ncs.instructions.append(NCSInstruction(T.CONSTI, [0]))       # nNth
        ncs.instructions.append(NCSInstruction(T.ACTION, [200, 2]))  # GetObjectByTag
    else:
        ncs.instructions.append(NCSInstruction(T.CPTOPSP, [-16, 4]))  # computed object
    ncs.instructions.append(NCSInstruction(T.ACTION, [680, 3]))   # SetLocalBoolean
    ncs.instructions.append(NCSInstruction(T.RETN))
    return bytes_ncs(ncs)


def test_extracts_literal_object_local_boolean_write() -> None:
    from src.core.modules.map_studio_pie_scripting import extract_ncs_local_effects

    effects = extract_ncs_local_effects(_compiled_setlocalbool("czerka_npc", 5, 1))
    assert [(e.owner_tag, e.index, e.value) for e in effects] == [("czerka_npc", 5, True)]

    # A computed (non-literal) object is skipped, not guessed.
    assert extract_ncs_local_effects(_compiled_setlocalbool("x", 3, 1, literal_object=False)) == ()


def test_executing_a_script_folds_local_boolean_into_the_evaluator() -> None:
    from src.core.modules.map_studio_pie_dialogue import MapStudioPIEDialogueContextEvaluator
    from src.core.modules.map_studio_pie_scripting import execute_ncs_global_effects

    evaluator = MapStudioPIEDialogueContextEvaluator()
    labels = execute_ncs_global_effects(_compiled_setlocalbool("czerka_npc", 5, 1), evaluator=evaluator)

    # Keyed by (owner_tag casefolded, index) — the same key a local condition reads.
    assert evaluator._local_booleans[("czerka_npc", 5)] is True
    assert any("czerka_npc[5]=True" in label for label in labels)
    # set_local_boolean is idempotent on repeat and casefolds the owner.
    assert evaluator.set_global_number  # (evaluator still supports globals too)
    assert evaluator.set_local_boolean("CZERKA_NPC", 5, True) is False  # unchanged


def test_routine_numbers_match_pykotor_engine_function_table() -> None:
    """Pin the ACTION routine ids to the engine's own function-declaration order.

    Guards the exact regression this slice hit once: a hand-counted routine
    number (577) that did not match the compiled bytecode. K1 and K2 agree on
    these ids, so both engine tables must resolve to the same index.
    """

    from pykotor.common.scriptdefs import KOTOR_FUNCTIONS, TSL_FUNCTIONS

    import src.core.modules.map_studio_pie_scripting as scripting

    for table in (KOTOR_FUNCTIONS, TSL_FUNCTIONS):
        names = [getattr(entry, "name", "") for entry in table]
        assert names.index("SetGlobalNumber") == scripting._ROUTINE_SET_GLOBAL_NUMBER
        assert names.index("SetGlobalBoolean") == scripting._ROUTINE_SET_GLOBAL_BOOLEAN
        assert names.index("AddJournalQuestEntry") == scripting._ROUTINE_ADD_JOURNAL_QUEST_ENTRY


def test_extracted_globals_satisfy_a_dialogue_active_condition() -> None:
    """The loop closes: an OnEnter global write flips a dialogue condition."""

    from src.core.modules.map_studio_pie_scripting import (
        apply_ncs_global_effects,
        extract_ncs_global_effects,
    )

    data = _compiled_ncs([(581, "203TEL_B-4D4_PC", 1)])
    numbers, _booleans, _strings, _journal = apply_ncs_global_effects(
        extract_ncs_global_effects(data), global_numbers={}, global_booleans={}
    )
    # A c_b4d4pc-style Active condition checks this global == 1.
    assert numbers.get("203TEL_B-4D4_PC") == 1
