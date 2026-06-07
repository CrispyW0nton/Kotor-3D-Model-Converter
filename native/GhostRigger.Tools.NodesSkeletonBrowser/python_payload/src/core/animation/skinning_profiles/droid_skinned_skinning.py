from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="droid_skinned",
    label="Skinned Droid Skinning",
    species="droid",
    preferred_qbone_layout="dfs",
    preferred_formula="G5_FULL_REF",
    animation_source="local",
    module_name=__name__,
    taxonomy=("droid",),
    character_modes=("humanoid",),
    model_tokens=("hk", "drd", "droid", "wardroid", "warbot"),
    node_tokens=("torsohoses", "l_hose", "r_hose"),
    requires_skin=True,
    priority=900,
)
