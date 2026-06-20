"""Data objects for XML-driven GhostRigger layouts."""

from __future__ import annotations

from dataclasses import dataclass, field

from .style_tokens import FALLBACK_METRICS


@dataclass(slots=True)
class ToolbarLayout:
    id: str
    visible: bool = True
    button_mode: str = "iconText"
    icon_size: int = 18
    height: int = 34


@dataclass(slots=True)
class PanelLayout:
    id: str
    region: str = "left"
    visible: bool = True
    min_width: int = 260
    preferred_width: int = 340
    min_height: int = 120
    preferred_height: int = 180
    collapsed: bool = False


@dataclass(slots=True)
class DockGroupLayout:
    id: str
    area: str = "left"
    mode: str = "tabbed"
    visible: bool = True
    active: str = ""
    docks: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ViewportLayout:
    min_width: int = 500
    preferred_width: int = 900
    toolbar_visible: bool = True
    toolbar_button_mode: str = "textOnly"
    toolbar_compact: bool = False


@dataclass(slots=True)
class LayoutDefinition:
    id: str
    name: str
    version: str
    main_width: int = 1650
    main_height: int = 920
    maximized: bool = False
    toolbars: dict[str, ToolbarLayout] = field(default_factory=dict)
    panels: dict[str, PanelLayout] = field(default_factory=dict)
    dock_groups: list[DockGroupLayout] = field(default_factory=list)
    viewport: ViewportLayout = field(default_factory=ViewportLayout)
    spacing: dict[str, int] = field(default_factory=dict)
    source_path: str = ""
    warnings: list[str] = field(default_factory=list)

    def toolbar(self, toolbar_id: str) -> ToolbarLayout:
        return self.toolbars.get(
            toolbar_id,
            ToolbarLayout(
                id=toolbar_id,
                button_mode="iconText",
                icon_size=FALLBACK_METRICS["toolbar.iconSize"],
                height=FALLBACK_METRICS["toolbar.height"],
            ),
        )

    def panel(self, panel_id: str) -> PanelLayout:
        return self.panels.get(
            panel_id,
            PanelLayout(
                id=panel_id,
                min_width=FALLBACK_METRICS["panel.minWidth"],
                preferred_width=FALLBACK_METRICS["panel.preferredWidth"],
                min_height=FALLBACK_METRICS["bottom.minHeight"],
                preferred_height=FALLBACK_METRICS["bottom.preferredHeight"],
            ),
        )

    def spacing_value(self, token: str, default: int = 0) -> int:
        try:
            return int(self.spacing.get(token, default))
        except (TypeError, ValueError):
            return int(default)
