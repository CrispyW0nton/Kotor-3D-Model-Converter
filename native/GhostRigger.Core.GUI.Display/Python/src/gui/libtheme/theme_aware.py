"""Small mixins for theme/layout-aware Qt widgets."""

from __future__ import annotations

from PySide6 import QtWidgets

from .layout_model import LayoutDefinition
from .theme_model import Theme


class ThemeAwareMixin:
    """Opt-in hook surface for widgets registered with ThemeManager."""

    def on_theme_changed(self, theme: Theme) -> None:
        return None

    def apply_theme_tokens(self, theme: Theme) -> None:
        return None

    def apply_ghost_theme(self, theme: Theme) -> None:
        self.apply_theme_tokens(theme)
        self.on_theme_changed(theme)


class LayoutAwareMixin:
    """Opt-in hook surface for widgets registered with LayoutManager callers."""

    def on_layout_changed(self, layout: LayoutDefinition) -> None:
        return None

    def apply_layout_metrics(self, layout: LayoutDefinition) -> None:
        return None

    def apply_ghost_layout(self, layout: LayoutDefinition) -> None:
        self.apply_layout_metrics(layout)
        self.on_layout_changed(layout)


class ThemedWidget(ThemeAwareMixin, LayoutAwareMixin, QtWidgets.QWidget):
    pass


class ThemedDialog(ThemeAwareMixin, LayoutAwareMixin, QtWidgets.QDialog):
    pass


class ThemedMainWindow(ThemeAwareMixin, LayoutAwareMixin, QtWidgets.QMainWindow):
    pass
