from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="local_character",
    label="Local Character Skinning",
    species="human",
    preferred_qbone_layout="dfs",
    preferred_formula="G5_FULL_REF",
    animation_source="local",
    module_name=__name__,
    taxonomy=("full_body_character", "humanoid"),
    character_modes=("humanoid",),
    model_tokens=("n_", "p_"),
    priority=620,
)
