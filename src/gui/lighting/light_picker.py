"""Viewport light helper picking."""

from __future__ import annotations

import math
from typing import Callable


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
    ):
        best_node = None
        best_score = float("inf")
        limit2 = float(self.max_screen_distance * self.max_screen_distance)
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
            if dist2 > limit2:
                continue
            depth = max(0.0, float(proj[2]))
            radius = max(0.0, float(getattr(node, "light_radius", 0.0) or 0.0))
            helper_bonus = min(4.0, math.sqrt(radius) * 0.15)
            score = dist2 + depth * 0.001 - helper_bonus
            if score < best_score:
                best_score = score
                best_node = node
        return best_node
