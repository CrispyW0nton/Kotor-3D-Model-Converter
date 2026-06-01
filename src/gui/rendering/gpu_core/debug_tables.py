"""Compatibility facade for :mod:`src.core.rendering.gpu_debug_tables`."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.rendering.gpu_debug_tables")
sys.modules[__name__] = _module
globals().update(_module.__dict__)
