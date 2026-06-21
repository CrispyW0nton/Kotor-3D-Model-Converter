"""Authored guide curves for Map Studio.

Curves are KMAP authoring guides, not KOTOR runtime curve objects.  They give
modders a durable path/road/ridge/planning curve that later tools can consume
for PTH, terrain, walkmesh, or room-shaping workflows while keeping export
capability honest.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any

from .authored_module_project import AuthoredModuleProject, normalise_resref


Vec3 = tuple[float, float, float]
CURVE_GUIDES_EXTRA_KEY = "map_studio_curve_guides"


@dataclass(frozen=True)
class MapStudioCurveGuide:
    """One KMAP-authored curve guide."""

    name: str
    purpose: str
    points: tuple[Vec3, ...]
    room_resref: str = ""
    coordinate_space: str = "kmap_world"
    length: float = 0.0
    bounds_min: Vec3 = (0.0, 0.0, 0.0)
    bounds_max: Vec3 = (0.0, 0.0, 0.0)
    metadata: dict[str, Any] = field(default_factory=dict)


def _float(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Curve guide {label} must be a finite number.") from exc
    if not math.isfinite(result):
        raise ValueError(f"Curve guide {label} must be finite.")
    return result


def _vec3(value: Any, index: int) -> Vec3:
    if isinstance(value, dict):
        value = (value.get("x"), value.get("y"), value.get("z", 0.0))
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise ValueError(f"Curve guide point {index} must contain at least X and Y.")
    z_value = value[2] if len(value) >= 3 else 0.0
    return (
        _float(value[0], f"point {index} X"),
        _float(value[1], f"point {index} Y"),
        _float(z_value, f"point {index} Z"),
    )


def _clean_points(points: Any) -> tuple[Vec3, ...]:
    if not isinstance(points, (list, tuple)):
        raise ValueError("Curve guide points must be a sequence of 2D/3D points.")
    cleaned = tuple(_vec3(point, index) for index, point in enumerate(points))
    if len(cleaned) < 2:
        raise ValueError("Curve guide requires at least two points.")
    length = _curve_length(cleaned)
    if length <= 0.0001:
        raise ValueError("Curve guide requires at least one non-zero segment.")
    return cleaned


def _curve_length(points: tuple[Vec3, ...]) -> float:
    length = 0.0
    for start, end in zip(points, points[1:]):
        length += math.dist(start, end)
    return float(length)


def _bounds(points: tuple[Vec3, ...]) -> tuple[Vec3, Vec3]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]
    return (
        (min(xs), min(ys), min(zs)),
        (max(xs), max(ys), max(zs)),
    )


def _guide_from_payload(payload: Any) -> MapStudioCurveGuide | None:
    if not isinstance(payload, dict):
        return None
    try:
        points = _clean_points(payload.get("points", ()))
    except ValueError:
        return None
    bounds_min, bounds_max = _bounds(points)
    length = _curve_length(points)
    return MapStudioCurveGuide(
        name=normalise_resref(payload.get("name") or "curve"),
        purpose=str(payload.get("purpose") or "path_guide").strip() or "path_guide",
        points=points,
        room_resref=normalise_resref(payload.get("room_resref") or ""),
        coordinate_space=str(payload.get("coordinate_space") or "kmap_world").strip() or "kmap_world",
        length=float(payload.get("length") or length),
        bounds_min=_vec3(payload.get("bounds_min") or bounds_min, 0),
        bounds_max=_vec3(payload.get("bounds_max") or bounds_max, 1),
        metadata=dict(payload.get("metadata") or {}),
    )


def _guide_payload(guide: MapStudioCurveGuide) -> dict[str, Any]:
    return {
        "name": guide.name,
        "purpose": guide.purpose,
        "room_resref": guide.room_resref,
        "coordinate_space": guide.coordinate_space,
        "points": [list(point) for point in guide.points],
        "length": float(guide.length),
        "bounds_min": list(guide.bounds_min),
        "bounds_max": list(guide.bounds_max),
        "metadata": dict(guide.metadata),
    }


def authored_curve_guides(project: AuthoredModuleProject) -> tuple[MapStudioCurveGuide, ...]:
    """Return valid authored curve guides stored in project extra metadata."""

    raw = dict(project.extra or {}).get(CURVE_GUIDES_EXTRA_KEY, ())
    guides: list[MapStudioCurveGuide] = []
    for payload in tuple(raw or ()):
        guide = _guide_from_payload(payload)
        if guide is not None:
            guides.append(guide)
    return tuple(guides)


def _unique_curve_name(existing: tuple[MapStudioCurveGuide, ...], requested: str) -> str:
    used = {guide.name for guide in existing}
    base = normalise_resref(requested) or "curve"
    if base not in used:
        return base
    for index in range(1, 1000):
        suffix = f"_{index:02d}"
        candidate = f"{base[: max(1, 16 - len(suffix))]}{suffix}"
        if candidate not in used:
            return candidate
    raise ValueError("Could not allocate a unique curve guide name.")


def add_authored_curve_guide(
    project: AuthoredModuleProject,
    *,
    name: str = "",
    points: Any = (),
    purpose: str = "path_guide",
    room_resref: str = "",
    coordinate_space: str = "kmap_world",
    metadata: dict[str, Any] | None = None,
) -> AuthoredModuleProject:
    """Append one KOTOR-aware authoring curve guide to a Map Studio project."""

    cleaned_points = _clean_points(points)
    length = _curve_length(cleaned_points)
    bounds_min, bounds_max = _bounds(cleaned_points)
    existing = authored_curve_guides(project)
    clean_purpose = str(purpose or "path_guide").strip().lower().replace(" ", "_") or "path_guide"
    clean_space = str(coordinate_space or "kmap_world").strip() or "kmap_world"
    guide = MapStudioCurveGuide(
        name=_unique_curve_name(existing, name or clean_purpose),
        purpose=clean_purpose,
        points=cleaned_points,
        room_resref=normalise_resref(room_resref),
        coordinate_space=clean_space,
        length=length,
        bounds_min=bounds_min,
        bounds_max=bounds_max,
        metadata={
            "source": "map_studio:curve_tool",
            "capability_stage": "preview_guide",
            "export_state": "guide_only_not_runtime_geometry",
            "point_count": len(cleaned_points),
            "segment_count": max(0, len(cleaned_points) - 1),
            "validation": "finite_nonzero_polyline",
            **dict(metadata or {}),
        },
    )
    extra = dict(project.extra or {})
    extra[CURVE_GUIDES_EXTRA_KEY] = [_guide_payload(item) for item in (*existing, guide)]
    extra["last_curve_guide"] = guide.name
    extra["last_map_studio_operation"] = "curve_guide"
    return replace(project, extra=extra)


__all__ = [
    "CURVE_GUIDES_EXTRA_KEY",
    "MapStudioCurveGuide",
    "add_authored_curve_guide",
    "authored_curve_guides",
]
