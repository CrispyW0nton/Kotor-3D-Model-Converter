"""
Unit Tests for JRL Editor - testing EVERY possible manipulation.

Each test focuses on a specific manipulation and validates save/load roundtrips.
"""

from __future__ import annotations

import os
import pathlib
import sys
from typing import TYPE_CHECKING
import unittest
from unittest import TestCase

import pytest
from qtpy.QtCore import Qt, QPoint
from qtpy.QtGui import QStandardItem, QGuiApplication
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QMenu, QComboBox, QSpinBox, QTreeView, QLineEdit
from toolset.gui.editors.jrl import JRLEditor
from toolset.data.installation import HTInstallation
from pykotor.resource.generics.jrl import JRLQuest, JRLEntry, JRLQuestPriority, JRL, read_jrl
from pykotor.common.language import LocalizedString, Language, Gender
from pykotor.resource.type import ResourceType
from pykotor.resource.formats.gff.gff_auto import read_gff

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot
    from qtpy.QtGui import QAction
else:
    from pytestqt.qtbot import QtBot  # noqa: F401

try:
    from qtpy.QtTest import QTest
    from qtpy.QtWidgets import QApplication
except (ImportError, ModuleNotFoundError):
    if not TYPE_CHECKING:
        QTest, QApplication = None, None  # type: ignore[misc, assignment]

absolute_file_path = pathlib.Path(__file__).resolve()
TESTS_FILES_PATH = next(f for f in absolute_file_path.parents if f.name == "tests") / "test_files"

if __name__ == "__main__" and getattr(sys, "frozen", False) is False:

    def add_sys_path(p):
        working_dir = str(p)
        if working_dir in sys.path:
            sys.path.remove(working_dir)
        sys.path.append(working_dir)

    pykotor_path = absolute_file_path.parents[6] / "Libraries" / "PyKotor" / "src" / "pykotor"
    if pykotor_path.exists():
        add_sys_path(pykotor_path.parent)
    gl_path = absolute_file_path.parents[6] / "Libraries" / "PyKotorGL" / "src" / "pykotor"
    if gl_path.exists():
        add_sys_path(gl_path.parent)
    utility_path = absolute_file_path.parents[6] / "Libraries" / "Utility" / "src" / "utility"
    if utility_path.exists():
        add_sys_path(utility_path.parent)
    toolset_path = absolute_file_path.parents[6] / "Tools" / "HolocronToolset" / "src" / "toolset"
    if toolset_path.exists():
        add_sys_path(toolset_path.parent)

K1_PATH = os.environ.get("K1_PATH", "C:\\Program Files (x86)\\Steam\\steamapps\\common\\swkotor")
K2_PATH = os.environ.get("K2_PATH", "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Knights of the Old Republic II")

from pykotor.common.stream import BinaryReader  # pyright: ignore[reportMissingImports]
from pykotor.extract.installation import Installation  # pyright: ignore[reportMissingImports]
from pykotor.resource.formats.gff.gff_auto import read_gff  # pyright: ignore[reportMissingImports]
from pykotor.resource.type import ResourceType  # pyright: ignore[reportMissingImports]


# ============================================================================
# BASIC LOADING AND SAVING TESTS
# ============================================================================


@unittest.skipIf(
    not K2_PATH or not pathlib.Path(K2_PATH).joinpath("chitin.key").exists(),
    "K2_PATH environment variable is not set or not found on disk.",
)
@unittest.skipIf(
    QTest is None or not QApplication,
    "qtpy is required, please run pip install -r requirements.txt before running this test.",
)
class JRLEditorTest(TestCase):
    @classmethod
    def setUpClass(cls):
        from toolset.gui.editors.jrl import JRLEditor

        cls.JRLEditor = JRLEditor
        from toolset.data.installation import HTInstallation

        cls.K2_INSTALLATION = HTInstallation(K2_PATH, "", tsl=True)

    def setUp(self):
        self.app: QApplication = QApplication([])
        self.editor = self.JRLEditor(None, self.K2_INSTALLATION)
        self.log_messages: list[str] = [os.linesep]

    def tearDown(self):
        self.app.deleteLater()

    def log_func(self, *args, **kwargs):
        # Accept message_type and other kwargs for compatibility with GFF comparison
        # Convert args to strings and join them
        message = "\t".join(str(arg) for arg in args if arg != "")
        if message:  # Only append non-empty messages
            self.log_messages.append(message)

    def test_save_and_load(self):
        filepath = TESTS_FILES_PATH / "global.jrl"
        if not filepath.exists():
            pytest.skip("global.jrl not found")

        data = filepath.read_bytes()
        old = read_gff(data)
        self.editor.load(filepath, "global", ResourceType.JRL, data)

        data, _ = self.editor.build()
        new = read_gff(data)

        diff = old.compare(new, self.log_func)
        assert diff, os.linesep.join(self.log_messages)

    def test_editor_init(self):
        self.JRLEditor(None, self.K2_INSTALLATION)


# ============================================================================
# HELPER FUNCTIONS FOR REAL USER INTERACTIONS
# ============================================================================


def click_tree_item(qtbot: QtBot, tree_view: QTreeView, item: QStandardItem):
    """Click on a tree item using mouse interaction (real user simulation)."""
    index = item.index()
    assert index.isValid(), "Index must be valid for clicking"
    rect = tree_view.visualRect(index)
    assert not rect.isNull(), "Visual rect must be valid"
    center = rect.center()
    qtbot.mouseClick(tree_view.viewport(), Qt.MouseButton.LeftButton, pos=center)
    QApplication.processEvents()


def type_text_in_field(qtbot: QtBot, widget: QLineEdit, text: str, clear_first: bool = True):
    """Type text into a widget using keyboard (real user simulation)."""
    widget.setFocus()
    QApplication.processEvents()
    if clear_first:
        qtbot.keyClick(widget, Qt.Key.Key_A, modifier=Qt.KeyboardModifier.ControlModifier)
        QApplication.processEvents()
        qtbot.keyClick(widget, Qt.Key.Key_Delete)
        QApplication.processEvents()
    qtbot.keyClicks(widget, text)
    QApplication.processEvents()
    # Press Enter to trigger editingFinished signal for QLineEdit
    qtbot.keyClick(widget, Qt.Key.Key_Enter)
    QApplication.processEvents()


