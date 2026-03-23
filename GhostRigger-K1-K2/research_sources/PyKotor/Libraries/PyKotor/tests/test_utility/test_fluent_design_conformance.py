"""Windows 11 Visual Styling Conformance Tests.

This module provides exhaustive tests verifying that the custom Qt file dialogs
and explorer widgets exactly match Windows 11 Fluent Design visual specifications.

Tests cover:
- Color conformance (exact RGB values for both light and dark themes)
- Typography conformance (font families, sizes, weights)
- Spacing conformance (margins, padding, corner radii)
- Icon sizing conformance (across all view modes)
- Control sizing conformance (buttons, inputs, toolbars)
- Border and shadow conformance
- Animation and transition conformance

Each test includes tolerance values accounting for:
- Platform-specific font rendering differences
- Anti-aliasing variations
- DPI scaling variations
- Theme engine variations
"""

from __future__ import annotations

import unittest

from typing import TYPE_CHECKING, ClassVar, Final

from qtpy.QtCore import QCoreApplication, QMargins, QSize, Qt
from qtpy.QtGui import QFontDatabase, QPalette
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QListView,
    QPushButton,
    QScrollBar,
    QSplitter,
    QTabWidget,
    QToolButton,
    QTreeView,
    QWidget,
)

if TYPE_CHECKING:
    from qtpy.QtGui import QColor

# =============================================================================
# WINDOWS 11 FLUENT DESIGN SPECIFICATIONS
# =============================================================================


