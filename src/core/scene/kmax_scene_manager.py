"""Active KMAX scene manager for the main GhostRigger editor."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.core.camera.camera_model import CAMERA_TYPES, GhostRiggerCamera
from src.core.lighting.light_model import GhostRiggerLight

from .kmax_scene import KMaxScene
from .kmax_serializer import KMaxSerializer
from .scene_object import PivotData, Transform
from .scene_object_instance import SceneObjectInstance
from .scene_resource_ref import SceneResourceRef


class KMaxSceneManager:
    """Owns the active editable GhostRigger scene."""

    def __init__(self, scene: KMaxScene | None = None) -> None:
        self.active_scene: KMaxScene = scene or KMaxScene.new()

    def create_new_scene(self, name: str = "Untitled Scene", game: str = "K1") -> KMaxScene:
        self.active_scene = KMaxScene.new(name=name, game=game)
        return self.active_scene

    def clear_scene(self) -> None:
        self.active_scene.objects.clear()
        self.active_scene.model_instances.clear()
        self.clear_selection()
        self.mark_dirty()

    def load_kmax(self, path: str | Path) -> KMaxScene:
        self.active_scene = KMaxSerializer.load(path)
        return self.active_scene

    def save_kmax(self, path: str | Path | None = None) -> None:
        if not (path or self.active_scene.path):
            raise ValueError("No KMAX path supplied.")
        target = Path(path or self.active_scene.path)
        KMaxSerializer.save(self.active_scene, target)

    def save_kmax_as(self, path: str | Path) -> None:
        self.save_kmax(path)

    def mark_dirty(self) -> None:
        self.active_scene.mark_dirty()

    def is_dirty(self) -> bool:
        return bool(self.active_scene.dirty)

    def add_model_instance(
        self,
        resource_ref: SceneResourceRef,
        transform: Transform | dict[str, Any] | None = None,
        *,
        name: str = "",
        runtime_model: Any = None,
        select: bool = True,
    ) -> SceneObjectInstance:
        if isinstance(transform, dict):
            transform_obj = Transform.from_dict(transform)
        else:
            transform_obj = transform or Transform()
        object_id = str(uuid4())
        label = name or resource_ref.original_name or resource_ref.resref or Path(resource_ref.source_path).stem or "Model"
        instance = SceneObjectInstance(
            id=object_id,
            name=self._unique_object_name(label),
            object_type="model",
            source_ref=resource_ref,
            transform=transform_obj,
        )
        if runtime_model is not None:
            instance.metadata["_runtime_model"] = runtime_model
        self.active_scene.objects.append(instance)
        self.active_scene.sync_collections()
        if select:
            self.select_object(instance.id)
        self.mark_dirty()
        return instance

    def add_camera_object(
        self,
        camera_type: str = "Cinematic Camera",
        transform: Transform | dict[str, Any] | None = None,
        *,
        name: str = "",
        properties: dict[str, Any] | GhostRiggerCamera | None = None,
        object_id: str | None = None,
        select: bool = True,
    ) -> SceneObjectInstance:
        transform_obj = Transform.from_dict(transform) if isinstance(transform, dict) else (transform or Transform())
        object_id = str(object_id or uuid4())
        payload = properties.to_dict() if isinstance(properties, GhostRiggerCamera) else dict(properties or {})
        camera = GhostRiggerCamera.from_dict(
            {
                **payload,
                "id": object_id,
                "name": name or payload.get("name") or self._next_asset_name("Camera"),
                "camera_type": self._normalize_camera_type(camera_type or payload.get("camera_type")),
                "position": transform_obj.position,
                "visible": bool(payload.get("visible", True)),
                "locked": bool(payload.get("locked", False)),
                "selected": bool(select),
            }
        )
        if camera.camera_type == "Target Camera":
            camera.target_enabled = True
        instance = SceneObjectInstance(
            id=object_id,
            name=self._unique_object_name(camera.name),
            object_type="camera",
            transform=transform_obj,
            visible=camera.visible,
            locked=camera.locked,
            selected=False,
            metadata={"camera": self._camera_payload(camera, transform_obj)},
        )
        self._sync_asset_metadata_from_object(instance)
        self.active_scene.objects.append(instance)
        self.active_scene.sync_collections()
        if select:
            self.select_object(instance.id)
        self.mark_dirty()
        return instance

    def add_light_object(
        self,
        light_type: str = "point",
        transform: Transform | dict[str, Any] | None = None,
        *,
        name: str = "",
        properties: dict[str, Any] | GhostRiggerLight | None = None,
        object_id: str | None = None,
        select: bool = True,
    ) -> SceneObjectInstance:
        transform_obj = Transform.from_dict(transform) if isinstance(transform, dict) else (transform or Transform())
        object_id = str(object_id or uuid4())
        payload = properties.__dict__.copy() if isinstance(properties, GhostRiggerLight) else dict(properties or {})
        clean = {
            key: value
            for key, value in {
                **payload,
                "id": object_id,
                "name": name or payload.get("name") or self._next_asset_name("Light"),
                "type": self._normalize_light_type(light_type or payload.get("type")),
                "position": transform_obj.position,
                "visible": bool(payload.get("visible", True)),
                "locked": bool(payload.get("locked", False)),
                "selected": bool(select),
                "source_type": str(payload.get("source_type") or "Scene"),
            }.items()
            if key in GhostRiggerLight.__dataclass_fields__ and key != "original_ref"  # type: ignore[attr-defined]
        }
        light = GhostRiggerLight(**clean)
        instance = SceneObjectInstance(
            id=object_id,
            name=self._unique_object_name(light.name),
            object_type="light",
            transform=transform_obj,
            visible=light.visible,
            locked=light.locked,
            selected=False,
            group_id=light.group_id,
            metadata={"light": self._light_payload(light, transform_obj)},
        )
        self._sync_asset_metadata_from_object(instance)
        self.active_scene.objects.append(instance)
        self.active_scene.sync_collections()
        if select:
            self.select_object(instance.id)
        self.mark_dirty()
        return instance

    def remove_object(self, object_id: str) -> bool:
        before = len(self.active_scene.objects)
        self.active_scene.objects = [obj for obj in self.active_scene.objects if obj.id != object_id]
        self.active_scene.sync_collections()
        changed = len(self.active_scene.objects) != before
        if changed:
            self.mark_dirty()
        return changed

    def remove_camera_object(self, object_id: str) -> bool:
        obj = self._find_object(object_id)
        return bool(obj is not None and obj.object_type == "camera" and self.remove_object(object_id))

    def remove_light_object(self, object_id: str) -> bool:
        obj = self._find_object(object_id)
        return bool(obj is not None and obj.object_type == "light" and self.remove_object(object_id))

    def duplicate_object(self, object_id: str) -> SceneObjectInstance | None:
        source = self._find_object(object_id)
        if source is None:
            return None
        duplicate = copy.deepcopy(source)
        duplicate.id = str(uuid4())
        duplicate.name = self._unique_object_name(f"{source.name}_copy")
        duplicate.selected = False
        duplicate.metadata.pop("_runtime_model", None)
        if duplicate.object_type in {"camera", "light"}:
            self._retarget_asset_metadata(duplicate)
        self.active_scene.objects.append(duplicate)
        self.active_scene.sync_collections()
        self.select_object(duplicate.id)
        self.mark_dirty()
        return duplicate

    def duplicate_camera_object(self, object_id: str) -> SceneObjectInstance | None:
        obj = self._find_object(object_id)
        return self.duplicate_object(object_id) if obj is not None and obj.object_type == "camera" else None

    def duplicate_light_object(self, object_id: str) -> SceneObjectInstance | None:
        obj = self._find_object(object_id)
        return self.duplicate_object(object_id) if obj is not None and obj.object_type == "light" else None

    def select_object(self, object_id: str) -> None:
        for obj in self.active_scene.objects:
            obj.selected = obj.id == object_id
            self._sync_asset_metadata_from_object(obj)
        self.active_scene.sync_collections()
        self.mark_dirty()

    def clear_selection(self) -> None:
        changed = False
        for obj in self.active_scene.objects:
            changed = changed or obj.selected
            obj.selected = False
            self._sync_asset_metadata_from_object(obj)
        if changed:
            self.active_scene.sync_collections()
            self.mark_dirty()

    def get_selected_objects(self) -> list[SceneObjectInstance]:
        return [obj for obj in self.active_scene.objects if obj.selected]

    def get_scene_objects(self) -> list[SceneObjectInstance]:
        return list(self.active_scene.objects)

    def serialize_scene(self) -> dict[str, Any]:
        return KMaxSerializer.to_dict(self.active_scene)

    def deserialize_scene(self, data: dict[str, Any]) -> KMaxScene:
        self.active_scene = KMaxSerializer.from_dict(data)
        self.active_scene.mark_clean()
        return self.active_scene

    def rename_object(self, object_id: str, name: str) -> bool:
        obj = self._find_object(object_id)
        clean = str(name or "").strip()
        if obj is None or not clean:
            return False
        obj.name = self._unique_object_name(clean) if clean != obj.name else clean
        self._sync_asset_metadata_from_object(obj)
        self.active_scene.sync_collections()
        self.mark_dirty()
        return True

    def set_object_visibility(self, object_id: str, visible: bool) -> bool:
        obj = self._find_object(object_id)
        if obj is None:
            return False
        obj.visible = bool(visible)
        self._sync_asset_metadata_from_object(obj)
        self.active_scene.sync_collections()
        self.mark_dirty()
        return True

    def set_object_locked(self, object_id: str, locked: bool) -> bool:
        obj = self._find_object(object_id)
        if obj is None:
            return False
        obj.locked = bool(locked)
        self._sync_asset_metadata_from_object(obj)
        self.active_scene.sync_collections()
        self.mark_dirty()
        return True

    def update_camera_properties(self, object_id: str, **changes: Any) -> bool:
        obj = self._find_object(object_id)
        if obj is None or obj.object_type != "camera":
            return False
        payload = dict(obj.metadata.get("camera") or {})
        payload.update(changes)
        payload["id"] = obj.id
        payload["scene_object_id"] = obj.id
        camera = GhostRiggerCamera.from_dict(payload)
        obj.name = camera.name or obj.name
        obj.visible = bool(camera.visible)
        obj.locked = bool(camera.locked)
        obj.selected = bool(camera.selected)
        obj.transform.position = tuple(float(v) for v in camera.position[:3])
        obj.metadata["camera"] = self._camera_payload(camera, obj.transform)
        self.active_scene.sync_collections()
        self.mark_dirty()
        return True

    def update_light_properties(self, object_id: str, **changes: Any) -> bool:
        obj = self._find_object(object_id)
        if obj is None or obj.object_type != "light":
            return False
        payload = dict(obj.metadata.get("light") or {})
        payload.update(changes)
        payload["id"] = obj.id
        payload["scene_object_id"] = obj.id
        clean = {
            key: value
            for key, value in payload.items()
            if key in GhostRiggerLight.__dataclass_fields__ and key != "original_ref"  # type: ignore[attr-defined]
        }
        light = GhostRiggerLight(**clean)
        obj.name = light.name or obj.name
        obj.visible = bool(light.visible)
        obj.locked = bool(light.locked)
        obj.selected = bool(light.selected)
        obj.group_id = light.group_id
        obj.transform.position = tuple(float(v) for v in light.position[:3])
        obj.metadata["light"] = self._light_payload(light, obj.transform)
        self.active_scene.sync_collections()
        self.mark_dirty()
        return True

    def update_object_transform(
        self,
        object_id: str,
        *,
        position: tuple[float, float, float] | None = None,
        rotation: tuple[float, float, float] | None = None,
        scale: tuple[float, float, float] | None = None,
    ) -> bool:
        obj = self._find_object(object_id)
        if obj is None:
            return False
        if position is not None:
            obj.transform.position = tuple(float(v) for v in position[:3])
        if rotation is not None:
            obj.transform.rotation = tuple(float(v) for v in rotation[:3])
        if scale is not None:
            obj.transform.scale = tuple(float(v) for v in scale[:3])
        self._sync_asset_metadata_from_object(obj)
        self.active_scene.sync_collections()
        self.mark_dirty()
        return True

    def update_object_pivot(
        self,
        object_id: str,
        *,
        position_local: tuple[float, float, float] | None = None,
        rotation_local: tuple[float, float, float] | None = None,
        enabled: bool | None = None,
    ) -> bool:
        obj = self._find_object(object_id)
        if obj is None or bool(getattr(obj, "locked", False)):
            return False
        if getattr(obj, "pivot", None) is None:
            obj.pivot = PivotData()
        if position_local is not None:
            obj.pivot.position_local = tuple(float(v) for v in position_local[:3])
        if rotation_local is not None:
            obj.pivot.rotation_local = tuple(float(v) for v in rotation_local[:3])
        if enabled is not None:
            obj.pivot.enabled = bool(enabled)
        obj.pivot = obj.pivot.sanitized()
        self.mark_dirty()
        return True

    def _find_object(self, object_id: str) -> SceneObjectInstance | None:
        return next((obj for obj in self.active_scene.objects if obj.id == object_id), None)

    def _unique_object_name(self, base: str) -> str:
        clean = str(base or "Object").strip() or "Object"
        names = {obj.name for obj in self.active_scene.objects}
        if clean not in names:
            return clean
        index = 2
        while f"{clean}_{index:03d}" in names:
            index += 1
        return f"{clean}_{index:03d}"

    def _next_asset_name(self, base: str) -> str:
        existing = {obj.name for obj in self.active_scene.objects}
        for index in range(1, 10000):
            candidate = f"{base}{index:03d}"
            if candidate not in existing:
                return candidate
        return base

    @staticmethod
    def _normalize_camera_type(value: str | None) -> str:
        raw = str(value or "").strip()
        text = raw.lower().replace("_", " ")
        mapping = {
            "free": "Free Camera",
            "free camera": "Free Camera",
            "target": "Target Camera",
            "target camera": "Target Camera",
            "cine": "Cinematic Camera",
            "cinematic": "Cinematic Camera",
            "cinematic camera": "Cinematic Camera",
            "orthographic": "Orthographic Camera",
            "orthographic camera": "Orthographic Camera",
        }
        return mapping.get(text, raw if raw in CAMERA_TYPES else "Cinematic Camera")

    @staticmethod
    def _normalize_light_type(value: str | None) -> str:
        text = str(value or "point").strip().lower().replace(" ", "_")
        return text if text in {"point", "spot", "directional", "area", "ambient"} else "point"

    @staticmethod
    def _camera_payload(camera: GhostRiggerCamera, transform: Transform) -> dict[str, Any]:
        payload = camera.serialize()
        payload["id"] = camera.id
        payload["scene_object_id"] = camera.id
        payload["position"] = [float(v) for v in transform.position]
        payload["transform"] = transform.to_dict()
        return payload

    @staticmethod
    def _light_payload(light: GhostRiggerLight, transform: Transform) -> dict[str, Any]:
        payload = {
            key: value
            for key, value in light.__dict__.items()
            if key != "original_ref" and not str(key).startswith("_")
        }
        payload["id"] = light.id
        payload["scene_object_id"] = light.id
        payload["position"] = [float(v) for v in transform.position]
        payload["transform"] = transform.to_dict()
        return payload

    def _sync_asset_metadata_from_object(self, obj: SceneObjectInstance) -> None:
        if obj.object_type == "camera":
            payload = dict(obj.metadata.get("camera") or {})
            payload.update(
                {
                    "id": obj.id,
                    "scene_object_id": obj.id,
                    "name": obj.name,
                    "visible": bool(obj.visible),
                    "locked": bool(obj.locked),
                    "selected": bool(obj.selected),
                    "position": [float(v) for v in obj.transform.position],
                    "transform": obj.transform.to_dict(),
                }
            )
            obj.metadata["camera"] = payload
        elif obj.object_type == "light":
            payload = dict(obj.metadata.get("light") or {})
            payload.update(
                {
                    "id": obj.id,
                    "scene_object_id": obj.id,
                    "name": obj.name,
                    "visible": bool(obj.visible),
                    "locked": bool(obj.locked),
                    "selected": bool(obj.selected),
                    "position": [float(v) for v in obj.transform.position],
                    "transform": obj.transform.to_dict(),
                    "group_id": obj.group_id,
                }
            )
            obj.metadata["light"] = payload

    def _retarget_asset_metadata(self, obj: SceneObjectInstance) -> None:
        key = obj.object_type
        payload = dict(obj.metadata.get(key) or {})
        payload["id"] = obj.id
        payload["scene_object_id"] = obj.id
        payload["name"] = obj.name
        payload["selected"] = False
        obj.metadata[key] = payload
