from __future__ import annotations

from typing import TYPE_CHECKING, Any

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QApplication, QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from utility.gui.qt.widgets.theme.theme_apply import apply_style, get_original_style
from utility.gui.qt.widgets.theme.theme_manager import ThemeManager

if TYPE_CHECKING:
    from qtpy.QtGui import QPalette


class ThemeDialog(QDialog):
    """Dialog for selecting and changing application themes."""

    def __init__(self, theme_manager: ThemeManager | None = None):
        """Initialize the theme dialog.

        Args:
            theme_manager: Optional ThemeManager for applying theme/style. If not provided, a default is created.
        """
        super().__init__()
        self._manager = theme_manager or ThemeManager()
        self._init_ui()

    @staticmethod
    def get_available_themes() -> tuple[str, ...]:
        """List all resources in the specified resource path."""
        manager = ThemeManager()
        return manager.get_available_themes()

    @staticmethod
    def get_default_styles() -> tuple[str, ...]:
        """Get the available styles."""
        return ThemeManager.get_default_styles()

    @classmethod
    def get_original_style(cls) -> str:
        """Get the original style of the application."""
        return get_original_style()

    @staticmethod
    def adjust_color(
        color: Any,
        lightness: int = 100,
        saturation: int = 100,
        hue_shift: int = 0,
    ) -> QColor:
        """
        Adjusts the color's lightness, saturation, and hue.

        Args:
            color: Input color to adjust.
            lightness: Percentage of lightness adjustment.
            saturation: Percentage of saturation adjustment.
            hue_shift: Degrees to shift the hue.

        Returns:
            Adjusted QColor instance.
        """
        qcolor = QColor(color)
        if not isinstance(qcolor, QColor):
            qcolor = QColor(qcolor)
        h, s, v, _ = qcolor.getHsv()
        assert h is not None, "Hue is None"
        assert s is not None, "Saturation is None"
        assert v is not None, "Value is None"
        s = max(0, min(255, s * saturation // 100))
        return qcolor

    def _init_ui(self):
        """Set up the user interface for the theme dialog."""
        self.setWindowTitle("Theme Selection")
        self.setWindowFlags(Qt.WindowType.WindowCloseButtonHint)

        # Theme selection label and combo box (themes and styles in one list for simple UI)
        self._theme_label: QLabel = QLabel("Select Theme:")
        self._theme_combo_box: QComboBox = QComboBox()
        themes = self.get_available_themes()
        styles = self.get_default_styles()
        self._theme_combo_box.addItems(sorted(set(themes) | set(styles)))
        self._theme_combo_box.currentTextChanged.connect(self.on_theme_changed)
        self._theme_names: frozenset[str] = frozenset(t.lower() for t in themes)
        self._style_names: frozenset[str] = frozenset(s.lower() for s in styles)

        # Buttons
        self._ok_button: QPushButton = QPushButton("Apply")
        self._ok_button.clicked.connect(lambda: self.accept())
        self._cancel_button: QPushButton = QPushButton("Cancel")
        self._cancel_button.clicked.connect(lambda: self.reject())

        # Layout
        self._button_layout: QHBoxLayout = QHBoxLayout()
        self._button_layout.addWidget(self._ok_button)
        self._button_layout.addWidget(self._cancel_button)

        self._main_layout: QVBoxLayout = QVBoxLayout()
        self._main_layout.addWidget(self._theme_label)
        self._main_layout.addWidget(self._theme_combo_box)
        self._main_layout.addLayout(self._button_layout)

        self.setLayout(self._main_layout)

    def on_theme_changed(self, selection: str):
        """Handle theme/style change: apply via ThemeManager if selection is a known theme or style."""
        if not selection:
            return
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        sel_lower = selection.lower()
        if sel_lower in self._theme_names:
            style_name = self._manager.get_original_style()
            self._manager.apply_theme_and_style(selection, style_name, fallback_theme="sourcegraph-dark", fallback_style="Fusion")
        elif sel_lower in self._style_names:
            themes = self._manager.get_available_themes()
            theme_name = themes[0] if themes else "sourcegraph-dark"
            self._manager.apply_theme_and_style(theme_name, selection, fallback_theme="sourcegraph-dark", fallback_style="Fusion")

    @classmethod
    def apply_style(
        cls,
        app: QApplication,
        sheet: str | None = None,
        style: str | None = None,
        palette: QPalette | None = None,
    ):
        """Apply the style, sheet, and palette to the application."""
        apply_style(app, sheet=sheet, style=style, palette=palette)

    def get_theme(self) -> str:
        """
        Get the selected theme.

        Returns:
            The name of the selected theme.
        """
        return self._theme_combo_box.currentText()
