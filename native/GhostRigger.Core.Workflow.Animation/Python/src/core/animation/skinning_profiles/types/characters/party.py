from __future__ import annotations

from . import SkinningSpeciesProfile


PARTY_CHARACTER_PROFILE_OVERRIDES: dict[str, dict[str, object]] = {
    "k1:p_bastilabb": {"species": "human"},
    "k1:p_carthbb": {"species": "human"},
    "k1:p_candbb": {"species": "mandalorian"},
    "k1:p_hk47": {"species": "droid"},
    "k1:p_joleebb": {"species": "human"},
    "k1:p_juhanibb": {"species": "human"},
    "k1:p_missionbb": {"species": "human"},
    "k1:p_t3m3": {"species": "utility_droid", "weight_policy": "rigid_node_animation"},
    "k1:p_zaalbar": {"species": "wookie"},
    "k2:n_darthnihilus": {"species": "human"},
    "k2:n_darthsion": {"species": "human"},
    "k2:p_attonbb": {"species": "human"},
    "k2:p_baodurbb": {"species": "human"},
    "k2:p_disciplebb": {"species": "human"},
    "k2:p_g0t0": {"species": "utility_droid", "weight_policy": "rigid_node_animation"},
    "k2:p_handmaidenbb": {"species": "human"},
    "k2:p_hanharr": {"species": "wookie"},
    "k2:p_hk47": {"species": "droid"},
    "k2:p_kreiabb": {"species": "human"},
    "k2:p_mandalore": {"species": "mandalorian"},
    "k2:p_mirabb": {"species": "human"},
    "k2:p_t3m4": {"species": "utility_droid", "weight_policy": "rigid_node_animation"},
    "k2:p_visasbb": {"species": "human"},
}

for _row in PARTY_CHARACTER_PROFILE_OVERRIDES.values():
    _row.setdefault("content_group", "party_character")
    _row.setdefault("weight_policy", "authored_normalized_top4")
    _row.setdefault("max_influences", 4)


PROFILE = SkinningSpeciesProfile(
    key="party_character",
    label="Party Character Skinning",
    species="human",
    preferred_qbone_layout="dfs",
    preferred_formula="G5_FULL_REF",
    animation_source="any",
    module_name=__name__,
    taxonomy=("party_member", "full_body_character", "humanoid", "droid"),
    character_modes=("humanoid",),
    model_tokens=tuple(key.split(":", 1)[1] for key in PARTY_CHARACTER_PROFILE_OVERRIDES),
    requires_skin=None,
    priority=900,
    content_group="party_character",
    weight_policy="authored_normalized_top4",
    max_influences=4,
)
