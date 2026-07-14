"""Qt orchestration for GhostStudio's Scripting Suite.

The controller is the GUI boundary between the presentation-only Qt window and
:mod:`src.core.scripting.studio`.  PyKotor's mutable DLG objects stay
private here; the window only receives immutable-ish dictionaries containing
opaque node and link identifiers.

Compilation and DLG structural readback are authoring checks.  They are not a
claim that a resource has executed successfully in retail KOTOR.
"""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from uuid import uuid4

from PySide6 import QtCore, QtWidgets

from src.core.scripting.studio import (
    DialogueDocument,
    NarrativeBuildResult,
    ScriptCompileResult,
    ScriptDocument,
    ScriptingStudioService,
    StudioDiagnostic,
    dialogue_node_text,
    dialogue_structure_summary,
    normalise_script_resref,
    set_dialogue_node_text,
)


log = logging.getLogger(__name__)

_NARRATIVE_RESTYPES = ("NSS", "NCS", "DLG")
_RESTYPE_IDS = {"NSS": 2009, "NCS": 2010, "DLG": 2029, "2DA": 2017, "UTC": 2027}


def _game_key(value: object) -> str:
    text = str(value or "K2").strip().upper()
    return "K1" if text in {"K1", "1", "KOTOR", "KOTOR1"} else "K2"


def _resource_text(value: object) -> str:
    getter = getattr(value, "get", None)
    if callable(getter):
        try:
            return str(getter() or "")
        except Exception:
            pass
    return str(value or "")


def _document_kind(document: ScriptDocument | DialogueDocument) -> str:
    return "script" if isinstance(document, ScriptDocument) else "dialogue"


def _context_rows(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, bytearray, memoryview, Mapping)):
        return (value,)
    try:
        return tuple(value)  # type: ignore[arg-type]
    except TypeError:
        return (value,)


def _record_value(record: object, *names: str) -> object:
    if isinstance(record, Mapping):
        folded = {str(key).casefold(): value for key, value in record.items()}
        for name in names:
            if name.casefold() in folded:
                return folded[name.casefold()]
        return None
    for name in names:
        if hasattr(record, name):
            return getattr(record, name)
    return None


