"""Compatibility facade for the null diagnostic viewport renderer."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.adapters.rendering.null_renderer")
sys.modules[__name__] = _module
