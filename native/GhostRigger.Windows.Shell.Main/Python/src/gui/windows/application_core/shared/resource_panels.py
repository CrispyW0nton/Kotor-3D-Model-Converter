"""Resource browser, 2DA, IPC, module-editor, and rig window handlers."""

from __future__ import annotations

from pathlib import Path

try:
    from PySide6 import QtCore, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.core.rendering.renderer_settings import RendererSettings
from src.core.rendering.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE
from src.gui.qt_lib.windows.module_editor_window import ModuleEditorWindow


class ResourcePanelsMixin:
    """Resource browser, 2DA, IPC, module-editor, and rig window handlers."""

    def _populate_resource_panel(self):
        if not hasattr(self, "resource_panel"):
            return
        try:
            from src.core.assets import resource_manager as rm

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
        elif str(row.get("type", "")).lower() in {"utc", "utp", "utd"} and row.get("resref"):
            self._open_blueprint_resource_from_ipc(
                str(row.get("type", "")).lower(),
                str(row.get("resref", "")),
                str(row.get("game", "")),
                str(row.get("source", "")),
            )
        else:
            self._log(f"No activation handler for {row.get('resref', 'resource')}", "warning")

    def _ipc_resource_rows(self) -> list[dict]:
        panel = getattr(self, "resource_panel", None)
        rows = list(getattr(panel, "_rows", []) or []) if panel is not None else []
        if not rows:
            self._populate_resource_panel()
            rows = list(getattr(panel, "_rows", []) or []) if panel is not None else []
        return [dict(row) for row in rows]

    def _ipc_resource_row_summary(self, row: dict) -> dict:
        keys = ("resref", "name", "type", "ext", "game", "source", "res_type", "path", "module_dir")
        summary = {}
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                summary[key] = value if isinstance(value, int) else str(value)
        if "type" not in summary and "ext" in summary:
            summary["type"] = summary["ext"]
        return summary

    def _ipc_resource_row_matches(self, row: dict, query: str, filters: dict) -> bool:
        game = str(filters.get("game") or "").strip().upper()
        if game and game != "ALL" and str(row.get("game") or "").upper() != game:
            return False
        res_type = str(filters.get("type") or filters.get("ext") or "").strip().lower().lstrip(".")
        row_type = str(row.get("type") or row.get("ext") or "").strip().lower().lstrip(".")
        if res_type and res_type != "all" and row_type != res_type:
            return False
        if not query:
            return True
        haystack = " ".join(
            str(row.get(key) or "")
            for key in ("resref", "name", "type", "ext", "game", "source", "path", "module_dir")
        ).lower()
        return query.lower() in haystack

    def _ipc_resource_search(self, query: str = "", limit: object = 50, filters: dict | None = None) -> dict:
        try:
            max_rows = max(1, min(1000, int(limit)))
        except (TypeError, ValueError):
            max_rows = 50
        filter_data = dict(filters or {})
        query_text = str(query or "").strip()
        rows = self._ipc_resource_rows()
        matches = [row for row in rows if self._ipc_resource_row_matches(row, query_text, filter_data)]
        return {
            "total": len(rows),
            "count": min(len(matches), max_rows),
            "query": query_text,
            "rows": [self._ipc_resource_row_summary(row) for row in matches[:max_rows]],
        }

    def _ipc_find_resource_row(self, query: str = "", filters: dict | None = None) -> dict | None:
        query_text = str(query or "").strip()
        filter_data = dict(filters or {})
        matches = [row for row in self._ipc_resource_rows() if self._ipc_resource_row_matches(row, query_text, filter_data)]
        if not matches:
            return None
        exact = query_text.lower()
        if exact:
            for row in matches:
                name = str(row.get("resref") or row.get("name") or "").lower()
                if name == exact:
                    return dict(row)
        return dict(matches[0])

    def _select_resource_browser_row(self, row: dict, query: str = "") -> bool:
        panel = getattr(self, "resource_panel", None)
        if panel is None:
            return False
        try:
            game = str(row.get("game") or "").upper()
            row_type = str(row.get("type") or row.get("ext") or "").upper()
            if hasattr(panel, "game_combo"):
                panel.game_combo.setCurrentText(game if game in {"K1", "K2"} else "All")
            if hasattr(panel, "type_combo"):
                panel.type_combo.setCurrentText(row_type if row_type else "All")
            if hasattr(panel, "search_edit"):
                panel.search_edit.setText(query or str(row.get("resref") or row.get("name") or ""))
            if hasattr(panel, "_apply_filter"):
                panel._apply_filter()
            listbox = getattr(panel, "listbox", None)
            if listbox is None:
                return False
            target_name = str(row.get("resref") or row.get("name") or "").lower()
            target_type = str(row.get("type") or row.get("ext") or "").lower()
            target_game = str(row.get("game") or "").upper()
            for index in range(listbox.count()):
                item = listbox.item(index)
                item_row = item.data(QtCore.Qt.UserRole) or {}
                if (
                    str(item_row.get("resref") or item_row.get("name") or "").lower() == target_name
                    and str(item_row.get("type") or item_row.get("ext") or "").lower() == target_type
                    and str(item_row.get("game") or "").upper() == target_game
                ):
                    listbox.setCurrentItem(item)
                    listbox.scrollToItem(item)
                    setattr(self, "_ipc_selected_resource_row", dict(item_row))
                    self._preview_resource_row(dict(item_row))
                    return True
        except Exception as exc:
            self._log(f"IPC resource_select UI sync failed: {exc}", "warning")
        return False

    def _ipc_resource_select(
        self,
        query: str = "",
        filters: dict | None = None,
        activate: object = False,
    ) -> dict:
        row = self._ipc_find_resource_row(query, filters)
        if row is None:
            self._log(f"IPC resource_select: no match for {query}", "warning")
            return {"selected": False, "query": str(query or ""), "row": {}}
        ui_selected = self._select_resource_browser_row(row, str(query or ""))
        if bool(activate):
            self._activate_resource_row(row)
        self._log(
            f"IPC resource_select: {row.get('game', '')}:{row.get('resref', row.get('name', ''))}.{row.get('type', row.get('ext', ''))}",
            "info",
        )
        return {
            "selected": True,
            "ui_selected": ui_selected,
            "activated": bool(activate),
            "query": str(query or ""),
            "row": self._ipc_resource_row_summary(row),
        }

    def _ipc_resource_state_snapshot(self) -> dict:
        panel = getattr(self, "resource_panel", None)
        rows = list(getattr(panel, "_rows", []) or []) if panel is not None else []
        selected = {}
        visible_count = 0
        if panel is not None:
            try:
                listbox = getattr(panel, "listbox", None)
                visible_count = listbox.count() if listbox is not None else 0
                item = listbox.currentItem() if listbox is not None else None
                row = item.data(QtCore.Qt.UserRole) if item is not None else None
                selected = self._ipc_resource_row_summary(row) if row else {}
            except Exception:
                selected = {}
        if not selected:
            fallback = getattr(self, "_ipc_selected_resource_row", None)
            selected = self._ipc_resource_row_summary(fallback) if fallback else {}
        return {"total": len(rows), "visible": visible_count, "selected": selected}

    def _open_blueprint_resource_from_ipc(
        self,
        resource_type: str,
        resref: str,
        game: str = "",
        module_dir: str = "",
    ) -> None:
        resource_type = str(resource_type or "").lower().strip()
        resref = str(resref or "").strip()
        game = str(game or getattr(self, "_current_game", "") or "K2").upper()
        if not resref:
            self._log(f"IPC open_{resource_type}: missing resref", "warning")
            return
        try:
            from src.core.assets import resource_manager as rm

            type_map = {
                "utc": rm.RES_UTC,
                "utp": rm.RES_UTP,
                "utd": rm.RES_UTD,
            }
            res_type = type_map.get(resource_type)
            if res_type is None:
                self._log(f"IPC open blueprint: unsupported type {resource_type}", "warning")
                return
            manager = self._resource_manager or self._get_resource_manager()
            raw = None
            if manager is not None:
                try:
                    raw = manager.get(resref, res_type, game)
                except Exception as exc:
                    self._log(f"IPC open_{resource_type} read warning: {exc}", "warning")
            open_window = getattr(self, "_open_blueprint_editor_window", None)
            if callable(open_window):
                open_window()
            window = getattr(self, "blueprint_window", None)
            panel = getattr(window, "panel", None) or getattr(self, "blueprint_panel", None)
            load_payload = getattr(panel, "load_ipc_resource_payload", None)
            if callable(load_payload):
                load_payload(
                    resource_type=resource_type,
                    resref=resref,
                    game=game,
                    module_dir=module_dir,
                    raw=raw,
                )
            if window is not None:
                window.show()
                window.raise_()
                window.activateWindow()
            self._log(f"IPC open_{resource_type}: {game}:{resref}", "success")
        except Exception as exc:
            self._log(f"IPC open_{resource_type} error: {exc}", "error")
    def _refresh_twoda_panel(self, game: str):
        self.twoda_panel.listbox.clear()
        self.twoda_panel.table.clear()
        try:
            from src.core.assets import resource_manager as rm

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
            from src.core.assets import resource_manager as rm
            from src.core.templates.twoda import TwoDA

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
            from src.core.geometry.model_data import CharacterScene, PartSlot
            from src.core.diagnostics.validation_service import ValidationService

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
        window.resource_manager = self._resource_manager or self._get_resource_manager()
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
    def _send_library_row_to_new_module_editor(self, row: dict) -> None:
        self._open_module_editor_window()
        window = getattr(self, "module_editor_window", None)
        if window is None:
            return
        if not window._confirm_discard_or_save():
            return
        window.controller.new_project()
        window._refresh_all("Created new KMAP project.")
        window.import_library_asset(row)
        resref = str(row.get("resref") or "asset")
        game = str(row.get("game") or "")
        self._log(f"New Level Editor <- {game}:{resref}", "success")
    def _open_rig_window(self):
        window = getattr(self, "rig_window", None)
        if window is None:
            self._not_migrated("Rigging Window")
            return
        window.show()
        window.raise_()
        window.activateWindow()
