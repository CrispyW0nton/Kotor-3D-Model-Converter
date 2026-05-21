"""Scene object instances stored in KMAX files."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .scene_object import Transform
from .scene_resource_ref import SceneResourceRef


@dataclass
class SceneObjectInstance:
    id: str
    name: str
    object_type: str = "model"
    source_ref: SceneResourceRef = field(default_factory=SceneResourceRef)
    transform: Transform = field(default_factory=Transform)
    visible: bool = True
    locked: bool = False
    selected: bool = False
    group_id: str = ""
    material_overrides: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        metadata = {
            key: value
            for key, value in self.metadata.items()
            if not str(key).startswith("_runtime")
        }
        return {
            "id": self.id,
            "name": self.name,
            "object_type": self.object_type,
            "source_ref": self.source_ref.to_dict(),
            "transform": self.transform.to_dict(),
            "visible": bool(self.visible),
            "locked": bool(self.locked),
            "selected": bool(self.selected),
            "group_id": self.group_id,
            "material_overrides": dict(self.material_overrides),
            "metadata": metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneObjectInstance":
        return cls(
            id=str(data.get("id") or ""),
            name=str(data.get("name") or "Scene Object"),
            object_type=str(data.get("object_type") or "model"),
            source_ref=SceneResourceRef.from_dict(data.get("source_ref") or data.get("resource_ref")),
            transform=Transform.from_dict(data.get("transform")),
            visible=bool(data.get("visible", True)),
            locked=bool(data.get("locked", False)),
            selected=bool(data.get("selected", False)),
            group_id=str(data.get("group_id") or ""),
            material_overrides=dict(data.get("material_overrides") or {}),
            metadata=dict(data.get("metadata") or {}),
        )
