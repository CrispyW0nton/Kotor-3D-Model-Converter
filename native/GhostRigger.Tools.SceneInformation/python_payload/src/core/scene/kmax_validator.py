"""Validation for GhostRigger KMAX scene files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .kmax_scene import KMAX_FILE_TYPE, KMAX_FILE_VERSION


@dataclass
class KMaxValidationResult:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.ok = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


class KMaxValidator:
    @staticmethod
    def validate(data: dict[str, Any]) -> KMaxValidationResult:
        result = KMaxValidationResult()
        if not isinstance(data, dict):
            result.add_error("KMAX payload must be a JSON object.")
            return result
        if data.get("file_type") != KMAX_FILE_TYPE:
            result.add_error("Invalid KMAX file_type.")
        version = int(data.get("file_version") or 0)
        if version <= 0:
            result.add_error("Missing or invalid KMAX file_version.")
        elif version > KMAX_FILE_VERSION:
            result.add_warning(f"Unsupported future KMAX file_version: {version}.")
        if not isinstance(data.get("scene"), dict):
            result.add_error("Missing scene block.")
        object_ids: set[str] = set()
        for obj in data.get("objects") or []:
            if not isinstance(obj, dict):
                result.add_warning("Ignoring non-object entry in objects.")
                continue
            object_id = str(obj.get("id") or "")
            if not object_id:
                result.add_warning("Scene object is missing a stable id.")
            elif object_id in object_ids:
                result.add_warning(f"Duplicate object id: {object_id}.")
            object_ids.add(object_id)
            transform = obj.get("transform") or {}
            for key in ("position", "rotation", "scale"):
                values = transform.get(key)
                if not isinstance(values, list) or len(values) != 3:
                    result.add_warning(f"Object {object_id or '<unknown>'} has invalid {key}.")
            pivot = obj.get("pivot")
            if pivot is not None:
                if not isinstance(pivot, dict):
                    result.add_warning(f"Object {object_id or '<unknown>'} has invalid pivot block.")
                else:
                    for key in ("position_local", "rotation_local"):
                        values = pivot.get(key, pivot.get(key.replace("_local", "")))
                        if not isinstance(values, list) or len(values) != 3:
                            result.add_warning(f"Object {object_id or '<unknown>'} has invalid pivot {key}.")
            source_ref = obj.get("source_ref") or {}
            if obj.get("object_type", "model") == "model":
                if not source_ref.get("resref") and not source_ref.get("source_path"):
                    result.add_warning(f"Model object {object_id or '<unknown>'} has no source reference.")
                source_path = str(source_ref.get("source_path") or "")
                if source_path and not Path(source_path).expanduser().exists():
                    result.add_warning(f"Missing model source: {source_path}.")
        return result
