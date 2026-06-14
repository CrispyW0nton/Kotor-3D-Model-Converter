"""Compatibility facade for backend lightmap manifest helpers.

Canonical owner: :mod:`src.core.lighting.lightmap_manifest`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.lightmap_manifest")
sys.modules[__name__] = _module
