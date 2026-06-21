"""Reusable authored primitive mesh builders for Map Studio.

These builders are deliberately small, deterministic, and headless.  The Map
Studio UI can expose them as creation tools; exporters can compile their
``PrimitiveMesh`` output into room MDL/MDX or derive WOK data from floor-like
surfaces.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .authored_room_geometry import Face, PrimitiveMesh, Vec2, Vec3
from .authored_walkmesh_surfaces import resolve_walkmesh_surface_id, walkmesh_surface_name
from .module_format import WOKData, WOKFace


@dataclass(frozen=True)
class PrimitiveMaterial:
    """Simple material tokens carried by authored primitives."""

    texture: str = "default"
    diffuse: Vec3 = (0.8, 0.8, 0.8)
    ambient: Vec3 = (0.35, 0.35, 0.35)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FloorPrimitive:
    name: str
    width: float = 4.0
    depth: float = 4.0
    z: float = 0.0
    surface_id: int | str = 4
    material: PrimitiveMaterial = field(default_factory=PrimitiveMaterial)


@dataclass(frozen=True)
class WallPrimitive:
    name: str
    width: float = 4.0
    height: float = 3.0
    thickness: float = 0.15
    axis: str = "x"
    center: Vec3 = (0.0, 0.0, 1.5)
    material: PrimitiveMaterial = field(default_factory=PrimitiveMaterial)


@dataclass(frozen=True)
class CubePrimitive:
    name: str
    size: Vec3 = (1.0, 1.0, 1.0)
    center: Vec3 = (0.0, 0.0, 0.5)
    material: PrimitiveMaterial = field(default_factory=PrimitiveMaterial)


@dataclass(frozen=True)
class RampPrimitive:
    name: str
    width: float = 2.0
    length: float = 4.0
    height: float = 1.0
    center: Vec3 = (0.0, 0.0, 0.0)
    surface_id: int | str = 4
    material: PrimitiveMaterial = field(default_factory=PrimitiveMaterial)


@dataclass(frozen=True)
class StairsPrimitive:
    name: str
    width: float = 2.0
    depth: float = 4.0
    height: float = 1.0
    steps: int = 4
    surface_id: int | str = 4
    material: PrimitiveMaterial = field(default_factory=PrimitiveMaterial)


@dataclass(frozen=True)
class CylinderPrimitive:
    name: str
    radius: float = 0.5
    height: float = 1.0
    segments: int = 16
    center: Vec3 = (0.0, 0.0, 0.5)
    material: PrimitiveMaterial = field(default_factory=PrimitiveMaterial)


@dataclass(frozen=True)
class DoorFramePrimitive:
    """Rectangular doorway frame for KOTOR transition/portal blockouts."""

    name: str
    width: float = 2.2
    height: float = 3.0
    jamb_width: float = 0.22
    lintel_height: float = 0.28
    depth: float = 0.25
    center: Vec3 = (0.0, 0.0, 1.5)
    material: PrimitiveMaterial = field(default_factory=PrimitiveMaterial)


@dataclass(frozen=True)
class ArchPrimitive:
    """Segmented doorway arch frame for authored room blockouts."""

    name: str
    width: float = 2.0
    height: float = 3.0
    frame_thickness: float = 0.25
    depth: float = 0.25
    segments: int = 12
    center: Vec3 = (0.0, 0.0, 1.5)
    material: PrimitiveMaterial = field(default_factory=PrimitiveMaterial)


def _mesh(
    *,
    name: str,
    vertices: tuple[Vec3, ...],
    faces: tuple[Face, ...],
    material: PrimitiveMaterial,
    primitive: str,
    metadata: dict[str, Any] | None = None,
) -> PrimitiveMesh:
    uvs: tuple[Vec2, ...] = tuple((0.0, 0.0) for _ in vertices)
    return PrimitiveMesh(
        name=name,
        vertices=vertices,
        faces=faces,
        normals=((0.0, 0.0, 1.0),) * len(vertices),
        uvs=uvs,
        texture=material.texture,
        diffuse=material.diffuse,
        ambient=material.ambient,
        metadata={"primitive": primitive, **dict(metadata or {}), **dict(material.metadata)},
    )


def _box_vertices_faces(*, name: str, x: float, y: float, z: float, center: Vec3, material: PrimitiveMaterial, primitive: str) -> PrimitiveMesh:
    hx = float(x) * 0.5
    hy = float(y) * 0.5
    hz = float(z) * 0.5
    cx, cy, cz = center
    vertices: tuple[Vec3, ...] = (
        (cx - hx, cy - hy, cz - hz),
        (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz),
        (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz),
        (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz),
        (cx - hx, cy + hy, cz + hz),
    )
    faces: tuple[Face, ...] = (
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
    )
    return _mesh(name=name, vertices=vertices, faces=faces, material=material, primitive=primitive)


def _append_mesh_parts(vertices: list[Vec3], faces: list[Face], mesh: PrimitiveMesh) -> None:
    offset = len(vertices)
    vertices.extend(mesh.vertices)
    faces.extend((a + offset, b + offset, c + offset) for a, b, c in mesh.faces)


def build_floor_mesh(primitive: FloorPrimitive) -> PrimitiveMesh:
    surface_id = resolve_walkmesh_surface_id(primitive.surface_id)
    half_w = float(primitive.width) * 0.5
    half_d = float(primitive.depth) * 0.5
    z = float(primitive.z)
    vertices: tuple[Vec3, ...] = (
        (-half_w, -half_d, z),
        (half_w, -half_d, z),
        (half_w, half_d, z),
        (-half_w, half_d, z),
    )
    faces: tuple[Face, ...] = ((0, 1, 2), (0, 2, 3))
    return _mesh(
        name=primitive.name,
        vertices=vertices,
        faces=faces,
        material=primitive.material,
        primitive="floor",
        metadata={"surface_id": surface_id, "surface_name": walkmesh_surface_name(surface_id)},
    )


def build_floor_wok(primitive: FloorPrimitive) -> WOKData:
    surface_id = resolve_walkmesh_surface_id(primitive.surface_id)
    mesh = build_floor_mesh(primitive)
    return WOKData(
        verts=list(mesh.vertices),
        faces=[
            WOKFace(0, 1, 2, surface=surface_id, adj1=-1, adj2=-1, adj3=1),
            WOKFace(0, 2, 3, surface=surface_id, adj1=0, adj2=-1, adj3=-1),
        ],
    )


def build_wall_mesh(primitive: WallPrimitive) -> PrimitiveMesh:
    axis = str(primitive.axis or "x").lower()
    if axis == "y":
        size = (float(primitive.thickness), float(primitive.width), float(primitive.height))
    else:
        size = (float(primitive.width), float(primitive.thickness), float(primitive.height))
    return _box_vertices_faces(
        name=primitive.name,
        x=size[0],
        y=size[1],
        z=size[2],
        center=primitive.center,
        material=primitive.material,
        primitive="wall",
    )


def build_cube_mesh(primitive: CubePrimitive) -> PrimitiveMesh:
    return _box_vertices_faces(
        name=primitive.name,
        x=float(primitive.size[0]),
        y=float(primitive.size[1]),
        z=float(primitive.size[2]),
        center=primitive.center,
        material=primitive.material,
        primitive="cube",
    )


def build_ramp_mesh(primitive: RampPrimitive) -> PrimitiveMesh:
    half_w = float(primitive.width) * 0.5
    half_l = float(primitive.length) * 0.5
    h = float(primitive.height)
    cx, cy, cz = primitive.center
    surface_id = resolve_walkmesh_surface_id(primitive.surface_id)
    vertices: tuple[Vec3, ...] = (
        (cx - half_w, cy - half_l, cz),
        (cx + half_w, cy - half_l, cz),
        (cx + half_w, cy + half_l, cz + h),
        (cx - half_w, cy + half_l, cz + h),
        (cx - half_w, cy + half_l, cz),
        (cx + half_w, cy + half_l, cz),
    )
    faces: tuple[Face, ...] = (
        (0, 1, 2),
        (0, 2, 3),
        (0, 4, 5),
        (0, 5, 1),
        (4, 3, 2),
        (4, 2, 5),
        (0, 3, 4),
        (0, 2, 3),
        (1, 5, 2),
    )
    return _mesh(
        name=primitive.name,
        vertices=vertices,
        faces=faces,
        material=primitive.material,
        primitive="ramp",
        metadata={"surface_id": surface_id, "surface_name": walkmesh_surface_name(surface_id)},
    )


def build_ramp_wok(primitive: RampPrimitive) -> WOKData:
    """Build a walkable sloped WOK from the ramp's top surface."""

    surface_id = resolve_walkmesh_surface_id(primitive.surface_id)
    mesh = build_ramp_mesh(primitive)
    return WOKData(
        verts=list(mesh.vertices[:4]),
        faces=[
            WOKFace(0, 1, 2, surface=surface_id, adj1=-1, adj2=-1, adj3=1),
            WOKFace(0, 2, 3, surface=surface_id, adj1=0, adj2=-1, adj3=-1),
        ],
    )


