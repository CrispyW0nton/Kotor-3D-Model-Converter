from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="bastila_headless_body_lower_limb",
    label="Bastila Headless Body Lower-Limb Skinning",
    species="human",
    preferred_qbone_layout="dfs",
    preferred_formula="G5_FULL_REF",
    animation_source="any",
    module_name=__name__,
    taxonomy=("party_member", "full_body_character", "humanoid"),
    character_modes=("humanoid", "headless_body"),
    model_tokens=("p_bastilabb",),
    node_tokens=("torso", "rlegflap01", "frntflap", "llegflap"),
    requires_skin=True,
    priority=1050,
    content_group="party_character_specialcase",
)
