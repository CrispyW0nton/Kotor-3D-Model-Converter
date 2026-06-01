"""Compatibility alias for WGPU resource adapter helpers."""

from __future__ import annotations

import sys
from importlib import import_module

_module = import_module("src.adapters.rendering.wgpu_core.resources")
sys.modules[__name__] = _module
