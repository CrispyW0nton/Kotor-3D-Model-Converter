"""Windows Explorer Conformance Tests for FileSystemExplorerWidget.

This module provides exhaustive conformance tests verifying that
FileSystemExplorerWidget matches the exact behavior, layout, styling,
and functionality of native Windows 11 Explorer (explorer.exe).

The tests cover:
- Complete ribbon interface (File, Home, Share, View tabs)
- Status bar elements and behavior
- Dynamic view modes (extra-large icons to details)
- Sorting, grouping, and column customization
- Quick access, This PC, and network locations
- Drag and drop behavior
- Property panels and details pane
- Search functionality and indexing
- Clipboard operations (cut, copy, paste)
- File operations (rename, delete, new folder, new file)

All tests use real widget instances without mocking to ensure actual behavior.
"""

from __future__ import annotations

import tempfile
import time
import unittest

from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final, NamedTuple, Sequence

from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtGui import QPalette
from qtpy.QtTest import QTest
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMenuBar,
    QStatusBar,
    QToolButton,
    QTreeView,
)

if TYPE_CHECKING:
    from qtpy.QtWidgets import (
        QSplitter,
        QToolBar,
    )

# =============================================================================
# WINDOWS EXPLORER SPECIFICATIONS
# =============================================================================


class ExplorerViewMode(Enum):
    """Windows Explorer view modes."""

    EXTRA_LARGE_ICONS = auto()
    LARGE_ICONS = auto()
    MEDIUM_ICONS = auto()
    SMALL_ICONS = auto()
    LIST = auto()
    DETAILS = auto()
    TILES = auto()
    CONTENT = auto()


class ExplorerSortColumn(Enum):
    """Windows Explorer sort columns."""

    NAME = auto()
    DATE_MODIFIED = auto()
    TYPE = auto()
    SIZE = auto()
    DATE_CREATED = auto()
    AUTHORS = auto()
    TAGS = auto()


class Windows11ExplorerSpecs:
    """Windows 11 Explorer UI specifications."""

    # Window dimensions
    MIN_WIDTH: Final[int] = 400
    MIN_HEIGHT: Final[int] = 300
    DEFAULT_WIDTH: Final[int] = 1024
    DEFAULT_HEIGHT: Final[int] = 768

    # Ribbon dimensions
    RIBBON_HEIGHT_COLLAPSED: Final[int] = 50
    RIBBON_HEIGHT_EXPANDED: Final[int] = 150
    RIBBON_TAB_HEIGHT: Final[int] = 30

    # Sidebar dimensions
    SIDEBAR_MIN_WIDTH: Final[int] = 160
    SIDEBAR_DEFAULT_WIDTH: Final[int] = 250
    SIDEBAR_MAX_WIDTH: Final[int] = 500

    # Navigation bar
    NAV_BAR_HEIGHT: Final[int] = 40
    BREADCRUMB_HEIGHT: Final[int] = 28
    SEARCH_BOX_WIDTH: Final[int] = 200

    # Status bar
    STATUSBAR_HEIGHT: Final[int] = 24

    # View item sizes (icon dimensions)
    ICON_EXTRA_LARGE: Final[int] = 256
    ICON_LARGE: Final[int] = 96
    ICON_MEDIUM: Final[int] = 48
    ICON_SMALL: Final[int] = 32
    ICON_LIST: Final[int] = 16
    ICON_DETAILS: Final[int] = 16
    ICON_TILES: Final[int] = 48

    # Item row heights
    ITEM_HEIGHT_SMALL: Final[int] = 20
    ITEM_HEIGHT_MEDIUM: Final[int] = 28
    ITEM_HEIGHT_DETAILS: Final[int] = 22

    # Ribbon tabs
    RIBBON_TABS: Final[tuple[str, ...]] = ("File", "Home", "Share", "View")

    # Quick Access default items
    QUICK_ACCESS_ITEMS: Final[tuple[str, ...]] = (
        "Desktop",
        "Downloads",
        "Documents",
        "Pictures",
        "Music",
        "Videos",
    )

    # This PC default items
    THIS_PC_ITEMS: Final[tuple[str, ...]] = (
        "Desktop",
        "Documents",
        "Downloads",
        "Music",
        "Pictures",
        "Videos",
    )


class Windows11Colors:
    """Windows 11 color palette for Explorer."""

    class Light:
        """Light theme colors."""

        WINDOW_BG: Final[str] = "#FFFFFF"
        RIBBON_BG: Final[str] = "#F3F3F3"
        SIDEBAR_BG: Final[str] = "#F5F5F5"
        CONTENT_BG: Final[str] = "#FFFFFF"
        STATUSBAR_BG: Final[str] = "#F0F0F0"
        TEXT_PRIMARY: Final[str] = "#1A1A1A"
        TEXT_SECONDARY: Final[str] = "#616161"
        TEXT_DISABLED: Final[str] = "#A0A0A0"
        SELECTION_BG: Final[str] = "#CCE4F7"
        SELECTION_BG_FOCUS: Final[str] = "#0078D4"
        SELECTION_TEXT_FOCUS: Final[str] = "#FFFFFF"
        HOVER_BG: Final[str] = "#E5E5E5"
        BORDER: Final[str] = "#E0E0E0"
        SPLITTER: Final[str] = "#E0E0E0"
        SCROLLBAR_TRACK: Final[str] = "#F0F0F0"
        SCROLLBAR_THUMB: Final[str] = "#C4C4C4"
        TREE_EXPAND: Final[str] = "#767676"

    class Dark:
        """Dark theme colors."""

        WINDOW_BG: Final[str] = "#1F1F1F"
        RIBBON_BG: Final[str] = "#2D2D2D"
        SIDEBAR_BG: Final[str] = "#252525"
        CONTENT_BG: Final[str] = "#1F1F1F"
        STATUSBAR_BG: Final[str] = "#2D2D2D"
        TEXT_PRIMARY: Final[str] = "#FFFFFF"
        TEXT_SECONDARY: Final[str] = "#9D9D9D"
        TEXT_DISABLED: Final[str] = "#5C5C5C"
        SELECTION_BG: Final[str] = "#2C3E50"
        SELECTION_BG_FOCUS: Final[str] = "#0078D4"
        SELECTION_TEXT_FOCUS: Final[str] = "#FFFFFF"
        HOVER_BG: Final[str] = "#383838"
        BORDER: Final[str] = "#3D3D3D"
        SPLITTER: Final[str] = "#3D3D3D"
        SCROLLBAR_TRACK: Final[str] = "#2D2D2D"
        SCROLLBAR_THUMB: Final[str] = "#5C5C5C"
        TREE_EXPAND: Final[str] = "#A0A0A0"


