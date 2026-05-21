"""First basic UE-source clip to KOTOR/Aurora animation retarget solver."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Iterable, List, Optional

import numpy as np

from src.core.animation.animation_engine import evaluate_aurora_animation_pose
from src.core.game.kotor_loader import resolve_animation_slot
from src.core.geometry.model_data import Animation, KotorModel, ModelNode
from src.core.validation.animation_block_validator import validate_animation_block_against_model

from .coordinate import BasisConversion
from .reference_pose import ReferencePosePair, build_reference_pose_pair
from .retarget_frame_audit import audit_retarget_reference_frames
from .retarget_frames import transfer_reference_frame_delta
from .retarget_mapping import HELPER_CLASSIFICATIONS, validate_retarget_profile
from .retarget_profile import RetargetProfile, normalize_retarget_profile
from .retarget_solve_audit import RetargetSolveError, RetargetSolveReport
from .root_motion import compute_target_local_translation_for_retarget
from .source_animation import (
    SourcePose,
    SourceSkeletonClip,
    Transform,
    hemisphere_continuity_xyzw,
    matrix_to_quat_xyzw,
    normalize_quat_xyzw,
    quat_dot_xyzw,
    quat_to_matrix_xyzw,
)


@dataclass
class RetargetSolverOptions:
    """Options for the first conservative Aurora animation solve."""

    sample_rate: Optional[float] = None
    rotation_transfer_mode: str = "reference_frame_delta"
    root_translation_policy: str = "in_place"
    allow_root_rotation: bool = True
    allow_pelvis_vertical_translation: bool = False
    key_unmapped_reference_nodes: bool = False
    basis_conversion: Optional[BasisConversion] = None
    validate_profile: bool = True
    strict: bool = True


@dataclass
class RetargetResult:
    """Generated animation plus the diagnostics needed for the next gate."""

    animation_block: Animation
    reference_pair: ReferencePosePair
    report: RetargetSolveReport
    warnings: list[str]


def retarget_source_clip_to_aurora_animation(
    *,
    source_clip: SourceSkeletonClip,
    target_model: KotorModel,
    profile: RetargetProfile,
    supermodel_chain=None,
    options: Optional[RetargetSolverOptions] = None,
) -> RetargetResult:
    """Generate a local Aurora animation block from sampled source motion."""

    opts = options or RetargetSolverOptions()
    normalized_profile = normalize_retarget_profile(profile)
    if not normalized_profile.animation_slot:
        raise RetargetSolveError(
            "Retarget profile must specify a valid KOTOR animation slot before generating "
            "an Aurora animation block. UE clip names are not KOTOR animation slot names."
        )
    if normalized_profile.target_reference.get("mode", "target_rest") != "target_rest" and not opts.key_unmapped_reference_nodes:
        raise RetargetSolveError(
            "Basic retarget solver currently requires target_reference.mode='target_rest' "
            "unless key_unmapped_reference_nodes=True."
        )

    if opts.validate_profile:
        validation = validate_retarget_profile(
            normalized_profile,
            source_clip,
            target_model,
            strict=opts.strict,
        )
        if not validation.success:
            raise RetargetSolveError("; ".join(validation.errors))
        validation_warnings = list(validation.warnings)
    else:
        validation_warnings = []

    try:
        resolved_slot = resolve_animation_slot(
            target_model,
            normalized_profile.animation_slot,
            require_valid=True,
        )
    except ValueError as exc:
        raise RetargetSolveError(
            f"Invalid animation slot '{normalized_profile.animation_slot}' for this target model/supermodel chain. "
            "UE clip names are not KOTOR animation slot names."
        ) from exc

    reference_pair = build_reference_pose_pair(
        source_clip=source_clip,
        target_model=target_model,
        profile=normalized_profile,
        supermodel_chain=supermodel_chain,
    )
    warnings = [*validation_warnings, *reference_pair.warnings]
    warnings.extend(_source_classification_warnings(source_clip, normalized_profile))
    if source_clip.axis_system and opts.basis_conversion is None:
        warnings.append(
            f"Source clip axis metadata '{source_clip.axis_system}' is recorded; no basis_conversion was supplied."
        )

    frame_audit = audit_retarget_reference_frames(normalized_profile, reference_pair)
    warnings.extend(frame_audit.warnings)

    source_poses = _sample_source_poses(source_clip, opts.sample_rate)
    source_to_target = {entry.source_node: entry.target_node for entry in normalized_profile.mappings}
    target_to_source = {entry.target_node: entry.source_node for entry in normalized_profile.mappings}
    role_by_target = {entry.target_node: entry.role for entry in normalized_profile.mappings}

    converted_reference_source = _convert_source_pose(reference_pair.source_pose, opts.basis_conversion)
    converted_source_poses = [_convert_source_pose(pose, opts.basis_conversion) for pose in source_poses]

    orientation_tracks: Dict[str, tuple[List[float], List[tuple[float, float, float, float]]]] = {
        entry.target_node: ([], [])
        for entry in normalized_profile.mappings
    }
    previous_quat_by_target: Dict[str, tuple[float, float, float, float]] = {}
    stripped_root_translation = False
    root_warning_seen = False

    target_nodes = target_model.all_nodes()
    target_nodes_by_name = {node.name: node for node in target_nodes}

    for source_pose in converted_source_poses:
        target_fk_world_rotation: Dict[str, tuple[float, float, float, float]] = {}
        target_fk_world_position: Dict[str, tuple[float, float, float]] = {}

        for target_node in target_nodes:
            target_name = target_node.name
            source_name = target_to_source.get(target_name)
            local_translation_result = compute_target_local_translation_for_retarget(
                target_node=target_node,
                target_reference_local=reference_pair.target_local_transforms[target_name],
                source_node_name=source_name,
                source_pose=source_pose,
                source_reference_pose=converted_reference_source,
                root_translation_policy=opts.root_translation_policy,
                allow_pelvis_vertical_translation=opts.allow_pelvis_vertical_translation,
            )
            stripped_root_translation = stripped_root_translation or local_translation_result.stripped_root_translation
            if local_translation_result.warning and not root_warning_seen:
                warnings.append(local_translation_result.warning)
                root_warning_seen = True

            if source_name is not None:
                desired_world_rotation = _desired_target_world_rotation(
                    source_pose=source_pose,
                    source_reference_pose=converted_reference_source,
                    source_node_name=source_name,
                    target_reference_pair=reference_pair,
                    target_node_name=target_name,
                    mode=opts.rotation_transfer_mode,
                )
                parent_world_rotation = None
                if target_node.parent is not None:
                    parent_world_rotation = target_fk_world_rotation.get(target_node.parent.name)
                if target_node.parent is None or parent_world_rotation is None:
                    local_rotation = desired_world_rotation
                else:
                    local_rotation = _local_rotation_from_world(parent_world_rotation, desired_world_rotation)
                if target_node.parent is None and not opts.allow_root_rotation:
                    local_rotation = reference_pair.target_local_transforms[target_name].rotation
            else:
                local_rotation = reference_pair.target_local_transforms[target_name].rotation

            local_rotation = hemisphere_continuity_xyzw(
                local_rotation,
                previous_quat_by_target.get(target_name),
            )
            previous_quat_by_target[target_name] = local_rotation

            if target_name in orientation_tracks:
                times, values = orientation_tracks[target_name]
                times.append(float(source_pose.time_seconds))
                values.append(local_rotation)

            parent_rotation = None
            parent_position = None
            if target_node.parent is not None:
                parent_rotation = target_fk_world_rotation.get(target_node.parent.name)
                parent_position = target_fk_world_position.get(target_node.parent.name)
            world_position, world_rotation = _compose_fk(
                parent_position=parent_position,
                parent_rotation=parent_rotation,
                local_position=local_translation_result.position,
                local_rotation=local_rotation,
            )
            target_fk_world_position[target_name] = world_position
            target_fk_world_rotation[target_name] = world_rotation

    animation = _build_animation_block(
        slot_name=resolved_slot.slot_name,
        duration=float(source_clip.duration_seconds),
        transition_time=float(resolved_slot.transtime),
        anim_root=str(resolved_slot.anim_root or ""),
        orientation_tracks=orientation_tracks,
    )

    structural = validate_animation_block_against_model(target_model, animation, strict=True)
    structural.raise_for_errors(animation.name, target_model.name)
    for pose in source_poses:
        evaluate_aurora_animation_pose(target_model, animation, pose.time_seconds)

    max_norm_error = _max_quaternion_norm_error(orientation_tracks)
    max_adjacent_degrees = _max_adjacent_rotation_degrees(orientation_tracks)
    report = RetargetSolveReport(
        generated_slot_name=animation.name,
        duration_seconds=float(animation.length),
        sample_count=len(source_poses),
        mapped_node_count=len(target_to_source),
        generated_orientation_track_count=len(animation.nodes),
        generated_position_track_count=0,
        stripped_root_translation=stripped_root_translation,
        max_quaternion_norm_error=max_norm_error,
        max_adjacent_rotation_degrees=max_adjacent_degrees,
        warnings=warnings,
    )
    return RetargetResult(
        animation_block=animation,
        reference_pair=reference_pair,
        report=report,
        warnings=warnings,
    )


def _sample_source_poses(source_clip: SourceSkeletonClip, sample_rate: Optional[float]) -> List[SourcePose]:
    if sample_rate is None:
        if not source_clip.sampled_poses:
            raise RetargetSolveError("Source clip has no sampled poses.")
        return list(source_clip.sampled_poses)
    rate = float(sample_rate)
    if rate <= 0.0:
        raise RetargetSolveError("Retarget solver sample_rate must be positive.")
    duration = max(0.0, float(source_clip.duration_seconds))
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
        global_transforms={
            name: basis_conversion.convert_transform(transform)
            for name, transform in pose.global_transforms.items()
        },
        local_transforms={
            name: basis_conversion.convert_transform(transform)
            for name, transform in pose.local_transforms.items()
        },
    )


def _desired_target_world_rotation(
    *,
    source_pose: SourcePose,
    source_reference_pose: SourcePose,
    source_node_name: str,
    target_reference_pair: ReferencePosePair,
    target_node_name: str,
    mode: str,
) -> tuple[float, float, float, float]:
    if mode != "reference_frame_delta":
        raise RetargetSolveError(f"Unsupported rotation transfer mode '{mode}'.")
    source_current = source_pose.global_transforms[source_node_name].rotation
    source_reference = source_reference_pose.global_transforms[source_node_name].rotation
    target_reference = target_reference_pair.target_global_transforms[target_node_name].rotation
    return transfer_reference_frame_delta(
        source_anim_rotation=source_current,
        source_reference_rotation=source_reference,
        target_reference_rotation=target_reference,
    )


def _local_rotation_from_world(
    parent_world_rotation,
    desired_world_rotation,
) -> tuple[float, float, float, float]:
    parent_matrix = quat_to_matrix_xyzw(parent_world_rotation)[:3, :3]
    desired_matrix = quat_to_matrix_xyzw(desired_world_rotation)[:3, :3]
    local_matrix = np.linalg.inv(parent_matrix) @ desired_matrix
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = _orthonormalized(local_matrix)
    return matrix_to_quat_xyzw(out)


def _compose_fk(
    *,
    parent_position: Optional[tuple[float, float, float]],
    parent_rotation: Optional[tuple[float, float, float, float]],
    local_position: tuple[float, float, float],
    local_rotation: tuple[float, float, float, float],
) -> tuple[tuple[float, float, float], tuple[float, float, float, float]]:
    local_rot = normalize_quat_xyzw(local_rotation)
    if parent_rotation is None or parent_position is None:
        return (
            tuple(float(value) for value in local_position),
            local_rot,
        )
    parent_rot = normalize_quat_xyzw(parent_rotation)
    parent_matrix = quat_to_matrix_xyzw(parent_rot)[:3, :3]
    rotated_position = parent_matrix @ np.asarray(local_position, dtype=np.float64)
    world_position = tuple(float(a + b) for a, b in zip(parent_position, rotated_position))
    world_rotation_matrix = parent_matrix @ quat_to_matrix_xyzw(local_rot)[:3, :3]
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = _orthonormalized(world_rotation_matrix)
    return world_position, matrix_to_quat_xyzw(out)


def _orthonormalized(matrix: np.ndarray) -> np.ndarray:
    u, _singular, vh = np.linalg.svd(np.asarray(matrix, dtype=np.float64)[:3, :3])
    return u @ vh


def _build_animation_block(
    *,
    slot_name: str,
    duration: float,
    transition_time: float,
    anim_root: str,
    orientation_tracks: Dict[str, tuple[List[float], List[tuple[float, float, float, float]]]],
) -> Animation:
    animation = Animation(
        name=slot_name,
        length=max(0.0, float(duration)),
        transition_time=transition_time,
        anim_root=anim_root,
    )
    for node_name, (times, values) in orientation_tracks.items():
        if not times or not values:
            continue
        animation.nodes.append(
            ModelNode(
                name=node_name,
                controllers=[
                    {
                        "type": 20,
                        "name": "orientation",
                        "columns": 4,
                        "times": [float(value) for value in times],
                        "values": [list(normalize_quat_xyzw(value)) for value in values],
                    }
                ],
            )
        )
    return animation


def _max_quaternion_norm_error(
    tracks: Dict[str, tuple[List[float], List[tuple[float, float, float, float]]]]
) -> float:
    max_error = 0.0
    for _times, values in tracks.values():
        for quat in values:
            norm = math.sqrt(sum(float(value) * float(value) for value in quat))
            max_error = max(max_error, abs(1.0 - norm))
    return max_error


def _max_adjacent_rotation_degrees(
    tracks: Dict[str, tuple[List[float], List[tuple[float, float, float, float]]]]
) -> float:
    max_degrees = 0.0
    for _times, values in tracks.values():
        for previous, current in zip(values, values[1:]):
            dot = abs(quat_dot_xyzw(previous, current))
            dot = max(-1.0, min(1.0, dot))
            max_degrees = max(max_degrees, math.degrees(2.0 * math.acos(dot)))
    return max_degrees


def _source_classification_warnings(
    source_clip: SourceSkeletonClip,
    profile: RetargetProfile,
) -> List[str]:
    mapped_sources = {entry.source_node.lower() for entry in profile.mappings}
    warnings: List[str] = []
    skipped = [
        node.name
        for node in source_clip.nodes
        if node.classification in HELPER_CLASSIFICATIONS and node.name.lower() not in mapped_sources
    ]
    if skipped:
        warnings.append(
            "Skipped source twist/IK/helper nodes for the basic solver: "
            + ", ".join(skipped[:12])
            + (" ..." if len(skipped) > 12 else "")
        )
    return warnings
