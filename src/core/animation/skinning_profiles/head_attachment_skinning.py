from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="head_attachment",
    label="Head Attachment Skinning",
    species="human",
    preferred_qbone_layout="dfs",
    preferred_formula="G5_FULL_REF",
    animation_source="supermodel",
    module_name=__name__,
    taxonomy=("head",),
    character_modes=("head",),
    model_tokens=("pmh", "pfh"),
    node_tokens=("talkdummy", "maskhook", "gogglehook"),
    priority=700,
)