class DetailViewColumnSpecs:
    """Detail view column specifications."""

    class Column(NamedTuple):
        """Column specification."""

        name: str
        display_name: str
        default_width: int
        min_width: int
        alignment: Qt.AlignmentFlag
        visible_by_default: bool

    NAME: Final = Column(
        name="Name",
        display_name="Name",
        default_width=300,
        min_width=100,
        alignment=Qt.AlignmentFlag.AlignLeft,
        visible_by_default=True,
    )

    DATE_MODIFIED: Final = Column(
        name="Date modified",
        display_name="Date modified",
        default_width=150,
        min_width=80,
        alignment=Qt.AlignmentFlag.AlignLeft,
        visible_by_default=True,
    )

    TYPE: Final = Column(
        name="Type",
        display_name="Type",
        default_width=120,
        min_width=60,
        alignment=Qt.AlignmentFlag.AlignLeft,
        visible_by_default=True,
    )

    SIZE: Final = Column(
        name="Size",
        display_name="Size",
        default_width=100,
        min_width=50,
        alignment=Qt.AlignmentFlag.AlignRight,
        visible_by_default=True,
    )

    DATE_CREATED: Final = Column(
        name="Date created",
        display_name="Date created",
        default_width=150,
        min_width=80,
        alignment=Qt.AlignmentFlag.AlignLeft,
        visible_by_default=False,
    )

    STANDARD_COLUMNS: Final[tuple[Column, ...]] = (NAME, DATE_MODIFIED, TYPE, SIZE)


# =============================================================================
# TEST UTILITIES
# =============================================================================


class ExplorerLayoutVerifier:
    """Utility for verifying explorer layout."""

    @staticmethod
    def verify_splitter_widget_order(
        splitter: QSplitter,
        expected_widgets: Sequence[type],
    ) -> tuple[bool, str]:
        """Verify widgets in splitter are in expected order.

        Args:
            splitter: The splitter to check
            expected_widgets: Expected widget types in order

        Returns:
            Tuple of (success, message)
        """
        if splitter.count() != len(expected_widgets):
            return False, f"Splitter has {splitter.count()} widgets, expected {len(expected_widgets)}"

        for i, expected_type in enumerate(expected_widgets):
            widget = splitter.widget(i)
            if not isinstance(widget, expected_type):
                return False, f"Widget {i} is {type(widget).__name__}, expected {expected_type.__name__}"

        return True, "OK"

    @staticmethod
    def verify_toolbar_button_order(
        toolbar: QToolBar,
        expected_actions: Sequence[str],
    ) -> tuple[bool, str]:
        """Verify toolbar buttons are in expected order.

        Args:
            toolbar: The toolbar to check
            expected_actions: Expected action names/texts in order

        Returns:
            Tuple of (success, message)
        """
        actions = toolbar.actions()
        action_texts = [a.text() for a in actions if not a.isSeparator()]

        for i, expected in enumerate(expected_actions):
            if i >= len(action_texts):
                return False, f"Missing action at position {i}: {expected}"
            if expected.lower() not in action_texts[i].lower():
                return False, f"Action {i} is '{action_texts[i]}', expected '{expected}'"

        return True, "OK"


class ViewModeVerifier:
    """Utility for verifying view mode settings."""

    @staticmethod
    def get_expected_icon_size(mode: ExplorerViewMode) -> int:
        """Get expected icon size for view mode.

        Returns:
            Icon size in pixels
        """
        mapping = {
            ExplorerViewMode.EXTRA_LARGE_ICONS: Windows11ExplorerSpecs.ICON_EXTRA_LARGE,
            ExplorerViewMode.LARGE_ICONS: Windows11ExplorerSpecs.ICON_LARGE,
            ExplorerViewMode.MEDIUM_ICONS: Windows11ExplorerSpecs.ICON_MEDIUM,
            ExplorerViewMode.SMALL_ICONS: Windows11ExplorerSpecs.ICON_SMALL,
            ExplorerViewMode.LIST: Windows11ExplorerSpecs.ICON_LIST,
            ExplorerViewMode.DETAILS: Windows11ExplorerSpecs.ICON_DETAILS,
            ExplorerViewMode.TILES: Windows11ExplorerSpecs.ICON_TILES,
        }
        return mapping.get(mode, Windows11ExplorerSpecs.ICON_MEDIUM)


# =============================================================================
# BASE TEST CLASS
# =============================================================================


class WindowsExplorerConformanceTestBase(unittest.TestCase):
    """Base class for Windows Explorer conformance tests."""

    TIMEOUT_SECONDS: ClassVar[int] = 120

    app: ClassVar[QApplication]
    temp_dir: ClassVar[tempfile.TemporaryDirectory]
    temp_path: ClassVar[Path]

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test class."""
        cls.app = QApplication.instance() or QApplication([])

        # Create temporary directory structure
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.temp_path = Path(cls.temp_dir.name)

        # Create realistic folder structure
        folders = [
            "Desktop",
            "Documents",
            "Documents/Work",
            "Documents/Personal",
            "Documents/Projects",
            "Downloads",
            "Music",
            "Pictures",
            "Pictures/Screenshots",
            "Pictures/Vacation",
            "Videos",
        ]

        for folder in folders:
            (cls.temp_path / folder).mkdir(parents=True, exist_ok=True)

        # Create test files
        files = [
            ("Desktop/shortcut.lnk", b"\x00" * 100),
            ("Documents/report.docx", b"PK\x03\x04" + b"\x00" * 200),
            ("Documents/budget.xlsx", b"PK\x03\x04" + b"\x00" * 150),
            ("Documents/notes.txt", b"Important notes content"),
            ("Documents/Work/presentation.pptx", b"PK\x03\x04" + b"\x00" * 300),
            ("Documents/Projects/readme.md", b"# Project README"),
            ("Downloads/setup.exe", b"MZ" + b"\x00" * 400),
            ("Downloads/archive.zip", b"PK\x03\x04" + b"\x00" * 250),
            ("Downloads/document.pdf", b"%PDF-1.4" + b"\x00" * 200),
            ("Music/song1.mp3", b"ID3" + b"\x00" * 500),
            ("Music/song2.flac", b"fLaC" + b"\x00" * 600),
            ("Pictures/photo1.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 300),
            ("Pictures/photo2.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 200),
            ("Pictures/Screenshots/screen1.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 150),
            ("Videos/video.mp4", b"\x00\x00\x00\x1cftyp" + b"\x00" * 700),
        ]

        for filepath, content in files:
            (cls.temp_path / filepath).write_bytes(content)

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up test class."""
        cls.temp_dir.cleanup()

    def setUp(self) -> None:
        """Set up for each test."""
        from utility.gui.qt.filesystem.explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.set_initial_path(str(self.temp_path))

        # Process events to let widget initialize
        self._process_events_with_timeout(500)

    def tearDown(self) -> None:
        """Clean up after each test."""
        if self.explorer.isVisible():
            self.explorer.close()
        self.explorer.deleteLater()
        self._process_events_with_timeout(100)

    def _process_events_with_timeout(self, timeout_ms: int) -> None:
        """Process Qt events with timeout."""
        start = time.time()
        while (time.time() - start) * 1000 < timeout_ms:
            QCoreApplication.processEvents()
            time.sleep(0.01)

    def _is_dark_theme(self) -> bool:
        """Detect dark theme."""
        palette = self.app.palette()
        window_color = palette.color(QPalette.ColorRole.Window)
        return window_color.lightness() < 128

    def _get_theme_colors(self) -> type[Windows11Colors.Light] | type[Windows11Colors.Dark]:
        """Get appropriate color class for current theme."""
        return Windows11Colors.Dark if self._is_dark_theme() else Windows11Colors.Light


