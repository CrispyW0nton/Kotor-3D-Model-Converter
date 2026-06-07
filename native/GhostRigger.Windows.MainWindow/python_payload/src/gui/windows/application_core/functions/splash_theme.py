"""Splash theme and palette helper functions for application-core windows."""

from __future__ import annotations

try:
    from PySide6 import QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.libtheme.style_tokens import LEGACY_MATRIX_COLORS

C = dict(LEGACY_MATRIX_COLORS)
_SPLASH_SURFACE_STYLES = {"matte", "bevelled", "glossy", "flat"}

def _lighten_hex(value: str, factor: float = 1.18) -> str:
    color = QtGui.QColor(value)
    if not color.isValid():
        return value
    return color.lighter(int(factor * 100)).name().upper()
def _darken_hex(value: str, factor: float = 1.18) -> str:
    color = QtGui.QColor(value)
    if not color.isValid():
        return value
    return color.darker(int(factor * 100)).name().upper()
def _surface_fill(value: str, style: str) -> str:
    style = style if style in _SPLASH_SURFACE_STYLES else "matte"
    if style == "flat":
        return value
    if style == "bevelled":
        return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {_lighten_hex(value, 1.18)}, stop:1 {_darken_hex(value, 1.05)})"
    if style == "glossy":
        return (
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {_lighten_hex(value, 1.35)}, stop:0.48 {_lighten_hex(value, 1.10)}, "
            f"stop:0.50 {value}, stop:1 {_darken_hex(value, 1.18)})"
        )
    return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {value}, stop:1 {_darken_hex(value, 1.06)})"
def _palette_hex(palette: QtGui.QPalette, role: QtGui.QPalette.ColorRole, group: QtGui.QPalette.ColorGroup | None = None) -> str:
    color = palette.color(group, role) if group is not None else palette.color(role)
    return color.name().upper()
def _native_splash_palette_colors() -> dict[str, str]:
    app = QtWidgets.QApplication.instance()
    palette = app.palette() if app is not None else QtGui.QPalette()
    role = QtGui.QPalette.ColorRole
    return {
        "splash.background": _palette_hex(palette, role.Window),
        "splash.panel": _palette_hex(palette, role.Button),
        "splash.brandBackground": _palette_hex(palette, role.Base),
        "splash.progressBackground": _palette_hex(palette, role.Base),
        "splash.border": _palette_hex(palette, role.Mid),
        "splash.text": _palette_hex(palette, role.WindowText),
        "splash.secondaryText": _palette_hex(palette, role.Text),
        "splash.accent": _palette_hex(palette, role.Highlight),
        "splash.progressTrack": _palette_hex(palette, role.Base),
        "splash.progressFill": _palette_hex(palette, role.Highlight),
        "window.background": _palette_hex(palette, role.Window),
        "panel.background": _palette_hex(palette, role.Button),
        "panel.backgroundAlt": _palette_hex(palette, role.Base),
        "panel.altBackground": _palette_hex(palette, role.Base),
        "toolbar.border": _palette_hex(palette, role.Mid),
        "viewportToolbar.background": _palette_hex(palette, role.Window),
        "viewportToolbar.border": _palette_hex(palette, role.Mid),
        "text.primary": _palette_hex(palette, role.WindowText),
        "text.secondary": _palette_hex(palette, role.Text),
        "accent.primary": _palette_hex(palette, role.Highlight),
        "input.background": _palette_hex(palette, role.Base),
        "success": _palette_hex(palette, role.Highlight),
    }
