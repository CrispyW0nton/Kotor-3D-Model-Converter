"""Transactional Character Builder MDL/MDX export.

The Character Builder export path must keep the selected native KOTOR model as
the authoritative DAG contract.  This module wraps MDL/MDX writing in the
shared :mod:`src.core.export.export_job` staging lifecycle and records the
engine-evidence-backed preflight report beside every successful export.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

from src.core.export.export_job import (
    ExportJobContext,
    ExportJobRequest,
    ExportJobResult,
    ExportJobStatus,
    ExportOutputSpec,
    run_export_job,
)
from src.core.validation.validation_bus import (
    ValidationBus,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
    ValidationSubsystem,
)

from .character_export_preflight import (
    CharacterExportPreflightOptions,
    CharacterExportPreflightResult,
    preflight_character_mdl_export,
)
from .kotor_constants import CHARACTER_EXPORT_EVIDENCE
from .native_skeleton import NativeSkeletonSnapshot
from .character_validation_report import (
    CharacterBuilderValidationReport,
    validation_report_paths,
)


LoaderCallable = Callable[[Path, Path], Any]


@dataclass
class CharacterBuilderExportTransactionRequest:
    """Inputs for a staged Character Builder KOTOR export."""

    model: Any
    output_mdl_path: Path
    game: str = "K1"
    native_snapshot: NativeSkeletonSnapshot | None = None
    overwrite: bool = False
    preflight_options: CharacterExportPreflightOptions | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    validation_bus: ValidationBus | None = None
    writer_cls: Any | None = None
    loader: LoaderCallable | None = None

    def __post_init__(self) -> None:
        self.output_mdl_path = Path(self.output_mdl_path)
        self.game = str(self.game or "K1").upper()
        self.metadata = dict(self.metadata or {})


@dataclass
class CharacterBuilderExportTransactionResult:
    """Result of :func:`export_character_mdl_mdx_transaction`."""

    export_job_result: ExportJobResult
    preflight_result: CharacterExportPreflightResult
    reloaded_model: Any | None = None

    @property
    def succeeded(self) -> bool:
        return self.export_job_result.succeeded

    @property
    def mdl_path(self) -> Path:
        return self.export_job_result.outputs[0].final_path

    @property
    def mdx_path(self) -> Path:
        return self.mdl_path.with_suffix(".mdx")

    @property
    def validation_report_json_path(self) -> Path:
        return _validation_json_path(self.mdl_path)

    @property
    def validation_report_txt_path(self) -> Path:
        return _validation_text_path(self.mdl_path)


def export_character_mdl_mdx_transaction(
    request: CharacterBuilderExportTransactionRequest,
) -> CharacterBuilderExportTransactionResult:
    """Write a Character Builder model as a staged, verified MDL/MDX pair."""

    mdl_path = Path(request.output_mdl_path)
    mdx_path = mdl_path.with_suffix(".mdx")
    json_path = _validation_json_path(mdl_path)
    txt_path = _validation_text_path(mdl_path)
    preflight_options = _preflight_options_for_request(request)

    preflight = preflight_character_mdl_export(
        request.model,
        native_snapshot=request.native_snapshot,
        options=preflight_options,
    )
    native_snapshot = preflight.native_snapshot

    metadata = {
        "mode": "character_builder",
        "game": request.game,
        "resref": _model_resref(request.model, mdl_path),
        "engine_evidence": CHARACTER_EXPORT_EVIDENCE,
        "character_builder_workflow": _character_builder_workflow_evidence(
            request.model,
            native_snapshot,
        ),
        **dict(request.metadata or {}),
    }
    job_request = ExportJobRequest(
        job_id=f"character_{metadata['resref']}",
        kind="character_mdl_mdx",
        outputs=[
            ExportOutputSpec(final_path=mdl_path, artifact_kind="mdl"),
            ExportOutputSpec(final_path=mdx_path, artifact_kind="mdx"),
            ExportOutputSpec(final_path=json_path, artifact_kind="validation_json"),
            ExportOutputSpec(final_path=txt_path, artifact_kind="validation_text"),
        ],
        overwrite=request.overwrite,
        metadata=metadata,
        preflight_report=preflight.report,
        validation_bus_source="character.export_transaction",
    )

    reloaded: dict[str, Any] = {}

    def _writer(context: ExportJobContext) -> None:
        writer_cls = request.writer_cls or _import_mdl_binary_writer()
        staged_mdl = context.staged_path_for(mdl_path)
        writer_cls().write_files(request.model, str(staged_mdl))
        _write_validation_artifacts(
            context,
            mdl_path=mdl_path,
            preflight=preflight.report,
            reload_report=None,
            status="written_not_verified",
            verified=False,
        )

    def _verifier(context: ExportJobContext) -> ValidationReport:
        loader = request.loader or _load_kotor_model_from_file
        staged_mdl = context.staged_path_for(mdl_path)
        staged_mdx = context.staged_path_for(mdx_path)
        issues: list[ValidationIssue] = []
        try:
            loaded = loader(staged_mdl, staged_mdx)
            reloaded["model"] = loaded
        except Exception as exc:
            report = ValidationReport(
                source="character.export_transaction.verify",
                issues=[
                    _export_issue(
                        "character.export.reload_failed",
                        f"Exported MDL/MDX failed reload verification: {exc}",
                        details={"exception_type": type(exc).__name__},
                    )
                ],
            )
            _write_validation_artifacts(
                context,
                mdl_path=mdl_path,
                preflight=preflight.report,
                reload_report=report,
                status="reload_failed",
                verified=False,
            )
            return report

        reload_preflight = preflight_character_mdl_export(
            loaded,
            native_snapshot=native_snapshot,
            options=preflight_options,
        )
        issues.extend(reload_preflight.report.issues)
        if not reload_preflight.report.has_blocking:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    subsystem=ValidationSubsystem.CHARACTER,
                    code="character.export.reload_verified",
                    message="Exported MDL/MDX reloaded and passed Character Builder preflight.",
                    details={"engine_evidence": CHARACTER_EXPORT_EVIDENCE},
                    source="character.export_transaction.verify",
                )
            )
        report = ValidationReport(
            source="character.export_transaction.verify",
            issues=issues,
        )
        _write_validation_artifacts(
            context,
            mdl_path=mdl_path,
            preflight=preflight.report,
            reload_report=report,
            status="verified" if not report.has_blocking else "reload_preflight_failed",
            verified=not report.has_blocking,
        )
        return report

    export_job = run_export_job(
        job_request,
        writer=_writer,
        verifier=_verifier,
        validation_bus=request.validation_bus,
    )
    return CharacterBuilderExportTransactionResult(
        export_job_result=export_job,
        preflight_result=preflight,
        reloaded_model=reloaded.get("model"),
    )


def _preflight_options_for_request(
    request: CharacterBuilderExportTransactionRequest,
) -> CharacterExportPreflightOptions:
    if request.preflight_options is None:
        return CharacterExportPreflightOptions(export_game=request.game)
    return replace(request.preflight_options, export_game=request.game)


def _write_validation_artifacts(
    context: ExportJobContext,
    *,
    mdl_path: Path,
    preflight: ValidationReport,
    reload_report: ValidationReport | None,
    status: str,
    verified: bool,
) -> None:
    report = CharacterBuilderValidationReport(
        status=status,
        verified=verified,
        job_id=context.request.job_id,
        export_kind=context.request.kind,
        game=str(context.request.metadata.get("game") or ""),
        resref=str(context.request.metadata.get("resref") or ""),
        outputs={
            "mdl": str(mdl_path),
            "mdx": str(mdl_path.with_suffix(".mdx")),
            "validation_json": str(_validation_json_path(mdl_path)),
            "validation_text": str(_validation_text_path(mdl_path)),
        },
        preflight_report=preflight,
        reload_report=reload_report,
        metadata=dict(context.request.metadata),
    )
    context.write_text(
        _validation_json_path(mdl_path),
        report.to_json(),
    )
    context.write_text(
        _validation_text_path(mdl_path),
        report.to_text(),
    )


def _validation_json_path(mdl_path: Path) -> Path:
    return validation_report_paths(mdl_path)[0]


def _validation_text_path(mdl_path: Path) -> Path:
    return validation_report_paths(mdl_path)[1]


def _model_resref(model: Any, mdl_path: Path) -> str:
    return str(getattr(model, "name", "") or mdl_path.stem or "untitled").lower()


def _character_builder_workflow_evidence(
    model: Any,
    native_snapshot: NativeSkeletonSnapshot | None,
) -> dict[str, Any]:
    metadata = getattr(model, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
    rig_state = getattr(model, "_gr_character_builder_rig_state", None)
    if hasattr(rig_state, "to_dict"):
        rig_state = rig_state.to_dict()
    elif not isinstance(rig_state, dict):
        rig_state = metadata.get("character_builder_rig_state")

    normalization = metadata.get("kotor_normalization")
    if isinstance(normalization, dict):
        normalization_summary = {
            key: normalization.get(key)
            for key in (
                "fit_policy",
                "scale",
                "scale_basis",
                "source_height",
                "target_height",
                "reference",
                "vertical_axis",
                "target_center_xy",
                "target_ground_z",
                "external_world_positions_fit",
                "fit_transform",
            )
            if key in normalization
        }
    else:
        normalization_summary = None

    snapshot_summary = None
    if native_snapshot is not None:
        snapshot_summary = {
            "model_name": native_snapshot.model_name,
            "game": native_snapshot.game,
            "supermodel": native_snapshot.supermodel,
            "node_count": native_snapshot.node_count,
            "mesh_node_count": native_snapshot.mesh_node_count,
            "skin_node_count": native_snapshot.skin_node_count,
            "hook_names": list(native_snapshot.hook_names),
            "metadata": dict(native_snapshot.metadata or {}),
        }

    return _json_safe({
        "native_skeleton_is_authority": True,
        "imported_mesh_role": "payload_guest",
        "final_dag_source": "selected_kotor_base",
        "rig_state": rig_state,
        "fit_report": metadata.get("kotor_fit_report"),
        "normalization": normalization_summary,
        "native_snapshot": snapshot_summary,
    })


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "to_dict"):
        return _json_safe(value.to_dict())
    return str(value)


def _export_issue(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> ValidationIssue:
    payload = dict(details or {})
    payload.setdefault("engine_evidence", CHARACTER_EXPORT_EVIDENCE)
    return ValidationIssue(
        severity=ValidationSeverity.BLOCKING,
        subsystem=ValidationSubsystem.CHARACTER,
        code=code,
        message=message,
        details=payload,
        source="character.export_transaction.verify",
    )


def _import_mdl_binary_writer() -> Any:  # pragma: no cover - import shim
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    return MDLBinaryWriter


def _load_kotor_model_from_file(mdl_path: Path, mdx_path: Path) -> Any:
    from src.core.game.kotor_loader import load_model_from_file

    return load_model_from_file(str(mdl_path), str(mdx_path))
