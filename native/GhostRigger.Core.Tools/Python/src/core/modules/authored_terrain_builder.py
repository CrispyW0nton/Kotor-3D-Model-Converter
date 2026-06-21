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


@dataclass(frozen=True)
class TerrainBrushStrokePoint:
    """One heightfield sample touched by a terrain sculpt stroke."""

    row_index: int
    column_index: int
    strength: float = 1.0


@dataclass(frozen=True)
class TerrainBrushDirtyRegion:
    """Minimal sample-space bounds changed by a terrain brush stroke."""

    min_row: int
    max_row: int
    min_column: int
    max_column: int
    changed_sample_count: int

    def to_metadata(self) -> dict[str, int]:
        """Return a JSON/KMAP-friendly dirty-region payload."""

        return {
            "min_row": int(self.min_row),
            "max_row": int(self.max_row),
            "min_column": int(self.min_column),
            "max_column": int(self.max_column),
            "changed_sample_count": int(self.changed_sample_count),
        }


@dataclass(frozen=True)
class TerrainBrushPerformanceAudit:
    """Deterministic interaction-budget estimate for one terrain brush stroke."""

    sample_point_count: int
    affected_sample_count: int
    dirty_region: TerrainBrushDirtyRegion
    estimated_apply_ms: float
    budget_ms: float = 8.0
    within_budget: bool = True
    input_event_policy: str = "Coalesce pointer samples and apply one terrain brush batch per viewport frame."
    rebuild_policy: str = "Update dirty terrain samples only; defer full MDL/WOK rebuild until stroke commit, validation, or export."
    warnings: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        """Return a JSON/KMAP-friendly terrain brush budget payload."""

        return {
            "sample_point_count": int(self.sample_point_count),
            "affected_sample_count": int(self.affected_sample_count),
            "dirty_region": self.dirty_region.to_metadata(),
            "estimated_apply_ms": float(self.estimated_apply_ms),
            "budget_ms": float(self.budget_ms),
            "within_budget": bool(self.within_budget),
            "input_event_policy": self.input_event_policy,
            "rebuild_policy": self.rebuild_policy,
            "warnings": list(self.warnings),
        }


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


def mirror_terrain_heightfield_z(
    primitive: TerrainHeightfieldPrimitive,
    *,
    center_height: float | None = None,
) -> TerrainHeightfieldPrimitive:
    """Reflect terrain height samples around a horizontal Z plane."""

    validation = validate_terrain_heightfield_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    min_height, max_height = terrain_height_range(primitive)
    if center_height is None:
        mirror_height = (float(min_height) + float(max_height)) * 0.5
    else:
        mirror_height = float(center_height)
    if not math.isfinite(mirror_height):
        raise ValueError("Terrain Mirror Z center height must be finite.")
    rows = tuple(
        tuple((2.0 * mirror_height) - float(value) for value in row)
        for row in _height_rows(primitive)
    )
    mirrored = _replace_height_rows(
        primitive,
        rows,
        operation="mirror_z",
        metadata={
            "mirror_axis": "z",
            "mirror_center_height": mirror_height,
            "height_min_before": float(min_height),
            "height_max_before": float(max_height),
            "source": "map_studio:terrain_mirror_z",
        },
    )
    slope_report = analyse_terrain_slopes(mirrored)
    return replace(
        mirrored,
        metadata={
            **dict(mirrored.metadata),
            "mirror_z_slope_report": {
                "max_slope_degrees": float(slope_report.max_slope_degrees),
                "walkable_triangle_count": int(slope_report.walkable_triangle_count),
                "non_walk_triangle_count": int(slope_report.non_walk_triangle_count),
                "warnings": list(slope_report.warnings),
            },
        },
    )


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


def _normalise_stroke_points(points: tuple[TerrainBrushStrokePoint | tuple[int, int] | tuple[int, int, float], ...] | list[Any]) -> tuple[TerrainBrushStrokePoint, ...]:
    normalised: list[TerrainBrushStrokePoint] = []
    for item in tuple(points or ()):
        if isinstance(item, TerrainBrushStrokePoint):
            normalised.append(item)
            continue
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            strength = float(item[2]) if len(item) >= 3 else 1.0
            normalised.append(TerrainBrushStrokePoint(int(item[0]), int(item[1]), strength))
    if not normalised:
        raise ValueError("Terrain brush stroke requires at least one sample point.")
    return tuple(normalised)


