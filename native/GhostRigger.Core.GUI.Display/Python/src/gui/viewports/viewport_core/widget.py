"""Lazy compatibility facade for Qt viewport widget classes."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, str] = {
    "QtViewportWidget": "src.gui.viewports.viewport_core.widgets.viewport_widget",
    "QtMainViewportWidget": "src.gui.viewports.viewport_core.widgets.variants",
    "QtMapStudioViewportWidget": "src.gui.viewports.viewport_core.widgets.variants",
    "QtCharacterBuilderViewportWidget": "src.gui.viewports.viewport_core.widgets.variants",
    "QtRetargetViewportWidget": "src.gui.viewports.viewport_core.widgets.variants",
    "QtUnrealAnimatorViewportWidget": "src.gui.viewports.viewport_core.widgets.variants",
}

__all__ = tuple(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
