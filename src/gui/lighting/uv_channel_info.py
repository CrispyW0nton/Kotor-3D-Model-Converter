"""Compatibility facade for backend lightmap UV channel records.

Canonical owner: :mod:`src.core.lighting.uv_channel_info`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.uv_channel_info")
sys.modules[__name__] = _module
