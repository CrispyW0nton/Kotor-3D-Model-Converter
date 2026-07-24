"""Named-space transforms for stock Head Builder component payloads.

Carrier node transforms are immutable.  When geometry comes from another
vanilla head, its vertices and normals must be rebased from the source node's
local space into the carrier node's local space before the payload is copied.
UVs and skin palette identities are not spatial channels and are untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np


Vec3 = tuple[float, float, float]
Mat4 = tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]


@dataclass(frozen=True, slots=True)
class HeadComponentRebase:
    source_node_local_to_world: Mat4
    world_to_carrier_node_local: Mat4
    source_node_local_to_carrier_node_local: Mat4
    skin_translation_only: bool


def build_head_component_rebase(
    source_node: Any,
    carrier_node: Any,
    *,
    skin_translation_only: bool,
) -> HeadComponentRebase:
    """Return the explicit source-local → carrier-local transform contract."""

    source_world = _node_world_matrix(
        source_node,
        translation_only=skin_translation_only,
    )
    carrier_world = _node_world_matrix(
        carrier_node,
        translation_only=skin_translation_only,
    )
    try:
        world_to_carrier = np.linalg.inv(
            np.asarray(carrier_world, dtype=np.float64)
        )
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "Carrier component node world transform is not invertible"
        ) from exc
    source_to_carrier = world_to_carrier @ np.asarray(
        source_world,
        dtype=np.float64,
    )
    return HeadComponentRebase(
        source_node_local_to_world=_matrix_tuple(source_world),
        world_to_carrier_node_local=_matrix_tuple(world_to_carrier),
        source_node_local_to_carrier_node_local=_matrix_tuple(
            source_to_carrier
        ),
        skin_translation_only=bool(skin_translation_only),
    )


def rebase_head_component_channels(
    *,
    vertices: Sequence[Sequence[float]],
    normals: Sequence[Sequence[float]],
    tangents: Sequence[Sequence[float]],
    rebase: HeadComponentRebase,
) -> tuple[tuple[Vec3, ...], tuple[Vec3, ...], tuple[Vec3, ...]]:
    """Rebase point/vector channels while preserving their channel semantics."""

    matrix = np.asarray(
        rebase.source_node_local_to_carrier_node_local,
        dtype=np.float64,
    )
    linear = matrix[:3, :3]
    try:
        normal_matrix = np.linalg.inv(linear).T
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "Component rebase has a non-invertible normal transform"
        ) from exc

    rebased_vertices = tuple(
        _point(matrix, row) for row in vertices
    )
    rebased_normals = tuple(
        _normalized_vector(normal_matrix, row) for row in normals
    )
    rebased_tangents = tuple(
        _normalized_vector(linear, row) for row in tangents
    )
    return rebased_vertices, rebased_normals, rebased_tangents


def _node_world_matrix(
    node: Any,
    *,
    translation_only: bool,
) -> np.ndarray:
    world_transform = getattr(node, "world_transform", None)
    if callable(world_transform):
        position, rotation = world_transform()
    else:
        position = getattr(node, "position", (0.0, 0.0, 0.0))
        rotation = getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))
    position_row = tuple(float(value) for value in position)
    rotation_row = tuple(float(value) for value in rotation)
    if len(position_row) != 3 or len(rotation_row) != 4:
        raise ValueError("Component node transform must be position3 + quat4")
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, 3] = np.asarray(position_row, dtype=np.float64)
    if not translation_only:
        matrix[:3, :3] = _quaternion_matrix(rotation_row)
    return matrix


def _quaternion_matrix(
    value: Sequence[float],
) -> np.ndarray:
    x, y, z, w = (float(component) for component in value)
    length = float(np.linalg.norm((x, y, z, w)))
    if length <= 1.0e-12:
        return np.eye(3, dtype=np.float64)
    x, y, z, w = (component / length for component in (x, y, z, w))
    return np.asarray(
        (
            (
                1.0 - 2.0 * (y * y + z * z),
                2.0 * (x * y - z * w),
                2.0 * (x * z + y * w),
            ),
            (
                2.0 * (x * y + z * w),
                1.0 - 2.0 * (x * x + z * z),
                2.0 * (y * z - x * w),
            ),
            (
                2.0 * (x * z - y * w),
                2.0 * (y * z + x * w),
                1.0 - 2.0 * (x * x + y * y),
            ),
        ),
        dtype=np.float64,
    )


def _point(matrix: np.ndarray, value: Sequence[float]) -> Vec3:
    row = np.asarray((*_vec3(value), 1.0), dtype=np.float64)
    transformed = matrix @ row
    if abs(float(transformed[3])) <= 1.0e-12:
        raise ValueError("Component point transform produced invalid w")
    return tuple(
        float(component)
        for component in (transformed[:3] / transformed[3])
    )


def _normalized_vector(
    matrix: np.ndarray,
    value: Sequence[float],
) -> Vec3:
    transformed = matrix @ np.asarray(_vec3(value), dtype=np.float64)
    length = float(np.linalg.norm(transformed))
    if length <= 1.0e-12:
        return (0.0, 0.0, 0.0)
    return tuple(float(component) for component in transformed / length)


def _vec3(value: Sequence[float]) -> Vec3:
    row = tuple(float(component) for component in value)
    if len(row) != 3:
        raise ValueError("Component channel rows must contain three values")
    return row


def _matrix_tuple(value: Any) -> Mat4:
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.shape != (4, 4):
        raise ValueError("Component transforms must be 4x4")
    return tuple(
        tuple(float(component) for component in row)
        for row in matrix
    )  # type: ignore[return-value]


__all__ = [
    "HeadComponentRebase",
    "build_head_component_rebase",
    "rebase_head_component_channels",
]