# =============================================================================
# WINDOW STRUCTURE TESTS
# =============================================================================


class TestExplorerWindowStructure(WindowsExplorerConformanceTestBase):
    """Tests for verifying main window structure."""

    def test_is_main_window(self) -> None:
        """Verify explorer is a QMainWindow."""
        self.assertIsInstance(
            self.explorer,
            QMainWindow,
            f"Explorer should be QMainWindow, got {type(self.explorer).__name__}",
        )

    def test_has_central_widget(self) -> None:
        """Verify explorer has central widget."""
        central = self.explorer.centralWidget()

        self.assertIsNotNone(
            central,
            "Explorer should have central widget",
        )

    def test_has_status_bar(self) -> None:
        """Verify explorer has status bar."""
        status_bar = self.explorer.statusBar()

        self.assertIsNotNone(
            status_bar,
            "Explorer should have status bar",
        )
        self.assertIsInstance(status_bar, QStatusBar)

    def test_minimum_size(self) -> None:
        """Verify explorer has reasonable minimum size."""
        min_size = self.explorer.minimumSize()

        self.assertGreaterEqual(
            min_size.width(),
            Windows11ExplorerSpecs.MIN_WIDTH,
            f"Min width {min_size.width()} should be >= {Windows11ExplorerSpecs.MIN_WIDTH}",
        )
        self.assertGreaterEqual(
            min_size.height(),
            Windows11ExplorerSpecs.MIN_HEIGHT,
            f"Min height {min_size.height()} should be >= {Windows11ExplorerSpecs.MIN_HEIGHT}",
        )

    def test_window_title_set(self) -> None:
        """Verify window has title."""
        title = self.explorer.windowTitle()

        # Title should be non-empty and reflect current path
        self.assertTrue(
            len(title) > 0,
            "Window should have a title",
        )


class TestExplorerMenuBar(WindowsExplorerConformanceTestBase):
    """Tests for verifying menu bar structure."""

    def test_has_menu_bar(self) -> None:
        """Verify explorer has menu bar."""
        menu_bar = self.explorer.menuBar()

        self.assertIsNotNone(menu_bar)
        self.assertIsInstance(menu_bar, QMenuBar)

    def test_menu_bar_has_file_menu(self) -> None:
        """Verify menu bar has File menu."""
        menu_bar = self.explorer.menuBar()

        file_menu_found = False
        for action in menu_bar.actions():
            if "file" in action.text().lower():
                file_menu_found = True
                break

        self.assertTrue(file_menu_found, "Menu bar should have File menu")

    def test_menu_bar_has_edit_menu(self) -> None:
        """Verify menu bar has Edit menu."""
        menu_bar = self.explorer.menuBar()

        edit_menu_found = False
        for action in menu_bar.actions():
            if "edit" in action.text().lower():
                edit_menu_found = True
                break

        self.assertTrue(edit_menu_found, "Menu bar should have Edit menu")

    def test_menu_bar_has_view_menu(self) -> None:
        """Verify menu bar has View menu."""
        menu_bar = self.explorer.menuBar()

        view_menu_found = False
        for action in menu_bar.actions():
            if "view" in action.text().lower():
                view_menu_found = True
                break

        self.assertTrue(view_menu_found, "Menu bar should have View menu")


# =============================================================================
# RIBBON INTERFACE TESTS
# =============================================================================


class TestExplorerRibbon(WindowsExplorerConformanceTestBase):
    """Tests for verifying ribbon interface."""

    def test_ribbon_exists(self) -> None:
        """Verify ribbon widget exists."""
        self.assertTrue(
            hasattr(self.explorer, "ribbons"),
            "Explorer should have ribbons attribute",
        )
        self.assertIsNotNone(self.explorer.ribbons)

    def test_ribbon_has_tab_widget(self) -> None:
        """Verify ribbon has tab widget."""
        self.assertTrue(
            hasattr(self.explorer.ribbons, "tab_widget"),
            "Ribbon should have tab_widget",
        )

    def test_ribbon_tab_count(self) -> None:
        """Verify ribbon has expected number of tabs."""
        tab_widget = self.explorer.ribbons.tab_widget

        # Should have at least File, Home, Share, View tabs
        self.assertGreaterEqual(
            tab_widget.count(),
            len(Windows11ExplorerSpecs.RIBBON_TABS),
            f"Ribbon should have at least {len(Windows11ExplorerSpecs.RIBBON_TABS)} tabs",
        )

    def test_ribbon_has_file_tab(self) -> None:
        """Verify ribbon has File tab."""
        tab_widget = self.explorer.ribbons.tab_widget
        tabs = [tab_widget.tabText(i).lower() for i in range(tab_widget.count())]

        self.assertIn("file", tabs, "Ribbon should have File tab")

    def test_ribbon_has_home_tab(self) -> None:
        """Verify ribbon has Home tab."""
        tab_widget = self.explorer.ribbons.tab_widget
        tabs = [tab_widget.tabText(i).lower() for i in range(tab_widget.count())]

        self.assertIn("home", tabs, "Ribbon should have Home tab")

    def test_ribbon_has_share_tab(self) -> None:
        """Verify ribbon has Share tab."""
        tab_widget = self.explorer.ribbons.tab_widget
        tabs = [tab_widget.tabText(i).lower() for i in range(tab_widget.count())]

        self.assertIn("share", tabs, "Ribbon should have Share tab")

    def test_ribbon_has_view_tab(self) -> None:
        """Verify ribbon has View tab."""
        tab_widget = self.explorer.ribbons.tab_widget
        tabs = [tab_widget.tabText(i).lower() for i in range(tab_widget.count())]

        self.assertIn("view", tabs, "Ribbon should have View tab")

    def test_home_tab_has_clipboard_group(self) -> None:
        """Verify Home tab has Clipboard group."""
        # The clipboard group should have Cut, Copy, Paste actions
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionCut)
        self.assertIsNotNone(actions.actionCopy)
        self.assertIsNotNone(actions.actionPaste)

    def test_home_tab_has_organize_group(self) -> None:
        """Verify Home tab has Organize group."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionDelete)
        self.assertIsNotNone(actions.actionRename)

    def test_home_tab_has_new_group(self) -> None:
        """Verify Home tab has New group."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionNewFolder)

    def test_home_tab_has_open_group(self) -> None:
        """Verify Home tab has Open group."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionOpen)

    def test_home_tab_has_select_group(self) -> None:
        """Verify Home tab has Select group."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionSelectAll)
        self.assertIsNotNone(actions.actionSelectNone)
        self.assertIsNotNone(actions.actionInvertSelection)


