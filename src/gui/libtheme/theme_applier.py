"""Runtime theme application."""

from __future__ import annotations

import logging
import time

from PySide6 import QtCore, QtGui, QtWidgets

from .font_manager import FontManager
from .qt_stylesheet_builder import QtStylesheetBuilder
from .theme_model import Theme

log = logging.getLogger(__name__)


class _StylesheetBuildWorker(QtCore.QObject):
    finished = QtCore.Signal(object, object, str, float)
    failed = QtCore.Signal(object, object, str)

    def __init__(self, theme: Theme, key: tuple) -> None:
        super().__init__()
        self.theme = theme
        self.key = key

    @QtCore.Slot()
    def run(self) -> None:
        try:
            start = time.perf_counter()
            stylesheet = QtStylesheetBuilder().build(self.theme)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self.finished.emit(self.theme, self.key, stylesheet, elapsed_ms)
        except Exception as exc:
            self.failed.emit(self.theme, self.key, str(exc))


class ThemeApplier(QtCore.QObject):
    themeChanged = QtCore.Signal(object)
    themeApplyStarted = QtCore.Signal(object)
    themeApplyProgress = QtCore.Signal(str, int, int)
    themeApplyFinished = QtCore.Signal(object, float)
    themeApplyFailed = QtCore.Signal(str)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.builder = QtStylesheetBuilder()
        self.font_manager = FontManager()
        self._aware_widgets: list[QtWidgets.QWidget] = []
        self._stylesheet_cache: dict[tuple, str] = {}
        self._last_applied_key: tuple | None = None
        self._last_target_id: int | None = None
        self._pending_theme: Theme | None = None
        self._pending_target: QtWidgets.QWidget | None = None
        self._apply_timer = QtCore.QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.setInterval(35)
        self._apply_timer.timeout.connect(self._flush_pending_apply)
        self._applying = False
        self._worker_thread: QtCore.QThread | None = None
        self._worker: _StylesheetBuildWorker | None = None
        self._worker_target: QtWidgets.QWidget | None = None

    def build_stylesheet(self, theme: Theme) -> str:
        key = self._theme_cache_key(theme)
        cached = self._stylesheet_cache.get(key)
        if cached is not None:
            return cached
        stylesheet = self.builder.build(theme)
        self._stylesheet_cache[key] = stylesheet
        return stylesheet

    def register_theme_aware_widget(self, widget: QtWidgets.QWidget) -> None:
        if widget not in self._aware_widgets:
            self._aware_widgets.append(widget)
            widget.destroyed.connect(lambda _obj=None, w=widget: self.unregister_theme_aware_widget(w))

    def unregister_theme_aware_widget(self, widget: QtWidgets.QWidget) -> None:
        try:
            self._aware_widgets.remove(widget)
        except ValueError:
            pass

    def apply_theme(self, theme: Theme, target: QtWidgets.QWidget | None = None, *, immediate: bool = False) -> None:
        """Queue a theme apply, coalescing rapid requests from settings/hot reload."""
        key = self._theme_cache_key(theme)
        target_id = id(target) if target is not None else 0
        if key == self._last_applied_key and target_id == self._last_target_id:
            log.debug("Theme apply skipped; theme is unchanged: %s", theme.id)
            return
        self._pending_theme = theme
        self._pending_target = target
        if immediate or self._last_applied_key is None:
            self._apply_timer.stop()
            self._flush_pending_apply()
            return
        if not self._apply_timer.isActive():
            self._apply_timer.start()

    def _flush_pending_apply(self) -> None:
        if self._pending_theme is None or self._applying:
            return
        theme = self._pending_theme
        target = self._pending_target
        self._pending_theme = None
        self._pending_target = None
        self._begin_theme_apply(theme, target)

    def _begin_theme_apply(self, theme: Theme, target: QtWidgets.QWidget | None = None) -> None:
        key = self._theme_cache_key(theme)
        target_id = id(target) if target is not None else 0
        if key == self._last_applied_key and target_id == self._last_target_id:
            return
        cached = self._stylesheet_cache.get(key)
        self._applying = True
        self.themeApplyStarted.emit(theme)
        self._pump_ui_events()
        if cached is not None:
            self.themeApplyProgress.emit("Applying cached stylesheet...", 2, 3)
            self._pump_ui_events()
            self._apply_theme_now(theme, target, cached, 0.0)
            return
        self.themeApplyProgress.emit("Building theme stylesheet in background...", 1, 3)
        self._pump_ui_events()
        self._worker_target = target
        self._worker_thread = QtCore.QThread(self)
        self._worker = _StylesheetBuildWorker(theme, key)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_stylesheet_built)
        self._worker.failed.connect(self._on_stylesheet_build_failed)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.failed.connect(self._worker_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.finished.connect(self._clear_stylesheet_worker)
        self._worker_thread.start()

    @QtCore.Slot(object, object, str, float)
    def _on_stylesheet_built(self, theme: Theme, key: tuple, stylesheet: str, style_ms: float) -> None:
        self._stylesheet_cache[key] = stylesheet
        if self._pending_theme is not None:
            self._applying = False
            self._worker_target = None
            QtCore.QTimer.singleShot(0, self._flush_pending_apply)
            return
        self.themeApplyProgress.emit("Applying theme to Qt widgets...", 2, 3)
        self._pump_ui_events()
        self._apply_theme_now(theme, self._worker_target, stylesheet, style_ms)

    @QtCore.Slot(object, object, str)
    def _on_stylesheet_build_failed(self, theme: Theme, key: tuple, message: str) -> None:
        self._applying = False
        self._worker_target = None
        self.themeApplyFailed.emit(message)
        log.error("Theme stylesheet build failed for '%s': %s", theme.id, message)
        if self._pending_theme is not None:
            QtCore.QTimer.singleShot(0, self._flush_pending_apply)

    @QtCore.Slot()
    def _clear_stylesheet_worker(self) -> None:
        self._worker_thread = None
        self._worker = None

    @staticmethod
    def _pump_ui_events() -> None:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents, 15)

    def _apply_theme_now(
        self,
        theme: Theme,
        target: QtWidgets.QWidget | None = None,
        stylesheet: str | None = None,
        style_ms: float | None = None,
    ) -> None:
        app = QtWidgets.QApplication.instance()
        key = self._theme_cache_key(theme)
        target_id = id(target) if target is not None else 0
        if key == self._last_applied_key and target_id == self._last_target_id:
            self._applying = False
            return

        total_start = time.perf_counter()
        if stylesheet is None:
            style_start = total_start
            stylesheet = self.build_stylesheet(theme)
            style_ms = (time.perf_counter() - style_start) * 1000.0
        elif style_ms is None:
            style_ms = 0.0
        widget = target or (app.activeWindow() if app is not None else None)
        updates_disabled = False
        cursor_set = False
        applied = False
        finished_total_ms = 0.0
        try:
            if app is not None:
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
                cursor_set = True
            if widget is not None:
                widget.setUpdatesEnabled(False)
                updates_disabled = True
            app_start = time.perf_counter()
            if app is not None:
                if theme.is_native():
                    app.setPalette(app.style().standardPalette())
                else:
                    self.font_manager.apply_application_font(app, theme)
                    app.setPalette(self._palette(theme))
                app.setStyleSheet(stylesheet)
            elif target is not None:
                target.setStyleSheet(stylesheet)
            app_ms = (time.perf_counter() - app_start) * 1000.0

            notify_start = time.perf_counter()
            self.notify_theme_changed(theme)
            notify_ms = (time.perf_counter() - notify_start) * 1000.0
            total_ms = (time.perf_counter() - total_start) * 1000.0
            self._last_applied_key = key
            self._last_target_id = target_id
            self.themeApplyProgress.emit("Theme applied.", 3, 3)
            applied = True
            finished_total_ms = total_ms
            log.info(
                "Theme apply '%s': stylesheet %.1f ms, QApplication %.1f ms, hooks/icons %.1f ms, total %.1f ms",
                theme.id,
                style_ms,
                app_ms,
                notify_ms,
                total_ms,
            )
        finally:
            if updates_disabled and widget is not None:
                widget.setUpdatesEnabled(True)
                widget.update()
            if cursor_set:
                QtWidgets.QApplication.restoreOverrideCursor()
            self._applying = False
            self._worker_target = None
            if applied:
                self.themeApplyFinished.emit(theme, finished_total_ms)
            if self._pending_theme is not None:
                QtCore.QTimer.singleShot(0, self._flush_pending_apply)

    def notify_theme_changed(self, theme: Theme) -> None:
        if theme.is_native():
            for widget in list(self._aware_widgets):
                if widget is None:
                    continue
                native_hook = getattr(widget, "apply_native_theme", None)
                if callable(native_hook):
                    native_hook()
                else:
                    self._clear_widget_styles(widget)
            self.themeChanged.emit(theme)
            return
        for widget in list(self._aware_widgets):
            if widget is None:
                continue
            hook = getattr(widget, "apply_ghost_theme", None)
            if callable(hook):
                hook(theme)
        self.themeChanged.emit(theme)

    @staticmethod
    def _clear_widget_styles(widget: QtWidgets.QWidget) -> None:
        widget.setStyleSheet("")
        for child in widget.findChildren(QtWidgets.QWidget):
            child.setStyleSheet("")

    @staticmethod
    def _theme_cache_key(theme: Theme) -> tuple:
        font_key = tuple(sorted((role, font.family, font.size, font.weight) for role, font in theme.fonts.items()))
        return (
            theme.id,
            theme.version,
            theme.mode,
            tuple(sorted(theme.colors.items())),
            tuple(sorted(theme.metrics.items())),
            tuple(sorted(theme.styles.items())),
            font_key,
            theme.icons.provider,
            theme.icons.default_mode,
            tuple(sorted(theme.icons.sizes.items())),
        )

    @staticmethod
    def _palette(theme: Theme) -> QtGui.QPalette:
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(theme.color("window.background")))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(theme.color("text.primary")))
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor(theme.color("viewport.background")))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(theme.color("panel.background")))
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor(theme.color("text.primary")))
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor(theme.color("button.background")))
        palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(theme.color("button.text")))
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(theme.color("selection.background")))
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(theme.color("selection.text")))
        return palette
