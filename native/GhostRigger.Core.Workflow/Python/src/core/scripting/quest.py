"""Versioned quest authoring contracts and coordinated KOTOR scaffolds.

The editable quest document is deliberately independent of Qt and KOTOR file
writers.  It preserves fields that GhostStudio does not yet understand so an
older GhostScripter document, or a newer community extension, can be opened,
edited, and saved without silently discarding data.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from src.core.scripting.data_authoring import (
    GlobalVariableRecord,
    JournalEntryRecord,
    JournalQuestRecord,
    LocalizedText,
)


QUEST_DOCUMENT_FORMAT = "ghoststudio.quest"
QUEST_SCHEMA_VERSION = 1
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
_RESREF = re.compile(r"^[A-Za-z0-9_]{1,16}$")
_GLOBAL_TYPES = {"boolean": "Boolean", "number": "Number", "string": "String", "location": "Location"}


def _copy_json(value: Any) -> Any:
    """Return an isolated JSON-compatible value without sharing nested state."""

    return deepcopy(value)


def _first(row: Mapping[str, Any], names: Sequence[str], default: Any = None) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return default


def _extras(row: Mapping[str, Any], known: Iterable[str]) -> dict[str, Any]:
    consumed = set(known)
    return {str(key): _copy_json(value) for key, value in row.items() if key not in consumed}


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, memoryview)):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


def _normal_game(value: Any) -> str:
    text = str(value or "K2").strip().upper().replace(" ", "")
    if text in {"1", "K1", "KOTOR", "KOTOR1"}:
        return "K1"
    if text in {"2", "K2", "TSL", "KOTOR2"}:
        return "K2"
    return str(value or "K2").strip().upper()


def _normal_global_type(value: Any) -> str:
    text = str(value or "Boolean").strip()
    return _GLOBAL_TYPES.get(text.casefold(), text)


def _default_for_type(value_type: str) -> Any:
    return {"Boolean": False, "Number": 0, "String": "", "Location": {}}.get(value_type)


@dataclass(frozen=True)
class QuestDiagnostic:
    severity: str
    code: str
    message: str
    path: str = ""

    @property
    def blocking(self) -> bool:
        return self.severity.casefold() in {"blocking", "error"}


@dataclass
class QuestVariableDefinition:
    name: str
    value_type: str = "Boolean"
    default: Any = False
    description: str = ""
    extras: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "QuestVariableDefinition":
        row = dict(raw or {})
        names = ("name", "variable_name", "variableName", "id")
        types = ("value_type", "variable_type", "variableType", "type")
        defaults = ("default", "default_value", "defaultValue", "initial_value", "initialValue")
        descriptions = ("description", "comment", "notes")
        value_type = _normal_global_type(_first(row, types, "Boolean"))
        default = _first(row, defaults, _default_for_type(value_type))
        return cls(
            str(_first(row, names, "") or ""),
            value_type,
            _copy_json(default),
            str(_first(row, descriptions, "") or ""),
            _extras(row, (*names, *types, *defaults, *descriptions)),
        )

    def to_dict(self) -> dict[str, Any]:
        row = _copy_json(self.extras)
        row.update(
            {
                "name": self.name,
                "value_type": self.value_type,
                "default": _copy_json(self.default),
                "description": self.description,
            }
        )
        return row


@dataclass
class QuestStateDefinition:
    state_id: int
    name: str
    description: str = ""
    entry_dialogue: str = ""
    entry_script: str = ""
    spawned_npcs: tuple[str, ...] = ()
    spawned_placeables: tuple[str, ...] = ()
    objectives: tuple[str, ...] = ()
    end: bool = False
    extras: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "QuestStateDefinition":
        row = dict(raw or {})
        ids = ("state_id", "stateId", "id", "index")
        names = ("name", "state_name", "title", "display_name", "displayName")
        descriptions = ("description", "journal_text", "journalText", "text")
        dialogues = ("entry_dialogue", "entryDialogue", "dialogue", "dialogue_resref")
        scripts = ("entry_script", "entryScript", "script", "script_resref")
        npcs = ("spawned_npcs", "spawnedNPCs", "npcs")
        placeables = ("spawned_placeables", "spawnedPlaceables", "placeables")
        objectives = ("objectives", "available_objectives", "goals")
        endings = ("end", "is_end", "isEnd", "complete")
        try:
            state_id = int(_first(row, ids, 0))
        except (TypeError, ValueError):
            state_id = 0
        return cls(
            state_id,
            str(_first(row, names, f"State {state_id}") or f"State {state_id}"),
            str(_first(row, descriptions, "") or ""),
            str(_first(row, dialogues, "") or ""),
            str(_first(row, scripts, "") or ""),
            _string_tuple(_first(row, npcs, ())),
            _string_tuple(_first(row, placeables, ())),
            _string_tuple(_first(row, objectives, ())),
            bool(_first(row, endings, False)),
            _extras(
                row,
                (*ids, *names, *descriptions, *dialogues, *scripts, *npcs, *placeables, *objectives, *endings),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        row = _copy_json(self.extras)
        row.update(
            {
                "state_id": int(self.state_id),
                "name": self.name,
                "description": self.description,
                "entry_dialogue": self.entry_dialogue,
                "entry_script": self.entry_script,
                "spawned_npcs": list(self.spawned_npcs),
                "spawned_placeables": list(self.spawned_placeables),
                "objectives": list(self.objectives),
                "end": bool(self.end),
            }
        )
        return row


@dataclass
class QuestTriggerDefinition:
    trigger_type: str
    condition: str = ""
    target_state: int = 0
    action_script: str = ""
    extras: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "QuestTriggerDefinition":
        row = dict(raw or {})
        types = ("trigger_type", "triggerType", "type")
        conditions = ("condition", "expression", "when")
        states = ("target_state", "targetState", "state", "state_id")
        scripts = ("action_script", "actionScript", "script", "on_trigger")
        try:
            target_state = int(_first(row, states, 0))
        except (TypeError, ValueError):
            target_state = 0
        return cls(
            str(_first(row, types, "manual") or "manual"),
            str(_first(row, conditions, "") or ""),
            target_state,
            str(_first(row, scripts, "") or ""),
            _extras(row, (*types, *conditions, *states, *scripts)),
        )

    def to_dict(self) -> dict[str, Any]:
        row = _copy_json(self.extras)
        row.update(
            {
                "trigger_type": self.trigger_type,
                "condition": self.condition,
                "target_state": int(self.target_state),
                "action_script": self.action_script,
            }
        )
        return row


@dataclass
class QuestDefinition:
    quest_id: str
    name: str
    description: str = ""
    target_game: str = "K2"
    variables: tuple[QuestVariableDefinition, ...] = ()
    states: tuple[QuestStateDefinition, ...] = ()
    triggers: tuple[QuestTriggerDefinition, ...] = ()
    dialogues: tuple[str, ...] = ()
    scripts: tuple[str, ...] = ()
    quest_type: str = "side_quest"
    priority: int = 5
    repeatable: bool = False
    conflicts: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    schema_version: int = QUEST_SCHEMA_VERSION
    source_path: Path | None = field(default=None, repr=False, compare=False)
    extras: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "QuestDefinition":
        row = dict(raw or {})
        ids = ("quest_id", "questId", "id", "tag")
        names = ("name", "quest_name", "display_name", "displayName", "title")
        descriptions = ("description", "comment", "notes")
        games = ("target_game", "targetGame", "game")
        variables = ("variables", "globals", "global_variables", "globalVariables")
        states = ("states", "quest_states", "questStates")
        triggers = ("triggers", "quest_triggers", "questTriggers")
        dialogues = ("dialogues", "dialogue_files", "dialogueFiles")
        scripts = ("scripts", "script_files", "scriptFiles")
        quest_types = ("quest_type", "questType", "type")
        priorities = ("priority", "journal_priority", "journalPriority")
        repeatables = ("repeatable", "is_repeatable", "isRepeatable")
        conflicts = ("conflicts", "conflicts_with", "conflictsWith")
        dependencies = ("dependencies", "depends_on", "dependsOn")
        versions = ("schema_version", "schemaVersion", "version")
        formats = ("format", "document_format", "documentFormat")
        try:
            priority = int(_first(row, priorities, 5))
        except (TypeError, ValueError):
            priority = 5
        try:
            version = int(_first(row, versions, QUEST_SCHEMA_VERSION))
        except (TypeError, ValueError):
            version = QUEST_SCHEMA_VERSION
        raw_variables = _first(row, variables, ()) or ()
        raw_states = _first(row, states, ()) or ()
        raw_triggers = _first(row, triggers, ()) or ()
        if not isinstance(raw_variables, Sequence) or isinstance(raw_variables, (str, bytes, bytearray)):
            raw_variables = ()
        if not isinstance(raw_states, Sequence) or isinstance(raw_states, (str, bytes, bytearray)):
            raw_states = ()
        if not isinstance(raw_triggers, Sequence) or isinstance(raw_triggers, (str, bytes, bytearray)):
            raw_triggers = ()
        return cls(
            quest_id=str(_first(row, ids, "") or ""),
            name=str(_first(row, names, "") or ""),
            description=str(_first(row, descriptions, "") or ""),
            target_game=_normal_game(_first(row, games, "K2")),
            variables=tuple(QuestVariableDefinition.from_dict(item) for item in raw_variables if isinstance(item, Mapping)),
            states=tuple(QuestStateDefinition.from_dict(item) for item in raw_states if isinstance(item, Mapping)),
            triggers=tuple(QuestTriggerDefinition.from_dict(item) for item in raw_triggers if isinstance(item, Mapping)),
            dialogues=_string_tuple(_first(row, dialogues, ())),
            scripts=_string_tuple(_first(row, scripts, ())),
            quest_type=str(_first(row, quest_types, "side_quest") or "side_quest"),
            priority=priority,
            repeatable=bool(_first(row, repeatables, False)),
            conflicts=_string_tuple(_first(row, conflicts, ())),
            dependencies=_string_tuple(_first(row, dependencies, ())),
            schema_version=max(1, version),
            extras=_extras(
                row,
                (
                    *ids,
                    *names,
                    *descriptions,
                    *games,
                    *variables,
                    *states,
                    *triggers,
                    *dialogues,
                    *scripts,
                    *quest_types,
                    *priorities,
                    *repeatables,
                    *conflicts,
                    *dependencies,
                    *versions,
                    *formats,
                ),
            ),
        )

    @classmethod
    def from_json(cls, source: str | bytes | bytearray | memoryview) -> "QuestDefinition":
        text = bytes(source).decode("utf-8-sig") if not isinstance(source, str) else source
        raw = json.loads(text)
        if not isinstance(raw, Mapping):
            raise ValueError("A quest document must contain one JSON object.")
        return cls.from_dict(raw)

    @classmethod
    def load(cls, source: str | Path | bytes | bytearray | memoryview) -> "QuestDefinition":
        if isinstance(source, (bytes, bytearray, memoryview)):
            return cls.from_json(source)
        path = Path(source)
        document = cls.from_json(path.read_bytes())
        document.source_path = path.resolve()
        return document

    def to_dict(self) -> dict[str, Any]:
        row = _copy_json(self.extras)
        row.update(
            {
                "format": QUEST_DOCUMENT_FORMAT,
                "schema_version": int(self.schema_version),
                "quest_id": self.quest_id,
                "name": self.name,
                "description": self.description,
                "target_game": _normal_game(self.target_game),
                "quest_type": self.quest_type,
                "priority": int(self.priority),
                "repeatable": bool(self.repeatable),
                "variables": [item.to_dict() for item in self.variables],
                "states": [item.to_dict() for item in self.states],
                "triggers": [item.to_dict() for item in self.triggers],
                "dialogues": list(self.dialogues),
                "scripts": list(self.scripts),
                "conflicts": list(self.conflicts),
                "dependencies": list(self.dependencies),
            }
        )
        return row

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def save(self, target: str | Path | None = None) -> Path:
        path = Path(target) if target is not None else self.source_path
        if path is None:
            raise ValueError("Choose a quest document path before saving.")
        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(self.to_json())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
        self.source_path = path
        return path

    def validate(self) -> tuple[QuestDiagnostic, ...]:
        issues: list[QuestDiagnostic] = []
        if not _IDENTIFIER.fullmatch(self.quest_id):
            issues.append(
                QuestDiagnostic(
                    "blocking",
                    "quest.invalid_id",
                    "Quest ID must start with a letter and use at most 32 letters, numbers, or underscores.",
                    "quest_id",
                )
            )
        if not self.name.strip():
            issues.append(QuestDiagnostic("blocking", "quest.empty_name", "Quest name cannot be empty.", "name"))
        if _normal_game(self.target_game) not in {"K1", "K2"}:
            issues.append(QuestDiagnostic("blocking", "quest.invalid_game", "Target game must be K1 or K2.", "target_game"))
        if not self.quest_type.strip():
            issues.append(QuestDiagnostic("blocking", "quest.empty_type", "Quest type cannot be empty.", "quest_type"))
        if self.priority < 0 or self.priority > 5:
            issues.append(QuestDiagnostic("blocking", "quest.invalid_priority", "Journal priority must be between 0 and 5.", "priority"))
        if self.schema_version > QUEST_SCHEMA_VERSION:
            issues.append(
                QuestDiagnostic(
                    "warning",
                    "quest.newer_schema",
                    f"This quest uses schema {self.schema_version}; unknown fields will be retained.",
                    "schema_version",
                )
            )

        variable_names: set[str] = set()
        for index, variable in enumerate(self.variables):
            path = f"variables[{index}]"
            key = variable.name.casefold()
            if not variable.name.strip():
                issues.append(QuestDiagnostic("blocking", "quest.variable_empty", "Variable name cannot be empty.", f"{path}.name"))
            elif key in variable_names:
                issues.append(QuestDiagnostic("blocking", "quest.variable_duplicate", f"Duplicate variable: {variable.name}", f"{path}.name"))
            variable_names.add(key)
            normal_type = _normal_global_type(variable.value_type)
            if normal_type not in _GLOBAL_TYPES.values():
                issues.append(QuestDiagnostic("blocking", "quest.variable_type", "Variable type must be Boolean, Number, String, or Location.", f"{path}.value_type"))
            elif normal_type == "Boolean" and not isinstance(variable.default, bool):
                issues.append(QuestDiagnostic("blocking", "quest.variable_default", "Boolean defaults must be true or false.", f"{path}.default"))
            elif normal_type == "Number" and (not isinstance(variable.default, (int, float)) or isinstance(variable.default, bool)):
                issues.append(QuestDiagnostic("blocking", "quest.variable_default", "Number defaults must be numeric.", f"{path}.default"))
            elif normal_type == "String" and not isinstance(variable.default, str):
                issues.append(QuestDiagnostic("blocking", "quest.variable_default", "String defaults must be text.", f"{path}.default"))

        state_ids: set[int] = set()
        for index, state in enumerate(self.states):
            path = f"states[{index}]"
            if state.state_id in state_ids:
                issues.append(QuestDiagnostic("blocking", "quest.state_duplicate", f"Duplicate state ID: {state.state_id}", f"{path}.state_id"))
            state_ids.add(state.state_id)
            if not state.name.strip():
                issues.append(QuestDiagnostic("blocking", "quest.state_empty", "State name cannot be empty.", f"{path}.name"))
            for field_name, resref in (("entry_dialogue", state.entry_dialogue), ("entry_script", state.entry_script)):
                if resref and not _RESREF.fullmatch(resref):
                    issues.append(QuestDiagnostic("blocking", "quest.invalid_resref", f"Invalid KOTOR ResRef: {resref}", f"{path}.{field_name}"))
            for field_name, values in (("spawned_npcs", state.spawned_npcs), ("spawned_placeables", state.spawned_placeables)):
                for value_index, resref in enumerate(values):
                    if not _RESREF.fullmatch(resref):
                        issues.append(QuestDiagnostic("blocking", "quest.invalid_resref", f"Invalid KOTOR ResRef: {resref}", f"{path}.{field_name}[{value_index}]"))

        if not self.states:
            issues.append(QuestDiagnostic("blocking", "quest.no_states", "A quest must contain at least one state.", "states"))
        for index, trigger in enumerate(self.triggers):
            if not trigger.trigger_type.strip():
                issues.append(QuestDiagnostic("blocking", "quest.trigger_type", "Trigger type cannot be empty.", f"triggers[{index}].trigger_type"))
            if trigger.target_state not in state_ids:
                issues.append(QuestDiagnostic("blocking", "quest.trigger_state", f"Trigger targets missing state {trigger.target_state}.", f"triggers[{index}].target_state"))
            if trigger.action_script and not _RESREF.fullmatch(trigger.action_script):
                issues.append(QuestDiagnostic("blocking", "quest.invalid_resref", f"Invalid KOTOR ResRef: {trigger.action_script}", f"triggers[{index}].action_script"))
        for collection_name, values in (("dialogues", self.dialogues), ("scripts", self.scripts)):
            for index, value in enumerate(values):
                if not _RESREF.fullmatch(value):
                    issues.append(QuestDiagnostic("blocking", "quest.invalid_resref", f"Invalid KOTOR ResRef: {value}", f"{collection_name}[{index}]"))
        for collection_name, values in (("conflicts", self.conflicts), ("dependencies", self.dependencies)):
            lowered: set[str] = set()
            for index, value in enumerate(values):
                key = value.casefold()
                if not value.strip():
                    issues.append(QuestDiagnostic("blocking", "quest.empty_relation", "Quest relation cannot be empty.", f"{collection_name}[{index}]"))
                elif key == self.quest_id.casefold():
                    issues.append(QuestDiagnostic("blocking", "quest.self_relation", "A quest cannot depend on or conflict with itself.", f"{collection_name}[{index}]"))
                elif key in lowered:
                    issues.append(QuestDiagnostic("blocking", "quest.duplicate_relation", f"Duplicate quest relation: {value}", f"{collection_name}[{index}]"))
                lowered.add(key)
        return tuple(issues)


@dataclass(frozen=True)
class QuestStateTemplate:
    state_id: int
    key: str
    title: str
    journal_text: str
    end: bool = False


@dataclass(frozen=True)
class QuestScriptResource:
    resref: str
    source: str
    state_id: int
    state_key: str


@dataclass(frozen=True)
class QuestScaffoldResult:
    template: str
    quest_tag: str
    display_name: str
    global_flag: str
    global_state: str
    globals: tuple[GlobalVariableRecord, ...]
    journal_quest: JournalQuestRecord
    scripts: tuple[QuestScriptResource, ...]
    definition: QuestDefinition | None = None


_TEMPLATES: dict[str, tuple[QuestStateTemplate, ...]] = {
    "simple": (
        QuestStateTemplate(0, "not_started", "Not Started", "Quest has not been initiated."),
        QuestStateTemplate(1, "active", "Active", "Quest is in progress."),
        QuestStateTemplate(2, "complete", "Complete", "Quest is finished.", True),
    ),
    "branching": (
        QuestStateTemplate(0, "not_started", "Not Started", "Quest has not been initiated."),
        QuestStateTemplate(1, "active_light", "Active - Light Side Path", "The light-side path is active."),
        QuestStateTemplate(2, "active_dark", "Active - Dark Side Path", "The dark-side path is active."),
        QuestStateTemplate(3, "complete_light", "Complete - Light Side", "The quest ended on the light-side path.", True),
        QuestStateTemplate(4, "complete_dark", "Complete - Dark Side", "The quest ended on the dark-side path.", True),
    ),
    "companion": (
        QuestStateTemplate(0, "not_recruited", "Not Recruited", "The companion has not been recruited."),
        QuestStateTemplate(1, "recruited", "Recruited", "The companion has joined the party."),
        QuestStateTemplate(2, "active", "Companion Quest Active", "The companion quest is in progress."),
        QuestStateTemplate(3, "complete", "Companion Quest Complete", "The companion quest is complete.", True),
    ),
}


def _safe_resref(value: str) -> str:
    normal = re.sub(r"[^a-z0-9_]", "_", str(value or "").strip().lower()).strip("_") or "quest"
    if len(normal) <= 16:
        return normal
    digest = hashlib.sha1(normal.encode("utf-8")).hexdigest()[:5]
    return f"{normal[:10]}_{digest}"


def _global_name(prefix: str, quest_tag: str, suffix: str = "") -> str:
    tail = f"_{suffix}" if suffix else ""
    seed = re.sub(r"[^A-Z0-9_]", "_", f"{prefix}_{quest_tag}{tail}".upper()).strip("_")
    if len(seed) <= 32:
        return seed
    digest = hashlib.sha1(seed.encode("ascii", "ignore")).hexdigest()[:6].upper()
    return f"{seed[:25]}_{digest}"


class QuestScaffoldService:
    """Create/edit quest definitions and derive auditable JRL/globalcat/NSS parts."""

    @staticmethod
    def template_names() -> tuple[tuple[str, str], ...]:
        return (
            ("simple", "Simple Quest (3 states)"),
            ("branching", "Branching Quest — Light / Dark (5 states)"),
            ("companion", "NPC Companion Recruitment (4 states)"),
        )

    @staticmethod
    def states(template: str) -> tuple[QuestStateTemplate, ...]:
        key = str(template or "simple").strip().lower()
        if key not in _TEMPLATES:
            raise ValueError(f"Unknown quest template: {template}")
        return _TEMPLATES[key]

    @classmethod
    def definition(
        cls,
        *,
        quest_tag: str,
        display_name: str,
        prefix: str,
        template: str = "simple",
        target_game: str = "K2",
    ) -> QuestDefinition:
        tag = str(quest_tag or "").strip()
        author_prefix = str(prefix or "").strip()
        if not _IDENTIFIER.fullmatch(tag):
            raise ValueError("Quest IDs must start with a letter and use at most 32 letters, numbers, or underscores.")
        if not _IDENTIFIER.fullmatch(author_prefix):
            raise ValueError("Use a unique author prefix beginning with a letter (up to 32 characters).")
        key = str(template or "simple").strip().lower()
        states = cls.states(key)
        if key == "companion":
            variables = (
                QuestVariableDefinition(_global_name(author_prefix, tag, "RECRUITED"), "Boolean", False, "Has the NPC been recruited?"),
                QuestVariableDefinition(_global_name(author_prefix, tag, "QUEST"), "Number", 0, "Companion quest state."),
            )
        else:
            variables_list = [
                QuestVariableDefinition(_global_name(author_prefix, tag), "Boolean", False, "Is the quest active?"),
                QuestVariableDefinition(_global_name(author_prefix, tag, "STATE"), "Number", 0, "Quest progression state."),
            ]
            if key == "branching":
                variables_list.append(
                    QuestVariableDefinition(_global_name(author_prefix, tag, "CHOICE"), "Number", 0, "Player alignment choice (1=light, 2=dark).")
                )
            variables = tuple(variables_list)
        return QuestDefinition(
            quest_id=tag,
            name=str(display_name or tag).strip() or tag,
            description="",
            target_game=_normal_game(target_game),
            variables=variables,
            states=tuple(
                QuestStateDefinition(row.state_id, row.title, row.journal_text, end=row.end)
                for row in states
            ),
            quest_type={"simple": "side_quest", "branching": "branching_quest", "companion": "companion_quest"}[key],
            priority=5,
            extras={"template": key},
        )

    @classmethod
    def scaffold_definition(cls, definition: QuestDefinition) -> QuestScaffoldResult:
        blocking = [issue.message for issue in definition.validate() if issue.blocking]
        if blocking:
            raise ValueError("Quest definition is not scaffold-ready: " + "; ".join(blocking))
        globals_ = tuple(
            GlobalVariableRecord(index, str(index), variable.name, _normal_global_type(variable.value_type))
            for index, variable in enumerate(definition.variables)
        )
        journal = JournalQuestRecord(
            tag=definition.quest_id,
            name=LocalizedText.from_english(definition.name),
            comment=definition.description,
            priority=definition.priority,
            entries=tuple(
                JournalEntryRecord(
                    state.state_id,
                    LocalizedText.from_english(state.description or state.name),
                    state.end,
                    0.0,
                )
                for state in definition.states
            ),
        )
        boolean_global = next((item.name for item in definition.variables if _normal_global_type(item.value_type) == "Boolean"), "")
        number_global = next(
            (
                item.name
                for item in definition.variables
                if _normal_global_type(item.value_type) == "Number" and ("STATE" in item.name.upper() or "QUEST" in item.name.upper())
            ),
            next((item.name for item in definition.variables if _normal_global_type(item.value_type) == "Number"), ""),
        )
        scripts: list[QuestScriptResource] = []
        for state in definition.states:
            resref = _safe_resref(f"{definition.quest_id}_{state.state_id:02d}")
            lines = ["void main()", "{"]
            if boolean_global:
                lines.append(f'    SetGlobalBoolean("{boolean_global}", {"FALSE" if state.state_id == 0 else "TRUE"});')
            if number_global:
                lines.append(f'    SetGlobalNumber("{number_global}", {state.state_id});')
            lines.append(f'    AddJournalQuestEntry("{definition.quest_id}", {state.state_id}, {"TRUE" if state.end else "FALSE"});')
            if state.entry_script and state.entry_script.casefold() != resref.casefold():
                lines.append(f'    ExecuteScript("{state.entry_script}", OBJECT_SELF);')
            lines.extend(("}", ""))
            scripts.append(
                QuestScriptResource(
                    resref,
                    "\n".join(lines),
                    state.state_id,
                    re.sub(r"[^a-z0-9_]", "_", state.name.casefold()).strip("_") or f"state_{state.state_id}",
                )
            )
        template = str(definition.extras.get("template") or definition.quest_type or "custom")
        return QuestScaffoldResult(
            template,
            definition.quest_id,
            definition.name,
            boolean_global,
            number_global,
            globals_,
            journal,
            tuple(scripts),
            definition,
        )

    @classmethod
    def scaffold(
        cls,
        *,
        quest_tag: str,
        display_name: str,
        prefix: str,
        template: str = "simple",
        target_game: str = "K2",
    ) -> QuestScaffoldResult:
        return cls.scaffold_definition(
            cls.definition(
                quest_tag=quest_tag,
                display_name=display_name,
                prefix=prefix,
                template=template,
                target_game=target_game,
            )
        )


__all__ = [
    "QUEST_DOCUMENT_FORMAT",
    "QUEST_SCHEMA_VERSION",
    "QuestDefinition",
    "QuestDiagnostic",
    "QuestScaffoldResult",
    "QuestScaffoldService",
    "QuestScriptResource",
    "QuestStateDefinition",
    "QuestStateTemplate",
    "QuestTriggerDefinition",
    "QuestVariableDefinition",
]
