"""Compatibility facade for backend camera render output helpers.

Canonical owner: :mod:`src.core.camera.render_output`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.camera.render_output")
sys.modules[__name__] = _module
