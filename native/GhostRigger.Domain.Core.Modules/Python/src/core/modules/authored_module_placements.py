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
from .authored_module_project import AuthoredModuleProject, authored_resref_blocking_issue, normalise_resref


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
    placement_id: str = ""


@dataclass(frozen=True)
class AuthoredGameplayPlacementRow:
    """Selectable authored gameplay object projected into Map Studio UI."""

    placement_id: str
    kind: str
    index: int
    template_resref: str
    tag: str
    position: Vec3
    bearing: float = 0.0
    is_spatial: bool = True
    transition_capable: bool = False
    linked_to: str = ""
    linked_to_module: str = ""
    transition_destination: int = 0


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


_KIND_FIELDS: dict[str, str] = {
    "placeable": "placeables",
    "creature": "creatures",
    "door": "doors",
    "waypoint": "waypoints",
    "trigger": "triggers",
    "encounter": "encounters",
    "sound": "sounds",
    "camera": "cameras",
    "store": "stores",
}


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


def authored_gameplay_placement_id(kind: Any, index: int) -> str:
    """Return the stable virtual UI id for one authored gameplay placement."""

    normalized = _kind(kind)
    if normalized not in SUPPORTED_AUTHORED_GAMEPLAY_PLACEMENTS:
        raise ValueError(f"Unsupported authored gameplay placement kind '{kind}'.")
    return f"authored:{normalized}:{int(index)}"


def parse_authored_gameplay_placement_id(value: Any) -> tuple[str, int]:
    """Parse a virtual id like ``authored:placeable:0``."""

    parts = str(value or "").strip().split(":")
    if len(parts) != 3 or parts[0] != "authored":
        raise ValueError(f"'{value}' is not an authored gameplay placement id.")
    kind = _kind(parts[1])
    if kind not in SUPPORTED_AUTHORED_GAMEPLAY_PLACEMENTS:
        raise ValueError(f"Unsupported authored gameplay placement kind '{parts[1]}'.")
    try:
        index = int(parts[2])
    except ValueError as exc:
        raise ValueError(f"Authored gameplay placement id '{value}' has an invalid index.") from exc
    if index < 0:
        raise ValueError(f"Authored gameplay placement id '{value}' has a negative index.")
    return kind, index


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


def _placement_template(item: Any) -> str:
    return str(getattr(item, "template_resref", getattr(item, "camera_id", "")) or "")


def _placement_tag(item: Any, kind: str, index: int) -> str:
    return str(getattr(item, "tag", "") or _placement_template(item) or authored_gameplay_placement_id(kind, index))


def _copy_label(label: str, kind: str, count: int) -> str:
    base = str(label or "").strip() or f"{kind}_{count + 1}"
    suffix = "_copy"
    if len(base) + len(suffix) <= 32:
        return f"{base}{suffix}"
    return f"{base[: 32 - len(suffix)]}{suffix}"


def _with_label(item: Any, label: str) -> Any:
    if hasattr(item, "tag"):
        return replace(item, tag=label)
    if hasattr(item, "camera_id"):
        return replace(item, camera_id=label)
    return item


def _offset_position(item: Any, offset: Vec3 = (0.5, 0.5, 0.0)) -> Any:
    if not hasattr(item, "position"):
        return item
    pos = _vec3(getattr(item, "position", (0.0, 0.0, 0.0)))
    moved = (pos[0] + offset[0], pos[1] + offset[1], pos[2] + offset[2])
    updated = replace(item, position=moved)
    if hasattr(updated, "geometry"):
        geometry = tuple(
            (float(point[0]) + offset[0], float(point[1]) + offset[1], float(point[2]) + offset[2])
            for point in tuple(getattr(updated, "geometry", ()) or ())
            if len(point) >= 3
        )
        updated = replace(updated, geometry=geometry)
    return updated


def _placement_items_for_id(project: AuthoredModuleProject, placement_id: Any) -> tuple[str, int, str, list[Any], Any]:
    kind, index = parse_authored_gameplay_placement_id(placement_id)
    field_name = _KIND_FIELDS[kind]
    items = list(tuple(getattr(project.placements, field_name, ()) or ()))
    if index >= len(items):
        raise ValueError(f"Authored gameplay placement '{placement_id}' does not exist.")
    return kind, index, field_name, items, items[index]


