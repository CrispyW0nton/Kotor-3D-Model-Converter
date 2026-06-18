"""ViewportOverlayLayers methods for the Qt viewport widget."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportOverlayLayersMixin:
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

    def _map_studio_project_point(self, point: object, w: int, h: int):
        try:
            x, y, z = point
            return self._renderer._proj(float(x), float(y), float(z), w, h)
        except Exception:
            return None

    def _draw_map_studio_placement_markers(self, draw, w: int, h: int) -> None:
        geometry = getattr(self, "_map_studio_marker_geometry", None)
        if geometry is None:
            return
        footprints = tuple(getattr(geometry, "footprints", ()) or ())
        lines = tuple(getattr(geometry, "lines", ()) or ())
        if not footprints and not lines:
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
                    color = self._map_studio_marker_rgba(getattr(footprint, "color", ""), 220)
                    fill = (color[0], color[1], color[2], 34)
                    outline = (color[0], color[1], color[2], 205)
                    closed = projected + [projected[0]]
                    draw.polygon(projected, fill=fill)
                    draw.line(closed, fill=(0, 0, 0, 125), width=4)
                    draw.line(closed, fill=outline, width=2)
            for guide in lines:
                start = self._map_studio_project_point(getattr(guide, "start", ()), w, h)
                end = self._map_studio_project_point(getattr(guide, "end", ()), w, h)
                if start is None or end is None:
                    continue
                color = self._map_studio_marker_rgba(getattr(guide, "color", ""), 235)
                role = str(getattr(guide, "role", "") or "")
                width = 3 if role == "facing" else 2
                sx, sy = float(start[0]), float(start[1])
                ex, ey = float(end[0]), float(end[1])
                if role == "height":
                    segments = 6
                    for index in range(segments):
                        if index % 2:
                            continue
                        t0 = index / segments
                        t1 = (index + 1) / segments
                        p0 = (sx + (ex - sx) * t0, sy + (ey - sy) * t0)
                        p1 = (sx + (ex - sx) * t1, sy + (ey - sy) * t1)
                        draw.line([p0, p1], fill=(0, 0, 0, 145), width=width + 2)
                        draw.line([p0, p1], fill=color, width=width)
                else:
                    draw.line([(sx, sy), (ex, ey)], fill=(0, 0, 0, 145), width=width + 2)
                    draw.line([(sx, sy), (ex, ey)], fill=color, width=width)
                radius = 4
                draw.ellipse(
                    [sx - radius, sy - radius, sx + radius, sy + radius],
                    fill=color,
                    outline=(0, 0, 0, 180),
                    width=1,
                )
                if role == "facing":
                    radius = 3
                    draw.ellipse(
                        [ex - radius, ey - radius, ex + radius, ey + radius],
                        fill=color,
                        outline=(0, 0, 0, 180),
                        width=1,
                    )
        except Exception as exc:
            log.debug("Map Studio placement marker overlay failed: %s", exc)

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
                selected_ids = {id(n) for n in self._selected_joint_nodes}
                outline_pen = QtGui.QPen(QtGui.QColor(0, 0, 0, alpha), 1.0)
                sel_pen = QtGui.QPen(QtGui.QColor(255, 255, 255, alpha), 2.0)
                key_color = QtGui.QColor(JOINT_DOT_COLOR_KEY)
                key_color.setAlpha(alpha)
                key_pen = QtGui.QPen(key_color, 2.0)
                for entry in positions:
                    if not entry or len(entry) < 4:
                        continue
                    sx, sy, _depth, node = entry[0], entry[1], entry[2], entry[3]
                    if sx is None or sy is None:
                        continue
                    name = getattr(node, "name", "") or ""
                    color = QtGui.QColor("#FFDA28") if node is sel_node else QtGui.QColor(_classify_joint_color(name))
                    color.setAlpha(alpha)
                    if _is_key_joint_name(name):
                        painter.setBrush(QtGui.QBrush(QtCore.Qt.NoBrush))
                        painter.setPen(key_pen)
                        painter.drawEllipse(
                            QtCore.QPointF(float(sx), float(sy)),
                            float(radius + 2),
                            float(radius + 2),
                        )
                    painter.setBrush(QtGui.QBrush(color))
                    painter.setPen(sel_pen if node is sel_node or id(node) in selected_ids else outline_pen)
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
            selected_ids = {id(n) for n in self._selected_joint_nodes}
            for entry in positions:
                if not entry or len(entry) < 4:
                    continue
                sx, sy, _depth, node = entry[0], entry[1], entry[2], entry[3]
                if sx is None or sy is None:
                    continue
                name = getattr(node, "name", "") or ""
                qc = QtGui.QColor("#FFDA28") if node is sel_node else _classify_joint_color(name)
                fill = (qc.red(), qc.green(), qc.blue(), alpha)
                is_selected = node is sel_node or id(node) in selected_ids
                outline = (255, 255, 255, alpha) if is_selected else (0, 0, 0, alpha)
                if _is_key_joint_name(name):
                    key_outline = (
                        JOINT_DOT_COLOR_KEY.red(),
                        JOINT_DOT_COLOR_KEY.green(),
                        JOINT_DOT_COLOR_KEY.blue(),
                        alpha,
                    )
                    draw.ellipse(
                        [sx - radius - 2, sy - radius - 2, sx + radius + 2, sy + radius + 2],
                        outline=key_outline,
                        width=2,
                    )
                draw.ellipse(
                    [sx - radius, sy - radius, sx + radius, sy + radius],
                    fill=fill,
                    outline=outline,
                    width=2 if is_selected else 1,
                )
        except Exception as exc:
            log.debug("Joint-dot PIL fallback failed: %s", exc)

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

    @property
    def joint_dot_enabled(self) -> bool:
        return self._joint_dot_enabled

    @property
    def joint_dot_size(self) -> int:
        return self._joint_dot_size

    @property
    def joint_dot_opacity(self) -> float:
        return self._joint_dot_opacity

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
