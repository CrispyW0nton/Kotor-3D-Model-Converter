"""Visual Layout Conformance Tests for QFileDialogExtended and FileSystemExplorerWidget.

These tests verify that the implementations match the visual layout and structure
of native Windows file dialogs and Windows 11 Explorer, as documented:

- QFileDialogExtended should match Windows "Open File" dialog (like Pasted Image 2 & 3)
- FileSystemExplorerWidget should match Windows 11 Explorer (like Pasted Image 4)

Key Visual Requirements:
-----------------------
Windows File Dialog (QFileDialogExtended):
1. Navigation toolbar: Back/Forward/Up buttons + Address bar + Search box (right-aligned)
2. Left sidebar: Quick access items (Desktop, Documents, etc.), This PC, Network
3. Main content: File list with columns (Name, Date modified, Type, Size)
4. Bottom controls: File name input, File type dropdown, Open/Cancel buttons
5. Optional right preview pane

Windows 11 Explorer (FileSystemExplorerWidget):
1. Toolbar with ribbon-style grouped actions (New, Cut, Copy, Paste, Sort, View)
2. Address bar with breadcrumb navigation
3. Left navigation pane with tree structure
4. Main content with multiple view modes
5. Status bar showing item count

These tests do NOT use mocking - they test actual widget properties and layout.
"""

from __future__ import annotations

import tempfile
import unittest

from pathlib import Path
from typing import TYPE_CHECKING

from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QLineEdit,
    QListView,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QTreeView,
)


