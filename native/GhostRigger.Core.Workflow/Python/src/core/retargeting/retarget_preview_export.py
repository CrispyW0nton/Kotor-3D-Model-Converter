"""Export a verified in-memory retarget preview to MDL/MDX."""

from __future__ import annotations

from dataclasses import dataclass, field
import copy
from pathlib import Path
from typing import Any, List

from src.core.export.export_job import (
    ExportJobContext,
    ExportJobRequest,
    ExportJobResult,
    ExportOutputSpec,
    run_export_job,
)
from src.core.retargeting.aurora_animation_writer import (
    AuroraAnimationInjectionRequest,
    AuroraAnimationWriter,
)
from src.core.retargeting.retarget_preview import RetargetPreviewResult
from src.core.retargeting.retarget_output_naming import (
    KotorOutputAnimationNameMode,
    validate_custom_kotor_animation_name,
)
from src.core.validation.validation_bus import (
    ValidationBus,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
    ValidationSubsystem,
)


class RetargetPreviewExportError(RuntimeError):
    """Raised when a retarget preview cannot be exported safely."""


@dataclass
class RetargetPreviewExportRequest:
    """Inputs for exporting the last approved retarget preview."""

    preview_result: RetargetPreviewResult
    original_target_model: Any
    output_mdl_path: Path
    output_mdx_path: Path
    overwrite: bool = False
    replace_existing: bool = True
    verify_roundtrip: bool = True
    write_manifest: bool = True
    roundtrip_tolerance: float = 1e-4
    kotor_output_name_mode: KotorOutputAnimationNameMode = KotorOutputAnimationNameMode.VANILLA_SLOT
    requires_custom_animation_patch: bool = False
    target_mdl_bytes: bytes | None = None
    target_mdx_bytes: bytes | None = None
    resource_manager: Any | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.output_mdl_path = Path(self.output_mdl_path)
        self.output_mdx_path = Path(self.output_mdx_path)


@dataclass
class RetargetPreviewExportResult:
    """Result of writing a retarget preview MDL/MDX candidate."""

    mdl_path: Path
    mdx_path: Path
    manifest_path: Path | None
    slot_name: str
    verified_roundtrip: bool
    warnings: List[str] = field(default_factory=list)
    export_job_result: ExportJobResult | None = None


