"""Editable GhostRigger light data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]
Color = tuple[float, float, float]


def _vec3(value: object, fallback: Vec3 = (0.0, 0.0, 0.0)) -> Vec3:
    try:
        seq = list(value)  # type: ignore[arg-type]
        return (float(seq[0]), float(seq[1]), float(seq[2]))
    except Exception:
        return fallback


def _quat(value: object, fallback: Quat = (0.0, 0.0, 0.0, 1.0)) -> Quat:
    try:
        seq = list(value)  # type: ignore[arg-type]
        return (float(seq[0]), float(seq[1]), float(seq[2]), float(seq[3]))
    except Exception:
        return fallback


@dataclass
class GhostRiggerLight:
    id: str = field(default_factory=lambda: f"light-{uuid4().hex}")
    name: str = "Light"
    source_type: str = "Editable"
    enabled: bool = True
    selected: bool = False
    visible: bool = True
    locked: bool = False
    type: str = "point"
    position: Vec3 = (0.0, 0.0, 0.0)
    rotation: Quat = (0.0, 0.0, 0.0, 1.0)
    color: Color = (1.0, 1.0, 1.0)
    radius: float = 5.0
    intensity: float = 1.0
    cone_angle: float = 45.0
    area_size: float = 1.0
    ambient_only: bool = False
    casts_shadows: bool = True
    affects_diffuse: bool = True
    affects_specular: bool = True
    affects_lightmap: bool = True
    affects_environment: bool = True
    group_id: str = ""
    original_ref: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    deleted: bool = False

    @classmethod
    def from_object(cls, obj: object, *, source_type: str = "Editable") -> "GhostRiggerLight":
        name = str(getattr(obj, "name", "") or "Light")
        light_id = str(getattr(obj, "_gr_light_id", "") or f"light-{uuid4().hex}")
        setattr(obj, "_gr_light_id", light_id)
        kind = str(getattr(obj, "light_kind", "point") or "point").strip().lower()
        return cls(
            id=light_id,
            name=name,
            source_type=str(getattr(obj, "source_type", source_type) or source_type),
            enabled=bool(getattr(obj, "light_enabled", True)),
            selected=bool(getattr(obj, "_gr_light_selected", False)),
            visible=not bool(getattr(obj, "_gr_light_hidden", False)),
            locked=bool(getattr(obj, "_gr_light_locked", False)),
            type=kind,
            position=_vec3(getattr(obj, "position", (0.0, 0.0, 0.0))),
            rotation=_quat(getattr(obj, "rotation", (0.0, 0.0, 0.0, 1.0))),
            color=_vec3(getattr(obj, "light_color", (1.0, 1.0, 1.0)), (1.0, 1.0, 1.0)),
            radius=max(0.0, float(getattr(obj, "light_radius", 5.0) or 0.0)),
            intensity=max(0.0, float(getattr(obj, "light_multiplier", 1.0) or 0.0)),
            cone_angle=max(1.0, min(179.0, float(getattr(obj, "light_cone_degrees", 45.0) or 45.0))),
            area_size=max(0.0, float(getattr(obj, "light_area_size", 1.0) or 0.0)),
            ambient_only=bool(getattr(obj, "light_ambient_only", False)),
            casts_shadows=bool(getattr(obj, "light_shadow", True)),
            affects_diffuse=bool(getattr(obj, "light_affects_diffuse", True)),
            affects_specular=bool(getattr(obj, "light_affects_specular", True)),
            affects_lightmap=bool(getattr(obj, "light_affects_lightmap", True)),
            affects_environment=bool(getattr(obj, "light_affects_environment", True)),
            group_id=str(getattr(obj, "_gr_light_group_id", "") or ""),
            original_ref=obj,
            metadata=dict(getattr(obj, "_gr_light_metadata", {}) or {}),
            deleted=bool(getattr(obj, "_gr_light_deleted", False)),
        )

    def apply_to_original(self) -> None:
        obj = self.original_ref
        if obj is None:
            return
        for attr, value in (
            ("name", self.name),
            ("position", tuple(self.position)),
            ("rotation", tuple(self.rotation)),
            ("light_kind", self.type),
            ("light_enabled", bool(self.enabled and not self.deleted)),
            ("light_color", tuple(self.color)),
            ("light_radius", float(self.radius)),
            ("light_multiplier", float(self.intensity)),
            ("light_cone_degrees", float(self.cone_angle)),
            ("light_area_size", float(self.area_size)),
            ("light_ambient_only", bool(self.ambient_only)),
            ("light_shadow", bool(self.casts_shadows)),
            ("light_affects_diffuse", bool(self.affects_diffuse)),
            ("light_affects_specular", bool(self.affects_specular)),
            ("light_affects_lightmap", bool(self.affects_lightmap)),
            ("light_affects_environment", bool(self.affects_environment)),
            ("source_type", self.source_type),
        ):
            try:
                setattr(obj, attr, value)
            except Exception:
                pass
        for attr, value in (
            ("_gr_light_id", self.id),
            ("_gr_light_selected", bool(self.selected)),
            ("_gr_light_hidden", not bool(self.visible)),
            ("_gr_light_locked", bool(self.locked)),
            ("_gr_light_group_id", self.group_id),
            ("_gr_light_metadata", dict(self.metadata)),
            ("_gr_light_deleted", bool(self.deleted)),
        ):
            try:
                setattr(obj, attr, value)
            except Exception:
                pass

    def copy_generated(self, *, name: str | None = None) -> "GhostRiggerLight":
        data = GhostRiggerLight(
            name=name or f"{self.name} Copy",
            source_type="Editable",
            enabled=self.enabled,
            visible=self.visible,
            locked=False,
            type=self.type,
            position=self.position,
            rotation=self.rotation,
            color=self.color,
            radius=self.radius,
            intensity=self.intensity,
            cone_angle=self.cone_angle,
            area_size=self.area_size,
            ambient_only=self.ambient_only,
            casts_shadows=self.casts_shadows,
            affects_diffuse=self.affects_diffuse,
            affects_specular=self.affects_specular,
            affects_lightmap=self.affects_lightmap,
            affects_environment=self.affects_environment,
            metadata=dict(self.metadata),
        )
        return data
