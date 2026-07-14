"""Qt orchestration for preservation-safe GFF and blueprint authoring."""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Mapping

from PySide6 import QtCore, QtWidgets

from src.core.scripting.blueprint_authoring import BlueprintGFFDocument, blueprint_rows


log = logging.getLogger(__name__)

_GFF_FILTER = (
    "KOTOR GFF resources ("
    "*.utc *.utp *.utd *.uti *.ute *.utm *.uts *.utt *.utw "
    "*.bic *.btc *.btd *.bti *.bte *.btm *.btp *.btt "
    "*.are *.git *.ifo *.dlg *.jrl *.pth *.fac *.gui *.itp *.gff"
    ");;KOTOR blueprints (*.utc *.utp *.utd *.uti *.ute *.utm *.uts *.utt *.utw);;All files (*)"
)


def _game_key(value: object) -> str:
    text = str(value or "K2").strip().upper()
    return "K1" if text in {"K1", "1", "KOTOR", "KOTOR1"} else "K2"


class ScriptingBlueprintController(QtCore.QObject):
    """Own the open GFF document and connect it to the typed blueprint page."""

    contentChanged = QtCore.Signal()
    documentOpened = QtCore.Signal(str, str)
    documentClosed = QtCore.Signal()
    diagnosticsChanged = QtCore.Signal(object, str)
    statusChanged = QtCore.Signal(str)
    operationFailed = QtCore.Signal(str)

    def __init__(
        self,
        window: Any,
        *,
        game_provider: Callable[[], str] | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.window = window
        self.page = self._find_page(window)
        self.game_provider = game_provider or (lambda: "K2")
        self.document: BlueprintGFFDocument | None = None
        self.resref = ""
        self._bind()
        self._present()
        self._status("Open a KOTOR GFF or blueprint resource to inspect every field.")

    @staticmethod
    def _find_page(window: Any) -> Any | None:
        page = getattr(window, "blueprint_page", None)
        if page is not None:
            return page
        return window if hasattr(window, "fieldEditRequested") else None

    def _bind(self) -> None:
        if self.page is None:
            return
        bindings = (
            ("openRequested", self.open),
            ("saveRequested", self.save),
            ("saveAsRequested", self.save_as),
            ("validateRequested", self.validate),
            ("searchRequested", self.search),
            ("fieldEditRequested", self.edit_field),
        )
        for signal_name, slot in bindings:
            signal = getattr(self.page, signal_name, None)
            if signal is not None:
                signal.connect(slot)

    def _dialog_parent(self) -> QtWidgets.QWidget | None:
        return self.window if isinstance(self.window, QtWidgets.QWidget) else None

    def _status(self, message: str, *, error: bool = False) -> None:
        text = str(message or "Ready")
        if self.page is not None and hasattr(self.page, "set_status"):
            self.page.set_status(text, error=error)
        self.statusChanged.emit(text)

    def _fail(self, error: Exception | str) -> bool:
        message = str(error).strip() or "Blueprint operation failed."
        if isinstance(error, Exception):
            log.error("Blueprint operation failed: %s", message, exc_info=True)
        self._status(message, error=True)
        self.operationFailed.emit(message)
        return False

    def _present(self, *, selected_path: str = "") -> None:
        if self.page is None:
            return
        if self.document is None:
            self.page.set_document({})
            self.page.set_field_rows(())
            self.page.set_diagnostics(())
            return
        self.page.set_document(self.document.summary())
        self.page.set_field_rows(blueprint_rows(self.document.fields()))
        if selected_path:
            self.page.select_path(selected_path)

    @QtCore.Slot()
    def open(self) -> bool:
        selected, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self._dialog_parent(),
            "Open KOTOR GFF or Blueprint",
            "",
            _GFF_FILTER,
        )
        return self.open_path(selected) if selected else False

    def open_path(self, path: str | Path) -> bool:
        """Open an existing GFF path without invoking a file dialog."""

        target = Path(path)
        if not target.is_file():
            return self._fail(f"GFF resource does not exist: {target}")
        try:
            document = BlueprintGFFDocument.load(target)
            # Serialize immediately so unsupported/corrupt graphs fail before
            # replacing the user's currently open document.
            document.to_bytes()
        except Exception as exc:
            return self._fail(exc)
        self.document = document
        self.resref = target.stem
        self._present()
        self.documentOpened.emit(self.resref, document.resource_type)
        self._status(
            f"Opened {target.name}: {document.summary().field_count} field(s), "
            f"{document.summary().editable_field_count} editable."
        )
        return True

    def open_bytes(
        self,
        data: bytes | bytearray | memoryview,
        *,
        resref: str,
        source_path: str | Path | None = None,
    ) -> bool:
        """Open resource bytes supplied by a project, archive, or resource browser."""

        try:
            document = BlueprintGFFDocument.load(data)
            document.to_bytes()
            if source_path is not None:
                document.source_path = Path(source_path)
        except Exception as exc:
            return self._fail(exc)
        self.document = document
        self.resref = str(resref or "").strip() or "new_blueprint"
        self._present()
        self.documentOpened.emit(self.resref, document.resource_type)
        self._status(f"Opened {self.resref}.{document.resource_type} from project resources.")
        return True

    @QtCore.Slot()
    def close(self) -> None:
        self.document = None
        self.resref = ""
        self._present()
        self.documentClosed.emit()
        self._status("Closed the typed GFF resource.")

    @QtCore.Slot()
    def save(self, path: str | Path | None = None) -> bool:
        document = self.document
        if document is None:
            return self._fail("Open a GFF or blueprint resource before saving.")
        target = Path(path) if path is not None else document.source_path
        if target is None:
            return self.save_as()
        try:
            saved = document.save(target)
        except Exception as exc:
            return self._fail(exc)
        self.resref = saved.stem
        self._present()
        self.contentChanged.emit()
        self._status(f"Saved and structurally verified {saved}.")
        return True

    @QtCore.Slot()
    def save_as(self, path: str | Path | None = None) -> bool:
        document = self.document
        if document is None:
            return self._fail("Open a GFF or blueprint resource before saving.")
        target = Path(path) if path is not None else None
        if target is None:
            suggested = f"{self.resref or 'new_blueprint'}.{document.resource_type}"
            selected, _filter = QtWidgets.QFileDialog.getSaveFileName(
                self._dialog_parent(),
                "Save Verified KOTOR GFF",
                suggested,
                _GFF_FILTER,
            )
            if not selected:
                return False
            target = Path(selected)
        if not target.suffix:
            target = target.with_suffix(f".{document.resource_type}")
        return self.save(target)

    @QtCore.Slot(str, str)
    def edit_field(self, path: str, text: str) -> bool:
        document = self.document
        if document is None:
            return self._fail("Open a GFF or blueprint before editing fields.")
        checkpoint = None
        try:
            checkpoint = document.checkpoint()
            document.set_text(path, text)
            # Verify the entire graph after every accepted edit.  The page can
            # now safely expose these bytes to project history at any time.
            document.to_bytes()
        except Exception as exc:
            if checkpoint is not None:
                document.restore(checkpoint)
            self._present(selected_path=str(path))
            return self._fail(exc)
        self._present(selected_path=str(path))
        self.contentChanged.emit()
        self._status(f"Updated {path} as {document.field(path).field_type}; save to commit it to disk.")
        return True

    @QtCore.Slot(str)
    def search(self, query: str) -> tuple[object, ...]:
        """Return matching snapshots while the page preserves full tree ancestry."""

        if self.document is None:
            return ()
        matches = self.document.search(query)
        if str(query).strip():
            self._status(f"{len(matches)} GFF field(s) match “{query}”.")
        return matches

    @QtCore.Slot()
    def validate(self) -> tuple[object, ...]:
        document = self.document
        if document is None:
            self._fail("Open a GFF or blueprint before checking its structure.")
            return ()
        diagnostics = document.validate()
        rows = [asdict(row) for row in diagnostics]
        blocking = sum(row.blocking for row in diagnostics)
        warnings = sum(row.severity.casefold() == "warning" for row in diagnostics)
        summary = f"GFF structure check: {blocking} blocking • {warnings} warning • {len(rows)} total"
        if self.page is not None:
            self.page.set_diagnostics(rows)
        self.diagnosticsChanged.emit(rows, summary)
        self._status(summary, error=bool(blocking))
        return diagnostics

    def current_resource_snapshot(self) -> dict[str, Any] | None:
        """Return verified bytes in the Scripting Project snapshot contract."""

        document = self.document
        if document is None:
            return None
        payload = document.to_bytes()
        source = document.source_path
        return {
            "resref": self.resref or (source.stem if source is not None else "new_blueprint"),
            "restype": document.resource_type,
            "data": payload,
            "role": "runtime",
            "game": _game_key(self.game_provider()),
            "dependencies": (),
            "metadata": {
                "content_type": document.content_type,
                "source_path": str(source or ""),
                "is_blueprint": document.is_blueprint,
                "semantic_readback_verified": True,
                "binary_layout_may_be_normalized": True,
            },
        }

    def resource_snapshots(self) -> tuple[Mapping[str, Any], ...]:
        snapshot = self.current_resource_snapshot()
        return (snapshot,) if snapshot is not None else ()


__all__ = ["ScriptingBlueprintController"]
