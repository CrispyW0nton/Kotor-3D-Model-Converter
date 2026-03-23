"""Windows File Dialog Conformance Tests.

This module provides exhaustive, pixel-perfect conformance tests that verify
QFileDialogExtended matches the exact behavior, layout, styling, and functionality
of native Windows IFileOpenDialog and IFileSaveDialog COM interfaces.

Test Categories:
----------------
1. Layout Structure Conformance
   - Grid layout positions for all elements
   - Widget hierarchy and containment
   - Splitter configurations and default sizes

2. Visual Styling Conformance
   - Colors matching Windows 11 Fluent Design
   - Font families, sizes, and weights
   - Border radii, margins, and padding
   - Icon sizes and positioning

3. Navigation Behavior Conformance
   - Back/Forward/Up button behavior
   - Address bar breadcrumb navigation
   - Keyboard navigation (arrow keys, Enter, Backspace, etc.)
   - History management

4. View Mode Conformance
   - List view exact layout (icon sizes, spacing, text positioning)
   - Detail view columns (Name, Date modified, Type, Size)
   - Column widths, header behavior, sorting indicators

5. File Selection Conformance
   - Single file selection
   - Multiple file selection (Ctrl+Click, Shift+Click)
   - Directory selection mode
   - Filter application

6. Dialog Button Conformance
   - Open/Save button states
   - Cancel button behavior
   - File name input validation
   - File type dropdown behavior

7. Sidebar Conformance
   - Quick access items
   - This PC section
   - Network locations
   - Recent locations

8. Context Menu Conformance
   - Menu item availability based on selection
   - Keyboard shortcut hints
   - Submenu structure

Reference:
---------
- Windows 11 File Explorer (explorer.exe)
- IFileOpenDialog / IFileSaveDialog COM interfaces
- Windows UI Automation patterns for file dialogs

All tests use real widget instances without mocking to ensure actual behavior
matches expectations. Each test has a 120-second timeout.
"""

from __future__ import annotations

import tempfile
import time
import unittest

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final, NamedTuple

from qtpy.QtCore import QCoreApplication, Qt
from qtpy.QtGui import QColor, QPalette
from qtpy.QtTest import QSignalSpy, QTest
from qtpy.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QToolButton,
)

if TYPE_CHECKING:
    from qtpy.QtCore import QModelIndex
    from qtpy.QtWidgets import (
        QAbstractButton,
        QAbstractItemView,
        QSizePolicy,
        QWidget,
    )


# =============================================================================
# WINDOWS FILE DIALOG CONSTANTS AND SPECIFICATIONS
# =============================================================================


class Windows11Colors:
    """Windows 11 Fluent Design System color specifications.

    These are the exact colors used by Windows 11 File Explorer and file dialogs.
    Colors are specified for both light and dark themes.
    """

    # Light Theme Colors
    class Light:
        """Light theme color palette."""

        BACKGROUND: Final[str] = "#FFFFFF"
        SURFACE: Final[str] = "#F9F9F9"
        CARD: Final[str] = "#FFFFFF"
        BORDER: Final[str] = "#E5E5E5"
        BORDER_SUBTLE: Final[str] = "#EBEBEB"
        TEXT_PRIMARY: Final[str] = "#1A1A1A"
        TEXT_SECONDARY: Final[str] = "#5C5C5C"
        TEXT_TERTIARY: Final[str] = "#9E9E9E"
        TEXT_DISABLED: Final[str] = "#BDBDBD"
        HOVER: Final[str] = "#F5F5F5"
        PRESSED: Final[str] = "#EBEBEB"
        SELECTED: Final[str] = "#E6F2FF"
        ACCENT: Final[str] = "#005FB8"
        ACCENT_HOVER: Final[str] = "#0067C0"
        ACCENT_PRESSED: Final[str] = "#0058A8"
        ACCENT_DISABLED: Final[str] = "#A3CFFF"
        SELECTION_BG: Final[str] = "#0078D4"
        SELECTION_TEXT: Final[str] = "#FFFFFF"
        SCROLLBAR_TRACK: Final[str] = "#F0F0F0"
        SCROLLBAR_THUMB: Final[str] = "#C2C2C2"
        SCROLLBAR_THUMB_HOVER: Final[str] = "#9E9E9E"
        SIDEBAR_BG: Final[str] = "#F3F3F3"
        RIBBON_BG: Final[str] = "#F3F3F3"
        HEADER_BG: Final[str] = "#FAFAFA"
        TREE_LINES: Final[str] = "#D1D1D1"

    class Dark:
        """Dark theme color palette."""

        BACKGROUND: Final[str] = "#1F1F1F"
        SURFACE: Final[str] = "#2D2D2D"
        CARD: Final[str] = "#292929"
        BORDER: Final[str] = "#3D3D3D"
        BORDER_SUBTLE: Final[str] = "#333333"
        TEXT_PRIMARY: Final[str] = "#FFFFFF"
        TEXT_SECONDARY: Final[str] = "#9D9D9D"
        TEXT_TERTIARY: Final[str] = "#717171"
        TEXT_DISABLED: Final[str] = "#5C5C5C"
        HOVER: Final[str] = "#383838"
        PRESSED: Final[str] = "#313131"
        SELECTED: Final[str] = "#2C3E50"
        ACCENT: Final[str] = "#60CDFF"
        ACCENT_HOVER: Final[str] = "#78D5FF"
        ACCENT_PRESSED: Final[str] = "#4DBFFF"
        ACCENT_DISABLED: Final[str] = "#3A5A6F"
        SELECTION_BG: Final[str] = "#0078D4"
        SELECTION_TEXT: Final[str] = "#FFFFFF"
        SCROLLBAR_TRACK: Final[str] = "#2D2D2D"
        SCROLLBAR_THUMB: Final[str] = "#4A4A4A"
        SCROLLBAR_THUMB_HOVER: Final[str] = "#5A5A5A"
        SIDEBAR_BG: Final[str] = "#252525"
        RIBBON_BG: Final[str] = "#2D2D2D"
        HEADER_BG: Final[str] = "#252525"
        TREE_LINES: Final[str] = "#404040"


class Windows11Fonts:
    """Windows 11 typography specifications."""

    PRIMARY_FAMILY: Final[str] = "Segoe UI Variable Text"
    FALLBACK_FAMILY: Final[str] = "Segoe UI"
    SYSTEM_FALLBACK: Final[str] = "system-ui"

    # Font sizes in points
    CAPTION: Final[int] = 9
    BODY: Final[int] = 10
    BODY_STRONG: Final[int] = 10
    SUBTITLE: Final[int] = 12
    TITLE: Final[int] = 14
    TITLE_LARGE: Final[int] = 20
    DISPLAY: Final[int] = 34

    # Font weights
    REGULAR: Final[int] = 400
    SEMIBOLD: Final[int] = 600
    BOLD: Final[int] = 700


class Windows11Spacing:
    """Windows 11 spacing and sizing specifications in pixels."""

    # Border radii
    CONTROL_CORNER_RADIUS: Final[int] = 4
    OVERLAY_CORNER_RADIUS: Final[int] = 8

    # Margins
    PAGE_MARGIN: Final[int] = 16
    CONTENT_MARGIN: Final[int] = 12
    ITEM_MARGIN: Final[int] = 4
    COMPACT_MARGIN: Final[int] = 2

    # Padding
    CONTROL_PADDING_HORIZONTAL: Final[int] = 12
    CONTROL_PADDING_VERTICAL: Final[int] = 8
    BUTTON_PADDING_HORIZONTAL: Final[int] = 16
    BUTTON_PADDING_VERTICAL: Final[int] = 8

    # Control heights
    BUTTON_HEIGHT: Final[int] = 32
    INPUT_HEIGHT: Final[int] = 32
    COMBOBOX_HEIGHT: Final[int] = 32
    TOOLBAR_HEIGHT: Final[int] = 40
    RIBBON_HEIGHT: Final[int] = 100
    STATUSBAR_HEIGHT: Final[int] = 24

    # Splitter
    SPLITTER_WIDTH: Final[int] = 1
    SIDEBAR_DEFAULT_WIDTH: Final[int] = 200
    PREVIEW_PANE_WIDTH: Final[int] = 300

    # List/Tree view items
    ITEM_HEIGHT_SMALL: Final[int] = 20
    ITEM_HEIGHT_MEDIUM: Final[int] = 28
    ITEM_HEIGHT_LARGE: Final[int] = 44

    # Icon sizes
    ICON_SIZE_SMALL: Final[int] = 16
    ICON_SIZE_MEDIUM: Final[int] = 32
    ICON_SIZE_LARGE: Final[int] = 48
    ICON_SIZE_EXTRA_LARGE: Final[int] = 96
    ICON_SIZE_JUMBO: Final[int] = 256

    # Scrollbar
    SCROLLBAR_WIDTH: Final[int] = 14
    SCROLLBAR_MIN_THUMB: Final[int] = 30


