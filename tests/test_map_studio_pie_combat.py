"""Focused proof for the standalone Map Studio PIE combat runtime."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
from scripts.mcp.start_kotormcp_stdio import _python_roots

for _root in reversed(_python_roots(ROOT)):
    _value = str(_root)
    if _value not in sys.path:
        sys.path.insert(0, _value)

from src.core.modules.map_studio_pie_combat import (
    PIE_COMBAT_ROUND_SECONDS,
    PIE_COMBAT_RUNTIME_LIMITATIONS,
    MapStudioPIECombatAnimationRoles,
    MapStudioPIECombatRuntime,
    MapStudioPIECombatStats,
    MapStudioPIECombatant,
    MapStudioPIEDamageDice,
    derive_pie_weapon_damage_dice,
    pie_damage_type_label,
)


def test_damage_type_label_matches_nwscript_constants() -> None:
    # Bit values verified against KOTOR nwscript.nss DAMAGE_TYPE_* constants.
    assert pie_damage_type_label(1) == "Bludgeoning"
    assert pie_damage_type_label(2) == "Piercing"
    assert pie_damage_type_label(4) == "Slashing"
    assert pie_damage_type_label(4096) == "Energy"  # DAMAGE_TYPE_BLASTER (lightsaber/blaster)
    assert pie_damage_type_label(6) == "Piercing/Slashing"  # 2|4
    assert pie_damage_type_label(0) == "Physical"
    assert pie_damage_type_label("****") == "Physical"


def test_creature_inspection_and_combat_carry_weapon_damage_type() -> None:
    from src.core.modules.map_studio_pie_resources import inspect_map_studio_pie_resource
    from pykotor.common.misc import EquipmentSlot, Game
    from pykotor.resource.generics.utc import UTC, InventoryItem, bytes_utc

    utc = UTC()
    utc.current_hp = 10
    utc.max_hp = 10
    utc.equipment[EquipmentSlot.RIGHT_HAND] = InventoryItem("g_w_lghtsbr01")
    payload = bytes_utc(utc, Game.K2)

    def dmg(resref, str_mod):
        return MapStudioPIEDamageDice(2, 10, int(str_mod))

    inspected = inspect_map_studio_pie_resource(
        "creature", "npc", payload,
        weapon_damage_resolver=dmg,
        weapon_damage_type_resolver=lambda r: "Energy" if r == "g_w_lghtsbr01" else None,
    )
    assert inspected["damage_type"] == "Energy"

    # The combat runtime reports the type in its attack_hit line.
    combatant = MapStudioPIECombatant(
        entity_id="e", display_name="E", relationship_to_player="hostile",
        stats=MapStudioPIECombatStats(
            max_hp=10, current_hp=10, armor_class=-100, attack_bonus=100,
            damage=MapStudioPIEDamageDice(0, 0, 3), damage_type="Energy",
        ),
        animations=ROLES,
    )
    player = MapStudioPIECombatant(
        entity_id="pie:player", display_name="Player", relationship_to_player="player",
        stats=MapStudioPIECombatStats(max_hp=30, current_hp=30, armor_class=10, attack_bonus=100,
                                      damage=MapStudioPIEDamageDice(0, 0, 2), damage_type="Energy",
                                      initiative_bonus=100),
        animations=ROLES, player_controlled=True,
    )
    runtime = MapStudioPIECombatRuntime((player, combatant), player_id="pie:player", seed=1)
    runtime.queue_player_attack("e")
    hit = next(e for e in runtime.advance(3.0).events if e.actor_id == "pie:player" and e.kind == "attack_hit")
    assert hit.damage_type == "Energy"
    assert "Energy damage" in hit.message


def test_weapon_damage_dice_from_baseitems_row_melee_adds_strength() -> None:
    # A vibroblade-like row: 1 die, d8, melee -> 1d8 + Str modifier.
    dice = derive_pie_weapon_damage_dice({"numdice": 1, "dietoroll": 8}, strength_modifier=2, ranged=False)
    assert (dice.count, dice.sides, dice.bonus) == (1, 8, 2)


def test_weapon_damage_dice_ranged_ignores_strength() -> None:
    # A blaster-like row: 1 die, d6, ranged -> 1d6 + 0 (no Str to ranged damage).
    dice = derive_pie_weapon_damage_dice({"NumDice": 1, "DieToRoll": 6}, strength_modifier=3, ranged=True)
    assert (dice.count, dice.sides, dice.bonus) == (1, 6, 0)


def test_weapon_damage_dice_falls_back_to_unarmed_on_empty_or_masked_row() -> None:
    assert (lambda d: (d.count, d.sides))(derive_pie_weapon_damage_dice({})) == (1, 3)
    # KOTOR 2DA masks empty cells with "****"; treat as unset -> unarmed 1d3.
    masked = derive_pie_weapon_damage_dice({"numdice": "****", "dietoroll": "****"}, strength_modifier=5)
    assert (masked.count, masked.sides, masked.bonus) == (1, 3, 5)


def test_creature_inspection_uses_equipped_weapon_damage_when_resolved() -> None:
    from types import SimpleNamespace

    from src.core.modules.map_studio_pie_resources import inspect_map_studio_pie_resource
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import Game
    from pykotor.resource.generics.utc import UTC, UTCClass, bytes_utc

    utc = UTC()
    utc.strength = 14  # +2 melee damage
    utc.dexterity = 10
    utc.current_hp = 20
    utc.max_hp = 20
    utc.classes.append(UTCClass(class_id=0, class_level=3))
    # A right-hand vibrosword-like weapon resref the resolver will identify.
    from pykotor.resource.generics.utc import InventoryItem
    from pykotor.common.misc import EquipmentSlot

    utc.equipment[EquipmentSlot.RIGHT_HAND] = InventoryItem("g_w_vibro01")
    payload = bytes_utc(utc, Game.K2)

    # Resolver: the vibrosword is 1d8 melee; +Str(2) -> 1d8+2 (min 3, max 10).
    def resolver(resref, strength_modifier):
        if resref == "g_w_vibro01":
            return MapStudioPIEDamageDice(count=1, sides=8, bonus=int(strength_modifier))
        return None

    inspected = inspect_map_studio_pie_resource("creature", "npc", payload, weapon_damage_resolver=resolver)
    assert inspected["damage_min"] == 3   # 1 + Str(2)
    assert inspected["damage_max"] == 10  # 8 + Str(2)

    # Without a resolver, the generic Strength-scaled fallback applies (1..6 + Str).
    generic = inspect_map_studio_pie_resource("creature", "npc", payload)
    assert (generic["damage_min"], generic["damage_max"]) == (3, 8)


def test_creature_inspection_carries_equipped_weapon_crit_threat_and_multiplier() -> None:
    from src.core.modules.map_studio_pie_resources import inspect_map_studio_pie_resource
    from pykotor.common.misc import EquipmentSlot, Game
    from pykotor.resource.generics.utc import UTC, InventoryItem, bytes_utc

    utc = UTC()
    utc.strength = 10
    utc.current_hp = 10
    utc.max_hp = 10
    utc.equipment[EquipmentSlot.RIGHT_HAND] = InventoryItem("g_w_lghtsbr01")
    payload = bytes_utc(utc, Game.K2)

    # Lightsaber: 1d? damage plus crit threat 2 (19-20), x2 multiplier.
    def dmg(resref, str_mod):
        return MapStudioPIEDamageDice(count=2, sides=10, bonus=int(str_mod)) if resref == "g_w_lghtsbr01" else None

    def crit(resref):
        return (2, 2) if resref == "g_w_lghtsbr01" else None

    inspected = inspect_map_studio_pie_resource(
        "creature", "npc", payload, weapon_damage_resolver=dmg, weapon_critical_resolver=crit
    )
    assert inspected["critical_threat"] == 2  # threatens on 19-20
    assert inspected["critical_multiplier"] == 2

    # No crit resolver -> d20 baseline (threat 1, x2).
    baseline = inspect_map_studio_pie_resource("creature", "npc", payload, weapon_damage_resolver=dmg)
    assert (baseline["critical_threat"], baseline["critical_multiplier"]) == (1, 2)


def test_creature_inspection_applies_weapon_focus_and_specialization_feats() -> None:
    from src.core.modules.map_studio_pie_resources import inspect_map_studio_pie_resource
    from pykotor.common.misc import EquipmentSlot, Game
    from pykotor.resource.generics.utc import UTC, InventoryItem, bytes_utc

    utc = UTC()
    utc.strength = 10  # +0, isolates the feat bonuses
    utc.current_hp = 10
    utc.max_hp = 10
    utc.classes.append(__import__("pykotor.resource.generics.utc", fromlist=["UTCClass"]).UTCClass(class_id=0, class_level=2))
    utc.equipment[EquipmentSlot.RIGHT_HAND] = InventoryItem("g_w_lghtsbr01")
    # feat.2da: 36 = WEAPON_FOCUS_LIGHTSABER, 50 = WEAPON_SPEC_LIGHTSABER.
    utc.feats.extend([36, 50])
    payload = bytes_utc(utc, Game.K2)

    def dmg(resref, str_mod):
        return MapStudioPIEDamageDice(2, 10, int(str_mod))  # 2d10, min 2 / max 20 at Str +0

    inspected = inspect_map_studio_pie_resource(
        "creature", "npc", payload,
        weapon_damage_resolver=dmg,
        weapon_feat_category_resolver=lambda r: "lightsaber" if r == "g_w_lghtsbr01" else "",
    )
    # attack = BAB(2) + Str(0) + Weapon Focus(+1) = 3
    assert inspected["attack_bonus"] == 3
    # damage 2d10 + Weapon Specialization(+2): min 4, max 22
    assert inspected["damage_min"] == 4
    assert inspected["damage_max"] == 22

    # A creature lacking the feats gets no bonus (BAB 2, damage 2..20).
    plain = UTC()
    plain.strength = 10
    plain.current_hp = 10
    plain.max_hp = 10
    plain.classes.append(__import__("pykotor.resource.generics.utc", fromlist=["UTCClass"]).UTCClass(class_id=0, class_level=2))
    plain.equipment[EquipmentSlot.RIGHT_HAND] = InventoryItem("g_w_lghtsbr01")
    plain_payload = bytes_utc(plain, Game.K2)
    plain_inspected = inspect_map_studio_pie_resource(
        "creature", "npc", plain_payload,
        weapon_damage_resolver=dmg,
        weapon_feat_category_resolver=lambda r: "lightsaber",
    )
    assert plain_inspected["attack_bonus"] == 2
    assert (plain_inspected["damage_min"], plain_inspected["damage_max"]) == (2, 20)


def test_creature_inspection_applies_equipped_armor_ac_and_dex_cap() -> None:
    from src.core.modules.map_studio_pie_resources import inspect_map_studio_pie_resource
    from pykotor.common.misc import EquipmentSlot, Game
    from pykotor.resource.generics.utc import UTC, InventoryItem, bytes_utc

    utc = UTC()
    utc.dexterity = 18  # +4 Dex modifier
    utc.natural_ac = 1
    utc.current_hp = 10
    utc.max_hp = 10
    utc.equipment[EquipmentSlot.ARMOR] = InventoryItem("a_light_01")
    payload = bytes_utc(utc, Game.K2)

    # Light armor: +4 base AC, max Dex bonus +5 (so full +4 Dex applies).
    def armor_resolver(resref):
        return (4, 5) if resref == "a_light_01" else None

    inspected = inspect_map_studio_pie_resource("creature", "npc", payload, armor_ac_resolver=armor_resolver)
    assert inspected["armor_class"] == 10 + 1 + 4 + 4  # 10 + natural + armor + Dex = 19

    # Heavy armor with a +1 Dex cap clamps the +4 Dex to +1.
    def heavy_resolver(resref):
        return (8, 1)

    heavy = inspect_map_studio_pie_resource("creature", "npc", payload, armor_ac_resolver=heavy_resolver)
    assert heavy["armor_class"] == 10 + 1 + 8 + 1  # Dex capped at +1 -> 20

    # No resolver -> uncapped Dex, no armor bonus (10 + natural + Dex).
    unarmored = inspect_map_studio_pie_resource("creature", "npc", payload)
    assert unarmored["armor_class"] == 10 + 1 + 4  # 15


ROLES = MapStudioPIECombatAnimationRoles(
    ready=("fixture_ready",),
    attack=("fixture_attack",),
    damage=("fixture_damage",),
    death=("fixture_death",),
)


def _combatant(
    entity_id: str,
    relationship: str,
    *,
    hp: int = 20,
    armor_class: int = 10,
    attack_bonus: int = 100,
    damage: int = 2,
    initiative_bonus: int = 0,
    player: bool = False,
    retaliates: bool = True,
) -> MapStudioPIECombatant:
    return MapStudioPIECombatant(
        entity_id=entity_id,
        display_name=entity_id.replace("_", " ").title(),
        relationship_to_player=relationship,
        stats=MapStudioPIECombatStats(
            max_hp=hp,
            current_hp=hp,
            armor_class=armor_class,
            attack_bonus=attack_bonus,
            damage=MapStudioPIEDamageDice(0, 0, damage),
            initiative_bonus=initiative_bonus,
        ),
        animations=ROLES,
        player_controlled=player,
        retaliates=retaliates,
    )


def _runtime(*, seed: int = 1, enemy_hp: int = 20) -> MapStudioPIECombatRuntime:
    return MapStudioPIECombatRuntime(
        (
            _combatant("player", "player", hp=30, initiative_bonus=100, player=True),
            _combatant("enemy", "hostile", hp=enemy_hp, initiative_bonus=-100),
        ),
        player_id="player",
        seed=seed,
    )


def test_combat_contract_is_immutable_explicit_and_clip_name_agnostic() -> None:
    combatant = _combatant("enemy", "hostile")
    with pytest.raises(FrozenInstanceError):
        combatant.display_name = "Changed"  # type: ignore[misc]

    assert PIE_COMBAT_ROUND_SECONDS == 3.0
    assert combatant.animations.candidates("attack") == ("fixture_attack",)
    assert MapStudioPIECombatAnimationRoles().attack == ()
    assert all("KOTOR" in text or "PIE" in text or "Callers" in text or "Range" in text for text in PIE_COMBAT_RUNTIME_LIMITATIONS)

    source = (ROOT / "src/core/modules/map_studio_pie_combat.py").read_text(encoding="utf-8")
    assert "PySide" not in source
    assert "resource_manager" not in source
    assert "import random" not in source
    assert "g1a1" not in source and "g0a1" not in source


def test_pause_preserves_time_hp_and_queue_until_resume_crosses_round_boundary() -> None:
    runtime = _runtime()
    runtime.pause()
    action = runtime.queue_player_attack("enemy")

    paused = runtime.advance(30.0)
    assert paused.paused is True
    assert paused.simulation_time == 0.0
    assert paused.round_index == 0
    assert paused.combatant("enemy").current_hp == 20
    assert paused.queued_actions == (action,)

    runtime.resume()
    before = runtime.advance(2.999)
    assert before.round_index == 0
    assert before.combatant("enemy").current_hp == 20
    after = runtime.advance(0.001)
    assert after.round_index == 1
    assert after.simulation_time == pytest.approx(3.0)
    assert after.combatant("enemy").current_hp == 18
    assert after.combatant("player").current_hp == 28
    assert after.queued_actions == ()


def test_round_menu_can_clear_queue_without_ending_realtime_encounter() -> None:
    runtime = _runtime(seed=17)
    runtime.queue_player_attack("enemy")
    runtime.queue_player_attack("enemy")

    cleared = runtime.clear_player_actions()

    assert cleared.active is True
    assert cleared.round_index == 0
    assert cleared.queued_actions == ()
    assert cleared.next_round_in == pytest.approx(3.0)
    assert cleared.events[-1].kind == "action_queue_cleared"
    assert "Cleared 2" in cleared.events[-1].message


def test_fixed_seed_trace_is_identical_across_frame_chunking() -> None:
    whole = _runtime(seed=123)
    chunked = _runtime(seed=123)
    for runtime in (whole, chunked):
        runtime.queue_player_attack("enemy")
        runtime.queue_player_attack("enemy")

    whole_snapshot = whole.advance(6.0)
    for _ in range(24):
        chunked_snapshot = chunked.advance(0.25)

    assert chunked_snapshot == whole_snapshot
    assert [event.sequence for event in whole_snapshot.events] == list(range(1, len(whole_snapshot.events) + 1))
    assert [event.kind for event in whole.events_since(0)] == [event.kind for event in chunked.events_since(0)]


def test_initiative_orders_round_and_defeated_actor_cannot_retaliate() -> None:
    runtime = MapStudioPIECombatRuntime(
        (
            _combatant(
                "player",
                "player",
                hp=20,
                damage=50,
                initiative_bonus=100,
                player=True,
            ),
            _combatant("enemy", "hostile", hp=5, damage=50, initiative_bonus=-100),
        ),
        player_id="player",
        seed=9,
    )
    runtime.queue_player_attack("enemy")
    snapshot = runtime.advance(3.0)

    assert snapshot.initiative_order == ("player", "enemy")
    assert snapshot.combatant("enemy").alive is False
    assert snapshot.combatant("player").current_hp == 20
    assert snapshot.active is False and snapshot.next_round_in is None
    kinds = [event.kind for event in snapshot.events]
    assert "combatant_defeated" in kinds
    assert "action_skipped" in kinds
    assert kinds[-1] == "combat_ended"


def test_combat_resolves_with_victory_when_all_hostiles_fall() -> None:
    runtime = MapStudioPIECombatRuntime(
        (
            _combatant("player", "player", hp=20, damage=50, initiative_bonus=100, player=True),
            _combatant("enemy", "hostile", hp=5, damage=1, initiative_bonus=-100),
        ),
        player_id="player",
        seed=9,
    )
    runtime.queue_player_attack("enemy")
    snapshot = runtime.advance(3.0)

    assert snapshot.active is False
    assert snapshot.outcome == "victory"
    ended = next(e for e in snapshot.events if e.kind == "combat_ended")
    assert ended.outcome == "victory"
    assert "victory" in ended.message


def test_combat_resolves_with_defeat_when_the_player_falls() -> None:
    runtime = MapStudioPIECombatRuntime(
        (
            _combatant("player", "player", hp=4, damage=1, initiative_bonus=-100, player=True),
            _combatant("enemy", "hostile", hp=40, damage=50, initiative_bonus=100),
        ),
        player_id="player",
        seed=9,
    )
    runtime.queue_player_attack("enemy")
    snapshot = runtime.advance(6.0)

    assert snapshot.active is False
    assert snapshot.outcome == "defeat"
    ended = next(e for e in snapshot.events if e.kind == "combat_ended")
    assert ended.outcome == "defeat"


def test_hostile_retaliates_every_active_round_even_when_player_queue_is_empty() -> None:
    runtime = _runtime(seed=3)
    runtime.queue_player_attack("enemy")
    first = runtime.advance(3.0)
    second = runtime.advance(3.0)

    assert first.combatant("player").current_hp == 28
    assert second.combatant("player").current_hp == 26
    assert first.combatant("enemy").current_hp == 18
    assert second.combatant("enemy").current_hp == 18
    retaliation_hits = [
        event
        for event in second.events
        if event.kind == "attack_hit" and event.actor_id == "enemy" and event.target_id == "player"
    ]
    assert len(retaliation_hits) == 2


def test_d20_natural_one_always_misses_and_natural_twenty_always_hits() -> None:
    natural_one = MapStudioPIECombatRuntime(
        (
            _combatant("player", "player", attack_bonus=100, initiative_bonus=100, player=True),
            _combatant("enemy", "hostile", armor_class=-100, initiative_bonus=-100),
        ),
        player_id="player",
        seed=63,
    )
    natural_one.queue_player_attack("enemy")
    miss = next(
        event
        for event in natural_one.advance(3.0).events
        if event.actor_id == "player" and event.kind in {"attack_hit", "attack_missed"}
    )
    assert miss.d20_roll == 1 and miss.kind == "attack_missed"

    natural_twenty = MapStudioPIECombatRuntime(
        (
            _combatant("player", "player", attack_bonus=-100, initiative_bonus=100, player=True),
            _combatant("enemy", "hostile", armor_class=100, initiative_bonus=-100),
        ),
        player_id="player",
        seed=2,
    )
    natural_twenty.queue_player_attack("enemy")
    hit = next(
        event
        for event in natural_twenty.advance(3.0).events
        if event.actor_id == "player" and event.kind in {"attack_hit", "attack_missed"}
    )
    assert hit.d20_roll == 20 and hit.kind == "attack_hit"


def test_natural_twenty_is_a_critical_hit_that_multiplies_damage() -> None:
    # Reuse the seed=2 path that forces the player's attack to roll a natural 20.
    # The default d20 baseline (threat 1, x2) makes that a critical: 2 base -> 4.
    runtime = MapStudioPIECombatRuntime(
        (
            _combatant("player", "player", attack_bonus=-100, initiative_bonus=100, player=True, damage=2),
            _combatant("enemy", "hostile", hp=99, armor_class=100, initiative_bonus=-100),
        ),
        player_id="player",
        seed=2,
    )
    runtime.queue_player_attack("enemy")
    hit = next(
        event
        for event in runtime.advance(3.0).events
        if event.actor_id == "player" and event.kind == "attack_hit"
    )
    assert hit.d20_roll == 20
    assert hit.critical is True
    assert hit.damage == 4  # 2 base damage x2 critical multiplier
    assert "critical x2" in hit.message


def test_assisting_ally_engages_and_attacks_a_hostile() -> None:
    ally = MapStudioPIECombatant(
        entity_id="companion",
        display_name="Companion",
        relationship_to_player="friendly",
        stats=MapStudioPIECombatStats(
            max_hp=20, current_hp=20, armor_class=10, attack_bonus=100,
            damage=MapStudioPIEDamageDice(0, 0, 5),
        ),
        animations=ROLES,
        assists=True,
    )
    runtime = MapStudioPIECombatRuntime(
        (
            _combatant("player", "player", attack_bonus=100, initiative_bonus=100, player=True),
            ally,
            _combatant("enemy", "hostile", hp=200, armor_class=-100, initiative_bonus=-100),
        ),
        player_id="player",
        seed=5,
    )
    runtime.queue_player_attack("enemy")
    events = runtime.advance(3.0).events
    # The ally announced it joined and then struck the hostile.
    assert any(e.kind == "ally_engaged" and e.actor_id == "companion" for e in events)
    ally_hits = [
        e for e in events
        if e.kind in {"attack_hit", "attack_missed"} and e.actor_id == "companion" and e.target_id == "enemy"
    ]
    assert len(ally_hits) == 1


def test_non_assisting_friendly_stays_out_of_combat() -> None:
    bystander = MapStudioPIECombatant(
        entity_id="bystander", display_name="Bystander", relationship_to_player="friendly",
        stats=MapStudioPIECombatStats(max_hp=10, current_hp=10, armor_class=10, attack_bonus=1,
                                      damage=MapStudioPIEDamageDice(0, 0, 1)),
        animations=ROLES,  # assists defaults to False
    )
    runtime = MapStudioPIECombatRuntime(
        (
            _combatant("player", "player", attack_bonus=100, initiative_bonus=100, player=True),
            bystander,
            _combatant("enemy", "hostile", hp=200, armor_class=-100, initiative_bonus=-100),
        ),
        player_id="player",
        seed=5,
    )
    runtime.queue_player_attack("enemy")
    events = runtime.advance(3.0).events
    assert not any(e.actor_id == "bystander" for e in events)  # untouched behavior


def test_default_stats_expose_d20_critical_baseline() -> None:
    stats = MapStudioPIECombatStats(
        max_hp=10, current_hp=10, armor_class=10, attack_bonus=0, damage=MapStudioPIEDamageDice(1, 6, 0)
    )
    assert stats.critical_threat == 1  # threatens only on a natural 20
    assert stats.critical_multiplier == 2


def test_attack_and_damage_events_carry_data_driven_animation_roles() -> None:
    runtime = _runtime(seed=5, enemy_hp=2)
    runtime.queue_player_attack("enemy")
    snapshot = runtime.advance(3.0)

    attack = next(event for event in snapshot.events if event.kind == "attack_started" and event.animation_actor_id == "player")
    defeated = next(event for event in snapshot.events if event.kind == "combatant_defeated")
    assert attack.actor_id == "player" and attack.target_id == "enemy"
    assert attack.animation_role == "attack"
    assert attack.animation_candidates == ("fixture_attack",)
    assert defeated.animation_actor_id == "enemy"
    assert defeated.animation_role == "death"
    assert defeated.animation_candidates == ("fixture_death",)


def test_friendly_fire_and_invalid_explicit_stats_are_rejected() -> None:
    friendly = _combatant("friend", "friendly")
    runtime = MapStudioPIECombatRuntime(
        (
            _combatant("player", "player", player=True),
            friendly,
        ),
        player_id="player",
    )
    with pytest.raises(ValueError, match="explicitly hostile"):
        runtime.queue_player_attack("friend")
    with pytest.raises(ValueError, match="max HP"):
        MapStudioPIECombatStats(0, 0, 10, 0, MapStudioPIEDamageDice(1, 4))
    with pytest.raises(ValueError, match="at least one side"):
        MapStudioPIEDamageDice(1, 0)


def test_source_current_hp_above_declared_max_is_preserved_without_mutating_input() -> None:
    stats = MapStudioPIECombatStats(
        max_hp=8,
        current_hp=9,
        armor_class=10,
        attack_bonus=0,
        damage=MapStudioPIEDamageDice(1, 4),
    )
    enemy = MapStudioPIECombatant("enemy", "Enemy", "hostile", stats, retaliates=False)
    runtime = MapStudioPIECombatRuntime(
        (_combatant("player", "player", player=True), enemy),
        player_id="player",
    )

    snapshot = runtime.snapshot().combatant("enemy")
    assert snapshot.current_hp == 9 and snapshot.max_hp == 9
    assert enemy.stats.current_hp == 9 and enemy.stats.max_hp == 9
