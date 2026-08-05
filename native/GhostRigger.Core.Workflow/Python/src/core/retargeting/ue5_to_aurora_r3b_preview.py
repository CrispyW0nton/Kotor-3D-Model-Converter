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

from src.core.geometry.model_data import Animation, KotorModel, ModelNode
from src.core.validation.animation_block_validator import validate_animation_block_against_model

from .aurora_animation_writer import (
    CTRL_POSITION,
    AuroraAnimationWriter,
    _slerp_xyzw,
)
from .coordinate import BasisConversion
from .reference_pose import build_reference_pose_pair, compute_target_rest_transforms
from .retarget_mapping import validate_retarget_profile
from .retarget_output_naming import KotorOutputAnimationNameMode, coerce_kotor_output_name_mode
from .retarget_profile import RetargetProfile, normalize_retarget_profile
from .retarget_solve_audit import RetargetSolveError, RetargetSolveReport
from .retarget_solver import RetargetResult, RetargetSolverOptions
from .source_animation import (
    SourcePose,
    SourceSkeletonClip,
    SourceSkeletonNode,
    Transform,
    matrix_to_quat_xyzw,
    normalize_quat_xyzw,
    quat_to_matrix_xyzw,
)


VERIFIED_UE5_TO_AURORA_PROFILE_GENERATOR = "verified_ue5_to_aurora_mapping"
VERIFIED_MIXAMO_TO_AURORA_PROFILE_GENERATOR = "verified_mixamo_to_aurora_mapping"
VERIFIED_SWTOR_BMN_TO_AURORA_PROFILE_GENERATOR = "verified_swtor_bmn_to_aurora_mapping"
VERIFIED_SOURCE_TO_AURORA_PROFILE_GENERATORS = {
    VERIFIED_UE5_TO_AURORA_PROFILE_GENERATOR,
    VERIFIED_MIXAMO_TO_AURORA_PROFILE_GENERATOR,
    VERIFIED_SWTOR_BMN_TO_AURORA_PROFILE_GENERATOR,
}
EXACT_PM_BAM_SEGMENT_PAIRS = (
    ("spine", "chest"),
    ("clavicle", "upperarm"),
    ("upperarm", "forearm"),
    ("forearm", "hand"),
    ("hand", "middle_base"),
    ("middle_base", "middle_tip"),
    ("thigh", "calf"),
    ("calf", "foot"),
    ("foot", "toe"),
)
MIXAMO_PM_BAM_STABLE_HUMANOID_SEGMENT_PAIRS = (
    ("spine", "chest"),
    ("upperarm", "forearm"),
    ("forearm", "hand"),
    ("hand", "middle_base"),
    ("index_base", "index_tip"),
    ("middle_base", "middle_tip"),
    ("ring_base", "ring_tip"),
    ("pinky_base", "pinky_tip"),
    ("thumb_base", "thumb_tip"),
    ("thigh", "calf"),
    ("calf", "foot"),
    ("foot", "toe"),
)
MIXAMO_PM_BAM_LIMB_ONLY_SEGMENT_PAIRS = (
    ("upperarm", "forearm"),
    ("forearm", "hand"),
    ("hand", "middle_base"),
    ("middle_base", "middle_tip"),
    ("thigh", "calf"),
    ("calf", "foot"),
    ("foot", "toe"),
)
PERFORMANCE_LOWER_BODY_SEGMENT_PAIRS = (
    ("thigh", "calf"),
    ("calf", "foot"),
    ("foot", "toe"),
)
PERFORMANCE_ANATOMICAL_SEGMENT_PAIRS = (
    # Correct the large, readable body chains without forcing source finger or
    # wrist axes onto Aurora's differently oriented terminal joints.
    ("spine", "chest"),
    ("upperarm", "forearm"),
    ("forearm", "hand"),
    ("thigh", "calf"),
    ("calf", "foot"),
    ("foot", "toe"),
)
DANCE_ANATOMICAL_SEGMENT_PAIRS = (
    # Keep Aurora's clavicle in its skinned bind-axis frame.  Driving the
    # foreign clavicle->upperarm direction increased the stock Twi'lek mesh's
    # measured shoulder stretch without improving the visible pose.  The two
    # downstream arm segments still reproduce the readable elbow/wrist motion
    # while their shortest-arc corrections preserve KOTOR's axial roll.
    ("spine", "chest"),
    ("upperarm", "forearm"),
    ("forearm", "hand"),
    ("thigh", "calf"),
    ("calf", "foot"),
    ("foot", "toe"),
)
DANCE_CLAVICLE_ANATOMICAL_SEGMENT_PAIRS = (
    # Diagnostic/advanced variant: distribute an authored overhead reach into
    # Aurora's clavicle as another bind-anchored shortest-arc swing.  Unlike
    # the spatial policy below, this still never copies the foreign joint's
    # axial basis.
    ("spine", "chest"),
    ("clavicle", "upperarm"),
    ("upperarm", "forearm"),
    ("forearm", "hand"),
    ("thigh", "calf"),
    ("calf", "foot"),
    ("foot", "toe"),
)
TERMINAL_PM_BAM_TWIST_CHAINS = (
    ("forearm", "hand", "middle_base"),
    ("calf", "foot", "toe"),
)
DANCE_SPATIAL_CHAIN_ROLES = (
    # Retained for the explicit experimental ``dance_spatial_anatomical``
    # policy.  Shipping dance retargets use bind-anchored shortest-arc segment
    # swings instead.  Copying a foreign rig's complete bend-plane basis drove
    # Aurora collar/thigh axial roll as high as 175 degrees and visibly tore
    # the stock shoulder/hip skin even when segment directions were exact.
    ("clavicle", "upperarm", "forearm", "hand", "middle_base"),
    ("thigh", "calf", "foot", "toe"),
)


@dataclass(frozen=True)
class R3BPayloadBuildResult:
    """R3.A-compatible payload plus warnings produced while adapting a clip."""

    payload: dict
    warnings: list[str]


@dataclass(frozen=True)
class DanceSpatialTransferAudit:
    """Every-frame proof that a dance limb solve matches source anatomy."""

    sample_count: int
    chain_count: int
    max_segment_direction_error_degrees: float
    max_bone_basis_error_degrees: float
    max_bend_plane_error_degrees: float
    errors: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.errors


def should_use_r3b_preview_path(profile: RetargetProfile) -> bool:
    """Return True when ``profile`` uses a verified source-family mapping."""

    normalized = normalize_retarget_profile(profile)
    generated_by = str(normalized.metadata.get("generated_by") or "")
    return generated_by in VERIFIED_SOURCE_TO_AURORA_PROFILE_GENERATORS


