from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="t3m4_rigid",
    label="T3-M4 Rigid Droid Skinning",
    species="utility_droid",
    animation_source="local",
    module_name=__name__,
    taxonomy=("droid",),
    character_modes=("humanoid",),
    model_tokens=("p_t3m4", "t3m4"),
    requires_skin=False,
    rigid_animated=True,
    priority=980,
)
