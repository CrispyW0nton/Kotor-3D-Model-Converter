"""ViewportOverlayLayers methods for the Qt viewport widget."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportOverlayLayersMixin:
    def _map_studio_clean_viewport_enabled(self) -> bool:
        presentation = getattr(self, "_map_studio_viewport_presentation", None)
        if isinstance(presentation, dict) and "clean_display" in presentation:
            return bool(presentation.get("clean_display"))
        return bool(self.property("_gr_map_studio_clean_viewport"))

    def _map_studio_presentation_flag(self, key: str, default: bool = False) -> bool:
        presentation = getattr(self, "_map_studio_viewport_presentation", None)
        if isinstance(presentation, dict) and key in presentation:
            return bool(presentation.get(key))
        return bool(default)

    @staticmethod
    def _map_studio_distance_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
        dx = bx - ax
        dy = by - ay
        denom = dx * dx + dy * dy
        if denom <= 1.0e-9:
            return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
        cx = ax + dx * t
        cy = ay + dy * t
        return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5

    def _map_studio_marker_rgba(self, color: object, alpha: int = 220) -> tuple[int, int, int, int]:
        text = str(color or "").strip()
        if text.startswith("#") and len(text) == 7:
            try:
                return (
                    int(text[1:3], 16),
                    int(text[3:5], 16),
                    int(text[5:7], 16),
                    max(0, min(255, int(alpha))),
                )
            except ValueError:
                pass
        return (82, 255, 122, max(0, min(255, int(alpha))))

    def _map_studio_theme_rgba(
        self,
        token: str,
        fallback: object,
        alpha: int = 220,
    ) -> tuple[int, int, int, int]:
        """Resolve an overlay color through the active Ghost theme."""

        value = fallback
        theme = getattr(self, "_current_theme", None)
        if theme is not None:
            try:
                value = theme.color(str(token or ""), str(fallback or ""))
            except Exception:
                value = fallback
        elif str(token or "") in {"info", "accent.primary", "accent.secondary"}:
            try:
                value = self.palette().color(QtGui.QPalette.ColorRole.Highlight).name()
            except Exception:
                value = fallback
        return self._map_studio_marker_rgba(value, alpha)

    def _map_studio_project_point(self, point: object, w: int, h: int):
        try:
            x, y, z = point
            return self._renderer._proj(float(x), float(y), float(z), w, h)
        except Exception:
            return None

    def _add_map_studio_marker_hit_zone(self, placement_id: object, kind: str, **zone: object) -> None:
        placement = str(placement_id or "")
        if not placement:
            return
        zones = getattr(self, "_map_studio_marker_hit_zones", None)
        if zones is None:
            zones = []
            self._map_studio_marker_hit_zones = zones
        zone["placement_id"] = placement
        zone["kind"] = kind
        zones.append(zone)

    def _add_map_studio_room_outline_hit_zone(self, room_resref: object, point_index: int, **zone: object) -> None:
        room = str(room_resref or "")
        if not room:
            return
        zones = getattr(self, "_map_studio_room_outline_hit_zones", None)
        if zones is None:
            zones = []
            self._map_studio_room_outline_hit_zones = zones
        zone["room_resref"] = room
        zone["point_index"] = int(point_index)
        zones.append(zone)

    def _add_map_studio_room_outline_edge_hit_zone(self, room_resref: object, edge_index: int, **zone: object) -> None:
        room = str(room_resref or "")
        if not room:
            return
        zones = getattr(self, "_map_studio_room_outline_edge_hit_zones", None)
        if zones is None:
            zones = []
            self._map_studio_room_outline_edge_hit_zones = zones
        zone["room_resref"] = room
        zone["edge_index"] = int(edge_index)
        zones.append(zone)

    def _add_map_studio_room_primitive_hit_zone(self, room_resref: object, primitive_name: object, **zone: object) -> None:
        room = str(room_resref or "")
        primitive = str(primitive_name or "")
        if not room or not primitive:
            return
        zones = getattr(self, "_map_studio_room_primitive_hit_zones", None)
        if zones is None:
            zones = []
            self._map_studio_room_primitive_hit_zones = zones
        zone["room_resref"] = room
        zone["primitive_name"] = primitive
        zones.append(zone)

    def map_studio_room_primitive_at_screen(self, x: float, y: float) -> tuple[str, str, tuple[float, float, float]] | tuple[()]:
        """Return the authored room primitive handle under a viewport screen point."""

        px = float(x)
        py = float(y)
        for zone in reversed(tuple(getattr(self, "_map_studio_room_primitive_hit_zones", ()) or ())):
            kind = str(zone.get("kind", "") or "")
            hit = False
            if kind == "rect":
                min_x, min_y, max_x, max_y = zone.get("bounds", (0.0, 0.0, -1.0, -1.0))
                hit = float(min_x) <= px <= float(max_x) and float(min_y) <= py <= float(max_y)
            elif kind == "circle":
                cx, cy = zone.get("center", (0.0, 0.0))
                radius = float(zone.get("radius", 0.0) or 0.0)
                hit = ((px - float(cx)) ** 2 + (py - float(cy)) ** 2) <= radius * radius
            if not hit:
                continue
            center = tuple(zone.get("world_center", (0.0, 0.0, 0.0)))
            if len(center) < 3:
                center = (0.0, 0.0, 0.0)
            return (
                str(zone.get("room_resref", "") or ""),
                str(zone.get("primitive_name", "") or ""),
                (float(center[0]), float(center[1]), float(center[2])),
            )
        return ()

    def map_studio_room_outline_point_at_screen(self, x: float, y: float) -> tuple[str, int, tuple[float, float, float]] | tuple[()]:
        """Return the authored room outline point under a viewport screen point."""

        px = float(x)
        py = float(y)
        for zone in reversed(tuple(getattr(self, "_map_studio_room_outline_hit_zones", ()) or ())):
            cx, cy = zone.get("center", (0.0, 0.0))
            radius = float(zone.get("radius", 0.0) or 0.0)
            if ((px - float(cx)) ** 2 + (py - float(cy)) ** 2) <= radius * radius:
                point = tuple(zone.get("world_point", (0.0, 0.0, 0.0)))
                if len(point) < 3:
                    point = (0.0, 0.0, 0.0)
                return (
                    str(zone.get("room_resref", "") or ""),
                    int(zone.get("point_index", -1)),
                    (float(point[0]), float(point[1]), float(point[2])),
                )
        return ()

    def map_studio_room_outline_edge_at_screen(
        self,
        x: float,
        y: float,
    ) -> tuple[str, int, tuple[float, float, float], tuple[float, float, float]] | tuple[()]:
        """Return the authored room outline edge under a viewport screen point."""

        px = float(x)
        py = float(y)
        for zone in reversed(tuple(getattr(self, "_map_studio_room_outline_edge_hit_zones", ()) or ())):
            ax, ay = zone.get("start", (0.0, 0.0))
            bx, by = zone.get("end", (0.0, 0.0))
            tolerance = float(zone.get("tolerance", 0.0) or 0.0)
            if self._map_studio_distance_to_segment(px, py, float(ax), float(ay), float(bx), float(by)) > tolerance:
                continue
            world_start = tuple(zone.get("world_start", (0.0, 0.0, 0.0)))
            world_end = tuple(zone.get("world_end", (0.0, 0.0, 0.0)))
            if len(world_start) < 3:
                world_start = (0.0, 0.0, 0.0)
            if len(world_end) < 3:
                world_end = (0.0, 0.0, 0.0)
            return (
                str(zone.get("room_resref", "") or ""),
                int(zone.get("edge_index", -1)),
                (float(world_start[0]), float(world_start[1]), float(world_start[2])),
                (float(world_end[0]), float(world_end[1]), float(world_end[2])),
            )
        return ()

    def map_studio_marker_at_screen(self, x: float, y: float) -> str:
        """Return the authored placement id under a viewport screen point."""

        px = float(x)
        py = float(y)
        for zone in reversed(tuple(getattr(self, "_map_studio_marker_hit_zones", ()) or ())):
            kind = str(zone.get("kind", "") or "")
            if kind == "rect":
                min_x, min_y, max_x, max_y = zone.get("bounds", (0.0, 0.0, -1.0, -1.0))
                if float(min_x) <= px <= float(max_x) and float(min_y) <= py <= float(max_y):
                    return str(zone.get("placement_id", "") or "")
            elif kind == "circle":
                cx, cy = zone.get("center", (0.0, 0.0))
                radius = float(zone.get("radius", 0.0) or 0.0)
                if ((px - float(cx)) ** 2 + (py - float(cy)) ** 2) <= radius * radius:
                    return str(zone.get("placement_id", "") or "")
            elif kind == "line":
                ax, ay = zone.get("start", (0.0, 0.0))
                bx, by = zone.get("end", (0.0, 0.0))
                tolerance = float(zone.get("tolerance", 0.0) or 0.0)
                if self._map_studio_distance_to_segment(px, py, float(ax), float(ay), float(bx), float(by)) <= tolerance:
                    return str(zone.get("placement_id", "") or "")
        return ""

    def _draw_map_studio_speaker_billboard(self, draw, icon: object, w: int, h: int) -> None:
        """Draw one selectable, screen-facing sound marker without fake geometry."""

        projected = self._map_studio_project_point(getattr(icon, "position", ()), w, h)
        if projected is None:
            return
        cx, cy = float(projected[0]), float(projected[1])
        color = self._map_studio_theme_rgba(
            str(getattr(icon, "color_role", "") or "info"),
            getattr(icon, "color", "#4080ff"),
            245,
        )
        text_color = self._map_studio_theme_rgba("viewport.text", "#ffffff", 245)
        background = self._map_studio_theme_rgba("viewport.background", "#20242a", 220)
        placement_id = str(getattr(icon, "placement_id", "") or "")
        label = str(getattr(icon, "label", "") or placement_id or "Sound")
        radius = 15.0
        self._add_map_studio_marker_hit_zone(
            placement_id,
            "circle",
            center=(cx, cy),
            radius=radius + 5.0,
        )
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=(background[0], background[1], background[2], 205),
            outline=(0, 0, 0, 220),
            width=3,
        )
        draw.ellipse(
            [cx - radius + 2.0, cy - radius + 2.0, cx + radius - 2.0, cy + radius - 2.0],
            outline=color,
            width=2,
        )
        # Speaker body/cone plus two radiating audio arcs.  Keeping this in
        # screen space makes it legible at any camera distance, like Unreal's
        # audio actor billboard.
        draw.rectangle([cx - 9.0, cy - 4.0, cx - 5.0, cy + 4.0], fill=color)
        draw.polygon(
            [
                (cx - 5.0, cy - 5.0),
                (cx + 1.0, cy - 10.0),
                (cx + 1.0, cy + 10.0),
                (cx - 5.0, cy + 5.0),
            ],
            fill=color,
        )
        draw.arc([cx - 2.0, cy - 8.0, cx + 10.0, cy + 8.0], start=-55, end=55, fill=color, width=2)
        draw.arc([cx - 3.0, cy - 12.0, cx + 16.0, cy + 12.0], start=-50, end=50, fill=color, width=2)
        text_position = (cx + radius + 6.0, cy - 7.0)
        try:
            bounds = draw.textbbox(text_position, label)
            self._add_map_studio_marker_hit_zone(
                placement_id,
                "rect",
                bounds=(float(bounds[0]) - 4.0, float(bounds[1]) - 3.0, float(bounds[2]) + 4.0, float(bounds[3]) + 3.0),
            )
            draw.rectangle(
                [bounds[0] - 4.0, bounds[1] - 3.0, bounds[2] + 4.0, bounds[3] + 3.0],
                fill=(background[0], background[1], background[2], 195),
                outline=(color[0], color[1], color[2], 190),
                width=1,
            )
        except Exception:
            pass
        draw.text(text_position, label, fill=text_color)

    def _draw_map_studio_placement_markers(self, draw, w: int, h: int) -> None:
        self._map_studio_marker_hit_zones = []
        geometry = getattr(self, "_map_studio_marker_geometry", None)
        if geometry is None:
            return
        clean_display = self._map_studio_clean_viewport_enabled()
        placement_guides_active = self._map_studio_presentation_flag("show_placement_guides", not clean_display)
        footprints = tuple(getattr(geometry, "footprints", ()) or ())
        lines = tuple(getattr(geometry, "lines", ()) or ())
        icons = tuple(getattr(geometry, "icons", ()) or ())
        if not footprints and not lines and not icons:
            return
        try:
            for footprint in footprints:
                points = tuple(getattr(footprint, "points", ()) or ())
                projected = []
                for point in points:
                    proj = self._map_studio_project_point(point, w, h)
                    if proj is None:
                        projected = []
                        break
                    projected.append((proj[0], proj[1]))
                if len(projected) >= 3:
                    color = self._map_studio_marker_rgba(
                        getattr(footprint, "color", ""),
                        120 if clean_display and not placement_guides_active else 220,
                    )
                    fill = (color[0], color[1], color[2], 14 if clean_display and not placement_guides_active else 34)
                    outline = (color[0], color[1], color[2], 110 if clean_display and not placement_guides_active else 205)
                    closed = projected + [projected[0]]
                    xs = [float(p[0]) for p in projected]
                    ys = [float(p[1]) for p in projected]
                    self._add_map_studio_marker_hit_zone(
                        getattr(footprint, "placement_id", ""),
                        "rect",
                        bounds=(min(xs) - 8.0, min(ys) - 8.0, max(xs) + 8.0, max(ys) + 8.0),
                    )
                    draw.polygon(projected, fill=fill)
                    draw.line(closed, fill=(0, 0, 0, 70 if clean_display and not placement_guides_active else 125), width=3 if clean_display and not placement_guides_active else 4)
                    draw.line(closed, fill=outline, width=1 if clean_display and not placement_guides_active else 2)
            for guide in lines:
                start = self._map_studio_project_point(getattr(guide, "start", ()), w, h)
                end = self._map_studio_project_point(getattr(guide, "end", ()), w, h)
                if start is None or end is None:
                    continue
                color = self._map_studio_marker_rgba(
                    getattr(guide, "color", ""),
                    120 if clean_display and not placement_guides_active else 235,
                )
                role = str(getattr(guide, "role", "") or "")
                width = 1 if clean_display and not placement_guides_active else 3 if role == "facing" else 2
                sx, sy = float(start[0]), float(start[1])
                ex, ey = float(end[0]), float(end[1])
                self._add_map_studio_marker_hit_zone(
                    getattr(guide, "placement_id", ""),
                    "line",
                    start=(sx, sy),
                    end=(ex, ey),
                    tolerance=8.0 if role == "facing" else 6.0,
                )
                if role == "height":
                    segments = 6
                    for index in range(segments):
                        if index % 2:
                            continue
                        t0 = index / segments
                        t1 = (index + 1) / segments
                        p0 = (sx + (ex - sx) * t0, sy + (ey - sy) * t0)
                        p1 = (sx + (ex - sx) * t1, sy + (ey - sy) * t1)
                        draw.line([p0, p1], fill=(0, 0, 0, 70 if clean_display and not placement_guides_active else 145), width=width + 2)
                        draw.line([p0, p1], fill=color, width=width)
                else:
                    draw.line([(sx, sy), (ex, ey)], fill=(0, 0, 0, 70 if clean_display and not placement_guides_active else 145), width=width + 2)
                    draw.line([(sx, sy), (ex, ey)], fill=color, width=width)
                if role == "sky_traffic_path":
                    # A sampled spline can contain dozens of segments; node
                    # dots on every sample obscure the actual flight path.
                    continue
                if role == "sky_traffic_direction":
                    dx, dy = ex - sx, ey - sy
                    length = max(1.0, (dx * dx + dy * dy) ** 0.5)
                    ux, uy = dx / length, dy / length
                    arrow_size = 9.0 if clean_display else 12.0
                    wing = arrow_size * 0.45
                    base_x, base_y = ex - (ux * arrow_size), ey - (uy * arrow_size)
                    left = (base_x - (uy * wing), base_y + (ux * wing))
                    right = (base_x + (uy * wing), base_y - (ux * wing))
                    draw.polygon([(ex, ey), left, right], fill=color)
                radius = 3 if clean_display and not placement_guides_active else 4
                self._add_map_studio_marker_hit_zone(
                    getattr(guide, "placement_id", ""),
                    "circle",
                    center=(sx, sy),
                    radius=9.0,
                )
                draw.ellipse(
                    [sx - radius, sy - radius, sx + radius, sy + radius],
                    fill=color,
                    outline=(0, 0, 0, 180),
                    width=1,
                )
                if role == "facing":
                    radius = 3
                    self._add_map_studio_marker_hit_zone(
                        getattr(guide, "placement_id", ""),
                        "circle",
                        center=(ex, ey),
                        radius=8.0,
                    )
                    draw.ellipse(
                        [ex - radius, ey - radius, ex + radius, ey + radius],
                        fill=color,
                        outline=(0, 0, 0, 180),
                        width=1,
                    )
            for icon in icons:
                if str(getattr(icon, "icon", "") or "").strip().lower() == "speaker":
                    self._draw_map_studio_speaker_billboard(draw, icon, w, h)
        except Exception as exc:
            log.debug("Map Studio placement marker overlay failed: %s", exc)

    def _draw_map_studio_room_outlines(self, draw, w: int, h: int) -> None:
        self._map_studio_room_outline_hit_zones = []
        self._map_studio_room_outline_edge_hit_zones = []
        self._map_studio_room_primitive_hit_zones = []
        geometry = getattr(self, "_map_studio_room_outline_geometry", None)
        if geometry is None:
            return
        clean_display = self._map_studio_clean_viewport_enabled()
        show_room_guides = self._map_studio_presentation_flag("show_room_guides", not clean_display)
        show_room_vertices = self._map_studio_presentation_flag("show_room_vertex_handles", not clean_display)
        show_primitive_handles = self._map_studio_presentation_flag("show_primitive_handles", True)
        subtle_outlines = self._map_studio_presentation_flag("subtle_room_outlines", clean_display)
        preview_model_loaded = self._map_studio_presentation_flag("preview_model_loaded", False)
        show_render_geometry_overlay = self._map_studio_presentation_flag(
            "show_render_geometry_overlay",
            not preview_model_loaded,
        )
        show_room_mesh_fill_overlay = self._map_studio_presentation_flag(
            "show_room_mesh_fill_overlay",
            not preview_model_loaded,
        )
        polygons = tuple(getattr(geometry, "polygons", ()) or ())
        lines = tuple(getattr(geometry, "lines", ()) or ())
        primitive_handles = tuple(getattr(geometry, "primitive_handles", ()) or ())
        if not polygons and not lines and not primitive_handles:
            return
        try:
            for polygon in polygons:
                points = tuple(getattr(polygon, "points", ()) or ())
                projected = []
                for point in points:
                    proj = self._map_studio_project_point(point, w, h)
                    if proj is None:
                        projected = []
                        break
                    projected.append((proj[0], proj[1]))
                if len(projected) < 3:
                    continue
                role = str(getattr(polygon, "role", "") or "")
                color = self._map_studio_marker_rgba(getattr(polygon, "color", ""), 145 if preview_model_loaded else 170 if subtle_outlines else 230)
                closed = projected + [projected[0]]
                if role == "floor":
                    room_resref = getattr(polygon, "room_resref", "")
                    for edge_index, (start_point, end_point, screen_start, screen_end) in enumerate(
                        zip(points, points[1:] + points[:1], projected, projected[1:] + projected[:1])
                    ):
                        self._add_map_studio_room_outline_edge_hit_zone(
                            room_resref,
                            edge_index,
                            start=(float(screen_start[0]), float(screen_start[1])),
                            end=(float(screen_end[0]), float(screen_end[1])),
                            tolerance=8.0,
                            world_start=start_point,
                            world_end=end_point,
                        )
                    for index, (point, projected_point) in enumerate(zip(points, projected)):
                        sx, sy = float(projected_point[0]), float(projected_point[1])
                        self._add_map_studio_room_outline_hit_zone(
                            room_resref,
                            index,
                            center=(sx, sy),
                            radius=10.0,
                            world_point=point,
                        )
                        if show_room_vertices:
                            radius = 4
                            draw.ellipse(
                                [sx - radius, sy - radius, sx + radius, sy + radius],
                                fill=(color[0], color[1], color[2], 235),
                                outline=(0, 0, 0, 190),
                                width=1,
                            )
                if not show_render_geometry_overlay:
                    continue
                fill_alpha = (
                    62 if show_room_mesh_fill_overlay and subtle_outlines and role == "floor"
                    else 34 if show_room_mesh_fill_overlay and subtle_outlines
                    else 24 if show_room_mesh_fill_overlay and role == "floor"
                    else 8 if show_room_mesh_fill_overlay
                    else 0
                )
                if fill_alpha > 0:
                    draw.polygon(projected, fill=(color[0], color[1], color[2], fill_alpha))
                width = 1 if preview_model_loaded else 2 if subtle_outlines and role == "floor" else 1 if subtle_outlines else 3 if role == "floor" else 2
                dash = role == "ceiling"
                if dash:
                    for start, end in zip(closed, closed[1:]):
                        self._draw_map_studio_dashed_line(draw, start, end, color=color, width=width)
                else:
                    shadow_alpha = 60 if preview_model_loaded else 95 if subtle_outlines else 150
                    draw.line(closed, fill=(0, 0, 0, shadow_alpha), width=width + 2)
                    draw.line(closed, fill=color, width=width)
            if not show_room_guides:
                lines = ()
            if not show_render_geometry_overlay:
                lines = ()
            for guide in lines:
                start = self._map_studio_project_point(getattr(guide, "start", ()), w, h)
                end = self._map_studio_project_point(getattr(guide, "end", ()), w, h)
                if start is None or end is None:
                    continue
                color = self._map_studio_marker_rgba(getattr(guide, "color", ""), 220)
                role = str(getattr(guide, "role", "") or "")
                width = 3 if role == "opening" else 2
                if role == "wall_height":
                    self._draw_map_studio_dashed_line(draw, (start[0], start[1]), (end[0], end[1]), color=color, width=width)
                else:
                    draw.line([(start[0], start[1]), (end[0], end[1])], fill=(0, 0, 0, 150), width=width + 2)
                    draw.line([(start[0], start[1]), (end[0], end[1])], fill=color, width=width)
            self._draw_map_studio_room_outline_edge_highlight(draw, w, h)
            if show_render_geometry_overlay and show_primitive_handles:
                self._draw_map_studio_room_primitive_handles(draw, primitive_handles, w, h)
            self._draw_map_studio_room_outline_snap_highlight(draw, w, h)
        except Exception as exc:
            log.debug("Map Studio room outline overlay failed: %s", exc)

    def _draw_map_studio_terrain_walkability(self, draw, w: int, h: int) -> None:
        overlay = getattr(self, "_map_studio_terrain_walkability_overlay", None)
        if overlay is None:
            return
        if self._map_studio_clean_viewport_enabled() and not self._map_studio_presentation_flag("show_terrain_walkability", False):
            return
        triangles = tuple(getattr(overlay, "triangles", ()) or ())
        if not triangles:
            return
        try:
            for triangle in triangles:
                points = tuple(getattr(triangle, "points", ()) or ())
                projected = []
                for point in points:
                    proj = self._map_studio_project_point(point, w, h)
                    if proj is None:
                        projected = []
                        break
                    projected.append((float(proj[0]), float(proj[1])))
                if len(projected) < 3:
                    continue
                walkable = bool(getattr(triangle, "walkable", False))
                state = str(getattr(triangle, "validation_state", "unknown") or "unknown").strip().lower()
                color_role = str(getattr(triangle, "color_role", "") or "")
                if not color_role:
                    color_role = "success" if state == "valid" else "error" if state == "invalid" else "warning"
                fallback = getattr(
                    triangle,
                    "color",
                    "#1b8f45" if state == "valid" else "#c93434" if state == "invalid" else "#d8a326",
                )
                color = self._map_studio_theme_rgba(color_role, fallback, 235)
                fill_alpha = 46 if state == "valid" else 78 if state == "invalid" else 58
                outline_alpha = 175 if state == "valid" else 235 if state == "invalid" else 210
                draw.polygon(projected, fill=(color[0], color[1], color[2], fill_alpha))
                closed = projected + [projected[0]]
                draw.line(closed, fill=(0, 0, 0, 135), width=3 if state == "invalid" else 2)
                draw.line(closed, fill=(color[0], color[1], color[2], outline_alpha), width=2 if state == "invalid" else 1)
                if state == "invalid":
                    draw.line(
                        [projected[0], projected[2]],
                        fill=(color[0], color[1], color[2], 235),
                        width=2,
                    )
                    draw.line(
                        [projected[1], ((projected[0][0] + projected[2][0]) * 0.5, (projected[0][1] + projected[2][1]) * 0.5)],
                        fill=(color[0], color[1], color[2], 235),
                        width=2,
                    )
                elif not walkable:
                    # Blocked faces can be intentional inside a valid WOK.
                    # Mark them subtly without misrepresenting the room as a
                    # failed red walkmesh.
                    draw.line([projected[0], projected[2]], fill=(0, 0, 0, 135), width=1)
        except Exception as exc:
            log.debug("Map Studio terrain walkability overlay failed: %s", exc)

    def _draw_map_studio_terrain_brush_cursor(self, draw, w: int, h: int) -> None:
        cursor = getattr(self, "_map_studio_terrain_brush_cursor", None)
        if not isinstance(cursor, dict):
            return
        if self._map_studio_clean_viewport_enabled() and not self._map_studio_presentation_flag("show_terrain_brush", False):
            return
        center = self._map_studio_project_point(cursor.get("world_position", ()), w, h)
        edge = self._map_studio_project_point(cursor.get("world_radius_position", ()), w, h)
        if center is None or edge is None:
            return
        try:
            cx, cy = float(center[0]), float(center[1])
            ex, ey = float(edge[0]), float(edge[1])
            radius = max(7.0, min(260.0, ((ex - cx) ** 2 + (ey - cy) ** 2) ** 0.5))
            color = self._map_studio_marker_rgba(cursor.get("color", "#00ff7a"), 235)
            bounds = (cx - radius, cy - radius, cx + radius, cy + radius)
            draw.ellipse(bounds, outline=(0, 0, 0, 190), width=4)
            draw.ellipse(bounds, outline=color, width=2)
            draw.line([(cx - radius, cy), (cx + radius, cy)], fill=(color[0], color[1], color[2], 175), width=1)
            draw.line([(cx, cy - radius), (cx, cy + radius)], fill=(color[0], color[1], color[2], 175), width=1)
            sample = cursor.get("sample", ())
            brush = str(cursor.get("brush", "") or "brush")
            room = str(cursor.get("room_resref", "") or "")
            label = f"{brush} {room} r{int(cursor.get('radius_samples', 0) or 0)}"
            if "hardness" in cursor:
                label = f"{label} h{float(cursor.get('hardness', 0.0) or 0.0):.2f}"
            if isinstance(sample, (tuple, list)) and len(sample) >= 2:
                label = f"{label} [{int(sample[0])},{int(sample[1])}]"
            text_pos = (cx + radius + 8.0, cy - 10.0)
            try:
                text_box = draw.textbbox(text_pos, label)
                draw.rectangle(
                    (text_box[0] - 4, text_box[1] - 2, text_box[2] + 4, text_box[3] + 2),
                    fill=(0, 0, 0, 155),
                    outline=(color[0], color[1], color[2], 165),
                )
            except Exception:
                pass
            draw.text(text_pos, label, fill=(color[0], color[1], color[2], 245))
        except Exception as exc:
            log.debug("Map Studio terrain brush cursor overlay failed: %s", exc)

    def _draw_map_studio_texture_paint_cursor(self, draw, w: int, h: int) -> None:
        """Draw texture-space size and hardness rings over the picked surface."""

        cursor = getattr(self, "_map_studio_texture_paint_cursor", None)
        if not isinstance(cursor, dict):
            return
        try:
            outer = list(tuple(cursor.get("outer") or ()))
            inner = list(tuple(cursor.get("inner") or ()))
            center = tuple(cursor.get("center") or ())
            if len(outer) < 3 or len(center) < 2:
                return
            valid = bool(cursor.get("valid", False))
            color = self._map_studio_theme_rgba(
                "success" if valid else "error",
                "#00e5ff" if valid else "#ff5c5c",
                245,
            )

            def closed(points):
                return points + [points[0]] if points else points

            draw.line(closed(outer), fill=(0, 0, 0, 210), width=5)
            draw.line(closed(outer), fill=color, width=2)
            if len(inner) >= 3:
                draw.line(closed(inner), fill=(0, 0, 0, 180), width=3)
                draw.line(closed(inner), fill=(color[0], color[1], color[2], 180), width=1)
            cx, cy = float(center[0]), float(center[1])
            draw.line([(cx - 4.0, cy), (cx + 4.0, cy)], fill=color, width=1)
            draw.line([(cx, cy - 4.0), (cx, cy + 4.0)], fill=color, width=1)
            if not valid:
                draw.line([(cx - 6.0, cy - 6.0), (cx + 6.0, cy + 6.0)], fill=color, width=2)
                draw.line([(cx - 6.0, cy + 6.0), (cx + 6.0, cy - 6.0)], fill=color, width=2)
        except Exception as exc:
            log.debug("Map Studio texture paint cursor overlay failed: %s", exc)

    def _draw_map_studio_component_selection(self, draw, w: int, h: int) -> None:
        """Selected components render YELLOW (selection owns that color now)."""

        selection = getattr(self, "_map_studio_component_selection", None)
        if not selection:
            return
        for entry in selection:
            try:
                component = str(entry.get("component_type", "") or "")
                world = tuple(entry.get("face_world_points", ()) or ())
                projected = []
                for point in world[:3]:
                    proj = self._map_studio_project_point(point, w, h)
                    if proj is None:
                        projected = []
                        break
                    projected.append((float(proj[0]), float(proj[1])))
                if component == "face" and len(projected) >= 3:
                    draw.polygon(projected, fill=(255, 214, 74, 88))
                    closed = projected + [projected[0]]
                    draw.line(closed, fill=(255, 214, 74, 255), width=2)
                elif component == "edge" and len(projected) >= 3:
                    edge = tuple(entry.get("edge_indices", (0, 1)) or (0, 1))
                    start = projected[int(edge[0]) % 3]
                    end = projected[int(edge[1]) % 3]
                    draw.line([start, end], fill=(255, 214, 74, 255), width=4)
                elif component == "vertex":
                    proj = self._map_studio_project_point(tuple(entry.get("world_point", ()) or ()), w, h)
                    if proj is not None:
                        cx, cy = float(proj[0]), float(proj[1])
                        draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), outline=(255, 214, 74, 255), width=3)
            except Exception:
                continue

    def _draw_map_studio_component_extrude_gizmo(self, draw, w: int, h: int) -> None:
        """Maya-style extrude gizmo: axis arrow at the armed face/edge anchor."""

        payload = getattr(self, "_map_studio_component_extrude", None)
        if not isinstance(payload, dict):
            return
        try:
            anchor = tuple(payload.get("anchor", ()) or ())
            axis = tuple(payload.get("axis", ()) or ())
            if len(anchor) < 3 or len(axis) < 3:
                return
            distance = float(payload.get("distance", 0.0) or 0.0)
            arrow_len = max(1.0, abs(distance))
            tip_world = (
                anchor[0] + axis[0] * arrow_len,
                anchor[1] + axis[1] * arrow_len,
                anchor[2] + axis[2] * arrow_len,
            )
            base = self._map_studio_project_point(anchor, w, h)
            tip = self._map_studio_project_point(tip_world, w, h)
            if base is None or tip is None:
                return
            bx, by = float(base[0]), float(base[1])
            tx, ty = float(tip[0]), float(tip[1])
            operator = str(payload.get("operator", "extrude") or "extrude")
            color = (
                (77, 184, 255) if operator == "bevel" else (86, 214, 122)
            ) if bool(payload.get("dragging", False)) else (255, 214, 74)
            draw.line([(bx, by), (tx, ty)], fill=(0, 0, 0, 170), width=6)
            draw.line([(bx, by), (tx, ty)], fill=(color[0], color[1], color[2], 255), width=3)
            # Arrowhead: two short strokes back from the tip.
            vx, vy = tx - bx, ty - by
            length = max(1.0e-6, (vx * vx + vy * vy) ** 0.5)
            ux, uy = vx / length, vy / length
            px, py = -uy, ux
            for side in (1.0, -1.0):
                draw.line(
                    [(tx, ty), (tx - ux * 12.0 + px * 6.0 * side, ty - uy * 12.0 + py * 6.0 * side)],
                    fill=(color[0], color[1], color[2], 255),
                    width=3,
                )
            draw.ellipse((bx - 4, by - 4, bx + 4, by + 4), outline=(color[0], color[1], color[2], 255), width=2)
            if operator == "bevel":
                label = (
                    f"bevel {distance:.3f}m | {int(payload.get('segments', 1) or 1)} seg | "
                    f"profile {float(payload.get('profile', 0.5) or 0.0):.2f}"
                )
            else:
                label = f"{distance:+.2f}m" if abs(distance) > 1.0e-6 else "drag to extrude"
            draw.text((tx + 8, ty - 8), label, fill=(color[0], color[1], color[2], 245))
            # Maya-style axis-orientation badge: click toggles normal <-> world.
            if operator == "bevel":
                return
            offset = tuple(payload.get("toggle_offset", (26.0, -26.0)) or (26.0, -26.0))
            world_mode = str(payload.get("axis_mode", "normal")) == "world"
            badge_x, badge_y = bx + float(offset[0]), by + float(offset[1])
            badge_color = (77, 184, 255) if world_mode else (255, 214, 74)
            draw.ellipse(
                (badge_x - 9, badge_y - 9, badge_x + 9, badge_y + 9),
                fill=(20, 20, 20, 200),
                outline=(badge_color[0], badge_color[1], badge_color[2], 255),
                width=2,
            )
            draw.text(
                (badge_x - 4, badge_y - 7),
                "W" if world_mode else "N",
                fill=(badge_color[0], badge_color[1], badge_color[2], 255),
            )
        except Exception as exc:
            log.debug("Map Studio extrude gizmo overlay failed: %s", exc)

    @staticmethod
    def _map_studio_draw_dashed_line(
        draw,
        start: tuple[float, float],
        end: tuple[float, float],
        *,
        fill: tuple[int, int, int, int],
        width: int,
        dash: float = 7.0,
        gap: float = 5.0,
    ) -> None:
        """Draw one screen-space dashed segment without renderer mutation."""

        ax, ay = float(start[0]), float(start[1])
        bx, by = float(end[0]), float(end[1])
        dx, dy = bx - ax, by - ay
        length = (dx * dx + dy * dy) ** 0.5
        if length <= 1.0e-6:
            return
        ux, uy = dx / length, dy / length
        cursor = 0.0
        stride = max(1.0, float(dash)) + max(0.0, float(gap))
        while cursor < length:
            stop = min(length, cursor + max(1.0, float(dash)))
            draw.line(
                [
                    (ax + ux * cursor, ay + uy * cursor),
                    (ax + ux * stop, ay + uy * stop),
                ],
                fill=fill,
                width=max(1, int(width)),
            )
            cursor += stride

    def _draw_map_studio_modeling_points_overlay(self, draw, w: int, h: int) -> None:
        """Paint Maya-style Quad Draw anchors and the prospective closing edge.

        The payload contains world-space feedback only.  Drawing it here keeps
        the first three clicks visible without touching the KMAP or the live
        imported mesh before the fourth click commits the quad.
        """

        overlay = getattr(self, "_map_studio_modeling_points_overlay", None)
        if not isinstance(overlay, dict) or str(overlay.get("tool") or "") != "quad_draw":
            return
        try:
            points = tuple(overlay.get("points") or ())[:3]
            projected: list[tuple[float, float]] = []
            for point in points:
                screen = self._map_studio_project_point(point, w, h)
                if screen is None:
                    continue
                projected.append((float(screen[0]), float(screen[1])))
            if not projected:
                return

            anchor_color = self._map_studio_theme_rgba("accent.secondary", "#00e5ff", 255)
            preview_color = self._map_studio_theme_rgba("accent.primary", "#ff9f43", 235)
            if len(projected) >= 2:
                draw.line(projected, fill=(0, 0, 0, 205), width=7)
                draw.line(projected, fill=anchor_color, width=3)

            preview_point = tuple(overlay.get("preview_point") or ())
            preview_screen = self._map_studio_project_point(preview_point, w, h) if len(preview_point) >= 3 else None
            if preview_screen is not None:
                candidate = (float(preview_screen[0]), float(preview_screen[1]))
                self._map_studio_draw_dashed_line(
                    draw,
                    projected[-1],
                    candidate,
                    fill=(0, 0, 0, 195),
                    width=6,
                    dash=7.0,
                    gap=5.0,
                )
                self._map_studio_draw_dashed_line(
                    draw,
                    projected[-1],
                    candidate,
                    fill=preview_color,
                    width=3,
                    dash=7.0,
                    gap=5.0,
                )
                if len(projected) == 3 and bool(overlay.get("close_preview", False)):
                    self._map_studio_draw_dashed_line(
                        draw,
                        candidate,
                        projected[0],
                        fill=(0, 0, 0, 195),
                        width=6,
                        dash=7.0,
                        gap=5.0,
                    )
                    self._map_studio_draw_dashed_line(
                        draw,
                        candidate,
                        projected[0],
                        fill=preview_color,
                        width=3,
                        dash=7.0,
                        gap=5.0,
                    )
                cx, cy = candidate
                draw.ellipse((cx - 5.0, cy - 5.0, cx + 5.0, cy + 5.0), fill=(0, 0, 0, 205))
                draw.ellipse(
                    (cx - 3.5, cy - 3.5, cx + 3.5, cy + 3.5),
                    outline=preview_color,
                    width=2,
                )

            for index, (cx, cy) in enumerate(projected, start=1):
                draw.ellipse((cx - 7.0, cy - 7.0, cx + 7.0, cy + 7.0), fill=(0, 0, 0, 220))
                draw.ellipse(
                    (cx - 4.5, cy - 4.5, cx + 4.5, cy + 4.5),
                    fill=anchor_color,
                    outline=(255, 255, 255, 235),
                    width=1,
                )
                draw.text((cx + 8.0, cy - 11.0), str(index), fill=anchor_color)
        except Exception as exc:
            log.debug("Map Studio modeling point overlay failed: %s", exc)

    def _draw_map_studio_hover_highlight(self, draw, w: int, h: int) -> None:
        payload = getattr(self, "_map_studio_hover_highlight", None)
        if not isinstance(payload, dict):
            return
        if self._map_studio_clean_viewport_enabled() and not self._map_studio_presentation_flag("show_hover_highlight", True):
            return
        try:
            component = str(payload.get("component_type", "") or "")
            placement_drop = bool(payload.get("placement_drop", False))
            world_points = tuple(payload.get("world_points", ()) or ())
            projected = []
            for point in world_points[:3]:
                proj = self._map_studio_project_point(point, w, h)
                if proj is None:
                    projected = []
                    break
                projected.append((float(proj[0]), float(proj[1])))
            if placement_drop:
                # Reuse the established walkable-green cue so a drag has one
                # unambiguous valid landing color across every theme.
                color = (0, 255, 122)
            elif component == "walkmesh_face":
                color = (0, 255, 122) if bool(payload.get("walkable", False)) else (255, 95, 95)
            else:
                # Orange is reserved for the live component/edge-selector cue;
                # yellow remains reserved for committed component selection.
                color = (255, 128, 16)
            if component in {"face", "walkmesh_face"} and len(projected) >= 3:
                draw.polygon(projected, fill=(color[0], color[1], color[2], 34))
                closed = projected + [projected[0]]
                draw.line(closed, fill=(0, 0, 0, 140), width=4)
                draw.line(closed, fill=(color[0], color[1], color[2], 215), width=2)
            elif component == "edge" and len(projected) >= 3:
                edge = tuple(payload.get("edge_indices", (0, 1)) or (0, 1))
                start = projected[int(edge[0]) % 3]
                end = projected[int(edge[1]) % 3]
                draw.line([start, end], fill=(0, 0, 0, 190), width=7)
                draw.line([start, end], fill=(255, 128, 16, 255), width=4)
            elif component == "vertex":
                proj = self._map_studio_project_point(tuple(payload.get("world_point", ()) or ()), w, h)
                if proj is None:
                    return
                cx, cy = float(proj[0]), float(proj[1])
                bounds = (cx - 5.0, cy - 5.0, cx + 5.0, cy + 5.0)
                draw.ellipse(bounds, outline=(0, 0, 0, 200), width=4)
                draw.ellipse(bounds, outline=(255, 128, 16, 255), width=3)

            if placement_drop:
                proj = self._map_studio_project_point(tuple(payload.get("world_point", ()) or ()), w, h)
                if proj is not None:
                    cx, cy = float(proj[0]), float(proj[1])
                    draw.ellipse((cx - 12.0, cy - 12.0, cx + 12.0, cy + 12.0), fill=(0, 0, 0, 150))
                    draw.ellipse(
                        (cx - 9.0, cy - 9.0, cx + 9.0, cy + 9.0),
                        outline=(0, 255, 122, 255),
                        width=3,
                    )
                    draw.line((cx - 15.0, cy, cx + 15.0, cy), fill=(0, 255, 122, 255), width=2)
                    draw.line((cx, cy - 15.0, cx, cy + 15.0), fill=(0, 255, 122, 255), width=2)
                    label = str(payload.get("placement_label", "object") or "object")
                    draw.text((cx + 16.0, cy - 9.0), f"Drop {label}", fill=(230, 255, 241, 255))

            # The edge-selector widget makes the next operation's
            # direction predictable.  Faces point from their center to the
            # cursor-nearest edge; vertices point along the chosen incident
            # edge.  Edges already communicate direction through the orange
            # segment itself.
            if component in {"face", "vertex"}:
                selector_origin = self._map_studio_project_point(
                    tuple(payload.get("selector_origin_world_point", ()) or ()), w, h
                )
                selector_target = self._map_studio_project_point(
                    tuple(payload.get("selector_world_point", ()) or ()), w, h
                )
                if selector_origin is not None and selector_target is not None:
                    start = (float(selector_origin[0]), float(selector_origin[1]))
                    end = (float(selector_target[0]), float(selector_target[1]))
                    if abs(end[0] - start[0]) + abs(end[1] - start[1]) > 1.0:
                        draw.line([start, end], fill=(0, 0, 0, 210), width=6)
                        draw.line([start, end], fill=(255, 128, 16, 255), width=3)
                        draw.ellipse(
                            (end[0] - 3.0, end[1] - 3.0, end[0] + 3.0, end[1] + 3.0),
                            fill=(255, 128, 16, 255),
                        )
        except Exception as exc:
            log.debug("Map Studio hover highlight overlay failed: %s", exc)

    def _draw_map_studio_room_primitive_handles(self, draw, primitive_handles: tuple[object, ...], w: int, h: int) -> None:
        clean_display = self._map_studio_clean_viewport_enabled()
        subtle_handles = self._map_studio_presentation_flag("subtle_primitive_handles", clean_display)
        show_labels = self._map_studio_presentation_flag("show_primitive_labels", not clean_display)
        selected = {
            (str(room or ""), str(name or ""))
            for room, name in tuple(getattr(self, "_map_studio_room_primitive_selection", ()) or ())
        }
        for handle in primitive_handles:
            footprint = tuple(getattr(handle, "footprint", ()) or ())
            projected = []
            for point in footprint:
                proj = self._map_studio_project_point(point, w, h)
                if proj is None:
                    projected = []
                    break
                projected.append((float(proj[0]), float(proj[1])))
            center = self._map_studio_project_point(getattr(handle, "center", ()), w, h)
            if center is None:
                continue
            color = self._map_studio_marker_rgba(getattr(handle, "color", "#ff9f43"), 155 if subtle_handles else 235)
            room_resref = getattr(handle, "room_resref", "")
            primitive_name = getattr(handle, "primitive_name", "")
            is_selected = (str(room_resref or ""), str(primitive_name or "")) in selected
            if is_selected:
                color = (255, 204, 0, 255)
            world_center = tuple(getattr(handle, "center", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))
            if len(projected) >= 3:
                closed = projected + [projected[0]]
                xs = [point[0] for point in projected]
                ys = [point[1] for point in projected]
                draw.polygon(projected, fill=(color[0], color[1], color[2], 12 if subtle_handles else 18))
                draw.line(closed, fill=(0, 0, 0, 90 if subtle_handles else 145), width=3 if subtle_handles else 4)
                draw.line(closed, fill=color, width=4 if is_selected else (1 if subtle_handles else 2))
                self._add_map_studio_room_primitive_hit_zone(
                    room_resref,
                    primitive_name,
                    kind="rect",
                    bounds=(min(xs) - 7.0, min(ys) - 7.0, max(xs) + 7.0, max(ys) + 7.0),
                    world_center=world_center,
                )
            cx, cy = float(center[0]), float(center[1])
            radius = 6
            diamond = [(cx, cy - radius), (cx + radius, cy), (cx, cy + radius), (cx - radius, cy), (cx, cy - radius)]
            self._add_map_studio_room_primitive_hit_zone(
                room_resref,
                primitive_name,
                kind="circle",
                center=(cx, cy),
                radius=11.0,
                world_center=world_center,
            )
            draw.polygon(
                diamond,
                fill=(color[0], color[1], color[2], 155 if subtle_handles else 225),
                outline=(255, 255, 255, 245) if is_selected else (0, 0, 0, 125 if subtle_handles else 190),
            )
            label = str(getattr(handle, "primitive_type", "") or "")
            if label and show_labels:
                draw.text((cx + 8, cy - 8), label, fill=color)

    def _draw_map_studio_universal_transform_overlay(self, draw, w: int, h: int) -> None:
        overlay = getattr(self, "_map_studio_universal_transform_overlay", None)
        if overlay is None:
            return
        edge_lines = tuple(getattr(overlay, "edge_lines", ()) or ())
        handles = tuple(getattr(overlay, "handles", ()) or ())
        clean_display = self._map_studio_clean_viewport_enabled()
        show_dimensions = self._map_studio_presentation_flag("show_transform_dimensions", not clean_display)
        show_handle_labels = self._map_studio_presentation_flag("show_gimbal_labels", not clean_display)
        labels = tuple(getattr(overlay, "dimension_labels", ()) or ()) if show_dimensions else ()
        if not edge_lines and not handles and not labels:
            return
        try:
            for line in edge_lines:
                start = self._map_studio_project_point(getattr(line, "start", ()), w, h)
                end = self._map_studio_project_point(getattr(line, "end", ()), w, h)
                if start is None or end is None:
                    continue
                color = self._map_studio_marker_rgba(getattr(line, "color", "#00e5ff"), 205 if clean_display else 235)
                points = [(float(start[0]), float(start[1])), (float(end[0]), float(end[1]))]
                draw.line(points, fill=(0, 0, 0, 150 if clean_display else 190), width=4 if clean_display else 5)
                draw.line(points, fill=color, width=1 if clean_display else 2)

            for label in labels:
                start = self._map_studio_project_point(getattr(label, "start", ()), w, h)
                end = self._map_studio_project_point(getattr(label, "end", ()), w, h)
                midpoint = self._map_studio_project_point(getattr(label, "midpoint", ()), w, h)
                if start is None or end is None or midpoint is None:
                    continue
                color = self._map_studio_marker_rgba(getattr(label, "color", "#ffd84a"), 245)
                line_points = [(float(start[0]), float(start[1])), (float(end[0]), float(end[1]))]
                self._draw_map_studio_dashed_line(draw, line_points[0], line_points[1], color=color, width=2)
                text = str(getattr(label, "label", "") or "")
                if text:
                    text_pos = (float(midpoint[0]) + 8.0, float(midpoint[1]) - 10.0)
                    try:
                        text_box = draw.textbbox(text_pos, text)
                        draw.rectangle(
                            (text_box[0] - 4, text_box[1] - 2, text_box[2] + 4, text_box[3] + 2),
                            fill=(0, 0, 0, 175),
                            outline=(color[0], color[1], color[2], 185),
                        )
                    except Exception:
                        pass
                    draw.text(text_pos, text, fill=color)

            room_resref = getattr(overlay, "room_resref", "")
            primitive_name = getattr(overlay, "primitive_name", "")
            mode = str(getattr(self, "_map_studio_transform_gizmo_mode", "translate") or "translate").lower()
            center_world = getattr(overlay, "center", (0.0, 0.0, 0.0))
            center_projected = self._map_studio_project_point(center_world, w, h)
            if center_projected is not None and mode == "rotate":
                cx, cy = float(center_projected[0]), float(center_projected[1])
                dimensions = tuple(getattr(overlay, "dimensions", (1.0, 1.0, 1.0)) or (1.0, 1.0, 1.0))
                max_dimension = max([float(value) for value in dimensions[:3]] + [1.0])
                radius = max(24.0, min(96.0, max_dimension * 18.0))
                for index, (axis, color_hex) in enumerate((("X", "#ff4d4d"), ("Y", "#43d17a"), ("Z", "#58a6ff"))):
                    color = self._map_studio_marker_rgba(color_hex, 235)
                    inset = float(index) * 7.0
                    draw.ellipse(
                        [cx - radius + inset, cy - radius * 0.55 + inset, cx + radius - inset, cy + radius * 0.55 - inset],
                        outline=(0, 0, 0, 215),
                        width=5,
                    )
                    draw.ellipse(
                        [cx - radius + inset, cy - radius * 0.55 + inset, cx + radius - inset, cy + radius * 0.55 - inset],
                        outline=color,
                        width=2,
                    )
                    draw.text((cx + radius - inset + 5.0, cy - 8.0 + (index * 12.0)), axis, fill=color)
            for handle in handles:
                role = str(getattr(handle, "role", "") or "")
                if mode == "rotate" and role != "translate":
                    continue
                if mode == "scale" and role not in {"translate", "corner_scale"}:
                    continue
                if mode not in {"rotate", "scale"} and role == "corner_scale":
                    continue
                projected = self._map_studio_project_point(getattr(handle, "position", ()), w, h)
                if projected is None:
                    continue
                cx, cy = float(projected[0]), float(projected[1])
                color = self._map_studio_marker_rgba(getattr(handle, "color", "#00ff7a"), 245)
                radius = 7.0 if role == "translate" else 5.0
                if mode == "translate" and center_projected is not None and role == "axis_translate":
                    start = (float(center_projected[0]), float(center_projected[1]))
                    end = (cx, cy)
                    draw.line([start, end], fill=(0, 0, 0, 220), width=6)
                    draw.line([start, end], fill=color, width=3)
                if role == "corner_scale":
                    diamond = [(cx, cy - radius), (cx + radius, cy), (cx, cy + radius), (cx - radius, cy)]
                    draw.polygon(diamond, fill=color, outline=(0, 0, 0, 220))
                elif mode == "scale" and role == "translate":
                    draw.rectangle(
                        [cx - radius, cy - radius, cx + radius, cy + radius],
                        fill=color,
                        outline=(0, 0, 0, 220),
                        width=2,
                    )
                else:
                    draw.ellipse(
                        [cx - radius, cy - radius, cx + radius, cy + radius],
                        fill=color,
                        outline=(0, 0, 0, 220),
                        width=2,
                    )
                self._add_map_studio_room_primitive_hit_zone(
                    room_resref,
                    primitive_name,
                    kind="circle",
                    center=(cx, cy),
                    radius=13.0,
                    world_center=getattr(overlay, "center", (0.0, 0.0, 0.0)),
                )
                label_text = str(getattr(handle, "label", "") or "")
                if label_text and role != "corner_scale" and show_handle_labels:
                    draw.text((cx + 8.0, cy - 8.0), label_text, fill=color)
        except Exception as exc:
            log.debug("Map Studio universal transform overlay failed: %s", exc)

    def _draw_map_studio_room_outline_edge_highlight(self, draw, w: int, h: int) -> None:
        highlight = getattr(self, "_map_studio_room_outline_edge_highlight", None)
        if not isinstance(highlight, dict):
            return
        start = self._map_studio_project_point(highlight.get("world_start", ()), w, h)
        end = self._map_studio_project_point(highlight.get("world_end", ()), w, h)
        if start is None or end is None:
            return
        try:
            sx, sy = float(start[0]), float(start[1])
            ex, ey = float(end[0]), float(end[1])
            color = self._map_studio_marker_rgba(highlight.get("color", "#00e5ff"), 245)
            draw.line([(sx, sy), (ex, ey)], fill=(0, 0, 0, 220), width=8)
            draw.line([(sx, sy), (ex, ey)], fill=color, width=4)
            radius = 5.0
            for px, py in ((sx, sy), (ex, ey)):
                draw.ellipse(
                    [px - radius, py - radius, px + radius, py + radius],
                    fill=color,
                    outline=(0, 0, 0, 215),
                    width=1,
                )
            label = str(highlight.get("label", "") or "")
            if label:
                mx = (sx + ex) * 0.5
                my = (sy + ey) * 0.5
                text_pos = (mx + 8.0, my - 10.0)
                try:
                    text_box = draw.textbbox(text_pos, label)
                    draw.rectangle(
                        (text_box[0] - 4, text_box[1] - 2, text_box[2] + 4, text_box[3] + 2),
                        fill=(0, 0, 0, 165),
                        outline=(color[0], color[1], color[2], 175),
                    )
                except Exception:
                    pass
                draw.text(text_pos, label, fill=color)
        except Exception as exc:
            log.debug("Map Studio room outline edge highlight failed: %s", exc)

    def _draw_map_studio_room_outline_snap_highlight(self, draw, w: int, h: int) -> None:
        highlight = getattr(self, "_map_studio_room_outline_snap_highlight", None)
        if not isinstance(highlight, dict):
            return
        position = highlight.get("world_position", ())
        projected = self._map_studio_project_point(position, w, h)
        if projected is None:
            return
        try:
            cx, cy = float(projected[0]), float(projected[1])
            color = self._map_studio_marker_rgba(highlight.get("color", "#ffd84a"), 245)
            outer = 11.0
            inner = 4.0
            draw.ellipse(
                [cx - outer, cy - outer, cx + outer, cy + outer],
                outline=(0, 0, 0, 215),
                width=5,
            )
            draw.ellipse(
                [cx - outer, cy - outer, cx + outer, cy + outer],
                outline=color,
                width=3,
            )
            draw.ellipse(
                [cx - inner, cy - inner, cx + inner, cy + inner],
                fill=color,
                outline=(0, 0, 0, 210),
                width=1,
            )
            draw.line([(cx - 15.0, cy), (cx - 7.0, cy)], fill=color, width=2)
            draw.line([(cx + 7.0, cy), (cx + 15.0, cy)], fill=color, width=2)
            draw.line([(cx, cy - 15.0), (cx, cy - 7.0)], fill=color, width=2)
            draw.line([(cx, cy + 7.0), (cx, cy + 15.0)], fill=color, width=2)
            label = str(highlight.get("label", "") or "")
            if label:
                text_pos = (cx + 14.0, cy - 12.0)
                try:
                    text_box = draw.textbbox(text_pos, label)
                    draw.rectangle(
                        (text_box[0] - 4, text_box[1] - 2, text_box[2] + 4, text_box[3] + 2),
                        fill=(0, 0, 0, 165),
                        outline=(color[0], color[1], color[2], 175),
                    )
                except Exception:
                    pass
                draw.text(text_pos, label, fill=color)
        except Exception as exc:
            log.debug("Map Studio room outline snap highlight failed: %s", exc)

    @staticmethod
    def _draw_map_studio_dashed_line(draw, start, end, *, color: tuple[int, int, int, int], width: int = 2) -> None:
        sx, sy = float(start[0]), float(start[1])
        ex, ey = float(end[0]), float(end[1])
        segments = 10
        for index in range(segments):
            if index % 2:
                continue
            t0 = index / segments
            t1 = (index + 1) / segments
            p0 = (sx + (ex - sx) * t0, sy + (ey - sy) * t0)
            p1 = (sx + (ex - sx) * t1, sy + (ey - sy) * t1)
            draw.line([p0, p1], fill=(0, 0, 0, 150), width=width + 2)
            draw.line([p0, p1], fill=color, width=width)

    def _draw_wgpu_helper_markers(self, draw, w: int, h: int) -> None:
        if self.model is None:
            return
        try:
            if self.canvas.is_live_surface() and str(getattr(getattr(self, "_gpu_renderer", None), "backend_id", "") or "") == "pygfx_wgpu":
                return
        except Exception:
            pass
        if not bool(getattr(self._renderer, "show_dummy_helpers", getattr(self, "_dummy_helpers_visible", True))):
            return
        try:
            nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        except Exception:
            return
        selected = getattr(self._renderer, "selected_node", None)
        selected_ids = {id(node) for node in getattr(self, "_selected_viewport_nodes", []) or []}
        hovered = getattr(self, "_hovered_helper_node", None)
        base = tuple(int(v) for v in tuple(getattr(self._camera_helper_renderer, "camera_color", (180, 210, 220, 210)))[:4])
        selected_color = (255, 212, 0, 235)
        hovered_color = (0, 215, 181, 235)
        for node in nodes:
            if not self._is_general_helper_node(node):
                continue
            if bool(getattr(node, "_gr_hidden", False)):
                continue
            try:
                x, y, _depth = self._renderer._proj(*self._helper_world_position(node), w, h)
            except Exception:
                continue
            is_selected = node is selected or id(node) in selected_ids or bool(getattr(node, "_gr_selected", False))
            is_hovered = node is hovered
            size = 7 if is_selected or is_hovered else 5
            color = selected_color if is_selected else (hovered_color if is_hovered else base)
            fill = (color[0], color[1], color[2], 65 if is_selected or is_hovered else 42)
            pts = [(x, y - size), (x + size, y), (x, y + size), (x - size, y), (x, y - size)]
            draw.polygon(pts, fill=fill)
            draw.line(pts, fill=color, width=2 if is_selected or is_hovered else 1)

    def _draw_active_camera_overlays(self, draw, w: int, h: int) -> None:
        try:
            if bool(getattr(self, "_render_suppress_camera_overlays", False)):
                return
            camera = self.camera_manager.get_active_camera()
            if camera is None or not self._camera_view_active:
                return
            self._camera_overlays.draw(draw, camera, w, h, include_guides=True)
        except Exception as exc:
            log.debug("Camera overlay draw failed: %s", exc)

    # ── T401: Joint-dot overlay ────────────────────────────────────────
    def _draw_joint_marquee(self, draw) -> None:
        if not self._joint_marquee_selecting:
            return
        try:
            x0, y0 = self._joint_marquee_start
            x1, y1 = self._joint_marquee_current
            if abs(x1 - x0) < self._drag_threshold and abs(y1 - y0) < self._drag_threshold:
                return
            left, right = sorted((int(x0), int(x1)))
            top, bottom = sorted((int(y0), int(y1)))
            draw.rectangle([left, top, right, bottom], fill=(255, 212, 0, 38), outline=(255, 212, 0, 210), width=1)
        except Exception as exc:
            log.debug("Joint marquee draw failed: %s", exc)

    def _draw_joint_dots(self, img, w: int, h: int) -> None:
        """Paint AccuRig-style color-coded joint dots over the mesh.

        Color classification follows the M4 spec:
          * center        → ``JOINT_DOT_COLOR_CENTER``         (#FFD400)
          * center-spine  → ``JOINT_DOT_COLOR_CENTER_SPINE``   (#00D7B5)
          * L-side        → ``JOINT_DOT_COLOR_LEFT``           (#FF4040)
          * R-side        → ``JOINT_DOT_COLOR_RIGHT``          (#00FF7A)

        Size and opacity are inspector-driven (see ``set_joint_dot_size`` /
        ``set_joint_dot_opacity``).  This method consumes the renderer's
        per-frame ``_bone_screen_positions`` cache (already populated by
        ``_draw_bones``) so projection cost is zero.
        """
        try:
            positions = getattr(self._renderer, "_bone_screen_positions", None)
            if not positions:
                return

            radius = int(max(1, min(8, self._joint_dot_size)))
            alpha = int(round(max(0.0, min(1.0, self._joint_dot_opacity)) * 255))
            if alpha <= 0:
                return

            # Convert the PIL image to a QImage in-place so we can render
            # smooth, anti-aliased Qt circles.  The image is wrapped
            # via the buffer protocol — no pixel copy is performed.
            try:
                from PIL.ImageQt import ImageQt
            except Exception:
                # Fallback: draw with PIL primitives (no AA but still correct).
                self._draw_joint_dots_pil(img, positions, radius, alpha)
                return

            qimg = QtGui.QImage(ImageQt(img))
            painter = QtGui.QPainter(qimg)
            try:
                painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
                # Selected node gets a brighter outline so the user can
                # still see selection state through the dot.
                sel_node = getattr(self._renderer, "selected_node", None)
                hovered_node = getattr(self._renderer, "_hovered_bone", None)
                bones_active = bool(getattr(self._renderer, "show_bones", False))
                joint_border = QtGui.QColor("#FFD400")
                hover_border = QtGui.QColor("#FF8C00")
                for entry in positions:
                    if not entry or len(entry) < 4:
                        continue
                    sx, sy, _depth, node = entry[0], entry[1], entry[2], entry[3]
                    if sx is None or sy is None:
                        continue
                    name = getattr(node, "name", "") or ""
                    color = QtGui.QColor("#FFDA28") if node is sel_node else QtGui.QColor(_classify_joint_color(name))
                    color.setAlpha(alpha)
                    border = QtGui.QColor(hover_border if bones_active and node is hovered_node else joint_border)
                    border.setAlpha(alpha)
                    painter.setBrush(QtGui.QBrush(color))
                    painter.setPen(QtGui.QPen(border, 2.0))
                    painter.drawEllipse(
                        QtCore.QPointF(float(sx), float(sy)),
                        float(radius),
                        float(radius),
                    )
            finally:
                painter.end()

            # Copy the painted QImage pixels back into the PIL image
            # buffer.  We rely on PIL's `frombytes` to avoid returning a
            # new object (the caller already holds `img`).
            try:
                qimg_rgba = qimg.convertToFormat(QtGui.QImage.Format_RGBA8888)
                ptr = qimg_rgba.constBits()
                # PySide6 returns a memoryview; ensure we have raw bytes
                raw = bytes(ptr)[: qimg_rgba.sizeInBytes()]
                from PIL import Image as _PILImage  # noqa: F401  (import side-effect safety)
                img.frombytes(raw)
            except Exception as exc:
                log.debug("Joint-dot pixel writeback fell back: %s", exc)
                self._draw_joint_dots_pil(img, positions, radius, alpha)
        except Exception as exc:
            log.debug("Joint-dot overlay failed: %s", exc)

    # ── T405: Weight heat-map overlay ──────────────────────────────────
    def _draw_weight_heatmap(self, draw, W: int, H: int) -> None:
        """Paint a per-vertex weight heat-map for the selected bone.

        For every skin-mesh node in the model, project each vertex to
        screen space and stamp a small filled circle whose color is
        :func:`_weight_to_heatmap_color` of the selected bone's weight
        on that vertex.  Vertices not influenced by the selected bone
        receive weight 0 → deep blue.

        No-op fast paths:
          * No model or no selected node → return immediately.
          * Selected node not present in a given mesh's ``bone_map`` →
            skip that mesh (all its vertices would be weight=0 noise).
        """
        if self.model is None:
            return
        sel = self._renderer.selected_node
        if sel is None:
            return
        sel_name = (getattr(sel, "name", "") or "").lower()
        if not sel_name:
            return
        try:
            mesh_iter = self.model.mesh_nodes() if hasattr(self.model, "mesh_nodes") else []
        except Exception:
            return
        radius = int(max(1, min(8, self._weight_heatmap_dot_size)))
        for node in mesh_iter:
            try:
                verts = getattr(node, "vertices", None) or []
                skin_data = getattr(node, "skin_data", None) or []
                bone_map = getattr(node, "bone_map", None) or []
                if not verts or not skin_data or not bone_map:
                    continue
                # Find the selected bone's index in this mesh's bone_map.
                # Bone names in bone_map are stored as authored; compare
                # case-insensitively.
                sel_idx = -1
                for i, bn in enumerate(bone_map):
                    if isinstance(bn, str) and bn.lower() == sel_name:
                        sel_idx = i
                        break
                if sel_idx < 0:
                    continue
                # Project all verts in this mesh in one batched call.
                try:
                    wp, _wo, _ = self._renderer._node_world_transform(node)
                except Exception:
                    wp = (0.0, 0.0, 0.0)
                world_verts = [(v[0] + wp[0], v[1] + wp[1], v[2] + wp[2]) for v in verts]
                projections = self._renderer._proj_batch(world_verts, W, H)
                for vi, proj in enumerate(projections):
                    if proj is None:
                        continue
                    sx, sy, _depth = proj
                    if sx < -radius or sy < -radius or sx > W + radius or sy > H + radius:
                        continue
                    # Look up the selected bone's weight on this vertex.
                    weight = 0.0
                    if vi < len(skin_data):
                        infl = getattr(skin_data[vi], "influences", None) or []
                        for bw in infl:
                            if getattr(bw, "bone_index", -1) == sel_idx:
                                weight = float(getattr(bw, "weight", 0.0))
                                break
                    r8, g8, b8 = _weight_to_heatmap_color(weight)
                    fill = (r8, g8, b8, 200)
                    draw.ellipse(
                        [sx - radius, sy - radius, sx + radius, sy + radius],
                        fill=fill,
                        outline=None,
                    )
            except Exception as exc:
                log.debug("Heat-map draw skipped node %s: %s",
                          getattr(node, "name", "?"), exc)
                continue

    def set_weight_heatmap_enabled(self, enabled: bool) -> None:
        """Toggle the per-vertex weight heat-map overlay."""
        new_val = bool(enabled)
        if new_val == self._weight_heatmap_enabled:
            if hasattr(self, "heatmap_button"):
                self.heatmap_button.blockSignals(True)
                self.heatmap_button.setChecked(new_val)
                self.heatmap_button.blockSignals(False)
            return
        self._weight_heatmap_enabled = new_val
        if hasattr(self, "heatmap_button"):
            self.heatmap_button.blockSignals(True)
            self.heatmap_button.setChecked(new_val)
            self.heatmap_button.blockSignals(False)
        self._request_render()

    def set_weight_heatmap_dot_size(self, size: int) -> None:
        """Set the heat-map dot radius in pixels.  Clamped to [1, 8]."""
        new_size = int(max(1, min(8, int(size))))
        if new_size == self._weight_heatmap_dot_size:
            return
        self._weight_heatmap_dot_size = new_size
        self._request_render()

    @property
    def weight_heatmap_enabled(self) -> bool:
        return self._weight_heatmap_enabled

    @property
    def weight_heatmap_dot_size(self) -> int:
        return self._weight_heatmap_dot_size

    def _draw_joint_dots_pil(self, img, positions, radius: int, alpha: int) -> None:
        """PIL-only fallback for ``_draw_joint_dots`` (no anti-aliasing).

        Used when ``PIL.ImageQt`` is unavailable or the QImage round-trip
        fails.  Functionally equivalent — colors and hit positions match.
        """
        try:
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img, "RGBA")
            sel_node = getattr(self._renderer, "selected_node", None)
            hovered_node = getattr(self._renderer, "_hovered_bone", None)
            bones_active = bool(getattr(self._renderer, "show_bones", False))
            for entry in positions:
                if not entry or len(entry) < 4:
                    continue
                sx, sy, _depth, node = entry[0], entry[1], entry[2], entry[3]
                if sx is None or sy is None:
                    continue
                name = getattr(node, "name", "") or ""
                qc = QtGui.QColor("#FFDA28") if node is sel_node else _classify_joint_color(name)
                fill = (qc.red(), qc.green(), qc.blue(), alpha)
                outline = (255, 140, 0, alpha) if bones_active and node is hovered_node else (255, 212, 0, alpha)
                draw.ellipse(
                    [sx - radius, sy - radius, sx + radius, sy + radius],
                    fill=fill,
                    outline=outline,
                    width=2,
                )
        except Exception as exc:
            log.debug("Joint-dot PIL fallback failed: %s", exc)

    def _draw_locomotion_discs(self, img, w: int, h: int) -> None:
        """Paint adjustable compass/ruler locomotion discs around key joints."""
        if not self._locomotion_disc_enabled:
            return
        positions = getattr(self._renderer, "_bone_screen_positions", None)
        if not positions:
            return
        try:
            from PIL import Image
            size = int(max(32, min(256, int(getattr(self, "_locomotion_disc_size", 96)))))
            cache = getattr(self, "_locomotion_disc_pixmap_cache", None)
            if not cache or cache[0] != size:
                asset = _ICON_DIR / "locomotion_disc.png"
                disc = Image.open(asset).convert("RGBA").resize((size, size), Image.LANCZOS)
                self._locomotion_disc_pixmap_cache = (size, disc)
            else:
                disc = cache[1]
            axis_angles = getattr(self._renderer, "_bone_screen_axis_angles", {}) or {}
            half = size * 0.5
            for entry in positions:
                if not entry or len(entry) < 4:
                    continue
                sx, sy, _depth, node = entry[0], entry[1], entry[2], entry[3]
                if sx is None or sy is None:
                    continue
                if not _is_key_joint_name(getattr(node, "name", "") or ""):
                    continue
                node_disc = disc
                angle = axis_angles.get(id(node))
                if angle is not None:
                    try:
                        node_disc = disc.rotate(float(angle), resample=Image.BICUBIC, expand=False)
                    except Exception:
                        node_disc = disc
                left = int(round(float(sx) - half))
                top = int(round(float(sy) - half))
                if left > w or top > h or left + size < 0 or top + size < 0:
                    continue
                img.alpha_composite(node_disc, (left, top))
        except Exception as exc:
            log.debug("Locomotion disc overlay failed: %s", exc)

    # ── T402: Joint-dot hit-test + symmetry ────────────────────────────
    def _joint_dot_hit_test(self, x: int, y: int):
        """Return the joint node under screen pixel ``(x, y)`` or ``None``.

        Uses the same ``_bone_screen_positions`` cache populated by the
        renderer's last ``_draw_bones`` pass, so this is essentially
        free.  The hit-radius is the user's current joint-dot radius
        plus a small slack so corner pixels still count.
        """
        if not self._joint_dot_enabled:
            return None
        positions = self._joint_hit_positions()
        if not positions:
            return None
        # 4 px slack so the cursor can be slightly outside the painted disc.
        radius = int(max(1, min(8, self._joint_dot_size))) + 4
        r2 = radius * radius
        best_node = None
        best_d2 = r2
        best_depth = 1e18
        for entry in positions:
            if not entry or len(entry) < 4:
                continue
            sx, sy, depth, node = entry[0], entry[1], entry[2], entry[3]
            if sx is None or sy is None:
                continue
            dx = sx - x
            dy = sy - y
            d2 = dx * dx + dy * dy
            if d2 > r2:
                continue
            # Prefer the closer (smaller depth) of the dots within range —
            # when joints overlap on screen the front-most one should win.
            if d2 < best_d2 or (d2 == best_d2 and depth < best_depth):
                best_d2 = d2
                best_depth = depth
                best_node = node
        return best_node

    def _joint_mirror_partner(self, node):
        """Return the MIRROR_PAIRS partner node of ``node`` or ``None``.

        Symmetry-aware drags rely on this to look up the bone whose
        position must be reflected across the model's X axis.  Looks
        up partners using ``src/autorig/accurig.MIRROR_PAIRS`` (the
        canonical AccuRig L↔R table) in both directions.
        """
        if node is None or not self._joint_symmetry_enabled:
            return None
        search_model = (
            getattr(self._renderer, "_ext_skeleton", None)
            if self._is_external_skeleton_node(node)
            else self.model
        )
        if not search_model:
            return None
        name = (getattr(node, "name", "") or "").lower()
        if not name:
            return None
        try:
            from src.autorig.accurig import MIRROR_PAIRS
        except Exception:
            try:
                from src.autorig.accurig import MIRROR_PAIRS  # type: ignore
            except Exception:
                try:
                    from autorig.accurig import MIRROR_PAIRS  # type: ignore
                except Exception:
                    MIRROR_PAIRS = {}
        partner_name = None
        # Forward lookup (left -> right)
        if name in MIRROR_PAIRS:
            partner_name = MIRROR_PAIRS[name]
        else:
            # Reverse lookup (right -> left)
            for ln, rn in MIRROR_PAIRS.items():
                if rn == name:
                    partner_name = ln
                    break
        if partner_name is not None:
            try:
                found = search_model.find_node(partner_name)
                if found is not None:
                    return found
            except Exception:
                pass

        # KOTOR skeletons include useful l*/r* pairs that are not all in
        # AcuRig's compact guide table, for example lcollar_dum/rcollar_dum.
        candidates = []
        if name.startswith("l"):
            candidates.append("r" + name[1:])
        elif name.startswith("r"):
            candidates.append("l" + name[1:])
        candidates.extend([
            name.replace("_l", "_r"),
            name.replace("_r", "_l"),
            name.replace(".l", ".r"),
            name.replace(".r", ".l"),
            name.replace("left", "right"),
            name.replace("right", "left"),
        ])
        for candidate in candidates:
            if not candidate or candidate == name:
                continue
            try:
                found = search_model.find_node(candidate)
                if found is not None:
                    return found
            except Exception:
                continue
        return None

    def set_joint_symmetry(self, enabled: bool) -> None:
        """Toggle MIRROR_PAIRS-based symmetry for joint-dot drags."""
        self._joint_symmetry_enabled = bool(enabled)

    @property
    def joint_symmetry_enabled(self) -> bool:
        return self._joint_symmetry_enabled

    # ── T401: Public setters (inspector wires these later in M4) ───────
    def set_joint_dot_enabled(self, enabled: bool) -> None:
        """Toggle the joint-dot overlay layer on/off."""
        new_val = bool(enabled)
        if new_val == self._joint_dot_enabled:
            if hasattr(self, "joint_dot_button"):
                self.joint_dot_button.blockSignals(True)
                self.joint_dot_button.setChecked(new_val)
                self.joint_dot_button.blockSignals(False)
            return
        self._joint_dot_enabled = new_val
        if hasattr(self, "joint_dot_button"):
            self.joint_dot_button.blockSignals(True)
            self.joint_dot_button.setChecked(new_val)
            self.joint_dot_button.blockSignals(False)
        self._request_render()

    def set_joint_dot_size(self, size: int) -> None:
        """Set joint-dot radius in pixels.  Clamped to [1, 8]."""
        new_size = int(max(1, min(8, int(size))))
        if new_size == self._joint_dot_size:
            return
        self._joint_dot_size = new_size
        self._request_render()

    def set_joint_dot_opacity(self, opacity: float) -> None:
        """Set joint-dot opacity in [0.0, 1.0]."""
        new_op = float(max(0.0, min(1.0, float(opacity))))
        if abs(new_op - self._joint_dot_opacity) < 1e-4:
            return
        self._joint_dot_opacity = new_op
        self._request_render()

    def set_locomotion_disc_enabled(self, enabled: bool) -> None:
        """Toggle the key-joint locomotion disc overlay on/off."""
        new_val = bool(enabled)
        if new_val == self._locomotion_disc_enabled:
            if hasattr(self, "locomotion_disc_button"):
                self.locomotion_disc_button.blockSignals(True)
                self.locomotion_disc_button.setChecked(new_val)
                self.locomotion_disc_button.blockSignals(False)
            return
        self._locomotion_disc_enabled = new_val
        if hasattr(self, "locomotion_disc_button"):
            self.locomotion_disc_button.blockSignals(True)
            self.locomotion_disc_button.setChecked(new_val)
            self.locomotion_disc_button.blockSignals(False)
        self._request_render()

    def set_locomotion_disc_size(self, size: int) -> None:
        """Set locomotion disc size in screen pixels. Clamped to [32, 256]."""
        new_size = int(max(32, min(256, int(size))))
        if hasattr(self, "locomotion_disc_size_spin"):
            self.locomotion_disc_size_spin.blockSignals(True)
            self.locomotion_disc_size_spin.setValue(new_size)
            self.locomotion_disc_size_spin.blockSignals(False)
        if new_size == self._locomotion_disc_size:
            return
        self._locomotion_disc_size = new_size
        self._locomotion_disc_pixmap_cache = None
        self._request_render()

    @property
    def joint_dot_enabled(self) -> bool:
        return self._joint_dot_enabled

    @property
    def joint_dot_size(self) -> int:
        return self._joint_dot_size

    @property
    def joint_dot_opacity(self) -> float:
        return self._joint_dot_opacity

    @property
    def locomotion_disc_enabled(self) -> bool:
        return self._locomotion_disc_enabled

    @property
    def locomotion_disc_size(self) -> int:
        return self._locomotion_disc_size

    def _update_fps(self) -> None:
        now = time_module.perf_counter()
        delta = max(0.0, now - self._fps_last_wall)
        self._fps_last_wall = now
        self._fps_accum += delta
        self._fps_frames += 1
        if self._fps_accum >= 0.5:
            self._fps_display = self._fps_frames / max(self._fps_accum, 1e-6)
            self._fps_accum = 0.0
            self._fps_frames = 0

    def _draw_performance_overlay(self, img, w: int, h: int):
        if bool(self.property("_gr_suppress_renderer_diagnostics")):
            return img
        if bool(
            getattr(self, "_map_studio_authoring_chrome_enabled", False)
            and getattr(self, "_nav_dragging", "")
        ):
            # Active Map Studio navigation uses a lean overlay set.  The full
            # diagnostics HUD is restored by the release-frame redraw.
            return img
        try:
            from PIL import ImageDraw

            if img.mode != "RGBA":
                img = img.convert("RGBA")
            draw = ImageDraw.Draw(img, "RGBA")
            fps = self._fps_display
            if fps <= 0.0 and self._last_render_ms > 0.0:
                fps = 1000.0 / max(self._last_render_ms, 1.0)
            mode = "fast" if time_module.perf_counter() < self._fast_frame_until else "hq"
            now = time_module.perf_counter()
            hz = max(0.1, float(getattr(self._renderer_settings, "diagnostics_hz", 2.0) or 2.0))
            if (
                not getattr(self._renderer_settings, "throttle_diagnostics", True)
                or now - float(getattr(self, "_last_performance_overlay_update_wall", 0.0)) >= (1.0 / hz)
                or not getattr(self, "_last_performance_overlay_label", "")
            ):
                self._last_performance_overlay_label = f"{fps:4.0f} fps  {self._last_render_ms:4.0f} ms  {mode}"
                self._last_performance_overlay_update_wall = now
            label = self._last_performance_overlay_label
            max_width = max(80, w - 16)
            text_w = (
                self._renderer._hud_pill_width(label, max_width=max_width)
                if hasattr(self._renderer, "_hud_pill_width")
                else min(max_width, len(label) * 7 + 14)
            )
            x = max(8, w - text_w - 8)
            y = max(8, h - 50)
            self._renderer._draw_hud_pill(
                draw,
                x,
                y,
                label,
                fill=(18, 22, 27),
                fg=(156, 232, 184),
                outline=(42, 90, 62),
                max_width=max_width,
            )
            return img
        except Exception as exc:
            log.debug("Viewport FPS overlay draw failed: %s", exc)
            return img

    def _preload_gpu_textures(self) -> None:
        model = self.model
        tex_cache = getattr(self._renderer, "tex_cache", None)
        if model is None or tex_cache is None or id(model) == self._gpu_tex_preload_model_id:
            return
        # Do not synchronously decode archive textures on the Qt paint path.
        # Background _prewarm_textures() populates TextureCache, and each refresh
        # uploads whatever is already resident. Missing textures render with the
        # GPU fallback material until the background pass emits a refresh.
        self._gpu_tex_preload_model_id = id(model)

    def _gpu_texture_snapshot(self) -> dict:
        tex_cache = getattr(self._renderer, "tex_cache", None)
        cache = getattr(tex_cache, "_cache", {}) if tex_cache is not None else {}
        live_items = tuple(sorted((str(key), id(value)) for key, value in cache.items() if value is not None))
        model_id = id(self.model) if self.model is not None else 0
        governor = getattr(self, "_frame_governor", None)
        dirty_flags = getattr(governor, "dirty_flags", {}) if governor is not None else {}
        if bool(dirty_flags.get("resources", False)):
            self._gpu_baked_lightmap_snapshot_model_id = 0
        if model_id != self._gpu_baked_lightmap_snapshot_model_id:
            baked_items: list[tuple[str, str, float]] = []
            try:
                nodes = self.model.all_nodes() if hasattr(self.model, "all_nodes") else []
                for node in nodes:
                    override_path = str(getattr(node, "_gr_baked_lightmap_preview_path", "") or getattr(node, "_gr_baked_lightmap_path", "") or "")
                    override_name = str(getattr(node, "_gr_baked_lightmap_preview_name", "") or "")
                    if override_path and override_name and os.path.isfile(override_path):
                        try:
                            mtime = os.path.getmtime(override_path)
                        except OSError:
                            mtime = 0.0
                        baked_items.append((override_name.lower(), override_path, float(mtime)))
            except Exception:
                baked_items = []
            self._gpu_baked_lightmap_snapshot_model_id = model_id
            self._gpu_baked_lightmap_snapshot = tuple(sorted(baked_items))
        key = (live_items, self._gpu_baked_lightmap_snapshot)
        if key == self._gpu_texture_snapshot_key:
            return self._gpu_texture_snapshot_cache
        textures = {key: value for key, value in cache.items() if value is not None}
        if self._gpu_baked_lightmap_snapshot:
            try:
                from PIL import Image

                for override_name, override_path, _mtime in self._gpu_baked_lightmap_snapshot:
                    textures[override_name] = Image.open(override_path).convert("RGBA")
            except Exception:
                pass
        self._gpu_texture_snapshot_key = key
        self._gpu_texture_snapshot_cache = textures
        self._gpu_texture_snapshot_rebuilds += 1
        return textures

    def _set_renderer_badge(self, gpu_active: bool) -> None:
        if not hasattr(self, "renderer_button"):
            return
        self._use_gpu = True
        self.renderer_button.setChecked(True)
        backend = ""
        if self._gpu_renderer is not None:
            get_diagnostics = getattr(self._gpu_renderer, "get_diagnostics", None)
            if callable(get_diagnostics):
                try:
                    backend = str((get_diagnostics() or {}).get("name") or "")
                except Exception:
                    backend = ""
        label = f"GPU renderer: {backend}" if backend else "GPU renderer"
        self.renderer_button.setToolTip(label if gpu_active else "GPU renderer unavailable")

    def _on_shade_change(self, text: str) -> None:
        self.set_shade_mode(text)

__all__ = ("ViewportOverlayLayersMixin",)
