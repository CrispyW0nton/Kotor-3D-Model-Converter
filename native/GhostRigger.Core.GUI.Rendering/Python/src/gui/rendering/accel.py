"""Compatibility facade for backend software-render acceleration helpers.

Canonical owner: :mod:`src.core.rendering.accel`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.rendering.accel")
sys.modules[__name__] = _module
