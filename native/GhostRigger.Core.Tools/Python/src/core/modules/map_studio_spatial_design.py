"""Purpose-led spatial design contracts for Map Studio.

The editor grid is more useful when it describes design intent instead of only
showing distance.  This module keeps a light, KMAP-serializable plan of named
zones, player circulation paths, landmarks, and deliberate object placements.
It is renderer and Qt independent so proof builders, validation, and the Map
Studio UI all reason from the same coordinates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Iterable

from .authored_gameplay_marker_geometry import (
    AuthoredGameplayMarkerFootprint,
    AuthoredGameplayMarkerGeometry,
    AuthoredGameplayMarkerLine,
)
from .authored_module_project import AuthoredModuleProject

SPATIAL_DESIGN_EXTRA_KEY = "map_studio_spatial_design"
SPATIAL_DESIGN_VERSION = 1
Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _vec2(value: Any) -> Vec2:
    values = tuple(value or ())
    return (_finite(values[0]) if len(values) > 0 else 0.0, _finite(values[1]) if len(values) > 1 else 0.0)


def _vec3(value: Any) -> Vec3:
    values = tuple(value or ())
    return (
        _finite(values[0]) if len(values) > 0 else 0.0,
        _finite(values[1]) if len(values) > 1 else 0.0,
        _finite(values[2]) if len(values) > 2 else 0.0,
    )


@dataclass(frozen=True)
class SpatialDesignZone:
    zone_id: str
    label: str
    purpose: str
    bounds: tuple[float, float, float, float]
    level_z: float = 0.0
    color: str = "#33d6c4"

    @classmethod
    def from_dict(cls, data: Any) -> "SpatialDesignZone":
        row = dict(data or {})
        raw_bounds = tuple(row.get("bounds") or ())
        bounds = tuple(_finite(raw_bounds[index]) if index < len(raw_bounds) else 0.0 for index in range(4))
        return cls(
            zone_id=_clean_text(row.get("zone_id")),
            label=_clean_text(row.get("label")),
            purpose=_clean_text(row.get("purpose")),
            bounds=bounds,
            level_z=_finite(row.get("level_z")),
            color=_clean_text(row.get("color")) or "#33d6c4",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "label": self.label,
            "purpose": self.purpose,
            "bounds": [float(value) for value in self.bounds],
            "level_z": float(self.level_z),
            "color": self.color,
        }


@dataclass(frozen=True)
class SpatialDesignPath:
    path_id: str
    label: str
    purpose: str
    points: tuple[Vec2, ...]
    width: float = 2.0
    level_z: float = 0.05
    color: str = "#8cf5df"

    @classmethod
    def from_dict(cls, data: Any) -> "SpatialDesignPath":
        row = dict(data or {})
        return cls(
            path_id=_clean_text(row.get("path_id")),
            label=_clean_text(row.get("label")),
            purpose=_clean_text(row.get("purpose")),
            points=tuple(_vec2(point) for point in tuple(row.get("points") or ())),
            width=max(0.0, _finite(row.get("width"), 2.0)),
            level_z=_finite(row.get("level_z"), 0.05),
            color=_clean_text(row.get("color")) or "#8cf5df",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_id": self.path_id,
            "label": self.label,
            "purpose": self.purpose,
            "points": [[float(value) for value in point] for point in self.points],
            "width": float(self.width),
            "level_z": float(self.level_z),
            "color": self.color,
        }


@dataclass(frozen=True)
class SpatialPlacementIntent:
    placement_id: str
    label: str
    asset_ref: str
    position: Vec3
    bearing: float
    zone_id: str
    purpose: str
    rationale: str
    footprint_radius: float = 0.5
    clearance_radius: float = 0.25
    landmark: bool = False
    allow_path_overlap: bool = False

    @classmethod
    def from_dict(cls, data: Any) -> "SpatialPlacementIntent":
        row = dict(data or {})
        return cls(
            placement_id=_clean_text(row.get("placement_id")),
            label=_clean_text(row.get("label")),
            asset_ref=_clean_text(row.get("asset_ref")),
            position=_vec3(row.get("position")),
            bearing=_finite(row.get("bearing")),
            zone_id=_clean_text(row.get("zone_id")),
            purpose=_clean_text(row.get("purpose")),
            rationale=_clean_text(row.get("rationale")),
            footprint_radius=max(0.0, _finite(row.get("footprint_radius"), 0.5)),
            clearance_radius=max(0.0, _finite(row.get("clearance_radius"), 0.25)),
            landmark=bool(row.get("landmark", False)),
            allow_path_overlap=bool(row.get("allow_path_overlap", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "placement_id": self.placement_id,
            "label": self.label,
            "asset_ref": self.asset_ref,
            "position": [float(value) for value in self.position],
            "bearing": float(self.bearing),
            "zone_id": self.zone_id,
            "purpose": self.purpose,
            "rationale": self.rationale,
            "footprint_radius": float(self.footprint_radius),
            "clearance_radius": float(self.clearance_radius),
            "landmark": bool(self.landmark),
            "allow_path_overlap": bool(self.allow_path_overlap),
        }


@dataclass(frozen=True)
class SpatialDesignPlan:
    name: str
    design_intent: str
    grid_size: float = 0.25
    player_clearance: float = 1.2
    zones: tuple[SpatialDesignZone, ...] = ()
    paths: tuple[SpatialDesignPath, ...] = ()
    placements: tuple[SpatialPlacementIntent, ...] = ()
    version: int = SPATIAL_DESIGN_VERSION

    @classmethod
    def from_dict(cls, data: Any) -> "SpatialDesignPlan":
        row = dict(data or {})
        return cls(
            name=_clean_text(row.get("name")),
            design_intent=_clean_text(row.get("design_intent")),
            grid_size=max(0.001, _finite(row.get("grid_size"), 0.25)),
            player_clearance=max(0.1, _finite(row.get("player_clearance"), 1.2)),
            zones=tuple(SpatialDesignZone.from_dict(item) for item in tuple(row.get("zones") or ())),
            paths=tuple(SpatialDesignPath.from_dict(item) for item in tuple(row.get("paths") or ())),
            placements=tuple(
                SpatialPlacementIntent.from_dict(item) for item in tuple(row.get("placements") or ())
            ),
            version=max(1, int(row.get("version", SPATIAL_DESIGN_VERSION) or SPATIAL_DESIGN_VERSION)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": int(self.version),
            "name": self.name,
            "design_intent": self.design_intent,
            "grid_size": float(self.grid_size),
            "player_clearance": float(self.player_clearance),
            "zones": [zone.to_dict() for zone in self.zones],
            "paths": [path.to_dict() for path in self.paths],
            "placements": [placement.to_dict() for placement in self.placements],
        }


@dataclass(frozen=True)
class SpatialDesignIssue:
    severity: str
    code: str
    subject_id: str
    message: str


@dataclass(frozen=True)
class SpatialDesignAudit:
    ok: bool
    issues: tuple[SpatialDesignIssue, ...] = ()
    zone_count: int = 0
    path_count: int = 0
    placement_count: int = 0
    purposeful_placement_count: int = 0
    landmark_count: int = 0

    @property
    def blocking_issues(self) -> tuple[str, ...]:
        return tuple(issue.message for issue in self.issues if issue.severity == "blocking")

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(issue.message for issue in self.issues if issue.severity == "warning")

    def summary(self) -> str:
        if self.ok:
            return (
                f"Spatial plan ready · {self.zone_count} zones · {self.path_count} routes · "
                f"{self.placement_count} purposeful placements"
            )
        return f"Spatial plan needs attention · {len(self.blocking_issues)} blocking issue(s)"


def read_authored_spatial_design(project: AuthoredModuleProject) -> SpatialDesignPlan | None:
    raw = dict(getattr(project, "extra", {}) or {}).get(SPATIAL_DESIGN_EXTRA_KEY)
    return SpatialDesignPlan.from_dict(raw) if isinstance(raw, dict) else None


def write_authored_spatial_design(
    project: AuthoredModuleProject,
    plan: SpatialDesignPlan | None,
) -> AuthoredModuleProject:
    extra = dict(getattr(project, "extra", {}) or {})
    if plan is None:
        extra.pop(SPATIAL_DESIGN_EXTRA_KEY, None)
    else:
        extra[SPATIAL_DESIGN_EXTRA_KEY] = plan.to_dict()
    return replace(project, extra=extra)


def _zone_contains(zone: SpatialDesignZone, placement: SpatialPlacementIntent) -> bool:
    x0, y0, x1, y1 = zone.bounds
    radius = placement.footprint_radius
    x, y, _z = placement.position
    return x0 + radius <= x <= x1 - radius and y0 + radius <= y <= y1 - radius


def _point_segment_distance(point: Vec2, start: Vec2, end: Vec2) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= 1.0e-12:
        return math.dist(point, start)
    amount = max(0.0, min(1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq))
    closest = (start[0] + dx * amount, start[1] + dy * amount)
    return math.dist(point, closest)


def _placement_intersects_path(placement: SpatialPlacementIntent, path: SpatialDesignPath) -> bool:
    required = path.width * 0.5 + placement.footprint_radius + placement.clearance_radius
    point = (placement.position[0], placement.position[1])
    return any(
        _point_segment_distance(point, start, end) < required
        for start, end in zip(path.points, path.points[1:])
    )


def _is_grid_aligned(value: float, grid_size: float) -> bool:
    snapped = round(float(value) / grid_size) * grid_size
    return abs(float(value) - snapped) <= max(1.0e-6, grid_size * 1.0e-5)


def audit_spatial_design(plan: SpatialDesignPlan | None) -> SpatialDesignAudit:
    if plan is None:
        issue = SpatialDesignIssue(
            "blocking",
            "missing_plan",
            "",
            "Create a spatial plan before calling the layout intentional.",
        )
        return SpatialDesignAudit(ok=False, issues=(issue,))

    issues: list[SpatialDesignIssue] = []
    if not plan.name or not plan.design_intent:
        issues.append(
            SpatialDesignIssue(
                "blocking",
                "missing_design_intent",
                "",
                "Name the map and state its player-facing design intent.",
            )
        )
    zone_by_id: dict[str, SpatialDesignZone] = {}
    for zone in plan.zones:
        if not zone.zone_id or zone.zone_id in zone_by_id:
            issues.append(
                SpatialDesignIssue("blocking", "invalid_zone_id", zone.zone_id, "Every spatial zone needs a unique ID.")
            )
            continue
        zone_by_id[zone.zone_id] = zone
        x0, y0, x1, y1 = zone.bounds
        if not zone.label or not zone.purpose or x1 <= x0 or y1 <= y0:
            issues.append(
                SpatialDesignIssue(
                    "blocking",
                    "invalid_zone",
                    zone.zone_id,
                    f"Zone {zone.label or zone.zone_id} needs a purpose and positive grid bounds.",
                )
            )

    path_ids: set[str] = set()
    for path in plan.paths:
        if not path.path_id or path.path_id in path_ids or len(path.points) < 2 or not path.purpose:
            issues.append(
                SpatialDesignIssue(
                    "blocking",
                    "invalid_path",
                    path.path_id,
                    f"Route {path.label or path.path_id or '(unnamed)'} needs a unique ID, purpose, and two points.",
                )
            )
        path_ids.add(path.path_id)
        if path.width < plan.player_clearance:
            issues.append(
                SpatialDesignIssue(
                    "blocking",
                    "narrow_path",
                    path.path_id,
                    f"Route {path.label or path.path_id} is {path.width:.2f} m wide; "
                    f"player clearance requires {plan.player_clearance:.2f} m.",
                )
            )

    purposeful = 0
    placement_ids: set[str] = set()
    for placement in plan.placements:
        if not placement.placement_id or placement.placement_id in placement_ids:
            issues.append(
                SpatialDesignIssue(
                    "blocking",
                    "invalid_placement_id",
                    placement.placement_id,
                    "Every planned placement needs a unique stable ID.",
                )
            )
        placement_ids.add(placement.placement_id)
        if not placement.label or not placement.asset_ref or not placement.purpose or not placement.rationale:
            issues.append(
                SpatialDesignIssue(
                    "blocking",
                    "unexplained_placement",
                    placement.placement_id,
                    f"Placement {placement.label or placement.placement_id} must name its asset, purpose, and reason for this location.",
                )
            )
        else:
            purposeful += 1
        zone = zone_by_id.get(placement.zone_id)
        if zone is None:
            issues.append(
                SpatialDesignIssue(
                    "blocking",
                    "unknown_zone",
                    placement.placement_id,
                    f"Placement {placement.label or placement.placement_id} is not assigned to a known zone.",
                )
            )
        elif not _zone_contains(zone, placement):
            issues.append(
                SpatialDesignIssue(
                    "blocking",
                    "outside_zone",
                    placement.placement_id,
                    f"Placement {placement.label} extends outside its {zone.label} zone.",
                )
            )
        if not _is_grid_aligned(placement.position[0], plan.grid_size) or not _is_grid_aligned(
            placement.position[1], plan.grid_size
        ):
            issues.append(
                SpatialDesignIssue(
                    "warning",
                    "off_grid",
                    placement.placement_id,
                    f"Placement {placement.label} is off the {plan.grid_size:.2f} m planning grid.",
                )
            )
        if not placement.allow_path_overlap:
            for path in plan.paths:
                if _placement_intersects_path(placement, path):
                    issues.append(
                        SpatialDesignIssue(
                            "blocking",
                            "blocks_route",
                            placement.placement_id,
                            f"Placement {placement.label} obstructs the {path.label} circulation route.",
                        )
                    )

    for index, first in enumerate(plan.placements):
        for second in plan.placements[index + 1 :]:
            required = (
                first.footprint_radius
                + first.clearance_radius
                + second.footprint_radius
                + second.clearance_radius
            )
            if math.dist(first.position[:2], second.position[:2]) < required:
                issues.append(
                    SpatialDesignIssue(
                        "blocking",
                        "placement_overlap",
                        first.placement_id,
                        f"Placements {first.label} and {second.label} overlap their usable clearances.",
                    )
                )

    landmark_count = sum(1 for placement in plan.placements if placement.landmark)
    if plan.zones and not landmark_count:
        issues.append(
            SpatialDesignIssue(
                "warning",
                "missing_landmark",
                "",
                "No landmark is identified; add one deliberate orientation anchor.",
            )
        )
    return SpatialDesignAudit(
        ok=not any(issue.severity == "blocking" for issue in issues),
        issues=tuple(issues),
        zone_count=len(plan.zones),
        path_count=len(plan.paths),
        placement_count=len(plan.placements),
        purposeful_placement_count=purposeful,
        landmark_count=landmark_count,
    )


def spatial_design_placement_ledger(plan: SpatialDesignPlan | None) -> tuple[dict[str, Any], ...]:
    if plan is None:
        return ()
    zone_labels = {zone.zone_id: zone.label for zone in plan.zones}
    return tuple(
        {
            "placement_id": placement.placement_id,
            "label": placement.label,
            "asset_ref": placement.asset_ref,
            "position": tuple(float(value) for value in placement.position),
            "bearing": float(placement.bearing),
            "zone_id": placement.zone_id,
            "zone": zone_labels.get(placement.zone_id, placement.zone_id),
            "purpose": placement.purpose,
            "rationale": placement.rationale,
            "landmark": bool(placement.landmark),
        }
        for placement in plan.placements
    )


def _rect_points(bounds: tuple[float, float, float, float], z: float) -> tuple[Vec3, ...]:
    x0, y0, x1, y1 = bounds
    return ((x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z))


def spatial_design_marker_geometry(plan: SpatialDesignPlan | None) -> AuthoredGameplayMarkerGeometry:
    if plan is None:
        return AuthoredGameplayMarkerGeometry()
    footprints: list[AuthoredGameplayMarkerFootprint] = []
    lines: list[AuthoredGameplayMarkerLine] = []
    for zone in plan.zones:
        footprints.append(
            AuthoredGameplayMarkerFootprint(
                placement_id=f"spatial:zone:{zone.zone_id}",
                kind="spatial_zone",
                label=f"{zone.label} · {zone.purpose}",
                points=_rect_points(zone.bounds, zone.level_z + 0.025),
                color=zone.color,
                role="spatial_zone",
            )
        )
    for path in plan.paths:
        for index, (start, end) in enumerate(zip(path.points, path.points[1:])):
            lines.append(
                AuthoredGameplayMarkerLine(
                    placement_id=f"spatial:path:{path.path_id}:{index}",
                    kind="spatial_path",
                    label=f"{path.label} · {path.purpose}",
                    start=(start[0], start[1], path.level_z),
                    end=(end[0], end[1], path.level_z),
                    color=path.color,
                    role="spatial_path",
                )
            )
    for placement in plan.placements:
        radius = max(placement.footprint_radius, 0.05)
        x, y, z = placement.position
        points = (
            (x - radius, y - radius, z + 0.03),
            (x + radius, y - radius, z + 0.03),
            (x + radius, y + radius, z + 0.03),
            (x - radius, y + radius, z + 0.03),
        )
        footprints.append(
            AuthoredGameplayMarkerFootprint(
                placement_id=f"spatial:placement:{placement.placement_id}",
                kind="spatial_landmark" if placement.landmark else "spatial_placement",
                label=f"{placement.label} · {placement.purpose}",
                points=points,
                color="#ffd166" if placement.landmark else "#9ce6d8",
                role="spatial_placement",
            )
        )
    audit = audit_spatial_design(plan)
    return AuthoredGameplayMarkerGeometry(
        marker_count=len(footprints) + len(lines),
        lines=tuple(lines),
        footprints=tuple(footprints),
        warnings=audit.blocking_issues + audit.warnings,
    )


def combine_marker_geometry(*layers: AuthoredGameplayMarkerGeometry | None) -> AuthoredGameplayMarkerGeometry:
    materialized = tuple(layer for layer in layers if layer is not None)
    return AuthoredGameplayMarkerGeometry(
        marker_count=sum(int(layer.marker_count) for layer in materialized),
        lines=tuple(line for layer in materialized for line in tuple(layer.lines or ())),
        footprints=tuple(footprint for layer in materialized for footprint in tuple(layer.footprints or ())),
        icons=tuple(icon for layer in materialized for icon in tuple(layer.icons or ())),
        warnings=tuple(warning for layer in materialized for warning in tuple(layer.warnings or ())),
    )


__all__ = [
    "SPATIAL_DESIGN_EXTRA_KEY",
    "SPATIAL_DESIGN_VERSION",
    "SpatialDesignAudit",
    "SpatialDesignIssue",
    "SpatialDesignPath",
    "SpatialDesignPlan",
    "SpatialDesignZone",
    "SpatialPlacementIntent",
    "audit_spatial_design",
    "combine_marker_geometry",
    "read_authored_spatial_design",
    "spatial_design_marker_geometry",
    "spatial_design_placement_ledger",
    "write_authored_spatial_design",
]