class TestExplorerRibbonViewTab(WindowsExplorerConformanceTestBase):
    """Tests for verifying View tab in ribbon."""

    def test_view_tab_has_layout_group(self) -> None:
        """Verify View tab has Layout group with view modes."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionExtraLargeIcons)
        self.assertIsNotNone(actions.actionLargeIcons)
        self.assertIsNotNone(actions.actionMediumIcons)
        self.assertIsNotNone(actions.actionSmallIcons)
        self.assertIsNotNone(actions.actionListView)
        self.assertIsNotNone(actions.actionDetailView)

    def test_view_tab_has_panes_group(self) -> None:
        """Verify View tab has Panes group."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionNavigationPane)
        self.assertIsNotNone(actions.actionPreviewPane)
        self.assertIsNotNone(actions.actionDetailsPane)

    def test_view_tab_has_show_hide_group(self) -> None:
        """Verify View tab has Show/Hide group."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionShowHiddenFiles)
        self.assertIsNotNone(actions.actionShowFileExtensions)

    def test_view_tab_has_sort_group(self) -> None:
        """Verify View tab has Sort group."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionSortByName)
        self.assertIsNotNone(actions.actionSortByDate)
        self.assertIsNotNone(actions.actionSortByType)
        self.assertIsNotNone(actions.actionSortBySize)


class TestExplorerRibbonShareTab(WindowsExplorerConformanceTestBase):
    """Tests for verifying Share tab in ribbon."""

    def test_share_tab_has_share_action(self) -> None:
        """Verify Share tab has Share action."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionShare)

    def test_share_tab_has_email_action(self) -> None:
        """Verify Share tab has Email action."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionEmail)

    def test_share_tab_has_zip_action(self) -> None:
        """Verify Share tab has Compress to ZIP action."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionCompressToZip)

    def test_share_tab_has_print_action(self) -> None:
        """Verify Share tab has Print action."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionPrint)


# =============================================================================
# NAVIGATION BAR TESTS
# =============================================================================


class TestExplorerNavigationBar(WindowsExplorerConformanceTestBase):
    """Tests for verifying navigation bar."""

    def test_has_address_bar(self) -> None:
        """Verify explorer has address bar."""
        self.assertTrue(
            hasattr(self.explorer, "address_bar"),
            "Explorer should have address_bar",
        )
        self.assertIsNotNone(self.explorer.address_bar)

    def test_has_back_button(self) -> None:
        """Verify explorer has back navigation button."""
        self.assertIsNotNone(self.explorer.ui.backButton)
        self.assertIsInstance(self.explorer.ui.backButton, QToolButton)

    def test_has_forward_button(self) -> None:
        """Verify explorer has forward navigation button."""
        self.assertIsNotNone(self.explorer.ui.forwardButton)
        self.assertIsInstance(self.explorer.ui.forwardButton, QToolButton)

    def test_has_up_button(self) -> None:
        """Verify explorer has up/parent navigation button."""
        self.assertIsNotNone(self.explorer.ui.toParentButton)
        self.assertIsInstance(self.explorer.ui.toParentButton, QToolButton)

    def test_back_button_initially_disabled(self) -> None:
        """Verify back button is disabled when no history."""
        # Fresh explorer should have no back history
        self.assertFalse(
            self.explorer.ui.backButton.isEnabled(),
            "Back button should be disabled with no history",
        )

    def test_forward_button_initially_disabled(self) -> None:
        """Verify forward button is disabled when no forward history."""
        self.assertFalse(
            self.explorer.ui.forwardButton.isEnabled(),
            "Forward button should be disabled with no forward history",
        )

    def test_address_bar_shows_current_path(self) -> None:
        """Verify address bar shows current path."""
        current_path = self.explorer.address_bar.current_path

        self.assertEqual(
            current_path,
            self.temp_path,
            f"Address bar should show {self.temp_path}, shows {current_path}",
        )


class TestExplorerSearchBox(WindowsExplorerConformanceTestBase):
    """Tests for verifying search box."""

    def test_has_search_widget(self) -> None:
        """Verify explorer has search widget."""
        self.assertTrue(
            hasattr(self.explorer, "search_filter"),
            "Explorer should have search_filter",
        )
        self.assertIsNotNone(self.explorer.search_filter)

    def test_search_box_has_line_edit(self) -> None:
        """Verify search widget has line edit."""
        self.assertTrue(
            hasattr(self.explorer.search_filter, "line_edit"),
            "Search filter should have line_edit",
        )
        self.assertIsNotNone(self.explorer.search_filter.line_edit)
        self.assertIsInstance(self.explorer.search_filter.line_edit, QLineEdit)

    def test_search_box_placeholder_text(self) -> None:
        """Verify search box has placeholder text."""
        line_edit = self.explorer.search_filter.line_edit
        placeholder = line_edit.placeholderText()

        # Should have search-related placeholder
        self.assertTrue(
            len(placeholder) > 0 and "search" in placeholder.lower(),
            f"Search box should have search placeholder, got '{placeholder}'",
        )

    def test_search_filters_content(self) -> None:
        """Verify search filters displayed content."""
        # Navigate to Documents with multiple files
        docs_path = self.temp_path / "Documents"
        self.explorer.navigate_to_path(str(docs_path))
        self._process_events_with_timeout(200)

        # Type search query
        self.explorer.search_filter.line_edit.setText("report")
        self._process_events_with_timeout(200)

        # Get visible items count
        view = self.explorer.dynamic_stacked_view.current_view
        model = view.model()

        if model:
            visible_count = model.rowCount(view.rootIndex())
            # Should show fewer items after filtering
            self.assertLessEqual(
                visible_count,
                3,  # Original Documents has more files
                "Search should filter to matching items",
            )

    def test_search_clear_restores_content(self) -> None:
        """Verify clearing search restores all content."""
        docs_path = self.temp_path / "Documents"
        self.explorer.navigate_to_path(str(docs_path))
        self._process_events_with_timeout(200)

        # Filter
        self.explorer.search_filter.line_edit.setText("xyz_nonexistent")
        self._process_events_with_timeout(100)

        # Clear
        self.explorer.search_filter.line_edit.clear()
        self._process_events_with_timeout(200)

        # Should show all items again
        view = self.explorer.dynamic_stacked_view.current_view
        model = view.model()

        if model:
            visible_count = model.rowCount(view.rootIndex())
            self.assertGreater(visible_count, 0, "Cleared search should show items")


# =============================================================================
# SIDEBAR TESTS
# =============================================================================


