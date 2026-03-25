"""
Unit Tests for LIP Editor - testing EVERY possible manipulation.

Each test focuses on a specific manipulation and validates save/load roundtrips.
Following the ARE and ERF editor test patterns for comprehensive coverage.
Tests all combinations of operations, edge cases, UI interactions, and roundtrips.
"""

from __future__ import annotations
import pathlib
import tempfile
import wave

import pytest
from pathlib import Path
from qtpy.QtCore import QEventLoop, Qt, QPoint
from qtpy.QtGui import QKeySequence
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QFileDialog, QMessageBox, QMenu, QPushButton
from toolset.gui.editors.lip.lip_editor import LIPEditor  # type: ignore[import-not-found]
from toolset.data.installation import HTInstallation  # type: ignore[import-not-found]
from pykotor.resource.formats.lip import LIP, LIPKeyFrame, LIPShape, read_lip, bytes_lip  # type: ignore[import-not-found]
from pykotor.resource.type import ResourceType  # type: ignore[import-not-found]
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

# Test constants
ALL_LIP_SHAPES = list(LIPShape)
TEST_TIMES = [0.0, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 100.0]
TEST_DURATIONS = [0.0, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0]


# Helper function to assert lip is not None before accessing frames
def assert_lip_not_none(editor: LIPEditor) -> LIP:
    """Helper to assert lip is not None and return it."""
    assert editor.lip is not None, "editor.lip should not be None"
    return editor.lip


# ============================================================================
# BASIC TESTS
# ============================================================================


def test_lip_editor_new_file_creation(qtbot: QtBot, installation: HTInstallation):
    """Test creating a new LIP file from scratch."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Create new
    editor.new()

    # Verify LIP object exists
    assert editor.lip is not None
    assert isinstance(editor.lip, LIP)
    assert len(editor.lip.frames) == 0


def test_lip_editor_initialization(qtbot: QtBot, installation: HTInstallation):
    """Test editor initialization."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Verify all components initialized
    assert editor.lip is None or isinstance(editor.lip, LIP)
    assert editor.duration == 0.0
    assert editor.phoneme_map is not None
    assert len(editor.phoneme_map) > 0
    assert editor.player is not None
    # audio_output is only set in Qt6; in Qt5 it remains None
    import qtpy

    if qtpy.QT6:
        assert editor.audio_output is not None
    else:
        assert editor.audio_output is None  # Qt5 doesn't require explicit audio output
    assert editor.preview_timer is not None


# ============================================================================
# KEYFRAME MANIPULATIONS
# ============================================================================


def test_lip_editor_add_keyframe(qtbot: QtBot, installation: HTInstallation):
    """Test adding a keyframe."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Set duration first
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Set time and shape
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)

    # Add keyframe
    editor.add_keyframe()

    # Verify keyframe was added
    assert editor.lip is not None
    assert len(editor.lip.frames) == 1
    assert abs(editor.lip.frames[0].time - 1.0) < 0.001
    assert editor.lip.frames[0].shape == LIPShape.AH


def test_lip_editor_add_multiple_keyframes(qtbot: QtBot, installation: HTInstallation):
    """Test adding multiple keyframes."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add multiple keyframes
    test_keyframes = [
        (0.0, LIPShape.AH),
        (1.0, LIPShape.EE),
        (2.0, LIPShape.OH),
        (3.0, LIPShape.MPB),
    ]

    for time, shape in test_keyframes:
        editor.time_input.setValue(time)
        editor.shape_select.setCurrentText(shape.name)
        editor.add_keyframe()

    # Verify all keyframes were added
    assert editor.lip is not None
    assert len(editor.lip.frames) == len(test_keyframes)

    # Verify keyframes are sorted by time
    sorted_frames = sorted(editor.lip.frames, key=lambda f: f.time)
    for i, (time, shape) in enumerate(test_keyframes):
        assert abs(sorted_frames[i].time - time) < 0.001
        assert sorted_frames[i].shape == shape


def test_lip_editor_update_keyframe(qtbot: QtBot, installation: HTInstallation):
    """Test updating a keyframe."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Select the keyframe
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.on_keyframe_selected()

    # Update keyframe
    editor.time_input.setValue(1.5)
    editor.shape_select.setCurrentText(LIPShape.EE.name)
    editor.update_keyframe()

    # Verify keyframe was updated
    assert editor.lip is not None
    assert len(editor.lip.frames) == 1
    assert abs(editor.lip.frames[0].time - 1.5) < 0.001
    assert editor.lip.frames[0].shape == LIPShape.EE


def test_lip_editor_delete_keyframe(qtbot: QtBot, installation: HTInstallation):
    """Test deleting a keyframe."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframes
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    editor.time_input.setValue(2.0)
    editor.shape_select.setCurrentText(LIPShape.EE.name)
    editor.add_keyframe()

    # Select and delete first keyframe
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.delete_keyframe()

    # Verify keyframe was deleted
    assert editor.lip is not None
    assert len(editor.lip.frames) == 1
    assert editor.lip.frames[0].shape == LIPShape.EE


# ============================================================================
# SHAPE SELECTION TESTS
# ============================================================================


def test_lip_editor_all_lip_shapes_available(qtbot: QtBot, installation: HTInstallation):
    """Test all LIP shapes are available in combo box."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Verify all LIP shapes are in combo box
    all_shapes = list(LIPShape)
    assert editor.shape_select.count() == len(all_shapes)

    # Verify each shape is present
    for shape in all_shapes:
        index = editor.shape_select.findText(shape.name)
        assert index >= 0


def test_lip_editor_set_different_shapes(qtbot: QtBot, installation: HTInstallation):
    """Test setting different LIP shapes."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Test various shapes
    test_shapes = [
        LIPShape.AH,
        LIPShape.EE,
        LIPShape.OH,
        LIPShape.MPB,
        LIPShape.FV,
        LIPShape.TD,
        LIPShape.KG,
        LIPShape.L,
    ]

    for i, shape in enumerate(test_shapes):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(shape.name)
        editor.add_keyframe()

    # Verify all shapes were set
    assert editor.lip is not None
    assert len(editor.lip.frames) == len(test_shapes)
    for i, shape in enumerate(test_shapes):
        sorted_frames: list[LIPKeyFrame] = sorted(editor.lip.frames, key=lambda f: f.time)
        assert sorted_frames[i].shape == shape


# ============================================================================
# PREVIEW TESTS
# ============================================================================


def test_lip_editor_update_preview(qtbot: QtBot, installation: HTInstallation):
    """Test preview list updates correctly."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframes
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    editor.time_input.setValue(2.0)
    editor.shape_select.setCurrentText(LIPShape.EE.name)
    editor.add_keyframe()

    # Update preview
    editor.update_preview()

    # Verify preview list has items
    assert editor.preview_list.count() == 2

    # Verify items are sorted by time
    item_0 = editor.preview_list.item(0)
    assert item_0 is not None
    assert "1.000" in item_0.text()
    item_1 = editor.preview_list.item(1)
    assert item_1 is not None
    assert "2.000" in item_1.text()


def test_lip_editor_keyframe_selection(qtbot: QtBot, installation: HTInstallation):
    """Test selecting a keyframe updates inputs."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(2.5)
    editor.shape_select.setCurrentText(LIPShape.OH.name)
    editor.add_keyframe()

    # Select keyframe
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.on_keyframe_selected()

    # Verify inputs were updated
    value = editor.time_input.value()
    assert value is not None
    assert abs(value - 2.5) < 0.001
    assert editor.shape_select.currentText() == LIPShape.OH.name


# ============================================================================
# SAVE/LOAD ROUNDTRIP TESTS
# ============================================================================


def test_lip_editor_save_load_roundtrip(qtbot: QtBot, installation: HTInstallation):
    """Test save/load roundtrip preserves data."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframes
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    editor.time_input.setValue(2.0)
    editor.shape_select.setCurrentText(LIPShape.EE.name)
    editor.add_keyframe()

    # Build
    data, _ = editor.build()
    assert len(data) > 0

    # Load it back
    editor.load(Path("test.lip"), "test", ResourceType.LIP, data)

    # Verify data was loaded
    assert editor.lip is not None
    assert len(editor.lip.frames) == 2
    assert abs(editor.lip.length - 10.0) < 0.001
    assert editor.duration == 10.0


def test_lip_editor_multiple_save_load_cycles(qtbot: QtBot, installation: HTInstallation):
    """Test multiple save/load cycles preserve data correctly."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Perform multiple cycles
    for cycle in range(3):
        # Clear and add keyframe
        editor.new()
        editor.duration = 10.0
        editor.duration_label.setText("10.000s")
        editor.time_input.setMaximum(10.0)

        editor.time_input.setValue(float(cycle))
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

        # Save
        data, _ = editor.build()

        # Load back
        editor.load(Path("test.lip"), "test", ResourceType.LIP, data)

        # Verify keyframe was preserved
        assert editor.lip is not None
        assert len(editor.lip.frames) == 1