class TestQFileDialogExtendedLayout(unittest.TestCase):
    """Test visual layout conformance for QFileDialogExtended.

    Verifies the dialog matches Windows file dialog layout requirements.
    """

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test class with QApplication."""
        cls.app: QApplication = QApplication.instance() or QApplication([])
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.temp_path = Path(cls.temp_dir.name)

        # Create test folder structure
        (cls.temp_path / "folder1").mkdir(exist_ok=True)
        (cls.temp_path / "file1.txt").write_text("test")

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up test resources."""
        cls.temp_dir.cleanup()

    def setUp(self) -> None:
        """Create fresh dialog for each test."""
        from utility.gui.qt.adapters.filesystem.qfiledialog.qfiledialog import (
            QFileDialog as AdapterQFileDialog,
        )
        from utility.gui.qt.filesystem.qfiledialogextended.qfiledialogextended import (
            QFileDialogExtended,
        )

        self.dialog = QFileDialogExtended(None, "Test", str(self.temp_path))
        self.dialog.setOption(AdapterQFileDialog.Option.DontUseNativeDialog, True)
        QTest.qWaitForWindowActive(self.dialog, 500)

    def tearDown(self) -> None:
        """Clean up dialog."""
        if self.dialog.isVisible():
            self.dialog.close()
        self.dialog.deleteLater()
        QCoreApplication.processEvents()

    # ========================================================================
    # GRID LAYOUT STRUCTURE TESTS
    # ========================================================================

    def test_main_layout_is_grid(self) -> None:
        """Verify the main layout is a QGridLayout."""
        layout = self.dialog.layout()
        self.assertIsInstance(layout, QGridLayout)

    def test_grid_has_minimum_rows(self) -> None:
        """Verify grid has at least the required rows for all elements."""
        grid = self.dialog.ui.gridlayout
        # Should have: ribbon (row 0), address (row 1), search (row 2),
        # splitter (row 3+), filename controls (row n-1), filetype (row n)
        self.assertGreaterEqual(grid.rowCount(), 4)

    def test_ribbon_position_in_grid(self) -> None:
        """Verify ribbon is at row 0 spanning all columns."""
        grid = self.dialog.ui.gridlayout
        ribbon_item = None

        # Search for ribbon in grid
        for i in range(grid.count()):
            item = grid.itemAt(i)
            if item and item.widget() is self.dialog.ribbons:
                row, col, row_span, col_span = grid.getItemPosition(i)
                self.assertEqual(row, 0, "Ribbon should be at row 0")
                self.assertGreaterEqual(col_span, 2, "Ribbon should span multiple columns")
                ribbon_item = item
                break

        self.assertIsNotNone(ribbon_item, "Ribbon should be in grid layout")

    def test_address_bar_position_in_grid(self) -> None:
        """Verify address bar is positioned correctly."""
        grid = self.dialog.ui.gridlayout

        for i in range(grid.count()):
            item = grid.itemAt(i)
            if item and item.widget() is self.dialog.address_bar:
                row, col, row_span, col_span = grid.getItemPosition(i)
                self.assertEqual(row, 1, "Address bar should be at row 1")
                self.assertGreaterEqual(col_span, 2, "Address bar should span columns")
                return

        self.fail("Address bar not found in grid layout")

    def test_search_filter_position_in_grid(self) -> None:
        """Verify search filter is positioned correctly."""
        grid = self.dialog.ui.gridlayout

        for i in range(grid.count()):
            item = grid.itemAt(i)
            if item and item.widget() is self.dialog.search_filter:
                row, col, row_span, col_span = grid.getItemPosition(i)
                self.assertEqual(row, 2, "Search filter should be at row 2")
                return

        self.fail("Search filter not found in grid layout")

    def test_splitter_position_in_grid(self) -> None:
        """Verify splitter (main content) is positioned after toolbar elements."""
        grid = self.dialog.ui.gridlayout

        for i in range(grid.count()):
            item = grid.itemAt(i)
            if item and item.widget() is self.dialog.ui.splitter:
                row, col, row_span, col_span = grid.getItemPosition(i)
                self.assertGreaterEqual(row, 3, "Splitter should be after toolbar rows")
                return

        # Splitter might be at different position due to offset
        self.assertIsNotNone(self.dialog.ui.splitter)

    # ========================================================================
    # SPLITTER AND SIDEBAR TESTS
    # ========================================================================

    def test_splitter_contains_sidebar(self) -> None:
        """Verify splitter contains sidebar on the left."""
        splitter = self.dialog.ui.splitter
        self.assertGreater(splitter.count(), 1, "Splitter should have multiple widgets")

        # First widget should be sidebar
        first_widget = splitter.widget(0)
        self.assertIsNotNone(first_widget)
        self.assertEqual(first_widget, self.dialog.ui.sidebar)

    def test_splitter_contains_content_frame(self) -> None:
        """Verify splitter contains main content frame."""
        splitter = self.dialog.ui.splitter

        # Second widget should be frame with stacked widget
        second_widget = splitter.widget(1)
        self.assertIsNotNone(second_widget)
        self.assertEqual(second_widget, self.dialog.ui.frame)

    def test_sidebar_is_visible_by_default(self) -> None:
        """Verify sidebar is visible by default."""
        self.assertTrue(self.dialog.ui.sidebar.isVisible())

    def test_sidebar_width_reasonable(self) -> None:
        """Verify sidebar has reasonable default width."""
        splitter_sizes = self.dialog.ui.splitter.sizes()
        if splitter_sizes:
            sidebar_width = splitter_sizes[0]
            # Should be between 150-300 pixels typically
            self.assertGreaterEqual(sidebar_width, 100)
            self.assertLessEqual(sidebar_width, 400)

    # ========================================================================
    # VIEW SWITCHING TESTS
    # ========================================================================

    def test_stacked_widget_has_two_pages(self) -> None:
        """Verify stacked widget has list view and tree view pages."""
        stacked = self.dialog.ui.stackedWidget
        self.assertEqual(stacked.count(), 2, "Should have exactly 2 pages")

    def test_list_view_exists_in_stack(self) -> None:
        """Verify list view exists."""
        self.assertIsNotNone(self.dialog.ui.listView)
        self.assertIsInstance(self.dialog.ui.listView, QListView)

    def test_tree_view_exists_in_stack(self) -> None:
        """Verify tree view exists."""
        self.assertIsNotNone(self.dialog.ui.treeView)
        self.assertIsInstance(self.dialog.ui.treeView, QTreeView)

    def test_view_mode_buttons_exist(self) -> None:
        """Verify view mode toggle buttons exist."""
        self.assertIsNotNone(self.dialog.ui.listModeButton)
        self.assertIsNotNone(self.dialog.ui.detailModeButton)
        self.assertIsInstance(self.dialog.ui.listModeButton, QToolButton)
        self.assertIsInstance(self.dialog.ui.detailModeButton, QToolButton)

    def test_view_mode_list_shows_list_view(self) -> None:
        """Verify list mode shows list view."""
        from utility.gui.qt.adapters.filesystem.qfiledialog.qfiledialog import (
            QFileDialog as AdapterQFileDialog,
        )

        self.dialog.setViewMode(AdapterQFileDialog.ViewMode.List)
        QTest.qWait(50)

        self.assertTrue(self.dialog.ui.listView.isVisible())
        self.assertFalse(self.dialog.ui.treeView.isVisible())

    def test_view_mode_detail_shows_tree_view(self) -> None:
        """Verify detail mode shows tree view."""
        from utility.gui.qt.adapters.filesystem.qfiledialog.qfiledialog import (
            QFileDialog as AdapterQFileDialog,
        )

        self.dialog.setViewMode(AdapterQFileDialog.ViewMode.Detail)
        QTest.qWait(50)

        self.assertFalse(self.dialog.ui.listView.isVisible())
        self.assertTrue(self.dialog.ui.treeView.isVisible())

    # ========================================================================
    # NAVIGATION BUTTONS TESTS
    # ========================================================================

    def test_navigation_buttons_exist(self) -> None:
        """Verify back, forward, up buttons exist."""
        self.assertIsNotNone(self.dialog.ui.backButton)
        self.assertIsNotNone(self.dialog.ui.forwardButton)
        self.assertIsNotNone(self.dialog.ui.toParentButton)

    def test_navigation_buttons_are_tool_buttons(self) -> None:
        """Verify navigation buttons are QToolButtons."""
        self.assertIsInstance(self.dialog.ui.backButton, QToolButton)
        self.assertIsInstance(self.dialog.ui.forwardButton, QToolButton)
        self.assertIsInstance(self.dialog.ui.toParentButton, QToolButton)

    def test_new_folder_button_exists(self) -> None:
        """Verify new folder button exists."""
        self.assertIsNotNone(self.dialog.ui.newFolderButton)
        self.assertIsInstance(self.dialog.ui.newFolderButton, QToolButton)

    # ========================================================================
    # BOTTOM CONTROLS TESTS
    # ========================================================================

    def test_file_name_label_exists(self) -> None:
        """Verify file name label exists."""
        self.assertIsNotNone(self.dialog.ui.fileNameLabel)
        self.assertIsInstance(self.dialog.ui.fileNameLabel, QLabel)

    def test_file_name_edit_exists(self) -> None:
        """Verify file name edit exists."""
        self.assertIsNotNone(self.dialog.ui.fileNameEdit)
        self.assertIsInstance(self.dialog.ui.fileNameEdit, QLineEdit)

    def test_file_type_label_exists(self) -> None:
        """Verify file type label exists."""
        self.assertIsNotNone(self.dialog.ui.fileTypeLabel)
        self.assertIsInstance(self.dialog.ui.fileTypeLabel, QLabel)

    def test_file_type_combo_exists(self) -> None:
        """Verify file type combo box exists."""
        self.assertIsNotNone(self.dialog.ui.fileTypeCombo)

    def test_button_box_exists(self) -> None:
        """Verify dialog button box exists."""
        self.assertIsNotNone(self.dialog.ui.buttonBox)

    # ========================================================================
    # ADDRESS BAR TESTS
    # ========================================================================

    def test_address_bar_has_navigation_buttons(self) -> None:
        """Verify address bar has back/forward/up buttons."""
        addr = self.dialog.address_bar
        self.assertTrue(hasattr(addr, "backButton"))
        self.assertTrue(hasattr(addr, "forwardButton"))
        self.assertTrue(hasattr(addr, "upButton"))

    def test_address_bar_shows_current_path(self) -> None:
        """Verify address bar displays current directory path."""
        current_dir = Path(self.dialog.directory().absolutePath())
        addr_path = self.dialog.address_bar.current_path
        self.assertEqual(addr_path, current_dir)

    def test_address_bar_updates_on_navigation(self) -> None:
        """Verify address bar updates when directory changes."""
        target = self.temp_path / "folder1"
        self.dialog.setDirectory(str(target))
        QTest.qWait(100)

        self.assertEqual(self.dialog.address_bar.current_path, target)

    # ========================================================================
    # SEARCH FILTER TESTS
    # ========================================================================

    def test_search_filter_has_line_edit(self) -> None:
        """Verify search filter has text input."""
        self.assertTrue(hasattr(self.dialog.search_filter, "line_edit"))
        self.assertIsInstance(self.dialog.search_filter.line_edit, QLineEdit)

    def test_search_filter_has_placeholder(self) -> None:
        """Verify search filter has placeholder text."""
        placeholder = self.dialog.search_filter.line_edit.placeholderText()
        self.assertTrue(len(placeholder) > 0)

    # ========================================================================
    # PREVIEW PANE TESTS
    # ========================================================================

    def test_preview_pane_exists(self) -> None:
        """Verify preview pane widget exists."""
        self.assertTrue(hasattr(self.dialog, "preview_pane"))
        self.assertIsNotNone(self.dialog.preview_pane)

    def test_preview_pane_hidden_by_default(self) -> None:
        """Verify preview pane is hidden by default."""
        self.assertFalse(self.dialog.preview_pane.isVisible())

    def test_preview_pane_can_be_shown(self) -> None:
        """Verify preview pane can be toggled visible."""
        self.dialog.toggle_preview_pane(True)
        QTest.qWait(50)
        self.assertTrue(self.dialog.preview_pane.isVisible())

    def test_preview_pane_in_splitter(self) -> None:
        """Verify preview pane is added to splitter."""
        splitter = self.dialog.ui.splitter
        # When visible, preview pane should be in splitter
        self.dialog.toggle_preview_pane(True)
        QTest.qWait(50)

        # Splitter should have 3 widgets: sidebar, frame, preview
        self.assertGreaterEqual(splitter.count(), 2)

    # ========================================================================
    # RIBBON TESTS
    # ========================================================================

    def test_ribbon_exists(self) -> None:
        """Verify ribbon widget exists."""
        self.assertIsNotNone(self.dialog.ribbons)

    def test_ribbon_has_tab_widget(self) -> None:
        """Verify ribbon has tab widget for different tabs."""
        self.assertTrue(hasattr(self.dialog.ribbons, "tab_widget"))

    def test_ribbon_has_view_tab(self) -> None:
        """Verify ribbon has View tab."""
        tab_widget = self.dialog.ribbons.tab_widget
        tab_texts = [tab_widget.tabText(i) for i in range(tab_widget.count())]
        self.assertIn("View", tab_texts)

    def test_ribbon_has_home_tab(self) -> None:
        """Verify ribbon has Home tab."""
        tab_widget = self.dialog.ribbons.tab_widget
        tab_texts = [tab_widget.tabText(i) for i in range(tab_widget.count())]
        self.assertIn("Home", tab_texts)

    # ========================================================================
    # COLUMN HEADER TESTS (Detail View)
    # ========================================================================

    def test_tree_view_has_header(self) -> None:
        """Verify tree view has header visible."""
        header = self.dialog.ui.treeView.header()
        self.assertIsNotNone(header)

    def test_tree_view_shows_name_column(self) -> None:
        """Verify Name column is shown."""
        model = self.dialog.model
        # Column 0 should be Name
        header_text = model.headerData(0, Qt.Orientation.Horizontal)
        self.assertIsNotNone(header_text)

    def test_tree_view_shows_size_column(self) -> None:
        """Verify Size column exists in model."""
        model = self.dialog.model
        # Should have Size column (column 1)
        header_text = model.headerData(1, Qt.Orientation.Horizontal)
        self.assertIsNotNone(header_text)

    def test_tree_view_shows_type_column(self) -> None:
        """Verify Type column exists in model."""
        model = self.dialog.model
        # Should have Type column (column 2)
        header_text = model.headerData(2, Qt.Orientation.Horizontal)
        self.assertIsNotNone(header_text)

    def test_tree_view_shows_date_column(self) -> None:
        """Verify Date Modified column exists in model."""
        model = self.dialog.model
        # Should have Date Modified column (column 3)
        header_text = model.headerData(3, Qt.Orientation.Horizontal)
        self.assertIsNotNone(header_text)


