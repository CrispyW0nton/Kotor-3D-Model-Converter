"""Compatibility facade for backend lightmap padding helpers.

Canonical owner: :mod:`src.core.lighting.lightmap_padding`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.lightmap_padding")
sys.modules[__name__] = _module
