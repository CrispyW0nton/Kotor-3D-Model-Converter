"""Compatibility alias for ModernGL scene helper exports."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.adapters.rendering.moderngl_scene_helpers")
sys.modules[__name__] = _module
