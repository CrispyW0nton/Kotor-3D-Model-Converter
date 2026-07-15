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
    subdivisions_width: int = 1
    subdivisions_depth: int = 1


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
    subdivisions_x: int = 1
    subdivisions_y: int = 1
    subdivisions_z: int = 1


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
class SpherePrimitive:
    """Maya-style polygon sphere with editable axis/height subdivisions."""

    name: str
    radius: float = 0.5
    subdivisions_axis: int = 20
    subdivisions_height: int = 20
    center: Vec3 = (0.0, 0.0, 0.5)
    material: PrimitiveMaterial = field(default_factory=PrimitiveMaterial)


@dataclass(frozen=True)
class ConePrimitive:
    """Maya-style capped polygon cone."""

    name: str
    radius: float = 0.5
    height: float = 1.0
    subdivisions_axis: int = 20
    subdivisions_height: int = 1
    subdivisions_caps: int = 1
    center: Vec3 = (0.0, 0.0, 0.5)
    material: PrimitiveMaterial = field(default_factory=PrimitiveMaterial)


@dataclass(frozen=True)
class TorusPrimitive:
    """Maya-style polygon torus with independent ring/tube subdivisions."""

    name: str
    radius: float = 1.0
    section_radius: float = 0.25
    subdivisions_axis: int = 20
    subdivisions_height: int = 20
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
    normals: tuple[Vec3, ...] | None = None,
    uvs: tuple[Vec2, ...] | None = None,
) -> PrimitiveMesh:
    resolved_normals = normals if normals is not None else ((0.0, 0.0, 1.0),) * len(vertices)
    resolved_uvs = uvs if uvs is not None else tuple((0.0, 0.0) for _ in vertices)
    return PrimitiveMesh(
        name=name,
        vertices=vertices,
        faces=faces,
        normals=resolved_normals,
        uvs=resolved_uvs,
        texture=material.texture,
        diffuse=material.diffuse,
        ambient=material.ambient,
        metadata={"primitive": primitive, **dict(metadata or {}), **dict(material.metadata)},
    )


def _append_corner_triangle(
    vertices: list[Vec3],
    faces: list[Face],
    normals: list[Vec3],
    uvs: list[Vec2],
    corners: tuple[tuple[Vec3, Vec3, Vec2], tuple[Vec3, Vec3, Vec2], tuple[Vec3, Vec3, Vec2]],
) -> None:
    """Append a triangle with independent face-corner attributes.

    ``PrimitiveMesh`` indexes positions, normals, and UVs through one shared
    vertex index.  Expanding each triangle corner is therefore the reliable
    representation for UV seams and hard cap/side normal boundaries.
    """

    start = len(vertices)
    for position, normal, uv in corners:
        vertices.append(position)
        normals.append(normal)
        uvs.append(uv)
    faces.append((start, start + 1, start + 2))


def _append_subdivided_quad(
    vertices: list[Vec3],
    faces: list[Face],
    normals: list[Vec3],
    uvs: list[Vec2],
    *,
    origin: Vec3,
    u_vector: Vec3,
    v_vector: Vec3,
    u_subdivisions: int,
    v_subdivisions: int,
    normal: Vec3,
) -> None:
    """Append one outward quad grid with one shared normal and 0..1 UV island."""

    u_count = max(1, int(u_subdivisions))
    v_count = max(1, int(v_subdivisions))
    start = len(vertices)
    if u_count == 1 and v_count == 1:
        # Preserve the original face-corner order for the default history
        # settings while fixing normals/UVs.
        corners = (
            origin,
            tuple(origin[axis] + u_vector[axis] for axis in range(3)),
            tuple(origin[axis] + u_vector[axis] + v_vector[axis] for axis in range(3)),
            tuple(origin[axis] + v_vector[axis] for axis in range(3)),
        )
        vertices.extend(corners)
        normals.extend((normal,) * 4)
        uvs.extend(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)))
        faces.extend(((start, start + 1, start + 2), (start, start + 2, start + 3)))
        return

    for v_index in range(v_count + 1):
        v = v_index / v_count
        for u_index in range(u_count + 1):
            u = u_index / u_count
            vertices.append(
                tuple(
                    origin[axis] + u_vector[axis] * u + v_vector[axis] * v
                    for axis in range(3)
                )
            )
            normals.append(normal)
            uvs.append((u, v))
    stride = u_count + 1
    for v_index in range(v_count):
        for u_index in range(u_count):
            a = start + v_index * stride + u_index
            b = a + 1
            c = a + stride
            d = c + 1
            faces.extend(((a, b, d), (a, d, c)))


