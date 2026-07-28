"""Build and validate Ghost Studio's comprehensive Rhen Var environment kit.

The pack combines Ghost Studio's deterministic original modular pieces with a
curated, permissioned subset of the user-supplied Rhen Var mod archives.
Imported sources are normalized and stored inside the repository, so routine
rebuilds validate them without requiring the original external archives.

Run from the repository root:
    py -3.14 scripts/build_rhen_var_asset_pack.py
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "assets" / "map_studio" / "terrain_kits" / "rhen_var"
MANIFEST_PATH = OUTPUT_ROOT / "manifest.json"
SOURCE_ROOT = OUTPUT_ROOT / "source"
IMPORTED_ROOT = OUTPUT_ROOT / "mod_sources" / "imported"
IMPORTED_PROVENANCE_PATH = IMPORTED_ROOT / "provenance.json"
SKYBOX_ROOT = OUTPUT_ROOT / "skybox"
SKYBOX_PROVENANCE_PATH = SKYBOX_ROOT / "provenance.json"

SOURCE_TEXTURES = {
    "gr_rvsnow": SOURCE_ROOT / "rhen_var_snow_source.png",
    "gr_rvstone": SOURCE_ROOT / "rhen_var_stone_source.png",
    "gr_rvfloor": SOURCE_ROOT / "rhen_var_floor_source.png",
}

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normal(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    cross = _cross(_sub(b, a), _sub(c, a))
    length = math.sqrt(sum(value * value for value in cross))
    if length <= 1.0e-9:
        raise ValueError(f"Degenerate triangle: {a}, {b}, {c}")
    return tuple(value / length for value in cross)  # type: ignore[return-value]


def _rotate_xy(point: Vec3, angle_radians: float, offset: Vec3 = (0.0, 0.0, 0.0)) -> Vec3:
    cosine = math.cos(angle_radians)
    sine = math.sin(angle_radians)
    x, y, z = point
    return (
        offset[0] + x * cosine - y * sine,
        offset[1] + x * sine + y * cosine,
        offset[2] + z,
    )


@dataclass
class Mesh:
    name: str
    material_name: str
    vertices: list[Vec3] = field(default_factory=list)
    uvs: list[Vec2] = field(default_factory=list)
    normals: list[Vec3] = field(default_factory=list)
    faces: list[tuple[int, int, int]] = field(default_factory=list)

    def triangle(
        self,
        a: Vec3,
        b: Vec3,
        c: Vec3,
        uv_a: Vec2 = (0.0, 0.0),
        uv_b: Vec2 = (1.0, 0.0),
        uv_c: Vec2 = (1.0, 1.0),
    ) -> None:
        face_normal = _normal(a, b, c)
        base = len(self.vertices) + 1
        self.vertices.extend((a, b, c))
        self.uvs.extend((uv_a, uv_b, uv_c))
        self.normals.extend((face_normal, face_normal, face_normal))
        self.faces.append((base, base + 1, base + 2))

    def quad(
        self,
        a: Vec3,
        b: Vec3,
        c: Vec3,
        d: Vec3,
        uvs: tuple[Vec2, Vec2, Vec2, Vec2] = (
            (0.0, 0.0),
            (1.0, 0.0),
            (1.0, 1.0),
            (0.0, 1.0),
        ),
    ) -> None:
        self.triangle(a, b, c, uvs[0], uvs[1], uvs[2])
        self.triangle(a, c, d, uvs[0], uvs[2], uvs[3])

    @property
    def triangle_count(self) -> int:
        return len(self.faces)

    def bounds(self) -> tuple[Vec3, Vec3]:
        if not self.vertices:
            raise ValueError(f"{self.name} has no vertices")
        minimum = tuple(min(vertex[axis] for vertex in self.vertices) for axis in range(3))
        maximum = tuple(max(vertex[axis] for vertex in self.vertices) for axis in range(3))
        return minimum, maximum  # type: ignore[return-value]

    def dimensions(self) -> Vec3:
        minimum, maximum = self.bounds()
        return tuple(maximum[axis] - minimum[axis] for axis in range(3))  # type: ignore[return-value]


def _add_box(mesh: Mesh, center: Vec3, size: Vec3) -> None:
    cx, cy, cz = center
    sx, sy, sz = size
    x0, x1 = cx - sx / 2.0, cx + sx / 2.0
    y0, y1 = cy - sy / 2.0, cy + sy / 2.0
    z0, z1 = cz - sz / 2.0, cz + sz / 2.0
    mesh.quad((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0))
    mesh.quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))
    mesh.quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1))
    mesh.quad((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1))
    mesh.quad((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1))
    mesh.quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))


def _add_chamfered_box(
    mesh: Mesh,
    center: Vec3,
    size: Vec3,
    bevel: float,
) -> None:
    cx, cy, cz = center
    sx, sy, sz = size
    x0, x1 = cx - sx / 2.0, cx + sx / 2.0
    y0, y1 = cy - sy / 2.0, cy + sy / 2.0
    z0, z1 = cz - sz / 2.0, cz + sz / 2.0
    bevel = min(bevel, sx * 0.24, sy * 0.24)
    ring_xy = (
        (x0 + bevel, y0),
        (x1 - bevel, y0),
        (x1, y0 + bevel),
        (x1, y1 - bevel),
        (x1 - bevel, y1),
        (x0 + bevel, y1),
        (x0, y1 - bevel),
        (x0, y0 + bevel),
    )
    for index, xy in enumerate(ring_xy):
        next_xy = ring_xy[(index + 1) % len(ring_xy)]
        mesh.quad(
            (xy[0], xy[1], z0),
            (next_xy[0], next_xy[1], z0),
            (next_xy[0], next_xy[1], z1),
            (xy[0], xy[1], z1),
        )
    top_center = (cx, cy, z1)
    bottom_center = (cx, cy, z0)
    for index, xy in enumerate(ring_xy):
        next_xy = ring_xy[(index + 1) % len(ring_xy)]
        mesh.triangle(
            top_center,
            (xy[0], xy[1], z1),
            (next_xy[0], next_xy[1], z1),
            (0.5, 0.5),
            (0.0, 0.0),
            (1.0, 0.0),
        )
        mesh.triangle(
            bottom_center,
            (next_xy[0], next_xy[1], z0),
            (xy[0], xy[1], z0),
            (0.5, 0.5),
            (1.0, 0.0),
            (0.0, 0.0),
        )


def _add_tapered_prism(
    mesh: Mesh,
    center_xy: Vec2,
    z_min: float,
    z_max: float,
    bottom_size: Vec2,
    top_size: Vec2,
    sides: int = 8,
    rotation: float = math.pi / 8.0,
) -> None:
    cx, cy = center_xy
    bottom: list[Vec3] = []
    top: list[Vec3] = []
    for index in range(sides):
        angle = rotation + math.tau * index / sides
        bottom.append(
            (
                cx + math.cos(angle) * bottom_size[0] / 2.0,
                cy + math.sin(angle) * bottom_size[1] / 2.0,
                z_min,
            )
        )
        top.append(
            (
                cx + math.cos(angle) * top_size[0] / 2.0,
                cy + math.sin(angle) * top_size[1] / 2.0,
                z_max,
            )
        )
    for index in range(sides):
        next_index = (index + 1) % sides
        mesh.quad(bottom[index], bottom[next_index], top[next_index], top[index])
    bottom_center = (cx, cy, z_min)
    top_center = (cx, cy, z_max)
    for index in range(sides):
        next_index = (index + 1) % sides
        mesh.triangle(top_center, top[index], top[next_index])
        mesh.triangle(bottom_center, bottom[next_index], bottom[index])


def _add_arch_ring(
    mesh: Mesh,
    center_x: float,
    center_y: float,
    spring_z: float,
    outer_radius: Vec2,
    inner_radius: Vec2,
    depth: float,
    segments: int = 16,
) -> None:
    outer_front: list[Vec3] = []
    outer_back: list[Vec3] = []
    inner_front: list[Vec3] = []
    inner_back: list[Vec3] = []
    for index in range(segments + 1):
        angle = math.pi * index / segments
        cosine = math.cos(angle)
        sine = math.sin(angle)
        outer_front.append(
            (
                center_x + cosine * outer_radius[0],
                center_y - depth / 2.0,
                spring_z + sine * outer_radius[1],
            )
        )
        outer_back.append(
            (
                center_x + cosine * outer_radius[0],
                center_y + depth / 2.0,
                spring_z + sine * outer_radius[1],
            )
        )
        inner_front.append(
            (
                center_x + cosine * inner_radius[0],
                center_y - depth / 2.0,
                spring_z + sine * inner_radius[1],
            )
        )
        inner_back.append(
            (
                center_x + cosine * inner_radius[0],
                center_y + depth / 2.0,
                spring_z + sine * inner_radius[1],
            )
        )
    for index in range(segments):
        mesh.quad(
            outer_front[index],
            outer_front[index + 1],
            inner_front[index + 1],
            inner_front[index],
        )
        mesh.quad(
            outer_back[index + 1],
            outer_back[index],
            inner_back[index],
            inner_back[index + 1],
        )
        mesh.quad(
            outer_front[index],
            outer_back[index],
            outer_back[index + 1],
            outer_front[index + 1],
        )
        mesh.quad(
            inner_front[index + 1],
            inner_back[index + 1],
            inner_back[index],
            inner_front[index],
        )
    for index in (0, segments):
        mesh.quad(
            outer_front[index],
            inner_front[index],
            inner_back[index],
            outer_back[index],
        )


def _add_arch_with_piers(
    mesh: Mesh,
    center_x: float,
    center_y: float,
    spring_z: float,
    outer_radius: Vec2,
    inner_radius: Vec2,
    depth: float,
) -> None:
    _add_arch_ring(
        mesh,
        center_x,
        center_y,
        spring_z,
        outer_radius,
        inner_radius,
        depth,
    )
    pier_width = outer_radius[0] - inner_radius[0]
    pier_x = (outer_radius[0] + inner_radius[0]) / 2.0
    for sign in (-1.0, 1.0):
        _add_chamfered_box(
            mesh,
            (center_x + sign * pier_x, center_y, spring_z / 2.0),
            (pier_width, depth, spring_z),
            min(0.12, pier_width * 0.16),
        )


def _add_rock(
    mesh: Mesh,
    center: Vec3,
    radii: Vec3,
    seed: int,
    sectors: int = 10,
    rings: int = 4,
) -> None:
    cx, cy, cz = center
    ring_vertices: list[list[Vec3]] = []
    for ring_index in range(rings):
        t = ring_index / max(1, rings - 1)
        z = cz + radii[2] * t
        profile = 0.72 + 0.36 * math.sin(math.pi * t)
        if ring_index == rings - 1:
            profile = 0.30
        ring: list[Vec3] = []
        for sector in range(sectors):
            angle = math.tau * sector / sectors
            variation = 1.0 + 0.13 * math.sin(
                seed * 1.731 + sector * 2.119 + ring_index * 0.917
            )
            ring.append(
                (
                    cx + math.cos(angle) * radii[0] * profile * variation,
                    cy + math.sin(angle) * radii[1] * profile / variation,
                    z
                    + 0.08
                    * radii[2]
                    * math.sin(seed * 0.73 + sector * 1.71 + ring_index),
                )
            )
        ring_vertices.append(ring)
    for ring_index in range(rings - 1):
        lower = ring_vertices[ring_index]
        upper = ring_vertices[ring_index + 1]
        for sector in range(sectors):
            next_sector = (sector + 1) % sectors
            mesh.quad(
                lower[sector],
                lower[next_sector],
                upper[next_sector],
                upper[sector],
            )
    bottom = (cx, cy, cz)
    top = (cx, cy, cz + radii[2] * 1.08)
    for sector in range(sectors):
        next_sector = (sector + 1) % sectors
        mesh.triangle(bottom, ring_vertices[0][next_sector], ring_vertices[0][sector])
        mesh.triangle(top, ring_vertices[-1][sector], ring_vertices[-1][next_sector])


def _append_mesh_transformed(
    target: Mesh,
    source: Mesh,
    rotation: float = 0.0,
    offset: Vec3 = (0.0, 0.0, 0.0),
) -> None:
    """Append a small detail mesh while preserving face-corner UVs."""

    for face in source.faces:
        corners = tuple(
            (
                _rotate_xy(source.vertices[index - 1], rotation, offset),
                source.uvs[index - 1],
            )
            for index in face
        )
        target.triangle(
            corners[0][0],
            corners[1][0],
            corners[2][0],
            corners[0][1],
            corners[1][1],
            corners[2][1],
        )


def _add_rotated_chamfered_box(
    mesh: Mesh,
    center: Vec3,
    size: Vec3,
    bevel: float,
    rotation: float,
) -> None:
    detail = Mesh(f"{mesh.name}_rotated_detail", mesh.material_name)
    _add_chamfered_box(detail, (0.0, 0.0, 0.0), size, bevel)
    _append_mesh_transformed(mesh, detail, rotation, center)


def _add_arch_relief(
    mesh: Mesh,
    center: Vec3,
    spring_z: float,
    outer_radius: Vec2,
    inner_radius: Vec2,
    depth: float,
    rotation: float = 0.0,
    segments: int = 12,
) -> None:
    """Add a shallow, solid arch molding that can face any horizontal direction."""

    detail = Mesh(f"{mesh.name}_arch_relief", mesh.material_name)
    _add_arch_ring(
        detail,
        0.0,
        0.0,
        spring_z,
        outer_radius,
        inner_radius,
        depth,
        segments,
    )
    _append_mesh_transformed(mesh, detail, rotation, center)


def _add_faceted_canyon_span(mesh: Mesh) -> None:
    """Build a watertight 16 m concave canyon wall from coarse rock facets."""

    xs = (-8.0, -6.0, -4.0, -2.0, 0.0, 2.0, 4.0, 6.0, 8.0)
    heights = (8.4, 9.15, 8.75, 9.85, 9.35, 8.9, 10.15, 9.1, 8.4)
    levels = (0.0, 0.22, 0.49, 0.74, 1.0)
    front: list[list[Vec3]] = []
    back: list[list[Vec3]] = []
    for column, (x, height) in enumerate(zip(xs, heights)):
        edge_ratio = abs(x) / 8.0
        concavity = 1.55 * (1.0 - edge_ratio**1.35)
        front_column: list[Vec3] = []
        back_column: list[Vec3] = []
        for level_index, level in enumerate(levels):
            front_y = (
                -1.18
                + concavity
                + 0.22 * math.sin(column * 1.73 + level_index * 2.17)
                + 0.10 * math.cos(column * 0.81 - level_index * 1.31)
            )
            back_y = (
                2.35
                + 0.18 * math.sin(column * 1.11 + level_index * 0.79)
                + 0.08 * math.cos(column * 2.03 - level_index)
            )
            z = height * level
            if 0.0 < level < 1.0:
                z += 0.16 * math.sin(column * 1.27 + level_index * 1.89)
            front_column.append((x, front_y, z))
            back_column.append((x, back_y, z + (0.12 if level == 1.0 else 0.0)))
        front.append(front_column)
        back.append(back_column)

    last_level = len(levels) - 1
    for column in range(len(xs) - 1):
        for level_index in range(last_level):
            mesh.quad(
                front[column][level_index],
                front[column + 1][level_index],
                front[column + 1][level_index + 1],
                front[column][level_index + 1],
            )
            mesh.quad(
                back[column + 1][level_index],
                back[column][level_index],
                back[column][level_index + 1],
                back[column + 1][level_index + 1],
            )
        mesh.quad(
            front[column][last_level],
            front[column + 1][last_level],
            back[column + 1][last_level],
            back[column][last_level],
        )
        mesh.quad(
            front[column][0],
            back[column][0],
            back[column + 1][0],
            front[column + 1][0],
        )
    for column, outward_order in (
        (0, (front, back)),
        (len(xs) - 1, (back, front)),
    ):
        first_surface, second_surface = outward_order
        for level_index in range(last_level):
            mesh.quad(
                first_surface[column][level_index],
                first_surface[column][level_index + 1],
                second_surface[column][level_index + 1],
                second_surface[column][level_index],
            )


def _asset_canyon_wall_16m() -> Mesh:
    mesh = Mesh("rv_canyon_wall_16m", "gr_rvstone_material")
    _add_faceted_canyon_span(mesh)
    for center, radii, seed in (
        ((-5.1, -1.55, 0.0), (1.35, 0.85, 2.45), 31),
        ((1.8, -0.65, 0.0), (1.55, 0.95, 2.05), 37),
        ((5.3, -1.35, 0.0), (1.10, 0.70, 3.15), 41),
    ):
        _add_rock(mesh, center, radii, seed, sectors=8, rings=4)
    return mesh


def _asset_canyon_corner() -> Mesh:
    """A faceted 90-degree canyon turn with a continuous, solid rock volume."""

    mesh = Mesh("rv_canyon_corner", "gr_rvstone_material")
    segments = 8
    levels = (0.0, 0.24, 0.51, 0.76, 1.0)
    angles = tuple(-math.pi / 2.0 + (math.pi / 2.0) * i / segments for i in range(segments + 1))
    heights = (8.4, 9.05, 8.7, 9.65, 9.2, 10.0, 9.15, 8.85, 8.4)
    inner: list[list[Vec3]] = []
    outer: list[list[Vec3]] = []
    for segment, (angle, height) in enumerate(zip(angles, heights)):
        inner_column: list[Vec3] = []
        outer_column: list[Vec3] = []
        for level_index, level in enumerate(levels):
            inner_radius = (
                5.55
                + 0.24 * math.sin(segment * 1.67 + level_index * 1.39)
                + 0.12 * math.cos(segment * 0.77 - level_index * 1.91)
            )
            outer_radius = (
                9.05
                + 0.20 * math.sin(segment * 1.03 + level_index * 1.71)
                + 0.09 * math.cos(segment * 2.11 - level_index)
            )
            z = height * level
            if 0.0 < level < 1.0:
                z += 0.14 * math.sin(segment * 1.37 + level_index * 2.03)
            inner_column.append(
                (math.cos(angle) * inner_radius, math.sin(angle) * inner_radius, z)
            )
            outer_column.append(
                (
                    math.cos(angle) * outer_radius,
                    math.sin(angle) * outer_radius,
                    z + (0.12 if level == 1.0 else 0.0),
                )
            )
        inner.append(inner_column)
        outer.append(outer_column)

    last_level = len(levels) - 1
    for segment in range(segments):
        for level_index in range(last_level):
            mesh.quad(
                inner[segment + 1][level_index],
                inner[segment][level_index],
                inner[segment][level_index + 1],
                inner[segment + 1][level_index + 1],
            )
            mesh.quad(
                outer[segment][level_index],
                outer[segment + 1][level_index],
                outer[segment + 1][level_index + 1],
                outer[segment][level_index + 1],
            )
        mesh.quad(
            inner[segment][last_level],
            outer[segment][last_level],
            outer[segment + 1][last_level],
            inner[segment + 1][last_level],
        )
        mesh.quad(
            inner[segment + 1][0],
            outer[segment + 1][0],
            outer[segment][0],
            inner[segment][0],
        )
    for segment, surfaces in (
        (0, (outer, inner)),
        (segments, (inner, outer)),
    ):
        first_surface, second_surface = surfaces
        for level_index in range(last_level):
            mesh.quad(
                first_surface[segment][level_index],
                first_surface[segment][level_index + 1],
                second_surface[segment][level_index + 1],
                second_surface[segment][level_index],
            )

    for center, radii, seed in (
        ((1.5, -5.4, 0.0), (1.1, 0.75, 2.1), 43),
        ((4.1, -3.8, 0.0), (1.35, 0.9, 2.7), 47),
        ((5.7, -1.2, 0.0), (0.9, 0.7, 1.8), 53),
    ):
        _add_rock(mesh, center, radii, seed, sectors=8, rings=4)
    return mesh


def _asset_snow_drift() -> Mesh:
    mesh = Mesh("rv_snow_drift", "gr_rvsnow_material")
    sectors = 24
    radial_levels = (1.0, 0.78, 0.52, 0.26)
    rings: list[list[Vec3]] = []
    for ring_index, radius in enumerate(radial_levels):
        ring: list[Vec3] = []
        for sector in range(sectors):
            angle = math.tau * sector / sectors
            distortion = 1.0 + 0.08 * math.sin(sector * 2.31 + ring_index * 1.17)
            x = math.cos(angle) * 3.8 * radius * distortion
            y = math.sin(angle) * 2.45 * radius / distortion
            z = 0.05 + 1.75 * (1.0 - radius**1.65)
            z += 0.08 * math.sin(angle * 3.0 + ring_index)
            ring.append((x, y, z))
        rings.append(ring)
    for ring_index in range(len(rings) - 1):
        for sector in range(sectors):
            next_sector = (sector + 1) % sectors
            mesh.quad(
                rings[ring_index][sector],
                rings[ring_index][next_sector],
                rings[ring_index + 1][next_sector],
                rings[ring_index + 1][sector],
            )
    summit = (0.35, -0.18, 1.95)
    for sector in range(sectors):
        next_sector = (sector + 1) % sectors
        mesh.triangle(summit, rings[-1][sector], rings[-1][next_sector])
        mesh.triangle((0.0, 0.0, 0.0), rings[0][next_sector], rings[0][sector])
    return mesh


def _asset_ice_ridge() -> Mesh:
    mesh = Mesh("rv_ice_ridge", "gr_rvsnow_material")
    xs = (-8.0, -6.0, -4.0, -2.0, 0.0, 2.0, 4.0, 6.0, 8.0)
    heights = (0.7, 2.4, 3.7, 4.9, 4.2, 5.5, 3.6, 2.1, 0.65)
    front: list[Vec3] = []
    back: list[Vec3] = []
    for index, (x, height) in enumerate(zip(xs, heights)):
        front.append((x, -1.65 + 0.18 * math.sin(index * 1.7), height))
        back.append((x, 1.45 + 0.15 * math.cos(index * 1.3), height * 0.88 + 0.25))
    for index in range(len(xs) - 1):
        mesh.quad(front[index], front[index + 1], back[index + 1], back[index])
        mesh.quad(
            (xs[index], -1.65, 0.0),
            (xs[index + 1], -1.65, 0.0),
            front[index + 1],
            front[index],
        )
        mesh.quad(
            (xs[index + 1], 1.45, 0.0),
            (xs[index], 1.45, 0.0),
            back[index],
            back[index + 1],
        )
        mesh.quad(
            (xs[index], 1.45, 0.0),
            (xs[index + 1], 1.45, 0.0),
            (xs[index + 1], -1.65, 0.0),
            (xs[index], -1.65, 0.0),
        )
    mesh.quad(
        (xs[0], 1.45, 0.0),
        (xs[0], -1.65, 0.0),
        front[0],
        back[0],
    )
    mesh.quad(
        (xs[-1], -1.65, 0.0),
        (xs[-1], 1.45, 0.0),
        back[-1],
        front[-1],
    )
    for x, y, z, size in (
        (-4.7, -1.72, 1.4, (2.4, 0.24, 0.7)),
        (-0.8, -1.82, 2.1, (3.2, 0.22, 0.55)),
        (3.2, -1.72, 1.5, (2.8, 0.20, 0.45)),
    ):
        _add_chamfered_box(mesh, (x, y, z), size, 0.08)
    return mesh


def _asset_rock_cluster() -> Mesh:
    mesh = Mesh("rv_rock_cluster", "gr_rvstone_material")
    rocks = (
        ((-1.5, 0.2, 0.0), (1.7, 1.4, 2.4), 3),
        ((1.2, -0.65, 0.0), (1.35, 1.1, 1.8), 7),
        ((0.65, 1.3, 0.0), (0.95, 0.85, 1.25), 11),
        ((-2.5, -1.25, 0.0), (0.85, 0.75, 1.1), 19),
        ((2.45, 0.75, 0.0), (0.75, 0.65, 0.9), 23),
    )
    for center, radii, seed in rocks:
        _add_rock(mesh, center, radii, seed)
    return mesh


def _add_broken_wall(
    mesh: Mesh,
    center: Vec3,
    length: float,
    depth: float,
    heights: Sequence[float],
    rotation: float = 0.0,
) -> None:
    segment_width = length / len(heights)
    for index, height in enumerate(heights):
        local_x = -length / 2.0 + segment_width * (index + 0.5)
        local_center = (local_x, 0.0, height / 2.0)
        rotated_center = _rotate_xy(local_center, rotation, center)
        _add_chamfered_box(
            mesh,
            rotated_center,
            (segment_width + 0.04, depth, height),
            0.06,
        )


def _asset_ruin_wall() -> Mesh:
    mesh = Mesh("rv_ruin_wall", "gr_rvstone_material")
    _add_broken_wall(
        mesh,
        (0.0, 0.0, 0.0),
        8.0,
        0.85,
        (5.3, 5.7, 5.45, 4.9, 5.15, 4.35, 3.85, 4.55),
    )
    _add_chamfered_box(mesh, (0.0, 0.0, 0.28), (8.0, 1.05, 0.56), 0.10)
    for x in (-3.0, -1.0, 1.0, 3.0):
        _add_chamfered_box(mesh, (x, -0.49, 2.15), (0.18, 0.16, 2.3), 0.04)
    _add_chamfered_box(mesh, (-1.6, -0.51, 3.55), (3.0, 0.14, 0.22), 0.04)
    return mesh


def _asset_ruin_corner() -> Mesh:
    mesh = Mesh("rv_ruin_corner", "gr_rvstone_material")
    heights_a = (5.4, 5.6, 5.15, 4.7, 4.1, 3.8, 4.3, 4.8)
    heights_b = (5.25, 5.55, 5.35, 4.95, 4.55, 4.05, 3.7, 4.2)
    _add_broken_wall(mesh, (0.0, 0.0, 0.0), 8.0, 0.85, heights_a)
    _add_broken_wall(mesh, (-3.58, 3.58, 0.0), 8.0, 0.85, heights_b, math.pi / 2.0)
    _add_chamfered_box(mesh, (-3.55, 0.0, 2.8), (1.25, 1.25, 5.6), 0.16)
    return mesh


def _asset_temple_arch() -> Mesh:
    mesh = Mesh("rv_temple_arch", "gr_rvstone_material")
    _add_arch_with_piers(
        mesh,
        0.0,
        0.0,
        2.75,
        (3.45, 3.15),
        (2.30, 2.20),
        1.40,
    )
    _add_arch_ring(
        mesh,
        0.0,
        -0.76,
        2.75,
        (3.12, 2.82),
        (2.62, 2.39),
        0.18,
        16,
    )
    for sign in (-1.0, 1.0):
        _add_chamfered_box(mesh, (sign * 3.08, 0.0, 0.32), (1.50, 1.95, 0.64), 0.15)
        _add_chamfered_box(mesh, (sign * 3.02, 0.0, 2.7), (1.28, 1.66, 0.38), 0.10)
    _add_chamfered_box(mesh, (0.0, 0.18, 0.16), (8.0, 2.3, 0.32), 0.12)
    return mesh


def _asset_buttress() -> Mesh:
    mesh = Mesh("rv_buttress", "gr_rvstone_material")
    _add_tapered_prism(mesh, (0.0, 0.0), 0.0, 5.8, (3.2, 4.0), (1.45, 1.65), 8)
    _add_chamfered_box(mesh, (0.0, 0.4, 0.35), (3.8, 4.8, 0.70), 0.18)
    _add_chamfered_box(mesh, (0.0, 0.25, 1.15), (2.9, 3.7, 0.42), 0.12)
    _add_chamfered_box(mesh, (0.0, 0.0, 5.75), (1.9, 2.1, 0.45), 0.10)
    return mesh


def _asset_broken_pillar() -> Mesh:
    mesh = Mesh("rv_broken_pillar", "gr_rvstone_material")
    _add_tapered_prism(mesh, (0.0, 0.0), 0.0, 0.45, (2.25, 2.25), (2.10, 2.10), 8)
    _add_tapered_prism(mesh, (0.0, 0.0), 0.45, 0.82, (1.85, 1.85), (1.65, 1.65), 8)
    _add_tapered_prism(mesh, (0.0, 0.0), 0.82, 4.35, (1.42, 1.42), (1.18, 1.18), 8)
    _add_tapered_prism(mesh, (0.02, -0.01), 4.35, 4.75, (1.40, 1.40), (1.05, 1.10), 7)
    for x, y, z, radii, seed in (
        ((-0.65), 0.55, 0.0, (0.42, 0.35, 0.48), 31),
        (0.72, 0.25, 0.0, (0.36, 0.30, 0.38), 37),
        (0.30, -0.72, 0.0, (0.28, 0.34, 0.30), 41),
    ):
        _add_rock(mesh, (x, y, z), radii, seed, 8, 3)
    return mesh


def _asset_ruin_stairs() -> Mesh:
    mesh = Mesh("rv_ruin_stairs", "gr_rvfloor_material")
    step_count = 12
    width = 8.0
    total_depth = 8.0
    total_height = 3.2
    step_depth = total_depth / step_count
    for step in range(step_count):
        height = total_height * (step + 1) / step_count
        y_center = -total_depth / 2.0 + step_depth * (step + 0.5)
        _add_box(mesh, (0.0, y_center, height / 2.0), (width, step_depth + 0.02, height))
    for sign in (-1.0, 1.0):
        _add_chamfered_box(
            mesh,
            (sign * 4.15, 0.0, 1.55),
            (0.42, total_depth + 0.4, 3.1),
            0.08,
        )
        _add_chamfered_box(
            mesh,
            (sign * 4.15, 3.60, 3.25),
            (0.70, 0.80, 0.55),
            0.10,
        )
    return mesh


def _asset_gatehouse_facade() -> Mesh:
    mesh = Mesh("rv_gatehouse_facade", "gr_rvstone_material")
    for sign in (-1.0, 1.0):
        _add_chamfered_box(mesh, (sign * 8.4, 0.0, 4.9), (7.2, 3.0, 9.8), 0.25)
        _add_chamfered_box(mesh, (sign * 8.4, 0.0, 10.0), (7.8, 3.4, 0.55), 0.16)
        for merlon in (-2.5, -0.8, 0.9, 2.6):
            _add_chamfered_box(
                mesh,
                (sign * 8.4 + merlon, 0.0, 10.65),
                (0.85, 3.0, 1.3),
                0.10,
            )
        _add_chamfered_box(mesh, (sign * 4.35, 0.0, 3.45), (1.15, 2.7, 6.9), 0.14)
        _add_chamfered_box(
            mesh,
            (sign * 8.4, -1.54, 3.25),
            (3.55, 0.12, 4.75),
            0.12,
        )
        _add_arch_relief(
            mesh,
            (sign * 8.4, -1.62, 0.0),
            4.45,
            (2.10, 2.15),
            (1.55, 1.60),
            0.20,
        )
        for bay_sign in (-1.0, 1.0):
            _add_chamfered_box(
                mesh,
                (sign * 8.4 + bay_sign * 1.78, -1.66, 3.15),
                (0.34, 0.24, 5.45),
                0.06,
            )
        _add_chamfered_box(
            mesh,
            (sign * 8.4, -1.68, 0.68),
            (4.25, 0.28, 0.72),
            0.11,
        )
    _add_arch_with_piers(mesh, 0.0, 0.0, 3.15, (3.75, 3.35), (2.45, 2.25), 2.7)
    _add_chamfered_box(mesh, (0.0, 0.0, 8.1), (8.2, 2.85, 2.2), 0.20)
    _add_arch_ring(mesh, 0.0, -1.42, 3.15, (3.35, 2.95), (2.70, 2.40), 0.16)
    _add_arch_ring(mesh, 0.0, -1.55, 3.15, (4.20, 3.85), (3.72, 3.37), 0.18)
    _add_arch_ring(mesh, 0.0, -1.67, 3.15, (4.62, 4.24), (4.28, 3.90), 0.15)
    for x in (-3.45, -2.30, -1.15, 0.0, 1.15, 2.30, 3.45):
        _add_chamfered_box(mesh, (x, -1.63, 7.12), (0.50, 0.54, 0.82), 0.08)
    for x in (-10.2, -8.4, -6.6, 6.6, 8.4, 10.2):
        _add_chamfered_box(mesh, (x, -1.58, 5.2), (0.24, 0.16, 5.9), 0.04)
        _add_chamfered_box(mesh, (x, -1.68, 8.42), (0.72, 0.36, 0.46), 0.08)
    for sign in (-1.0, 1.0):
        _add_tapered_prism(
            mesh,
            (sign * 11.0, 0.15),
            0.0,
            8.8,
            (2.0, 4.8),
            (0.82, 2.0),
            8,
        )
        _add_chamfered_box(
            mesh,
            (sign * 11.0, -1.58, 0.36),
            (2.25, 0.52, 0.72),
            0.10,
        )
        _add_rock(
            mesh,
            (sign * 9.85, -1.75, 0.0),
            (0.95, 0.55, 0.72),
            61 if sign < 0.0 else 67,
            sectors=8,
            rings=3,
        )
    return mesh


def _add_rotunda_segment(
    mesh: Mesh,
    angle_a: float,
    angle_b: float,
    inner_radius: float,
    outer_radius: float,
    height: float,
) -> None:
    def point(radius: float, angle: float, z: float) -> Vec3:
        return (math.cos(angle) * radius, math.sin(angle) * radius, z)

    outer_a_0 = point(outer_radius, angle_a, 0.0)
    outer_b_0 = point(outer_radius, angle_b, 0.0)
    outer_a_1 = point(outer_radius, angle_a, height)
    outer_b_1 = point(outer_radius, angle_b, height)
    inner_a_0 = point(inner_radius, angle_a, 0.0)
    inner_b_0 = point(inner_radius, angle_b, 0.0)
    inner_a_1 = point(inner_radius, angle_a, height)
    inner_b_1 = point(inner_radius, angle_b, height)
    mesh.quad(outer_a_0, outer_b_0, outer_b_1, outer_a_1)
    mesh.quad(inner_b_0, inner_a_0, inner_a_1, inner_b_1)
    mesh.quad(outer_a_1, outer_b_1, inner_b_1, inner_a_1)
    mesh.quad(inner_a_0, inner_b_0, outer_b_0, outer_a_0)
    mesh.quad(inner_a_0, outer_a_0, outer_a_1, inner_a_1)
    mesh.quad(outer_b_0, inner_b_0, inner_b_1, outer_b_1)


def _asset_rotunda_shell() -> Mesh:
    mesh = Mesh("rv_rotunda_shell", "gr_rvstone_material")
    segments = 32
    gap_center = -math.pi / 2.0
    gap_half_angle = math.radians(22.5)
    retained_segments: list[tuple[float, float, float]] = []
    for index in range(segments):
        angle_a = math.tau * index / segments
        angle_b = math.tau * (index + 1) / segments
        midpoint = (angle_a + angle_b) / 2.0
        delta = math.atan2(
            math.sin(midpoint - gap_center),
            math.cos(midpoint - gap_center),
        )
        if abs(delta) < gap_half_angle:
            continue
        _add_rotunda_segment(mesh, angle_a, angle_b, 10.6, 12.0, 8.0)
        retained_segments.append((angle_a, angle_b, midpoint))
        for band_height, band_z in ((0.50, 0.20), (0.34, 3.85), (0.52, 7.72)):
            band = Mesh("rv_rotunda_band", mesh.material_name)
            _add_rotunda_segment(
                band,
                angle_a,
                angle_b,
                10.40,
                12.22,
                band_height,
            )
            _append_mesh_transformed(mesh, band, offset=(0.0, 0.0, band_z))
    retained_midpoints = [row[2] for row in retained_segments]
    for index, angle in enumerate(retained_midpoints):
        if index % 4:
            continue
        center = (math.cos(angle) * 11.25, math.sin(angle) * 11.25)
        _add_tapered_prism(mesh, center, 0.0, 8.8, (1.25, 1.25), (0.9, 0.9), 8)
        base_center = (math.cos(angle) * 12.05, math.sin(angle) * 12.05, 0.55)
        _add_rotated_chamfered_box(
            mesh,
            base_center,
            (2.05, 1.25, 1.10),
            0.14,
            angle + math.pi / 2.0,
        )
        _add_arch_relief(
            mesh,
            (math.cos(angle) * 12.12, math.sin(angle) * 12.12, 0.0),
            4.55,
            (1.42, 2.02),
            (0.98, 1.53),
            0.24,
            angle + math.pi / 2.0,
            10,
        )
    for angle in (-math.pi / 2.0 - gap_half_angle, -math.pi / 2.0 + gap_half_angle):
        center = (math.cos(angle) * 11.3, math.sin(angle) * 11.3)
        _add_tapered_prism(mesh, center, 0.0, 9.4, (1.7, 1.7), (1.1, 1.1), 8)
    for index, angle in enumerate(retained_midpoints):
        if index % 2:
            continue
        crown_height = 0.72 + 0.22 * ((index // 2) % 3)
        _add_rotated_chamfered_box(
            mesh,
            (
                math.cos(angle) * 12.18,
                math.sin(angle) * 12.18,
                8.0 + crown_height / 2.0,
            ),
            (0.82, 0.72, crown_height),
            0.10,
            angle + math.pi / 2.0,
        )
    return mesh


def _asset_lookout_tower() -> Mesh:
    mesh = Mesh("rv_lookout_tower", "gr_rvstone_material")
    _add_chamfered_box(mesh, (0.0, 0.0, 0.4), (8.0, 8.0, 0.8), 0.35)
    _add_chamfered_box(mesh, (0.0, 0.0, 1.05), (7.2, 7.2, 0.55), 0.30)
    _add_tapered_prism(mesh, (0.0, 0.0), 0.8, 11.8, (6.4, 6.4), (5.2, 5.2), 8)
    _add_chamfered_box(mesh, (0.0, 0.0, 12.15), (9.2, 9.2, 0.7), 0.35)
    _add_chamfered_box(mesh, (0.0, 0.0, 13.0), (8.4, 8.4, 0.45), 0.25)
    for angle_index in range(8):
        angle = math.tau * angle_index / 8.0 + math.pi / 8.0
        merlon_height = 2.70 if angle_index % 2 == 0 else 1.82
        _add_chamfered_box(
            mesh,
            (
                math.cos(angle) * 3.75,
                math.sin(angle) * 3.75,
                13.08 + merlon_height / 2.0,
            ),
            (1.15, 1.15, merlon_height),
            0.14,
        )
        _add_rotated_chamfered_box(
            mesh,
            (
                math.cos(angle) * 4.05,
                math.sin(angle) * 4.05,
                11.55,
            ),
            (0.74, 1.32, 0.82),
            0.10,
            angle + math.pi / 2.0,
        )
    for angle_index in range(4):
        angle = math.tau * angle_index / 4.0 + math.pi / 4.0
        center = (math.cos(angle) * 3.15, math.sin(angle) * 3.15)
        _add_tapered_prism(mesh, center, 0.3, 8.4, (1.4, 1.4), (0.55, 0.55), 6)
        _add_chamfered_box(mesh, (center[0], center[1], 0.64), (1.95, 1.95, 0.72), 0.18)
        _add_chamfered_box(mesh, (center[0], center[1], 8.35), (0.95, 0.95, 0.48), 0.12)
    for angle_index in range(4):
        angle = math.tau * angle_index / 4.0
        _add_arch_relief(
            mesh,
            (math.cos(angle) * 3.12, math.sin(angle) * 3.12, 0.0),
            5.55,
            (1.42, 2.15),
            (0.92, 1.58),
            0.22,
            angle + math.pi / 2.0,
            10,
        )
        for side in (-1.0, 1.0):
            tangent = (-math.sin(angle), math.cos(angle))
            _add_rotated_chamfered_box(
                mesh,
                (
                    math.cos(angle) * 3.20 + tangent[0] * side * 1.52,
                    math.sin(angle) * 3.20 + tangent[1] * side * 1.52,
                    5.05,
                ),
                (0.34, 0.30, 7.25),
                0.06,
                angle + math.pi / 2.0,
            )
    return mesh


def _add_interior_wall_details(mesh: Mesh, y_front: float = -0.36) -> None:
    _add_chamfered_box(mesh, (0.0, 0.0, 0.25), (8.0, 0.78, 0.50), 0.08)
    _add_chamfered_box(mesh, (0.0, 0.0, 4.50), (8.0, 0.78, 0.42), 0.08)
    for x in (-3.65, 0.0, 3.65):
        _add_chamfered_box(mesh, (x, y_front, 2.35), (0.32, 0.18, 4.0), 0.04)
    for x in (-1.85, 1.85):
        _add_chamfered_box(mesh, (x, y_front, 2.35), (3.25, 0.12, 2.8), 0.05)
        _add_chamfered_box(mesh, (x, y_front - 0.08, 3.92), (3.30, 0.13, 0.18), 0.04)


def _asset_interior_wall() -> Mesh:
    mesh = Mesh("rv_interior_wall", "gr_rvstone_material")
    _add_chamfered_box(mesh, (0.0, 0.0, 2.35), (8.0, 0.62, 4.7), 0.08)
    _add_interior_wall_details(mesh)
    return mesh


def _asset_interior_corner() -> Mesh:
    mesh = Mesh("rv_interior_corner", "gr_rvstone_material")
    _add_chamfered_box(mesh, (0.0, 0.0, 2.35), (8.0, 0.62, 4.7), 0.08)
    _add_interior_wall_details(mesh)
    for x in (-3.65, 0.0, 3.65):
        _add_chamfered_box(mesh, (-3.69, x + 3.69, 2.35), (0.18, 0.32, 4.0), 0.04)
    _add_chamfered_box(mesh, (-3.69, 3.69, 2.35), (0.62, 8.0, 4.7), 0.08)
    _add_chamfered_box(mesh, (-3.35, 3.69, 0.25), (0.16, 8.0, 0.50), 0.04)
    _add_chamfered_box(mesh, (-3.35, 3.69, 4.50), (0.16, 8.0, 0.42), 0.04)
    return mesh


def _asset_interior_alcove() -> Mesh:
    mesh = Mesh("rv_interior_alcove", "gr_rvstone_material")
    _add_arch_with_piers(mesh, 0.0, 0.0, 2.45, (2.75, 2.35), (1.75, 1.55), 0.85)
    for sign in (-1.0, 1.0):
        _add_chamfered_box(mesh, (sign * 3.35, 0.0, 2.45), (1.30, 0.85, 4.90), 0.10)
    _add_chamfered_box(mesh, (0.0, 0.48, 2.40), (3.55, 0.12, 4.65), 0.04)
    _add_chamfered_box(mesh, (0.0, -0.10, 0.28), (4.30, 1.25, 0.56), 0.10)
    _add_chamfered_box(mesh, (0.0, -0.52, 2.42), (0.65, 0.18, 3.15), 0.05)
    return mesh


def _asset_interior_floor() -> Mesh:
    mesh = Mesh("rv_interior_floor", "gr_rvfloor_material")
    _add_chamfered_box(mesh, (0.0, 0.0, 0.12), (8.0, 8.0, 0.24), 0.08)
    border = 0.36
    _add_chamfered_box(mesh, (0.0, -3.72, 0.285), (8.0, border, 0.09), 0.05)
    _add_chamfered_box(mesh, (0.0, 3.72, 0.285), (8.0, border, 0.09), 0.05)
    _add_chamfered_box(mesh, (-3.72, 0.0, 0.285), (border, 8.0, 0.09), 0.05)
    _add_chamfered_box(mesh, (3.72, 0.0, 0.285), (border, 8.0, 0.09), 0.05)
    for x in (-1.9, 1.9):
        for y in (-1.9, 1.9):
            _add_chamfered_box(mesh, (x, y, 0.275), (3.45, 3.45, 0.07), 0.12)
    return mesh


def _asset_interior_ceiling() -> Mesh:
    mesh = Mesh("rv_interior_ceiling", "gr_rvstone_material")
    _add_chamfered_box(mesh, (0.0, 0.0, 0.20), (8.0, 8.0, 0.40), 0.10)
    for x in (-3.55, 0.0, 3.55):
        _add_chamfered_box(mesh, (x, 0.0, -0.12), (0.40, 8.0, 0.28), 0.06)
    for y in (-3.55, 0.0, 3.55):
        _add_chamfered_box(mesh, (0.0, y, -0.12), (8.0, 0.40, 0.28), 0.06)
    for x in (-1.78, 1.78):
        for y in (-1.78, 1.78):
            _add_chamfered_box(mesh, (x, y, -0.08), (3.0, 3.0, 0.16), 0.10)
    return mesh


def _asset_interior_tunnel_dressing() -> Mesh:
    mesh = Mesh("rv_interior_tunnel_dressing", "gr_rvstone_material")
    for y in (-3.85, 0.0, 3.85):
        _add_arch_with_piers(
            mesh,
            0.0,
            y,
            3.15,
            (3.75, 2.25),
            (3.25, 1.75),
            0.28,
        )
    for sign in (-1.0, 1.0):
        _add_chamfered_box(mesh, (sign * 3.55, 0.0, 0.22), (0.48, 8.0, 0.44), 0.08)
        _add_chamfered_box(mesh, (sign * 3.62, 0.0, 2.10), (0.22, 8.0, 2.25), 0.05)
    _add_chamfered_box(mesh, (0.0, 0.0, 5.18), (1.05, 8.0, 0.20), 0.05)
    for y in (-2.0, 0.0, 2.0):
        _add_chamfered_box(mesh, (0.0, y, 5.02), (0.74, 0.95, 0.16), 0.04)
    return mesh


@dataclass(frozen=True)
class AssetSpec:
    asset_id: str
    label: str
    category: str
    texture_resref: str
    tags: tuple[str, ...]
    role: str
    collision_intent: str
    sockets: tuple[dict[str, object], ...]
    builder: Callable[[], Mesh]


def _socket(name: str, position: Vec3, forward: Vec3, kind: str = "module_edge") -> dict[str, object]:
    return {
        "name": name,
        "position_m": list(position),
        "forward": list(forward),
        "kind": kind,
    }


ASSET_SPECS = (
    AssetSpec(
        "rv_snow_drift",
        "Snow Drift",
        "Snow Terrain",
        "gr_rvsnow",
        ("rhen-var", "snow", "drift", "terrain", "scatter"),
        "Soft snowbank used to dress landing-pad edges and blend terrain seams.",
        "nonblocking_visual; optional simplified convex hull",
        (),
        _asset_snow_drift,
    ),
    AssetSpec(
        "rv_ice_ridge",
        "Ice Ridge / Cliff",
        "Cliffs & Rocks",
        "gr_rvsnow",
        ("rhen-var", "ice", "cliff", "ridge", "terrain"),
        "Sixteen-metre frozen ridge for perimeter cliffs and elevation framing.",
        "nonwalkable compound hull; preserve authored traversal side",
        (
            _socket("west", (-8.0, 0.0, 0.0), (-1.0, 0.0, 0.0), "terrain_edge"),
            _socket("east", (8.0, 0.0, 0.0), (1.0, 0.0, 0.0), "terrain_edge"),
        ),
        _asset_ice_ridge,
    ),
    AssetSpec(
        "rv_canyon_wall_16m",
        "Rocky Canyon Wall — 16 m",
        "Cliffs & Rocks",
        "gr_rvstone",
        (
            "rhen-var",
            "rock",
            "canyon",
            "wall",
            "concave",
            "faceted",
            "terrain",
            "sixteen-metre",
        ),
        (
            "Sixteen-metre asymmetrical canyon boundary with a recessed traversal "
            "face, coarse rock facets, and grounded outcrops."
        ),
        "nonwalkable watertight canyon hull; preserve concave traversal face",
        (
            _socket("west", (-8.0, 0.55, 0.0), (-1.0, 0.0, 0.0), "terrain_edge"),
            _socket("east", (8.0, 0.55, 0.0), (1.0, 0.0, 0.0), "terrain_edge"),
        ),
        _asset_canyon_wall_16m,
    ),
    AssetSpec(
        "rv_canyon_corner",
        "Rocky Canyon Turn",
        "Cliffs & Rocks",
        "gr_rvstone",
        (
            "rhen-var",
            "rock",
            "canyon",
            "corner",
            "turn",
            "faceted",
            "terrain",
        ),
        (
            "Solid ninety-degree canyon turn matching the straight wall's coarse "
            "facets, height, thickness, and rock outcrop language."
        ),
        "nonwalkable watertight canyon hull; inner curve faces traversal space",
        (
            _socket("south", (0.0, -7.30, 0.0), (0.0, -1.0, 0.0), "terrain_edge"),
            _socket("east", (7.30, 0.0, 0.0), (1.0, 0.0, 0.0), "terrain_edge"),
        ),
        _asset_canyon_corner,
    ),
    AssetSpec(
        "rv_rock_cluster",
        "Frozen Rock Cluster",
        "Cliffs & Rocks",
        "gr_rvstone",
        ("rhen-var", "rocks", "boulders", "terrain", "scatter"),
        "Purposeful cover, path-edge marker, or terrain transition cluster.",
        "nonwalkable per-rock convex hulls",
        (),
        _asset_rock_cluster,
    ),
    AssetSpec(
        "rv_ruin_wall",
        "Broken Temple Wall",
        "Ruins",
        "gr_rvstone",
        ("rhen-var", "ruin", "wall", "modular", "broken"),
        "Eight-metre broken wall with a readable modular baseline and damaged crown.",
        "simple wall boxes; nonwalkable",
        (
            _socket("west", (-4.0, 0.0, 0.0), (-1.0, 0.0, 0.0)),
            _socket("east", (4.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ),
        _asset_ruin_wall,
    ),
    AssetSpec(
        "rv_ruin_corner",
        "Broken Temple Corner",
        "Ruins",
        "gr_rvstone",
        ("rhen-var", "ruin", "corner", "modular", "broken"),
        "Ninety-degree corner that closes ruin silhouettes without open seams.",
        "two perpendicular wall boxes; nonwalkable",
        (
            _socket("south", (0.0, -0.43, 0.0), (0.0, -1.0, 0.0)),
            _socket("east", (-3.58, 7.58, 0.0), (0.0, 1.0, 0.0)),
        ),
        _asset_ruin_corner,
    ),
    AssetSpec(
        "rv_temple_arch",
        "Cathedral Temple Arch",
        "Ruins",
        "gr_rvstone",
        ("rhen-var", "temple", "cathedral", "arch", "entrance", "portal"),
        "Solid three-dimensional temple threshold and landmark entrance.",
        "compound frame collision; opening remains clear",
        (
            _socket("front", (0.0, -1.15, 0.0), (0.0, -1.0, 0.0), "doorway"),
            _socket("back", (0.0, 1.15, 0.0), (0.0, 1.0, 0.0), "doorway"),
        ),
        _asset_temple_arch,
    ),
    AssetSpec(
        "rv_buttress",
        "Temple Buttress",
        "Ruins",
        "gr_rvstone",
        ("rhen-var", "temple", "buttress", "support", "detail"),
        "Structural rhythm piece for exterior walls, gatehouses, and cathedral shells.",
        "single tapered convex hull; nonwalkable",
        (_socket("wall", (0.0, -2.40, 0.0), (0.0, -1.0, 0.0), "wall_detail"),),
        _asset_buttress,
    ),
    AssetSpec(
        "rv_broken_pillar",
        "Broken Temple Pillar",
        "Ruins",
        "gr_rvstone",
        ("rhen-var", "pillar", "ruin", "debris", "detail"),
        "Damaged vertical landmark for ruined halls and courtyard path framing.",
        "single simplified column hull plus nonblocking debris",
        (),
        _asset_broken_pillar,
    ),
    AssetSpec(
        "rv_ruin_stairs",
        "Temple Ruin Stairs",
        "Ruins",
        "gr_rvfloor",
        ("rhen-var", "stairs", "ruin", "traversal", "modular"),
        "Eight-metre traversal stair connecting landing and temple elevations.",
        "walkable simplified stair ramp with side-rail blockers",
        (
            _socket("lower", (0.0, -4.0, 0.0), (0.0, -1.0, 0.0), "walkmesh_edge"),
            _socket("upper", (0.0, 4.0, 3.2), (0.0, 1.0, 0.0), "walkmesh_edge"),
        ),
        _asset_ruin_stairs,
    ),
    AssetSpec(
        "rv_gatehouse_facade",
        "Rhen Var Gatehouse Facade",
        "Exterior Buildings",
        "gr_rvstone",
        ("rhen-var", "gatehouse", "exterior", "building", "facade", "portal"),
        "Twenty-four-metre exterior landmark with a clear central traversal portal.",
        "compound tower/frame boxes; opening remains clear",
        (
            _socket("front", (0.0, -1.70, 0.0), (0.0, -1.0, 0.0), "doorway"),
            _socket("back", (0.0, 1.70, 0.0), (0.0, 1.0, 0.0), "doorway"),
            _socket("west", (-12.0, 0.0, 0.0), (-1.0, 0.0, 0.0)),
            _socket("east", (12.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ),
        _asset_gatehouse_facade,
    ),
    AssetSpec(
        "rv_rotunda_shell",
        "Ruined Rotunda Shell",
        "Exterior Buildings",
        "gr_rvstone",
        ("rhen-var", "rotunda", "exterior", "temple", "building", "shell"),
        "Open-roof circular temple shell with a deliberate entrance gap.",
        "nonwalkable curved wall segments; floor supplied by authored room",
        (_socket("entrance", (0.0, -12.0, 0.0), (0.0, -1.0, 0.0), "doorway"),),
        _asset_rotunda_shell,
    ),
    AssetSpec(
        "rv_lookout_tower",
        "Frozen Lookout Tower",
        "Exterior Buildings",
        "gr_rvstone",
        ("rhen-var", "tower", "lookout", "exterior", "landmark"),
        "Vertical navigation landmark and distant silhouette for the landing zone.",
        "compound tower hull; upper deck disabled until separate WOK is authored",
        (_socket("entrance", (0.0, -4.0, 0.0), (0.0, -1.0, 0.0), "doorway"),),
        _asset_lookout_tower,
    ),
    AssetSpec(
        "rv_interior_wall",
        "Temple Interior Wall",
        "Interior Architecture",
        "gr_rvstone",
        ("rhen-var", "interior", "wall", "modular", "eight-metre"),
        "Eight-metre paneled wall defining the core interior architectural style.",
        "simple wall box; nonwalkable",
        (
            _socket("west", (-4.0, 0.0, 0.0), (-1.0, 0.0, 0.0)),
            _socket("east", (4.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ),
        _asset_interior_wall,
    ),
    AssetSpec(
        "rv_interior_corner",
        "Temple Interior Corner",
        "Interior Architecture",
        "gr_rvstone",
        ("rhen-var", "interior", "corner", "modular", "eight-metre"),
        "Finished ninety-degree interior corner for seamless room assembly.",
        "two perpendicular wall boxes; nonwalkable",
        (
            _socket("south", (0.0, -0.40, 0.0), (0.0, -1.0, 0.0)),
            _socket("east", (-3.69, 7.69, 0.0), (0.0, 1.0, 0.0)),
        ),
        _asset_interior_corner,
    ),
    AssetSpec(
        "rv_interior_alcove",
        "Temple Interior Alcove",
        "Interior Architecture",
        "gr_rvstone",
        ("rhen-var", "interior", "alcove", "wall-detail", "arch"),
        "Recessed display or statue bay for intentional interior dressing.",
        "compound frame/back collision; floor ledge nonwalkable",
        (
            _socket("west", (-4.0, 0.0, 0.0), (-1.0, 0.0, 0.0)),
            _socket("east", (4.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        ),
        _asset_interior_alcove,
    ),
    AssetSpec(
        "rv_interior_floor",
        "Temple Interior Floor",
        "Interior Architecture",
        "gr_rvfloor",
        ("rhen-var", "interior", "floor", "modular", "walkable", "eight-metre"),
        "Eight-metre bordered floor tile and primary interior WOK surface.",
        "walkable top plane; generate two-triangle floor WOK",
        (
            _socket("north", (0.0, 4.0, 0.30), (0.0, 1.0, 0.0), "walkmesh_edge"),
            _socket("south", (0.0, -4.0, 0.30), (0.0, -1.0, 0.0), "walkmesh_edge"),
            _socket("west", (-4.0, 0.0, 0.30), (-1.0, 0.0, 0.0), "walkmesh_edge"),
            _socket("east", (4.0, 0.0, 0.30), (1.0, 0.0, 0.0), "walkmesh_edge"),
        ),
        _asset_interior_floor,
    ),
    AssetSpec(
        "rv_interior_ceiling",
        "Temple Interior Ceiling",
        "Interior Architecture",
        "gr_rvstone",
        ("rhen-var", "interior", "ceiling", "coffered", "eight-metre"),
        "Eight-metre coffered ceiling insert placed at the authored room ceiling.",
        "visual-only overhead shell; no walkmesh",
        (),
        _asset_interior_ceiling,
    ),
    AssetSpec(
        "rv_interior_tunnel_dressing",
        "Temple Tunnel Dressing",
        "Interior Architecture",
        "gr_rvstone",
        ("rhen-var", "interior", "tunnel", "ribs", "corridor", "eight-metre"),
        "Open arch-rib dressing for an authored eight-metre corridor and its WOK floor.",
        "compound rib/rail collision; center traversal remains clear",
        (
            _socket("south", (0.0, -4.0, 0.0), (0.0, -1.0, 0.0), "doorway"),
            _socket("north", (0.0, 4.0, 0.0), (0.0, 1.0, 0.0), "doorway"),
        ),
        _asset_interior_tunnel_dressing,
    ),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _make_seamless_texture(source: Path, target: Path) -> dict[str, object]:
    """Mirror-center a generated source into an exactly tileable 1024px TGA."""

    with Image.open(source) as image:
        square = image.convert("RGB")
        edge = min(square.size)
        left = (square.width - edge) // 2
        top = (square.height - edge) // 2
        square = square.crop((left, top, left + edge, top + edge))
        square = square.resize((1024, 1024), Image.Resampling.LANCZOS)
        mirrored_x = square.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        mirrored_y = square.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        mirrored_xy = mirrored_x.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        mosaic = Image.new("RGB", (2048, 2048))
        mosaic.paste(square, (0, 0))
        mosaic.paste(mirrored_x, (1024, 0))
        mosaic.paste(mirrored_y, (0, 1024))
        mosaic.paste(mirrored_xy, (1024, 1024))
        seamless = mosaic.crop((512, 512, 1536, 1536))
        seamless.save(target, format="TGA", rle=True)
        pixels = seamless.load()
        horizontal_delta = max(
            max(
                abs(pixels[0, y][channel] - pixels[1023, y][channel])
                for channel in range(3)
            )
            for y in range(1024)
        )
        vertical_delta = max(
            max(
                abs(pixels[x, 0][channel] - pixels[x, 1023][channel])
                for channel in range(3)
            )
            for x in range(1024)
        )
    return {
        "filename": target.name,
        "width": 1024,
        "height": 1024,
        "edge_delta_max": max(horizontal_delta, vertical_delta),
        "source_kind": "Ghost Studio commissioned generated source image",
        "source_file": source.relative_to(OUTPUT_ROOT).as_posix(),
        "source_provenance": "Ghost Studio commissioned original image",
        "source_sha256": _sha256(source),
        "output_sha256": _sha256(target),
    }


def _write_mtl(target: Path, texture_resref: str) -> None:
    target.write_text(
        "\n".join(
            (
                f"# Ghost Studio original Rhen Var material: {texture_resref}",
                f"newmtl {texture_resref}_material",
                "illum 2",
                "Ka 0.280000 0.300000 0.330000",
                "Kd 1.000000 1.000000 1.000000",
                "Ks 0.080000 0.100000 0.120000",
                "Ns 18.000000",
                "d 1.000000",
                f"map_Kd {texture_resref}.tga",
                "",
            )
        ),
        encoding="utf-8",
    )


def _write_obj(mesh: Mesh, target: Path, mtl_name: str) -> None:
    rows = [
        "# Ghost Studio original procedural Rhen Var asset",
        "# Units: metres; up axis: Z",
        f"mtllib {mtl_name}",
        f"o {mesh.name}",
    ]
    rows.extend(f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in mesh.vertices)
    rows.extend(f"vt {u:.6f} {v:.6f}" for u, v in mesh.uvs)
    rows.extend(f"vn {x:.7f} {y:.7f} {z:.7f}" for x, y, z in mesh.normals)
    rows.extend((f"usemtl {mesh.material_name}", "s off"))
    rows.extend(f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}" for a, b, c in mesh.faces)
    target.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _validate_obj(path: Path, expected_triangles: int) -> dict[str, int]:
    counts = {"v": 0, "vt": 0, "vn": 0, "f": 0}
    for line in path.read_text(encoding="utf-8").splitlines():
        prefix = line.partition(" ")[0]
        if prefix in counts:
            counts[prefix] += 1
        if prefix == "f":
            tokens = line.split()[1:]
            if len(tokens) != 3:
                raise ValueError(f"{path.name} contains a non-triangle face")
            for token in tokens:
                vertex, uv, normal = (int(index) for index in token.split("/"))
                if not (1 <= vertex <= counts["v"]):
                    raise ValueError(f"{path.name} has invalid vertex index {vertex}")
                if not (1 <= uv <= counts["vt"]):
                    raise ValueError(f"{path.name} has invalid UV index {uv}")
                if not (1 <= normal <= counts["vn"]):
                    raise ValueError(f"{path.name} has invalid normal index {normal}")
    if counts["f"] != expected_triangles:
        raise ValueError(
            f"{path.name} wrote {counts['f']} triangles, expected {expected_triangles}"
        )
    if not (counts["v"] == counts["vt"] == counts["vn"] == counts["f"] * 3):
        raise ValueError(f"{path.name} attribute counts are not face-corner complete: {counts}")
    return counts


def _is_power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


def _validate_authorized_import() -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
]:
    """Validate the repository-packaged authorized mod-source curation."""

    if not IMPORTED_PROVENANCE_PATH.is_file():
        return [], [], {}
    provenance = json.loads(IMPORTED_PROVENANCE_PATH.read_text(encoding="utf-8"))
    if provenance.get("schema") != "ghostrigger.rhen-var-authorized-import/v1":
        raise ValueError(
            f"Unsupported authorized import schema: {provenance.get('schema')!r}"
        )
    if provenance.get("permission_confirmation_date") != "2026-07-25":
        raise ValueError("Authorized Rhen Var source permission date is missing")

    texture_rows = list(provenance.get("textures") or ())
    texture_resrefs: set[str] = set()
    expected_import_files = {
        IMPORTED_PROVENANCE_PATH.resolve(),
        (IMPORTED_ROOT / "CREDITS.md").resolve(),
    }
    for row in texture_rows:
        texture_resref = str(row.get("texture_resref") or "").strip().lower()
        texture_file = str(row.get("texture_file") or "").strip()
        if not texture_resref or len(texture_resref) > 16:
            raise ValueError(f"Invalid imported KOTOR texture resref {texture_resref!r}")
        if texture_resref in texture_resrefs:
            raise ValueError(f"Duplicate imported texture resref {texture_resref}")
        texture_resrefs.add(texture_resref)
        texture_path = OUTPUT_ROOT / texture_file
        if not texture_path.is_file():
            raise FileNotFoundError(texture_path)
        expected_import_files.add(texture_path.resolve())
        if _sha256(texture_path) != row.get("packaged_sha256"):
            raise ValueError(f"Imported texture hash drifted: {texture_path}")
        with Image.open(texture_path) as image:
            if not (
                _is_power_of_two(image.width)
                and _is_power_of_two(image.height)
                and max(image.size) <= 512
            ):
                raise ValueError(
                    f"{texture_path.name} is not a <=512 power-of-two texture: "
                    f"{image.size}"
                )
            expected_mode = str(row.get("packaged_mode") or "")
            if expected_mode and image.mode != expected_mode:
                raise ValueError(
                    f"{texture_path.name} mode drifted: {image.mode} != {expected_mode}"
                )

    asset_rows = list(provenance.get("assets") or ())
    asset_ids: set[str] = set()
    collision_modes = {
        "walkable_floor_quad",
        "walkable_stair_ramp",
        "visual_only",
        "host_wok_required",
    }
    for row in asset_rows:
        asset_id = str(row.get("asset_id") or "").strip()
        if not asset_id or asset_id in asset_ids:
            raise ValueError(f"Invalid or duplicate imported asset id {asset_id!r}")
        asset_ids.add(asset_id)
        if not str(row.get("source_author") or "").strip():
            raise ValueError(f"{asset_id} is missing source_author")
        if not str(row.get("source_mod_id") or "").strip():
            raise ValueError(f"{asset_id} is missing source_mod_id")
        if row.get("collision_mode") not in collision_modes:
            raise ValueError(
                f"{asset_id} has unsupported collision_mode "
                f"{row.get('collision_mode')!r}"
            )
        obj_path = OUTPUT_ROOT / str(row["obj_name"])
        mtl_path = OUTPUT_ROOT / str(row["mtl_name"])
        for path in (obj_path, mtl_path):
            if not path.is_file():
                raise FileNotFoundError(path)
            expected_import_files.add(path.resolve())
        if _sha256(obj_path) != row.get("obj_sha256"):
            raise ValueError(f"Imported OBJ hash drifted: {obj_path}")
        if _sha256(mtl_path) != row.get("mtl_sha256"):
            raise ValueError(f"Imported MTL hash drifted: {mtl_path}")
        face_count = sum(
            1
            for line in obj_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("f ")
        )
        if face_count != int(row.get("triangle_count") or 0):
            raise ValueError(
                f"{asset_id} has {face_count} OBJ faces, expected "
                f"{row.get('triangle_count')}"
            )
        material_textures = dict(row.get("material_textures") or {})
        used_materials = {
            line.partition(" ")[2].strip()
            for line in obj_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("usemtl ")
        }
        if set(material_textures) != used_materials:
            raise ValueError(
                f"{asset_id} material mapping differs from OBJ: "
                f"{set(material_textures)} != {used_materials}"
            )
        for material_name, mapping in material_textures.items():
            resref = str(mapping.get("texture_resref") or "").strip().lower()
            if resref not in texture_resrefs:
                raise ValueError(
                    f"{asset_id}/{material_name} references unknown texture {resref}"
                )
            texture_path = OUTPUT_ROOT / str(mapping.get("texture_file") or "")
            if not texture_path.is_file():
                raise FileNotFoundError(texture_path)

    actual_import_files = {
        path.resolve()
        for path in IMPORTED_ROOT.rglob("*")
        if path.is_file()
    }
    if actual_import_files != expected_import_files:
        unexpected = sorted(str(path) for path in actual_import_files - expected_import_files)
        missing = sorted(str(path) for path in expected_import_files - actual_import_files)
        raise RuntimeError(
            f"Authorized import inventory differs; unexpected={unexpected}, missing={missing}"
        )
    return asset_rows, texture_rows, provenance


def _validate_skybox() -> tuple[list[dict[str, object]], dict[str, object]]:
    """Validate the licensed HDR-derived five-face KOTOR skybox."""

    if not SKYBOX_PROVENANCE_PATH.is_file():
        raise FileNotFoundError(
            f"Rhen Var skybox is missing. Run {ROOT / 'scripts' / 'build_rhen_var_skybox.py'}."
        )
    provenance = json.loads(SKYBOX_PROVENANCE_PATH.read_text(encoding="utf-8"))
    if provenance.get("schema") != "ghostrigger.rhen-var-skybox/v1":
        raise ValueError(f"Unsupported Rhen Var skybox schema: {provenance.get('schema')!r}")
    if provenance.get("source_license") != "CC0 1.0":
        raise ValueError("Rhen Var skybox must retain its CC0 license provenance.")
    if provenance.get("source_author") != "Andreas Mischok":
        raise ValueError("Rhen Var skybox author attribution drifted.")
    expected_faces = ("north", "east", "south", "west", "top")
    if tuple(provenance.get("face_order") or ()) != expected_faces:
        raise ValueError("Rhen Var skybox face order is not KOTOR north/east/south/west/top.")
    credits_path = SKYBOX_ROOT / "CREDITS.md"
    if not credits_path.is_file():
        raise FileNotFoundError(credits_path)

    rows = list(provenance.get("textures") or ())
    if tuple(str(row.get("skybox_face") or "") for row in rows) != expected_faces:
        raise ValueError("Rhen Var skybox texture rows are incomplete or out of order.")
    resrefs: set[str] = set()
    expected_files = {SKYBOX_PROVENANCE_PATH.resolve(), credits_path.resolve()}
    for row in rows:
        resref = str(row.get("texture_resref") or "").strip().lower()
        relative = str(row.get("texture_file") or "").strip()
        if not resref or len(resref) > 16 or resref in resrefs:
            raise ValueError(f"Invalid or duplicate Rhen Var skybox texture resref: {resref!r}")
        resrefs.add(resref)
        path = OUTPUT_ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        expected_files.add(path.resolve())
        if _sha256(path) != row.get("packaged_sha256"):
            raise ValueError(f"Rhen Var skybox texture hash drifted: {path}")
        with Image.open(path) as image:
            if image.size != (1024, 1024) or image.mode not in {"RGB", "RGBA"}:
                raise ValueError(
                    f"Rhen Var skybox face must be 1024x1024 RGB/RGBA: "
                    f"{path} is {image.size} {image.mode}"
                )
    actual_files = {path.resolve() for path in SKYBOX_ROOT.iterdir() if path.is_file()}
    if actual_files != expected_files:
        raise ValueError(
            "Rhen Var skybox inventory drifted: "
            f"{sorted(str(path) for path in actual_files ^ expected_files)}"
        )
    return rows, provenance


def main() -> int:
    for source in SOURCE_TEXTURES.values():
        if not source.is_file():
            raise FileNotFoundError(source)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    texture_rows: list[dict[str, object]] = []
    for texture_resref, source in SOURCE_TEXTURES.items():
        texture_rows.append(
            {
                "texture_resref": texture_resref,
                **_make_seamless_texture(
                    source,
                    OUTPUT_ROOT / f"{texture_resref}.tga",
                ),
            }
        )

    asset_rows: list[dict[str, object]] = []
    for spec in ASSET_SPECS:
        mesh = spec.builder()
        if mesh.name != spec.asset_id:
            raise ValueError(f"Builder returned {mesh.name!r} for {spec.asset_id!r}")
        expected_material = f"{spec.texture_resref}_material"
        if mesh.material_name != expected_material:
            raise ValueError(
                f"{spec.asset_id} uses {mesh.material_name!r}, expected {expected_material!r}"
            )
        obj_path = OUTPUT_ROOT / f"{spec.asset_id}.obj"
        mtl_path = OUTPUT_ROOT / f"{spec.asset_id}.mtl"
        _write_mtl(mtl_path, spec.texture_resref)
        _write_obj(mesh, obj_path, mtl_path.name)
        obj_counts = _validate_obj(obj_path, mesh.triangle_count)
        dimensions = mesh.dimensions()
        minimum, maximum = mesh.bounds()
        asset_rows.append(
            {
                "asset_id": spec.asset_id,
                "label": spec.label,
                "category": spec.category,
                "obj_name": obj_path.name,
                "mtl_name": mtl_path.name,
                "texture_file": f"{spec.texture_resref}.tga",
                "texture_resref": spec.texture_resref,
                "source_units": "meters",
                "source_up_axis": "z",
                "triangle_count": mesh.triangle_count,
                "dimensions_m": [round(value, 4) for value in dimensions],
                "bounds_m": {
                    "minimum": [round(value, 4) for value in minimum],
                    "maximum": [round(value, 4) for value in maximum],
                },
                "tags": list(spec.tags),
                "role": spec.role,
                "provenance": "Ghost Studio original",
                "collision_intent": spec.collision_intent,
                "sockets": list(spec.sockets),
                "obj_sha256": _sha256(obj_path),
                "mtl_sha256": _sha256(mtl_path),
                "validation": obj_counts,
            }
        )

    imported_asset_rows, imported_texture_rows, imported_provenance = (
        _validate_authorized_import()
    )
    skybox_texture_rows, skybox_provenance = _validate_skybox()
    original_asset_ids = {str(row["asset_id"]) for row in asset_rows}
    imported_asset_ids = {str(row["asset_id"]) for row in imported_asset_rows}
    overlap = original_asset_ids & imported_asset_ids
    if overlap:
        raise ValueError(f"Original/imported Rhen Var asset ids overlap: {sorted(overlap)}")
    original_texture_resrefs = {str(row["texture_resref"]) for row in texture_rows}
    imported_texture_resrefs = {
        str(row["texture_resref"]) for row in imported_texture_rows
    }
    skybox_texture_resrefs = {
        str(row["texture_resref"]) for row in skybox_texture_rows
    }
    overlap = (
        (original_texture_resrefs & imported_texture_resrefs)
        | (original_texture_resrefs & skybox_texture_resrefs)
        | (imported_texture_resrefs & skybox_texture_resrefs)
    )
    if overlap:
        raise ValueError(
            f"Original/imported Rhen Var texture resrefs overlap: {sorted(overlap)}"
        )

    manifest = {
        "schema": "ghostrigger.rhen-var-asset-pack/v1",
        "pack_id": "ghost_studio_rhen_var_comprehensive",
        "label": "Rhen Var — Frozen Temple & Landing Zone",
        "module_standard_m": 8.0,
        "source_units": "meters",
        "source_up_axis": "z",
        "provenance": (
            "Ghost Studio original procedural geometry and commissioned texture "
            "sources, plus a curated subset of user-supplied Rhen Var mod assets "
            "packaged under mod-author permission confirmed by the user on "
            "2026-07-25. The permission record does not assert a general public "
            "license; underlying rights remain with their creators and rights holders."
        ),
        "source_assets": [
            {
                "texture_resref": row["texture_resref"],
                "file": row["source_file"],
                "sha256": row["source_sha256"],
                "provenance": row["source_provenance"],
            }
            for row in texture_rows
        ],
        "authorized_import": {
            "permission_confirmation_date": imported_provenance.get(
                "permission_confirmation_date"
            ),
            "permission_statement": imported_provenance.get("permission_statement"),
            "source_archives": imported_provenance.get("source_archives", []),
            "conversion_tools": imported_provenance.get("conversion_tools", []),
            "credits_file": "mod_sources/imported/CREDITS.md",
            "provenance_file": "mod_sources/imported/provenance.json",
            "curation": imported_provenance.get("curation", {}),
        },
        "skybox": {
            key: value
            for key, value in skybox_provenance.items()
            if key != "textures"
        },
        "textures": [*texture_rows, *imported_texture_rows, *skybox_texture_rows],
        "imported_textures": imported_texture_rows,
        "skybox_textures": skybox_texture_rows,
        "assets": [*asset_rows, *imported_asset_rows],
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    generated_files = sorted(path.name for path in OUTPUT_ROOT.iterdir() if path.is_file())
    expected_file_count = len(ASSET_SPECS) * 2 + len(SOURCE_TEXTURES) + 1
    if len(generated_files) != expected_file_count:
        raise RuntimeError(
            f"Generated {len(generated_files)} files, expected {expected_file_count}: "
            f"{generated_files}"
        )
    if any(row["edge_delta_max"] != 0 for row in texture_rows):
        raise RuntimeError(f"Texture seam validation failed: {texture_rows}")
    source_files = sorted(path.name for path in SOURCE_ROOT.iterdir() if path.is_file())
    expected_source_files = sorted(path.name for path in SOURCE_TEXTURES.values())
    if source_files != expected_source_files:
        raise RuntimeError(
            f"Source texture inventory differs: {source_files} != {expected_source_files}"
        )

    all_packaged_files = sorted(
        path
        for path in OUTPUT_ROOT.rglob("*")
        if path.is_file()
    )
    largest_file = max(all_packaged_files, key=lambda path: path.stat().st_size)
    summary = {
        "output": str(OUTPUT_ROOT),
        "schema": manifest["schema"],
        "asset_count": len(manifest["assets"]),
        "original_asset_count": len(asset_rows),
        "imported_asset_count": len(imported_asset_rows),
        "texture_count": len(manifest["textures"]),
        "original_texture_count": len(texture_rows),
        "imported_texture_count": len(imported_texture_rows),
        "skybox_texture_count": len(skybox_texture_rows),
        "file_count": len(generated_files),
        "source_file_count": len(source_files),
        "package_file_count": len(all_packaged_files),
        "package_bytes": sum(path.stat().st_size for path in all_packaged_files),
        "largest_file": {
            "path": largest_file.relative_to(OUTPUT_ROOT).as_posix(),
            "bytes": largest_file.stat().st_size,
        },
        "triangle_count": sum(
            int(row["triangle_count"]) for row in manifest["assets"]
        ),
        "categories": sorted(
            {str(row["category"]) for row in manifest["assets"]}
        ),
        "files": generated_files,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
