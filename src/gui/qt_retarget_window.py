"""Detachable animation retargeting workbench."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .qt_animation_panel import QtAnimationRetargetPanel
from .qt_viewport import QtViewportWidget


class QtAnimationRetargetWindow(QtWidgets.QMainWindow):
    """Standalone retargeting workspace with source/target viewports."""

    sourceCurrentRequested = QtCore.Signal()
    targetCurrentRequested = QtCore.Signal()
    sourceLibraryRequested = QtCore.Signal()
    targetLibraryRequested = QtCore.Signal()
    previewRequested = QtCore.Signal(str)
    applyRequested = QtCore.Signal(str)
    stopRequested = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Animation Retargeting Workbench")
        self.resize(1280, 820)
        self.setMinimumSize(960, 640)
        self._texture_dir = ""
        self._resource_manager = None
        self._source_game = "K1"
        self._target_game = "K1"
        self._build_actions()
        self._build_menu()
        self._build_statusbar()
        self._build_central()

    def _build_actions(self) -> None:
        self.close_action = QtGui.QAction("Close", self)
        self.close_action.setShortcut("Ctrl+W")
        self.close_action.triggered.connect(self.close)
        self.preview_action = QtGui.QAction("Preview Selected", self)
        self.preview_action.setShortcut("Space")
        self.preview_action.triggered.connect(lambda: self.previewRequested.emit(self.panel.selected_animation()))
        self.apply_action = QtGui.QAction("Apply Selected", self)
        self.apply_action.setShortcut("Ctrl+Return")
        self.apply_action.triggered.connect(lambda: self.applyRequested.emit(self.panel.selected_animation()))
        self.stop_action = QtGui.QAction("Stop Preview", self)
        self.stop_action.triggered.connect(self.stopRequested.emit)
        self.frame_source_action = QtGui.QAction("Frame Source", self)
        self.frame_source_action.triggered.connect(lambda: self.source_viewport.frame_all())
        self.frame_target_action = QtGui.QAction("Frame Target", self)
        self.frame_target_action.triggered.connect(lambda: self.target_viewport.frame_all())
        self.vertex_tweak_action = QtGui.QAction("Vertex", self)
        self.skin_paint_action = QtGui.QAction("Skin Paint", self)
        self.weight_balance_action = QtGui.QAction("Weights", self)
        self.diagnostics_action = QtGui.QAction("Diagnostics", self)
        self.tool_action_group = QtGui.QActionGroup(self)
        self.tool_action_group.setExclusive(True)
        for action in (
            self.vertex_tweak_action,
            self.skin_paint_action,
            self.weight_balance_action,
            self.diagnostics_action,
        ):
            action.setCheckable(True)
            self.tool_action_group.addAction(action)
            action.triggered.connect(self._tool_mode_changed)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.close_action)
        retarget_menu = self.menuBar().addMenu("Retarget")
        retarget_menu.addAction(self.preview_action)
        retarget_menu.addAction(self.apply_action)
        retarget_menu.addAction(self.stop_action)
        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.frame_source_action)
        view_menu.addAction(self.frame_target_action)
        tools_menu = self.menuBar().addMenu("Tools")
        mode_menu = tools_menu.addMenu("Workbench Tools")
        mode_menu.addAction(self.vertex_tweak_action)
        mode_menu.addAction(self.skin_paint_action)
        mode_menu.addAction(self.weight_balance_action)
        mode_menu.addAction(self.diagnostics_action)

    def _build_statusbar(self) -> None:
        self.statusBar().showMessage("Ready")

    def _build_central(self) -> None:
        root = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        root.setChildrenCollapsible(False)
        self.source_viewport = QtViewportWidget(self)
        self.target_viewport = QtViewportWidget(self)

        self.panel = QtAnimationRetargetPanel(self)
        self.panel.sourceCurrentRequested.connect(self.sourceCurrentRequested.emit)
        self.panel.targetCurrentRequested.connect(self.targetCurrentRequested.emit)
        self.panel.sourceLibraryRequested.connect(self.sourceLibraryRequested.emit)
        self.panel.targetLibraryRequested.connect(self.targetLibraryRequested.emit)
        self.panel.previewRequested.connect(self.previewRequested.emit)
        self.panel.applyRequested.connect(self.applyRequested.emit)
        self.panel.stopRequested.connect(self.stopRequested.emit)

        viewport_split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        viewport_split.setChildrenCollapsible(False)
        viewport_split.addWidget(self._viewport_group(self.panel.source_box, self.source_viewport))
        viewport_split.addWidget(self._viewport_group(self.panel.target_box, self.target_viewport))
        viewport_split.setSizes([640, 640])

        root.addWidget(viewport_split)
        root.addWidget(self.panel)
        root.setSizes([560, 260])
        self.setCentralWidget(root)

    def _viewport_group(
        self,
        selector: QtWidgets.QWidget,
        viewport: QtViewportWidget,
    ) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addWidget(selector, 0)
        layout.addWidget(viewport, 1)
        return box

    def set_texture_dir(self, texture_dir: str) -> None:
        self._texture_dir = texture_dir or ""

    def set_resource_manager(self, manager, game_tag: str = "K1") -> None:
        self._resource_manager = manager
        self._source_game = (game_tag or self._source_game or "K1").upper()
        self._target_game = (game_tag or self._target_game or "K1").upper()

    def set_source_resource_context(self, manager, game_tag: str = "K1") -> None:
        self._resource_manager = manager
        self._source_game = (game_tag or "K1").upper()

    def set_target_resource_context(self, manager, game_tag: str = "K1") -> None:
        self._resource_manager = manager
        self._target_game = (game_tag or "K1").upper()

    def set_source_model(self, model, game_tag: str = "") -> None:
        if game_tag:
            self._source_game = game_tag.upper()
        if self._resource_manager is not None:
            self.source_viewport.set_resource_manager(self._resource_manager, self._source_game)
        self.panel.set_source_model(model)
        self.source_viewport.load_model(model, self._texture_dir)
        self.statusBar().showMessage(f"Source: {getattr(model, 'name', 'None') if model else 'None'}")

    def set_target_model(self, model, game_tag: str = "") -> None:
        if game_tag:
            self._target_game = game_tag.upper()
        if self._resource_manager is not None:
            self.target_viewport.set_resource_manager(self._resource_manager, self._target_game)
        self.panel.set_target_model(model)
        self.target_viewport.load_model(model, self._texture_dir)
        self.statusBar().showMessage(f"Target: {getattr(model, 'name', 'None') if model else 'None'}")

    def set_mapping_report(self, report) -> None:
        self.panel.set_mapping_report(report)
        self.statusBar().showMessage(f"Mapped bones: {getattr(report, 'matched_count', 0)}")

    def config_kwargs(self) -> dict:
        return self.panel.config_kwargs()

    def selected_animation(self) -> str:
        return self.panel.selected_animation()

    def set_source_pose(self, pose, name: str = "", time: float = 0.0, length: float = 0.0) -> None:
        self.source_viewport.set_animation_pose(pose, name=name, time=time, length=length)

    def set_target_pose(self, pose, name: str = "", time: float = 0.0, length: float = 0.0) -> None:
        self.target_viewport.set_animation_pose(pose, name=name, time=time, length=length)

    def clear_poses(self) -> None:
        self.source_viewport.clear_animation_pose()
        self.target_viewport.clear_animation_pose()

    def _tool_mode_changed(self) -> None:
        active = self.tool_action_group.checkedAction()
        self.statusBar().showMessage(f"Tool: {active.text()}" if active else "Tools: Ready")
