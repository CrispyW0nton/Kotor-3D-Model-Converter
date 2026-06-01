"""Compatibility facade for backend Aurora light conversion helpers.

Canonical owner: :mod:`src.core.lighting.aurora_light_adapter`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.aurora_light_adapter")
sys.modules[__name__] = _module
