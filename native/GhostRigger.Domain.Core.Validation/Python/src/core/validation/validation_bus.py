"""Shared validation issue schema and in-memory bus for GhostRigger."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Callable

from src.core.project.resource_address import ResourceAddress
from src.core.validation._native import native_validation


class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class ValidationSubsystem(str, Enum):
    PROJECT = "project"
    CHARACTER = "character"
    RETARGET = "retarget"
    MODULE = "module"
    MAP = "map"
    SCENARIO = "scenario"
    SCRIPT = "script"
    EXPORT = "export"
    RESOURCE = "resource"
    VIEWPORT = "viewport"


_SEVERITY_RANK = {
    ValidationSeverity.INFO: 0,
    ValidationSeverity.WARNING: 1,
    ValidationSeverity.ERROR: 2,
    ValidationSeverity.BLOCKING: 3,
}


@dataclass(frozen=True)
class ValidationNavigationTarget:
    route: str | None = None
    resource: ResourceAddress | None = None
    object_id: str | None = None
    field_path: str | None = None
    time_seconds: float | None = None
    node_name: str | None = None
    camera_angle: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True)
class ValidationIssue:
    severity: ValidationSeverity
    subsystem: ValidationSubsystem
    code: str
    message: str
    target: ResourceAddress | None = None
    navigation: ValidationNavigationTarget | None = None
    fix_hint: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    issue_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "severity", _coerce_severity(self.severity))
        object.__setattr__(self, "subsystem", _coerce_subsystem(self.subsystem))
        object.__setattr__(self, "code", str(self.code or ""))
        object.__setattr__(self, "message", str(self.message or ""))
        object.__setattr__(self, "details", dict(self.details or {}))


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_blocking(self) -> bool:
        return any(issue.severity == ValidationSeverity.BLOCKING for issue in self.issues)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity in {ValidationSeverity.ERROR, ValidationSeverity.BLOCKING} for issue in self.issues)

    @property
    def blocking_issues(self) -> list[ValidationIssue]:
        return self.by_severity(ValidationSeverity.BLOCKING)

    def by_severity(self, severity: ValidationSeverity | str) -> list[ValidationIssue]:
        wanted = _coerce_severity(severity)
        return [issue for issue in self.issues if issue.severity == wanted]

    def by_subsystem(self, subsystem: ValidationSubsystem | str) -> list[ValidationIssue]:
        wanted = _coerce_subsystem(subsystem)
        return [issue for issue in self.issues if issue.subsystem == wanted]

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)


class ValidationBus:
    """Headless publish/subscribe store for validation reports."""

    def __init__(self) -> None:
        self._issues: list[ValidationIssue] = []
        self._subscribers: list[Callable[[ValidationReport], None]] = []

    def publish(self, report: ValidationReport, *, replace_source: bool = True) -> None:
        source = report.source
        incoming = [
            replace(issue, source=source) if source and issue.source is None else issue
            for issue in report.issues
        ]
        if replace_source and source:
            self._issues = [issue for issue in self._issues if issue.source != source]
        self._issues = _dedupe_issues([*self._issues, *incoming])
        self._notify()

    def clear(
        self,
        *,
        source: str | None = None,
        subsystem: ValidationSubsystem | str | None = None,
    ) -> None:
        if source is None and subsystem is None:
            self._issues = []
        else:
            wanted_subsystem = _coerce_subsystem(subsystem) if subsystem is not None else None
            self._issues = [
                issue
                for issue in self._issues
                if not (
                    (source is None or issue.source == source)
                    and (wanted_subsystem is None or issue.subsystem == wanted_subsystem)
                )
            ]
        self._notify()

    def snapshot(self) -> ValidationReport:
        return ValidationReport(issues=list(self._issues), source="validation_bus")

    def issues(self) -> list[ValidationIssue]:
        return list(self._issues)

    def has_blocking(self) -> bool:
        return self.snapshot().has_blocking

    def subscribe(self, callback: Callable[[ValidationReport], None]) -> Callable[[], None]:
        self._subscribers.append(callback)

        def unsubscribe() -> None:
            try:
                self._subscribers.remove(callback)
            except ValueError:
                pass

        return unsubscribe

    def _notify(self) -> None:
        snapshot = self.snapshot()
        for callback in list(self._subscribers):
            callback(snapshot)


def _python_severity_rank(severity: ValidationSeverity | str) -> int:
    return _SEVERITY_RANK[_coerce_severity(severity)]


def severity_rank(severity: ValidationSeverity | str) -> int:
    dll = native_validation()
    if dll is not None:
        try:
            raw = dll.gr_validation_severity_rank(str(getattr(severity, "value", severity) or "").encode("utf-8"))
            if raw >= 0:
                return int(raw)
        except OSError:
            pass
    return _python_severity_rank(severity)


def make_issue_id(issue: ValidationIssue) -> str:
    if issue.issue_id:
        return str(issue.issue_id)
    payload = {
        "severity": issue.severity.value,
        "subsystem": issue.subsystem.value,
        "code": issue.code,
        "message": issue.message,
        "target": issue.target.stable_key() if issue.target else None,
        "navigation": validation_navigation_target_to_dict(issue.navigation) if issue.navigation else None,
        "source": issue.source,
    }
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"{issue.subsystem.value}:{issue.code}:{digest[:16]}"


def merge_validation_reports(*reports: ValidationReport) -> ValidationReport:
    issues: list[ValidationIssue] = []
    metadata: dict[str, Any] = {}
    sources: list[str] = []
    for report in reports:
        issues.extend(report.issues)
        metadata.update(report.metadata)
        if report.source:
            sources.append(report.source)
    return ValidationReport(
        issues=_dedupe_issues(issues),
        source="+".join(sources) if sources else None,
        metadata=metadata,
    )


def validation_navigation_target_to_dict(target: ValidationNavigationTarget | None) -> dict[str, Any] | None:
    if target is None:
        return None
    data = {
        "route": target.route,
        "resource": target.resource.to_dict() if target.resource else None,
        "object_id": target.object_id,
        "field_path": target.field_path,
        "time_seconds": target.time_seconds,
        "node_name": target.node_name,
        "camera_angle": target.camera_angle,
        "metadata": dict(target.metadata),
    }
    _ensure_json_serializable(data, "Validation navigation target")
    return data


def validation_navigation_target_from_dict(data: dict[str, Any] | None) -> ValidationNavigationTarget | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("Validation navigation target must be a JSON object.")
    return ValidationNavigationTarget(
        route=data.get("route"),
        resource=ResourceAddress.from_dict(data["resource"]) if data.get("resource") else None,
        object_id=data.get("object_id"),
        field_path=data.get("field_path"),
        time_seconds=float(data["time_seconds"]) if data.get("time_seconds") is not None else None,
        node_name=data.get("node_name"),
        camera_angle=data.get("camera_angle"),
        metadata=dict(data.get("metadata") or {}),
    )


def validation_issue_to_dict(issue: ValidationIssue) -> dict[str, Any]:
    data = {
        "severity": issue.severity.value,
        "subsystem": issue.subsystem.value,
        "code": issue.code,
        "message": issue.message,
        "target": issue.target.to_dict() if issue.target else None,
        "navigation": validation_navigation_target_to_dict(issue.navigation),
        "fix_hint": issue.fix_hint,
        "details": dict(issue.details),
        "source": issue.source,
        "issue_id": issue.issue_id,
    }
    _ensure_json_serializable(data, "Validation issue")
    return data


def validation_issue_from_dict(data: dict[str, Any]) -> ValidationIssue:
    if not isinstance(data, dict):
        raise ValueError("Validation issue must be a JSON object.")
    return ValidationIssue(
        severity=ValidationSeverity(data.get("severity") or ValidationSeverity.ERROR.value),
        subsystem=ValidationSubsystem(data.get("subsystem") or ValidationSubsystem.PROJECT.value),
        code=str(data.get("code") or ""),
        message=str(data.get("message") or ""),
        target=ResourceAddress.from_dict(data["target"]) if data.get("target") else None,
        navigation=validation_navigation_target_from_dict(data.get("navigation")),
        fix_hint=data.get("fix_hint"),
        details=dict(data.get("details") or {}),
        source=data.get("source"),
        issue_id=data.get("issue_id"),
    )


def validation_report_to_dict(report: ValidationReport) -> dict[str, Any]:
    data = {
        "source": report.source,
        "metadata": dict(report.metadata),
        "issues": [validation_issue_to_dict(issue) for issue in report.issues],
    }
    _ensure_json_serializable(data, "Validation report")
    return data


def validation_report_from_dict(data: dict[str, Any]) -> ValidationReport:
    if not isinstance(data, dict):
        raise ValueError("Validation report must be a JSON object.")
    return ValidationReport(
        source=data.get("source"),
        metadata=dict(data.get("metadata") or {}),
        issues=[validation_issue_from_dict(issue) for issue in data.get("issues", []) or []],
    )


def _dedupe_issues(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    seen: set[str] = set()
    deduped: list[ValidationIssue] = []
    for issue in issues:
        key = make_issue_id(issue)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


def _python_coerce_severity(value: ValidationSeverity | str) -> ValidationSeverity:
    if isinstance(value, ValidationSeverity):
        return value
    return ValidationSeverity(str(value or ValidationSeverity.ERROR.value).lower())


def _coerce_severity(value: ValidationSeverity | str) -> ValidationSeverity:
    if isinstance(value, ValidationSeverity):
        return value
    raw_value = str(value or ValidationSeverity.ERROR.value)
    dll = native_validation()
    if dll is not None:
        try:
            if dll.gr_validation_is_valid_severity(raw_value.encode("utf-8")):
                return ValidationSeverity(raw_value.lower())
        except OSError:
            pass
    return _python_coerce_severity(value)


def _python_coerce_subsystem(value: ValidationSubsystem | str) -> ValidationSubsystem:
    if isinstance(value, ValidationSubsystem):
        return value
    return ValidationSubsystem(str(value or ValidationSubsystem.PROJECT.value).lower())


def _coerce_subsystem(value: ValidationSubsystem | str) -> ValidationSubsystem:
    if isinstance(value, ValidationSubsystem):
        return value
    raw_value = str(value or ValidationSubsystem.PROJECT.value)
    dll = native_validation()
    if dll is not None:
        try:
            if dll.gr_validation_is_valid_subsystem(raw_value.encode("utf-8")):
                return ValidationSubsystem(raw_value.lower())
        except OSError:
            pass
    return _python_coerce_subsystem(value)


def _ensure_json_serializable(value: Any, context: str) -> None:
    try:
        json.dumps(value)
    except TypeError as exc:
        raise ValueError(f"{context} contains non-JSON-serializable data: {exc}") from exc
