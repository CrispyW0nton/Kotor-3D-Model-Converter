"""ViewportState methods for the Qt viewport widget."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportStateMixin:
    def _ensure_renderer_gimbal_state(self) -> bool:
        """Keep older/reloaded FrameRenderer instances compatible with the gimbal UI."""

        if not hasattr(self._renderer, "show_gimbal"):
            self._renderer.show_gimbal = True
        visible = bool(getattr(self._renderer, "show_gimbal", True))
        if hasattr(self, "gimbal_button"):
            self.gimbal_button.blockSignals(True)
            self.gimbal_button.setChecked(visible)
            self.gimbal_button.blockSignals(False)
        return visible

    def _set_renderer_gimbal_visible(self, visible: bool) -> None:
        self._renderer.show_gimbal = bool(visible)
        self._transform_gizmo.visible = bool(visible)

    def _active_gizmo_node(self):
        node = getattr(self._renderer, "selected_node", None)
        if node is not None:
            return self._promoted_model_root_for_mesh_transform(node) or node
        return None

    def _promoted_model_root_for_mesh_transform(self, node):
        """Return the model root when this viewport treats mesh drags as placement.

        Character Builder users often load a custom mesh, then move it to line up
        with the generated KOTOR skeleton. In that workflow, selecting the mesh
        itself should place the whole character instead of leaving the guide
        skeleton behind. The flag is disabled for normal viewports.
        """

        if not bool(getattr(self, "_mesh_transform_promotes_to_model_root", False)):
            return None
        if node is None or self.model is None or self._is_external_skeleton_node(node):
            return None
        root = getattr(self.model, "root_node", None)
        if root is None or node is root or bool(getattr(node, "_gr_scene_object_root", False)):
            return None
        vertices = getattr(node, "vertices", None)
        if not vertices:
            return None
        return root

    def _gizmo_world_position(self, node) -> tuple[float, float, float] | None:
        if node is None:
            return None
        if self._is_external_skeleton_node(node):
            return self._external_overlay_world_position(node)
        if bool(getattr(node, "is_light", False)) or bool(getattr(node, "is_camera", False)):
            if str(getattr(node, "_gr_pivot_edit_mode", "") or "") == "affect_pivot_only":
                pivot_world = getattr(node, "_gr_pivot_world", None)
                if pivot_world is not None:
                    try:
                        return tuple(float(v) for v in pivot_world[:3])
                    except Exception:
                        pass
            else:
                try:
                    if getattr(node, "parent", None) is not None and not bool(getattr(node, "_gr_scene_object_root", False)):
                        transform = getattr(self._renderer, "_node_world_transform", None)
                        if callable(transform):
                            position = tuple(float(v) for v in transform(node)[0][:3])
                        else:
                            position = tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0))[:3])
                    else:
                        position = tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0))[:3])
                    setattr(node, "_gr_gizmo_world_position", position)
                    return position
                except Exception:
                    pass
        pivot_local = getattr(node, "_gr_pivot_local", None)
        if pivot_local is not None and not bool(getattr(node, "_gr_pivot_world_dirty", False)):
            try:
                position = tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0))[:3])
                rotation = tuple(float(v) for v in getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))[:4])
                local = tuple(float(v) for v in pivot_local[:3])
                offset = rotate_vector(rotation, local)
                pivot_world = (position[0] + offset[0], position[1] + offset[1], position[2] + offset[2])
                setattr(node, "_gr_pivot_world", pivot_world)
                return pivot_world
            except Exception:
                pass
        pivot_world = getattr(node, "_gr_pivot_world", None)
        if pivot_world is not None:
            try:
                return tuple(float(v) for v in pivot_world[:3])
            except Exception:
                pass
        if self._is_selected_model_root(node):
            try:
                bb_min, bb_max = self._renderer._get_render_bounds()
                return (
                    (float(bb_min[0]) + float(bb_max[0])) * 0.5,
                    (float(bb_min[1]) + float(bb_max[1])) * 0.5,
                    (float(bb_min[2]) + float(bb_max[2])) * 0.5,
                )
            except Exception:
                pass
        try:
            wp, _wo, _is_id = self._renderer._node_world_transform(node)
            return (float(wp[0]), float(wp[1]), float(wp[2]))
        except Exception:
            pos = getattr(node, "position", None)
            if pos is None:
                return None
            try:
                return tuple(float(v) for v in tuple(pos)[:3])
            except Exception:
                return None

    @staticmethod
    def _quat_conjugate(quat) -> tuple[float, float, float, float]:
        try:
            x, y, z, w = (float(v) for v in tuple(quat)[:4])
            return (-x, -y, -z, w)
        except Exception:
            return (0.0, 0.0, 0.0, 1.0)

    def _scene_instance_for_node(self, node):
        object_id = str(getattr(node, "_gr_scene_object_id", "") or "")
        if not object_id:
            return None
        return next((obj for obj in self._scene_instances if getattr(obj, "id", "") == object_id), None)

    def _sync_transform_reference_for_node(self, node) -> None:
        if node is None:
            return
        try:
            object_rotation = getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))
            pivot_rotation = getattr(node, "_gr_pivot_rotation", None)
            reference_rotation = (
                multiply_quaternions(object_rotation, pivot_rotation)
                if pivot_rotation is not None
                else object_rotation
            )
            setattr(node, "_gr_reference_rotation", reference_rotation)
            basis = self.transform_reference_controller.get_transform_basis(node, self.camera, None)
            setattr(node, "_gr_axis_basis", basis)
        except Exception:
            setattr(node, "_gr_axis_basis", ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
        setattr(node, "_gr_pivot_edit_mode", self._pivot_edit_mode)

    def set_axis_mode(self, mode) -> None:
        resolved = self.transform_reference_controller.set_axis_mode(mode)
        self._pick_reference_waiting = resolved is AxisMode.PICK
        if hasattr(self, "axis_mode_control"):
            self.axis_mode_control.set_axis_mode(resolved)
        if self._pick_reference_waiting:
            self.statusMessage.emit("Pick an object to use as transform reference.")
        self._request_render(fast=True, reason="model loaded", resources=True, overlay=True, hud=True)

    def axis_mode(self) -> AxisMode:
        return self.transform_reference_controller.get_axis_mode()

    def set_pivot_edit_mode(self, mode: str) -> None:
        mode = str(mode or "affect_object_only")
        if mode == "affect_hierarchy_only":
            self.statusMessage.emit("Hierarchy mode is not available for this selection.")
            return
        self._pivot_edit_mode = mode if mode in {"affect_pivot_only", "affect_object_only"} else "affect_object_only"
        node = getattr(self._renderer, "selected_node", None)
        if node is not None:
            setattr(node, "_gr_pivot_edit_mode", self._pivot_edit_mode)
            self._sync_transform_reference_for_node(node)
            self._transform_gizmo.update_from_object_transform()
        self._sync_transform_typein_bar()
        self._request_render(fast=True)

    def pivot_edit_mode(self) -> str:
        return self._pivot_edit_mode

    def _pivot_world_from_instance(self, instance) -> tuple[float, float, float]:
        transform = getattr(instance, "transform", None)
        pivot = getattr(instance, "pivot", None)
        position = tuple(float(v) for v in getattr(transform, "position", (0.0, 0.0, 0.0))[:3])
        rotation_q = self._euler_degrees_to_quat(getattr(transform, "rotation", (0.0, 0.0, 0.0)))
        local = tuple(float(v) for v in getattr(pivot, "position_local", (0.0, 0.0, 0.0))[:3])
        offset = rotate_vector(rotation_q, local)
        return (position[0] + offset[0], position[1] + offset[1], position[2] + offset[2])

    def _pivot_local_from_node(self, node) -> tuple[float, float, float]:
        instance = self._scene_instance_for_node(node)
        if instance is None:
            return (0.0, 0.0, 0.0)
        transform = getattr(instance, "transform", None)
        position = tuple(float(v) for v in getattr(node, "position", getattr(transform, "position", (0.0, 0.0, 0.0)))[:3])
        pivot_world = tuple(float(v) for v in getattr(node, "_gr_pivot_world", position)[:3])
        rotation = tuple(float(v) for v in getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))[:4])
        rel = (pivot_world[0] - position[0], pivot_world[1] - position[1], pivot_world[2] - position[2])
        local = rotate_vector(self._quat_conjugate(rotation), rel)
        try:
            setattr(node, "_gr_pivot_local", local)
            setattr(node, "_gr_pivot_world_dirty", False)
        except Exception:
            pass
        return local

    def _current_transform_target_node(self):
        node = getattr(self._renderer, "selected_node", None)
        if node is not None:
            return self._promoted_model_root_for_mesh_transform(node) or node
        if self.model is not None:
            return getattr(self.model, "root_node", None)
        return None

    def _set_node_pivot_world(self, node, pivot_world: tuple[float, float, float]) -> None:
        position = tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0))[:3])
        rotation = tuple(float(v) for v in getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))[:4])
        rel = (
            float(pivot_world[0]) - position[0],
            float(pivot_world[1]) - position[1],
            float(pivot_world[2]) - position[2],
        )
        local = rotate_vector(self._quat_conjugate(rotation), rel)
        node._gr_pivot_world = tuple(float(v) for v in pivot_world[:3])
        node._gr_pivot_local = tuple(float(v) for v in local[:3])
        node._gr_pivot_world_dirty = False
        node._gr_gizmo_world_position = tuple(float(v) for v in pivot_world[:3])
        self._sync_transform_reference_for_node(node)
        self._transform_gizmo.set_selected_object(node)

    def center_pivot_to_selection(self) -> bool:
        """Move the active pivot to the selected object/mesh bounds center."""
        node = self._current_transform_target_node()
        if node is None:
            self.statusMessage.emit("Select an object or mesh before centering its pivot.")
            return False
        if self._is_external_skeleton_node(node):
            self.statusMessage.emit("Center Pivot is not available for the reference-skeleton overlay.")
            return False
        bounds = self._selection_navigation_bounds()
        if bounds is None:
            try:
                bounds = self._renderer._get_render_bounds()
            except Exception:
                bounds = None
        if bounds is None:
            self.statusMessage.emit("Center Pivot is unavailable: selected object has no bounds.")
            return False
        pivot = self._bounds_center(bounds)
        before_pos = tuple(getattr(node, "position", (0.0, 0.0, 0.0)))
        before_rot = tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0)))
        before_pivot_world = self._optional_tuple_attr(node, "_gr_pivot_world")
        before_pivot_rotation = self._optional_tuple_attr(node, "_gr_pivot_rotation")
        self._set_node_pivot_world(node, pivot)
        self._commit_node_transform(
            node,
            before_pos,
            before_rot,
            before_pos,
            before_rot,
            "Center Pivot",
            before_pivot_world=before_pivot_world,
            after_pivot_world=self._optional_tuple_attr(node, "_gr_pivot_world"),
            before_pivot_rotation=before_pivot_rotation,
            after_pivot_rotation=self._optional_tuple_attr(node, "_gr_pivot_rotation"),
        )
        self._sync_transform_typein_bar()
        self._request_render(fast=True)
        self.statusMessage.emit("Pivot centered on selected bounds.")
        return True

    def freeze_selected_transform(self) -> bool:
        """Bake the selected mesh node's transform into geometry and reset it.

        This deliberately targets a selected mesh node, not a whole KOTOR node
        hierarchy. Freezing a hierarchy safely needs an export-aware rig pass.
        """
        node = getattr(self._renderer, "selected_node", None)
        if node is None or self._is_external_skeleton_node(node):
            self.statusMessage.emit("Select a mesh node before freezing transforms.")
            return False
        vertices = getattr(node, "vertices", None)
        if not vertices:
            self.statusMessage.emit("Freeze Transforms is available for selected mesh nodes with vertices.")
            return False
        before_pos = tuple(getattr(node, "position", (0.0, 0.0, 0.0)))
        before_rot = tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0)))
        before_vertices = self._snapshot_vertices(node)
        before_scale = self._node_scale(node)
        before_pivot_world = self._optional_tuple_attr(node, "_gr_pivot_world")
        before_pivot_rotation = self._optional_tuple_attr(node, "_gr_pivot_rotation")
        sx, sy, sz = before_scale
        px, py, pz = (float(v) for v in before_pos[:3])
        baked = []
        for vertex in vertices:
            try:
                local = (
                    float(vertex[0]) * sx,
                    float(vertex[1]) * sy,
                    float(vertex[2]) * sz,
                )
                rotated = rotate_vector(before_rot, local)
                baked.append((rotated[0] + px, rotated[1] + py, rotated[2] + pz))
            except Exception:
                baked.append(tuple(vertex[:3]))
        node.vertices = baked
        node.position = (0.0, 0.0, 0.0)
        node.rotation = (0.0, 0.0, 0.0, 1.0)
        node._gr_scale = (1.0, 1.0, 1.0)
        compute_bounds = getattr(node, "compute_bounds", None)
        if callable(compute_bounds):
            compute_bounds()
        try:
            bounds = self._bounds_from_points(baked, min_extent=0.05)
            self._set_node_pivot_world(node, self._bounds_center(bounds))
        except Exception:
            pass
        after_vertices = self._snapshot_vertices(node)
        self._commit_node_transform(
            node,
            before_pos,
            before_rot,
            tuple(getattr(node, "position", (0.0, 0.0, 0.0))),
            tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))),
            "Freeze Transforms",
            before_vertices=before_vertices,
            after_vertices=after_vertices,
            before_scale=before_scale,
            after_scale=self._node_scale(node),
            before_pivot_world=before_pivot_world,
            after_pivot_world=self._optional_tuple_attr(node, "_gr_pivot_world"),
            before_pivot_rotation=before_pivot_rotation,
            after_pivot_rotation=self._optional_tuple_attr(node, "_gr_pivot_rotation"),
        )
        self._evict_transform_cache(node)
        self._notify_node_moved(node)
        self._sync_transform_typein_bar()
        self._request_render(fast=True)
        self.statusMessage.emit("Transforms frozen into selected mesh geometry.")
        return True

    @property
    def navigation_profile(self) -> str:
        return self._navigation_profile

    def set_navigation_profile(self, profile: object) -> None:
        self._navigation_profile = normalize_viewport_navigation_profile(profile)
        self._sync_navigation_button()

    def _toolbar_text(self, full: str, compact: str) -> str:
        return compact if self._compact_controls else full

    def _navigation_button_text(self) -> str:
        label = viewport_profile_label(self._navigation_profile)
        if not self._compact_controls:
            return label
        return {
            "3ds Max": "3ds",
            "Blender": "Blnd",
            "Maya": "Maya",
        }.get(label, label[:4])

    def _gimbal_mode_button_text(self) -> str:
        mode = self._transform_gizmo.mode
        if mode == GizmoMode.ROTATE:
            return "[R]" if self._compact_controls else "[Rotate]"
        if mode == GizmoMode.SCALE:
            return "[S]" if self._compact_controls else "[Scale]"
        return "[T]" if self._compact_controls else "[Translate]"

    def _gimbal_mode_icon_name(self) -> str:
        mode = self._transform_gizmo.mode
        if mode == GizmoMode.ROTATE:
            return "viewport_rotate"
        if mode == GizmoMode.SCALE:
            return "viewport_scale"
        return "viewport_translate"

    def _selection_mode_icon_name(self) -> str:
        return VIEWPORT_SELECTION_MODE_ICONS.get(self._viewport_selection_mode, "viewport_select_object")

    def _selection_mode_label(self) -> str:
        return VIEWPORT_SELECTION_MODE_LABELS.get(self._viewport_selection_mode, "Object")

    def _sync_gimbal_mode_button(self) -> None:
        button = getattr(self, "gimbal_mode_button", None)
        if button is None:
            return
        button.setIcon(_icon(self._gimbal_mode_icon_name()))
        button.setText("")
        button.setToolTip(f"Cycle gimbal mode: {self._transform_gizmo.mode.value.title()}")

    def _sync_selection_mode_button(self) -> None:
        button = getattr(self, "selection_mode_button", None)
        if button is None:
            return
        button.setIcon(_icon(self._selection_mode_icon_name()))
        button.setText("")
        label = self._selection_mode_label()
        button.setToolTip(f"Viewport selection mode: {label}")
        menu = button.menu()
        if menu is not None:
            for action in menu.actions():
                action.setChecked(action.data() == self._viewport_selection_mode)

    def _build_selection_mode_menu(self) -> QtWidgets.QMenu:
        menu = QtWidgets.QMenu(self)
        for mode, label, icon_name in VIEWPORT_SELECTION_MODES:
            action = menu.addAction(_icon(icon_name), label)
            action.setCheckable(True)
            action.setData(mode)
            action.triggered.connect(lambda _checked=False, value=mode: self.set_viewport_selection_mode(value))
        return menu

    def set_viewport_selection_mode(self, mode: str) -> None:
        value = str(mode or "object").strip().lower()
        if value not in VIEWPORT_SELECTION_MODE_LABELS:
            value = "object"
        if value == self._viewport_selection_mode:
            self._sync_selection_mode_button()
            return
        self._viewport_selection_mode = value
        self._sync_selection_mode_button()
        self.statusMessage.emit(f"Selection: {self._selection_mode_label()}")

    def toggle_dummy_helpers(self, checked: bool = False) -> None:
        self.set_dummy_helper_visibility(bool(checked))

    def set_dummy_helper_visibility(self, visible: bool) -> None:
        self._dummy_helpers_visible = bool(visible)
        for target in (self._renderer, self._gpu_renderer):
            if target is not None:
                setattr(target, "show_dummy_helpers", self._dummy_helpers_visible)
        button = getattr(self, "dummy_helpers_button", None)
        if button is not None:
            button.blockSignals(True)
            button.setChecked(self._dummy_helpers_visible)
            button.blockSignals(False)
        selected = getattr(self._renderer, "selected_node", None)
        if not self._dummy_helpers_visible and self._is_general_helper_node(selected):
            self.set_selected_node(None)
        self.statusMessage.emit("Dummy helpers visible" if self._dummy_helpers_visible else "Dummy helpers hidden")
        self._request_render(fast=True, reason="dummy helper visibility changed", overlay=True, selection=True)

    def _navigation_tooltip(self) -> str:
        label = viewport_profile_label(self._navigation_profile)
        controls = {
            "3dsmax": "3ds Max: Alt+MMB orbit, MMB pan, Alt+RMB zoom, wheel zoom; Shift+F/T/L/P views",
            "blender": "Blender: MMB orbit, Shift+MMB pan, Ctrl+MMB zoom, wheel zoom; 1/3/7/Home views",
            "maya": "Maya: Alt+LMB orbit, Alt+MMB pan, Alt+RMB zoom, wheel zoom; A/F frame",
        }.get(self._navigation_profile, "")
        return f"Viewport navigation profile: {label}\n{controls}"

    def _select_navigation_profile(self, profile: object) -> None:
        self.set_navigation_profile(profile)

    def _build_navigation_menu(self) -> QtWidgets.QMenu:
        menu = QtWidgets.QMenu(self)
        for profile in ("3dsmax", "blender", "maya"):
            label = viewport_profile_label(profile)
            action = menu.addAction(_navigation_profile_icon(profile), label)
            action.setCheckable(True)
            action.setData(profile)
            action.triggered.connect(lambda _checked=False, value=profile: self._select_navigation_profile(value))
        return menu

    def _sync_navigation_button(self) -> None:
        button = getattr(self, "navigation_button", None)
        if button is None:
            return
        button.setIcon(_navigation_profile_icon(self._navigation_profile))
        button.setText("")
        button.setToolTip(self._navigation_tooltip())
        menu = button.menu()
        if menu is not None:
            for action in menu.actions():
                profile = action.data()
                action.setChecked(profile == self._navigation_profile)

__all__ = ("ViewportStateMixin",)
