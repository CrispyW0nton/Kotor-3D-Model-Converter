"""Compatibility facade for backend material-map preview state."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.material_map_controller")
sys.modules[__name__] = _module
