"""Headless Universal Manipulator overlay geometry for Map Studio.

The Level Editor viewport can draw this data, but the bounds, handles, labels,
and coordinate-space contract live in core so the UI does not become the owner
of transform math or KMAP export-readiness policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class MapStudioUniversalTransformLine:
    """One world-space line segment in the Universal Manipulator overlay."""

    key: str
    role: str
    start: Vec3
    end: Vec3
    color: str = "#00e5ff"
    label: str = ""


@dataclass(frozen=True)
class MapStudioUniversalTransformHandle:
    """One world-space control handle for the selected authored primitive."""

    key: str
    label: str
    role: str
    position: Vec3
    axis: str = ""
    color: str = "#00ff7a"


@dataclass(frozen=True)
class MapStudioUniversalTransformDimensionLabel:
    """One exact dimension label for the selected authored primitive."""

    key: str
    label: str
    axis: str
    value: float
    start: Vec3
    end: Vec3
    midpoint: Vec3
    unit: str = "m"
    color: str = "#ffd84a"


@dataclass(frozen=True)
class MapStudioUniversalTransformOverlay:
    """Viewport-ready overlay for Ctrl+T / Universal Manipulator."""

    room_resref: str
    primitive_name: str
    primitive_type: str
    coordinate_space: str
    bounds_min: Vec3
    bounds_max: Vec3
    center: Vec3
    dimensions: Vec3
    corner_points: tuple[Vec3, ...]
    edge_lines: tuple[MapStudioUniversalTransformLine, ...]
    handles: tuple[MapStudioUniversalTransformHandle, ...]
    dimension_labels: tuple[MapStudioUniversalTransformDimensionLabel, ...]
    vertex_count: int
    face_count: int
    committed_edit_stale_outputs: tuple[str, ...]
    readiness_impact: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _vec3(value: Any, *, fallback: Vec3 = (0.0, 0.0, 0.0)) -> Vec3:
    try:
        x, y, z = value
        return (float(x), float(y), float(z))
    except Exception:
        return fallback


def _midpoint(start: Vec3, end: Vec3) -> Vec3:
    return (
        (float(start[0]) + float(end[0])) * 0.5,
        (float(start[1]) + float(end[1])) * 0.5,
        (float(start[2]) + float(end[2])) * 0.5,
    )


def _bbox_corners(bounds_min: Vec3, bounds_max: Vec3) -> tuple[Vec3, ...]:
    x0, y0, z0 = bounds_min
    x1, y1, z1 = bounds_max
    return (
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    )


def _bbox_edges(corners: tuple[Vec3, ...]) -> tuple[MapStudioUniversalTransformLine, ...]:
    edge_indices = (
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    )
    return tuple(
        MapStudioUniversalTransformLine(
            key=f"bbox_edge_{index:02d}",
            role="bounds",
            start=corners[first],
            end=corners[second],
        )
        for index, (first, second) in enumerate(edge_indices)
    )


def _dimension_label(
    *,
    key: str,
    label: str,
    axis: str,
    value: float,
    start: Vec3,
    end: Vec3,
) -> MapStudioUniversalTransformDimensionLabel:
    return MapStudioUniversalTransformDimensionLabel(
        key=key,
        label=f"{label} {float(value):.3f} m",
        axis=axis,
        value=float(value),
        start=start,
        end=end,
        midpoint=_midpoint(start, end),
    )


def _dimension_labels(bounds_min: Vec3, bounds_max: Vec3, dimensions: Vec3) -> tuple[MapStudioUniversalTransformDimensionLabel, ...]:
    x0, y0, z0 = bounds_min
    x1, y1, z1 = bounds_max
    max_dimension = max(float(dimensions[0]), float(dimensions[1]), float(dimensions[2]), 1.0)
    offset = max(0.15, max_dimension * 0.08)
    return (
        _dimension_label(
            key="width",
            label="W",
            axis="x",
            value=dimensions[0],
            start=(x0, y0 - offset, z0),
            end=(x1, y0 - offset, z0),
        ),
        _dimension_label(
            key="depth",
            label="D",
            axis="y",
            value=dimensions[1],
            start=(x1 + offset, y0, z0),
            end=(x1 + offset, y1, z0),
        ),
        _dimension_label(
            key="height",
            label="H",
            axis="z",
            value=dimensions[2],
            start=(x1 + offset, y1 + offset, z0),
            end=(x1 + offset, y1 + offset, z1),
        ),
    )


def _handles(bounds_min: Vec3, bounds_max: Vec3, center: Vec3, dimensions: Vec3) -> tuple[MapStudioUniversalTransformHandle, ...]:
    x0, y0, z0 = bounds_min
    x1, y1, z1 = bounds_max
    cx, cy, cz = center
    max_dimension = max(float(dimensions[0]), float(dimensions[1]), float(dimensions[2]), 1.0)
    offset = max(0.25, max_dimension * 0.18)
    return (
        MapStudioUniversalTransformHandle(
            key="center",
            label="Move",
            role="translate",
            position=center,
            color="#00ff7a",
        ),
        MapStudioUniversalTransformHandle(
            key="axis_x",
            label="X",
            role="axis_translate",
            axis="x",
            position=(x1 + offset, cy, cz),
            color="#ff4d4d",
        ),
        MapStudioUniversalTransformHandle(
            key="axis_y",
            label="Y",
            role="axis_translate",
            axis="y",
            position=(cx, y1 + offset, cz),
            color="#43d17a",
        ),
        MapStudioUniversalTransformHandle(
            key="axis_z",
            label="Z",
            role="axis_translate",
            axis="z",
            position=(cx, cy, z1 + offset),
            color="#58a6ff",
        ),
        MapStudioUniversalTransformHandle(
            key="scale_min",
            label="Scale",
            role="corner_scale",
            position=(x0, y0, z0),
            color="#ffd84a",
        ),
        MapStudioUniversalTransformHandle(
            key="scale_max",
            label="Scale",
            role="corner_scale",
            position=(x1, y1, z1),
            color="#ffd84a",
        ),
    )


def build_map_studio_universal_transform_overlay(selection: Any) -> MapStudioUniversalTransformOverlay:
    """Build a viewport-ready overlay from a selected primitive bounds query."""

    bounds_min = _vec3(getattr(selection, "bounds_min", ()))
    bounds_max = _vec3(getattr(selection, "bounds_max", ()))
    center = _vec3(getattr(selection, "center", ()))
    dimensions = _vec3(getattr(selection, "dimensions", ()))
    corners = _bbox_corners(bounds_min, bounds_max)
    metadata = dict(getattr(selection, "metadata", {}) or {})
    metadata.update(
        {
            "source": "map_studio:universal_transform_overlay",
            "capability_stage": "previewable_overlay",
            "coordinate_space": str(getattr(selection, "coordinate_space", "") or "kmap_world"),
            "live_edit_policy": "query_only_until_transform_or_dimension_commit",
        }
    )
    return MapStudioUniversalTransformOverlay(
        room_resref=str(getattr(selection, "room_resref", "") or ""),
        primitive_name=str(getattr(selection, "primitive_name", "") or ""),
        primitive_type=str(getattr(selection, "primitive_type", "") or ""),
        coordinate_space=str(getattr(selection, "coordinate_space", "") or "kmap_world"),
        bounds_min=bounds_min,
        bounds_max=bounds_max,
        center=center,
        dimensions=dimensions,
        corner_points=corners,
        edge_lines=_bbox_edges(corners),
        handles=_handles(bounds_min, bounds_max, center, dimensions),
        dimension_labels=_dimension_labels(bounds_min, bounds_max, dimensions),
        vertex_count=int(getattr(selection, "vertex_count", 0) or 0),
        face_count=int(getattr(selection, "face_count", 0) or 0),
        committed_edit_stale_outputs=tuple(getattr(selection, "committed_edit_stale_outputs", ()) or ()),
        readiness_impact=str(getattr(selection, "readiness_impact", "") or ""),
        metadata=metadata,
    )


__all__ = [
    "MapStudioUniversalTransformDimensionLabel",
    "MapStudioUniversalTransformHandle",
    "MapStudioUniversalTransformLine",
    "MapStudioUniversalTransformOverlay",
    "build_map_studio_universal_transform_overlay",
]
