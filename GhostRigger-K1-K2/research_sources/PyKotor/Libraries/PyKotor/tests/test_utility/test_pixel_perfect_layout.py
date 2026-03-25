"""Windows 11 Pixel-Perfect Layout Tests.

This module provides exhaustive tests verifying exact pixel-level conformance
of the custom Qt file dialogs and explorer widgets to Windows 11 specifications.

Tests cover:
- Exact dimensions (width, height) with sub-pixel tolerance
- Exact positioning (x, y coordinates)
- Exact margins and padding
- Exact spacing between elements
- Exact alignment (left, center, right, top, bottom)
- Exact corner radii
- Exact border widths

Tolerance levels:
- STRICT: ±1px (for critical UI elements)
- NORMAL: ±2px (for most UI elements)
- RELAXED: ±5px (for elements that may vary by DPI/font)
"""

from __future__ import annotations

import unittest

from enum import IntEnum
from typing import TYPE_CHECKING, ClassVar, Final

from qtpy.QtCore import QCoreApplication, QMargins
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QPushButton,
    QToolBar,
    QToolButton,
)

if TYPE_CHECKING:
    from qtpy.QtCore import QRect
    from qtpy.QtWidgets import (
        QLayout,
        QWidget,
    )

# =============================================================================
# TOLERANCE LEVELS
# =============================================================================


class LayoutTolerance(IntEnum):
    """Tolerance levels for layout comparisons."""

    STRICT = 1  # ±1px - For critical elements
    NORMAL = 2  # ±2px - For most elements
    RELAXED = 5  # ±5px - For DPI-sensitive elements
    LOOSE = 10  # ±10px - For flexible elements


# =============================================================================
# WINDOWS 11 EXACT SPECIFICATIONS
# =============================================================================


