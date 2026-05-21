"""Light property tracks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..sequence_keyframe import InterpolationMode
from ..sequence_track import SequenceTrack, register_track


LIGHT_PROPERTIES = {
    "enabled",
    "visible",
    "color",
    "intensity",
    "radius",
    "cone_angle",
    "area_size",
    "ambient_only",
    "affects_diffuse",
    "affects_specular",
    "affects_lightmap",
    "affects_environment",
}


@register_track
@dataclass
class LightPropertyTrack(SequenceTrack):
    TRACK_TYPE = "Light Property"
    property_name: str = "intensity"

    def __post_init__(self) -> None:
        self.track_type = self.TRACK_TYPE
        self.property_name = str(self.property_name or self.metadata.get("property_name") or "intensity")
        self.metadata["property_name"] = self.property_name
        if not self.name or self.name == "Track":
            self.name = self.property_name
        super().__post_init__()

    def default_interpolation(self) -> InterpolationMode:
        if self.property_name in {"enabled", "visible", "ambient_only", "affects_diffuse", "affects_specular", "affects_lightmap", "affects_environment"}:
            return InterpolationMode.CONSTANT
        return InterpolationMode.LINEAR

    def serialize(self) -> dict[str, Any]:
        data = super().serialize()
        data["property_name"] = self.property_name
        data["metadata"]["property_name"] = self.property_name
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any] | None) -> "LightPropertyTrack":
        payload = dict(data or {})
        return cls(
            track_id=str(payload.get("track_id") or ""),
            name=str(payload.get("name") or payload.get("property_name") or "Light Property"),
            track_type=cls.TRACK_TYPE,
            enabled=bool(payload.get("enabled", True)),
            muted=bool(payload.get("muted", False)),
            locked=bool(payload.get("locked", False)),
            expanded=bool(payload.get("expanded", True)),
            color=str(payload.get("color") or "#FFD400"),
            keyframes=payload.get("keyframes", []) or [],
            parent_binding_id=str(payload.get("parent_binding_id") or ""),
            metadata=dict(payload.get("metadata", {}) or {}),
            property_name=str(payload.get("property_name") or dict(payload.get("metadata", {}) or {}).get("property_name") or "intensity"),
        )