def build_humanoid_rest_basis_conversion(
    *,
    source_clip: SourceSkeletonClip,
    target_model: KotorModel,
    profile: RetargetProfile,
) -> BasisConversion:
    """Align one imported humanoid's rest frame to the target Aurora frame.

    Blender evaluates FBX transforms in one Z-up world, but it does not erase
    the armature object's authored yaw/pitch/roll.  Mixed-source animation FBXs
    therefore cannot safely share one hard-coded 180-degree Z conversion.  A
    stable actor frame is recovered from mapped anatomy instead: character
    right is left-shoulder -> right-shoulder, up is pelvis -> head, and forward
    is their right-handed cross product.  The returned rigid basis maps that
    source frame onto the target model's rest frame.
    """

    normalized = normalize_retarget_profile(profile)
    source_world = source_clip.rest_pose.global_transforms
    _target_local, target_world = compute_target_rest_transforms(target_model)
    mappings = {
        (str(entry.role or "").lower(), str(entry.side or "center").lower()): entry
        for entry in normalized.mappings
    }

    def mapped_positions(role: str, side: str = "center") -> tuple[np.ndarray, np.ndarray]:
        entry = mappings.get((role, side)) or mappings.get((role, "center"))
        if entry is None:
            raise RetargetSolveError(
                f"Adaptive humanoid basis requires a mapped {side} {role} node."
            )
        source_transform = source_world.get(entry.source_node)
        target_transform = target_world.get(entry.target_node)
        if source_transform is None or target_transform is None:
            raise RetargetSolveError(
                "Adaptive humanoid basis could not resolve mapped rest transforms "
                f"for {entry.source_node!r} -> {entry.target_node!r}."
            )
        return (
            np.asarray(source_transform.position, dtype=np.float64),
            np.asarray(target_transform.position, dtype=np.float64),
        )

    source_left, target_left = mapped_positions("upperarm", "left")
    source_right, target_right = mapped_positions("upperarm", "right")
    source_pelvis, target_pelvis = mapped_positions("pelvis")
    source_head, target_head = mapped_positions("head")

    source_frame = _humanoid_actor_frame(
        right_hint=source_right - source_left,
        up_hint=source_head - source_pelvis,
        label="source",
    )
    target_frame = _humanoid_actor_frame(
        right_hint=target_right - target_left,
        up_hint=target_head - target_pelvis,
        label="target",
    )
    change_of_basis = _orthonormalized(target_frame @ source_frame.T)
    if float(np.linalg.det(change_of_basis)) < 0.999:
        raise RetargetSolveError(
            "Adaptive humanoid basis produced a reflected or degenerate frame."
        )
    return BasisConversion(
        source_basis=change_of_basis,
        target_basis=np.eye(3, dtype=np.float64),
    )


def convert_source_clip_basis(
    source_clip: SourceSkeletonClip,
    basis_conversion: BasisConversion,
) -> SourceSkeletonClip:
    """Return a source clip expressed wholly in one converted coordinate frame.

    The R3.B writer consumes source world rotations while the anatomical
    post-pass consumes positions and rotations.  Converting the complete clip
    once keeps those two paths in the same frame and prevents the previous
    split where the torso used a fixed UE conversion while the limbs used a
    separate solver conversion.
    """

    def convert_pose(pose: SourcePose) -> SourcePose:
        return SourcePose(
            time_seconds=float(pose.time_seconds),
            global_transforms={
                name: basis_conversion.convert_transform(transform)
                for name, transform in pose.global_transforms.items()
            },
            local_transforms={
                name: basis_conversion.convert_transform(transform)
                for name, transform in pose.local_transforms.items()
            },
        )

    converted_rest = convert_pose(source_clip.rest_pose)
    converted_nodes = [
        SourceSkeletonNode(
            name=node.name,
            parent_name=node.parent_name,
            index=int(node.index),
            rest_local=converted_rest.local_transforms[node.name],
            rest_global=converted_rest.global_transforms[node.name],
            classification=node.classification,
        )
        for node in source_clip.nodes
    ]
    return SourceSkeletonClip(
        source_path=source_clip.source_path,
        clip_name=source_clip.clip_name,
        duration_seconds=float(source_clip.duration_seconds),
        sample_rate=float(source_clip.sample_rate),
        nodes=converted_nodes,
        rest_pose=converted_rest,
        sampled_poses=[convert_pose(pose) for pose in source_clip.sampled_poses],
        axis_system="aurora_aligned_humanoid_rest",
        unit_scale_to_meters=source_clip.unit_scale_to_meters,
        handedness=source_clip.handedness,
        import_warnings=[
            *source_clip.import_warnings,
            "Applied one rigid humanoid rest-frame conversion before R3.B writing.",
        ],
        available_clips=list(source_clip.available_clips),
    )


