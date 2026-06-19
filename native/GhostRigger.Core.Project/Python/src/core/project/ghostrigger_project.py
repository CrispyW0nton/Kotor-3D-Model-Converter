"""Suite-level GhostRigger project/session model."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .resource_address import ResourceAddress


GHOSTRIGGER_PROJECT_FILE_TYPE = "GhostRiggerProject"
CURRENT_GHOSTRIGGER_PROJECT_SCHEMA_VERSION = 1


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_project_id(prefix: str = "project") -> str:
    return f"{prefix}_{uuid4().hex}"


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _address_or_none(value: Any) -> ResourceAddress | None:
    if value in (None, ""):
        return None
    return ResourceAddress.from_dict(value)


def _address_to_dict(address: ResourceAddress | None) -> dict[str, Any] | None:
    return address.to_dict() if address is not None else None


def _addresses_from_list(values: Any) -> list[ResourceAddress]:
    return [ResourceAddress.from_dict(value) for value in (values or [])]


def _addresses_to_list(values: list[ResourceAddress]) -> list[dict[str, Any]]:
    return [value.to_dict() for value in values]


@dataclass
class GameInstallRef:
    id: str
    game: str
    root_path: str
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "game": self.game, "root_path": self.root_path, "label": self.label}

    @classmethod
    def from_dict(cls, data: Any) -> "GameInstallRef":
        data = _dict(data)
        return cls(
            id=str(data.get("id") or ""),
            game=str(data.get("game") or "unknown"),
            root_path=str(data.get("root_path") or ""),
            label=str(data["label"]) if data.get("label") is not None else None,
        )


@dataclass
class ProjectAssetRef:
    id: str
    kind: str
    address: ResourceAddress
    label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "address": self.address.to_dict(),
            "label": self.label,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ProjectAssetRef":
        data = _dict(data)
        return cls(
            id=str(data.get("id") or ""),
            kind=str(data.get("kind") or ""),
            address=ResourceAddress.from_dict(data.get("address") or {"scheme": ""}),
            label=str(data["label"]) if data.get("label") is not None else None,
            metadata=_dict(data.get("metadata")),
        )


@dataclass
class CharacterJobRef:
    id: str
    kind: str = "character"
    source_asset: ResourceAddress | None = None
    target_base_model: ResourceAddress | None = None
    last_export: ResourceAddress | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "source_asset": _address_to_dict(self.source_asset),
            "target_base_model": _address_to_dict(self.target_base_model),
            "last_export": _address_to_dict(self.last_export),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "CharacterJobRef":
        data = _dict(data)
        return cls(
            id=str(data.get("id") or ""),
            kind=str(data.get("kind") or "character"),
            source_asset=_address_or_none(data.get("source_asset")),
            target_base_model=_address_or_none(data.get("target_base_model")),
            last_export=_address_or_none(data.get("last_export")),
            metadata=_dict(data.get("metadata")),
        )


@dataclass
class RetargetJobRef:
    id: str
    mode: str
    source: ResourceAddress | None = None
    target: ResourceAddress | None = None
    profile: ResourceAddress | None = None
    output_animation_name: str | None = None
    output_name_mode: str | None = None
    requires_custom_animation_patch: bool = False
    last_preview: ResourceAddress | None = None
    last_export: ResourceAddress | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "mode": self.mode,
            "source": _address_to_dict(self.source),
            "target": _address_to_dict(self.target),
            "profile": _address_to_dict(self.profile),
            "output_animation_name": self.output_animation_name,
            "output_name_mode": self.output_name_mode,
            "requires_custom_animation_patch": self.requires_custom_animation_patch,
            "last_preview": _address_to_dict(self.last_preview),
            "last_export": _address_to_dict(self.last_export),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "RetargetJobRef":
        data = _dict(data)
        return cls(
            id=str(data.get("id") or ""),
            mode=str(data.get("mode") or ""),
            source=_address_or_none(data.get("source")),
            target=_address_or_none(data.get("target")),
            profile=_address_or_none(data.get("profile")),
            output_animation_name=str(data["output_animation_name"])
            if data.get("output_animation_name") is not None
            else None,
            output_name_mode=str(data["output_name_mode"]) if data.get("output_name_mode") is not None else None,
            requires_custom_animation_patch=bool(data.get("requires_custom_animation_patch", False)),
            last_preview=_address_or_none(data.get("last_preview")),
            last_export=_address_or_none(data.get("last_export")),
            metadata=_dict(data.get("metadata")),
        )


@dataclass
class ModuleWorkspaceRef:
    id: str
    module_id: str
    game: str | None
    base_module: ResourceAddress | None = None
    edited_resources: list[ResourceAddress] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "module_id": self.module_id,
            "game": self.game,
            "base_module": _address_to_dict(self.base_module),
            "edited_resources": _addresses_to_list(self.edited_resources),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ModuleWorkspaceRef":
        data = _dict(data)
        return cls(
            id=str(data.get("id") or ""),
            module_id=str(data.get("module_id") or ""),
            game=str(data["game"]) if data.get("game") is not None else None,
            base_module=_address_or_none(data.get("base_module")),
            edited_resources=_addresses_from_list(data.get("edited_resources")),
            metadata=_dict(data.get("metadata")),
        )


@dataclass
class MapProjectRef:
    id: str
    kmap_address: ResourceAddress | None = None
    kmax_scene_address: ResourceAddress | None = None
    module_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kmap_address": _address_to_dict(self.kmap_address),
            "kmax_scene_address": _address_to_dict(self.kmax_scene_address),
            "module_id": self.module_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "MapProjectRef":
        data = _dict(data)
        return cls(
            id=str(data.get("id") or ""),
            kmap_address=_address_or_none(data.get("kmap_address")),
            kmax_scene_address=_address_or_none(data.get("kmax_scene_address")),
            module_id=str(data["module_id"]) if data.get("module_id") is not None else None,
            metadata=_dict(data.get("metadata")),
        )


@dataclass
class ScenarioPackageRef:
    id: str
    module_ids: list[str] = field(default_factory=list)
    actors: list[ResourceAddress] = field(default_factory=list)
    scripts: list[ResourceAddress] = field(default_factory=list)
    dialogs: list[ResourceAddress] = field(default_factory=list)
    sequences: list[ResourceAddress] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "module_ids": list(self.module_ids),
            "actors": _addresses_to_list(self.actors),
            "scripts": _addresses_to_list(self.scripts),
            "dialogs": _addresses_to_list(self.dialogs),
            "sequences": _addresses_to_list(self.sequences),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ScenarioPackageRef":
        data = _dict(data)
        return cls(
            id=str(data.get("id") or ""),
            module_ids=[str(value) for value in (data.get("module_ids") or [])],
            actors=_addresses_from_list(data.get("actors")),
            scripts=_addresses_from_list(data.get("scripts")),
            dialogs=_addresses_from_list(data.get("dialogs")),
            sequences=_addresses_from_list(data.get("sequences")),
            metadata=_dict(data.get("metadata")),
        )


@dataclass
class ValidationSnapshotRef:
    id: str
    address: ResourceAddress | None = None
    label: str | None = None
    issue_count: int = 0
    blocking_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "address": _address_to_dict(self.address),
            "label": self.label,
            "issue_count": int(self.issue_count),
            "blocking_count": int(self.blocking_count),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ValidationSnapshotRef":
        data = _dict(data)
        return cls(
            id=str(data.get("id") or ""),
            address=_address_or_none(data.get("address")),
            label=str(data["label"]) if data.get("label") is not None else None,
            issue_count=int(data.get("issue_count") or 0),
            blocking_count=int(data.get("blocking_count") or 0),
            metadata=_dict(data.get("metadata")),
        )


@dataclass
class ExportCandidateRef:
    id: str
    kind: str
    outputs: list[ResourceAddress] = field(default_factory=list)
    manifest: ResourceAddress | None = None
    verified: bool = False
    validation_snapshot: ResourceAddress | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "outputs": _addresses_to_list(self.outputs),
            "manifest": _address_to_dict(self.manifest),
            "verified": bool(self.verified),
            "validation_snapshot": _address_to_dict(self.validation_snapshot),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ExportCandidateRef":
        data = _dict(data)
        return cls(
            id=str(data.get("id") or ""),
            kind=str(data.get("kind") or ""),
            outputs=_addresses_from_list(data.get("outputs")),
            manifest=_address_or_none(data.get("manifest")),
            verified=bool(data.get("verified", False)),
            validation_snapshot=_address_or_none(data.get("validation_snapshot")),
            metadata=_dict(data.get("metadata")),
        )


@dataclass
class GhostRiggerProject:
    schema_version: int
    project_id: str
    name: str
    created_at_utc: str
    updated_at_utc: str
    game_install_refs: list[GameInstallRef] = field(default_factory=list)
    imported_assets: list[ProjectAssetRef] = field(default_factory=list)
    character_jobs: list[CharacterJobRef] = field(default_factory=list)
    retarget_jobs: list[RetargetJobRef] = field(default_factory=list)
    module_workspaces: list[ModuleWorkspaceRef] = field(default_factory=list)
    map_projects: list[MapProjectRef] = field(default_factory=list)
    scenario_packages: list[ScenarioPackageRef] = field(default_factory=list)
    validation_snapshots: list[ValidationSnapshotRef] = field(default_factory=list)
    export_candidates: list[ExportCandidateRef] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(cls, name: str = "Untitled GhostRigger Project") -> "GhostRiggerProject":
        now = utc_now_iso()
        return cls(
            schema_version=CURRENT_GHOSTRIGGER_PROJECT_SCHEMA_VERSION,
            project_id=stable_project_id(),
            name=name or "Untitled GhostRigger Project",
            created_at_utc=now,
            updated_at_utc=now,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_type": GHOSTRIGGER_PROJECT_FILE_TYPE,
            "schema_version": int(self.schema_version),
            "project_id": self.project_id,
            "name": self.name,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "game_install_refs": [item.to_dict() for item in self.game_install_refs],
            "imported_assets": [item.to_dict() for item in self.imported_assets],
            "character_jobs": [item.to_dict() for item in self.character_jobs],
            "retarget_jobs": [item.to_dict() for item in self.retarget_jobs],
            "module_workspaces": [item.to_dict() for item in self.module_workspaces],
            "map_projects": [item.to_dict() for item in self.map_projects],
            "scenario_packages": [item.to_dict() for item in self.scenario_packages],
            "validation_snapshots": [item.to_dict() for item in self.validation_snapshots],
            "export_candidates": [item.to_dict() for item in self.export_candidates],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "GhostRiggerProject":
        if not isinstance(data, dict):
            raise ValueError("GhostRigger project root must be a JSON object.")
        version = int(data.get("schema_version") or 0)
        if version > CURRENT_GHOSTRIGGER_PROJECT_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported GhostRigger project schema version {version}. "
                f"This build supports version {CURRENT_GHOSTRIGGER_PROJECT_SCHEMA_VERSION}."
            )
        if version != CURRENT_GHOSTRIGGER_PROJECT_SCHEMA_VERSION:
            raise ValueError(f"GhostRigger project schema_version must be {CURRENT_GHOSTRIGGER_PROJECT_SCHEMA_VERSION}.")
        return cls(
            schema_version=version,
            project_id=str(data.get("project_id") or ""),
            name=str(data.get("name") or "Untitled GhostRigger Project"),
            created_at_utc=str(data.get("created_at_utc") or ""),
            updated_at_utc=str(data.get("updated_at_utc") or ""),
            game_install_refs=[GameInstallRef.from_dict(item) for item in data.get("game_install_refs", []) or []],
            imported_assets=[ProjectAssetRef.from_dict(item) for item in data.get("imported_assets", []) or []],
            character_jobs=[CharacterJobRef.from_dict(item) for item in data.get("character_jobs", []) or []],
            retarget_jobs=[RetargetJobRef.from_dict(item) for item in data.get("retarget_jobs", []) or []],
            module_workspaces=[
                ModuleWorkspaceRef.from_dict(item) for item in data.get("module_workspaces", []) or []
            ],
            map_projects=[MapProjectRef.from_dict(item) for item in data.get("map_projects", []) or []],
            scenario_packages=[
                ScenarioPackageRef.from_dict(item) for item in data.get("scenario_packages", []) or []
            ],
            validation_snapshots=[
                ValidationSnapshotRef.from_dict(item) for item in data.get("validation_snapshots", []) or []
            ],
            export_candidates=[
                ExportCandidateRef.from_dict(item) for item in data.get("export_candidates", []) or []
            ],
            metadata=_dict(data.get("metadata")),
        )


def save_ghostrigger_project(project: GhostRiggerProject, path: str | Path) -> None:
    target = Path(path)
    data = project.to_dict()
    try:
        payload = json.dumps(data, indent=2, sort_keys=True)
    except TypeError as exc:
        raise ValueError(f"GhostRigger project contains non-JSON-serializable data: {exc}") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload + "\n", encoding="utf-8")


def load_ghostrigger_project(path: str | Path) -> GhostRiggerProject:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid GhostRigger project JSON: {exc}") from exc
    return GhostRiggerProject.from_dict(data)
