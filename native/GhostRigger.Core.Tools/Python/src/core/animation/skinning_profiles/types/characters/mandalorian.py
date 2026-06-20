from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="mandalorian_humanoid",
    label="Mandalorian Humanoid Skinning",
    species="mandalorian",
    animation_source="supermodel",
    module_name=__name__,
    taxonomy=("full_body_character", "humanoid"),
    character_modes=("humanoid",),
    model_tokens=("mandalorian", "n_mandalorian"),
    supermodel_tokens=("s_male", "s_female"),
    priority=790,
)