# ============================================================================
# DURATION TESTS
# ============================================================================


def test_lip_editor_duration_setting(qtbot: QtBot, installation: HTInstallation):
    """Test setting duration."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Set duration
    editor.duration = 5.5
    editor.duration_label.setText("5.500s")
    editor.time_input.setMaximum(5.5)

    # Verify duration was set
    assert editor.duration == 5.5
    assert editor.time_input.maximum() == 5.5


def test_lip_editor_duration_from_loaded_lip(qtbot: QtBot, installation: HTInstallation):
    """Test duration is loaded from LIP file."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()
    editor.duration = 10.0
    editor.lip = LIP()
    editor.lip.length = 10.0
    # Add at least one frame to make the LIP valid
    editor.lip.add(0.0, LIPShape.NEUTRAL)

    # Build and load
    data, _ = editor.build()
    assert len(data) > 0, "LIP data should not be empty"
    editor.load(Path("test.lip"), "test", ResourceType.LIP, data)

    # Verify duration was loaded
    assert abs(editor.duration - 10.0) < 0.001


# ============================================================================
# PHONEME MAPPING TESTS
# ============================================================================


def test_lip_editor_phoneme_map_initialization(qtbot: QtBot, installation: HTInstallation):
    """Test phoneme map is properly initialized."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Verify phoneme map exists and has entries
    assert editor.phoneme_map is not None
    assert len(editor.phoneme_map) > 0

    # Verify some expected phonemes exist
    assert "AA" in editor.phoneme_map
    assert "B" in editor.phoneme_map
    assert "M" in editor.phoneme_map
    assert "P" in editor.phoneme_map

    # Verify phonemes map to valid LIP shapes
    for phoneme, shape in editor.phoneme_map.items():
        assert isinstance(shape, LIPShape)


# ============================================================================
# PLAYBACK TESTS (Limited - requires audio file)
# ============================================================================


def test_lip_editor_playback_methods_exist(qtbot: QtBot, installation: HTInstallation):
    """Test playback methods exist."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Verify playback methods exist
    assert hasattr(editor, "play_preview")
    assert hasattr(editor, "stop_preview")
    assert callable(editor.play_preview)
    assert callable(editor.stop_preview)


def test_lip_editor_stop_preview(qtbot: QtBot, installation: HTInstallation):
    """Test stopping preview."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Stop preview (should work even if not playing)
    editor.stop_preview()

    # Verify preview label was reset
    assert editor.preview_label is not None
    assert editor.preview_label.text() == "None"
    assert editor.current_shape is None


# ============================================================================
# KEYBOARD SHORTCUTS
# ============================================================================


def test_lip_editor_shortcuts_setup(qtbot: QtBot, installation: HTInstallation):
    """Test keyboard shortcuts are set up."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Verify shortcut setup method exists
    assert hasattr(editor, "setup_shortcuts")
    assert callable(editor.setup_shortcuts)


# ============================================================================
# CONTEXT MENU TESTS
# ============================================================================


def test_lip_editor_context_menu(qtbot: QtBot, installation: HTInstallation):
    """Test context menu functionality."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Verify context menu method exists
    assert hasattr(editor, "show_preview_context_menu")
    assert callable(editor.show_preview_context_menu)

    # Verify preview list has context menu enabled
    assert editor.preview_list.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


# ============================================================================
# UNDO/REDO TESTS
# ============================================================================


def test_lip_editor_undo_redo_methods_exist(qtbot: QtBot, installation: HTInstallation):
    """Test undo/redo methods exist (even if not implemented)."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Verify undo/redo methods exist
    assert hasattr(editor, "undo")
    assert hasattr(editor, "redo")
    assert callable(editor.undo)
    assert callable(editor.redo)


# ============================================================================
# UI ELEMENT TESTS
# ============================================================================


def test_lip_editor_ui_elements(qtbot: QtBot, installation: HTInstallation):
    """Test that UI elements exist."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Verify UI elements exist
    assert hasattr(editor, "audio_path")
    assert hasattr(editor, "duration_label")
    assert hasattr(editor, "preview_list")
    assert hasattr(editor, "time_input")
    assert hasattr(editor, "shape_select")
    assert hasattr(editor, "preview_label")


# ============================================================================
# EDGE CASES
# ============================================================================


def test_lip_editor_empty_lip_file(qtbot: QtBot, installation: HTInstallation):
    """Test handling of empty LIP file."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()

    # Build empty file
    data, _ = editor.build()

    # Empty LIPs produce empty data, which cannot be loaded
    # This is expected behavior - empty LIPs are not valid
    assert len(data) == 0, "Empty LIP should produce empty data"

    # Verify that empty data cannot be loaded (expected behavior)
    # Empty LIPs produce empty data, which cannot be loaded
    # This is expected behavior - empty LIPs are not valid
    assert len(data) == 0, "Empty LIP should produce empty data"

    # Verify that empty data cannot be loaded (expected behavior)
    with pytest.raises(ValueError, match="Failed to determine the format"):
        editor.load(Path("test.lip"), "test", ResourceType.LIP, data)
    # After failed load, lip should still be None or empty
    if editor.lip is not None:
        assert len(editor.lip.frames) == 0


def test_lip_editor_keyframes_sorted_by_time(qtbot: QtBot, installation: HTInstallation):
    """Test keyframes are sorted by time when displayed."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframes out of order
    editor.time_input.setValue(3.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.EE.name)
    editor.add_keyframe()

    editor.time_input.setValue(2.0)
    editor.shape_select.setCurrentText(LIPShape.OH.name)
    editor.add_keyframe()

    # Update preview
    editor.update_preview()

    # Verify preview list is sorted
    assert editor.preview_list.count() == 3
    item_0 = editor.preview_list.item(0)
    assert item_0 is not None
    item_1 = editor.preview_list.item(1)
    assert item_1 is not None
    item_2 = editor.preview_list.item(2)
    assert item_2 is not None
    assert "1.000" in item_0.text()
    assert "2.000" in item_1.text()
    assert "3.000" in item_2.text()


# ============================================================================
# COMBINATION TESTS
# ============================================================================


def test_lip_editor_complex_lip_file(qtbot: QtBot, installation: HTInstallation):
    """Test creating a complex LIP file with many keyframes."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add many keyframes
    shapes = [LIPShape.AH, LIPShape.EE, LIPShape.OH, LIPShape.MPB, LIPShape.FV]
    for i in range(10):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(shapes[i % len(shapes)].name)
        editor.add_keyframe()

    # Verify all keyframes were added
    assert editor.lip is not None
    assert len(editor.lip.frames) == 10

    # Build and verify
    data, _ = editor.build()
    assert len(data) > 0

    # Load and verify
    editor.load(Path("test.lip"), "test", ResourceType.LIP, data)
    assert editor.lip is not None
    assert len(editor.lip.frames) == 10
    assert abs(editor.lip.length - 10.0) < 0.001


def test_lip_editor_all_shapes_used(qtbot: QtBot, installation: HTInstallation):
    """Test using all LIP shapes."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    editor.new()
    editor.duration = 100.0
    editor.duration_label.setText("100.000s")
    editor.time_input.setMaximum(100.0)

    # Add keyframe for each shape
    all_shapes = list(LIPShape)
    for i, shape in enumerate(all_shapes):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(shape.name)
        editor.add_keyframe()

    # Verify all shapes were used
    assert editor.lip is not None
    assert len(editor.lip.frames) == len(all_shapes)

    # Verify each shape appears at least once
    used_shapes = {frame.shape for frame in editor.lip.frames}
    assert len(used_shapes) == len(all_shapes)


# ============================================================================
# HEADLESS UI TESTS WITH REAL FILES
# ============================================================================


def test_lipeditor_editor_help_dialog_opens_correct_file(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test that LIPEditor help dialog opens and displays the correct help file (not 'Help File Not Found')."""
    from toolset.gui.dialogs.editor_help import EditorHelpDialog

    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Trigger help dialog with the correct file for LIPEditor
    editor._show_help_dialog("LIP-File-Format.md")
    QApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)  # Wait for dialog to be created

    # Find the help dialog
    dialogs = [child for child in editor.findChildren(EditorHelpDialog)]
    assert len(dialogs) > 0, "Help dialog should be opened"

    dialog = dialogs[0]
    assert dialog is not None
    qtbot.waitExposed(dialog)

    # Get the HTML content
    html = dialog.text_browser.toHtml()

    # Assert that "Help File Not Found" error is NOT shown
    assert "Help File Not Found" not in html, f"Help file 'LIP-File-Format.md' should be found, but error was shown. HTML: {html[:500]}"

    # Assert that some content is present (file was loaded successfully)
    assert len(html) > 100, "Help dialog should contain content"


