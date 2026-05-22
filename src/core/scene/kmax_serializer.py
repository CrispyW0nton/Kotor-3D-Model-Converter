"""JSON serializer for GhostRigger KMAX scenes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .kmax_scene import KMAX_FILE_TYPE, KMAX_FILE_VERSION, KMaxScene, utc_now_iso
from .kmax_validator import KMaxValidator, KMaxValidationResult
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
