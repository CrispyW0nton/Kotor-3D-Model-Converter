"""Game-library resource palette for authored Map Studio gameplay placement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .authored_module_objects import normalise_resource_resref


_RESTYPE_KIND: dict[str, str] = {
    "utc": "creature",
    "utp": "placeable",
    "utd": "door",
    "utt": "trigger",
    "ute": "encounter",
    "uts": "sound",
    "utm": "store",
    "utw": "waypoint",
}


_CATEGORY_KIND: tuple[tuple[tuple[str, ...], str], ...] = (
    (("creature", "creatures", "npc", "npcs", "commoner", "commoners", "droid", "droids", "turret", "turrets", "party member", "party members"), "creature"),
    (("placeable", "placeables"), "placeable"),
    (("door", "doors"), "door"),
    (("trigger", "triggers"), "trigger"),
    (("encounter", "encounters"), "encounter"),
    (("sound", "sounds"), "sound"),
    (("store", "stores", "merchant", "merchants"), "store"),
    (("waypoint", "waypoints", "engine item", "engine items"), "waypoint"),
)


@dataclass(frozen=True)
class AuthoredGameplayPaletteEntry:
    """Resource option a modder can use to seed an authored GIT placement."""

    kind: str
    template_resref: str
    label: str
    authoring_family: str = ""
    game: str = ""
    category: str = ""
    source: str = ""
    confidence: str = "template"
    warning: str = ""
    metadata: dict[str, Any] | None = None


def _row_value(row: Any, *keys: str) -> str:
    if isinstance(row, dict):
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                return str(value)
    for key in keys:
        value = getattr(row, key, None)
        if value not in (None, ""):
            return str(value)
    return ""


def _resource_type(row: Any) -> str:
    value = _row_value(row, "restype", "resource_type", "type", "extension")
    value = value.lower().strip().lstrip(".")
    if "/" in value:
        value = value.rsplit("/", 1)[-1]
    return value


def _kind_from_category(category: str, subcategory: str = "") -> str:
    haystack = f"{category} {subcategory}".strip().lower()
    for needles, kind in _CATEGORY_KIND:
        if any(needle == haystack or needle in haystack for needle in needles):
            return kind
    return ""


def _kind_from_resref(resref: str) -> str:
    lower = resref.lower()
    if lower.startswith(("c_", "n_")):
        return "creature"
    if lower.startswith(("plc_", "utp_")):
        return "placeable"
    if lower.startswith(("dor_", "door_", "utd_")):
        return "door"
    if lower.startswith(("wp_", "waypoint", "sw_startloc")):
        return "waypoint"
    if lower.startswith(("trg_", "utt_")):
        return "trigger"
    if lower.startswith(("enc_", "ute_")):
        return "encounter"
    if lower.startswith(("snd_", "uts_")):
        return "sound"
    if lower.startswith(("stm_", "utm_")):
        return "store"
    return ""


def authored_gameplay_authoring_family(kind: str) -> str:
    """Return the user-facing authoring family without changing engine kind.

    Doors are animated placeable objects in the level-design workflow, while
    remaining UTD/GIT Door List resources for KOTOR serialization.
    """

    clean = str(kind or "").strip().lower()
    return "placeable" if clean in {"placeable", "door"} else clean


def gameplay_palette_entry_from_library_row(row: Any) -> AuthoredGameplayPaletteEntry | None:
    """Convert one game-library row into a gameplay placement palette entry."""

    restype = _resource_type(row)
    # The startup library is model-oriented.  Its enriched rows retain the
    # true backing UTP/UTD resref; use that authority instead of accidentally
    # placing a visual ``plc_*``/``dor_*`` model name as a GIT template.
    typed_template = ""
    if isinstance(row, dict):
        if row.get("utc_template_resref"):
            typed_template = str(row.get("utc_template_resref") or "")
            restype = "utc"
        elif row.get("door_template_resref"):
            typed_template = str(row.get("door_template_resref") or "")
            restype = "utd"
        elif row.get("placeable_template_resref"):
            typed_template = str(row.get("placeable_template_resref") or "")
            restype = "utp"
    resref = normalise_resource_resref(typed_template or _row_value(row, "template_resref", "resref", "name"))
    if not resref:
        return None
    category = _row_value(row, "category")
    subcategory = _row_value(row, "subcategory")
    game = _row_value(row, "game")
    source = _row_value(row, "source", "path")
    kind = _RESTYPE_KIND.get(restype) or _kind_from_category(category, subcategory) or _kind_from_resref(resref)
    if not kind:
        return None
    confidence = "template" if restype in _RESTYPE_KIND else "model_or_resref"
    if confidence != "template":
        # Geometry models remain useful in the asset browser, but cannot seed a
        # runtime GIT row until a real UTC/UTP/UTD/etc. template identity is
        # known.  In particular, creature appearance models such as
        # ``c_gizka.mdl`` are not evidence that ``c_gizka.utc`` exists.
        return None
    warning = ""
    category_label = f"{category} / {subcategory}" if category and subcategory else category or kind.title()
    authoring_family = authored_gameplay_authoring_family(kind)
    if kind == "door":
        original_category = category_label.strip()
        category_label = "Placeables / Animated Doors"
        if original_category and original_category.lower() not in {"door", "doors", "animated doors"}:
            category_label = f"{category_label} / {original_category}"
    label = f"{resref} ({kind})"
    if game:
        label = f"{game}: {label}"
    if category_label:
        label = f"{label} - {category_label}"
    return AuthoredGameplayPaletteEntry(
        kind=kind,
        template_resref=resref,
        label=label,
        authoring_family=authoring_family,
        game=game,
        category=category_label,
        source=source,
        confidence=confidence,
        warning=warning,
        metadata=dict(row) if isinstance(row, dict) else {},
    )


def authored_gameplay_palette_from_library_rows(
    rows: Any,
    *,
    game: str = "",
    kind: str = "",
    query: str = "",
    limit: int | None = None,
) -> tuple[AuthoredGameplayPaletteEntry, ...]:
    """Return sorted, filtered gameplay placement palette entries."""

    wanted_game = str(game or "").strip().upper()
    wanted_kind = str(kind or "").strip().lower()
    needle = str(query or "").strip().lower()
    entries: dict[tuple[str, str, str], AuthoredGameplayPaletteEntry] = {}
    for row in rows or ():
        entry = gameplay_palette_entry_from_library_row(row)
        if entry is None:
            continue
        if wanted_game and entry.game and entry.game.upper() != wanted_game:
            continue
        if wanted_kind and entry.kind != wanted_kind and entry.authoring_family != wanted_kind:
            continue
        haystack = " ".join((entry.template_resref, entry.label, entry.category, entry.source)).lower()
        if needle and needle not in haystack:
            continue
        entries[(entry.kind, entry.template_resref, entry.game)] = entry
    ordered = sorted(entries.values(), key=lambda item: (item.kind, item.template_resref, item.game))
    if limit is not None and int(limit) > 0:
        ordered = ordered[: int(limit)]
    return tuple(ordered)


__all__ = [
    "AuthoredGameplayPaletteEntry",
    "authored_gameplay_authoring_family",
    "authored_gameplay_palette_from_library_rows",
    "gameplay_palette_entry_from_library_row",
]
