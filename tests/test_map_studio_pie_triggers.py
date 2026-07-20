"""Focused contracts for PIE trigger-volume crossing detection.

Grounded in real 207TEL GIT triggers: geometry points are authored local to the
trigger position, so world polygons offset by that position. Enter/exit is
even-odd point-in-polygon on XY; transition triggers are reported, not warped;
OnEnter scripts are reported as deferred. Editor-side detection only.
"""

from __future__ import annotations

from types import SimpleNamespace


def _trigger_entity(entity_id, tag, position, geometry, *, module="", target="", scripts=()):
    return SimpleNamespace(
        entity_id=entity_id,
        kind="trigger",
        tag=tag,
        position=position,
        geometry=geometry,
        transition_module=module,
        transition_target=target,
        scripts=scripts,
    )


def test_validate_module_transitions_flags_missing_destinations() -> None:
    from src.core.modules.map_studio_pie_triggers import (
        normalize_module_root,
        validate_module_transitions,
    )

    assert normalize_module_root("202TEL.mod") == "202tel"
    assert normalize_module_root("danm13_s.rim") == "danm13"
    assert normalize_module_root("  Korr_M33aa.RIM ") == "korr_m33aa"

    transitions = [
        ("door", "d_Cantina_main", "202tel", "from_207TEL_main"),      # installed
        ("door", "d_broken", "zzz_missing", "wp"),                     # not installed
        ("door", "d_Cantina_game", "202TEL.mod", "from_207TEL_game"),  # installed (filename form)
    ]
    available = ["202tel.mod", "207tel.rim", "danm13_s.rim"]
    checks = validate_module_transitions(transitions, available)

    by_key = {(c.module, c.target): c.exists for c in checks}
    assert by_key[("202tel", "from_207TEL_main")] is True
    assert by_key[("202tel", "from_207TEL_game")] is True   # filename normalized to root
    assert by_key[("zzz_missing", "wp")] is False
    assert sum(1 for c in checks if c.exists is False) == 1
    # A blank/degenerate destination is skipped, not reported as missing.
    assert validate_module_transitions([("door", "x", "", "wp")], available) == ()

    # When the module list can't be resolved (empty), report unverifiable
    # (exists=None) rather than a false "missing" alarm.
    unverifiable = validate_module_transitions(
        [("door", "d", "202tel", "from_207TEL_main")], available_modules=()
    )
    assert len(unverifiable) == 1
    assert unverifiable[0].exists is None


def test_point_in_polygon_inside_outside_and_degenerate() -> None:
    from src.core.modules.map_studio_pie_triggers import point_in_polygon_xy

    square = ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0))
    assert point_in_polygon_xy(2.0, 2.0, square) is True
    assert point_in_polygon_xy(5.0, 2.0, square) is False
    assert point_in_polygon_xy(-1.0, 2.0, square) is False
    # A concave L-shape: the cut-out corner is outside, both bars are inside.
    l_shape = ((0.0, 0.0), (4.0, 0.0), (4.0, 1.0), (1.0, 1.0), (1.0, 4.0), (0.0, 4.0))
    assert point_in_polygon_xy(2.0, 0.5, l_shape) is True   # horizontal bar
    assert point_in_polygon_xy(0.5, 3.0, l_shape) is True   # vertical bar
    assert point_in_polygon_xy(3.0, 3.0, l_shape) is False  # the notch
    assert point_in_polygon_xy(0.0, 0.0, ((0.0, 0.0), (1.0, 1.0))) is False  # < 3 points


def test_build_offsets_local_geometry_by_trigger_position() -> None:
    from src.core.modules.map_studio_pie_triggers import build_trigger_volumes, point_in_polygon_xy

    entity = _trigger_entity(
        "authored:trigger:0",
        "exit_pad",
        position=(15.0, -27.0, 10.2),
        geometry=((-2.0, -2.0, 0.02), (2.0, -2.0, 0.02), (2.0, 2.0, 0.02), (-2.0, 2.0, 0.02)),
    )
    volumes = build_trigger_volumes([entity])
    assert len(volumes) == 1
    volume = volumes[0]
    # World polygon centered on the trigger position, not the local origin.
    assert point_in_polygon_xy(15.0, -27.0, volume.polygon_xy) is True
    assert point_in_polygon_xy(0.0, 0.0, volume.polygon_xy) is False
    assert volume.is_transition is False


