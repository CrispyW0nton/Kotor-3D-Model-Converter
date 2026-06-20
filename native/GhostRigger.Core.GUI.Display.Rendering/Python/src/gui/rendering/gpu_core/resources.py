"""Compatibility facade for ModernGL resource helpers.

The implementation lives in ``src.adapters.rendering.moderngl_resources``.
Keep this legacy GUI path logic-free while callers migrate to the adapter owner.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.adapters.rendering.moderngl_resources")
sys.modules[__name__] = _module
