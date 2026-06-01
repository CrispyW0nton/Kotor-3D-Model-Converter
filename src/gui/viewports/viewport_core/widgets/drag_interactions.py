"""ViewportDragInteractions methods for the Qt viewport widget."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportDragInteractionsMixin:
    def _begin_transform_gizmo_drag(self, x: int, y: int) -> bool:
        node = self._active_gizmo_node()
        if not self._ensure_renderer_gimbal_state() or node is None:
            return False
        if bool(getattr(node, "_gr_camera_locked", False)):
            return False
        if bool(getattr(node, "_gr_scene_object_locked", False)):
            self.statusMessage.emit("Selected object is locked.")
            return False
        try:
            wp = self._gizmo_world_position(node)
            setattr(node, "_gr_gizmo_world_position", wp)
        except Exception:
            pass
        self._sync_transform_reference_for_node(node)
        self._transform_gizmo.set_selected_object(node)
        handle = self._transform_gizmo.hit_test((x, y), self.camera)
        if not handle:
            return False
        self._transform_gizmo_dragging = True
        self._gimbal_dragging = False
        self._clear_mesh_hover(reason="gizmo drag started")
        self._transform_gizmo.begin_drag(handle, (x, y), self.camera)
        self._renderer.is_interactive = True
        self._frame_governor.begin_interaction("gizmo drag")
        self._request_render(fast=True, reason="gizmo drag started", gizmo=True, overlay=True)
        return True

    def _cancel_transform_gizmo_drag(self) -> None:
        self._transform_gizmo.cancel_drag()
        self._transform_gizmo_dragging = False
        self._renderer.is_interactive = False
        self._renderer._wt_cache.clear()
        self._frame_governor.end_interaction("gizmo drag cancelled")
        self._request_render(reason="gizmo drag cancelled", gizmo=True, overlay=True)

    def _commit_transform_gizmo_drag(self) -> None:
        before, after, node = self._transform_gizmo.end_drag()
        self._transform_gizmo_dragging = False
        self._renderer.is_interactive = False
        self._frame_governor.end_interaction("gizmo drag ended")
        self._renderer._wt_cache.clear()
        if node is not None and before is not None and after is not None:
            self._commit_node_transform(
                node,
                before.position,
                before.rotation,
                after.position,
                after.rotation,
                f"Gizmo {self._transform_gizmo.mode.value.title()}",
                before_vertices=before.vertices,
                after_vertices=after.vertices,
                before_scale=before.scale,
                after_scale=after.scale,
                before_pivot_world=before.pivot_world,
                after_pivot_world=after.pivot_world,
                before_pivot_rotation=before.pivot_rotation,
                after_pivot_rotation=after.pivot_rotation,
            )
            self._notify_node_moved(node)
        self._request_render(reason="gizmo drag ended", gizmo=True, selection=True, overlay=True)

    def _press_lmb(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        self._mx = self._press_x = x
        self._my = self._press_y = y
        self._is_dragging = False
        self._gimbal_dragging = False
        self._joint_dragging = False
        self._joint_drag_node = None
        self._joint_drag_mirror_node = None
        self._joint_drag_nodes = []
        self._joint_drag_mirror_nodes = []
        self._joint_drag_start_positions = {}
        self._joint_marquee_selecting = False
        self._joint_marquee_start = (x, y)
        self._joint_marquee_current = (x, y)
        self._mesh_box_start = None
        self._mesh_box_selecting = False
        self._marquee_base_selection = self._current_viewport_selection_for_mode(
            getattr(self, "_viewport_selection_mode", "object")
        )
        if hasattr(self, "_selection_rubber_band"):
            self._selection_rubber_band.hide()

        if self._begin_transform_gizmo_drag(x, y):
            return

        # ── T402: Prefer joint-dot click over plain bone hit-test ──────
        # The dots are painted on top of the bone markers, so a click
        # within their hit-radius should select the same joint AND arm
        # a translate-drag.  The drag activates lazily on cursor motion
        # past `_drag_threshold` so simple clicks still behave as
        # selection-only (matching AccuRig).
        if self._renderer.show_bones and self._joint_dot_enabled:
            joint_node = self._joint_dot_hit_test(x, y)
            if joint_node is not None:
                modifiers = event.modifiers()
                if modifiers & (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier):
                    self._toggle_selected_joint_node(joint_node)
                    self._renderer._hovered_bone = joint_node
                    self._request_render()
                    return
                self._joint_drag_node = joint_node
                if len(self._selected_joint_nodes) > 1 and any(n is joint_node for n in self._selected_joint_nodes):
                    self._joint_drag_nodes = list(self._selected_joint_nodes)
                    self._joint_drag_mirror_node = None
                else:
                    self._joint_drag_nodes = [joint_node]
                selected_ids = {id(n) for n in self._joint_drag_nodes}
                self._joint_drag_mirror_nodes = []
                if self._joint_symmetry_enabled:
                    for drag_node in self._joint_drag_nodes:
                        partner = self._joint_mirror_partner(drag_node)
                        if partner is not None and id(partner) not in selected_ids:
                            selected_ids.add(id(partner))
                            self._joint_drag_mirror_nodes.append(partner)
                self._joint_drag_mirror_node = (
                    self._joint_drag_mirror_nodes[0]
                    if self._joint_drag_mirror_nodes else None
                )
                self._joint_drag_start_screen = (x, y)
                try:
                    self._joint_drag_start_pos = tuple(joint_node.position)
                except Exception:
                    self._joint_drag_start_pos = (0.0, 0.0, 0.0)
                self._joint_drag_start_positions = {}
                for drag_node in self._joint_drag_nodes:
                    try:
                        self._joint_drag_start_positions[id(drag_node)] = tuple(drag_node.position)
                    except Exception:
                        self._joint_drag_start_positions[id(drag_node)] = (0.0, 0.0, 0.0)
                if self._joint_drag_mirror_node is not None:
                    for mirror_node in self._joint_drag_mirror_nodes:
                        try:
                            self._joint_drag_start_positions[id(mirror_node)] = tuple(
                                mirror_node.position
                            )
                        except Exception:
                            self._joint_drag_start_positions[id(mirror_node)] = (0.0, 0.0, 0.0)
                    self._joint_drag_mirror_start_pos = self._joint_drag_start_positions.get(
                        id(self._joint_drag_mirror_node),
                        (0.0, 0.0, 0.0),
                    )
                else:
                    self._joint_drag_mirror_start_pos = (0.0, 0.0, 0.0)
                # Cache the screen→world conversion factor at the joint's
                # depth so the drag-translate math feels consistent
                # regardless of camera distance.
                try:
                    w = self.canvas.width() or 800
                    h = self.canvas.height() or 600
                    if self._is_external_skeleton_node(joint_node):
                        wp = self._external_overlay_world_position(joint_node)
                    else:
                        wp, _, _ = self._renderer._node_world_transform(joint_node)
                    proj = self._renderer._proj(*wp, w, h)
                    dist = max(0.5, proj[2] if proj else 1.0)
                    self._joint_drag_world_per_px = (
                        2.0 * dist * math.tan(math.radians(self.camera.fov) * 0.5)
                    ) / max(h, 1)
                except Exception:
                    self._joint_drag_world_per_px = 0.01
                self._renderer._hovered_bone = joint_node
                self._request_render()
                return

        if self._renderer.show_bones:
            node = self._renderer.hit_test_bone(x, y)
            if node:
                self._renderer._hovered_bone = node
                self._request_render()
                return

        if self._renderer.show_bones and self._joint_dot_enabled:
            self._joint_marquee_selecting = True
            self._joint_marquee_start = (x, y)
            self._joint_marquee_current = (x, y)
            self._request_render()
            return
        self._mesh_box_start = QtCore.QPoint(x, y)

    def _drag_lmb(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        if self._transform_gizmo_dragging:
            self._transform_gizmo.drag((x, y), self.camera, self.canvas.height())
            self._request_render(fast=True, reason="gizmo drag", scene=True, gizmo=True)
            return
        if self._gimbal_dragging and self._renderer.selected_node:
            if (
                self._snap_key_down
                and self._renderer.gimbal_mode == 1
                and self._selection_targets_external_skeleton(
                    self._selected_joint_nodes or [self._renderer.selected_node]
                )
                and self._snap_selected_external_bones_to_imported_at_cursor(x, y)
            ):
                self._request_render(fast=True)
                return
            self._apply_gimbal_drag(x, y)
            self._notify_node_moved(self._renderer.selected_node)
            self._request_render(fast=True)
            return

        # ── T402: Joint-dot drag translation ────────────────────────────
        # Activate joint drag the moment the cursor leaves the click slop
        # circle, then keep translating the primary node (and its mirror
        # partner, if symmetry is on) per screen→world delta.
        if self._joint_drag_node is not None:
            sx0, sy0 = self._joint_drag_start_screen
            if not self._joint_dragging:
                if (
                    abs(x - sx0) > self._drag_threshold
                    or abs(y - sy0) > self._drag_threshold
                ):
                    self._joint_dragging = True
                    self._renderer.is_interactive = True
            if self._joint_dragging:
                self._apply_joint_drag(x, y)
                self._request_render(fast=True)
            return

        if self._joint_marquee_selecting:
            self._joint_marquee_current = (x, y)
            if not self._is_dragging:
                if abs(x - self._press_x) > self._drag_threshold or abs(y - self._press_y) > self._drag_threshold:
                    self._is_dragging = True
            self._request_render(fast=True)
            return

        if not self._is_dragging:
            if abs(x - self._press_x) > self._drag_threshold or abs(y - self._press_y) > self._drag_threshold:
                self._is_dragging = True
                self._renderer._hovered_bone = None
        if self._is_dragging:
            self._mx, self._my = x, y
            if self._mesh_box_start is not None:
                self._mesh_box_selecting = True
                rect = QtCore.QRect(self._mesh_box_start, QtCore.QPoint(x, y)).normalized()
                self._selection_rubber_band.setGeometry(rect)
                self._selection_rubber_band.show()
                self._apply_marquee_selection(rect, event.modifiers(), live=True)

    def _release_lmb(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        if self._transform_gizmo_dragging:
            self._commit_transform_gizmo_drag()
            return
        if self._gimbal_dragging:
            self._gimbal_dragging = False
            self._renderer.gimbal_active_axis = None
            self._renderer.is_interactive = False
            self._renderer._wt_cache.clear()
            node = self._renderer.selected_node
            if node is not None:
                if (
                    not self._is_selected_model_root(node)
                    and len(self._selected_joint_nodes) > 1
                    and any(n is node for n in self._selected_joint_nodes)
                    and self._renderer.gimbal_mode == 1
                ):
                    for sel_node in self._selected_joint_nodes:
                        before_pos = self._gimbal_joint_start_positions.get(
                            id(sel_node),
                            tuple(sel_node.position),
                        )
                        self._commit_node_transform(
                            sel_node,
                            before_pos,
                            tuple(sel_node.rotation),
                            tuple(sel_node.position),
                            tuple(sel_node.rotation),
                            "Gimbal Multi-Joint Translate",
                        )
                        self._notify_node_moved(sel_node)
                    for mirror_node in self._gimbal_joint_mirror_nodes:
                        before_pos = self._gimbal_joint_start_positions.get(
                            id(mirror_node),
                            tuple(mirror_node.position),
                        )
                        self._commit_node_transform(
                            mirror_node,
                            before_pos,
                            tuple(mirror_node.rotation),
                            tuple(mirror_node.position),
                            tuple(mirror_node.rotation),
                            "Gimbal Multi-Joint Translate (mirror)",
                        )
                        self._notify_node_moved(mirror_node)
                elif not self._is_selected_model_root(node):
                    self._commit_node_transform(
                        node,
                        self._gimbal_node_start_pos,
                        self._gimbal_node_start_rot,
                        tuple(node.position),
                        tuple(node.rotation),
                        "Gimbal Transform",
                    )
                    self._notify_node_moved(node)
                    for mirror_node in self._gimbal_joint_mirror_nodes:
                        before_pos = self._gimbal_joint_start_positions.get(
                            id(mirror_node),
                            tuple(mirror_node.position),
                        )
                        self._commit_node_transform(
                            mirror_node,
                            before_pos,
                            tuple(mirror_node.rotation),
                            tuple(mirror_node.position),
                            tuple(mirror_node.rotation),
                            "Gimbal Transform (mirror)",
                        )
                        self._notify_node_moved(mirror_node)
            self._request_render()
            return

        # ── T402: Joint-drag release ─────────────────────────────────────
        # Two modes:
        #   • If the user dragged → commit the translation (and its mirror)
        #     onto the undo stack with one "Joint Translate" entry, then
        #     keep the joint selected as the active node.
        #   • If the user just clicked (no drag) → treat as selection-only.
        if self._joint_drag_node is not None:
            joint = self._joint_drag_node
            mirror = self._joint_drag_mirror_node
            mirror_nodes = list(self._joint_drag_mirror_nodes)
            was_dragging = self._joint_dragging
            self._joint_dragging = False
            self._renderer.is_interactive = False
            self._renderer._wt_cache.clear()
            if was_dragging:
                try:
                    for moved in self._joint_drag_nodes or [joint]:
                        start_pos = self._joint_drag_start_positions.get(
                            id(moved),
                            self._joint_drag_start_pos if moved is joint else tuple(moved.position),
                        )
                        self._commit_node_transform(
                            moved,
                            start_pos,
                            tuple(moved.rotation),
                            tuple(moved.position),
                            tuple(moved.rotation),
                            "Joint Translate",
                        )
                        self._notify_node_moved(moved)
                    for mirror in mirror_nodes:
                        mirror_start = self._joint_drag_start_positions.get(
                            id(mirror),
                            self._joint_drag_mirror_start_pos,
                        )
                        self._commit_node_transform(
                            mirror,
                            mirror_start,
                            tuple(mirror.rotation),
                            tuple(mirror.position),
                            tuple(mirror.rotation),
                            "Joint Translate (mirror)",
                        )
                        self._notify_node_moved(mirror)
                except Exception as exc:
                    log.debug("Joint-drag commit failed: %s", exc)
            self._joint_drag_node = None
            self._joint_drag_mirror_node = None
            self._joint_drag_nodes = []
            self._joint_drag_mirror_nodes = []
            self._joint_drag_start_positions = {}
            # Click-or-drag: always finish by selecting the joint so the
            # inspector reflects the user's intent.
            if was_dragging and self._selected_joint_nodes:
                self._set_selected_joint_nodes(self._selected_joint_nodes, primary=joint)
            else:
                self.set_selected_node(joint)
            if self.on_bone_selected:
                self.on_bone_selected(joint)
            self._renderer._hovered_bone = None
            self._request_render()
            return

        if self._joint_marquee_selecting:
            self._joint_marquee_selecting = False
            self._renderer.is_interactive = False
            if self._is_dragging:
                nodes = self._joint_nodes_in_rect(
                    self._joint_marquee_start[0],
                    self._joint_marquee_start[1],
                    x,
                    y,
                )
                self._set_selected_joint_nodes(nodes)
                if self.on_bone_selected:
                    self.on_bone_selected(self._renderer.selected_node)
                self._is_dragging = False
                self._request_render()
                return
            self._request_render()

        self._renderer._hovered_bone = None
        self._renderer.is_interactive = False
        if self._is_dragging:
            if self._mesh_box_selecting and self._mesh_box_start is not None:
                rect = QtCore.QRect(self._mesh_box_start, QtCore.QPoint(x, y)).normalized()
                self._selection_rubber_band.hide()
                self._apply_marquee_selection(rect, event.modifiers(), live=False)
                self._mesh_box_start = None
                self._mesh_box_selecting = False
                self._marquee_base_selection = []
                self._is_dragging = False
                return
            if hasattr(self, "_selection_rubber_band"):
                self._selection_rubber_band.hide()
            self._mesh_box_start = None
            self._mesh_box_selecting = False
            self._marquee_base_selection = []
            self._is_dragging = False
            self._request_render()
            return

        if self._pick_reference_waiting:
            target = self._pick_reference_hit_test(x, y)
            if target is not None:
                self.transform_reference_controller.resolve_pick_reference(target)
                self._pick_reference_waiting = False
                label = str(getattr(target, "_gr_scene_object_name", getattr(target, "name", "Object")) or "Object")
                if hasattr(self, "axis_mode_control"):
                    self.axis_mode_control.set_axis_mode(AxisMode.PICK, label=f"Pick: {label[:24]}")
                self.statusMessage.emit(f"Transform reference picked: {label}")
                self._request_render(fast=True)
            else:
                self.statusMessage.emit("Pick an object to use as transform reference.")
            return

        selection_mode = str(getattr(self, "_viewport_selection_mode", "object") or "object").lower()

        if selection_mode == "helpers":
            helper_node = self._helper_hit_test(x, y)
            if helper_node is not None:
                self.set_selected_node(helper_node)
                if self.on_bone_selected:
                    self.on_bone_selected(None)
                return
            self.set_selected_node(None)
            if self.on_bone_selected:
                self.on_bone_selected(None)
            return

        if selection_mode == "lights":
            light_node = self._light_hit_test(x, y)
            if light_node is not None:
                self.set_selected_node(light_node)
                if self.on_bone_selected:
                    self.on_bone_selected(None)
                return
            self.set_selected_node(None)
            if self.on_bone_selected:
                self.on_bone_selected(None)
            return

        if selection_mode == "cameras":
            camera_node = self._camera_hit_test(x, y)
            if camera_node is not None:
                if event.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier):
                    camera = self.camera_manager.find_by_original(camera_node)
                    if camera is not None:
                        self.camera_manager.select_camera(camera.id, additive=True)
                        self.cameraSelectionChanged.emit(camera_node)
                self.set_selected_node(camera_node)
                if self.on_bone_selected:
                    self.on_bone_selected(None)
                return
            self.set_selected_node(None)
            if self.on_bone_selected:
                self.on_bone_selected(None)
            return

        if selection_mode == "mesh":
            if self.mesh_selection_state.mode is not MeshSelectionMode.OBJECT:
                if self._apply_mesh_subobject_hit(
                    self._mesh_subobject_hit_test(x, y),
                    event.modifiers(),
                ):
                    if self.on_bone_selected:
                        self.on_bone_selected(None)
                    return
            mesh_hit = self._mesh_hit_test_detail(x, y, allow_gpu=False)
            if mesh_hit is not None:
                mesh_node, face_bounds = mesh_hit
                self.set_selected_node(mesh_node, orbit_bounds=face_bounds)
                if self.on_bone_selected:
                    self.on_bone_selected(None)
                return
            self.set_selected_node(None)
            if self.on_bone_selected:
                self.on_bone_selected(None)
            return

        if self._renderer.show_bones:
            # T402: joint-dot hit-test takes priority over the underlying
            # bone hit-test so clicks on a dot always select the right node.
            node = (
                self._joint_dot_hit_test(x, y)
                if self._joint_dot_enabled
                else None
            )
            if node is None:
                node = self._renderer.hit_test_bone(x, y)
            if node:
                self.set_selected_node(node)
                if self.on_bone_selected:
                    self.on_bone_selected(node)
                return
        if self.mesh_selection_state.mode is not MeshSelectionMode.OBJECT:
            if self._apply_mesh_subobject_hit(
                self._mesh_subobject_hit_test(x, y),
                event.modifiers(),
            ):
                if self.on_bone_selected:
                    self.on_bone_selected(None)
                return
        mesh_hit = self._mesh_hit_test_detail(x, y, allow_gpu=False)
        if mesh_hit is not None:
            mesh_node, face_bounds = mesh_hit
            self.set_selected_node(mesh_node, orbit_bounds=face_bounds)
            if self.on_bone_selected:
                self.on_bone_selected(None)
            return
        camera_node = self._camera_hit_test(x, y)
        if camera_node is not None:
            if event.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier):
                camera = self.camera_manager.find_by_original(camera_node)
                if camera is not None:
                    self.camera_manager.select_camera(camera.id, additive=True)
                    self.cameraSelectionChanged.emit(camera_node)
            self.set_selected_node(camera_node)
            if self.on_bone_selected:
                self.on_bone_selected(None)
            return
        light_node = self._light_hit_test(x, y)
        if light_node is not None:
            self.set_selected_node(light_node)
            if self.on_bone_selected:
                self.on_bone_selected(None)
            return
        helper_node = self._helper_hit_test(x, y)
        if helper_node is not None:
            self.set_selected_node(helper_node)
            if self.on_bone_selected:
                self.on_bone_selected(None)
            return
        self.set_selected_node(None)
        if self.on_bone_selected:
            self.on_bone_selected(None)

    def _press_pan(self, event) -> None:
        self._pan_dragging = True
        self._mx = int(event.position().x())
        self._my = int(event.position().y())

    def _drag_pan(self, event) -> None:
        if not self._pan_dragging:
            return
        x, y = int(event.position().x()), int(event.position().y())
        dx, dy = x - self._mx, y - self._my
        self._mx, self._my = x, y
        self.camera.pan(dx, dy, self.canvas.height())
        self._request_render(fast=True)

    def _release_pan(self, event) -> None:
        self._pan_dragging = False
        self._renderer.is_interactive = False
        self._request_render()

    # ── T402: Joint-drag translation math ──────────────────────────────
    def _apply_joint_drag(self, mx: int, my: int) -> None:
        """Translate the drag-target joint (and its mirror) by the
        screen-delta from the press point.

        Movement is performed in the camera's right/up plane (the
        standard 3-axis-free-translate behaviour for joint-dot drags
        in AccuRig).  Depth along the view forward is left untouched —
        joint dots are inherently a 2D screen-space affordance.

        Symmetry: when ``self._joint_symmetry_enabled`` is True and a
        MIRROR_PAIRS partner was identified at press-time, the partner
        joint receives the same delta with the X component negated, so
        L↔R parity is preserved while editing.
        """
        node = self._joint_drag_node
        if node is None:
            return
        try:
            sx0, sy0 = self._joint_drag_start_screen
            dx_screen = mx - sx0
            dy_screen = my - sy0
            wpp = float(self._joint_drag_world_per_px)
            # Camera basis at press time (right/up of view matrix).
            try:
                right, up, _fwd, _eye = self.camera._view_matrix()
            except Exception:
                # Defensive fallback if the camera matrix isn't available
                right = (1.0, 0.0, 0.0)
                up = (0.0, 1.0, 0.0)
            # Screen-space delta → world-space vector.
            #   +x screen drag → +right
            #   +y screen drag → -up   (Qt y axis points down)
            dwx = (dx_screen * right[0] + (-dy_screen) * up[0]) * wpp
            dwy = (dx_screen * right[1] + (-dy_screen) * up[1]) * wpp
            dwz = (dx_screen * right[2] + (-dy_screen) * up[2]) * wpp
            drag_nodes = self._joint_drag_nodes or [node]
            for drag_node in drag_nodes:
                delta = (
                    self._external_world_delta_to_local((dwx, dwy, dwz))
                    if self._is_external_skeleton_node(drag_node)
                    else (dwx, dwy, dwz)
                )
                sp = self._joint_drag_start_positions.get(
                    id(drag_node),
                    self._joint_drag_start_pos if drag_node is node else tuple(drag_node.position),
                )
                drag_node.position = (sp[0] + delta[0], sp[1] + delta[1], sp[2] + delta[2])
                self._evict_transform_cache(drag_node)

            mirror_nodes = list(self._joint_drag_mirror_nodes)
            for mirror in mirror_nodes:
                msp = self._joint_drag_start_positions.get(
                    id(mirror),
                    self._joint_drag_mirror_start_pos,
                )
                mdx, mdy, mdz = (
                    self._external_world_delta_to_local((dwx, dwy, dwz))
                    if self._is_external_skeleton_node(mirror)
                    else (dwx, dwy, dwz)
                )
                # Mirror across the X axis: negate the X component of the
                # translation delta so the partner moves symmetrically.
                mirror.position = (msp[0] - mdx, msp[1] + mdy, msp[2] + mdz)
                self._evict_transform_cache(mirror)
        except Exception as exc:
            log.debug("Joint-drag translation failed: %s", exc)

    def _apply_gimbal_drag(self, mx: int, my: int) -> None:
        node = self._renderer.selected_node
        if not node:
            return
        sx0, sy0 = self._gimbal_drag_start
        dx_screen = mx - sx0
        dy_screen = my - sy0
        w = self.canvas.width() or 800
        h = self.canvas.height() or 600
        if self._is_external_skeleton_node(node):
            wp = self._external_overlay_world_position(node)
        else:
            wp, _, _ = self._renderer._node_world_transform(node)
        proj = self._renderer._proj(*wp, w, h)
        dist = max(0.5, proj[2] if proj else 1.0)
        world_per_px = (2.0 * dist * math.tan(math.radians(self.camera.fov) * 0.5)) / max(h, 1)
        axis = self._gimbal_axis
        start = self._gimbal_node_start_pos
        if self._is_selected_model_root(node):
            self._apply_model_gimbal_drag(
                dx_screen,
                dy_screen,
                world_per_px,
                axis,
                wp,
            )
            return

        if self._renderer.gimbal_mode == 1:
            def axis_delta(axis_name: str):
                return self._projected_axis_delta(
                    axis_name,
                    wp,
                    dx_screen,
                    dy_screen,
                    world_per_px,
                )

            if len(axis) == 1:
                d = axis_delta(axis)
            else:
                d1 = axis_delta(axis[0])
                d2 = axis_delta(axis[1])
                d = (d1[0] + d2[0], d1[1] + d2[1], d1[2] + d2[2])
            if any(n is node for n in self._selected_joint_nodes) and len(self._selected_joint_nodes) > 1:
                for sel_node in self._selected_joint_nodes:
                    sp = self._gimbal_joint_start_positions.get(id(sel_node), tuple(sel_node.position))
                    delta = (
                        self._external_world_delta_to_local(d)
                        if self._is_external_skeleton_node(sel_node)
                        else d
                    )
                    sel_node.position = (sp[0] + delta[0], sp[1] + delta[1], sp[2] + delta[2])
                    self._evict_transform_cache(sel_node)
            else:
                delta = self._external_world_delta_to_local(d) if self._is_external_skeleton_node(node) else d
                node.position = (start[0] + delta[0], start[1] + delta[1], start[2] + delta[2])
            for mirror_node in self._gimbal_joint_mirror_nodes:
                sp = self._gimbal_joint_start_positions.get(id(mirror_node), tuple(mirror_node.position))
                delta = (
                    self._external_world_delta_to_local(d)
                    if self._is_external_skeleton_node(mirror_node)
                    else d
                )
                mirror_node.position = (sp[0] - delta[0], sp[1] + delta[1], sp[2] + delta[2])
                self._evict_transform_cache(mirror_node)
        elif self._renderer.gimbal_mode == 2:
            angle = dx_screen * 0.01
            angle = self.angle_snap.snap_radians(angle)
            ha = angle * 0.5
            c, s = math.cos(ha), math.sin(ha)
            rq = {"X": (s, 0.0, 0.0, c), "Y": (0.0, s, 0.0, c)}.get(axis, (0.0, 0.0, s, c))
            ax, ay, az, aw = rq
            bx, by, bz, bw = self._gimbal_node_start_rot
            new_rot = (
                aw * bx + ax * bw + ay * bz - az * by,
                aw * by - ax * bz + ay * bw + az * bx,
                aw * bz + ax * by - ay * bx + az * bw,
                aw * bw - ax * bx - ay * by - az * bz,
            )
            ll = math.sqrt(sum(v * v for v in new_rot))
            if ll > 1e-9:
                node.rotation = tuple(v / ll for v in new_rot)

        self._evict_transform_cache(node)

    def _is_selected_model_root(self, node) -> bool:
        return bool(
            self.model is not None
            and (
                node is getattr(self.model, "root_node", None)
                or bool(getattr(node, "_gr_scene_object_root", False))
            )
        )

    def _model_gimbal_axis_delta(
        self,
        axis_name: str,
        dx_screen: float,
        dy_screen: float,
        world_per_px: float,
        origin_world: tuple[float, float, float] | None = None,
    ) -> tuple[float, float, float]:
        if origin_world is not None:
            return self._projected_axis_delta(
                axis_name,
                origin_world,
                dx_screen,
                dy_screen,
                world_per_px,
            )
        right, up, _fwd, _eye = self.camera._view_matrix()
        w_dir = self._gimbal_world_axis(axis_name)
        sc_x = w_dir[0] * right[0] + w_dir[1] * right[1] + w_dir[2] * right[2]
        sc_y = w_dir[0] * up[0] + w_dir[1] * up[1] + w_dir[2] * up[2]
        ll = math.sqrt(sc_x * sc_x + sc_y * sc_y)
        if ll < 1e-6:
            return (0.0, 0.0, 0.0)
        delta = ((dx_screen * sc_x + (-dy_screen) * sc_y) / ll) * world_per_px
        return (delta * w_dir[0], delta * w_dir[1], delta * w_dir[2])

    def _apply_model_gimbal_drag(
        self,
        dx_screen: float,
        dy_screen: float,
        world_per_px: float,
        axis: str,
        origin_world: tuple[float, float, float] | None = None,
    ) -> None:
        if self.model is None:
            return
        mode = int(getattr(self._renderer, "gimbal_mode", 1) or 1)
        translation_delta = (0.0, 0.0, 0.0)
        rotation_delta = (0.0, 0.0, 0.0)
        scale_delta = 1.0

        if mode == 1:
            if len(axis) == 1:
                target = self._model_gimbal_axis_delta(
                    axis,
                    dx_screen,
                    dy_screen,
                    world_per_px,
                    origin_world,
                )
            else:
                d1 = self._model_gimbal_axis_delta(
                    axis[0],
                    dx_screen,
                    dy_screen,
                    world_per_px,
                    origin_world,
                )
                d2 = self._model_gimbal_axis_delta(
                    axis[1],
                    dx_screen,
                    dy_screen,
                    world_per_px,
                    origin_world,
                )
                target = (d1[0] + d2[0], d1[1] + d2[1], d1[2] + d2[2])
            prev = self._gimbal_model_applied_translation
            translation_delta = tuple(target[i] - prev[i] for i in range(3))
            self._gimbal_model_applied_translation = target
        elif mode == 2:
            angle = dx_screen * 0.01
            if QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier:
                deg = round(math.degrees(angle) / 10.0) * 10.0
                angle = math.radians(deg)
            delta_angle = angle - float(self._gimbal_model_applied_rotation or 0.0)
            self._gimbal_model_applied_rotation = angle
            deg_delta = math.degrees(delta_angle)
            if axis == "X":
                rotation_delta = (deg_delta, 0.0, 0.0)
            elif axis == "Y":
                rotation_delta = (0.0, deg_delta, 0.0)
            else:
                rotation_delta = (0.0, 0.0, deg_delta)
        elif mode == 3:
            target_scale = max(0.01, min(100.0, math.exp(dx_screen * 0.006)))
            prev_scale = max(0.01, float(self._gimbal_model_applied_scale or 1.0))
            scale_delta = target_scale / prev_scale
            self._gimbal_model_applied_scale = target_scale

        if (
            abs(scale_delta - 1.0) < 1e-6
            and all(abs(v) < 1e-6 for v in translation_delta)
            and all(abs(v) < 1e-6 for v in rotation_delta)
        ):
            return
        try:
            try:
                from core.characters import headless_body_workflow as _wf
            except ImportError:                              # pragma: no cover
                from src.core.characters import headless_body_workflow as _wf  # type: ignore
            result = _wf.apply_external_model_fit_adjustment(
                self.model,
                rotation_delta_degrees=rotation_delta,
                scale_delta=scale_delta,
                translation_delta=translation_delta,
            )
            if bool(result.get("ok")):
                self.refresh_model_geometry()
                root_node = getattr(self.model, "root_node", None)
                if root_node is not None:
                    self._renderer.selected_node = root_node
        except Exception as exc:
            log.debug("Model gimbal transform failed: %s", exc)

    def _hit_test_model_bounds(self, sx: int, sy: int) -> bool:
        if self.model is None:
            return False
        try:
            bb_min, bb_max = self._renderer._get_render_bounds()
            w = self.canvas.width() or 800
            h = self.canvas.height() or 600
            points = []
            for x in (bb_min[0], bb_max[0]):
                for y in (bb_min[1], bb_max[1]):
                    for z in (bb_min[2], bb_max[2]):
                        sp = self._renderer._proj(float(x), float(y), float(z), w, h)
                        if sp is not None:
                            points.append(sp)
            if not points:
                return False
            min_x = min(p[0] for p in points) - 12
            max_x = max(p[0] for p in points) + 12
            min_y = min(p[1] for p in points) - 12
            max_y = max(p[1] for p in points) + 12
            return min_x <= sx <= max_x and min_y <= sy <= max_y
        except Exception:
            return False

    def _draw_hovered_mesh_outline(self, draw, w: int, h: int) -> None:
        if not self.mesh_hover_enabled:
            return
        if self._mesh_hover_suppressed_for_animation():
            return
        node = getattr(self, "_hovered_mesh_node", None)
        if node is None or getattr(node, "_gr_hidden", False):
            return
        if node is getattr(self._renderer, "selected_node", None):
            return
        if any(node is selected for selected in getattr(self, "_selected_meshes", []) or []):
            return
        try:
            bounds = self._projected_mesh_bounds(node, w, h)
            if bounds is None:
                return
            _min_x, _min_y, _max_x, _max_y, world_verts, projected = bounds
            faces = list(getattr(node, "faces", []) or [])
            if not faces:
                return

            edge_faces: dict[tuple[int, int], list[bool]] = {}
            for face in faces:
                try:
                    i0, i1, i2 = int(face[0]), int(face[1]), int(face[2])
                    if i0 < 0 or i1 < 0 or i2 < 0:
                        continue
                    if i0 >= len(projected) or i1 >= len(projected) or i2 >= len(projected):
                        continue
                    if projected[i0] is None or projected[i1] is None or projected[i2] is None:
                        continue
                    front = self._front_facing_score(world_verts, (i0, i1, i2)) >= 0.0
                    for a, b in ((i0, i1), (i1, i2), (i2, i0)):
                        edge_faces.setdefault(normalize_edge(a, b), []).append(front)
                except Exception:
                    continue

            outline_edges = []
            for edge, front_flags in edge_faces.items():
                if len(front_flags) == 1 or (any(front_flags) and not all(front_flags)):
                    p0, p1 = projected[edge[0]], projected[edge[1]]
                    if p0 is not None and p1 is not None:
                        outline_edges.append(((float(p0[0]), float(p0[1])), (float(p1[0]), float(p1[1]))))
            if not outline_edges:
                return
            shadow = (0, 0, 0, 105)
            glow = (0, 190, 165, 165)
            for p0, p1 in outline_edges:
                draw.line([p0, p1], fill=shadow, width=4)
            for p0, p1 in outline_edges:
                draw.line([p0, p1], fill=glow, width=2)
        except Exception as exc:
            log.debug("Hovered mesh outline draw failed: %s", exc)

    def _draw_selected_model_outline(self, draw, w: int, h: int) -> None:
        self._draw_hovered_mesh_outline(draw, w, h)

    def _draw_mesh_subobject_selection(self, draw, w: int, h: int) -> None:
        state = getattr(self, "mesh_selection_state", None)
        if state is None or state.mode is MeshSelectionMode.OBJECT:
            return
        mesh = self._active_edit_mesh()
        topology = self._active_topology()
        if mesh is None or topology is None:
            return
        try:
            bounds = self._projected_mesh_bounds(mesh, w, h)
            if bounds is None:
                return
            _min_x, _min_y, _max_x, _max_y, _world_verts, projected = bounds

            def point(vi):
                if vi < 0 or vi >= len(projected):
                    return None
                p = projected[vi]
                if p is None:
                    return None
                return (float(p[0]), float(p[1]))

            def draw_edge(edge, color, width=2):
                p0 = point(edge[0])
                p1 = point(edge[1])
                if p0 is not None and p1 is not None:
                    draw.line([p0, p1], fill=color, width=width)

            if state.mode is MeshSelectionMode.VERTEX:
                for vi in state.selected_vertices:
                    p = point(vi)
                    if p is not None:
                        x, y = p
                        draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(0, 255, 122, 235), outline=(255, 255, 255, 230))
            elif state.mode is MeshSelectionMode.EDGE:
                for edge in state.selected_edges:
                    draw_edge(edge, (0, 215, 181, 245), 3)
                for edge in getattr(mesh, "_gr_connect_edges", set()) or set():
                    draw_edge(edge, (255, 212, 0, 210), 1)
            elif state.mode is MeshSelectionMode.BORDER:
                for idx in state.selected_borders:
                    if isinstance(idx, int) and 0 <= idx < len(topology.border_loops):
                        loop = topology.border_loops[idx]
                        for i in range(len(loop) - 1):
                            draw_edge((loop[i], loop[i + 1]), (255, 170, 0, 245), 3)
            elif state.mode in (MeshSelectionMode.FACE, MeshSelectionMode.POLYGON):
                faces = state.selected_faces if state.mode is MeshSelectionMode.FACE else state.selected_polygons
                for fi in faces:
                    if 0 <= fi < len(topology.faces):
                        pts = [point(vi) for vi in topology.faces[fi]]
                        if all(p is not None for p in pts):
                            draw.polygon(pts, fill=(0, 255, 122, 58), outline=(0, 255, 122, 230))
            elif state.mode is MeshSelectionMode.ELEMENT:
                for idx in state.selected_elements:
                    if 0 <= idx < len(topology.connected_elements):
                        for fi in topology.connected_elements[idx]:
                            pts = [point(vi) for vi in topology.faces[fi]]
                            if all(p is not None for p in pts):
                                draw.polygon(pts, fill=(0, 215, 181, 48), outline=(0, 215, 181, 210))
        except Exception as exc:
            log.debug("Mesh sub-object overlay draw failed: %s", exc)

__all__ = ("ViewportDragInteractionsMixin",)
