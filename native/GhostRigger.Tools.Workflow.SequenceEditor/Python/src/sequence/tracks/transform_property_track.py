"""Individual transform property animation tracks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..sequence_track import SequenceTrack, register_track


TRANSFORM_PROPERTIES = {
    "position",
    "position_x",
    "position_y",
    "position_z",
    "rotation",
    "rotation_x",
    "rotation_y",
    "rotation_z",
    "scale",
    "scale_x",
    "scale_y",
    "scale_z",
}


TRANSFORM_PROPERTY_LABELS = {
    "position": "Position",
    "position_x": "Position X",
    "position_y": "Position Y",
    "position_z": "Position Z",
    "rotation": "Rotation",
    "rotation_x": "Rotation X",
    "rotation_y": "Rotation Y",
    "rotation_z": "Rotation Z",
    "scale": "Scale",
    "scale_x": "Scale X",
    "scale_y": "Scale Y",
    "scale_z": "Scale Z",
}


@register_track
@dataclass
class TransformPropertyTrack(SequenceTrack):
    TRACK_TYPE = "Transform Property"
    property_name: str = "position"

    def __post_init__(self) -> None:
        self.track_type = self.TRACK_TYPE
        self.property_name = str(self.property_name or self.metadata.get("property_name") or "position")
        if self.property_name not in TRANSFORM_PROPERTIES:
            self.property_name = "position"
        self.metadata["property_name"] = self.property_name
        if not self.name or self.name == "Track":
            self.name = TRANSFORM_PROPERTY_LABELS.get(self.property_name, self.property_name)
        super().__post_init__()

    def serialize(self) -> dict[str, Any]:
        data = super().serialize()
        data["property_name"] = self.property_name
        data["metadata"]["property_name"] = self.property_name
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "TransformPropertyTrack":
        payload = dict(data or {})
        property_name = str(payload.get("property_name") or dict(payload.get("metadata", {}) or {}).get("property_name") or "position")
        return cls(
            track_id=str(payload.get("track_id") or ""),
            name=str(payload.get("name") or TRANSFORM_PROPERTY_LABELS.get(property_name, property_name)),
            track_type=cls.TRACK_TYPE,
            enabled=bool(payload.get("enabled", True)),
            muted=bool(payload.get("muted", False)),
            locked=bool(payload.get("locked", False)),
            expanded=bool(payload.get("expanded", True)),
            color=str(payload.get("color") or "#00D7B5"),
            keyframes=payload.get("keyframes", []) or [],
            parent_binding_id=str(payload.get("parent_binding_id") or ""),
            metadata=dict(payload.get("metadata", {}) or {}),
            property_name=property_name,
        )