def test_build_skips_degenerate_and_non_trigger_entities() -> None:
    from src.core.modules.map_studio_pie_triggers import build_trigger_volumes

    two_point = _trigger_entity("t:short", "short", (0.0, 0.0, 0.0), ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)))
    creature = SimpleNamespace(entity_id="c:0", kind="creature", tag="npc", position=(0.0, 0.0, 0.0), geometry=())
    good = _trigger_entity("t:ok", "ok", (0.0, 0.0, 0.0), ((0.0, 0.0), (2.0, 0.0), (1.0, 2.0)))
    volumes = build_trigger_volumes([two_point, creature, good])
    assert [v.entity_id for v in volumes] == ["t:ok"]


def test_transition_flag_and_target() -> None:
    from src.core.modules.map_studio_pie_triggers import build_trigger_volumes

    entity = _trigger_entity(
        "t:warp",
        "to_citadel",
        (0.0, 0.0, 0.0),
        ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)),
        module="262tel",
        target="wp_from_207",
    )
    volume = build_trigger_volumes([entity])[0]
    assert volume.is_transition is True
    assert volume.transition_module == "262tel"
    assert volume.transition_target == "wp_from_207"


def test_tracker_debounces_enter_and_reports_exit() -> None:
    from src.core.modules.map_studio_pie_triggers import TriggerCrossingTracker, build_trigger_volumes

    volumes = build_trigger_volumes(
        [_trigger_entity("t:0", "pad", (0.0, 0.0, 0.0), ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)))]
    )
    tracker = TriggerCrossingTracker(volumes)

    assert tracker.update(-1.0, 2.0) == ()  # outside -> nothing
    first = tracker.update(2.0, 2.0)  # walk in
    assert [c.kind for c in first] == ["entered"]
    assert tracker.update(2.5, 2.0) == ()  # still inside -> debounced, no repeat
    exited = tracker.update(10.0, 2.0)  # walk out
    assert [c.kind for c in exited] == ["exited"]
    assert tracker.inside_ids() == frozenset()


def test_gameplay_runtime_emits_trigger_and_transition_events() -> None:
    from src.core.modules.map_studio_pie_entities import PIEEntity, PIEEntityRegistry
    from src.core.modules.map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

    player = PIEEntity(
        entity_id="pie:player", kind="player", tag="player", display_name="Player",
        template_resref="", position=(0.0, 0.0, 0.0), faction="player",
        focusable=False, interactive=False,
    )
    script_trigger = PIEEntity(
        entity_id="authored:trigger:0", kind="trigger", tag="onenter_pad", display_name="onenter_pad",
        template_resref="", position=(10.0, 0.0, 0.0), interaction="trigger",
        geometry=((-2.0, -2.0, 0.0), (2.0, -2.0, 0.0), (2.0, 2.0, 0.0), (-2.0, 2.0, 0.0)),
        scripts=(("onenter", "k_pad_enter"),),
    )
    warp_trigger = PIEEntity(
        entity_id="authored:trigger:1", kind="trigger", tag="to_citadel", display_name="to_citadel",
        template_resref="", position=(30.0, 0.0, 0.0), interaction="trigger",
        geometry=((-2.0, -2.0, 0.0), (2.0, -2.0, 0.0), (2.0, 2.0, 0.0), (-2.0, 2.0, 0.0)),
        transition_module="262tel", transition_target="wp_from_207",
    )
    registry = PIEEntityRegistry((player, script_trigger, warp_trigger))
    runtime = MapStudioPIEGameplayRuntime(registry, game="K2")

    runtime.advance(0.1, player_position=(0.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
    assert runtime.drain_events() == ()  # outside every trigger

    runtime.advance(0.1, player_position=(10.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
    script_events = [e for e in runtime.drain_events() if e.kind.startswith("trigger")]
    assert any(e.kind == "trigger_entered" and "deferred" in e.message for e in script_events)

    runtime.advance(0.1, player_position=(30.0, 0.0, 0.0), camera_forward=(1.0, 0.0, 0.0))
    warp_events = runtime.drain_events()
    entered = next(e for e in warp_events if e.kind == "transition_trigger_entered")
    assert entered.value == "262tel/wp_from_207"
    assert "warp" in entered.message.lower()
    # Leaving the previous script trigger also reported an exit.
    assert any(e.kind == "trigger_exited" for e in warp_events)