# ============================================================================
# COMPREHENSIVE KEYFRAME MANIPULATION TESTS
# ============================================================================


def test_lip_editor_add_keyframe_at_zero_time(qtbot: QtBot, installation: HTInstallation):
    """Test adding keyframe at time 0.0."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    editor.time_input.setValue(0.0)
    editor.shape_select.setCurrentText(LIPShape.NEUTRAL.name)
    editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 1
    assert abs(editor.lip.frames[0].time - 0.0) < 0.001
    assert editor.lip.frames[0].shape == LIPShape.NEUTRAL


def test_lip_editor_add_keyframe_at_max_time(qtbot: QtBot, installation: HTInstallation):
    """Test adding keyframe at maximum duration time."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    editor.time_input.setValue(10.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 1
    assert abs(editor.lip.frames[0].time - 10.0) < 0.001


def test_lip_editor_add_keyframe_replace_existing(qtbot: QtBot, installation: HTInstallation):
    """Test adding keyframe at same time replaces existing."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add first keyframe
    editor.time_input.setValue(5.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Add at same time with different shape
    editor.time_input.setValue(5.0)
    editor.shape_select.setCurrentText(LIPShape.EE.name)
    editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 1
    assert editor.lip.frames[0].shape == LIPShape.EE


def test_lip_editor_add_keyframe_precise_times(qtbot: QtBot, installation: HTInstallation):
    """Test adding keyframes with precise decimal times."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    precise_times = [0.001, 0.123, 1.456, 2.789, 5.999]
    for time in precise_times:
        editor.time_input.setValue(time)
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == len(precise_times)
    for i, time in enumerate(sorted(precise_times)):
        assert abs(editor.lip.frames[i].time - time) < 0.001


def test_lip_editor_update_keyframe_time_only(qtbot: QtBot, installation: HTInstallation):
    """Test updating keyframe time without changing shape."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Update time only
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.on_keyframe_selected()

    editor.time_input.setValue(2.0)
    editor.update_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 1
    assert abs(editor.lip.frames[0].time - 2.0) < 0.001
    assert editor.lip.frames[0].shape == LIPShape.AH


def test_lip_editor_update_keyframe_shape_only(qtbot: QtBot, installation: HTInstallation):
    """Test updating keyframe shape without changing time."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Update shape only
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.on_keyframe_selected()

    editor.shape_select.setCurrentText(LIPShape.EE.name)
    editor.update_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 1
    assert abs(editor.lip.frames[0].time - 1.0) < 0.001
    assert editor.lip.frames[0].shape == LIPShape.EE


def test_lip_editor_update_keyframe_both_time_and_shape(qtbot: QtBot, installation: HTInstallation):
    """Test updating both time and shape of keyframe."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Update both
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.on_keyframe_selected()

    editor.time_input.setValue(3.0)
    editor.shape_select.setCurrentText(LIPShape.OH.name)
    editor.update_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 1
    assert abs(editor.lip.frames[0].time - 3.0) < 0.001
    assert editor.lip.frames[0].shape == LIPShape.OH


def test_lip_editor_delete_first_keyframe(qtbot: QtBot, installation: HTInstallation):
    """Test deleting the first keyframe."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add multiple keyframes
    for i, shape in enumerate([LIPShape.AH, LIPShape.EE, LIPShape.OH]):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(shape.name)
        editor.add_keyframe()

    # Delete first
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.delete_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 2
    assert editor.lip.frames[0].shape == LIPShape.EE


def test_lip_editor_delete_middle_keyframe(qtbot: QtBot, installation: HTInstallation):
    """Test deleting a middle keyframe."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add multiple keyframes
    for i, shape in enumerate([LIPShape.AH, LIPShape.EE, LIPShape.OH]):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(shape.name)
        editor.add_keyframe()

    # Delete middle
    editor.update_preview()
    editor.preview_list.setCurrentRow(1)
    editor.delete_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 2
    assert editor.lip.frames[0].shape == LIPShape.AH
    assert editor.lip.frames[1].shape == LIPShape.OH


def test_lip_editor_delete_last_keyframe(qtbot: QtBot, installation: HTInstallation):
    """Test deleting the last keyframe."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add multiple keyframes
    for i, shape in enumerate([LIPShape.AH, LIPShape.EE, LIPShape.OH]):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(shape.name)
        editor.add_keyframe()

    # Delete last
    editor.update_preview()
    editor.preview_list.setCurrentRow(2)
    editor.delete_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 2
    assert editor.lip.frames[-1].shape == LIPShape.EE


def test_lip_editor_delete_all_keyframes(qtbot: QtBot, installation: HTInstallation):
    """Test deleting all keyframes one by one."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add multiple keyframes
    for i in range(5):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

    # Delete all
    while editor.preview_list.count() > 0:
        editor.update_preview()
        editor.preview_list.setCurrentRow(0)
        editor.delete_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 0


# ============================================================================
# COMPREHENSIVE SHAPE TESTS
# ============================================================================


def test_lip_editor_add_keyframe_each_shape(qtbot: QtBot, installation: HTInstallation):
    """Test adding a keyframe with each LIP shape."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 100.0
    editor.duration_label.setText("100.000s")
    editor.time_input.setMaximum(100.0)

    for i, shape in enumerate(ALL_LIP_SHAPES):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(shape.name)
        editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == len(ALL_LIP_SHAPES)

    # Verify all shapes are present
    used_shapes = {frame.shape for frame in editor.lip.frames}
    assert len(used_shapes) == len(ALL_LIP_SHAPES)
    assert used_shapes == set(ALL_LIP_SHAPES)


def test_lip_editor_update_to_each_shape(qtbot: QtBot, installation: HTInstallation):
    """Test updating a keyframe to each possible shape."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add initial keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.NEUTRAL.name)
    editor.add_keyframe()

    # Update to each shape
    for shape in ALL_LIP_SHAPES:
        editor.update_preview()
        editor.preview_list.setCurrentRow(0)
        editor.on_keyframe_selected()

        editor.shape_select.setCurrentText(shape.name)
        editor.update_keyframe()

        assert editor.lip is not None
        assert len(editor.lip.frames) == 1
        assert editor.lip.frames[0].shape == shape


def test_lip_editor_shape_combinations(qtbot: QtBot, installation: HTInstallation):
    """Test various shape combinations in sequence."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 50.0
    editor.duration_label.setText("50.000s")
    editor.time_input.setMaximum(50.0)

    # Common speech pattern shapes
    speech_pattern = [
        LIPShape.NEUTRAL,
        LIPShape.AH,
        LIPShape.MPB,
        LIPShape.AH,
        LIPShape.TD,
        LIPShape.AH,
        LIPShape.L,
        LIPShape.EE,
        LIPShape.SH,
        LIPShape.AH,
        LIPShape.KG,
        LIPShape.NEUTRAL,
    ]

    for i, shape in enumerate(speech_pattern):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(shape.name)
        editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == len(speech_pattern)
    for i, shape in enumerate(speech_pattern):
        assert editor.lip.frames[i].shape == shape


# ============================================================================
# COMPREHENSIVE UNDO/REDO TESTS
# ============================================================================


def test_lip_editor_undo_add_keyframe(qtbot: QtBot, installation: HTInstallation):
    """Test undoing an add keyframe operation."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 1

    # Undo
    editor.undo()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 0


def test_lip_editor_redo_add_keyframe(qtbot: QtBot, installation: HTInstallation):
    """Test redoing an add keyframe operation."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Undo
    editor.undo()
    assert editor.lip is not None
    assert len(editor.lip.frames) == 0

    # Redo
    editor.redo()
    assert editor.lip is not None
    assert len(editor.lip.frames) == 1
    assert abs(editor.lip.frames[0].time - 1.0) < 0.001
    assert editor.lip.frames[0].shape == LIPShape.AH


