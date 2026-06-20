"""Compatibility facade for backend light grouping helpers.

Canonical owner: :mod:`src.core.lighting.light_grouping`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.light_grouping")
sys.modules[__name__] = _module
