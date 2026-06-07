"""Conservative translation policy for the first basic retarget solver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from src.core.geometry.model_data import ModelNode

from .source_animation import SourcePose, Transform


Vec3 = Tuple[float, float, float]


@dataclass(frozen=True)
class TranslationPolicyResult:
    """Local translation selected for one target node at one sample."""

    position: Vec3
    wrote_controller: bool = False
    stripped_root_translation: bool = False
    warning: str = ""


def compute_target_local_translation_for_retarget(
    *,
    target_node: ModelNode,
    target_reference_local: Transform,
    source_node_name: str | None,
    source_pose: SourcePose,
    source_reference_pose: SourcePose,
    root_translation_policy: str = "in_place",
    allow_pelvis_vertical_translation: bool = False,
) -> TranslationPolicyResult:
    """Return the Aurora local translation selected for this solver pass."""

    stripped_root = False
    warning = ""
    position = target_reference_local.position
    if target_node.parent is None and source_node_name:
        src_current = source_pose.global_transforms.get(source_node_name)
        src_ref = source_reference_pose.global_transforms.get(source_node_name)
        if src_current is not None and src_ref is not None:
            dx = float(src_current.position[0] - src_ref.position[0])
            dy = float(src_current.position[1] - src_ref.position[1])
            dz = float(src_current.position[2] - src_ref.position[2])
            moved = abs(dx) > 1e-6 or abs(dy) > 1e-6 or abs(dz) > 1e-6
            if root_translation_policy == "in_place":
                if moved:
                    stripped_root = True
                    warning = "Source root translation was stripped by the in-place root motion policy."
            elif root_translation_policy in {"copy_source_root", "preserve_source_root", "root_motion"}:
                position = (
                    float(target_reference_local.position[0] + dx),
                    float(target_reference_local.position[1] + dy),
                    float(target_reference_local.position[2] + dz),
                )
                return TranslationPolicyResult(
                    position=position,
                    wrote_controller=True,
                    stripped_root_translation=False,
                    warning="",
                )

    return TranslationPolicyResult(
        position=position,
        wrote_controller=False,
        stripped_root_translation=stripped_root,
        warning=warning,
    )
