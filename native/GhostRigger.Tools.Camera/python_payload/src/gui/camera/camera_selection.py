"""Compatibility facade for :mod:`src.core.camera.camera_selection`."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.camera.camera_selection")
sys.modules[__name__] = _module
