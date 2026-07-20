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
    focusable: bool = False
    interactive: bool = False
    interaction: str = "none"
    actions: tuple[str, ...] = ()
    locked: bool = False
    key_required: str = ""
    auto_remove_key: bool = False
    conversation: str = ""
    has_inventory: bool = False
    inventory_items: tuple[dict[str, Any], ...] = ()
    useable: bool = True
    plot: bool = False
    current_hp: int = 0
    max_hp: int = 0
    armor_class: int = 10
    attack_bonus: int = 0
    damage_min: int = 1
    damage_max: int = 6
    critical_threat: int = 1
    critical_multiplier: int = 2
    damage_type: str = "Physical"
    initiative_bonus: int = 0
    scripts: tuple[tuple[str, str], ...] = ()
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


def _resolved_tag(inspected: Mapping[str, Any], instance: Any) -> str:
    """Return the runtime Tag, preserving an explicit authored override.

    Imported GIT placements commonly leave ``tag`` blank because the Odyssey
    runtime identity lives on the referenced UTC/UTP/UTD template.  The PIE
    template inspector projects that source Tag as ``inspected["tag"]``.
    """

    authored = str(getattr(instance, "tag", "") or "").strip()
    if authored:
        return authored
    return str(inspected.get("tag", "") or "").strip()


def _display_name(inspected: Mapping[str, Any], instance: Any) -> str:
    name = str(inspected.get("name", "") or "").strip()
    if name:
        return name
    tag = _resolved_tag(inspected, instance)
    return tag or str(getattr(instance, "template_resref", "") or "").strip()


