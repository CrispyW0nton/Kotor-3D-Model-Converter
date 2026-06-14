"""ViewportCameraWorkflow methods for the Qt viewport widget."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportCameraWorkflowMixin:
    def refresh_cameras(self) -> None:
        self.sync_camera_target_bindings()
        if self._camera_view_active:
            camera = self.camera_manager.get_active_camera()
            if camera is not None:
                self.update_view_from_camera(camera)
            else:
                self.switch_to_perspective()
        self._refresh_camera_view_combo()
        self._request_render(fast=True, reason="camera settings changed", camera=True, overlay=True, scene=True)

    def create_scene_camera(self, camera_type: str = "Cinematic Camera"):
        camera = self.camera_controller.create_camera(camera_type=camera_type, from_current_view=True)
        self.set_selected_node(camera.original_ref)
        self._refresh_camera_view_combo()
        self.cameraChanged.emit()
        self._request_render()
        return camera

    def create_camera_from_current_view(self, make_active: bool = True):
        camera = self.camera_controller.create_camera_from_current_view(make_active=make_active)
        self.set_selected_node(camera.original_ref)
        self._refresh_camera_view_combo()
        if make_active:
            self.switch_to_camera(camera.id)
        self.cameraChanged.emit()
        return camera

    def duplicate_selected_camera(self, camera_id: str | None = None):
        camera = self.camera_manager.get_camera(camera_id or "")
        if camera is None:
            selected = self.camera_manager.selected_cameras()
            camera = selected[-1] if selected else None
        if camera is None:
            return None
        dup = self.camera_manager.duplicate_camera(camera.id)
        if dup is not None:
            self.set_selected_node(dup.original_ref)
        self._refresh_camera_view_combo()
        self.cameraChanged.emit()
        self._request_render()
        return dup

    def delete_camera(self, camera_id: str) -> bool:
        if self.camera_manager.active_camera_id == camera_id:
            self.switch_to_perspective()
        ok = self.camera_manager.delete_camera(camera_id)
        if ok:
            self._refresh_camera_view_combo()
            self.cameraChanged.emit()
            self._request_render()
        return ok

    def delete_selected_camera(self) -> None:
        selected = self.camera_manager.selected_cameras()
        if len(selected) > 1:
            answer = QtWidgets.QMessageBox.question(self, "Delete Cameras", f"Delete {len(selected)} selected cameras?")
            if answer != QtWidgets.QMessageBox.Yes:
                return
        for camera in list(selected):
            self.delete_camera(camera.id)

    def switch_to_camera(self, camera_id: str):
        camera = self.camera_manager.set_active_camera(camera_id)
        if camera is None:
            return None
        if not self._camera_view_active:
            self._camera_adapter.save_perspective_state()
        self._camera_view_active = True
        self.update_view_from_camera(camera)
        self._refresh_camera_view_combo()
        self.activeCameraChanged.emit(camera.original_ref)
        self._request_render()
        return camera

    def switch_to_perspective(self) -> None:
        self.camera_manager.clear_active_camera()
        if self._camera_view_active:
            self._camera_adapter.restore_perspective_state()
        self._camera_view_active = False
        self._refresh_camera_view_combo()
        self.activeCameraChanged.emit(None)
        self._request_render()

    def is_camera_view_active(self) -> bool:
        return bool(self._camera_view_active and self.camera_manager.get_active_camera() is not None)

    def update_view_from_camera(self, camera) -> None:
        self._camera_adapter.update_view_from_camera(camera)
        self._request_render(fast=True, reason="camera view refreshed", camera=True, overlay=True, scene=True)

    def update_camera_from_view(self, camera=None) -> None:
        target = camera or self.camera_manager.get_active_camera()
        if target is None:
            return
        if bool(getattr(target, "locked", False)):
            return
        self._camera_adapter.update_camera_from_view(target)
        self.camera_manager._store_on_model()
        self.cameraChanged.emit()
        self._request_render(fast=True, reason="active camera updated from viewport", camera=True, overlay=True, scene=True)

    def _camera_for_target_handle(self, node):
        if node is None or not bool(getattr(node, "_gr_camera_target_handle", False)):
            return None
        return self.camera_manager.get_camera(str(getattr(node, "_gr_camera_target_camera_id", "") or ""))

    def _camera_target_handle(self, camera):
        from types import SimpleNamespace

        handles = getattr(self, "_camera_target_handles", None)
        if handles is None:
            handles = {}
            setattr(self, "_camera_target_handles", handles)
        position = tuple(float(v) for v in tuple(getattr(camera, "target_position", (0.0, 0.0, 0.0)))[:3])
        handle = handles.get(camera.id)
        if handle is None:
            handle = SimpleNamespace(
                name="",
                position=position,
                rotation=(0.0, 0.0, 0.0, 1.0),
                children=[],
                is_camera=True,
                _gr_camera_target_handle=True,
                _gr_camera_target_camera_id=camera.id,
                _gr_scene_object_name="",
            )
            handles[camera.id] = handle
        handle.name = f"{getattr(camera, 'name', 'Camera')} Target"
        handle.position = position
        handle._gr_gizmo_world_position = position
        handle._gr_camera_target_camera_id = camera.id
        handle._gr_scene_object_name = handle.name
        return handle

    def _scene_target_position(self, object_id: str):
        target_id = str(object_id or "")
        if not target_id or self.model is None:
            return None
        try:
            nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        except Exception:
            nodes = []
        fallback = None
        for node in nodes:
            if str(getattr(node, "_gr_scene_object_id", "") or "") != target_id:
                continue
            if bool(getattr(node, "_gr_scene_object_root", False)):
                fallback = node
                break
            if fallback is None:
                fallback = node
        if fallback is None:
            return None
        try:
            return tuple(float(v) for v in getattr(fallback, "position", (0.0, 0.0, 0.0))[:3])
        except Exception:
            return None

    def _apply_camera_target_position(self, camera, target_position, *, allow_follow: bool = True) -> bool:
        from src.math.camera_math import look_at_quaternion

        try:
            new_target = tuple(float(v) for v in tuple(target_position)[:3])
        except Exception:
            return False
        old_target = tuple(float(v) for v in tuple(getattr(camera, "target_position", (0.0, 0.0, 0.0)))[:3])
        old_position = tuple(float(v) for v in tuple(getattr(camera, "position", (0.0, 0.0, 0.0)))[:3])
        delta = tuple(new_target[i] - old_target[i] for i in range(3))
        changed = any(abs(value) > 1e-9 for value in delta) or not bool(getattr(camera, "target_enabled", False))
        camera.target_enabled = True
        camera.target_position = new_target
        if allow_follow and bool(getattr(camera, "target_follow_enabled", False)) and any(abs(value) > 1e-9 for value in delta):
            new_position = tuple(old_position[i] + delta[i] for i in range(3))
            camera.position = new_position
            node = getattr(camera, "original_ref", None)
            if node is not None:
                try:
                    node.position = new_position
                except Exception:
                    pass
            changed = True
        if changed:
            try:
                camera.rotation = look_at_quaternion(camera.position, camera.target_position)
            except Exception:
                pass
            camera.apply_to_original()
        return changed

    def sync_camera_target_bindings(self, moved_node=None) -> bool:
        object_id = str(getattr(moved_node, "_gr_scene_object_id", "") or "") if moved_node is not None else ""
        changed = False
        for camera in self.camera_manager.get_all_cameras():
            target_object_id = str(getattr(camera, "target_object_id", "") or "")
            if not target_object_id:
                continue
            if object_id and target_object_id != object_id:
                continue
            target_position = self._scene_target_position(target_object_id)
            if target_position is None:
                continue
            changed = self._apply_camera_target_position(camera, target_position) or changed
        if changed:
            self.camera_manager._store_on_model()
            active = self.camera_manager.get_active_camera()
            if active is not None and self.is_camera_view_active():
                self.update_view_from_camera(active)
            self.cameraChanged.emit()
            self._request_render(fast=True, reason="camera target binding updated", camera=True, overlay=True, scene=True)
        return changed

    def align_active_camera_to_view(self):
        camera = self.camera_controller.align_active_camera_to_view()
        if camera is not None:
            self.cameraChanged.emit()
            self._request_render()
        return camera

    def align_camera_to_current_view(self, camera_id: str):
        camera = self.camera_manager.get_camera(camera_id)
        if camera is None:
            return None
        self._camera_adapter.update_camera_from_view(camera)
        self.cameraChanged.emit()
        self._request_render()
        return camera

    def align_view_to_camera(self, camera_id: str):
        return self.switch_to_camera(camera_id)

    def set_lock_view_to_camera(self, checked: Optional[bool] = None) -> None:
        self._lock_view_to_camera = bool(checked) if checked is not None else not self._lock_view_to_camera
        if hasattr(self, "lock_camera_button"):
            self.lock_camera_button.blockSignals(True)
            self.lock_camera_button.setChecked(self._lock_view_to_camera)
            self.lock_camera_button.blockSignals(False)

    def render_still_frame(self, settings=None, camera_id: str = "") -> str:
        camera = self.camera_manager.get_camera(camera_id) if camera_id else self.camera_manager.get_active_camera()
        return self._camera_frame_renderer.render_to_file(
            settings,
            camera,
            module_name=str(getattr(self.model, "name", "") or "scene"),
        )

    def _refresh_camera_view_combo(self) -> None:
        combo = getattr(self, "camera_view_combo", None)
        if combo is None:
            return
        current = self.camera_manager.active_camera_id if self._camera_view_active else ""
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Perspective", "")
        combo.addItem("Top", "__top__")
        combo.addItem("Front", "__front__")
        combo.addItem("Side", "__side__")
        for camera in self.camera_manager.get_all_cameras():
            combo.addItem(camera.name, camera.id)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _on_camera_view_combo_changed(self) -> None:
        combo = getattr(self, "camera_view_combo", None)
        if combo is None:
            return
        value = str(combo.currentData() or "")
        if not value:
            self.switch_to_perspective()
        elif value == "__top__":
            self.switch_to_perspective()
            self._snap_to_view("top")
        elif value == "__front__":
            self.switch_to_perspective()
            self._snap_to_view("front")
        elif value == "__side__":
            self.switch_to_perspective()
            self._snap_to_view("right")
        else:
            self.switch_to_camera(value)

__all__ = ("ViewportCameraWorkflowMixin",)
