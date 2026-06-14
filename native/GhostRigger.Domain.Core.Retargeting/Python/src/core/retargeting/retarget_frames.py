"""Reference-frame rotation transfer helpers for basic retarget solving."""

from __future__ import annotations

import numpy as np

from .source_animation import Transform, matrix_to_quat_xyzw, quat_to_matrix_xyzw


def transfer_reference_frame_delta(
    *,
    source_anim_rotation,
    source_reference_rotation,
    target_reference_rotation,
    source_frame_rotation=None,
    target_frame_rotation=None,
) -> tuple[float, float, float, float]:
    """Transfer source reference-relative world motion into target reference space.

    The default frames are the source and target reference rotations. This
    keeps the first basic solver intentionally close to the chain/reference
    pose model used by retargeting tools while leaving room for richer segment
    frames later.
    """

    source_anim = _rot_matrix(source_anim_rotation)
    source_ref = _rot_matrix(source_reference_rotation)
    target_ref = _rot_matrix(target_reference_rotation)
    source_frame = _rot_matrix(source_frame_rotation or source_reference_rotation)
    target_frame = _rot_matrix(target_frame_rotation or target_reference_rotation)

    source_world_delta = source_anim @ np.linalg.inv(source_ref)
    semantic_delta = np.linalg.inv(source_frame) @ source_world_delta @ source_frame
    target_world_delta = target_frame @ semantic_delta @ np.linalg.inv(target_frame)
    desired_target_world = target_world_delta @ target_ref
    return matrix_to_quat_xyzw(_orthonormalized(desired_target_world))


def _rot_matrix(rotation) -> np.ndarray:
    return quat_to_matrix_xyzw(rotation)[:3, :3]


def _orthonormalized(matrix: np.ndarray) -> np.ndarray:
    u, _singular, vh = np.linalg.svd(np.asarray(matrix, dtype=np.float64)[:3, :3])
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = u @ vh
    return out
