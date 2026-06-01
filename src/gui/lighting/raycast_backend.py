"""Compatibility facade for backend lightmap raycast helpers.

Canonical owner: :mod:`src.core.lighting.raycast_backend`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.raycast_backend")
sys.modules[__name__] = _module