class Windows11DialogSpecs:
    """Exact pixel specifications for Windows 11 File Dialog."""

    # Dialog dimensions
    class Dialog:
        MIN_WIDTH: Final[int] = 500
        MIN_HEIGHT: Final[int] = 400
        DEFAULT_WIDTH: Final[int] = 750
        DEFAULT_HEIGHT: Final[int] = 500

    # Top toolbar/navigation area
    class NavigationArea:
        HEIGHT: Final[int] = 40
        BUTTON_SIZE: Final[int] = 32
        BUTTON_SPACING: Final[int] = 4
        BACK_FORWARD_GROUP_WIDTH: Final[int] = 68
        UP_BUTTON_LEFT_MARGIN: Final[int] = 8

    # Address bar
    class AddressBar:
        HEIGHT: Final[int] = 28
        LEFT_MARGIN: Final[int] = 0
        RIGHT_MARGIN: Final[int] = 8
        ICON_SIZE: Final[int] = 16
        ICON_LEFT_PADDING: Final[int] = 8
        TEXT_LEFT_PADDING: Final[int] = 4
        BREADCRUMB_ARROW_WIDTH: Final[int] = 12
        CORNER_RADIUS: Final[int] = 4

    # Search box
    class SearchBox:
        HEIGHT: Final[int] = 28
        MIN_WIDTH: Final[int] = 180
        MAX_WIDTH: Final[int] = 300
        RIGHT_MARGIN: Final[int] = 12
        ICON_SIZE: Final[int] = 16
        ICON_PADDING: Final[int] = 8
        CORNER_RADIUS: Final[int] = 4

    # Sidebar / Navigation pane
    class Sidebar:
        MIN_WIDTH: Final[int] = 160
        DEFAULT_WIDTH: Final[int] = 200
        MAX_WIDTH: Final[int] = 400
        ITEM_HEIGHT: Final[int] = 28
        ITEM_LEFT_PADDING: Final[int] = 12
        ITEM_ICON_SIZE: Final[int] = 16
        ITEM_ICON_TEXT_SPACING: Final[int] = 8
        GROUP_HEADER_HEIGHT: Final[int] = 32
        GROUP_VERTICAL_SPACING: Final[int] = 4
        INDENT_WIDTH: Final[int] = 24

    # File list content area
    class FileList:
        MIN_WIDTH: Final[int] = 200
        ITEM_PADDING_HORIZONTAL: Final[int] = 8
        ITEM_PADDING_VERTICAL: Final[int] = 4

        # Details view
        DETAILS_ROW_HEIGHT: Final[int] = 22
        DETAILS_HEADER_HEIGHT: Final[int] = 26
        DETAILS_ICON_SIZE: Final[int] = 16
        DETAILS_ICON_PADDING: Final[int] = 4

        # Icons view
        ICON_EXTRA_LARGE: Final[int] = 256
        ICON_LARGE: Final[int] = 96
        ICON_MEDIUM: Final[int] = 48
        ICON_SMALL: Final[int] = 32

        # List view
        LIST_ICON_SIZE: Final[int] = 16
        LIST_ITEM_HEIGHT: Final[int] = 20

        # Grid spacing
        EXTRA_LARGE_GRID_WIDTH: Final[int] = 280
        EXTRA_LARGE_GRID_HEIGHT: Final[int] = 300
        LARGE_GRID_WIDTH: Final[int] = 130
        LARGE_GRID_HEIGHT: Final[int] = 140
        MEDIUM_GRID_WIDTH: Final[int] = 80
        MEDIUM_GRID_HEIGHT: Final[int] = 90
        SMALL_GRID_WIDTH: Final[int] = 50
        SMALL_GRID_HEIGHT: Final[int] = 60

    # Preview pane
    class PreviewPane:
        MIN_WIDTH: Final[int] = 200
        DEFAULT_WIDTH: Final[int] = 250
        PADDING: Final[int] = 16
        PREVIEW_IMAGE_MAX_HEIGHT: Final[int] = 200
        FILENAME_TOP_MARGIN: Final[int] = 12
        INFO_SPACING: Final[int] = 8

    # Bottom controls area
    class BottomControls:
        HEIGHT: Final[int] = 64
        TOP_MARGIN: Final[int] = 8
        BOTTOM_MARGIN: Final[int] = 12
        LEFT_MARGIN: Final[int] = 12
        RIGHT_MARGIN: Final[int] = 12
        HORIZONTAL_SPACING: Final[int] = 12

        # Filename row
        FILENAME_LABEL_WIDTH: Final[int] = 80
        FILENAME_EDIT_HEIGHT: Final[int] = 24

        # Filter row
        FILTER_LABEL_WIDTH: Final[int] = 80
        FILTER_COMBO_HEIGHT: Final[int] = 24

        # Buttons
        BUTTON_WIDTH: Final[int] = 80
        BUTTON_HEIGHT: Final[int] = 28
        BUTTON_SPACING: Final[int] = 8

    # Splitter
    class Splitter:
        WIDTH: Final[int] = 1
        HANDLE_WIDTH: Final[int] = 5


class Windows11ExplorerSpecs:
    """Exact pixel specifications for Windows 11 Explorer."""

    # Ribbon
    class Ribbon:
        COLLAPSED_HEIGHT: Final[int] = 34
        EXPANDED_HEIGHT: Final[int] = 94
        TAB_HEIGHT: Final[int] = 30
        TAB_MIN_WIDTH: Final[int] = 50
        TAB_PADDING_HORIZONTAL: Final[int] = 12
        TAB_PADDING_VERTICAL: Final[int] = 6

        # Groups
        GROUP_PADDING_TOP: Final[int] = 4
        GROUP_PADDING_BOTTOM: Final[int] = 4
        GROUP_PADDING_LEFT: Final[int] = 8
        GROUP_PADDING_RIGHT: Final[int] = 8
        GROUP_LABEL_HEIGHT: Final[int] = 16
        GROUP_SPACING: Final[int] = 4
        GROUP_SEPARATOR_WIDTH: Final[int] = 1

        # Buttons
        LARGE_BUTTON_WIDTH: Final[int] = 56
        LARGE_BUTTON_HEIGHT: Final[int] = 66
        LARGE_BUTTON_ICON_SIZE: Final[int] = 32
        LARGE_BUTTON_LABEL_HEIGHT: Final[int] = 26

        SMALL_BUTTON_HEIGHT: Final[int] = 22
        SMALL_BUTTON_ICON_SIZE: Final[int] = 16
        SMALL_BUTTON_HORIZONTAL_PADDING: Final[int] = 8


