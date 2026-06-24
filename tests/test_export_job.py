"""Shared ExportJob transaction helper tests."""

from __future__ import annotations

import json
from pathlib import Path

from src.core.export.export_job import (
    ExportJobContext,
    ExportJobRequest,
    ExportJobStatus,
    ExportOutputSpec,
    run_export_job,
)
from src.core.ports import FileWriterPort
from src.core.validation.validation_bus import (
    ValidationBus,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
    ValidationSubsystem,
)


def _blocking_report(message: str = "blocked") -> ValidationReport:
    return ValidationReport(
        source="test.export",
        issues=[
            ValidationIssue(
                severity=ValidationSeverity.BLOCKING,
                subsystem=ValidationSubsystem.EXPORT,
                code="test.blocking",
                message=message,
            )
        ],
    )


def _request(output: Path, **kwargs) -> ExportJobRequest:
    return ExportJobRequest(
        job_id=kwargs.pop("job_id", "job1"),
        kind=kwargs.pop("kind", "test_export"),
        outputs=kwargs.pop("outputs", [ExportOutputSpec(output, "txt")]),
        **kwargs,
    )


def test_successful_export_writes_staging_then_promotes(tmp_path: Path) -> None:
    final = tmp_path / "out" / "test.txt"
    seen_staged: list[Path] = []

    def writer(context: ExportJobContext) -> None:
        staged = context.staged_path_for(final)
        assert not final.exists()
        assert isinstance(context, FileWriterPort)
        context.write_text(final, "hello", encoding="utf-8")
        seen_staged.append(staged)

    result = run_export_job(_request(final), writer=writer)

    assert result.succeeded is True
    assert result.status == ExportJobStatus.SUCCEEDED
    assert final.read_text(encoding="utf-8") == "hello"
    assert seen_staged and not seen_staged[0].parent.exists()


def test_export_context_file_writer_port_writes_bytes_to_staging(tmp_path: Path) -> None:
    final = tmp_path / "out" / "payload.bin"
    seen_staged: list[Path] = []

    def writer(context: ExportJobContext) -> None:
        assert isinstance(context, FileWriterPort)
        staged = context.staged_path_for(final)
        context.write_bytes(final, b"payload")
        seen_staged.append(staged)
        assert staged.exists()
        assert final.exists() is False

    result = run_export_job(_request(final), writer=writer)

    assert result.succeeded is True
    assert final.read_bytes() == b"payload"
    assert seen_staged and not seen_staged[0].parent.exists()


def test_preflight_blocking_report_prevents_writer_call(tmp_path: Path) -> None:
    final = tmp_path / "blocked.txt"
    called = False
    request = _request(final, preflight_report=_blocking_report())

    def writer(_context: ExportJobContext) -> None:
        nonlocal called
        called = True

    result = run_export_job(request, writer=writer)

    assert result.status == ExportJobStatus.PREFLIGHT_FAILED
    assert called is False
    assert not final.exists()


def test_overwrite_false_blocks_existing_output_before_writer(tmp_path: Path) -> None:
    final = tmp_path / "exists.txt"
    final.write_text("original", encoding="utf-8")
    called = False

    def writer(_context: ExportJobContext) -> None:
        nonlocal called
        called = True

    result = run_export_job(_request(final, overwrite=False), writer=writer)

    assert result.status == ExportJobStatus.PREFLIGHT_FAILED
    assert called is False
    assert final.read_text(encoding="utf-8") == "original"
    assert any(issue.code == "export.output.exists" for issue in result.validation_report.issues)


def test_verifier_failure_prevents_promotion(tmp_path: Path) -> None:
    final = tmp_path / "verified.txt"

    def writer(context: ExportJobContext) -> None:
        context.staged_path_for(final).write_text("staged", encoding="utf-8")

    result = run_export_job(
        _request(final),
        writer=writer,
        verifier=lambda _context: _blocking_report("verification failed"),
    )

    assert result.status == ExportJobStatus.FAILED
    assert not final.exists()
    assert any("verification failed" in issue.message for issue in result.validation_report.issues)


def test_writer_exception_cleans_staging(tmp_path: Path) -> None:
    final = tmp_path / "boom.txt"
    staged_parent: list[Path] = []

    def writer(context: ExportJobContext) -> None:
        staged = context.staged_path_for(final)
        staged.write_text("partial", encoding="utf-8")
        staged_parent.append(staged.parent)
        raise RuntimeError("boom")

    result = run_export_job(_request(final), writer=writer)

    assert result.status == ExportJobStatus.FAILED
    assert not final.exists()
    assert staged_parent and not staged_parent[0].exists()
    assert any("boom" in issue.message for issue in result.validation_report.issues)


