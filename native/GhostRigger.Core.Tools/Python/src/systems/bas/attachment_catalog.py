"""Game-derived Body Attachment System item catalog.

Enumerates every attachable item model from the installed KOTOR 1 and
KOTOR 2 resources so BAS slots list real game content instead of a small
hardcoded preset, and maps lightsaber model variations to blade colors.

The saber variation -> color tables were derived empirically on 2026-07-12
by loading every ``w_lghtsbr``/``w_shortsbr``/``w_dblsbr`` variation from
both installed games and reading the blade texture each references
(``w_lsabreblue01`` etc.).  ``w_lghtsbr_006`` is the unique red hilt
(Malak's saber), which shifts the full-size family's gold/cyan entries to
007/008; the short and double families have no unique-hilt slot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

SABER_FAMILY_LABELS: dict[str, str] = {
    "w_lghtsbr": "Lightsaber",
    "w_shortsbr": "Short Lightsaber",
    "w_dblsbr": "Double-Bladed Lightsaber",
}

# Blade colors by model variation, verified against the installed games.
_LGHTSBR_COLORS: dict[int, str] = {
    1: "Blue", 2: "Red", 3: "Green", 4: "Yellow", 5: "Violet",
    6: "Red (Malak)", 7: "Gold", 8: "Cyan", 9: "Viridian", 10: "Silver", 11: "Bronze",
}
_SHORT_DBL_COLORS: dict[int, str] = {
    1: "Blue", 2: "Red", 3: "Green", 4: "Yellow", 5: "Violet",
    6: "Gold", 7: "Cyan", 8: "Viridian", 9: "Silver", 10: "Bronze",
}
SABER_VARIATION_COLORS: dict[str, dict[int, str]] = {
    "w_lghtsbr": _LGHTSBR_COLORS,
    "w_shortsbr": _SHORT_DBL_COLORS,
    "w_dblsbr": _SHORT_DBL_COLORS,
}

WEAPON_FAMILY_LABELS: dict[str, str] = {
    **SABER_FAMILY_LABELS,
    "w_vbroswrd": "Vibrosword",
    "w_vbroshort": "Vibroblade",
    "w_vbrdblswd": "Vibro Double-Blade",
    "w_blstrpstl": "Blaster Pistol",
    "w_blstrrfl": "Blaster Rifle",
    "w_blstrcrbn": "Blaster Carbine",
    "w_hvyblstr": "Heavy Blaster",
    "w_hldoblst": "Hold-Out Blaster",
    "w_ionblstr": "Ion Blaster",
    "w_ionrfl": "Ion Rifle",
    "w_dsrptpstl": "Disruptor Pistol",
    "w_dsrptrfl": "Disruptor Rifle",
    "w_sonicpstl": "Sonic Pistol",
    "w_sonicrfl": "Sonic Rifle",
    "w_bowcstr": "Bowcaster",
    "w_rptnblstr": "Repeating Blaster",
    "w_hvrptbltr": "Heavy Repeating Blaster",
    "w_lngswrd": "Long Sword",
    "w_shortswrd": "Short Sword",
    "w_dblswrd": "Double-Bladed Sword",
    "w_qtrstaff": "Quarterstaff",
    "w_stunbaton": "Stun Baton",
    "w_gaffi": "Gaffi Stick",
    "w_waraxe": "War Axe",
    "w_warblade": "War Blade",
    "w_forcepike": "Force Pike",
    "w_fraggren": "Frag Grenade",
    "w_stungren": "Stun Grenade",
    "w_iongren": "Ion Grenade",
    "w_poisngren": "Poison Grenade",
    "w_sonicgren": "Sonic Grenade",
    "w_adhsvgren": "Adhesive Grenade",
    "w_cryobgren": "CryoBan Grenade",
    "w_firegren": "Plasma Grenade",
    "w_flashgren": "Flash Grenade",
    "w_thermdet": "Thermal Detonator",
}

# Renderer effect/projectile models that are not holdable items.
_WEAPON_EXCLUDED_FAMILIES = re.compile(r"^w_(laserfire|lfire|null$|notready)")

_VARIATION_PATTERN = re.compile(r"^([a-z0-9_]+?)_(\d{2,3})$")


@dataclass(frozen=True)
class BasCatalogEntry:
    """One attachable game model for a BAS slot."""

    label: str
    resref: str
    games: tuple[str, ...] = ()
    family: str = ""
    color: str = ""

    @property
    def games_label(self) -> str:
        return "+".join(self.games) if self.games else ""


@dataclass(frozen=True)
class BasAttachmentCatalog:
    """Slot -> entries mapping shared by the BAS panels."""

    entries_by_slot: dict[str, tuple[BasCatalogEntry, ...]] = field(default_factory=dict)

    def entries(self, slot: str) -> tuple[BasCatalogEntry, ...]:
        return self.entries_by_slot.get(str(slot or "").strip().lower(), ())

    @property
    def empty(self) -> bool:
        return not any(self.entries_by_slot.values())


def saber_family(resref: str) -> str:
    """Return the saber family prefix for a model resref, or ''."""

    match = _VARIATION_PATTERN.match(str(resref or "").strip().lower())
    if match and match.group(1) in SABER_VARIATION_COLORS:
        return match.group(1)
    return ""


def saber_variation(resref: str) -> int:
    match = _VARIATION_PATTERN.match(str(resref or "").strip().lower())
    if match and match.group(1) in SABER_VARIATION_COLORS:
        return int(match.group(2))
    return 0


def saber_color_label(resref: str) -> str:
    family = saber_family(resref)
    if not family:
        return ""
    return SABER_VARIATION_COLORS[family].get(saber_variation(resref), "")


def saber_variant_resref(family: str, variation: int) -> str:
    return f"{family}_{int(variation):03d}"


def _weapon_label(family: str, variation: int, color: str) -> str:
    base = WEAPON_FAMILY_LABELS.get(family)
    if base is None:
        base = family[2:].replace("_", " ").title() if family.startswith("w_") else family.title()
    if color:
        return f"{base} ({color})"
    if variation > 1:
        return f"{base} {variation:03d}"
    return base


def _item_label(prefix: str, resref: str) -> str:
    suffix = resref[len(prefix) + 1 :] if resref.startswith(prefix + "_") else resref
    pretty = suffix.replace("_", " ").strip().title() or resref
    base = "Mask" if prefix == "i_mask" else "Belt"
    return f"{base} {pretty}"


def _classified_models(manager: Any) -> list[tuple[str, str]]:
    try:
        rows = list(manager.list_models("all") or ())
    except Exception:
        log.debug("BAS catalog: resource manager cannot list models", exc_info=True)
        return []
    return [(str(name or "").strip().lower(), str(game or "").strip().upper()) for name, game in rows]


def _head_entries(manager: Any) -> tuple[BasCatalogEntry, ...]:
    """Read heads.2da from each installed game for the authoritative head list."""

    heads: dict[str, set[str]] = {}
    try:
        from src.core.assets.resource_manager import RES_2DA
        from src.core.templates.twoda import TwoDA
    except Exception:
        return ()
    for game in ("K1", "K2"):
        try:
            data = manager.get_strict("heads", RES_2DA, game)
        except Exception:
            data = None
        if not data:
            continue
        try:
            table = TwoDA.from_bytes(data, "heads")
        except Exception:
            log.debug("BAS catalog: heads.2da parse failed for %s", game, exc_info=True)
            continue
        for row in table:
            head = str(row.get("head", "") or "").strip().lower()
            if head and head != TwoDA.BLANK.lower():
                heads.setdefault(head, set()).add(game)
    entries = [
        BasCatalogEntry(
            label=f"Head {resref}",
            resref=resref,
            games=tuple(sorted(games)),
        )
        for resref, games in heads.items()
    ]
    return tuple(sorted(entries, key=lambda entry: entry.resref))


def build_bas_attachment_catalog(manager: Any) -> BasAttachmentCatalog:
    """Enumerate attachable items for every BAS slot from installed games."""

    if manager is None:
        return BasAttachmentCatalog()
    weapons: dict[str, set[str]] = {}
    masks: dict[str, set[str]] = {}
    belts: dict[str, set[str]] = {}
    for name, game in _classified_models(manager):
        if not name or not game:
            continue
        if name.startswith("w_"):
            if _WEAPON_EXCLUDED_FAMILIES.match(name):
                continue
            weapons.setdefault(name, set()).add(game)
        elif name.startswith("i_mask_"):
            masks.setdefault(name, set()).add(game)
        elif name.startswith("i_belt_"):
            belts.setdefault(name, set()).add(game)

    def _weapon_entry(resref: str, games: set[str]) -> BasCatalogEntry:
        match = _VARIATION_PATTERN.match(resref)
        family = match.group(1) if match else resref
        variation = int(match.group(2)) if match else 0
        color = SABER_VARIATION_COLORS.get(family, {}).get(variation, "") if family in SABER_VARIATION_COLORS else ""
        return BasCatalogEntry(
            label=_weapon_label(family, variation, color),
            resref=resref,
            games=tuple(sorted(games)),
            family=family,
            color=color,
        )

    def _sorted(entries: list[BasCatalogEntry]) -> tuple[BasCatalogEntry, ...]:
        return tuple(sorted(entries, key=lambda entry: (entry.family or entry.resref, entry.resref)))

    weapon_entries = _sorted([_weapon_entry(resref, games) for resref, games in weapons.items()])
    mask_entries = _sorted(
        [BasCatalogEntry(label=_item_label("i_mask", resref), resref=resref, games=tuple(sorted(games)), family="i_mask") for resref, games in masks.items()]
    )
    belt_entries = _sorted(
        [BasCatalogEntry(label=_item_label("i_belt", resref), resref=resref, games=tuple(sorted(games)), family="i_belt") for resref, games in belts.items()]
    )
    head_entries = _head_entries(manager)

    return BasAttachmentCatalog(
        entries_by_slot={
            "head": head_entries,
            "mask": mask_entries,
            "goggles": mask_entries,
            "belt": belt_entries,
            "left_weapon": weapon_entries,
            "right_weapon": weapon_entries,
        }
    )


def saber_color_variants(resref: str, catalog: BasAttachmentCatalog | None, slot: str = "left_weapon") -> tuple[BasCatalogEntry, ...]:
    """Return the color variants available for the resref's saber family.

    When a catalog is provided, only variants that exist in an installed game
    are returned; otherwise the full verified table is offered.
    """

    family = saber_family(resref)
    if not family:
        return ()
    colors = SABER_VARIATION_COLORS[family]
    if catalog is not None and not catalog.empty:
        by_resref = {entry.resref: entry for entry in catalog.entries(slot) if entry.family == family}
        variants = [by_resref[saber_variant_resref(family, variation)] for variation in sorted(colors) if saber_variant_resref(family, variation) in by_resref]
        if variants:
            return tuple(variants)
    return tuple(
        BasCatalogEntry(
            label=_weapon_label(family, variation, color),
            resref=saber_variant_resref(family, variation),
            games=(),
            family=family,
            color=color,
        )
        for variation, color in sorted(colors.items())
    )


__all__ = [
    "BasAttachmentCatalog",
    "BasCatalogEntry",
    "SABER_FAMILY_LABELS",
    "SABER_VARIATION_COLORS",
    "WEAPON_FAMILY_LABELS",
    "build_bas_attachment_catalog",
    "saber_color_label",
    "saber_color_variants",
    "saber_family",
    "saber_variant_resref",
    "saber_variation",
]
