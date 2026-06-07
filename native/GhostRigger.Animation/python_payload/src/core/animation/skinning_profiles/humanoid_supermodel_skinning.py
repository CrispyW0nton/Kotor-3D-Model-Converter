from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="humanoid_supermodel",
    label="Humanoid Supermodel Skinning",
    species="human",
    preferred_qbone_layout="dfs",
    preferred_formula="G5_FULL_REF",
    animation_source="supermodel",
    module_name=__name__,
    taxonomy=("full_body_character", "humanoid"),
    character_modes=("humanoid",),
    supermodel_tokens=("s_male", "s_female", "s_fml", "s_mal"),
    model_tokens=("pm", "pf", "p_", "n_"),
    priority=520,
)
