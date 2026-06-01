"""Compatibility alias for viewport renderer adapter selection."""

from __future__ import annotations

import sys
from importlib import import_module

_module = import_module("src.adapters.rendering.renderer_factory")
sys.modules[__name__] = _module
