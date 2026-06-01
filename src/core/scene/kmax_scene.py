"""GhostRigger KMAX scene data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .scene_object_instance import SceneObjectInstance

KMAX_FILE_TYPE = "GhostRiggerKMax"
KMAX_FILE_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class KMaxScene:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Untitled Scene"
    path: str = ""
    dirty: bool = False
    created_at: str = field(default_factory=utc_now_iso)
    modified_at: str = field(default_factory=utc_now_iso)
    game: str = "K1"
    units: dict[str, str] = field(default_factory=lambda: {"system_unit": "cm", "display_unit": "cm"})
    objects: list[SceneObjectInstance] = field(default_factory=list)
    model_instances: list[SceneObjectInstance] = field(default_factory=list)
    lights: list[dict[str, Any]] = field(default_factory=list)
    cameras: list[dict[str, Any]] = field(default_factory=list)
    sequences: list[dict[str, Any]] = field(default_factory=list)
    materials: list[dict[str, Any]] = field(default_factory=list)
    textures: list[dict[str, Any]] = field(default_factory=list)
    kmap_references: list[dict[str, Any]] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        if self.path:
            return Path(self.path).name
        return self.name or "Untitled Scene"

    def all_objects(self) -> list[SceneObjectInstance]:
        by_id: dict[str, SceneObjectInstance] = {}
        for obj in [*self.objects, *self.model_instances]:
            if obj and obj.id:
                by_id[obj.id] = obj
        return list(by_id.values())

    def sync_collections(self) -> None:
        self.model_instances = [obj for obj in self.objects if obj.object_type == "model"]
        self.lights = [self._asset_payload(obj, "light") for obj in self.objects if obj.object_type == "light"]
        self.cameras = [self._asset_payload(obj, "camera") for obj in self.objects if obj.object_type == "camera"]

    @staticmethod
    def _asset_payload(obj: SceneObjectInstance, key: str) -> dict[str, Any]:
        metadata = dict(getattr(obj, "metadata", {}) or {})
        payload = dict(metadata.get(key) or {})
        payload.setdefault("id", obj.id)
        payload["scene_object_id"] = obj.id
        payload["name"] = obj.name
        payload["visible"] = bool(obj.visible)
        payload["locked"] = bool(obj.locked)
        payload["selected"] = bool(obj.selected)
        payload["object_type"] = obj.object_type
        payload["transform"] = obj.transform.to_dict()
        source = dict(metadata.get("source") or {})
        if source:
            payload["source"] = source
        runtime = dict(metadata.get("runtime") or {})
        if runtime:
            payload["runtime"] = runtime
        return payload

    def mark_dirty(self) -> None:
        self.dirty = True
        self.modified_at = utc_now_iso()

    def mark_clean(self) -> None:
        self.dirty = False

    @classmethod
    def new(cls, name: str = "Untitled Scene", game: str = "K1") -> "KMaxScene":
        scene = cls(name=name or "Untitled Scene", game=(game or "K1").upper())
        scene.sync_collections()
        scene.mark_clean()
        return scene
