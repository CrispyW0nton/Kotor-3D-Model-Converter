"""Unreal target skeleton and baked animation clip contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.validation.validation_bus import (
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
    ValidationSubsystem,
)

from .source_animation import Transform


UE_AXIS_SYSTEM = "ue_x_forward_y_right_z_up"
UE_UNIT_SCALE_TO_METERS = 0.01


@dataclass(frozen=True)
class UnrealSkeletonNode:
    """One node in a target Unreal-compatible skeleton."""

    name: str
    parent_name: str | None
    index: int
    rest_local: Transform
    rest_global: Transform
    classification: str = "deform"


@dataclass
class UnrealTargetSkeleton:
    """A UE target skeleton contract for KOTOR-to-Unreal retargeting."""

    name: str
    nodes: list[UnrealSkeletonNode]
    axis_system: str = UE_AXIS_SYSTEM
    unit_scale_to_meters: float = UE_UNIT_SCALE_TO_METERS
    source_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def node_names(self) -> list[str]:
        return [node.name for node in self.nodes]

    def node_by_name(self) -> dict[str, UnrealSkeletonNode]:
        return {node.name: node for node in self.nodes}


@dataclass
class UnrealAnimationPose:
    """One baked UE animation pose in local/global target skeleton spaces."""

    time_seconds: float
    local_transforms: dict[str, Transform]
    global_transforms: dict[str, Transform]


@dataclass
class UnrealAnimationClip:
    """Baked UE-compatible animation clip."""

    clip_name: str
    duration_seconds: float
    sample_rate: float
    target_skeleton_name: str
    poses: list[UnrealAnimationPose]
    axis_system: str = UE_AXIS_SYSTEM
    unit_scale_to_meters: float = UE_UNIT_SCALE_TO_METERS
    metadata: dict[str, Any] = field(default_factory=dict)


def audit_unreal_target_skeleton(target: UnrealTargetSkeleton) -> ValidationReport:
    """Validate target skeleton shape without requiring Unreal or FBX runtime."""

    issues: list[ValidationIssue] = []
    if target is None:
        issues.append(_issue("unreal_skeleton.missing", "Target Unreal skeleton is required."))
        return ValidationReport(issues=issues, source="retarget.kotor_to_unreal.skeleton")

    if not str(target.name or "").strip():
        issues.append(_issue("unreal_skeleton.name", "Target Unreal skeleton name is empty."))
    nodes = list(target.nodes or [])
    if not nodes:
        issues.append(_issue("unreal_skeleton.empty", "Target Unreal skeleton has no nodes."))
        return ValidationReport(issues=issues, source="retarget.kotor_to_unreal.skeleton")

    names = [str(node.name or "") for node in nodes]
    lowered = [name.lower() for name in names]
    duplicates = sorted({name for name in lowered if lowered.count(name) > 1})
    for duplicate in duplicates:
        issues.append(_issue("unreal_skeleton.duplicate_node", f"Duplicate Unreal skeleton node name: {duplicate}"))

    name_set = set(names)
    visiting: set[str] = set()
    visited: set[str] = set()
    by_name = {node.name: node for node in nodes}
    for node in nodes:
        if node.parent_name and node.parent_name not in name_set:
            issues.append(
                _issue(
                    "unreal_skeleton.missing_parent",
                    f"Unreal skeleton node '{node.name}' references missing parent '{node.parent_name}'.",
                )
            )
        if not node.rest_local.is_finite() or not node.rest_global.is_finite():
            issues.append(
                _issue(
                    "unreal_skeleton.non_finite_rest",
                    f"Unreal skeleton node '{node.name}' has a non-finite rest transform.",
                )
            )
        _detect_cycle(node.name, by_name, visiting, visited, issues)

    return ValidationReport(issues=issues, source="retarget.kotor_to_unreal.skeleton")


def import_unreal_target_skeleton_from_fbx(path: str | Path, *_args, **_kwargs) -> UnrealTargetSkeleton:
    """Import a target skeleton from FBX.

    The project does not currently ship a real FBX skeleton backend. This
    interface is intentionally present so UI/controllers can fail clearly until
    Autodesk/Blender/project-specific import support is configured.
    """

    raise NotImplementedError(
        "Unreal target skeleton FBX import requires a configured FBX backend. "
        "Configure Autodesk FBX SDK, Blender export bridge, or project-supported backend."
    )


def classify_unreal_node_name(name: str) -> str:
    raw = str(name or "").lower()
    if not raw or raw in {"root", "rootbone"}:
        return "root"
    if "twist" in raw:
        return "twist"
    if raw.startswith("ik_") or raw.startswith("ik"):
        return "ik"
    if "socket" in raw or "helper" in raw or "ctrl" in raw:
        return "helper"
    return "deform"


def _detect_cycle(
    node_name: str,
    by_name: dict[str, UnrealSkeletonNode],
    visiting: set[str],
    visited: set[str],
    issues: list[ValidationIssue],
) -> None:
    if node_name in visited:
        return
    if node_name in visiting:
        issues.append(_issue("unreal_skeleton.parent_cycle", f"Unreal skeleton parent cycle at '{node_name}'."))
        return
    visiting.add(node_name)
    parent = by_name.get(node_name).parent_name if node_name in by_name else None
    if parent and parent in by_name:
        _detect_cycle(parent, by_name, visiting, visited, issues)
    visiting.discard(node_name)
    visited.add(node_name)


def _issue(code: str, message: str, *, severity: ValidationSeverity = ValidationSeverity.BLOCKING) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,
        subsystem=ValidationSubsystem.RETARGET,
        code=code,
        message=message,
    )