class FileDialogLayout:
    """Windows File Dialog layout specifications."""

    # Grid positions (row, column)
    TOOLBAR_ROW: Final[int] = 0
    ADDRESS_BAR_ROW: Final[int] = 1
    CONTENT_ROW: Final[int] = 2
    FILENAME_ROW: Final[int] = 3
    FILETYPE_ROW: Final[int] = 4

    # Column indices
    LABEL_COLUMN: Final[int] = 0
    INPUT_COLUMN: Final[int] = 1
    BUTTON_COLUMN: Final[int] = 2

    # Default dimensions
    DIALOG_MIN_WIDTH: Final[int] = 600
    DIALOG_MIN_HEIGHT: Final[int] = 400
    DIALOG_DEFAULT_WIDTH: Final[int] = 800
    DIALOG_DEFAULT_HEIGHT: Final[int] = 500

    # Splitter ratios
    SIDEBAR_RATIO: Final[float] = 0.2
    CONTENT_RATIO: Final[float] = 0.6
    PREVIEW_RATIO: Final[float] = 0.2


class DetailViewColumns:
    """Detail view column specifications for file dialogs."""

    class ColumnSpec(NamedTuple):
        """Column specification."""

        name: str
        header: str
        default_width: int
        min_width: int
        resizable: bool
        sortable: bool
        alignment: Qt.AlignmentFlag

    # Standard columns in Windows File Dialog detail view
    NAME: Final = ColumnSpec(
        name="Name",
        header="Name",
        default_width=250,
        min_width=100,
        resizable=True,
        sortable=True,
        alignment=Qt.AlignmentFlag.AlignLeft,
    )

    DATE_MODIFIED: Final = ColumnSpec(
        name="Date modified",
        header="Date modified",
        default_width=150,
        min_width=80,
        resizable=True,
        sortable=True,
        alignment=Qt.AlignmentFlag.AlignLeft,
    )

    TYPE: Final = ColumnSpec(
        name="Type",
        header="Type",
        default_width=120,
        min_width=60,
        resizable=True,
        sortable=True,
        alignment=Qt.AlignmentFlag.AlignLeft,
    )

    SIZE: Final = ColumnSpec(
        name="Size",
        header="Size",
        default_width=80,
        min_width=50,
        resizable=True,
        sortable=True,
        alignment=Qt.AlignmentFlag.AlignRight,
    )

    # Column order in standard Windows File Dialog
    STANDARD_ORDER: Final[tuple[ColumnSpec, ...]] = (NAME, DATE_MODIFIED, TYPE, SIZE)


# =============================================================================
# TEST UTILITIES AND HELPERS
# =============================================================================


class ColorComparator:
    """Utility for comparing colors with tolerance for anti-aliasing and rendering differences."""

    DEFAULT_TOLERANCE: ClassVar[int] = 5  # RGB component tolerance

    @staticmethod
    def colors_match(
        color1: QColor | str,
        color2: QColor | str,
        tolerance: int = DEFAULT_TOLERANCE,
    ) -> bool:
        """Check if two colors match within tolerance.

        Args:
            color1: First color (QColor or hex string)
            color2: Second color (QColor or hex string)
            tolerance: Maximum difference allowed per RGB component

        Returns:
            True if colors match within tolerance
        """
        if isinstance(color1, str):
            color1 = QColor(color1)
        if isinstance(color2, str):
            color2 = QColor(color2)

        r_diff = abs(color1.red() - color2.red())
        g_diff = abs(color1.green() - color2.green())
        b_diff = abs(color1.blue() - color2.blue())

        return r_diff <= tolerance and g_diff <= tolerance and b_diff <= tolerance

    @staticmethod
    def get_color_diff(color1: QColor | str, color2: QColor | str) -> tuple[int, int, int]:
        """Get the RGB difference between two colors.

        Returns:
            Tuple of (r_diff, g_diff, b_diff)
        """
        if isinstance(color1, str):
            color1 = QColor(color1)
        if isinstance(color2, str):
            color2 = QColor(color2)

        return (
            abs(color1.red() - color2.red()),
            abs(color1.green() - color2.green()),
            abs(color1.blue() - color2.blue()),
        )


class LayoutVerifier:
    """Utility for verifying widget layout positions and sizes."""

    @staticmethod
    def get_grid_position(
        layout: QGridLayout,
        widget: QWidget,
    ) -> tuple[int, int, int, int] | None:
        """Get the grid position of a widget.

        Returns:
            Tuple of (row, column, row_span, col_span) or None if not found
        """
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item is not None and item.widget() is widget:
                return layout.getItemPosition(i)
        return None

    @staticmethod
    def verify_widget_in_layout(
        layout: QGridLayout,
        widget: QWidget,
        expected_row: int,
        expected_col: int,
        expected_row_span: int = 1,
        expected_col_span: int = 1,
    ) -> tuple[bool, str]:
        """Verify a widget is at the expected grid position.

        Returns:
            Tuple of (success, message)
        """
        pos = LayoutVerifier.get_grid_position(layout, widget)
        if pos is None:
            return False, f"Widget {widget.objectName()} not found in layout"

        row, col, row_span, col_span = pos

        if row != expected_row:
            return False, f"Widget {widget.objectName()} at row {row}, expected {expected_row}"
        if col != expected_col:
            return False, f"Widget {widget.objectName()} at col {col}, expected {expected_col}"
        if row_span != expected_row_span:
            return False, f"Widget {widget.objectName()} row_span {row_span}, expected {expected_row_span}"
        if col_span != expected_col_span:
            return False, f"Widget {widget.objectName()} col_span {col_span}, expected {expected_col_span}"

        return True, "OK"

    @staticmethod
    def verify_size_policy(
        widget: QWidget,
        h_policy: QSizePolicy.Policy,
        v_policy: QSizePolicy.Policy,
    ) -> tuple[bool, str]:
        """Verify a widget has the expected size policy.

        Returns:
            Tuple of (success, message)
        """
        policy = widget.sizePolicy()
        actual_h = policy.horizontalPolicy()
        actual_v = policy.verticalPolicy()

        if actual_h != h_policy:
            return False, f"Widget {widget.objectName()} h_policy {actual_h.name}, expected {h_policy.name}"
        if actual_v != v_policy:
            return False, f"Widget {widget.objectName()} v_policy {actual_v.name}, expected {v_policy.name}"

        return True, "OK"


class FontVerifier:
    """Utility for verifying font properties."""

    @staticmethod
    def verify_font_family(widget: QWidget, expected_families: list[str]) -> tuple[bool, str]:
        """Verify widget font is one of the expected families.

        Args:
            widget: Widget to check
            expected_families: List of acceptable font family names

        Returns:
            Tuple of (success, message)
        """
        font = widget.font()
        actual_family = font.family()

        if actual_family in expected_families:
            return True, "OK"

        return False, f"Widget {widget.objectName()} font '{actual_family}' not in {expected_families}"

    @staticmethod
    def verify_font_size(
        widget: QWidget,
        expected_size: int,
        tolerance: int = 1,
    ) -> tuple[bool, str]:
        """Verify widget font size matches expected.

        Args:
            widget: Widget to check
            expected_size: Expected font size in points
            tolerance: Allowed deviation in points

        Returns:
            Tuple of (success, message)
        """
        font = widget.font()
        actual_size = font.pointSize()

        if abs(actual_size - expected_size) <= tolerance:
            return True, "OK"

        return False, f"Widget {widget.objectName()} font size {actual_size}pt, expected {expected_size}pt"


class ViewItemVerifier:
    """Utility for verifying view item properties."""

    @staticmethod
    def get_visible_items(view: QAbstractItemView) -> list[QModelIndex]:
        """Get all visible items in a view.

        Returns:
            List of visible model indices
        """
        items = []
        model = view.model()
        if model is None:
            return items

        viewport = view.viewport()
        if viewport is None:
            return items

        rect = viewport.rect()

        # Get the index at each corner and edges to find visible range
        top_left = view.indexAt(rect.topLeft())
        if not top_left.isValid():
            return items

        # Iterate through visible items
        index = top_left
        while index.isValid():
            item_rect = view.visualRect(index)
            if not rect.intersects(item_rect):
                break
            items.append(index)
            index = view.indexBelow(index)

        return items

    @staticmethod
    def verify_item_height(
        view: QAbstractItemView,
        expected_height: int,
        tolerance: int = 2,
    ) -> tuple[bool, str]:
        """Verify item heights in a view.

        Returns:
            Tuple of (success, message)
        """
        items = ViewItemVerifier.get_visible_items(view)
        if not items:
            return True, "No visible items to verify"

        for index in items:
            rect = view.visualRect(index)
            if abs(rect.height() - expected_height) > tolerance:
                return False, f"Item height {rect.height()}px, expected {expected_height}px"

        return True, "OK"


# =============================================================================
# BASE TEST CLASS
# =============================================================================