def _box_vertices_faces(
    *,
    name: str,
    x: float,
    y: float,
    z: float,
    center: Vec3,
    material: PrimitiveMaterial,
    primitive: str,
    subdivisions_x: int = 1,
    subdivisions_y: int = 1,
    subdivisions_z: int = 1,
) -> PrimitiveMesh:
    """Build a Maya-style hard-edged box with outward winding and face UVs.

    A polygon cube needs independent face corners: one spatial corner belongs
    to three different hard normals and three UV islands.  Twenty-four indexed
    vertices preserve those attributes without relying on unsupported separate
    normal/UV index streams.
    """

    hx = float(x) * 0.5
    hy = float(y) * 0.5
    hz = float(z) * 0.5
    cx, cy, cz = center
    p000 = (cx - hx, cy - hy, cz - hz)
    p100 = (cx + hx, cy - hy, cz - hz)
    p110 = (cx + hx, cy + hy, cz - hz)
    p010 = (cx - hx, cy + hy, cz - hz)
    p001 = (cx - hx, cy - hy, cz + hz)
    p101 = (cx + hx, cy - hy, cz + hz)
    p111 = (cx + hx, cy + hy, cz + hz)
    p011 = (cx - hx, cy + hy, cz + hz)
    sub_x = max(1, int(subdivisions_x))
    sub_y = max(1, int(subdivisions_y))
    sub_z = max(1, int(subdivisions_z))
    vertices: list[Vec3] = []
    faces: list[Face] = []
    normals: list[Vec3] = []
    uvs: list[Vec2] = []
    face_specs: tuple[tuple[Vec3, Vec3, Vec3, int, int, Vec3], ...] = (
        (p000, (0.0, y, 0.0), (x, 0.0, 0.0), sub_y, sub_x, (0.0, 0.0, -1.0)),
        (p001, (x, 0.0, 0.0), (0.0, y, 0.0), sub_x, sub_y, (0.0, 0.0, 1.0)),
        (p000, (x, 0.0, 0.0), (0.0, 0.0, z), sub_x, sub_z, (0.0, -1.0, 0.0)),
        (p100, (0.0, y, 0.0), (0.0, 0.0, z), sub_y, sub_z, (1.0, 0.0, 0.0)),
        (p110, (-x, 0.0, 0.0), (0.0, 0.0, z), sub_x, sub_z, (0.0, 1.0, 0.0)),
        (p010, (0.0, -y, 0.0), (0.0, 0.0, z), sub_y, sub_z, (-1.0, 0.0, 0.0)),
    )
    for origin, u_vector, v_vector, u_subdivisions, v_subdivisions, normal in face_specs:
        _append_subdivided_quad(
            vertices,
            faces,
            normals,
            uvs,
            origin=origin,
            u_vector=u_vector,
            v_vector=v_vector,
            u_subdivisions=u_subdivisions,
            v_subdivisions=v_subdivisions,
            normal=normal,
        )
    return _mesh(
        name=name,
        vertices=tuple(vertices),
        faces=tuple(faces),
        normals=tuple(normals),
        uvs=tuple(uvs),
        material=material,
        primitive=primitive,
        metadata={
            "hard_face_normals": True,
            "uv_layout": "per_face_0_1",
            "subdivisions_x": sub_x,
            "subdivisions_y": sub_y,
            "subdivisions_z": sub_z,
        },
    )


