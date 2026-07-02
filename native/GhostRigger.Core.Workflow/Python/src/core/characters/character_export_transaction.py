"""Transactional Character Builder MDL/MDX export.

The Character Builder export path must keep the selected native KOTOR model as
the authoritative DAG contract.  This module wraps MDL/MDX writing in the
shared :mod:`src.core.export.export_job` staging lifecycle and records the
engine-evidence-backed preflight report beside every successful export.
"""

from __future__ import annotations

import hashlib
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
    ValidationNavigationTarget,
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
from .native_skeleton import NativeSkeletonSnapshot, native_skeleton_fingerprint
from .character_validation_report import (
    CharacterBuilderValidationReport,
    validation_report_paths,
)


LoaderCallable = Callable[[Path, Path], Any]


_RELOADED_NATIVE_DAG_ROLES = frozenset({"socket", "helper", "deform_helper"})


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
            options=_reload_preflight_options(preflight_options),
        )
        issues.extend(reload_preflight.report.issues)
        reload_dag_report = _verify_reloaded_native_dag_contract(
            loaded,
            native_snapshot,
        )
        issues.extend(reload_dag_report.issues)
        reload_payload_report = _verify_reloaded_payload_contract(
            request.model,
            loaded,
        )
        issues.extend(reload_payload_report.issues)
        if (
            not reload_preflight.report.has_blocking
            and not reload_dag_report.has_blocking
            and not reload_payload_report.has_blocking
        ):
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    subsystem=ValidationSubsystem.CHARACTER,
                    code="character.export.reload_verified",
                    message="Exported MDL/MDX reloaded and passed Character Builder preflight.",
                    details={
                        "engine_evidence": CHARACTER_EXPORT_EVIDENCE,
                        "reloaded_model": _reloaded_model_summary(
                            loaded,
                            native_snapshot,
                        ),
                    },
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


def _reload_preflight_options(
    preflight_options: CharacterExportPreflightOptions,
) -> CharacterExportPreflightOptions:
    """Return runtime checks for a reloaded MDL/MDX.

    The pre-write pass must prove the model came from the Character Builder's
    native-template workflow.  A real MDL reload cannot preserve those Python
    workflow markers, so the verifier keeps structural/runtime checks while
    disabling only workflow-only rig-state requirements.
    """

    return replace(
        preflight_options,
        require_native_template_final_rig=False,
    )


def _verify_reloaded_native_dag_contract(
    model: Any,
    native_snapshot: NativeSkeletonSnapshot | None,
) -> ValidationReport:
    """Return reload-specific proof that the selected native DAG survived IO."""

    issues: list[ValidationIssue] = []
    if native_snapshot is None:
        issues.append(_export_issue(
            "character.export.reload_missing_native_snapshot",
            (
                "Reload verification requires the selected native KOTOR "
                "skeleton snapshot."
            ),
        ))
        return ValidationReport(
            source="character.export_transaction.verify.native_dag",
            issues=issues,
        )

    current_nodes = _model_nodes(model)
    current_paths = {_node_path(node): node for node in current_nodes}
    current_paths_lower = {
        tuple(part.lower() for part in _node_path(node)): node
        for node in current_nodes
    }
    current_names: dict[str, Any] = {}
    for node in current_nodes:
        current_names.setdefault(str(getattr(node, "name", "") or ""), node)

    checked_paths: list[tuple[str, ...]] = []
    for native_node in native_snapshot.nodes:
        if native_node.export_role not in _RELOADED_NATIVE_DAG_ROLES:
            continue
        expected_path = tuple(native_node.full_path)
        checked_paths.append(expected_path)
        if expected_path in current_paths:
            continue

        lower_match = current_paths_lower.get(
            tuple(part.lower() for part in expected_path)
        )
        if lower_match is not None:
            issues.append(_reload_dag_issue(
                "character.export.reload_node_case_changed",
                (
                    f"Reloaded MDL changed native node casing for "
                    f"'{native_node.name}'."
                ),
                native_snapshot=native_snapshot,
                native_node=native_node,
                details={
                    "expected_path": list(expected_path),
                    "actual_path": list(_node_path(lower_match)),
                    "role": native_node.export_role,
                },
            ))
            continue

        exact_name_match = current_names.get(native_node.name)
        if exact_name_match is not None:
            issues.append(_reload_dag_issue(
                "character.export.reload_node_path_changed",
                (
                    f"Reloaded MDL moved native {native_node.export_role} "
                    f"node '{native_node.name}' away from its selected "
                    "KOTOR template path."
                ),
                native_snapshot=native_snapshot,
                native_node=native_node,
                details={
                    "expected_path": list(expected_path),
                    "actual_path": list(_node_path(exact_name_match)),
                    "role": native_node.export_role,
                },
            ))
            continue

        issues.append(_reload_dag_issue(
            "character.export.reload_node_path_missing",
            (
                f"Reloaded MDL is missing native {native_node.export_role} "
                f"node '{native_node.name}' at the selected KOTOR template path."
            ),
            native_snapshot=native_snapshot,
            native_node=native_node,
            details={
                "expected_path": list(expected_path),
                "role": native_node.export_role,
            },
        ))

    if not issues:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            subsystem=ValidationSubsystem.CHARACTER,
            code="character.export.reload_native_dag_verified",
            message=(
                "Reloaded MDL/MDX preserved the selected native KOTOR "
                "structural DAG contract."
            ),
            details=_json_safe({
                "native_snapshot": _native_snapshot_reload_evidence(native_snapshot),
                "checked_roles": sorted(_RELOADED_NATIVE_DAG_ROLES),
                "checked_path_count": len(checked_paths),
                "checked_paths": [list(path) for path in checked_paths],
            }),
            source="character.export_transaction.verify.native_dag",
        ))

    return ValidationReport(
        source="character.export_transaction.verify.native_dag",
        issues=issues,
    )


