from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="default",
    label="Default Skinning",
    species="unknown",
    preferred_qbone_layout="dfs",
    preferred_formula="G5_FULL_REF",
    animation_source="any",
    module_name=__name__,
    priority=-1000,
)

