from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="wookie_humanoid",
    label="Wookie Humanoid Skinning",
    species="wookie",
    animation_source="supermodel",
    module_name=__name__,
    taxonomy=("full_body_character", "humanoid"),
    character_modes=("humanoid",),
    model_tokens=("wookie", "wook", "zaalbar", "hanharr"),
    supermodel_tokens=("s_male", "s_female"),
    priority=770,
)
