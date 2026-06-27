"""Validation for GhostRigger KMAP projects."""

from __future__ import annotations

import math
import re
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
        issues.extend(self._validate_resrefs(project))
        issues.extend(self._validate_walkmesh_faces(project))
        issues.extend(self._validate_transition_targets(project))
        issues.extend(self._validate_texture_formats(project))
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

    # ── KOTOR resref / walkmesh / transition / texture hardening (#7) ──────

    #: Fields a placed-object dict may carry that hold a transition target
    #: (destination module resref) under the KOTOR GIT door/trigger schema.
    _TRANSITION_FIELDS: tuple[str, ...] = (
        "LinkedTo",
        "LinkedToModule",
        "TargetModule",
        "TransitionTarget",
        "transition_target",
        "linked_to",
        "linked_to_module",
    )

    #: Image suffixes that must NOT appear inside a KOTOR texture resref.
    _TEXTURE_EXTENSIONS: tuple[str, ...] = (
        ".tga", ".tpc", ".dds", ".png", ".bmp",
        ".jpg", ".jpeg", ".tif", ".tiff", ".txi",
    )

    def _validate_resref(self, resref: str, context: str, item_id: str = "") -> list[KMapValidationIssue]:
        """Validate a KOTOR resref: lowercase, <=16 chars, ``[a-z0-9_]`` only."""
        issues: list[KMapValidationIssue] = []
        if not resref:
            return issues
        if len(resref) > 16:
            issues.append(KMapValidationIssue(
                "Warning", "RESREF_TOO_LONG",
                f'Resref "{resref}" ({context}) exceeds the 16-character KOTOR limit.',
                item_id, "Shorten the resref to 16 characters or fewer."))
        if resref != resref.lower():
            issues.append(KMapValidationIssue(
                "Warning", "RESREF_CASE",
                f'Resref "{resref}" ({context}) should be lowercase.',
                item_id, "Convert the resref to lowercase."))
        if not re.match(r"^[a-z0-9_]+$", resref):
            issues.append(KMapValidationIssue(
                "Warning", "RESREF_INVALID_CHARS",
                f'Resref "{resref}" ({context}) contains invalid characters (allowed: a-z 0-9 _).',
                item_id, "Use only lowercase letters, digits, and underscores."))
        return issues

    def _validate_resrefs(self, project: KMapProject) -> list[KMapValidationIssue]:
        """Check every resref-bearing field: modules, room models, textures,
        blueprint templates, and placed-object resrefs."""
        issues: list[KMapValidationIssue] = []
        for module in project.modules:
            issues.extend(self._validate_resref(
                module.module_name, f"module '{module.module_name}'", module.module_id))
        for room in project.rooms:
            issues.extend(self._validate_resref(
                room.model_resref, f"room '{room.name}' model resref", room.room_id))
        for blueprint in project.blueprints:
            issues.extend(self._validate_resref(
                blueprint.template_resref,
                f"blueprint '{blueprint.name}' template resref",
                blueprint.blueprint_id))
        for texture in project.textures:
            issues.extend(self._validate_resref(
                texture.resref, "texture resref", texture.texture_id))
        for index, obj in enumerate(project.objects, start=1):
            if not isinstance(obj, dict):
                continue
            obj_resref = str(obj.get("resref") or obj.get("ResRef") or obj.get("TemplateResref") or "")
            if obj_resref:
                issues.extend(self._validate_resref(
                    obj_resref, f"placed object #{index} resref",
                    str(obj.get("id") or "")))
        return issues

    def _validate_walkmesh_faces(self, project: KMapProject) -> list[KMapValidationIssue]:
        """Walkable-face sanity: flag walkmeshes that report no faces (the
        zero-area/degenerate proxy at the KMAP summary level) and rooms that
        have a walkmesh but no walkable faces. KMAP deliberately omits raw
        vertex data, so true per-face area cannot be measured here; an empty
        or zero-total ``face_types`` set is the actionable degenerate signal."""
        issues: list[KMapValidationIssue] = []
        for wok in project.walkmeshes:
            face_types = wok.face_types or {}
            total_faces = sum(int(count or 0) for count in face_types.values())
            if wok.source_path and not face_types:
                issues.append(KMapValidationIssue(
                    "Warning", "DEGENERATE_WALKMESH",
                    f"Walkmesh {wok.wok_id} has a source but reports no faces (zero-area / empty).",
                    wok.wok_id, "Regenerate the WOK so it exports at least one face."))
            elif face_types and total_faces <= 0:
                issues.append(KMapValidationIssue(
                    "Warning", "DEGENERATE_WALKMESH",
                    f"Walkmesh {wok.wok_id} reports zero total faces.",
                    wok.wok_id, "Regenerate the WOK so it exports walkable geometry."))
        for room in project.rooms:
            room_woks = [wok for wok in project.walkmeshes if wok.room_id == room.room_id]
            if not room_woks:
                continue  # already covered by ROOM_WITHOUT_WALKMESH
            walkable_faces = sum(
                sum(int(count or 0) for count in (wok.face_types or {}).values())
                for wok in room_woks
            )
            if walkable_faces <= 0:
                issues.append(KMapValidationIssue(
                    "Warning", "ROOM_WITHOUT_WALKABLE_FACE",
                    f"Room '{room.name}' has a walkmesh but no walkable faces.",
                    room.room_id, "Author at least one walkable floor face in the room's WOK."))
        return issues

    def _validate_transition_targets(self, project: KMapProject) -> list[KMapValidationIssue]:
        """Check door/trigger transition targets are well-formed resrefs and,
        when this project defines modules, that the referenced module exists
        locally (external cross-module links are flagged Info, not errors)."""
        issues: list[KMapValidationIssue] = []
        module_names = {module.module_name.lower() for module in project.modules if module.module_name}
        has_modules = bool(module_names)
        for index, obj in enumerate(project.objects, start=1):
            if not isinstance(obj, dict):
                continue
            item_id = str(obj.get("id") or obj.get("resref") or f"object_{index}")
            for field in self._TRANSITION_FIELDS:
                target = obj.get(field)
                if target is None:
                    continue
                target = str(target).strip()
                if not target:
                    continue
                issues.extend(self._validate_resref(
                    target, f"object #{index} transition target ({field})", item_id))
                if has_modules and target.lower() not in module_names:
                    issues.append(KMapValidationIssue(
                        "Info", "TRANSITION_TARGET_UNKNOWN_MODULE",
                        f'Transition target "{target}" ({field}) on object #{index} does not match a module in this project.',
                        item_id, "Leave as-is if it links to an external module; otherwise fix the target resref."))
        return issues

    def _validate_texture_formats(self, project: KMapProject) -> list[KMapValidationIssue]:
        """Check texture resrefs do not include a file extension (KOTOR
        resolves TGA/TPC by resref without an extension)."""
        issues: list[KMapValidationIssue] = []
        for texture in project.textures:
            resref = (texture.resref or "").strip()
            if not resref:
                continue
            lowered = resref.lower()
            for ext in self._TEXTURE_EXTENSIONS:
                if lowered.endswith(ext):
                    issues.append(KMapValidationIssue(
                        "Warning", "TEXTURE_RESREF_HAS_EXTENSION",
                        f'Texture resref "{resref}" includes a file extension; KOTOR resrefs omit extensions.',
                        texture.texture_id, f'Remove the "{ext}" suffix from the resref.'))
                    break
        return issues