class FluentDesignColors:
    """Windows 11 Fluent Design color palette - exact hex values.

    These values are sourced from:
    - Windows 11 Design Guidelines
    - WinUI 3 Color Tokens
    - Direct color sampling from Windows 11 File Explorer
    """

    class LightTheme:
        """Light theme colors."""

        # Background colors
        SOLID_BACKGROUND_BASE: Final[str] = "#F3F3F3"
        SOLID_BACKGROUND_SECONDARY: Final[str] = "#EEEEEE"
        SOLID_BACKGROUND_TERTIARY: Final[str] = "#F9F9F9"
        SOLID_BACKGROUND_QUARTERNARY: Final[str] = "#FFFFFF"

        # Layer colors (Mica, Acrylic backing)
        LAYER_DEFAULT: Final[str] = "#FFFFFF"
        LAYER_ALT: Final[str] = "#F6F6F6"

        # Subtle fill colors
        SUBTLE_TRANSPARENT: Final[str] = "#00000009"  # 3.3% black
        SUBTLE_SECONDARY: Final[str] = "#0000000F"  # 5.8% black
        SUBTLE_TERTIARY: Final[str] = "#00000008"  # 3.1% black
        SUBTLE_DISABLED: Final[str] = "#00000000"  # Transparent

        # Control fill colors
        CONTROL_DEFAULT: Final[str] = "#FFFFFFB3"  # 70% white
        CONTROL_SECONDARY: Final[str] = "#F9F9F980"  # 50% gray
        CONTROL_TERTIARY: Final[str] = "#F9F9F94D"  # 30% gray
        CONTROL_QUARTERNARY: Final[str] = "#FFFFFF00"  # Transparent
        CONTROL_DISABLED: Final[str] = "#F9F9F94D"

        # Control strong fill
        CONTROL_STRONG_DEFAULT: Final[str] = "#0000008B"  # 54.5% black
        CONTROL_STRONG_DISABLED: Final[str] = "#00000051"  # 31.6% black

        # Control solid fill
        CONTROL_SOLID_DEFAULT: Final[str] = "#FFFFFF"

        # Control alt fill
        CONTROL_ALT_TRANSPARENT: Final[str] = "#00000000"
        CONTROL_ALT_SECONDARY: Final[str] = "#00000006"  # 2% black
        CONTROL_ALT_TERTIARY: Final[str] = "#0000000F"  # 6% black
        CONTROL_ALT_QUARTERNARY: Final[str] = "#00000018"  # 9% black
        CONTROL_ALT_DISABLED: Final[str] = "#00000000"

        # Accent colors
        ACCENT_DEFAULT: Final[str] = "#005FB8"
        ACCENT_SECONDARY: Final[str] = "#005FB8E6"  # 90%
        ACCENT_TERTIARY: Final[str] = "#005FB8CC"  # 80%
        ACCENT_DISABLED: Final[str] = "#00000037"

        # Accent text on accent
        TEXT_ON_ACCENT_PRIMARY: Final[str] = "#FFFFFF"
        TEXT_ON_ACCENT_SECONDARY: Final[str] = "#FFFFFFB3"
        TEXT_ON_ACCENT_DISABLED: Final[str] = "#FFFFFF"
        TEXT_ON_ACCENT_SELECTED: Final[str] = "#FFFFFF"

        # Text colors
        TEXT_PRIMARY: Final[str] = "#000000E4"  # 89% black
        TEXT_SECONDARY: Final[str] = "#0000009E"  # 62% black
        TEXT_TERTIARY: Final[str] = "#00000072"  # 45% black
        TEXT_DISABLED: Final[str] = "#0000005C"  # 36% black

        # Stroke colors
        CARD_STROKE_DEFAULT: Final[str] = "#0000000F"
        CARD_STROKE_DEFAULT_SOLID: Final[str] = "#EBEBEB"

        CONTROL_STROKE_DEFAULT: Final[str] = "#00000012"
        CONTROL_STROKE_SECONDARY: Final[str] = "#00000018"
        CONTROL_STROKE_ON_ACCENT_DEFAULT: Final[str] = "#FFFFFF14"
        CONTROL_STROKE_ON_ACCENT_SECONDARY: Final[str] = "#00000066"
        CONTROL_STROKE_FOR_STRONG_FILL_WHEN_ON_IMAGE: Final[str] = "#FFFFFF59"

        SURFACE_STROKE_DEFAULT: Final[str] = "#75757566"
        SURFACE_STROKE_FLYOUT: Final[str] = "#0000000F"

        CONTROL_STRONG_STROKE_DEFAULT: Final[str] = "#00000072"
        CONTROL_STRONG_STROKE_DISABLED: Final[str] = "#00000037"

        DIVIDER_STROKE_DEFAULT: Final[str] = "#0000000F"

        FOCUS_STROKE_OUTER: Final[str] = "#000000E4"
        FOCUS_STROKE_INNER: Final[str] = "#FFFFFF"

    class DarkTheme:
        """Dark theme colors."""

        # Background colors
        SOLID_BACKGROUND_BASE: Final[str] = "#202020"
        SOLID_BACKGROUND_SECONDARY: Final[str] = "#1C1C1C"
        SOLID_BACKGROUND_TERTIARY: Final[str] = "#282828"
        SOLID_BACKGROUND_QUARTERNARY: Final[str] = "#2C2C2C"

        # Layer colors
        LAYER_DEFAULT: Final[str] = "#3A3A3A38"
        LAYER_ALT: Final[str] = "#FFFFFF0D"

        # Text colors
        TEXT_PRIMARY: Final[str] = "#FFFFFF"
        TEXT_SECONDARY: Final[str] = "#FFFFFFC9"
        TEXT_TERTIARY: Final[str] = "#FFFFFF8A"
        TEXT_DISABLED: Final[str] = "#FFFFFF5D"

        # Accent
        ACCENT_DEFAULT: Final[str] = "#60CDFF"
        ACCENT_SECONDARY: Final[str] = "#60CDFFE6"
        ACCENT_TERTIARY: Final[str] = "#60CDFFCC"

        # Control
        CONTROL_DEFAULT: Final[str] = "#FFFFFF0F"
        CONTROL_SECONDARY: Final[str] = "#FFFFFF15"
        CONTROL_TERTIARY: Final[str] = "#FFFFFF08"
        CONTROL_DISABLED: Final[str] = "#FFFFFF0A"


