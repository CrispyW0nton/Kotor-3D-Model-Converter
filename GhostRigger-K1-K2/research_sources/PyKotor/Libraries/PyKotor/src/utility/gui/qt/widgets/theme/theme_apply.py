"""Apply theme/style/palette to QApplication. No persistence or catalog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import QApplication, QStyleFactory

if TYPE_CHECKING:
    from qtpy.QtGui import QPalette
    from qtpy.QtWidgets import QStyle


def get_original_style() -> str:
    """Return the application's current style name (lowercase)."""
    app = QApplication.instance()
    if app is None or not isinstance(app, QApplication):
        raise RuntimeError("QApplication instance not found or not QApplication type.")
    style: QStyle | None = app.style()
    if style is None:
        raise RuntimeError("Failed to get application style")
    return str(style.objectName()).lower()


def apply_style(
    app: QApplication,
    sheet: str | None = None,
    style: str | None = None,
    palette: QPalette | None = None,
) -> None:
    """Apply style, palette, and stylesheet to the application. Caller owns persistence."""
    if style:
        style_obj = QStyleFactory.create(style)
        if style_obj:
            app.setStyle(style_obj)
    app_style: QStyle | None = app.style()
    if palette is None and app_style is not None:
        palette = app_style.standardPalette()
    if palette is not None:
        app.setPalette(palette)
    app.setStyleSheet(sheet or "")


def get_tooltip_stylesheet() -> str:
    """Palette-relative tooltip stylesheet for theme consistency."""
    return """
        QToolTip {
            background-color: palette(window);
            color: palette(window-text);
            border: 1px solid palette(mid);
            border-radius: 4px;
            padding: 8px 12px;
            font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
            font-size: 12px;
        }
    """


def apply_tooltip_style_to_app(app: QApplication | None = None) -> None:
    """Append tooltip stylesheet to the app if not already present."""
    parsed = QApplication.instance() if app is None else app
    if not isinstance(parsed, QApplication):
        return
    current = parsed.styleSheet() or ""
    if "QToolTip" not in current:
        parsed.setStyleSheet(current + "\n" + get_tooltip_stylesheet())
