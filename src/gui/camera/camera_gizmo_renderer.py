"""Lightweight viewport drawing for camera helpers and frustums."""

from __future__ import annotations

import math

from .camera_math import add, camera_forward, cross, length, mul, normalize, rotate_vector


class CameraGizmoRenderer:
    def __init__(self) -> None:
        self.show_camera_helpers = True
        self.show_camera_frustums = True
        self.show_focus_plane = True

    def draw(self, draw, cameras, active_camera_id: str, projector, width: int, height: int) -> None:
        if not self.show_camera_helpers:
            return
        for camera in cameras:
            if not bool(getattr(camera, "visible", True)) or bool(getattr(camera, "deleted", False)):
                continue
            self._draw_camera(draw, camera, camera.id == active_camera_id, projector, width, height)

    def _draw_camera(self, draw, camera, active: bool, projector, width: int, height: int) -> None:
        pos = tuple(camera.position)
        p = projector(pos[0], pos[1], pos[2], width, height)
        if p is None:
            return
        selected = bool(getattr(camera, "selected", False))
        color = (98, 190, 255, 245) if active else ((255, 214, 88, 245) if selected else (180, 210, 220, 210))
        fill = (98, 190, 255, 70) if active else ((255, 214, 88, 68) if selected else (80, 100, 110, 55))
        x, y = int(p[0]), int(p[1])
        r = 7 if selected or active else 5
        draw.rectangle([x - r, y - r, x + r, y + r], outline=color, fill=fill, width=2 if selected or active else 1)
        draw.line([x + r, y - 3, x + r + 7, y - 7, x + r + 7, y + 7, x + r, y + 3], fill=color, width=1)
        if self.show_camera_frustums:
            self._draw_frustum(draw, camera, color, projector, width, height)
        if bool(getattr(camera, "target_enabled", False)):
            self._draw_target(draw, camera, color, projector, width, height)

    def _draw_target(self, draw, camera, color, projector, width: int, height: int) -> None:
        target = tuple(camera.target_position)
        tp = projector(target[0], target[1], target[2], width, height)
        cp = projector(camera.position[0], camera.position[1], camera.position[2], width, height)
        if tp is None:
            return
        x, y = int(tp[0]), int(tp[1])
        draw.ellipse([x - 5, y - 5, x + 5, y + 5], outline=color, fill=(color[0], color[1], color[2], 50), width=2)
        draw.line([x - 8, y, x + 8, y], fill=color, width=1)
        draw.line([x, y - 8, x, y + 8], fill=color, width=1)
        if cp is not None:
            draw.line([int(cp[0]), int(cp[1]), x, y], fill=(color[0], color[1], color[2], 150), width=1)

    def _draw_frustum(self, draw, camera, color, projector, width: int, height: int) -> None:
        pos = tuple(camera.position)
        forward = camera_forward(camera.rotation)
        if bool(getattr(camera, "target_enabled", False)):
            forward = normalize((camera.target_position[0] - pos[0], camera.target_position[1] - pos[1], camera.target_position[2] - pos[2]))
        right = normalize(cross(forward, (0.0, 0.0, 1.0)))
        if length(right) <= 1e-6:
            right = normalize(cross(forward, (0.0, 1.0, 0.0)))
        up = normalize(cross(right, forward))
        fov = math.radians(max(1.0, min(179.0, float(camera.field_of_view_degrees))))
        aspect = max(0.05, float(camera.aspect_ratio_width) / max(1.0, float(camera.aspect_ratio_height)))
        near = max(0.05, min(float(camera.near_clip), 10.0))
        far = max(near + 0.25, min(float(camera.focus_distance or 8.0), 8.0))
        for dist, alpha in ((near, 100), (far, 170)):
            hh = math.tan(fov * 0.5) * dist
            hw = hh * aspect
            center = add(pos, mul(forward, dist))
            corners = [
                add(add(center, mul(right, -hw)), mul(up, -hh)),
                add(add(center, mul(right, hw)), mul(up, -hh)),
                add(add(center, mul(right, hw)), mul(up, hh)),
                add(add(center, mul(right, -hw)), mul(up, hh)),
            ]
            pts = [projector(c[0], c[1], c[2], width, height) for c in corners]
            if all(pt is not None for pt in pts):
                screen = [(int(pt[0]), int(pt[1])) for pt in pts if pt is not None]
                draw.line(screen + [screen[0]], fill=(color[0], color[1], color[2], alpha), width=1)
                if dist == far:
                    cp = projector(pos[0], pos[1], pos[2], width, height)
                    if cp is not None:
                        for point in screen:
                            draw.line([int(cp[0]), int(cp[1]), point[0], point[1]], fill=(color[0], color[1], color[2], 125), width=1)
