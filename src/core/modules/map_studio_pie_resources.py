"""Typed KOTOR resource projection for Map Studio PIE.

The resource manager owns byte discovery and PyKotor owns binary decoding.  This
module performs the narrow domain projection between those layers: it turns one
UTC/UTP/UTD/UTT/UTM/UTI payload into immutable-friendly scalar data consumed by
the editor-only PIE entity, interaction, inventory, and combat systems.

No projected value is written back to the source resource.  Script hooks remain
resrefs and are reported as deferred rather than being interpreted as NWScript.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable


TLKLookup = Callable[[int], str]


_CREATURE_VARIATION_SUFFIX = re.compile(r"\s*\{[FM]\d{2}S\}\s*$", re.IGNORECASE)


def _resref(value: Any) -> str:
    return str(value or "").strip().lower()


# feat.2da ids: category -> (Weapon Focus feat, Weapon Specialization feat).
# Only the unambiguous lightsaber/melee categories are applied; blaster is
# omitted because its pistol-vs-rifle focus feat can't be split from baseitems.
_WEAPON_FEAT_IDS: dict[str, tuple[int, int]] = {
    "lightsaber": (36, 50),
    "melee": (37, 51),
}


def _ability_modifier(value: Any) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        score = 10
    return (score - 10) // 2


def localized_text(value: Any, tlk_lookup: TLKLookup | None = None) -> str:
    """Resolve one PyKotor ``LocalizedString`` without fabricating text."""

    if value is None:
        return ""
    getter = getattr(value, "get", None)
    if callable(getter):
        try:
            from pykotor.common.language import Gender, Language

            for language, gender in (
                (Language.ENGLISH, Gender.MALE),
                (Language.ENGLISH, Gender.FEMALE),
            ):
                text = str(getter(language, gender) or "").strip()
                if text:
                    return text
        except Exception:
            pass
    try:
        stringref = int(getattr(value, "stringref", -1) or -1)
    except (TypeError, ValueError):
        stringref = -1
    if stringref >= 0 and callable(tlk_lookup):
        try:
            text = str(tlk_lookup(stringref) or "").strip()
            if text:
                return text
        except Exception:
            pass
    return f"<TLK {stringref}>" if stringref >= 0 else ""


def _creature_display_name(value: str) -> str:
    """Remove the narrow K2 generic-NPC variation suffix hidden by retail UI."""

    return _CREATURE_VARIATION_SUFFIX.sub("", str(value or "")).strip()


def _inventory_rows(items: Iterable[Any]) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for item in tuple(items or ()):
        resref = _resref(getattr(item, "resref", item))
        if not resref:
            continue
        rows.append(
            {
                "resref": resref,
                "droppable": bool(getattr(item, "droppable", False)),
                "infinite": bool(getattr(item, "infinite", False)),
                "count": max(1, int(getattr(item, "stack_size", 1) or 1)),
            }
        )
    return tuple(rows)


def _script_rows(resource: Any, names: Iterable[str]) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    for name in names:
        resref = _resref(getattr(resource, name, ""))
        if resref:
            rows.append((str(name), resref))
    return tuple(rows)


_UTC_SCRIPTS = (
    "on_attacked",
    "on_blocked",
    "on_damaged",
    "on_death",
    "on_dialog",
    "on_disturbed",
    "on_end_dialog",
    "on_end_round",
    "on_heartbeat",
    "on_notice",
    "on_rested",
    "on_spawn",
    "on_spell",
    "on_user_defined",
)

_UTP_SCRIPTS = (
    "on_closed",
    "on_damaged",
    "on_death",
    "on_disarm",
    "on_end_dialog",
    "on_force_power",
    "on_heartbeat",
    "on_inventory",
    "on_lock",
    "on_melee_attack",
    "on_open",
    "on_open_failed",
    "on_trap_triggered",
    "on_unlock",
    "on_used",
    "on_user_defined",
)

_UTD_SCRIPTS = (
    "on_click",
    "on_closed",
    "on_damaged",
    "on_death",
    "on_disarm",
    "on_heartbeat",
    "on_lock",
    "on_melee",
    "on_open",
    "on_open_failed",
    "on_power",
    "on_trap_triggered",
    "on_unlock",
    "on_user_defined",
)


def _creature_projection(
    utc: Any,
    tlk_lookup: TLKLookup | None,
    *,
    weapon_damage_resolver: Any = None,
    armor_ac_resolver: Any = None,
    weapon_critical_resolver: Any = None,
    weapon_damage_type_resolver: Any = None,
    weapon_feat_category_resolver: Any = None,
) -> dict[str, Any]:
    first = localized_text(getattr(utc, "first_name", None), tlk_lookup)
    last = localized_text(getattr(utc, "last_name", None), tlk_lookup)
    name = _creature_display_name(" ".join(value for value in (first, last) if value))
    level = sum(max(0, int(getattr(row, "class_level", 0) or 0)) for row in tuple(getattr(utc, "classes", ()) or ()))
    strength_mod = _ability_modifier(getattr(utc, "strength", 10))
    dexterity_mod = _ability_modifier(getattr(utc, "dexterity", 10))
    maximum_hp = max(
        1,
        int(getattr(utc, "max_hp", 0) or 0),
        int(getattr(utc, "hp", 0) or 0),
        int(getattr(utc, "current_hp", 0) or 0),
    )
    current_hp = max(0, min(maximum_hp, int(getattr(utc, "current_hp", maximum_hp) or maximum_hp)))
    inventory = list(_inventory_rows(getattr(utc, "inventory", ())))
    equipped_resrefs: list[str] = []
    for slot, item in dict(getattr(utc, "equipment", {}) or {}).items():
        resref = _resref(getattr(item, "resref", item))
        if resref:
            equipped_resrefs.append(resref)
            inventory.append(
                {
                    "resref": resref,
                    "droppable": bool(getattr(item, "droppable", False)),
                    "infinite": bool(getattr(item, "infinite", False)),
                    "count": 1,
                    "equipped_slot": str(getattr(slot, "name", slot) or slot),
                }
            )
    # Faithful weapon damage: use the first equipped item the resolver identifies
    # as a weapon (its baseitems.2da dice + Strength for melee). Non-weapons and
    # an unarmed creature keep the generic Strength-scaled fallback below.
    damage_min = max(1, 1 + strength_mod)
    damage_max = max(2, 6 + strength_mod)
    critical_threat = 1
    critical_multiplier = 2
    damage_type = "Physical"
    attack_feat_bonus = 0
    damage_feat_bonus = 0
    if callable(weapon_damage_resolver):
        for resref in equipped_resrefs:
            try:
                dice = weapon_damage_resolver(resref, strength_mod)
            except Exception:
                dice = None
            if dice is not None:
                weapon_min = int(dice.count) + int(dice.bonus)
                weapon_max = int(dice.count) * int(dice.sides) + int(dice.bonus)
                damage_min = max(1, weapon_min)
                damage_max = max(damage_min, weapon_max)
                # Same weapon's baseitems.2da crit threat/multiplier, if resolvable.
                if callable(weapon_critical_resolver):
                    try:
                        crit = weapon_critical_resolver(resref)
                    except Exception:
                        crit = None
                    if crit is not None:
                        critical_threat = max(1, int(crit[0]))
                        critical_multiplier = max(1, int(crit[1]))
                if callable(weapon_damage_type_resolver):
                    try:
                        resolved_type = weapon_damage_type_resolver(resref)
                    except Exception:
                        resolved_type = None
                    if resolved_type:
                        damage_type = str(resolved_type)
                # Weapon Focus (+1 attack) / Weapon Specialization (+2 damage) for
                # the unambiguous lightsaber/melee categories, when the creature
                # actually has the matching feat (feat.2da ids, folded in below).
                if callable(weapon_feat_category_resolver):
                    try:
                        category = str(weapon_feat_category_resolver(resref) or "")
                    except Exception:
                        category = ""
                    feat_ids = _WEAPON_FEAT_IDS.get(category)
                    if feat_ids:
                        creature_feats = {
                            int(value)
                            for value in tuple(getattr(utc, "feats", ()) or ())
                            if isinstance(value, (int, float))
                        }
                        focus_id, spec_id = feat_ids
                        if focus_id in creature_feats:
                            attack_feat_bonus = 1
                        if spec_id in creature_feats:
                            damage_feat_bonus = 2
                break
    # Faithful armor class: equipped armor adds its baseitems.2da base AC and caps
    # the Dexterity bonus. Without armor the Dexterity bonus is uncapped.
    armor_bonus = 0
    dexterity_ac = dexterity_mod
    if callable(armor_ac_resolver):
        for resref in equipped_resrefs:
            try:
                armor = armor_ac_resolver(resref)
            except Exception:
                armor = None
            if armor is not None:
                armor_bonus = int(armor[0])
                dexterity_ac = min(dexterity_mod, int(armor[1]))
                break
    armor_class = max(1, 10 + int(getattr(utc, "natural_ac", 0) or 0) + armor_bonus + dexterity_ac)
    damage_min = max(1, damage_min + damage_feat_bonus)
    damage_max = max(damage_min, damage_max + damage_feat_bonus)
    return {
        "name": name,
        "tag": str(getattr(utc, "tag", "") or ""),
        "faction_id": int(getattr(utc, "faction_id", 0) or 0),
        "conversation": _resref(getattr(utc, "conversation", "")),
        "visible": not bool(getattr(utc, "will_not_render", False)),
        "party_interact": bool(getattr(utc, "party_interact", True)),
        "plot": bool(getattr(utc, "plot", False)),
        "current_hp": current_hp,
        "max_hp": maximum_hp,
        "armor_class": armor_class,
        "attack_bonus": max(0, level) + strength_mod + attack_feat_bonus,
        "damage_min": damage_min,
        "damage_max": damage_max,
        "critical_threat": critical_threat,
        "critical_multiplier": critical_multiplier,
        "damage_type": damage_type,
        "initiative_bonus": dexterity_mod,
        "level": level,
        "inventory_items": tuple(inventory),
        "scripts": _script_rows(utc, _UTC_SCRIPTS),
    }


def _placeable_projection(utp: Any, tlk_lookup: TLKLookup | None) -> dict[str, Any]:
    maximum_hp = max(1, int(getattr(utp, "maximum_hp", 0) or 0), int(getattr(utp, "current_hp", 0) or 0))
    return {
        "name": localized_text(getattr(utp, "name", None), tlk_lookup),
        "description": localized_text(getattr(utp, "description", None), tlk_lookup),
        "tag": str(getattr(utp, "tag", "") or ""),
        "faction_id": int(getattr(utp, "faction_id", 0) or 0),
        "conversation": _resref(getattr(utp, "conversation", "")),
        "useable": bool(getattr(utp, "useable", False)),
        "static": bool(getattr(utp, "static", False)),
        "plot": bool(getattr(utp, "plot", False)),
        "locked": bool(getattr(utp, "locked", False)),
        "key_required": _resref(getattr(utp, "key_name", "")) if bool(getattr(utp, "key_required", False)) else "",
        "auto_remove_key": bool(getattr(utp, "auto_remove_key", False)),
        "lock_dc": int(getattr(utp, "lock_dc", 0) or 0),
        "has_inventory": bool(getattr(utp, "has_inventory", False)),
        "inventory_items": _inventory_rows(getattr(utp, "inventory", ())),
        "current_hp": max(0, min(maximum_hp, int(getattr(utp, "current_hp", maximum_hp) or maximum_hp))),
        "max_hp": maximum_hp,
        "armor_class": max(1, 10 + int(getattr(utp, "hardness", 0) or 0)),
        "scripts": _script_rows(utp, _UTP_SCRIPTS),
    }


def _door_projection(utd: Any, tlk_lookup: TLKLookup | None) -> dict[str, Any]:
    maximum_hp = max(1, int(getattr(utd, "maximum_hp", 0) or 0), int(getattr(utd, "current_hp", 0) or 0))
    return {
        "name": localized_text(getattr(utd, "name", None), tlk_lookup),
        "description": localized_text(getattr(utd, "description", None), tlk_lookup),
        "tag": str(getattr(utd, "tag", "") or ""),
        "faction_id": int(getattr(utd, "faction_id", 0) or 0),
        "conversation": _resref(getattr(utd, "conversation", "")),
        "plot": bool(getattr(utd, "plot", False)),
        "static": bool(getattr(utd, "static", False)),
        "locked": bool(getattr(utd, "locked", False)),
        "key_required": _resref(getattr(utd, "key_name", "")) if bool(getattr(utd, "key_required", False)) else "",
        "auto_remove_key": bool(getattr(utd, "auto_remove_key", False)),
        "lock_dc": int(getattr(utd, "lock_dc", 0) or 0),
        "open_state": int(getattr(utd, "open_state", 0) or 0),
        "current_hp": max(0, min(maximum_hp, int(getattr(utd, "current_hp", maximum_hp) or maximum_hp))),
        "max_hp": maximum_hp,
        "armor_class": max(1, 10 + int(getattr(utd, "hardness", 0) or 0)),
        "scripts": _script_rows(utd, _UTD_SCRIPTS),
    }


def _trigger_projection(utt: Any, tlk_lookup: TLKLookup | None) -> dict[str, Any]:
    return {
        "name": localized_text(getattr(utt, "name", None), tlk_lookup),
        "tag": str(getattr(utt, "tag", "") or ""),
        "faction_id": int(getattr(utt, "faction_id", 0) or 0),
        "trap_one_shot": bool(getattr(utt, "trap_once", False)),
        "trap_type": int(getattr(utt, "trap_type", 0) or 0),
        "scripts": _script_rows(
            utt,
            ("on_click", "on_disarm", "on_enter", "on_exit", "on_heartbeat", "on_trap_triggered", "on_user_defined"),
        ),
    }


def _store_projection(utm: Any, tlk_lookup: TLKLookup | None) -> dict[str, Any]:
    return {
        "name": localized_text(getattr(utm, "name", None), tlk_lookup),
        "tag": str(getattr(utm, "tag", "") or ""),
        "can_buy": bool(getattr(utm, "can_buy", False)),
        "can_sell": bool(getattr(utm, "can_sell", False)),
        "mark_up": int(getattr(utm, "mark_up", 0) or 0),
        "mark_down": int(getattr(utm, "mark_down", 0) or 0),
        "inventory_items": _inventory_rows(getattr(utm, "inventory", ())),
        "scripts": _script_rows(utm, ("on_open",)),
    }


def _item_projection(uti: Any, tlk_lookup: TLKLookup | None) -> dict[str, Any]:
    return {
        "name": localized_text(getattr(uti, "name", None), tlk_lookup),
        "description": localized_text(getattr(uti, "description", None), tlk_lookup),
        "tag": str(getattr(uti, "tag", "") or ""),
        "base_item": int(getattr(uti, "base_item", 0) or 0),
        "cost": max(0, int(getattr(uti, "cost", 0) or 0) + int(getattr(uti, "add_cost", 0) or 0)),
        "stack_size": max(1, int(getattr(uti, "stack_size", 1) or 1)),
        "charges": max(0, int(getattr(uti, "charges", 0) or 0)),
        "plot": bool(getattr(uti, "plot", False)),
    }


def inspect_map_studio_pie_resource(
    kind: str,
    resref: str,
    data: bytes,
    *,
    tlk_lookup: TLKLookup | None = None,
    weapon_damage_resolver: Any = None,
    armor_ac_resolver: Any = None,
    weapon_critical_resolver: Any = None,
    weapon_damage_type_resolver: Any = None,
    weapon_feat_category_resolver: Any = None,
) -> dict[str, Any]:
    """Decode and project one supported KOTOR resource for PIE."""

    clean_kind = str(kind or "").strip().lower()
    payload = bytes(data or b"")
    if not payload:
        raise ValueError(f"{clean_kind or 'resource'} {resref} has no bytes")
    if clean_kind in {"creature", "utc"}:
        from pykotor.resource.generics.utc import read_utc

        result = _creature_projection(
            read_utc(payload),
            tlk_lookup,
            weapon_damage_resolver=weapon_damage_resolver,
            armor_ac_resolver=armor_ac_resolver,
            weapon_critical_resolver=weapon_critical_resolver,
            weapon_damage_type_resolver=weapon_damage_type_resolver,
            weapon_feat_category_resolver=weapon_feat_category_resolver,
        )
    elif clean_kind in {"placeable", "utp"}:
        from pykotor.resource.generics.utp import read_utp

        result = _placeable_projection(read_utp(payload), tlk_lookup)
    elif clean_kind in {"door", "utd"}:
        from pykotor.resource.generics.utd import read_utd

        result = _door_projection(read_utd(payload), tlk_lookup)
    elif clean_kind in {"trigger", "utt"}:
        from pykotor.resource.generics.utt import read_utt

        result = _trigger_projection(read_utt(payload), tlk_lookup)
    elif clean_kind in {"store", "utm"}:
        from pykotor.resource.generics.utm import read_utm

        result = _store_projection(read_utm(payload), tlk_lookup)
    elif clean_kind in {"item", "uti"}:
        from pykotor.resource.generics.uti import read_uti

        result = _item_projection(read_uti(payload), tlk_lookup)
    else:
        raise ValueError(f"Unsupported PIE resource kind: {kind}")
    result["resref"] = _resref(resref)
    result["kind"] = clean_kind
    return result


__all__ = [
    "TLKLookup",
    "inspect_map_studio_pie_resource",
    "localized_text",
]
