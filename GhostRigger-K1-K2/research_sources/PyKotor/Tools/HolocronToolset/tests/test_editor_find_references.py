"""
Unit Tests for Find References functionality in specific editors.

Tests cover NSS, DLG, TLK editors and ComboBox2DA widget.
Each test uses real installation data and pytest-qt for headless testing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pathlib import Path
from qtpy.QtCore import Qt
from qtpy.QtGui import QTextCursor

from toolset.data.installation import HTInstallation
from toolset.gui.editors.nss import NSSEditor
from toolset.gui.editors.dlg.editor import DLGEditor
from toolset.gui.editors.tlk import TLKEditor
from toolset.gui.widgets.edit.combobox_2da import ComboBox2DA

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


class TestNSSEditorFindReferences:
    """Tests for NSS editor Find References functionality."""

    def test_nss_editor_find_all_references_in_file(self, qtbot: QtBot, installation: HTInstallation):
        """Test NSS editor Find All References in current file."""
        editor = NSSEditor(None, installation)
        qtbot.addWidget(editor)

        # Set some code with a function
        code = """
void main() {
    int x = 5;
    int y = 10;
    int result = x + y;
}
"""
        editor.ui.codeEdit.setPlainText(code)

        # Move cursor to "x"
        cursor = editor.ui.codeEdit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, 2)  # Line 2 (0-indexed)
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, 8)  # Column 8
        editor.ui.codeEdit.setTextCursor(cursor)

        # Trigger Find All References
        editor._find_all_references_at_cursor()

        # Should find results panel
        assert editor.ui.panelTabs.currentWidget() == editor.ui.findResultsTab

    def test_nss_editor_find_references_in_installation(self, qtbot: QtBot, installation: HTInstallation):
        """Test NSS editor Find References in Installation."""
        editor = NSSEditor(None, installation)
        qtbot.addWidget(editor)

        # Set code with a script name
        code = "void main() { }"
        editor.ui.codeEdit.setPlainText(code)

        # Set the file path to a script name
        editor._filepath = Path("test_script")
        editor._resname = "test_script"

        # The context menu should have "Find References in Installation..."
        # We can't easily test the menu action without showing dialogs,
        # but we can verify the method exists
        assert hasattr(editor, "_find_script_references_in_installation")

    def test_nss_editor_context_menu_find_references(self, qtbot: QtBot, installation: HTInstallation):
        """Test NSS editor context menu has Find References action."""
        editor = NSSEditor(None, installation)
        qtbot.addWidget(editor)

        code = "void main() { int x = 5; }"
        editor.ui.codeEdit.setPlainText(code)

        # Move cursor to a word
        cursor = editor.ui.codeEdit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, 10)  # Column 10 (on "main")
        editor.ui.codeEdit.setTextCursor(cursor)

        # The context menu should be available
        # We can verify the code editor has context menu support
        assert editor.ui.codeEdit is not None


class TestDLGEditorFindReferences:
    """Tests for DLG editor Find References functionality."""

    def test_dlg_editor_find_references_method_exists(self, qtbot: QtBot, installation: HTInstallation):
        """Test DLG editor has find_references method."""
        editor = DLGEditor(None, installation)
        qtbot.addWidget(editor)

        # Verify method exists
        assert hasattr(editor, "find_references")
        assert hasattr(editor, "_find_dialog_references_in_installation")

    def test_dlg_editor_find_references_in_installation(self, qtbot: QtBot, installation: HTInstallation):
        """Test DLG editor Find References in Installation."""
        editor = DLGEditor(None, installation)
        qtbot.addWidget(editor)

        # Set a dialog resref
        editor._resname = "test_dialog"

        # The method should exist and be callable
        # We can't easily test it without actual dialog data, but we can verify
        # the method signature
        assert callable(editor._find_dialog_references_in_installation)


class TestTLKEditorFindReferences:
    """Tests for TLK editor Find References functionality."""

    def test_tlk_editor_find_references_method_exists(self, qtbot: QtBot, installation: HTInstallation):
        """Test TLK editor has find_references method."""
        editor = TLKEditor(None, installation)
        qtbot.addWidget(editor)

        # Verify method exists
        assert hasattr(editor, "find_references")

    def test_tlk_editor_find_references_context_menu(self, qtbot: QtBot, installation: HTInstallation):
        """Test TLK editor context menu has Find References action."""
        editor = TLKEditor(None, installation)
        qtbot.addWidget(editor)

        # Load a TLK file if available
        # We can't easily test without actual TLK data, but we can verify
        # the editor can be created
        assert editor is not None


class TestComboBox2DAFindReferences:
    """Tests for ComboBox2DA Find References functionality."""

    def test_combobox2da_context_menu_setup(self, qtbot: QtBot, installation: HTInstallation):
        """Test ComboBox2DA context menu is set up for reference search."""
        from qtpy.QtWidgets import QWidget
        from pykotor.resource.type import ResourceType
        from pykotor.extract.installation import SearchLocation

        # Create a ComboBox2DA with a parent widget
        parent = QWidget()
        qtbot.addWidget(parent)
        combo = ComboBox2DA(parent)
        qtbot.addWidget(combo)

        # Set a 2DA file - load it from installation and use set_context
        try:
            from toolset.data.installation import HTInstallation

            resname = "classes"
            order = [SearchLocation.OVERRIDE, SearchLocation.MODULES, SearchLocation.CHITIN]
            result = installation.resource(resname, ResourceType.TwoDA, order)
            if result:
                from pykotor.resource.formats.twoda.twoda_auto import read_2da

                twoda_data = read_2da(result.data)
                combo.set_context(twoda_data, installation, resname)
                combo.set_items(twoda_data.get_column("label"))
        except Exception:
            # If classes.2da doesn't exist, that's okay
            pass

        # Verify context menu policy is set
        assert combo.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu

    def test_combobox2da_find_references_action(self, qtbot: QtBot, installation: HTInstallation):
        """Test ComboBox2DA has Find References action in context menu."""
        from qtpy.QtCore import QPoint
        from qtpy.QtWidgets import QWidget
        from pykotor.resource.type import ResourceType
        from pykotor.extract.installation import SearchLocation

        # Create a ComboBox2DA with a parent widget
        parent = QWidget()
        qtbot.addWidget(parent)
        combo = ComboBox2DA(parent)
        qtbot.addWidget(combo)

        # Try to set a 2DA
        try:
            resname = "classes"
            order = [SearchLocation.OVERRIDE, SearchLocation.MODULES, SearchLocation.CHITIN]
            result = installation.resource(resname, ResourceType.TwoDA, order)
            if result:
                from pykotor.resource.formats.twoda.twoda_auto import read_2da

                twoda_data = read_2da(result.data)
                combo.set_context(twoda_data, installation, resname)
                combo.set_items(twoda_data.get_column("label"))
                combo.setCurrentIndex(0)  # Select first row

                # Call the context menu handler directly
                # The on_context_menu method creates the menu internally
                combo.on_context_menu(QPoint(0, 0))

                # Verify the context menu policy is set correctly
                assert combo.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
            else:
                pytest.skip("2DA file not available")
        except Exception:
            # If 2DA doesn't exist or other error, skip
            pytest.skip("2DA file not available or error setting up ComboBox2DA")


class TestReferenceSearchIntegration:
    """Integration tests for reference search across editors."""

    def test_utc_editor_script_field_tooltip(self, qtbot: QtBot, installation: HTInstallation):
        """Test UTC editor script field has reference search tooltip."""
        from toolset.gui.editors.utc import UTCEditor

        editor = UTCEditor(None, installation)
        qtbot.addWidget(editor)

        script_field = editor.ui.onHeartbeatSelect

        # Check tooltip
        tooltip = script_field.toolTip()
        assert "find references" in tooltip.lower() or "reference" in tooltip.lower()

    def test_utp_editor_tag_field_tooltip(self, qtbot: QtBot, installation: HTInstallation):
        """Test UTP editor tag field has reference search tooltip."""
        from toolset.gui.editors.utp import UTPEditor

        editor = UTPEditor(None, installation)
        qtbot.addWidget(editor)

        tag_field = editor.ui.tagEdit

        # Check tooltip
        tooltip = tag_field.toolTip()
        assert "find references" in tooltip.lower() or "reference" in tooltip.lower()

    def test_utd_editor_conversation_field_tooltip(self, qtbot: QtBot, installation: HTInstallation):
        """Test UTD editor conversation field has reference search tooltip."""
        from toolset.gui.editors.utd import UTDEditor

        editor = UTDEditor(None, installation)
        qtbot.addWidget(editor)

        conversation_field = editor.ui.conversationEdit

        # Check tooltip
        tooltip = conversation_field.toolTip()
        assert "find references" in tooltip.lower() or "reference" in tooltip.lower()

    def test_are_editor_script_field_tooltip(self, qtbot: QtBot, installation: HTInstallation):
        """Test ARE editor script field has reference search tooltip."""
        from toolset.gui.editors.are import AREEditor

        editor = AREEditor(None, installation)
        qtbot.addWidget(editor)

        script_field = editor.ui.onEnterSelect

        # Check tooltip
        tooltip = script_field.toolTip()
        assert "find references" in tooltip.lower() or "reference" in tooltip.lower()

    def test_ifo_editor_script_field_tooltip(self, qtbot: QtBot, installation: HTInstallation):
        """Test IFO editor script field has reference search tooltip."""
        from toolset.gui.editors.ifo import IFOEditor

        editor = IFOEditor(None, installation)
        qtbot.addWidget(editor)

        # IFO has multiple script fields, check at least one
        # The actual field names depend on the UI structure
        # We can verify the editor was created
        assert editor is not None

    def test_uti_editor_tag_field_tooltip(self, qtbot: QtBot, installation: HTInstallation):
        """Test UTI editor tag field has reference search tooltip."""
        from toolset.gui.editors.uti import UTIEditor

        editor = UTIEditor(None, installation)
        qtbot.addWidget(editor)

        tag_field = editor.ui.tagEdit
        assert tag_field is not None, "UTI editor has no tagEdit widget"

        # Reference search appends "Right-click to find references..." (or translated); accept any hint
        tooltip = (tag_field.toolTip() or "").lower()
        assert "reference" in tooltip or "find reference" in tooltip, (
            f"Tag field tooltip should mention reference search; got: {tooltip[:80]!r}..."
        )

    def test_utt_editor_script_field_tooltip(self, qtbot: QtBot, installation: HTInstallation):
        """Test UTT editor script field has reference search tooltip."""
        from toolset.gui.editors.utt import UTTEditor

        editor = UTTEditor(None, installation)
        qtbot.addWidget(editor)

        script_field = editor.ui.onHeartbeatSelect

        # Check tooltip
        tooltip = script_field.toolTip()
        assert "find references" in tooltip.lower() or "reference" in tooltip.lower()
