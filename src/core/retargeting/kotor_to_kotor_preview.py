"""KOTOR-to-KOTOR Retarget Workbench preview adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.retargeting.kotor_source_animation import (
    KotorAnimationSourceRequest,
    KotorAnimationSourceResult,
    sample_kotor_animation_slot_as_source_clip,
)
from src.core.retargeting.retarget_modes import RetargetMode
from src.core.retargeting.retarget_output_naming import RetargetOutputNaming
from src.core.retargeting.retarget_preview import (
    RetargetPreviewRequest,
    RetargetPreviewResult,
    build_retarget_preview,
)
from src.core.retargeting.retarget_profile import RetargetProfile
from src.core.retargeting.retarget_solver import RetargetSolverOptions


@dataclass
class KotorToKotorPreviewRequest:
    """Inputs for sampling a KOTOR source slot and previewing it on a KOTOR target."""

    source_model: Any
    source_animation_slot: str
    target_model: Any
    retarget_profile: RetargetProfile
    output_naming: RetargetOutputNaming | None = None
    source_supermodel_chain: Any | None = None
    target_supermodel_chain: Any | None = None
    source_sample_rate: float = 30.0
    solver_options: RetargetSolverOptions | None = None
    auto_play: bool = True
    enable_numeric_audit: bool = True


@dataclass
class KotorToKotorPreviewResult:
    """Source sampling result plus the in-memory target preview."""

    source_sample_result: KotorAnimationSourceResult
    preview_result: RetargetPreviewResult
    warnings: list[str]


def build_kotor_to_kotor_retarget_preview(
    request: KotorToKotorPreviewRequest,
) -> KotorToKotorPreviewResult:
    """Sample a source KOTOR animation slot and build a target KOTOR preview.

    Source animation identity and target output identity are intentionally kept
    separate: ``source_animation_slot`` selects what is sampled, while
    ``output_naming`` selects what is attached to the target preview model.
    """

    source_slot = str(request.source_animation_slot or "").strip()
    sample_result = sample_kotor_animation_slot_as_source_clip(
        KotorAnimationSourceRequest(
            source_model=request.source_model,
            animation_slot=source_slot,
            supermodel_chain=request.source_supermodel_chain,
            sample_rate=float(request.source_sample_rate or 30.0),
        )
    )
    preview_result = build_retarget_preview(
        RetargetPreviewRequest(
            source_clip=sample_result.source_clip,
            target_model=request.target_model,
            profile=request.retarget_profile,
            supermodel_chain=request.target_supermodel_chain,
            solver_options=request.solver_options,
            output_naming=request.output_naming,
            workbench_mode=RetargetMode.KOTOR_TO_KOTOR,
            auto_play=request.auto_play,
            enable_numeric_audit=request.enable_numeric_audit,
        )
    )
    warnings = [
        *list(sample_result.report.warnings or []),
        *list(preview_result.warnings or []),
    ]
    return KotorToKotorPreviewResult(
        source_sample_result=sample_result,
        preview_result=preview_result,
        warnings=warnings,
    )