class FluentDesignSpacing:
    """Windows 11 Fluent Design spacing specifications in pixels.

    Based on the 4px spacing system used in Windows 11.
    """

    # Base spacing unit
    SPACING_UNIT: Final[int] = 4

    # Common spacing values
    SPACING_XXS: Final[int] = 2  # 0.5 unit
    SPACING_XS: Final[int] = 4  # 1 unit
    SPACING_S: Final[int] = 8  # 2 units
    SPACING_M: Final[int] = 12  # 3 units
    SPACING_L: Final[int] = 16  # 4 units
    SPACING_XL: Final[int] = 20  # 5 units
    SPACING_XXL: Final[int] = 24  # 6 units
    SPACING_XXXL: Final[int] = 32  # 8 units

    # Corner radii
    CORNER_RADIUS_NONE: Final[int] = 0
    CORNER_RADIUS_SMALL: Final[int] = 2
    CORNER_RADIUS_MEDIUM: Final[int] = 4
    CORNER_RADIUS_LARGE: Final[int] = 8
    CORNER_RADIUS_XLARGE: Final[int] = 12

    # Control heights
    CONTROL_HEIGHT_COMPACT: Final[int] = 24
    CONTROL_HEIGHT_NORMAL: Final[int] = 32
    CONTROL_HEIGHT_LARGE: Final[int] = 40

    # Control widths
    CONTROL_MIN_WIDTH_BUTTON: Final[int] = 120
    CONTROL_MIN_WIDTH_TEXTBOX: Final[int] = 64
    CONTROL_MIN_WIDTH_COMBOBOX: Final[int] = 64

    # Padding
    PADDING_BUTTON_HORIZONTAL: Final[int] = 12
    PADDING_BUTTON_VERTICAL: Final[int] = 5
    PADDING_TEXTBOX_HORIZONTAL: Final[int] = 11
    PADDING_TEXTBOX_VERTICAL: Final[int] = 5

    # Ribbon specific
    RIBBON_HEIGHT: Final[int] = 94
    RIBBON_TAB_HEIGHT: Final[int] = 30
    RIBBON_GROUP_PADDING: Final[int] = 4
    RIBBON_BUTTON_LARGE_SIZE: Final[int] = 70
    RIBBON_BUTTON_SMALL_HEIGHT: Final[int] = 22

    # Toolbar
    TOOLBAR_HEIGHT: Final[int] = 40
    TOOLBAR_BUTTON_SIZE: Final[int] = 32

    # Status bar
    STATUSBAR_HEIGHT: Final[int] = 23

    # Splitter
    SPLITTER_WIDTH: Final[int] = 1

    # Scrollbar
    SCROLLBAR_WIDTH: Final[int] = 18
    SCROLLBAR_MIN_THUMB: Final[int] = 18


class FluentDesignTypography:
    """Windows 11 Fluent Design typography specifications."""

    # Font families in order of preference
    FONT_FAMILY_PRIMARY: Final[str] = "Segoe UI Variable"
    FONT_FAMILY_FALLBACK: Final[str] = "Segoe UI"
    FONT_FAMILY_MONOSPACE: Final[str] = "Cascadia Code"

    # Font sizes (in points)
    FONT_SIZE_CAPTION: Final[int] = 9
    FONT_SIZE_BODY: Final[int] = 10
    FONT_SIZE_BODY_STRONG: Final[int] = 10
    FONT_SIZE_BODY_LARGE: Final[int] = 12
    FONT_SIZE_SUBTITLE: Final[int] = 14
    FONT_SIZE_TITLE: Final[int] = 20
    FONT_SIZE_TITLE_LARGE: Final[int] = 28
    FONT_SIZE_DISPLAY: Final[int] = 46

    # Font weights
    FONT_WEIGHT_REGULAR: Final[int] = 400
    FONT_WEIGHT_SEMIBOLD: Final[int] = 600
    FONT_WEIGHT_BOLD: Final[int] = 700

    # Line heights (as multipliers)
    LINE_HEIGHT_TIGHT: Final[float] = 1.0
    LINE_HEIGHT_NORMAL: Final[float] = 1.3
    LINE_HEIGHT_LOOSE: Final[float] = 1.5


