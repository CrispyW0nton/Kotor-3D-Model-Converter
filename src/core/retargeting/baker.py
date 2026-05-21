"""Pure animation bake core for GhostRigger retargeting Day 3A.

This module deliberately performs no file I/O.  It takes a fixed-rate
``SampledClip`` plus normalized source/target bind registries and returns a new
``SampledClip`` shaped like the target skeleton.  All transform math is routed
through :mod:`coordinate_normalizer` so retargeting uses WXYZ quaternions and
canonical world-space matrices throughout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Optional

import numpy as np

from src.core.retargeting.coordinate_normalizer import (
    BindPoseRegistry,
    compose_matrix,
    matrix_to_quat_wxyz,
    normalize_quat_wxyz,
    quat_inverse_wxyz,
    quat_mul_wxyz,
    scale_matrix,
)
from src.core.retargeting.sampler import SampledClip


TWIST_BONE_NAMES = (
    "upperarm_twist_01_l",
    "upperarm_twist_02_l",
    "upperarm_twist_01_r",
    "upperarm_twist_02_r",
    "lowerarm_twist_01_l",
    "lowerarm_twist_02_l",
    "lowerarm_twist_01_r",
    "lowerarm_twist_02_r",
    "thigh_twist_01_l",
    "thigh_twist_02_l",
    "thigh_twist_01_r",
    "thigh_twist_02_r",
    "calf_twist_01_l",
    "calf_twist_02_l",
    "calf_twist_01_r",
    "calf_twist_02_r",
)


def _key(name: str) -> str:
    return str(name or "").strip().lower()


def _safe_inv(matrix: np.ndarray) -> np.ndarray:
    try:
        return np.linalg.inv(matrix)
    except np.linalg.LinAlgError:
        return np.eye(4, dtype=np.float64)


def _slerp_wxyz(a: Iterable[float], b: Iterable[float], t: float) -> np.ndarray:
    q1 = normalize_quat_wxyz(a)
    q2 = normalize_quat_wxyz(b)
    t = max(0.0, min(1.0, float(t)))
    dot = float(np.dot(q1, q2))
    if dot < 0.0:
        q2 = -q2
        dot = -dot
    if dot > 0.9995:
        return normalize_quat_wxyz(q1 + t * (q2 - q1))
    theta_0 = np.arccos(max(-1.0, min(1.0, dot)))
    sin_theta_0 = np.sin(theta_0)
    theta = theta_0 * t
    s0 = np.cos(theta) - dot * np.sin(theta) / sin_theta_0
    s1 = np.sin(theta) / sin_theta_0
    return normalize_quat_wxyz((s0 * q1) + (s1 * q2))


@dataclass(frozen=True)
class BindOffsets:
    """Per-mapped-bone world-rotation offset from source bind to target bind."""

    offsets: Dict[str, np.ndarray]
    bone_map: Dict[str, str]
    source_skeleton_id: str = ""
    target_skeleton_id: str = ""

    def offset_for(self, source_bone: str) -> np.ndarray:
        return self.offsets.get(_key(source_bone), np.asarray((1.0, 0.0, 0.0, 0.0), dtype=np.float64))


@dataclass(frozen=True)
class BakerOptions:
    """Controls pure retarget bake behavior."""

    root_motion_scale: float = 1.0
    derive_unmapped_target_bones: bool = True
    twist_bone_rotation_weight: float = 0.35
    root_motion_targets: tuple[str, ...] = ("pelvis", "root")


@dataclass(frozen=True)
class BakeDiagnostics:
    """Small in-memory summary useful for tests and audit docs."""

    direct_targets: tuple[str, ...] = ()
    derived_targets: tuple[str, ...] = ()
    unmapped_sources: tuple[str, ...] = ()
    max_quat_norm_error: float = 0.0


def compute_bind_offsets(
    source_skel: BindPoseRegistry,
    target_skel: BindPoseRegistry,
    bone_map: Mapping[str, str],
) -> BindOffsets:
    """Compute ``target_world_bind * inverse(source_world_bind)`` rotations."""

    offsets: Dict[str, np.ndarray] = {}
    clean_map: Dict[str, str] = {}
    for source_name, target_name in (bone_map or {}).items():
        src = _key(source_name)
        dst = _key(target_name)
        if not src or not dst or not source_skel.has_bone(src) or not target_skel.has_bone(dst):
            continue
        source_rot = source_skel.world_rotation(src)
        target_rot = target_skel.world_rotation(dst)
        offsets[src] = quat_mul_wxyz(target_rot, quat_inverse_wxyz(source_rot))
        clean_map[src] = dst
    return BindOffsets(
        offsets=offsets,
        bone_map=clean_map,
        source_skeleton_id=source_skel.skeleton_id,
        target_skeleton_id=target_skel.skeleton_id,
    )


def _identity_retarget_possible(
    sampled: SampledClip,
    source_skel: BindPoseRegistry,
    target_skel: BindPoseRegistry,
    bone_map: Mapping[str, str],
) -> bool:
    if source_skel.skeleton_id != target_skel.skeleton_id:
        return False
    sample_keys = {_key(name) for name in sampled.bone_names}
    if sample_keys != {_key(name) for name in target_skel.bone_names}:
        return False
    return all(_key(src) == _key(dst) for src, dst in (bone_map or {}).items())


def _copy_identity_clip(sampled: SampledClip, target_skel: BindPoseRegistry) -> SampledClip:
    source_index = {_key(name): idx for idx, name in enumerate(sampled.bone_names)}
    indices = [source_index[_key(name)] for name in target_skel.bone_names]
    return SampledClip(
        clip_name=sampled.clip_name,
        fps=sampled.fps,
        frame_count=sampled.frame_count,
        bone_names=list(target_skel.bone_names),
        positions=np.asarray(sampled.positions[:, indices, :], dtype=np.float32).copy(),
        rotations=np.asarray(sampled.rotations[:, indices, :], dtype=np.float32).copy(),
        scales=np.asarray(sampled.scales[:, indices, :], dtype=np.float32).copy(),
        source_model=sampled.source_model,
        source_chain=list(sampled.source_chain),
        resolved_clip_source=sampled.resolved_clip_source,
        duration_s=sampled.duration_s,
        bake_math_audit_id=sampled.bake_math_audit_id,
        palette_frames=sampled.palette_frames,
    )


def _frame_source_world(sampled: SampledClip, source_skel: BindPoseRegistry, frame_index: int) -> Dict[str, np.ndarray]:
    sampled_lookup = {_key(name): idx for idx, name in enumerate(sampled.bone_names)}
    world: Dict[str, np.ndarray] = {}
    for name in source_skel.bone_names:
        key = _key(name)
        idx = sampled_lookup.get(key)
        if idx is None:
            local = source_skel.local_matrix(key)
        else:
            local = compose_matrix(
                sampled.positions[frame_index, idx, :],
                sampled.rotations[frame_index, idx, :],
                sampled.scales[frame_index, idx, :],
            )
        parent = source_skel.parent_key(key)
        world[key] = (world[parent] @ local) if parent in world else local
    return world


def _derive_target_local(
    target_key: str,
    parent_key: str,
    target_skel: BindPoseRegistry,
    output_local: Dict[str, np.ndarray],
    options: BakerOptions,
) -> tuple[np.ndarray, bool]:
    bind_local = target_skel.local_matrix(target_key).copy()
    if not options.derive_unmapped_target_bones:
        return bind_local, False
    if target_key not in TWIST_BONE_NAMES:
        return bind_local, False
    parent_local = output_local.get(parent_key)
    if parent_local is None:
        return bind_local, False
    bind_rot = target_skel.local_rotation(target_key)
    parent_rot = matrix_to_quat_wxyz(parent_local)
    twist_rot = _slerp_wxyz(bind_rot, parent_rot, options.twist_bone_rotation_weight)
    derived = compose_matrix(bind_local[:3, 3], twist_rot)
    return derived, True


def bake_retargeted_clip(
    sampled_source: SampledClip,
    source_skel: BindPoseRegistry,
    target_skel: BindPoseRegistry,
    bone_map: Mapping[str, str],
    bind_offsets: BindOffsets,
    *,
    options: Optional[BakerOptions] = None,
) -> SampledClip:
    """Bake a sampled source clip onto a target skeleton.

    Rotation transfer is world-space:
    ``target_world_rot = bind_offset(source, target) * source_world_rot``.
    Translation uses bind-space deltas, preserving target bone lengths while
    allowing root/pelvis motion to cross skeletons.
    """

    opts = options or BakerOptions()
    if _identity_retarget_possible(sampled_source, source_skel, target_skel, bone_map):
        return _copy_identity_clip(sampled_source, target_skel)

    frame_count = sampled_source.frame_count
    target_count = len(target_skel.bone_names)
    positions = np.zeros((frame_count, target_count, 3), dtype=np.float32)
    rotations = np.zeros((frame_count, target_count, 4), dtype=np.float32)
    scales = np.ones((frame_count, target_count, 3), dtype=np.float32)

    clean_map = {
        _key(src): _key(dst)
        for src, dst in (bone_map or {}).items()
        if source_skel.has_bone(src) and target_skel.has_bone(dst)
    }

    for frame_index in range(frame_count):
        source_world = _frame_source_world(sampled_source, source_skel, frame_index)
        desired_world: Dict[str, np.ndarray] = {}
        for source_key, target_key in clean_map.items():
            src_world = source_world.get(source_key)
            if src_world is None:
                continue
            src_bind = source_skel.world_matrix(source_key)
            dst_bind = target_skel.world_matrix(target_key)
            offset = bind_offsets.offset_for(source_key)

            src_rot = matrix_to_quat_wxyz(src_world)
            dst_rot = quat_mul_wxyz(offset, src_rot)
            pos_delta = src_world[:3, 3] - src_bind[:3, 3]
            if target_key not in opts.root_motion_targets:
                pos_delta = pos_delta * opts.root_motion_scale
            dst_pos = dst_bind[:3, 3] + pos_delta
            desired_world[target_key] = compose_matrix(dst_pos, dst_rot)

        output_world: Dict[str, np.ndarray] = {}
        output_local: Dict[str, np.ndarray] = {}
        for target_index, target_name in enumerate(target_skel.bone_names):
            target_key = _key(target_name)
            parent_key = target_skel.parent_key(target_key)
            parent_world = output_world.get(parent_key, np.eye(4, dtype=np.float64))
            if target_key in desired_world:
                local = _safe_inv(parent_world) @ desired_world[target_key]
            else:
                local, _derived = _derive_target_local(target_key, parent_key, target_skel, output_local, opts)
            world = parent_world @ local
            output_local[target_key] = local
            output_world[target_key] = world

            positions[frame_index, target_index, :] = local[:3, 3].astype(np.float32)
            rotations[frame_index, target_index, :] = matrix_to_quat_wxyz(local).astype(np.float32)
            scales[frame_index, target_index, :] = np.asarray((
                np.linalg.norm(local[:3, 0]),
                np.linalg.norm(local[:3, 1]),
                np.linalg.norm(local[:3, 2]),
            ), dtype=np.float32)
            if not np.all(np.isfinite(scales[frame_index, target_index, :])):
                scales[frame_index, target_index, :] = 1.0

    return SampledClip(
        clip_name=sampled_source.clip_name,
        fps=sampled_source.fps,
        frame_count=frame_count,
        bone_names=list(target_skel.bone_names),
        positions=positions,
        rotations=rotations,
        scales=scales,
        source_model=sampled_source.source_model,
        source_chain=list(sampled_source.source_chain),
        resolved_clip_source=sampled_source.resolved_clip_source,
        duration_s=sampled_source.duration_s,
        bake_math_audit_id=sampled_source.bake_math_audit_id,
        palette_frames=sampled_source.palette_frames,
    )


def max_quat_component_delta(a: np.ndarray, b: np.ndarray) -> float:
    """Return max component delta while accounting for q and -q equivalence."""

    aa = np.asarray(a, dtype=np.float64)
    bb = np.asarray(b, dtype=np.float64)
    direct = np.max(np.abs(aa - bb))
    flipped = np.max(np.abs(aa + bb))
    return float(min(direct, flipped))
