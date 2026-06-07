"""Font helpers for theme application."""

from __future__ import annotations

from PySide6 import QtGui, QtWidgets

from .theme_model import Theme


class FontManager:
    def apply_application_font(self, app: QtWidgets.QApplication, theme: Theme) -> None:
        font_token = theme.font("default")
        font = QtGui.QFont(font_token.family, int(font_token.size))
        if font_token.weight.lower() == "bold":
            font.setBold(True)
        app.setFont(font)