def _humanoid_actor_frame(
    *,
    right_hint: Iterable[float],
    up_hint: Iterable[float],
    label: str,
) -> np.ndarray:
    """Build a proper right/up/forward actor frame from anatomical landmarks."""

    up = _normalize_vec(up_hint)
    if up is None:
        raise RetargetSolveError(f"Adaptive humanoid {label} up axis is degenerate.")
    right_raw = np.asarray(list(right_hint), dtype=np.float64)[:3]
    right = _normalize_vec(right_raw - up * float(np.dot(right_raw, up)))
    if right is None:
        raise RetargetSolveError(f"Adaptive humanoid {label} shoulder axis is degenerate.")
    forward = _normalize_vec(np.cross(right, up))
    if forward is None:
        raise RetargetSolveError(f"Adaptive humanoid {label} forward axis is degenerate.")
    up = _normalize_vec(np.cross(forward, right))
    if up is None:
        raise RetargetSolveError(f"Adaptive humanoid {label} frame is degenerate.")
    frame = _orthonormalized(np.column_stack((right, up, forward)))
    if float(np.linalg.det(frame)) < 0.999:
        raise RetargetSolveError(f"Adaptive humanoid {label} frame is reflected.")
    return frame


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

    working_source_clip = source_clip
    effective_basis_conversion = opts.basis_conversion
    if opts.basis_conversion is not None:
        working_source_clip = convert_source_clip_basis(
            source_clip,
            opts.basis_conversion,
        )
        normalized_profile.metadata = {
            **dict(normalized_profile.metadata or {}),
            "source_quaternion_conversion": "identity",
            "source_basis_conversion_applied": "r3b_whole_clip_pretransform",
        }
        effective_basis_conversion = None

    reference_pair = build_reference_pose_pair(
        source_clip=working_source_clip,
        target_model=target_model,
        profile=normalized_profile,
        supermodel_chain=supermodel_chain,
    )
    payload_result = build_r3a_payload_from_source_clip(
        source_clip=working_source_clip,
        target_model=target_model,
        profile=normalized_profile,
    )
    warnings = [
        *validation.warnings,
        *reference_pair.warnings,
        *payload_result.warnings,
    ]
    if opts.basis_conversion is not None:
        warnings.append(
            "R3.B applied the source basis once to the complete clip before writer, "
            "root, and anatomical-chain evaluation."
        )
    profile_metadata = dict(getattr(normalized_profile, "metadata", {}) or {})
    source_reference_mode = str(
        opts.source_reference_mode
        or profile_metadata.get("source_reference_mode")
        or "hybrid_limb_source_rest"
    )
    hybrid_weight_raw = (
        opts.hybrid_limb_source_rest_weight
        if opts.hybrid_limb_source_rest_weight is not None
        else profile_metadata.get("hybrid_limb_source_rest_weight", 0.35)
    )
    try:
        hybrid_weight = float(hybrid_weight_raw)
    except (TypeError, ValueError):
        hybrid_weight = 0.35
    writer = AuroraAnimationWriter()
    animation = writer.build_animation_from_r3a(
        payload=payload_result.payload,
        model=target_model,
        slot_name=normalized_profile.animation_slot,
        fps=float(working_source_clip.sample_rate or 30.0),
        write_zero_position_controllers=False,
        write_root_position_controllers=False,
        source_reference_mode=source_reference_mode,
        hybrid_limb_source_rest_weight=hybrid_weight,
        warnings=warnings,
    )
    amplitude_issues = writer._validate_export_motion_amplitude(
        payload_result.payload,
        animation,
        model=target_model,
    )
    if amplitude_issues:
        raise RetargetSolveError(
            "R3.B preview flattened source motion before viewport playback: "
            + "; ".join(amplitude_issues[:8])
        )
    if opts.root_translation_policy != "in_place":
        copied_root_motion = apply_r3b_source_root_motion_to_target_root(
            animation=animation,
            source_clip=working_source_clip,
            target_model=target_model,
            profile=normalized_profile,
            basis_conversion=effective_basis_conversion,
        )
        if copied_root_motion:
            warnings.append(
                "R3.B root movement enabled: copied source root motion onto the target model root only."
            )
    corrected_segments = apply_verified_pmbam_segment_pose_correction(
        animation=animation,
        source_clip=working_source_clip,
        target_model=target_model,
        profile=normalized_profile,
        basis_conversion=effective_basis_conversion,
    )
    if corrected_segments:
        warnings.append(
            "R3.B exact KOTOR humanoid segment correction aligned "
            f"{corrected_segments} configured target segment tracks against the source clip."
        )

    dance_audit = audit_dance_spatial_chain_transfer(
        animation=animation,
        source_clip=working_source_clip,
        target_model=target_model,
        profile=normalized_profile,
        basis_conversion=effective_basis_conversion,
    )
    if dance_audit.chain_count:
        if not dance_audit.passed:
            raise RetargetSolveError(
                "Dance spatial anatomy audit failed: "
                + "; ".join(dance_audit.errors[:8])
            )
        warnings.append(
            "Dance spatial anatomy audit passed every sampled frame: "
            f"{dance_audit.chain_count} chains, "
            f"max segment error {dance_audit.max_segment_direction_error_degrees:.4f} deg, "
            f"max axial-basis error {dance_audit.max_bone_basis_error_degrees:.4f} deg, "
            f"max bend-plane error {dance_audit.max_bend_plane_error_degrees:.4f} deg."
        )

    structural = validate_animation_block_against_model(target_model, animation, strict=True)
    structural.raise_for_errors(animation.name, target_model.name)

    report = _build_report(
        animation=animation,
        source_clip=working_source_clip,
        profile=normalized_profile,
        warnings=warnings,
        root_translation_policy=opts.root_translation_policy,
    )
    return RetargetResult(
        animation_block=animation,
        reference_pair=reference_pair,
        report=report,
        warnings=warnings,
    )


