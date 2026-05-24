"""Unreal animator window for targeting SKM_Quinn_Simple."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.qt_core.animation.animation_engine import AnimationEngine
from src.core.qt_core.geometry.model_data import ModelNode, NodeFlags, is_animation_supermodel
from src.unreal.animation_retargeting import build_bone_map, retarget_animation, retarget_pose
from src.unreal import UnrealSkeletonAsset, load_quinn_fbx_model, load_quinn_skeleton_asset, unreal_skeleton_model

from src.gui.qt_lib.rendering.qt_gpu_renderer import create_viewport_renderer
from src.gui.qt_lib.rendering.renderer_settings import RendererSettings
from src.gui.qt_lib.assets.qt_theme import heading
from src.gui.qt_lib.panels.qt_ue5_rig_export_panel import QtUE5RigExportPanel
from src.gui.qt_lib.viewports.qt_viewport import QtUnrealAnimatorViewportWidget
from src.gui.qt_lib.rendering.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE


_UNREAL_STYLE = """
QMainWindow#UnrealAnimatorWindow {
    background: #101214;
    color: #d8dde6;
}
QMainWindow#UnrealAnimatorWindow QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 9pt;
}
QMainWindow#UnrealAnimatorWindow QMenuBar,
QMainWindow#UnrealAnimatorWindow QMenu,
QMainWindow#UnrealAnimatorWindow QStatusBar {
    background: #15181d;
    color: #cdd6e5;
    border: 0;
}
QMainWindow#UnrealAnimatorWindow QMenuBar {
    border-bottom: 1px solid #2b313a;
    padding: 2px 8px;
}
QMainWindow#UnrealAnimatorWindow QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
}
QMainWindow#UnrealAnimatorWindow QMenuBar::item:selected,
QMainWindow#UnrealAnimatorWindow QMenu::item:selected {
    background: #26384f;
    color: #74b7ff;
}
QMainWindow#UnrealAnimatorWindow QSplitter::handle {
    background: #242a32;
}
QMainWindow#UnrealAnimatorWindow QSplitter::handle:hover {
    background: #2d6fb3;
}
QMainWindow#UnrealAnimatorWindow QWidget#UnrealPanel,
QMainWindow#UnrealAnimatorWindow QWidget#UnrealViewportPanel {
    background: #181b20;
    border: 1px solid #303741;
    border-radius: 4px;
}
QMainWindow#UnrealAnimatorWindow QWidget#UnrealViewportCell {
    background: #12151a;
    border: 1px solid #2a313a;
    border-radius: 4px;
}
QMainWindow#UnrealAnimatorWindow QWidget#TimelineStrip {
    background: #15191f;
    border-top: 1px solid #2a313a;
}
QMainWindow#UnrealAnimatorWindow QLabel {
    background: transparent;
    color: #d8dde6;
}
QMainWindow#UnrealAnimatorWindow QLabel[heading="true"] {
    color: #74b7ff;
    font-weight: 700;
}
QMainWindow#UnrealAnimatorWindow QLabel[meta="true"] {
    color: #96a3b5;
}
QMainWindow#UnrealAnimatorWindow QLabel#SelectedAnimationPill {
    background: #10141a;
    color: #74b7ff;
    border: 1px solid #2d6fb3;
    border-radius: 4px;
    padding: 4px 8px;
}
QMainWindow#UnrealAnimatorWindow QLineEdit,
QMainWindow#UnrealAnimatorWindow QComboBox,
QMainWindow#UnrealAnimatorWindow QPlainTextEdit,
QMainWindow#UnrealAnimatorWindow QListWidget,
QMainWindow#UnrealAnimatorWindow QTreeWidget {
    background: #10141a;
    color: #d8dde6;
    border: 1px solid #303741;
    selection-background-color: #1f5f9f;
    selection-color: #ffffff;
}
QMainWindow#UnrealAnimatorWindow QLineEdit,
QMainWindow#UnrealAnimatorWindow QComboBox {
    padding: 5px 7px;
    border-radius: 3px;
}
QMainWindow#UnrealAnimatorWindow QLineEdit:focus,
QMainWindow#UnrealAnimatorWindow QComboBox:focus,
QMainWindow#UnrealAnimatorWindow QPlainTextEdit:focus,
QMainWindow#UnrealAnimatorWindow QListWidget:focus,
QMainWindow#UnrealAnimatorWindow QTreeWidget:focus {
    border-color: #2d8cff;
}
QMainWindow#UnrealAnimatorWindow QHeaderView::section {
    background: #20252d;
    color: #b9c5d6;
    border: 0;
    border-right: 1px solid #303741;
    border-bottom: 1px solid #303741;
    padding: 5px 6px;
    font-weight: 600;
}
QMainWindow#UnrealAnimatorWindow QTreeView::item,
QMainWindow#UnrealAnimatorWindow QListView::item {
    min-height: 22px;
}
QMainWindow#UnrealAnimatorWindow QTreeView::item:hover,
QMainWindow#UnrealAnimatorWindow QListView::item:hover {
    background: #1b2736;
}
QMainWindow#UnrealAnimatorWindow QPushButton {
    background: #242a32;
    color: #d8dde6;
    border: 1px solid #3a424e;
    border-radius: 3px;
    padding: 5px 10px;
}
QMainWindow#UnrealAnimatorWindow QPushButton:hover {
    background: #2b3542;
    border-color: #4f83b9;
    color: #ffffff;
}
QMainWindow#UnrealAnimatorWindow QPushButton:pressed {
    background: #1c222a;
}
QMainWindow#UnrealAnimatorWindow QPushButton:disabled {
    background: #181b20;
    color: #687386;
    border-color: #2a3038;
}
QMainWindow#UnrealAnimatorWindow QPushButton[accent="true"] {
    background: #0f5fa8;
    color: #ffffff;
    border-color: #2d8cff;
    font-weight: 700;
}
QMainWindow#UnrealAnimatorWindow QPushButton[accent="true"]:hover {
    background: #1473c9;
}
QMainWindow#UnrealAnimatorWindow QPushButton[accent="true"]:disabled {
    background: #181b20;
    color: #687386;
    border-color: #2a3038;
    font-weight: 400;
}
QMainWindow#UnrealAnimatorWindow QSlider::groove:horizontal {
    height: 5px;
    background: #2a313a;
    border-radius: 2px;
}
QMainWindow#UnrealAnimatorWindow QSlider::sub-page:horizontal {
    background: #2d8cff;
    border-radius: 2px;
}
QMainWindow#UnrealAnimatorWindow QSlider::handle:horizontal {
    background: #d8dde6;
    border: 1px solid #74b7ff;
    width: 12px;
    margin: -5px 0;
    border-radius: 6px;
}
"""

_SOURCE_BRIDGE_QUINN_ROLES = frozenset({"deform", "twist"})


class QtUnrealAnimatorWindow(QtWidgets.QMainWindow):
    """Animator for retargeting KotOR supermodel clips to Unreal skeletons."""

    sourceLoadRequested = QtCore.Signal(dict)
    reloadCodeRequested = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("UnrealAnimatorWindow")
        self.setWindowTitle("Unreal Animator - SKM_Quinn_Simple")
        self.setStyleSheet(_UNREAL_STYLE)
        self.resize(1380, 860)
        self.setMinimumSize(940, 620)
        self._navigation_profile = DEFAULT_VIEWPORT_NAVIGATION_PROFILE
        self._renderer_settings = RendererSettings.from_settings(getattr(parent, "settings_data", {}) or {})
        self._library_rows: list[dict] = []
        self._source_model = None
        self._source_game = ""
        self._target_asset: UnrealSkeletonAsset = load_quinn_skeleton_asset()
        self._target_model = unreal_skeleton_model(self._target_asset)
        self._mapping_report = None
        self._manual_mapping: dict[str, str] = {}
        self._updating_mapping = False
        self._preview_engine: Optional[AnimationEngine] = None
        self._preview_last_tick: Optional[float] = None
        self._animation_gpu_restore_state: Optional[tuple[bool, bool]] = None
        self._preview_timer = QtCore.QTimer(self)
        self._preview_timer.setInterval(16)
        self._preview_timer.timeout.connect(self._tick_preview)
        self._build_actions()
        self._build_menu()
        self._build_statusbar()
        self._build_central()
        self.set_target_asset(self._target_asset)

    def _build_actions(self) -> None:
        self.close_action = QtGui.QAction("Close", self)
        self.close_action.setShortcut("Ctrl+W")
        self.close_action.triggered.connect(self.close)
        self.refresh_mapping_action = QtGui.QAction("Refresh Mapping", self)
        self.refresh_mapping_action.setShortcut("F5")
        self.refresh_mapping_action.triggered.connect(self.refresh_mapping)
        self.frame_source_action = QtGui.QAction("Frame Source", self)
        self.frame_source_action.triggered.connect(lambda: self.source_viewport.frame_all())
        self.frame_target_action = QtGui.QAction("Frame Target", self)
        self.frame_target_action.triggered.connect(lambda: self.target_viewport.frame_all())
        self.import_target_fbx_action = QtGui.QAction("Import Target FBX", self)
        self.import_target_fbx_action.triggered.connect(lambda *_: self.import_target_fbx())
        self.reload_code_action = QtGui.QAction("Reload Animator Code", self)
        self.reload_code_action.setShortcut("Ctrl+Shift+R")
        self.reload_code_action.triggered.connect(self.reloadCodeRequested.emit)
        self.preview_action = QtGui.QAction("Preview", self)
        self.preview_action.setShortcut("Ctrl+Space")
        self.preview_action.triggered.connect(self.preview_selected_animation)
        self.cycle_gizmo_action = QtGui.QAction("Cycle Gizmo Mode", self)
        self.cycle_gizmo_action.setShortcut("Space")
        self.cycle_gizmo_action.setShortcutContext(QtCore.Qt.WindowShortcut)
        self.cycle_gizmo_action.triggered.connect(self._cycle_animator_gizmo)
        self.stop_action = QtGui.QAction("Stop", self)
        self.stop_action.triggered.connect(self.stop_preview)
        self.bake_action = QtGui.QAction("Bake Animation", self)
        self.bake_action.triggered.connect(self.bake_selected_animation)
        self.export_action = QtGui.QAction("Export FBX Animation", self)
        self.export_action.triggered.connect(self.export_fbx_animation)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.close_action)
        unreal_menu = self.menuBar().addMenu("Unreal")
        unreal_menu.addAction(self.import_target_fbx_action)
        unreal_menu.addAction(self.refresh_mapping_action)
        unreal_menu.addAction(self.reload_code_action)
        unreal_menu.addSeparator()
        unreal_menu.addAction(self.cycle_gizmo_action)
        unreal_menu.addAction(self.preview_action)
        unreal_menu.addAction(self.stop_action)
        unreal_menu.addAction(self.bake_action)
        unreal_menu.addAction(self.export_action)
        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.frame_source_action)
        view_menu.addAction(self.frame_target_action)

    def _build_statusbar(self) -> None:
        self.statusBar().showMessage("Ready")

    def _build_central(self) -> None:
        root = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        root.setObjectName("UnrealRootSplitter")
        root.setChildrenCollapsible(False)

        self.source_viewport = QtUnrealAnimatorViewportWidget(self)
        self.target_viewport = QtUnrealAnimatorViewportWidget(self)
        self.source_viewport.set_animation_supermodel_hud_placement("bottom")
        for viewport in (self.source_viewport, self.target_viewport):
            viewport.set_hidden_bone_name_fragments(("dummy", "hook"))
        self.source_viewport.set_renderer_settings(self._renderer_settings)
        self.target_viewport.set_renderer_settings(self._renderer_settings)
        self._shared_gpu_renderer = create_viewport_renderer(self._renderer_settings)
        self.source_viewport.set_shared_gpu_renderer(self._shared_gpu_renderer)
        self.target_viewport.set_shared_gpu_renderer(self._shared_gpu_renderer)
        self.source_viewport.set_dual_viewport_mode(True)
        self.target_viewport.set_dual_viewport_mode(True)
        self.source_viewport.set_navigation_profile(self._navigation_profile)
        self.target_viewport.set_navigation_profile(self._navigation_profile)

        top_split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        top_split.setObjectName("UnrealTopSplitter")
        top_split.setChildrenCollapsible(False)
        top_split.addWidget(self._source_group())
        top_split.addWidget(self._viewport_group())
        top_split.addWidget(self._target_group())
        top_split.setStretchFactor(0, 0)
        top_split.setStretchFactor(1, 1)
        top_split.setStretchFactor(2, 0)
        top_split.setSizes([260, 820, 300])

        root.addWidget(top_split)
        root.addWidget(self._mapping_group())
        root.setStretchFactor(0, 1)
        root.setStretchFactor(1, 0)
        root.setSizes([500, 300])
        self.setCentralWidget(root)

    def set_renderer_settings(self, settings: RendererSettings | dict | None) -> None:
        self._renderer_settings = settings if isinstance(settings, RendererSettings) else RendererSettings.from_settings(settings or {})
        apply_settings = getattr(getattr(self, "_shared_gpu_renderer", None), "set_settings", None)
        if callable(apply_settings):
            apply_settings(self._renderer_settings)
        for viewport in (getattr(self, "source_viewport", None), getattr(self, "target_viewport", None)):
            if viewport is not None:
                viewport.set_renderer_settings(self._renderer_settings)

    def _source_group(self) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget()
        box.setObjectName("UnrealPanel")
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        box.setMinimumWidth(190)
        box.setMaximumWidth(360)
        layout.addWidget(heading("KotOR Supermodel Library"))

        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)
        layout.addWidget(tabs, 1)

        library_tab = QtWidgets.QWidget()
        library_layout = QtWidgets.QVBoxLayout(library_tab)
        library_layout.setContentsMargins(0, 0, 0, 0)
        library_layout.setSpacing(6)
        tools = QtWidgets.QHBoxLayout()
        self.source_filter = QtWidgets.QLineEdit()
        self.source_filter.setPlaceholderText("Filter supermodels")
        self.source_filter.textChanged.connect(self._populate_source_library)
        self.load_source_button = QtWidgets.QPushButton("Load Source")
        self.load_source_button.setProperty("accent", True)
        self.load_source_button.clicked.connect(self._request_selected_source)
        tools.addWidget(self.source_filter, 1)
        tools.addWidget(self.load_source_button)
        library_layout.addLayout(tools)
        self.source_tree = QtWidgets.QTreeWidget()
        self.source_tree.setHeaderLabels(["Game", "Supermodel", "Animations", "Nodes"])
        self.source_tree.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.source_tree.itemDoubleClicked.connect(lambda *_args: self._request_selected_source())
        library_layout.addWidget(self.source_tree, 1)
        tabs.addTab(library_tab, "Library")

        bones_tab = QtWidgets.QWidget()
        bones_layout = QtWidgets.QVBoxLayout(bones_tab)
        bones_layout.setContentsMargins(0, 0, 0, 0)
        bones_layout.setSpacing(6)
        bone_tools = QtWidgets.QHBoxLayout()
        self.add_source_synthetic_button = QtWidgets.QPushButton("Add Synthetic")
        self.add_source_synthetic_button.setToolTip("Add a synthetic source bone under the selected KotOR source bone")
        self.add_source_synthetic_button.clicked.connect(lambda *_: self._prompt_add_source_synthetic_bone())
        self.insert_source_synthetic_button = QtWidgets.QPushButton("Insert Before")
        self.insert_source_synthetic_button.setToolTip("Insert a synthetic source bone between the selected bone and its parent")
        self.insert_source_synthetic_button.clicked.connect(lambda *_: self._prompt_insert_source_synthetic_bone())
        self.delete_source_synthetic_button = QtWidgets.QPushButton("Delete Synthetic")
        self.delete_source_synthetic_button.setToolTip("Delete the selected synthetic source bone")
        self.delete_source_synthetic_button.clicked.connect(lambda *_: self._delete_selected_source_synthetic_bone())
        bone_tools.addWidget(self.add_source_synthetic_button)
        bone_tools.addWidget(self.insert_source_synthetic_button)
        bone_tools.addWidget(self.delete_source_synthetic_button)
        bones_layout.addLayout(bone_tools)
        self.source_bones = QtWidgets.QTreeWidget()
        self.source_bones.setHeaderLabels(["Bone", "Parent", "Role"])
        self.source_bones.currentItemChanged.connect(self._on_source_bone_selected)
        bones_layout.addWidget(self.source_bones, 1)
        tabs.addTab(bones_tab, "Source Bones")

        self.ue5_rig_export_panel = QtUE5RigExportPanel(self)
        self.ue5_rig_export_panel.exportCompleted.connect(self._on_ue5_rig_export_completed)
        tabs.addTab(self.ue5_rig_export_panel, "UE5 Rig Export")
        return box

    def _viewport_group(self) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget()
        box.setObjectName("UnrealViewportPanel")
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        box.setMinimumWidth(320)
        layout.addWidget(heading("Preview Viewports"))

        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.addWidget(self._single_viewport_group("KotOR Source", self.source_viewport, source=True))
        split.addWidget(self._single_viewport_group("SKM_Quinn_Simple Target", self.target_viewport, source=False))
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        split.setSizes([410, 410])
        layout.addWidget(split, 1)
        return box

    def _single_viewport_group(
        self,
        title: str,
        viewport: QtUnrealAnimatorViewportWidget,
        *,
        source: bool,
    ) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget()
        box.setObjectName("UnrealViewportCell")
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)
        title_label = QtWidgets.QLabel(title)
        title_label.setProperty("heading", True)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        status = QtWidgets.QLabel("No source loaded" if source else "SKM_Quinn_Simple")
        status.setProperty("meta", True)
        status.setWordWrap(True)
        if source:
            self.source_label = status
        else:
            self.target_label = status
        layout.addWidget(status)
        viewport.setMinimumSize(140, 130)
        layout.addWidget(viewport, 1)
        framebar = self._framebar(source=source)
        layout.addWidget(framebar, 0)
        return box

    def _framebar(self, *, source: bool) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget()
        box.setObjectName("TimelineStrip")
        row = QtWidgets.QHBoxLayout(box)
        row.setContentsMargins(6, 4, 6, 2)
        row.setSpacing(6)
        label = QtWidgets.QLabel("0 / 0f")
        label.setMinimumWidth(62)
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(0, 1000)
        slider.setSingleStep(1)
        slider.setPageStep(33)
        slider.setEnabled(False)
        slider.setToolTip("Scrub animation frame")
        slider.valueChanged.connect(self._scrub_preview)
        row.addWidget(slider, 1)
        row.addWidget(label)
        if source:
            self.source_frame_slider = slider
            self.source_frame_label = label
        else:
            self.target_frame_slider = slider
            self.target_frame_label = label
        return box

    def _target_group(self) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget()
        box.setObjectName("UnrealPanel")
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        box.setMinimumWidth(220)
        box.setMaximumWidth(460)
        header = QtWidgets.QHBoxLayout()
        header.addWidget(heading("Unreal Target"), 1)
        self.import_fbx_button = QtWidgets.QPushButton("Import FBX")
        self.import_fbx_button.setProperty("accent", True)
        self.import_fbx_button.setToolTip("Import SKM_Quinn_Simple.FBX into the target viewport")
        self.import_fbx_button.clicked.connect(lambda *_: self.import_target_fbx())
        header.addWidget(self.import_fbx_button)
        layout.addLayout(header)
        self.target_info = QtWidgets.QPlainTextEdit()
        self.target_info.setReadOnly(True)
        self.target_info.setMaximumHeight(104)
        layout.addWidget(self.target_info)
        self.target_bones = QtWidgets.QTreeWidget()
        self.target_bones.setHeaderLabels(["#", "Bone", "Side", "Group", "Role"])
        self.target_bones.currentItemChanged.connect(self._on_target_bone_selected)
        layout.addWidget(self.target_bones, 1)
        return box

    def _mapping_group(self) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget()
        box.setObjectName("UnrealPanel")
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        header = QtWidgets.QHBoxLayout()
        header.addWidget(heading("Retarget Plan"), 1)
        self.selected_anim_label = QtWidgets.QLabel("No animation selected")
        self.selected_anim_label.setObjectName("SelectedAnimationPill")
        self.selected_anim_label.setMinimumWidth(160)
        header.addWidget(self.selected_anim_label)
        self.reload_code_button = QtWidgets.QPushButton("Reload Code")
        self.reload_code_button.setToolTip("Reload Unreal Animator Python modules and rebuild this window")
        self.reload_code_button.clicked.connect(self.reload_code_action.trigger)
        header.addWidget(self.reload_code_button)
        self.preview_button = QtWidgets.QPushButton("Preview")
        self.preview_button.setProperty("accent", True)
        self.preview_button.clicked.connect(self.preview_selected_animation)
        self.preview_button.setEnabled(False)
        self.stop_button = QtWidgets.QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_preview)
        self.stop_button.setEnabled(False)
        self.bake_button = QtWidgets.QPushButton("Bake Animation")
        self.bake_button.clicked.connect(self.bake_selected_animation)
        self.bake_button.setEnabled(False)
        self.export_button = QtWidgets.QPushButton("Export FBX Animation")
        self.export_button.setProperty("accent", True)
        self.export_button.clicked.connect(self.export_fbx_animation)
        self.export_button.setEnabled(False)
        header.addWidget(self.preview_button)
        header.addWidget(self.stop_button)
        header.addWidget(self.bake_button)
        header.addWidget(self.export_button)
        layout.addLayout(header)

        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        split.setChildrenCollapsible(False)
        self.anim_list = QtWidgets.QListWidget()
        self.anim_list.currentItemChanged.connect(lambda *_: self._on_animation_selection_changed())
        self.mapping_tree = QtWidgets.QTreeWidget()
        self.mapping_tree.setHeaderLabels(["KotOR Bone", "Quinn Bone"])
        self.mapping_tree.setAlternatingRowColors(True)
        self.mapping_info = QtWidgets.QPlainTextEdit()
        self.mapping_info.setReadOnly(True)
        split.addWidget(self.anim_list)
        split.addWidget(self.mapping_tree)
        split.addWidget(self.mapping_info)
        split.setSizes([300, 560, 320])
        layout.addWidget(split, 1)
        return box

    def set_navigation_profile(self, profile: object) -> None:
        self._navigation_profile = profile or DEFAULT_VIEWPORT_NAVIGATION_PROFILE
        if hasattr(self, "source_viewport"):
            self.source_viewport.set_navigation_profile(self._navigation_profile)
        if hasattr(self, "target_viewport"):
            self.target_viewport.set_navigation_profile(self._navigation_profile)

    def _on_ue5_rig_export_completed(self, result: object) -> None:
        if bool(getattr(result, "success", False)):
            path = getattr(result, "fbx_path", None)
            self.statusBar().showMessage(f"UE5 Rig Export PASS: {path}")
        else:
            reason = getattr(result, "halt_reason", None) or "export failed"
            self.statusBar().showMessage(f"UE5 Rig Export HALT: {reason}")

    def set_supermodel_library(self, rows: list[dict]) -> None:
        self._library_rows = [
            dict(row)
            for row in rows
            if str(row.get("resref", "") or "").lower().startswith("s_")
        ]
        self._populate_source_library()

    def set_source_model(self, model, game_tag: str = "") -> None:
        model = self._prepare_source_supermodel(model)
        self._source_model = model
        self._source_game = (game_tag or self._source_game or "").upper()
        self._manual_mapping.clear()
        self.source_label.setText(self._source_label_text(model))
        self.source_label.setToolTip(self._source_label_tooltip(model))
        self._populate_source_bones()
        self.anim_list.blockSignals(True)
        self.anim_list.clear()
        for anim in getattr(model, "animations", []) or [] if model else []:
            self.anim_list.addItem(str(getattr(anim, "name", anim)))
        selected_row = -1
        if self.anim_list.count() > 0:
            pause_row = 0
            for row in range(self.anim_list.count()):
                item = self.anim_list.item(row)
                if item is not None and item.text().lower() == "pause1":
                    pause_row = row
                    break
            selected_row = pause_row
            self.anim_list.setCurrentRow(selected_row)
        self.anim_list.blockSignals(False)
        self.source_viewport.set_selected_node(None)
        self.source_viewport.load_model(model)
        self.refresh_mapping()
        if selected_row >= 0:
            self._on_animation_selection_changed()
        self._update_playback_controls()

    def _prepare_source_supermodel(self, model):
        if model is None or not is_animation_supermodel(model):
            return model
        self._clear_source_quinn_marks(model)
        self._remove_source_quinn_synthetic_bones(model)
        self._ensure_source_spine_g(model)
        return model

    def _clear_source_quinn_marks(self, model) -> None:
        if model is None or not hasattr(model, "all_nodes"):
            return
        for node in model.all_nodes():
            setattr(node, "_ghostrigger_unreal_effective_source", False)
            if bool(getattr(node, "_ghostrigger_unreal_animator_hidden", False)):
                setattr(node, "_hide_skeleton_overlay", False)
                setattr(node, "_ghostrigger_unreal_animator_hidden", False)

    def _remove_source_quinn_synthetic_bones(self, model) -> int:
        if model is None or not hasattr(model, "all_nodes"):
            return 0
        removed = 0
        for node in reversed(list(model.all_nodes())):
            if not bool(getattr(node, "_ghostrigger_synthetic_unreal_target", False)):
                continue
            parent = getattr(node, "parent", None)
            children = list(getattr(node, "children", []) or [])
            child_world = [(child, self._node_world_position(child)) for child in children]
            parent_world = self._node_world_position(parent) if parent is not None else (0.0, 0.0, 0.0)
            insert_at = 0
            if parent is not None and node in parent.children:
                insert_at = parent.children.index(node)
                parent.children.pop(insert_at)
            for child, world_pos in child_world:
                child.parent = parent
                if parent is not None:
                    child.position = tuple(float(a) - float(b) for a, b in zip(world_pos, parent_world))
                    parent.children.insert(insert_at, child)
                    insert_at += 1
                else:
                    child.position = world_pos
            node.children = []
            node.parent = None
            removed += 1
        return removed

    def _ensure_source_quinn_bridge_bones(self, model) -> int:
        target_model = getattr(self, "_target_model", None)
        target_asset = getattr(self, "_target_asset", None)
        if model is None or target_model is None or target_asset is None:
            return 0
        if not hasattr(model, "find_node") or not hasattr(model, "all_nodes") or not hasattr(target_model, "all_nodes"):
            return 0

        report = build_bone_map(model, target_model)
        source_nodes = {
            self._node_name_key(node): node
            for node in model.all_nodes()
            if self._node_name_key(node)
        }
        source_by_target: dict[str, object] = {}
        for source_key, target_key in report.mapping.items():
            source_node = source_nodes.get(str(source_key or "").lower())
            if source_node is not None:
                source_by_target.setdefault(str(target_key or "").lower(), source_node)

        target_nodes = {
            self._node_name_key(node): node
            for node in target_model.all_nodes()
            if self._node_name_key(node)
        }
        target_roles = {
            str(bone.name or "").strip().lower(): str(bone.role or "").strip().lower()
            for bone in target_asset.bones
        }
        added = 0
        for target_node in target_model.all_nodes():
            target_key = self._node_name_key(target_node)
            source_child = source_by_target.get(target_key)
            if source_child is None:
                continue
            ancestor = self._nearest_mapped_target_ancestor(target_node, source_by_target)
            if ancestor is None:
                continue
            ancestor_key = self._node_name_key(ancestor)
            source_parent = source_by_target.get(ancestor_key)
            if source_parent is None or source_parent is source_child:
                continue
            if not self._can_thread_bridge_between_source_nodes(source_parent, source_child):
                continue

            bridge_targets = [
                item
                for item in self._target_chain_between(ancestor, target_node)
                if self._should_synthesize_quinn_bridge_bone(self._node_name_key(item), target_roles)
            ]
            if not bridge_targets:
                continue
            added += self._insert_source_bridge_chain(source_parent, source_child, bridge_targets, source_by_target, target_roles)
        return added

    @classmethod
    def _should_synthesize_quinn_bridge_bone(cls, target_key: str, target_roles: dict[str, str]) -> bool:
        key = str(target_key or "").strip().lower()
        if not key or cls._is_source_null_helper_name(key):
            return False
        role = target_roles.get(key, "")
        return role in _SOURCE_BRIDGE_QUINN_ROLES

    @classmethod
    def _nearest_mapped_target_ancestor(cls, target_node, source_by_target: dict[str, object]):
        parent = getattr(target_node, "parent", None)
        visited: set[int] = set()
        while parent is not None:
            parent_id = id(parent)
            if parent_id in visited:
                return None
            visited.add(parent_id)
            if cls._node_name_key(parent) in source_by_target:
                return parent
            parent = getattr(parent, "parent", None)
        return None

    @classmethod
    def _target_chain_between(cls, ancestor, descendant) -> list[object]:
        chain: list[object] = []
        current = getattr(descendant, "parent", None)
        visited: set[int] = set()
        while current is not None and current is not ancestor:
            current_id = id(current)
            if current_id in visited:
                return []
            visited.add(current_id)
            chain.append(current)
            current = getattr(current, "parent", None)
        if current is not ancestor:
            return []
        chain.reverse()
        return chain

    @classmethod
    def _can_thread_bridge_between_source_nodes(cls, parent, child) -> bool:
        if cls._is_descendant(child, parent):
            return True
        parent_parent = getattr(parent, "parent", None)
        child_parent = getattr(child, "parent", None)
        return parent_parent is not None and parent_parent is child_parent and cls._is_source_null_helper_node(parent_parent)

    def _insert_source_bridge_chain(
        self,
        source_parent,
        source_child,
        bridge_targets: list[object],
        source_by_target: dict[str, object],
        target_roles: dict[str, str],
    ) -> int:
        parent_world = self._node_world_position(source_parent)
        child_world = self._node_world_position(source_child)
        old_parent = getattr(source_child, "parent", None)
        if old_parent is not None and source_child in getattr(old_parent, "children", []):
            old_parent.children = [child for child in old_parent.children if child is not source_child]

        previous = source_parent
        previous_world = parent_world
        added = 0
        count = len(bridge_targets)
        for index, target_node in enumerate(bridge_targets, start=1):
            target_key = self._node_name_key(target_node)
            existing = source_by_target.get(target_key)
            if existing is None:
                existing = ModelNode(name=str(getattr(target_node, "name", "") or target_key), flags=int(NodeFlags.HEADER))
                existing.rotation = tuple(getattr(target_node, "rotation", (0.0, 0.0, 0.0, 1.0)))
                setattr(existing, "_ghostrigger_synthetic_unreal_source", True)
                setattr(existing, "_ghostrigger_synthetic_unreal_target", True)
                setattr(existing, "_ghostrigger_unreal_target_role", target_roles.get(target_key, ""))
                added += 1
            if getattr(existing, "parent", None) is not previous:
                old = getattr(existing, "parent", None)
                if old is not None:
                    old.children = [child for child in old.children if child is not existing]
                existing.parent = previous
            if existing not in previous.children:
                previous.children.append(existing)
            fraction = float(index) / float(count + 1)
            world = tuple(float(a) + (float(b) - float(a)) * fraction for a, b in zip(parent_world, child_world))
            existing.position = tuple(float(a) - float(b) for a, b in zip(world, previous_world))
            source_by_target[target_key] = existing
            previous = existing
            previous_world = world

        source_child.parent = previous
        if source_child not in previous.children:
            previous.children.append(source_child)
        source_child.position = tuple(float(a) - float(b) for a, b in zip(child_world, previous_world))
        return added

    @staticmethod
    def _node_name_key(node) -> str:
        return str(getattr(node, "name", "") or "").strip().lower()

    def _ensure_source_spine_g(self, model) -> bool:
        if not hasattr(model, "find_node"):
            return False
        pelvis = model.find_node("pelvis_g")
        torso = model.find_node("torso_g")
        if pelvis is None or torso is None or pelvis is torso:
            return False
        if not self._can_thread_source_spine(pelvis, torso):
            return False
        spine = model.find_node("spine_g")
        if spine is pelvis or spine is torso or (spine is not None and self._is_descendant(spine, torso)):
            return False

        pelvis_world = self._node_world_position(pelvis)
        torso_world = self._node_world_position(torso)
        spine_world = tuple((float(a) + float(b)) * 0.5 for a, b in zip(pelvis_world, torso_world))

        changed = False
        if spine is None:
            spine = ModelNode(name="spine_g", flags=int(NodeFlags.HEADER))
            spine.rotation = (0.0, 0.0, 0.0, 1.0)
            setattr(spine, "_ghostrigger_synthetic_unreal_source", True)
            changed = True

        spine_old_parent = getattr(spine, "parent", None)
        if spine_old_parent is not pelvis:
            if spine_old_parent is not None:
                spine_old_parent.children = [child for child in spine_old_parent.children if child is not spine]
            spine.parent = pelvis
            changed = True
        if spine not in pelvis.children:
            pelvis.children.append(spine)
            changed = True

        old_parent = getattr(torso, "parent", None)
        if old_parent is not spine:
            if old_parent is not None:
                old_parent.children = [child for child in old_parent.children if child is not torso]
            torso.parent = spine
            changed = True
        if torso not in spine.children:
            spine.children.append(torso)
            changed = True

        spine_position = tuple(float(a) - float(b) for a, b in zip(spine_world, pelvis_world))
        torso_position = tuple(float(a) - float(b) for a, b in zip(torso_world, spine_world))
        if tuple(getattr(spine, "position", ())) != spine_position:
            spine.position = spine_position
            changed = True
        if tuple(getattr(torso, "position", ())) != torso_position:
            torso.position = torso_position
            changed = True
        return changed

    @staticmethod
    def _is_descendant(node, ancestor) -> bool:
        current = getattr(node, "parent", None)
        visited: set[int] = set()
        while current is not None:
            node_id = id(current)
            if node_id in visited:
                return False
            visited.add(node_id)
            if current is ancestor:
                return True
            current = getattr(current, "parent", None)
        return False

    @classmethod
    def _can_thread_source_spine(cls, pelvis, torso) -> bool:
        if cls._is_descendant(torso, pelvis):
            return True
        pelvis_parent = getattr(pelvis, "parent", None)
        torso_parent = getattr(torso, "parent", None)
        if pelvis_parent is not None and pelvis_parent is torso_parent:
            return cls._is_source_null_helper_node(pelvis_parent)
        if torso_parent is not None and cls._is_source_null_helper_node(torso_parent):
            return cls._is_descendant(pelvis, torso_parent)
        return False

    @staticmethod
    def _is_source_null_helper_node(node) -> bool:
        name = str(getattr(node, "name", "") or "").strip().lower()
        return QtUnrealAnimatorWindow._is_source_null_helper_name(name)

    @staticmethod
    def _is_source_null_helper_name(name: str) -> bool:
        key = str(name or "").strip().lower()
        return "dummy" in key or "hook" in key

    @staticmethod
    def _node_world_position(node) -> tuple[float, float, float]:
        try:
            return tuple(float(part) for part in node.bone_world_position())
        except Exception:
            try:
                return tuple(float(part) for part in node.world_position())
            except Exception:
                return tuple(float(part) for part in getattr(node, "position", (0.0, 0.0, 0.0)))

    def set_target_asset(self, asset: UnrealSkeletonAsset) -> None:
        self._target_asset = asset
        self._target_model = unreal_skeleton_model(asset)
        self._manual_mapping.clear()
        if hasattr(self, "target_label"):
            self.target_label.setText(f"{asset.name}\n{asset.bone_count} bones")
        if hasattr(self, "import_fbx_button"):
            self.import_fbx_button.setEnabled(asset.fbx_path.exists())
            self.import_fbx_button.setToolTip(
                f"Import {asset.fbx_path.name} into the target viewport"
                if asset.fbx_path.exists()
                else f"Missing FBX: {asset.fbx_path}"
            )
        if hasattr(self, "import_target_fbx_action"):
            self.import_target_fbx_action.setEnabled(asset.fbx_path.exists())
        self.target_viewport.load_model(self._target_model)
        self._populate_target_bones()
        self.refresh_mapping()
        self._update_playback_controls()

    def import_target_fbx(self, path: Optional[str | Path] = None) -> None:
        fbx_path = Path(path) if path is not None else self._target_asset.fbx_path
        if not fbx_path.exists():
            message = f"FBX not found: {fbx_path}"
            self.statusBar().showMessage(message)
            QtWidgets.QMessageBox.warning(self, "Import FBX", message)
            return
        try:
            model = load_quinn_fbx_model(self._target_asset, fbx_path)
        except Exception as exc:
            message = f"FBX import failed: {exc}"
            self.statusBar().showMessage(message)
            QtWidgets.QMessageBox.warning(self, "Import FBX", message)
            return

        self._target_model = model
        self._manual_mapping.clear()
        mesh_count = sum(1 for node in model.mesh_nodes() if getattr(node, "vertices", None))
        face_count = sum(len(getattr(node, "faces", []) or []) for node in model.mesh_nodes())
        if hasattr(self, "target_label"):
            self.target_label.setText(
                f"{model.name}\n"
                f"{self._target_asset.bone_count} bones  {mesh_count} mesh  {face_count} tris"
            )
        self.target_viewport.load_model(
            model,
            texture_dir=str(fbx_path.parent),
            extra_texture_dirs=[str(fbx_path.parent)],
        )
        self._on_target_bone_selected(self.target_bones.currentItem(), None)
        self.statusBar().showMessage(
            f"Imported {fbx_path.name}: {mesh_count} mesh node(s), {face_count} triangle(s)"
        )
        self.refresh_mapping()
        self._update_playback_controls()

    def refresh_mapping(self) -> None:
        self._updating_mapping = True
        self.mapping_tree.clear()
        if self._source_model is None or self._target_model is None:
            self._mapping_report = None
            self._updating_mapping = False
            self.mapping_info.setPlainText("Load a KotOR supermodel source to build a Quinn mapping.")
            return
        report = build_bone_map(
            self._source_model,
            self._target_model,
            manual_mapping=self._manual_mapping,
        )
        self._mapping_report = report
        target_names = self._target_bone_names()
        mapped = dict(report.mapping)
        missing = {str(source or "").lower() for source in (getattr(report, "missing_source", []) or [])}
        for source in sorted(set(mapped).union(missing)):
            auto_target = mapped.get(source, "")
            current_target = self._manual_mapping.get(source, auto_target)
            item = QtWidgets.QTreeWidgetItem([source, ""])
            item.setData(0, QtCore.Qt.UserRole, source)
            item.setData(1, QtCore.Qt.UserRole, auto_target)
            self.mapping_tree.addTopLevelItem(item)
            combo = QtWidgets.QComboBox(self.mapping_tree)
            combo.addItem("")
            for name in target_names:
                combo.addItem(name)
            if current_target and combo.findText(current_target) < 0:
                combo.addItem(current_target)
            combo.setCurrentText(current_target)
            combo.currentTextChanged.connect(
                lambda text, source_key=source, auto_key=auto_target: self._on_mapping_changed(
                    source_key,
                    auto_key,
                    text,
                )
            )
            self.mapping_tree.setItemWidget(item, 1, combo)
        for target in sorted(getattr(report, "derived_target", ()) or ()):
            self.mapping_tree.addTopLevelItem(QtWidgets.QTreeWidgetItem(["(interpolated)", target]))
        self._updating_mapping = False
        self.mapping_tree.resizeColumnToContents(0)
        self.mapping_info.setPlainText(
            f"Source: {getattr(self._source_model, 'name', '')}\n"
            f"Target: {self._target_asset.name}\n"
            f"Mapped bones: {report.matched_count}\n"
            f"Interpolated target: {getattr(report, 'derived_count', 0)}\n"
            f"Exact: {report.exact_matches}  Alias: {report.alias_matches}  Manual: {report.manual_matches}\n"
            f"Unmapped source: {len(report.missing_source)}\n"
            f"Unmapped Quinn: {len(report.missing_target)}"
        )
        self.statusBar().showMessage(f"Mapped {report.matched_count} bone(s) to {self._target_asset.name}")
        self._update_playback_controls()

    def _target_bone_names(self) -> list[str]:
        if self._target_model is None or not hasattr(self._target_model, "all_nodes"):
            return []
        names = []
        for node in self._target_model.all_nodes():
            if getattr(node, "is_mesh", False):
                continue
            name = str(getattr(node, "name", "") or "").strip().lower()
            if name:
                names.append(name)
        return sorted(set(names))

    def _current_mapping_report(self):
        if self._source_model is None or self._target_model is None:
            return None
        report = build_bone_map(
            self._source_model,
            self._target_model,
            manual_mapping=self._manual_mapping,
        )
        self._mapping_report = report
        return report

    def _on_mapping_changed(self, source_key: str, auto_key: str, text: str) -> None:
        if self._updating_mapping:
            return
        target_key = str(text or "").strip().lower()
        if not target_key or target_key == str(auto_key or "").lower():
            self._manual_mapping.pop(source_key, None)
        else:
            self._manual_mapping[source_key] = target_key
        self.refresh_mapping()

    def selected_animation_name(self) -> str:
        item = self.anim_list.currentItem() if hasattr(self, "anim_list") else None
        return item.text() if item is not None else ""

    def _selected_source_animation(self):
        anim_name = self.selected_animation_name().lower()
        if not anim_name or self._source_model is None:
            return None
        for anim in getattr(self._source_model, "animations", []) or []:
            if str(getattr(anim, "name", "") or "").lower() == anim_name:
                return anim
        return None

    @staticmethod
    def _set_viewport_gpu_enabled(viewport, enabled: bool) -> None:
        if viewport is None or not hasattr(viewport, "toggle_gpu_renderer"):
            return
        if not bool(enabled):
            return
        current = bool(getattr(viewport, "_use_gpu", False))
        if not current:
            viewport.toggle_gpu_renderer(True)

    def _force_gpu_for_animation_preview(self) -> None:
        if self._animation_gpu_restore_state is None:
            self._animation_gpu_restore_state = (
                bool(getattr(self.source_viewport, "_use_gpu", False)),
                bool(getattr(self.target_viewport, "_use_gpu", False)),
            )
        self._set_viewport_gpu_enabled(self.source_viewport, True)
        self._set_viewport_gpu_enabled(self.target_viewport, True)

    def _restore_gpu_after_animation_preview(self) -> None:
        self._animation_gpu_restore_state = None
        self._set_viewport_gpu_enabled(self.source_viewport, True)
        self._set_viewport_gpu_enabled(self.target_viewport, True)

    def _on_animation_selection_changed(self) -> None:
        anim = self._selected_source_animation()
        name = getattr(anim, "name", "") if anim is not None else ""
        length = float(getattr(anim, "length", 0.0) or 0.0) if anim is not None else 0.0
        if hasattr(self, "selected_anim_label"):
            self.selected_anim_label.setText(name or "No animation selected")
        self._set_framebar_time(0.0, length)
        self._arm_selected_animation_preview()
        self._update_playback_controls()

    def _arm_selected_animation_preview(self) -> None:
        anim_name = self.selected_animation_name()
        was_playing = bool(getattr(self, "_preview_timer", None) and self._preview_timer.isActive())
        if getattr(self, "_preview_timer", None) is not None:
            self._preview_timer.stop()
        if self._preview_engine is not None:
            self._preview_engine.stop()
        self._preview_engine = None
        self._preview_last_tick = None
        self.source_viewport.clear_animation_pose()
        self.target_viewport.clear_animation_pose()
        if not anim_name or self._selected_source_animation() is None or self._source_model is None or self._target_model is None:
            self._restore_gpu_after_animation_preview()
            return
        engine = AnimationEngine(self._source_model)
        if not engine.play(anim_name, loop=True, blend=False):
            self.statusBar().showMessage(f"Animation not found: {anim_name}")
            return
        self._preview_engine = engine
        self._apply_preview_pose(0.0)
        if was_playing:
            self._preview_last_tick = None
            self._preview_timer.start()
            self.statusBar().showMessage(f"Previewing {anim_name}")
        else:
            engine.stop()
            self.statusBar().showMessage(f"{anim_name} ready to preview")

    def _set_framebars_enabled(self, enabled: bool) -> None:
        for attr in ("source_frame_slider", "target_frame_slider"):
            slider = getattr(self, attr, None)
            if slider is not None:
                slider.setEnabled(enabled)

    def _set_framebar_time(self, current: float, length: float) -> None:
        pct = int(round((current / length) * 1000.0)) if length > 0.0 else 0
        pct = max(0, min(1000, pct))
        for attr in ("source_frame_slider", "target_frame_slider"):
            slider = getattr(self, attr, None)
            if slider is not None:
                slider.blockSignals(True)
                slider.setValue(pct)
                slider.blockSignals(False)
        frame = int(round(current * 30.0))
        total = int(round(length * 30.0)) if length > 0.0 else 0
        text = f"{frame} / {total}f"
        for attr in ("source_frame_label", "target_frame_label"):
            label = getattr(self, attr, None)
            if label is not None:
                label.setText(text)

    def _update_playback_controls(self) -> None:
        has_anim = self._selected_source_animation() is not None
        has_target = self._target_model is not None
        for widget in (
            getattr(self, "preview_button", None),
            getattr(self, "bake_button", None),
            getattr(self, "export_button", None),
        ):
            if widget is not None:
                widget.setEnabled(has_anim and has_target)
        if hasattr(self, "stop_button"):
            self.stop_button.setEnabled(self._preview_timer.isActive())
        self.preview_action.setEnabled(has_anim and has_target)
        self.bake_action.setEnabled(has_anim and has_target)
        self.export_action.setEnabled(has_anim and has_target)
        self.stop_action.setEnabled(self._preview_timer.isActive())
        self._set_framebars_enabled(has_anim)

    def preview_selected_animation(self) -> None:
        anim_name = self.selected_animation_name()
        if not anim_name or self._source_model is None:
            self.statusBar().showMessage("Select a source animation to preview.")
            return
        self._force_gpu_for_animation_preview()
        self._preview_engine = AnimationEngine(self._source_model)
        if not self._preview_engine.play(anim_name, loop=True, blend=False):
            self.statusBar().showMessage(f"Animation not found: {anim_name}")
            self._preview_engine = None
            self._restore_gpu_after_animation_preview()
            return
        self._preview_last_tick = None
        self._apply_preview_pose(0.0)
        self._preview_timer.start()
        self.statusBar().showMessage(f"Previewing {anim_name}")
        self._update_playback_controls()

    def stop_preview(self) -> None:
        self._preview_timer.stop()
        self._preview_last_tick = None
        if self._preview_engine is not None:
            self._preview_engine.stop()
        self.source_viewport.clear_animation_pose()
        self.target_viewport.clear_animation_pose()
        self._restore_gpu_after_animation_preview()
        anim = self._selected_source_animation()
        self._set_framebar_time(0.0, float(getattr(anim, "length", 0.0) or 0.0) if anim else 0.0)
        self.statusBar().showMessage("Preview stopped.")
        self._update_playback_controls()

    def _scrub_preview(self, value: int) -> None:
        anim = self._selected_source_animation()
        if anim is None:
            return
        length = float(getattr(anim, "length", 0.0) or 0.0)
        if length <= 0.0:
            return
        self._apply_preview_pose((float(value) / 1000.0) * length)

    def _apply_preview_pose(self, t: float) -> None:
        anim_name = self.selected_animation_name()
        if not anim_name or self._source_model is None or self._target_model is None:
            return
        if self._preview_engine is None:
            self._preview_engine = AnimationEngine(self._source_model)
            if not self._preview_engine.play(anim_name, loop=True, blend=False):
                return
            self._preview_engine.stop()
        self._preview_engine.seek(t)
        source_pose = self._preview_engine.evaluate()
        length = float(getattr(self._preview_engine.current_animation, "length", 0.0) or 0.0)
        self.source_viewport.set_animation_pose(source_pose, name=anim_name, time=t, length=length)
        try:
            result = retarget_pose(
                source_pose,
                self._source_model,
                self._target_model,
                mapping_report=self._current_mapping_report(),
            )
            self.target_viewport.set_animation_pose(result.pose, name=anim_name, time=t, length=length)
        except Exception:
            self.target_viewport.clear_animation_pose()
        self._set_framebar_time(t, length)

    def _tick_preview(self) -> None:
        engine = self._preview_engine
        if engine is None or not engine.is_playing:
            self.stop_preview()
            return
        now = time.perf_counter()
        if self._preview_last_tick is None:
            dt = 1.0 / 60.0
        else:
            dt = max(1.0 / 120.0, min(now - self._preview_last_tick, 0.15))
        self._preview_last_tick = now
        still = engine.advance(dt)
        t = engine.current_time
        pose = engine.evaluate()
        anim = engine.current_animation
        length = float(getattr(anim, "length", 0.0) or 0.0) if anim else 0.0
        name = str(getattr(anim, "name", "") or self.selected_animation_name())
        self._force_gpu_for_animation_preview()
        self.source_viewport.set_animation_pose(pose, name=name, time=t, length=length)
        try:
            result = retarget_pose(
                pose,
                self._source_model,
                self._target_model,
                mapping_report=self._current_mapping_report(),
            )
            self.target_viewport.set_animation_pose(result.pose, name=name, time=t, length=length)
        except Exception:
            pass
        self._set_framebar_time(t, length)
        if not still:
            self.stop_preview()

    def bake_selected_animation(self) -> None:
        anim = self._selected_source_animation()
        if anim is None or self._source_model is None or self._target_model is None:
            self.statusBar().showMessage("Select a source animation to bake.")
            return
        baked, report = retarget_animation(
            anim,
            self._source_model,
            self._target_model,
            mapping_report=self._current_mapping_report(),
            name_suffix="_quinn",
        )
        target_anims = getattr(self._target_model, "animations", None)
        if target_anims is None:
            self._target_model.animations = []
            target_anims = self._target_model.animations
        target_anims.append(baked)
        self.mapping_info.setPlainText(
            f"Baked: {baked.name}\n"
            f"Length: {baked.length:.3f}s\n"
            f"Nodes: {len(getattr(baked, 'nodes', []) or [])}\n"
            f"Mapped bones: {report.matched_count}"
        )
        self.statusBar().showMessage(f"Baked animation {baked.name}")

    def export_fbx_animation(self) -> None:
        anim = self._selected_source_animation()
        if anim is None or self._source_model is None or self._target_model is None:
            self.statusBar().showMessage("Select a source animation to export.")
            return
        default_name = f"{self._target_asset.name}_{getattr(anim, 'name', 'animation')}.fbx"
        path, _selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export FBX Animation",
            str(self._target_asset.fbx_path.with_name(default_name)),
            "FBX (*.fbx)",
        )
        if not path:
            return
        baked, _report = retarget_animation(
            anim,
            self._source_model,
            self._target_model,
            mapping_report=self._current_mapping_report(),
            name_suffix="_quinn",
        )
        original_anims = list(getattr(self._target_model, "animations", []) or [])
        self._target_model.animations = [baked]
        try:
            from src.converters.mesh_converter import FBXExporter

            ok = FBXExporter().export(
                self._target_model,
                path,
                tex_cache=getattr(self.target_viewport, "tex_cache", None),
                export_rigging=True,
            )
        except Exception as exc:
            ok = False
            self.statusBar().showMessage(f"FBX export failed: {exc}")
            QtWidgets.QMessageBox.warning(self, "Export FBX Animation", f"FBX export failed:\n{exc}")
        finally:
            self._target_model.animations = original_anims
        if ok:
            self.statusBar().showMessage(f"Exported FBX animation: {Path(path).name}")

    def selected_source_row(self) -> Optional[dict]:
        item = self.source_tree.currentItem()
        return item.data(0, QtCore.Qt.UserRole) if item is not None else None

    def _request_selected_source(self) -> None:
        row = self.selected_source_row()
        if row:
            self.sourceLoadRequested.emit(row)

    def _populate_source_library(self) -> None:
        if not hasattr(self, "source_tree"):
            return
        needle = self.source_filter.text().strip().lower() if hasattr(self, "source_filter") else ""
        self.source_tree.clear()
        for row in self._library_rows:
            resref = str(row.get("resref", "") or "")
            if needle and needle not in resref.lower():
                continue
            item = QtWidgets.QTreeWidgetItem([
                str(row.get("game", "")),
                resref,
                str(row.get("animations", "")),
                str(row.get("nodes", "")),
            ])
            item.setData(0, QtCore.Qt.UserRole, row)
            self.source_tree.addTopLevelItem(item)
        self.source_tree.resizeColumnToContents(1)

    def _populate_source_bones(self) -> None:
        if not hasattr(self, "source_bones"):
            return
        current_name = ""
        current = self.source_bones.currentItem()
        if current is not None:
            current_name = str(current.text(0) or "")
        self.source_bones.clear()
        model = self._source_model
        if model is None or not hasattr(model, "all_nodes"):
            return
        item_by_name: dict[str, QtWidgets.QTreeWidgetItem] = {}
        for index, node in enumerate(model.all_nodes()):
            if not self._is_source_bone_node(node):
                continue
            parent = getattr(node, "parent", None)
            role = self._source_bone_role(node)
            item = QtWidgets.QTreeWidgetItem([
                str(getattr(node, "name", "") or ""),
                str(getattr(parent, "name", "") or ""),
                role,
            ])
            item.setData(0, QtCore.Qt.UserRole, node)
            item.setData(1, QtCore.Qt.UserRole, index)
            if role == "synthetic":
                color = QtGui.QColor("#74b7ff")
                for column in range(3):
                    item.setForeground(column, color)
            self.source_bones.addTopLevelItem(item)
            item_by_name[item.text(0)] = item
        self.source_bones.resizeColumnToContents(0)
        self.source_bones.resizeColumnToContents(1)
        if current_name and current_name in item_by_name:
            self.source_bones.setCurrentItem(item_by_name[current_name])
        self._update_source_synthetic_buttons()

    def _is_source_bone_node(self, node) -> bool:
        return self._is_potential_source_bone_node(node)

    def _is_potential_source_bone_node(self, node) -> bool:
        name = str(getattr(node, "name", "") or "").strip().lower()
        if not name:
            return False
        if "dummy" in name or "hook" in name:
            return False
        if bool(getattr(node, "is_skin", False)):
            return False
        if not bool(getattr(node, "is_mesh", False)):
            return True
        return name.endswith("_g") or name.endswith("_g0")

    @staticmethod
    def _source_bone_role(node) -> str:
        if bool(getattr(node, "_ghostrigger_synthetic_unreal_source", False)):
            return "synthetic"
        if bool(getattr(node, "is_mesh", False)):
            return "deform"
        return "bone"

    def _on_source_bone_selected(self, current, _previous) -> None:
        if current is None or self._source_model is None:
            self.source_viewport.set_selected_node(None)
            self._update_source_synthetic_buttons()
            return
        node = current.data(0, QtCore.Qt.UserRole)
        self.source_viewport.set_selected_node(node)
        self._update_source_synthetic_buttons()

    def _selected_source_bone_node(self):
        current = self.source_bones.currentItem() if hasattr(self, "source_bones") else None
        if current is None:
            return None
        return current.data(0, QtCore.Qt.UserRole)

    def _update_source_synthetic_buttons(self) -> None:
        node = self._selected_source_bone_node()
        has_model = self._source_model is not None
        is_synthetic = bool(getattr(node, "_ghostrigger_synthetic_unreal_source", False)) if node is not None else False
        if hasattr(self, "add_source_synthetic_button"):
            self.add_source_synthetic_button.setEnabled(has_model and node is not None)
        if hasattr(self, "insert_source_synthetic_button"):
            self.insert_source_synthetic_button.setEnabled(has_model and node is not None and getattr(node, "parent", None) is not None)
        if hasattr(self, "delete_source_synthetic_button"):
            self.delete_source_synthetic_button.setEnabled(has_model and is_synthetic)

    def _prompt_add_source_synthetic_bone(self) -> None:
        parent = self._selected_source_bone_node()
        if parent is None:
            self.statusBar().showMessage("Select a source bone to parent the synthetic bone.")
            return
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Add Synthetic Source Bone",
            f"Name for new child under {getattr(parent, 'name', '')}:",
        )
        if ok:
            self._add_source_synthetic_bone(str(name or ""), parent_node=parent)

    def _prompt_insert_source_synthetic_bone(self) -> None:
        child = self._selected_source_bone_node()
        parent = getattr(child, "parent", None)
        if child is None or parent is None:
            self.statusBar().showMessage("Select a source bone with a parent to insert before it.")
            return
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Insert Synthetic Source Bone",
            f"Name for bone between {getattr(parent, 'name', '')} and {getattr(child, 'name', '')}:",
        )
        if ok:
            self._add_source_synthetic_bone(str(name or ""), child_node=child)

    def _add_source_synthetic_bone(self, name: str, parent_node=None, child_node=None):
        if self._source_model is None or not hasattr(self._source_model, "find_node"):
            return None
        clean_name = str(name or "").strip()
        if not clean_name:
            self.statusBar().showMessage("Synthetic bone name is required.")
            return None
        if self._is_source_null_helper_name(clean_name):
            self.statusBar().showMessage("Synthetic source bones cannot be dummy/hook helpers.")
            return None
        clean_name = self._unique_source_bone_name(clean_name)

        if child_node is not None:
            parent_node = getattr(child_node, "parent", None)
        if parent_node is None:
            parent_node = getattr(self._source_model, "root_node", None)
        if parent_node is None:
            return None

        node = ModelNode(name=clean_name, flags=int(NodeFlags.HEADER))
        node.rotation = (0.0, 0.0, 0.0, 1.0)
        setattr(node, "_ghostrigger_synthetic_unreal_source", True)
        setattr(node, "_ghostrigger_synthetic_manual_source", True)

        if child_node is not None:
            self._insert_manual_synthetic_before_child(node, parent_node, child_node)
        else:
            self._append_manual_synthetic_child(node, parent_node)

        self._refresh_source_after_synthetic_edit(node)
        self.statusBar().showMessage(f"Added synthetic source bone {clean_name}")
        return node

    def _append_manual_synthetic_child(self, node, parent_node) -> None:
        parent_world = self._node_world_position(parent_node)
        next_child = next(
            (
                child
                for child in getattr(parent_node, "children", []) or []
                if self._is_source_bone_node(child)
            ),
            None,
        )
        if next_child is not None:
            child_world = self._node_world_position(next_child)
            node.position = tuple((float(a) - float(b)) * 0.5 for a, b in zip(child_world, parent_world))
        else:
            node.position = (0.0, 0.0, 0.25)
        node.parent = parent_node
        parent_node.children.append(node)

    def _insert_manual_synthetic_before_child(self, node, parent_node, child_node) -> None:
        parent_world = self._node_world_position(parent_node)
        child_world = self._node_world_position(child_node)
        node_world = tuple((float(a) + float(b)) * 0.5 for a, b in zip(parent_world, child_world))
        node.position = tuple(float(a) - float(b) for a, b in zip(node_world, parent_world))
        child_position = tuple(float(a) - float(b) for a, b in zip(child_world, node_world))
        if child_node in getattr(parent_node, "children", []):
            index = parent_node.children.index(child_node)
            parent_node.children[index] = node
        else:
            parent_node.children.append(node)
        node.parent = parent_node
        node.children.append(child_node)
        child_node.parent = node
        child_node.position = child_position

    def _unique_source_bone_name(self, base_name: str) -> str:
        if self._source_model is None or not hasattr(self._source_model, "find_node"):
            return base_name
        candidate = base_name
        suffix = 1
        while self._source_model.find_node(candidate) is not None:
            suffix += 1
            candidate = f"{base_name}_{suffix}"
        return candidate

    def _delete_selected_source_synthetic_bone(self) -> bool:
        node = self._selected_source_bone_node()
        if node is None:
            return False
        if not bool(getattr(node, "_ghostrigger_synthetic_unreal_source", False)):
            self.statusBar().showMessage("Only synthetic source bones can be deleted.")
            return False
        deleted_name = str(getattr(node, "name", "") or "synthetic")
        parent = self._delete_source_synthetic_node(node)
        self._refresh_source_after_synthetic_edit(parent)
        self.statusBar().showMessage(f"Deleted synthetic source bone {deleted_name}")
        return True

    def _delete_source_synthetic_node(self, node):
        parent = getattr(node, "parent", None)
        children = list(getattr(node, "children", []) or [])
        child_world_positions = [(child, self._node_world_position(child)) for child in children]
        parent_world = self._node_world_position(parent) if parent is not None else (0.0, 0.0, 0.0)
        insert_at = 0
        if parent is not None and node in getattr(parent, "children", []):
            insert_at = parent.children.index(node)
            parent.children.pop(insert_at)
        for child, world_pos in child_world_positions:
            child.parent = parent
            if parent is not None:
                child.position = tuple(float(a) - float(b) for a, b in zip(world_pos, parent_world))
                parent.children.insert(insert_at, child)
                insert_at += 1
            else:
                child.position = world_pos
        node.children = []
        node.parent = None
        if self.source_viewport._renderer.selected_node is node:
            self.source_viewport.set_selected_node(parent)
        return parent

    def _refresh_source_after_synthetic_edit(self, select_node=None) -> None:
        if self._source_model is None:
            return
        self.source_label.setText(self._source_label_text(self._source_model))
        self.source_label.setToolTip(self._source_label_tooltip(self._source_model))
        self._populate_source_bones()
        if select_node is not None:
            self._select_source_bone_node(select_node)
        self.source_viewport.load_model(self._source_model)
        self.source_viewport.set_selected_node(select_node)
        self.refresh_mapping()
        self._arm_selected_animation_preview()
        self._update_playback_controls()

    def _select_source_bone_node(self, node) -> None:
        if node is None or not hasattr(self, "source_bones"):
            return
        for row in range(self.source_bones.topLevelItemCount()):
            item = self.source_bones.topLevelItem(row)
            if item is not None and item.data(0, QtCore.Qt.UserRole) is node:
                self.source_bones.setCurrentItem(item)
                return

    def _populate_target_bones(self) -> None:
        self.target_bones.clear()
        for bone in self._target_asset.bones:
            item = QtWidgets.QTreeWidgetItem([
                str(bone.index),
                bone.name,
                bone.side,
                bone.group,
                bone.role,
            ])
            item.setData(0, QtCore.Qt.UserRole, bone.name)
            self.target_bones.addTopLevelItem(item)
        self.target_bones.resizeColumnToContents(1)
        asset = self._target_asset
        self.target_info.setPlainText(
            f"{asset.name}\n"
            f"{asset.source}\n"
            f"Bones: {asset.bone_count}\n"
            f"Bone data: {'FBX skeleton' if asset.fbx_path.exists() else asset.bone_map_path.name}\n"
            f"FBX: {asset.fbx_path.name} ({'found' if asset.fbx_path.exists() else 'missing'})\n"
            f"Textures: {len(asset.texture_paths)}"
        )

    def _cycle_animator_gizmo(self) -> None:
        for viewport in (self.source_viewport, self.target_viewport):
            viewport.cycle_gimbal_mode()
        mode = "Rotate" if self.target_viewport._renderer.gimbal_mode == 2 else "Translate"
        self.statusBar().showMessage(f"Gizmo: {mode}")

    def _on_target_bone_selected(self, current, _previous) -> None:
        if current is None or self._target_model is None:
            self.target_viewport.set_selected_node(None)
            return
        bone_name = current.data(0, QtCore.Qt.UserRole) or current.text(1)
        node = self._target_model.find_node(str(bone_name)) if hasattr(self._target_model, "find_node") else None
        self.target_viewport.set_selected_node(node)

    def _source_label_text(self, model) -> str:
        if model is None:
            return "No source loaded"
        mode = "supermodel" if is_animation_supermodel(model) else "model"
        return (
            f"{getattr(model, 'name', '?')} [{self._source_game or '?'}] {mode}\n"
            f"{len(getattr(model, 'animations', []) or [])} animations  "
            f"{len(list(model.all_nodes())) if hasattr(model, 'all_nodes') else 0} nodes"
        )

    def _source_label_tooltip(self, model) -> str:
        if model is None or not hasattr(model, "all_nodes"):
            return ""
        raw_nodes = len(list(model.all_nodes()))
        synthetic = sum(1 for node in model.all_nodes() if bool(getattr(node, "_ghostrigger_synthetic_unreal_source", False)))
        if synthetic:
            return f"{raw_nodes} raw KotOR-authoritative nodes including {synthetic} synthetic bridge node(s)"
        return f"{raw_nodes} raw KotOR-authoritative nodes"
