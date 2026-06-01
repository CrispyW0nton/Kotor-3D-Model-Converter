"""Compatibility facade for :mod:`src.core.gizmo.transform_gizmo`."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.gizmo.transform_gizmo")
sys.modules[__name__] = _module
globals().update(_module.__dict__)
