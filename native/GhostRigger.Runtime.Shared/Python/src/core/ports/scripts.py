"""Script compiler port for KOTOR/Aurora tooling adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from src.core.project.resource_address import ResourceAddress
from src.core.validation.validation_bus import ValidationReport


@dataclass(frozen=True)
class ScriptCompileResult:
    """Compiled script bytes plus diagnostics and provenance."""

    source: ResourceAddress | Path | str
    output: bytes = b""
    report: ValidationReport = field(default_factory=lambda: ValidationReport(source="script_compile"))
    metadata: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class ScriptCompilerPort(Protocol):
    """Compile script source into game-ready bytecode without owning the compiler."""

    def compile_script(self, source: ResourceAddress | Path | str, *, game: str | None = None) -> ScriptCompileResult:
        ...
