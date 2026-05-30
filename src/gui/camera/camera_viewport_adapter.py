"""Bridge between scene cameras and the existing ArcBall viewport camera."""

from __future__ import annotations

import math

from src.math.camera_math import add, camera_forward, length, look_at_quaternion, mul, sub
from .camera_model import GhostRiggerCamera


class CameraViewportAdapter:
    def __init__(self, arcball_camera) -> None:
        self.arcball_camera = arcball_camera
        self._perspective_state: dict | None = None

    def save_perspective_state(self) -> None:
        cam = self.arcball_camera
        self._perspective_state = {
            "azimuth": float(getattr(cam, "azimuth", 90.0)),
            "elevation": float(getattr(cam, "elevation", 20.0)),
            "distance": float(getattr(cam, "distance", 5.0)),
            "target": list(getattr(cam, "target", [0.0, 0.0, 0.0])),
            "fov": float(getattr(cam, "fov", 45.0)),
            "near": float(getattr(cam, "_near", 0.01)),
            "far": float(getattr(cam, "_far", 1000.0)),
        }

    def restore_perspective_state(self) -> None:
        if not self._perspective_state:
            return
        cam = self.arcball_camera
        for key, value in self._perspective_state.items():
            if key == "near":
                setattr(cam, "_near", value)
            elif key == "far":
                setattr(cam, "_far", value)
            else:
                setattr(cam, key, list(value) if key == "target" else value)

    def update_view_from_camera(self, camera: GhostRiggerCamera) -> None:
        cam = self.arcball_camera
        target = self._resolve_target(camera)
        offset = sub(camera.position, target)
        distance = max(0.05, length(offset))
        cam.target = [float(target[0]), float(target[1]), float(target[2])]
        cam.distance = distance
        cam.azimuth = math.degrees(math.atan2(offset[1], offset[0])) % 360.0
        cam.elevation = max(-85.0, min(85.0, math.degrees(math.asin(max(-1.0, min(1.0, offset[2] / distance))))))
        cam.fov = float(camera.field_of_view_degrees)
        cam._near = max(0.001, float(camera.near_clip))
        cam._far = max(cam._near + 1.0, float(camera.far_clip))

    def update_camera_from_view(self, camera: GhostRiggerCamera) -> None:
        cam = self.arcball_camera
        eye = tuple(float(v) for v in cam.eye())
        target = tuple(float(v) for v in getattr(cam, "target", (0.0, 0.0, 0.0))[:3])
        camera.position = eye
        camera.target_position = target
        camera.focus_distance = length(sub(target, eye))
        camera.rotation = look_at_quaternion(eye, target)
        camera.set_field_of_view(float(getattr(cam, "fov", camera.field_of_view_degrees)))
        camera.near_clip = float(getattr(cam, "_near", camera.near_clip))
        camera.far_clip = float(getattr(cam, "_far", camera.far_clip))
        camera.apply_to_original()

    def _resolve_target(self, camera: GhostRiggerCamera):
        if camera.target_enabled:
            return tuple(camera.target_position)
        distance = camera.focus_distance if camera.focus_distance > 0.001 else 100.0
        return add(camera.position, mul(camera_forward(camera.rotation), distance))
