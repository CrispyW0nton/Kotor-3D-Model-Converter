"""Compatibility facade for the ModernGL renderer CLI adapter."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.adapters.rendering.moderngl_cli")
sys.modules[__name__] = _module
