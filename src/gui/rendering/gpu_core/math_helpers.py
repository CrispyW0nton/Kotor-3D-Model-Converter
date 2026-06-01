"""Compatibility shim for GPU renderer math helpers.

Canonical math helpers live under :mod:`src.math.gpu_math`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.math.gpu_math")
sys.modules[__name__] = _module
