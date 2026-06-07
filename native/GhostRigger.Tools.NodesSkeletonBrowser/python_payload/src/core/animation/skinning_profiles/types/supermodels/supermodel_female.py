from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="female_supermodel",
    label="Female Supermodel Animation Skinning",
    species="supermodel",
    animation_source="supermodel",
    module_name=__name__,
    taxonomy=("supermodel",),
    model_tokens=("s_female", "s_fml"),
    priority=870,
)
