"""Compatibility shim for the backend software frame-rendering core.

The implementation lives under :mod:`src.core.rendering.frame_core.renderer`.
Rendering backends should not grow viewport interaction code in this package.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from src.core.rendering.frame_core.renderer import __all__ as __all__

_TARGET = "src.core.rendering.frame_core.renderer"


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_TARGET)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
