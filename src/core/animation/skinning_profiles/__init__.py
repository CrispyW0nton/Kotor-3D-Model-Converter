"""Data-driven animation/skinning profiles for KotOR model families.

The files in this package are intentionally grouped by content-browser model
families rather than one-off character names.  Loaded models are resolved via
``classify_kotor_model`` when available, with name/supermodel fallbacks for
lightweight callers and tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from importlib import import_module
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class SkinningSpeciesProfile:
    key: str
    label: str
    species: str = "unknown"
    preferred_qbone_layout: str = "dfs"
    preferred_formula: str = "G5_FULL_REF"
    animation_source: str = "any"
    module_name: str = ""
    taxonomy: tuple[str, ...] = field(default_factory=tuple)
    character_modes: tuple[str, ...] = field(default_factory=tuple)
    model_tokens: tuple[str, ...] = field(default_factory=tuple)
    supermodel_tokens: tuple[str, ...] = field(default_factory=tuple)
    node_tokens: tuple[str, ...] = field(default_factory=tuple)
    requires_skin: bool | None = None
    game: str = ""
    resref: str = ""
    skin_node_count: int = 0
    rigid_animated: bool = False
    priority: int = 0
    content_group: str = ""
    weight_policy: str = "authored_normalized_top4"
    max_influences: int = 4


_PROFILE_MODULES: tuple[str, ...] = (
    "droid_rigid_skinning",
    "droid_skinned_skinning",
    "creature_skinning",
    "head_attachment_skinning",
    "modular_body_skinning",
    "animation_supermodel_skinning",
    "local_character_skinning",
    "humanoid_supermodel_skinning",
    "default_skinning",
)

_PROFILE_TYPE_MODULES: tuple[str, ...] = (
    "types.characters.bith",
    "types.characters.duros",
    "types.characters.hero",
    "types.characters.human",
    "types.characters.mandalorian",
    "types.characters.party",
    "types.characters.sith",
    "types.characters.wookie",
    "types.creatures.selkath",
    "types.droids.battledroid",
    "types.droids.t3m3",
    "types.droids.t3m4",
    "types.droids.utilitydroid",
    "types.specialcase.kreia",
    "types.specialcase.malak",
    "types.specialcase.nihlus",
    "types.specialcase.revan",
    "types.specialcase.sion",
    "types.supermodels.supermodel_female",
    "types.supermodels.supermodel_male",
    "types.turrets.turret_01",
)


def _load_profiles() -> tuple[SkinningSpeciesProfile, ...]:
    profiles: list[SkinningSpeciesProfile] = []
    package = __name__
    for module_name in (*_PROFILE_MODULES, *_PROFILE_TYPE_MODULES):
        module = import_module(f"{package}.{module_name}")
        profile = getattr(module, "PROFILE")
        profiles.append(replace(profile, module_name=profile.module_name or module.__name__))
    return tuple(sorted(profiles, key=lambda item: item.priority, reverse=True))


SKINNING_PROFILES: tuple[SkinningSpeciesProfile, ...] = _load_profiles()
_BY_KEY: dict[str, SkinningSpeciesProfile] = {}
for _profile in SKINNING_PROFILES:
    _BY_KEY.setdefault(_profile.key, _profile)

SKINNING_SPECIES_PROFILES: dict[str, SkinningSpeciesProfile] = {
    "human": _BY_KEY["humanoid_supermodel"],
    "bith": replace(_BY_KEY["humanoid_supermodel"], species="bith", label="Bith"),
    "droid": _BY_KEY["droid_skinned"],
    "utility_droid": _BY_KEY["droid_rigid"],
    "battle_droid": replace(_BY_KEY["droid_skinned"], species="battle_droid", label="Battle Droid"),
    "creature": _BY_KEY["creature"],
    "yoda": replace(_BY_KEY["humanoid_supermodel"], species="yoda", label="Yoda"),
    "mandalorian": replace(_BY_KEY["humanoid_supermodel"], species="mandalorian", label="Mandalorian"),
    "wookie": _BY_KEY["wookie_humanoid"],
    "gamorrean": replace(_BY_KEY["creature"], species="gamorrean", label="Gamorrean"),
    "supermodel": _BY_KEY["animation_supermodel"],
    "unknown": _BY_KEY["default"],
}


def _contains_any(value: str, tokens: Iterable[str]) -> bool:
    return any(token and token in value for token in tokens)


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").strip().lower()


def _node_names_from_model(model: object) -> tuple[str, ...]:
    try:
        return tuple(str(getattr(node, "name", "") or "") for node in model.all_nodes())
    except Exception:
        return ()


def _has_skin_from_nodes(node_names: Sequence[str], model: object | None = None) -> bool | None:
    if model is not None:
        try:
            for node in model.all_nodes():
                if getattr(node, "bone_map", None) or getattr(node, "qbone_list", None):
                    return True
        except Exception:
            pass
    joined = " ".join(name.lower() for name in node_names)
    if any(token in joined for token in ("torsohoses", "l_hose", "r_hose")):
        return True
    return None


def _taxonomy_from_model(model: object) -> tuple[str, str]:
    try:
        from src.core.geometry.model_data import classify_kotor_model

        result = classify_kotor_model(model)
        return _enum_value(result.category), _enum_value(result.character_mode)
    except Exception:
        return "", ""


def _context_from_args(
    model_or_name: object = "",
    supermodel: str | None = None,
    node_names: Sequence[str] | None = None,
    *,
    has_skin: bool | None = None,
    taxonomy: str | None = None,
    character_mode: str | None = None,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    metadata = metadata or {}
    model_obj = None if isinstance(model_or_name, (str, bytes)) else model_or_name
    name = str(model_or_name or "") if model_obj is None else str(getattr(model_obj, "name", "") or "")
    super_name = str(supermodel if supermodel is not None else getattr(model_obj, "supermodel", "") if model_obj is not None else "")
    game_value = ""
    if model_obj is not None:
        raw_game = getattr(model_obj, "game_version", getattr(model_obj, "game", ""))
        game_value = str(getattr(raw_game, "name", getattr(raw_game, "value", raw_game)) or "").strip().lower()
        if game_value in {"1", "gameversion.k1"}:
            game_value = "k1"
        elif game_value in {"2", "gameversion.k2"}:
            game_value = "k2"
    game_value = str(metadata.get("game", game_value) if metadata else game_value).strip().lower()
    nodes = tuple(str(item or "") for item in (node_names if node_names is not None else _node_names_from_model(model_obj) if model_obj is not None else ()))

    detected_taxonomy = ""
    detected_mode = ""
    if model_obj is not None:
        detected_taxonomy, detected_mode = _taxonomy_from_model(model_obj)

    return {
        "name": name.strip().lower(),
        "game": game_value,
        "supermodel": super_name.strip().lower(),
        "nodes": tuple(node.lower() for node in nodes),
        "taxonomy": str(taxonomy or metadata.get("taxonomy") or detected_taxonomy or "").strip().lower(),
        "character_mode": str(character_mode or metadata.get("character_mode") or detected_mode or "").strip().lower(),
        "has_skin": has_skin if has_skin is not None else _has_skin_from_nodes(nodes, model_obj),
    }


def _specific_profile_for_context(
    *,
    game: str,
    name: str,
    supermodel: str,
    nodes: Sequence[str],
    has_skin: bool | None,
    inherited_animation: bool | None,
) -> SkinningSpeciesProfile | None:
    try:
        from .types.generated_character_skinning import (
            CHARACTER_SKINNING_PROFILE_BY_KEY,
            CHARACTER_SKINNING_PROFILE_BY_RESREF,
        )
    except Exception:
        return None

    row = None
    if game:
        row = CHARACTER_SKINNING_PROFILE_BY_KEY.get(f"{game}:{name}")
    if row is None:
        row = CHARACTER_SKINNING_PROFILE_BY_RESREF.get(name)
    if row is None:
        return None

    skin_count = int(row.get("skin_node_count", 0) or 0)
    rigid_animated = bool(row.get("rigid_animated", False))
    if has_skin is True and skin_count <= 0:
        return None
    if has_skin is False and skin_count > 0:
        return None
    resref = str(row.get("resref", name) or name).lower()
    row_game = str(row.get("game", game) or game).lower()
    species = _species_for_context(resref, supermodel, nodes, "")
    try:
        from .types.characters.party import PARTY_CHARACTER_PROFILE_OVERRIDES
    except Exception:
        PARTY_CHARACTER_PROFILE_OVERRIDES = {}
    party_override = PARTY_CHARACTER_PROFILE_OVERRIDES.get(f"{row_game}:{resref}")
    if party_override is not None:
        species = str(party_override.get("species") or species)
    if skin_count <= 0 and rigid_animated:
        base = _BY_KEY["droid_rigid"] if species in {"droid", "utility_droid", "battle_droid"} else _BY_KEY["animation_supermodel"]
    elif species in {"droid", "utility_droid", "battle_droid"}:
        base = _BY_KEY["droid_skinned"]
    elif resref.startswith("c_"):
        base = _BY_KEY["creature"]
    elif resref.startswith("s_"):
        base = _BY_KEY["animation_supermodel"]
    elif resref.startswith(("pmh", "pfh")):
        base = _BY_KEY["head_attachment"]
    elif resref.startswith(("pmb", "pfb")):
        base = _BY_KEY["modular_body"]
    elif inherited_animation is True:
        base = _BY_KEY["humanoid_supermodel"]
    else:
        base = _BY_KEY["local_character"]

    return replace(
        base,
        key=f"{row_game}:{resref}",
        label=f"{row_game.upper()} {resref} Skinning",
        species=species,
        module_name="src.core.animation.skinning_profiles.types.generated_character_skinning",
        model_tokens=(resref,),
        supermodel_tokens=(str(row.get("supermodel", "") or "").lower(),),
        requires_skin=skin_count > 0,
        game=row_game,
        resref=resref,
        skin_node_count=skin_count,
        rigid_animated=rigid_animated,
        priority=max(base.priority, 5000),
        content_group=str(party_override.get("content_group", "") if party_override else ""),
        weight_policy=str(party_override.get("weight_policy", base.weight_policy) if party_override else base.weight_policy),
        max_influences=int(party_override.get("max_influences", base.max_influences) if party_override else base.max_influences),
    )


def _species_for_context(name: str, supermodel: str, nodes: Sequence[str], taxonomy: str) -> str:
    haystack = " ".join((name, supermodel, " ".join(nodes)))
    if "bith" in haystack or "brith" in haystack:
        return "bith"
    if "wardroid" in haystack or "warbot" in haystack or "c_drd" in name:
        return "battle_droid"
    if "t3" in name or "g0t0" in name or "goto" in name:
        return "utility_droid"
    if "hk" in name or "droid" in haystack or "drd" in name or taxonomy == "droid":
        return "droid"
    if "wookie" in haystack or "wook" in haystack or "zaalbar" in haystack or "hanharr" in haystack:
        return "wookie"
    if "yoda" in name:
        return "yoda"
    if "mandalorian" in name:
        return "mandalorian"
    if "gammorean" in name or "gamorrean" in name:
        return "gamorrean"
    if taxonomy == "creature" or name.startswith("c_"):
        return "creature"
    if taxonomy == "supermodel" or name.startswith("s_"):
        return "supermodel"
    return "human"


def _profile_matches(
    profile: SkinningSpeciesProfile,
    *,
    name: str,
    supermodel: str,
    nodes: Sequence[str],
    taxonomy: str,
    character_mode: str,
    has_skin: bool | None,
    inherited_animation: bool | None,
) -> bool:
    if profile.key == "default":
        return False
    if inherited_animation is True and profile.animation_source == "local":
        return False
    if inherited_animation is False and profile.animation_source == "supermodel":
        return False
    if profile.requires_skin is not None and has_skin is not None and profile.requires_skin != has_skin:
        return False
    if taxonomy and taxonomy in profile.taxonomy:
        return True
    if character_mode and character_mode in profile.character_modes:
        return True

    joined_nodes = " ".join(nodes)
    haystack = " ".join((name, supermodel, joined_nodes))
    return (
        _contains_any(name, profile.model_tokens)
        or _contains_any(supermodel, profile.supermodel_tokens)
        or _contains_any(haystack, profile.node_tokens)
    )


def resolve_skinning_profile(
    model_or_name: object = "",
    supermodel: str | None = "",
    node_names: Sequence[str] | None = None,
    *,
    inherited_animation: bool | None = None,
    has_skin: bool | None = None,
    taxonomy: str | None = None,
    character_mode: str | None = None,
    metadata: Mapping[str, object] | None = None,
) -> SkinningSpeciesProfile:
    context = _context_from_args(
        model_or_name,
        supermodel,
        node_names,
        has_skin=has_skin,
        taxonomy=taxonomy,
        character_mode=character_mode,
        metadata=metadata,
    )
    name = str(context["name"])
    game = str(context["game"])
    super_name = str(context["supermodel"])
    nodes = tuple(context["nodes"])  # type: ignore[arg-type]
    taxonomy_value = str(context["taxonomy"])
    mode_value = str(context["character_mode"])
    has_skin_value = context["has_skin"] if isinstance(context["has_skin"], bool) else None

    specific = _specific_profile_for_context(
        game=game,
        name=name,
        supermodel=super_name,
        nodes=nodes,
        has_skin=has_skin_value,
        inherited_animation=inherited_animation,
    )
    if specific is not None:
        return specific

    selected = SKINNING_SPECIES_PROFILES["unknown"]
    for profile in SKINNING_PROFILES:
        if _profile_matches(
            profile,
            name=name,
            supermodel=super_name,
            nodes=nodes,
            taxonomy=taxonomy_value,
            character_mode=mode_value,
            has_skin=has_skin_value,
            inherited_animation=inherited_animation,
        ):
            selected = profile
            break

    species = _species_for_context(name, super_name, nodes, taxonomy_value)
    if selected.key == "default" and species in SKINNING_SPECIES_PROFILES:
        return SKINNING_SPECIES_PROFILES[species]
    if selected.key == "default":
        return selected
    if species != selected.species:
        species_profile = SKINNING_SPECIES_PROFILES.get(species)
        label = species_profile.label if species_profile is not None else selected.label
        return replace(selected, species=species, label=label)
    return selected


def classify_skinning_species(
    model_or_name: object = "",
    supermodel: str | None = "",
    node_names: Sequence[str] | None = None,
) -> str:
    profile = resolve_skinning_profile(model_or_name, supermodel, node_names)
    return profile.species or profile.key or "unknown"
