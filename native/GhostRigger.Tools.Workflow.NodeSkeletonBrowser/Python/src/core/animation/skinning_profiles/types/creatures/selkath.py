from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="selkath_creature",
    label="Selkath Creature Skinning",
    species="creature",
    animation_source="local",
    module_name=__name__,
    taxonomy=("creature", "full_body_character"),
    model_tokens=("selkath",),
    priority=830,
)
