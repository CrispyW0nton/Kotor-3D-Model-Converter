"""Compatibility facade for backend lighting enums.

Canonical owner: :mod:`src.core.lighting.light_types`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.light_types")
sys.modules[__name__] = _module
