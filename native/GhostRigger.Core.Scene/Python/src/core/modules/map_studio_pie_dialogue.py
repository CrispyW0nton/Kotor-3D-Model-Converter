"""Bounded DLG traversal for Map Studio Play in Editor.

The Odyssey dialogue runtime executes arbitrary conditional and action NCS,
updates quests, controls cameras, plays LIP/voice resources, and mutates world
state.  PIE must not claim those semantics until their owning simulators exist.
This module therefore owns only the deterministic graph/navigation subset:

* load real K1/K2 DLG bytes with PyKotor;
* resolve localized line text through an optional TLK callback;
* alternate NPC entries and player reply choices;
* follow blank one-link glue nodes and terminal replies;
* guard automatic cycles; and
* evaluate Active/Active2 through an optional, injected headless condition
  service;
* filter conditions that are known false and preserve unknown reply branches
  as visibly labelled preview assumptions; and
* never let an unknown starter outrank a later branch that is known true.

The state machine is Qt-free and does not mutate the DLG model or authored
KMAP data.  A Tools/GUI adapter may use its immutable snapshots to drive a
KOTOR-like overlay, audio, actor animation, and camera presentation.  Retail
KOTOR remains the authority for scripts, conditions, timing, and side effects.
"""

from __future__ import annotations

from collections import deque
from contextlib import redirect_stdout
from dataclasses import dataclass
from enum import Enum
import hashlib
from io import StringIO
import math
from typing import Any, Callable, Iterable, Mapping


TLKLookup = Callable[[int], str]


PIE_DIALOGUE_READY = "ready"
PIE_DIALOGUE_LISTENING = "listening"
PIE_DIALOGUE_CHOOSING = "choosing"
PIE_DIALOGUE_ENDED = "ended"
PIE_DIALOGUE_BLOCKED = "blocked"


class MapStudioPIEDialogueConditionTruth(str, Enum):
    """Three-valued truth used when retail NWScript is not available.

    ``UNKNOWN`` is deliberately distinct from ``TRUE``.  PIE may expose an
    unknown player reply for graph coverage, but it must label that reply as
    assumed and cannot let an unknown starter hide a later known-true branch.
    """

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MapStudioPIEDialogueConditionRequest:
    """One Active or Active2 invocation described by a DLG link.

    Parameters mirror K2's five integer ``Param`` fields plus ``ParamStr``.
    Context identifiers let an injected evaluator resolve local state without
    coupling the dialogue graph to the editor GUI or a particular module.
    """

    game: str
    conversation_resref: str
    owner_id: str
    listener_id: str
    link_id: str
    slot: str
    resref: str
    parameters: tuple[int, int, int, int, int, str]
    negated: bool = False


@dataclass(frozen=True, slots=True)
class MapStudioPIEDialogueConditionResult:
    """Result returned by a bounded condition evaluator."""

    truth: MapStudioPIEDialogueConditionTruth
    reason: str = ""


DialogueConditionValue = bool | None | MapStudioPIEDialogueConditionResult


class MapStudioPIEDialogueConditionTable:
    """Small state-table evaluator suitable for deterministic PIE fixtures.

    Exact ``(resref, parameters)`` rows take precedence over a resref-wide
    value.  The table does not interpret NCS and therefore remains honest
    about the source of its result; production adapters can inject a richer
    evaluator through the same request contract.
    """

    def __init__(
        self,
        by_resref: Mapping[str, DialogueConditionValue] | None = None,
        *,
        by_request: Mapping[
            tuple[str, tuple[int, int, int, int, int, str]],
            DialogueConditionValue,
        ]
        | None = None,
    ) -> None:
        self._by_resref = {
            _clean_resref(key): value
            for key, value in dict(by_resref or {}).items()
            if _clean_resref(key)
        }
        self._by_request = {
            (_clean_resref(key[0]), tuple(key[1])): value
            for key, value in dict(by_request or {}).items()
            if _clean_resref(key[0])
        }

    def evaluate(self, request: MapStudioPIEDialogueConditionRequest) -> DialogueConditionValue:
        exact = (request.resref, request.parameters)
        if exact in self._by_request:
            return self._by_request[exact]
        return self._by_resref.get(request.resref)

    def __call__(self, request: MapStudioPIEDialogueConditionRequest) -> DialogueConditionValue:
        return self.evaluate(request)


@dataclass(frozen=True, slots=True)
class MapStudioPIEDialogueStarterOption:
    """One real DLG starter exposed to the editor preview context."""

    conversation_resref: str
    node_id: str
    link_id: str
    label: str
    text: str
    speaker_tag: str
    condition_resrefs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MapStudioPIEDialogueConversationOption:
    """One resource-backed conversation and its available starter nodes."""

    conversation_resref: str
    display_name: str
    owner_ids: tuple[str, ...]
    owner_names: tuple[str, ...]
    resource_sha256: str
    source_label: str
    starters: tuple[MapStudioPIEDialogueStarterOption, ...]