def _verify_reloaded_payload_contract(
    original_model: Any,
    reloaded_model: Any,
) -> ValidationReport:
    """Return reload-specific proof that imported skin payload survived IO."""

    issues: list[ValidationIssue] = []
    payload_names = _character_payload_mesh_names(original_model)
    if not payload_names:
        issues.append(_export_issue(
            "character.export.reload_payload_names_missing",
            (
                "Reload verification requires imported payload mesh names from "
                "Character Builder bind evidence."
            ),
        ))
        return ValidationReport(
            source="character.export_transaction.verify.payload",
            issues=issues,
        )

    original_payloads = _payload_summaries_by_name(original_model, payload_names)
    reloaded_payloads = _payload_summaries_by_name(reloaded_model, payload_names)
    for name in payload_names:
        expected = original_payloads.get(name)
        actual = reloaded_payloads.get(name)
        if expected is None:
            issues.append(_payload_issue(
                "character.export.reload_payload_missing_from_source",
                (
                    f"Original Character Builder model no longer contains "
                    f"payload mesh '{name}'."
                ),
                payload_name=name,
                details={"payload_name": name},
            ))
            continue
        if actual is None:
            issues.append(_payload_issue(
                "character.export.reload_payload_missing",
                (
                    f"Reloaded MDL/MDX is missing imported payload mesh "
                    f"'{name}'."
                ),
                payload_name=name,
                details={
                    "payload_name": name,
                    "expected": expected,
                },
            ))
            continue

        for key, code, label in (
            ("vertices", "character.export.reload_payload_vertex_count_changed", "vertex count"),
            ("faces", "character.export.reload_payload_face_count_changed", "face count"),
            ("bone_map_count", "character.export.reload_payload_bone_map_count_changed", "bone-map count"),
            ("skin_rows", "character.export.reload_payload_skin_rows_changed", "skin row count"),
        ):
            if expected.get(key) == actual.get(key):
                continue
            issues.append(_payload_issue(
                code,
                (
                    f"Reloaded payload mesh '{name}' changed {label} "
                    "during MDL/MDX writer/readback verification."
                ),
                payload_name=name,
                details={
                    "payload_name": name,
                    "field": key,
                    "expected": expected.get(key),
                    "actual": actual.get(key),
                    "expected_payload": expected,
                    "actual_payload": actual,
                },
            ))

    if not issues:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.INFO,
            subsystem=ValidationSubsystem.CHARACTER,
            code="character.export.reload_payload_verified",
            message=(
                "Reloaded MDL/MDX preserved imported Character Builder payload "
                "mesh geometry and skin binding counts."
            ),
            details=_json_safe({
                "payload_names": payload_names,
                "checked_payload_count": len(payload_names),
                "payloads": [reloaded_payloads[name] for name in payload_names],
            }),
            source="character.export_transaction.verify.payload",
        ))

    return ValidationReport(
        source="character.export_transaction.verify.payload",
        issues=issues,
    )


