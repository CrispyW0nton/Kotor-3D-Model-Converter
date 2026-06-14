"""Compatibility shim for the backend software frame-rendering core.

The implementation lives under :mod:`src.core.rendering.frame_core.renderer`.
Rendering backends should not grow viewport interaction code in this package.
"""

from importlib import import_module
import sys

_TARGET = "src.core.rendering.frame_core.renderer"
_module = import_module(_TARGET)
sys.modules[__name__] = _module
