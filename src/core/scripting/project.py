"""Portable project, inventory, recent-project, and revision contracts.

This module is intentionally Qt-free.  A narrative project is represented by a
small, versioned JSON manifest whose asset paths are relative to the project
root.  Project files contain references and fingerprints, never embedded game
resource blobs.  Revision snapshots are project-local, immutable copies that
can only be materialized into a new folder; they never overwrite the live
project.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4


PROJECT_FILE_TYPE = "GhostStudioNarrativeProject"
PROJECT_SCHEMA_VERSION = 1
PROJECT_FILE_NAME = "ghoststudio-narrative.json"
RECENT_FILE_TYPE = "GhostStudioRecentNarrativeProjects"
REVISION_FILE_TYPE = "GhostStudioNarrativeRevision"
EXPORT_HISTORY_FILE_TYPE = "GhostStudioNarrativeExportHistory"
REVISION_ASSET_RECOVERY_FILE_TYPE = "GhostStudioNarrativeRevisionAssetRecovery"
LEGACY_HISTORY_FILE_TYPE = "GhostStudioLegacyGhostScripterHistory"
LEGACY_HISTORY_SCHEMA_VERSION = 1
LEGACY_HISTORY_RECOVERY_FILE_TYPE = "GhostStudioLegacyGhostScripterHistoryRecovery"

_RESREF_PATTERN = re.compile(r"^[a-z0-9_]{1,16}$")
_REVISION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,96}$")
_STANDARD_DIRECTORIES = (
    "scripts",
    "dialogues",
    "quests",
    "journals",
    "tables",
    "blueprints",
    "assets",
)
_GFF_BLUEPRINT_TYPES = {"utc", "uti", "utp", "utd", "ute", "utm", "uts", "utt", "utw"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _game_key(value: object) -> str:
    game = str(value or "K2").strip().upper()
    if game in {"K1", "1", "KOTOR", "KOTOR1"}:
        return "K1"
    if game in {"K2", "2", "TSL", "KOTOR2"}:
        return "K2"
    raise ValueError("Target game must be K1 or K2.")


def _resource_type(extension: object):
    from pykotor.resource.type import ResourceType

    value = str(extension or "").strip().lower().lstrip(".")
    resource_type = ResourceType.from_extension(value)
    if int(resource_type.type_id) < 0 or not value:
        raise ValueError(f"Unknown KOTOR resource type: {value or '<empty>'}")
    return resource_type


def _validated_resref(value: object) -> str:
    resref = str(value or "").strip().lower()
    if not _RESREF_PATTERN.fullmatch(resref):
        raise ValueError("Resource identifiers must use 1-16 lowercase letters, numbers, or underscores.")
    return resref


def _portable_relative_path(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or re.match(r"^[A-Za-z]:", text):
        raise ValueError("Project asset paths must be non-empty relative paths.")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Project asset paths cannot escape the project root.")
    return path.as_posix()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(bytes(data))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write(path, (json.dumps(payload, indent=2, sort_keys=False) + "\n").encode("utf-8"))


def _safe_recovery_stem(value: object, fallback: str) -> str:
    """Return a portable filename stem without changing the archived identity."""

    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip()).strip("._")
    return (text or fallback)[:96]


def _project_asset_path(project: "NarrativeProject", relative_path: object, *, require_file: bool = False) -> Path:
    relative = _portable_relative_path(relative_path)
    root = Path(project.root_path).resolve()
    lexical = root / Path(*PurePosixPath(relative).parts)
    candidate = lexical.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("Project asset path resolves outside the project root.") from error
    if require_file and (not candidate.is_file() or lexical.is_symlink()):
        raise ValueError(f"Tracked project asset is missing or unsafe: {relative}")
    return candidate


@dataclass(frozen=True)
class NarrativeAssetDependency:
    """A typed resource reference made by one project asset."""

    resref: str
    restype: str
    relation: str = "references"
    required: bool = True
    scope: str = "project"

    def __post_init__(self) -> None:
        object.__setattr__(self, "resref", _validated_resref(self.resref))
        object.__setattr__(self, "restype", _resource_type(self.restype).extension.lower())
        relation = str(self.relation or "references").strip().lower().replace(" ", "_")
        object.__setattr__(self, "relation", relation or "references")
        scope = str(self.scope or "project").strip().lower()
        if scope not in {"project", "game", "external"}:
            raise ValueError("Dependency scope must be project, game, or external.")
        object.__setattr__(self, "scope", scope)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resref": self.resref,
            "restype": self.restype,
            "relation": self.relation,
            "required": bool(self.required),
            "scope": self.scope,
        }

    @property
    def identity(self) -> tuple[str, str]:
        return self.resref, self.restype

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NarrativeAssetDependency":
        return cls(
            resref=payload.get("resref", ""),
            restype=payload.get("restype", ""),
            relation=payload.get("relation", "references"),
            required=bool(payload.get("required", True)),
            scope=payload.get("scope", "project"),
        )


@dataclass
class NarrativeAssetRecord:
    """One portable, typed project resource entry."""

    asset_id: str
    resref: str
    restype: str
    path: str
    role: str = "runtime"
    dependencies: tuple[NarrativeAssetDependency, ...] = ()
    sha256: str = ""
    byte_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.asset_id = str(self.asset_id or f"asset_{uuid4().hex}")
        self.resref = _validated_resref(self.resref)
        self.restype = _resource_type(self.restype).extension.lower()
        self.path = _portable_relative_path(self.path)
        self.role = str(self.role or "runtime").strip().lower().replace(" ", "_") or "runtime"
        self.dependencies = tuple(
            row if isinstance(row, NarrativeAssetDependency) else NarrativeAssetDependency.from_dict(row)
            for row in self.dependencies
        )
        self.sha256 = str(self.sha256 or "").strip().lower()
        self.byte_count = max(0, int(self.byte_count or 0))
        self.metadata = dict(self.metadata or {})

    @property
    def filename(self) -> str:
        return f"{self.resref}.{self.restype}"

    @property
    def identity(self) -> tuple[str, str]:
        return self.resref, self.restype

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "resref": self.resref,
            "restype": self.restype,
            "path": self.path,
            "role": self.role,
            "dependencies": [row.to_dict() for row in self.dependencies],
            "sha256": self.sha256,
            "byte_count": self.byte_count,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NarrativeAssetRecord":
        return cls(
            asset_id=payload.get("asset_id", ""),
            resref=payload.get("resref", ""),
            restype=payload.get("restype", ""),
            path=payload.get("path", ""),
            role=payload.get("role", "runtime"),
            dependencies=tuple(payload.get("dependencies", ()) or ()),
            sha256=payload.get("sha256", ""),
            byte_count=payload.get("byte_count", 0),
            metadata=dict(payload.get("metadata", {}) or {}),
        )


@dataclass(frozen=True)
class NarrativeProjectIssue:
    severity: str
    code: str
    message: str
    asset_id: str = ""

    @property
    def blocking(self) -> bool:
        return self.severity.lower() in {"blocking", "error"}


@dataclass(frozen=True)
class LegacyNarrativeProjectImportResult:
    """Result of a non-destructive GhostScripter project migration."""

    project: "NarrativeProject"
    source_manifest: str
    imported_resources: tuple[str, ...]
    preserved_files: int
    history_rows: int
    preference_rows: int = 0
    recent_project_rows: int = 0
    warnings: tuple[str, ...] = ()


@dataclass
class NarrativeProject:
    project_id: str
    name: str
    game: str
    root_path: str
    manifest_path: str
    assets: list[NarrativeAssetRecord] = field(default_factory=list)
    revision: int = 1
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.project_id = str(self.project_id or f"narrative_{uuid4().hex}")
        self.name = str(self.name or "Untitled Narrative Project").strip() or "Untitled Narrative Project"
        self.game = _game_key(self.game)
        self.root_path = str(Path(self.root_path).resolve())
        self.manifest_path = str(Path(self.manifest_path).resolve())
        self.assets = [
            row if isinstance(row, NarrativeAssetRecord) else NarrativeAssetRecord.from_dict(row)
            for row in self.assets
        ]
        self.revision = max(1, int(self.revision or 1))
        self.metadata = dict(self.metadata or {})
        self.extensions = dict(self.extensions or {})

    def asset_by_id(self, asset_id: str) -> NarrativeAssetRecord | None:
        return next((row for row in self.assets if row.asset_id == str(asset_id)), None)

    def asset_by_identity(self, resref: str, restype: str) -> NarrativeAssetRecord | None:
        identity = (_validated_resref(resref), _resource_type(restype).extension.lower())
        return next((row for row in self.assets if row.identity == identity), None)

    def to_dict(self, *, revision: int | None = None, updated_at: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "file_type": PROJECT_FILE_TYPE,
            "schema_version": PROJECT_SCHEMA_VERSION,
            "project_id": self.project_id,
            "name": self.name,
            "game": self.game,
            "revision": int(self.revision if revision is None else revision),
            "created_at": self.created_at,
            "updated_at": self.updated_at if updated_at is None else updated_at,
            "assets": [row.to_dict() for row in self.assets],
            "metadata": dict(self.metadata),
        }
        for key, value in self.extensions.items():
            if key not in payload:
                payload[key] = value
        return payload


def _project_from_payload(payload: dict[str, Any], manifest_path: Path) -> NarrativeProject:
    if payload.get("file_type") != PROJECT_FILE_TYPE:
        raise ValueError("This is not a GhostStudio narrative project manifest.")
    version = int(payload.get("schema_version", 0) or 0)
    if version != PROJECT_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported narrative project schema {version}; this build supports {PROJECT_SCHEMA_VERSION}."
        )
    known = {
        "file_type",
        "schema_version",
        "project_id",
        "name",
        "game",
        "revision",
        "created_at",
        "updated_at",
        "assets",
        "metadata",
    }
    return NarrativeProject(
        project_id=payload.get("project_id", ""),
        name=payload.get("name", ""),
        game=payload.get("game", "K2"),
        root_path=str(manifest_path.parent),
        manifest_path=str(manifest_path),
        assets=list(payload.get("assets", ()) or ()),
        revision=payload.get("revision", 1),
        created_at=str(payload.get("created_at", "") or _utc_now()),
        updated_at=str(payload.get("updated_at", "") or _utc_now()),
        metadata=dict(payload.get("metadata", {}) or {}),
        extensions={key: value for key, value in payload.items() if key not in known},
    )


@dataclass(frozen=True)
class LegacyNarrativeHistoryRecord:
    """One immutable, recoverable record from a migrated GhostScripter project."""

    record_id: str
    kind: str
    identity: str
    created_at: str
    revision: int
    summary: str
    content: str
    content_source: str
    suggested_filename: str
    source_table: str
    source_row_index: int
    source_row: dict[str, Any]

    @property
    def byte_count(self) -> int:
        return len(self.content.encode("utf-8"))

    @property
    def sha256(self) -> str:
        return _sha256(self.content.encode("utf-8"))

    def to_dict(self, *, include_content: bool = True) -> dict[str, Any]:
        source_row = dict(self.source_row)
        if not include_content:
            for key in ("content", "source", "script_text", "data_json", "snapshot", "json_data"):
                value = source_row.get(key)
                if isinstance(value, str):
                    source_row[key] = f"<preserved by recovery service; {len(value)} character(s)>"
        payload = {
            "record_id": self.record_id,
            "kind": self.kind,
            "identity": self.identity,
            "created_at": self.created_at,
            "revision": self.revision,
            "summary": self.summary,
            "content_source": self.content_source,
            "suggested_filename": self.suggested_filename,
            "source_table": self.source_table,
            "source_row_index": self.source_row_index,
            "source_row": source_row,
            "byte_count": self.byte_count,
            "sha256": self.sha256,
        }
        if include_content:
            payload["content"] = self.content
        else:
            payload["content_preview"] = self.content[:4000]
            payload["content_truncated"] = len(self.content) > 4000
            payload["character_count"] = len(self.content)
        return payload


class LegacyNarrativeHistoryStore:
    """Read and recover preserved GhostScripter history without editing it.

    Migration keeps the exact database rows, original project tree, and
    read-only settings archive.  This service makes the authoring snapshots,
    project quest artifacts, metadata, 2DA plans, dependencies, preferences,
    and recent-project rows browseable.  Recovery always commits into a new
    folder with a fingerprinted provenance manifest; neither the archive nor
    the open project is modified.
    """

    _TABLE_CONTRACTS: dict[str, dict[str, tuple[str, ...] | str]] = {
        "script_history": {
            "kind": "script",
            "identity": ("script_name", "resref", "name"),
            "content": ("content", "source", "script_text"),
            "created": ("saved_at", "created_at", "updated_at"),
            "revision": ("revision", "version"),
        },
        "quest_snapshots": {
            "kind": "quest",
            "identity": ("quest_id", "quest_name", "name", "resref"),
            "content": ("data_json", "content", "snapshot", "json_data"),
            "created": ("saved_at", "created_at", "updated_at"),
            "revision": ("revision", "version"),
        },
        "dialogue_snapshots": {
            "kind": "dialogue",
            "identity": ("dlg_name", "dialogue_name", "resref", "name"),
            "content": ("data_json", "content", "snapshot", "json_data"),
            "created": ("saved_at", "created_at", "updated_at"),
            "revision": ("revision", "version"),
        },
    }

    def __init__(self, project: NarrativeProject) -> None:
        self.project = project
        self.path = Path(project.root_path).resolve() / "legacy_import" / "ghostscripter-history.json"

    @staticmethod
    def _first(row: Mapping[str, Any], keys: Sequence[str], default: object = "") -> object:
        for key in keys:
            if key in row and row.get(key) is not None:
                return row.get(key)
        return default

    def _payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "file_type": LEGACY_HISTORY_FILE_TYPE,
                "schema_version": LEGACY_HISTORY_SCHEMA_VERSION,
                "legacy_project_id": "",
                "rows": [],
            }
        if not self.path.is_file() or self.path.is_symlink():
            raise ValueError("Legacy GhostScripter history is missing or unsafe.")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("file_type") != LEGACY_HISTORY_FILE_TYPE:
            raise ValueError("Legacy GhostScripter history has the wrong file type.")
        if int(payload.get("schema_version", 0) or 0) != LEGACY_HISTORY_SCHEMA_VERSION:
            raise ValueError("Unsupported legacy GhostScripter history schema.")
        rows = payload.get("rows", ()) or ()
        if not isinstance(rows, list):
            raise ValueError("Legacy GhostScripter history rows must be a JSON list.")
        legacy_metadata = dict(self.project.metadata.get("legacy_ghostscripter", {}) or {})
        expected_owner = str(legacy_metadata.get("legacy_project_id") or "")
        actual_owner = str(payload.get("legacy_project_id") or "")
        if expected_owner and actual_owner and expected_owner != actual_owner:
            raise ValueError("Legacy GhostScripter history belongs to a different migrated project.")
        return payload

    @staticmethod
    def _content_text(value: object) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _archive_record(
        *,
        kind: str,
        identity: str,
        content: str,
        content_source: str,
        suggested_filename: str,
        source_table: str,
        source_row_index: int,
        source_row: Mapping[str, Any],
        created_at: str = "",
        revision: int = 0,
        summary: str = "",
    ) -> LegacyNarrativeHistoryRecord:
        canonical_source = json.dumps(
            dict(source_row), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        digest_seed = f"{source_table}\n{source_row_index}\n{canonical_source}\n{content}".encode("utf-8")
        record_id = f"legacy_{kind}_{source_row_index:06d}_{_sha256(digest_seed)[:12]}"
        return LegacyNarrativeHistoryRecord(
            record_id=record_id,
            kind=kind,
            identity=identity,
            created_at=created_at,
            revision=max(0, int(revision or 0)),
            summary=summary or f"Legacy {kind.replace('_', ' ')} record",
            content=content,
            content_source=content_source,
            suggested_filename=suggested_filename,
            source_table=source_table,
            source_row_index=source_row_index,
            source_row=dict(source_row),
        )

    def _append_preserved_project_records(self, records: list[LegacyNarrativeHistoryRecord]) -> None:
        legacy_root = Path(self.project.root_path).resolve() / "legacy_source"
        manifest_path = legacy_root / "project.json"
        if not manifest_path.exists():
            return
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise ValueError("Preserved GhostScripter project manifest is missing or unsafe.")
        manifest_text = manifest_path.read_text(encoding="utf-8")
        payload = json.loads(manifest_text)
        if not isinstance(payload, dict) or "target_game" not in payload:
            raise ValueError("Preserved GhostScripter project manifest is invalid.")
        identity = str(payload.get("name") or payload.get("project_id") or "GhostScripter project")
        records.append(
            self._archive_record(
                kind="legacy_project",
                identity=identity,
                content=manifest_text,
                content_source="legacy_source/project.json",
                suggested_filename="legacy-project.json",
                source_table="project_manifest",
                source_row_index=0,
                source_row=payload,
                created_at=str(payload.get("updated_at") or payload.get("created_at") or ""),
                summary="Exact preserved GhostScripter project manifest",
            )
        )

        raw_artifacts = payload.get("artifacts", {}) or {}
        artifacts = dict(raw_artifacts) if isinstance(raw_artifacts, Mapping) else {}
        for artifact_index, raw_artifact in enumerate(tuple(artifacts.get("quests", ()) or ())):
            artifact = dict(raw_artifact) if isinstance(raw_artifact, Mapping) else {"path": str(raw_artifact)}
            try:
                relative = _portable_relative_path(artifact.get("path", ""))
                source = (legacy_root / Path(*PurePosixPath(relative).parts)).resolve()
                source.relative_to(legacy_root.resolve())
                if not source.is_file() or source.is_symlink():
                    raise ValueError("missing or unsafe preserved file")
                content = source.read_text(encoding="utf-8")
            except (OSError, UnicodeError, ValueError):
                relative = str(artifact.get("path") or f"quest_{artifact_index + 1}.json")
                identity = str(
                    artifact.get("quest_id") or artifact.get("name") or PurePosixPath(relative).stem
                    or f"legacy_quest_{artifact_index + 1}"
                )
                content = json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
                records.append(
                    self._archive_record(
                        kind="quest_reference",
                        identity=identity,
                        content=content,
                        content_source="project.json:artifacts.quests",
                        suggested_filename=f"{_safe_recovery_stem(identity, 'legacy_quest')}.reference.json",
                        source_table="project_artifact_quests",
                        source_row_index=artifact_index,
                        source_row=artifact,
                        summary="Unresolved GhostScripter quest artifact reference (preserved for repair)",
                    )
                )
                continue
            try:
                quest_payload = json.loads(content)
            except json.JSONDecodeError:
                quest_payload = {}
            identity = str(
                (quest_payload.get("quest_id") if isinstance(quest_payload, Mapping) else "")
                or artifact.get("quest_id")
                or artifact.get("name")
                or PurePosixPath(relative).stem
            )
            stem = _safe_recovery_stem(identity, f"legacy_quest_{artifact_index + 1}")
            records.append(
                self._archive_record(
                    kind="quest",
                    identity=identity,
                    content=content,
                    content_source=f"legacy_source/{relative}",
                    suggested_filename=f"{stem}.quest.json",
                    source_table="project_artifact_quests",
                    source_row_index=artifact_index,
                    source_row=artifact,
                    summary="Preserved GhostScripter quest project artifact",
                )
            )

        for kind, key, filename, label in (
            ("twoda_edits", "twoda_edits", "legacy-2da-edits.json", "Preserved GhostScripter 2DA edit plan"),
            ("dependencies", "dependencies", "legacy-dependencies.json", "Preserved GhostScripter dependencies"),
        ):
            value = payload.get(key)
            if value in (None, {}, []):
                continue
            content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
            source_row = {key: value}
            records.append(
                self._archive_record(
                    kind=kind,
                    identity=label,
                    content=content,
                    content_source=f"project.json:{key}",
                    suggested_filename=filename,
                    source_table=f"project_{key}",
                    source_row_index=0,
                    source_row=source_row,
                    summary=label + " (preserved for review; not applied automatically)",
                )
            )

    def _append_preserved_settings_records(self, records: list[LegacyNarrativeHistoryRecord]) -> None:
        settings_path = Path(self.project.root_path).resolve() / "legacy_import" / "ghostscripter-settings.json"
        if not settings_path.exists():
            return
        if not settings_path.is_file() or settings_path.is_symlink():
            raise ValueError("Preserved GhostScripter settings are missing or unsafe.")
        settings_text = settings_path.read_text(encoding="utf-8")
        payload = json.loads(settings_text)
        if not isinstance(payload, dict) or payload.get("file_type") != "GhostStudioLegacyGhostScripterSettings":
            raise ValueError("Preserved GhostScripter settings have the wrong file type.")
        records.append(
            self._archive_record(
                kind="legacy_settings",
                identity="GhostScripter settings archive",
                content=settings_text,
                content_source="legacy_import/ghostscripter-settings.json",
                suggested_filename="ghostscripter-settings.json",
                source_table="settings_archive",
                source_row_index=0,
                source_row={
                    "source_database": str(payload.get("source_database") or ""),
                    "migration_note": str(payload.get("migration_note") or ""),
                },
                summary="Exact preserved settings/history metadata archive (read-only; not applied)",
            )
        )
        for kind, key, filename, label in (
            ("preferences", "preferences", "legacy-preferences.json", "Legacy user preferences"),
            ("recent_projects", "recent_projects", "legacy-recent-projects.json", "Legacy recent projects"),
            ("legacy_schema", "legacy_schema", "legacy-database-schema.json", "Legacy database schema rows"),
        ):
            rows = tuple(payload.get(key, ()) or ())
            if not rows:
                continue
            content = json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
            records.append(
                self._archive_record(
                    kind=kind,
                    identity=f"{label} ({len(rows)})",
                    content=content,
                    content_source=f"legacy_import/ghostscripter-settings.json:{key}",
                    suggested_filename=filename,
                    source_table=key,
                    source_row_index=0,
                    source_row={"rows": list(rows), "migration_note": str(payload.get("migration_note") or "")},
                    summary=label + " (read-only; not applied to GhostStudio)",
                )
            )

    def list(self) -> tuple[LegacyNarrativeHistoryRecord, ...]:
        payload = self._payload()
        records: list[LegacyNarrativeHistoryRecord] = []
        for row_index, raw in enumerate(tuple(payload.get("rows", ()) or ())):
            if not isinstance(raw, Mapping):
                continue
            row = dict(raw)
            table = str(row.get("table") or "")
            contract = self._TABLE_CONTRACTS.get(table)
            if contract is None:
                continue
            kind = str(contract["kind"])
            fallback_identity = f"legacy_{kind}_{row_index + 1}"
            identity = str(self._first(row, contract["identity"], fallback_identity) or fallback_identity)
            content_keys = tuple(contract["content"])
            content_key = next((key for key in content_keys if key in row and row.get(key) is not None), "")
            if content_key:
                content = self._content_text(row[content_key])
                content_source = content_key
            else:
                content = json.dumps(row, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
                content_source = "derived_source_row"
            created_at = str(self._first(row, contract["created"], ""))
            try:
                revision = max(0, int(self._first(row, contract["revision"], 0) or 0))
            except (TypeError, ValueError):
                revision = 0
            canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            digest = _sha256(canonical.encode("utf-8"))[:12]
            record_id = f"legacy_{kind}_{row_index:06d}_{digest}"
            stem = _safe_recovery_stem(identity, f"legacy_{kind}_{row_index + 1}")
            filename = (
                f"{stem}.nss" if kind == "script" else
                f"{stem}.quest.json" if kind == "quest" else
                f"{stem}.dialogue.json"
            )
            summary = f"Legacy {kind} snapshot"
            if revision:
                summary += f" revision {revision}"
            records.append(
                LegacyNarrativeHistoryRecord(
                    record_id=record_id,
                    kind=kind,
                    identity=identity,
                    created_at=created_at,
                    revision=revision,
                    summary=summary,
                    content=content,
                    content_source=content_source,
                    suggested_filename=filename,
                    source_table=table,
                    source_row_index=row_index,
                    source_row=row,
                )
            )
        self._append_preserved_project_records(records)
        self._append_preserved_settings_records(records)
        return tuple(records)

    def recover(self, record_id: str, output_dir: str | Path) -> Path:
        """Recover exact snapshot text and provenance into a new folder."""

        key = str(record_id or "")
        record = next((row for row in self.list() if row.record_id == key), None)
        if record is None:
            raise KeyError(f"Unknown legacy GhostScripter history record: {key}")
        target = Path(output_dir).resolve()
        if target.exists():
            raise FileExistsError(
                "Legacy history recovery requires a new output folder; live project data is never overwritten."
            )
        project_root = Path(self.project.root_path).resolve()
        try:
            target.relative_to(project_root)
        except ValueError:
            pass
        else:
            raise ValueError("Legacy history recovery must be outside the open project folder.")
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.with_name(f".{target.name}.stage-{uuid4().hex}")
        content = record.content.encode("utf-8")
        payload = self._payload()
        manifest = {
            "file_type": LEGACY_HISTORY_RECOVERY_FILE_TYPE,
            "schema_version": 1,
            "recovered_at": _utc_now(),
            "project_id": self.project.project_id,
            "record_id": record.record_id,
            "kind": record.kind,
            "identity": record.identity,
            "created_at": record.created_at,
            "revision": record.revision,
            "resource_filename": record.suggested_filename,
            "content_source": record.content_source,
            "sha256": _sha256(content),
            "byte_count": len(content),
            "valid_json": None if record.kind == "script" else self._is_valid_json(record.content),
            "source": {
                "history_path": str(self.path),
                "source_database": str(payload.get("source_database") or ""),
                "legacy_project_id": str(payload.get("legacy_project_id") or ""),
                "table": record.source_table,
                "row_index": record.source_row_index,
                "row": dict(record.source_row),
            },
        }
        try:
            staging.mkdir(parents=False, exist_ok=False)
            _atomic_write(staging / record.suggested_filename, content)
            _atomic_json(staging / "legacy-history-recovery.json", manifest)
            os.replace(staging, target)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return target / "legacy-history-recovery.json"

    @staticmethod
    def _is_valid_json(content: str) -> bool:
        try:
            json.loads(content)
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        return True


class NarrativeProjectService:
    """Create and maintain portable narrative projects without Qt state."""

    @staticmethod
    def create_project(root: str | Path, *, name: str, game: str = "K2") -> NarrativeProject:
        target = Path(root).resolve()
        if target.exists() and any(target.iterdir()):
            raise FileExistsError(f"Refusing to create a project in a nonempty folder: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.with_name(f".{target.name}.stage-{uuid4().hex}")
        project = NarrativeProject(
            project_id=f"narrative_{uuid4().hex}",
            name=name,
            game=game,
            root_path=str(target),
            manifest_path=str(target / PROJECT_FILE_NAME),
        )
        try:
            staging.mkdir(parents=False, exist_ok=False)
            for folder in _STANDARD_DIRECTORIES:
                (staging / folder).mkdir()
            _atomic_json(staging / PROJECT_FILE_NAME, project.to_dict())
            if target.exists():
                target.rmdir()  # The folder was proven empty above.
            os.replace(staging, target)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return project

    @staticmethod
    def load_project(path: str | Path) -> NarrativeProject:
        manifest = Path(path).resolve()
        if manifest.is_dir():
            manifest = manifest / PROJECT_FILE_NAME
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Narrative project manifest root must be a JSON object.")
        return _project_from_payload(payload, manifest)

    @staticmethod
    def save_project(project: NarrativeProject) -> Path:
        manifest = Path(project.manifest_path).resolve()
        root = Path(project.root_path).resolve()
        if not root.is_dir() or root.is_symlink():
            raise ValueError("Narrative project root is missing or unsafe.")
        try:
            manifest.relative_to(root)
        except ValueError as error:
            raise ValueError("Project manifest must stay inside the project root.") from error
        next_revision = project.revision + 1
        updated_at = _utc_now()
        _atomic_json(manifest, project.to_dict(revision=next_revision, updated_at=updated_at))
        project.revision = next_revision
        project.updated_at = updated_at
        return manifest

    @staticmethod
    def validate_project(project: NarrativeProject) -> tuple[NarrativeProjectIssue, ...]:
        issues: list[NarrativeProjectIssue] = []
        identities: dict[tuple[str, str], str] = {}
        paths: dict[str, str] = {}
        asset_ids: set[str] = set()
        known = {row.identity for row in project.assets}
        for asset in project.assets:
            if asset.asset_id in asset_ids:
                issues.append(
                    NarrativeProjectIssue(
                        "blocking",
                        "narrative_project.duplicate_asset_id",
                        f"Stable asset ID is duplicated: {asset.asset_id}.",
                        asset.asset_id,
                    )
                )
            asset_ids.add(asset.asset_id)
            prior = identities.setdefault(asset.identity, asset.asset_id)
            if prior != asset.asset_id:
                issues.append(
                    NarrativeProjectIssue(
                        "blocking",
                        "narrative_project.duplicate_resource",
                        f"Multiple assets produce {asset.filename}.",
                        asset.asset_id,
                    )
                )
            prior_path = paths.setdefault(asset.path.casefold(), asset.asset_id)
            if prior_path != asset.asset_id:
                issues.append(
                    NarrativeProjectIssue(
                        "blocking",
                        "narrative_project.duplicate_path",
                        f"Multiple assets use {asset.path}.",
                        asset.asset_id,
                    )
                )
            try:
                path = _project_asset_path(project, asset.path, require_file=True)
                payload = path.read_bytes()
            except Exception as error:
                issues.append(
                    NarrativeProjectIssue(
                        "blocking",
                        "narrative_project.asset_missing",
                        str(error),
                        asset.asset_id,
                    )
                )
                payload = b""
            if payload and asset.sha256 and _sha256(payload) != asset.sha256:
                issues.append(
                    NarrativeProjectIssue(
                        "warning",
                        "narrative_project.asset_modified",
                        f"{asset.path} changed since its inventory fingerprint was recorded.",
                        asset.asset_id,
                    )
                )
            for dependency in asset.dependencies:
                if dependency.scope == "project" and dependency.identity not in known:
                    issues.append(
                        NarrativeProjectIssue(
                            "blocking" if dependency.required else "warning",
                            "narrative_project.dependency_missing",
                            f"{asset.filename} {dependency.relation} missing resource "
                            f"{dependency.resref}.{dependency.restype}.",
                            asset.asset_id,
                        )
                    )
        return tuple(issues)

    @staticmethod
    def refresh_asset_fingerprints(project: NarrativeProject, *, save: bool = True) -> tuple[NarrativeAssetRecord, ...]:
        for asset in project.assets:
            data = _project_asset_path(project, asset.path, require_file=True).read_bytes()
            asset.sha256 = _sha256(data)
            asset.byte_count = len(data)
        if save:
            NarrativeProjectService.save_project(project)
        return tuple(project.assets)

    @staticmethod
    def register_asset(
        project: NarrativeProject,
        path: str | Path,
        *,
        resref: str | None = None,
        restype: str | None = None,
        role: str | None = None,
        dependencies: Sequence[NarrativeAssetDependency] = (),
        metadata: dict[str, Any] | None = None,
        save: bool = True,
    ) -> NarrativeAssetRecord:
        source = Path(path)
        if source.is_absolute():
            root = Path(project.root_path).resolve()
            try:
                relative = source.resolve().relative_to(root)
            except ValueError as error:
                raise ValueError("Register only files already inside the narrative project.") from error
        else:
            relative = Path(*PurePosixPath(_portable_relative_path(path)).parts)
        candidate = _project_asset_path(project, relative.as_posix(), require_file=True)
        extension = _resource_type(restype or candidate.suffix).extension.lower()
        resource_name = _validated_resref(resref or candidate.stem)
        if project.asset_by_identity(resource_name, extension) is not None:
            raise ValueError(f"Project already contains {resource_name}.{extension}.")
        data = candidate.read_bytes()
        record = NarrativeAssetRecord(
            asset_id=f"asset_{uuid4().hex}",
            resref=resource_name,
            restype=extension,
            path=relative.as_posix(),
            role=role or ("source" if extension == "nss" else "runtime"),
            dependencies=tuple(dependencies),
            sha256=_sha256(data),
            byte_count=len(data),
            metadata=dict(metadata or {}),
        )
        project.assets.append(record)
        try:
            if save:
                NarrativeProjectService.save_project(project)
        except Exception:
            project.assets.remove(record)
            raise
        return record

    @staticmethod
    def import_asset(
        project: NarrativeProject,
        source_path: str | Path,
        *,
        resref: str | None = None,
        restype: str | None = None,
        role: str | None = None,
        dependencies: Sequence[NarrativeAssetDependency] = (),
        metadata: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> NarrativeAssetRecord:
        requested_source = Path(source_path)
        if not requested_source.is_file() or requested_source.is_symlink():
            raise FileNotFoundError(f"Asset import source is missing or unsafe: {requested_source}")
        source = requested_source.resolve()
        extension = _resource_type(restype or source.suffix).extension.lower()
        resource_name = _validated_resref(resref or source.stem)
        if project.asset_by_identity(resource_name, extension) is not None:
            raise ValueError(f"Project already contains {resource_name}.{extension}.")
        folder = "scripts" if extension in {"nss", "ncs"} else "dialogues" if extension == "dlg" else (
            "journals" if extension == "jrl" else "tables" if extension == "2da" else (
                "blueprints" if extension in _GFF_BLUEPRINT_TYPES else "assets"
            )
        )
        relative = f"{folder}/{resource_name}.{extension}"
        destination = _project_asset_path(project, relative)
        previous = destination.read_bytes() if destination.exists() and destination.is_file() else None
        if destination.exists() and not overwrite:
            raise FileExistsError(f"Project asset destination already exists: {relative}")
        incoming = source.read_bytes()
        _atomic_write(destination, incoming)
        try:
            return NarrativeProjectService.register_asset(
                project,
                relative,
                resref=resource_name,
                restype=extension,
                role=role,
                dependencies=dependencies,
                metadata=metadata,
                save=True,
            )
        except Exception:
            if previous is None:
                destination.unlink(missing_ok=True)
            else:
                _atomic_write(destination, previous)
            raise

    @staticmethod
    def write_asset(
        project: NarrativeProject,
        *,
        resref: str,
        restype: str,
        data: bytes,
        role: str | None = None,
        dependencies: Sequence[NarrativeAssetDependency] = (),
        metadata: dict[str, Any] | None = None,
        save: bool = True,
    ) -> NarrativeAssetRecord:
        """Atomically create or update one project-owned resource.

        Workbench controllers use this method when the user explicitly saves a
        project.  It keeps bytes out of the JSON manifest, retains stable asset
        IDs for existing resources, and restores both the file and inventory
        row if manifest promotion fails.
        """

        extension = _resource_type(restype).extension.lower()
        resource_name = _validated_resref(resref)
        existing = project.asset_by_identity(resource_name, extension)
        if existing is not None:
            relative = existing.path
        else:
            folder = (
                "scripts" if extension in {"nss", "ncs"}
                else "dialogues" if extension == "dlg"
                else "journals" if extension == "jrl"
                else "tables" if extension == "2da"
                else "blueprints" if extension in _GFF_BLUEPRINT_TYPES
                else "assets"
            )
            relative = f"{folder}/{resource_name}.{extension}"
        destination = _project_asset_path(project, relative)
        previous_bytes = destination.read_bytes() if destination.is_file() and not destination.is_symlink() else None
        previous_row = existing.to_dict() if existing is not None else None
        payload = bytes(data or b"")
        _atomic_write(destination, payload)
        if existing is None:
            record = NarrativeAssetRecord(
                asset_id=f"asset_{uuid4().hex}",
                resref=resource_name,
                restype=extension,
                path=relative,
                role=role or ("source" if extension == "nss" else "runtime"),
                dependencies=tuple(dependencies),
                sha256=_sha256(payload),
                byte_count=len(payload),
                metadata=dict(metadata or {}),
            )
            project.assets.append(record)
        else:
            record = existing
            record.role = str(role or record.role)
            record.dependencies = tuple(dependencies) if dependencies else record.dependencies
            record.metadata = dict(metadata) if metadata is not None else record.metadata
            record.sha256 = _sha256(payload)
            record.byte_count = len(payload)
        try:
            if save:
                NarrativeProjectService.save_project(project)
        except Exception:
            if previous_bytes is None:
                destination.unlink(missing_ok=True)
            else:
                _atomic_write(destination, previous_bytes)
            if previous_row is None:
                project.assets.remove(record)
            else:
                restored = NarrativeAssetRecord.from_dict(previous_row)
                record.asset_id = restored.asset_id
                record.resref = restored.resref
                record.restype = restored.restype
                record.path = restored.path
                record.role = restored.role
                record.dependencies = restored.dependencies
                record.sha256 = restored.sha256
                record.byte_count = restored.byte_count
                record.metadata = restored.metadata
            raise
        return record

    @staticmethod
    def import_legacy_ghostscripter_project(
        source: str | Path,
        destination: str | Path,
        *,
        legacy_database: str | Path | None = None,
    ) -> LegacyNarrativeProjectImportResult:
        """Migrate a legacy ``project.json`` without modifying its source.

        The complete legacy tree is retained under ``legacy_source``.  KOTOR
        resource files are additionally registered as first-class portable
        assets.  Quest JSON and any unknown artifacts remain preserved even
        when they cannot be safely converted to an engine resource.  Optional
        SQLite history is read through a read-only connection and exported as
        JSON inside the new project.
        """

        source_root = Path(source).resolve()
        source_manifest = source_root / "project.json" if source_root.is_dir() else source_root
        if not source_manifest.is_file() or source_manifest.is_symlink():
            raise FileNotFoundError("Choose a legacy GhostScripter project.json or its project folder.")
        source_root = source_manifest.parent.resolve()
        payload = json.loads(source_manifest.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or "target_game" not in payload:
            raise ValueError("The selected project.json is not a recognized GhostScripter project manifest.")

        target = Path(destination).resolve()
        if target.exists() and (not target.is_dir() or any(target.iterdir())):
            raise FileExistsError(f"Legacy migration requires an empty destination: {target}")
        stage = target.with_name(f".{target.name}.legacy-import-{uuid4().hex}")
        warnings: list[str] = []
        imported: list[str] = []
        preserved_count = 0
        history_rows: list[dict[str, Any]] = []
        preference_rows: list[dict[str, Any]] = []
        recent_project_rows: list[dict[str, Any]] = []
        schema_rows: list[dict[str, Any]] = []
        try:
            project = NarrativeProjectService.create_project(
                stage,
                name=str(payload.get("name") or "Imported GhostScripter Project"),
                game=str(payload.get("target_game") or "K1"),
            )
            project.metadata.update(
                {
                    "legacy_ghostscripter": {
                        "source_manifest": str(source_manifest),
                        "schema_version": payload.get("schema_version"),
                        "legacy_project_id": str(payload.get("project_id") or ""),
                        "version": str(payload.get("version") or ""),
                        "author": str(payload.get("author") or ""),
                        "description": str(payload.get("description") or ""),
                        "category": str(payload.get("category") or ""),
                        "tags": list(payload.get("tags", ()) or ()),
                        "compatibility": list(payload.get("compatibility", ()) or ()),
                        "dependencies": list(payload.get("dependencies", ()) or ()),
                        "twoda_edits": dict(payload.get("twoda_edits", {}) or {}),
                    }
                }
            )

            preserved_root = stage / "legacy_source"
            preserved_root.mkdir()
            for path in sorted(source_root.rglob("*"), key=lambda item: str(item).casefold()):
                relative = path.relative_to(source_root)
                if path.is_symlink():
                    warnings.append(f"Skipped unsafe legacy symlink: {relative.as_posix()}")
                    continue
                destination_path = preserved_root / relative
                if path.is_dir():
                    destination_path.mkdir(parents=True, exist_ok=True)
                    continue
                if not path.is_file():
                    continue
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination_path)
                if destination_path.read_bytes() != path.read_bytes():
                    raise OSError(f"Legacy preservation copy failed verification: {relative.as_posix()}")
                preserved_count += 1

                extension = path.suffix.lower().lstrip(".")
                try:
                    _resource_type(extension)
                    resource_name = _validated_resref(path.stem)
                except (ValueError, TypeError):
                    continue
                if project.asset_by_identity(resource_name, extension) is not None:
                    warnings.append(f"Preserved but did not register duplicate resource: {relative.as_posix()}")
                    continue
                role = "source" if extension == "nss" else (
                    "global_install" if extension == "tlk" else "runtime"
                )
                NarrativeProjectService.write_asset(
                    project,
                    resref=resource_name,
                    restype=extension,
                    data=path.read_bytes(),
                    role=role,
                    metadata={"legacy_path": relative.as_posix()},
                    save=False,
                )
                imported.append(f"{resource_name}.{extension}")

            database_path = Path(legacy_database).resolve() if legacy_database else None
            if database_path is not None and database_path.is_file() and not database_path.is_symlink():
                legacy_project_id = str(payload.get("project_id") or "")
                connection = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
                connection.row_factory = sqlite3.Row
                try:
                    scoped_tables = {
                        "script_history": "project_id",
                        "quest_snapshots": "project_id",
                        "dialogue_snapshots": "project_id",
                        "export_history": "project_id",
                    }
                    for table, column in scoped_tables.items():
                        try:
                            rows = connection.execute(
                                f"SELECT * FROM {table} WHERE {column} = ?", (legacy_project_id,)
                            ).fetchall()
                        except sqlite3.DatabaseError as error:
                            warnings.append(f"Could not read legacy {table}: {error}")
                            continue
                        history_rows.extend({"table": table, **dict(row)} for row in rows)
                    for table, destination_rows in (
                        ("user_prefs", preference_rows),
                        ("recent_projects", recent_project_rows),
                        ("schema_version", schema_rows),
                    ):
                        try:
                            rows = connection.execute(f"SELECT * FROM {table}").fetchall()
                        except sqlite3.DatabaseError as error:
                            warnings.append(f"Could not read legacy {table}: {error}")
                            continue
                        destination_rows.extend({"table": table, **dict(row)} for row in rows)
                finally:
                    connection.close()
            elif legacy_database is not None:
                warnings.append(f"Legacy history database was not a safe readable file: {database_path}")

            if history_rows:
                history_path = stage / "legacy_import" / "ghostscripter-history.json"
                _atomic_json(
                    history_path,
                    {
                        "file_type": LEGACY_HISTORY_FILE_TYPE,
                        "schema_version": LEGACY_HISTORY_SCHEMA_VERSION,
                        "source_database": str(database_path),
                        "legacy_project_id": str(payload.get("project_id") or ""),
                        "rows": history_rows,
                    },
                )
            if preference_rows or recent_project_rows or schema_rows:
                _atomic_json(
                    stage / "legacy_import" / "ghostscripter-settings.json",
                    {
                        "file_type": "GhostStudioLegacyGhostScripterSettings",
                        "schema_version": 1,
                        "source_database": str(database_path),
                        "preferences": preference_rows,
                        "recent_projects": recent_project_rows,
                        "legacy_schema": schema_rows,
                        "migration_note": (
                            "Preserved losslessly for review. GhostStudio does not silently apply legacy global "
                            "paths, themes, or window state to the current application."
                        ),
                    },
                )

            # Make old export receipts visible in the new project history while
            # retaining the exact legacy database rows above.  Legacy receipts
            # did not store input bytes/hashes, so that limitation is explicit.
            legacy_exports = [row for row in history_rows if row.get("table") == "export_history"]
            if legacy_exports:
                export_store = NarrativeExportHistoryStore(project)
                for row in legacy_exports:
                    succeeded = bool(int(row.get("success", 0) or 0))
                    export_store.record(
                        operation=f"legacy_{str(row.get('export_type') or 'export')}",
                        outcome="succeeded" if succeeded else "failed",
                        destination=str(row.get("output_path") or ""),
                        summary=(
                            f"Imported GhostScripter export receipt ({int(row.get('files_count', 0) or 0)} file(s)); "
                            "legacy input hashes were not recorded."
                        ),
                        metadata={
                            "legacy": True,
                            "legacy_exported_at": str(row.get("exported_at") or ""),
                            "legacy_row": dict(row),
                        },
                    )
            project.metadata["legacy_ghostscripter"]["history_rows"] = len(history_rows)
            project.metadata["legacy_ghostscripter"]["preference_rows"] = len(preference_rows)
            project.metadata["legacy_ghostscripter"]["recent_project_rows"] = len(recent_project_rows)
            project.metadata["legacy_ghostscripter"]["warnings"] = list(warnings)
            NarrativeProjectService.save_project(project)

            if target.exists():
                target.rmdir()
            os.replace(stage, target)
            imported_project = NarrativeProjectService.load_project(target)
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise

        return LegacyNarrativeProjectImportResult(
            imported_project,
            str(source_manifest),
            tuple(imported),
            preserved_count,
            len(history_rows),
            len(preference_rows),
            len(recent_project_rows),
            tuple(warnings),
        )


@dataclass(frozen=True)
class RecentNarrativeProject:
    project_id: str
    name: str
    game: str
    manifest_path: str
    last_opened_at: str

    def to_dict(self) -> dict[str, str]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "game": self.game,
            "manifest_path": self.manifest_path,
            "last_opened_at": self.last_opened_at,
        }


class RecentNarrativeProjectStore:
    """An explicit JSON-backed recent list; importing this module writes nothing."""

    def __init__(self, path: str | Path, *, limit: int = 20) -> None:
        self.path = Path(path).resolve()
        self.limit = max(1, int(limit))

    def list(self, *, existing_only: bool = False) -> tuple[RecentNarrativeProject, ...]:
        if not self.path.is_file():
            return ()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("file_type") != RECENT_FILE_TYPE or int(payload.get("schema_version", 0)) != 1:
            raise ValueError("Unsupported GhostStudio recent-project registry.")
        rows = tuple(
            RecentNarrativeProject(
                project_id=str(item.get("project_id", "")),
                name=str(item.get("name", "")),
                game=_game_key(item.get("game", "K2")),
                manifest_path=str(item.get("manifest_path", "")),
                last_opened_at=str(item.get("last_opened_at", "")),
            )
            for item in payload.get("projects", ())
        )
        if existing_only:
            rows = tuple(row for row in rows if Path(row.manifest_path).is_file())
        return rows

    def remember(self, project: NarrativeProject) -> tuple[RecentNarrativeProject, ...]:
        current = [row for row in self.list() if row.project_id != project.project_id]
        current.insert(
            0,
            RecentNarrativeProject(
                project.project_id,
                project.name,
                project.game,
                str(Path(project.manifest_path).resolve()),
                _utc_now(),
            ),
        )
        rows = tuple(current[: self.limit])
        _atomic_json(
            self.path,
            {
                "file_type": RECENT_FILE_TYPE,
                "schema_version": 1,
                "projects": [row.to_dict() for row in rows],
            },
        )
        return rows

    def forget(self, project_id: str) -> tuple[RecentNarrativeProject, ...]:
        rows = tuple(row for row in self.list() if row.project_id != str(project_id))
        _atomic_json(
            self.path,
            {
                "file_type": RECENT_FILE_TYPE,
                "schema_version": 1,
                "projects": [row.to_dict() for row in rows],
            },
        )
        return rows


@dataclass(frozen=True)
class NarrativeRevision:
    revision_id: str
    created_at: str
    message: str
    project_revision: int
    asset_count: int
    manifest_path: str
    asset_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class NarrativeRevisionAsset:
    """Fingerprint and source metadata for one asset in an immutable snapshot."""

    revision_id: str
    asset_id: str
    path: str
    sha256: str
    byte_count: int
    asset: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NarrativeExportInputFingerprint:
    """One exact operation input without retaining its potentially large bytes."""

    filename: str
    sha256: str
    byte_count: int
    source_asset_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
            "source_asset_id": self.source_asset_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "NarrativeExportInputFingerprint":
        return cls(
            filename=str(payload.get("filename") or "input"),
            sha256=str(payload.get("sha256") or "").lower(),
            byte_count=max(0, int(payload.get("byte_count") or 0)),
            source_asset_id=str(payload.get("source_asset_id") or ""),
        )


@dataclass(frozen=True)
class NarrativeExportHistoryRecord:
    """Persistent receipt for one package, stage, install, or restore attempt."""

    receipt_id: str
    created_at: str
    operation: str
    outcome: str
    destination: str
    input_hashes: tuple[NarrativeExportInputFingerprint, ...] = ()
    backup_path: str = ""
    receipt_path: str = ""
    summary: str = ""
    issues: tuple[dict[str, Any], ...] = ()
    engine_proof: str = "not_recorded"
    engine_proof_evidence: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "receipt_id": self.receipt_id,
            "created_at": self.created_at,
            "operation": self.operation,
            "outcome": self.outcome,
            "destination": self.destination,
            "input_hashes": [row.to_dict() for row in self.input_hashes],
            "backup_path": self.backup_path,
            "receipt_path": self.receipt_path,
            "summary": self.summary,
            "issues": [dict(row) for row in self.issues],
            "engine_proof": self.engine_proof,
            "engine_proof_evidence": self.engine_proof_evidence,
            "metadata": dict(self.metadata),
        }
        for key, value in self.extensions.items():
            if key not in payload:
                payload[key] = value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "NarrativeExportHistoryRecord":
        known = {
            "receipt_id",
            "created_at",
            "operation",
            "outcome",
            "destination",
            "input_hashes",
            "backup_path",
            "receipt_path",
            "summary",
            "issues",
            "engine_proof",
            "engine_proof_evidence",
            "metadata",
        }
        return cls(
            receipt_id=str(payload.get("receipt_id") or ""),
            created_at=str(payload.get("created_at") or ""),
            operation=str(payload.get("operation") or "unknown"),
            outcome=str(payload.get("outcome") or "unknown"),
            destination=str(payload.get("destination") or ""),
            input_hashes=tuple(
                NarrativeExportInputFingerprint.from_dict(dict(row))
                for row in tuple(payload.get("input_hashes", ()) or ())
                if isinstance(row, Mapping)
            ),
            backup_path=str(payload.get("backup_path") or ""),
            receipt_path=str(payload.get("receipt_path") or ""),
            summary=str(payload.get("summary") or ""),
            issues=tuple(dict(row) for row in tuple(payload.get("issues", ()) or ()) if isinstance(row, Mapping)),
            engine_proof=str(payload.get("engine_proof") or "not_recorded"),
            engine_proof_evidence=str(payload.get("engine_proof_evidence") or ""),
            metadata=dict(payload.get("metadata", {}) or {}),
            extensions={key: value for key, value in payload.items() if key not in known},
        )


class NarrativeExportHistoryStore:
    """Project-local, atomic distribution receipts with forward-compatible JSON."""

    def __init__(self, project: NarrativeProject) -> None:
        self.project = project
        self.path = Path(project.root_path).resolve() / ".ghoststudio" / "export-history.json"

    @staticmethod
    def _fingerprint(value: object) -> NarrativeExportInputFingerprint:
        if isinstance(value, NarrativeExportInputFingerprint):
            return value
        if isinstance(value, Mapping):
            filename = str(value.get("filename") or value.get("name") or "input")
            data = value.get("data")
            source_asset_id = str(value.get("source_asset_id") or value.get("asset_id") or "")
        else:
            filename = str(getattr(value, "filename", "input") or "input")
            data = getattr(value, "data", None)
            source_asset_id = str(getattr(value, "source_asset_id", "") or "")
        if data is None:
            raise ValueError(f"Export history input {filename!r} does not expose bytes for exact hashing.")
        payload = bytes(data)
        return NarrativeExportInputFingerprint(filename, _sha256(payload), len(payload), source_asset_id)

    def _payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "file_type": EXPORT_HISTORY_FILE_TYPE,
                "schema_version": 1,
                "project_id": self.project.project_id,
                "records": [],
            }
        if not self.path.is_file() or self.path.is_symlink():
            raise ValueError("Narrative export history is missing or unsafe.")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("file_type") != EXPORT_HISTORY_FILE_TYPE:
            raise ValueError("Narrative export history has the wrong file type.")
        if int(payload.get("schema_version", 0) or 0) != 1:
            raise ValueError("Unsupported narrative export-history schema.")
        owner = str(payload.get("project_id") or "")
        if owner and owner != self.project.project_id:
            raise ValueError("Narrative export history belongs to a different project.")
        return payload

    def list(
        self,
        *,
        operation: str = "",
        outcome: str = "",
        query: str = "",
    ) -> tuple[NarrativeExportHistoryRecord, ...]:
        payload = self._payload()
        rows = [
            NarrativeExportHistoryRecord.from_dict(dict(row))
            for row in tuple(payload.get("records", ()) or ())
            if isinstance(row, Mapping)
        ]
        operation_key = str(operation or "").strip().casefold()
        outcome_key = str(outcome or "").strip().casefold()
        query_key = str(query or "").strip().casefold()
        filtered: list[NarrativeExportHistoryRecord] = []
        for row in reversed(rows):
            if operation_key and row.operation.casefold() != operation_key:
                continue
            if outcome_key and row.outcome.casefold() != outcome_key:
                continue
            haystack = " ".join(
                (
                    row.operation,
                    row.outcome,
                    row.destination,
                    row.backup_path,
                    row.receipt_path,
                    row.summary,
                    row.engine_proof,
                    *(fingerprint.filename for fingerprint in row.input_hashes),
                    *(fingerprint.sha256 for fingerprint in row.input_hashes),
                )
            ).casefold()
            if query_key and query_key not in haystack:
                continue
            filtered.append(row)
        return tuple(filtered)

    def record(
        self,
        *,
        operation: str,
        outcome: str,
        destination: str | Path = "",
        inputs: Iterable[object] = (),
        backup_path: str | Path = "",
        receipt_path: str | Path = "",
        summary: str = "",
        issues: Sequence[Mapping[str, Any]] = (),
        engine_proof: str = "not_recorded",
        engine_proof_evidence: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> NarrativeExportHistoryRecord:
        operation_key = str(operation or "unknown").strip().lower().replace(" ", "_") or "unknown"
        outcome_key = str(outcome or "unknown").strip().lower().replace(" ", "_") or "unknown"
        fingerprints = tuple(self._fingerprint(row) for row in inputs)
        record = NarrativeExportHistoryRecord(
            receipt_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:10],
            created_at=_utc_now(),
            operation=operation_key,
            outcome=outcome_key,
            destination=str(destination or ""),
            input_hashes=fingerprints,
            backup_path=str(backup_path or ""),
            receipt_path=str(receipt_path or ""),
            summary=str(summary or ""),
            issues=tuple(dict(row) for row in issues),
            engine_proof=str(engine_proof or "not_recorded"),
            engine_proof_evidence=str(engine_proof_evidence or ""),
            metadata=dict(metadata or {}),
        )
        payload = self._payload()
        records = list(payload.get("records", ()) or ())
        records.append(record.to_dict())
        payload["file_type"] = EXPORT_HISTORY_FILE_TYPE
        payload["schema_version"] = 1
        payload["project_id"] = self.project.project_id
        payload["records"] = records
        _atomic_json(self.path, payload)
        return record

    def set_engine_proof(
        self,
        receipt_id: str,
        status: str,
        *,
        evidence: str = "",
    ) -> NarrativeExportHistoryRecord:
        key = str(receipt_id or "")
        payload = self._payload()
        records = list(payload.get("records", ()) or ())
        updated: NarrativeExportHistoryRecord | None = None
        for index, raw in enumerate(records):
            if not isinstance(raw, Mapping) or str(raw.get("receipt_id") or "") != key:
                continue
            row = dict(raw)
            row["engine_proof"] = str(status or "not_recorded")
            row["engine_proof_evidence"] = str(evidence or "")
            records[index] = row
            updated = NarrativeExportHistoryRecord.from_dict(row)
            break
        if updated is None:
            raise KeyError(f"Unknown narrative export receipt: {key}")
        payload["records"] = records
        _atomic_json(self.path, payload)
        return updated


class NarrativeRevisionStore:
    """Immutable project-local snapshots with non-destructive materialization."""

    def __init__(self, project: NarrativeProject) -> None:
        self.project = project
        self.root = Path(project.root_path).resolve() / ".ghoststudio" / "revisions"

    def create(self, *, message: str = "", author: str = "") -> NarrativeRevision:
        issues = NarrativeProjectService.validate_project(self.project)
        blocking = [row.message for row in issues if row.blocking]
        if blocking:
            raise ValueError("Cannot snapshot an invalid narrative project: " + "; ".join(blocking))
        created_at = _utc_now()
        revision_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:10]
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / revision_id
        staging = self.root / f".{revision_id}.stage-{uuid4().hex}"
        files: list[dict[str, Any]] = []
        try:
            (staging / "files").mkdir(parents=True)
            for asset in self.project.assets:
                source = _project_asset_path(self.project, asset.path, require_file=True)
                destination = staging / "files" / Path(*PurePosixPath(asset.path).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                data = source.read_bytes()
                destination.write_bytes(data)
                files.append(
                    {
                        "asset_id": asset.asset_id,
                        "path": asset.path,
                        "sha256": _sha256(data),
                        "byte_count": len(data),
                    }
                )
            project_payload = self.project.to_dict()
            fingerprints = {row["asset_id"]: row for row in files}
            for asset_payload in project_payload.get("assets", ()):
                fingerprint = fingerprints.get(asset_payload.get("asset_id"))
                if fingerprint is not None:
                    asset_payload["sha256"] = fingerprint["sha256"]
                    asset_payload["byte_count"] = fingerprint["byte_count"]
            snapshot = {
                "file_type": REVISION_FILE_TYPE,
                "schema_version": 1,
                "revision_id": revision_id,
                "created_at": created_at,
                "author": str(author or ""),
                "message": str(message or ""),
                "project_revision": self.project.revision,
                "project": project_payload,
                "files": files,
            }
            _atomic_json(staging / "revision.json", snapshot)
            os.replace(staging, target)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return NarrativeRevision(
            revision_id,
            created_at,
            str(message or ""),
            self.project.revision,
            len(files),
            str(target / "revision.json"),
            tuple(str(row["asset_id"]) for row in files),
        )

    def list(self) -> tuple[NarrativeRevision, ...]:
        if not self.root.is_dir():
            return ()
        rows: list[NarrativeRevision] = []
        for manifest in sorted(self.root.glob("*/revision.json"), reverse=True):
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                if payload.get("file_type") != REVISION_FILE_TYPE:
                    continue
                rows.append(
                    NarrativeRevision(
                        str(payload.get("revision_id", "")),
                        str(payload.get("created_at", "")),
                        str(payload.get("message", "")),
                        int(payload.get("project_revision", 0)),
                        len(tuple(payload.get("files", ()) or ())),
                        str(manifest),
                        tuple(
                            str(row.get("asset_id") or "")
                            for row in tuple(payload.get("files", ()) or ())
                            if isinstance(row, Mapping) and row.get("asset_id")
                        ),
                    )
                )
            except Exception:
                continue
        return tuple(rows)

    def list_for_asset(self, asset_id: str) -> tuple[NarrativeRevision, ...]:
        """Return only snapshots containing ``asset_id`` without reading live bytes."""

        key = str(asset_id or "")
        return tuple(row for row in self.list() if key and key in row.asset_ids)

    def list_assets(self, revision_id: str) -> tuple[NarrativeRevisionAsset, ...]:
        """Inspect immutable asset fingerprints and original manifest metadata."""

        revision_key, source_root, payload = self._snapshot_payload(revision_id)
        project_assets = {
            str(row.get("asset_id") or ""): dict(row)
            for row in tuple(dict(payload.get("project", {}) or {}).get("assets", ()) or ())
            if isinstance(row, Mapping)
        }
        return tuple(
            NarrativeRevisionAsset(
                revision_id=revision_key,
                asset_id=str(row.get("asset_id") or ""),
                path=_portable_relative_path(row.get("path", "")),
                sha256=str(row.get("sha256") or ""),
                byte_count=max(0, int(row.get("byte_count") or 0)),
                asset=project_assets.get(str(row.get("asset_id") or ""), {}),
            )
            for row in tuple(payload.get("files", ()) or ())
            if isinstance(row, Mapping)
        )

    def _snapshot_payload(self, revision_id: str) -> tuple[str, Path, dict[str, Any]]:
        revision_key = str(revision_id or "")
        if not _REVISION_ID_PATTERN.fullmatch(revision_key):
            raise ValueError("Invalid narrative revision identifier.")
        source_root = self.root / revision_key
        payload = json.loads((source_root / "revision.json").read_text(encoding="utf-8"))
        if payload.get("file_type") != REVISION_FILE_TYPE or payload.get("revision_id") != revision_key:
            raise ValueError("Narrative revision manifest is missing or mismatched.")
        return revision_key, source_root, payload

    def materialize_asset(
        self,
        revision_id: str,
        asset_id: str,
        output_dir: str | Path,
    ) -> Path:
        """Recover one snapshotted asset and its metadata into a new folder.

        The caller cannot target the live project (or any existing directory),
        so reviewing an older resource never mutates current work.
        """

        revision_key, source_root, payload = self._snapshot_payload(revision_id)
        key = str(asset_id or "")
        rows = [
            dict(row)
            for row in tuple(payload.get("files", ()) or ())
            if isinstance(row, Mapping) and str(row.get("asset_id") or "") == key
        ]
        if len(rows) != 1:
            raise KeyError(f"Snapshot {revision_key} does not contain asset {key!r}.")
        row = rows[0]
        relative = _portable_relative_path(row.get("path", ""))
        files_root = (source_root / "files").resolve()
        source = (files_root / Path(*PurePosixPath(relative).parts)).resolve()
        try:
            source.relative_to(files_root)
        except ValueError as error:
            raise ValueError("Revision asset path escapes its snapshot.") from error
        data = source.read_bytes()
        expected_hash = str(row.get("sha256") or "")
        if _sha256(data) != expected_hash or len(data) != int(row.get("byte_count", -1)):
            raise ValueError(f"Revision asset fingerprint mismatch: {relative}")
        project_payload = dict(payload.get("project", {}) or {})
        asset_payload = next(
            (
                dict(candidate)
                for candidate in tuple(project_payload.get("assets", ()) or ())
                if isinstance(candidate, Mapping) and str(candidate.get("asset_id") or "") == key
            ),
            {},
        )
        target = Path(output_dir).resolve()
        if target.exists():
            raise FileExistsError("Asset recovery requires a new output folder; live project data is never overwritten.")
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.with_name(f".{target.name}.stage-{uuid4().hex}")
        try:
            destination = staging / Path(*PurePosixPath(relative).parts)
            destination.parent.mkdir(parents=True)
            destination.write_bytes(data)
            recovery = {
                "file_type": REVISION_ASSET_RECOVERY_FILE_TYPE,
                "schema_version": 1,
                "recovered_at": _utc_now(),
                "project_id": self.project.project_id,
                "revision_id": revision_key,
                "asset_id": key,
                "path": relative,
                "sha256": expected_hash,
                "byte_count": len(data),
                "asset": asset_payload,
            }
            _atomic_json(staging / "recovered-asset.json", recovery)
            os.replace(staging, target)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return target / "recovered-asset.json"

    def materialize(self, revision_id: str, output_dir: str | Path) -> Path:
        revision_key, source_root, payload = self._snapshot_payload(revision_id)
        target = Path(output_dir).resolve()
        if target.exists():
            raise FileExistsError("Revision recovery requires a new output folder; live project data is never overwritten.")
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.with_name(f".{target.name}.stage-{uuid4().hex}")
        try:
            staging.mkdir()
            for row in payload.get("files", ()):
                relative = _portable_relative_path(row.get("path", ""))
                source = (source_root / "files" / Path(*PurePosixPath(relative).parts)).resolve()
                try:
                    source.relative_to((source_root / "files").resolve())
                except ValueError as error:
                    raise ValueError("Revision asset path escapes its snapshot.") from error
                data = source.read_bytes()
                if _sha256(data) != str(row.get("sha256", "")):
                    raise ValueError(f"Revision asset hash mismatch: {relative}")
                destination = staging / Path(*PurePosixPath(relative).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            project_payload = dict(payload.get("project", {}) or {})
            _atomic_json(staging / PROJECT_FILE_NAME, project_payload)
            os.replace(staging, target)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return target / PROJECT_FILE_NAME


__all__ = [
    "EXPORT_HISTORY_FILE_TYPE",
    "LEGACY_HISTORY_FILE_TYPE",
    "LEGACY_HISTORY_RECOVERY_FILE_TYPE",
    "LEGACY_HISTORY_SCHEMA_VERSION",
    "LegacyNarrativeHistoryRecord",
    "LegacyNarrativeHistoryStore",
    "LegacyNarrativeProjectImportResult",
    "NarrativeAssetDependency",
    "NarrativeAssetRecord",
    "NarrativeExportHistoryRecord",
    "NarrativeExportHistoryStore",
    "NarrativeExportInputFingerprint",
    "NarrativeProject",
    "NarrativeProjectIssue",
    "NarrativeProjectService",
    "NarrativeRevision",
    "NarrativeRevisionAsset",
    "NarrativeRevisionStore",
    "PROJECT_FILE_NAME",
    "PROJECT_FILE_TYPE",
    "PROJECT_SCHEMA_VERSION",
    "RecentNarrativeProject",
    "RecentNarrativeProjectStore",
    "REVISION_ASSET_RECOVERY_FILE_TYPE",
]
