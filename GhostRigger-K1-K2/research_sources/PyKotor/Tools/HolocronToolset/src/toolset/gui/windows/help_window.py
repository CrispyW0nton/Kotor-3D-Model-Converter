"""Help window: display markdown/HTML help content and navigation tree."""

from __future__ import annotations

import sys

from pathlib import Path
from typing import TYPE_CHECKING

import markdown

from qtpy import QtCore
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QApplication, QMainWindow, QMessageBox

from pykotor.tools.encoding import decode_bytes_with_fallbacks
from toolset.gui.windows.help_content import HelpContent
from toolset.gui.windows.help_paths import get_help_base_paths, get_help_file_path
from utility.system.os_helper import is_frozen

if TYPE_CHECKING:
    import os

    from qtpy.QtGui import QShowEvent
    from qtpy.QtWidgets import QTreeWidgetItem, QWidget


def get_help_path() -> Path:
    """Get the path to the help directory.

    Returns:
        Path to help directory, checking both frozen and development locations.
    """
    if is_frozen():
        help_path = Path("./help").absolute()
    else:
        this_file_path = Path(__file__).absolute()
        help_path = this_file_path.parents[2].joinpath("help").absolute()
    return help_path
    if is_frozen():
        # When frozen, help should be bundled in the same directory as the executable
        exe_path = Path(sys.executable).parent
        help_path = exe_path / "help"
        if help_path.exists():
            return help_path

    # Development mode: check toolset/help first, then root help
    toolset_help = this_file_path.parents[2] / "help"

    # Fallback
    return toolset_help


class HelpWindow(QMainWindow):
    ENABLE_UPDATES = True

    def __init__(self, parent: QWidget | None, startingPage: str | None = None):
        super().__init__(parent)

        from toolset.gui.windows.help_updater import HelpUpdater
        from toolset.uic.qtpy.windows import help as toolset_help

        self.ui = toolset_help.Ui_MainWindow()
        self.ui.setupUi(self)

        self.help_content: HelpContent = HelpContent(self)
        self.help_updater: HelpUpdater = HelpUpdater(self)

        self._setup_signals()
        self.help_content.setup_contents()
        self.starting_page: str | None = startingPage

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

    def showEvent(self, event: QShowEvent):  # pyright: ignore[reportIncompatibleMethodOverride]
        super().showEvent(event)
        # Set search paths for all help file locations
        base_paths = get_help_base_paths()
        search_paths = [str(p) for p in base_paths]
        if not search_paths:
            search_paths = [str(get_help_path())]  # Fallback
        self.ui.textDisplay.setSearchPaths(search_paths)

        if self.ENABLE_UPDATES:
            self.help_updater.check_for_updates()

        if self.starting_page is None:
            return
        self.display_file(self.starting_page)

    def _setup_signals(self):
        self.ui.contentsTree.clicked.connect(self.on_contents_clicked)

    def _wrap_html_with_styles(self, html_body: str) -> str:
        """Wrap HTML body with theme-aware CSS styling."""
        # Get palette from QApplication
        app = QApplication.instance()
        if app is None or not isinstance(app, QApplication):
            palette = QPalette()
        else:
            palette = app.palette()

        # Get palette colors
        text_color_obj = palette.color(QPalette.ColorRole.Text)
        base_color_obj = palette.color(QPalette.ColorRole.Base)
        window_text_obj = palette.color(QPalette.ColorRole.WindowText)
        window_color_obj = palette.color(QPalette.ColorRole.Window)
        alternate_base_obj = palette.color(QPalette.ColorRole.AlternateBase)
        mid_color_obj = palette.color(QPalette.ColorRole.Mid)
        shadow_color_obj = palette.color(QPalette.ColorRole.Shadow)
        link_color_obj = palette.color(QPalette.ColorRole.Link)
        bright_text_obj = palette.color(QPalette.ColorRole.BrightText)

        # Ensure we have valid colors
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

        # Create variants for code backgrounds and table headers
        if alternate_base_obj != base_color_obj:
            code_bg = alternate_base
            table_header_bg = alternate_base
        else:
            code_bg_obj = QColor(base_color_obj)
            code_bg_obj = code_bg_obj.lighter(110)
            code_bg = color_to_hex(code_bg_obj)
            table_header_bg_obj = QColor(base_color_obj)
            table_header_bg_obj = table_header_bg_obj.darker(105)
            table_header_bg = color_to_hex(table_header_bg_obj)

        # Hover color
        hover_bg_obj = QColor(base_color_obj)
        hover_bg_obj = hover_bg_obj.darker(102)
        hover_bg = color_to_hex(hover_bg_obj)

        # Code text color
        if bright_text_obj != text_color_obj:
            code_text = bright_text
        else:
            code_text = link_color

        # Wrap with styled HTML
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
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 24px 0;
            display: block;
            overflow-x: auto;
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
            color: {shadow_color};
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

    def display_file(self, filepath: os.PathLike | str):
        # If filepath is a relative path string, try to resolve it
        filepath_str = str(filepath)
        if not Path(filepath_str).is_absolute():
            resolved_path = get_help_file_path(filepath_str)
            if resolved_path is not None:
                filepath = resolved_path
            else:
                # Try as-is if resolution failed
                filepath = Path(filepath)
        else:
            filepath = Path(filepath)

        try:
            text: str = decode_bytes_with_fallbacks(filepath.read_bytes())
            if filepath.suffix.lower() == ".md":
                from toolset.gui.common.palette_helpers import wrap_html_with_palette_styles

                html_body: str = markdown.markdown(text, extensions=["tables", "fenced_code", "codehilite"])
                html: str = wrap_html_with_palette_styles(html_body, self)
            else:
                html = text
            self.ui.textDisplay.setHtml(html)
        except OSError as e:
            from toolset.gui.common.localization import translate as tr, trf

            QMessageBox(
                QMessageBox.Icon.Critical,
                tr("Failed to open help file"),
                trf("Could not access '{filepath}'.\n{error}", filepath=str(filepath), error=str((e.__class__.__name__, str(e)))),
            ).exec()

    def on_contents_clicked(self):
        if not self.ui.contentsTree.selectedItems():
            return
        item: QTreeWidgetItem = self.ui.contentsTree.selectedItems()[0]  # type: ignore[arg-type]
        filename = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if filename:
            # Try to resolve the file path
            resolved_path = get_help_file_path(filename)
            if resolved_path is not None:
                # Update search paths to include the file's parent directory
                base_paths = get_help_base_paths()
                search_paths = [str(p) for p in base_paths]
                search_paths.append(str(resolved_path.parent))
                self.ui.textDisplay.setSearchPaths(search_paths)
                self.display_file(resolved_path)
            else:
                # Fallback to old behavior
                help_path = get_help_path()
                file_path = Path(help_path, filename)
                base_paths = get_help_base_paths()
                search_paths = [str(p) for p in base_paths]
                search_paths.extend([str(help_path), str(file_path.parent)])
                self.ui.textDisplay.setSearchPaths(search_paths)
                self.display_file(file_path)
