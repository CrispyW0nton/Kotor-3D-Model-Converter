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
_BODY_MODEL_COLUMN_PATTERN = re.compile(r"^model[a-z]$")
_DETACHABLE_HEAD_NAME_PATTERN = re.compile(r"^(?:p[fm]h[a-z0-9_]+|c_twohead)$")
_PLAYER_BODY_NAME_PATTERN = re.compile(r"^p[fm]b[a-n](?:[lms])?$")
_GAME_TAGS = ("K1", "K2")


@dataclass(frozen=True)
class BasCatalogEntry:
    """One attachable game model for a BAS slot."""

    label: str
    resref: str
    games: tuple[str, ...] = ()
    game: str = ""
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


def _available_models_by_game(rows: list[tuple[str, str]]) -> dict[str, set[str]]:
    available = {game: set() for game in _GAME_TAGS}
    for resref, game in rows:
        if resref and game in available:
            available[game].add(resref)
    return available


def _read_twoda(manager: Any, resref: str, game: str):
    try:
        from src.core.assets.resource_manager import RES_2DA
        from src.core.templates.twoda import TwoDA
    except Exception:
        return None
    try:
        data = manager.get_strict(resref, RES_2DA, game)
    except Exception:
        data = None
    if not data:
        return None
    try:
        return TwoDA.from_bytes(data, resref)
    except Exception:
        log.debug("BAS catalog: %s.2da parse failed for %s", resref, game, exc_info=True)
        return None


