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
from .retarget_calibration import (
    CalibratedRetargetFrame,
    build_calibrated_retarget_frames,
    current_source_basis_for_frame,
    transfer_calibrated_frame_delta,
)
from .retarget_frame_audit import audit_retarget_reference_frames
from .retarget_frames import transfer_reference_frame_delta
from .retarget_mapping import HELPER_CLASSIFICATIONS, validate_retarget_profile
from .retarget_output_naming import (
    KotorOutputAnimationNameMode,
    coerce_kotor_output_name_mode,
    validate_custom_kotor_animation_name,
)
from .retarget_profile import RetargetProfile, normalize_retarget_profile
from .retarget_solve_audit import RetargetSolveError, RetargetSolveReport, SegmentPoseError
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
    kotor_output_name_mode: KotorOutputAnimationNameMode = KotorOutputAnimationNameMode.VANILLA_SLOT
    allow_custom_kotor_animation_name: bool = False


@dataclass
class RetargetResult:
    """Generated animation plus the diagnostics needed for the next gate."""

    animation_block: Animation
    reference_pair: ReferencePosePair
    report: RetargetSolveReport
    warnings: list[str]


@dataclass(frozen=True)
class _MappedSegment:
    role: str
    side: str
    source_parent: str
    source_child: str
    target_parent: str
    target_child: str


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
        output_name_mode = coerce_kotor_output_name_mode(opts.kotor_output_name_mode)
        validation = validate_retarget_profile(
            normalized_profile,
            source_clip,
            target_model,
            strict=opts.strict,
            allow_custom_kotor_animation_name=(
                opts.allow_custom_kotor_animation_name
                or output_name_mode == KotorOutputAnimationNameMode.CUSTOM_PATCH
            ),
            output_name_mode=output_name_mode,
        )
        if not validation.success:
            raise RetargetSolveError("; ".join(validation.errors))
        validation_warnings = list(validation.warnings)
    else:
        validation_warnings = []

    output_name_mode = coerce_kotor_output_name_mode(opts.kotor_output_name_mode)
    if opts.allow_custom_kotor_animation_name or output_name_mode == KotorOutputAnimationNameMode.CUSTOM_PATCH:
        custom_name = validate_custom_kotor_animation_name(normalized_profile.animation_slot)
        resolved_slot_name = custom_name
        resolved_transtime = 0.25
        resolved_anim_root = str(getattr(getattr(target_model, "root_node", None), "name", "") or getattr(target_model, "name", ""))
    else:
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
        resolved_slot_name = resolved_slot.slot_name
        resolved_transtime = float(resolved_slot.transtime)
        resolved_anim_root = str(resolved_slot.anim_root or "")

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
    calibration_by_target: Dict[str, CalibratedRetargetFrame] = {}
    if opts.rotation_transfer_mode == "calibrated_frame_delta":
        calibration_report = build_calibrated_retarget_frames(normalized_profile, reference_pair)
        warnings.extend(calibration_report.warnings)
        if calibration_report.errors:
            raise RetargetSolveError("; ".join(calibration_report.errors))
        calibration_by_target = calibration_report.by_target_parent()
        if not calibration_by_target:
            warnings.append("No calibrated retarget frames were available; falling back to reference-frame deltas.")

    source_poses = _sample_source_poses(source_clip, opts.sample_rate)
    target_to_source = {entry.target_node: entry.source_node for entry in normalized_profile.mappings}
    mapped_segments = _mapped_segments(normalized_profile)

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
                    mapped_segments=mapped_segments,
                    calibrated_frames_by_target=calibration_by_target,
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
        slot_name=resolved_slot_name,
        duration=float(source_clip.duration_seconds),
        transition_time=resolved_transtime,
        anim_root=resolved_anim_root,
        orientation_tracks=orientation_tracks,
    )

    structural = validate_animation_block_against_model(target_model, animation, strict=True)
    structural.raise_for_errors(animation.name, target_model.name)
    for pose in source_poses:
        evaluate_aurora_animation_pose(target_model, animation, pose.time_seconds)

    segment_pose_errors = _audit_segment_pose_errors(
        target_model=target_model,
        animation=animation,
        source_poses=converted_source_poses,
        source_reference_pose=converted_reference_source,
        target_reference_pair=reference_pair,
        mapped_segments=mapped_segments,
        mode=opts.rotation_transfer_mode,
    )
    max_norm_error = _max_quaternion_norm_error(orientation_tracks)
    max_adjacent_degrees = _max_adjacent_rotation_degrees(orientation_tracks)
    max_segment_error = max((error.angle_degrees for error in segment_pose_errors), default=0.0)
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
        max_segment_direction_error_degrees=max_segment_error,
        segment_pose_errors=segment_pose_errors,
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
    mapped_segments: List[_MappedSegment],
    calibrated_frames_by_target: Dict[str, CalibratedRetargetFrame],
) -> tuple[float, float, float, float]:
    if mode == "calibrated_frame_delta":
        calibrated_frame = calibrated_frames_by_target.get(target_node_name)
        if calibrated_frame is not None:
            current_basis = current_source_basis_for_frame(calibrated_frame, source_pose)
            if current_basis is not None:
                return transfer_calibrated_frame_delta(
                    source_current_basis=current_basis,
                    calibrated_frame=calibrated_frame,
                    target_reference_rotation=target_reference_pair.target_global_transforms[target_node_name].rotation,
                )
    elif mode == "segment_direction":
        segment_rotation = _segment_direction_world_rotation(
            source_pose=source_pose,
            source_reference_pose=source_reference_pose,
            target_reference_pair=target_reference_pair,
            target_node_name=target_node_name,
            mapped_segments=mapped_segments,
        )
        if segment_rotation is not None:
            return segment_rotation
    elif mode != "reference_frame_delta":
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