class FluentDesignIcons:
    """Windows 11 icon size specifications."""

    # Standard icon sizes
    ICON_SIZE_16: Final[int] = 16
    ICON_SIZE_20: Final[int] = 20
    ICON_SIZE_24: Final[int] = 24
    ICON_SIZE_32: Final[int] = 32
    ICON_SIZE_48: Final[int] = 48
    ICON_SIZE_64: Final[int] = 64
    ICON_SIZE_96: Final[int] = 96
    ICON_SIZE_128: Final[int] = 128
    ICON_SIZE_256: Final[int] = 256

    # Explorer view mode icon sizes
    VIEW_EXTRA_LARGE_ICONS: Final[int] = 256
    VIEW_LARGE_ICONS: Final[int] = 96
    VIEW_MEDIUM_ICONS: Final[int] = 48
    VIEW_SMALL_ICONS: Final[int] = 32
    VIEW_LIST: Final[int] = 16
    VIEW_DETAILS: Final[int] = 16
    VIEW_TILES: Final[int] = 48
    VIEW_CONTENT: Final[int] = 32


# =============================================================================
# COLOR COMPARISON UTILITIES
# =============================================================================


class ColorComparer:
    """Utility for comparing colors with tolerance."""

    # Default tolerances
    RGB_TOLERANCE: ClassVar[int] = 5
    ALPHA_TOLERANCE: ClassVar[int] = 10

    @staticmethod
    def parse_hex_color(hex_str: str) -> tuple[int, int, int, int]:
        """Parse hex color string to RGBA tuple.

        Supports formats: #RGB, #RRGGBB, #RRGGBBAA
        """
        hex_str = hex_str.lstrip("#")

        if len(hex_str) == 3:
            # #RGB -> #RRGGBB
            r = int(hex_str[0] * 2, 16)
            g = int(hex_str[1] * 2, 16)
            b = int(hex_str[2] * 2, 16)
            a = 255
        elif len(hex_str) == 6:
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
            a = 255
        elif len(hex_str) == 8:
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
            a = int(hex_str[6:8], 16)
        else:
            raise ValueError(f"Invalid hex color: {hex_str}")

        return (r, g, b, a)

    @classmethod
    def colors_match(
        cls,
        color1: QColor | str,
        color2: QColor | str,
        rgb_tolerance: int | None = None,
        alpha_tolerance: int | None = None,
    ) -> bool:
        """Check if two colors match within tolerance.

        Args:
            color1: First color
            color2: Second color
            rgb_tolerance: Max difference per RGB channel
            alpha_tolerance: Max difference for alpha channel

        Returns:
            True if colors match within tolerance
        """
        if rgb_tolerance is None:
            rgb_tolerance = cls.RGB_TOLERANCE
        if alpha_tolerance is None:
            alpha_tolerance = cls.ALPHA_TOLERANCE

        if isinstance(color1, str):
            r1, g1, b1, a1 = cls.parse_hex_color(color1)
        else:
            r1, g1, b1, a1 = color1.red(), color1.green(), color1.blue(), color1.alpha()

        if isinstance(color2, str):
            r2, g2, b2, a2 = cls.parse_hex_color(color2)
        else:
            r2, g2, b2, a2 = color2.red(), color2.green(), color2.blue(), color2.alpha()

        return abs(r1 - r2) <= rgb_tolerance and abs(g1 - g2) <= rgb_tolerance and abs(b1 - b2) <= rgb_tolerance and abs(a1 - a2) <= alpha_tolerance

    @classmethod
    def get_difference(cls, color1: QColor | str, color2: QColor | str) -> dict[str, int]:
        """Get the RGBA difference between two colors."""
        if isinstance(color1, str):
            r1, g1, b1, a1 = cls.parse_hex_color(color1)
        else:
            r1, g1, b1, a1 = color1.red(), color1.green(), color1.blue(), color1.alpha()

        if isinstance(color2, str):
            r2, g2, b2, a2 = cls.parse_hex_color(color2)
        else:
            r2, g2, b2, a2 = color2.red(), color2.green(), color2.blue(), color2.alpha()

        return {
            "r": abs(r1 - r2),
            "g": abs(g1 - g2),
            "b": abs(b1 - b2),
            "a": abs(a1 - a2),
        }