def _reload_dag_issue(
    code: str,
    message: str,
    *,
    native_snapshot: NativeSkeletonSnapshot,
    native_node: Any,
    details: dict[str, Any],
) -> ValidationIssue:
    payload = {
        **dict(details or {}),
        "native_snapshot": _native_snapshot_reload_evidence(native_snapshot),
        "engine_evidence": CHARACTER_EXPORT_EVIDENCE,
    }
    return ValidationIssue(
        severity=ValidationSeverity.BLOCKING,
        subsystem=ValidationSubsystem.CHARACTER,
        code=code,
        message=message,
        navigation=ValidationNavigationTarget(node_name=str(native_node.name or "")),
        fix_hint=(
            "Inspect the staged/reloaded MDL writer path and restore the exact "
            "native KOTOR node path before promoting this Character Builder export."
        ),
        details=_json_safe(payload),
        source="character.export_transaction.verify.native_dag",
    )


def _native_snapshot_reload_evidence(
    native_snapshot: NativeSkeletonSnapshot,
) -> dict[str, Any]:
    return {
        "model_name": native_snapshot.model_name,
        "game": native_snapshot.game,
        "supermodel": native_snapshot.supermodel,
        "dag_fingerprint": native_skeleton_fingerprint(native_snapshot),
        "dag_fingerprint_algorithm": "sha256",
        "node_count": native_snapshot.node_count,
        "hook_names": list(native_snapshot.hook_names),
    }


def _payload_issue(
    code: str,
    message: str,
    *,
    payload_name: str,
    details: dict[str, Any],
) -> ValidationIssue:
    payload = {
        **dict(details or {}),
        "engine_evidence": CHARACTER_EXPORT_EVIDENCE,
    }
    return ValidationIssue(
        severity=ValidationSeverity.BLOCKING,
        subsystem=ValidationSubsystem.CHARACTER,
        code=code,
        message=message,
        navigation=ValidationNavigationTarget(node_name=payload_name),
        fix_hint=(
            "Inspect the staged/reloaded MDL writer path and restore the "
            "imported mesh payload geometry and skin data before promotion."
        ),
        details=_json_safe(payload),
        source="character.export_transaction.verify.payload",
    )


def _character_payload_mesh_names(model: Any) -> list[str]:
    metadata = getattr(model, "metadata", None)
    metadata = metadata if isinstance(metadata, dict) else {}
    bind = metadata.get("character_builder_bind")
    bind = bind if isinstance(bind, dict) else {}
    payload = bind.get("imported_payload")
    payload = payload if isinstance(payload, dict) else {}
    names = [
        str(name or "").strip()
        for name in payload.get("mesh_names", []) or []
        if str(name or "").strip()
    ]
    if names:
        return names

    rig_state = getattr(model, "_gr_character_builder_rig_state", None)
    if hasattr(rig_state, "payload_mesh_names"):
        return [
            str(name or "").strip()
            for name in getattr(rig_state, "payload_mesh_names", ()) or ()
            if str(name or "").strip()
        ]
    return []


def _payload_summaries_by_name(
    model: Any,
    payload_names: list[str],
) -> dict[str, dict[str, Any]]:
    wanted = set(payload_names)
    result: dict[str, dict[str, Any]] = {}
    for node in _model_nodes(model):
        name = str(getattr(node, "name", "") or "")
        if name not in wanted:
            continue
        result[name] = _payload_summary(node)
    return result


def _payload_summary(node: Any) -> dict[str, Any]:
    # T2518: count only real bone-map entries.  The MDL loader materializes the
    # engine's fixed 16-slot bonemap with blank trailing padding, so comparing
    # raw lengths between a builder-shaped live node (exact count) and its
    # reloaded twin (padded to 16) would flag every <16-bone skin node as
    # "bone-map count changed" during writer/readback verification.
    bone_map = list(getattr(node, "bone_map", []) or [])
    while bone_map and not str(bone_map[-1] or "").strip():
        bone_map.pop()
    return {
        "name": str(getattr(node, "name", "") or ""),
        "is_mesh": bool(getattr(node, "is_mesh", False)),
        "is_skin": bool(getattr(node, "is_skin", False)),
        "vertices": len(list(getattr(node, "vertices", []) or [])),
        "faces": len(list(getattr(node, "faces", []) or [])),
        "bone_map_count": len(bone_map),
        "skin_rows": len(list(getattr(node, "skin_data", []) or [])),
    }


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
        output_hashes=_staged_output_hashes(context, mdl_path),
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


