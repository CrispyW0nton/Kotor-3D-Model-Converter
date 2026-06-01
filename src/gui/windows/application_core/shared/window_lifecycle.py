"""Settings, theme editor, restart, measurement, close, and GUI log-handler behavior."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.libtheme.theme_editor_window import ThemeEditorWindow
from src.gui.libtheme.theme_settings import ThemeLayoutSettings
from src.gui.qt_lib.dialogs.qt_settings_dialog import QtSettingsDialog, save_settings
from src.gui.qt_lib.panels.qt_character_builder_panel import QtCharacterBuilderWindow
from src.gui.qt_lib.panels.qt_log_panel import QtLogPanelHandler
from src.core.rendering.renderer_backend import renderer_backend_label
from src.core.rendering.renderer_settings import RendererSettings
from src.core.rendering.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE, normalize_viewport_navigation_profile
from src.gui.windows.application_core.application_core_lib.functions.qt_helpers import _wgpu_backend_restart_required
from src.measurement.unit_settings import MeasurementSettings

log = logging.getLogger(__name__)


class WindowLifecycleMixin:
    """Settings, theme editor, restart, measurement, close, and GUI log-handler behavior."""

    def _open_qt_character_builder_window(self):
        """Open (or raise) the M2 AccuRig-style Character Builder window.

        Entry points (all wired here per M2/T206):
          * Tools → Character Builder (New Window)…
          * Main toolbar Character Builder button
          * Keyboard shortcut Ctrl+B

        The window is created lazily on first access and reused for the
        rest of the session — closing it merely hides it so QSettings
        (T207) persists window/dock state between opens.
        """
        if self._character_builder_window is None:
            self._character_builder_window = QtCharacterBuilderWindow(self)
        self._character_builder_window.set_renderer_settings(RendererSettings.from_settings(self.settings_data))
        self._character_builder_window.show()
        self._character_builder_window.raise_()
        self._character_builder_window.activateWindow()
    def _send_library_row_to_character_builder(self, row: dict) -> None:
        self._open_qt_character_builder_window()
        resref = str(row.get("resref") or "asset")
        game = str(row.get("game") or "")
        self._log(f"Character Builder <- {game}:{resref}", "success")
    def _open_settings_dialog(self):
        dialog = getattr(self, "_settings_dialog", None)
        if dialog is None:
            dialog = QtSettingsDialog(
                self.settings_data,
                self,
                theme_manager=self.theme_manager,
                layout_manager=self.layout_manager,
                hardware_diagnostics=self._preloaded_hardware_diagnostics,
                renderer_capabilities=self._preloaded_renderer_capabilities,
            )
            dialog.setModal(False)
            dialog.setWindowModality(QtCore.Qt.NonModal)
            dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
            dialog.destroyed.connect(lambda _obj=None: setattr(self, "_settings_dialog", None))
            dialog.settingsSaved.connect(self._save_settings_data)
            dialog.autoDetectRequested.connect(self._auto_detect_dirs)
            self._settings_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
    def _open_theme_editor_window(self):
        editor = getattr(self, "_theme_editor_window", None)
        if editor is None:
            editor = ThemeEditorWindow(
                self.theme_manager,
                self.layout_manager,
                self,
                matrix_bar_settings=self._matrix_bar_settings(self.theme_manager.get_theme()),
                matrix_background_enabled=bool(self.settings_data.get("matrix_background", True)),
            )
            editor.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
            editor.destroyed.connect(lambda _obj=None: setattr(self, "_theme_editor_window", None))
            editor.themeApplied.connect(self._persist_theme_layout_settings)
            self._theme_editor_window = editor
        editor.show()
        editor.raise_()
        editor.activateWindow()
    def _persist_theme_layout_settings(self, *_args) -> None:
        self._sync_theme_layout_settings()
        try:
            save_settings(self.settings_path, self.settings_data)
            self._log("Theme/layout settings saved.", "success")
        except Exception as exc:
            self._log(f"Theme/layout settings save failed: {exc}", "error")
    def _save_settings_data(self, values: dict):
        values = dict(values or {})
        restart_after_save = bool(values.pop("__restart_after_save", False))
        old_dirs = (
            self.k1_dir_edit.text().strip() if hasattr(self, "k1_dir_edit") else "",
            self.k2_dir_edit.text().strip() if hasattr(self, "k2_dir_edit") else "",
        )
        old_renderer_settings = RendererSettings.from_settings(self.settings_data)
        new_renderer_settings = RendererSettings.from_settings(values)
        renderer_restart_required = _wgpu_backend_restart_required(
            old_renderer_settings,
            new_renderer_settings,
        )
        self.settings_data = values
        self.theme_manager.settings = ThemeLayoutSettings.from_settings(values)
        self.layout_manager.settings = ThemeLayoutSettings.from_settings(values)
        self._button_mode_override = self.layout_manager.settings.button_mode_override
        self._icon_size_override = self.layout_manager.settings.icon_size_override
        self.theme_manager.reload()
        self.layout_manager.reload()
        self.theme_manager.apply_current_theme(self)
        self._apply_matrix_theme(self.theme_manager.get_theme())
        self.layout_manager.apply_current_layout(self)
        self._configure_theme_watcher()
        viewport = getattr(self, "viewport", None)
        if viewport is not None and not renderer_restart_required:
            viewport.set_renderer_settings(new_renderer_settings)
            viewport.set_navigation_profile(
                normalize_viewport_navigation_profile(
                    values.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
                )
            )
        elif viewport is not None:
            viewport.set_navigation_profile(
                normalize_viewport_navigation_profile(
                    values.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
                )
            )
        retarget_window = getattr(self, "animation_retarget_window", None)
        if retarget_window is not None:
            set_renderer_settings = getattr(retarget_window, "set_renderer_settings", None)
            if callable(set_renderer_settings) and not renderer_restart_required:
                set_renderer_settings(new_renderer_settings)
            retarget_window.set_navigation_profile(
                normalize_viewport_navigation_profile(
                    values.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
                )
            )
        unreal_window = getattr(self, "unreal_animator_window", None)
        if unreal_window is not None:
            set_renderer_settings = getattr(unreal_window, "set_renderer_settings", None)
            if callable(set_renderer_settings) and not renderer_restart_required:
                set_renderer_settings(new_renderer_settings)
            unreal_window.set_navigation_profile(
                normalize_viewport_navigation_profile(
                    values.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
                )
            )
        module_editor_window = getattr(self, "module_editor_window", None)
        if module_editor_window is not None:
            set_renderer_settings = getattr(module_editor_window, "set_renderer_settings", None)
            if callable(set_renderer_settings) and not renderer_restart_required:
                set_renderer_settings(new_renderer_settings)
            module_editor_window.set_navigation_profile(
                normalize_viewport_navigation_profile(
                    values.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
                )
            )
        character_builder_window = getattr(self, "_character_builder_window", None)
        if character_builder_window is not None:
            set_renderer_settings = getattr(character_builder_window, "set_renderer_settings", None)
            if callable(set_renderer_settings) and not renderer_restart_required:
                set_renderer_settings(new_renderer_settings)
        for sequence_window in (
            getattr(self, "sequence_editor_window", None),
            getattr(self, "sequence_editor_docked_window", None),
        ):
            if sequence_window is not None:
                set_renderer_settings = getattr(sequence_window, "set_renderer_settings", None)
                if callable(set_renderer_settings) and not renderer_restart_required:
                    set_renderer_settings(new_renderer_settings)
        if renderer_restart_required:
            old_label = renderer_backend_label(old_renderer_settings.backend)
            new_label = renderer_backend_label(new_renderer_settings.backend)
            self._log(
                f"Renderer change saved for next launch: {old_label} -> {new_label}. Restart required for WGPU_BACKEND_TYPE.",
                "warning",
            )
        new_dirs = (str(values.get("k1_dir") or "").strip(), str(values.get("k2_dir") or "").strip())
        if hasattr(self, "k1_dir_edit"):
            self.k1_dir_edit.setText(new_dirs[0])
            self.k2_dir_edit.setText(new_dirs[1])
        texture_dir = str(values.get("texture_dir") or "").strip()
        if texture_dir:
            self._texture_dir = texture_dir
        if new_dirs != old_dirs:
            self._resource_manager = None
            self._resource_manager_dirs = ("", "")
            if hasattr(self, "library_panel"):
                self.library_panel.set_status("Game directories updated")
            self._log("Game directories updated. Run Scan to refresh the library.", "success")
        self._apply_measurement_settings()
        try:
            save_settings(self.settings_path, values)
            self._log("Settings saved.", "success")
        except Exception as exc:
            self._log(f"Settings save failed: {exc}", "error")
            restart_after_save = False
        if restart_after_save:
            QtCore.QTimer.singleShot(0, self._restart_application_after_settings_save)
    def _restart_application_after_settings_save(self) -> None:
        if not self._prompt_save_dirty_scene():
            self._log("Renderer restart cancelled because the current scene was not closed.", "warning")
            return
        program, args = self._restart_command()
        ok = QtCore.QProcess.startDetached(program, args, str(self.app_root))
        if not ok:
            self._log("Automatic restart failed. Close and reopen GhostRigger to apply the renderer change.", "error")
            QtWidgets.QMessageBox.warning(
                self,
                "Restart Failed",
                "GhostRigger could not restart automatically. Close and reopen the application to apply the renderer change.",
            )
            return
        self._log("Restarting GhostRigger to apply renderer backend change.", "success")
        QtCore.QTimer.singleShot(100, QtWidgets.QApplication.quit)
    def _restart_command(self) -> tuple[str, list[str]]:
        if getattr(sys, "frozen", False):
            return sys.executable, list(sys.argv[1:])
        script = Path(sys.argv[0])
        if not script.is_absolute():
            script = (Path.cwd() / script).resolve()
        return sys.executable, [str(script), *sys.argv[1:]]
    def _apply_measurement_settings(self) -> None:
        settings = MeasurementSettings.from_dict(self.settings_data.get("measurement", {}))
        self.settings_data["measurement"] = settings.to_dict()
        for widget_name in ("viewport", "properties_panel", "module_geometry_panel"):
            widget = getattr(self, widget_name, None)
            apply_settings = getattr(widget, "set_measurement_settings", None)
            if callable(apply_settings):
                apply_settings(settings)
    def _merge_measurement_settings(self, values: dict) -> None:
        measurement = MeasurementSettings.from_dict(values.get("measurement", values)).to_dict()
        self.settings_data["measurement"] = measurement
        self._apply_measurement_settings()
        try:
            save_settings(self.settings_path, self.settings_data)
        except Exception as exc:
            self._log(f"Measurement settings save failed: {exc}", "error")
    def closeEvent(self, event: QtGui.QCloseEvent):
        if not self._prompt_save_dirty_scene():
            event.ignore()
            return
        self._remove_gui_log_handler()
        try:
            self._matrix_engine.stop()
        except Exception:
            pass
        super().closeEvent(event)
    def _install_gui_log_handler(self) -> None:
        if self._gui_log_handler is not None or not hasattr(self, "log_panel"):
            return
        handler = QtLogPanelHandler(self.log_panel)
        handler.setLevel(logging.WARNING)
        logging.getLogger().addHandler(handler)
        self._gui_log_handler = handler
    def _remove_gui_log_handler(self) -> None:
        handler = self._gui_log_handler
        if handler is None:
            return
        logging.getLogger().removeHandler(handler)
        handler.close()
        self._gui_log_handler = None
    def _log(self, msg: str, level: str = "info"):
        if hasattr(self, "log_panel"):
            self.log_panel.log(msg, level)
        else:
            log.info(msg)