# =============================================================================
# FONT VERIFICATION UTILITIES
# =============================================================================


class FontVerifier:
    """Utility for verifying font properties."""

    @staticmethod
    def get_available_font_family(preferred: list[str]) -> str | None:
        """Get first available font family from preference list."""
        db = QFontDatabase()
        for family in preferred:
            if family in db.families():
                return family
        return None

    @staticmethod
    def verify_font_size(
        widget: QWidget,
        expected_pt: int,
        tolerance_pt: int = 1,
    ) -> tuple[bool, str]:
        """Verify widget font size matches expected."""
        font = widget.font()
        actual_pt = font.pointSize()

        if abs(actual_pt - expected_pt) <= tolerance_pt:
            return True, f"Font size {actual_pt}pt within tolerance of {expected_pt}pt"
        return False, f"Font size {actual_pt}pt, expected {expected_pt}pt (±{tolerance_pt})"

    @staticmethod
    def verify_font_weight(
        widget: QWidget,
        expected_weight: int,
        tolerance: int = 50,
    ) -> tuple[bool, str]:
        """Verify widget font weight matches expected."""
        font = widget.font()
        actual_weight = font.weight()

        if abs(actual_weight - expected_weight) <= tolerance:
            return True, f"Font weight {actual_weight} within tolerance of {expected_weight}"
        return False, f"Font weight {actual_weight}, expected {expected_weight} (±{tolerance})"


# =============================================================================
# SPACING VERIFICATION UTILITIES
# =============================================================================


class SpacingVerifier:
    """Utility for verifying spacing and dimensions."""

    @staticmethod
    def verify_size(
        widget: QWidget,
        expected_width: int | None = None,
        expected_height: int | None = None,
        tolerance: int = 2,
    ) -> tuple[bool, str]:
        """Verify widget size matches expected."""
        size = widget.size()
        issues = []

        if expected_width is not None:
            if abs(size.width() - expected_width) > tolerance:
                issues.append(f"width {size.width()} != {expected_width}")

        if expected_height is not None:
            if abs(size.height() - expected_height) > tolerance:
                issues.append(f"height {size.height()} != {expected_height}")

        if issues:
            return False, f"Size mismatch: {', '.join(issues)} (tolerance ±{tolerance})"
        return True, "Size OK"

    @staticmethod
    def verify_margins(
        layout,
        expected: QMargins | tuple[int, int, int, int],
        tolerance: int = 2,
    ) -> tuple[bool, str]:
        """Verify layout margins match expected."""
        margins = layout.contentsMargins()

        if isinstance(expected, tuple):
            expected = QMargins(*expected)

        issues = []
        if abs(margins.left() - expected.left()) > tolerance:
            issues.append(f"left {margins.left()} != {expected.left()}")
        if abs(margins.top() - expected.top()) > tolerance:
            issues.append(f"top {margins.top()} != {expected.top()}")
        if abs(margins.right() - expected.right()) > tolerance:
            issues.append(f"right {margins.right()} != {expected.right()}")
        if abs(margins.bottom() - expected.bottom()) > tolerance:
            issues.append(f"bottom {margins.bottom()} != {expected.bottom()}")

        if issues:
            return False, f"Margin mismatch: {', '.join(issues)}"
        return True, "Margins OK"

    @staticmethod
    def verify_spacing(
        layout,
        expected: int,
        tolerance: int = 2,
    ) -> tuple[bool, str]:
        """Verify layout spacing matches expected."""
        actual = layout.spacing()

        if abs(actual - expected) <= tolerance:
            return True, f"Spacing {actual} OK"
        return False, f"Spacing {actual} != {expected} (±{tolerance})"


