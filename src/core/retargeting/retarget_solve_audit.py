"""Audit/result dataclasses for basic UE-source to Aurora retarget solving."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RetargetSolveReport:
    """Summary of one generated Aurora animation solve."""

    generated_slot_name: str
    duration_seconds: float
    sample_count: int
    mapped_node_count: int
    generated_orientation_track_count: int
    generated_position_track_count: int
    stripped_root_translation: bool = False
    max_quaternion_norm_error: float = 0.0
    max_adjacent_rotation_degrees: float = 0.0
    warnings: list[str] = field(default_factory=list)


class RetargetSolveError(ValueError):
    """Raised when the basic retarget solver cannot produce a safe animation."""
