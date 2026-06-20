from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="droid_rigid",
    label="Rigid Droid Animation Skinning",
    species="utility_droid",
    preferred_qbone_layout="dfs",
    preferred_formula="G5_FULL_REF",
    animation_source="local",
    module_name=__name__,
    taxonomy=("droid",),
    character_modes=("humanoid",),
    model_tokens=("t3", "g0t0", "goto"),
    requires_skin=False,
    priority=920,
)