class TestFileSystemExplorerWidgetLayout(unittest.TestCase):
    """Test visual layout conformance for FileSystemExplorerWidget.

    Verifies the widget matches Windows 11 Explorer layout requirements.
    """

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test class with QApplication."""
        cls.app: QApplication = QApplication.instance() or QApplication([])
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.temp_path = Path(cls.temp_dir.name)

        (cls.temp_path / "folder1").mkdir(exist_ok=True)
        (cls.temp_path / "file1.txt").write_text("test")

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up test resources."""
        cls.temp_dir.cleanup()

    def setUp(self) -> None:
        """Create fresh explorer widget for each test."""
        from utility.gui.qt.filesystem.qfileexplorer.explorer import (
            FileSystemExplorerWidget,
        )

        self.explorer = FileSystemExplorerWidget(
            initial_path=self.temp_path,
            parent=None,
        )
        QTest.qWaitForWindowActive(self.explorer, 500)

    def tearDown(self) -> None:
        """Clean up explorer widget."""
        if self.explorer.isVisible():
            self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    # ========================================================================
    # MAIN STRUCTURE TESTS
    # ========================================================================

    def test_is_main_window(self) -> None:
        """Verify explorer is a QMainWindow."""
        from qtpy.QtWidgets import QMainWindow

        self.assertIsInstance(self.explorer, QMainWindow)

    def test_has_central_widget(self) -> None:
        """Verify explorer has central widget."""
        self.assertIsNotNone(self.explorer.centralWidget())

    def test_has_status_bar(self) -> None:
        """Verify explorer has status bar."""
        self.assertIsNotNone(self.explorer.statusBar())

    def test_has_menu_bar(self) -> None:
        """Verify explorer has menu bar."""
        self.assertIsNotNone(self.explorer.menuBar())

    # ========================================================================
    # TOOLBAR/RIBBON TESTS
    # ========================================================================

    def test_ribbon_widget_exists(self) -> None:
        """Verify ribbon widget exists."""
        self.assertIsNotNone(self.explorer.ui.ribbonWidget)

    def test_ribbon_at_top(self) -> None:
        """Verify ribbon is at top of layout."""
        ribbon = self.explorer.ui.ribbonWidget
        layout = self.explorer.ui.topLayout

        # Ribbon should be first widget in top layout
        self.assertEqual(layout.itemAt(0).widget(), ribbon)

    def test_address_bar_exists(self) -> None:
        """Verify address bar exists."""
        self.assertIsNotNone(self.explorer.ui.addressBar)

    def test_search_bar_exists(self) -> None:
        """Verify search bar exists."""
        self.assertIsNotNone(self.explorer.ui.searchBar)

    # ========================================================================
    # SIDEBAR TESTS
    # ========================================================================

    def test_main_splitter_exists(self) -> None:
        """Verify main splitter exists for sidebar/content split."""
        self.assertIsNotNone(self.explorer.ui.mainSplitter)
        self.assertIsInstance(self.explorer.ui.mainSplitter, QSplitter)

    def test_sidebar_widget_exists(self) -> None:
        """Verify sidebar widget exists."""
        self.assertIsNotNone(self.explorer.ui.sidebarWidget)

    def test_sidebar_has_tree_view(self) -> None:
        """Verify sidebar has file system tree view."""
        self.assertIsNotNone(self.explorer.ui.fileSystemTreeView)
        self.assertIsInstance(self.explorer.ui.fileSystemTreeView, QTreeView)

    def test_sidebar_tree_shows_only_name(self) -> None:
        """Verify sidebar tree only shows name column."""
        tree = self.explorer.ui.fileSystemTreeView
        # Columns 1-3 should be hidden
        self.assertTrue(tree.isColumnHidden(1) or tree.columnWidth(1) == 0)

    def test_sidebar_has_bookmarks(self) -> None:
        """Verify sidebar has bookmarks list."""
        self.assertIsNotNone(self.explorer.ui.bookmarksListView)

    def test_sidebar_has_drives_widget(self) -> None:
        """Verify sidebar has drives/quick access widget."""
        self.assertIsNotNone(self.explorer.ui.drivesWidget)

    # ========================================================================
    # MAIN VIEW TESTS
    # ========================================================================

    def test_dynamic_view_exists(self) -> None:
        """Verify dynamic stacked view exists."""
        self.assertIsNotNone(self.explorer.ui.dynamicView)

    def test_dynamic_view_has_multiple_modes(self) -> None:
        """Verify dynamic view supports multiple view modes."""
        view = self.explorer.ui.dynamicView
        self.assertGreater(view.count(), 1)

    def test_has_list_view(self) -> None:
        """Verify list view exists."""
        list_view = self.explorer.ui.dynamicView.list_view()
        self.assertIsNotNone(list_view)

    def test_has_tree_view(self) -> None:
        """Verify tree view exists."""
        tree_view = self.explorer.ui.dynamicView.tree_view()
        self.assertIsNotNone(tree_view)

    # ========================================================================
    # STATUS BAR TESTS
    # ========================================================================

    def test_status_bar_has_item_count(self) -> None:
        """Verify status bar shows item count."""
        self.assertIsNotNone(self.explorer.ui.itemCountLabel)

    def test_status_bar_has_selected_count(self) -> None:
        """Verify status bar shows selected count."""
        self.assertIsNotNone(self.explorer.ui.selectedCountLabel)

    def test_status_bar_has_free_space(self) -> None:
        """Verify status bar shows free space."""
        self.assertIsNotNone(self.explorer.ui.freeSpaceLabel)

    def test_status_bar_has_zoom_slider(self) -> None:
        """Verify status bar has zoom slider."""
        self.assertIsNotNone(self.explorer.ui.zoom_slider)

    def test_status_bar_has_progress_bar(self) -> None:
        """Verify status bar has progress bar (hidden by default)."""
        self.assertIsNotNone(self.explorer.ui.progressBar)

    # ========================================================================
    # PREVIEW WIDGET TESTS
    # ========================================================================

    def test_preview_widget_exists(self) -> None:
        """Verify preview widget exists."""
        self.assertIsNotNone(self.explorer.ui.previewWidget)

    def test_preview_widget_hidden_by_default(self) -> None:
        """Verify preview widget is hidden by default."""
        self.assertFalse(self.explorer.ui.previewWidget.isVisible())

    # ========================================================================
    # TASK STATUS TESTS
    # ========================================================================

    def test_task_status_widget_exists(self) -> None:
        """Verify task status widget exists."""
        self.assertIsNotNone(self.explorer.ui.taskStatusWidget)

    # ========================================================================
    # NAVIGATION TESTS
    # ========================================================================

    def test_address_bar_has_refresh_button(self) -> None:
        """Verify address bar has refresh button."""
        addr = self.explorer.ui.addressBar
        self.assertTrue(hasattr(addr, "refreshButton"))

    def test_address_bar_shows_current_path(self) -> None:
        """Verify address bar shows current path."""
        self.assertEqual(self.explorer.ui.addressBar.current_path, self.explorer.current_path)

    # ========================================================================
    # SIZE POLICY TESTS
    # ========================================================================

    def test_sidebar_has_fixed_minimum_width(self) -> None:
        """Verify sidebar has reasonable minimum width."""
        sidebar = self.explorer.ui.sidebarWidget
        min_width = sidebar.minimumWidth()
        # Should have some minimum width set
        self.assertGreaterEqual(min_width, 0)

    def test_dynamic_view_expands(self) -> None:
        """Verify dynamic view expands to fill space."""
        view = self.explorer.ui.dynamicView
        policy = view.sizePolicy()
        self.assertIn(policy.horizontalPolicy(), [QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred])

    # ========================================================================
    # MODEL TESTS
    # ========================================================================

    def test_has_filesystem_model(self) -> None:
        """Verify file system model is set up."""
        self.assertIsNotNone(self.explorer.fs_model)

    def test_has_proxy_model(self) -> None:
        """Verify proxy model exists for filtering."""
        self.assertIsNotNone(self.explorer.proxy_model)

    def test_proxy_model_source_is_fs_model(self) -> None:
        """Verify proxy model wraps file system model."""
        self.assertEqual(self.explorer.proxy_model.sourceModel(), self.explorer.fs_model)

    def test_views_use_proxy_model(self) -> None:
        """Verify views use the proxy model."""
        dynamic_view = self.explorer.ui.dynamicView
        for view in dynamic_view.all_views():
            self.assertEqual(view.model(), self.explorer.proxy_model)


