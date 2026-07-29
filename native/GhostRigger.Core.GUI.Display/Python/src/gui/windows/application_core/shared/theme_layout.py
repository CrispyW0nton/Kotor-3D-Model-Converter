"""Theme and layout hooks for the GhostRigger main window."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

try:
    from PySide6 import QtCore, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.qt_lib.assets.qt_theme import update_legacy_palette
from src.gui.qt_lib.dialogs.qt_settings_dialog import save_settings
from src.gui.libtheme.style_tokens import LEGACY_MATRIX_COLORS
from src.gui.libtheme.theme_watcher import ThemeLayoutWatcher

C = dict(LEGACY_MATRIX_COLORS)
_GUI_DIR = Path(__file__).resolve().parents[3]
_QT_ICON_DIR = (_GUI_DIR / "icons").as_posix()
log = logging.getLogger(__name__)


class ThemeLayoutMixin:
    """Theme, layout, and hot-reload behavior for ``QtGhostRiggerMainWindow``."""

    def _apply_theme(self):
        if hasattr(self, "theme_manager"):
            theme = self.theme_manager.apply_current_theme(self)
            update_legacy_palette(theme)
            return
        self.setStyleSheet(
            f"""
            QMainWindow, QWidget {{
                background: {C['bg']};
                color: {C['text']};
                font-family: Consolas, Segoe UI, sans-serif;
                font-size: 9pt;
            }}
            QMenuBar, QMenu, QToolBar, QStatusBar {{
                background: {C['panel']};
                color: {C['text']};
                border: 0;
            }}
            QMenuBar {{
                padding: 2px 6px;
            }}
            QMenuBar::item:selected, QMenu::item:selected {{
                background: {C['border']};
                color: {C['accent']};
            }}
            QListWidget, QTextEdit, QPlainTextEdit, QTreeWidget, QTableWidget, QTabWidget::pane {{
                background: {C['bg2']};
                color: {C['text']};
                border: 1px solid {C['border']};
            }}
            QTabWidget::pane {{
                top: -1px;
            }}
            QTabBar::tab {{
                background: {C['panel']};
                color: {C['text2']};
                border: 1px solid {C['border']};
                border-bottom-color: #D8D8D8;
                padding: 6px 12px;
                min-width: 78px;
                min-height: 22px;
            }}
            QTabBar::tab:selected {{
                background: {C['bg2']};
                color: {C['accent']};
                border-color: #D8D8D8;
                border-bottom-color: {C['bg2']};
            }}
            QTabBar::tab:hover {{
                color: {C['accent']};
                background: {C['hover']};
            }}
            QTabBar QToolButton {{
                background: {C['panel2']};
                color: {C['accent']};
                border: 1px solid {C['border']};
                width: 22px;
                height: 24px;
                padding: 0px;
                margin: 0px;
            }}
            QTabBar::scroller {{
                width: 48px;
            }}
            QTabBar QToolButton::left-arrow {{
                image: url("{_QT_ICON_DIR}/tab_left.svg");
                width: 22px;
                height: 24px;
            }}
            QTabBar QToolButton::right-arrow {{
                image: url("{_QT_ICON_DIR}/tab_right.svg");
                width: 22px;
                height: 24px;
            }}
            QHeaderView::section {{
                background: {C['panel2']};
                color: {C['text']};
                border: 1px solid {C['border']};
                padding: 4px;
            }}
            QRadioButton, QCheckBox, QGroupBox {{
                color: {C['text']};
            }}
            QRadioButton::indicator, QCheckBox::indicator {{
                width: 12px;
                height: 12px;
            }}
            QRadioButton::indicator:checked, QCheckBox::indicator:checked {{
                background: {C['accent']};
                border: 1px solid #D8D8D8;
            }}
            QRadioButton::indicator:unchecked, QCheckBox::indicator:unchecked {{
                background: {C['bg']};
                border: 1px solid {C['text2']};
            }}
            QLineEdit {{
                background: {C['panel2']};
                color: {C['text']};
                border: 1px solid {C['border']};
                padding: 5px;
            }}
            QPushButton, QToolButton {{
                background: {C['panel2']};
                color: {C['text']};
                border: 1px solid {C['border']};
                padding: 5px 10px;
            }}
            QPushButton:hover, QToolButton:hover {{
                background: {C['border']};
                color: {C['accent']};
            }}
            QPushButton[accent="true"], QToolButton[accent="true"] {{
                background: {C['accent']};
                color: #001A0E;
                border-color: {C['accent']};
            }}
            QPushButton[compact="true"], QToolButton[compact="true"] {{
                padding: 2px 8px;
                font-size: 8pt;
            }}
            QFrame#HeaderBar, QFrame#CommandBar, QFrame#CommandBarHost {{
                background: transparent;
            }}
            QMainWindow::separator {{
                background: {C['border']};
                width: 4px;
                height: 4px;
            }}
            QMainWindow::separator:hover {{
                background: {C['border']};
            }}
            QFrame#HeaderBar {{
                border-bottom: 1px solid #102019;
            }}
            QFrame#CommandBarHost {{
                border-top: 1px solid #102019;
                border-bottom: 1px solid {C['border']};
            }}
            QFrame#CommandBar {{
                border: 0;
            }}
            QFrame#CommandBar QToolButton#CommandStripButton,
            QFrame#CommandBar QToolButton#CommandStripMenuButton {{
                background: {C['panel2']};
                color: {C['text']};
                border: 1px solid {C['border']};
                border-radius: 2px;
                padding: 1px 5px;
                font-size: 8pt;
                min-height: 20px;
                max-height: 20px;
                min-width: 28px;
            }}
            QFrame#CommandBar QToolButton#CommandStripMenuButton {{
                min-width: 32px;
            }}
            QFrame#CommandBar QToolButton#CommandStripButton:hover,
            QFrame#CommandBar QToolButton#CommandStripMenuButton:hover {{
                background: {C['border']};
                color: {C['accent']};
                border-color: {C['accent']};
            }}
            QFrame#CommandBar QToolButton#CommandStripButton:checked {{
                background: {C['accent2']};
                color: {C['text']};
                border-color: {C['accent']};
            }}
            QComboBox#VisualProfileCombo {{
                background: {C['panel2']};
                color: {C['text']};
                border: 1px solid {C['border']};
                border-radius: 2px;
                padding: 1px 7px;
                min-height: 18px;
            }}
            QFrame#LogHeader {{
                background: {C['bg']};
                border-top: 1px solid {C['border']};
            }}
            QLabel#GhostTitle {{
                color: {C['accent']};
                font-size: 14pt;
                font-weight: bold;
            }}
            QLabel#GhostSubtitle, QLabel#HeaderMeta {{
                color: {C['text2']};
                font-size: 8pt;
            }}
            QLabel#HeaderIpcMeta {{
                color: {C['accent']};
                font-size: 7pt;
            }}
            QLabel#ModelPill {{
                background: transparent;
                color: {C['text']};
                border: 0;
                padding: 2px 6px;
                font-weight: bold;
            }}
            QSplitter::handle {{
                background: {C['border']};
            }}
            """
        )

    def apply_ghost_theme(self, theme) -> None:
        if theme is not None and getattr(theme, "is_native", lambda: False)():
            self.apply_native_theme()
            return
        update_legacy_palette(theme)
        self._apply_matrix_theme(theme)
        toolbar_band = getattr(self, "viewport_toolbar_band", None)
        if toolbar_band is not None:
            toolbar_band.setStyleSheet(
                f"QFrame#ViewportToolbarBand {{ background:{theme.color('viewportToolbar.background', theme.color('toolbar.background'))}; "
                f"border:1px solid {theme.color('viewportToolbar.border', theme.color('toolbar.border'))}; }}"
        )
        viewport = getattr(self, "viewport", None)
        if viewport is not None and hasattr(viewport, "apply_ghost_theme"):
            self._profile_theme_hook("viewport", viewport.apply_ghost_theme, theme)
        for widget in self.findChildren(QtWidgets.QWidget):
            if self._defer_startup_theme_hook(widget, primary_widget=viewport):
                continue
            hook = getattr(widget, "apply_ghost_theme", None)
            if callable(hook):
                self._profile_theme_hook(widget.__class__.__name__, hook, theme)

    def apply_native_theme(self) -> None:
        for widget in self.findChildren(QtWidgets.QWidget):
            if not self._defer_startup_theme_hook(widget):
                widget.setStyleSheet("")
        theme = self.theme_manager.current_theme or self.theme_manager.get_theme()
        self.setStyleSheet(
            f"""
            QMainWindow::separator {{
                background: {theme.color('panel.border', C['border'])};
                width: 4px;
                height: 4px;
            }}
            QMainWindow::separator:hover {{
                background: {theme.color('panel.border', C['border'])};
            }}
            """
        )
        viewport = getattr(self, "viewport", None)
        if viewport is not None and hasattr(viewport, "apply_native_theme"):
            self._profile_theme_hook("viewport native", viewport.apply_native_theme)
        for panel in (getattr(self, "header_bar", None),):
            if panel is not None:
                self._apply_matrix_bar_config(panel, theme)
                panel.apply_ghost_theme(theme)
                if self._matrix_bar_settings(theme).get("style") == "disabled" and hasattr(panel, "_background"):
                    palette_color = self.palette().window().color()
                    panel._background = palette_color
                panel.update()
        for widget in self.findChildren(QtWidgets.QWidget):
            if self._defer_startup_theme_hook(widget, primary_widget=viewport):
                continue
            hook = getattr(widget, "apply_native_theme", None)
            if callable(hook):
                self._profile_theme_hook(f"{widget.__class__.__name__} native", hook)

    def _defer_startup_theme_hook(self, widget, *, primary_widget=None) -> bool:
        """Skip expensive theme hooks for widget trees already handled or hidden at launch."""

        if widget is None:
            return True
        if primary_widget is not None and (
            widget is primary_widget
            or primary_widget.isAncestorOf(widget)
        ):
            return True
        for dock in getattr(self, "_detachable_panels", {}).values():
            if dock is None or dock.isVisible():
                continue
            if widget is dock or dock.isAncestorOf(widget):
                return True
        return False

    def _apply_theme_to_visible_panel(self, root_widget) -> None:
        """Apply deferred theme hooks when a hidden dock panel is first shown."""

        if root_widget is None or not hasattr(self, "theme_manager"):
            return
        theme = self.theme_manager.current_theme or self.theme_manager.get_theme()
        native = theme is not None and getattr(theme, "is_native", lambda: False)()
        widgets = [root_widget, *root_widget.findChildren(QtWidgets.QWidget)]
        for widget in widgets:
            if widget is None:
                continue
            hook = getattr(widget, "apply_native_theme" if native else "apply_ghost_theme", None)
            if callable(hook):
                if native:
                    self._profile_theme_hook(widget.__class__.__name__, hook)
                else:
                    self._profile_theme_hook(widget.__class__.__name__, hook, theme)

    @staticmethod
    def _theme_hook_profile_enabled() -> bool:
        return str(os.environ.get("GHOSTRIGGER_THEME_PROFILE", "")).strip().lower() in {"1", "true", "yes", "on"}

    def _profile_theme_hook(self, label: str, hook, *args) -> None:
        if not self._theme_hook_profile_enabled():
            hook(*args)
            return
        started = time.perf_counter()
        hook(*args)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if elapsed_ms >= 5.0:
            log.info("Theme hook %s: %.1f ms", label, elapsed_ms)

    def _on_theme_changed(self, theme) -> None:
        update_legacy_palette(theme)
        self._profile_theme_hook("main window sync theme/layout settings", self._sync_theme_layout_settings)
        self._profile_theme_hook("main window refresh theme icons", self._refresh_theme_sensitive_icons)
        self._profile_theme_hook("main window progress toast theme", self._apply_progress_toast_theme)

    def _on_layout_changed(self, layout) -> None:
        self._sync_theme_layout_settings()
        combo = getattr(self, "visual_profile_combo", None)
        if combo is not None:
            combo.blockSignals(True)
            try:
                index = combo.findData(getattr(layout, "id", "default"))
                combo.setCurrentIndex(max(index, 0))
            finally:
                combo.blockSignals(False)
        QtCore.QTimer.singleShot(0, self._sync_reserved_top_rows)
        QtCore.QTimer.singleShot(0, self._update_command_bar_responsiveness)

    def _refresh_startup_layout_after_show(self) -> None:
        """Re-apply the selected layout once startup widgets have real screen geometry."""

        if not hasattr(self, "layout_manager"):
            return
        self.layout_manager.apply_current_layout(self)
        self._sync_reserved_top_rows()
        QtCore.QTimer.singleShot(0, self._sync_reserved_top_rows)
        QtCore.QTimer.singleShot(75, self._sync_reserved_top_rows)

    def _sync_theme_layout_settings(self) -> dict:
        theme_values = self.theme_manager.to_settings()
        layout_values = self.layout_manager.to_settings()
        merged = self.settings_data.setdefault("theme_layout", {})
        merged.update(layout_values)
        for key in (
            "theme_mode",
            "selected_theme",
            "os_light_theme",
            "os_dark_theme",
            "last_known_os_theme",
            "user_theme_dir",
        ):
            if key in theme_values:
                merged[key] = theme_values[key]
        return merged

    def _apply_appearance_from_ipc(self, theme_id: str = "", layout_id: str = "", *, persist: bool = True) -> dict:
        """Apply theme/layout choices through the active managers for IPC callers."""
        requested_theme = str(theme_id or "").strip()
        requested_layout = str(layout_id or "").strip()
        theme = self.theme_manager.current_theme or self.theme_manager.get_theme()
        layout = self.layout_manager.current_layout or self.layout_manager.get_layout()
        if requested_theme:
            theme = self.theme_manager.select_theme(requested_theme, apply=True, target=self)
            update_legacy_palette(theme)
            self._refresh_theme_sensitive_icons()
        if requested_layout:
            layout = self.layout_manager.select_layout(requested_layout, apply=True, window=self)
            combo = getattr(self, "visual_profile_combo", None)
            if combo is not None:
                combo.blockSignals(True)
                try:
                    index = combo.findData(getattr(layout, "id", "default"))
                    combo.setCurrentIndex(max(index, 0))
                finally:
                    combo.blockSignals(False)
            QtCore.QTimer.singleShot(0, self._sync_reserved_top_rows)
        self._sync_theme_layout_settings()
        if persist:
            try:
                save_settings(self.settings_path, self.settings_data)
            except Exception as exc:
                self._log(f"IPC appearance settings save failed: {exc}", "warning")
        self._log(
            f"IPC appearance: theme={getattr(theme, 'id', '') or '<unchanged>'}, "
            f"layout={getattr(layout, 'id', '') or '<unchanged>'}",
            "info",
        )
        return {
            "theme": getattr(theme, "id", ""),
            "layout": getattr(layout, "id", ""),
            "persisted": bool(persist),
        }

    def _refresh_theme_sensitive_icons(self) -> None:
        for name, action in (
            ("open", getattr(self, "open_model_action", None)),
            ("settings", getattr(self, "settings_action", None)),
            ("anims", getattr(self, "anims_action", None)),
            ("diag", getattr(self, "diag_action", None)),
            ("scene", getattr(self, "scene_panel_action", None)),
            ("props", getattr(self, "properties_panel_action", None)),
            ("body_attachment", getattr(self, "body_attachment_panel_action", None)),
            ("sequence", getattr(self, "sequence_editor_action", None)),
            ("lights", getattr(self, "lighting_panel_action", None)),
            ("cameras", getattr(self, "camera_panel_action", None)),
            ("mesh_tools", getattr(self, "mesh_tools_panel_action", None)),
            ("output_log", getattr(self, "output_log_panel_action", None)),
            ("python_terminal", getattr(self, "python_terminal_panel_action", None)),
        ):
            if action is not None:
                action.setIcon(self._icon(name))

    def _configure_theme_watcher(self) -> None:
        if self._theme_watcher is not None:
            self._theme_watcher.stop()
            self._theme_watcher = None
        if not bool(self.theme_manager.settings.hot_reload_enabled):
            return
        watcher = ThemeLayoutWatcher(
            [
                self.theme_manager.packaged_theme_dir,
                self.theme_manager.user_theme_dir,
                self.layout_manager.packaged_layout_dir,
                self.layout_manager.user_layout_dir,
            ],
            self,
        )
        watcher.changed.connect(self._on_theme_layout_file_changed)
        if watcher.start():
            self._theme_watcher = watcher

    def _on_theme_layout_file_changed(self, _kind: str, path: str) -> None:
        lower = path.lower()
        if "\\themes\\" in lower or "/themes/" in lower:
            self.theme_manager.reload()
            self.theme_manager.apply_current_theme(self)
            self._log(f"Theme file reloaded: {Path(path).name}", "success")
            return
        if "\\layouts\\" in lower or "/layouts/" in lower:
            self.layout_manager.reload()
            current = self.layout_manager.get_layout()
            answer = QtWidgets.QMessageBox.question(
                self,
                "Apply layout changes?",
                f"Reload layout '{current.name}' now?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if answer == QtWidgets.QMessageBox.Yes:
                self.layout_manager.apply_current_layout(self)
            self._log(f"Layout file reloaded: {Path(path).name}", "success")
