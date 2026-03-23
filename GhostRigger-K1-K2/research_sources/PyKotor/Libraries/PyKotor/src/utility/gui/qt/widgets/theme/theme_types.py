"""Type definitions and configuration for the Qt theme system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ThemeSources:
    """Configurable sources for theme discovery (QRC prefixes and filesystem dirs)."""

    qrc_prefixes: tuple[str, ...] = (":/themes",)
    """Qt resource prefixes to scan for QSS themes (e.g. :/themes)."""

    extra_theme_dirs: tuple[str, ...] = ()
    """Filesystem paths to scan for VS Code JSON theme files."""

    def with_qrc_prefixes(self, *prefixes: str) -> ThemeSources:
        """Return a new instance with the given QRC prefixes."""
        return ThemeSources(qrc_prefixes=prefixes, extra_theme_dirs=self.extra_theme_dirs)

    def with_extra_dirs(self, *dirs: str) -> ThemeSources:
        """Return a new instance with the given extra theme directories."""
        return ThemeSources(qrc_prefixes=self.qrc_prefixes, extra_theme_dirs=dirs)


# Theme config dict: style (str), palette (callable -> QPalette | None), sheet (str | callable -> str)
ThemeConfig = dict[str, Any]