def build_stairs_mesh(primitive: StairsPrimitive) -> PrimitiveMesh:
    steps = max(1, int(primitive.steps))
    step_depth = float(primitive.depth) / steps
    step_height = float(primitive.height) / steps
    half_w = float(primitive.width) * 0.5
    y0 = -float(primitive.depth) * 0.5
    vertices: list[Vec3] = []
    faces: list[Face] = []
    for index in range(steps):
        z = step_height * (index + 0.5)
        y = y0 + step_depth * index + step_depth * 0.5
        step = _box_vertices_faces(
            name=f"{primitive.name}_step{index + 1}",
            x=half_w * 2.0,
            y=step_depth,
            z=step_height * (index + 1),
            center=(0.0, y, z),
            material=primitive.material,
            primitive="stair_step",
        )
        offset = len(vertices)
        vertices.extend(step.vertices)
        faces.extend((a + offset, b + offset, c + offset) for a, b, c in step.faces)
    return _mesh(
        name=primitive.name,
        vertices=tuple(vertices),
        faces=tuple(faces),
        material=primitive.material,
        primitive="stairs",
        metadata={
            "steps": steps,
            "surface_id": resolve_walkmesh_surface_id(primitive.surface_id),
            "surface_name": walkmesh_surface_name(resolve_walkmesh_surface_id(primitive.surface_id)),
        },
    )


