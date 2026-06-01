"""Compatibility facade for the Qt viewport still-frame renderer adapter."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.adapters.qt_viewport.still_frame_renderer")
sys.modules[__name__] = _module