def apply_r3b_source_root_motion_to_target_root(
    *,
    animation: Animation,
    source_clip: SourceSkeletonClip,
    target_model: KotorModel,
    profile: RetargetProfile,
    basis_conversion: BasisConversion | None = None,
) -> bool:
    """Copy source root displacement onto the Aurora model root only.

    The verified R3.B bridge intentionally pins each target node's location to
    the target bind pose so PMBAM does not receive destructive pelvis/limb
    translation tracks.  When the Workbench root movement toggle is enabled,
    the safe exception is the top-level model root: moving that node carries the
    whole target character across the floor while preserving child bind offsets.
    Aurora animation position controllers are relative offsets added to the
    node's static local position in the live engine, so emitted keys contain
    only the source displacement.  Writing bind position plus displacement
    doubles the target root height and makes the character float or intersect
    the floor after hierarchy adaptation.
    """

    target_root = getattr(target_model, "root_node", None)
    if target_root is None or not source_clip.sampled_poses:
        return False
    source_root_name = _select_source_root_motion_node(source_clip, profile, target_root.name)
    if not source_root_name:
        return False

    converted_poses = [
        _convert_pose_for_segment_correction(pose, basis_conversion)
        for pose in source_clip.sampled_poses
    ]
    first_pose = converted_poses[0]
    first_transform = first_pose.global_transforms.get(source_root_name)
    if first_transform is None:
        return False

    start_time = float(first_pose.time_seconds)
    reference = np.asarray(first_transform.position, dtype=np.float64)
    times: list[float] = []
    values: list[list[float]] = []
    moved = False
    for pose in converted_poses:
        transform = pose.global_transforms.get(source_root_name)
        if transform is None:
            continue
        delta = np.asarray(transform.position, dtype=np.float64) - reference
        if float(np.linalg.norm(delta)) > 1e-5:
            moved = True
        times.append(round(max(0.0, float(pose.time_seconds) - start_time), 7))
        values.append([float(delta[index]) for index in range(3)])
    if len(times) < 2 or not moved:
        return False

    anim_node = _animation_node_for(animation, target_root.name)
    anim_node.controllers = [
        ctrl
        for ctrl in getattr(anim_node, "controllers", []) or []
        if not (ctrl.get("type") == CTRL_POSITION or str(ctrl.get("name", "")).lower() == "position")
    ]
    anim_node.controllers.insert(
        0,
        {
            "type": CTRL_POSITION,
            "name": "position",
            "columns": 3,
            "times": times,
            "values": values,
        },
    )
    return True


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

    normalized_profile = normalize_retarget_profile(profile)
    metadata = dict(getattr(normalized_profile, "metadata", {}) or {})
    rotation_anchor = str(metadata.get("exact_segment_rotation_anchor") or "").strip().lower()
    arm_strength = max(
        0.0,
        min(1.0, float(metadata.get("exact_segment_arm_strength", 1.0))),
    )
    arm_parent_share = max(
        0.0,
        min(1.0, float(metadata.get("exact_segment_arm_parent_share", 0.0))),
    )
    upperarm_targets = {
        str(entry.target_node or "").strip().lower()
        for entry in normalized_profile.mappings
        if str(entry.role or "").strip().lower() == "upperarm"
    }
    target_nodes = list(target_model.all_nodes())
    target_by_key = {node.name.lower(): node.name for node in target_nodes}
    terminal_chains = _mapped_terminal_twist_chains(profile)
    dance_spatial_chains = _mapped_dance_spatial_chains(profile)
    source_rest_pose = _convert_pose_for_segment_correction(
        source_clip.rest_pose,
        basis_conversion,
    )
    rest_local_rotations = {
        node.name: normalize_quat_xyzw(node.rotation)
        for node in target_nodes
    }
    target_rest_positions, target_rest_rotations = _compose_target_fk(target_nodes, rest_local_rotations)
    corrected_count = 0
    source_poses = [_convert_pose_for_segment_correction(pose, basis_conversion) for pose in source_clip.sampled_poses]
    previous_terminal_basis_by_chain: dict[tuple[str, str, str], np.ndarray] = {}
    previous_dance_plane_by_chain: dict[tuple[str, ...], np.ndarray] = {}
    for frame_index, source_pose in enumerate(source_poses):
        local_rotations = _local_rotations_for_frame(target_nodes, animation_tracks, frame_index)
        for source_parent, source_child, target_parent, target_child in segments:
            if dance_spatial_chains and _segment_is_in_spatial_chain(
                target_parent,
                target_child,
                dance_spatial_chains,
            ):
                # The full spatial chain solve below constrains both swing and
                # axial roll.  Applying the direction-only correction first
                # would bake an arbitrary twist into its starting pose.
                continue
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
            if rotation_anchor in {"target_rest", "rest", "bind", "bind_pose"}:
                rest_dir = _segment_direction(
                    target_rest_positions.get(actual_target_parent),
                    target_rest_positions.get(actual_target_child),
                )
                rest_rotation = target_rest_rotations.get(actual_target_parent)
                if rest_dir is None or rest_rotation is None:
                    continue
                swing = _shortest_arc_matrix(rest_dir, desired_dir)
                anchor_world = quat_to_matrix_xyzw(rest_rotation)[:3, :3]
            else:
                swing = _shortest_arc_matrix(actual_dir, desired_dir)
                anchor_world = quat_to_matrix_xyzw(world_rotations[actual_target_parent])[:3, :3]
            target_node = target_model.find_node(actual_target_parent)
            if target_node is None:
                continue
            if (
                actual_target_parent.lower() in upperarm_targets
                and arm_parent_share > 0.0
                and target_node.parent is not None
                and target_node.parent.name in world_rotations
                and target_node.parent.name in local_rotations
            ):
                # Share the shoulder swing with Aurora's collar in the same
                # world-space plane, then re-solve the upper arm below.  This
                # preserves the authored elbow direction while reducing the
                # relative collar/bicep rotation that stretches vertices
                # weighted across both bones.
                parent_node = target_node.parent
                partial_swing_quat = _slerp_xyzw(
                    (0.0, 0.0, 0.0, 1.0),
                    matrix_to_quat_xyzw(_matrix4(swing)),
                    arm_parent_share,
                )
                partial_swing = quat_to_matrix_xyzw(partial_swing_quat)[:3, :3]
                parent_world = quat_to_matrix_xyzw(
                    world_rotations[parent_node.name]
                )[:3, :3]
                corrected_parent_world_quat = matrix_to_quat_xyzw(
                    _matrix4(_orthonormalized(partial_swing @ parent_world))
                )
                if (
                    parent_node.parent is not None
                    and parent_node.parent.name in world_rotations
                ):
                    corrected_parent_local = _local_rotation_from_world(
                        world_rotations[parent_node.parent.name],
                        corrected_parent_world_quat,
                    )
                else:
                    corrected_parent_local = corrected_parent_world_quat
                local_rotations[parent_node.name] = corrected_parent_local
                _set_orientation_value(
                    animation_tracks,
                    parent_node.name,
                    frame_index,
                    corrected_parent_local,
                )
                corrected_count += 1

                world_positions, world_rotations = _compose_target_fk(
                    target_nodes,
                    local_rotations,
                )
                actual_dir = _segment_direction(
                    world_positions.get(actual_target_parent),
                    world_positions.get(actual_target_child),
                )
                if actual_dir is None:
                    continue
                swing = _shortest_arc_matrix(actual_dir, desired_dir)
                anchor_world = quat_to_matrix_xyzw(
                    world_rotations[actual_target_parent]
                )[:3, :3]
            corrected_world = _orthonormalized(swing @ anchor_world)
            corrected_world_quat = matrix_to_quat_xyzw(_matrix4(corrected_world))
            if target_node.parent is not None and target_node.parent.name in world_rotations:
                corrected_local = _local_rotation_from_world(
                    world_rotations[target_node.parent.name],
                    corrected_world_quat,
                )
            else:
                corrected_local = corrected_world_quat
            if (
                actual_target_parent.lower() in upperarm_targets
                and arm_strength < 1.0
            ):
                corrected_local = _slerp_xyzw(
                    local_rotations[actual_target_parent],
                    corrected_local,
                    arm_strength,
                )
            local_rotations[actual_target_parent] = corrected_local
            _set_orientation_value(animation_tracks, actual_target_parent, frame_index, corrected_local)
            corrected_count += 1

        if dance_spatial_chains:
            chain_corrections, current_planes = _apply_dance_spatial_chain_correction(
                animation_tracks=animation_tracks,
                frame_index=frame_index,
                local_rotations=local_rotations,
                source_pose=source_pose,
                source_rest_pose=source_rest_pose,
                target_model=target_model,
                target_nodes=target_nodes,
                target_rest_positions=target_rest_positions,
                target_rest_rotations=target_rest_rotations,
                mapped_chains=dance_spatial_chains,
                previous_planes=previous_dance_plane_by_chain,
            )
            corrected_count += chain_corrections
            previous_dance_plane_by_chain.update(current_planes)

        if terminal_chains:
            world_positions, world_rotations = _compose_target_fk(target_nodes, local_rotations)
            for source_parent, source_joint, source_child, target_parent, target_joint, target_child in terminal_chains:
                actual_target_parent = target_by_key.get(target_parent.lower(), target_parent)
                actual_target_joint = target_by_key.get(target_joint.lower(), target_joint)
                actual_target_child = target_by_key.get(target_child.lower(), target_child)
                if (
                    actual_target_parent not in world_positions
                    or actual_target_joint not in world_positions
                    or actual_target_child not in world_positions
                    or actual_target_joint not in local_rotations
                ):
                    continue
                try:
                    source_basis = _terminal_chain_basis(
                        source_pose.global_transforms[source_parent].position,
                        source_pose.global_transforms[source_joint].position,
                        source_pose.global_transforms[source_child].position,
                    )
                except KeyError:
                    continue
                current_basis = _terminal_chain_basis(
                    world_positions.get(actual_target_parent),
                    world_positions.get(actual_target_joint),
                    world_positions.get(actual_target_child),
                )
                if source_basis is None or current_basis is None:
                    continue
                chain_key = (source_parent.lower(), source_joint.lower(), source_child.lower())
                source_basis = _continuity_aligned_terminal_basis(
                    source_basis,
                    previous_terminal_basis_by_chain.get(chain_key),
                )
                previous_terminal_basis_by_chain[chain_key] = source_basis
                roll = _terminal_roll_correction_matrix(current_basis, source_basis)
                if roll is None:
                    continue
                current_world = quat_to_matrix_xyzw(world_rotations[actual_target_joint])[:3, :3]
                corrected_world = _orthonormalized(roll @ current_world)
                corrected_world_quat = matrix_to_quat_xyzw(_matrix4(corrected_world))
                target_node = target_model.find_node(actual_target_joint)
                if target_node is None:
                    continue
                if target_node.parent is not None and target_node.parent.name in world_rotations:
                    corrected_local = _local_rotation_from_world(
                        world_rotations[target_node.parent.name],
                        corrected_world_quat,
                    )
                else:
                    corrected_local = corrected_world_quat
                local_rotations[actual_target_joint] = corrected_local
                _set_orientation_value(animation_tracks, actual_target_joint, frame_index, corrected_local)
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
            "source_quaternion_conversion": normalized_profile.metadata.get(
                "source_quaternion_conversion",
                "ue5_to_aurora",
            ),
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
    root_translation_policy: str,
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
        stripped_root_translation=str(root_translation_policy or "in_place") == "in_place",
        max_quaternion_norm_error=max_norm_error,
        max_adjacent_rotation_degrees=max_adjacent_degrees,
        warnings=list(warnings),
    )


