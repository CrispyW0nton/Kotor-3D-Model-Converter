"""Qt-facing bridge for the GPU renderer.

``gpu_renderer.py`` is already GUI-toolkit agnostic.  This module is the Qt
landing point for future QOpenGLWidget integration while keeping existing
renderer classes available under the migration naming convention.
"""

from __future__ import annotations

from src.gui.qt_lib.rendering.gpu_renderer import *  # noqa: F401,F403
from src.gui.qt_lib.rendering.renderer_factory import (  # noqa: F401
    FallbackViewportRenderer,
    create_viewport_renderer,
    renderer_capabilities_snapshot,
)