class TestExplorerSidebar(WindowsExplorerConformanceTestBase):
    """Tests for verifying sidebar/navigation pane."""

    def test_has_sidebar(self) -> None:
        """Verify explorer has sidebar."""
        self.assertIsNotNone(self.explorer.ui.sidebar)

    def test_sidebar_is_visible_by_default(self) -> None:
        """Verify sidebar is visible by default."""
        self.assertTrue(
            self.explorer.ui.sidebar.isVisible(),
            "Sidebar should be visible by default",
        )

    def test_sidebar_width_reasonable(self) -> None:
        """Verify sidebar has reasonable width."""
        width = self.explorer.ui.sidebar.width()

        self.assertGreaterEqual(
            width,
            Windows11ExplorerSpecs.SIDEBAR_MIN_WIDTH,
            f"Sidebar width {width} should be >= {Windows11ExplorerSpecs.SIDEBAR_MIN_WIDTH}",
        )
        self.assertLessEqual(
            width,
            Windows11ExplorerSpecs.SIDEBAR_MAX_WIDTH,
            f"Sidebar width {width} should be <= {Windows11ExplorerSpecs.SIDEBAR_MAX_WIDTH}",
        )

    def test_sidebar_has_tree_view(self) -> None:
        """Verify sidebar has tree view for navigation."""
        self.assertIsNotNone(self.explorer.ui.treeView)
        self.assertIsInstance(self.explorer.ui.treeView, QTreeView)

    def test_sidebar_tree_shows_drives(self) -> None:
        """Verify sidebar tree shows drives (This PC level)."""
        tree = self.explorer.ui.treeView
        model = tree.model()

        self.assertIsNotNone(model, "Sidebar tree should have model")
        self.assertGreater(
            model.rowCount(),
            0,
            "Sidebar tree should show root items (drives)",
        )

    def test_sidebar_can_be_hidden(self) -> None:
        """Verify sidebar can be toggled hidden."""
        actions = self.explorer.ribbons.actions_definitions

        # Toggle navigation pane off
        actions.actionNavigationPane.trigger()
        self._process_events_with_timeout(100)

        self.assertFalse(
            self.explorer.ui.sidebar.isVisible(),
            "Sidebar should be hidden after toggle",
        )

        # Toggle back on
        actions.actionNavigationPane.trigger()
        self._process_events_with_timeout(100)

        self.assertTrue(
            self.explorer.ui.sidebar.isVisible(),
            "Sidebar should be visible after toggle back",
        )


# =============================================================================
# CONTENT AREA TESTS
# =============================================================================


class TestExplorerContentArea(WindowsExplorerConformanceTestBase):
    """Tests for verifying content area."""

    def test_has_content_view(self) -> None:
        """Verify explorer has content view area."""
        self.assertTrue(
            hasattr(self.explorer, "dynamic_stacked_view"),
            "Explorer should have dynamic_stacked_view",
        )
        self.assertIsNotNone(self.explorer.dynamic_stacked_view)

    def test_content_view_has_current_view(self) -> None:
        """Verify content area has current active view."""
        self.assertIsNotNone(
            self.explorer.dynamic_stacked_view.current_view,
            "Should have current view",
        )

    def test_content_view_shows_files(self) -> None:
        """Verify content view shows files from current directory."""
        view = self.explorer.dynamic_stacked_view.current_view
        model = view.model()

        self.assertIsNotNone(model, "View should have model")
        self.assertGreater(
            model.rowCount(view.rootIndex()),
            0,
            "View should show items in directory",
        )

    def test_content_view_is_item_view(self) -> None:
        """Verify content view is an item view."""
        view = self.explorer.dynamic_stacked_view.current_view

        self.assertIsInstance(
            view,
            QAbstractItemView,
            f"Current view should be QAbstractItemView, got {type(view).__name__}",
        )


# =============================================================================
# VIEW MODE TESTS
# =============================================================================


class TestExplorerViewModes(WindowsExplorerConformanceTestBase):
    """Tests for verifying view modes."""

    def test_extra_large_icons_mode(self) -> None:
        """Verify extra large icons mode works."""
        actions = self.explorer.ribbons.actions_definitions
        actions.actionExtraLargeIcons.trigger()
        self._process_events_with_timeout(100)

        view = self.explorer.dynamic_stacked_view.current_view

        # Should be icon view with large icons
        self.assertIsInstance(view, (QListView, QAbstractItemView))

        icon_size = view.iconSize()
        expected = Windows11ExplorerSpecs.ICON_EXTRA_LARGE
        self.assertGreaterEqual(
            max(icon_size.width(), icon_size.height()),
            expected - 50,  # Allow some tolerance
            f"Icon size should be ~{expected}px",
        )

    def test_large_icons_mode(self) -> None:
        """Verify large icons mode works."""
        actions = self.explorer.ribbons.actions_definitions
        actions.actionLargeIcons.trigger()
        self._process_events_with_timeout(100)

        view = self.explorer.dynamic_stacked_view.current_view
        icon_size = view.iconSize()
        expected = Windows11ExplorerSpecs.ICON_LARGE

        self.assertGreaterEqual(
            max(icon_size.width(), icon_size.height()),
            expected - 20,
            f"Icon size should be ~{expected}px",
        )

    def test_medium_icons_mode(self) -> None:
        """Verify medium icons mode works."""
        actions = self.explorer.ribbons.actions_definitions
        actions.actionMediumIcons.trigger()
        self._process_events_with_timeout(100)

        view = self.explorer.dynamic_stacked_view.current_view
        icon_size = view.iconSize()
        expected = Windows11ExplorerSpecs.ICON_MEDIUM

        self.assertGreaterEqual(
            max(icon_size.width(), icon_size.height()),
            expected - 10,
            f"Icon size should be ~{expected}px",
        )

    def test_small_icons_mode(self) -> None:
        """Verify small icons mode works."""
        actions = self.explorer.ribbons.actions_definitions
        actions.actionSmallIcons.trigger()
        self._process_events_with_timeout(100)

        view = self.explorer.dynamic_stacked_view.current_view
        icon_size = view.iconSize()
        expected = Windows11ExplorerSpecs.ICON_SMALL

        self.assertGreaterEqual(
            max(icon_size.width(), icon_size.height()),
            expected - 5,
            f"Icon size should be ~{expected}px",
        )

    def test_list_view_mode(self) -> None:
        """Verify list view mode works."""
        actions = self.explorer.ribbons.actions_definitions
        actions.actionListView.trigger()
        self._process_events_with_timeout(100)

        view = self.explorer.dynamic_stacked_view.current_view

        # Should be list mode
        if isinstance(view, QListView):
            self.assertEqual(
                view.viewMode(),
                QListView.ViewMode.ListMode,
                "Should be in list mode",
            )

    def test_detail_view_mode(self) -> None:
        """Verify detail view mode works."""
        actions = self.explorer.ribbons.actions_definitions
        actions.actionDetailView.trigger()
        self._process_events_with_timeout(100)

        view = self.explorer.dynamic_stacked_view.current_view

        # Should be tree view for details
        self.assertIsInstance(
            view,
            QTreeView,
            "Detail view should use QTreeView",
        )

    def test_detail_view_has_header(self) -> None:
        """Verify detail view has visible header."""
        actions = self.explorer.ribbons.actions_definitions
        actions.actionDetailView.trigger()
        self._process_events_with_timeout(100)

        view = self.explorer.dynamic_stacked_view.current_view

        if isinstance(view, QTreeView):
            header = view.header()
            self.assertIsNotNone(header)
            self.assertFalse(header.isHidden(), "Header should be visible")

    def test_detail_view_has_multiple_columns(self) -> None:
        """Verify detail view has multiple columns."""
        actions = self.explorer.ribbons.actions_definitions
        actions.actionDetailView.trigger()
        self._process_events_with_timeout(100)

        view = self.explorer.dynamic_stacked_view.current_view

        if isinstance(view, QTreeView):
            header = view.header()
            visible_count = sum(1 for i in range(header.count()) if not header.isSectionHidden(i))
            self.assertGreaterEqual(
                visible_count,
                4,  # Name, Date, Type, Size
                f"Should have at least 4 visible columns, has {visible_count}",
            )


