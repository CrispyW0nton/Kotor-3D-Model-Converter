"""Compatibility facade for backend ArcBall camera state.

Canonical owner: :mod:`src.core.camera.arcball_camera`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.camera.arcball_camera")
sys.modules[__name__] = _module