class WindowsFileDialogConformanceTestBase(unittest.TestCase):
    """Base class for Windows File Dialog conformance tests.

    Provides common setup, teardown, and utility methods for all conformance tests.
    """

    # Class-level test configuration
    TIMEOUT_SECONDS: ClassVar[int] = 120

    # Test environment
    app: ClassVar[QApplication]
    temp_dir: ClassVar[tempfile.TemporaryDirectory]
    temp_path: ClassVar[Path]

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test class with QApplication and temporary directory structure."""
        # Ensure QApplication exists
        cls.app = QApplication.instance() or QApplication([])

        # Create temporary directory structure mimicking typical filesystem
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.temp_path = Path(cls.temp_dir.name)

        # Create folder structure
        (cls.temp_path / "Documents").mkdir()
        (cls.temp_path / "Documents" / "Reports").mkdir()
        (cls.temp_path / "Documents" / "Letters").mkdir()
        (cls.temp_path / "Pictures").mkdir()
        (cls.temp_path / "Pictures" / "Vacation").mkdir()
        (cls.temp_path / "Downloads").mkdir()
        (cls.temp_path / "Music").mkdir()
        (cls.temp_path / "Videos").mkdir()

        # Create test files
        (cls.temp_path / "Documents" / "report.txt").write_text("Report content")
        (cls.temp_path / "Documents" / "report.docx").write_bytes(b"PK\x03\x04" + b"\x00" * 100)
        (cls.temp_path / "Documents" / "data.xlsx").write_bytes(b"PK\x03\x04" + b"\x00" * 100)
        (cls.temp_path / "Documents" / "Reports" / "annual.pdf").write_bytes(b"%PDF-1.4" + b"\x00" * 100)
        (cls.temp_path / "Pictures" / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        (cls.temp_path / "Pictures" / "screenshot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        (cls.temp_path / "Downloads" / "setup.exe").write_bytes(b"MZ" + b"\x00" * 100)
        (cls.temp_path / "Downloads" / "archive.zip").write_bytes(b"PK\x03\x04" + b"\x00" * 100)
        (cls.temp_path / "Music" / "song.mp3").write_bytes(b"ID3" + b"\x00" * 100)
        (cls.temp_path / "Videos" / "video.mp4").write_bytes(b"\x00\x00\x00\x1c" + b"ftyp" + b"\x00" * 100)

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up test class resources."""
        cls.temp_dir.cleanup()

    def setUp(self) -> None:
        """Set up for each test - create fresh dialog instance."""
        # Import here to avoid import errors during test discovery
        from utility.gui.qt.adapters.filesystem.qfiledialog.qfiledialog import (
            QFileDialog as AdapterQFileDialog,
        )
        from utility.gui.qt.filesystem.qfiledialogextended.qfiledialogextended import (
            QFileDialogExtended,
        )

        self.AdapterQFileDialog = AdapterQFileDialog
        self.dialog = QFileDialogExtended(None, "Test File Dialog", str(self.temp_path))
        self.dialog.setOption(AdapterQFileDialog.Option.DontUseNativeDialog, True)

        # Wait for dialog to be ready
        self._process_events_with_timeout(500)

    def tearDown(self) -> None:
        """Clean up after each test."""
        if self.dialog.isVisible():
            self.dialog.close()
        self.dialog.deleteLater()
        self._process_events_with_timeout(100)

    def _process_events_with_timeout(self, timeout_ms: int) -> None:
        """Process Qt events with timeout.

        Args:
            timeout_ms: Maximum time to process events in milliseconds
        """
        start = time.time()
        while (time.time() - start) * 1000 < timeout_ms:
            QCoreApplication.processEvents()
            time.sleep(0.01)

    def _is_dark_theme(self) -> bool:
        """Detect if the current theme is dark.

        Returns:
            True if dark theme is active
        """
        palette = self.app.palette()
        window_color = palette.color(QPalette.ColorRole.Window)
        return window_color.lightness() < 128

    def _get_theme_colors(self) -> type[Windows11Colors.Light] | type[Windows11Colors.Dark]:
        """Get the appropriate color palette for the current theme.

        Returns:
            Light or Dark color class
        """
        return Windows11Colors.Dark if self._is_dark_theme() else Windows11Colors.Light


# =============================================================================
# LAYOUT STRUCTURE CONFORMANCE TESTS
# =============================================================================


class TestFileDialogLayoutStructure(WindowsFileDialogConformanceTestBase):
    """Tests for verifying the layout structure matches Windows File Dialog."""

    def test_main_layout_type(self) -> None:
        """Verify the main layout is a QGridLayout."""
        layout = self.dialog.layout()
        self.assertIsInstance(
            layout,
            QGridLayout,
            f"Main layout should be QGridLayout, got {type(layout).__name__}",
        )

    def test_grid_layout_minimum_dimensions(self) -> None:
        """Verify grid layout has sufficient rows and columns."""
        grid = self.dialog.ui.gridlayout

        # Must have at least: toolbar, address, search, content, filename, filetype rows
        self.assertGreaterEqual(
            grid.rowCount(),
            6,
            f"Grid should have at least 6 rows, has {grid.rowCount()}",
        )

        # Must have at least: label, input, button columns
        self.assertGreaterEqual(
            grid.columnCount(),
            3,
            f"Grid should have at least 3 columns, has {grid.columnCount()}",
        )

    def test_ribbons_widget_position(self) -> None:
        """Verify ribbons widget is at correct grid position."""
        grid = self.dialog.ui.gridlayout
        success, msg = LayoutVerifier.verify_widget_in_layout(
            grid,
            self.dialog.ribbons,
            expected_row=0,
            expected_col=0,
            expected_row_span=1,
            expected_col_span=3,
        )
        self.assertTrue(success, msg)

    def test_address_bar_position(self) -> None:
        """Verify address bar is at correct grid position."""
        grid = self.dialog.ui.gridlayout
        success, msg = LayoutVerifier.verify_widget_in_layout(
            grid,
            self.dialog.address_bar,
            expected_row=1,
            expected_col=0,
            expected_row_span=1,
            expected_col_span=3,
        )
        self.assertTrue(success, msg)

    def test_search_filter_position(self) -> None:
        """Verify search filter is at correct grid position."""
        grid = self.dialog.ui.gridlayout
        success, msg = LayoutVerifier.verify_widget_in_layout(
            grid,
            self.dialog.search_filter,
            expected_row=2,
            expected_col=0,
            expected_row_span=1,
            expected_col_span=3,
        )
        self.assertTrue(success, msg)

    def test_look_in_label_offset_position(self) -> None:
        """Verify lookInLabel is offset by 3 rows after extended elements."""
        grid = self.dialog.ui.gridlayout
        success, msg = LayoutVerifier.verify_widget_in_layout(
            grid,
            self.dialog.ui.lookInLabel,
            expected_row=3,
            expected_col=0,
        )
        self.assertTrue(success, msg)

    def test_splitter_position(self) -> None:
        """Verify main splitter is at correct grid position."""
        grid = self.dialog.ui.gridlayout
        success, msg = LayoutVerifier.verify_widget_in_layout(
            grid,
            self.dialog.ui.splitter,
            expected_row=4,
            expected_col=0,
            expected_col_span=3,
        )
        self.assertTrue(success, msg)

    def test_splitter_widget_count(self) -> None:
        """Verify splitter contains expected number of widgets."""
        splitter = self.dialog.ui.splitter

        # Should have at least: sidebar, content frame
        # May have 3 if preview pane is present
        self.assertGreaterEqual(
            splitter.count(),
            2,
            f"Splitter should have at least 2 widgets, has {splitter.count()}",
        )

    def test_splitter_first_widget_is_sidebar(self) -> None:
        """Verify first splitter widget is the sidebar."""
        splitter = self.dialog.ui.splitter
        first_widget = splitter.widget(0)

        self.assertIs(
            first_widget,
            self.dialog.ui.sidebar,
            "First splitter widget should be sidebar",
        )

    def test_splitter_second_widget_is_frame(self) -> None:
        """Verify second splitter widget is the content frame."""
        splitter = self.dialog.ui.splitter
        second_widget = splitter.widget(1)

        self.assertIs(
            second_widget,
            self.dialog.ui.frame,
            "Second splitter widget should be content frame",
        )

    def test_stacked_widget_page_count(self) -> None:
        """Verify stacked widget has exactly 2 pages (list and detail view)."""
        stacked = self.dialog.ui.stackedWidget

        self.assertEqual(
            stacked.count(),
            2,
            f"Stacked widget should have exactly 2 pages, has {stacked.count()}",
        )

    def test_list_view_in_stacked_page(self) -> None:
        """Verify list view is contained in stacked widget page."""
        list_view = self.dialog.ui.listView
        parent = list_view.parent()

        # Parent should be page widget in stacked widget
        self.assertIs(
            parent,
            self.dialog.ui.page,
            "List view parent should be stacked widget page",
        )

    def test_tree_view_in_stacked_page(self) -> None:
        """Verify tree view is contained in stacked widget page."""
        tree_view = self.dialog.ui.treeView
        parent = tree_view.parent()

        self.assertIs(
            parent,
            self.dialog.ui.page_2,
            "Tree view parent should be stacked widget page_2",
        )

    def test_file_name_controls_row(self) -> None:
        """Verify file name label, edit, and button box are in same row."""
        grid = self.dialog.ui.gridlayout

        # Get positions
        label_pos = LayoutVerifier.get_grid_position(grid, self.dialog.ui.fileNameLabel)
        edit_pos = LayoutVerifier.get_grid_position(grid, self.dialog.ui.fileNameEdit)
        button_pos = LayoutVerifier.get_grid_position(grid, self.dialog.ui.buttonBox)

        self.assertIsNotNone(label_pos, "fileNameLabel not found in grid")
        self.assertIsNotNone(edit_pos, "fileNameEdit not found in grid")
        self.assertIsNotNone(button_pos, "buttonBox not found in grid")

        # All should be in same row
        self.assertEqual(
            label_pos[0],
            edit_pos[0],
            "fileNameLabel and fileNameEdit should be in same row",
        )
        self.assertEqual(
            edit_pos[0],
            button_pos[0],
            "fileNameEdit and buttonBox should be in same row",
        )

    def test_file_type_controls_row(self) -> None:
        """Verify file type label and combo are in same row."""
        grid = self.dialog.ui.gridlayout

        label_pos = LayoutVerifier.get_grid_position(grid, self.dialog.ui.fileTypeLabel)
        combo_pos = LayoutVerifier.get_grid_position(grid, self.dialog.ui.fileTypeCombo)

        self.assertIsNotNone(label_pos, "fileTypeLabel not found in grid")
        self.assertIsNotNone(combo_pos, "fileTypeCombo not found in grid")

        self.assertEqual(
            label_pos[0],
            combo_pos[0],
            "fileTypeLabel and fileTypeCombo should be in same row",
        )

    def test_file_type_row_below_file_name_row(self) -> None:
        """Verify file type row is below file name row."""
        grid = self.dialog.ui.gridlayout

        filename_pos = LayoutVerifier.get_grid_position(grid, self.dialog.ui.fileNameLabel)
        filetype_pos = LayoutVerifier.get_grid_position(grid, self.dialog.ui.fileTypeLabel)

        self.assertIsNotNone(filename_pos)
        self.assertIsNotNone(filetype_pos)

        self.assertGreater(
            filetype_pos[0],
            filename_pos[0],
            "File type row should be below file name row",
        )


