"""Bounded NCS global-state effect extraction for Play-in-Editor.

A full NWScript VM is out of scope, but the most common scripting-state effects
in module OnEnter/OnUsed scripts are literal global-variable and journal writes:
``SetGlobalNumber("207TEL_B-4D4_PC", 1)``, ``SetGlobalBoolean(...)``,
``AddJournalQuestEntry("quest", 10)``. Those compile to a fixed shape — a couple
of CONST pushes followed by the routine ACTION — which is recoverable without a
stack machine (the same technique the scene-animation reader already uses).

This module extracts those literal effects so PIE can *execute* them into its
global/local sandbox (which dialogue Active conditions already read) instead of
only reporting them. It is deliberately conservative: an effect whose arguments
are not adjacent literals is skipped rather than guessed. Non-literal/branching
scripts remain outside this bounded reader — tracked, not faked.
"""

from __future__ import annotations

from dataclasses import dataclass
import io
from typing import Any

# KOTOR nwscript ACTION routine numbers, taken from PyKotor's authoritative
# engine function table (``KOTOR_FUNCTIONS``/``TSL_FUNCTIONS`` — K1 and K2 agree
# on these). Verified against real 207TEL ``k_207tel_enter`` bytecode, which
# issues SetGlobalNumber (581) 13x and SetGlobalBoolean (579) 2x.
_ROUTINE_SET_GLOBAL_STRING = 160
_ROUTINE_ADD_JOURNAL_QUEST_ENTRY = 367
_ROUTINE_SET_GLOBAL_BOOLEAN = 579
_ROUTINE_SET_GLOBAL_NUMBER = 581
# KOTOR area ambient music is script-driven (not a static ARE field): the area
# OnEnter calls MusicBackgroundChangeDay(oArea, nTrack)/…Night with a literal
# ambientmusic.2da row. Args push right-to-left, so nTrack is the CONSTI nearest
# the ACTION. Verified against real 207TEL k_207tel_enter (day 18, night 18).
_ROUTINE_MUSIC_BACKGROUND_CHANGE_DAY = 428
_ROUTINE_MUSIC_BACKGROUND_CHANGE_NIGHT = 429
_ROUTINE_MUSIC_BATTLE_CHANGE = 432  # MusicBattleChange(oArea, nTrack)
# Local-variable writes on a literal-tag object: SetLocalBoolean(GetObjectByTag(
# "tag"), nIndex, nValue). Only the literal GetObjectByTag object is handled (no
# stack dataflow), matching the "skip rather than guess" contract.
_ROUTINE_SET_LOCAL_BOOLEAN = 680
_ROUTINE_GET_OBJECT_BY_TAG = 200


@dataclass(frozen=True)
class NCSGlobalEffect:
    """One literal global-state write recovered from a compiled NCS script."""

    kind: str  # "global_number" | "global_boolean" | "global_string" | "journal"
    name: str
    value: int | str


def _instruction_type_name(instruction: Any) -> str:
    ins_type = getattr(instruction, "ins_type", None)
    return str(getattr(ins_type, "name", "") or "")


def _action_routine(instruction: Any) -> int | None:
    if _instruction_type_name(instruction) != "ACTION":
        return None
    args = tuple(getattr(instruction, "args", ()) or ())
    return int(args[0]) if args else None


def _preceding_literals(rows: list[Any], index: int, *, window: int = 8) -> tuple[str | None, int | None]:
    """First literal string and int pushed in the window before ``index``.

    The SetGlobal*/AddJournalQuestEntry calls push a string name then an int
    value immediately before the ACTION, so scanning back for the nearest
    CONSTS/CONSTI recovers the literal arguments. Stops at an earlier ACTION.
    """

    name: str | None = None
    value: int | None = None
    for j in range(index - 1, max(-1, index - window), -1):
        if _action_routine(rows[j]) is not None:
            break
        kind = _instruction_type_name(rows[j])
        args = tuple(getattr(rows[j], "args", ()) or ())
        if not args:
            continue
        if kind == "CONSTS" and name is None:
            name = str(args[0])
        elif kind == "CONSTI" and value is None:
            try:
                value = int(args[0])
            except (TypeError, ValueError):
                value = None
    return name, value


