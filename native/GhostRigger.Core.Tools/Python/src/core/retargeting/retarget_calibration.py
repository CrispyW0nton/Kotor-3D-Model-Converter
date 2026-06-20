"""Calibrated retarget frames for source-to-Aurora animation transfer.

KOTOR/Odyssey nodes are transform objects, not ordinary skeletal bones.  A
single parent->child direction is therefore an under-defined rotation target:
it constrains swing, but leaves the anatomical plane and twist ambiguous.  This
module builds full orthonormal frames from mapped reference-pose segments so the
solver can transfer source motion through a stable basis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from .reference_pose import ReferencePosePair
from .retarget_frame_audit import SEGMENT_ROLE_PAIRS
from .retarget_frames import transfer_reference_frame_delta
from .retarget_profile import RetargetMappingEntry, RetargetProfile
from .source_animation import (
    SourcePose,
    Transform,
    matrix_to_quat_xyzw,
    quat_to_matrix_xyzw,
)


@dataclass(frozen=True)
class RetargetFrameBasis:
    """A right-handed orthonormal frame anchored to a mapped segment."""

    origin: Tuple[float, float, float]
    primary_axis: Tuple[float, float, float]
    secondary_axis: Tuple[float, float, float]
    tertiary_axis: Tuple[float, float, float]
    rotation: Tuple[float, float, float, float]


@dataclass(frozen=True)
class CalibratedRetargetFrame:
    """Reference source/target frames for one mapped anatomical segment."""

    role: str
    side: str
    source_parent_node: str
    source_child_node: str
    target_parent_node: str
    target_child_node: str
    source_reference_basis: RetargetFrameBasis
    target_reference_basis: RetargetFrameBasis
    source_length: float
    target_length: float
    angular_difference_degrees: float
    warnings: Tuple[str, ...] = ()


@dataclass
class RetargetCalibrationReport:
    """All calibrated frames available to one retarget solve."""

    frames: List[CalibratedRetargetFrame] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.errors

    def by_target_parent(self) -> Dict[str, CalibratedRetargetFrame]:
        """Return first calibrated frame keyed by target parent node name."""

        result: Dict[str, CalibratedRetargetFrame] = {}
        for frame in self.frames:
            result.setdefault(frame.target_parent_node, frame)
        return result


def build_orthonormal_basis(
    primary: Iterable[float],
    *,
    secondary_hint: Optional[Iterable[float]] = None,
    fallback_rotation: Optional[Iterable[float]] = None,
) -> Optional[np.ndarray]:
    """Build a right-handed 3x3 basis from a primary axis and plane hint.

    The primary axis becomes the first column.  The secondary hint is projected
    onto the plane perpendicular to primary, then the third axis is computed by
    cross product.  A fallback rotation supplies stable hints when the supplied
    secondary vector is missing or nearly parallel to the primary axis.
    """

    x_axis = _normalize_vec(primary)
    if x_axis is None:
        return None

    hints: List[np.ndarray] = []
    if secondary_hint is not None:
        hints.append(np.asarray(tuple(secondary_hint), dtype=np.float64))
    if fallback_rotation is not None:
        fallback = quat_to_matrix_xyzw(fallback_rotation)[:3, :3]
        hints.extend([fallback[:, 1], fallback[:, 2], fallback[:, 0]])
    hints.extend(
        [
            np.asarray((0.0, 0.0, 1.0), dtype=np.float64),
            np.asarray((0.0, 1.0, 0.0), dtype=np.float64),
            np.asarray((1.0, 0.0, 0.0), dtype=np.float64),
        ]
    )

    y_axis = None
    for hint in hints:
        projected = hint - x_axis * float(np.dot(x_axis, hint))
        candidate = _normalize_vec(projected)
        if candidate is not None:
            y_axis = candidate
            break
    if y_axis is None:
        return None

    z_axis = _normalize_vec(np.cross(x_axis, y_axis))
    if z_axis is None:
        return None
    y_axis = _normalize_vec(np.cross(z_axis, x_axis))
    if y_axis is None:
        return None

    basis = np.column_stack((x_axis, y_axis, z_axis))
    if float(np.linalg.det(basis)) < 0.0:
        basis[:, 2] *= -1.0
    return _orthonormalized(basis)


def build_reference_basis_from_segment(
    *,
    parent_transform: Transform,
    child_transform: Transform,
    secondary_hint: Optional[Iterable[float]] = None,
) -> Optional[RetargetFrameBasis]:
    """Build a calibrated frame from parent/child reference transforms."""

    origin = np.asarray(parent_transform.position, dtype=np.float64)
    child = np.asarray(child_transform.position, dtype=np.float64)
    primary = child - origin
    basis = build_orthonormal_basis(
        primary,
        secondary_hint=secondary_hint,
        fallback_rotation=parent_transform.rotation,
    )
    if basis is None:
        return None
    return _basis_from_matrix(origin, basis)


def build_calibrated_retarget_frames(
    profile: RetargetProfile,
    reference_pair: ReferencePosePair,
) -> RetargetCalibrationReport:
    """Build calibrated source/target segment frames from mapped references."""

    report = RetargetCalibrationReport()
    by_role_side = _entries_by_role_side(profile.mappings)

    for parent_role, child_role in SEGMENT_ROLE_PAIRS:
        for side in _candidate_sides(profile.mappings, parent_role, child_role):
            parent = _entry_for(by_role_side, parent_role, side)
            child = _entry_for(by_role_side, child_role, side)
            if parent is None or child is None:
                continue
            frame = _build_frame_entry(parent, child, side, reference_pair)
            if frame is None:
                report.warnings.append(
                    f"Could not build calibrated frame for {parent_role}->{child_role} on side '{side}'."
                )
                continue
            report.frames.append(frame)
            report.warnings.extend(frame.warnings)

    return report


def current_source_basis_for_frame(
    frame: CalibratedRetargetFrame,
    source_pose: SourcePose,
) -> Optional[RetargetFrameBasis]:
    """Build the current source frame for a calibrated reference frame."""

    try:
        parent = source_pose.global_transforms[frame.source_parent_node]
        child = source_pose.global_transforms[frame.source_child_node]
    except KeyError:
        return None
    secondary_hint = quat_to_matrix_xyzw(parent.rotation)[:3, 1]
    return build_reference_basis_from_segment(
        parent_transform=parent,
        child_transform=child,
        secondary_hint=secondary_hint,
    )


def transfer_calibrated_frame_delta(
    *,
    source_current_basis: RetargetFrameBasis,
    calibrated_frame: CalibratedRetargetFrame,
    target_reference_rotation,
) -> Tuple[float, float, float, float]:
    """Transfer current source basis motion through calibrated target basis."""

    return transfer_reference_frame_delta(
        source_anim_rotation=source_current_basis.rotation,
        source_reference_rotation=calibrated_frame.source_reference_basis.rotation,
        target_reference_rotation=target_reference_rotation,
        source_frame_rotation=calibrated_frame.source_reference_basis.rotation,
        target_frame_rotation=calibrated_frame.target_reference_basis.rotation,
    )


def _build_frame_entry(
    parent: RetargetMappingEntry,
    child: RetargetMappingEntry,
    side: str,
    reference_pair: ReferencePosePair,
) -> Optional[CalibratedRetargetFrame]:
    try:
        source_parent = reference_pair.source_pose.global_transforms[parent.source_node]
        source_child = reference_pair.source_pose.global_transforms[child.source_node]
        target_parent = reference_pair.target_global_transforms[parent.target_node]
        target_child = reference_pair.target_global_transforms[child.target_node]
    except KeyError:
        return None

    source_secondary = quat_to_matrix_xyzw(source_parent.rotation)[:3, 1]
    target_secondary = quat_to_matrix_xyzw(target_parent.rotation)[:3, 1]
    source_basis = build_reference_basis_from_segment(
        parent_transform=source_parent,
        child_transform=source_child,
        secondary_hint=source_secondary,
    )
    target_basis = build_reference_basis_from_segment(
        parent_transform=target_parent,
        child_transform=target_child,
        secondary_hint=target_secondary,
    )
    if source_basis is None or target_basis is None:
        return None

    source_length = _distance(source_parent.position, source_child.position)
    target_length = _distance(target_parent.position, target_child.position)
    angle = _angle_between_degrees(
        np.asarray(source_basis.primary_axis, dtype=np.float64),
        np.asarray(target_basis.primary_axis, dtype=np.float64),
    )
    warnings: List[str] = []
    if source_length <= 1e-8:
        warnings.append(f"Calibrated frame {parent.role}->{child.role} has zero-length source segment.")
    if target_length <= 1e-8:
        warnings.append(f"Calibrated frame {parent.role}->{child.role} has zero-length target segment.")
    if source_length > 1e-8 and target_length > 1e-8:
        ratio = target_length / source_length
        if ratio < 0.1 or ratio > 10.0:
            warnings.append(
                f"Calibrated frame {parent.role}->{child.role} has large target/source length ratio {ratio:.3g}."
            )

    return CalibratedRetargetFrame(
        role=f"{parent.role}->{child.role}",
        side=side,
        source_parent_node=parent.source_node,
        source_child_node=child.source_node,
        target_parent_node=parent.target_node,
        target_child_node=child.target_node,
        source_reference_basis=source_basis,
        target_reference_basis=target_basis,
        source_length=source_length,
        target_length=target_length,
        angular_difference_degrees=angle,
        warnings=tuple(warnings),
    )


def _basis_from_matrix(origin: np.ndarray, basis: np.ndarray) -> RetargetFrameBasis:
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = _orthonormalized(basis)
    return RetargetFrameBasis(
        origin=tuple(float(value) for value in origin),
        primary_axis=tuple(float(value) for value in matrix[:3, 0]),
        secondary_axis=tuple(float(value) for value in matrix[:3, 1]),
        tertiary_axis=tuple(float(value) for value in matrix[:3, 2]),
        rotation=matrix_to_quat_xyzw(matrix),
    )


def _entries_by_role_side(
    mappings: Iterable[RetargetMappingEntry],
) -> Dict[Tuple[str, str], RetargetMappingEntry]:
    result: Dict[Tuple[str, str], RetargetMappingEntry] = {}
    for entry in mappings:
        role = str(entry.role or "").strip().lower()
        side = str(entry.side or "center").strip().lower() or "center"
        result.setdefault((role, side), entry)
    return result


def _candidate_sides(
    mappings: Iterable[RetargetMappingEntry],
    parent_role: str,
    child_role: str,
) -> List[str]:
    sides = {
        str(entry.side or "center").strip().lower() or "center"
        for entry in mappings
        if str(entry.role or "").strip().lower() in {parent_role, child_role}
    }
    return sorted(sides or {"center"})


def _entry_for(
    by_role_side: Dict[Tuple[str, str], RetargetMappingEntry],
    role: str,
    side: str,
) -> Optional[RetargetMappingEntry]:
    return by_role_side.get((role, side)) or by_role_side.get((role, "center"))


def _normalize_vec(value: Iterable[float]) -> Optional[np.ndarray]:
    vec = np.asarray(tuple(value), dtype=np.float64)
    length = float(np.linalg.norm(vec))
    if length <= 1e-8 or not math.isfinite(length):
        return None
    return vec / length


def _orthonormalized(matrix: np.ndarray) -> np.ndarray:
    u, _singular, vh = np.linalg.svd(np.asarray(matrix, dtype=np.float64)[:3, :3])
    out = u @ vh
    if float(np.linalg.det(out)) < 0.0:
        out[:, 2] *= -1.0
    return out


def _distance(a: Iterable[float], b: Iterable[float]) -> float:
    return float(np.linalg.norm(np.asarray(tuple(b), dtype=np.float64) - np.asarray(tuple(a), dtype=np.float64)))


def _angle_between_degrees(a: np.ndarray, b: np.ndarray) -> float:
    a_norm = _normalize_vec(a)
    b_norm = _normalize_vec(b)
    if a_norm is None or b_norm is None:
        return 0.0
    dot = max(-1.0, min(1.0, float(np.dot(a_norm, b_norm))))
    return math.degrees(math.acos(dot))
