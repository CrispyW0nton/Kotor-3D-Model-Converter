from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="hero_modular_body",
    label="Hero Modular Body Skinning",
    species="human",
    animation_source="supermodel",
    module_name=__name__,
    taxonomy=("full_body_character", "humanoid"),
    character_modes=("humanoid",),
    model_tokens=("pmb", "pfb"),
    supermodel_tokens=("s_male", "s_female"),
    requires_skin=True,
    priority=780,
)
