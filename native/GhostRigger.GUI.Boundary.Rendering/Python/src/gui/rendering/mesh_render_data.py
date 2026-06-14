"""Compatibility facade for the ModernGL-backed mesh render-data adapter."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.adapters.rendering.mesh_render_data")
sys.modules[__name__] = _module
