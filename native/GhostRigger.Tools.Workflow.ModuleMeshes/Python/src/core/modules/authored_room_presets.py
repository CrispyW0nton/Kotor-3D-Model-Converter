"""Named authored-room presets for Map Studio primitive creation.

These presets are small, deterministic starter shapes that the Map Studio UI
can expose as "create room" choices.  They compile through the same authored
module pipeline as hand-authored KMAP data, so the UI is not responsible for
geometry, WOK, LYT, VIS, ARE, GIT, IFO, or package policy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .authored_module_objects import (
    AuthoredGameplayPlacement,
    AuthoredPlaceableInstance,
    AuthoredWaypointInstance,
    ModuleEntryPoint,
)
from .authored_module_project import AuthoredModuleProject, create_floor_plan_room_project, normalise_resref
from .authored_room_floorplan import FloorPlanRoomPrimitive, FloorPlanWallOpening
from .authored_room_geometry import Vec2, Vec3
from .authored_room_materials import DEFAULT_AUTHORED_ROOM_TEXTURE, normalize_authored_room_texture
from .authored_room_primitives import PrimitiveMaterial


@dataclass(frozen=True)
class AuthoredRoomPrimitivePreset:
    """Reusable starter room shape for from-scratch module authoring."""

    preset_id: str
    label: str
    description: str
    points: tuple[Vec2, ...]
    wall_height: float = 3.0
    floor_surface_id: int | str = 4
    texture: str = DEFAULT_AUTHORED_ROOM_TEXTURE
    openings: tuple[FloorPlanWallOpening, ...] = ()
    entry_position: Vec3 = (0.0, -3.0, 0.0)
    placeable_position: Vec3 = (1.75, 1.5, 0.0)
    metadata: dict[str, Any] = field(default_factory=dict)


def _octagon_points(radius: float = 4.5) -> tuple[Vec2, ...]:
    points: list[Vec2] = []
    for index in range(8):
        angle = (math.pi * 0.25 * index) + (math.pi * 0.125)
        points.append((round(math.cos(angle) * radius, 6), round(math.sin(angle) * radius, 6)))
    return tuple(points)


_PRESETS: tuple[AuthoredRoomPrimitivePreset, ...] = (
    AuthoredRoomPrimitivePreset(
        preset_id="rectangular_dev_room",
        label="Rectangular Dev Room",
        description="Single rectangular room with walls, walkable floor, player start, and test placeable.",
        points=((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)),
        metadata={"shape": "rectangle", "supports_t2601_smoke": True},
    ),
    AuthoredRoomPrimitivePreset(
        preset_id="doorway_blockout",
        label="Doorway Blockout",
        description="Rectangular room with one generated wall opening for early doorway and transition tests.",
        points=((-5.0, -3.5), (5.0, -3.5), (5.0, 3.5), (-5.0, 3.5)),
        openings=(
            FloorPlanWallOpening(
                name="south_doorway",
                edge_index=0,
                center_fraction=0.5,
                width=2.0,
                height=2.2,
                bottom=0.0,
                metadata={"purpose": "door_marker"},
            ),
        ),
        metadata={"shape": "rectangle_with_opening", "supports_doorway_authoring": True},
    ),
    AuthoredRoomPrimitivePreset(
        preset_id="wide_hall",
        label="Wide Hall",
        description="Long rectangular hall for testing pathing, camera placement, and object spacing.",
        points=((-8.0, -2.0), (8.0, -2.0), (8.0, 2.0), (-8.0, 2.0)),
        entry_position=(-6.0, 0.0, 0.0),
        placeable_position=(5.0, 0.0, 0.0),
        metadata={"shape": "hall", "supports_pathing_smoke": True},
    ),
    AuthoredRoomPrimitivePreset(
        preset_id="octagonal_room",
        label="Octagonal Room",
        description="Convex octagonal room for testing non-rectangular floor plans and generated WOK triangulation.",
        points=_octagon_points(),
        entry_position=(0.0, -2.5, 0.0),
        placeable_position=(1.5, 1.5, 0.0),
        metadata={"shape": "octagon", "supports_non_rectangular_floorplan": True},
    ),
)


def available_authored_room_primitive_presets() -> tuple[AuthoredRoomPrimitivePreset, ...]:
    """Return stable room presets for the Map Studio Builder tab."""

    return _PRESETS


def get_authored_room_primitive_preset(preset_id: str) -> AuthoredRoomPrimitivePreset:
    """Return one room preset by id, raising a clear error when missing."""

    wanted = str(preset_id or "").strip().lower()
    for preset in _PRESETS:
        if preset.preset_id == wanted:
            return preset
    known = ", ".join(preset.preset_id for preset in _PRESETS)
    raise ValueError(f"Unknown Map Studio room primitive preset '{preset_id}'. Known presets: {known}.")


def create_authored_module_from_room_preset(
    *,
    preset_id: str,
    module_root: str,
    game: str = "K1",
    display_name: str | None = None,
) -> AuthoredModuleProject:
    """Create editable authored module intent from a named primitive preset."""

    preset = get_authored_room_primitive_preset(preset_id)
    root = normalise_resref(module_root or "grdev01")
    room_resref = normalise_resref(f"{root}_room01")
    texture = normalize_authored_room_texture(preset.texture)
    primitive = FloorPlanRoomPrimitive(
        room_resref=room_resref,
        points=tuple((float(x), float(y)) for x, y in preset.points),
        wall_height=float(preset.wall_height),
        floor_surface_id=preset.floor_surface_id,
        material=PrimitiveMaterial(
            texture=texture,
            metadata={
                "source": "map_studio:room_primitive_preset",
                "preset_id": preset.preset_id,
            },
        ),
        include_walls=True,
        openings=preset.openings,
        metadata={
            "source": "map_studio:room_primitive_preset",
            "preset_id": preset.preset_id,
            **dict(preset.metadata),
        },
    )
    placements = AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(area_resref=root, position=preset.entry_position),
        placeables=(
            AuthoredPlaceableInstance(
                template_resref="plc_bench",
                tag=f"{root}_test_placeable",
                position=preset.placeable_position,
            ),
        ),
        waypoints=(
            AuthoredWaypointInstance(
                template_resref="sw_startloc001",
                tag="start",
                position=preset.entry_position,
            ),
        ),
        metadata={
            "source": "map_studio:room_primitive_preset",
            "player_start_is_module_entry": True,
            "preset_id": preset.preset_id,
        },
    )
    return create_floor_plan_room_project(
        module_root=root,
        game=str(game or "K1").upper(),
        display_name=display_name or preset.label,
        floor_plan=primitive,
        placements=placements,
        notes=(
            f"Map Studio primitive preset: {preset.label}.",
            "Editable KMAP-authored floor-plan room with generated WOK intent.",
        ),
        metadata={
            "task": "T2650",
            "source": "map_studio:room_primitive_preset",
            "room_geometry_mode": "floor_plan_extrusion",
            "preset_id": preset.preset_id,
        },
    )


__all__ = [
    "AuthoredRoomPrimitivePreset",
    "available_authored_room_primitive_presets",
    "create_authored_module_from_room_preset",
    "get_authored_room_primitive_preset",
]
