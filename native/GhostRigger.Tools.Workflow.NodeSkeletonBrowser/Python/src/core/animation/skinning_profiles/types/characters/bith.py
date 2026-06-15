from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="bith_humanoid",
    label="Bith Humanoid Skinning",
    species="bith",
    animation_source="supermodel",
    module_name=__name__,
    taxonomy=("full_body_character", "humanoid"),
    character_modes=("humanoid",),
    model_tokens=("n_bith", "bith"),
    supermodel_tokens=("s_male", "s_female"),
    priority=760,
)
