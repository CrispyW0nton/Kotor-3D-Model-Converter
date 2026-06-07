"""Compatibility facade for backend lighting settings persistence.

Canonical owner: :mod:`src.core.lighting.settings`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.settings")
sys.modules[__name__] = _module