def _diagnostic_rows(rows: Iterable[StudioDiagnostic | Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(row.to_dict() if isinstance(row, StudioDiagnostic) else dict(row))
    return result


@dataclass
class _DialogueGraphIndex:
    """Stable opaque IDs and live object references for one open DLG."""

    node_ids: dict[int, str] = field(default_factory=dict)
    link_ids: dict[int, str] = field(default_factory=dict)
    nodes: dict[str, Any] = field(default_factory=dict)
    links: dict[str, Any] = field(default_factory=dict)
    link_containers: dict[str, list[Any]] = field(default_factory=dict)

    def node_id(self, node: object) -> str:
        identity = id(node)
        if identity not in self.node_ids:
            self.node_ids[identity] = f"node_{uuid4().hex}"
        value = self.node_ids[identity]
        self.nodes[value] = node
        return value

    def link_id(self, link: object) -> str:
        identity = id(link)
        if identity not in self.link_ids:
            self.link_ids[identity] = f"link_{uuid4().hex}"
        value = self.link_ids[identity]
        self.links[value] = link
        return value

    def begin_snapshot(self) -> None:
        self.nodes.clear()
        self.links.clear()
        self.link_containers.clear()


class ScriptingStudioController(QtCore.QObject):
    """Own open narrative documents and connect them to the studio window."""

    buildCompleted = QtCore.Signal(str, object)
    buildInvalidated = QtCore.Signal()
    compileCompleted = QtCore.Signal(str, bool, object)
    validationCompleted = QtCore.Signal(str, bool)
    documentOpened = QtCore.Signal(str)
    documentUpdated = QtCore.Signal(str)
    documentsChanged = QtCore.Signal(object)
    resourcesChanged = QtCore.Signal(object)
    diagnosticsChanged = QtCore.Signal(object, str)
    statusChanged = QtCore.Signal(str)
    operationFailed = QtCore.Signal(str)

    def __init__(
        self,
        window: Any | None = None,
        *,
        resource_manager: Any | None = None,
        resource_provider: Any | None = None,
        output_root: str | Path | None = None,
        service: ScriptingStudioService | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service or ScriptingStudioService()
        self.resource_manager = resource_manager
        self.resource_provider = resource_provider
        self.output_root = Path(output_root or (Path.cwd() / "Saved" / "ScriptingStudio" / "Build"))
        self.window: Any | None = None
        self._documents: "OrderedDict[str, ScriptDocument | DialogueDocument]" = OrderedDict()
        self.last_build: NarrativeBuildResult | None = None
        self._compiled: dict[str, ScriptCompileResult] = {}
        self._dialogue_indices: dict[str, _DialogueGraphIndex] = {}
        self._dialogue_topology_copy_required: dict[str, bool] = {}
        self._catalog_by_id: dict[str, dict[str, Any]] = {}
        self._catalog_rows: dict[str, list[dict[str, Any]]] = {}
        self._external_catalog_rows: dict[str, list[dict[str, Any]]] = {}
        self._external_document_ids: dict[tuple[str, str, str], str] = {}
        self._audio_preview: Any | None = None
        self._audio_preview_context: tuple[str, str, str] | None = None
        self._audio_browse_paths: dict[tuple[str, str], tuple[str, Path]] = {}
        self._participant_context: dict[str, tuple[object, ...]] = {}
        self._participant_blueprints: dict[str, tuple[object, ...]] = {}
        self._participant_appearance_payloads: dict[str, bytes] = {}
        self._connected_window: Any | None = None
        if window is not None:
            self.attach_window(window)

    # ------------------------------------------------------------------
    # Window wiring and presentation snapshots

    def attach_window(self, window: Any) -> None:
        """Attach the presentation shell once and populate its current state."""

        if window is self._connected_window:
            self.window = window
            return
        if self._connected_window is not None:
            raise RuntimeError("ScriptingStudioController is already attached to a different window.")
        self.window = window
        self._connected_window = window
        bindings = (
            ("newScriptRequested", self.new_script),
            ("newDialogueRequested", self.new_dialogue),
            ("openFileRequested", self._request_open_file),
            ("saveRequested", self.save_document),
            ("saveAllRequested", self.save_all),
            ("compileRequested", self.compile_document),
            ("validateRequested", self.validate_document),
            ("buildRequested", self.build_documents),
            ("refreshResourcesRequested", self.refresh_resource_catalog),
            ("resourceActivated", self.activate_resource),
            ("targetGameChanged", self.show_current_catalog),
            ("targetGameChanged", self.refresh_script_reference),
            ("referenceSearchRequested", self.search_script_reference),
            ("referenceInsertRequested", self.insert_script_reference),
            ("documentClosed", self.close_document),
            ("scriptSourceChanged", self.update_script_source),
            ("dialogueFieldsApplied", self.update_dialogue_fields),
            ("dialogueSettingsApplied", self.update_dialogue_settings),
            ("dialogueAddStarterRequested", self.add_dialogue_starter),
            ("dialogueAddChildRequested", self.add_dialogue_child),
            ("dialogueLinkExistingRequested", self.link_existing_dialogue_node),
            ("dialogueStartExistingRequested", self.start_dialogue_at_existing),
            ("dialogueRetargetLinkRequested", self.retarget_dialogue_link),
            ("dialogueRemoveLinkRequested", self.remove_dialogue_link),
            ("dialogueDeleteNodeRequested", self.delete_dialogue_node),
            ("dialogueMakeEditableCopyRequested", self.make_dialogue_editable_copy),
            ("dialogueAudioPreviewRequested", self.preview_dialogue_audio),
            ("dialogueAudioBrowseRequested", self.browse_dialogue_audio),
            ("dialogueAudioStopRequested", self.stop_dialogue_audio),
            ("dialogueParticipantBrowseRequested", self.browse_dialogue_participant),
        )
        for signal_name, slot in bindings:
            signal = getattr(window, signal_name, None)
            if signal is not None:
                signal.connect(slot)
        set_save_all_handler = getattr(window, "set_save_all_handler", None)
        if callable(set_save_all_handler):
            set_save_all_handler(self.save_all)
        for document in self._documents.values():
            self._present_document(document)
        self._publish_documents()
        self.show_current_catalog(getattr(window, "target_game", lambda: "K2")())
        self.refresh_script_reference(getattr(window, "target_game", lambda: "K2")())

    def document_row(self, document: ScriptDocument | DialogueDocument) -> dict[str, Any]:
        kind = _document_kind(document)
        compiled = self._compiled.get(document.document_id)
        status = "Modified" if document.dirty else "Saved"
        if kind == "script" and compiled is not None and compiled.ok:
            status = "Compiled" if not document.dirty else "Modified since compile"
        row = {
            "document_id": document.document_id,
            "kind": kind,
            "resref": document.resref,
            "restype": "NSS" if kind == "script" else "DLG",
            "display_name": document.display_name,
            "game": document.game,
            "origin": document.origin,
            "source_path": document.source_path,
            "dirty": bool(document.dirty),
            "status": status,
        }
        if isinstance(document, ScriptDocument):
            row.update({
                "disassembly": document.disassembly,
                "decompiled_from_sha256": document.decompiled_from_sha256,
                "recovered_source_exact": bool(document.recovered_source_exact),
                "recovery_error": document.recovery_error,
            })
        else:
            try:
                requires_copy = self._dialogue_topology_requires_copy(document)
            except Exception:
                requires_copy = bool(document.source_bytes)
            row.update({
                "topology_requires_editable_copy": requires_copy,
                "imported_source_protected": bool(document.source_bytes),
            })
        return row

    def _dialogue_topology_requires_copy(self, document: DialogueDocument) -> bool:
        cached = self._dialogue_topology_copy_required.get(document.document_id)
        if cached is None:
            cached = bool(self.service.dialogue_topology_requires_editable_copy(document))
            self._dialogue_topology_copy_required[document.document_id] = cached
        return cached

    def document_rows(self) -> list[dict[str, Any]]:
        return [self.document_row(document) for document in self._documents.values()]

    @property
    def documents(self) -> tuple[dict[str, Any], ...]:
        """Read-only presentation snapshots for callers outside the controller."""

        return tuple(self.document_rows())

    def _publish_documents(self) -> None:
        rows = self.document_rows()
        self.documentsChanged.emit(rows)
        if self.window is not None:
            for row in rows:
                updater = getattr(self.window, "update_document_row", None)
                if callable(updater):
                    updater(row)

    def _publish_document(self, document: ScriptDocument | DialogueDocument) -> None:
        row = self.document_row(document)
        if self.window is not None:
            updater = getattr(self.window, "update_document_row", None)
            if callable(updater):
                updater(row)
        self.documentUpdated.emit(document.document_id)
        self.documentsChanged.emit(self.document_rows())

    def _present_document(self, document: ScriptDocument | DialogueDocument) -> None:
        if self.window is None:
            return
        row = self.document_row(document)
        if isinstance(document, ScriptDocument):
            self.window.add_script_document(row, document.source)
        else:
            self.window.add_dialogue_document(row)
            self.window.set_dialogue_graph(document.document_id, self.dialogue_snapshot(document.document_id))
            setter = getattr(self.window, "set_dialogue_settings", None)
            if callable(setter):
                setter(document.document_id, self.dialogue_settings_snapshot(document.document_id))

    def _register_document(
        self,
        document: ScriptDocument | DialogueDocument,
        *,
        source_key: tuple[str, str, str] | None = None,
        diagnostics: Sequence[StudioDiagnostic] = (),
    ) -> str:
        self._documents[document.document_id] = document
        if isinstance(document, DialogueDocument):
            self._dialogue_indices[document.document_id] = _DialogueGraphIndex()
        if source_key is not None:
            self._external_document_ids[source_key] = document.document_id
        self._invalidate_build()
        self._present_document(document)
        self._publish_documents()
        self.documentOpened.emit(document.document_id)
        if diagnostics:
            self._set_diagnostics(diagnostics, summary=f"Opened {document.display_name} with review notes")
        self._set_status(f"Opened {document.display_name}")
        self.show_current_catalog(document.game)
        return document.document_id

    # ------------------------------------------------------------------
    # Script and dialogue document lifecycle

    @QtCore.Slot(str)
    def new_script(self, game: str = "K2", resref: str = "new_script") -> str:
        document = self.service.new_script(game=_game_key(game), resref=resref)
        return self._register_document(document)

    @QtCore.Slot(str)
    def new_dialogue(self, game: str = "K2", resref: str = "new_dialogue") -> str:
        document = self.service.new_dialogue(game=_game_key(game), resref=resref)
        return self._register_document(document)

    def _request_open_file(self, game: str) -> str:
        if self.window is None:
            return ""
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self.window,
            "Open NWScript or KOTOR Dialogue",
            "",
            "KOTOR narrative resources (*.nss *.ncs *.dlg);;NWScript (*.nss *.ncs);;Dialogue (*.dlg)",
        )
        return self.open_file(path, game=game) if path else ""

    def open_file(self, path: str | Path, *, game: str = "K2") -> str:
        source_path = Path(path)
        if not source_path.is_file():
            return self._fail(f"Narrative resource does not exist: {source_path}")
        suffix = source_path.suffix.lower()
        try:
            if suffix == ".nss":
                document = self.service.load_script(source_path, game=_game_key(game))
                diagnostics: tuple[StudioDiagnostic, ...] = ()
            elif suffix == ".ncs":
                document, diagnostics = self.service.decompile_ncs(
                    source_path.read_bytes(), game=_game_key(game), resref=source_path.stem
                )
            elif suffix == ".dlg":
                document = self.service.load_dialogue(source_path, game=_game_key(game))
                diagnostics = ()
            else:
                return self._fail("Open an NSS, NCS, or DLG resource.")
        except Exception as exc:
            log.exception("Could not open narrative resource %s", source_path)
            return self._fail(str(exc).strip() or exc.__class__.__name__)
        return self._register_document(document, diagnostics=diagnostics)

    def close_document(self, document_id: str) -> None:
        self.stop_dialogue_audio(str(document_id))
        document = self._documents.pop(str(document_id), None)
        if document is None:
            return
        self._compiled.pop(document.document_id, None)
        self._dialogue_indices.pop(document.document_id, None)
        self._dialogue_topology_copy_required.pop(document.document_id, None)
        self._participant_context.pop(document.document_id, None)
        self._participant_blueprints.pop(document.document_id, None)
        self._external_document_ids = {
            key: value for key, value in self._external_document_ids.items() if value != document.document_id
        }
        self._invalidate_build()
        self._publish_documents()
        self.show_current_catalog(document.game)

    @QtCore.Slot(str, str)
    def update_script_source(self, document_id: str, source: str) -> None:
        document = self._documents.get(str(document_id))
        if not isinstance(document, ScriptDocument) or document.source == str(source):
            return
        document.source = str(source)
        document.dirty = True
        self._compiled.pop(document.document_id, None)
        self._invalidate_build()
        self._publish_document(document)

    def save_document(self, document_id: str, save_as: bool = False, path: str | Path | None = None) -> bool:
        document = self._documents.get(str(document_id))
        if document is None:
            self._fail("Choose an open script or dialogue before saving.")
            return False
        target = str(path or "").strip()
        expected = ".nss" if isinstance(document, ScriptDocument) else ".dlg"
        if save_as or not target and not document.source_path:
            if self.window is None and not target:
                self._fail(f"Choose a save path for {document.display_name}.")
                return False
            if not target:
                selected, _filter = QtWidgets.QFileDialog.getSaveFileName(
                    self.window,
                    f"Save {document.display_name}",
                    document.display_name,
                    f"KOTOR {'NWScript' if expected == '.nss' else 'Dialogue'} (*{expected})",
                )
                if not selected:
                    return False
                target = selected
        if target and Path(target).suffix.lower() != expected:
            target = str(Path(target).with_suffix(expected))
        previous_identity = (document.resref, document.source_path)
        try:
            if isinstance(document, ScriptDocument):
                saved = self.service.save_script(document, target or None)
                diagnostics: tuple[StudioDiagnostic, ...] = ()
            else:
                saved, diagnostics = self.service.save_dialogue(document, target or None)
                if any(row.blocking for row in diagnostics):
                    self._set_diagnostics(diagnostics, summary=f"Could not save {document.display_name}")
                    return False
                document.source_structure = dialogue_structure_summary(document.dialogue)
            document.origin = "local_file"
        except Exception as exc:
            log.exception("Could not save %s", document.display_name)
            self._fail(str(exc).strip() or exc.__class__.__name__, resource=document.resref)
            return False
        if (document.resref, document.source_path) != previous_identity:
            self._invalidate_build()
        self._publish_document(document)
        if diagnostics:
            self._set_diagnostics(diagnostics, summary=f"Saved and read back {document.display_name}")
        self._set_status(f"Saved {saved}")
        self.show_current_catalog(document.game)
        return True

    @QtCore.Slot()
    def save_all(self) -> bool:
        for document in tuple(self._documents.values()):
            if document.dirty and not self.save_document(document.document_id):
                return False
        return True

    # ------------------------------------------------------------------
    # Compilation, validation, and transactional narrative build

    def compile_document(self, document_id: str) -> ScriptCompileResult | None:
        document = self._documents.get(str(document_id))
        if not isinstance(document, ScriptDocument):
            self._fail("Compile is available for an open NSS document.")
            return None
        result = self.service.compile_script(document, include_dirs=self._include_dirs(document))
        if result.ok:
            self._compiled[document.document_id] = result
            document.last_compiled_sha256 = hashlib.sha256(result.ncs_bytes).hexdigest()
        else:
            self._compiled.pop(document.document_id, None)
        self._set_diagnostics(result.diagnostics, summary=(
            f"Compiled {document.display_name}" if result.ok else f"Compile failed for {document.display_name}"
        ))
        self._publish_document(document)
        self.show_current_catalog(document.game)
        self.compileCompleted.emit(document.document_id, result.ok, bytes(result.ncs_bytes))
        self._set_status(
            f"Compiled {len(result.ncs_bytes)} NCS bytes; retail game proof is still required."
            if result.ok else f"Compile failed for {document.display_name}."
        )
        return result

    def validate_document(self, document_id: str) -> tuple[StudioDiagnostic, ...]:
        document = self._documents.get(str(document_id))
        if document is None:
            self._fail("Choose an open script or dialogue before validating.")
            return ()
        if isinstance(document, ScriptDocument):
            diagnostics = self.service.validate_script(document)
        else:
            _payload, diagnostics = self.service.dialogue_bytes(document)
        ok = not any(row.blocking for row in diagnostics)
        self._set_diagnostics(
            diagnostics,
            summary=f"{'Validation passed' if ok else 'Validation blocked'} for {document.display_name}",
        )
        self.validationCompleted.emit(document.document_id, ok)
        return tuple(diagnostics)

    def build_documents(self, game: str = "K2", output_dir: str | Path | None = None) -> NarrativeBuildResult:
        target_game = _game_key(game)
        documents = [document for document in self._documents.values() if document.game == target_game]
        destination = Path(output_dir) if output_dir else self.output_root / target_game.lower()
        result = self.service.build(
            documents,
            destination,
            game=target_game,
            include_dirs=self._all_include_dirs(documents),
        )
        self.last_build = result
        self._set_diagnostics(
            result.diagnostics,
            summary=(
                f"Built {len(result.resources)} narrative resources"
                if result.ok else "Narrative build blocked"
            ),
        )
        if result.ok:
            resources = result.resource_tuples(runtime_only=True)
            self.buildCompleted.emit(result.output_dir, resources)
            self._set_status(
                f"Staged {len(resources)} runtime resources. Retail KOTOR execution proof remains required."
            )
        else:
            self._set_status(self._build_failure_status(result))
        return result

    @staticmethod
    def _build_failure_status(result: NarrativeBuildResult) -> str:
        codes = {str(row.code) for row in result.diagnostics if row.blocking}
        if "narrative.build_rollback_failed" in codes:
            return (
                "Narrative build promotion and rollback failed. Inspect the preserved backup "
                "reported in Diagnostics before exporting."
            )
        if "narrative.build_promotion_failed" in codes:
            return "Narrative build promotion failed; the live output was restored or left unchanged."
        if "narrative.build_staging_failed" in codes:
            return "Narrative build staging failed before promotion; the live output was not replaced."
        if "narrative.output_not_owned" in codes:
            return "Narrative destination safety checks blocked staging; the live output was not replaced."
        if result.committed:
            return "Narrative output was promoted, but blocking verification diagnostics prevent runtime staging."
        return "Narrative validation failed before staging; the live output was not replaced."

    def runtime_resources(self) -> tuple[tuple[str, str, bytes], ...]:
        if self.last_build is None or not self.last_build.ok:
            return ()
        return self.last_build.resource_tuples(runtime_only=True)

    @staticmethod
    def _include_dirs(document: ScriptDocument) -> tuple[Path, ...]:
        return (Path(document.source_path).parent,) if document.source_path else ()

    @staticmethod
    def _all_include_dirs(documents: Sequence[ScriptDocument | DialogueDocument]) -> tuple[Path, ...]:
        values = {
            Path(document.source_path).parent
            for document in documents
            if isinstance(document, ScriptDocument) and document.source_path
        }
        return tuple(sorted(values, key=lambda value: str(value).lower()))

    # ------------------------------------------------------------------
    # DLG graph snapshots and mutations

    def dialogue_snapshot(self, document_id: str) -> list[dict[str, Any]]:
        document = self._documents.get(str(document_id))
        if not isinstance(document, DialogueDocument) or document.dialogue is None:
            return []
        from pykotor.resource.generics.dlg import DLGEntry

        index = self._dialogue_indices.setdefault(document.document_id, _DialogueGraphIndex())
        index.begin_snapshot()
        rows: list[dict[str, Any]] = []
        expanded_nodes: set[int] = set()
        seen_links: set[int] = set()
        pending: list[tuple[Any, list[Any], str, int]] = [
            (link, document.dialogue.starters, "", 0)
            for link in tuple(document.dialogue.starters or ())
        ]
        cursor = 0
        while cursor < len(pending):
            link, container, parent_link_id, depth = pending[cursor]
            cursor += 1
            if id(link) in seen_links:
                continue
            seen_links.add(id(link))
            link_id = index.link_id(link)
            index.link_containers[link_id] = container
            node = getattr(link, "node", None)
            node_id = index.node_id(node) if node is not None else ""
            kind = "entry" if isinstance(node, DLGEntry) else "reply"
            row = {
                "document_id": document.document_id,
                "link_id": link_id,
                "node_id": node_id,
                "parent_link_id": parent_link_id,
                "depth": depth,
                "kind": kind,
                "text": dialogue_node_text(node, tlk_lookup=self._tlk_lookup(document.game)) if node else "",
                "speaker": str(getattr(node, "speaker", "") or ""),
                "listener": str(getattr(node, "listener", "") or ""),
                "script1": _resource_text(getattr(node, "script1", "")),
                "script2": _resource_text(getattr(node, "script2", "")),
                "sound": _resource_text(getattr(node, "sound", "")),
                "voice": _resource_text(getattr(node, "vo_resref", "")),
                "quest": str(getattr(node, "quest", "") or ""),
                "quest_entry": int(getattr(node, "quest_entry", 0) or 0),
                "active1": _resource_text(getattr(link, "active1", "")),
                "active2": _resource_text(getattr(link, "active2", "")),
                "active1_not": bool(getattr(link, "active1_not", False)),
                "active2_not": bool(getattr(link, "active2_not", False)),
                "logic": bool(getattr(link, "logic", False)),
                "shared_target": bool(node is not None and id(node) in expanded_nodes),
            }
            if node is not None:
                from src.core.scripting.dialogue_contract import (
                    snapshot_dialogue_link,
                    snapshot_dialogue_node,
                )

                node_fields = asdict(snapshot_dialogue_node(node, tlk_lookup=self._tlk_lookup(document.game)))
                link_fields = asdict(snapshot_dialogue_link(link))
                for key in ("stable_id", "kind", "list_index"):
                    node_fields.pop(key, None)
                for key in ("stable_id", "target_node_id", "list_index"):
                    link_fields.pop(key, None)
                # Keep the opaque graph identity distinct from KOTOR 2's
                # serialized numeric NodeID field.  The graph uses ``node_id``
                # for stable selection across refreshes; the inspector exposes
                # the engine field as ``node_id_tsl`` and maps it back on edit.
                node_fields["node_id_tsl"] = node_fields.pop("node_id", None)
                node_fields["node_comment"] = node_fields.pop("comment", "")
                link_fields["link_comment"] = link_fields.pop("comment", "")
                row.update(node_fields)
                row.update(link_fields)
                row["voice"] = row.get("vo_resref", "")
            rows.append(row)
            if node is None or id(node) in expanded_nodes:
                continue
            expanded_nodes.add(id(node))
            for child in tuple(getattr(node, "links", ()) or ()):
                pending.append((child, node.links, link_id, depth + 1))
        return rows

    def update_dialogue_fields(
        self,
        document_id: str,
        node_id: str,
        link_id: str,
        values: Mapping[str, Any] | object,
    ) -> bool:
        document = self._documents.get(str(document_id))
        if not isinstance(document, DialogueDocument):
            return False
        self.dialogue_snapshot(document.document_id)
        index = self._dialogue_indices[document.document_id]
        node = index.nodes.get(str(node_id))
        link = index.links.get(str(link_id))
        if node is None or link is None:
            self._fail("The selected dialogue node no longer exists. Refresh the graph and try again.")
            return False
        data = dict(values) if isinstance(values, Mapping) else {}
        try:
            from src.core.scripting.dialogue_contract import (
                apply_dialogue_link_fields,
                apply_dialogue_node_fields,
            )

            if "voice" in data and "vo_resref" not in data:
                data["vo_resref"] = data.pop("voice")
            if "node_comment" in data:
                data["comment"] = data.pop("node_comment")
            link_comment = data.pop("link_comment", None)
            node_fields = {
                "text", "text_stringref", "text_substrings", "comment", "speaker", "listener",
                "script1", "script2", "script1_params", "script2_params", "sound", "sound_exists",
                "vo_resref", "wait_flags", "delay", "quest", "quest_entry", "plot_index",
                "plot_xp_percentage", "animations", "camera_angle", "camera_anim", "camera_id",
                "camera_fov", "camera_height", "camera_effect", "target_height", "fade_type",
                "fade_color", "fade_delay", "fade_length", "alien_race_node", "emotion_id",
                "facial_id", "node_id", "post_proc_node", "unskippable", "record_vo",
                "record_no_vo_override", "vo_text_changed",
            }
            link_fields = {
                "comment", "active1", "active2", "active1_not", "active2_not", "logic",
                "active1_params", "active2_params", "is_child", "display_inactive",
            }
            node_changes = {key: value for key, value in data.items() if key in node_fields}
            link_changes = {key: value for key, value in data.items() if key in link_fields}
            if link_comment is not None:
                link_changes["comment"] = link_comment
            if node_changes:
                apply_dialogue_node_fields(node, node_changes)
            if link_changes:
                apply_dialogue_link_fields(link, link_changes)
        except Exception as exc:
            self._fail(str(exc).strip() or exc.__class__.__name__, resource=document.resref)
            return False
        document.dirty = True
        self._invalidate_build()
        self._refresh_dialogue_presentation(document)
        return True

    # ------------------------------------------------------------------
    # Dialogue voice/sound preview (editor-only; not retail engine proof)

    def _ensure_audio_preview(self, game: str) -> Any:
        source = self.resource_manager or self.resource_provider
        if self._audio_preview is None:
            from src.adapters.qt_audio.narrative_audio_preview import NarrativeAudioPreview

            self._audio_preview = NarrativeAudioPreview(source, game, self)
            self._audio_preview.previewStarted.connect(self._audio_preview_started)
            self._audio_preview.previewStopped.connect(self._audio_preview_stopped)
            self._audio_preview.previewFailed.connect(self._audio_preview_failed)
            self._audio_preview.progressChanged.connect(self._audio_preview_progress)
        else:
            self._audio_preview.set_resource_source(source, game)
        return self._audio_preview

    def preview_dialogue_audio(self, document_id: str, field: str, resref: str) -> bool:
        document = self._documents.get(str(document_id))
        if not isinstance(document, DialogueDocument):
            return False
        key = "voice" if str(field).strip().lower() in {"voice", "vo"} else "sound"
        name = str(resref or "").strip().lower()
        preview = self._ensure_audio_preview(document.game)
        self._audio_preview_context = (document.document_id, key, name)
        self._present_audio_preview_state("loading", "Resolving editor preview…")
        browsed = self._audio_browse_paths.get((document.document_id, key))
        if browsed is not None and browsed[0] == name and browsed[1].is_file():
            played = bool(preview.play_file(browsed[1]))
        else:
            played = bool(preview.play_resref(name, document.game))
        if played:
            self._set_status(
                f"Previewing {key} audio {name or preview.source_label}; retail KOTOR playback is not yet proven."
            )
        return played

    def browse_dialogue_audio(self, document_id: str, field: str) -> str:
        document = self._documents.get(str(document_id))
        if not isinstance(document, DialogueDocument) or self.window is None:
            return ""
        key = "voice" if str(field).strip().lower() in {"voice", "vo"} else "sound"
        existing = self._audio_browse_paths.get((document.document_id, key))
        start = str(existing[1].parent if existing is not None else Path.home())
        selected, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self.window,
            f"Choose {key.title()} Audio for Editor Preview",
            start,
            "KOTOR/standard audio (*.wav *.mp3 *.ogg *.flac);;All files (*)",
        )
        if not selected:
            return ""
        path = Path(selected)
        self.stop_dialogue_audio()
        resref = path.stem.strip().lower()[:16]
        self._audio_browse_paths[(document.document_id, key)] = (resref, path)
        setter = getattr(self.window, "set_dialogue_audio_reference", None)
        if callable(setter):
            setter(
                document.document_id,
                key,
                resref,
                message=f"Linked local preview: {path.name} (not staged or packaged)",
            )
        self._set_status(
            f"Linked {path.name} for local preview. Apply node fields to keep ResRef {resref!r}."
        )
        return str(path)

    def set_dialogue_participant_context(
        self,
        document_id: str,
        participants: object = (),
        *,
        utc_blueprints: object = (),
    ) -> None:
        """Replace the real module/blueprint tags available to one DLG.

        Map Studio owns placement state and supplies it here.  Appearance rows
        are never accepted as participants; the core catalogue service uses
        ``appearance.2da`` only to decorate these supplied records.
        """

        key = str(document_id or "")
        if not key:
            return
        self._participant_context[key] = _context_rows(participants)
        self._participant_blueprints[key] = _context_rows(utc_blueprints)

    def _appearance_payload(self, game: str) -> bytes:
        target = _game_key(game)
        if target not in self._participant_appearance_payloads:
            self._participant_appearance_payloads[target] = self._read_resource(
                None, target, "appearance", "2DA"
            )
        return self._participant_appearance_payloads[target]

    def _resolve_participant_utc(
        self,
        row: object,
        game: str,
        *,
        blueprint_resref: bool = False,
    ) -> object:
        existing = _record_value(row, "utc_bytes", "blueprint_bytes", "payload", "data")
        if isinstance(existing, (bytes, bytearray, memoryview)):
            return row
        candidate = (
            row
            if blueprint_resref and isinstance(row, str)
            else _record_value(
                row,
                "template_resref",
                "utc_resref",
                "creature_source_template_resref",
                "source_template_resref",
            )
        )
        resref = str(candidate or "").strip().lower()[:16]
        if not resref:
            return row
        payload = self._read_resource(None, _game_key(game), resref, "UTC")
        if not payload:
            return row
        if isinstance(row, Mapping):
            return {**dict(row), "utc_bytes": payload}
        return {
            "tag": _record_value(row, "tag", "creature_tag", "participant_tag") or "",
            "appearance_id": _record_value(
                row, "appearance_id", "appearance_type", "appearance", "Appearance_Type"
            ) or "",
            "source": _record_value(row, "source") or (
                "UTC blueprint" if blueprint_resref else "Current module"
            ),
            "template_resref": resref,
            "utc_bytes": payload,
        }

    def browse_dialogue_participant(self, document_id: str, field: str, current: str = "") -> str:
        document = self._documents.get(str(document_id))
        if not isinstance(document, DialogueDocument) or self.window is None:
            return ""
        from src.core.scripting.dialogue_participants import DialogueParticipantCatalogService

        used: list[dict[str, str]] = []
        seen_used: set[str] = set()
        for row in self.dialogue_snapshot(document.document_id):
            for key in ("speaker", "listener"):
                tag = str(row.get(key) or "").strip()
                folded = tag.casefold()
                if tag and folded not in seen_used:
                    seen_used.add(folded)
                    used.append({"tag": tag, "source": "Current dialogue"})
        placements = tuple(
            self._resolve_participant_utc(row, document.game)
            for row in self._participant_context.get(document.document_id, ())
        )
        blueprints = tuple(
            self._resolve_participant_utc(row, document.game, blueprint_resref=True)
            for row in self._participant_blueprints.get(document.document_id, ())
        )
        catalog = [
            participant.as_row()
            for participant in DialogueParticipantCatalogService().build(
                placed_creatures=placements,
                utc_blueprints=blueprints,
                dialogue_tags=used,
                appearance_2da=self._appearance_payload(document.game),
            )
        ]
        chooser = getattr(self.window, "choose_dialogue_participant", None)
        if not callable(chooser):
            return ""
        selected = str(
            chooser(document.document_id, field, catalog, current=str(current or "")) or ""
        ).strip()
        if selected:
            self._set_status(
                f"Selected dialogue {str(field).casefold()} {selected!r}; Apply Node Fields to keep the change."
            )
        elif not placements and not blueprints and not used:
            self._set_status(
                "No placed creature tags are available. Type the creature tag directly or open this DLG from Map Studio."
            )
        return selected

    def stop_dialogue_audio(self, document_id: str = "") -> None:
        context = self._audio_preview_context
        if context is None:
            return
        requested = str(document_id or "")
        if requested and requested != context[0]:
            return
        if self._audio_preview is not None:
            self._audio_preview.stop()
        if self._audio_preview_context is not None:
            self._audio_preview_stopped()

    def _present_audio_preview_state(
        self,
        state: str,
        message: str,
        *,
        position_ms: int = 0,
        duration_ms: int = 0,
    ) -> None:
        context = self._audio_preview_context
        if context is None or self.window is None:
            return
        setter = getattr(self.window, "set_dialogue_audio_preview_state", None)
        if callable(setter):
            setter(
                context[0],
                context[1],
                state,
                message=message,
                position_ms=position_ms,
                duration_ms=duration_ms,
            )

    @QtCore.Slot(str)
    def _audio_preview_started(self, source_label: str) -> None:
        self._present_audio_preview_state("playing", f"Playing {source_label} (editor preview)")

    @QtCore.Slot()
    def _audio_preview_stopped(self) -> None:
        if self._audio_preview_context is None:
            return
        self._present_audio_preview_state("stopped", "Preview stopped")
        self._audio_preview_context = None

    @QtCore.Slot(str)
    def _audio_preview_failed(self, message: str) -> None:
        text = str(message or "Audio preview failed.")
        self._present_audio_preview_state("error", text)
        self._set_status(text)
        self._audio_preview_context = None

    @QtCore.Slot(int, int)
    def _audio_preview_progress(self, position_ms: int, duration_ms: int) -> None:
        self._present_audio_preview_state(
            "playing",
            "Playing editor preview",
            position_ms=position_ms,
            duration_ms=duration_ms,
        )

    def dialogue_settings_snapshot(self, document_id: str) -> dict[str, Any]:
        document = self._documents.get(str(document_id))
        if not isinstance(document, DialogueDocument) or document.dialogue is None:
            return {}
        from src.core.scripting.dialogue_contract import snapshot_dialogue_settings

        return asdict(snapshot_dialogue_settings(document.dialogue))

    def update_dialogue_settings(self, document_id: str, values: Mapping[str, Any] | object) -> bool:
        document = self._documents.get(str(document_id))
        if not isinstance(document, DialogueDocument) or document.dialogue is None:
            return False
        try:
            from src.core.scripting.dialogue_contract import apply_dialogue_settings

            apply_dialogue_settings(
                document.dialogue,
                dict(values) if isinstance(values, Mapping) else {},
            )
        except Exception as exc:
            self._fail(str(exc).strip() or exc.__class__.__name__, resource=document.resref)
            return False
        document.dirty = True
        self._invalidate_build()
        if self.window is not None:
            setter = getattr(self.window, "set_dialogue_settings", None)
            if callable(setter):
                setter(document.document_id, self.dialogue_settings_snapshot(document.document_id))
        self._publish_document(document)
        return True

    def _ensure_dialogue_topology_editable(self, document: DialogueDocument) -> bool:
        try:
            protected = self._dialogue_topology_requires_copy(document)
        except Exception as exc:
            self._fail(
                f"Could not verify imported DLG extension fields: {str(exc).strip() or exc.__class__.__name__}",
                resource=document.resref,
            )
            return False
        if not protected:
            return True
        self._fail(
            "This imported DLG has unknown fields, so topology changes are locked. "
            "Use Make Editable Copy… to create a separate authored DLG; the imported bytes and path stay untouched.",
            resource=document.resref,
        )
        return False

    def make_dialogue_editable_copy(
        self,
        document_id: str,
        target_path: str | Path | None = None,
    ) -> str:
        """Open an explicitly authored DLG copy at a path distinct from source."""

        document = self._documents.get(str(document_id))
        if not isinstance(document, DialogueDocument):
            return ""
        target = str(target_path or "").strip()
        if not target:
            if self.window is None:
                self._fail("Choose a new DLG path for the editable copy.", resource=document.resref)
                return ""
            source = Path(document.source_path) if document.source_path else Path(f"{document.resref}.dlg")
            suggested = source.with_name(f"{source.stem}_editable.dlg")
            selected, _filter = QtWidgets.QFileDialog.getSaveFileName(
                self.window,
                "Make Editable Dialogue Copy (Original Remains Untouched)",
                str(suggested),
                "KOTOR Dialogue (*.dlg)",
            )
            if not selected:
                return ""
            target = selected
        path = Path(target)
        if path.suffix.lower() != ".dlg":
            path = path.with_suffix(".dlg")
        try:
            authored = self.service.make_editable_dialogue_copy(
                document,
                resref=path.stem,
                source_path=path,
            )
        except Exception as exc:
            self._fail(str(exc).strip() or exc.__class__.__name__, resource=document.resref)
            return ""
        copy_id = self._register_document(authored)
        self._set_status(
            f"Created editable copy {authored.display_name}. The imported {document.display_name} remains unchanged."
        )
        return copy_id

    def add_dialogue_starter(self, document_id: str) -> str:
        document = self._documents.get(str(document_id))
        if not isinstance(document, DialogueDocument) or not self._ensure_dialogue_topology_editable(document):
            return ""
        from pykotor.resource.generics.dlg import DLGEntry, DLGLink

        entry = DLGEntry()
        entry.speaker = "OWNER"
        set_dialogue_node_text(entry, "New starting dialogue line")
        link = DLGLink(entry)
        document.dialogue.starters.append(link)
        document.dirty = True
        self._invalidate_build()
        self._refresh_dialogue_presentation(document)
        index = self._dialogue_indices[document.document_id]
        link_id = index.link_ids.get(id(link), "")
        self._select_dialogue_link(document.document_id, link_id)
        return link_id

    def add_dialogue_child(self, document_id: str, link_id: str) -> str:
        document = self._documents.get(str(document_id))
        if not isinstance(document, DialogueDocument) or not self._ensure_dialogue_topology_editable(document):
            return ""
        self.dialogue_snapshot(document.document_id)
        index = self._dialogue_indices[document.document_id]
        parent_link = index.links.get(str(link_id))
        parent_node = getattr(parent_link, "node", None)
        if parent_node is None:
            self._fail("The selected dialogue link has no target node.", resource=document.resref)
            return ""
        from pykotor.resource.generics.dlg import DLGEntry, DLGLink, DLGReply

        child = DLGReply() if isinstance(parent_node, DLGEntry) else DLGEntry()
        if isinstance(child, DLGEntry):
            child.speaker = "OWNER"
            text = "New NPC dialogue line"
        else:
            text = "New player reply"
        set_dialogue_node_text(child, text)
        child_link = DLGLink(child)
        parent_node.links.append(child_link)
        document.dirty = True
        self._invalidate_build()
        self._refresh_dialogue_presentation(document)
        new_link_id = self._dialogue_indices[document.document_id].link_ids.get(id(child_link), "")
        self._select_dialogue_link(document.document_id, new_link_id)
        return new_link_id

    def link_existing_dialogue_node(self, document_id: str, source_link_id: str, target_node_id: str) -> str:
        document = self._documents.get(str(document_id))
        if not isinstance(document, DialogueDocument) or not self._ensure_dialogue_topology_editable(document):
            return ""
        self.dialogue_snapshot(document.document_id)
        index = self._dialogue_indices[document.document_id]
        source_link = index.links.get(str(source_link_id))
        source_node = getattr(source_link, "node", None)
        target_node = index.nodes.get(str(target_node_id))
        if source_node is None or target_node is None:
            self._fail("Choose an existing source and target node from this dialogue.", resource=document.resref)
            return ""
        try:
            from src.core.scripting.dialogue_contract import connect_existing_dialogue_node

            new_link = connect_existing_dialogue_node(document.dialogue, source_node, target_node)
        except Exception as exc:
            self._fail(str(exc).strip() or exc.__class__.__name__, resource=document.resref)
            return ""
        document.dirty = True
        self._invalidate_build()
        self._refresh_dialogue_presentation(document)
        new_link_id = self._dialogue_indices[document.document_id].link_ids.get(id(new_link), "")
        self._select_dialogue_link(document.document_id, new_link_id)
        return new_link_id

    def start_dialogue_at_existing(self, document_id: str, target_node_id: str) -> str:
        document = self._documents.get(str(document_id))
        if not isinstance(document, DialogueDocument) or not self._ensure_dialogue_topology_editable(document):
            return ""
        self.dialogue_snapshot(document.document_id)
        target_node = self._dialogue_indices[document.document_id].nodes.get(str(target_node_id))
        if target_node is None:
            self._fail("Choose an existing NPC entry from this dialogue.", resource=document.resref)
            return ""
        try:
            from src.core.scripting.dialogue_contract import start_dialogue_at_existing_node

            new_link = start_dialogue_at_existing_node(document.dialogue, target_node)
        except Exception as exc:
            self._fail(str(exc).strip() or exc.__class__.__name__, resource=document.resref)
            return ""
        document.dirty = True
        self._invalidate_build()
        self._refresh_dialogue_presentation(document)
        new_link_id = self._dialogue_indices[document.document_id].link_ids.get(id(new_link), "")
        self._select_dialogue_link(document.document_id, new_link_id)
        return new_link_id

    def retarget_dialogue_link(self, document_id: str, link_id: str, target_node_id: str) -> bool:
        document = self._documents.get(str(document_id))
        if not isinstance(document, DialogueDocument) or not self._ensure_dialogue_topology_editable(document):
            return False
        self.dialogue_snapshot(document.document_id)
        index = self._dialogue_indices[document.document_id]
        link = index.links.get(str(link_id))
        target_node = index.nodes.get(str(target_node_id))
        if link is None or target_node is None:
            self._fail("The selected link or target node no longer exists.", resource=document.resref)
            return False
        try:
            from src.core.scripting.dialogue_contract import retarget_dialogue_link

            retarget_dialogue_link(document.dialogue, link, target_node)
        except Exception as exc:
            self._fail(str(exc).strip() or exc.__class__.__name__, resource=document.resref)
            return False
        document.dirty = True
        self._invalidate_build()
        self._refresh_dialogue_presentation(document)
        self._select_dialogue_link(document.document_id, str(link_id))
        return True

    def remove_dialogue_link(self, document_id: str, link_id: str) -> bool:
        document = self._documents.get(str(document_id))
        if not isinstance(document, DialogueDocument) or not self._ensure_dialogue_topology_editable(document):
            return False
        self.dialogue_snapshot(document.document_id)
        index = self._dialogue_indices[document.document_id]
        link = index.links.get(str(link_id))
        if link is None:
            self._fail("The selected dialogue link no longer exists.", resource=document.resref)
            return False
        from src.core.scripting.dialogue_contract import remove_dialogue_link

        if not remove_dialogue_link(document.dialogue, link):
            self._fail("The selected dialogue link no longer exists.", resource=document.resref)
            return False
        document.dirty = True
        self._invalidate_build()
        self._refresh_dialogue_presentation(document)
        return True

    def delete_dialogue_node(self, document_id: str, node_id: str) -> bool:
        document = self._documents.get(str(document_id))
        if not isinstance(document, DialogueDocument) or not self._ensure_dialogue_topology_editable(document):
            return False
        self.dialogue_snapshot(document.document_id)
        node = self._dialogue_indices[document.document_id].nodes.get(str(node_id))
        if node is None:
            self._fail("The selected dialogue node no longer exists.", resource=document.resref)
            return False
        try:
            from src.core.scripting.dialogue_contract import delete_dialogue_node

            removed = delete_dialogue_node(document.dialogue, node)
        except Exception as exc:
            self._fail(str(exc).strip() or exc.__class__.__name__, resource=document.resref)
            return False
        if not removed:
            self._fail("The selected dialogue node has no incoming links.", resource=document.resref)
            return False
        document.dirty = True
        self._invalidate_build()
        self._refresh_dialogue_presentation(document)
        self._set_status(f"Deleted dialogue node and removed {removed} incoming link(s).")
        return True

    def _select_dialogue_link(self, document_id: str, link_id: str) -> None:
        if not link_id or self.window is None:
            return
        selector = getattr(self.window, "select_dialogue_link", None)
        if callable(selector):
            selector(document_id, link_id)

    def _refresh_dialogue_presentation(self, document: DialogueDocument) -> None:
        rows = self.dialogue_snapshot(document.document_id)
        if self.window is not None:
            self.window.set_dialogue_graph(document.document_id, rows)
            setter = getattr(self.window, "set_dialogue_settings", None)
            if callable(setter):
                setter(document.document_id, self.dialogue_settings_snapshot(document.document_id))
        self._publish_document(document)

    def _tlk_lookup(self, game: str) -> Callable[[int], str] | None:
        candidates = (self.resource_provider, self.resource_manager)
        for owner in candidates:
            getter = getattr(owner, "get_tlk_string", None)
            if callable(getter):
                return lambda stringref, getter=getter, game=game: getter(stringref, game)
        return None

    # ------------------------------------------------------------------
    # Read-only game-resource catalog

    def resource_catalog(self, game: str = "K2") -> list[dict[str, Any]]:
        target_game = _game_key(game)
        if target_game not in self._catalog_rows:
            self._catalog_rows[target_game] = self._build_resource_catalog(target_game)
        return [dict(row) for row in self._catalog_rows[target_game]]

    def show_current_catalog(self, game: str = "K2") -> list[dict[str, Any]]:
        """Refresh open-document rows without scanning the whole installation.

        Installed KOTOR catalogs can contain thousands of NSS/NCS/DLG rows.
        Loading those synchronously while a workbench is opening makes the new
        window appear broken.  The explicit Refresh button performs that scan;
        routine edits keep the already-loaded catalog (if any) and otherwise
        publish only the immediately useful open documents.
        """

        target_game = _game_key(game)
        return self._publish_resource_catalog(target_game, self._build_resource_catalog(target_game))

    def refresh_resource_catalog(self, game: str = "K2") -> list[dict[str, Any]]:
        target_game = _game_key(game)
        self._external_catalog_rows[target_game] = self._scan_external_catalog(target_game)
        return self._publish_resource_catalog(target_game, self._build_resource_catalog(target_game))

    def _publish_resource_catalog(
        self,
        target_game: str,
        rows: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        cached = [dict(row) for row in rows]
        self._catalog_rows[target_game] = cached
        published = [dict(row) for row in cached]
        if self.window is not None and getattr(self.window, "target_game", lambda: target_game)() == target_game:
            self.window.set_resource_rows(published)
        self.resourcesChanged.emit(published)
        return published

    def _build_resource_catalog(self, game: str) -> list[dict[str, Any]]:
        """Merge live document rows with the last explicit installation scan."""

        rows: list[dict[str, Any]] = []
        for document in self._documents.values():
            if document.game != game:
                continue
            restype = "NSS" if isinstance(document, ScriptDocument) else "DLG"
            rows.append({
                **self.document_row(document),
                "catalog_id": f"open:{document.document_id}",
                "origin": "Open document",
                "size": len(document.source.encode("utf-8")) if isinstance(document, ScriptDocument) else 0,
            })
            compiled = self._compiled.get(document.document_id)
            if isinstance(document, ScriptDocument) and compiled is not None and compiled.ok:
                rows.append({
                    "catalog_id": f"compiled:{document.document_id}",
                    "kind": "script",
                    "resref": document.resref,
                    "restype": "NCS",
                    "game": game,
                    "origin": "Current compile",
                    "status": "Readback passed; not retail-proven",
                    "size": len(compiled.ncs_bytes),
                })

        rows.extend(dict(row) for row in self._external_catalog_rows.get(game, ()))
        rows.sort(key=lambda row: (str(row.get("resref") or "").lower(), str(row.get("restype") or "")))
        return rows

    def _scan_external_catalog(self, game: str) -> list[dict[str, Any]]:
        """Scan an installation once for the explicit Refresh operation."""

        self._catalog_by_id = {
            key: value for key, value in self._catalog_by_id.items() if value.get("game") != game
        }
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for restype in _NARRATIVE_RESTYPES:
            for locator in self._external_rows(game, restype):
                resref = str(locator.get("resref") or "").strip().lower()
                if not resref:
                    continue
                origin = str(locator.get("origin") or "Game resource")
                key = (resref, restype, origin)
                if key in seen:
                    continue
                seen.add(key)
                catalog_id = f"external:{game}:{restype}:{len(self._catalog_by_id)}:{uuid4().hex[:8]}"
                locator.update({"catalog_id": catalog_id, "game": game, "restype": restype})
                self._catalog_by_id[catalog_id] = locator
                rows.append({
                    "catalog_id": catalog_id,
                    "kind": "dialogue" if restype == "DLG" else "script",
                    "resref": resref,
                    "restype": restype,
                    "game": game,
                    "origin": origin,
                    "status": "Read-only game resource",
                    "size": int(locator.get("size") or 0),
                    "source": str(locator.get("source") or ""),
                })
        return rows

    def _external_rows(self, game: str, restype: str) -> Iterable[dict[str, Any]]:
        provider = self.resource_provider
        if provider is not None:
            listing = getattr(provider, "list_resources", None)
            if callable(listing):
                try:
                    records = listing({"game": game, "restype": restype})
                except Exception:
                    records = ()
                for record in records or ():
                    address = getattr(record, "address", None)
                    yield {
                        "mode": "provider",
                        "owner": provider,
                        "record": record,
                        "resref": getattr(record, "resref", None) or getattr(address, "resref", ""),
                        "origin": getattr(record, "source", "") or getattr(address, "layer", "") or "Game resource",
                        "source": getattr(record, "source_path", "") or "",
                        "size": getattr(record, "size", 0),
                    }
        manager = self.resource_manager
        if manager is None or manager is provider:
            return
        listing = getattr(manager, "list_resources", None)
        records: Iterable[Any] = ()
        if callable(listing):
            try:
                records = listing(_RESTYPE_IDS[restype], game) or ()
            except Exception:
                records = ()
        if not records:
            install_getter = getattr(manager, "get_k1" if game == "K1" else "get_k2", None)
            install = install_getter() if callable(install_getter) else None
            list_resrefs = getattr(install, "list_resrefs", None)
            if callable(list_resrefs):
                records = tuple(list_resrefs(_RESTYPE_IDS[restype]) or ())
        for record in records or ():
            resref = record if isinstance(record, str) else getattr(record, "resref", "")
            yield {
                "mode": "manager",
                "owner": manager,
                "record": record,
                "resref": resref,
                "origin": getattr(record, "source_file", "") or "Game installation",
                "source": getattr(record, "source_file", "") or "",
                "size": getattr(record, "size", 0),
            }

    def activate_resource(self, row: Mapping[str, Any] | object) -> str:
        data = dict(row) if isinstance(row, Mapping) else {}
        catalog_id = str(data.get("catalog_id") or "")
        if catalog_id.startswith("open:"):
            document_id = catalog_id.split(":", 1)[1]
            if self.window is not None:
                self.window.focus_document(document_id)
            return document_id
        if catalog_id.startswith("compiled:"):
            document_id = catalog_id.split(":", 1)[1]
            if self.window is not None:
                self.window.focus_document(document_id)
            return document_id
        return self.open_resource(
            game=str(data.get("game") or "K2"),
            resref=str(data.get("resref") or ""),
            restype=str(data.get("restype") or "NSS"),
            catalog_id=catalog_id,
        )

    def open_resource(
        self,
        *,
        game: str,
        resref: str,
        restype: str,
        catalog_id: str = "",
        report_missing: bool = True,
    ) -> str:
        target_game = _game_key(game)
        target_resref = str(resref or "").strip().lower()
        target_type = str(restype or "NSS").strip().upper()
        source_key = (target_game, target_resref, target_type)
        existing = self._external_document_ids.get(source_key)
        if existing in self._documents:
            if self.window is not None:
                self.window.focus_document(existing)
            return existing
        locator = self._catalog_by_id.get(catalog_id)
        if locator is None:
            for row in self.resource_catalog(target_game):
                if row.get("resref") == target_resref and row.get("restype") == target_type:
                    locator = self._catalog_by_id.get(str(row.get("catalog_id") or ""))
                    if locator is not None:
                        break
        try:
            payload = self._read_resource(locator, target_game, target_resref, target_type)
            if not payload:
                if report_missing:
                    return self._fail(f"Could not read {target_resref}.{target_type.lower()} from {target_game} resources.")
                return ""
            diagnostics: tuple[StudioDiagnostic, ...] = ()
            if target_type == "NSS":
                document = self.service.script_from_bytes(
                    payload, game=target_game, resref=target_resref, origin="game_resource"
                )
            elif target_type == "NCS":
                document, diagnostics = self.service.decompile_ncs(
                    payload, game=target_game, resref=target_resref
                )
            elif target_type == "DLG":
                document = self.service.dialogue_from_bytes(
                    payload, game=target_game, resref=target_resref, origin="game_resource"
                )
            else:
                return self._fail(f"Unsupported narrative resource type: {target_type}")
        except Exception as exc:
            log.exception("Could not open %s.%s", target_resref, target_type.lower())
            return self._fail(str(exc).strip() or exc.__class__.__name__)
        return self._register_document(document, source_key=source_key, diagnostics=diagnostics)

    def _read_resource(
        self,
        locator: Mapping[str, Any] | None,
        game: str,
        resref: str,
        restype: str,
    ) -> bytes:
        owner = locator.get("owner") if locator else None
        mode = locator.get("mode") if locator else ""
        if mode == "provider" and owner is not None:
            record = locator.get("record")
            address = getattr(record, "address", None)
            reader = getattr(owner, "read_bytes", None)
            if callable(reader):
                for query in (address, record, {"game": game, "resref": resref, "restype": restype}):
                    if query is None:
                        continue
                    try:
                        return bytes(reader(query) or b"")
                    except Exception:
                        continue
            resolver = getattr(owner, "resolve", None)
            if callable(resolver):
                try:
                    result = resolver(address or {"game": game, "resref": resref, "restype": restype})
                    return bytes(getattr(result, "data", b"") or b"")
                except Exception:
                    pass
        manager = owner if mode == "manager" else self.resource_manager
        if manager is not None:
            getter = getattr(manager, "get_resource_data", None)
            if callable(getter):
                try:
                    return bytes(getter(resref, _RESTYPE_IDS[restype], game) or b"")
                except Exception:
                    pass
            getter = getattr(manager, "get_strict", None) or getattr(manager, "get", None)
            if callable(getter):
                try:
                    return bytes(getter(resref, _RESTYPE_IDS[restype], game) or b"")
                except TypeError:
                    try:
                        return bytes(getter(resref, _RESTYPE_IDS[restype]) or b"")
                    except Exception:
                        pass
                except Exception:
                    pass
        provider = self.resource_provider
        if provider is not None and provider is not owner:
            reader = getattr(provider, "read_bytes", None)
            if callable(reader):
                try:
                    return bytes(reader({"game": game, "resref": resref, "restype": restype}) or b"")
                except Exception:
                    pass
        return b""

    def open_context(self, context: Mapping[str, Any] | None) -> str:
        """Open a Map Studio script/dialogue reference or create it if absent."""

        data = dict(context or {})
        game = _game_key(data.get("game") or "K2")
        restype = str(data.get("restype") or ("DLG" if data.get("kind") == "dialogue" else "NSS")).upper()
        default_resref = "new_dialogue" if restype == "DLG" else "new_script"
        suggested_resref = normalise_script_resref(
            data.get("suggested_resref"),
            fallback=default_resref,
        )
        resref = normalise_script_resref(data.get("resref"), fallback=suggested_resref)
        if self.window is not None:
            self.window.set_target_game(game)
        opened = ""
        if resref:
            opened = self.open_resource(
                game=game,
                resref=resref,
                restype=restype,
                report_missing=False,
            )
        if not opened:
            opened = self.new_dialogue(game, resref) if restype == "DLG" else self.new_script(game, resref)
        participant_keys = (
            "participants",
            "dialogue_participants",
            "placed_creatures",
            "module_creatures",
            "creatures",
        )
        blueprint_keys = ("utc_blueprints", "creature_blueprints")
        has_participant_context = any(key in data for key in (*participant_keys, *blueprint_keys))
        owner_tag = str(data.get("owner_tag") or data.get("creature_tag") or "").strip()
        if restype == "DLG" and (has_participant_context or owner_tag):
            participants: list[object] = []
            blueprints: list[object] = []
            for key in participant_keys:
                participants.extend(_context_rows(data.get(key)))
            for key in blueprint_keys:
                blueprints.extend(_context_rows(data.get(key)))
            if owner_tag:
                participants.append({"tag": owner_tag, "source": "Map Studio owner"})
            self.set_dialogue_participant_context(
                opened,
                participants,
                utc_blueprints=blueprints,
            )
        return opened

    def set_resource_sources(
        self,
        *,
        resource_manager: Any | None = None,
        resource_provider: Any | None = None,
    ) -> None:
        """Replace lazily-created resource sources and refresh the active game."""

        self.resource_manager = resource_manager
        self.resource_provider = resource_provider
        self._participant_appearance_payloads.clear()
        if self._audio_preview is not None:
            self._audio_preview.set_resource_source(
                resource_manager or resource_provider,
                getattr(self.window, "target_game", lambda: "K2")() if self.window is not None else "K2",
            )
        self._catalog_rows.clear()
        self._external_catalog_rows.clear()
        self._catalog_by_id.clear()
        game = getattr(self.window, "target_game", lambda: "K2")() if self.window is not None else "K2"
        self.show_current_catalog(game)

    # ------------------------------------------------------------------
    # Searchable NWScript compiler definitions

    def refresh_script_reference(self, game: str = "K2") -> list[dict[str, Any]]:
        from src.core.scripting.reference import NWScriptReferenceService

        target = _game_key(game)
        if self.window is not None:
            setter = getattr(self.window, "set_script_completion_symbols", None)
            if callable(setter):
                setter(
                    tuple(row.name for row in NWScriptReferenceService.functions(target))
                    + tuple(row.name for row in NWScriptReferenceService.constants(target))
                )
            definition_setter = getattr(self.window, "set_script_completion_definitions", None)
            if callable(definition_setter):
                definition_setter(
                    tuple(
                        {
                            "kind": "function",
                            "name": row.name,
                            "signature": row.signature,
                            "description": row.description,
                            "parameters": tuple(parameter.name for parameter in row.parameters),
                        }
                        for row in NWScriptReferenceService.functions(target)
                    )
                    + tuple(
                        {
                            "kind": "constant",
                            "name": row.name,
                            "signature": f"{row.datatype} {row.name} = {row.value}",
                            "description": f"{target} NWScript constant",
                            "parameters": (),
                        }
                        for row in NWScriptReferenceService.constants(target)
                    )
                )
        return self.search_script_reference(target, "function", "", "")

    def search_script_reference(
        self,
        game: str = "K2",
        kind: str = "function",
        query: str = "",
        category: str = "",
    ) -> list[dict[str, Any]]:
        from src.core.scripting.reference import NWScriptReferenceService

        target = _game_key(game)
        requested_kind = str(kind or "function").lower()
        needle = str(query or "").strip().casefold()
        if requested_kind == "constant":
            definitions = (
                row for row in NWScriptReferenceService.constants(target)
                if not needle or needle in row.name.casefold() or needle in row.value.casefold()
            )
            rows = [
                {
                    "name": row.name,
                    "value": f"{row.datatype} = {row.value}",
                    "description": f"{target} NWScript constant",
                    "insert_text": row.name,
                    "category": "",
                }
                for row in definitions
            ][:1000]
        else:
            functions = NWScriptReferenceService.search_functions(
                query,
                game=target,
                category=category,
                limit=1000,
            )
            rows = [
                {
                    "name": row.name,
                    "signature": row.signature,
                    "description": row.description,
                    "category": row.category,
                    "routine_id": row.routine_id,
                    "insert_text": row.name + "(" + ", ".join(param.name for param in row.parameters) + ")",
                }
                for row in functions
            ]
        if self.window is not None:
            category_setter = getattr(self.window, "set_reference_categories", None)
            if callable(category_setter):
                category_setter(NWScriptReferenceService.categories(target))
            setter = getattr(self.window, "set_reference_rows", None)
            if callable(setter):
                setter(rows, summary=f"{len(rows)} {target} {requested_kind} definition(s)")
        return rows

    def insert_script_reference(self, text: str) -> bool:
        if self.window is None:
            return False
        inserter = getattr(self.window, "insert_into_active_script", None)
        if not callable(inserter) or not inserter(str(text or "")):
            self._set_status("Open a script tab before inserting an NWScript definition.")
            return False
        self._set_status("Inserted NWScript reference into the active script.")
        return True

    # ------------------------------------------------------------------
    # Diagnostics

    def _set_diagnostics(
        self,
        diagnostics: Iterable[StudioDiagnostic | Mapping[str, Any]],
        *,
        summary: str = "",
    ) -> None:
        rows = _diagnostic_rows(diagnostics)
        if self.window is not None:
            self.window.set_diagnostics(rows, summary=summary)
        self.diagnosticsChanged.emit(rows, summary)

    def _invalidate_build(self) -> None:
        was_runtime_ready = self.last_build is not None and self.last_build.ok
        self.last_build = None
        if was_runtime_ready:
            self.buildInvalidated.emit()

    def _set_status(self, message: str) -> None:
        text = str(message or "")
        if self.window is not None:
            status_bar = getattr(self.window, "statusBar", None)
            if callable(status_bar):
                status_bar().showMessage(text, 7000)
        self.statusChanged.emit(text)

    def _fail(self, message: str, *, resource: str = "") -> str:
        text = str(message or "Operation failed.")
        diagnostic = StudioDiagnostic("blocking", "scripting_studio.operation_failed", text, resource)
        self._set_diagnostics((diagnostic,), summary="Operation blocked")
        self._set_status(text)
        self.operationFailed.emit(text)
        return ""


__all__ = ["ScriptingStudioController"]
