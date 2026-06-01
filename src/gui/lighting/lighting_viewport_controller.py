"""Compatibility facade for viewport lighting-state adapter.

Canonical owner: :mod:`src.adapters.qt_viewport.lighting_viewport_controller`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.adapters.qt_viewport.lighting_viewport_controller")
sys.modules[__name__] = _module