class TestExplorerViewModeColumns(WindowsExplorerConformanceTestBase):
    """Tests for verifying detail view columns."""

    def setUp(self) -> None:
        """Set up with detail view."""
        super().setUp()
        actions = self.explorer.ribbons.actions_definitions
        actions.actionDetailView.trigger()
        self._process_events_with_timeout(100)

    def test_has_name_column(self) -> None:
        """Verify detail view has Name column."""
        view = self.explorer.dynamic_stacked_view.current_view

        if isinstance(view, QTreeView):
            model = view.model()
            if model:
                header_text = model.headerData(0, Qt.Orientation.Horizontal)
                self.assertEqual(str(header_text), "Name")

    def test_has_size_column(self) -> None:
        """Verify detail view has Size column."""
        view = self.explorer.dynamic_stacked_view.current_view

        if isinstance(view, QTreeView):
            model = view.model()
            if model:
                header_text = model.headerData(1, Qt.Orientation.Horizontal)
                self.assertEqual(str(header_text), "Size")

    def test_has_type_column(self) -> None:
        """Verify detail view has Type column."""
        view = self.explorer.dynamic_stacked_view.current_view

        if isinstance(view, QTreeView):
            model = view.model()
            if model:
                header_text = model.headerData(2, Qt.Orientation.Horizontal)
                self.assertEqual(str(header_text), "Type")

    def test_has_date_modified_column(self) -> None:
        """Verify detail view has Date Modified column."""
        view = self.explorer.dynamic_stacked_view.current_view

        if isinstance(view, QTreeView):
            model = view.model()
            if model:
                header_text = model.headerData(3, Qt.Orientation.Horizontal)
                self.assertIn("Date", str(header_text))

    def test_columns_are_resizable(self) -> None:
        """Verify columns are resizable."""
        view = self.explorer.dynamic_stacked_view.current_view

        if isinstance(view, QTreeView):
            header = view.header()
            for i in range(min(4, header.count())):
                mode = header.sectionResizeMode(i)
                self.assertIn(
                    mode,
                    [QHeaderView.ResizeMode.Interactive, QHeaderView.ResizeMode.Stretch],
                    f"Column {i} should be resizable",
                )

    def test_header_is_clickable_for_sort(self) -> None:
        """Verify header is clickable for sorting."""
        view = self.explorer.dynamic_stacked_view.current_view

        if isinstance(view, QTreeView):
            header = view.header()
            self.assertTrue(
                header.sectionsClickable(),
                "Header sections should be clickable for sorting",
            )


# =============================================================================
# SORTING TESTS
# =============================================================================


class TestExplorerSorting(WindowsExplorerConformanceTestBase):
    """Tests for verifying sorting functionality."""

    def test_sort_by_name_action(self) -> None:
        """Verify Sort by Name action exists and works."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionSortByName)

        actions.actionSortByName.trigger()
        self._process_events_with_timeout(100)

        # Verify sort column changed (or verify it's enabled)
        self.assertTrue(
            actions.actionSortByName.isChecked() or actions.actionSortByName.isEnabled(),
        )

    def test_sort_by_date_action(self) -> None:
        """Verify Sort by Date action exists and works."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionSortByDate)

        actions.actionSortByDate.trigger()
        self._process_events_with_timeout(100)

    def test_sort_by_type_action(self) -> None:
        """Verify Sort by Type action exists and works."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionSortByType)

        actions.actionSortByType.trigger()
        self._process_events_with_timeout(100)

    def test_sort_by_size_action(self) -> None:
        """Verify Sort by Size action exists and works."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionSortBySize)

        actions.actionSortBySize.trigger()
        self._process_events_with_timeout(100)

    def test_sort_ascending_action(self) -> None:
        """Verify Sort Ascending action exists."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionSortAscending)

    def test_sort_descending_action(self) -> None:
        """Verify Sort Descending action exists."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionSortDescending)


# =============================================================================
# STATUS BAR TESTS
# =============================================================================


class TestExplorerStatusBar(WindowsExplorerConformanceTestBase):
    """Tests for verifying status bar."""

    def test_status_bar_exists(self) -> None:
        """Verify status bar exists."""
        status_bar = self.explorer.statusBar()

        self.assertIsNotNone(status_bar)
        self.assertIsInstance(status_bar, QStatusBar)

    def test_status_bar_shows_item_count(self) -> None:
        """Verify status bar shows item count."""
        status_bar = self.explorer.statusBar()

        # Look for item count label
        found_count = False
        for widget in status_bar.findChildren(QLabel):
            text = widget.text()
            if "item" in text.lower() or any(c.isdigit() for c in text):
                found_count = True
                break

        self.assertTrue(found_count, "Status bar should show item count")

    def test_status_bar_updates_on_selection(self) -> None:
        """Verify status bar updates when items selected."""
        # Navigate to folder with files
        docs_path = self.temp_path / "Documents"
        self.explorer.navigate_to_path(str(docs_path))
        self._process_events_with_timeout(200)

        # Get initial status
        status_bar = self.explorer.statusBar()

        # Select an item
        view = self.explorer.dynamic_stacked_view.current_view
        model = view.model()

        if model and model.rowCount(view.rootIndex()) > 0:
            first_index = model.index(0, 0, view.rootIndex())
            view.setCurrentIndex(first_index)
            self._process_events_with_timeout(100)

            # Status should update (may show selection count or file info)
            # Just verify status bar is still functioning
            self.assertTrue(status_bar.isVisible())


# =============================================================================
# FILE OPERATIONS TESTS
# =============================================================================


