"""Data objects for XML-driven GhostRigger themes."""

from __future__ import annotations

from dataclasses import dataclass, field

from .style_tokens import FALLBACK_COLORS, FALLBACK_FONTS, FALLBACK_METRICS, FALLBACK_STYLES, color_alias_view


@dataclass(slots=True)
class ThemeFont:
    role: str
    family: str
    size: int
    weight: str = "normal"


@dataclass(slots=True)
class ThemeIcons:
    provider: str = "qtawesome"
    default_mode: str = "iconText"
    sizes: dict[str, int] = field(default_factory=lambda: {"toolbar": 18, "largeToolbar": 24})


@dataclass(slots=True)
class Theme:
    id: str
    name: str
    version: str
    author: str = "GhostRigger"
    description: str = ""
    mode: str = "dark"
    colors: dict[str, str] = field(default_factory=dict)
    fonts: dict[str, ThemeFont] = field(default_factory=dict)
    icons: ThemeIcons = field(default_factory=ThemeIcons)
    metrics: dict[str, int] = field(default_factory=dict)
    styles: dict[str, str] = field(default_factory=dict)
    high_contrast: bool = False
    source_path: str = ""
    warnings: list[str] = field(default_factory=list)

    def color(self, token: str, default: str | None = None) -> str:
        return self.colors.get(token, FALLBACK_COLORS.get(token, default or "#000000"))

    def metric(self, token: str, default: int | None = None) -> int:
        fallback = FALLBACK_METRICS.get(token, default if default is not None else 0)
        try:
            return int(self.metrics.get(token, fallback))
        except (TypeError, ValueError):
            return int(fallback)

    def style(self, token: str, default: str | None = None) -> str:
        return str(self.styles.get(token, FALLBACK_STYLES.get(token, default or "")))

    def font(self, role: str = "default") -> ThemeFont:
        fallback = FALLBACK_FONTS.get(role, FALLBACK_FONTS["default"])
        return self.fonts.get(
            role,
            ThemeFont(
                role=role,
                family=str(fallback["family"]),
                size=int(fallback["size"]),
                weight=str(fallback["weight"]),
            ),
        )

    def legacy_colors(self) -> dict[str, str]:
        return color_alias_view({**FALLBACK_COLORS, **self.colors})