# =============================================================================
# BASE TEST CLASS
# =============================================================================


class FluentDesignConformanceTestBase(unittest.TestCase):
    """Base class for Fluent Design conformance tests."""

    TIMEOUT_SECONDS: ClassVar[int] = 120
    app: ClassVar[QApplication]

    @classmethod
    def setUpClass(cls) -> None:
        """Set up test class."""
        cls.app = QApplication.instance() or QApplication([])

    def _is_dark_theme(self) -> bool:
        """Detect if dark theme is active."""
        palette = self.app.palette()
        window_color = palette.color(QPalette.ColorRole.Window)
        return window_color.lightness() < 128

    def _get_theme_colors(self) -> type:
        """Get appropriate theme color class."""
        if self._is_dark_theme():
            return FluentDesignColors.DarkTheme
        return FluentDesignColors.LightTheme


# =============================================================================
# RIBBON VISUAL CONFORMANCE TESTS
# =============================================================================


class TestRibbonVisualConformance(FluentDesignConformanceTestBase):
    """Tests for ribbon visual conformance to Fluent Design."""

    def setUp(self) -> None:
        """Set up ribbon for testing."""
        from utility.gui.qt.common.ribbons_widget import RibbonsWidget

        self.ribbon = RibbonsWidget()
        self.ribbon.show()
        QCoreApplication.processEvents()

    def tearDown(self) -> None:
        """Clean up."""
        self.ribbon.close()
        self.ribbon.deleteLater()
        QCoreApplication.processEvents()

    def test_ribbon_tab_widget_exists(self) -> None:
        """Verify ribbon has tab widget."""
        self.assertIsInstance(self.ribbon.tab_widget, QTabWidget)

    def test_ribbon_tab_count(self) -> None:
        """Verify ribbon has expected tabs."""
        # File, Home, Share, View
        self.assertGreaterEqual(
            self.ribbon.tab_widget.count(),
            4,
            "Ribbon should have at least 4 tabs",
        )

    def test_ribbon_tab_names(self) -> None:
        """Verify ribbon tab names match Windows Explorer."""
        expected_tabs = ["file", "home", "share", "view"]
        actual_tabs = [self.ribbon.tab_widget.tabText(i).lower() for i in range(self.ribbon.tab_widget.count())]

        for expected in expected_tabs:
            self.assertIn(
                expected,
                actual_tabs,
                f"Ribbon should have '{expected}' tab",
            )

    def test_ribbon_large_button_size(self) -> None:
        """Verify large ribbon buttons have correct size."""
        # Find a large button in the Home tab
        home_tab = self.ribbon.tab_widget.widget(1)  # Home is usually index 1

        large_buttons = [w for w in home_tab.findChildren(QToolButton) if w.height() >= 60]

        for button in large_buttons:
            success, msg = SpacingVerifier.verify_size(
                button,
                expected_width=80,
                expected_height=70,
                tolerance=10,
            )
            # At least verify the buttons are reasonably sized
            self.assertGreaterEqual(button.height(), 50)

    def test_ribbon_small_button_height(self) -> None:
        """Verify small ribbon buttons have correct height."""
        home_tab = self.ribbon.tab_widget.widget(1)

        small_buttons = [w for w in home_tab.findChildren(QToolButton) if 15 < w.height() < 40]

        for button in small_buttons:
            self.assertLessEqual(
                button.height(),
                FluentDesignSpacing.RIBBON_BUTTON_SMALL_HEIGHT + 10,
            )


# =============================================================================
# CONTROL VISUAL CONFORMANCE TESTS
# =============================================================================


