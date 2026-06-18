"""Headless authored room geometry primitives for Map Studio.

This module owns the first reusable product seam between future Map Studio UI
tools and KOTOR module export.  It deliberately stays Qt-free: widgets can
create/edit these primitive specs, while exporters consume the compiled mesh
and WOK data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .module_format import WOKData, WOKFace


Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
Face = tuple[int, int, int]


@dataclass(frozen=True)
class PrimitiveMesh:
    """Triangle mesh emitted by an authored room primitive."""

    name: str
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    normals: tuple[Vec3, ...] = ()
    uvs: tuple[Vec2, ...] = ()
    texture: str = ""
    diffuse: Vec3 = (0.8, 0.8, 0.8)
    ambient: Vec3 = (0.35, 0.35, 0.35)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthoredRoomGeometry:
    """Compiled room geometry plus the walkmesh derived from its floor."""

    room_resref: str
    room_mesh: PrimitiveMesh
    helper_meshes: tuple[PrimitiveMesh, ...]
    wok: WOKData
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RectangularRoomPrimitive:
    """Single-room primitive used by the first T2601 proof module."""

    room_resref: str
    width: float = 10.0
    depth: float = 10.0
    wall_height: float = 3.0
    floor_surface_id: int = 4
    texture: str = "default"
    include_doorway_marker: bool = True


def _box_mesh(*, x0: float, y0: float, z0: float, x1: float, y1: float, z1: float) -> tuple[list[Vec3], list[Face]]:
    vertices: list[Vec3] = [
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    ]
    faces: list[Face] = [
        (0, 1, 2),
        (0, 2, 3),
        (4, 6, 5),
        (4, 7, 6),
        (0, 4, 5),
        (0, 5, 1),
        (1, 5, 6),
        (1, 6, 2),
        (2, 6, 7),
        (2, 7, 3),
        (3, 7, 4),
        (3, 4, 0),
    ]
    return vertices, faces


def _offset_faces(faces: list[Face], offset: int) -> list[Face]:
    return [(a + offset, b + offset, c + offset) for a, b, c in faces]


def build_rectangular_room_wok(primitive: RectangularRoomPrimitive) -> WOKData:
    """Derive a simple walkable floor WOK from the room floor primitive."""

    half_w = float(primitive.width) * 0.5
    half_d = float(primitive.depth) * 0.5
    return WOKData(
        verts=[
            (-half_w, -half_d, 0.0),
            (half_w, -half_d, 0.0),
            (half_w, half_d, 0.0),
            (-half_w, half_d, 0.0),
        ],
        faces=[
            WOKFace(0, 1, 2, surface=int(primitive.floor_surface_id), adj1=-1, adj2=-1, adj3=1),
            WOKFace(0, 2, 3, surface=int(primitive.floor_surface_id), adj1=0, adj2=-1, adj3=-1),
        ],
    )


def build_rectangular_room_mesh(primitive: RectangularRoomPrimitive) -> PrimitiveMesh:
    """Build one rectangular room shell: floor plus four walls, open top."""

    w = float(primitive.width) * 0.5
    d = float(primitive.depth) * 0.5
    h = float(primitive.wall_height)
    vertices: tuple[Vec3, ...] = (
        (-w, -d, 0.0),
        (w, -d, 0.0),
        (w, d, 0.0),
        (-w, d, 0.0),
        (-w, -d, h),
        (w, -d, h),
        (w, d, h),
        (-w, d, h),
    )
    faces: tuple[Face, ...] = (
        (0, 1, 2),
        (0, 2, 3),
        (0, 5, 1),
        (0, 4, 5),
        (1, 6, 2),
        (1, 5, 6),
        (2, 7, 3),
        (2, 6, 7),
        (3, 4, 0),
        (3, 7, 4),
    )
    uvs: tuple[Vec2, ...] = (
        (0.0, 0.0),
        (1.0, 0.0),
        (1.0, 1.0),
        (0.0, 1.0),
        (0.0, 0.0),
        (1.0, 0.0),
        (1.0, 1.0),
        (0.0, 1.0),
    )
    return PrimitiveMesh(
        name=f"{primitive.room_resref}_mesh",
        vertices=vertices,
        faces=faces,
        normals=((0.0, 0.0, 1.0),) * len(vertices),
        uvs=uvs,
        texture=str(primitive.texture or ""),
        metadata={"primitive": "rectangular_room_shell", "source": "map_studio:t2601"},
    )


def build_doorway_marker_mesh(primitive: RectangularRoomPrimitive) -> PrimitiveMesh:
    """Build visible doorway marker geometry for the smoke room."""

    d = float(primitive.depth) * 0.5
    marker_depth = 0.08
    post_half = 0.08
    clear_half_width = 0.75
    lintel_height = 0.12
    door_height = min(float(primitive.wall_height) - 0.25, 2.15)
    y0 = d - marker_depth
    y1 = d + marker_depth
    parts = [
        _box_mesh(x0=-clear_half_width - post_half, y0=y0, z0=0.0, x1=-clear_half_width + post_half, y1=y1, z1=door_height),
        _box_mesh(x0=clear_half_width - post_half, y0=y0, z0=0.0, x1=clear_half_width + post_half, y1=y1, z1=door_height),
        _box_mesh(
            x0=-clear_half_width - post_half,
            y0=y0,
            z0=door_height - lintel_height,
            x1=clear_half_width + post_half,
            y1=y1,
            z1=door_height + lintel_height,
        ),
    ]
    vertices: list[Vec3] = []
    faces: list[Face] = []
    for part_vertices, part_faces in parts:
        offset = len(vertices)
        vertices.extend(part_vertices)
        faces.extend(_offset_faces(part_faces, offset))
    return PrimitiveMesh(
        name=f"{primitive.room_resref}_door_marker",
        vertices=tuple(vertices),
        faces=tuple(faces),
        normals=((0.0, -1.0, 0.0),) * len(vertices),
        uvs=((0.0, 0.0),) * len(vertices),
        texture=str(primitive.texture or ""),
        diffuse=(1.0, 0.9, 0.25),
        ambient=(0.45, 0.35, 0.1),
        metadata={"primitive": "doorway_marker", "source": "map_studio:t2601"},
    )


def build_rectangular_room_geometry(primitive: RectangularRoomPrimitive) -> AuthoredRoomGeometry:
    """Compile a rectangular room primitive into render mesh data and WOK."""

    helpers = (build_doorway_marker_mesh(primitive),) if primitive.include_doorway_marker else ()
    return AuthoredRoomGeometry(
        room_resref=primitive.room_resref,
        room_mesh=build_rectangular_room_mesh(primitive),
        helper_meshes=helpers,
        wok=build_rectangular_room_wok(primitive),
        metadata={
            "primitive": "rectangular_room",
            "width": float(primitive.width),
            "depth": float(primitive.depth),
            "wall_height": float(primitive.wall_height),
            "floor_surface_id": int(primitive.floor_surface_id),
            "helper_mesh_count": len(helpers),
        },
    )


__all__ = [
    "AuthoredRoomGeometry",
    "PrimitiveMesh",
    "RectangularRoomPrimitive",
    "build_doorway_marker_mesh",
    "build_rectangular_room_geometry",
    "build_rectangular_room_mesh",
    "build_rectangular_room_wok",
]
