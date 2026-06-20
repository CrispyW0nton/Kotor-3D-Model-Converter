from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="sion_local",
    label="Sion Local Skinning",
    species="human",
    animation_source="local",
    module_name=__name__,
    taxonomy=("full_body_character", "humanoid"),
    character_modes=("humanoid",),
    model_tokens=("sion",),
    priority=1030,
)
