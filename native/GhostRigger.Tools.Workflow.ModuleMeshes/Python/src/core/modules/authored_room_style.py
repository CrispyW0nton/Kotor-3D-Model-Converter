"""Project-level room material and walkmesh surface assignment for Map Studio."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .authored_module_project import AuthoredModuleProject, AuthoredRoomSpec, normalise_resref
from .authored_room_floorplan import FloorPlanRoomPrimitive
from .authored_room_geometry import RectangularRoomPrimitive
from .authored_room_materials import AuthoredRoomMaterialPreflight, compile_authored_room_material_preflight
from .authored_room_primitives import PrimitiveMaterial
from .authored_terrain_builder import TerrainHeightfieldPrimitive
from .authored_walkmesh_surfaces import (
    is_walkable_walkmesh_surface,
    resolve_walkmesh_surface_id,
    walkmesh_surface_name,
)


@dataclass(frozen=True)
class AuthoredRoomStyleUpdate:
    """Result of applying a texture and WOK surface to an authored room."""

    project: AuthoredModuleProject
    room_resref: str
    texture: str
    floor_surface_id: int
    floor_surface_name: str
    material_preflight: AuthoredRoomMaterialPreflight
    warnings: tuple[str, ...] = ()


def _target_room_index(project: AuthoredModuleProject, room_resref: str = "") -> int:
    target = normalise_resref(room_resref)
    if not project.rooms:
        raise ValueError("Room material assignment requires at least one authored room.")
    if not target:
        return 0
    for index, room in enumerate(project.rooms):
        if normalise_resref(room.room_resref) == target:
            return index
    raise ValueError(f"Room material assignment could not find authored room '{room_resref}'.")


def _style_metadata(texture: str, surface_id: int, surface_name: str) -> dict[str, Any]:
    return {
        "source": "map_studio:room_style_update",
        "texture": texture,
        "floor_surface_id": surface_id,
        "floor_surface_name": surface_name,
    }


def _styled_floor_plan(
    primitive: FloorPlanRoomPrimitive,
    *,
    texture: str,
    surface_id: int,
    surface_name: str,
) -> FloorPlanRoomPrimitive:
    material = replace(
        primitive.material,
        texture=texture,
        metadata={
            **dict(primitive.material.metadata),
            **_style_metadata(texture, surface_id, surface_name),
        },
    )
    return replace(
        primitive,
        material=material,
        floor_surface_id=surface_id,
        metadata={
            **dict(primitive.metadata),
            "last_room_style_update": _style_metadata(texture, surface_id, surface_name),
        },
    )


def _styled_rectangular(
    primitive: RectangularRoomPrimitive,
    *,
    texture: str,
    surface_id: int,
) -> RectangularRoomPrimitive:
    return replace(
        primitive,
        texture=texture,
        floor_surface_id=surface_id,
    )


def _styled_terrain(
    primitive: TerrainHeightfieldPrimitive,
    *,
    texture: str,
    surface_id: int,
    surface_name: str,
) -> TerrainHeightfieldPrimitive:
    material = replace(
        primitive.material,
        texture=texture,
        metadata={
            **dict(primitive.material.metadata),
            **_style_metadata(texture, surface_id, surface_name),
        },
    )
    return replace(
        primitive,
        material=material,
        floor_surface_id=surface_id,
        metadata={
            **dict(primitive.metadata),
            "last_room_style_update": _style_metadata(texture, surface_id, surface_name),
        },
    )


def _styled_room(
    room: AuthoredRoomSpec,
    *,
    texture: str,
    surface_id: int,
    surface_name: str,
) -> AuthoredRoomSpec:
    primitive = room.primitive
    if isinstance(primitive, FloorPlanRoomPrimitive):
        updated_primitive = _styled_floor_plan(
            primitive,
            texture=texture,
            surface_id=surface_id,
            surface_name=surface_name,
        )
    elif isinstance(primitive, RectangularRoomPrimitive):
        updated_primitive = _styled_rectangular(
            primitive,
            texture=texture,
            surface_id=surface_id,
        )
    elif isinstance(primitive, TerrainHeightfieldPrimitive):
        updated_primitive = _styled_terrain(
            primitive,
            texture=texture,
            surface_id=surface_id,
            surface_name=surface_name,
        )
    else:
        raise ValueError(f"Room {room.room_resref} has unsupported primitive type: {type(primitive)!r}")

    return replace(
        room,
        primitive=updated_primitive,
        composition=None,
        metadata={
            **dict(room.metadata),
            "last_room_style_update": _style_metadata(texture, surface_id, surface_name),
        },
    )


def update_authored_room_style(
    project: AuthoredModuleProject,
    *,
    texture: Any = "",
    floor_surface: Any = 4,
    room_resref: str = "",
    require_game_texture_resolution: bool = False,
) -> AuthoredRoomStyleUpdate:
    """Apply a KOTOR texture resref and WOK surface to one authored room."""

    material = compile_authored_room_material_preflight(
        texture,
        require_game_resolution=bool(require_game_texture_resolution),
    )
    if material.blocking_issues:
        raise ValueError(material.blocking_issues[0])

    surface_id = resolve_walkmesh_surface_id(floor_surface)
    surface_name = walkmesh_surface_name(surface_id)
    warnings = list(material.warnings)
    if not is_walkable_walkmesh_surface(surface_id):
        warnings.append(
            f"Room floor surface {surface_id} ({surface_name}) is not normally walkable; player start and placeables may fail walkmesh validation."
        )

    index = _target_room_index(project, room_resref)
    room = project.rooms[index]
    updated_room = _styled_room(
        room,
        texture=material.texture,
        surface_id=surface_id,
        surface_name=surface_name,
    )
    rooms = tuple(project.rooms[:index] + (updated_room,) + project.rooms[index + 1 :])
    updated = replace(
        project,
        rooms=rooms,
        notes=tuple(project.notes)
        + (
            f"Applied Map Studio room style: texture {material.texture}, surface {surface_id} ({surface_name}).",
        ),
        extra={
            **dict(project.extra),
            "last_room_style_update": {
                "room_resref": updated_room.normalised_resref(),
                "texture": material.texture,
                "floor_surface_id": surface_id,
                "floor_surface_name": surface_name,
            },
        },
    )
    return AuthoredRoomStyleUpdate(
        project=updated,
        room_resref=updated_room.normalised_resref(),
        texture=material.texture,
        floor_surface_id=surface_id,
        floor_surface_name=surface_name,
        material_preflight=material,
        warnings=tuple(warnings),
    )


def apply_authored_room_style(
    project: AuthoredModuleProject,
    *,
    texture: Any = "",
    floor_surface: Any = 4,
    room_resref: str = "",
    require_game_texture_resolution: bool = False,
) -> AuthoredModuleProject:
    """Compatibility helper returning only the updated project."""

    return update_authored_room_style(
        project,
        texture=texture,
        floor_surface=floor_surface,
        room_resref=room_resref,
        require_game_texture_resolution=require_game_texture_resolution,
    ).project


__all__ = [
    "AuthoredRoomStyleUpdate",
    "apply_authored_room_style",
    "update_authored_room_style",
]
