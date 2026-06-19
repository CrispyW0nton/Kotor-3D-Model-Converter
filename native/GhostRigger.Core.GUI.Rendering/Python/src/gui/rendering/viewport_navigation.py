"""Compatibility shim for backend viewport navigation profiles.

The implementation lives under :mod:`src.core.rendering.viewport_navigation`.
"""

from importlib import import_module
import sys

_TARGET = "src.core.rendering.viewport_navigation"
_module = import_module(_TARGET)
sys.modules[__name__] = _module
