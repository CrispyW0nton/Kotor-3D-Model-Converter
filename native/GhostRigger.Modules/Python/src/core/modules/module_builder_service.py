"""Builder/package service for KMAP projects."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.level import KMapProject
from src.core.level.kmap_validator import KMapValidator
from src.core.level.level_manifest import build_level_manifest


@dataclass
class ModuleBuildResult:
    ok: bool = False
    output_dir: str = ""
    manifest_path: str = ""
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_built"


class ModuleBuilderService:
    def build_preview(self, project: KMapProject, output_dir: str | Path) -> ModuleBuildResult:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        issues = KMapValidator().validate(project)
        blocking = [issue for issue in issues if issue.severity.lower() == "error"]
        manifest_path = output / f"{project.name}_manifest.json"
        manifest = build_level_manifest(project, kmap_path=project.path, issues=issues)
        manifest["build_mode"] = "preview"
        manifest["notes"] = [
            "Structured KMAP project output generated.",
            "Full KOTOR module archive writing is experimental and must not overwrite source modules.",
        ]
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return ModuleBuildResult(
            ok=not blocking,
            output_dir=str(output),
            manifest_path=str(manifest_path),
            warnings=[issue.message for issue in issues if issue.severity.lower() != "error"],
            blocking_issues=[issue.message for issue in blocking],
            message="Generated build preview manifest." if not blocking else "Build preview found blocking validation errors.",
            code="preview_generated" if not blocking else "validation_blocked",
        )
