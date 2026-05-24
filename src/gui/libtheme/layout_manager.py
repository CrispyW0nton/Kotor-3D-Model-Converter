"""Layout manager for GhostRigger."""

from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from .layout_applier import LayoutApplier
from .layout_loader import LayoutLoader
from .layout_model import DockGroupLayout, LayoutDefinition, PanelLayout
from .theme_settings import ThemeLayoutSettings, user_config_root

log = logging.getLogger(__name__)


class LayoutManager(QtCore.QObject):
    layoutChanged = QtCore.Signal(object)

    def __init__(self, app_root: Path, settings_data: dict | None = None, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.app_root = Path(app_root)
        self.settings = ThemeLayoutSettings.from_settings(settings_data or {})
        self.loader = LayoutLoader()
        self.applier = LayoutApplier(self)
        self.layouts: dict[str, LayoutDefinition] = {}
        self.current_layout: LayoutDefinition | None = None
        self.diagnostics: list[str] = []
        self.applier.layoutChanged.connect(self.layoutChanged.emit)
        self.reload()

    @property
    def packaged_layout_dir(self) -> Path:
        return self.app_root / "config" / "themes" / "layouts"

    @property
    def user_layout_dir(self) -> Path:
        return user_config_root() / "layouts"

    def reload(self) -> None:
        diagnostics: list[str] = []
        layouts = self.loader.load_dir(self.packaged_layout_dir)
        user_layouts = self.loader.load_dir(self.user_layout_dir)
        for layout_id in user_layouts:
            if layout_id in layouts:
                diagnostics.append(f"User layout '{layout_id}' overrides packaged layout.")
        layouts.update(user_layouts)
        for layout in layouts.values():
            diagnostics.extend(f"{layout.name}: {warning}" for warning in layout.warnings)
        self.layouts = layouts
        self.diagnostics = diagnostics

    def available_layouts(self) -> list[LayoutDefinition]:
        return sorted(self.layouts.values(), key=lambda layout: layout.name.lower())

    def get_layout(self, layout_id: str | None = None) -> LayoutDefinition:
        requested = layout_id or self.settings.selected_layout
        layout = self.layouts.get(requested) or self.layouts.get("default") or next(iter(self.layouts.values()))
        return self._layout_with_user_override(layout)

    def apply_current_layout(self, window: QtWidgets.QMainWindow) -> LayoutDefinition:
        layout = self.get_layout()
        self.current_layout = layout
        self.applier.apply_layout(layout, window)
        return layout

    def select_layout(self, layout_id: str, *, apply: bool = True, window: QtWidgets.QMainWindow | None = None) -> LayoutDefinition:
        self.settings.selected_layout = layout_id if layout_id in self.layouts else "default"
        layout = self.get_layout(self.settings.selected_layout)
        if apply and window is not None:
            self.current_layout = layout
            self.applier.apply_layout(layout, window)
        return layout

    def set_button_override(self, mode: str = "", icon_size: int = 0) -> None:
        self.settings.button_mode_override = mode
        self.settings.icon_size_override = int(icon_size or 0)

    def reset_layout(self, window: QtWidgets.QMainWindow) -> LayoutDefinition:
        self.settings.splitter_sizes = {}
        return self.apply_current_layout(window)

    def to_settings(self) -> dict:
        return self.settings.to_dict()

    def _layout_with_user_override(self, layout: LayoutDefinition) -> LayoutDefinition:
        override = dict(self.settings.layout_overrides.get(layout.id) or {})
        if not override:
            return layout
        merged = deepcopy(layout)
        for panel_id, panel_data in dict(override.get("panels") or {}).items():
            if not isinstance(panel_data, dict):
                continue
            base = merged.panels.get(panel_id) or PanelLayout(id=panel_id)
            merged.panels[panel_id] = PanelLayout(
                id=panel_id,
                region=str(panel_data.get("region") or base.region),
                visible=bool(panel_data.get("visible", base.visible)),
                min_width=int(panel_data.get("min_width") or base.min_width),
                preferred_width=int(panel_data.get("preferred_width") or base.preferred_width),
                min_height=int(panel_data.get("min_height") or base.min_height),
                preferred_height=int(panel_data.get("preferred_height") or base.preferred_height),
                collapsed=bool(panel_data.get("collapsed", base.collapsed)),
            )
        dock_groups = []
        for group_data in list(override.get("dock_groups") or []):
            if not isinstance(group_data, dict):
                continue
            docks = [str(dock) for dock in group_data.get("docks") or [] if str(dock)]
            if not docks:
                continue
            dock_groups.append(
                DockGroupLayout(
                    id=str(group_data.get("id") or "userDockGroup"),
                    area=str(group_data.get("area") or "left"),
                    mode=str(group_data.get("mode") or "tabbed"),
                    visible=bool(group_data.get("visible", True)),
                    active=str(group_data.get("active") or docks[0]),
                    docks=docks,
                )
            )
        if dock_groups:
            merged.dock_groups = dock_groups
        return merged