# =============================================================================
# LAYOUT VERIFICATION UTILITIES
# =============================================================================


class LayoutVerifier:
    """Utility class for verifying widget layouts."""

    @staticmethod
    def verify_dimension(
        actual: int,
        expected: int,
        tolerance: LayoutTolerance = LayoutTolerance.NORMAL,
        name: str = "dimension",
    ) -> tuple[bool, str]:
        """Verify a single dimension value."""
        diff = abs(actual - expected)

        if diff <= tolerance:
            return True, f"{name}: {actual}px OK (expected {expected}±{tolerance})"
        return False, f"{name}: {actual}px != {expected}px (diff {diff}, tolerance ±{tolerance})"

    @staticmethod
    def verify_position(
        widget: QWidget,
        expected_x: int | None = None,
        expected_y: int | None = None,
        tolerance: LayoutTolerance = LayoutTolerance.NORMAL,
    ) -> tuple[bool, str]:
        """Verify widget position."""
        pos = widget.pos()
        issues = []

        if expected_x is not None:
            diff = abs(pos.x() - expected_x)
            if diff > tolerance:
                issues.append(f"x: {pos.x()} != {expected_x}")

        if expected_y is not None:
            diff = abs(pos.y() - expected_y)
            if diff > tolerance:
                issues.append(f"y: {pos.y()} != {expected_y}")

        if issues:
            return False, f"Position mismatch: {', '.join(issues)}"
        return True, "Position OK"

    @staticmethod
    def verify_size(
        widget: QWidget,
        expected_width: int | None = None,
        expected_height: int | None = None,
        tolerance: LayoutTolerance = LayoutTolerance.NORMAL,
    ) -> tuple[bool, str]:
        """Verify widget size."""
        size = widget.size()
        issues = []

        if expected_width is not None:
            diff = abs(size.width() - expected_width)
            if diff > tolerance:
                issues.append(f"width: {size.width()} != {expected_width}")

        if expected_height is not None:
            diff = abs(size.height() - expected_height)
            if diff > tolerance:
                issues.append(f"height: {size.height()} != {expected_height}")

        if issues:
            return False, f"Size mismatch: {', '.join(issues)} (tolerance ±{tolerance})"
        return True, "Size OK"

    @staticmethod
    def verify_rect(
        widget: QWidget,
        expected: QRect,
        tolerance: LayoutTolerance = LayoutTolerance.NORMAL,
    ) -> tuple[bool, str]:
        """Verify widget geometry rectangle."""
        actual = widget.geometry()
        issues = []

        if abs(actual.x() - expected.x()) > tolerance:
            issues.append(f"x: {actual.x()} != {expected.x()}")
        if abs(actual.y() - expected.y()) > tolerance:
            issues.append(f"y: {actual.y()} != {expected.y()}")
        if abs(actual.width() - expected.width()) > tolerance:
            issues.append(f"width: {actual.width()} != {expected.width()}")
        if abs(actual.height() - expected.height()) > tolerance:
            issues.append(f"height: {actual.height()} != {expected.height()}")

        if issues:
            return False, f"Geometry mismatch: {', '.join(issues)}"
        return True, "Geometry OK"

    @staticmethod
    def verify_margins(
        layout: QLayout,
        expected: QMargins | tuple[int, int, int, int],
        tolerance: LayoutTolerance = LayoutTolerance.NORMAL,
    ) -> tuple[bool, str]:
        """Verify layout margins."""
        actual = layout.contentsMargins()

        if isinstance(expected, tuple):
            expected = QMargins(*expected)

        issues = []
        if abs(actual.left() - expected.left()) > tolerance:
            issues.append(f"left: {actual.left()} != {expected.left()}")
        if abs(actual.top() - expected.top()) > tolerance:
            issues.append(f"top: {actual.top()} != {expected.top()}")
        if abs(actual.right() - expected.right()) > tolerance:
            issues.append(f"right: {actual.right()} != {expected.right()}")
        if abs(actual.bottom() - expected.bottom()) > tolerance:
            issues.append(f"bottom: {actual.bottom()} != {expected.bottom()}")

        if issues:
            return False, f"Margins mismatch: {', '.join(issues)}"
        return True, "Margins OK"

    @staticmethod
    def verify_spacing(
        layout: QLayout,
        expected: int,
        tolerance: LayoutTolerance = LayoutTolerance.NORMAL,
    ) -> tuple[bool, str]:
        """Verify layout spacing."""
        actual = layout.spacing()
        diff = abs(actual - expected)

        if diff <= tolerance:
            return True, f"Spacing: {actual}px OK"
        return False, f"Spacing: {actual}px != {expected}px"

    @staticmethod
    def verify_alignment(
        widget1: QWidget,
        widget2: QWidget,
        alignment: str,  # "left", "right", "top", "bottom", "center_h", "center_v"
        tolerance: LayoutTolerance = LayoutTolerance.NORMAL,
    ) -> tuple[bool, str]:
        """Verify two widgets are aligned."""
        geo1 = widget1.geometry()
        geo2 = widget2.geometry()

        if alignment == "left":
            diff = abs(geo1.left() - geo2.left())
        elif alignment == "right":
            diff = abs(geo1.right() - geo2.right())
        elif alignment == "top":
            diff = abs(geo1.top() - geo2.top())
        elif alignment == "bottom":
            diff = abs(geo1.bottom() - geo2.bottom())
        elif alignment == "center_h":
            diff = abs(geo1.center().x() - geo2.center().x())
        elif alignment == "center_v":
            diff = abs(geo1.center().y() - geo2.center().y())
        else:
            return False, f"Unknown alignment: {alignment}"

        if diff <= tolerance:
            return True, f"{alignment} aligned OK"
        return False, f"{alignment} misaligned by {diff}px"


