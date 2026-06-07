"""Compatibility facade for backend renderer identifiers.

Canonical owner: :mod:`src.core.rendering.renderer_backend`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.rendering.renderer_backend")
sys.modules[__name__] = _module
