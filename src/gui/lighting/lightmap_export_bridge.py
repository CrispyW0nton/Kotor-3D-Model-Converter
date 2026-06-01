"""Compatibility facade for backend lightmap export manifest helpers.

Canonical owner: :mod:`src.core.lighting.lightmap_export_bridge`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.lightmap_export_bridge")
sys.modules[__name__] = _module
