"""Qt orchestration for quest, journal, table, TLK, LIP, and SSF authoring."""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Mapping

from PySide6 import QtCore, QtWidgets

from src.core.scripting.data_authoring import (
    GlobalVariableTable,
    JournalDocument,
    JournalEntryRecord,
    JournalQuestRecord,
    LipDocument,
    LocalizedText,
    NarrativeDataAuthoringService,
    SoundSetDocument,
    TalkTableDocument,
    TwoDADocument,
    TwoDASnapshot,
)
from src.core.scripting.quest import QuestDefinition, QuestScaffoldResult, QuestScaffoldService


log = logging.getLogger(__name__)
_TABLE_HISTORY_LIMIT = 100


class ScriptingDataController(QtCore.QObject):
    """Keep all mutable non-DLG narrative documents outside Qt widgets."""

    contentChanged = QtCore.Signal()
    diagnosticsChanged = QtCore.Signal(object, str)
    operationFailed = QtCore.Signal(str)
    statusChanged = QtCore.Signal(str)
    questScaffoldCommitted = QtCore.Signal(object)

    def __init__(
        self,
        window: Any,
        *,
        script_sink: Callable[[str, str, str], object] | None = None,
        game_provider: Callable[[], str] | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.window = window
        self.script_sink = script_sink
        self.game_provider = game_provider or (lambda: "K2")
        self.journal: JournalDocument | None = None
        self.table: TwoDADocument | None = None
        self.globals: GlobalVariableTable | None = None
        self.talk_table: TalkTableDocument | None = None
        self.lip: LipDocument | None = None
        self.sound_set: SoundSetDocument | None = None
        self._table_mode = "2da"
        self._table_undo: dict[str, list[TwoDASnapshot]] = {"2da": [], "globals": []}
        self._table_redo: dict[str, list[TwoDASnapshot]] = {"2da": [], "globals": []}
        self._quest_preview: QuestScaffoldResult | None = None
        self.quest_definition: QuestDefinition | None = None
        self._lip_audio_preview: Any | None = None
        self._bind()
        self._initialise_pages()

    def _bind(self) -> None:
        journal = getattr(self.window, "quest_journal_page", None)
        if journal is not None:
            journal.openRequested.connect(self.open_journal)
            journal.saveRequested.connect(self.save_journal)
            journal.validateRequested.connect(self.validate_journal)
            journal.addQuestRequested.connect(self.add_quest)
            journal.removeQuestRequested.connect(self.remove_quest)
            journal.editQuestRequested.connect(self.edit_quest)
            journal.addEntryRequested.connect(self.add_journal_entry)
            journal.removeEntryRequested.connect(self.remove_journal_entry)
            journal.editEntryRequested.connect(self.edit_journal_entry)

        tables = getattr(self.window, "twoda_globals_page", None)
        if tables is not None:
            tables.openRequested.connect(self.open_table)
            tables.saveRequested.connect(self.save_table)
            tables.exportPatchRequested.connect(self.export_table_patch)
            tables.modeChanged.connect(self.set_table_mode)
            tables.cellEditRequested.connect(self.edit_table_cell)
            tables.rowLabelEditRequested.connect(self.edit_table_label)
            tables.addRowRequested.connect(self.add_table_row)
            tables.removeRowRequested.connect(self.remove_table_row)
            tables.duplicateRowsRequested.connect(self.duplicate_table_rows)
            tables.addColumnRequested.connect(self.add_table_column)
            tables.renameColumnRequested.connect(self.rename_table_column)
            tables.removeColumnRequested.connect(self.remove_table_column)
            tables.addGlobalRequested.connect(self.add_global)
            tables.copyTextRequested.connect(self.copy_table_text)
            tables.pasteCellsRequested.connect(self.paste_table_cells)
            tables.undoRequested.connect(self.undo_table)
            tables.redoRequested.connect(self.redo_table)

        talk = getattr(self.window, "talk_table_page", None)
        if talk is not None:
            talk.openRequested.connect(self.open_talk_table)
            talk.saveRequested.connect(self.save_talk_table)
            talk.addEntryRequested.connect(self.add_talk_entry)
            talk.entryEditRequested.connect(self.edit_talk_entry)
            talk.installGameRequested.connect(self.install_talk_table)
            talk.restoreGameRequested.connect(self.restore_talk_table)

        voice = getattr(self.window, "lip_sound_set_page", None)
        if voice is not None:
            voice.openLipRequested.connect(self.open_lip)
            voice.saveLipRequested.connect(self.save_lip)
            voice.addLipKeyframeRequested.connect(self.add_lip_keyframe)
            voice.removeLipKeyframeRequested.connect(self.remove_lip_keyframe)
            voice.lipKeyframeEditRequested.connect(self.edit_lip_keyframe)
            voice.lipDurationChangedRequested.connect(self.set_lip_duration)
            voice.lipAudioBrowseRequested.connect(self.browse_lip_audio)
            voice.lipAudioPlayRequested.connect(self.play_lip_audio)
            voice.lipAudioStopRequested.connect(self.stop_lip_audio)
            voice.openSoundSetRequested.connect(self.open_sound_set)
            voice.saveSoundSetRequested.connect(self.save_sound_set)
            voice.soundSetSlotEditRequested.connect(self.edit_sound_set_slot)
        destroyed = getattr(self.window, "destroyed", None)
        if destroyed is not None and hasattr(destroyed, "connect"):
            destroyed.connect(lambda _obj=None: self.stop_lip_audio())

        scaffold = getattr(self.window, "quest_scaffold_page", None)
        if scaffold is not None:
            scaffold.newRequested.connect(self.new_quest_definition)
            scaffold.openRequested.connect(self.open_quest_definition)
            scaffold.saveRequested.connect(self.save_quest_definition)
            scaffold.saveAsRequested.connect(lambda: self.save_quest_definition(save_as=True))
            scaffold.templateRequested.connect(self.load_quest_template)
            scaffold.validateRequested.connect(self.validate_quest_definition)
            scaffold.previewRequested.connect(self.preview_quest_scaffold)
            scaffold.commitRequested.connect(self.commit_quest_scaffold)

    def _initialise_pages(self) -> None:
        scaffold = getattr(self.window, "quest_scaffold_page", None)
        if scaffold is not None:
            scaffold.set_templates(QuestScaffoldService.template_names())
            self.new_quest_definition()
        tables = getattr(self.window, "twoda_globals_page", None)
        if tables is not None:
            tables.set_global_mode(False)

    def _dialog_open(self, title: str, filters: str) -> Path | None:
        path, _selected = QtWidgets.QFileDialog.getOpenFileName(self.window, title, "", filters)
        return Path(path) if path else None

    def _dialog_save(self, title: str, suggested: str, filters: str) -> Path | None:
        path, _selected = QtWidgets.QFileDialog.getSaveFileName(self.window, title, suggested, filters)
        return Path(path) if path else None

    def _status(self, message: str, page: Any | None = None, *, error: bool = False) -> None:
        if page is not None and hasattr(page, "set_status"):
            page.set_status(message, error=error)
        self.statusChanged.emit(str(message))

    def _fail(self, error: Exception | str, page: Any | None = None) -> None:
        message = str(error).strip() or "Narrative data operation failed."
        if isinstance(error, Exception):
            log.error("Narrative data operation failed: %s", error, exc_info=error)
        self._status(message, page, error=True)
        self.operationFailed.emit(message)

    @staticmethod
    def _source_name(document: object | None, fallback: str) -> str:
        source = getattr(document, "source_path", None)
        return str(Path(source).name) if source else fallback

    def _changed(self) -> None:
        self.contentChanged.emit()

    # Journal ---------------------------------------------------------

    def _present_journal(self) -> None:
        page = getattr(self.window, "quest_journal_page", None)
        if page is not None:
            page.set_journal(
                self.journal.quests if self.journal is not None else (),
                source_name=self._source_name(self.journal, "Unsaved global.jrl"),
            )

    def open_journal(self, path: str | Path | None = None) -> bool:
        page = getattr(self.window, "quest_journal_page", None)
        target = Path(path) if path else self._dialog_open("Open KOTOR Journal", "KOTOR journal (*.jrl)")
        if target is None:
            return False
        try:
            self.journal = NarrativeDataAuthoringService.open_jrl(target)
            self._present_journal()
            self._status(f"Opened {target}", page)
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    def save_journal(self, path: str | Path | None = None) -> bool:
        page = getattr(self.window, "quest_journal_page", None)
        if self.journal is None:
            self._fail("Create or open a JRL before saving.", page)
            return False
        target = Path(path) if path else self.journal.source_path
        if target is None:
            target = self._dialog_save("Save KOTOR Journal", "global.jrl", "KOTOR journal (*.jrl)")
        if target is None:
            return False
        try:
            saved = self.journal.save(target)
            self._present_journal()
            self._status(f"Saved and structurally verified {saved}", page)
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    def validate_journal(self) -> tuple[object, ...]:
        page = getattr(self.window, "quest_journal_page", None)
        diagnostics = self.journal.validate() if self.journal is not None else ()
        rows = [asdict(row) for row in diagnostics]
        blocked = any(bool(getattr(row, "blocking", False)) for row in diagnostics)
        summary = f"Journal {'blocked' if blocked else 'ready'}: {len(rows)} issue(s)"
        self.diagnosticsChanged.emit(rows, summary)
        self._status(summary, page, error=blocked)
        return diagnostics

    def add_quest(self, values: Mapping[str, Any] | object = ()) -> None:
        data = dict(values) if isinstance(values, Mapping) else {}
        self.journal = self.journal or JournalDocument()
        index = len(self.journal.quests) + 1
        try:
            self.journal.add_quest(
                JournalQuestRecord(
                    tag=str(data.get("tag") or f"new_quest_{index}"),
                    name=LocalizedText.from_english(str(data.get("name") or f"New Quest {index}")),
                    comment=str(data.get("comment") or ""),
                    priority=int(data.get("priority", 4)),
                )
            )
            self._present_journal()
            self._changed()
        except Exception as exc:
            self._fail(exc, getattr(self.window, "quest_journal_page", None))

    def remove_quest(self, quest_index: int) -> None:
        if self.journal is None:
            return
        self.journal.remove_quest(int(quest_index))
        self._present_journal()
        self._changed()

    def edit_quest(self, quest_index: int, values: Mapping[str, Any] | object) -> None:
        if self.journal is None:
            return
        data = dict(values) if isinstance(values, Mapping) else {}
        try:
            index = int(quest_index)
            if "name" in data:
                data["name"] = self.journal.quests[index].name.with_english(str(data["name"]))
            self.journal.update_quest(index, **data)
            self._present_journal()
            self._changed()
        except Exception as exc:
            self._fail(exc, getattr(self.window, "quest_journal_page", None))

    def add_journal_entry(self, quest_index: int, values: Mapping[str, Any] | object = ()) -> None:
        if self.journal is None:
            return
        data = dict(values) if isinstance(values, Mapping) else {}
        existing = self.journal.quests[int(quest_index)].entries
        state = int(data.get("entry_id", max((row.entry_id for row in existing), default=0) + 10))
        try:
            self.journal.add_entry(
                int(quest_index),
                JournalEntryRecord(
                    state,
                    LocalizedText.from_english(str(data.get("text") or "New journal state")),
                    bool(data.get("end", False)),
                    float(data.get("xp_percentage", 0.0)),
                ),
            )
            self._present_journal()
            self._changed()
        except Exception as exc:
            self._fail(exc, getattr(self.window, "quest_journal_page", None))

    def remove_journal_entry(self, quest_index: int, entry_index: int) -> None:
        if self.journal is None:
            return
        self.journal.remove_entry(int(quest_index), int(entry_index))
        self._present_journal()
        self._changed()

    def edit_journal_entry(self, quest_index: int, entry_index: int, values: Mapping[str, Any] | object) -> None:
        if self.journal is None:
            return
        data = dict(values) if isinstance(values, Mapping) else {}
        try:
            quest = int(quest_index)
            entry = int(entry_index)
            if "text" in data:
                data["text"] = self.journal.quests[quest].entries[entry].text.with_english(str(data["text"]))
            self.journal.update_entry(quest, entry, **data)
            self._present_journal()
            self._changed()
        except Exception as exc:
            self._fail(exc, getattr(self.window, "quest_journal_page", None))

    # 2DA and globals -------------------------------------------------

    def _active_table(self) -> TwoDADocument:
        if self._table_mode == "globals":
            self.globals = self.globals or GlobalVariableTable()
            return self.globals.table
        self.table = self.table or TwoDADocument()
        return self.table

    def _present_table(self) -> None:
        page = getattr(self.window, "twoda_globals_page", None)
        if page is None:
            return
        table = self._active_table()
        page.set_global_mode(self._table_mode == "globals")
        page.set_table(
            table.headers,
            table.labels,
            [table.row(index) for index in range(table.row_count)],
            source_name=self._source_name(table, "Unsaved globalcat.2da" if self._table_mode == "globals" else "Unsaved 2DA"),
        )
        page.set_history_state(
            bool(self._table_undo[self._table_mode]),
            bool(self._table_redo[self._table_mode]),
        )

    def _reset_table_history(self) -> None:
        self._table_undo[self._table_mode].clear()
        self._table_redo[self._table_mode].clear()

    def _mutate_table(self, operation: Callable[[TwoDADocument], object]) -> bool:
        page = getattr(self.window, "twoda_globals_page", None)
        table = self._active_table()
        before = table.snapshot()
        try:
            operation(table)
            after = table.snapshot()
            if after == before:
                self._present_table()
                return True
            undo = self._table_undo[self._table_mode]
            undo.append(before)
            del undo[:-_TABLE_HISTORY_LIMIT]
            self._table_redo[self._table_mode].clear()
            self._present_table()
            self._changed()
            return True
        except Exception as exc:
            table.restore(before)
            self._fail(exc, page)
            self._present_table()
            return False

    def set_table_mode(self, mode: str) -> None:
        self._table_mode = "globals" if str(mode).lower() == "globals" else "2da"
        self._present_table()

    def open_table(self, path: str | Path | None = None) -> bool:
        page = getattr(self.window, "twoda_globals_page", None)
        target = Path(path) if path else self._dialog_open("Open KOTOR 2DA", "KOTOR table (*.2da)")
        if target is None:
            return False
        try:
            if self._table_mode == "globals":
                self.globals = NarrativeDataAuthoringService.open_globals(target)
            else:
                self.table = NarrativeDataAuthoringService.open_2da(target)
            self._reset_table_history()
            self._present_table()
            self._status(f"Opened {target}", page)
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    def save_table(self, path: str | Path | None = None) -> bool:
        page = getattr(self.window, "twoda_globals_page", None)
        table = self._active_table()
        target = Path(path) if path else table.source_path
        if target is None:
            suggested = "globalcat.2da" if self._table_mode == "globals" else "new_table.2da"
            target = self._dialog_save("Save KOTOR 2DA", suggested, "KOTOR table (*.2da)")
        if target is None:
            return False
        try:
            saved = self.globals.save(target) if self._table_mode == "globals" and self.globals else table.save(target)
            self._present_table()
            self._status(f"Saved and structurally verified {saved}", page)
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    def export_table_patch(self, path: str | Path | None = None) -> bool:
        page = getattr(self.window, "twoda_globals_page", None)
        if self._table_mode == "globals":
            self._fail("Open the original globalcat.2da alongside the edited table before generating a merge patch.", page)
            return False
        if self.table is None or self.table.source_path is None:
            self._fail("Open an existing 2DA before exporting a conservative changes.ini patch.", page)
            return False
        target = Path(path) if path else self._dialog_save("Export TSLPatcher changes.ini", "changes.ini", "INI file (*.ini)")
        if target is None:
            return False
        try:
            original = TwoDADocument.load(self.table.source_path)
            text = self.table.export_changes_ini(original, self.table.source_path.name)
            target.write_text(text, encoding="utf-8")
            self._status(f"Exported conservative 2DA patch {target}", page)
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    def edit_table_cell(self, row: int, column: str, value: object) -> None:
        def edit(table: TwoDADocument) -> None:
            if self._table_mode == "globals" and self.globals is not None:
                if str(column) == "name":
                    self.globals.update_variable(int(row), name=str(value))
                    return
                if str(column) == "type":
                    self.globals.update_variable(int(row), value_type=str(value))
                    return
            table.set_cell(int(row), str(column), value)

        self._mutate_table(edit)

    def edit_table_label(self, row: int, label: str) -> None:
        self._mutate_table(lambda table: table.set_row_label(int(row), label))

    def add_table_row(self, values: Mapping[str, Any] | object = ()) -> None:
        self._mutate_table(
            lambda table: table.add_row(dict(values) if isinstance(values, Mapping) else {})
        )

    def remove_table_row(self, row: int) -> None:
        self._mutate_table(lambda table: table.remove_row(int(row)))

    def duplicate_table_rows(self, rows: object) -> None:
        if self._table_mode == "globals":
            self._fail(
                "Global variables must have unique names; use + Global to create a new variable.",
                getattr(self.window, "twoda_globals_page", None),
            )
            return
        selected = tuple(int(row) for row in rows) if isinstance(rows, (list, tuple)) else ()
        if selected:
            self._mutate_table(lambda table: table.duplicate_rows(selected))

    def add_table_column(self, name: str, default: object = "") -> None:
        if self._table_mode == "globals":
            self._fail("globalcat.2da column structure is fixed.", getattr(self.window, "twoda_globals_page", None))
            return
        self._mutate_table(lambda table: table.add_column(name, default))

    def rename_table_column(self, old_name: str, new_name: str) -> None:
        if self._table_mode == "globals":
            self._fail("globalcat.2da column structure is fixed.", getattr(self.window, "twoda_globals_page", None))
            return
        self._mutate_table(lambda table: table.rename_column(old_name, new_name))

    def remove_table_column(self, name: str) -> None:
        if self._table_mode == "globals":
            self._fail("globalcat.2da column structure is fixed.", getattr(self.window, "twoda_globals_page", None))
            return
        self._mutate_table(lambda table: table.remove_column(name))

    def copy_table_text(self, text: str) -> None:
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(str(text))
        self._status("Copied 2DA selection to the clipboard.", getattr(self.window, "twoda_globals_page", None))

    def paste_table_cells(self, edits: object) -> None:
        if not isinstance(edits, (list, tuple)):
            return

        def paste(table: TwoDADocument) -> None:
            table.apply_cell_edits(edits)
            if self._table_mode == "globals" and self.globals is not None:
                blocking = [diagnostic.message for diagnostic in self.globals.validate() if diagnostic.blocking]
                if blocking:
                    raise ValueError("Invalid globalcat.2da paste: " + "; ".join(blocking))

        if self._mutate_table(paste):
            self._status("Pasted clipboard cells as one undoable edit.", getattr(self.window, "twoda_globals_page", None))

    def undo_table(self) -> bool:
        table = self._active_table()
        undo = self._table_undo[self._table_mode]
        if not undo:
            return False
        current = table.snapshot()
        target = undo.pop()
        redo = self._table_redo[self._table_mode]
        redo.append(current)
        del redo[:-_TABLE_HISTORY_LIMIT]
        table.restore(target)
        self._present_table()
        self._changed()
        self._status("Undid 2DA edit.", getattr(self.window, "twoda_globals_page", None))
        return True

    def redo_table(self) -> bool:
        table = self._active_table()
        redo = self._table_redo[self._table_mode]
        if not redo:
            return False
        current = table.snapshot()
        target = redo.pop()
        undo = self._table_undo[self._table_mode]
        undo.append(current)
        del undo[:-_TABLE_HISTORY_LIMIT]
        table.restore(target)
        self._present_table()
        self._changed()
        self._status("Redid 2DA edit.", getattr(self.window, "twoda_globals_page", None))
        return True

    def add_global(self, name: str, value_type: str) -> None:
        self.globals = self.globals or GlobalVariableTable()
        self._table_mode = "globals"
        self._mutate_table(lambda _table: self.globals.add_variable(name, value_type))

    # TLK -------------------------------------------------------------

    def _present_talk(self) -> None:
        page = getattr(self.window, "talk_table_page", None)
        if page is not None:
            page.set_entries(
                self.talk_table.entries if self.talk_table is not None else (),
                language=str(self.talk_table.language_id) if self.talk_table is not None else "",
                source_name=self._source_name(self.talk_table, "Unsaved dialog.tlk"),
            )

    def open_talk_table(self, path: str | Path | None = None) -> bool:
        page = getattr(self.window, "talk_table_page", None)
        target = Path(path) if path else self._dialog_open("Open KOTOR Talk Table", "KOTOR talk table (*.tlk)")
        if target is None:
            return False
        try:
            self.talk_table = NarrativeDataAuthoringService.open_tlk(target)
            self._present_talk()
            self._status(f"Opened {target}", page)
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    def save_talk_table(self, path: str | Path | None = None) -> bool:
        page = getattr(self.window, "talk_table_page", None)
        if self.talk_table is None:
            self._fail("Open a TLK before saving.", page)
            return False
        target = Path(path) if path else self.talk_table.source_path
        if target is None:
            target = self._dialog_save("Save KOTOR Talk Table", "dialog.tlk", "KOTOR talk table (*.tlk)")
        if target is None:
            return False
        try:
            saved = self.talk_table.save(target)
            self._present_talk()
            self._status(f"Saved metadata-preserving TLK {saved}", page)
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    def add_talk_entry(self, values: Mapping[str, Any] | object = ()) -> None:
        self.talk_table = self.talk_table or TalkTableDocument()
        data = dict(values) if isinstance(values, Mapping) else {}
        try:
            self.talk_table.add_entry(
                str(data.get("text") or "New talk-table string"),
                voiceover=str(data.get("voiceover") or ""),
                sound_length=float(data.get("sound_length", 0.0)),
            )
            self._present_talk()
            self._changed()
        except Exception as exc:
            self._fail(exc, getattr(self.window, "talk_table_page", None))

    def edit_talk_entry(self, strref: int, values: Mapping[str, Any] | object) -> None:
        if self.talk_table is None:
            return
        try:
            self.talk_table.update_entry(int(strref), **(dict(values) if isinstance(values, Mapping) else {}))
            self._present_talk()
            self._changed()
        except Exception as exc:
            self._fail(exc, getattr(self.window, "talk_table_page", None))

    def install_talk_table(self, game_root: str | Path | None = None) -> bool:
        """Explicitly install the edited game-global TLK with backup/receipt."""

        page = getattr(self.window, "talk_table_page", None)
        if self.talk_table is None:
            self._fail("Open or create a TLK before installing it.", page)
            return False
        root = Path(game_root) if game_root else None
        if root is None:
            selected = QtWidgets.QFileDialog.getExistingDirectory(
                self.window,
                "Select the KOTOR game folder containing dialog.tlk",
                "",
            )
            if not selected:
                return False
            root = Path(selected)
        choice = QtWidgets.QMessageBox.warning(
            self.window,
            "Install Game-Global dialog.tlk",
            "This changes the selected game's global dialog.tlk. GhostStudio will create an exact backup and restore receipt first. Continue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Cancel,
        )
        if choice != QtWidgets.QMessageBox.Yes:
            return False
        try:
            from src.core.scripting.packaging import NarrativePackagingService

            result = NarrativePackagingService.install_global_tlk(
                self.talk_table.to_bytes(),
                root,
                game=str(self.game_provider() or "K2"),
            )
            if not result.ok:
                raise ValueError("; ".join(row.message for row in result.issues))
            self._status(
                f"Installed dialog.tlk with backup {result.backup_path} and receipt {result.receipt_path}",
                page,
            )
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    def restore_talk_table(
        self,
        receipt_path: str | Path | None = None,
        game_root: str | Path | None = None,
    ) -> bool:
        """Restore a prior TLK receipt while retaining the currently installed bytes."""

        page = getattr(self.window, "talk_table_page", None)
        receipt = Path(receipt_path) if receipt_path else self._dialog_open(
            "Open GhostStudio TLK Install Receipt",
            "GhostStudio install receipt (install-receipt.json);;JSON files (*.json)",
        )
        if receipt is None:
            return False
        root = Path(game_root) if game_root else None
        if root is None:
            selected = QtWidgets.QFileDialog.getExistingDirectory(
                self.window,
                "Select the KOTOR game folder to restore",
                "",
            )
            if not selected:
                return False
            root = Path(selected)
        choice = QtWidgets.QMessageBox.warning(
            self.window,
            "Restore Game-Global dialog.tlk",
            "Restore the backed-up dialog.tlk from this receipt? The currently installed file will be retained beside the receipt.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Cancel,
        )
        if choice != QtWidgets.QMessageBox.Yes:
            return False
        try:
            from src.core.scripting.packaging import NarrativePackagingService

            result = NarrativePackagingService.restore_global_tlk(receipt, root)
            if not result.ok:
                raise ValueError("; ".join(row.message for row in result.issues))
            self._status(
                f"Restored dialog.tlk; the replaced version is retained at {result.backup_path}",
                page,
            )
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    # LIP / SSF -------------------------------------------------------

    def _present_voice(self) -> None:
        page = getattr(self.window, "lip_sound_set_page", None)
        if page is None:
            return
        page.set_lip(
            self.lip.duration if self.lip else 0.0,
            self.lip.keyframes if self.lip else (),
            LipDocument.shape_names(),
            source_name=self._source_name(self.lip, "Unsaved LIP"),
        )
        page.set_sound_set(
            SoundSetDocument.slot_names(),
            self.sound_set.stringrefs if self.sound_set else (-1,) * 28,
            source_name=self._source_name(self.sound_set, "Unsaved SSF"),
        )

    def open_lip(self, path: str | Path | None = None) -> bool:
        page = getattr(self.window, "lip_sound_set_page", None)
        target = Path(path) if path else self._dialog_open("Open KOTOR Lip Animation", "KOTOR lip animation (*.lip)")
        if target is None:
            return False
        try:
            self.lip = NarrativeDataAuthoringService.open_lip(target)
            self._present_voice()
            self._status(f"Opened {target}", page)
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    def save_lip(self, path: str | Path | None = None) -> bool:
        page = getattr(self.window, "lip_sound_set_page", None)
        if self.lip is None:
            self._fail("Create or open a LIP resource before saving.", page)
            return False
        target = Path(path) if path else self.lip.source_path
        if target is None:
            target = self._dialog_save("Save KOTOR Lip Animation", "new_lip.lip", "KOTOR lip animation (*.lip)")
        if target is None:
            return False
        try:
            saved = self.lip.save(target)
            self._present_voice()
            self._status(f"Saved and structurally verified {saved}", page)
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    def _ensure_lip_audio_preview(self):
        if self._lip_audio_preview is not None:
            return self._lip_audio_preview
        from src.adapters.qt_audio.narrative_audio_preview import NarrativeAudioPreview

        preview = NarrativeAudioPreview(parent=self)
        preview.previewStarted.connect(self._lip_audio_started)
        preview.previewStopped.connect(self._lip_audio_stopped)
        preview.previewFailed.connect(self._lip_audio_failed)
        preview.progressChanged.connect(self._lip_audio_progress)
        self._lip_audio_preview = preview
        return preview

    def browse_lip_audio(self) -> str:
        selected, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self.window,
            "Choose Matching Dialogue Audio",
            "",
            "Audio files (*.wav *.mp3 *.ogg *.flac);;All files (*)",
        )
        if not selected:
            return ""
        page = getattr(self.window, "lip_sound_set_page", None)
        if page is not None:
            page.set_lip_audio_path(selected)
            page.set_lip_audio_state("Ready to preview matching audio.")
        return selected

    def play_lip_audio(self, path: str) -> bool:
        page = getattr(self.window, "lip_sound_set_page", None)
        target = str(path or "").strip()
        if not target:
            self._fail("Choose matching audio before starting the LIP preview.", page)
            return False
        return bool(self._ensure_lip_audio_preview().play_file(target))

    def stop_lip_audio(self) -> None:
        preview = self._lip_audio_preview
        if preview is not None:
            preview.stop()

    def _lip_audio_started(self, label: str) -> None:
        page = getattr(self.window, "lip_sound_set_page", None)
        if page is not None:
            page.set_lip_audio_state(f"Playing {label} — editor preview, not retail proof.", playing=True)

    def _lip_audio_stopped(self) -> None:
        page = getattr(self.window, "lip_sound_set_page", None)
        if page is not None:
            page.set_lip_audio_state("Audio preview stopped.")

    def _lip_audio_failed(self, message: str) -> None:
        page = getattr(self.window, "lip_sound_set_page", None)
        if page is not None:
            page.set_lip_audio_state(str(message), error=True)
        self.operationFailed.emit(str(message))

    def _lip_audio_progress(self, position_ms: int, duration_ms: int) -> None:
        page = getattr(self.window, "lip_sound_set_page", None)
        if page is not None:
            page.set_lip_audio_state(
                "Previewing matching audio; the closest viseme keyframe is selected.",
                position_ms=position_ms,
                duration_ms=duration_ms,
                playing=bool(getattr(self._lip_audio_preview, "active", False)),
            )

    def open_sound_set(self, path: str | Path | None = None) -> bool:
        page = getattr(self.window, "lip_sound_set_page", None)
        target = Path(path) if path else self._dialog_open("Open KOTOR Sound Set", "KOTOR sound set (*.ssf)")
        if target is None:
            return False
        try:
            self.sound_set = NarrativeDataAuthoringService.open_ssf(target)
            self._present_voice()
            self._status(f"Opened {target}", page)
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    def save_sound_set(self, path: str | Path | None = None) -> bool:
        page = getattr(self.window, "lip_sound_set_page", None)
        if self.sound_set is None:
            self._fail("Create or open an SSF resource before saving.", page)
            return False
        target = Path(path) if path else self.sound_set.source_path
        if target is None:
            target = self._dialog_save("Save KOTOR Sound Set", "new_soundset.ssf", "KOTOR sound set (*.ssf)")
        if target is None:
            return False
        try:
            saved = self.sound_set.save(target)
            self._present_voice()
            self._status(f"Saved all 28 SSF slots to {saved}", page)
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    def add_lip_keyframe(self, time: float, shape: int) -> None:
        self.lip = self.lip or LipDocument()
        try:
            self.lip.add_keyframe(time, shape)
            self._present_voice()
            self._changed()
        except Exception as exc:
            self._fail(exc, getattr(self.window, "lip_sound_set_page", None))

    def remove_lip_keyframe(self, index: int) -> None:
        if self.lip is None:
            return
        self.lip.remove_keyframe(int(index))
        self._present_voice()
        self._changed()

    def edit_lip_keyframe(self, index: int, values: Mapping[str, Any] | object) -> None:
        if self.lip is None:
            return
        try:
            self.lip.update_keyframe(int(index), **(dict(values) if isinstance(values, Mapping) else {}))
            self._present_voice()
            self._changed()
        except Exception as exc:
            self._fail(exc, getattr(self.window, "lip_sound_set_page", None))

    def set_lip_duration(self, duration: float) -> None:
        self.lip = self.lip or LipDocument()
        try:
            self.lip.set_duration(duration)
            self._present_voice()
            self._changed()
        except Exception as exc:
            self._fail(exc, getattr(self.window, "lip_sound_set_page", None))

    def edit_sound_set_slot(self, slot: int, stringref: int) -> None:
        self.sound_set = self.sound_set or SoundSetDocument()
        try:
            if int(slot) < 28:
                self.sound_set.set_slot(slot, stringref)
            else:
                self.sound_set.set_unknown_entry(slot, stringref)
            self._present_voice()
            self._changed()
        except Exception as exc:
            self._fail(exc, getattr(self.window, "lip_sound_set_page", None))

    # Quest definition / scaffold ------------------------------------

    def _quest_page(self) -> Any | None:
        return getattr(self.window, "quest_scaffold_page", None)

    def _quest_values(self) -> dict[str, Any]:
        page = self._quest_page()
        getter = getattr(page, "definition_payload", None)
        return dict(getter() or {}) if callable(getter) else {}

    def new_quest_definition(self) -> QuestDefinition | None:
        """Start a complete editable quest without writing any files."""

        page = self._quest_page()
        try:
            definition = QuestScaffoldService.definition(
                quest_tag="new_quest",
                display_name="New Quest",
                prefix="mod",
                template="simple",
                target_game=str(self.game_provider() or "K2"),
            )
            definition.extras["author_prefix"] = "mod"
            self.quest_definition = definition
            self._quest_preview = None
            if page is not None:
                page.set_definition(definition.to_dict(), source_name="Unsaved quest", dirty=False)
                page.set_status("New quest ready. Edit every collection, then validate and preview it.")
            return definition
        except Exception as exc:
            self._fail(exc, page)
            return None

    def load_quest_template(self, template: str) -> QuestDefinition | None:
        """Replace the editor with one of the preserved legacy quest patterns."""

        page = self._quest_page()
        values = self._quest_values()
        tag = str(values.get("quest_id") or "new_quest").strip() or "new_quest"
        name = str(values.get("name") or tag).strip() or tag
        prefix = str(values.get("author_prefix") or "mod").strip() or "mod"
        try:
            definition = QuestScaffoldService.definition(
                quest_tag=tag,
                display_name=name,
                prefix=prefix,
                template=str(template or "simple"),
                target_game=str(values.get("target_game") or self.game_provider() or "K2"),
            )
            definition.description = str(values.get("description") or "")
            definition.extras["author_prefix"] = prefix
            self.quest_definition = definition
            self._quest_preview = None
            if page is not None:
                page.set_definition(definition.to_dict(), source_name="Unsaved quest", dirty=True)
                page.set_status(
                    f"Loaded {template} template with {len(definition.states)} states and {len(definition.variables)} globals."
                )
            self._changed()
            return definition
        except Exception as exc:
            self._fail(exc, page)
            return None

    def open_quest_definition(
        self,
        path: str | Path | bytes | bytearray | memoryview | None = None,
    ) -> bool:
        """Open native or recovered legacy quest JSON into the editable model."""

        page = self._quest_page()
        target: str | Path | bytes | bytearray | memoryview | None = path
        if target is None:
            target = self._dialog_open(
                "Open Quest Definition",
                "Quest definitions (*.quest.json *.json);;All files (*)",
            )
        if target is None:
            return False
        try:
            definition = QuestDefinition.load(target)
            self.quest_definition = definition
            self._quest_preview = None
            source_name = (
                definition.source_path.name
                if definition.source_path is not None
                else "Recovered legacy quest"
            )
            if page is not None:
                page.set_definition(definition.to_dict(), source_name=source_name, dirty=False)
                page.set_validation(definition.validate())
            self._status(f"Opened editable quest definition: {source_name}", page)
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    def validate_quest_definition(
        self,
        values: Mapping[str, Any] | object | None = None,
    ) -> tuple[object, ...]:
        page = self._quest_page()
        try:
            data = dict(values) if isinstance(values, Mapping) else self._quest_values()
            definition = QuestDefinition.from_dict(data)
            if self.quest_definition is not None:
                definition.source_path = self.quest_definition.source_path
            self.quest_definition = definition
            diagnostics = definition.validate()
            if page is not None:
                page.set_validation(diagnostics)
            return diagnostics
        except Exception as exc:
            self._fail(exc, page)
            return ()

    def save_quest_definition(
        self,
        save_as: bool = False,
        path: str | Path | None = None,
    ) -> bool:
        """Atomically save the complete editable quest document."""

        page = self._quest_page()
        try:
            definition = QuestDefinition.from_dict(self._quest_values())
            if self.quest_definition is not None:
                definition.source_path = self.quest_definition.source_path
            blocking = [row.message for row in definition.validate() if row.blocking]
            if blocking:
                if page is not None:
                    page.set_validation(definition.validate())
                raise ValueError("Quest cannot be saved: " + "; ".join(blocking))
            target = Path(path) if path is not None else None
            if target is None and (save_as or definition.source_path is None):
                suggested = f"{definition.quest_id or 'new_quest'}.quest.json"
                target = self._dialog_save(
                    "Save Quest Definition",
                    suggested,
                    "Quest definitions (*.quest.json);;JSON files (*.json)",
                )
                if target is None:
                    return False
            saved = definition.save(target)
            self.quest_definition = definition
            self._quest_preview = None
            if page is not None:
                page.set_definition(definition.to_dict(), source_name=saved.name, dirty=False)
                page.set_validation(definition.validate())
            self._status(f"Saved loss-preserving quest definition: {saved}", page)
            self._changed()
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    def preview_quest_scaffold(self, values: Mapping[str, Any] | object) -> QuestScaffoldResult | None:
        page = self._quest_page()
        try:
            data = dict(values) if isinstance(values, Mapping) else {}
            if "states" in data or "variables" in data or "quest_id" in data:
                definition = QuestDefinition.from_dict(data)
                if self.quest_definition is not None:
                    definition.source_path = self.quest_definition.source_path
                result = QuestScaffoldService.scaffold_definition(definition)
                self.quest_definition = definition
            else:
                # Preserve the original small controller API for automation and
                # tests that still send quest_tag/display_name/prefix/template.
                result = QuestScaffoldService.scaffold(**data)
                self.quest_definition = result.definition
            self._quest_preview = result
            definition = result.definition
            states = tuple(definition.states) if definition is not None else ()
            if page is not None:
                page.set_preview(
                    {
                        "quest_tag": result.quest_tag,
                        "display_name": result.display_name,
                        "globals": [asdict(row) for row in result.globals],
                        "states": [
                            {
                                "state_id": row.state_id,
                                "journal_text": row.description or row.name,
                                "name": row.name,
                                "end": row.end,
                            }
                            for row in states
                        ],
                        "scripts": [asdict(row) for row in result.scripts],
                        "summary": f"{len(states)} journal states, {len(result.globals)} globals, and {len(result.scripts)} scripts are ready for review.",
                    }
                )
            return result
        except Exception as exc:
            self._quest_preview = None
            self._fail(exc, page)
            return None

    def commit_quest_scaffold(self) -> bool:
        result = self._quest_preview
        page = getattr(self.window, "quest_scaffold_page", None)
        if result is None:
            self._fail("Generate and review a quest preview first.", page)
            return False
        self.journal = self.journal or JournalDocument()
        self.globals = self.globals or GlobalVariableTable()
        if any(row.tag.casefold() == result.quest_tag.casefold() for row in self.journal.quests):
            self._fail(f"Journal quest already exists: {result.quest_tag}", page)
            return False
        existing_globals = {row.name.casefold() for row in self.globals.variables}
        if any(row.name.casefold() in existing_globals for row in result.globals):
            self._fail("One or more generated global variables already exist.", page)
            return False
        try:
            self.journal.add_quest(result.journal_quest)
            for variable in result.globals:
                self.globals.add_variable(variable.name, variable.value_type)
            if self.script_sink is not None:
                game = str(self.game_provider() or "K2")
                for script in result.scripts:
                    self.script_sink(game, script.resref, script.source)
            self._present_journal()
            if self._table_mode == "globals":
                self._present_table()
            self._changed()
            payload = {
                "quest_tag": result.quest_tag,
                "display_name": result.display_name,
                "script_count": len(result.scripts),
            }
            self.questScaffoldCommitted.emit(payload)
            self._status(
                f"Added {result.display_name}: journal, globals, and {len(result.scripts)} editable scripts.",
                page,
            )
            return True
        except Exception as exc:
            self._fail(exc, page)
            return False

    # Project/package handoff ----------------------------------------

    def resource_snapshots(self) -> tuple[tuple[str, str, bytes, str], ...]:
        """Return current data resources without writing them to disk."""

        rows: list[tuple[str, str, bytes, str]] = []
        if self.journal is not None:
            rows.append(((self.journal.source_path.stem if self.journal.source_path else "global"), "jrl", self.journal.to_bytes(), "runtime"))
        if self.table is not None:
            rows.append(((self.table.source_path.stem if self.table.source_path else "new_table"), "2da", self.table.to_bytes(), "runtime"))
        if self.globals is not None:
            rows.append(("globalcat", "2da", self.globals.to_bytes(), "runtime"))
        if self.talk_table is not None:
            rows.append(("dialog", "tlk", self.talk_table.to_bytes(), "global_install"))
        if self.lip is not None:
            rows.append(((self.lip.source_path.stem if self.lip.source_path else "new_lip"), "lip", self.lip.to_bytes(), "runtime"))
        if self.sound_set is not None:
            rows.append(((self.sound_set.source_path.stem if self.sound_set.source_path else "new_soundset"), "ssf", self.sound_set.to_bytes(), "runtime"))
        return tuple(rows)


__all__ = ["ScriptingDataController"]
