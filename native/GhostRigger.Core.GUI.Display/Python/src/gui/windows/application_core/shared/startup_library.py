"""Startup progress and game-library workflows for the main window."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from PySide6 import QtCore, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.qt_lib.dialogs.qt_settings_dialog import save_settings
from src.gui.qt_lib.windows.progress_toast import (
    FeedbackAction,
    OperationFeedback,
    OperationPhase,
    QtProgressToast,
)
from src.gui.windows.application_core.application_core_lib.shared.workers import (
    AutoDetectWorker,
    LibraryBatchExportWorker,
)


class StartupLibraryMixin:
    """Progress toasts, game-dir detection, and content-browser startup loading."""

    @QtCore.Slot(str, str)
    def _on_library_dirs_changed(self, k1_dir: str, k2_dir: str):
        self.k1_dir_edit.setText(k1_dir)
        self.k2_dir_edit.setText(k2_dir)
        self.settings_data["k1_dir"] = k1_dir
        self.settings_data["k2_dir"] = k2_dir
        dialog = getattr(self, "_settings_dialog", None)
        if dialog is not None:
            try:
                dialog.set_game_dirs(k1_dir, k2_dir)
            except RuntimeError:
                pass
        try:
            save_settings(self.settings_path, self.settings_data)
        except Exception as exc:
            self._log(f"Could not save game directories: {exc}", "warning")
        self._resource_manager = None
        self._resource_manager_dirs = ("", "")
        self.library_panel.set_status("Game directories updated")
        self._log("Game directories updated. Run Scan to refresh the library.", "success")

    def _show_progress_toast(self, title: str, detail: str):
        self._show_operation_feedback(
            OperationFeedback(OperationPhase.BUSY, title, detail)
        )

    def _update_progress_toast(self, title: str, detail: str, value: int, total: int):
        toast = self._ensure_progress_toast()
        toast.update_progress(title, detail, value, total)

    def _finish_progress_toast(self, title: str, detail: str):
        self._show_operation_feedback(
            OperationFeedback(OperationPhase.SUCCEEDED, title, detail),
            delay_ms=2200,
        )

    def _show_operation_feedback(
        self,
        feedback: OperationFeedback,
        *,
        callbacks=None,
        delay_ms: int | None = None,
    ) -> None:
        toast = self._ensure_progress_toast()
        toast.present(feedback, callbacks=callbacks, delay_ms=delay_ms)

    def _ensure_progress_toast(self) -> QtProgressToast:
        if self._progress_toast is None:
            self._progress_toast = QtProgressToast(self)
            self.theme_manager.register_theme_aware_widget(self._progress_toast)
        self._apply_progress_toast_theme()
        return self._progress_toast

    def _apply_progress_toast_theme(self) -> None:
        toast = getattr(self, "_progress_toast", None)
        if toast is None:
            return
        theme = getattr(self.theme_manager, "current_theme", None) or self.theme_manager.get_theme()
        native = getattr(getattr(self.theme_manager, "settings", None), "theme_mode", "") == "native"
        if native and hasattr(toast, "apply_native_theme"):
            toast.apply_native_theme()
        else:
            toast.apply_ghost_theme(theme)

    @QtCore.Slot(object)
    def _on_theme_apply_started(self, theme) -> None:
        if getattr(self, "_suppress_theme_progress_toast", False):
            return
        name = getattr(theme, "name", getattr(theme, "id", "theme"))
        self._show_progress_toast("Applying theme", f"Preparing {name}...")

    @QtCore.Slot(str, int, int)
    def _on_theme_apply_progress(self, detail: str, value: int, total: int) -> None:
        if getattr(self, "_suppress_theme_progress_toast", False):
            return
        self._update_progress_toast("Applying theme", detail, value, total)

    @QtCore.Slot(object, float)
    def _on_theme_apply_finished(self, theme, total_ms: float) -> None:
        if getattr(self, "_suppress_theme_progress_toast", False):
            return
        name = getattr(theme, "name", getattr(theme, "id", "Theme"))
        self._finish_progress_toast("Theme applied", f"{name} applied in {total_ms:.0f} ms.")

    @QtCore.Slot(str)
    def _on_theme_apply_failed(self, detail: str) -> None:
        if getattr(self, "_suppress_theme_progress_toast", False):
            return
        self._show_operation_feedback(
            OperationFeedback(
                phase=OperationPhase.FAILED,
                title="Theme could not be applied",
                detail="The previous appearance remains active.",
                reason=detail[:180],
                actions=(
                    FeedbackAction(
                        "open_settings",
                        "Open Settings",
                        "Review appearance and renderer settings.",
                    ),
                ),
                preserves_work=True,
            ),
            callbacks={"open_settings": self._open_settings_dialog},
        )

    @QtCore.Slot(str, int, int)
    def _on_model_load_progress(self, detail: str, value: int, total: int):
        self._update_progress_toast("Loading model", detail, value, total)
        self.statusBar().showMessage(detail)

    @QtCore.Slot(int, int)
    def _on_viewport_gpu_upload_progress(self, uploaded: int, total: int):
        if total <= 0:
            return
        self._pending_gpu_upload_total = total
        self._update_progress_toast(
            "Uploading mesh buffers",
            f"Moving mesh buffers into GPU memory ({uploaded}/{total})...",
            uploaded,
            total,
        )
        if uploaded >= total:
            self._pending_gpu_upload_model_id = 0
            self._pending_gpu_upload_total = 0
            self._finish_progress_toast("Model ready", "Mesh buffers are resident in GPU memory.")

    def _finish_model_load_toast_if_pending(self, model_id: int):
        if self._pending_gpu_upload_model_id != model_id:
            return
        self._pending_gpu_upload_model_id = 0
        self._pending_gpu_upload_total = 0
        self._finish_progress_toast("Model ready", "Model loaded; GPU upload will continue on demand.")

    def _auto_detect_dirs(self):
        if self._auto_detect_worker_is_running():
            return
        self._show_progress_toast(
            "Detecting game installs",
            "Looking for KotOR 1 and KotOR 2 directories...",
        )
        self._log("Auto-detecting game directories...")

        worker = AutoDetectWorker()
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_auto_detect_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_auto_detect_thread", None))
        thread.finished.connect(lambda: setattr(self, "_auto_detect_worker", None))
        self._auto_detect_thread = thread
        self._auto_detect_worker = worker
        thread.start()

    @QtCore.Slot(str, str, str)
    def _on_auto_detect_finished(self, k1_dir: str, k2_dir: str, error: str):
        if error:
            error_lines = error.strip().splitlines()
            self._show_operation_feedback(
                OperationFeedback(
                    phase=OperationPhase.FAILED,
                    title="Game install detection failed",
                    detail="Review the settings or retry the search.",
                    reason=(error_lines[-1] if error_lines else "Unknown detection error.")[:180],
                    actions=self._install_detection_actions(),
                    preserves_work=True,
                ),
                callbacks=self._install_detection_callbacks(),
            )
            self._log(f"Auto-detect failed:\n{error}", "error")
            return
        if not (k1_dir or k2_dir):
            self._show_operation_feedback(
                OperationFeedback(
                    phase=OperationPhase.BLOCKED,
                    title="No KotOR installs were found",
                    detail="Set the game directories manually, or retry after installing or moving the games.",
                    reason="None of the detected folders contained a valid KotOR installation.",
                    searched_scopes=(
                        "saved GhostStudio game paths",
                        "KOTOR1_DIR and KOTOR2_DIR environment variables",
                        "Steam libraries",
                        "GOG install locations",
                        "platform default install folders",
                        "project-local game_data folders",
                    ),
                    actions=self._install_detection_actions(),
                    preserves_work=True,
                ),
                callbacks=self._install_detection_callbacks(),
            )
            self.library_panel.set_status("No KotOR directories found")
            self._log("No KotOR installation found automatically.", "warning")
            return
        self._on_library_dirs_changed(k1_dir or self.k1_dir_edit.text().strip(), k2_dir or self.k2_dir_edit.text().strip())
        self._scan_library()

    @staticmethod
    def _install_detection_actions() -> tuple[FeedbackAction, ...]:
        return (
            FeedbackAction(
                "open_settings",
                "Open Settings",
                "Choose the KotOR game folders manually.",
            ),
            FeedbackAction(
                "retry_detection",
                "Retry Detection",
                "Search the known install locations again.",
            ),
        )

    def _install_detection_callbacks(self):
        return {
            "open_settings": self._open_settings_dialog,
            "retry_detection": self._auto_detect_dirs,
        }

    def _auto_detect_dirs_on_startup(self):
        if self._auto_detect_worker_is_running() or self._scan_worker_is_running():
            return
        self._auto_detect_dirs()

    def _apply_deferred_preloaded_library(self) -> None:
        if getattr(self, "_preloaded_library_applied", False):
            return
        self._apply_preloaded_library()

    def _apply_preloaded_library(self) -> None:
        if getattr(self, "_preloaded_library_applied", False):
            return
        preloaded = getattr(self, "_preloaded_library", {}) or {}
        if not preloaded:
            return
        if preloaded.get("pending"):
            self.library_panel.set_status("Startup library scan finishing in background")
            return
        self._preloaded_library_applied = True
        k1_dir = str(preloaded.get("k1_dir") or "").strip()
        k2_dir = str(preloaded.get("k2_dir") or "").strip()
        if k1_dir or k2_dir:
            self._on_library_dirs_changed(k1_dir or self.k1_dir_edit.text().strip(), k2_dir or self.k2_dir_edit.text().strip())
            manager = preloaded.get("_resource_manager")
            if manager is not None:
                self._resource_manager = manager
                self._resource_manager_dirs = (k1_dir, k2_dir)
        error = str(preloaded.get("error") or "")
        if error and not preloaded.get("rows"):
            self.library_panel.set_status("Startup library scan unavailable")
            self._log(f"Startup library preload warning:\n{error}", "warning")
            self.statusBar().showMessage("Library preload unavailable")
            return
        rows = list(preloaded.get("rows") or [])
        if not rows:
            status = "No KotOR directories found" if not (k1_dir or k2_dir) else "No models indexed"
            self.library_panel.set_status(status)
            self.statusBar().showMessage(status)
            self._log(status, "warning")
            return
        self._library_rows = rows
        self.library_list.clear()
        self.library_list.addItem("Content Browser is preparing indexed models...")
        if hasattr(self.library_panel, "set_rows_deferred"):
            self.library_panel.set_rows_deferred(rows)
        else:
            self.library_panel.set_rows(rows)
        self.library_panel.set_status(f"{len(rows)} models")
        module_editor_window = getattr(self, "module_editor_window", None)
        if module_editor_window is not None:
            module_editor_window.set_library_rows(rows)
        stock_module_editor_window = getattr(self, "stock_module_editor_window", None)
        configure_stock_module_editor = getattr(self, "_configure_stock_module_editor_game_library", None)
        if stock_module_editor_window is not None and callable(configure_stock_module_editor):
            configure_stock_module_editor(stock_module_editor_window)
        QtCore.QTimer.singleShot(300, self._finish_preloaded_library_after_first_paint)
        self.statusBar().showMessage(f"{len(rows)} models")
        self._log(f"Startup library preload complete: {len(rows)} models", "success")

    def _finish_preloaded_library_after_first_paint(self) -> None:
        rows = list(getattr(self, "_library_rows", []) or [])
        if not rows:
            return
        self._unreal_refresh_supermodel_library()
        resource_dock = getattr(self, "_detachable_panels", {}).get("resources")
        if resource_dock is not None and resource_dock.isVisible():
            self._populate_resource_panel()
        self._populate_animation_library_from_current_model()

    def _finish_pending_prelaunch_after_first_paint(self) -> None:
        prelaunch_run = getattr(self, "_pending_prelaunch_run", None)
        if prelaunch_run is None:
            return

        if not getattr(self, "_pending_prelaunch_diagnostics_applied", False) and prelaunch_run.task_done(0):
            try:
                diagnostics = prelaunch_run.result(0, timeout=0) or {}
                self._preloaded_renderer_capabilities = list(diagnostics.get("renderer_capabilities") or [])
                self._preloaded_hardware_diagnostics = dict(diagnostics.get("hardware_diagnostics") or {})
                self._log("Startup renderer and hardware diagnostics completed in the background.", "success")
            except Exception as exc:
                self._log(f"Startup renderer and hardware diagnostics failed after launch: {exc}", "warning")
            self._pending_prelaunch_diagnostics_applied = True

        if not getattr(self, "_pending_prelaunch_library_applied", False) and prelaunch_run.task_done(1):
            try:
                payload = prelaunch_run.result(1, timeout=0) or {}
                self._preloaded_library = dict(payload.get("preloaded_library") or {})
                self._apply_preloaded_library()
                self._log("Startup library and detection work completed in the background.", "success")
            except Exception as exc:
                self._log(f"Startup library preparation failed after launch: {exc}", "warning")
            self._pending_prelaunch_library_applied = True

        if prelaunch_run.done():
            prelaunch_run.shutdown()
            self._pending_prelaunch_run = None
            return
        QtCore.QTimer.singleShot(250, self._finish_pending_prelaunch_after_first_paint)

    def _extract_library_row(self, row: dict):
        resref = str(row.get("resref") or "")
        game = str(row.get("game") or "K1").upper()
        if not resref:
            return
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(self, f"Extract {game}:{resref}")
        if not out_dir:
            return
        try:
            written = self._extract_model_resource(row, out_dir)
            QtWidgets.QMessageBox.information(
                self,
                "Extracted",
                f"Extracted {len(written)} file(s) to:\n{out_dir}",
            )
            self._log(f"Extracted {game}:{resref} -> {Path(out_dir).name}", "success")
        except Exception as exc:
            self._log(f"Extract failed: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Extract", str(exc))

    def _handle_content_browser_asset_action(self, action: str, row: dict) -> None:
        resref = str(row.get("resref") or "")
        game = str(row.get("game") or "K1").upper()
        if action == "extract_fbx_openfbx":
            QtWidgets.QMessageBox.information(
                self,
                "Extract FBX",
                "OpenFBX export for content-browser assets is not wired yet.",
            )
            self._log(f"OpenFBX asset export requested for {game}:{resref}", "info")
        elif action == "extract_fbx_autodesk":
            QtWidgets.QMessageBox.information(
                self,
                "Extract FBX",
                "Autodesk FBX export for content-browser assets requires an installed SDK and is not wired from this menu yet.",
            )
            self._log(f"Autodesk FBX asset export requested for {game}:{resref}", "info")

    def _extract_model_resource(self, row: dict, out_dir: str) -> list[str]:
        from src.core.graphics.tpc import _is_tpc_data

        mgr = self._get_resource_manager()
        if mgr is None:
            raise RuntimeError("Set a KotOR game directory before extracting library resources.")
        resref = str(row.get("resref") or "")
        game = str(row.get("game") or "K1").upper()
        os.makedirs(out_dir, exist_ok=True)
        written: list[str] = []
        mdl = mgr.get_mdl(resref, game)
        mdx = mgr.get_mdx(resref, game) or b""
        if not mdl:
            raise FileNotFoundError(f"{game}:{resref}.mdl")
        mdl_path = os.path.join(out_dir, f"{resref}.mdl")
        Path(mdl_path).write_bytes(mdl)
        written.append(mdl_path)
        if mdx:
            mdx_path = os.path.join(out_dir, f"{resref}.mdx")
            Path(mdx_path).write_bytes(mdx)
            written.append(mdx_path)

        try:
            from src.core.game.kotor_loader import load_model_from_bytes

            model = load_model_from_bytes(mdl, mdx)
            tex_names = {
                str(getattr(node, "texture", "") or "").strip()
                for node in model.all_nodes()
                if str(getattr(node, "texture", "") or "").strip().lower() not in ("", "null", "none")
            }
            tex_dir = Path(out_dir) / "textures"
            tex_dir.mkdir(exist_ok=True)
            for tex_name in tex_names:
                raw = mgr.get_texture(tex_name, game)
                if not raw:
                    continue
                ext = ".tpc" if _is_tpc_data(raw) else ".tga"
                dst = tex_dir / f"{tex_name}{ext}"
                if not dst.exists():
                    dst.write_bytes(raw)
                    written.append(str(dst))
        except Exception as exc:
            self._log(f"Texture extraction skipped for {resref}: {exc}", "warning")
        return written

    def _batch_library_export(self, fmt: str, rows: list):
        rows = [row for row in rows if row.get("resref") and row.get("game")]
        if not rows:
            QtWidgets.QMessageBox.information(self, "Batch Export", "No models visible. Apply a filter first.")
            return
        if self._batch_thread is not None and self._batch_thread.isRunning():
            self._log("A batch export is already running.", "warning")
            return
        labels = {"obj": "OBJ", "ascii": "ASCII MDL", "tga": "TGA textures"}
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(self, f"Export {len(rows)} models as {labels.get(fmt, fmt)}")
        if not out_dir:
            return
        k1_dir, k2_dir = self._configured_game_dirs()
        if not (k1_dir or k2_dir):
            QtWidgets.QMessageBox.information(self, "Batch Export", "Set a KotOR game directory first.")
            return
        worker = LibraryBatchExportWorker(rows, out_dir, fmt, k1_dir, k2_dir)
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_batch_progress)
        worker.finished.connect(self._on_batch_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_batch_worker", None))
        self._batch_thread = thread
        self._batch_worker = worker
        self.library_panel.set_status(f"Starting batch {fmt} export ({len(rows)} models)...")
        self._log(f"Batch {fmt}: {len(rows)} visible model(s) -> {out_dir}")
        thread.start()

    @QtCore.Slot(int, int, int, int)
    def _on_batch_progress(self, index: int, total: int, ok: int, fail: int):
        self.library_panel.set_status(f"Batch: {index}/{total}  ok={ok} fail={fail}")

    @QtCore.Slot(str, int, int, int, str, str)
    def _on_batch_finished(self, fmt: str, ok: int, fail: int, total: int, out_dir: str, error: str):
        if error:
            self._log(f"Batch {fmt} error:\n{error}", "error")
        self.library_panel.set_status(f"Batch done: ok={ok} fail={fail} total={total}")
        QtWidgets.QMessageBox.information(
            self,
            "Batch Export Complete",
            f"Format: {fmt.upper()}\nOutput: {out_dir}\nOK: {ok}   Failed: {fail}   Total: {total}",
        )
