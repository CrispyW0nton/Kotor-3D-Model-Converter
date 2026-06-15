"""Manifest helpers for KMAP build/export outputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .kmap_model import KMapProject
from .kmap_validator import KMapValidationIssue


def build_level_manifest(
    project: KMapProject,
    *,
    kmap_path: str = "",
    export_paths: dict[str, Any] | None = None,
    issues: list[KMapValidationIssue] | None = None,
) -> dict[str, Any]:
    return {
        "file_type": "GhostRiggerLevelManifest",
        "file_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "kmap_path": kmap_path or project.path,
        "project": {
            "id": project.project_id,
            "name": project.name,
            "game": project.game,
            "source_game": project.source_game,
            "target_game": project.target_game,
        },
        "module_instances": [module.to_dict() for module in project.modules],
        "rooms": [room.to_dict() for room in project.rooms],
        "walkmeshes": [wok.to_dict() for wok in project.walkmeshes],
        "textures": [texture.to_dict() for texture in project.textures],
        "materials": [material.to_dict() for material in project.materials],
        "blueprints": [blueprint.to_dict() for blueprint in project.blueprints],
        "export_paths": dict(export_paths or {}),
        "validation": [issue.to_dict() for issue in issues or []],
    }
