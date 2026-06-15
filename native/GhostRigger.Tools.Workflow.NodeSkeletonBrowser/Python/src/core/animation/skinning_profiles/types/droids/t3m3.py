from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="t3m3_rigid",
    label="T3-M3 Rigid Droid Skinning",
    species="utility_droid",
    animation_source="local",
    module_name=__name__,
    taxonomy=("droid",),
    character_modes=("humanoid",),
    model_tokens=("p_t3m3", "t3m3"),
    requires_skin=False,
    rigid_animated=True,
    priority=980,
)
