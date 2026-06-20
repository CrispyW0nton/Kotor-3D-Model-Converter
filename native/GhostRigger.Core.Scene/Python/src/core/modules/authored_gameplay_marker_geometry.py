"""Renderable geometry contract for authored Map Studio gameplay markers."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .authored_gameplay_preview import AuthoredGameplayPlacementPreviewMarker, authored_gameplay_preview_markers
from .authored_module_project import AuthoredModuleProject


Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class AuthoredGameplayMarkerLine:
    """One world-space guide line for a placement marker overlay."""

    placement_id: str
    kind: str
    label: str
    start: Vec3
    end: Vec3
    color: str
    role: str


@dataclass(frozen=True)
class AuthoredGameplayMarkerFootprint:
    """One floor footprint for a spatial authored gameplay placement."""

    placement_id: str
    kind: str
    label: str
    points: tuple[Vec3, ...]
    color: str
    role: str = "footprint"


@dataclass(frozen=True)
class AuthoredGameplayMarkerGeometry:
    """UI/renderer-ready authored placement marker geometry."""

    marker_count: int = 0
    lines: tuple[AuthoredGameplayMarkerLine, ...] = ()
    footprints: tuple[AuthoredGameplayMarkerFootprint, ...] = ()
    warnings: tuple[str, ...] = ()


def _footprint_points(marker: AuthoredGameplayPlacementPreviewMarker) -> tuple[Vec3, ...]:
    radius = max(float(marker.radius or 0.0), 0.05)
    x, y, z = marker.position
    bearing = float(marker.bearing or 0.0)
    forward = (math.cos(bearing), math.sin(bearing))
    side = (-forward[1], forward[0])
    corners = (
        (-1.0, -1.0),
        (1.0, -1.0),
        (1.0, 1.0),
        (-1.0, 1.0),
    )
    return tuple(
        (
            x + ((forward[0] * fx) + (side[0] * sx)) * radius,
            y + ((forward[1] * fx) + (side[1] * sx)) * radius,
            z,
        )
        for fx, sx in corners
    )


def authored_gameplay_marker_geometry(
    markers: tuple[AuthoredGameplayPlacementPreviewMarker, ...] | list[AuthoredGameplayPlacementPreviewMarker],
) -> AuthoredGameplayMarkerGeometry:
    """Build footprint, facing, and height guide geometry for placement markers."""

    marker_tuple = tuple(markers or ())
    lines: list[AuthoredGameplayMarkerLine] = []
    footprints: list[AuthoredGameplayMarkerFootprint] = []
    warnings: list[str] = []
    for marker in marker_tuple:
        footprints.append(
            AuthoredGameplayMarkerFootprint(
                placement_id=marker.placement_id,
                kind=marker.kind,
                label=marker.label,
                points=_footprint_points(marker),
                color=marker.color,
            )
        )
        lines.append(
            AuthoredGameplayMarkerLine(
                placement_id=marker.placement_id,
                kind=marker.kind,
                label=marker.label,
                start=marker.position,
                end=marker.forward_endpoint,
                color=marker.color,
                role="facing",
            )
        )
        if float(marker.height or 0.0) > 0.0:
            x, y, z = marker.position
            lines.append(
                AuthoredGameplayMarkerLine(
                    placement_id=marker.placement_id,
                    kind=marker.kind,
                    label=marker.label,
                    start=marker.position,
                    end=(x, y, z + float(marker.height)),
                    color=marker.color,
                    role="height",
                )
            )
        if marker.warning:
            warnings.append(f"{marker.label}: {marker.warning}")
    return AuthoredGameplayMarkerGeometry(
        marker_count=len(marker_tuple),
        lines=tuple(lines),
        footprints=tuple(footprints),
        warnings=tuple(warnings),
    )


def authored_gameplay_marker_geometry_for_project(project: AuthoredModuleProject) -> AuthoredGameplayMarkerGeometry:
    """Return renderer-ready marker geometry for a full authored module project."""

    return authored_gameplay_marker_geometry(authored_gameplay_preview_markers(project))


__all__ = [
    "AuthoredGameplayMarkerFootprint",
    "AuthoredGameplayMarkerGeometry",
    "AuthoredGameplayMarkerLine",
    "authored_gameplay_marker_geometry",
    "authored_gameplay_marker_geometry_for_project",
]
