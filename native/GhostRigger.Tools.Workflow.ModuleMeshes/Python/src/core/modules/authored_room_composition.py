"""Composable authored room geometry for Map Studio.

This module is the headless bridge between Map Studio creation tools and the
module export pipeline.  Editors should store primitive intent here first, then
compile it into ``AuthoredRoomGeometry`` for MDL/MDX/WOK packaging.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Union

from .authored_room_geometry import AuthoredRoomGeometry, PrimitiveMesh, RectangularRoomPrimitive
from .authored_room_primitives import (
    CubePrimitive,
    CylinderPrimitive,
    FloorPrimitive,
    PrimitiveMaterial,
    RampPrimitive,
    StairsPrimitive,
    WallPrimitive,
    build_cube_mesh,
    build_cylinder_mesh,
    build_floor_mesh,
    build_floor_wok,
    build_ramp_mesh,
    build_stairs_mesh,
    build_wall_mesh,
)


RoomPrimitive = Union[WallPrimitive, CubePrimitive, RampPrimitive, StairsPrimitive, CylinderPrimitive]


@dataclass(frozen=True)
class AuthoredRoomComposition:
    """Editable primitive collection for one room model."""

    room_resref: str
    floor: FloorPrimitive
    primitives: tuple[RoomPrimitive, ...] = ()
    helper_meshes: tuple[PrimitiveMesh, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthoredRoomCompositionValidation:
    """Validation result for primitive room intent before compilation."""

    ok: bool
    warnings: tuple[str, ...] = ()
    blocking_issues: tuple[str, ...] = ()


def _normalise_name(value: Any) -> str:
    return str(value or "").strip().lower()[:16]


def _primitive_to_mesh(primitive: RoomPrimitive) -> PrimitiveMesh:
    if isinstance(primitive, WallPrimitive):
        return build_wall_mesh(primitive)
    if isinstance(primitive, CubePrimitive):
        return build_cube_mesh(primitive)
    if isinstance(primitive, RampPrimitive):
        return build_ramp_mesh(primitive)
    if isinstance(primitive, StairsPrimitive):
        return build_stairs_mesh(primitive)
    if isinstance(primitive, CylinderPrimitive):
        return build_cylinder_mesh(primitive)
    raise TypeError(f"Unsupported authored room primitive: {type(primitive)!r}")


def validate_authored_room_composition(composition: AuthoredRoomComposition) -> AuthoredRoomCompositionValidation:
    """Validate a primitive room composition before it is compiled."""

    warnings: list[str] = []
    blocking: list[str] = []
    if not _normalise_name(composition.room_resref):
        blocking.append("Authored room composition requires a room resref.")
    if float(composition.floor.width) <= 0.0 or float(composition.floor.depth) <= 0.0:
        blocking.append("Authored room floor must have positive width and depth.")
    names: set[str] = set()
    for primitive in (composition.floor, *composition.primitives):
        name = str(getattr(primitive, "name", "") or "").strip()
        if not name:
            blocking.append("Every authored room primitive requires a stable name.")
            continue
        if name in names:
            blocking.append(f"Duplicate authored room primitive name: {name}")
        names.add(name)
    if not composition.primitives and not composition.helper_meshes:
        warnings.append("Authored room composition has only a floor; add walls or helpers before game-facing export.")
    return AuthoredRoomCompositionValidation(
        ok=not blocking,
        warnings=tuple(warnings),
        blocking_issues=tuple(blocking),
    )


def compile_authored_room_composition(composition: AuthoredRoomComposition) -> AuthoredRoomGeometry:
    """Compile editable room primitives into room geometry and a derived WOK."""

    validation = validate_authored_room_composition(composition)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    floor_mesh = build_floor_mesh(composition.floor)
    primitive_meshes = tuple(_primitive_to_mesh(primitive) for primitive in composition.primitives)
    room_resref = _normalise_name(composition.room_resref)
    return AuthoredRoomGeometry(
        room_resref=room_resref,
        room_mesh=floor_mesh,
        helper_meshes=primitive_meshes + tuple(composition.helper_meshes),
        wok=build_floor_wok(composition.floor),
        metadata={
            **dict(composition.metadata),
            "primitive": "authored_room_composition",
            "source": "src.core.modules.authored_room_composition",
            "floor": floor_mesh.name,
            "primitive_count": len(composition.primitives),
            "helper_mesh_count": len(composition.helper_meshes),
            "compiled_mesh_count": 1 + len(primitive_meshes) + len(composition.helper_meshes),
            "warnings": list(validation.warnings),
        },
    )


def create_rectangular_room_composition(primitive: RectangularRoomPrimitive) -> AuthoredRoomComposition:
    """Convert the legacy rectangular smoke-room primitive to editable parts."""

    room_resref = _normalise_name(primitive.room_resref)
    material = PrimitiveMaterial(texture=str(primitive.texture or "default"))
    half_w = float(primitive.width) * 0.5
    half_d = float(primitive.depth) * 0.5
    wall_height = float(primitive.wall_height)
    thickness = 0.15
    floor = FloorPrimitive(
        name=f"{room_resref}_mesh",
        width=float(primitive.width),
        depth=float(primitive.depth),
        z=0.0,
        surface_id=int(primitive.floor_surface_id),
        material=material,
    )
    walls: tuple[RoomPrimitive, ...] = (
        WallPrimitive(
            name=f"{room_resref}_wall_n",
            width=float(primitive.width),
            height=wall_height,
            thickness=thickness,
            axis="x",
            center=(0.0, half_d, wall_height * 0.5),
            material=material,
        ),
        WallPrimitive(
            name=f"{room_resref}_wall_s",
            width=float(primitive.width),
            height=wall_height,
            thickness=thickness,
            axis="x",
            center=(0.0, -half_d, wall_height * 0.5),
            material=material,
        ),
        WallPrimitive(
            name=f"{room_resref}_wall_e",
            width=float(primitive.depth),
            height=wall_height,
            thickness=thickness,
            axis="y",
            center=(half_w, 0.0, wall_height * 0.5),
            material=material,
        ),
        WallPrimitive(
            name=f"{room_resref}_wall_w",
            width=float(primitive.depth),
            height=wall_height,
            thickness=thickness,
            axis="y",
            center=(-half_w, 0.0, wall_height * 0.5),
            material=material,
        ),
    )
    helper_meshes = ()
    if primitive.include_doorway_marker:
        from .authored_room_geometry import build_doorway_marker_mesh

        helper_meshes = (replace(build_doorway_marker_mesh(primitive), metadata={"primitive": "doorway_marker", "source": "map_studio:t2601"}),)
    return AuthoredRoomComposition(
        room_resref=room_resref,
        floor=floor,
        primitives=walls,
        helper_meshes=helper_meshes,
        metadata={
            "composition_source": "map_studio:rectangular_room_composition",
            "width": float(primitive.width),
            "depth": float(primitive.depth),
            "wall_height": wall_height,
            "floor_surface_id": int(primitive.floor_surface_id),
        },
    )


__all__ = [
    "AuthoredRoomComposition",
    "AuthoredRoomCompositionValidation",
    "RoomPrimitive",
    "compile_authored_room_composition",
    "create_rectangular_room_composition",
    "validate_authored_room_composition",
]
