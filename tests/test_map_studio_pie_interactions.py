"""Focused proof for standalone Map Studio PIE focus/interaction state."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def _entity(
    entity_id: str,
    kind: str,
    *,
    position=(0.0, 0.0, 0.0),
    radius=0.5,
    faction="neutral",
    interaction="none",
    interactive=True,
    locked=False,
    key_required="",
    conversation="",
    has_inventory=False,
    metadata=None,
):
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_entities import PIEEntity

    return PIEEntity(
        entity_id=entity_id,
        kind=kind,
        tag=entity_id.rsplit(":", 1)[-1],
        display_name=entity_id.rsplit(":", 1)[-1].replace("_", " ").title(),
        template_resref=entity_id.rsplit(":", 1)[-1],
        position=position,
        faction=faction,
        interactive=interactive,
        interaction=interaction,
        locked=locked,
        key_required=key_required,
        conversation=conversation,
        has_inventory=has_inventory,
        target_radius=radius,
        metadata=dict(metadata or {}),
    )


def test_ordered_actions_preserve_all_entity_capabilities() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_interactions import ordered_actions_for_entity

    hostile = _entity(
        "authored:creature:guard",
        "creature",
        faction="hostile",
        interaction="combat",
        conversation="guard_dlg",
        metadata={"on_dialog": "k_guard_dialog"},
    )
    assert [action.command for action in ordered_actions_for_entity(hostile)] == ["attack", "talk"]
    assert ordered_actions_for_entity(hostile)[1].script_resref == "k_guard_dialog"

    friendly = _entity(
        "authored:creature:civilian",
        "creature",
        faction="friendly",
        interaction="dialogue",
        conversation="civilian_dlg",
    )
    assert [action.command for action in ordered_actions_for_entity(friendly)] == ["talk"]

    door = _entity(
        "authored:door:airlock",
        "door",
        interaction="door",
        metadata={"scripts": {"on_click": "k_airlock_click"}},
    )
    assert [action.command for action in ordered_actions_for_entity(door)] == ["door"]
    assert ordered_actions_for_entity(door)[0].script_resref == "k_airlock_click"

    multipurpose = _entity(
        "authored:placeable:console_crate",
        "placeable",
        interaction="container",
        has_inventory=True,
        conversation="console_dlg",
        metadata={"on_open": "k_crate_open", "on_used": "k_console_used"},
    )
    actions = ordered_actions_for_entity(multipurpose)
    assert [action.command for action in actions] == ["container", "terminal", "use"]
    assert [action.script_resref for action in actions] == ["k_crate_open", "k_console_used", "k_console_used"]

    store = _entity("authored:store:merchant", "store", interactive=False, metadata={"on_open_store": "k_shop"})
    store_action = ordered_actions_for_entity(store)[0]
    assert store_action.command == "store"
    assert not store_action.supported
    assert store_action.script_resref == "k_shop"


def test_focus_uses_front_half_space_footprint_distance_and_prior_hysteresis() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_interactions import acquire_pie_focus, focus_candidates

    prior = _entity("authored:door:prior", "door", position=(2.50, 0.0, 0.0), radius=0.50, interaction="door")
    slightly_better = _entity(
        "authored:door:better",
        "door",
        position=(2.42, 0.20, 0.0),
        radius=0.50,
        interaction="door",
    )
    large_footprint = _entity(
        "authored:placeable:large",
        "placeable",
        position=(3.0, 0.0, 0.0),
        radius=1.10,
        interaction="use",
    )
    behind = _entity("authored:door:behind", "door", position=(-0.5, 0.0, 0.0), radius=0.25, interaction="door")

    rows = focus_candidates(
        (prior, slightly_better, large_footprint, behind),
        player_position=(0.0, 0.0, 0.0),
        camera_forward=(1.0, 0.0, 0.0),
    )
    assert rows[0].entity_id == "authored:placeable:large"
    assert rows[0].center_distance == pytest.approx(3.0)
    assert rows[0].interaction_distance == pytest.approx(1.9)
    assert rows[0].in_range
    assert "authored:door:behind" not in {row.entity_id for row in rows}

    # Remove the large target: the slightly closer footprint wins normally,
    # but a still-valid prior focus is retained inside the explicit margin.
    focused = acquire_pie_focus(
        (prior, slightly_better),
        player_position=(0.0, 0.0, 0.0),
        camera_forward=(1.0, 0.0, 0.0),
        prior_focus_id=prior.entity_id,
        hysteresis=0.15,
    )
    assert focused is not None and focused.entity_id == prior.entity_id
    focused_without_margin = acquire_pie_focus(
        (prior, slightly_better),
        player_position=(0.0, 0.0, 0.0),
        camera_forward=(1.0, 0.0, 0.0),
        prior_focus_id=prior.entity_id,
        hysteresis=0.01,
    )
    assert focused_without_margin is not None and focused_without_margin.entity_id == slightly_better.entity_id

    visible_only = acquire_pie_focus(
        (prior, slightly_better),
        player_position=(0.0, 0.0, 0.0),
        camera_forward=(1.0, 0.0, 0.0),
        visible_entity_ids=(prior.entity_id,),
    )
    assert visible_only is not None and visible_only.entity_id == prior.entity_id


def test_focus_cycle_is_stable_bidirectional_and_wraps() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_interactions import cycle_pie_focus, focus_candidates

    entities = (
        _entity("authored:door:front", "door", position=(1.5, 0.0, 0.0), interaction="door"),
        _entity("authored:door:left", "door", position=(0.0, 2.0, 0.0), interaction="door"),
        _entity("authored:door:right", "door", position=(0.0, -2.0, 0.0), interaction="door"),
        _entity("authored:door:back", "door", position=(-2.5, 0.0, 0.0), interaction="door"),
    )
    rows = focus_candidates(entities, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
    assert [row.entity_id for row in rows] == [entities[0].entity_id]
    assert [row.cycle_index for row in rows] == [0]
    # Q selects camera-relative left; E selects right, independent of source
    # insertion order and while retaining the current eligible target.
    assert cycle_pie_focus(
        entities,
        player_position=(0.0, 0.0, 0.0),
        camera_forward=(1.0, 0.0, 0.0),
        current_focus_id=entities[0].entity_id,
        direction=-1,
    ).entity_id == entities[1].entity_id
    assert cycle_pie_focus(
        entities,
        player_position=(0.0, 0.0, 0.0),
        camera_forward=(1.0, 0.0, 0.0),
        current_focus_id=entities[0].entity_id,
        direction=1,
    ).entity_id == entities[2].entity_id
    assert cycle_pie_focus(
        entities,
        player_position=(0.0, 0.0, 0.0),
        camera_forward=(1.0, 0.0, 0.0),
        current_focus_id=entities[3].entity_id,
        direction=-1,
    ).entity_id == entities[2].entity_id
    assert cycle_pie_focus(
        entities,
        player_position=(0.0, 0.0, 0.0),
        camera_forward=(1.0, 0.0, 0.0),
        current_focus_id="",
        direction=1,
    ).entity_id == entities[0].entity_id


def test_focus_uses_retail_ordinary_and_hostile_distance_bands() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_interactions import acquire_pie_focus, cycle_pie_focus

    ordinary_near = _entity(
        "authored:door:ordinary_near",
        "door",
        position=(9.0, 0.0, 0.0),
        radius=0.0,
        interaction="door",
    )
    ordinary_far = _entity(
        "authored:door:ordinary_far",
        "door",
        position=(11.0, 1.0, 0.0),
        radius=0.0,
        interaction="door",
    )
    hostile_far = _entity(
        "authored:creature:hostile_far",
        "creature",
        position=(20.0, -1.0, 0.0),
        radius=0.0,
        faction="hostile",
        interaction="combat",
    )
    hostile_too_far = _entity(
        "authored:creature:hostile_too_far",
        "creature",
        position=(31.0, 0.0, 0.0),
        radius=0.0,
        faction="hostile",
        interaction="combat",
    )
    entities = (ordinary_near, ordinary_far, hostile_far, hostile_too_far)

    acquired = acquire_pie_focus(
        entities,
        player_position=(0.0, 0.0, 0.0),
        camera_forward=(1.0, 0.0, 0.0),
        maximum_distance=10.0,
        hostile_maximum_distance=30.0,
    )
    assert acquired is not None and acquired.entity_id == ordinary_near.entity_id
    hostile_acquired = acquire_pie_focus(
        (hostile_far, hostile_too_far),
        player_position=(0.0, 0.0, 0.0),
        camera_forward=(1.0, 0.0, 0.0),
        maximum_distance=10.0,
        hostile_maximum_distance=30.0,
    )
    assert hostile_acquired is not None and hostile_acquired.entity_id == hostile_far.entity_id
    cycled = cycle_pie_focus(
        entities,
        player_position=(0.0, 0.0, 0.0),
        camera_forward=(1.0, 0.0, 0.0),
        current_focus_id=ordinary_near.entity_id,
        direction=1,
        maximum_distance=10.0,
        hostile_maximum_distance=30.0,
    )
    assert cycled is not None and cycled.entity_id == hostile_far.entity_id

    with pytest.raises(ValueError, match="finite non-negative"):
        acquire_pie_focus(
            entities,
            player_position=(0.0, 0.0, 0.0),
            camera_forward=(1.0, 0.0, 0.0),
            maximum_distance=float("nan"),
            hostile_maximum_distance=30.0,
        )


def test_router_key_checks_unlock_and_open_without_consuming_key() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_interactions import PIEInteractionRouter

    door = _entity(
        "authored:door:locked",
        "door",
        interaction="door",
        locked=True,
        key_required="airlock_key",
    )
    blocked = PIEInteractionRouter((door,)).route(door.entity_id)
    assert blocked.status == "blocked"
    assert "airlock_key" in blocked.message
    assert blocked.snapshot.open_doors == ()

    router = PIEInteractionRouter((door,), player_inventory=({"resref": "AIRLOCK_KEY", "quantity": 1},))
    opened = router.route(door.entity_id, "open_door")
    assert opened.status == "executed"
    assert opened.command == "door"
    assert opened.snapshot.open_doors == (door.entity_id,)
    assert opened.snapshot.unlocked_entities == (door.entity_id,)
    assert router.player_inventory[0].quantity == 1
    repeated = router.route(door.entity_id, "door")
    assert repeated.status == "executed" and "already open" in repeated.message


def test_container_take_and_take_all_are_runtime_only_and_stack_items() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_interactions import PIEInteractionRouter

    authored_inventory = [
        {"resref": "medpac", "quantity": 3, "display_name": "Medpac"},
        {"resref": "MEDPAC", "quantity": 1, "display_name": "Medpac"},
        ("parts", 2, "Components"),
    ]
    container = _entity(
        "authored:placeable:footlocker",
        "placeable",
        interaction="container",
        has_inventory=True,
        metadata={"inventory": authored_inventory, "on_inventory": "k_loot_changed"},
    )
    original_metadata = [dict(authored_inventory[0]), dict(authored_inventory[1]), authored_inventory[2]]
    router = PIEInteractionRouter((container,))

    opened = router.route(container.entity_id, "container")
    assert opened.status == "executed"
    assert [(item.resref.casefold(), item.quantity) for item in opened.items] == [("medpac", 4), ("parts", 2)]

    partial = router.take(container.entity_id, "MEDPAC", 2)
    assert partial.status == "executed"
    assert partial.items[0].quantity == 2
    assert partial.deferred_scripts == ("k_loot_changed",)
    assert [(item.resref.casefold(), item.quantity) for item in router.container_inventory(container.entity_id)] == [
        ("medpac", 2),
        ("parts", 2),
    ]

    all_items = router.take_all(container.entity_id)
    assert all_items.status == "executed"
    assert router.container_inventory(container.entity_id) == ()
    assert [(item.resref.casefold(), item.quantity) for item in router.player_inventory] == [
        ("medpac", 4),
        ("parts", 2),
    ]
    assert authored_inventory == original_metadata
    assert container.metadata["inventory"] is authored_inventory


def test_dialogue_and_combat_are_deferred_without_callbacks_and_injected_when_supplied() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_interactions import PIEInteractionRouter

    talker = _entity(
        "authored:creature:talker",
        "creature",
        faction="friendly",
        interaction="dialogue",
        conversation="talker_dlg",
    )
    hostile = _entity(
        "authored:creature:hostile",
        "creature",
        faction="hostile",
        interaction="combat",
    )
    headless = PIEInteractionRouter((talker, hostile))
    assert headless.route(talker.entity_id, "talk").status == "deferred"
    assert headless.route(hostile.entity_id, "attack").status == "deferred"

    calls: list[tuple[str, str]] = []
    injected = PIEInteractionRouter(
        (talker, hostile),
        dialogue_callback=lambda entity, action: calls.append((entity.entity_id, action.command)) or "Dialogue preview opened.",
        combat_callback=lambda entity, action: calls.append((entity.entity_id, action.command)) or True,
    )
    talk = injected.route(talker.entity_id, "talk")
    attack = injected.route(hostile.entity_id, "attack")
    assert talk.status == "executed" and talk.message == "Dialogue preview opened."
    assert attack.status == "executed"
    assert calls == [(talker.entity_id, "talk"), (hostile.entity_id, "attack")]


def test_terminal_use_store_and_ncs_report_deferred_instead_of_faking_execution() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_interactions import PIEInteractionRouter

    terminal = _entity(
        "authored:placeable:terminal",
        "placeable",
        interaction="terminal",
        conversation="terminal_dlg",
        metadata={"on_used": "k_terminal_used"},
    )
    scripted = _entity(
        "authored:placeable:scripted",
        "placeable",
        interaction="use",
        metadata={"on_used": "k_scripted_use"},
    )
    inert = _entity("authored:placeable:inert", "placeable", interaction="use")
    store = _entity(
        "authored:store:shop",
        "store",
        interactive=False,
        metadata={"on_open_store": "k_store_open"},
    )
    router = PIEInteractionRouter((terminal, scripted, inert, store))

    terminal_result = router.route(terminal.entity_id, "terminal")
    assert terminal_result.status == "deferred"
    assert terminal_result.deferred_scripts == ("k_terminal_used",)
    scripted_result = router.route(scripted.entity_id, "use")
    assert scripted_result.status == "deferred"
    assert scripted_result.deferred_scripts == ("k_scripted_use",)
    assert "not executed" in " ".join(scripted_result.coverage_warnings)
    assert router.route(inert.entity_id, "use").status == "unsupported"
    store_result = router.route(store.entity_id, "store")
    assert store_result.status == "deferred"
    assert store_result.deferred_scripts == ("k_store_open",)


def test_route_focus_enforces_range_and_public_snapshots_are_immutable() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_interactions import (
        PIEActionSpec,
        PIEInteractionRouter,
        acquire_pie_focus,
    )

    door = _entity("authored:door:far", "door", position=(5.0, 0.0, 0.0), radius=0.5, interaction="door")
    focus = acquire_pie_focus(
        (door,),
        player_position=(0.0, 0.0, 0.0),
        camera_forward=(1.0, 0.0, 0.0),
    )
    assert focus is not None and not focus.in_range
    result = PIEInteractionRouter((door,)).route_focus(focus)
    assert result.status == "blocked"
    assert result.snapshot.open_doors == ()

    with pytest.raises(FrozenInstanceError):
        result.snapshot.open_doors = (door.entity_id,)  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        PIEActionSpec("talk", "Talk").label = "Changed"  # type: ignore[misc]


def test_interaction_module_mirrors_are_byte_identical() -> None:
    root = (ROOT / "src/core/modules/map_studio_pie_interactions.py").read_bytes()
    scene = (
        ROOT / "native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_pie_interactions.py"
    ).read_bytes()
    tools = (
        ROOT / "native/GhostRigger.Core.Tools/Python/src/core/modules/map_studio_pie_interactions.py"
    ).read_bytes()
    assert scene == root
    assert tools == root
