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

from .authored_module_lighting import AuthoredRoomLight
from .authored_module_objects import (
    AuthoredGameplayPlacement,
    AuthoredPlaceableInstance,
    AuthoredWaypointInstance,
    ModuleEntryPoint,
)
from .authored_module_project import (
    AuthoredModuleProject,
    create_composition_room_project,
    create_floor_plan_room_project,
    create_terrain_room_project,
    normalise_resref,
)
from .authored_terrain_builder import TerrainHeightfieldPrimitive, sample_terrain_height
from .authored_room_composition import AuthoredRoomComposition, PlacedRoomPrimitive, PrimitiveTransform
from .authored_room_floorplan import FloorPlanRoomPrimitive, FloorPlanWallOpening
from .authored_room_geometry import Vec2, Vec3
from .authored_room_materials import DEFAULT_AUTHORED_ROOM_TEXTURE, normalize_authored_room_texture
from .authored_room_primitives import ArchPrimitive, FloorPrimitive, PrimitiveMaterial, RampPrimitive, StairsPrimitive, WallPrimitive


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
    AuthoredRoomPrimitivePreset(
        preset_id="composition_starter_room",
        label="Composition Starter Room",
        description="Export-safe primitive-composition room with one connected walkable floor and editable wall primitives.",
        points=((-6.0, -5.0), (6.0, -5.0), (6.0, 5.0), (-6.0, 5.0)),
        entry_position=(0.0, -3.5, 0.0),
        placeable_position=(2.5, 1.75, 0.0),
        metadata={
            "shape": "primitive_composition_starter",
            "room_geometry_mode": "authored_room_composition",
            "supports_blockout_primitives": True,
        },
    ),
    AuthoredRoomPrimitivePreset(
        preset_id="elevation_test_room",
        label="Elevation Test Room",
        description="Primitive-composition room with walls, ramp, stairs, and arch geometry for testing elevated walkmesh export.",
        points=((-6.0, -5.0), (6.0, -5.0), (6.0, 5.0), (-6.0, 5.0)),
        entry_position=(0.0, -3.5, 0.0),
        placeable_position=(2.5, 1.75, 0.0),
        metadata={
            "shape": "primitive_composition",
            "room_geometry_mode": "authored_room_composition",
            "supports_elevation_geometry": True,
            "supports_walkable_ramp_and_stairs": True,
        },
    ),
    AuthoredRoomPrimitivePreset(
        preset_id="terrain_heightfield",
        label="Terrain Heightfield",
        description="Gentle editable terrain patch with generated visible mesh, slope-aware WOK faces, and smoke-test gameplay placement.",
        points=((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)),
        floor_surface_id="grass",
        entry_position=(0.0, -4.5, 0.0),
        placeable_position=(3.5, 3.0, 0.0),
        metadata={
            "shape": "terrain_heightfield",
            "room_geometry_mode": "terrain_heightfield",
            "supports_terrain_authoring": True,
            "supports_slope_walkability": True,
        },
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


def _preset_room_lights(*, preset: AuthoredRoomPrimitivePreset, root: str, room_resref: str) -> tuple[AuthoredRoomLight, ...]:
    """Return starter authored light intent for one room preset."""

    return (
        AuthoredRoomLight(
            name=f"{root}_key_light"[:32],
            room_resref=room_resref,
            position=(0.0, -1.5, max(2.25, float(preset.wall_height) * 0.75)),
            color=(1.0, 0.92, 0.76),
            radius=max(8.0, max(abs(float(x)) for point in preset.points for x in point)),
            intensity=0.65,
            light_type="point",
            metadata={
                "source": "map_studio:room_primitive_preset",
                "preset_id": preset.preset_id,
                "purpose": "starter_room_visibility",
            },
        ),
    )


def _preset_lighting_metadata(preset: AuthoredRoomPrimitivePreset) -> dict[str, Any]:
    """Return game-visible lighting policy for generated room presets."""

    return {
        "lighting": {
            "profile": "standard",
            "source": "map_studio:room_primitive_preset_balanced",
            "preset_id": preset.preset_id,
            "purpose": "readable_textured_room_preview",
            "sun_ambient": [48, 48, 48],
            "sun_diffuse": [150, 150, 150],
            "dynamic_ambient": [72, 72, 72],
            "shadow_opacity": 80,
            "sun_shadows": 0,
        }
    }


def _composition_project_from_preset(
    *,
    preset: AuthoredRoomPrimitivePreset,
    root: str,
    room_resref: str,
    game: str,
    display_name: str,
) -> AuthoredModuleProject:
    texture = normalize_authored_room_texture(preset.texture)
    material = PrimitiveMaterial(
        texture=texture,
        metadata={
            "source": "map_studio:room_primitive_preset",
            "preset_id": preset.preset_id,
        },
    )
    floor_surface = preset.floor_surface_id
    primitives: tuple[Any, ...] = (
        WallPrimitive(
            name=f"{room_resref}_wall_n",
            width=12.0,
            height=preset.wall_height,
            center=(0.0, 5.0, preset.wall_height * 0.5),
            material=material,
        ),
        WallPrimitive(
            name=f"{room_resref}_wall_s",
            width=12.0,
            height=preset.wall_height,
            center=(0.0, -5.0, preset.wall_height * 0.5),
            material=material,
        ),
        WallPrimitive(
            name=f"{room_resref}_wall_e",
            axis="y",
            width=10.0,
            height=preset.wall_height,
            center=(6.0, 0.0, preset.wall_height * 0.5),
            material=material,
        ),
        WallPrimitive(
            name=f"{room_resref}_wall_w",
            axis="y",
            width=10.0,
            height=preset.wall_height,
            center=(-6.0, 0.0, preset.wall_height * 0.5),
            material=material,
        ),
    )
    if preset.metadata.get("supports_elevation_geometry"):
        primitives = primitives + (
            PlacedRoomPrimitive(
                primitive=RampPrimitive(
                    name=f"{room_resref}_ramp",
                    width=2.0,
                    length=3.5,
                    height=1.0,
                    surface_id="metal",
                    material=material,
                ),
                transform=PrimitiveTransform(translation=(-2.75, 0.5, 0.0), rotation_degrees_z=0.0),
            ),
            PlacedRoomPrimitive(
                primitive=StairsPrimitive(
                    name=f"{room_resref}_stairs",
                    width=2.0,
                    depth=3.0,
                    height=1.0,
                    steps=4,
                    surface_id=floor_surface,
                    material=material,
                ),
                transform=PrimitiveTransform(translation=(2.75, 0.5, 0.0), rotation_degrees_z=0.0),
            ),
            ArchPrimitive(
                name=f"{room_resref}_arch",
                width=2.4,
                height=3.0,
                frame_thickness=0.3,
                depth=0.35,
                center=(0.0, -4.9, 1.5),
                material=material,
            ),
        )
    composition = AuthoredRoomComposition(
        room_resref=room_resref,
        floor=FloorPrimitive(
            name=f"{room_resref}_floor",
            width=12.0,
            depth=10.0,
            surface_id=floor_surface,
            material=material,
        ),
        primitives=primitives,
        metadata={
            "source": "map_studio:room_primitive_preset",
            "preset_id": preset.preset_id,
            "room_geometry_mode": "authored_room_composition",
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
    return create_composition_room_project(
        module_root=root,
        game=game,
        display_name=display_name,
        composition=composition,
        placements=placements,
        lights=_preset_room_lights(preset=preset, root=root, room_resref=room_resref),
        notes=(
            f"Map Studio primitive preset: {preset.label}.",
            "Editable KMAP-authored primitive-composition room with generated WOK intent.",
        ),
        metadata={
            "task": "T2668",
            "source": "map_studio:room_primitive_preset",
            "room_geometry_mode": "authored_room_composition",
            "preset_id": preset.preset_id,
            **_preset_lighting_metadata(preset),
        },
    )


def _terrain_project_from_preset(
    *,
    preset: AuthoredRoomPrimitivePreset,
    root: str,
    room_resref: str,
    game: str,
    display_name: str,
) -> AuthoredModuleProject:
    texture = normalize_authored_room_texture(preset.texture)
    material = PrimitiveMaterial(
        texture=texture,
        metadata={
            "source": "map_studio:room_primitive_preset",
            "preset_id": preset.preset_id,
        },
    )
    terrain = TerrainHeightfieldPrimitive(
        room_resref=room_resref,
        width=10.0,
        depth=10.0,
        heights=(
            (0.0, 0.0, 0.0, 0.0, 0.0),
            (0.0, 0.12, 0.2, 0.12, 0.0),
            (0.0, 0.2, 0.35, 0.2, 0.0),
            (0.0, 0.12, 0.2, 0.12, 0.0),
            (0.0, 0.0, 0.0, 0.0, 0.0),
        ),
        floor_surface_id=preset.floor_surface_id,
        material=material,
        metadata={
            "preset_source": "map_studio:room_primitive_preset",
            "preset_id": preset.preset_id,
            **dict(preset.metadata),
        },
    )
    entry_position = _position_on_terrain(terrain, preset.entry_position)
    placeable_position = _position_on_terrain(terrain, preset.placeable_position)
    placements = AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(area_resref=root, position=entry_position),
        placeables=(
            AuthoredPlaceableInstance(
                template_resref="plc_bench",
                tag=f"{root}_test_placeable",
                position=placeable_position,
            ),
        ),
        waypoints=(
            AuthoredWaypointInstance(
                template_resref="sw_startloc001",
                tag="start",
                position=entry_position,
            ),
        ),
        metadata={
            "source": "map_studio:room_primitive_preset",
            "player_start_is_module_entry": True,
            "preset_id": preset.preset_id,
        },
    )
    return create_terrain_room_project(
        module_root=root,
        game=game,
        display_name=display_name,
        terrain=terrain,
        placements=placements,
        lights=_preset_room_lights(preset=preset, root=root, room_resref=room_resref),
        notes=(
            f"Map Studio primitive preset: {preset.label}.",
            "Editable KMAP-authored terrain heightfield with generated slope-aware WOK intent.",
        ),
        metadata={
            "task": "T2907",
            "source": "map_studio:room_primitive_preset",
            "room_geometry_mode": "terrain_heightfield",
            "preset_id": preset.preset_id,
            **_preset_lighting_metadata(preset),
        },
    )


def _position_on_terrain(terrain: TerrainHeightfieldPrimitive, position: Vec3) -> Vec3:
    x = float(position[0])
    y = float(position[1])
    return (x, y, sample_terrain_height(terrain, x=x, y=y))


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
    if preset.metadata.get("room_geometry_mode") == "authored_room_composition":
        return _composition_project_from_preset(
            preset=preset,
            root=root,
            room_resref=room_resref,
            game=str(game or "K1").upper(),
            display_name=display_name or preset.label,
        )
    if preset.metadata.get("room_geometry_mode") == "terrain_heightfield":
        return _terrain_project_from_preset(
            preset=preset,
            root=root,
            room_resref=room_resref,
            game=str(game or "K1").upper(),
            display_name=display_name or preset.label,
        )
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
        lights=_preset_room_lights(preset=preset, root=root, room_resref=room_resref),
        notes=(
            f"Map Studio primitive preset: {preset.label}.",
            "Editable KMAP-authored floor-plan room with generated WOK intent.",
        ),
        metadata={
            "task": "T2650",
            "source": "map_studio:room_primitive_preset",
            "room_geometry_mode": "floor_plan_extrusion",
            "preset_id": preset.preset_id,
            **_preset_lighting_metadata(preset),
        },
    )


__all__ = [
    "AuthoredRoomPrimitivePreset",
    "available_authored_room_primitive_presets",
    "create_authored_module_from_room_preset",
    "get_authored_room_primitive_preset",
]
