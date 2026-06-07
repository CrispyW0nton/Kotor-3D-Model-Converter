from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="modular_body",
    label="Modular Body Skinning",
    species="human",
    preferred_qbone_layout="dfs",
    preferred_formula="G5_FULL_REF",
    animation_source="supermodel",
    module_name=__name__,
    taxonomy=("modular_body",),
    character_modes=("headless_body",),
    model_tokens=("pmb", "pfb"),
    node_tokens=("headhook", "rhand", "lhand_g"),
    priority=680,
)
