"""Compatibility facade for public WGPU renderer exports."""

from importlib import import_module
import sys

_TARGET = "src.adapters.rendering.wgpu_renderer_exports"
_module = import_module(_TARGET)
sys.modules[__name__] = _module
