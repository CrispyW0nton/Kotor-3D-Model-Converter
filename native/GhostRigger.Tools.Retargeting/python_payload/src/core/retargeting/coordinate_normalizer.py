"""Canonical coordinate-space helpers for GhostRigger retargeting.

Retargeting code uses one convention at its boundary: world-space transforms,
Z-up right-handed coordinates, and WXYZ quaternions.  GhostRigger's in-memory
``ModelNode`` rotations are XYZW, so this module is the explicit conversion
point.  Aurora/KotOR bind matrices are cross-checked against the audited G5
``MatrixPaletteUploader`` inverse-bind cache.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional

import numpy as np

from src.core.animation.gpu_skinning import MatrixPaletteUploader
from src.core.geometry.model_data import KotorModel, ModelNode


IDENTITY_WXYZ = np.asarray((1.0, 0.0, 0.0, 0.0), dtype=np.float64)


def _key(name: str) -> str:
    return str(name or "").strip().lower()


def normalize_quat_wxyz(quat: Iterable[float]) -> np.ndarray:
    values = np.asarray(list(quat), dtype=np.float64)
    if values.shape[0] < 4:
        values = np.pad(values, (0, 4 - values.shape[0]))
        values[0] = 1.0
    values = values[:4]
    length = float(np.linalg.norm(values))
    if length <= 1e-12:
        return IDENTITY_WXYZ.copy()
    return values / length


def xyzw_to_wxyz(quat: Iterable[float]) -> np.ndarray:
    values = list(quat or (0.0, 0.0, 0.0, 1.0))
    values = (values + [0.0, 0.0, 0.0, 1.0])[:4]
    return normalize_quat_wxyz((values[3], values[0], values[1], values[2]))


def wxyz_to_xyzw(quat: Iterable[float]) -> np.ndarray:
    w, x, y, z = normalize_quat_wxyz(quat)
    return np.asarray((x, y, z, w), dtype=np.float64)


def quat_conjugate_wxyz(quat: Iterable[float]) -> np.ndarray:
    w, x, y, z = normalize_quat_wxyz(quat)
    return np.asarray((w, -x, -y, -z), dtype=np.float64)


def quat_inverse_wxyz(quat: Iterable[float]) -> np.ndarray:
    return quat_conjugate_wxyz(quat)


def quat_mul_wxyz(a: Iterable[float], b: Iterable[float]) -> np.ndarray:
    aw, ax, ay, az = normalize_quat_wxyz(a)
    bw, bx, by, bz = normalize_quat_wxyz(b)
    return normalize_quat_wxyz((
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    ))


def quat_to_matrix_wxyz(quat: Iterable[float]) -> np.ndarray:
    w, x, y, z = normalize_quat_wxyz(quat)
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = np.asarray((
        (1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)),
        (2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)),
        (2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)),
    ), dtype=np.float64)
    return out


def matrix_to_quat_wxyz(matrix: np.ndarray) -> np.ndarray:
    rot = np.asarray(matrix, dtype=np.float64)[:3, :3]
    trace = float(np.trace(rot))
    if trace > 0.0:
        s = np.sqrt(trace + 1.0) * 2.0
        w = 0.25 * s
        x = (rot[2, 1] - rot[1, 2]) / s
        y = (rot[0, 2] - rot[2, 0]) / s
        z = (rot[1, 0] - rot[0, 1]) / s
    else:
        diag = np.diag(rot)
        idx = int(np.argmax(diag))
        if idx == 0:
            s = np.sqrt(1.0 + rot[0, 0] - rot[1, 1] - rot[2, 2]) * 2.0
            w = (rot[2, 1] - rot[1, 2]) / s
            x = 0.25 * s
            y = (rot[0, 1] + rot[1, 0]) / s
            z = (rot[0, 2] + rot[2, 0]) / s
        elif idx == 1:
            s = np.sqrt(1.0 + rot[1, 1] - rot[0, 0] - rot[2, 2]) * 2.0
            w = (rot[0, 2] - rot[2, 0]) / s
            x = (rot[0, 1] + rot[1, 0]) / s
            y = 0.25 * s
            z = (rot[1, 2] + rot[2, 1]) / s
        else:
            s = np.sqrt(1.0 + rot[2, 2] - rot[0, 0] - rot[1, 1]) * 2.0
            w = (rot[1, 0] - rot[0, 1]) / s
            x = (rot[0, 2] + rot[2, 0]) / s
            y = (rot[1, 2] + rot[2, 1]) / s
            z = 0.25 * s
    return normalize_quat_wxyz((w, x, y, z))


def translation_matrix(position: Iterable[float]) -> np.ndarray:
    values = list((0.0, 0.0, 0.0) if position is None else position)
    values = (values + [0.0, 0.0, 0.0])[:3]
    out = np.eye(4, dtype=np.float64)
    out[:3, 3] = np.asarray(values, dtype=np.float64)
    return out


def scale_matrix(scale: Iterable[float] | float | None = None) -> np.ndarray:
    if scale is None:
        values = (1.0, 1.0, 1.0)
    elif isinstance(scale, (int, float)):
        values = (float(scale), float(scale), float(scale))
    else:
        raw = list(scale)
        values = tuple((raw + [1.0, 1.0, 1.0])[:3])
    out = np.eye(4, dtype=np.float64)
    out[0, 0] = float(values[0])
    out[1, 1] = float(values[1])
    out[2, 2] = float(values[2])
    return out


def compose_matrix(
    position: Iterable[float],
    rotation_wxyz: Iterable[float],
    scale: Iterable[float] | float | None = None,
) -> np.ndarray:
    return translation_matrix(position) @ quat_to_matrix_wxyz(rotation_wxyz) @ scale_matrix(scale)


def transform_position(matrix: np.ndarray, position: Iterable[float]) -> np.ndarray:
    values = list((0.0, 0.0, 0.0) if position is None else position)
    values = (values + [0.0, 0.0, 0.0])[:3]
    point = np.asarray((values[0], values[1], values[2], 1.0), dtype=np.float64)
    return (np.asarray(matrix, dtype=np.float64) @ point)[:3]


def _mat_from_g5(value: Iterable[Iterable[float]]) -> np.ndarray:
    return np.asarray([[float(col) for col in row] for row in value], dtype=np.float64)


@dataclass
class BindPoseRegistry:
    """World-space bind-pose cache in canonical retargeting coordinates."""

    skeleton_id: str
    bone_names: List[str]
    bone_index: Dict[str, int]
    parents: Dict[str, str]
    bind_world: Dict[str, np.ndarray]
    bind_world_inv: Dict[str, np.ndarray]
    local_bind: Dict[str, np.ndarray]
    node_lookup: Dict[str, ModelNode] = field(default_factory=dict)
    g5_inverse_bind_delta_max: float = 0.0
    g5_bone_count: int = 0

    def has_bone(self, name: str) -> bool:
        return _key(name) in self.bind_world

    def world_matrix(self, name: str) -> np.ndarray:
        return self.bind_world[_key(name)]

    def world_inverse(self, name: str) -> np.ndarray:
        return self.bind_world_inv[_key(name)]

    def local_matrix(self, name: str) -> np.ndarray:
        return self.local_bind[_key(name)]

    def parent_key(self, name: str) -> str:
        return self.parents.get(_key(name), "")

    def world_position(self, name: str) -> np.ndarray:
        return self.world_matrix(name)[:3, 3].copy()

    def world_rotation(self, name: str) -> np.ndarray:
        return matrix_to_quat_wxyz(self.world_matrix(name))

    def local_position(self, name: str) -> np.ndarray:
        return self.local_matrix(name)[:3, 3].copy()

    def local_rotation(self, name: str) -> np.ndarray:
        return matrix_to_quat_wxyz(self.local_matrix(name))


class CoordinateNormalizer:
    """Single source of truth for retargeting coordinate conversions."""

    CANONICAL_AXIS = "Z_UP_RH_WXYZ"

    def normalize_aurora_bind(self, model: KotorModel, skeleton_id: str | None = None) -> BindPoseRegistry:
        return self.normalize_model_bind(model, skeleton_id=skeleton_id or str(getattr(model, "name", "") or "aurora"))

    def normalize_ue5_bind(self, model: KotorModel, skeleton_id: str | None = None) -> BindPoseRegistry:
        # Quinn is converted into GhostRigger's canonical model coordinates by
        # src.unreal.quinn before it reaches this normalizer. Raw FBX axis
        # conversion belongs at the FBX import/export boundary.
        return self.normalize_model_bind(model, skeleton_id=skeleton_id or str(getattr(model, "name", "") or "ue5"))

    def normalize_model_bind(self, model: KotorModel, skeleton_id: str) -> BindPoseRegistry:
        nodes = [
            node for node in (list(model.all_nodes()) if callable(getattr(model, "all_nodes", None)) else [])
            if str(getattr(node, "name", "") or "") and not bool(getattr(node, "is_skin", False))
        ]
        local_bind: Dict[str, np.ndarray] = {}
        bind_world: Dict[str, np.ndarray] = {}
        parents: Dict[str, str] = {}
        node_lookup: Dict[str, ModelNode] = {}
        bone_names: List[str] = []

        for node in nodes:
            name = str(getattr(node, "name", "") or "")
            key = _key(name)
            bone_names.append(name)
            node_lookup[key] = node
            parent = getattr(node, "parent", None)
            parent_key = _key(getattr(parent, "name", "") if parent is not None else "")
            if parent_key and parent_key != key:
                parents[key] = parent_key
            local_bind[key] = compose_matrix(
                getattr(node, "position", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0),
                xyzw_to_wxyz(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0)),
            )

        for name in bone_names:
            key = _key(name)
            parent_key = parents.get(key, "")
            parent_world = bind_world.get(parent_key)
            bind_world[key] = (parent_world @ local_bind[key]) if parent_world is not None else local_bind[key]

        bind_world_inv = {
            key: np.linalg.inv(matrix)
            for key, matrix in bind_world.items()
        }
        g5_count, g5_delta = self._compare_g5_inverse_bind(model, bind_world_inv)
        return BindPoseRegistry(
            skeleton_id=str(skeleton_id),
            bone_names=bone_names,
            bone_index={_key(name): idx for idx, name in enumerate(bone_names)},
            parents=parents,
            bind_world=bind_world,
            bind_world_inv=bind_world_inv,
            local_bind=local_bind,
            node_lookup=node_lookup,
            g5_inverse_bind_delta_max=g5_delta,
            g5_bone_count=g5_count,
        )

    def normalize_vertex_positions(self, positions: np.ndarray, parent_world_transform: np.ndarray) -> np.ndarray:
        vertices = np.asarray(positions, dtype=np.float64)
        ones = np.ones((vertices.shape[0], 1), dtype=np.float64)
        hom = np.concatenate([vertices, ones], axis=1)
        return (np.asarray(parent_world_transform, dtype=np.float64) @ hom.T).T[:, :3]

    def _compare_g5_inverse_bind(
        self,
        model: KotorModel,
        bind_world_inv: Mapping[str, np.ndarray],
    ) -> tuple[int, float]:
        uploader = MatrixPaletteUploader()
        count = uploader.build_inverse_bind_pose(model)
        raw_inv = getattr(uploader, "_inv_bind", {}) or {}
        max_delta = 0.0
        for name, matrix in raw_inv.items():
            key = _key(name)
            if key not in bind_world_inv:
                continue
            delta = float(np.max(np.abs(_mat_from_g5(matrix) - bind_world_inv[key])))
            max_delta = max(max_delta, delta)
        return int(count), max_delta