def _animation_node_for(animation: Animation, node_name: str) -> ModelNode:
    wanted = str(node_name or "").lower()
    for anim_node in getattr(animation, "nodes", []) or []:
        if str(getattr(anim_node, "name", "") or "").lower() == wanted:
            return anim_node
    anim_node = ModelNode(name=node_name, controllers=[])
    animation.nodes.append(anim_node)
    return anim_node


def _select_source_root_motion_node(
    source_clip: SourceSkeletonClip,
    profile: RetargetProfile,
    target_root_name: str,
) -> str | None:
    by_name = {node.name.lower(): node.name for node in source_clip.nodes}
    candidates: list[str] = []

    target_root_key = str(target_root_name or "").lower()
    for entry in normalize_retarget_profile(profile).mappings:
        role = str(entry.role or "").lower()
        target = str(entry.target_node or "").lower()
        if target == target_root_key or role in {"root", "pelvis", "hips"}:
            actual = by_name.get(str(entry.source_node or "").lower())
            if actual and actual not in candidates:
                candidates.append(actual)

    for node in source_clip.nodes:
        key = str(node.name or "").lower()
        if (
            node.parent_name is None
            or str(node.classification or "").lower() == "root"
            or "root" in key
            or "hips" in key
        ) and node.name not in candidates:
            candidates.append(node.name)

    if not candidates:
        return None
    return max(candidates, key=lambda name: _source_node_motion_distance(source_clip, name))


def _source_node_motion_distance(source_clip: SourceSkeletonClip, node_name: str) -> float:
    if len(source_clip.sampled_poses) < 2:
        return 0.0
    first = source_clip.sampled_poses[0].global_transforms.get(node_name)
    if first is None:
        return 0.0
    reference = np.asarray(first.position, dtype=np.float64)
    max_distance = 0.0
    for pose in source_clip.sampled_poses[1:]:
        transform = pose.global_transforms.get(node_name)
        if transform is None:
            continue
        current = np.asarray(transform.position, dtype=np.float64)
        max_distance = max(max_distance, float(np.linalg.norm(current - reference)))
    return max_distance


def _exact_segment_role_pairs_for_profile(profile: RetargetProfile) -> tuple[tuple[str, str], ...]:
    normalized = normalize_retarget_profile(profile)
    metadata = dict(getattr(normalized, "metadata", {}) or {})
    policy = str(metadata.get("exact_segment_correction_policy") or "").strip().lower()
    source_family = str(metadata.get("source_skeleton_family") or "").strip().lower()
    generated_by = str(metadata.get("generated_by") or "").strip().lower()
    if policy in {"disabled", "off", "none"}:
        return ()
    if policy in {"mixamo_limb_only", "limb_only", "limbs_only"}:
        return MIXAMO_PM_BAM_LIMB_ONLY_SEGMENT_PAIRS
    if policy in {
        "performance_lower_body",
        "lower_body_only",
        "legs_only",
    }:
        return PERFORMANCE_LOWER_BODY_SEGMENT_PAIRS
    if policy in {
        "dance_anatomical",
        "anatomical_dance",
        "dance_spatial_anatomical",
    }:
        return DANCE_ANATOMICAL_SEGMENT_PAIRS
    if policy in {
        "dance_clavicle_anatomical",
        "anatomical_dance_clavicle",
    }:
        return DANCE_CLAVICLE_ANATOMICAL_SEGMENT_PAIRS
    if policy in {
        "performance_anatomical",
        "anatomical_performance",
    }:
        return PERFORMANCE_ANATOMICAL_SEGMENT_PAIRS
    if policy in {"mixamo_stable_humanoid", "pmbam_mixamo_stable", "stable_humanoid"}:
        return MIXAMO_PM_BAM_STABLE_HUMANOID_SEGMENT_PAIRS
    if policy in {"pmbam_full_humanoid", "full_humanoid", "full", "all"}:
        return EXACT_PM_BAM_SEGMENT_PAIRS
    if source_family == "mixamo" or generated_by == VERIFIED_MIXAMO_TO_AURORA_PROFILE_GENERATOR:
        return MIXAMO_PM_BAM_STABLE_HUMANOID_SEGMENT_PAIRS
    return EXACT_PM_BAM_SEGMENT_PAIRS


def _mapped_exact_segments(profile: RetargetProfile) -> list[tuple[str, str, str, str]]:
    role_pairs = _exact_segment_role_pairs_for_profile(profile)
    by_role_side = {
        (str(entry.role or "").lower(), str(entry.side or "center").lower()): entry
        for entry in profile.mappings
    }
    segments: list[tuple[str, str, str, str]] = []
    for parent_role, child_role in role_pairs:
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


def _mapped_terminal_twist_chains(profile: RetargetProfile) -> list[tuple[str, str, str, str, str, str]]:
    normalized = normalize_retarget_profile(profile)
    metadata = dict(getattr(normalized, "metadata", {}) or {})
    policy = str(metadata.get("terminal_twist_correction_policy") or "").strip().lower()
    segment_policy = str(metadata.get("exact_segment_correction_policy") or "").strip().lower()
    if policy in {"disabled", "off", "none"}:
        return []
    if not policy and segment_policy in {
        "mixamo_stable_humanoid",
        "pmbam_mixamo_stable",
        "stable_humanoid",
        "performance_lower_body",
        "lower_body_only",
        "legs_only",
        "performance_anatomical",
        "anatomical_performance",
        "dance_anatomical",
        "anatomical_dance",
        "dance_clavicle_anatomical",
        "anatomical_dance_clavicle",
        "dance_spatial_anatomical",
    }:
        return []
    by_role_side = {
        (str(entry.role or "").lower(), str(entry.side or "center").lower()): entry
        for entry in normalized.mappings
    }
    chains: list[tuple[str, str, str, str, str, str]] = []
    for parent_role, joint_role, child_role in TERMINAL_PM_BAM_TWIST_CHAINS:
        sides = sorted({
            side
            for role, side in by_role_side
            if role in {parent_role, joint_role, child_role} and side
        })
        for side in sides:
            parent = by_role_side.get((parent_role, side)) or by_role_side.get((parent_role, "center"))
            joint = by_role_side.get((joint_role, side)) or by_role_side.get((joint_role, "center"))
            child = by_role_side.get((child_role, side)) or by_role_side.get((child_role, "center"))
            if parent is None or joint is None or child is None:
                continue
            chains.append(
                (
                    parent.source_node,
                    joint.source_node,
                    child.source_node,
                    parent.target_node,
                    joint.target_node,
                    child.target_node,
                )
            )
    return chains


