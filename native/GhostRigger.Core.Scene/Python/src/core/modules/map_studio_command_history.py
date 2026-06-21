"""Undo/redo command history for Map Studio KMAP mutations.

The history stores serialized KMAP snapshots plus editor selection context so
Map Studio tools can remain headless commands while the Qt window stays a thin
caller.  It deliberately records authored-resource/readiness metadata because
modeling commands stale MDL/MDX/WOK/LYT/VIS/PTH/.mod proof even when no files
are written immediately.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from src.core.level import KMapProject, KMapSerializer


@dataclass(frozen=True)
class MapStudioProjectSnapshot:
    """Serializable editor state before or after one Map Studio command."""

    data: dict[str, Any]
    path: str = ""
    dirty: bool = False
    selected_ids: tuple[str, ...] = ()
    active_module_id: str = ""
    active_room_id: str = ""


@dataclass(frozen=True)
class MapStudioCommandRecord:
    """One undoable Map Studio command with KOTOR output impact metadata."""

    action_key: str
    label: str
    before: MapStudioProjectSnapshot
    after: MapStudioProjectSnapshot
    stale_outputs: tuple[str, ...] = ()
    readiness_impact: str = ""
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MapStudioCommandRestoreResult:
    """Restored KMAP project plus editor context after undo or redo."""

    project: KMapProject
    selected_ids: tuple[str, ...]
    active_module_id: str
    active_room_id: str
    record: MapStudioCommandRecord
    direction: str
    message: str


class MapStudioCommandHistory:
    """Bounded undo/redo stack for authored Map Studio project commands."""

    def __init__(self, max_depth: int = 100) -> None:
        self.max_depth = max(1, int(max_depth))
        self.undo_stack: list[MapStudioCommandRecord] = []
        self.redo_stack: list[MapStudioCommandRecord] = []

    @property
    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    @property
    def undo_label(self) -> str:
        return self.undo_stack[-1].label if self.undo_stack else ""

    @property
    def redo_label(self) -> str:
        return self.redo_stack[-1].label if self.redo_stack else ""

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()

    def capture(
        self,
        project: KMapProject,
        *,
        selected_ids: tuple[str, ...] | list[str] = (),
        active_module_id: str = "",
        active_room_id: str = "",
    ) -> MapStudioProjectSnapshot:
        """Capture a deep, serializer-backed snapshot of the current editor state."""

        return MapStudioProjectSnapshot(
            data=deepcopy(KMapSerializer.to_dict(project)),
            path=str(getattr(project, "path", "") or ""),
            dirty=bool(getattr(project, "dirty", False)),
            selected_ids=tuple(str(value) for value in selected_ids if value),
            active_module_id=str(active_module_id or ""),
            active_room_id=str(active_room_id or ""),
        )

    def record(
        self,
        *,
        action_key: str,
        label: str,
        before: MapStudioProjectSnapshot,
        after: MapStudioProjectSnapshot,
        stale_outputs: tuple[str, ...] = (),
        readiness_impact: str = "",
        summary: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> MapStudioCommandRecord | None:
        """Record one command unless the captured state is unchanged."""

        if before == after:
            return None
        record = MapStudioCommandRecord(
            action_key=str(action_key or "map_studio.command"),
            label=str(label or "Map Studio command"),
            before=before,
            after=after,
            stale_outputs=tuple(str(value) for value in stale_outputs if value),
            readiness_impact=str(readiness_impact or ""),
            summary=str(summary or ""),
            metadata=dict(metadata or {}),
        )
        self.undo_stack.append(record)
        if len(self.undo_stack) > self.max_depth:
            del self.undo_stack[0 : len(self.undo_stack) - self.max_depth]
        self.redo_stack.clear()
        return record

    def undo(self) -> MapStudioCommandRestoreResult | None:
        if not self.undo_stack:
            return None
        record = self.undo_stack.pop()
        self.redo_stack.append(record)
        return self._restore(record=record, snapshot=record.before, direction="undo")

    def redo(self) -> MapStudioCommandRestoreResult | None:
        if not self.redo_stack:
            return None
        record = self.redo_stack.pop()
        self.undo_stack.append(record)
        return self._restore(record=record, snapshot=record.after, direction="redo")

    def _restore(
        self,
        *,
        record: MapStudioCommandRecord,
        snapshot: MapStudioProjectSnapshot,
        direction: str,
    ) -> MapStudioCommandRestoreResult:
        project = KMapSerializer.from_dict(deepcopy(snapshot.data))
        project.path = snapshot.path
        project.dirty = True
        verb = "Undid" if direction == "undo" else "Redid"
        stale = f" Stale outputs: {', '.join(record.stale_outputs)}." if record.stale_outputs else ""
        impact = f" {record.readiness_impact}" if record.readiness_impact else ""
        return MapStudioCommandRestoreResult(
            project=project,
            selected_ids=snapshot.selected_ids,
            active_module_id=snapshot.active_module_id,
            active_room_id=snapshot.active_room_id,
            record=record,
            direction=direction,
            message=f"{verb} {record.label}.{stale}{impact}".strip(),
        )


__all__ = [
    "MapStudioCommandHistory",
    "MapStudioCommandRecord",
    "MapStudioCommandRestoreResult",
    "MapStudioProjectSnapshot",
]
