"""Qt-facing bridge for GhostRigger's acceleration layer.

The original ``accel.py`` is renderer/math code rather than Tk UI.  The Qt
counterpart deliberately re-exports the same acceleration API so Qt viewport
work can depend on a ``qt_`` module without duplicating the JIT/NumPy logic.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.rendering.accel")
sys.modules[__name__] = _module

