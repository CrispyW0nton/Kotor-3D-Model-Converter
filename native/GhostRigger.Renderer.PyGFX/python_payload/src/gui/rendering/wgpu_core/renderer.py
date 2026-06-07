"""Compatibility alias for the WGPU viewport renderer adapter."""

from __future__ import annotations

import sys
from importlib import import_module

_module = import_module("src.adapters.rendering.wgpu_core.renderer")
sys.modules[__name__] = _module