def _transition_fields_for_item(kind: str, item: Any) -> tuple[bool, str, str, int]:
    if kind not in {"door", "trigger", "waypoint"}:
        return False, "", "", 0
    return (
        True,
        str(getattr(item, "linked_to", "") or ""),
        normalise_resref(getattr(item, "linked_to_module", "")) if hasattr(item, "linked_to_module") else "",
        int(getattr(item, "transition_destination", 0) or 0),
    )


def _transition_metadata(*, placement_id: Any, kind: str, index: int, linked_to: str, linked_to_module: str, destination: int) -> dict[str, Any]:
    return {
        "placement_id": str(placement_id),
        "kind": kind,
        "index": int(index),
        "linked_to": str(linked_to or ""),
        "linked_to_module": normalise_resref(linked_to_module),
        "transition_destination": int(destination),
    }


def authored_gameplay_placement_rows(project: AuthoredModuleProject) -> tuple[AuthoredGameplayPlacementRow, ...]:
    """Return selectable UI rows for authored GIT/IFO gameplay placements."""

    rows: list[AuthoredGameplayPlacementRow] = []
    placement = project.placements
    for kind, field_name in _KIND_FIELDS.items():
        for index, item in enumerate(tuple(getattr(placement, field_name, ()) or ())):
            is_spatial = hasattr(item, "position")
            if is_spatial:
                try:
                    position = _vec3(getattr(item, "position", (0.0, 0.0, 0.0)))
                except ValueError:
                    position = (0.0, 0.0, 0.0)
            else:
                position = (0.0, 0.0, 0.0)
            transition_capable, linked_to, linked_to_module, transition_destination = _transition_fields_for_item(kind, item)
            rows.append(
                AuthoredGameplayPlacementRow(
                    placement_id=authored_gameplay_placement_id(kind, index),
                    kind=kind,
                    index=index,
                    template_resref=_placement_template(item),
                    tag=_placement_tag(item, kind, index),
                    position=position,
                    bearing=float(getattr(item, "bearing", 0.0) or 0.0),
                    is_spatial=is_spatial,
                    transition_capable=transition_capable,
                    linked_to=linked_to,
                    linked_to_module=linked_to_module,
                    transition_destination=transition_destination,
                )
            )
    return tuple(rows)


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
        placement_id=authored_gameplay_placement_id(normalized_kind, count - 1),
    )


def update_authored_gameplay_placement_transform(
    project: AuthoredModuleProject,
    placement_id: Any,
    *,
    position: Any | None = None,
    bearing: float | None = None,
) -> AuthoredGameplayPlacementUpdate:
    """Move/rotate one authored gameplay placement selected in Map Studio."""

    kind, index, field_name, items, current = _placement_items_for_id(project, placement_id)
    if not hasattr(current, "position"):
        raise ValueError(f"Authored gameplay placement '{placement_id}' is not a spatial map object.")
    pos = _vec3(position) if position is not None else _vec3(getattr(current, "position", (0.0, 0.0, 0.0)))
    updated_item = replace(current, position=pos)
    if bearing is not None and hasattr(updated_item, "bearing"):
        updated_item = replace(updated_item, bearing=float(bearing))
    items[index] = updated_item
    transform_metadata = {
        "placement_id": str(placement_id),
        "kind": kind,
        "index": index,
        "position": [float(pos[0]), float(pos[1]), float(pos[2])],
        "bearing": float(getattr(updated_item, "bearing", 0.0) or 0.0),
    }
    updated_placements = replace(
        project.placements,
        **{
            field_name: tuple(items),
            "metadata": {
                **dict(project.placements.metadata),
                "last_gameplay_placement_transform": transform_metadata,
            },
        },
    )
    updated = replace(
        project,
        placements=updated_placements,
        notes=tuple(project.notes) + (f"Moved Map Studio gameplay placement: {placement_id}.",),
        extra={
            **dict(project.extra),
            "last_gameplay_placement_transform": transform_metadata,
        },
    )
    return AuthoredGameplayPlacementUpdate(
        project=updated,
        kind=kind,
        template_resref=_placement_template(updated_item),
        tag=_placement_tag(updated_item, kind, index),
        position=pos,
        count=len(items),
        placement_id=authored_gameplay_placement_id(kind, index),
    )