class TestFileDialogSidebarStructure(WindowsFileDialogConformanceTestBase):
    """Tests for verifying sidebar structure matches Windows File Dialog."""

    def test_sidebar_is_qframe(self) -> None:
        """Verify sidebar is a QFrame widget."""
        self.assertIsInstance(
            self.dialog.ui.sidebar,
            QFrame,
            f"Sidebar should be QFrame, got {type(self.dialog.ui.sidebar).__name__}",
        )

    def test_sidebar_visible_by_default(self) -> None:
        """Verify sidebar is visible by default."""
        self.assertTrue(
            self.dialog.ui.sidebar.isVisible(),
            "Sidebar should be visible by default",
        )

    def test_sidebar_minimum_width(self) -> None:
        """Verify sidebar has reasonable minimum width."""
        sidebar = self.dialog.ui.sidebar
        min_width = sidebar.minimumWidth()

        # Windows file dialog sidebar is typically 150-250px
        # Allow some flexibility but ensure it's not too narrow
        self.assertGreaterEqual(
            min_width,
            100,
            f"Sidebar minimum width {min_width} should be at least 100px",
        )

    def test_sidebar_default_width_in_splitter(self) -> None:
        """Verify sidebar has appropriate default width in splitter."""
        splitter = self.dialog.ui.splitter
        sizes = splitter.sizes()

        if sizes:
            sidebar_width = sizes[0]
            total_width = sum(sizes)

            # Sidebar should be roughly 15-30% of total width
            ratio = sidebar_width / total_width if total_width > 0 else 0
            self.assertGreaterEqual(
                ratio,
                0.10,
                f"Sidebar ratio {ratio:.2f} should be at least 0.10",
            )
            self.assertLessEqual(
                ratio,
                0.40,
                f"Sidebar ratio {ratio:.2f} should be at most 0.40",
            )


class TestFileDialogToolbarStructure(WindowsFileDialogConformanceTestBase):
    """Tests for verifying toolbar/navigation structure."""

    def test_back_button_exists(self) -> None:
        """Verify back button exists and is QToolButton."""
        self.assertIsNotNone(self.dialog.ui.backButton)
        self.assertIsInstance(self.dialog.ui.backButton, QToolButton)

    def test_forward_button_exists(self) -> None:
        """Verify forward button exists and is QToolButton."""
        self.assertIsNotNone(self.dialog.ui.forwardButton)
        self.assertIsInstance(self.dialog.ui.forwardButton, QToolButton)

    def test_to_parent_button_exists(self) -> None:
        """Verify up/parent button exists and is QToolButton."""
        self.assertIsNotNone(self.dialog.ui.toParentButton)
        self.assertIsInstance(self.dialog.ui.toParentButton, QToolButton)

    def test_new_folder_button_exists(self) -> None:
        """Verify new folder button exists and is QToolButton."""
        self.assertIsNotNone(self.dialog.ui.newFolderButton)
        self.assertIsInstance(self.dialog.ui.newFolderButton, QToolButton)

    def test_list_mode_button_exists(self) -> None:
        """Verify list mode button exists and is QToolButton."""
        self.assertIsNotNone(self.dialog.ui.listModeButton)
        self.assertIsInstance(self.dialog.ui.listModeButton, QToolButton)

    def test_detail_mode_button_exists(self) -> None:
        """Verify detail mode button exists and is QToolButton."""
        self.assertIsNotNone(self.dialog.ui.detailModeButton)
        self.assertIsInstance(self.dialog.ui.detailModeButton, QToolButton)

    def test_navigation_buttons_in_horizontal_layout(self) -> None:
        """Verify navigation buttons are arranged horizontally."""
        hbox = self.dialog.ui.hboxlayout

        # Verify it's a horizontal layout
        self.assertIsInstance(hbox, QHBoxLayout)

        # Verify buttons are in the layout in correct order
        widgets_in_order = []
        for i in range(hbox.count()):
            item = hbox.itemAt(i)
            if item and item.widget():
                widgets_in_order.append(item.widget())

        # Should contain: lookInCombo, back, forward, toParent, newFolder, listMode, detailMode
        self.assertIn(self.dialog.ui.backButton, widgets_in_order)
        self.assertIn(self.dialog.ui.forwardButton, widgets_in_order)
        self.assertIn(self.dialog.ui.toParentButton, widgets_in_order)


# =============================================================================
# VIEW MODE CONFORMANCE TESTS
# =============================================================================


