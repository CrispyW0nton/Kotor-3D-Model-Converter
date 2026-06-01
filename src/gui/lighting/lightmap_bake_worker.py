"""Compatibility facade for the Qt lightmap bake worker."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.gui.dialogs.lightmap_bake_worker")
sys.modules[__name__] = _module
