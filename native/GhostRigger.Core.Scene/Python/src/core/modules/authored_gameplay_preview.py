"""Preview markers for authored Map Studio gameplay placements."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .authored_module_placements import AuthoredGameplayPlacementRow, authored_gameplay_placement_rows
from .authored_module_project import AuthoredModuleProject


Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class AuthoredGameplayPlacementPreviewMarker:
    """UI-ready marker data for one spatial authored gameplay placement."""

    placement_id: str
    kind: str
    label: str
    template_resref: str
    position: Vec3
    bearing: float
    forward_endpoint: Vec3
    shape: str
    color: str
    radius: float
    height: float = 0.0
    warning: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


_MARKER_STYLE: dict[str, tuple[str, str, float, float]] = {
    "creature": ("diamond", "#ff5c5c", 0.35, 1.7),
    "placeable": ("cube", "#ffd34d", 0.45, 0.9),
    "door": ("doorway", "#42d9ff", 0.65, 2.2),
    "waypoint": ("flag", "#52ff7a", 0.25, 1.2),
    "trigger": ("volume", "#d46bff", 0.8, 0.15),
    "encounter": ("encounter", "#ff8a3d", 0.8, 0.2),
    "sound": ("sphere", "#6fa8ff", 0.5, 0.5),
    "camera": ("camera", "#c18cff", 0.3, 0.3),
}


def _vec3(value: Any) -> Vec3:
    if isinstance(value, dict):
        value = (value.get("x"), value.get("y"), value.get("z"))
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    return (0.0, 0.0, 0.0)


def _forward_endpoint(position: Vec3, bearing: float, radius: float) -> Vec3:
    length = max(float(radius) * 1.5, 0.35)
    return (
        float(position[0]) + math.cos(float(bearing)) * length,
        float(position[1]) + math.sin(float(bearing)) * length,
        float(position[2]),
    )


def authored_gameplay_preview_marker_for_row(
    row: AuthoredGameplayPlacementRow,
) -> AuthoredGameplayPlacementPreviewMarker | None:
    """Return a marker for a selectable authored placement row."""

    if not bool(getattr(row, "is_spatial", True)):
        return None
    kind = str(row.kind or "").strip().lower()
    if kind not in _MARKER_STYLE:
        return None
    shape, color, radius, height = _MARKER_STYLE[kind]
    position = _vec3(row.position)
    label = str(row.tag or row.template_resref or row.placement_id)
    warning = ""
    if kind == "trigger":
        warning = "Trigger footprint is shown as an approximate volume until polygon editing is exposed."
    transition_status = str(getattr(row, "transition_status", "") or "")
    transition_summary = str(getattr(row, "transition_summary", "") or "")
    return AuthoredGameplayPlacementPreviewMarker(
        placement_id=str(row.placement_id),
        kind=kind,
        label=label,
        template_resref=str(row.template_resref or ""),
        position=position,
        bearing=float(row.bearing or 0.0),
        forward_endpoint=_forward_endpoint(position, float(row.bearing or 0.0), radius),
        shape=shape,
        color=color,
        radius=radius,
        height=height,
        warning=warning,
        metadata={
            "source": "authored_gameplay_placement_rows",
            "index": int(row.index),
            "marker_shape": shape,
            "runtime_kind": kind,
            "transition_capable": bool(getattr(row, "transition_capable", False)),
            "transition_status": transition_status,
            "transition_summary": transition_summary,
            "linked_to": str(getattr(row, "linked_to", "") or ""),
            "linked_to_module": str(getattr(row, "linked_to_module", "") or ""),
        },
    )


def authored_gameplay_preview_markers(
    project: AuthoredModuleProject,
) -> tuple[AuthoredGameplayPlacementPreviewMarker, ...]:
    """Return UI-ready markers for spatial authored gameplay placements."""

    markers = [
        marker
        for row in authored_gameplay_placement_rows(project)
        for marker in (authored_gameplay_preview_marker_for_row(row),)
        if marker is not None
    ]
    return tuple(markers)


__all__ = [
    "AuthoredGameplayPlacementPreviewMarker",
    "authored_gameplay_preview_marker_for_row",
    "authored_gameplay_preview_markers",
]