def _terrain_symmetry_axes(symmetry_axis: str | None) -> tuple[str, ...]:
    axis = str(symmetry_axis or "").strip().lower().replace("-", "_").replace(" ", "_")
    if axis in {"", "none", "off", "false"}:
        return ()
    if axis in {"row", "rows", "y", "depth"}:
        return ("row",)
    if axis in {"column", "columns", "col", "x", "width"}:
        return ("column",)
    if axis in {"both", "all", "xy", "x_y", "row_column", "column_row"}:
        return ("row", "column")
    raise ValueError("Terrain brush symmetry_axis must be one of none, row/y, column/x, or both/xy.")


def _expand_stroke_points_for_symmetry(
    primitive: TerrainHeightfieldPrimitive,
    validation: TerrainHeightfieldValidation,
    points: tuple[TerrainBrushStrokePoint, ...],
    *,
    symmetry_axis: str | None = None,
) -> tuple[TerrainBrushStrokePoint, ...]:
    axes = _terrain_symmetry_axes(symmetry_axis)
    if not axes:
        return points
    ordered: list[tuple[int, int]] = []
    strengths: dict[tuple[int, int], float] = {}
    for point in points:
        row, column = _sample_indices(primitive, point.row_index, point.column_index)
        mirrored: list[tuple[int, int]] = [(row, column)]
        mirror_row = validation.row_count - 1 - row
        mirror_column = validation.column_count - 1 - column
        if "row" in axes:
            mirrored.append((mirror_row, column))
        if "column" in axes:
            mirrored.append((row, mirror_column))
        if "row" in axes and "column" in axes:
            mirrored.append((mirror_row, mirror_column))
        strength = max(0.0, min(1.0, float(point.strength)))
        for candidate in mirrored:
            if candidate not in strengths:
                ordered.append(candidate)
                strengths[candidate] = strength
            else:
                strengths[candidate] = max(strengths[candidate], strength)
    return tuple(TerrainBrushStrokePoint(row, column, strengths[(row, column)]) for row, column in ordered)


def _brush_cells(
    *,
    validation: TerrainHeightfieldValidation,
    row: int,
    column: int,
    radius: int,
    point_strength: float = 1.0,
) -> tuple[tuple[int, int, float], ...]:
    brush_radius = max(0, int(radius))
    cells: list[tuple[int, int, float]] = []
    for row_cursor in range(max(0, row - brush_radius), min(validation.row_count, row + brush_radius + 1)):
        for column_cursor in range(max(0, column - brush_radius), min(validation.column_count, column + brush_radius + 1)):
            distance = math.sqrt(float(row_cursor - row) ** 2 + float(column_cursor - column) ** 2)
            if distance > brush_radius:
                continue
            falloff = 1.0 if brush_radius <= 0 else max(0.0, 1.0 - (distance / float(brush_radius + 1)))
            cells.append((row_cursor, column_cursor, falloff * max(0.0, min(1.0, float(point_strength)))))
    return tuple(cells)


def _dirty_region(cells: set[tuple[int, int]]) -> TerrainBrushDirtyRegion:
    if not cells:
        return TerrainBrushDirtyRegion(0, 0, 0, 0, 0)
    rows = [row for row, _column in cells]
    columns = [column for _row, column in cells]
    return TerrainBrushDirtyRegion(
        min_row=min(rows),
        max_row=max(rows),
        min_column=min(columns),
        max_column=max(columns),
        changed_sample_count=len(cells),
    )


def _deterministic_noise(row: int, column: int, seed: int) -> float:
    value = math.sin(((int(row) + 1) * 12.9898) + ((int(column) + 1) * 78.233) + (int(seed) * 37.719)) * 43758.5453
    fractional = value - math.floor(value)
    return (fractional * 2.0) - 1.0


