"""Compatibility facade for backend renderer interface contracts.

Canonical owner: :mod:`src.core.rendering.renderer_interface`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.rendering.renderer_interface")
sys.modules[__name__] = _module
