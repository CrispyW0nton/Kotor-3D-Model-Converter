"""Compatibility facade for backend TPC render utilities.

Canonical owner: :mod:`src.core.graphics.tpc_render_utils`.
"""

from importlib import import_module
import sys

_TARGET = "src.core.graphics.tpc_render_utils"
_module = import_module(_TARGET)
sys.modules[__name__] = _module
