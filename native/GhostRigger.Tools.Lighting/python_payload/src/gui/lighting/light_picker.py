"""Compatibility facade for backend light-helper picking."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.light_picker")
sys.modules[__name__] = _module
