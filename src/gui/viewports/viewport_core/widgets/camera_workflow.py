"""ViewportCameraWorkflow methods for the Qt viewport widget."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportCameraWorkflowMixin:
    def refresh_cameras(self) -> None:
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