def build_stairs_wok(primitive: StairsPrimitive) -> WOKData:
    """Build a continuous walkable WOK proxy over visual stair treads."""

    surface_id = resolve_walkmesh_surface_id(primitive.surface_id)
    half_w = float(primitive.width) * 0.5
    half_d = float(primitive.depth) * 0.5
    h = float(primitive.height)
    verts: list[Vec3] = [
        (-half_w, -half_d, 0.0),
        (half_w, -half_d, 0.0),
        (half_w, half_d, h),
        (-half_w, half_d, h),
    ]
    return WOKData(
        verts=verts,
        faces=[
            WOKFace(0, 1, 2, surface=surface_id, adj1=-1, adj2=-1, adj3=1),
            WOKFace(0, 2, 3, surface=surface_id, adj1=0, adj2=-1, adj3=-1),
        ],
    )


def build_cylinder_mesh(primitive: CylinderPrimitive) -> PrimitiveMesh:
    segments = max(3, int(primitive.segments))
    radius = float(primitive.radius)
    half_h = float(primitive.height) * 0.5
    cx, cy, cz = primitive.center
    vertices: list[Vec3] = [(cx, cy, cz - half_h), (cx, cy, cz + half_h)]
    for index in range(segments):
        angle = (math.tau * index) / segments
        x = cx + math.cos(angle) * radius
        y = cy + math.sin(angle) * radius
        vertices.append((x, y, cz - half_h))
        vertices.append((x, y, cz + half_h))
    faces: list[Face] = []
    for index in range(segments):
        b0 = 2 + index * 2
        t0 = b0 + 1
        b1 = 2 + ((index + 1) % segments) * 2
        t1 = b1 + 1
        faces.append((0, b1, b0))
        faces.append((1, t0, t1))
        faces.append((b0, b1, t1))
        faces.append((b0, t1, t0))
    return _mesh(
        name=primitive.name,
        vertices=tuple(vertices),
        faces=tuple(faces),
        material=primitive.material,
        primitive="cylinder",
        metadata={"segments": segments},
    )


def build_door_frame_mesh(primitive: DoorFramePrimitive) -> PrimitiveMesh:
    """Build a rectangular U-shaped doorway frame from deterministic box parts."""

    width = max(0.001, float(primitive.width))
    height = max(0.001, float(primitive.height))
    depth = max(0.001, float(primitive.depth))
    jamb_width = max(0.001, min(float(primitive.jamb_width), width * 0.45))
    lintel_height = max(0.001, min(float(primitive.lintel_height), height * 0.8))
    cx, cy, cz = primitive.center
    bottom = cz - height * 0.5
    top = cz + height * 0.5
    jamb_height = max(0.001, height - lintel_height)
    half_width = width * 0.5

    vertices: list[Vec3] = []
    faces: list[Face] = []
    for part_mesh in (
        _box_vertices_faces(
                name=f"{primitive.name}_left_jamb",
                x=jamb_width,
                y=depth,
                z=jamb_height,
                center=(cx - half_width + jamb_width * 0.5, cy, bottom + jamb_height * 0.5),
                material=primitive.material,
                primitive="door_frame_jamb",
        ),
        _box_vertices_faces(
                name=f"{primitive.name}_right_jamb",
                x=jamb_width,
                y=depth,
                z=jamb_height,
                center=(cx + half_width - jamb_width * 0.5, cy, bottom + jamb_height * 0.5),
                material=primitive.material,
                primitive="door_frame_jamb",
        ),
        _box_vertices_faces(
                name=f"{primitive.name}_lintel",
                x=width,
                y=depth,
                z=lintel_height,
                center=(cx, cy, top - lintel_height * 0.5),
                material=primitive.material,
                primitive="door_frame_lintel",
        ),
    ):
        _append_mesh_parts(vertices, faces, part_mesh)

    return _mesh(
        name=primitive.name,
        vertices=tuple(vertices),
        faces=tuple(faces),
        material=primitive.material,
        primitive="door_frame",
        metadata={
            "jamb_width": jamb_width,
            "lintel_height": lintel_height,
            "opening_width": max(0.0, width - jamb_width * 2.0),
            "opening_height": max(0.0, height - lintel_height),
            "depth": depth,
            "kotor_intent": "doorway_frame_transition_blockout",
        },
    )


