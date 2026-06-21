"""Compatibility facade for backend lightmap comparison helpers.

Canonical owner: :mod:`src.core.lighting.lightmap_compare`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.lightmap_compare")
sys.modules[__name__] = _module
