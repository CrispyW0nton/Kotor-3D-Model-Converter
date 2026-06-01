"""Compatibility facade for ModernGL diagnostics helpers."""

from importlib import import_module
import sys

_TARGET = "src.adapters.rendering.gpu_diagnostics_exports"
_module = import_module(_TARGET)
sys.modules[__name__] = _module