def build_arch_mesh(primitive: ArchPrimitive) -> PrimitiveMesh:
    """Build a segmented semi-circular doorway arch frame."""

    width = max(0.001, float(primitive.width))
    height = max(0.001, float(primitive.height))
    depth = max(0.001, float(primitive.depth))
    outer_radius = width * 0.5
    frame = max(0.001, min(float(primitive.frame_thickness), outer_radius * 0.95))
    inner_radius = max(0.001, outer_radius - frame)
    segments = max(4, int(primitive.segments))
    cx, cy, cz = primitive.center
    bottom = cz - height * 0.5
    top = cz + height * 0.5
    spring_z = max(bottom, top - outer_radius)
    pillar_height = max(0.001, spring_z - bottom)
    half_depth = depth * 0.5

    vertices: list[Vec3] = []
    faces: list[Face] = []
    for pillar_name, pillar_x in (
        ("left", cx - outer_radius + frame * 0.5),
        ("right", cx + outer_radius - frame * 0.5),
    ):
        pillar = _box_vertices_faces(
            name=f"{primitive.name}_{pillar_name}_pillar",
            x=frame,
            y=depth,
            z=pillar_height,
            center=(pillar_x, cy, bottom + pillar_height * 0.5),
            material=primitive.material,
            primitive="arch_pillar",
        )
        _append_mesh_parts(vertices, faces, pillar)

    band_start = len(vertices)
    for index in range(segments + 1):
        angle = math.pi - (math.pi * index / segments)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        vertices.extend(
            (
                (cx + cos_a * outer_radius, cy - half_depth, spring_z + sin_a * outer_radius),
                (cx + cos_a * inner_radius, cy - half_depth, spring_z + sin_a * inner_radius),
                (cx + cos_a * outer_radius, cy + half_depth, spring_z + sin_a * outer_radius),
                (cx + cos_a * inner_radius, cy + half_depth, spring_z + sin_a * inner_radius),
            )
        )
    for index in range(segments):
        a = band_start + index * 4
        b = band_start + (index + 1) * 4
        outer_front_a, inner_front_a, outer_back_a, inner_back_a = a, a + 1, a + 2, a + 3
        outer_front_b, inner_front_b, outer_back_b, inner_back_b = b, b + 1, b + 2, b + 3
        faces.extend(
            (
                (outer_front_a, outer_front_b, inner_front_b),
                (outer_front_a, inner_front_b, inner_front_a),
                (outer_back_a, inner_back_b, outer_back_b),
                (outer_back_a, inner_back_a, inner_back_b),
                (outer_front_a, outer_back_b, outer_front_b),
                (outer_front_a, outer_back_a, outer_back_b),
                (inner_front_a, inner_front_b, inner_back_b),
                (inner_front_a, inner_back_b, inner_back_a),
            )
        )
    start = band_start
    end = band_start + segments * 4
    faces.extend(
        (
            (start, start + 1, start + 3),
            (start, start + 3, start + 2),
            (end, end + 3, end + 1),
            (end, end + 2, end + 3),
        )
    )
    return _mesh(
        name=primitive.name,
        vertices=tuple(vertices),
        faces=tuple(faces),
        material=primitive.material,
        primitive="arch",
        metadata={
            "segments": segments,
            "frame_thickness": frame,
            "opening_width": inner_radius * 2.0,
            "opening_height": spring_z - bottom,
            "depth": depth,
        },
    )


__all__ = [
    "ArchPrimitive",
    "CubePrimitive",
    "CylinderPrimitive",
    "DoorFramePrimitive",
    "FloorPrimitive",
    "PrimitiveMaterial",
    "RampPrimitive",
    "StairsPrimitive",
    "WallPrimitive",
    "build_arch_mesh",
    "build_cube_mesh",
    "build_cylinder_mesh",
    "build_door_frame_mesh",
    "build_floor_mesh",
    "build_floor_wok",
    "build_ramp_mesh",
    "build_ramp_wok",
    "build_stairs_mesh",
    "build_stairs_wok",
    "build_wall_mesh",
]
