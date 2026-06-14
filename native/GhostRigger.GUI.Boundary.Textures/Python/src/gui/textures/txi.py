"""Compatibility facade for backend TXI texture metadata helpers.

Canonical owner: :mod:`src.core.graphics.txi`.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("src.core.graphics.txi")
sys.modules[__name__] = _module
