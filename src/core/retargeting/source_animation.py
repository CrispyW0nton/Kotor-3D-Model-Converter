"""Backend-neutral source skeleton animation clip data for UE/FBX imports."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np


IDENTITY_XYZW: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)


def normalize_quat_xyzw(quat: Iterable[float]) -> Tuple[float, float, float, float]:
    """Normalize a GhostRigger XYZW quaternion."""

    raw = list(quat or IDENTITY_XYZW)
    values = (raw + [0.0, 0.0, 0.0, 1.0])[:4]
    x, y, z, w = (float(value) for value in values)
    mag_sq = x * x + y * y + z * z + w * w
    if mag_sq <= 1e-12:
        return IDENTITY_XYZW
    mag = math.sqrt(mag_sq)
    return (x / mag, y / mag, z / mag, w / mag)


def quat_dot_xyzw(a: Iterable[float], b: Iterable[float]) -> float:
    qa = normalize_quat_xyzw(a)
    qb = normalize_quat_xyzw(b)
    return sum(x * y for x, y in zip(qa, qb))


def hemisphere_continuity_xyzw(
    quat: Iterable[float],
    previous: Optional[Iterable[float]],
) -> Tuple[float, float, float, float]:
    """Normalize ``quat`` and flip sign if needed to stay near ``previous``."""

    q = normalize_quat_xyzw(quat)
    if previous is not None and quat_dot_xyzw(q, previous) < 0.0:
        return tuple(-value for value in q)  # type: ignore[return-value]
    return q


def matrix_to_quat_xyzw(matrix: np.ndarray) -> Tuple[float, float, float, float]:
    """Convert the rotation component of a matrix to GhostRigger XYZW order."""

    rot = np.asarray(matrix, dtype=np.float64)[:3, :3]
    trace = float(np.trace(rot))
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * s
        x = (rot[2, 1] - rot[1, 2]) / s
        y = (rot[0, 2] - rot[2, 0]) / s
        z = (rot[1, 0] - rot[0, 1]) / s
    else:
        diag = np.diag(rot)
        idx = int(np.argmax(diag))
        if idx == 0:
            s = math.sqrt(max(0.0, 1.0 + rot[0, 0] - rot[1, 1] - rot[2, 2])) * 2.0
            x = 0.25 * s
            y = (rot[0, 1] + rot[1, 0]) / s if s else 0.0
            z = (rot[0, 2] + rot[2, 0]) / s if s else 0.0
            w = (rot[2, 1] - rot[1, 2]) / s if s else 1.0
        elif idx == 1:
            s = math.sqrt(max(0.0, 1.0 + rot[1, 1] - rot[0, 0] - rot[2, 2])) * 2.0
            x = (rot[0, 1] + rot[1, 0]) / s if s else 0.0
            y = 0.25 * s
            z = (rot[1, 2] + rot[2, 1]) / s if s else 0.0
            w = (rot[0, 2] - rot[2, 0]) / s if s else 1.0
        else:
            s = math.sqrt(max(0.0, 1.0 + rot[2, 2] - rot[0, 0] - rot[1, 1])) * 2.0
            x = (rot[0, 2] + rot[2, 0]) / s if s else 0.0
            y = (rot[1, 2] + rot[2, 1]) / s if s else 0.0
            z = 0.25 * s
            w = (rot[1, 0] - rot[0, 1]) / s if s else 1.0
    return normalize_quat_xyzw((x, y, z, w))


def quat_to_matrix_xyzw(quat: Iterable[float]) -> np.ndarray:
    """Return a 4x4 rotation matrix for an XYZW quaternion."""

    x, y, z, w = normalize_quat_xyzw(quat)
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = np.asarray(
        (
            (1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)),
            (2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)),
            (2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)),
        ),
        dtype=np.float64,
    )
    return out


@dataclass(frozen=True)
class Transform:
    """TRS transform with GhostRigger XYZW quaternion storage."""

    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: Tuple[float, float, float, float] = IDENTITY_XYZW
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)

    @classmethod
    def from_matrix(cls, matrix: Iterable[Iterable[float]]) -> "Transform":
        mat = np.asarray(matrix, dtype=np.float64)
        if mat.shape != (4, 4):
            raise ValueError(f"Transform matrix must be 4x4, got {mat.shape}")
        position = tuple(float(value) for value in mat[:3, 3])
        basis = mat[:3, :3].copy()
        scale_values = []
        for col in range(3):
            length = float(np.linalg.norm(basis[:, col]))
            if length <= 1e-12:
                length = 1.0
            scale_values.append(length)
            basis[:, col] /= length
        return cls(
            position=position,  # type: ignore[arg-type]
            rotation=matrix_to_quat_xyzw(basis),
            scale=tuple(scale_values),  # type: ignore[arg-type]
        )

    def to_matrix(self) -> np.ndarray:
        mat = quat_to_matrix_xyzw(self.rotation)
        for col, value in enumerate(self.scale):
            mat[:3, col] *= float(value)
        mat[:3, 3] = np.asarray(self.position, dtype=np.float64)
        return mat

    def is_finite(self) -> bool:
        return all(
            math.isfinite(float(value))
            for value in (*self.position, *self.rotation, *self.scale)
        )


@dataclass(frozen=True)
class SourceSkeletonNode:
    """One source skeleton node imported from UE/FBX."""

    name: str
    parent_name: Optional[str]
    index: int
    rest_local: Transform
    rest_global: Transform
    classification: str = "deform"


@dataclass
class SourcePose:
    """One sampled source pose in both global and local transform spaces."""

    time_seconds: float
    global_transforms: Dict[str, Transform]
    local_transforms: Dict[str, Transform]


@dataclass
class SourceSkeletonClip:
    """Sampled source skeleton clip ready for later retargeting."""

    source_path: str
    clip_name: str
    duration_seconds: float
    sample_rate: float
    nodes: List[SourceSkeletonNode]
    rest_pose: SourcePose
    sampled_poses: List[SourcePose]
    axis_system: Optional[str] = None
    unit_scale_to_meters: Optional[float] = None
    handedness: Optional[str] = None
    import_warnings: List[str] = field(default_factory=list)

    @property
    def node_names(self) -> List[str]:
        return [node.name for node in self.nodes]

    def pose_at_time(self, time_seconds: float) -> SourcePose:
        if not self.sampled_poses:
            raise ValueError("SourceSkeletonClip has no sampled poses")
        return min(self.sampled_poses, key=lambda pose: abs(pose.time_seconds - time_seconds))