def audit_terrain_brush_stroke_interaction(
    primitive: TerrainHeightfieldPrimitive,
    *,
    points: tuple[TerrainBrushStrokePoint | tuple[int, int] | tuple[int, int, float], ...] | list[Any],
    radius: int = 0,
    brush: str = "raise",
    iterations: int = 1,
    budget_ms: float = 8.0,
    symmetry_axis: str | None = None,
) -> TerrainBrushPerformanceAudit:
    """Estimate whether a terrain brush stroke can stay inside the live interaction budget."""

    validation = validate_terrain_heightfield_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    input_points = _normalise_stroke_points(points)
    stroke_points = _expand_stroke_points_for_symmetry(
        primitive,
        validation,
        input_points,
        symmetry_axis=symmetry_axis,
    )
    brush_radius = max(0, int(radius))
    affected_cells: set[tuple[int, int]] = set()
    for point in stroke_points:
        row, column = _sample_indices(primitive, point.row_index, point.column_index)
        for row_cursor, column_cursor, weight in _brush_cells(
            validation=validation,
            row=row,
            column=column,
            radius=brush_radius,
            point_strength=point.strength,
        ):
            if weight > 0.0:
                affected_cells.add((row_cursor, column_cursor))

    op = str(brush or "").strip().lower()
    iteration_multiplier = max(1, int(iterations)) if op in {"smooth", "erode"} else 1
    if op in {"terrace", "noise", "plateau", "pinch", "ramp", "slope", "erase", "reset"}:
        iteration_multiplier = max(1, iteration_multiplier)
    operation_count = max(1, len(affected_cells) * iteration_multiplier)
    estimated_apply_ms = round((operation_count * 0.01) + (len(stroke_points) * 0.02), 3)
    warnings: list[str] = []
    within_budget = estimated_apply_ms <= float(budget_ms)
    if not within_budget:
        warnings.append(
            "Terrain brush stroke exceeds the live sculpt budget; coalesce input samples or commit a smaller dirty region."
        )
    if len(stroke_points) > 32:
        warnings.append("Terrain brush stroke contains many pointer samples; UI should coalesce high-frequency input per frame.")
    return TerrainBrushPerformanceAudit(
        sample_point_count=len(stroke_points),
        affected_sample_count=len(affected_cells),
        dirty_region=_dirty_region(affected_cells),
        estimated_apply_ms=estimated_apply_ms,
        budget_ms=float(budget_ms),
        within_budget=within_budget,
        warnings=tuple(warnings),
    )


