"""Live terrain sculpt stroke contracts for Map Studio.

This module owns the headless interaction policy for terrain painting.  The UI
can feed many mouse/tablet samples into this layer and receive one coalesced
frame batch that is safe to apply without rebuilding the whole module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from time import perf_counter
from typing import Any

from .authored_module_project import AuthoredModuleProject, normalise_resref
from .authored_terrain_builder import (
    TerrainBrushDirtyRegion,
    TerrainBrushPerformanceAudit,
    TerrainBrushStrokePoint,
    TerrainHeightfieldPrimitive,
    analyse_terrain_slopes,
    audit_terrain_brush_stroke_interaction,
)


DEFERRED_TERRAIN_SCULPT_BRUSHES = frozenset({"ramp", "slope"})


@dataclass(frozen=True)
class MapStudioTerrainSculptFrame:
    """One coalesced terrain brush frame for live viewport sculpting."""

    room_resref: str
    brush: str
    raw_sample_count: int
    applied_sample_count: int
    coalesced_sample_count: int
    points: tuple[TerrainBrushStrokePoint, ...]
    operation: str
    operation_kwargs: dict[str, Any]
    performance: TerrainBrushPerformanceAudit
    should_apply_live: bool
    defer_full_rebuild: bool = True
    warnings: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        """Return a JSON/KMAP-friendly live-sculpt frame summary."""

        return {
            "room_resref": self.room_resref,
            "brush": self.brush,
            "raw_sample_count": int(self.raw_sample_count),
            "applied_sample_count": int(self.applied_sample_count),
            "coalesced_sample_count": int(self.coalesced_sample_count),
            "points": [
                {
                    "row_index": int(point.row_index),
                    "column_index": int(point.column_index),
                    "strength": float(point.strength),
                }
                for point in self.points
            ],
            "operation": self.operation,
            "performance": self.performance.to_metadata(),
            "should_apply_live": bool(self.should_apply_live),
            "defer_full_rebuild": bool(self.defer_full_rebuild),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class MapStudioTerrainSculptApplyResult:
    """Result for a lightweight live terrain sculpt frame application."""

    applied: bool
    frame: MapStudioTerrainSculptFrame
    message: str
    full_rebuild_deferred: bool = True
    dirty_region: "MapStudioTerrainSculptDirtyRegion | None" = None
    dirty_region_with_halo: "MapStudioTerrainSculptDirtyRegion | None" = None
    dirty_height_patch: tuple[tuple[float, ...], ...] = ()
    row_count: int = 0
    column_count: int = 0
    elapsed_ms: float = 0.0
    project_serialized: bool = False


@dataclass(frozen=True)
class MapStudioTerrainSculptDirtyRegion:
    """A clipped sample-space rectangle used for partial terrain updates.

    ``changed_sample_count`` counts samples actually changed by the brush.  A
    halo region can cover more samples than that count because normals and the
    two triangles sharing a height sample depend on its immediate neighbours.
    """

    min_row: int = 0
    max_row: int = -1
    min_column: int = 0
    max_column: int = -1
    changed_sample_count: int = 0

    @property
    def empty(self) -> bool:
        return self.max_row < self.min_row or self.max_column < self.min_column

    @property
    def row_count(self) -> int:
        return 0 if self.empty else self.max_row - self.min_row + 1

    @property
    def column_count(self) -> int:
        return 0 if self.empty else self.max_column - self.min_column + 1

    @property
    def covered_sample_count(self) -> int:
        return self.row_count * self.column_count

    def expanded(
        self,
        *,
        row_count: int,
        column_count: int,
        halo: int = 1,
    ) -> "MapStudioTerrainSculptDirtyRegion":
        """Return this rectangle expanded and clipped to the heightfield."""

        if self.empty:
            return self
        amount = max(0, int(halo))
        return MapStudioTerrainSculptDirtyRegion(
            min_row=max(0, self.min_row - amount),
            max_row=min(max(0, int(row_count) - 1), self.max_row + amount),
            min_column=max(0, self.min_column - amount),
            max_column=min(max(0, int(column_count) - 1), self.max_column + amount),
            changed_sample_count=self.changed_sample_count,
        )

    def to_metadata(self) -> dict[str, int | bool]:
        return {
            "min_row": int(self.min_row),
            "max_row": int(self.max_row),
            "min_column": int(self.min_column),
            "max_column": int(self.max_column),
            "changed_sample_count": int(self.changed_sample_count),
            "covered_sample_count": int(self.covered_sample_count),
            "empty": bool(self.empty),
        }


@dataclass(frozen=True)
class MapStudioTerrainSculptStrokeFrameResult:
    """Result of one in-place frame update inside a terrain stroke."""

    applied: bool
    frame: MapStudioTerrainSculptFrame
    dirty_region: MapStudioTerrainSculptDirtyRegion
    dirty_region_with_halo: MapStudioTerrainSculptDirtyRegion
    changed_flat_indices: tuple[int, ...]
    elapsed_ms: float
    message: str
    project_serialized: bool = False


@dataclass(frozen=True)
class MapStudioTerrainSculptCommitResult:
    """Durable result produced once when a live terrain stroke is released."""

    project: AuthoredModuleProject
    primitive: TerrainHeightfieldPrimitive
    payload: dict[str, Any]
    dirty_region: MapStudioTerrainSculptDirtyRegion
    dirty_region_with_halo: MapStudioTerrainSculptDirtyRegion
    frame_count: int
    decode_count: int
    serialization_count: int
    commit_elapsed_ms: float
    serialization_elapsed_ms: float


_LIVE_TERRAIN_BRUSHES = frozenset(
    {
        "raise",
        "lower",
        "offset",
        "flatten",
        "smooth",
        "terrace",
        "noise",
        "plateau",
        "pinch",
        "ramp",
        "slope",
        "erode",
        "erase",
        "reset",
    }
)


def _dirty_region_from_flat_indices(
    indices: set[int] | tuple[int, ...] | list[int],
    *,
    column_count: int,
) -> MapStudioTerrainSculptDirtyRegion:
    values = tuple(int(index) for index in indices)
    if not values or int(column_count) <= 0:
        return MapStudioTerrainSculptDirtyRegion()
    rows = tuple(index // int(column_count) for index in values)
    columns = tuple(index % int(column_count) for index in values)
    return MapStudioTerrainSculptDirtyRegion(
        min_row=min(rows),
        max_row=max(rows),
        min_column=min(columns),
        max_column=max(columns),
        changed_sample_count=len(set(values)),
    )


@dataclass
class MapStudioTerrainSculptStrokeSession:
    """Mutable, dirty-region terrain state for one press-to-release stroke.

    A session is deliberately not a KMAP object.  It decodes the authored
    payload once at begin, flattens the target heightfield once, and mutates
    that flat buffer for every pointer frame.  ``commit`` reconstructs the
    immutable terrain/project and serializes the authored payload exactly
    once.  This keeps payload IO and whole-grid slope analysis out of the live
    interaction path.
    """

    project: AuthoredModuleProject
    room_index: int
    room_resref: str
    source_primitive: TerrainHeightfieldPrimitive
    row_count: int
    column_count: int
    _heights: list[float] = field(repr=False)
    decode_count: int = 0
    serialization_count: int = 0
    frame_count: int = 0
    _dirty_indices: set[int] = field(default_factory=set, repr=False)
    _last_frame: MapStudioTerrainSculptFrame | None = field(default=None, repr=False)
    _last_options: dict[str, Any] = field(default_factory=dict, repr=False)
    _commit_result: MapStudioTerrainSculptCommitResult | None = field(default=None, repr=False)
    _cancelled: bool = False

    @classmethod
    def from_project(
        cls,
        project: AuthoredModuleProject,
        *,
        room_resref: str,
    ) -> "MapStudioTerrainSculptStrokeSession":
        """Begin a stroke from an already decoded authored project."""

        wanted = normalise_resref(room_resref)
        room_index = -1
        primitive: TerrainHeightfieldPrimitive | None = None
        for index, room in enumerate(tuple(project.rooms or ())):
            if wanted and normalise_resref(room.room_resref) != wanted:
                continue
            if isinstance(room.primitive, TerrainHeightfieldPrimitive):
                room_index = index
                primitive = room.primitive
                break
        if primitive is None or room_index < 0:
            label = room_resref or "first authored room"
            raise ValueError(f"Map Studio terrain sculpting could not find editable terrain room '{label}'.")
        rows = tuple(tuple(float(value) for value in row) for row in tuple(primitive.heights or ()))
        row_count = len(rows)
        column_count = len(rows[0]) if rows else 0
        if row_count < 2 or column_count < 2:
            raise ValueError("Terrain heightfield requires at least a 2x2 height grid.")
        if any(len(row) != column_count for row in rows):
            raise ValueError("Terrain heightfield rows must all have the same number of columns.")
        if not math.isfinite(float(primitive.width)) or not math.isfinite(float(primitive.depth)):
            raise ValueError("Terrain heightfield width and depth must be finite.")
        if float(primitive.width) <= 0.0 or float(primitive.depth) <= 0.0:
            raise ValueError("Terrain heightfield width and depth must be positive.")
        heights = [value for row in rows for value in row]
        if not all(math.isfinite(value) for value in heights):
            raise ValueError("Terrain heightfield samples must be finite.")
        return cls(
            project=project,
            room_index=room_index,
            room_resref=normalise_resref(room_resref or primitive.room_resref),
            source_primitive=primitive,
            row_count=row_count,
            column_count=column_count,
            _heights=heights,
        )

    @classmethod
    def from_kmap_payload(
        cls,
        payload: Any,
        *,
        room_resref: str,
        fallback_name: str = "new_level",
        fallback_game: str = "K1",
    ) -> "MapStudioTerrainSculptStrokeSession":
        """Decode an authored KMAP payload once and begin a terrain stroke."""

        from .authored_module_kmap_bridge import authored_project_from_kmap_payload

        project = authored_project_from_kmap_payload(
            payload,
            fallback_name=fallback_name,
            fallback_game=fallback_game,
        )
        session = cls.from_project(project, room_resref=room_resref)
        session.decode_count = 1
        return session

    @property
    def height_buffer(self) -> list[float]:
        """Return the stroke-owned flat buffer used by partial viewport upload."""

        return self._heights

    @property
    def dirty_region(self) -> MapStudioTerrainSculptDirtyRegion:
        return _dirty_region_from_flat_indices(self._dirty_indices, column_count=self.column_count)

    @property
    def dirty_region_with_halo(self) -> MapStudioTerrainSculptDirtyRegion:
        return self.dirty_region.expanded(
            row_count=self.row_count,
            column_count=self.column_count,
            halo=1,
        )

    @property
    def committed(self) -> bool:
        return self._commit_result is not None

    @property
    def cancelled(self) -> bool:
        return bool(self._cancelled)

    def _ensure_active(self) -> None:
        if self.committed:
            raise RuntimeError("Terrain sculpt stroke has already been committed.")
        if self.cancelled:
            raise RuntimeError("Terrain sculpt stroke has been cancelled.")

    def _flat_index(self, row: int, column: int) -> int:
        row_index = int(row)
        column_index = int(column)
        if row_index < 0 or row_index >= self.row_count:
            raise ValueError(
                f"Terrain row index {row_index} is outside the heightfield range 0..{self.row_count - 1}."
            )
        if column_index < 0 or column_index >= self.column_count:
            raise ValueError(
                f"Terrain column index {column_index} is outside the heightfield range 0..{self.column_count - 1}."
            )
        return row_index * self.column_count + column_index

    def height_at(self, row: int, column: int) -> float:
        return float(self._heights[self._flat_index(row, column)])

    def _expand_symmetry(
        self,
        points: tuple[TerrainBrushStrokePoint, ...],
        symmetry_axis: str | None,
    ) -> tuple[TerrainBrushStrokePoint, ...]:
        axis = str(symmetry_axis or "").strip().lower()
        if axis in {"", "none", "off"}:
            axes: tuple[str, ...] = ()
        elif axis in {"row", "rows", "y", "depth"}:
            axes = ("row",)
        elif axis in {"column", "columns", "col", "x", "width"}:
            axes = ("column",)
        elif axis in {"both", "all", "xy", "x_y", "row_column", "column_row"}:
            axes = ("row", "column")
        else:
            raise ValueError("Terrain brush symmetry_axis must be one of none, row/y, column/x, or both/xy.")
        if not axes:
            for point in points:
                self._flat_index(point.row_index, point.column_index)
            return points
        ordered: list[tuple[int, int]] = []
        strengths: dict[tuple[int, int], float] = {}
        for point in points:
            row = int(point.row_index)
            column = int(point.column_index)
            self._flat_index(row, column)
            candidates = [(row, column)]
            mirror_row = self.row_count - 1 - row
            mirror_column = self.column_count - 1 - column
            if "row" in axes:
                candidates.append((mirror_row, column))
            if "column" in axes:
                candidates.append((row, mirror_column))
            if "row" in axes and "column" in axes:
                candidates.append((mirror_row, mirror_column))
            point_strength = max(0.0, min(1.0, float(point.strength)))
            for candidate in candidates:
                if candidate not in strengths:
                    ordered.append(candidate)
                    strengths[candidate] = point_strength
                else:
                    strengths[candidate] = max(strengths[candidate], point_strength)
        return tuple(TerrainBrushStrokePoint(row, column, strengths[(row, column)]) for row, column in ordered)

    def _brush_cells(
        self,
        *,
        row: int,
        column: int,
        radius: int,
        point_strength: float,
        falloff_hardness: float,
    ) -> tuple[tuple[int, int, float], ...]:
        brush_radius = max(0, int(radius))
        hardness = max(0.0, min(1.0, float(falloff_hardness)))
        strength = max(0.0, min(1.0, float(point_strength)))
        cells: list[tuple[int, int, float]] = []
        for row_cursor in range(max(0, row - brush_radius), min(self.row_count, row + brush_radius + 1)):
            for column_cursor in range(
                max(0, column - brush_radius),
                min(self.column_count, column + brush_radius + 1),
            ):
                distance = math.hypot(float(row_cursor - row), float(column_cursor - column))
                if distance > brush_radius:
                    continue
                if brush_radius <= 0 or hardness >= 1.0 - 1.0e-9:
                    falloff = 1.0
                else:
                    normalized_distance = distance / float(brush_radius + 0.5)
                    if normalized_distance <= hardness:
                        falloff = 1.0
                    else:
                        t = max(
                            0.0,
                            min(
                                1.0,
                                (normalized_distance - hardness) / max(1.0e-9, 1.0 - hardness),
                            ),
                        )
                        falloff = 1.0 - ((t * t) * (3.0 - (2.0 * t)))
                cells.append((row_cursor, column_cursor, falloff * strength))
        return tuple(cells)

    @staticmethod
    def _deterministic_noise(row: int, column: int, seed: int) -> float:
        value = (
            math.sin(
                ((int(row) + 1) * 12.9898)
                + ((int(column) + 1) * 78.233)
                + (int(seed) * 37.719)
            )
            * 43758.5453
        )
        fractional = value - math.floor(value)
        return (fractional * 2.0) - 1.0

    def _set_height(self, index: int, value: float, changed: set[int]) -> None:
        next_value = float(value)
        if not math.isfinite(next_value):
            raise ValueError("Terrain brush produced a non-finite height sample.")
        if abs(next_value - float(self._heights[index])) <= 1.0e-12:
            return
        self._heights[index] = next_value
        changed.add(index)

    def _build_frame(
        self,
        *,
        brush: str,
        points: tuple[TerrainBrushStrokePoint | tuple[int, int] | tuple[int, int, float], ...] | list[Any],
        delta: float,
        radius: int,
        height: float,
        iterations: int,
        strength: float,
        falloff_hardness: float,
        preserve_boundary: bool,
        symmetry_axis: str | None,
        max_points_per_frame: int,
        budget_ms: float,
    ) -> tuple[MapStudioTerrainSculptFrame, tuple[TerrainBrushStrokePoint, ...]]:
        raw_points = normalise_terrain_sculpt_points(points)
        coalesced = coalesce_terrain_sculpt_points(raw_points, max_points_per_frame=max_points_per_frame)
        brush_key = str(brush or "raise").strip().lower() or "raise"
        if brush_key not in _LIVE_TERRAIN_BRUSHES:
            raise ValueError(f"Unsupported terrain brush stroke '{brush}'.")
        expanded = self._expand_symmetry(coalesced, symmetry_axis)
        affected_indices: set[int] = set()
        for point in expanded:
            for row, column, weight in self._brush_cells(
                row=int(point.row_index),
                column=int(point.column_index),
                radius=radius,
                point_strength=point.strength,
                falloff_hardness=falloff_hardness,
            ):
                if weight > 0.0:
                    affected_indices.add(self._flat_index(row, column))
        iteration_multiplier = max(1, int(iterations)) if brush_key in {"smooth", "erode"} else 1
        operation_count = max(1, len(affected_indices) * iteration_multiplier)
        # This estimate intentionally covers only the dirty-buffer work.  The
        # one-time payload decode and commit serialization are outside frames.
        estimated_apply_ms = round((operation_count * 0.01) + (len(expanded) * 0.02), 3)
        within_budget = estimated_apply_ms <= float(budget_ms)
        warnings: list[str] = []
        if not within_budget:
            warnings.append(
                "Terrain brush stroke exceeds the live dirty-buffer budget; coalesce input samples or reduce the brush footprint."
            )
        if len(coalesced) < len(raw_points):
            warnings.append(
                f"Coalesced {len(raw_points)} raw pointer sample(s) into {len(coalesced)} terrain point(s) for this frame."
            )
        performance_region = _dirty_region_from_flat_indices(
            affected_indices,
            column_count=self.column_count,
        )
        performance = TerrainBrushPerformanceAudit(
            sample_point_count=len(expanded),
            affected_sample_count=len(affected_indices),
            dirty_region=TerrainBrushDirtyRegion(
                min_row=performance_region.min_row if not performance_region.empty else 0,
                max_row=performance_region.max_row if not performance_region.empty else 0,
                min_column=performance_region.min_column if not performance_region.empty else 0,
                max_column=performance_region.max_column if not performance_region.empty else 0,
                changed_sample_count=len(affected_indices),
            ),
            estimated_apply_ms=estimated_apply_ms,
            budget_ms=float(budget_ms),
            within_budget=within_budget,
            rebuild_policy=(
                "Mutate the stroke-owned flat height buffer and update the dirty rectangle plus one-sample halo; "
                "serialize and run whole-grid slope analysis once on commit."
            ),
            warnings=tuple(warnings),
        )
        operation_kwargs = {
            "room_resref": self.room_resref,
            "points": tuple((point.row_index, point.column_index, point.strength) for point in coalesced),
            "delta": float(delta),
            "radius": int(radius),
            "height": float(height),
            "iterations": int(iterations),
            "strength": float(strength),
            "falloff_hardness": float(falloff_hardness),
            "preserve_boundary": bool(preserve_boundary),
            "symmetry_axis": str(symmetry_axis or ""),
        }
        return (
            MapStudioTerrainSculptFrame(
                room_resref=self.room_resref,
                brush=brush_key,
                raw_sample_count=len(raw_points),
                applied_sample_count=len(coalesced),
                coalesced_sample_count=max(0, len(raw_points) - len(coalesced)),
                points=coalesced,
                operation=f"brush_stroke:{brush_key}",
                operation_kwargs=operation_kwargs,
                performance=performance,
                should_apply_live=within_budget,
                warnings=tuple(warnings),
            ),
            expanded,
        )

    def apply_frame(
        self,
        *,
        brush: str,
        points: tuple[TerrainBrushStrokePoint | tuple[int, int] | tuple[int, int, float], ...] | list[Any],
        delta: float = 0.1,
        radius: int = 0,
        height: float = 0.0,
        iterations: int = 1,
        strength: float = 0.5,
        falloff_hardness: float = 0.5,
        preserve_boundary: bool = True,
        symmetry_axis: str | None = None,
        max_points_per_frame: int = 8,
        budget_ms: float = 8.0,
        force: bool = False,
    ) -> MapStudioTerrainSculptStrokeFrameResult:
        """Apply one coalesced frame without rebuilding a project or payload."""

        self._ensure_active()
        started = perf_counter()
        frame, stroke_points = self._build_frame(
            brush=brush,
            points=points,
            delta=delta,
            radius=radius,
            height=height,
            iterations=iterations,
            strength=strength,
            falloff_hardness=falloff_hardness,
            preserve_boundary=preserve_boundary,
            symmetry_axis=symmetry_axis,
            max_points_per_frame=max_points_per_frame,
            budget_ms=budget_ms,
        )
        if not frame.should_apply_live and not force:
            elapsed_ms = (perf_counter() - started) * 1000.0
            return MapStudioTerrainSculptStrokeFrameResult(
                applied=False,
                frame=frame,
                dirty_region=MapStudioTerrainSculptDirtyRegion(),
                dirty_region_with_halo=MapStudioTerrainSculptDirtyRegion(),
                changed_flat_indices=(),
                elapsed_ms=elapsed_ms,
                message=(
                    f"Skipped terrain frame: estimated {frame.performance.estimated_apply_ms:.3f} ms exceeds "
                    f"{frame.performance.budget_ms:.3f} ms dirty-buffer budget."
                ),
            )

        op = frame.brush
        brush_radius = max(0, int(radius))
        blend = max(0.0, min(1.0, float(strength)))
        changed: set[int] = set()
        if op in {"smooth", "erode"}:
            affected: set[tuple[int, int]] = set()
            for point in stroke_points:
                for row, column, weight in self._brush_cells(
                    row=int(point.row_index),
                    column=int(point.column_index),
                    radius=brush_radius,
                    point_strength=point.strength,
                    falloff_hardness=falloff_hardness,
                ):
                    if weight > 0.0:
                        affected.add((row, column))
            offsets = (
                ((-1, 0), (1, 0), (0, -1), (0, 1))
                if op == "smooth"
                else ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
            )
            for _iteration in range(max(1, int(iterations))):
                needed = set(affected)
                for row, column in affected:
                    for row_delta, column_delta in offsets:
                        neighbour = (row + row_delta, column + column_delta)
                        if 0 <= neighbour[0] < self.row_count and 0 <= neighbour[1] < self.column_count:
                            needed.add(neighbour)
                source = {
                    (row, column): float(self._heights[self._flat_index(row, column)])
                    for row, column in needed
                }
                for row, column in affected:
                    boundary = row in {0, self.row_count - 1} or column in {0, self.column_count - 1}
                    if preserve_boundary and boundary:
                        continue
                    neighbours = [
                        source[(row + row_delta, column + column_delta)]
                        for row_delta, column_delta in offsets
                        if (row + row_delta, column + column_delta) in source
                    ]
                    if not neighbours:
                        continue
                    average = sum(neighbours) / len(neighbours)
                    current = source[(row, column)]
                    if op == "erode":
                        talus = abs(float(height)) if abs(float(height)) > 1.0e-6 else max(0.02, abs(float(delta)) * 0.5)
                        difference = current - average
                        if abs(difference) < talus:
                            continue
                        next_value = current - (difference * max(0.0, min(1.0, blend * 0.65)))
                    else:
                        next_value = current * (1.0 - blend) + average * blend
                    self._set_height(self._flat_index(row, column), next_value, changed)
        else:
            signed_delta = float(delta)
            if op == "raise":
                signed_delta = abs(signed_delta)
            elif op == "lower":
                signed_delta = -abs(signed_delta)
            terrace_step = abs(float(height)) if abs(float(height)) > 1.0e-6 else max(0.05, abs(float(delta)))
            ramp_start = (int(stroke_points[0].row_index), int(stroke_points[0].column_index))
            ramp_end = (int(stroke_points[-1].row_index), int(stroke_points[-1].column_index))
            ramp_start_height = self.height_at(*ramp_start)
            ramp_end_height = float(height) if abs(float(height)) > 1.0e-6 else ramp_start_height + signed_delta
            for point in stroke_points:
                center_row = int(point.row_index)
                center_column = int(point.column_index)
                center_height = self.height_at(center_row, center_column)
                noise_seed = (center_row * 131) + (center_column * 17) + len(stroke_points)
                for row, column, weight in self._brush_cells(
                    row=center_row,
                    column=center_column,
                    radius=brush_radius,
                    point_strength=point.strength,
                    falloff_hardness=falloff_hardness,
                ):
                    index = self._flat_index(row, column)
                    current = float(self._heights[index])
                    if op == "flatten":
                        local_blend = max(0.0, min(1.0, blend * weight))
                        next_value = current * (1.0 - local_blend) + float(height) * local_blend
                    elif op in {"erase", "reset"}:
                        local_blend = max(0.0, min(1.0, blend * weight))
                        baseline = float(height) if abs(float(height)) > 1.0e-6 else 0.0
                        next_value = current * (1.0 - local_blend) + baseline * local_blend
                    elif op == "terrace":
                        local_blend = max(0.0, min(1.0, blend * weight))
                        target = round(current / terrace_step) * terrace_step
                        next_value = current * (1.0 - local_blend) + target * local_blend
                    elif op == "noise":
                        next_value = current + (
                            abs(signed_delta)
                            * self._deterministic_noise(row, column, noise_seed)
                            * blend
                            * weight
                        )
                    elif op == "plateau":
                        local_blend = max(0.0, min(1.0, blend * weight))
                        next_value = current * (1.0 - local_blend) + center_height * local_blend
                    elif op == "pinch":
                        local_blend = max(0.0, min(1.0, blend * weight))
                        next_value = current + ((center_height - current) * local_blend)
                    elif op in {"ramp", "slope"}:
                        path_row = float(ramp_end[0] - ramp_start[0])
                        path_column = float(ramp_end[1] - ramp_start[1])
                        path_length_sq = (path_row * path_row) + (path_column * path_column)
                        if path_length_sq > 1.0e-6:
                            sample_row = float(row - ramp_start[0])
                            sample_column = float(column - ramp_start[1])
                            path_t = ((sample_row * path_row) + (sample_column * path_column)) / path_length_sq
                            path_t = max(0.0, min(1.0, path_t))
                            target = ramp_start_height + ((ramp_end_height - ramp_start_height) * path_t)
                        else:
                            target = ramp_end_height
                        local_blend = max(0.0, min(1.0, blend * weight))
                        next_value = current * (1.0 - local_blend) + target * local_blend
                    else:
                        next_value = current + (signed_delta * weight)
                    self._set_height(index, next_value, changed)

        self._dirty_indices.update(changed)
        self.frame_count += 1
        self._last_frame = frame
        self._last_options = dict(frame.operation_kwargs)
        frame_region = _dirty_region_from_flat_indices(changed, column_count=self.column_count)
        elapsed_ms = (perf_counter() - started) * 1000.0
        return MapStudioTerrainSculptStrokeFrameResult(
            applied=True,
            frame=frame,
            dirty_region=frame_region,
            dirty_region_with_halo=frame_region.expanded(
                row_count=self.row_count,
                column_count=self.column_count,
                halo=1,
            ),
            changed_flat_indices=tuple(sorted(changed)),
            elapsed_ms=elapsed_ms,
            message=(
                f"Applied {len(changed)} terrain sample change(s) in {elapsed_ms:.3f} ms; "
                "project decode, whole-grid slope analysis, and KMAP serialization remain deferred."
            ),
        )

    def dirty_height_patch(
        self,
        region: MapStudioTerrainSculptDirtyRegion | None = None,
    ) -> tuple[tuple[float, ...], ...]:
        """Copy only a dirty rectangle for a partial viewport buffer update."""

        target = region or self.dirty_region_with_halo
        if target.empty:
            return ()
        return tuple(
            tuple(
                float(self._heights[(row * self.column_count) + column])
                for column in range(target.min_column, target.max_column + 1)
            )
            for row in range(target.min_row, target.max_row + 1)
        )

    def _height_rows(self) -> tuple[tuple[float, ...], ...]:
        return tuple(
            tuple(self._heights[row * self.column_count : (row + 1) * self.column_count])
            for row in range(self.row_count)
        )

    def commit(self) -> MapStudioTerrainSculptCommitResult:
        """Commit the stroke once, including exactly one authored payload encode."""

        if self._commit_result is not None:
            return self._commit_result
        self._ensure_active()
        started = perf_counter()
        rows = self._height_rows()
        preview = replace(self.source_primitive, heights=rows)
        slope_report = analyse_terrain_slopes(preview)
        dirty = self.dirty_region
        halo = self.dirty_region_with_halo
        options = dict(self._last_options)
        last_frame = self._last_frame
        last_performance = last_frame.performance.to_metadata() if last_frame is not None else {}
        primitive = replace(
            preview,
            metadata={
                **dict(self.source_primitive.metadata),
                "last_operation": "terrain_brush_stroke",
                "last_brush": str(last_frame.brush if last_frame is not None else ""),
                "last_brush_radius": int(options.get("radius", 0)),
                "last_brush_delta": float(options.get("delta", 0.0)),
                "last_brush_height": float(options.get("height", 0.0)),
                "last_brush_strength": float(options.get("strength", 0.5)),
                "last_brush_falloff_hardness": float(options.get("falloff_hardness", 0.5)),
                "last_brush_symmetry_axis": str(options.get("symmetry_axis", "")),
                "last_brush_slope_report": {
                    "max_slope_degrees": float(slope_report.max_slope_degrees),
                    "walkable_triangle_count": int(slope_report.walkable_triangle_count),
                    "non_walk_triangle_count": int(slope_report.non_walk_triangle_count),
                    "warnings": list(slope_report.warnings),
                },
                "last_stroke_frame_count": int(self.frame_count),
                "last_dirty_region": dirty.to_metadata(),
                "last_dirty_region_with_halo": halo.to_metadata(),
                "last_changed_sample_count": int(dirty.changed_sample_count),
                "last_brush_performance": last_performance,
                "defer_full_rebuild_until_stroke_end": True,
                "full_rebuild_deferred_until_commit": True,
                "terrain_stroke_committed": True,
                "dirty_region_only": True,
                "source": "map_studio:terrain_sculpt_stroke_session",
            },
        )
        source_room = self.project.rooms[self.room_index]
        room = replace(
            source_room,
            primitive=primitive,
            composition=None,
            metadata={
                **dict(source_room.metadata),
                "primitive": "terrain_heightfield",
                "last_operation": "terrain_brush_stroke",
            },
        )
        rooms = tuple(
            self.project.rooms[: self.room_index]
            + (room,)
            + self.project.rooms[self.room_index + 1 :]
        )
        # Keep the existing authored-terrain contract: actors and the entry
        # point are snapped to the final committed terrain, never per frame.
        from .authored_room_operations import _repair_placements_for_terrain

        placements = _repair_placements_for_terrain(
            self.project.placements,
            terrain=primitive,
            room=room,
            operation="terrain_brush_stroke",
        )
        project = replace(
            self.project,
            rooms=rooms,
            placements=placements,
            notes=tuple(self.project.notes) + ("Applied Map Studio room operation: terrain_brush_stroke.",),
            extra={
                **dict(self.project.extra),
                "last_room_operation": "terrain_brush_stroke",
                "terrain_sculpt_stroke": {
                    "room_resref": self.room_resref,
                    "frame_count": int(self.frame_count),
                    "dirty_region": dirty.to_metadata(),
                    "dirty_region_with_halo": halo.to_metadata(),
                },
            },
        )
        from .authored_module_kmap_bridge import authored_project_to_kmap_payload

        serialization_started = perf_counter()
        payload = authored_project_to_kmap_payload(project)
        serialization_elapsed_ms = (perf_counter() - serialization_started) * 1000.0
        self.serialization_count += 1
        result = MapStudioTerrainSculptCommitResult(
            project=project,
            primitive=primitive,
            payload=payload,
            dirty_region=dirty,
            dirty_region_with_halo=halo,
            frame_count=self.frame_count,
            decode_count=self.decode_count,
            serialization_count=self.serialization_count,
            commit_elapsed_ms=(perf_counter() - started) * 1000.0,
            serialization_elapsed_ms=serialization_elapsed_ms,
        )
        self._commit_result = result
        return result

    def cancel(self) -> AuthoredModuleProject:
        """Discard the mutable buffer without serializing or changing project state."""

        self._ensure_active()
        self._cancelled = True
        return self.project


def begin_terrain_sculpt_stroke(
    source: AuthoredModuleProject | Any,
    *,
    room_resref: str,
    fallback_name: str = "new_level",
    fallback_game: str = "K1",
) -> MapStudioTerrainSculptStrokeSession:
    """Compatibility-friendly entry point for decoded projects or KMAP payloads."""

    if isinstance(source, AuthoredModuleProject):
        return MapStudioTerrainSculptStrokeSession.from_project(source, room_resref=room_resref)
    return MapStudioTerrainSculptStrokeSession.from_kmap_payload(
        source,
        room_resref=room_resref,
        fallback_name=fallback_name,
        fallback_game=fallback_game,
    )


def normalise_terrain_sculpt_points(
    points: tuple[TerrainBrushStrokePoint | tuple[int, int] | tuple[int, int, float], ...] | list[Any],
) -> tuple[TerrainBrushStrokePoint, ...]:
    """Normalize UI pointer samples into terrain stroke points."""

    result: list[TerrainBrushStrokePoint] = []
    for item in tuple(points or ()):
        if isinstance(item, TerrainBrushStrokePoint):
            result.append(item)
            continue
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            strength = float(item[2]) if len(item) >= 3 else 1.0
            result.append(TerrainBrushStrokePoint(int(item[0]), int(item[1]), strength))
    if not result:
        raise ValueError("Map Studio terrain sculpt frame requires at least one pointer sample.")
    return tuple(result)


def interpolate_terrain_sculpt_segment(
    start: TerrainBrushStrokePoint | tuple[int, int] | tuple[int, int, float] | list[Any] | None,
    end: TerrainBrushStrokePoint | tuple[int, int] | tuple[int, int, float] | list[Any],
    *,
    include_start: bool = False,
) -> tuple[TerrainBrushStrokePoint, ...]:
    """Fill every integer heightfield sample crossed by one pointer segment.

    Viewport mouse events are not guaranteed to land in adjacent terrain
    cells.  Interpolating in the headless session layer prevents fast strokes
    from leaving dotted gaps and keeps the same deterministic samples for
    undo, tests, and future tablet input.
    """

    end_point = normalise_terrain_sculpt_points((end,))[0]
    if start is None:
        return (end_point,)
    start_point = normalise_terrain_sculpt_points((start,))[0]
    row_delta = int(end_point.row_index) - int(start_point.row_index)
    column_delta = int(end_point.column_index) - int(start_point.column_index)
    step_count = max(abs(row_delta), abs(column_delta))
    if step_count <= 0:
        return (end_point,) if include_start else ()
    first_step = 0 if include_start else 1
    result: list[TerrainBrushStrokePoint] = []
    seen: set[tuple[int, int]] = set()
    for step in range(first_step, step_count + 1):
        amount = float(step) / float(step_count)
        row = int(round(float(start_point.row_index) + (float(row_delta) * amount)))
        column = int(round(float(start_point.column_index) + (float(column_delta) * amount)))
        key = (row, column)
        if key in seen:
            continue
        seen.add(key)
        point_strength = float(start_point.strength) + (
            (float(end_point.strength) - float(start_point.strength)) * amount
        )
        result.append(TerrainBrushStrokePoint(row, column, point_strength))
    return tuple(result)


def terrain_sculpt_brush_is_deferred(brush: str) -> bool:
    """Return whether a brush needs the complete press-to-release gesture."""

    return str(brush or "").strip().lower() in DEFERRED_TERRAIN_SCULPT_BRUSHES


def coalesce_terrain_sculpt_points(
    points: tuple[TerrainBrushStrokePoint | tuple[int, int] | tuple[int, int, float], ...] | list[Any],
    *,
    max_points_per_frame: int = 8,
) -> tuple[TerrainBrushStrokePoint, ...]:
    """Reduce high-frequency pointer samples to a deterministic per-frame batch."""

    normalized = normalise_terrain_sculpt_points(points)
    latest_by_sample: dict[tuple[int, int], TerrainBrushStrokePoint] = {}
    ordered_keys: list[tuple[int, int]] = []
    for point in normalized:
        key = (int(point.row_index), int(point.column_index))
        if key not in latest_by_sample:
            ordered_keys.append(key)
        latest_by_sample[key] = point
    unique_points = tuple(latest_by_sample[key] for key in ordered_keys)
    limit = max(1, int(max_points_per_frame))
    if len(unique_points) <= limit:
        return unique_points
    if limit == 1:
        return (unique_points[-1],)
    last_index = len(unique_points) - 1
    selected_indices = {
        round((last_index * index) / float(limit - 1))
        for index in range(limit)
    }
    selected_indices.add(last_index)
    return tuple(unique_points[index] for index in sorted(selected_indices)[-limit:])


def terrain_sculpt_primitive_for_project(project: AuthoredModuleProject, *, room_resref: str) -> TerrainHeightfieldPrimitive:
    """Return the terrain primitive targeted by a live sculpt frame."""

    wanted = normalise_resref(room_resref)
    if not project.rooms:
        raise ValueError("Map Studio terrain sculpting requires an authored terrain room.")
    for room in tuple(project.rooms or ()):
        if wanted and normalise_resref(room.room_resref) != wanted:
            continue
        if isinstance(room.primitive, TerrainHeightfieldPrimitive):
            return room.primitive
    label = room_resref or "first authored room"
    raise ValueError(f"Map Studio terrain sculpting could not find editable terrain room '{label}'.")


def prepare_terrain_sculpt_frame(
    primitive: TerrainHeightfieldPrimitive,
    *,
    room_resref: str = "",
    brush: str,
    points: tuple[TerrainBrushStrokePoint | tuple[int, int] | tuple[int, int, float], ...] | list[Any],
    delta: float = 0.1,
    radius: int = 0,
    height: float = 0.0,
    iterations: int = 1,
    strength: float = 0.5,
    falloff_hardness: float = 0.5,
    preserve_boundary: bool = True,
    max_points_per_frame: int = 8,
    budget_ms: float = 8.0,
) -> MapStudioTerrainSculptFrame:
    """Build a live terrain sculpt frame without mutating the authored module."""

    raw_points = normalise_terrain_sculpt_points(points)
    coalesced = coalesce_terrain_sculpt_points(raw_points, max_points_per_frame=max_points_per_frame)
    brush_key = str(brush or "raise").strip().lower() or "raise"
    performance = audit_terrain_brush_stroke_interaction(
        primitive,
        points=coalesced,
        radius=int(radius),
        brush=brush_key,
        iterations=int(iterations),
        budget_ms=float(budget_ms),
        falloff_hardness=float(falloff_hardness),
    )
    warnings = list(performance.warnings)
    if len(coalesced) < len(raw_points):
        warnings.append(
            f"Coalesced {len(raw_points)} raw pointer sample(s) into {len(coalesced)} terrain point(s) for this frame."
        )
    return MapStudioTerrainSculptFrame(
        room_resref=normalise_resref(room_resref or primitive.room_resref),
        brush=brush_key,
        raw_sample_count=len(raw_points),
        applied_sample_count=len(coalesced),
        coalesced_sample_count=max(0, len(raw_points) - len(coalesced)),
        points=coalesced,
        operation=f"brush_stroke:{brush_key}",
        operation_kwargs={
            "room_resref": normalise_resref(room_resref or primitive.room_resref),
            "points": tuple((point.row_index, point.column_index, point.strength) for point in coalesced),
            "delta": float(delta),
            "radius": int(radius),
            "height": float(height),
            "iterations": int(iterations),
            "strength": float(strength),
            "falloff_hardness": float(falloff_hardness),
            "preserve_boundary": bool(preserve_boundary),
        },
        performance=performance,
        should_apply_live=bool(performance.within_budget),
        warnings=tuple(warnings),
    )


def prepare_terrain_sculpt_frame_for_project(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    brush: str,
    points: tuple[TerrainBrushStrokePoint | tuple[int, int] | tuple[int, int, float], ...] | list[Any],
    delta: float = 0.1,
    radius: int = 0,
    height: float = 0.0,
    iterations: int = 1,
    strength: float = 0.5,
    falloff_hardness: float = 0.5,
    preserve_boundary: bool = True,
    max_points_per_frame: int = 8,
    budget_ms: float = 8.0,
) -> MapStudioTerrainSculptFrame:
    """Build a live terrain sculpt frame for an authored project."""

    primitive = terrain_sculpt_primitive_for_project(project, room_resref=room_resref)
    return prepare_terrain_sculpt_frame(
        primitive,
        room_resref=room_resref or primitive.room_resref,
        brush=brush,
        points=points,
        delta=delta,
        radius=radius,
        height=height,
        iterations=iterations,
        strength=strength,
        falloff_hardness=falloff_hardness,
        preserve_boundary=preserve_boundary,
        max_points_per_frame=max_points_per_frame,
        budget_ms=budget_ms,
    )


__all__ = [
    "MapStudioTerrainSculptApplyResult",
    "MapStudioTerrainSculptCommitResult",
    "MapStudioTerrainSculptDirtyRegion",
    "MapStudioTerrainSculptFrame",
    "MapStudioTerrainSculptStrokeFrameResult",
    "MapStudioTerrainSculptStrokeSession",
    "DEFERRED_TERRAIN_SCULPT_BRUSHES",
    "begin_terrain_sculpt_stroke",
    "coalesce_terrain_sculpt_points",
    "interpolate_terrain_sculpt_segment",
    "normalise_terrain_sculpt_points",
    "prepare_terrain_sculpt_frame",
    "prepare_terrain_sculpt_frame_for_project",
    "terrain_sculpt_primitive_for_project",
    "terrain_sculpt_brush_is_deferred",
]