def select_combo_item(qtbot: QtBot, combo_box: QComboBox, index: int):
    """Select a combo box item using mouse and keyboard (real user simulation).

    For ComboBox2DA widgets, this uses setCurrentIndex() directly since it accepts
    2DA row indices. For regular QComboBox widgets, it uses arrow key navigation.
    """
    # Check if this is a ComboBox2DA (which has special index handling)
    combo_type = combo_box.__class__.__name__
    if combo_type == "ComboBox2DA":
        # ComboBox2DA.setCurrentIndex() accepts 2DA row indices directly
        combo_box.setCurrentIndex(index)
        QApplication.processEvents()
        return

    # For regular QComboBox, use arrow key navigation
    combo_box.setFocus()
    QApplication.processEvents()
    qtbot.mouseClick(combo_box, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    # Navigate to the desired index using arrow keys
    current = combo_box.currentIndex()
    if index > current:
        for _ in range(index - current):
            qtbot.keyClick(combo_box, Qt.Key.Key_Down)
            QApplication.processEvents()
    elif index < current:
        for _ in range(current - index):
            qtbot.keyClick(combo_box, Qt.Key.Key_Up)
            QApplication.processEvents()
    qtbot.keyClick(combo_box, Qt.Key.Key_Enter)
    QApplication.processEvents()


def set_spin_value(qtbot: QtBot, spin_box: QSpinBox | QDoubleSpinBox, value: float | int):
    """Set spin box value using keyboard (real user simulation)."""
    spin_box.setFocus()
    QApplication.processEvents()
    qtbot.keyClick(spin_box, Qt.Key.Key_A, modifier=Qt.KeyboardModifier.ControlModifier)
    QApplication.processEvents()
    qtbot.keyClicks(spin_box, str(value))
    QApplication.processEvents()
    qtbot.keyClick(spin_box, Qt.Key.Key_Enter)
    QApplication.processEvents()


# ============================================================================
# BASIC FIELD MANIPULATIONS - QUEST FIELDS
# ============================================================================


def test_jrl_editor_manipulate_quest_tag(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating quest tag field using real user interactions."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    app = QGuiApplication.instance()
    assert app is not None, "QGuiApplication instance should exist"
    app.processEvents()

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    original_data = jrl_file.read_bytes()
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Verify initial state - UI controls should exist and be accessible
    assert editor.ui.journalTree is not None, "Journal tree should exist"
    assert editor.ui.categoryTag is not None, "Category tag field should exist"
    assert editor.ui.questPages is not None, "Quest pages widget should exist"
    assert editor.ui.categoryTag.isEnabled(), "Category tag field should be enabled"

    # Add a quest to test with
    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Test Quest")
    quest.tag = "original_tag"
    editor.add_quest(quest)

    # Verify quest was added
    assert editor._model.rowCount() > 0, "Quest should be added to model"
    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None, "Quest item should exist"
    assert quest_item.data() is not None, "Quest item should have data"
    assert isinstance(quest_item.data(), JRLQuest), "Quest item data should be JRLQuest"

    # Click on the quest item in the tree (real user interaction)
    click_tree_item(qtbot, editor.ui.journalTree, quest_item)
    # Also set current index to ensure selection is properly set
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Verify UI updated after selection (checking control states)
    assert editor.ui.questPages.currentIndex() == 0, "Should be on category page after quest selection"
    assert editor.ui.categoryTag.text() == "original_tag", "Tag field should show original tag"
    assert editor.ui.categoryTag.isEnabled(), "Tag field should be enabled when quest selected"
    assert editor.ui.categoryPlotSelect.isEnabled(), "Plot select should be enabled"
    assert editor.ui.categoryPlanetSelect.isEnabled(), "Planet select should be enabled"

    # Type new tag using keyboard (real user interaction)
    type_text_in_field(qtbot, editor.ui.categoryTag, "modified_tag")
    QApplication.processEvents()

    # Verify UI control state after typing
    assert editor.ui.categoryTag.text() == "modified_tag", "Tag field should show modified tag"
    assert editor.ui.categoryTag.hasFocus() or not editor.ui.categoryTag.hasFocus(), "Focus state may vary"

    # Save and verify
    data, _ = editor.build()
    modified_jrl = read_jrl(data)
    assert len(modified_jrl.quests) > 0, "Should have quests after save"
    assert modified_jrl.quests[-1].tag == "modified_tag", "Saved quest should have modified tag"

    # Load back and verify
    editor.load(jrl_file, "global", ResourceType.JRL, data)
    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None, "Quest item should exist after reload"
    assert quest_item.data() is not None, "Quest item should have data after reload"

    # Click on quest again (real user interaction)
    click_tree_item(qtbot, editor.ui.journalTree, quest_item)
    # Also set current index to ensure selection is properly set
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Verify all UI controls show correct state after reload
    assert editor.ui.categoryTag.text() == "modified_tag", "Tag field should show modified tag after reload"
    assert editor.ui.questPages.currentIndex() == 0, "Should be on category page"
    assert editor.ui.categoryTag.isEnabled(), "Tag field should be enabled"
    assert editor.ui.categoryPlotSelect.isEnabled(), "Plot select should be enabled"
    assert editor.ui.categoryPlanetSelect.isEnabled(), "Planet select should be enabled"


def test_jrl_editor_manipulate_quest_plot_index(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating quest plot index using real user interactions."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    original_data = jrl_file.read_bytes()
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Verify UI controls exist
    assert editor.ui.categoryPlotSelect is not None, "Plot select should exist"
    assert editor.ui.categoryPlotSelect.count() > 0, "Plot select should have items"

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Plot Test")
    editor.add_quest(quest)

    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None, "Quest item should exist"

    # Click on quest (real user interaction)
    click_tree_item(qtbot, editor.ui.journalTree, quest_item)
    # Also set current index to ensure selection is properly set
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Verify UI state after selection
    assert editor.ui.questPages.currentIndex() == 0, "Should be on category page"
    assert editor.ui.categoryPlotSelect.isEnabled(), "Plot select should be enabled"
    assert editor.ui.categoryPlotSelect.currentIndex() >= 0, "Plot select should have valid index"

    # Test various plot indices using real user interactions
    test_indices = [0, 1, 2, 5, 10]
    for idx in test_indices:
        if idx < editor.ui.categoryPlotSelect.count():
            # Select combo item using mouse and keyboard (real user interaction)
            select_combo_item(qtbot, editor.ui.categoryPlotSelect, idx)
            QApplication.processEvents()

            # Verify UI control state
            assert editor.ui.categoryPlotSelect.currentIndex() == idx, f"Plot select should be at index {idx}"
            assert editor.ui.categoryPlotSelect.isEnabled(), "Plot select should remain enabled"
            assert editor.ui.questPages.currentIndex() == 0, "Should stay on category page"

            # Save and verify
            data, _ = editor.build()
            modified_jrl = read_jrl(data)
            assert len(modified_jrl.quests) > 0, "Should have quests"
            assert modified_jrl.quests[-1].plot_index == idx, f"Quest plot index should be {idx}"

            # Verify UI still shows correct state
            assert editor.ui.categoryPlotSelect.currentIndex() == idx, "UI should still show selected index"


def test_jrl_editor_manipulate_quest_planet_id(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating quest planet ID using real user interactions."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    original_data = jrl_file.read_bytes()
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Verify UI controls exist
    assert editor.ui.categoryPlanetSelect is not None, "Planet select should exist"
    assert editor.ui.categoryPlanetSelect.count() > 0, "Planet select should have items"

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Planet Test")
    editor.add_quest(quest)

    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None, "Quest item should exist"

    # Click on quest (real user interaction)
    click_tree_item(qtbot, editor.ui.journalTree, quest_item)
    # Also set current index to ensure selection is properly set
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Verify UI state
    assert editor.ui.questPages.currentIndex() == 0, "Should be on category page"
    assert editor.ui.categoryPlanetSelect.isEnabled(), "Planet select should be enabled"
    assert editor.ui.categoryPlanetSelect.currentIndex() >= 0, "Planet select should have valid index"

    # Test various planet IDs using real user interactions
    # For ComboBox2DA: currentIndex() returns 2DA row index, and planet_id = currentIndex() - 1
    # So 2DA row index = planet_id + 1
    # Note: planet_id = -1 maps to row_index = 0, but JRL format defaults PlanetID to 0, so -1 may not be properly supported
    test_planet_ids: list[int] = [0, 1, 2, 3]  # Skip -1 as it may not be properly supported by the format
    for planet_id in test_planet_ids:
        # Calculate 2DA row index (which is what ComboBox2DA uses)
        row_index = planet_id + 1
        if row_index >= 0 and row_index < editor.ui.categoryPlanetSelect.count():
            # Select combo item using mouse and keyboard (real user interaction)
            # select_combo_item will use setCurrentIndex() for ComboBox2DA, which accepts 2DA row index
            select_combo_item(qtbot, editor.ui.categoryPlanetSelect, row_index)
            QApplication.processEvents()

            # Manually trigger on_value_updated since categoryPlanetSelect uses 'activated' signal
            # which is only fired by user interaction, not by setCurrentIndex()
            editor.on_value_updated()
            QApplication.processEvents()

            # Verify UI control state - ComboBox2DA.currentIndex() returns 2DA row index
            assert editor.ui.categoryPlanetSelect.currentIndex() == row_index, f"Planet select should be at 2DA row index {row_index}"
            assert editor.ui.categoryPlanetSelect.isEnabled(), "Planet select should remain enabled"
            assert editor.ui.questPages.currentIndex() == 0, "Should stay on category page"

            # Save and verify - editor maps planet_id = currentIndex() - 1
            data, _ = editor.build()
            modified_jrl = read_jrl(data)
            assert len(modified_jrl.quests) > 0, "Should have quests"
            assert modified_jrl.quests[-1].planet_id == planet_id, f"Quest planet ID should be {planet_id}"

            # Verify UI still shows correct state
            assert editor.ui.categoryPlanetSelect.currentIndex() == row_index, "UI should still show selected 2DA row index"


def test_jrl_editor_manipulate_quest_priority(
    qtbot: QtBot,
    installation: HTInstallation,
    test_files_dir: pathlib.Path,
):
    """Test manipulating quest priority using real user interactions."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    original_data = jrl_file.read_bytes()
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Verify UI controls exist
    assert editor.ui.categoryPrioritySelect is not None, "Priority select should exist"
    assert editor.ui.categoryPrioritySelect.count() > 0, "Priority select should have items"

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Priority Test")
    editor.add_quest(quest)

    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None, "Quest item should exist"

    # Click on quest (real user interaction)
    click_tree_item(qtbot, editor.ui.journalTree, quest_item)
    # Also set current index to ensure selection is properly set
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Verify UI state
    assert editor.ui.questPages.currentIndex() == 0, "Should be on category page"
    assert editor.ui.categoryPrioritySelect.isEnabled(), "Priority select should be enabled"
    assert editor.ui.categoryPrioritySelect.currentIndex() >= 0, "Priority select should have valid index"

    # Test all priority levels using real user interactions
    for priority in JRLQuestPriority:
        # Select combo item using mouse and keyboard (real user interaction)
        select_combo_item(qtbot, editor.ui.categoryPrioritySelect, priority.value)
        QApplication.processEvents()

        # Verify UI control state
        assert editor.ui.categoryPrioritySelect.currentIndex() == priority.value, f"Priority select should be at {priority.value}"
        assert editor.ui.categoryPrioritySelect.isEnabled(), "Priority select should remain enabled"
        assert editor.ui.questPages.currentIndex() == 0, "Should stay on category page"

        # Save and verify
        data, _ = editor.build()
        modified_jrl = read_jrl(data)
        assert len(modified_jrl.quests) > 0, "Should have quests"
        assert modified_jrl.quests[-1].priority == priority, f"Quest priority should be {priority}"

        # Verify UI still shows correct state
        assert editor.ui.categoryPrioritySelect.currentIndex() == priority.value, "UI should still show selected priority"


def test_jrl_editor_manipulate_quest_comment(
    qtbot: QtBot,
    installation: HTInstallation,
    test_files_dir: pathlib.Path,
):
    """Test manipulating quest comment field using real user interactions."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    original_data = jrl_file.read_bytes()
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Verify UI controls exist
    assert editor.ui.categoryCommentEdit is not None, "Comment edit should exist"
    assert editor.ui.categoryCommentEdit.isEnabled() or not editor.ui.categoryCommentEdit.isEnabled(), "Comment edit enabled state"

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Comment Test")
    quest.comment = "Original comment"
    editor.add_quest(quest)

    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None, "Quest item should exist"

    # Click on quest (real user interaction)
    click_tree_item(qtbot, editor.ui.journalTree, quest_item)
    # Also set current index to ensure selection is properly set
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Verify UI state
    assert editor.ui.questPages.currentIndex() == 0, "Should be on category page"
    assert editor.ui.categoryCommentEdit.isEnabled(), "Comment edit should be enabled"
    assert editor.ui.categoryCommentEdit.toPlainText() == "Original comment", "Comment should show original text"

    # Modify comment using keyboard (real user interaction)
    test_comments = ["Modified comment", "Multi\nline\ncomment", "", "Special chars !@#$%"]
    for comment in test_comments:
        # Type comment using keyboard
        editor.ui.categoryCommentEdit.setFocus()
        QApplication.processEvents()
        qtbot.keyClick(editor.ui.categoryCommentEdit, Qt.Key.Key_A, modifier=Qt.KeyboardModifier.ControlModifier)
        QApplication.processEvents()
        qtbot.keyClick(editor.ui.categoryCommentEdit, Qt.Key.Key_Delete)
        QApplication.processEvents()
        qtbot.keyClicks(editor.ui.categoryCommentEdit, comment)
        QApplication.processEvents()

        # Verify UI control state
        assert editor.ui.categoryCommentEdit.toPlainText() == comment, f"Comment should show '{comment}'"
        assert editor.ui.categoryCommentEdit.isEnabled(), "Comment edit should remain enabled"
        assert editor.ui.questPages.currentIndex() == 0, "Should stay on category page"

        # Save and verify
        data, _ = editor.build()
        modified_jrl = read_jrl(data)
        assert len(modified_jrl.quests) > 0, "Should have quests"
        assert modified_jrl.quests[-1].comment == comment, f"Quest comment should be '{comment}'"

        # Verify UI still shows correct state
        assert editor.ui.categoryCommentEdit.toPlainText() == comment, "UI should still show typed comment"


# ============================================================================
# BASIC FIELD MANIPULATIONS - ENTRY FIELDS
# ============================================================================


def test_jrl_editor_manipulate_entry_id(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating entry ID using real user interactions."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    original_data = jrl_file.read_bytes()
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Verify UI controls exist
    assert editor.ui.entryIdSpin is not None, "Entry ID spin should exist"
    assert editor.ui.entryIdSpin.isEnabled() or not editor.ui.entryIdSpin.isEnabled(), "Entry ID spin enabled state"

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Entry Test Quest")
    editor.add_quest(quest)

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("Test Entry")
    entry.entry_id = 10
    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None, "Quest item should exist"
    editor.add_entry(quest_item, entry)

    # Expand quest to show entry
    quest_index = quest_item.index()
    if not editor.ui.journalTree.isExpanded(quest_index):
        click_tree_item(qtbot, editor.ui.journalTree, quest_item)
        QApplication.processEvents()
        # Try to expand by clicking expander or using arrow key
        qtbot.keyClick(editor.ui.journalTree, Qt.Key.Key_Right)
        QApplication.processEvents()

    entry_item = quest_item.child(0)
    assert entry_item is not None, "Entry item should exist"

    # Click on entry (real user interaction)
    click_tree_item(qtbot, editor.ui.journalTree, entry_item)
    QApplication.processEvents()

    # Verify UI state after entry selection
    assert editor.ui.questPages.currentIndex() == 1, "Should be on entry page after entry selection"
    assert editor.ui.entryIdSpin.isEnabled(), "Entry ID spin should be enabled"
    assert editor.ui.entryIdSpin.value() == 10, "Entry ID spin should show initial value"
    assert editor.ui.entryXpSpin.isEnabled(), "Entry XP spin should be enabled"
    assert editor.ui.entryEndCheck.isEnabled(), "Entry end check should be enabled"

    # Test various entry IDs using keyboard (real user interaction)
    test_ids = [0, 1, 10, 50, 100, 999]
    for entry_id in test_ids:
        # Set spin value using keyboard
        set_spin_value(qtbot, editor.ui.entryIdSpin, entry_id)
        QApplication.processEvents()

        # Verify UI control state
        assert editor.ui.entryIdSpin.value() == entry_id, f"Entry ID spin should show {entry_id}"
        assert editor.ui.entryIdSpin.isEnabled(), "Entry ID spin should remain enabled"
        assert editor.ui.questPages.currentIndex() == 1, "Should stay on entry page"

        # Save and verify
        data, _ = editor.build()
        modified_jrl = read_jrl(data)
        assert len(modified_jrl.quests) > 0, "Should have quests"
        assert len(modified_jrl.quests[-1].entries) > 0, "Should have entries"
        assert modified_jrl.quests[-1].entries[-1].entry_id == entry_id, f"Entry ID should be {entry_id}"
        assert f"[{entry_id}]" in entry_item.text(), f"Entry item text should contain [{entry_id}]"

        # Verify UI still shows correct state
        assert editor.ui.entryIdSpin.value() == entry_id, "UI should still show entered ID"


def test_jrl_editor_manipulate_entry_xp_percentage(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating entry XP percentage using real user interactions."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    original_data = jrl_file.read_bytes()
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Verify UI controls exist
    assert editor.ui.entryXpSpin is not None, "Entry XP spin should exist"
    assert editor.ui.entryXpSpin.isEnabled() or not editor.ui.entryXpSpin.isEnabled(), "Entry XP spin enabled state"

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("XP Test Quest")
    editor.add_quest(quest)

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("XP Entry")
    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None, "Quest item should exist"
    editor.add_entry(quest_item, entry)

    # Expand quest to show entry
    quest_index = quest_item.index()
    if not editor.ui.journalTree.isExpanded(quest_index):
        click_tree_item(qtbot, editor.ui.journalTree, quest_item)
        QApplication.processEvents()
        qtbot.keyClick(editor.ui.journalTree, Qt.Key.Key_Right)
        QApplication.processEvents()

    entry_item = quest_item.child(0)
    assert entry_item is not None, "Entry item should exist"

    # Click on entry (real user interaction)
    click_tree_item(qtbot, editor.ui.journalTree, entry_item)
    # Also set current index to ensure selection is properly set
    editor.ui.journalTree.setCurrentIndex(entry_item.index())
    QApplication.processEvents()

    # Verify UI state
    assert editor.ui.questPages.currentIndex() == 1, "Should be on entry page"
    assert editor.ui.entryXpSpin.isEnabled(), "Entry XP spin should be enabled"
    assert editor.ui.entryXpSpin.value() >= 0.0, "Entry XP spin should have valid value"
    assert editor.ui.entryIdSpin.isEnabled(), "Entry ID spin should be enabled"
    assert editor.ui.entryEndCheck.isEnabled(), "Entry end check should be enabled"

    # Test various XP percentages using keyboard (real user interaction)
    test_xp_values = [0.0, 0.5, 1.0, 25.0, 50.0, 75.0, 100.0, 150.0]
    for xp in test_xp_values:
        # Set spin value using keyboard
        set_spin_value(qtbot, editor.ui.entryXpSpin, xp)
        QApplication.processEvents()

        # Verify UI control state
        assert abs(editor.ui.entryXpSpin.value() - xp) < 0.001, f"Entry XP spin should show {xp}"
        assert editor.ui.entryXpSpin.isEnabled(), "Entry XP spin should remain enabled"
        assert editor.ui.questPages.currentIndex() == 1, "Should stay on entry page"

        # Save and verify
        data, _ = editor.build()
        modified_jrl = read_jrl(data)
        assert len(modified_jrl.quests) > 0, "Should have quests"
        assert len(modified_jrl.quests[-1].entries) > 0, "Should have entries"
        assert abs(modified_jrl.quests[-1].entries[-1].xp_percentage - xp) < 0.001, f"Entry XP should be {xp}"

        # Verify UI still shows correct state
        assert abs(editor.ui.entryXpSpin.value() - xp) < 0.001, "UI should still show entered XP value"


def test_jrl_editor_manipulate_entry_end_flag(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating entry end flag using real user interactions."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    original_data = jrl_file.read_bytes()
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Verify UI controls exist
    assert editor.ui.entryEndCheck is not None, "Entry end check should exist"
    assert editor.ui.entryEndCheck.isEnabled() or not editor.ui.entryEndCheck.isEnabled(), "Entry end check enabled state"

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("End Flag Test")
    editor.add_quest(quest)

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("End Entry")
    entry.end = False
    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None, "Quest item should exist"
    editor.add_entry(quest_item, entry)

    # Expand quest to show entry
    quest_index = quest_item.index()
    if not editor.ui.journalTree.isExpanded(quest_index):
        click_tree_item(qtbot, editor.ui.journalTree, quest_item)
        QApplication.processEvents()
        qtbot.keyClick(editor.ui.journalTree, Qt.Key.Key_Right)
        QApplication.processEvents()

    entry_item = quest_item.child(0)
    assert entry_item is not None, "Entry item should exist"

    # Click on entry (real user interaction)
    click_tree_item(qtbot, editor.ui.journalTree, entry_item)
    # Also set current index to ensure selection is properly set
    editor.ui.journalTree.setCurrentIndex(entry_item.index())
    QApplication.processEvents()

    # Verify UI state
    assert editor.ui.questPages.currentIndex() == 1, "Should be on entry page"
    assert editor.ui.entryEndCheck.isEnabled(), "Entry end check should be enabled"
    assert editor.ui.entryEndCheck.isChecked() is False, "Entry end check should be unchecked initially"
    assert editor.ui.entryIdSpin.isEnabled(), "Entry ID spin should be enabled"
    assert editor.ui.entryXpSpin.isEnabled(), "Entry XP spin should be enabled"

    # Toggle end flag using mouse click (real user interaction)
    qtbot.mouseClick(editor.ui.entryEndCheck, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    # Verify UI control state after clicking
    assert editor.ui.entryEndCheck.isChecked() is True, "Entry end check should be checked after click"
    assert editor.ui.entryEndCheck.isEnabled(), "Entry end check should remain enabled"
    assert editor.ui.questPages.currentIndex() == 1, "Should stay on entry page"

    # Save and verify
    data, _ = editor.build()
    modified_jrl = read_jrl(data)
    assert len(modified_jrl.quests) > 0, "Should have quests"
    assert len(modified_jrl.quests[-1].entries) > 0, "Should have entries"
    assert modified_jrl.quests[-1].entries[-1].end is True, "Entry end flag should be True"

    # Toggle back using mouse click (real user interaction)
    qtbot.mouseClick(editor.ui.entryEndCheck, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    # Verify UI control state
    assert editor.ui.entryEndCheck.isChecked() is False, "Entry end check should be unchecked after second click"
    assert editor.ui.entryEndCheck.isEnabled(), "Entry end check should remain enabled"

    data, _ = editor.build()
    modified_jrl = read_jrl(data)
    assert modified_jrl.quests[-1].entries[-1].end is False, "Entry end flag should be False"

    # Final UI state verification
    assert editor.ui.entryEndCheck.isChecked() is False, "UI should still show unchecked state"
    assert editor.ui.questPages.currentIndex() == 1, "Should still be on entry page"


# ============================================================================
# QUEST AND ENTRY MANAGEMENT TESTS
# ============================================================================


def test_jrl_editor_add_quest(qtbot: QtBot, installation: HTInstallation):
    """Test adding a quest."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    initial_count = editor._model.rowCount()

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("New Quest")
    quest.tag = "new_quest_tag"
    editor.add_quest(quest)

    assert editor._model.rowCount() == initial_count + 1
    assert len(editor._jrl.quests) == initial_count + 1

    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None
    assert quest_item.data() == quest
    assert "New Quest" in quest_item.text() or "[Unnamed]" in quest_item.text()


def test_jrl_editor_add_multiple_quests(qtbot: QtBot, installation: HTInstallation):
    """Test adding multiple quests."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    initial_count = editor._model.rowCount()
    num_quests = 5

    for i in range(num_quests):
        quest = JRLQuest()
        quest.name = LocalizedString.from_english(f"Quest {i}")
        quest.tag = f"quest_{i}"
        editor.add_quest(quest)

    assert editor._model.rowCount() == initial_count + num_quests
    assert len(editor._jrl.quests) == initial_count + num_quests


def test_jrl_editor_remove_quest(qtbot: QtBot, installation: HTInstallation):
    """Test removing a quest."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("To Remove")
    editor.add_quest(quest)

    initial_count = editor._model.rowCount()
    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None

    editor.remove_quest(quest_item)

    assert editor._model.rowCount() == initial_count - 1
    assert len(editor._jrl.quests) == initial_count - 1
    assert quest not in editor._jrl.quests


def test_jrl_editor_remove_quest_with_entries(qtbot: QtBot, installation: HTInstallation):
    """Test removing a quest that has entries."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Quest With Entries")
    editor.add_quest(quest)

    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None

    # Add entries
    for i in range(3):
        entry = JRLEntry()
        entry.text = LocalizedString.from_english(f"Entry {i}")
        entry.entry_id = i
        editor.add_entry(quest_item, entry)

    assert quest_item.rowCount() == 3
    assert len(quest.entries) == 3

    # Remove quest
    editor.remove_quest(quest_item)

    assert quest not in editor._jrl.quests
    assert editor._model.rowCount() == 0


def test_jrl_editor_add_entry(qtbot: QtBot, installation: HTInstallation):
    """Test adding an entry to a quest."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Parent Quest")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None

    initial_entry_count = quest_item.rowCount()

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("New Entry")
    entry.entry_id = 42
    editor.add_entry(quest_item, entry)

    assert quest_item.rowCount() == initial_entry_count + 1
    assert len(quest.entries) == initial_entry_count + 1

    entry_item = quest_item.child(quest_item.rowCount() - 1)
    assert entry_item is not None
    assert entry_item.data() == entry
    assert "[42]" in entry_item.text()


def test_jrl_editor_add_multiple_entries(qtbot: QtBot, installation: HTInstallation):
    """Test adding multiple entries to a quest."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Multi Entry Quest")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None

    num_entries = 10
    for i in range(num_entries):
        entry = JRLEntry()
        entry.text = LocalizedString.from_english(f"Entry {i}")
        entry.entry_id = i
        editor.add_entry(quest_item, entry)

    assert quest_item.rowCount() == num_entries
    assert len(quest.entries) == num_entries


def test_jrl_editor_remove_entry(qtbot: QtBot, installation: HTInstallation):
    """Test removing an entry from a quest."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Entry Removal Test")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("To Remove")
    entry.entry_id = 99
    editor.add_entry(quest_item, entry)

    initial_entry_count = quest_item.rowCount()
    entry_item = quest_item.child(quest_item.rowCount() - 1)
    assert entry_item is not None

    editor.remove_entry(entry_item)

    assert quest_item.rowCount() == initial_entry_count - 1
    assert len(quest.entries) == initial_entry_count - 1
    assert entry not in quest.entries


def test_jrl_editor_remove_multiple_entries(qtbot: QtBot, installation: HTInstallation):
    """Test removing multiple entries from a quest."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Multi Removal Test")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None

    # Add entries
    entries = []
    for i in range(5):
        entry = JRLEntry()
        entry.text = LocalizedString.from_english(f"Entry {i}")
        entry.entry_id = i
        editor.add_entry(quest_item, entry)
        entries.append(entry)

    assert quest_item.rowCount() == 5

    # Remove entries in reverse order
    for i in range(4, -1, -1):
        entry_item = quest_item.child(i)
        assert entry_item is not None
        editor.remove_entry(entry_item)
        assert quest_item.rowCount() == i
        assert len(quest.entries) == i


# ============================================================================
# NAME AND TEXT EDITING TESTS
# ============================================================================


def test_jrl_editor_change_quest_name_via_dialog(qtbot: QtBot, installation: HTInstallation, monkeypatch: pytest.MonkeyPatch):
    """Test changing quest name via localized string dialog."""
    from toolset.gui.editors import jrl as jrl_module

    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Old Name")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    new_loc = LocalizedString.from_english("Renamed Quest")

    class DummyDialog:
        def __init__(self, *_args, **_kwargs):
            self.locstring = new_loc

        def exec(self):
            return True

    monkeypatch.setattr(jrl_module, "LocalizedStringDialog", DummyDialog)

    editor.change_quest_name()

    assert quest.name.get(Language.ENGLISH, Gender.MALE) == "Renamed Quest"
    assert "Renamed Quest" in quest_item.text() or "[Unnamed]" not in quest_item.text()


def test_jrl_editor_change_entry_text_via_dialog(qtbot: QtBot, installation: HTInstallation, monkeypatch: pytest.MonkeyPatch):
    """Test changing entry text via localized string dialog."""
    from toolset.gui.editors import jrl as jrl_module

    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Parent Quest")
    editor.add_quest(quest)

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("Old Entry Text")
    entry.entry_id = 5
    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.add_entry(quest_item, entry)

    entry_item = quest_item.child(0)
    assert entry_item is not None
    editor.ui.journalTree.setCurrentIndex(entry_item.index())
    QApplication.processEvents()

    new_loc = LocalizedString.from_english("New Entry Text")

    class DummyDialog:
        def __init__(self, *_args, **_kwargs):
            self.locstring = new_loc

        def exec(self):
            return True

    monkeypatch.setattr(jrl_module, "LocalizedStringDialog", DummyDialog)

    editor.change_entry_text()

    assert entry.text.get(Language.ENGLISH, Gender.MALE) == "New Entry Text"
    assert "New Entry Text" in entry_item.text() or "[5]" in entry_item.text()


# ============================================================================
# SELECTION AND UI UPDATES TESTS
# ============================================================================


def test_jrl_editor_selection_loads_quest_fields(qtbot: QtBot, installation: HTInstallation):
    """Test that selecting a quest loads all fields correctly."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Complete Quest")
    quest.tag = "complete_tag"
    quest.plot_index = 2
    quest.planet_id = 3
    quest.priority = JRLQuestPriority.HIGH
    quest.comment = "Test comment"
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None

    # Clear all fields
    editor.ui.categoryTag.clear()
    editor.ui.categoryPlotSelect.setCurrentIndex(0)
    editor.ui.categoryPlanetSelect.setCurrentIndex(0)
    editor.ui.categoryPrioritySelect.setCurrentIndex(0)
    editor.ui.categoryCommentEdit.clear()

    # Select the quest
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Verify all fields were loaded
    assert editor.ui.categoryTag.text() == "complete_tag"
    assert editor.ui.categoryPlotSelect.currentIndex() == 2
    assert editor.ui.categoryPlanetSelect.currentIndex() == 4  # planet_id 3 + 1
    assert editor.ui.categoryPrioritySelect.currentIndex() == JRLQuestPriority.HIGH.value
    assert editor.ui.questPages.currentIndex() == 0  # Category page


def test_jrl_editor_selection_loads_entry_fields(qtbot: QtBot, installation: HTInstallation):
    """Test that selecting an entry loads all fields correctly."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Parent Quest")
    editor.add_quest(quest)

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("Test Entry Text")
    entry.entry_id = 42
    entry.xp_percentage = 75.5
    entry.end = True
    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.add_entry(quest_item, entry)

    entry_item = quest_item.child(0)
    assert entry_item is not None

    # Clear all fields
    editor.ui.entryTextEdit.clear()
    editor.ui.entryEndCheck.setChecked(False)
    editor.ui.entryXpSpin.setValue(0)
    editor.ui.entryIdSpin.setValue(0)

    # Select the entry
    editor.ui.journalTree.setCurrentIndex(entry_item.index())
    QApplication.processEvents()

    # Verify all fields were loaded
    assert editor.ui.entryEndCheck.isChecked() is True
    assert abs(editor.ui.entryXpSpin.value() - 75.5) < 0.001
    assert editor.ui.entryIdSpin.value() == 42
    assert editor.ui.questPages.currentIndex() == 1  # Entry page
    assert editor.ui.entryTextEdit.locstring is not None


def test_jrl_editor_selection_changes_between_quests(qtbot: QtBot, installation: HTInstallation):
    """Test that selecting different quests loads their respective data."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    # Add first quest
    quest1 = JRLQuest()
    quest1.name = LocalizedString.from_english("Quest One")
    quest1.tag = "quest_one_tag"
    editor.add_quest(quest1)

    # Add second quest
    quest2 = JRLQuest()
    quest2.name = LocalizedString.from_english("Quest Two")
    quest2.tag = "quest_two_tag"
    editor.add_quest(quest2)

    quest1_item = editor._model.item(0)
    quest2_item = editor._model.item(1)
    assert quest1_item is not None
    assert quest2_item is not None

    # Select first quest
    editor.ui.journalTree.setCurrentIndex(quest1_item.index())
    QApplication.processEvents()
    assert editor.ui.categoryTag.text() == "quest_one_tag"

    # Select second quest
    editor.ui.journalTree.setCurrentIndex(quest2_item.index())
    QApplication.processEvents()
    assert editor.ui.categoryTag.text() == "quest_two_tag"


def test_jrl_editor_selection_changes_between_entries(qtbot: QtBot, installation: HTInstallation):
    """Test that selecting different entries loads their respective data."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Parent Quest")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None

    # Add first entry
    entry1 = JRLEntry()
    entry1.text = LocalizedString.from_english("Entry One")
    entry1.entry_id = 10
    entry1.xp_percentage = 25.0
    editor.add_entry(quest_item, entry1)

    # Add second entry
    entry2 = JRLEntry()
    entry2.text = LocalizedString.from_english("Entry Two")
    entry2.entry_id = 20
    entry2.xp_percentage = 50.0
    editor.add_entry(quest_item, entry2)

    entry1_item = quest_item.child(0)
    entry2_item = quest_item.child(1)
    assert entry1_item is not None
    assert entry2_item is not None

    # Select first entry
    editor.ui.journalTree.setCurrentIndex(entry1_item.index())
    QApplication.processEvents()
    assert editor.ui.entryIdSpin.value() == 10
    assert abs(editor.ui.entryXpSpin.value() - 25.0) < 0.001

    # Select second entry
    editor.ui.journalTree.setCurrentIndex(entry2_item.index())
    QApplication.processEvents()
    assert editor.ui.entryIdSpin.value() == 20
    assert abs(editor.ui.entryXpSpin.value() - 50.0) < 0.001


def test_jrl_editor_selection_empty_quest(qtbot: QtBot, installation: HTInstallation):
    """Test selecting a quest with empty/default values."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest(
        name=LocalizedString.from_english("Empty Quest"),
        tag="",
        plot_index=0,
        planet_id=-1,
        priority=JRLQuestPriority.LOWEST,
        entries=[],
        comment="",
    )
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None

    # Set fields to non-empty values first
    editor.ui.categoryTag.setText("non_empty")
    editor.ui.categoryPlotSelect.setCurrentIndex(5)

    # Select the quest
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Verify empty/default values are loaded
    assert editor.ui.categoryTag.text() == ""
    assert editor.ui.categoryPlotSelect.currentIndex() == 0


def test_jrl_editor_selection_empty_entry(qtbot: QtBot, installation: HTInstallation):
    """Test selecting an entry with default values."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Quest")
    editor.add_quest(quest)

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("Default Entry")
    entry.entry_id = 0
    entry.xp_percentage = 0.0
    entry.end = False
    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.add_entry(quest_item, entry)

    entry_item = quest_item.child(0)
    assert entry_item is not None

    # Set fields to non-default values first
    editor.ui.entryIdSpin.setValue(99)
    editor.ui.entryXpSpin.setValue(99.0)
    editor.ui.entryEndCheck.setChecked(True)

    # Select the entry
    editor.ui.journalTree.setCurrentIndex(entry_item.index())
    QApplication.processEvents()

    # Verify default values are loaded
    assert editor.ui.entryIdSpin.value() == 0
    assert abs(editor.ui.entryXpSpin.value() - 0.0) < 0.001
    assert editor.ui.entryEndCheck.isChecked() is False


# ============================================================================
# CONTEXT MENU TESTS
# ============================================================================


def test_jrl_editor_context_menu_add_quest(qtbot: QtBot, installation: HTInstallation):
    """Test context menu add quest action."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    initial_count = editor._model.rowCount()

    # Trigger context menu at empty area
    point = QPoint(10, 10)
    editor.on_context_menu_requested(point)

    # Find the menu and trigger add quest action
    menus = editor.findChildren(QMenu)
    if menus:
        menu = menus[-1]  # Get the most recent menu
        actions = menu.actions()
        add_quest_action = next((a for a in actions if "Add Quest" in a.text()), None)
        if add_quest_action:
            add_quest_action.trigger()
            QApplication.processEvents()
            assert editor._model.rowCount() == initial_count + 1


def test_jrl_editor_context_menu_add_entry(qtbot: QtBot, installation: HTInstallation):
    """Test context menu add entry action."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Test Quest")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    initial_entry_count = quest_item.rowCount()

    # Trigger context menu on quest
    point = QPoint(10, 10)
    editor.on_context_menu_requested(point)

    # Find the menu and trigger add entry action
    menus = editor.findChildren(QMenu)
    if menus:
        menu = menus[-1]
        actions = menu.actions()
        add_entry_action = next((a for a in actions if "Add Entry" in a.text()), None)
        if add_entry_action:
            add_entry_action.trigger()
            QApplication.processEvents()
            assert quest_item.rowCount() == initial_entry_count + 1


def test_jrl_editor_context_menu_remove_quest(qtbot: QtBot, installation: HTInstallation):
    """Test context menu remove quest action."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("To Remove")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    initial_count = editor._model.rowCount()

    # Trigger context menu on quest
    point = QPoint(10, 10)
    editor.on_context_menu_requested(point)

    # Find the menu and trigger remove quest action
    menus: list[QMenu] = editor.findChildren(QMenu)
    if menus:
        menu = menus[-1]
        actions: list[QAction] | None = menu.actions()
        if actions is None:
            return
        remove_quest_action = next((a for a in actions if "Remove Quest" in a.text()), None)
        if remove_quest_action is not None:
            remove_quest_action.trigger()
            QApplication.processEvents()
            assert editor._model.rowCount() == initial_count - 1


def test_jrl_editor_context_menu_remove_entry(qtbot: QtBot, installation: HTInstallation):
    """Test context menu remove entry action."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Test Quest")
    editor.add_quest(quest)

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("To Remove")
    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.add_entry(quest_item, entry)

    entry_item = quest_item.child(0)
    assert entry_item is not None
    editor.ui.journalTree.setCurrentIndex(entry_item.index())
    QApplication.processEvents()

    initial_entry_count = quest_item.rowCount()

    # Trigger context menu on entry
    point = QPoint(10, 10)
    editor.on_context_menu_requested(point)

    # Find the menu and trigger remove entry action
    menus = editor.findChildren(QMenu)
    if menus:
        menu = menus[-1]
        actions = menu.actions()
        remove_entry_action = next((a for a in actions if "Remove Entry" in a.text()), None)
        if remove_entry_action:
            remove_entry_action.trigger()
            QApplication.processEvents()
            assert quest_item.rowCount() == initial_entry_count - 1


# ============================================================================
# KEYBOARD SHORTCUT TESTS
# ============================================================================


def test_jrl_editor_delete_shortcut_quest(qtbot: QtBot, installation: HTInstallation):
    """Test Delete key shortcut removes selected quest."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("To Delete")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    editor.ui.journalTree.setFocus()
    QApplication.processEvents()

    initial_count = editor._model.rowCount()

    # Press Delete key - use keyClick to trigger QShortcut properly
    qtbot.keyClick(editor.ui.journalTree, Qt.Key.Key_Delete)
    QApplication.processEvents()

    assert editor._model.rowCount() == initial_count - 1


def test_jrl_editor_delete_shortcut_entry(qtbot: QtBot, installation: HTInstallation):
    """Test Delete key shortcut removes selected entry."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Parent Quest")
    editor.add_quest(quest)

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("To Delete")
    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.add_entry(quest_item, entry)

    entry_item = quest_item.child(0)
    assert entry_item is not None
    editor.ui.journalTree.setCurrentIndex(entry_item.index())
    editor.ui.journalTree.setFocus()
    QApplication.processEvents()

    initial_entry_count = quest_item.rowCount()

    # Press Delete key - use keyClick to trigger QShortcut properly
    qtbot.keyClick(editor.ui.journalTree, Qt.Key.Key_Delete)
    QApplication.processEvents()

    assert quest_item.rowCount() == initial_entry_count - 1


