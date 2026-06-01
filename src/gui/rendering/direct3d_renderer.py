"""Compatibility facade for the Direct3D viewport renderer adapter."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.adapters.rendering.direct3d_renderer")
sys.modules[__name__] = _module
