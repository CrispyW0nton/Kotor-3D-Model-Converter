"""Composition facade for GhostStudio's integrated Scripting Suite.

The facade keeps the established script/DLG controller, the non-DLG narrative
data controller, and the project/package controller independently testable.
It exposes the small lifecycle surface consumed by the main application while
merging runtime-safe resources for Map Studio handoff.
"""

from __future__ import annotations

from collections import OrderedDict
import hashlib
from pathlib import Path
from typing import Any, Mapping

from PySide6 import QtCore

from src.core.scripting.studio import DialogueDocument, ScriptDocument, ScriptingStudioService
from src.gui.controllers.scripting_blueprint_controller import ScriptingBlueprintController
from src.gui.controllers.scripting_data_controller import ScriptingDataController
from src.gui.controllers.scripting_project_controller import (
    ProjectResourceSnapshot,
    ScriptingProjectController,
)
from src.gui.controllers.scripting_studio_controller import ScriptingStudioController


_SCRIPT_RESOURCE_TYPES = {"nss", "ncs", "dlg"}
_GFF_RESOURCE_TYPES = {
    "utc", "utp", "utd", "uti", "ute", "utm", "uts", "utt", "utw",
    "are", "git", "ifo", "pth", "fac", "gui", "itp", "gff",
}


