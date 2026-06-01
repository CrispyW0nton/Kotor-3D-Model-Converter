"""Compatibility facade for backend light manager service.

Canonical owner: :mod:`src.core.lighting.light_manager`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.light_manager")
sys.modules[__name__] = _module
