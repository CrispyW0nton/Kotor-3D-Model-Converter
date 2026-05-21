"""Persistence model for theme/layout settings."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ThemeLayoutSettings:
    theme_mode: str = "manual"
    selected_theme: str = "matrix"
    os_light_theme: str = "light"
    os_dark_theme: str = "dark"
    selected_layout: str = "default"
    button_mode_override: str = ""
    icon_size_override: int = 0
    density_override: str = ""
    hot_reload_enabled: bool = False
    last_known_os_theme: str = "dark"
    last_theme_editor_section: str = "Theme"
    user_theme_dir: str = ""
    user_layout_dir: str = ""
    panel_sizes: dict[str, int] = field(default_factory=dict)
    splitter_sizes: dict[str, list[int]] = field(default_factory=dict)

    @classmethod
    def from_settings(cls, settings: dict) -> "ThemeLayoutSettings":
        raw = dict(settings.get("theme_layout") or settings)
        return cls(
            theme_mode=str(raw.get("theme_mode") or "manual"),
            selected_theme=str(raw.get("selected_theme") or "matrix"),
            os_light_theme=str(raw.get("os_light_theme") or "light"),
            os_dark_theme=str(raw.get("os_dark_theme") or "dark"),
            selected_layout=str(raw.get("selected_layout") or "default"),
            button_mode_override=str(raw.get("button_mode_override") or ""),
            icon_size_override=int(raw.get("icon_size_override") or 0),
            density_override=str(raw.get("density_override") or ""),
            hot_reload_enabled=bool(raw.get("hot_reload_enabled", False)),
            last_known_os_theme=str(raw.get("last_known_os_theme") or "dark"),
            last_theme_editor_section=str(raw.get("last_theme_editor_section") or "Theme"),
            user_theme_dir=str(raw.get("user_theme_dir") or ""),
            user_layout_dir=str(raw.get("user_layout_dir") or ""),
            panel_sizes=dict(raw.get("panel_sizes") or {}),
            splitter_sizes={key: list(value) for key, value in dict(raw.get("splitter_sizes") or {}).items()},
        )

    def to_dict(self) -> dict:
        return asdict(self)


def user_config_root() -> Path:
    try:
        from platformdirs import user_config_dir

        return Path(user_config_dir("GhostRigger", "GhostRigger"))
    except Exception:
        return Path.home() / ".ghostrigger"
