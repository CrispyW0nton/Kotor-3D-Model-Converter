"""Mixamo source skeleton adaptation for Aurora/PMBAM retargeting."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


MIXAMO_PREFIX = "mixamorig:"


def mixamo_key(name: str) -> str:
    """Return a stable Mixamo bone key without namespace/punctuation noise."""

    text = str(name or "").strip().lower()
    if ":" in text:
        text = text.split(":", 1)[1]
    return re.sub(r"[^a-z0-9]+", "", text)


MIXAMO_TO_AURORA_CORE: dict[str, tuple[str, str, str]] = {
    "hips": ("pelvis", "center", "pelvis_g"),
    "spine": ("spine", "center", "torso_g"),
    "spine2": ("chest", "center", "torsoupr_g"),
    "leftshoulder": ("clavicle", "left", "lcollar_g"),
    "leftarm": ("upperarm", "left", "lbicep_g"),
    "leftforearm": ("forearm", "left", "Lforearm_g"),
    "lefthand": ("hand", "left", "Lhand_g"),
    "lefthandmiddle1": ("middle_base", "left", "LbFngrB_g"),
    "lefthandmiddle3": ("middle_tip", "left", "LbFngrT_g"),
    "rightshoulder": ("clavicle", "right", "rcollar_g"),
    "rightarm": ("upperarm", "right", "rbicep_g"),
    "rightforearm": ("forearm", "right", "Rforearm_g"),
    "righthand": ("hand", "right", "Rhand_g"),
    "righthandmiddle1": ("middle_base", "right", "RbFngrB_g"),
    "righthandmiddle3": ("middle_tip", "right", "RbFngrT_g"),
    "leftupleg": ("thigh", "left", "lthigh_g"),
    "leftleg": ("calf", "left", "lshin_g"),
    "leftfoot": ("foot", "left", "lfoot_g"),
    "lefttoebase": ("toe", "left", "lfootT_g"),
    "rightupleg": ("thigh", "right", "rthigh_g"),
    "rightleg": ("calf", "right", "rshin_g"),
    "rightfoot": ("foot", "right", "rfoot_g"),
    "righttoebase": ("toe", "right", "rfootT_g"),
}

MIXAMO_IGNORED_KEYS = {
    "spine1",
    "neck",
    "head",
    "headtopend",
    "lefttoeend",
    "righttoeend",
}


@dataclass(frozen=True)
class MixamoBoneDecision:
    source_bone: str
    key: str
    action: str
    role: str | None = None
    side: str | None = None
    target_bone: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class MixamoSourceAdapterResult:
    decisions: tuple[MixamoBoneDecision, ...]

    @property
    def mapped(self) -> list[MixamoBoneDecision]:
        return [item for item in self.decisions if item.action == "map"]

    @property
    def ignored(self) -> list[MixamoBoneDecision]:
        return [item for item in self.decisions if item.action == "ignore"]

    @property
    def unmapped(self) -> list[MixamoBoneDecision]:
        return [item for item in self.decisions if item.action == "unmapped"]


def is_mixamo_skeleton(source_bones: Iterable[str]) -> bool:
    """Return True when the source names look like a Mixamo humanoid rig."""

    keys = {mixamo_key(name) for name in source_bones}
    prefixed = any(str(name or "").strip().lower().startswith(MIXAMO_PREFIX) for name in source_bones)
    required = {"hips", "spine", "spine1", "spine2", "leftarm", "rightarm", "leftupleg", "rightupleg"}
    return prefixed and required.issubset(keys)


class MixamoSourceAdapter:
    """Classify Mixamo source bones against a KOTOR/Aurora target skeleton."""

    def adapt(self, source_bones: Iterable[str], target_bones: Iterable[str]) -> MixamoSourceAdapterResult:
        target_name_by_key = {str(name or "").strip().lower(): str(name) for name in target_bones}
        decisions: list[MixamoBoneDecision] = []
        for source_name in source_bones:
            key = mixamo_key(source_name)
            mapping = MIXAMO_TO_AURORA_CORE.get(key)
            if mapping is not None:
                role, side, target_key = mapping
                target_name = target_name_by_key.get(target_key.lower())
                if target_name:
                    decisions.append(
                        MixamoBoneDecision(
                            source_bone=str(source_name),
                            key=key,
                            action="map",
                            role=role,
                            side=side,
                            target_bone=target_name,
                            reason="Mixamo humanoid core mapping",
                        )
                    )
                else:
                    decisions.append(
                        MixamoBoneDecision(
                            source_bone=str(source_name),
                            key=key,
                            action="unmapped",
                            reason=f"mapped Aurora target '{target_key}' missing from target skeleton",
                        )
                    )
                continue
            if key in MIXAMO_IGNORED_KEYS or ("hand" in key and key[-1:].isdigit()):
                decisions.append(
                    MixamoBoneDecision(
                        source_bone=str(source_name),
                        key=key,
                        action="ignore",
                        reason="Mixamo helper/finger channel outside PMBAM core map",
                    )
                )
                continue
            decisions.append(
                MixamoBoneDecision(
                    source_bone=str(source_name),
                    key=key,
                    action="unmapped",
                    reason="no Mixamo-to-Aurora mapping policy",
                )
            )
        return MixamoSourceAdapterResult(decisions=tuple(decisions))
