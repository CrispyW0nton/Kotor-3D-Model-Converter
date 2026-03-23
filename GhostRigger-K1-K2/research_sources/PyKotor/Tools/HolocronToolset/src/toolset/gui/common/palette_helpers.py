"""Helper functions for working with QApplication palette colors.

This module provides utilities for getting theme-aware colors from the application palette,
ensuring that UI elements adapt properly to different themes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QApplication

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget


def get_semantic_colors() -> dict[str, str]:
    """Get semantic colors from the application palette.

    Returns a dictionary with theme-aware colors for common semantic purposes:
    - 'success': Color for success/positive indicators (green-like)
    - 'warning': Color for warning indicators (orange/yellow-like)
    - 'error': Color for error indicators (red-like)
    - 'muted': Color for muted/secondary text
    - 'info': Color for informational text (blue-like)
    - 'link': Color for links

    Returns:
        Dictionary with color names as hex strings (e.g., '#RRGGBB')
    """
    app = QApplication.instance()
    if app is None or not isinstance(app, QApplication):
        palette = QPalette()
    else:
        palette = app.palette()

    # Get base colors from palette
    link_color = palette.color(QPalette.ColorRole.Link)
    mid_color = palette.color(QPalette.ColorRole.Mid)
    shadow_color = palette.color(QPalette.ColorRole.Shadow)
    window_text = palette.color(QPalette.ColorRole.WindowText)

    # Success: Green-like color derived from palette
    # Start with a base color and adjust to green while maintaining theme awareness
    base_for_success = QColor(link_color) if link_color.isValid() else window_text
    success_color = QColor(base_for_success)
    # Shift hue toward green (hue ~120) while maintaining lightness appropriate for theme
    if success_color.lightness() < 128:  # Dark theme
        # Use a green that's visible on dark backgrounds, derived from palette lightness
        target_lightness = min(180, max(120, base_for_success.lightness() + 60))
        success_color = QColor(76, 175, 80)  # Material green as base
        # Adjust lightness to match theme brightness
        if target_lightness > success_color.lightness():
            success_color = success_color.lighter(int((target_lightness - success_color.lightness()) * 0.5))
    else:  # Light theme
        # Use a darker green for light backgrounds
        success_color = QColor(46, 125, 50)  # Darker green for light theme

    # Warning: Orange/yellow-like color derived from mid color
    warning_color = QColor(mid_color)
    if not warning_color.isValid():
        warning_color = QColor(window_text)
    if warning_color.lightness() < 128:  # Dark theme
        # Bright orange/yellow for dark themes
        warning_color = QColor(255, 152, 0)  # Material orange
    else:  # Light theme
        # Darker orange for light themes
        warning_color = QColor(245, 124, 0)  # Darker orange for light theme

    # Error: Red-like color derived from shadow color
    error_color = QColor(shadow_color)
    if not error_color.isValid():
        error_color = QColor(window_text)
    if error_color.lightness() < 128:  # Dark theme
        # Bright red for dark themes
        error_color = QColor(244, 67, 54)  # Material red
    else:  # Light theme
        # Darker red for light themes
        error_color = QColor(198, 40, 40)  # Darker red for light theme

    # Muted: Use mid color for secondary/muted text
    muted_color = mid_color
    if not muted_color.isValid():
        muted_color = window_text
        # Make it more muted
        if muted_color.lightness() < 128:  # Dark theme
            muted_color = muted_color.lighter(150)
        else:  # Light theme
            muted_color = muted_color.darker(150)

    # Info: Use link color (usually blue)
    info_color = link_color

    return {
        "success": success_color.name(),
        "warning": warning_color.name(),
        "error": error_color.name(),
        "muted": muted_color.name(),
        "info": info_color.name(),
        "link": link_color.name(),
    }


def get_palette_color(role: QPalette.ColorRole) -> QColor:
    """Get a color from the application palette.

    Args:
        role: The palette color role to retrieve

    Returns:
        QColor from the palette, or an invalid QColor if palette is not available
    """
    app = QApplication.instance()
    if app is None or not isinstance(app, QApplication):
        palette = QPalette()
    else:
        palette = app.palette()

    return palette.color(role)


def get_status_colors() -> dict[str, str]:
    """Get colors for status indicators (info, ok, warn, error).

    Similar to get_semantic_colors but with additional 'ok' color.
    Useful for status messages and indicators.

    Returns:
        Dictionary with 'info', 'ok', 'warn', 'error' color names as hex strings
    """
    semantic = get_semantic_colors()
    return {
        "info": semantic["info"],
        "ok": semantic["success"],
        "warn": semantic["warning"],
        "error": semantic["error"],
    }


def wrap_html_with_palette_styles(html_body: str, widget: QWidget | None = None) -> str:
    """Wrap HTML body with CSS styling using QApplication palette colors.

    This function creates theme-aware HTML by using colors from the application
    palette, ensuring that HTML content displayed in QTextEdit/QTextBrowser
    widgets matches the current theme.

    Args:
        html_body: The HTML body content to wrap
        widget: Optional widget to get palette from (defaults to QApplication)

    Returns:
        Complete HTML document with embedded CSS styles using palette colors
    """
    app = QApplication.instance()
    if widget is not None:
        palette = widget.palette()
    elif app is not None and isinstance(app, QApplication):
        palette = app.palette()
    else:
        # Fallback: use default palette
        palette = QPalette()

    # Get palette colors as QColor objects
    text_color_obj = palette.color(QPalette.ColorRole.Text)
    base_color_obj = palette.color(QPalette.ColorRole.Base)
    window_text_obj = palette.color(QPalette.ColorRole.WindowText)
    window_color_obj = palette.color(QPalette.ColorRole.Window)
    alternate_base_obj = palette.color(QPalette.ColorRole.AlternateBase)
    mid_color_obj = palette.color(QPalette.ColorRole.Mid)
    shadow_color_obj = palette.color(QPalette.ColorRole.Shadow)
    link_color_obj = palette.color(QPalette.ColorRole.Link)
    bright_text_obj = palette.color(QPalette.ColorRole.BrightText)

    # Ensure we have valid colors - use Window/WindowText as fallback if Base/Text are invalid
    if not text_color_obj.isValid() or text_color_obj == base_color_obj:
        text_color_obj = window_text_obj
    if not base_color_obj.isValid():
        base_color_obj = window_color_obj

    # Convert to hex strings
    def color_to_hex(color: QColor) -> str:
        return f"#{color.red():02x}{color.green():02x}{color.blue():02x}"

    text_color = color_to_hex(text_color_obj)
    base_color = color_to_hex(base_color_obj)
    alternate_base = color_to_hex(alternate_base_obj)
    border_color = color_to_hex(mid_color_obj)
    shadow_color = color_to_hex(shadow_color_obj)
    link_color = color_to_hex(link_color_obj)
    bright_text = color_to_hex(bright_text_obj)

    # Create lighter/darker variants for borders and backgrounds
    # Use AlternateBase for code backgrounds, or create a lighter variant of Base
    if alternate_base_obj != base_color_obj:
        code_bg = alternate_base
    else:
        code_bg_obj = QColor(base_color_obj)
        code_bg_obj = code_bg_obj.lighter(110)
        code_bg = color_to_hex(code_bg_obj)

    # Use a slightly different shade for table headers
    if alternate_base_obj != base_color_obj:
        table_header_bg = alternate_base
    else:
        table_header_bg_obj = QColor(base_color_obj)
        table_header_bg_obj = table_header_bg_obj.darker(105)
        table_header_bg = color_to_hex(table_header_bg_obj)

    # Hover color - slightly darker than base
    hover_bg_obj = QColor(base_color_obj)
    hover_bg_obj = hover_bg_obj.darker(102)
    hover_bg = color_to_hex(hover_bg_obj)

    # For code text, use BrightText if it's different from text, otherwise use link color
    if bright_text_obj != text_color_obj:
        code_text = bright_text
    else:
        code_text = link_color

    # Muted color for blockquotes
    muted_fg = QColor(text_color_obj)
    muted_fg.setAlpha(190)
    muted_css = f"rgba({muted_fg.red()}, {muted_fg.green()}, {muted_fg.blue()}, {muted_fg.alpha() / 255.0:.3f})"

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
            line-height: 1.6;
            color: {text_color};
            max-width: 100%;
            margin: 0;
            padding: 24px;
            background-color: {base_color};
        }}

        h1 {{
            font-size: 2em;
            font-weight: 600;
            margin-top: 0;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 2px solid {border_color};
            color: {text_color};
        }}

        h2 {{
            font-size: 1.5em;
            font-weight: 600;
            margin-top: 32px;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid {border_color};
            color: {text_color};
        }}

        h3 {{
            font-size: 1.25em;
            font-weight: 600;
            margin-top: 24px;
            margin-bottom: 12px;
            color: {text_color};
        }}

        h4, h5, h6 {{
            font-size: 1.1em;
            font-weight: 600;
            margin-top: 20px;
            margin-bottom: 10px;
            color: {text_color};
        }}

        p {{
            margin-top: 0;
            margin-bottom: 16px;
        }}

        ul, ol {{
            margin-top: 0;
            margin-bottom: 16px;
            padding-left: 32px;
        }}

        li {{
            margin-bottom: 8px;
        }}

        li > p {{
            margin-bottom: 8px;
        }}

        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 24px 0;
            display: block;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}

        table thead {{
            background-color: {table_header_bg};
        }}

        table th {{
            font-weight: 600;
            text-align: left;
            padding: 12px 16px;
            border: 1px solid {border_color};
            background-color: {table_header_bg};
            color: {text_color};
        }}

        table td {{
            padding: 12px 16px;
            border: 1px solid {border_color};
            vertical-align: top;
        }}

        table tbody tr:nth-child(even) {{
            background-color: {alternate_base};
        }}

        table tbody tr:hover {{
            background-color: {hover_bg};
        }}

        code {{
            font-family: 'SFMono-Regular', 'Consolas', 'Liberation Mono', 'Menlo', 'Courier', monospace;
            font-size: 0.9em;
            padding: 2px 6px;
            background-color: {code_bg};
            border-radius: 3px;
            color: {code_text};
        }}

        pre {{
            font-family: 'SFMono-Regular', 'Consolas', 'Liberation Mono', 'Menlo', 'Courier', monospace;
            font-size: 0.9em;
            padding: 16px;
            background-color: {code_bg};
            border-radius: 6px;
            overflow-x: auto;
            margin: 16px 0;
            border: 1px solid {border_color};
        }}

        pre code {{
            padding: 0;
            background-color: transparent;
            color: {text_color};
            border-radius: 0;
        }}

        a {{
            color: {link_color};
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        hr {{
            height: 0;
            margin: 24px 0;
            background: transparent;
            border: 0;
            border-top: 1px solid {border_color};
        }}

        blockquote {{
            margin: 16px 0;
            padding: 0 16px;
            color: {muted_css};
            border-left: 4px solid {border_color};
        }}

        strong {{
            font-weight: 600;
            color: {text_color};
        }}
    </style>
</head>
<body>
{html_body}
</body>
</html>"""
