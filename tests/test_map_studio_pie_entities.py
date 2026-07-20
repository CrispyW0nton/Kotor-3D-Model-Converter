"""Focused proof: PIE builds a deterministic, honest entity registry.

The registry is derived from the same authored placement instances the GIT
compiler consumes, so entity ids match Map Studio selection ids. Unsupported
simulation surfaces (stores, encounters, unknown factions, scripted OnUsed)
must surface as coverage warnings rather than silent guesses.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def _project() -> SimpleNamespace:
    placements = SimpleNamespace(
        entry_point=SimpleNamespace(position=(1.0, 2.0, 0.0), facing=1.57),
        creatures=(
            SimpleNamespace(template_resref="c_enemy", tag="guard", position=(4.0, 0.0, 0.0), bearing=0.5, instance_id="i_guard"),
            SimpleNamespace(template_resref="n_civ", tag="civ", position=(6.0, 0.0, 0.0), bearing=0.0, instance_id="i_civ"),
        ),
        doors=(
            SimpleNamespace(
                template_resref="door_a", tag="exit_door", position=(8.0, 0.0, 0.0), bearing=0.0,
                linked_to="dest_wp", linked_to_module="plcab", linked_to_flags=2,
                transition_destination=-1, instance_id="i_door",
            ),
        ),
        placeables=(
            SimpleNamespace(template_resref="footlker", tag="crate", position=(2.0, 2.0, 0.0), bearing=0.0, instance_id="i_crate"),
            SimpleNamespace(template_resref="comppnl", tag="terminal", position=(3.0, 2.0, 0.0), bearing=0.0, instance_id="i_term"),
        ),
        triggers=(
            SimpleNamespace(
                template_resref="trg_a", tag="tripwire", position=(5.0, 5.0, 0.0),
                geometry=((4.0, 4.0, 0.0), (6.0, 4.0, 0.0), (6.0, 6.0, 0.0), (4.0, 6.0, 0.0)),
                linked_to="", linked_to_module="", linked_to_flags=0,
                transition_destination=-1, instance_id="i_trig",
            ),
        ),
        waypoints=(SimpleNamespace(template_resref="wp", tag="start", position=(1.0, 1.0, 0.0), bearing=0.0, instance_id="i_wp"),),
        sounds=(SimpleNamespace(template_resref="snd", tag="hum", position=(0.0, 0.0, 1.0), instance_id="i_snd"),),
        cameras=(SimpleNamespace(tag="", position=(0.0, 0.0, 3.0), camera_id=7, instance_id="i_cam"),),
        stores=(SimpleNamespace(template_resref="stm_shop", tag="shop", position=(9.0, 0.0, 0.0), bearing=0.0, instance_id="i_shop"),),
        encounters=(SimpleNamespace(template_resref="enc", tag="amb", instance_id="i_enc"),),
        metadata={
            "creature_behaviors": {
                "authored:creature:i_guard": {"faction_role": "hostile", "conversation_resref": "", "movement_mode": "stationary"},
                "authored:creature:i_civ": {"faction_role": "friendly", "conversation_resref": "civ_talk", "movement_mode": "free_roam"},
            },
        },
    )
    return SimpleNamespace(placements=placements)


def _inspector(kind: str, resref: str):
    return {
        ("placeable", "footlker"): {"has_inventory": True, "name": "Footlocker", "locked": True, "key_required": "key_a"},
        ("placeable", "comppnl"): {"conversation": "term_dlg", "name": "Computer Panel"},
        ("door", "door_a"): {"locked": False, "name": "Airlock"},
        ("creature", "c_enemy"): {"name": "Czerka Guard"},
        ("creature", "n_civ"): {"name": "Civilian"},
    }.get((kind, resref), {})


def test_registry_is_deterministic_and_id_stable() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_entities import build_pie_entity_registry

    first = build_pie_entity_registry(_project(), template_inspector=_inspector)
    second = build_pie_entity_registry(_project(), template_inspector=_inspector)
    assert [e.entity_id for e in first.entities] == [e.entity_id for e in second.entities]
    ids = [e.entity_id for e in first.entities]
    assert ids[0] == "pie:player"
    assert "authored:creature:i_guard" in ids
    assert "authored:door:i_door" in ids
    assert "authored:trigger:i_trig" in ids
    # Kind-major deterministic ordering.
    kinds = [e.kind for e in first.entities]
    assert kinds == sorted(kinds, key=lambda k: (
        ["player", "creature", "door", "placeable", "trigger", "waypoint", "sound", "camera", "store"].index(k)
    ))


def test_registry_classifies_factions_and_interactions() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_entities import build_pie_entity_registry

    registry = build_pie_entity_registry(_project(), template_inspector=_inspector)
    guard = registry.by_id("authored:creature:i_guard")
    assert guard.faction == "hostile" and guard.interaction == "combat" and guard.interactive
    assert guard.display_name == "Czerka Guard"
    civ = registry.by_id("authored:creature:i_civ")
    assert civ.faction == "friendly" and civ.interaction == "dialogue"
    assert civ.conversation == "civ_talk" and civ.movement_mode == "free_roam"
    crate = registry.by_id("authored:placeable:i_crate")
    assert crate.interaction == "container" and crate.has_inventory
    assert crate.locked and crate.key_required == "key_a"
    terminal = registry.by_id("authored:placeable:i_term")
    assert terminal.interaction == "terminal" and terminal.conversation == "term_dlg"
    door = registry.by_id("authored:door:i_door")
    assert door.interaction == "door" and not door.locked
    assert door.transition_module == "plcab" and door.transition_target == "dest_wp"
    trigger = registry.by_id("authored:trigger:i_trig")
    assert trigger.interaction == "trigger" and len(trigger.geometry) == 4 and not trigger.interactive
    player = registry.by_id("pie:player")
    assert player.faction == "player" and abs(player.facing - 1.57) < 1e-9
    camera = registry.of_kind("camera")[0]
    assert camera.metadata["camera_id"] == 7
    assert camera.metadata["field_of_view"] == 45.0
    assert camera.metadata["orientation"] == (0.0, 0.0, 0.0, 1.0)
    # Only genuinely actionable entities are targetable.
    interactive_ids = {e.entity_id for e in registry.interactive_entities}
    assert "authored:store:i_shop" not in interactive_ids
    assert "authored:waypoint:i_wp" not in interactive_ids


def test_registry_reports_unsupported_coverage_honestly() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_entities import build_pie_entity_registry

    registry = build_pie_entity_registry(_project(), template_inspector=_inspector)
    text = " ".join(registry.coverage_warnings)
    assert "does not simulate commerce" in text
    assert "encounter placement(s) are not simulated" in text

    # Without an inspector, unknown factions degrade to neutral WITH a warning.
    bare = build_pie_entity_registry(_project())
    civ = bare.by_id("authored:creature:i_civ")
    assert civ.faction == "friendly"  # authored behavior intent still wins
    lonely = SimpleNamespace(placements=SimpleNamespace(
        entry_point=None,
        creatures=(SimpleNamespace(template_resref="c_x", tag="x", position=(0, 0, 0), bearing=0.0, instance_id="i_x"),),
        doors=(), placeables=(), triggers=(), waypoints=(), sounds=(), cameras=(), stores=(), encounters=(),
        metadata={},
    ))
    result = build_pie_entity_registry(lonely)
    creature = result.by_id("authored:creature:i_x")
    assert creature.faction == "neutral"
    warning_text = " ".join(result.coverage_warnings)
    assert "no authored faction intent" in warning_text
    assert "player entity was not registered" in warning_text


def test_registry_carries_template_locked_state_to_door_entity() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_entities import build_pie_entity_registry

    registry = build_pie_entity_registry(
        _project(),
        template_inspector=lambda kind, _resref: {"locked": True, "key_required": "door_key"}
        if kind == "door"
        else {},
    )
    door = registry.by_id("authored:door:i_door")
    assert door is not None
    assert door.locked is True
    assert door.key_required == "door_key"


def test_registry_hydrates_blank_runtime_tags_from_inspected_templates() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_pie_entities import build_pie_entity_registry

    placements = SimpleNamespace(
        entry_point=None,
        creatures=(
            SimpleNamespace(
                template_resref="n_czerkaoff002",
                tag="",
                position=(0.0, 0.0, 0.0),
                bearing=0.0,
                instance_id="blank_creature",
            ),
            SimpleNamespace(
                template_resref="n_czerkaoff002",
                tag="AuthoredCreature",
                position=(1.0, 0.0, 0.0),
                bearing=0.0,
                instance_id="authored_creature",
            ),
        ),
        doors=(
            SimpleNamespace(
                template_resref="door_a",
                tag="",
                position=(2.0, 0.0, 0.0),
                bearing=0.0,
                instance_id="blank_door",
            ),
            SimpleNamespace(
                template_resref="door_a",
                tag="AuthoredDoor",
                position=(3.0, 0.0, 0.0),
                bearing=0.0,
                instance_id="authored_door",
            ),
        ),
        placeables=(
            SimpleNamespace(
                template_resref="footlker",
                tag="",
                position=(4.0, 0.0, 0.0),
                bearing=0.0,
                instance_id="blank_placeable",
            ),
            SimpleNamespace(
                template_resref="footlker",
                tag="AuthoredPlaceable",
                position=(5.0, 0.0, 0.0),
                bearing=0.0,
                instance_id="authored_placeable",
            ),
        ),
        triggers=(),
        waypoints=(),
        sounds=(),
        cameras=(),
        stores=(),
        encounters=(),
        metadata={},
    )
    template_tags = {
        "creature": "207_Falt",
        "door": "TemplateDoor",
        "placeable": "TemplatePlaceable",
    }
    registry = build_pie_entity_registry(
        SimpleNamespace(placements=placements),
        template_inspector=lambda kind, _resref: {
            "tag": template_tags[kind],
            "useable": kind == "placeable",
        },
    )

    expected = {
        "authored:creature:blank_creature": "207_Falt",
        "authored:creature:authored_creature": "AuthoredCreature",
        "authored:door:blank_door": "TemplateDoor",
        "authored:door:authored_door": "AuthoredDoor",
        "authored:placeable:blank_placeable": "TemplatePlaceable",
        "authored:placeable:authored_placeable": "AuthoredPlaceable",
    }
    assert {entity_id: registry.by_id(entity_id).tag for entity_id in expected} == expected


def test_session_build_attaches_entity_registry() -> None:
    _configure_native_python_roots()
    source = (ROOT / "native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_pie.py").read_text(encoding="utf-8")
    assert "build_pie_entity_registry" in source
    assert "template_inspector=template_inspector" in source
    assert "entity_registry" in source
    mirror = (ROOT / "native/GhostRigger.Core.Tools/Python/src/core/modules/map_studio_pie.py").read_text(encoding="utf-8")
    assert "build_pie_entity_registry" in mirror
