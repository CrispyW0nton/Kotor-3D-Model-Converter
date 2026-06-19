from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="nihilus_local",
    label="Nihilus Local Skinning",
    species="human",
    animation_source="local",
    module_name=__name__,
    taxonomy=("full_body_character", "humanoid"),
    character_modes=("humanoid",),
    model_tokens=("nihilus", "nihil"),
    priority=1030,
)
