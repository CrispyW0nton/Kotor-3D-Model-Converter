"""Atomic file repository for Custom Head Builder projects.

Core Project owns persistence, path relocation, schema migration, and
concurrent-save policy.  The domain object in
``src.core.characters.head_builder_project`` remains filesystem-free.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from src.core.characters.head_builder_project import (
    HEAD_BUILDER_PROJECT_EXTENSION,
    HEAD_BUILDER_PROJECT_SCHEMA,
    HEAD_BUILDER_PROJECT_VERSION,
    HeadBuilderProject,
)


MAX_HEAD_BUILDER_PROJECT_BYTES = 16 * 1024 * 1024


class HeadBuilderProjectRepositoryError(RuntimeError):
    """Base error for project-file operations."""


class HeadBuilderProjectConflictError(HeadBuilderProjectRepositoryError):
    """Raised when a save would overwrite externally changed content."""


class HeadBuilderProjectFormatError(HeadBuilderProjectRepositoryError):
    """Raised when a project file is malformed or unsupported."""


@dataclass(slots=True)
class HeadBuilderProjectDocument:
    """Open repository document plus its optimistic-concurrency revision."""

    project: HeadBuilderProject
    path: Path
    source_sha256: str = ""
    migrated_from_version: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.project, HeadBuilderProject):
            raise TypeError("project must be a HeadBuilderProject")
        self.path = Path(self.path)
        self.source_sha256 = str(self.source_sha256 or "").lower()


def migrate_head_builder_project_payload(
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], int | None]:
    """Return a current-schema payload and the migrated source version.

    Version ``0`` was the architecture-draft shape used before the v1 domain
    contract landed. Version ``2`` adds the durable appearance/component
    recipe. Supporting both migrations here keeps persistence policy in Core
    Project while leaving the domain model strict.
    """

    data = deepcopy(dict(payload))
    schema = str(data.get("schema") or "")
    if schema != HEAD_BUILDER_PROJECT_SCHEMA:
        raise HeadBuilderProjectFormatError(
            f"Unsupported Head Builder project schema: {schema!r}"
        )
    try:
        version = int(data.get("version"))
    except (TypeError, ValueError) as exc:
        raise HeadBuilderProjectFormatError(
            "Head Builder project version must be an integer"
        ) from exc
    if version > HEAD_BUILDER_PROJECT_VERSION:
        raise HeadBuilderProjectFormatError(
            "This Head Builder project was written by a newer Ghost Studio "
            f"version (project v{version}, supported v{HEAD_BUILDER_PROJECT_VERSION})."
        )
    if version < 0:
        raise HeadBuilderProjectFormatError(
            f"Unsupported Head Builder project version: {version}"
        )

    migrated_from: int | None = None
    if version == 0:
        migrated_from = 0
        baseline = HeadBuilderProject.new(
            display_name=str(
                data.get("display_name")
                or data.get("project_name")
                or "Untitled Head"
            ),
        ).to_dict()
        baseline.update(data)
        baseline["schema"] = HEAD_BUILDER_PROJECT_SCHEMA
        baseline["version"] = 1
        baseline["display_name"] = str(
            data.get("display_name")
            or data.get("project_name")
            or baseline["display_name"]
        )
        baseline["game"] = str(
            data.get("game")
            or data.get("target_game")
            or baseline["game"]
        ).upper()
        baseline["resource_view"] = str(
            data.get("resource_view")
            or data.get("resource_policy")
            or baseline["resource_view"]
        ).lower()
        if "workflow" not in data and "steps" in data:
            baseline["workflow"] = {
                "current_step": int(data.get("current_step") or 1),
                "steps": deepcopy(dict(data.get("steps") or {})),
            }
        for legacy_key in (
            "project_name",
            "target_game",
            "resource_policy",
            "steps",
            "current_step",
        ):
            baseline.pop(legacy_key, None)
        data = baseline
        version = 1

    if version == 1:
        if migrated_from is None:
            migrated_from = 1
        data.setdefault("appearance_customization", {})
        data["version"] = 2
        version = 2

    if version != HEAD_BUILDER_PROJECT_VERSION:
        raise HeadBuilderProjectFormatError(
            f"No migration path exists for Head Builder project v{version}"
        )
    return data, migrated_from


class FileHeadBuilderProjectRepository:
    """JSON repository with atomic replace and revision conflict checks."""

    def __init__(self, *, maximum_bytes: int = MAX_HEAD_BUILDER_PROJECT_BYTES):
        self.maximum_bytes = max(1024, int(maximum_bytes))

    def new_document(
        self,
        project: HeadBuilderProject,
        path: str | Path,
    ) -> HeadBuilderProjectDocument:
        target = _validate_project_path(path)
        return HeadBuilderProjectDocument(project=project, path=target)

    def load(self, path: str | Path) -> HeadBuilderProjectDocument:
        target = _validate_project_path(path)
        try:
            size = target.stat().st_size
        except FileNotFoundError as exc:
            raise HeadBuilderProjectRepositoryError(
                f"Head Builder project does not exist: {target}"
            ) from exc
        if not target.is_file():
            raise HeadBuilderProjectRepositoryError(
                f"Head Builder project is not a file: {target}"
            )
        if size > self.maximum_bytes:
            raise HeadBuilderProjectFormatError(
                f"Head Builder project exceeds {self.maximum_bytes} bytes"
            )
        try:
            raw_bytes = target.read_bytes()
        except OSError as exc:
            raise HeadBuilderProjectRepositoryError(
                f"Unable to read Head Builder project: {target}"
            ) from exc
        payload = _decode_project_json(raw_bytes)
        migrated, migrated_from = migrate_head_builder_project_payload(payload)
        relocated = _resolve_portable_paths(migrated, target.parent)
        try:
            project = HeadBuilderProject.from_dict(relocated)
        except (TypeError, ValueError) as exc:
            raise HeadBuilderProjectFormatError(
                f"Invalid Head Builder project contract: {exc}"
            ) from exc
        return HeadBuilderProjectDocument(
            project=project,
            path=target.resolve(),
            source_sha256=_sha256(raw_bytes),
            migrated_from_version=migrated_from,
        )

    def save(
        self,
        document: HeadBuilderProjectDocument,
        path: str | Path | None = None,
        *,
        force: bool = False,
    ) -> HeadBuilderProjectDocument:
        if not isinstance(document, HeadBuilderProjectDocument):
            raise TypeError("save expects HeadBuilderProjectDocument")
        target = _validate_project_path(path or document.path)
        same_target = _same_path(target, document.path)
        if (
            same_target
            and document.source_sha256
            and not target.exists()
            and not force
        ):
            raise HeadBuilderProjectConflictError(
                "Head Builder project was deleted after it was opened; "
                "use Save As or explicitly force recreation."
            )
        if target.exists() and not force:
            current_hash = _sha256(_read_bounded(target, self.maximum_bytes))
            expected_hash = document.source_sha256 if same_target else ""
            if not expected_hash:
                raise HeadBuilderProjectConflictError(
                    f"Refusing to overwrite an existing project without its revision: {target}"
                )
            if current_hash != expected_hash:
                raise HeadBuilderProjectConflictError(
                    "Head Builder project changed on disk after it was opened; "
                    "reload it or use an explicit Save As destination."
                )

        target.parent.mkdir(parents=True, exist_ok=True)
        old_updated_at = document.project.updated_at
        saved_at = datetime.now(timezone.utc).isoformat()
        document.project.updated_at = saved_at
        try:
            payload = document.project.to_dict()
            payload["updated_at"] = saved_at
            portable = _make_paths_portable(payload, target.parent)
            encoded = _encode_project_json(portable)
            if len(encoded) > self.maximum_bytes:
                raise HeadBuilderProjectFormatError(
                    f"Head Builder project exceeds {self.maximum_bytes} bytes"
                )
            _atomic_replace(target, encoded)
        except Exception:
            document.project.updated_at = old_updated_at
            raise

        document.path = target.resolve()
        document.source_sha256 = _sha256(encoded)
        document.migrated_from_version = None
        return document


def _validate_project_path(path: str | Path) -> Path:
    target = Path(path).expanduser()
    if not str(target):
        raise HeadBuilderProjectRepositoryError("Head Builder project path is blank")
    if not target.name.lower().endswith(HEAD_BUILDER_PROJECT_EXTENSION):
        raise HeadBuilderProjectRepositoryError(
            "Head Builder projects must use the "
            f"{HEAD_BUILDER_PROJECT_EXTENSION} extension"
        )
    return target


def _decode_project_json(raw_bytes: bytes) -> dict[str, Any]:
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HeadBuilderProjectFormatError(
            "Head Builder projects must be UTF-8 JSON"
        ) from exc

    def reject_duplicate_keys(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise HeadBuilderProjectFormatError(
                    f"Duplicate JSON key in Head Builder project: {key!r}"
                )
            result[key] = value
        return result

    try:
        payload = json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=lambda value: _reject_json_constant(value),
        )
    except HeadBuilderProjectFormatError:
        raise
    except json.JSONDecodeError as exc:
        raise HeadBuilderProjectFormatError(
            f"Malformed Head Builder project JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(payload, dict):
        raise HeadBuilderProjectFormatError(
            "Head Builder project root must be a JSON object"
        )
    return payload


def _encode_project_json(payload: Mapping[str, Any]) -> bytes:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    return (text + "\n").encode("utf-8")


def _reject_json_constant(value: str) -> Any:
    raise HeadBuilderProjectFormatError(
        f"Non-finite JSON number is not allowed: {value}"
    )


def _atomic_replace(target: Path, data: bytes) -> None:
    temporary = target.with_name(
        f".{target.name}.{os.getpid()}.{uuid4().hex}.tmp"
    )
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _read_bounded(path: Path, maximum_bytes: int) -> bytes:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise HeadBuilderProjectRepositoryError(
            f"Unable to inspect Head Builder project: {path}"
        ) from exc
    if size > maximum_bytes:
        raise HeadBuilderProjectFormatError(
            f"Head Builder project exceeds {maximum_bytes} bytes"
        )
    try:
        return path.read_bytes()
    except OSError as exc:
        raise HeadBuilderProjectRepositoryError(
            f"Unable to read Head Builder project: {path}"
        ) from exc


def _make_paths_portable(value: Any, project_dir: Path, key: str = "") -> Any:
    if isinstance(value, Mapping):
        return {
            str(child_key): _make_paths_portable(
                child_value,
                project_dir,
                str(child_key),
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [
            _make_paths_portable(item, project_dir, key)
            for item in value
        ]
    if isinstance(value, str) and _is_relocatable_path_key(key):
        return _portable_path(value, project_dir)
    return deepcopy(value)


def _resolve_portable_paths(value: Any, project_dir: Path, key: str = "") -> Any:
    if isinstance(value, Mapping):
        return {
            str(child_key): _resolve_portable_paths(
                child_value,
                project_dir,
                str(child_key),
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [
            _resolve_portable_paths(item, project_dir, key)
            for item in value
        ]
    if (
        isinstance(value, str)
        and _is_relocatable_path_key(key)
        and value.replace("\\", "/").startswith("./")
    ):
        relative = value.replace("\\", "/")[2:]
        return str((project_dir / relative).resolve())
    return deepcopy(value)


def _is_relocatable_path_key(key: str) -> bool:
    normalized = str(key or "").strip().lower()
    if normalized == "game_install_dir":
        return False
    return (
        normalized in {
            "path",
            "source_path",
            "output_path",
            "backup_path",
            "install_path",
            "manifest_path",
            "artifact_paths",
        }
        or normalized.endswith("_path")
        or normalized.endswith("_dir")
    )


def _portable_path(value: str, project_dir: Path) -> str:
    text = str(value or "")
    if not text:
        return text
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        return text.replace("\\", "/")
    try:
        relative = candidate.resolve().relative_to(project_dir.resolve())
    except (OSError, ValueError):
        return text
    if str(relative) == ".":
        return "./"
    return "./" + relative.as_posix()


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return os.path.abspath(left) == os.path.abspath(right)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


__all__ = [
    "FileHeadBuilderProjectRepository",
    "HeadBuilderProjectConflictError",
    "HeadBuilderProjectDocument",
    "HeadBuilderProjectFormatError",
    "HeadBuilderProjectRepositoryError",
    "MAX_HEAD_BUILDER_PROJECT_BYTES",
    "migrate_head_builder_project_payload",
]
