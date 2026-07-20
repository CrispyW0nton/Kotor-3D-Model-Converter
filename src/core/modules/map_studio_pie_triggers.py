"""Trigger-volume crossing detection for Play-in-Editor.

KOTOR GIT triggers carry a Position plus a Geometry polygon whose points are
*local* to that position (verified against real 207TEL triggers: geometry points
sit near the origin while the trigger position is the world anchor). A trigger
fires its OnEnter when the player walks into that world polygon; transition
triggers additionally carry LinkedToModule/LinkedTo, the area they warp to.

This module builds world-space trigger volumes from PIE trigger entities and
tracks player enter/exit crossings by even-odd point-in-polygon on XY. It only
detects and classifies crossings; PIE reports cross-module transitions rather
than warping (mirroring the inter-module door policy), and never executes the
referenced OnEnter NWScript. Editor-side detection, not a retail proof.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

Vec2 = tuple[float, float]


def normalize_module_root(name: Any) -> str:
    """Strip a module filename to its lowercase root (``202tel.mod`` → ``202tel``)."""

    text = str(name or "").strip().lower()
    for suffix in (".mod", ".rim", ".erf", ".sav"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    if text.endswith("_s"):
        text = text[:-2]
    return text


@dataclass(frozen=True)
class MapStudioPIETransitionCheck:
    """One authored module transition validated against installed modules."""

    source_kind: str  # "door" | "trigger"
    tag: str
    module: str       # normalized destination module root
    target: str       # destination waypoint / object tag
    exists: bool | None  # True installed, False missing, None when unverifiable


def validate_module_transitions(
    transitions: Iterable[Any],
    available_modules: Iterable[Any],
) -> tuple[MapStudioPIETransitionCheck, ...]:
    """Validate ``(source_kind, tag, module, target)`` links against installed modules.

    A transition whose destination module is not installed would black-screen or
    crash the retail game — surfacing that here lets a creator catch broken
    ``LinkedToModule`` links before launching. ``available_modules`` is any
    iterable of module filenames/roots; comparison is on the normalized root.
    When the available set is empty (the module list could not be resolved),
    every destination is reported as ``exists=None`` (unverifiable) rather than
    falsely ``missing`` — an honest "couldn't check" beats a false alarm.
    """

    installed = {normalize_module_root(name) for name in (available_modules or ()) if normalize_module_root(name)}
    verifiable = bool(installed)
    checks: list[MapStudioPIETransitionCheck] = []
    seen: set[tuple[str, str, str]] = set()
    for row in tuple(transitions or ()):
        values = tuple(row or ())
        if len(values) < 4:
            continue
        source_kind = str(values[0] or "").strip().lower()
        tag = str(values[1] or "").strip()
        module = normalize_module_root(values[2])
        target = str(values[3] or "").strip()
        if not module:
            continue
        key = (source_kind, module, target)
        if key in seen:
            continue
        seen.add(key)
        checks.append(
            MapStudioPIETransitionCheck(
                source_kind=source_kind or "unknown",
                tag=tag,
                module=module,
                target=target,
                exists=(module in installed) if verifiable else None,
            )
        )
    return tuple(checks)


@dataclass(frozen=True)
class TriggerVolume:
    """One authored trigger resolved to a world-space XY polygon."""

    entity_id: str
    tag: str
    polygon_xy: tuple[Vec2, ...]
    transition_module: str = ""
    transition_target: str = ""
    has_scripts: bool = False
    on_enter_script: str = ""

    @property
    def is_transition(self) -> bool:
        return bool(self.transition_module or self.transition_target)


@dataclass(frozen=True)
class TriggerCrossing:
    """A detected player enter/exit against one trigger volume."""

    kind: str  # "entered" | "exited"
    volume: TriggerVolume


def point_in_polygon_xy(x: float, y: float, polygon: tuple[Vec2, ...]) -> bool:
    """Even-odd ray-cast point-in-polygon test on the XY plane."""

    count = len(polygon)
    if count < 3:
        return False
    inside = False
    previous = count - 1
    for current in range(count):
        xi, yi = float(polygon[current][0]), float(polygon[current][1])
        xj, yj = float(polygon[previous][0]), float(polygon[previous][1])
        if (yi > y) != (yj > y):
            crossing_x = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside


def build_trigger_volumes(entities: Any) -> tuple[TriggerVolume, ...]:
    """Resolve trigger entities to world-space volumes, skipping degenerate ones.

    The GIT geometry is authored local to the trigger position, so each world
    vertex is ``trigger.position.xy + geometry_point.xy``.
    """

    volumes: list[TriggerVolume] = []
    for entity in tuple(entities or ()):
        if str(getattr(entity, "kind", "") or "").strip().lower() != "trigger":
            continue
        geometry = tuple(getattr(entity, "geometry", ()) or ())
        if len(geometry) < 3:
            continue
        position = tuple(getattr(entity, "position", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))
        origin_x = float(position[0]) if len(position) > 0 else 0.0
        origin_y = float(position[1]) if len(position) > 1 else 0.0
        polygon: list[Vec2] = []
        for point in geometry:
            values = tuple(point or ())
            if len(values) < 2:
                continue
            polygon.append((origin_x + float(values[0]), origin_y + float(values[1])))
        if len(polygon) < 3:
            continue
        scripts = tuple(getattr(entity, "scripts", ()) or ())
        on_enter_script = ""
        for row in scripts:
            pair = tuple(row or ())
            if len(pair) >= 2 and str(pair[0]).strip().lower() == "on_enter":
                on_enter_script = str(pair[1] or "").strip()
                break
        volumes.append(
            TriggerVolume(
                entity_id=str(getattr(entity, "entity_id", "") or ""),
                tag=str(getattr(entity, "tag", "") or ""),
                polygon_xy=tuple(polygon),
                transition_module=str(getattr(entity, "transition_module", "") or ""),
                transition_target=str(getattr(entity, "transition_target", "") or ""),
                has_scripts=bool(scripts),
                on_enter_script=on_enter_script,
            )
        )
    return tuple(volumes)


class TriggerCrossingTracker:
    """Debounced player enter/exit tracking across a set of trigger volumes."""

    def __init__(self, volumes: Any) -> None:
        self._volumes: tuple[TriggerVolume, ...] = tuple(volumes or ())
        self._inside_ids: set[str] = set()

    @property
    def volumes(self) -> tuple[TriggerVolume, ...]:
        return self._volumes

    def inside_ids(self) -> frozenset[str]:
        return frozenset(self._inside_ids)

    def update(self, player_x: float, player_y: float) -> tuple[TriggerCrossing, ...]:
        """Return the enter/exit crossings caused by moving to (player_x, player_y)."""

        now_inside: set[str] = set()
        crossings: list[TriggerCrossing] = []
        for volume in self._volumes:
            if point_in_polygon_xy(float(player_x), float(player_y), volume.polygon_xy):
                now_inside.add(volume.entity_id)
                if volume.entity_id not in self._inside_ids:
                    crossings.append(TriggerCrossing("entered", volume))
        for volume in self._volumes:
            if volume.entity_id in self._inside_ids and volume.entity_id not in now_inside:
                crossings.append(TriggerCrossing("exited", volume))
        self._inside_ids = now_inside
        return tuple(crossings)


__all__ = [
    "TriggerVolume",
    "TriggerCrossing",
    "TriggerCrossingTracker",
    "point_in_polygon_xy",
    "build_trigger_volumes",
]
