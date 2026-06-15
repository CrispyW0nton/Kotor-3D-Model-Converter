"""Compatibility facade for backend camera scene DTOs.

Canonical owner: :mod:`src.core.camera.camera_model`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.camera.camera_model")
sys.modules[__name__] = _module
