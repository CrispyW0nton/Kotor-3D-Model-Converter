"""Headless terrain heightfield builder for Map Studio.

Terrain authoring must produce both visible room geometry and matching WOK
faces.  This module owns the first durable Map Studio terrain primitive so the
UI can later expose sculpt/heightfield controls without owning geometry policy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
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


@dataclass(frozen=True)
class TerrainShapePreset:
    """Named terrain form a modder can apply without editing samples one by one."""

    preset_id: str
    label: str
    description: str
    default_height: float = 0.5


_TERRAIN_SHAPE_PRESETS: tuple[TerrainShapePreset, ...] = (
    TerrainShapePreset(
        preset_id="flat",
        label="Flat Pad",
        description="Level the terrain into a simple playable pad.",
        default_height=0.0,
    ),
    TerrainShapePreset(
        preset_id="gentle_mound",
        label="Gentle Mound",
        description="Raise a soft center hill while keeping the edges lower.",
        default_height=0.6,
    ),
    TerrainShapePreset(
        preset_id="shallow_bowl",
        label="Shallow Bowl",
        description="Create a shallow center depression with higher edges.",
        default_height=0.45,
    ),
    TerrainShapePreset(
        preset_id="ridge",
        label="Center Ridge",
        description="Raise a broad ridge through the middle of the terrain.",
        default_height=0.5,
    ),
    TerrainShapePreset(
        preset_id="ramp",
        label="Walkable Ramp",
        description="Slope the patch from one side to the other.",
        default_height=0.75,
    ),
    TerrainShapePreset(
        preset_id="terraces",
        label="Terraces",
        description="Create stepped height bands for tiered terrain blocking.",
        default_height=0.75,
    ),
)


def _height_rows(primitive: TerrainHeightfieldPrimitive) -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(float(value) for value in row) for row in primitive.heights)


def _replace_height_rows(
    primitive: TerrainHeightfieldPrimitive,
    rows: tuple[tuple[float, ...], ...],
    *,
    operation: str,
    metadata: dict[str, Any] | None = None,
) -> TerrainHeightfieldPrimitive:
    return replace(
        primitive,
        heights=rows,
        metadata={
            **dict(primitive.metadata),
            "last_operation": operation,
            **dict(metadata or {}),
        },
    )


def _sample_indices(primitive: TerrainHeightfieldPrimitive, row_index: int, column_index: int) -> tuple[int, int]:
    rows = _height_rows(primitive)
    row_count = len(rows)
    column_count = len(rows[0]) if rows else 0
    row = int(row_index)
    column = int(column_index)
    if row < 0 or row >= row_count:
        raise ValueError(f"Terrain row index {row} is outside the heightfield range 0..{max(0, row_count - 1)}.")
    if column < 0 or column >= column_count:
        raise ValueError(f"Terrain column index {column} is outside the heightfield range 0..{max(0, column_count - 1)}.")
    return row, column


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


def terrain_height_range(primitive: TerrainHeightfieldPrimitive) -> tuple[float, float]:
    """Return min/max terrain height samples for UI summaries."""

    rows = _height_rows(primitive)
    values = [height for row in rows for height in row]
    if not values:
        return (0.0, 0.0)
    return (min(values), max(values))


def available_terrain_shape_presets() -> tuple[TerrainShapePreset, ...]:
    """Return named terrain forms available to Map Studio."""

    return _TERRAIN_SHAPE_PRESETS


def _terrain_shape_preset(preset_id: str) -> TerrainShapePreset:
    wanted = str(preset_id or "").strip().lower()
    for preset in _TERRAIN_SHAPE_PRESETS:
        if preset.preset_id == wanted:
            return preset
    known = ", ".join(preset.preset_id for preset in _TERRAIN_SHAPE_PRESETS)
    raise ValueError(f"Unknown Map Studio terrain shape preset '{preset_id}'. Known presets: {known}.")


def sample_terrain_height(primitive: TerrainHeightfieldPrimitive, *, x: float, y: float) -> float:
    """Return bilinear terrain height at local room X/Y coordinates."""

    validation = validate_terrain_heightfield_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    rows = _height_rows(primitive)
    width = float(primitive.width)
    depth = float(primitive.depth)
    column_pos = ((float(x) + (width * 0.5)) / width) * float(validation.column_count - 1)
    row_pos = ((float(y) + (depth * 0.5)) / depth) * float(validation.row_count - 1)
    column_pos = max(0.0, min(float(validation.column_count - 1), column_pos))
    row_pos = max(0.0, min(float(validation.row_count - 1), row_pos))
    column0 = int(math.floor(column_pos))
    row0 = int(math.floor(row_pos))
    column1 = min(validation.column_count - 1, column0 + 1)
    row1 = min(validation.row_count - 1, row0 + 1)
    column_t = column_pos - float(column0)
    row_t = row_pos - float(row0)
    h00 = float(rows[row0][column0])
    h10 = float(rows[row0][column1])
    h01 = float(rows[row1][column0])
    h11 = float(rows[row1][column1])
    h0 = h00 * (1.0 - column_t) + h10 * column_t
    h1 = h01 * (1.0 - column_t) + h11 * column_t
    return h0 * (1.0 - row_t) + h1 * row_t


def apply_terrain_shape_preset(
    primitive: TerrainHeightfieldPrimitive,
    *,
    preset_id: str,
    height: float | None = None,
) -> TerrainHeightfieldPrimitive:
    """Replace height samples with a named terrain form."""

    validation = validate_terrain_heightfield_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    preset = _terrain_shape_preset(preset_id)
    amplitude = float(preset.default_height if height is None else height)
    rows: list[tuple[float, ...]] = []
    row_max = max(1, validation.row_count - 1)
    column_max = max(1, validation.column_count - 1)
    for row_index in range(validation.row_count):
        row_t = row_index / row_max
        y = (row_t * 2.0) - 1.0
        values: list[float] = []
        for column_index in range(validation.column_count):
            column_t = column_index / column_max
            x = (column_t * 2.0) - 1.0
            radial = min(1.0, math.sqrt((x * x) + (y * y)))
            if preset.preset_id == "flat":
                value = amplitude
            elif preset.preset_id == "gentle_mound":
                value = amplitude * max(0.0, 1.0 - radial) ** 1.35
            elif preset.preset_id == "shallow_bowl":
                value = amplitude * radial * 0.65
            elif preset.preset_id == "ridge":
                value = amplitude * max(0.0, 1.0 - abs(x)) ** 1.15
            elif preset.preset_id == "ramp":
                value = amplitude * row_t
            elif preset.preset_id == "terraces":
                bands = 3.0
                value = amplitude * (math.floor(row_t * bands) / bands)
            else:
                raise ValueError(f"Unsupported terrain shape preset '{preset.preset_id}'.")
            values.append(float(value))
        rows.append(tuple(values))
    return _replace_height_rows(
        primitive,
        tuple(rows),
        operation="shape_preset",
        metadata={
            "last_shape_preset_id": preset.preset_id,
            "last_shape_preset_label": preset.label,
            "last_shape_height": amplitude,
        },
    )


def set_terrain_heightfield_sample(
    primitive: TerrainHeightfieldPrimitive,
    *,
    row_index: int,
    column_index: int,
    height: float,
) -> TerrainHeightfieldPrimitive:
    """Return terrain with one grid sample set to a specific height."""

    validation = validate_terrain_heightfield_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    row, column = _sample_indices(primitive, row_index, column_index)
    rows = [list(item) for item in _height_rows(primitive)]
    rows[row][column] = float(height)
    return _replace_height_rows(
        primitive,
        tuple(tuple(item) for item in rows),
        operation="set_height_sample",
        metadata={"last_row_index": row, "last_column_index": column, "last_height": float(height)},
    )


def offset_terrain_heightfield_samples(
    primitive: TerrainHeightfieldPrimitive,
    *,
    row_index: int,
    column_index: int,
    delta: float,
    radius: int = 0,
) -> TerrainHeightfieldPrimitive:
    """Return terrain with one sample or a small grid brush raised/lowered."""

    validation = validate_terrain_heightfield_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    row, column = _sample_indices(primitive, row_index, column_index)
    brush_radius = max(0, int(radius))
    rows = [list(item) for item in _height_rows(primitive)]
    changed = 0
    for row_cursor in range(max(0, row - brush_radius), min(validation.row_count, row + brush_radius + 1)):
        for column_cursor in range(max(0, column - brush_radius), min(validation.column_count, column + brush_radius + 1)):
            distance = math.sqrt(float(row_cursor - row) ** 2 + float(column_cursor - column) ** 2)
            if distance > brush_radius:
                continue
            weight = 1.0 if brush_radius <= 0 else max(0.0, 1.0 - (distance / float(brush_radius + 1)))
            rows[row_cursor][column_cursor] = float(rows[row_cursor][column_cursor]) + (float(delta) * weight)
            changed += 1
    return _replace_height_rows(
        primitive,
        tuple(tuple(item) for item in rows),
        operation="offset_height_samples",
        metadata={
            "last_row_index": row,
            "last_column_index": column,
            "last_delta": float(delta),
            "last_radius": brush_radius,
            "last_changed_sample_count": changed,
        },
    )


def flatten_terrain_heightfield(primitive: TerrainHeightfieldPrimitive, *, height: float = 0.0) -> TerrainHeightfieldPrimitive:
    """Return terrain with every height sample set to one level."""

    validation = validate_terrain_heightfield_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    rows = tuple(tuple(float(height) for _column in range(validation.column_count)) for _row in range(validation.row_count))
    return _replace_height_rows(
        primitive,
        rows,
        operation="flatten",
        metadata={"last_height": float(height)},
    )


def smooth_terrain_heightfield(
    primitive: TerrainHeightfieldPrimitive,
    *,
    iterations: int = 1,
    strength: float = 0.5,
    preserve_boundary: bool = True,
) -> TerrainHeightfieldPrimitive:
    """Return terrain with height samples averaged toward their neighbors."""

    validation = validate_terrain_heightfield_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    count = max(1, int(iterations))
    blend = max(0.0, min(1.0, float(strength)))
    rows = [list(item) for item in _height_rows(primitive)]
    for _iteration in range(count):
        source = [list(item) for item in rows]
        for row_index in range(validation.row_count):
            for column_index in range(validation.column_count):
                boundary = row_index in {0, validation.row_count - 1} or column_index in {0, validation.column_count - 1}
                if preserve_boundary and boundary:
                    continue
                neighbours: list[float] = []
                for row_delta, column_delta in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    row_cursor = row_index + row_delta
                    column_cursor = column_index + column_delta
                    if 0 <= row_cursor < validation.row_count and 0 <= column_cursor < validation.column_count:
                        neighbours.append(float(source[row_cursor][column_cursor]))
                if not neighbours:
                    continue
                average = sum(neighbours) / len(neighbours)
                rows[row_index][column_index] = float(source[row_index][column_index]) * (1.0 - blend) + average * blend
    return _replace_height_rows(
        primitive,
        tuple(tuple(item) for item in rows),
        operation="smooth",
        metadata={
            "last_iterations": count,
            "last_strength": blend,
            "preserve_boundary": bool(preserve_boundary),
        },
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
    "TerrainShapePreset",
    "TerrainSlopeReport",
    "analyse_terrain_slopes",
    "apply_terrain_shape_preset",
    "available_terrain_shape_presets",
    "build_terrain_mesh",
    "build_terrain_wok",
    "compile_terrain_room_geometry",
    "flatten_terrain_heightfield",
    "offset_terrain_heightfield_samples",
    "sample_terrain_height",
    "set_terrain_heightfield_sample",
    "smooth_terrain_heightfield",
    "terrain_height_range",
    "validate_terrain_heightfield_primitive",
]
