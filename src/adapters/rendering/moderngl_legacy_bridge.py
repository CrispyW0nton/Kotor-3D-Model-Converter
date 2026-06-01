"""Bridge to the current ModernGL renderer implementation.

The large ModernGL renderer and VBO builder still live behind the public GUI
facade until their transform/skinning-sensitive code is migrated separately.
Keep direct GUI imports isolated here so other renderer adapters depend on an
explicit boundary instead of reaching into GUI packages ad hoc.
"""

from __future__ import annotations

from src.gui.rendering.gpu_core import renderer as _gpu_renderer_impl
from src.gui.rendering.gpu_core.renderer import GpuRenderer
from src.gui.rendering.gpu_core.resources import _build_vbo_data


def moderngl_runtime_available() -> bool:
    return bool(getattr(_gpu_renderer_impl, "_MODERNGL", False) and getattr(_gpu_renderer_impl, "_NUMPY", False))


__all__ = ("GpuRenderer", "_build_vbo_data", "moderngl_runtime_available")
