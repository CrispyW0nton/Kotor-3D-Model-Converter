"""Export bridge for complete KMAP scenes.

The first pass always writes a sidecar manifest. FBX output is attempted only
when room model objects are attached to KMAP metadata and the existing mesh
exporter can handle them; otherwise the bridge returns a clean dry-run result.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .kmap_model import KMapProject
from .kmap_validator import KMapValidator, KMapValidationIssue
from .level_manifest import build_level_manifest


@dataclass(frozen=True)
class LevelExportOptions:
    selected_only: bool = False
    visible_only: bool = True
    include_textures: bool = True
    include_lightmaps: bool = True
    include_walkmesh: bool = True
    include_lights: bool = True
    include_cameras: bool = True
    bake_transforms: bool = True
    copy_textures: bool = False
    generate_sidecar_manifest: bool = True
    dry_run: bool = False


@dataclass
class LevelExportResult:
    ok: bool = False
    code: str = "not_exported"
    message: str = ""
    fbx_path: str = ""
    manifest_path: str = ""
    warnings: list[str] = field(default_factory=list)
    issues: list[KMapValidationIssue] = field(default_factory=list)


class LevelExportBridge:
    def __init__(self, validator: KMapValidator | None = None) -> None:
        self.validator = validator or KMapValidator()

    def export_fbx(
        self,
        project: KMapProject,
        output_path: str | Path,
        options: LevelExportOptions | None = None,
    ) -> LevelExportResult:
        options = options or LevelExportOptions()
        target = Path(output_path)
        issues = self.validator.validate(project)
        blocking = [issue for issue in issues if issue.severity.lower() == "error"]
        result = LevelExportResult(fbx_path=str(target), issues=issues)
        if blocking:
            result.code = "validation_blocked"
            result.message = "KMAP has validation errors; FBX export was not started."
            return result

        manifest_path = target.with_name(f"{target.stem}_manifest.json")
        manifest = build_level_manifest(
            project,
            export_paths={"fbx": str(target), "manifest": str(manifest_path)},
            issues=issues,
        )
        manifest["export_options"] = options.__dict__
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result.manifest_path = str(manifest_path)

        if options.dry_run:
            result.ok = True
            result.code = "dry_run"
            result.message = "FBX export dry-run generated the scene manifest."
            return result

        model = self._single_export_model(project)
        if model is None:
            result.ok = True
            result.code = "manifest_only"
            result.warnings.append("No assembled export model is available yet; wrote a manifest sidecar only.")
            result.message = "KMAP scene manifest generated. FBX mesh assembly is pending room-model bridge support."
            return result

        try:
            from src.converters.mesh_converter import FBXExporter
        except Exception as exc:
            result.code = "fbx_unavailable"
            result.message = f"FBX exporter is unavailable: {exc}"
            return result

        target.parent.mkdir(parents=True, exist_ok=True)
        ok = bool(FBXExporter().export(model, str(target)))
        result.ok = ok
        result.code = "exported" if ok else "fbx_failed"
        result.message = f"Exported {target.name}." if ok else "FBX exporter reported failure."
        return result

    @staticmethod
    def _single_export_model(project: KMapProject) -> Any:
        models = [room.metadata.get("export_model") for room in project.rooms if isinstance(room.metadata, dict)]
        models = [model for model in models if model is not None]
        return models[0] if len(models) == 1 else None
