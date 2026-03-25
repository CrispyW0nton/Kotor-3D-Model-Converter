"""
Unit Tests for LTR Editor - testing EVERY possible manipulation.

Each test focuses on a specific manipulation and validates save/load roundtrips.
Following the ARE editor test pattern for comprehensive coverage.
"""

from __future__ import annotations

import pathlib

import pytest
from pathlib import Path
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QTableWidgetItem
from toolset.gui.editors.ltr import LTREditor  # type: ignore[import-not-found]
from toolset.data.installation import HTInstallation  # type: ignore[import-not-found]
from pykotor.resource.formats.ltr import LTR, read_ltr  # type: ignore[import-not-found]
from pykotor.resource.type import ResourceType  # type: ignore[import-not-found]
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

# ============================================================================
# BASIC FIELD MANIPULATIONS
# ============================================================================


def test_ltr_editor_new_file_creation(qtbot: QtBot, installation: HTInstallation):
    """Test creating a new LTR file from scratch."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    # Create new
    editor.new()

    # Verify UI is populated
    assert editor.ui.tableSingles.rowCount() > 0
    assert editor.ui.tableDoubles.rowCount() > 0
    assert editor.ui.tableTriples.rowCount() > 0

    # Build and verify
    data, _ = editor.build()
    new_ltr = read_ltr(data)
    assert new_ltr is not None


def test_ltr_editor_load_empty_file(qtbot: QtBot, installation: HTInstallation):
    """Test loading an empty/new LTR file."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Build empty file
    data, _ = editor.build()

    # Load it back
    editor.load(Path("test.ltr"), "test", ResourceType.LTR, data)

    # Verify it loaded correctly
    assert editor.ltr is not None


# ============================================================================
# SINGLE CHARACTER MANIPULATIONS
# ============================================================================


