"""Qt-facing bridge for the GPU renderer.

``gpu_renderer.py`` is already GUI-toolkit agnostic.  This module is the Qt
landing point for future QOpenGLWidget integration while keeping existing
renderer classes available under the migration naming convention.
"""

from __future__ import annotations

from .gpu_renderer import *  # noqa: F401,F403

