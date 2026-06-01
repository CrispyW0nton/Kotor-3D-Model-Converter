"""Compatibility facade for Qt viewport camera-helper drawing.

Canonical owner: :mod:`src.adapters.qt_viewport.camera_gizmo_renderer`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.adapters.qt_viewport.camera_gizmo_renderer")
sys.modules[__name__] = _module
