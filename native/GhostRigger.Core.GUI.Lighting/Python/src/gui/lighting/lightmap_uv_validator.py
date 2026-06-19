"""Compatibility facade for backend lightmap UV validation helpers.

Canonical owner: :mod:`src.core.lighting.lightmap_uv_validator`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.lightmap_uv_validator")
sys.modules[__name__] = _module
