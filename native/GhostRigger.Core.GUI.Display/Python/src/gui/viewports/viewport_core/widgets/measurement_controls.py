"""ViewportMeasurementControls methods for the Qt viewport widget."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportMeasurementControlsMixin:
    def toggle_gpu_renderer(self, checked: Optional[bool] = None) -> None:
        self._use_gpu = True
        self.renderer_button.setChecked(True)
        self.renderer_button.setToolTip("GPU renderer")
        self._emit_render_state_changed()
        self._request_render(fast=True)

    def toggle_xray(self, checked: Optional[bool] = None) -> None:
        self._xray_mode = bool(checked) if checked is not None else not self._xray_mode
        self._set_display_options(self.display_options.with_changes(xray=self._xray_mode))
        self._request_render(fast=True)

    def toggle_joint_dots(self, checked: Optional[bool] = None) -> None:
        """Toolbar toggle for the AccuRig joint-dot HUD layer."""
        enabled = bool(checked) if checked is not None else not self._joint_dot_enabled
        self.set_joint_dot_enabled(enabled)

    def toggle_locomotion_discs(self, checked: Optional[bool] = None) -> None:
        """Toolbar toggle for key-joint locomotion discs."""
        enabled = bool(checked) if checked is not None else not self._locomotion_disc_enabled
        self.set_locomotion_disc_enabled(enabled)

    def toggle_weight_heatmap(self, checked: Optional[bool] = None) -> None:
        """Toolbar toggle for the selected-bone weight heat-map HUD layer."""
        enabled = bool(checked) if checked is not None else not self._weight_heatmap_enabled
        self.set_weight_heatmap_enabled(enabled)

    @property
    def mesh_hover_enabled(self) -> bool:
        return bool(getattr(self, "_mesh_hover_enabled", True))

    def set_mesh_hover_enabled(self, enabled: bool) -> None:
        """Enable or disable the viewport mesh hover outline helper."""
        new_value = bool(enabled)
        if self._mesh_hover_enabled == new_value:
            if hasattr(self, "mesh_hover_button"):
                self.mesh_hover_button.blockSignals(True)
                self.mesh_hover_button.setChecked(new_value)
                self.mesh_hover_button.blockSignals(False)
            return
        self._mesh_hover_enabled = new_value
        if not new_value:
            self._hovered_mesh_node = None
            self._hovered_mesh_face_bounds = None
        if hasattr(self, "mesh_hover_button"):
            self.mesh_hover_button.blockSignals(True)
            self.mesh_hover_button.setChecked(new_value)
            self.mesh_hover_button.blockSignals(False)
        self._request_render(fast=True)

    def toggle_mesh_hover(self, checked: Optional[bool] = None) -> None:
        """Toolbar toggle for the mesh hover outline helper."""
        enabled = bool(checked) if checked is not None else not self.mesh_hover_enabled
        self.set_mesh_hover_enabled(enabled)

    def toggle_walkmesh(self, checked: Optional[bool] = None) -> None:
        if self._renderer._walkmesh_overlay is None:
            parent = self.window()
            coload = getattr(parent, "_try_coload_walkmesh", None)
            if callable(coload):
                try:
                    coload()
                except TypeError:
                    coload(None)
            if self._renderer._walkmesh_overlay is None:
                self.walkmesh_button.setChecked(False)
                self._request_render()
                return
        self._renderer.show_walkmesh = bool(checked) if checked is not None else not self._renderer.show_walkmesh
        self.walkmesh_button.setChecked(self._renderer.show_walkmesh)
        self._request_render()

    def toggle_gimbal(self, checked: Optional[bool] = None) -> None:
        current = self._ensure_renderer_gimbal_state()
        self._set_renderer_gimbal_visible(bool(checked) if checked is not None else not current)
        self.gimbal_button.setChecked(self._ensure_renderer_gimbal_state())
        self._request_render()

    def toggle_measurement_mode(self, checked: Optional[bool] = None) -> None:
        self._measurement_mode = bool(checked) if checked is not None else not self._measurement_mode
        self.measure_button.setChecked(self._measurement_mode)
        if not self._measurement_mode:
            self.measurement_controller.active = False
        self._request_render()

    def toggle_snap(self, checked: Optional[bool] = None) -> None:
        enabled = bool(checked) if checked is not None else not self.measurement_settings.snap_enabled
        self.measurement_settings.snap_enabled = enabled
        self._apply_snap_settings_to_controller()
        self._emit_measurement_settings_changed()
        self._sync_transform_typein_bar()

    def toggle_angle_snap(self, checked: Optional[bool] = None) -> None:
        enabled = bool(checked) if checked is not None else not self.angle_snap.enabled
        self.angle_snap.set_enabled(enabled)
        self.measurement_settings.angle_snap_enabled = enabled
        self._emit_measurement_settings_changed()
        self._sync_transform_typein_bar()
        self._request_render(fast=True)

    def toggle_percent_snap(self, checked: Optional[bool] = None) -> None:
        enabled = bool(checked) if checked is not None else not self.percent_snap.enabled
        self.percent_snap.set_enabled(enabled)
        self.measurement_settings.percent_snap_enabled = enabled
        self._emit_measurement_settings_changed()
        self._sync_transform_typein_bar()
        self._request_render(fast=True)

    def _on_angle_snap_increment_changed(self, text: str) -> None:
        try:
            value = float(str(text or "").replace("deg", "").replace("°", "").strip())
        except ValueError:
            return
        value = max(1e-6, min(value, 360.0))
        self.angle_snap.set_increment_degrees(value)
        self.measurement_settings.angle_snap_increment_degrees = value
        self._emit_measurement_settings_changed()
        self._sync_transform_typein_bar()

    def _on_percent_snap_increment_changed(self, text: str) -> None:
        try:
            value = float(str(text or "").replace("%", "").strip())
        except ValueError:
            return
        value = max(1e-6, min(value, 1000.0))
        self.percent_snap.set_increment_percent(value)
        self.measurement_settings.percent_snap_increment_percent = value
        self._emit_measurement_settings_changed()
        self._sync_transform_typein_bar()

    def set_measurement_settings(self, values: dict | MeasurementSettings | None) -> None:
        settings = values if isinstance(values, MeasurementSettings) else MeasurementSettings.from_dict(values)
        self.measurement_settings = settings
        self.unit_system.set_system_unit(settings.system_unit)
        self.unit_system.set_display_unit(settings.display_unit)
        self.angle_snap.set_enabled(settings.angle_snap_enabled)
        self.angle_snap.set_increment_degrees(settings.angle_snap_increment_degrees)
        self.percent_snap.set_enabled(settings.percent_snap_enabled)
        self.percent_snap.set_increment_percent(settings.percent_snap_increment_percent)
        self.measurement_controller.configure(self.unit_system, settings.distance_precision)
        self._renderer.unit_system = self.unit_system
        self._renderer.grid_measurement = GridMeasurement(
            self.unit_system,
            minor_spacing=settings.minor_grid_spacing,
            major_spacing=settings.major_grid_spacing,
            show_labels=settings.show_grid_measurements,
            precision=settings.distance_precision,
        )
        self._apply_snap_settings_to_controller()
        self._sync_transform_typein_bar()
        self._request_render()

    def _apply_snap_settings_to_controller(self) -> None:
        controller = getattr(self._transform_gizmo, "controller", None)
        if controller is not None and hasattr(controller, "set_position_snap"):
            controller.set_position_snap(
                self.measurement_settings.snap_enabled,
                self.measurement_settings.minor_grid_spacing,
            )

    def _emit_measurement_settings_changed(self) -> None:
        self.measurementSettingsChanged.emit({"measurement": self.measurement_settings.to_dict()})

    def _sync_transform_typein_bar(self) -> None:
        bar = getattr(self, "transform_typein_bar", None)
        if bar is None:
            return
        mode = self._transform_gizmo.mode
        mode_label = {
            GizmoMode.TRANSLATE: "MOVE",
            GizmoMode.ROTATE: "ROTATE",
            GizmoMode.SCALE: "SCALE",
        }.get(mode, "MOVE")
        bar.set_mode_label(mode_label)
        bar.set_grid_text(self.unit_system.format_distance(
            self.measurement_settings.minor_grid_spacing,
            self.measurement_settings.distance_precision,
        ))
        bar.set_snap_state(
            snap=self.measurement_settings.snap_enabled,
            angle=self.angle_snap.enabled,
            percent=self.percent_snap.enabled,
        )
        bar.set_increment_texts(
            angle=f"{self.angle_snap.increment_degrees:g}°",
            percent=f"{self.percent_snap.increment_percent:g}%",
        )
        node = getattr(self._renderer, "selected_node", None)
        bar.set_transform_enabled(node is not None)
        if node is None:
            bar.set_transform_values(("", "", ""))
            return
        if mode == GizmoMode.ROTATE:
            rx, ry, rz = self._quat_to_euler_degrees(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0)))
            bar.set_transform_values((f"{rx:.3f}°", f"{ry:.3f}°", f"{rz:.3f}°"))
        elif mode == GizmoMode.SCALE:
            sx, sy, sz = self._node_scale(node)
            bar.set_transform_values((f"{sx:.3f}", f"{sy:.3f}", f"{sz:.3f}"))
        else:
            px, py, pz = tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0))[:3])
            p = self.measurement_settings.distance_precision
            bar.set_transform_values(
                (
                    self.unit_system.format_distance(px, p),
                    self.unit_system.format_distance(py, p),
                    self.unit_system.format_distance(pz, p),
                )
            )

    def _on_grid_spacing_edited(self, text: str) -> None:
        try:
            spacing = self.unit_system.parse_distance(text)
        except ValueError:
            self._sync_transform_typein_bar()
            return
        spacing = max(1e-6, float(spacing))
        self.measurement_settings.minor_grid_spacing = spacing
        self.measurement_settings.major_grid_spacing = max(spacing, spacing * 10.0)
        self.set_measurement_settings(self.measurement_settings)
        self._emit_measurement_settings_changed()

    def _on_transform_typein_edited(self, axis: str, text: str) -> None:
        node = getattr(self._renderer, "selected_node", None)
        if node is None:
            self._sync_transform_typein_bar()
            return
        axis_index = {"X": 0, "Y": 1, "Z": 2}.get(axis)
        if axis_index is None:
            return
        before_pos = tuple(getattr(node, "position", (0.0, 0.0, 0.0)))
        before_rot = tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0)))
        before_vertices = self._snapshot_vertices(node)
        before_scale = self._node_scale(node)
        before_pivot_world = self._optional_tuple_attr(node, "_gr_pivot_world")
        before_pivot_rotation = self._optional_tuple_attr(node, "_gr_pivot_rotation")
        try:
            if self._transform_gizmo.mode == GizmoMode.ROTATE:
                self._apply_rotation_typein(node, axis_index, text)
                label = "Set Rotation"
            elif self._transform_gizmo.mode == GizmoMode.SCALE:
                self._apply_scale_typein(node, axis_index, text)
                label = "Set Scale"
            else:
                self._apply_position_typein(node, axis_index, text)
                label = "Set Position"
        except ValueError:
            self._sync_transform_typein_bar()
            return
        after_vertices = self._snapshot_vertices(node)
        self._commit_node_transform(
            node,
            before_pos,
            before_rot,
            tuple(getattr(node, "position", (0.0, 0.0, 0.0))),
            tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))),
            label,
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
        self._request_render(fast=True)

    def _apply_position_typein(self, node, axis_index: int, text: str) -> None:
        value = self.unit_system.parse_distance(text)
        if self.measurement_settings.snap_enabled:
            inc = self.measurement_settings.minor_grid_spacing
            value = round(value / inc) * inc
        position = list(tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0))[:3]))
        old_position = tuple(position)
        position[axis_index] = float(value)
        new_position = tuple(position)
        node.position = new_position
        if str(getattr(node, "_gr_pivot_edit_mode", "") or "") != "affect_pivot_only":
            pivot_world = getattr(node, "_gr_pivot_world", None)
            if pivot_world is not None:
                delta = (
                    new_position[0] - old_position[0],
                    new_position[1] - old_position[1],
                    new_position[2] - old_position[2],
                )
                updated = (
                    float(pivot_world[0]) + delta[0],
                    float(pivot_world[1]) + delta[1],
                    float(pivot_world[2]) + delta[2],
                )
                setattr(node, "_gr_pivot_world", updated)
                setattr(node, "_gr_pivot_world_dirty", True)
                setattr(node, "_gr_gizmo_world_position", updated)

    def _apply_rotation_typein(self, node, axis_index: int, text: str) -> None:
        value = float(str(text or "").replace("deg", "").replace("°", "").strip())
        if self.angle_snap.enabled:
            value = self.angle_snap.snap_degrees(value)
        euler = list(self._quat_to_euler_degrees(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))))
        euler[axis_index] = value
        node.rotation = self._euler_degrees_to_quat(euler)

    def _apply_scale_typein(self, node, axis_index: int, text: str) -> None:
        raw = str(text or "").strip()
        if raw.endswith("%"):
            value = float(raw[:-1].strip()) / 100.0
        else:
            value = float(raw)
        if self.percent_snap.enabled:
            value = self.percent_snap.snap_scale_factor(value)
        value = max(0.001, float(value))
        scale = list(self._node_scale(node))
        old_value = max(0.001, scale[axis_index])
        scale[axis_index] = value
        ratio = value / old_value
        if bool(getattr(node, "is_camera", False)):
            node._gr_helper_size = max(0.05, float(getattr(node, "_gr_helper_size", 1.0) or 1.0) * ratio)
            node._gr_scale = tuple(scale)
            return
        if bool(getattr(node, "_gr_scene_object_root", False)):
            node._gr_scale = tuple(scale)
            return
        verts = getattr(node, "vertices", None)
        if verts is not None:
            node.vertices = [
                tuple(
                    coord * ratio if idx == axis_index else coord
                    for idx, coord in enumerate(tuple(vertex[:3]))
                )
                for vertex in verts
            ]
            compute_bounds = getattr(node, "compute_bounds", None)
            if callable(compute_bounds):
                compute_bounds()
        node._gr_scale = tuple(scale)

__all__ = ("ViewportMeasurementControlsMixin",)
