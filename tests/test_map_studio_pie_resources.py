"""Focused contracts for typed KOTOR resource projection into PIE."""

from __future__ import annotations

from pykotor.common.language import LocalizedString
from pykotor.common.misc import InventoryItem, ResRef
from pykotor.resource.generics.utc import UTC, UTCClass, bytes_utc
from pykotor.resource.generics.utd import UTD, bytes_utd
from pykotor.resource.generics.uti import UTI, bytes_uti
from pykotor.resource.generics.utm import UTM, bytes_utm
from pykotor.resource.generics.utp import UTP, bytes_utp

from src.core.modules.map_studio_pie_resources import inspect_map_studio_pie_resource


def test_creature_projection_keeps_combat_dialogue_and_inventory_contracts() -> None:
    utc = UTC()
    utc.first_name = LocalizedString.from_english("Czerka Guard")
    utc.tag = "guard_a"
    utc.faction_id = 1
    utc.conversation = ResRef("guard_talk")
    utc.current_hp = 18
    utc.max_hp = 20
    utc.strength = 14
    utc.dexterity = 12
    utc.natural_ac = 2
    utc.classes = [UTCClass(0, 4)]
    utc.inventory = [InventoryItem(ResRef("g_i_keycard"), droppable=True)]
    utc.on_attacked = ResRef("guard_hit")

    row = inspect_map_studio_pie_resource("creature", "guard", bytes_utc(utc))

    assert row["name"] == "Czerka Guard"
    assert row["faction_id"] == 1
    assert row["conversation"] == "guard_talk"
    assert row["current_hp"] == 18 and row["max_hp"] == 20
    assert row["armor_class"] == 13
    assert row["attack_bonus"] == 6
    assert row["damage_min"] == 3 and row["damage_max"] == 8
    assert row["inventory_items"][0]["resref"] == "g_i_keycard"
    assert ("on_attacked", "guard_hit") in row["scripts"]


def test_creature_projection_hides_retail_generic_variation_suffix() -> None:
    utc = UTC()
    utc.first_name = LocalizedString.from_english("Telosian{F01s}")

    row = inspect_map_studio_pie_resource("creature", "n_telf01s", bytes_utc(utc))

    assert row["name"] == "Telosian"

    utc.first_name = LocalizedString.from_english("Keeper {Archive}")
    preserved = inspect_map_studio_pie_resource("creature", "keeper", bytes_utc(utc))
    assert preserved["name"] == "Keeper {Archive}"


def test_placeable_and_door_projection_keep_keys_and_all_actions_available() -> None:
    utp = UTP()
    utp.name = LocalizedString.from_english("Footlocker")
    utp.useable = True
    utp.has_inventory = True
    utp.inventory = [InventoryItem(ResRef("g_i_credits001"))]
    utp.conversation = ResRef("locker_talk")
    utp.locked = True
    utp.key_required = True
    utp.key_name = "locker_key"
    utp.auto_remove_key = True
    utp.on_used = ResRef("locker_used")
    placeable = inspect_map_studio_pie_resource("placeable", "locker", bytes_utp(utp))

    assert placeable["name"] == "Footlocker"
    assert placeable["useable"] and placeable["has_inventory"]
    assert placeable["conversation"] == "locker_talk"
    assert placeable["key_required"] == "locker_key"
    assert placeable["auto_remove_key"] is True
    assert placeable["inventory_items"][0]["resref"] == "g_i_credits001"
    assert ("on_used", "locker_used") in placeable["scripts"]

    utd = UTD()
    utd.name = LocalizedString.from_english("Security Door")
    utd.locked = True
    utd.key_required = True
    utd.key_name = "door_key"
    utd.conversation = ResRef("door_talk")
    door = inspect_map_studio_pie_resource("door", "security", bytes_utd(utd))

    assert door["name"] == "Security Door"
    assert door["locked"] is True
    assert door["key_required"] == "door_key"
    assert door["conversation"] == "door_talk"


def test_store_and_item_projection_support_inventory_display_and_prices() -> None:
    utm = UTM()
    utm.name = LocalizedString.from_english("Dendis' Store")
    utm.can_buy = True
    utm.can_sell = True
    utm.mark_up = 125
    utm.mark_down = 25
    utm.inventory = [InventoryItem(ResRef("g_w_vbroswrd01"), infinite=True)]
    store = inspect_map_studio_pie_resource("store", "m_202_001", bytes_utm(utm))

    assert store["name"] == "Dendis' Store"
    assert store["can_buy"] and store["can_sell"]
    assert store["inventory_items"][0] == {
        "resref": "g_w_vbroswrd01",
        "droppable": False,
        "infinite": True,
        "count": 1,
    }

    uti = UTI()
    uti.name = LocalizedString.from_english("Vibrosword")
    uti.description = LocalizedString.from_english("A balanced melee weapon.")
    uti.cost = 100
    uti.add_cost = 25
    uti.stack_size = 1
    item = inspect_map_studio_pie_resource("item", "g_w_vbroswrd01", bytes_uti(uti))

    assert item["name"] == "Vibrosword"
    assert item["description"] == "A balanced melee weapon."
    assert item["cost"] == 125
