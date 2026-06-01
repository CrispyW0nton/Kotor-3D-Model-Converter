"""Compatibility facade for :mod:`src.core.gizmo.gizmo_picker`."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.gizmo.gizmo_picker")
sys.modules[__name__] = _module
