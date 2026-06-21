from __future__ import annotations

from . import SkinningSpeciesProfile


PROFILE = SkinningSpeciesProfile(
    key="turret_rigid",
    label="Turret Rigid Animation Skinning",
    species="creature",
    animation_source="local",
    module_name=__name__,
    taxonomy=("creature",),
    model_tokens=("turret", "tur_"),
    requires_skin=False,
    rigid_animated=True,
    priority=700,
)
