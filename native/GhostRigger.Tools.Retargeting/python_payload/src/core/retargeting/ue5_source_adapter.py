"""UE5 source skeleton adaptation for reverse Aurora injection.

R3.A does not modify target MDL files. It classifies UE5 source animation
channels so the extraction stage can emit a deterministic Aurora-targeted JSON
payload for the later MDL writer stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional

from .reverse_renamer import ReverseRenameSpec


KNOWN_UE5_EXTRAS = {
    "attach",
    "global",
    "ik_foot_root",
    "ik_foot_l",
    "ik_foot_r",
    "ik_hand_root",
    "ik_hand_gun",
    "ik_hand_l",
    "ik_hand_r",
    "interaction",
    "center_of_mass",
    "weapon_l",
    "weapon_r",
    "camera",
    "neck_02",
}

FINGER_TOKENS = (
    "thumb_",
    "index_",
    "middle_",
    "ring_",
    "pinky_",
)

DEFAULT_ROOT_ALIASES = ("root", "attach")
DEFAULT_SPINE_COLLAPSE = {
    "spine_02": "torsoupr_g",
    "spine_04": "torsoupr_g",
    "spine_05": "torsoupr_g",
}


def key_name(name: str) -> str:
    return str(name or "").strip().lower()


@dataclass(frozen=True)
class SourceBoneDecision:
    """Classification for one UE5 source bone."""

    source_bone: str
    action: str
    target_bone: Optional[str] = None
    reason: str = ""


@dataclass
class UE5SourceAdapterResult:
    """Summary of source-channel adaptation."""

    decisions: list[SourceBoneDecision] = field(default_factory=list)

    @property
    def mapped(self) -> list[SourceBoneDecision]:
        return [item for item in self.decisions if item.action in {"map", "alias"}]

    @property
    def dropped(self) -> list[SourceBoneDecision]:
        return [item for item in self.decisions if item.action == "drop"]

    @property
    def collapsed(self) -> list[SourceBoneDecision]:
        return [item for item in self.decisions if item.action == "collapse"]

    @property
    def unmapped(self) -> list[SourceBoneDecision]:
        return [item for item in self.decisions if item.action == "unmapped"]

    def target_for(self, source_bone: str) -> Optional[str]:
        source_key = key_name(source_bone)
        for decision in self.decisions:
            if decision.source_bone == source_key and decision.action in {"map", "alias"}:
                return decision.target_bone
        return None

    def to_dict(self) -> dict:
        return {
            "mapped_count": len(self.mapped),
            "dropped_count": len(self.dropped),
            "collapsed_count": len(self.collapsed),
            "unmapped_count": len(self.unmapped),
            "decisions": [
                {
                    "source_bone": item.source_bone,
                    "action": item.action,
                    "target_bone": item.target_bone,
                    "reason": item.reason,
                }
                for item in self.decisions
            ],
        }


class UE5SourceAdapter:
    """Classify UE5 Manny/UEFN source bones against a reverse rename spec."""

    def __init__(
        self,
        *,
        root_aliases: Iterable[str] = DEFAULT_ROOT_ALIASES,
        spine_collapse: Mapping[str, str] = DEFAULT_SPINE_COLLAPSE,
    ):
        self.root_aliases = tuple(key_name(name) for name in root_aliases)
        self.spine_collapse = {
            key_name(source): key_name(target)
            for source, target in dict(spine_collapse).items()
        }

    def adapt(
        self,
        source_bones: Iterable[str],
        spec: ReverseRenameSpec,
        target_bones: Iterable[str] = (),
    ) -> UE5SourceAdapterResult:
        source_keys = [key_name(name) for name in source_bones]
        source_set = set(source_keys)
        target_set = {key_name(name) for name in target_bones}
        dropped_by_spec = {
            key_name(name)
            for name in [*spec.ue5_only_bones_dropped, *spec.synthetic_helper_bones_dropped]
        }
        root_target = key_name(spec.rename_pairs.get("root", "rootdummy"))
        canonical_root_present = "root" in source_set

        decisions: list[SourceBoneDecision] = []
        for source in source_keys:
            if source in spec.rename_pairs:
                target = key_name(spec.rename_pairs[source])
                if target_set and target not in target_set:
                    decisions.append(
                        SourceBoneDecision(
                            source_bone=source,
                            action="unmapped",
                            reason=f"mapped target '{target}' missing from Aurora skeleton",
                        )
                    )
                else:
                    decisions.append(
                        SourceBoneDecision(
                            source_bone=source,
                            action="map",
                            target_bone=target,
                            reason="reverse rename pair",
                        )
                    )
                continue

            if source in self.root_aliases and source != "root" and not canonical_root_present:
                decisions.append(
                    SourceBoneDecision(
                        source_bone=source,
                        action="alias",
                        target_bone=root_target,
                        reason="source root alias",
                    )
                )
                continue

            if source in self.spine_collapse:
                decisions.append(
                    SourceBoneDecision(
                        source_bone=source,
                        action="collapse",
                        target_bone=self.spine_collapse[source],
                        reason="spine chain collapse candidate",
                    )
                )
                continue

            if source in dropped_by_spec or source in KNOWN_UE5_EXTRAS:
                decisions.append(
                    SourceBoneDecision(
                        source_bone=source,
                        action="drop",
                        reason="known UE5 helper or reverse-map drop",
                    )
                )
                continue

            if "twist" in source or any(token in source for token in FINGER_TOKENS):
                decisions.append(
                    SourceBoneDecision(
                        source_bone=source,
                        action="drop",
                        reason="finger or twist channel outside PMBAM core",
                    )
                )
                continue

            decisions.append(
                SourceBoneDecision(
                    source_bone=source,
                    action="unmapped",
                    reason="no reverse mapping policy",
                )
            )

        return UE5SourceAdapterResult(decisions=decisions)
