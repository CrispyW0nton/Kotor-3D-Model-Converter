from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="droid_rigid",
    label="Utility Droid Rigid Skinning",
    species="utility_droid",
    animation_source="local",
    module_name=__name__,
    taxonomy=("droid",),
    character_modes=("humanoid",),
    model_tokens=("t3", "g0t0", "goto"),
    requires_skin=False,
    rigid_animated=True,
    priority=925,
)
