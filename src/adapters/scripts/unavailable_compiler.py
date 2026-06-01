"""Unavailable script compiler adapter.

This adapter gives workflows a concrete ``ScriptCompilerPort`` implementation
when no NWScript compiler is configured. It reports a blocking validation result
instead of silently passing source through as bytecode.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.ports import ScriptCompileResult, ScriptCompilerPort
from src.core.project.resource_address import ResourceAddress
from src.core.validation.validation_bus import (
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
    ValidationSubsystem,
)


@dataclass(frozen=True)
class UnavailableScriptCompiler(ScriptCompilerPort):
    """Deterministic fallback for script compile requests without a backend."""

    reason: str = "No NWScript compiler adapter is configured."

    def compile_script(self, source: ResourceAddress | Path | str, *, game: str | None = None) -> ScriptCompileResult:
        issue = ValidationIssue(
            severity=ValidationSeverity.BLOCKING,
            subsystem=ValidationSubsystem.SCRIPT,
            code="script.compiler.unavailable",
            message=self.reason,
            target=source if isinstance(source, ResourceAddress) else None,
            details={
                "source": str(source),
                "game": str(game or ""),
            },
        )
        return ScriptCompileResult(
            source=source,
            output=b"",
            report=ValidationReport(issues=[issue], source="script.compiler"),
            metadata={"available": False, "reason": self.reason, "game": str(game or "")},
        )
