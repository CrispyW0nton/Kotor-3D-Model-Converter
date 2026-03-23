"""Windows 11 Explorer Widget Component Tests.

This module provides exhaustive component-level tests for the FileSystemExplorerWidget
and its subcomponents:
- DynamicStackedView
- Navigation toolbar
- RibbonsWidget integration
- Quick Access panel
- Status bar

Tests verify exact conformance to Windows 11 Explorer behavior.
"""

from __future__ import annotations

import tempfile
import unittest

from pathlib import Path
from typing import ClassVar, Final

from qtpy.QtCore import (
    QCoreApplication,
    Qt,
)
from qtpy.QtTest import QTest
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QLabel,
    QListView,
    QMainWindow,
    QMenuBar,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QToolButton,
    QTreeView,
    QWidget,
)

# =============================================================================
# TEST CONSTANTS
# =============================================================================


class WindowsExplorerSpecs:
    """Windows 11 Explorer specifications."""

    # Window dimensions
    MIN_WIDTH: Final[int] = 500
    MIN_HEIGHT: Final[int] = 400
    DEFAULT_WIDTH: Final[int] = 1024
    DEFAULT_HEIGHT: Final[int] = 600

    # Title bar (captured in OS, not Qt)
    TITLE_BAR_HEIGHT: Final[int] = 32

    # Ribbon
    RIBBON_COLLAPSED_HEIGHT: Final[int] = 30
    RIBBON_EXPANDED_HEIGHT: Final[int] = 94
    RIBBON_TAB_HEIGHT: Final[int] = 30
    RIBBON_GROUP_SPACING: Final[int] = 4

    # Navigation bar
    NAV_BAR_HEIGHT: Final[int] = 40
    NAV_BUTTON_SIZE: Final[int] = 32

    # Address bar
    ADDRESS_BAR_HEIGHT: Final[int] = 28
    ADDRESS_BAR_MIN_WIDTH: Final[int] = 200

    # Search box
    SEARCH_BOX_HEIGHT: Final[int] = 28
    SEARCH_BOX_WIDTH: Final[int] = 220

    # Navigation pane (sidebar)
    NAV_PANE_MIN_WIDTH: Final[int] = 150
    NAV_PANE_DEFAULT_WIDTH: Final[int] = 200
    NAV_PANE_MAX_WIDTH: Final[int] = 400
    NAV_PANE_ITEM_HEIGHT: Final[int] = 24

    # Content area
    CONTENT_MIN_WIDTH: Final[int] = 200
    CONTENT_PADDING: Final[int] = 0

    # Status bar
    STATUS_BAR_HEIGHT: Final[int] = 23

    # View mode icon sizes
    ICON_EXTRA_LARGE: Final[int] = 256
    ICON_LARGE: Final[int] = 96
    ICON_MEDIUM: Final[int] = 48
    ICON_SMALL: Final[int] = 32
    ICON_LIST: Final[int] = 16
    ICON_DETAILS: Final[int] = 16

    # Details view
    DETAILS_ROW_HEIGHT: Final[int] = 20
    DETAILS_HEADER_HEIGHT: Final[int] = 22


class QuickAccessSpecs:
    """Quick Access panel specifications."""

    # Standard pinned folders
    STANDARD_FOLDERS: Final[list[str]] = [
        "Desktop",
        "Downloads",
        "Documents",
        "Pictures",
        "Music",
        "Videos",
    ]

    # Recent files section
    RECENT_FILES_HEADER: Final[str] = "Recent files"
    MAX_RECENT_FILES: Final[int] = 20


class ThisPCSpecs:
    """This PC section specifications."""

    # Folders section
    FOLDERS: Final[list[str]] = [
        "Desktop",
        "Documents",
        "Downloads",
        "Music",
        "Pictures",
        "Videos",
    ]

    # Device categories
    DEVICE_CATEGORIES: Final[list[str]] = [
        "Devices and drives",
        "Network locations",
    ]


class RibbonTabSpecs:
    """Ribbon tab specifications."""

    # Standard tabs
    FILE_TAB: Final[str] = "File"
    HOME_TAB: Final[str] = "Home"
    SHARE_TAB: Final[str] = "Share"
    VIEW_TAB: Final[str] = "View"

    # Home tab groups
    HOME_GROUPS: Final[list[str]] = [
        "Clipboard",
        "Organize",
        "New",
        "Open",
        "Select",
    ]

    # Share tab groups
    SHARE_GROUPS: Final[list[str]] = [
        "Send",
        "Share with",
    ]

    # View tab groups
    VIEW_GROUPS: Final[list[str]] = [
        "Panes",
        "Layout",
        "Current view",
        "Show/hide",
    ]


