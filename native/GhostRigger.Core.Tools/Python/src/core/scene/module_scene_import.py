"""Helpers for importing KOTOR module room models into KMAX scenes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.modules.module_categories import get_module_info, module_model_stem
from src.core.modules.module_format import LYTLayout


@dataclass(frozen=True)
class ModuleRoomPlacement:
    """Game-layout placement for a room model imported as a scene group."""

    game: str
    resref: str
    module_code: str
    module_root: str
    area_label: str
    layout_resref: str
    room_index: int
    position: tuple[float, float, float]

    @property
    def group_id(self) -> str:
        return f"{self.game}:{self.module_root}".upper()

    def to_metadata(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "resref": self.resref,
            "module_code": self.module_code,
            "module_root": self.module_root,
            "area_label": self.area_label,
            "layout_resref": self.layout_resref,
            "room_index": int(self.room_index),
            "position": [float(v) for v in self.position],
            "group_id": self.group_id,
        }


def resolve_module_room_placement(
    *,
    game: str,
    resref: str,
    resource_manager: Any,
) -> ModuleRoomPlacement | None:
    """Return the LYT-authored placement for a module room model.

    ``resource_manager`` is intentionally duck-typed so the GUI can pass the
    existing game-resource manager and tests can use a tiny fake.
    """

    game_key = "K2" if str(game or "").upper() in {"K2", "TSL"} else "K1"
    room_resref = str(resref or "").rsplit(".", 1)[0].strip()
    if not room_resref or resource_manager is None:
        return None

    info = get_module_info(room_resref, game_key)
    if info is None:
        return None

    module_root = module_model_stem(info.module_code, game_key)
    layout_bytes = _resource_bytes(resource_manager, module_root, game_key)
    if not layout_bytes:
        return None

    try:
        layout = LYTLayout.from_text(layout_bytes.decode("latin-1", errors="replace"))
    except Exception:
        return None

    target = room_resref.lower()
    for index, room in enumerate(getattr(layout, "rooms", []) or []):
        model = str(getattr(room, "model", "") or "").lower()
        if model != target:
            continue
        return ModuleRoomPlacement(
            game=game_key,
            resref=room_resref,
            module_code=info.module_code,
            module_root=module_root,
            area_label=info.label,
            layout_resref=module_root,
            room_index=index,
            position=(
                float(getattr(room, "x", 0.0) or 0.0),
                float(getattr(room, "y", 0.0) or 0.0),
                float(getattr(room, "z", 0.0) or 0.0),
            ),
        )
    return None


def resolve_module_room_placements(
    *,
    game: str,
    resref: str,
    resource_manager: Any,
) -> list[ModuleRoomPlacement]:
    """Return all LYT-authored room placements for a module/category row.

    ``resref`` may be a module code (``303NAR``), room stem (``303nar``), or
    one room/submesh from that module (``303NARb3``). The returned rows stay in
    LYT order so the GUI can import the module as a stable scene group.
    """

    game_key = "K2" if str(game or "").upper() in {"K2", "TSL"} else "K1"
    source_resref = str(resref or "").rsplit(".", 1)[0].strip()
    if not source_resref or resource_manager is None:
        return []

    info = get_module_info(source_resref, game_key)
    if info is None:
        return []

    module_root = module_model_stem(info.module_code, game_key)
    layout_bytes = _resource_bytes(resource_manager, module_root, game_key)
    if not layout_bytes:
        return []

    try:
        layout = LYTLayout.from_text(layout_bytes.decode("latin-1", errors="replace"))
    except Exception:
        return []

    placements: list[ModuleRoomPlacement] = []
    for index, room in enumerate(getattr(layout, "rooms", []) or []):
        model = str(getattr(room, "model", "") or "").strip()
        if not model or model.lower() == "null":
            continue
        placements.append(
            ModuleRoomPlacement(
                game=game_key,
                resref=model,
                module_code=info.module_code,
                module_root=module_root,
                area_label=info.label,
                layout_resref=module_root,
                room_index=index,
                position=(
                    float(getattr(room, "x", 0.0) or 0.0),
                    float(getattr(room, "y", 0.0) or 0.0),
                    float(getattr(room, "z", 0.0) or 0.0),
                ),
            )
        )
    return placements


def _resource_bytes(resource_manager: Any, resref: str, game: str) -> bytes | None:
    try:
        from src.core.assets.resource_manager import RES_LYT
    except Exception:
        RES_LYT = 3005
    getter = getattr(resource_manager, "get", None)
    if not callable(getter):
        return None
    try:
        data = getter(resref, RES_LYT, game)
    except TypeError:
        data = getter(resref, RES_LYT)
    return bytes(data) if isinstance(data, (bytes, bytearray)) else None
