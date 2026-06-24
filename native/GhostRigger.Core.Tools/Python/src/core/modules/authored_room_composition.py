"""Composable authored room geometry for Map Studio.

This module is the headless bridge between Map Studio creation tools and the
module export pipeline.  Editors should store primitive intent here first, then
compile it into ``AuthoredRoomGeometry`` for MDL/MDX/WOK packaging.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Union

from .authored_room_geometry import AuthoredRoomGeometry, PrimitiveMesh, RectangularRoomPrimitive
from .authored_walkmesh_surfaces import require_walkable_walkmesh_surface, resolve_walkmesh_surface_id, walkmesh_surface_name
from .authored_room_primitives import (
    ArchPrimitive,
    CubePrimitive,
    CylinderPrimitive,
    DoorFramePrimitive,
    FloorPrimitive,
    PrimitiveMaterial,
    RampPrimitive,
    StairsPrimitive,
    WallPrimitive,
    build_arch_mesh,
    build_cube_mesh,
    build_cylinder_mesh,
    build_door_frame_mesh,
    build_floor_mesh,
    build_floor_wok,
    build_ramp_mesh,
    build_ramp_wok,
    build_stairs_mesh,
    build_stairs_wok,
    build_wall_mesh,
)
from .module_format import WOKData, WOKFace


DOOR_TRANSITION_SURFACE_ID = 18


BaseRoomPrimitive = Union[
    FloorPrimitive,
    WallPrimitive,
    CubePrimitive,
    RampPrimitive,
    StairsPrimitive,
    CylinderPrimitive,
    DoorFramePrimitive,
    ArchPrimitive,
]


@dataclass(frozen=True)
class PrimitiveTransform:
    """Durable transform intent for one authored primitive instance.

    Map Studio gizmos should persist transforms here before compilation so the
    visible MDL mesh and derived WOK stay in lockstep for export.
    """

    translation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_degrees_z: float = 0.0
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    pivot: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class PlacedRoomPrimitive:
    """A primitive plus editor-authored transform data."""

    primitive: BaseRoomPrimitive
    transform: PrimitiveTransform = field(default_factory=PrimitiveTransform)
    name: str = ""


RoomPrimitive = Union[BaseRoomPrimitive, PlacedRoomPrimitive]


@dataclass(frozen=True)
class AuthoredRoomComposition:
    """Editable primitive collection for one room model."""

    room_resref: str
    floor: FloorPrimitive | PlacedRoomPrimitive
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


def _transform_manifest(transform: PrimitiveTransform) -> dict[str, Any]:
    return {
        "translation": [float(value) for value in transform.translation],
        "rotation_degrees_z": float(transform.rotation_degrees_z),
        "scale": [float(value) for value in transform.scale],
        "pivot": [float(value) for value in transform.pivot],
    }


def _transform_point(point: tuple[float, float, float], transform: PrimitiveTransform) -> tuple[float, float, float]:
    px, py, pz = (float(value) for value in transform.pivot)
    sx, sy, sz = (float(value) for value in transform.scale)
    tx, ty, tz = (float(value) for value in transform.translation)
    x = (float(point[0]) - px) * sx
    y = (float(point[1]) - py) * sy
    z = (float(point[2]) - pz) * sz
    angle = math.radians(float(transform.rotation_degrees_z))
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return (
        x * cos_a - y * sin_a + px + tx,
        x * sin_a + y * cos_a + py + ty,
        z + pz + tz,
    )


def _transform_normal(normal: tuple[float, float, float], transform: PrimitiveTransform) -> tuple[float, float, float]:
    angle = math.radians(float(transform.rotation_degrees_z))
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    x = float(normal[0]) * cos_a - float(normal[1]) * sin_a
    y = float(normal[0]) * sin_a + float(normal[1]) * cos_a
    z = float(normal[2])
    length = math.sqrt(x * x + y * y + z * z)
    if length <= 0.0:
        return (0.0, 0.0, 1.0)
    return (x / length, y / length, z / length)


def transform_primitive_mesh(mesh: PrimitiveMesh, transform: PrimitiveTransform, *, name: str = "") -> PrimitiveMesh:
    """Apply an editor transform to a primitive mesh without mutating it."""

    return PrimitiveMesh(
        name=name or mesh.name,
        vertices=tuple(_transform_point(vertex, transform) for vertex in mesh.vertices),
        faces=tuple(mesh.faces),
        normals=tuple(_transform_normal(normal, transform) for normal in mesh.normals),
        uvs=tuple(mesh.uvs),
        texture=mesh.texture,
        diffuse=mesh.diffuse,
        ambient=mesh.ambient,
        metadata={
            **dict(mesh.metadata),
            "transform": _transform_manifest(transform),
            "transform_source": "src.core.modules.authored_room_composition",
        },
    )


def transform_wok_data(wok: WOKData, transform: PrimitiveTransform) -> WOKData:
    """Apply the same editor transform to WOK vertices as the visible mesh."""

    return WOKData(
        name=wok.name,
        verts=[_transform_point(vertex, transform) for vertex in wok.verts],
        faces=[
            WOKFace(face.v1, face.v2, face.v3, face.surface, face.adj1, face.adj2, face.adj3)
            for face in wok.faces
        ],
    )


def _base_primitive(primitive: RoomPrimitive) -> BaseRoomPrimitive:
    return primitive.primitive if isinstance(primitive, PlacedRoomPrimitive) else primitive


def _floor_base_and_transform(floor: FloorPrimitive | PlacedRoomPrimitive) -> tuple[FloorPrimitive, PrimitiveTransform | None]:
    if isinstance(floor, PlacedRoomPrimitive):
        base = floor.primitive
        if not isinstance(base, FloorPrimitive):
            raise TypeError(f"Authored room composition floor must be a FloorPrimitive, not {type(base)!r}.")
        return base, floor.transform
    return floor, None


def _primitive_name(primitive: FloorPrimitive | RoomPrimitive) -> str:
    if isinstance(primitive, PlacedRoomPrimitive):
        return str(primitive.name or getattr(primitive.primitive, "name", "") or "").strip()
    return str(getattr(primitive, "name", "") or "").strip()


def _primitive_to_mesh(primitive: RoomPrimitive) -> PrimitiveMesh:
    if isinstance(primitive, PlacedRoomPrimitive):
        mesh = _primitive_to_mesh(primitive.primitive)
        return transform_primitive_mesh(mesh, primitive.transform, name=_primitive_name(primitive))
    if isinstance(primitive, FloorPrimitive):
        return build_floor_mesh(primitive)
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
    if isinstance(primitive, DoorFramePrimitive):
        return build_door_frame_mesh(primitive)
    if isinstance(primitive, ArchPrimitive):
        return build_arch_mesh(primitive)
    raise TypeError(f"Unsupported authored room primitive: {type(primitive)!r}")


def primitive_to_mesh(primitive: RoomPrimitive) -> PrimitiveMesh:
    """Return the compiled mesh for one authored primitive instance.

    Map Studio tools such as the Universal Manipulator need exact selected
    bounds without owning primitive-specific mesh math in the UI layer.
    """

    return _primitive_to_mesh(primitive)


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


def _build_floor_wok_for_composition(composition: AuthoredRoomComposition) -> WOKData:
    """Build the base floor WOK, optionally reserving a doorway transition strip."""

    floor, transform = _floor_base_and_transform(composition.floor)
    if not bool(dict(composition.metadata or {}).get("include_door_transition_surface", False)):
        wok = build_floor_wok(floor)
        return transform_wok_data(wok, transform) if transform is not None else wok

    surface_id = resolve_walkmesh_surface_id(floor.surface_id)
    half_w = float(floor.width) * 0.5
    half_d = float(floor.depth) * 0.5
    z = float(floor.z)
    strip_depth = max(0.25, min(2.0, float(floor.depth) * 0.25))
    strip_y = half_d - strip_depth
    wok = WOKData(
        verts=[
            (-half_w, -half_d, z),
            (half_w, -half_d, z),
            (half_w, strip_y, z),
            (-half_w, strip_y, z),
            (half_w, half_d, z),
            (-half_w, half_d, z),
        ],
        faces=[
            WOKFace(0, 1, 2, surface=surface_id, adj1=-1, adj2=-1, adj3=1),
            WOKFace(0, 2, 3, surface=surface_id, adj1=0, adj2=2, adj3=-1),
            WOKFace(3, 2, 4, surface=DOOR_TRANSITION_SURFACE_ID, adj1=1, adj2=-1, adj3=3),
            WOKFace(3, 4, 5, surface=DOOR_TRANSITION_SURFACE_ID, adj1=2, adj2=-1, adj3=-1),
        ],
    )
    return transform_wok_data(wok, transform) if transform is not None else wok


def build_composition_wok(composition: AuthoredRoomComposition) -> WOKData:
    """Build the room WOK from the floor plus walkable authored primitives."""

    wok = _build_floor_wok_for_composition(composition)
    for primitive in composition.primitives:
        base = _base_primitive(primitive)
        primitive_wok: WOKData | None = None
        if isinstance(base, FloorPrimitive):
            primitive_wok = build_floor_wok(base)
        if isinstance(base, RampPrimitive):
            primitive_wok = build_ramp_wok(base)
        if isinstance(base, StairsPrimitive):
            primitive_wok = build_stairs_wok(base)
        if primitive_wok is not None:
            if isinstance(primitive, PlacedRoomPrimitive):
                primitive_wok = transform_wok_data(primitive_wok, primitive.transform)
            _append_wok(wok, primitive_wok)
    return wok


def validate_authored_room_composition(composition: AuthoredRoomComposition) -> AuthoredRoomCompositionValidation:
    """Validate a primitive room composition before it is compiled."""

    warnings: list[str] = []
    blocking: list[str] = []
    floor, floor_transform = _floor_base_and_transform(composition.floor)
    if not _normalise_name(composition.room_resref):
        blocking.append("Authored room composition requires a room resref.")
    if float(floor.width) <= 0.0 or float(floor.depth) <= 0.0:
        blocking.append("Authored room floor must have positive width and depth.")
    try:
        require_walkable_walkmesh_surface(floor.surface_id, context=f"{composition.room_resref} floor")
    except ValueError as exc:
        blocking.append(str(exc))
    if floor_transform is not None and any(float(value) <= 0.0 for value in floor_transform.scale):
        blocking.append(f"Placed floor {_primitive_name(composition.floor) or '(unnamed)'} must have positive transform scale.")
    names: set[str] = set()
    for primitive in (composition.floor, *composition.primitives):
        name = _primitive_name(primitive)
        if not name:
            blocking.append("Every authored room primitive requires a stable name.")
            continue
        if name in names:
            blocking.append(f"Duplicate authored room primitive name: {name}")
        names.add(name)
    for primitive in composition.primitives:
        if isinstance(primitive, PlacedRoomPrimitive) and any(float(value) <= 0.0 for value in primitive.transform.scale):
            blocking.append(f"Placed primitive {_primitive_name(primitive) or '(unnamed)'} must have positive transform scale.")
        base = _base_primitive(primitive)
        base_name = _primitive_name(primitive) or str(getattr(base, "name", "") or "(unnamed)")
        if isinstance(base, FloorPrimitive):
            if float(base.width) <= 0.0 or float(base.depth) <= 0.0:
                blocking.append(f"Plane primitive {base_name} must have positive width and depth.")
            try:
                require_walkable_walkmesh_surface(base.surface_id, context=f"{base_name} plane")
            except ValueError as exc:
                blocking.append(str(exc))
        if isinstance(base, RampPrimitive):
            if float(base.width) <= 0.0 or float(base.length) <= 0.0 or float(base.height) <= 0.0:
                blocking.append(f"Ramp primitive {base_name} must have positive width, length, and height.")
            try:
                require_walkable_walkmesh_surface(base.surface_id, context=f"{base_name} ramp")
            except ValueError as exc:
                blocking.append(str(exc))
        if isinstance(base, StairsPrimitive):
            if (
                float(base.width) <= 0.0
                or float(base.depth) <= 0.0
                or float(base.height) <= 0.0
                or int(base.steps) <= 0
            ):
                blocking.append(f"Stairs primitive {base_name} must have positive width, depth, height, and step count.")
            try:
                require_walkable_walkmesh_surface(base.surface_id, context=f"{base_name} stairs")
            except ValueError as exc:
                blocking.append(str(exc))
        if isinstance(base, ArchPrimitive):
            if (
                float(base.width) <= 0.0
                or float(base.height) <= 0.0
                or float(base.depth) <= 0.0
                or float(base.frame_thickness) <= 0.0
            ):
                blocking.append(f"Arch primitive {base_name} must have positive width, height, depth, and frame thickness.")
        if isinstance(base, DoorFramePrimitive):
            if (
                float(base.width) <= 0.0
                or float(base.height) <= 0.0
                or float(base.depth) <= 0.0
                or float(base.jamb_width) <= 0.0
                or float(base.lintel_height) <= 0.0
            ):
                blocking.append(f"Door frame primitive {base_name} must have positive width, height, depth, jamb width, and lintel height.")
            if float(base.width) <= float(base.jamb_width) * 2.0:
                blocking.append(f"Door frame primitive {base_name} must leave a positive doorway opening width.")
            if float(base.height) <= float(base.lintel_height):
                blocking.append(f"Door frame primitive {base_name} must leave a positive doorway opening height.")
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
    floor, _floor_transform = _floor_base_and_transform(composition.floor)
    floor_mesh = _primitive_to_mesh(composition.floor)
    floor_surface_id = resolve_walkmesh_surface_id(floor.surface_id)
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
            "transition_surface_id": DOOR_TRANSITION_SURFACE_ID
            if bool(dict(composition.metadata or {}).get("include_door_transition_surface", False))
            else 0,
            "primitive_count": len(composition.primitives),
            "helper_mesh_count": len(composition.helper_meshes),
            "compiled_mesh_count": 1 + len(primitive_meshes) + len(composition.helper_meshes),
            "walkmesh_primitive_count": sum(
                1
                for primitive in composition.primitives
                if isinstance(_base_primitive(primitive), (FloorPrimitive, RampPrimitive, StairsPrimitive))
            ),
            "transformed_primitive_count": sum(
                1 for primitive in (composition.floor,) + tuple(composition.primitives) if isinstance(primitive, PlacedRoomPrimitive)
            ),
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
            "include_door_transition_surface": bool(primitive.include_doorway_marker),
        },
    )


__all__ = [
    "AuthoredRoomComposition",
    "AuthoredRoomCompositionValidation",
    "PlacedRoomPrimitive",
    "PrimitiveTransform",
    "RoomPrimitive",
    "build_composition_wok",
    "compile_authored_room_composition",
    "create_rectangular_room_composition",
    "primitive_to_mesh",
    "transform_primitive_mesh",
    "transform_wok_data",
    "validate_authored_room_composition",
]
