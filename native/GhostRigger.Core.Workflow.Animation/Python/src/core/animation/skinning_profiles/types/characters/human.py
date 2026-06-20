from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="humanoid_supermodel",
    label="Humanoid Supermodel Skinning",
    species="human",
    animation_source="supermodel",
    module_name=__name__,
    taxonomy=("full_body_character", "humanoid"),
    character_modes=("humanoid",),
    model_tokens=("pm", "pf", "p_", "n_"),
    supermodel_tokens=("s_male", "s_female", "s_fml", "s_mal"),
    priority=540,
)
