"""Constants and cache keys for viewport light helpers.

The actual GPU drawing path lives in ``gpu_renderer.py`` so it can use the
existing ModernGL programs. This module keeps the shared policy centralized.
"""

from __future__ import annotations


LIGHT_HELPER_COLORS = {
    "point": (0.72, 0.60, 0.16),
    "aurora_point": (0.72, 0.60, 0.16),
    "spot": (0.32, 0.62, 0.78),
    "directional": (0.38, 0.74, 0.36),
    "area": (0.78, 0.42, 0.30),
    "ambient": (0.50, 0.52, 0.76),
    "aurora_ambient": (0.50, 0.52, 0.76),
}

LIGHT_HELPER_MARKER_RADIUS = 0.18
LIGHT_HELPER_POINT_RADIUS = 0.65
LIGHT_HELPER_SPOT_LENGTH = 1.15
LIGHT_HELPER_SPOT_CAP_MAX_RADIUS = 0.55
LIGHT_HELPER_DIRECTION_LENGTH = 1.4
LIGHT_HELPER_AREA_SIZE = 0.8
LIGHT_HELPER_SELECTED_BOOST = 1.28


def helper_cache_key(light: object) -> tuple:
    return (
        str(getattr(light, "light_kind", "point") or "point"),
    )