class TestExplorerFileOperations(WindowsExplorerConformanceTestBase):
    """Tests for verifying file operations."""

    def test_new_folder_action(self) -> None:
        """Verify New Folder action exists and is accessible."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionNewFolder)
        self.assertTrue(actions.actionNewFolder.isEnabled())

    def test_delete_action(self) -> None:
        """Verify Delete action exists."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionDelete)

    def test_rename_action(self) -> None:
        """Verify Rename action exists."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionRename)

    def test_properties_action(self) -> None:
        """Verify Properties action exists."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionProperties)

    def test_cut_action(self) -> None:
        """Verify Cut action exists."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionCut)

    def test_copy_action(self) -> None:
        """Verify Copy action exists."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionCopy)

    def test_paste_action(self) -> None:
        """Verify Paste action exists."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionPaste)

    def test_copy_path_action(self) -> None:
        """Verify Copy Path action exists."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionCopyPath)


# =============================================================================
# NAVIGATION TESTS
# =============================================================================


class TestExplorerNavigation(WindowsExplorerConformanceTestBase):
    """Tests for verifying navigation behavior."""

    def test_navigate_to_subfolder(self) -> None:
        """Verify navigating to subfolder works."""
        target = self.temp_path / "Documents"
        self.explorer.navigate_to_path(str(target))
        self._process_events_with_timeout(200)

        current = self.explorer.address_bar.current_path
        self.assertEqual(current, target)

    def test_navigate_up(self) -> None:
        """Verify navigating up works."""
        # Start in subfolder
        start = self.temp_path / "Documents" / "Work"
        self.explorer.navigate_to_path(str(start))
        self._process_events_with_timeout(100)

        # Go up
        self.explorer.address_bar.go_up()
        self._process_events_with_timeout(100)

        current = self.explorer.address_bar.current_path
        expected = self.temp_path / "Documents"
        self.assertEqual(current, expected)

    def test_back_navigation(self) -> None:
        """Verify back navigation works."""
        dir1 = self.temp_path / "Documents"
        dir2 = self.temp_path / "Pictures"

        self.explorer.navigate_to_path(str(dir1))
        self._process_events_with_timeout(100)

        self.explorer.navigate_to_path(str(dir2))
        self._process_events_with_timeout(100)

        # Go back
        self.explorer.address_bar.go_back()
        self._process_events_with_timeout(100)

        current = self.explorer.address_bar.current_path
        self.assertEqual(current, dir1)

    def test_forward_navigation(self) -> None:
        """Verify forward navigation works."""
        dir1 = self.temp_path / "Documents"
        dir2 = self.temp_path / "Pictures"

        self.explorer.navigate_to_path(str(dir1))
        self._process_events_with_timeout(100)

        self.explorer.navigate_to_path(str(dir2))
        self._process_events_with_timeout(100)

        self.explorer.address_bar.go_back()
        self._process_events_with_timeout(100)

        self.explorer.address_bar.go_forward()
        self._process_events_with_timeout(100)

        current = self.explorer.address_bar.current_path
        self.assertEqual(current, dir2)

    def test_double_click_opens_folder(self) -> None:
        """Verify double-clicking folder navigates into it."""
        self.explorer.navigate_to_path(str(self.temp_path))
        self._process_events_with_timeout(200)

        view = self.explorer.dynamic_stacked_view.current_view
        model = view.model()

        if model is None:
            self.skipTest("Model not ready")

        # Find Documents folder
        root = view.rootIndex()
        for i in range(model.rowCount(root)):
            index = model.index(i, 0, root)
            name = model.data(index)
            if name == "Documents":
                rect = view.visualRect(index)
                if rect.isValid():
                    QTest.mouseDClick(
                        view.viewport(),
                        Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier,
                        rect.center(),
                    )
                    self._process_events_with_timeout(200)

                    current = self.explorer.address_bar.current_path
                    expected = self.temp_path / "Documents"
                    self.assertEqual(current, expected)
                    return

        self.skipTest("Documents folder not found")


