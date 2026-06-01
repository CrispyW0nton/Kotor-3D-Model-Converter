"""Compatibility facade for backend lightmap sampler helpers.

Canonical owner: :mod:`src.core.lighting.lightmap_sampler`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.lightmap_sampler")
sys.modules[__name__] = _module
