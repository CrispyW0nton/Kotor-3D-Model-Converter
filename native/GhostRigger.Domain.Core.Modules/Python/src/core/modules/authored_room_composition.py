"""Composable authored room geometry for Map Studio.

This module is the headless bridge between Map Studio creation tools and the
module export pipeline.  Editors should store primitive intent here first, then
compile it into ``AuthoredRoomGeometry`` for MDL/MDX/WOK packaging.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Union

from .authored_room_geometry import AuthoredRoomGeometry, PrimitiveMesh, RectangularRoomPrimitive
from .authored_walkmesh_surfaces import require_walkable_walkmesh_surface, resolve_walkmesh_surface_id, walkmesh_surface_name
from .authored_room_primitives import (
    ArchPrimitive,
    CubePrimitive,
    CylinderPrimitive,
    FloorPrimitive,
    PrimitiveMaterial,
    RampPrimitive,
    StairsPrimitive,
    WallPrimitive,
    build_arch_mesh,
    build_cube_mesh,
    build_cylinder_mesh,
    build_floor_mesh,
    build_floor_wok,
    build_ramp_mesh,
    build_ramp_wok,
    build_stairs_mesh,
    build_stairs_wok,
    build_wall_mesh,
)
from .module_format import WOKData, WOKFace


RoomPrimitive = Union[WallPrimitive, CubePrimitive, RampPrimitive, StairsPrimitive, CylinderPrimitive, ArchPrimitive]


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
    if isinstance(primitive, ArchPrimitive):
        return build_arch_mesh(primitive)
    raise TypeError(f"Unsupported authored room primitive: {type(primitive)!r}")


def _append_wok(base: WOKData, extra: WOKData) -> WOKData:
    """Append one primitive WOK to another while preserving local adjacency."""

    vertex_offset = len(base.verts)
    face_offset = len(base.faces)
    base.verts.extend(tuple(vertex) for vertex in extra.verts)
    for face in extra.faces:
        base.faces.append(
            WOKFace(
                face.v1 + vertex_offset,
                face.v2 + vertex_offset,
                face.v3 + vertex_offset,
                face.surface,
                face.adj1 + face_offset if face.adj1 >= 0 else -1,
                face.adj2 + face_offset if face.adj2 >= 0 else -1,
                face.adj3 + face_offset if face.adj3 >= 0 else -1,
            )
        )
    return base


def build_composition_wok(composition: AuthoredRoomComposition) -> WOKData:
    """Build the room WOK from the floor plus walkable authored primitives."""

    wok = build_floor_wok(composition.floor)
    for primitive in composition.primitives:
        if isinstance(primitive, RampPrimitive):
            _append_wok(wok, build_ramp_wok(primitive))
        if isinstance(primitive, StairsPrimitive):
            _append_wok(wok, build_stairs_wok(primitive))
    return wok


def validate_authored_room_composition(composition: AuthoredRoomComposition) -> AuthoredRoomCompositionValidation:
    """Validate a primitive room composition before it is compiled."""

    warnings: list[str] = []
    blocking: list[str] = []
    if not _normalise_name(composition.room_resref):
        blocking.append("Authored room composition requires a room resref.")
    if float(composition.floor.width) <= 0.0 or float(composition.floor.depth) <= 0.0:
        blocking.append("Authored room floor must have positive width and depth.")
    try:
        require_walkable_walkmesh_surface(composition.floor.surface_id, context=f"{composition.room_resref} floor")
    except ValueError as exc:
        blocking.append(str(exc))
    names: set[str] = set()
    for primitive in (composition.floor, *composition.primitives):
        name = str(getattr(primitive, "name", "") or "").strip()
        if not name:
            blocking.append("Every authored room primitive requires a stable name.")
            continue
        if name in names:
            blocking.append(f"Duplicate authored room primitive name: {name}")
        names.add(name)
    for primitive in composition.primitives:
        if isinstance(primitive, RampPrimitive):
            if float(primitive.width) <= 0.0 or float(primitive.length) <= 0.0 or float(primitive.height) <= 0.0:
                blocking.append(f"Ramp primitive {primitive.name or '(unnamed)'} must have positive width, length, and height.")
            try:
                require_walkable_walkmesh_surface(primitive.surface_id, context=f"{primitive.name} ramp")
            except ValueError as exc:
                blocking.append(str(exc))
        if isinstance(primitive, StairsPrimitive):
            if (
                float(primitive.width) <= 0.0
                or float(primitive.depth) <= 0.0
                or float(primitive.height) <= 0.0
                or int(primitive.steps) <= 0
            ):
                blocking.append(f"Stairs primitive {primitive.name or '(unnamed)'} must have positive width, depth, height, and step count.")
            try:
                require_walkable_walkmesh_surface(primitive.surface_id, context=f"{primitive.name} stairs")
            except ValueError as exc:
                blocking.append(str(exc))
        if isinstance(primitive, ArchPrimitive):
            if (
                float(primitive.width) <= 0.0
                or float(primitive.height) <= 0.0
                or float(primitive.depth) <= 0.0
                or float(primitive.frame_thickness) <= 0.0
            ):
                blocking.append(f"Arch primitive {primitive.name or '(unnamed)'} must have positive width, height, depth, and frame thickness.")
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
    floor_surface_id = resolve_walkmesh_surface_id(composition.floor.surface_id)
    primitive_meshes = tuple(_primitive_to_mesh(primitive) for primitive in composition.primitives)
    room_resref = _normalise_name(composition.room_resref)
    return AuthoredRoomGeometry(
        room_resref=room_resref,
        room_mesh=floor_mesh,
        helper_meshes=primitive_meshes + tuple(composition.helper_meshes),
        wok=build_composition_wok(composition),
        metadata={
            **dict(composition.metadata),
            "primitive": "authored_room_composition",
            "source": "src.core.modules.authored_room_composition",
            "floor": floor_mesh.name,
            "floor_surface_id": floor_surface_id,
            "floor_surface_name": walkmesh_surface_name(floor_surface_id),
            "primitive_count": len(composition.primitives),
            "helper_mesh_count": len(composition.helper_meshes),
            "compiled_mesh_count": 1 + len(primitive_meshes) + len(composition.helper_meshes),
            "walkmesh_primitive_count": sum(1 for primitive in composition.primitives if isinstance(primitive, (RampPrimitive, StairsPrimitive))),
            "warnings": list(validation.warnings),
        },
    )


def create_rectangular_room_composition(primitive: RectangularRoomPrimitive) -> AuthoredRoomComposition:
    """Convert the legacy rectangular smoke-room primitive to editable parts."""

    room_resref = _normalise_name(primitive.room_resref)
    material = PrimitiveMaterial(texture=str(primitive.texture or "default"))
    floor_surface_id = resolve_walkmesh_surface_id(primitive.floor_surface_id)
    half_w = float(primitive.width) * 0.5
    half_d = float(primitive.depth) * 0.5
    wall_height = float(primitive.wall_height)
    thickness = 0.15
    floor = FloorPrimitive(
        name=f"{room_resref}_mesh",
        width=float(primitive.width),
        depth=float(primitive.depth),
        z=0.0,
        surface_id=floor_surface_id,
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
            "floor_surface_id": floor_surface_id,
            "floor_surface_name": walkmesh_surface_name(floor_surface_id),
        },
    )


__all__ = [
    "AuthoredRoomComposition",
    "AuthoredRoomCompositionValidation",
    "RoomPrimitive",
    "build_composition_wok",
    "compile_authored_room_composition",
    "create_rectangular_room_composition",
    "validate_authored_room_composition",
]
