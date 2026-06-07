"""Reference-pose construction for source-to-Aurora retarget profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Dict, Tuple

import numpy as np

from src.core.animation.animation_engine import AuroraTransform, evaluate_aurora_animation_pose
from src.core.game.kotor_loader import resolve_animation_slot
from src.core.geometry.model_data import KotorModel

from .retarget_profile import RetargetProfile
from .source_animation import SourcePose, SourceSkeletonClip, Transform, normalize_quat_xyzw


@dataclass
class ReferencePosePair:
    """Explicit source/target reference poses for later retarget-frame solving."""

    source_pose: SourcePose
    target_local_transforms: Dict[str, Transform]
    target_global_transforms: Dict[str, Transform]
    source_reference_mode: str
    target_reference_mode: str
    warnings: list[str] = field(default_factory=list)


def compute_target_rest_transforms(
    model: KotorModel,
) -> Tuple[Dict[str, Transform], Dict[str, Transform]]:
    """Compute Aurora rest local and global transforms by parent-first FK."""

    local_by_node: Dict[str, Transform] = {}
    global_by_node: Dict[str, Transform] = {}
    global_matrices: Dict[str, np.ndarray] = {}

    for node in model.all_nodes():
        local = Transform(
            position=tuple(float(value) for value in node.position),
            rotation=normalize_quat_xyzw(node.rotation),
            scale=(1.0, 1.0, 1.0),
        )
        local_by_node[node.name] = local

        parent_matrix = None
        if node.parent is not None:
            parent_matrix = global_matrices.get(node.parent.name)
        world_matrix = local.to_matrix() if parent_matrix is None else parent_matrix @ local.to_matrix()
        global_matrices[node.name] = world_matrix
        global_by_node[node.name] = Transform.from_matrix(world_matrix)

    return local_by_node, global_by_node


def build_reference_pose_pair(
    *,
    source_clip: SourceSkeletonClip,
    target_model: KotorModel,
    profile: RetargetProfile,
    supermodel_chain=None,
) -> ReferencePosePair:
    """Build explicit source and target references without mutating either asset."""

    warnings: list[str] = []
    source_mode = str((profile.source_reference or {}).get("mode", "clip_rest") or "clip_rest")
    target_mode = str((profile.target_reference or {}).get("mode", "target_rest") or "target_rest")

    source_pose = _select_source_reference(source_clip, profile, source_mode, warnings)
    target_local, target_global = _select_target_reference(target_model, profile, target_mode)

    _validate_reference_transforms("source", source_pose.local_transforms)
    _validate_reference_transforms("source", source_pose.global_transforms)
    _validate_reference_transforms("target", target_local)
    _validate_reference_transforms("target", target_global)

    return ReferencePosePair(
        source_pose=source_pose,
        target_local_transforms=target_local,
        target_global_transforms=target_global,
        source_reference_mode=source_mode,
        target_reference_mode=target_mode,
        warnings=warnings,
    )


def _select_source_reference(
    source_clip: SourceSkeletonClip,
    profile: RetargetProfile,
    mode: str,
    warnings: list[str],
) -> SourcePose:
    if mode == "clip_rest":
        return source_clip.rest_pose
    if mode == "clip_time":
        raw_time = (profile.source_reference or {}).get("time_seconds")
        if raw_time is None:
            raw_time = (profile.source_reference or {}).get("time", 0.0)
        pose = source_clip.pose_at_time(float(raw_time))
        if abs(pose.time_seconds - float(raw_time)) > 1e-6:
            warnings.append(
                f"Source clip_time reference {float(raw_time):g}s used nearest sampled pose "
                f"{pose.time_seconds:g}s; interpolation is not implemented in this gate."
            )
        return pose
    raise ValueError(f"Unsupported source reference mode '{mode}'.")


def _select_target_reference(
    target_model: KotorModel,
    profile: RetargetProfile,
    mode: str,
) -> Tuple[Dict[str, Transform], Dict[str, Transform]]:
    if mode == "target_rest":
        return compute_target_rest_transforms(target_model)

    if mode == "animation_slot_time":
        slot = str((profile.target_reference or {}).get("slot") or profile.animation_slot or "").strip()
        if not slot:
            raise ValueError("Target animation_slot_time reference requires a slot or profile.animation_slot.")
        raw_time = (profile.target_reference or {}).get("time_seconds")
        if raw_time is None:
            raw_time = (profile.target_reference or {}).get("time", 0.0)
        resolved = resolve_animation_slot(target_model, slot, require_valid=True)
        if resolved.animation is None:
            raise ValueError(f"Animation slot '{slot}' did not resolve to an animation block.")
        evaluated = evaluate_aurora_animation_pose(target_model, resolved.animation, float(raw_time))
        return (
            {
                name: _transform_from_aurora(value)
                for name, value in evaluated.local_transforms_by_node.items()
            },
            {
                name: _transform_from_aurora(value)
                for name, value in evaluated.world_transforms_by_node.items()
            },
        )

    raise ValueError(f"Unsupported target reference mode '{mode}'.")


def _transform_from_aurora(value: AuroraTransform) -> Transform:
    return Transform(
        position=tuple(float(component) for component in value.position),
        rotation=normalize_quat_xyzw(value.rotation),
        scale=(1.0, 1.0, 1.0),
    )


def _validate_reference_transforms(kind: str, transforms: Dict[str, Transform]) -> None:
    for name, transform in transforms.items():
        if not transform.is_finite():
            raise ValueError(f"{kind} reference transform for '{name}' contains non-finite values.")
        q_norm = math.sqrt(sum(float(value) * float(value) for value in transform.rotation))
        if q_norm <= 1e-9:
            raise ValueError(f"{kind} reference transform for '{name}' has a zero-length quaternion.")
