from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="malak_local",
    label="Malak Local Skinning",
    species="human",
    animation_source="local",
    module_name=__name__,
    taxonomy=("full_body_character", "humanoid"),
    character_modes=("humanoid",),
    model_tokens=("n_darthmalak", "malak"),
    priority=1040,
)
