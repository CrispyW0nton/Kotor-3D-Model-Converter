"""JSON serializer for GhostRigger KMAX scenes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .kmax_scene import KMAX_FILE_TYPE, KMAX_FILE_VERSION, KMaxScene, utc_now_iso
from .kmax_validator import KMaxValidator, KMaxValidationResult
from .scene_object import Transform
from .scene_object_instance import SceneObjectInstance


class KMaxSerializer:
    @classmethod
    def save(cls, scene: KMaxScene, path: str | Path) -> None:
        target = Path(path)
        if target.suffix.lower() != ".kmax":
            target = target.with_suffix(".kmax")
        scene.path = str(target)
        scene.modified_at = utc_now_iso()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(cls.to_dict(scene), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        scene.mark_clean()

    @classmethod
    def load(cls, path: str | Path) -> KMaxScene:
        source = Path(path)
        data = json.loads(source.read_text(encoding="utf-8"))
        scene = cls.from_dict(data)
        scene.path = str(source)
        scene.mark_clean()
        return scene

    @classmethod
    def to_dict(cls, scene: KMaxScene) -> dict[str, Any]:
        scene.sync_collections()
        return {
            "file_type": KMAX_FILE_TYPE,
            "file_version": KMAX_FILE_VERSION,
            "scene": {
                "id": scene.id,
                "name": scene.name,
                "description": str(scene.metadata.get("description", "")),
                "created_at": scene.created_at,
                "modified_at": scene.modified_at,
                "game": scene.game,
                "units": dict(scene.units),
            },
            "objects": [obj.to_dict() for obj in scene.objects],
            "models": [obj.to_dict() for obj in scene.model_instances],
            "materials": list(scene.materials),
            "textures": list(scene.textures),
            "lights": list(scene.lights),
            "cameras": list(scene.cameras),
            "sequences": list(scene.sequences),
            "kmap_references": list(scene.kmap_references),
            "settings": dict(scene.settings),
            "metadata": dict(scene.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KMaxScene:
        migrated = cls.migrate(data)
        validation = cls.validate(migrated)
        if validation.errors:
            raise ValueError("; ".join(validation.errors))
        scene_block = migrated.get("scene") or {}
        object_payloads = migrated.get("objects") or migrated.get("models") or []
        objects = [SceneObjectInstance.from_dict(obj) for obj in object_payloads if isinstance(obj, dict)]
        objects.extend(cls._legacy_asset_objects(migrated, objects))
        scene = KMaxScene(
            id=str(scene_block.get("id") or ""),
            name=str(scene_block.get("name") or "Untitled Scene"),
            created_at=str(scene_block.get("created_at") or utc_now_iso()),
            modified_at=str(scene_block.get("modified_at") or utc_now_iso()),
            game=str(scene_block.get("game") or "K1").upper(),
            units=dict(scene_block.get("units") or {"system_unit": "cm", "display_unit": "cm"}),
            objects=objects,
            lights=list(migrated.get("lights") or []),
            cameras=list(migrated.get("cameras") or []),
            sequences=list(migrated.get("sequences") or []),
            materials=list(migrated.get("materials") or []),
            textures=list(migrated.get("textures") or []),
            kmap_references=list(migrated.get("kmap_references") or []),
            settings=dict(migrated.get("settings") or {}),
            metadata=dict(migrated.get("metadata") or {}),
        )
        scene.sync_collections()
        return scene

    @classmethod
    def _legacy_asset_objects(
        cls,
        data: dict[str, Any],
        existing: list[SceneObjectInstance],
    ) -> list[SceneObjectInstance]:
        existing_ids = {obj.id for obj in existing}
        created: list[SceneObjectInstance] = []
        for object_type, key in (("light", "lights"), ("camera", "cameras")):
            for entry in data.get(key) or []:
                if not isinstance(entry, dict):
                    continue
                object_id = str(entry.get("scene_object_id") or entry.get("id") or "")
                if not object_id:
                    object_id = f"{object_type}-{uuid4().hex}"
                if object_id in existing_ids:
                    continue
                existing_ids.add(object_id)
                transform = entry.get("transform") if isinstance(entry.get("transform"), dict) else None
                if transform is None:
                    transform = {"position": entry.get("position", (0.0, 0.0, 0.0))}
                payload = dict(entry)
                payload["id"] = object_id
                payload.setdefault("scene_object_id", object_id)
                created.append(
                    SceneObjectInstance(
                        id=object_id,
                        name=str(entry.get("name") or object_type.title()),
                        object_type=object_type,
                        transform=Transform.from_dict(transform),
                        visible=bool(entry.get("visible", True)),
                        locked=bool(entry.get("locked", False)),
                        selected=bool(entry.get("selected", False)),
                        group_id=str(entry.get("group_id") or ""),
                        metadata={
                            object_type: payload,
                            "source": dict(entry.get("source") or {}),
                            "runtime": dict(entry.get("runtime") or {}),
                        },
                    )
                )
        return created

    @staticmethod
    def validate(data: dict[str, Any]) -> KMaxValidationResult:
        return KMaxValidator.validate(data)

    @staticmethod
    def migrate(data: dict[str, Any]) -> dict[str, Any]:
        version = int((data or {}).get("file_version") or 1)
        if version == KMAX_FILE_VERSION:
            return data
        if version < KMAX_FILE_VERSION:
            migrated = dict(data)
            migrated["file_version"] = KMAX_FILE_VERSION
            return migrated
        return data
