"""Project-level gameplay placement editing for authored Map Studio modules."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
from typing import Any
from uuid import uuid4

from .authored_module_objects import (
    AuthoredCameraInstance,
    AuthoredCreatureInstance,
    AuthoredDoorInstance,
    AuthoredEncounterInstance,
    AuthoredGameplayPlacement,
    AuthoredPlaceableInstance,
    ModuleEntryPoint,
    AuthoredSoundInstance,
    AuthoredStoreInstance,
    AuthoredTriggerInstance,
    AuthoredWaypointInstance,
    normalise_resource_resref,
)
from .authored_module_project import AuthoredModuleProject, authored_resref_blocking_issue, normalise_resref
from .authored_module_walkmesh import AuthoredWalkmeshSnapResult, snap_position_to_authored_walkmesh


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
class AuthoredModuleEntryPointUpdate:
    """Result of editing the authored module IFO player start."""

    project: AuthoredModuleProject
    area_resref: str
    position: Vec3
    facing: float


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
    linked_to_flags: int = 0
    transition_destination: int = 0
    transition_status: str = "not_applicable"
    transition_summary: str = ""
    camera_id: int | str = ""
    field_of_view: float = 45.0
    height: float = 0.0
    mic_range: float = 0.0
    pitch: float = 0.0
    creature_source_template_resref: str = ""
    creature_behavior_role: str = "template"
    creature_conversation_resref: str = ""
    creature_movement_mode: str = "stationary"
    creature_generated_template_resref: str = ""


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


def new_authored_gameplay_instance_id() -> str:
    """Return a new KMAP-only durable gameplay-instance token."""

    return f"i_{uuid4().hex}"


def _instance_token(value: Any) -> str:
    token = str(value or "").strip()
    if not token or ":" in token:
        return ""
    return token[:96]


def authored_gameplay_placement_id(kind: Any, identity: int | str) -> str:
    """Return the virtual UI id for a durable token or legacy list index."""

    normalized = _kind(kind)
    if normalized not in SUPPORTED_AUTHORED_GAMEPLAY_PLACEMENTS:
        raise ValueError(f"Unsupported authored gameplay placement kind '{kind}'.")
    if isinstance(identity, int):
        if identity < 0:
            raise ValueError("Authored gameplay placement index cannot be negative.")
        token = str(identity)
    else:
        token = _instance_token(identity)
        if not token:
            raise ValueError("Authored gameplay placement identity cannot be empty or contain ':'.")
    return f"authored:{normalized}:{token}"


def parse_authored_gameplay_placement_id(value: Any) -> tuple[str, int | str]:
    """Parse a durable id while accepting legacy ``authored:kind:index`` ids."""

    parts = str(value or "").strip().split(":", 2)
    if len(parts) != 3 or parts[0] != "authored":
        raise ValueError(f"'{value}' is not an authored gameplay placement id.")
    kind = _kind(parts[1])
    if kind not in SUPPORTED_AUTHORED_GAMEPLAY_PLACEMENTS:
        raise ValueError(f"Unsupported authored gameplay placement kind '{parts[1]}'.")
    token = _instance_token(parts[2])
    if not token:
        raise ValueError(f"Authored gameplay placement id '{value}' has an invalid identity token.")
    try:
        index = int(token)
    except ValueError:
        return kind, token
    if index < 0:
        raise ValueError(f"Authored gameplay placement id '{value}' has a negative index.")
    return kind, index


def _canonical_placement_id(kind: str, index: int, item: Any) -> str:
    token = _instance_token(getattr(item, "instance_id", ""))
    return authored_gameplay_placement_id(kind, token if token else index)


def _creature_behavior_records(placement: AuthoredGameplayPlacement) -> dict[str, dict[str, Any]]:
    raw = dict(placement.metadata.get("creature_behaviors") or {})
    return {
        str(key): dict(value)
        for key, value in raw.items()
        if isinstance(value, dict)
    }


def _generated_creature_template_resref(project: AuthoredModuleProject, placement_id: str) -> str:
    """Return a stable, per-instance 16-character UTC resref."""

    digest = hashlib.sha1(
        f"{normalise_resref(project.module_root)}|{str(placement_id)}".encode("utf-8")
    ).hexdigest()
    return f"grc{digest[:13]}"


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
    if kind in {"camera"}:
        return ""
    if not str(template_resref or "").strip():
        raise ValueError(f"{kind.title()} placement requires a template resref.")
    issue = authored_resref_blocking_issue(f"{kind.title()} template", template_resref)
    if issue:
        raise ValueError(issue)
    template = normalise_resource_resref(template_resref)
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
    return str(getattr(item, "tag", "") or _placement_template(item) or _canonical_placement_id(kind, index, item))


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
    kind, identity = parse_authored_gameplay_placement_id(placement_id)
    field_name = _KIND_FIELDS[kind]
    items = list(tuple(getattr(project.placements, field_name, ()) or ()))
    if isinstance(identity, int):
        index = identity
    else:
        index = next(
            (
                candidate_index
                for candidate_index, item in enumerate(items)
                if _instance_token(getattr(item, "instance_id", "")) == identity
            ),
            -1,
        )
    if index < 0 or index >= len(items):
        raise ValueError(f"Authored gameplay placement '{placement_id}' does not exist.")
    return kind, index, field_name, items, items[index]


def _transition_fields_for_item(kind: str, item: Any) -> tuple[bool, str, str, int, int]:
    if kind not in {"door", "trigger"}:
        return False, "", "", 0, 0
    return (
        True,
        str(getattr(item, "linked_to", "") or ""),
        normalise_resref(getattr(item, "linked_to_module", "")),
        int(getattr(item, "linked_to_flags", 0) or 0),
        int(getattr(item, "transition_destination", 0) or 0),
    )


def _transition_status_and_summary(
    *,
    kind: str,
    linked_to: str,
    linked_to_module: str,
    linked_to_flags: int,
) -> tuple[str, str]:
    if kind not in {"door", "trigger"}:
        return "not_applicable", ""
    destination = str(linked_to or "").strip()
    module = normalise_resref(linked_to_module)
    flags = int(linked_to_flags or 0)
    target_label = {1: "door", 2: "waypoint"}.get(flags, "untyped target")
    if destination and flags not in {1, 2}:
        return "missing_link_type", f"Links to {destination}, but target type is not set"
    if destination and module:
        return "module_transition", f"Links to {target_label} {destination} in {module}"
    if destination:
        return "local_transition", f"Links to local {target_label} {destination}"
    if module:
        return "missing_destination", f"Module {module} selected, destination tag missing"
    return "not_configured", "No transition destination set"


def _transition_metadata(
    *,
    placement_id: Any,
    kind: str,
    index: int,
    linked_to: str,
    linked_to_module: str,
    linked_to_flags: int,
    destination: int,
) -> dict[str, Any]:
    return {
        "placement_id": str(placement_id),
        "kind": kind,
        "index": int(index),
        "linked_to": str(linked_to or ""),
        "linked_to_module": normalise_resref(linked_to_module),
        "linked_to_flags": int(linked_to_flags),
        "transition_destination": int(destination),
    }


def authored_gameplay_placement_rows(project: AuthoredModuleProject) -> tuple[AuthoredGameplayPlacementRow, ...]:
    """Return selectable UI rows for authored GIT/IFO gameplay placements."""

    rows: list[AuthoredGameplayPlacementRow] = []
    placement = project.placements
    creature_behaviors = _creature_behavior_records(placement)
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
            transition_capable, linked_to, linked_to_module, linked_to_flags, transition_destination = _transition_fields_for_item(kind, item)
            transition_status, transition_summary = _transition_status_and_summary(
                kind=kind,
                linked_to=linked_to,
                linked_to_module=linked_to_module,
                linked_to_flags=linked_to_flags,
            )
            camera_id = getattr(item, "camera_id", "") if kind == "camera" else ""
            placement_id = _canonical_placement_id(kind, index, item)
            creature_behavior = creature_behaviors.get(placement_id, {}) if kind == "creature" else {}
            rows.append(
                AuthoredGameplayPlacementRow(
                    placement_id=placement_id,
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
                    linked_to_flags=linked_to_flags,
                    transition_destination=transition_destination,
                    transition_status=transition_status,
                    transition_summary=transition_summary,
                    camera_id=camera_id,
                    field_of_view=float(getattr(item, "field_of_view", 45.0) or 0.0) if kind == "camera" else 45.0,
                    height=float(getattr(item, "height", 0.0) or 0.0) if kind == "camera" else 0.0,
                    mic_range=float(getattr(item, "mic_range", 0.0) or 0.0) if kind == "camera" else 0.0,
                    pitch=float(getattr(item, "pitch", 0.0) or 0.0) if kind == "camera" else 0.0,
                    creature_source_template_resref=str(creature_behavior.get("source_template_resref") or ""),
                    creature_behavior_role=str(creature_behavior.get("faction_role") or "template"),
                    creature_conversation_resref=str(creature_behavior.get("conversation_resref") or ""),
                    creature_movement_mode=str(creature_behavior.get("movement_mode") or "stationary"),
                    creature_generated_template_resref=str(creature_behavior.get("generated_template_resref") or ""),
                )
            )
    return tuple(rows)


def update_authored_creature_behavior(
    project: AuthoredModuleProject,
    placement_id: Any,
    *,
    faction_role: Any = "template",
    conversation_resref: Any = "",
    movement_mode: Any = "stationary",
) -> AuthoredGameplayPlacementUpdate:
    """Persist one selected creature's UTC authoring intent in human-readable KMAP state."""

    kind, index, field_name, items, current = _placement_items_for_id(project, placement_id)
    if kind != "creature":
        raise ValueError(f"Authored {kind} placements do not support creature behavior properties.")
    role = str(faction_role or "template").strip().lower().replace("-", "_").replace(" ", "_")
    if role not in {"template", "hostile", "friendly", "neutral"}:
        raise ValueError("Creature role must be template, hostile, friendly, or neutral.")
    movement = str(movement_mode or "stationary").strip().lower().replace("-", "_")
    if movement not in {"stationary", "free_roam"}:
        raise ValueError("Creature movement must be stationary or free_roam.")
    conversation = normalise_resource_resref(conversation_resref)
    if str(conversation_resref or "").strip():
        issue = authored_resref_blocking_issue("Creature conversation", conversation_resref)
        if issue:
            raise ValueError(issue)

    canonical_id = _canonical_placement_id(kind, index, current)
    behavior_records = _creature_behavior_records(project.placements)
    previous = dict(behavior_records.get(canonical_id) or {})
    source_template = normalise_resource_resref(
        previous.get("source_template_resref") or getattr(current, "template_resref", "")
    )
    if not source_template:
        raise ValueError("Creature behavior authoring requires a source UTC template resref.")

    if role == "template":
        updated_item = replace(current, template_resref=source_template)
        behavior_records.pop(canonical_id, None)
        generated_template = ""
    else:
        generated_template = normalise_resource_resref(
            previous.get("generated_template_resref")
            or _generated_creature_template_resref(project, canonical_id)
        )
        updated_item = replace(current, template_resref=generated_template)
        behavior_records[canonical_id] = {
            "schema": "ghostrigger.map_studio.creature_behavior/v1",
            "source_template_resref": source_template,
            "generated_template_resref": generated_template,
            "faction_role": role,
            "conversation_resref": conversation,
            "movement_mode": movement,
        }
    items[index] = updated_item
    metadata = {
        "placement_id": canonical_id,
        "source_template_resref": source_template,
        "generated_template_resref": generated_template,
        "faction_role": role,
        "conversation_resref": conversation,
        "movement_mode": movement,
    }
    placement_metadata = dict(project.placements.metadata)
    if behavior_records:
        placement_metadata["creature_behaviors"] = behavior_records
    else:
        placement_metadata.pop("creature_behaviors", None)
    placement_metadata["last_creature_behavior_update"] = metadata
    updated_placements = replace(
        project.placements,
        **{field_name: tuple(items), "metadata": placement_metadata},
    )
    updated = replace(
        project,
        placements=updated_placements,
        notes=tuple(project.notes) + (f"Updated Map Studio creature behavior: {canonical_id} ({role}, {movement}).",),
        extra={**dict(project.extra), "last_creature_behavior_update": metadata},
    )
    return AuthoredGameplayPlacementUpdate(
        project=updated,
        kind=kind,
        template_resref=updated_item.template_resref,
        tag=_placement_tag(updated_item, kind, index),
        position=_vec3(updated_item.position),
        count=len(items),
        placement_id=canonical_id,
    )


