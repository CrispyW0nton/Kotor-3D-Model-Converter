"""Compatibility facade for backend picking helpers.

Canonical owner: :mod:`src.core.rendering.picking`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.rendering.picking")
sys.modules[__name__] = _module
