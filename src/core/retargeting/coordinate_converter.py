"""UE5/Unity-style to Aurora coordinate conversion for reverse retargeting.

The conversion maps UE's exported humanoid convention to the PMBAM/Aurora
viewport convention used by GhostRigger.  Current stock PMBAM calibration shows
the lowest rest-pose segment error with X and Y mirrored while preserving Z-up:
``(-X, -Y, Z)``.  The transform is
involutive, so the same mapping can be used for the reverse direction after
accounting for quaternion storage order.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Tuple


@dataclass(frozen=True)
class Quaternion:
    """Quaternion stored in Aurora-friendly WXYZ order."""

    w: float
    x: float
    y: float
    z: float

    @classmethod
    def from_xyzw(cls, x: float, y: float, z: float, w: float) -> "Quaternion":
        return cls(w=float(w), x=float(x), y=float(y), z=float(z)).normalized()

    def normalized(self) -> "Quaternion":
        mag = math.sqrt(self.w * self.w + self.x * self.x + self.y * self.y + self.z * self.z)
        if mag <= 1e-12:
            return Quaternion(1.0, 0.0, 0.0, 0.0)
        return Quaternion(self.w / mag, self.x / mag, self.y / mag, self.z / mag)

    def to_xyzw(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.z, self.w)

    def to_wxyz(self) -> Tuple[float, float, float, float]:
        return (self.w, self.x, self.y, self.z)


@dataclass(frozen=True)
class Vector3:
    x: float
    y: float
    z: float

    def to_xyz(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)


def aurora_from_ue5_quat(ue5_xyzw: Tuple[float, float, float, float]) -> Quaternion:
    """Convert UE5/Unity-style XYZW quaternion to Aurora WXYZ."""

    x, y, z, w = (float(v) for v in ue5_xyzw)
    return Quaternion(w=w, x=-x, y=-y, z=z).normalized()


def ue5_from_aurora_quat(aurora_wxyz: Tuple[float, float, float, float]) -> Quaternion:
    """Convert Aurora WXYZ quaternion back to UE5/Unity-style storage."""

    w, x, y, z = (float(v) for v in aurora_wxyz)
    return Quaternion(w=w, x=-x, y=-y, z=z).normalized()


def aurora_from_ue5_position(ue5_xyz: Tuple[float, float, float]) -> Vector3:
    """Convert UE5/Unity-style position to Aurora with calibrated X/Y mirror."""

    x, y, z = (float(v) for v in ue5_xyz)
    return Vector3(x=-x, y=-y, z=z)


def ue5_from_aurora_position(aurora_xyz: Tuple[float, float, float]) -> Vector3:
    """Convert Aurora position back to UE5/Unity-style coordinates."""

    x, y, z = (float(v) for v in aurora_xyz)
    return Vector3(x=-x, y=-y, z=z)


def verify_round_trip(
    quat_xyzw: Tuple[float, float, float, float],
    pos_xyz: Tuple[float, float, float],
    tolerance: float = 1e-6,
) -> bool:
    """Return True when UE5 -> Aurora -> UE5 preserves values within tolerance."""

    q_aurora = aurora_from_ue5_quat(quat_xyzw)
    q_back = ue5_from_aurora_quat(q_aurora.to_wxyz())
    if any(abs(a - b) > tolerance for a, b in zip(quat_xyzw, q_back.to_xyzw())):
        return False

    p_aurora = aurora_from_ue5_position(pos_xyz)
    p_back = ue5_from_aurora_position(p_aurora.to_xyz())
    return all(abs(a - b) <= tolerance for a, b in zip(pos_xyz, p_back.to_xyz()))
