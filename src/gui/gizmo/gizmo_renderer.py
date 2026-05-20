"""PIL renderer for the transform gizmo overlay."""

from __future__ import annotations

import math

from .gizmo_mode import GizmoMode


class GizmoRenderer:
    """Draws a stable screen-size transform gizmo and caches pick handles."""

    AXIS_COLORS = {
        "X": (220, 60, 60, 255),
        "Y": (60, 220, 80, 255),
        "Z": (70, 135, 240, 255),
    }
    HILITE = (255, 235, 80, 255)

    def __init__(self):
        self.handles: list[dict] = []

    def draw(self, draw, gizmo, camera, projector, width: int, height: int) -> list[dict]:
        self.handles = []
        if not gizmo.visible or gizmo.selected_object is None:
            return self.handles
        center = gizmo.position
        cp = projector(center[0], center[1], center[2], width, height)
        if cp is None:
            return self.handles
        cx, cy, depth = cp
        world_per_px = (2.0 * max(0.5, float(depth)) * math.tan(math.radians(float(camera.fov)) * 0.5)) / max(1, height)
        arm_world = 82.0 * world_per_px
        axes = {"X": (arm_world, 0.0, 0.0), "Y": (0.0, arm_world, 0.0), "Z": (0.0, 0.0, arm_world)}
        if gizmo.mode == GizmoMode.TRANSLATE:
            self._draw_translate(draw, gizmo, projector, width, height, (cx, cy), center, axes)
        elif gizmo.mode == GizmoMode.ROTATE:
            self._draw_rotate(draw, gizmo, camera, projector, width, height, (cx, cy, depth), center, arm_world)
        elif gizmo.mode == GizmoMode.SCALE:
            self._draw_scale(draw, gizmo, projector, width, height, (cx, cy), center, axes)
        return self.handles

    def _color(self, gizmo, handle: str, axis: str):
        return self.HILITE if handle in (gizmo.hovered_handle, gizmo.active_handle) else self.AXIS_COLORS[axis]

    def _draw_translate(self, draw, gizmo, projector, width, height, center_screen, center_world, axes) -> None:
        cx, cy = center_screen
        for axis, delta in axes.items():
            name = f"TRANSLATE_{axis}"
            sp = projector(center_world[0] + delta[0], center_world[1] + delta[1], center_world[2] + delta[2], width, height)
            if sp is None:
                continue
            sx, sy, _ = sp
            col = self._color(gizmo, name, axis)
            line_w = 4 if name in (gizmo.hovered_handle, gizmo.active_handle) else 3
            draw.line([cx, cy, sx, sy], fill=col, width=line_w)
            self._draw_arrowhead(draw, cx, cy, sx, sy, col)
            self.handles.append({"name": name, "kind": "segment", "start": (cx, cy), "end": (sx, sy), "radius": 10})
        draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(235, 235, 235, 255), outline=(30, 32, 36, 255), width=2)

    def _draw_scale(self, draw, gizmo, projector, width, height, center_screen, center_world, axes) -> None:
        cx, cy = center_screen
        uniform_active = "SCALE_UNIFORM" in (gizmo.hovered_handle, gizmo.active_handle)
        for axis, delta in axes.items():
            name = f"SCALE_{axis}"
            sp = projector(center_world[0] + delta[0], center_world[1] + delta[1], center_world[2] + delta[2], width, height)
            if sp is None:
                continue
            sx, sy, _ = sp
            col = self.HILITE if uniform_active else self._color(gizmo, name, axis)
            draw.line([cx, cy, sx, sy], fill=col, width=4 if uniform_active or name == gizmo.active_handle else 3)
            draw.rectangle([sx - 6, sy - 6, sx + 6, sy + 6], fill=col, outline=(20, 22, 26, 255), width=2)
            self.handles.append({"name": name, "kind": "segment", "start": (cx, cy), "end": (sx, sy), "radius": 10})
            self.handles.append({"name": name, "kind": "point", "pos": (sx, sy), "radius": 12})
        uniform_col = self.HILITE if uniform_active else (235, 235, 235, 255)
        draw.rectangle([cx - 7, cy - 7, cx + 7, cy + 7], fill=uniform_col, outline=(20, 22, 26, 255), width=2)
        self.handles.append({"name": "SCALE_UNIFORM", "kind": "point", "pos": (cx, cy), "radius": 14, "priority": 10})

    def _draw_rotate(self, draw, gizmo, camera, projector, width, height, center_screen, center_world, radius_world) -> None:
        cx, cy, center_depth = center_screen
        radius_px = 82
        draw.ellipse(
            [cx - radius_px, cy - radius_px, cx + radius_px, cy + radius_px],
            outline=(160, 166, 176, 95),
            width=1,
        )

        ring_points = {
            "X": self._world_ring_points(center_world, radius_world, (0, 1, 0), (0, 0, 1)),
            "Y": self._world_ring_points(center_world, radius_world, (1, 0, 0), (0, 0, 1)),
            "Z": self._world_ring_points(center_world, radius_world, (1, 0, 0), (0, 1, 0)),
        }
        projected: dict[str, list[tuple[int, int, float] | None]] = {}
        for axis, points in ring_points.items():
            projected[axis] = [projector(px, py, pz, width, height) for px, py, pz in points]

        # Draw far halves first in muted color, then near halves bright. This
        # gives the rings a readable 3-D order without depth-buffer access.
        for front_pass in (False, True):
            for axis in ("X", "Y", "Z"):
                name = f"ROTATE_{axis}"
                base_col = self._color(gizmo, name, axis)
                active = name in (gizmo.hovered_handle, gizmo.active_handle)
                col = base_col if front_pass else self._muted(base_col)
                line_w = 5 if active else 3
                if not front_pass:
                    line_w = max(2, line_w - 1)
                self._draw_projected_ring_segments(
                    draw,
                    projected[axis],
                    col,
                    line_w,
                    center_depth,
                    front=front_pass,
                )
                if front_pass:
                    polyline = [(p[0], p[1]) for p in projected[axis] if p is not None]
                    if polyline:
                        self.handles.append(
                            {
                                "name": name,
                                "kind": "polyline",
                                "points": polyline,
                                "radius": 10,
                            }
                        )
        draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(235, 235, 235, 255), outline=(20, 22, 26, 255), width=1)

    @staticmethod
    def _draw_arrowhead(draw, cx, cy, sx, sy, color) -> None:
        dx, dy = float(sx - cx), float(sy - cy)
        length = math.hypot(dx, dy)
        if length <= 1.0:
            return
        ux, uy = dx / length, dy / length
        px, py = -uy * 6.0, ux * 6.0
        draw.polygon(
            [(sx, sy), (sx - ux * 13 + px, sy - uy * 13 + py), (sx - ux * 13 - px, sy - uy * 13 - py)],
            fill=color,
        )

    @staticmethod
    def _muted(color):
        r, g, b, *rest = color
        a = rest[0] if rest else 255
        return (max(25, int(r * 0.32)), max(25, int(g * 0.32)), max(25, int(b * 0.32)), min(170, a))

    @staticmethod
    def _world_ring_points(center, radius, u, v, steps: int = 144):
        cx, cy, cz = float(center[0]), float(center[1]), float(center[2])
        ux, uy, uz = float(u[0]), float(u[1]), float(u[2])
        vx, vy, vz = float(v[0]), float(v[1]), float(v[2])
        pts = []
        for i in range(steps + 1):
            t = math.tau * float(i) / float(steps)
            ct = math.cos(t) * radius
            st = math.sin(t) * radius
            pts.append((cx + ux * ct + vx * st, cy + uy * ct + vy * st, cz + uz * ct + vz * st))
        return pts

    @staticmethod
    def _draw_projected_ring_segments(draw, points, color, width: int, center_depth: float, *, front: bool) -> None:
        for a, b in zip(points, points[1:]):
            if a is None or b is None:
                continue
            avg_depth = (float(a[2]) + float(b[2])) * 0.5
            is_front = avg_depth <= float(center_depth)
            if is_front != front:
                continue
            draw.line([a[0], a[1], b[0], b[1]], fill=color, width=width)
