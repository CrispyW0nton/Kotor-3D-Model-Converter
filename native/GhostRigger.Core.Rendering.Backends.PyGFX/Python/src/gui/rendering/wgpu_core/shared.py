"""Compatibility alias for WGPU shared adapter helpers."""

from __future__ import annotations

import sys
from importlib import import_module

_module = import_module("src.adapters.rendering.wgpu_core.shared")
sys.modules[__name__] = _module
