"""Adapters from existing GhostRigger validation/audit reports to ValidationBus."""

from __future__ import annotations

import re
from typing import Any

from src.core.project.project_validation import ProjectValidationReport
from src.core.project.resource_address import ResourceAddress

from .validation_bus import (
    ValidationIssue,
    ValidationNavigationTarget,
    ValidationReport,
    ValidationSeverity,
    ValidationSubsystem,
)


def project_validation_report_to_bus_report(project_report: ProjectValidationReport) -> ValidationReport:
    """Convert T2301 project validation issues into the shared bus shape."""

    issues: list[ValidationIssue] = []
    for issue in getattr(project_report, "issues", []) or []:
        target = getattr(issue, "target", None)
        navigation = None
        resource_target = target if isinstance(target, ResourceAddress) else None
        if target is not None and resource_target is None:
            navigation = ValidationNavigationTarget(route=str(target))
        issues.append(
            ValidationIssue(
                severity=_severity(getattr(issue, "severity", "error")),
                subsystem=ValidationSubsystem.PROJECT,
                code=str(getattr(issue, "code", "") or ""),
                message=str(getattr(issue, "message", "") or ""),
                target=resource_target,
                navigation=navigation,
                fix_hint=getattr(issue, "fix_hint", None),
                details=dict(getattr(issue, "details", {}) or {}),
                source="project.validation",
            )
        )
    return ValidationReport(issues=issues, source="project.validation")


def retarget_preview_audit_to_validation_report(
    preview_audit: Any,
    *,
    slot_name: str | None = None,
    target_model_name: str | None = None,
) -> ValidationReport:
    """Convert a retarget preview audit into shared validation issues."""

    slot = slot_name or str(getattr(preview_audit, "slot_name", "") or "")
    target_name = target_model_name or ""
    prefix = f"Retarget preview audit for slot '{slot}'"
    if target_name:
        prefix += f" on '{target_name}'"

    issues: list[ValidationIssue] = []
    for message in getattr(preview_audit, "finite_transform_failures", []) or []:
        issues.append(
            _retarget_issue(
                ValidationSeverity.BLOCKING,
                "retarget_preview_non_finite_transform",
                f"{prefix}: {message}",
                message,
            )
        )
    for message in getattr(preview_audit, "non_root_translation_deviations", []) or []:
        issues.append(
            _retarget_issue(
                ValidationSeverity.BLOCKING,
                "retarget_preview_non_root_translation",
                f"{prefix}: {message}",
                message,
                fix_hint="Non-root translation transfer is disabled to protect KOTOR mesh deformation.",
            )
        )
    for node_name in getattr(preview_audit, "missing_controller_nodes", []) or []:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.BLOCKING,
                subsystem=ValidationSubsystem.RETARGET,
                code="retarget_preview_unknown_controller_node",
                message=f"{prefix}: unknown controller node '{node_name}'.",
                navigation=ValidationNavigationTarget(node_name=str(node_name)),
                source="retarget.preview_audit",
            )
        )

    root_drift = float(getattr(preview_audit, "root_drift_distance", 0.0) or 0.0)
    if root_drift > 1e-4:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                subsystem=ValidationSubsystem.RETARGET,
                code="retarget_preview_root_drift",
                message=f"{prefix}: root drift distance {root_drift:.6g} exceeds in-place tolerance.",
                details={"root_drift_distance": root_drift},
                source="retarget.preview_audit",
            )
        )

    quat_norm_error = float(getattr(preview_audit, "max_quaternion_norm_error", 0.0) or 0.0)
    if quat_norm_error > 1e-4:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                subsystem=ValidationSubsystem.RETARGET,
                code="retarget_preview_quaternion_norm_error",
                message=f"{prefix}: maximum quaternion norm error is {quat_norm_error:.6g}.",
                details={"max_quaternion_norm_error": quat_norm_error},
                source="retarget.preview_audit",
            )
        )

    adjacent_degrees = float(getattr(preview_audit, "max_adjacent_rotation_degrees", 0.0) or 0.0)
    if adjacent_degrees > 150.0:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                subsystem=ValidationSubsystem.RETARGET,
                code="retarget_preview_large_adjacent_rotation",
                message=f"{prefix}: adjacent orientation jump reached {adjacent_degrees:.3f} degrees.",
                details={"max_adjacent_rotation_degrees": adjacent_degrees},
                source="retarget.preview_audit",
            )
        )

    for warning in getattr(preview_audit, "warnings", []) or []:
        issues.append(
            _retarget_issue(
                ValidationSeverity.WARNING,
                "retarget_preview_warning",
                f"{prefix}: {warning}",
                str(warning),
            )
        )

    return ValidationReport(issues=issues, source="retarget.preview_audit")


def _retarget_issue(
    severity: ValidationSeverity,
    code: str,
    message: str,
    raw_text: str,
    *,
    fix_hint: str | None = None,
) -> ValidationIssue:
    node_name, time_seconds = _extract_node_time(raw_text)
    navigation = None
    if node_name is not None or time_seconds is not None:
        navigation = ValidationNavigationTarget(node_name=node_name, time_seconds=time_seconds)
    return ValidationIssue(
        severity=severity,
        subsystem=ValidationSubsystem.RETARGET,
        code=code,
        message=message,
        navigation=navigation,
        fix_hint=fix_hint,
        source="retarget.preview_audit",
    )


def _extract_node_time(text: str) -> tuple[str | None, float | None]:
    node_name = None
    quoted = re.search(r"node\s+'([^']+)'", text)
    if quoted:
        node_name = quoted.group(1)
    else:
        plain = re.search(r"\bnode\s+([A-Za-z0-9_]+)", text)
        if plain:
            node_name = plain.group(1)
        else:
            leading = re.search(r"\b([A-Za-z][A-Za-z0-9_]+)\s+(?:at|changed|has|local|world)\b", text)
            if leading:
                node_name = leading.group(1)

    time_seconds = None
    time_match = re.search(r"\bt\s*=\s*([0-9.+-]+)", text)
    if not time_match:
        time_match = re.search(r"\bat\s+([0-9.+-]+)", text)
    if time_match:
        try:
            time_seconds = float(time_match.group(1))
        except ValueError:
            time_seconds = None
    return node_name, time_seconds


def _severity(value: str) -> ValidationSeverity:
    try:
        return ValidationSeverity(str(value or "").lower())
    except ValueError:
        return ValidationSeverity.ERROR
