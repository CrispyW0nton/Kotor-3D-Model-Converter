"""Live terrain sculpt stroke contracts for Map Studio.

This module owns the headless interaction policy for terrain painting.  The UI
can feed many mouse/tablet samples into this layer and receive one coalesced
frame batch that is safe to apply without rebuilding the whole module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .authored_module_project import AuthoredModuleProject, normalise_resref
from .authored_terrain_builder import (
    TerrainBrushPerformanceAudit,
    TerrainBrushStrokePoint,
    TerrainHeightfieldPrimitive,
    audit_terrain_brush_stroke_interaction,
)


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
        preserve_boundary=preserve_boundary,
        max_points_per_frame=max_points_per_frame,
        budget_ms=budget_ms,
    )


__all__ = [
    "MapStudioTerrainSculptApplyResult",
    "MapStudioTerrainSculptFrame",
    "coalesce_terrain_sculpt_points",
    "normalise_terrain_sculpt_points",
    "prepare_terrain_sculpt_frame",
    "prepare_terrain_sculpt_frame_for_project",
    "terrain_sculpt_primitive_for_project",
]
