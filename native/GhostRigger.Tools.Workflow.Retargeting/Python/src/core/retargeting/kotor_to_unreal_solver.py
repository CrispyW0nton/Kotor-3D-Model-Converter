"""First-pass KOTOR/Aurora source clip to Unreal skeleton retarget solver."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

import numpy as np

from src.core.validation.validation_bus import (
    ValidationIssue,
    ValidationNavigationTarget,
    ValidationReport,
    ValidationSeverity,
    ValidationSubsystem,
    merge_validation_reports,
)

from .coordinate import BasisConversion
from .retarget_frames import transfer_reference_frame_delta
from .retarget_profile import RetargetProfile, normalize_retarget_profile
from .source_animation import (
    SourcePose,
    SourceSkeletonClip,
    Transform,
    hemisphere_continuity_xyzw,
    matrix_to_quat_xyzw,
    normalize_quat_xyzw,
    quat_to_matrix_xyzw,
)
from .unreal_target_skeleton import (
    UnrealAnimationClip,
    UnrealAnimationPose,
    UnrealSkeletonNode,
    UnrealTargetSkeleton,
    audit_unreal_target_skeleton,
)


class KotorToUnrealSolveError(ValueError):
    """Raised when KOTOR-to-Unreal solving cannot produce a deterministic clip."""


@dataclass(frozen=True)
class KotorToUnrealSolveAudit:
    validation_report: ValidationReport
    warnings: list[str]


def validate_retarget_profile_for_unreal_target(
    profile: RetargetProfile,
    source_clip: SourceSkeletonClip,
    target_skeleton: UnrealTargetSkeleton,
    *,
    strict: bool = True,
) -> ValidationReport:
    """Validate a retarget profile against KOTOR source clip and UE skeleton nodes."""

    normalized = normalize_retarget_profile(profile)
    source_names = set(source_clip.node_names)
    source_by_name = {node.name: node for node in source_clip.nodes}
    target_names = set(target_skeleton.node_names)
    issues: list[ValidationIssue] = []
    seen_targets: set[str] = set()

    if not normalized.mappings:
        issues.append(_issue("retarget_profile.empty_mapping", "Retarget profile has no source-to-Unreal mappings."))

    for entry in normalized.mappings:
        source = str(entry.source_node or "").strip()
        target = str(entry.target_node or "").strip()
        if source not in source_names:
            issues.append(
                _issue(
                    "retarget_profile.unknown_source_node",
                    f"Retarget profile maps unknown KOTOR source node '{source}'.",
                    node_name=source,
                )
            )
        else:
            classification = str(getattr(source_by_name[source], "classification", "") or "").lower()
            if classification in {"hook", "helper", "mesh"} and not entry.allow_helper_mapping:
                severity = ValidationSeverity.ERROR if strict else ValidationSeverity.WARNING
                issues.append(
                    _issue(
                        "retarget_profile.helper_source_mapping",
                        f"Source node '{source}' is classified as {classification}; enable helper mapping explicitly.",
                        severity=severity,
                        node_name=source,
                    )
                )
        if target not in target_names:
            issues.append(
                _issue(
                    "retarget_profile.unknown_unreal_target_node",
                    f"Retarget profile maps to unknown Unreal target bone '{target}'.",
                    node_name=target,
                )
            )
        if target in seen_targets:
            issues.append(
                _issue(
                    "retarget_profile.duplicate_unreal_target",
                    f"Retarget profile maps multiple source nodes to Unreal target bone '{target}'.",
                    node_name=target,
                )
            )
        seen_targets.add(target)

    target_by_name = target_skeleton.node_by_name()
    unmapped_special = [
        node.name
        for node in target_skeleton.nodes
        if node.name not in seen_targets and str(node.classification or "").lower() in {"twist", "ik", "helper"}
    ]
    if unmapped_special:
        issues.append(
            _issue(
                "retarget_profile.unmapped_unreal_helper_nodes",
                "UE target has twist/IK/helper bones that were left at rest: "
                + ", ".join(unmapped_special[:8])
                + ("" if len(unmapped_special) <= 8 else f", ... ({len(unmapped_special) - 8} more)"),
                severity=ValidationSeverity.WARNING,
                details={"nodes": unmapped_special},
            )
        )

    humanoid_roles = {"root", "pelvis", "spine", "chest", "head", "upperarm", "forearm", "hand", "thigh", "calf", "foot"}
    roles = {str(entry.role or "").lower() for entry in normalized.mappings}
    missing_roles = sorted(role for role in humanoid_roles if role not in roles)
    if missing_roles:
        issues.append(
            _issue(
                "retarget_profile.missing_humanoid_roles",
                "Retarget profile is missing common humanoid roles: " + ", ".join(missing_roles[:10]),
                severity=ValidationSeverity.WARNING,
                details={"missing_roles": missing_roles},
            )
        )

    return merge_validation_reports(
        audit_unreal_target_skeleton(target_skeleton),
        ValidationReport(issues=issues, source="retarget.kotor_to_unreal.profile"),
    )


def retarget_kotor_source_clip_to_unreal_animation(
    *,
    source_clip: SourceSkeletonClip,
    target_skeleton: UnrealTargetSkeleton,
    profile: RetargetProfile,
    output_clip_name: str,
    basis_conversion: BasisConversion | None = None,
    sample_rate: float | None = None,
    root_motion_policy: str = "in_place",
    strict: bool = True,
) -> UnrealAnimationClip:
    """Bake a sampled KOTOR source clip onto a UE target skeleton."""

    clip_name = str(output_clip_name or "").strip()
    if not clip_name:
        raise KotorToUnrealSolveError("KOTOR → Unreal output requires a UE animation clip name.")

    validation = validate_retarget_profile_for_unreal_target(profile, source_clip, target_skeleton, strict=strict)
    if validation.has_errors:
        raise KotorToUnrealSolveError("; ".join(issue.message for issue in validation.issues if issue.severity in {ValidationSeverity.ERROR, ValidationSeverity.BLOCKING}))

    normalized = normalize_retarget_profile(profile)
    source_poses = _sample_source_poses(source_clip, sample_rate)
    if not source_poses:
        raise KotorToUnrealSolveError("Source clip has no sampled poses.")
    source_reference = _convert_source_pose(source_clip.rest_pose, basis_conversion)
    converted_source_poses = [_convert_source_pose(pose, basis_conversion) for pose in source_poses]
    target_to_source = {entry.target_node: entry.source_node for entry in normalized.mappings}
    previous_quat_by_target: dict[str, tuple[float, float, float, float]] = {}
    poses: list[UnrealAnimationPose] = []

    for source_pose in converted_source_poses:
        local_transforms: dict[str, Transform] = {}
        global_transforms: dict[str, Transform] = {}
        for node in sorted(target_skeleton.nodes, key=lambda item: item.index):
            parent_world_rotation = None
            if node.parent_name and node.parent_name in global_transforms:
                parent_world_rotation = global_transforms[node.parent_name].rotation
            local = _local_transform_for_target(
                node=node,
                source_pose=source_pose,
                source_reference=source_reference,
                source_node_name=target_to_source.get(node.name),
                parent_world_rotation=parent_world_rotation,
                previous_quat_by_target=previous_quat_by_target,
                root_motion_policy=root_motion_policy,
            )
            local_transforms[node.name] = local
            global_transforms[node.name] = _compose_global(node, target_skeleton, local_transforms, global_transforms)
        poses.append(
            UnrealAnimationPose(
                time_seconds=float(source_pose.time_seconds),
                local_transforms=local_transforms,
                global_transforms=global_transforms,
            )
        )

    return UnrealAnimationClip(
        clip_name=clip_name,
        duration_seconds=float(source_clip.duration_seconds),
        sample_rate=float(sample_rate or source_clip.sample_rate or 30.0),
        target_skeleton_name=target_skeleton.name,
        poses=poses,
        axis_system=target_skeleton.axis_system,
        unit_scale_to_meters=float(target_skeleton.unit_scale_to_meters),
        metadata={
            "source_clip_name": source_clip.clip_name,
            "source_axis_system": source_clip.axis_system,
            "root_motion_policy": root_motion_policy,
            "basis_conversion": "custom" if basis_conversion is not None else "identity",
        },
    )


def audit_unreal_animation_clip(
    clip: UnrealAnimationClip,
    target_skeleton: UnrealTargetSkeleton,
    *,
    root_motion_policy: str = "in_place",
) -> ValidationReport:
    """Validate baked UE clip transforms."""

    issues: list[ValidationIssue] = []
    if not str(clip.clip_name or "").strip():
        issues.append(_issue("unreal_clip.name", "UE animation clip name is empty."))
    if not clip.poses:
        issues.append(_issue("unreal_clip.empty", "UE animation clip contains no sampled poses."))
        return ValidationReport(issues=issues, source="retarget.kotor_to_unreal.clip")

    target_names = set(target_skeleton.node_names)
    previous_time = -math.inf
    root = _root_node(target_skeleton)
    root_rest = root.rest_local.position if root is not None else (0.0, 0.0, 0.0)
    by_name = target_skeleton.node_by_name()
    for pose in clip.poses:
        if pose.time_seconds < previous_time:
            issues.append(_issue("unreal_clip.unsorted_times", "UE animation sample times are not sorted."))
        previous_time = pose.time_seconds
        unknown = sorted(set(pose.local_transforms) - target_names)
        if unknown:
            issues.append(
                _issue(
                    "unreal_clip.unknown_target_node",
                    "UE animation pose contains unknown target bone(s): " + ", ".join(unknown),
                )
            )
        for node_name, transform in pose.local_transforms.items():
            if not transform.is_finite():
                issues.append(
                    _issue(
                        "unreal_clip.non_finite_transform",
                        f"UE animation clip produced a non-finite transform for '{node_name}' at t={pose.time_seconds:.3f}.",
                        node_name=node_name,
                    )
                )
            q = normalize_quat_xyzw(transform.rotation)
            norm = math.sqrt(sum(value * value for value in q))
            if abs(1.0 - norm) > 1e-4:
                issues.append(
                    _issue(
                        "unreal_clip.quaternion_norm",
                        f"UE animation clip quaternion for '{node_name}' at t={pose.time_seconds:.3f} is not normalized.",
                        severity=ValidationSeverity.ERROR,
                        node_name=node_name,
                    )
                )
            node = by_name.get(node_name)
            if node is not None and node.parent_name is not None:
                rest_pos = node.rest_local.position
                if _distance(transform.position, rest_pos) > 1e-5:
                    issues.append(
                        _issue(
                            "unreal_clip.non_root_translation",
                            f"Non-root UE bone '{node_name}' changed local translation at t={pose.time_seconds:.3f}.",
                            severity=ValidationSeverity.ERROR,
                            node_name=node_name,
                        )
                    )
        if root is not None and root.name in pose.local_transforms and root_motion_policy == "in_place":
            root_pos = pose.local_transforms[root.name].position
            if _horizontal_distance(root_pos, root_rest) > 1e-5:
                issues.append(
                    _issue(
                        "unreal_clip.root_motion_not_stripped",
                        f"Root motion was not stripped at t={pose.time_seconds:.3f}.",
                        severity=ValidationSeverity.ERROR,
                        node_name=root.name,
                    )
                )
    return ValidationReport(issues=issues, source="retarget.kotor_to_unreal.clip")


def _sample_source_poses(source_clip: SourceSkeletonClip, sample_rate: Optional[float]) -> list[SourcePose]:
    if sample_rate is None:
        return list(source_clip.sampled_poses)
    rate = float(sample_rate)
    if rate <= 0.0:
        raise KotorToUnrealSolveError("KOTOR → Unreal sample_rate must be positive.")
    duration = max(0.0, float(source_clip.duration_seconds))
    if duration <= 0.0:
        return [source_clip.pose_at_time(0.0)]
    frame_count = int(math.floor(duration * rate + 1e-7))
    times = {0.0, duration}
    for frame in range(frame_count + 1):
        times.add(round(min(duration, frame / rate), 10))
    return [source_clip.pose_at_time(time_value) for time_value in sorted(times)]


def _convert_source_pose(pose: SourcePose, basis_conversion: Optional[BasisConversion]) -> SourcePose:
    if basis_conversion is None:
        return pose
    return SourcePose(
        time_seconds=pose.time_seconds,
        global_transforms={name: basis_conversion.convert_transform(transform) for name, transform in pose.global_transforms.items()},
        local_transforms={name: basis_conversion.convert_transform(transform) for name, transform in pose.local_transforms.items()},
    )


def _local_transform_for_target(
    *,
    node: UnrealSkeletonNode,
    source_pose: SourcePose,
    source_reference: SourcePose,
    source_node_name: str | None,
    parent_world_rotation,
    previous_quat_by_target: dict[str, tuple[float, float, float, float]],
    root_motion_policy: str,
) -> Transform:
    rest_local = node.rest_local
    if source_node_name and source_node_name in source_pose.global_transforms and source_node_name in source_reference.global_transforms:
        desired_world_rotation = transfer_reference_frame_delta(
            source_anim_rotation=source_pose.global_transforms[source_node_name].rotation,
            source_reference_rotation=source_reference.global_transforms[source_node_name].rotation,
            target_reference_rotation=node.rest_global.rotation,
        )
        if node.parent_name:
            local_rotation = _local_rotation_from_world(parent_world_rotation, desired_world_rotation)
        else:
            local_rotation = desired_world_rotation
    else:
        local_rotation = rest_local.rotation
    local_rotation = hemisphere_continuity_xyzw(local_rotation, previous_quat_by_target.get(node.name))
    previous_quat_by_target[node.name] = local_rotation
    position = rest_local.position
    if node.parent_name is None and root_motion_policy != "in_place" and source_node_name:
        source_transform = source_pose.local_transforms.get(source_node_name)
        if source_transform is not None:
            position = source_transform.position
    return Transform(position=position, rotation=local_rotation, scale=rest_local.scale)


def _local_rotation_from_world(parent_world_rotation, desired_world_rotation) -> tuple[float, float, float, float]:
    if parent_world_rotation is None:
        return normalize_quat_xyzw(desired_world_rotation)
    parent_matrix = quat_to_matrix_xyzw(parent_world_rotation)[:3, :3]
    desired_matrix = quat_to_matrix_xyzw(desired_world_rotation)[:3, :3]
    local_matrix = np.linalg.inv(parent_matrix) @ desired_matrix
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = _orthonormalized(local_matrix)
    return matrix_to_quat_xyzw(out)


def _compose_global(
    node: UnrealSkeletonNode,
    target_skeleton: UnrealTargetSkeleton,
    local_transforms: dict[str, Transform],
    global_transforms: dict[str, Transform],
) -> Transform:
    local = local_transforms[node.name]
    if not node.parent_name:
        return local
    parent_global = global_transforms[node.parent_name]
    return Transform.from_matrix(parent_global.to_matrix() @ local.to_matrix())


def _root_node(target_skeleton: UnrealTargetSkeleton) -> UnrealSkeletonNode | None:
    return next((node for node in target_skeleton.nodes if node.parent_name is None), None)


def _orthonormalized(matrix: np.ndarray) -> np.ndarray:
    u, _singular, vh = np.linalg.svd(np.asarray(matrix, dtype=np.float64)[:3, :3])
    return u @ vh


def _distance(a, b) -> float:
    return float(np.linalg.norm(np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)))


def _horizontal_distance(a, b) -> float:
    av = np.asarray(a, dtype=np.float64)
    bv = np.asarray(b, dtype=np.float64)
    return float(np.linalg.norm(np.asarray((av[0] - bv[0], av[1] - bv[1]), dtype=np.float64)))


def _issue(
    code: str,
    message: str,
    *,
    severity: ValidationSeverity = ValidationSeverity.BLOCKING,
    node_name: str | None = None,
    details: dict | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,
        subsystem=ValidationSubsystem.RETARGET,
        code=code,
        message=message,
        navigation=ValidationNavigationTarget(node_name=node_name) if node_name else None,
        details=dict(details or {}),
    )
