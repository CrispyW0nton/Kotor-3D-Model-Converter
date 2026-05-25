"""Viewport light helper picking."""

from __future__ import annotations

import math
from typing import Callable

from .light_gizmo_renderer import (
    LIGHT_HELPER_AREA_SIZE,
    LIGHT_HELPER_DIRECTION_LENGTH,
    LIGHT_HELPER_MARKER_RADIUS,
    LIGHT_HELPER_POINT_RADIUS,
    LIGHT_HELPER_SPOT_CAP_MAX_RADIUS,
    LIGHT_HELPER_SPOT_LENGTH,
)


class LightPicker:
    def __init__(self, max_screen_distance: int = 12) -> None:
        self.max_screen_distance = int(max_screen_distance)

    def hit_test(
        self,
        lights,
        sx: int,
        sy: int,
        width: int,
        height: int,
        project: Callable[[float, float, float, int, int], tuple | None],
        world_transform: Callable[[object], tuple],
        *,
        include_volumes: bool = True,
    ):
        best_node = None
        best_score = float("inf")
        base_limit = float(self.max_screen_distance)
        for node in lights:
            if not bool(getattr(node, "is_light", False)):
                continue
            if bool(getattr(node, "_gr_light_hidden", False)) or bool(getattr(node, "_gr_light_deleted", False)):
                continue
            try:
                wp, _wo, _is_id = world_transform(node)
            except Exception:
                wp = getattr(node, "position", (0.0, 0.0, 0.0))
            try:
                proj = project(float(wp[0]), float(wp[1]), float(wp[2]), width, height)
            except Exception:
                proj = None
            if proj is None:
                continue
            dx = float(proj[0]) - float(sx)
            dy = float(proj[1]) - float(sy)
            dist2 = dx * dx + dy * dy
            helper_radius = self._projected_helper_radius(
                node,
                wp,
                width,
                height,
                project,
                include_volumes=include_volumes,
            )
            limit = max(base_limit, helper_radius + base_limit * 0.45)
            if dist2 > limit * limit:
                continue
            depth = max(0.0, float(proj[2]))
            ring_error = max(0.0, math.sqrt(dist2) - helper_radius)
            selected_bonus = 20.0 if bool(getattr(node, "_gr_light_selected", False)) else 0.0
            score = ring_error * ring_error + depth * 0.001 - selected_bonus
            if score < best_score:
                best_score = score
                best_node = node
        return best_node

    def _projected_helper_radius(
        self,
        node: object,
        wp,
        width: int,
        height: int,
        project: Callable[[float, float, float, int, int], tuple | None],
        *,
        include_volumes: bool,
    ) -> float:
        helper_kind = str(getattr(node, "light_kind", "point") or "point").lower().replace("aurora_", "")
        world_radius = LIGHT_HELPER_MARKER_RADIUS
        if include_volumes:
            if helper_kind == "point":
                world_radius = LIGHT_HELPER_POINT_RADIUS
            elif helper_kind == "spot":
                cap_radius = min(
                    math.tan(math.radians(float(getattr(node, "light_cone_degrees", 45.0) or 45.0) * 0.5)) * LIGHT_HELPER_SPOT_LENGTH,
                    LIGHT_HELPER_SPOT_CAP_MAX_RADIUS,
                )
                world_radius = max(LIGHT_HELPER_SPOT_LENGTH * 0.45, cap_radius)
            elif helper_kind == "area":
                world_radius = LIGHT_HELPER_AREA_SIZE * 0.75
            elif helper_kind == "directional":
                world_radius = LIGHT_HELPER_DIRECTION_LENGTH * 0.45
        center = project(float(wp[0]), float(wp[1]), float(wp[2]), width, height)
        if center is None:
            return 0.0
        best = 0.0
        for axis in ((world_radius, 0.0, 0.0), (0.0, world_radius, 0.0), (0.0, 0.0, world_radius)):
            try:
                edge = project(float(wp[0]) + axis[0], float(wp[1]) + axis[1], float(wp[2]) + axis[2], width, height)
            except Exception:
                edge = None
            if edge is None:
                continue
            dx = float(edge[0]) - float(center[0])
            dy = float(edge[1]) - float(center[1])
            best = max(best, math.sqrt(dx * dx + dy * dy))
        return best