def _compact_box_part_mesh(*, name: str, x: float, y: float, z: float, center: Vec3, material: PrimitiveMaterial, primitive: str) -> PrimitiveMesh:
    """Compact box positions for composite builders that re-author channels.

    Stairs, doorway frames, and arch pillars concatenate several box parts and
    currently apply one composite material channel afterward.  Keeping their
    eight-corner topology avoids silently changing persisted component indices
    while standalone Cube/Wall use the full Maya-style face-corner contract.
    """

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
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
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
    subdivisions_width = max(1, int(primitive.subdivisions_width))
    subdivisions_depth = max(1, int(primitive.subdivisions_depth))
    vertices: list[Vec3] = []
    faces: list[Face] = []
    normals: list[Vec3] = []
    uvs: list[Vec2] = []
    _append_subdivided_quad(
        vertices,
        faces,
        normals,
        uvs,
        origin=(-half_w, -half_d, z),
        u_vector=(float(primitive.width), 0.0, 0.0),
        v_vector=(0.0, float(primitive.depth), 0.0),
        u_subdivisions=subdivisions_width,
        v_subdivisions=subdivisions_depth,
        normal=(0.0, 0.0, 1.0),
    )
    return _mesh(
        name=primitive.name,
        vertices=tuple(vertices),
        faces=tuple(faces),
        normals=tuple(normals),
        uvs=tuple(uvs),
        material=primitive.material,
        primitive="floor",
        metadata={
            "surface_id": surface_id,
            "surface_name": walkmesh_surface_name(surface_id),
            "subdivisions_width": subdivisions_width,
            "subdivisions_depth": subdivisions_depth,
        },
    )


