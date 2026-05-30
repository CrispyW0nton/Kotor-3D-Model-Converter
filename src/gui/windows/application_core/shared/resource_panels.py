"""Resource browser, 2DA, IPC, module-editor, and rig window handlers."""

from __future__ import annotations

from pathlib import Path

try:
    from PySide6 import QtCore, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.qt_lib.rendering.renderer_settings import RendererSettings
from src.gui.qt_lib.viewports.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE
from src.gui.qt_lib.windows.module_editor_window import ModuleEditorWindow


class ResourcePanelsMixin:
    """Resource browser, 2DA, IPC, module-editor, and rig window handlers."""

    def _populate_resource_panel(self):
        if not hasattr(self, "resource_panel"):
            return
        try:
            from src.core.qt_core.assets import resource_manager as rm

            k1_dir = self.k1_dir_edit.text().strip()
            k2_dir = self.k2_dir_edit.text().strip()
            manager = self._get_resource_manager()
            type_map = {
                "mdl": rm.RES_MDL,
                "mdx": rm.RES_MDX,
                "tpc": rm.RES_TPC,
                "tga": rm.RES_TGA,
                "2da": rm.RES_2DA,
                "dlg": rm.RES_DLG,
                "utc": rm.RES_UTC,
                "uti": getattr(rm, "RES_UTI", None),
                "are": rm.RES_ARE,
                "git": rm.RES_GIT,
                "ifo": rm.RES_IFO,
                "wok": rm.RES_WOK,
            }
            rows = []
            if manager is not None:
                for game, install in (("K1", manager.get_k1()), ("K2", manager.get_k2())):
                    if install is None:
                        continue
                    for ext, res_type in type_map.items():
                        if res_type is None:
                            continue
                        try:
                            names = install.list_resrefs(res_type)
                        except Exception:
                            names = []
                        for name in names:
                            rows.append(
                                {
                                    "game": game,
                                    "resref": name,
                                    "type": ext,
                                    "res_type": res_type,
                                    "source": k1_dir if game == "K1" else k2_dir,
                                }
                            )
        except Exception as exc:
            self._log(f"Resource scan error: {exc}", "error")
            rows = []
            self._resource_manager = None
            self._resource_manager_dirs = ("", "")

        if not rows:
            for row in self._library_rows:
                if row.get("template"):
                    continue
                rows.append(
                    {
                        "game": row.get("game", ""),
                        "resref": row.get("resref", ""),
                        "source": row.get("source", ""),
                        "type": "mdl",
                        "res_type": 2002,
                    }
                )
        self.resource_panel.set_resources(rows)
        self.resource_panel.text_preview.setPlainText(f"{len(rows)} resources indexed.")
    def _preview_resource_row(self, row: dict):
        raw = None
        manager = getattr(self, "_resource_manager", None)
        if manager is not None and row.get("res_type"):
            try:
                raw = manager.get(str(row.get("resref", "")), int(row.get("res_type")), str(row.get("game", "K1")))
            except Exception as exc:
                self._log(f"Resource preview read error: {exc}", "warning")
        text = "\n".join(
            [
                f"Resource: {row.get('resref', '')}.{row.get('type', '')}",
                f"Game:     {row.get('game', '')}",
                f"Source:   {row.get('source', '')}",
                f"Bytes:    {len(raw) if raw is not None else '(not loaded)'}",
                "",
                (raw[:4096].decode("latin-1", errors="replace") if raw else ""),
            ]
        )
        self.resource_panel.text_preview.setPlainText(text)
        hex_raw = raw if raw is not None else repr(row).encode("utf-8")
        lines = []
        for offset in range(0, min(len(hex_raw), 1024), 16):
            chunk = hex_raw[offset:offset + 16]
            hex_part = " ".join(f"{byte:02x}" for byte in chunk)
            asc_part = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
            lines.append(f"{offset:06x}  {hex_part:<48}  {asc_part}")
        if len(hex_raw) > 1024:
            lines.append(f"... ({len(hex_raw)} total bytes)")
        self.resource_panel.hex_preview.setPlainText("\n".join(lines))
    def _activate_resource_row(self, row: dict):
        if str(row.get("type", "")).lower() == "mdl" and row.get("resref") and row.get("game"):
            self._start_resource_load(str(row["resref"]), str(row["game"]))
        elif str(row.get("type", "")).lower() == "2da" and row.get("resref") and row.get("game"):
            self._show_detachable_panel("2das")
            self.twoda_panel.game_combo.setCurrentText(str(row["game"]))
            self._load_twoda_table(str(row["game"]), str(row["resref"]))
        else:
            self._log(f"No activation handler for {row.get('resref', 'resource')}", "warning")
    def _refresh_twoda_panel(self, game: str):
        self.twoda_panel.listbox.clear()
        self.twoda_panel.table.clear()
        try:
            from src.core.qt_core.assets import resource_manager as rm

            manager = rm.ResourceManager()
            k1_dir = self.k1_dir_edit.text().strip()
            k2_dir = self.k2_dir_edit.text().strip()
            if k1_dir:
                manager.set_k1_dir(k1_dir)
            if k2_dir:
                manager.set_k2_dir(k2_dir)
            install = manager.get_k1() if game == "K1" else manager.get_k2()
            names = sorted(install.list_resrefs(rm.RES_2DA)) if install is not None else []
            self._resource_manager = manager
            self._resource_manager_dirs = (k1_dir, k2_dir)
            self.twoda_panel.listbox.addItems(names)
            self._log(f"2DA list refreshed: {len(names)} tables for {game}", "success")
        except Exception as exc:
            self._log(f"2DA refresh error: {exc}", "error")
    def _load_twoda_table(self, game: str, name: str):
        if not name:
            return
        try:
            from src.core.qt_core.assets import resource_manager as rm
            from src.core.qt_core.templates.twoda import TwoDA

            manager = getattr(self, "_resource_manager", None)
            if manager is None:
                manager = rm.ResourceManager()
                k1_dir = self.k1_dir_edit.text().strip()
                k2_dir = self.k2_dir_edit.text().strip()
                if k1_dir:
                    manager.set_k1_dir(k1_dir)
                if k2_dir:
                    manager.set_k2_dir(k2_dir)
                self._resource_manager = manager
                self._resource_manager_dirs = (k1_dir, k2_dir)
            raw = manager.get(name, rm.RES_2DA, game)
            if not raw:
                self._log(f"2DA not found: {game}:{name}", "warning")
                return
            table = TwoDA.from_bytes(raw, name=name)
            columns = list(getattr(table, "columns", []) or [])
            rows = list(table)
            self.twoda_panel.table.clear()
            self.twoda_panel.table.setColumnCount(len(columns))
            self.twoda_panel.table.setHorizontalHeaderLabels(columns)
            self.twoda_panel.table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for col_index, column in enumerate(columns):
                    value = row.get(column, "")
                    self.twoda_panel.table.setItem(row_index, col_index, QtWidgets.QTableWidgetItem(str(value)))
            self._log(f"Loaded 2DA {game}:{name} ({len(rows)} rows)", "success")
        except Exception as exc:
            self._log(f"2DA load error: {exc}", "error")
    def _about_modular(self):
        QtWidgets.QMessageBox.information(
            self,
            "Module Editor",
            "GhostRigger Module Editor\n\n"
            "The standalone Module Editor creates and opens KMAP level projects, "
            "loads LYT/WOK data, tracks rooms/modules/blueprints, validates level "
            "state, and generates build/export manifests without overwriting source "
            "KOTOR data.",
        )
    def _validate_current_character(self):
        try:
            from src.core.qt_core.geometry.model_data import CharacterScene, PartSlot
            from src.core.qt_core.diagnostics.validation_service import ValidationService

            scene = None
            builder = getattr(self, "_character_builder_window", None)
            if builder is not None and getattr(builder, "scene", None) is not None:
                scene = builder.scene
            else:
                scene = CharacterScene(game_version="K1")
                if self._current_model is not None:
                    scene.assign(PartSlot.HEAD_SHELL, self._current_model, resref=getattr(self._current_model, "name", "model"))
            issues = ValidationService(scene).validate()
            lines = [str(issue) for issue in issues] if issues else ["No issues found."]
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("Character Validation Results")
            dialog.resize(720, 420)
            layout = QtWidgets.QVBoxLayout(dialog)
            text = QtWidgets.QPlainTextEdit()
            text.setReadOnly(True)
            text.setPlainText("\n".join(lines))
            layout.addWidget(text, 1)
            close_button = QtWidgets.QPushButton("Close")
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button, 0, QtCore.Qt.AlignRight)
            dialog.exec()
        except Exception as exc:
            self._log(f"Validation error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Validate", str(exc))
    def _ipc_ping(self, program_name: str, port: int):
        try:
            from src.ipc.client import ping_program

            ok, msg = ping_program(program_name, port, timeout=1.5)
            if ok:
                QtWidgets.QMessageBox.information(self, f"IPC: {program_name}", msg)
            else:
                QtWidgets.QMessageBox.warning(self, f"IPC: {program_name}", msg)
            self._log(f"IPC ping {program_name}: {msg}", "success" if ok else "warning")
        except Exception as exc:
            self._log(f"IPC ping error: {exc}", "error")
    def _ipc_notify_saved(self):
        if not self._model_path:
            QtWidgets.QMessageBox.information(self, "IPC", "No model or blueprint is currently open.")
            return
        try:
            from src.ipc.client import notify_blueprint_saved

            resref = Path(self._model_path).stem
            notify_blueprint_saved(resref, "utc")
            self._log(f"IPC: sent blueprint_saved to GModular for {resref}", "info")
        except Exception as exc:
            self._log(f"IPC notify error: {exc}", "error")
    def _ipc_refresh_gmodular(self):
        try:
            from src.ipc.client import refresh_gmodular_viewport

            refresh_gmodular_viewport()
            self._log("IPC: sent refresh_viewport to GModular", "info")
        except Exception as exc:
            self._log(f"IPC refresh error: {exc}", "error")
    def _open_uv_viewer(self):
        viewport = getattr(self, "viewport", None)
        if viewport is None:
            self._not_migrated("Open UV Viewer...")
            return
        viewport.open_uv_viewer()
    def _open_module_editor_window(self):
        window = getattr(self, "module_editor_window", None)
        if window is None:
            window = ModuleEditorWindow(
                self,
                theme_manager=getattr(self, "theme_manager", None),
                layout_manager=getattr(self, "layout_manager", None),
            )
            self.module_editor_window = window
            window.set_library_rows(getattr(self, "_library_rows", []) or [])
        window.set_renderer_settings(RendererSettings.from_settings(self.settings_data))
        window.set_navigation_profile(
            self.settings_data.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
        )
        window.set_library_rows(getattr(self, "_library_rows", []) or [])
        window.show()
        window.raise_()
        window.activateWindow()
    def _send_library_row_to_module_editor(self, row: dict) -> None:
        self._open_module_editor_window()
        window = getattr(self, "module_editor_window", None)
        if window is None:
            return
        window.import_library_asset(row)
        resref = str(row.get("resref") or "asset")
        game = str(row.get("game") or "")
        self._log(f"Level Editor <- {game}:{resref}", "success")
    def _open_rig_window(self):
        window = getattr(self, "rig_window", None)
        if window is None:
            self._not_migrated("Rigging Window")
            return
        window.show()
        window.raise_()
        window.activateWindow()
