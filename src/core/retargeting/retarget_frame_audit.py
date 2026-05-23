"""Diagnostic segment-frame audit for source-to-Aurora retarget profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from .reference_pose import ReferencePosePair
from .retarget_profile import RetargetMappingEntry, RetargetProfile


SEGMENT_ROLE_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("upperarm", "forearm"),
    ("forearm", "hand"),
    ("hand", "middle_base"),
    ("middle_base", "middle_tip"),
    ("thigh", "calf"),
    ("calf", "foot"),
    ("foot", "toe"),
    ("spine", "chest"),
    ("neck", "head"),
)


@dataclass
class RetargetSegmentAuditEntry:
    """One mapped source/target segment comparison."""

    parent_role: str
    child_role: str
    side: str
    source_parent_node: str
    source_child_node: str
    target_parent_node: str
    target_child_node: str
    source_length: float
    target_length: float
    length_ratio: Optional[float]
    angular_difference_degrees: Optional[float]
    warnings: List[str] = field(default_factory=list)


@dataclass
class RetargetFrameAudit:
    """Diagnostic report for mapped segment lengths/directions."""

    entries: List[RetargetSegmentAuditEntry] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.errors


def audit_retarget_reference_frames(
    profile: RetargetProfile,
    reference_pair: ReferencePosePair,
) -> RetargetFrameAudit:
    """Compare mapped source/target segment lengths and directions."""

    audit = RetargetFrameAudit()
    by_role_side = _entries_by_role_side(profile.mappings)

    for parent_role, child_role in SEGMENT_ROLE_PAIRS:
        sides = _candidate_sides(profile.mappings, parent_role, child_role)
        for side in sides:
            parent = _entry_for(by_role_side, parent_role, side)
            child = _entry_for(by_role_side, child_role, side)
            if not parent or not child:
                if parent or child:
                    audit.warnings.append(
                        f"Mapped segment {parent_role}->{child_role} on side '{side}' is incomplete."
                    )
                continue
            entry = _audit_segment(parent, child, side, reference_pair)
            audit.entries.append(entry)
            audit.warnings.extend(entry.warnings)

    return audit


def _entries_by_role_side(
    mappings: Iterable[RetargetMappingEntry],
) -> Dict[Tuple[str, str], RetargetMappingEntry]:
    result: Dict[Tuple[str, str], RetargetMappingEntry] = {}
    for entry in mappings:
        role = str(entry.role or "").strip()
        side = str(entry.side or "center").strip() or "center"
        result.setdefault((role, side), entry)
    return result


def _candidate_sides(
    mappings: Iterable[RetargetMappingEntry],
    parent_role: str,
    child_role: str,
) -> List[str]:
    sides = {
        str(entry.side or "center").strip() or "center"
        for entry in mappings
        if entry.role in {parent_role, child_role}
    }
    if not sides:
        sides = {"center"}
    return sorted(sides)


def _entry_for(
    by_role_side: Dict[Tuple[str, str], RetargetMappingEntry],
    role: str,
    side: str,
) -> Optional[RetargetMappingEntry]:
    return by_role_side.get((role, side)) or by_role_side.get((role, "center"))


def _audit_segment(
    parent: RetargetMappingEntry,
    child: RetargetMappingEntry,
    side: str,
    reference_pair: ReferencePosePair,
) -> RetargetSegmentAuditEntry:
    source_parent = _position(reference_pair.source_pose.global_transforms[parent.source_node])
    source_child = _position(reference_pair.source_pose.global_transforms[child.source_node])
    target_parent = _position(reference_pair.target_global_transforms[parent.target_node])
    target_child = _position(reference_pair.target_global_transforms[child.target_node])

    source_vec = source_child - source_parent
    target_vec = target_child - target_parent
    source_length = float(np.linalg.norm(source_vec))
    target_length = float(np.linalg.norm(target_vec))
    warnings: List[str] = []

    if source_length <= 1e-8:
        warnings.append(
            f"Mapped segment {parent.role}->{child.role} on side '{side}' has zero-length source segment."
        )
    if target_length <= 1e-8:
        warnings.append(
            f"Mapped segment {parent.role}->{child.role} on side '{side}' has zero-length target segment."
        )

    length_ratio = None
    angular_difference = None
    if source_length > 1e-8 and target_length > 1e-8:
        length_ratio = target_length / source_length
        if length_ratio > 10.0 or length_ratio < 0.1:
            warnings.append(
                f"Mapped segment {parent.role}->{child.role} on side '{side}' has large length ratio {length_ratio:.3g}."
            )
        angular_difference = _angle_degrees(source_vec, target_vec)
        if angular_difference >= 170.0:
            warnings.append(
                f"Mapped segment {parent.role}->{child.role} on side '{side}' directions differ by {angular_difference:.1f} degrees."
            )

    return RetargetSegmentAuditEntry(
        parent_role=parent.role,
        child_role=child.role,
        side=side,
        source_parent_node=parent.source_node,
        source_child_node=child.source_node,
        target_parent_node=parent.target_node,
        target_child_node=child.target_node,
        source_length=source_length,
        target_length=target_length,
        length_ratio=length_ratio,
        angular_difference_degrees=angular_difference,
        warnings=warnings,
    )


def _position(transform) -> np.ndarray:
    return np.asarray(transform.position, dtype=np.float64)


def _angle_degrees(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na <= 1e-8 or nb <= 1e-8:
        return 0.0
    dot = float(np.dot(a, b) / (na * nb))
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(math.acos(dot))
