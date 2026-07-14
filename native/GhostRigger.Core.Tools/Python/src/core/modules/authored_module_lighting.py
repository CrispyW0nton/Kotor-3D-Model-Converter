"""Authored room lighting intent for Map Studio.

KOTOR area lighting is not a GIT object list like creatures or placeables.
Map Studio stores lights as room-authoring intent so the viewport and baked
lightmap pipeline can consume the same stable data without pretending lights
are gameplay placements.  This contract does not imply that authored lights
are currently emitted as dynamic KOTOR MDL light nodes.
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import dataclass, field, replace
from typing import Any


Vec3 = tuple[float, float, float]
_UNSET_BAKE_GROUP = object()


@dataclass(frozen=True)
class AuthoredRoomLight:
    """One author-placed light used by viewport and lightmap authoring.

    ``light_id`` is persisted independently from the display ``name`` so a
    rename cannot invalidate bake bindings.  New fields follow ``metadata`` to
    preserve the positional constructor used by older Python integrations.
    """

    name: str
    room_resref: str
    position: Vec3 = (0.0, 0.0, 2.25)
    color: Vec3 = (1.0, 0.92, 0.78)
    radius: float = 8.0
    intensity: float = 1.0
    light_type: str = "point"
    metadata: dict[str, Any] = field(default_factory=dict)
    light_id: str = ""
    enabled: bool = True
    casts_shadows: bool = True
    affects_diffuse: bool = True
    affects_lightmap: bool = True
    direction: Vec3 = (0.0, 0.0, -1.0)
    cone_angle_degrees: float = 45.0
    bake_group: str | None = None

    def __post_init__(self) -> None:
        # Direct constructors pre-date persistent IDs and remain common in
        # fixtures/presets.  Give those rows the same deterministic migration
        # identity that a legacy KMAP row receives during normalization.
        if not str(self.light_id or "").strip():
            object.__setattr__(self, "light_id", _legacy_light_id(self))


@dataclass(frozen=True)
class AuthoredRoomLightUpdate:
    """Result of appending or editing authored room lighting."""

    project: Any
    light: AuthoredRoomLight
    count: int
    light_id: str = ""


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
    enabled: bool
    casts_shadows: bool
    affects_diffuse: bool
    affects_lightmap: bool
    direction: Vec3
    cone_angle_degrees: float
    bake_group: str | None


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


def _is_finite_vec3(value: Any) -> bool:
    try:
        return len(value) == 3 and all(math.isfinite(float(item)) for item in value)
    except (TypeError, ValueError):
        return False


def _is_finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _normalise_light_type(value: Any) -> str:
    text = str(value or "point").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "": "point",
        "omni": "point",
        "omnidirectional": "point",
        "spotlight": "spot",
    }
    return aliases.get(text, text)


def _normalise_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    return bool(default)


def _finite_float(value: Any, *, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _normalise_direction(value: Any) -> Vec3:
    direction = _finite_vec3(value, default=(0.0, 0.0, -1.0))
    if not _is_finite_vec3(direction):
        return (0.0, 0.0, -1.0)
    magnitude = math.sqrt(sum(float(component) ** 2 for component in direction))
    if magnitude <= 1.0e-8:
        return (0.0, 0.0, -1.0)
    return tuple(float(component) / magnitude for component in direction)  # type: ignore[return-value]


def _normalise_bake_group(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:32] or None


def _legacy_light_id(data: Any) -> str:
    """Return a deterministic identity for one pre-ID light row.

    The complete legacy row is used only as a migration seed.  Once serialized,
    the resulting explicit ID survives later renames and property edits.
    """

    if isinstance(data, AuthoredRoomLight):
        source = {
            "name": data.name,
            "room_resref": data.room_resref,
            "position": list(data.position),
            "color": list(data.color),
            "radius": data.radius,
            "intensity": data.intensity,
            "light_type": data.light_type,
            "metadata": dict(data.metadata),
        }
    else:
        source = dict(data) if isinstance(data, dict) else {"value": str(data or "")}
        source.pop("light_id", None)
    canonical = json.dumps(source, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    return f"legacy_{digest}"


def _new_light_id(existing_lights: tuple[AuthoredRoomLight, ...] | list[AuthoredRoomLight]) -> str:
    existing = {str(light.light_id or "").strip() for light in existing_lights}
    while True:
        candidate = f"light_{uuid.uuid4().hex}"
        if candidate not in existing:
            return candidate


def _clamped_color(value: Any) -> Vec3:
    color = _finite_vec3(value, default=(1.0, 0.92, 0.78))
    return tuple(max(0.0, min(1.0, float(channel))) for channel in color)  # type: ignore[return-value]


def normalise_authored_room_light(data: Any) -> AuthoredRoomLight:
    """Parse serialized KMAP light data into a stable authored light."""

    if isinstance(data, AuthoredRoomLight):
        return data
    source = dict(data) if isinstance(data, dict) else {}
    return AuthoredRoomLight(
        name=str(source.get("name") or source.get("tag") or "room_light").strip()[:32],
        room_resref=str(source.get("room_resref") or source.get("room") or "").strip().lower()[:16],
        position=_finite_vec3(source.get("position"), default=(0.0, 0.0, 2.25)),
        color=_clamped_color(source.get("color")),
        radius=_finite_float(source.get("radius", 8.0), default=8.0),
        intensity=_finite_float(source.get("intensity", 1.0), default=1.0),
        light_type=_normalise_light_type(source.get("light_type")),
        metadata=dict(source.get("metadata")) if isinstance(source.get("metadata"), dict) else {},
        light_id=str(source.get("light_id") or "").strip()[:96] or _legacy_light_id(source),
        enabled=_normalise_bool(source.get("enabled"), default=True),
        casts_shadows=_normalise_bool(source.get("casts_shadows"), default=True),
        affects_diffuse=_normalise_bool(source.get("affects_diffuse"), default=True),
        affects_lightmap=_normalise_bool(source.get("affects_lightmap"), default=True),
        direction=_normalise_direction(source.get("direction")),
        cone_angle_degrees=_finite_float(
            source.get("cone_angle_degrees", source.get("cone_angle", 45.0)),
            default=45.0,
        ),
        bake_group=_normalise_bake_group(source.get("bake_group")),
    )


def authored_room_light_payload(light: AuthoredRoomLight) -> dict[str, Any]:
    """Return JSON/KMAP-friendly authored light data."""

    return {
        "light_id": light.light_id,
        "name": light.name,
        "room_resref": light.room_resref,
        "position": [float(light.position[0]), float(light.position[1]), float(light.position[2])],
        "color": [float(light.color[0]), float(light.color[1]), float(light.color[2])],
        "radius": float(light.radius),
        "intensity": float(light.intensity),
        "light_type": light.light_type,
        "enabled": bool(light.enabled),
        "casts_shadows": bool(light.casts_shadows),
        "affects_diffuse": bool(light.affects_diffuse),
        "affects_lightmap": bool(light.affects_lightmap),
        "direction": [float(light.direction[0]), float(light.direction[1]), float(light.direction[2])],
        "cone_angle_degrees": float(light.cone_angle_degrees),
        "bake_group": light.bake_group,
        "metadata": dict(light.metadata),
    }


def authored_room_light_id(light_or_id: AuthoredRoomLight | str) -> str:
    """Return the virtual KMAP editor id for one authored room light."""

    identity = light_or_id.light_id if isinstance(light_or_id, AuthoredRoomLight) else str(light_or_id or "").strip()
    if identity.startswith("authored_light:"):
        return identity
    return f"authored_light:{identity}"


def parse_authored_room_light_id(light_id: str) -> str:
    """Extract a persistent ID (or accepted legacy name alias) from an editor id."""

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
                light_id=authored_room_light_id(light),
                name=light.name,
                room_resref=light.room_resref,
                position=light.position,
                color=light.color,
                radius=float(light.radius),
                intensity=float(light.intensity),
                light_type=light.light_type,
                enabled=bool(light.enabled),
                casts_shadows=bool(light.casts_shadows),
                affects_diffuse=bool(light.affects_diffuse),
                affects_lightmap=bool(light.affects_lightmap),
                direction=light.direction,
                cone_angle_degrees=float(light.cone_angle_degrees),
                bake_group=light.bake_group,
            )
        )
    return tuple(rows)


def _copy_light_name(name: str, count: int) -> str:
    base = str(name or "").strip() or f"room_light_{count + 1}"
    suffix = "_copy"
    if len(base) + len(suffix) <= 32:
        return f"{base}{suffix}"
    return f"{base[: 32 - len(suffix)]}{suffix}"


def _offset_position(position: Vec3, offset: Vec3 = (0.5, 0.5, 0.0)) -> Vec3:
    return (
        float(position[0]) + float(offset[0]),
        float(position[1]) + float(offset[1]),
        float(position[2]) + float(offset[2]),
    )


def _light_items_for_id(project: Any, light_id: str) -> tuple[str, list[AuthoredRoomLight], int, AuthoredRoomLight]:
    identity = parse_authored_room_light_id(light_id)
    lights = list(tuple(getattr(project, "lights", ()) or ()))
    for index, light in enumerate(lights):
        if light.light_id == identity:
            return identity, lights, index, light
    # Older commands and KMAP-era integrations addressed rows by display name.
    # Keep that lookup as a migration alias, but all returned IDs are stable.
    for index, light in enumerate(lights):
        if light.name == identity:
            return identity, lights, index, light
    raise ValueError(f"Unknown authored room light: {identity}.")


def _validate_all_lights(project: Any, lights: tuple[AuthoredRoomLight, ...]) -> None:
    validation = validate_authored_room_lights(
        lights,
        room_resrefs={room.normalised_resref() for room in tuple(getattr(project, "rooms", ()) or ())},
    )
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))


def validate_authored_room_lights(
    lights: tuple[AuthoredRoomLight, ...],
    *,
    room_resrefs: set[str],
) -> AuthoredRoomLightValidation:
    """Validate authored room lighting intent before package/export."""

    warnings: list[str] = []
    blocking: list[str] = []
    names: set[str] = set()
    light_ids: set[str] = set()
    for index, light in enumerate(tuple(lights or ())):
        label = light.name or f"room_light_{index + 1}"
        stable_id = str(light.light_id or "").strip()
        if not isinstance(light.light_id, str):
            blocking.append(f"Authored room light {label} light_id must be text.")
        if not stable_id:
            blocking.append(f"Authored room light {label} requires a stable light_id.")
        elif stable_id in light_ids:
            blocking.append(f"Duplicate authored room light id: {stable_id}.")
        elif len(stable_id) > 96:
            blocking.append(f"Authored room light {label} light_id exceeds 96 characters.")
        light_ids.add(stable_id)
        if not label:
            blocking.append("Authored room light requires a stable name.")
        if label in names:
            blocking.append(f"Duplicate authored room light name: {label}.")
        names.add(label)
        if light.room_resref not in room_resrefs:
            blocking.append(f"Authored room light {label} targets missing room {light.room_resref or '(missing)'}.")
        if not _is_finite_vec3(light.position):
            blocking.append(f"Authored room light {label} has an invalid position.")
        color_is_finite = _is_finite_vec3(light.color)
        if not color_is_finite:
            blocking.append(f"Authored room light {label} has an invalid color.")
        elif any(float(channel) < 0.0 or float(channel) > 1.0 for channel in light.color):
            blocking.append(f"Authored room light {label} color channels must be in the 0..1 range.")
        radius_is_finite = _is_finite_number(light.radius)
        if not radius_is_finite or float(light.radius) <= 0.0:
            blocking.append(f"Authored room light {label} radius must be positive.")
        if not _is_finite_number(light.intensity) or float(light.intensity) < 0.0:
            blocking.append(f"Authored room light {label} intensity must be non-negative.")
        light_type = _normalise_light_type(light.light_type)
        if light_type not in {"point", "spot", "ambient"}:
            blocking.append(f"Authored room light {label} has unsupported type {light.light_type!r}.")
        for flag_name in ("enabled", "casts_shadows", "affects_diffuse", "affects_lightmap"):
            if not isinstance(getattr(light, flag_name), bool):
                blocking.append(f"Authored room light {label} {flag_name} must be a boolean.")
        if not _is_finite_vec3(light.direction):
            blocking.append(f"Authored room light {label} has an invalid direction.")
        else:
            direction_length = math.sqrt(sum(float(component) ** 2 for component in light.direction))
            if light_type == "spot" and not math.isclose(direction_length, 1.0, rel_tol=1.0e-5, abs_tol=1.0e-5):
                blocking.append(f"Authored room light {label} spot direction must be a non-zero unit vector.")
        cone_is_finite = _is_finite_number(light.cone_angle_degrees)
        if not cone_is_finite:
            blocking.append(f"Authored room light {label} cone angle must be finite.")
        elif light_type == "spot" and not 0.0 < float(light.cone_angle_degrees) < 180.0:
            blocking.append(f"Authored room light {label} spot cone angle must be between 0 and 180 degrees.")
        if light.bake_group is not None:
            if not isinstance(light.bake_group, str):
                blocking.append(f"Authored room light {label} bake group must be text or null.")
            elif not light.bake_group.strip() or len(light.bake_group) > 32:
                blocking.append(f"Authored room light {label} bake group must contain 1..32 characters.")
        if light_type == "ambient" and radius_is_finite and float(light.radius) != 8.0:
            warnings.append(f"Authored room light {label} is ambient; radius is retained for editor preview only.")
        if not bool(light.affects_diffuse) and not bool(light.affects_lightmap):
            warnings.append(f"Authored room light {label} affects neither viewport diffuse lighting nor baked lightmaps.")
        if light_type != "spot" and cone_is_finite and not math.isclose(float(light.cone_angle_degrees), 45.0):
            warnings.append(f"Authored room light {label} is not a spot light; cone angle is retained for later editing.")
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
    enabled: Any = True,
    casts_shadows: Any = True,
    affects_diffuse: Any = True,
    affects_lightmap: Any = True,
    direction: Any = (0.0, 0.0, -1.0),
    cone_angle_degrees: float = 45.0,
    bake_group: Any = None,
) -> AuthoredRoomLightUpdate:
    """Append one room light to an authored Map Studio project."""

    from .authored_module_project import normalise_resref

    target_room = normalise_resref(room_resref)
    if not target_room and getattr(project, "rooms", ()):
        target_room = project.rooms[0].normalised_resref()
    existing_lights = tuple(getattr(project, "lights", ()) or ())
    light_count = len(existing_lights)
    light = AuthoredRoomLight(
        name=str(name or f"room_light_{light_count + 1}").strip()[:32],
        room_resref=target_room,
        position=_finite_vec3(position, default=(0.0, 0.0, 2.25)),
        color=_clamped_color(color),
        radius=float(radius),
        intensity=float(intensity),
        light_type=_normalise_light_type(light_type),
        metadata={"source": "map_studio:authored_room_light"},
        light_id=_new_light_id(existing_lights),
        enabled=_normalise_bool(enabled, default=True),
        casts_shadows=_normalise_bool(casts_shadows, default=True),
        affects_diffuse=_normalise_bool(affects_diffuse, default=True),
        affects_lightmap=_normalise_bool(affects_lightmap, default=True),
        direction=_normalise_direction(direction),
        cone_angle_degrees=_finite_float(cone_angle_degrees, default=45.0),
        bake_group=_normalise_bake_group(bake_group),
    )
    updated_lights = existing_lights + (light,)
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
    return AuthoredRoomLightUpdate(project=updated, light=light, count=len(updated_lights), light_id=authored_room_light_id(light))


def update_authored_room_light_transform(
    project: Any,
    light_id: str,
    *,
    position: Any,
    direction: Any | None = None,
) -> AuthoredRoomLightUpdate:
    """Move one authored room light by virtual id."""

    _name, lights, index, light = _light_items_for_id(project, light_id)
    updated_light = replace(
        light,
        position=_finite_vec3(position, default=light.position),
        direction=_normalise_direction(direction) if direction is not None else light.direction,
    )
    lights[index] = updated_light
    _validate_all_lights(project, tuple(lights))
    updated = replace(
        project,
        lights=tuple(lights),
        notes=tuple(project.notes) + (f"Moved Map Studio room light: {updated_light.name}.",),
        extra={
            **dict(project.extra),
            "last_room_light": authored_room_light_payload(updated_light),
        },
    )
    return AuthoredRoomLightUpdate(project=updated, light=updated_light, count=len(lights), light_id=authored_room_light_id(updated_light))


def update_authored_room_light_properties(
    project: Any,
    light_id: str,
    *,
    color: Any | None = None,
    radius: float | None = None,
    intensity: float | None = None,
    light_type: Any | None = None,
    enabled: Any | None = None,
    casts_shadows: Any | None = None,
    affects_diffuse: Any | None = None,
    affects_lightmap: Any | None = None,
    direction: Any | None = None,
    cone_angle_degrees: float | None = None,
    bake_group: Any = _UNSET_BAKE_GROUP,
) -> AuthoredRoomLightUpdate:
    """Edit the non-transform preview/export properties for one authored room light."""

    _name, lights, index, light = _light_items_for_id(project, light_id)
    updated_light = replace(
        light,
        color=_clamped_color(color) if color is not None else light.color,
        radius=float(radius) if radius is not None else light.radius,
        intensity=float(intensity) if intensity is not None else light.intensity,
        light_type=_normalise_light_type(light_type) if light_type is not None else light.light_type,
        enabled=_normalise_bool(enabled, default=light.enabled) if enabled is not None else light.enabled,
        casts_shadows=(
            _normalise_bool(casts_shadows, default=light.casts_shadows) if casts_shadows is not None else light.casts_shadows
        ),
        affects_diffuse=(
            _normalise_bool(affects_diffuse, default=light.affects_diffuse) if affects_diffuse is not None else light.affects_diffuse
        ),
        affects_lightmap=(
            _normalise_bool(affects_lightmap, default=light.affects_lightmap)
            if affects_lightmap is not None
            else light.affects_lightmap
        ),
        direction=_normalise_direction(direction) if direction is not None else light.direction,
        cone_angle_degrees=(
            _finite_float(cone_angle_degrees, default=light.cone_angle_degrees)
            if cone_angle_degrees is not None
            else light.cone_angle_degrees
        ),
        bake_group=(
            light.bake_group if bake_group is _UNSET_BAKE_GROUP else _normalise_bake_group(bake_group)
        ),
    )
    lights[index] = updated_light
    _validate_all_lights(project, tuple(lights))
    updated = replace(
        project,
        lights=tuple(lights),
        notes=tuple(project.notes) + (f"Edited Map Studio room light properties: {updated_light.name}.",),
        extra={
            **dict(project.extra),
            "last_room_light": authored_room_light_payload(updated_light),
        },
    )
    return AuthoredRoomLightUpdate(project=updated, light=updated_light, count=len(lights), light_id=authored_room_light_id(updated_light))


def rename_authored_room_light(
    project: Any,
    light_id: str,
    *,
    name: Any,
) -> AuthoredRoomLightUpdate:
    """Rename one authored room light by virtual id."""

    label = str(name or "").strip()[:32]
    if not label:
        raise ValueError("Authored room light name cannot be empty.")
    _old_name, lights, index, light = _light_items_for_id(project, light_id)
    updated_light = replace(light, name=label)
    lights[index] = updated_light
    _validate_all_lights(project, tuple(lights))
    updated = replace(
        project,
        lights=tuple(lights),
        notes=tuple(project.notes) + (f"Renamed Map Studio room light: {light.name} to {updated_light.name}.",),
        extra={
            **dict(project.extra),
            "last_room_light_rename": authored_room_light_payload(updated_light),
        },
    )
    return AuthoredRoomLightUpdate(project=updated, light=updated_light, count=len(lights), light_id=authored_room_light_id(updated_light))


def duplicate_authored_room_light(project: Any, light_id: str) -> AuthoredRoomLightUpdate:
    """Duplicate one authored room light by virtual id."""

    _name, lights, _index, light = _light_items_for_id(project, light_id)
    duplicated = replace(
        light,
        name=_copy_light_name(light.name, len(lights)),
        position=_offset_position(light.position),
        light_id=_new_light_id(lights),
    )
    lights.append(duplicated)
    _validate_all_lights(project, tuple(lights))
    updated = replace(
        project,
        lights=tuple(lights),
        notes=tuple(project.notes) + (f"Duplicated Map Studio room light: {light.name} to {duplicated.name}.",),
        extra={
            **dict(project.extra),
            "last_room_light_duplicate": authored_room_light_payload(duplicated),
        },
    )
    return AuthoredRoomLightUpdate(project=updated, light=duplicated, count=len(lights), light_id=authored_room_light_id(duplicated))


def remove_authored_room_light(project: Any, light_id: str) -> AuthoredRoomLightUpdate:
    """Remove one authored room light by virtual id."""

    _name, lights, index, light = _light_items_for_id(project, light_id)
    del lights[index]
    _validate_all_lights(project, tuple(lights))
    updated = replace(
        project,
        lights=tuple(lights),
        notes=tuple(project.notes) + (f"Removed Map Studio room light: {light.name}.",),
        extra={
            **dict(project.extra),
            "last_room_light_remove": authored_room_light_payload(light),
        },
    )
    return AuthoredRoomLightUpdate(project=updated, light=light, count=len(lights), light_id="")


__all__ = [
    "AuthoredRoomLight",
    "AuthoredRoomLightRow",
    "AuthoredRoomLightUpdate",
    "AuthoredRoomLightValidation",
    "add_authored_room_light",
    "authored_room_light_id",
    "authored_room_light_payload",
    "authored_room_light_rows",
    "duplicate_authored_room_light",
    "normalise_authored_room_light",
    "parse_authored_room_light_id",
    "remove_authored_room_light",
    "rename_authored_room_light",
    "update_authored_room_light_properties",
    "update_authored_room_light_transform",
    "validate_authored_room_lights",
]
