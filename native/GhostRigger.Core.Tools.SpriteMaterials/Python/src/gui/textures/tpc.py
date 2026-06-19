"""Compatibility facade for backend TPC texture-format helpers.

Canonical owner: :mod:`src.core.graphics.tpc`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.graphics.tpc")
sys.modules[__name__] = _module
