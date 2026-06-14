"""Versioned GhostRigger KMAP project data model.

KMAP stores editable level state and source references. It deliberately avoids
embedding raw room meshes, textures, or heavy animation payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


KMAP_FILE_TYPE = "GhostRiggerKMap"
KMAP_FILE_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _vec3(value: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
    if isinstance(value, dict):
        value = (value.get("x"), value.get("y"), value.get("z"))
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except (TypeError, ValueError):
            return default
    return default


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


@dataclass
class LevelTransform:
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)

    @classmethod
    def from_dict(cls, data: Any) -> "LevelTransform":
        data = _dict(data)
        return cls(
            position=_vec3(data.get("position"), (0.0, 0.0, 0.0)),
            rotation=_vec3(data.get("rotation"), (0.0, 0.0, 0.0)),
            scale=_vec3(data.get("scale"), (1.0, 1.0, 1.0)),
        )

    def to_dict(self) -> dict[str, list[float]]:
        return {
            "position": [float(v) for v in self.position],
            "rotation": [float(v) for v in self.rotation],
            "scale": [float(v) for v in self.scale],
        }


@dataclass
class WalkmeshReference:
    wok_id: str = field(default_factory=lambda: stable_id("wok"))
    source_path: str = ""
    room_id: str = ""
    face_types: dict[str, int] = field(default_factory=dict)
    materials: dict[str, Any] = field(default_factory=dict)
    edited: bool = False
    visible: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Any) -> "WalkmeshReference":
        data = _dict(data)
        return cls(
            wok_id=str(data.get("wok_id") or stable_id("wok")),
            source_path=str(data.get("source_path") or ""),
            room_id=str(data.get("room_id") or ""),
            face_types={str(k): int(v) for k, v in _dict(data.get("face_types")).items()},
            materials=_dict(data.get("materials")),
            edited=bool(data.get("edited", False)),
            visible=bool(data.get("visible", True)),
            metadata=_dict(data.get("metadata")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "wok_id": self.wok_id,
            "source_path": self.source_path,
            "room_id": self.room_id,
            "face_types": dict(self.face_types),
            "materials": dict(self.materials),
            "edited": self.edited,
            "visible": self.visible,
            "metadata": dict(self.metadata),
        }


@dataclass
class RoomInstance:
    room_id: str = field(default_factory=lambda: stable_id("room"))
    name: str = "Room"
    model_resref: str = ""
    source_module: str = ""
    transform: LevelTransform = field(default_factory=LevelTransform)
    enabled: bool = True
    visible: bool = True
    locked: bool = False
    lyt_entry: dict[str, Any] = field(default_factory=dict)
    wok_entry: dict[str, Any] = field(default_factory=dict)
    lightmap_refs: list[str] = field(default_factory=list)
    texture_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Any) -> "RoomInstance":
        data = _dict(data)
        return cls(
            room_id=str(data.get("room_id") or stable_id("room")),
            name=str(data.get("name") or data.get("model_resref") or "Room"),
            model_resref=str(data.get("model_resref") or ""),
            source_module=str(data.get("source_module") or ""),
            transform=LevelTransform.from_dict(data.get("transform")),
            enabled=bool(data.get("enabled", True)),
            visible=bool(data.get("visible", True)),
            locked=bool(data.get("locked", False)),
            lyt_entry=_dict(data.get("lyt_entry")),
            wok_entry=_dict(data.get("wok_entry")),
            lightmap_refs=[str(v) for v in data.get("lightmap_refs", []) or []],
            texture_refs=[str(v) for v in data.get("texture_refs", []) or []],
            metadata=_dict(data.get("metadata")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "room_id": self.room_id,
            "name": self.name,
            "model_resref": self.model_resref,
            "source_module": self.source_module,
            "transform": self.transform.to_dict(),
            "enabled": self.enabled,
            "visible": self.visible,
            "locked": self.locked,
            "lyt_entry": dict(self.lyt_entry),
            "wok_entry": dict(self.wok_entry),
            "lightmap_refs": list(self.lightmap_refs),
            "texture_refs": list(self.texture_refs),
            "metadata": dict(self.metadata),
        }


@dataclass
class ModuleInstance:
    module_id: str = field(default_factory=lambda: stable_id("module"))
    module_name: str = "Module"
    source_path: str = ""
    game: str = "K1"
    enabled: bool = True
    visible: bool = True
    locked: bool = False
    transform: LevelTransform = field(default_factory=LevelTransform)
    rooms: list[str] = field(default_factory=list)
    walkmeshes: list[str] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Any) -> "ModuleInstance":
        data = _dict(data)
        return cls(
            module_id=str(data.get("module_id") or stable_id("module")),
            module_name=str(data.get("module_name") or data.get("name") or "Module"),
            source_path=str(data.get("source_path") or ""),
            game=str(data.get("game") or "K1").upper(),
            enabled=bool(data.get("enabled", True)),
            visible=bool(data.get("visible", True)),
            locked=bool(data.get("locked", False)),
            transform=LevelTransform.from_dict(data.get("transform")),
            rooms=[str(v) for v in data.get("rooms", []) or []],
            walkmeshes=[str(v) for v in data.get("walkmeshes", []) or []],
            resources=[_dict(v) for v in data.get("resources", []) or []],
            metadata=_dict(data.get("metadata")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "module_name": self.module_name,
            "source_path": self.source_path,
            "game": self.game,
            "enabled": self.enabled,
            "visible": self.visible,
            "locked": self.locked,
            "transform": self.transform.to_dict(),
            "rooms": list(self.rooms),
            "walkmeshes": list(self.walkmeshes),
            "resources": list(self.resources),
            "metadata": dict(self.metadata),
        }


@dataclass
class BlueprintEntry:
    blueprint_id: str = field(default_factory=lambda: stable_id("blueprint"))
    blueprint_type: str = "Custom"
    name: str = "Blueprint"
    template_resref: str = ""
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    properties: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Any) -> "BlueprintEntry":
        data = _dict(data)
        return cls(
            blueprint_id=str(data.get("blueprint_id") or stable_id("blueprint")),
            blueprint_type=str(data.get("blueprint_type") or "Custom"),
            name=str(data.get("name") or "Blueprint"),
            template_resref=str(data.get("template_resref") or ""),
            position=_vec3(data.get("position"), (0.0, 0.0, 0.0)),
            rotation=_vec3(data.get("rotation"), (0.0, 0.0, 0.0)),
            properties=_dict(data.get("properties")),
            metadata=_dict(data.get("metadata")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "blueprint_id": self.blueprint_id,
            "blueprint_type": self.blueprint_type,
            "name": self.name,
            "template_resref": self.template_resref,
            "position": [float(v) for v in self.position],
            "rotation": [float(v) for v in self.rotation],
            "properties": dict(self.properties),
            "metadata": dict(self.metadata),
        }


@dataclass
class TextureReference:
    texture_id: str = field(default_factory=lambda: stable_id("tex"))
    resref: str = ""
    path: str = ""
    source: str = ""
    include_in_export: bool = True
    lightmap: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Any) -> "TextureReference":
        data = _dict(data)
        return cls(
            texture_id=str(data.get("texture_id") or data.get("id") or stable_id("tex")),
            resref=str(data.get("resref") or ""),
            path=str(data.get("path") or ""),
            source=str(data.get("source") or ""),
            include_in_export=bool(data.get("include_in_export", True)),
            lightmap=str(data.get("lightmap") or ""),
            metadata=_dict(data.get("metadata")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "texture_id": self.texture_id,
            "resref": self.resref,
            "path": self.path,
            "source": self.source,
            "include_in_export": self.include_in_export,
            "lightmap": self.lightmap,
            "metadata": dict(self.metadata),
        }


@dataclass
class MaterialReference:
    material_id: str = field(default_factory=lambda: stable_id("mat"))
    name: str = "Material"
    texture_id: str = ""
    room_id: str = ""
    include_in_export: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Any) -> "MaterialReference":
        data = _dict(data)
        return cls(
            material_id=str(data.get("material_id") or data.get("id") or stable_id("mat")),
            name=str(data.get("name") or "Material"),
            texture_id=str(data.get("texture_id") or ""),
            room_id=str(data.get("room_id") or ""),
            include_in_export=bool(data.get("include_in_export", True)),
            metadata=_dict(data.get("metadata")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "material_id": self.material_id,
            "name": self.name,
            "texture_id": self.texture_id,
            "room_id": self.room_id,
            "include_in_export": self.include_in_export,
            "metadata": dict(self.metadata),
        }


@dataclass
class KMapProject:
    project_id: str = field(default_factory=lambda: stable_id("kmap"))
    name: str = "new_level"
    description: str = ""
    game: str = "K1"
    source_game: str = "K1"
    target_game: str = "K1"
    created_at: str = field(default_factory=utc_now_iso)
    modified_at: str = field(default_factory=utc_now_iso)
    author: str = ""
    path: str = ""
    source_directory: str = ""
    output_directory: str = ""
    system_unit: str = "cm"
    display_unit: str = "cm"
    modules: list[ModuleInstance] = field(default_factory=list)
    rooms: list[RoomInstance] = field(default_factory=list)
    objects: list[dict[str, Any]] = field(default_factory=list)
    lights: list[dict[str, Any]] = field(default_factory=list)
    cameras: list[dict[str, Any]] = field(default_factory=list)
    sequences: list[dict[str, Any]] = field(default_factory=list)
    materials: list[MaterialReference] = field(default_factory=list)
    textures: list[TextureReference] = field(default_factory=list)
    walkmeshes: list[WalkmeshReference] = field(default_factory=list)
    blueprints: list[BlueprintEntry] = field(default_factory=list)
    exports: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    extra_sections: dict[str, Any] = field(default_factory=dict)
    dirty: bool = False

    def mark_dirty(self) -> None:
        self.dirty = True
        self.modified_at = utc_now_iso()

    def find_room(self, room_id: str) -> RoomInstance | None:
        return next((room for room in self.rooms if room.room_id == room_id), None)

    def find_module(self, module_id: str) -> ModuleInstance | None:
        return next((module for module in self.modules if module.module_id == module_id), None)

    def find_walkmesh(self, wok_id: str) -> WalkmeshReference | None:
        return next((wok for wok in self.walkmeshes if wok.wok_id == wok_id), None)

    def find_blueprint(self, blueprint_id: str) -> BlueprintEntry | None:
        return next((bp for bp in self.blueprints if bp.blueprint_id == blueprint_id), None)


def new_kmap_project(name: str = "new_level", game: str = "K1", author: str = "") -> KMapProject:
    game_key = str(game or "K1").upper()
    return KMapProject(
        name=name or "new_level",
        game=game_key,
        source_game=game_key,
        target_game=game_key,
        author=author,
    )