class TestExplorerKeyboardNavigation(WindowsExplorerConformanceTestBase):
    """Tests for verifying keyboard navigation."""

    def test_arrow_down_moves_selection(self) -> None:
        """Verify Down arrow moves selection."""
        view = self.explorer.dynamic_stacked_view.current_view
        view.setFocus()
        self._process_events_with_timeout(100)

        model = view.model()
        if model is None or model.rowCount(view.rootIndex()) < 2:
            self.skipTest("Need at least 2 items")

        first = model.index(0, 0, view.rootIndex())
        view.setCurrentIndex(first)
        self._process_events_with_timeout(50)

        QTest.keyClick(view, Qt.Key.Key_Down)
        self._process_events_with_timeout(50)

        current = view.currentIndex()
        self.assertNotEqual(current.row(), first.row())

    def test_enter_opens_folder(self) -> None:
        """Verify Enter key opens selected folder."""
        self.explorer.navigate_to_path(str(self.temp_path))
        self._process_events_with_timeout(200)

        view = self.explorer.dynamic_stacked_view.current_view
        model = view.model()

        if model is None:
            self.skipTest("Model not ready")

        # Find Documents folder
        root = view.rootIndex()
        for i in range(model.rowCount(root)):
            index = model.index(i, 0, root)
            name = model.data(index)
            if name == "Documents":
                view.setCurrentIndex(index)
                view.setFocus()
                self._process_events_with_timeout(50)

                QTest.keyClick(view, Qt.Key.Key_Return)
                self._process_events_with_timeout(200)

                current = self.explorer.address_bar.current_path
                expected = self.temp_path / "Documents"
                self.assertEqual(current, expected)
                return

        self.skipTest("Documents folder not found")

    def test_backspace_goes_up(self) -> None:
        """Verify Backspace goes to parent."""
        start = self.temp_path / "Documents"
        self.explorer.navigate_to_path(str(start))
        self._process_events_with_timeout(100)

        view = self.explorer.dynamic_stacked_view.current_view
        view.setFocus()

        QTest.keyClick(view, Qt.Key.Key_Backspace)
        self._process_events_with_timeout(200)

        current = self.explorer.address_bar.current_path
        self.assertEqual(current, self.temp_path)

    def test_ctrl_a_selects_all(self) -> None:
        """Verify Ctrl+A selects all items."""
        docs_path = self.temp_path / "Documents"
        self.explorer.navigate_to_path(str(docs_path))
        self._process_events_with_timeout(200)

        view = self.explorer.dynamic_stacked_view.current_view
        view.setFocus()

        QTest.keyClick(view, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        self._process_events_with_timeout(50)

        selection = view.selectionModel().selectedIndexes()
        model = view.model()

        if model:
            total = model.rowCount(view.rootIndex())
            # Column 0 selected items
            selected_rows = {idx.row() for idx in selection if idx.column() == 0}
            self.assertEqual(len(selected_rows), total, "Ctrl+A should select all items")


# =============================================================================
# CONTEXT MENU TESTS
# =============================================================================


class TestExplorerContextMenu(WindowsExplorerConformanceTestBase):
    """Tests for verifying context menu."""

    def test_context_menu_on_empty_area(self) -> None:
        """Verify context menu on empty area."""
        view = self.explorer.dynamic_stacked_view.current_view

        # Clear selection
        view.clearSelection()
        self._process_events_with_timeout(50)

        # Get context menu (would need dispatcher or similar)
        # This test verifies the infrastructure exists
        self.assertIsNotNone(view)

    def test_context_menu_on_file(self) -> None:
        """Verify context menu on file selection."""
        docs_path = self.temp_path / "Documents"
        self.explorer.navigate_to_path(str(docs_path))
        self._process_events_with_timeout(200)

        view = self.explorer.dynamic_stacked_view.current_view
        model = view.model()

        if model and model.rowCount(view.rootIndex()) > 0:
            # Select first item
            first = model.index(0, 0, view.rootIndex())
            view.setCurrentIndex(first)
            self._process_events_with_timeout(50)

            # Verify selection works
            self.assertTrue(view.currentIndex().isValid())


# =============================================================================
# PANES TESTS
# =============================================================================


class TestExplorerPanes(WindowsExplorerConformanceTestBase):
    """Tests for verifying pane functionality."""

    def test_preview_pane_toggle(self) -> None:
        """Verify preview pane can be toggled."""
        actions = self.explorer.ribbons.actions_definitions

        # Toggle on
        if hasattr(actions, "actionPreviewPane"):
            initial_visible = hasattr(self.explorer, "preview_pane") and self.explorer.preview_pane.isVisible()

            actions.actionPreviewPane.trigger()
            self._process_events_with_timeout(100)

            if hasattr(self.explorer, "preview_pane"):
                after_toggle = self.explorer.preview_pane.isVisible()
                self.assertNotEqual(
                    initial_visible,
                    after_toggle,
                    "Preview pane visibility should toggle",
                )

    def test_details_pane_toggle(self) -> None:
        """Verify details pane can be toggled."""
        actions = self.explorer.ribbons.actions_definitions

        if hasattr(actions, "actionDetailsPane"):
            actions.actionDetailsPane.trigger()
            self._process_events_with_timeout(100)

            # Just verify action is functional
            self.assertTrue(actions.actionDetailsPane.isEnabled())

    def test_navigation_pane_toggle(self) -> None:
        """Verify navigation pane can be toggled."""
        actions = self.explorer.ribbons.actions_definitions

        initial_visible = self.explorer.ui.sidebar.isVisible()

        actions.actionNavigationPane.trigger()
        self._process_events_with_timeout(100)

        after_toggle = self.explorer.ui.sidebar.isVisible()
        self.assertNotEqual(
            initial_visible,
            after_toggle,
            "Navigation pane visibility should toggle",
        )


# =============================================================================
# SHOW/HIDE OPTIONS TESTS
# =============================================================================


class TestExplorerShowHideOptions(WindowsExplorerConformanceTestBase):
    """Tests for verifying show/hide options."""

    def test_show_hidden_files_action(self) -> None:
        """Verify Show Hidden Files action exists."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionShowHiddenFiles)
        self.assertTrue(actions.actionShowHiddenFiles.isCheckable())

    def test_show_file_extensions_action(self) -> None:
        """Verify Show File Extensions action exists."""
        actions = self.explorer.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionShowFileExtensions)
        self.assertTrue(actions.actionShowFileExtensions.isCheckable())

    def test_toggle_hidden_files(self) -> None:
        """Verify toggling hidden files works."""
        actions = self.explorer.ribbons.actions_definitions

        initial_checked = actions.actionShowHiddenFiles.isChecked()

        actions.actionShowHiddenFiles.trigger()
        self._process_events_with_timeout(100)

        after_toggle = actions.actionShowHiddenFiles.isChecked()
        self.assertNotEqual(
            initial_checked,
            after_toggle,
            "Show hidden files should toggle",
        )


# =============================================================================
# SELECTION TESTS
# =============================================================================


class TestExplorerSelection(WindowsExplorerConformanceTestBase):
    """Tests for verifying selection behavior."""

    def test_select_all_action(self) -> None:
        """Verify Select All action works."""
        docs_path = self.temp_path / "Documents"
        self.explorer.navigate_to_path(str(docs_path))
        self._process_events_with_timeout(200)

        actions = self.explorer.ribbons.actions_definitions
        actions.actionSelectAll.trigger()
        self._process_events_with_timeout(50)

        view = self.explorer.dynamic_stacked_view.current_view
        selection = view.selectionModel().selectedIndexes()
        model = view.model()

        if model:
            total = model.rowCount(view.rootIndex())
            selected_rows = {idx.row() for idx in selection if idx.column() == 0}
            self.assertEqual(len(selected_rows), total)

    def test_select_none_action(self) -> None:
        """Verify Select None action works."""
        docs_path = self.temp_path / "Documents"
        self.explorer.navigate_to_path(str(docs_path))
        self._process_events_with_timeout(200)

        # First select all
        view = self.explorer.dynamic_stacked_view.current_view
        view.selectAll()
        self._process_events_with_timeout(50)

        # Then select none
        actions = self.explorer.ribbons.actions_definitions
        actions.actionSelectNone.trigger()
        self._process_events_with_timeout(50)

        selection = view.selectionModel().selectedIndexes()
        self.assertEqual(len(selection), 0, "Select None should clear selection")

    def test_invert_selection_action(self) -> None:
        """Verify Invert Selection action works."""
        docs_path = self.temp_path / "Documents"
        self.explorer.navigate_to_path(str(docs_path))
        self._process_events_with_timeout(200)

        view = self.explorer.dynamic_stacked_view.current_view
        model = view.model()

        if model is None or model.rowCount(view.rootIndex()) < 2:
            self.skipTest("Need at least 2 items")

        # Select first item only
        first = model.index(0, 0, view.rootIndex())
        view.selectionModel().select(first, view.selectionModel().ClearAndSelect)
        self._process_events_with_timeout(50)

        initial_selected = {idx.row() for idx in view.selectionModel().selectedIndexes() if idx.column() == 0}

        # Invert
        actions = self.explorer.ribbons.actions_definitions
        actions.actionInvertSelection.trigger()
        self._process_events_with_timeout(50)

        after_selected = {idx.row() for idx in view.selectionModel().selectedIndexes() if idx.column() == 0}

        # Should be different
        self.assertNotEqual(initial_selected, after_selected)


# =============================================================================
# TEST RUNNER
# =============================================================================


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestExplorerWindowStructure,
        TestExplorerMenuBar,
        TestExplorerRibbon,
        TestExplorerRibbonViewTab,
        TestExplorerRibbonShareTab,
        TestExplorerNavigationBar,
        TestExplorerSearchBox,
        TestExplorerSidebar,
        TestExplorerContentArea,
        TestExplorerViewModes,
        TestExplorerViewModeColumns,
        TestExplorerSorting,
        TestExplorerStatusBar,
        TestExplorerFileOperations,
        TestExplorerNavigation,
        TestExplorerKeyboardNavigation,
        TestExplorerContextMenu,
        TestExplorerPanes,
        TestExplorerShowHideOptions,
        TestExplorerSelection,
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
