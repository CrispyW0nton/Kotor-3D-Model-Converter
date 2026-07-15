"""Deterministic PIE entity registry built from authored GIT placements.

Play-in-Editor gameplay simulation needs one stable, headless view of every
placed gameplay object: who can be targeted, how each object is interacted
with, and which authored intent (faction, conversation, transition, lock)
applies.  This registry is derived from the same authored placement instances
the GIT compiler consumes, so entity ids match the Map Studio selection ids
(``authored:<kind>:<instance>``) used everywhere else in the editor.

PIE is an editor simulator, not a KOTOR engine: every field this registry
cannot honestly derive (deep UTC/UTP template state without an inspector,
store commerce, encounters) is reported in ``coverage_warnings`` instead of
being silently guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

Vec3 = tuple[float, float, float]

PIE_ENTITY_KINDS: tuple[str, ...] = (
    "player",
    "creature",
    "door",
    "placeable",
    "trigger",
    "waypoint",
    "sound",
    "camera",
    "store",
)

_FACTION_ROLES = {"hostile", "friendly", "neutral"}


@dataclass(frozen=True)
class PIEEntity:
    """One simulated gameplay object with stable identity and honest intent."""

    entity_id: str
    kind: str
    tag: str
    display_name: str
    template_resref: str
    position: Vec3
    facing: float = 0.0
    faction: str = "neutral"
    interactive: bool = False
    interaction: str = "none"
    locked: bool = False
    key_required: str = ""
    conversation: str = ""
    has_inventory: bool = False
    transition_module: str = ""
    transition_target: str = ""
    geometry: tuple[Vec3, ...] = ()
    movement_mode: str = "stationary"
    target_radius: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PIEEntityRegistry:
    """Deterministically ordered entities plus honest coverage reporting."""

    entities: tuple[PIEEntity, ...] = ()
    coverage_warnings: tuple[str, ...] = ()

    def by_id(self, entity_id: str) -> PIEEntity | None:
        wanted = str(entity_id or "")
        for entity in self.entities:
            if entity.entity_id == wanted:
                return entity
        return None

    def of_kind(self, kind: str) -> tuple[PIEEntity, ...]:
        wanted = str(kind or "").strip().lower()
        return tuple(entity for entity in self.entities if entity.kind == wanted)

    @property
    def interactive_entities(self) -> tuple[PIEEntity, ...]:
        return tuple(entity for entity in self.entities if entity.interactive)


# Interaction footprints, in meters, for focus-circle targeting.  These are
# editor approximations (creature personal space, door width, placeable use
# radius), not engine-extracted values.
_TARGET_RADII = {
    "creature": 0.6,
    "door": 1.0,
    "placeable": 0.7,
    "store": 0.6,
}


def _entity_id(kind: str, index: int, instance: Any) -> str:
    instance_id = str(getattr(instance, "instance_id", "") or "").strip()
    return f"authored:{kind}:{instance_id or index}"


def _vec3(value: Any) -> Vec3:
    values = tuple(value or ())
    if len(values) < 3:
        values = tuple(values) + (0.0,) * (3 - len(values))
    return (float(values[0]), float(values[1]), float(values[2]))


def _display_name(inspected: Mapping[str, Any], instance: Any) -> str:
    name = str(inspected.get("name", "") or "").strip()
    if name:
        return name
    tag = str(getattr(instance, "tag", "") or "").strip()
    return tag or str(getattr(instance, "template_resref", "") or "").strip()


def _inspect(
    template_inspector: Callable[[str, str], Mapping[str, Any]] | None,
    kind: str,
    template_resref: str,
    warnings: list[str],
) -> Mapping[str, Any]:
    if template_inspector is None or not template_resref:
        return {}
    try:
        return dict(template_inspector(kind, template_resref) or {})
    except Exception as exc:
        warnings.append(f"PIE could not inspect {kind} template {template_resref}: {exc}")
        return {}


def build_pie_entity_registry(
    project: Any,
    *,
    template_inspector: Callable[[str, str], Mapping[str, Any]] | None = None,
) -> PIEEntityRegistry:
    """Register every authored gameplay placement for PIE simulation.

    ``template_inspector(kind, resref)`` may supply deep template fields
    (``name``, ``faction``, ``conversation``, ``locked``, ``key_required``,
    ``has_inventory``).  Without one, the registry uses only authored
    instance/behavior data and reports what it could not determine.
    """

    placements = getattr(project, "placements", None)
    warnings: list[str] = []
    entities: list[PIEEntity] = []
    if placements is None:
        return PIEEntityRegistry(coverage_warnings=("Authored project has no gameplay placements.",))

    behaviors = dict((getattr(placements, "metadata", {}) or {}).get("creature_behaviors") or {})

    entry = getattr(placements, "entry_point", None)
    if entry is not None and tuple(getattr(entry, "position", ()) or ()):
        entities.append(
            PIEEntity(
                entity_id="pie:player",
                kind="player",
                tag="player",
                display_name="Player",
                template_resref="",
                position=_vec3(getattr(entry, "position", (0.0, 0.0, 0.0))),
                facing=float(getattr(entry, "facing", 0.0) or 0.0),
                faction="player",
            )
        )
    else:
        warnings.append("PIE has no authored player entry point; the player entity was not registered.")

    for index, creature in enumerate(tuple(getattr(placements, "creatures", ()) or ())):
        entity_id = _entity_id("creature", index, creature)
        behavior = dict(behaviors.get(entity_id) or {})
        inspected = _inspect(template_inspector, "creature", str(creature.template_resref or ""), warnings)
        role = str(behavior.get("faction_role", "") or "").strip().lower()
        if role not in _FACTION_ROLES:
            role = str(inspected.get("faction", "") or "").strip().lower()
        if role not in _FACTION_ROLES:
            role = "neutral"
            warnings.append(
                f"Creature {creature.tag or creature.template_resref} has no authored faction intent; "
                "PIE treats it as neutral."
            )
        conversation = str(
            behavior.get("conversation_resref", "") or inspected.get("conversation", "") or ""
        ).strip()
        interaction = "combat" if role == "hostile" else ("dialogue" if conversation else "none")
        if interaction == "none":
            warnings.append(
                f"Creature {creature.tag or creature.template_resref} is {role} without a conversation; "
                "PIE will only focus it."
            )
        entities.append(
            PIEEntity(
                entity_id=entity_id,
                kind="creature",
                tag=str(creature.tag or ""),
                display_name=_display_name(inspected, creature),
                template_resref=str(creature.template_resref or ""),
                position=_vec3(creature.position),
                facing=float(creature.bearing or 0.0),
                faction=role,
                interactive=True,
                interaction=interaction,
                conversation=conversation,
                movement_mode=str(behavior.get("movement_mode", "stationary") or "stationary"),
                target_radius=_TARGET_RADII["creature"],
            )
        )

    for index, door in enumerate(tuple(getattr(placements, "doors", ()) or ())):
        inspected = _inspect(template_inspector, "door", str(door.template_resref or ""), warnings)
        entities.append(
            PIEEntity(
                entity_id=_entity_id("door", index, door),
                kind="door",
                tag=str(door.tag or ""),
                display_name=_display_name(inspected, door),
                template_resref=str(door.template_resref or ""),
                position=_vec3(door.position),
                facing=float(door.bearing or 0.0),
                interactive=True,
                interaction="door",
                locked=bool(inspected.get("locked", False)),
                key_required=str(inspected.get("key_required", "") or ""),
                conversation=str(inspected.get("conversation", "") or ""),
                transition_module=str(getattr(door, "linked_to_module", "") or ""),
                transition_target=str(getattr(door, "linked_to", "") or ""),
                target_radius=_TARGET_RADII["door"],
            )
        )

    for index, placeable in enumerate(tuple(getattr(placements, "placeables", ()) or ())):
        inspected = _inspect(template_inspector, "placeable", str(placeable.template_resref or ""), warnings)
        has_inventory = bool(inspected.get("has_inventory", False))
        conversation = str(inspected.get("conversation", "") or "").strip()
        if has_inventory:
            interaction = "container"
        elif conversation:
            interaction = "terminal"
        else:
            interaction = "use"
            if template_inspector is not None:
                warnings.append(
                    f"Placeable {placeable.tag or placeable.template_resref} has no inventory or conversation; "
                    "PIE exposes a generic Use action whose scripted OnUsed behavior is not simulated yet."
                )
        entities.append(
            PIEEntity(
                entity_id=_entity_id("placeable", index, placeable),
                kind="placeable",
                tag=str(placeable.tag or ""),
                display_name=_display_name(inspected, placeable),
                template_resref=str(placeable.template_resref or ""),
                position=_vec3(placeable.position),
                facing=float(placeable.bearing or 0.0),
                interactive=True,
                interaction=interaction,
                locked=bool(inspected.get("locked", False)),
                key_required=str(inspected.get("key_required", "") or ""),
                conversation=conversation,
                has_inventory=has_inventory,
                target_radius=_TARGET_RADII["placeable"],
            )
        )

    for index, trigger in enumerate(tuple(getattr(placements, "triggers", ()) or ())):
        entities.append(
            PIEEntity(
                entity_id=_entity_id("trigger", index, trigger),
                kind="trigger",
                tag=str(trigger.tag or ""),
                display_name=str(trigger.tag or trigger.template_resref or ""),
                template_resref=str(trigger.template_resref or ""),
                position=_vec3(trigger.position),
                interactive=False,
                interaction="trigger",
                transition_module=str(getattr(trigger, "linked_to_module", "") or ""),
                transition_target=str(getattr(trigger, "linked_to", "") or ""),
                geometry=tuple(_vec3(point) for point in tuple(getattr(trigger, "geometry", ()) or ())),
            )
        )

    for index, waypoint in enumerate(tuple(getattr(placements, "waypoints", ()) or ())):
        entities.append(
            PIEEntity(
                entity_id=_entity_id("waypoint", index, waypoint),
                kind="waypoint",
                tag=str(waypoint.tag or ""),
                display_name=str(waypoint.tag or waypoint.template_resref or ""),
                template_resref=str(getattr(waypoint, "template_resref", "") or ""),
                position=_vec3(waypoint.position),
                facing=float(getattr(waypoint, "bearing", 0.0) or 0.0),
            )
        )

    for index, sound in enumerate(tuple(getattr(placements, "sounds", ()) or ())):
        entities.append(
            PIEEntity(
                entity_id=_entity_id("sound", index, sound),
                kind="sound",
                tag=str(getattr(sound, "tag", "") or ""),
                display_name=str(getattr(sound, "tag", "") or getattr(sound, "template_resref", "") or ""),
                template_resref=str(getattr(sound, "template_resref", "") or ""),
                position=_vec3(getattr(sound, "position", (0.0, 0.0, 0.0))),
            )
        )

    for index, camera in enumerate(tuple(getattr(placements, "cameras", ()) or ())):
        entities.append(
            PIEEntity(
                entity_id=_entity_id("camera", index, camera),
                kind="camera",
                tag=str(getattr(camera, "tag", "") or ""),
                display_name=str(getattr(camera, "tag", "") or f"camera {getattr(camera, 'camera_id', index)}"),
                template_resref="",
                position=_vec3(getattr(camera, "position", (0.0, 0.0, 0.0))),
                metadata={"camera_id": int(getattr(camera, "camera_id", index) or 0)},
            )
        )

    for index, store in enumerate(tuple(getattr(placements, "stores", ()) or ())):
        entities.append(
            PIEEntity(
                entity_id=_entity_id("store", index, store),
                kind="store",
                tag=str(store.tag or ""),
                display_name=str(store.tag or store.template_resref or ""),
                template_resref=str(store.template_resref or ""),
                position=_vec3(store.position),
                facing=float(getattr(store, "bearing", 0.0) or 0.0),
                interactive=False,
                interaction="none",
                target_radius=_TARGET_RADII["store"],
            )
        )
        warnings.append(
            f"Store {store.tag or store.template_resref} is registered but PIE does not simulate "
            "commerce yet; open it through its owning creature dialogue in the real game."
        )

    encounters = tuple(getattr(placements, "encounters", ()) or ())
    if encounters:
        warnings.append(
            f"{len(encounters)} encounter placement(s) are not simulated by PIE yet."
        )

    order = {kind: rank for rank, kind in enumerate(PIE_ENTITY_KINDS)}
    entities.sort(key=lambda entity: (order.get(entity.kind, len(order)), entity.entity_id))
    return PIEEntityRegistry(
        entities=tuple(entities),
        coverage_warnings=tuple(dict.fromkeys(warnings)),
    )


__all__ = [
    "PIE_ENTITY_KINDS",
    "PIEEntity",
    "PIEEntityRegistry",
    "build_pie_entity_registry",
]
