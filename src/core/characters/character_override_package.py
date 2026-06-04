"""Character Builder Override-style package readiness.

This module prepares a verified Character Builder MDL/MDX export candidate for
modder installation without writing into a live KOTOR install.  It keeps the
game-facing package step headless and staged through ExportJob: the source
MDL/MDX pair is copied into a package directory under the requested replacement
resref, with a manifest that preserves Character Builder validation evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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

from .character_validation_report import (
    CHARACTER_BUILDER_MANUAL_CHECKLIST,
    character_game_test_evidence_passed,
)
from .kotor_constants import CHARACTER_EXPORT_EVIDENCE, KOTOR_NATIVE_RESREF_MAX_LEN


_RESREF_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
_PACKAGE_SCHEMA = "ghostrigger.character_override_package.v1"
_VALIDATION_SCHEMA = "ghostrigger.character_export_validation.v1"


@dataclass
class CharacterBuilderOverridePackageRequest:
    """Inputs for a staged Character Builder install-readiness package."""

    source_mdl_path: Path
    output_dir: Path
    target_resref: str
    game: str = "K1"
    validation_report_path: Path | None = None
    overwrite: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.source_mdl_path = Path(self.source_mdl_path)
        self.output_dir = Path(self.output_dir)
        self.target_resref = str(self.target_resref or "").strip()
        self.game = str(self.game or "K1").upper()
        if self.validation_report_path is not None:
            self.validation_report_path = Path(self.validation_report_path)
        self.metadata = dict(self.metadata or {})


@dataclass
class CharacterBuilderOverridePackageResult:
    """Result of :func:`package_character_override_candidate`."""

    export_job_result: ExportJobResult
    manifest: dict[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.export_job_result.succeeded

    @property
    def mdl_path(self) -> Path:
        return _target_mdl_path(
            self.export_job_result.outputs[0].final_path.parent,
            self.export_job_result.metadata.get("target_resref", ""),
        )

    @property
    def mdx_path(self) -> Path:
        return self.mdl_path.with_suffix(".mdx")

    @property
    def manifest_path(self) -> Path:
        return self.mdl_path.with_name(f"{self.mdl_path.stem}_override_manifest.json")

    @property
    def readme_path(self) -> Path:
        return self.mdl_path.with_name(f"{self.mdl_path.stem}_override_readme.txt")


def package_character_override_candidate(
    request: CharacterBuilderOverridePackageRequest,
) -> CharacterBuilderOverridePackageResult:
    """Stage a verified MDL/MDX pair for safe Override/Patcher installation."""

    validation_payload, preflight = _preflight_package_request(request)
    target_mdl = _target_mdl_path(request.output_dir, request.target_resref)
    target_mdx = target_mdl.with_suffix(".mdx")
    manifest_path = target_mdl.with_name(f"{target_mdl.stem}_override_manifest.json")
    readme_path = target_mdl.with_name(f"{target_mdl.stem}_override_readme.txt")

    metadata = {
        "mode": "character_builder_override_package",
        "game": request.game,
        "target_resref": request.target_resref.lower(),
        "source_mdl_path": str(request.source_mdl_path),
        "source_mdx_path": str(request.source_mdl_path.with_suffix(".mdx")),
        "validation_report_path": str(
            request.validation_report_path or _default_validation_report_path(request.source_mdl_path)
        ),
        **dict(request.metadata or {}),
    }
    job_request = ExportJobRequest(
        job_id=f"character_override_{request.target_resref.lower()}",
        kind="character_override_package",
        outputs=[
            ExportOutputSpec(target_mdl, "mdl"),
            ExportOutputSpec(target_mdx, "mdx"),
            ExportOutputSpec(manifest_path, "manifest"),
            ExportOutputSpec(readme_path, "readme"),
        ],
        overwrite=request.overwrite,
        metadata=metadata,
        preflight_report=preflight,
        validation_bus_source="character.override_package",
    )

    manifest_holder: dict[str, Any] = {}

    def _writer(context: ExportJobContext) -> None:
        source_mdx = request.source_mdl_path.with_suffix(".mdx")
        context.write_bytes(target_mdl, request.source_mdl_path.read_bytes())
        context.write_bytes(target_mdx, source_mdx.read_bytes())
        package_hashes = _staged_output_hashes(context, target_mdl, target_mdx)
        manifest = _build_manifest(
            request,
            validation_payload,
            target_mdl,
            target_mdx,
            package_hashes=package_hashes,
        )
        manifest_holder["manifest"] = manifest
        context.write_text(
            manifest_path,
            json.dumps(manifest, indent=2, sort_keys=True),
        )
        context.write_text(readme_path, _build_readme(manifest))

    def _verifier(context: ExportJobContext) -> ValidationReport:
        issues: list[ValidationIssue] = []
        staged_manifest = context.staged_path_for(manifest_path)
        try:
            parsed = json.loads(staged_manifest.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(_issue(
                "character.override_package.manifest_invalid",
                f"Override package manifest could not be read: {exc}",
            ))
            return ValidationReport(issues=issues, source="character.override_package.verify")

        if parsed.get("schema") != _PACKAGE_SCHEMA:
            issues.append(_issue(
                "character.override_package.manifest_invalid",
                "Override package manifest schema is invalid.",
                details={"schema": parsed.get("schema")},
            ))
        if parsed.get("target_resref") != request.target_resref.lower():
            issues.append(_issue(
                "character.override_package.target_mismatch",
                "Override package manifest target resref does not match request.",
                details={
                    "expected": request.target_resref.lower(),
                    "actual": parsed.get("target_resref"),
                },
            ))
        return ValidationReport(issues=issues, source="character.override_package.verify")

    export_result = run_export_job(job_request, writer=_writer, verifier=_verifier)
    manifest = (
        manifest_holder.get("manifest")
        if export_result.succeeded
        else _build_manifest(
            request,
            validation_payload,
            target_mdl,
            target_mdx,
            package_hashes={},
        )
        if validation_payload
        else {}
    )
    return CharacterBuilderOverridePackageResult(
        export_job_result=export_result,
        manifest=manifest,
    )


def _preflight_package_request(
    request: CharacterBuilderOverridePackageRequest,
) -> tuple[dict[str, Any], ValidationReport]:
    issues: list[ValidationIssue] = []
    target = request.target_resref
    if not target:
        issues.append(_issue(
            "character.override_package.resref_required",
            "Target replacement resref is required.",
        ))
    elif len(target) > KOTOR_NATIVE_RESREF_MAX_LEN:
        issues.append(_issue(
            "character.override_package.resref_too_long",
            f"Target resref '{target}' exceeds the KOTOR {KOTOR_NATIVE_RESREF_MAX_LEN}-character limit.",
            details={"target_resref": target, "max_length": KOTOR_NATIVE_RESREF_MAX_LEN},
        ))
    elif not _RESREF_PATTERN.match(target):
        issues.append(_issue(
            "character.override_package.resref_unsafe",
            f"Target resref '{target}' is not safe for KOTOR Override packaging.",
            details={"target_resref": target},
        ))

    source_mdl = request.source_mdl_path
    source_mdx = source_mdl.with_suffix(".mdx")
    if not source_mdl.exists():
        issues.append(_issue(
            "character.override_package.source_missing",
            f"Source MDL does not exist: {source_mdl}",
            details={"path": str(source_mdl)},
        ))
    if not source_mdx.exists():
        issues.append(_issue(
            "character.override_package.source_missing",
            f"Source MDX does not exist: {source_mdx}",
            details={"path": str(source_mdx)},
        ))

    validation_path = request.validation_report_path or _default_validation_report_path(source_mdl)
    validation_payload: dict[str, Any] = {}
    if not validation_path.exists():
        issues.append(_issue(
            "character.override_package.validation_report_missing",
            f"Character Builder validation report is required: {validation_path}",
            details={"path": str(validation_path)},
        ))
    else:
        try:
            validation_payload = json.loads(validation_path.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(_issue(
                "character.override_package.validation_report_invalid",
                f"Character Builder validation report could not be read: {exc}",
                details={"path": str(validation_path), "exception_type": type(exc).__name__},
            ))
        else:
            issues.extend(_validation_payload_issues(validation_payload, request))

    return validation_payload, ValidationReport(
        issues=issues,
        source="character.override_package.preflight",
    )


def _validation_payload_issues(
    payload: dict[str, Any],
    request: CharacterBuilderOverridePackageRequest,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if payload.get("schema") != _VALIDATION_SCHEMA:
        issues.append(_issue(
            "character.override_package.validation_report_invalid",
            "Character Builder validation report has an unexpected schema.",
            details={"schema": payload.get("schema")},
        ))
    if payload.get("verified") is not True:
        issues.append(_issue(
            "character.override_package.export_not_verified",
            "Only reload-verified Character Builder MDL/MDX exports can be packaged.",
            details={"verified": payload.get("verified"), "status": payload.get("status")},
        ))
    capability = payload.get("capability") if isinstance(payload.get("capability"), dict) else {}
    stage = capability.get("stage")
    if stage not in {"export_candidate", "game_tested"}:
        issues.append(_issue(
            "character.override_package.capability_stage_invalid",
            "Character Builder export is not at an install-package capable stage.",
            details={"stage": stage},
        ))
    output_hashes = _normalize_output_hashes(payload.get("output_hashes"))
    if not output_hashes:
        issues.append(_issue(
            "character.override_package.output_hashes_missing",
            (
                "Character Builder validation report does not record MDL/MDX "
                "output hashes."
            ),
        ))
    else:
        actual_hashes = _file_pair_hashes(request.source_mdl_path)
        mismatched = _hash_mismatches(output_hashes, actual_hashes)
        if mismatched:
            issues.append(_issue(
                "character.override_package.output_hash_mismatch",
                (
                    "Character Builder validation report hashes do not match "
                    "the MDL/MDX files being packaged."
                ),
                details={"mismatches": mismatched},
            ))

    if stage == "game_tested" and not character_game_test_evidence_passed(
        payload.get("game_test_evidence"),
        output_hashes,
        require_output_hashes=True,
    ):
        issues.append(_issue(
            "character.override_package.game_test_evidence_incomplete",
            (
                "Character Builder export claims game-tested status without "
                "complete K1/K2 checklist and artifact-hash evidence."
            ),
            details={
                "stage": stage,
                "game_test_status": capability.get("game_test_status"),
            },
        ))
    game = str(payload.get("game") or "").upper()
    if game and game != request.game:
        issues.append(_issue(
            "character.override_package.game_mismatch",
            "Character Builder validation report game does not match package request.",
            details={"expected": request.game, "actual": game},
        ))

    workflow = (
        payload.get("metadata", {}).get("character_builder_workflow", {})
        if isinstance(payload.get("metadata"), dict)
        else {}
    )
    if workflow.get("native_skeleton_is_authority") is not True:
        issues.append(_issue(
            "character.override_package.native_authority_missing",
            "Character Builder workflow evidence does not prove native KOTOR skeleton authority.",
        ))
    if workflow.get("imported_mesh_role") != "payload_guest":
        issues.append(_issue(
            "character.override_package.payload_role_missing",
            "Character Builder workflow evidence does not identify the imported mesh as payload guest.",
        ))
    if workflow.get("final_dag_source") != "selected_kotor_base":
        issues.append(_issue(
            "character.override_package.final_dag_source_invalid",
            "Character Builder workflow evidence does not identify the selected KOTOR base as final DAG source.",
        ))
    return issues


def _build_manifest(
    request: CharacterBuilderOverridePackageRequest,
    validation_payload: dict[str, Any],
    target_mdl: Path,
    target_mdx: Path,
    *,
    package_hashes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    capability = validation_payload.get("capability")
    capability = capability if isinstance(capability, dict) else {}
    workflow = {}
    metadata = validation_payload.get("metadata")
    if isinstance(metadata, dict):
        workflow = metadata.get("character_builder_workflow") or {}
        workflow = workflow if isinstance(workflow, dict) else {}
    evidence_gates = validation_payload.get("character_builder_evidence_gates")
    evidence_gates = evidence_gates if isinstance(evidence_gates, dict) else {}
    return {
        "schema": _PACKAGE_SCHEMA,
        "game": request.game,
        "target_resref": request.target_resref.lower(),
        "outputs": {
            "mdl": str(target_mdl),
            "mdx": str(target_mdx),
        },
        "source_export": {
            "mdl": str(request.source_mdl_path),
            "mdx": str(request.source_mdl_path.with_suffix(".mdx")),
            "validation_report": str(
                request.validation_report_path or _default_validation_report_path(request.source_mdl_path)
            ),
            "output_hashes": _normalize_output_hashes(validation_payload.get("output_hashes")),
        },
        "package_output_hashes": {
            "algorithm": "sha256",
            "artifacts": package_hashes,
        },
        "capability": {
            "stage": capability.get("stage", "blocked"),
            "game_tested": bool(capability.get("game_tested", False)),
            "game_test_status": capability.get("game_test_status", "not_game_tested"),
            "game_ready": bool(capability.get("game_ready", False)),
            "game_ready_blockers": list(capability.get("game_ready_blockers") or []),
            "game_ready_actual_gate_stages": dict(
                capability.get("game_ready_actual_gate_stages") or {}
            ),
            "honesty_note": (
                "This package is install-ready only when MDL/MDX export was reload verified. "
                "It is not game-tested until the manual checklist is completed in KOTOR, "
                "and it is not game-ready until all Character Builder evidence gates are clean."
            ),
        },
        "install_instructions": [
            "Review the validation report and this manifest before installing.",
            "Copy the packaged MDL and MDX into Override, or feed them to the project patch workflow.",
            "Do not overwrite a live game install without a backup.",
            "Run the manual in-game checklist before calling the asset game-ready.",
        ],
        "manual_in_game_checklist": list(
            validation_payload.get("manual_in_game_checklist")
            or CHARACTER_BUILDER_MANUAL_CHECKLIST
        ),
        "game_test_evidence": dict(validation_payload.get("game_test_evidence") or {}),
        "engine_evidence": CHARACTER_EXPORT_EVIDENCE,
        "character_builder_evidence_gates": evidence_gates,
        "character_builder_workflow": workflow,
        "metadata": dict(request.metadata or {}),
    }


def _build_readme(manifest: dict[str, Any]) -> str:
    capability = dict(manifest.get("capability") or {})
    evidence_gates = dict(manifest.get("character_builder_evidence_gates") or {})
    lines = [
        "GhostRigger Character Builder Override Package",
        f"Game: {manifest.get('game')}",
        f"Target resref: {manifest.get('target_resref')}",
        f"Capability stage: {capability.get('stage')}",
        f"Game tested: {capability.get('game_tested')}",
        f"Game ready: {capability.get('game_ready')}",
    ]
    blockers = [
        str(item or "")
        for item in list(capability.get("game_ready_blockers") or [])
        if str(item or "").strip()
    ]
    if blockers:
        lines.append("Game-ready blockers:")
        for item in blockers:
            lines.append(f"- {item}")
    if evidence_gates:
        lines.append(
            "Evidence gates: "
            f"fit={_evidence_gate_stage(evidence_gates, 'fit')}, "
            f"bind={_evidence_gate_stage(evidence_gates, 'bind')}, "
            f"weight={_evidence_gate_stage(evidence_gates, 'weight')}, "
            f"animation={_evidence_gate_stage(evidence_gates, 'animation')}, "
            f"material={_evidence_gate_stage(evidence_gates, 'material')}, "
            f"engine={_evidence_gate_stage(evidence_gates, 'engine')}"
        )
        fit_gate = dict(evidence_gates.get("fit") or {})
        paired = dict(fit_gate.get("paired_landmark_alignment") or {})
        if paired.get("present"):
            worst = str(paired.get("worst_pair_role") or "").strip()
            lines.append(
                "Fit paired landmarks: "
                f"{paired.get('pair_count')} pairs, "
                f"rms={paired.get('rms_error')}, "
                f"max={paired.get('max_error')}"
                + (f", worst={worst}" if worst else "")
            )
        engine = dict(evidence_gates.get("engine") or {})
        if engine:
            lines.append(
                "Engine evidence: "
                f"{engine.get('stage')} "
                f"(pending Ghidra: {engine.get('pending_ghidra_count')})"
            )
    lines.extend(["", "Install:"])
    for item in list(manifest.get("install_instructions") or []):
        lines.append(f"- {item}")
    lines.extend(["", "Manual in-game checklist:"])
    for index, item in enumerate(list(manifest.get("manual_in_game_checklist") or []), start=1):
        lines.append(f"{index}. {item}")
    return "\n".join(lines) + "\n"


def _evidence_gate_stage(evidence_gates: dict[str, Any], gate: str) -> str:
    value = evidence_gates.get(gate)
    if not isinstance(value, dict):
        return "missing"
    return str(value.get("stage") or "missing")


def _target_mdl_path(output_dir: Path, target_resref: str) -> Path:
    return Path(output_dir) / f"{str(target_resref or '').lower()}.mdl"


def _default_validation_report_path(source_mdl: Path) -> Path:
    path = Path(source_mdl)
    return path.with_name(f"{path.stem}_validation_report.json")


def _staged_output_hashes(
    context: ExportJobContext,
    target_mdl: Path,
    target_mdx: Path,
) -> dict[str, dict[str, Any]]:
    hashes: dict[str, dict[str, Any]] = {}
    for artifact, final_path in (("mdl", target_mdl), ("mdx", target_mdx)):
        staged = context.staged_path_for(final_path)
        if staged.exists():
            hashes[artifact] = _file_hash(staged)
    return hashes


def _file_pair_hashes(source_mdl: Path) -> dict[str, dict[str, Any]]:
    hashes: dict[str, dict[str, Any]] = {}
    mdl = Path(source_mdl)
    mdx = mdl.with_suffix(".mdx")
    if mdl.exists():
        hashes["mdl"] = _file_hash(mdl)
    if mdx.exists():
        hashes["mdx"] = _file_hash(mdx)
    return hashes


def _file_hash(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"sha256": digest.hexdigest(), "size": Path(path).stat().st_size}


def _normalize_output_hashes(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for key, item in value.items():
        if not isinstance(item, dict):
            continue
        artifact = str(key or "").strip().lower()
        digest = str(item.get("sha256") or "").strip().lower()
        if not artifact or not digest:
            continue
        payload: dict[str, Any] = {"sha256": digest}
        try:
            payload["size"] = int(item.get("size"))
        except (TypeError, ValueError, OverflowError):
            pass
        result[artifact] = payload
    return result


def _hash_mismatches(
    expected_hashes: dict[str, dict[str, Any]],
    actual_hashes: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    mismatches: dict[str, dict[str, Any]] = {}
    for artifact in ("mdl", "mdx"):
        expected = expected_hashes.get(artifact)
        actual = actual_hashes.get(artifact)
        if expected is None or actual is None:
            mismatches[artifact] = {"expected": expected, "actual": actual}
            continue
        if (
            expected.get("sha256") != actual.get("sha256")
            or expected.get("size") != actual.get("size")
        ):
            mismatches[artifact] = {"expected": expected, "actual": actual}
    return mismatches


def _issue(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        severity=ValidationSeverity.BLOCKING,
        subsystem=ValidationSubsystem.CHARACTER,
        code=code,
        message=message,
        details=dict(details or {}),
        source="character.override_package",
    )
