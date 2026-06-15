"""Mutable Level Editor scene operations backed by a KMAP project."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .kmap_model import (
    BlueprintEntry,
    KMapProject,
    LevelTransform,
    ModuleInstance,
    RoomInstance,
    WalkmeshReference,
)


@dataclass
class LevelScene:
    project: KMapProject
    selection: list[str] = field(default_factory=list)

    def add_module(
        self,
        name: str,
        *,
        source_path: str = "",
        game: str | None = None,
        transform: LevelTransform | None = None,
    ) -> ModuleInstance:
        module = ModuleInstance(
            module_name=name or "Module",
            source_path=source_path,
            game=(game or self.project.game or "K1").upper(),
            transform=transform or LevelTransform(),
        )
        self.project.modules.append(module)
        self.project.mark_dirty()
        return module

    def remove_module(self, module_id: str, *, remove_rooms: bool = False) -> bool:
        module = self.project.find_module(module_id)
        if module is None:
            return False
        self.project.modules = [item for item in self.project.modules if item.module_id != module_id]
        if remove_rooms:
            owned = set(module.rooms)
            self.project.rooms = [room for room in self.project.rooms if room.room_id not in owned]
            self.project.walkmeshes = [wok for wok in self.project.walkmeshes if wok.room_id not in owned]
        self.selection = [item for item in self.selection if item != module_id]
        self.project.mark_dirty()
        return True

    def add_room(
        self,
        name: str,
        *,
        model_resref: str = "",
        source_module: str = "",
        module_id: str = "",
        transform: LevelTransform | None = None,
        lyt_entry: dict | None = None,
    ) -> RoomInstance:
        room = RoomInstance(
            name=name or model_resref or "Room",
            model_resref=model_resref or name,
            source_module=source_module or module_id,
            transform=transform or LevelTransform(),
            lyt_entry=dict(lyt_entry or {}),
        )
        self.project.rooms.append(room)
        if module_id:
            module = self.project.find_module(module_id)
            if module is not None and room.room_id not in module.rooms:
                module.rooms.append(room.room_id)
        self.project.mark_dirty()
        return room

    def remove_room(self, room_id: str) -> bool:
        if self.project.find_room(room_id) is None:
            return False
        self.project.rooms = [room for room in self.project.rooms if room.room_id != room_id]
        self.project.walkmeshes = [wok for wok in self.project.walkmeshes if wok.room_id != room_id]
        for module in self.project.modules:
            module.rooms = [item for item in module.rooms if item != room_id]
        self.selection = [item for item in self.selection if item != room_id]
        self.project.mark_dirty()
        return True

    def duplicate_room(self, room_id: str) -> RoomInstance | None:
        room = self.project.find_room(room_id)
        if room is None:
            return None
        clone = RoomInstance.from_dict(room.to_dict())
        clone.room_id = RoomInstance().room_id
        clone.name = f"{room.name}_copy"
        clone.transform.position = (
            clone.transform.position[0] + 100.0,
            clone.transform.position[1],
            clone.transform.position[2],
        )
        self.project.rooms.append(clone)
        for module in self.project.modules:
            if room_id in module.rooms:
                module.rooms.append(clone.room_id)
                break
        self.project.mark_dirty()
        return clone

    def associate_walkmesh(
        self,
        room_id: str,
        *,
        source_path: str = "",
        face_types: dict[str, int] | None = None,
    ) -> WalkmeshReference:
        existing = next((wok for wok in self.project.walkmeshes if wok.room_id == room_id), None)
        if existing is None:
            existing = WalkmeshReference(room_id=room_id)
            self.project.walkmeshes.append(existing)
        existing.source_path = source_path or existing.source_path
        if face_types:
            existing.face_types.update({str(k): int(v) for k, v in face_types.items()})
        room = self.project.find_room(room_id)
        if room is not None:
            room.wok_entry.update({"wok_id": existing.wok_id, "source_path": existing.source_path})
        for module in self.project.modules:
            if room_id in module.rooms and existing.wok_id not in module.walkmeshes:
                module.walkmeshes.append(existing.wok_id)
        self.project.mark_dirty()
        return existing

    def add_blueprint(
        self,
        name: str,
        *,
        blueprint_type: str = "Custom",
        template_resref: str = "",
        position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> BlueprintEntry:
        blueprint = BlueprintEntry(
            name=name or template_resref or "Blueprint",
            blueprint_type=blueprint_type,
            template_resref=template_resref,
            position=position,
        )
        self.project.blueprints.append(blueprint)
        self.project.mark_dirty()
        return blueprint

    def select(self, ids: str | Iterable[str]) -> None:
        if isinstance(ids, str):
            self.selection = [ids]
        else:
            self.selection = [str(item) for item in ids]

    def set_transform(self, item_id: str, transform: LevelTransform) -> bool:
        item = self.project.find_room(item_id) or self.project.find_module(item_id)
        if item is None:
            return False
        if getattr(item, "locked", False):
            return False
        item.transform = transform
        self.project.mark_dirty()
        return True

    def set_visibility(self, item_id: str, visible: bool) -> bool:
        item = self.project.find_room(item_id) or self.project.find_module(item_id)
        if item is None:
            return False
        item.visible = bool(visible)
        self.project.mark_dirty()
        return True

    def set_locked(self, item_id: str, locked: bool) -> bool:
        item = self.project.find_room(item_id) or self.project.find_module(item_id)
        if item is None:
            return False
        item.locked = bool(locked)
        self.project.mark_dirty()
        return True
