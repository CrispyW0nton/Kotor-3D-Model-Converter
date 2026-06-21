"""Compatibility facade for backend skeleton render-data helpers.

Canonical owner: :mod:`src.core.rendering.skeleton_render_data`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.rendering.skeleton_render_data")
sys.modules[__name__] = _module