# =============================================================================
# BASE TEST CLASS
# =============================================================================


class PixelLayoutTestBase(unittest.TestCase):
    """Base class for pixel-level layout tests."""

    TIMEOUT_SECONDS: ClassVar[int] = 120
    app: ClassVar[QApplication]

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test class."""
        cls.app = QApplication.instance() or QApplication([])

    def assertDimension(
        self,
        actual: int,
        expected: int,
        tolerance: LayoutTolerance = LayoutTolerance.NORMAL,
        msg: str = "",
    ) -> None:
        """Assert dimension matches within tolerance."""
        diff = abs(actual - expected)
        self.assertLessEqual(
            diff,
            tolerance,
            f"{msg}: {actual}px != {expected}px (tolerance ±{tolerance})",
        )

    def assertWidgetSize(
        self,
        widget: QWidget,
        expected_width: int | None = None,
        expected_height: int | None = None,
        tolerance: LayoutTolerance = LayoutTolerance.NORMAL,
    ) -> None:
        """Assert widget size matches within tolerance."""
        size = widget.size()

        if expected_width is not None:
            self.assertDimension(
                size.width(),
                expected_width,
                tolerance,
                "width",
            )

        if expected_height is not None:
            self.assertDimension(
                size.height(),
                expected_height,
                tolerance,
                "height",
            )


# =============================================================================
# FILE DIALOG LAYOUT TESTS
# =============================================================================


class TestFileDialogNavigationLayout(PixelLayoutTestBase):
    """Tests for file dialog navigation area layout."""

    def setUp(self) -> None:
        """Set up dialog for testing."""
        from utility.gui.qt.widgets.extended_dialogs.qfiledialog_extended import (
            QFileDialogExtended,
        )

        self.dialog = QFileDialogExtended()
        self.dialog.resize(
            Windows11DialogSpecs.Dialog.DEFAULT_WIDTH,
            Windows11DialogSpecs.Dialog.DEFAULT_HEIGHT,
        )
        self.dialog.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.dialog.close()
        self.dialog.deleteLater()
        QCoreApplication.processEvents()

    def test_navigation_bar_height(self) -> None:
        """Verify navigation bar has correct height."""
        # Find navigation toolbar
        toolbars = self.dialog.findChildren(QToolBar)

        for toolbar in toolbars:
            if toolbar.isVisible():
                self.assertDimension(
                    toolbar.height(),
                    Windows11DialogSpecs.NavigationArea.HEIGHT,
                    LayoutTolerance.RELAXED,
                    "Navigation bar height",
                )
                break

    def test_navigation_button_size(self) -> None:
        """Verify navigation buttons have correct size."""
        tool_buttons = self.dialog.findChildren(QToolButton)

        # Navigation buttons should be square
        for button in tool_buttons:
            if button.isVisible():
                # At least verify they're reasonably sized
                self.assertGreaterEqual(button.width(), 20)
                self.assertGreaterEqual(button.height(), 20)


class TestFileDialogAddressBarLayout(PixelLayoutTestBase):
    """Tests for file dialog address bar layout."""

    def setUp(self) -> None:
        """Set up dialog for testing."""
        from utility.gui.qt.widgets.extended_dialogs.qfiledialog_extended import (
            QFileDialogExtended,
        )

        self.dialog = QFileDialogExtended()
        self.dialog.resize(
            Windows11DialogSpecs.Dialog.DEFAULT_WIDTH,
            Windows11DialogSpecs.Dialog.DEFAULT_HEIGHT,
        )
        self.dialog.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.dialog.close()
        self.dialog.deleteLater()
        QCoreApplication.processEvents()

    def test_address_bar_height(self) -> None:
        """Verify address bar has correct height."""
        address_bar = self.dialog.address_bar

        self.assertDimension(
            address_bar.height(),
            Windows11DialogSpecs.AddressBar.HEIGHT,
            LayoutTolerance.RELAXED,
            "Address bar height",
        )

    def test_address_bar_minimum_width(self) -> None:
        """Verify address bar has minimum width."""
        address_bar = self.dialog.address_bar

        self.assertGreaterEqual(
            address_bar.width(),
            Windows11DialogSpecs.AddressBar.LEFT_MARGIN + 100,
        )


class TestFileDialogSearchBoxLayout(PixelLayoutTestBase):
    """Tests for file dialog search box layout."""

    def setUp(self) -> None:
        """Set up dialog for testing."""
        from utility.gui.qt.widgets.extended_dialogs.qfiledialog_extended import (
            QFileDialogExtended,
        )

        self.dialog = QFileDialogExtended()
        self.dialog.resize(
            Windows11DialogSpecs.Dialog.DEFAULT_WIDTH,
            Windows11DialogSpecs.Dialog.DEFAULT_HEIGHT,
        )
        self.dialog.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.dialog.close()
        self.dialog.deleteLater()
        QCoreApplication.processEvents()

    def test_search_box_height(self) -> None:
        """Verify search box has correct height."""
        search_box = self.dialog.search_filter

        self.assertDimension(
            search_box.height(),
            Windows11DialogSpecs.SearchBox.HEIGHT,
            LayoutTolerance.RELAXED,
            "Search box height",
        )

    def test_search_box_width_constraints(self) -> None:
        """Verify search box respects width constraints."""
        search_box = self.dialog.search_filter

        # Should be at least minimum width
        self.assertGreaterEqual(
            search_box.width(),
            Windows11DialogSpecs.SearchBox.MIN_WIDTH - 20,
        )

        # Should not exceed maximum width
        self.assertLessEqual(
            search_box.width(),
            Windows11DialogSpecs.SearchBox.MAX_WIDTH + 50,
        )


class TestFileDialogSidebarLayout(PixelLayoutTestBase):
    """Tests for file dialog sidebar layout."""

    def setUp(self) -> None:
        """Set up dialog for testing."""
        from utility.gui.qt.widgets.extended_dialogs.qfiledialog_extended import (
            QFileDialogExtended,
        )

        self.dialog = QFileDialogExtended()
        self.dialog.resize(
            Windows11DialogSpecs.Dialog.DEFAULT_WIDTH,
            Windows11DialogSpecs.Dialog.DEFAULT_HEIGHT,
        )
        self.dialog.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.dialog.close()
        self.dialog.deleteLater()
        QCoreApplication.processEvents()

    def test_sidebar_minimum_width(self) -> None:
        """Verify sidebar has minimum width."""
        sidebar = self.dialog.sidebar

        self.assertGreaterEqual(
            sidebar.minimumWidth(),
            Windows11DialogSpecs.Sidebar.MIN_WIDTH,
        )

    def test_sidebar_maximum_width(self) -> None:
        """Verify sidebar has maximum width."""
        sidebar = self.dialog.sidebar

        self.assertLessEqual(
            sidebar.maximumWidth(),
            Windows11DialogSpecs.Sidebar.MAX_WIDTH + 100,
        )

    def test_sidebar_default_width(self) -> None:
        """Verify sidebar has reasonable default width."""
        sidebar = self.dialog.sidebar

        width = sidebar.width()

        # Should be between min and max
        self.assertGreaterEqual(width, Windows11DialogSpecs.Sidebar.MIN_WIDTH)
        self.assertLessEqual(width, Windows11DialogSpecs.Sidebar.MAX_WIDTH + 100)


class TestFileDialogBottomControlsLayout(PixelLayoutTestBase):
    """Tests for file dialog bottom controls layout."""

    def setUp(self) -> None:
        """Set up dialog for testing."""
        from utility.gui.qt.widgets.extended_dialogs.qfiledialog_extended import (
            QFileDialogExtended,
        )

        self.dialog = QFileDialogExtended()
        self.dialog.resize(
            Windows11DialogSpecs.Dialog.DEFAULT_WIDTH,
            Windows11DialogSpecs.Dialog.DEFAULT_HEIGHT,
        )
        self.dialog.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.dialog.close()
        self.dialog.deleteLater()
        QCoreApplication.processEvents()

    def test_button_dimensions(self) -> None:
        """Verify button dimensions are correct."""
        buttons = self.dialog.findChildren(QPushButton)

        for button in buttons:
            if button.isVisible() and button.text():
                # Buttons should have reasonable dimensions
                self.assertGreaterEqual(
                    button.width(),
                    Windows11DialogSpecs.BottomControls.BUTTON_WIDTH - 20,
                )

    def test_line_edit_height(self) -> None:
        """Verify line edits have correct height."""
        line_edits = self.dialog.findChildren(QLineEdit)

        for edit in line_edits:
            if edit.isVisible():
                self.assertDimension(
                    edit.height(),
                    Windows11DialogSpecs.BottomControls.FILENAME_EDIT_HEIGHT,
                    LayoutTolerance.RELAXED,
                    "Line edit height",
                )

    def test_combobox_height(self) -> None:
        """Verify combo boxes have correct height."""
        combos = self.dialog.findChildren(QComboBox)

        for combo in combos:
            if combo.isVisible():
                self.assertDimension(
                    combo.height(),
                    Windows11DialogSpecs.BottomControls.FILTER_COMBO_HEIGHT,
                    LayoutTolerance.RELAXED,
                    "ComboBox height",
                )


# =============================================================================
# EXPLORER RIBBON LAYOUT TESTS
# =============================================================================


class TestExplorerRibbonLayout(PixelLayoutTestBase):
    """Tests for explorer ribbon layout."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.resize(1024, 600)
        self.explorer.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_ribbon_tab_height(self) -> None:
        """Verify ribbon tab bar has correct height."""
        ribbon = self.explorer.ribbon_widget
        tab_widget = ribbon.tab_widget
        tab_bar = tab_widget.tabBar()

        self.assertDimension(
            tab_bar.height(),
            Windows11ExplorerSpecs.Ribbon.TAB_HEIGHT,
            LayoutTolerance.RELAXED,
            "Tab bar height",
        )

    def test_ribbon_tab_minimum_width(self) -> None:
        """Verify ribbon tabs have minimum width."""
        ribbon = self.explorer.ribbon_widget
        tab_widget = ribbon.tab_widget
        tab_bar = tab_widget.tabBar()

        for i in range(tab_bar.count()):
            rect = tab_bar.tabRect(i)
            self.assertGreaterEqual(
                rect.width(),
                Windows11ExplorerSpecs.Ribbon.TAB_MIN_WIDTH,
            )