def test_lip_editor_undo_update_keyframe(qtbot: QtBot, installation: HTInstallation):
    """Test undoing an update keyframe operation."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Update keyframe
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.on_keyframe_selected()
    editor.time_input.setValue(2.0)
    editor.shape_select.setCurrentText(LIPShape.EE.name)
    editor.update_keyframe()

    assert editor.lip is not None
    assert abs(editor.lip.frames[0].time - 2.0) < 0.001
    assert editor.lip.frames[0].shape == LIPShape.EE

    # Undo
    editor.undo()

    assert editor.lip is not None
    assert abs(editor.lip.frames[0].time - 1.0) < 0.001
    assert editor.lip.frames[0].shape == LIPShape.AH


def test_lip_editor_undo_delete_keyframe(qtbot: QtBot, installation: HTInstallation):
    """Test undoing a delete keyframe operation."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Delete keyframe
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.delete_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 0

    # Undo
    editor.undo()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 1
    assert abs(editor.lip.frames[0].time - 1.0) < 0.001
    assert editor.lip.frames[0].shape == LIPShape.AH


def test_lip_editor_multiple_undo_operations(qtbot: QtBot, installation: HTInstallation):
    """Test multiple consecutive undo operations."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add multiple keyframes
    for i in range(5):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 5

    # Undo multiple times
    for i in range(5):
        editor.undo()
        assert editor.lip is not None
        assert len(editor.lip.frames) == 4 - i

    assert editor.lip is not None
    assert len(editor.lip.frames) == 0


def test_lip_editor_multiple_redo_operations(qtbot: QtBot, installation: HTInstallation):
    """Test multiple consecutive redo operations."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add multiple keyframes
    for i in range(5):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

    # Undo all
    for _ in range(5):
        editor.undo()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 0

    # Redo all
    for i in range(5):
        editor.redo()
        assert editor.lip is not None
        assert len(editor.lip.frames) == i + 1

    assert editor.lip is not None
    assert len(editor.lip.frames) == 5


def test_lip_editor_undo_redo_chain(qtbot: QtBot, installation: HTInstallation):
    """Test complex undo/redo chain of operations."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Update it
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.on_keyframe_selected()
    editor.time_input.setValue(2.0)
    editor.update_keyframe()

    # Add another
    editor.time_input.setValue(3.0)
    editor.shape_select.setCurrentText(LIPShape.EE.name)
    editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 2

    # Undo add
    editor.undo()
    assert editor.lip is not None
    assert len(editor.lip.frames) == 1

    # Undo update
    editor.undo()
    assert editor.lip is not None
    assert abs(editor.lip.frames[0].time - 1.0) < 0.001

    # Redo update
    editor.redo()
    assert editor.lip is not None
    assert abs(editor.lip.frames[0].time - 2.0) < 0.001

    # Redo add
    editor.redo()
    assert editor.lip is not None
    assert len(editor.lip.frames) == 2


def test_lip_editor_undo_after_new_command_clears_redo(qtbot: QtBot, installation: HTInstallation):
    """Test that new command after undo clears redo stack."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Undo
    editor.undo()

    # Add new keyframe (should clear redo)
    editor.time_input.setValue(2.0)
    editor.shape_select.setCurrentText(LIPShape.EE.name)
    editor.add_keyframe()

    # Redo should not work (redo stack cleared)
    assert editor.lip is not None
    initial_count = len(editor.lip.frames)
    editor.redo()
    assert editor.lip is not None
    assert len(editor.lip.frames) == initial_count  # Should not change


# ============================================================================
# KEYBOARD SHORTCUT TESTS
# ============================================================================