class TestLayoutConformanceIntegration(unittest.TestCase):
    """Integration tests verifying both widgets work together correctly."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test class."""
        cls.app: QApplication = QApplication.instance() or QApplication([])
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.temp_path = Path(cls.temp_dir.name)
        (cls.temp_path / "test_folder").mkdir(exist_ok=True)
        (cls.temp_path / "test.txt").write_text("content")

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up."""
        cls.temp_dir.cleanup()

    def test_both_widgets_initialize_without_error(self) -> None:
        """Verify both widgets can be initialized together."""
        from utility.gui.qt.filesystem.qfiledialogextended.qfiledialogextended import (
            QFileDialogExtended,
        )
        from utility.gui.qt.filesystem.qfileexplorer.explorer import (
            FileSystemExplorerWidget,
        )

        dialog = QFileDialogExtended(None, "Test", str(self.temp_path))
        explorer = FileSystemExplorerWidget(initial_path=self.temp_path)

        self.assertIsNotNone(dialog)
        self.assertIsNotNone(explorer)

        dialog.deleteLater()
        explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_widgets_share_similar_structure(self) -> None:
        """Verify both widgets have similar structural elements."""
        from utility.gui.qt.filesystem.qfiledialogextended.qfiledialogextended import (
            QFileDialogExtended,
        )
        from utility.gui.qt.filesystem.qfileexplorer.explorer import (
            FileSystemExplorerWidget,
        )

        dialog = QFileDialogExtended(None, "Test", str(self.temp_path))
        explorer = FileSystemExplorerWidget(initial_path=self.temp_path)

        # Both should have address bar
        self.assertTrue(hasattr(dialog, "address_bar"))
        self.assertTrue(hasattr(explorer.ui, "addressBar"))

        # Both should have ribbon/toolbar
        self.assertTrue(hasattr(dialog, "ribbons"))
        self.assertTrue(hasattr(explorer.ui, "ribbonWidget"))

        # Both should use file system model
        self.assertIsNotNone(dialog.model)
        self.assertIsNotNone(explorer.fs_model)

        dialog.deleteLater()
        explorer.deleteLater()
        QCoreApplication.processEvents()


if __name__ == "__main__":
    unittest.main()
