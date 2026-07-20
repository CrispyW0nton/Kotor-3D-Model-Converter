"""Focused integration contracts for Map Studio PIE gameplay orchestration."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import math
from types import SimpleNamespace

import pytest


def _entity(entity_id: str, kind: str, position, **overrides):
    from src.core.modules.map_studio_pie_entities import PIEEntity

    values = {
        "entity_id": entity_id,
        "kind": kind,
        "tag": entity_id.rsplit(":", 1)[-1],
        "display_name": entity_id.rsplit(":", 1)[-1].replace("_", " ").title(),
        "template_resref": "",
        "position": position,
        "focusable": True,
        "interactive": True,
    }
    values.update(overrides)
    return PIEEntity(**values)


def _registry(*entities):
    from src.core.modules.map_studio_pie_entities import PIEEntityRegistry

    player = _entity(
        "pie:player",
        "player",
        (0.0, 0.0, 0.0),
        faction="player",
        focusable=False,
        interactive=False,
    )
    return PIEEntityRegistry((player,) + tuple(entities))


def _simple_dialogue_bytes() -> bytes:
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import Game
    from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink, DLGReply, bytes_dlg

    dialogue = DLG()
    greeting = DLGEntry()
    greeting.list_index = 0
    greeting.speaker = "OWNER"
    greeting.text = LocalizedString.from_english("Welcome to the preview.")
    ending = DLGReply()
    ending.list_index = 0
    ending.text = LocalizedString.from_english("")
    greeting.links.append(DLGLink(ending))
    dialogue.starters.append(DLGLink(greeting))
    with redirect_stdout(StringIO()):
        return bytes_dlg(dialogue, Game.K2)


def test_gameplay_snapshot_publishes_only_semantically_selectable_world_targets() -> None:
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    creature = _entity(
        "authored:creature:posed",
        "creature",
        (2.0, 3.0, 4.0),
        target_radius=0.65,
        metadata={"selection_height": 1.92},
    )
    future_click_trigger = _entity(
        "authored:trigger:clickable",
        "trigger",
        (5.0, 6.0, 7.0),
        focusable=True,
        interactive=False,
        target_radius=0.4,
    )
    automatic_trigger = _entity(
        "authored:trigger:automatic",
        "trigger",
        (8.0, 9.0, 10.0),
        focusable=False,
        interactive=False,
    )
    hidden_creature = _entity(
        "authored:creature:hidden",
        "creature",
        (11.0, 12.0, 13.0),
        metadata={"visible": False},
    )
    runtime = MapStudioPIEGameplayRuntime(
        _registry(creature, future_click_trigger, automatic_trigger, hidden_creature),
        game="K2",
    )

    targets = runtime.snapshot().world_targets
    assert tuple(row.entity_id for row in targets) == (
        creature.entity_id,
        future_click_trigger.entity_id,
    )
    assert targets[0].position == creature.position
    assert targets[0].target_radius == pytest.approx(0.65)
    assert targets[0].height == pytest.approx(1.92)
    assert targets[1].kind == "trigger"
    assert targets[1].height == pytest.approx(0.35)


def test_gameplay_focus_routes_real_dialogue_and_locks_locomotion() -> None:
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    civilian = _entity(
        "authored:creature:civ",
        "creature",
        (1.0, 0.0, 0.0),
        faction="friendly",
        interaction="dialogue",
        actions=("talk",),
        conversation="civ_dlg",
    )
    runtime = MapStudioPIEGameplayRuntime(
        _registry(civilian),
        game="K2",
        dialogue_loader=lambda resref: _simple_dialogue_bytes() if resref == "civ_dlg" else None,
    )

    exploration = runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
    assert exploration.focus is not None and exploration.focus.entity_id == civilian.entity_id
    assert runtime.activate_focused().executed
    listening = runtime.snapshot()
    assert listening.mode == "dialogue" and listening.movement_locked
    assert listening.dialogue is not None and listening.dialogue.text == "Welcome to the preview."

    ended = runtime.continue_dialogue()
    assert ended is not None and ended.ended
    assert runtime.snapshot().mode == "exploration"
    assert any(event.kind == "dialogue_conversation_ended" for event in runtime.drain_events())


def _compiled_setglobal(name: str, value: int) -> bytes:
    from pykotor.resource.formats.ncs import (
        NCS,
        NCSInstruction,
        NCSInstructionType as T,
        bytes_ncs,
    )

    ncs = NCS()
    ncs.instructions.append(NCSInstruction(T.CONSTS, [name]))
    ncs.instructions.append(NCSInstruction(T.CONSTI, [value]))
    ncs.instructions.append(NCSInstruction(T.ACTION, [581, 2]))  # SetGlobalNumber
    ncs.instructions.append(NCSInstruction(T.RETN))
    return bytes_ncs(ncs)


def test_using_placeable_executes_its_onused_global_write() -> None:
    from src.core.modules.map_studio_pie_dialogue import MapStudioPIEDialogueContextEvaluator
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    terminal = _entity(
        "authored:placeable:term",
        "placeable",
        (1.0, 0.0, 0.0),
        interaction="use",
        actions=("use",),
        metadata={"on_used": "k_term_used"},
    )
    evaluator = MapStudioPIEDialogueContextEvaluator()
    ncs = _compiled_setglobal("terminal_used", 1)
    runtime = MapStudioPIEGameplayRuntime(
        _registry(terminal),
        game="K2",
        dialogue_condition_evaluator=evaluator,
        script_loader=lambda resref: ncs if resref == "k_term_used" else None,
    )
    runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
    runtime.drain_events()

    result = runtime.activate_entity(terminal.entity_id, "use")
    assert result.deferred_scripts == ("k_term_used",)
    # The OnUsed script's literal global write folded into the shared state.
    assert evaluator._global_numbers["terminal_used"] == 1
    executed = [e for e in runtime.drain_events() if e.kind == "interaction_script_executed"]
    assert len(executed) == 1
    assert "terminal_used=1" in executed[0].message


def test_snapshot_exposes_live_global_state_including_script_writes() -> None:
    from src.core.modules.map_studio_pie_dialogue import MapStudioPIEDialogueContextEvaluator
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    # Evaluator pre-seeded (as OnEnter globals would be) with a number + boolean.
    evaluator = MapStudioPIEDialogueContextEvaluator(
        global_numbers={"200TEL_Falt_Arrest": 6},
        global_booleans={"207TEL_Destroy_Luxa": False},
    )
    terminal = _entity(
        "authored:placeable:term",
        "placeable",
        (1.0, 0.0, 0.0),
        interaction="use",
        actions=("use",),
        metadata={"on_used": "k_term_used"},
    )
    ncs = _compiled_setglobal("terminal_used", 1)
    runtime = MapStudioPIEGameplayRuntime(
        _registry(terminal),
        game="K2",
        dialogue_condition_evaluator=evaluator,
        script_loader=lambda resref: ncs if resref == "k_term_used" else None,
    )
    runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))

    before = {g.name: g.value for g in runtime.snapshot().globals}
    assert before["200tel_falt_arrest"] == 6          # seeded number (casefolded)
    assert before["207tel_destroy_luxa"] is False       # seeded boolean

    runtime.activate_entity(terminal.entity_id, "use")  # OnUsed sets terminal_used=1
    after = {g.name: g.value for g in runtime.snapshot().globals}
    assert after["terminal_used"] == 1                  # script write is now visible
    # Numbers and booleans are both surfaced with a kind tag.
    kinds = {g.name: g.kind for g in runtime.snapshot().globals}
    assert kinds["terminal_used"] == "number"
    assert kinds["207tel_destroy_luxa"] == "boolean"


def test_crossing_trigger_executes_its_onenter_global_write() -> None:
    from src.core.modules.map_studio_pie_dialogue import MapStudioPIEDialogueContextEvaluator
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    # A non-transition trigger whose OnEnter script sets a global.
    trigger = _entity(
        "authored:trigger:plot",
        "trigger",
        (0.0, 0.0, 0.0),
        interaction="trigger",
        geometry=((-2.0, -2.0, 0.0), (2.0, -2.0, 0.0), (2.0, 2.0, 0.0), (-2.0, 2.0, 0.0)),
        scripts=(("on_enter", "a_trig_set"),),
    )
    evaluator = MapStudioPIEDialogueContextEvaluator()
    ncs = _compiled_setglobal("207tel_plot_reached", 3)
    runtime = MapStudioPIEGameplayRuntime(
        _registry(trigger),
        game="K2",
        dialogue_condition_evaluator=evaluator,
        script_loader=lambda resref: ncs if resref == "a_trig_set" else None,
    )
    # Start outside the trigger, then step into it.
    runtime.advance(0.0, player_position=(100.0, 100.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
    runtime.drain_events()
    runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))

    assert evaluator._global_numbers["207tel_plot_reached"] == 3
    events = runtime.drain_events()
    assert any(e.kind == "trigger_script_executed" for e in events)
    # The trigger_entered message reflects execution, not the deferred fallback.
    entered = next(e for e in events if e.kind == "trigger_entered")
    assert "executed" in entered.message and "deferred" not in entered.message


def test_using_placeable_without_loader_does_not_execute() -> None:
    from src.core.modules.map_studio_pie_dialogue import MapStudioPIEDialogueContextEvaluator
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    terminal = _entity(
        "authored:placeable:term",
        "placeable",
        (1.0, 0.0, 0.0),
        interaction="use",
        actions=("use",),
        metadata={"on_used": "k_term_used"},
    )
    evaluator = MapStudioPIEDialogueContextEvaluator()
    runtime = MapStudioPIEGameplayRuntime(
        _registry(terminal),
        game="K2",
        dialogue_condition_evaluator=evaluator,
    )
    runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
    runtime.drain_events()

    runtime.activate_entity(terminal.entity_id, "use")
    assert not evaluator._global_numbers  # nothing executed without a loader
    assert not any(e.kind == "interaction_script_executed" for e in runtime.drain_events())


def test_gameplay_forwards_bounded_dialogue_condition_state() -> None:
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import Game, ResRef
    from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink, bytes_dlg

    from src.core.modules.map_studio_pie_dialogue import MapStudioPIEDialogueConditionTable
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    dialogue = DLG()
    unavailable = DLGEntry()
    unavailable.text = LocalizedString.from_english("Wrong branch")
    unavailable_link = DLGLink(unavailable)
    unavailable_link.active1 = ResRef("gate_false")
    available = DLGEntry()
    available.text = LocalizedString.from_english("Bounded state branch")
    available_link = DLGLink(available)
    available_link.active1 = ResRef("gate_true")
    dialogue.starters.extend((unavailable_link, available_link))
    with redirect_stdout(StringIO()):
        payload = bytes_dlg(dialogue, Game.K2)

    civilian = _entity(
        "authored:creature:conditional",
        "creature",
        (1.0, 0.0, 0.0),
        faction="friendly",
        interaction="dialogue",
        actions=("talk",),
        conversation="conditional_dlg",
    )
    runtime = MapStudioPIEGameplayRuntime(
        _registry(civilian),
        game="K2",
        dialogue_loader=lambda _resref: payload,
        dialogue_condition_evaluator=MapStudioPIEDialogueConditionTable(
            {"gate_false": False, "gate_true": True}
        ),
    )
    runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))

    assert runtime.activate_focused().executed
    snapshot = runtime.snapshot()
    assert snapshot.dialogue is not None
    assert snapshot.dialogue.text == "Bounded state branch"


def test_world_picked_207_falt_focus_is_separate_from_primary_activation() -> None:
    """A depth-proved world click selects first, then uses the retained target."""

    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    player_position = (7.79, -16.59, 10.20)
    nearer_door = _entity(
        "authored:door:nearby",
        "door",
        (8.35, -16.59, 10.20),
        interaction="door",
        actions=("open_door",),
    )
    czerka_officer = _entity(
        "authored:creature:n_czerkaoff002",
        "creature",
        (7.79, -15.30, 10.20),
        tag="207_Falt",
        display_name="Falt",
        faction="friendly",
        interaction="dialogue",
        actions=("talk",),
        conversation="207falt",
    )
    runtime = MapStudioPIEGameplayRuntime(
        _registry(nearer_door, czerka_officer),
        game="K2",
        dialogue_loader=lambda resref: _simple_dialogue_bytes() if resref == "207falt" else None,
    )
    automatic = runtime.advance(
        0.0,
        player_position=player_position,
        camera_forward=(1.0, 0.0, 0.0),
    )
    assert automatic.focus is not None and automatic.focus.entity_id == nearer_door.entity_id

    focused = runtime.focus_entity(czerka_officer.entity_id)
    assert focused is not None and focused.entity_id == czerka_officer.entity_id
    selected = runtime.snapshot()
    assert selected.last_result is None
    assert selected.dialogue is None
    assert nearer_door.entity_id not in selected.interaction.open_doors

    activated = runtime.activate_focused()
    assert activated.executed and activated.entity_id == czerka_officer.entity_id
    assert runtime.snapshot().mode == "dialogue"


def test_world_pick_focus_uses_retail_ten_and_thirty_meter_bands() -> None:
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    ordinary_beyond_legacy_eight = _entity(
        "authored:door:ordinary_9m",
        "door",
        (9.0, 0.0, 0.0),
        interaction="door",
    )
    ordinary_beyond_retail_ten = _entity(
        "authored:door:ordinary_10_2m",
        "door",
        (10.2, 0.0, 0.0),
        interaction="door",
    )
    hostile_beyond_ordinary_band = _entity(
        "authored:creature:hostile_20m",
        "creature",
        (20.0, 0.0, 0.0),
        faction="hostile",
        interaction="combat",
    )
    runtime = MapStudioPIEGameplayRuntime(
        _registry(
            ordinary_beyond_legacy_eight,
            ordinary_beyond_retail_ten,
            hostile_beyond_ordinary_band,
        ),
        game="K2",
    )
    runtime.advance(
        0.0,
        player_position=(0.0, 0.0, 0.0),
        camera_forward=(1.0, 0.0, 0.0),
    )

    assert runtime.focus_entity(ordinary_beyond_legacy_eight.entity_id).entity_id == ordinary_beyond_legacy_eight.entity_id
    assert runtime.focus_entity(ordinary_beyond_retail_ten.entity_id) is None
    assert runtime.focus_entity(hostile_beyond_ordinary_band.entity_id).entity_id == hostile_beyond_ordinary_band.entity_id


def test_gameplay_snapshot_exposes_live_player_transform_for_retail_minimap() -> None:
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    runtime = MapStudioPIEGameplayRuntime(_registry(), game="K2")
    snapshot = runtime.advance(
        0.0,
        player_position=(7.8, -13.35, 1.25),
        player_facing_radians=math.pi * 0.5,
        camera_forward=(0.0, 1.0, 0.0),
    )

    assert snapshot.player_position == pytest.approx((7.8, -13.35, 1.25))
    assert snapshot.player_facing_radians == pytest.approx(math.pi * 0.5)
    assert snapshot.camera_forward == pytest.approx((0.0, 1.0, 0.0))


def test_gameplay_container_transfer_unlocks_door_without_mutating_entities() -> None:
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    crate = _entity(
        "authored:placeable:crate",
        "placeable",
        (1.0, 0.0, 0.0),
        interaction="container",
        actions=("open_container",),
        has_inventory=True,
        inventory_items=({"resref": "airlock_key", "count": 1}, {"resref": "medpac", "count": 2}),
        metadata={"inventory_items": ({"resref": "airlock_key", "count": 1}, {"resref": "medpac", "count": 2})},
    )
    door = _entity(
        "authored:door:airlock",
        "door",
        (1.5, 0.0, 0.0),
        interaction="door",
        actions=("open_door",),
        locked=True,
        key_required="airlock_key",
    )
    registry = _registry(crate, door)
    runtime = MapStudioPIEGameplayRuntime(
        registry,
        game="K2",
        item_inspector=lambda resref: {"name": {"airlock_key": "Airlock Key", "medpac": "Advanced Medpac"}[resref]},
    )
    runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))

    opened = runtime.activate_entity(crate.entity_id)
    assert opened.executed and runtime.snapshot().mode == "inventory"
    assert runtime.take_all(crate.entity_id).executed
    assert runtime.router.has_key("AIRLOCK_KEY")
    assert runtime.router.container_inventory(crate.entity_id) == ()
    runtime.close_modal()
    unlocked = runtime.activate_entity(door.entity_id)
    assert unlocked.executed
    assert door.entity_id in runtime.snapshot().interaction.open_doors
    assert registry.by_id(door.entity_id).locked is True


def test_gameplay_combat_is_realtime_with_pause_and_emits_animation_roles() -> None:
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    hostile = _entity(
        "authored:creature:guard",
        "creature",
        (1.0, 0.0, 0.0),
        faction="hostile",
        interaction="combat",
        actions=("attack",),
        current_hp=18,
        max_hp=18,
        armor_class=12,
        attack_bonus=2,
        damage_min=2,
        damage_max=7,
        initiative_bonus=1,
    )
    runtime = MapStudioPIEGameplayRuntime(_registry(hostile), game="K2", combat_seed=7)
    runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))

    assert runtime.activate_focused().executed
    queued = runtime.snapshot()
    assert queued.mode == "combat" and queued.combat is not None
    assert len(queued.combat.queued_actions) == 1
    runtime.clear_combat_queue()
    assert runtime.snapshot().combat.queued_actions == ()
    runtime.queue_attack(hostile.entity_id)
    runtime.toggle_combat_pause()
    paused = runtime.snapshot()
    assert paused.mode == "combat_paused" and paused.movement_locked
    before = paused.combat.simulation_time
    runtime.advance(9.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
    assert runtime.snapshot().combat.simulation_time == before
    runtime.toggle_combat_pause()
    runtime.advance(3.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))

    events = runtime.drain_events()
    assert any(event.kind == "combat_round_started" for event in events)
    assert any(event.animation_role in {"ready", "attack", "damage", "death"} for event in events)


def test_configured_player_build_replaces_the_combat_proxy() -> None:
    from src.core.modules.map_studio_pie_combat import (
        MapStudioPIECombatStats,
        MapStudioPIEDamageDice,
    )
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    hostile = _entity(
        "authored:creature:guard",
        "creature",
        (1.0, 0.0, 0.0),
        faction="hostile",
        interaction="combat",
        actions=("attack",),
        current_hp=20,
        max_hp=20,
        armor_class=12,
        attack_bonus=2,
        damage_min=2,
        damage_max=7,
    )
    build_stats = MapStudioPIECombatStats(
        max_hp=99,
        current_hp=99,
        armor_class=25,
        attack_bonus=15,
        damage=MapStudioPIEDamageDice(2, 8, 4),
        initiative_bonus=9,
    )
    runtime = MapStudioPIEGameplayRuntime(
        _registry(hostile), game="K2", combat_seed=3, player_combat_stats=build_stats
    )
    runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
    assert runtime.activate_focused().executed  # opens combat

    player = runtime.snapshot().combat.combatant("pie:player")
    assert player is not None
    # The resolved build stats replace the fixed editor proxy (24 HP / AC 14).
    assert player.max_hp == 99
    assert player.armor_class == 25


def _oneliner_dlg_with_unprovable_starter() -> bytes:
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import Game, ResRef
    from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink, bytes_dlg

    dlg = DLG()
    entry = DLGEntry()
    entry.list_index = 0
    entry.text = LocalizedString.from_english("Move along, citizen.")
    link = DLGLink(entry)
    link.active1 = ResRef("c_unprovable_bark")  # arbitrary condition PIE can't evaluate
    dlg.starters.append(link)
    with redirect_stdout(StringIO()):
        return bytes_dlg(dlg, Game.K2)


def test_side_npc_oneliner_shows_via_preview_assumption_when_starter_unprovable() -> None:
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    commoner = _entity(
        "authored:creature:commoner",
        "creature",
        (1.0, 0.0, 0.0),
        faction="friendly",
        interaction="dialogue",
        actions=("talk",),
        conversation="200comm",
    )
    dlg = _oneliner_dlg_with_unprovable_starter()
    runtime = MapStudioPIEGameplayRuntime(
        _registry(commoner), game="K2",
        dialogue_loader=lambda resref: dlg if resref == "200comm" else None,
    )
    runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))

    result = runtime.activate_entity(commoner.entity_id, "talk")
    assert result.executed  # previously this raised/blocked → no dialogue
    snapshot = runtime.snapshot()
    assert snapshot.mode == "dialogue"
    assert snapshot.dialogue is not None and snapshot.dialogue.text == "Move along, citizen."
    assert any(e.kind == "dialogue_starter_assumed" for e in runtime.drain_events())


def test_party_companion_joins_combat_as_assisting_ally() -> None:
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    hostile = _entity(
        "authored:creature:guard",
        "creature",
        (1.0, 0.0, 0.0),
        faction="hostile",
        interaction="combat",
        actions=("attack",),
        current_hp=30,
        max_hp=30,
        armor_class=10,
        attack_bonus=1,
        damage_min=1,
        damage_max=3,
    )
    party = [
        {
            "entity_id": "pie:party:0",
            "display_name": "Atton Rand",
            "max_hp": 40,
            "current_hp": 40,
            "armor_class": 16,
            "attack_bonus": 6,
            "damage_min": 3,
            "damage_max": 12,
        }
    ]
    runtime = MapStudioPIEGameplayRuntime(
        _registry(hostile), game="K2", combat_seed=7, party_combatants=party
    )
    runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))

    assert runtime.activate_focused().executed  # opens combat on the hostile
    combat = runtime.snapshot().combat
    assert combat is not None
    companion = combat.combatant("pie:party:0")
    assert companion is not None
    assert companion.relationship_to_player == "friendly"
    assert companion.max_hp == 40

    # The companion auto-engages as an assisting ally when combat opens.
    events = runtime.drain_events()
    assert any(
        e.kind == "combat_ally_engaged" and e.entity_id == "pie:party:0" for e in events
    )
    # Advancing rounds, the companion lands basic attacks on the hostile.
    runtime.advance(6.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
    events = runtime.drain_events()
    assert any(
        e.kind in {"combat_attack_hit", "combat_attack_missed"} and e.entity_id == "pie:party:0"
        for e in events
    )


def test_combat_qe_focus_cycle_filters_to_live_hostiles_and_uses_left_right() -> None:
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    friendly = _entity(
        "authored:creature:friendly",
        "creature",
        (0.0, 1.0, 0.0),
        faction="friendly",
        interaction="dialogue",
        conversation="friendly_dlg",
    )
    front = _entity(
        "authored:creature:front",
        "creature",
        (1.0, 0.0, 0.0),
        faction="hostile",
        interaction="combat",
        current_hp=8,
        max_hp=8,
    )
    left = _entity(
        "authored:creature:left",
        "creature",
        (0.0, 2.0, 0.0),
        faction="hostile",
        interaction="combat",
        current_hp=8,
        max_hp=8,
    )
    right = _entity(
        "authored:creature:right",
        "creature",
        (0.0, -2.0, 0.0),
        faction="hostile",
        interaction="combat",
        current_hp=8,
        max_hp=8,
    )
    runtime = MapStudioPIEGameplayRuntime(_registry(friendly, front, left, right), game="K2")
    runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
    assert runtime.focus.entity_id == front.entity_id
    assert runtime.activate_focused("attack").executed

    assert runtime.cycle_focus(-1).entity_id == left.entity_id
    runtime.advance(0.1, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
    assert runtime.focus.entity_id == left.entity_id
    assert runtime.cycle_focus(1).entity_id == front.entity_id
    assert runtime.cycle_focus(1).entity_id == right.entity_id
    assert runtime.focus.entity_id != friendly.entity_id


def test_exploration_qe_retains_distant_target_without_expanding_action_range() -> None:
    from src.core.modules.map_studio_pie_gameplay import (
        PIE_QE_HOSTILE_DISTANCE,
        PIE_QE_INTERACTABLE_DISTANCE,
        MapStudioPIEGameplayRuntime,
    )

    near = _entity(
        "authored:creature:near",
        "creature",
        (2.0, 0.0, 0.0),
        interaction="dialogue",
        conversation="near_dlg",
        current_hp=11,
        max_hp=20,
    )
    distant = _entity(
        "authored:creature:distant",
        "creature",
        (0.0, 24.0, 0.0),
        faction="hostile",
        interaction="dialogue",
        conversation="distant_dlg",
        current_hp=7,
        max_hp=9,
    )
    runtime = MapStudioPIEGameplayRuntime(_registry(near, distant), game="K2")
    runtime.advance(0.0, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
    assert PIE_QE_INTERACTABLE_DISTANCE == 10.0
    assert PIE_QE_HOSTILE_DISTANCE == 30.0
    selected = runtime.cycle_focus(-1)
    assert selected is not None and selected.entity_id == distant.entity_id
    assert not selected.in_range
    assert selected.current_hp == 7 and selected.max_hp == 9
    assert selected.camera_side_alignment > 0.0
    retained = runtime.advance(
        0.1,
        player_position=(0.0, 0.0, 0.0),
        camera_forward=(1.0, 0.0, 0.0),
    ).focus
    assert retained is not None and retained.entity_id == distant.entity_id
    assert not runtime.activate_focused().executed

    ordinary_too_far = _entity(
        "authored:creature:ordinary_too_far",
        "creature",
        (0.0, -12.0, 0.0),
        faction="neutral",
        interaction="dialogue",
        conversation="ordinary_dlg",
    )
    ordinary_runtime = MapStudioPIEGameplayRuntime(
        _registry(near, ordinary_too_far),
        game="K2",
    )
    ordinary_runtime.advance(
        0.0,
        player_position=(0.0, 0.0, 0.0),
        camera_forward=(1.0, 0.0, 0.0),
    )
    assert ordinary_runtime.cycle_focus(1).entity_id == near.entity_id


def test_map_session_frame_carries_gameplay_and_focus_overlay() -> None:
    from src.core.modules.map_studio_pie import MapStudioPIESession

    wok = SimpleNamespace(
        verts=[(0.0, -2.0, 0.0), (6.0, -2.0, 0.0), (6.0, 2.0, 0.0), (0.0, 2.0, 0.0)],
        faces=[
            SimpleNamespace(v1=0, v2=1, v3=2, surface=4, adj1=-1, adj2=-1, adj3=-1),
            SimpleNamespace(v1=0, v2=2, v3=3, surface=4, adj1=-1, adj2=-1, adj3=-1),
        ],
    )
    terminal = _entity(
        "authored:placeable:terminal",
        "placeable",
        (2.0, 0.0, 0.0),
        interaction="use",
        actions=("use_placeable",),
        metadata={"useable": True},
    )
    session = MapStudioPIESession(wok, game="K2", spawn_position=(1.0, 0.0, 0.0))
    session.configure_gameplay(_registry(terminal))
    session.set_camera_azimuth(180.0)
    frame = session.advance(1.0 / 60.0)

    assert frame.gameplay is not None and frame.gameplay.focus.entity_id == terminal.entity_id
    overlay = session.overlay_geometry()
    assert overlay.marker_count == 2
    assert any(row.role == "pie_focus" for row in overlay.footprints)
