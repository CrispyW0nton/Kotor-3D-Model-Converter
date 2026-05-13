"""Qt main-window shell for GhostRigger.

This is the first migration step away from Tkinter.  Qt owns the main
application window and process event loop; legacy Tk tools are launched in a
separate process so Qt and Tk do not fight over GUI ownership in one process.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import traceback
import copy
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Tk fallback
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from .qt_library_panel import QtLibraryPanel
from .qt_log_panel import QtLogPanel
from .qt_matrix_background import QtMatrixEngine, QtMatrixLabel, QtMatrixPanel
from .qt_properties_panel import QtPropertiesPanel, QtSkeletonPanel
from .qt_viewport import QtViewportWidget
from .qt_animation_panel import QtAnimationLibraryPanel, QtAnimationsPanel
from .qt_blueprint_editor import QtBlueprintEditorPanel
from .qt_character_builder_panel import QtCharacterBuilderPanel, QtCharacterBuilderWindow
from .qt_diagnostics_panel import QtDiagnosticsPanel
from .qt_dialogs import show_about, show_format_reference, show_ipc_info
from .qt_modular_panel import QtModularModePanel
from .qt_normal_map_panel import QtNormalMapPanel
from .qt_resource_panel import QtResourceBrowserPanel, QtTwoDaBrowserPanel
from .qt_rig_panel import QtRigPanel
from .qt_settings_dialog import QtSettingsDialog, save_settings
from .qt_texture_panel import QtTexturePanel


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

_QT_ICON_DIR = (Path(__file__).resolve().parent / "icons").as_posix()


class ModelLoadWorker(QtCore.QObject):
    finished = QtCore.Signal(object, str, str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    @QtCore.Slot()
    def run(self):
        try:
            from src.core.kotor_loader import load_model_from_file

            model = load_model_from_file(self.path)
            self.finished.emit(model, self.path, "")
        except Exception:
            self.finished.emit(None, self.path, traceback.format_exc())


class ResourceModelLoadWorker(QtCore.QObject):
    finished = QtCore.Signal(object, str, str)

    def __init__(self, resref: str, game: str, k1_dir: str = "", k2_dir: str = ""):
        super().__init__()
        self.resref = resref
        self.game = game
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

            mdl = mgr.get_mdl(self.resref, self.game)
            if not mdl:
                raise FileNotFoundError(f"{self.game}:{self.resref}.mdl")
            mdx = mgr.get_mdx(self.resref, self.game) or b""
            model = load_model_from_bytes(mdl, mdx)
            model.game_version = GameVersion.K2 if self.game == "K2" else GameVersion.K1
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
            rows.sort(key=lambda item: (item["game"], item["resref"]))
            self.finished.emit(rows, "")
        except Exception:
            self.finished.emit([], traceback.format_exc())


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


class QtGhostRiggerMainWindow(QtWidgets.QMainWindow):
    APP_TITLE = "GhostRigger-K1-K2  //  Odyssey Engine Pipeline v6.1"
    APP_VERSION = "6.1.0"

    def __init__(self, app_root: Optional[Path] = None):
        super().__init__()
        self.app_root = app_root or Path(__file__).resolve().parents[2]
        self.settings_path = self.app_root / "settings.json"
        self.settings_data = self._load_settings()
        self._worker_thread: Optional[QtCore.QThread] = None
        self._scan_thread: Optional[QtCore.QThread] = None
        self._legacy_process: Optional[subprocess.Popen] = None
        self._library_rows: list[dict] = []
        self._current_model = None
        self._model_path = ""
        self._texture_dir = ""
        self._animation_engine = None
        self._animation_loop = False
        self._animation_last_tick: Optional[float] = None
        self._character_builder_window: Optional[QtCharacterBuilderWindow] = None
        self._matrix_engine = QtMatrixEngine(self, fps=12)
        self._animation_timer = QtCore.QTimer(self)
        self._animation_timer.setInterval(33)
        self._animation_timer.timeout.connect(self._tick_animation)

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
        self.open_ascii_action.triggered.connect(self._open_model)
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
        self.diag_action = QtGui.QAction("Run Diagnostics", self)
        self.diag_action.setShortcut("Ctrl+D")
        self.diag_action.triggered.connect(self._run_diagnostics_popup)
        self.info_action = QtGui.QAction("Model Info...", self)
        self.info_action.triggered.connect(self._show_model_info)
        self.refresh_action = QtGui.QAction("Refresh All", self)
        self.refresh_action.setShortcut("F5")
        self.refresh_action.triggered.connect(self._refresh_all)
        self.character_builder_action = QtGui.QAction(self._icon("charbuilder"), "Character Builder", self)
        self.character_builder_action.setShortcut("Ctrl+B")
        self.character_builder_action.triggered.connect(self._open_qt_character_builder_window)
        self.anims_action = QtGui.QAction(self._icon("anims"), "Animations", self)
        self.anims_action.setShortcut("Ctrl+A")
        self.anims_action.triggered.connect(lambda: self._show_right_tab("Animations"))
        self.modules_action = QtGui.QAction(self._icon("modular"), "Modules", self)
        self.modules_action.triggered.connect(self._show_modules_tab)
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
            self.wire_action,
            self.bones_action,
            self.texture_action,
            None,
            self.uv_action,
            None,
            self.diag_action,
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
        help_menu.addAction(about_action)
        help_menu.addAction(format_action)

        modules_menu = self.menuBar().addMenu("Modules")
        modules_menu.addAction(self.modules_action)
        modules_menu.addSeparator()
        modules_menu.addAction(self.port_model_action)
        modules_menu.addAction(self.generate_module_action)
        modules_menu.addSeparator()
        modules_menu.addAction(self.about_module_action)

        tools_menu = self.menuBar().addMenu("Tools")
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
        path = Path(__file__).resolve().parent / "icons" / f"{name}_{size}.png"
        if path.exists():
            return QtGui.QIcon(str(path))
        fallback = Path(__file__).resolve().parent / "icons" / f"{name}_24.png"
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

    def _build_layout(self):
        central = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(3, 0, 3, 3)
        root.setSpacing(0)
        self.setCentralWidget(central)

        root.addWidget(self._make_header())
        root.addWidget(self._make_command_bar())

        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)

        left_tabs = QtWidgets.QTabWidget()
        left_tabs.setUsesScrollButtons(True)
        left_tabs.setElideMode(QtCore.Qt.ElideRight)
        left_tabs.tabBar().setExpanding(False)
        self.left_tabs = left_tabs

        self.library_panel = QtLibraryPanel(self)
        self.library_panel.scanRequested.connect(self._scan_library)
        self.library_panel.deepScanRequested.connect(self._scan_library)
        self.library_panel.loadRequested.connect(self._start_resource_load)
        self.library_panel.dirsChanged.connect(self._on_library_dirs_changed)
        left_tabs.addTab(self.library_panel, self._icon("library", 16), "Library")

        right_tabs = QtWidgets.QTabWidget()
        right_tabs.setUsesScrollButtons(True)
        right_tabs.setElideMode(QtCore.Qt.ElideRight)
        right_tabs.tabBar().setExpanding(False)
        self.right_tabs = right_tabs
        self.skeleton_panel = QtSkeletonPanel(self)
        self.properties_panel = QtPropertiesPanel(self)
        self.skeleton_panel.nodeSelected.connect(self.properties_panel.show_node)
        self.rig_panel = QtRigPanel(self)
        self.rig_panel.rigActionRequested.connect(self._handle_rig_action)
        self.texture_panel = QtTexturePanel(self)
        self.normal_map_panel = QtNormalMapPanel(self)
        self.diagnostics_panel = QtDiagnosticsPanel(self._get_model, self)
        self.animations_panel = QtAnimationsPanel(self)
        self.animations_panel.animationActionRequested.connect(self._handle_animation_action)
        self.animation_library_panel = QtAnimationLibraryPanel(self)
        self.animation_library_panel.libraryActionRequested.connect(self._handle_animation_library_action)
        self.twoda_panel = QtTwoDaBrowserPanel(self)
        self.twoda_panel.refreshRequested.connect(self._refresh_twoda_panel)
        self.twoda_panel.tableSelected.connect(self._load_twoda_table)
        self.resource_panel = QtResourceBrowserPanel(self)
        self.resource_panel.scanRequested.connect(self._populate_resource_panel)
        self.resource_panel.resourceSelected.connect(self._preview_resource_row)
        self.resource_panel.resourceActivated.connect(self._activate_resource_row)
        self.character_builder_panel = QtCharacterBuilderPanel(self)
        self.modular_panel = QtModularModePanel(self)
        self.modular_panel.moduleActionRequested.connect(self._handle_module_action)
        self.blueprint_panel = QtBlueprintEditorPanel(self)
        left_tabs.addTab(self.skeleton_panel, self._icon("skeleton", 16), "Nodes")
        left_tabs.addTab(self.twoda_panel, self._icon("twoda", 16), "2DAs")
        left_tabs.addTab(self.resource_panel, self._icon("resources", 16), "Resources")
        left_tabs.addTab(self.modular_panel, self._icon("modular", 16), "Modules")
        main_splitter.addWidget(left_tabs)

        self.viewport = QtViewportWidget(self)
        self.viewport_label = self.viewport.canvas
        self.skeleton_panel.nodeSelected.connect(self.viewport.set_selected_node)
        self.viewport.nodeSelected.connect(self.properties_panel.show_node)
        self.properties_panel.positionApplied.connect(
            lambda node, _x, _y, _z: self.viewport.refresh_node_transform(node)
        )
        main_splitter.addWidget(self.viewport)

        right_tabs.addTab(self.properties_panel, self._icon("props", 16), "Properties")
        right_tabs.addTab(self.rig_panel, self._icon("rig", 16), "Rig")
        right_tabs.addTab(self.texture_panel, self._icon("texture", 16), "Texture")
        right_tabs.addTab(self.normal_map_panel, self._icon("normalmap", 16), "Normal")
        right_tabs.addTab(self.diagnostics_panel, self._icon("diag", 16), "Diag")
        right_tabs.addTab(self.animations_panel, self._icon("anims", 16), "Anims")
        right_tabs.addTab(self.animation_library_panel, self._icon("library", 16), "Anim Lib")
        right_tabs.addTab(self.character_builder_panel, self._icon("charbuilder", 16), "Builder")
        right_tabs.addTab(self.blueprint_panel, self._icon("library", 16), "Blueprint")
        main_splitter.addWidget(right_tabs)
        main_splitter.setSizes([420, 760, 380])
        root.addWidget(main_splitter, 1)

        self.log_panel = QtLogPanel(self)
        root.addWidget(self.log_panel, 0)

        # Compatibility placeholders for the already-migrated loading helpers.
        self.k1_dir_edit = QtWidgets.QLineEdit(str(self.settings_data.get("k1_dir") or ""))
        self.k2_dir_edit = QtWidgets.QLineEdit(str(self.settings_data.get("k2_dir") or ""))
        self.scan_button = QtWidgets.QPushButton("Scan")
        self.library_list = QtWidgets.QListWidget()
        self.library_filter = QtWidgets.QLineEdit()
        self.props_text = QtWidgets.QTextEdit()

        self.resource_panel.type_combo.currentTextChanged.connect(lambda _text: self._populate_resource_panel())
        self.resource_panel.search_edit.textChanged.connect(lambda _text: self._populate_resource_panel())

    @QtCore.Slot(str, str)
    def _on_library_dirs_changed(self, k1_dir: str, k2_dir: str):
        self.k1_dir_edit.setText(k1_dir)
        self.k2_dir_edit.setText(k2_dir)
        self.library_panel.set_status("Game directories updated")
        self._log("Game directories updated. Run Scan to refresh the library.", "success")

    def _build_statusbar(self):
        self.statusBar().showMessage("Ready")

    def _require_model(self, action: str):
        if self._current_model is None:
            QtWidgets.QMessageBox.information(self, action, "Load or import a model first.")
            return None
        return self._current_model

    def _set_model_internal(self, model, path: str = ""):
        if model is None:
            self._animation_timer.stop()
            self._animation_engine = None
            self._animation_last_tick = None
            self._current_model = None
            self._model_path = ""
            self.model_pill.setText("// No model loaded")
            self.statusBar().showMessage("Ready")
            if hasattr(self, "viewport"):
                self.viewport.set_model(None)
            if hasattr(self, "skeleton_panel"):
                self.skeleton_panel.load_model(None)
            if hasattr(self, "properties_panel"):
                self.properties_panel.show_model(None)
            if hasattr(self, "animations_panel"):
                self.animations_panel.load_model(None)
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
            self.viewport.load_model(model, self._texture_dir)
        if hasattr(self, "skeleton_panel"):
            self.skeleton_panel.load_model(model)
        if hasattr(self, "properties_panel"):
            self.properties_panel.show_model(model)
        if hasattr(self, "animations_panel"):
            self.animations_panel.load_model(model)
        self._animation_engine = None
        self._animation_timer.stop()
        self._animation_last_tick = None
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

    def _handle_rig_action(self, action: str):
        if action == "Auto-Rig Model":
            self._quick_autorig()
        elif action == "Remove Rigging":
            self._remove_rig()
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
            from src.core.mdl_porter import MDLBinaryWriter
            from src.core.model_data import GameVersion

            mdl = copy.deepcopy(model)
            mdl.game_version = GameVersion.K2 if chosen_gv == "K2" else GameVersion.K1
            mdx_path = str(Path(path).with_suffix(".mdx"))
            MDLBinaryWriter().write(mdl, path, mdx_path)
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
            from src.core.mdl_porter import MDLBinaryWriter

            model = build_humanoid_template(game_version=chosen_gv, name=Path(path).stem)
            mdx_path = str(Path(path).with_suffix(".mdx"))
            MDLBinaryWriter().write(model, path, mdx_path)
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
            self._log(f"Generated starter module files for {mod} in {output}", "success")
        except Exception as exc:
            self._log(f"Module generation error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Module Generation Error", str(exc))

    def _handle_module_action(self, action: str):
        if action in {"Generate Module Files", "Validate Module", "Open Output"}:
            if action == "Generate Module Files":
                self._generate_module_files()
            else:
                self._log(f"{action} needs a generated/open module workspace first.", "warning")
            return
        if action in {"Port K1 to K2", "Port K2 to K1"}:
            self._port_current_model()
            return
        self._log(f"{action} is waiting for deeper Qt module-editor migration.", "warning")

    def _handle_animation_action(self, action: str, anim_name: str):
        model = self._require_model("Animations")
        if model is None:
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
        except Exception as exc:
            self._log(f"Animation action error: {exc}", "error")
            QtWidgets.QMessageBox.critical(self, "Animations", str(exc))

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
            self._show_right_tab("Animations")
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
        rows = []
        for row in self._library_rows:
            rows.append(
                {
                    "game": row.get("game", ""),
                    "resref": row.get("resref", ""),
                    "source": row.get("source", ""),
                    "type": "mdl",
                }
            )
        self.resource_panel.set_resources(rows)
        self.resource_panel.text_preview.setPlainText(f"{len(rows)} model resources indexed from the library scan.")

    def _preview_resource_row(self, row: dict):
        text = "\n".join(
            [
                f"Resource: {row.get('resref', '')}.{row.get('type', '')}",
                f"Game:     {row.get('game', '')}",
                f"Source:   {row.get('source', '')}",
                "",
                "Double-click loading will be wired when the resource browser is expanded beyond model rows.",
            ]
        )
        self.resource_panel.text_preview.setPlainText(text)
        raw = repr(row).encode("utf-8")
        self.resource_panel.hex_preview.setPlainText(" ".join(f"{byte:02x}" for byte in raw))

    def _activate_resource_row(self, row: dict):
        if str(row.get("type", "")).lower() == "mdl" and row.get("resref") and row.get("game"):
            self._start_resource_load(str(row["resref"]), str(row["game"]))
        else:
            self._log(f"No activation handler for {row.get('resref', 'resource')}", "warning")

    def _refresh_twoda_panel(self, game: str):
        self.twoda_panel.listbox.clear()
        self.twoda_panel.table.clear()
        try:
            from src.resources.game_library import GameLibrary

            lib = GameLibrary()
            k1_dir = self.k1_dir_edit.text().strip()
            k2_dir = self.k2_dir_edit.text().strip()
            if k1_dir:
                lib.set_k1_dir(k1_dir)
            if k2_dir:
                lib.set_k2_dir(k2_dir)
            names = lib.list_2da_names(game)
            self.twoda_panel.listbox.addItems(names)
            self._log(f"2DA list refreshed: {len(names)} tables for {game}", "success")
        except Exception as exc:
            self._log(f"2DA refresh error: {exc}", "error")

    def _load_twoda_table(self, game: str, name: str):
        if not name:
            return
        try:
            from src.resources.game_library import GameLibrary

            lib = GameLibrary()
            k1_dir = self.k1_dir_edit.text().strip()
            k2_dir = self.k2_dir_edit.text().strip()
            if k1_dir:
                lib.set_k1_dir(k1_dir)
            if k2_dir:
                lib.set_k2_dir(k2_dir)
            table = lib.get_2da(name, game)
            if table is None:
                self._log(f"2DA not found: {game}:{name}", "warning")
                return
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

    def _populate_saved_dirs(self):
        self.library_list.clear()
        for key, label in (("k1_dir", "KotOR 1"), ("k2_dir", "KotOR 2")):
            value = str(self.settings_data.get(key) or "").strip()
            if value:
                self.library_list.addItem(f"{label}: {value}")
        if self.library_list.count() == 0:
            self.library_list.addItem("No saved game directories yet")

    def _scan_library(self):
        if self._scan_thread is not None and self._scan_thread.isRunning():
            return
        k1_dir = self.k1_dir_edit.text().strip()
        k2_dir = self.k2_dir_edit.text().strip()
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
        self._scan_thread = thread
        thread.start()

    @QtCore.Slot(list, str)
    def _on_library_scanned(self, rows: list, error: str):
        self.scan_button.setEnabled(True)
        if error:
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
        self._populate_resource_panel()
        self._populate_animation_library_from_current_model()
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
        if self._worker_thread is not None and self._worker_thread.isRunning():
            self._log("A model is already loading.", "warning")
            return
        self._log(f"Loading {game}:{resref} ...")
        self.statusBar().showMessage(f"Loading {game}:{resref}...")

        worker = ResourceModelLoadWorker(
            resref,
            game,
            self.k1_dir_edit.text().strip(),
            self.k2_dir_edit.text().strip(),
        )
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_model_loaded)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._worker_thread = thread
        thread.start()

    def _open_model(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open KotOR MDL",
            str(Path(self.settings_data.get("last_import") or self.app_root)),
            "KotOR MDL (*.mdl);;All files (*.*)",
        )
        if not path:
            return
        self._log(f"Loading {path} ...")
        self.statusBar().showMessage("Loading model...")

        worker = ModelLoadWorker(path)
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_model_loaded)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._worker_thread = thread
        thread.start()

    @QtCore.Slot(object, str, str)
    def _on_model_loaded(self, model, path: str, error: str):
        if error:
            self._log(f"Model load failed:\n{error}", "error")
            self.statusBar().showMessage("Model load failed")
            return
        self._current_model = model
        if path:
            self._model_path = path
            if not str(path).startswith(("K1:", "K2:")):
                self._texture_dir = str(Path(path).parent)
        mesh_count = len(model.mesh_nodes()) if hasattr(model, "mesh_nodes") else 0
        node_count = model.node_count() if hasattr(model, "node_count") else 0
        anim_count = len(getattr(model, "animations", []) or [])
        name = getattr(model, "name", Path(path).stem)
        if hasattr(self, "viewport"):
            self.viewport.load_model(model, self._texture_dir)
        else:
            self.viewport_label.setText(f"{name}\n\nQt viewport host\n{mesh_count} mesh | {node_count} nodes")
        self.model_pill.setText(f"// {name}")
        if hasattr(self, "skeleton_panel"):
            self.skeleton_panel.load_model(model)
        if hasattr(self, "properties_panel"):
            self.properties_panel.show_model(model)
        if hasattr(self, "animations_panel"):
            self.animations_panel.load_model(model)
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
        self._log(f"Loaded {name} ({mesh_count} mesh, {node_count} nodes)", "success")
        self.statusBar().showMessage(f"Loaded {name}")

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


def run(app_root: Optional[str] = None) -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName("GhostRigger")
    app.setStyle("Fusion")
    win = QtGhostRiggerMainWindow(Path(app_root) if app_root else None)
    win.show()
    return app.exec()
