"""Runtime theme application."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from .font_manager import FontManager
from .qt_stylesheet_builder import QtStylesheetBuilder
from .theme_model import Theme


class ThemeApplier(QtCore.QObject):
    themeChanged = QtCore.Signal(object)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.builder = QtStylesheetBuilder()
        self.font_manager = FontManager()
        self._aware_widgets: list[QtWidgets.QWidget] = []

    def build_stylesheet(self, theme: Theme) -> str:
        return self.builder.build(theme)

    def register_theme_aware_widget(self, widget: QtWidgets.QWidget) -> None:
        if widget not in self._aware_widgets:
            self._aware_widgets.append(widget)

    def apply_theme(self, theme: Theme, target: QtWidgets.QWidget | None = None) -> None:
        app = QtWidgets.QApplication.instance()
        stylesheet = self.build_stylesheet(theme)
        if app is not None:
            self.font_manager.apply_application_font(app, theme)
            app.setStyleSheet(stylesheet)
            app.setPalette(self._palette(theme))
        if target is not None:
            target.setStyleSheet(stylesheet)
        self.notify_theme_changed(theme)

    def notify_theme_changed(self, theme: Theme) -> None:
        for widget in list(self._aware_widgets):
            hook = getattr(widget, "apply_ghost_theme", None)
            if callable(hook):
                hook(theme)
        self.themeChanged.emit(theme)

    @staticmethod
    def _palette(theme: Theme) -> QtGui.QPalette:
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(theme.color("window.background")))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(theme.color("text.primary")))
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor(theme.color("viewport.background")))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(theme.color("panel.background")))
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor(theme.color("text.primary")))
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor(theme.color("button.background")))
        palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(theme.color("button.text")))
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(theme.color("selection.background")))
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(theme.color("selection.text")))
        return palette