def _preceding_two_strings(rows: list[Any], index: int, *, window: int = 8) -> tuple[str | None, str | None]:
    """Literal ``(name, value)`` for ``SetGlobalString(sName, sValue)``.

    Both arguments are literal strings, so the compiled shape is two CONSTS
    pushes before the ACTION. Args push left-to-right, so the CONSTS nearest the
    ACTION is the value and the one before it is the name. Stops at an earlier
    ACTION; returns ``(None, None)`` when two literals are not present.
    """

    strings: list[str] = []
    for j in range(index - 1, max(-1, index - window), -1):
        if _action_routine(rows[j]) is not None:
            break
        if _instruction_type_name(rows[j]) == "CONSTS":
            args = tuple(getattr(rows[j], "args", ()) or ())
            if args:
                strings.append(str(args[0]))
                if len(strings) == 2:
                    break
    if len(strings) < 2:
        return None, None
    value, name = strings[0], strings[1]
    return name, value


def extract_ncs_global_effects_from_instructions(
    instructions: list[Any] | tuple[Any, ...],
) -> tuple[NCSGlobalEffect, ...]:
    """Recover literal SetGlobalNumber/Boolean and AddJournalQuestEntry writes."""

    rows = list(instructions or ())
    effects: list[NCSGlobalEffect] = []
    for index, instruction in enumerate(rows):
        routine = _action_routine(instruction)
        if routine == _ROUTINE_SET_GLOBAL_STRING:
            name, string_value = _preceding_two_strings(rows, index)
            if name and string_value is not None:
                clean = str(name).strip()
                if clean:
                    effects.append(NCSGlobalEffect("global_string", clean, str(string_value)))
            continue
        if routine not in (
            _ROUTINE_SET_GLOBAL_NUMBER,
            _ROUTINE_SET_GLOBAL_BOOLEAN,
            _ROUTINE_ADD_JOURNAL_QUEST_ENTRY,
        ):
            continue
        name, value = _preceding_literals(rows, index)
        if not name or value is None:
            continue  # non-literal args: skip rather than guess
        clean = str(name).strip()
        if not clean:
            continue
        if routine == _ROUTINE_SET_GLOBAL_NUMBER:
            effects.append(NCSGlobalEffect("global_number", clean, int(value)))
        elif routine == _ROUTINE_SET_GLOBAL_BOOLEAN:
            effects.append(NCSGlobalEffect("global_boolean", clean, 1 if int(value) else 0))
        else:
            effects.append(NCSGlobalEffect("journal", clean, int(value)))
    return tuple(effects)


def extract_ncs_global_effects(ncs_bytes: bytes) -> tuple[NCSGlobalEffect, ...]:
    """Recover literal global/journal writes from a compiled NCS script."""

    if not ncs_bytes:
        return ()
    try:
        from pykotor.resource.formats.ncs import NCSBinaryReader

        ncs = NCSBinaryReader(io.BytesIO(bytes(ncs_bytes))).load()
    except Exception:
        return ()
    return extract_ncs_global_effects_from_instructions(list(getattr(ncs, "instructions", ()) or ()))


@dataclass(frozen=True)
class NCSLocalEffect:
    """One literal local-boolean write on a literal-tag object."""

    owner_tag: str   # the GetObjectByTag literal tag the local is set on
    index: int       # the local variable slot
    value: bool


