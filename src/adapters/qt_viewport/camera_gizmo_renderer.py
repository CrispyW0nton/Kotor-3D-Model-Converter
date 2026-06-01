"""Viewport drawing for camera helpers and frustums."""

from __future__ import annotations

import math

from src.math.camera_math import add, camera_forward, cross, length, mul, normalize


class CameraGizmoRenderer:
    def __init__(self) -> None:
        self.show_camera_helpers = True
        self.show_camera_frustums = True
        self.show_focus_plane = True
        self.reset_theme_colors()

    @staticmethod
    def _hex_to_rgba(value: str, fallback: tuple[int, int, int, int], alpha: int | None = None) -> tuple[int, int, int, int]:
        text = str(value or "").strip().lstrip("#")
        try:
            if len(text) not in {6, 8}:
                raise ValueError
            r = int(text[0:2], 16)
            g = int(text[2:4], 16)
            b = int(text[4:6], 16)
            a = int(text[6:8], 16) if len(text) == 8 else fallback[3]
            return (r, g, b, int(alpha if alpha is not None else a))
        except Exception:
            return fallback if alpha is None else (fallback[0], fallback[1], fallback[2], int(alpha))

    @staticmethod
    def _blend(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
        t = max(0.0, min(1.0, float(t)))
        return tuple(int(round(float(a[i]) * (1.0 - t) + float(b[i]) * t)) for i in range(3))

    def set_theme_colors(self, theme) -> None:
        self.camera_color = self._hex_to_rgba(theme.color("viewport.helper.camera", theme.color("viewport.text")), self.camera_color)
        self.camera_selected_color = self._hex_to_rgba(
            theme.color("viewport.helper.cameraSelected", theme.color("selection.background")),
            self.camera_selected_color,
        )
        self.camera_active_color = self._hex_to_rgba(theme.color("accent.secondary", theme.color("accent.primary")), self.camera_active_color)
        self.camera_fill = self._hex_to_rgba(theme.color("viewport.helper.camera", theme.color("viewport.text")), self.camera_fill, alpha=55)
        self.camera_selected_fill = self._hex_to_rgba(
            theme.color("viewport.helper.cameraSelected", theme.color("selection.background")),
            self.camera_selected_fill,
            alpha=68,
        )
        self.camera_active_fill = self._hex_to_rgba(theme.color("accent.secondary", theme.color("accent.primary")), self.camera_active_fill, alpha=70)

    def reset_theme_colors(self) -> None:
        self.camera_color = (180, 210, 220, 210)
        self.camera_selected_color = (255, 214, 88, 245)
        self.camera_hovered_color = (0, 215, 181, 240)
        self.camera_active_color = (98, 190, 255, 245)
        self.camera_fill = (80, 100, 110, 55)
        self.camera_selected_fill = (255, 214, 88, 68)
        self.camera_hovered_fill = (0, 215, 181, 62)
        self.camera_active_fill = (98, 190, 255, 70)
        self.hovered_camera_id = ""

    def set_native_palette_colors(
        self,
        *,
        base: tuple[int, int, int],
        text: tuple[int, int, int],
        highlight: tuple[int, int, int],
    ) -> None:
        bg = tuple(int(v) for v in base[:3])
        fg = tuple(int(v) for v in text[:3])
        hi = tuple(int(v) for v in highlight[:3])
        camera = self._blend(bg, fg, 0.72)
        self.camera_color = (*camera, 210)
        self.camera_selected_color = (255, 214, 88, 245)
        self.camera_hovered_color = (*hi, 230)
        self.camera_active_color = (*hi, 245)
        self.camera_fill = (*camera, 55)
        self.camera_selected_fill = (255, 214, 88, 68)
        self.camera_hovered_fill = (*hi, 58)
        self.camera_active_fill = (*hi, 70)

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
        hovered = str(getattr(camera, "id", "") or "") == str(getattr(self, "hovered_camera_id", "") or "")
        color = self.camera_active_color if active else (self.camera_selected_color if selected else (self.camera_hovered_color if hovered else self.camera_color))
        fill = self.camera_active_fill if active else (self.camera_selected_fill if selected else (self.camera_hovered_fill if hovered else self.camera_fill))
        x, y = int(p[0]), int(p[1])
        r = 7 if selected or active or hovered else 5
        draw.rectangle([x - r, y - r, x + r, y + r], outline=color, fill=fill, width=2 if selected or active or hovered else 1)
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