def _clean_resref(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("resref(") and text.endswith(")"):
        text = text[7:-1].strip()
    return "" if text in {"", "****", "null"} else text[:16]


class MapStudioPIEDialogueContextEvaluator:
    """Evaluate a bounded set of stock predicates from the PIE sandbox.

    The retail dialogue VM remains authoritative for arbitrary NCS and plot
    state.  The predicates below are safe to resolve from the editor's selected
    player identity and explicit preview globals.  Absent globals use Odyssey's
    clean-state zero/false defaults.  Everything else deliberately remains
    unknown unless the caller supplies an explicit bounded override.
    """

    def __init__(
        self,
        *,
        player_role: str = "player",
        player_gender: str = "male",
        global_numbers: Mapping[str, int] | None = None,
        global_booleans: Mapping[str, bool] | None = None,
        local_booleans: Mapping[tuple[str, int], bool] | None = None,
        overrides: Mapping[str, DialogueConditionValue] | None = None,
    ) -> None:
        role = str(player_role or "player").strip().lower().replace("-", "_")
        self.player_role = "b4d4" if role in {"b4d4", "b_4d4", "protocol_droid"} else "player"
        gender = str(player_gender or "male").strip().lower()
        self.player_gender = "female" if gender in {"female", "f", "woman"} else "male"
        self._global_numbers = {
            str(key or "").strip().casefold(): int(value)
            for key, value in dict(global_numbers or {}).items()
            if str(key or "").strip()
        }
        self._global_booleans = {
            str(key or "").strip().casefold(): bool(value)
            for key, value in dict(global_booleans or {}).items()
            if str(key or "").strip()
        }
        self._local_booleans = {
            (str(key[0] or "").strip().casefold(), int(key[1])): bool(value)
            for key, value in dict(local_booleans or {}).items()
            if isinstance(key, tuple) and len(key) == 2
        }
        self._overrides = {
            _clean_resref(key): value
            for key, value in dict(overrides or {}).items()
            if _clean_resref(key)
        }

    def evaluate(self, request: MapStudioPIEDialogueConditionRequest) -> DialogueConditionValue:
        if request.resref in self._overrides:
            return self._overrides[request.resref]
        first, _second, _third, _fourth, _fifth, parameter_string = request.parameters
        global_name = str(parameter_string or "").strip().casefold()
        global_number = self._global_numbers.get(global_name, 0)
        global_boolean = self._global_booleans.get(global_name, False)
        if request.resref == "c_b4d4pc":
            return MapStudioPIEDialogueConditionResult(
                MapStudioPIEDialogueConditionTruth.TRUE
                if self._global_numbers.get("203tel_b-4d4_pc", 1 if self.player_role == "b4d4" else 0) == 1
                else MapStudioPIEDialogueConditionTruth.FALSE,
                "c_b4d4pc checks whether global number 203TEL_B-4D4_PC equals 1.",
            )
        if request.resref == "c_ismale":
            return MapStudioPIEDialogueConditionResult(
                MapStudioPIEDialogueConditionTruth.TRUE
                if self.player_gender == "male"
                else MapStudioPIEDialogueConditionTruth.FALSE,
                f"PIE player gender is {self.player_gender}.",
            )
        if request.resref == "c_isfemale":
            return MapStudioPIEDialogueConditionResult(
                MapStudioPIEDialogueConditionTruth.TRUE
                if self.player_gender == "female"
                else MapStudioPIEDialogueConditionTruth.FALSE,
                f"PIE player gender is {self.player_gender}.",
            )
        if request.resref in {"c_chk202luxa", "c_chk202falt"}:
            variable = "202tel_luxa" if request.resref == "c_chk202luxa" else "202tel_falt"
            return MapStudioPIEDialogueConditionResult(
                MapStudioPIEDialogueConditionTruth.TRUE
                if self._global_numbers.get(variable, 0) == first
                else MapStudioPIEDialogueConditionTruth.FALSE,
                f"{request.resref} compares global number {variable} with Param1 ({first}).",
            )
        if request.resref == "c_global_eq" and global_name:
            value = global_number == first
        elif request.resref == "c_global_gt" and global_name:
            value = global_number > first
        elif request.resref == "c_global_lt" and global_name:
            value = global_number < first
        elif request.resref == "c_global_set" and global_name:
            value = global_boolean
        elif request.resref in {"c_global_notset", "c_global_unset"} and global_name:
            value = not global_boolean
        elif request.resref == "c_talkedto":
            value = self._local_booleans.get((str(request.owner_id or "").casefold(), 10), False)
        elif request.resref == "c_local_set":
            value = self._local_booleans.get((str(request.owner_id or "").casefold(), first), False)
        else:
            return None
        return MapStudioPIEDialogueConditionResult(
            MapStudioPIEDialogueConditionTruth.TRUE if value else MapStudioPIEDialogueConditionTruth.FALSE,
            "PIE evaluated a bounded stock global/local-state predicate; absent sandbox values use Odyssey defaults.",
        )

    def __call__(self, request: MapStudioPIEDialogueConditionRequest) -> DialogueConditionValue:
        return self.evaluate(request)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def map_studio_pie_dialogue_line_interval(
    text: str,
    *,
    delay_milliseconds: int = -1,
    audio_duration_seconds: float | None = None,
) -> float:
    """Return a bounded editor-side approximation of Odyssey line timing.

    Fresh executable evidence proves that retail prefers an audio/TLK-derived
    duration, falls back to text length, enforces a minimum, and treats DLG
    ``Delay`` (milliseconds) as a lower bound.  The exact retail text-rate and
    every ``WaitFlags`` bit remain unknown, so those two constants are kept as
    an explicit preview policy rather than labelled engine facts.
    """

    normalized = " ".join(str(text or "").split())
    # Roughly 18 readable characters per second plus a short presentation
    # lead-in.  Bound malformed/very long editor text while allowing an
    # explicit authored Delay to remain the required lower bound.
    text_fallback = min(15.0, max(1.0, 0.75 + (len(normalized) / 18.0)))
    audio = _optional_float(audio_duration_seconds)
    if audio is not None and audio > 0.0:
        base = min(60.0, max(1.0, audio))
    else:
        base = text_fallback
    try:
        delay = max(0.0, int(delay_milliseconds) / 1000.0)
    except (TypeError, ValueError, OverflowError):
        delay = 0.0
    return max(base, delay)


@dataclass(frozen=True, slots=True)
class MapStudioPIEDialogueAnimationPolicy:
    """Playback flags recovered from one ``dialoganimations.2da`` row."""

    animation_id: int
    name: str = ""
    dialog: bool = False
    fire_and_forget: bool = False
    looping: bool = False
    overlay: bool = False


def load_map_studio_pie_dialogue_animation_policies(
    two_da_bytes: bytes,
) -> dict[int, MapStudioPIEDialogueAnimationPolicy]:
    """Parse dialogue animation playback policy without importing Qt."""

    payload = bytes(two_da_bytes or b"")
    if not payload:
        return {}
    try:
        from pykotor.resource.formats.twoda import read_2da

        table = read_2da(payload)
    except Exception:
        return {}

    headers = {str(value).casefold(): str(value) for value in table.get_headers()}

    def cell(row: int, name: str) -> str:
        header = headers.get(name.casefold())
        if not header:
            return ""
        try:
            value = str(table.get_cell(row, header) or "").strip()
        except Exception:
            return ""
        return "" if value == "****" else value

    def flag(row: int, name: str) -> bool:
        return cell(row, name).casefold() in {"1", "true", "yes"}

    result: dict[int, MapStudioPIEDialogueAnimationPolicy] = {}
    for row in range(int(table.get_height())):
        try:
            animation_id = int(table.get_label(row))
        except (TypeError, ValueError):
            animation_id = row
        result[animation_id] = MapStudioPIEDialogueAnimationPolicy(
            animation_id=animation_id,
            name=cell(row, "name"),
            dialog=flag(row, "dialog"),
            fire_and_forget=flag(row, "fireforget"),
            looping=flag(row, "looping"),
            overlay=flag(row, "overlay"),
        )
    return result


def _localized_text(value: Any, tlk_lookup: TLKLookup | None) -> str:
    """Resolve a PyKotor ``LocalizedString`` without changing it."""

    if value is None:
        return ""
    try:
        stringref = int(getattr(value, "stringref", -1))
    except (TypeError, ValueError):
        stringref = -1
    if stringref >= 0 and callable(tlk_lookup):
        try:
            resolved = str(tlk_lookup(stringref) or "")
        except Exception:
            resolved = ""
        if resolved:
            return resolved

    substrings = dict(getattr(value, "_substrings_internal", {}) or {})
    if 0 in substrings:
        return str(substrings[0] or "")
    if substrings:
        return str(next(iter(substrings.values())) or "")

    # PyKotor can provide a language/gender fallback even when a caller did
    # not supply a TLK service.  Keep this last so embedded substring identity
    # remains deterministic in focused tests and authored documents.
    getter = getattr(value, "get", None)
    if callable(getter):
        try:
            from pykotor.common.language import Gender, Language

            fallback = getter(Language.ENGLISH, Gender.MALE, use_fallback=True)
            if fallback:
                return str(fallback)
        except Exception:
            pass
    return f"<TLK {stringref}>" if stringref >= 0 else ""


def _node_text(node: Any, tlk_lookup: TLKLookup | None) -> str:
    return _localized_text(getattr(node, "text", None), tlk_lookup)


def _condition_resrefs(link: Any) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            value
            for name in ("active1", "active2")
            if (value := _clean_resref(getattr(link, name, "")))
        )
    )