def _mapped_dance_spatial_chains(
    profile: RetargetProfile,
) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    """Return complete source/target limb chains for the dance spatial solve."""

    normalized = normalize_retarget_profile(profile)
    metadata = dict(getattr(normalized, "metadata", {}) or {})
    policy = str(metadata.get("exact_segment_correction_policy") or "").strip().lower()
    if policy not in {"dance_spatial_anatomical"}:
        return []
    by_role_side = {
        (str(entry.role or "").lower(), str(entry.side or "center").lower()): entry
        for entry in normalized.mappings
    }
    chains: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    for roles in DANCE_SPATIAL_CHAIN_ROLES:
        sides = sorted({
            side
            for role, side in by_role_side
            if role in set(roles) and side not in {"", "center"}
        })
        if not sides and all(
            (role, "center") in by_role_side
            for role in roles
        ):
            sides = ["center"]
        for side in sides:
            entries = [
                by_role_side.get((role, side)) or by_role_side.get((role, "center"))
                for role in roles
            ]
            if any(entry is None for entry in entries):
                continue
            chains.append(
                (
                    tuple(entry.source_node for entry in entries if entry is not None),
                    tuple(entry.target_node for entry in entries if entry is not None),
                )
            )
    return chains


def _segment_is_in_spatial_chain(
    target_parent: str,
    target_child: str,
    mapped_chains: list[tuple[tuple[str, ...], tuple[str, ...]]],
) -> bool:
    parent_key = str(target_parent or "").lower()
    child_key = str(target_child or "").lower()
    for _source_nodes, target_nodes in mapped_chains:
        for index in range(len(target_nodes) - 1):
            if (
                target_nodes[index].lower() == parent_key
                and target_nodes[index + 1].lower() == child_key
            ):
                return True
    return False


def _apply_dance_spatial_chain_correction(
    *,
    animation_tracks: dict[str, tuple[str, dict]],
    frame_index: int,
    local_rotations: dict[str, tuple[float, float, float, float]],
    source_pose: SourcePose,
    source_rest_pose: SourcePose,
    target_model: KotorModel,
    target_nodes,
    target_rest_positions: dict[str, tuple[float, float, float]],
    target_rest_rotations: dict[str, tuple[float, float, float, float]],
    mapped_chains: list[tuple[tuple[str, ...], tuple[str, ...]]],
    previous_planes: dict[tuple[str, ...], np.ndarray],
) -> tuple[int, dict[tuple[str, ...], np.ndarray]]:
    """Solve dance limbs as spatial chains with a stable anatomical plane.

    Matching only parent->child directions leaves one unconstrained degree of
    freedom: roll around the bone.  On a foreign rig that ambiguity visibly
    corkscrews KOTOR shoulders, elbows, wrists, hips, and knees.  This pass uses
    the entire shoulder-elbow-wrist or hip-knee-ankle chain to build a full
    orthonormal frame.  The source clip has already been rigidly aligned into
    the target actor frame, so the current anatomical segment basis is the
    desired basis directly.  Treating it as a delta from the FBX bind pose is
    incorrect for mixed-authoring rigs whose neutral shoulder/hip poses differ:
    it can turn a visibly lowered source arm into a raised Aurora arm.  Target
    bind data is used only to preserve KOTOR's native bone-axis convention.
    """

    corrected = 0
    current_planes: dict[tuple[str, ...], np.ndarray] = {}
    target_by_key = {node.name.lower(): node.name for node in target_nodes}
    for source_names_raw, target_names_raw in mapped_chains:
        source_names = tuple(source_names_raw)
        target_names = tuple(
            target_by_key.get(name.lower(), name)
            for name in target_names_raw
        )
        try:
            source_rest_positions = [
                source_rest_pose.global_transforms[name].position
                for name in source_names
            ]
            source_current_positions = [
                source_pose.global_transforms[name].position
                for name in source_names
            ]
            source_rest_rotation = source_rest_pose.global_transforms[source_names[0]].rotation
            source_current_rotation = source_pose.global_transforms[source_names[0]].rotation
            target_rest_chain_positions = [target_rest_positions[name] for name in target_names]
            target_rest_rotation = target_rest_rotations[target_names[0]]
        except KeyError:
            continue

        source_reference_plane = _stable_anatomical_plane_normal(
            source_rest_positions[0],
            source_rest_positions[1],
            source_rest_positions[2],
            rotation_hint=source_rest_rotation,
        )
        target_reference_plane = _stable_anatomical_plane_normal(
            target_rest_chain_positions[0],
            target_rest_chain_positions[1],
            target_rest_chain_positions[2],
            rotation_hint=target_rest_rotation,
        )
        if source_reference_plane is None or target_reference_plane is None:
            continue

        source_rest_matrix = quat_to_matrix_xyzw(source_rest_rotation)[:3, :3]
        source_current_matrix = quat_to_matrix_xyzw(source_current_rotation)[:3, :3]
        expected_current_plane = _normalize_vec(
            source_current_matrix @ source_rest_matrix.T @ source_reference_plane
        )
        chain_key = tuple(name.lower() for name in source_names)
        source_current_plane = _stable_anatomical_plane_normal(
            source_current_positions[0],
            source_current_positions[1],
            source_current_positions[2],
            rotation_hint=source_current_rotation,
            expected_normal=expected_current_plane,
            previous_normal=previous_planes.get(chain_key),
        )
        if source_current_plane is None:
            continue
        current_planes[chain_key] = source_current_plane

        for segment_index in range(len(source_names) - 1):
            target_parent = target_names[segment_index]
            target_child = target_names[segment_index + 1]
            target_node = target_model.find_node(target_parent)
            if target_node is None or target_parent not in local_rotations:
                continue
            source_reference_primary = _segment_direction(
                source_rest_positions[segment_index],
                source_rest_positions[segment_index + 1],
            )
            source_current_primary = _segment_direction(
                source_current_positions[segment_index],
                source_current_positions[segment_index + 1],
            )
            target_reference_primary = _segment_direction(
                target_rest_chain_positions[segment_index],
                target_rest_chain_positions[segment_index + 1],
            )
            if (
                source_reference_primary is None
                or source_current_primary is None
                or target_reference_primary is None
            ):
                continue
            source_current_basis = _anatomical_segment_basis(
                source_current_primary,
                source_current_plane,
            )
            target_reference_basis = _anatomical_segment_basis(
                target_reference_primary,
                target_reference_plane,
            )
            if (
                source_current_basis is None
                or target_reference_basis is None
            ):
                continue
            desired_anatomical_basis = source_current_basis
            target_rest_world = quat_to_matrix_xyzw(
                target_rest_rotations[target_parent]
            )[:3, :3]
            anatomical_to_target_bone = _orthonormalized(
                target_reference_basis.T @ target_rest_world
            )
            desired_target_world = _orthonormalized(
                desired_anatomical_basis @ anatomical_to_target_bone
            )
            desired_target_world_quat = matrix_to_quat_xyzw(
                _matrix4(desired_target_world)
            )

            _world_positions, world_rotations = _compose_target_fk(
                target_nodes,
                local_rotations,
            )
            if target_node.parent is not None and target_node.parent.name in world_rotations:
                corrected_local = _local_rotation_from_world(
                    world_rotations[target_node.parent.name],
                    desired_target_world_quat,
                )
            else:
                corrected_local = desired_target_world_quat
            local_rotations[target_parent] = corrected_local
            _set_orientation_value(
                animation_tracks,
                target_parent,
                frame_index,
                corrected_local,
            )
            corrected += 1
    return corrected, current_planes


