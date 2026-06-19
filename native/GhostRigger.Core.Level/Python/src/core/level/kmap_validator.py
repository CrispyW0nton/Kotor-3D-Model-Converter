"""Validation for GhostRigger KMAP projects."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .kmap_model import KMAP_FILE_VERSION, KMapProject, LevelTransform


@dataclass(frozen=True)
class KMapValidationIssue:
    severity: str
    code: str
    message: str
    item_id: str = ""
    suggested_fix: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "item_id": self.item_id,
            "suggested_fix": self.suggested_fix,
        }


class KMapValidator:
    def validate(self, project: KMapProject) -> list[KMapValidationIssue]:
        issues: list[KMapValidationIssue] = []
        issues.extend(self._duplicate_ids(project))
        if not project.name.strip():
            issues.append(KMapValidationIssue("Error", "PROJECT_NAME_MISSING", "KMAP project name is empty.", project.project_id))
        if project.game.upper() not in {"K1", "K2"}:
            issues.append(KMapValidationIssue("Error", "INVALID_GAME", f"Unsupported project game '{project.game}'.", project.project_id))
        if project.output_directory and not Path(project.output_directory).exists():
            issues.append(
                KMapValidationIssue(
                    "Warning",
                    "INVALID_OUTPUT_DIRECTORY",
                    f"Output directory does not exist: {project.output_directory}",
                    project.project_id,
                    "Choose or create an output folder before building/exporting.",
                )
            )
        for module in project.modules:
            if module.source_path and not Path(module.source_path).exists():
                issues.append(
                    KMapValidationIssue(
                        "Warning",
                        "MISSING_SOURCE_MODULE",
                        f"Module '{module.module_name}' source path is missing: {module.source_path}",
                        module.module_id,
                        "Re-link the source module or clear the stale path.",
                    )
                )
            if not self._valid_transform(module.transform):
                issues.append(KMapValidationIssue("Error", "INVALID_TRANSFORM", f"Module '{module.module_name}' has invalid transform values.", module.module_id))
            for room_id in module.rooms:
                if project.find_room(room_id) is None:
                    issues.append(KMapValidationIssue("Error", "BROKEN_ROOM_REFERENCE", f"Module '{module.module_name}' references missing room {room_id}.", module.module_id))
            for wok_id in module.walkmeshes:
                if project.find_walkmesh(wok_id) is None:
                    issues.append(KMapValidationIssue("Warning", "BROKEN_WALKMESH_REFERENCE", f"Module '{module.module_name}' references missing walkmesh {wok_id}.", module.module_id))
        room_ids_with_wok = {wok.room_id for wok in project.walkmeshes if wok.room_id}
        for room in project.rooms:
            if not room.model_resref:
                issues.append(KMapValidationIssue("Warning", "MISSING_ROOM_MODEL", f"Room '{room.name}' has no model resref.", room.room_id, "Assign a room MDL/model resref."))
            if not room.lyt_entry:
                issues.append(KMapValidationIssue("Info", "MISSING_LYT_DATA", f"Room '{room.name}' has no LYT entry metadata.", room.room_id))
            if room.room_id not in room_ids_with_wok:
                issues.append(KMapValidationIssue("Warning", "ROOM_WITHOUT_WALKMESH", f"Room '{room.name}' has no associated WOK walkmesh.", room.room_id))
            if not self._valid_transform(room.transform):
                issues.append(KMapValidationIssue("Error", "INVALID_TRANSFORM", f"Room '{room.name}' has invalid transform values.", room.room_id))
            for tex_id in room.texture_refs:
                if not any(texture.texture_id == tex_id for texture in project.textures):
                    issues.append(KMapValidationIssue("Warning", "MISSING_TEXTURE", f"Room '{room.name}' references missing texture {tex_id}.", room.room_id))
            for lightmap_id in room.lightmap_refs:
                if not any(texture.texture_id == lightmap_id or texture.resref == lightmap_id for texture in project.textures):
                    issues.append(KMapValidationIssue("Warning", "MISSING_LIGHTMAP", f"Room '{room.name}' references missing lightmap {lightmap_id}.", room.room_id))
        for wok in project.walkmeshes:
            if wok.room_id and project.find_room(wok.room_id) is None:
                issues.append(KMapValidationIssue("Error", "WALKMESH_WITHOUT_ROOM", f"Walkmesh {wok.wok_id} references missing room {wok.room_id}.", wok.wok_id))
            if wok.source_path and not Path(wok.source_path).exists():
                issues.append(KMapValidationIssue("Warning", "MISSING_WOK", f"Walkmesh source file is missing: {wok.source_path}", wok.wok_id))
        for blueprint in project.blueprints:
            if not blueprint.template_resref:
                issues.append(KMapValidationIssue("Info", "BLUEPRINT_TEMPLATE_MISSING", f"Blueprint '{blueprint.name}' has no template resref yet.", blueprint.blueprint_id))
        return issues

    def validate_file_version(self, version: int) -> list[KMapValidationIssue]:
        if int(version) > KMAP_FILE_VERSION:
            return [
                KMapValidationIssue(
                    "Error",
                    "INVALID_KMAP_VERSION",
                    f"KMAP file version {version} is newer than supported version {KMAP_FILE_VERSION}.",
                )
            ]
        return []

    def _duplicate_ids(self, project: KMapProject) -> list[KMapValidationIssue]:
        ids: list[tuple[str, str]] = [(project.project_id, "project")]
        ids.extend((module.module_id, "module") for module in project.modules)
        ids.extend((room.room_id, "room") for room in project.rooms)
        ids.extend((wok.wok_id, "walkmesh") for wok in project.walkmeshes)
        ids.extend((blueprint.blueprint_id, "blueprint") for blueprint in project.blueprints)
        seen: set[str] = set()
        issues: list[KMapValidationIssue] = []
        for item_id, kind in ids:
            if not item_id:
                issues.append(KMapValidationIssue("Error", "MISSING_ID", f"A {kind} entry has no stable ID."))
                continue
            if item_id in seen:
                issues.append(KMapValidationIssue("Error", "DUPLICATE_ID", f"Duplicate KMAP ID: {item_id}", item_id, "Regenerate one of the duplicate IDs."))
            seen.add(item_id)
        return issues

    @staticmethod
    def _valid_transform(transform: LevelTransform) -> bool:
        values: Iterable[float] = (*transform.position, *transform.rotation, *transform.scale)
        return all(math.isfinite(float(value)) for value in values) and all(abs(float(value)) > 1e-9 for value in transform.scale)