def _condition_parameters(link: Any, slot: str) -> tuple[int, int, int, int, int, str]:
    integers: list[int] = []
    for index in range(1, 6):
        try:
            integers.append(int(getattr(link, f"{slot}_param{index}", 0) or 0))
        except (TypeError, ValueError, OverflowError):
            integers.append(0)
    return (
        integers[0],
        integers[1],
        integers[2],
        integers[3],
        integers[4],
        str(getattr(link, f"{slot}_param6", "") or ""),
    )


def _coerce_condition_result(
    value: DialogueConditionValue | Any,
    *,
    fallback_reason: str,
) -> MapStudioPIEDialogueConditionResult:
    if isinstance(value, MapStudioPIEDialogueConditionResult):
        return value
    if value is True:
        return MapStudioPIEDialogueConditionResult(
            MapStudioPIEDialogueConditionTruth.TRUE,
            fallback_reason,
        )
    if value is False:
        return MapStudioPIEDialogueConditionResult(
            MapStudioPIEDialogueConditionTruth.FALSE,
            fallback_reason,
        )
    if value is None:
        return MapStudioPIEDialogueConditionResult(
            MapStudioPIEDialogueConditionTruth.UNKNOWN,
            fallback_reason,
        )
    return MapStudioPIEDialogueConditionResult(
        MapStudioPIEDialogueConditionTruth.UNKNOWN,
        f"{fallback_reason} Evaluator returned unsupported {type(value).__name__} data.",
    )


def _negate_condition_result(
    result: MapStudioPIEDialogueConditionResult,
) -> MapStudioPIEDialogueConditionResult:
    if result.truth == MapStudioPIEDialogueConditionTruth.TRUE:
        truth = MapStudioPIEDialogueConditionTruth.FALSE
    elif result.truth == MapStudioPIEDialogueConditionTruth.FALSE:
        truth = MapStudioPIEDialogueConditionTruth.TRUE
    else:
        truth = MapStudioPIEDialogueConditionTruth.UNKNOWN
    reason = f"DLG NOT applied. {result.reason}".strip()
    return MapStudioPIEDialogueConditionResult(truth, reason)


@dataclass(frozen=True, slots=True)
class _MapStudioPIELinkConditionEvaluation:
    truth: MapStudioPIEDialogueConditionTruth
    logic: str
    requests: tuple[MapStudioPIEDialogueConditionRequest, ...] = ()
    results: tuple[MapStudioPIEDialogueConditionResult, ...] = ()

    @property
    def diagnostics(self) -> tuple[str, ...]:
        return tuple(
            f"{request.slot} {request.resref}: {result.truth.value}"
            + (f" ({result.reason})" if result.reason else "")
            for request, result in zip(self.requests, self.results, strict=True)
        )


def _node_script_resrefs(node: Any) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            value
            for name in ("script1", "script2")
            if (value := _clean_resref(getattr(node, name, "")))
        )
    )


@dataclass(frozen=True, slots=True)
class MapStudioPIEDialogueChoice:
    """One numbered player reply exposed by the current entry."""

    number: int
    link_id: str
    node_id: str
    text: str
    condition_resrefs: tuple[str, ...] = ()
    condition_logic: str = "AND"
    preview_assumed: bool = False
    display_inactive: bool = False
    condition_state: str = MapStudioPIEDialogueConditionTruth.TRUE.value
    condition_diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MapStudioPIEDialogueEvent:
    """One honest state transition or deferred Odyssey behavior."""

    kind: str
    message: str
    node_id: str = ""
    link_id: str = ""
    resrefs: tuple[str, ...] = ()
    preview_assumed: bool = False


