"""Serializable cinematic camera scene object."""

from __future__ import annotations

from dataclasses import dataclass, fields, field
from typing import Any
from uuid import uuid4

from src.math.camera_math import (
    Vec3,
    Quat,
    clamp,
    focal_length_to_fov,
    fov_to_focal_length,
    quat,
    vec3,
)

CAMERA_TYPES = ("Free Camera", "Target Camera", "Cinematic Camera", "Orthographic Camera")


@dataclass
class GhostRiggerCamera:
    id: str = field(default_factory=lambda: f"camera-{uuid4().hex}")
    name: str = "Camera"
    enabled: bool = True
    visible: bool = True
    locked: bool = False
    selected: bool = False
    position: Vec3 = (0.0, -5.0, 2.0)
    rotation: Quat = (0.0, 0.0, 0.0, 1.0)
    target_enabled: bool = False
    target_position: Vec3 = (0.0, 0.0, 1.0)
    target_object_id: str = ""
    focal_length_mm: float = 35.0
    field_of_view_degrees: float = field(default_factory=lambda: focal_length_to_fov(36.0, 35.0))
    sensor_width_mm: float = 36.0
    sensor_height_mm: float = 24.0
    aperture_f_stop: float = 5.6
    focus_distance: float = 1000.0
    near_clip: float = 1.0
    far_clip: float = 100000.0
    aspect_ratio_width: int = 16
    aspect_ratio_height: int = 9
    resolution_width: int = 1920
    resolution_height: int = 1080
    show_safe_frame: bool = True
    show_letterbox: bool = True
    letterbox_ratio: float = 2.35
    camera_type: str = "Cinematic Camera"
    metadata: dict[str, Any] = field(default_factory=dict)
    original_ref: Any = None
    deleted: bool = False

    def __post_init__(self) -> None:
        self.field_of_view_degrees = clamp(float(self.field_of_view_degrees), 1.0, 179.0)
        self.focal_length_mm = max(0.001, float(self.focal_length_mm))
        if self.camera_type not in CAMERA_TYPES:
            self.camera_type = "Cinematic Camera"

    @classmethod
    def from_object(cls, obj: object) -> "GhostRiggerCamera":
        camera_id = str(getattr(obj, "_gr_camera_id", "") or f"camera-{uuid4().hex}")
        try:
            setattr(obj, "_gr_camera_id", camera_id)
        except Exception:
            pass
        payload = dict(getattr(obj, "_gr_camera_data", {}) or {})
        payload.setdefault("id", camera_id)
        payload.setdefault("name", str(getattr(obj, "name", "") or "Camera"))
        payload.setdefault("position", vec3(getattr(obj, "position", (0.0, -5.0, 2.0))))
        payload.setdefault("rotation", quat(getattr(obj, "rotation", (0.0, 0.0, 0.0, 1.0))))
        payload.setdefault("selected", bool(getattr(obj, "_gr_camera_selected", False)))
        payload.setdefault("visible", not bool(getattr(obj, "_gr_camera_hidden", False)))
        payload.setdefault("locked", bool(getattr(obj, "_gr_camera_locked", False)))
        payload.setdefault("deleted", bool(getattr(obj, "_gr_camera_deleted", False)))
        camera = cls.from_dict(payload)
        camera.original_ref = obj
        return camera

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "GhostRiggerCamera":
        raw = dict(data or {})
        raw["position"] = vec3(raw.get("position", (0.0, -5.0, 2.0)))
        raw["rotation"] = quat(raw.get("rotation", (0.0, 0.0, 0.0, 1.0)))
        raw["target_position"] = vec3(raw.get("target_position", (0.0, 0.0, 1.0)))
        for key in ("aspect_ratio_width", "aspect_ratio_height", "resolution_width", "resolution_height"):
            try:
                raw[key] = max(1, int(raw.get(key, getattr(cls(), key))))
            except Exception:
                raw[key] = getattr(cls(), key)
        allowed = {field.name for field in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        clean = {key: value for key, value in raw.items() if key in allowed and key != "original_ref"}
        camera = cls(**clean)
        camera.validate()
        return camera

    def to_dict(self) -> dict[str, Any]:
        return {
            item.name: getattr(self, item.name)
            for item in fields(self)
            if item.name != "original_ref"
        }

    def serialize(self) -> dict[str, Any]:
        return self.to_dict()

    def apply_to_original(self) -> None:
        obj = self.original_ref
        if obj is None:
            return
        for attr, value in (
            ("name", self.name),
            ("position", tuple(self.position)),
            ("rotation", tuple(self.rotation)),
            ("is_camera", True),
            ("children", list(getattr(obj, "children", []) or [])),
        ):
            try:
                setattr(obj, attr, value)
            except Exception:
                pass
        for attr, value in (
            ("_gr_camera_id", self.id),
            ("_gr_camera_data", self.to_dict()),
            ("_gr_camera_selected", bool(self.selected)),
            ("_gr_camera_hidden", not bool(self.visible)),
            ("_gr_camera_locked", bool(self.locked)),
            ("_gr_camera_deleted", bool(self.deleted)),
            ("_gr_helper_size", float(self.metadata.get("helper_size", 1.0))),
        ):
            try:
                setattr(obj, attr, value)
            except Exception:
                pass

    def set_focal_length(self, value: float) -> None:
        self.focal_length_mm = max(0.001, float(value))
        self.field_of_view_degrees = focal_length_to_fov(self.sensor_width_mm, self.focal_length_mm)

    def set_field_of_view(self, value: float) -> None:
        self.field_of_view_degrees = clamp(float(value), 1.0, 179.0)
        self.focal_length_mm = fov_to_focal_length(self.sensor_width_mm, self.field_of_view_degrees)

    def set_sensor(self, width_mm: float, height_mm: float) -> None:
        self.sensor_width_mm = max(0.001, float(width_mm))
        self.sensor_height_mm = max(0.001, float(height_mm))
        self.set_focal_length(self.focal_length_mm)

    def validate(self) -> None:
        self.enabled = bool(self.enabled)
        self.visible = bool(self.visible)
        self.locked = bool(self.locked)
        self.selected = bool(self.selected)
        self.position = vec3(self.position)
        self.rotation = quat(self.rotation)
        self.target_position = vec3(self.target_position)
        self.focal_length_mm = max(0.001, float(self.focal_length_mm))
        self.field_of_view_degrees = clamp(float(self.field_of_view_degrees), 1.0, 179.0)
        self.sensor_width_mm = max(0.001, float(self.sensor_width_mm))
        self.sensor_height_mm = max(0.001, float(self.sensor_height_mm))
        self.aperture_f_stop = max(0.1, float(self.aperture_f_stop))
        self.focus_distance = max(0.0, float(self.focus_distance))
        self.near_clip = max(0.001, float(self.near_clip))
        self.far_clip = max(self.near_clip + 1.0, float(self.far_clip))
        self.aspect_ratio_width = max(1, int(self.aspect_ratio_width))
        self.aspect_ratio_height = max(1, int(self.aspect_ratio_height))
        self.resolution_width = max(1, int(self.resolution_width))
        self.resolution_height = max(1, int(self.resolution_height))
        self.letterbox_ratio = max(0.1, float(self.letterbox_ratio))
        if self.camera_type not in CAMERA_TYPES:
            self.camera_type = "Cinematic Camera"

    def copy_generated(self, *, name: str | None = None) -> "GhostRiggerCamera":
        data = self.to_dict()
        data.pop("id", None)
        data["name"] = name or f"{self.name} Copy"
        data["locked"] = False
        dup = GhostRiggerCamera.from_dict(data)
        dup.position = (self.position[0] + 0.35, self.position[1] + 0.35, self.position[2])
        dup.target_position = (self.target_position[0] + 0.35, self.target_position[1] + 0.35, self.target_position[2])
        return dup
