"""Command facade for camera creation and viewport alignment."""

from __future__ import annotations

from .camera_manager import CameraManager
from .camera_viewport_adapter import CameraViewportAdapter


class CameraController:
    def __init__(self, manager: CameraManager, adapter: CameraViewportAdapter) -> None:
        self.manager = manager
        self.adapter = adapter

    def create_camera(self, name: str | None = None, camera_type: str = "Cinematic Camera", *, from_current_view: bool = False):
        camera = self.manager.create_camera(name=name, camera_type=camera_type)
        if from_current_view:
            self.adapter.update_camera_from_view(camera)
        self.manager.select_camera(camera.id)
        return camera

    def create_camera_from_current_view(self, name: str | None = None, *, make_active: bool = True):
        camera = self.create_camera(name=name, camera_type="Cinematic Camera", from_current_view=True)
        if make_active:
            self.manager.set_active_camera(camera.id)
        return camera

    def align_active_camera_to_view(self):
        camera = self.manager.get_active_camera()
        if camera is None:
            return None
        self.adapter.update_camera_from_view(camera)
        return camera

    def align_view_to_selected_camera(self):
        selected = self.manager.selected_cameras()
        camera = selected[-1] if selected else None
        if camera is None:
            return None
        self.manager.set_active_camera(camera.id)
        self.adapter.update_view_from_camera(camera)
        return camera
