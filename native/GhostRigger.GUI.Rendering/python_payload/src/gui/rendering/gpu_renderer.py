"""Compatibility facade for public ModernGL renderer exports."""

from importlib import import_module
import sys

_TARGET = "src.adapters.rendering.gpu_renderer_exports"
_module = import_module(_TARGET)
sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(getattr(_module, "_main")())
