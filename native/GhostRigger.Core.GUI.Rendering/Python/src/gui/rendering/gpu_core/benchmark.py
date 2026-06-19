"""Compatibility facade for the ModernGL renderer benchmark adapter."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.adapters.rendering.moderngl_benchmark")
sys.modules[__name__] = _module