def _mapped_segments(profile: RetargetProfile) -> List[_MappedSegment]:
    """Return mapped parent->child limb/body segments for pose-direction solving."""

    by_key: dict[tuple[str, str], object] = {}
    for entry in profile.mappings:
        role = str(entry.role or "").lower()
        side = str(entry.side or "center").lower()
        by_key[(role, side)] = entry

    pairs = (
        ("clavicle", "upperarm"),
        ("upperarm", "forearm"),
        ("forearm", "hand"),
        ("thigh", "calf"),
        ("calf", "foot"),
        ("foot", "toe"),
        ("spine", "chest"),
        ("chest", "neck"),
        ("neck", "head"),
    )
    segments: List[_MappedSegment] = []
    for parent_role, child_role in pairs:
        for side in sorted({key_side for _key_role, key_side in by_key if key_side}):
            parent = by_key.get((parent_role, side))
            child = by_key.get((child_role, side))
            if parent is None or child is None:
                continue
            segments.append(
                _MappedSegment(
                    role=f"{parent_role}->{child_role}",
                    side=side,
                    source_parent=parent.source_node,
                    source_child=child.source_node,
                    target_parent=parent.target_node,
                    target_child=child.target_node,
                )
            )
    return segments


def _segment_direction_world_rotation(
    *,
    source_pose: SourcePose,
    source_reference_pose: SourcePose,
    target_reference_pair: ReferencePosePair,
    target_node_name: str,
    mapped_segments: List[_MappedSegment],
) -> tuple[float, float, float, float] | None:
    segment = next((item for item in mapped_segments if item.target_parent == target_node_name), None)
    if segment is None:
        return None
    try:
        source_current_parent = source_pose.global_transforms[segment.source_parent]
        source_current_child = source_pose.global_transforms[segment.source_child]
        source_ref_parent = source_reference_pose.global_transforms[segment.source_parent]
        source_ref_child = source_reference_pose.global_transforms[segment.source_child]
        target_ref_parent = target_reference_pair.target_global_transforms[segment.target_parent]
        target_ref_child = target_reference_pair.target_global_transforms[segment.target_child]
    except KeyError:
        return None

    source_ref_dir = _segment_direction(source_ref_parent.position, source_ref_child.position)
    source_current_dir = _segment_direction(source_current_parent.position, source_current_child.position)
    target_ref_dir = _segment_direction(target_ref_parent.position, target_ref_child.position)
    if source_ref_dir is None or source_current_dir is None or target_ref_dir is None:
        return None

    source_frame = _frame_from_primary(source_ref_dir, source_ref_parent.rotation)
    target_frame = _frame_from_primary(target_ref_dir, target_ref_parent.rotation)
    source_current_local = source_frame.T @ source_current_dir
    target_desired_dir = _normalize_vec(target_frame @ source_current_local)
    if target_desired_dir is None:
        return None

    swing = _shortest_arc_matrix(target_ref_dir, target_desired_dir)
    target_ref_rot = quat_to_matrix_xyzw(target_ref_parent.rotation)[:3, :3]
    desired = swing @ target_ref_rot
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = _orthonormalized(desired)
    return matrix_to_quat_xyzw(out)


def _segment_direction(parent_position, child_position) -> np.ndarray | None:
    raw = np.asarray(child_position, dtype=np.float64) - np.asarray(parent_position, dtype=np.float64)
    return _normalize_vec(raw)


def _normalize_vec(value) -> np.ndarray | None:
    vec = np.asarray(value, dtype=np.float64)
    length = float(np.linalg.norm(vec))
    if length <= 1e-8 or not math.isfinite(length):
        return None
    return vec / length


def _frame_from_primary(primary: np.ndarray, reference_rotation) -> np.ndarray:
    x_axis = _normalize_vec(primary)
    if x_axis is None:
        return np.eye(3, dtype=np.float64)
    ref = quat_to_matrix_xyzw(reference_rotation)[:3, :3]
    helper = ref[:, 1]
    helper_norm = _normalize_vec(helper)
    if helper_norm is None or abs(float(np.dot(x_axis, helper_norm))) > 0.95:
        helper = ref[:, 2]
        helper_norm = _normalize_vec(helper)
    if helper_norm is None or abs(float(np.dot(x_axis, helper_norm))) > 0.95:
        helper = np.asarray((0.0, 0.0, 1.0), dtype=np.float64)
        helper_norm = _normalize_vec(helper)
    if helper_norm is None or abs(float(np.dot(x_axis, helper_norm))) > 0.95:
        helper = np.asarray((0.0, 1.0, 0.0), dtype=np.float64)
    z_axis = _normalize_vec(np.cross(x_axis, helper))
    if z_axis is None:
        z_axis = np.asarray((0.0, 0.0, 1.0), dtype=np.float64)
    y_axis = _normalize_vec(np.cross(z_axis, x_axis))
    if y_axis is None:
        y_axis = np.asarray((0.0, 1.0, 0.0), dtype=np.float64)
    return np.column_stack((x_axis, y_axis, z_axis))


