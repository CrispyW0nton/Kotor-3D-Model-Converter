"""Compatibility facade for backend lightmap rasterizer helpers.

Canonical owner: :mod:`src.core.lighting.lightmap_rasterizer`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.lightmap_rasterizer")
sys.modules[__name__] = _module
