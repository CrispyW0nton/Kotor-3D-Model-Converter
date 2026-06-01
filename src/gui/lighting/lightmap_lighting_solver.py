"""Compatibility facade for backend lightmap lighting solver.

Canonical owner: :mod:`src.core.lighting.lightmap_lighting_solver`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.lightmap_lighting_solver")
sys.modules[__name__] = _module
