"""Headless authored room geometry primitives for Map Studio.

This module owns the first reusable product seam between future Map Studio UI
tools and KOTOR module export.  It deliberately stays Qt-free: widgets can
create/edit these primitive specs, while exporters consume the compiled mesh
and WOK data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .authored_room_materials import DEFAULT_AUTHORED_ROOM_TEXTURE, DEFAULT_AUTHORED_ROOM_UV_TILE_SIZE
from .authored_walkmesh_surfaces import resolve_walkmesh_surface_id, walkmesh_surface_name
from .module_format import WOKData, WOKFace


DOOR_TRANSITION_SURFACE_ID = 18


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
    floor_surface_id: int | str = 4
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

    surface_id = resolve_walkmesh_surface_id(primitive.floor_surface_id)
    half_w = float(primitive.width) * 0.5
    half_d = float(primitive.depth) * 0.5
    if primitive.include_doorway_marker:
        strip_depth = max(0.25, min(2.0, float(primitive.depth) * 0.25))
        strip_y = half_d - strip_depth
        return WOKData(
            verts=[
                (-half_w, -half_d, 0.0),
                (half_w, -half_d, 0.0),
                (half_w, strip_y, 0.0),
                (-half_w, strip_y, 0.0),
                (half_w, half_d, 0.0),
                (-half_w, half_d, 0.0),
            ],
            faces=[
                WOKFace(0, 1, 2, surface=surface_id, adj1=-1, adj2=-1, adj3=1),
                WOKFace(0, 2, 3, surface=surface_id, adj1=0, adj2=2, adj3=-1),
                WOKFace(3, 2, 4, surface=DOOR_TRANSITION_SURFACE_ID, adj1=1, adj2=-1, adj3=3),
                WOKFace(3, 4, 5, surface=DOOR_TRANSITION_SURFACE_ID, adj1=2, adj2=-1, adj3=-1),
            ],
        )
    return WOKData(
        verts=[
            (-half_w, -half_d, 0.0),
            (half_w, -half_d, 0.0),
            (half_w, half_d, 0.0),
            (-half_w, half_d, 0.0),
        ],
        faces=[
            WOKFace(0, 1, 2, surface=surface_id, adj1=-1, adj2=-1, adj3=1),
            WOKFace(0, 2, 3, surface=surface_id, adj1=0, adj2=-1, adj3=-1),
        ],
    )


def build_rectangular_room_mesh(primitive: RectangularRoomPrimitive) -> PrimitiveMesh:
    """Build one rectangular room shell: floor plus four walls, open top."""

    w = float(primitive.width) * 0.5
    d = float(primitive.depth) * 0.5
    h = float(primitive.wall_height)
    texture = str(primitive.texture or "")
    tile_size = (
        DEFAULT_AUTHORED_ROOM_UV_TILE_SIZE
        if texture.strip().lower() == DEFAULT_AUTHORED_ROOM_TEXTURE.lower()
        else 0.0
    )
    vertices: list[Vec3] = []
    faces: list[Face] = []
    normals: list[Vec3] = []
    uvs: list[Vec2] = []

    def append_quad(
        corners: tuple[Vec3, Vec3, Vec3, Vec3],
        normal: Vec3,
        size_u: float,
        size_v: float,
    ) -> None:
        start = len(vertices)
        repeat_u = float(size_u) / tile_size if tile_size else 1.0
        repeat_v = float(size_v) / tile_size if tile_size else 1.0
        vertices.extend(corners)
        normals.extend((normal,) * 4)
        uvs.extend(((0.0, 0.0), (repeat_u, 0.0), (repeat_u, repeat_v), (0.0, repeat_v)))
        faces.extend(((start, start + 1, start + 2), (start, start + 2, start + 3)))

    # Independent face corners preserve the inward wall normals and the UV
    # seams that the earlier eight-vertex shell could not represent.
    append_quad(((-w, -d, 0.0), (w, -d, 0.0), (w, d, 0.0), (-w, d, 0.0)), (0.0, 0.0, 1.0), 2.0 * w, 2.0 * d)
    append_quad(((w, -d, 0.0), (-w, -d, 0.0), (-w, -d, h), (w, -d, h)), (0.0, 1.0, 0.0), 2.0 * w, h)
    append_quad(((w, d, 0.0), (w, -d, 0.0), (w, -d, h), (w, d, h)), (-1.0, 0.0, 0.0), 2.0 * d, h)
    append_quad(((-w, d, 0.0), (w, d, 0.0), (w, d, h), (-w, d, h)), (0.0, -1.0, 0.0), 2.0 * w, h)
    append_quad(((-w, -d, 0.0), (-w, d, 0.0), (-w, d, h), (-w, -d, h)), (1.0, 0.0, 0.0), 2.0 * d, h)
    return PrimitiveMesh(
        name=f"{primitive.room_resref}_mesh",
        vertices=tuple(vertices),
        faces=tuple(faces),
        normals=tuple(normals),
        uvs=tuple(uvs),
        texture=texture,
        metadata={
            "primitive": "rectangular_room_shell",
            "source": "map_studio:t2601",
            "hard_face_normals": True,
            "uv_layout": "plcaa_world_tiled" if tile_size else "per_face_0_1",
            "uv_tile_size_m": tile_size,
        },
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
            "floor_surface_id": resolve_walkmesh_surface_id(primitive.floor_surface_id),
            "floor_surface_name": walkmesh_surface_name(resolve_walkmesh_surface_id(primitive.floor_surface_id)),
            "transition_surface_id": DOOR_TRANSITION_SURFACE_ID if primitive.include_doorway_marker else 0,
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
