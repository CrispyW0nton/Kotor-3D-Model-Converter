"""Headless terrain heightfield builder for Map Studio.

Terrain authoring must produce both visible room geometry and matching WOK
faces.  This module owns the first durable Map Studio terrain primitive so the
UI can later expose sculpt/heightfield controls without owning geometry policy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .authored_room_geometry import AuthoredRoomGeometry, Face, PrimitiveMesh, Vec2, Vec3
from .authored_room_primitives import PrimitiveMaterial
from .authored_walkmesh_surfaces import resolve_walkmesh_surface_id, walkmesh_surface_name
from .module_format import WOKData, WOKFace


@dataclass(frozen=True)
class TerrainHeightfieldPrimitive:
    """Editable terrain patch represented by a rectangular height grid."""

    room_resref: str
    heights: tuple[tuple[float, ...], ...] = ((0.0, 0.0), (0.0, 0.0))
    width: float = 10.0
    depth: float = 10.0
    floor_surface_id: int | str = 4
    non_walk_surface_id: int | str = 7
    max_walkable_slope_degrees: float = 35.0
    material: PrimitiveMaterial = field(default_factory=PrimitiveMaterial)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TerrainHeightfieldValidation:
    """Validation summary for a terrain heightfield primitive."""

    ok: bool
    row_count: int = 0
    column_count: int = 0
    warnings: tuple[str, ...] = ()
    blocking_issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class TerrainSlopeReport:
    """Derived slope/walkability facts for generated terrain."""

    triangle_count: int
    walkable_triangle_count: int
    non_walk_triangle_count: int
    max_slope_degrees: float
    warnings: tuple[str, ...] = ()


def _height_rows(primitive: TerrainHeightfieldPrimitive) -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(float(value) for value in row) for row in primitive.heights)


def validate_terrain_heightfield_primitive(primitive: TerrainHeightfieldPrimitive) -> TerrainHeightfieldValidation:
    """Validate terrain dimensions before mesh/WOK generation."""

    blocking: list[str] = []
    warnings: list[str] = []
    rows = _height_rows(primitive)
    row_count = len(rows)
    column_count = len(rows[0]) if rows else 0
    if row_count < 2 or column_count < 2:
        blocking.append("Terrain heightfield requires at least a 2x2 height grid.")
    for index, row in enumerate(rows):
        if len(row) != column_count:
            blocking.append(f"Terrain heightfield row {index} has {len(row)} columns; expected {column_count}.")
    if float(primitive.width) <= 0.0 or float(primitive.depth) <= 0.0:
        blocking.append("Terrain heightfield width and depth must be positive.")
    max_slope = float(primitive.max_walkable_slope_degrees)
    if max_slope <= 0.0 or max_slope >= 90.0:
        blocking.append("Terrain max walkable slope must be greater than 0 and less than 90 degrees.")
    if not str(primitive.room_resref or "").strip():
        blocking.append("Terrain heightfield requires a room resref.")
    if not blocking:
        report = analyse_terrain_slopes(primitive)
        warnings.extend(report.warnings)
    return TerrainHeightfieldValidation(
        ok=not blocking,
        row_count=row_count,
        column_count=column_count,
        warnings=tuple(warnings),
        blocking_issues=tuple(blocking),
    )


def _grid_vertices(primitive: TerrainHeightfieldPrimitive) -> tuple[Vec3, ...]:
    rows = _height_rows(primitive)
    row_count = len(rows)
    column_count = len(rows[0])
    width = float(primitive.width)
    depth = float(primitive.depth)
    vertices: list[Vec3] = []
    for row_index, row in enumerate(rows):
        y = -depth * 0.5 + (depth * row_index / (row_count - 1))
        for column_index, height in enumerate(row):
            x = -width * 0.5 + (width * column_index / (column_count - 1))
            vertices.append((x, y, height))
    return tuple(vertices)


def _grid_uvs(row_count: int, column_count: int) -> tuple[Vec2, ...]:
    uvs: list[Vec2] = []
    for row_index in range(row_count):
        v = row_index / max(1, row_count - 1)
        for column_index in range(column_count):
            u = column_index / max(1, column_count - 1)
            uvs.append((u, v))
    return tuple(uvs)


def _triangle_slope_degrees(a: Vec3, b: Vec3, c: Vec3) -> float:
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    normal = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    length = math.sqrt(normal[0] * normal[0] + normal[1] * normal[1] + normal[2] * normal[2])
    if length <= 1e-9:
        return 90.0
    cos_from_up = max(-1.0, min(1.0, abs(normal[2]) / length))
    return math.degrees(math.acos(cos_from_up))


def _terrain_faces(row_count: int, column_count: int) -> tuple[Face, ...]:
    faces: list[Face] = []
    for row_index in range(row_count - 1):
        for column_index in range(column_count - 1):
            v00 = row_index * column_count + column_index
            v10 = v00 + 1
            v01 = (row_index + 1) * column_count + column_index
            v11 = v01 + 1
            faces.append((v00, v10, v11))
            faces.append((v00, v11, v01))
    return tuple(faces)


def _set_face_adjacent(face: WOKFace, edge_index: int, adjacent: int) -> None:
    if edge_index == 0:
        face.adj1 = adjacent
    elif edge_index == 1:
        face.adj2 = adjacent
    else:
        face.adj3 = adjacent


def _assign_wok_adjacency(faces: list[WOKFace]) -> None:
    edge_owner: dict[tuple[int, int], tuple[int, int]] = {}
    for face_index, face in enumerate(faces):
        vertices = (face.v1, face.v2, face.v3)
        for edge_index in range(3):
            a = vertices[edge_index]
            b = vertices[(edge_index + 1) % 3]
            key = (min(a, b), max(a, b))
            other = edge_owner.get(key)
            if other is None:
                edge_owner[key] = (face_index, edge_index)
                continue
            other_face_index, other_edge_index = other
            _set_face_adjacent(face, edge_index, other_face_index)
            _set_face_adjacent(faces[other_face_index], other_edge_index, face_index)


def analyse_terrain_slopes(primitive: TerrainHeightfieldPrimitive) -> TerrainSlopeReport:
    """Report generated terrain slope classification without building bytes."""

    validation_rows = _height_rows(primitive)
    if len(validation_rows) < 2 or not validation_rows or len(validation_rows[0]) < 2:
        return TerrainSlopeReport(0, 0, 0, 0.0, ("Terrain heightfield is too small to analyse.",))
    vertices = _grid_vertices(primitive)
    faces = _terrain_faces(len(validation_rows), len(validation_rows[0]))
    max_walkable_slope = float(primitive.max_walkable_slope_degrees)
    max_slope = 0.0
    non_walk = 0
    for face in faces:
        slope = _triangle_slope_degrees(vertices[face[0]], vertices[face[1]], vertices[face[2]])
        max_slope = max(max_slope, slope)
        if slope > max_walkable_slope:
            non_walk += 1
    warnings: list[str] = []
    if non_walk:
        warnings.append(
            f"Terrain has {non_walk} triangle(s) steeper than {max_walkable_slope:.1f} degrees; they will export as non-walk."
        )
    return TerrainSlopeReport(
        triangle_count=len(faces),
        walkable_triangle_count=len(faces) - non_walk,
        non_walk_triangle_count=non_walk,
        max_slope_degrees=max_slope,
        warnings=tuple(warnings),
    )


def build_terrain_mesh(primitive: TerrainHeightfieldPrimitive) -> PrimitiveMesh:
    """Build the visible terrain mesh for a Map Studio room."""

    validation = validate_terrain_heightfield_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    rows = _height_rows(primitive)
    vertices = _grid_vertices(primitive)
    faces = _terrain_faces(validation.row_count, validation.column_count)
    report = analyse_terrain_slopes(primitive)
    heights = [vertex[2] for vertex in vertices]
    return PrimitiveMesh(
        name=f"{primitive.room_resref}_terrain",
        vertices=vertices,
        faces=faces,
        normals=((0.0, 0.0, 1.0),) * len(vertices),
        uvs=_grid_uvs(validation.row_count, validation.column_count),
        texture=primitive.material.texture,
        diffuse=primitive.material.diffuse,
        ambient=primitive.material.ambient,
        metadata={
            "primitive": "terrain_heightfield",
            "source": "src.core.modules.authored_terrain_builder",
            "row_count": validation.row_count,
            "column_count": validation.column_count,
            "height_min": min(heights),
            "height_max": max(heights),
            "max_slope_degrees": report.max_slope_degrees,
            "walkable_triangle_count": report.walkable_triangle_count,
            "non_walk_triangle_count": report.non_walk_triangle_count,
            "height_samples": rows,
            **dict(primitive.metadata),
        },
    )


def build_terrain_wok(primitive: TerrainHeightfieldPrimitive) -> WOKData:
    """Build the WOK faces that match the authored terrain heightfield."""

    validation = validate_terrain_heightfield_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    vertices = _grid_vertices(primitive)
    mesh_faces = _terrain_faces(validation.row_count, validation.column_count)
    walk_surface = resolve_walkmesh_surface_id(primitive.floor_surface_id)
    non_walk_surface = resolve_walkmesh_surface_id(primitive.non_walk_surface_id)
    max_walkable_slope = float(primitive.max_walkable_slope_degrees)
    wok_faces: list[WOKFace] = []
    for face in mesh_faces:
        slope = _triangle_slope_degrees(vertices[face[0]], vertices[face[1]], vertices[face[2]])
        surface = walk_surface if slope <= max_walkable_slope else non_walk_surface
        wok_faces.append(WOKFace(face[0], face[1], face[2], surface=surface, adj1=-1, adj2=-1, adj3=-1))
    _assign_wok_adjacency(wok_faces)
    return WOKData(name=f"{primitive.room_resref}.wok", verts=list(vertices), faces=wok_faces)


def compile_terrain_room_geometry(primitive: TerrainHeightfieldPrimitive) -> AuthoredRoomGeometry:
    """Compile terrain into room geometry and matching WOK data."""

    validation = validate_terrain_heightfield_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    report = analyse_terrain_slopes(primitive)
    return AuthoredRoomGeometry(
        room_resref=primitive.room_resref,
        room_mesh=build_terrain_mesh(primitive),
        helper_meshes=(),
        wok=build_terrain_wok(primitive),
        metadata={
            "primitive": "terrain_heightfield",
            "source": "src.core.modules.authored_terrain_builder",
            "row_count": validation.row_count,
            "column_count": validation.column_count,
            "floor_surface_id": resolve_walkmesh_surface_id(primitive.floor_surface_id),
            "floor_surface_name": walkmesh_surface_name(resolve_walkmesh_surface_id(primitive.floor_surface_id)),
            "non_walk_surface_id": resolve_walkmesh_surface_id(primitive.non_walk_surface_id),
            "non_walk_surface_name": walkmesh_surface_name(resolve_walkmesh_surface_id(primitive.non_walk_surface_id)),
            "max_walkable_slope_degrees": float(primitive.max_walkable_slope_degrees),
            "max_slope_degrees": report.max_slope_degrees,
            "walkable_triangle_count": report.walkable_triangle_count,
            "non_walk_triangle_count": report.non_walk_triangle_count,
            "warnings": report.warnings,
        },
    )


__all__ = [
    "TerrainHeightfieldPrimitive",
    "TerrainHeightfieldValidation",
    "TerrainSlopeReport",
    "analyse_terrain_slopes",
    "build_terrain_mesh",
    "build_terrain_wok",
    "compile_terrain_room_geometry",
    "validate_terrain_heightfield_primitive",
]