def test_lip_editor_shortcut_insert_adds_keyframe(qtbot: QtBot, installation: HTInstallation):
    """Test Insert key shortcut adds keyframe."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    editor.setFocus()
    qtbot.waitExposed(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)

    # Press Insert key
    qtbot.keyClick(editor, Qt.Key.Key_Insert)

    assert editor.lip is not None
    assert len(editor.lip.frames) == 1


def test_lip_editor_shortcut_return_updates_keyframe(qtbot: QtBot, installation: HTInstallation):
    """Test Return key shortcut updates keyframe."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    editor.setFocus()
    qtbot.waitExposed(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Select and update
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.on_keyframe_selected()
    editor.time_input.setValue(2.0)

    # Press Return key
    qtbot.keyClick(editor, Qt.Key.Key_Return)

    assert editor.lip is not None
    assert editor.lip.frames is not None
    assert len(editor.lip.frames) == 1
    assert abs(editor.lip.frames[0].time - 2.0) < 0.001


def test_lip_editor_shortcut_delete_removes_keyframe(qtbot: QtBot, installation: HTInstallation):
    """Test Delete key shortcut removes keyframe."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    editor.setFocus()
    qtbot.waitExposed(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Select and delete
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)

    # Press Delete key
    qtbot.keyClick(editor, Qt.Key.Key_Delete)

    assert editor.lip is not None
    assert len(editor.lip.frames) == 0


def test_lip_editor_shortcut_ctrl_z_undo(qtbot: QtBot, installation: HTInstallation):
    """Test Ctrl+Z shortcut for undo."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    editor.setFocus()
    qtbot.waitExposed(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Press Ctrl+Z
    qtbot.keyClick(editor, Qt.Key.Key_Z, modifier=Qt.KeyboardModifier.ControlModifier)

    assert editor.lip is not None
    assert len(editor.lip.frames) == 0


def test_lip_editor_shortcut_ctrl_y_redo(qtbot: QtBot, installation: HTInstallation):
    """Test Ctrl+Y shortcut for redo."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.show()
    editor.setFocus()
    qtbot.waitExposed(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Undo
    editor.undo()

    # Press Ctrl+Y
    qtbot.keyClick(editor, Qt.Key.Key_Y, modifier=Qt.KeyboardModifier.ControlModifier)

    assert editor.lip is not None
    assert editor.lip.frames is not None
    assert len(editor.lip.frames) == 1
    assert editor.lip.frames[0].time == 1.0
    assert editor.lip.frames[0].shape == LIPShape.AH


# ============================================================================
# AUDIO LOADING TESTS
# ============================================================================


def test_lip_editor_load_audio_file(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test loading an audio file."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a test WAV file
    wav_file = tmp_path / "test.wav"
    with wave.open(str(wav_file), "wb") as wav:
        wav.setnchannels(1)  # Mono
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(44100)  # 44.1kHz
        # Write 1 second of silence
        wav.writeframes(b"\x00" * 44100 * 2)

    # Mock file dialog
    from unittest.mock import patch

    with patch("toolset.gui.editors.lip.lip_editor.QFileDialog.getOpenFileName", return_value=(str(wav_file), "")):
        editor.load_audio()

    assert editor.audio_path.text() == str(wav_file)
    assert abs(editor.duration - 1.0) < 0.1  # Approximately 1 second


def test_lip_editor_load_audio_sets_duration(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test that loading audio sets duration correctly."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Create a 5 second WAV file
    wav_file = tmp_path / "test5s.wav"
    with wave.open(str(wav_file), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        # Write 5 seconds
        wav.writeframes(b"\x00" * 44100 * 2 * 5)

    from unittest.mock import patch

    with patch("toolset.gui.editors.lip.lip_editor.QFileDialog.getOpenFileName", return_value=(str(wav_file), "")):
        editor.load_audio()

    assert abs(editor.duration - 5.0) < 0.1
    assert editor.time_input.maximum() == 5.0


def test_lip_editor_load_audio_clears_undo_history(qtbot: QtBot, installation: HTInstallation, tmp_path: Path):
    """Test that loading audio clears undo history."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    assert editor.undo_redo_manager.can_undo()

    # Create and load audio
    wav_file = tmp_path / "test.wav"
    with wave.open(str(wav_file), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(b"\x00" * 44100 * 2)

    from unittest.mock import patch

    with patch("toolset.gui.editors.lip.lip_editor.QFileDialog.getOpenFileName", return_value=(str(wav_file), "")):
        editor.load_audio()

    # Undo should not be available (history cleared)
    assert not editor.undo_redo_manager.can_undo()


# ============================================================================
# COMPREHENSIVE SAVE/LOAD ROUNDTRIP TESTS
# ============================================================================


def test_lip_editor_save_load_roundtrip_all_shapes(qtbot: QtBot, installation: HTInstallation):
    """Test save/load roundtrip with all shapes."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 100.0
    editor.duration_label.setText("100.000s")
    editor.time_input.setMaximum(100.0)

    # Add keyframe for each shape
    for i, shape in enumerate(ALL_LIP_SHAPES):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(shape.name)
        editor.add_keyframe()

    # Save
    data, _ = editor.build()
    assert len(data) > 0

    # Load
    editor.load(Path("test.lip"), "test", ResourceType.LIP, data)

    # Verify all shapes preserved
    assert editor.lip is not None
    assert len(editor.lip.frames) == len(ALL_LIP_SHAPES)
    for i, shape in enumerate(ALL_LIP_SHAPES):
        assert editor.lip.frames[i].shape == shape


def test_lip_editor_save_load_roundtrip_precise_times(qtbot: QtBot, installation: HTInstallation):
    """Test save/load roundtrip preserves precise time values."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    precise_times = [0.001, 0.123, 1.456, 2.789, 5.999]
    for time in precise_times:
        editor.time_input.setValue(time)
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

    # Save and load
    data, _ = editor.build()
    editor.load(Path("test.lip"), "test", ResourceType.LIP, data)

    # Verify times preserved
    assert editor.lip is not None
    assert len(editor.lip.frames) == len(precise_times)
    for i, time in enumerate(sorted(precise_times)):
        assert abs(editor.lip.frames[i].time - time) < 0.001


def test_lip_editor_multiple_roundtrips_with_modifications(qtbot: QtBot, installation: HTInstallation):
    """Test multiple roundtrips with modifications between each."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    for cycle in range(5):
        # Add keyframe
        editor.time_input.setValue(float(cycle))
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

        # Save
        data, _ = editor.build()

        # Load
        editor.load(Path("test.lip"), "test", ResourceType.LIP, data)

        # Verify
        assert editor.lip is not None
        assert len(editor.lip.frames) == cycle + 1


def test_lip_editor_roundtrip_preserves_duration(qtbot: QtBot, installation: HTInstallation):
    """Test that duration is preserved through roundtrip."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 15.5
    editor.lip = LIP()
    editor.lip.length = 15.5
    editor.lip.add(0.0, LIPShape.NEUTRAL)

    # Save and load
    data, _ = editor.build()
    editor.load(Path("test.lip"), "test", ResourceType.LIP, data)

    assert abs(editor.duration - 15.5) < 0.001
    assert abs(editor.lip.length - 15.5) < 0.001


# ============================================================================
# COMPLEX COMBINATION TESTS
# ============================================================================


def test_lip_editor_complex_workflow_add_update_delete(qtbot: QtBot, installation: HTInstallation):
    """Test complex workflow: add, update, delete operations."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 20.0
    editor.duration_label.setText("20.000s")
    editor.time_input.setMaximum(20.0)

    # Add multiple keyframes
    for i in range(5):
        editor.time_input.setValue(float(i * 2))
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

    assert editor.lip is not None
    assert editor.lip.frames is not None
    assert len(editor.lip.frames) == 5

    # Update middle one
    editor.update_preview()
    editor.preview_list.setCurrentRow(2)
    editor.on_keyframe_selected()
    editor.time_input.setValue(5.0)
    editor.shape_select.setCurrentText(LIPShape.EE.name)
    editor.update_keyframe()

    assert editor.lip is not None
    assert editor.lip.frames is not None
    assert len(editor.lip.frames) == 5
    assert editor.lip.frames[2].shape == LIPShape.EE

    # Delete first and last
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.delete_keyframe()

    editor.update_preview()
    editor.preview_list.setCurrentRow(3)  # Last is now at index 3
    editor.delete_keyframe()

    assert editor.lip is not None
    assert editor.lip.frames is not None
    assert len(editor.lip.frames) == 3


def test_lip_editor_complex_workflow_undo_redo_chain(qtbot: QtBot, installation: HTInstallation):
    """Test complex undo/redo chain with multiple operations."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add 3 keyframes
    for i in range(3):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

    # Update second
    editor.update_preview()
    editor.preview_list.setCurrentRow(1)
    editor.on_keyframe_selected()
    editor.time_input.setValue(1.5)
    editor.update_keyframe()

    # Delete first
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.delete_keyframe()

    assert editor.lip is not None
    assert editor.lip.frames is not None
    assert len(editor.lip.frames) == 2

    # Undo delete
    editor.undo()
    assert len(editor.lip.frames) == 3

    # Undo update
    editor.undo()
    assert abs(editor.lip.frames[1].time - 1.0) < 0.001

    # Undo all adds
    for _ in range(3):
        editor.undo()

    assert len(editor.lip.frames) == 0

    # Redo all
    for _ in range(3):
        editor.redo()

    assert len(editor.lip.frames) == 3


def test_lip_editor_complex_workflow_all_operations(qtbot: QtBot, installation: HTInstallation):
    """Test all operations in a complex sequence."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 30.0
    editor.duration_label.setText("30.000s")
    editor.time_input.setMaximum(30.0)

    # Add keyframes with all shapes
    for i, shape in enumerate(ALL_LIP_SHAPES[:10]):  # First 10 shapes
        editor.time_input.setValue(float(i * 2))
        editor.shape_select.setCurrentText(shape.name)
        editor.add_keyframe()

    # Update some
    for i in [1, 3, 5]:
        editor.update_preview()
        editor.preview_list.setCurrentRow(i)
        editor.on_keyframe_selected()
        editor.time_input.setValue(editor.time_input.value() + 0.5)
        editor.update_keyframe()

    # Delete some
    for i in [2, 4]:
        editor.update_preview()
        editor.preview_list.setCurrentRow(i)
        editor.delete_keyframe()

    # Save and load
    data, _ = editor.build()
    editor.load(Path("test.lip"), "test", ResourceType.LIP, data)

    assert editor.lip is not None
    assert len(editor.lip.frames) == 8  # 10 - 2 deleted


# ============================================================================
# EDGE CASES AND BOUNDARY TESTS
# ============================================================================


def test_lip_editor_keyframe_at_exact_duration(qtbot: QtBot, installation: HTInstallation):
    """Test adding keyframe at exact duration time."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    editor.time_input.setValue(10.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 1
    assert abs(editor.lip.frames[0].time - 10.0) < 0.001


def test_lip_editor_keyframe_very_small_time(qtbot: QtBot, installation: HTInstallation):
    """Test adding keyframe with very small time value."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    editor.time_input.setValue(0.001)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 1
    assert abs(editor.lip.frames[0].time - 0.001) < 0.001


def test_lip_editor_keyframes_very_close_together(qtbot: QtBot, installation: HTInstallation):
    """Test adding keyframes very close together in time."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframes 0.01 seconds apart
    for i in range(10):
        editor.time_input.setValue(1.0 + i * 0.01)
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 10

    # Verify they're sorted
    for i in range(9):
        assert editor.lip.frames[i].time < editor.lip.frames[i + 1].time


def test_lip_editor_update_keyframe_to_same_time(qtbot: QtBot, installation: HTInstallation):
    """Test updating keyframe to same time (should work)."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Update to same time, different shape
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.on_keyframe_selected()
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.EE.name)
    editor.update_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 1
    assert abs(editor.lip.frames[0].time - 1.0) < 0.001
    assert editor.lip.frames[0].shape == LIPShape.EE


def test_lip_editor_delete_only_keyframe(qtbot: QtBot, installation: HTInstallation):
    """Test deleting the only keyframe."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add single keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Delete it
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.delete_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 0


def test_lip_editor_update_with_no_selection(qtbot: QtBot, installation: HTInstallation):
    """Test update keyframe with no selection (should show error)."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Try to update without selection
    from unittest.mock import patch

    with patch("toolset.gui.editors.lip.lip_editor.QMessageBox.warning") as mock_warning:
        editor.update_keyframe()
        mock_warning.assert_called_once()


def test_lip_editor_delete_with_no_selection(qtbot: QtBot, installation: HTInstallation):
    """Test delete keyframe with no selection (should show error)."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()

    # Try to delete without selection
    from unittest.mock import patch

    with patch("toolset.gui.editors.lip.lip_editor.QMessageBox.warning") as mock_warning:
        editor.delete_keyframe()
        mock_warning.assert_called_once()


# ============================================================================
# PREVIEW FUNCTIONALITY TESTS
# ============================================================================


def test_lip_editor_preview_list_updates_after_add(qtbot: QtBot, installation: HTInstallation):
    """Test that preview list updates after adding keyframe."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    assert editor.preview_list.count() == 0

    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    assert editor.preview_list.count() == 1


def test_lip_editor_preview_list_updates_after_delete(qtbot: QtBot, installation: HTInstallation):
    """Test that preview list updates after deleting keyframe."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframes
    for i in range(3):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

    assert editor.preview_list.count() == 3

    # Delete one
    editor.update_preview()
    editor.preview_list.setCurrentRow(1)
    editor.delete_keyframe()

    assert editor.preview_list.count() == 2


def test_lip_editor_preview_list_shows_correct_format(qtbot: QtBot, installation: HTInstallation):
    """Test that preview list shows correct format."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    editor.time_input.setValue(1.234)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    editor.update_preview()
    item = editor.preview_list.item(0)
    assert item is not None
    assert "1.234" in item.text()
    assert LIPShape.AH.name in item.text()


# ============================================================================
# DURATION EDGE CASES
# ============================================================================


def test_lip_editor_duration_zero(qtbot: QtBot, installation: HTInstallation):
    """Test handling zero duration."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 0.0
    editor.duration_label.setText("0.000s")
    editor.time_input.setMaximum(0.0)

    assert editor.duration == 0.0
    assert editor.time_input.maximum() == 0.0


def test_lip_editor_duration_very_large(qtbot: QtBot, installation: HTInstallation):
    """Test handling very large duration."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 999.999
    editor.duration_label.setText("999.999s")
    editor.time_input.setMaximum(999.999)

    assert editor.duration == 999.999
    assert editor.time_input.maximum() == 999.999


def test_lip_editor_time_input_respects_duration(qtbot: QtBot, installation: HTInstallation):
    """Test that time input maximum respects duration."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()

    for duration in [5.0, 10.0, 25.0, 50.0]:
        editor.duration = duration
        editor.duration_label.setText(f"{duration:.3f}s")
        editor.time_input.setMaximum(duration)

        assert editor.time_input.maximum() == duration


# ============================================================================
# HELP DIALOG TESTS
# ============================================================================


def test_lip_editor_help_dialog_opens_correct_file(qtbot: QtBot, installation: HTInstallation):
    """Test that LIPEditor help dialog opens and displays the correct help file."""
    from toolset.gui.dialogs.editor_help import EditorHelpDialog

    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Trigger help dialog
    editor._show_help_dialog("LIP-File-Format.md")
    QApplication.processEvents()

    # Find the help dialog
    dialogs = [child for child in editor.findChildren(EditorHelpDialog)]
    assert len(dialogs) > 0, "Help dialog should be opened"

    dialog = dialogs[0]
    qtbot.waitExposed(dialog)

    # Get the HTML content
    html = dialog.text_browser.toHtml()

    # Assert that "Help File Not Found" error is NOT shown
    assert "Help File Not Found" not in html, f"Help file 'LIP-File-Format.md' should be found, but error was shown. HTML: {html[:500]}"

    # Assert that some content is present
    assert len(html) > 100, "Help dialog should contain content"


# ============================================================================
# COMPREHENSIVE ROUNDTRIP VALIDATION
# ============================================================================


def test_lip_editor_comprehensive_roundtrip_validation(qtbot: QtBot, installation: HTInstallation):
    """Comprehensive test that validates ALL data is preserved through roundtrip."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 50.0
    editor.lip = LIP()
    editor.lip.length = 50.0
    editor.duration_label.setText("50.000s")
    editor.time_input.setMaximum(50.0)

    # Create comprehensive LIP with all shapes and various times
    test_keyframes = []
    for i, shape in enumerate(ALL_LIP_SHAPES):
        time = float(i * 2)
        editor.lip.add(time, shape)
        test_keyframes.append((time, shape))

    # Save
    data, _ = editor.build()
    assert len(data) > 0

    # Load
    editor.load(Path("test.lip"), "test", ResourceType.LIP, data)

    # Verify everything preserved
    assert editor.lip is not None
    assert abs(editor.lip.length - 50.0) < 0.001
    assert abs(editor.duration - 50.0) < 0.001
    assert len(editor.lip.frames) == len(test_keyframes)

    for i, (time, shape) in enumerate(test_keyframes):
        assert abs(editor.lip.frames[i].time - time) < 0.001
        assert editor.lip.frames[i].shape == shape


def test_lip_editor_roundtrip_with_real_file(qtbot: QtBot, installation: HTInstallation, test_files_dir: pathlib.Path):
    """Test roundtrip with a real LIP file from installation or test files."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Try to find a LIP file
    lip_files = list(test_files_dir.glob("*.lip")) + list(test_files_dir.rglob("*.lip"))
    if not lip_files:
        # Try to get one from installation
        from pykotor.extract.file import ResourceIdentifier

        lip_resources = list(installation.resources([ResourceIdentifier(restype=ResourceType.LIP)]).values())[:1]
        if not lip_resources:
            pytest.skip("No LIP files available for testing")
        lip_resource = lip_resources[0]
        assert lip_resource is not None
        assert lip_resource.resname is not None
        assert lip_resource.restype is not None
        lip_data = installation.resource(lip_resource.resname, lip_resource.restype)
        if not lip_data:
            pytest.skip(f"Could not load LIP data for {lip_resource.resname}")
        editor.load(
            lip_resource.filepath if hasattr(lip_resource, "filepath") else Path("module.lip"),
            lip_resource.resname,
            ResourceType.LIP,
            lip_data.data if isinstance(lip_data.data, bytes) else lip_data.data.tobytes,
        )
    else:
        lip_file = lip_files[0]
        original_data = lip_file.read_bytes()
        editor.load(lip_file, lip_file.stem, ResourceType.LIP, original_data)

    # Verify editor loaded the data
    assert editor is not None
    assert editor.lip is not None

    # Build and verify it works
    data, _ = editor.build()
    assert len(data) > 0

    # Verify we can read it back
    loaded_lip = read_lip(data)
    assert loaded_lip is not None

    # Verify key properties match
    assert editor.lip is not None
    assert abs(loaded_lip.length - editor.lip.length) < 0.001
    assert len(loaded_lip.frames) == len(editor.lip.frames)


# ============================================================================
# REPEATED OPERATION TESTS (Medium to long combinations)
# ============================================================================


def test_lip_editor_repeated_add_delete_cycle(qtbot: QtBot, installation: HTInstallation):
    """Test repeated add/delete cycles."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 20.0
    editor.duration_label.setText("20.000s")
    editor.time_input.setMaximum(20.0)

    # Add and delete keyframes repeatedly
    for cycle in range(10):
        # Add keyframe
        editor.time_input.setValue(float(cycle))
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

        assert editor.lip is not None
        assert len(editor.lip.frames) == cycle + 1

        # Delete it
        editor.update_preview()
        editor.preview_list.setCurrentRow(0)
        editor.delete_keyframe()

        assert editor.lip is not None
        assert len(editor.lip.frames) == cycle


def test_lip_editor_repeated_update_operations(qtbot: QtBot, installation: HTInstallation):
    """Test repeated update operations on same keyframe."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add initial keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Update it multiple times with different values
    shapes_to_test = [LIPShape.EE, LIPShape.OH, LIPShape.MPB, LIPShape.FV, LIPShape.TD]
    for shape in shapes_to_test:
        editor.update_preview()
        editor.preview_list.setCurrentRow(0)
        editor.on_keyframe_selected()
        editor.shape_select.setCurrentText(shape.name)
        editor.update_keyframe()

        assert editor.lip is not None
        assert len(editor.lip.frames) == 1
        assert editor.lip.frames[0].shape == shape


def test_lip_editor_repeated_time_changes(qtbot: QtBot, installation: HTInstallation):
    """Test repeatedly changing keyframe times."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Update time multiple times
    times_to_test = [2.0, 3.0, 4.0, 5.0, 6.0]
    for time in times_to_test:
        editor.update_preview()
        editor.preview_list.setCurrentRow(0)
        editor.on_keyframe_selected()
        editor.time_input.setValue(time)
        editor.update_keyframe()

        assert editor.lip is not None
        assert len(editor.lip.frames) == 1
        assert abs(editor.lip.frames[0].time - time) < 0.001


def test_lip_editor_add_delete_all_shapes_sequence(qtbot: QtBot, installation: HTInstallation):
    """Test adding and deleting all shapes in sequence."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 100.0
    editor.duration_label.setText("100.000s")
    editor.time_input.setMaximum(100.0)

    # Add all shapes
    for i, shape in enumerate(ALL_LIP_SHAPES):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(shape.name)
        editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == len(ALL_LIP_SHAPES)

    # Delete all shapes (in reverse order to test deletion)
    while editor.preview_list.count() > 0:
        editor.update_preview()
        editor.preview_list.setCurrentRow(editor.preview_list.count() - 1)
        editor.delete_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 0


def test_lip_editor_complex_undo_redo_sequence(qtbot: QtBot, installation: HTInstallation):
    """Test complex sequence of operations with undo/redo."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 20.0
    editor.duration_label.setText("20.000s")
    editor.time_input.setMaximum(20.0)

    # Add 5 keyframes
    for i in range(5):
        editor.time_input.setValue(float(i * 2))
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 5

    # Update middle one
    editor.update_preview()
    editor.preview_list.setCurrentRow(2)
    editor.on_keyframe_selected()
    editor.time_input.setValue(5.0)
    editor.shape_select.setCurrentText(LIPShape.EE.name)
    editor.update_keyframe()

    # Delete first
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.delete_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 4

    # Undo delete
    editor.undo()
    assert editor.lip is not None
    assert len(editor.lip.frames) == 5

    # Undo update
    editor.undo()
    assert editor.lip is not None
    assert editor.lip.frames[2].shape == LIPShape.AH

    # Redo update
    editor.redo()
    assert editor.lip is not None
    assert editor.lip.frames[2].shape == LIPShape.EE

    # Redo delete
    editor.redo()
    assert editor.lip is not None
    assert len(editor.lip.frames) == 4


def test_lip_editor_multiple_roundtrips_complex_data(qtbot: QtBot, installation: HTInstallation):
    """Test multiple roundtrips with complex data."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 50.0
    editor.lip = LIP()
    editor.lip.length = 50.0
    editor.duration_label.setText("50.000s")
    editor.time_input.setMaximum(50.0)

    # Create complex LIP with all shapes at various times
    test_data = []
    for i, shape in enumerate(ALL_LIP_SHAPES):
        time = float(i * 3)
        editor.lip.add(time, shape)
        test_data.append((time, shape))

    # Perform 5 roundtrips
    for roundtrip in range(5):
        # Save
        data, _ = editor.build()
        assert len(data) > 0

        # Load
        editor.load(Path(f"test_roundtrip_{roundtrip}.lip"), f"test_{roundtrip}", ResourceType.LIP, data)

        # Verify
        assert editor.lip is not None
        assert len(editor.lip.frames) == len(test_data)
        for i, (time, shape) in enumerate(test_data):
            assert abs(editor.lip.frames[i].time - time) < 0.001
            assert editor.lip.frames[i].shape == shape


# ============================================================================
# TIME MANIPULATION TESTS
# ============================================================================


def test_lip_editor_time_input_range_validation(qtbot: QtBot, installation: HTInstallation):
    """Test that time input respects duration range."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()

    # Test various durations
    for duration in [5.0, 10.0, 25.0, 50.0, 100.0]:
        editor.duration = duration
        editor.duration_label.setText(f"{duration:.3f}s")
        editor.time_input.setMaximum(duration)

        assert editor.time_input.maximum() == duration
        assert editor.time_input.minimum() == 0.0


def test_lip_editor_time_input_precision(qtbot: QtBot, installation: HTInstallation):
    """Test time input precision (3 decimal places)."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Test precise values
    precise_values = [0.001, 0.123, 1.456, 2.789, 5.999]
    for value in precise_values:
        editor.time_input.setValue(value)
        assert abs(editor.time_input.value() - value) < 0.0001


# ============================================================================
# SHAPE SELECTION UNIT TESTS
# ============================================================================


def test_lip_editor_shape_select_all_items(qtbot: QtBot, installation: HTInstallation):
    """Test that shape select has all LIP shapes."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    assert editor.shape_select.count() == len(ALL_LIP_SHAPES)

    # Verify each shape is present and accessible
    for shape in ALL_LIP_SHAPES:
        index = editor.shape_select.findText(shape.name)
        assert index >= 0
        assert editor.shape_select.itemText(index) == shape.name


def test_lip_editor_shape_select_set_each_shape(qtbot: QtBot, installation: HTInstallation):
    """Test setting shape select to each possible shape."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    for shape in ALL_LIP_SHAPES:
        editor.shape_select.setCurrentText(shape.name)
        assert editor.shape_select.currentText() == shape.name


# ============================================================================
# PREVIEW LIST UNIT TESTS
# ============================================================================


def test_lip_editor_preview_list_initial_state(qtbot: QtBot, installation: HTInstallation):
    """Test preview list initial state."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()

    assert editor.preview_list.count() == 0
    assert editor.preview_list.currentRow() == -1


def test_lip_editor_preview_list_selection_clears_inputs(qtbot: QtBot, installation: HTInstallation):
    """Test that clearing selection doesn't crash."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Select it
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.on_keyframe_selected()

    # Clear selection
    editor.preview_list.setCurrentRow(-1)
    editor.on_keyframe_selected()

    # Should not crash


def test_lip_editor_preview_list_multiple_selections(qtbot: QtBot, installation: HTInstallation):
    """Test preview list with multiple keyframes."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 20.0
    editor.duration_label.setText("20.000s")
    editor.time_input.setMaximum(20.0)

    # Add multiple keyframes
    for i in range(10):
        editor.time_input.setValue(float(i))
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

    editor.update_preview()
    assert editor.preview_list.count() == 10

    # Select different items
    for i in range(10):
        editor.preview_list.setCurrentRow(i)
        editor.on_keyframe_selected()
        assert abs(editor.time_input.value() - float(i)) < 0.001


# ============================================================================
# DURATION UNIT TESTS
# ============================================================================


def test_lip_editor_duration_various_values(qtbot: QtBot, installation: HTInstallation):
    """Test setting duration to various values."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()

    for duration in TEST_DURATIONS:
        editor.duration = duration
        editor.duration_label.setText(f"{duration:.3f}s")
        editor.time_input.setMaximum(duration)

        assert editor.duration == duration
        assert editor.time_input.maximum() == duration


def test_lip_editor_duration_label_format(qtbot: QtBot, installation: HTInstallation):
    """Test duration label format."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()

    test_durations = [0.0, 0.1, 1.0, 1.234, 10.0, 10.123, 100.0]
    for duration in test_durations:
        editor.duration = duration
        editor.duration_label.setText(f"{duration:.3f}s")

        expected_text = f"{duration:.3f}s"
        assert editor.duration_label.text() == expected_text


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


def test_lip_editor_add_keyframe_without_duration(qtbot: QtBot, installation: HTInstallation):
    """Test adding keyframe when duration is 0 (should still work)."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 0.0
    editor.duration_label.setText("0.000s")
    editor.time_input.setMaximum(0.0)

    # Should still be able to add keyframe at time 0
    editor.time_input.setValue(0.0)
    editor.shape_select.setCurrentText(LIPShape.NEUTRAL.name)
    editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 1


def test_lip_editor_update_keyframe_without_lip(qtbot: QtBot, installation: HTInstallation):
    """Test update keyframe without LIP loaded (should show error)."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()

    # Try to update without LIP
    from unittest.mock import patch

    with patch("toolset.gui.editors.lip.lip_editor.QMessageBox.warning") as mock_warning:
        editor.update_keyframe()
        mock_warning.assert_called_once()


def test_lip_editor_delete_keyframe_without_lip(qtbot: QtBot, installation: HTInstallation):
    """Test delete keyframe without LIP loaded (should show error)."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()

    # Try to delete without LIP
    from unittest.mock import patch

    with patch("toolset.gui.editors.lip.lip_editor.QMessageBox.warning") as mock_warning:
        editor.delete_keyframe()
        mock_warning.assert_called_once()


# ============================================================================
# UI STATE TESTS
# ============================================================================


def test_lip_editor_ui_state_after_new(qtbot: QtBot, installation: HTInstallation):
    """Test UI state after creating new file."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()

    assert editor.lip is not None
    assert editor.duration == 0.0
    assert editor.preview_list.count() == 0
    assert editor.time_input.value() == 0.0
    assert editor.shape_select.currentIndex() >= 0


def test_lip_editor_ui_state_after_load(qtbot: QtBot, installation: HTInstallation):
    """Test UI state after loading LIP file."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.lip = LIP()
    editor.lip.length = 10.0
    editor.lip.add(1.0, LIPShape.AH)
    editor.lip.add(2.0, LIPShape.EE)

    # Build and load
    data, _ = editor.build()
    editor.load(Path("test.lip"), "test", ResourceType.LIP, data)

    assert editor.lip is not None
    assert abs(editor.duration - 10.0) < 0.001
    assert editor.preview_list.count() == 2


# ============================================================================
# KEYFRAME INTERPOLATION TESTS
# ============================================================================


def test_lip_editor_keyframe_interpolation_between_frames(qtbot: QtBot, installation: HTInstallation):
    """Test that keyframes can be added between existing frames."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframes at 1.0 and 3.0
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    editor.time_input.setValue(3.0)
    editor.shape_select.setCurrentText(LIPShape.EE.name)
    editor.add_keyframe()

    # Add keyframe between them
    editor.time_input.setValue(2.0)
    editor.shape_select.setCurrentText(LIPShape.OH.name)
    editor.add_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 3

    # Verify order
    assert abs(editor.lip.frames[0].time - 1.0) < 0.001
    assert abs(editor.lip.frames[1].time - 2.0) < 0.001
    assert abs(editor.lip.frames[2].time - 3.0) < 0.001


# ============================================================================
# SAVE/LOAD FORMAT TESTS
# ============================================================================


def test_lip_editor_save_binary_format(qtbot: QtBot, installation: HTInstallation):
    """Test that saved LIP is in binary format."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.lip = LIP()
    editor.lip.length = 10.0
    editor.lip.add(1.0, LIPShape.AH)

    data, _ = editor.build()

    # Verify it starts with "LIP V1.0"
    assert data.startswith(b"LIP V1.0")


def test_lip_editor_load_binary_format(qtbot: QtBot, installation: HTInstallation):
    """Test loading binary LIP format."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Create LIP data manually
    lip = LIP()
    lip.length = 10.0
    lip.add(1.0, LIPShape.AH)
    lip.add(2.0, LIPShape.EE)

    data = bytes_lip(lip)

    # Load it
    editor.load(Path("test.lip"), "test", ResourceType.LIP, data)

    assert editor.lip is not None
    assert len(editor.lip.frames) == 2
    assert abs(editor.lip.length - 10.0) < 0.001


# ============================================================================
# PHONEME MAPPING UNIT TESTS
# ============================================================================


def test_lip_editor_phoneme_map_completeness(qtbot: QtBot, installation: HTInstallation):
    """Test that phoneme map has all expected phonemes."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Expected phonemes (common ones)
    expected_phonemes = [
        "AA",
        "AE",
        "AH",
        "AO",
        "AW",
        "AY",
        "B",
        "CH",
        "D",
        "DH",
        "EH",
        "ER",
        "EY",
        "F",
        "G",
        "HH",
        "IH",
        "IY",
        "JH",
        "K",
        "L",
        "M",
        "N",
        "NG",
        "OW",
        "OY",
        "P",
        "R",
        "S",
        "SH",
        "T",
        "TH",
        "UH",
        "UW",
        "V",
        "W",
        "Y",
        "Z",
        "ZH",
    ]

    for phoneme in expected_phonemes:
        assert phoneme in editor.phoneme_map, f"Phoneme {phoneme} should be in phoneme_map"


def test_lip_editor_phoneme_map_valid_shapes(qtbot: QtBot, installation: HTInstallation):
    """Test that all phoneme map values are valid LIP shapes."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    for phoneme, shape in editor.phoneme_map.items():
        assert isinstance(shape, LIPShape), f"Phoneme {phoneme} maps to invalid shape"
        assert shape in ALL_LIP_SHAPES, f"Phoneme {phoneme} maps to unknown shape"


# ============================================================================
# PLAYBACK STATE TESTS
# ============================================================================


def test_lip_editor_play_preview_without_audio(qtbot: QtBot, installation: HTInstallation):
    """Test play preview without audio file (should show error)."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.lip = LIP()
    editor.lip.length = 10.0
    editor.lip.add(1.0, LIPShape.AH)

    # Try to play without audio
    from unittest.mock import patch

    with patch("toolset.gui.editors.lip.lip_editor.QMessageBox.warning") as mock_warning:
        editor.play_preview()
        mock_warning.assert_called_once()


def test_lip_editor_play_preview_without_lip(qtbot: QtBot, installation: HTInstallation):
    """Test play preview without LIP file (should show error)."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()

    # Set audio path but no LIP
    editor.audio_path.setText("test.wav")

    # Try to play
    from unittest.mock import patch

    with patch("toolset.gui.editors.lip.lip_editor.QMessageBox.warning") as mock_warning:
        editor.play_preview()
        mock_warning.assert_called_once()


# ============================================================================
# CONTEXT MENU UNIT TESTS
# ============================================================================


def test_lip_editor_context_menu_add_action(qtbot: QtBot, installation: HTInstallation):
    """Test context menu add action."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Right-click to show menu
    pos = QPoint(10, 10)
    editor.show_preview_context_menu(pos)

    # Menu should appear (we can't easily test menu actions in unit tests)


def test_lip_editor_context_menu_update_delete_actions(qtbot: QtBot, installation: HTInstallation):
    """Test context menu update and delete actions when item selected."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 10.0
    editor.duration_label.setText("10.000s")
    editor.time_input.setMaximum(10.0)

    # Add keyframe
    editor.time_input.setValue(1.0)
    editor.shape_select.setCurrentText(LIPShape.AH.name)
    editor.add_keyframe()

    # Select and right-click
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    pos = QPoint(10, 10)
    editor.show_preview_context_menu(pos)

    # Menu should show update and delete options


# ============================================================================
# COMPREHENSIVE INTEGRATION TESTS
# ============================================================================


def test_lip_editor_full_workflow_create_edit_save(qtbot: QtBot, installation: HTInstallation):
    """Test full workflow: create, edit, save."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)

    # Create new
    editor.new()
    editor.duration = 15.0
    editor.lip = LIP()
    editor.lip.length = 15.0
    editor.duration_label.setText("15.000s")
    editor.time_input.setMaximum(15.0)

    # Add keyframes
    for i in range(5):
        editor.time_input.setValue(float(i * 2))
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

    # Update some
    editor.update_preview()
    editor.preview_list.setCurrentRow(1)
    editor.on_keyframe_selected()
    editor.shape_select.setCurrentText(LIPShape.EE.name)
    editor.update_keyframe()

    # Delete one
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.delete_keyframe()

    # Save
    data, _ = editor.build()
    assert len(data) > 0

    # Load and verify
    editor.load(Path("test.lip"), "test", ResourceType.LIP, data)
    assert editor.lip is not None
    assert len(editor.lip.frames) == 4


def test_lip_editor_full_workflow_with_undo_redo(qtbot: QtBot, installation: HTInstallation):
    """Test full workflow with undo/redo operations."""
    editor = LIPEditor(None, installation)
    qtbot.addWidget(editor)
    editor.new()
    editor.duration = 20.0
    editor.duration_label.setText("20.000s")
    editor.time_input.setMaximum(20.0)

    # Add keyframes
    for i in range(3):
        editor.time_input.setValue(float(i * 3))
        editor.shape_select.setCurrentText(LIPShape.AH.name)
        editor.add_keyframe()

    # Update middle
    editor.update_preview()
    editor.preview_list.setCurrentRow(1)
    editor.on_keyframe_selected()
    editor.time_input.setValue(4.0)
    editor.update_keyframe()

    # Delete first
    editor.update_preview()
    editor.preview_list.setCurrentRow(0)
    editor.delete_keyframe()

    assert editor.lip is not None
    assert len(editor.lip.frames) == 2

    # Undo all
    editor.undo()  # Undo delete
    editor.undo()  # Undo update
    for _ in range(3):
        editor.undo()  # Undo adds

    assert editor.lip is not None
    assert len(editor.lip.frames) == 0

    # Redo all
    for _ in range(3):
        editor.redo()  # Redo adds
    editor.redo()  # Redo update
    editor.redo()  # Redo delete

    assert editor.lip is not None
    assert len(editor.lip.frames) == 2