def rename_authored_gameplay_placement(
    project: AuthoredModuleProject,
    placement_id: Any,
    *,
    tag: Any,
) -> AuthoredGameplayPlacementUpdate:
    """Rename one authored gameplay placement selected in Map Studio."""

    label = str(tag or "").strip()[:32]
    if not label:
        raise ValueError("Authored gameplay placement name cannot be empty.")
    kind, index, field_name, items, current = _placement_items_for_id(project, placement_id)
    updated_item = _with_label(current, label)
    items[index] = updated_item
    metadata = {
        "placement_id": str(placement_id),
        "kind": kind,
        "index": index,
        "tag": label,
    }
    updated_placements = replace(
        project.placements,
        **{
            field_name: tuple(items),
            "metadata": {
                **dict(project.placements.metadata),
                "last_gameplay_placement_rename": metadata,
            },
        },
    )
    updated = replace(
        project,
        placements=updated_placements,
        notes=tuple(project.notes) + (f"Renamed Map Studio gameplay placement: {placement_id} to {label}.",),
        extra={
            **dict(project.extra),
            "last_gameplay_placement_rename": metadata,
        },
    )
    position = _vec3(getattr(updated_item, "position", (0.0, 0.0, 0.0))) if hasattr(updated_item, "position") else (0.0, 0.0, 0.0)
    return AuthoredGameplayPlacementUpdate(
        project=updated,
        kind=kind,
        template_resref=_placement_template(updated_item),
        tag=_placement_tag(updated_item, kind, index),
        position=position,
        count=len(items),
        placement_id=authored_gameplay_placement_id(kind, index),
    )