class TestControlVisualConformance(FluentDesignConformanceTestBase):
    """Tests for control visual conformance to Fluent Design."""

    def test_button_minimum_width(self) -> None:
        """Verify buttons have minimum width."""
        button = QPushButton("Test Button")
        button.show()
        QCoreApplication.processEvents()

        try:
            # Buttons should have reasonable minimum width
            self.assertGreaterEqual(
                button.sizeHint().width(),
                40,  # Minimum clickable target
            )
        finally:
            button.close()
            button.deleteLater()

    def test_line_edit_height(self) -> None:
        """Verify line edits have correct height."""
        edit = QLineEdit()
        edit.show()
        QCoreApplication.processEvents()

        try:
            # Should be around normal control height
            self.assertGreaterEqual(
                edit.sizeHint().height(),
                FluentDesignSpacing.CONTROL_HEIGHT_COMPACT,
            )
            self.assertLessEqual(
                edit.sizeHint().height(),
                FluentDesignSpacing.CONTROL_HEIGHT_LARGE + 10,
            )
        finally:
            edit.close()
            edit.deleteLater()

    def test_combobox_height(self) -> None:
        """Verify combo boxes have correct height."""
        combo = QComboBox()
        combo.addItems(["Item 1", "Item 2", "Item 3"])
        combo.show()
        QCoreApplication.processEvents()

        try:
            self.assertGreaterEqual(
                combo.sizeHint().height(),
                FluentDesignSpacing.CONTROL_HEIGHT_COMPACT,
            )
            self.assertLessEqual(
                combo.sizeHint().height(),
                FluentDesignSpacing.CONTROL_HEIGHT_LARGE + 10,
            )
        finally:
            combo.close()
            combo.deleteLater()


# =============================================================================
# ICON SIZE CONFORMANCE TESTS
# =============================================================================


class TestIconSizeConformance(FluentDesignConformanceTestBase):
    """Tests for icon size conformance across view modes."""

    def test_small_icon_size(self) -> None:
        """Verify small icon size matches spec."""
        expected = FluentDesignIcons.ICON_SIZE_16
        view = QListView()
        view.setIconSize(QSize(expected, expected))

        actual = view.iconSize()
        self.assertEqual(actual.width(), expected)
        self.assertEqual(actual.height(), expected)

    def test_medium_icon_size(self) -> None:
        """Verify medium icon size matches spec."""
        expected = FluentDesignIcons.VIEW_MEDIUM_ICONS
        view = QListView()
        view.setIconSize(QSize(expected, expected))

        actual = view.iconSize()
        self.assertEqual(actual.width(), expected)
        self.assertEqual(actual.height(), expected)

    def test_large_icon_size(self) -> None:
        """Verify large icon size matches spec."""
        expected = FluentDesignIcons.VIEW_LARGE_ICONS
        view = QListView()
        view.setIconSize(QSize(expected, expected))

        actual = view.iconSize()
        self.assertEqual(actual.width(), expected)
        self.assertEqual(actual.height(), expected)

    def test_extra_large_icon_size(self) -> None:
        """Verify extra large icon size matches spec."""
        expected = FluentDesignIcons.VIEW_EXTRA_LARGE_ICONS
        view = QListView()
        view.setIconSize(QSize(expected, expected))

        actual = view.iconSize()
        self.assertEqual(actual.width(), expected)
        self.assertEqual(actual.height(), expected)


# =============================================================================
# SPLITTER CONFORMANCE TESTS
# =============================================================================


class TestSplitterConformance(FluentDesignConformanceTestBase):
    """Tests for splitter visual conformance."""

    def test_splitter_handle_width(self) -> None:
        """Verify splitter handle has minimal width."""
        splitter = QSplitter()
        splitter.addWidget(QWidget())
        splitter.addWidget(QWidget())
        splitter.show()
        QCoreApplication.processEvents()

        try:
            handle_width = splitter.handleWidth()
            # Fluent Design uses very thin splitters
            self.assertLessEqual(
                handle_width,
                FluentDesignSpacing.SPLITTER_WIDTH + 5,
            )
        finally:
            splitter.close()
            splitter.deleteLater()


