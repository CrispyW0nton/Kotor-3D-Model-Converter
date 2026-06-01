"""Compatibility facade for ModernGL diagnostics helpers."""

from __future__ import annotations

from src.adapters.gpu.moderngl_context import (
    _create_moderngl_standalone_context,
    _gl_context_backend_candidates,
)
from src.adapters.gpu.moderngl_runtime import *  # noqa: F401,F403
from src.adapters.gpu.viewport_probe import *  # noqa: F401,F403
from src.core.geometry.model_data import KOTOR_BASE_SKELETONS as _KOTOR_BASE_SKELETONS
from src.core.lighting.light_gizmo_renderer import (
    LIGHT_HELPER_AREA_SIZE,
    LIGHT_HELPER_COLORS,
    LIGHT_HELPER_DIRECTION_LENGTH,
    LIGHT_HELPER_MARKER_RADIUS,
    LIGHT_HELPER_POINT_RADIUS,
    LIGHT_HELPER_SELECTED_BOOST,
    LIGHT_HELPER_SPOT_CAP_MAX_RADIUS,
    LIGHT_HELPER_SPOT_LENGTH,
)
from src.core.rendering.color_utils import *  # noqa: F401,F403
from src.core.rendering.gpu_debug_tables import ModuleDrawItem
from src.core.rendering.gpu_diagnostics_config import *  # noqa: F401,F403
from src.core.rendering.gpu_diagnostics_records import *  # noqa: F401,F403
from src.core.special.render_constants import (
    FACE_MESH_SUBSTRINGS as _FACE_MESH_SUBSTRINGS,
    INNER_GEO_SUBSTRINGS as _INNER_GEO_SUBSTRINGS,
)

__all__ = tuple(name for name in globals() if not name.startswith("__"))
