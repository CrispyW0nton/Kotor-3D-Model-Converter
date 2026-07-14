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
    color_role: str = ""
    warning: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


_MARKER_STYLE: dict[str, tuple[str, str, float, float]] = {
    # IFO player start: editor-only semantic marker with a facing arrow.  It
    # is deliberately part of the preview contract even though it is not a
    # GIT placement row; otherwise a correctly hydrated stock module appears
    # to have no spawn point anywhere in the viewport.
    "entry_point": ("player_start", "#37f58d", 0.35, 1.8),
    "creature": ("diamond", "#ff5c5c", 0.35, 1.7),
    "placeable": ("cube", "#ffd34d", 0.45, 0.9),
    "door": ("doorway", "#42d9ff", 0.65, 2.2),
    "waypoint": ("flag", "#52ff7a", 0.25, 1.2),
    "trigger": ("volume", "#d46bff", 0.8, 0.15),
    "encounter": ("encounter", "#ff8a3d", 0.8, 0.2),
    # Sounds are editor-only billboards, never fake scene geometry.  The
    # viewport draws this semantic shape as an Unreal-style speaker icon.
    "sound": ("speaker", "#6fa8ff", 0.5, 0.0),
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
        color_role="info" if kind == "sound" else "",
        warning=warning,
        metadata={
            "source": "authored_gameplay_placement_rows",
            "index": int(row.index),
            "marker_shape": shape,
            "marker_icon": "speaker" if kind == "sound" else "",
            "runtime_kind": kind,
            "transition_capable": bool(getattr(row, "transition_capable", False)),
            "transition_status": transition_status,
            "transition_summary": transition_summary,
            "linked_to": str(getattr(row, "linked_to", "") or ""),
            "linked_to_module": str(getattr(row, "linked_to_module", "") or ""),
            "linked_to_flags": int(getattr(row, "linked_to_flags", 0) or 0),
            "transition_destination": int(getattr(row, "transition_destination", 0) or 0),
        },
    )


def authored_module_entry_point_preview_marker(
    project: AuthoredModuleProject,
) -> AuthoredGameplayPlacementPreviewMarker:
    """Return the editor marker for the IFO player start.

    The entry point is not a GIT placement row, so it intentionally stays out
    of :func:`authored_gameplay_preview_markers`.  Viewport fallback composition
    appends it separately while existing placement-only callers keep their
    stable row/marker cardinality.
    """

    entry = project.placements.entry_point
    entry_position = _vec3(entry.position)
    entry_facing = float(entry.facing or 0.0)
    shape, color, radius, height = _MARKER_STYLE["entry_point"]
    return AuthoredGameplayPlacementPreviewMarker(
        placement_id="entry_point",
        kind="entry_point",
        label=f"Player Start ({str(entry.area_resref or project.metadata.module_root)})",
        template_resref="",
        position=entry_position,
        bearing=entry_facing,
        forward_endpoint=_forward_endpoint(entry_position, entry_facing, radius),
        shape=shape,
        color=color,
        radius=radius,
        height=height,
        color_role="success",
        warning="" if str(entry.area_resref or "").strip() else "Player start has no entry-area resref.",
        metadata={
            "source": "authored_module_ifo_entry_point",
            "runtime_kind": "entry_point",
            "area_resref": str(entry.area_resref or ""),
            "marker_shape": shape,
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
    "authored_module_entry_point_preview_marker",
]