def export_retarget_preview_override(
    request: RetargetPreviewExportRequest,
    *,
    writer: AuroraAnimationWriter | None = None,
    validation_bus: ValidationBus | None = None,
) -> RetargetPreviewExportResult:
    """Export the exact animation block from a successful preview result."""

    preview = request.preview_result
    _validate_preview_for_export(preview)
    if request.output_mdx_path != request.output_mdl_path.with_suffix(".mdx"):
        raise RetargetPreviewExportError(
            "Output MDX path must match the MDL basename "
            f"({request.output_mdl_path.with_suffix('.mdx')})."
        )
    _validate_target_source_available(request)
    warnings = _basename_warnings(request.original_target_model, request.output_mdl_path)
    output_mode = _request_output_mode(request, preview)
    requires_custom_patch = _request_requires_custom_patch(request, preview)
    if output_mode == KotorOutputAnimationNameMode.CUSTOM_PATCH:
        validate_custom_kotor_animation_name(preview.slot_name)
        if not any("custom animation name" in warning for warning in warnings):
            warnings.append(
                "This MDL contains a custom animation name and is not vanilla-slot playable. "
                "Install/use it through the custom animation patch workflow."
            )
    manifest_path = request.output_mdl_path.with_suffix(".retarget_preview.json")
    outputs = [
        ExportOutputSpec(final_path=request.output_mdl_path, artifact_kind="mdl"),
        ExportOutputSpec(final_path=request.output_mdx_path, artifact_kind="mdx"),
    ]
    if request.write_manifest:
        outputs.append(ExportOutputSpec(final_path=manifest_path, artifact_kind="manifest"))

    export_writer = writer or AuroraAnimationWriter()
    injection_holder: dict[str, Any] = {}

    def _writer(context: ExportJobContext) -> None:
        target_mdl, target_mdx = _resolve_target_source_paths(request, context.staging_dir)
        tmp_json = _write_staged_preview_payload(context.staging_dir)
        staged_mdl = context.staged_path_for(request.output_mdl_path)
        staged_manifest = (
            context.staged_path_for(manifest_path)
            if request.write_manifest
            else context.staging_dir / manifest_path.name
        )
        try:
            injection_request = AuroraAnimationInjectionRequest(
                r3a_animation_json=tmp_json,
                target_mdl=target_mdl,
                target_mdx=target_mdx,
                animation_slot=preview.slot_name,
                output_mdl=staged_mdl,
                output_manifest=staged_manifest,
                game=_game_tag(request.original_target_model),
                overwrite_existing=request.replace_existing,
                verify_roundtrip=request.verify_roundtrip,
                roundtrip_tolerance=request.roundtrip_tolerance,
                target_model_override=copy.deepcopy(request.original_target_model),
                resource_manager=request.resource_manager,
                kotor_output_name_mode=output_mode,
                requires_custom_animation_patch=requires_custom_patch,
            )
            injection_result = export_writer.inject_animation_block(
                injection_request,
                copy.deepcopy(preview.animation_block),
            )
            injection_holder["result"] = injection_result
            if not injection_result.success:
                message = "; ".join(injection_result.errors or ["unknown export failure"])
                raise RetargetPreviewExportError(message)
        finally:
            try:
                tmp_json.unlink()
            except OSError:
                pass

    def _verifier(context: ExportJobContext) -> ValidationReport:
        issues: list[ValidationIssue] = []
        injection_result = injection_holder.get("result")
        if injection_result is None or not getattr(injection_result, "success", False):
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.BLOCKING,
                    subsystem=ValidationSubsystem.EXPORT,
                    code="export.verification.failed",
                    message="Retarget preview export did not complete MDL/MDX writer verification.",
                )
            )
        return ValidationReport(issues=issues, source="retarget.preview_export")

    export_job_request = ExportJobRequest(
        job_id=f"retarget_{preview.slot_name}",
        kind="retarget_mdl_mdx",
        outputs=outputs,
        overwrite=request.overwrite,
        metadata={
            "slot_name": preview.slot_name,
            "verify_roundtrip": request.verify_roundtrip,
            "write_manifest": request.write_manifest,
            "kotor_output_name_mode": output_mode.value,
            "animation_name": preview.slot_name,
            "requires_custom_animation_patch": requires_custom_patch,
            "vanilla_slot_safe": not requires_custom_patch,
        },
        validation_bus_source="retarget.preview_export",
    )
    export_job_result = run_export_job(
        export_job_request,
        writer=_writer,
        verifier=_verifier,
        validation_bus=validation_bus,
    )
    if not export_job_result.succeeded:
        messages = [issue.message for issue in export_job_result.validation_report.issues]
        message = "; ".join(messages or ["unknown export failure"])
        raise RetargetPreviewExportError(f"Export failed: {message}")

    injection_result = injection_holder["result"]
    manifest_path_out: Path | None = manifest_path if request.write_manifest and manifest_path.exists() else None

    return RetargetPreviewExportResult(
        mdl_path=request.output_mdl_path,
        mdx_path=request.output_mdx_path,
        manifest_path=manifest_path_out,
        slot_name=injection_result.animation_slot or preview.slot_name,
        verified_roundtrip=bool(request.verify_roundtrip),
        warnings=[*warnings, *list(injection_result.warnings or [])],
        export_job_result=export_job_result,
    )


def _validate_preview_for_export(preview: RetargetPreviewResult | None) -> None:
    if preview is None:
        raise RetargetPreviewExportError(
            "No successful retarget preview is available to export. "
            "Preview the animation in GhostRigger before exporting MDL/MDX."
        )
    audit = getattr(preview, "preview_audit", None)
    if audit is None or not bool(getattr(audit, "passed", False)):
        raise RetargetPreviewExportError(
            "Retarget preview audit did not pass. Run Preview Retarget again "
            "before exporting MDL/MDX."
        )
    if getattr(preview, "animation_block", None) is None:
        raise RetargetPreviewExportError("Retarget preview has no animation block to export.")
    if not str(getattr(preview, "slot_name", "") or "").strip():
        raise RetargetPreviewExportError("Retarget preview has no KOTOR animation slot name.")


def _validate_target_source_available(request: RetargetPreviewExportRequest) -> None:
    if _has_target_mdl_file(request.original_target_model) or _target_source_mdl_bytes(request) is not None:
        return
    raise RetargetPreviewExportError(
        "Original target model has no source MDL path or cached game-library MDL bytes. "
        "Load the target from the Game Library or from an MDL file before exporting."
    )


