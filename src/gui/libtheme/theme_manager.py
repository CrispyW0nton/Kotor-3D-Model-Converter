"""Theme manager for GhostRigger."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from .icon_manager import ThemeIconManager
from .os_theme_detector import OSThemeDetector
from .theme_applier import ThemeApplier
from .theme_loader import ThemeLoader
from .theme_model import Theme
from .theme_settings import ThemeLayoutSettings, user_config_root

log = logging.getLogger(__name__)


class ThemeManager(QtCore.QObject):
    themeChanged = QtCore.Signal(object)

    def __init__(self, app_root: Path, settings_data: dict | None = None, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.app_root = Path(app_root)
        self.settings = ThemeLayoutSettings.from_settings(settings_data or {})
        self.loader = ThemeLoader()
        self.applier = ThemeApplier(self)
        self.icons = ThemeIconManager()
        self.os_detector = OSThemeDetector()
        self.themes: dict[str, Theme] = {}
        self.current_theme: Theme | None = None
        self.diagnostics: list[str] = []
        self.applier.themeChanged.connect(self.themeChanged.emit)
        self.reload()

    @property
    def packaged_theme_dir(self) -> Path:
        return self.app_root / "config" / "themes" / "themes"

    @property
    def user_theme_dir(self) -> Path:
        return user_config_root() / "themes"

    def reload(self) -> None:
        diagnostics: list[str] = []
        themes = self.loader.load_dir(self.packaged_theme_dir)
        user_themes = self.loader.load_dir(self.user_theme_dir)
        for theme_id in user_themes:
            if theme_id in themes:
                diagnostics.append(f"User theme '{theme_id}' overrides packaged theme.")
        themes.update(user_themes)
        for theme in themes.values():
            diagnostics.extend(f"{theme.name}: {warning}" for warning in theme.warnings if "missing recommended" not in warning)
        self.themes = themes
        self.diagnostics = diagnostics
        if not self.themes:
            fallback = self.loader.load_file(self.packaged_theme_dir / "matrix.xml")
            if fallback is not None:
                self.themes[fallback.id] = fallback

    def available_themes(self) -> list[Theme]:
        return sorted(self.themes.values(), key=lambda theme: theme.name.lower())

    def resolve_theme_id(self) -> str:
        if self.settings.theme_mode == "follow_os":
            os_mode = self.os_detector.current_mode()
            self.settings.last_known_os_theme = os_mode
            return self.settings.os_light_theme if os_mode == "light" else self.settings.os_dark_theme
        return self.settings.selected_theme

    def get_theme(self, theme_id: str | None = None) -> Theme:
        requested = theme_id or self.resolve_theme_id()
        return self.themes.get(requested) or self.themes.get("matrix") or next(iter(self.themes.values()))

    def apply_current_theme(self, target: QtWidgets.QWidget | None = None) -> Theme:
        theme = self.get_theme()
        self.current_theme = theme
        self.applier.apply_theme(theme, target)
        return theme

    def select_theme(self, theme_id: str, *, apply: bool = True, target: QtWidgets.QWidget | None = None) -> Theme:
        self.settings.theme_mode = "manual"
        self.settings.selected_theme = theme_id if theme_id in self.themes else "matrix"
        theme = self.get_theme(self.settings.selected_theme)
        if apply:
            self.current_theme = theme
            self.applier.apply_theme(theme, target)
        return theme

    def set_follow_os(self, enabled: bool, *, apply: bool = True, target: QtWidgets.QWidget | None = None) -> Theme:
        self.settings.theme_mode = "follow_os" if enabled else "manual"
        theme = self.get_theme()
        if apply:
            self.current_theme = theme
            self.applier.apply_theme(theme, target)
        return theme

    def to_settings(self) -> dict:
        return self.settings.to_dict()

    def register_theme_aware_widget(self, widget: QtWidgets.QWidget) -> None:
        self.applier.register_theme_aware_widget(widget)

    def icon(self, name: str, size: int = 16):
        return self.icons.icon(name, self.current_theme or self.get_theme(), size)
