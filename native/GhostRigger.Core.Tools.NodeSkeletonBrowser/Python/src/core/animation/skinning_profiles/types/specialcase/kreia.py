from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="kreia_local",
    label="Kreia Local Skinning",
    species="human",
    animation_source="local",
    module_name=__name__,
    taxonomy=("full_body_character", "humanoid"),
    character_modes=("humanoid",),
    model_tokens=("kreia", "kerya", "n_darthtraya"),
    priority=1020,
)