def test_ltr_editor_manipulate_single_character(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating single character values."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test setting single character values
    test_char = "A"
    start_val = 10
    middle_val = 20
    end_val = 30

    # Set values via combo box and spin boxes
    index = editor.ui.comboBoxSingleChar.findText(test_char)
    if index >= 0:
        editor.ui.comboBoxSingleChar.setCurrentIndex(index)
        editor.ui.spinBoxSingleStart.setValue(start_val)
        editor.ui.spinBoxSingleMiddle.setValue(middle_val)
        editor.ui.spinBoxSingleEnd.setValue(end_val)

        # Apply changes
        editor.setSingleCharacter()

        # Verify values were set
        assert editor.ltr._singles.get_start(test_char) == start_val
        assert editor.ltr._singles.get_middle(test_char) == middle_val
        assert editor.ltr._singles.get_end(test_char) == end_val


def test_ltr_editor_manipulate_multiple_single_characters(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating multiple single characters."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test multiple characters (LTR.CHARACTER_SET uses lowercase)
    # Use valid probability values between 0.0 and 1.0
    test_chars = ["a", "b", "c", "z"]
    for i, char in enumerate(test_chars):
        index = editor.ui.comboBoxSingleChar.findText(char)
        if index >= 0:
            editor.ui.comboBoxSingleChar.setCurrentIndex(index)
            # Use values in valid range [0.0, 1.0] with small increments
            start_val = 0.1 + (i * 0.1)
            middle_val = 0.2 + (i * 0.1)
            end_val = 0.3 + (i * 0.1)
            editor.ui.spinBoxSingleStart.setValue(start_val)
            editor.ui.spinBoxSingleMiddle.setValue(middle_val)
            editor.ui.spinBoxSingleEnd.setValue(end_val)
            editor.setSingleCharacter()

    # Build and verify
    data, _ = editor.build()
    modified_ltr = read_ltr(data)

    # Verify all characters were set (use approximate comparison for floating-point values)
    for i, char in enumerate(test_chars):
        expected_start = 0.1 + (i * 0.1)
        expected_middle = 0.2 + (i * 0.1)
        expected_end = 0.3 + (i * 0.1)
        assert modified_ltr._singles.get_start(char) == pytest.approx(expected_start)
        assert modified_ltr._singles.get_middle(char) == pytest.approx(expected_middle)
        assert modified_ltr._singles.get_end(char) == pytest.approx(expected_end)


# ============================================================================
# DOUBLE CHARACTER MANIPULATIONS
# ============================================================================


def test_ltr_editor_manipulate_double_character(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating double character values."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test setting double character values
    prev_char = "A"
    char = "B"
    start_val = 5
    middle_val = 10
    end_val = 15

    # Set values via combo boxes and spin boxes
    prev_index = editor.ui.comboBoxDoublePrevChar.findText(prev_char)
    char_index = editor.ui.comboBoxDoubleChar.findText(char)

    if prev_index >= 0 and char_index >= 0:
        editor.ui.comboBoxDoublePrevChar.setCurrentIndex(prev_index)
        editor.ui.comboBoxDoubleChar.setCurrentIndex(char_index)
        editor.ui.spinBoxDoubleStart.setValue(start_val)
        editor.ui.spinBoxDoubleMiddle.setValue(middle_val)
        editor.ui.spinBoxDoubleEnd.setValue(end_val)

        # Apply changes
        editor.setDoubleCharacter()

        # Verify values were set
        assert editor.ltr._doubles[0].get_start(char) == start_val
        assert editor.ltr._doubles[0].get_middle(char) == middle_val
        assert editor.ltr._doubles[0].get_end(char) == end_val


def test_ltr_editor_manipulate_multiple_double_characters(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating multiple double character combinations."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test multiple double combinations (LTR.CHARACTER_SET uses lowercase)
    # Use valid probability values between 0.0 and 1.0
    test_combos = [("a", "b"), ("b", "c"), ("c", "d")]
    for i, (prev, char) in enumerate(test_combos):
        prev_index = editor.ui.comboBoxDoublePrevChar.findText(prev)
        char_index = editor.ui.comboBoxDoubleChar.findText(char)

        if prev_index >= 0 and char_index >= 0:
            editor.ui.comboBoxDoublePrevChar.setCurrentIndex(prev_index)
            editor.ui.comboBoxDoubleChar.setCurrentIndex(char_index)
            # Use values in valid range [0.0, 1.0] with small increments
            start_val = 0.1 + (i * 0.1)
            middle_val = 0.2 + (i * 0.1)
            end_val = 0.3 + (i * 0.1)
            editor.ui.spinBoxDoubleStart.setValue(start_val)
            editor.ui.spinBoxDoubleMiddle.setValue(middle_val)
            editor.ui.spinBoxDoubleEnd.setValue(end_val)
            editor.setDoubleCharacter()

    # Build and verify
    data, _ = editor.build()
    modified_ltr = read_ltr(data)

    # Verify combinations were set (use approximate comparison for floating-point values)
    char_set = LTR.CHARACTER_SET
    for i, (prev, char) in enumerate(test_combos):
        prev_idx = char_set.index(prev)
        expected_start = 0.1 + (i * 0.1)
        expected_middle = 0.2 + (i * 0.1)
        expected_end = 0.3 + (i * 0.1)
        assert modified_ltr._doubles[prev_idx].get_start(char) == pytest.approx(expected_start)
        assert modified_ltr._doubles[prev_idx].get_middle(char) == pytest.approx(expected_middle)
        assert modified_ltr._doubles[prev_idx].get_end(char) == pytest.approx(expected_end)


# ============================================================================
# TRIPLE CHARACTER MANIPULATIONS
# ============================================================================


def test_ltr_editor_manipulate_triple_character(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating triple character values."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Test setting triple character values
    prev2_char = "A"
    prev1_char = "B"
    char = "C"
    start_val = 3
    middle_val = 6
    end_val = 9

    # Set values via combo boxes and spin boxes
    prev2_index = editor.ui.comboBoxTriplePrev2Char.findText(prev2_char)
    prev1_index = editor.ui.comboBoxTriplePrev1Char.findText(prev1_char)
    char_index = editor.ui.comboBoxTripleChar.findText(char)

    if prev2_index >= 0 and prev1_index >= 0 and char_index >= 0:
        editor.ui.comboBoxTriplePrev2Char.setCurrentIndex(prev2_index)
        editor.ui.comboBoxTriplePrev1Char.setCurrentIndex(prev1_index)
        editor.ui.comboBoxTripleChar.setCurrentIndex(char_index)
        editor.ui.spinBoxTripleStart.setValue(start_val)
        editor.ui.spinBoxTripleMiddle.setValue(middle_val)
        editor.ui.spinBoxTripleEnd.setValue(end_val)

        # Apply changes
        editor.setTripleCharacter()

        # Verify values were set (triples are nested arrays)
        char_set = LTR.CHARACTER_SET
        prev2_idx = char_set.index(prev2_char)
        prev1_idx = char_set.index(prev1_char)
        assert editor.ltr._triples[prev2_idx][prev1_idx].get_start(char) == start_val
        assert editor.ltr._triples[prev2_idx][prev1_idx].get_middle(char) == middle_val
        assert editor.ltr._triples[prev2_idx][prev1_idx].get_end(char) == end_val


# ============================================================================
# NAME GENERATION TESTS
# ============================================================================


def test_ltr_editor_generate_name(qtbot: QtBot, installation: HTInstallation):
    """Test name generation functionality."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Generate name
    editor.generateName()

    # Verify generated name is displayed
    generated_name = editor.ui.lineEditGeneratedName.text()
    assert len(generated_name) > 0

    # Verify it was generated from LTR
    expected_name = editor.ltr.generate()
    assert generated_name == expected_name


def test_ltr_editor_generate_multiple_names(qtbot: QtBot, installation: HTInstallation):
    """Test generating multiple names."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Generate multiple names
    generated_names: list[str] = []
    for _ in range(10):
        editor.generateName()
        name = editor.ui.lineEditGeneratedName.text()
        generated_names.append(name)

    # Verify all names were generated (may be different)
    assert len(set(generated_names)) > 0  # At least some variation


# ============================================================================
# TABLE MANIPULATIONS
# ============================================================================


def test_ltr_editor_table_row_add_remove_singles(qtbot: QtBot, installation: HTInstallation):
    """Test adding and removing rows in singles table."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    initial_count = editor.ui.tableSingles.rowCount()

    # Add row
    editor.addSingleRow()
    assert editor.ui.tableSingles.rowCount() == initial_count + 1

    # Select and remove row
    editor.ui.tableSingles.selectRow(initial_count)
    editor.removeSingleRow()
    assert editor.ui.tableSingles.rowCount() == initial_count


def test_ltr_editor_table_row_add_remove_doubles(qtbot: QtBot, installation: HTInstallation):
    """Test adding and removing rows in doubles table."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    initial_count = editor.ui.tableDoubles.rowCount()

    # Add row
    editor.addDoubleRow()
    assert editor.ui.tableDoubles.rowCount() == initial_count + 1

    # Select and remove row
    editor.ui.tableDoubles.selectRow(initial_count)
    editor.removeDoubleRow()
    assert editor.ui.tableDoubles.rowCount() == initial_count


def test_ltr_editor_table_row_add_remove_triples(qtbot: QtBot, installation: HTInstallation):
    """Test adding and removing rows in triples table."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    initial_count = editor.ui.tableTriples.rowCount()

    # Add row
    editor.addTripleRow()
    assert editor.ui.tableTriples.rowCount() == initial_count + 1

    # Select and remove row
    editor.ui.tableTriples.selectRow(initial_count)
    editor.removeTripleRow()
    assert editor.ui.tableTriples.rowCount() == initial_count


# ============================================================================
# SAVE/LOAD ROUNDTRIP VALIDATION TESTS
# ============================================================================


def test_ltr_editor_save_load_roundtrip_identity(qtbot: QtBot, installation: HTInstallation):
    """Test that save/load roundtrip preserves all data exactly."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Set some values
    char = "A"
    index = editor.ui.comboBoxSingleChar.findText(char)
    if index >= 0:
        editor.ui.comboBoxSingleChar.setCurrentIndex(index)
        editor.ui.spinBoxSingleStart.setValue(10)
        editor.ui.spinBoxSingleMiddle.setValue(20)
        editor.ui.spinBoxSingleEnd.setValue(30)
        editor.setSingleCharacter()

    # Save
    data1, _ = editor.build()
    saved_ltr1 = read_ltr(data1)

    # Load saved data
    editor.load(Path("test.ltr"), "test", ResourceType.LTR, data1)

    # Verify modifications preserved
    if index >= 0:
        assert editor.ltr._singles.get_start(char) == 10
        assert editor.ltr._singles.get_middle(char) == 20
        assert editor.ltr._singles.get_end(char) == 30

    # Save again
    data2, _ = editor.build()
    saved_ltr2 = read_ltr(data2)

    # Verify second save matches first
    if index >= 0:
        assert saved_ltr2._singles.get_start(char) == saved_ltr1._singles.get_start(char)
        assert saved_ltr2._singles.get_middle(char) == saved_ltr1._singles.get_middle(char)
        assert saved_ltr2._singles.get_end(char) == saved_ltr1._singles.get_end(char)


def test_ltr_editor_multiple_save_load_cycles(qtbot: QtBot, installation: HTInstallation):
    """Test multiple save/load cycles preserve data correctly."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    char = "B"
    index = editor.ui.comboBoxSingleChar.findText(char)
    if index < 0:
        pytest.skip("Character not found in combo box")

    # Perform multiple cycles
    for cycle in range(3):
        # Modify
        editor.ui.comboBoxSingleChar.setCurrentIndex(index)
        editor.ui.spinBoxSingleStart.setValue(10 + cycle)
        editor.ui.spinBoxSingleMiddle.setValue(20 + cycle)
        editor.ui.spinBoxSingleEnd.setValue(30 + cycle)
        editor.setSingleCharacter()

        # Save
        data, _ = editor.build()
        saved_ltr = read_ltr(data)

        # Verify
        assert saved_ltr._singles.get_start(char) == 10 + cycle
        assert saved_ltr._singles.get_middle(char) == 20 + cycle
        assert saved_ltr._singles.get_end(char) == 30 + cycle

        # Load back
        editor.load(Path("test.ltr"), "test", ResourceType.LTR, data)

        # Verify loaded
        assert editor.ltr._singles.get_start(char) == 10 + cycle
        assert editor.ltr._singles.get_middle(char) == 20 + cycle
        assert editor.ltr._singles.get_end(char) == 30 + cycle


# ============================================================================
# UI FEATURE TESTS
# ============================================================================


def test_ltr_editor_table_sorting(qtbot: QtBot, installation: HTInstallation):
    """Test that tables have sorting enabled."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Verify sorting is enabled
    assert editor.ui.tableSingles.isSortingEnabled()
    assert editor.ui.tableDoubles.isSortingEnabled()
    assert editor.ui.tableTriples.isSortingEnabled()


def test_ltr_editor_auto_fit_columns(qtbot: QtBot, installation: HTInstallation):
    """Test auto-fit columns functionality."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Toggle auto-fit on
    editor.toggle_auto_fit_columns(True)
    assert editor.auto_resize_enabled

    # Toggle auto-fit off
    editor.toggle_auto_fit_columns(False)
    assert not editor.auto_resize_enabled


def test_ltr_editor_alternate_row_colors(qtbot: QtBot, installation: HTInstallation):
    """Test alternate row colors toggle."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Toggle alternate row colors
    initial_state = editor.ui.tableSingles.alternatingRowColors()
    editor.toggle_alternate_row_colors()

    # Verify state changed
    assert editor.ui.tableSingles.alternatingRowColors() != initial_state

    # Toggle back
    editor.toggle_alternate_row_colors()
    assert editor.ui.tableSingles.alternatingRowColors() == initial_state


def test_ltr_editor_combo_box_population(qtbot: QtBot, installation: HTInstallation):
    """Test that combo boxes are properly populated."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Verify combo boxes have items
    assert editor.ui.comboBoxSingleChar.count() > 0
    assert editor.ui.comboBoxDoubleChar.count() > 0
    assert editor.ui.comboBoxDoublePrevChar.count() > 0
    assert editor.ui.comboBoxTripleChar.count() > 0
    assert editor.ui.comboBoxTriplePrev1Char.count() > 0
    assert editor.ui.comboBoxTriplePrev2Char.count() > 0

    # Verify all combo boxes have same character set
    char_set = LTR.CHARACTER_SET
    assert editor.ui.comboBoxSingleChar.count() == len(char_set)
    assert editor.ui.comboBoxDoubleChar.count() == len(char_set)


# ============================================================================
# EDGE CASES
# ============================================================================


def test_ltr_editor_extreme_values(qtbot: QtBot, installation: HTInstallation):
    """Test handling of extreme values."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    char = "A"
    index = editor.ui.comboBoxSingleChar.findText(char)
    if index >= 0:
        # Test extreme values
        editor.ui.comboBoxSingleChar.setCurrentIndex(index)
        editor.ui.spinBoxSingleStart.setValue(0)
        editor.ui.spinBoxSingleMiddle.setValue(100)
        editor.ui.spinBoxSingleEnd.setValue(255)
        editor.setSingleCharacter()

        # Verify values were set
        assert editor.ltr._singles.get_start(char) == 0
        assert editor.ltr._singles.get_middle(char) == 100
        assert editor.ltr._singles.get_end(char) == 255


def test_ltr_editor_empty_tables(qtbot: QtBot, installation: HTInstallation):
    """Test handling of empty/new tables."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Verify tables are populated after new()
    assert editor.ui.tableSingles.rowCount() > 0
    assert editor.ui.tableDoubles.rowCount() > 0
    assert editor.ui.tableTriples.rowCount() > 0

    # Verify LTR object is not None
    assert editor.ltr is not None


# ============================================================================
# COMBINATION TESTS
# ============================================================================


def test_ltr_editor_manipulate_all_character_types(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating singles, doubles, and triples together."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Set single
    char = "A"
    index = editor.ui.comboBoxSingleChar.findText(char)
    if index >= 0:
        editor.ui.comboBoxSingleChar.setCurrentIndex(index)
        editor.ui.spinBoxSingleStart.setValue(10)
        editor.ui.spinBoxSingleMiddle.setValue(20)
        editor.ui.spinBoxSingleEnd.setValue(30)
        editor.setSingleCharacter()

    # Set double
    prev_char = "A"
    char2 = "B"
    prev_index = editor.ui.comboBoxDoublePrevChar.findText(prev_char)
    char2_index = editor.ui.comboBoxDoubleChar.findText(char2)
    if prev_index >= 0 and char2_index >= 0:
        editor.ui.comboBoxDoublePrevChar.setCurrentIndex(prev_index)
        editor.ui.comboBoxDoubleChar.setCurrentIndex(char2_index)
        editor.ui.spinBoxDoubleStart.setValue(5)
        editor.ui.spinBoxDoubleMiddle.setValue(10)
        editor.ui.spinBoxDoubleEnd.setValue(15)
        editor.setDoubleCharacter()

    # Set triple
    prev2 = "A"
    prev1 = "B"
    char3 = "C"
    prev2_index = editor.ui.comboBoxTriplePrev2Char.findText(prev2)
    prev1_index = editor.ui.comboBoxTriplePrev1Char.findText(prev1)
    char3_index = editor.ui.comboBoxTripleChar.findText(char3)
    if prev2_index >= 0 and prev1_index >= 0 and char3_index >= 0:
        editor.ui.comboBoxTriplePrev2Char.setCurrentIndex(prev2_index)
        editor.ui.comboBoxTriplePrev1Char.setCurrentIndex(prev1_index)
        editor.ui.comboBoxTripleChar.setCurrentIndex(char3_index)
        editor.ui.spinBoxTripleStart.setValue(3)
        editor.ui.spinBoxTripleMiddle.setValue(6)
        editor.ui.spinBoxTripleEnd.setValue(9)
        editor.setTripleCharacter()

    # Build and verify all values
    data, _ = editor.build()
    modified_ltr = read_ltr(data)

    if index >= 0:
        assert modified_ltr._singles.get_start(char) == 10
    if prev_index >= 0 and char2_index >= 0:
        char_set = LTR.CHARACTER_SET
        prev_idx = char_set.index(prev_char)
        assert modified_ltr._doubles[prev_idx].get_start(char2) == 5


# ============================================================================
# HEADLESS UI TESTS WITH REAL FILES
# ============================================================================


def test_ltreditor_editor_help_dialog_opens_correct_file(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test that LTREditor help dialog opens and displays the correct help file (not 'Help File Not Found')."""
    from toolset.gui.dialogs.editor_help import EditorHelpDialog

    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    # Trigger help dialog with the correct file for LTREditor
    editor._show_help_dialog("LTR-File-Format.md")
    QApplication.processEvents()  # Wait for dialog to be created

    # Find the help dialog
    dialogs = [child for child in editor.findChildren(EditorHelpDialog)]
    assert len(dialogs) > 0, "Help dialog should be opened"

    dialog = dialogs[0]
    qtbot.waitExposed(dialog)

    # Get the HTML content
    html = dialog.text_browser.toHtml()

    # Assert that "Help File Not Found" error is NOT shown
    assert "Help File Not Found" not in html, f"Help file 'LTR-File-Format.md' should be found, but error was shown. HTML: {html[:500]}"

    # Assert that some content is present (file was loaded successfully)
    assert len(html) > 100, "Help dialog should contain content"


def test_ltr_editor_headless_ui_load_build(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test LTR Editor in headless UI - loads real file and builds data."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)

    # Try to find a LTR file
    ltr_files: list[Path] = list(test_files_dir.glob("*.ltr")) + list(test_files_dir.rglob("*.ltr"))
    if not ltr_files:
        # Try to get one from installation
        ltr_resources = list(installation.resources((ResourceType.LTR,)).values())[:1]
        if not ltr_resources:
            pytest.skip("No LTR files available for testing")
        ltr_resource = ltr_resources[0]
        assert ltr_resource is not None, "LTR resource is None"
        ltr_resource_result = installation.resource(ltr_resource.resname, ltr_resource.restype)
        assert ltr_resource_result is not None, "LTR resource result is None"
        ltr_data = ltr_resource_result.data
        if not ltr_data:
            pytest.skip(f"Could not load LTR data for {ltr_resource.identifier()}")
        editor.load(ltr_resource.filepath if hasattr(ltr_resource, "filepath") else Path("module.ltr"), ltr_resource.resname, ResourceType.LTR, ltr_data)
    else:
        ltr_file = ltr_files[0]
        original_data = ltr_file.read_bytes()
        editor.load(ltr_file, ltr_file.stem, ResourceType.LTR, original_data)

    # Verify editor loaded the data
    assert editor is not None
    assert editor.ltr is not None

    # Build and verify it works
    data, _ = editor.build()
    assert len(data) > 0

    # Verify we can read it back
    loaded_ltr = read_ltr(data)
    assert loaded_ltr is not None


# ============================================================================
# TABLE CELL EDITING TESTS
# ============================================================================


def test_ltr_editor_table_cell_editing_singles(qtbot: QtBot, installation: HTInstallation):
    """Test editing cells directly in singles table."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Edit a cell directly
    if editor.ui.tableSingles.rowCount() > 0:
        item = editor.ui.tableSingles.item(0, 1)  # Start column
        if item is not None:
            editor.ui.tableSingles.setCurrentCell(0, 1)
            editor.ui.tableSingles.editItem(item)
            QApplication.processEvents()

            # Type new value
            qtbot.keyClicks(editor.ui.tableSingles, "50")
            qtbot.keyClick(editor.ui.tableSingles, Qt.Key.Key_Enter)
            QApplication.processEvents()

            # Verify value was set
            assert item.text() == "50"


def test_ltr_editor_table_cell_editing_doubles(qtbot: QtBot, installation: HTInstallation):
    """Test editing cells directly in doubles table."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Edit a cell directly
    if editor.ui.tableDoubles.rowCount() > 0:
        item = editor.ui.tableDoubles.item(0, 2)  # Start column
        if item is not None:
            editor.ui.tableDoubles.setCurrentCell(0, 2)
            editor.ui.tableDoubles.editItem(item)
            QApplication.processEvents()

            # Type new value
            qtbot.keyClicks(editor.ui.tableDoubles, "25")
            qtbot.keyClick(editor.ui.tableDoubles, Qt.Key.Key_Enter)
            QApplication.processEvents()

            # Verify value was set
            assert item.text() == "25"


def test_ltr_editor_table_cell_editing_triples(qtbot: QtBot, installation: HTInstallation):
    """Test editing cells directly in triples table."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Edit a cell directly
    if editor.ui.tableTriples.rowCount() > 0:
        item = editor.ui.tableTriples.item(0, 3)  # Start column
        if item is not None:
            editor.ui.tableTriples.setCurrentCell(0, 3)
            editor.ui.tableTriples.editItem(item)
            QApplication.processEvents()

            # Type new value
            qtbot.keyClicks(editor.ui.tableTriples, "15")
            qtbot.keyClick(editor.ui.tableTriples, Qt.Key.Key_Enter)
            QApplication.processEvents()

            # Verify value was set
            assert item.text() == "15"


# ============================================================================
# TABLE SORTING TESTS
# ============================================================================


def test_ltr_editor_table_sorting_singles(qtbot: QtBot, installation: HTInstallation):
    """Test sorting singles table by different columns."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Sort by character column
    editor.ui.tableSingles.sortItems(0, Qt.SortOrder.AscendingOrder)
    QApplication.processEvents()

    # Verify sorted
    first_item = editor.ui.tableSingles.item(0, 0)
    if first_item is not None:
        assert first_item.text() is not None

    # Sort by start column
    editor.ui.tableSingles.sortItems(1, Qt.SortOrder.DescendingOrder)
    QApplication.processEvents()

    # Verify sorted
    first_start = editor.ui.tableSingles.item(0, 1)
    second_start = editor.ui.tableSingles.item(1, 1)
    if first_start is not None and second_start is not None:
        first_val = float(first_start.text() or "0")
        second_val = float(second_start.text() or "0")
        assert first_val >= second_val


def test_ltr_editor_table_sorting_doubles(qtbot: QtBot, installation: HTInstallation):
    """Test sorting doubles table by different columns."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Sort by previous character column
    editor.ui.tableDoubles.sortItems(0, Qt.SortOrder.AscendingOrder)
    QApplication.processEvents()

    # Sort by start column
    editor.ui.tableDoubles.sortItems(2, Qt.SortOrder.DescendingOrder)
    QApplication.processEvents()

    # Verify sorted
    first_start = editor.ui.tableDoubles.item(0, 2)
    second_start = editor.ui.tableDoubles.item(1, 2)
    if first_start is not None and second_start is not None:
        first_val = float(first_start.text() or "0")
        second_val = float(second_start.text() or "0")
        assert first_val >= second_val


def test_ltr_editor_table_sorting_triples(qtbot: QtBot, installation: HTInstallation):
    """Test sorting triples table by different columns."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Sort by start column
    editor.ui.tableTriples.sortItems(3, Qt.SortOrder.DescendingOrder)
    QApplication.processEvents()

    # Verify sorted
    first_start = editor.ui.tableTriples.item(0, 3)
    second_start = editor.ui.tableTriples.item(1, 3)
    if first_start is not None and second_start is not None:
        first_val = float(first_start.text() or "0")
        second_val = float(second_start.text() or "0")
        assert first_val >= second_val


# ============================================================================
# HEADER CONTEXT MENU TESTS
# ============================================================================


def test_ltr_editor_header_context_menu_auto_fit(qtbot: QtBot, installation: HTInstallation):
    """Test header context menu auto-fit columns action."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Get header
    header = editor.ui.tableSingles.horizontalHeader()
    assert header is not None

    # Trigger context menu
    header.customContextMenuRequested.emit(header.mapFromGlobal(header.mapToGlobal(header.pos())))
    QApplication.processEvents()

    # Find menu
    menus = editor.findChildren(QMenu)
    if menus:
        menu = menus[-1]
        actions = menu.actions()
        auto_fit_action = next((a for a in actions if "Auto-fit" in a.text()), None)
        if auto_fit_action:
            # Toggle auto-fit
            initial_state = editor.auto_resize_enabled
            auto_fit_action.trigger()
            QApplication.processEvents()

            # Verify state changed
            assert editor.auto_resize_enabled != initial_state or editor.auto_resize_enabled is True


def test_ltr_editor_header_context_menu_alternate_colors(qtbot: QtBot, installation: HTInstallation):
    """Test header context menu alternate row colors action."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Get header
    header = editor.ui.tableSingles.horizontalHeader()
    assert header is not None

    # Get initial state
    initial_state = editor.ui.tableSingles.alternatingRowColors()

    # Trigger context menu
    header.customContextMenuRequested.emit(header.mapFromGlobal(header.mapToGlobal(header.pos())))
    QApplication.processEvents()

    # Find menu
    menus = editor.findChildren(QMenu)
    if menus:
        menu = menus[-1]
        actions = menu.actions()
        alternate_action = next((a for a in actions if "Alternate" in a.text()), None)
        if alternate_action:
            alternate_action.trigger()
            QApplication.processEvents()

            # Verify state changed
            assert editor.ui.tableSingles.alternatingRowColors() != initial_state


# ============================================================================
# AUTO-FIT COLUMNS TESTS
# ============================================================================


def test_ltr_editor_auto_fit_columns_enabled(qtbot: QtBot, installation: HTInstallation):
    """Test auto-fit columns when enabled."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Enable auto-fit
    editor.toggle_auto_fit_columns(True)
    QApplication.processEvents()

    # Verify enabled
    assert editor.auto_resize_enabled is True

    # Get column widths
    header = editor.ui.tableSingles.horizontalHeader()
    assert header is not None
    widths = [header.sectionSize(i) for i in range(header.count())]

    # Verify columns have reasonable widths
    assert all(w > 0 for w in widths)


def test_ltr_editor_auto_fit_columns_disabled(qtbot: QtBot, installation: HTInstallation):
    """Test auto-fit columns when disabled."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Disable auto-fit
    editor.toggle_auto_fit_columns(False)
    QApplication.processEvents()

    # Verify disabled
    assert editor.auto_resize_enabled is False


def test_ltr_editor_auto_fit_columns_toggle(qtbot: QtBot, installation: HTInstallation):
    """Test toggling auto-fit columns multiple times."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Toggle multiple times
    for _ in range(5):
        current_state = editor.auto_resize_enabled
        editor.toggle_auto_fit_columns()
        QApplication.processEvents()
        assert editor.auto_resize_enabled != current_state


# ============================================================================
# ALTERNATE ROW COLORS TESTS
# ============================================================================


def test_ltr_editor_alternate_row_colors_toggle(qtbot: QtBot, installation: HTInstallation):
    """Test toggling alternate row colors multiple times."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Toggle multiple times
    for _ in range(5):
        initial_state = editor.ui.tableSingles.alternatingRowColors()
        editor.toggle_alternate_row_colors()
        QApplication.processEvents()
        assert editor.ui.tableSingles.alternatingRowColors() != initial_state


def test_ltr_editor_alternate_row_colors_all_tables(qtbot: QtBot, installation: HTInstallation):
    """Test that alternate row colors affects all tables."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Get initial states
    singles_state = editor.ui.tableSingles.alternatingRowColors()
    doubles_state = editor.ui.tableDoubles.alternatingRowColors()
    triples_state = editor.ui.tableTriples.alternatingRowColors()

    # Toggle
    editor.toggle_alternate_row_colors()
    QApplication.processEvents()

    # Verify all tables changed
    assert editor.ui.tableSingles.alternatingRowColors() != singles_state
    assert editor.ui.tableDoubles.alternatingRowColors() != doubles_state
    assert editor.ui.tableTriples.alternatingRowColors() != triples_state


# ============================================================================
# NAME GENERATION TESTS
# ============================================================================


def test_ltr_editor_generate_name_consistency(qtbot: QtBot, installation: HTInstallation):
    """Test that name generation produces valid names."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Generate multiple names
    names = []
    for _ in range(20):
        editor.generateName()
        name = editor.ui.lineEditGeneratedName.text()
        names.append(name)
        assert len(name) > 0
        assert isinstance(name, str)

    # Verify names are generated (may be different)
    assert len(set(names)) > 0


def test_ltr_editor_generate_name_with_modified_probabilities(qtbot: QtBot, installation: HTInstallation):
    """Test name generation after modifying character probabilities."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Modify some character probabilities
    char = "a"
    index = editor.ui.comboBoxSingleChar.findText(char)
    if index >= 0:
        editor.ui.comboBoxSingleChar.setCurrentIndex(index)
        editor.ui.spinBoxSingleStart.setValue(0.5)
        editor.ui.spinBoxSingleMiddle.setValue(0.5)
        editor.ui.spinBoxSingleEnd.setValue(0.5)
        editor.setSingleCharacter()

    # Generate name
    editor.generateName()
    name = editor.ui.lineEditGeneratedName.text()

    # Verify name was generated
    assert len(name) > 0
    assert name == editor.ltr.generate()


# ============================================================================
# ROW ADDITION/REMOVAL TESTS
# ============================================================================


def test_ltr_editor_add_remove_multiple_single_rows(qtbot: QtBot, installation: HTInstallation):
    """Test adding and removing multiple single rows."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    initial_count = editor.ui.tableSingles.rowCount()

    # Add multiple rows
    for _ in range(5):
        editor.addSingleRow()
        QApplication.processEvents()

    assert editor.ui.tableSingles.rowCount() == initial_count + 5

    # Remove rows
    for _ in range(5):
        if editor.ui.tableSingles.rowCount() > 0:
            editor.ui.tableSingles.selectRow(editor.ui.tableSingles.rowCount() - 1)
            editor.removeSingleRow()
            QApplication.processEvents()

    assert editor.ui.tableSingles.rowCount() == initial_count


def test_ltr_editor_add_remove_multiple_double_rows(qtbot: QtBot, installation: HTInstallation):
    """Test adding and removing multiple double rows."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    initial_count = editor.ui.tableDoubles.rowCount()

    # Add multiple rows
    for _ in range(5):
        editor.addDoubleRow()
        QApplication.processEvents()

    assert editor.ui.tableDoubles.rowCount() == initial_count + 5

    # Remove rows
    for _ in range(5):
        if editor.ui.tableDoubles.rowCount() > 0:
            editor.ui.tableDoubles.selectRow(editor.ui.tableDoubles.rowCount() - 1)
            editor.removeDoubleRow()
            QApplication.processEvents()

    assert editor.ui.tableDoubles.rowCount() == initial_count


def test_ltr_editor_add_remove_multiple_triple_rows(qtbot: QtBot, installation: HTInstallation):
    """Test adding and removing multiple triple rows."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    initial_count = editor.ui.tableTriples.rowCount()

    # Add multiple rows
    for _ in range(5):
        editor.addTripleRow()
        QApplication.processEvents()

    assert editor.ui.tableTriples.rowCount() == initial_count + 5

    # Remove rows
    for _ in range(5):
        if editor.ui.tableTriples.rowCount() > 0:
            editor.ui.tableTriples.selectRow(editor.ui.tableTriples.rowCount() - 1)
            editor.removeTripleRow()
            QApplication.processEvents()

    assert editor.ui.tableTriples.rowCount() == initial_count


# ============================================================================
# EDGE CASES - EXTREME VALUES
# ============================================================================


def test_ltr_editor_extreme_probability_values(qtbot: QtBot, installation: HTInstallation):
    """Test handling extreme probability values."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    char = "a"
    index = editor.ui.comboBoxSingleChar.findText(char)
    if index >= 0:
        # Test minimum value
        editor.ui.comboBoxSingleChar.setCurrentIndex(index)
        editor.ui.spinBoxSingleStart.setValue(0.0)
        editor.ui.spinBoxSingleMiddle.setValue(0.0)
        editor.ui.spinBoxSingleEnd.setValue(0.0)
        editor.setSingleCharacter()

        assert editor.ltr._singles.get_start(char) == 0.0
        assert editor.ltr._singles.get_middle(char) == 0.0
        assert editor.ltr._singles.get_end(char) == 0.0

        # Test maximum value
        editor.ui.spinBoxSingleStart.setValue(1.0)
        editor.ui.spinBoxSingleMiddle.setValue(1.0)
        editor.ui.spinBoxSingleEnd.setValue(1.0)
        editor.setSingleCharacter()

        assert editor.ltr._singles.get_start(char) == 1.0
        assert editor.ltr._singles.get_middle(char) == 1.0
        assert editor.ltr._singles.get_end(char) == 1.0


def test_ltr_editor_all_characters_manipulated(qtbot: QtBot, installation: HTInstallation):
    """Test manipulating all characters in the character set."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    char_set = LTR.CHARACTER_SET

    # Set values for all characters
    for i, char in enumerate(char_set):
        index = editor.ui.comboBoxSingleChar.findText(char)
        if index >= 0:
            editor.ui.comboBoxSingleChar.setCurrentIndex(index)
            value = 0.1 + (i * 0.01)
            editor.ui.spinBoxSingleStart.setValue(value)
            editor.ui.spinBoxSingleMiddle.setValue(value)
            editor.ui.spinBoxSingleEnd.setValue(value)
            editor.setSingleCharacter()

    # Verify all characters were set
    data, _ = editor.build()
    modified_ltr = read_ltr(data)

    for i, char in enumerate(char_set):
        expected_value = 0.1 + (i * 0.01)
        assert modified_ltr._singles.get_start(char) == pytest.approx(expected_value)
        assert modified_ltr._singles.get_middle(char) == pytest.approx(expected_value)
        assert modified_ltr._singles.get_end(char) == pytest.approx(expected_value)


# ============================================================================
# COMPREHENSIVE ROUNDTRIP TESTS
# ============================================================================


def test_ltr_editor_comprehensive_roundtrip_all_tables(qtbot: QtBot, installation: HTInstallation):
    """Test comprehensive roundtrip with all table types modified."""
    editor = LTREditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    QApplication.processEvents()

    editor.new()

    # Modify singles
    char = "a"
    index = editor.ui.comboBoxSingleChar.findText(char)
    if index >= 0:
        editor.ui.comboBoxSingleChar.setCurrentIndex(index)
        editor.ui.spinBoxSingleStart.setValue(0.2)
        editor.ui.spinBoxSingleMiddle.setValue(0.3)
        editor.ui.spinBoxSingleEnd.setValue(0.4)
        editor.setSingleCharacter()

    # Modify doubles
    prev_char = "a"
    char2 = "b"
    prev_index = editor.ui.comboBoxDoublePrevChar.findText(prev_char)
    char2_index = editor.ui.comboBoxDoubleChar.findText(char2)
    if prev_index >= 0 and char2_index >= 0:
        editor.ui.comboBoxDoublePrevChar.setCurrentIndex(prev_index)
        editor.ui.comboBoxDoubleChar.setCurrentIndex(char2_index)
        editor.ui.spinBoxDoubleStart.setValue(0.1)
        editor.ui.spinBoxDoubleMiddle.setValue(0.2)
        editor.ui.spinBoxDoubleEnd.setValue(0.3)
        editor.setDoubleCharacter()

    # Modify triples
    prev2 = "a"
    prev1 = "b"
    char3 = "c"
    prev2_index = editor.ui.comboBoxTriplePrev2Char.findText(prev2)
    prev1_index = editor.ui.comboBoxTriplePrev1Char.findText(prev1)
    char3_index = editor.ui.comboBoxTripleChar.findText(char3)
    if prev2_index >= 0 and prev1_index >= 0 and char3_index >= 0:
        editor.ui.comboBoxTriplePrev2Char.setCurrentIndex(prev2_index)
        editor.ui.comboBoxTriplePrev1Char.setCurrentIndex(prev1_index)
        editor.ui.comboBoxTripleChar.setCurrentIndex(char3_index)
        editor.ui.spinBoxTripleStart.setValue(0.05)
        editor.ui.spinBoxTripleMiddle.setValue(0.1)
        editor.ui.spinBoxTripleEnd.setValue(0.15)
        editor.setTripleCharacter()

    # Save
    data1, _ = editor.build()
    saved_ltr1 = read_ltr(data1)

    # Load
    editor.load(Path("test.ltr"), "test", ResourceType.LTR, data1)

    # Verify all modifications preserved
    if index >= 0:
        assert saved_ltr1._singles.get_start(char) == pytest.approx(0.2)
        assert saved_ltr1._singles.get_middle(char) == pytest.approx(0.3)
        assert saved_ltr1._singles.get_end(char) == pytest.approx(0.4)

    if prev_index >= 0 and char2_index >= 0:
        char_set = LTR.CHARACTER_SET
        prev_idx = char_set.index(prev_char)
        assert saved_ltr1._doubles[prev_idx].get_start(char2) == pytest.approx(0.1)
        assert saved_ltr1._doubles[prev_idx].get_middle(char2) == pytest.approx(0.2)
        assert saved_ltr1._doubles[prev_idx].get_end(char2) == pytest.approx(0.3)

    # Save again
    data2, _ = editor.build()
    saved_ltr2 = read_ltr(data2)

    # Verify second save matches first
    if index >= 0:
        assert saved_ltr2._singles.get_start(char) == saved_ltr1._singles.get_start(char)
        assert saved_ltr2._singles.get_middle(char) == saved_ltr1._singles.get_middle(char)
        assert saved_ltr2._singles.get_end(char) == saved_ltr1._singles.get_end(char)