def _inventory_items(inspected: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for raw in tuple(inspected.get("inventory_items") or ()):
        if isinstance(raw, Mapping):
            row = dict(raw)
            resref = str(row.get("resref") or "").strip().lower()
        else:
            resref = str(getattr(raw, "resref", raw) or "").strip().lower()
            row = {"resref": resref}
        if not resref:
            continue
        row["resref"] = resref
        row["count"] = max(1, int(row.get("count", 1) or 1))
        rows.append(row)
    return tuple(rows)


def _faction_role(inspected: Mapping[str, Any]) -> str:
    explicit = str(inspected.get("faction", "") or "").strip().lower()
    if explicit in _FACTION_ROLES:
        return explicit
    try:
        faction_id = int(inspected.get("faction_id"))
    except (TypeError, ValueError):
        return ""
    if faction_id in {1, 3}:
        return "hostile"
    if faction_id in {0, 2, 4}:
        return "friendly"
    if faction_id == 5:
        return "neutral"
    return ""


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
            role = _faction_role(inspected)
        if role not in _FACTION_ROLES:
            role = "neutral"
            warnings.append(
                f"Creature {creature.tag or creature.template_resref} has no authored faction intent; "
                "PIE treats it as neutral."
            )
        conversation = str(
            behavior.get("conversation_resref", "") or inspected.get("conversation", "") or ""
        ).strip()
        actions: list[str] = []
        if role == "hostile":
            actions.append("attack")
        if conversation:
            actions.append("talk")
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
                tag=_resolved_tag(inspected, creature),
                display_name=_display_name(inspected, creature),
                template_resref=str(creature.template_resref or ""),
                position=_vec3(creature.position),
                facing=float(creature.bearing or 0.0),
                faction=role,
                focusable=True,
                interactive=True,
                interaction=interaction,
                actions=tuple(actions),
                conversation=conversation,
                has_inventory=bool(inspected.get("inventory_items")),
                inventory_items=_inventory_items(inspected),
                useable=bool(inspected.get("party_interact", True)),
                plot=bool(inspected.get("plot", False)),
                current_hp=max(0, int(inspected.get("current_hp", 0) or 0)),
                max_hp=max(0, int(inspected.get("max_hp", 0) or 0)),
                armor_class=max(1, int(inspected.get("armor_class", 10) or 10)),
                attack_bonus=int(inspected.get("attack_bonus", 0) or 0),
                damage_min=max(1, int(inspected.get("damage_min", 1) or 1)),
                damage_max=max(1, int(inspected.get("damage_max", 6) or 6)),
                critical_threat=max(1, int(inspected.get("critical_threat", 1) or 1)),
                critical_multiplier=max(1, int(inspected.get("critical_multiplier", 2) or 2)),
                damage_type=str(inspected.get("damage_type", "Physical") or "Physical"),
                initiative_bonus=int(inspected.get("initiative_bonus", 0) or 0),
                scripts=tuple(tuple(row) for row in tuple(inspected.get("scripts") or ())),
                movement_mode=str(behavior.get("movement_mode", "stationary") or "stationary"),
                target_radius=_TARGET_RADII["creature"],
                metadata=dict(inspected),
            )
        )

    for index, door in enumerate(tuple(getattr(placements, "doors", ()) or ())):
        inspected = _inspect(template_inspector, "door", str(door.template_resref or ""), warnings)
        entities.append(
            PIEEntity(
                entity_id=_entity_id("door", index, door),
                kind="door",
                tag=_resolved_tag(inspected, door),
                display_name=_display_name(inspected, door),
                template_resref=str(door.template_resref or ""),
                position=_vec3(door.position),
                facing=float(door.bearing or 0.0),
                focusable=True,
                interactive=True,
                interaction="door",
                actions=tuple(
                    action
                    for action in ("open_door", "talk" if str(inspected.get("conversation", "") or "") else "")
                    if action
                ),
                locked=bool(getattr(door, "locked", inspected.get("locked", False))),
                key_required=str(inspected.get("key_required", "") or ""),
                auto_remove_key=bool(inspected.get("auto_remove_key", False)),
                conversation=str(inspected.get("conversation", "") or ""),
                plot=bool(inspected.get("plot", False)),
                current_hp=max(0, int(inspected.get("current_hp", 0) or 0)),
                max_hp=max(0, int(inspected.get("max_hp", 0) or 0)),
                armor_class=max(1, int(inspected.get("armor_class", 10) or 10)),
                scripts=tuple(tuple(row) for row in tuple(inspected.get("scripts") or ())),
                transition_module=str(getattr(door, "linked_to_module", "") or ""),
                transition_target=str(getattr(door, "linked_to", "") or ""),
                target_radius=_TARGET_RADII["door"],
                metadata=dict(inspected),
            )
        )

    for index, placeable in enumerate(tuple(getattr(placements, "placeables", ()) or ())):
        inspected = _inspect(template_inspector, "placeable", str(placeable.template_resref or ""), warnings)
        has_inventory = bool(inspected.get("has_inventory", False))
        conversation = str(inspected.get("conversation", "") or "").strip()
        useable = bool(inspected.get("useable", True))
        actions: list[str] = []
        if has_inventory:
            actions.append("open_container")
        if conversation:
            actions.append("use_terminal")
        if useable and not conversation:
            actions.append("use_placeable")
        if has_inventory:
            interaction = "container"
        elif conversation:
            interaction = "terminal"
        elif useable:
            interaction = "use"
            if template_inspector is not None:
                warnings.append(
                    f"Placeable {placeable.tag or placeable.template_resref} has no inventory or conversation; "
                    "PIE exposes a generic Use action whose scripted OnUsed behavior is not simulated yet."
                )
        else:
            interaction = "none"
        entities.append(
            PIEEntity(
                entity_id=_entity_id("placeable", index, placeable),
                kind="placeable",
                tag=_resolved_tag(inspected, placeable),
                display_name=_display_name(inspected, placeable),
                template_resref=str(placeable.template_resref or ""),
                position=_vec3(placeable.position),
                facing=float(placeable.bearing or 0.0),
                focusable=bool(actions),
                interactive=bool(actions),
                interaction=interaction,
                actions=tuple(actions),
                locked=bool(inspected.get("locked", False)),
                key_required=str(inspected.get("key_required", "") or ""),
                auto_remove_key=bool(inspected.get("auto_remove_key", False)),
                conversation=conversation,
                has_inventory=has_inventory,
                inventory_items=_inventory_items(inspected),
                useable=useable,
                plot=bool(inspected.get("plot", False)),
                current_hp=max(0, int(inspected.get("current_hp", 0) or 0)),
                max_hp=max(0, int(inspected.get("max_hp", 0) or 0)),
                armor_class=max(1, int(inspected.get("armor_class", 10) or 10)),
                scripts=tuple(tuple(row) for row in tuple(inspected.get("scripts") or ())),
                target_radius=_TARGET_RADII["placeable"],
                metadata=dict(inspected),
            )
        )

    for index, trigger in enumerate(tuple(getattr(placements, "triggers", ()) or ())):
        inspected = _inspect(template_inspector, "trigger", str(trigger.template_resref or ""), warnings)
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
                scripts=tuple(tuple(row) for row in tuple(inspected.get("scripts") or ())),
                metadata=dict(inspected),
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
        orientation = tuple(float(value) for value in tuple(getattr(camera, "orientation", ()) or ())[:4])
        entities.append(
            PIEEntity(
                entity_id=_entity_id("camera", index, camera),
                kind="camera",
                tag=str(getattr(camera, "tag", "") or ""),
                display_name=str(getattr(camera, "tag", "") or f"camera {getattr(camera, 'camera_id', index)}"),
                template_resref="",
                position=_vec3(getattr(camera, "position", (0.0, 0.0, 0.0))),
                metadata={
                    "camera_id": int(getattr(camera, "camera_id", index) or 0),
                    "orientation": orientation if len(orientation) == 4 else (0.0, 0.0, 0.0, 1.0),
                    "field_of_view": float(getattr(camera, "field_of_view", 45.0) or 45.0),
                    "height": float(getattr(camera, "height", 0.0) or 0.0),
                    "mic_range": float(getattr(camera, "mic_range", 0.0) or 0.0),
                    "pitch": float(getattr(camera, "pitch", 0.0) or 0.0),
                },
            )
        )

    for index, store in enumerate(tuple(getattr(placements, "stores", ()) or ())):
        inspected = _inspect(template_inspector, "store", str(store.template_resref or ""), warnings)
        entities.append(
            PIEEntity(
                entity_id=_entity_id("store", index, store),
                kind="store",
                tag=str(store.tag or ""),
                display_name=_display_name(inspected, store),
                template_resref=str(store.template_resref or ""),
                position=_vec3(store.position),
                facing=float(getattr(store, "bearing", 0.0) or 0.0),
                interactive=False,
                interaction="store",
                actions=("open_store",),
                inventory_items=_inventory_items(inspected),
                scripts=tuple(tuple(row) for row in tuple(inspected.get("scripts") or ())),
                target_radius=_TARGET_RADII["store"],
                metadata=dict(inspected),
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
