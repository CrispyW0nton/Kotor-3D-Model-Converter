"""Lazy compatibility facade for the Qt viewport widgets.

The implementation lives in :mod:`src.gui.viewports.viewport_core` so viewport
chrome/helpers and the main widget implementation can be maintained separately
without keeping the public import path as one very large file.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_MODULES: tuple[str, ...] = (
    "src.gui.viewports.viewport_core.widget",
    "src.gui.viewports.viewport_core.shared.icons",
    "src.gui.viewports.viewport_core.shared.joint_palette",
    "src.gui.viewports.viewport_core.shared.selection_modes",
    "src.gui.viewports.viewport_core.shared.weight_heatmap",
    "src.gui.viewports.viewport_core.widgets.mini_thumbnail",
    "src.gui.viewports.viewport_core.widgets.snap_view_bar",
)

_EXPORTS: dict[str, str] = {
    "QtViewportWidget": "src.gui.viewports.viewport_core.widget",
    "QtMainViewportWidget": "src.gui.viewports.viewport_core.widget",
    "QtMapStudioViewportWidget": "src.gui.viewports.viewport_core.widget",
    "QtCharacterBuilderViewportWidget": "src.gui.viewports.viewport_core.widget",
    "QtRetargetViewportWidget": "src.gui.viewports.viewport_core.widget",
    "QtUnrealAnimatorViewportWidget": "src.gui.viewports.viewport_core.widget",
    "_FloatingSnapViewWidget": "src.gui.viewports.viewport_core.widgets.snap_view_bar",
    "_MiniThumbnailWidget": "src.gui.viewports.viewport_core.widgets.mini_thumbnail",
    "_icon": "src.gui.viewports.viewport_core.shared.icons",
    "_gpu_icon": "src.gui.viewports.viewport_core.shared.icons",
    "_gpu_icon_name": "src.gui.viewports.viewport_core.shared.icons",
    "_detect_gpu_brand": "src.gui.viewports.viewport_core.shared.icons",
    "_navigation_profile_icon": "src.gui.viewports.viewport_core.shared.icons",
    "_weight_to_heatmap_color": "src.gui.viewports.viewport_core.shared.weight_heatmap",
    "_classify_joint_color": "src.gui.viewports.viewport_core.shared.joint_palette",
    "_is_key_joint_name": "src.gui.viewports.viewport_core.shared.joint_palette",
    "_ICON_DIR": "src.gui.viewports.viewport_core.shared.icons",
    "VIEWPORT_SELECTION_MODES": "src.gui.viewports.viewport_core.shared.selection_modes",
    "VIEWPORT_SELECTION_MODE_LABELS": "src.gui.viewports.viewport_core.shared.selection_modes",
    "VIEWPORT_SELECTION_MODE_ICONS": "src.gui.viewports.viewport_core.shared.selection_modes",
    "JOINT_DOT_COLOR_CENTER": "src.gui.viewports.viewport_core.shared.joint_palette",
    "JOINT_DOT_COLOR_CENTER_SPINE": "src.gui.viewports.viewport_core.shared.joint_palette",
    "JOINT_DOT_COLOR_LEFT": "src.gui.viewports.viewport_core.shared.joint_palette",
    "JOINT_DOT_COLOR_RIGHT": "src.gui.viewports.viewport_core.shared.joint_palette",
    "JOINT_DOT_COLOR_KEY": "src.gui.viewports.viewport_core.shared.joint_palette",
}

__all__ = tuple(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        for candidate in _EXPORT_MODULES:
            module = import_module(candidate)
            if hasattr(module, name):
                value = getattr(module, name)
                globals()[name] = value
                return value
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
