"""Standalone retarget workbench, Unreal animator, sequence editor, and content-browser routing."""

from __future__ import annotations

import importlib
from pathlib import Path

try:
    from PySide6 import QtCore, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.core.retargeting.retarget_output_naming import KotorOutputAnimationNameMode
from src.gui.qt_lib.dialogs.qt_settings_dialog import save_settings
from src.gui.qt_lib.sequence_editor.sequence_editor_window import SequenceEditorWindow
from src.core.rendering.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE
from src.gui.qt_lib.windows.qt_retarget_preview_controller import QtRetargetViewportAdapter
from src.gui.qt_lib.windows.qt_retarget_workbench_controller import combo_current_retarget_mode


class RetargetWindowWorkflowMixin:
    """Standalone retarget workbench, Unreal animator, sequence editor, and content-browser routing."""

    def _ensure_animation_retarget_window(self):
        window = getattr(self, "animation_retarget_window", None)
        if window is not None:
            return window
        from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

        window = QtAnimationRetargetWindow(self)
        window.set_navigation_profile(
            self.settings_data.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
        )
        window.sourceCurrentRequested.connect(self._retarget_set_source_current)
        window.targetCurrentRequested.connect(self._retarget_set_target_current)
        window.sourceLibraryRequested.connect(lambda: self._retarget_select_library_model("source"))
        window.targetLibraryRequested.connect(lambda: self._retarget_select_library_model("target"))
        window.sourceGameLibraryRequested.connect(lambda row: self._send_library_row_to_retarget(row, "source"))
        window.targetGameLibraryRequested.connect(lambda row: self._send_library_row_to_retarget(row, "target"))
        window.sourceExternalImportRequested.connect(lambda: self._retarget_import_external_model("source"))
        window.targetExternalImportRequested.connect(lambda: self._retarget_import_external_model("target"))
        window.previewRequested.connect(self._retarget_workbench_preview_from_window)
        window.sourceAnimationPlayRequested.connect(self._retarget_workbench_play_source_animation_from_window)
        window.sourceAnimationTimeChanged.connect(self._retarget_workbench_sync_target_time_from_source)
        window.applyRequested.connect(self._retarget_workbench_apply_from_window)
        window.pauseRequested.connect(self._retarget_pause)
        window.stopRequested.connect(self._retarget_stop)
        self.animation_retarget_window = window
        self.animation_retarget_panel = window
        self._retarget_workbench_controls_connected = False
        self._connect_retarget_workbench_window_controls()
        return window

    def _ensure_unreal_animator_window(self):
        window = getattr(self, "unreal_animator_window", None)
        if window is not None:
            return window
        from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

        window = QtUnrealAnimatorWindow(self)
        window.set_navigation_profile(
            self.settings_data.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
        )
        window.sourceLoadRequested.connect(self._unreal_load_supermodel)
        window.reloadCodeRequested.connect(self._reload_unreal_animator_window)
        self.unreal_animator_window = window
        return window

    def _open_animation_retarget_window(self):
        window = self._ensure_animation_retarget_window()
        if window is None:
            self._not_migrated("Animation Retargeting Workbench")
            return
        try:
            self._ensure_retarget_workbench_target_viewport_adapter()
            window.set_texture_dir(self._texture_dir)
            window.set_navigation_profile(
                self.settings_data.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
            )
            window.set_library_rows(getattr(self, "_library_rows", []) or [])
            if self._retarget_source_model is not None:
                window.set_source_model(self._retarget_source_model)
            if self._retarget_target_model is not None:
                window.set_target_model(self._retarget_target_model)
        except Exception:
            pass
        window.show()
        window.raise_()
        window.activateWindow()
    def _ensure_retarget_workbench_target_viewport_adapter(self):
        window = getattr(self, "animation_retarget_window", None)
        if window is None or not hasattr(window, "target_viewport"):
            return getattr(self, "_retarget_preview_viewport", None)
        adapter = getattr(window, "_retarget_target_viewport_adapter", None)
        if adapter is None or getattr(adapter, "viewport", None) is not window.target_viewport:
            adapter = QtRetargetViewportAdapter(window.target_viewport, parent=window)
            window._retarget_target_viewport_adapter = adapter
        preview_controller = getattr(self, "retarget_preview_controller", None)
        if preview_controller is not None:
            preview_controller.viewport = adapter
        workbench_controller = getattr(self, "retarget_workbench_controller", None)
        if workbench_controller is not None:
            workbench_controller.viewport = adapter
        return adapter
    def _sync_retarget_preview_target(self) -> None:
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is None:
            return
        controller.set_target_model(self._retarget_target_model or self._current_model)
        self._refresh_target_kotor_animation_slots()
        self._apply_retarget_workbench_mode_status()
    def _connect_retarget_workbench_window_controls(self) -> None:
        window = getattr(self, "animation_retarget_window", None)
        if window is None or getattr(self, "_retarget_workbench_controls_connected", False):
            return
        window.retarget_mode_combo.currentIndexChanged.connect(self._on_retarget_mode_changed)
        window.kotor_output_name_mode_combo.currentIndexChanged.connect(self._on_kotor_output_name_mode_changed)
        window.target_kotor_animation_slot_combo.currentTextChanged.connect(self._on_target_kotor_animation_slot_changed)
        window.custom_kotor_animation_name_edit.textChanged.connect(self._on_custom_kotor_animation_name_changed)
        window.output_unreal_clip_name_edit.textChanged.connect(self._on_output_unreal_clip_name_changed)
        window.retarget_output_display_label_edit.textChanged.connect(self._on_retarget_output_display_label_changed)
        window.rootMotionToggled.connect(self._on_retarget_root_motion_toggled)
        self._retarget_workbench_controls_connected = True
    def _retarget_workbench_widget(self, name: str):
        window = getattr(self, "animation_retarget_window", None)
        if window is not None and hasattr(window, name):
            return getattr(window, name)
        return getattr(self, name, None)
    def _on_retarget_mode_changed(self, _index: int = -1) -> None:
        combo = self._retarget_workbench_widget("retarget_mode_combo")
        controller = getattr(self, "retarget_workbench_controller", None)
        if combo is None or controller is None:
            return
        try:
            controller.set_mode(combo_current_retarget_mode(combo))
            self._apply_retarget_workbench_mode_status()
        except Exception as exc:
            self._log(f"Retarget mode change failed: {exc}", "error")
            self.statusBar().showMessage("Retarget mode change failed")
    def _apply_retarget_workbench_mode_status(self) -> None:
        controller = getattr(self, "retarget_workbench_controller", None)
        combo = self._retarget_workbench_widget("retarget_mode_combo")
        if controller is None:
            return
        spec = controller.current_mode_spec()
        if combo is not None:
            combo.setToolTip(controller.mode_status_text())
        readiness = controller.readiness()
        status_label = self._retarget_workbench_widget("retarget_workbench_status_label")
        inputs_label = self._retarget_workbench_widget("retarget_workbench_inputs_label")
        output_label = self._retarget_workbench_widget("retarget_workbench_output_label")
        runtime_label = self._retarget_workbench_widget("retarget_workbench_runtime_label")
        if status_label is not None:
            status_label.setText(
                f"Mode: {readiness.mode_label} | Preview: {readiness.preview_status} | Export: {readiness.export_status}"
            )
            status_label.setToolTip("\n".join(readiness.blocking_messages or readiness.warnings))
        if inputs_label is not None:
            inputs_label.setText(f"Source: {readiness.source_summary} | Target: {readiness.target_summary}")
        if output_label is not None:
            output_label.setText(f"Output: {readiness.output_summary}")
        if runtime_label is not None:
            runtime_label.setText(f"Runtime: {readiness.runtime_summary}")
        self._apply_retarget_output_naming_controls()
        self._sync_retarget_workbench_profile_mapping()
        self.statusBar().showMessage(f"Retarget mode: {spec.label}")
    def _sync_retarget_workbench_profile_mapping(self) -> None:
        window = getattr(self, "animation_retarget_window", None)
        controller = getattr(self, "retarget_workbench_controller", None)
        if window is None or controller is None or not hasattr(window, "set_mapping_report"):
            return
        if getattr(controller.state.mode, "name", "") == "KOTOR_TO_UNREAL":
            return
        profile = getattr(controller.state, "retarget_profile", None)
        target_model = controller.current_target_model()
        if profile is None or target_model is None:
            return
        entries = list(getattr(profile, "mappings", []) or [])
        mapping = {
            str(getattr(entry, "source_node", "") or ""): str(getattr(entry, "target_node", "") or "")
            for entry in entries
            if str(getattr(entry, "source_node", "") or "").strip()
            and str(getattr(entry, "target_node", "") or "").strip()
        }
        window.set_mapping_report(
            SimpleNamespace(
                mapping=mapping,
                missing_source=[],
                missing_target=[],
                matched_count=len(mapping),
                exact_matches=0,
                alias_matches=len(mapping),
                manual_matches=0,
            )
        )
    def _apply_retarget_output_naming_controls(self) -> None:
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is None:
            return
        is_kotor_output = controller.state.mode.name in {"UNREAL_TO_KOTOR", "KOTOR_TO_KOTOR"}
        mode_combo = self._retarget_workbench_widget("kotor_output_name_mode_combo")
        slot_combo = self._retarget_workbench_widget("target_kotor_animation_slot_combo")
        custom_edit = self._retarget_workbench_widget("custom_kotor_animation_name_edit")
        unreal_clip_edit = self._retarget_workbench_widget("output_unreal_clip_name_edit")
        label_edit = self._retarget_workbench_widget("retarget_output_display_label_edit")
        mode_label = self._retarget_workbench_widget("kotor_output_name_mode_label")
        slot_label = self._retarget_workbench_widget("target_kotor_animation_slot_label")
        custom_label = self._retarget_workbench_widget("custom_kotor_animation_name_label")
        unreal_clip_label = self._retarget_workbench_widget("output_unreal_clip_name_label")
        notes_label = self._retarget_workbench_widget("retarget_output_display_label")
        selected = KotorOutputAnimationNameMode.VANILLA_SLOT.value
        if mode_combo is not None:
            data = mode_combo.currentData()
            selected = str(data or selected)
            mode_combo.setVisible(True)
            mode_combo.setEnabled(is_kotor_output)
        if mode_label is not None:
            mode_label.setEnabled(is_kotor_output)
        custom = selected == KotorOutputAnimationNameMode.CUSTOM_PATCH.value
        if slot_combo is not None:
            slot_combo.setVisible(True)
            slot_combo.setEnabled(is_kotor_output and not custom)
        if slot_label is not None:
            slot_label.setEnabled(is_kotor_output and not custom)
        if custom_edit is not None:
            custom_edit.setVisible(True)
            custom_edit.setEnabled(is_kotor_output and custom)
        if custom_label is not None:
            custom_label.setEnabled(is_kotor_output and custom)
        if unreal_clip_edit is not None:
            unreal_clip_edit.setVisible(True)
            unreal_clip_edit.setEnabled(not is_kotor_output)
        if unreal_clip_label is not None:
            unreal_clip_label.setEnabled(not is_kotor_output)
        if label_edit is not None:
            label_edit.setVisible(True)
            label_edit.setEnabled(True)
        if notes_label is not None:
            notes_label.setEnabled(True)
    def _refresh_target_kotor_animation_slots(self) -> None:
        controller = getattr(self, "retarget_workbench_controller", None)
        combo = self._retarget_workbench_widget("target_kotor_animation_slot_combo")
        if controller is None or combo is None:
            return
        current = combo.currentText()
        slots = controller.available_target_kotor_slots()
        combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItems(slots)
            if current:
                combo.setCurrentText(current)
            elif slots:
                combo.setCurrentIndex(0)
        finally:
            combo.blockSignals(False)
        selected = combo.currentText().strip()
        naming = getattr(controller.state, "output_naming", None)
        is_custom_output = (
            getattr(naming, "kotor_name_mode", None) == KotorOutputAnimationNameMode.CUSTOM_PATCH
        )
        is_kotor_output = getattr(controller.state.mode, "name", "") in {"UNREAL_TO_KOTOR", "KOTOR_TO_KOTOR"}
        if selected and is_kotor_output and not is_custom_output:
            controller.set_target_kotor_animation_slot(selected)
    def _on_kotor_output_name_mode_changed(self, _index: int = -1) -> None:
        controller = getattr(self, "retarget_workbench_controller", None)
        combo = self._retarget_workbench_widget("kotor_output_name_mode_combo")
        if controller is None or combo is None:
            return
        try:
            controller.set_kotor_output_name_mode(combo.currentData())
            self._apply_retarget_output_naming_controls()
            self._apply_retarget_workbench_mode_status()
        except Exception as exc:
            self._log(f"Retarget output name mode change failed: {exc}", "error")
    def _on_target_kotor_animation_slot_changed(self, text: str) -> None:
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is None:
            return
        controller.set_target_kotor_animation_slot(text)
        self._apply_retarget_workbench_mode_status()
    def _on_custom_kotor_animation_name_changed(self, text: str) -> None:
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is None:
            return
        controller.set_custom_kotor_animation_name(text)
        self._apply_retarget_workbench_mode_status()
    def _on_output_unreal_clip_name_changed(self, text: str) -> None:
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is None:
            return
        controller.set_output_unreal_clip_name(text)
        self._apply_retarget_workbench_mode_status()
    def _on_retarget_output_display_label_changed(self, text: str) -> None:
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is None:
            return
        controller.set_output_display_label(text)
        self._apply_retarget_workbench_mode_status()
    def _on_retarget_root_motion_toggled(self, enabled: bool) -> None:
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is None:
            return
        controller.set_root_motion_enabled(enabled)
        self._apply_retarget_workbench_mode_status()
    def _load_retarget_source_clip(self):
        path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load UE/FBX Source Animation",
            str(Path(self._model_path).parent if self._model_path else self.app_root),
            "FBX animation files (*.fbx);;All files (*.*)",
        )
        if not path:
            return
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is None:
            self._not_migrated("Preview Retarget")
            return
        try:
            clip = controller.load_source_clip(path)
            self._apply_retarget_workbench_mode_status()
            self.statusBar().showMessage(f"Loaded source clip: {getattr(clip, 'clip_name', Path(path).stem)}")
        except Exception as exc:
            self._log(f"UE/FBX source import failed: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Load UE/FBX Source Animation", str(exc))
    def _load_retarget_profile(self):
        path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Retarget Profile",
            str(self.app_root),
            "Retarget profile JSON (*.json);;All files (*.*)",
        )
        if not path:
            return
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is None:
            self._not_migrated("Preview Retarget")
            return
        try:
            profile = controller.load_retarget_profile(path)
            slot = str(getattr(profile, "animation_slot", "") or "(no slot)")
            slot_combo = self._retarget_workbench_widget("target_kotor_animation_slot_combo")
            if slot_combo is not None and slot != "(no slot)":
                slot_combo.setCurrentText(slot)
            self._apply_retarget_workbench_mode_status()
            self.statusBar().showMessage(f"Loaded retarget profile: {getattr(profile, 'name', Path(path).stem)} [{slot}]")
        except Exception as exc:
            self._log(f"Retarget profile load failed: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Load Retarget Profile", str(exc))
    def _preview_retarget_animation(self):
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is None:
            self._not_migrated("Preview Retarget")
            return
        try:
            window = getattr(self, "animation_retarget_window", None)
            show_nodes = True
            if window is not None and hasattr(window, "retarget_bones_visible"):
                show_nodes = bool(window.retarget_bones_visible())
            preview = controller.preview(auto_play=True, show_node_overlay=show_nodes)
            self._apply_retarget_workbench_mode_status()
            if preview is None and getattr(controller, "last_error", ""):
                self.statusBar().showMessage("Retarget preview failed")
        except Exception as exc:
            self._log(str(exc), "warning")
            self.statusBar().showMessage("Retarget preview unavailable in this mode")
    def _export_retarget_preview(self):
        controller = getattr(self, "retarget_workbench_controller", None)
        if controller is None:
            self._not_migrated("Export Retarget Preview")
            return
        is_kotor_to_unreal = getattr(controller.state.mode, "name", "") == "KOTOR_TO_UNREAL"
        if not controller.can_export():
            message = (
                "No successful current retarget preview is available to export. "
                "Run Preview Retarget before exporting."
            )
            if is_kotor_to_unreal and getattr(controller.state, "last_kotor_to_unreal_preview_result", None) is not None:
                readiness = controller.readiness()
                message = readiness.export_status or (
                    "No FBX export backend is configured. Configure the project-supported "
                    "FBX backend before exporting."
                )
            elif getattr(controller.state, "last_preview_result", None) is not None:
                message = (
                    "The retarget preview is stale because the source clip, target model, "
                    "or retarget profile changed. Run Preview Retarget again before exporting."
                )
            self._log(message, "warning")
            QtWidgets.QMessageBox.information(self, "Export Retarget Preview", message)
            return

        target = controller.state.target_unreal_skeleton if is_kotor_to_unreal else controller.current_target_model()
        naming = getattr(controller.state, "output_naming", None)
        stem = str(
            (getattr(naming, "unreal_clip_name", "") if is_kotor_to_unreal else "")
            or getattr(target, "name", "")
            or ""
        ).strip() or "retarget_preview"
        default_dir = self.app_root / "exports" / "retarget_previews"
        default_path = default_dir / f"{stem}.{'fbx' if is_kotor_to_unreal else 'mdl'}"
        path, _selected = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export UE FBX Animation" if is_kotor_to_unreal else "Export Retarget Preview",
            str(default_path),
            "FBX animation files (*.fbx);;All files (*.*)" if is_kotor_to_unreal else "KOTOR MDL files (*.mdl);;All files (*.*)",
        )
        if not path:
            return
        output_path = Path(path)
        if is_kotor_to_unreal:
            if output_path.suffix.lower() != ".fbx":
                output_path = output_path.with_suffix(".fbx")
            paired_paths = (output_path, output_path.with_suffix(".ghostrigger.json"))
        else:
            if output_path.suffix.lower() != ".mdl":
                output_path = output_path.with_suffix(".mdl")
            paired_paths = (output_path, output_path.with_suffix(".mdx"))
        overwrite = False
        existing = [p for p in paired_paths if p.exists()]
        if existing:
            names = "\n".join(str(p) for p in existing)
            answer = QtWidgets.QMessageBox.question(
                self,
                "Overwrite Retarget Preview Export?",
                f"The following output file(s) already exist:\n{names}\n\nOverwrite them?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if answer != QtWidgets.QMessageBox.Yes:
                return
            overwrite = True

        result = controller.export_preview(output_path, overwrite=overwrite)
        self._apply_retarget_workbench_mode_status()
        if result is None:
            detail = getattr(controller, "last_error", "") or "Export failed."
            QtWidgets.QMessageBox.critical(self, "Export Retarget Preview", detail)
            return
        if is_kotor_to_unreal:
            final_paths = [str(path) for path in getattr(result, "final_paths", [])]
            self.statusBar().showMessage(
                "KOTOR → Unreal FBX exported: " + (", ".join(final_paths) if final_paths else str(output_path))
            )
        else:
            self.statusBar().showMessage(f"Retarget preview exported: {result.mdl_path}")
    def _open_unreal_animator_window(self):
        window = self._ensure_unreal_animator_window()
        if window is None:
            self._not_migrated("Unreal Animator")
            return
        self._unreal_refresh_supermodel_library()
        window.set_navigation_profile(
            self.settings_data.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
        )
        window.show()
        window.raise_()
        window.activateWindow()
    def _open_sequence_editor_window(self):
        window = getattr(self, "sequence_editor_window", None)
        if window is None:
            window = SequenceEditorWindow(self, getattr(self, "viewport", None), self.app_root, self, docked=False)
            self.sequence_editor_window = window
        else:
            try:
                window.source_viewport = getattr(self, "viewport", None)
                window.viewport_panel.source_viewport = window.source_viewport
                window.set_docked_preview(False, window.source_viewport)
            except Exception:
                pass
        window.set_renderer_settings(self._effective_renderer_settings())
        window.show()
        window.raise_()
        window.activateWindow()
    def _ensure_sequence_editor_dock(self):
        dock = getattr(self, "sequence_editor_dock", None)
        editor = getattr(self, "sequence_editor_docked_window", None)
        if dock is not None and editor is not None:
            return dock, editor
        editor = SequenceEditorWindow(
            self,
            getattr(self, "viewport", None),
            self.app_root,
            self,
            docked=True,
        )
        editor.setWindowFlags(QtCore.Qt.Widget)
        editor.menuBar().setVisible(False)
        dock = self._create_detachable_panel(
            "sequence_editor",
            "Sequence Editor",
            editor,
            QtCore.Qt.BottomDockWidgetArea,
            scroll=True,
        )
        self.sequence_editor_docked_window = editor
        self.sequence_editor_dock = dock
        return dock, editor
    def _show_sequence_editor_dock(self):
        dock, editor = self._ensure_sequence_editor_dock()
        if dock is None or editor is None:
            self._not_migrated("Sequence Editor")
            return
        editor.set_docked_preview(True, getattr(self, "viewport", None))
        self._show_workspace_dock("sequence_editor")
    def _reload_unreal_animator_window(self) -> None:
        old_window = getattr(self, "unreal_animator_window", None)
        visible = bool(old_window is not None and old_window.isVisible())
        geometry = old_window.saveGeometry() if old_window is not None else None
        source_row = dict(getattr(self, "_unreal_source_row", {}) or {})
        source_model = getattr(old_window, "_source_model", None) if old_window is not None else None
        source_game = str(getattr(old_window, "_source_game", "") or getattr(self, "_unreal_source_game", "") or "")

        try:
            import src.unreal.animation_retargeting as unreal_retargeting
            import src.unreal.quinn as unreal_quinn
            import src.gui.qt_lib.viewports.qt_viewport as qt_viewport
            import src.gui.qt_lib.windows.qt_unreal_animator as qt_unreal_animator

            importlib.reload(unreal_retargeting)
            importlib.reload(unreal_quinn)
            importlib.reload(qt_viewport)
            qt_unreal_animator = importlib.reload(qt_unreal_animator)
            QtUnrealAnimatorWindow = qt_unreal_animator.QtUnrealAnimatorWindow
        except Exception as exc:
            self._log(f"Unreal Animator reload failed: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Reload Unreal Animator", str(exc))
            return

        if old_window is not None:
            try:
                old_window.stop_preview()
            except Exception:
                pass
            old_window.hide()
            old_window.setParent(None)
            old_window.deleteLater()

        window = QtUnrealAnimatorWindow(self)
        window.set_navigation_profile(
            self.settings_data.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
        )
        window.sourceLoadRequested.connect(self._unreal_load_supermodel)
        window.reloadCodeRequested.connect(self._reload_unreal_animator_window)
        self.unreal_animator_window = window
        self._unreal_refresh_supermodel_library()

        if source_row:
            self._unreal_load_supermodel(source_row)
        elif source_model is not None:
            window.set_source_model(source_model, source_game)
            self._unreal_source_game = source_game

        if geometry is not None:
            window.restoreGeometry(geometry)
        if visible:
            window.show()
            window.raise_()
            window.activateWindow()
        self._log("Unreal Animator code reloaded.", "success")
        self.statusBar().showMessage("Unreal Animator code reloaded")
    def _unreal_refresh_supermodel_library(self) -> None:
        window = getattr(self, "unreal_animator_window", None)
        if window is None:
            return
        rows = []
        for row in getattr(self, "_library_rows", []) or []:
            resref = str(row.get("resref", "") or "").lower()
            if not resref.startswith("s_"):
                continue
            item = dict(row)
            try:
                item.setdefault("animations", "")
                item.setdefault("nodes", "")
            except Exception:
                pass
            rows.append(item)
        window.set_supermodel_library(rows)
    def _unreal_load_supermodel(self, row: dict) -> None:
        model, game = self._load_resource_model_for_retarget(row)
        if model is None:
            return
        window = getattr(self, "unreal_animator_window", None)
        if window is None:
            return
        self._unreal_source_row = dict(row)
        self._unreal_source_game = game
        window.set_source_model(model, game)
        self._log(f"Unreal source <- {game}:{row.get('resref', '')}", "success")
    def _show_right_tab(self, label: str):
        needle = label.lower()
        aliases = {
            "animations": "animations",
            "animation library": "animations",
            "properties": "properties",
        }
        key = aliases.get(needle)
        if key:
            self._show_workspace_dock(key)
        else:
            self._not_migrated(label)
    def _show_content_browser(self, asset_type: str = "All"):
        panel = getattr(self, "content_browser_panel", None)
        if panel is None:
            self._not_migrated("Content Browser")
            return
        self._show_workspace_dock("content_browser")
        if hasattr(panel, "select_asset_type"):
            panel.select_asset_type(asset_type)
    def _get_model(self):
        return self._current_model
    def _load_resource_model_for_retarget(self, row: dict):
        resref = str(row.get("resref", "") or "").strip()
        game = str(row.get("game", "") or self._current_game or "K1").upper()
        if not resref:
            return None, game
        mgr = self._get_resource_manager()
        if mgr is None:
            QtWidgets.QMessageBox.information(
                self,
                "Retarget Workbench",
                "Set the K1/K2 game directories before sending library models to retargeting.",
            )
            return None, game
        try:
            model = mgr.load_model(resref, game)
        except Exception as exc:
            self._log(f"Retarget load failed for {game}:{resref}: {exc}", "error")
            model = None
        if model is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Retarget Workbench",
                f"Could not load {game}:{resref}.",
            )
        return model, game
    def _send_library_row_to_retarget(self, row: dict, role: str) -> None:
        model, game = self._load_resource_model_for_retarget(row)
        if model is None:
            return
        window = self._ensure_animation_retarget_window()
        if window is None:
            return
        window.set_texture_dir(self._texture_dir)
        mgr = self._get_resource_manager()
        if role == "source":
            self._retarget_source_model = model
            self._retarget_engine = None
            if mgr is not None:
                window.set_source_resource_context(mgr, game)
            window.set_source_model(model, game)
            self._log(f"Retarget source <- {game}:{row.get('resref', '')}", "success")
        else:
            self._retarget_target_model = model
            self._retarget_engine = None
            self._retarget_mapping_report = None
            if mgr is not None:
                window.set_target_resource_context(mgr, game)
            window.set_target_model(model, game)
            self._log(f"Retarget target <- {game}:{row.get('resref', '')}", "success")
            if hasattr(self, "retarget_preview_controller"):
                self._sync_retarget_preview_target()
        self._retarget_refresh_mapping()
        self._open_animation_retarget_window()
    def _retarget_select_library_model(self, role: str) -> None:
        panel = getattr(self, "library_panel", None)
        row = panel.selected_row() if panel is not None else None
        if not row:
            self._show_content_browser("Model")
            QtWidgets.QMessageBox.information(
                self,
                "Retarget Workbench",
                "Select a model in the Game Library first.",
            )
            return
        self._send_library_row_to_retarget(row, role)
    def _retarget_import_external_model(self, role: str) -> None:
        title = "Import External Retarget Source" if role == "source" else "Import External Retarget Target"
        path, _selected = QtWidgets.QFileDialog.getOpenFileName(
            self,
            title,
            str(Path(self.settings_data.get("last_import") or self.app_root)),
            "External models (*.fbx *.obj *.glb *.gltf);;FBX files (*.fbx);;OBJ files (*.obj);;GLB/GLTF files (*.glb *.gltf);;All files (*.*)",
        )
        if not path:
            return
        texture_dir = str(Path(path).resolve().parent)
        window = getattr(self, "animation_retarget_window", None)
        controller = getattr(self, "retarget_workbench_controller", None)
        mode_value = getattr(getattr(controller, "state", None), "mode", None)
        mode_name = str(getattr(mode_value, "name", mode_value) or "")
        suffix = Path(path).suffix.lower()

        if role == "source" and suffix == ".fbx" and controller is not None and mode_name == "UNREAL_TO_KOTOR":
            try:
                clip = controller.load_source_clip(path)
            except Exception as exc:
                self._log(f"UE/FBX source clip import failed: {exc}", "error")
                QtWidgets.QMessageBox.critical(self, title, str(exc))
                return
            mesh_model = None
            try:
                from src.converters.blender_fbx_mesh_importer import import_fbx_mesh_with_blender

                mesh_model = import_fbx_mesh_with_blender(str(path), game_version=self._game_version())
                try:
                    from src.core.retargeting.mixamo_companion_mesh import is_mixamo_companion_mesh_filename

                    if is_mixamo_companion_mesh_filename(path):
                        self.settings_data["mixamo_companion_mesh_path"] = str(Path(path).resolve())
                        save_settings(self.settings_path, self.settings_data)
                        self._log(f"Stored Mixamo companion mesh reference: {Path(path).name}", "info")
                except Exception as store_exc:
                    self._log(f"Could not store Mixamo companion mesh reference: {store_exc}", "warning")
            except Exception as exc:
                self._log(f"UE/FBX source mesh preview unavailable: {exc}", "warning")
                try:
                    from src.core.retargeting.mixamo_companion_mesh import find_mixamo_companion_mesh_path
                    from src.converters.blender_fbx_mesh_importer import import_fbx_mesh_with_blender

                    companion = find_mixamo_companion_mesh_path(
                        path,
                        [getattr(node, "name", "") for node in (getattr(clip, "nodes", []) or [])],
                        configured_mesh_path=self.settings_data.get("mixamo_companion_mesh_path"),
                    )
                    if companion is not None:
                        mesh_model = import_fbx_mesh_with_blender(str(companion), game_version=self._game_version())
                        self.settings_data["mixamo_companion_mesh_path"] = str(Path(companion).resolve())
                        save_settings(self.settings_path, self.settings_data)
                        self._log(
                            f"Using Mixamo companion source mesh preview <- {companion.name}",
                            "info",
                        )
                except Exception as companion_exc:
                    self._log(
                        f"Mixamo companion source mesh preview unavailable: {companion_exc}",
                        "warning",
                    )
            self._texture_dir = texture_dir
            if window is not None:
                window.set_texture_dir(texture_dir)
                if hasattr(window, "set_source_clip_preview"):
                    window.set_source_clip_preview(clip, mesh_model=mesh_model)
                else:
                    panel = getattr(window, "panel", None)
                    label = getattr(panel, "source_label", None)
                    if label is not None:
                        label.setText(f"UE/FBX clip: {Path(path).name}")
            self._retarget_source_model = None
            self._apply_retarget_workbench_mode_status()
            self._log(f"Retarget source UE/FBX clip <- {Path(path).name}", "success")
            self._open_animation_retarget_window()
            return

        if role == "target" and suffix == ".fbx" and controller is not None and mode_name == "KOTOR_TO_UNREAL":
            try:
                from src.core.retargeting.unreal_target_skeleton import import_unreal_target_skeleton_from_fbx

                controller.set_target_unreal_skeleton(import_unreal_target_skeleton_from_fbx(path))
            except Exception as exc:
                self._log(f"Unreal target skeleton import failed: {exc}", "error")
                QtWidgets.QMessageBox.critical(self, title, str(exc))
                return
            self._texture_dir = texture_dir
            if window is not None:
                window.set_texture_dir(texture_dir)
                panel = getattr(window, "panel", None)
                label = getattr(panel, "target_label", None)
                if label is not None:
                    label.setText(f"Unreal skeleton: {Path(path).name}")
            self._apply_retarget_workbench_mode_status()
            self._log(f"Retarget target Unreal skeleton <- {Path(path).name}", "success")
            self._open_animation_retarget_window()
            return

        try:
            model = self._load_external_retarget_model(path)
        except Exception as exc:
            self._log(f"External retarget import failed: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, title, str(exc))
            return

        self._texture_dir = texture_dir
        if window is None:
            return
        window.set_texture_dir(texture_dir)

        if role == "source":
            self._retarget_source_model = model
            self._retarget_engine = None
            window.set_source_model(model, "")
            if controller is not None and mode_name in {"KOTOR_TO_KOTOR", "KOTOR_TO_UNREAL"}:
                controller.set_source_kotor_model(model)
                self._apply_retarget_workbench_mode_status()
            self._log(f"Retarget source external import <- {Path(path).name}", "success")
        else:
            self._retarget_target_model = model
            self._retarget_engine = None
            self._retarget_mapping_report = None
            window.set_target_model(model, "")
            if controller is not None:
                controller.set_target_model(model)
            self._sync_retarget_preview_target()
            self._log(f"Retarget target external import <- {Path(path).name}", "success")
        self._retarget_refresh_mapping()
        self._open_animation_retarget_window()
    def _load_external_retarget_model(self, path: str):
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        if suffix == ".obj":
            from src.converters.mesh_converter import OBJImporter

            return OBJImporter().import_file(str(file_path), game_version=self._game_version())
        if suffix == ".fbx":
            from src.converters.mesh_converter import FBXImporter

            model = FBXImporter().import_file(str(file_path), game_version=self._game_version())
            if model is None:
                raise RuntimeError("FBX import failed. Install pyassimp, assimp-py, or trimesh.")
            return model
        if suffix in {".glb", ".gltf"}:
            from src.converters.mesh_converter import GLTFImporter

            model = GLTFImporter().import_file(str(file_path), game_version=self._game_version())
            if model is None:
                raise RuntimeError("GLTF import failed. Install pygltflib or trimesh.")
            return model
        raise RuntimeError("Choose an external FBX, OBJ, GLB, or GLTF model file.")