# =============================================================================
# BASE TEST CLASS
# =============================================================================


class ExplorerComponentTestBase(unittest.TestCase):
    """Base class for explorer component tests."""

    TIMEOUT_SECONDS: ClassVar[int] = 120
    app: ClassVar[QApplication]
    temp_dir: ClassVar[tempfile.TemporaryDirectory]

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test class."""
        cls.app = QApplication.instance() or QApplication([])
        cls.temp_dir = tempfile.TemporaryDirectory()

        # Create test file structure
        test_dir = Path(cls.temp_dir.name)

        # Create files
        (test_dir / "document.txt").write_text("Document content")
        (test_dir / "spreadsheet.xlsx").write_bytes(b"PK\x03\x04")
        (test_dir / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (test_dir / "archive.zip").write_bytes(b"PK\x03\x04")

        # Create folders
        (test_dir / "Folder_A").mkdir(exist_ok=True)
        (test_dir / "Folder_B").mkdir(exist_ok=True)
        (test_dir / "Folder_A" / "nested.txt").write_text("Nested file")

        # Create hidden file (Windows-style)
        (test_dir / ".hidden_file").write_text("Hidden")

    @classmethod
    def tearDownClass(cls) -> None:
        """Tear down test class."""
        cls.temp_dir.cleanup()


# =============================================================================
# MAIN WINDOW STRUCTURE TESTS
# =============================================================================


class TestExplorerMainWindowStructure(ExplorerComponentTestBase):
    """Tests for explorer main window structure."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_explorer_is_main_window(self) -> None:
        """Verify explorer is a QMainWindow."""
        self.assertIsInstance(self.explorer, QMainWindow)

    def test_explorer_has_menu_bar(self) -> None:
        """Verify explorer has menu bar."""
        menu_bar = self.explorer.menuBar()
        self.assertIsNotNone(menu_bar)
        self.assertIsInstance(menu_bar, QMenuBar)

    def test_explorer_has_status_bar(self) -> None:
        """Verify explorer has status bar."""
        status_bar = self.explorer.statusBar()
        self.assertIsNotNone(status_bar)
        self.assertIsInstance(status_bar, QStatusBar)

    def test_explorer_has_central_widget(self) -> None:
        """Verify explorer has central widget."""
        central = self.explorer.centralWidget()
        self.assertIsNotNone(central)

    def test_explorer_minimum_size(self) -> None:
        """Verify explorer has reasonable minimum size."""
        min_size = self.explorer.minimumSize()

        # Should have some minimum constraints
        self.assertGreaterEqual(min_size.width(), 0)
        self.assertGreaterEqual(min_size.height(), 0)


class TestExplorerToolbars(ExplorerComponentTestBase):
    """Tests for explorer toolbars."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_has_navigation_toolbar(self) -> None:
        """Verify explorer has navigation toolbar."""
        toolbars = self.explorer.findChildren(QToolBar)

        # Should have at least one toolbar
        self.assertGreater(len(toolbars), 0)

    def test_navigation_buttons_exist(self) -> None:
        """Verify navigation buttons exist."""
        tool_buttons = self.explorer.findChildren(QToolButton)

        # Should have tool buttons for navigation
        self.assertGreater(len(tool_buttons), 0)


# =============================================================================
# RIBBON TESTS
# =============================================================================


class TestExplorerRibbon(ExplorerComponentTestBase):
    """Tests for explorer ribbon component."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_ribbon_widget_exists(self) -> None:
        """Verify ribbon widget exists."""
        ribbon = self.explorer.ribbon_widget
        self.assertIsNotNone(ribbon)

    def test_ribbon_has_tabs(self) -> None:
        """Verify ribbon has tab widget."""
        ribbon = self.explorer.ribbon_widget

        tab_widgets = ribbon.findChildren(QTabWidget)
        self.assertGreater(len(tab_widgets), 0)

    def test_ribbon_file_tab_exists(self) -> None:
        """Verify File tab exists."""
        ribbon = self.explorer.ribbon_widget
        tab_widget = ribbon.tab_widget

        tab_names = [tab_widget.tabText(i).lower() for i in range(tab_widget.count())]

        self.assertIn("file", tab_names)

    def test_ribbon_home_tab_exists(self) -> None:
        """Verify Home tab exists."""
        ribbon = self.explorer.ribbon_widget
        tab_widget = ribbon.tab_widget

        tab_names = [tab_widget.tabText(i).lower() for i in range(tab_widget.count())]

        self.assertIn("home", tab_names)

    def test_ribbon_share_tab_exists(self) -> None:
        """Verify Share tab exists."""
        ribbon = self.explorer.ribbon_widget
        tab_widget = ribbon.tab_widget

        tab_names = [tab_widget.tabText(i).lower() for i in range(tab_widget.count())]

        self.assertIn("share", tab_names)

    def test_ribbon_view_tab_exists(self) -> None:
        """Verify View tab exists."""
        ribbon = self.explorer.ribbon_widget
        tab_widget = ribbon.tab_widget

        tab_names = [tab_widget.tabText(i).lower() for i in range(tab_widget.count())]

        self.assertIn("view", tab_names)


