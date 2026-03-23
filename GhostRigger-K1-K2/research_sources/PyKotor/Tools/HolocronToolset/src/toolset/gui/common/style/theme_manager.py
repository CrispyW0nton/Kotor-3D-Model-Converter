"""Toolset compatibility wrapper: delegates to utility ThemeManager. Settings owned by main window."""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Slot
from qtpy.QtWidgets import QAction

from toolset.gui.widgets.settings.widgets.misc import GlobalSettings
from utility.gui.qt.widgets.theme import ThemeManager as UtilityThemeManager
from utility.gui.qt.widgets.theme import ThemeSources

# Optional extra_themes dirs (Toolset resources); :/themes is default in ThemeSources
def _toolset_extra_theme_dirs() -> tuple[str, ...]:
    current = Path(__file__).resolve()
    # Toolset layout: .../toolset/gui/common/style/theme_manager.py -> .../resources/extra_themes
    for parent in [current.parent.parent.parent.parent, current.parent.parent.parent.parent.parent]:
        extra = parent / "resources" / "extra_themes"
        if extra.exists() and extra.is_dir():
            return (str(extra),)
    return ()


class ThemeManager:
    """
    Toolset theme manager: delegates to utility.gui ThemeManager.
    Persistence (selectedTheme/selectedStyle) is handled by the main window; this wrapper
    only reads them for apply context. Prefer importing from utility.gui.qt.widgets.theme
    for new code.
    """

    def __init__(self, original_style: str | None = None):
        extra = _toolset_extra_theme_dirs()
        sources = ThemeSources().with_extra_dirs(*extra) if extra else None
        self._utility = UtilityThemeManager(
            original_style=original_style,
            theme_sources=sources,
            on_theme_error=self._on_theme_error,
        )
        self.original_style: str = self._utility.original_style

    def _on_theme_error(self, title: str, message: str) -> None:
        from qtpy.QtWidgets import QMessageBox
        from toolset.gui.common.localization import translate as tr
        QMessageBox.critical(None, tr(title), tr(message))
        GlobalSettings().reset_setting("selectedTheme")
        theme = GlobalSettings().selectedTheme or "sourcegraph-dark"
        style = GlobalSettings().selectedStyle or "Fusion"
        self._utility.apply_theme_and_style(theme, style, fallback_theme="sourcegraph-dark", fallback_style="Fusion")

    @classmethod
    def get_available_themes(cls) -> tuple[str, ...]:
        """List all available themes (delegates to utility)."""
        m = cls()
        return m._utility.get_available_themes()

    @staticmethod
    def get_default_styles() -> tuple[str, ...]:
        """Get available Qt styles (delegates to utility)."""
        return UtilityThemeManager.get_default_styles()

    @classmethod
    def get_original_style(cls) -> str:
        """Get the application's original style name (delegates to utility)."""
        return UtilityThemeManager.get_original_style()

    @Slot()
    def change_theme(self, theme: QAction | str | None = None) -> None:
        """Apply theme; current style read from settings. Main window persists selectedTheme."""
        theme_name = theme.text() if isinstance(theme, QAction) else theme
        if not isinstance(theme_name, str):
            return
        style_name = GlobalSettings().selectedStyle or "Fusion"
        self._utility.apply_theme_and_style(
            theme_name,
            style_name,
            fallback_theme="sourcegraph-dark",
            fallback_style="Fusion",
        )

    @Slot()
    def change_style(self, style: QAction | str | None = None) -> None:
        """Apply style; current theme read from settings. Main window persists selectedStyle."""
        style_name = style.text() if isinstance(style, QAction) else style
        if not isinstance(style_name, str):
            return
        theme_name = GlobalSettings().selectedTheme or "sourcegraph-dark"
        self._utility.apply_theme_and_style(
            theme_name,
            style_name,
            fallback_theme="sourcegraph-dark",
            fallback_style="Fusion",
        )

    def _apply_theme_and_style(
        self,
        theme_name: str | None = None,
        style_name: str | None = None,
    ) -> None:
        """Apply theme and style (used at startup and by main window). Reads settings if None."""
        theme_name = theme_name or GlobalSettings().selectedTheme or "sourcegraph-dark"
        style_name = style_name if style_name is not None else (GlobalSettings().selectedStyle or "Fusion")
        self._utility.apply_theme_and_style(
            theme_name,
            style_name,
            fallback_theme="sourcegraph-dark",
            fallback_style="Fusion",
        )
