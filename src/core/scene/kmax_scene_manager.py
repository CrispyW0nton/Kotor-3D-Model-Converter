"""Active KMAX scene manager for the main GhostRigger editor."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any
from uuid import uuid4

from .kmax_scene import KMaxScene
from .kmax_serializer import KMaxSerializer
from .scene_object import Transform
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

    def remove_object(self, object_id: str) -> bool:
        before = len(self.active_scene.objects)
        self.active_scene.objects = [obj for obj in self.active_scene.objects if obj.id != object_id]
        self.active_scene.sync_collections()
        changed = len(self.active_scene.objects) != before
        if changed:
            self.mark_dirty()
        return changed

    def duplicate_object(self, object_id: str) -> SceneObjectInstance | None:
        source = self._find_object(object_id)
        if source is None:
            return None
        duplicate = copy.deepcopy(source)
        duplicate.id = str(uuid4())
        duplicate.name = self._unique_object_name(f"{source.name}_copy")
        duplicate.selected = False
        duplicate.metadata.pop("_runtime_model", None)
        self.active_scene.objects.append(duplicate)
        self.active_scene.sync_collections()
        self.select_object(duplicate.id)
        self.mark_dirty()
        return duplicate

    def select_object(self, object_id: str) -> None:
        for obj in self.active_scene.objects:
            obj.selected = obj.id == object_id
        self.mark_dirty()

    def clear_selection(self) -> None:
        changed = False
        for obj in self.active_scene.objects:
            changed = changed or obj.selected
            obj.selected = False
        if changed:
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
