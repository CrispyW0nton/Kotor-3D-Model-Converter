"""KOTOR-to-Unreal Retarget Workbench preview adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.validation.validation_bus import (
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
    ValidationSubsystem,
    merge_validation_reports,
)

from .coordinate import BasisConversion
from .kotor_source_animation import (
    KotorAnimationSourceRequest,
    KotorAnimationSourceResult,
    sample_kotor_animation_slot_as_source_clip,
)
from .kotor_to_unreal_solver import (
    audit_unreal_animation_clip,
    retarget_kotor_source_clip_to_unreal_animation,
    validate_retarget_profile_for_unreal_target,
)
from .retarget_output_naming import RetargetOutputNaming, validate_unreal_clip_name
from .retarget_profile import RetargetProfile
from .unreal_target_skeleton import UnrealAnimationClip, UnrealTargetSkeleton


@dataclass
class KotorToUnrealPreviewRequest:
    source_model: Any
    source_animation_slot: str
    target_skeleton: UnrealTargetSkeleton
    retarget_profile: RetargetProfile
    output_naming: RetargetOutputNaming
    source_supermodel_chain: Any | None = None
    source_sample_rate: float = 30.0
    basis_conversion: BasisConversion | None = None
    root_motion_policy: str = "in_place"
    strict: bool = True


@dataclass
class KotorToUnrealPreviewResult:
    source_sample_result: KotorAnimationSourceResult
    target_skeleton: UnrealTargetSkeleton
    animation_clip: UnrealAnimationClip
    validation_report: ValidationReport
    warnings: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


def build_kotor_to_unreal_preview(request: KotorToUnrealPreviewRequest) -> KotorToUnrealPreviewResult:
    """Sample a KOTOR source animation and build a baked UE animation clip."""

    clip_name = validate_unreal_clip_name(getattr(request.output_naming, "unreal_clip_name", None))
    sample_result = sample_kotor_animation_slot_as_source_clip(
        KotorAnimationSourceRequest(
            source_model=request.source_model,
            animation_slot=str(request.source_animation_slot or "").strip(),
            supermodel_chain=request.source_supermodel_chain,
            sample_rate=float(request.source_sample_rate or 30.0),
        )
    )
    profile_report = validate_retarget_profile_for_unreal_target(
        request.retarget_profile,
        sample_result.source_clip,
        request.target_skeleton,
        strict=bool(request.strict),
    )
    if profile_report.has_blocking:
        raise ValueError("; ".join(issue.message for issue in profile_report.blocking_issues))
    warnings = [*list(sample_result.report.warnings or [])]
    if sample_result.source_clip.axis_system == "kotor_aurora" and request.basis_conversion is None:
        warnings.append("No explicit KOTOR→UE basis conversion supplied; using identity conversion for this preview.")
    warnings.extend(issue.message for issue in profile_report.issues if issue.severity == ValidationSeverity.WARNING)
    animation_clip = retarget_kotor_source_clip_to_unreal_animation(
        source_clip=sample_result.source_clip,
        target_skeleton=request.target_skeleton,
        profile=request.retarget_profile,
        output_clip_name=clip_name,
        basis_conversion=request.basis_conversion,
        sample_rate=request.source_sample_rate,
        root_motion_policy=request.root_motion_policy,
        strict=request.strict,
    )
    clip_report = audit_unreal_animation_clip(
        animation_clip,
        request.target_skeleton,
        root_motion_policy=request.root_motion_policy,
    )
    root_policy_message = (
        "Root horizontal translation is stripped by default for KOTOR → Unreal in-place preview."
        if request.root_motion_policy == "in_place"
        else "Root movement is enabled for this KOTOR → Unreal preview."
    )
    root_policy_report = ValidationReport(
        issues=[
            ValidationIssue(
                severity=ValidationSeverity.INFO,
                subsystem=ValidationSubsystem.RETARGET,
                code="kotor_to_unreal.root_motion_policy",
                message=root_policy_message,
            )
        ],
        source="retarget.kotor_to_unreal.preview",
    )
    report = merge_validation_reports(profile_report, clip_report, root_policy_report)
    if report.has_blocking:
        raise ValueError("; ".join(issue.message for issue in report.blocking_issues))
    return KotorToUnrealPreviewResult(
        source_sample_result=sample_result,
        target_skeleton=request.target_skeleton,
        animation_clip=animation_clip,
        validation_report=report,
        warnings=warnings,
        metadata={
            "mode": "kotor_to_unreal",
            "source_kotor_animation": sample_result.report.resolved_slot_name,
            "output_unreal_clip_name": animation_clip.clip_name,
            "target_skeleton": request.target_skeleton.name,
            "sample_rate": animation_clip.sample_rate,
            "root_motion_policy": request.root_motion_policy,
            "basis_conversion": "custom" if request.basis_conversion is not None else "identity",
        },
    )
