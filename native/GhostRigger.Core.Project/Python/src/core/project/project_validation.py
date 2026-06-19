"""Validation helpers for GhostRigger project/session files."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from .ghostrigger_project import (
    CURRENT_GHOSTRIGGER_PROJECT_SCHEMA_VERSION,
    ExportCandidateRef,
    GhostRiggerProject,
)
from .resource_address import ResourceAddress, SUPPORTED_RESOURCE_ADDRESS_SCHEMES


KOTOR_RESREF_MAX_LEN = 16
_SAFE_KOTOR_RESREF_RE = re.compile(r"^[A-Za-z0-9_]+$")


@dataclass
class ProjectValidationIssue:
    severity: str
    code: str
    message: str
    target: ResourceAddress | str | None = None
    fix_hint: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "target": self.target.to_dict() if isinstance(self.target, ResourceAddress) else self.target,
            "fix_hint": self.fix_hint,
            "details": dict(self.details),
        }


@dataclass
class ProjectValidationReport:
    issues: list[ProjectValidationIssue] = field(default_factory=list)

    @property
    def has_blocking(self) -> bool:
        return any(issue.severity == "blocking" for issue in self.issues)

    @property
    def blocking_issues(self) -> list[ProjectValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "blocking"]

    def add(
        self,
        severity: str,
        code: str,
        message: str,
        *,
        target: ResourceAddress | str | None = None,
        fix_hint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.issues.append(
            ProjectValidationIssue(
                severity=severity,
                code=code,
                message=message,
                target=target,
                fix_hint=fix_hint,
                details=dict(details or {}),
            )
        )


def _json_issue(value: Any, target: ResourceAddress | str | None, context: str) -> ProjectValidationIssue | None:
    try:
        json.dumps(value)
    except TypeError as exc:
        return ProjectValidationIssue(
            severity="blocking",
            code="metadata_not_json_serializable",
            message=f"{context} contains non-JSON-serializable data: {exc}",
            target=target,
            fix_hint="Store file paths or resource addresses instead of raw bytes or Python objects.",
        )
    return None


def _require(report: ProjectValidationReport, condition: bool, code: str, message: str, target: Any) -> None:
    if not condition:
        report.add("blocking", code, message, target=target)


def validate_resource_address(address: ResourceAddress, *, strict: bool = True) -> list[ProjectValidationIssue]:
    report = ProjectValidationReport()
    target = address
    if not isinstance(address, ResourceAddress):
        return [
            ProjectValidationIssue(
                severity="blocking",
                code="invalid_resource_address",
                message="Resource address must be a ResourceAddress instance.",
                target=str(address),
            )
        ]

    _require(report, bool(address.scheme), "missing_scheme", "Resource address scheme is required.", target)
    if address.scheme and address.scheme not in SUPPORTED_RESOURCE_ADDRESS_SCHEMES:
        report.add(
            "blocking",
            "unsupported_scheme",
            f"Unsupported resource address scheme '{address.scheme}'.",
            target=target,
        )

    if address.scheme == "module_resource":
        _require(report, bool(address.module_id), "missing_module_id", "Module resource address requires module_id.", target)
        _require(report, bool(address.resref), "missing_resref", "Module resource address requires resref.", target)
        _require(report, bool(address.restype), "missing_restype", "Module resource address requires restype.", target)
    elif address.scheme == "local_file":
        _require(report, bool(address.path), "missing_path", "Local file resource address requires path.", target)
    elif address.scheme in {"kmap_object", "kmax_object"}:
        _require(
            report,
            bool(address.object_id),
            "missing_object_id",
            f"{address.scheme} resource address requires object_id.",
            target,
        )
    elif address.scheme in {"game_resource", "override_resource"}:
        if not address.path:
            _require(report, bool(address.resref), "missing_resref", f"{address.scheme} requires resref or path.", target)
            _require(report, bool(address.restype), "missing_restype", f"{address.scheme} requires restype or path.", target)

    if address.resref is not None:
        _validate_resref(report, address.resref, target, strict=strict)

    metadata_issue = _json_issue(address.metadata, target, "Resource address metadata")
    if metadata_issue:
        report.issues.append(metadata_issue)

    return report.issues


def validate_ghostrigger_project(project: GhostRiggerProject, *, strict: bool = True) -> ProjectValidationReport:
    report = ProjectValidationReport()

    _require(report, bool(project.project_id), "missing_project_id", "GhostRigger project ID is required.", "project_id")
    if project.schema_version != CURRENT_GHOSTRIGGER_PROJECT_SCHEMA_VERSION:
        report.add(
            "blocking",
            "unsupported_schema_version",
            (
                f"Unsupported GhostRigger project schema version {project.schema_version}. "
                f"This build supports version {CURRENT_GHOSTRIGGER_PROJECT_SCHEMA_VERSION}."
            ),
            target="schema_version",
        )

    _append_json_issue(report, project.metadata, "project.metadata", "Project metadata")

    for collection_name in (
        "game_install_refs",
        "imported_assets",
        "character_jobs",
        "retarget_jobs",
        "module_workspaces",
        "map_projects",
        "scenario_packages",
        "validation_snapshots",
        "export_candidates",
    ):
        _validate_duplicate_ids(report, getattr(project, collection_name), collection_name)

    for asset in project.imported_assets:
        _validate_address_field(report, asset.address, f"imported_assets.{asset.id}.address", strict)
        _append_json_issue(report, asset.metadata, f"imported_assets.{asset.id}.metadata", "Imported asset metadata")

    for job in project.character_jobs:
        for field_name in ("source_asset", "target_base_model", "last_export"):
            _validate_optional_address_field(report, getattr(job, field_name), f"character_jobs.{job.id}.{field_name}", strict)
        _append_json_issue(report, job.metadata, f"character_jobs.{job.id}.metadata", "Character job metadata")

    for job in project.retarget_jobs:
        for field_name in ("source", "target", "profile", "last_preview", "last_export"):
            _validate_optional_address_field(report, getattr(job, field_name), f"retarget_jobs.{job.id}.{field_name}", strict)
        if job.requires_custom_animation_patch and not job.output_animation_name:
            report.add(
                "blocking",
                "missing_custom_animation_name",
                "Retarget jobs that require the custom animation patch must define output_animation_name.",
                target=f"retarget_jobs.{job.id}.output_animation_name",
            )
        _append_json_issue(report, job.metadata, f"retarget_jobs.{job.id}.metadata", "Retarget job metadata")

    for workspace in project.module_workspaces:
        _validate_optional_address_field(
            report,
            workspace.base_module,
            f"module_workspaces.{workspace.id}.base_module",
            strict,
        )
        for index, address in enumerate(workspace.edited_resources):
            _validate_address_field(report, address, f"module_workspaces.{workspace.id}.edited_resources[{index}]", strict)
        _append_json_issue(
            report,
            workspace.metadata,
            f"module_workspaces.{workspace.id}.metadata",
            "Module workspace metadata",
        )

    for map_project in project.map_projects:
        for field_name in ("kmap_address", "kmax_scene_address"):
            _validate_optional_address_field(report, getattr(map_project, field_name), f"map_projects.{map_project.id}.{field_name}", strict)
        _append_json_issue(report, map_project.metadata, f"map_projects.{map_project.id}.metadata", "Map project metadata")

    for package in project.scenario_packages:
        _validate_address_list(report, package.actors, f"scenario_packages.{package.id}.actors", strict)
        _validate_address_list(report, package.scripts, f"scenario_packages.{package.id}.scripts", strict)
        _validate_address_list(report, package.dialogs, f"scenario_packages.{package.id}.dialogs", strict)
        _validate_address_list(report, package.sequences, f"scenario_packages.{package.id}.sequences", strict)
        _append_json_issue(report, package.metadata, f"scenario_packages.{package.id}.metadata", "Scenario package metadata")

    for snapshot in project.validation_snapshots:
        _validate_optional_address_field(report, snapshot.address, f"validation_snapshots.{snapshot.id}.address", strict)
        _append_json_issue(
            report,
            snapshot.metadata,
            f"validation_snapshots.{snapshot.id}.metadata",
            "Validation snapshot metadata",
        )

    for candidate in project.export_candidates:
        _validate_export_candidate(report, candidate, strict=strict)

    return report


def _validate_resref(
    report: ProjectValidationReport,
    resref: str,
    target: ResourceAddress | str,
    *,
    strict: bool,
) -> None:
    severity = "blocking" if strict else "warning"
    if not resref:
        report.add("blocking", "empty_resref", "KOTOR resource resref cannot be empty.", target=target)
        return
    if not _SAFE_KOTOR_RESREF_RE.match(resref):
        report.add(
            "blocking",
            "unsafe_resref",
            f"KOTOR resource resref '{resref}' contains unsafe characters.",
            target=target,
            fix_hint="Use letters, numbers, and underscores for KOTOR resource resrefs.",
        )
    if len(resref) > KOTOR_RESREF_MAX_LEN:
        report.add(
            severity,
            "resref_too_long",
            f"KOTOR resource resref '{resref}' is longer than {KOTOR_RESREF_MAX_LEN} characters.",
            target=target,
            fix_hint="Use a 16-character-or-shorter KOTOR-safe resref for game resources.",
        )


def _validate_duplicate_ids(report: ProjectValidationReport, items: Iterable[Any], collection_name: str) -> None:
    seen: dict[str, int] = {}
    for index, item in enumerate(items):
        item_id = str(getattr(item, "id", "") or "")
        target = f"{collection_name}[{index}]"
        if not item_id:
            report.add("blocking", "missing_id", f"{collection_name} entry at index {index} is missing id.", target=target)
            continue
        if item_id in seen:
            report.add(
                "blocking",
                "duplicate_id",
                f"{collection_name} contains duplicate id '{item_id}'.",
                target=target,
                details={"first_index": seen[item_id], "duplicate_index": index},
            )
        else:
            seen[item_id] = index


def _append_json_issue(report: ProjectValidationReport, value: Any, target: str, context: str) -> None:
    issue = _json_issue(value, target, context)
    if issue:
        report.issues.append(issue)


def _validate_address_field(
    report: ProjectValidationReport,
    address: ResourceAddress,
    target: str,
    strict: bool,
) -> None:
    for issue in validate_resource_address(address, strict=strict):
        if issue.target is None:
            issue.target = target
        report.issues.append(issue)


def _validate_optional_address_field(
    report: ProjectValidationReport,
    address: ResourceAddress | None,
    target: str,
    strict: bool,
) -> None:
    if address is not None:
        _validate_address_field(report, address, target, strict)


def _validate_address_list(
    report: ProjectValidationReport,
    addresses: list[ResourceAddress],
    target: str,
    strict: bool,
) -> None:
    for index, address in enumerate(addresses):
        _validate_address_field(report, address, f"{target}[{index}]", strict)


def _validate_export_candidate(
    report: ProjectValidationReport,
    candidate: ExportCandidateRef,
    *,
    strict: bool,
) -> None:
    _validate_address_list(report, candidate.outputs, f"export_candidates.{candidate.id}.outputs", strict)
    _validate_optional_address_field(report, candidate.manifest, f"export_candidates.{candidate.id}.manifest", strict)
    _validate_optional_address_field(
        report,
        candidate.validation_snapshot,
        f"export_candidates.{candidate.id}.validation_snapshot",
        strict,
    )
    if candidate.verified and not candidate.outputs:
        report.add(
            "blocking",
            "verified_export_without_outputs",
            "Verified export candidates must reference at least one output resource.",
            target=f"export_candidates.{candidate.id}.outputs",
        )
    if candidate.verified and candidate.outputs and candidate.manifest is None and not candidate.metadata.get("manifest_not_required"):
        report.add(
            "warning",
            "verified_export_without_manifest",
            "Verified export candidates should reference a manifest or explain why no manifest is required.",
            target=f"export_candidates.{candidate.id}.manifest",
        )
    _append_json_issue(report, candidate.metadata, f"export_candidates.{candidate.id}.metadata", "Export candidate metadata")
