"""Compatibility facade for the GPU-default lightmap baker adapter."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.adapters.gpu.lightmap_baker")
sys.modules[__name__] = _module
