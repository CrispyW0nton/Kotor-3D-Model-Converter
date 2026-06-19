"""Compatibility facade for backend texture-array cache helpers.

Canonical owner: :mod:`src.core.graphics.tex_atlas`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.graphics.tex_atlas")
sys.modules[__name__] = _module
