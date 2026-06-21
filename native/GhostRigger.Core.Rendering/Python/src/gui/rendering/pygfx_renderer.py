"""Compatibility facade for public pygfx renderer exports."""

from importlib import import_module
import sys

_TARGET = "src.adapters.rendering.pygfx_renderer_exports"
_module = import_module(_TARGET)
sys.modules[__name__] = _module
