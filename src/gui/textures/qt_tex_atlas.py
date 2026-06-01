"""Qt-facing bridge for texture atlas caches."""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.graphics.tex_atlas")
sys.modules[__name__] = _module

