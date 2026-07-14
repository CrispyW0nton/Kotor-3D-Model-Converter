"""Presentation-only pages for GhostStudio narrative data authoring.

The widgets in this module expose user intent through Qt signals and accept
immutable presentation snapshots through ``set_*`` methods.  They do not open
files, parse KOTOR resources, or mutate domain documents; those responsibilities
remain with the Scripting Suite controller and core services.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any, Optional

from PySide6 import QtCore, QtGui, QtWidgets


SOURCE_ROW_ROLE = int(QtCore.Qt.UserRole) + 341
ITEM_KIND_ROLE = SOURCE_ROW_ROLE + 1
QUEST_INDEX_ROLE = SOURCE_ROW_ROLE + 2
ENTRY_INDEX_ROLE = SOURCE_ROW_ROLE + 3
RECORD_ROLE = SOURCE_ROW_ROLE + 4


def _field(record: object, name: str, default: object = "") -> object:
    if isinstance(record, Mapping):
        return record.get(name, default)
    return getattr(record, name, default)


def _localized_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    english = getattr(value, "english", None)
    if english is not None:
        return str(english)
    if isinstance(value, Mapping):
        if "english" in value:
            return str(value.get("english", ""))
        substrings = value.get("substrings", ())
        if isinstance(substrings, Mapping):
            return str(substrings.get(0, substrings.get("0", next(iter(substrings.values()), ""))))
    return str(value)


def _repolish(widget: QtWidgets.QWidget) -> None:
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()


class _NarrativeDataPage(QtWidgets.QWidget):
    """Shared theme/layout/status shell without domain behavior."""

    def __init__(self, object_name: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self._busy_widgets: list[QtWidgets.QWidget] = []
        self.root_layout = QtWidgets.QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.status_label = QtWidgets.QLabel("Ready", self)
        self.status_label.setObjectName(f"{object_name}Status")
        self.status_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

    def _register_busy_widgets(self, *widgets: QtWidgets.QWidget) -> None:
        self._busy_widgets.extend(widgets)

    def _finish_layout(self) -> None:
        self.root_layout.addWidget(self.status_label)

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status_label.setText(str(message or "Ready"))
        self.status_label.setProperty("status", "error" if error else "normal")
        _repolish(self.status_label)

    def set_busy(self, busy: bool, message: str = "Working…") -> None:
        for widget in self._busy_widgets:
            widget.setEnabled(not busy)
        if busy:
            self.set_status(message)

    def apply_ghost_theme(self, theme: Any) -> None:
        name = getattr(theme, "name", None) or getattr(theme, "id", None) or str(theme or "")
        self.setProperty("ghostTheme", name)
        _repolish(self)

    def apply_ghost_layout(self, layout: Any) -> None:
        name = getattr(layout, "name", None) or getattr(layout, "id", None) or str(layout or "")
        self.setProperty("ghostLayout", name)
        self.updateGeometry()


class QuestJournalPage(_NarrativeDataPage):
    """Quest/category tree and entry inspector for JRL authoring."""

    openRequested = QtCore.Signal()
    saveRequested = QtCore.Signal()
    validateRequested = QtCore.Signal()
    searchRequested = QtCore.Signal(str)
    addQuestRequested = QtCore.Signal(object)
    removeQuestRequested = QtCore.Signal(int)
    editQuestRequested = QtCore.Signal(int, object)
    addEntryRequested = QtCore.Signal(int, object)
    removeEntryRequested = QtCore.Signal(int, int)
    editEntryRequested = QtCore.Signal(int, int, object)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("scriptingStudioQuestJournalPage", parent)

        command_row = QtWidgets.QHBoxLayout()
        self.open_button = QtWidgets.QPushButton("Open JRL…", self)
        self.open_button.setObjectName("scriptingStudioJournalOpen")
        self.save_button = QtWidgets.QPushButton("Save JRL", self)
        self.save_button.setObjectName("scriptingStudioJournalSave")
        self.validate_button = QtWidgets.QPushButton("Validate", self)
        self.validate_button.setObjectName("scriptingStudioJournalValidate")
        self.add_quest_button = QtWidgets.QPushButton("+ Quest", self)
        self.add_quest_button.setObjectName("scriptingStudioJournalAddQuest")
        self.remove_quest_button = QtWidgets.QPushButton("− Quest", self)
        self.remove_quest_button.setObjectName("scriptingStudioJournalRemoveQuest")
        self.add_entry_button = QtWidgets.QPushButton("+ Entry", self)
        self.add_entry_button.setObjectName("scriptingStudioJournalAddEntry")
        self.remove_entry_button = QtWidgets.QPushButton("− Entry", self)
        self.remove_entry_button.setObjectName("scriptingStudioJournalRemoveEntry")
        self.search_edit = QtWidgets.QLineEdit(self)
        self.search_edit.setObjectName("scriptingStudioJournalSearch")
        self.search_edit.setPlaceholderText("Filter quests, tags, and journal text…")
        for widget in (
            self.open_button,
            self.save_button,
            self.validate_button,
            self.add_quest_button,
            self.remove_quest_button,
            self.add_entry_button,
            self.remove_entry_button,
        ):
            command_row.addWidget(widget)
        command_row.addStretch(1)
        command_row.addWidget(self.search_edit, 1)
        self.root_layout.addLayout(command_row)

        self.model = QtGui.QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(["Quest / journal entry", "Tag / state"])
        self.proxy = QtCore.QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setRecursiveFilteringEnabled(True)
        self.tree = QtWidgets.QTreeView(self)
        self.tree.setObjectName("scriptingStudioJournalTree")
        self.tree.setModel(self.proxy)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tree.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)

        self.inspector_stack = QtWidgets.QStackedWidget(self)
        self.inspector_stack.setObjectName("scriptingStudioJournalInspector")
        empty = QtWidgets.QLabel("Select a quest or journal entry to edit it.", self)
        empty.setAlignment(QtCore.Qt.AlignCenter)
        self.inspector_stack.addWidget(empty)
        self.inspector_stack.addWidget(self._create_quest_inspector())
        self.inspector_stack.addWidget(self._create_entry_inspector())

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        splitter.setObjectName("scriptingStudioJournalSplitter")
        splitter.addWidget(self.tree)
        splitter.addWidget(self.inspector_stack)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.root_layout.addWidget(splitter, 1)
        self._finish_layout()

        self.open_button.clicked.connect(self.openRequested)
        self.save_button.clicked.connect(self.saveRequested)
        self.validate_button.clicked.connect(self.validateRequested)
        self.add_quest_button.clicked.connect(lambda: self.addQuestRequested.emit({}))
        self.remove_quest_button.clicked.connect(self._request_remove_quest)
        self.add_entry_button.clicked.connect(self._request_add_entry)
        self.remove_entry_button.clicked.connect(self._request_remove_entry)
        self.search_edit.textChanged.connect(self.proxy.setFilterFixedString)
        self.search_edit.textChanged.connect(self.searchRequested)
        self.tree.selectionModel().currentChanged.connect(self._selection_changed)
        self._register_busy_widgets(
            self.open_button,
            self.save_button,
            self.validate_button,
            self.add_quest_button,
            self.remove_quest_button,
            self.add_entry_button,
            self.remove_entry_button,
            self.search_edit,
            self.tree,
        )

    def _create_quest_inspector(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(self)
        page.setObjectName("scriptingStudioJournalQuestInspector")
        layout = QtWidgets.QFormLayout(page)
        self.quest_tag_edit = QtWidgets.QLineEdit(page)
        self.quest_name_edit = QtWidgets.QLineEdit(page)
        self.quest_comment_edit = QtWidgets.QPlainTextEdit(page)
        self.quest_priority_spin = QtWidgets.QSpinBox(page)
        self.quest_priority_spin.setRange(0, 4)
        self.quest_priority_spin.setToolTip("0 is highest priority; 4 is lowest.")
        self.quest_planet_spin = QtWidgets.QSpinBox(page)
        self.quest_planet_spin.setRange(-2147483648, 2147483647)
        self.quest_plot_spin = QtWidgets.QSpinBox(page)
        self.quest_plot_spin.setRange(-2147483648, 2147483647)
        self.quest_apply_button = QtWidgets.QPushButton("Apply Quest Changes", page)
        self.quest_apply_button.setObjectName("scriptingStudioJournalApplyQuest")
        layout.addRow("Tag", self.quest_tag_edit)
        layout.addRow("Display name", self.quest_name_edit)
        layout.addRow("Developer comment", self.quest_comment_edit)
        layout.addRow("Priority", self.quest_priority_spin)
        layout.addRow("Planet ID", self.quest_planet_spin)
        layout.addRow("Plot index", self.quest_plot_spin)
        layout.addRow(self.quest_apply_button)
        self.quest_apply_button.clicked.connect(self._apply_quest)
        self._register_busy_widgets(self.quest_apply_button)
        return page

    def _create_entry_inspector(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(self)
        page.setObjectName("scriptingStudioJournalEntryInspector")
        layout = QtWidgets.QFormLayout(page)
        self.entry_id_spin = QtWidgets.QSpinBox(page)
        self.entry_id_spin.setRange(0, 2147483647)
        self.entry_text_edit = QtWidgets.QPlainTextEdit(page)
        self.entry_end_check = QtWidgets.QCheckBox("Completes the quest", page)
        self.entry_xp_spin = QtWidgets.QDoubleSpinBox(page)
        self.entry_xp_spin.setRange(0.0, 100.0)
        self.entry_xp_spin.setDecimals(3)
        self.entry_apply_button = QtWidgets.QPushButton("Apply Entry Changes", page)
        self.entry_apply_button.setObjectName("scriptingStudioJournalApplyEntry")
        layout.addRow("State ID", self.entry_id_spin)
        layout.addRow("Journal text", self.entry_text_edit)
        layout.addRow("End state", self.entry_end_check)
        layout.addRow("XP percentage", self.entry_xp_spin)
        layout.addRow(self.entry_apply_button)
        self.entry_apply_button.clicked.connect(self._apply_entry)
        self._register_busy_widgets(self.entry_apply_button)
        return page

    def _source_current(self) -> QtCore.QModelIndex:
        current = self.tree.currentIndex()
        return self.proxy.mapToSource(current) if current.isValid() else QtCore.QModelIndex()

    def _selection_indices(self) -> tuple[str, int, int]:
        source = self._source_current()
        if not source.isValid():
            return "", -1, -1
        return (
            str(source.data(ITEM_KIND_ROLE) or ""),
            int(source.data(QUEST_INDEX_ROLE) if source.data(QUEST_INDEX_ROLE) is not None else -1),
            int(source.data(ENTRY_INDEX_ROLE) if source.data(ENTRY_INDEX_ROLE) is not None else -1),
        )

    def _selection_changed(self, _current: QtCore.QModelIndex, _previous: QtCore.QModelIndex) -> None:
        source = self._source_current()
        if not source.isValid():
            self.inspector_stack.setCurrentIndex(0)
            return
        record = source.data(RECORD_ROLE) or {}
        kind = source.data(ITEM_KIND_ROLE)
        if kind == "quest":
            self.quest_tag_edit.setText(str(record.get("tag", "")))
            self.quest_name_edit.setText(str(record.get("name", "")))
            self.quest_comment_edit.setPlainText(str(record.get("comment", "")))
            self.quest_priority_spin.setValue(int(record.get("priority", 4)))
            self.quest_planet_spin.setValue(int(record.get("planet_id", 0)))
            self.quest_plot_spin.setValue(int(record.get("plot_index", 0)))
            self.inspector_stack.setCurrentIndex(1)
        elif kind == "entry":
            self.entry_id_spin.setValue(int(record.get("entry_id", 0)))
            self.entry_text_edit.setPlainText(str(record.get("text", "")))
            self.entry_end_check.setChecked(bool(record.get("end", False)))
            self.entry_xp_spin.setValue(float(record.get("xp_percentage", 0.0)))
            self.inspector_stack.setCurrentIndex(2)

    def _quest_index_for_selection(self) -> int:
        _kind, quest_index, _entry_index = self._selection_indices()
        return quest_index

    def _request_remove_quest(self) -> None:
        quest_index = self._quest_index_for_selection()
        if quest_index >= 0:
            self.removeQuestRequested.emit(quest_index)

    def _request_add_entry(self) -> None:
        quest_index = self._quest_index_for_selection()
        if quest_index >= 0:
            self.addEntryRequested.emit(quest_index, {})

    def _request_remove_entry(self) -> None:
        kind, quest_index, entry_index = self._selection_indices()
        if kind == "entry" and quest_index >= 0 and entry_index >= 0:
            self.removeEntryRequested.emit(quest_index, entry_index)

    def _apply_quest(self) -> None:
        kind, quest_index, _entry_index = self._selection_indices()
        if kind != "quest" or quest_index < 0:
            return
        self.editQuestRequested.emit(
            quest_index,
            {
                "tag": self.quest_tag_edit.text().strip(),
                "name": self.quest_name_edit.text(),
                "comment": self.quest_comment_edit.toPlainText(),
                "priority": self.quest_priority_spin.value(),
                "planet_id": self.quest_planet_spin.value(),
                "plot_index": self.quest_plot_spin.value(),
            },
        )

    def _apply_entry(self) -> None:
        kind, quest_index, entry_index = self._selection_indices()
        if kind != "entry" or quest_index < 0 or entry_index < 0:
            return
        self.editEntryRequested.emit(
            quest_index,
            entry_index,
            {
                "entry_id": self.entry_id_spin.value(),
                "text": self.entry_text_edit.toPlainText(),
                "end": self.entry_end_check.isChecked(),
                "xp_percentage": self.entry_xp_spin.value(),
            },
        )

    def set_journal(self, quests: Sequence[object], *, source_name: str = "") -> None:
        self.model.removeRows(0, self.model.rowCount())
        for quest_index, quest in enumerate(quests):
            quest_record = {
                "tag": str(_field(quest, "tag", "")),
                "name": _localized_text(_field(quest, "name", "")),
                "comment": str(_field(quest, "comment", "")),
                "priority": int(_field(quest, "priority", 4)),
                "planet_id": int(_field(quest, "planet_id", 0)),
                "plot_index": int(_field(quest, "plot_index", 0)),
            }
            title = quest_record["name"] or quest_record["tag"] or f"Quest {quest_index + 1}"
            quest_item = QtGui.QStandardItem(str(title))
            tag_item = QtGui.QStandardItem(quest_record["tag"])
            for item in (quest_item, tag_item):
                item.setData("quest", ITEM_KIND_ROLE)
                item.setData(quest_index, QUEST_INDEX_ROLE)
                item.setData(-1, ENTRY_INDEX_ROLE)
                item.setData(quest_record, RECORD_ROLE)
                item.setEditable(False)
            entries = _field(quest, "entries", ())
            for entry_index, entry in enumerate(entries if isinstance(entries, Sequence) else ()):
                entry_record = {
                    "entry_id": int(_field(entry, "entry_id", 0)),
                    "text": _localized_text(_field(entry, "text", "")),
                    "end": bool(_field(entry, "end", False)),
                    "xp_percentage": float(_field(entry, "xp_percentage", 0.0)),
                }
                entry_item = QtGui.QStandardItem(entry_record["text"] or f"State {entry_record['entry_id']}")
                state_item = QtGui.QStandardItem(str(entry_record["entry_id"]))
                for item in (entry_item, state_item):
                    item.setData("entry", ITEM_KIND_ROLE)
                    item.setData(quest_index, QUEST_INDEX_ROLE)
                    item.setData(entry_index, ENTRY_INDEX_ROLE)
                    item.setData(entry_record, RECORD_ROLE)
                    item.setEditable(False)
                quest_item.appendRow((entry_item, state_item))
            self.model.appendRow((quest_item, tag_item))
        self.tree.expandAll()
        self.inspector_stack.setCurrentIndex(0)
        detail = f" — {source_name}" if source_name else ""
        self.set_status(f"{len(quests)} quest categories loaded{detail}")


class TwoDAGlobalsPage(_NarrativeDataPage):
    """Spreadsheet-style 2DA editor with a typed globalcat workflow."""

    openRequested = QtCore.Signal()
    saveRequested = QtCore.Signal()
    exportPatchRequested = QtCore.Signal()
    searchRequested = QtCore.Signal(str)
    modeChanged = QtCore.Signal(str)
    cellEditRequested = QtCore.Signal(int, str, object)
    rowLabelEditRequested = QtCore.Signal(int, str)
    addRowRequested = QtCore.Signal(object)
    removeRowRequested = QtCore.Signal(int)
    duplicateRowsRequested = QtCore.Signal(object)
    addColumnRequested = QtCore.Signal(str, object)
    renameColumnRequested = QtCore.Signal(str, str)
    removeColumnRequested = QtCore.Signal(str)
    addGlobalRequested = QtCore.Signal(str, str)
    copyTextRequested = QtCore.Signal(str)
    pasteCellsRequested = QtCore.Signal(object)
    undoRequested = QtCore.Signal()
    redoRequested = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("scriptingStudioTwoDAGlobalsPage", parent)
        self._presenting = False
        self._headers: tuple[str, ...] = ()

        command_row = QtWidgets.QHBoxLayout()
        self.mode_combo = QtWidgets.QComboBox(self)
        self.mode_combo.setObjectName("scriptingStudioTwoDAMode")
        self.mode_combo.addItem("2DA Table", "2da")
        self.mode_combo.addItem("Global Variables", "globals")
        self.open_button = QtWidgets.QPushButton("Open 2DA…", self)
        self.save_button = QtWidgets.QPushButton("Save 2DA", self)
        self.patch_button = QtWidgets.QPushButton("Export changes.ini…", self)
        self.add_row_button = QtWidgets.QPushButton("+ Row", self)
        self.remove_row_button = QtWidgets.QPushButton("− Row", self)
        self.search_edit = QtWidgets.QLineEdit(self)
        self.search_edit.setObjectName("scriptingStudioTwoDASearch")
        self.search_edit.setPlaceholderText("Filter any row or cell…")
        for widget in (
            self.mode_combo,
            self.open_button,
            self.save_button,
            self.patch_button,
            self.add_row_button,
            self.remove_row_button,
        ):
            command_row.addWidget(widget)
        command_row.addStretch(1)
        command_row.addWidget(self.search_edit, 1)
        self.root_layout.addLayout(command_row)

        edit_row = QtWidgets.QHBoxLayout()
        self.undo_button = QtWidgets.QPushButton("Undo", self)
        self.undo_button.setObjectName("scriptingStudioTwoDAUndo")
        self.redo_button = QtWidgets.QPushButton("Redo", self)
        self.redo_button.setObjectName("scriptingStudioTwoDARedo")
        self.copy_button = QtWidgets.QPushButton("Copy", self)
        self.copy_button.setObjectName("scriptingStudioTwoDACopy")
        self.paste_button = QtWidgets.QPushButton("Paste", self)
        self.paste_button.setObjectName("scriptingStudioTwoDAPaste")
        self.duplicate_row_button = QtWidgets.QPushButton("Duplicate Row", self)
        self.duplicate_row_button.setObjectName("scriptingStudioTwoDADuplicateRow")
        for widget in (
            self.undo_button,
            self.redo_button,
            self.copy_button,
            self.paste_button,
            self.duplicate_row_button,
        ):
            edit_row.addWidget(widget)
        edit_row.addStretch(1)
        self.root_layout.addLayout(edit_row)

        author_row = QtWidgets.QHBoxLayout()
        self.column_name_edit = QtWidgets.QLineEdit(self)
        self.column_name_edit.setObjectName("scriptingStudioTwoDAColumnName")
        self.column_name_edit.setPlaceholderText("New column name")
        self.column_default_edit = QtWidgets.QLineEdit(self)
        self.column_default_edit.setPlaceholderText("Default value")
        self.add_column_button = QtWidgets.QPushButton("+ Column", self)
        self.remove_column_combo = QtWidgets.QComboBox(self)
        self.remove_column_combo.setObjectName("scriptingStudioTwoDARemoveColumnChoice")
        self.rename_column_button = QtWidgets.QPushButton("Rename Column", self)
        self.remove_column_button = QtWidgets.QPushButton("− Column", self)
        self.global_name_edit = QtWidgets.QLineEdit(self)
        self.global_name_edit.setObjectName("scriptingStudioGlobalName")
        self.global_name_edit.setPlaceholderText("MYMOD_VARIABLE")
        self.global_type_combo = QtWidgets.QComboBox(self)
        self.global_type_combo.addItems(("Boolean", "Number", "String", "Location"))
        self.add_global_button = QtWidgets.QPushButton("+ Global", self)
        for widget in (
            self.column_name_edit,
            self.column_default_edit,
            self.add_column_button,
            self.remove_column_combo,
            self.rename_column_button,
            self.remove_column_button,
            self.global_name_edit,
            self.global_type_combo,
            self.add_global_button,
        ):
            author_row.addWidget(widget)
        self.root_layout.addLayout(author_row)

        self.model = QtGui.QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(["Row label"])
        self.proxy = QtCore.QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.table = QtWidgets.QTableView(self)
        self.table.setObjectName("scriptingStudioTwoDATable")
        self.table.setModel(self.proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.root_layout.addWidget(self.table, 1)
        self._finish_layout()

        self.open_button.clicked.connect(self.openRequested)
        self.save_button.clicked.connect(self.saveRequested)
        self.patch_button.clicked.connect(self.exportPatchRequested)
        self.add_row_button.clicked.connect(lambda: self.addRowRequested.emit({}))
        self.remove_row_button.clicked.connect(self._request_remove_row)
        self.duplicate_row_button.clicked.connect(self._request_duplicate_rows)
        self.add_column_button.clicked.connect(self._request_add_column)
        self.rename_column_button.clicked.connect(self._request_rename_column)
        self.remove_column_button.clicked.connect(self._request_remove_column)
        self.add_global_button.clicked.connect(self._request_add_global)
        self.copy_button.clicked.connect(self._request_copy)
        self.paste_button.clicked.connect(self._request_paste)
        self.undo_button.clicked.connect(self.undoRequested)
        self.redo_button.clicked.connect(self.redoRequested)
        self.search_edit.textChanged.connect(self.proxy.setFilterFixedString)
        self.search_edit.textChanged.connect(self.searchRequested)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.model.itemChanged.connect(self._item_changed)
        self.copy_shortcut = QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Copy, self.table)
        self.copy_shortcut.activated.connect(self._request_copy)
        self.paste_shortcut = QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Paste, self.table)
        self.paste_shortcut.activated.connect(self._request_paste)
        self.undo_shortcut = QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Undo, self.table)
        self.undo_shortcut.activated.connect(self.undoRequested)
        self.redo_shortcut = QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Redo, self.table)
        self.redo_shortcut.activated.connect(self.redoRequested)
        for shortcut in (
            self.copy_shortcut,
            self.paste_shortcut,
            self.undo_shortcut,
            self.redo_shortcut,
        ):
            shortcut.setContext(QtCore.Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.set_global_mode(False)
        self.set_history_state(False, False)
        self._register_busy_widgets(
            self.mode_combo,
            self.open_button,
            self.save_button,
            self.patch_button,
            self.add_row_button,
            self.remove_row_button,
            self.duplicate_row_button,
            self.add_column_button,
            self.rename_column_button,
            self.remove_column_button,
            self.add_global_button,
            self.undo_button,
            self.redo_button,
            self.copy_button,
            self.paste_button,
            self.search_edit,
            self.table,
        )

    def _mode_changed(self) -> None:
        mode = str(self.mode_combo.currentData() or "2da")
        self.set_global_mode(mode == "globals", update_combo=False)
        self.modeChanged.emit(mode)

    def set_global_mode(self, enabled: bool, *, update_combo: bool = True) -> None:
        if update_combo:
            self.mode_combo.setCurrentIndex(1 if enabled else 0)
        self.global_name_edit.setVisible(enabled)
        self.global_type_combo.setVisible(enabled)
        self.add_global_button.setVisible(enabled)
        self.duplicate_row_button.setVisible(not enabled)
        for widget in (
            self.column_name_edit,
            self.column_default_edit,
            self.add_column_button,
            self.remove_column_combo,
            self.rename_column_button,
            self.remove_column_button,
        ):
            widget.setVisible(not enabled)

    def _selected_source_row(self) -> int:
        current = self.table.currentIndex()
        if not current.isValid():
            return -1
        source = self.proxy.mapToSource(current)
        value = source.data(SOURCE_ROW_ROLE)
        return int(value) if value is not None else source.row()

    def _request_remove_row(self) -> None:
        row = self._selected_source_row()
        if row >= 0:
            self.removeRowRequested.emit(row)

    def _selected_source_rows(self) -> tuple[int, ...]:
        selection = self.table.selectionModel()
        indexes = selection.selectedIndexes() if selection is not None else []
        if not indexes and self.table.currentIndex().isValid():
            indexes = [self.table.currentIndex()]
        rows: list[int] = []
        for proxy_index in sorted(indexes, key=lambda index: (index.row(), index.column())):
            source = self.proxy.mapToSource(proxy_index)
            value = source.data(SOURCE_ROW_ROLE)
            row = int(value) if value is not None else source.row()
            if row not in rows:
                rows.append(row)
        return tuple(rows)

    def _request_duplicate_rows(self) -> None:
        rows = self._selected_source_rows()
        if rows:
            self.duplicateRowsRequested.emit(rows)

    def _request_add_column(self) -> None:
        name = self.column_name_edit.text().strip()
        if name:
            self.addColumnRequested.emit(name, self.column_default_edit.text())

    def _request_rename_column(self) -> None:
        old_name = self.remove_column_combo.currentText()
        new_name = self.column_name_edit.text().strip()
        if old_name and new_name:
            self.renameColumnRequested.emit(old_name, new_name)

    def _request_remove_column(self) -> None:
        column = self.remove_column_combo.currentText()
        if column:
            self.removeColumnRequested.emit(column)

    def _request_add_global(self) -> None:
        name = self.global_name_edit.text().strip()
        if name:
            self.addGlobalRequested.emit(name, self.global_type_combo.currentText())

    def _request_copy(self) -> None:
        selection = self.table.selectionModel()
        indexes = selection.selectedIndexes() if selection is not None else []
        if not indexes and self.table.currentIndex().isValid():
            indexes = [self.table.currentIndex()]
        if not indexes:
            return
        top = min(index.row() for index in indexes)
        bottom = max(index.row() for index in indexes)
        left = min(index.column() for index in indexes)
        right = max(index.column() for index in indexes)
        output = io.StringIO(newline="")
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        for row in range(top, bottom + 1):
            writer.writerow(
                str(self.proxy.index(row, column).data(QtCore.Qt.DisplayRole) or "")
                for column in range(left, right + 1)
            )
        self.copyTextRequested.emit(output.getvalue().rstrip("\n"))

    def _request_paste(self, text: str | None = None) -> None:
        clipboard_text = QtWidgets.QApplication.clipboard().text() if text is None else str(text)
        if not clipboard_text:
            return
        start = self.table.currentIndex()
        if not start.isValid():
            indexes = self.table.selectionModel().selectedIndexes() if self.table.selectionModel() else []
            if not indexes:
                return
            start = min(indexes, key=lambda index: (index.row(), index.column()))
        values = list(csv.reader(io.StringIO(clipboard_text), delimiter="\t"))
        edits: list[tuple[int, str | None, str]] = []
        for row_offset, row_values in enumerate(values):
            proxy_row = start.row() + row_offset
            if proxy_row >= self.proxy.rowCount():
                break
            source = self.proxy.mapToSource(self.proxy.index(proxy_row, 0))
            source_value = source.data(SOURCE_ROW_ROLE)
            source_row = int(source_value) if source_value is not None else source.row()
            for column_offset, value in enumerate(row_values):
                model_column = start.column() + column_offset
                if model_column >= self.model.columnCount():
                    break
                column_name = None if model_column == 0 else self._headers[model_column - 1]
                edits.append((source_row, column_name, value))
        if edits:
            self.pasteCellsRequested.emit(tuple(edits))

    def set_history_state(self, can_undo: bool, can_redo: bool) -> None:
        self.undo_button.setEnabled(bool(can_undo))
        self.redo_button.setEnabled(bool(can_redo))

    def _item_changed(self, item: QtGui.QStandardItem) -> None:
        if self._presenting:
            return
        source_row = item.data(SOURCE_ROW_ROLE)
        row_index = int(source_row) if source_row is not None else item.row()
        if item.column() == 0:
            self.rowLabelEditRequested.emit(row_index, item.text())
            return
        header_index = item.column() - 1
        if 0 <= header_index < len(self._headers):
            self.cellEditRequested.emit(row_index, self._headers[header_index], item.text())

    def set_table(
        self,
        headers: Sequence[str],
        labels: Sequence[str],
        rows: Sequence[object],
        *,
        source_name: str = "",
    ) -> None:
        self._presenting = True
        try:
            self._headers = tuple(str(header) for header in headers)
            self.model.clear()
            self.model.setHorizontalHeaderLabels(["Row label", *self._headers])
            for row_index, label in enumerate(labels):
                record = rows[row_index]
                if isinstance(record, Mapping):
                    values = [record.get(header, "") for header in self._headers]
                else:
                    values = list(record) if isinstance(record, Sequence) and not isinstance(record, str) else []
                items = [QtGui.QStandardItem(str(label)), *(QtGui.QStandardItem(str(value)) for value in values)]
                while len(items) < len(self._headers) + 1:
                    items.append(QtGui.QStandardItem(""))
                for item in items:
                    item.setData(row_index, SOURCE_ROW_ROLE)
                self.model.appendRow(items)
            self.remove_column_combo.clear()
            self.remove_column_combo.addItems(self._headers)
            self.table.resizeColumnsToContents()
        finally:
            self._presenting = False
        detail = f" — {source_name}" if source_name else ""
        self.set_status(f"{len(labels)} rows × {len(self._headers)} columns loaded{detail}")


class TalkTablePage(_NarrativeDataPage):
    """Searchable TLK editor with StrRef jump and metadata columns."""

    openRequested = QtCore.Signal()
    saveRequested = QtCore.Signal()
    addEntryRequested = QtCore.Signal(object)
    entryEditRequested = QtCore.Signal(int, object)
    searchRequested = QtCore.Signal(str)
    jumpRequested = QtCore.Signal(int)
    installGameRequested = QtCore.Signal()
    restoreGameRequested = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("scriptingStudioTalkTablePage", parent)
        self._presenting = False

        command_row = QtWidgets.QHBoxLayout()
        self.open_button = QtWidgets.QPushButton("Open dialog.tlk…", self)
        self.save_button = QtWidgets.QPushButton("Save TLK", self)
        self.add_button = QtWidgets.QPushButton("+ String", self)
        self.jump_spin = QtWidgets.QSpinBox(self)
        self.jump_spin.setObjectName("scriptingStudioTlkJump")
        self.jump_spin.setRange(0, 0)
        self.jump_button = QtWidgets.QPushButton("Go to StrRef", self)
        self.search_edit = QtWidgets.QLineEdit(self)
        self.search_edit.setObjectName("scriptingStudioTlkSearch")
        self.search_edit.setPlaceholderText("Search text, voiceover, or StrRef…")
        for widget in (self.open_button, self.save_button, self.add_button, self.jump_spin, self.jump_button):
            command_row.addWidget(widget)
        command_row.addStretch(1)
        command_row.addWidget(self.search_edit, 1)
        self.root_layout.addLayout(command_row)

        delivery = QtWidgets.QGroupBox("Game-global TLK delivery", self)
        delivery.setObjectName("scriptingStudioTlkDeliveryGroup")
        delivery_layout = QtWidgets.QHBoxLayout(delivery)
        delivery_note = QtWidgets.QLabel(
            "dialog.tlk is game-global. GhostStudio backs up the installed file and writes a restore receipt; it is never placed in Override or a MOD.",
            delivery,
        )
        delivery_note.setWordWrap(True)
        delivery_layout.addWidget(delivery_note, 1)
        self.install_button = QtWidgets.QPushButton("Install with Backup…", delivery)
        self.install_button.setObjectName("scriptingStudioTlkInstallButton")
        self.restore_button = QtWidgets.QPushButton("Restore from Receipt…", delivery)
        self.restore_button.setObjectName("scriptingStudioTlkRestoreButton")
        delivery_layout.addWidget(self.install_button)
        delivery_layout.addWidget(self.restore_button)
        self.root_layout.addWidget(delivery)

        self.model = QtGui.QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(["StrRef", "Text", "Voiceover", "Sound length"])
        self.proxy = QtCore.QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.table = QtWidgets.QTableView(self)
        self.table.setObjectName("scriptingStudioTlkTable")
        self.table.setModel(self.proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.root_layout.addWidget(self.table, 1)
        self._finish_layout()

        self.open_button.clicked.connect(self.openRequested)
        self.save_button.clicked.connect(self.saveRequested)
        self.add_button.clicked.connect(lambda: self.addEntryRequested.emit({}))
        self.jump_button.clicked.connect(self._jump)
        self.jump_spin.lineEdit().returnPressed.connect(self._jump)
        self.search_edit.textChanged.connect(self.proxy.setFilterFixedString)
        self.search_edit.textChanged.connect(self.searchRequested)
        self.model.itemChanged.connect(self._item_changed)
        self.install_button.clicked.connect(self.installGameRequested)
        self.restore_button.clicked.connect(self.restoreGameRequested)
        self._register_busy_widgets(
            self.open_button,
            self.save_button,
            self.add_button,
            self.jump_spin,
            self.jump_button,
            self.search_edit,
            self.table,
            self.install_button,
            self.restore_button,
        )

    def _jump(self) -> None:
        strref = self.jump_spin.value()
        self.jumpRequested.emit(strref)
        source = self.model.index(strref, 0)
        proxy_index = self.proxy.mapFromSource(source)
        if proxy_index.isValid():
            self.table.setCurrentIndex(proxy_index)
            self.table.scrollTo(proxy_index, QtWidgets.QAbstractItemView.PositionAtCenter)

    def _item_changed(self, item: QtGui.QStandardItem) -> None:
        if self._presenting or item.column() == 0:
            return
        strref = int(item.data(SOURCE_ROW_ROLE) if item.data(SOURCE_ROW_ROLE) is not None else item.row())
        fields = {1: "text", 2: "voiceover", 3: "sound_length"}
        value: object = item.text()
        if item.column() == 3:
            try:
                value = float(item.text())
            except ValueError:
                pass
        self.entryEditRequested.emit(strref, {fields[item.column()]: value})

    def set_entries(self, entries: Sequence[object], *, language: str = "", source_name: str = "") -> None:
        self._presenting = True
        try:
            self.model.removeRows(0, self.model.rowCount())
            for row_index, entry in enumerate(entries):
                strref = int(_field(entry, "strref", row_index))
                values = (
                    strref,
                    _field(entry, "text", ""),
                    _field(entry, "voiceover", ""),
                    _field(entry, "sound_length", 0.0),
                )
                items = [QtGui.QStandardItem(str(value)) for value in values]
                items[0].setEditable(False)
                for item in items:
                    item.setData(strref, SOURCE_ROW_ROLE)
                self.model.appendRow(items)
            self.jump_spin.setRange(0, max(0, len(entries) - 1))
        finally:
            self._presenting = False
        details = " · ".join(value for value in (language, source_name) if value)
        self.set_status(f"{len(entries)} TLK strings loaded" + (f" — {details}" if details else ""))


class LipSoundSetPage(_NarrativeDataPage):
    """Combined LIP viseme timeline and 28-slot SSF editor."""

    openLipRequested = QtCore.Signal()
    saveLipRequested = QtCore.Signal()
    addLipKeyframeRequested = QtCore.Signal(float, int)
    removeLipKeyframeRequested = QtCore.Signal(int)
    lipKeyframeEditRequested = QtCore.Signal(int, object)
    lipDurationChangedRequested = QtCore.Signal(float)
    lipAudioBrowseRequested = QtCore.Signal()
    lipAudioPlayRequested = QtCore.Signal(str)
    lipAudioStopRequested = QtCore.Signal()
    openSoundSetRequested = QtCore.Signal()
    saveSoundSetRequested = QtCore.Signal()
    soundSetSlotEditRequested = QtCore.Signal(int, int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("scriptingStudioLipSoundSetPage", parent)
        self._presenting_lip = False
        self._presenting_ssf = False
        self._shape_names: tuple[str, ...] = ()
        self.tabs = QtWidgets.QTabWidget(self)
        self.tabs.setObjectName("scriptingStudioLipSoundSetTabs")
        self.tabs.addTab(self._create_lip_page(), "LIP Timeline")
        self.tabs.addTab(self._create_ssf_page(), "Sound Set (SSF)")
        self.root_layout.addWidget(self.tabs, 1)
        self._finish_layout()

    def _create_lip_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(self)
        page.setObjectName("scriptingStudioLipPage")
        layout = QtWidgets.QVBoxLayout(page)
        commands = QtWidgets.QHBoxLayout()
        self.open_lip_button = QtWidgets.QPushButton("Open LIP…", page)
        self.save_lip_button = QtWidgets.QPushButton("Save LIP", page)
        self.duration_spin = QtWidgets.QDoubleSpinBox(page)
        self.duration_spin.setObjectName("scriptingStudioLipDuration")
        self.duration_spin.setRange(0.0, 86400.0)
        self.duration_spin.setDecimals(4)
        self.duration_spin.setSuffix(" s")
        self.key_time_spin = QtWidgets.QDoubleSpinBox(page)
        self.key_time_spin.setRange(0.0, 86400.0)
        self.key_time_spin.setDecimals(4)
        self.key_time_spin.setSuffix(" s")
        self.shape_combo = QtWidgets.QComboBox(page)
        self.shape_combo.setObjectName("scriptingStudioLipShape")
        self.add_key_button = QtWidgets.QPushButton("+ Keyframe", page)
        self.remove_key_button = QtWidgets.QPushButton("− Keyframe", page)
        commands.addWidget(self.open_lip_button)
        commands.addWidget(self.save_lip_button)
        commands.addWidget(QtWidgets.QLabel("Duration", page))
        commands.addWidget(self.duration_spin)
        commands.addStretch(1)
        commands.addWidget(self.key_time_spin)
        commands.addWidget(self.shape_combo)
        commands.addWidget(self.add_key_button)
        commands.addWidget(self.remove_key_button)
        layout.addLayout(commands)

        audio_group = QtWidgets.QGroupBox("Synchronized audio preview", page)
        audio_group.setObjectName("scriptingStudioLipAudioPreviewGroup")
        audio_layout = QtWidgets.QGridLayout(audio_group)
        self.lip_audio_path_edit = QtWidgets.QLineEdit(audio_group)
        self.lip_audio_path_edit.setObjectName("scriptingStudioLipAudioPath")
        self.lip_audio_path_edit.setPlaceholderText("Choose the matching KOTOR WAV or a local preview audio file")
        self.lip_audio_browse_button = QtWidgets.QPushButton("Browse…", audio_group)
        self.lip_audio_play_button = QtWidgets.QPushButton("Play", audio_group)
        self.lip_audio_stop_button = QtWidgets.QPushButton("Stop", audio_group)
        self.lip_audio_progress = QtWidgets.QProgressBar(audio_group)
        self.lip_audio_progress.setObjectName("scriptingStudioLipAudioProgress")
        self.lip_audio_progress.setRange(0, 1)
        self.lip_audio_progress.setValue(0)
        self.lip_audio_progress.setTextVisible(True)
        self.lip_audio_status = QtWidgets.QLabel(
            "Editor preview only; retail KOTOR remains authoritative for lip timing and playback.",
            audio_group,
        )
        self.lip_audio_status.setWordWrap(True)
        audio_layout.addWidget(self.lip_audio_path_edit, 0, 0, 1, 3)
        audio_layout.addWidget(self.lip_audio_browse_button, 0, 3)
        audio_layout.addWidget(self.lip_audio_play_button, 0, 4)
        audio_layout.addWidget(self.lip_audio_stop_button, 0, 5)
        audio_layout.addWidget(self.lip_audio_progress, 1, 0, 1, 6)
        audio_layout.addWidget(self.lip_audio_status, 2, 0, 1, 6)
        audio_layout.setColumnStretch(0, 1)
        layout.addWidget(audio_group)

        self.lip_model = QtGui.QStandardItemModel(self)
        self.lip_model.setHorizontalHeaderLabels(["Time (seconds)", "Mouth shape"])
        self.lip_table = QtWidgets.QTableView(page)
        self.lip_table.setObjectName("scriptingStudioLipTable")
        self.lip_table.setModel(self.lip_model)
        self.lip_table.setAlternatingRowColors(True)
        self.lip_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.lip_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.lip_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.lip_table, 1)

        self.open_lip_button.clicked.connect(self.openLipRequested)
        self.save_lip_button.clicked.connect(self.saveLipRequested)
        self.duration_spin.editingFinished.connect(lambda: self.lipDurationChangedRequested.emit(self.duration_spin.value()))
        self.add_key_button.clicked.connect(
            lambda: self.addLipKeyframeRequested.emit(self.key_time_spin.value(), self.shape_combo.currentIndex())
        )
        self.remove_key_button.clicked.connect(self._request_remove_keyframe)
        self.lip_audio_browse_button.clicked.connect(self.lipAudioBrowseRequested)
        self.lip_audio_play_button.clicked.connect(
            lambda: self.lipAudioPlayRequested.emit(self.lip_audio_path_edit.text().strip())
        )
        self.lip_audio_stop_button.clicked.connect(self.lipAudioStopRequested)
        self.lip_model.itemChanged.connect(self._lip_item_changed)
        self._register_busy_widgets(
            self.open_lip_button,
            self.save_lip_button,
            self.duration_spin,
            self.key_time_spin,
            self.shape_combo,
            self.add_key_button,
            self.remove_key_button,
            self.lip_audio_path_edit,
            self.lip_audio_browse_button,
            self.lip_audio_play_button,
            self.lip_audio_stop_button,
            self.lip_table,
        )
        self.set_lip_audio_state("Choose matching audio to preview the viseme timing.")
        return page

    def set_lip_audio_path(self, path: str) -> None:
        value = str(path or "")
        self.lip_audio_path_edit.setText(value)
        self.lip_audio_play_button.setEnabled(bool(value))

    def set_lip_audio_state(
        self,
        message: str,
        *,
        position_ms: int = 0,
        duration_ms: int = 0,
        playing: bool = False,
        error: bool = False,
    ) -> None:
        duration = max(0, int(duration_ms))
        position = min(max(0, int(position_ms)), duration) if duration else 0
        self.lip_audio_progress.setRange(0, max(1, duration))
        self.lip_audio_progress.setValue(position)
        self.lip_audio_progress.setFormat(
            f"{position / 1000.0:.2f} / {duration / 1000.0:.2f} s" if duration else "Stopped"
        )
        self.lip_audio_status.setText(str(message or "Audio preview stopped."))
        self.lip_audio_status.setProperty("error", bool(error))
        self.lip_audio_play_button.setEnabled(not playing and bool(self.lip_audio_path_edit.text().strip()))
        self.lip_audio_stop_button.setEnabled(playing)
        if duration and self.lip_model.rowCount():
            seconds = position / 1000.0
            nearest = min(
                range(self.lip_model.rowCount()),
                key=lambda row: abs(float(self.lip_model.index(row, 0).data() or 0.0) - seconds),
            )
            index = self.lip_model.index(nearest, 0)
            self.lip_table.setCurrentIndex(index)
            self.lip_table.scrollTo(index, QtWidgets.QAbstractItemView.PositionAtCenter)

    def _create_ssf_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(self)
        page.setObjectName("scriptingStudioSoundSetPage")
        layout = QtWidgets.QVBoxLayout(page)
        commands = QtWidgets.QHBoxLayout()
        self.open_ssf_button = QtWidgets.QPushButton("Open SSF…", page)
        self.save_ssf_button = QtWidgets.QPushButton("Save SSF", page)
        self.unset_ssf_button = QtWidgets.QPushButton("Unset Selected Slot", page)
        commands.addWidget(self.open_ssf_button)
        commands.addWidget(self.save_ssf_button)
        commands.addWidget(self.unset_ssf_button)
        commands.addStretch(1)
        layout.addLayout(commands)

        self.ssf_model = QtGui.QStandardItemModel(self)
        self.ssf_model.setHorizontalHeaderLabels(["Engine event", "TLK StrRef"])
        self.ssf_table = QtWidgets.QTableView(page)
        self.ssf_table.setObjectName("scriptingStudioSoundSetTable")
        self.ssf_table.setModel(self.ssf_model)
        self.ssf_table.setAlternatingRowColors(True)
        self.ssf_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.ssf_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.ssf_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        layout.addWidget(self.ssf_table, 1)

        self.open_ssf_button.clicked.connect(self.openSoundSetRequested)
        self.save_ssf_button.clicked.connect(self.saveSoundSetRequested)
        self.unset_ssf_button.clicked.connect(self._unset_selected_ssf)
        self.ssf_model.itemChanged.connect(self._ssf_item_changed)
        self._register_busy_widgets(
            self.open_ssf_button,
            self.save_ssf_button,
            self.unset_ssf_button,
            self.ssf_table,
        )
        return page

    def _request_remove_keyframe(self) -> None:
        current = self.lip_table.currentIndex()
        if current.isValid():
            source_index = current.data(SOURCE_ROW_ROLE)
            self.removeLipKeyframeRequested.emit(int(source_index if source_index is not None else current.row()))

    def _lip_item_changed(self, item: QtGui.QStandardItem) -> None:
        if self._presenting_lip:
            return
        index = int(item.data(SOURCE_ROW_ROLE) if item.data(SOURCE_ROW_ROLE) is not None else item.row())
        if item.column() == 0:
            try:
                value: object = float(item.text())
            except ValueError:
                value = item.text()
            payload = {"time": value}
        else:
            text = item.text().strip()
            payload = {"shape": self._shape_names.index(text) if text in self._shape_names else text}
        self.lipKeyframeEditRequested.emit(index, payload)

    def _unset_selected_ssf(self) -> None:
        current = self.ssf_table.currentIndex()
        if current.isValid():
            source_index = current.data(SOURCE_ROW_ROLE)
            self.soundSetSlotEditRequested.emit(int(source_index if source_index is not None else current.row()), -1)

    def _ssf_item_changed(self, item: QtGui.QStandardItem) -> None:
        if self._presenting_ssf or item.column() != 1:
            return
        slot = int(item.data(SOURCE_ROW_ROLE) if item.data(SOURCE_ROW_ROLE) is not None else item.row())
        try:
            stringref = int(item.text())
        except ValueError:
            return
        self.soundSetSlotEditRequested.emit(slot, stringref)

    def set_lip(
        self,
        duration: float,
        keyframes: Sequence[object],
        shape_names: Sequence[str],
        *,
        source_name: str = "",
    ) -> None:
        self._presenting_lip = True
        try:
            self._shape_names = tuple(str(name) for name in shape_names)
            self.shape_combo.clear()
            self.shape_combo.addItems(self._shape_names)
            self.duration_spin.setValue(float(duration))
            self.key_time_spin.setMaximum(max(86400.0, float(duration)))
            self.lip_model.removeRows(0, self.lip_model.rowCount())
            for index, frame in enumerate(keyframes):
                time_value = float(_field(frame, "time", 0.0))
                shape_value = int(_field(frame, "shape", 0))
                shape_name = self._shape_names[shape_value] if 0 <= shape_value < len(self._shape_names) else str(shape_value)
                items = [QtGui.QStandardItem(f"{time_value:.4f}"), QtGui.QStandardItem(shape_name)]
                for item in items:
                    item.setData(index, SOURCE_ROW_ROLE)
                self.lip_model.appendRow(items)
        finally:
            self._presenting_lip = False
        detail = f" — {source_name}" if source_name else ""
        self.set_status(f"{len(keyframes)} LIP keyframes over {float(duration):.3f} seconds{detail}")

    def set_sound_set(
        self,
        slot_names: Sequence[str],
        stringrefs: Sequence[int],
        *,
        source_name: str = "",
    ) -> None:
        self._presenting_ssf = True
        try:
            self.ssf_model.removeRows(0, self.ssf_model.rowCount())
            names = tuple(str(name) for name in slot_names)
            for index, stringref in enumerate(stringrefs):
                name = names[index] if index < len(names) else f"UNNAMED_RETAIL_ENTRY_{index}"
                name_item = QtGui.QStandardItem(str(name).replace("_", " ").title())
                name_item.setToolTip(str(name))
                name_item.setEditable(False)
                ref_item = QtGui.QStandardItem(str(int(stringref)))
                for item in (name_item, ref_item):
                    item.setData(index, SOURCE_ROW_ROLE)
                self.ssf_model.appendRow((name_item, ref_item))
        finally:
            self._presenting_ssf = False
        detail = f" — {source_name}" if source_name else ""
        tail_count = max(0, len(stringrefs) - len(slot_names))
        tail = f" including {tail_count} preserved unnamed retail entries" if tail_count else ""
        self.set_status(f"{min(len(stringrefs), len(slot_names))} named SSF sound slots{tail}{detail}")


__all__ = [
    "LipSoundSetPage",
    "QuestJournalPage",
    "TalkTablePage",
    "TwoDAGlobalsPage",
]