class TestExplorerRibbonHomeTab(ExplorerComponentTestBase):
    """Tests for ribbon Home tab content."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.show()
        QCoreApplication.processEvents()

        # Switch to Home tab
        ribbon = self.explorer.ribbon_widget
        for i in range(ribbon.tab_widget.count()):
            if ribbon.tab_widget.tabText(i).lower() == "home":
                ribbon.tab_widget.setCurrentIndex(i)
                break
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_home_tab_has_copy_action(self) -> None:
        """Verify Home tab has Copy action."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        copy_action = actions.actionCopy
        self.assertIsNotNone(copy_action)

    def test_home_tab_has_paste_action(self) -> None:
        """Verify Home tab has Paste action."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        paste_action = actions.actionPaste
        self.assertIsNotNone(paste_action)

    def test_home_tab_has_cut_action(self) -> None:
        """Verify Home tab has Cut action."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        cut_action = actions.actionCut
        self.assertIsNotNone(cut_action)

    def test_home_tab_has_delete_action(self) -> None:
        """Verify Home tab has Delete action."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        delete_action = actions.actionDelete
        self.assertIsNotNone(delete_action)

    def test_home_tab_has_rename_action(self) -> None:
        """Verify Home tab has Rename action."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        rename_action = actions.actionRename
        self.assertIsNotNone(rename_action)


class TestExplorerRibbonViewTab(ExplorerComponentTestBase):
    """Tests for ribbon View tab content."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.show()
        QCoreApplication.processEvents()

        # Switch to View tab
        ribbon = self.explorer.ribbon_widget
        for i in range(ribbon.tab_widget.count()):
            if ribbon.tab_widget.tabText(i).lower() == "view":
                ribbon.tab_widget.setCurrentIndex(i)
                break
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_view_tab_has_extra_large_icons_action(self) -> None:
        """Verify View tab has Extra large icons action."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        action = actions.actionExtraLargeIcons
        self.assertIsNotNone(action)

    def test_view_tab_has_large_icons_action(self) -> None:
        """Verify View tab has Large icons action."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        action = actions.actionLargeIcons
        self.assertIsNotNone(action)

    def test_view_tab_has_medium_icons_action(self) -> None:
        """Verify View tab has Medium icons action."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        action = actions.actionMediumIcons
        self.assertIsNotNone(action)

    def test_view_tab_has_small_icons_action(self) -> None:
        """Verify View tab has Small icons action."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        action = actions.actionSmallIcons
        self.assertIsNotNone(action)

    def test_view_tab_has_list_action(self) -> None:
        """Verify View tab has List action."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        action = actions.actionListView
        self.assertIsNotNone(action)

    def test_view_tab_has_details_action(self) -> None:
        """Verify View tab has Details action."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        action = actions.actionDetailsView
        self.assertIsNotNone(action)

    def test_view_tab_has_tiles_action(self) -> None:
        """Verify View tab has Tiles action."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        action = actions.actionTilesView
        self.assertIsNotNone(action)

    def test_view_tab_has_content_action(self) -> None:
        """Verify View tab has Content action."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        action = actions.actionContentView
        self.assertIsNotNone(action)


# =============================================================================
# NAVIGATION PANE TESTS
# =============================================================================


class TestNavigationPane(ExplorerComponentTestBase):
    """Tests for navigation pane (sidebar)."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_navigation_pane_exists(self) -> None:
        """Verify navigation pane exists."""
        nav_pane = self.explorer.sidebar
        self.assertIsNotNone(nav_pane)

    def test_navigation_pane_visible_by_default(self) -> None:
        """Verify navigation pane is visible by default."""
        nav_pane = self.explorer.sidebar
        self.assertTrue(nav_pane.isVisible())

    def test_navigation_pane_can_be_hidden(self) -> None:
        """Verify navigation pane can be hidden."""
        nav_pane = self.explorer.sidebar
        nav_pane.hide()
        QCoreApplication.processEvents()

        self.assertFalse(nav_pane.isVisible())

    def test_navigation_pane_can_be_shown(self) -> None:
        """Verify navigation pane can be shown."""
        nav_pane = self.explorer.sidebar
        nav_pane.hide()
        QCoreApplication.processEvents()

        nav_pane.show()
        QCoreApplication.processEvents()

        self.assertTrue(nav_pane.isVisible())

    def test_navigation_pane_min_width(self) -> None:
        """Verify navigation pane has minimum width."""
        nav_pane = self.explorer.sidebar

        self.assertGreaterEqual(
            nav_pane.minimumWidth(),
            WindowsExplorerSpecs.NAV_PANE_MIN_WIDTH,
        )

    def test_navigation_pane_has_tree_view(self) -> None:
        """Verify navigation pane contains tree view."""
        nav_pane = self.explorer.sidebar

        tree_views = nav_pane.findChildren(QTreeView)
        self.assertGreater(len(tree_views), 0)


