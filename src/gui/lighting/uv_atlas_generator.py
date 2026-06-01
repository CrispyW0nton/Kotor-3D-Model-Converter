"""Compatibility facade for backend lightmap UV atlas helpers.

Canonical owner: :mod:`src.core.lighting.uv_atlas_generator`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.uv_atlas_generator")
sys.modules[__name__] = _module
