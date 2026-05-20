"""GUI package compatibility helpers."""

from __future__ import annotations

from importlib import import_module

_COMPAT_ALIASES = {
    "gpu_renderer": "src.gui.qt_lib.rendering.gpu_renderer",
}


def __getattr__(name: str):
    target = _COMPAT_ALIASES.get(name)
    if target is None:
        raise AttributeError(name)
    module = import_module(target)
    globals()[name] = module
    return module


__all__ = sorted(_COMPAT_ALIASES)
