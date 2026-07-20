"""Main-shell composition for the standalone Odyssey GUI Editor.

The workflow owns window lifetime and coordinates resource/IO providers.  PIE
consumes ``current_pie_hud_preview_payload`` and never imports the editor or Qt
widget implementation.
"""

from __future__ import annotations

from pathlib import Path
from PySide6 import QtCore, QtWidgets

from src.core.rendering.kotor_gui_preview import KotorGuiPreviewSnapshot


KOTOR_GUI_RESOURCE_TYPE = 2047
KOTOR_TPC_RESOURCE_TYPE = 3007
KOTOR_TGA_RESOURCE_TYPE = 3
_FALLBACK_GUI_CATALOG = (
    "maininterface_p",
    "maininterface_x",
    "dialog_p",
    "dialog_x",
    "container_p",
    "container_x",
    "inventory_p",
    "inventory_x",
    "pause_p",
    "pause_x",
)


def _window_is_alive(window: object) -> bool:
    if window is None:
        return False
    try:
        import shiboken6

        return bool(shiboken6.isValid(window))
    except Exception:
        return isinstance(window, QtWidgets.QWidget)


class GuiEditorWorkflowMixin:
    """Open/reuse the GUI Editor and publish its immutable PIE contract."""

    def _open_gui_editor_window(self, _checked: bool = False):
        window = getattr(self, "gui_editor_window", None)
        if not _window_is_alive(window):
            from src.gui.qt_lib.windows.qt_gui_editor_window import QtGuiEditorWindow

            window = QtGuiEditorWindow(self)
            window.retailGuiRequested.connect(self._load_gui_editor_retail_resource)
            window.retailCatalogRequested.connect(self._populate_gui_editor_catalog)
            window.localGuiRequested.connect(self._open_gui_editor_local_resource)
            window.saveGuiRequested.connect(self._save_gui_editor_document)
            window.piePreviewRequested.connect(self._publish_gui_editor_preview_to_pie)
            window.destroyed.connect(self._clear_gui_editor_references)
            window.set_texture_provider(self._load_gui_editor_texture)
            self.gui_editor_window = window

        configured = str(
            getattr(self, "_current_game", "")
            or (getattr(self, "settings_data", {}) or {}).get("default_game")
            or "K2"
        ).upper()
        window.set_target_game(configured)
        self._populate_gui_editor_catalog(window.target_game())
        window.show()
        window.raise_()
        window.activateWindow()
        if window.active_preview_snapshot() is None:
            QtCore.QTimer.singleShot(0, window.request_selected_retail_gui)
        return window

    def _clear_gui_editor_references(self, _obj: object = None) -> None:
        self.gui_editor_window = None

    def _gui_editor_resource_manager(self):
        manager = getattr(self, "_resource_manager", None)
        if manager is not None:
            return manager
        getter = getattr(self, "_get_resource_manager", None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                return None
        return None

    def _populate_gui_editor_catalog(self, game: str) -> tuple[str, ...]:
        tag = str(game or "K2").strip().upper()
        manager = self._gui_editor_resource_manager()
        rows: tuple[str, ...] = ()
        texture_rows: tuple[str, ...] = ()
        if manager is not None:
            installation_getter = getattr(manager, "get_k2" if tag == "K2" else "get_k1", None)
            installation = installation_getter() if callable(installation_getter) else None
            list_resrefs = getattr(installation, "list_resrefs", None)
            if callable(list_resrefs):
                try:
                    rows = tuple(sorted(str(value).lower() for value in list_resrefs(KOTOR_GUI_RESOURCE_TYPE)))
                except Exception:
                    rows = ()
                try:
                    texture_rows = tuple(
                        sorted(
                            {
                                *(str(value).lower() for value in list_resrefs(KOTOR_TPC_RESOURCE_TYPE)),
                                *(str(value).lower() for value in list_resrefs(KOTOR_TGA_RESOURCE_TYPE)),
                            }
                        )
                    )
                except Exception:
                    texture_rows = ()
        if not rows:
            rows = _FALLBACK_GUI_CATALOG
        window = getattr(self, "gui_editor_window", None)
        if _window_is_alive(window):
            current = getattr(self, "_gui_editor_preview_snapshot", None)
            preferred = current.resref if isinstance(current, KotorGuiPreviewSnapshot) and current.game == tag else ""
            window.set_retail_gui_catalog(rows, preferred=preferred)
            window.set_texture_catalog(texture_rows)
            if manager is None:
                window.set_status("Configure a KOTOR installation to load retail .gui bytes.")
        return rows

    def _load_gui_editor_retail_resource(self, game: str, resref: str) -> KotorGuiPreviewSnapshot | None:
        tag = str(game or "K2").strip().upper()
        name = str(resref or "").strip().lower()
        window = getattr(self, "gui_editor_window", None)
        manager = self._gui_editor_resource_manager()
        if manager is None:
            if _window_is_alive(window):
                window.set_status("No configured KOTOR resource manager is available.")
            return None
        getter = getattr(manager, "get_strict", None) or getattr(manager, "get", None)
        try:
            raw = getter(name, KOTOR_GUI_RESOURCE_TYPE, tag) if callable(getter) else None
        except Exception as exc:
            raw = None
            self._gui_editor_log(f"GUI Editor could not read {tag}:{name}.gui: {exc}", "error")
        if not raw:
            if _window_is_alive(window):
                window.set_status(f"Retail GUI not found in {tag}: {name}.gui")
            return None
        try:
            from src.core.tools.kotor_gui_document import KotorGuiDocument

            document = KotorGuiDocument.from_bytes(
                raw,
                game=tag,
                resref=name,
                source_kind="retail_gui",
            )
            snapshot = document.preview_snapshot()
        except Exception as exc:
            if _window_is_alive(window):
                window.set_status(f"Could not parse {tag}:{name}.gui: {exc}")
            self._gui_editor_log(f"GUI Editor parse failed for {tag}:{name}.gui: {exc}", "error")
            return None
        accepted = True
        if _window_is_alive(window):
            accepted = bool(window.set_document(document))
        if not accepted:
            return None
        self._gui_editor_document = document
        self._gui_editor_preview_snapshot = snapshot
        self._gui_editor_log(
            f"GUI Editor loaded retail {tag}:{name}.gui ({len(snapshot.controls)} controls).",
            "success",
        )
        return snapshot

    def _load_gui_editor_texture(self, game: str, resref: str) -> bytes | None:
        """Resolve a GUI texture strictly from the selected KOTOR install."""

        manager = self._gui_editor_resource_manager()
        getter = getattr(manager, "get_strict", None) if manager is not None else None
        if not callable(getter):
            return None
        tag = str(game or "K2").strip().upper()
        name = str(resref or "").strip().lower()
        if not name:
            return None
        for resource_type in (KOTOR_TPC_RESOURCE_TYPE, KOTOR_TGA_RESOURCE_TYPE):
            try:
                raw = getter(name, resource_type, tag)
            except Exception:
                raw = None
            if raw:
                return bytes(raw)
        return None

    def _open_gui_editor_local_resource(self, game: str) -> object | None:
        window = getattr(self, "gui_editor_window", None)
        if not _window_is_alive(window):
            return None
        filename, _selected = QtWidgets.QFileDialog.getOpenFileName(
            window,
            "Open KOTOR GUI",
            "",
            "KOTOR GUI (*.gui);;All files (*)",
        )
        if not filename:
            return None
        try:
            from src.io.kotor_gui_io import load_kotor_gui_document

            document = load_kotor_gui_document(filename, game=str(game or "K2").upper())
        except Exception as exc:
            window.set_status(f"Could not open {Path(filename).name}: {exc}")
            self._gui_editor_log(f"GUI Editor local open failed for {filename}: {exc}", "error")
            return None
        if not window.set_document(document):
            return None
        self._gui_editor_document = document
        self._gui_editor_preview_snapshot = document.preview_snapshot()
        self._gui_editor_log(f"GUI Editor opened local file {filename}.", "success")
        return document

    def _save_gui_editor_document(self, document: object, save_as: bool = False) -> object | None:
        from src.core.tools.kotor_gui_document import KotorGuiDocument

        if not isinstance(document, KotorGuiDocument):
            return None
        window = getattr(self, "gui_editor_window", None)
        target = document.source_path if not save_as else None
        if target is None:
            initial = str(document.source_path or Path.cwd() / f"{document.resref}.gui")
            filename, _selected = QtWidgets.QFileDialog.getSaveFileName(
                window if _window_is_alive(window) else None,
                "Save KOTOR GUI",
                initial,
                "KOTOR GUI (*.gui)",
            )
            if not filename:
                if _window_is_alive(window):
                    window.set_status("Save cancelled.")
                return None
            target = Path(filename)
        try:
            from src.io.kotor_gui_io import write_kotor_gui_document

            result = write_kotor_gui_document(document, target)
        except Exception as exc:
            if _window_is_alive(window):
                window.set_status(f"Could not save GUI: {exc}")
            self._gui_editor_log(f"GUI Editor save failed for {target}: {exc}", "error")
            return None
        self._gui_editor_document = document
        self._gui_editor_preview_snapshot = document.preview_snapshot()
        if _window_is_alive(window):
            backup = f" Backup: {result.backup_path.name}." if result.backup_path is not None else ""
            window.set_status(f"Saved {result.path.name} ({result.byte_count:,} bytes).{backup}")
        self._gui_editor_log(f"GUI Editor saved {result.path} atomically.", "success")
        return result

    def _publish_gui_editor_preview_to_pie(self, snapshot: object) -> None:
        if not isinstance(snapshot, KotorGuiPreviewSnapshot):
            return
        self._gui_editor_preview_snapshot = snapshot
        self._pie_hud_preview_payload = snapshot.to_pie_payload()
        map_window = getattr(self, "module_editor_window", None)
        receiver = getattr(map_window, "set_pie_hud_preview_snapshot", None)
        accepted = False
        if callable(receiver):
            try:
                receiver(self._pie_hud_preview_payload)
                accepted = True
            except Exception as exc:
                self._gui_editor_log(f"PIE HUD preview hand-off failed: {exc}", "warning")
        window = getattr(self, "gui_editor_window", None)
        if _window_is_alive(window):
            suffix = "sent to the open PIE adapter" if accepted else "stored for the next PIE adapter/session"
            window.set_status(f"Published {snapshot.game}:{snapshot.resref}.gui — {suffix}.")
        self._gui_editor_log(
            f"GUI Editor published {snapshot.game}:{snapshot.resref}.gui as {snapshot.schema}; "
            "PIE does not import the editor window.",
            "info",
        )

    def current_pie_hud_preview_payload(self) -> dict[str, object] | None:
        """Return the last published JSON-safe GUI definition for PIE."""

        payload = getattr(self, "_pie_hud_preview_payload", None)
        return dict(payload) if isinstance(payload, dict) else None

    def _gui_editor_log(self, message: str, level: str = "info") -> None:
        logger = getattr(self, "_log", None)
        if callable(logger):
            logger(message, level)


__all__ = [
    "GuiEditorWorkflowMixin",
    "KOTOR_GUI_RESOURCE_TYPE",
    "KOTOR_TGA_RESOURCE_TYPE",
    "KOTOR_TPC_RESOURCE_TYPE",
]
