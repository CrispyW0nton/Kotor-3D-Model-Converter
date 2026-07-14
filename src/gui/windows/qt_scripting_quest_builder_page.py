"""Presentation-only editable Quest Builder for the integrated Scripting Suite."""

from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any, Mapping, Optional, Sequence

from PySide6 import QtCore, QtWidgets


QUEST_SOURCE_ROW_ROLE = int(QtCore.Qt.UserRole) + 392

_ROOT_LEGACY_ALIASES = (
    "questId",
    "id",
    "tag",
    "quest_name",
    "display_name",
    "displayName",
    "title",
    "comment",
    "notes",
    "targetGame",
    "game",
    "questType",
    "type",
    "journal_priority",
    "journalPriority",
    "is_repeatable",
    "isRepeatable",
    "globals",
    "global_variables",
    "globalVariables",
    "quest_states",
    "questStates",
    "quest_triggers",
    "questTriggers",
    "dialogue_files",
    "dialogueFiles",
    "script_files",
    "scriptFiles",
    "depends_on",
    "dependsOn",
    "conflicts_with",
    "conflictsWith",
    "schemaVersion",
    "version",
    "document_format",
    "documentFormat",
    "prefix",
)
_VARIABLE_LEGACY_ALIASES = (
    "variable_name",
    "variableName",
    "id",
    "variable_type",
    "variableType",
    "type",
    "default_value",
    "defaultValue",
    "initial_value",
    "initialValue",
    "comment",
    "notes",
)
_STATE_LEGACY_ALIASES = (
    "stateId",
    "id",
    "index",
    "state_name",
    "title",
    "display_name",
    "displayName",
    "journal_text",
    "journalText",
    "text",
    "entryDialogue",
    "dialogue",
    "dialogue_resref",
    "entryScript",
    "script",
    "script_resref",
    "spawnedNPCs",
    "npcs",
    "spawnedPlaceables",
    "placeables",
    "available_objectives",
    "goals",
    "is_end",
    "isEnd",
    "complete",
)
_TRIGGER_LEGACY_ALIASES = (
    "triggerType",
    "type",
    "expression",
    "when",
    "targetState",
    "state",
    "state_id",
    "actionScript",
    "script",
    "on_trigger",
)


def _first(row: Mapping[str, Any], *names: str, default: Any = "") -> Any:
    for name in names:
        if name in row:
            return row[name]
    return default


