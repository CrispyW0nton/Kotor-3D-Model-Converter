"""Compatibility facade for backend renderer profiling helpers.

Canonical owner: :mod:`src.core.rendering.renderer_profiler`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.rendering.renderer_profiler")
sys.modules[__name__] = _module
