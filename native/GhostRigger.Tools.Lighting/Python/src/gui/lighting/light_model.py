"""Compatibility facade for backend editable light records.

Canonical owner: :mod:`src.core.lighting.light_model`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.light_model")
sys.modules[__name__] = _module