def build_floor_wok(primitive: FloorPrimitive) -> WOKData:
    surface_id = resolve_walkmesh_surface_id(primitive.surface_id)
    half_w = float(primitive.width) * 0.5
    half_d = float(primitive.depth) * 0.5
    z = float(primitive.z)
    vertices = [
        (-half_w, -half_d, z),
        (half_w, -half_d, z),
        (half_w, half_d, z),
        (-half_w, half_d, z),
    ]
    return WOKData(
        # Render subdivisions do not inflate the engine walkmesh: the same
        # rectangular walkable region remains two stable WOK triangles.
        verts=vertices,
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
        subdivisions_x=primitive.subdivisions_x,
        subdivisions_y=primitive.subdivisions_y,
        subdivisions_z=primitive.subdivisions_z,
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
        step = _compact_box_part_mesh(
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


def build_sphere_mesh(primitive: SpherePrimitive) -> PrimitiveMesh:
    """Build a smooth, seam-safe UV sphere from Maya-style parameters."""

    axis = max(3, int(primitive.subdivisions_axis))
    height = max(2, int(primitive.subdivisions_height))
    radius = float(primitive.radius)
    cx, cy, cz = primitive.center
    vertices: list[Vec3] = []
    faces: list[Face] = []
    normals: list[Vec3] = []
    uvs: list[Vec2] = []

    def corner(u: float, v: float, *, uv: Vec2 | None = None) -> tuple[Vec3, Vec3, Vec2]:
        theta = math.tau * u
        phi = math.pi * v
        sin_phi = math.sin(phi)
        normal = (sin_phi * math.cos(theta), sin_phi * math.sin(theta), math.cos(phi))
        position = (
            cx + normal[0] * radius,
            cy + normal[1] * radius,
            cz + normal[2] * radius,
        )
        return position, normal, uv if uv is not None else (u, v)

    for row in range(height):
        v0 = row / height
        v1 = (row + 1) / height
        for column in range(axis):
            u0 = column / axis
            u1 = (column + 1) / axis
            u_mid = (u0 + u1) * 0.5
            if row == 0:
                _append_corner_triangle(
                    vertices,
                    faces,
                    normals,
                    uvs,
                    (
                        corner(u_mid, 0.0, uv=(u_mid, 0.0)),
                        corner(u0, v1),
                        corner(u1, v1),
                    ),
                )
            elif row == height - 1:
                _append_corner_triangle(
                    vertices,
                    faces,
                    normals,
                    uvs,
                    (
                        corner(u0, v0),
                        corner(u_mid, 1.0, uv=(u_mid, 1.0)),
                        corner(u1, v0),
                    ),
                )
            else:
                p00 = corner(u0, v0)
                p10 = corner(u0, v1)
                p11 = corner(u1, v1)
                p01 = corner(u1, v0)
                _append_corner_triangle(vertices, faces, normals, uvs, (p00, p10, p11))
                _append_corner_triangle(vertices, faces, normals, uvs, (p00, p11, p01))

    return _mesh(
        name=primitive.name,
        vertices=tuple(vertices),
        faces=tuple(faces),
        normals=tuple(normals),
        uvs=tuple(uvs),
        material=primitive.material,
        primitive="sphere",
        metadata={"subdivisions_axis": axis, "subdivisions_height": height},
    )


def build_cone_mesh(primitive: ConePrimitive) -> PrimitiveMesh:
    """Build a capped cone with smooth sides and hard, planar cap normals."""

    axis = max(3, int(primitive.subdivisions_axis))
    height_subdivisions = max(1, int(primitive.subdivisions_height))
    cap_subdivisions = max(1, int(primitive.subdivisions_caps))
    radius = float(primitive.radius)
    height = float(primitive.height)
    half_height = height * 0.5
    cx, cy, cz = primitive.center
    vertices: list[Vec3] = []
    faces: list[Face] = []
    normals: list[Vec3] = []
    uvs: list[Vec2] = []
    slant = math.sqrt(height * height + radius * radius) or 1.0

    def side_corner(u: float, v: float, *, uv: Vec2 | None = None) -> tuple[Vec3, Vec3, Vec2]:
        theta = math.tau * u
        ring_radius = radius * (1.0 - v)
        position = (
            cx + math.cos(theta) * ring_radius,
            cy + math.sin(theta) * ring_radius,
            cz - half_height + height * v,
        )
        normal = (
            math.cos(theta) * height / slant,
            math.sin(theta) * height / slant,
            radius / slant,
        )
        return position, normal, uv if uv is not None else (u, v)

    for row in range(height_subdivisions):
        v0 = row / height_subdivisions
        v1 = (row + 1) / height_subdivisions
        for column in range(axis):
            u0 = column / axis
            u1 = (column + 1) / axis
            p00 = side_corner(u0, v0)
            p10 = side_corner(u1, v0)
            if row == height_subdivisions - 1:
                u_mid = (u0 + u1) * 0.5
                apex = side_corner(u_mid, 1.0, uv=(u_mid, 1.0))
                _append_corner_triangle(vertices, faces, normals, uvs, (p00, p10, apex))
            else:
                p11 = side_corner(u1, v1)
                p01 = side_corner(u0, v1)
                _append_corner_triangle(vertices, faces, normals, uvs, (p00, p10, p11))
                _append_corner_triangle(vertices, faces, normals, uvs, (p00, p11, p01))

    cap_z = cz - half_height
    cap_normal: Vec3 = (0.0, 0.0, -1.0)

    def cap_corner(ring_fraction: float, u: float) -> tuple[Vec3, Vec3, Vec2]:
        theta = math.tau * u
        cos_theta = math.cos(theta)
        sin_theta = math.sin(theta)
        ring_radius = radius * ring_fraction
        return (
            (cx + cos_theta * ring_radius, cy + sin_theta * ring_radius, cap_z),
            cap_normal,
            (0.5 + cos_theta * ring_fraction * 0.5, 0.5 + sin_theta * ring_fraction * 0.5),
        )

    for ring in range(cap_subdivisions):
        inner = ring / cap_subdivisions
        outer = (ring + 1) / cap_subdivisions
        for column in range(axis):
            u0 = column / axis
            u1 = (column + 1) / axis
            if ring == 0:
                _append_corner_triangle(
                    vertices,
                    faces,
                    normals,
                    uvs,
                    (cap_corner(0.0, u0), cap_corner(outer, u1), cap_corner(outer, u0)),
                )
            else:
                inner0 = cap_corner(inner, u0)
                inner1 = cap_corner(inner, u1)
                outer1 = cap_corner(outer, u1)
                outer0 = cap_corner(outer, u0)
                _append_corner_triangle(vertices, faces, normals, uvs, (inner0, inner1, outer1))
                _append_corner_triangle(vertices, faces, normals, uvs, (inner0, outer1, outer0))

    return _mesh(
        name=primitive.name,
        vertices=tuple(vertices),
        faces=tuple(faces),
        normals=tuple(normals),
        uvs=tuple(uvs),
        material=primitive.material,
        primitive="cone",
        metadata={
            "subdivisions_axis": axis,
            "subdivisions_height": height_subdivisions,
            "subdivisions_caps": cap_subdivisions,
        },
    )


def build_torus_mesh(primitive: TorusPrimitive) -> PrimitiveMesh:
    """Build a smooth torus with deterministic seam-expanded triangle corners."""

    axis = max(3, int(primitive.subdivisions_axis))
    height = max(3, int(primitive.subdivisions_height))
    radius = float(primitive.radius)
    section_radius = float(primitive.section_radius)
    cx, cy, cz = primitive.center
    vertices: list[Vec3] = []
    faces: list[Face] = []
    normals: list[Vec3] = []
    uvs: list[Vec2] = []

    def corner(u: float, v: float) -> tuple[Vec3, Vec3, Vec2]:
        theta = math.tau * u
        phi = math.tau * v
        cos_theta = math.cos(theta)
        sin_theta = math.sin(theta)
        cos_phi = math.cos(phi)
        sin_phi = math.sin(phi)
        ring_radius = radius + section_radius * cos_phi
        position = (
            cx + ring_radius * cos_theta,
            cy + ring_radius * sin_theta,
            cz + section_radius * sin_phi,
        )
        normal = (cos_phi * cos_theta, cos_phi * sin_theta, sin_phi)
        return position, normal, (u, v)

    for row in range(height):
        v0 = row / height
        v1 = (row + 1) / height
        for column in range(axis):
            u0 = column / axis
            u1 = (column + 1) / axis
            p00 = corner(u0, v0)
            p10 = corner(u1, v0)
            p11 = corner(u1, v1)
            p01 = corner(u0, v1)
            _append_corner_triangle(vertices, faces, normals, uvs, (p00, p10, p11))
            _append_corner_triangle(vertices, faces, normals, uvs, (p00, p11, p01))

    return _mesh(
        name=primitive.name,
        vertices=tuple(vertices),
        faces=tuple(faces),
        normals=tuple(normals),
        uvs=tuple(uvs),
        material=primitive.material,
        primitive="torus",
        metadata={"subdivisions_axis": axis, "subdivisions_height": height},
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
        _compact_box_part_mesh(
                name=f"{primitive.name}_left_jamb",
                x=jamb_width,
                y=depth,
                z=jamb_height,
                center=(cx - half_width + jamb_width * 0.5, cy, bottom + jamb_height * 0.5),
                material=primitive.material,
                primitive="door_frame_jamb",
        ),
        _compact_box_part_mesh(
                name=f"{primitive.name}_right_jamb",
                x=jamb_width,
                y=depth,
                z=jamb_height,
                center=(cx + half_width - jamb_width * 0.5, cy, bottom + jamb_height * 0.5),
                material=primitive.material,
                primitive="door_frame_jamb",
        ),
        _compact_box_part_mesh(
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
        pillar = _compact_box_part_mesh(
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
    "ConePrimitive",
    "CubePrimitive",
    "CylinderPrimitive",
    "DoorFramePrimitive",
    "FloorPrimitive",
    "PrimitiveMaterial",
    "RampPrimitive",
    "StairsPrimitive",
    "SpherePrimitive",
    "TorusPrimitive",
    "WallPrimitive",
    "build_arch_mesh",
    "build_cone_mesh",
    "build_cube_mesh",
    "build_cylinder_mesh",
    "build_door_frame_mesh",
    "build_floor_mesh",
    "build_floor_wok",
    "build_ramp_mesh",
    "build_ramp_wok",
    "build_stairs_mesh",
    "build_stairs_wok",
    "build_sphere_mesh",
    "build_torus_mesh",
    "build_wall_mesh",
]
