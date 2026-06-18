"""Project-level gameplay placement editing for authored Map Studio modules."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .authored_module_objects import (
    AuthoredCameraInstance,
    AuthoredCreatureInstance,
    AuthoredDoorInstance,
    AuthoredEncounterInstance,
    AuthoredGameplayPlacement,
    AuthoredPlaceableInstance,
    AuthoredSoundInstance,
    AuthoredStoreInstance,
    AuthoredTriggerInstance,
    AuthoredWaypointInstance,
    normalise_resource_resref,
)
from .authored_module_project import AuthoredModuleProject


Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class AuthoredGameplayPlacementUpdate:
    """Result of adding one authored gameplay placement."""

    project: AuthoredModuleProject
    kind: str
    template_resref: str
    tag: str
    position: Vec3
    count: int


SUPPORTED_AUTHORED_GAMEPLAY_PLACEMENTS: tuple[str, ...] = (
    "placeable",
    "creature",
    "door",
    "waypoint",
    "trigger",
    "encounter",
    "sound",
    "camera",
    "store",
)


def _kind(value: Any) -> str:
    text = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "npc": "creature",
        "utc": "creature",
        "utp": "placeable",
        "utd": "door",
        "utt": "trigger",
        "ute": "encounter",
        "uts": "sound",
        "utm": "store",
        "merchant": "store",
        "waypoint_start": "waypoint",
    }
    return aliases.get(text, text)


def _vec3(value: Any) -> Vec3:
    if isinstance(value, dict):
        value = (value.get("x"), value.get("y"), value.get("z"))
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except (TypeError, ValueError):
            pass
    raise ValueError("Gameplay placement position must contain finite X, Y, and Z values.")


def _default_trigger_geometry(position: Vec3, size: float = 1.0) -> tuple[Vec3, ...]:
    half = max(float(size), 0.1) * 0.5
    x, y, z = position
    return (
        (x - half, y - half, z),
        (x + half, y - half, z),
        (x + half, y + half, z),
        (x - half, y + half, z),
    )


def _require_template(kind: str, template_resref: Any) -> str:
    template = normalise_resource_resref(template_resref)
    if kind not in {"camera"} and not template:
        raise ValueError(f"{kind.title()} placement requires a template resref.")
    return template


def _tag_or_default(tag: Any, template_resref: str, kind: str, count: int) -> str:
    text = str(tag or "").strip()
    if text:
        return text[:32]
    if template_resref:
        return template_resref
    return f"{kind}_{count + 1}"


def _append_placement(
    placement: AuthoredGameplayPlacement,
    *,
    kind: str,
    template_resref: str,
    tag: str,
    position: Vec3,
    bearing: float,
    linked_to: str = "",
    linked_to_module: str = "",
    trigger_size: float = 1.0,
) -> tuple[AuthoredGameplayPlacement, int]:
    if kind == "placeable":
        items = placement.placeables + (AuthoredPlaceableInstance(template_resref=template_resref, tag=tag, position=position, bearing=bearing),)
        return replace(placement, placeables=items), len(items)
    if kind == "creature":
        items = placement.creatures + (AuthoredCreatureInstance(template_resref=template_resref, tag=tag, position=position, bearing=bearing),)
        return replace(placement, creatures=items), len(items)
    if kind == "door":
        items = placement.doors + (
            AuthoredDoorInstance(
                template_resref=template_resref,
                tag=tag,
                position=position,
                bearing=bearing,
                linked_to=linked_to,
                linked_to_module=linked_to_module,
            ),
        )
        return replace(placement, doors=items), len(items)
    if kind == "waypoint":
        items = placement.waypoints + (AuthoredWaypointInstance(template_resref=template_resref, tag=tag, position=position, bearing=bearing, linked_to=linked_to),)
        return replace(placement, waypoints=items), len(items)
    if kind == "trigger":
        items = placement.triggers + (
            AuthoredTriggerInstance(
                template_resref=template_resref,
                tag=tag,
                position=position,
                geometry=_default_trigger_geometry(position, size=trigger_size),
                linked_to=linked_to,
                linked_to_module=linked_to_module,
            ),
        )
        return replace(placement, triggers=items), len(items)
    if kind == "encounter":
        items = placement.encounters + (AuthoredEncounterInstance(template_resref=template_resref, tag=tag, position=position),)
        return replace(placement, encounters=items), len(items)
    if kind == "sound":
        items = placement.sounds + (AuthoredSoundInstance(template_resref=template_resref, tag=tag, position=position),)
        return replace(placement, sounds=items), len(items)
    if kind == "camera":
        items = placement.cameras + (AuthoredCameraInstance(camera_id=tag or str(len(placement.cameras) + 1), position=position),)
        return replace(placement, cameras=items), len(items)
    if kind == "store":
        items = placement.stores + (AuthoredStoreInstance(template_resref=template_resref, tag=tag),)
        return replace(placement, stores=items), len(items)
    raise ValueError(f"Unsupported authored gameplay placement kind '{kind}'.")


def add_authored_gameplay_placement(
    project: AuthoredModuleProject,
    *,
    kind: Any,
    template_resref: Any = "",
    tag: Any = "",
    position: Any = (0.0, 0.0, 0.0),
    bearing: float = 0.0,
    linked_to: str = "",
    linked_to_module: str = "",
    trigger_size: float = 1.0,
) -> AuthoredGameplayPlacementUpdate:
    """Append one gameplay placement to an authored module project."""

    normalized_kind = _kind(kind)
    if normalized_kind not in SUPPORTED_AUTHORED_GAMEPLAY_PLACEMENTS:
        known = ", ".join(SUPPORTED_AUTHORED_GAMEPLAY_PLACEMENTS)
        raise ValueError(f"Unsupported authored gameplay placement kind '{kind}'. Known kinds: {known}.")
    pos = _vec3(position)
    template = _require_template(normalized_kind, template_resref)
    current_count = len(tuple(getattr(project.placements, f"{normalized_kind}s", ()) or ()))
    label = _tag_or_default(tag, template, normalized_kind, current_count)
    placement, count = _append_placement(
        project.placements,
        kind=normalized_kind,
        template_resref=template,
        tag=label,
        position=pos,
        bearing=float(bearing),
        linked_to=str(linked_to or ""),
        linked_to_module=str(linked_to_module or ""),
        trigger_size=float(trigger_size),
    )
    metadata = {
        "kind": normalized_kind,
        "template_resref": template,
        "tag": label,
        "position": [float(pos[0]), float(pos[1]), float(pos[2])],
    }
    updated = replace(
        project,
        placements=replace(
            placement,
            metadata={
                **dict(placement.metadata),
                "last_gameplay_placement": metadata,
            },
        ),
        notes=tuple(project.notes) + (f"Added Map Studio gameplay placement: {normalized_kind} {label}.",),
        extra={
            **dict(project.extra),
            "last_gameplay_placement": metadata,
        },
    )
    return AuthoredGameplayPlacementUpdate(
        project=updated,
        kind=normalized_kind,
        template_resref=template,
        tag=label,
        position=pos,
        count=count,
    )


__all__ = [
    "AuthoredGameplayPlacementUpdate",
    "SUPPORTED_AUTHORED_GAMEPLAY_PLACEMENTS",
    "add_authored_gameplay_placement",
]
