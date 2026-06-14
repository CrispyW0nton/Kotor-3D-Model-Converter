"""Compatibility facade for backend lightmap bake settings.

Canonical owner: :mod:`src.core.lighting.lightmap_bake_settings`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.lightmap_bake_settings")
sys.modules[__name__] = _module