def extract_ncs_local_effects_from_instructions(
    instructions: list[Any] | tuple[Any, ...],
) -> tuple[NCSLocalEffect, ...]:
    """Recover ``SetLocalBoolean(GetObjectByTag("tag"), index, value)`` writes.

    Only the literal-object shape (the SetLocalBoolean ACTION is immediately
    preceded by a ``GetObjectByTag`` ACTION on a literal CONSTS tag) is handled;
    computed/stack-referenced objects are skipped, not guessed. Compiled shape:
    ``CONSTI value, CONSTI index, CONSTS tag, CONSTI nth, ACTION 200, ACTION 680``.
    """

    rows = list(instructions or ())
    effects: list[NCSLocalEffect] = []
    for index, instruction in enumerate(rows):
        if _action_routine(instruction) != _ROUTINE_SET_LOCAL_BOOLEAN:
            continue
        if index == 0 or _action_routine(rows[index - 1]) != _ROUTINE_GET_OBJECT_BY_TAG:
            continue  # object is not a literal GetObjectByTag — skip

        tag: str | None = None
        tag_pos: int | None = None
        for j in range(index - 2, max(-1, index - 8), -1):
            if _action_routine(rows[j]) is not None:
                break
            if _instruction_type_name(rows[j]) == "CONSTS":
                args = tuple(getattr(rows[j], "args", ()) or ())
                if args:
                    tag = str(args[0])
                    tag_pos = j
                break
        if not tag or tag_pos is None:
            continue

        ints: list[int] = []
        for j in range(tag_pos - 1, max(-1, tag_pos - 8), -1):
            if _action_routine(rows[j]) is not None:
                break
            if _instruction_type_name(rows[j]) == "CONSTI":
                args = tuple(getattr(rows[j], "args", ()) or ())
                if args:
                    try:
                        ints.append(int(args[0]))
                    except (TypeError, ValueError):
                        break
                    if len(ints) == 2:
                        break
        if len(ints) < 2:
            continue
        slot, value = ints[0], ints[1]  # nearest CONSTI is the index, next is the value
        clean = str(tag).strip()
        if clean:
            effects.append(NCSLocalEffect(owner_tag=clean, index=int(slot), value=bool(value)))
    return tuple(effects)


def extract_ncs_local_effects(ncs_bytes: bytes) -> tuple[NCSLocalEffect, ...]:
    """Recover literal-object ``SetLocalBoolean`` writes from a compiled NCS."""

    if not ncs_bytes:
        return ()
    try:
        from pykotor.resource.formats.ncs import NCSBinaryReader

        ncs = NCSBinaryReader(io.BytesIO(bytes(ncs_bytes))).load()
    except Exception:
        return ()
    return extract_ncs_local_effects_from_instructions(list(getattr(ncs, "instructions", ()) or ()))


def apply_ncs_global_effects(
    effects: Any,
    *,
    global_numbers: dict[str, int] | None = None,
    global_booleans: dict[str, bool] | None = None,
    global_strings: dict[str, str] | None = None,
) -> tuple[dict[str, int], dict[str, bool], dict[str, str], tuple[NCSGlobalEffect, ...]]:
    """Fold extracted effects into global maps for PIE conditions.

    Returns the updated number/boolean/string maps plus the journal effects
    (which PIE reports rather than mutating campaign quest state). Later writes
    win, matching sequential script execution.
    """

    numbers = dict(global_numbers or {})
    booleans = dict(global_booleans or {})
    strings = dict(global_strings or {})
    journal: list[NCSGlobalEffect] = []
    for effect in tuple(effects or ()):
        if effect.kind == "global_number":
            numbers[effect.name] = int(effect.value)
        elif effect.kind == "global_boolean":
            booleans[effect.name] = bool(effect.value)
        elif effect.kind == "global_string":
            strings[effect.name] = str(effect.value)
        elif effect.kind == "journal":
            journal.append(effect)
    return numbers, booleans, strings, tuple(journal)


@dataclass(frozen=True)
class NCSAreaMusic:
    """Ambient music ``ambientmusic.2da`` rows an area OnEnter script selects."""

    day_track: int | None
    night_track: int | None
    battle_track: int | None = None


def _nearest_preceding_int(rows: list[Any], index: int, *, window: int = 8) -> int | None:
    """The nearest CONSTI value pushed before ``index`` (skips object pushes)."""

    for j in range(index - 1, max(-1, index - window), -1):
        if _action_routine(rows[j]) is not None:
            break
        if _instruction_type_name(rows[j]) == "CONSTI":
            args = tuple(getattr(rows[j], "args", ()) or ())
            if args:
                try:
                    return int(args[0])
                except (TypeError, ValueError):
                    return None
    return None