def _string_rows(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[\n,;]+", value) if part.strip()]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, memoryview)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _parse_default(text: str, value_type: str) -> Any:
    value = str(text or "").strip()
    kind = str(value_type or "Boolean").casefold()
    if kind == "boolean":
        return value.casefold() in {"1", "true", "yes", "on"}
    if kind == "number":
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value
    if kind == "location" and value:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _default_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return "" if value is None else str(value)


class QtQuestScaffoldPage(QtWidgets.QWidget):
    """Edit a loss-preserving quest document and derive KOTOR resources."""

    newRequested = QtCore.Signal()
    openRequested = QtCore.Signal()
    saveRequested = QtCore.Signal()
    saveAsRequested = QtCore.Signal()
    templateRequested = QtCore.Signal(str)
    validateRequested = QtCore.Signal(object)
    previewRequested = QtCore.Signal(object)
    commitRequested = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("scriptingStudioQuestScaffoldPage")
        self.setProperty("ghostLayoutId", "scriptingStudioQuestScaffold")
        self._has_preview = False
        self._loading = False
        self._dirty = False
        self._source_name = "Unsaved quest"
        self._base_payload: dict[str, Any] = {}

        outer = QtWidgets.QVBoxLayout(self)
        margin = self.style().pixelMetric(QtWidgets.QStyle.PM_LayoutLeftMargin, None, self)
        spacing = self.style().pixelMetric(QtWidgets.QStyle.PM_LayoutVerticalSpacing, None, self)
        outer.setContentsMargins(margin, margin, margin, margin)
        outer.setSpacing(max(0, spacing))

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Quest Builder", self)
        title.setObjectName("scriptingStudioQuestScaffoldHeading")
        title.setProperty("headingLevel", 1)
        header.addWidget(title)
        self.source_label = QtWidgets.QLabel(self._source_name, self)
        self.source_label.setObjectName("scriptingStudioQuestSourceLabel")
        self.source_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        header.addWidget(self.source_label, 1)
        outer.addLayout(header)

        guidance = QtWidgets.QLabel(
            "Design the complete quest here, then preview the journal, globalcat.2da, and NWScript resources before adding them to the workbench.",
            self,
        )
        guidance.setObjectName("scriptingStudioQuestGuidance")
        guidance.setWordWrap(True)
        outer.addWidget(guidance)

        toolbar = QtWidgets.QHBoxLayout()
        self.new_button = self._button("New", "scriptingStudioQuestNewButton")
        self.open_button = self._button("Open…", "scriptingStudioQuestOpenButton")
        self.save_button = self._button("Save", "scriptingStudioQuestSaveButton")
        self.save_as_button = self._button("Save As…", "scriptingStudioQuestSaveAsButton")
        for button in (self.new_button, self.open_button, self.save_button, self.save_as_button):
            toolbar.addWidget(button)
        toolbar.addSpacing(max(0, spacing))
        self.template_combo = QtWidgets.QComboBox(self)
        self.template_combo.setObjectName("scriptingStudioQuestTemplateCombo")
        self.load_template_button = self._button("Load Template", "scriptingStudioQuestLoadTemplateButton")
        toolbar.addWidget(self.template_combo)
        toolbar.addWidget(self.load_template_button)
        toolbar.addStretch(1)
        self.validate_button = self._button("Validate", "scriptingStudioQuestValidateButton")
        self.preview_button = self._button("Generate Preview", "scriptingStudioQuestPreviewButton")
        self.commit_button = self._button("Add to Workbench", "scriptingStudioQuestCommitButton")
        self.commit_button.setEnabled(False)
        toolbar.addWidget(self.validate_button)
        toolbar.addWidget(self.preview_button)
        toolbar.addWidget(self.commit_button)
        outer.addLayout(toolbar)

        self.tabs = QtWidgets.QTabWidget(self)
        self.tabs.setObjectName("scriptingStudioQuestEditorTabs")
        self.tabs.addTab(self._build_overview(), "Overview")
        self.tabs.addTab(self._build_variables(), "Variables")
        self.tabs.addTab(self._build_states(), "States")
        self.tabs.addTab(self._build_triggers(), "Triggers")
        self.tabs.addTab(self._build_preview(), "Build Preview")
        outer.addWidget(self.tabs, 1)

        self.status_label = QtWidgets.QLabel("Create a quest or open a preserved GhostScripter quest JSON document.", self)
        self.status_label.setObjectName("scriptingStudioQuestScaffoldStatus")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)

        self.new_button.clicked.connect(self.newRequested.emit)
        self.open_button.clicked.connect(self.openRequested.emit)
        self.save_button.clicked.connect(self.saveRequested.emit)
        self.save_as_button.clicked.connect(self.saveAsRequested.emit)
        self.load_template_button.clicked.connect(
            lambda: self.templateRequested.emit(str(self.template_combo.currentData() or "simple"))
        )
        self.validate_button.clicked.connect(lambda: self.validateRequested.emit(self.definition_payload()))
        self.preview_button.clicked.connect(lambda: self.previewRequested.emit(self.definition_payload()))
        self.commit_button.clicked.connect(self.commitRequested.emit)
        self._connect_dirty_signals()

    def _button(self, label: str, object_name: str) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(label, self)
        button.setObjectName(object_name)
        return button

    def _build_overview(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(self)
        page.setObjectName("scriptingStudioQuestOverviewPage")
        form = QtWidgets.QFormLayout(page)
        self.quest_id_edit = QtWidgets.QLineEdit(page)
        self.quest_id_edit.setObjectName("scriptingStudioQuestIdEdit")
        self.quest_id_edit.setPlaceholderText("lost_holocron")
        self.name_edit = QtWidgets.QLineEdit(page)
        self.name_edit.setObjectName("scriptingStudioQuestNameEdit")
        self.name_edit.setPlaceholderText("The Lost Holocron")
        self.prefix_edit = QtWidgets.QLineEdit(page)
        self.prefix_edit.setObjectName("scriptingStudioQuestPrefixEdit")
        self.prefix_edit.setPlaceholderText("my_mod")
        self.description_edit = QtWidgets.QPlainTextEdit(page)
        self.description_edit.setObjectName("scriptingStudioQuestDescriptionEdit")
        self.description_edit.setPlaceholderText("Purpose, story context, and implementation notes")
        self.target_game_combo = QtWidgets.QComboBox(page)
        self.target_game_combo.setObjectName("scriptingStudioQuestTargetGameCombo")
        self.target_game_combo.addItem("KOTOR 1", "K1")
        self.target_game_combo.addItem("KOTOR 2", "K2")
        self.quest_type_edit = QtWidgets.QLineEdit(page)
        self.quest_type_edit.setObjectName("scriptingStudioQuestTypeEdit")
        self.quest_type_edit.setPlaceholderText("side_quest")
        self.priority_spin = QtWidgets.QSpinBox(page)
        self.priority_spin.setObjectName("scriptingStudioQuestPrioritySpin")
        self.priority_spin.setRange(0, 5)
        self.repeatable_check = QtWidgets.QCheckBox("Can be repeated", page)
        self.repeatable_check.setObjectName("scriptingStudioQuestRepeatableCheck")
        self.dialogues_edit = self._list_editor(page, "scriptingStudioQuestDialoguesEdit", "One DLG ResRef per line")
        self.scripts_edit = self._list_editor(page, "scriptingStudioQuestScriptsEdit", "One NSS/NCS ResRef per line")
        self.dependencies_edit = self._list_editor(page, "scriptingStudioQuestDependenciesEdit", "Quest IDs required first")
        self.conflicts_edit = self._list_editor(page, "scriptingStudioQuestConflictsEdit", "Mutually exclusive quest IDs")
        form.addRow("Quest ID / journal tag", self.quest_id_edit)
        form.addRow("Display name", self.name_edit)
        form.addRow("Author prefix", self.prefix_edit)
        form.addRow("Description", self.description_edit)
        form.addRow("Target game", self.target_game_combo)
        form.addRow("Quest type", self.quest_type_edit)
        form.addRow("Journal priority", self.priority_spin)
        form.addRow("Runtime", self.repeatable_check)
        form.addRow("Dialogue resources", self.dialogues_edit)
        form.addRow("Script resources", self.scripts_edit)
        form.addRow("Dependencies", self.dependencies_edit)
        form.addRow("Conflicts", self.conflicts_edit)
        return page

    @staticmethod
    def _list_editor(parent: QtWidgets.QWidget, object_name: str, placeholder: str) -> QtWidgets.QPlainTextEdit:
        editor = QtWidgets.QPlainTextEdit(parent)
        editor.setObjectName(object_name)
        editor.setPlaceholderText(placeholder)
        editor.setTabChangesFocus(True)
        return editor

    def _table_page(
        self,
        object_name: str,
        headers: Sequence[str],
        add_label: str,
        add_slot: Any,
        remove_slot: Any,
    ) -> tuple[QtWidgets.QWidget, QtWidgets.QTableWidget]:
        page = QtWidgets.QWidget(self)
        page.setObjectName(object_name)
        layout = QtWidgets.QVBoxLayout(page)
        actions = QtWidgets.QHBoxLayout()
        add_button = self._button(add_label, f"{object_name}AddButton")
        remove_button = self._button("Remove Selected", f"{object_name}RemoveButton")
        actions.addWidget(add_button)
        actions.addWidget(remove_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        table = QtWidgets.QTableWidget(0, len(headers), page)
        table.setObjectName(f"{object_name}Table")
        table.setHorizontalHeaderLabels(list(headers))
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table, 1)
        add_button.clicked.connect(add_slot)
        remove_button.clicked.connect(remove_slot)
        return page, table

    def _build_variables(self) -> QtWidgets.QWidget:
        page, self.variables_table = self._table_page(
            "scriptingStudioQuestVariablesPage",
            ("Name", "Type", "Default", "Description"),
            "Add Variable",
            self._add_variable,
            lambda: self._remove_rows(self.variables_table),
        )
        return page

    def _build_states(self) -> QtWidgets.QWidget:
        page, self.states_table = self._table_page(
            "scriptingStudioQuestStatesPage",
            (
                "ID",
                "Name",
                "Description / journal text",
                "Entry dialogue",
                "Entry script",
                "Spawned NPCs",
                "Spawned placeables",
                "Objectives",
                "End",
            ),
            "Add State",
            self._add_state,
            lambda: self._remove_rows(self.states_table),
        )
        return page

    def _build_triggers(self) -> QtWidgets.QWidget:
        page, self.triggers_table = self._table_page(
            "scriptingStudioQuestTriggersPage",
            ("Type", "Condition", "Target state", "Action script"),
            "Add Trigger",
            self._add_trigger,
            lambda: self._remove_rows(self.triggers_table),
        )
        return page

    def _build_preview(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(self)
        page.setObjectName("scriptingStudioQuestPreviewPage")
        layout = QtWidgets.QVBoxLayout(page)
        self.preview_tree = QtWidgets.QTreeWidget(page)
        self.preview_tree.setObjectName("scriptingStudioQuestPreviewTree")
        self.preview_tree.setHeaderLabels(["Resource", "Purpose", "Generated value"])
        self.preview_tree.setAlternatingRowColors(True)
        self.preview_tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.preview_tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.preview_tree.header().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.preview_tree, 1)
        return page

    def _connect_dirty_signals(self) -> None:
        for edit in (
            self.quest_id_edit,
            self.name_edit,
            self.prefix_edit,
            self.quest_type_edit,
        ):
            edit.textChanged.connect(self._mark_dirty)
        for edit in (
            self.description_edit,
            self.dialogues_edit,
            self.scripts_edit,
            self.dependencies_edit,
            self.conflicts_edit,
        ):
            edit.textChanged.connect(self._mark_dirty)
        self.target_game_combo.currentIndexChanged.connect(self._mark_dirty)
        self.priority_spin.valueChanged.connect(self._mark_dirty)
        self.repeatable_check.toggled.connect(self._mark_dirty)
        self.variables_table.itemChanged.connect(self._mark_dirty)
        self.states_table.itemChanged.connect(self._mark_dirty)
        self.triggers_table.itemChanged.connect(self._mark_dirty)

    @QtCore.Slot()
    def _mark_dirty(self, *_args: Any) -> None:
        if self._loading:
            return
        self._dirty = True
        self._has_preview = False
        self.commit_button.setEnabled(False)
        self._update_source_label()

    def _update_source_label(self) -> None:
        self.source_label.setText(f"{self._source_name}{' *' if self._dirty else ''}")

    @staticmethod
    def _set_row(
        table: QtWidgets.QTableWidget,
        values: Sequence[Any],
        *,
        source: Mapping[str, Any] | None = None,
    ) -> None:
        row = table.rowCount()
        table.insertRow(row)
        for column, value in enumerate(values):
            item = QtWidgets.QTableWidgetItem(str(value))
            if column == 0 and source is not None:
                # The source record is the row's preservation identity.  It
                # moves with the QTableWidgetItem when rows are sorted or
                # reordered and disappears with that row when it is deleted.
                item.setData(QUEST_SOURCE_ROW_ROLE, deepcopy(dict(source)))
            table.setItem(row, column, item)

    def _add_variable(self) -> None:
        self._set_row(self.variables_table, ("NEW_GLOBAL", "Boolean", "false", ""))
        self._mark_dirty()

    def _add_state(self) -> None:
        ids = []
        for row in range(self.states_table.rowCount()):
            try:
                ids.append(int(self._cell(self.states_table, row, 0)))
            except ValueError:
                continue
        self._set_row(self.states_table, (max(ids, default=-1) + 1, "New State", "", "", "", "", "", "", "false"))
        self._mark_dirty()

    def _add_trigger(self) -> None:
        first_state = self._cell(self.states_table, 0, 0) if self.states_table.rowCount() else "0"
        self._set_row(self.triggers_table, ("manual", "", first_state, ""))
        self._mark_dirty()

    def _remove_rows(self, table: QtWidgets.QTableWidget) -> None:
        rows = sorted({index.row() for index in table.selectionModel().selectedRows()}, reverse=True)
        for row in rows:
            table.removeRow(row)
        if rows:
            self._mark_dirty()

    @staticmethod
    def _cell(table: QtWidgets.QTableWidget, row: int, column: int) -> str:
        item = table.item(row, column)
        return item.text().strip() if item is not None else ""

    @staticmethod
    def _source_row(table: QtWidgets.QTableWidget, row: int) -> dict[str, Any]:
        item = table.item(row, 0)
        source = item.data(QUEST_SOURCE_ROW_ROLE) if item is not None else None
        return deepcopy(dict(source)) if isinstance(source, Mapping) else {}

    @staticmethod
    def _merge_row(
        source: Mapping[str, Any],
        updates: Mapping[str, Any],
        legacy_aliases: Sequence[str],
    ) -> dict[str, Any]:
        base = deepcopy(dict(source))
        for alias in legacy_aliases:
            base.pop(alias, None)
        base.update(deepcopy(dict(updates)))
        return base

    def definition_payload(self) -> dict[str, Any]:
        payload = deepcopy(self._base_payload)
        for alias in _ROOT_LEGACY_ALIASES:
            payload.pop(alias, None)
        variables = []
        for row in range(self.variables_table.rowCount()):
            variables.append(
                self._merge_row(
                    self._source_row(self.variables_table, row),
                    {
                        "name": self._cell(self.variables_table, row, 0),
                        "value_type": self._cell(self.variables_table, row, 1) or "Boolean",
                        "default": _parse_default(
                            self._cell(self.variables_table, row, 2),
                            self._cell(self.variables_table, row, 1),
                        ),
                        "description": self._cell(self.variables_table, row, 3),
                    },
                    _VARIABLE_LEGACY_ALIASES,
                )
            )
        states = []
        for row in range(self.states_table.rowCount()):
            try:
                state_id = int(self._cell(self.states_table, row, 0))
            except ValueError:
                state_id = 0
            states.append(
                self._merge_row(
                    self._source_row(self.states_table, row),
                    {
                        "state_id": state_id,
                        "name": self._cell(self.states_table, row, 1),
                        "description": self._cell(self.states_table, row, 2),
                        "entry_dialogue": self._cell(self.states_table, row, 3),
                        "entry_script": self._cell(self.states_table, row, 4),
                        "spawned_npcs": _string_rows(self._cell(self.states_table, row, 5)),
                        "spawned_placeables": _string_rows(self._cell(self.states_table, row, 6)),
                        "objectives": _string_rows(self._cell(self.states_table, row, 7)),
                        "end": self._cell(self.states_table, row, 8).casefold() in {"1", "true", "yes", "on"},
                    },
                    _STATE_LEGACY_ALIASES,
                )
            )
        triggers = []
        for row in range(self.triggers_table.rowCount()):
            try:
                target_state = int(self._cell(self.triggers_table, row, 2))
            except ValueError:
                target_state = 0
            triggers.append(
                self._merge_row(
                    self._source_row(self.triggers_table, row),
                    {
                        "trigger_type": self._cell(self.triggers_table, row, 0),
                        "condition": self._cell(self.triggers_table, row, 1),
                        "target_state": target_state,
                        "action_script": self._cell(self.triggers_table, row, 3),
                    },
                    _TRIGGER_LEGACY_ALIASES,
                )
            )
        payload.update(
            {
                "format": "ghoststudio.quest",
                "schema_version": int(payload.get("schema_version", 1) or 1),
                "quest_id": self.quest_id_edit.text().strip(),
                "name": self.name_edit.text().strip(),
                "description": self.description_edit.toPlainText(),
                "target_game": str(self.target_game_combo.currentData() or "K2"),
                "quest_type": self.quest_type_edit.text().strip() or "side_quest",
                "priority": self.priority_spin.value(),
                "repeatable": self.repeatable_check.isChecked(),
                "variables": variables,
                "states": states,
                "triggers": triggers,
                "dialogues": _string_rows(self.dialogues_edit.toPlainText()),
                "scripts": _string_rows(self.scripts_edit.toPlainText()),
                "dependencies": _string_rows(self.dependencies_edit.toPlainText()),
                "conflicts": _string_rows(self.conflicts_edit.toPlainText()),
                "author_prefix": self.prefix_edit.text().strip(),
            }
        )
        return payload

    def set_templates(self, rows: Sequence[Sequence[str]]) -> None:
        current = str(self.template_combo.currentData() or "")
        self.template_combo.clear()
        for row in rows:
            if len(row) >= 2:
                self.template_combo.addItem(str(row[1]), str(row[0]))
        index = self.template_combo.findData(current)
        if index >= 0:
            self.template_combo.setCurrentIndex(index)

    def set_definition(self, raw: Mapping[str, Any], *, source_name: str = "", dirty: bool = False) -> None:
        data = deepcopy(dict(raw or {}))
        self._loading = True
        try:
            self._base_payload = data
            self.quest_id_edit.setText(str(_first(data, "quest_id", "questId", "id", "tag", default="") or ""))
            self.name_edit.setText(
                str(_first(data, "name", "quest_name", "display_name", "displayName", "title", default="") or "")
            )
            self.prefix_edit.setText(str(_first(data, "author_prefix", "prefix", default="") or ""))
            self.description_edit.setPlainText(str(_first(data, "description", "comment", "notes", default="") or ""))
            game = str(_first(data, "target_game", "targetGame", "game", default="K2") or "K2").upper()
            game = "K1" if game in {"1", "KOTOR", "KOTOR1"} else "K2" if game in {"2", "TSL", "KOTOR2"} else game
            game_index = self.target_game_combo.findData(game)
            self.target_game_combo.setCurrentIndex(game_index if game_index >= 0 else 1)
            self.quest_type_edit.setText(str(_first(data, "quest_type", "questType", "type", default="side_quest") or "side_quest"))
            try:
                self.priority_spin.setValue(int(_first(data, "priority", "journal_priority", default=5)))
            except (TypeError, ValueError):
                self.priority_spin.setValue(5)
            self.repeatable_check.setChecked(bool(_first(data, "repeatable", "is_repeatable", default=False)))
            self.dialogues_edit.setPlainText("\n".join(_string_rows(_first(data, "dialogues", "dialogue_files", default=[]))))
            self.scripts_edit.setPlainText("\n".join(_string_rows(_first(data, "scripts", "script_files", default=[]))))
            self.dependencies_edit.setPlainText("\n".join(_string_rows(_first(data, "dependencies", "depends_on", default=[]))))
            self.conflicts_edit.setPlainText("\n".join(_string_rows(_first(data, "conflicts", "conflicts_with", default=[]))))

            self.variables_table.setRowCount(0)
            for source in _first(data, "variables", "globals", "global_variables", default=[]) or []:
                row = dict(source) if isinstance(source, Mapping) else {}
                self._set_row(
                    self.variables_table,
                    (
                        _first(row, "name", "variable_name", "id", default=""),
                        _first(row, "value_type", "variable_type", "type", default="Boolean"),
                        _default_text(_first(row, "default", "default_value", default=False)),
                        _first(row, "description", "comment", default=""),
                    ),
                    source=row,
                )
            self.states_table.setRowCount(0)
            for source in _first(data, "states", "quest_states", default=[]) or []:
                row = dict(source) if isinstance(source, Mapping) else {}
                self._set_row(
                    self.states_table,
                    (
                        _first(row, "state_id", "id", "index", default=0),
                        _first(row, "name", "state_name", "title", "display_name", "displayName", default=""),
                        _first(row, "description", "journal_text", "text", default=""),
                        _first(row, "entry_dialogue", "dialogue", default=""),
                        _first(row, "entry_script", "script", default=""),
                        "; ".join(_string_rows(_first(row, "spawned_npcs", "npcs", default=[]))),
                        "; ".join(_string_rows(_first(row, "spawned_placeables", "placeables", default=[]))),
                        "; ".join(
                            _string_rows(_first(row, "objectives", "available_objectives", "goals", default=[]))
                        ),
                        "true" if bool(_first(row, "end", "is_end", "complete", default=False)) else "false",
                    ),
                    source=row,
                )
            self.triggers_table.setRowCount(0)
            for source in _first(data, "triggers", "quest_triggers", default=[]) or []:
                row = dict(source) if isinstance(source, Mapping) else {}
                self._set_row(
                    self.triggers_table,
                    (
                        _first(row, "trigger_type", "type", default="manual"),
                        _first(row, "condition", "expression", default=""),
                        _first(row, "target_state", "state", "state_id", default=0),
                        _first(row, "action_script", "script", default=""),
                    ),
                    source=row,
                )
            self.preview_tree.clear()
            self._has_preview = False
            self.commit_button.setEnabled(False)
            self._source_name = source_name or "Unsaved quest"
            self._dirty = bool(dirty)
            self._update_source_label()
        finally:
            self._loading = False

    def set_preview(self, row: Mapping[str, Any]) -> None:
        data = dict(row or {})
        self.preview_tree.clear()
        quest = QtWidgets.QTreeWidgetItem(
            [str(data.get("quest_tag") or "quest"), "Journal category", str(data.get("display_name") or "")]
        )
        for state in data.get("states", ()) or ():
            item = dict(state)
            quest.addChild(
                QtWidgets.QTreeWidgetItem(
                    [str(item.get("state_id", 0)), "Journal state", str(item.get("journal_text") or item.get("description") or "")]
                )
            )
        self.preview_tree.addTopLevelItem(quest)
        globals_root = QtWidgets.QTreeWidgetItem(["globalcat.2da", "Runtime globals", ""])
        for variable in data.get("globals", ()) or ():
            item = dict(variable)
            globals_root.addChild(
                QtWidgets.QTreeWidgetItem(
                    [str(item.get("name") or ""), str(item.get("value_type") or "Global"), "Registered"]
                )
            )
        self.preview_tree.addTopLevelItem(globals_root)
        scripts_root = QtWidgets.QTreeWidgetItem(["NWScript", "Quest state handlers", ""])
        for script in data.get("scripts", ()) or ():
            item = dict(script)
            scripts_root.addChild(
                QtWidgets.QTreeWidgetItem(
                    [f"{item.get('resref', '')}.nss", str(item.get("state_key") or "State"), str(item.get("state_id", 0))]
                )
            )
        self.preview_tree.addTopLevelItem(scripts_root)
        self.preview_tree.expandAll()
        self.tabs.setCurrentWidget(self.preview_tree.parentWidget())
        self._has_preview = bool(data)
        self.commit_button.setEnabled(self._has_preview)
        self.set_status(
            str(data.get("summary") or "Preview ready. Review every generated resource before adding it to the workbench.")
        )

    def set_validation(self, rows: Sequence[Mapping[str, Any] | object]) -> None:
        issues = tuple(rows or ())
        blocking = 0
        messages = []
        for issue in issues:
            severity = str(issue.get("severity", "") if isinstance(issue, Mapping) else getattr(issue, "severity", ""))
            message = str(issue.get("message", "") if isinstance(issue, Mapping) else getattr(issue, "message", issue))
            if severity.casefold() in {"blocking", "error"}:
                blocking += 1
            if message:
                messages.append(message)
        if not issues:
            self.set_status("Quest definition is structurally ready for preview.")
        else:
            self.set_status(
                f"{blocking} blocking issue(s), {len(issues) - blocking} warning(s): " + "; ".join(messages[:3]),
                error=blocking > 0,
            )

    def mark_saved(self, source_name: str) -> None:
        self._source_name = str(source_name or self._source_name)
        self._dirty = False
        self._base_payload = self.definition_payload()
        self._update_source_label()

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status_label.setText(str(message or ""))
        self.status_label.setProperty("validationState", "error" if error else "info")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def apply_ghost_theme(self, _theme: Any) -> None:
        self.setPalette(QtWidgets.QApplication.palette())
        self.update()

    def apply_ghost_layout(self, layout: Any) -> None:
        spacing_value = getattr(layout, "spacing_value", None)
        if callable(spacing_value) and self.layout() is not None:
            self.layout().setSpacing(int(spacing_value("panelSpacing", 8)))


__all__ = ["QtQuestScaffoldPage"]
