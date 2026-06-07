"""Compatibility facade for backend lightmap denoiser helpers.

Canonical owner: :mod:`src.core.lighting.lightmap_denoiser`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.lightmap_denoiser")
sys.modules[__name__] = _module
