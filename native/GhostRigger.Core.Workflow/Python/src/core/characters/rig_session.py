"""Persistent, revisioned state for the Character Builder rig workflow.

``RigSession`` records the artifacts that already exist in Character Builder;
it does not run landmark detection, correspondence, skinning, or export.  The
contract gives those operations durable stage boundaries so a failed or
cancelled retry cannot silently discard the last valid result.

The dependency graph deliberately keeps body and finger landmarks independent.
Revising either invalidates skeleton/weight/bind/export work, while revising body
landmarks does not erase a separately reviewed finger result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
import math
from pathlib import Path
from typing import Any, ClassVar, Mapping
import uuid


RIG_SESSION_SCHEMA = "ghostrigger.rig_session.v1"
RIG_SESSION_SCHEMA_VERSION = 1
RIG_SESSION_METADATA_KEY = "rig_session"


class RigStage(str, Enum):
    """Stable Character Builder workflow stage identifiers."""

    SOURCE = "source"
    BODY_LANDMARKS = "body_landmarks"
    FINGERS = "fingers"
    SKELETON = "skeleton"
    CORRESPONDENCE = "correspondence"
    WEIGHTS = "weights"
    BIND = "bind"
    EXPORT = "export"


class RigStageStatus(str, Enum):
    """Lifecycle state for one stage attempt.

    ``STALE`` means that a previous output is still available for inspection,
    but an upstream revision changed and the output must not be treated as the
    current result.
    """

    PENDING = "pending"
    RUNNING = "running"
    VALID = "valid"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALE = "stale"


STAGE_DEPENDENCIES: dict[RigStage, tuple[RigStage, ...]] = {
    RigStage.SOURCE: (),
    RigStage.BODY_LANDMARKS: (RigStage.SOURCE,),
    RigStage.FINGERS: (RigStage.SOURCE,),
    RigStage.SKELETON: (
        RigStage.SOURCE,
        RigStage.BODY_LANDMARKS,
        RigStage.FINGERS,
    ),
    RigStage.CORRESPONDENCE: (RigStage.SOURCE, RigStage.SKELETON),
    RigStage.WEIGHTS: (RigStage.SKELETON, RigStage.CORRESPONDENCE),
    RigStage.BIND: (RigStage.SKELETON, RigStage.WEIGHTS),
    RigStage.EXPORT: (
        RigStage.SOURCE,
        RigStage.SKELETON,
        RigStage.WEIGHTS,
        RigStage.BIND,
    ),
}


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stage(value: RigStage | str) -> RigStage:
    if isinstance(value, RigStage):
        return value
    return RigStage(str(value or "").strip().lower())


def _json_safe(value: Any, *, path: str = "artifact") -> Any:
    """Return a strict JSON-safe copy or raise for runtime/heavy objects."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, Enum):
        return _json_safe(value.value, path=path)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            result[key_text] = _json_safe(item, path=f"{path}.{key_text}")
        return result
    if isinstance(value, (list, tuple)):
        return [
            _json_safe(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise TypeError(
        f"{path} contains unsupported {type(value).__name__}; "
        "store references and editable values, not runtime objects"
    )


@dataclass
class RigStageState:
    """Serializable state and last valid artifact for one rig stage."""

    stage: RigStage
    status: RigStageStatus = RigStageStatus.PENDING
    input_revision: int = 0
    output_revision: int = 0
    cancellable: bool = False
    artifact: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    job_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    invalidated_by: str = ""
    invalidated_revision: int = 0

    @property
    def valid(self) -> bool:
        return self.status is RigStageStatus.VALID

    @property
    def running(self) -> bool:
        return self.status is RigStageStatus.RUNNING

    @property
    def failed(self) -> bool:
        return self.status is RigStageStatus.FAILED

    @property
    def can_cancel(self) -> bool:
        return self.running and self.cancellable

    @property
    def has_preserved_output(self) -> bool:
        """True when a previous successful output remains inspectable."""

        return self.output_revision > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "status": self.status.value,
            "input_revision": int(self.input_revision),
            "output_revision": int(self.output_revision),
            "cancellable": bool(self.cancellable),
            "artifact": _json_safe(self.artifact),
            "error": str(self.error or ""),
            "job_id": str(self.job_id or ""),
            "started_at": str(self.started_at or ""),
            "completed_at": str(self.completed_at or ""),
            "invalidated_by": str(self.invalidated_by or ""),
            "invalidated_revision": int(self.invalidated_revision),
        }

    @classmethod
    def from_dict(cls, stage: RigStage, payload: Mapping[str, Any]) -> "RigStageState":
        raw_status = str(payload.get("status") or RigStageStatus.PENDING.value)
        try:
            status = RigStageStatus(raw_status)
        except ValueError:
            status = RigStageStatus.PENDING
        error = str(payload.get("error") or "")
        cancellable = bool(payload.get("cancellable", False))
        # A restored process cannot still own an in-flight worker.  Preserve
        # its last output, but report the interrupted attempt honestly.
        if status is RigStageStatus.RUNNING:
            status = RigStageStatus.FAILED
            cancellable = False
            error = error or "Stage was interrupted before the rig session was restored."
        artifact = payload.get("artifact")
        return cls(
            stage=stage,
            status=status,
            input_revision=max(0, int(payload.get("input_revision") or 0)),
            output_revision=max(0, int(payload.get("output_revision") or 0)),
            cancellable=cancellable,
            artifact=_json_safe(artifact if isinstance(artifact, Mapping) else {}),
            error=error,
            job_id="" if status is RigStageStatus.FAILED else str(payload.get("job_id") or ""),
            started_at=str(payload.get("started_at") or ""),
            completed_at=str(payload.get("completed_at") or ""),
            invalidated_by=str(payload.get("invalidated_by") or ""),
            invalidated_revision=max(0, int(payload.get("invalidated_revision") or 0)),
        )


@dataclass
class RigSession:
    """Durable revision graph for one Character Builder scene."""

    schema: str = RIG_SESSION_SCHEMA
    schema_version: int = RIG_SESSION_SCHEMA_VERSION
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    revision: int = 0
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    stages: dict[RigStage, RigStageState] = field(default_factory=dict)

    ORDER: ClassVar[tuple[RigStage, ...]] = tuple(RigStage)

    def __post_init__(self) -> None:
        if not str(self.session_id or "").strip():
            self.session_id = str(uuid.uuid4())
        self.revision = max(0, int(self.revision or 0))
        normalized: dict[RigStage, RigStageState] = {}
        for stage in self.ORDER:
            state = self.stages.get(stage)
            normalized[stage] = (
                state if isinstance(state, RigStageState) else RigStageState(stage=stage)
            )
        self.stages = normalized
        self.revision = max(
            self.revision,
            max((state.output_revision for state in self.stages.values()), default=0),
        )

    def state(self, stage: RigStage | str) -> RigStageState:
        return self.stages[_stage(stage)]

    def dependency_revision(self, stage: RigStage | str) -> int:
        dependencies = STAGE_DEPENDENCIES[_stage(stage)]
        return max(
            (self.stages[item].output_revision for item in dependencies),
            default=0,
        )

    def start_stage(
        self,
        stage: RigStage | str,
        *,
        cancellable: bool = False,
        job_id: str = "",
    ) -> RigStageState:
        """Begin an attempt without discarding the last valid artifact."""

        item = self.state(stage)
        item.status = RigStageStatus.RUNNING
        item.input_revision = self.dependency_revision(item.stage)
        item.cancellable = bool(cancellable)
        item.job_id = str(job_id or (uuid.uuid4() if cancellable else ""))
        item.error = ""
        item.started_at = _utc_now()
        item.completed_at = ""
        item.invalidated_by = ""
        item.invalidated_revision = 0
        self.updated_at = item.started_at
        return item

    def complete_stage(
        self,
        stage: RigStage | str,
        artifact: Mapping[str, Any] | None = None,
    ) -> RigStageState:
        """Commit a valid stage output and invalidate transitive dependants."""

        item = self.state(stage)
        safe_artifact = _json_safe(dict(artifact or {}))
        self.revision += 1
        item.input_revision = self.dependency_revision(item.stage)
        item.output_revision = self.revision
        item.status = RigStageStatus.VALID
        item.cancellable = False
        item.artifact = safe_artifact
        item.error = ""
        item.job_id = ""
        item.completed_at = _utc_now()
        item.invalidated_by = ""
        item.invalidated_revision = 0
        self.updated_at = item.completed_at
        self.invalidate_downstream(item.stage, at_revision=item.output_revision)
        return item

    def fail_stage(self, stage: RigStage | str, error: str) -> RigStageState:
        """Fail the current attempt while retaining any earlier output."""

        item = self.state(stage)
        item.status = RigStageStatus.FAILED
        item.input_revision = self.dependency_revision(item.stage)
        item.cancellable = False
        item.error = str(error or "Stage failed.")
        item.job_id = ""
        item.completed_at = _utc_now()
        self.updated_at = item.completed_at
        return item

    def cancel_stage(self, stage: RigStage | str, reason: str = "") -> RigStageState:
        """Cancel a running cancellable attempt and preserve its last output."""

        item = self.state(stage)
        if not item.running:
            raise RuntimeError(f"Rig stage '{item.stage.value}' is not running")
        if not item.cancellable:
            raise RuntimeError(f"Rig stage '{item.stage.value}' is not cancellable")
        item.status = RigStageStatus.CANCELLED
        item.cancellable = False
        item.error = str(reason or "Stage cancelled.")
        item.job_id = ""
        item.completed_at = _utc_now()
        self.updated_at = item.completed_at
        return item

    def invalidate_downstream(
        self,
        stage: RigStage | str,
        *,
        at_revision: int | None = None,
    ) -> tuple[RigStage, ...]:
        """Mark every transitive dependant stale without deleting artifacts."""

        changed = _stage(stage)
        revision = int(at_revision if at_revision is not None else self.revision)
        invalidated: list[RigStage] = []
        frontier = [changed]
        visited: set[RigStage] = set()
        while frontier:
            upstream = frontier.pop(0)
            for candidate in self.ORDER:
                if candidate in visited or upstream not in STAGE_DEPENDENCIES[candidate]:
                    continue
                visited.add(candidate)
                frontier.append(candidate)
                state = self.stages[candidate]
                if state.output_revision > 0 or state.status is not RigStageStatus.PENDING:
                    state.status = RigStageStatus.STALE
                    state.cancellable = False
                    state.job_id = ""
                    state.error = ""
                    state.invalidated_by = changed.value
                    state.invalidated_revision = revision
                    invalidated.append(candidate)
        return tuple(invalidated)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema": RIG_SESSION_SCHEMA,
            "schema_version": RIG_SESSION_SCHEMA_VERSION,
            "session_id": str(self.session_id),
            "revision": int(self.revision),
            "created_at": str(self.created_at or ""),
            "updated_at": str(self.updated_at or ""),
            "stages": {
                stage.value: self.stages[stage].to_dict()
                for stage in self.ORDER
            },
        }
        # Strict serialization is an intentional guard against accidentally
        # placing KotorModel/NumPy/runtime objects in human-readable scenes.
        json.dumps(payload, ensure_ascii=False, allow_nan=False)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RigSession":
        schema = str(payload.get("schema") or RIG_SESSION_SCHEMA)
        if schema != RIG_SESSION_SCHEMA:
            raise ValueError(f"Unsupported RigSession schema: {schema}")
        version = int(payload.get("schema_version") or 0)
        if version > RIG_SESSION_SCHEMA_VERSION:
            raise ValueError(
                f"RigSession version {version} is newer than supported "
                f"version {RIG_SESSION_SCHEMA_VERSION}"
            )
        raw_stages = payload.get("stages")
        stage_payloads = raw_stages if isinstance(raw_stages, Mapping) else {}
        states: dict[RigStage, RigStageState] = {}
        for stage in cls.ORDER:
            raw = stage_payloads.get(stage.value)
            states[stage] = RigStageState.from_dict(
                stage,
                raw if isinstance(raw, Mapping) else {},
            )
        return cls(
            session_id=str(payload.get("session_id") or uuid.uuid4()),
            revision=max(0, int(payload.get("revision") or 0)),
            created_at=str(payload.get("created_at") or _utc_now()),
            updated_at=str(payload.get("updated_at") or _utc_now()),
            stages=states,
        )

    @classmethod
    def restore_from_metadata(cls, metadata: Mapping[str, Any] | None) -> "RigSession":
        payload = (metadata or {}).get(RIG_SESSION_METADATA_KEY)
        if not isinstance(payload, Mapping):
            return cls()
        return cls.from_dict(payload)

    def store_in_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        metadata[RIG_SESSION_METADATA_KEY] = self.to_dict()
        return metadata


__all__ = [
    "RIG_SESSION_METADATA_KEY",
    "RIG_SESSION_SCHEMA",
    "RIG_SESSION_SCHEMA_VERSION",
    "RigSession",
    "RigStage",
    "RigStageState",
    "RigStageStatus",
    "STAGE_DEPENDENCIES",
]