@dataclass(frozen=True, slots=True)
class MapStudioPIEDialogueSnapshot:
    """Immutable conversation presentation state for a GUI/runtime adapter."""

    state: str
    game: str
    conversation_resref: str
    owner_id: str = ""
    listener_id: str = ""
    current_node_id: str = ""
    current_node_kind: str = ""
    speaker_tag: str = ""
    listener_tag: str = ""
    text: str = ""
    sound_resref: str = ""
    voice_resref: str = ""
    camera_angle: int = 0
    camera_id: int | None = None
    camera_animation: int | None = None
    camera_fov: float | None = None
    camera_height_offset: float = 0.0
    target_height_offset: float = 0.0
    animations: tuple[tuple[str, int], ...] = ()
    choices: tuple[MapStudioPIEDialogueChoice, ...] = ()
    can_continue: bool = False
    can_abort: bool = False
    ended: bool = False
    blocked: bool = False
    skippable: bool = False
    node_unskippable: bool = False
    delay: int = -1
    wait_flags: int = 0
    line_interval_seconds: float = 1.0
    conversation_type: int = 0
    events: tuple[MapStudioPIEDialogueEvent, ...] = ()
    warnings: tuple[str, ...] = ()


class MapStudioPIEDialogueSession:
    """Traverse one DLG without executing arbitrary scripts.

    ``choose`` accepts the one-based number exposed by
    :class:`MapStudioPIEDialogueChoice`, matching KOTOR's numbered PC replies.
    An injected ``condition_evaluator`` can provide bounded editor state for
    one Active/Active2 request at a time.  Unknown player replies remain
    selectable for graph coverage with explicit assumption diagnostics, while
    unknown automatic links cannot outrank a branch that is known true.
    """

    def __init__(
        self,
        dlg_bytes: bytes,
        *,
        game: str = "K2",
        resref: str = "",
        owner_id: str = "",
        listener_id: str = "",
        tlk_lookup: TLKLookup | None = None,
        condition_evaluator: Any = None,
        starter_link_id: str = "",
        allow_unknown_starter_assumption: bool = True,
        max_auto_hops: int = 64,
    ) -> None:
        payload = bytes(dlg_bytes or b"")
        if not payload:
            raise ValueError("PIE dialogue requires non-empty DLG bytes.")
        try:
            from pykotor.resource.generics.dlg import read_dlg

            # Some PyKotor GFF readers still print optional field diagnostics.
            # Loading dialogue for PIE must not flood the embedded terminal.
            with redirect_stdout(StringIO()):
                dialogue = read_dlg(payload)
        except Exception as exc:
            raise ValueError(f"PIE could not parse DLG {resref or '(unnamed)'}: {exc}") from exc

        self.game = "K1" if str(game or "K2").strip().upper() in {"K1", "1", "KOTOR", "KOTOR1"} else "K2"
        self.resref = _clean_resref(resref)
        self.owner_id = str(owner_id or "")
        self.listener_id = str(listener_id or "")
        self.tlk_lookup = tlk_lookup
        self.condition_evaluator = condition_evaluator
        self.starter_link_id = str(starter_link_id or "").strip().lower()
        self.allow_unknown_starter_assumption = bool(allow_unknown_starter_assumption)
        self.max_auto_hops = max(1, int(max_auto_hops))
        self._dialogue = dialogue
        self._state = PIE_DIALOGUE_READY
        self._current_entry: Any = None
        self._choice_links: tuple[Any, ...] = ()
        self._choice_condition_evaluations: tuple[_MapStudioPIELinkConditionEvaluation, ...] = ()
        self._choices: tuple[MapStudioPIEDialogueChoice, ...] = ()
        self._events: list[MapStudioPIEDialogueEvent] = []
        self._warnings: list[str] = []
        self._node_ids: dict[int, str] = {}
        self._link_ids: dict[int, str] = {}
        self._index_graph()

    @classmethod
    def from_bytes(cls, dlg_bytes: bytes, **kwargs: Any) -> "MapStudioPIEDialogueSession":
        """Named constructor kept for resource-reader and test adapters."""

        return cls(dlg_bytes, **kwargs)

    @property
    def state(self) -> str:
        return self._state

    @property
    def active(self) -> bool:
        return self._state in {PIE_DIALOGUE_LISTENING, PIE_DIALOGUE_CHOOSING}

    @property
    def ended(self) -> bool:
        return self._state in {PIE_DIALOGUE_ENDED, PIE_DIALOGUE_BLOCKED}

    def starter_options(self) -> tuple[MapStudioPIEDialogueStarterOption, ...]:
        """Return the actual ordered DLG starters for compact editor controls."""

        options: list[MapStudioPIEDialogueStarterOption] = []
        for link in tuple(getattr(self._dialogue, "starters", ()) or ()):
            node = getattr(link, "node", None)
            if node is None or node.__class__.__name__ != "DLGEntry":
                continue
            node_id = self._node_id(node)
            text = " ".join(_node_text(node, self.tlk_lookup).split())
            summary = text or "(blank entry)"
            if len(summary) > 72:
                summary = summary[:69].rstrip() + "..."
            conditions = _condition_resrefs(link)
            condition_suffix = f" [{', '.join(conditions)}]" if conditions else ""
            options.append(
                MapStudioPIEDialogueStarterOption(
                    conversation_resref=self.resref,
                    node_id=node_id,
                    link_id=self._link_id(link),
                    label=f"{node_id} - {summary}{condition_suffix}",
                    text=text,
                    speaker_tag=str(getattr(node, "speaker", "") or ""),
                    condition_resrefs=conditions,
                )
            )
        return tuple(options)

    def _index_graph(self) -> None:
        """Assign stable-in-session IDs without recursing through cycles."""

        used_node_ids: set[str] = set()
        used_link_ids: set[str] = set()
        node_counts = {"entry": 0, "reply": 0}
        pending: deque[tuple[Any, str, int]] = deque(
            (link, "starter", index)
            for index, link in enumerate(tuple(getattr(self._dialogue, "starters", ()) or ()))
        )
        seen_links: set[int] = set()
        expanded_nodes: set[int] = set()
        while pending:
            link, source_id, link_index = pending.popleft()
            if link is None or id(link) in seen_links:
                continue
            seen_links.add(id(link))
            link_base = f"{source_id}:link:{link_index}"
            link_id = link_base
            suffix = 2
            while link_id in used_link_ids:
                link_id = f"{link_base}:{suffix}"
                suffix += 1
            used_link_ids.add(link_id)
            self._link_ids[id(link)] = link_id

            node = getattr(link, "node", None)
            if node is None:
                continue
            kind = "entry" if node.__class__.__name__ == "DLGEntry" else "reply"
            if id(node) not in self._node_ids:
                try:
                    list_index = int(getattr(node, "list_index", -1))
                except (TypeError, ValueError):
                    list_index = -1
                if list_index >= 0:
                    node_base = f"{kind}:{list_index}"
                else:
                    node_base = f"{kind}:runtime:{node_counts[kind]}"
                node_counts[kind] += 1
                node_id = node_base
                suffix = 2
                while node_id in used_node_ids:
                    node_id = f"{node_base}:{suffix}"
                    suffix += 1
                used_node_ids.add(node_id)
                self._node_ids[id(node)] = node_id
            node_id = self._node_ids[id(node)]
            if id(node) in expanded_nodes:
                continue
            expanded_nodes.add(id(node))
            for child_index, child in enumerate(tuple(getattr(node, "links", ()) or ())):
                pending.append((child, node_id, child_index))

    def _node_id(self, node: Any) -> str:
        return self._node_ids.get(id(node), "")

    def _link_id(self, link: Any) -> str:
        return self._link_ids.get(id(link), "")

    def _reset_events(self) -> None:
        self._events = []

    def _emit(
        self,
        kind: str,
        message: str,
        *,
        node: Any = None,
        link: Any = None,
        resrefs: Iterable[str] = (),
        preview_assumed: bool = False,
    ) -> None:
        self._events.append(
            MapStudioPIEDialogueEvent(
                kind=str(kind),
                message=str(message),
                node_id=self._node_id(node) if node is not None else "",
                link_id=self._link_id(link) if link is not None else "",
                resrefs=tuple(dict.fromkeys(_clean_resref(value) for value in resrefs if _clean_resref(value))),
                preview_assumed=bool(preview_assumed),
            )
        )

    def _condition_request(self, link: Any, slot: str) -> MapStudioPIEDialogueConditionRequest | None:
        resref = _clean_resref(getattr(link, slot, ""))
        if not resref:
            return None
        return MapStudioPIEDialogueConditionRequest(
            game=self.game,
            conversation_resref=self.resref,
            owner_id=self.owner_id,
            listener_id=self.listener_id,
            link_id=self._link_id(link),
            slot=slot,
            resref=resref,
            parameters=_condition_parameters(link, slot),
            negated=bool(getattr(link, f"{slot}_not", False)),
        )

    def _evaluate_condition_request(
        self,
        request: MapStudioPIEDialogueConditionRequest,
    ) -> MapStudioPIEDialogueConditionResult:
        evaluator = self.condition_evaluator
        if evaluator is None:
            result = MapStudioPIEDialogueConditionResult(
                MapStudioPIEDialogueConditionTruth.UNKNOWN,
                "No bounded PIE condition evaluator was supplied; arbitrary NWScript remains deferred.",
            )
        else:
            evaluate = getattr(evaluator, "evaluate", None)
            try:
                if callable(evaluate):
                    raw = evaluate(request)
                elif callable(evaluator):
                    raw = evaluator(request)
                else:
                    raw = None
                result = _coerce_condition_result(
                    raw,
                    fallback_reason="Bounded PIE condition state was injected by the caller.",
                )
            except Exception as exc:
                result = MapStudioPIEDialogueConditionResult(
                    MapStudioPIEDialogueConditionTruth.UNKNOWN,
                    f"Condition evaluator failed safely: {exc.__class__.__name__}: {exc}",
                )
        return _negate_condition_result(result) if request.negated else result

    def _evaluate_link_condition(self, link: Any) -> _MapStudioPIELinkConditionEvaluation:
        requests = tuple(
            request
            for slot in ("active1", "active2")
            if (request := self._condition_request(link, slot)) is not None
        )
        logic = "OR" if bool(getattr(link, "logic", False)) else "AND"
        if not requests:
            return _MapStudioPIELinkConditionEvaluation(
                MapStudioPIEDialogueConditionTruth.TRUE,
                logic,
            )
        results = tuple(self._evaluate_condition_request(request) for request in requests)
        truths = tuple(result.truth for result in results)
        if len(truths) == 1:
            combined = truths[0]
        elif logic == "OR":
            if MapStudioPIEDialogueConditionTruth.TRUE in truths:
                combined = MapStudioPIEDialogueConditionTruth.TRUE
            elif MapStudioPIEDialogueConditionTruth.UNKNOWN in truths:
                combined = MapStudioPIEDialogueConditionTruth.UNKNOWN
            else:
                combined = MapStudioPIEDialogueConditionTruth.FALSE
        else:
            if MapStudioPIEDialogueConditionTruth.FALSE in truths:
                combined = MapStudioPIEDialogueConditionTruth.FALSE
            elif MapStudioPIEDialogueConditionTruth.UNKNOWN in truths:
                combined = MapStudioPIEDialogueConditionTruth.UNKNOWN
            else:
                combined = MapStudioPIEDialogueConditionTruth.TRUE
        return _MapStudioPIELinkConditionEvaluation(combined, logic, requests, results)

    def _report_condition_evaluation(
        self,
        link: Any,
        evaluation: _MapStudioPIELinkConditionEvaluation,
    ) -> None:
        if not evaluation.requests:
            return
        details = "; ".join(evaluation.diagnostics)
        if evaluation.truth == MapStudioPIEDialogueConditionTruth.TRUE:
            self._emit(
                "condition_evaluated_true",
                f"PIE condition evaluated true using bounded editor state. {details}",
                link=link,
                resrefs=(request.resref for request in evaluation.requests),
            )
        elif evaluation.truth == MapStudioPIEDialogueConditionTruth.FALSE:
            self._emit(
                "condition_evaluated_false",
                f"PIE skipped a branch whose condition evaluated false. {details}",
                link=link,
                resrefs=(request.resref for request in evaluation.requests),
            )
        else:
            self._emit(
                "condition_unknown",
                f"PIE could not prove this branch condition. {details}",
                link=link,
                resrefs=(request.resref for request in evaluation.requests),
            )

    def _mark_condition_assumed(
        self,
        link: Any,
        evaluation: _MapStudioPIELinkConditionEvaluation,
    ) -> tuple[str, ...]:
        conditions = _condition_resrefs(link)
        if conditions and evaluation.truth == MapStudioPIEDialogueConditionTruth.UNKNOWN:
            self._emit(
                "condition_preview_assumed",
                "PIE included this branch as an explicit preview assumption; its Active/Active2 result is unknown.",
                link=link,
                resrefs=conditions,
                preview_assumed=True,
            )
        return conditions

    def _defer_node_scripts(self, node: Any) -> None:
        scripts = _node_script_resrefs(node)
        if scripts:
            self._emit(
                "node_scripts_deferred",
                "Dialogue node action scripts were preserved but not executed by PIE.",
                node=node,
                resrefs=scripts,
            )

    def _guard_node(self, node: Any, seen: set[str], hops: list[int]) -> bool:
        node_id = self._node_id(node) or f"runtime:{id(node)}"
        hops[0] += 1
        if node_id in seen or hops[0] > self.max_auto_hops:
            self._state = PIE_DIALOGUE_BLOCKED
            self._choice_links = ()
            self._choice_condition_evaluations = ()
            self._choices = ()
            message = (
                f"Automatic dialogue traversal stopped at {node_id}; the blank-node path cycles "
                f"or exceeds {self.max_auto_hops} hops."
            )
            self._warnings.append(message)
            self._emit("automatic_cycle_blocked", message, node=node)
            return False
        seen.add(node_id)
        return True

    def _first_target_link(self, links: Iterable[Any], *, expected_kind: str) -> Any | None:
        unknown: list[tuple[Any, _MapStudioPIELinkConditionEvaluation]] = []
        for link in tuple(links or ()):
            node = getattr(link, "node", None)
            if node is None:
                self._emit("broken_link_skipped", "PIE skipped a DLG link with no target node.", link=link)
                continue
            kind = "entry" if node.__class__.__name__ == "DLGEntry" else "reply"
            if kind != expected_kind:
                self._emit(
                    "invalid_link_target_skipped",
                    f"PIE skipped a DLG link that targeted {kind} where {expected_kind} was required.",
                    node=node,
                    link=link,
                )
                continue
            evaluation = self._evaluate_link_condition(link)
            self._report_condition_evaluation(link, evaluation)
            if evaluation.truth == MapStudioPIEDialogueConditionTruth.TRUE:
                return link
            if evaluation.truth == MapStudioPIEDialogueConditionTruth.UNKNOWN:
                unknown.append((link, evaluation))
        if unknown and self.allow_unknown_starter_assumption:
            link, evaluation = unknown[0]
            self._mark_condition_assumed(link, evaluation)
            return link
        return None

    def _enter_entry(self, entry: Any, seen: set[str], hops: list[int]) -> None:
        if not self._guard_node(entry, seen, hops):
            return
        self._current_entry = entry
        self._choice_links = ()
        self._choice_condition_evaluations = ()
        self._choices = ()
        self._defer_node_scripts(entry)
        text = _node_text(entry, self.tlk_lookup)
        if text:
            self._state = PIE_DIALOGUE_LISTENING
            self._emit("entry_presented", "PIE presented an NPC dialogue entry.", node=entry)
            return
        self._emit(
            "blank_entry_glue",
            "PIE followed a blank entry as dialogue glue without displaying fabricated text.",
            node=entry,
        )
        self._present_replies(entry, seen, hops)

    def _choice_for(
        self,
        link: Any,
        number: int,
        evaluation: _MapStudioPIELinkConditionEvaluation,
    ) -> MapStudioPIEDialogueChoice:
        reply = getattr(link, "node", None)
        conditions = _condition_resrefs(link)
        return MapStudioPIEDialogueChoice(
            number=number,
            link_id=self._link_id(link),
            node_id=self._node_id(reply),
            text=_node_text(reply, self.tlk_lookup) if reply is not None else "",
            condition_resrefs=conditions,
            condition_logic=evaluation.logic,
            preview_assumed=evaluation.truth == MapStudioPIEDialogueConditionTruth.UNKNOWN,
            display_inactive=bool(getattr(link, "display_inactive", False)),
            condition_state=evaluation.truth.value,
            condition_diagnostics=evaluation.diagnostics,
        )

    def _present_replies(self, entry: Any, seen: set[str], hops: list[int]) -> None:
        valid: list[tuple[Any, _MapStudioPIELinkConditionEvaluation]] = []
        for link in tuple(getattr(entry, "links", ()) or ()):
            reply = getattr(link, "node", None)
            if reply is None:
                self._emit("broken_link_skipped", "PIE skipped a reply link with no target node.", link=link)
                continue
            if reply.__class__.__name__ != "DLGReply":
                self._emit(
                    "invalid_link_target_skipped",
                    "PIE skipped an entry link that did not target a player reply.",
                    node=reply,
                    link=link,
                )
                continue
            evaluation = self._evaluate_link_condition(link)
            self._report_condition_evaluation(link, evaluation)
            if evaluation.truth == MapStudioPIEDialogueConditionTruth.FALSE:
                continue
            if evaluation.truth == MapStudioPIEDialogueConditionTruth.UNKNOWN:
                self._mark_condition_assumed(link, evaluation)
            valid.append((link, evaluation))
        if not valid:
            self._finish(aborted=False)
            return

        # Odyssey uses a single blank reply with an outgoing entry as a
        # continue/glue node, and a single blank terminal reply as End Dialog.
        if len(valid) == 1 and not _node_text(getattr(valid[0][0], "node", None), self.tlk_lookup):
            link, evaluation = valid[0]
            self._emit(
                "blank_reply_glue",
                "PIE followed the single blank player reply without inventing a visible choice.",
                node=getattr(link, "node", None),
                link=link,
            )
            self._select_reply_link(link, evaluation, seen, hops, automatic=True)
            return

        self._choice_links = tuple(link for link, _evaluation in valid)
        self._choice_condition_evaluations = tuple(evaluation for _link, evaluation in valid)
        self._choices = tuple(
            self._choice_for(link, index + 1, evaluation)
            for index, (link, evaluation) in enumerate(valid)
        )
        self._state = PIE_DIALOGUE_CHOOSING
        self._emit(
            "choices_presented",
            f"PIE presented {len(self._choices)} numbered player reply choice(s).",
            node=entry,
        )

    def _select_reply_link(
        self,
        link: Any,
        evaluation: _MapStudioPIELinkConditionEvaluation,
        seen: set[str],
        hops: list[int],
        *,
        automatic: bool,
    ) -> None:
        reply = getattr(link, "node", None)
        if reply is None or reply.__class__.__name__ != "DLGReply":
            self._state = PIE_DIALOGUE_BLOCKED
            self._emit("invalid_reply_selection", "PIE could not follow the selected reply link.", link=link)
            return
        if automatic and not self._guard_node(reply, seen, hops):
            return
        # Visible choices start a new event batch when ``choose`` is called,
        # so repeat the assumption there.  Automatic blank-reply glue is
        # selected in the same batch where ``_present_replies`` already
        # recorded its condition and must not duplicate the warning.
        if not automatic:
            self._mark_condition_assumed(link, evaluation)
        self._defer_node_scripts(reply)
        self._emit(
            "reply_selected",
            "PIE selected a player reply and followed its next entry link.",
            node=reply,
            link=link,
        )
        next_link = self._first_target_link(getattr(reply, "links", ()), expected_kind="entry")
        if next_link is None:
            self._finish(aborted=False)
            return
        self._enter_entry(getattr(next_link, "node", None), seen, hops)

    def _finish(self, *, aborted: bool) -> None:
        self._state = PIE_DIALOGUE_ENDED
        self._choice_links = ()
        self._choice_condition_evaluations = ()
        self._choices = ()
        script = _clean_resref(getattr(self._dialogue, "on_abort" if aborted else "on_end", ""))
        if script:
            self._emit(
                "conversation_end_script_deferred",
                "The conversation end script was preserved but not executed by PIE.",
                resrefs=(script,),
            )
        self._emit(
            "conversation_aborted" if aborted else "conversation_ended",
            "PIE aborted the dialogue preview." if aborted else "PIE reached the end of the dialogue preview.",
        )

    def start(self) -> MapStudioPIEDialogueSnapshot:
        """Select the first preview-eligible starter and present its entry."""

        if self._state != PIE_DIALOGUE_READY:
            return self.snapshot()
        self._reset_events()
        self._emit(
            "conversation_started",
            "PIE started bounded DLG graph traversal; arbitrary NWScript remains deferred.",
        )
        link = None
        if self.starter_link_id:
            link = next(
                (
                    candidate
                    for candidate in tuple(getattr(self._dialogue, "starters", ()) or ())
                    if self._link_id(candidate).lower() == self.starter_link_id
                ),
                None,
            )
            if link is not None:
                self._emit(
                    "starter_override_applied",
                    "PIE forced the editor-selected DLG starter node; retail conditions were intentionally bypassed for preview.",
                    node=getattr(link, "node", None),
                    link=link,
                    resrefs=_condition_resrefs(link),
                    preview_assumed=True,
                )
            else:
                message = (
                    f"Configured PIE starter link {self.starter_link_id!r} is not present in DLG "
                    f"{self.resref or '(unnamed)'}; automatic selection was used."
                )
                self._warnings.append(message)
                self._emit("starter_override_missing", message)
        if link is None:
            link = self._first_target_link(getattr(self._dialogue, "starters", ()), expected_kind="entry")
        if link is None:
            self._state = PIE_DIALOGUE_BLOCKED
            message = "Dialogue has no valid starting NPC entry."
            self._warnings.append(message)
            self._emit("missing_starting_entry", message)
            return self.snapshot()
        self._enter_entry(getattr(link, "node", None), set(), [0])
        return self.snapshot()

    def continue_dialogue(self) -> MapStudioPIEDialogueSnapshot:
        """Finish the current NPC line and expose/follow its replies."""

        self._reset_events()
        if self._state != PIE_DIALOGUE_LISTENING or self._current_entry is None:
            self._emit("continue_ignored", "PIE ignored Continue because no NPC line is being presented.")
            return self.snapshot()
        self._present_replies(self._current_entry, set(), [0])
        return self.snapshot()

    def advance(self) -> MapStudioPIEDialogueSnapshot:
        """Alias used by timer/audio adapters when an NPC line completes."""

        return self.continue_dialogue()

    def choose(self, number: int) -> MapStudioPIEDialogueSnapshot:
        """Choose one visible one-based player reply number."""

        self._reset_events()
        if self._state != PIE_DIALOGUE_CHOOSING:
            self._emit("choice_ignored", "PIE ignored the reply choice because choices are not active.")
            return self.snapshot()
        try:
            wanted = int(number)
        except (TypeError, ValueError):
            wanted = -1
        if wanted < 1 or wanted > len(self._choice_links):
            self._emit(
                "choice_rejected",
                f"PIE reply choice {number!r} is outside 1..{len(self._choice_links)}.",
            )
            return self.snapshot()
        self._select_reply_link(
            self._choice_links[wanted - 1],
            self._choice_condition_evaluations[wanted - 1],
            set(),
            [0],
            automatic=False,
        )
        return self.snapshot()

    def abort(self) -> MapStudioPIEDialogueSnapshot:
        """End the editor preview without executing EndConverAbort."""

        self._reset_events()
        if self.ended or self._state == PIE_DIALOGUE_READY:
            self._emit("abort_ignored", "PIE ignored Abort because no dialogue preview is active.")
            return self.snapshot()
        self._finish(aborted=True)
        return self.snapshot()

    def end(self) -> MapStudioPIEDialogueSnapshot:
        """Explicitly finish the preview without executing EndConversation."""

        self._reset_events()
        if not self.ended:
            self._finish(aborted=False)
        return self.snapshot()

    def snapshot(self) -> MapStudioPIEDialogueSnapshot:
        """Return the current immutable presentation state."""

        node = self._current_entry
        animations = tuple(
            (
                str(getattr(animation, "participant", "") or ""),
                int(getattr(animation, "animation_id", 0) or 0),
            )
            for animation in tuple(getattr(node, "animations", ()) or ())
        ) if node is not None else ()
        try:
            conversation_type = int(getattr(self._dialogue, "conversation_type", 0) or 0)
        except (TypeError, ValueError):
            conversation_type = 0
        camera_angle = int(getattr(node, "camera_angle", 0) or 0) if node is not None else 0
        camera_id = _optional_int(getattr(node, "camera_id", None)) if node is not None else None
        if camera_angle != 6 or camera_id is None or camera_id < 0:
            camera_id = None
        camera_fov = _optional_float(getattr(node, "camera_fov", None)) if node is not None else None
        if camera_fov is None or camera_fov <= 0.0:
            camera_fov = None
        camera_animation = _optional_int(getattr(node, "camera_anim", None)) if node is not None else None
        if camera_animation is not None and camera_animation < 0:
            camera_animation = None
        camera_height_offset = _optional_float(getattr(node, "camera_height", None)) if node is not None else None
        target_height_offset = _optional_float(getattr(node, "target_height", None)) if node is not None else None
        delay = int(getattr(node, "delay", -1)) if node is not None else -1
        text = _node_text(node, self.tlk_lookup) if node is not None and self._state == PIE_DIALOGUE_LISTENING else ""
        return MapStudioPIEDialogueSnapshot(
            state=self._state,
            game=self.game,
            conversation_resref=self.resref,
            owner_id=self.owner_id,
            listener_id=self.listener_id,
            current_node_id=self._node_id(node) if node is not None else "",
            current_node_kind="entry" if node is not None else "",
            speaker_tag=str(getattr(node, "speaker", "") or "") if node is not None else "",
            listener_tag=str(getattr(node, "listener", "") or "") if node is not None else "",
            text=text,
            sound_resref=_clean_resref(getattr(node, "sound", "")) if node is not None else "",
            voice_resref=_clean_resref(getattr(node, "vo_resref", "")) if node is not None else "",
            camera_angle=camera_angle,
            camera_id=camera_id,
            camera_animation=camera_animation,
            camera_fov=camera_fov,
            camera_height_offset=float(camera_height_offset or 0.0),
            target_height_offset=float(target_height_offset or 0.0),
            animations=animations,
            choices=self._choices,
            can_continue=self._state == PIE_DIALOGUE_LISTENING,
            can_abort=self.active,
            ended=self.ended,
            blocked=self._state == PIE_DIALOGUE_BLOCKED,
            skippable=bool(getattr(self._dialogue, "skippable", False)),
            node_unskippable=bool(getattr(node, "unskippable", False)) if node is not None else False,
            delay=delay,
            wait_flags=int(getattr(node, "wait_flags", 0) or 0) if node is not None else 0,
            line_interval_seconds=map_studio_pie_dialogue_line_interval(text, delay_milliseconds=delay),
            conversation_type=conversation_type,
            events=tuple(self._events),
            warnings=tuple(dict.fromkeys(self._warnings)),
        )


