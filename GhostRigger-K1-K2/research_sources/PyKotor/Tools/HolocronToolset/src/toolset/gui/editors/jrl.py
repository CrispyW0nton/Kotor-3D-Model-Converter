"""JRL (journal) editor: quest entries, categories, and priority."""

from __future__ import annotations

from copy import deepcopy
from enum import Enum, auto
from typing import TYPE_CHECKING

from qtpy.QtGui import QColor, QPalette, QStandardItem, QStandardItemModel
from qtpy.QtWidgets import (
    QApplication,
    QMenu,
    QMessageBox,
    QShortcut,  # pyright: ignore[reportPrivateImportUsage]
    QTreeView,
)

from pykotor.resource.formats.gff import write_gff
from pykotor.resource.generics.jrl import JRL, JRLEntry, JRLQuest, JRLQuestPriority, dismantle_jrl, read_jrl
from pykotor.resource.type import ResourceType
from toolset.data.installation import HTInstallation
from toolset.gui.dialogs.edit.locstring import LocalizedStringDialog
from toolset.gui.editor import Editor

if TYPE_CHECKING:
    import os

    from qtpy.QtCore import QItemSelection, QPoint
    from qtpy.QtWidgets import QWidget

    from pykotor.resource.formats.twoda.twoda_data import TwoDA


class PhaseTask(Enum):
    """Enum for tracking quest phase tasks."""

    NONE = auto()
    KILL = auto()
    TALK = auto()
    ITEM = auto()
    LOCATION = auto()
    CUSTOM = auto()


