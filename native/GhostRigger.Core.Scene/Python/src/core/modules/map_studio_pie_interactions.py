"""Headless focus, interaction, and runtime-inventory contracts for Map Studio PIE.

This module deliberately does not know about Qt, renderers, the PIE session, or
KOTOR script execution.  It consumes immutable :class:`PIEEntity` records and
keeps every simulated change in a private runtime state.  Authored KMAP/GIT
state and the entity registry are never mutated.

Dialogue and combat are optional injected callbacks.  NCS, commerce, and other
engine-only behavior are reported as deferred instead of being presented as a
successful KOTOR simulation.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
import math
from typing import Any

from .map_studio_pie_entities import PIEEntity, PIEEntityRegistry


Vec3 = tuple[float, float, float]
InventoryValue = "PIEInventoryItem | str | Mapping[str, Any] | Sequence[Any]"
InteractionCallback = Callable[[PIEEntity, "PIEActionSpec"], object]

ACTION_TALK = "talk"
ACTION_ATTACK = "attack"
ACTION_DOOR = "door"
ACTION_CONTAINER = "container"
ACTION_TERMINAL = "terminal"
ACTION_USE = "use"
ACTION_STORE = "store"
ACTION_TAKE = "take"
ACTION_TAKE_ALL = "take_all"

STATUS_EXECUTED = "executed"
STATUS_BLOCKED = "blocked"
STATUS_DEFERRED = "deferred"
STATUS_UNSUPPORTED = "unsupported"
STATUS_NO_TARGET = "no_target"

_ACTION_ALIASES = {
    "open": ACTION_DOOR,
    "open_door": ACTION_DOOR,
    "use_door": ACTION_DOOR,
    "open_container": ACTION_CONTAINER,
    "inventory": ACTION_CONTAINER,
    "dialogue": ACTION_TALK,
    "combat": ACTION_ATTACK,
    "use_terminal": ACTION_TERMINAL,
    "open_store": ACTION_STORE,
    "takeall": ACTION_TAKE_ALL,
}


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _clean_command(value: object) -> str:
    command = _clean_text(value).lower().replace("-", "_").replace(" ", "_")
    return _ACTION_ALIASES.get(command, command)


def _vec3(value: object) -> Vec3:
    values = tuple(value or ()) if not isinstance(value, str) else ()
    if len(values) < 3:
        values = values + (0.0,) * (3 - len(values))
    return (float(values[0]), float(values[1]), float(values[2]))


@dataclass(frozen=True)
class PIEActionSpec:
    """One ordered action advertised for a PIE entity."""

    command: str
    label: str
    interaction_range: float = 2.25
    repeat_policy: str = "repeatable"
    supported: bool = True
    requires_callback: bool = False
    script_resref: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        command = _clean_command(self.command)
        if not command:
            raise ValueError("PIE action command cannot be blank.")
        interaction_range = float(self.interaction_range)
        if not math.isfinite(interaction_range) or interaction_range < 0.0:
            raise ValueError("PIE action interaction_range must be a finite non-negative value.")
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "label", _clean_text(self.label) or command.replace("_", " ").title())
        object.__setattr__(self, "interaction_range", interaction_range)
        object.__setattr__(self, "repeat_policy", _clean_text(self.repeat_policy) or "repeatable")
        object.__setattr__(self, "script_resref", _clean_text(self.script_resref))
        object.__setattr__(self, "reason", _clean_text(self.reason))


@dataclass(frozen=True)
class PIEFocusState:
    """Immutable focus choice and its distance/depth proof values."""

    entity_id: str
    kind: str
    display_name: str
    position: Vec3
    target_radius: float
    center_distance: float
    interaction_distance: float
    camera_depth: float
    forward_alignment: float
    camera_side_alignment: float
    in_range: bool
    semantic_state: str
    actions: tuple[PIEActionSpec, ...]
    current_hp: int = 0
    max_hp: int = 0
    cycle_index: int = 0

    @property
    def primary_action(self) -> PIEActionSpec | None:
        return self.actions[0] if self.actions else None


@dataclass(frozen=True)
class PIEInventoryItem:
    """One immutable runtime inventory stack."""

    resref: str
    quantity: int = 1
    display_name: str = ""
    droppable: bool = True

    def __post_init__(self) -> None:
        resref = _clean_text(self.resref)
        if not resref:
            raise ValueError("PIE inventory item resref cannot be blank.")
        quantity = int(self.quantity)
        if quantity <= 0:
            raise ValueError("PIE inventory item quantity must be positive.")
        object.__setattr__(self, "resref", resref)
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "display_name", _clean_text(self.display_name))
        object.__setattr__(self, "droppable", bool(self.droppable))

    @property
    def stack_key(self) -> str:
        return self.resref.casefold()


@dataclass(frozen=True)
class PIEInteractionSnapshot:
    """Deeply immutable view of all runtime-only interaction state."""

    player_inventory: tuple[PIEInventoryItem, ...] = ()
    container_inventories: tuple[tuple[str, tuple[PIEInventoryItem, ...]], ...] = ()
    open_doors: tuple[str, ...] = ()
    open_containers: tuple[str, ...] = ()
    unlocked_entities: tuple[str, ...] = ()

    def container_inventory(self, entity_id: str) -> tuple[PIEInventoryItem, ...]:
        wanted = _clean_text(entity_id)
        for current_id, inventory in self.container_inventories:
            if current_id == wanted:
                return inventory
        return ()


@dataclass(frozen=True)
class PIEInteractionResult:
    """Immutable outcome of one routed editor-side interaction command."""

    status: str
    command: str
    entity_id: str
    message: str
    snapshot: PIEInteractionSnapshot
    action: PIEActionSpec | None = None
    items: tuple[PIEInventoryItem, ...] = ()
    deferred_scripts: tuple[str, ...] = ()
    coverage_warnings: tuple[str, ...] = ()

    @property
    def executed(self) -> bool:
        return self.status == STATUS_EXECUTED


def _metadata(entity: PIEEntity) -> Mapping[str, Any]:
    value = getattr(entity, "metadata", {}) or {}
    return value if isinstance(value, Mapping) else {}


def _script_map(entity: PIEEntity) -> dict[str, str]:
    metadata = _metadata(entity)
    result: dict[str, str] = {}
    scripts = metadata.get("scripts", {})
    if isinstance(scripts, Mapping):
        for key, value in scripts.items():
            clean = _clean_text(value)
            if clean:
                result[_clean_command(key)] = clean
    elif isinstance(scripts, Iterable) and not isinstance(scripts, (str, bytes, bytearray)):
        for row in scripts:
            try:
                key, value = tuple(row)[:2]
            except (TypeError, ValueError):
                continue
            clean = _clean_text(value)
            if clean:
                result[_clean_command(key)] = clean
    for key in (
        "script_resref",
        "ncs",
        "on_dialog",
        "on_click",
        "on_open",
        "on_inventory",
        "on_inv_disturbed",
        "on_used",
        "on_open_store",
    ):
        clean = _clean_text(metadata.get(key, ""))
        if clean:
            result[key] = clean
    return result


def _first_script(entity: PIEEntity, *keys: str) -> str:
    scripts = _script_map(entity)
    for key in keys:
        clean_key = _clean_command(key)
        value = scripts.get(clean_key) or scripts.get(key)
        if value:
            return value
    return ""


def ordered_actions_for_entity(entity: PIEEntity) -> tuple[PIEActionSpec, ...]:
    """Derive stable, non-lossy action order from one registry entity.

    Multiple actions are retained.  A placeable may be both a container and a
    terminal, for example; the old single ``interaction`` field must not erase
    either capability.
    """

    kind = _clean_text(getattr(entity, "kind", "")).lower()
    interaction = _clean_command(getattr(entity, "interaction", ""))
    conversation = _clean_text(getattr(entity, "conversation", ""))
    metadata = _metadata(entity)
    actions: list[PIEActionSpec] = []

    if kind == "creature":
        hostile = _clean_text(getattr(entity, "faction", "")).lower() == "hostile"
        attackable = hostile or interaction == ACTION_ATTACK or bool(metadata.get("attackable", False))
        talkable = bool(conversation) or interaction == ACTION_TALK
        attack = PIEActionSpec(
            ACTION_ATTACK,
            "Attack",
            requires_callback=True,
            reason="Combat execution requires an injected PIE callback.",
        )
        talk = PIEActionSpec(
            ACTION_TALK,
            "Talk",
            requires_callback=True,
            script_resref=_first_script(entity, "on_dialog"),
            reason="Dialogue execution requires an injected PIE callback.",
        )
        if hostile:
            if attackable:
                actions.append(attack)
            if talkable:
                actions.append(talk)
        else:
            if talkable:
                actions.append(talk)
            if attackable:
                actions.append(attack)

    elif kind == "door":
        actions.append(
            PIEActionSpec(
                ACTION_DOOR,
                "Open Door",
                script_resref=_first_script(entity, "on_click", "on_open"),
                reason="Door state is simulated locally; referenced NCS remains deferred.",
            )
        )

    elif kind == "placeable":
        has_inventory = bool(getattr(entity, "has_inventory", False)) or interaction == ACTION_CONTAINER
        if has_inventory:
            actions.append(
                PIEActionSpec(
                    ACTION_CONTAINER,
                    "Open Container",
                    script_resref=_first_script(entity, "on_open", "on_inventory", "on_inv_disturbed"),
                    reason="Container inventory is a runtime-only editor snapshot.",
                )
            )
        if conversation or interaction == ACTION_TERMINAL:
            actions.append(
                PIEActionSpec(
                    ACTION_TERMINAL,
                    "Use Terminal",
                    requires_callback=bool(conversation),
                    script_resref=_first_script(entity, "on_used", "on_click"),
                    reason="Terminal dialogue needs a callback; NCS execution remains deferred.",
                )
            )
        use_script = _first_script(entity, "on_used", "script_resref", "ncs")
        use_requested = interaction == ACTION_USE or bool(use_script) or (
            bool(getattr(entity, "interactive", False)) and not actions
        )
        if use_requested:
            explicitly_unusable = metadata.get("useable") is False
            reason = (
                "The UTP template is not engine-useable."
                if explicitly_unusable
                else "Generic OnUsed/NCS behavior is not executed by headless PIE."
            )
            actions.append(
                PIEActionSpec(
                    ACTION_USE,
                    "Use",
                    supported=False,
                    script_resref=use_script,
                    reason=reason,
                )
            )

    elif kind == "store":
        actions.append(
            PIEActionSpec(
                ACTION_STORE,
                "Open Store",
                supported=False,
                script_resref=_first_script(entity, "on_open_store", "on_open"),
                reason="KOTOR commerce is not simulated by headless PIE.",
            )
        )

    return tuple(actions)


def _entities(source: PIEEntityRegistry | Iterable[PIEEntity]) -> tuple[PIEEntity, ...]:
    if isinstance(source, PIEEntityRegistry):
        return tuple(source.entities)
    value = getattr(source, "entities", None)
    if value is not None:
        return tuple(value or ())
    return tuple(source or ())


def _semantic_state(entity: PIEEntity, primary: PIEActionSpec) -> str:
    if bool(getattr(entity, "locked", False)):
        return "locked"
    faction = _clean_text(getattr(entity, "faction", "")).lower()
    if getattr(entity, "kind", "") == "creature" and faction in {"friendly", "neutral", "hostile"}:
        return faction
    if not primary.supported:
        return "unsupported"
    return "actionable"


def focus_candidates(
    source: PIEEntityRegistry | Iterable[PIEEntity],
    *,
    player_position: Vec3,
    camera_forward: Vec3,
    maximum_distance: float = 8.0,
    visible_entity_ids: Iterable[str] | None = None,
    front_only: bool = True,
) -> tuple[PIEFocusState, ...]:
    """Return stable nearest-first actionable targets.

    Automatic acquisition keeps ``front_only=True`` so it behaves like the
    existing nearest/front reticle.  Directional left/right selection opts
    into the full camera-relative circle instead; Odyssey's selection help
    text describes objects to either side, including wraparound.
    """

    origin = _vec3(player_position)
    forward = _vec3(camera_forward)
    forward_length = math.sqrt(sum(value * value for value in forward))
    if forward_length <= 1.0e-12:
        raise ValueError("camera_forward must have non-zero length.")
    forward = tuple(value / forward_length for value in forward)  # type: ignore[assignment]
    maximum = float(maximum_distance)
    if not math.isfinite(maximum) or maximum < 0.0:
        raise ValueError("maximum_distance must be a finite non-negative value.")
    visible = None if visible_entity_ids is None else {_clean_text(value) for value in visible_entity_ids}

    ranked: list[tuple[tuple[float, float, float, str], PIEFocusState]] = []
    for entity in _entities(source):
        entity_id = _clean_text(getattr(entity, "entity_id", ""))
        if not entity_id or (visible is not None and entity_id not in visible):
            continue
        actions = ordered_actions_for_entity(entity)
        if not actions:
            continue
        position = _vec3(getattr(entity, "position", (0.0, 0.0, 0.0)))
        delta = tuple(position[index] - origin[index] for index in range(3))
        center_distance = math.sqrt(sum(value * value for value in delta))
        radius = max(0.0, float(getattr(entity, "target_radius", 0.0) or 0.0))
        interaction_distance = max(0.0, center_distance - radius)
        if interaction_distance > maximum + 1.0e-9:
            continue
        depth = sum(delta[index] * forward[index] for index in range(3))
        # A player standing inside a target footprint can still focus it;
        # otherwise the target center must be in front of the camera plane.
        if front_only and depth <= 1.0e-9 and center_distance > radius + 1.0e-9:
            continue
        alignment = depth / center_distance if center_distance > 1.0e-12 else 1.0
        side_alignment = (
            ((forward[0] * delta[1]) - (forward[1] * delta[0])) / center_distance
            if center_distance > 1.0e-12
            else 0.0
        )
        primary = actions[0]
        maximum_hp = max(0, int(getattr(entity, "max_hp", 0) or 0))
        current_hp = max(0, int(getattr(entity, "current_hp", maximum_hp) or 0))
        if maximum_hp:
            current_hp = min(current_hp, maximum_hp)
        state = PIEFocusState(
            entity_id=entity_id,
            kind=_clean_text(getattr(entity, "kind", "")),
            display_name=_clean_text(getattr(entity, "display_name", "")) or entity_id,
            position=position,
            target_radius=radius,
            center_distance=center_distance,
            interaction_distance=interaction_distance,
            camera_depth=depth,
            forward_alignment=alignment,
            camera_side_alignment=side_alignment,
            in_range=interaction_distance <= primary.interaction_range + 1.0e-9,
            semantic_state=_semantic_state(entity, primary),
            actions=actions,
            current_hp=current_hp,
            max_hp=maximum_hp,
        )
        # Distance to the target footprint is primary.  More centered targets
        # win an exact-distance tie, then nearer camera depth and stable id.
        rank = (interaction_distance, -alignment, depth, entity_id)
        ranked.append((rank, state))

    ranked.sort(key=lambda row: row[0])
    return tuple(replace(row[1], cycle_index=index) for index, row in enumerate(ranked))


def acquire_pie_focus(
    source: PIEEntityRegistry | Iterable[PIEEntity],
    *,
    player_position: Vec3,
    camera_forward: Vec3,
    prior_focus_id: str = "",
    hysteresis: float = 0.15,
    maximum_distance: float = 8.0,
    hostile_maximum_distance: float | None = None,
    visible_entity_ids: Iterable[str] | None = None,
) -> PIEFocusState | None:
    """Choose nearest-front focus while retaining a nearly-equal prior target."""

    margin = float(hysteresis)
    if not math.isfinite(margin) or margin < 0.0:
        raise ValueError("hysteresis must be a finite non-negative value.")
    ordinary_maximum = float(maximum_distance)
    hostile_maximum = ordinary_maximum if hostile_maximum_distance is None else float(hostile_maximum_distance)
    if (
        not math.isfinite(ordinary_maximum)
        or not math.isfinite(hostile_maximum)
        or ordinary_maximum < 0.0
        or hostile_maximum < 0.0
    ):
        raise ValueError("PIE focus distances must be finite non-negative values.")
    entities = _entities(source)
    entity_by_id = {
        _clean_text(getattr(entity, "entity_id", "")): entity
        for entity in entities
    }
    candidates = focus_candidates(
        entities,
        player_position=player_position,
        camera_forward=camera_forward,
        maximum_distance=max(ordinary_maximum, hostile_maximum),
        visible_entity_ids=visible_entity_ids,
    )
    candidates = tuple(
        row
        for row in candidates
        if row.center_distance
        <= (
            hostile_maximum
            if _clean_text(getattr(entity_by_id.get(row.entity_id), "faction", "")).lower() == "hostile"
            else ordinary_maximum
        )
        + 1.0e-9
    )
    if not candidates:
        return None
    best = candidates[0]
    wanted = _clean_text(prior_focus_id)
    prior = next((candidate for candidate in candidates if candidate.entity_id == wanted), None)
    if prior is None:
        return best
    # Never retain an out-of-range target over a newly in-range target.
    if best.in_range and not prior.in_range:
        return best
    if prior.interaction_distance <= best.interaction_distance + margin + 1.0e-9:
        return prior
    return best


def cycle_pie_focus(
    source: PIEEntityRegistry | Iterable[PIEEntity],
    *,
    player_position: Vec3,
    camera_forward: Vec3,
    current_focus_id: str = "",
    direction: int = 1,
    maximum_distance: float = 8.0,
    hostile_maximum_distance: float | None = None,
    visible_entity_ids: Iterable[str] | None = None,
) -> PIEFocusState | None:
    """Select the next target to the camera-relative left or right.

    ``direction < 0`` means left (Q) and ``direction > 0`` means right (E).
    The current eligible target is the angular origin and wraparound is
    deterministic.  When no eligible focus is retained, the nearest/front
    automatic acquisition rule remains the starting point.
    """

    ordinary_maximum = float(maximum_distance)
    hostile_maximum = (
        ordinary_maximum
        if hostile_maximum_distance is None
        else float(hostile_maximum_distance)
    )
    if (
        not math.isfinite(ordinary_maximum)
        or not math.isfinite(hostile_maximum)
        or ordinary_maximum < 0.0
        or hostile_maximum < 0.0
    ):
        raise ValueError("Q/E focus distances must be finite non-negative values.")
    entities = _entities(source)
    entity_by_id = {
        _clean_text(getattr(entity, "entity_id", "")): entity
        for entity in entities
    }
    candidates = focus_candidates(
        entities,
        player_position=player_position,
        camera_forward=camera_forward,
        maximum_distance=max(ordinary_maximum, hostile_maximum),
        visible_entity_ids=visible_entity_ids,
        front_only=False,
    )
    candidates = tuple(
        row
        for row in candidates
        if row.center_distance
        <= (
            hostile_maximum
            if _clean_text(getattr(entity_by_id.get(row.entity_id), "faction", "")).lower() == "hostile"
            else ordinary_maximum
        )
        + 1.0e-9
    )
    if not candidates:
        return None
    wanted = _clean_text(current_focus_id)
    current = next((row for row in candidates if row.entity_id == wanted), None)
    if current is None:
        # Preserve the normal nearest/front acquire instead of making the
        # first Q/E press jump to an arbitrary angular extreme.
        return acquire_pie_focus(
            source,
            player_position=player_position,
            camera_forward=camera_forward,
            maximum_distance=maximum_distance,
            hostile_maximum_distance=hostile_maximum_distance,
            visible_entity_ids=visible_entity_ids,
        ) or candidates[0]
    if int(direction) == 0 or len(candidates) == 1:
        return current

    origin = _vec3(player_position)
    forward = _vec3(camera_forward)
    planar_forward = (forward[0], forward[1])
    planar_length = math.hypot(*planar_forward)
    if planar_length <= 1.0e-12:
        planar_forward = (1.0, 0.0)
        planar_length = 1.0
    fx, fy = planar_forward[0] / planar_length, planar_forward[1] / planar_length

    def signed_angle(row: PIEFocusState) -> float:
        dx = float(row.position[0]) - origin[0]
        dy = float(row.position[1]) - origin[1]
        if math.hypot(dx, dy) <= 1.0e-12:
            return 0.0
        # Positive is camera-relative left (counter-clockwise in module XY).
        return math.atan2((fx * dy) - (fy * dx), (fx * dx) + (fy * dy))

    ordered = sorted(candidates, key=lambda row: (signed_angle(row), row.interaction_distance, row.entity_id))
    current_index = next(index for index, row in enumerate(ordered) if row.entity_id == current.entity_id)
    # Q/left moves toward increasing signed angle; E/right moves toward
    # decreasing signed angle.  The public direction values retain the input
    # adapter's established Q=-1 / E=+1 contract.
    step = 1 if int(direction) < 0 else -1
    return ordered[(current_index + step) % len(ordered)]


def _coerce_inventory_item(value: InventoryValue) -> PIEInventoryItem:
    if isinstance(value, PIEInventoryItem):
        return value
    if isinstance(value, str):
        return PIEInventoryItem(value)
    if isinstance(value, Mapping):
        return PIEInventoryItem(
            resref=_clean_text(value.get("resref") or value.get("item") or value.get("template_resref")),
            quantity=int(value.get("quantity", value.get("count", 1)) or 1),
            display_name=_clean_text(value.get("display_name") or value.get("name")),
            droppable=bool(value.get("droppable", True)),
        )
    values = tuple(value)
    if not values:
        raise ValueError("PIE inventory item sequence cannot be empty.")
    return PIEInventoryItem(
        resref=_clean_text(values[0]),
        quantity=int(values[1]) if len(values) > 1 else 1,
        display_name=_clean_text(values[2]) if len(values) > 2 else "",
        droppable=bool(values[3]) if len(values) > 3 else True,
    )


def _inventory_values(source: object) -> tuple[InventoryValue, ...]:
    if source is None:
        return ()
    if isinstance(source, Mapping):
        item_keys = {"resref", "item", "template_resref"}
        if item_keys.intersection(source):
            return (source,)  # type: ignore[return-value]
        return tuple((resref, quantity) for resref, quantity in source.items())
    if isinstance(source, (str, PIEInventoryItem)):
        return (source,)
    return tuple(source)  # type: ignore[arg-type,return-value]


def _stack_inventory(source: object) -> dict[str, PIEInventoryItem]:
    stacks: dict[str, PIEInventoryItem] = {}
    for value in _inventory_values(source):
        item = _coerce_inventory_item(value)
        previous = stacks.get(item.stack_key)
        if previous is None:
            stacks[item.stack_key] = item
            continue
        stacks[item.stack_key] = PIEInventoryItem(
            resref=previous.resref,
            quantity=previous.quantity + item.quantity,
            display_name=previous.display_name or item.display_name,
            droppable=previous.droppable and item.droppable,
        )
    return stacks


def _inventory_tuple(stacks: Mapping[str, PIEInventoryItem]) -> tuple[PIEInventoryItem, ...]:
    return tuple(stacks[key] for key in sorted(stacks))


class PIEInteractionRouter:
    """Runtime-only action router with immutable results and snapshots."""

    def __init__(
        self,
        source: PIEEntityRegistry | Iterable[PIEEntity],
        *,
        player_inventory: object = (),
        container_inventories: Mapping[str, object] | None = None,
        dialogue_callback: InteractionCallback | None = None,
        combat_callback: InteractionCallback | None = None,
    ) -> None:
        entities = _entities(source)
        self._entities = tuple(entities)
        self._entity_by_id = {
            _clean_text(entity.entity_id): entity
            for entity in entities
            if _clean_text(getattr(entity, "entity_id", ""))
        }
        self._actions = {
            entity_id: ordered_actions_for_entity(entity)
            for entity_id, entity in self._entity_by_id.items()
        }
        self._player_inventory = _stack_inventory(player_inventory)
        explicit = dict(container_inventories or {})
        self._container_inventories: dict[str, dict[str, PIEInventoryItem]] = {}
        for entity_id, entity in self._entity_by_id.items():
            if not any(action.command == ACTION_CONTAINER for action in self._actions[entity_id]):
                continue
            if entity_id in explicit:
                inventory_source = explicit[entity_id]
            else:
                metadata = _metadata(entity)
                inventory_source = metadata.get("inventory_items", metadata.get("inventory", ()))
            self._container_inventories[entity_id] = _stack_inventory(inventory_source)
        self._open_doors: set[str] = set()
        self._open_containers: set[str] = set()
        self._unlocked_entities: set[str] = set()
        self._dialogue_callback = dialogue_callback
        self._combat_callback = combat_callback

    @property
    def entities(self) -> tuple[PIEEntity, ...]:
        return self._entities

    @property
    def player_inventory(self) -> tuple[PIEInventoryItem, ...]:
        return _inventory_tuple(self._player_inventory)

    def container_inventory(self, entity_id: str) -> tuple[PIEInventoryItem, ...]:
        return _inventory_tuple(self._container_inventories.get(_clean_text(entity_id), {}))

    def has_key(self, key_resref: str) -> bool:
        key = _clean_text(key_resref).casefold()
        return bool(key and key in self._player_inventory and self._player_inventory[key].quantity > 0)

    def snapshot(self) -> PIEInteractionSnapshot:
        return PIEInteractionSnapshot(
            player_inventory=self.player_inventory,
            container_inventories=tuple(
                (entity_id, _inventory_tuple(self._container_inventories[entity_id]))
                for entity_id in sorted(self._container_inventories)
            ),
            open_doors=tuple(sorted(self._open_doors)),
            open_containers=tuple(sorted(self._open_containers)),
            unlocked_entities=tuple(sorted(self._unlocked_entities)),
        )

    def _result(
        self,
        status: str,
        command: str,
        entity_id: str,
        message: str,
        *,
        action: PIEActionSpec | None = None,
        items: tuple[PIEInventoryItem, ...] = (),
        deferred_scripts: tuple[str, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> PIEInteractionResult:
        return PIEInteractionResult(
            status=status,
            command=_clean_command(command),
            entity_id=_clean_text(entity_id),
            message=_clean_text(message),
            snapshot=self.snapshot(),
            action=action,
            items=tuple(items),
            deferred_scripts=tuple(dict.fromkeys(_clean_text(value) for value in deferred_scripts if _clean_text(value))),
            coverage_warnings=tuple(dict.fromkeys(_clean_text(value) for value in warnings if _clean_text(value))),
        )

    @staticmethod
    def _script_warning(script_resref: str) -> tuple[str, ...]:
        script = _clean_text(script_resref)
        if not script:
            return ()
        return (f"NCS {script} is referenced but is not executed by headless PIE.",)

    def _locked_result(self, entity: PIEEntity, action: PIEActionSpec, command: str) -> PIEInteractionResult | None:
        entity_id = _clean_text(entity.entity_id)
        if not bool(getattr(entity, "locked", False)) or entity_id in self._unlocked_entities:
            return None
        key = _clean_text(getattr(entity, "key_required", ""))
        if key and self.has_key(key):
            self._unlocked_entities.add(entity_id)
            return None
        if key:
            message = f"{entity.display_name or entity_id} is locked and requires key {key}."
        else:
            message = f"{entity.display_name or entity_id} is locked; no usable key resref is known."
        return self._result(STATUS_BLOCKED, command, entity_id, message, action=action)

    def _callback_result(
        self,
        entity: PIEEntity,
        action: PIEActionSpec,
        callback: InteractionCallback | None,
        *,
        resource_label: str,
        resource_resref: str = "",
    ) -> PIEInteractionResult:
        entity_id = _clean_text(entity.entity_id)
        script = _clean_text(action.script_resref)
        warnings = self._script_warning(script)
        if callback is None:
            resource = f" {resource_resref}" if resource_resref else ""
            return self._result(
                STATUS_DEFERRED,
                action.command,
                entity_id,
                f"{resource_label}{resource} requires an injected callback; headless PIE did not execute it.",
                action=action,
                deferred_scripts=(script,),
                warnings=warnings,
            )
        try:
            outcome = callback(entity, action)
        except Exception as exc:
            return self._result(
                STATUS_BLOCKED,
                action.command,
                entity_id,
                f"Injected {resource_label.lower()} callback failed: {exc}",
                action=action,
                deferred_scripts=(script,),
                warnings=warnings,
            )
        if outcome is False:
            return self._result(
                STATUS_BLOCKED,
                action.command,
                entity_id,
                f"Injected {resource_label.lower()} callback declined the action.",
                action=action,
                deferred_scripts=(script,),
                warnings=warnings,
            )
        message = _clean_text(outcome) if isinstance(outcome, str) else ""
        return self._result(
            STATUS_EXECUTED,
            action.command,
            entity_id,
            message or f"{resource_label} callback executed for {entity.display_name or entity_id}.",
            action=action,
            deferred_scripts=(script,),
            warnings=warnings,
        )

    def route(self, entity_id: str, command: str | None = None) -> PIEInteractionResult:
        """Route one advertised action without mutating registry/authored data."""

        wanted = _clean_text(entity_id)
        entity = self._entity_by_id.get(wanted)
        if entity is None:
            return self._result(STATUS_NO_TARGET, command or "", wanted, "PIE interaction target was not found.")
        actions = self._actions.get(wanted, ())
        chosen_command = _clean_command(command) if command is not None else (actions[0].command if actions else "")
        action = next((value for value in actions if value.command == chosen_command), None)
        if action is None:
            return self._result(
                STATUS_UNSUPPORTED,
                chosen_command,
                wanted,
                f"{entity.display_name or wanted} does not advertise the {chosen_command or '(blank)'} action.",
            )

        if chosen_command == ACTION_TALK:
            conversation = _clean_text(getattr(entity, "conversation", ""))
            if not conversation:
                return self._result(
                    STATUS_UNSUPPORTED,
                    chosen_command,
                    wanted,
                    f"{entity.display_name or wanted} has no dialogue resref.",
                    action=action,
                )
            return self._callback_result(
                entity,
                action,
                self._dialogue_callback,
                resource_label="Dialogue",
                resource_resref=conversation,
            )

        if chosen_command == ACTION_ATTACK:
            return self._callback_result(
                entity,
                action,
                self._combat_callback,
                resource_label="Combat",
            )

        if chosen_command == ACTION_DOOR:
            blocked = self._locked_result(entity, action, chosen_command)
            if blocked is not None:
                return blocked
            already_open = wanted in self._open_doors
            self._open_doors.add(wanted)
            script = _clean_text(action.script_resref)
            return self._result(
                STATUS_EXECUTED,
                chosen_command,
                wanted,
                f"Door {entity.display_name or wanted} was already open."
                if already_open
                else f"Door {entity.display_name or wanted} opened in editor-side PIE.",
                action=action,
                deferred_scripts=(script,),
                warnings=self._script_warning(script),
            )

        if chosen_command == ACTION_CONTAINER:
            blocked = self._locked_result(entity, action, chosen_command)
            if blocked is not None:
                return blocked
            self._open_containers.add(wanted)
            inventory = self.container_inventory(wanted)
            script = _clean_text(action.script_resref)
            return self._result(
                STATUS_EXECUTED,
                chosen_command,
                wanted,
                f"Opened runtime-only inventory for {entity.display_name or wanted} ({len(inventory)} stack(s)).",
                action=action,
                items=inventory,
                deferred_scripts=(script,),
                warnings=self._script_warning(script),
            )

        if chosen_command == ACTION_TERMINAL:
            conversation = _clean_text(getattr(entity, "conversation", ""))
            if conversation:
                return self._callback_result(
                    entity,
                    action,
                    self._dialogue_callback,
                    resource_label="Terminal dialogue",
                    resource_resref=conversation,
                )
            script = _clean_text(action.script_resref)
            if script:
                return self._result(
                    STATUS_DEFERRED,
                    chosen_command,
                    wanted,
                    f"Terminal behavior depends on NCS {script}; headless PIE did not execute it.",
                    action=action,
                    deferred_scripts=(script,),
                    warnings=self._script_warning(script),
                )
            return self._result(
                STATUS_UNSUPPORTED,
                chosen_command,
                wanted,
                "Terminal has neither a dialogue resref nor a known script.",
                action=action,
            )

        if chosen_command == ACTION_USE:
            script = _clean_text(action.script_resref)
            if script:
                return self._result(
                    STATUS_DEFERRED,
                    chosen_command,
                    wanted,
                    f"Use action depends on NCS {script}; headless PIE did not execute it.",
                    action=action,
                    deferred_scripts=(script,),
                    warnings=self._script_warning(script),
                )
            return self._result(
                STATUS_UNSUPPORTED,
                chosen_command,
                wanted,
                action.reason or "Generic object use has no editor-side implementation.",
                action=action,
            )

        if chosen_command == ACTION_STORE:
            script = _clean_text(action.script_resref)
            return self._result(
                STATUS_DEFERRED,
                chosen_command,
                wanted,
                "Store commerce is registered but is not simulated by headless PIE.",
                action=action,
                deferred_scripts=(script,),
                warnings=self._script_warning(script),
            )

        return self._result(
            STATUS_UNSUPPORTED,
            chosen_command,
            wanted,
            f"PIE has no router implementation for {chosen_command}.",
            action=action,
        )

    def route_focus(self, focus: PIEFocusState | None, command: str | None = None) -> PIEInteractionResult:
        if focus is None:
            return self._result(STATUS_NO_TARGET, command or "", "", "PIE has no focused interaction target.")
        if not focus.in_range:
            chosen = _clean_command(command) if command is not None else (
                focus.primary_action.command if focus.primary_action is not None else ""
            )
            return self._result(
                STATUS_BLOCKED,
                chosen,
                focus.entity_id,
                f"{focus.display_name} is outside interaction range.",
                action=focus.primary_action,
            )
        return self.route(focus.entity_id, command)

    def take(self, entity_id: str, item_resref: str, quantity: int = 1) -> PIEInteractionResult:
        """Transfer up to ``quantity`` from a container into player inventory."""

        wanted = _clean_text(entity_id)
        entity = self._entity_by_id.get(wanted)
        action = next(
            (value for value in self._actions.get(wanted, ()) if value.command == ACTION_CONTAINER),
            None,
        )
        if entity is None:
            return self._result(STATUS_NO_TARGET, ACTION_TAKE, wanted, "PIE container target was not found.")
        if action is None:
            return self._result(
                STATUS_UNSUPPORTED,
                ACTION_TAKE,
                wanted,
                f"{entity.display_name or wanted} is not a container.",
            )
        requested = int(quantity)
        if requested <= 0:
            return self._result(
                STATUS_BLOCKED,
                ACTION_TAKE,
                wanted,
                "Take quantity must be positive.",
                action=action,
            )
        blocked = self._locked_result(entity, action, ACTION_TAKE)
        if blocked is not None:
            return blocked
        self._open_containers.add(wanted)
        key = _clean_text(item_resref).casefold()
        stack = self._container_inventories.setdefault(wanted, {})
        item = stack.get(key)
        if not key or item is None:
            return self._result(
                STATUS_BLOCKED,
                ACTION_TAKE,
                wanted,
                f"Container {entity.display_name or wanted} does not contain {_clean_text(item_resref) or '(blank)' }.",
                action=action,
            )
        taken_quantity = min(requested, item.quantity)
        taken = PIEInventoryItem(item.resref, taken_quantity, item.display_name, item.droppable)
        if taken_quantity == item.quantity:
            del stack[key]
        else:
            stack[key] = PIEInventoryItem(
                item.resref,
                item.quantity - taken_quantity,
                item.display_name,
                item.droppable,
            )
        previous = self._player_inventory.get(key)
        if previous is None:
            self._player_inventory[key] = taken
        else:
            self._player_inventory[key] = PIEInventoryItem(
                previous.resref,
                previous.quantity + taken.quantity,
                previous.display_name or taken.display_name,
                previous.droppable and taken.droppable,
            )
        inventory_script = _first_script(entity, "on_inventory", "on_inv_disturbed")
        return self._result(
            STATUS_EXECUTED,
            ACTION_TAKE,
            wanted,
            f"Took {taken.quantity} x {taken.display_name or taken.resref} into runtime-only player inventory.",
            action=action,
            items=(taken,),
            deferred_scripts=(inventory_script,),
            warnings=self._script_warning(inventory_script),
        )

    def take_all(self, entity_id: str) -> PIEInteractionResult:
        """Transfer every runtime stack from one accessible container."""

        wanted = _clean_text(entity_id)
        entity = self._entity_by_id.get(wanted)
        action = next(
            (value for value in self._actions.get(wanted, ()) if value.command == ACTION_CONTAINER),
            None,
        )
        if entity is None:
            return self._result(STATUS_NO_TARGET, ACTION_TAKE_ALL, wanted, "PIE container target was not found.")
        if action is None:
            return self._result(
                STATUS_UNSUPPORTED,
                ACTION_TAKE_ALL,
                wanted,
                f"{entity.display_name or wanted} is not a container.",
            )
        blocked = self._locked_result(entity, action, ACTION_TAKE_ALL)
        if blocked is not None:
            return blocked
        self._open_containers.add(wanted)
        stack = self._container_inventories.setdefault(wanted, {})
        taken = _inventory_tuple(stack)
        for item in taken:
            previous = self._player_inventory.get(item.stack_key)
            if previous is None:
                self._player_inventory[item.stack_key] = item
            else:
                self._player_inventory[item.stack_key] = PIEInventoryItem(
                    previous.resref,
                    previous.quantity + item.quantity,
                    previous.display_name or item.display_name,
                    previous.droppable and item.droppable,
                )
        stack.clear()
        inventory_script = _first_script(entity, "on_inventory", "on_inv_disturbed") if taken else ""
        return self._result(
            STATUS_EXECUTED,
            ACTION_TAKE_ALL,
            wanted,
            f"Took {len(taken)} stack(s) into runtime-only player inventory."
            if taken
            else f"Container {entity.display_name or wanted} is empty.",
            action=action,
            items=taken,
            deferred_scripts=(inventory_script,),
            warnings=self._script_warning(inventory_script),
        )


__all__ = [
    "ACTION_ATTACK",
    "ACTION_CONTAINER",
    "ACTION_DOOR",
    "ACTION_STORE",
    "ACTION_TAKE",
    "ACTION_TAKE_ALL",
    "ACTION_TALK",
    "ACTION_TERMINAL",
    "ACTION_USE",
    "PIEActionSpec",
    "PIEFocusState",
    "PIEInteractionResult",
    "PIEInteractionRouter",
    "PIEInteractionSnapshot",
    "PIEInventoryItem",
    "STATUS_BLOCKED",
    "STATUS_DEFERRED",
    "STATUS_EXECUTED",
    "STATUS_NO_TARGET",
    "STATUS_UNSUPPORTED",
    "acquire_pie_focus",
    "cycle_pie_focus",
    "focus_candidates",
    "ordered_actions_for_entity",
]
