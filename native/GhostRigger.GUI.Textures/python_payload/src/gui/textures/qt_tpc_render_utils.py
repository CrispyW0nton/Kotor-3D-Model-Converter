"""Qt-facing bridge for TPC render helpers."""

from importlib import import_module
import sys

_TARGET = "src.core.graphics.tpc_render_utils"
_module = import_module(_TARGET)
sys.modules[__name__] = _module

