"""Compatibility shim for camera math helpers.

Canonical math helpers live under :mod:`src.math.camera_math`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.math.camera_math")
sys.modules[__name__] = _module
