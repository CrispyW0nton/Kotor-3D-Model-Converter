"""Compatibility facade for backend shader-complexity scoring helpers.

Canonical owner: :mod:`src.core.lighting.shader_complexity`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.shader_complexity")
sys.modules[__name__] = _module
