"""Deterministic, editor-only combat contract for Map Studio PIE.

This module models a deliberately bounded combat preview.  It accepts explicit
combat stats supplied by a caller, advances in fixed three-second rounds, and
emits immutable events that a renderer adapter may translate into actor
animations and HUD feedback.  It does not read UTC/UTI/2DA resources, execute
NWScript, mutate a KMAP project, or claim Odyssey combat parity.

The runtime owns no Qt, renderer, resource-manager, or global-random state.  A
local versioned integer generator keeps initiative, attack, and damage rolls
stable across Python processes and across differently chunked frame deltas.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable


PIE_COMBAT_ROUND_SECONDS = 3.0

PIE_COMBAT_RUNTIME_LIMITATIONS: tuple[str, ...] = (
    "PIE combat is a deterministic editor preview, not the Odyssey combat engine.",
    "Callers must supply explicit combat stats; PIE does not derive feats, equipment, powers, or 2DA rules.",
    "PIE combat does not execute NWScript event handlers, AI/action queues, perception, party logic, or loot.",
    "Range, pathfinding, projectiles, effects, sounds, and line of sight belong to later adapter layers.",
    "Export and a manual KOTOR run remain the authoritative gameplay proof.",
)

_RELATIONSHIPS = frozenset({"player", "hostile", "friendly", "neutral"})
_ANIMATION_ROLES = frozenset({"ready", "attack", "damage", "death"})
_EPSILON = 1.0e-9


def _clean_candidates(values: Iterable[str]) -> tuple[str, ...]:
    """Return stable, case-preserving animation candidates without blanks."""

    result: list[str] = []
    seen: set[str] = set()
    for value in tuple(values or ()):
        text = str(value or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return tuple(result)


@dataclass(frozen=True)
class MapStudioPIECombatAnimationRoles:
    """Per-model clip candidates supplied by the renderer/actor adapter.

    No clip name is implied by the combat runtime.  Humanoids, creatures, and
    droids use different Odyssey animation families, so callers provide an
    ordered candidate tuple for each semantic role after inspecting the actual
    actor model and supermodel chain.
    """

    ready: tuple[str, ...] = ()
    attack: tuple[str, ...] = ()
    damage: tuple[str, ...] = ()
    death: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for role in sorted(_ANIMATION_ROLES):
            object.__setattr__(self, role, _clean_candidates(getattr(self, role)))

    def candidates(self, role: str) -> tuple[str, ...]:
        key = str(role or "").strip().lower()
        return tuple(getattr(self, key, ())) if key in _ANIMATION_ROLES else ()


@dataclass(frozen=True)
class MapStudioPIEDamageDice:
    """Explicit damage expression used after a successful d20 attack roll."""

    count: int
    sides: int
    bonus: int = 0

    def __post_init__(self) -> None:
        count = int(self.count)
        sides = int(self.sides)
        if count < 0:
            raise ValueError("PIE combat damage dice count cannot be negative.")
        if count and sides < 1:
            raise ValueError("PIE combat damage dice require at least one side.")
        if not count and sides < 0:
            raise ValueError("PIE combat damage die sides cannot be negative.")
        object.__setattr__(self, "count", count)
        object.__setattr__(self, "sides", sides)
        object.__setattr__(self, "bonus", int(self.bonus))


# Authoritative DAMAGE_TYPE_* bit values from KOTOR's own nwscript.nss, ordered
# so a single-type weapon reports its exact name and blends read left-to-right.
_PIE_DAMAGE_TYPE_NAMES: tuple[tuple[int, str], ...] = (
    (1, "Bludgeoning"),
    (2, "Piercing"),
    (4, "Slashing"),
    (8, "Universal"),
    (16, "Acid"),
    (32, "Cold"),
    (64, "Light Side"),
    (128, "Electrical"),
    (256, "Fire"),
    (512, "Dark Side"),
    (1024, "Sonic"),
    (2048, "Ion"),
    (4096, "Energy"),  # DAMAGE_TYPE_BLASTER — lightsabers and blasters
)


def pie_damage_type_label(damage_flags: Any) -> str:
    """Map a baseitems.2da ``damageflags`` bitfield to its KOTOR damage type.

    Uses the exact `DAMAGE_TYPE_*` bit values from the game's nwscript.nss.
    Multiple set bits join with '/'; an empty/unset field returns "Physical".
    """

    try:
        flags = int(damage_flags)
    except (TypeError, ValueError):
        return "Physical"
    if flags <= 0:
        return "Physical"
    names = [name for bit, name in _PIE_DAMAGE_TYPE_NAMES if flags & bit]
    return "/".join(names) if names else "Physical"


def derive_pie_weapon_damage_dice(
    base_item_fields: Any,
    *,
    strength_modifier: int = 0,
    ranged: bool = False,
) -> MapStudioPIEDamageDice:
    """Map a baseitems.2da weapon row to its editor-side damage expression.

    KOTOR weapon damage is ``numdice`` × d``dietoroll`` from baseitems.2da; melee
    attacks add the wielder's Strength modifier, ranged (blaster) attacks do not.
    An empty/undecodable row falls back to an unarmed 1d3. This is the evidence-
    grounded core the combat runtime consumes; it rolls nothing itself.
    """

    fields = dict(base_item_fields or {})

    def _int(*keys: str, default: int = 0) -> int:
        for key in keys:
            if key in fields and str(fields[key]).strip() not in ("", "****"):
                try:
                    return int(float(fields[key]))
                except (TypeError, ValueError):
                    continue
        return default

    count = max(0, _int("numdice", "NumDice", default=1))
    sides = max(1, _int("dietoroll", "DieToRoll", default=3))
    bonus = int(strength_modifier) if not ranged else 0
    if count == 0:
        # No weapon dice defined: fall back to an unarmed strike.
        count, sides = 1, 3
    return MapStudioPIEDamageDice(count=count, sides=sides, bonus=bonus)


@dataclass(frozen=True)
class MapStudioPIECombatStats:
    """Caller-supplied stats; no engine or resource derivation occurs here."""

    max_hp: int
    current_hp: int
    armor_class: int
    attack_bonus: int
    damage: MapStudioPIEDamageDice
    initiative_bonus: int = 0
    # d20 critical baseline: a threat of 1 crits only on a natural 20 at x2.
    # A weapon's baseitems.2da critthreat/critmult can widen these later.
    critical_threat: int = 1
    critical_multiplier: int = 2
    damage_type: str = "Physical"

    def __post_init__(self) -> None:
        max_hp = int(self.max_hp)
        current_hp = int(self.current_hp)
        if max_hp < 1:
            raise ValueError("PIE combat max HP must be at least one.")
        if current_hp < 0:
            raise ValueError("PIE combat current HP cannot be negative.")
        if not isinstance(self.damage, MapStudioPIEDamageDice):
            raise TypeError("PIE combat damage must be a MapStudioPIEDamageDice value.")
        object.__setattr__(self, "max_hp", max(max_hp, current_hp))
        object.__setattr__(self, "current_hp", current_hp)
        object.__setattr__(self, "armor_class", int(self.armor_class))
        object.__setattr__(self, "attack_bonus", int(self.attack_bonus))
        object.__setattr__(self, "initiative_bonus", int(self.initiative_bonus))
        # A threat of 1 means only a natural 20 threatens; clamp to [1, 20].
        object.__setattr__(self, "critical_threat", max(1, min(20, int(self.critical_threat))))
        object.__setattr__(self, "critical_multiplier", max(1, int(self.critical_multiplier)))
        object.__setattr__(self, "damage_type", str(self.damage_type or "Physical").strip() or "Physical")


@dataclass(frozen=True)
class MapStudioPIECombatant:
    """One immutable combat participant projected from authored intent."""

    entity_id: str
    display_name: str
    relationship_to_player: str
    stats: MapStudioPIECombatStats
    animations: MapStudioPIECombatAnimationRoles = MapStudioPIECombatAnimationRoles()
    player_controlled: bool = False
    retaliates: bool = True
    # An assisting ally (party companion / friendly NPC) auto-engages when combat
    # starts and makes one basic attack per round against an engaged hostile.
    assists: bool = False

    def __post_init__(self) -> None:
        entity_id = str(self.entity_id or "").strip()
        if not entity_id:
            raise ValueError("PIE combatants require a stable entity id.")
        relationship = str(self.relationship_to_player or "neutral").strip().lower()
        if relationship not in _RELATIONSHIPS:
            raise ValueError(f"Unsupported PIE combat relationship: {relationship!r}.")
        if not isinstance(self.stats, MapStudioPIECombatStats):
            raise TypeError("PIE combatants require explicit MapStudioPIECombatStats.")
        if not isinstance(self.animations, MapStudioPIECombatAnimationRoles):
            raise TypeError("PIE combatants require MapStudioPIECombatAnimationRoles.")
        object.__setattr__(self, "entity_id", entity_id)
        object.__setattr__(self, "display_name", str(self.display_name or entity_id).strip() or entity_id)
        object.__setattr__(self, "relationship_to_player", relationship)
        object.__setattr__(self, "player_controlled", bool(self.player_controlled))
        object.__setattr__(self, "retaliates", bool(self.retaliates))
        object.__setattr__(self, "assists", bool(self.assists))


@dataclass(frozen=True)
class MapStudioPIECombatAction:
    """One immutable basic-attack request in the player or retaliation queue."""

    action_id: int
    actor_id: str
    target_id: str
    queued_at: float
    kind: str = "basic_attack"
    automatic: bool = False


@dataclass(frozen=True)
class MapStudioPIECombatEvent:
    """One deterministic combat diagnostic and optional animation request."""

    sequence: int
    simulation_time: float
    kind: str
    message: str
    actor_id: str = ""
    target_id: str = ""
    action_id: int | None = None
    round_index: int = 0
    d20_roll: int | None = None
    total_roll: int | None = None
    target_armor_class: int | None = None
    damage: int | None = None
    damage_type: str = ""
    critical: bool = False
    remaining_hp: int | None = None
    outcome: str = ""  # "victory" | "defeat" on combat_ended
    animation_actor_id: str = ""
    animation_role: str = ""
    animation_candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class MapStudioPIECombatantSnapshot:
    """Immutable public state for one participant at one simulation instant."""

    entity_id: str
    display_name: str
    relationship_to_player: str
    current_hp: int
    max_hp: int
    armor_class: int
    alive: bool
    engaged: bool
    initiative_roll: int | None
    initiative_total: int | None
    animations: MapStudioPIECombatAnimationRoles


@dataclass(frozen=True)
class MapStudioPIECombatSnapshot:
    """Complete immutable state suitable for tests, HUDs, and IPC proof."""

    simulation_time: float
    paused: bool
    active: bool
    round_index: int
    round_seconds: float
    next_round_in: float | None
    initiative_order: tuple[str, ...]
    combatants: tuple[MapStudioPIECombatantSnapshot, ...]
    queued_actions: tuple[MapStudioPIECombatAction, ...]
    events: tuple[MapStudioPIECombatEvent, ...]
    outcome: str = ""  # "victory" | "defeat" once combat has resolved; else ""
    limitations: tuple[str, ...] = PIE_COMBAT_RUNTIME_LIMITATIONS

    def combatant(self, entity_id: str) -> MapStudioPIECombatantSnapshot | None:
        wanted = str(entity_id or "")
        return next((row for row in self.combatants if row.entity_id == wanted), None)


@dataclass
class _RuntimeCombatant:
    spec: MapStudioPIECombatant
    current_hp: int
    engaged: bool = False
    initiative_roll: int | None = None
    initiative_total: int | None = None

    @property
    def alive(self) -> bool:
        return self.current_hp > 0


class _StableCombatRNG:
    """Small version-stable LCG; never shares process-global random state."""

    _MULTIPLIER = 1_664_525
    _INCREMENT = 1_013_904_223
    _MASK = 0xFFFFFFFF

    def __init__(self, seed: int) -> None:
        self._state = int(seed) & self._MASK

    def randint(self, low: int, high: int) -> int:
        if high < low:
            raise ValueError("Stable combat RNG received an inverted range.")
        self._state = (self._state * self._MULTIPLIER + self._INCREMENT) & self._MASK
        return int(low) + (self._state % ((int(high) - int(low)) + 1))


class MapStudioPIECombatRuntime:
    """Deterministic real-time-with-pause d20 combat preview.

    A queued player attack engages only its explicit hostile target.  Once
    engaged, a living hostile with ``retaliates=True`` makes one automatic
    basic attack per three-second round.  One queued player action is consumed
    per round.  Initiative orders simultaneous round actions; a defeated actor
    cannot finish a later action in the same round.
    """

    def __init__(
        self,
        combatants: Iterable[MapStudioPIECombatant],
        *,
        player_id: str,
        seed: int = 1,
        round_seconds: float = PIE_COMBAT_ROUND_SECONDS,
    ) -> None:
        rows = tuple(combatants or ())
        if not rows:
            raise ValueError("PIE combat requires at least one combatant.")
        states: dict[str, _RuntimeCombatant] = {}
        for row in rows:
            if not isinstance(row, MapStudioPIECombatant):
                raise TypeError("PIE combat accepts only MapStudioPIECombatant values.")
            if row.entity_id in states:
                raise ValueError(f"Duplicate PIE combat entity id: {row.entity_id}.")
            states[row.entity_id] = _RuntimeCombatant(row, int(row.stats.current_hp))
        wanted_player = str(player_id or "").strip()
        player = states.get(wanted_player)
        if player is None:
            raise ValueError(f"PIE combat player {wanted_player!r} is not registered.")
        if not player.spec.player_controlled:
            raise ValueError("The PIE combat player must be marked player_controlled.")
        seconds = float(round_seconds)
        if not math.isfinite(seconds) or seconds <= 0.0:
            raise ValueError("PIE combat round duration must be finite and positive.")

        self._states = states
        self._player_id = wanted_player
        self._round_seconds = seconds
        self._rng = _StableCombatRNG(seed)
        self._time = 0.0
        self._paused = False
        self._active = False
        self._outcome = ""
        self._round_index = 0
        self._next_round_time: float | None = None
        self._engaged_hostiles: set[str] = set()
        # Assisting allies (party companions / friendly NPCs) fight for the player.
        self._assisting_ally_ids: tuple[str, ...] = tuple(
            entity_id
            for entity_id, state in states.items()
            if state.spec.assists
            and not state.spec.player_controlled
            and state.spec.relationship_to_player in {"friendly", "player_ally"}
        )
        self._player_actions: list[MapStudioPIECombatAction] = []
        self._events: list[MapStudioPIECombatEvent] = []
        self._next_action_id = 1
        self._next_event_sequence = 1

    @property
    def simulation_time(self) -> float:
        return float(self._time)

    @property
    def paused(self) -> bool:
        return bool(self._paused)

    @property
    def active(self) -> bool:
        return bool(self._active)

    @property
    def player_id(self) -> str:
        return self._player_id

    @property
    def queued_actions(self) -> tuple[MapStudioPIECombatAction, ...]:
        return tuple(self._player_actions)

    def pause(self) -> MapStudioPIECombatSnapshot:
        if not self._paused:
            self._paused = True
            self._emit("combat_paused", "PIE combat paused; queued actions and simulation time are preserved.")
        return self.snapshot()

    def resume(self) -> MapStudioPIECombatSnapshot:
        if self._paused:
            self._paused = False
            self._emit("combat_resumed", "PIE combat resumed from the preserved simulation instant.")
        return self.snapshot()

    def toggle_pause(self) -> MapStudioPIECombatSnapshot:
        return self.resume() if self._paused else self.pause()

    def queue_player_attack(self, target_id: str) -> MapStudioPIECombatAction:
        """Queue one basic player attack and engage an explicit hostile target."""

        player = self._states[self._player_id]
        if not player.alive:
            raise ValueError("A defeated PIE player cannot queue an attack.")
        wanted = str(target_id or "").strip()
        target = self._states.get(wanted)
        if target is None:
            raise KeyError(f"Unknown PIE combat target: {wanted!r}.")
        if wanted == self._player_id:
            raise ValueError("The PIE player cannot attack itself.")
        if target.spec.relationship_to_player != "hostile":
            raise ValueError("PIE basic attacks require an explicitly hostile target.")
        if not target.alive:
            raise ValueError("A defeated PIE target cannot receive another queued attack.")

        first_engagement = wanted not in self._engaged_hostiles
        self._engaged_hostiles.add(wanted)
        player.engaged = True
        target.engaged = True
        self._ensure_initiative(self._player_id)
        self._ensure_initiative(wanted)
        if first_engagement:
            self._emit(
                "combat_started" if not self._active else "combatant_engaged",
                f"{target.spec.display_name} entered the deterministic PIE combat preview.",
                actor_id=self._player_id,
                target_id=wanted,
            )
            self._emit_animation(self._player_id, "ready", "combat_ready")
            self._emit_animation(wanted, "ready", "combat_ready")
            # Party companions / friendly allies join the fight when combat opens.
            for ally_id in self._assisting_ally_ids:
                ally = self._states.get(ally_id)
                if ally is None or not ally.alive or ally.engaged:
                    continue
                ally.engaged = True
                self._ensure_initiative(ally_id)
                self._emit(
                    "ally_engaged",
                    f"{ally.spec.display_name} joined the PIE combat preview to assist the player.",
                    actor_id=ally_id,
                    target_id=wanted,
                )
                self._emit_animation(ally_id, "ready", "combat_ready")
        self._active = True
        if self._next_round_time is None:
            self._next_round_time = self._time + self._round_seconds

        action = MapStudioPIECombatAction(
            action_id=self._next_action_id,
            actor_id=self._player_id,
            target_id=wanted,
            queued_at=self._time,
        )
        self._next_action_id += 1
        self._player_actions.append(action)
        self._emit(
            "action_queued",
            f"Queued basic attack on {target.spec.display_name} for a future PIE combat round.",
            actor_id=self._player_id,
            target_id=wanted,
            action_id=action.action_id,
        )
        return action

    def clear_player_actions(self) -> MapStudioPIECombatSnapshot:
        """Clear queued player commands while preserving live round state."""

        removed = len(self._player_actions)
        self._player_actions.clear()
        self._emit(
            "action_queue_cleared",
            f"Cleared {removed} queued PIE combat action(s); the real-time encounter remains active.",
            actor_id=self._player_id,
        )
        return self.snapshot()

    def advance(self, real_delta_time: float) -> MapStudioPIECombatSnapshot:
        """Advance simulation time and resolve every crossed round boundary."""

        delta = float(real_delta_time)
        if not math.isfinite(delta) or delta < 0.0:
            raise ValueError("PIE combat delta time must be finite and non-negative.")
        if self._paused:
            return self.snapshot()
        target_time = self._time + delta
        while self._next_round_time is not None and self._next_round_time <= target_time + _EPSILON:
            self._time = float(self._next_round_time)
            self._resolve_round()
        self._time = target_time
        return self.snapshot()

    def snapshot(self) -> MapStudioPIECombatSnapshot:
        next_round_in = None
        if self._next_round_time is not None:
            next_round_in = max(0.0, float(self._next_round_time) - float(self._time))
        combatants = tuple(
            MapStudioPIECombatantSnapshot(
                entity_id=entity_id,
                display_name=state.spec.display_name,
                relationship_to_player=state.spec.relationship_to_player,
                current_hp=int(state.current_hp),
                max_hp=int(state.spec.stats.max_hp),
                armor_class=int(state.spec.stats.armor_class),
                alive=state.alive,
                engaged=bool(state.engaged),
                initiative_roll=state.initiative_roll,
                initiative_total=state.initiative_total,
                animations=state.spec.animations,
            )
            for entity_id, state in sorted(self._states.items())
        )
        return MapStudioPIECombatSnapshot(
            simulation_time=float(self._time),
            paused=bool(self._paused),
            active=bool(self._active),
            round_index=int(self._round_index),
            round_seconds=float(self._round_seconds),
            next_round_in=next_round_in,
            initiative_order=self._initiative_order(),
            combatants=combatants,
            queued_actions=tuple(self._player_actions),
            events=tuple(self._events),
            outcome=str(self._outcome),
        )

    def events_since(self, sequence: int = 0) -> tuple[MapStudioPIECombatEvent, ...]:
        """Return immutable events after an adapter-owned sequence cursor."""

        cursor = int(sequence)
        return tuple(event for event in self._events if event.sequence > cursor)

    def _ensure_initiative(self, entity_id: str) -> None:
        state = self._states[entity_id]
        if state.initiative_roll is not None:
            return
        roll = self._rng.randint(1, 20)
        total = roll + state.spec.stats.initiative_bonus
        state.initiative_roll = roll
        state.initiative_total = total
        self._emit(
            "initiative_rolled",
            f"{state.spec.display_name} rolled initiative {roll} + {state.spec.stats.initiative_bonus} = {total}.",
            actor_id=entity_id,
            d20_roll=roll,
            total_roll=total,
        )

    def _initiative_order(self) -> tuple[str, ...]:
        participants = [
            state
            for state in self._states.values()
            if state.engaged and state.initiative_total is not None
        ]
        participants.sort(key=lambda state: (-int(state.initiative_total or 0), state.spec.entity_id))
        return tuple(state.spec.entity_id for state in participants)

    def _resolve_round(self) -> None:
        boundary = float(self._next_round_time if self._next_round_time is not None else self._time)
        self._round_index += 1
        self._emit(
            "round_started",
            f"PIE combat round {self._round_index} started at {boundary:.3f}s.",
        )

        actions: list[MapStudioPIECombatAction] = []
        while self._player_actions:
            candidate = self._player_actions.pop(0)
            actor = self._states.get(candidate.actor_id)
            target = self._states.get(candidate.target_id)
            if actor is not None and target is not None and actor.alive and target.alive:
                actions.append(candidate)
                break
            self._emit(
                "action_cancelled",
                "A queued PIE attack was cancelled because its actor or target was no longer alive.",
                actor_id=candidate.actor_id,
                target_id=candidate.target_id,
                action_id=candidate.action_id,
            )

        player = self._states[self._player_id]
        if player.alive:
            for hostile_id in sorted(self._engaged_hostiles):
                hostile = self._states.get(hostile_id)
                if hostile is None or not hostile.alive or not hostile.spec.retaliates:
                    continue
                actions.append(
                    MapStudioPIECombatAction(
                        action_id=self._next_action_id,
                        actor_id=hostile_id,
                        target_id=self._player_id,
                        queued_at=boundary,
                        automatic=True,
                    )
                )
                self._next_action_id += 1

        # Assisting allies each make one basic attack against a living engaged
        # hostile (lowest-id first — deterministic, no positional AI).
        for ally_id in self._assisting_ally_ids:
            ally = self._states.get(ally_id)
            if ally is None or not ally.alive or not ally.engaged:
                continue
            ally_target_id = next(
                (
                    hostile_id
                    for hostile_id in sorted(self._engaged_hostiles)
                    if (self._states.get(hostile_id) is not None and self._states[hostile_id].alive)
                ),
                "",
            )
            if not ally_target_id:
                continue
            actions.append(
                MapStudioPIECombatAction(
                    action_id=self._next_action_id,
                    actor_id=ally_id,
                    target_id=ally_target_id,
                    queued_at=boundary,
                    automatic=True,
                )
            )
            self._next_action_id += 1

        actions.sort(
            key=lambda action: (
                -int(self._states[action.actor_id].initiative_total or 0),
                action.actor_id,
                action.action_id,
            )
        )
        for action in actions:
            actor = self._states[action.actor_id]
            target = self._states[action.target_id]
            if not actor.alive or not target.alive:
                self._emit(
                    "action_skipped",
                    "A PIE combat action was skipped after an earlier initiative action defeated its actor or target.",
                    actor_id=action.actor_id,
                    target_id=action.target_id,
                    action_id=action.action_id,
                )
                continue
            self._resolve_attack(action)

        self._finish_or_schedule_next_round(boundary)

    def _resolve_attack(self, action: MapStudioPIECombatAction) -> None:
        actor = self._states[action.actor_id]
        target = self._states[action.target_id]
        self._emit_animation(
            action.actor_id,
            "attack",
            "attack_started",
            target_id=action.target_id,
            action_id=action.action_id,
            message=f"{actor.spec.display_name} began a basic attack on {target.spec.display_name}.",
        )
        roll = self._rng.randint(1, 20)
        total = roll + actor.spec.stats.attack_bonus
        armor_class = target.spec.stats.armor_class
        hit = roll == 20 or (roll != 1 and total >= armor_class)
        if not hit:
            self._emit(
                "attack_missed",
                f"{actor.spec.display_name} missed {target.spec.display_name}: d20 {roll} + "
                f"{actor.spec.stats.attack_bonus} = {total} vs AC {armor_class}.",
                actor_id=action.actor_id,
                target_id=action.target_id,
                action_id=action.action_id,
                d20_roll=roll,
                total_roll=total,
                target_armor_class=armor_class,
                remaining_hp=target.current_hp,
            )
            return

        damage = int(actor.spec.stats.damage.bonus)
        for _ in range(actor.spec.stats.damage.count):
            damage += self._rng.randint(1, actor.spec.stats.damage.sides)
        damage = max(0, damage)
        # d20 critical: a roll within the weapon's threat range multiplies the
        # damage. A basic weapon threatens only on a natural 20 (threat 1) at x2.
        threat_floor = 21 - int(actor.spec.stats.critical_threat)
        is_critical = roll >= threat_floor
        if is_critical:
            damage = damage * int(actor.spec.stats.critical_multiplier)
        target.current_hp = max(0, target.current_hp - damage)
        target_animation = self._animation_fields(action.target_id, "damage") if target.alive else {}
        crit_note = (
            f" critical x{int(actor.spec.stats.critical_multiplier)}!" if is_critical else ""
        )
        damage_type = str(actor.spec.stats.damage_type or "Physical")
        self._emit(
            "attack_hit",
            f"{actor.spec.display_name} hit {target.spec.display_name}: d20 {roll} + "
            f"{actor.spec.stats.attack_bonus} = {total} vs AC {armor_class};{crit_note} "
            f"{damage} {damage_type} damage, {target.current_hp} HP remaining.",
            actor_id=action.actor_id,
            target_id=action.target_id,
            action_id=action.action_id,
            d20_roll=roll,
            total_roll=total,
            target_armor_class=armor_class,
            damage=damage,
            damage_type=damage_type,
            critical=is_critical,
            remaining_hp=target.current_hp,
            **target_animation,
        )
        if not target.alive:
            self._emit_animation(
                action.target_id,
                "death",
                "combatant_defeated",
                actor_id=action.actor_id,
                target_id=action.target_id,
                action_id=action.action_id,
                remaining_hp=0,
                message=f"{target.spec.display_name} was defeated in the editor-only combat preview.",
            )

    def _finish_or_schedule_next_round(self, boundary: float) -> None:
        player = self._states[self._player_id]
        living_hostiles = tuple(
            hostile_id
            for hostile_id in sorted(self._engaged_hostiles)
            if hostile_id in self._states and self._states[hostile_id].alive
        )
        self._player_actions = [
            action
            for action in self._player_actions
            if self._states.get(action.target_id) is not None and self._states[action.target_id].alive
        ]
        if not player.alive or not living_hostiles:
            self._active = False
            self._next_round_time = None
            self._player_actions.clear()
            # Defeat takes precedence when the player falls (even if the last
            # hostile died the same round); otherwise every hostile is down.
            self._outcome = "defeat" if not player.alive else "victory"
            summary = (
                "the player's side was defeated"
                if self._outcome == "defeat"
                else "every engaged hostile was defeated"
            )
            self._emit(
                "combat_ended",
                f"PIE combat ended in {self._outcome}: {summary}.",
                actor_id=self._player_id,
                outcome=self._outcome,
            )
            return
        self._active = True
        self._next_round_time = float(boundary) + self._round_seconds

    def _animation_fields(self, entity_id: str, role: str) -> dict[str, object]:
        candidates = self._states[entity_id].spec.animations.candidates(role)
        return {
            "animation_actor_id": entity_id,
            "animation_role": role,
            "animation_candidates": candidates,
        }

    def _emit_animation(
        self,
        entity_id: str,
        role: str,
        kind: str,
        *,
        message: str | None = None,
        **fields: object,
    ) -> MapStudioPIECombatEvent:
        state = self._states[entity_id]
        fields.setdefault("actor_id", entity_id)
        return self._emit(
            kind,
            message or f"{state.spec.display_name} requested the PIE {role} animation role.",
            **self._animation_fields(entity_id, role),
            **fields,
        )

    def _emit(self, kind: str, message: str, **fields: object) -> MapStudioPIECombatEvent:
        event = MapStudioPIECombatEvent(
            sequence=self._next_event_sequence,
            simulation_time=float(self._time),
            kind=str(kind or "combat_event"),
            message=str(message or ""),
            round_index=int(self._round_index),
            **fields,
        )
        self._next_event_sequence += 1
        self._events.append(event)
        return event


__all__ = [
    "MapStudioPIECombatAction",
    "MapStudioPIECombatAnimationRoles",
    "MapStudioPIECombatEvent",
    "MapStudioPIECombatRuntime",
    "MapStudioPIECombatSnapshot",
    "MapStudioPIECombatStats",
    "MapStudioPIECombatant",
    "MapStudioPIECombatantSnapshot",
    "MapStudioPIEDamageDice",
    "PIE_COMBAT_ROUND_SECONDS",
    "PIE_COMBAT_RUNTIME_LIMITATIONS",
    "derive_pie_weapon_damage_dice",
    "pie_damage_type_label",
]
