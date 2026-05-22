from dataclasses import dataclass, field

import pytest

from src.core.project import GhostRiggerProject, ProjectAssetRef, ResourceAddress, validate_ghostrigger_project
from src.core.validation.validation_adapters import (
    project_validation_report_to_bus_report,
    retarget_preview_audit_to_validation_report,
)
from src.core.validation.validation_bus import (
    ValidationBus,
    ValidationIssue,
    ValidationNavigationTarget,
    ValidationReport,
    ValidationSeverity,
    ValidationSubsystem,
    merge_validation_reports,
    severity_rank,
    validation_issue_from_dict,
    validation_issue_to_dict,
    validation_report_to_dict,
)


@dataclass
class FakePreviewAudit:
    slot_name: str = "pause1"
    duration_seconds: float = 1.0
    sample_count: int = 2
    finite_transform_failures: list[str] = field(default_factory=list)
    non_root_translation_deviations: list[str] = field(default_factory=list)
    root_drift_distance: float = 0.0
    max_quaternion_norm_error: float = 0.0
    max_adjacent_rotation_degrees: float = 0.0
    missing_controller_nodes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _resource() -> ResourceAddress:
    return ResourceAddress(
        scheme="module_resource",
        game="k1",
        module_id="tar_m09aa",
        layer="project",
        restype="UTC",
        resref="gr_beklead",
    )


def test_validation_issue_json_roundtrip_preserves_resource_target() -> None:
    issue = ValidationIssue(
        severity=ValidationSeverity.ERROR,
        subsystem=ValidationSubsystem.MODULE,
        code="missing_template",
        message="Template is missing.",
        target=_resource(),
        navigation=ValidationNavigationTarget(route="module/object", field_path="TemplateResRef"),
        fix_hint="Choose a valid UTC.",
        details={"count": 1},
        source="module.validator",
        issue_id="stable-id",
    )

    restored = validation_issue_from_dict(validation_issue_to_dict(issue))

    assert restored == issue
    assert restored.target == _resource()


def test_node_casing_is_preserved() -> None:
    issue = ValidationIssue(
        severity="warning",
        subsystem="retarget",
        code="node_pose",
        message="Node pose warning.",
        navigation=ValidationNavigationTarget(node_name="RHand"),
    )

    restored = validation_issue_from_dict(validation_issue_to_dict(issue))

    assert restored.navigation is not None
    assert restored.navigation.node_name == "RHand"


def test_severity_ordering_and_blocking_helpers() -> None:
    assert severity_rank(ValidationSeverity.INFO) < severity_rank(ValidationSeverity.WARNING)
    assert severity_rank(ValidationSeverity.WARNING) < severity_rank(ValidationSeverity.ERROR)
    assert severity_rank(ValidationSeverity.ERROR) < severity_rank(ValidationSeverity.BLOCKING)

    warning_report = ValidationReport(
        issues=[
            ValidationIssue(
                severity="warning",
                subsystem="project",
                code="warn",
                message="warning",
            )
        ]
    )
    assert warning_report.has_blocking is False
    assert warning_report.has_errors is False

    error_report = ValidationReport(
        issues=[
            ValidationIssue(
                severity="error",
                subsystem="project",
                code="err",
                message="error",
            )
        ]
    )
    assert error_report.has_errors is True
    assert error_report.has_blocking is False

    blocking_report = ValidationReport(
        issues=[
            ValidationIssue(
                severity="blocking",
                subsystem="project",
                code="block",
                message="blocking",
            )
        ]
    )
    assert blocking_report.has_errors is True
    assert blocking_report.has_blocking is True
    assert len(blocking_report.blocking_issues) == 1


def test_bus_publish_replaces_same_source() -> None:
    bus = ValidationBus()
    issue_a = ValidationIssue(severity="warning", subsystem="retarget", code="A", message="A", issue_id="A")
    issue_b = ValidationIssue(severity="warning", subsystem="retarget", code="B", message="B", issue_id="B")

    bus.publish(ValidationReport(source="retarget.preview", issues=[issue_a]))
    bus.publish(ValidationReport(source="retarget.preview", issues=[issue_b]))

    assert [issue.code for issue in bus.snapshot().issues] == ["B"]