def audit_dance_spatial_chain_transfer(
    *,
    animation: Animation,
    source_clip: SourceSkeletonClip,
    target_model: KotorModel,
    profile: RetargetProfile,
    basis_conversion: BasisConversion | None = None,
    segment_tolerance_degrees: float = 0.5,
    basis_tolerance_degrees: float = 0.75,
) -> DanceSpatialTransferAudit:
    """Compare every solved limb frame with its bind-calibrated source frame.

    Finite quaternions and fixed bone lengths cannot detect a corkscrewed arm:
    the pose is numerically valid while the shoulder, elbow, wrist, and skinned
    mesh are spatially wrong.  This audit reconstructs the exact anatomical
    basis expected by the dance solver for every arm and leg segment, then
    compares it with the evaluated Aurora pose.  It therefore checks swing,
    axial roll, and elbow/knee bend planes rather than trusting controller data
    alone.
    """

    mapped_chains = _mapped_dance_spatial_chains(profile)
    sample_count = len(source_clip.sampled_poses)
    if not mapped_chains or not sample_count:
        return DanceSpatialTransferAudit(sample_count, 0, 0.0, 0.0, 0.0)

    animation_tracks = _orientation_tracks(animation)
    target_nodes = list(target_model.all_nodes())
    target_by_key = {node.name.lower(): node.name for node in target_nodes}
    target_rest_local = {
        node.name: normalize_quat_xyzw(node.rotation)
        for node in target_nodes
    }
    target_rest_positions, target_rest_rotations = _compose_target_fk(
        target_nodes,
        target_rest_local,
    )
    source_rest_pose = _convert_pose_for_segment_correction(
        source_clip.rest_pose,
        basis_conversion,
    )
    source_poses = [
        _convert_pose_for_segment_correction(pose, basis_conversion)
        for pose in source_clip.sampled_poses
    ]

    max_segment_error = 0.0
    max_basis_error = 0.0
    max_plane_error = 0.0
    errors: list[str] = []
    previous_source_planes: dict[tuple[str, ...], np.ndarray] = {}
    for frame_index, source_pose in enumerate(source_poses):
        local_rotations = _local_rotations_for_frame(
            target_nodes,
            animation_tracks,
            frame_index,
        )
        target_positions, target_rotations = _compose_target_fk(
            target_nodes,
            local_rotations,
        )
        for source_names_raw, target_names_raw in mapped_chains:
            source_names = tuple(source_names_raw)
            target_names = tuple(
                target_by_key.get(name.lower(), name)
                for name in target_names_raw
            )
            try:
                source_rest_positions = [
                    source_rest_pose.global_transforms[name].position
                    for name in source_names
                ]
                source_current_positions = [
                    source_pose.global_transforms[name].position
                    for name in source_names
                ]
                source_rest_rotation = (
                    source_rest_pose.global_transforms[source_names[0]].rotation
                )
                source_current_rotation = (
                    source_pose.global_transforms[source_names[0]].rotation
                )
                target_rest_chain_positions = [
                    target_rest_positions[name]
                    for name in target_names
                ]
                target_current_chain_positions = [
                    target_positions[name]
                    for name in target_names
                ]
            except KeyError:
                continue

            source_reference_plane = _stable_anatomical_plane_normal(
                *source_rest_positions[:3],
                rotation_hint=source_rest_rotation,
            )
            target_reference_plane = _stable_anatomical_plane_normal(
                *target_rest_chain_positions[:3],
                rotation_hint=target_rest_rotations[target_names[0]],
            )
            if source_reference_plane is None or target_reference_plane is None:
                continue
            source_rest_matrix = quat_to_matrix_xyzw(source_rest_rotation)[:3, :3]
            source_current_matrix = quat_to_matrix_xyzw(source_current_rotation)[:3, :3]
            expected_source_plane = _normalize_vec(
                source_current_matrix @ source_rest_matrix.T @ source_reference_plane
            )
            source_current_plane = _stable_anatomical_plane_normal(
                *source_current_positions[:3],
                rotation_hint=source_current_rotation,
                expected_normal=expected_source_plane,
                previous_normal=previous_source_planes.get(
                    tuple(name.lower() for name in source_names)
                ),
            )
            target_current_plane = _stable_anatomical_plane_normal(
                *target_current_chain_positions[:3],
                rotation_hint=target_rotations[target_names[0]],
            )
            if source_current_plane is None or target_current_plane is None:
                continue
            previous_source_planes[
                tuple(name.lower() for name in source_names)
            ] = source_current_plane

            expected_plane = None
            for segment_index in range(len(source_names) - 1):
                source_reference_primary = _segment_direction(
                    source_rest_positions[segment_index],
                    source_rest_positions[segment_index + 1],
                )
                source_current_primary = _segment_direction(
                    source_current_positions[segment_index],
                    source_current_positions[segment_index + 1],
                )
                target_reference_primary = _segment_direction(
                    target_rest_chain_positions[segment_index],
                    target_rest_chain_positions[segment_index + 1],
                )
                target_current_primary = _segment_direction(
                    target_current_chain_positions[segment_index],
                    target_current_chain_positions[segment_index + 1],
                )
                if (
                    source_reference_primary is None
                    or source_current_primary is None
                    or target_reference_primary is None
                    or target_current_primary is None
                ):
                    continue
                source_current_basis = _anatomical_segment_basis(
                    source_current_primary,
                    source_current_plane,
                )
                target_reference_basis = _anatomical_segment_basis(
                    target_reference_primary,
                    target_reference_plane,
                )
                if (
                    source_current_basis is None
                    or target_reference_basis is None
                ):
                    continue
                desired_anatomical_basis = source_current_basis
                if segment_index == 0:
                    expected_plane = desired_anatomical_basis[:, 2]
                segment_error = _vector_angle_degrees(
                    desired_anatomical_basis[:, 0],
                    target_current_primary,
                )
                max_segment_error = max(max_segment_error, segment_error)

                target_parent = target_names[segment_index]
                target_rest_world = quat_to_matrix_xyzw(
                    target_rest_rotations[target_parent]
                )[:3, :3]
                anatomical_to_target_bone = _orthonormalized(
                    target_reference_basis.T @ target_rest_world
                )
                desired_target_world = _orthonormalized(
                    desired_anatomical_basis @ anatomical_to_target_bone
                )
                actual_target_world = quat_to_matrix_xyzw(
                    target_rotations[target_parent]
                )[:3, :3]
                basis_error = _rotation_matrix_angle_degrees(
                    desired_target_world,
                    actual_target_world,
                )
                max_basis_error = max(max_basis_error, basis_error)

                if segment_error > segment_tolerance_degrees and len(errors) < 8:
                    errors.append(
                        f"frame {frame_index} chain {target_names[0]} segment "
                        f"{target_parent}->{target_names[segment_index + 1]} "
                        f"direction error {segment_error:.4f} deg"
                    )
                if basis_error > basis_tolerance_degrees and len(errors) < 8:
                    errors.append(
                        f"frame {frame_index} bone {target_parent} axial-basis "
                        f"error {basis_error:.4f} deg"
                    )

            if expected_plane is not None:
                plane_error = _unsigned_vector_angle_degrees(
                    expected_plane,
                    target_current_plane,
                )
                max_plane_error = max(max_plane_error, plane_error)

    return DanceSpatialTransferAudit(
        sample_count=sample_count,
        chain_count=len(mapped_chains),
        max_segment_direction_error_degrees=max_segment_error,
        max_bone_basis_error_degrees=max_basis_error,
        max_bend_plane_error_degrees=max_plane_error,
        errors=tuple(errors),
    )


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


