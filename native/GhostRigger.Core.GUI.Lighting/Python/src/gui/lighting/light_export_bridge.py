"""Compatibility facade for backend light export bridge helpers.

Canonical owner: :mod:`src.core.lighting.light_export_bridge`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.light_export_bridge")
sys.modules[__name__] = _module
