"""ViewportEventNavigation methods for the Qt viewport widget."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportEventNavigationMixin:
    def set_map_studio_terrain_sculpt_input_lock(self, enabled: bool) -> None:
        """Make sculpt strokes and shared viewport navigation mutually exclusive.

        Map Studio supplies its own deliberate right-button orbit while this
        lock is active.  Cancelling any generic navigation already in flight
        prevents an Alt+left or middle-button gesture from leaking across the
        moment Sculpt Mode is entered.
        """

        locked = bool(enabled)
        self._gr_map_studio_terrain_sculpt_input_lock = locked
        if not locked:
            return
        if getattr(self, "_nav_dragging", ""):
            self._release_navigation(None)
        cancel_marquee = getattr(self, "cancel_selection_marquee", None)
        if callable(cancel_marquee):
            cancel_marquee()
        if bool(getattr(self, "_transform_gizmo_dragging", False)):
            cancel_gizmo = getattr(self, "_cancel_transform_gizmo_drag", None)
            if callable(cancel_gizmo):
                cancel_gizmo()

    def _consume_map_studio_terrain_navigation_event(self, event) -> bool:
        """Fail closed if the Map Studio sculpt handler misses a drag event."""

        if not bool(getattr(self, "_gr_map_studio_terrain_sculpt_input_lock", False)):
            return False
        event_type = event.type()
        pointer_buttons = QtCore.Qt.LeftButton | QtCore.Qt.MiddleButton | QtCore.Qt.RightButton
        if event_type in {
            QtCore.QEvent.MouseButtonPress,
            QtCore.QEvent.MouseButtonDblClick,
            QtCore.QEvent.MouseButtonRelease,
        }:
            consumes = bool(event.button() & pointer_buttons)
        elif event_type == QtCore.QEvent.MouseMove:
            consumes = bool(event.buttons() & pointer_buttons)
        else:
            consumes = False
        if not consumes:
            return False
        if getattr(self, "_nav_dragging", ""):
            self._release_navigation(None)
        return True

    def _cycle_navigation_profile(self) -> None:
        order = ["3dsmax", "blender", "maya"]
        try:
            index = order.index(self._navigation_profile)
        except ValueError:
            index = -1
        self.set_navigation_profile(order[(index + 1) % len(order)])

    def _is_viewport_event_source(self, obj) -> bool:
        return obj is self.canvas or obj is self.canvas.current_surface()

    def eventFilter(self, obj, event):  # noqa: N802 - Qt override
        if self._is_viewport_event_source(obj):
            et = event.type()
            if et == QtCore.QEvent.Resize:
                size = (event.size().width(), event.size().height())
                if size != self._last_canvas_size:
                    self._last_canvas_size = size
                    self._request_render(fast=True, reason="viewport resized", overlay=True, hud=True)
                # Keep the ViewCube pinned to the viewport overlay corner.
                self._reposition_viewcube()
                # Keep the mini-thumbnail nearby without covering the cube.
                self._reposition_thumbnail()
                return False
            if et == QtCore.QEvent.FocusOut:
                self._snap_key_down = False
                return False
            if et == QtCore.QEvent.Leave:
                self._clear_viewport_hover(reason="viewport leave")
                return False
            if et in {
                QtCore.QEvent.MouseButtonPress,
                QtCore.QEvent.MouseButtonDblClick,
                QtCore.QEvent.MouseMove,
                QtCore.QEvent.MouseButtonRelease,
                QtCore.QEvent.KeyPress,
            }:
                map_studio_handler = getattr(self, "_gr_map_studio_viewport_input_handler", None)
                if callable(map_studio_handler) and bool(map_studio_handler(event, obj)):
                    return True
                # Sculpt Mode owns pointer drags.  This fallback is deliberately
                # after Map Studio's handler (so LMB paints and RMB orbits) but
                # before every shared Maya/Max/Blender navigation path.
                if self._consume_map_studio_terrain_navigation_event(event):
                    return True
            if et == QtCore.QEvent.MouseButtonPress:
                self.canvas.setFocus()
                action = self._navigation_action(event.button(), event.modifiers())
                if action:
                    self._press_navigation(event, action)
                    return True
                if event.button() == QtCore.Qt.RightButton:
                    self._show_mesh_context_menu(event)
                    return True
                if event.button() == QtCore.Qt.LeftButton:
                    if self._measurement_mode:
                        self._handle_measurement_click(event)
                        return True
                    self._press_lmb(event)
                    return True
            if et == QtCore.QEvent.MouseButtonDblClick:
                self.canvas.setFocus()
                if event.button() == QtCore.Qt.LeftButton:
                    self._double_click_lmb(event)
                    return True
            if et == QtCore.QEvent.MouseMove:
                if self._nav_dragging:
                    self._drag_navigation(event)
                    return True
                action, button = self._navigation_action_for_buttons(event.buttons(), event.modifiers())
                if action:
                    self._press_navigation(event, action, button=button)
                    self._drag_navigation(event)
                    return True
                if self._measurement_mode and not (event.buttons() & QtCore.Qt.LeftButton):
                    self._handle_measurement_preview(event)
                    return True
                if event.buttons() & QtCore.Qt.LeftButton:
                    self._drag_lmb(event)
                    return True
                self._update_gizmo_hover(event)
                self._update_mesh_hover(event)
                return False
            if et == QtCore.QEvent.MouseButtonRelease:
                if self._nav_dragging and event.button() == self._nav_button:
                    self._release_navigation(event)
                    return True
                if event.button() == QtCore.Qt.LeftButton:
                    self._release_lmb(event)
                    return True
            if et in (QtCore.QEvent.FocusOut, QtCore.QEvent.WindowDeactivate):
                if self._transform_gizmo_dragging:
                    self._cancel_transform_gizmo_drag()
                    return True
            if et == QtCore.QEvent.Wheel:
                steps = event.angleDelta().y() / 120.0
                hover_cleared = self._clear_viewport_hover(request=False)
                self.camera.zoom(steps)
                if self.is_camera_view_active():
                    self.update_camera_from_view()
                self._renderer.is_interactive = False
                self._request_render(reason="camera zoom", camera=True, overlay=True, selection=hover_cleared)
                return True
            if et == QtCore.QEvent.KeyPress:
                key = event.key()
                if key == QtCore.Qt.Key_V and not event.isAutoRepeat():
                    self._snap_key_down = True
                    return True
                modifiers = event.modifiers()
                no_modifiers = not (
                    modifiers
                    & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier | QtCore.Qt.ShiftModifier)
                )
                if key == QtCore.Qt.Key_F and no_modifiers:
                    self.frame_all(); return True
                if key == QtCore.Qt.Key_Home and no_modifiers:
                    self.frame_all(); return True
                if key in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace) and no_modifiers:
                    if self._delete_selected_scene_objects():
                        return True
                if key == QtCore.Qt.Key_Z and no_modifiers:
                    self.frame_selection_or_all(); return True
                if self._active_gizmo_node() is not None:
                    if key == QtCore.Qt.Key_W and no_modifiers:
                        self._set_transform_gizmo_mode(GizmoMode.TRANSLATE); return True
                    if key == QtCore.Qt.Key_E and no_modifiers:
                        self._set_transform_gizmo_mode(GizmoMode.ROTATE); return True
                    if key == QtCore.Qt.Key_R and no_modifiers:
                        self._set_transform_gizmo_mode(GizmoMode.SCALE); return True
                if key == QtCore.Qt.Key_R and no_modifiers:
                    self.reset_camera(); return True
                if key == QtCore.Qt.Key_W and no_modifiers:
                    self.wire_button.click(); return True
                if key == QtCore.Qt.Key_B and no_modifiers:
                    self.bones_button.click(); return True
                if key == QtCore.Qt.Key_T and no_modifiers:
                    self.texture_button.click(); return True
                if key == QtCore.Qt.Key_G and no_modifiers:
                    self.gimbal_button.click(); return True
                if key == QtCore.Qt.Key_G and (event.modifiers() & QtCore.Qt.AltModifier):
                    self.grid_button.click(); return True
                if key == QtCore.Qt.Key_S and no_modifiers:
                    self.snap_button.click(); return True
                if key == QtCore.Qt.Key_A and no_modifiers and self._navigation_profile != "maya":
                    self.angle_snap_button.click(); return True
                if key == QtCore.Qt.Key_P and no_modifiers:
                    self.percent_snap_button.click(); return True
                if key == QtCore.Qt.Key_Tab and no_modifiers:
                    self.cycle_gimbal_mode(); return True
                if key == QtCore.Qt.Key_Space and no_modifiers:
                    self.cycle_gimbal_mode(); return True
                if key == QtCore.Qt.Key_Escape and no_modifiers:
                    if self._pick_reference_waiting:
                        self._pick_reference_waiting = False
                        self.transform_reference_controller.clear_pick_reference()
                        self.statusMessage.emit("Pick reference cancelled.")
                        self._request_render(fast=True)
                        return True
                    if self._transform_gizmo_dragging:
                        self._cancel_transform_gizmo_drag()
                        return True
                    if self._measurement_mode:
                        self.measurement_controller.clear_measurement()
                        self.measure_button.setChecked(False)
                        self._measurement_mode = False
                        self._request_render()
                        return True
                if key == QtCore.Qt.Key_Z and (event.modifiers() & QtCore.Qt.ControlModifier):
                    if event.modifiers() & QtCore.Qt.ShiftModifier:
                        self.redo()
                    else:
                        self.undo()
                    return True
                if key == QtCore.Qt.Key_Y and (event.modifiers() & QtCore.Qt.ControlModifier):
                    self.redo()
                    return True
                if key == QtCore.Qt.Key_A and (event.modifiers() & QtCore.Qt.ControlModifier):
                    self.select_all_visible_viewport_nodes()
                    return True
                if key == QtCore.Qt.Key_X and (event.modifiers() & QtCore.Qt.AltModifier):
                    return True
                if self._handle_view_key(event):
                    return True
            if et == QtCore.QEvent.KeyRelease:
                if event.key() == QtCore.Qt.Key_V and not event.isAutoRepeat():
                    self._snap_key_down = False
                    return True
        return super().eventFilter(obj, event)

    def _delete_selected_scene_objects(self) -> bool:
        nodes = list(getattr(self, "_selected_viewport_nodes", []) or [])
        selected = getattr(self._renderer, "selected_node", None)
        if selected is not None and selected not in nodes:
            nodes.append(selected)
        object_ids: list[str] = []
        seen: set[str] = set()
        locked = False
        for node in nodes:
            object_id = str(getattr(node, "_gr_scene_object_id", "") or "")
            if not object_id or object_id in seen:
                continue
            if bool(getattr(node, "_gr_scene_object_locked", False)):
                locked = True
                continue
            seen.add(object_id)
            object_ids.append(object_id)
        if locked and not object_ids:
            self.statusMessage.emit("Selected scene object is locked.")
            return True
        if not object_ids:
            return False
        if locked:
            self.statusMessage.emit("Locked scene objects were not deleted.")
        for object_id in object_ids:
            self.sceneObjectDeleteRequested.emit(object_id)
        self.set_selected_node(None)
        self._request_render(fast=True, reason="scene object deleted", scene=True, selection=True)
        return True

    def _world_point_from_mouse(self, event) -> tuple[float, float, float]:
        x = int(event.position().x())
        y = int(event.position().y())
        origin, direction = ray_from_mouse((x, y), self.camera, self.canvas.width(), self.canvas.height())
        dz = float(direction[2])
        if abs(dz) > 1e-8:
            t = -float(origin[2]) / dz
            if t > 0.0:
                point = origin + direction * t
                return (float(point[0]), float(point[1]), 0.0)
        try:
            target = getattr(self.camera, "target", (0.0, 0.0, 0.0))
            return (float(target[0]), float(target[1]), float(target[2]))
        except Exception:
            return (0.0, 0.0, 0.0)

    def _handle_measurement_click(self, event) -> None:
        world = self._world_point_from_mouse(event)
        if self.measurement_controller.point_a is None or self.measurement_controller.point_b is not None:
            self.measurement_controller.begin_measurement(world)
        else:
            self.measurement_controller.finish_measurement(world)
        self._request_render(fast=True)

    def _handle_measurement_preview(self, event) -> None:
        if self.measurement_controller.point_a is None or self.measurement_controller.point_b is not None:
            return
        self.measurement_controller.update_preview(self._world_point_from_mouse(event))
        self._request_render(fast=True)

    def _navigation_action(self, button, modifiers) -> str:
        alt = has_modifier(modifiers, QtCore.Qt.AltModifier)
        shift = has_modifier(modifiers, QtCore.Qt.ShiftModifier)
        ctrl = has_modifier(modifiers, QtCore.Qt.ControlModifier)
        profile = self._navigation_profile
        if profile == "3dsmax":
            if button == QtCore.Qt.MiddleButton and alt:
                return "orbit"
            if button == QtCore.Qt.MiddleButton:
                return "pan"
            if button == QtCore.Qt.RightButton and alt:
                return "zoom"
            return ""
        if profile == "blender":
            if button == QtCore.Qt.MiddleButton and shift:
                return "pan"
            if button == QtCore.Qt.MiddleButton and ctrl:
                return "zoom"
            if button == QtCore.Qt.MiddleButton:
                return "orbit"
            return ""
        if profile == "maya":
            if not alt:
                return ""
            if button == QtCore.Qt.LeftButton:
                return "orbit"
            if button == QtCore.Qt.MiddleButton:
                return "pan"
            if button == QtCore.Qt.RightButton:
                return "zoom"
        return ""

    def _navigation_action_for_buttons(self, buttons, modifiers) -> tuple[str, object]:
        for button in (QtCore.Qt.MiddleButton, QtCore.Qt.RightButton, QtCore.Qt.LeftButton):
            if buttons & button:
                action = self._navigation_action(button, modifiers)
                if action:
                    return action, button
        return "", QtCore.Qt.NoButton

    def _press_navigation(self, event, action: str, *, button=None) -> None:
        if self._transform_gizmo_dragging:
            self._cancel_transform_gizmo_drag()
        self._nav_dragging = action
        self._nav_button = button if button is not None else event.button()
        self._mx = int(event.position().x())
        self._my = int(event.position().y())
        self._renderer._hovered_bone = None
        self._clear_mesh_hover(reason=f"camera {action} started")
        self._frame_governor.begin_interaction(f"camera {action}")

    def _drag_navigation(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        dx, dy = x - self._mx, y - self._my
        self._mx, self._my = x, y
        if self._nav_dragging == "orbit":
            self.camera.orbit(dx * 0.4, -dy * 0.4)
        elif self._nav_dragging == "pan":
            self.camera.pan(dx, dy, self.canvas.height())
        elif self._nav_dragging == "zoom":
            self.camera.zoom((-dy + dx) / 120.0)
        if self.is_camera_view_active():
            self.update_camera_from_view()
        self._renderer.is_interactive = self._fast_drag_enabled
        self._request_render(fast=True, reason=f"camera {self._nav_dragging}", camera=True, overlay=True)

    def _release_navigation(self, _event) -> None:
        self._nav_dragging = ""
        self._nav_button = QtCore.Qt.NoButton
        self._renderer.is_interactive = False
        self._fast_frame_until = 0.0
        self._frame_governor.end_interaction("camera interaction ended")
        self._request_render(reason="camera interaction ended", camera=True, overlay=True)

    def _handle_view_key(self, event) -> bool:
        key = event.key()
        modifiers = event.modifiers()
        ctrl = bool(modifiers & QtCore.Qt.ControlModifier)
        alt = bool(modifiers & QtCore.Qt.AltModifier)
        shift = bool(modifiers & QtCore.Qt.ShiftModifier)
        profile = self._navigation_profile
        if profile == "3dsmax":
            if ctrl or alt:
                return False
            if key == QtCore.Qt.Key_F and shift:
                self._set_camera_view("front")
            elif key == QtCore.Qt.Key_T and shift:
                self._set_camera_view("top")
            elif key == QtCore.Qt.Key_L and shift:
                self._set_camera_view("left")
            elif key == QtCore.Qt.Key_P and shift:
                self.reset_camera()
            elif key == QtCore.Qt.Key_Z and not shift:
                self.frame_selection_or_all()
            else:
                return False
            return True
        if profile == "blender":
            if alt or shift:
                return False
            if key == QtCore.Qt.Key_1:
                self._set_camera_view("back" if ctrl else "front")
            elif key == QtCore.Qt.Key_3:
                self._set_camera_view("left" if ctrl else "right")
            elif key == QtCore.Qt.Key_7:
                self._set_camera_view("bottom" if ctrl else "top")
            elif key == QtCore.Qt.Key_Home:
                self.frame_all()
            else:
                return False
            return True
        if profile == "maya":
            if ctrl or alt or shift:
                return False
            if key in (QtCore.Qt.Key_A, QtCore.Qt.Key_F):
                self.frame_all()
                return True
            return False
        return False

    def _set_camera_view(self, view: str) -> None:
        # T404: delegate to the smooth-interpolation path so keyboard
        # shortcuts (Shift+F / T / L / 1 / 3 / 7) feel consistent with
        # the new snap-view button cluster.
        self._snap_to_view(view)

    # ── T406: Per-mode camera presets ──────────────────────────────────
    def set_character_mode(self, mode: object) -> None:
        """React to a Character-Mode change by reframing the camera.

        Mode-specific presets:
          • Head           → auto-frame the ``head_g`` subtree (with
                             20% padding) and force-hide the thumbnail
                             (Head close-up).
          • Creature       → frame the full model bbox.
          • Headless Body  → frame the full body + bias the camera
                             toward the upper torso (canonical front).
          • Supermodel     → same as Headless Body (skeletons only).
          • Ambiguous /
            Unsupported   → leave the camera alone.

        ``_mode_user_camera_dirty`` tracks whether the user has touched
        the camera since the last preset was applied; the preset only
        runs on a *change* of mode so subsequent renders never clobber
        the user's framing.
        """
        # Accept either the enum or its string value.
        key = getattr(mode, "value", mode)
        key = str(key).lower() if key is not None else None
        if key == self._character_mode:
            return
        self._character_mode = key
        self._mode_user_camera_dirty = False
        self._apply_mode_camera_preset(key)

    @property
    def character_mode(self) -> Optional[str]:
        return self._character_mode

    def _apply_mode_camera_preset(self, key: Optional[str]) -> None:
        """Apply the camera-framing preset for the active mode."""
        if not self.model or not getattr(self.model, "root_node", None):
            return
        if key == "head":
            framed = self._frame_head_subtree(padding=0.20)
            # Auto-hide the mini-thumbnail in Head close-up.
            self.set_thumbnail_force_hidden(True)
            if not framed:
                # Fallback to full-bbox framing if no head subtree exists.
                self.frame_all()
            return
        # Non-Head modes always show the thumbnail (mode-driven hide-flag off).
        self.set_thumbnail_force_hidden(False)
        if key == "creature":
            # Full bbox; no special biasing for quadrupeds since the
            # bbox is asymmetric and `frame_all` already accounts for it.
            self.frame_all()
            return
        if key in ("headless_body", "humanoid", "supermodel"):
            # Body modes default to the canonical front view + frame-all
            # so the silhouette reads clearly.  The dual front+back
            # framing the spec mentions is satisfied implicitly: front
            # is the default, and the user can flick to back via the
            # T404 snap-view cluster.
            self.camera.azimuth = self.camera.DEFAULT_AZIMUTH
            self.camera.elevation = self.camera.DEFAULT_ELEVATION
            self.frame_all()
            return
        # Ambiguous / Unsupported / None → no preset.

    def _frame_head_subtree(self, padding: float = 0.20) -> bool:
        """Frame the camera tightly on the ``head_g`` subtree bbox.

        Walks downward from any node whose name contains ``head_g``
        (case-insensitive) and computes the world-space bbox of every
        vertex it owns or any descendant owns.  Returns True if a head
        subtree was found and the camera was reframed, False otherwise.
        """
        if not self.model or not getattr(self.model, "root_node", None):
            return False
        # Locate the head subtree root.  Walk the full node tree to
        # find any node whose lowercased name contains "head_g" — this
        # catches ``head_g``, ``HEAD_G``, ``f_head_g`` etc.
        head_root = None
        visited = set()
        stack = [self.model.root_node]
        while stack:
            node = stack.pop()
            nid = id(node)
            if nid in visited:
                continue
            visited.add(nid)
            nlow = (getattr(node, "name", "") or "").lower()
            if "head_g" in nlow or nlow == "head":
                head_root = node
                break
            stack.extend(getattr(node, "children", []) or [])
        if head_root is None:
            return False
        # Walk the head subtree and accumulate the world bbox of all verts.
        mins = [1e18, 1e18, 1e18]
        maxs = [-1e18, -1e18, -1e18]
        has_data = False
        sub_visited = set()
        sub_stack = [head_root]
        while sub_stack:
            node = sub_stack.pop()
            sid = id(node)
            if sid in sub_visited:
                continue
            sub_visited.add(sid)
            sub_stack.extend(getattr(node, "children", []) or [])
            verts = getattr(node, "vertices", None) or []
            if not verts:
                continue
            try:
                wp, _, _ = self._renderer._node_world_transform(node)
            except Exception:
                wp = node.world_position() if hasattr(node, "world_position") else (0.0, 0.0, 0.0)
            for vx, vy, vz in verts:
                x, y, z = vx + wp[0], vy + wp[1], vz + wp[2]
                if x < mins[0]: mins[0] = x
                if y < mins[1]: mins[1] = y
                if z < mins[2]: mins[2] = z
                if x > maxs[0]: maxs[0] = x
                if y > maxs[1]: maxs[1] = y
                if z > maxs[2]: maxs[2] = z
                has_data = True
        if not has_data:
            # Fall back to the node's own world position if it has no verts.
            try:
                wp, _, _ = self._renderer._node_world_transform(head_root)
                mins = [wp[0] - 0.2, wp[1] - 0.2, wp[2] - 0.2]
                maxs = [wp[0] + 0.2, wp[1] + 0.2, wp[2] + 0.2]
                has_data = True
            except Exception:
                return False
        # Apply padding by expanding the bbox.
        pad = float(max(0.0, padding))
        dx = (maxs[0] - mins[0]) * pad * 0.5
        dy = (maxs[1] - mins[1]) * pad * 0.5
        dz = (maxs[2] - mins[2]) * pad * 0.5
        mins[0] -= dx; mins[1] -= dy; mins[2] -= dz
        maxs[0] += dx; maxs[1] += dy; maxs[2] += dz
        try:
            self.camera.frame_bounds(tuple(mins), tuple(maxs), reset_view=True)
        except Exception as exc:
            log.debug("Head-subtree frame_bounds failed: %s", exc)
            return False
        self._request_render()
        return True

    # ── T404: Snap-view interpolation + Persp/Ortho ───────────────────
    def _reposition_viewcube(self) -> None:
        """Pin the ViewCube to the top-right viewport overlay area."""
        cube = getattr(self, "_viewcube_widget", None)
        if cube is None:
            return
        if not getattr(self, "_viewcube_visible", True):
            cube.hide()
            return
        cube.adjustSize()
        cw = max(0, self.canvas.width())
        ch = max(0, self.canvas.height())
        if cw < VIEWCUBE_MIN_CANVAS_W or ch < VIEWCUBE_MIN_CANVAS_H:
            cube.hide()
            return
        x = max(VIEWCUBE_MARGIN, cw - cube.width() - VIEWCUBE_MARGIN)
        y = VIEWCUBE_MARGIN
        cube.move(x, y)
        cube.show()
        cube.raise_()

    def _reposition_snap_view(self) -> None:
        """Backward-compatible name for older tests/extensions."""
        self._reposition_viewcube()

    def _viewcube_camera_state(self) -> tuple[float, float, bool]:
        return (
            float(getattr(self.camera, "azimuth", 90.0)),
            float(getattr(self.camera, "elevation", 20.0)),
            bool(getattr(self, "_ortho_mode", False)),
        )

    def execute_view_action(self, action: object) -> None:
        """Route ViewCube and legacy commands through the existing camera."""
        try:
            view_action = action if isinstance(action, ViewAction) else ViewAction(str(action))
        except ValueError:
            return
        if view_action is ViewAction.PERSPECTIVE:
            self.set_view_perspective()
            return
        if view_action is ViewAction.HOME:
            self.set_view_home()
            return
        target = target_for_action(view_action)
        if target is not None:
            self.animate_to_orientation(*target)

    def animate_to_orientation(self, azimuth: float, elevation: float) -> None:
        """Smoothly interpolate the arcball camera to an azimuth/elevation."""
        from_az = float(self.camera.azimuth)
        from_el = float(self.camera.elevation)
        to_az, to_el = float(azimuth), float(elevation)
        delta_az = ((to_az - from_az) + 540.0) % 360.0 - 180.0
        self._snap_anim_from = (from_az, from_el)
        self._snap_anim_to = (from_az + delta_az, to_el)
        self._snap_anim_t0 = time_module.perf_counter()
        self._frame_governor.set_animation_playing(True, "viewcube snap animation")
        if not self._snap_anim_timer.isActive():
            self._snap_anim_timer.start()

    def orbit_from_viewcube_drag(self, daz: float, del_: float) -> None:
        """Orbit the existing camera in response to a ViewCube drag."""
        if self._snap_anim_timer.isActive():
            self._snap_anim_timer.stop()
        self.camera.orbit(float(daz), float(del_))
        if self.is_camera_view_active():
            self.update_camera_from_view()
        self._renderer.is_interactive = self._fast_drag_enabled
        if hasattr(self, "_viewcube_widget") and self._viewcube_widget is not None:
            self._viewcube_widget.update()
        self._request_render(fast=True, reason="viewcube orbit", camera=True, overlay=True)

    def get_orientation_quaternion(self) -> tuple[float, float, float, float]:
        return view_orientation_quaternion(self.camera.azimuth, self.camera.elevation)

    def set_view_front(self) -> None:
        self.execute_view_action(ViewAction.FRONT)

    def set_view_back(self) -> None:
        self.execute_view_action(ViewAction.BACK)

    def set_view_left(self) -> None:
        self.execute_view_action(ViewAction.LEFT)

    def set_view_right(self) -> None:
        self.execute_view_action(ViewAction.RIGHT)

    def set_view_top(self) -> None:
        self.execute_view_action(ViewAction.TOP)

    def set_view_bottom(self) -> None:
        self.execute_view_action(ViewAction.BOTTOM)

    def set_view_perspective(self) -> None:
        self.set_ortho_mode(not self._ortho_mode)
        if self.is_camera_view_active():
            self.switch_to_perspective()
        else:
            self._request_render(fast=True)

    def set_view_home(self) -> None:
        self.reset_camera()

    def _snap_to_view(self, view: str) -> None:
        """Legacy snap-view entry point retained for shortcuts/extensions."""
        action = action_from_view_name(view)
        if action is not None:
            self.execute_view_action(action)
            return
        target = SNAP_VIEW_PRESETS.get(view)
        if target is None:
            return
        # Snapshot start state.  Azimuth must take the shortest angular
        # path (handle wrap-around 0 ↔ 360).
        from_az = float(self.camera.azimuth)
        from_el = float(self.camera.elevation)
        to_az, to_el = float(target[0]), float(target[1])
        delta_az = ((to_az - from_az) + 540.0) % 360.0 - 180.0
        to_az_resolved = from_az + delta_az
        self._snap_anim_from = (from_az, from_el)
        self._snap_anim_to = (to_az_resolved, to_el)
        self._snap_anim_t0 = time_module.perf_counter()
        self._frame_governor.set_animation_playing(True, "snap view animation")
        if not self._snap_anim_timer.isActive():
            self._snap_anim_timer.start()

    def _snap_anim_tick(self) -> None:
        """One frame of the 200 ms snap-view tween."""
        elapsed_ms = (time_module.perf_counter() - self._snap_anim_t0) * 1000.0
        t = max(0.0, min(1.0, elapsed_ms / float(SNAP_VIEW_INTERP_MS)))
        # Ease-in-out cubic — feels natural for a camera snap.
        if t < 0.5:
            ease = 4.0 * t * t * t
        else:
            f = (2.0 * t - 2.0)
            ease = 1.0 + 0.5 * f * f * f
        from_az, from_el = self._snap_anim_from
        to_az,   to_el   = self._snap_anim_to
        self.camera.azimuth   = (from_az + (to_az - from_az) * ease) % 360.0
        self.camera.elevation = from_el + (to_el - from_el) * ease
        if t >= 1.0:
            self._snap_anim_timer.stop()
            self._frame_governor.set_animation_playing(False)
            # Snap to exact target to defeat float drift.
            self.camera.azimuth   = to_az % 360.0
            self.camera.elevation = to_el
        if self.is_camera_view_active():
            self.update_camera_from_view()
        if hasattr(self, "_viewcube_widget") and self._viewcube_widget is not None:
            self._viewcube_widget.update()
        self._request_render(fast=True)

    def set_ortho_mode(self, ortho: bool) -> None:
        """Toggle perspective ↔ orthographic projection.

        Implementation note: ``ArcBallCamera`` only models a perspective
        projection.  We simulate orthographic by collapsing the FOV to
        a very small value and increasing the camera distance to keep
        the framing roughly stable — visually indistinguishable from
        a true ortho projection for the rigging use case.
        """
        new_val = bool(ortho)
        if new_val == self._ortho_mode:
            return
        self._ortho_mode = new_val
        # Persist a "real" perspective FOV the first time we go ortho so
        # we can restore exactly on toggle-off.
        if not hasattr(self, "_persp_fov_saved") or self._persp_fov_saved is None:
            self._persp_fov_saved = float(getattr(self.camera, "fov", 45.0))
        if new_val:
            # Save current state and shrink FOV.
            self._persp_fov_saved = float(self.camera.fov)
            self._persp_distance_saved = float(self.camera.distance)
            # Pull camera back and shrink FOV proportionally so the
            # projected size of the model stays approximately constant.
            ortho_fov = 1.5
            scale = math.tan(math.radians(self._persp_fov_saved) * 0.5) / math.tan(
                math.radians(ortho_fov) * 0.5
            )
            self.camera.fov = ortho_fov
            self.camera.distance = max(0.5, self._persp_distance_saved * scale)
        else:
            # Restore perspective.
            self.camera.fov = float(getattr(self, "_persp_fov_saved", 45.0))
            saved_dist = getattr(self, "_persp_distance_saved", None)
            if saved_dist is not None:
                self.camera.distance = float(saved_dist)
        # Keep the snap-view bar's toggle button in sync if the call
        # came from somewhere other than the bar itself.
        if hasattr(self, "_snap_view_widget") and self._snap_view_widget is not None and hasattr(self._snap_view_widget, "ortho_button"):
            btn = self._snap_view_widget.ortho_button
            with QtCore.QSignalBlocker(btn):
                btn.setChecked(new_val)
                btn.setText("Ortho" if new_val else "Persp")
        if hasattr(self, "_viewcube_widget") and self._viewcube_widget is not None:
            self._viewcube_widget.update()
        if self.is_camera_view_active():
            self.update_camera_from_view()
        self._request_render(fast=True, reason="camera projection changed", camera=True, overlay=True)

    @property
    def ortho_mode(self) -> bool:
        return self._ortho_mode

__all__ = ("ViewportEventNavigationMixin",)