def inspect_map_studio_pie_dialogue_starters(
    dlg_bytes: bytes,
    *,
    game: str = "K2",
    resref: str = "",
    tlk_lookup: TLKLookup | None = None,
) -> tuple[MapStudioPIEDialogueStarterOption, ...]:
    """Inspect a real DLG's ordered starter nodes without starting playback."""

    return MapStudioPIEDialogueSession(
        dlg_bytes,
        game=game,
        resref=resref,
        tlk_lookup=tlk_lookup,
    ).starter_options()


def build_map_studio_pie_dialogue_catalog(
    source: Any,
    *,
    dialogue_loader: Callable[[str], bytes | None],
    game: str = "K2",
    tlk_lookup: TLKLookup | None = None,
    dialogue_source_label: Callable[[str], str] | None = None,
) -> tuple[MapStudioPIEDialogueConversationOption, ...]:
    """Build compact conversation choices from the loaded module resources."""

    entities = tuple(getattr(source, "entities", source) or ())
    owner_names_by_resref: dict[str, list[str]] = {}
    owner_ids_by_resref: dict[str, list[str]] = {}
    for entity in entities:
        resref = _clean_resref(getattr(entity, "conversation", ""))
        if not resref:
            continue
        owner_id = str(getattr(entity, "entity_id", "") or "").strip()
        name = str(
            getattr(entity, "display_name", "")
            or getattr(entity, "tag", "")
            or owner_id
            or resref
        ).strip()
        names = owner_names_by_resref.setdefault(resref, [])
        ids = owner_ids_by_resref.setdefault(resref, [])
        if name and name not in names:
            names.append(name)
        if owner_id and owner_id not in ids:
            ids.append(owner_id)

    catalog: list[MapStudioPIEDialogueConversationOption] = []
    for resref in sorted(owner_names_by_resref):
        try:
            payload = dialogue_loader(resref)
            if not payload:
                continue
            starters = inspect_map_studio_pie_dialogue_starters(
                payload,
                game=game,
                resref=resref,
                tlk_lookup=tlk_lookup,
            )
        except Exception:
            continue
        owner_names = tuple(owner_names_by_resref[resref])
        owner_ids = tuple(owner_ids_by_resref.get(resref, ()))
        owner_label = ", ".join(owner_names[:2])
        if len(owner_names) > 2:
            owner_label += f" +{len(owner_names) - 2}"
        display_name = owner_label or resref
        catalog.append(
            MapStudioPIEDialogueConversationOption(
                conversation_resref=resref,
                display_name=display_name,
                owner_ids=owner_ids,
                owner_names=owner_names,
                resource_sha256=hashlib.sha256(bytes(payload)).hexdigest(),
                source_label=(
                    str(dialogue_source_label(resref) or "").strip()
                    if dialogue_source_label is not None
                    else ""
                ),
                starters=starters,
            )
        )
    return tuple(catalog)


__all__ = [
    "PIE_DIALOGUE_BLOCKED",
    "PIE_DIALOGUE_CHOOSING",
    "PIE_DIALOGUE_ENDED",
    "PIE_DIALOGUE_LISTENING",
    "PIE_DIALOGUE_READY",
    "MapStudioPIEDialogueChoice",
    "MapStudioPIEDialogueAnimationPolicy",
    "MapStudioPIEDialogueConditionRequest",
    "MapStudioPIEDialogueConditionResult",
    "MapStudioPIEDialogueConditionTable",
    "MapStudioPIEDialogueConditionTruth",
    "MapStudioPIEDialogueContextEvaluator",
    "MapStudioPIEDialogueConversationOption",
    "MapStudioPIEDialogueEvent",
    "MapStudioPIEDialogueSession",
    "MapStudioPIEDialogueSnapshot",
    "MapStudioPIEDialogueStarterOption",
    "build_map_studio_pie_dialogue_catalog",
    "inspect_map_studio_pie_dialogue_starters",
    "load_map_studio_pie_dialogue_animation_policies",
    "map_studio_pie_dialogue_line_interval",
]
