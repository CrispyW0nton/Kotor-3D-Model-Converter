from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="duros_humanoid",
    label="Duros Humanoid Skinning",
    species="human",
    animation_source="supermodel",
    module_name=__name__,
    taxonomy=("full_body_character", "humanoid"),
    character_modes=("humanoid",),
    model_tokens=("n_duros", "duros"),
    supermodel_tokens=("s_male", "s_female"),
    priority=730,
)