def _clean_table_resref(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "" if text in {"", "****", "none", "null"} else text


def _strict_texture_exists(manager: Any, texture: str, game: str) -> bool:
    """Return whether *texture* exists in the explicitly selected game.

    Body-slot MDLs occasionally carry an engine placeholder texture.  BAS
    must not let the ResourceManager's legacy cross-game fallback hide that
    condition, because the replacement must travel with the selected K1/K2
    body into composed exports.
    """

    name = _clean_table_resref(texture)
    tag = str(game or "").strip().upper()
    if not name or tag not in _GAME_TAGS or manager is None:
        return False
    try:
        from src.core.assets.resource_manager import RES_TGA, RES_TPC

        return bool(
            manager.get_strict(name, RES_TPC, tag)
            or manager.get_strict(name, RES_TGA, tag)
        )
    except Exception:
        return False


def repair_bas_body_texture_references(
    model: Any,
    *,
    manager: Any,
    game: str,
    resref: str,
) -> dict[str, str]:
    """Repair unresolved skin textures on a catalog-selected body model.

    A small number of shipped headless-body templates (notably K2 ``PMBD``)
    reference an authoring placeholder such as ``PMBMV_01`` that is absent
    from both games.  The game normally supplies the body-slot texture from
    appearance/item state; selecting the bare MDL in BAS has no UTC/UTI row
    from which to obtain that override.  Use the installed conventional
    ``<body-resref>01`` texture only when the authored skin texture cannot be
    resolved in the selected game.  Valid authored textures are never
    replaced.

    The loaded model is a fresh ResourceManager parse, so updating its skin
    material fields is isolated to this BAS build and is intentionally kept in
    the composed MDL/OBJ/FBX output.  The returned mapping is
    ``{missing_texture: replacement_texture}`` for diagnostics/tests.
    """

    tag = str(game or "").strip().upper()
    body = str(resref or "").strip().lower()
    if model is None or manager is None or tag not in _GAME_TAGS or not body:
        return {}

    candidates: list[str] = [f"{body}01"]
    size_match = re.fullmatch(r"(p[fm]b[a-n])[lms]", body)
    if size_match:
        candidates.append(f"{size_match.group(1)}01")
    replacement = next(
        (candidate for candidate in candidates if _strict_texture_exists(manager, candidate, tag)),
        "",
    )
    if not replacement:
        return {}

    try:
        nodes = list(model.all_nodes())
    except Exception:
        nodes = list(getattr(model, "nodes", []) or [])

    repairs: dict[str, str] = {}
    for node in nodes:
        if not bool(getattr(node, "is_skin", False)):
            continue
        if not list(getattr(node, "vertices", []) or []):
            continue
        current = _clean_table_resref(getattr(node, "texture", ""))
        if current and _strict_texture_exists(manager, current, tag):
            continue
        setattr(node, "texture", replacement)
        texture_names = list(getattr(node, "texture_names", []) or [])
        if texture_names:
            texture_names[0] = replacement
        else:
            texture_names = [replacement]
        setattr(node, "texture_names", texture_names)
        if hasattr(node, "tex_count"):
            setattr(node, "tex_count", max(1, int(getattr(node, "tex_count", 0) or 0)))
        repairs[current or "<empty>"] = replacement

    if repairs:
        setattr(model, "_gr_bas_texture_repairs", dict(repairs))
        log.info(
            "BAS body texture repair for %s:%s: %s",
            tag,
            body,
            repairs,
        )
    return repairs


def _head_entries(
    manager: Any,
    available_models: dict[str, set[str]],
) -> tuple[BasCatalogEntry, ...]:
    """Return every installed detachable head, preserving K1/K2 provenance."""

    entries: list[BasCatalogEntry] = []
    for game in _GAME_TAGS:
        table = _read_twoda(manager, "heads", game)
        if table is None:
            continue
        seen: set[str] = set()
        for row in table:
            head = _clean_table_resref(row.get("head", ""))
            if not head or head in seen or head not in available_models.get(game, set()):
                continue
            seen.add(head)
            entries.append(
                BasCatalogEntry(
                    label=f"Head {head}",
                    resref=head,
                    games=(game,),
                    game=game,
                )
            )
        # A few shipped player-head variations and c_twohead are valid,
        # detachable HEAD models but are not referenced by stock heads.2da.
        # The narrow Odyssey naming contract includes them without scanning all
        # 6,000+ installed MDLs synchronously when the panel first opens.
        for head in sorted(available_models.get(game, set())):
            if head in seen or not _DETACHABLE_HEAD_NAME_PATTERN.fullmatch(head):
                continue
            seen.add(head)
            entries.append(
                BasCatalogEntry(
                    label=f"Head {head}",
                    resref=head,
                    games=(game,),
                    game=game,
                )
            )
    return tuple(sorted(entries, key=lambda entry: (entry.resref, entry.game)))


def _headless_body_entries(
    manager: Any,
    available_models: dict[str, set[str]],
) -> tuple[BasCatalogEntry, ...]:
    """Return installed ``appearance.2da`` modeltype-B body models.

    Odyssey composes ``modeltype=B`` appearances from one of the armor/body
    columns plus a detachable ``heads.2da`` head.  Reading those tables avoids
    parsing thousands of unrelated MDLs when the BAS panel opens, while the
    installed-model intersection removes stale cross-game table references.
    """

    entries: list[BasCatalogEntry] = []
    for game in _GAME_TAGS:
        table = _read_twoda(manager, "appearance", game)
        if table is None:
            continue
        model_columns = [
            column
            for column in table.columns
            if _BODY_MODEL_COLUMN_PATTERN.fullmatch(str(column or "").strip().lower())
        ]
        seen: set[str] = set()
        for row in table:
            if str(row.get("modeltype", "") or "").strip().upper() != "B":
                continue
            for column in model_columns:
                body = _clean_table_resref(row.get(column, ""))
                if not body or body in seen or body not in available_models.get(game, set()):
                    continue
                seen.add(body)
                entries.append(
                    BasCatalogEntry(
                        label=f"Body {body}",
                        resref=body,
                        games=(game,),
                        game=game,
                    )
                )
        # Some shipped player armor/size variants are real headless body MDLs
        # even though no stock appearance row currently selects them.  Their
        # p[f/m]b<armor> naming is an Odyssey engine convention; keep the
        # fallback deliberately narrow so creatures/full-body models stay out.
        for body in sorted(available_models.get(game, set())):
            if body in seen or not _PLAYER_BODY_NAME_PATTERN.fullmatch(body):
                continue
            seen.add(body)
            entries.append(
                BasCatalogEntry(
                    label=f"Body {body}",
                    resref=body,
                    games=(game,),
                    game=game,
                )
            )
    return tuple(sorted(entries, key=lambda entry: (entry.resref, entry.game)))


def build_bas_attachment_catalog(manager: Any) -> BasAttachmentCatalog:
    """Enumerate attachable items for every BAS slot from installed games."""

    if manager is None:
        return BasAttachmentCatalog()
    classified_models = _classified_models(manager)
    available_models = _available_models_by_game(classified_models)
    weapons: dict[str, set[str]] = {}
    masks: dict[str, set[str]] = {}
    belts: dict[str, set[str]] = {}
    for name, game in classified_models:
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
            game=next(iter(games)) if len(games) == 1 else "",
            family=family,
            color=color,
        )

    def _sorted(entries: list[BasCatalogEntry]) -> tuple[BasCatalogEntry, ...]:
        return tuple(sorted(entries, key=lambda entry: (entry.family or entry.resref, entry.resref)))

    weapon_entries = _sorted([_weapon_entry(resref, games) for resref, games in weapons.items()])
    mask_entries = _sorted(
        [BasCatalogEntry(label=_item_label("i_mask", resref), resref=resref, games=tuple(sorted(games)), game=next(iter(games)) if len(games) == 1 else "", family="i_mask") for resref, games in masks.items()]
    )
    belt_entries = _sorted(
        [BasCatalogEntry(label=_item_label("i_belt", resref), resref=resref, games=tuple(sorted(games)), game=next(iter(games)) if len(games) == 1 else "", family="i_belt") for resref, games in belts.items()]
    )
    head_entries = _head_entries(manager, available_models)
    body_entries = _headless_body_entries(manager, available_models)

    return BasAttachmentCatalog(
        entries_by_slot={
            "body": body_entries,
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
    "repair_bas_body_texture_references",
    "saber_color_label",
    "saber_color_variants",
    "saber_family",
    "saber_variant_resref",
    "saber_variation",
]
