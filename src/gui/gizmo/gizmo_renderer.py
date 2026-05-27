"""PIL renderer for the transform gizmo overlay."""

from __future__ import annotations

import math

from .gizmo_draw_data import GizmoDrawCommand, GizmoRenderData, rgba255_to_float
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
        basis = getattr(gizmo, "axis_basis", None) or {}
        axes = {
            axis: (
                float((basis.get(axis) or fallback)[0]) * arm_world,
                float((basis.get(axis) or fallback)[1]) * arm_world,
                float((basis.get(axis) or fallback)[2]) * arm_world,
            )
            for axis, fallback in {
                "X": (1.0, 0.0, 0.0),
                "Y": (0.0, 1.0, 0.0),
                "Z": (0.0, 0.0, 1.0),
            }.items()
        }
        if gizmo.mode == GizmoMode.TRANSLATE:
            self._draw_translate(draw, gizmo, projector, width, height, (cx, cy), center, axes)
        elif gizmo.mode == GizmoMode.ROTATE:
            self._draw_rotate(draw, gizmo, camera, projector, width, height, (cx, cy, depth), center, arm_world, axes)
        elif gizmo.mode == GizmoMode.SCALE:
            self._draw_scale(draw, gizmo, projector, width, height, (cx, cy), center, axes)
        return self.handles

    def build_render_data(self, gizmo, camera, projector, width: int, height: int) -> GizmoRenderData:
        """Build world-space commands that renderers can draw without owning tool policy."""

        if not gizmo.visible or gizmo.selected_object is None:
            return GizmoRenderData()
        center = gizmo.position
        cp = projector(center[0], center[1], center[2], width, height)
        if cp is None:
            return GizmoRenderData(origin=tuple(float(v) for v in center), active_tool=gizmo.mode.value)
        _cx, _cy, depth = cp
        world_per_px = (2.0 * max(0.5, float(depth)) * math.tan(math.radians(float(camera.fov)) * 0.5)) / max(1, height)
        arm_world = 82.0 * world_per_px
        basis = getattr(gizmo, "axis_basis", None) or {}
        axes = {
            axis: self._scaled_axis(basis.get(axis) or fallback, arm_world)
            for axis, fallback in {
                "X": (1.0, 0.0, 0.0),
                "Y": (0.0, 1.0, 0.0),
                "Z": (0.0, 0.0, 1.0),
            }.items()
        }
        commands: list[GizmoDrawCommand] = []
        if gizmo.mode == GizmoMode.TRANSLATE:
            for axis, delta in axes.items():
                name = f"TRANSLATE_{axis}"
                commands.append(self._line_command(center, delta, self._color(gizmo, name, axis), name))
            commands.extend(self._pivot_marker(center, arm_world * 0.06, "TRANSLATE_VIEW"))
        elif gizmo.mode == GizmoMode.SCALE:
            uniform_active = "SCALE_UNIFORM" in (gizmo.hovered_handle, gizmo.active_handle)
            for axis, delta in axes.items():
                name = f"SCALE_{axis}"
                color = self.HILITE if uniform_active else self._color(gizmo, name, axis)
                commands.append(self._line_command(center, delta, color, name))
                endpoint = (center[0] + delta[0], center[1] + delta[1], center[2] + delta[2])
                commands.extend(self._pivot_marker(endpoint, arm_world * 0.045, name))
            commands.extend(self._pivot_marker(center, arm_world * 0.07, "SCALE_UNIFORM"))
        elif gizmo.mode == GizmoMode.ROTATE:
            ring_axes = {
                "X": (axes["Y"], axes["Z"]),
                "Y": (axes["X"], axes["Z"]),
                "Z": (axes["X"], axes["Y"]),
            }
            for axis, (u, v) in ring_axes.items():
                name = f"ROTATE_{axis}"
                commands.append(
                    GizmoDrawCommand(
                        kind="polyline",
                        points=tuple(self._world_ring_points(center, arm_world, u, v, steps=72, normalize=True)),
                        colour=rgba255_to_float(self._color(gizmo, name, axis)),
                        thickness=3.0 if name in (gizmo.hovered_handle, gizmo.active_handle) else 2.0,
                        pick_id=name,
                    )
                )
            commands.extend(self._pivot_marker(center, arm_world * 0.05, "ROTATE_CENTER"))
        return GizmoRenderData(
            origin=tuple(float(v) for v in center),
            orientation=getattr(gizmo, "orientation", None),
            scale=float(arm_world),
            active_tool=gizmo.mode.value,
            active_axis=getattr(gizmo, "active_handle", None),
            hover_axis=getattr(gizmo, "hovered_handle", None),
            axis_mode=str(getattr(getattr(gizmo, "transform_space", None), "value", "world")),
            commands=tuple(commands),
            handle_count=len(self.handles),
        )

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
        center_name = "TRANSLATE_VIEW"
        center_col = self.HILITE if center_name in (gizmo.hovered_handle, gizmo.active_handle) else (235, 235, 235, 255)
        draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=center_col, outline=(30, 32, 36, 255), width=2)
        self.handles.append({"name": center_name, "kind": "point", "pos": (cx, cy), "radius": 14, "priority": 10})

    @staticmethod
    def _scaled_axis(axis, length: float):
        ax, ay, az = float(axis[0]), float(axis[1]), float(axis[2])
        mag = max(1.0e-9, math.sqrt(ax * ax + ay * ay + az * az))
        return (ax / mag * length, ay / mag * length, az / mag * length)

    @staticmethod
    def _line_command(center, delta, color, pick_id: str) -> GizmoDrawCommand:
        return GizmoDrawCommand(
            kind="line",
            points=(
                (float(center[0]), float(center[1]), float(center[2])),
                (float(center[0] + delta[0]), float(center[1] + delta[1]), float(center[2] + delta[2])),
            ),
            colour=rgba255_to_float(color),
            thickness=3.0,
            pick_id=pick_id,
        )

    def _pivot_marker(self, center, radius: float, pick_id: str) -> list[GizmoDrawCommand]:
        cx, cy, cz = float(center[0]), float(center[1]), float(center[2])
        r = float(radius)
        color = rgba255_to_float((235, 235, 235, 255))
        return [
            GizmoDrawCommand(kind="line", points=((cx - r, cy, cz), (cx + r, cy, cz)), colour=color, pick_id=pick_id),
            GizmoDrawCommand(kind="line", points=((cx, cy - r, cz), (cx, cy + r, cz)), colour=color, pick_id=pick_id),
            GizmoDrawCommand(kind="line", points=((cx, cy, cz - r), (cx, cy, cz + r)), colour=color, pick_id=pick_id),
        ]

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

    def _draw_rotate(self, draw, gizmo, camera, projector, width, height, center_screen, center_world, radius_world, axes) -> None:
        cx, cy, center_depth = center_screen
        radius_px = 82
        draw.ellipse(
            [cx - radius_px, cy - radius_px, cx + radius_px, cy + radius_px],
            outline=(160, 166, 176, 95),
            width=1,
        )

        ring_points = {
            "X": self._world_ring_points(center_world, radius_world, axes["Y"], axes["Z"], normalize=True),
            "Y": self._world_ring_points(center_world, radius_world, axes["X"], axes["Z"], normalize=True),
            "Z": self._world_ring_points(center_world, radius_world, axes["X"], axes["Y"], normalize=True),
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
    def _world_ring_points(center, radius, u, v, steps: int = 144, normalize: bool = False):
        cx, cy, cz = float(center[0]), float(center[1]), float(center[2])
        ux, uy, uz = float(u[0]), float(u[1]), float(u[2])
        vx, vy, vz = float(v[0]), float(v[1]), float(v[2])
        if normalize:
            ul = max(1e-9, math.sqrt(ux * ux + uy * uy + uz * uz))
            vl = max(1e-9, math.sqrt(vx * vx + vy * vy + vz * vz))
            ux, uy, uz = ux / ul, uy / ul, uz / ul
            vx, vy, vz = vx / vl, vy / vl, vz / vl
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
