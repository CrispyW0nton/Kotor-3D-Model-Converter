"""Compatibility facade for backend viewport display mode state.

Canonical owner: :mod:`src.core.rendering.viewport_display`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.rendering.viewport_display")
sys.modules[__name__] = _module