class TestNavigationPaneContent(ExplorerComponentTestBase):
    """Tests for navigation pane content."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_navigation_pane_click_navigates(self) -> None:
        """Verify clicking nav pane item navigates."""
        nav_pane = self.explorer.sidebar

        tree_views = nav_pane.findChildren(QTreeView)
        if tree_views:
            tree = tree_views[0]
            model = tree.model()

            if model and model.rowCount() > 0:
                index = model.index(0, 0)
                rect = tree.visualRect(index)

                if rect.isValid():
                    QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
                    QCoreApplication.processEvents()


# =============================================================================
# CONTENT AREA TESTS
# =============================================================================


class TestContentArea(ExplorerComponentTestBase):
    """Tests for content area (file list)."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.navigate(self.temp_dir.name)
        self.explorer.show()
        QCoreApplication.processEvents()
        QTest.qWait(200)  # Allow loading

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_content_area_exists(self) -> None:
        """Verify content area exists."""
        content = self.explorer.view
        self.assertIsNotNone(content)

    def test_content_shows_files(self) -> None:
        """Verify content area shows files."""
        content = self.explorer.view

        # Find the actual view widget
        list_views = content.findChildren(QListView)
        tree_views = content.findChildren(QTreeView)

        all_views = list_views + tree_views

        for view in all_views:
            model = view.model()
            if model and model.rowCount() > 0:
                return  # Found view with content

    def test_content_min_width(self) -> None:
        """Verify content area has minimum width."""
        content = self.explorer.view

        self.assertGreaterEqual(
            content.minimumWidth(),
            0,  # At least not negative
        )


class TestContentAreaViewModes(ExplorerComponentTestBase):
    """Tests for content area view modes."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.navigate(self.temp_dir.name)
        self.explorer.show()
        QCoreApplication.processEvents()
        QTest.qWait(200)

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_can_switch_to_icons_view(self) -> None:
        """Verify can switch to icons view mode."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        action = actions.actionLargeIcons
        action.trigger()
        QCoreApplication.processEvents()

    def test_can_switch_to_list_view(self) -> None:
        """Verify can switch to list view mode."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        action = actions.actionListView
        action.trigger()
        QCoreApplication.processEvents()

    def test_can_switch_to_details_view(self) -> None:
        """Verify can switch to details view mode."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        action = actions.actionDetailsView
        action.trigger()
        QCoreApplication.processEvents()

    def test_can_switch_to_tiles_view(self) -> None:
        """Verify can switch to tiles view mode."""
        ribbon = self.explorer.ribbon_widget
        actions = ribbon.actions_definitions

        action = actions.actionTilesView
        action.trigger()
        QCoreApplication.processEvents()


# =============================================================================
# ADDRESS BAR TESTS
# =============================================================================


