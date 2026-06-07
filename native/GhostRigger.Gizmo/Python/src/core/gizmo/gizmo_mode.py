"""Transform gizmo mode declarations."""

from __future__ import annotations

from enum import Enum


class GizmoMode(Enum):
    """Viewport transform modes."""

    TRANSLATE = "translate"
    ROTATE = "rotate"
    SCALE = "scale"


TransformGizmoMode = GizmoMode


class TransformSpace(Enum):
    """Coordinate space for gizmo axes."""

    WORLD = "world"
    LOCAL = "local"
