"""R3.B preview bridge for verified UE/FBX source clips targeting Aurora MDLs.

The generic retarget solver is intentionally conservative, but the PMBAM UE idle
workflow was validated through the R3.B Aurora writer's hybrid local-basis path.
This module adapts an already-imported ``SourceSkeletonClip`` back into the
R3.A-style payload shape consumed by that writer so Workbench preview and export
use the same animation generation logic.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np

from src.core.geometry.model_data import Animation, KotorModel
from src.core.validation.animation_block_validator import validate_animation_block_against_model

from .aurora_animation_writer import AuroraAnimationWriter
from .coordinate import BasisConversion
from .reference_pose import build_reference_pose_pair
from .retarget_mapping import validate_retarget_profile
from .retarget_output_naming import KotorOutputAnimationNameMode, coerce_kotor_output_name_mode
from .retarget_profile import RetargetProfile, normalize_retarget_profile
from .retarget_solve_audit import RetargetSolveError, RetargetSolveReport
from .retarget_solver import RetargetResult, RetargetSolverOptions
from .source_animation import (
    SourcePose,
    SourceSkeletonClip,
    Transform,
    matrix_to_quat_xyzw,
    normalize_quat_xyzw,
    quat_to_matrix_xyzw,
)


VERIFIED_UE5_TO_AURORA_PROFILE_GENERATOR = "verified_ue5_to_aurora_mapping"
VERIFIED_MIXAMO_TO_AURORA_PROFILE_GENERATOR = "verified_mixamo_to_aurora_mapping"
VERIFIED_SOURCE_TO_AURORA_PROFILE_GENERATORS = {
    VERIFIED_UE5_TO_AURORA_PROFILE_GENERATOR,
    VERIFIED_MIXAMO_TO_AURORA_PROFILE_GENERATOR,
}
EXACT_PM_BAM_SEGMENT_PAIRS = (
    ("upperarm", "forearm"),
    ("forearm", "hand"),
    ("hand", "middle_base"),
    ("middle_base", "middle_tip"),
    ("thigh", "calf"),
    ("calf", "foot"),
    ("foot", "toe"),
)


@dataclass(frozen=True)
class R3BPayloadBuildResult:
    """R3.A-compatible payload plus warnings produced while adapting a clip."""

    payload: dict
    warnings: list[str]


def should_use_r3b_preview_path(profile: RetargetProfile) -> bool:
    """Return True when ``profile`` uses a verified source-family mapping."""

    normalized = normalize_retarget_profile(profile)
    generated_by = str(normalized.metadata.get("generated_by") or "")
    return generated_by in VERIFIED_SOURCE_TO_AURORA_PROFILE_GENERATORS


def build_r3b_ue5_to_aurora_retarget_result(
    *,
    source_clip: SourceSkeletonClip,
    target_model: KotorModel,
    profile: RetargetProfile,
    supermodel_chain=None,
    options: RetargetSolverOptions | None = None,
) -> RetargetResult:
    """Build an Aurora animation using the proven R3.B local-basis writer path."""

    opts = options or RetargetSolverOptions()
    normalized_profile = normalize_retarget_profile(profile)
    if not normalized_profile.animation_slot:
        raise RetargetSolveError("R3.B preview requires a target output animation name.")

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

    reference_pair = build_reference_pose_pair(
        source_clip=source_clip,
        target_model=target_model,
        profile=normalized_profile,
        supermodel_chain=supermodel_chain,
    )
    payload_result = build_r3a_payload_from_source_clip(
        source_clip=source_clip,
        target_model=target_model,
        profile=normalized_profile,
    )
    warnings = [
        *validation.warnings,
        *reference_pair.warnings,
        *payload_result.warnings,
    ]
    writer = AuroraAnimationWriter()
    animation = writer.build_animation_from_r3a(
        payload=payload_result.payload,
        model=target_model,
        slot_name=normalized_profile.animation_slot,
        fps=float(source_clip.sample_rate or 30.0),
        write_zero_position_controllers=False,
        source_reference_mode="hybrid_limb_source_rest",
        hybrid_limb_source_rest_weight=0.35,
        warnings=warnings,
    )
    corrected_segments = apply_verified_pmbam_segment_pose_correction(
        animation=animation,
        source_clip=source_clip,
        target_model=target_model,
        profile=normalized_profile,
        basis_conversion=opts.basis_conversion,
    )
    if corrected_segments:
        warnings.append(
            "R3.B exact PMBAM segment correction aligned "
            f"{corrected_segments} limb/hand/foot segment tracks against the source clip."
        )
    amplitude_issues = writer._validate_export_motion_amplitude(payload_result.payload, animation)
    if amplitude_issues:
        raise RetargetSolveError(
            "R3.B preview flattened source motion before viewport playback: "
            + "; ".join(amplitude_issues[:8])
        )

    structural = validate_animation_block_against_model(target_model, animation, strict=True)
    structural.raise_for_errors(animation.name, target_model.name)

    report = _build_report(
        animation=animation,
        source_clip=source_clip,
        profile=normalized_profile,
        warnings=warnings,
    )
    return RetargetResult(
        animation_block=animation,
        reference_pair=reference_pair,
        report=report,
        warnings=warnings,
    )


def apply_verified_pmbam_segment_pose_correction(
    *,
    animation: Animation,
    source_clip: SourceSkeletonClip,
    target_model: KotorModel,
    profile: RetargetProfile,
    basis_conversion: BasisConversion | None = None,
) -> int:
    """Post-correct PMBAM limb segment directions while preserving R3.B twist.

    The visually approved PMBAM idle candidate used the R3.B local-basis writer
    as a stable starting point, then applied exact segment pose correction to
    arms, hands/fingers, thighs, shins, feet, and toes.  This function promotes
    that final pass into Workbench preview: for each sampled frame it rotates
    the target segment parent from its R3.B pose just enough to align the target
    child direction with the converted UE source segment direction.
    """

    segments = _mapped_exact_segments(profile)
    if not segments:
        return 0
    animation_tracks = _orientation_tracks(animation)
    if not animation_tracks:
        return 0

    target_nodes = list(target_model.all_nodes())
    target_by_key = {node.name.lower(): node.name for node in target_nodes}
    corrected_count = 0
    source_poses = [_convert_pose_for_segment_correction(pose, basis_conversion) for pose in source_clip.sampled_poses]
    for frame_index, source_pose in enumerate(source_poses):
        local_rotations = _local_rotations_for_frame(target_nodes, animation_tracks, frame_index)
        for source_parent, source_child, target_parent, target_child in segments:
            actual_target_parent = target_by_key.get(target_parent.lower(), target_parent)
            actual_target_child = target_by_key.get(target_child.lower(), target_child)
            if actual_target_parent not in local_rotations or actual_target_child not in local_rotations:
                continue
            try:
                source_parent_pos = source_pose.global_transforms[source_parent].position
                source_child_pos = source_pose.global_transforms[source_child].position
            except KeyError:
                continue
            world_positions, world_rotations = _compose_target_fk(target_nodes, local_rotations)
            actual_dir = _segment_direction(
                world_positions.get(actual_target_parent),
                world_positions.get(actual_target_child),
            )
            desired_dir = _segment_direction(source_parent_pos, source_child_pos)
            if actual_dir is None or desired_dir is None:
                continue
            swing = _shortest_arc_matrix(actual_dir, desired_dir)
            current_world = quat_to_matrix_xyzw(world_rotations[actual_target_parent])[:3, :3]
            corrected_world = _orthonormalized(swing @ current_world)
            corrected_world_quat = matrix_to_quat_xyzw(_matrix4(corrected_world))
            target_node = target_model.find_node(actual_target_parent)
            if target_node is None:
                continue
            if target_node.parent is not None and target_node.parent.name in world_rotations:
                corrected_local = _local_rotation_from_world(
                    world_rotations[target_node.parent.name],
                    corrected_world_quat,
                )
            else:
                corrected_local = corrected_world_quat
            local_rotations[actual_target_parent] = corrected_local
            _set_orientation_value(animation_tracks, actual_target_parent, frame_index, corrected_local)
            corrected_count += 1

    _restore_quaternion_continuity(animation_tracks)
    return corrected_count


def build_r3a_payload_from_source_clip(
    *,
    source_clip: SourceSkeletonClip,
    target_model: KotorModel,
    profile: RetargetProfile,
) -> R3BPayloadBuildResult:
    """Adapt ``SourceSkeletonClip`` samples into the R3.A JSON payload schema."""

    normalized_profile = normalize_retarget_profile(profile)
    if not source_clip.sampled_poses:
        raise RetargetSolveError("Source clip has no sampled poses for R3.B preview.")

    source_names = {node.name.lower(): node.name for node in source_clip.nodes}
    parent_by_source = {
        node.name: node.parent_name
        for node in source_clip.nodes
    }
    source_bones = [node.name for node in source_clip.nodes]
    rest_world = {
        node.name: _transform_payload(source_clip.rest_pose.global_transforms[node.name])
        for node in source_clip.nodes
        if node.name in source_clip.rest_pose.global_transforms
    }
    rest_pose_bases = {
        name: dict(value)
        for name, value in rest_world.items()
    }
    target_curves: dict[str, dict] = {}
    warnings: list[str] = []

    for entry in normalized_profile.mappings:
        source_name = source_names.get(entry.source_node.lower(), entry.source_node)
        target_node = target_model.find_node(entry.target_node)
        if target_node is None:
            raise RetargetSolveError(
                f"Verified UE5 -> Aurora profile maps missing target node '{entry.target_node}'."
            )
        if source_name not in rest_world:
            raise RetargetSolveError(
                f"Verified UE5 -> Aurora profile maps missing source node '{entry.source_node}'."
            )

        frames = _frames_for_source(
            source_clip,
            source_name,
            location_override=target_node.position,
        )
        source_parent = parent_by_source.get(source_name)
        parent_frames = _frames_for_source(source_clip, source_parent) if source_parent else []
        curve = {
            "target_bone": target_node.name,
            "source_bone": source_name,
            "role": entry.role,
            "side": entry.side,
            "space": "source_world",
            "conversion_status": "source_clip_to_r3b_preview",
            "source_rest_world": rest_world[source_name],
            "source_rest_basis": rest_pose_bases[source_name],
            "frames": frames,
        }
        if source_parent and source_parent in rest_world:
            curve["source_parent"] = source_parent
            curve["source_parent_rest_world"] = rest_world[source_parent]
            curve["source_parent_rest_basis"] = rest_pose_bases[source_parent]
            curve["source_parent_frames"] = parent_frames
        target_curves[target_node.name] = curve

    payload = {
        "schema": "r3a_payload_from_source_skeleton_clip",
        "source_path": source_clip.source_path,
        "action_name": source_clip.clip_name,
        "target_slot": normalized_profile.animation_slot,
        "fps": float(source_clip.sample_rate or 30.0),
        "frame_count": len(source_clip.sampled_poses),
        "duration_seconds": float(source_clip.duration_seconds or 0.0),
        "source_bones": source_bones,
        "bone_parents": parent_by_source,
        "axis_system": source_clip.axis_system,
        "unit_scale_to_meters": source_clip.unit_scale_to_meters,
        "handedness": source_clip.handedness,
        "rest_world": rest_world,
        "rest_pose_bases": rest_pose_bases,
        "target_curves": target_curves,
        "metadata": {
            "generated_by": "SourceSkeletonClip R3.B preview bridge",
            "profile": normalized_profile.name,
            "profile_generated_by": normalized_profile.metadata.get("generated_by"),
        },
    }
    if not target_curves:
        raise RetargetSolveError("Verified UE5 -> Aurora profile produced no R3.B target curves.")
    warnings.append(
        "Workbench preview uses the verified R3.B hybrid local-basis path for UE/FBX -> PMBAM retargeting."
    )
    return R3BPayloadBuildResult(payload=payload, warnings=warnings)


def _frames_for_source(
    source_clip: SourceSkeletonClip,
    source_name: str | None,
    *,
    location_override: Iterable[float] | None = None,
) -> list[dict]:
    if not source_name:
        return []
    frames: list[dict] = []
    for index, pose in enumerate(source_clip.sampled_poses):
        transform = pose.global_transforms.get(source_name)
        if transform is None:
            continue
        payload = _transform_payload(transform)
        if location_override is not None:
            payload["location_xyz"] = [float(value) for value in list(location_override)[:3]]
        frames.append(
            {
                "frame": index,
                "time_seconds": float(pose.time_seconds),
                **payload,
            }
        )
    return frames


def _transform_payload(transform: Transform) -> dict:
    matrix = transform.to_matrix()
    rotation = _xyzw_to_wxyz(transform.rotation)
    position = [float(value) for value in transform.position]
    return {
        "rotation_wxyz": rotation,
        "location_xyz": position,
        "matrix": _matrix_rows(matrix),
        "world_matrix_at_rest": _matrix_rows(matrix),
    }


def _xyzw_to_wxyz(quat: Iterable[float]) -> list[float]:
    x, y, z, w = normalize_quat_xyzw(quat)
    return [float(w), float(x), float(y), float(z)]


def _matrix_rows(matrix) -> list[list[float]]:
    return [[float(value) for value in row] for row in matrix]


def _build_report(
    *,
    animation: Animation,
    source_clip: SourceSkeletonClip,
    profile: RetargetProfile,
    warnings: list[str],
) -> RetargetSolveReport:
    orientation_count = 0
    position_count = 0
    max_norm_error = 0.0
    max_adjacent_degrees = 0.0
    for anim_node in getattr(animation, "nodes", []) or []:
        for ctrl in getattr(anim_node, "controllers", []) or []:
            ctrl_type = ctrl.get("type")
            if ctrl_type == 20:
                orientation_count += 1
                previous = None
                for value in ctrl.get("values", []) or []:
                    quat = normalize_quat_xyzw(value)
                    norm = math.sqrt(sum(component * component for component in quat))
                    max_norm_error = max(max_norm_error, abs(1.0 - norm))
                    if previous is not None:
                        dot = abs(sum(a * b for a, b in zip(previous, quat)))
                        dot = max(-1.0, min(1.0, dot))
                        max_adjacent_degrees = max(
                            max_adjacent_degrees,
                            math.degrees(2.0 * math.acos(dot)),
                        )
                    previous = quat
            elif ctrl_type == 8:
                position_count += 1
    return RetargetSolveReport(
        generated_slot_name=animation.name,
        duration_seconds=float(animation.length or source_clip.duration_seconds or 0.0),
        sample_count=len(source_clip.sampled_poses),
        mapped_node_count=len(profile.mappings),
        generated_orientation_track_count=orientation_count,
        generated_position_track_count=position_count,
        stripped_root_translation=True,
        max_quaternion_norm_error=max_norm_error,
        max_adjacent_rotation_degrees=max_adjacent_degrees,
        warnings=list(warnings),
    )


def _mapped_exact_segments(profile: RetargetProfile) -> list[tuple[str, str, str, str]]:
    by_role_side = {
        (str(entry.role or "").lower(), str(entry.side or "center").lower()): entry
        for entry in profile.mappings
    }
    segments: list[tuple[str, str, str, str]] = []
    for parent_role, child_role in EXACT_PM_BAM_SEGMENT_PAIRS:
        sides = sorted({
            side
            for role, side in by_role_side
            if role in {parent_role, child_role} and side
        })
        for side in sides:
            parent = by_role_side.get((parent_role, side)) or by_role_side.get((parent_role, "center"))
            child = by_role_side.get((child_role, side)) or by_role_side.get((child_role, "center"))
            if parent is None or child is None:
                continue
            segments.append(
                (
                    parent.source_node,
                    child.source_node,
                    parent.target_node,
                    child.target_node,
                )
            )
    return segments


def _orientation_tracks(animation: Animation) -> dict[str, tuple[str, dict]]:
    tracks: dict[str, tuple[str, dict]] = {}
    for node in getattr(animation, "nodes", []) or []:
        node_name = str(getattr(node, "name", "") or "")
        for ctrl in getattr(node, "controllers", []) or []:
            if ctrl.get("type") == 20:
                tracks[node_name.lower()] = (node_name, ctrl)
                break
    return tracks


def _local_rotations_for_frame(
    target_nodes,
    tracks: dict[str, tuple[str, dict]],
    frame_index: int,
) -> dict[str, tuple[float, float, float, float]]:
    rotations: dict[str, tuple[float, float, float, float]] = {}
    for node in target_nodes:
        key = str(node.name or "").lower()
        track = tracks.get(key)
        if track is None:
            rotations[node.name] = normalize_quat_xyzw(node.rotation)
            continue
        values = list(track[1].get("values", []) or [])
        if not values:
            rotations[node.name] = normalize_quat_xyzw(node.rotation)
            continue
        index = min(frame_index, len(values) - 1)
        rotations[node.name] = normalize_quat_xyzw(values[index])
    return rotations


def _set_orientation_value(
    tracks: dict[str, tuple[str, dict]],
    node_name: str,
    frame_index: int,
    rotation,
) -> None:
    track = tracks.get(str(node_name or "").lower())
    if track is None:
        return
    values = track[1].setdefault("values", [])
    if not values:
        return
    index = min(frame_index, len(values) - 1)
    values[index] = list(normalize_quat_xyzw(rotation))


def _restore_quaternion_continuity(tracks: dict[str, tuple[str, dict]]) -> None:
    for _node_name, ctrl in tracks.values():
        previous = None
        fixed = []
        for raw in ctrl.get("values", []) or []:
            quat = normalize_quat_xyzw(raw)
            if previous is not None and sum(a * b for a, b in zip(previous, quat)) < 0.0:
                quat = tuple(-value for value in quat)
            fixed.append(list(quat))
            previous = quat
        ctrl["values"] = fixed


def _convert_pose_for_segment_correction(
    pose: SourcePose,
    basis_conversion: BasisConversion | None,
) -> SourcePose:
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


def _compose_target_fk(
    target_nodes,
    local_rotations: dict[str, tuple[float, float, float, float]],
) -> tuple[dict[str, tuple[float, float, float]], dict[str, tuple[float, float, float, float]]]:
    world_positions: dict[str, tuple[float, float, float]] = {}
    world_rotations: dict[str, tuple[float, float, float, float]] = {}
    for node in target_nodes:
        local_rotation = normalize_quat_xyzw(local_rotations.get(node.name, node.rotation))
        local_position = tuple(float(value) for value in node.position)
        if node.parent is None or node.parent.name not in world_rotations:
            world_positions[node.name] = local_position
            world_rotations[node.name] = local_rotation
            continue
        parent_position = np.asarray(world_positions[node.parent.name], dtype=np.float64)
        parent_rotation = world_rotations[node.parent.name]
        parent_matrix = quat_to_matrix_xyzw(parent_rotation)[:3, :3]
        world_position = parent_position + parent_matrix @ np.asarray(local_position, dtype=np.float64)
        world_rotation = parent_matrix @ quat_to_matrix_xyzw(local_rotation)[:3, :3]
        world_positions[node.name] = tuple(float(value) for value in world_position)
        world_rotations[node.name] = matrix_to_quat_xyzw(_matrix4(world_rotation))
    return world_positions, world_rotations


def _local_rotation_from_world(parent_world_rotation, desired_world_rotation) -> tuple[float, float, float, float]:
    parent_matrix = quat_to_matrix_xyzw(parent_world_rotation)[:3, :3]
    desired_matrix = quat_to_matrix_xyzw(desired_world_rotation)[:3, :3]
    local_matrix = np.linalg.inv(parent_matrix) @ desired_matrix
    return matrix_to_quat_xyzw(_matrix4(_orthonormalized(local_matrix)))


def _segment_direction(parent_position, child_position) -> np.ndarray | None:
    if parent_position is None or child_position is None:
        return None
    raw = np.asarray(child_position, dtype=np.float64) - np.asarray(parent_position, dtype=np.float64)
    return _normalize_vec(raw)


def _normalize_vec(value) -> np.ndarray | None:
    vec = np.asarray(value, dtype=np.float64)
    length = float(np.linalg.norm(vec))
    if length <= 1e-8 or not math.isfinite(length):
        return None
    return vec / length


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


def _orthonormalized(matrix: np.ndarray) -> np.ndarray:
    u, _singular, vh = np.linalg.svd(np.asarray(matrix, dtype=np.float64)[:3, :3])
    out = u @ vh
    if float(np.linalg.det(out)) < 0.0:
        out[:, 2] *= -1.0
    return out


def _matrix4(rotation: np.ndarray) -> np.ndarray:
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = np.asarray(rotation, dtype=np.float64)[:3, :3]
    return out
