"""Prepare GhostRigger lights for modern scene export targets."""

from __future__ import annotations

from dataclasses import dataclass, field

from .light_model import GhostRiggerLight


@dataclass
class ExportLightRecord:
    name: str
    target_type: str
    position: tuple[float, float, float]
    rotation: tuple[float, float, float, float]
    color: tuple[float, float, float]
    intensity: float
    radius: float
    cone_angle: float
    area_size: float
    metadata: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class LightExportBridge:
    AREA_TARGETS = {"usd", "unreal", "3dsmax", "json"}

    def convert(self, lights: list[GhostRiggerLight], target: str) -> list[ExportLightRecord]:
        target_key = str(target or "json").lower()
        return [self._convert_one(light, target_key) for light in lights if not light.deleted]

    def _convert_one(self, light: GhostRiggerLight, target: str) -> ExportLightRecord:
        kind = light.type.replace("aurora_", "")
        if kind == "unknown":
            kind = "point"
        warnings: list[str] = []
        metadata = dict(light.metadata)
        metadata.update({"source_type": light.source_type, "ghostrigger_light_id": light.id})
        if light.ambient_only and target not in {"json", "usd"}:
            warnings.append("Target format does not support Aurora ambient-only flag. Stored in metadata.")
            metadata["ambient_only"] = True
        if kind == "area" and target not in self.AREA_TARGETS:
            warnings.append("Area light unsupported by this target. Converted to point approximation.")
            kind = "point"
            metadata["area_size"] = light.area_size
        if metadata.get("ies_profile") and target not in {"usd", "unreal", "json"}:
            warnings.append("Target format does not support IES preview. Stored as sidecar property.")
        return ExportLightRecord(
            name=light.name,
            target_type=kind,
            position=light.position,
            rotation=light.rotation,
            color=light.color,
            intensity=light.intensity,
            radius=light.radius,
            cone_angle=light.cone_angle,
            area_size=light.area_size,
            metadata=metadata,
            warnings=warnings,
        )
