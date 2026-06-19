"""Authored room lighting intent for Map Studio.

KOTOR area lighting is not a GIT object list like creatures or placeables.
Map Studio stores lights as room-authoring intent so future room MDL/lightmap
export can consume the same stable data without pretending lights are gameplay
placements.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any


Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class AuthoredRoomLight:
    """One author-placed room light for a Map Studio module."""

    name: str
    room_resref: str
    position: Vec3 = (0.0, 0.0, 2.25)
    color: Vec3 = (1.0, 0.92, 0.78)
    radius: float = 8.0
    intensity: float = 1.0
    light_type: str = "point"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthoredRoomLightUpdate:
    """Result of appending or editing authored room lighting."""

    project: Any
    light: AuthoredRoomLight
    count: int


@dataclass(frozen=True)
class AuthoredRoomLightRow:
    """UI-friendly authored room light row."""

    light_id: str
    name: str
    room_resref: str
    position: Vec3
    color: Vec3
    radius: float
    intensity: float
    light_type: str


@dataclass(frozen=True)
class AuthoredRoomLightValidation:
    """Validation result for authored room lights."""

    ok: bool
    warnings: tuple[str, ...] = ()
    blocking_issues: tuple[str, ...] = ()


def _finite_vec3(value: Any, *, default: Vec3) -> Vec3:
    if isinstance(value, dict):
        value = (value.get("x"), value.get("y"), value.get("z"))
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            result = (float(value[0]), float(value[1]), float(value[2]))
        except (TypeError, ValueError):
            result = default
    else:
        result = default
    return result


def _is_finite_vec3(value: Vec3) -> bool:
    return len(value) == 3 and all(math.isfinite(float(item)) for item in value)


def _normalise_light_type(value: Any) -> str:
    text = str(value or "point").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "": "point",
        "omni": "point",
        "omnidirectional": "point",
        "spotlight": "spot",
    }
    return aliases.get(text, text)


def _clamped_color(value: Any) -> Vec3:
    color = _finite_vec3(value, default=(1.0, 0.92, 0.78))
    return tuple(max(0.0, min(1.0, float(channel))) for channel in color)  # type: ignore[return-value]


def normalise_authored_room_light(data: Any) -> AuthoredRoomLight:
    """Parse serialized KMAP light data into a stable authored light."""

    source = dict(data) if isinstance(data, dict) else {}
    return AuthoredRoomLight(
        name=str(source.get("name") or source.get("tag") or "room_light").strip()[:32],
        room_resref=str(source.get("room_resref") or source.get("room") or "").strip().lower()[:16],
        position=_finite_vec3(source.get("position"), default=(0.0, 0.0, 2.25)),
        color=_clamped_color(source.get("color")),
        radius=float(source.get("radius", 8.0) or 8.0),
        intensity=float(source.get("intensity", 1.0) or 1.0),
        light_type=_normalise_light_type(source.get("light_type")),
        metadata=dict(source.get("metadata")) if isinstance(source.get("metadata"), dict) else {},
    )


def authored_room_light_payload(light: AuthoredRoomLight) -> dict[str, Any]:
    """Return JSON/KMAP-friendly authored light data."""

    return {
        "name": light.name,
        "room_resref": light.room_resref,
        "position": [float(light.position[0]), float(light.position[1]), float(light.position[2])],
        "color": [float(light.color[0]), float(light.color[1]), float(light.color[2])],
        "radius": float(light.radius),
        "intensity": float(light.intensity),
        "light_type": light.light_type,
        "metadata": dict(light.metadata),
    }


def authored_room_light_id(name: str) -> str:
    """Return the virtual KMAP editor id for one authored room light."""

    return f"authored_light:{str(name or '').strip()}"


def parse_authored_room_light_id(light_id: str) -> str:
    """Extract a light name from a virtual authored-room-light id."""

    text = str(light_id or "").strip()
    prefix = "authored_light:"
    if not text.startswith(prefix) or not text[len(prefix) :]:
        raise ValueError(f"Invalid authored room light id: {light_id!r}")
    return text[len(prefix) :]


def authored_room_light_rows(project: Any) -> tuple[AuthoredRoomLightRow, ...]:
    """Return UI rows for authored room lights in a project."""

    rows: list[AuthoredRoomLightRow] = []
    for light in tuple(getattr(project, "lights", ()) or ()):
        rows.append(
            AuthoredRoomLightRow(
                light_id=authored_room_light_id(light.name),
                name=light.name,
                room_resref=light.room_resref,
                position=light.position,
                color=light.color,
                radius=float(light.radius),
                intensity=float(light.intensity),
                light_type=light.light_type,
            )
        )
    return tuple(rows)


def validate_authored_room_lights(
    lights: tuple[AuthoredRoomLight, ...],
    *,
    room_resrefs: set[str],
) -> AuthoredRoomLightValidation:
    """Validate authored room lighting intent before package/export."""

    warnings: list[str] = []
    blocking: list[str] = []
    names: set[str] = set()
    for index, light in enumerate(tuple(lights or ())):
        label = light.name or f"room_light_{index + 1}"
        if not label:
            blocking.append("Authored room light requires a stable name.")
        if label in names:
            blocking.append(f"Duplicate authored room light name: {label}.")
        names.add(label)
        if light.room_resref not in room_resrefs:
            blocking.append(f"Authored room light {label} targets missing room {light.room_resref or '(missing)'}.")
        if not _is_finite_vec3(light.position):
            blocking.append(f"Authored room light {label} has an invalid position.")
        if not _is_finite_vec3(light.color):
            blocking.append(f"Authored room light {label} has an invalid color.")
        if any(float(channel) < 0.0 or float(channel) > 1.0 for channel in light.color):
            blocking.append(f"Authored room light {label} color channels must be in the 0..1 range.")
        if not math.isfinite(float(light.radius)) or float(light.radius) <= 0.0:
            blocking.append(f"Authored room light {label} radius must be positive.")
        if not math.isfinite(float(light.intensity)) or float(light.intensity) < 0.0:
            blocking.append(f"Authored room light {label} intensity must be non-negative.")
        if _normalise_light_type(light.light_type) not in {"point", "spot", "ambient"}:
            blocking.append(f"Authored room light {label} has unsupported type {light.light_type!r}.")
        if light.light_type == "ambient" and float(light.radius) != 8.0:
            warnings.append(f"Authored room light {label} is ambient; radius is retained for editor preview only.")
    return AuthoredRoomLightValidation(
        ok=not blocking,
        warnings=tuple(warnings),
        blocking_issues=tuple(blocking),
    )


def add_authored_room_light(
    project: Any,
    *,
    room_resref: Any = "",
    name: Any = "",
    position: Any = (0.0, 0.0, 2.25),
    color: Any = (1.0, 0.92, 0.78),
    radius: float = 8.0,
    intensity: float = 1.0,
    light_type: Any = "point",
) -> AuthoredRoomLightUpdate:
    """Append one room light to an authored Map Studio project."""

    from .authored_module_project import normalise_resref

    target_room = normalise_resref(room_resref)
    if not target_room and getattr(project, "rooms", ()):
        target_room = project.rooms[0].normalised_resref()
    light_count = len(tuple(getattr(project, "lights", ()) or ()))
    light = AuthoredRoomLight(
        name=str(name or f"room_light_{light_count + 1}").strip()[:32],
        room_resref=target_room,
        position=_finite_vec3(position, default=(0.0, 0.0, 2.25)),
        color=_clamped_color(color),
        radius=float(radius),
        intensity=float(intensity),
        light_type=_normalise_light_type(light_type),
        metadata={"source": "map_studio:authored_room_light"},
    )
    updated_lights = tuple(getattr(project, "lights", ()) or ()) + (light,)
    validation = validate_authored_room_lights(
        (light,),
        room_resrefs={room.normalised_resref() for room in tuple(getattr(project, "rooms", ()) or ())},
    )
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    metadata = authored_room_light_payload(light)
    updated = replace(
        project,
        lights=updated_lights,
        notes=tuple(project.notes) + (f"Added Map Studio room light: {light.name}.",),
        extra={
            **dict(project.extra),
            "last_room_light": metadata,
        },
    )
    return AuthoredRoomLightUpdate(project=updated, light=light, count=len(updated_lights))


def update_authored_room_light_transform(
    project: Any,
    light_id: str,
    *,
    position: Any,
) -> AuthoredRoomLightUpdate:
    """Move one authored room light by virtual id."""

    name = parse_authored_room_light_id(light_id)
    lights = list(tuple(getattr(project, "lights", ()) or ()))
    for index, light in enumerate(lights):
        if light.name != name:
            continue
        updated_light = replace(light, position=_finite_vec3(position, default=light.position))
        validation = validate_authored_room_lights(
            (updated_light,),
            room_resrefs={room.normalised_resref() for room in tuple(getattr(project, "rooms", ()) or ())},
        )
        if not validation.ok:
            raise ValueError("; ".join(validation.blocking_issues))
        lights[index] = updated_light
        updated = replace(
            project,
            lights=tuple(lights),
            notes=tuple(project.notes) + (f"Moved Map Studio room light: {updated_light.name}.",),
            extra={
                **dict(project.extra),
                "last_room_light": authored_room_light_payload(updated_light),
            },
        )
        return AuthoredRoomLightUpdate(project=updated, light=updated_light, count=len(lights))
    raise ValueError(f"Unknown authored room light: {name}.")


__all__ = [
    "AuthoredRoomLight",
    "AuthoredRoomLightRow",
    "AuthoredRoomLightUpdate",
    "AuthoredRoomLightValidation",
    "add_authored_room_light",
    "authored_room_light_id",
    "authored_room_light_payload",
    "authored_room_light_rows",
    "normalise_authored_room_light",
    "parse_authored_room_light_id",
    "update_authored_room_light_transform",
    "validate_authored_room_lights",
]