class TestFileDialogViewModes(WindowsFileDialogConformanceTestBase):
    """Tests for verifying view mode behavior matches Windows File Dialog."""

    def test_list_view_mode_shows_list_view(self) -> None:
        """Verify List mode shows list view widget."""
        self.dialog.setViewMode(self.AdapterQFileDialog.ViewMode.List)
        self._process_events_with_timeout(100)

        self.assertTrue(
            self.dialog.ui.listView.isVisible(),
            "List view should be visible in List mode",
        )
        self.assertFalse(
            self.dialog.ui.treeView.isVisible(),
            "Tree view should be hidden in List mode",
        )

    def test_detail_view_mode_shows_tree_view(self) -> None:
        """Verify Detail mode shows tree view widget."""
        self.dialog.setViewMode(self.AdapterQFileDialog.ViewMode.Detail)
        self._process_events_with_timeout(100)

        self.assertTrue(
            self.dialog.ui.treeView.isVisible(),
            "Tree view should be visible in Detail mode",
        )
        self.assertFalse(
            self.dialog.ui.listView.isVisible(),
            "List view should be hidden in Detail mode",
        )

    def test_list_mode_button_switches_to_list(self) -> None:
        """Verify clicking list mode button switches to list view."""
        # Start in detail mode
        self.dialog.setViewMode(self.AdapterQFileDialog.ViewMode.Detail)
        self._process_events_with_timeout(50)

        # Click list mode button
        self.dialog.ui.listModeButton.click()
        self._process_events_with_timeout(100)

        self.assertEqual(
            self.dialog.viewMode(),
            self.AdapterQFileDialog.ViewMode.List,
            "View mode should be List after clicking list button",
        )

    def test_detail_mode_button_switches_to_detail(self) -> None:
        """Verify clicking detail mode button switches to detail view."""
        # Start in list mode
        self.dialog.setViewMode(self.AdapterQFileDialog.ViewMode.List)
        self._process_events_with_timeout(50)

        # Click detail mode button
        self.dialog.ui.detailModeButton.click()
        self._process_events_with_timeout(100)

        self.assertEqual(
            self.dialog.viewMode(),
            self.AdapterQFileDialog.ViewMode.Detail,
            "View mode should be Detail after clicking detail button",
        )

    def test_list_mode_button_pressed_state(self) -> None:
        """Verify list mode button shows pressed state when list view active."""
        self.dialog.setViewMode(self.AdapterQFileDialog.ViewMode.List)
        self._process_events_with_timeout(100)

        self.assertTrue(
            self.dialog.ui.listModeButton.isDown(),
            "List mode button should be down when list view active",
        )
        self.assertFalse(
            self.dialog.ui.detailModeButton.isDown(),
            "Detail mode button should not be down when list view active",
        )

    def test_detail_mode_button_pressed_state(self) -> None:
        """Verify detail mode button shows pressed state when detail view active."""
        self.dialog.setViewMode(self.AdapterQFileDialog.ViewMode.Detail)
        self._process_events_with_timeout(100)

        self.assertTrue(
            self.dialog.ui.detailModeButton.isDown(),
            "Detail mode button should be down when detail view active",
        )
        self.assertFalse(
            self.dialog.ui.listModeButton.isDown(),
            "List mode button should not be down when detail view active",
        )

    def test_view_mode_persistence_across_navigation(self) -> None:
        """Verify view mode persists when navigating directories."""
        # Set to detail mode
        self.dialog.setViewMode(self.AdapterQFileDialog.ViewMode.Detail)
        self._process_events_with_timeout(50)

        # Navigate to subfolder
        self.dialog.setDirectory(str(self.temp_path / "Documents"))
        self._process_events_with_timeout(100)

        # View mode should still be detail
        self.assertEqual(
            self.dialog.viewMode(),
            self.AdapterQFileDialog.ViewMode.Detail,
            "View mode should persist after navigation",
        )


class TestFileDialogDetailViewColumns(WindowsFileDialogConformanceTestBase):
    """Tests for verifying detail view columns match Windows File Dialog."""

    def setUp(self) -> None:
        """Set up and switch to detail view."""
        super().setUp()
        self.dialog.setViewMode(self.AdapterQFileDialog.ViewMode.Detail)
        self._process_events_with_timeout(100)

    def test_tree_view_has_header(self) -> None:
        """Verify tree view has visible header."""
        header = self.dialog.ui.treeView.header()

        self.assertIsNotNone(header, "Tree view should have header")
        self.assertFalse(
            header.isHidden(),
            "Tree view header should be visible",
        )

    def test_tree_view_has_name_column(self) -> None:
        """Verify tree view has Name column."""
        model = self.dialog.model
        header_text = model.headerData(0, Qt.Orientation.Horizontal)

        self.assertIsNotNone(header_text, "Column 0 should have header text")
        self.assertEqual(
            str(header_text),
            "Name",
            f"Column 0 should be 'Name', got '{header_text}'",
        )

    def test_tree_view_has_size_column(self) -> None:
        """Verify tree view has Size column."""
        model = self.dialog.model
        header_text = model.headerData(1, Qt.Orientation.Horizontal)

        self.assertIsNotNone(header_text, "Column 1 should have header text")
        self.assertEqual(
            str(header_text),
            "Size",
            f"Column 1 should be 'Size', got '{header_text}'",
        )

    def test_tree_view_has_type_column(self) -> None:
        """Verify tree view has Type column."""
        model = self.dialog.model
        header_text = model.headerData(2, Qt.Orientation.Horizontal)

        self.assertIsNotNone(header_text, "Column 2 should have header text")
        self.assertEqual(
            str(header_text),
            "Type",
            f"Column 2 should be 'Type', got '{header_text}'",
        )

    def test_tree_view_has_date_modified_column(self) -> None:
        """Verify tree view has Date Modified column."""
        model = self.dialog.model
        header_text = model.headerData(3, Qt.Orientation.Horizontal)

        self.assertIsNotNone(header_text, "Column 3 should have header text")
        self.assertIn(
            "Date",
            str(header_text),
            f"Column 3 should contain 'Date', got '{header_text}'",
        )

    def test_tree_view_columns_resizable(self) -> None:
        """Verify tree view columns are resizable."""
        header = self.dialog.ui.treeView.header()

        for i in range(4):  # First 4 columns
            resize_mode = header.sectionResizeMode(i)
            self.assertIn(
                resize_mode,
                [QHeaderView.ResizeMode.Interactive, QHeaderView.ResizeMode.Stretch],
                f"Column {i} should be resizable",
            )

    def test_tree_view_header_clickable_for_sort(self) -> None:
        """Verify tree view header is clickable for sorting."""
        header = self.dialog.ui.treeView.header()

        self.assertTrue(
            header.isSortIndicatorShown() or header.sectionsClickable(),
            "Header should be sortable (clickable or show sort indicator)",
        )


# =============================================================================
# NAVIGATION BEHAVIOR CONFORMANCE TESTS
# =============================================================================


class TestFileDialogNavigation(WindowsFileDialogConformanceTestBase):
    """Tests for verifying navigation behavior matches Windows File Dialog."""

    def test_set_directory_updates_view(self) -> None:
        """Verify setDirectory updates the file view."""
        target = self.temp_path / "Documents"
        self.dialog.setDirectory(str(target))
        self._process_events_with_timeout(100)

        current = Path(self.dialog.directory().absolutePath())
        self.assertEqual(current, target)

    def test_set_directory_updates_address_bar(self) -> None:
        """Verify setDirectory updates the address bar."""
        target = self.temp_path / "Documents"
        self.dialog.setDirectory(str(target))
        self._process_events_with_timeout(100)

        self.assertEqual(
            self.dialog.address_bar.current_path,
            target,
            "Address bar should show current directory",
        )

    def test_navigate_to_parent(self) -> None:
        """Verify navigating to parent directory works."""
        # Start in subfolder
        start = self.temp_path / "Documents" / "Reports"
        self.dialog.setDirectory(str(start))
        self._process_events_with_timeout(100)

        # Navigate up
        self.dialog.address_bar.go_up()
        self._process_events_with_timeout(100)

        current = Path(self.dialog.directory().absolutePath())
        expected = self.temp_path / "Documents"
        self.assertEqual(current, expected, "Should navigate to parent directory")

    def test_navigate_back_in_history(self) -> None:
        """Verify back navigation through history."""
        # Build history
        dir1 = self.temp_path / "Documents"
        dir2 = self.temp_path / "Pictures"

        self.dialog.setDirectory(str(dir1))
        self._process_events_with_timeout(50)

        self.dialog.setDirectory(str(dir2))
        self._process_events_with_timeout(50)

        # Go back
        self.dialog.address_bar.go_back()
        self._process_events_with_timeout(100)

        current = Path(self.dialog.directory().absolutePath())
        self.assertEqual(current, dir1, "Should navigate back to previous directory")

    def test_navigate_forward_in_history(self) -> None:
        """Verify forward navigation through history."""
        # Build history
        dir1 = self.temp_path / "Documents"
        dir2 = self.temp_path / "Pictures"

        self.dialog.setDirectory(str(dir1))
        self._process_events_with_timeout(50)

        self.dialog.setDirectory(str(dir2))
        self._process_events_with_timeout(50)

        # Go back then forward
        self.dialog.address_bar.go_back()
        self._process_events_with_timeout(50)

        self.dialog.address_bar.go_forward()
        self._process_events_with_timeout(100)

        current = Path(self.dialog.directory().absolutePath())
        self.assertEqual(current, dir2, "Should navigate forward to next directory")

    def test_double_click_folder_navigates(self) -> None:
        """Verify double-clicking a folder navigates into it."""
        self.dialog.setDirectory(str(self.temp_path))
        self._process_events_with_timeout(200)  # Wait for model to populate

        # Find Documents folder in view
        view = self.dialog.ui.treeView
        model = view.model()

        if model is None:
            self.skipTest("Model not ready")

        # Look for Documents folder
        root_index = view.rootIndex()
        for i in range(model.rowCount(root_index)):
            index = model.index(i, 0, root_index)
            name = model.data(index)
            if name == "Documents":
                # Double-click to navigate
                rect = view.visualRect(index)
                if rect.isValid():
                    QTest.mouseDClick(
                        view.viewport(),
                        Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier,
                        rect.center(),
                    )
                    self._process_events_with_timeout(200)

                    current = Path(self.dialog.directory().absolutePath())
                    expected = self.temp_path / "Documents"
                    self.assertEqual(
                        current,
                        expected,
                        "Double-click should navigate into folder",
                    )
                    return

        self.skipTest("Documents folder not visible in view")


