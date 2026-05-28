"""Qt game library panel for the GhostRigger migration."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from PySide6 import QtCore, QtWidgets

from src.core.qt_core.modules.module_categories import get_module_info
from src.gui.qt_lib.assets.qt_theme import icon, heading


_ITEM_PREFIXES = (
    "iw_", "ia_", "g_w_", "g_i_", "g_a_", "g1_", "g2_", "g3_",
    "uti_", "lbl_", "lbn_",
)

MODEL_CATEGORY_ORDER = (
    "Player Characters",
    "Party Members",
    "Commoners",
    "NPCs",
    "Droids",
    "Turrets",
    "Creatures",
    "Holograms",
    "Supermodels",
    "Modules",
    "Level Assets",
    "Environment",
    "Skyboxes",
    "Minigame",
    "Menus",
    "GUI",
    "Placeables",
    "Doors",
    "Engine Items",
    "Armor",
    "Inventory",
    "Weapons",
    "Item/Armor/Weapons",
    "Visual FX",
    "Visuals",
    "Planets",
    "Misc Models",
    "Stunts",
    "Uncategorised",
    "Other",
    "Templates",
)

MODEL_SUBCATEGORY_ORDER = {
    "Inventory": (
        "Security Spikes",
        "Computer Spikes",
        "Parts",
        "Mines",
        "Spikes",
        "Traps",
        "Medkits",
        "Masks",
        "Implants",
        "Gauntlets",
        "Armbands",
        "Droid Items",
        "Belts",
        "Stims",
        "Adrenal Stims",
        "Combat Shots",
        "Credits",
        "Upgrades",
        "Datapads",
        "Pazaak",
        "Quest Items",
        "Misc Items",
    ),
    "Weapons": (
        "Grenades",
        "Lightsabers",
        "Double-Bladed Lightsabers",
        "Short Lightsabers",
        "Lightsaber Crystals",
        "Vibroblades",
        "Double-Bladed Melee",
        "Blasters",
        "Heavy Blasters",
        "Blaster Rifles",
        "Heavy Weapons",
        "Creature Weapons",
        "Single-Handed Melee",
        "Two-Handed Weapons",
        "Misc Weapons",
    ),
    "Armor": (
        "Clothing",
        "Jedi Robes",
        "Light Armor",
        "Medium Armor",
        "Heavy Armor",
        "Environmental Suits",
        "Disguises",
        "Misc Armor",
    ),
    "Placeables": (
        "Containers",
        "Computers & Panels",
        "Doors & Transitions",
        "Furniture",
        "Lights & VFX",
        "Traps & Hazards",
        "Environmental Props",
        "Misc Placeables",
    ),
    "Doors": (
        "Taris",
        "Dantooine",
        "Tatooine",
        "Kashyyyk",
        "Manaan",
        "Korriban",
        "Leviathan",
        "Star Forge",
        "Rakata",
        "Yavin",
        "Endar Spire",
        "Ebon Hawk",
        "Peragus",
        "Telos",
        "Harbinger",
        "Nar Shaddaa",
        "Dxun",
        "Onderon",
        "Malachor",
        "Ravager",
        "Droid Planet",
        "Force Fields",
        "Generic Doors",
        "Unknown Doors",
    ),
}

_PARTY_MEMBER_NAMES = {
    "bastila", "carth", "mission", "zaalbar", "canderous", "jolee", "juhani",
    "hk47", "t3m4", "kreia", "atton", "mical", "disciple", "bao", "baodur",
    "visas", "hanharr", "handmaiden", "mandalore", "mandra", "g0t0", "goto",
    "mira",
}

_DROID_TOKENS = ("drd", "droid", "hk47", "t3m4", "t3m3", "g0t0", "goto", "warbot", "wardroid")
_PLAYER_BODY_PREFIXES = ("pmb", "pmh", "pmc", "pmf", "pfb", "pfh", "pfc", "pff")
_MISC_MODEL_PREFIXES = ("twilek_", "sith_", "rep_", "old_")
_MISC_MODEL_NAMES = {"watersuit", "spacesuit"}
_PARTY_MODEL_NAMES = {"p_candh03", "p_candh", "p_candbb", "p_candba", "p_atrisbb"}
_COMMONER_MODEL_NAMES = {"child_f", "child_m", "czerka_com_h"}
_ENVIRONMENT_MODEL_NAMES = {"tree_base"}
_ENGINE_ITEM_NAMES = {
    "spawnpoint", "sol_start", "shirt_003", "shirt_002", "shirt_001",
    "plcaa", "mydoor", "mydoor2", "c_emsphere", "c_emcube", "c_embsphere", "c_embcube",
}
_VISUAL_FX_NAMES = {"fxmuzzle"}
_DROID_MODEL_NAMES = {"l_astro02", "l_atromech"}
_SKYBOX_MODEL_NAMES = {"skyboxbase"}
_GUI_MODEL_NAMES = {"maingui"}
_LEVEL_ASSET_NAMES = {
    "l_alien01", "l_alien02", "l_alien03", "l_alien05", "l_commf", "l_commfb",
    "l_commm", "l_commmb", "l_gammorean", "l_jawa", "l_rakata", "l_repofff",
    "l_repoffm", "l_selkath", "l_sithhoff_f", "l_sithoff_m", "l_sithsoldier",
    "l_twilekf", "l_twilekm", "l_wookie", "l_wookief",
}

_RES_UTI = 2025
_RES_UTD = 2042
_RES_UTP = 2044

_BASEITEM_CATEGORIES = {
    **{baseitem: "Weapons" for baseitem in range(0, 35)},
    **{baseitem: "Armor" for baseitem in range(35, 44)},
    **{baseitem: "Inventory" for baseitem in range(44, 77)},
    **{baseitem: "Weapons" for baseitem in range(77, 84)},
    84: "Inventory",
    85: "Armor",
    86: "Inventory",
    87: "Inventory",
    88: "Inventory",
    89: "Armor",
    90: "Armor",
    91: "Inventory",
    92: "Weapons",
    93: "Weapons",
    94: "Inventory",
    95: "Inventory",
    96: "Inventory",
    98: "Armor",
    100: "Armor",
    101: "Armor",
    102: "Armor",
    103: "Armor",
}

_BASEITEM_SUBCATEGORIES = {
    0: "Two-Handed Weapons",
    1: "Single-Handed Melee",
    2: "Single-Handed Melee",
    3: "Vibroblades",
    4: "Single-Handed Melee",
    5: "Vibroblades",
    6: "Double-Bladed Melee",
    7: "Double-Bladed Melee",
    8: "Lightsabers",
    9: "Double-Bladed Lightsabers",
    10: "Short Lightsabers",
    11: "Lightsaber Crystals",
    12: "Blasters",
    13: "Heavy Blasters",
    14: "Heavy Blasters",
    15: "Blasters",
    16: "Blasters",
    17: "Blasters",
    18: "Blaster Rifles",
    19: "Blaster Rifles",
    20: "Blaster Rifles",
    21: "Blaster Rifles",
    22: "Blaster Rifles",
    23: "Blaster Rifles",
    24: "Heavy Weapons",
    25: "Grenades",
    26: "Grenades",
    27: "Grenades",
    28: "Grenades",
    29: "Grenades",
    30: "Grenades",
    31: "Grenades",
    32: "Grenades",
    33: "Grenades",
    34: "Grenades",
    35: "Jedi Robes",
    36: "Jedi Robes",
    37: "Jedi Robes",
    38: "Light Armor",
    39: "Light Armor",
    40: "Medium Armor",
    41: "Medium Armor",
    42: "Heavy Armor",
    43: "Heavy Armor",
    44: "Masks",
    45: "Gauntlets",
    46: "Armbands",
    47: "Belts",
    48: "Implants",
    49: "Implants",
    50: "Implants",
    53: "Stims",
    54: "Combat Shots",
    55: "Medkits",
    56: "Droid Items",
    57: "Credits",
    58: "Mines",
    59: "Security Spikes",
    60: "Computer Spikes",
    61: "Misc Items",
    62: "Misc Items",
    63: "Misc Items",
    64: "Upgrades",
    65: "Pazaak",
    66: "Droid Items",
    67: "Droid Items",
    68: "Droid Items",
    69: "Droid Items",
    70: "Droid Items",
    71: "Droid Items",
    72: "Droid Items",
    73: "Droid Items",
    74: "Droid Items",
    75: "Droid Items",
    76: "Droid Items",
    77: "Blaster Rifles",
    78: "Two-Handed Weapons",
    79: "Single-Handed Melee",
    80: "Single-Handed Melee",
    81: "Creature Weapons",
    82: "Creature Weapons",
    83: "Creature Weapons",
    84: "Misc Items",
    85: "Clothing",
    86: "Pazaak",
    87: "Pazaak",
    88: "Belts",
    89: "Jedi Robes",
    90: "Disguises",
    91: "Medkits",
    92: "Heavy Weapons",
    93: "Single-Handed Melee",
    94: "Medkits",
    95: "Quest Items",
    96: "Quest Items",
    98: "Environmental Suits",
    100: "Clothing",
    101: "Environmental Suits",
    102: "Jedi Robes",
    103: "Disguises",
}

_DOOR_TOKEN_SUBCATEGORIES = (
    (("taris", "tar_", "lta", "lts"), "Taris"),
    (("dantooine", "dan", "lda"), "Dantooine"),
    (("tatooine", "tat"), "Tatooine"),
    (("kashyyyk", "kash", "lka"), "Kashyyyk"),
    (("manaan", "lma"), "Manaan"),
    (("korriban", "kor", "kban", "lko"), "Korriban"),
    (("leviathan", "lza"), "Leviathan"),
    (("starforge", "star_forge", "lsf"), "Star Forge"),
    (("rakata", "rakatan", "lrk"), "Rakata"),
    (("yavin", "lyv"), "Yavin"),
    (("endar", "spier", "spire", "lhr"), "Endar Spire"),
    (("ebon", "hawk", "eh1"), "Ebon Hawk"),
    (("peragus", "per"), "Peragus"),
    (("telos", "tel"), "Telos"),
    (("harbinger", "har"), "Harbinger"),
    (("narshaddaa", "nar_shaddaa", "narshad", "nar"), "Nar Shaddaa"),
    (("dxun", "dxn"), "Dxun"),
    (("onderon", "ond"), "Onderon"),
    (("malachor", "mal"), "Malachor"),
    (("ravager", "nih"), "Ravager"),
    (("droidplanet", "droid_planet", "droid", "dro"), "Droid Planet"),
    (("ffield", "forcefield", "force_field"), "Force Fields"),
)


def _looks_like_minigame(resref: str) -> bool:
    return resref.startswith(("mgf", "mgb", "mg_", "mg"))


def _category_sort_key(category: str) -> tuple[int, str]:
    try:
        return (MODEL_CATEGORY_ORDER.index(category), category)
    except ValueError:
        return (len(MODEL_CATEGORY_ORDER), category)


def _looks_like_party_member(resref: str) -> bool:
    return any(token in resref for token in _PARTY_MEMBER_NAMES)


def _looks_like_droid(resref: str) -> bool:
    return any(token in resref for token in _DROID_TOKENS)


def infer_model_category(resref: str, model_class: str = "") -> str:
    """Return the library tab category for a model row."""
    r = (resref or "").lower()
    cls = (model_class or "").lower()
    if r.startswith("gr_"):
        return "Templates"
    if cls == "tile":
        return "Modules"
    if r in _ENGINE_ITEM_NAMES:
        return "Engine Items"
    if r.startswith("fxc_droid") or r in _VISUAL_FX_NAMES:
        return "Visual FX"
    if r in _PARTY_MODEL_NAMES:
        return "Party Members"
    if r in _COMMONER_MODEL_NAMES:
        return "Commoners"
    if r in _DROID_MODEL_NAMES:
        return "Droids"
    if r in _LEVEL_ASSET_NAMES:
        return "Level Assets"
    if r in _SKYBOX_MODEL_NAMES:
        return "Skyboxes"
    if r in _GUI_MODEL_NAMES:
        return "GUI"
    if _looks_like_minigame(r):
        return "Minigame"
    if r.startswith("mainmenu"):
        return "Menus"
    if r.startswith("stunt"):
        return "Stunts"
    if r in _MISC_MODEL_NAMES or r.startswith(_MISC_MODEL_PREFIXES):
        return "Misc Models"
    if r.startswith("or_") or r in _ENVIRONMENT_MODEL_NAMES:
        return "Environment"
    if r.startswith(("a_robe", "a_jedirobe", "a_light", "a_medium", "a_heavy", "a_class", "g_a_", "d_armor")):
        return "Armor"
    if r.startswith(("gi_", "a_")):
        return "Engine Items"
    if r.startswith("plc_"):
        return "Placeables"
    if r.startswith("dor_"):
        return "Doors"
    if r.startswith("fx_"):
        return "Visual FX"
    if r.startswith("v_"):
        return "Visuals"
    if r.startswith("comm_"):
        return "Commoners"
    if r.startswith("planet_"):
        return "Planets"
    if r.startswith("i_"):
        return "Inventory"
    if r.startswith("w_"):
        return "Weapons"
    if "turret" in r:
        return "Turrets"
    if "holo" in r:
        return "Holograms"
    if _looks_like_droid(r):
        return "Droids"
    if r.startswith(("s_male", "s_female", "s_human")):
        return "Supermodels"
    if r.startswith(_PLAYER_BODY_PREFIXES):
        return "Player Characters"
    if r.startswith("p_") and _looks_like_party_member(r):
        return "Party Members"
    if cls == "character":
        return "Creatures" if r.startswith("c_") else "NPCs"
    if cls in {"item"}:
        return "Inventory"
    if cls == "door":
        return "Doors"
    if cls in {"effect", "effects"}:
        return "Visual FX"
    if cls in {"misc"}:
        return "Uncategorised"
    if r.startswith("c_"):
        return "Creatures"
    if r.startswith(
        (
            "n_", "k_p_", "k_m_", "po_",
            "darkjedi", "malak", "bastila", "trask", "canderous", "revan",
            "jolee", "juhani", "carth", "mission", "zaalbar", "hk47", "g0t0",
            "t3m4", "kreia", "atton", "mical", "bao", "visas", "hanharr",
            "mandra", "darth",
        )
    ):
        return "Party Members" if _looks_like_party_member(r) else "NPCs"
    if _module_info_for_row(resref, "") is not None:
        return "Modules"
    if any(r.startswith(prefix) for prefix in _ITEM_PREFIXES):
        return "Item/Armor/Weapons"
    if r.startswith(
        (
            "ad_", "ai_", "jo_", "bi_", "br_", "bo_", "do_", "dr_", "du_",
            "fr_", "ga_", "go_", "gr_", "gu_", "ha_", "he_", "ho_",
            "hu_", "ja_", "je_", "ki_", "la_", "le_", "li_", "lo_", "ma_",
            "me_", "mi_", "mo_", "mu_", "ni_", "nu_", "pa_", "pi_",
            "qu_", "ra_", "ri_", "ro_", "sa_", "se_", "si_", "sk_", "sl_",
            "sm_", "so_", "sp_", "st_", "su_", "sw_", "ta_", "te_", "ti_",
            "tr_", "tu_", "ul_", "un_", "ur_", "va_", "vi_", "wa_", "wi_",
            "wo_", "ya_", "yo_", "za_", "ze_", "zo_", "zu_",
        )
    ):
        return "NPCs"
    return "Uncategorised"


def _stripped_resource_token(resref: str) -> str:
    r = (resref or "").lower()
    for prefix in ("g_w_", "g_i_", "g_a_", "iw_", "ia_", "w_", "i_", "plc_"):
        if r.startswith(prefix):
            return r[len(prefix):]
    return r


def _metadata_int(metadata: dict[str, Any], key: str) -> Optional[int]:
    value = metadata.get(key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _subcategory_from_item_metadata(metadata: dict[str, Any]) -> str:
    haystack = " ".join(
        str(metadata.get(key, ""))
        for key in (
            "item_template_resref",
            "item_tag",
            "template_resref",
            "tag",
            "resref",
        )
    ).lower()
    baseitem = _metadata_int(metadata, "item_baseitem")
    if "secspike" in haystack:
        return "Security Spikes"
    if "progspike" in haystack:
        return "Computer Spikes"
    if "parts" in haystack:
        return "Parts"
    if any(part in haystack for part in ("parts", "drd", "droid", "repair", "shield")):
        return "Droid Items"
    if any(part in haystack for part in ("mine", "trapkit")):
        return "Mines"
    if "trap" in haystack:
        return "Traps"
    if any(part in haystack for part in ("medpac", "medpack", "medkit", "med_")):
        return "Medkits"
    if "adrnaline" in haystack or "adrenal" in haystack:
        return "Adrenal Stims"
    if "stim" in haystack:
        return "Stims"
    return _BASEITEM_SUBCATEGORIES.get(baseitem, "") if baseitem is not None else ""


def _category_from_item_metadata(metadata: dict[str, Any]) -> str:
    baseitem = _metadata_int(metadata, "item_baseitem")
    if baseitem is not None:
        return _BASEITEM_CATEGORIES.get(baseitem, "")
    return ""


def _subcategory_from_door_metadata(metadata: dict[str, Any]) -> str:
    haystack = " ".join(
        str(metadata.get(key, ""))
        for key in (
            "door_template_resref",
            "door_tag",
            "template_resref",
            "tag",
            "resref",
        )
    ).lower().replace(" ", "")
    for tokens, subcategory in _DOOR_TOKEN_SUBCATEGORIES:
        if any(token in haystack for token in tokens):
            return subcategory
    return ""


def infer_model_subcategory(resref: str, category: str = "", metadata: Optional[dict[str, Any]] = None) -> str:
    """Return a game-style browser subcategory for known item and placeable rows."""
    r = (resref or "").lower()
    token = _stripped_resource_token(r)
    cat = category or infer_model_category(resref)
    if metadata:
        if cat == "Doors":
            metadata_subcategory = _subcategory_from_door_metadata({**metadata, "resref": resref})
            if metadata_subcategory:
                return metadata_subcategory
        metadata_subcategory = _subcategory_from_item_metadata({**metadata, "resref": resref})
        if metadata_subcategory and cat in {"Armor", "Inventory", "Weapons", "Item/Armor/Weapons"}:
            return metadata_subcategory
    if cat == "Inventory":
        if "secspike" in token:
            return "Security Spikes"
        if "progspike" in token:
            return "Computer Spikes"
        if "spike" in token:
            return "Spikes"
        if "parts" in token:
            return "Parts"
        if any(part in token for part in ("trapkit", "mine")):
            return "Mines"
        if "trap" in token:
            return "Traps"
        if any(part in token for part in ("medpac", "medpack", "medkit", "med_")):
            return "Medkits"
        if "mask" in token:
            return "Masks"
        if "implant" in token:
            return "Implants"
        if any(part in token for part in ("gauntlet", "glove")):
            return "Gauntlets"
        if "armband" in token:
            return "Armbands"
        if any(part in token for part in ("drd", "droid", "parts", "prog")):
            return "Droid Items"
        if "belt" in token:
            return "Belts"
        if "stim" in token:
            return "Stims"
        if "adrnaline" in token or "adrenal" in token:
            return "Adrenal Stims"
        if "credit" in token:
            return "Credits"
        if "datapad" in token:
            return "Datapads"
        if "paz" in token:
            return "Pazaak"
        if any(part in token for part in ("upgrade", "chem", "compont", "crystal")):
            return "Upgrades"
        return "Misc Items"
    if cat == "Weapons":
        if any(part in token for part in ("gren", "grenade")):
            return "Grenades"
        if any(part in token for part in ("dblsbr", "double_saber")):
            return "Double-Bladed Lightsabers"
        if any(part in token for part in ("shortsbr", "short_saber")):
            return "Short Lightsabers"
        if "sbrcrstl" in token or "crystal" in token:
            return "Lightsaber Crystals"
        if any(part in token for part in ("lghtsbr", "lightsbr", "saber", "sabre", "sbr")):
            return "Lightsabers"
        if any(part in token for part in ("dblswrd", "vbrdblswd", "double", "staff")):
            return "Double-Bladed Melee"
        if any(part in token for part in ("vbro", "vibro", "shortswrd", "lngswrd", "dblswrd", "sword")):
            return "Vibroblades"
        if any(part in token for part in ("hvyblstr", "hldoblstr")):
            return "Heavy Blasters"
        if any(part in token for part in ("hvrpt", "rocket")):
            return "Heavy Weapons"
        if any(part in token for part in ("blstrrfl", "bowcstr", "rptnblstr", "hvyrptr", "rifle")):
            return "Blaster Rifles"
        if any(part in token for part in ("blstrpstl", "hldoblstr", "pistol", "blaster")):
            return "Blasters"
        if any(part in token for part in ("dbl", "double", "staff", "rfl", "rifle", "bow")):
            return "Two-Handed Weapons"
        if any(part in token for part in ("pstl", "pistol", "short")):
            return "Single-Handed Melee"
        return "Misc Weapons"
    if cat == "Armor":
        if "robe" in token:
            return "Jedi Robes"
        if "light" in token:
            return "Light Armor"
        if "medium" in token:
            return "Medium Armor"
        if "heavy" in token:
            return "Heavy Armor"
        if any(part in token for part in ("env", "space", "under", "suit")):
            return "Environmental Suits"
        if any(part in token for part in ("disguise", "uniform", "sandper")):
            return "Disguises"
        if "cloth" in token:
            return "Clothing"
        return "Misc Armor"
    if cat == "Placeables":
        if any(part in token for part in ("footlker", "locker", "container", "crate", "chest", "box")):
            return "Containers"
        if any(part in token for part in ("comp", "panel", "terminal", "console")):
            return "Computers & Panels"
        if any(part in token for part in ("door", "trans", "elev", "ramp")):
            return "Doors & Transitions"
        if any(part in token for part in ("chair", "table", "desk", "bed", "bench", "shelf")):
            return "Furniture"
        if any(part in token for part in ("light", "lamp", "fx", "fire", "flame", "spark")):
            return "Lights & VFX"
        if any(part in token for part in ("trap", "mine", "gas", "poison", "hazard")):
            return "Traps & Hazards"
        if any(part in token for part in ("rock", "tree", "plant", "sign", "statue", "debris", "barrel")):
            return "Environmental Props"
        return "Misc Placeables"
    if cat == "Doors":
        subcategory = _subcategory_from_door_metadata({"resref": resref})
        if subcategory:
            return subcategory
        if "ukn" in token or "unknown" in token:
            return "Unknown Doors"
        return "Generic Doors"
    return ""


def _subcategory_sort_key(category: str, subcategory: str) -> tuple[int, str]:
    order = MODEL_SUBCATEGORY_ORDER.get(category, ())
    try:
        return (order.index(subcategory), subcategory)
    except ValueError:
        return (len(order), subcategory)


def content_browser_metadata_for_resref(resref: str, category: str) -> dict[str, str]:
    """Return lightweight taxonomy tags for library rows without loading MDLs."""
    r = (resref or "").lower()
    metadata: dict[str, str] = {}
    if category in {
        "Droids", "Turrets", "Creatures", "Holograms", "NPCs", "Party Members",
        "Player Characters", "Supermodels", "Environment", "Placeables", "Doors",
        "Engine Items", "Armor", "Inventory", "Weapons", "Visual FX", "Visuals", "Commoners",
        "Planets", "Misc Models", "Stunts", "Skyboxes", "Minigame", "Menus", "GUI",
        "Level Assets", "Uncategorised",
    }:
        metadata["taxonomy"] = category
    if "holo" in r:
        metadata["variant"] = "Hologram"
    if _looks_like_droid(r):
        metadata["species"] = "Droid"
    if "turret" in r:
        metadata["species"] = "Turret"
    if _looks_like_party_member(r):
        metadata["role"] = "Party Member"
    if category == "Engine Items":
        metadata["role"] = "Engine Marker"
    if category == "Environment":
        metadata["role"] = "Environment Asset"
    if category == "Commoners":
        metadata["role"] = "Commoner"
    subcategory = infer_model_subcategory(resref, category)
    if subcategory:
        metadata["subcategory"] = subcategory
    return metadata


def _module_info_for_row(resref: str, game: str = ""):
    games = [game] if str(game or "").upper() in {"K1", "K2"} else ["K1", "K2"]
    for game_key in games:
        info = get_module_info(resref, game_key)
        if info is not None:
            return info
    return None


def _as_gff_dict(raw: Optional[bytes]) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        from src.core.game.game_library_ext import GFFReader

        parsed = GFFReader.from_bytes(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _template_field_text(gff: dict[str, Any], field: str, fallback: str = "") -> str:
    value = gff.get(field, fallback)
    return str(value or fallback or "").strip()


def _template_model_candidates(template_resref: str, model_variation: Any) -> set[str]:
    template = str(template_resref or "").strip().lower()
    candidates = {template} if template else set()
    if not template:
        return candidates
    stem = template
    for prefix in ("g1_", "g2_", "g3_", "g_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
            candidates.add(stem)
            break
    try:
        variation = int(model_variation)
    except (TypeError, ValueError):
        variation = 0
    match = re.search(r"(\d+)$", stem)
    if match and variation <= 0:
        try:
            variation = int(match.group(1))
        except ValueError:
            variation = 0
    if match and variation > 0:
        suffix_len = len(match.group(1))
        trimmed_len = 3 if suffix_len >= 3 else suffix_len
        base = stem[:-trimmed_len].rstrip("_")
        if base:
            candidates.add(f"{base}_{variation:03d}")
            candidates.add(f"{base}{variation:03d}")
    return {candidate for candidate in candidates if candidate}


def _door_model_candidates(template_resref: str, tag: str = "") -> set[str]:
    values = {
        str(template_resref or "").strip().lower(),
        str(tag or "").strip().lower().replace(" ", "_"),
        str(tag or "").strip().lower().replace(" ", ""),
    }
    candidates = {value for value in values if value}
    for value in list(candidates):
        if value.startswith("door_"):
            stem = value[5:]
            replacements = (
                ("dxun", "dxn"),
                ("droid", "dro"),
                ("narshad", "nar"),
            )
            candidates.add(f"dor_{stem}")
            for old, new in replacements:
                if stem.startswith(old):
                    candidates.add(f"dor_{new}{stem[len(old):]}")
        if value.startswith("sw_door_"):
            candidates.add(value[3:])
    return {candidate for candidate in candidates if candidate}


def _template_metadata_index_for_game(resource_manager: Any, game: str) -> dict[str, dict[str, str]]:
    install = resource_manager.get_k1() if game == "K1" else resource_manager.get_k2()
    if install is None or not hasattr(install, "list_resrefs"):
        return {}
    index: dict[str, dict[str, str]] = {}
    try:
        item_resrefs = install.list_resrefs(_RES_UTI)
    except Exception:
        item_resrefs = []
    for template_resref in item_resrefs:
        gff = _as_gff_dict(resource_manager.get(template_resref, _RES_UTI, game))
        if not gff:
            continue
        model_variation = gff.get("ModelVariation", "")
        baseitem = gff.get("BaseItem", "")
        template = _template_field_text(gff, "TemplateResRef", template_resref).lower()
        metadata = {
            "item_template_resref": template,
            "item_tag": _template_field_text(gff, "Tag", template),
            "item_baseitem": str(baseitem) if baseitem not in ("", None) else "",
            "item_model_variation": str(model_variation) if model_variation not in ("", None) else "",
            "metadata_source": "UTI",
        }
        subcategory = infer_model_subcategory(template, infer_model_category(template), metadata)
        if subcategory:
            metadata["subcategory"] = subcategory
        for candidate in _template_model_candidates(template, model_variation):
            existing = index.get(candidate)
            if existing is None or (metadata.get("subcategory") and not existing.get("subcategory")):
                index[candidate] = dict(metadata)

    try:
        placeable_resrefs = install.list_resrefs(_RES_UTP)
    except Exception:
        placeable_resrefs = []
    for template_resref in placeable_resrefs:
        gff = _as_gff_dict(resource_manager.get(template_resref, _RES_UTP, game))
        if not gff:
            continue
        tag = _template_field_text(gff, "Tag", template_resref)
        template = _template_field_text(gff, "TemplateResRef", template_resref).lower()
        metadata = {
            "placeable_template_resref": template,
            "placeable_tag": tag,
            "placeable_appearance": str(gff.get("Appearance", "")),
            "metadata_source": "UTP",
        }
        subcategory = infer_model_subcategory(tag or template, "Placeables")
        if subcategory:
            metadata["subcategory"] = subcategory
        for candidate in (template, tag.lower()):
            if candidate:
                index.setdefault(candidate, dict(metadata))

    try:
        door_resrefs = install.list_resrefs(_RES_UTD)
    except Exception:
        door_resrefs = []
    for template_resref in door_resrefs:
        gff = _as_gff_dict(resource_manager.get(template_resref, _RES_UTD, game))
        if not gff:
            continue
        tag = _template_field_text(gff, "Tag", template_resref)
        template = _template_field_text(gff, "TemplateResRef", template_resref).lower()
        generic_type = gff.get("GenericType", gff.get("Appearance", ""))
        metadata = {
            "door_template_resref": template,
            "door_tag": tag,
            "door_generic_type": str(generic_type) if generic_type not in ("", None) else "",
            "door_open_lock_dc": str(gff.get("OpenLockDC", "")),
            "door_key_name": _template_field_text(gff, "KeyName", ""),
            "door_linked_to": _template_field_text(gff, "LinkedTo", ""),
            "metadata_source": "UTD",
        }
        subcategory = infer_model_subcategory(tag or template, "Doors", metadata)
        if subcategory:
            metadata["subcategory"] = subcategory
        for candidate in _door_model_candidates(template, tag):
            if candidate:
                index.setdefault(candidate, dict(metadata))
    return index


def enrich_library_rows_with_resource_metadata(rows: list[dict], resource_manager: Any) -> list[dict]:
    """Attach optional UTI/UTP metadata to library model rows from indexed game files."""
    indices: dict[str, dict[str, dict[str, str]]] = {}
    enriched: list[dict] = []
    for row in rows:
        item = dict(row)
        game = str(item.get("game", "")).upper()
        if game in {"K1", "K2"}:
            if game not in indices:
                indices[game] = _template_metadata_index_for_game(resource_manager, game)
            metadata = indices[game].get(str(item.get("resref", "")).lower())
            if metadata:
                item.update({key: value for key, value in metadata.items() if value not in ("", None)})
        enriched.append(item)
    return enriched


def enrich_library_rows(rows: list[dict]) -> list[dict]:
    """Copy rows, add category/area fields, and append built-in templates."""
    enriched: list[dict] = []
    seen = set()
    for row in rows:
        item = dict(row)
        resref = str(item.get("resref", ""))
        game = str(item.get("game", ""))
        module_info = _module_info_for_row(resref, game)
        supplied_category = str(item.get("category", ""))
        metadata_category = _category_from_item_metadata(item)
        item["category"] = (
            "Modules" if module_info is not None
            else metadata_category
            or (supplied_category if supplied_category in MODEL_CATEGORY_ORDER and supplied_category not in {"Character", "Creature"} else "")
            or infer_model_category(resref, str(item.get("model_class", "")))
        )
        subcategory = infer_model_subcategory(resref, str(item.get("category", "")), item)
        if subcategory:
            item["subcategory"] = subcategory
        if module_info is not None:
            item.setdefault("module_code", module_info.module_code)
            item.setdefault("location", module_info.location)
            item.setdefault("area_name", module_info.area_name)
            item.setdefault("area", module_info.location)
            item.setdefault("area_label", module_info.label)
            item.setdefault("location_type", module_info.location_type)
        enriched.append(item)
        seen.add((resref.lower(), game.upper()))

    for game in ("K1", "K2"):
        resref = f"gr_humanoid_{game.lower()}"
        if (resref, game) in seen:
            continue
        enriched.append(
            {
                "game": game,
                "resref": resref,
                "source": "[GhostRigger Built-in]",
                "category": "Templates",
                "template": True,
            }
        )
    enriched.sort(
        key=lambda item: (
            str(item.get("game", "")),
            _category_sort_key(str(item.get("category", ""))),
            _subcategory_sort_key(str(item.get("category", "")), str(item.get("subcategory", ""))),
            str(item.get("resref", "")),
        )
    )
    return enriched


class QtModelListItem(QtWidgets.QListWidgetItem):
    def __init__(self, row: dict):
        label = f"[{row.get('game', '?')}] {row.get('resref', '')}"
        if row.get("area_label"):
            label = f"{label} - {row.get('area_label')}"
        super().__init__(label)
        self.row = row


class QtLibraryPanel(QtWidgets.QWidget):
    loadRequested = QtCore.Signal(str, str)
    extractRequested = QtCore.Signal(dict)
    retargetSourceRequested = QtCore.Signal(dict)
    retargetTargetRequested = QtCore.Signal(dict)
    levelEditorImportRequested = QtCore.Signal(dict)
    batchRequested = QtCore.Signal(str, list)
    scanRequested = QtCore.Signal()
    deepScanRequested = QtCore.Signal()

    CATEGORIES = [
        ("All", "All", "library"),
        ("Player", "Player Characters", "cat_character"),
        ("Party", "Party Members", "cat_character"),
        ("Commoners", "Commoners", "cat_character"),
        ("NPCs", "NPCs", "cat_character"),
        ("Droids", "Droids", "cat_creature"),
        ("Turrets", "Turrets", "cat_creature"),
        ("Creatures", "Creatures", "cat_creature"),
        ("Holograms", "Holograms", "cat_character"),
        ("Supermodels", "Supermodels", "cat_character"),
        ("Modules", "Modules", "cat_module"),
        ("Level Assets", "Level Assets", "cat_other"),
        ("Environment", "Environment", "cat_other"),
        ("Skyboxes", "Skyboxes", "cat_other"),
        ("Minigame", "Minigame", "cat_other"),
        ("Menus", "Menus", "cat_other"),
        ("GUI", "GUI", "cat_other"),
        ("Placeables", "Placeables", "cat_item"),
        ("Doors", "Doors", "cat_other"),
        ("Engine", "Engine Items", "cat_other"),
        ("Inventory", "Inventory", "cat_item"),
        ("Weapons", "Weapons", "cat_item"),
        ("Item/Armor", "Item/Armor/Weapons", "cat_item"),
        ("Visual FX", "Visual FX", "cat_other"),
        ("Visuals", "Visuals", "cat_other"),
        ("Planets", "Planets", "cat_module"),
        ("Misc", "Misc Models", "cat_other"),
        ("Stunts", "Stunts", "cat_other"),
        ("Uncategorised", "Uncategorised", "cat_other"),
        ("Other", "Other", "cat_other"),
        ("Templates", "Templates", "skeleton"),
    ]

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._rows: list[dict] = []
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(5)
        root.addWidget(heading("Game Library"))

        filter_row = QtWidgets.QHBoxLayout()
        self.game_filter = QtWidgets.QButtonGroup(self)
        for label in ("All", "K1", "K2"):
            rb = QtWidgets.QRadioButton(label)
            rb.setChecked(label == "All")
            rb.toggled.connect(self._apply_filter)
            self.game_filter.addButton(rb)
            filter_row.addWidget(rb)
        filter_row.addStretch(1)
        root.addLayout(filter_row)

        self.category_tabs = QtWidgets.QTabWidget()
        self.category_tabs.setTabPosition(QtWidgets.QTabWidget.North)
        self.category_tabs.setUsesScrollButtons(True)
        self.category_tabs.setElideMode(QtCore.Qt.ElideRight)
        self.category_tabs.tabBar().setExpanding(False)
        for label, _key, icon_name in self.CATEGORIES:
            self.category_tabs.addTab(QtWidgets.QWidget(), icon(icon_name, 16), label)
        self.category_tabs.currentChanged.connect(self._apply_filter)
        root.addWidget(self.category_tabs, 0)

        self.module_area_combo = QtWidgets.QComboBox()
        self.module_area_combo.addItem("All Areas")
        self.module_area_combo.currentTextChanged.connect(self._apply_filter)
        root.addWidget(self.module_area_combo)
        self.module_area_combo.hide()

        search_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Filter models")
        self.search_edit.textChanged.connect(self._apply_filter)
        clear = QtWidgets.QPushButton("x")
        clear.setProperty("compact", True)
        clear.clicked.connect(self.search_edit.clear)
        search_row.addWidget(self.search_edit)
        search_row.addWidget(clear)
        root.addLayout(search_row)

        self.listbox = QtWidgets.QListWidget()
        self.listbox.itemDoubleClicked.connect(self._load_item)
        self.listbox.itemSelectionChanged.connect(self._update_selection_text)
        self.listbox.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.listbox.customContextMenuRequested.connect(self._show_context_menu)
        root.addWidget(self.listbox, 1)

        self.thumb_label = QtWidgets.QLabel("")
        self.thumb_label.setMinimumHeight(34)
        self.thumb_label.setWordWrap(True)
        root.addWidget(self.thumb_label)

        count_row = QtWidgets.QHBoxLayout()
        self.category_count_label = QtWidgets.QLabel("")
        self.filter_count_label = QtWidgets.QLabel("")
        count_row.addWidget(self.category_count_label)
        count_row.addStretch(1)
        count_row.addWidget(self.filter_count_label)
        root.addLayout(count_row)

        self.status_label = QtWidgets.QLabel("No game directory set")
        root.addWidget(self.status_label)

        action_row = QtWidgets.QHBoxLayout()
        self.load_button = QtWidgets.QPushButton("Load Model")
        self.load_button.setProperty("accent", True)
        self.extract_button = QtWidgets.QPushButton("Extract")
        self.level_button = QtWidgets.QPushButton("Add to Level")
        self.load_button.clicked.connect(self.load_selected)
        self.extract_button.clicked.connect(self.extract_selected)
        self.level_button.clicked.connect(self.import_selected_to_level)
        action_row.addWidget(self.load_button, 1)
        action_row.addWidget(self.extract_button)
        action_row.addWidget(self.level_button)
        root.addLayout(action_row)

        batch_row = QtWidgets.QHBoxLayout()
        for label, fmt in (("Batch OBJ", "obj"), ("Batch ASCII", "ascii"), ("Batch TGA", "tga")):
            button = QtWidgets.QPushButton(label)
            button.setProperty("compact", True)
            button.clicked.connect(lambda _checked=False, f=fmt: self.batchRequested.emit(f, self.visible_rows()))
            batch_row.addWidget(button)
        batch_row.addStretch(1)
        root.addLayout(batch_row)

        scan_row = QtWidgets.QHBoxLayout()
        self.deep_button = QtWidgets.QPushButton("Deep Scan")
        self.scan_button = QtWidgets.QPushButton("Scan")
        self.scan_button.setProperty("accent", True)
        self.deep_button.clicked.connect(self.deepScanRequested.emit)
        self.scan_button.clicked.connect(self.scanRequested.emit)
        scan_row.addStretch(1)
        for button in (self.deep_button, self.scan_button):
            button.setProperty("compact", True)
            scan_row.addWidget(button)
        root.addLayout(scan_row)

    def set_rows(self, rows: list[dict]) -> None:
        self._rows = enrich_library_rows(rows)
        self._rebuild_module_areas()
        self._apply_filter()

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def selected_row(self) -> Optional[dict]:
        item = self.listbox.currentItem()
        return getattr(item, "row", None) if item else None

    def visible_rows(self) -> list[dict]:
        rows = []
        for index in range(self.listbox.count()):
            row = getattr(self.listbox.item(index), "row", None)
            if row:
                rows.append(row)
        return rows

    def load_selected(self) -> None:
        row = self.selected_row()
        if row:
            self.loadRequested.emit(row.get("resref", ""), row.get("game", ""))

    def extract_selected(self) -> None:
        row = self.selected_row()
        if row:
            self.extractRequested.emit(row)

    def import_selected_to_level(self) -> None:
        row = self.selected_row()
        if row:
            self.levelEditorImportRequested.emit(row)

    def _load_item(self, item: QtWidgets.QListWidgetItem) -> None:
        row = getattr(item, "row", None)
        if row:
            self.loadRequested.emit(row.get("resref", ""), row.get("game", ""))

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self.listbox.itemAt(pos)
        if item is not None:
            self.listbox.setCurrentItem(item)
        row = self.selected_row()
        if not row:
            return
        menu = QtWidgets.QMenu(self)
        load_action = menu.addAction("Load Model")
        add_to_level_action = menu.addAction("Add to Level Editor")
        extract_action = menu.addAction("Extract")
        menu.addSeparator()
        source_action = menu.addAction("Send to Retarget Workbench (Source)")
        target_action = menu.addAction("Send to Retarget Workbench (Target)")
        chosen = menu.exec(self.listbox.mapToGlobal(pos))
        if chosen is load_action:
            self.loadRequested.emit(row.get("resref", ""), row.get("game", ""))
        elif chosen is add_to_level_action:
            self.levelEditorImportRequested.emit(row)
        elif chosen is extract_action:
            self.extractRequested.emit(row)
        elif chosen is source_action:
            self.retargetSourceRequested.emit(row)
        elif chosen is target_action:
            self.retargetTargetRequested.emit(row)

    def _current_game_filter(self) -> str:
        checked = self.game_filter.checkedButton()
        return checked.text() if checked else "All"

    def _current_category(self) -> str:
        idx = self.category_tabs.currentIndex()
        if 0 <= idx < len(self.CATEGORIES):
            return self.CATEGORIES[idx][1]
        return "All"

    def _apply_filter(self) -> None:
        if not hasattr(self, "listbox"):
            return
        category = self._current_category()
        self.module_area_combo.setVisible(category == "Modules")
        game_filter = self._current_game_filter()
        needle = self.search_edit.text().lower().strip()
        area_filter = self.module_area_combo.currentText() if category == "Modules" else "All Areas"

        self.listbox.clear()
        count = 0
        counts: dict[str, int] = {}
        for row in self._rows:
            row_cat = row.get("category") or infer_model_category(str(row.get("resref", "")))
            counts[row_cat] = counts.get(row_cat, 0) + 1

        for row in self._rows:
            text = " ".join(
                str(row.get(key, ""))
                for key in ("game", "resref", "module_code", "location", "area_name", "area_label")
            )
            if game_filter != "All" and row.get("game") != game_filter:
                continue
            row_cat = row.get("category") or infer_model_category(str(row.get("resref", "")))
            if category != "All" and row_cat != category:
                continue
            if category == "Modules" and area_filter not in ("", "All Areas") and row.get("area_label") != area_filter:
                continue
            if needle and needle not in text.lower():
                continue
            self.listbox.addItem(QtModelListItem(row))
            count += 1
        if count == 0:
            self.listbox.addItem("No matching models")
        self.filter_count_label.setText(f"{count} shown")
        parts = [f"All: {len(self._rows)}"]
        for label, key, _icon_name in self.CATEGORIES[1:]:
            value = counts.get(key, 0)
            if value:
                parts.append(f"{label}: {value}")
        self.category_count_label.setText("  ".join(parts))

    def _rebuild_module_areas(self) -> None:
        current = self.module_area_combo.currentText()
        self.module_area_combo.clear()
        self.module_area_combo.addItem("All Areas")
        areas = sorted({str(row.get("area_label", "")) for row in self._rows if row.get("area_label")})
        self.module_area_combo.addItems(areas)
        idx = self.module_area_combo.findText(current)
        if idx >= 0:
            self.module_area_combo.setCurrentIndex(idx)

    def _update_selection_text(self) -> None:
        row = self.selected_row()
        if not row:
            self.thumb_label.setText("")
            return
        source = Path(str(row.get("source", ""))).name if row.get("source") else ""
        parts = [str(row.get("resref", "")), str(row.get("game", ""))]
        if row.get("area_label"):
            parts.append(str(row.get("area_label")))
        if source:
            parts.append(source)
        self.thumb_label.setText("  ".join(part for part in parts if part))
