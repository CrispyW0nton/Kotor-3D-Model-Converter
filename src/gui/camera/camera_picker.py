"""Viewport camera helper picking."""

from __future__ import annotations

import math
from typing import Callable

from .camera_math import length, sub


class CameraPicker:
    def __init__(self, max_screen_distance: int = 14) -> None:
        self.max_screen_distance = int(max_screen_distance)

    def hit_test(
        self,
        cameras,
        sx: int,
        sy: int,
        width: int,
        height: int,
        project: Callable[[float, float, float, int, int], tuple | None],
    ):
        best = None
        best_score = float("inf")
        limit2 = float(self.max_screen_distance * self.max_screen_distance)
        for camera in cameras:
            if not bool(getattr(camera, "visible", True)) or bool(getattr(camera, "deleted", False)):
                continue
            candidates = [("camera", getattr(camera, "position", (0.0, 0.0, 0.0)))]
            if bool(getattr(camera, "target_enabled", False)):
                candidates.append(("target", getattr(camera, "target_position", (0.0, 0.0, 0.0))))
            for kind, point in candidates:
                try:
                    proj = project(float(point[0]), float(point[1]), float(point[2]), width, height)
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
                score = dist2 + depth * 0.001 - (6.0 if kind == "target" else 0.0)
                if score < best_score:
                    best_score = score
                    best = (camera, kind)
        return best
