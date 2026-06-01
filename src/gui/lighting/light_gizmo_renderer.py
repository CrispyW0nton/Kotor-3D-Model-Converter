"""Compatibility facade for backend light helper drawing policy.

Canonical owner: :mod:`src.core.lighting.light_gizmo_renderer`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.light_gizmo_renderer")
sys.modules[__name__] = _module
