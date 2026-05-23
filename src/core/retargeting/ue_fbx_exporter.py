"""FBX export backend contract for KOTOR-to-Unreal animation clips."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from src.core.export.export_job import (
    ExportJobContext,
    ExportJobRequest,
    ExportJobResult,
    ExportOutputSpec,
    run_export_job,
)
from src.core.validation.validation_bus import (
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
    ValidationSubsystem,
)

from .kotor_to_unreal_preview import KotorToUnrealPreviewResult


class UnrealFbxExportUnavailableError(RuntimeError):
    """Raised when KOTOR-to-Unreal export has no configured FBX backend."""


class UnrealFbxAnimationExportBackend(Protocol):
    def is_available(self) -> bool:
        ...

    def export_animation_clip(
        self,
        *,
        target_skeleton,
        animation_clip,
        output_fbx_path: Path,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ...


@dataclass
class KotorToUnrealExportRequest:
    preview_result: KotorToUnrealPreviewResult
    output_fbx_path: Path
    output_manifest_path: Path | None = None
    overwrite: bool = False
    verify_export: bool = True
    exporter_backend: UnrealFbxAnimationExportBackend | None = None


def export_kotor_to_unreal_preview(request: KotorToUnrealExportRequest) -> ExportJobResult:
    """Export the exact baked UE clip from a KOTOR-to-Unreal preview."""

    backend = request.exporter_backend
    fbx_path = Path(request.output_fbx_path).with_suffix(".fbx")
    manifest_path = Path(request.output_manifest_path) if request.output_manifest_path else fbx_path.with_suffix(".ghostrigger.json")
    preflight = _backend_preflight(backend)
    metadata = _manifest_payload(request.preview_result)
    export_request = ExportJobRequest(
        job_id=f"kotor_to_unreal_{request.preview_result.animation_clip.clip_name}",
        kind="kotor_to_unreal_fbx",
        outputs=[
            ExportOutputSpec(final_path=fbx_path, artifact_kind="fbx"),
            ExportOutputSpec(final_path=manifest_path, artifact_kind="manifest"),
        ],
        overwrite=bool(request.overwrite),
        metadata=metadata,
        preflight_report=preflight,
        validation_bus_source="retarget.kotor_to_unreal.export",
    )

    def writer(context: ExportJobContext) -> None:
        if backend is None or not backend.is_available():
            raise UnrealFbxExportUnavailableError(_backend_message())
        backend.export_animation_clip(
            target_skeleton=request.preview_result.target_skeleton,
            animation_clip=request.preview_result.animation_clip,
            output_fbx_path=context.staged_path_for(fbx_path),
            metadata=metadata,
        )

    def verifier(context: ExportJobContext) -> ValidationReport:
        issues: list[ValidationIssue] = []
        staged = context.staged_path_for(fbx_path)
        if request.verify_export and (not staged.exists() or staged.stat().st_size <= 0):
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.BLOCKING,
                    subsystem=ValidationSubsystem.EXPORT,
                    code="kotor_to_unreal.export.verify",
                    message="KOTOR → Unreal FBX export verification failed: exported FBX file is missing or empty.",
                )
            )
        return ValidationReport(issues=issues, source="retarget.kotor_to_unreal.export")

    def manifest_writer(context: ExportJobContext, _result: ExportJobResult) -> Path:
        staged_manifest = context.staged_path_for(manifest_path)
        staged_manifest.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return staged_manifest

    return run_export_job(
        export_request,
        writer=writer,
        verifier=verifier,
        manifest_writer=manifest_writer,
    )


def _backend_preflight(backend: UnrealFbxAnimationExportBackend | None) -> ValidationReport:
    if backend is not None and backend.is_available():
        return ValidationReport(source="retarget.kotor_to_unreal.export")
    return ValidationReport(
        issues=[
            ValidationIssue(
                severity=ValidationSeverity.BLOCKING,
                subsystem=ValidationSubsystem.EXPORT,
                code="kotor_to_unreal.fbx_backend_missing",
                message=_backend_message(),
            )
        ],
        source="retarget.kotor_to_unreal.export",
    )


def _backend_message() -> str:
    return (
        "KOTOR → Unreal export requires an FBX export backend. "
        "Configure Autodesk FBX SDK, Blender export bridge, or project-supported backend."
    )


def _manifest_payload(preview: KotorToUnrealPreviewResult) -> dict[str, Any]:
    return {
        "mode": "kotor_to_unreal",
        "source_kotor_animation": preview.source_sample_result.report.resolved_slot_name,
        "output_unreal_clip_name": preview.animation_clip.clip_name,
        "target_skeleton": preview.target_skeleton.name,
        "sample_rate": preview.animation_clip.sample_rate,
        "root_motion_policy": preview.animation_clip.metadata.get("root_motion_policy", "in_place"),
        "basis_conversion": preview.animation_clip.metadata.get("basis_conversion", "identity"),
        "verified": True,
    }