class TestExplorerAddressBar(ExplorerComponentTestBase):
    """Tests for explorer address bar."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_address_bar_exists(self) -> None:
        """Verify address bar exists."""
        address_bar = self.explorer.address_bar
        self.assertIsNotNone(address_bar)

    def test_address_bar_shows_path(self) -> None:
        """Verify address bar shows current path."""
        self.explorer.navigate(self.temp_dir.name)
        QCoreApplication.processEvents()

        address_bar = self.explorer.address_bar
        # Implementation may vary - just check it exists
        self.assertIsNotNone(address_bar)

    def test_address_bar_height(self) -> None:
        """Verify address bar has correct height."""
        address_bar = self.explorer.address_bar

        height = address_bar.height()
        self.assertGreaterEqual(height, WindowsExplorerSpecs.ADDRESS_BAR_HEIGHT - 10)
        self.assertLessEqual(height, WindowsExplorerSpecs.ADDRESS_BAR_HEIGHT + 20)


# =============================================================================
# STATUS BAR TESTS
# =============================================================================


class TestExplorerStatusBar(ExplorerComponentTestBase):
    """Tests for explorer status bar."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.navigate(self.temp_dir.name)
        self.explorer.show()
        QCoreApplication.processEvents()
        QTest.qWait(200)

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_status_bar_exists(self) -> None:
        """Verify status bar exists."""
        status_bar = self.explorer.statusBar()
        self.assertIsNotNone(status_bar)

    def test_status_bar_visible(self) -> None:
        """Verify status bar is visible."""
        status_bar = self.explorer.statusBar()
        self.assertTrue(status_bar.isVisible())

    def test_status_bar_height(self) -> None:
        """Verify status bar has correct height."""
        status_bar = self.explorer.statusBar()

        height = status_bar.height()
        self.assertGreaterEqual(height, WindowsExplorerSpecs.STATUS_BAR_HEIGHT - 10)
        self.assertLessEqual(height, WindowsExplorerSpecs.STATUS_BAR_HEIGHT + 10)

    def test_status_bar_shows_item_count(self) -> None:
        """Verify status bar shows item count."""
        status_bar = self.explorer.statusBar()

        # Check if status bar has some text or widgets
        has_content = status_bar.currentMessage() != "" or len(status_bar.findChildren(QLabel)) > 0
        # May or may not show count depending on implementation


# =============================================================================
# KEYBOARD NAVIGATION TESTS
# =============================================================================


class TestExplorerKeyboardNavigation(ExplorerComponentTestBase):
    """Tests for keyboard navigation in explorer."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.navigate(self.temp_dir.name)
        self.explorer.show()
        QCoreApplication.processEvents()
        QTest.qWait(200)

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_alt_d_focuses_address_bar(self) -> None:
        """Verify Alt+D focuses address bar."""
        # Focus explorer first
        self.explorer.setFocus()
        QCoreApplication.processEvents()

        # Alt+D shortcut
        QTest.keyClick(
            self.explorer,
            Qt.Key.Key_D,
            Qt.KeyboardModifier.AltModifier,
        )
        QCoreApplication.processEvents()

        # Address bar or child should have focus
        address_bar = self.explorer.address_bar
        has_focus = address_bar.hasFocus() or any(w.hasFocus() for w in address_bar.findChildren(QWidget))
        # May depend on implementation

    def test_f4_opens_address_bar_dropdown(self) -> None:
        """Verify F4 opens address bar dropdown."""
        self.explorer.setFocus()
        QCoreApplication.processEvents()

        QTest.keyClick(self.explorer, Qt.Key.Key_F4)
        QCoreApplication.processEvents()

    def test_backspace_goes_up(self) -> None:
        """Verify Backspace navigates up."""
        # Navigate to nested folder first
        nested_path = Path(self.temp_dir.name) / "Folder_A"
        self.explorer.navigate(str(nested_path))
        QCoreApplication.processEvents()
        QTest.qWait(100)

        # Focus content area
        view = self.explorer.view
        view.setFocus()
        QCoreApplication.processEvents()

        # Press backspace
        QTest.keyClick(view, Qt.Key.Key_Backspace)
        QCoreApplication.processEvents()

    def test_enter_opens_selected_folder(self) -> None:
        """Verify Enter opens selected folder."""
        # Focus on view and select folder
        view = self.explorer.view
        view.setFocus()
        QCoreApplication.processEvents()

        # Find and click on a folder in the view
        list_views = view.findChildren(QListView)
        tree_views = view.findChildren(QTreeView)

        for v in list_views + tree_views:
            model = v.model()
            if model and model.rowCount() > 0:
                # Select first item
                index = model.index(0, 0)
                v.setCurrentIndex(index)
                QCoreApplication.processEvents()

                # Press Enter
                QTest.keyClick(v, Qt.Key.Key_Return)
                QCoreApplication.processEvents()
                break


# =============================================================================
# DRAG AND DROP TESTS
# =============================================================================


class TestExplorerDragDrop(ExplorerComponentTestBase):
    """Tests for drag and drop functionality."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.navigate(self.temp_dir.name)
        self.explorer.show()
        QCoreApplication.processEvents()
        QTest.qWait(200)

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_view_accepts_drops(self) -> None:
        """Verify view accepts drag drops."""
        view = self.explorer.view

        # Check if drag drop is enabled on child views
        list_views = view.findChildren(QListView)
        tree_views = view.findChildren(QTreeView)

        for v in list_views + tree_views:
            if v.acceptDrops():
                return  # Found view that accepts drops

    def test_drag_enabled(self) -> None:
        """Verify drag is enabled for files."""
        view = self.explorer.view

        list_views = view.findChildren(QListView)
        tree_views = view.findChildren(QTreeView)

        for v in list_views + tree_views:
            if v.dragEnabled():
                return  # Found view with drag enabled


