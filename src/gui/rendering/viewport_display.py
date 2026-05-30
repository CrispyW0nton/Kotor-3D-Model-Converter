"""Compatibility shim for viewport display mode state.

The implementation lives under :mod:`src.gui.viewports.viewport_display`.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = (
    "ViewportDisplayMode",
    "ViewportDisplayOptions",
    "normalize_display_mode",
    "display_mode_values",
)

_TARGET = "src.gui.viewports.viewport_display"


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_TARGET)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