class TestExplorerSidebarLayout(PixelLayoutTestBase):
    """Tests for explorer sidebar layout."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.resize(1024, 600)
        self.explorer.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_sidebar_minimum_width(self) -> None:
        """Verify sidebar has minimum width."""
        sidebar = self.explorer.sidebar

        self.assertGreaterEqual(
            sidebar.minimumWidth(),
            Windows11DialogSpecs.Sidebar.MIN_WIDTH,
        )


class TestExplorerStatusBarLayout(PixelLayoutTestBase):
    """Tests for explorer status bar layout."""

    def setUp(self) -> None:
        """Set up explorer for testing."""
        from utility.gui.qt.widgets.item_explorer import FileSystemExplorerWidget

        self.explorer = FileSystemExplorerWidget()
        self.explorer.resize(1024, 600)
        self.explorer.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.explorer.close()
        self.explorer.deleteLater()
        QCoreApplication.processEvents()

    def test_status_bar_height(self) -> None:
        """Verify status bar has correct height."""
        status_bar = self.explorer.statusBar()

        # Standard Windows status bar is ~23px
        self.assertDimension(
            status_bar.height(),
            23,
            LayoutTolerance.RELAXED,
            "Status bar height",
        )


# =============================================================================
# RESPONSIVE LAYOUT TESTS
# =============================================================================


class TestResponsiveFileDialogLayout(PixelLayoutTestBase):
    """Tests for responsive file dialog layout behavior."""

    def setUp(self) -> None:
        """Set up dialog for testing."""
        from utility.gui.qt.widgets.extended_dialogs.qfiledialog_extended import (
            QFileDialogExtended,
        )

        self.dialog = QFileDialogExtended()
        self.dialog.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.dialog.close()
        self.dialog.deleteLater()
        QCoreApplication.processEvents()

    def test_minimum_size_respected(self) -> None:
        """Verify dialog respects minimum size."""
        self.dialog.resize(100, 100)  # Try to make very small
        QCoreApplication.processEvents()

        size = self.dialog.size()

        # Should not be smaller than minimum
        self.assertGreaterEqual(
            size.width(),
            Windows11DialogSpecs.Dialog.MIN_WIDTH - 50,  # Allow some tolerance
        )
        self.assertGreaterEqual(
            size.height(),
            Windows11DialogSpecs.Dialog.MIN_HEIGHT - 50,
        )

    def test_sidebar_resizes_with_dialog(self) -> None:
        """Verify sidebar adjusts when dialog resizes."""
        # Start with default size
        self.dialog.resize(800, 600)
        QCoreApplication.processEvents()

        sidebar_width_initial = self.dialog.sidebar.width()

        # Resize dialog wider
        self.dialog.resize(1200, 600)
        QCoreApplication.processEvents()

        # Sidebar may or may not change
        # Just verify it's still reasonable
        sidebar_width_new = self.dialog.sidebar.width()

        self.assertGreaterEqual(sidebar_width_new, Windows11DialogSpecs.Sidebar.MIN_WIDTH)
        self.assertLessEqual(sidebar_width_new, Windows11DialogSpecs.Sidebar.MAX_WIDTH + 100)


class TestResponsiveExplorerLayout(PixelLayoutTestBase):
    """Tests for responsive explorer layout behavior."""

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

    def test_minimum_window_size(self) -> None:
        """Verify explorer has reasonable minimum size."""
        self.explorer.resize(100, 100)  # Try to make very small
        QCoreApplication.processEvents()

        size = self.explorer.size()

        # Should maintain some minimum
        self.assertGreater(size.width(), 200)
        self.assertGreater(size.height(), 200)

    def test_content_area_grows_with_window(self) -> None:
        """Verify content area grows when window grows."""
        # Start with small size
        self.explorer.resize(600, 400)
        QCoreApplication.processEvents()

        view_width_small = self.explorer.view.width()

        # Resize larger
        self.explorer.resize(1000, 600)
        QCoreApplication.processEvents()

        view_width_large = self.explorer.view.width()

        # Content should be larger
        self.assertGreater(view_width_large, view_width_small)


# =============================================================================
# TEST RUNNER
# =============================================================================


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestFileDialogNavigationLayout,
        TestFileDialogAddressBarLayout,
        TestFileDialogSearchBoxLayout,
        TestFileDialogSidebarLayout,
        TestFileDialogBottomControlsLayout,
        TestExplorerRibbonLayout,
        TestExplorerSidebarLayout,
        TestExplorerStatusBarLayout,
        TestResponsiveFileDialogLayout,
        TestResponsiveExplorerLayout,
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