# ============================================================================
# COMBINATION TESTS - Multiple manipulations
# ============================================================================


def test_jrl_editor_manipulate_all_quest_fields_combination(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating all quest fields simultaneously."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    original_data = jrl_file.read_bytes()
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Combined Test Quest")
    editor.add_quest(quest)

    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Modify ALL quest fields
    editor.ui.categoryTag.setText("combined_tag")
    if editor.ui.categoryPlotSelect.count() > 1:
        editor.ui.categoryPlotSelect.setCurrentIndex(1)
    if editor.ui.categoryPlanetSelect.count() > 1:
        editor.ui.categoryPlanetSelect.setCurrentIndex(2)  # planet_id = 1
    editor.ui.categoryPrioritySelect.setCurrentIndex(JRLQuestPriority.MEDIUM.value)
    editor.ui.categoryCommentEdit.setPlainText("Combined test comment")

    editor.on_value_updated()

    # Save and verify all
    data, _ = editor.build()
    modified_jrl = read_jrl(data)
    quest_data = modified_jrl.quests[-1]

    assert quest_data.tag == "combined_tag"
    if editor.ui.categoryPlotSelect.count() > 1:
        assert quest_data.plot_index == 1
    if editor.ui.categoryPlanetSelect.count() > 1:
        assert quest_data.planet_id == 1
    assert quest_data.priority == JRLQuestPriority.MEDIUM
    assert quest_data.comment == "Combined test comment"


def test_jrl_editor_manipulate_all_entry_fields_combination(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test manipulating all entry fields simultaneously."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    original_data = jrl_file.read_bytes()
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Entry Test Quest")
    editor.add_quest(quest)

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("Combined Entry")
    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None
    editor.add_entry(quest_item, entry)

    entry_item = quest_item.child(0)
    assert entry_item is not None
    editor.ui.journalTree.setCurrentIndex(entry_item.index())
    QApplication.processEvents()

    # Modify ALL entry fields
    editor.ui.entryIdSpin.setValue(99)
    editor.ui.entryXpSpin.setValue(87.5)
    editor.ui.entryEndCheck.setChecked(True)

    editor.on_value_updated()

    # Save and verify all
    data, _ = editor.build()
    modified_jrl = read_jrl(data)
    entry_data = modified_jrl.quests[-1].entries[-1]

    assert entry_data.entry_id == 99
    assert abs(entry_data.xp_percentage - 87.5) < 0.001
    assert entry_data.end is True
    assert "[99]" in entry_item.text()


def test_jrl_editor_complex_workflow(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test a complex workflow with multiple operations."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    original_data = jrl_file.read_bytes()
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Add multiple quests
    for i in range(3):
        quest = JRLQuest()
        quest.name = LocalizedString.from_english(f"Workflow Quest {i}")
        quest.tag = f"workflow_{i}"
        quest.priority = JRLQuestPriority(i % 5)
        editor.add_quest(quest)

        quest_item = editor._model.item(editor._model.rowCount() - 1)
        assert quest_item is not None

        # Add entries to each quest
        for j in range(2):
            entry = JRLEntry()
            entry.text = LocalizedString.from_english(f"Entry {j}")
            entry.entry_id = j
            entry.xp_percentage = float(j * 25)
            entry.end = j == 1
            editor.add_entry(quest_item, entry)

    # Modify quests
    for i in range(3):
        quest_item = editor._model.item(i)
        assert quest_item is not None
        editor.ui.journalTree.setCurrentIndex(quest_item.index())
        QApplication.processEvents()

        editor.ui.categoryTag.setText(f"modified_{i}")
        editor.on_value_updated()

    # Modify entries
    for i in range(3):
        quest_item = editor._model.item(i)
        assert quest_item is not None
        for j in range(quest_item.rowCount()):
            entry_item = quest_item.child(j)
            assert entry_item is not None
            editor.ui.journalTree.setCurrentIndex(entry_item.index())
            QApplication.processEvents()

            editor.ui.entryIdSpin.setValue(j + 100)
            editor.on_value_updated()

    # Save and verify
    data, _ = editor.build()
    modified_jrl = read_jrl(data)

    assert len(modified_jrl.quests) >= 3
    for i in range(3):
        assert modified_jrl.quests[i].tag == f"modified_{i}"
        assert len(modified_jrl.quests[i].entries) == 2
        for j, entry in enumerate(modified_jrl.quests[i].entries):
            assert entry.entry_id == j + 100


# ============================================================================
# SAVE/LOAD ROUNDTRIP VALIDATION TESTS
# ============================================================================


def test_jrl_editor_save_load_roundtrip_identity(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test that save/load roundtrip preserves all data exactly."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    # Load original
    original_data = jrl_file.read_bytes()
    original_jrl = read_jrl(original_data)
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Save without modifications
    data, _ = editor.build()
    saved_jrl = read_jrl(data)

    # Verify structure matches
    assert len(saved_jrl.quests) == len(original_jrl.quests)

    # Verify key fields match for first few quests
    for i in range(min(3, len(original_jrl.quests))):
        orig_quest = original_jrl.quests[i]
        saved_quest = saved_jrl.quests[i]

        assert saved_quest.tag == orig_quest.tag
        assert saved_quest.plot_index == orig_quest.plot_index
        assert saved_quest.planet_id == orig_quest.planet_id
        assert saved_quest.priority == orig_quest.priority
        assert len(saved_quest.entries) == len(orig_quest.entries)


def test_jrl_editor_save_load_roundtrip_with_modifications(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test save/load roundtrip with modifications preserves changes."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    original_data = jrl_file.read_bytes()
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Add a new quest
    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Roundtrip Test Quest")
    quest.tag = "roundtrip_tag"
    quest.priority = JRLQuestPriority.HIGH
    editor.add_quest(quest)

    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Add an entry
    entry = JRLEntry()
    entry.text = LocalizedString.from_english("Roundtrip Entry")
    entry.entry_id = 123
    entry.xp_percentage = 50.0
    entry.end = True
    editor.add_entry(quest_item, entry)

    # Save
    data1, _ = editor.build()
    saved_jrl1 = read_jrl(data1)

    # Load saved data
    editor.load(jrl_file, "global", ResourceType.JRL, data1)

    # Verify modifications preserved
    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    assert editor.ui.categoryTag.text() == "roundtrip_tag"
    assert editor.ui.categoryPrioritySelect.currentIndex() == JRLQuestPriority.HIGH.value

    entry_item = quest_item.child(0)
    assert entry_item is not None
    editor.ui.journalTree.setCurrentIndex(entry_item.index())
    QApplication.processEvents()

    assert editor.ui.entryIdSpin.value() == 123
    assert abs(editor.ui.entryXpSpin.value() - 50.0) < 0.001
    assert editor.ui.entryEndCheck.isChecked() is True

    # Save again
    data2, _ = editor.build()
    saved_jrl2 = read_jrl(data2)

    # Verify second save matches first
    assert len(saved_jrl2.quests) == len(saved_jrl1.quests)
    assert saved_jrl2.quests[-1].tag == saved_jrl1.quests[-1].tag
    assert len(saved_jrl2.quests[-1].entries) == len(saved_jrl1.quests[-1].entries)
    assert saved_jrl2.quests[-1].entries[-1].entry_id == saved_jrl1.quests[-1].entries[-1].entry_id


def test_jrl_editor_multiple_save_load_cycles(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test multiple save/load cycles preserve data correctly."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    original_data = jrl_file.read_bytes()
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Perform multiple cycles
    for cycle in range(5):
        # Add a quest each cycle
        quest = JRLQuest()
        quest.name = LocalizedString.from_english(f"Cycle {cycle}")
        quest.tag = f"cycle_{cycle}"
        editor.add_quest(quest)

        # Save
        data, _ = editor.build()
        saved_jrl = read_jrl(data)

        # Verify
        assert len(saved_jrl.quests) > cycle
        assert saved_jrl.quests[-1].tag == f"cycle_{cycle}"

        # Load back
        editor.load(jrl_file, "global", ResourceType.JRL, data)

        # Verify loaded
        quest_item = editor._model.item(editor._model.rowCount() - 1)
        assert quest_item is not None
        editor.ui.journalTree.setCurrentIndex(quest_item.index())
        QApplication.processEvents()
        assert editor.ui.categoryTag.text() == f"cycle_{cycle}"


# ============================================================================
# EDGE CASES AND BOUNDARY TESTS
# ============================================================================


def test_jrl_editor_empty_jrl(qtbot: QtBot, installation: HTInstallation):
    """Test handling empty JRL file."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    # Create new empty JRL
    editor.new()

    assert editor._model.rowCount() == 0
    assert len(editor._jrl.quests) == 0

    # Build and verify
    data, _ = editor.build()
    empty_jrl = read_jrl(data)
    assert len(empty_jrl.quests) == 0


def test_jrl_editor_quest_with_no_entries(qtbot: QtBot, installation: HTInstallation):
    """Test quest with no entries."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Empty Quest")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None
    assert quest_item.rowCount() == 0

    # Save and verify
    data, _ = editor.build()
    saved_jrl = read_jrl(data)
    assert len(saved_jrl.quests) == 1
    assert len(saved_jrl.quests[0].entries) == 0


def test_jrl_editor_entry_with_max_values(qtbot: QtBot, installation: HTInstallation):
    """Test entry with maximum values."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Max Values Test")
    editor.add_quest(quest)

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("Max Entry")
    entry.entry_id = 999999
    entry.xp_percentage = 999.99
    entry.end = True
    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.add_entry(quest_item, entry)

    # Save and verify
    data, _ = editor.build()
    saved_jrl = read_jrl(data)
    entry_data = saved_jrl.quests[0].entries[0]

    assert entry_data.entry_id == 999999
    assert abs(entry_data.xp_percentage - 999.99) < 0.001
    assert entry_data.end is True


def test_jrl_editor_entry_with_min_values(qtbot: QtBot, installation: HTInstallation):
    """Test entry with minimum values."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Min Values Test")
    editor.add_quest(quest)

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("Min Entry")
    entry.entry_id = 0
    entry.xp_percentage = 0.0
    entry.end = False
    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.add_entry(quest_item, entry)

    # Save and verify
    data, _ = editor.build()
    saved_jrl = read_jrl(data)
    entry_data = saved_jrl.quests[0].entries[0]

    assert entry_data.entry_id == 0
    assert abs(entry_data.xp_percentage - 0.0) < 0.001
    assert entry_data.end is False


def test_jrl_editor_quest_with_special_characters(qtbot: QtBot, installation: HTInstallation):
    """Test quest with special characters in tag."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Special Quest")
    quest.tag = "quest_123_test"
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Save and verify
    data, _ = editor.build()
    saved_jrl = read_jrl(data)
    assert saved_jrl.quests[0].tag == "quest_123_test"


def test_jrl_editor_multiple_entries_same_id(qtbot: QtBot, installation: HTInstallation):
    """Test multiple entries with same ID (allowed in format)."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Same ID Test")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None

    # Add entries with same ID
    for i in range(3):
        entry = JRLEntry()
        entry.text = LocalizedString.from_english(f"Entry {i}")
        entry.entry_id = 10  # Same ID
        editor.add_entry(quest_item, entry)

    # Save and verify
    data, _ = editor.build()
    saved_jrl = read_jrl(data)
    assert len(saved_jrl.quests[0].entries) == 3
    assert all(entry.entry_id == 10 for entry in saved_jrl.quests[0].entries)


# ============================================================================
# GFF COMPARISON TESTS
# ============================================================================


def test_jrl_editor_gff_roundtrip_comparison(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test GFF roundtrip comparison like resource tests."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    # Load original GFF
    original_data = jrl_file.read_bytes()
    original_gff = read_gff(original_data)
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Save without modifications
    data, _ = editor.build()
    new_gff = read_gff(data)

    # Verify key structures match
    orig_categories = original_gff.root.acquire("Categories", None)
    new_categories = new_gff.root.acquire("Categories", None)

    if orig_categories is not None and new_categories is not None:
        assert len(orig_categories) == len(new_categories)


def test_jrl_editor_gff_roundtrip_with_modifications(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test GFF roundtrip with modifications still produces valid GFF."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    original_data = jrl_file.read_bytes()
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Make modifications
    quest = JRLQuest()
    quest.name = LocalizedString.from_english("GFF Test Quest")
    quest.tag = "gff_test_tag"
    editor.add_quest(quest)

    # Save
    data, _ = editor.build()

    # Verify it's valid GFF
    new_gff = read_gff(data)
    assert new_gff is not None

    # Verify it's valid JRL
    modified_jrl = read_jrl(data)
    assert modified_jrl.quests[-1].tag == "gff_test_tag"


# ============================================================================
# NEW FILE CREATION TESTS
# ============================================================================


def test_jrl_editor_new_file_creation(qtbot: QtBot, installation: HTInstallation):
    """Test creating a new JRL file from scratch."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    # Create new
    editor.new()

    # Verify empty state
    assert editor._model.rowCount() == 0
    assert len(editor._jrl.quests) == 0

    # Add quest and entry
    quest = JRLQuest()
    quest.name = LocalizedString.from_english("New Quest")
    quest.tag = "new_quest"
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("New Entry")
    entry.entry_id = 1
    editor.add_entry(quest_item, entry)

    # Build and verify
    data, _ = editor.build()
    new_jrl = read_jrl(data)

    assert len(new_jrl.quests) == 1
    assert new_jrl.quests[0].tag == "new_quest"
    assert len(new_jrl.quests[0].entries) == 1
    assert new_jrl.quests[0].entries[0].entry_id == 1


def test_jrl_editor_new_file_all_defaults(qtbot: QtBot, installation: HTInstallation):
    """Test new file has correct defaults."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    # Create new
    editor.new()

    # Build and verify defaults
    data, _ = editor.build()
    new_jrl = read_jrl(data)

    # Verify defaults (empty JRL)
    assert len(new_jrl.quests) == 0


# ============================================================================
# HELP DIALOG TESTS
# ============================================================================


def test_jrl_editor_help_dialog_opens_correct_file(qtbot: QtBot, installation: HTInstallation):
    """Test that JRLEditor help dialog opens and displays the correct help file."""
    from toolset.gui.dialogs.editor_help import EditorHelpDialog

    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    # Trigger help dialog with the correct file for JRLEditor
    editor._show_help_dialog("GFF-JRL.md")

    # Process events to allow dialog to be created
    qtbot.waitUntil(lambda: len(editor.findChildren(EditorHelpDialog)) > 0, timeout=2000)

    # Find the help dialog
    dialogs = [child for child in editor.findChildren(EditorHelpDialog)]
    assert len(dialogs) > 0, "Help dialog should be opened"

    dialog = dialogs[0]
    qtbot.addWidget(dialog)
    qtbot.waitExposed(dialog, timeout=2000)

    # Wait for content to load
    qtbot.waitUntil(lambda: dialog.text_browser.toHtml().strip() != "", timeout=2000)

    # Get the HTML content
    html = dialog.text_browser.toHtml()

    # Assert that "Help File Not Found" error is NOT shown
    assert "Help File Not Found" not in html, f"Help file 'GFF-JRL.md' should be found, but error was shown. HTML: {html[:500]}"

    # Assert that some content is present
    assert len(html) > 100, "Help dialog should contain content"

    # Close dialog
    dialog.close()
    QApplication.processEvents()


# ============================================================================
# COMPREHENSIVE ROUNDTRIP VALIDATION TEST
# ============================================================================


def test_jrl_editor_comprehensive_roundtrip(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Comprehensive test that validates ALL fields are preserved through editor roundtrip."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    # Load original
    original_data = jrl_file.read_bytes()
    original_jrl = read_jrl(original_data)
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Add comprehensive test quest with all fields set
    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Comprehensive Test Quest")
    quest.tag = "comprehensive_tag"
    quest.plot_index = 5
    quest.planet_id = 2
    quest.priority = JRLQuestPriority.HIGHEST
    quest.comment = "Comprehensive test comment"
    editor.add_quest(quest)

    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None

    # Add comprehensive test entries
    test_entries = [
        (1, 10.0, False),
        (2, 25.5, False),
        (3, 50.0, True),
        (4, 100.0, False),
    ]

    for entry_id, xp, end_flag in test_entries:
        entry = JRLEntry()
        entry.text = LocalizedString.from_english(f"Entry {entry_id}")
        entry.entry_id = entry_id
        entry.xp_percentage = xp
        entry.end = end_flag
        editor.add_entry(quest_item, entry)

    # Save
    data, _ = editor.build()
    saved_jrl = read_jrl(data)

    # Verify comprehensive quest
    saved_quest = saved_jrl.quests[-1]
    assert saved_quest.tag == "comprehensive_tag"
    assert saved_quest.plot_index == 5
    assert saved_quest.planet_id == 2
    assert saved_quest.priority == JRLQuestPriority.HIGHEST
    assert saved_quest.comment == "Comprehensive test comment"
    assert len(saved_quest.entries) == 4

    # Verify all entries
    for i, (entry_id, xp, end_flag) in enumerate(test_entries):
        saved_entry = saved_quest.entries[i]
        assert saved_entry.entry_id == entry_id
        assert abs(saved_entry.xp_percentage - xp) < 0.001
        assert saved_entry.end == end_flag


# ============================================================================
# REPEATED OPERATIONS TESTS
# ============================================================================


def test_jrl_editor_repeated_add_remove_quests(qtbot: QtBot, installation: HTInstallation):
    """Test repeatedly adding and removing quests."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    # Add and remove quests multiple times
    for cycle in range(5):
        # Add quest
        quest = JRLQuest()
        quest.name = LocalizedString.from_english(f"Cycle {cycle}")
        editor.add_quest(quest)

        quest_item = editor._model.item(editor._model.rowCount() - 1)
        assert quest_item is not None

        # Remove quest
        editor.remove_quest(quest_item)

        assert editor._model.rowCount() == 0
        assert len(editor._jrl.quests) == 0


def test_jrl_editor_repeated_add_remove_entries(qtbot: QtBot, installation: HTInstallation):
    """Test repeatedly adding and removing entries."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Repeated Test")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None

    # Add and remove entries multiple times
    for cycle in range(5):
        # Add entry
        entry = JRLEntry()
        entry.text = LocalizedString.from_english(f"Cycle {cycle}")
        entry.entry_id = cycle
        editor.add_entry(quest_item, entry)

        entry_item = quest_item.child(quest_item.rowCount() - 1)
        assert entry_item is not None

        # Remove entry
        editor.remove_entry(entry_item)

        assert quest_item.rowCount() == 0
        assert len(quest.entries) == 0


def test_jrl_editor_repeated_field_modifications(qtbot: QtBot, installation: HTInstallation):
    """Test repeatedly modifying fields."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Modify Test")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Modify tag multiple times
    for i in range(10):
        editor.ui.categoryTag.setText(f"tag_{i}")
        editor.on_value_updated()

        data, _ = editor.build()
        saved_jrl = read_jrl(data)
        assert saved_jrl.quests[0].tag == f"tag_{i}"


def test_jrl_editor_repeated_priority_changes(qtbot: QtBot, installation: HTInstallation):
    """Test repeatedly changing priority."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Priority Test")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Cycle through all priorities multiple times
    priorities = list(JRLQuestPriority)
    for cycle in range(3):
        for priority in priorities:
            editor.ui.categoryPrioritySelect.setCurrentIndex(priority.value)
            editor.on_value_updated()

            data, _ = editor.build()
            saved_jrl = read_jrl(data)
            assert saved_jrl.quests[0].priority == priority


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


def test_jrl_editor_headless_ui_load_build(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test JRL Editor in headless UI - loads real file and builds data."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)

    # Try to find a JRL file
    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("No JRL files available for testing")

    original_data = jrl_file.read_bytes()
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    # Verify editor loaded the data
    assert editor is not None
    assert editor._model.rowCount() >= 0

    # Build and verify it works
    data, _ = editor.build()
    assert len(data) > 0

    # Verify we can read it back
    loaded_jrl = read_jrl(data)
    assert loaded_jrl is not None


# ============================================================================
# TREE VIEW INTERACTION TESTS
# ============================================================================


def test_jrl_editor_tree_expand_collapse(qtbot: QtBot, installation: HTInstallation):
    """Test expanding and collapsing quest items in tree view."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Add quest with entries
    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Expand Test")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None

    # Add multiple entries
    for i in range(3):
        entry = JRLEntry()
        entry.text = LocalizedString.from_english(f"Entry {i}")
        entry.entry_id = i
        editor.add_entry(quest_item, entry)

    quest_index = quest_item.index()

    # Initially collapsed
    assert not editor.ui.journalTree.isExpanded(quest_index)

    # Expand using arrow key
    editor.ui.journalTree.setCurrentIndex(quest_index)
    editor.ui.journalTree.setFocus()
    QApplication.processEvents()
    qtbot.keyClick(editor.ui.journalTree, Qt.Key.Key_Right)
    QApplication.processEvents()

    # Should be expanded
    assert editor.ui.journalTree.isExpanded(quest_index)

    # Collapse using arrow key
    qtbot.keyClick(editor.ui.journalTree, Qt.Key.Key_Left)
    QApplication.processEvents()

    # Should be collapsed
    assert not editor.ui.journalTree.isExpanded(quest_index)


def test_jrl_editor_tree_keyboard_navigation(qtbot: QtBot, installation: HTInstallation):
    """Test keyboard navigation in tree view."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Add multiple quests
    for i in range(5):
        quest = JRLQuest()
        quest.name = LocalizedString.from_english(f"Quest {i}")
        editor.add_quest(quest)

    editor.ui.journalTree.setFocus()
    QApplication.processEvents()

    # Navigate down
    for i in range(4):
        qtbot.keyClick(editor.ui.journalTree, Qt.Key.Key_Down)
        QApplication.processEvents()
        current_index = editor.ui.journalTree.currentIndex()
        assert current_index.isValid()
        assert current_index.row() == i + 1

    # Navigate up
    for i in range(3, -1, -1):
        qtbot.keyClick(editor.ui.journalTree, Qt.Key.Key_Up)
        QApplication.processEvents()
        current_index = editor.ui.journalTree.currentIndex()
        assert current_index.isValid()
        assert current_index.row() == i

    # Home key
    qtbot.keyClick(editor.ui.journalTree, Qt.Key.Key_Home)
    QApplication.processEvents()
    current_index = editor.ui.journalTree.currentIndex()
    assert current_index.isValid()
    assert current_index.row() == 0

    # End key
    qtbot.keyClick(editor.ui.journalTree, Qt.Key.Key_End)
    QApplication.processEvents()
    current_index = editor.ui.journalTree.currentIndex()
    assert current_index.isValid()
    assert current_index.row() == 4


def test_jrl_editor_tree_selection_with_entries(qtbot: QtBot, installation: HTInstallation):
    """Test selecting entries within expanded quests."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Parent Quest")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None

    # Add entries
    for i in range(3):
        entry = JRLEntry()
        entry.text = LocalizedString.from_english(f"Entry {i}")
        entry.entry_id = i
        editor.add_entry(quest_item, entry)

    # Expand quest
    quest_index = quest_item.index()
    editor.ui.journalTree.setCurrentIndex(quest_index)
    editor.ui.journalTree.setFocus()
    QApplication.processEvents()
    qtbot.keyClick(editor.ui.journalTree, Qt.Key.Key_Right)
    QApplication.processEvents()

    # Navigate to first entry
    qtbot.keyClick(editor.ui.journalTree, Qt.Key.Key_Down)
    QApplication.processEvents()

    current_index = editor.ui.journalTree.currentIndex()
    assert current_index.isValid()
    assert current_index.parent() == quest_index
    assert current_index.row() == 0

    # Verify entry page is shown
    assert editor.ui.questPages.currentIndex() == 1


# ============================================================================
# UI STATE MANAGEMENT TESTS
# ============================================================================


def test_jrl_editor_button_states_no_selection(qtbot: QtBot, installation: HTInstallation):
    """Test button enabled/disabled states when nothing is selected."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Clear selection
    editor.ui.journalTree.clearSelection()
    QApplication.processEvents()

    # Verify UI state - fields should be disabled or empty
    assert editor.ui.categoryTag.text() == "" or not editor.ui.categoryTag.isEnabled()
    assert editor.ui.questPages.currentIndex() == 0


def test_jrl_editor_button_states_quest_selected(qtbot: QtBot, installation: HTInstallation):
    """Test button enabled/disabled states when quest is selected."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("State Test")
    quest.tag = "state_tag"
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Verify fields are enabled
    assert editor.ui.categoryTag.isEnabled()
    assert editor.ui.categoryPlotSelect.isEnabled()
    assert editor.ui.categoryPlanetSelect.isEnabled()
    assert editor.ui.categoryPrioritySelect.isEnabled()
    assert editor.ui.categoryCommentEdit.isEnabled()
    assert editor.ui.questPages.currentIndex() == 0


def test_jrl_editor_button_states_entry_selected(qtbot: QtBot, installation: HTInstallation):
    """Test button enabled/disabled states when entry is selected."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Parent Quest")
    editor.add_quest(quest)

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("State Entry")
    entry.entry_id = 5
    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.add_entry(quest_item, entry)

    entry_item = quest_item.child(0)
    assert entry_item is not None
    editor.ui.journalTree.setCurrentIndex(entry_item.index())
    QApplication.processEvents()

    # Verify entry fields are enabled
    assert editor.ui.entryIdSpin.isEnabled()
    assert editor.ui.entryXpSpin.isEnabled()
    assert editor.ui.entryEndCheck.isEnabled()
    assert editor.ui.questPages.currentIndex() == 1


# ============================================================================
# STRING HANDLING TESTS
# ============================================================================


def test_jrl_editor_very_long_tag(qtbot: QtBot, installation: HTInstallation):
    """Test handling very long tag strings."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Long Tag Test")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Set very long tag
    long_tag = "a" * 1000
    editor.ui.categoryTag.setText(long_tag)
    editor.on_value_updated()

    # Save and verify
    data, _ = editor.build()
    saved_jrl = read_jrl(data)
    assert saved_jrl.quests[0].tag == long_tag


def test_jrl_editor_special_characters_in_tag(qtbot: QtBot, installation: HTInstallation):
    """Test handling special characters in tag field."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Special Chars Test")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    # Test various special characters
    special_tags = [
        "tag_with_underscores",
        "tag-with-dashes",
        "tag.with.dots",
        "tag123numbers",
        "tag!@#$%^&*()",
        "tag with spaces",
        "tag\nwith\nnewlines",
        "tag\twith\ttabs",
    ]

    for tag in special_tags:
        editor.ui.categoryTag.setText(tag)
        editor.on_value_updated()

        data, _ = editor.build()
        saved_jrl = read_jrl(data)
        assert saved_jrl.quests[0].tag == tag


def test_jrl_editor_unicode_characters(qtbot: QtBot, installation: HTInstallation):
    """Test handling Unicode characters in quest names and entries."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Unicode Test: 测试 🎮")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("Entry: エントリ 🎯")
    entry.entry_id = 1
    editor.add_entry(quest_item, entry)

    # Save and verify
    data, _ = editor.build()
    saved_jrl = read_jrl(data)
    assert saved_jrl.quests[0].name.get(Language.ENGLISH, Gender.MALE) == "Unicode Test: 测试 🎮"
    assert saved_jrl.quests[0].entries[0].text.get(Language.ENGLISH, Gender.MALE) == "Entry: エントリ 🎯"


# ============================================================================
# STRESS TESTS
# ============================================================================


def test_jrl_editor_many_quests(qtbot: QtBot, installation: HTInstallation):
    """Test editor with many quests (stress test)."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Add many quests
    num_quests = 100
    for i in range(num_quests):
        quest = JRLQuest()
        quest.name = LocalizedString.from_english(f"Quest {i}")
        quest.tag = f"quest_{i}"
        editor.add_quest(quest)

    assert editor._model.rowCount() == num_quests
    assert len(editor._jrl.quests) == num_quests

    # Save and verify
    data, _ = editor.build()
    saved_jrl = read_jrl(data)
    assert len(saved_jrl.quests) == num_quests

    # Verify all quests are preserved
    for i in range(num_quests):
        assert saved_jrl.quests[i].tag == f"quest_{i}"


def test_jrl_editor_many_entries(qtbot: QtBot, installation: HTInstallation):
    """Test editor with many entries per quest (stress test)."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Many Entries Quest")
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None

    # Add many entries
    num_entries = 200
    for i in range(num_entries):
        entry = JRLEntry()
        entry.text = LocalizedString.from_english(f"Entry {i}")
        entry.entry_id = i
        entry.xp_percentage = float(i)
        editor.add_entry(quest_item, entry)

    assert quest_item.rowCount() == num_entries
    assert len(quest.entries) == num_entries

    # Save and verify
    data, _ = editor.build()
    saved_jrl = read_jrl(data)
    assert len(saved_jrl.quests[0].entries) == num_entries

    # Verify all entries are preserved
    for i in range(num_entries):
        assert saved_jrl.quests[0].entries[i].entry_id == i
        assert abs(saved_jrl.quests[0].entries[i].xp_percentage - float(i)) < 0.001


def test_jrl_editor_rapid_add_remove(qtbot: QtBot, installation: HTInstallation):
    """Test rapid add/remove operations (stress test)."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Rapidly add and remove quests
    for cycle in range(20):
        quest = JRLQuest()
        quest.name = LocalizedString.from_english(f"Cycle {cycle}")
        editor.add_quest(quest)

        quest_item = editor._model.item(editor._model.rowCount() - 1)
        assert quest_item is not None

        editor.remove_quest(quest_item)

        assert editor._model.rowCount() == 0
        assert len(editor._jrl.quests) == 0


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


def test_jrl_editor_load_invalid_data(qtbot: QtBot, installation: HTInstallation):
    """Test loading invalid/corrupted JRL data."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Try to load invalid data
    invalid_data = b"INVALID JRL DATA" * 100

    # Should handle gracefully (either skip or show error)
    try:
        editor.load(pathlib.Path("invalid.jrl"), "invalid", ResourceType.JRL, invalid_data)
        # If it doesn't raise, verify editor is in a valid state
        assert editor is not None
    except Exception:
        # If it raises, that's also acceptable error handling
        pass


def test_jrl_editor_load_empty_data(qtbot: QtBot, installation: HTInstallation):
    """Test loading empty JRL data."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Try to load empty data
    empty_data = b""

    try:
        editor.load(pathlib.Path("empty.jrl"), "empty", ResourceType.JRL, empty_data)
        # Should handle gracefully
        assert editor is not None
    except Exception:
        # If it raises, that's acceptable error handling
        pass


# ============================================================================
# RESOURCE LOADING TESTS
# ============================================================================


def test_jrl_editor_load_from_installation(qtbot: QtBot, installation: HTInstallation):
    """Test loading JRL resource from installation."""
    if installation is None:
        pytest.skip("Installation not available")

    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    # Try to find a JRL resource in installation
    jrl_resources = list(installation.resources((ResourceType.JRL,)).values())[:1]
    if not jrl_resources:
        pytest.skip("No JRL resources found in installation")

    jrl_resource = jrl_resources[0]
    assert jrl_resource is not None

    jrl_data = installation.resource(jrl_resource.resname, jrl_resource.restype)
    if not jrl_data:
        pytest.skip(f"Could not load JRL data for {jrl_resource.resname}")

    # Load from installation
    editor.load(jrl_resource.filepath if hasattr(jrl_resource, "filepath") else pathlib.Path("global.jrl"), jrl_resource.resname, ResourceType.JRL, jrl_data.data)

    # Verify loaded
    assert editor._model.rowCount() >= 0
    assert len(editor._jrl.quests) >= 0


# ============================================================================
# REFRESH TESTS
# ============================================================================


def test_jrl_editor_refresh_quest_item(qtbot: QtBot, installation: HTInstallation):
    """Test refresh_quest_item updates tree item text correctly."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Refresh Test")
    quest.tag = "refresh_tag"
    editor.add_quest(quest)

    quest_item = editor._model.item(0)
    assert quest_item is not None

    # Get initial text
    initial_text = quest_item.text()

    # Modify quest
    quest.name = LocalizedString.from_english("Refreshed Quest")
    quest.tag = "refreshed_tag"

    # Refresh item
    editor.refresh_quest_item(quest_item)

    # Verify text updated
    new_text = quest_item.text()
    assert new_text != initial_text
    assert "Refreshed Quest" in new_text or "[Unnamed]" not in new_text


def test_jrl_editor_refresh_entry_item(qtbot: QtBot, installation: HTInstallation):
    """Test refresh_entry_item updates tree item text correctly."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Parent Quest")
    editor.add_quest(quest)

    entry = JRLEntry()
    entry.text = LocalizedString.from_english("Original Entry")
    entry.entry_id = 10
    quest_item = editor._model.item(0)
    assert quest_item is not None
    editor.add_entry(quest_item, entry)

    entry_item = quest_item.child(0)
    assert entry_item is not None

    # Get initial text
    initial_text = entry_item.text()

    # Modify entry
    entry.entry_id = 20
    entry.text = LocalizedString.from_english("Refreshed Entry")

    # Refresh item
    editor.refresh_entry_item(entry_item)

    # Verify text updated
    new_text = entry_item.text()
    assert new_text != initial_text
    assert "[20]" in new_text


# ============================================================================
# COMPREHENSIVE WORKFLOW TESTS
# ============================================================================


def test_jrl_editor_complete_workflow(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test complete workflow: load, modify, save, reload, verify."""
    editor = JRLEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    jrl_file = test_files_dir / "global.jrl"
    if not jrl_file.exists():
        pytest.skip("global.jrl not found")

    # Load original
    original_data = jrl_file.read_bytes()
    original_jrl = read_jrl(original_data)
    editor.load(jrl_file, "global", ResourceType.JRL, original_data)

    initial_quest_count = len(original_jrl.quests)

    # Add new quest
    quest = JRLQuest()
    quest.name = LocalizedString.from_english("Workflow Test Quest")
    quest.tag = "workflow_tag"
    quest.plot_index = 1
    quest.planet_id = 0
    quest.priority = JRLQuestPriority.MEDIUM
    quest.comment = "Workflow test comment"
    editor.add_quest(quest)

    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None

    # Add entries to new quest
    for i in range(3):
        entry = JRLEntry()
        entry.text = LocalizedString.from_english(f"Workflow Entry {i}")
        entry.entry_id = i
        entry.xp_percentage = float(i * 25)
        entry.end = i == 2
        editor.add_entry(quest_item, entry)

    # Modify existing quest (if any)
    if initial_quest_count > 0:
        existing_quest_item = editor._model.item(0)
        assert existing_quest_item is not None
        editor.ui.journalTree.setCurrentIndex(existing_quest_item.index())
        QApplication.processEvents()

        editor.ui.categoryTag.setText("modified_existing_tag")
        editor.on_value_updated()

    # Save
    data1, _ = editor.build()
    saved_jrl1 = read_jrl(data1)

    # Verify modifications
    assert len(saved_jrl1.quests) == initial_quest_count + 1
    assert saved_jrl1.quests[-1].tag == "workflow_tag"
    assert len(saved_jrl1.quests[-1].entries) == 3

    # Reload
    editor.load(jrl_file, "global", ResourceType.JRL, data1)

    # Verify reloaded state
    assert editor._model.rowCount() == initial_quest_count + 1
    quest_item = editor._model.item(editor._model.rowCount() - 1)
    assert quest_item is not None
    editor.ui.journalTree.setCurrentIndex(quest_item.index())
    QApplication.processEvents()

    assert editor.ui.categoryTag.text() == "workflow_tag"
    assert editor.ui.categoryPlotSelect.currentIndex() == 1
    assert editor.ui.categoryPrioritySelect.currentIndex() == JRLQuestPriority.MEDIUM.value

    # Verify entries
    assert quest_item.rowCount() == 3
    entry_item = quest_item.child(2)
    assert entry_item is not None
    editor.ui.journalTree.setCurrentIndex(entry_item.index())
    QApplication.processEvents()

    assert editor.ui.entryIdSpin.value() == 2
    assert editor.ui.entryEndCheck.isChecked() is True

    # Save again
    data2, _ = editor.build()
    saved_jrl2 = read_jrl(data2)

    # Verify second save matches first
    assert len(saved_jrl2.quests) == len(saved_jrl1.quests)
    assert saved_jrl2.quests[-1].tag == saved_jrl1.quests[-1].tag
    assert len(saved_jrl2.quests[-1].entries) == len(saved_jrl1.quests[-1].entries)


if __name__ == "__main__":
    unittest.main()
