"""Compatibility facade for backend renderer settings.

Canonical owner: :mod:`src.core.rendering.renderer_settings`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.rendering.renderer_settings")
sys.modules[__name__] = _module