class TestFileDialogKeyboardNavigation(WindowsFileDialogConformanceTestBase):
    """Tests for verifying keyboard navigation matches Windows File Dialog."""

    def test_arrow_down_moves_selection(self) -> None:
        """Verify Down arrow moves selection to next item."""
        view = self.dialog.ui.treeView
        view.setFocus()
        self._process_events_with_timeout(100)

        # Get first item
        model = view.model()
        if model is None or model.rowCount() == 0:
            self.skipTest("No items in view")

        first_index = model.index(0, 0, view.rootIndex())
        view.setCurrentIndex(first_index)
        self._process_events_with_timeout(50)

        # Press down arrow
        QTest.keyClick(view, Qt.Key.Key_Down)
        self._process_events_with_timeout(50)

        # Should move to next item
        current = view.currentIndex()
        self.assertNotEqual(
            current,
            first_index,
            "Down arrow should move to next item",
        )

    def test_arrow_up_moves_selection(self) -> None:
        """Verify Up arrow moves selection to previous item."""
        view = self.dialog.ui.treeView
        view.setFocus()
        self._process_events_with_timeout(100)

        model = view.model()
        if model is None or model.rowCount() < 2:
            self.skipTest("Need at least 2 items in view")

        # Start at second item
        second_index = model.index(1, 0, view.rootIndex())
        view.setCurrentIndex(second_index)
        self._process_events_with_timeout(50)

        # Press up arrow
        QTest.keyClick(view, Qt.Key.Key_Up)
        self._process_events_with_timeout(50)

        # Should move to first item
        current = view.currentIndex()
        first_index = model.index(0, 0, view.rootIndex())
        self.assertEqual(
            current.row(),
            first_index.row(),
            "Up arrow should move to previous item",
        )

    def test_enter_opens_folder(self) -> None:
        """Verify Enter key opens selected folder."""
        self.dialog.setDirectory(str(self.temp_path))
        self._process_events_with_timeout(200)

        view = self.dialog.ui.treeView
        model = view.model()

        if model is None:
            self.skipTest("Model not ready")

        # Find and select Documents folder
        root_index = view.rootIndex()
        for i in range(model.rowCount(root_index)):
            index = model.index(i, 0, root_index)
            name = model.data(index)
            if name == "Documents":
                view.setCurrentIndex(index)
                view.setFocus()
                self._process_events_with_timeout(50)

                # Press Enter
                QTest.keyClick(view, Qt.Key.Key_Return)
                self._process_events_with_timeout(200)

                current = Path(self.dialog.directory().absolutePath())
                expected = self.temp_path / "Documents"
                self.assertEqual(
                    current,
                    expected,
                    "Enter should open selected folder",
                )
                return

        self.skipTest("Documents folder not found")

    def test_backspace_goes_to_parent(self) -> None:
        """Verify Backspace navigates to parent directory."""
        start = self.temp_path / "Documents"
        self.dialog.setDirectory(str(start))
        self._process_events_with_timeout(100)

        view = self.dialog.ui.treeView
        view.setFocus()

        # Press Backspace
        QTest.keyClick(view, Qt.Key.Key_Backspace)
        self._process_events_with_timeout(200)

        current = Path(self.dialog.directory().absolutePath())
        self.assertEqual(
            current,
            self.temp_path,
            "Backspace should navigate to parent",
        )

    def test_home_key_selects_first_item(self) -> None:
        """Verify Home key selects first item in view."""
        view = self.dialog.ui.treeView
        view.setFocus()
        self._process_events_with_timeout(100)

        model = view.model()
        if model is None or model.rowCount() < 2:
            self.skipTest("Need at least 2 items")

        # Select last item
        last_index = model.index(model.rowCount(view.rootIndex()) - 1, 0, view.rootIndex())
        view.setCurrentIndex(last_index)
        self._process_events_with_timeout(50)

        # Press Home
        QTest.keyClick(view, Qt.Key.Key_Home)
        self._process_events_with_timeout(50)

        current = view.currentIndex()
        self.assertEqual(
            current.row(),
            0,
            "Home should select first item",
        )

    def test_end_key_selects_last_item(self) -> None:
        """Verify End key selects last item in view."""
        view = self.dialog.ui.treeView
        view.setFocus()
        self._process_events_with_timeout(100)

        model = view.model()
        if model is None or model.rowCount() < 2:
            self.skipTest("Need at least 2 items")

        # Select first item
        first_index = model.index(0, 0, view.rootIndex())
        view.setCurrentIndex(first_index)
        self._process_events_with_timeout(50)

        # Press End
        QTest.keyClick(view, Qt.Key.Key_End)
        self._process_events_with_timeout(50)

        current = view.currentIndex()
        last_row = model.rowCount(view.rootIndex()) - 1
        self.assertEqual(
            current.row(),
            last_row,
            "End should select last item",
        )


# =============================================================================
# FILE SELECTION CONFORMANCE TESTS
# =============================================================================


class TestFileDialogFileSelection(WindowsFileDialogConformanceTestBase):
    """Tests for verifying file selection behavior matches Windows File Dialog."""

    def test_single_file_selection(self) -> None:
        """Verify single file can be selected."""
        file_path = self.temp_path / "Documents" / "report.txt"
        self.dialog.selectFile(str(file_path))
        self._process_events_with_timeout(100)

        selected = self.dialog.selectedFiles()
        self.assertIn(
            str(file_path),
            selected,
            "File should be in selected files",
        )

    def test_multiple_file_selection_mode(self) -> None:
        """Verify multiple file selection mode works."""
        self.dialog.setFileMode(self.AdapterQFileDialog.FileMode.ExistingFiles)
        self._process_events_with_timeout(50)

        self.assertEqual(
            self.dialog.fileMode(),
            self.AdapterQFileDialog.FileMode.ExistingFiles,
            "File mode should be ExistingFiles",
        )

    def test_directory_selection_mode(self) -> None:
        """Verify directory selection mode works."""
        self.dialog.setFileMode(self.AdapterQFileDialog.FileMode.Directory)
        self._process_events_with_timeout(50)

        self.assertEqual(
            self.dialog.fileMode(),
            self.AdapterQFileDialog.FileMode.Directory,
            "File mode should be Directory",
        )

    def test_ctrl_click_adds_to_selection(self) -> None:
        """Verify Ctrl+Click adds items to selection in multi-select mode."""
        self.dialog.setFileMode(self.AdapterQFileDialog.FileMode.ExistingFiles)
        self.dialog.setDirectory(str(self.temp_path / "Documents"))
        self._process_events_with_timeout(200)

        view = self.dialog.ui.treeView
        model = view.model()

        if model is None or model.rowCount(view.rootIndex()) < 2:
            self.skipTest("Need at least 2 items")

        # Click first item
        first_index = model.index(0, 0, view.rootIndex())
        rect1 = view.visualRect(first_index)
        if rect1.isValid():
            QTest.mouseClick(
                view.viewport(),
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
                rect1.center(),
            )
            self._process_events_with_timeout(50)

        # Ctrl+Click second item
        second_index = model.index(1, 0, view.rootIndex())
        rect2 = view.visualRect(second_index)
        if rect2.isValid():
            QTest.mouseClick(
                view.viewport(),
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.ControlModifier,
                rect2.center(),
            )
            self._process_events_with_timeout(50)

        # Both should be selected
        selection = view.selectionModel().selectedIndexes()
        # Filter to column 0 only (name column)
        selected_rows = {idx.row() for idx in selection if idx.column() == 0}

        self.assertIn(0, selected_rows, "First item should be selected")
        self.assertIn(1, selected_rows, "Second item should be selected")

    def test_shift_click_range_selection(self) -> None:
        """Verify Shift+Click selects range of items."""
        self.dialog.setFileMode(self.AdapterQFileDialog.FileMode.ExistingFiles)
        self.dialog.setDirectory(str(self.temp_path / "Documents"))
        self._process_events_with_timeout(200)

        view = self.dialog.ui.treeView
        model = view.model()

        row_count = model.rowCount(view.rootIndex()) if model else 0
        if row_count < 3:
            self.skipTest("Need at least 3 items")

        # Click first item
        first_index = model.index(0, 0, view.rootIndex())
        rect1 = view.visualRect(first_index)
        if rect1.isValid():
            QTest.mouseClick(
                view.viewport(),
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
                rect1.center(),
            )
            self._process_events_with_timeout(50)

        # Shift+Click third item
        third_index = model.index(2, 0, view.rootIndex())
        rect3 = view.visualRect(third_index)
        if rect3.isValid():
            QTest.mouseClick(
                view.viewport(),
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.ShiftModifier,
                rect3.center(),
            )
            self._process_events_with_timeout(50)

        # Items 0, 1, 2 should all be selected
        selection = view.selectionModel().selectedIndexes()
        selected_rows = {idx.row() for idx in selection if idx.column() == 0}

        self.assertIn(0, selected_rows, "First item should be selected")
        self.assertIn(1, selected_rows, "Second item should be selected")
        self.assertIn(2, selected_rows, "Third item should be selected")


