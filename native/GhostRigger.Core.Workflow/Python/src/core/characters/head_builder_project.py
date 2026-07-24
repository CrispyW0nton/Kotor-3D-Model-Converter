"""Versioned, Qt-free project state for the Custom Head Builder.

The Head Builder is a multi-step product workflow.  This module owns the
durable state shared by Workflow, Project, Validation, Tools, and GUI callers;
it deliberately performs no filesystem IO, game-resource loading, rendering,
or Qt work.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Any, Mapping
from uuid import uuid4


HEAD_BUILDER_PROJECT_SCHEMA = "ghostrigger.head_builder_project"
HEAD_BUILDER_PROJECT_VERSION = 2
HEAD_BUILDER_PROJECT_EXTENSION = ".ghosthead.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HeadBuilderGame(str, Enum):
    K1 = "K1"
    K2 = "K2"


class ResourceView(str, Enum):
    STOCK_ONLY = "stock_only"
    EFFECTIVE_OVERRIDE = "effective_override"


class ResourceOrigin(str, Enum):
    CHITIN_BIF = "chitin_bif"
    MODULE = "module"
    OVERRIDE = "override"
    PROJECT_FILE = "project_file"
    IMPORTED_FILE = "imported_file"
    GENERATED = "generated"


class HeadBuilderStep(IntEnum):
    PROJECT_GAME = 1
    IMPORT_CUSTOM_ART = 2
    SELECT_NATIVE_DONOR = 3
    ALIGN_NECK_AND_HOOK = 4
    REPLACE_GEOMETRY_AND_SKIN = 5
    UV_TEXTURES_AND_MATERIALS = 6
    ATTACHMENT_AND_ANIMATION_PREVIEW = 7
    OPTIONAL_HAIR_PHYSICS = 8
    BINARY_PREFLIGHT = 9
    GAME_RECORDS_AND_PACKAGE = 10
    SAFE_RETAIL_TEST = 11

    @property
    def key(self) -> str:
        return {
            self.PROJECT_GAME: "project_game",
            self.IMPORT_CUSTOM_ART: "import_custom_art",
            self.SELECT_NATIVE_DONOR: "select_native_donor",
            self.ALIGN_NECK_AND_HOOK: "align_neck_and_hook",
            self.REPLACE_GEOMETRY_AND_SKIN: "replace_geometry_and_skin",
            self.UV_TEXTURES_AND_MATERIALS: "uv_textures_and_materials",
            self.ATTACHMENT_AND_ANIMATION_PREVIEW: "attachment_and_animation_preview",
            self.OPTIONAL_HAIR_PHYSICS: "optional_hair_physics",
            self.BINARY_PREFLIGHT: "binary_preflight",
            self.GAME_RECORDS_AND_PACKAGE: "game_records_and_package",
            self.SAFE_RETAIL_TEST: "safe_retail_test",
        }[self]

    @property
    def label(self) -> str:
        return {
            self.PROJECT_GAME: "Project and game",
            self.IMPORT_CUSTOM_ART: "Import custom art",
            self.SELECT_NATIVE_DONOR: "Select native donor",
            self.ALIGN_NECK_AND_HOOK: "Align neck seam and head hook",
            self.REPLACE_GEOMETRY_AND_SKIN: "Replace donor geometry and skin",
            self.UV_TEXTURES_AND_MATERIALS: "UVs, textures, and materials",
            self.ATTACHMENT_AND_ANIMATION_PREVIEW: "Attachment and animation preview",
            self.OPTIONAL_HAIR_PHYSICS: "Optional hair/accessory physics",
            self.BINARY_PREFLIGHT: "Binary preflight",
            self.GAME_RECORDS_AND_PACKAGE: "Game records and package",
            self.SAFE_RETAIL_TEST: "Safe retail test",
        }[self]

    @classmethod
    def coerce(cls, value: Any) -> "HeadBuilderStep":
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            return cls(value)
        text = str(value or "").strip()
        if text.isdigit():
            return cls(int(text))
        normalized = text.casefold()
        for step in cls:
            if normalized in {step.name.casefold(), step.key.casefold()}:
                return step
        raise ValueError(f"Unknown Head Builder step: {value!r}")


class StepStatus(str, Enum):
    NOT_STARTED = "not_started"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETE = "complete"


class EvidenceLevel(str, Enum):
    STRUCTURAL = "structural"
    EDITOR_VISUAL = "editor_visual"
    RETAIL_OBSERVED = "retail_observed"
    NOT_TESTED = "not_tested"


class EvidenceOutcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    NOT_TESTED = "not_tested"


@dataclass(slots=True)
class StepProgress:
    status: StepStatus = StepStatus.NOT_STARTED
    completed_at: str = ""
    evidence_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.status = StepStatus(self.status)
        self.evidence_ids = [str(value) for value in self.evidence_ids if str(value)]
        if self.status is not StepStatus.COMPLETE:
            self.completed_at = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "completed_at": self.completed_at,
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StepProgress":
        return cls(
            status=StepStatus(str(payload.get("status") or StepStatus.NOT_STARTED.value)),
            completed_at=str(payload.get("completed_at") or ""),
            evidence_ids=list(payload.get("evidence_ids") or []),
        )


@dataclass(slots=True)
class ResourceProvenance:
    """Source identity for a game, donor, custom-art, or generated resource."""

    resource_id: str
    resource_type: str
    resref: str = ""
    origin: ResourceOrigin = ResourceOrigin.PROJECT_FILE
    source_path: str = ""
    container: str = ""
    sha256: str = ""
    stock: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.resource_id = str(self.resource_id or "").strip()
        self.resource_type = str(self.resource_type or "").strip()
        if not self.resource_id:
            raise ValueError("Head Builder resources require a stable resource_id")
        if not self.resource_type:
            raise ValueError("Head Builder resources require a resource_type")
        self.resref = str(self.resref or "").strip()
        self.origin = ResourceOrigin(self.origin)
        self.source_path = str(self.source_path or "")
        self.container = str(self.container or "")
        self.sha256 = str(self.sha256 or "").strip().upper()
        self.metadata = deepcopy(dict(self.metadata or {}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "resref": self.resref,
            "origin": self.origin.value,
            "source_path": self.source_path,
            "container": self.container,
            "sha256": self.sha256,
            "stock": bool(self.stock),
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ResourceProvenance":
        return cls(
            resource_id=str(payload.get("resource_id") or ""),
            resource_type=str(payload.get("resource_type") or ""),
            resref=str(payload.get("resref") or ""),
            origin=ResourceOrigin(
                str(payload.get("origin") or ResourceOrigin.PROJECT_FILE.value)
            ),
            source_path=str(payload.get("source_path") or ""),
            container=str(payload.get("container") or ""),
            sha256=str(payload.get("sha256") or ""),
            stock=bool(payload.get("stock", False)),
            metadata=deepcopy(dict(payload.get("metadata") or {})),
        )


@dataclass(slots=True)
class EvidenceRecord:
    """One honestly labelled validation or proof result."""

    evidence_id: str
    check_id: str
    label: str
    level: EvidenceLevel
    outcome: EvidenceOutcome
    message: str = ""
    recorded_at: str = field(default_factory=_utc_now)
    artifact_paths: list[str] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)
    observer_session: str = ""
    confirmed_by_user: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.evidence_id = str(self.evidence_id or "").strip()
        self.check_id = str(self.check_id or "").strip()
        self.label = str(self.label or "").strip()
        if not self.evidence_id or not self.check_id or not self.label:
            raise ValueError("Evidence requires evidence_id, check_id, and label")
        self.level = EvidenceLevel(self.level)
        self.outcome = EvidenceOutcome(self.outcome)
        self.message = str(self.message or "")
        self.recorded_at = str(self.recorded_at or _utc_now())
        self.artifact_paths = [
            str(value) for value in self.artifact_paths if str(value)
        ]
        self.hashes = {
            str(key): str(value).upper()
            for key, value in dict(self.hashes or {}).items()
        }
        self.observer_session = str(self.observer_session or "").strip()
        self.metadata = deepcopy(dict(self.metadata or {}))
        if self.level is EvidenceLevel.NOT_TESTED:
            if self.outcome is not EvidenceOutcome.NOT_TESTED:
                raise ValueError("Not-tested evidence must use the not_tested outcome")
        elif self.outcome is EvidenceOutcome.NOT_TESTED:
            raise ValueError("A not_tested outcome must use the not_tested evidence level")
        if (
            self.level is EvidenceLevel.RETAIL_OBSERVED
            and self.outcome is EvidenceOutcome.PASS
        ):
            if not self.confirmed_by_user:
                raise ValueError(
                    "Retail-observed pass requires explicit user confirmation"
                )
            if not self.observer_session:
                raise ValueError(
                    "Retail-observed pass requires an observer session identifier"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "check_id": self.check_id,
            "label": self.label,
            "level": self.level.value,
            "outcome": self.outcome.value,
            "message": self.message,
            "recorded_at": self.recorded_at,
            "artifact_paths": list(self.artifact_paths),
            "hashes": dict(self.hashes),
            "observer_session": self.observer_session,
            "confirmed_by_user": bool(self.confirmed_by_user),
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvidenceRecord":
        return cls(
            evidence_id=str(payload.get("evidence_id") or ""),
            check_id=str(payload.get("check_id") or ""),
            label=str(payload.get("label") or ""),
            level=EvidenceLevel(
                str(payload.get("level") or EvidenceLevel.NOT_TESTED.value)
            ),
            outcome=EvidenceOutcome(
                str(payload.get("outcome") or EvidenceOutcome.NOT_TESTED.value)
            ),
            message=str(payload.get("message") or ""),
            recorded_at=str(payload.get("recorded_at") or _utc_now()),
            artifact_paths=list(payload.get("artifact_paths") or []),
            hashes=dict(payload.get("hashes") or {}),
            observer_session=str(payload.get("observer_session") or ""),
            confirmed_by_user=bool(payload.get("confirmed_by_user", False)),
            metadata=deepcopy(dict(payload.get("metadata") or {})),
        )


def _default_step_progress() -> dict[HeadBuilderStep, StepProgress]:
    return {
        step: StepProgress(
            status=(
                StepStatus.READY
                if step is HeadBuilderStep.PROJECT_GAME
                else StepStatus.NOT_STARTED
            )
        )
        for step in HeadBuilderStep
    }


@dataclass(slots=True)
class HeadBuilderProject:
    """Serializable state shared by every Head Builder product layer."""

    project_id: str
    display_name: str
    created_at: str
    updated_at: str
    game: HeadBuilderGame = HeadBuilderGame.K2
    resource_view: ResourceView = ResourceView.STOCK_ONLY
    current_step: HeadBuilderStep = HeadBuilderStep.PROJECT_GAME
    workflow_steps: dict[HeadBuilderStep, StepProgress] = field(
        default_factory=_default_step_progress
    )
    game_install_dir: str = ""
    output_project_dir: str = ""
    output_head_resref: str = ""
    character_context: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, ResourceProvenance] = field(default_factory=dict)
    import_art: dict[str, Any] = field(default_factory=dict)
    donor_contract: dict[str, Any] = field(default_factory=dict)
    appearance_customization: dict[str, Any] = field(default_factory=dict)
    alignment: dict[str, Any] = field(default_factory=dict)
    skin_transfer: dict[str, Any] = field(default_factory=dict)
    texture_materials: dict[str, Any] = field(default_factory=dict)
    attachment_preview: dict[str, Any] = field(default_factory=dict)
    physics: dict[str, Any] = field(default_factory=dict)
    validation_results: list[EvidenceRecord] = field(default_factory=list)
    export_plan: dict[str, Any] = field(default_factory=dict)
    package_state: dict[str, Any] = field(default_factory=dict)
    retail_test: dict[str, Any] = field(default_factory=dict)
    acknowledged_warnings: list[str] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.project_id = str(self.project_id or "").strip()
        if not self.project_id:
            raise ValueError("Head Builder project_id cannot be blank")
        self.display_name = str(self.display_name or "").strip() or "Untitled Head"
        self.created_at = str(self.created_at or _utc_now())
        self.updated_at = str(self.updated_at or self.created_at)
        self.game = HeadBuilderGame(self.game)
        self.resource_view = ResourceView(self.resource_view)
        self.current_step = HeadBuilderStep.coerce(self.current_step)
        normalized_steps = _default_step_progress()
        for raw_step, progress in dict(self.workflow_steps or {}).items():
            step = HeadBuilderStep.coerce(raw_step)
            normalized_steps[step] = (
                progress
                if isinstance(progress, StepProgress)
                else StepProgress.from_dict(dict(progress))
            )
        self.workflow_steps = normalized_steps
        self.resources = {
            str(resource_id): (
                resource
                if isinstance(resource, ResourceProvenance)
                else ResourceProvenance.from_dict(dict(resource))
            )
            for resource_id, resource in dict(self.resources or {}).items()
        }
        for resource_id, resource in self.resources.items():
            if resource_id != resource.resource_id:
                raise ValueError(
                    f"Resource key {resource_id!r} does not match "
                    f"resource_id {resource.resource_id!r}"
                )
        self.validation_results = [
            row if isinstance(row, EvidenceRecord) else EvidenceRecord.from_dict(row)
            for row in list(self.validation_results or [])
        ]
        evidence_ids = [row.evidence_id for row in self.validation_results]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Head Builder evidence_id values must be unique")
        self.acknowledged_warnings = [
            str(value) for value in self.acknowledged_warnings if str(value)
        ]
        for name in (
            "character_context",
            "import_art",
            "donor_contract",
            "appearance_customization",
            "alignment",
            "skin_transfer",
            "texture_materials",
            "attachment_preview",
            "physics",
            "export_plan",
            "package_state",
            "retail_test",
            "extensions",
        ):
            setattr(self, name, deepcopy(dict(getattr(self, name) or {})))

    @classmethod
    def new(
        cls,
        *,
        display_name: str = "Untitled Head",
        game: HeadBuilderGame = HeadBuilderGame.K2,
    ) -> "HeadBuilderProject":
        now = _utc_now()
        return cls(
            project_id=str(uuid4()),
            display_name=display_name,
            created_at=now,
            updated_at=now,
            game=game,
        )

    def touch(self) -> None:
        self.updated_at = _utc_now()

    def set_current_step(self, step: HeadBuilderStep | int | str) -> None:
        self.current_step = HeadBuilderStep.coerce(step)
        progress = self.workflow_steps[self.current_step]
        if progress.status is StepStatus.NOT_STARTED:
            progress.status = StepStatus.READY
        self.touch()

    def mark_step(
        self,
        step: HeadBuilderStep | int | str,
        status: StepStatus | str,
        *,
        evidence_ids: list[str] | None = None,
    ) -> None:
        normalized_step = HeadBuilderStep.coerce(step)
        normalized_status = StepStatus(status)
        known_evidence = {row.evidence_id for row in self.validation_results}
        requested_evidence = [
            str(value) for value in (evidence_ids or []) if str(value)
        ]
        unknown = sorted(set(requested_evidence) - known_evidence)
        if unknown:
            raise ValueError(
                "Step progress references unknown evidence: " + ", ".join(unknown)
            )
        if (
            normalized_step is HeadBuilderStep.SAFE_RETAIL_TEST
            and normalized_status is StepStatus.COMPLETE
        ):
            evidence_by_id = {
                row.evidence_id: row for row in self.validation_results
            }
            has_retail_pass = any(
                evidence_by_id[evidence_id].level
                is EvidenceLevel.RETAIL_OBSERVED
                and evidence_by_id[evidence_id].outcome is EvidenceOutcome.PASS
                for evidence_id in requested_evidence
            )
            if not has_retail_pass:
                raise ValueError(
                    "Safe retail test completion requires referenced "
                    "retail-observed passing evidence"
                )
        progress = self.workflow_steps[normalized_step]
        progress.status = normalized_status
        progress.evidence_ids = requested_evidence
        progress.completed_at = (
            _utc_now() if normalized_status is StepStatus.COMPLETE else ""
        )
        self.touch()

    def put_resource(self, resource: ResourceProvenance) -> None:
        if not isinstance(resource, ResourceProvenance):
            raise TypeError("put_resource expects ResourceProvenance")
        self.resources[resource.resource_id] = resource
        self.touch()

    def record_evidence(self, record: EvidenceRecord) -> None:
        if not isinstance(record, EvidenceRecord):
            raise TypeError("record_evidence expects EvidenceRecord")
        for index, existing in enumerate(self.validation_results):
            if existing.evidence_id == record.evidence_id:
                self.validation_results[index] = record
                self.touch()
                return
        self.validation_results.append(record)
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": HEAD_BUILDER_PROJECT_SCHEMA,
            "version": HEAD_BUILDER_PROJECT_VERSION,
            "project_id": self.project_id,
            "display_name": self.display_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "game": self.game.value,
            "resource_view": self.resource_view.value,
            "game_install_dir": self.game_install_dir,
            "output_project_dir": self.output_project_dir,
            "output_head_resref": self.output_head_resref,
            "character_context": deepcopy(self.character_context),
            "workflow": {
                "current_step": int(self.current_step),
                "steps": {
                    step.key: self.workflow_steps[step].to_dict()
                    for step in HeadBuilderStep
                },
            },
            "resources": [
                self.resources[key].to_dict() for key in sorted(self.resources)
            ],
            "import_art": deepcopy(self.import_art),
            "donor_contract": deepcopy(self.donor_contract),
            "appearance_customization": deepcopy(
                self.appearance_customization
            ),
            "alignment": deepcopy(self.alignment),
            "skin_transfer": deepcopy(self.skin_transfer),
            "texture_materials": deepcopy(self.texture_materials),
            "attachment_preview": deepcopy(self.attachment_preview),
            "physics": deepcopy(self.physics),
            "validation_results": [
                record.to_dict() for record in self.validation_results
            ],
            "export_plan": deepcopy(self.export_plan),
            "package_state": deepcopy(self.package_state),
            "retail_test": deepcopy(self.retail_test),
            "acknowledged_warnings": list(self.acknowledged_warnings),
            "extensions": deepcopy(
                {
                    key: value
                    for key, value in self.extensions.items()
                    if key != "_unknown_top_level"
                }
            ),
        }
        unknown = self.extensions.get("_unknown_top_level")
        if isinstance(unknown, Mapping):
            for key, value in unknown.items():
                if key not in payload:
                    payload[str(key)] = deepcopy(value)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HeadBuilderProject":
        raw = deepcopy(dict(payload))
        schema = str(raw.get("schema") or "")
        if schema != HEAD_BUILDER_PROJECT_SCHEMA:
            raise ValueError(
                f"Unsupported Head Builder project schema: {schema!r}"
            )
        version = int(raw.get("version") or 0)
        if version < 1 or version > HEAD_BUILDER_PROJECT_VERSION:
            raise ValueError(
                f"Unsupported Head Builder project version: {version}"
            )
        workflow = dict(raw.get("workflow") or {})
        raw_steps = dict(workflow.get("steps") or {})
        steps = {
            HeadBuilderStep.coerce(step_key): StepProgress.from_dict(
                dict(step_payload or {})
            )
            for step_key, step_payload in raw_steps.items()
        }
        resources = {
            resource.resource_id: resource
            for resource in (
                ResourceProvenance.from_dict(dict(row))
                for row in list(raw.get("resources") or [])
            )
        }
        known_keys = {
            "schema",
            "version",
            "project_id",
            "display_name",
            "created_at",
            "updated_at",
            "game",
            "resource_view",
            "game_install_dir",
            "output_project_dir",
            "output_head_resref",
            "character_context",
            "workflow",
            "resources",
            "import_art",
            "donor_contract",
            "appearance_customization",
            "alignment",
            "skin_transfer",
            "texture_materials",
            "attachment_preview",
            "physics",
            "validation_results",
            "export_plan",
            "package_state",
            "retail_test",
            "acknowledged_warnings",
            "extensions",
        }
        extensions = deepcopy(dict(raw.get("extensions") or {}))
        unknown = {
            key: deepcopy(value)
            for key, value in raw.items()
            if key not in known_keys
        }
        if unknown:
            extensions["_unknown_top_level"] = unknown
        return cls(
            project_id=str(raw.get("project_id") or ""),
            display_name=str(raw.get("display_name") or ""),
            created_at=str(raw.get("created_at") or ""),
            updated_at=str(raw.get("updated_at") or ""),
            game=HeadBuilderGame(str(raw.get("game") or HeadBuilderGame.K2.value)),
            resource_view=ResourceView(
                str(raw.get("resource_view") or ResourceView.STOCK_ONLY.value)
            ),
            current_step=HeadBuilderStep.coerce(
                workflow.get("current_step", HeadBuilderStep.PROJECT_GAME)
            ),
            workflow_steps=steps,
            game_install_dir=str(raw.get("game_install_dir") or ""),
            output_project_dir=str(raw.get("output_project_dir") or ""),
            output_head_resref=str(raw.get("output_head_resref") or ""),
            character_context=deepcopy(dict(raw.get("character_context") or {})),
            resources=resources,
            import_art=deepcopy(dict(raw.get("import_art") or {})),
            donor_contract=deepcopy(dict(raw.get("donor_contract") or {})),
            appearance_customization=deepcopy(
                dict(raw.get("appearance_customization") or {})
            ),
            alignment=deepcopy(dict(raw.get("alignment") or {})),
            skin_transfer=deepcopy(dict(raw.get("skin_transfer") or {})),
            texture_materials=deepcopy(dict(raw.get("texture_materials") or {})),
            attachment_preview=deepcopy(
                dict(raw.get("attachment_preview") or {})
            ),
            physics=deepcopy(dict(raw.get("physics") or {})),
            validation_results=[
                EvidenceRecord.from_dict(dict(row))
                for row in list(raw.get("validation_results") or [])
            ],
            export_plan=deepcopy(dict(raw.get("export_plan") or {})),
            package_state=deepcopy(dict(raw.get("package_state") or {})),
            retail_test=deepcopy(dict(raw.get("retail_test") or {})),
            acknowledged_warnings=list(raw.get("acknowledged_warnings") or []),
            extensions=extensions,
        )


__all__ = [
    "EvidenceLevel",
    "EvidenceOutcome",
    "EvidenceRecord",
    "HEAD_BUILDER_PROJECT_EXTENSION",
    "HEAD_BUILDER_PROJECT_SCHEMA",
    "HEAD_BUILDER_PROJECT_VERSION",
    "HeadBuilderGame",
    "HeadBuilderProject",
    "HeadBuilderStep",
    "ResourceOrigin",
    "ResourceProvenance",
    "ResourceView",
    "StepProgress",
    "StepStatus",
]