def _vector_angle_degrees(a, b) -> float:
    first = _normalize_vec(a)
    second = _normalize_vec(b)
    if first is None or second is None:
        return 180.0
    dot = max(-1.0, min(1.0, float(np.dot(first, second))))
    return math.degrees(math.acos(dot))


def _unsigned_vector_angle_degrees(a, b) -> float:
    first = _normalize_vec(a)
    second = _normalize_vec(b)
    if first is None or second is None:
        return 90.0
    dot = max(-1.0, min(1.0, abs(float(np.dot(first, second)))))
    return math.degrees(math.acos(dot))


def _rotation_matrix_angle_degrees(expected, actual) -> float:
    delta = _orthonormalized(np.asarray(expected).T @ np.asarray(actual))
    cosine = max(-1.0, min(1.0, (float(np.trace(delta)) - 1.0) * 0.5))
    return math.degrees(math.acos(cosine))


def _stable_anatomical_plane_normal(
    parent_position,
    joint_position,
    child_position,
    *,
    rotation_hint=None,
    expected_normal: np.ndarray | None = None,
    previous_normal: np.ndarray | None = None,
) -> np.ndarray | None:
    """Return a continuity-safe bend-plane normal for a three-joint chain.

    A nearly straight elbow or knee has no geometric plane, so using its raw
    cross product amplifies tiny source noise into 180-degree roll flips.  The
    source joint's bind-calibrated orientation is the preferred fallback, then
    the previous frame.  When a real bend exists its sign is aligned to that
    expected anatomical normal.
    """

    incoming = _segment_direction(parent_position, joint_position)
    outgoing = _segment_direction(joint_position, child_position)
    if incoming is None or outgoing is None:
        return None
    expected = _normalize_vec(expected_normal) if expected_normal is not None else None
    previous = _normalize_vec(previous_normal) if previous_normal is not None else None
    if expected is None and rotation_hint is not None:
        rotation = quat_to_matrix_xyzw(rotation_hint)[:3, :3]
        best_hint = None
        best_length = -1.0
        for column in range(3):
            projected = rotation[:, column] - incoming * float(np.dot(rotation[:, column], incoming))
            length = float(np.linalg.norm(projected))
            if length > best_length:
                best_hint = projected
                best_length = length
        expected = _normalize_vec(best_hint) if best_hint is not None else None

    raw_normal = np.cross(incoming, outgoing)
    geometric = _normalize_vec(raw_normal) if float(np.linalg.norm(raw_normal)) >= 0.03 else None
    normal = geometric if geometric is not None else expected
    if normal is None:
        normal = previous
    if normal is None:
        return None
    anchor = expected if expected is not None else previous
    if anchor is not None and float(np.dot(normal, anchor)) < 0.0:
        normal = -normal
    if previous is not None and float(np.dot(normal, previous)) < 0.0:
        normal = -normal
    return _normalize_vec(normal)


def _anatomical_segment_basis(
    primary_direction,
    plane_normal,
) -> np.ndarray | None:
    """Build a right-handed segment frame from direction and bend plane."""

    primary = _normalize_vec(primary_direction)
    normal = _project_onto_plane(plane_normal, primary)
    if primary is None or normal is None:
        return None
    secondary = _normalize_vec(np.cross(normal, primary))
    if secondary is None:
        return None
    normal = _normalize_vec(np.cross(primary, secondary))
    if normal is None:
        return None
    return _orthonormalized(np.column_stack((primary, secondary, normal)))


def _terminal_chain_basis(parent_position, joint_position, child_position) -> np.ndarray | None:
    incoming = _segment_direction(parent_position, joint_position)
    outgoing = _segment_direction(joint_position, child_position)
    if incoming is None or outgoing is None:
        return None
    raw_normal = np.cross(incoming, outgoing)
    # A nearly straight chain has no trustworthy bend plane.  Skipping roll
    # correction for that sample is safer than amplifying floating-point noise
    # into a visible axial arm flip.
    if float(np.linalg.norm(raw_normal)) < 0.03:
        return None
    normal = _normalize_vec(raw_normal)
    if normal is None:
        return None
    side = _normalize_vec(np.cross(normal, outgoing))
    if side is None:
        return None
    return _orthonormalized(np.column_stack((outgoing, side, normal)))


def _continuity_aligned_terminal_basis(
    basis: np.ndarray,
    previous_basis: np.ndarray | None,
) -> np.ndarray:
    """Keep hand/foot roll-plane normals from flipping between adjacent frames."""

    if previous_basis is None:
        return basis
    current = np.asarray(basis, dtype=np.float64)
    previous = np.asarray(previous_basis, dtype=np.float64)
    if current.shape != (3, 3) or previous.shape != (3, 3):
        return basis
    if float(np.dot(current[:, 2], previous[:, 2])) >= 0.0:
        return basis
    flipped = current.copy()
    flipped[:, 1] *= -1.0
    flipped[:, 2] *= -1.0
    return _orthonormalized(flipped)


def _terminal_roll_correction_matrix(current_basis: np.ndarray, desired_basis: np.ndarray) -> np.ndarray | None:
    """Return a roll-only correction around the terminal segment axis."""

    axis = _normalize_vec(np.asarray(current_basis, dtype=np.float64)[:, 0])
    if axis is None:
        return None
    current_normal = _project_onto_plane(np.asarray(current_basis, dtype=np.float64)[:, 2], axis)
    desired_normal = _project_onto_plane(np.asarray(desired_basis, dtype=np.float64)[:, 2], axis)
    if current_normal is None or desired_normal is None:
        return None
    dot = max(-1.0, min(1.0, float(np.dot(current_normal, desired_normal))))
    signed = float(np.dot(axis, np.cross(current_normal, desired_normal)))
    angle = math.atan2(signed, dot)
    if not math.isfinite(angle) or abs(angle) <= 1e-7:
        return np.eye(3, dtype=np.float64)
    return _axis_angle_matrix(axis, angle)


def _project_onto_plane(value, normal) -> np.ndarray | None:
    vec = np.asarray(value, dtype=np.float64)
    axis = _normalize_vec(normal)
    if axis is None:
        return None
    projected = vec - axis * float(np.dot(vec, axis))
    return _normalize_vec(projected)


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