def extract_ncs_area_music_from_instructions(instructions: list[Any] | tuple[Any, ...]) -> NCSAreaMusic:
    """Recover the day/night ambient-music track an area OnEnter script selects.

    Reads ``MusicBackgroundChangeDay``/``…Night`` calls whose ``nTrack`` is a
    literal ``ambientmusic.2da`` row. Later calls win (sequential execution), so
    a script that conditionally overrides the track ends on its final choice.
    """

    rows = list(instructions or ())
    day: int | None = None
    night: int | None = None
    battle: int | None = None
    for index, instruction in enumerate(rows):
        routine = _action_routine(instruction)
        if routine == _ROUTINE_MUSIC_BACKGROUND_CHANGE_DAY:
            track = _nearest_preceding_int(rows, index)
            if track is not None:
                day = track
        elif routine == _ROUTINE_MUSIC_BACKGROUND_CHANGE_NIGHT:
            track = _nearest_preceding_int(rows, index)
            if track is not None:
                night = track
        elif routine == _ROUTINE_MUSIC_BATTLE_CHANGE:
            track = _nearest_preceding_int(rows, index)
            if track is not None:
                battle = track
    return NCSAreaMusic(day_track=day, night_track=night, battle_track=battle)


def extract_ncs_area_music(ncs_bytes: bytes) -> NCSAreaMusic:
    """Recover the area's day/night ambient-music tracks from a compiled NCS."""

    if not ncs_bytes:
        return NCSAreaMusic(None, None)
    try:
        from pykotor.resource.formats.ncs import NCSBinaryReader

        ncs = NCSBinaryReader(io.BytesIO(bytes(ncs_bytes))).load()
    except Exception:
        return NCSAreaMusic(None, None)
    return extract_ncs_area_music_from_instructions(list(getattr(ncs, "instructions", ()) or ()))


def execute_ncs_global_effects(
    ncs_bytes: bytes,
    *,
    evaluator: Any = None,
    journal_sink: Any = None,
) -> list[str]:
    """Apply a compiled script's literal global writes to a condition evaluator.

    Global numbers/booleans are set on ``evaluator`` (via its
    ``set_global_number``/``set_global_boolean`` methods, if present) so later
    conditions read the advanced value; journal writes are forwarded to
    ``journal_sink(name, entry)``. Returns short human-readable labels for each
    write actually applied. Shared by dialogue node scripts and placeable/door
    interaction scripts. Never raises.
    """

    applied: list[str] = []
    try:
        effects = extract_ncs_global_effects(bytes(ncs_bytes or b""))
    except Exception:
        return applied
    for effect in effects:
        try:
            if effect.kind == "global_number" and hasattr(evaluator, "set_global_number"):
                evaluator.set_global_number(effect.name, int(effect.value))
                applied.append(f"{effect.name}={int(effect.value)}")
            elif effect.kind == "global_boolean" and hasattr(evaluator, "set_global_boolean"):
                evaluator.set_global_boolean(effect.name, bool(effect.value))
                applied.append(f"{effect.name}={bool(effect.value)}")
            elif effect.kind == "global_string" and hasattr(evaluator, "set_global_string"):
                evaluator.set_global_string(effect.name, str(effect.value))
                applied.append(f"{effect.name}={str(effect.value)!r}")
            elif effect.kind == "journal" and callable(journal_sink):
                journal_sink(effect.name, int(effect.value))
                applied.append(f"journal {effect.name}:{int(effect.value)}")
        except Exception:
            continue

    # Literal-object local-boolean writes advance the evaluator's local state so
    # a dialogue condition keyed by (owner_tag, index) reads them.
    if hasattr(evaluator, "set_local_boolean"):
        try:
            local_effects = extract_ncs_local_effects(bytes(ncs_bytes or b""))
        except Exception:
            local_effects = ()
        for local in local_effects:
            try:
                evaluator.set_local_boolean(local.owner_tag, local.index, local.value)
                applied.append(f"{local.owner_tag}[{local.index}]={local.value}")
            except Exception:
                continue
    return applied


__all__ = [
    "NCSGlobalEffect",
    "NCSLocalEffect",
    "NCSAreaMusic",
    "extract_ncs_global_effects",
    "extract_ncs_global_effects_from_instructions",
    "extract_ncs_local_effects",
    "extract_ncs_local_effects_from_instructions",
    "extract_ncs_area_music",
    "extract_ncs_area_music_from_instructions",
    "apply_ncs_global_effects",
    "execute_ncs_global_effects",
]
