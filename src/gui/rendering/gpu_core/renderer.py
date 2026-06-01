"""Compatibility facade for the ModernGL renderer implementation.

The concrete renderer now lives in ``src.adapters.rendering.moderngl_renderer_impl``.
Keep this legacy GUI path import-compatible while callers migrate to adapter
owners.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.adapters.rendering.moderngl_renderer_impl")
sys.modules[__name__] = _module