def _staged_output_hashes(
    context: ExportJobContext,
    mdl_path: Path,
) -> dict[str, dict[str, Any]]:
    hashes: dict[str, dict[str, Any]] = {}
    for artifact, final_path in (
        ("mdl", mdl_path),
        ("mdx", mdl_path.with_suffix(".mdx")),
    ):
        try:
            staged_path = context.staged_path_for(final_path)
        except KeyError:
            continue
        if not staged_path.exists():
            continue
        hashes[artifact] = _file_hash(staged_path)
    return hashes


def _file_hash(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "sha256": digest.hexdigest(),
        "size": Path(path).stat().st_size,
    }


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
        fingerprint = native_skeleton_fingerprint(native_snapshot)
        snapshot_summary = {
            "model_name": native_snapshot.model_name,
            "game": native_snapshot.game,
            "supermodel": native_snapshot.supermodel,
            "dag_fingerprint": fingerprint,
            "dag_fingerprint_algorithm": "sha256",
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
        "bind": metadata.get("character_builder_bind"),
        "fit_report": metadata.get("kotor_fit_report"),
        "motion_assignment": metadata.get("character_builder_motion_assignment"),
        "animation_library": metadata.get("character_builder_animation_library"),
        "normalization": normalization_summary,
        "native_snapshot": snapshot_summary,
    })


def _reloaded_model_summary(
    model: Any,
    native_snapshot: NativeSkeletonSnapshot | None,
) -> dict[str, Any]:
    nodes = _model_nodes(model)
    skin_nodes = [node for node in nodes if bool(getattr(node, "is_skin", False))]
    mesh_nodes = [node for node in nodes if bool(getattr(node, "is_mesh", False))]
    skin_payloads = []
    for node in skin_nodes:
        skin_payloads.append({
            "name": str(getattr(node, "name", "") or ""),
            "vertices": len(list(getattr(node, "vertices", []) or [])),
            "faces": len(list(getattr(node, "faces", []) or [])),
            "bone_map_count": len(list(getattr(node, "bone_map", []) or [])),
            "skin_rows": len(list(getattr(node, "skin_data", []) or [])),
        })
    snapshot = None
    if native_snapshot is not None:
        fingerprint = native_skeleton_fingerprint(native_snapshot)
        snapshot = {
            "model_name": native_snapshot.model_name,
            "game": native_snapshot.game,
            "supermodel": native_snapshot.supermodel,
            "dag_fingerprint": fingerprint,
            "dag_fingerprint_algorithm": "sha256",
            "node_count": native_snapshot.node_count,
            "hook_names": list(native_snapshot.hook_names),
        }
    return _json_safe({
        "model_name": str(getattr(model, "name", "") or ""),
        "supermodel": str(getattr(model, "supermodel", "") or "NULL"),
        "node_count": len(nodes),
        "mesh_node_count": len(mesh_nodes),
        "skin_node_count": len(skin_nodes),
        "skin_payloads": skin_payloads,
        "native_snapshot_checked": snapshot,
    })


def _model_nodes(model: Any) -> list[Any]:
    all_nodes = getattr(model, "all_nodes", None)
    if callable(all_nodes):
        return list(all_nodes())
    root = getattr(model, "root_node", None)
    if root is None:
        return []
    result: list[Any] = []
    stack = [root]
    visited: set[int] = set()
    while stack:
        node = stack.pop()
        node_id = id(node)
        if node_id in visited:
            continue
        visited.add(node_id)
        result.append(node)
        stack.extend(reversed(list(getattr(node, "children", []) or [])))
    return result


def _node_path(node: Any) -> tuple[str, ...]:
    names = [str(getattr(node, "name", "") or "")]
    parent = getattr(node, "parent", None)
    visited: set[int] = set()
    while parent is not None:
        parent_id = id(parent)
        if parent_id in visited:
            break
        visited.add(parent_id)
        names.append(str(getattr(parent, "name", "") or ""))
        parent = getattr(parent, "parent", None)
    names.reverse()
    return tuple(names)


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
