from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="sith_humanoid",
    label="Sith Humanoid Skinning",
    species="human",
    animation_source="supermodel",
    module_name=__name__,
    taxonomy=("full_body_character", "humanoid"),
    character_modes=("humanoid",),
    model_tokens=("sith", "darkjedi", "jedi"),
    supermodel_tokens=("s_male", "s_female"),
    priority=750,
)
