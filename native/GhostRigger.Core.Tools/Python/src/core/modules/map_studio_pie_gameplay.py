"""Headless gameplay orchestration for Map Studio Play-in-Editor.

This module joins the independent focus/action, DLG, and combat contracts into
one runtime-only state consumed by :mod:`map_studio_pie`.  It never mutates the
entity registry or authored KMAP data and never executes arbitrary NWScript.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Any, Callable, Iterable, Mapping

from .map_studio_pie_combat import (
    MapStudioPIECombatAnimationRoles,
    MapStudioPIECombatEvent,
    MapStudioPIECombatRuntime,
    MapStudioPIECombatSnapshot,
    MapStudioPIECombatStats,
    MapStudioPIECombatant,
    MapStudioPIEDamageDice,
)
from .map_studio_pie_dialogue import (
    MapStudioPIEDialogueSession,
    MapStudioPIEDialogueSnapshot,
)
from .map_studio_pie_entities import PIEEntity, PIEEntityRegistry
from .map_studio_pie_journal import MapStudioPIEJournalState, MapStudioPIEQuestState
from .map_studio_pie_triggers import TriggerCrossingTracker, build_trigger_volumes
from .map_studio_pie_interactions import (
    ACTION_ATTACK,
    ACTION_CONTAINER,
    ACTION_DOOR,
    PIEFocusState,
    PIEInteractionResult,
    PIEInteractionRouter,
    PIEInteractionSnapshot,
    acquire_pie_focus,
    cycle_pie_focus,
    focus_candidates,
)


Vec3 = tuple[float, float, float]
DialogueLoader = Callable[[str], bytes | None]
ItemInspector = Callable[[str], Mapping[str, Any]]
TLKLookup = Callable[[int], str]


# K2 FUN_0057be40 uses separate Q/E candidate radii: 10 m for ordinary
# interactables and 30 m for hostile targets.  LOS pruning remains an injected
# visibility set because the editor renderer does not expose Odyssey's exact
# FUN_00778510 query.  Action activation still enforces its smaller per-action
# interaction range through PIEFocusState.
PIE_QE_INTERACTABLE_DISTANCE = 10.0
PIE_QE_HOSTILE_DISTANCE = 30.0


_PIE_WORLD_TARGET_HEIGHTS = {
    "creature": 1.80,
    "door": 2.20,
    "placeable": 1.10,
    "store": 1.45,
    "trigger": 0.35,
}


def _world_target_extent(entity: PIEEntity) -> tuple[float, float]:
    default_height = _PIE_WORLD_TARGET_HEIGHTS.get(entity.kind, 0.9)
    try:
        radius = float(entity.target_radius or 0.5)
    except (TypeError, ValueError):
        radius = 0.5
    try:
        height = float((entity.metadata or {}).get("selection_height", default_height) or default_height)
    except (TypeError, ValueError):
        height = default_height
    if not math.isfinite(radius):
        radius = 0.5
    if not math.isfinite(height):
        height = default_height
    return max(0.1, min(8.0, radius)), max(0.2, min(12.0, height))


@dataclass(frozen=True)
class MapStudioPIEGlobalValue:
    """One current global variable exposed for a HUD/state inspector."""

    name: str
    kind: str  # "number" | "boolean" | "string"
    value: int | bool | str


@dataclass(frozen=True)
class MapStudioPIEGameplayEvent:
    """One presentation-neutral gameplay event for adapters and tests."""

    kind: str
    message: str
    entity_id: str = ""
    target_id: str = ""
    animation_role: str = ""
    animation_candidates: tuple[str, ...] = ()
    value: int | float | str | None = None


@dataclass(frozen=True)
class MapStudioPIEWorldTarget:
    """Renderer-neutral selection volume for one gameplay interactable.

    Retained character meshes are posed on the GPU, while the generic editor
    triangle picker may still see their unposed CPU vertices.  PIE therefore
    publishes the same stable gameplay identity and footprint used by Q/E as a
    compact upright selection volume.  The Qt adapter projects it and still
    uses the scene pick depth to reject targets hidden by nearer geometry.
    """

    entity_id: str
    kind: str
    position: Vec3
    target_radius: float
    height: float


@dataclass(frozen=True)
class MapStudioPIEGameplaySnapshot:
    """Immutable state for the PIE HUD and controller adapter."""

    focus: PIEFocusState | None
    interaction: PIEInteractionSnapshot
    world_targets: tuple[MapStudioPIEWorldTarget, ...] = ()
    dialogue: MapStudioPIEDialogueSnapshot | None = None
    combat: MapStudioPIECombatSnapshot | None = None
    open_container_id: str = ""
    last_result: PIEInteractionResult | None = None
    movement_locked: bool = False
    mode: str = "exploration"
    player_position: Vec3 = (0.0, 0.0, 0.0)
    player_facing_radians: float = 0.0
    camera_forward: Vec3 = (1.0, 0.0, 0.0)
    limitations: tuple[str, ...] = ()
    journal: tuple[MapStudioPIEQuestState, ...] = ()
    globals: tuple[MapStudioPIEGlobalValue, ...] = ()


class MapStudioPIEGameplayRuntime:
    """Coordinate exploration, dialogue, inventory, doors, and RTwP combat."""

    def __init__(
        self,
        registry: PIEEntityRegistry,
        *,
        game: str,
        dialogue_loader: DialogueLoader | None = None,
        item_inspector: ItemInspector | None = None,
        tlk_lookup: TLKLookup | None = None,
        dialogue_condition_evaluator: Any = None,
        dialogue_start_overrides: Mapping[str, object] | None = None,
        player_combat_stats: MapStudioPIECombatStats | None = None,
        combat_seed: int = 1,
        journal_seed: Iterable[Any] | None = None,
        script_loader: Any = None,
        party_combatants: Iterable[Mapping[str, Any]] | None = None,
    ) -> None:
        self.registry = registry
        # Compiled-NCS loader (resref -> bytes) used to execute a dialogue node
        # action script's bounded literal global/journal writes.
        self._script_loader = script_loader
        # Resolved party companion combat stats (from the configured roster);
        # they join RTwP combat as assisting allies when it opens.
        self._party_combatants = tuple(dict(member) for member in (party_combatants or ()))
        # Runtime-only quest log; seeded from a module OnEnter script's literal
        # AddJournalQuestEntry writes, then advanced by dialogue journal nodes.
        self._journal = MapStudioPIEJournalState(seed=journal_seed)
        self.game = str(game or "K1").strip().upper()
        self._dialogue_loader = dialogue_loader
        self._tlk_lookup = tlk_lookup
        self._dialogue_condition_evaluator = dialogue_condition_evaluator
        self._dialogue_start_overrides = {
            str(resref or "").strip().lower(): value
            for resref, value in dict(dialogue_start_overrides or {}).items()
            if str(resref or "").strip()
        }
        self._player_combat_stats = player_combat_stats or MapStudioPIECombatStats(
            max_hp=24,
            current_hp=24,
            armor_class=14,
            attack_bonus=3,
            damage=MapStudioPIEDamageDice(1, 8, 2),
            initiative_bonus=2,
        )
        self._combat_seed = int(combat_seed)
        self._focus: PIEFocusState | None = None
        self._retained_focus_id = ""
        self._dialogue: MapStudioPIEDialogueSession | None = None
        self._combat: MapStudioPIECombatRuntime | None = None
        self._combat_event_cursor = 0
        self._open_container_id = ""
        self._last_result: PIEInteractionResult | None = None
        self._events: list[MapStudioPIEGameplayEvent] = []
        self._last_player_position: Vec3 = (0.0, 0.0, 0.0)
        self._last_player_facing_radians = 0.0
        self._last_camera_forward: Vec3 = (1.0, 0.0, 0.0)
        self._entity_by_id = {entity.entity_id: entity for entity in registry.entities}
        self._trigger_tracker = TriggerCrossingTracker(build_trigger_volumes(registry.entities))
        self._world_targets = tuple(
            MapStudioPIEWorldTarget(
                entity_id=entity.entity_id,
                kind=entity.kind,
                position=entity.position,
                target_radius=extent[0],
                height=extent[1],
            )
            for entity in registry.entities
            if (
                entity.entity_id != "pie:player"
                and (entity.focusable or entity.interactive)
                and bool((entity.metadata or {}).get("visible", True))
            )
            for extent in (_world_target_extent(entity),)
        )
        self._router = PIEInteractionRouter(
            registry,
            container_inventories=self._container_inventories(item_inspector),
            dialogue_callback=self._start_dialogue,
            combat_callback=self._start_combat,
        )

    def _container_inventories(
        self,
        item_inspector: ItemInspector | None,
    ) -> dict[str, tuple[dict[str, Any], ...]]:
        result: dict[str, tuple[dict[str, Any], ...]] = {}
        cache: dict[str, Mapping[str, Any]] = {}
        for entity in self.registry.entities:
            if not entity.has_inventory:
                continue
            rows: list[dict[str, Any]] = []
            for source in entity.inventory_items:
                row = dict(source)
                resref = str(row.get("resref") or "").strip().lower()
                if not resref:
                    continue
                if item_inspector is not None:
                    if resref not in cache:
                        try:
                            cache[resref] = dict(item_inspector(resref) or {})
                        except Exception:
                            cache[resref] = {}
                    inspected = cache[resref]
                    row.setdefault("display_name", str(inspected.get("name") or ""))
                    row.setdefault("droppable", not bool(inspected.get("plot", False)))
                rows.append(row)
            result[entity.entity_id] = tuple(rows)
        return result

    @property
    def focus(self) -> PIEFocusState | None:
        return self._focus

    @property
    def router(self) -> PIEInteractionRouter:
        return self._router

    @property
    def dialogue_session(self) -> MapStudioPIEDialogueSession | None:
        return self._dialogue

    @property
    def combat_runtime(self) -> MapStudioPIECombatRuntime | None:
        return self._combat

    def _emit(
        self,
        kind: str,
        message: str,
        *,
        entity_id: str = "",
        target_id: str = "",
        animation_role: str = "",
        animation_candidates: tuple[str, ...] = (),
        value: int | float | str | None = None,
    ) -> None:
        self._events.append(
            MapStudioPIEGameplayEvent(
                kind=str(kind),
                message=str(message),
                entity_id=str(entity_id or ""),
                target_id=str(target_id or ""),
                animation_role=str(animation_role or ""),
                animation_candidates=tuple(animation_candidates or ()),
                value=value,
            )
        )

    def _capture_dialogue_events(self, snapshot: MapStudioPIEDialogueSnapshot) -> None:
        for event in snapshot.events:
            if event.kind == "journal_updated":
                # Surface journal updates as a top-level gameplay event carrying
                # the "quest:entry" value so a HUD/quest-log adapter can list it,
                # and fold it into the runtime quest log (monotonic per plot).
                value = str(getattr(event, "value", "") or "")
                self._journal.record_value(value)
                self._emit(
                    "journal_updated",
                    event.message,
                    entity_id=snapshot.owner_id,
                    value=value,
                )
                continue
            self._emit(
                f"dialogue_{event.kind}",
                event.message,
                entity_id=snapshot.owner_id,
                target_id=snapshot.listener_id,
            )

    def _capture_combat_events(self) -> None:
        if self._combat is None:
            return
        for event in self._combat.events_since(self._combat_event_cursor):
            self._capture_combat_event(event)
            self._combat_event_cursor = max(self._combat_event_cursor, event.sequence)

    def _capture_combat_event(self, event: MapStudioPIECombatEvent) -> None:
        # combat_ended carries the victory/defeat outcome; other events carry the
        # damage or d20 roll for a HUD/log adapter.
        value: int | float | str | None = event.outcome or event.damage
        if value is None:
            value = event.d20_roll
        self._emit(
            f"combat_{event.kind}",
            event.message,
            entity_id=event.actor_id or event.animation_actor_id,
            target_id=event.target_id,
            animation_role=event.animation_role,
            animation_candidates=event.animation_candidates,
            value=value,
        )

    def _record_result(self, result: PIEInteractionResult) -> PIEInteractionResult:
        self._last_result = result
        self._emit(
            f"interaction_{result.status}",
            result.message,
            entity_id=result.entity_id,
            value=result.command,
        )
        for warning in result.coverage_warnings:
            self._emit("interaction_coverage_warning", warning, entity_id=result.entity_id)
        self._execute_interaction_scripts(result)
        if result.executed and result.command == ACTION_CONTAINER:
            self._open_container_id = result.entity_id
        return result

    def _execute_scripts_into_shared_state(
        self, scripts: Any, entity_id: str, *, source_label: str
    ) -> tuple[list[str], list[str]]:
        """Run bounded literal global/journal writes from a set of NCS scripts.

        Shared by placeable/door interaction scripts and trigger OnEnter scripts:
        loads each compiled NCS via the session loader and folds its literal
        `SetGlobalNumber`/`SetGlobalBoolean`/`SetGlobalString`/`AddJournalQuestEntry`
        writes into the shared condition state (and the runtime quest log). Returns
        ``(applied_labels, executed_resrefs)``. Non-literal/branching scripts stay
        honestly deferred. Preview state only, never campaign state.
        """

        resrefs = tuple(r for r in (scripts or ()) if str(r or "").strip())
        if not resrefs or not callable(self._script_loader):
            return [], []
        from .map_studio_pie_scripting import execute_ncs_global_effects

        def _journal_sink(name: str, entry: int) -> None:
            self._journal.record(name, entry)
            self._emit(
                "journal_updated",
                f"PIE would set journal quest {name!r} to entry {int(entry)} via the {source_label} "
                "script's AddJournalQuestEntry. PIE reports it without mutating campaign quest state.",
                entity_id=entity_id,
                value=f"{name}:{int(entry)}",
            )

        applied: list[str] = []
        executed_scripts: list[str] = []
        for resref in resrefs:
            try:
                data = self._script_loader(resref)
            except Exception:
                data = None
            if not data:
                continue
            labels = execute_ncs_global_effects(
                bytes(data),
                evaluator=self._dialogue_condition_evaluator,
                journal_sink=_journal_sink,
            )
            if labels:
                executed_scripts.append(str(resref))
                applied.extend(labels)
        return applied, executed_scripts

    def _execute_interaction_scripts(self, result: PIEInteractionResult) -> None:
        """Execute a placeable/door interaction script's literal global writes.

        The router reports OnUsed/OnOpen NCS as deferred; with a compiled-NCS
        loader PIE runs the bounded literal writes into the shared condition
        state (and the runtime quest log). Preview state only.
        """

        applied, executed_scripts = self._execute_scripts_into_shared_state(
            getattr(result, "deferred_scripts", ()), result.entity_id, source_label="interaction"
        )
        if executed_scripts:
            self._emit(
                "interaction_script_executed",
                "PIE executed the interaction script's literal global/journal writes: "
                + ", ".join(applied)
                + ". Editor-side preview state, not campaign state.",
                entity_id=result.entity_id,
                value=",".join(executed_scripts),
            )

    def _start_dialogue(self, entity: PIEEntity, _action: object) -> str:
        resref = str(entity.conversation or "").strip()
        if not resref:
            raise ValueError(f"{entity.display_name or entity.entity_id} has no dialogue resref.")
        if self._dialogue_loader is None:
            raise RuntimeError(f"DLG {resref} cannot be resolved by this PIE session.")
        payload = self._dialogue_loader(resref)
        if not payload:
            raise FileNotFoundError(f"DLG {resref} was not found in the active {self.game} resources.")
        payload = bytes(payload)
        starter_link_id = ""
        override = self._dialogue_start_overrides.get(resref.lower())
        if isinstance(override, Mapping):
            candidate_link_id = str(override.get("starter_link_id") or "").strip().lower()
            expected_sha256 = str(override.get("resource_sha256") or "").strip().lower()
            actual_sha256 = hashlib.sha256(payload).hexdigest()
            if candidate_link_id and (not expected_sha256 or expected_sha256 == actual_sha256):
                starter_link_id = candidate_link_id
            elif candidate_link_id and expected_sha256 != actual_sha256:
                self._emit(
                    "dialogue_override_stale",
                    f"DLG {resref} changed since its PIE start override was selected; using canonical Auto start.",
                    entity_id=entity.entity_id,
                )
        if self._dialogue is not None and self._dialogue.active:
            self._dialogue.abort()
        self._open_container_id = ""

        def _new_session(assume_unknown: bool) -> MapStudioPIEDialogueSession:
            return MapStudioPIEDialogueSession(
                payload,
                game=self.game,
                resref=resref,
                owner_id=entity.entity_id,
                listener_id="pie:player",
                tlk_lookup=self._tlk_lookup,
                condition_evaluator=self._dialogue_condition_evaluator,
                script_loader=self._script_loader,
                starter_link_id=starter_link_id,
                allow_unknown_starter_assumption=assume_unknown,
            )

        self._dialogue = _new_session(False)
        snapshot = self._dialogue.start()
        if snapshot.blocked and not starter_link_id:
            # Every starting line's Active condition was unprovable (arbitrary
            # NWScript PIE cannot evaluate) — the common case for commoner
            # one-liners like 200comm/200comf. Retail runs the script and shows a
            # line, so instead of showing nothing PIE assumes the first unknown
            # starter and marks it as a preview assumption.
            assumed = _new_session(True)
            assumed_snapshot = assumed.start()
            if not assumed_snapshot.blocked:
                self._dialogue = assumed
                snapshot = assumed_snapshot
                self._emit(
                    "dialogue_starter_assumed",
                    f"PIE could not prove a starting line for {resref}; showing the first as a preview "
                    "assumption (retail runs the condition script). Editor-side preview only.",
                    entity_id=entity.entity_id,
                    value=resref,
                )
        self._capture_dialogue_events(snapshot)
        if snapshot.blocked:
            raise RuntimeError(snapshot.warnings[-1] if snapshot.warnings else f"DLG {resref} could not start.")
        return f"Started dialogue {resref} with {entity.display_name or entity.entity_id}."

    @staticmethod
    def _damage_dice(entity: PIEEntity) -> MapStudioPIEDamageDice:
        minimum = max(1, int(entity.damage_min or 1))
        maximum = max(minimum, int(entity.damage_max or minimum))
        return MapStudioPIEDamageDice(1, max(1, maximum - minimum + 1), minimum - 1)

    def _combatants(self) -> tuple[MapStudioPIECombatant, ...]:
        rows: list[MapStudioPIECombatant] = [
            MapStudioPIECombatant(
                entity_id="pie:player",
                display_name="Player",
                relationship_to_player="player",
                stats=self._player_combat_stats,
                animations=MapStudioPIECombatAnimationRoles(),
                player_controlled=True,
                retaliates=False,
            )
        ]
        for entity in self.registry.of_kind("creature"):
            maximum_hp = max(1, int(entity.max_hp or entity.current_hp or 1))
            current_hp = max(0, min(maximum_hp, int(entity.current_hp or maximum_hp)))
            rows.append(
                MapStudioPIECombatant(
                    entity_id=entity.entity_id,
                    display_name=entity.display_name or entity.tag or entity.entity_id,
                    relationship_to_player=entity.faction if entity.faction in {"hostile", "friendly", "neutral"} else "neutral",
                    stats=MapStudioPIECombatStats(
                        max_hp=maximum_hp,
                        current_hp=current_hp,
                        armor_class=max(1, int(entity.armor_class or 10)),
                        attack_bonus=int(entity.attack_bonus or 0),
                        damage=self._damage_dice(entity),
                        initiative_bonus=int(entity.initiative_bonus or 0),
                        critical_threat=max(1, int(getattr(entity, "critical_threat", 1) or 1)),
                        critical_multiplier=max(1, int(getattr(entity, "critical_multiplier", 2) or 2)),
                        damage_type=str(getattr(entity, "damage_type", "Physical") or "Physical"),
                    ),
                    animations=MapStudioPIECombatAnimationRoles(),
                    retaliates=entity.faction == "hostile",
                    # Friendly NPCs assist the player when combat opens.
                    assists=entity.faction == "friendly",
                )
            )
        # Configured party companions join as assisting allies (resolved from
        # their UTC combat stats, same chain as creatures).
        for index, member in enumerate(self._party_combatants):
            maximum_hp = max(1, int(member.get("max_hp") or member.get("current_hp") or 1))
            current_hp = max(0, min(maximum_hp, int(member.get("current_hp") or maximum_hp)))
            damage_min = max(1, int(member.get("damage_min") or 1))
            damage_max = max(damage_min, int(member.get("damage_max") or damage_min))
            rows.append(
                MapStudioPIECombatant(
                    entity_id=str(member.get("entity_id") or f"pie:party:{index}"),
                    display_name=str(member.get("display_name") or f"Companion {index + 1}"),
                    relationship_to_player="friendly",
                    stats=MapStudioPIECombatStats(
                        max_hp=maximum_hp,
                        current_hp=current_hp,
                        armor_class=max(1, int(member.get("armor_class") or 10)),
                        attack_bonus=int(member.get("attack_bonus") or 0),
                        damage=MapStudioPIEDamageDice(1, max(1, damage_max - damage_min + 1), damage_min - 1),
                        initiative_bonus=int(member.get("initiative_bonus") or 0),
                        critical_threat=max(1, int(member.get("critical_threat") or 1)),
                        critical_multiplier=max(1, int(member.get("critical_multiplier") or 2)),
                        damage_type=str(member.get("damage_type") or "Physical"),
                    ),
                    animations=MapStudioPIECombatAnimationRoles(),
                    retaliates=False,
                    assists=True,
                )
            )
        return tuple(rows)

    def _start_combat(self, entity: PIEEntity, _action: object) -> str:
        if self._combat is None:
            self._combat = MapStudioPIECombatRuntime(
                self._combatants(),
                player_id="pie:player",
                seed=self._combat_seed,
            )
        self._open_container_id = ""
        if self._dialogue is not None and self._dialogue.active:
            self._dialogue.abort()
        action = self._combat.queue_player_attack(entity.entity_id)
        self._capture_combat_events()
        return f"Queued basic attack {action.action_id} against {entity.display_name or entity.entity_id}."

    def update_focus(
        self,
        player_position: Vec3,
        camera_forward: Vec3,
        *,
        visible_entity_ids: tuple[str, ...] | None = None,
    ) -> PIEFocusState | None:
        self._last_player_position = tuple(float(value) for value in player_position[:3])  # type: ignore[assignment]
        self._last_camera_forward = tuple(float(value) for value in camera_forward[:3])  # type: ignore[assignment]
        prior_id = self._focus.entity_id if self._focus is not None else ""
        combat_eligible = self._combat_focus_eligible_ids()
        automatic_visible = visible_entity_ids
        if combat_eligible is not None:
            automatic_visible = tuple(
                value
                for value in combat_eligible
                if visible_entity_ids is None or value in visible_entity_ids
            )
        retained = None
        if self._retained_focus_id:
            retained = next(
                (
                    row
                    for row in focus_candidates(
                        self.registry,
                        player_position=self._last_player_position,
                        camera_forward=self._last_camera_forward,
                        visible_entity_ids=automatic_visible,
                        front_only=False,
                        maximum_distance=PIE_QE_HOSTILE_DISTANCE,
                    )
                    if row.entity_id == self._retained_focus_id
                    and row.center_distance
                    <= (
                        PIE_QE_HOSTILE_DISTANCE
                        if str(getattr(self._entity_by_id.get(row.entity_id), "faction", "") or "").lower()
                        == "hostile"
                        else PIE_QE_INTERACTABLE_DISTANCE
                    )
                ),
                None,
            )
            if retained is None:
                self._retained_focus_id = ""
        focus = retained or acquire_pie_focus(
            self.registry,
            player_position=self._last_player_position,
            camera_forward=self._last_camera_forward,
            prior_focus_id=prior_id,
            maximum_distance=PIE_QE_INTERACTABLE_DISTANCE,
            hostile_maximum_distance=PIE_QE_HOSTILE_DISTANCE,
            visible_entity_ids=automatic_visible,
        )
        if (focus.entity_id if focus is not None else "") != prior_id:
            self._emit(
                "focus_changed",
                f"Focused {focus.display_name}." if focus is not None else "Interaction focus cleared.",
                entity_id=focus.entity_id if focus is not None else "",
            )
        self._focus = focus
        return focus

    def _combat_focus_eligible_ids(self) -> tuple[str, ...] | None:
        if self._combat is None or not self._combat.active:
            return None
        return tuple(
            row.entity_id
            for row in self._combat.snapshot().combatants
            if row.relationship_to_player == "hostile" and row.alive
        )

    def cycle_focus(self, direction: int = 1) -> PIEFocusState | None:
        prior_id = self._focus.entity_id if self._focus is not None else ""
        eligible_ids = self._combat_focus_eligible_ids()
        self._focus = cycle_pie_focus(
            self.registry,
            player_position=self._last_player_position,
            camera_forward=self._last_camera_forward,
            current_focus_id=prior_id,
            direction=direction,
            visible_entity_ids=eligible_ids,
            maximum_distance=PIE_QE_INTERACTABLE_DISTANCE,
            hostile_maximum_distance=PIE_QE_HOSTILE_DISTANCE,
        )
        self._retained_focus_id = self._focus.entity_id if self._focus is not None else ""
        if self._focus is not None:
            self._emit("focus_changed", f"Focused {self._focus.display_name}.", entity_id=self._focus.entity_id)
        return self._focus

    def focus_entity(self, entity_id: str) -> PIEFocusState | None:
        """Focus one explicitly picked entity without activating its action.

        Mouse/world picking has already proved which rendered surface was in
        front, so it must not be re-ranked against a nearer automatic target.
        The exact target still obeys Odyssey's ordinary/hostile acquisition
        bands and the current combat target filter; action range remains the
        smaller value carried by :class:`PIEFocusState`.
        """

        wanted = str(entity_id or "").strip()
        entity = self._entity_by_id.get(wanted)
        if entity is None:
            return None
        eligible_ids = self._combat_focus_eligible_ids()
        if eligible_ids is not None and wanted not in eligible_ids:
            return None
        maximum_distance = (
            PIE_QE_HOSTILE_DISTANCE
            if str(getattr(entity, "faction", "") or "").strip().lower() == "hostile"
            else PIE_QE_INTERACTABLE_DISTANCE
        )
        candidates = focus_candidates(
            self.registry,
            player_position=self._last_player_position,
            camera_forward=self._last_camera_forward,
            maximum_distance=maximum_distance,
            visible_entity_ids=(wanted,),
            front_only=False,
        )
        selected = next((candidate for candidate in candidates if candidate.entity_id == wanted), None)
        if selected is None or selected.center_distance > maximum_distance + 1.0e-9:
            return None
        prior_id = self._focus.entity_id if self._focus is not None else ""
        self._focus = selected
        self._retained_focus_id = selected.entity_id
        if selected.entity_id != prior_id:
            self._emit("focus_changed", f"Focused {selected.display_name}.", entity_id=selected.entity_id)
        return self._focus

    def activate_focused(self, command: str | None = None) -> PIEInteractionResult:
        return self._record_result(self._router.route_focus(self._focus, command))

    def activate_entity(self, entity_id: str, command: str | None = None) -> PIEInteractionResult:
        focus = self.focus_entity(entity_id)
        return self._record_result(self._router.route_focus(focus, command))

    def continue_dialogue(self) -> MapStudioPIEDialogueSnapshot | None:
        if self._dialogue is None:
            return None
        snapshot = self._dialogue.continue_dialogue()
        self._capture_dialogue_events(snapshot)
        return snapshot

    def choose_dialogue(self, number: int) -> MapStudioPIEDialogueSnapshot | None:
        if self._dialogue is None:
            return None
        snapshot = self._dialogue.choose(number)
        self._capture_dialogue_events(snapshot)
        return snapshot

    def abort_dialogue(self) -> MapStudioPIEDialogueSnapshot | None:
        if self._dialogue is None:
            return None
        snapshot = self._dialogue.abort()
        self._capture_dialogue_events(snapshot)
        return snapshot

    def take_item(self, entity_id: str, resref: str, quantity: int = 1) -> PIEInteractionResult:
        return self._record_result(self._router.take(entity_id, resref, quantity))

    def take_all(self, entity_id: str) -> PIEInteractionResult:
        return self._record_result(self._router.take_all(entity_id))

    def close_modal(self) -> bool:
        if self._dialogue is not None and self._dialogue.active:
            self.abort_dialogue()
            return True
        if self._open_container_id:
            self._emit("container_closed", "Closed runtime-only container inventory.", entity_id=self._open_container_id)
            self._open_container_id = ""
            return True
        return False

    def toggle_combat_pause(self) -> MapStudioPIECombatSnapshot | None:
        if self._combat is None:
            self._emit("combat_pause_ignored", "No PIE combat encounter is active.")
            return None
        snapshot = self._combat.toggle_pause()
        self._capture_combat_events()
        return snapshot

    def clear_combat_queue(self) -> MapStudioPIECombatSnapshot | None:
        if self._combat is None:
            self._emit("combat_queue_clear_ignored", "No PIE combat encounter is active.")
            return None
        snapshot = self._combat.clear_player_actions()
        self._capture_combat_events()
        return snapshot

    def queue_attack(self, target_id: str) -> object:
        entity = self._entity_by_id.get(str(target_id or ""))
        if entity is None:
            raise KeyError(f"Unknown PIE combat target: {target_id!r}.")
        return self._record_result(self._router.route(entity.entity_id, ACTION_ATTACK))

    def advance(
        self,
        delta_time: float,
        *,
        player_position: Vec3,
        camera_forward: Vec3,
        player_facing_radians: float | None = None,
    ) -> MapStudioPIEGameplaySnapshot:
        if player_facing_radians is not None:
            self._last_player_facing_radians = float(player_facing_radians)
        self.update_focus(player_position, camera_forward)
        self._update_triggers()
        if self._combat is not None:
            self._combat.advance(max(0.0, float(delta_time)))
            self._capture_combat_events()
        return self.snapshot()

    def _update_triggers(self) -> None:
        """Emit enter/exit events as the player crosses authored trigger volumes.

        Transition triggers are reported, not warped (mirroring the inter-module
        door policy); OnEnter scripts are reported as deferred, never executed.
        """

        position = self._last_player_position
        for crossing in self._trigger_tracker.update(float(position[0]), float(position[1])):
            volume = crossing.volume
            label = volume.tag or volume.entity_id
            if crossing.kind == "exited":
                self._emit(
                    "trigger_exited",
                    f"Player left trigger {label}.",
                    entity_id=volume.entity_id,
                )
                continue
            if volume.is_transition:
                destination = "/".join(
                    part for part in (volume.transition_module, volume.transition_target) if part
                )
                self._emit(
                    "transition_trigger_entered",
                    f"Player entered transition trigger {label}; retail would warp to {destination or 'its linked area'}. "
                    "PIE reports cross-module transitions instead of loading another module.",
                    entity_id=volume.entity_id,
                    value=destination,
                )
                continue
            message = f"Player entered trigger {label}."
            applied, executed_scripts = self._execute_scripts_into_shared_state(
                (volume.on_enter_script,) if volume.on_enter_script else (),
                volume.entity_id,
                source_label="trigger OnEnter",
            )
            if executed_scripts:
                message += " Its OnEnter script executed: " + ", ".join(applied) + "."
                self._emit(
                    "trigger_script_executed",
                    "PIE executed the trigger OnEnter script's literal global/journal writes: "
                    + ", ".join(applied)
                    + ". Editor-side preview state, not campaign state.",
                    entity_id=volume.entity_id,
                    value=",".join(executed_scripts),
                )
            elif volume.has_scripts:
                message += " Its OnEnter script is reported as deferred; PIE executes no arbitrary NWScript."
            self._emit("trigger_entered", message, entity_id=volume.entity_id, value=volume.tag)

    def drain_events(self) -> tuple[MapStudioPIEGameplayEvent, ...]:
        events = tuple(self._events)
        self._events.clear()
        return events

    def journal_entries(self) -> tuple[MapStudioPIEQuestState, ...]:
        """Current runtime quest log (highest entry reached per plot)."""

        return self._journal.entries()

    def snapshot(self) -> MapStudioPIEGameplaySnapshot:
        dialogue = self._dialogue.snapshot() if self._dialogue is not None else None
        combat = self._combat.snapshot() if self._combat is not None else None
        dialogue_active = bool(dialogue is not None and not dialogue.ended and dialogue.state != "ready")
        combat_paused = bool(combat is not None and combat.active and combat.paused)
        player_dead = False
        if combat is not None:
            player = combat.combatant("pie:player")
            player_dead = bool(player is not None and not player.alive)
        if dialogue_active:
            mode = "dialogue"
        elif self._open_container_id:
            mode = "inventory"
        elif combat is not None and combat.active:
            mode = "combat_paused" if combat.paused else "combat"
        else:
            mode = "exploration"
        limitations = (
            "PIE executes no arbitrary NWScript; referenced scripts are reported as deferred.",
            "Player combat stats are an editor proxy until a player UTC/build contract is supplied.",
            "Feats, powers, equipment effects, AI, quests, globals, commerce, and loot generation remain outside this preview.",
            "Dialogue WaitFlags bits, LIP synchronization, layered Overlay playback, and unavailable camera-animation tracks remain approximations.",
            "Export and a manual KOTOR run remain the authoritative gameplay proof.",
        )
        return MapStudioPIEGameplaySnapshot(
            focus=self._focus,
            interaction=self._router.snapshot(),
            world_targets=self._world_targets,
            dialogue=dialogue,
            combat=combat,
            open_container_id=self._open_container_id,
            last_result=self._last_result,
            movement_locked=dialogue_active or bool(self._open_container_id) or combat_paused or player_dead,
            mode=mode,
            player_position=self._last_player_position,
            player_facing_radians=self._last_player_facing_radians,
            camera_forward=self._last_camera_forward,
            limitations=limitations,
            journal=self._journal.entries(),
            globals=self._global_state(),
        )

    def _global_state(self) -> tuple[MapStudioPIEGlobalValue, ...]:
        """Current global variables (sandbox + script-set) for a HUD/inspector."""

        evaluator = self._dialogue_condition_evaluator
        reader = getattr(evaluator, "global_state", None)
        if not callable(reader):
            return ()
        try:
            state = reader()
            numbers, booleans = state[0], state[1]
            strings = state[2] if len(state) > 2 else {}
        except Exception:
            return ()
        values = [
            MapStudioPIEGlobalValue(name=str(name), kind="number", value=int(value))
            for name, value in dict(numbers or {}).items()
        ]
        values.extend(
            MapStudioPIEGlobalValue(name=str(name), kind="boolean", value=bool(value))
            for name, value in dict(booleans or {}).items()
        )
        values.extend(
            MapStudioPIEGlobalValue(name=str(name), kind="string", value=str(value))
            for name, value in dict(strings or {}).items()
        )
        return tuple(sorted(values, key=lambda item: (item.kind, item.name)))

    def global_state(self) -> tuple[MapStudioPIEGlobalValue, ...]:
        """Public accessor for the current global variables."""

        return self._global_state()


__all__ = [
    "MapStudioPIEGameplayEvent",
    "MapStudioPIEGameplayRuntime",
    "MapStudioPIEGameplaySnapshot",
    "MapStudioPIEWorldTarget",
    "PIE_QE_HOSTILE_DISTANCE",
    "PIE_QE_INTERACTABLE_DISTANCE",
]
