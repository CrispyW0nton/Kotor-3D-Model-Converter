"""Compatibility facade for :mod:`src.core.camera.camera_viewport_adapter`."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.camera.camera_viewport_adapter")
sys.modules[__name__] = _module