def update_authored_module_entry_point(
    project: AuthoredModuleProject,
    *,
    area_resref: Any = "",
    position: Any = (0.0, 0.0, 0.0),
    facing: float = 0.0,
) -> AuthoredModuleEntryPointUpdate:
    """Update the module entry point/player start that compiles into IFO."""

    area = normalise_resref(area_resref or project.module_root)
    issue = authored_resref_blocking_issue("Module entry area", area)
    if issue:
        raise ValueError(issue)
    pos = _vec3(position)
    entry = ModuleEntryPoint(
        area_resref=area,
        position=pos,
        facing=float(facing),
    )
    metadata = {
        "area_resref": area,
        "position": [float(pos[0]), float(pos[1]), float(pos[2])],
        "facing": float(facing),
    }
    updated_placements = replace(
        project.placements,
        entry_point=entry,
        metadata={
            **dict(project.placements.metadata),
            "last_entry_point_update": metadata,
        },
    )
    updated = replace(
        project,
        placements=updated_placements,
        notes=tuple(project.notes) + (f"Updated Map Studio module entry point: {area}.",),
        extra={
            **dict(project.extra),
            "last_entry_point_update": metadata,
        },
    )
    return AuthoredModuleEntryPointUpdate(
        project=updated,
        area_resref=area,
        position=pos,
        facing=float(facing),
    )


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
    linked_to_flags: int = 0,
    trigger_size: float = 1.0,
) -> tuple[AuthoredGameplayPlacement, int]:
    instance_id = new_authored_gameplay_instance_id()
    if kind == "placeable":
        items = placement.placeables + (AuthoredPlaceableInstance(template_resref=template_resref, tag=tag, position=position, bearing=bearing, instance_id=instance_id),)
        return replace(placement, placeables=items), len(items)
    if kind == "creature":
        items = placement.creatures + (AuthoredCreatureInstance(template_resref=template_resref, tag=tag, position=position, bearing=bearing, instance_id=instance_id),)
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
                linked_to_flags=linked_to_flags,
                instance_id=instance_id,
            ),
        )
        return replace(placement, doors=items), len(items)
    if kind == "waypoint":
        items = placement.waypoints + (AuthoredWaypointInstance(template_resref=template_resref, tag=tag, position=position, bearing=bearing, instance_id=instance_id),)
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
                linked_to_flags=linked_to_flags,
                instance_id=instance_id,
            ),
        )
        return replace(placement, triggers=items), len(items)
    if kind == "encounter":
        items = placement.encounters + (AuthoredEncounterInstance(template_resref=template_resref, tag=tag, position=position, instance_id=instance_id),)
        return replace(placement, encounters=items), len(items)
    if kind == "sound":
        items = placement.sounds + (AuthoredSoundInstance(template_resref=template_resref, tag=tag, position=position, instance_id=instance_id),)
        return replace(placement, sounds=items), len(items)
    if kind == "camera":
        items = placement.cameras + (AuthoredCameraInstance(camera_id=tag or str(len(placement.cameras) + 1), position=position, instance_id=instance_id),)
        return replace(placement, cameras=items), len(items)
    if kind == "store":
        items = placement.stores + (AuthoredStoreInstance(template_resref=template_resref, tag=tag, instance_id=instance_id),)
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
    linked_to_flags: int = 0,
    trigger_size: float = 1.0,
    provenance: dict[str, Any] | None = None,
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
        linked_to_flags=int(linked_to_flags or 0),
        trigger_size=float(trigger_size),
    )
    placement_id = _canonical_placement_id(normalized_kind, count - 1, tuple(getattr(placement, _KIND_FIELDS[normalized_kind]))[-1])
    if provenance:
        safe_provenance = {
            key: str(provenance.get(key) or "").strip()
            for key in ("game", "library_source", "asset_id", "asset_path")
            if str(provenance.get(key) or "").strip()
        }
        if normalized_kind == "placeable" and template:
            safe_provenance["template_resref"] = template
        if safe_provenance:
            by_instance = dict(placement.metadata.get("instance_provenance") or {})
            by_instance[placement_id] = safe_provenance
            placement = replace(
                placement,
                metadata={**dict(placement.metadata), "instance_provenance": by_instance},
            )
    metadata = {
        "placement_id": placement_id,
        "instance_id": placement_id.rsplit(":", 1)[-1],
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
        placement_id=placement_id,
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
    previous_position = _vec3(getattr(current, "position", (0.0, 0.0, 0.0)))
    updated_item = replace(current, position=pos)
    if hasattr(updated_item, "geometry"):
        delta = tuple(pos[axis] - previous_position[axis] for axis in range(3))
        geometry = tuple(
            (
                float(point[0]) + delta[0],
                float(point[1]) + delta[1],
                float(point[2]) + delta[2],
            )
            for point in tuple(getattr(updated_item, "geometry", ()) or ())
            if len(point) >= 3
        )
        updated_item = replace(updated_item, geometry=geometry)
    if bearing is not None and hasattr(updated_item, "bearing"):
        updated_item = replace(updated_item, bearing=float(bearing))
    items[index] = updated_item
    canonical_id = _canonical_placement_id(kind, index, updated_item)
    transform_metadata = {
        "placement_id": canonical_id,
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
        placement_id=canonical_id,
    )


def snap_authored_gameplay_placement_to_walkmesh(
    project: AuthoredModuleProject,
    placement_id: Any,
    *,
    max_horizontal_distance: float | None = None,
    downward_only: bool = False,
) -> tuple[AuthoredGameplayPlacementUpdate, AuthoredWalkmeshSnapResult]:
    """Move one spatial GIT placement onto the nearest walkable authored WOK."""

    _kind_name, _index, _field_name, _items, current = _placement_items_for_id(project, placement_id)
    if not hasattr(current, "position"):
        raise ValueError(f"Authored gameplay placement '{placement_id}' is not a spatial map object.")
    snap = snap_position_to_authored_walkmesh(
        project,
        getattr(current, "position", (0.0, 0.0, 0.0)),
        max_horizontal_distance=max_horizontal_distance,
        downward_only=bool(downward_only),
    )
    if snap is None:
        raise ValueError("No walkable authored WOK face is available for this placement.")
    update = update_authored_gameplay_placement_transform(project, placement_id, position=snap.position)
    return update, snap


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
    canonical_id = _canonical_placement_id(kind, index, updated_item)
    metadata = {
        "placement_id": canonical_id,
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
        placement_id=canonical_id,
    )


def update_authored_gameplay_transition(
    project: AuthoredModuleProject,
    placement_id: Any,
    *,
    linked_to: Any = "",
    linked_to_module: Any = "",
    linked_to_flags: Any = 0,
    transition_destination: Any = 0,
) -> AuthoredGameplayPlacementUpdate:
    """Set transition destination fields for an authored door or trigger."""

    kind, index, field_name, items, current = _placement_items_for_id(project, placement_id)
    if kind not in {"door", "trigger"}:
        raise ValueError(f"Authored {kind} placements do not support transition destination fields.")
    destination_tag = str(linked_to or "").strip()[:64]
    module = normalise_resref(linked_to_module)
    if str(linked_to_module or "").strip():
        issue = authored_resref_blocking_issue("Transition destination module", linked_to_module)
        if issue:
            raise ValueError(issue)
    try:
        flags = int(linked_to_flags or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("Transition target type must be 0 (none), 1 (door), or 2 (waypoint).") from exc
    if flags not in {0, 1, 2}:
        raise ValueError("Transition target type must be 0 (none), 1 (door), or 2 (waypoint).")
    try:
        destination = int(transition_destination or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("Transition destination must be an integer.") from exc
    if destination < 0:
        raise ValueError("Transition destination cannot be negative.")
    if destination > 2147483647:
        raise ValueError("Transition destination StringRef cannot exceed 2147483647.")

    updated_item = replace(
        current,
        linked_to=destination_tag,
        linked_to_module=module,
        linked_to_flags=flags,
        transition_destination=destination,
    )
    items[index] = updated_item
    canonical_id = _canonical_placement_id(kind, index, updated_item)
    metadata = _transition_metadata(
        placement_id=canonical_id,
        kind=kind,
        index=index,
        linked_to=destination_tag,
        linked_to_module=module,
        linked_to_flags=flags,
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
        placement_id=canonical_id,
    )


def update_authored_gameplay_camera_properties(
    project: AuthoredModuleProject,
    placement_id: Any,
    *,
    camera_id: Any | None = None,
    field_of_view: Any | None = None,
    height: Any | None = None,
    mic_range: Any | None = None,
    pitch: Any | None = None,
) -> AuthoredGameplayPlacementUpdate:
    """Set KOTOR GIT CameraList fields for a selected authored camera."""

    kind, index, field_name, items, current = _placement_items_for_id(project, placement_id)
    if kind != "camera":
        raise ValueError(f"Authored {kind} placements do not support camera properties.")

    def _camera_id(value: Any) -> int:
        try:
            numeric = int(str(value).strip(), 10)
        except (TypeError, ValueError) as exc:
            raise ValueError("Camera ID must be a non-negative integer.") from exc
        if numeric < 0:
            raise ValueError("Camera ID must be a non-negative integer.")
        return numeric

    def _finite(value: Any, label: str, *, minimum: float | None = None) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a finite number.") from exc
        if not math.isfinite(numeric):
            raise ValueError(f"{label} must be a finite number.")
        if minimum is not None and numeric < minimum:
            raise ValueError(f"{label} must be at least {minimum:g}.")
        return numeric

    updated_item = current
    if camera_id is not None:
        updated_item = replace(updated_item, camera_id=_camera_id(camera_id))
    if field_of_view is not None:
        updated_item = replace(updated_item, field_of_view=_finite(field_of_view, "Camera field of view", minimum=0.0))
    if height is not None:
        updated_item = replace(updated_item, height=_finite(height, "Camera height"))
    if mic_range is not None:
        updated_item = replace(updated_item, mic_range=_finite(mic_range, "Camera mic range", minimum=0.0))
    if pitch is not None:
        updated_item = replace(updated_item, pitch=_finite(pitch, "Camera pitch"))
    items[index] = updated_item
    canonical_id = _canonical_placement_id(kind, index, updated_item)
    metadata = {
        "placement_id": canonical_id,
        "kind": kind,
        "index": index,
        "camera_id": str(updated_item.camera_id),
        "field_of_view": float(updated_item.field_of_view),
        "height": float(updated_item.height),
        "mic_range": float(updated_item.mic_range),
        "pitch": float(updated_item.pitch),
    }
    updated_placements = replace(
        project.placements,
        **{
            field_name: tuple(items),
            "metadata": {
                **dict(project.placements.metadata),
                "last_gameplay_camera_properties": metadata,
            },
        },
    )
    updated = replace(
        project,
        placements=updated_placements,
        notes=tuple(project.notes) + (f"Updated Map Studio camera placement: {placement_id}.",),
        extra={
            **dict(project.extra),
            "last_gameplay_camera_properties": metadata,
        },
    )
    return AuthoredGameplayPlacementUpdate(
        project=updated,
        kind=kind,
        template_resref=_placement_template(updated_item),
        tag=_placement_tag(updated_item, kind, index),
        position=_vec3(getattr(updated_item, "position", (0.0, 0.0, 0.0))),
        count=len(items),
        placement_id=canonical_id,
    )


def duplicate_authored_gameplay_placement(
    project: AuthoredModuleProject,
    placement_id: Any,
) -> AuthoredGameplayPlacementUpdate:
    """Duplicate one authored gameplay placement selected in Map Studio."""

    kind, index, field_name, items, current = _placement_items_for_id(project, placement_id)
    duplicated = replace(
        _offset_position(_with_label(current, _copy_label(_placement_tag(current, kind, index), kind, len(items)))),
        instance_id=new_authored_gameplay_instance_id(),
    )
    items.append(duplicated)
    new_index = len(items) - 1
    new_id = _canonical_placement_id(kind, new_index, duplicated)
    source_id = _canonical_placement_id(kind, index, current)
    placement_metadata = dict(project.placements.metadata)
    creature_behaviors = _creature_behavior_records(project.placements)
    if kind == "creature" and source_id in creature_behaviors:
        duplicated_behavior = dict(creature_behaviors[source_id])
        generated_template = _generated_creature_template_resref(project, new_id)
        duplicated_behavior["generated_template_resref"] = generated_template
        creature_behaviors[new_id] = duplicated_behavior
        duplicated = replace(duplicated, template_resref=generated_template)
        items[new_index] = duplicated
        placement_metadata["creature_behaviors"] = creature_behaviors
    provenance = dict(placement_metadata.get("instance_provenance") or {})
    if source_id in provenance:
        provenance[new_id] = dict(provenance[source_id])
        placement_metadata["instance_provenance"] = provenance
    metadata = {
        "source_placement_id": source_id,
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
                **placement_metadata,
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
    canonical_id = _canonical_placement_id(kind, index, current)
    placement_metadata = dict(project.placements.metadata)
    creature_behaviors = _creature_behavior_records(project.placements)
    creature_behaviors.pop(canonical_id, None)
    if creature_behaviors:
        placement_metadata["creature_behaviors"] = creature_behaviors
    else:
        placement_metadata.pop("creature_behaviors", None)
    provenance = dict(placement_metadata.get("instance_provenance") or {})
    provenance.pop(canonical_id, None)
    if provenance:
        placement_metadata["instance_provenance"] = provenance
    else:
        placement_metadata.pop("instance_provenance", None)
    del items[index]
    metadata = {
        "placement_id": canonical_id,
        "kind": kind,
        "index": index,
        "tag": removed_tag,
    }
    updated_placements = replace(
        project.placements,
        **{
            field_name: tuple(items),
            "metadata": {
                **placement_metadata,
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
    "AuthoredModuleEntryPointUpdate",
    "AuthoredGameplayPlacementRow",
    "AuthoredGameplayPlacementUpdate",
    "SUPPORTED_AUTHORED_GAMEPLAY_PLACEMENTS",
    "add_authored_gameplay_placement",
    "authored_gameplay_placement_id",
    "authored_gameplay_placement_rows",
    "duplicate_authored_gameplay_placement",
    "new_authored_gameplay_instance_id",
    "parse_authored_gameplay_placement_id",
    "remove_authored_gameplay_placement",
    "rename_authored_gameplay_placement",
    "update_authored_module_entry_point",
    "update_authored_creature_behavior",
    "update_authored_gameplay_camera_properties",
    "update_authored_gameplay_placement_transform",
    "update_authored_gameplay_transition",
]