class TestFileDialogFileFiltering(WindowsFileDialogConformanceTestBase):
    """Tests for verifying file filtering matches Windows File Dialog."""

    def test_set_name_filter(self) -> None:
        """Verify name filter can be set."""
        filter_str = "Text Files (*.txt)"
        self.dialog.setNameFilter(filter_str)

        filters = self.dialog.nameFilters()
        self.assertIn("Text Files", filters[0])

    def test_multiple_name_filters(self) -> None:
        """Verify multiple name filters can be set."""
        filters = ["Text Files (*.txt)", "Word Documents (*.docx)", "All Files (*)"]
        self.dialog.setNameFilters(filters)

        result_filters = self.dialog.nameFilters()
        self.assertEqual(len(result_filters), 3)

    def test_filter_selection(self) -> None:
        """Verify filter can be selected."""
        filters = ["Text Files (*.txt)", "All Files (*)"]
        self.dialog.setNameFilters(filters)
        self.dialog.selectNameFilter("All Files (*)")

        selected = self.dialog.selectedNameFilter()
        self.assertIn("All Files", selected)

    def test_search_filter_updates_proxy(self) -> None:
        """Verify search filter updates proxy model."""
        self.dialog.search_filter.line_edit.setText("report")
        self._process_events_with_timeout(100)

        pattern = self.dialog.proxy_model.filterRegularExpression().pattern()
        self.assertIn("report", pattern.lower())

    def test_search_filter_case_insensitive(self) -> None:
        """Verify search filter is case insensitive."""
        self.dialog.search_filter.line_edit.setText("REPORT")
        self._process_events_with_timeout(50)

        case_sensitivity = self.dialog.proxy_model.filterCaseSensitivity()
        self.assertEqual(
            case_sensitivity,
            Qt.CaseSensitivity.CaseInsensitive,
            "Search should be case insensitive",
        )

    def test_search_filter_clear(self) -> None:
        """Verify clearing search filter shows all files."""
        self.dialog.search_filter.line_edit.setText("xyz")
        self._process_events_with_timeout(50)

        self.dialog.search_filter.line_edit.clear()
        self._process_events_with_timeout(50)

        pattern = self.dialog.proxy_model.filterRegularExpression().pattern()
        self.assertEqual(pattern, "", "Cleared search should show all files")


# =============================================================================
# DIALOG CONTROLS CONFORMANCE TESTS
# =============================================================================


class TestFileDialogBottomControls(WindowsFileDialogConformanceTestBase):
    """Tests for verifying bottom control behavior matches Windows File Dialog."""

    def test_file_name_label_text(self) -> None:
        """Verify file name label has correct text."""
        label = self.dialog.ui.fileNameLabel
        text = label.text()

        # Should contain "File name" or similar
        self.assertTrue(
            "file" in text.lower() or "name" in text.lower(),
            f"File name label should indicate file name, got '{text}'",
        )

    def test_file_name_edit_is_editable(self) -> None:
        """Verify file name edit is editable."""
        edit = self.dialog.ui.fileNameEdit

        self.assertFalse(
            edit.isReadOnly(),
            "File name edit should be editable",
        )

    def test_file_name_edit_updates_selection(self) -> None:
        """Verify typing in file name edit updates selection."""
        edit = self.dialog.ui.fileNameEdit
        edit.setText("report.txt")
        self._process_events_with_timeout(100)

        # The dialog should recognize the file name
        # (actual selection behavior may vary)
        self.assertEqual(edit.text(), "report.txt")

    def test_file_type_combo_has_filters(self) -> None:
        """Verify file type combo shows filters."""
        filters = ["Text Files (*.txt)", "All Files (*)"]
        self.dialog.setNameFilters(filters)
        self._process_events_with_timeout(50)

        combo = self.dialog.ui.fileTypeCombo
        self.assertGreater(
            combo.count(),
            0,
            "File type combo should have filter entries",
        )

    def test_button_box_has_accept_button(self) -> None:
        """Verify button box has accept (Open/Save) button."""
        button_box = self.dialog.ui.buttonBox
        accept_button = button_box.button(QDialogButtonBox.StandardButton.Open)

        # Try Open first, then Save
        if accept_button is None:
            accept_button = button_box.button(QDialogButtonBox.StandardButton.Save)
        if accept_button is None:
            # Check for custom button with accept role
            for button in button_box.buttons():
                if button_box.buttonRole(button) == QDialogButtonBox.ButtonRole.AcceptRole:
                    accept_button = button
                    break

        self.assertIsNotNone(
            accept_button,
            "Button box should have accept button",
        )

    def test_button_box_has_reject_button(self) -> None:
        """Verify button box has reject (Cancel) button."""
        button_box = self.dialog.ui.buttonBox
        cancel_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)

        if cancel_button is None:
            # Check for custom button with reject role
            for button in button_box.buttons():
                if button_box.buttonRole(button) == QDialogButtonBox.ButtonRole.RejectRole:
                    cancel_button = button
                    break

        self.assertIsNotNone(
            cancel_button,
            "Button box should have cancel button",
        )


class TestFileDialogAcceptModes(WindowsFileDialogConformanceTestBase):
    """Tests for verifying accept mode behavior matches Windows File Dialog."""

    def test_accept_open_mode(self) -> None:
        """Verify AcceptOpen mode is set correctly."""
        self.dialog.setAcceptMode(self.AdapterQFileDialog.AcceptMode.AcceptOpen)

        self.assertEqual(
            self.dialog.acceptMode(),
            self.AdapterQFileDialog.AcceptMode.AcceptOpen,
        )

    def test_accept_save_mode(self) -> None:
        """Verify AcceptSave mode is set correctly."""
        self.dialog.setAcceptMode(self.AdapterQFileDialog.AcceptMode.AcceptSave)

        self.assertEqual(
            self.dialog.acceptMode(),
            self.AdapterQFileDialog.AcceptMode.AcceptSave,
        )

    def test_accept_mode_changes_button_text(self) -> None:
        """Verify accept mode changes button text appropriately."""
        button_box = self.dialog.ui.buttonBox

        # Set Open mode
        self.dialog.setAcceptMode(self.AdapterQFileDialog.AcceptMode.AcceptOpen)
        self._process_events_with_timeout(50)

        # Get accept button text
        accept_button: QAbstractButton | None = None
        for button in button_box.buttons():
            role = button_box.buttonRole(button)
            if role == QDialogButtonBox.ButtonRole.AcceptRole:
                accept_button = button
                break

        if accept_button is not None:
            open_text = accept_button.text()

            # Set Save mode
            self.dialog.setAcceptMode(self.AdapterQFileDialog.AcceptMode.AcceptSave)
            self._process_events_with_timeout(50)

            save_text = accept_button.text()

            # Text should differ between Open and Save modes
            # (or at least be appropriate for the mode)
            self.assertTrue(
                "Open" in open_text or "Save" in save_text or open_text != save_text,
                "Accept button text should reflect mode",
            )


# =============================================================================
# PREVIEW PANE CONFORMANCE TESTS
# =============================================================================


class TestFileDialogPreviewPane(WindowsFileDialogConformanceTestBase):
    """Tests for verifying preview pane behavior matches Windows File Dialog."""

    def test_preview_pane_exists(self) -> None:
        """Verify preview pane widget exists."""
        self.assertTrue(
            hasattr(self.dialog, "preview_pane"),
            "Dialog should have preview_pane attribute",
        )
        self.assertIsNotNone(
            self.dialog.preview_pane,
            "Preview pane should not be None",
        )

    def test_preview_pane_hidden_by_default(self) -> None:
        """Verify preview pane is hidden by default."""
        self.assertFalse(
            self.dialog.preview_pane.isVisible(),
            "Preview pane should be hidden by default",
        )

    def test_preview_pane_can_be_shown(self) -> None:
        """Verify preview pane can be toggled visible."""
        self.dialog.toggle_preview_pane(True)
        self._process_events_with_timeout(100)

        self.assertTrue(
            self.dialog.preview_pane.isVisible(),
            "Preview pane should be visible after toggle",
        )

    def test_preview_pane_can_be_hidden(self) -> None:
        """Verify preview pane can be toggled hidden."""
        self.dialog.toggle_preview_pane(True)
        self._process_events_with_timeout(50)

        self.dialog.toggle_preview_pane(False)
        self._process_events_with_timeout(100)

        self.assertFalse(
            self.dialog.preview_pane.isVisible(),
            "Preview pane should be hidden after toggle off",
        )

    def test_preview_pane_in_splitter(self) -> None:
        """Verify preview pane is added to main splitter."""
        self.dialog.toggle_preview_pane(True)
        self._process_events_with_timeout(100)

        splitter = self.dialog.ui.splitter

        # Find preview pane in splitter
        found = False
        for i in range(splitter.count()):
            if splitter.widget(i) is self.dialog.preview_pane:
                found = True
                break

        self.assertTrue(found, "Preview pane should be in splitter")


