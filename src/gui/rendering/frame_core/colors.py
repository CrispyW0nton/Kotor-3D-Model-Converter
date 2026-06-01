"""Compatibility facade for :mod:`src.core.rendering.frame_core.colors`."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.rendering.frame_core.colors")
sys.modules[__name__] = _module
globals().update(_module.__dict__)