class ScriptingSuiteController(QtCore.QObject):
    """Stable main-shell facade over the focused Scripting Suite controllers."""

    buildCompleted = QtCore.Signal(str, object)
    buildInvalidated = QtCore.Signal()
    operationFailed = QtCore.Signal(str)
    statusChanged = QtCore.Signal(str)
    diagnosticsChanged = QtCore.Signal(object, str)
    externalAssetRequested = QtCore.Signal(str, object)

    def __init__(
        self,
        window: Any,
        *,
        resource_manager: Any | None = None,
        resource_provider: Any | None = None,
        output_root: str | Path | None = None,
        recent_store_path: str | Path | None = None,
        service: ScriptingStudioService | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.window = window
        self.script_controller = ScriptingStudioController(
            window,
            resource_manager=resource_manager,
            resource_provider=resource_provider,
            output_root=output_root,
            service=service,
            parent=self,
        )
        self.data_controller = ScriptingDataController(
            window,
            script_sink=self._create_scaffold_script,
            game_provider=self._target_game,
            parent=self,
        )
        self.blueprint_controller = ScriptingBlueprintController(
            window,
            game_provider=self._target_game,
            parent=self,
        )
        inferred_recent_path = recent_store_path
        if inferred_recent_path is None and output_root is not None:
            inferred_recent_path = Path(output_root).resolve().parent / "recent-projects.json"
        self.project_controller = ScriptingProjectController(
            window,
            recent_store_path=inferred_recent_path,
            snapshot_provider=self.project_resource_snapshots,
            asset_activator=self._activate_project_asset,
            parent=self,
        )
        self._runtime_resources: tuple[tuple[str, str, bytes], ...] = ()
        self._runtime_output_dir = ""
        self._bind()

    @property
    def service(self) -> ScriptingStudioService:
        return self.script_controller.service

    @property
    def documents(self) -> tuple[dict[str, Any], ...]:
        return self.script_controller.documents

    @property
    def last_build(self):
        return self.script_controller.last_build

    def _bind(self) -> None:
        self.script_controller.buildCompleted.connect(self._on_script_build_completed)
        self.script_controller.compileCompleted.connect(self._publish_script_compiled_event)
        self.script_controller.buildInvalidated.connect(self._invalidate_runtime_build)
        self.data_controller.contentChanged.connect(self._invalidate_runtime_build)
        self.blueprint_controller.contentChanged.connect(self._invalidate_runtime_build)
        for controller in (
            self.script_controller,
            self.data_controller,
            self.blueprint_controller,
            self.project_controller,
        ):
            controller.operationFailed.connect(self.operationFailed.emit)
            status = getattr(controller, "statusChanged", None)
            if status is not None:
                status.connect(self.statusChanged.emit)
        self.script_controller.diagnosticsChanged.connect(self.diagnosticsChanged.emit)
        self.data_controller.diagnosticsChanged.connect(self.diagnosticsChanged.emit)
        self.blueprint_controller.diagnosticsChanged.connect(self.diagnosticsChanged.emit)
        self.project_controller.projectChanged.connect(self._project_changed)
        self.project_controller.legacyQuestOpened.connect(self._open_legacy_quest_payload)

    def _target_game(self) -> str:
        getter = getattr(self.window, "target_game", None)
        return str(getter() if callable(getter) else "K2").upper()

    def _project_changed(self, row: Mapping[str, Any] | object) -> None:
        values = dict(row) if isinstance(row, Mapping) else {}
        game = str(values.get("game") or "")
        setter = getattr(self.window, "set_target_game", None)
        if game and callable(setter):
            setter(game)

    def _open_legacy_quest_payload(self, row: Mapping[str, Any] | object) -> None:
        values = dict(row) if isinstance(row, Mapping) else {}
        content = str(values.get("content") or "")
        if content:
            self.data_controller.open_quest_definition(content.encode("utf-8"))

    def _create_scaffold_script(self, game: str, resref: str, source: str) -> str:
        document_id = self.script_controller.new_script(game, resref)
        self.script_controller.update_script_source(document_id, source)
        return document_id

    # Main-shell compatibility -----------------------------------------

    def open_context(self, context: Mapping[str, Any] | None) -> str:
        return self.script_controller.open_context(context)

    def set_resource_sources(
        self,
        *,
        resource_manager: Any | None = None,
        resource_provider: Any | None = None,
    ) -> None:
        self.script_controller.set_resource_sources(
            resource_manager=resource_manager,
            resource_provider=resource_provider,
        )

    def runtime_resources(self) -> tuple[tuple[str, str, bytes], ...]:
        return self._runtime_resources

    # Preserve the public script/DLG controller surface used by existing
    # automation and tests while the window itself remains wired directly to
    # the focused controller.

    def new_script(self, game: str = "K2", resref: str = "new_script") -> str:
        return self.script_controller.new_script(game, resref)

    def new_dialogue(self, game: str = "K2", resref: str = "new_dialogue") -> str:
        return self.script_controller.new_dialogue(game, resref)

    def open_file(self, path: str | Path, *, game: str = "K2") -> str:
        return self.script_controller.open_file(path, game=game)

    def save_document(self, document_id: str, save_as: bool = False, path: str | Path | None = None) -> bool:
        return self.script_controller.save_document(document_id, save_as=save_as, path=path)

    def save_all(self) -> bool:
        return self.script_controller.save_all()

    def compile_document(self, document_id: str):
        return self.script_controller.compile_document(document_id)

    def validate_document(self, document_id: str):
        return self.script_controller.validate_document(document_id)

    def build_documents(self, game: str = "K2", output_dir: str | Path | None = None):
        return self.script_controller.build_documents(game, output_dir)

    # Project snapshots -------------------------------------------------

    def project_resource_snapshots(self) -> tuple[ProjectResourceSnapshot, ...]:
        """Serialize every open editor surface without writing game data."""

        rows: list[ProjectResourceSnapshot] = []
        for document in tuple(self.script_controller._documents.values()):
            if isinstance(document, ScriptDocument):
                rows.append(
                    ProjectResourceSnapshot(
                        document.resref,
                        "nss",
                        document.source.encode("utf-8"),
                        "source",
                        document.game,
                    )
                )
                compiled = self.script_controller._compiled.get(document.document_id)
                if compiled is not None and compiled.ok:
                    rows.append(
                        ProjectResourceSnapshot(
                            document.resref,
                            "ncs",
                            bytes(compiled.ncs_bytes),
                            "runtime",
                            document.game,
                        )
                    )
            elif isinstance(document, DialogueDocument):
                payload, diagnostics = self.script_controller.service.dialogue_bytes(document)
                blocking = tuple(row.message for row in diagnostics if row.blocking)
                if blocking:
                    raise ValueError(
                        f"Dialogue {document.resref}.dlg is not project-save ready: " + "; ".join(blocking)
                    )
                rows.append(
                    ProjectResourceSnapshot(document.resref, "dlg", payload, "runtime", document.game)
                )

        game = self._target_game()
        rows.extend(
            ProjectResourceSnapshot(resref, restype, data, role, game)
            for resref, restype, data, role in self.data_controller.resource_snapshots()
        )
        for source in self.blueprint_controller.resource_snapshots():
            rows.append(
                ProjectResourceSnapshot(
                    str(source.get("resref") or ""),
                    str(source.get("restype") or ""),
                    bytes(source.get("data") or b""),
                    str(source.get("role") or "runtime"),
                    str(source.get("game") or game),
                    tuple(source.get("dependencies", ()) or ()),
                    dict(source.get("metadata", {}) or {}),
                )
            )
        provider = getattr(self.window, "additional_scripting_resource_snapshots", None)
        if callable(provider):
            for source in tuple(provider() or ()):
                if isinstance(source, ProjectResourceSnapshot):
                    rows.append(source)
                elif isinstance(source, Mapping):
                    rows.append(
                        ProjectResourceSnapshot(
                            str(source.get("resref") or ""),
                            str(source.get("restype") or ""),
                            bytes(source.get("data") or b""),
                            str(source.get("role") or "runtime"),
                            str(source.get("game") or game),
                            metadata=dict(source.get("metadata", {}) or {}),
                        )
                    )
                else:
                    values = tuple(source)
                    rows.append(
                        ProjectResourceSnapshot(
                            str(values[0]),
                            str(values[1]),
                            bytes(values[2]),
                            str(values[3] if len(values) > 3 else "runtime"),
                            game,
                        )
                    )
        return tuple(rows)

    # Merged runtime handoff -------------------------------------------

    def _on_script_build_completed(self, output_dir: str, resources: object) -> None:
        try:
            merged: "OrderedDict[tuple[str, str], bytes]" = OrderedDict()
            for resref, restype, data in tuple(resources or ()):
                merged[(str(resref).casefold(), str(restype).lower())] = bytes(data)
            for resref, restype, data, role in self.data_controller.resource_snapshots():
                extension = str(restype).lower()
                if str(role).lower() != "runtime" or extension == "tlk":
                    continue
                identity = (str(resref).casefold(), extension)
                prior = merged.get(identity)
                if prior is not None and prior != bytes(data):
                    raise ValueError(f"Runtime build contains conflicting bytes for {resref}.{extension}.")
                merged.setdefault(identity, bytes(data))
            for source in self.blueprint_controller.resource_snapshots():
                if str(source.get("role") or "runtime").lower() != "runtime":
                    continue
                identity = (
                    str(source.get("resref") or "").casefold(),
                    str(source.get("restype") or "").lower(),
                )
                payload = bytes(source.get("data") or b"")
                prior = merged.get(identity)
                if prior is not None and prior != payload:
                    raise ValueError(
                        f"Runtime build contains conflicting bytes for {identity[0]}.{identity[1]}."
                    )
                merged.setdefault(identity, payload)
            self._runtime_resources = tuple((resref, restype, data) for (resref, restype), data in merged.items())
            self._runtime_output_dir = str(output_dir)
            self.buildCompleted.emit(self._runtime_output_dir, self._runtime_resources)
        except Exception as exc:
            self._runtime_resources = ()
            self._runtime_output_dir = ""
            self.operationFailed.emit(str(exc))
            self.buildInvalidated.emit()

    def _publish_script_compiled_event(self, document_id: str, success: bool, ncs_bytes: object) -> None:
        """Preserve the versioned GhostScripter-to-GModular compile event."""

        document = self.script_controller._documents.get(str(document_id))
        if not isinstance(document, ScriptDocument):
            return
        result = self.script_controller._compiled.get(str(document_id))
        diagnostics = [
            row.to_dict() if hasattr(row, "to_dict") else {"message": str(row)}
            for row in tuple(getattr(result, "diagnostics", ()) or ())
        ]
        payload = bytes(ncs_bytes or b"")
        try:
            from src.ipc.client import notify_script_compiled

            notify_script_compiled(
                document.resref,
                game=document.game,
                success=bool(success),
                sha256=hashlib.sha256(payload).hexdigest() if payload else "",
                diagnostics=diagnostics,
            )
        except Exception:
            # An unavailable optional compatibility receiver must never turn a
            # successful local compile into a failed authoring operation.
            return

    def _invalidate_runtime_build(self) -> None:
        had_runtime = bool(self._runtime_resources)
        self._runtime_resources = ()
        self._runtime_output_dir = ""
        if had_runtime:
            self.buildInvalidated.emit()

    # Project inventory activation -------------------------------------

    def _activate_project_asset(self, path: str, row: Mapping[str, Any]) -> object:
        restype = str(row.get("restype") or Path(path).suffix).lower().lstrip(".")
        game = self.project_controller.project.game if self.project_controller.project is not None else self._target_game()
        if restype in _SCRIPT_RESOURCE_TYPES:
            return self.script_controller.open_file(path, game=game)
        if restype == "jrl":
            return self.data_controller.open_journal(path)
        if restype == "2da":
            resref = str(row.get("resref") or Path(path).stem).casefold()
            self.data_controller.set_table_mode("globals" if resref.startswith("global") else "2da")
            return self.data_controller.open_table(path)
        if restype == "tlk":
            return self.data_controller.open_talk_table(path)
        if restype == "lip":
            return self.data_controller.open_lip(path)
        if restype == "ssf":
            return self.data_controller.open_sound_set(path)
        if restype in _GFF_RESOURCE_TYPES:
            opened = self.blueprint_controller.open_path(path)
            if opened:
                show_page = getattr(self.window, "show_suite_page", None)
                if callable(show_page):
                    show_page("blueprint")
            return opened
        self.externalAssetRequested.emit(path, dict(row))
        return path


__all__ = ["ScriptingSuiteController"]