def _resolve_target_source_paths(
    request: RetargetPreviewExportRequest,
    staging_dir: Path,
) -> tuple[Path, Path | None]:
    target_mdl = _target_mdl_path(request.original_target_model, required=False)
    if target_mdl is not None:
        return target_mdl, _target_mdx_path(request.original_target_model, target_mdl)

    mdl_bytes = _target_source_mdl_bytes(request)
    if mdl_bytes is None:
        raise RetargetPreviewExportError(
            "Original target model has no source MDL path or cached game-library MDL bytes. "
            "Load the target from the Game Library or from an MDL file before exporting."
        )
    source_dir = staging_dir / "_original_target"
    source_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_target_source_stem(request.original_target_model)
    target_mdl = source_dir / f"{stem}.mdl"
    target_mdl.write_bytes(mdl_bytes)

    mdx_bytes = _target_source_mdx_bytes(request)
    target_mdx = None
    if mdx_bytes:
        target_mdx = source_dir / f"{stem}.mdx"
        target_mdx.write_bytes(mdx_bytes)
    return target_mdl, target_mdx


def _has_target_mdl_file(model: Any) -> bool:
    return _target_mdl_path(model, required=False) is not None


def _target_mdl_path(model: Any, *, required: bool = True) -> Path | None:
    raw = str(getattr(model, "mdl_path", "") or "").strip()
    if not raw:
        if not required:
            return None
        raise RetargetPreviewExportError(
            "Original target model has no source MDL path. Load the target from an MDL file before exporting."
        )
    path = Path(raw)
    if not path.exists():
        if not required:
            return None
        raise RetargetPreviewExportError(f"Original target MDL path is not available: {raw}")
    return path


def _target_mdx_path(model: Any, target_mdl: Path) -> Path | None:
    raw = str(getattr(model, "mdx_path", "") or "").strip()
    if raw and Path(raw).exists():
        return Path(raw)
    guessed = target_mdl.with_suffix(".mdx")
    return guessed if guessed.exists() else None


def _target_source_mdl_bytes(request: RetargetPreviewExportRequest) -> bytes | None:
    return _coerce_optional_bytes(request.target_mdl_bytes) or _model_source_bytes(
        request.original_target_model,
        (
            "_gr_source_mdl_bytes",
            "_gr_original_mdl_bytes",
            "source_mdl_bytes",
            "_source_mdl_bytes",
        ),
    )


def _target_source_mdx_bytes(request: RetargetPreviewExportRequest) -> bytes | None:
    return _coerce_optional_bytes(request.target_mdx_bytes) or _model_source_bytes(
        request.original_target_model,
        (
            "_gr_source_mdx_bytes",
            "_gr_original_mdx_bytes",
            "source_mdx_bytes",
            "_source_mdx_bytes",
        ),
    )


def _model_source_bytes(model: Any, attribute_names: tuple[str, ...]) -> bytes | None:
    for name in attribute_names:
        value = _coerce_optional_bytes(getattr(model, name, None))
        if value is not None:
            return value
    return None


def _coerce_optional_bytes(value: Any) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    return None


def _safe_target_source_stem(model: Any) -> str:
    raw = str(
        getattr(model, "_gr_source_resref", "")
        or getattr(model, "resref", "")
        or getattr(model, "name", "")
        or "target_model"
    ).strip()
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in raw).strip("._")
    return cleaned or "target_model"


def _game_tag(model: Any) -> str:
    raw = getattr(getattr(model, "game_version", None), "name", getattr(model, "game_version", "K1"))
    text = str(raw or "K1").upper()
    return "K2" if text == "K2" else "K1"


def _basename_warnings(model: Any, output_mdl: Path) -> list[str]:
    target_name = str(getattr(model, "name", "") or "").strip()
    if target_name and output_mdl.stem.lower() != target_name.lower():
        return [
            "Override install usually requires the MDL/MDX filename to match "
            f"the target model resref ('{target_name}')."
        ]
    return []


def _request_output_mode(
    request: RetargetPreviewExportRequest,
    preview: RetargetPreviewResult,
) -> KotorOutputAnimationNameMode:
    mode = getattr(preview, "output_name_mode", None) or request.kotor_output_name_mode
    return KotorOutputAnimationNameMode(mode)


def _request_requires_custom_patch(
    request: RetargetPreviewExportRequest,
    preview: RetargetPreviewResult,
) -> bool:
    return bool(
        request.requires_custom_animation_patch
        or getattr(preview, "requires_custom_animation_patch", False)
        or _request_output_mode(request, preview) == KotorOutputAnimationNameMode.CUSTOM_PATCH
    )


def _write_staged_preview_payload(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ".retarget_preview_export_payload.json"
    path.write_text('{"frame_count": 0, "target_curves": {}}\n', encoding="utf-8")
    return path
