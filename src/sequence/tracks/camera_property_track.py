"""Camera property tracks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..sequence_track import SequenceTrack, register_track


CAMERA_PROPERTIES = {
    "focal_length_mm",
    "field_of_view_degrees",
    "aperture_f_stop",
    "focus_distance",
    "near_clip",
    "far_clip",
    "letterbox_ratio",
    "show_letterbox",
    "sensor_width_mm",
    "sensor_height_mm",
}


@register_track
@dataclass
class CameraPropertyTrack(SequenceTrack):
    TRACK_TYPE = "Camera Property"
    property_name: str = "focal_length_mm"

    def __post_init__(self) -> None:
        self.track_type = self.TRACK_TYPE
        self.property_name = str(self.property_name or self.metadata.get("property_name") or "focal_length_mm")
        self.metadata["property_name"] = self.property_name
        if not self.name or self.name == "Track":
            self.name = self.property_name
        super().__post_init__()

    def serialize(self) -> dict[str, Any]:
        data = super().serialize()
        data["property_name"] = self.property_name
        data["metadata"]["property_name"] = self.property_name
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "CameraPropertyTrack":
        payload = dict(data or {})
        return cls(
            track_id=str(payload.get("track_id") or ""),
            name=str(payload.get("name") or payload.get("property_name") or "Camera Property"),
            track_type=cls.TRACK_TYPE,
            enabled=bool(payload.get("enabled", True)),
            muted=bool(payload.get("muted", False)),
            locked=bool(payload.get("locked", False)),
            expanded=bool(payload.get("expanded", True)),
            color=str(payload.get("color") or "#8FB3FF"),
            keyframes=payload.get("keyframes", []) or [],
            parent_binding_id=str(payload.get("parent_binding_id") or ""),
            metadata=dict(payload.get("metadata", {}) or {}),
            property_name=str(payload.get("property_name") or dict(payload.get("metadata", {}) or {}).get("property_name") or "focal_length_mm"),
        )
