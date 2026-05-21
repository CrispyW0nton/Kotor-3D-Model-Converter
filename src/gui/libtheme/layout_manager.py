"""Layout manager for GhostRigger."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from .layout_applier import LayoutApplier
from .layout_loader import LayoutLoader
from .layout_model import LayoutDefinition
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
        return self.layouts.get(requested) or self.layouts.get("default") or next(iter(self.layouts.values()))

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
