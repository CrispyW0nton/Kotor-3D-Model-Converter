"""Compatibility facade for backend lightmap preview state."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.lightmap_controller")
sys.modules[__name__] = _module
