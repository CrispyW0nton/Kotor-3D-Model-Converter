"""Compatibility facade for backend renderer performance helpers.

Canonical owner: :mod:`src.core.rendering.renderer_performance`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.rendering.renderer_performance")
sys.modules[__name__] = _module