def apply_terrain_brush_stroke(
    primitive: TerrainHeightfieldPrimitive,
    *,
    brush: str,
    points: tuple[TerrainBrushStrokePoint | tuple[int, int] | tuple[int, int, float], ...] | list[Any],
    delta: float = 0.1,
    radius: int = 0,
    height: float = 0.0,
    iterations: int = 1,
    strength: float = 0.5,
    preserve_boundary: bool = True,
    symmetry_axis: str | None = None,
) -> TerrainHeightfieldPrimitive:
    """Apply a local, batch terrain brush stroke and record dirty sample bounds."""

    validation = validate_terrain_heightfield_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    input_points = _normalise_stroke_points(points)
    stroke_points = _expand_stroke_points_for_symmetry(
        primitive,
        validation,
        input_points,
        symmetry_axis=symmetry_axis,
    )
    op = str(brush or "").strip().lower()
    if op not in {"raise", "lower", "offset", "flatten", "smooth", "terrace", "noise", "plateau", "pinch", "ramp", "slope", "erode", "erase", "reset"}:
        raise ValueError(f"Unsupported terrain brush stroke '{brush}'.")
    rows = [list(item) for item in _height_rows(primitive)]
    dirty_cells: set[tuple[int, int]] = set()
    brush_radius = max(0, int(radius))
    blend = max(0.0, min(1.0, float(strength)))

    if op in {"raise", "lower", "offset", "flatten", "terrace", "noise", "plateau", "pinch", "ramp", "slope", "erase", "reset"}:
        signed_delta = float(delta)
        if op == "raise":
            signed_delta = abs(signed_delta)
        elif op == "lower":
            signed_delta = -abs(signed_delta)
        terrace_step = abs(float(height)) if abs(float(height)) > 1e-6 else max(0.05, abs(float(delta)))
        ramp_start: tuple[int, int] | None = None
        ramp_end: tuple[int, int] | None = None
        ramp_start_height = 0.0
        ramp_end_height = 0.0
        if op in {"ramp", "slope"}:
            start_point = stroke_points[0]
            end_point = stroke_points[-1]
            ramp_start = _sample_indices(primitive, start_point.row_index, start_point.column_index)
            ramp_end = _sample_indices(primitive, end_point.row_index, end_point.column_index)
            ramp_start_height = float(rows[ramp_start[0]][ramp_start[1]])
            ramp_end_height = float(height) if abs(float(height)) > 1e-6 else ramp_start_height + signed_delta
        for point in stroke_points:
            row, column = _sample_indices(primitive, point.row_index, point.column_index)
            center_height = float(rows[row][column])
            noise_seed = (row * 131) + (column * 17) + len(stroke_points)
            for row_cursor, column_cursor, weight in _brush_cells(
                validation=validation,
                row=row,
                column=column,
                radius=brush_radius,
                point_strength=point.strength,
            ):
                if op == "flatten":
                    local_blend = max(0.0, min(1.0, blend * weight))
                    rows[row_cursor][column_cursor] = float(rows[row_cursor][column_cursor]) * (1.0 - local_blend) + float(height) * local_blend
                elif op in {"erase", "reset"}:
                    local_blend = max(0.0, min(1.0, blend * weight))
                    current = float(rows[row_cursor][column_cursor])
                    baseline = float(height) if abs(float(height)) > 1e-6 else 0.0
                    rows[row_cursor][column_cursor] = current * (1.0 - local_blend) + baseline * local_blend
                elif op == "terrace":
                    local_blend = max(0.0, min(1.0, blend * weight))
                    current = float(rows[row_cursor][column_cursor])
                    target = round(current / terrace_step) * terrace_step
                    rows[row_cursor][column_cursor] = current * (1.0 - local_blend) + target * local_blend
                elif op == "noise":
                    noise = _deterministic_noise(row_cursor, column_cursor, noise_seed)
                    rows[row_cursor][column_cursor] = float(rows[row_cursor][column_cursor]) + (abs(signed_delta) * noise * blend * weight)
                elif op == "plateau":
                    local_blend = max(0.0, min(1.0, blend * weight))
                    current = float(rows[row_cursor][column_cursor])
                    rows[row_cursor][column_cursor] = current * (1.0 - local_blend) + center_height * local_blend
                elif op == "pinch":
                    local_blend = max(0.0, min(1.0, blend * weight))
                    current = float(rows[row_cursor][column_cursor])
                    rows[row_cursor][column_cursor] = current + ((center_height - current) * local_blend)
                elif op in {"ramp", "slope"}:
                    current = float(rows[row_cursor][column_cursor])
                    target = current
                    if ramp_start is not None and ramp_end is not None:
                        start_row, start_column = ramp_start
                        end_row, end_column = ramp_end
                        path_row = float(end_row - start_row)
                        path_column = float(end_column - start_column)
                        path_length_sq = (path_row * path_row) + (path_column * path_column)
                        if path_length_sq > 1e-6:
                            sample_row = float(row_cursor - start_row)
                            sample_column = float(column_cursor - start_column)
                            path_t = ((sample_row * path_row) + (sample_column * path_column)) / path_length_sq
                            path_t = max(0.0, min(1.0, path_t))
                            target = ramp_start_height + ((ramp_end_height - ramp_start_height) * path_t)
                        else:
                            target = ramp_end_height
                    local_blend = max(0.0, min(1.0, blend * weight))
                    rows[row_cursor][column_cursor] = current * (1.0 - local_blend) + target * local_blend
                else:
                    rows[row_cursor][column_cursor] = float(rows[row_cursor][column_cursor]) + (signed_delta * weight)
                dirty_cells.add((row_cursor, column_cursor))
    elif op in {"smooth", "erode"}:
        affected: set[tuple[int, int]] = set()
        for point in stroke_points:
            row, column = _sample_indices(primitive, point.row_index, point.column_index)
            for row_cursor, column_cursor, weight in _brush_cells(
                validation=validation,
                row=row,
                column=column,
                radius=brush_radius,
                point_strength=point.strength,
            ):
                if weight > 0.0:
                    affected.add((row_cursor, column_cursor))
        for _iteration in range(max(1, int(iterations))):
            source = [list(item) for item in rows]
            for row_cursor, column_cursor in affected:
                boundary = row_cursor in {0, validation.row_count - 1} or column_cursor in {0, validation.column_count - 1}
                if preserve_boundary and boundary:
                    continue
                neighbours: list[float] = []
                offsets = (
                    ((-1, 0), (1, 0), (0, -1), (0, 1))
                    if op == "smooth"
                    else ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
                )
                for row_delta, column_delta in offsets:
                    row_neighbour = row_cursor + row_delta
                    column_neighbour = column_cursor + column_delta
                    if 0 <= row_neighbour < validation.row_count and 0 <= column_neighbour < validation.column_count:
                        neighbours.append(float(source[row_neighbour][column_neighbour]))
                if not neighbours:
                    continue
                average = sum(neighbours) / len(neighbours)
                current = float(source[row_cursor][column_cursor])
                if op == "erode":
                    talus = abs(float(height)) if abs(float(height)) > 1e-6 else max(0.02, abs(float(delta)) * 0.5)
                    difference = current - average
                    if abs(difference) < talus:
                        continue
                    erode_blend = max(0.0, min(1.0, blend * 0.65))
                    rows[row_cursor][column_cursor] = current - (difference * erode_blend)
                else:
                    rows[row_cursor][column_cursor] = current * (1.0 - blend) + average * blend
                dirty_cells.add((row_cursor, column_cursor))

    dirty = _dirty_region(dirty_cells)
    updated_preview = replace(primitive, heights=tuple(tuple(item) for item in rows))
    slope_report = analyse_terrain_slopes(updated_preview)
    slope_warnings = list(slope_report.warnings)
    if op == "noise" and slope_report.non_walk_triangle_count:
        slope_warnings.append(
            "Noise brush created or retained non-walkable terrain triangles; review WOK surface output before game proof."
        )
    performance = audit_terrain_brush_stroke_interaction(
        primitive,
        points=input_points,
        radius=brush_radius,
        brush=op,
        iterations=iterations,
        symmetry_axis=symmetry_axis,
    )
    return _replace_height_rows(
        primitive,
        tuple(tuple(item) for item in rows),
        operation="terrain_brush_stroke",
        metadata={
            "last_brush": op,
            "last_brush_radius": brush_radius,
            "last_brush_delta": float(delta),
            "last_brush_height": float(height),
            "last_brush_strength": blend,
            "last_brush_symmetry_axis": str(symmetry_axis or "").strip().lower(),
            "last_brush_slope_report": {
                "max_slope_degrees": float(slope_report.max_slope_degrees),
                "walkable_triangle_count": int(slope_report.walkable_triangle_count),
                "non_walk_triangle_count": int(slope_report.non_walk_triangle_count),
                "warnings": slope_warnings,
            },
            "last_stroke_point_count": len(stroke_points),
            "last_input_stroke_point_count": len(input_points),
            "last_dirty_region": dirty.to_metadata(),
            "last_changed_sample_count": dirty.changed_sample_count,
            "last_brush_performance": performance.to_metadata(),
            "defer_full_rebuild_until_stroke_end": True,
            "dirty_region_only": True,
            "source": "map_studio:terrain_brush_stroke",
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


def terrain_triangle_slope_degrees(a: Vec3, b: Vec3, c: Vec3) -> float:
    """Return the grade angle for one generated terrain triangle."""

    return _triangle_slope_degrees(a, b, c)


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
    "TerrainBrushDirtyRegion",
    "TerrainBrushPerformanceAudit",
    "TerrainBrushStrokePoint",
    "TerrainShapePreset",
    "TerrainSlopeReport",
    "analyse_terrain_slopes",
    "audit_terrain_brush_stroke_interaction",
    "apply_terrain_brush_stroke",
    "apply_terrain_shape_preset",
    "available_terrain_shape_presets",
    "build_terrain_mesh",
    "build_terrain_wok",
    "compile_terrain_room_geometry",
    "flatten_terrain_heightfield",
    "mirror_terrain_heightfield_z",
    "offset_terrain_heightfield_samples",
    "sample_terrain_height",
    "set_terrain_heightfield_sample",
    "smooth_terrain_heightfield",
    "terrain_height_range",
    "terrain_triangle_slope_degrees",
    "validate_terrain_heightfield_primitive",
]
