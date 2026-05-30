"""ViewportHistoryAnimation methods for the Qt viewport widget."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportHistoryAnimationMixin:
    def _state_changed(before_pos, before_rot, after_pos, after_rot, before_vertices=None, after_vertices=None) -> bool:
        values = tuple(before_pos) + tuple(before_rot) + tuple(after_pos) + tuple(after_rot)
        if any(not math.isfinite(float(v)) for v in values):
            return False
        if before_vertices is not None or after_vertices is not None:
            if before_vertices != after_vertices:
                return True
        return (
            any(abs(float(a) - float(b)) > 1e-7 for a, b in zip(before_pos, after_pos))
            or any(abs(float(a) - float(b)) > 1e-7 for a, b in zip(before_rot, after_rot))
        )

    def _commit_node_transform(
        self,
        node,
        before_pos,
        before_rot,
        after_pos,
        after_rot,
        label: str,
        *,
        before_vertices=None,
        after_vertices=None,
        before_scale=None,
        after_scale=None,
        before_pivot_world=None,
        after_pivot_world=None,
        before_pivot_rotation=None,
        after_pivot_rotation=None,
    ) -> None:
        scale_changed = before_scale is not None and after_scale is not None and tuple(before_scale) != tuple(after_scale)
        pivot_changed = (
            (before_pivot_world is not None and after_pivot_world is not None and tuple(before_pivot_world) != tuple(after_pivot_world))
            or (
                before_pivot_rotation is not None
                and after_pivot_rotation is not None
                and tuple(before_pivot_rotation) != tuple(after_pivot_rotation)
            )
        )
        if node is None or (
            not scale_changed
            and not pivot_changed
            and not self._state_changed(before_pos, before_rot, after_pos, after_rot, before_vertices, after_vertices)
        ):
            return
        self._undo_stack.append(
            {
                "node": node,
                "before_pos": tuple(before_pos),
                "before_rot": tuple(before_rot),
                "after_pos": tuple(after_pos),
                "after_rot": tuple(after_rot),
                "before_vertices": before_vertices,
                "after_vertices": after_vertices,
                "before_scale": before_scale,
                "after_scale": after_scale,
                "before_pivot_world": before_pivot_world,
                "after_pivot_world": after_pivot_world,
                "before_pivot_rotation": before_pivot_rotation,
                "after_pivot_rotation": after_pivot_rotation,
                "label": label,
            }
        )
        if len(self._undo_stack) > self._undo_limit:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _apply_transform_action(self, action: dict, use_after: bool) -> None:
        node = action.get("node")
        if node is None:
            return
        node.position = action["after_pos"] if use_after else action["before_pos"]
        node.rotation = action["after_rot"] if use_after else action["before_rot"]
        vertices = action.get("after_vertices") if use_after else action.get("before_vertices")
        scale = action.get("after_scale") if use_after else action.get("before_scale")
        pivot_world = action.get("after_pivot_world") if use_after else action.get("before_pivot_world")
        pivot_rotation = action.get("after_pivot_rotation") if use_after else action.get("before_pivot_rotation")
        if scale is not None:
            node._gr_scale = tuple(scale)
        if pivot_world is not None:
            node._gr_pivot_world = tuple(pivot_world)
            node._gr_gizmo_world_position = tuple(pivot_world)
            node._gr_pivot_world_dirty = True
        if pivot_rotation is not None:
            node._gr_pivot_rotation = tuple(pivot_rotation)
        if vertices is not None:
            node.vertices = [tuple(v) for v in vertices]
            compute_bounds = getattr(node, "compute_bounds", None)
            if callable(compute_bounds):
                compute_bounds()
        self._evict_transform_cache(node)
        self._notify_node_moved(node)
        self._request_render()

    def undo(self) -> bool:
        if getattr(self, "mesh_selection_state", None) is not None and self.mesh_selection_state.mode is not MeshSelectionMode.OBJECT:
            if self.mesh_tool_undo():
                return True
        if not self._undo_stack:
            return False
        action = self._undo_stack.pop()
        self._apply_transform_action(action, use_after=False)
        self._redo_stack.append(action)
        return True

    def redo(self) -> bool:
        if getattr(self, "mesh_selection_state", None) is not None and self.mesh_selection_state.mode is not MeshSelectionMode.OBJECT:
            if self.mesh_tool_redo():
                return True
        if not self._redo_stack:
            return False
        action = self._redo_stack.pop()
        self._apply_transform_action(action, use_after=True)
        self._undo_stack.append(action)
        if len(self._undo_stack) > self._undo_limit:
            self._undo_stack.pop(0)
        return True

    def _notify_node_moved(self, node) -> None:
        if bool(getattr(node, "is_camera", False)):
            camera = self.camera_manager.find_by_original(node)
            if camera is not None:
                camera.position = tuple(float(v) for v in getattr(node, "position", camera.position)[:3])
                camera.rotation = tuple(float(v) for v in getattr(node, "rotation", camera.rotation)[:4])
                camera.metadata["helper_size"] = float(getattr(node, "_gr_helper_size", camera.metadata.get("helper_size", 1.0)) or 1.0)
                camera.apply_to_original()
                self.camera_manager._store_on_model()
                if self.camera_manager.active_camera_id == camera.id:
                    self.update_view_from_camera(camera)
                self.cameraChanged.emit()
        if self.on_node_moved:
            self.on_node_moved(node)
        self.nodeMoved.emit(node)
        if node is getattr(self._renderer, "selected_node", None):
            self._transform_gizmo.update_from_object_transform()
        self._sync_transform_typein_bar()
        if self._renderer.rig_edit_mode and self._renderer.on_bone_moved:
            try:
                self._renderer.on_bone_moved(node.name, node.position)
            except Exception:
                pass

    def set_anim_base_pose(self, base_pose) -> None:
        self._renderer.set_anim_base_pose(base_pose)

    def set_animation_pose(self, pose, name: str = "", time: float = 0.0, length: float = 0.0) -> None:
        self._renderer.set_animation_pose(pose, name=name, time=time, length=length)
        if pose is not None:
            self._clear_mesh_hover(request=False, reason="animation pose active")
        self._fast_frame_until = max(self._fast_frame_until, time_module.perf_counter() + 0.12)
        self._request_render(fast=True, reason="animation pose changed", scene=True, overlay=True, hud=True)

    def set_animation_playback_active(self, active: bool, reason: str = "animation playback") -> None:
        self._frame_governor.set_animation_playing(bool(active), reason)
        if active:
            self._clear_mesh_hover(request=False, reason=reason)
            self._request_render(fast=True, reason=reason, scene=True, overlay=True, hud=True)

    def clear_animation_pose(self) -> None:
        self._renderer.set_animation_pose(None)
        self._frame_governor.set_animation_playing(False)
        self._fast_frame_until = 0.0
        self._request_render(reason="animation pose cleared", scene=True, overlay=True, hud=True)

    def load_walkmesh(self, wok_data_or_path, world_offset=(0.0, 0.0, 0.0)) -> None:
        self._renderer.load_walkmesh(wok_data_or_path, world_offset)
        self.walkmesh_button.setChecked(self._renderer.show_walkmesh)
        self._request_render()

    def clear_walkmesh(self) -> None:
        self._renderer.clear_walkmesh()
        self.walkmesh_button.setChecked(False)
        self._request_render()

    def open_uv_viewer(self) -> None:
        if self._uv_viewer is None:
            self._uv_viewer = QtUVViewerWindow(self.window())
            self._uv_viewer.destroyed.connect(lambda *_: setattr(self, "_uv_viewer", None))
            self._uv_viewer._tex_cache = self._renderer.tex_cache
            self._update_uv_viewer_model()
            if self._renderer.selected_node:
                self._uv_viewer.set_selected_node(self._renderer.selected_node)
        self._uv_viewer.show()
        self._uv_viewer.raise_()
        self._uv_viewer.activateWindow()

__all__ = ("ViewportHistoryAnimationMixin",)
