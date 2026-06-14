from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="animation_supermodel",
    label="Male Supermodel Animation Skinning",
    species="supermodel",
    animation_source="supermodel",
    module_name=__name__,
    taxonomy=("supermodel",),
    model_tokens=("s_male", "s_mal"),
    priority=850,
)
