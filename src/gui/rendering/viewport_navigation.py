"""Compatibility shim for viewport navigation profiles.

The implementation lives under :mod:`src.gui.viewports.viewport_navigation`.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = (
    "ViewportNavigationProfile",
    "DEFAULT_VIEWPORT_NAVIGATION_PROFILE",
    "VIEWPORT_NAVIGATION_HELP",
    "VIEWPORT_NAVIGATION_PROFILES",
    "normalize_viewport_navigation_profile",
    "viewport_profile_label",
    "has_modifier",
)

_TARGET = "src.gui.viewports.viewport_navigation"


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_TARGET)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