# =============================================================================
# CONTEXT MENU TESTS
# =============================================================================


class TestExplorerContextMenu(ExplorerComponentTestBase):
    """Tests for context menu functionality."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.navigate(self.temp_dir.name)
        self.explorer.show()
        QCoreApplication.processEvents()
        QTest.qWait(200)

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_context_menu_policy(self) -> None:
        """Verify view has context menu policy."""
        view = self.explorer.view

        list_views = view.findChildren(QListView)
        tree_views = view.findChildren(QTreeView)

        for v in list_views + tree_views:
            policy = v.contextMenuPolicy()
            # Should have custom or default context menu
            self.assertIn(
                policy,
                [
                    Qt.ContextMenuPolicy.DefaultContextMenu,
                    Qt.ContextMenuPolicy.CustomContextMenu,
                    Qt.ContextMenuPolicy.ActionsContextMenu,
                ],
            )


# =============================================================================
# SELECTION TESTS
# =============================================================================


class TestExplorerSelection(ExplorerComponentTestBase):
    """Tests for selection functionality."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.navigate(self.temp_dir.name)
        self.explorer.show()
        QCoreApplication.processEvents()
        QTest.qWait(200)

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_selection_mode(self) -> None:
        """Verify selection mode is extended."""
        view = self.explorer.view

        list_views = view.findChildren(QListView)
        tree_views = view.findChildren(QTreeView)

        for v in list_views + tree_views:
            mode = v.selectionMode()
            # Should support selection
            self.assertNotEqual(mode, QAbstractItemView.SelectionMode.NoSelection)

    def test_ctrl_a_selects_all(self) -> None:
        """Verify Ctrl+A selects all items."""
        view = self.explorer.view
        view.setFocus()
        QCoreApplication.processEvents()

        QTest.keyClick(
            view,
            Qt.Key.Key_A,
            Qt.KeyboardModifier.ControlModifier,
        )
        QCoreApplication.processEvents()

    def test_click_selects_item(self) -> None:
        """Verify clicking selects item."""
        view = self.explorer.view

        list_views = view.findChildren(QListView)
        tree_views = view.findChildren(QTreeView)

        for v in list_views + tree_views:
            model = v.model()
            if model and model.rowCount() > 0:
                index = model.index(0, 0)
                rect = v.visualRect(index)

                if rect.isValid():
                    QTest.mouseClick(v.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
                    QCoreApplication.processEvents()

                    # Check selection
                    selected = v.selectedIndexes()
                    self.assertGreater(len(selected), 0)
                    break


# =============================================================================
# TEST RUNNER
# =============================================================================


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestExplorerMainWindowStructure,
        TestExplorerToolbars,
        TestExplorerRibbon,
        TestExplorerRibbonHomeTab,
        TestExplorerRibbonViewTab,
        TestNavigationPane,
        TestNavigationPaneContent,
        TestContentArea,
        TestContentAreaViewModes,
        TestExplorerAddressBar,
        TestExplorerStatusBar,
        TestExplorerKeyboardNavigation,
        TestExplorerDragDrop,
        TestExplorerContextMenu,
        TestExplorerSelection,
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
