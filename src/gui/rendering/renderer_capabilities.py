"""Compatibility facade for backend renderer capability records.

Canonical owner: :mod:`src.core.rendering.renderer_capabilities`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.rendering.renderer_capabilities")
sys.modules[__name__] = _module
