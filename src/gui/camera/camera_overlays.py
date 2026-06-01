"""Compatibility facade for Qt viewport camera overlay drawing.

Canonical owner: :mod:`src.adapters.qt_viewport.camera_overlays`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.adapters.qt_viewport.camera_overlays")
sys.modules[__name__] = _module