def test_duplicate_final_output_paths_fail_preflight(tmp_path: Path) -> None:
    final = tmp_path / "dup.txt"
    called = False

    def writer(_context: ExportJobContext) -> None:
        nonlocal called
        called = True

    request = _request(
        final,
        outputs=[
            ExportOutputSpec(final, "txt"),
            ExportOutputSpec(final, "txt-copy"),
        ],
    )
    result = run_export_job(request, writer=writer)

    assert result.status == ExportJobStatus.PREFLIGHT_FAILED
    assert called is False
    assert any(issue.code == "export.output.duplicate" for issue in result.validation_report.issues)


def test_validation_bus_receives_reports(tmp_path: Path) -> None:
    final = tmp_path / "bus.txt"
    bus = ValidationBus()
    request = _request(
        final,
        preflight_report=_blocking_report("bus failure"),
        validation_bus_source="export.job.test",
    )

    run_export_job(request, writer=lambda _context: None, validation_bus=bus)

    snapshot = bus.snapshot()
    assert any(issue.source == "export.job.test" for issue in snapshot.issues)
    assert any("bus failure" in issue.message for issue in snapshot.issues)


def test_non_serializable_metadata_fails_preflight(tmp_path: Path) -> None:
    final = tmp_path / "bad.txt"
    called = False

    def writer(_context: ExportJobContext) -> None:
        nonlocal called
        called = True

    result = run_export_job(_request(final, metadata={"bad": b"bytes"}), writer=writer)

    assert result.status == ExportJobStatus.PREFLIGHT_FAILED
    assert called is False
    assert any("non-JSON-serializable" in issue.message for issue in result.validation_report.issues)


def test_multi_directory_outputs_stage_and_promote_together(tmp_path: Path) -> None:
    out_a = tmp_path / "a" / "one.txt"
    out_b = tmp_path / "b" / "two.txt"
    seen_staging_dirs: list[Path] = []

    def writer(context: ExportJobContext) -> None:
        context.write_text(out_a, "one", encoding="utf-8")
        context.write_text(out_b, "two", encoding="utf-8")
        staged_a = context.staged_path_for(out_a)
        staged_b = context.staged_path_for(out_b)
        assert staged_a.exists()
        assert staged_b.exists()
        assert staged_a.parent != staged_b.parent
        assert not out_a.exists()
        assert not out_b.exists()
        seen_staging_dirs.extend([staged_a.parent, staged_b.parent])

    result = run_export_job(
        _request(
            out_a,
            outputs=[
                ExportOutputSpec(out_a, "txt"),
                ExportOutputSpec(out_b, "txt"),
            ],
        ),
        writer=writer,
    )

    assert result.status == ExportJobStatus.SUCCEEDED
    assert out_a.read_text(encoding="utf-8") == "one"
    assert out_b.read_text(encoding="utf-8") == "two"
    assert Path(result.staged_paths[str(out_a)]).name == "one.txt"
    assert Path(result.staged_paths[str(out_b)]).name == "two.txt"
    assert seen_staging_dirs and all(not path.exists() for path in seen_staging_dirs)


def test_manifest_writer_output_is_promoted(tmp_path: Path) -> None:
    final = tmp_path / "payload.txt"
    manifest = tmp_path / "payload.manifest.json"

    def writer(context: ExportJobContext) -> None:
        context.staged_path_for(final).write_text("payload", encoding="utf-8")

    def manifest_writer(context: ExportJobContext, result) -> Path:
        staged_manifest = context.staged_path_for(manifest)
        context.write_text(
            manifest,
            json.dumps({"job_id": result.job_id, "kind": result.kind}),
            encoding="utf-8",
        )
        return staged_manifest

    result = run_export_job(
        _request(
            final,
            outputs=[
                ExportOutputSpec(final, "txt"),
                ExportOutputSpec(manifest, "manifest"),
            ],
        ),
        writer=writer,
        manifest_writer=manifest_writer,
    )

    assert result.succeeded is True
    assert result.manifest_path == manifest
    assert manifest.exists()
    assert json.loads(manifest.read_text(encoding="utf-8"))["job_id"] == "job1"