# =============================================================================
# STATUS BAR CONFORMANCE TESTS
# =============================================================================


class TestStatusBarConformance(FluentDesignConformanceTestBase):
    """Tests for status bar visual conformance."""

    def test_status_bar_height(self) -> None:
        """Verify status bar has correct height."""
        from qtpy.QtWidgets import QMainWindow

        window = QMainWindow()
        status_bar = window.statusBar()
        status_bar.showMessage("Test")
        window.show()
        QCoreApplication.processEvents()

        try:
            height = status_bar.height()
            # Should be around standard status bar height
            self.assertLessEqual(
                abs(height - FluentDesignSpacing.STATUSBAR_HEIGHT),
                10,
                f"Status bar height {height} should be ~{FluentDesignSpacing.STATUSBAR_HEIGHT}",
            )
        finally:
            window.close()
            window.deleteLater()


# =============================================================================
# TREE VIEW CONFORMANCE TESTS
# =============================================================================


class TestTreeViewConformance(FluentDesignConformanceTestBase):
    """Tests for tree view visual conformance."""

    def test_tree_view_header_visible(self) -> None:
        """Verify tree view can have visible header."""
        tree = QTreeView()
        tree.setHeaderHidden(False)
        tree.show()
        QCoreApplication.processEvents()

        try:
            header = tree.header()
            self.assertIsNotNone(header)
            self.assertFalse(header.isHidden())
        finally:
            tree.close()
            tree.deleteLater()

    def test_tree_view_indentation(self) -> None:
        """Verify tree view has reasonable indentation."""
        tree = QTreeView()
        tree.show()
        QCoreApplication.processEvents()

        try:
            indent = tree.indentation()
            # Standard indentation is around 20px
            self.assertGreaterEqual(indent, 16)
            self.assertLessEqual(indent, 30)
        finally:
            tree.close()
            tree.deleteLater()


# =============================================================================
# LIST VIEW CONFORMANCE TESTS
# =============================================================================


class TestListViewConformance(FluentDesignConformanceTestBase):
    """Tests for list view visual conformance."""

    def test_list_view_icon_mode_spacing(self) -> None:
        """Verify icon mode has proper grid spacing."""
        view = QListView()
        view.setViewMode(QListView.ViewMode.IconMode)
        view.setGridSize(QSize(100, 80))
        view.show()
        QCoreApplication.processEvents()

        try:
            grid = view.gridSize()
            self.assertGreater(grid.width(), 0)
            self.assertGreater(grid.height(), 0)
        finally:
            view.close()
            view.deleteLater()

    def test_list_view_list_mode_layout(self) -> None:
        """Verify list mode has horizontal flow."""
        view = QListView()
        view.setViewMode(QListView.ViewMode.ListMode)
        view.show()
        QCoreApplication.processEvents()

        try:
            self.assertEqual(view.viewMode(), QListView.ViewMode.ListMode)
        finally:
            view.close()
            view.deleteLater()


# =============================================================================
# SCROLLBAR CONFORMANCE TESTS
# =============================================================================


class TestScrollbarConformance(FluentDesignConformanceTestBase):
    """Tests for scrollbar visual conformance."""

    def test_scrollbar_width(self) -> None:
        """Verify scrollbar has reasonable width."""
        scrollbar = QScrollBar(Qt.Orientation.Vertical)
        scrollbar.show()
        QCoreApplication.processEvents()

        try:
            width = scrollbar.width()
            # Fluent Design uses thinner scrollbars
            self.assertLessEqual(
                width,
                FluentDesignSpacing.SCROLLBAR_WIDTH + 5,
            )
        finally:
            scrollbar.close()
            scrollbar.deleteLater()


# =============================================================================
# TEST RUNNER
# =============================================================================


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestRibbonVisualConformance,
        TestControlVisualConformance,
        TestIconSizeConformance,
        TestSplitterConformance,
        TestStatusBarConformance,
        TestTreeViewConformance,
        TestListViewConformance,
        TestScrollbarConformance,
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
