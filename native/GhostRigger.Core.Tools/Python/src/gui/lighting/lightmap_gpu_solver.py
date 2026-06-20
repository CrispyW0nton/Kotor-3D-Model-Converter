"""Compatibility facade for the ModernGL lightmap GPU solver adapter."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.adapters.gpu.lightmap_gpu_solver")
sys.modules[__name__] = _module