class JRLEditor(Editor):
    """Journal Editor is designed for editing JRL files.

    Journal Editor is simular to the NWN counterpart which displays quests as root items in a tree plus their respective
    entries as child items. Entries that are marked as end nodes are highlighted a dark red color. The selected entry
    or quest can be edited at the bottom of the window.
    """

    # TODO(NickHugi): JRLEditor stores a tree model and a JRL instance. These two objects must be kept in sync with each other manually:
    # eg. if you code an entry to be deleted from the journal, ensure that you delete corresponding item in the tree.
    # It would be nice at some point to create our own implementation of QAbstractItemModel that automatically mirrors
    # the JRL object.

    def __init__(self, parent: QWidget | None, installation: HTInstallation | None = None):
        supported: list[ResourceType] = [ResourceType.JRL]
        super().__init__(parent, "Journal Editor", "journal", supported, supported, installation)

        self._jrl: JRL = JRL()
        self._model: QStandardItemModel = QStandardItemModel(self)
        from toolset.uic.qtpy.editors.jrl import Ui_MainWindow

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.journalTree.setModel(self._model)
        self.ui.journalTree.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self.ui.splitter.setSizes([99999999, 1])

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)
        self.resize(400, 250)

        from toolset.gui.editors.jrl_settings import JRLEditorSettings

        self._settings: JRLEditorSettings = JRLEditorSettings()

        self._setup_menus()
        self._add_help_action()
        self._setup_signals()
        self._setup_filter()
        if installation is not None:  # will only be none in the unittests
            self._setup_installation(installation)

        self.new()

    def _setup_signals(self):
        # Connect selection changed signal using selection model (more reliable than property assignment)
        sel_model = self.ui.journalTree.selectionModel()
        if sel_model is not None:
            sel_model.selectionChanged.connect(self.on_selection_changed)
        self.ui.journalTree.customContextMenuRequested.connect(self.on_context_menu_requested)

        self.ui.entryTextEdit.sig_double_clicked.connect(self.change_entry_text)

        # Make sure all these signals are excusively fired through user interaction NOT when values change
        # programmatically, otherwise values bleed into other items when onSelectionChanged() fires.
        self.ui.categoryNameEdit.sig_editing_finished.connect(self.on_value_updated)
        self.ui.categoryTag.editingFinished.connect(self.on_value_updated)
        self.ui.categoryPlotSelect.currentIndexChanged.connect(self.on_value_updated)
        self.ui.categoryPlanetSelect.activated.connect(self.on_value_updated)
        self.ui.categoryPrioritySelect.activated.connect(self.on_value_updated)
        self.ui.categoryCommentEdit.sig_key_released.connect(self.on_value_updated)
        self.ui.entryIdSpin.editingFinished.connect(self.on_value_updated)
        self.ui.entryXpSpin.editingFinished.connect(self.on_value_updated)
        from toolset.gui.common.localization import translate as tr

        self.ui.entryXpSpin.setToolTip(tr("The game multiplies the value set here by 1000 to calculate actual XP to award."))
        self.ui.entryEndCheck.clicked.connect(self.on_value_updated)

        # Register delete shortcut on both the editor and tree view to ensure it works
        QShortcut("Del", self).activated.connect(self.on_delete_shortcut)
        QShortcut("Del", self.ui.journalTree).activated.connect(self.on_delete_shortcut)

        self.ui.actionSettings.triggered.connect(self._show_settings)

    def _create_item_with_data(self, data) -> QStandardItem:
        """Create a QStandardItem and set its data.

        Args:
        ----
            data: The data to store in the item

        Returns:
        -------
            QStandardItem: The created item with data set
        """
        item = QStandardItem()
        item.setData(data)
        return item

    def _show_no_tag_warning(self):
        """Show a warning message when a quest has no tag set."""
        QMessageBox(QMessageBox.Icon.Warning, "No Tag", "This quest has no tag set.", parent=self).exec()

    def _setup_installation(self, installation: HTInstallation):
        self._installation = installation
        self.ui.categoryNameEdit.set_installation(installation)

        # Tag field: right-click → find quest journal references
        installation.setup_file_context_menu(
            self.ui.categoryTag,
            resref_type=[],
            enable_reference_search=True,
            reference_search_type="quest",
        )

        planets: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_PLANETS)
        if planets is None:
            from toolset.gui.common.localization import translate as tr, trf

            QMessageBox(
                QMessageBox.Icon.Warning,
                tr("Missing 2DA"),
                trf("'{file}.2da' is missing from your installation. Please reinstall your game, this should be in the read-only bifs.", file=HTInstallation.TwoDA_PLANETS),
            ).exec()
            return

        plot2DA: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_PLOT)
        if plot2DA:
            self.ui.categoryPlotSelect.clear()
            self.ui.categoryPlotSelect.setPlaceholderText("[Unset]")
            self.ui.categoryPlotSelect.set_items(
                [cell.title() for cell in plot2DA.get_column("label")],
                cleanup_strings=True,
            )
            self.ui.categoryPlotSelect.set_context(plot2DA, installation, HTInstallation.TwoDA_PLOT)

        self.ui.categoryPlanetSelect.clear()
        self.ui.categoryPlanetSelect.setPlaceholderText("[Unset]")
        for row in planets:
            text = self._installation.talktable().string(row.get_integer("name", 0)) or row.get_string("label").replace("_", " ").title()
            self.ui.categoryPlanetSelect.addItem(text)
        self.ui.categoryPlanetSelect.set_context(planets, self._installation, HTInstallation.TwoDA_PLANETS)

    def load(
        self,
        filepath: os.PathLike | str,
        resref: str,
        restype: ResourceType,
        data: bytes,
    ):
        """Load JRL from bytes. Defaults when field missing: Categories optional; per-category Comment "", Name empty, PlanetID/PlotIndex 0, Priority 0 (LOWEST), Tag ""; per-entry End 0, ID 0, Text empty, XP_Percentage 0.0. K1 LoadJournal @ 0x004f17d0 (LoadCharacterFromIFO @ 0x00561e30), TSL @ 0x006fd830 (caller 0x00701d10); module format Categories/EntryList."""
        super().load(filepath, resref, restype, data)

        self._jrl = read_jrl(data)

        self._model.clear()
        self.ui.filterEdit.clear()
        for quest in self._jrl.quests:
            quest_item = self._create_item_with_data(quest)
            self.refresh_quest_item(quest_item)
            self._model.appendRow(quest_item)

            for entry in quest.entries:
                entry_item = self._create_item_with_data(entry)
                self.refresh_entry_item(entry_item)
                quest_item.appendRow(entry_item)

    def build(self) -> tuple[bytes, bytes]:
        """Build JRL bytes from editor state. Write values match engine/module layout (Categories/EntryList, Comment, Name, PlanetID, PlotIndex, Priority, Tag, End, ID, Text, XP_Percentage). K1 LoadJournal @ 0x004f17d0, TSL @ 0x006fd830."""
        data = bytearray()
        write_gff(dismantle_jrl(self._jrl), data)
        return data, b""

    def new(self):
        super().new()
        self._jrl = JRL()
        self._model.clear()

    def refresh_entry_item(self, entryItem: QStandardItem):
        """Updates the specified item's (storing entry data) text.

        Args:
        ----
            entryItem: The item to refresh.
        """
        if self._installation is None:
            text: str = f"[{entryItem.data().entry_id}] {entryItem.data().text}"
        else:
            text: str = f"[{entryItem.data().entry_id}] {self._installation.string(entryItem.data().text)}"

        # Use QPalette for text colors instead of hardcoded values
        palette: QPalette = self.palette()
        if entryItem.data().end:
            # For end entries, use a distinct but palette-based color
            # Use Link color or adjust WindowText to indicate it's an end entry
            end_color = palette.color(QPalette.ColorRole.Link)
            if not end_color.isValid() or end_color == QColor(0, 0, 0):
                # Fallback: use a slightly adjusted WindowText color
                base_color = palette.color(QPalette.ColorRole.WindowText)
                end_color = QColor(min(255, base_color.red() + 50), max(0, base_color.green() - 30), max(0, base_color.blue() - 30))
            entryItem.setForeground(end_color)
        else:
            # Normal entries use standard WindowText color from palette
            entryItem.setForeground(palette.color(QPalette.ColorRole.WindowText))

        entryItem.setText(text)

    def refresh_quest_item(self, questItem: QStandardItem):
        """Updates the specified item's (storing quest data) text.

        Args:
        ----
            questItem: The item to refresh.
        """
        if self._installation is None:
            text: str = questItem.data().name or "[Unnamed]"
        else:
            text: str = self._installation.string(questItem.data().name, "[Unnamed]")
        questItem.setText(text)

    def change_quest_name(self):
        """Opens a LocalizedStringDialog for editing the name of the selected quest."""
        assert self._installation is not None, "Installation is None"
        dialog = LocalizedStringDialog(self, self._installation, self.ui.categoryNameEdit.locstring())
        if dialog.exec():
            self.ui.categoryNameEdit.set_installation(self._installation)
            self.on_value_updated()
            item: QStandardItem = self._get_item()
            quest: JRLQuest = item.data()
            quest.name = dialog.locstring
            self.refresh_quest_item(item)

    def change_entry_text(self):
        """Opens a LocalizedStringDialog for editing the text of the selected entry."""
        assert self._installation is not None, "Installation is None"
        assert self.ui.entryTextEdit.locstring is not None, "Entry text is None"
        dialog = LocalizedStringDialog(self, self._installation, self.ui.entryTextEdit.locstring)
        if dialog.exec():
            self._load_locstring(self.ui.entryTextEdit, dialog.locstring)
            self.on_value_updated()
            item: QStandardItem = self._get_item()
            entry: JRLEntry = item.data()
            entry.text = dialog.locstring
            self.refresh_entry_item(item)

    def remove_quest(self, questItem: QStandardItem):
        """Removes a quest from the journal.

        Args:
        ----
            questItem: The item in the tree that stores the quest.
        """
        quest: JRLQuest = questItem.data()
        self._model.removeRow(questItem.row())
        self._jrl.quests.remove(quest)

    def remove_entry(self, entryItem: QStandardItem):
        """Removes an entry from the journal.

        Args:
        ----
            entryItem: The item in the tree that stores the entry.
        """
        entry: JRLEntry = entryItem.data()
        entry_parent = entryItem.parent()
        if entry_parent is not None:
            entry_parent.removeRow(entryItem.row())
        for quest in self._jrl.quests:
            if entry in quest.entries:
                quest.entries.remove(entry)
                break

    def add_entry(self, quest_item: QStandardItem, newEntry: JRLEntry):
        """Adds a entry to a quest in the journal.

        Args:
        ----
            questItem: The item in the tree that stores the quest.
            newEntry: The entry to add into the quest.
        """
        entry_item = self._create_item_with_data(newEntry)
        self.refresh_entry_item(entry_item)
        quest_item.appendRow(entry_item)
        quest: JRLQuest = quest_item.data()
        quest.entries.append(newEntry)
        # Expand the quest item so entries are visible
        quest_index = quest_item.index()
        if quest_index.isValid():
            self.ui.journalTree.expand(quest_index)

    def add_quest(self, newQuest: JRLQuest):
        """Adds a quest to the journal.

        Args:
        ----
            newQuest: The new quest to be added in.
        """
        quest_item = self._create_item_with_data(newQuest)
        self.refresh_quest_item(quest_item)
        self._model.appendRow(quest_item)
        self._jrl.quests.append(newQuest)

    def on_value_updated(self, *args, **kwargs):
        """Updates the selected item in the journal tree when values change.

        This method should be connected to all the widgets that store data related quest or entry text (besides the
        ones storing localized strings, those are updated elsewhere). This method will update either all the values
        for an entry or quest based off the aforementioned widgets.
        """
        # Check if there's a selection before trying to get the item
        if not self.ui.journalTree.selectedIndexes():
            return
        item: QStandardItem = self._get_item()
        data = item.data()
        if isinstance(data, JRLQuest):  # sourcery skip: extract-method
            data.name = self.ui.categoryNameEdit.locstring()
            data.tag = self.ui.categoryTag.text()
            data.plot_index = self.ui.categoryPlotSelect.currentIndex()
            data.planet_id = self.ui.categoryPlanetSelect.currentIndex() - 1
            data.priority = JRLQuestPriority(self.ui.categoryPrioritySelect.currentIndex())
            data.comment = self.ui.categoryCommentEdit.toPlainText()
        elif isinstance(data, JRLEntry):
            if self.ui.entryTextEdit.locstring is not None:
                data.text = self.ui.entryTextEdit.locstring
            data.end = self.ui.entryEndCheck.isChecked()
            data.xp_percentage = self.ui.entryXpSpin.value()
            data.entry_id = self.ui.entryIdSpin.value()
            self.refresh_entry_item(item)

    def on_selection_changed(self, selection: QItemSelection, deselected: QItemSelection):
        """Updates UI on journal tree selection change.

        This method should be connected to a signal that emits when selection changes for the journalTree widget. It
        will update the widget values that store data for either entries or quests, depending what has been selected
        in the tree.

        Args:
        ----
            selection: QItemSelection - Current selection
            deselected: QItemSelection - Previously selected
        """
        QTreeView.selectionChanged(self.ui.journalTree, selection, deselected)

        # Block signals to prevent recursive updates
        widgets_to_block: list[QWidget] = [
            self.ui.categoryCommentEdit,
            self.ui.entryTextEdit,
            self.ui.categoryNameEdit,
            self.ui.categoryTag,
            self.ui.categoryPlotSelect,
            self.ui.categoryPlanetSelect,
            self.ui.categoryPrioritySelect,
            self.ui.entryEndCheck,
            self.ui.entryXpSpin,
            self.ui.entryIdSpin,
        ]

        for widget in widgets_to_block:
            widget.blockSignals(True)

        try:
            if selection.indexes():
                index = selection.indexes()[0]
                item = self._model.itemFromIndex(index)
                if item is None:
                    return

                data = item.data()
                if data is None:
                    return
                if isinstance(data, JRLQuest):
                    self.ui.questPages.setCurrentIndex(0)
                    if self._installation is not None:
                        self.ui.categoryNameEdit.set_locstring(data.name)
                    # Set tag - handle None/empty string
                    tag_text = data.tag if data.tag is not None else ""
                    self.ui.categoryTag.setText(tag_text)
                    # Set plot index - ComboBox2DA handles row indices
                    self.ui.categoryPlotSelect.setCurrentIndex(data.plot_index)
                    # Set planet ID - combobox index = planet_id + 1 (0 is [Unset])
                    planet_combo_index = data.planet_id + 1
                    if planet_combo_index < 0:
                        planet_combo_index = 0
                    if planet_combo_index < self.ui.categoryPlanetSelect.count():
                        self.ui.categoryPlanetSelect.setCurrentIndex(planet_combo_index)
                    else:
                        self.ui.categoryPlanetSelect.setCurrentIndex(0)
                    # Set priority
                    self.ui.categoryPrioritySelect.setCurrentIndex(data.priority.value)
                    # Set comment - handle None/empty string
                    comment_text = data.comment if data.comment is not None else ""
                    self.ui.categoryCommentEdit.setPlainText(comment_text)

                elif isinstance(data, JRLEntry):
                    self.ui.questPages.setCurrentIndex(1)
                    # Load entry text - works with or without installation
                    self._load_locstring(self.ui.entryTextEdit, data.text)
                    self.ui.entryEndCheck.setChecked(data.end)
                    self.ui.entryXpSpin.setValue(data.xp_percentage)
                    self.ui.entryIdSpin.setValue(data.entry_id)
        finally:
            # Always unblock signals
            for widget in widgets_to_block:
                widget.blockSignals(False)

    def on_context_menu_requested(self, point: QPoint):
        """Handle context menu requests for the journal tree widget.

        This method should be connected to the customContextMenuRequested of the journalTree object. This will popup the
        context menu and display various options depending on if there is an item selected in the tree and what kind
        of data the item stores (Quest or Entry).

        Args:
        ----
            point: QPoint: The position of the context menu request
        """
        index = self.ui.journalTree.indexAt(point)
        item = self._model.itemFromIndex(index)

        menu = QMenu(self)

        if item:
            item = self._get_item()
            data = item.data()

            if isinstance(data, JRLQuest):
                menu.addAction("Rename Quest...").triggered.connect(lambda: self.change_quest_name())
                menu.addSeparator()
                menu.addAction("Add Entry").triggered.connect(lambda: self.add_entry(item, JRLEntry()))
                menu.addAction("Duplicate Quest").triggered.connect(lambda: self._duplicate_quest(item))
                menu.addAction("Remove Quest").triggered.connect(lambda: self.remove_quest(item))
                menu.addSeparator()
                sort_menu = menu.addMenu("Sort Entries")
                sort_menu.addAction("By ID (Ascending)").triggered.connect(lambda: self._sort_entries(item, ascending=True))
                sort_menu.addAction("By ID (Descending)").triggered.connect(lambda: self._sort_entries(item, ascending=False))
                menu.addAction("Move Quest Up").triggered.connect(lambda: self._move_quest(item, -1))
                menu.addAction("Move Quest Down").triggered.connect(lambda: self._move_quest(item, +1))
                menu.addSeparator()
                menu.addAction("Copy Tag").triggered.connect(lambda: self._copy_quest_tag(item))
                if hasattr(self, "_installation") and self._installation is not None:
                    menu.addSeparator()
                    menu.addAction("Find Scripts...").triggered.connect(lambda: self._find_quest_scripts(item))
                    menu.addAction("Find Dialogs...").triggered.connect(lambda: self._find_quest_dialogs(item))
                    menu.addAction("Find All Tag References...").triggered.connect(lambda: self._find_quest_all(item))
                # Always show Add Quest at bottom for easy discoverability
                menu.addSeparator()
                menu.addAction("Add Quest").triggered.connect(lambda: self.add_quest(JRLQuest()))

            elif isinstance(data, JRLEntry):
                menu.addAction("Edit Entry Text...").triggered.connect(lambda: self.change_entry_text())
                menu.addAction("Duplicate Entry").triggered.connect(lambda: self._duplicate_entry(item))
                menu.addAction("Remove Entry").triggered.connect(lambda: self.remove_entry(item))
                menu.addSeparator()
                menu.addAction("Move Entry Up").triggered.connect(lambda: self._move_entry(item, -1))
                menu.addAction("Move Entry Down").triggered.connect(lambda: self._move_entry(item, +1))
        else:
            menu.addAction("Add Quest").triggered.connect(lambda: self.add_quest(JRLQuest()))

        jrlTree_viewport = self.ui.journalTree.viewport()
        assert jrlTree_viewport is not None, "Journal tree viewport is None"
        menu.popup(jrlTree_viewport.mapToGlobal(point))

    # ── Filter ─────────────────────────────────────────────────────────────

    def _setup_filter(self):
        """Connect filter bar signals."""
        self.ui.filterEdit.textChanged.connect(self._on_filter_changed)
        self.ui.filterClearBtn.clicked.connect(self.ui.filterEdit.clear)

    def _on_filter_changed(self, text: str):
        """Show/hide tree items based on the filter text and mode."""
        text = text.strip().lower()
        mode = self._settings.filter_mode
        root = self._model.invisibleRootItem()
        for row in range(root.rowCount()):
            quest_item = root.child(row)
            if quest_item is None:
                continue
            quest: JRLQuest = quest_item.data()
            if not text:
                self.ui.journalTree.setRowHidden(row, self.ui.journalTree.rootIndex(), False)
                for erow in range(quest_item.rowCount()):
                    self.ui.journalTree.setRowHidden(erow, quest_item.index(), False)
                continue

            quest_name = self._installation.string(quest.name, "") if hasattr(self, "_installation") and self._installation else ""
            quest_tag = quest.tag or ""
            quest_matches = text in quest_name.lower() or text in quest_tag.lower()

            entry_matches = False
            for erow in range(quest_item.rowCount()):
                entry_item = quest_item.child(erow)
                if entry_item is None:
                    continue
                entry: JRLEntry = entry_item.data()
                entry_text = self._installation.string(entry.text, "") if hasattr(self, "_installation") and self._installation else ""
                entry_id_str = str(entry.entry_id)
                ematch = text in entry_text.lower() or text in entry_id_str
                hide_entry = False
                if mode == "all_levels":
                    hide_entry = not (quest_matches or ematch)
                elif mode == "quest_only":
                    hide_entry = False  # show all entries if quest matches; hide quest handled below
                else:  # smart
                    hide_entry = not ematch and not quest_matches
                self.ui.journalTree.setRowHidden(erow, quest_item.index(), hide_entry)
                if ematch:
                    entry_matches = True

            if mode == "quest_only":
                hide_quest = not quest_matches
            elif mode == "all_levels":
                hide_quest = not quest_matches and not entry_matches
            else:  # smart
                hide_quest = not quest_matches and not entry_matches
            self.ui.journalTree.setRowHidden(row, self.ui.journalTree.rootIndex(), hide_quest)
            if not hide_quest and quest_item.rowCount() > 0:
                self.ui.journalTree.expand(quest_item.index())

    # ── Settings ───────────────────────────────────────────────────────────

    def _show_settings(self):
        """Open the JRL editor settings dialog."""
        from toolset.gui.editors.jrl_settings import JRLSettingsDialog

        dlg = JRLSettingsDialog(self, self._settings)
        dlg.exec()
        # Re-apply filter after settings change
        self._on_filter_changed(self.ui.filterEdit.text())

    # ── Quest manipulation ─────────────────────────────────────────────────

    def _duplicate_quest(self, quest_item: QStandardItem):
        """Deep-copy a quest and append it after the original."""
        original: JRLQuest = quest_item.data()
        new_quest = deepcopy(original)
        new_quest.tag = (new_quest.tag or "") + "_copy"
        self.add_quest(new_quest)
        new_index = self._model.index(self._model.rowCount() - 1, 0)
        self.ui.journalTree.setCurrentIndex(new_index)
        self.ui.journalTree.scrollTo(new_index)

    def _move_quest(self, quest_item: QStandardItem, direction: int):
        """Move a quest up (-1) or down (+1) in the list."""
        root = self._model.invisibleRootItem()
        row = quest_item.row()
        new_row = row + direction
        if new_row < 0 or new_row >= root.rowCount():
            return
        taken = root.takeRow(row)
        root.insertRow(new_row, taken)
        quest: JRLQuest = quest_item.data()
        self._jrl.quests.remove(quest)
        self._jrl.quests.insert(new_row, quest)
        new_index = quest_item.index()
        self.ui.journalTree.setCurrentIndex(new_index)

    def _sort_entries(self, quest_item: QStandardItem, *, ascending: bool = True):
        """Sort all child entry items of a quest by entry_id."""
        quest: JRLQuest = quest_item.data()
        quest.entries.sort(key=lambda e: e.entry_id, reverse=not ascending)
        # Rebuild child items to match sorted order
        quest_item.removeRows(0, quest_item.rowCount())
        for entry in quest.entries:
            entry_item = self._create_item_with_data(entry)
            self.refresh_entry_item(entry_item)
            quest_item.appendRow(entry_item)

    def _copy_quest_tag(self, quest_item: QStandardItem):
        """Copy the quest tag to the clipboard."""
        quest: JRLQuest = quest_item.data()
        QApplication.clipboard().setText(quest.tag or "")

    # ── Entry manipulation ─────────────────────────────────────────────────

    def _duplicate_entry(self, entry_item: QStandardItem):
        """Deep-copy an entry and append after the original."""
        parent_item = entry_item.parent()
        if parent_item is None:
            return
        original: JRLEntry = entry_item.data()
        new_entry = deepcopy(original)
        new_entry.entry_id = new_entry.entry_id + 1
        self.add_entry(parent_item, new_entry)

    def _move_entry(self, entry_item: QStandardItem, direction: int):
        """Move an entry up (-1) or down (+1) within its parent quest."""
        parent_item = entry_item.parent()
        if parent_item is None:
            return
        row = entry_item.row()
        new_row = row + direction
        if new_row < 0 or new_row >= parent_item.rowCount():
            return
        taken = parent_item.takeRow(row)
        parent_item.insertRow(new_row, taken)
        quest: JRLQuest = parent_item.data()
        entry: JRLEntry = entry_item.data()
        quest.entries.remove(entry)
        quest.entries.insert(new_row, entry)
        new_index = entry_item.index()
        self.ui.journalTree.setCurrentIndex(new_index)

    # ── Reference searching ────────────────────────────────────────────────

    def _ensure_installation(self) -> HTInstallation | None:
        """Check if installation is available and return it, or None if not."""
        if not hasattr(self, "_installation") or self._installation is None:
            return None
        return self._installation

    def _find_quest_scripts(self, quest_item: QStandardItem):
        """Find NCS/NSS scripts that reference this quest tag."""
        installation = self._ensure_installation()
        if installation is None:
            return
        quest: JRLQuest = quest_item.data()
        tag = quest.tag or ""
        if not tag:
            self._show_no_tag_warning()
            return
        installation._find_references(self, tag, "quest")

    def _find_quest_dialogs(self, quest_item: QStandardItem):
        """Find DLG dialogs that reference this quest tag in their Quest field."""
        installation = self._ensure_installation()
        if installation is None:
            return
        quest: JRLQuest = quest_item.data()
        tag = quest.tag or ""
        if not tag:
            self._show_no_tag_warning()
            return
        installation._find_references(self, tag, "quest")

    def _find_quest_all(self, quest_item: QStandardItem):
        """Find all resources that reference this quest tag (scripts + dialogs + tag)."""
        installation = self._ensure_installation()
        if installation is None:
            return
        quest: JRLQuest = quest_item.data()
        tag = quest.tag or ""
        if not tag:
            self._show_no_tag_warning()
            return
        installation._find_references(self, tag, "tag")

    # ── Internal helpers ───────────────────────────────────────────────────

    def on_delete_shortcut(self):
        """Deletes selected shortcut from journal tree.

        This method should be connected to the activated signal of a QShortcut. The method will delete the selected
        item from the tree.

        Args:
        ----
            self: The class instance
        """
        if self.ui.journalTree.selectedIndexes():
            item = self._get_item()
            if item.parent() is None:  # ie. root item, therefore quest
                self.remove_quest(item)
            else:  # child item, therefore entry
                self.remove_entry(item)

    def _get_item(self) -> QStandardItem:
        index = self.ui.journalTree.selectedIndexes()[0]
        result = self._model.itemFromIndex(index)
        assert result is not None, f"Could not find journalTree index '{index}'"
        return result

if __name__ == "__main__":
    import sys

    from toolset.gui.editors.standalone import launch_editor_cli

    sys.exit(launch_editor_cli("jrl"))
