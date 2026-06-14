"""Validation and reporting helpers for imported source skeleton clips."""

from __future__ import annotations

from dataclasses import dataclass, field
import csv
import math
from pathlib import Path
from typing import List

import numpy as np

from .source_animation import SourceSkeletonClip, Transform


@dataclass
class SourceAnimationAudit:
    """Audit result for one imported source skeleton clip."""

    success: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.success = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


def audit_source_skeleton_clip(clip: SourceSkeletonClip) -> SourceAnimationAudit:
    """Return deterministic sanity checks for a source skeleton clip."""

    report = SourceAnimationAudit()
    if not clip.nodes:
        report.add_error("source skeleton has no nodes")
        return report

    names = [node.name for node in clip.nodes]
    lowered = [name.lower() for name in names]
    if len(lowered) != len(set(lowered)):
        duplicates = sorted({name for name in lowered if lowered.count(name) > 1})
        report.add_error(f"source skeleton has duplicate node names: {', '.join(duplicates)}")

    name_set = set(names)
    roots = [node for node in clip.nodes if not node.parent_name]
    if not roots:
        report.add_error("source skeleton has no root node")
    elif len(roots) > 1:
        report.add_warning(f"source skeleton has multiple roots: {', '.join(node.name for node in roots)}")

    for node in clip.nodes:
        if node.parent_name and node.parent_name not in name_set:
            report.add_error(f"source node '{node.name}' references missing parent '{node.parent_name}'")
        _check_transform(report, node.rest_global, f"rest global transform for '{node.name}'")
        _check_transform(report, node.rest_local, f"rest local transform for '{node.name}'")

    _check_acyclic(report, clip)

    sample_times = [pose.time_seconds for pose in clip.sampled_poses]
    if sample_times != sorted(sample_times):
        report.add_error("sample times are not sorted")
    if len(sample_times) != len(set(sample_times)):
        report.add_error("sample times contain duplicates")
    if clip.duration_seconds < 0:
        report.add_error("clip duration is negative")

    for pose in clip.sampled_poses:
        for node_name, transform in pose.global_transforms.items():
            _check_transform(report, transform, f"sample global transform for '{node_name}' at {pose.time_seconds:g}")
        for node_name, transform in pose.local_transforms.items():
            _check_transform(report, transform, f"sample local transform for '{node_name}' at {pose.time_seconds:g}")

    helper_count = sum(
        1
        for node in clip.nodes
        if node.classification in {"twist", "ik", "helper"}
    )
    if helper_count >= max(3, len(clip.nodes) // 4):
        report.add_warning(f"source skeleton contains {helper_count} twist/IK/helper nodes")

    return report


def write_source_skeleton_audit_csv(clip: SourceSkeletonClip, path: Path) -> None:
    """Write a compact source hierarchy audit CSV."""

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "index",
                "name",
                "parent",
                "classification",
                "rest_global_pos_x",
                "rest_global_pos_y",
                "rest_global_pos_z",
            ]
        )
        for node in clip.nodes:
            x, y, z = node.rest_global.position
            writer.writerow(
                [
                    node.index,
                    node.name,
                    node.parent_name or "",
                    node.classification,
                    x,
                    y,
                    z,
                ]
            )


def _check_transform(report: SourceAnimationAudit, transform: Transform, label: str) -> None:
    if not transform.is_finite():
        report.add_error(f"{label} contains non-finite values")
        return
    qx, qy, qz, qw = transform.rotation
    norm = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    if norm <= 1e-8:
        report.add_error(f"{label} has a zero-length quaternion")
    elif abs(norm - 1.0) > 1e-4:
        report.add_warning(f"{label} quaternion is not unit length before normalization")

    matrix = transform.to_matrix()
    basis = matrix[:3, :3]
    det = float(np.linalg.det(basis))
    if abs(det) <= 1e-8:
        report.add_warning(f"{label} has degenerate or near-zero scale")
    shear = basis.T @ basis
    off_diag = shear - np.diag(np.diag(shear))
    if float(np.max(np.abs(off_diag))) > 1e-4:
        report.add_warning(f"{label} may contain shear or non-orthogonal basis")


def _check_acyclic(report: SourceAnimationAudit, clip: SourceSkeletonClip) -> None:
    parent_by_name = {node.name: node.parent_name for node in clip.nodes}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            report.add_error(f"source skeleton hierarchy cycle detected at '{name}'")
            return
        visiting.add(name)
        parent = parent_by_name.get(name)
        if parent:
            visit(parent)
        visiting.remove(name)
        visited.add(name)

    for node in clip.nodes:
        visit(node.name)
