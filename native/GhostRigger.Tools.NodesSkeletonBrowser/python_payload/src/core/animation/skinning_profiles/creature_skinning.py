from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="creature",
    label="Creature Skinning",
    species="creature",
    preferred_qbone_layout="dfs",
    preferred_formula="G5_FULL_REF",
    animation_source="any",
    module_name=__name__,
    taxonomy=("creature",),
    character_modes=("creature",),
    model_tokens=("c_",),
    supermodel_tokens=("c_", "wardroid", "n_wardroid"),
    node_tokens=("cameramaster", "impact_head", "impact_chest"),
    priority=760,
)