def update_authored_gameplay_transition(
    project: AuthoredModuleProject,
    placement_id: Any,
    *,
    linked_to: Any = "",
    linked_to_module: Any = "",
    transition_destination: Any = 0,
) -> AuthoredGameplayPlacementUpdate:
    """Set transition destination fields for an authored door, trigger, or waypoint."""

    kind, index, field_name, items, current = _placement_items_for_id(project, placement_id)
    if kind not in {"door", "trigger", "waypoint"}:
        raise ValueError(f"Authored {kind} placements do not support transition destination fields.")
    destination_tag = str(linked_to or "").strip()[:64]
    module = normalise_resref(linked_to_module)
    if str(linked_to_module or "").strip():
        issue = authored_resref_blocking_issue("Transition destination module", linked_to_module)
        if issue:
            raise ValueError(issue)
    try:
        destination = int(transition_destination or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("Transition destination must be an integer.") from exc
    if destination < 0:
        raise ValueError("Transition destination cannot be negative.")

    updated_item = replace(current, linked_to=destination_tag)
    if hasattr(updated_item, "linked_to_module"):
        updated_item = replace(updated_item, linked_to_module=module)
    if hasattr(updated_item, "transition_destination"):
        updated_item = replace(updated_item, transition_destination=destination)
    items[index] = updated_item
    metadata = _transition_metadata(
        placement_id=placement_id,
        kind=kind,
        index=index,
        linked_to=destination_tag,
        linked_to_module=module,
        destination=destination,
    )
    updated_placements = replace(
        project.placements,
        **{
            field_name: tuple(items),
            "metadata": {
                **dict(project.placements.metadata),
                "last_gameplay_transition": metadata,
            },
        },
    )
    updated = replace(
        project,
        placements=updated_placements,
        notes=tuple(project.notes) + (f"Updated Map Studio transition: {placement_id}.",),
        extra={
            **dict(project.extra),
            "last_gameplay_transition": metadata,
        },
    )
    position = _vec3(getattr(updated_item, "position", (0.0, 0.0, 0.0))) if hasattr(updated_item, "position") else (0.0, 0.0, 0.0)
    return AuthoredGameplayPlacementUpdate(
        project=updated,
        kind=kind,
        template_resref=_placement_template(updated_item),
        tag=_placement_tag(updated_item, kind, index),
        position=position,
        count=len(items),
        placement_id=authored_gameplay_placement_id(kind, index),
    )


def duplicate_authored_gameplay_placement(
    project: AuthoredModuleProject,
    placement_id: Any,
) -> AuthoredGameplayPlacementUpdate:
    """Duplicate one authored gameplay placement selected in Map Studio."""

    kind, index, field_name, items, current = _placement_items_for_id(project, placement_id)
    duplicated = _offset_position(_with_label(current, _copy_label(_placement_tag(current, kind, index), kind, len(items))))
    items.append(duplicated)
    new_index = len(items) - 1
    new_id = authored_gameplay_placement_id(kind, new_index)
    metadata = {
        "source_placement_id": str(placement_id),
        "placement_id": new_id,
        "kind": kind,
        "index": new_index,
        "tag": _placement_tag(duplicated, kind, new_index),
    }
    updated_placements = replace(
        project.placements,
        **{
            field_name: tuple(items),
            "metadata": {
                **dict(project.placements.metadata),
                "last_gameplay_placement_duplicate": metadata,
            },
        },
    )
    updated = replace(
        project,
        placements=updated_placements,
        notes=tuple(project.notes) + (f"Duplicated Map Studio gameplay placement: {placement_id} to {new_id}.",),
        extra={
            **dict(project.extra),
            "last_gameplay_placement_duplicate": metadata,
        },
    )
    position = _vec3(getattr(duplicated, "position", (0.0, 0.0, 0.0))) if hasattr(duplicated, "position") else (0.0, 0.0, 0.0)
    return AuthoredGameplayPlacementUpdate(
        project=updated,
        kind=kind,
        template_resref=_placement_template(duplicated),
        tag=_placement_tag(duplicated, kind, new_index),
        position=position,
        count=len(items),
        placement_id=new_id,
    )


def remove_authored_gameplay_placement(
    project: AuthoredModuleProject,
    placement_id: Any,
) -> AuthoredGameplayPlacementUpdate:
    """Remove one authored gameplay placement selected in Map Studio."""

    kind, index, field_name, items, current = _placement_items_for_id(project, placement_id)
    removed_tag = _placement_tag(current, kind, index)
    removed_template = _placement_template(current)
    removed_position = _vec3(getattr(current, "position", (0.0, 0.0, 0.0))) if hasattr(current, "position") else (0.0, 0.0, 0.0)
    del items[index]
    metadata = {
        "placement_id": str(placement_id),
        "kind": kind,
        "index": index,
        "tag": removed_tag,
    }
    updated_placements = replace(
        project.placements,
        **{
            field_name: tuple(items),
            "metadata": {
                **dict(project.placements.metadata),
                "last_gameplay_placement_remove": metadata,
            },
        },
    )
    updated = replace(
        project,
        placements=updated_placements,
        notes=tuple(project.notes) + (f"Removed Map Studio gameplay placement: {placement_id}.",),
        extra={
            **dict(project.extra),
            "last_gameplay_placement_remove": metadata,
        },
    )
    return AuthoredGameplayPlacementUpdate(
        project=updated,
        kind=kind,
        template_resref=removed_template,
        tag=removed_tag,
        position=removed_position,
        count=len(items),
        placement_id="",
    )


__all__ = [
    "AuthoredGameplayPlacementRow",
    "AuthoredGameplayPlacementUpdate",
    "SUPPORTED_AUTHORED_GAMEPLAY_PLACEMENTS",
    "add_authored_gameplay_placement",
    "authored_gameplay_placement_id",
    "authored_gameplay_placement_rows",
    "duplicate_authored_gameplay_placement",
    "parse_authored_gameplay_placement_id",
    "remove_authored_gameplay_placement",
    "rename_authored_gameplay_placement",
    "update_authored_gameplay_placement_transform",
    "update_authored_gameplay_transition",
]
