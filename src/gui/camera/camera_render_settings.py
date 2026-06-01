"""Compatibility facade for backend camera render settings.

Canonical owner: :mod:`src.core.camera.camera_render_settings`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.camera.camera_render_settings")
sys.modules[__name__] = _module