def _shortest_arc_matrix(source_dir: np.ndarray, target_dir: np.ndarray) -> np.ndarray:
    source = _normalize_vec(source_dir)
    target = _normalize_vec(target_dir)
    if source is None or target is None:
        return np.eye(3, dtype=np.float64)
    dot = max(-1.0, min(1.0, float(np.dot(source, target))))
    if dot > 0.999999:
        return np.eye(3, dtype=np.float64)
    if dot < -0.999999:
        axis = _normalize_vec(np.cross(source, np.asarray((1.0, 0.0, 0.0), dtype=np.float64)))
        if axis is None:
            axis = _normalize_vec(np.cross(source, np.asarray((0.0, 1.0, 0.0), dtype=np.float64)))
        if axis is None:
            axis = np.asarray((0.0, 0.0, 1.0), dtype=np.float64)
        return _axis_angle_matrix(axis, math.pi)
    axis = _normalize_vec(np.cross(source, target))
    if axis is None:
        axis = np.asarray((0.0, 0.0, 1.0), dtype=np.float64)
    return _axis_angle_matrix(axis, math.acos(dot))


def _axis_angle_matrix(axis: np.ndarray, angle: float) -> np.ndarray:
    axis = _normalize_vec(axis)
    if axis is None:
        return np.eye(3, dtype=np.float64)
    x, y, z = axis
    c = math.cos(float(angle))
    s = math.sin(float(angle))
    t = 1.0 - c
    return np.asarray(
        (
            (t * x * x + c, t * x * y - s * z, t * x * z + s * y),
            (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
            (t * x * z - s * y, t * y * z + s * x, t * z * z + c),
        ),
        dtype=np.float64,
    )


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


def _audit_segment_pose_errors(
    *,
    target_model: KotorModel,
    animation: Animation,
    source_poses: List[SourcePose],
    source_reference_pose: SourcePose,
    target_reference_pair: ReferencePosePair,
    mapped_segments: List[_MappedSegment],
    mode: str,
) -> List[SegmentPoseError]:
    if mode not in {"segment_direction", "calibrated_frame_delta"} or not mapped_segments:
        return []
    errors: List[SegmentPoseError] = []
    for source_pose in source_poses:
        target_pose = evaluate_aurora_animation_pose(target_model, animation, source_pose.time_seconds)
        for segment in mapped_segments:
            try:
                actual_parent = target_pose.world_transforms_by_node[segment.target_parent]
                actual_child = target_pose.world_transforms_by_node[segment.target_child]
                target_ref_parent = target_reference_pair.target_global_transforms[segment.target_parent]
                target_ref_child = target_reference_pair.target_global_transforms[segment.target_child]
                source_current_parent = source_pose.global_transforms[segment.source_parent]
                source_current_child = source_pose.global_transforms[segment.source_child]
                source_ref_parent = source_reference_pose.global_transforms[segment.source_parent]
                source_ref_child = source_reference_pose.global_transforms[segment.source_child]
            except KeyError:
                continue

            actual_dir = _segment_direction(actual_parent.position, actual_child.position)
            target_ref_dir = _segment_direction(target_ref_parent.position, target_ref_child.position)
            source_ref_dir = _segment_direction(source_ref_parent.position, source_ref_child.position)
            source_current_dir = _segment_direction(source_current_parent.position, source_current_child.position)
            if actual_dir is None or target_ref_dir is None or source_ref_dir is None or source_current_dir is None:
                continue
            source_frame = _frame_from_primary(source_ref_dir, source_ref_parent.rotation)
            target_frame = _frame_from_primary(target_ref_dir, target_ref_parent.rotation)
            desired_dir = _normalize_vec(target_frame @ (source_frame.T @ source_current_dir))
            if desired_dir is None:
                continue
            angle = _angle_between_degrees(actual_dir, desired_dir)
            errors.append(
                SegmentPoseError(
                    role=segment.role,
                    side=segment.side,
                    source_parent=segment.source_parent,
                    source_child=segment.source_child,
                    target_parent=segment.target_parent,
                    target_child=segment.target_child,
                    time_seconds=float(source_pose.time_seconds),
                    angle_degrees=angle,
                )
            )
    return errors


def _angle_between_degrees(a: np.ndarray, b: np.ndarray) -> float:
    a_norm = _normalize_vec(a)
    b_norm = _normalize_vec(b)
    if a_norm is None or b_norm is None:
        return 0.0
    dot = max(-1.0, min(1.0, float(np.dot(a_norm, b_norm))))
    return math.degrees(math.acos(dot))


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
