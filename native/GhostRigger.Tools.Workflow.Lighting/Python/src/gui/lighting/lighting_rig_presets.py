"""Compatibility facade for backend generated lighting rig presets.

Canonical owner: :mod:`src.core.lighting.lighting_rig_presets`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.lighting.lighting_rig_presets")
sys.modules[__name__] = _module
