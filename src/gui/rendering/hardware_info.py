"""Compatibility facade for backend hardware diagnostics helpers.

Canonical owner: :mod:`src.core.rendering.hardware_info`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_FACADE_NAME = __name__
_module = import_module("src.core.rendering.hardware_info")
globals().update(_module.__dict__)
sys.modules[_FACADE_NAME] = _module
_parent_name, _, _child_name = _FACADE_NAME.rpartition(".")
_parent = sys.modules.get(_parent_name)
if _parent is not None:
    setattr(_parent, _child_name, _module)