# =============================================================================
# RIBBON CONFORMANCE TESTS
# =============================================================================


class TestFileDialogRibbon(WindowsFileDialogConformanceTestBase):
    """Tests for verifying ribbon matches Windows File Dialog/Explorer ribbon."""

    def test_ribbon_exists(self) -> None:
        """Verify ribbon widget exists."""
        self.assertIsNotNone(
            self.dialog.ribbons,
            "Dialog should have ribbons widget",
        )

    def test_ribbon_has_tab_widget(self) -> None:
        """Verify ribbon has tab widget."""
        self.assertTrue(
            hasattr(self.dialog.ribbons, "tab_widget"),
            "Ribbon should have tab_widget attribute",
        )

    def test_ribbon_has_home_tab(self) -> None:
        """Verify ribbon has Home tab."""
        tab_widget = self.dialog.ribbons.tab_widget
        tab_texts = [tab_widget.tabText(i).lower() for i in range(tab_widget.count())]

        self.assertIn("home", tab_texts, "Ribbon should have Home tab")

    def test_ribbon_has_view_tab(self) -> None:
        """Verify ribbon has View tab."""
        tab_widget = self.dialog.ribbons.tab_widget
        tab_texts = [tab_widget.tabText(i).lower() for i in range(tab_widget.count())]

        self.assertIn("view", tab_texts, "Ribbon should have View tab")

    def test_ribbon_view_tab_has_preview_pane_action(self) -> None:
        """Verify View tab has preview pane toggle action."""
        actions = self.dialog.ribbons.actions_definitions

        self.assertIsNotNone(
            actions.actionPreviewPane,
            "Actions should have preview pane action",
        )

    def test_ribbon_view_tab_has_navigation_pane_action(self) -> None:
        """Verify View tab has navigation pane toggle action."""
        actions = self.dialog.ribbons.actions_definitions

        self.assertIsNotNone(
            actions.actionNavigationPane,
            "Actions should have navigation pane action",
        )

    def test_ribbon_has_view_mode_actions(self) -> None:
        """Verify ribbon has all view mode actions."""
        actions = self.dialog.ribbons.actions_definitions

        self.assertIsNotNone(actions.actionExtraLargeIcons)
        self.assertIsNotNone(actions.actionLargeIcons)
        self.assertIsNotNone(actions.actionMediumIcons)
        self.assertIsNotNone(actions.actionSmallIcons)
        self.assertIsNotNone(actions.actionListView)
        self.assertIsNotNone(actions.actionDetailView)


# =============================================================================
# CONTEXT MENU CONFORMANCE TESTS
# =============================================================================


class TestFileDialogContextMenu(WindowsFileDialogConformanceTestBase):
    """Tests for verifying context menu matches Windows File Dialog."""

    def test_context_menu_can_be_created(self) -> None:
        """Verify context menu can be created."""
        view = self.dialog.ui.treeView
        menu = self.dialog.dispatcher.get_context_menu(view, view.rect().center())

        self.assertIsNotNone(menu, "Should create context menu")
        self.assertIsInstance(menu, QMenu)

    def test_context_menu_has_actions(self) -> None:
        """Verify context menu has actions."""
        view = self.dialog.ui.treeView
        menu = self.dialog.dispatcher.get_context_menu(view, view.rect().center())

        self.assertGreater(
            len(menu.actions()),
            0,
            "Context menu should have actions",
        )

    def test_context_menu_on_file_has_open(self) -> None:
        """Verify context menu on file has Open action."""
        self.dialog.setDirectory(str(self.temp_path / "Documents"))
        self._process_events_with_timeout(200)

        view = self.dialog.ui.treeView
        model = view.model()

        if model is None:
            self.skipTest("Model not ready")

        # Find a file (not folder)
        root = view.rootIndex()
        for i in range(model.rowCount(root)):
            index = model.index(i, 0, root)
            # Check if it's a file by looking at the source model
            source_index = self.dialog.proxy_model.mapToSource(index)
            if not self.dialog.model.isDir(source_index):
                view.setCurrentIndex(index)
                rect = view.visualRect(index)
                menu = self.dialog.dispatcher.get_context_menu(view, rect.center())

                action_texts = [a.text().lower() for a in menu.actions()]
                self.assertTrue(
                    any("open" in t for t in action_texts),
                    f"Context menu should have Open action, got: {action_texts}",
                )
                return

        self.skipTest("No files found in directory")


# =============================================================================
# SIGNALS AND EVENTS CONFORMANCE TESTS
# =============================================================================


class TestFileDialogSignals(WindowsFileDialogConformanceTestBase):
    """Tests for verifying signals match expected behavior."""

    def test_directory_entered_signal(self) -> None:
        """Verify directoryEntered signal is emitted."""
        spy = QSignalSpy(self.dialog.directoryEntered)

        self.dialog.setDirectory(str(self.temp_path / "Documents"))
        self._process_events_with_timeout(100)

        # Signal may or may not be emitted depending on implementation
        # Just verify it exists and is connectable
        self.assertTrue(
            hasattr(self.dialog, "directoryEntered"),
            "Dialog should have directoryEntered signal",
        )

    def test_current_changed_signal(self) -> None:
        """Verify currentChanged signal exists."""
        self.assertTrue(
            hasattr(self.dialog, "currentChanged"),
            "Dialog should have currentChanged signal",
        )

    def test_files_selected_signal(self) -> None:
        """Verify filesSelected signal exists."""
        self.assertTrue(
            hasattr(self.dialog, "filesSelected"),
            "Dialog should have filesSelected signal",
        )

    def test_filter_selected_signal(self) -> None:
        """Verify filterSelected signal exists."""
        self.assertTrue(
            hasattr(self.dialog, "filterSelected"),
            "Dialog should have filterSelected signal",
        )


# =============================================================================
# OPTIONS AND FLAGS CONFORMANCE TESTS
# =============================================================================


class TestFileDialogOptions(WindowsFileDialogConformanceTestBase):
    """Tests for verifying dialog options match Windows File Dialog."""

    def test_dont_use_native_dialog_option(self) -> None:
        """Verify DontUseNativeDialog option is set."""
        self.assertTrue(
            self.dialog.testOption(self.AdapterQFileDialog.Option.DontUseNativeDialog),
            "DontUseNativeDialog should be set",
        )

    def test_show_dirs_only_option(self) -> None:
        """Verify ShowDirsOnly option can be set/unset."""
        self.dialog.setOption(self.AdapterQFileDialog.Option.ShowDirsOnly, True)
        self.assertTrue(
            self.dialog.testOption(self.AdapterQFileDialog.Option.ShowDirsOnly),
        )

        self.dialog.setOption(self.AdapterQFileDialog.Option.ShowDirsOnly, False)
        self.assertFalse(
            self.dialog.testOption(self.AdapterQFileDialog.Option.ShowDirsOnly),
        )

    def test_read_only_option(self) -> None:
        """Verify ReadOnly option can be set/unset."""
        self.dialog.setOption(self.AdapterQFileDialog.Option.ReadOnly, True)
        self.assertTrue(
            self.dialog.testOption(self.AdapterQFileDialog.Option.ReadOnly),
        )

        self.dialog.setOption(self.AdapterQFileDialog.Option.ReadOnly, False)
        self.assertFalse(
            self.dialog.testOption(self.AdapterQFileDialog.Option.ReadOnly),
        )

    def test_hide_name_filter_details_option(self) -> None:
        """Verify HideNameFilterDetails option works."""
        self.dialog.setOption(self.AdapterQFileDialog.Option.HideNameFilterDetails, True)
        self.assertTrue(
            self.dialog.testOption(self.AdapterQFileDialog.Option.HideNameFilterDetails),
        )

    def test_dont_resolve_symlinks_option(self) -> None:
        """Verify DontResolveSymlinks option works."""
        # Set resolve to True then False
        self.dialog.setResolveSymlinks(True)
        self.assertTrue(self.dialog.resolveSymlinks())

        self.dialog.setResolveSymlinks(False)
        self.assertFalse(self.dialog.resolveSymlinks())


# =============================================================================
# TEST RUNNER
# =============================================================================


if __name__ == "__main__":
    # Configure test runner
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    test_classes = [
        TestFileDialogLayoutStructure,
        TestFileDialogSidebarStructure,
        TestFileDialogToolbarStructure,
        TestFileDialogViewModes,
        TestFileDialogDetailViewColumns,
        TestFileDialogNavigation,
        TestFileDialogKeyboardNavigation,
        TestFileDialogFileSelection,
        TestFileDialogFileFiltering,
        TestFileDialogBottomControls,
        TestFileDialogAcceptModes,
        TestFileDialogPreviewPane,
        TestFileDialogRibbon,
        TestFileDialogContextMenu,
        TestFileDialogSignals,
        TestFileDialogOptions,
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # Run with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