def test_bus_can_append_merge_and_dedupe_when_replace_source_false() -> None:
    bus = ValidationBus()
    issue_a = ValidationIssue(severity="warning", subsystem="retarget", code="A", message="A", issue_id="A")
    issue_b = ValidationIssue(severity="error", subsystem="retarget", code="B", message="B", issue_id="B")
    issue_b_duplicate = ValidationIssue(severity="error", subsystem="retarget", code="B", message="B", issue_id="B")

    bus.publish(ValidationReport(source="retarget.preview", issues=[issue_a]))
    bus.publish(ValidationReport(source="retarget.preview", issues=[issue_b, issue_b_duplicate]), replace_source=False)

    assert [issue.code for issue in bus.snapshot().issues] == ["A", "B"]


def test_subscribers_receive_snapshots() -> None:
    bus = ValidationBus()
    snapshots: list[ValidationReport] = []
    unsubscribe = bus.subscribe(snapshots.append)

    bus.publish(
        ValidationReport(
            source="project",
            issues=[ValidationIssue(severity="info", subsystem="project", code="ok", message="ok")],
        )
    )
    unsubscribe()
    bus.publish(
        ValidationReport(
            source="project",
            issues=[ValidationIssue(severity="info", subsystem="project", code="later", message="later")],
        )
    )

    assert len(snapshots) == 1
    assert snapshots[0].issues[0].code == "ok"


def test_project_validation_adapter_preserves_issues() -> None:
    project = GhostRiggerProject.new("bad")
    project.imported_assets.append(ProjectAssetRef(id="asset", kind="mesh", address=ResourceAddress(scheme="local_file")))
    project_report = validate_ghostrigger_project(project)

    bus_report = project_validation_report_to_bus_report(project_report)

    assert bus_report.issues
    first = bus_report.issues[0]
    assert first.subsystem == ValidationSubsystem.PROJECT
    assert first.severity == ValidationSeverity.BLOCKING
    assert any(issue.code == "missing_path" for issue in bus_report.issues)
    assert any(issue.target and issue.target.scheme == "local_file" for issue in bus_report.issues)


def test_retarget_preview_audit_adapter_maps_hard_failures() -> None:
    audit = FakePreviewAudit(
        finite_transform_failures=["node RHand has non-finite world transform at t=0.5"],
        non_root_translation_deviations=["LForearm changed by 10"],
        missing_controller_nodes=["BadNode"],
        warnings=["mesh deformation audit skipped"],
    )

    report = retarget_preview_audit_to_validation_report(
        audit,
        slot_name="pause1",
        target_model_name="PMBAM",
    )

    assert report.issues
    assert all(issue.subsystem == ValidationSubsystem.RETARGET for issue in report.issues)
    assert len(report.by_severity(ValidationSeverity.BLOCKING)) == 3
    assert len(report.by_severity(ValidationSeverity.WARNING)) == 1
    assert all("pause1" in issue.message for issue in report.issues)
    assert any(issue.navigation and issue.navigation.node_name == "RHand" for issue in report.issues)
    assert any(issue.navigation and issue.navigation.node_name == "BadNode" for issue in report.issues)


def test_non_serializable_details_rejected() -> None:
    report = ValidationReport(
        issues=[
            ValidationIssue(
                severity="error",
                subsystem="project",
                code="bad",
                message="bad",
                details={"bad": b"bytes"},
            )
        ]
    )

    with pytest.raises(ValueError, match="non-JSON-serializable"):
        validation_report_to_dict(report)


def test_merge_reports_preserves_issue_order_deterministically() -> None:
    first = ValidationReport(
        source="first",
        issues=[
            ValidationIssue(severity="info", subsystem="project", code="A", message="A", issue_id="A"),
            ValidationIssue(severity="warning", subsystem="project", code="B", message="B", issue_id="B"),
        ],
    )
    second = ValidationReport(
        source="second",
        issues=[
            ValidationIssue(severity="error", subsystem="module", code="C", message="C", issue_id="C"),
            ValidationIssue(severity="warning", subsystem="project", code="B", message="B", issue_id="B"),
        ],
    )

    merged = merge_validation_reports(first, second)

    assert [issue.code for issue in merged.issues] == ["A", "B", "C"]
    assert merged.source == "first+second"
