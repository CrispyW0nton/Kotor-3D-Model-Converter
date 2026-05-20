"""Qt main-window shell for GhostRigger.

This is the first migration step away from Tkinter.  Qt owns the main
application window and process event loop; legacy Tk tools are launched in a
separate process so Qt and Tk do not fight over GUI ownership in one process.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
import sys
import time
import traceback
import copy
import importlib
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Tk fallback
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.qt_lib.panels.qt_library_panel import QtLibraryPanel, enrich_library_rows
from src.gui.qt_lib.panels.qt_log_panel import QtLogPanel
from src.gui.qt_lib.assets.qt_matrix_background import QtMatrixEngine, QtMatrixLabel, QtMatrixPanel
from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel, QtSkeletonPanel
from src.gui.qt_lib.viewports.qt_viewport import QtMainViewportWidget
from src.gui.qt_lib.panels.qt_animation_panel import (
    QtAnimationLibraryCombinedPanel,
    QtAnimationLibraryPanel,
    QtAnimationsPanel,
)
from src.gui.qt_lib.windows.qt_blueprint_editor import QtBlueprintEditorWindow
from src.gui.qt_lib.panels.qt_character_builder_panel import QtCharacterBuilderWindow
from src.gui.qt_lib.panels.qt_diagnostics_panel import QtDiagnosticsWindow
from src.gui.qt_lib.dialogs.qt_dialogs import show_about, show_format_reference, show_ipc_info, show_viewport_navigation_reference
from src.gui.qt_lib.panels.qt_modular_panel import QtModularModePanel
from src.gui.qt_lib.panels.qt_resource_panel import QtResourceBrowserPanel, QtTwoDaBrowserPanel
from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow
from src.gui.qt_lib.panels.qt_rig_panel import QtRigWindow
from src.gui.qt_lib.dialogs.qt_settings_dialog import QtSettingsDialog, save_settings
from src.gui.qt_lib.panels.qt_texture_panel import QtTextureToolWindow
from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow
from src.gui.qt_lib.rendering.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE, normalize_viewport_navigation_profile


C = {
    "bg": "#0B0F0D",
    "bg2": "#07100C",
    "panel": "#111916",
    "panel2": "#151D1A",
    "border": "#1B2A22",
    "hover": "#183428",
    "selected": "#00FF7A",
    "accent": "#00FF7A",
    "accent2": "#00D7B5",
    "text": "#E8F0EC",
    "text2": "#7A9A88",
    "success": "#00FF7A",
    "warning": "#FFAA00",
    "error": "#FF4444",
}

_GUI_DIR = Path(__file__).resolve().parents[1]
_QT_ICON_DIR = (_GUI_DIR / "icons").as_posix()


def _prebuild_gpu_mesh_data_for_model(model) -> None:
    try:
        from src.gui.qt_lib.rendering.gpu_renderer import prebuild_static_gpu_mesh_data

        prebuild_static_gpu_mesh_data(model)
    except Exception:
        log.debug("Static GPU mesh prebuild failed", exc_info=True)


class ModelLoadWorker(QtCore.QObject):
    progress = QtCore.Signal(str, int, int)
    finished = QtCore.Signal(object, str, str)

    def __init__(self, path: str, mdx_path: str = "", game: str = ""):
        super().__init__()
        self.path = path
        self.mdx_path = mdx_path
        self.game = game.upper()

    @QtCore.Slot()
    def run(self):
        try:
            path = Path(self.path)
            self.progress.emit("Reading model into RAM", 1, 5)
            raw = path.read_bytes()
            first16 = raw[:16]
            printable_count = sum(
                1 for byte in first16
                if 0x20 <= byte <= 0x7E or byte in (0x09, 0x0A, 0x0D)
            )
            is_ascii_mdl = (
                printable_count >= 10
                or raw[:8].lstrip(b"\x00").startswith(b"newmodel")
                or raw[:2] in (b"#\x20", b"# ")
            )
            if is_ascii_mdl:
                from src.core.mdl_parser import MDLAsciiParser

                self.progress.emit("Parsing ASCII MDL", 2, 5)
                lines = raw.decode("utf-8", errors="replace").splitlines()
                model = MDLAsciiParser().parse(lines)
                model.mdl_path = str(path)
                model.mdx_path = ""
            else:
                from src.core.kotor_loader import load_model_from_bytes
                from src.core.model_data import GameVersion

                self.progress.emit("Reading MDX bytes", 2, 5)
                mdx_path = Path(self.mdx_path) if self.mdx_path else path.with_suffix(".mdx")
                mdx = mdx_path.read_bytes() if mdx_path.exists() else b""
                game_version = None
                if self.game:
                    game_version = GameVersion.K2 if self.game == "K2" else GameVersion.K1
                self.progress.emit("Parsing binary MDL/MDX", 3, 5)
                model = load_model_from_bytes(raw, mdx, game_version=game_version)
                if model is not None:
                    model.mdl_path = str(path)
                    model.mdx_path = str(mdx_path) if mdx else ""
            if model is None:
                raise RuntimeError(f"Could not parse {path.name}")
            if self.game:
                from src.core.model_data import GameVersion

                model.game_version = GameVersion.K2 if self.game == "K2" else GameVersion.K1
            self.progress.emit("Preparing GPU mesh buffers in RAM", 4, 5)
            _prebuild_gpu_mesh_data_for_model(model)
            self.progress.emit("Handing model to viewport", 5, 5)
            self.finished.emit(model, self.path, "")
        except Exception:
            self.finished.emit(None, self.path, traceback.format_exc())


class ResourceModelLoadWorker(QtCore.QObject):
    progress = QtCore.Signal(str, int, int)
    finished = QtCore.Signal(object, str, str)

    def __init__(self, resref: str, game: str, k1_dir: str = "", k2_dir: str = ""):
        super().__init__()
        self.resref = resref
        self.game = game.upper()
        self.k1_dir = k1_dir
        self.k2_dir = k2_dir

    @QtCore.Slot()
    def run(self):
        try:
            from src.core.kotor_loader import load_model_from_bytes
            from src.core.model_data import GameVersion
            from src.core.resource_manager import ResourceManager

            mgr = ResourceManager()
            if self.k1_dir:
                mgr.set_k1_dir(self.k1_dir)
            if self.k2_dir:
                mgr.set_k2_dir(self.k2_dir)

            self.progress.emit("Reading model resource into RAM", 1, 5)
            mdl = mgr.get_mdl(self.resref, self.game)
            if not mdl:
                raise FileNotFoundError(f"{self.game}:{self.resref}.mdl")
            self.progress.emit("Reading MDX resource", 2, 5)
            mdx = mgr.get_mdx(self.resref, self.game) or b""
            game_version = GameVersion.K2 if self.game == "K2" else GameVersion.K1
            self.progress.emit("Parsing binary MDL/MDX", 3, 5)
            model = load_model_from_bytes(mdl, mdx, game_version=game_version)
            if model is None:
                raise RuntimeError(f"Could not parse {self.game}:{self.resref}.mdl")
            model.game_version = game_version
            self.progress.emit("Preparing GPU mesh buffers in RAM", 4, 5)
            _prebuild_gpu_mesh_data_for_model(model)
            self.progress.emit("Handing model to viewport", 5, 5)
            self.finished.emit(model, f"{self.game}:{self.resref}", "")
        except Exception:
            self.finished.emit(None, f"{self.game}:{self.resref}", traceback.format_exc())


class LibraryScanWorker(QtCore.QObject):
    finished = QtCore.Signal(list, str)

    def __init__(self, k1_dir: str = "", k2_dir: str = ""):
        super().__init__()
        self.k1_dir = k1_dir
        self.k2_dir = k2_dir

    @QtCore.Slot()
    def run(self):
        try:
            from src.core.resource_manager import ResourceManager

            mgr = ResourceManager()
            rows = []
            if self.k1_dir:
                ok = mgr.set_k1_dir(self.k1_dir)
                if ok:
                    for resref, _restype in mgr.list_models("K1"):
                        rows.append({"game": "K1", "resref": resref, "source": self.k1_dir})
            if self.k2_dir:
                ok = mgr.set_k2_dir(self.k2_dir)
                if ok:
                    for resref, _restype in mgr.list_models("K2"):
                        rows.append({"game": "K2", "resref": resref, "source": self.k2_dir})
            rows = enrich_library_rows(rows)
            rows.sort(key=lambda item: (item["game"], item["resref"]))
            self.finished.emit(rows, "")
        except Exception:
            self.finished.emit([], traceback.format_exc())


class AutoDetectWorker(QtCore.QObject):
    finished = QtCore.Signal(str, str, str)

    @QtCore.Slot()
    def run(self):
        try:
            from src.resources.game_detector import detect_kotor_dirs

            k1_dir, k2_dir = detect_kotor_dirs()
            self.finished.emit(k1_dir or "", k2_dir or "", "")
        except Exception:
            self.finished.emit("", "", traceback.format_exc())


class LibraryBatchExportWorker(QtCore.QObject):
    progress = QtCore.Signal(int, int, int, int)
    finished = QtCore.Signal(str, int, int, int, str, str)

    def __init__(self, rows: list[dict], out_dir: str, fmt: str, k1_dir: str = "", k2_dir: str = ""):
        super().__init__()
        self.rows = rows
        self.out_dir = out_dir
        self.fmt = fmt
        self.k1_dir = k1_dir
        self.k2_dir = k2_dir

    @QtCore.Slot()
    def run(self):
        ok = 0
        fail = 0
        total = len(self.rows)
        try:
            from src.core.resource_manager import ResourceManager

            mgr = ResourceManager()
            if self.k1_dir:
                mgr.set_k1_dir(self.k1_dir)
            if self.k2_dir:
                mgr.set_k2_dir(self.k2_dir)

            os.makedirs(self.out_dir, exist_ok=True)
            for index, row in enumerate(self.rows, start=1):
                try:
                    resref = str(row.get("resref", ""))
                    game = str(row.get("game", "K1")).upper()
                    mdl = mgr.get_mdl(resref, game)
                    mdx = mgr.get_mdx(resref, game) or b""
                    if not mdl:
                        fail += 1
                        continue

                    from src.core.kotor_loader import load_model_from_bytes

                    model = load_model_from_bytes(mdl, mdx)
                    if self.fmt == "obj":
                        from src.converters.mesh_converter import OBJExporter

                        OBJExporter().export(model, os.path.join(self.out_dir, f"{resref}.obj"))
                        ok += 1
                    elif self.fmt == "ascii":
                        from src.core.mdl_parser import MDLAsciiWriter

                        MDLAsciiWriter().write(model, os.path.join(self.out_dir, f"{resref}.mdl"))
                        ok += 1
                    elif self.fmt == "tga":
                        from src.gui.qt_lib.rendering.viewport_core import _load_tpc_bytes

                        tex_names = {
                            str(getattr(node, "texture", "") or "").strip()
                            for node in model.all_nodes()
                            if str(getattr(node, "texture", "") or "").strip().lower() not in ("", "null", "none")
                        }
                        wrote_any = False
                        for tex_name in tex_names:
                            raw = mgr.get_texture(tex_name, game)
                            if not raw:
                                continue
                            dst = os.path.join(self.out_dir, f"{tex_name}.tga")
                            if os.path.exists(dst):
                                continue
                            img = _load_tpc_bytes(raw)
                            if img:
                                img.save(dst)
                                ok += 1
                                wrote_any = True
                        if not wrote_any:
                            fail += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1
                if index % 25 == 0 or index == total:
                    self.progress.emit(index, total, ok, fail)
            self.finished.emit(self.fmt, ok, fail, total, self.out_dir, "")
        except Exception:
            self.finished.emit(self.fmt, ok, fail, total, self.out_dir, traceback.format_exc())


class ModelListItem(QtWidgets.QListWidgetItem):
    def __init__(self, row: dict):
        super().__init__(f"[{row.get('game', '?')}] {row.get('resref', '')}")
        self.row = row


class GhostRiggerLogPanel(QtWidgets.QWidget):
    MAX_LOG_LINES = 500

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._collapsed = False
        self._lines: list[tuple[str, str, str]] = []
        self._build()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QtWidgets.QFrame()
        header.setObjectName("LogHeader")
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(4, 2, 4, 2)
        header_layout.setSpacing(4)

        self.toggle_button = QtWidgets.QToolButton()
        self.toggle_button.setText("// Output Log")
        self.toggle_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.toggle_button.clicked.connect(self._toggle_collapse)
        header_layout.addWidget(self.toggle_button)
        header_layout.addStretch(1)

        self.save_button = QtWidgets.QPushButton("Save")
        self.save_button.clicked.connect(self._save_log)
        self.copy_button = QtWidgets.QPushButton("Copy")
        self.copy_button.clicked.connect(self._copy_to_clipboard)
        self.clear_button = QtWidgets.QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear)
        for button in (self.save_button, self.copy_button, self.clear_button):
            button.setProperty("compact", True)
            header_layout.addWidget(button)

        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(True)
        self.text.setMinimumHeight(118)
        self.text.setMaximumHeight(220)

        root.addWidget(header)
        root.addWidget(self.text)

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self.text.setVisible(not self._collapsed)
        self.toggle_button.setText(">> Output Log" if self._collapsed else "// Output Log")

    def log(self, msg: str, level: str = "info"):
        stamp = QtCore.QTime.currentTime().toString("HH:mm:ss")
        self._lines.append((stamp, msg, level))
        if len(self._lines) > self.MAX_LOG_LINES:
            self._lines = self._lines[-self.MAX_LOG_LINES :]
        self._render()

    def _render(self):
        colors = {
            "info": C["text2"],
            "success": C["success"],
            "warning": C["warning"],
            "error": C["error"],
        }
        html = []
        for stamp, msg, level in self._lines:
            color = colors.get(level, C["text2"])
            html.append(
                f'<span style="color:{C["accent2"]}; font-size:8pt">[{stamp}]</span> '
                f'<span style="color:{color}">{msg}</span>'
            )
        self.text.setHtml("<br>".join(html))
        self.text.moveCursor(QtGui.QTextCursor.End)

    def get_text(self) -> str:
        return "\n".join(f"[{stamp}] {msg}" for stamp, msg, _level in self._lines)

    def clear(self):
        self._lines.clear()
        self.text.clear()

    def _copy_to_clipboard(self):
        QtWidgets.QApplication.clipboard().setText(self.get_text())

    def _save_log(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Output Log",
            "ghostrigger_log.txt",
            "Text files (*.txt);;All files (*.*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(self.get_text(), encoding="utf-8")
        except Exception as exc:
            log.error("Log save failed: %s", exc)


class QtProgressToast(QtWidgets.QFrame):
    """Small non-modal progress toast anchored to the main window."""

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setObjectName("ProgressToast")
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setFixedWidth(340)
        self._close_timer = QtCore.QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self.hide)
        self._build()

    def _build(self):
        self.setStyleSheet(
            f"""
            #ProgressToast {{
                background: {C['panel']};
                border: 1px solid {C['accent']};
            }}
            QLabel#ToastTitle {{
                color: {C['text']};
                font-weight: 700;
            }}
            QLabel#ToastDetail {{
                color: {C['text2']};
            }}
            QProgressBar {{
                background: {C['bg']};
                border: 1px solid {C['border']};
                height: 8px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: {C['accent']};
            }}
            """
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        self.title_label = QtWidgets.QLabel()
        self.title_label.setObjectName("ToastTitle")
        self.detail_label = QtWidgets.QLabel()
        self.detail_label.setObjectName("ToastDetail")
        self.detail_label.setWordWrap(True)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setTextVisible(False)
        layout.addWidget(self.title_label)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.progress)

    def show_busy(self, title: str, detail: str):
        self._close_timer.stop()
        self.title_label.setText(title)
        self.detail_label.setText(detail)
        self.progress.setRange(0, 0)
        self._reposition()
        self.show()
        self.raise_()

    def update_progress(self, title: str, detail: str, value: int, total: int):
        self._close_timer.stop()
        self.title_label.setText(title)
        self.detail_label.setText(detail)
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(max(0, min(value, total)))
        else:
            self.progress.setRange(0, 0)
        self._reposition()
        self.show()
        self.raise_()

    def finish(self, title: str, detail: str, delay_ms: int = 2200):
        self.title_label.setText(title)
        self.detail_label.setText(detail)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self._reposition()
        self.show()
        self.raise_()
        self._close_timer.start(delay_ms)

    def _reposition(self):
        parent = self.parentWidget()
        if parent is None:
            return
        x = max(18, (parent.width() - self.width()) // 2)
        y = max(92, int(parent.height() * 0.18))
        point = parent.mapToGlobal(
            QtCore.QPoint(x, y)
        )
        self.move(point)


class QtGhostRiggerMainWindow(QtWidgets.QMainWindow):
    APP_TITLE = "GhostRigger-K1-K2  //  Odyssey Engine Pipeline v6.1"
    APP_VERSION = "6.1.0"

    def __init__(self, app_root: Optional[Path] = None, startup_input: Optional[dict] = None):
        super().__init__()
        self.app_root = app_root or Path(__file__).resolve().parents[2]
        self.startup_input = startup_input or {}
        self.settings_path = self.app_root / "settings.json"
        self.settings_data = self._load_settings()
        self._worker_thread: Optional[QtCore.QThread] = None
        self._model_worker: Optional[QtCore.QObject] = None
        self._scan_thread: Optional[QtCore.QThread] = None
        self._scan_worker: Optional[QtCore.QObject] = None
        self._auto_detect_thread: Optional[QtCore.QThread] = None
        self._auto_detect_worker: Optional[QtCore.QObject] = None
        self._batch_thread: Optional[QtCore.QThread] = None
        self._batch_worker: Optional[QtCore.QObject] = None
        self._legacy_process: Optional[subprocess.Popen] = None
        self._library_rows: list[dict] = []
        self._current_model = None
        self._model_path = ""
        self._current_game = ""
        self._resource_manager = None
        self._resource_manager_dirs: tuple[str, str] = ("", "")
        self._progress_toast: Optional[QtProgressToast] = None
        self._pending_gpu_upload_model_id = 0
        self._pending_gpu_upload_total = 0
        self._texture_dir = ""
        self._animation_engine = None
        self._animation_loop = False
        self._animation_last_tick: Optional[float] = None
        self._retarget_source_model = None
        self._retarget_target_model = None
        self._retarget_engine = None
        self._retarget_mapping_report = None
        self._retarget_last_tick: Optional[float] = None
        self._character_builder_window: Optional[QtCharacterBuilderWindow] = None
        self._matrix_engine = QtMatrixEngine(self, fps=12)
        self._animation_timer = QtCore.QTimer(self)
        self._animation_timer.setInterval(33)
        self._animation_timer.timeout.connect(self._tick_animation)
        self._retarget_timer = QtCore.QTimer(self)
        self._retarget_timer.setInterval(33)
        self._retarget_timer.timeout.connect(self._tick_retarget_animation)

        self.setWindowTitle(self.APP_TITLE)
        self.resize(1600, 950)
        self.setMinimumSize(1100, 700)
        self._apply_theme()
        self._build_actions()
        self._build_menu()
        self._build_toolbar()
        self._build_layout()
        self._build_statusbar()
        self._log("Qt host window ready.", "success")
        QtCore.QTimer.singleShot(0, self._open_startup_inputs)
        QtCore.QTimer.singleShot(250, self._auto_detect_dirs_on_startup)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._progress_toast is not None and self._progress_toast.isVisible():
            self._progress_toast._reposition()

    def moveEvent(self, event):
        super().moveEvent(event)
        if self._progress_toast is not None and self._progress_toast.isVisible():
            self._progress_toast._reposition()

    def _load_settings(self) -> dict:
        try:
            if self.settings_path.exists():
                return json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("Could not read settings.json: %s", exc)
        return {}

    def _apply_theme(self):
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
            QFrame#HeaderBar, QFrame#CommandBar {{
                background: transparent;
            }}
            QFrame#HeaderBar {{
                border-bottom: 1px solid #102019;
            }}
            QFrame#CommandBar {{
                border-top: 1px solid #102019;
                border-bottom: 1px solid {C['border']};
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
            QLabel#ModelPill {{
                background: {C['bg']};
                color: {C['accent']};
                border: 1px solid {C['border']};
                padding: 4px 10px;
                font-weight: bold;
            }}
            QSplitter::handle {{
                background: {C['border']};
            }}
            """
        )

    def _build_actions(self):
        self.open_model_action = QtGui.QAction(self._icon("open"), "Open MDL (binary)...", self)
        self.open_model_action.setShortcut("Ctrl+O")
        self.open_model_action.triggered.connect(self._open_model)

        self.open_ascii_action = QtGui.QAction("Open MDL (ASCII text)...", self)
        self.open_ascii_action.setShortcut("Ctrl+Shift+O")
        self.open_ascii_action.triggered.connect(lambda _checked=False: self._open_model(ascii_only=True))
        self.clear_model_action = QtGui.QAction("Clear Model", self)
        self.clear_model_action.setShortcut("Ctrl+W")
        self.clear_model_action.triggered.connect(self._clear_model)
        self.import_obj_action = QtGui.QAction("Import OBJ...", self)
        self.import_obj_action.setShortcut("Ctrl+I")
        self.import_obj_action.triggered.connect(self._import_obj)
        self.import_fbx_action = QtGui.QAction("Import FBX...", self)
        self.import_fbx_action.triggered.connect(self._import_fbx)
        self.import_gltf_action = QtGui.QAction("Import GLB/GLTF...", self)
        self.import_gltf_action.triggered.connect(self._import_gltf)
        self.save_ascii_action = QtGui.QAction("Save ASCII MDL...", self)
        self.save_ascii_action.setShortcut("Ctrl+S")
        self.save_ascii_action.triggered.connect(self._save_ascii_mdl)
        self.export_binary_action = QtGui.QAction("Export Binary MDL...", self)
        self.export_binary_action.setShortcut("Ctrl+M")
        self.export_binary_action.triggered.connect(self._export_mdl_binary)
        self.export_obj_action = QtGui.QAction("Export OBJ...", self)
        self.export_obj_action.setShortcut("Ctrl+E")
        self.export_obj_action.triggered.connect(self._export_obj)
        self.export_fbx_action = QtGui.QAction("Export FBX...", self)
        self.export_fbx_action.triggered.connect(self._export_fbx)
        self.export_gltf_action = QtGui.QAction("Export GLB/GLTF...", self)
        self.export_gltf_action.setShortcut("Ctrl+G")
        self.export_gltf_action.triggered.connect(self._export_gltf)
        self.export_humanoid_action = QtGui.QAction("Export Humanoid Template...", self)
        self.export_humanoid_action.triggered.connect(self._export_humanoid_template)
        self.texture_dir_action = QtGui.QAction("Set Texture Directory...", self)
        self.texture_dir_action.triggered.connect(self._set_texture_dir)
        self.settings_action = QtGui.QAction(self._icon("settings"), "Settings...", self)
        self.settings_action.setShortcut("F2")
        self.settings_action.triggered.connect(self._open_settings_dialog)
        self.autorig_action = QtGui.QAction(self._icon("autorig"), "Auto-Rig Current Model", self)
        self.autorig_action.setShortcut("Ctrl+R")
        self.autorig_action.triggered.connect(self._quick_autorig)
        self.remove_rig_action = QtGui.QAction("Remove Rigging", self)
        self.remove_rig_action.triggered.connect(self._remove_rig)
        self.frame_all_action = QtGui.QAction("Frame All", self)
        self.frame_all_action.setShortcut("F")
        self.frame_all_action.triggered.connect(lambda: self._call_viewport("frame_all"))
        self.reset_camera_action = QtGui.QAction("Reset Camera", self)
        self.reset_camera_action.setShortcut("R")
        self.reset_camera_action.triggered.connect(lambda: self._call_viewport("reset_camera"))
        self.undo_viewport_action = QtGui.QAction("Undo Viewport Edit", self)
        self.undo_viewport_action.setShortcut("Ctrl+Z")
        self.undo_viewport_action.triggered.connect(lambda: self._call_viewport("undo"))
        self.redo_viewport_action = QtGui.QAction("Redo Viewport Edit", self)
        self.redo_viewport_action.setShortcut("Ctrl+Y")
        self.redo_viewport_action.triggered.connect(lambda: self._call_viewport("redo"))
        self.wire_action = QtGui.QAction("Toggle Wireframe", self)
        self.wire_action.setShortcut("W")
        self.wire_action.triggered.connect(lambda: self._click_viewport_button("wire_button"))
        self.bones_action = QtGui.QAction("Toggle Bones", self)
        self.bones_action.setShortcut("B")
        self.bones_action.triggered.connect(lambda: self._click_viewport_button("bones_button"))
        self.texture_action = QtGui.QAction("Toggle Texture", self)
        self.texture_action.setShortcut("T")
        self.texture_action.triggered.connect(lambda: self._click_viewport_button("texture_button"))
        self.uv_action = QtGui.QAction("Open UV Viewer...", self)
        self.uv_action.triggered.connect(self._open_uv_viewer)
        self.diag_action = QtGui.QAction(self._icon("diag"), "Diagnostics...", self)
        self.diag_action.setShortcut("Ctrl+D")
        self.diag_action.triggered.connect(self._show_diagnostics_panel)
        self.info_action = QtGui.QAction("Model Info...", self)
        self.info_action.triggered.connect(self._show_model_info)
        self.refresh_action = QtGui.QAction("Refresh All", self)
        self.refresh_action.setShortcut("F5")
        self.refresh_action.triggered.connect(self._refresh_all)
        self.character_builder_action = QtGui.QAction(self._icon("charbuilder"), "Character Builder (New Window)...", self)
        self.character_builder_action.setShortcut("Ctrl+B")
        self.character_builder_action.triggered.connect(self._open_qt_character_builder_window)
        self.anims_action = QtGui.QAction(self._icon("anims"), "Animation Library", self)
        self.anims_action.setShortcut("Ctrl+A")
        self.anims_action.triggered.connect(lambda: self._show_right_tab("Animation Library"))
        self.retarget_workbench_action = QtGui.QAction(self._icon("anims"), "Animation Retargeting Workbench...", self)
        self.retarget_workbench_action.setShortcut("Ctrl+Shift+A")
        self.retarget_workbench_action.triggered.connect(self._open_animation_retarget_window)
        self.unreal_animator_action = QtGui.QAction(self._icon("anims"), "Unreal Animator...", self)
        self.unreal_animator_action.setShortcut("Ctrl+Shift+U")
        self.unreal_animator_action.triggered.connect(self._open_unreal_animator_window)
        self.modules_action = QtGui.QAction(self._icon("modular"), "Open Module Editor", self)
        self.modules_action.triggered.connect(self._show_modules_tab)
        self.rig_window_action = QtGui.QAction(self._icon("rig"), "Open Rigging Window", self)
        self.rig_window_action.triggered.connect(self._open_rig_window)
        self.texture_tool_action = QtGui.QAction(self._icon("texture"), "Texture Tool...", self)
        self.texture_tool_action.triggered.connect(self._open_texture_tool_window)
        self.blueprint_editor_action = QtGui.QAction(self._icon("library"), "Blueprint Editor...", self)
        self.blueprint_editor_action.triggered.connect(self._open_blueprint_editor_window)
        self.nodes_panel_action = QtGui.QAction(self._icon("skeleton"), "Open Nodes Panel", self)
        self.nodes_panel_action.triggered.connect(lambda: self._show_detachable_panel("nodes"))
        self.twoda_panel_action = QtGui.QAction(self._icon("twoda"), "Open 2DA Browser", self)
        self.twoda_panel_action.triggered.connect(lambda: self._show_detachable_panel("2das"))
        self.resources_panel_action = QtGui.QAction(self._icon("resources"), "Open Resource Browser", self)
        self.resources_panel_action.triggered.connect(lambda: self._show_detachable_panel("resources"))
        self.module_meshes_panel_action = QtGui.QAction(self._icon("props"), "Open Module Meshes", self)
        self.module_meshes_panel_action.triggered.connect(lambda: self._show_detachable_panel("module_meshes"))
        self.set_mdlops_action = QtGui.QAction("Set MDLOps Path...", self)
        self.set_mdlops_action.triggered.connect(self._set_mdlops)
        self.compile_action = QtGui.QAction("Compile ASCII MDL to Binary", self)
        self.compile_action.triggered.connect(self._compile_mdlops)
        self.decompile_action = QtGui.QAction("Decompile Binary MDL", self)
        self.decompile_action.triggered.connect(self._decompile_mdlops)
        self.port_model_action = QtGui.QAction("Port Current Model (K1/K2)...", self)
        self.port_model_action.triggered.connect(self._port_current_model)
        self.generate_module_action = QtGui.QAction("Generate Module Files...", self)
        self.generate_module_action.triggered.connect(self._generate_module_files)
        self.about_module_action = QtGui.QAction("About Module Editor", self)
        self.about_module_action.triggered.connect(self._about_modular)
        self.validate_character_action = QtGui.QAction("Validate Current Character...", self)
        self.validate_character_action.triggered.connect(self._validate_current_character)
        self.ping_scripter_action = QtGui.QAction("Ping GhostScripter (port 7002)...", self)
        self.ping_scripter_action.triggered.connect(lambda: self._ipc_ping("GhostScripter", 7002))
        self.ping_gmodular_action = QtGui.QAction("Ping GModular (port 7003)...", self)
        self.ping_gmodular_action.triggered.connect(lambda: self._ipc_ping("GModular", 7003))
        self.notify_gmodular_action = QtGui.QAction("Notify GModular: Blueprint Saved...", self)
        self.notify_gmodular_action.triggered.connect(self._ipc_notify_saved)
        self.refresh_gmodular_action = QtGui.QAction("Refresh GModular Viewport", self)
        self.refresh_gmodular_action.triggered.connect(self._ipc_refresh_gmodular)

        self.launch_legacy_action = QtGui.QAction("Open Legacy Tk Workbench", self)
        self.launch_legacy_action.triggered.connect(self._launch_legacy_tk)

        self.quit_action = QtGui.QAction("Exit", self)
        self.quit_action.setShortcut("Alt+F4")
        self.quit_action.triggered.connect(self.close)

    def _build_menu(self):
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.open_model_action)
        file_menu.addAction(self.open_ascii_action)
        file_menu.addAction(self.clear_model_action)
        file_menu.addSeparator()
        file_menu.addAction(self.import_obj_action)
        file_menu.addAction(self.import_fbx_action)
        file_menu.addAction(self.import_gltf_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_ascii_action)
        file_menu.addAction(self.export_binary_action)
        file_menu.addAction(self.export_obj_action)
        file_menu.addAction(self.export_fbx_action)
        file_menu.addAction(self.export_gltf_action)
        file_menu.addSeparator()
        file_menu.addAction(self.export_humanoid_action)
        file_menu.addSeparator()
        file_menu.addAction(self.texture_dir_action)
        file_menu.addSeparator()
        file_menu.addAction(self.settings_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)

        model_menu = self.menuBar().addMenu("Model")
        for action in (
            self.autorig_action,
            self.remove_rig_action,
            None,
            self.frame_all_action,
            self.reset_camera_action,
            None,
            self.undo_viewport_action,
            self.redo_viewport_action,
            None,
            self.wire_action,
            self.bones_action,
            self.texture_action,
            None,
            self.uv_action,
            self.info_action,
            self.refresh_action,
        ):
            self._add_menu_action(model_menu, action)

        mdlops_menu = self.menuBar().addMenu("MDLOps")
        mdlops_menu.addAction(self.set_mdlops_action)
        mdlops_menu.addAction(self.compile_action)
        mdlops_menu.addAction(self.decompile_action)

        help_menu = self.menuBar().addMenu("Help")
        about_action = QtGui.QAction("About", self)
        about_action.triggered.connect(lambda: show_about(self))
        format_action = QtGui.QAction("KotOR MDL Format Reference", self)
        format_action.triggered.connect(lambda: show_format_reference(self))
        viewport_controls_action = QtGui.QAction("Viewport Navigation Controls", self)
        viewport_controls_action.triggered.connect(lambda: show_viewport_navigation_reference(self))
        help_menu.addAction(about_action)
        help_menu.addAction(viewport_controls_action)
        help_menu.addAction(format_action)

        modules_menu = self.menuBar().addMenu("Modules")
        modules_menu.addAction(self.modules_action)
        modules_menu.addAction(self.rig_window_action)
        modules_menu.addAction(self.retarget_workbench_action)
        modules_menu.addAction(self.unreal_animator_action)
        modules_menu.addSeparator()
        modules_menu.addAction(self.nodes_panel_action)
        modules_menu.addAction(self.module_meshes_panel_action)
        modules_menu.addAction(self.twoda_panel_action)
        modules_menu.addAction(self.resources_panel_action)
        modules_menu.addSeparator()
        modules_menu.addAction(self.port_model_action)
        modules_menu.addAction(self.generate_module_action)
        modules_menu.addSeparator()
        modules_menu.addAction(self.about_module_action)

        tools_menu = self.menuBar().addMenu("Tools")
        tools_menu.addAction(self.diag_action)
        tools_menu.addAction(self.texture_tool_action)
        tools_menu.addAction(self.blueprint_editor_action)
        tools_menu.addSeparator()
        tools_menu.addAction(self.character_builder_action)
        tools_menu.addSeparator()
        tools_menu.addAction(self.validate_character_action)
        tools_menu.addSeparator()
        tools_menu.addAction(self.launch_legacy_action)

        ipc_menu = self.menuBar().addMenu("IPC")
        server_action = QtGui.QAction("GhostRigger Server (port 7001) - This Program", self)
        server_action.setEnabled(False)
        ipc_menu.addAction(server_action)
        ipc_menu.addSeparator()
        ipc_menu.addAction(self.ping_scripter_action)
        ipc_menu.addAction(self.ping_gmodular_action)
        ipc_menu.addSeparator()
        ipc_menu.addAction(self.notify_gmodular_action)
        ipc_menu.addAction(self.refresh_gmodular_action)
        ipc_menu.addSeparator()
        ipc_info_action = QtGui.QAction("IPC Protocol Info", self)
        ipc_info_action.triggered.connect(lambda: show_ipc_info(self))
        ipc_menu.addAction(ipc_info_action)

    def _build_toolbar(self):
        # The original GhostRigger top chrome is rebuilt as regular Qt widgets
        # so later panels can be swapped in without changing the host frame.
        pass

    def _icon(self, name: str, size: int = 16) -> QtGui.QIcon:
        path = _GUI_DIR / "icons" / f"{name}_{size}.png"
        if path.exists():
            return QtGui.QIcon(str(path))
        fallback = _GUI_DIR / "icons" / f"{name}_24.png"
        return QtGui.QIcon(str(fallback)) if fallback.exists() else QtGui.QIcon()

    def _placeholder_action(self, text: str, shortcut: str = "") -> QtGui.QAction:
        action = QtGui.QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(lambda _checked=False, label=text: self._not_migrated(label))
        return action

    def _add_menu_action(self, menu: QtWidgets.QMenu, action: Optional[QtGui.QAction]):
        if action is None:
            menu.addSeparator()
        else:
            menu.addAction(action)

    def _not_migrated(self, label: str):
        self._log(f"{label} is waiting for its Qt panel migration.", "warning")

    def _make_header(self) -> QtWidgets.QFrame:
        header = QtMatrixPanel(engine=self._matrix_engine, opacity=0.55)
        header.setObjectName("HeaderBar")
        header.setFixedHeight(58)

        layout = QtWidgets.QHBoxLayout(header)
        layout.setContentsMargins(18, 7, 18, 7)
        layout.setSpacing(10)

        logo = QtWidgets.QLabel()
        pix = self._icon("logo", 24).pixmap(24, 24)
        if not pix.isNull():
            logo.setPixmap(pix)
        else:
            logo.setText("//")
            logo.setStyleSheet(f"color:{C['accent']}; font-weight:bold; font-size:16pt;")
        logo.setStyleSheet(logo.styleSheet() + "background:transparent;")
        layout.addWidget(logo)

        title_box = QtWidgets.QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(0)
        title = QtMatrixLabel("GHOSTRIGGER")
        title.setObjectName("GhostTitle")
        subtitle = QtWidgets.QLabel("Odyssey Engine Pipeline  //  KotOR 1 & 2 TSL")
        subtitle.setObjectName("GhostSubtitle")
        subtitle.setStyleSheet("background:transparent;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)
        layout.addStretch(1)

        meta_box = QtWidgets.QVBoxLayout()
        meta_box.setContentsMargins(0, 0, 0, 0)
        meta_box.setSpacing(2)
        self.metrics_label = QtWidgets.QLabel("")
        self.metrics_label.setObjectName("HeaderMeta")
        version = QtWidgets.QLabel(f"v{self.APP_VERSION}")
        version.setObjectName("HeaderMeta")
        ipc = QtWidgets.QLabel("IPC: port 7001 *")
        ipc.setObjectName("HeaderMeta")
        ipc.setStyleSheet(f"color:{C['accent']}; font-size:7pt;")
        for label in (self.metrics_label, version, ipc):
            label.setAlignment(QtCore.Qt.AlignRight)
            label.setStyleSheet(label.styleSheet() + "background:transparent;")
            meta_box.addWidget(label)
        layout.addLayout(meta_box)
        return header

    def _make_command_bar(self) -> QtWidgets.QFrame:
        bar = QtMatrixPanel(engine=self._matrix_engine, opacity=0.35)
        bar.setObjectName("CommandBar")
        bar.setFixedHeight(40)

        layout = QtWidgets.QHBoxLayout(bar)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(5)

        layout.addWidget(self._tool_button("Open  Ctrl+O", self.open_model_action, "open"))
        layout.addWidget(self._tool_button("Auto-Rig  R", self.autorig_action, "autorig", accent=True))
        layout.addWidget(self._tool_button("Character Builder", self.character_builder_action, "charbuilder", accent=True))
        layout.addWidget(self._tool_button("Modules", self.modules_action, "modular"))
        layout.addWidget(self._tool_button("Tex Dir", self.texture_dir_action, "texture"))
        layout.addWidget(self._separator())

        import_button = self._menu_button("Import", "import", [
            self.import_obj_action,
            self.import_fbx_action,
            self.import_gltf_action,
            None,
            self.open_ascii_action,
        ])
        export_button = self._menu_button("Export", "export", [
            self.export_binary_action,
            self.export_obj_action,
            self.export_fbx_action,
            self.export_gltf_action,
            None,
            self.export_humanoid_action,
            None,
            self.save_ascii_action,
            self.compile_action,
        ])
        layout.addWidget(import_button)
        layout.addWidget(export_button)
        layout.addWidget(self._separator())

        self.model_pill = QtWidgets.QLabel("// No model loaded")
        self.model_pill.setObjectName("ModelPill")
        self.model_pill.setMinimumWidth(154)
        self.model_pill.setAlignment(QtCore.Qt.AlignCenter)
        self.model_pill.setToolTip("No model loaded. Ctrl+W clears the current viewport.")
        layout.addWidget(self.model_pill)
        layout.addStretch(1)

        layout.addWidget(self._tool_button("Settings  F2", self.settings_action, "settings", compact=True))
        layout.addWidget(self._separator())
        layout.addWidget(self._tool_button("Anims  Ctrl+A", self.anims_action, "anims", compact=True))
        layout.addWidget(self._tool_button("Diag  Ctrl+D", self.diag_action, "diag", compact=True))
        return bar

    def _tool_button(
        self,
        text: str,
        action: QtGui.QAction,
        icon_name: str = "",
        accent: bool = False,
        compact: bool = False,
    ) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(text)
        if icon_name:
            button.setIcon(self._icon(icon_name, 16))
        button.setProperty("accent", accent)
        button.setProperty("compact", compact)
        button.clicked.connect(action.trigger)
        if action.shortcut():
            button.setToolTip(f"{action.text()} ({action.shortcut().toString()})")
        else:
            button.setToolTip(action.text())
        return button

    def _menu_button(
        self,
        text: str,
        icon_name: str,
        actions: list[Optional[QtGui.QAction]],
    ) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setText(f"{text}  v")
        button.setIcon(self._icon(icon_name, 16))
        button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(button)
        for action in actions:
            self._add_menu_action(menu, action)
        button.setMenu(menu)
        return button

    def _separator(self) -> QtWidgets.QFrame:
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setFrameShadow(QtWidgets.QFrame.Plain)
        sep.setStyleSheet(f"color:{C['border']}; background:{C['border']};")
        sep.setFixedWidth(1)
        return sep

    def _create_detachable_panel(self, key: str, title: str, widget: QtWidgets.QWidget, area) -> QtWidgets.QDockWidget:
        dock = QtWidgets.QDockWidget(title, self)
        dock.setObjectName(f"{key}Dock")
        dock.setWidget(widget)
        dock.setAllowedAreas(QtCore.Qt.AllDockWidgetAreas)
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetClosable
            | QtWidgets.QDockWidget.DockWidgetFloatable
            | QtWidgets.QDockWidget.DockWidgetMovable
        )
        self.addDockWidget(area, dock)
        dock.hide()
        self._detachable_panels[key] = dock
        return dock

    def _show_detachable_panel(self, key: str):
        dock = getattr(self, "_detachable_panels", {}).get(key)
        if dock is None:
            self._not_migrated(key)
            return
        if key == "resources" and getattr(self.resource_panel, "listbox", None) is not None:
            if self.resource_panel.listbox.count() == 0:
                self._populate_resource_panel()
        dock.show()
        dock.setFloating(True)
        width, height = getattr(self, "_detachable_panel_sizes", {}).get(key, (760, 520))
        dock.resize(width, height)
        dock.raise_()
        dock.activateWindow()

    def _build_layout(self):
        central = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(3, 0, 3, 3)
        root.setSpacing(0)
        self.setCentralWidget(central)

        root.addWidget(self._make_header())
        root.addWidget(self._make_command_bar())

        vertical_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        vertical_splitter.setChildrenCollapsible(False)
        vertical_splitter.setHandleWidth(8)
        self.vertical_splitter = vertical_splitter

        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setHandleWidth(8)
        self.main_splitter = main_splitter

        left_tabs = QtWidgets.QTabWidget()
        left_tabs.setUsesScrollButtons(True)
        left_tabs.setElideMode(QtCore.Qt.ElideRight)
        left_tabs.tabBar().setExpanding(False)
        left_tabs.setMinimumWidth(260)
        left_tabs.setMaximumWidth(520)
        left_tabs.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        self.left_tabs = left_tabs

        self.library_panel = QtLibraryPanel(self)
        self.library_panel.autoDetectRequested.connect(self._auto_detect_dirs)
        self.library_panel.scanRequested.connect(self._scan_library)
        self.library_panel.deepScanRequested.connect(self._scan_library)
        self.library_panel.loadRequested.connect(self._start_resource_load)
        self.library_panel.extractRequested.connect(self._extract_library_row)
        self.library_panel.retargetSourceRequested.connect(
            lambda row: self._send_library_row_to_retarget(row, "source")
        )
        self.library_panel.retargetTargetRequested.connect(
            lambda row: self._send_library_row_to_retarget(row, "target")
        )
        self.library_panel.batchRequested.connect(self._batch_library_export)
        self.library_panel.dirsChanged.connect(self._on_library_dirs_changed)
        left_tabs.addTab(self.library_panel, self._icon("library", 16), "Library")

        right_tabs = QtWidgets.QTabWidget()
        right_tabs.setUsesScrollButtons(True)
        right_tabs.setElideMode(QtCore.Qt.ElideRight)
        right_tabs.tabBar().setExpanding(False)
        right_tabs.setMinimumWidth(280)
        right_tabs.setMaximumWidth(560)
        right_tabs.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        self.right_tabs = right_tabs
        self.skeleton_panel = QtSkeletonPanel(self)
        self.properties_panel = QtPropertiesPanel(self, module_browser_enabled=False)
        self.module_geometry_panel = QtPropertiesPanel(self)
        self.module_geometry_panel.set_module_browser_only(True)
        self.skeleton_panel.nodeSelected.connect(self.properties_panel.show_node)
        self.rig_window = QtRigWindow(self)
        self.rig_window.rigActionRequested.connect(self._handle_rig_action)
        self.rig_panel = self.rig_window.panel
        self.texture_tool_window = QtTextureToolWindow(self)
        self.texture_panel = self.texture_tool_window.texture_panel
        self.normal_map_panel = self.texture_tool_window.normal_map_panel
        self.diagnostics_window = QtDiagnosticsWindow(self._get_model, self)
        self.diagnostics_panel = self.diagnostics_window.panel
        self.animations_panel = QtAnimationsPanel(self)
        self.animations_panel.animationSelected.connect(self._handle_animation_selected)
        self.animations_panel.animationActionRequested.connect(self._handle_animation_action)
        self.animations_panel.seekRequested.connect(self._handle_animation_seek)
        self.animation_library_panel = QtAnimationLibraryPanel(self)
        self.animation_library_panel.libraryActionRequested.connect(self._handle_animation_library_action)
        self.animation_library_combined_panel = QtAnimationLibraryCombinedPanel(
            self.animations_panel,
            self.animation_library_panel,
            self,
        )
        self.animation_retarget_window = QtAnimationRetargetWindow(self)
        self.animation_retarget_window.set_navigation_profile(
            self.settings_data.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
        )
        self.animation_retarget_window.sourceCurrentRequested.connect(self._retarget_set_source_current)
        self.animation_retarget_window.targetCurrentRequested.connect(self._retarget_set_target_current)
        self.animation_retarget_window.sourceLibraryRequested.connect(
            lambda: self._retarget_select_library_model("source")
        )
        self.animation_retarget_window.targetLibraryRequested.connect(
            lambda: self._retarget_select_library_model("target")
        )
        self.animation_retarget_window.previewRequested.connect(self._retarget_preview)
        self.animation_retarget_window.applyRequested.connect(self._retarget_apply)
        self.animation_retarget_window.stopRequested.connect(self._retarget_stop)
        self.animation_retarget_panel = self.animation_retarget_window
        self.unreal_animator_window = QtUnrealAnimatorWindow(self)
        self.unreal_animator_window.set_navigation_profile(
            self.settings_data.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
        )
        self.unreal_animator_window.sourceLoadRequested.connect(self._unreal_load_supermodel)
        self.unreal_animator_window.reloadCodeRequested.connect(self._reload_unreal_animator_window)
        self._unreal_source_row: Optional[dict] = None
        self._unreal_source_game = ""
        self.twoda_panel = QtTwoDaBrowserPanel(self)
        self.twoda_panel.refreshRequested.connect(self._refresh_twoda_panel)
        self.twoda_panel.tableSelected.connect(self._load_twoda_table)
        self.resource_panel = QtResourceBrowserPanel(self)
        self.resource_panel.scanRequested.connect(self._populate_resource_panel)
        self.resource_panel.resourceSelected.connect(self._preview_resource_row)
        self.resource_panel.resourceActivated.connect(self._activate_resource_row)
        self.modular_panel = QtModularModePanel(self)
        self.modular_panel.moduleActionRequested.connect(self._handle_module_action)
        self.blueprint_window = QtBlueprintEditorWindow(self)
        self.blueprint_panel = self.blueprint_window.panel
        self._detachable_panels: dict[str, QtWidgets.QDockWidget] = {}
        self._detachable_panel_sizes = {
            "nodes": (620, 700),
            "module_meshes": (620, 720),
            "2das": (980, 640),
            "resources": (980, 640),
        }
        self._create_detachable_panel("nodes", "Nodes", self.skeleton_panel, QtCore.Qt.LeftDockWidgetArea)
        self._create_detachable_panel("module_meshes", "Module Meshes", self.module_geometry_panel, QtCore.Qt.RightDockWidgetArea)
        self._create_detachable_panel("2das", "2DA Browser", self.twoda_panel, QtCore.Qt.LeftDockWidgetArea)
        self._create_detachable_panel("resources", "Resource Browser", self.resource_panel, QtCore.Qt.LeftDockWidgetArea)
        left_tabs.addTab(self.modular_panel, self._icon("modular", 16), "Modules")
        main_splitter.addWidget(left_tabs)

        self.viewport = QtMainViewportWidget(self)
        self.viewport.set_navigation_profile(
            self.settings_data.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
        )
        self.viewport.setMinimumWidth(420)
        self.viewport.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.viewport_label = self.viewport.canvas
        self.skeleton_panel.nodeSelected.connect(self.viewport.set_selected_node)
        self.viewport.nodeSelected.connect(self.properties_panel.show_node)
        self.viewport.nodeSelected.connect(self.module_geometry_panel.show_node)
        self.viewport.nodeSelected.connect(self.module_geometry_panel.select_module_mesh)
        self.viewport.meshSelectionChanged.connect(self.module_geometry_panel.select_module_meshes)
        self.viewport.nodeMoved.connect(self.properties_panel.show_node)
        self.viewport.nodeMoved.connect(self.module_geometry_panel.show_node)
        self.viewport.meshVisibilityChanged.connect(self.module_geometry_panel.refresh_module_mesh_rows)
        self.viewport.gpuUploadProgress.connect(self._on_viewport_gpu_upload_progress)
        self.module_geometry_panel.moduleMeshesSelected.connect(self.viewport.set_selected_meshes)
        self.module_geometry_panel.moduleMeshVisibilityChanged.connect(self.viewport.refresh_view)
        self.module_geometry_panel.moduleMeshesWindowRequested.connect(lambda: self._show_detachable_panel("module_meshes"))
        self.properties_panel.positionApplied.connect(
            lambda node, _x, _y, _z: self.viewport.refresh_node_transform(node)
        )
        main_splitter.addWidget(self.viewport)

        right_tabs.addTab(self.properties_panel, self._icon("props", 16), "Properties")
        right_tabs.addTab(self.animation_library_combined_panel, self._icon("anims", 16), "Animation Library")
        main_splitter.addWidget(right_tabs)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)
        main_splitter.setSizes([420, 760, 380])
        vertical_splitter.addWidget(main_splitter)

        self.log_panel = QtLogPanel(self)
        self.log_panel.setMinimumHeight(96)
        self._configure_python_terminal_context()
        vertical_splitter.addWidget(self.log_panel)
        vertical_splitter.setStretchFactor(0, 1)
        vertical_splitter.setStretchFactor(1, 0)
        vertical_splitter.setSizes([720, 240])
        root.addWidget(vertical_splitter, 1)

        # Compatibility placeholders for the already-migrated loading helpers.
        self.k1_dir_edit = QtWidgets.QLineEdit(str(self.settings_data.get("k1_dir") or ""))
        self.k2_dir_edit = QtWidgets.QLineEdit(str(self.settings_data.get("k2_dir") or ""))
        self.scan_button = QtWidgets.QPushButton("Scan")
        self.library_list = QtWidgets.QListWidget()
        self.library_filter = QtWidgets.QLineEdit()
        self.props_text = QtWidgets.QTextEdit()

    @QtCore.Slot(str, str)
    def _on_library_dirs_changed(self, k1_dir: str, k2_dir: str):
        self.k1_dir_edit.setText(k1_dir)
        self.k2_dir_edit.setText(k2_dir)
        self.settings_data["k1_dir"] = k1_dir
        self.settings_data["k2_dir"] = k2_dir
        try:
            save_settings(self.settings_path, self.settings_data)
        except Exception as exc:
            self._log(f"Could not save game directories: {exc}", "warning")
        self._resource_manager = None
        self._resource_manager_dirs = ("", "")
        self.library_panel.set_status("Game directories updated")
        self._log("Game directories updated. Run Scan to refresh the library.", "success")

    def _show_progress_toast(self, title: str, detail: str):
        if self._progress_toast is None:
            self._progress_toast = QtProgressToast(self)
        self._progress_toast.show_busy(title, detail)

    def _update_progress_toast(self, title: str, detail: str, value: int, total: int):
        if self._progress_toast is None:
            self._progress_toast = QtProgressToast(self)
        self._progress_toast.update_progress(title, detail, value, total)

    def _finish_progress_toast(self, title: str, detail: str):
        if self._progress_toast is None:
            self._progress_toast = QtProgressToast(self)
        self._progress_toast.finish(title, detail)

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
            self._finish_progress_toast("Auto-detect failed", "Check the output log for details.")
            self._log(f"Auto-detect failed:\n{error}", "error")
            return
        if not (k1_dir or k2_dir):
            self._finish_progress_toast("No installs found", "Set game directories manually to scan the library.")
            self.library_panel.set_status("No KotOR directories found")
            self._log("No KotOR installation found automatically.", "warning")
            return
        self._on_library_dirs_changed(k1_dir or self.k1_dir_edit.text().strip(), k2_dir or self.k2_dir_edit.text().strip())
        self._scan_library()

    def _auto_detect_dirs_on_startup(self):
        if self._auto_detect_worker_is_running() or self._scan_worker_is_running():
            return
        self._auto_detect_dirs()

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

    def _extract_model_resource(self, row: dict, out_dir: str) -> list[str]:
        from src.gui.qt_lib.rendering.viewport_core import _is_tpc_data

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
            from src.core.kotor_loader import load_model_from_bytes

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

    def _build_statusbar(self):
        self.statusBar().showMessage("Ready")

    def _require_model(self, action: str):
        if self._current_model is None:
            QtWidgets.QMessageBox.information(self, action, "Load or import a model first.")
            return None
        return self._current_model

    def _model_worker_is_running(self) -> bool:
        thread = self._worker_thread
        if thread is None:
            return False
        try:
            return thread.isRunning()
        except RuntimeError:
            self._worker_thread = None
            self._model_worker = None
            return False

    def _scan_worker_is_running(self) -> bool:
        thread = self._scan_thread
        if thread is None:
            return False
        try:
            return thread.isRunning()
        except RuntimeError:
            self._scan_thread = None
            self._scan_worker = None
            return False

    def _auto_detect_worker_is_running(self) -> bool:
        thread = self._auto_detect_thread
        if thread is None:
            return False
        try:
            return thread.isRunning()
        except RuntimeError:
            self._auto_detect_thread = None
            self._auto_detect_worker = None
            return False

    def _set_model_internal(self, model, path: str = ""):
        if model is None:
            old_model = self._current_model
            if old_model is not None:
                try:
                    from src.gui.qt_lib.rendering.gpu_renderer import clear_prebuilt_static_gpu_model_data

                    clear_prebuilt_static_gpu_model_data(old_model)
                except Exception:
                    log.debug("Model RAM buffer cleanup failed", exc_info=True)
            self._pending_gpu_upload_model_id = 0
            self._pending_gpu_upload_total = 0
            self._animation_timer.stop()
            self._retarget_timer.stop()
            self._animation_engine = None
            self._animation_last_tick = None
            self._retarget_engine = None
            self._retarget_target_model = None
            self._retarget_last_tick = None
            self._current_model = None
            self._model_path = ""
            self.model_pill.setText("// No model loaded")
            self.model_pill.setToolTip("No model loaded. Ctrl+W clears the current viewport.")
            self.statusBar().showMessage("Ready")
            if hasattr(self, "viewport"):
                self.viewport.set_model(None)
            if hasattr(self, "skeleton_panel"):
                self.skeleton_panel.load_model(None)
            if hasattr(self, "properties_panel"):
                self.properties_panel.show_model(None)
            if hasattr(self, "module_geometry_panel"):
                self.module_geometry_panel.show_model(None)
            if hasattr(self, "animations_panel"):
                self.animations_panel.load_model(None)
            if hasattr(self, "animation_retarget_panel"):
                self.animation_retarget_panel.set_target_model(None)
            if hasattr(self, "diagnostics_panel"):
                self.diagnostics_panel.run_diagnostics(None)
            self.props_text.clear()
            return
        self._on_model_loaded(model, path or getattr(model, "name", "model"), "")

    def _pick_export_game_version(self) -> Optional[str]:
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Export Target Game")
        box.setText("Choose the target game version for this export.")
        k1_button = box.addButton("K1", QtWidgets.QMessageBox.AcceptRole)
        k2_button = box.addButton("K2", QtWidgets.QMessageBox.AcceptRole)
        box.addButton(QtWidgets.QMessageBox.Cancel)
        box.setDefaultButton(k1_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is k1_button:
            return "K1"
        if clicked is k2_button:
            return "K2"
        return None

    def _game_version(self):
        from src.core.model_data import GameVersion

        default_game = str(self.settings_data.get("default_game") or "K1").upper()
        return GameVersion.K2 if default_game == "K2" else GameVersion.K1

    def _get_tex_cache_for_export(self):
        return None

    def _call_viewport(self, method_name: str):
        viewport = getattr(self, "viewport", None)
        method = getattr(viewport, method_name, None)
        if method is None:
            self._not_migrated(method_name)
            return
        method()

    def _click_viewport_button(self, button_name: str):
        viewport = getattr(self, "viewport", None)
        button = getattr(viewport, button_name, None)
        if button is None:
            self._not_migrated(button_name)
            return
        button.click()

    def _clear_model(self):
        self._set_model_internal(None)
        self._finish_progress_toast("Model cleared", "GPU buffers and RAM-side mesh buffers were released.")
        self._log("Model cleared.", "info")

    def _set_texture_dir(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Texture Directory",
            self._texture_dir or str(self.app_root),
        )
        if not directory:
            return
        self._texture_dir = directory
        self._log(f"Texture dir -> {Path(directory).name}", "success")
        self._refresh_all()

    def _refresh_all(self):
        model = self._current_model
        if hasattr(self, "viewport"):
            self._configure_viewport_resources()
            self.viewport.load_model(model, self._texture_dir)
        if hasattr(self, "skeleton_panel"):
            self.skeleton_panel.load_model(model)
        if hasattr(self, "properties_panel"):
            self.properties_panel.show_model(model)
        if hasattr(self, "module_geometry_panel"):
            self.module_geometry_panel.show_model(model)
        if hasattr(self, "animations_panel"):
            self.animations_panel.load_model(model)
        if hasattr(self, "animation_retarget_panel"):
            self.animation_retarget_panel.set_texture_dir(self._texture_dir)
            game = (self._current_game or self._infer_game_from_model(model)).upper()
            self._retarget_mapping_report = None
            if self._supports_animation_retarget_target(model):
                mgr = self._get_resource_manager()
                if mgr is not None:
                    self.animation_retarget_panel.set_target_resource_context(mgr, game)
                self._retarget_target_model = model
                self.animation_retarget_panel.set_target_model(model, game)
            else:
                self._retarget_target_model = None
                self.animation_retarget_panel.set_target_model(None, game)
        self._animation_engine = None
        self._animation_timer.stop()
        self._animation_last_tick = None
        self._retarget_timer.stop()
        self._retarget_engine = None
        self._retarget_last_tick = None
        if hasattr(self, "diagnostics_panel"):
            self.diagnostics_panel.run_diagnostics(model)
        self.statusBar().showMessage("Refreshed")
        self._log("Panels refreshed.", "info")

    def _show_model_info(self):
        model = self._require_model("Model Info")
        if model is None:
            return
        mesh_nodes = model.mesh_nodes() if hasattr(model, "mesh_nodes") else []
        bone_nodes = model.bone_nodes() if hasattr(model, "bone_nodes") else []
        textures = model.texture_list() if hasattr(model, "texture_list") else []
        info = "\n".join(
            [
                f"Name:       {getattr(model, 'name', '')}",
                f"Game:       {getattr(getattr(model, 'game_version', ''), 'name', getattr(model, 'game_version', ''))}",
                f"Supermodel: {getattr(model, 'supermodel', '')}",
                f"Class:      {getattr(model, 'classification', '')}",
                f"Nodes:      {model.node_count() if hasattr(model, 'node_count') else 0}",
                f"Mesh nodes: {len(mesh_nodes)}",
                f"Bone nodes: {len(bone_nodes)}",
                f"Animations: {len(getattr(model, 'animations', []) or [])}",
                f"Textures:   {', '.join(textures) or '(none)'}",
                f"BB min:     {getattr(model, 'bb_min', '')}",
                f"BB max:     {getattr(model, 'bb_max', '')}",
                f"Radius:     {getattr(model, 'radius', '')}",
            ]
        )
        QtWidgets.QMessageBox.information(self, "Model Info", info)

    def _run_diagnostics_popup(self):
        if hasattr(self, "diagnostics_panel"):
            self.diagnostics_panel.run_diagnostics(self._current_model)
            content = self.diagnostics_panel.text.toPlainText()
        else:
            content = "No diagnostics panel available."
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Diagnostics")
        dialog.resize(720, 520)
        layout = QtWidgets.QVBoxLayout(dialog)
        text = QtWidgets.QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(content or "No diagnostics available.")
        layout.addWidget(text, 1)
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button, 0, QtCore.Qt.AlignRight)
        dialog.exec()

    def _show_diagnostics_panel(self):
        window = getattr(self, "diagnostics_window", None)
        if window is None:
            self._not_migrated("Diagnostics")
            return
        window.run_diagnostics(self._current_model)
        window.show()
        window.raise_()
        window.activateWindow()

    def _configure_python_terminal_context(self) -> None:
        terminal = getattr(getattr(self, "log_panel", None), "terminal", None)
        if terminal is None:
            return
        terminal.set_context(
            window=self,
            main_window=self,
            viewport=lambda: getattr(self, "viewport", None),
            model=self._terminal_model,
            selected_model=self._terminal_model,
            animation_names=self._terminal_animation_names,
            select_animation=self._terminal_select_animation,
            play_animation=self._terminal_play_animation,
            stop_animation=self._terminal_stop_animation,
            seek_animation=self._terminal_seek_animation,
            override_animation=self._terminal_override_animation,
        )

    def _terminal_model(self):
        return getattr(self, "_current_model", None)

    def _terminal_animation_names(self) -> list[str]:
        model = self._terminal_model()
        return [
            str(getattr(anim, "name", anim))
            for anim in (getattr(model, "animations", []) or [])
        ] if model is not None else []

    def _terminal_select_animation(self, anim_name: str) -> bool:
        anim_name = str(anim_name or "")
        if not anim_name or not hasattr(self, "animations_panel"):
            return False
        ok = self.animations_panel.select_animation(anim_name)
        if ok:
            self._show_right_tab("Animation Library")
        return ok

    def _terminal_play_animation(self, anim_name: str = "", loop: Optional[bool] = None) -> str:
        if loop is not None:
            self._animation_loop = bool(loop)
        anim_name = str(anim_name or "")
        if not anim_name and hasattr(self, "animations_panel"):
            anim_name = self.animations_panel.selected_animation()
        if anim_name:
            self._terminal_select_animation(anim_name)
        self._handle_animation_action("Play", anim_name)
        return anim_name

    def _terminal_stop_animation(self) -> None:
        self._handle_animation_action("Stop", "")

    def _terminal_seek_animation(self, percent: int | float) -> None:
        self._handle_animation_seek(int(percent))

    def _terminal_override_animation(
        self,
        target_name: str,
        source_name: str = "",
        source_model=None,
    ) -> str:
        import copy

        model = self._terminal_model()
        if model is None:
            raise RuntimeError("No selected model is loaded.")
        target_name = str(target_name or "").strip()
        if not target_name:
            raise ValueError("target_name is required.")
        source_model = source_model or model
        if not source_name and hasattr(self, "animations_panel"):
            source_name = self.animations_panel.selected_animation()
        source_name = str(source_name or target_name).strip()
        source_anim = next(
            (
                anim for anim in (getattr(source_model, "animations", []) or [])
                if str(getattr(anim, "name", "")).lower() == source_name.lower()
            ),
            None,
        )
        if source_anim is None:
            raise ValueError(f"Source animation not found: {source_name}")
        replacement = copy.deepcopy(source_anim)
        replacement.name = target_name
        animations = list(getattr(model, "animations", []) or [])
        for index, anim in enumerate(animations):
            if str(getattr(anim, "name", "")).lower() == target_name.lower():
                animations[index] = replacement
                break
        else:
            animations.append(replacement)
        model.animations = animations
        if hasattr(self, "animations_panel"):
            self.animations_panel.load_model(model, select_name=target_name)
        self._populate_animation_library_from_current_model()
        self._show_right_tab("Animation Library")
        self._log(f"Animation override: {source_name} -> {target_name}", "success")
        return target_name

    def _open_texture_tool_window(self):
        window = getattr(self, "texture_tool_window", None)
        if window is None:
            self._not_migrated("Texture Tool")
            return
        window.show()
        window.raise_()
        window.activateWindow()

    def _open_blueprint_editor_window(self):
        window = getattr(self, "blueprint_window", None)
        if window is None:
            self._not_migrated("Blueprint Editor")
            return
        window.show()
        window.raise_()
        window.activateWindow()

    def _quick_autorig(self):
        model = self._require_model("Auto-Rig")
        if model is None:
            return
        try:
            from src.autorig.auto_rigger import AutoRigger

            rigged = AutoRigger().rig_model(model, template="humanoid")
            self._set_model_internal(rigged, self._model_path)
            self._log("Auto-rig applied.", "success")
            if hasattr(self, "rig_panel"):
                self.rig_panel.status_label.setText("Auto-rig applied.")
        except Exception as exc:
            self._log(f"Auto-rig error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Auto-Rig Error", str(exc))

    def _remove_rig(self):
        model = self._require_model("Remove Rigging")
        if model is None:
            return
        try:
            from src.core.model_data import NodeFlags

            for node in model.mesh_nodes() if hasattr(model, "mesh_nodes") else []:
                node.flags &= ~int(NodeFlags.SKIN)
                node.skin_data = []
                node.bone_map = []
            if getattr(model, "root_node", None):
                model.root_node.children = [
                    child for child in model.root_node.children if getattr(child, "is_mesh", False)
                ]
            self._set_model_internal(model, self._model_path)
            self._log("Rigging removed.", "success")
            if hasattr(self, "rig_panel"):
                self.rig_panel.status_label.setText("Rigging removed.")
        except Exception as exc:
            self._log(f"Remove rigging error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Remove Rigging Error", str(exc))

    def _clear_skeleton(self):
        model = self._require_model("Clear Skeleton")
        if model is None:
            return
        if not getattr(model, "root_node", None):
            QtWidgets.QMessageBox.warning(self, "Clear Skeleton", "No root node found.")
            return
        if QtWidgets.QMessageBox.question(
            self,
            "Clear Skeleton",
            "Remove all bone/dummy nodes and skin weights from this model?\n\nMesh nodes will be re-parented to the root.",
        ) != QtWidgets.QMessageBox.Yes:
            return
        try:
            from src.core.model_data import NodeFlags

            root = model.root_node
            mesh_nodes = [node for node in model.all_nodes() if getattr(node, "is_mesh", False)]
            for node in mesh_nodes:
                node.flags &= ~int(NodeFlags.SKIN)
                node.skin_data = []
                node.bone_map = []
                if hasattr(node, "bone_map_floats"):
                    node.bone_map_floats = []
                node.parent = root
                node.position = (0.0, 0.0, 0.0)
            root.children = mesh_nodes
            self._set_model_internal(model, self._model_path)
            self._log(f"Skeleton cleared: {len(mesh_nodes)} mesh nodes remain at root.", "success")
            if hasattr(self, "rig_panel"):
                self.rig_panel.status_label.setText(f"Skeleton cleared: {len(mesh_nodes)} mesh nodes")
        except Exception as exc:
            self._log(f"Clear skeleton error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Clear Skeleton Error", str(exc))

    def _show_weight_stats(self):
        model = self._require_model("Weight Stats")
        if model is None:
            return
        try:
            from src.autorig.auto_rigger import AutoRigger

            stats = AutoRigger().get_weight_stats(model)
            if not stats:
                QtWidgets.QMessageBox.information(self, "Weight Stats", "No rigged nodes found. Run Auto-Rig first.")
                return
            lines = []
            for node_name, data in stats.items():
                lines.append(f"-- {node_name} --")
                lines.append(
                    f"  verts={data['total_verts']}  avg_infl={data['avg_influences']:.2f}  "
                    f"max_infl={data['max_influences']}  zero={data['zero_weight_verts']}"
                )
                lines.append("  Top bones:")
                for bone_name, total_w in sorted(data["bone_usage"].items(), key=lambda item: -item[1])[:8]:
                    bar = "#" * int(total_w / max(data["total_verts"], 1) * 20)
                    lines.append(f"    {bone_name:<16} {bar}")
                lines.append("")
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("Weight Statistics")
            dialog.resize(560, 420)
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
            self._log(f"Weight stats error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Weight Stats", str(exc))

    def _handle_rig_action(self, action: str):
        if action == "Auto-Rig Model":
            self._quick_autorig()
        elif action == "Remove Rigging":
            self._remove_rig()
        elif action == "Clear Skeleton":
            self._clear_skeleton()
        elif action == "Weight Stats":
            self._show_weight_stats()
        else:
            self._log(f"{action} is waiting for its Qt behavior migration.", "warning")

    def _import_obj(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import OBJ",
            str(Path(self.settings_data.get("last_import") or self.app_root)),
            "OBJ files (*.obj);;All files (*.*)",
        )
        if path:
            self._import_obj_from_path(path)

    def _import_obj_from_path(self, path: str):
        try:
            from src.converters.mesh_converter import OBJImporter

            model = OBJImporter().import_file(path, game_version=self._game_version())
            self._texture_dir = str(Path(path).parent)
            self._set_model_internal(model, path)
            self._log(f"Imported OBJ: {Path(path).name}", "success")
        except Exception as exc:
            self._log(f"OBJ import error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "OBJ Import Error", str(exc))

    def _import_fbx(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import FBX",
            str(Path(self.settings_data.get("last_import") or self.app_root)),
            "FBX files (*.fbx);;OBJ files (*.obj);;All files (*.*)",
        )
        if not path:
            return
        if path.lower().endswith(".obj"):
            self._import_obj_from_path(path)
            return
        try:
            from src.converters.mesh_converter import FBXImporter

            model = FBXImporter().import_file(path, game_version=self._game_version())
            if model is None:
                raise RuntimeError("FBX import failed. Install pyassimp, assimp-py, or trimesh.")
            self._texture_dir = str(Path(path).parent)
            self._set_model_internal(model, path)
            self._log(f"Imported FBX: {Path(path).name}", "success")
        except Exception as exc:
            self._log(f"FBX import error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "FBX Import Error", str(exc))

    def _import_gltf(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import GLB / GLTF",
            str(Path(self.settings_data.get("last_import") or self.app_root)),
            "GLB/GLTF files (*.glb *.gltf);;All files (*.*)",
        )
        if not path:
            return
        try:
            from src.converters.mesh_converter import GLTFImporter

            model = GLTFImporter().import_file(path, game_version=self._game_version())
            if model is None:
                raise RuntimeError("GLTF import failed. Install pygltflib or trimesh.")
            self._texture_dir = str(Path(path).parent)
            self._set_model_internal(model, path)
            self._log(f"Imported GLB/GLTF: {Path(path).name}", "success")
        except Exception as exc:
            self._log(f"GLTF import error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "GLTF Import Error", str(exc))

    def _save_ascii_mdl(self):
        model = self._require_model("Save ASCII MDL")
        if model is None:
            return
        chosen_gv = self._pick_export_game_version()
        if not chosen_gv:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save ASCII MDL",
            f"{getattr(model, 'name', 'model')}.mdl",
            "MDL files (*.mdl);;All files (*.*)",
        )
        if not path:
            return
        try:
            from src.core.mdl_parser import MDLAsciiWriter
            from src.core.model_data import GameVersion

            mdl = copy.deepcopy(model)
            mdl.game_version = GameVersion.K2 if chosen_gv == "K2" else GameVersion.K1
            MDLAsciiWriter().write(mdl, path)
            self._log(f"Saved ASCII MDL ({chosen_gv}) -> {Path(path).name}", "success")
        except Exception as exc:
            self._log(f"Save error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Save Error", str(exc))

    def _export_mdl_binary(self):
        model = self._require_model("Export Binary MDL")
        if model is None:
            return
        chosen_gv = self._pick_export_game_version()
        if not chosen_gv:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Binary MDL",
            f"{getattr(model, 'name', 'model')}.mdl",
            "MDL files (*.mdl);;All files (*.*)",
        )
        if not path:
            return
        try:
            from src.core.mdl_writer import MDLBinaryWriter
            from src.core.model_data import GameVersion

            mdl = copy.deepcopy(model)
            mdl.game_version = GameVersion.K2 if chosen_gv == "K2" else GameVersion.K1
            mdx_path = str(Path(path).with_suffix(".mdx"))
            mdl_bytes, mdx_bytes = MDLBinaryWriter().write(mdl)
            Path(path).write_bytes(mdl_bytes)
            Path(mdx_path).write_bytes(mdx_bytes)
            self._log(
                f"Exported binary MDL ({chosen_gv}) -> {Path(path).name} (+ {Path(mdx_path).name})",
                "success",
            )
        except Exception as exc:
            self._log(f"Binary MDL export error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Export Error", str(exc))

    def _export_obj(self):
        model = self._require_model("Export OBJ")
        if model is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export OBJ",
            f"{getattr(model, 'name', 'model')}.obj",
            "OBJ files (*.obj);;All files (*.*)",
        )
        if not path:
            return
        try:
            from src.converters.mesh_converter import OBJExporter

            OBJExporter().export(model, path, tex_cache=self._get_tex_cache_for_export(), export_rigging=True)
            self._log(f"Exported OBJ -> {Path(path).name}", "success")
        except Exception as exc:
            self._log(f"OBJ export error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Export Error", str(exc))

    def _export_fbx(self):
        model = self._require_model("Export FBX")
        if model is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export FBX",
            f"{getattr(model, 'name', 'model')}.fbx",
            "FBX files (*.fbx);;OBJ files (*.obj);;All files (*.*)",
        )
        if not path:
            return
        try:
            from src.converters.mesh_converter import FBXExporter

            ok = FBXExporter().export(
                model,
                path,
                tex_cache=self._get_tex_cache_for_export(),
                export_rigging=True,
                base_skeleton_model=getattr(self, "_base_skeleton_model", None),
            )
            level = "success" if ok else "warning"
            msg = f"Exported FBX -> {Path(path).name}" if ok else "FBX export fell back or failed; see log."
            self._log(msg, level)
        except Exception as exc:
            self._log(f"FBX export error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Export Error", str(exc))

    def _export_gltf(self):
        model = self._require_model("Export GLB/GLTF")
        if model is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export GLB / GLTF",
            f"{getattr(model, 'name', 'model')}.glb",
            "GLB binary (*.glb);;GLTF JSON (*.gltf);;All files (*.*)",
        )
        if not path:
            return
        try:
            from src.converters.mesh_converter import GLTFExporter

            binary = path.lower().endswith(".glb")
            ok = GLTFExporter().export(
                model,
                path,
                binary=binary,
                tex_cache=self._get_tex_cache_for_export(),
                export_rigging=True,
            )
            if not ok:
                raise RuntimeError("GLTF export failed. Install pygltflib or check the log.")
            self._log(f"Exported {'GLB' if binary else 'GLTF'} -> {Path(path).name}", "success")
        except Exception as exc:
            self._log(f"GLTF export error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Export Error", str(exc))

    def _export_humanoid_template(self):
        chosen_gv = self._pick_export_game_version()
        if not chosen_gv:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Universal Humanoid Template",
            f"gr_humanoid_template_{chosen_gv.lower()}.mdl",
            "MDL files (*.mdl);;All files (*.*)",
        )
        if not path:
            return
        try:
            from src.core.template_builder import build_humanoid_template, save_template_manifest
            from src.core.mdl_writer import MDLBinaryWriter

            model = build_humanoid_template(game_version=chosen_gv, name=Path(path).stem)
            mdx_path = str(Path(path).with_suffix(".mdx"))
            mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
            Path(path).write_bytes(mdl_bytes)
            Path(mdx_path).write_bytes(mdx_bytes)
            manifest_path = save_template_manifest(model, str(Path(path).parent))
            self._log(
                f"Exported Humanoid Template ({chosen_gv}) -> {Path(path).name} (+ {Path(mdx_path).name})",
                "success",
            )
            self._log(f"Manifest -> {Path(manifest_path).name}", "info")
            if QtWidgets.QMessageBox.question(
                self,
                "Template Exported",
                "Load the exported template into the viewer now?",
            ) == QtWidgets.QMessageBox.Yes:
                self._set_model_internal(model, path)
        except Exception as exc:
            self._log(f"Template export error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Export Error", str(exc))

    def _find_mdlops(self) -> str:
        configured = str(self.settings_data.get("mdlops_path") or "")
        guesses = [
            configured,
            str(self.app_root / "mdlops.pl"),
            str(self.app_root / "tools" / "mdlops.pl"),
        ]
        for candidate in guesses:
            if candidate and Path(candidate).exists():
                return candidate
        return ""

    def _set_mdlops(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Locate mdlops.pl or mdlops.exe",
            str(self.app_root),
            "MDLOps (*.pl *.exe *.py);;All files (*.*)",
        )
        if not path:
            return
        self.settings_data["mdlops_path"] = path
        try:
            save_settings(self.settings_path, self.settings_data)
        except Exception as exc:
            self._log(f"Could not save MDLOps setting: {exc}", "warning")
        self._log(f"MDLOps set: {path}", "success")

    def _mdlops_command(self, mdlops: str, game_flag: str, mode_flag: str, path: str) -> list[str]:
        if mdlops.lower().endswith(".pl"):
            return ["perl", mdlops, game_flag, mode_flag, path]
        return [mdlops, game_flag, mode_flag, path]

    def _compile_mdlops(self):
        model = self._require_model("Compile ASCII MDL to Binary")
        if model is None:
            return
        work_dir = Path(self.settings_data.get("work_dir") or self.app_root)
        work_dir.mkdir(parents=True, exist_ok=True)
        ascii_path = work_dir / f"{getattr(model, 'name', 'model')}.mdl"
        try:
            from src.core.mdl_parser import MDLAsciiWriter

            MDLAsciiWriter().write(model, str(ascii_path))
        except Exception as exc:
            self._log(f"Could not write ASCII MDL: {exc}", "error")
            return

        mdlops = self._find_mdlops()
        if not mdlops:
            QtWidgets.QMessageBox.information(
                self,
                "MDLOps",
                "MDLOps was not found. Set the path via MDLOps > Set MDLOps Path.\n\n"
                f"ASCII MDL has been saved to:\n{ascii_path}",
            )
            return
        game_name = getattr(getattr(model, "game_version", ""), "name", str(getattr(model, "game_version", "K1")))
        game_flag = "-k2" if game_name.upper() == "K2" else "-k1"
        cmd = self._mdlops_command(mdlops, game_flag, "-c", str(ascii_path))
        self._run_mdlops(cmd, work_dir)

    def _decompile_mdlops(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select binary MDL to decompile",
            str(Path(self._model_path).parent if self._model_path else self.app_root),
            "MDL files (*.mdl);;All files (*.*)",
        )
        if not path:
            return
        mdlops = self._find_mdlops()
        if not mdlops:
            QtWidgets.QMessageBox.information(
                self,
                "MDLOps",
                "Set the MDLOps path first with MDLOps > Set MDLOps Path.",
            )
            return
        cmd = self._mdlops_command(mdlops, "-k1", "-d", path)
        self._run_mdlops(cmd, Path(path).parent)

    def _run_mdlops(self, cmd: list[str], cwd: Path):
        self._log(f"Running MDLOps: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(cwd))
            if result.stdout:
                self._log(result.stdout.strip())
            if result.stderr:
                self._log(result.stderr.strip(), "warning")
            if result.returncode == 0:
                self._log("MDLOps operation complete.", "success")
            else:
                self._log(f"MDLOps exited with code {result.returncode}", "warning")
        except FileNotFoundError:
            self._log("'perl' was not found. Install Perl or use the Windows MDLOps exe.", "error")
        except subprocess.TimeoutExpired:
            self._log("MDLOps timed out.", "error")
        except Exception as exc:
            self._log(f"MDLOps error: {exc}", "error")

    def _port_current_model(self):
        model = self._require_model("Port Current Model")
        if model is None:
            return
        current = getattr(getattr(model, "game_version", ""), "name", str(getattr(model, "game_version", "K1"))).upper()
        target = "K2" if current == "K1" else "K1"
        if QtWidgets.QMessageBox.question(
            self,
            "Port Current Model",
            f"Port '{getattr(model, 'name', 'model')}' to {target} and load the ported copy?",
        ) != QtWidgets.QMessageBox.Yes:
            return
        try:
            from src.core.mdl_porter import CrossGamePorter

            ported = CrossGamePorter().port(model, target)
            self._set_model_internal(ported, self._model_path)
            self._log(f"Ported current model to {target}.", "success")
        except Exception as exc:
            self._log(f"Port error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Port Error", str(exc))

    def _generate_module_files(self):
        self._show_modules_tab()
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select output directory for module files",
            str(self.app_root),
        )
        if not out_dir:
            return
        module_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Generate Module Files",
            "Module resref:",
            text="mymodule",
        )
        if not ok or not module_name.strip():
            return
        mod = module_name.strip().lower()
        room = f"{mod}_r01"
        files = {
            f"{mod}.lyt": f"filedependancy {mod}\n\nbeginlayout\n  room 0 {room} 0.0 0.0 0.0\nendlayout\n",
            f"{mod}.vis": f"{room}\n",
            f"{mod}.are.txt": f"# Starter ARE template for {mod}\n# Import into a KotOR GFF tool and save as {mod}.are\n",
            f"{mod}.git.txt": f"# Starter GIT template for {mod}\n# Add creatures, doors, placeables, sounds, and triggers here.\n",
            f"{mod}.ifo.txt": f"# Starter IFO template for {mod}\nMod_ID = \"{mod}\"\nMod_Entry_Area = \"{room}\"\n",
            "README_module_starter.txt": (
                f"Starter module files for {mod}.\n"
                "Convert the .txt GFF templates into ARE/GIT/IFO with your preferred GFF tool.\n"
            ),
        }
        try:
            output = Path(out_dir)
            for name, text in files.items():
                (output / name).write_text(text, encoding="utf-8")
            self._last_module_output_dir = str(output)
            self._log(f"Generated starter module files for {mod} in {output}", "success")
        except Exception as exc:
            self._log(f"Module generation error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Module Generation Error", str(exc))

    def _handle_module_action(self, action: str):
        if action in {"Generate Module Files", "Validate Module", "Open Output"}:
            if action == "Generate Module Files":
                self._generate_module_files()
            elif action == "Open Output":
                path = getattr(self, "_last_module_output_dir", "")
                if path:
                    QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
                else:
                    self._log("Generate module files first, then Open Output.", "warning")
            else:
                self._log(f"{action} needs a generated/open module workspace first.", "warning")
            return
        if action in {"Port K1 to K2", "Port K2 to K1"}:
            self._port_current_model()
            return
        if action == "Open Blueprint":
            self._open_blueprint_editor_window()
            self.blueprint_panel.open_blueprint()
            return
        if action == "Save Blueprint":
            self._open_blueprint_editor_window()
            self.blueprint_panel.save_blueprint()
            return
        if action == "Send to GModular":
            self._ipc_notify_saved()
            return
        self._log(f"{action} is waiting for deeper Qt module-editor migration.", "warning")

    def _retarget_config(self):
        from src.core.animation_retargeting import RetargetConfig

        kwargs = (
            self.animation_retarget_panel.config_kwargs()
            if hasattr(self, "animation_retarget_panel") else {}
        )
        return RetargetConfig(**kwargs)

    def _retarget_refresh_mapping(self):
        if self._retarget_source_model is None or self._retarget_target_model is None:
            return None
        from src.core.animation_retargeting import build_bone_map

        manual_mapping = {}
        if hasattr(self.animation_retarget_panel, "panel"):
            manual_mapping = self.animation_retarget_panel.panel.manual_bone_mapping()
        self._retarget_mapping_report = build_bone_map(
            self._retarget_source_model,
            self._retarget_target_model,
            manual_mapping=manual_mapping,
        )
        self.animation_retarget_panel.set_mapping_report(self._retarget_mapping_report)
        return self._retarget_mapping_report

    def _retarget_set_source_current(self):
        model = self._require_model("Retarget Source")
        if model is None:
            return
        if not (getattr(model, "animations", []) or []):
            QtWidgets.QMessageBox.information(
                self, "Retarget Source",
                "The current model has no local animations to use as a source.",
            )
            return
        self._retarget_source_model = model
        self._retarget_engine = None
        self.animation_retarget_panel.set_texture_dir(self._texture_dir)
        game = (self._current_game or self._infer_game_from_model(model)).upper()
        mgr = self._get_resource_manager()
        if mgr is not None:
            self.animation_retarget_panel.set_source_resource_context(mgr, game)
        self.animation_retarget_panel.set_source_model(model, game)
        self._retarget_refresh_mapping()
        self._log(f"Retarget source set: {getattr(model, 'name', '?')}", "success")

    def _retarget_set_target_current(self):
        model = self._require_model("Retarget Target")
        if model is None:
            return
        self._retarget_target_model = model
        self._retarget_engine = None
        self.animation_retarget_panel.set_texture_dir(self._texture_dir)
        game = (self._current_game or self._infer_game_from_model(model)).upper()
        mgr = self._get_resource_manager()
        if mgr is not None:
            self.animation_retarget_panel.set_target_resource_context(mgr, game)
        self.animation_retarget_panel.set_target_model(model, game)
        self._retarget_refresh_mapping()
        self._log(f"Retarget target set: {getattr(model, 'name', '?')}", "success")

    def _retarget_preview(self, anim_name: str):
        if not anim_name:
            QtWidgets.QMessageBox.information(self, "Retarget", "Select a source animation first.")
            return
        if self._retarget_source_model is None or self._retarget_target_model is None:
            QtWidgets.QMessageBox.information(self, "Retarget", "Set both a source and target model.")
            return
        try:
            from src.core.animation_engine import AnimationEngine

            self._animation_timer.stop()
            self._animation_engine = None
            self._retarget_engine = AnimationEngine(self._retarget_source_model)
            if not self._retarget_engine.play(anim_name, loop=True, blend=False):
                QtWidgets.QMessageBox.information(self, "Retarget", f"Animation not found: {anim_name}")
                return
            self._retarget_refresh_mapping()
            self._retarget_last_tick = None
            self._retarget_timer.start()
            self._log(
                f"Retarget preview: {getattr(self._retarget_source_model, 'name', '?')}:{anim_name} -> "
                f"{getattr(self._retarget_target_model, 'name', '?')}",
                "success",
            )
        except Exception as exc:
            self._log(f"Retarget preview error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Retarget", str(exc))

    def _retarget_target_label(self) -> str:
        model = self._retarget_target_model
        if model is None:
            return ""
        path = str(getattr(model, "mdl_path", "") or "").strip()
        if path:
            return path
        retarget_panel = getattr(self, "animation_retarget_panel", None)
        game = str(
            getattr(retarget_panel, "_target_game", "")
            or self._current_game
            or self._infer_game_from_model(model)
        ).upper()
        name = str(getattr(model, "name", "") or "target").strip() or "target"
        return f"{game}:{name}"

    def _activate_retarget_target_model(self, selected_anim: str) -> None:
        model = self._retarget_target_model
        if model is None:
            return
        if self._current_model is not model:
            self._set_model_internal(model, self._retarget_target_label())
        else:
            if hasattr(self, "animations_panel"):
                self.animations_panel.load_model(model)
        self._populate_animation_library_from_current_model()
        if hasattr(self, "animations_panel"):
            self.animations_panel.select_animation(selected_anim)
        self._show_right_tab("Animations")

    def _retarget_apply(self, anim_name: str):
        if not anim_name:
            QtWidgets.QMessageBox.information(self, "Retarget", "Select a source animation first.")
            return
        if self._retarget_source_model is None or self._retarget_target_model is None:
            QtWidgets.QMessageBox.information(self, "Retarget", "Set both a source and target model.")
            return
        try:
            from src.core.animation_retargeting import retarget_animation

            source_anim = next(
                (
                    anim for anim in (getattr(self._retarget_source_model, "animations", []) or [])
                    if str(getattr(anim, "name", "")).lower() == anim_name.lower()
                ),
                None,
            )
            if source_anim is None:
                QtWidgets.QMessageBox.information(self, "Retarget", f"Animation not found: {anim_name}")
                return
            apply_options = self.animation_retarget_panel.request_apply_options(
                source_anim,
                self._retarget_target_model,
            )
            if apply_options is None:
                return
            report = self._retarget_refresh_mapping()
            new_anim, report = retarget_animation(
                source_anim,
                self._retarget_source_model,
                self._retarget_target_model,
                config=self._retarget_config(),
                mapping_report=report,
            )
            new_anim.name = str(apply_options["name"])
            target_anims = getattr(self._retarget_target_model, "animations", None)
            if target_anims is None:
                self._retarget_target_model.animations = []
                target_anims = self._retarget_target_model.animations
            replaced = False
            if apply_options.get("replace"):
                needle = new_anim.name.lower()
                for index, existing in enumerate(list(target_anims)):
                    if str(getattr(existing, "name", "") or "").lower() == needle:
                        target_anims[index] = new_anim
                        replaced = True
                        break
            if not replaced:
                target_anims.append(new_anim)
            self._activate_retarget_target_model(new_anim.name)
            if hasattr(self, "animation_retarget_panel") and hasattr(self.animation_retarget_panel, "panel"):
                self.animation_retarget_panel.panel.set_target_model(self._retarget_target_model)
            self.animation_retarget_panel.set_mapping_report(report)
            self.statusBar().showMessage(
                f"{'Replaced' if replaced else 'Added'} animation {new_anim.name} on "
                f"{getattr(self._retarget_target_model, 'name', 'target')}"
            )
            self._log(
                f"{'Replaced' if replaced else 'Added'} retargeted animation {new_anim.name} "
                f"from {anim_name} to target animation list ({report.matched_count} bones)",
                "success",
            )
        except Exception as exc:
            self._log(f"Retarget apply error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Retarget", str(exc))

    def _retarget_stop(self):
        self._retarget_timer.stop()
        self._retarget_last_tick = None
        if self._retarget_engine is not None:
            self._retarget_engine.stop()
        if hasattr(self, "animation_retarget_panel"):
            self.animation_retarget_panel.clear_poses()
        self._log("Retarget preview stopped.", "info")

    def _tick_retarget_animation(self):
        engine = self._retarget_engine
        if engine is None or not engine.is_playing:
            self._retarget_timer.stop()
            self._retarget_last_tick = None
            return
        if self._retarget_source_model is None or self._retarget_target_model is None:
            self._retarget_stop()
            return
        now = time.perf_counter()
        if self._retarget_last_tick is None:
            dt = 1.0 / 30.0
        else:
            dt = max(1.0 / 60.0, min(now - self._retarget_last_tick, 0.25))
        self._retarget_last_tick = now
        still_playing = engine.advance(dt)
        source_pose = engine.evaluate()
        anim = engine.current_animation
        anim_name = getattr(anim, "name", "") if anim else ""
        anim_length = float(getattr(anim, "length", 0.0) or 0.0) if anim else 0.0
        try:
            from src.core.animation_retargeting import retarget_pose

            result = retarget_pose(
                source_pose,
                self._retarget_source_model,
                self._retarget_target_model,
                config=self._retarget_config(),
                mapping_report=self._retarget_mapping_report,
            )
            self._retarget_mapping_report = result.report
            if hasattr(self, "animation_retarget_panel"):
                self.animation_retarget_panel.set_source_pose(
                    source_pose,
                    name=anim_name,
                    time=engine.current_time,
                    length=anim_length,
                )
                self.animation_retarget_panel.set_target_pose(
                    result.pose,
                    name=f"retarget:{anim_name}",
                    time=engine.current_time,
                    length=anim_length,
                )
        except Exception as exc:
            self._log(f"Retarget tick error: {exc}", "error")
            self._retarget_stop()
            return
        if not still_playing:
            self._retarget_stop()

    def _handle_animation_selected(self, anim_name: str):
        model = self._current_model
        if not model or not anim_name:
            return
        for anim in getattr(model, "animations", []) or []:
            if getattr(anim, "name", "") != anim_name:
                continue
            length = float(getattr(anim, "length", 0.0) or 0.0)
            events = getattr(anim, "events", []) or []
            node_anims = getattr(anim, "node_anims", {}) or {}
            key_count = 0
            for node_anim in node_anims.values() if hasattr(node_anims, "values") else []:
                for attr in ("position_keys", "rotation_keys", "scale_keys"):
                    key_count += len(getattr(node_anim, attr, []) or [])
            self.animations_panel.info.setPlainText(
                f"{anim_name}\nLength: {length:.3f} s\nKeys: {key_count}  Nodes: {len(node_anims)}  Events: {len(events)}"
            )
            self.animations_panel.seek.blockSignals(True)
            self.animations_panel.seek.setValue(0)
            self.animations_panel.seek.blockSignals(False)
            return

    def _handle_animation_action(self, action: str, anim_name: str):
        model = self._require_model("Animations")
        if model is None:
            return
        if action == "Export Binary MDL":
            self._export_mdl_binary()
            return
        animations = getattr(model, "animations", []) or []
        if not animations:
            QtWidgets.QMessageBox.information(self, "Animations", "No animations available on this model.")
            return
        if not anim_name and action not in {"Stop", "Loop"}:
            QtWidgets.QMessageBox.information(self, "Animations", "Select an animation first.")
            return
        try:
            from src.core.animation_engine import AnimationEngine

            if self._animation_engine is None or getattr(self._animation_engine, "model", None) is not model:
                self._animation_engine = AnimationEngine(model)
            if action == "Play":
                ok = self._animation_engine.play(anim_name, loop=self._animation_loop, blend=False)
                if ok:
                    try:
                        self.viewport.set_anim_base_pose(self._animation_engine.evaluate(0.0))
                    except Exception:
                        pass
                    self._animation_last_tick = None
                    self._animation_timer.start()
                self.animations_panel.info.setPlainText(
                    f"Playing {anim_name}" if ok else f"Animation not found: {anim_name}"
                )
                self._log(f"Animation play: {anim_name}", "success" if ok else "warning")
            elif action == "Stop":
                self._animation_timer.stop()
                self._animation_last_tick = None
                self._animation_engine.stop()
                if hasattr(self.viewport, "clear_animation_pose"):
                    self.viewport.clear_animation_pose()
                self.animations_panel.info.setPlainText("Animation stopped.")
            elif action == "Loop":
                self._animation_loop = not self._animation_loop
                if self._animation_engine is not None:
                    self._animation_engine._loop = self._animation_loop
                self.animations_panel.info.setPlainText(f"Loop {'on' if self._animation_loop else 'off'}.")
            elif action == "Export":
                self._export_selected_animation(anim_name)
            elif action == "Bake Animation":
                self._bake_selected_animation(anim_name)
        except Exception as exc:
            self._log(f"Animation action error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Animations", str(exc))

    def _request_bake_animation_options(self, anim_name: str) -> Optional[dict]:
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Bake Animation")
        layout = QtWidgets.QVBoxLayout(dialog)
        form = QtWidgets.QFormLayout()
        name_edit = QtWidgets.QLineEdit(anim_name)
        fps_spin = QtWidgets.QSpinBox()
        fps_spin.setRange(1, 120)
        fps_spin.setValue(30)
        replace_box = QtWidgets.QCheckBox("Replace animation with same name")
        replace_box.setChecked(True)
        form.addRow("Name:", name_edit)
        form.addRow("FPS:", fps_spin)
        layout.addLayout(form)
        layout.addWidget(replace_box)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return None
        name = name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.information(self, "Bake Animation", "Enter an animation name.")
            return None
        return {"name": name, "fps": int(fps_spin.value()), "replace": replace_box.isChecked()}

    def _bake_selected_animation(self, anim_name: str):
        model = self._require_model("Bake Animation")
        if model is None:
            return
        options = self._request_bake_animation_options(anim_name)
        if options is None:
            return
        baked = self._build_baked_animation(
            model,
            anim_name,
            str(options["name"]),
            fps=int(options["fps"]),
        )
        animations = getattr(model, "animations", None)
        if animations is None:
            model.animations = []
            animations = model.animations
        replaced = False
        if options.get("replace"):
            needle = baked.name.lower()
            for index, existing in enumerate(list(animations)):
                if str(getattr(existing, "name", "") or "").lower() == needle:
                    animations[index] = baked
                    replaced = True
                    break
        if not replaced:
            animations.append(baked)
        self._animation_engine = None
        if hasattr(self, "animations_panel"):
            self.animations_panel.load_model(model, select_name=baked.name)
            self.animations_panel.info.setPlainText(
                f"Baked {anim_name} -> {baked.name}\n"
                f"{len(getattr(baked, 'nodes', []) or [])} nodes @ {int(options['fps'])} fps"
            )
        self._populate_animation_library_from_current_model()
        self.statusBar().showMessage(f"Baked animation {baked.name}")
        self._log(
            f"{'Replaced' if replaced else 'Added'} baked animation {baked.name} "
            f"from {anim_name}",
            "success",
        )

    def _build_baked_animation(self, model, anim_name: str, output_name: str, fps: int = 30):
        from src.core.animation_engine import AnimationEngine
        from src.core.model_data import Animation

        fps = max(1, int(fps or 30))
        engine = AnimationEngine(model)
        if not engine.play(anim_name, loop=False, blend=False):
            raise ValueError(f"Animation not found: {anim_name}")
        source_anim = engine.current_animation
        if source_anim is None:
            raise ValueError(f"Animation not found: {anim_name}")
        length = max(0.0, float(getattr(source_anim, "length", 0.0) or 0.0))
        frame_count = max(1, int(math.ceil(length * fps))) if length > 0.0 else 1
        times = [min(length, i / float(fps)) for i in range(frame_count + 1)]
        if not times:
            times = [0.0]

        base_nodes = {
            str(getattr(node, "name", "") or "").lower(): node
            for node in (list(model.all_nodes()) if hasattr(model, "all_nodes") else [])
            if getattr(node, "name", "")
        }
        sampled_poses = [(t, engine.evaluate(t)) for t in times]
        baked = Animation(
            name=output_name,
            length=length,
            transition_time=float(getattr(source_anim, "transition_time", 0.25) or 0.25),
            anim_root=str(getattr(source_anim, "anim_root", "") or ""),
            events=copy.deepcopy(getattr(source_anim, "events", []) or []),
            nodes=[],
        )
        ctrl_names = {
            8: "position",
            20: "orientation",
            36: "scale",
            100: "selfillumcolor",
            128: "alpha",
            132: "alpha",
        }

        for source_node in getattr(source_anim, "nodes", []) or []:
            key = str(getattr(source_node, "name", "") or "").lower()
            if not key:
                continue
            source_types = {
                int(ctrl.get("type", -1))
                for ctrl in (getattr(source_node, "controllers", []) or [])
                if isinstance(ctrl, dict)
            }
            if not source_types:
                continue
            base_node = base_nodes.get(key)
            if base_node is not None and hasattr(base_node, "clone_shallow"):
                baked_node = base_node.clone_shallow()
            elif hasattr(source_node, "clone_shallow"):
                baked_node = source_node.clone_shallow()
            else:
                baked_node = copy.copy(source_node)
            baked_node.name = str(getattr(base_node or source_node, "name", key) or key)
            baked_node.children = []
            baked_node.parent = None
            baked_node.controllers = []
            base_pos = tuple(getattr(base_node, "position", (0.0, 0.0, 0.0)) if base_node else (0.0, 0.0, 0.0))

            def _samples_for_node():
                for sample_time, pose in sampled_poses:
                    node_pose = getattr(pose, "nodes", {}).get(key)
                    if node_pose is not None:
                        yield sample_time, node_pose

            node_samples = list(_samples_for_node())
            if not node_samples:
                continue
            node_times = [sample_time for sample_time, _node_pose in node_samples]
            poses = [node_pose for _sample_time, node_pose in node_samples]
            if 8 in source_types:
                baked_node.controllers.append({
                    "type": 8,
                    "name": ctrl_names[8],
                    "columns": 3,
                    "times": node_times,
                    "values": [
                        [
                            float(node_pose.position[0]) - float(base_pos[0]),
                            float(node_pose.position[1]) - float(base_pos[1]),
                            float(node_pose.position[2]) - float(base_pos[2]),
                        ]
                        for node_pose in poses
                    ],
                })
            if 20 in source_types:
                baked_node.controllers.append({
                    "type": 20,
                    "name": ctrl_names[20],
                    "columns": 4,
                    "times": node_times,
                    "values": [[float(v) for v in node_pose.rotation[:4]] for node_pose in poses],
                })
            if 36 in source_types:
                baked_node.controllers.append({
                    "type": 36,
                    "name": ctrl_names[36],
                    "columns": 1,
                    "times": node_times,
                    "values": [[float(node_pose.scale)] for node_pose in poses],
                })
            alpha_type = 132 if 132 in source_types else 128 if 128 in source_types else None
            if alpha_type is not None:
                baked_node.controllers.append({
                    "type": alpha_type,
                    "name": ctrl_names[alpha_type],
                    "columns": 1,
                    "times": node_times,
                    "values": [[float(node_pose.alpha if node_pose.alpha is not None else 1.0)] for node_pose in poses],
                })
            if 100 in source_types:
                baked_node.controllers.append({
                    "type": 100,
                    "name": ctrl_names[100],
                    "columns": 3,
                    "times": node_times,
                    "values": [
                        [float(v) for v in (node_pose.selfillum or (0.0, 0.0, 0.0))[:3]]
                        for node_pose in poses
                    ],
                })
            if baked_node.controllers:
                baked.nodes.append(baked_node)
        return baked

    def _handle_animation_seek(self, percent: int):
        model = self._current_model
        anim_name = self.animations_panel.selected_animation() if hasattr(self, "animations_panel") else ""
        if model is None or not anim_name:
            return
        try:
            from src.core.animation_engine import AnimationEngine

            if self._animation_engine is None or getattr(self._animation_engine, "model", None) is not model:
                self._animation_engine = AnimationEngine(model)
            current = self._animation_engine.current_animation
            if current is None or getattr(current, "name", "") != anim_name:
                if not self._animation_engine.play(anim_name, loop=self._animation_loop, blend=False):
                    return
                self._animation_engine.stop()
                current = self._animation_engine.current_animation
            length = float(getattr(current, "length", 0.0) or 0.0) if current else 0.0
            if length <= 0.0:
                return
            t = max(0.0, min(100.0, float(percent))) / 100.0 * length
            was_playing = self._animation_engine.is_playing
            self._animation_engine.seek(t)
            pose = self._animation_engine.evaluate()
            if hasattr(self, "viewport"):
                self.viewport.set_animation_pose(pose, name=anim_name, time=t, length=length)
            self.animations_panel.info.setPlainText(f"{anim_name}\n{t:.3f} / {length:.3f} s")
            if not was_playing:
                self._animation_engine.stop()
        except Exception as exc:
            self._log(f"Animation seek error: {exc}", "error")

    def _tick_animation(self):
        engine = self._animation_engine
        if engine is None or not engine.is_playing:
            self._animation_timer.stop()
            self._animation_last_tick = None
            return
        now = time.perf_counter()
        if self._animation_last_tick is None:
            dt = 1.0 / 30.0
        else:
            dt = max(1.0 / 60.0, min(now - self._animation_last_tick, 0.25))
        self._animation_last_tick = now
        still_playing = engine.advance(dt)
        pose = engine.evaluate()
        anim = engine.current_animation
        anim_name = getattr(anim, "name", "") if anim else ""
        anim_length = float(getattr(anim, "length", 0.0) or 0.0) if anim else 0.0
        if hasattr(self, "viewport"):
            self.viewport.set_animation_pose(
                pose,
                name=anim_name,
                time=engine.current_time,
                length=anim_length,
            )
        if anim_length > 0 and hasattr(self, "animations_panel"):
            pct = max(0, min(100, int((engine.current_time / anim_length) * 100.0)))
            self.animations_panel.seek.blockSignals(True)
            self.animations_panel.seek.setValue(pct)
            self.animations_panel.seek.blockSignals(False)
            self.animations_panel.info.setPlainText(
                f"Playing {anim_name}\n{engine.current_time:.3f} / {anim_length:.3f} s"
            )
        if not still_playing:
            self._animation_timer.stop()
            self._animation_last_tick = None

    def _export_selected_animation(self, anim_name: str):
        model = self._require_model("Export Animation")
        if model is None:
            return
        path, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Animation",
            f"{anim_name}.json",
            "Animation JSON (*.json);;BVH (*.bvh)",
        )
        if not path:
            return
        from src.core.animation_engine import AnimationEngine

        engine = AnimationEngine(model)
        if selected_filter.startswith("BVH") or path.lower().endswith(".bvh"):
            ok = engine.export_animation_bvh(anim_name, path)
        else:
            ok = engine.export_animation_json(anim_name, path)
        self._log(
            f"Exported animation {anim_name} -> {Path(path).name}" if ok else f"Animation export failed: {anim_name}",
            "success" if ok else "error",
        )

    def _populate_animation_library_from_current_model(self):
        if not hasattr(self, "animation_library_panel"):
            return
        model = self._current_model
        entries = []
        if model is not None:
            for anim in getattr(model, "animations", []) or []:
                length = float(getattr(anim, "length", 0.0) or 0.0)
                entries.append(
                    {
                        "model": getattr(model, "name", ""),
                        "animation": getattr(anim, "name", ""),
                        "frames": int(round(length * 30.0)) if length else "",
                        "source": "Current model",
                    }
                )
        self.animation_library_panel.set_entries(entries)

    def _handle_animation_library_action(self, action: str):
        if action in {"Scan Animations", "Refresh"}:
            self._populate_animation_library_from_current_model()
            count = self.animation_library_panel.tree.topLevelItemCount()
            self._log(f"Animation library refreshed: {count} current-model animations", "info")
            return
        entry = self.animation_library_panel.selected_entry()
        if not entry:
            QtWidgets.QMessageBox.information(self, "Animation Library", "Select an animation entry first.")
            return
        anim_name = str(entry.get("animation") or "")
        if action in {"Load", "Preview"}:
            self._show_right_tab("Animation Library")
            matches = self.animations_panel.listbox.findItems(anim_name, QtCore.Qt.MatchExactly)
            if matches:
                self.animations_panel.listbox.setCurrentItem(matches[0])
            if action == "Preview":
                self._handle_animation_action("Play", anim_name)
        elif action == "Export":
            self._export_selected_animation(anim_name)

    def _populate_resource_panel(self):
        if not hasattr(self, "resource_panel"):
            return
        try:
            from src.core import resource_manager as rm

            manager = rm.ResourceManager()
            k1_dir = self.k1_dir_edit.text().strip()
            k2_dir = self.k2_dir_edit.text().strip()
            if k1_dir:
                manager.set_k1_dir(k1_dir)
            if k2_dir:
                manager.set_k2_dir(k2_dir)
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
            self._resource_manager = manager
            self._resource_manager_dirs = (k1_dir, k2_dir)
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
            from src.core import resource_manager as rm

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
            from src.core import resource_manager as rm
            from src.core.twoda import TwoDA

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
            "Tabs include room layout, walkmesh tools, K1/K2 model porting, module "
            "starter-file generation, and blueprint handoff to GModular.\n\n"
            "The Qt panel is wired for navigation and starter generation; deeper "
            "module editing tools will migrate from the Tk module panel in later passes.",
        )

    def _validate_current_character(self):
        try:
            from src.core.model_data import CharacterScene, PartSlot
            from src.core.validation_service import ValidationService

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

    def _show_modules_tab(self):
        tabs = getattr(self, "left_tabs", None)
        panel = getattr(self, "modular_panel", None)
        if tabs is None or panel is None:
            self._not_migrated("Modules")
            return
        index = tabs.indexOf(panel)
        if index >= 0:
            tabs.setCurrentIndex(index)

    def _open_rig_window(self):
        window = getattr(self, "rig_window", None)
        if window is None:
            self._not_migrated("Rigging Window")
            return
        window.show()
        window.raise_()
        window.activateWindow()

    def _open_animation_retarget_window(self):
        window = getattr(self, "animation_retarget_window", None)
        if window is None:
            self._not_migrated("Animation Retargeting Workbench")
            return
        try:
            window.set_texture_dir(self._texture_dir)
            window.set_navigation_profile(
                self.settings_data.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
            )
            if self._retarget_source_model is not None:
                window.set_source_model(self._retarget_source_model)
            if self._retarget_target_model is not None:
                window.set_target_model(self._retarget_target_model)
        except Exception:
            pass
        window.show()
        window.raise_()
        window.activateWindow()

    def _open_unreal_animator_window(self):
        window = getattr(self, "unreal_animator_window", None)
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

    def _reload_unreal_animator_window(self) -> None:
        global QtUnrealAnimatorWindow

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
        tabs = getattr(self, "right_tabs", None)
        if tabs is None:
            self._not_migrated(label)
            return
        needle = label.lower()
        aliases = {"animations": ("anims", "anim lib")}
        names = aliases.get(needle, (needle,))
        for index in range(tabs.count()):
            text = tabs.tabText(index).lower()
            if any(name in text for name in names):
                tabs.setCurrentIndex(index)
                return

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
        window = getattr(self, "animation_retarget_window", None)
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
        self._retarget_refresh_mapping()
        self._open_animation_retarget_window()

    def _retarget_select_library_model(self, role: str) -> None:
        panel = getattr(self, "library_panel", None)
        row = panel.selected_row() if panel is not None else None
        if not row:
            tabs = getattr(self, "left_tabs", None)
            if tabs is not None and panel is not None:
                index = tabs.indexOf(panel)
                if index >= 0:
                    tabs.setCurrentIndex(index)
            QtWidgets.QMessageBox.information(
                self,
                "Retarget Workbench",
                "Select a model in the Game Library first.",
            )
            return
        self._send_library_row_to_retarget(row, role)

    def _populate_saved_dirs(self):
        self.library_list.clear()
        for key, label in (("k1_dir", "KotOR 1"), ("k2_dir", "KotOR 2")):
            value = str(self.settings_data.get(key) or "").strip()
            if value:
                self.library_list.addItem(f"{label}: {value}")
        if self.library_list.count() == 0:
            self.library_list.addItem("No saved game directories yet")

    def _scan_library(self):
        if self._scan_worker_is_running():
            return
        k1_dir = self.k1_dir_edit.text().strip()
        k2_dir = self.k2_dir_edit.text().strip()
        self._show_progress_toast(
            "Scanning game library",
            "Indexing model resources from detected game directories...",
        )
        self.scan_button.setEnabled(False)
        self.library_list.clear()
        self.library_list.addItem("Scanning...")
        self._log("Scanning game library...")
        self.statusBar().showMessage("Scanning library...")

        worker = LibraryScanWorker(k1_dir, k2_dir)
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_library_scanned)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_scan_thread", None))
        thread.finished.connect(lambda: setattr(self, "_scan_worker", None))
        self._scan_thread = thread
        self._scan_worker = worker
        thread.start()

    @QtCore.Slot(list, str)
    def _on_library_scanned(self, rows: list, error: str):
        self.scan_button.setEnabled(True)
        if error:
            self._finish_progress_toast("Library scan failed", "Check the output log for details.")
            self.library_list.clear()
            self.library_list.addItem("Scan failed")
            if hasattr(self, "library_panel"):
                self.library_panel.set_rows([])
                self.library_panel.set_status("Scan failed")
            self._log(f"Library scan failed:\n{error}", "error")
            self.statusBar().showMessage("Library scan failed")
            return
        self._library_rows = rows
        self._rebuild_library_list()
        if hasattr(self, "library_panel"):
            self.library_panel.set_rows(rows)
            self.library_panel.set_status(f"{len(rows)} models")
        self._unreal_refresh_supermodel_library()
        self._populate_resource_panel()
        self._populate_animation_library_from_current_model()
        self._finish_progress_toast("Library ready", f"{len(rows)} models indexed.")
        self._log(f"Library scan complete: {len(rows)} models", "success")
        self.statusBar().showMessage(f"{len(rows)} models")

    def _rebuild_library_list(self):
        self.library_list.clear()
        needle = self.library_filter.text().lower().strip()
        for row in self._library_rows:
            text = f"[{row.get('game', '?')}] {row.get('resref', '')}"
            if needle and needle not in text.lower():
                continue
            self.library_list.addItem(ModelListItem(row))
        if self.library_list.count() == 0:
            self.library_list.addItem("No matching models")

    def _filter_library(self, text: str):
        if self._library_rows:
            self._rebuild_library_list()
            return
        needle = text.lower().strip()
        for row in range(self.library_list.count()):
            item = self.library_list.item(row)
            item.setHidden(bool(needle and needle not in item.text().lower()))

    def _load_library_item(self, item: QtWidgets.QListWidgetItem):
        row = getattr(item, "row", None)
        if not row:
            return
        self._start_resource_load(row["resref"], row["game"])

    def _start_resource_load(self, resref: str, game: str):
        if self._model_worker_is_running():
            self._log("A model is already loading.", "warning")
            return
        if str(resref).lower().startswith("gr_humanoid"):
            try:
                from src.core.template_builder import build_humanoid_template

                self._show_progress_toast("Loading model", f"Building template {game}:{resref}...")
                game_tag = game.upper() if game else "K1"
                model = build_humanoid_template(game_version=game_tag, name=resref)
                self._current_game = game_tag
                self._on_model_loaded(model, f"{game_tag}:{resref}", "")
            except Exception:
                self._log(f"Template load failed:\n{traceback.format_exc()}", "error")
            return
        self._log(f"Loading {game}:{resref} ...")
        self.statusBar().showMessage(f"Loading {game}:{resref}...")
        self._show_progress_toast("Loading model", f"Loading {game}:{resref} from game resources...")
        self._current_game = game.upper()

        worker = ResourceModelLoadWorker(
            resref,
            game,
            self.k1_dir_edit.text().strip(),
            self.k2_dir_edit.text().strip(),
        )
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_model_load_progress)
        worker.finished.connect(self._on_model_loaded)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_worker_thread", None))
        thread.finished.connect(lambda: setattr(self, "_model_worker", None))
        self._worker_thread = thread
        self._model_worker = worker
        thread.start()

    def _open_model(self, _checked: bool = False, *, ascii_only: bool = False):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open ASCII MDL" if ascii_only else "Open KotOR MDL",
            str(Path(self.settings_data.get("last_import") or self.app_root)),
            "ASCII MDL (*.mdl);;All files (*.*)" if ascii_only else "KotOR MDL (*.mdl);;All files (*.*)",
        )
        if not path:
            return
        self._start_model_load(path)

    def _open_startup_inputs(self):
        mdl_path = str(self.startup_input.get("mdl") or "").strip()
        if not mdl_path:
            return
        texture_dir = str(self.startup_input.get("texture_dir") or "").strip()
        textures = [str(path) for path in (self.startup_input.get("tga") or []) if path]
        if not texture_dir and textures:
            texture_dir = str(Path(textures[0]).resolve().parent)
        mdx_path = str(self.startup_input.get("mdx") or "").strip()
        game = str(self.startup_input.get("game") or "").upper()
        self._start_model_load(mdl_path, mdx_path=mdx_path, texture_dir=texture_dir, game=game)
        if textures:
            self._log(f"Startup texture context: {len(textures)} file(s)", "info")

    def _start_model_load(
        self,
        path: str,
        *,
        mdx_path: str = "",
        texture_dir: str = "",
        game: str = "",
    ):
        if self._model_worker_is_running():
            self._log("A model is already loading.", "warning")
            return
        mdl = Path(path)
        if not mdl.exists():
            self._log(f"Startup model not found: {path}", "error")
            self.statusBar().showMessage("Model file not found")
            return
        if mdx_path and not Path(mdx_path).exists():
            self._log(f"MDX file not found, using sibling lookup: {mdx_path}", "warning")
            mdx_path = ""
        self._texture_dir = texture_dir or str(mdl.parent)
        self._log(f"Loading {mdl} ...")
        self.statusBar().showMessage("Loading model...")
        self._show_progress_toast("Loading model", f"Loading {mdl.name}...")
        self._current_game = game.upper()

        worker = ModelLoadWorker(str(mdl), mdx_path, self._current_game)
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_model_load_progress)
        worker.finished.connect(self._on_model_loaded)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_worker_thread", None))
        thread.finished.connect(lambda: setattr(self, "_model_worker", None))
        self._worker_thread = thread
        self._model_worker = worker
        thread.start()

    @QtCore.Slot(object, str, str)
    def _on_model_loaded(self, model, path: str, error: str):
        if error:
            self._log(f"Model load failed:\n{error}", "error")
            self.statusBar().showMessage("Model load failed")
            self._pending_gpu_upload_model_id = 0
            self._pending_gpu_upload_total = 0
            self._finish_progress_toast("Model load failed", "Check the output log for details.")
            return
        self._update_progress_toast("Loading model", "Updating viewport and panels...", 5, 6)
        self._animation_timer.stop()
        self._animation_engine = None
        self._animation_last_tick = None
        self._retarget_timer.stop()
        self._retarget_engine = None
        self._retarget_last_tick = None
        self._current_model = model
        self._retarget_target_model = model
        self._retarget_mapping_report = None
        if path:
            self._model_path = path
            if str(path).startswith(("K1:", "K2:")):
                self._current_game = str(path).split(":", 1)[0].upper()
            else:
                self._texture_dir = self._texture_dir or str(Path(path).parent)
                self._current_game = self._infer_game_from_model(model)
        mesh_count = len(model.mesh_nodes()) if hasattr(model, "mesh_nodes") else 0
        node_count = model.node_count() if hasattr(model, "node_count") else 0
        anim_count = len(getattr(model, "animations", []) or [])
        name = getattr(model, "name", Path(path).stem)
        if hasattr(self, "viewport"):
            self._configure_viewport_resources()
            self.viewport.load_model(model, self._texture_dir)
            self._try_coload_walkmesh()
        else:
            self.viewport_label.setText(f"{name}\n\nQt viewport host\n{mesh_count} mesh | {node_count} nodes")
        self.model_pill.setText(f"// {name}")
        self.model_pill.setToolTip(
            f"Currently loaded model: {name} (Ctrl+W to clear)"
        )
        if hasattr(self, "skeleton_panel"):
            self.skeleton_panel.load_model(model)
        if hasattr(self, "properties_panel"):
            self.properties_panel.show_model(model)
        if hasattr(self, "module_geometry_panel"):
            self.module_geometry_panel.show_model(model)
        if hasattr(self, "animations_panel"):
            self.animations_panel.load_model(model)
        if hasattr(self, "animation_retarget_panel"):
            self.animation_retarget_panel.set_texture_dir(self._texture_dir)
            game = (self._current_game or self._infer_game_from_model(model)).upper()
            if self._supports_animation_retarget_target(model):
                mgr = self._get_resource_manager()
                if mgr is not None:
                    self.animation_retarget_panel.set_target_resource_context(mgr, game)
                self.animation_retarget_panel.set_target_model(model, game)
            else:
                self._retarget_target_model = None
                self._retarget_mapping_report = None
                self.animation_retarget_panel.set_target_model(None, game)
        if hasattr(self, "diagnostics_panel"):
            self.diagnostics_panel.run_diagnostics(model)
        self.props_text.setPlainText(
            "\n".join(
                [
                    f"Name: {name}",
                    f"Path: {path}",
                    f"Meshes: {mesh_count}",
                    f"Nodes: {node_count}",
                    f"Animations: {anim_count}",
                    f"Supermodel: {getattr(model, 'supermodel', '')}",
                ]
            )
        )
        prebuilt_meshes = int(getattr(model, "_gr_gpu_prebuilt_mesh_count", 0) or 0)
        if prebuilt_meshes:
            self._pending_gpu_upload_model_id = id(model)
            self._pending_gpu_upload_total = prebuilt_meshes
            self._update_progress_toast(
                "Uploading mesh buffers",
                f"Moving mesh buffers into GPU memory (0/{prebuilt_meshes})...",
                0,
                prebuilt_meshes,
            )
            QtCore.QTimer.singleShot(
                5000,
                lambda model_id=id(model): self._finish_model_load_toast_if_pending(model_id),
            )
        else:
            self._pending_gpu_upload_model_id = 0
            self._pending_gpu_upload_total = 0
            self._finish_progress_toast("Model ready", f"{name} loaded.")
        if prebuilt_meshes:
            self._log(
                f"Loaded {name} ({mesh_count} mesh, {node_count} nodes; {prebuilt_meshes} GPU buffers prepared in RAM)",
                "success",
            )
        else:
            self._log(f"Loaded {name} ({mesh_count} mesh, {node_count} nodes)", "success")
        self.statusBar().showMessage(f"Loaded {name}")

    def _infer_game_from_model(self, model) -> str:
        try:
            game_name = getattr(getattr(model, "game_version", ""), "name", "")
            if str(game_name).upper() == "K2":
                return "K2"
        except Exception:
            pass
        return str(self.settings_data.get("default_game") or "K1").upper()

    def _configured_game_dirs(self) -> tuple[str, str]:
        k1_dir = self.k1_dir_edit.text().strip() if hasattr(self, "k1_dir_edit") else ""
        k2_dir = self.k2_dir_edit.text().strip() if hasattr(self, "k2_dir_edit") else ""
        return k1_dir, k2_dir

    def _get_resource_manager(self):
        k1_dir, k2_dir = self._configured_game_dirs()
        if not (k1_dir or k2_dir):
            return None
        existing = getattr(self, "_resource_manager", None)
        if existing is not None and getattr(self, "_resource_manager_dirs", ("", "")) == (k1_dir, k2_dir):
            return existing
        try:
            from src.core.resource_manager import ResourceManager

            mgr = ResourceManager()
            if k1_dir:
                mgr.set_k1_dir(k1_dir)
            if k2_dir:
                mgr.set_k2_dir(k2_dir)
            self._resource_manager = mgr
            self._resource_manager_dirs = (k1_dir, k2_dir)
            return mgr
        except Exception as exc:
            self._log(f"Resource manager unavailable: {exc}", "warning")
            return None

    @staticmethod
    def _supports_animation_retarget_target(model) -> bool:
        if model is None:
            return True
        try:
            return int(getattr(model, "model_type", 0)) == 4
        except Exception:
            pass
        return str(getattr(model, "classification", "") or "").lower() in {
            "character",
            "creature",
            "headless_body",
            "head",
        }

    def _configure_viewport_resources(self):
        viewport = getattr(self, "viewport", None)
        if viewport is None:
            return
        game = (self._current_game or self._infer_game_from_model(self._current_model)).upper()
        mgr = self._get_resource_manager()
        if mgr is not None:
            try:
                viewport.set_resource_manager(mgr, game)
            except Exception as exc:
                self._log(f"Viewport texture resource setup failed: {exc}", "warning")

    @staticmethod
    def _derive_wok_resrefs(stem: str) -> list[str]:
        candidates = [stem]
        match = re.match(r"^(.+?)_[0-9a-z]+$", stem)
        if match:
            base = match.group(1)
            if base and base != stem:
                candidates.append(base)
                if base[:3].isdigit() and len(base) > 3:
                    candidates.append(base[:3])
        return candidates

    def _try_coload_walkmesh(self, mdl_path: Optional[Path] = None):
        try:
            if mdl_path is None:
                path = str(self._model_path or "")
                if path and not path.startswith(("K1:", "K2:")):
                    mdl_path = Path(path)
            self._do_coload_walkmesh(mdl_path)
        except Exception as exc:
            log.debug("_try_coload_walkmesh: %s", exc)

    def _do_coload_walkmesh(self, mdl_path: Optional[Path]):
        viewport = getattr(self, "viewport", None)
        if viewport is None:
            return
        model = self._current_model
        if model is None:
            viewport.clear_walkmesh()
            return

        path_label = str(self._model_path or "")
        if mdl_path is not None and mdl_path.name:
            stem = mdl_path.stem.lower()
            folder = mdl_path.parent
        elif ":" in path_label:
            stem = path_label.split(":", 1)[1].lower()
            folder = None
        else:
            stem = str(getattr(model, "name", "") or "").lower()
            folder = None
        if not stem:
            return

        viewport.clear_walkmesh()
        candidates = self._derive_wok_resrefs(stem)
        for base in candidates:
            if folder is not None:
                for ext in (".wok", ".pwk", ".dwk", ".bwm"):
                    path = folder / f"{base}{ext}"
                    if path.exists() and self._load_walkmesh_source(str(path), path.name):
                        return

        mgr = self._resource_manager or self._get_resource_manager()
        game = (self._current_game or self._infer_game_from_model(model)).upper()
        if mgr is not None:
            try:
                from src.core.resource_manager import RES_WOK

                for base in candidates:
                    data = mgr.get(base, RES_WOK, game)
                    if data and self._load_walkmesh_source(data, f"{game}:{base}.wok"):
                        return
            except Exception as exc:
                log.debug("resource walkmesh lookup failed: %s", exc)

    def _load_walkmesh_source(self, source, label: str) -> bool:
        try:
            if isinstance(source, (bytes, bytearray)):
                from src.core.module_format import WOKData

                source = WOKData.from_bytes(bytes(source))
            self.viewport.load_walkmesh(source)
            self.viewport._renderer.show_walkmesh = True
            self.viewport.walkmesh_button.setChecked(True)
            self.viewport._request_render()
            self._log(f"Walkmesh loaded: {label}", "success")
            return True
        except Exception as exc:
            log.debug("walkmesh load failed for %s: %s", label, exc)
            return False

    def _launch_legacy_tk(self):
        if self._legacy_process is not None and self._legacy_process.poll() is None:
            self._log("Legacy Tk workbench is already running.", "warning")
            return

        env = os.environ.copy()
        env["GHOSTRIGGER_GUI"] = "tk"
        env["GHOSTRIGGER_NO_MCP_AUTOSTART"] = "1"

        if getattr(sys, "frozen", False):
            argv = [sys.executable]
        else:
            argv = [sys.executable, str(self.app_root / "main.py")]

        try:
            self._legacy_process = subprocess.Popen(
                argv,
                cwd=str(self.app_root),
                env=env,
                stdin=subprocess.DEVNULL,
            )
            self._log("Legacy Tk workbench launched.", "success")
        except Exception as exc:
            self._log(f"Could not launch legacy Tk workbench: {exc}", "error")

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
        self._character_builder_window.show()
        self._character_builder_window.raise_()
        self._character_builder_window.activateWindow()

    def _open_settings_dialog(self):
        dialog = QtSettingsDialog(self.settings_data, self)
        dialog.settingsSaved.connect(self._save_settings_data)
        dialog.exec()

    def _save_settings_data(self, values: dict):
        self.settings_data = values
        viewport = getattr(self, "viewport", None)
        if viewport is not None:
            viewport.set_navigation_profile(
                normalize_viewport_navigation_profile(
                    values.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
                )
            )
        retarget_window = getattr(self, "animation_retarget_window", None)
        if retarget_window is not None:
            retarget_window.set_navigation_profile(
                normalize_viewport_navigation_profile(
                    values.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
                )
            )
        unreal_window = getattr(self, "unreal_animator_window", None)
        if unreal_window is not None:
            unreal_window.set_navigation_profile(
                normalize_viewport_navigation_profile(
                    values.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
                )
            )
        try:
            save_settings(self.settings_path, values)
            self._log("Settings saved.", "success")
        except Exception as exc:
            self._log(f"Settings save failed: {exc}", "error")

    def closeEvent(self, event: QtGui.QCloseEvent):
        try:
            self._matrix_engine.stop()
        except Exception:
            pass
        super().closeEvent(event)

    def _log(self, msg: str, level: str = "info"):
        if hasattr(self, "log_panel"):
            self.log_panel.log(msg, level)
        else:
            log.info(msg)


def run(app_root: Optional[str] = None, startup_input: Optional[dict] = None) -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName("GhostRigger")
    app.setStyle("Fusion")
    for family in ("Consolas", "Lucida Console", "Courier New"):
        if family in QtGui.QFontDatabase.families():
            app.setFont(QtGui.QFont(family, 9))
            break
    win = QtGhostRiggerMainWindow(Path(app_root) if app_root else None, startup_input=startup_input)
    win.show()
    return app.exec()
