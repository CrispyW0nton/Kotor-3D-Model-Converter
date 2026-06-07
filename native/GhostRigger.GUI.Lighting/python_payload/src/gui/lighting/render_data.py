"""Compatibility facade for backend lighting render-data snapshots.

Canonical owner: :mod:`src.core.lighting.render_data`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.render_data")
sys.modules[__name__] = _module
