from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="animation_supermodel",
    label="Animation Supermodel Skinning",
    species="supermodel",
    preferred_qbone_layout="dfs",
    preferred_formula="G5_FULL_REF",
    animation_source="local",
    module_name=__name__,
    taxonomy=("supermodel",),
    character_modes=("supermodel",),
    model_tokens=("s_",),
    priority=600,
)
