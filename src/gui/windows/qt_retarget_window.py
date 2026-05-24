"""Detachable animation retargeting workbench."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.animation.animation_engine import AnimPose, NodePose
from src.gui.qt_lib.panels.qt_animation_panel import QtAnimationRetargetPanel
from src.gui.qt_lib.rendering.qt_gpu_renderer import create_viewport_renderer
from src.gui.qt_lib.rendering.renderer_settings import RendererSettings
from src.gui.qt_lib.viewports.qt_viewport import QtRetargetViewportWidget, QtViewportWidget
from src.gui.qt_lib.rendering.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE
from src.gui.qt_lib.windows.qt_source_clip_preview_model import build_source_clip_preview_model
from src.gui.qt_lib.windows.qt_retarget_workbench_controller import populate_retarget_mode_combo
from src.core.retargeting.retarget_output_naming import KotorOutputAnimationNameMode


class QtAnimationRetargetWindow(QtWidgets.QMainWindow):
    """Standalone retargeting workspace with source/target viewports."""

    sourceCurrentRequested = QtCore.Signal()
    targetCurrentRequested = QtCore.Signal()
    sourceLibraryRequested = QtCore.Signal()
    targetLibraryRequested = QtCore.Signal()
    sourceGameLibraryRequested = QtCore.Signal(dict)
    targetGameLibraryRequested = QtCore.Signal(dict)
    sourceExternalImportRequested = QtCore.Signal()
    targetExternalImportRequested = QtCore.Signal()
    previewRequested = QtCore.Signal(str)
    applyRequested = QtCore.Signal(str)
    pauseRequested = QtCore.Signal()
    stopRequested = QtCore.Signal()
    sourceAnimationPlayRequested = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Animation Retargeting Workbench")
        self.resize(1280, 820)
        self.setMinimumSize(960, 640)
        self._texture_dir = ""
        self._resource_manager = None
        self._source_game = "K1"
        self._target_game = "K1"
        self._navigation_profile = DEFAULT_VIEWPORT_NAVIGATION_PROFILE
        self._renderer_settings = RendererSettings.from_settings(getattr(parent, "settings_data", {}) or {})
        self._source_clip_preview_clip = None
        self._source_clip_mesh_model = None
        self._source_clip_play_name = ""
        self._source_clip_play_clock = QtCore.QElapsedTimer()
        self._source_clip_play_timer = QtCore.QTimer(self)
        self._source_clip_play_timer.setInterval(33)
        self._source_clip_play_timer.timeout.connect(self._tick_source_clip_playback)
        self._retarget_docks: dict[str, QtWidgets.QDockWidget] = {}
        self._build_actions()
        self._build_menu()
        self._build_statusbar()
        self._build_central()
        theme_manager = getattr(parent, "theme_manager", None)
        layout_manager = getattr(parent, "layout_manager", None)
        if theme_manager is not None:
            theme_manager.register_theme_aware_widget(self)
            self.apply_ghost_theme(theme_manager.current_theme or theme_manager.get_theme())
        if layout_manager is not None:
            self.apply_ghost_layout(layout_manager.current_layout or layout_manager.get_layout())

    def apply_ghost_theme(self, theme) -> None:
        for viewport in (getattr(self, "source_viewport", None), getattr(self, "target_viewport", None)):
            hook = getattr(viewport, "apply_ghost_theme", None)
            if callable(hook):
                hook(theme)
        dock_style = (
            "QDockWidget {"
            f"  background:{theme.color('panel.backgroundAlt', theme.color('panel.altBackground'))};"
            f"  color:{theme.color('text.primary')};"
            f"  border:1px solid {theme.color('panel.border')};"
            "}"
            "QDockWidget::title {"
            f"  background:{theme.color('toolbar.background')};"
            f"  color:{theme.color('text.primary')};"
            "  padding:4px 8px;"
            "}"
        )
        for dock in getattr(self, "_retarget_docks", {}).values():
            dock.setStyleSheet(dock_style)
        self.statusBar().setStyleSheet(
            f"background:{theme.color('toolbar.background')}; color:{theme.color('text.secondary')};"
        )

    def apply_ghost_layout(self, layout) -> None:
        self.resize(layout.main_width, layout.main_height)
        for splitter in self.findChildren(QtWidgets.QSplitter):
            splitter.setHandleWidth(layout.spacing_value("splitterHandleWidth", 6))
        for dock in getattr(self, "_retarget_docks", {}).values():
            dock.setMinimumWidth(max(220, layout.viewport.preferred_width // 4))
        button_height = max(22, layout.toolbar("viewport").height - 8)
        for button in self.findChildren(QtWidgets.QPushButton):
            button.setMinimumHeight(button_height)
        for widget in [
            *self.findChildren(QtWidgets.QComboBox),
            *self.findChildren(QtWidgets.QSpinBox),
            *self.findChildren(QtWidgets.QDoubleSpinBox),
            *self.findChildren(QtWidgets.QLineEdit),
        ]:
            widget.setMinimumHeight(layout.spacing_value("inputHeight", 24))

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
        self.stop_action.triggered.connect(self._stop_requested)
        self.frame_source_action = QtGui.QAction("Frame Source", self)
        self.frame_source_action.triggered.connect(lambda: self.source_viewport.frame_all())
        self.frame_target_action = QtGui.QAction("Frame Target", self)
        self.frame_target_action.triggered.connect(lambda: self.target_viewport.frame_all())
        self.viewport_toolbar_action = QtGui.QAction("Viewport Toolbar", self)
        self.viewport_toolbar_action.setCheckable(True)
        self.viewport_toolbar_action.setChecked(False)
        self.viewport_toolbar_action.toggled.connect(lambda checked: self._set_viewport_chrome(toolbar=checked))
        self.viewcube_action = QtGui.QAction("ViewCube", self)
        self.viewcube_action.setCheckable(True)
        self.viewcube_action.setChecked(False)
        self.viewcube_action.toggled.connect(lambda checked: self._set_viewport_chrome(viewcube=checked))
        self.transform_typein_action = QtGui.QAction("Transform Type-In", self)
        self.transform_typein_action.setCheckable(True)
        self.transform_typein_action.setChecked(False)
        self.transform_typein_action.toggled.connect(lambda checked: self._set_viewport_chrome(transform_typein=checked))
        self.vertex_tweak_action = QtGui.QAction("Vertex", self)
        self.skin_paint_action = QtGui.QAction("Skin Paint", self)
        self.weight_balance_action = QtGui.QAction("Weights", self)
        self.diagnostics_action = QtGui.QAction("Diagnostics", self)
        self.cloth_rigging_action = QtGui.QAction("Cloth Rigging...", self)
        self.cloth_rigging_action.triggered.connect(self._show_cloth_tool)
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
        self.view_menu = self.menuBar().addMenu("View")
        self.view_menu.addAction(self.frame_source_action)
        self.view_menu.addAction(self.frame_target_action)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.viewport_toolbar_action)
        self.view_menu.addAction(self.viewcube_action)
        self.view_menu.addAction(self.transform_typein_action)
        self.view_menu.addSeparator()
        tools_menu = self.menuBar().addMenu("Tools")
        mode_menu = tools_menu.addMenu("Workbench Tools")
        mode_menu.addAction(self.vertex_tweak_action)
        mode_menu.addAction(self.skin_paint_action)
        mode_menu.addAction(self.weight_balance_action)
        mode_menu.addAction(self.diagnostics_action)
        tools_menu.addSeparator()
        tools_menu.addAction(self.cloth_rigging_action)

    def _build_statusbar(self) -> None:
        self.statusBar().showMessage("Ready")

    def _build_central(self) -> None:
        central = QtWidgets.QWidget(self)
        central_layout = QtWidgets.QVBoxLayout(central)
        central_layout.setContentsMargins(4, 4, 4, 4)
        central_layout.setSpacing(4)
        central_layout.addWidget(self._build_workbench_controls(), 0)

        self.source_viewport = QtRetargetViewportWidget(self)
        self.target_viewport = QtRetargetViewportWidget(self)
        self.source_viewport.set_renderer_settings(self._renderer_settings)
        self.target_viewport.set_renderer_settings(self._renderer_settings)
        self._shared_gpu_renderer = create_viewport_renderer(self._renderer_settings)
        self.source_viewport.set_shared_gpu_renderer(self._shared_gpu_renderer)
        self.target_viewport.set_shared_gpu_renderer(self._shared_gpu_renderer)
        self.source_viewport.set_dual_viewport_mode(True)
        self.target_viewport.set_dual_viewport_mode(True)
        self.source_viewport.set_navigation_profile(self._navigation_profile)
        self.target_viewport.set_navigation_profile(self._navigation_profile)
        self._sync_viewport_chrome_actions()

        self.panel = QtAnimationRetargetPanel(self)
        self.panel.sourceCurrentRequested.connect(self.sourceCurrentRequested.emit)
        self.panel.targetCurrentRequested.connect(self.targetCurrentRequested.emit)
        self.panel.sourceLibraryRequested.connect(self.sourceLibraryRequested.emit)
        self.panel.targetLibraryRequested.connect(self.targetLibraryRequested.emit)
        self.panel.sourceGameLibraryRequested.connect(self.sourceGameLibraryRequested.emit)
        self.panel.targetGameLibraryRequested.connect(self.targetGameLibraryRequested.emit)
        self.panel.sourceExternalImportRequested.connect(self.sourceExternalImportRequested.emit)
        self.panel.targetExternalImportRequested.connect(self.targetExternalImportRequested.emit)
        self.panel.previewRequested.connect(self.previewRequested.emit)
        self.panel.applyRequested.connect(self.applyRequested.emit)
        self.panel.pauseRequested.connect(self._pause_requested)
        self.panel.stopRequested.connect(self._stop_requested)
        self.panel.sourceAnimationPlayRequested.connect(self._source_animation_play_requested)

        viewport_split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        viewport_split.setChildrenCollapsible(False)
        viewport_split.addWidget(self._viewport_group(self.panel.source_box, self.source_viewport))
        viewport_split.addWidget(self._viewport_group(self.panel.target_box, self.target_viewport))
        viewport_split.setSizes([640, 640])

        root = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        root.setChildrenCollapsible(False)
        root.addWidget(viewport_split)
        root.addWidget(self.panel)
        root.setSizes([560, 260])
        central_layout.addWidget(root, 1)
        self.setCentralWidget(central)

    def set_renderer_settings(self, settings: RendererSettings | dict | None) -> None:
        self._renderer_settings = settings if isinstance(settings, RendererSettings) else RendererSettings.from_settings(settings or {})
        apply_settings = getattr(getattr(self, "_shared_gpu_renderer", None), "set_settings", None)
        if callable(apply_settings):
            apply_settings(self._renderer_settings)
        for viewport in (getattr(self, "source_viewport", None), getattr(self, "target_viewport", None)):
            if viewport is not None:
                viewport.set_renderer_settings(self._renderer_settings)

    def _build_workbench_controls(self) -> QtWidgets.QWidget:
        box = QtWidgets.QFrame(self)
        box.setObjectName("RetargetWorkbenchControls")
        outer = QtWidgets.QVBoxLayout(box)
        outer.setContentsMargins(4, 2, 4, 2)
        outer.setSpacing(3)

        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        mode_label = QtWidgets.QLabel("Mode", box)
        self.retarget_mode_combo = QtWidgets.QComboBox(box)
        self.retarget_mode_combo.setObjectName("retargetModeComboBox")
        self.retarget_mode_combo.setMinimumWidth(170)
        populate_retarget_mode_combo(self.retarget_mode_combo)
        top.addWidget(mode_label)
        top.addWidget(self.retarget_mode_combo)
        top.addStretch(1)
        self.retarget_workbench_status_label = QtWidgets.QLabel("Mode: Unreal → KOTOR", box)
        self.retarget_workbench_status_label.setObjectName("retargetWorkbenchStatusLabel")
        top.addWidget(self.retarget_workbench_status_label, 4)
        outer.addLayout(top)

        self.retarget_output_global_controls = QtWidgets.QFrame(box)
        self.retarget_output_global_controls.setObjectName("retargetOutputGlobalControls")
        self.retarget_output_global_controls.setVisible(False)
        names = QtWidgets.QHBoxLayout(self.retarget_output_global_controls)
        names.setContentsMargins(0, 0, 0, 0)
        names.setSpacing(6)
        self.kotor_output_name_mode_combo = QtWidgets.QComboBox(self.retarget_output_global_controls)
        self.kotor_output_name_mode_combo.setObjectName("kotorOutputNameModeComboBox")
        self.kotor_output_name_mode_combo.addItem("Vanilla slot override", KotorOutputAnimationNameMode.VANILLA_SLOT.value)
        self.kotor_output_name_mode_combo.addItem("Custom animation patch", KotorOutputAnimationNameMode.CUSTOM_PATCH.value)
        self.target_kotor_animation_slot_combo = QtWidgets.QComboBox(self.retarget_output_global_controls)
        self.target_kotor_animation_slot_combo.setObjectName("targetKotorAnimationSlotComboBox")
        self.target_kotor_animation_slot_combo.setEditable(True)
        self.target_kotor_animation_slot_combo.setMinimumWidth(120)
        self.custom_kotor_animation_name_edit = QtWidgets.QLineEdit(self.retarget_output_global_controls)
        self.custom_kotor_animation_name_edit.setObjectName("customKotorAnimationNameLineEdit")
        self.custom_kotor_animation_name_edit.setPlaceholderText("gr_spin_attack_01")
        self.output_unreal_clip_name_edit = QtWidgets.QLineEdit(self.retarget_output_global_controls)
        self.output_unreal_clip_name_edit.setObjectName("outputUnrealClipNameLineEdit")
        self.output_unreal_clip_name_edit.setPlaceholderText("pmbam_pause1")
        self.retarget_output_display_label_edit = QtWidgets.QLineEdit(self.retarget_output_global_controls)
        self.retarget_output_display_label_edit.setObjectName("retargetOutputDisplayLabelLineEdit")
        self.retarget_output_display_label_edit.setPlaceholderText("Display label / notes")
        for widget in (
            self.kotor_output_name_mode_combo,
            self.target_kotor_animation_slot_combo,
            self.custom_kotor_animation_name_edit,
            self.output_unreal_clip_name_edit,
            self.retarget_output_display_label_edit,
        ):
            names.addWidget(widget)
        outer.addWidget(self.retarget_output_global_controls, 0)

        details = QtWidgets.QGridLayout()
        details.setContentsMargins(0, 0, 0, 0)
        details.setHorizontalSpacing(10)
        details.setVerticalSpacing(1)
        self.retarget_workbench_inputs_label = QtWidgets.QLabel("Source: (not selected) / Target: (not selected)", box)
        self.retarget_workbench_inputs_label.setObjectName("retargetWorkbenchInputsLabel")
        self.retarget_workbench_output_label = QtWidgets.QLabel("Output: (not selected)", box)
        self.retarget_workbench_output_label.setObjectName("retargetWorkbenchOutputLabel")
        self.retarget_workbench_runtime_label = QtWidgets.QLabel("Runtime: Vanilla slot override", box)
        self.retarget_workbench_runtime_label.setObjectName("retargetWorkbenchRuntimeLabel")
        details.addWidget(self.retarget_workbench_inputs_label, 0, 0)
        details.addWidget(self.retarget_workbench_output_label, 0, 1)
        details.addWidget(self.retarget_workbench_runtime_label, 1, 0, 1, 2)
        outer.addLayout(details)
        return box

    def _build_overrides_panel(self) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget(self)
        layout = QtWidgets.QFormLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)

        self.kotor_output_name_mode_combo = QtWidgets.QComboBox(box)
        self.kotor_output_name_mode_combo.setObjectName("kotorOutputNameModeComboBox")
        self.kotor_output_name_mode_combo.addItem("Vanilla slot override", KotorOutputAnimationNameMode.VANILLA_SLOT.value)
        self.kotor_output_name_mode_combo.addItem("Custom animation patch", KotorOutputAnimationNameMode.CUSTOM_PATCH.value)
        self.target_kotor_animation_slot_combo = QtWidgets.QComboBox(box)
        self.target_kotor_animation_slot_combo.setObjectName("targetKotorAnimationSlotComboBox")
        self.target_kotor_animation_slot_combo.setEditable(True)
        self.target_kotor_animation_slot_combo.setMinimumWidth(160)
        self.custom_kotor_animation_name_edit = QtWidgets.QLineEdit(box)
        self.custom_kotor_animation_name_edit.setObjectName("customKotorAnimationNameLineEdit")
        self.custom_kotor_animation_name_edit.setPlaceholderText("gr_spin_attack_01")
        self.output_unreal_clip_name_edit = QtWidgets.QLineEdit(box)
        self.output_unreal_clip_name_edit.setObjectName("outputUnrealClipNameLineEdit")
        self.output_unreal_clip_name_edit.setPlaceholderText("pmbam_pause1")
        self.retarget_output_display_label_edit = QtWidgets.QLineEdit(box)
        self.retarget_output_display_label_edit.setObjectName("retargetOutputDisplayLabelLineEdit")
        self.retarget_output_display_label_edit.setPlaceholderText("Display label / notes")

        layout.addRow("Output type", self.kotor_output_name_mode_combo)
        layout.addRow("Vanilla slot", self.target_kotor_animation_slot_combo)
        layout.addRow("Custom patch", self.custom_kotor_animation_name_edit)
        layout.addRow("UE clip", self.output_unreal_clip_name_edit)
        layout.addRow("Label / notes", self.retarget_output_display_label_edit)
        return box

    def _build_retarget_docks(self) -> None:
        self._retarget_docks = {}
        animations = self._create_retarget_dock("animations", "Animations", self.panel.animation_section)
        info = self._create_retarget_dock("information", "Information", self.panel.info_section)
        transfer = self._create_retarget_dock("transfer", "Transfer", self.panel.transfer_section)
        overrides = self._create_retarget_dock("overrides", "Overrides", self._build_overrides_panel())

        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, animations)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, info)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, transfer)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, overrides)
        self.tabifyDockWidget(info, transfer)
        self.tabifyDockWidget(info, overrides)
        info.raise_()
        self.resizeDocks([animations], [300], QtCore.Qt.Horizontal)
        self.resizeDocks([info], [190], QtCore.Qt.Vertical)

    def _create_retarget_dock(self, key: str, title: str, widget: QtWidgets.QWidget) -> QtWidgets.QDockWidget:
        dock = QtWidgets.QDockWidget(title, self)
        dock.setObjectName(f"Retarget{key.title().replace('_', '')}Dock")
        dock.setWidget(widget)
        dock.setAllowedAreas(
            QtCore.Qt.LeftDockWidgetArea
            | QtCore.Qt.RightDockWidgetArea
            | QtCore.Qt.BottomDockWidgetArea
        )
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetClosable
            | QtWidgets.QDockWidget.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFloatable
        )
        self._retarget_docks[key] = dock
        view_menu = getattr(self, "view_menu", None)
        if view_menu is not None:
            view_menu.addAction(dock.toggleViewAction())
        return dock

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

    def set_navigation_profile(self, profile: object) -> None:
        self._navigation_profile = profile or DEFAULT_VIEWPORT_NAVIGATION_PROFILE
        if hasattr(self, "source_viewport"):
            self.source_viewport.set_navigation_profile(self._navigation_profile)
        if hasattr(self, "target_viewport"):
            self.target_viewport.set_navigation_profile(self._navigation_profile)

    def _set_viewport_chrome(
        self,
        *,
        toolbar: bool | None = None,
        viewcube: bool | None = None,
        transform_typein: bool | None = None,
    ) -> None:
        for viewport in (getattr(self, "source_viewport", None), getattr(self, "target_viewport", None)):
            if viewport is None:
                continue
            viewport.set_viewport_chrome_visible(
                toolbar=toolbar,
                viewcube=viewcube,
                transform_typein=transform_typein,
            )
        self._sync_viewport_chrome_actions()

    def _sync_viewport_chrome_actions(self) -> None:
        viewport = getattr(self, "source_viewport", None)
        if viewport is None:
            return
        for action, value in (
            (getattr(self, "viewport_toolbar_action", None), getattr(viewport, "viewport_toolbar_chrome_visible", False)),
            (getattr(self, "viewcube_action", None), getattr(viewport, "viewcube_chrome_visible", False)),
            (getattr(self, "transform_typein_action", None), getattr(viewport, "transform_typein_chrome_visible", False)),
        ):
            if action is None:
                continue
            with QtCore.QSignalBlocker(action):
                action.setChecked(bool(value))

    def set_source_resource_context(self, manager, game_tag: str = "K1") -> None:
        self._resource_manager = manager
        self._source_game = (game_tag or "K1").upper()

    def set_target_resource_context(self, manager, game_tag: str = "K1") -> None:
        self._resource_manager = manager
        self._target_game = (game_tag or "K1").upper()

    def set_source_model(self, model, game_tag: str = "") -> None:
        self._source_clip_preview_clip = None
        self._source_clip_mesh_model = None
        if game_tag:
            self._source_game = game_tag.upper()
        if self._resource_manager is not None:
            self.source_viewport.set_resource_manager(self._resource_manager, self._source_game)
        self.panel.set_source_model(model)
        self.source_viewport.load_model(model, self._texture_dir)
        self._refresh_cloth_tool()
        self.statusBar().showMessage(f"Source: {getattr(model, 'name', 'None') if model else 'None'}")

    def set_source_clip_preview(self, clip, mesh_model=None) -> None:
        self._source_clip_preview_clip = clip
        if mesh_model is None:
            mesh_model = self._source_clip_mesh_model
        else:
            self._source_clip_mesh_model = mesh_model
        preview_model = build_source_clip_preview_model(clip, mesh_model=mesh_model)
        self.panel.set_source_model(preview_model)
        self.panel.select_animation(str(getattr(clip, "clip_name", "") or ""))
        self.source_viewport.load_model(preview_model, self._texture_dir)
        if hasattr(self.source_viewport, "bones_button"):
            self.source_viewport.bones_button.blockSignals(True)
            self.source_viewport.bones_button.setChecked(True)
            self.source_viewport.bones_button.blockSignals(False)
        self.source_viewport.toggle_bones(True)
        self.source_viewport.set_joint_dot_enabled(True)
        self.source_viewport.clear_animation_pose()
        self.source_viewport.frame_all()
        node_count = int(getattr(preview_model, "_gr_source_clip_node_count", 0) or 0)
        mesh_count = int(getattr(preview_model, "_gr_source_clip_mesh_count", 0) or 0)
        sample_count = len(getattr(clip, "sampled_poses", []) or [])
        duration = float(getattr(clip, "duration_seconds", 0.0) or 0.0)
        mesh_suffix = f", {mesh_count} mesh" if mesh_count == 1 else (f", {mesh_count} meshes" if mesh_count else "")
        self.panel.source_label.setText(
            f"UE/FBX clip: {getattr(clip, 'clip_name', 'Source Clip')} "
            f"({node_count} nodes{mesh_suffix}, {sample_count} samples, {duration:.3f}s)"
        )
        self._refresh_cloth_tool()
        self.statusBar().showMessage(f"Source clip preview: {getattr(clip, 'clip_name', 'Source Clip')}")

    def set_source_clip_animation_pose(self, animation_name: str, time_seconds: float = 0.0) -> None:
        clip = self._source_clip_preview_clip
        if clip is None:
            return
        if animation_name and str(animation_name) != str(getattr(clip, "clip_name", "")):
            return
        self._set_source_clip_pose(clip, time_seconds)

    def play_source_clip_animation(self, animation_name: str) -> None:
        clip = self._source_clip_preview_clip
        if clip is None:
            self.statusBar().showMessage("No imported source clip is loaded.")
            return
        current_name = str(getattr(clip, "clip_name", "") or "")
        if animation_name and animation_name != current_name:
            self.statusBar().showMessage(f"Loading source animation: {animation_name}")
            return
        self._source_clip_play_name = current_name
        self._set_source_clip_pose(clip, 0.0)
        duration = float(getattr(clip, "duration_seconds", 0.0) or 0.0)
        if duration > 0.0 and len(getattr(clip, "sampled_poses", []) or []) > 1:
            self._source_clip_play_clock.restart()
            self._source_clip_play_timer.start()
        self.statusBar().showMessage(f"Playing source animation: {current_name}")

    def pause_source_clip_animation(self) -> None:
        self._source_clip_play_timer.stop()
        self.statusBar().showMessage("Source animation paused")

    def set_target_model(self, model, game_tag: str = "") -> None:
        if game_tag:
            self._target_game = game_tag.upper()
        if self._resource_manager is not None:
            self.target_viewport.set_resource_manager(self._resource_manager, self._target_game)
        self.panel.set_target_model(model)
        self.target_viewport.load_model(model, self._texture_dir)
        self._refresh_cloth_tool()
        self.statusBar().showMessage(f"Target: {getattr(model, 'name', 'None') if model else 'None'}")

    def set_mapping_report(self, report) -> None:
        self.panel.set_mapping_report(report)
        self.statusBar().showMessage(f"Mapped bones: {getattr(report, 'matched_count', 0)}")

    def set_library_rows(self, rows: list[dict]) -> None:
        self.panel.set_library_rows(rows)

    def config_kwargs(self) -> dict:
        return self.panel.config_kwargs()

    def selected_animation(self) -> str:
        return self.panel.selected_animation()

    def current_animation_assignment(self) -> dict:
        return self.panel.assignment_for_animation(self.panel.selected_animation())

    def checked_animation_assignments(self) -> list[dict]:
        return self.panel.checked_animation_assignments()

    def set_animation_assignment(self, anim_name: str, **kwargs) -> None:
        self.panel.set_animation_assignment(anim_name, **kwargs)

    def request_apply_options(self, source_anim, target_model) -> Optional[dict]:
        dialog = QtRetargetApplyDialog(source_anim, target_model, self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return None
        return dialog.values()

    def set_source_pose(self, pose, name: str = "", time: float = 0.0, length: float = 0.0) -> None:
        self.source_viewport.set_animation_pose(pose, name=name, time=time, length=length)

    def set_target_pose(self, pose, name: str = "", time: float = 0.0, length: float = 0.0) -> None:
        self.target_viewport.set_animation_pose(pose, name=name, time=time, length=length)

    def clear_poses(self) -> None:
        self._source_clip_play_timer.stop()
        self.source_viewport.clear_animation_pose()
        self.target_viewport.clear_animation_pose()

    def _set_source_clip_pose(self, clip, time_seconds: float) -> None:
        try:
            source_pose = clip.pose_at_time(float(time_seconds))
        except Exception:
            return
        pose = AnimPose(time=float(getattr(source_pose, "time_seconds", time_seconds) or time_seconds))
        model = getattr(self.source_viewport, "model", None)
        global_transforms = getattr(source_pose, "global_transforms", {}) or {}
        for node_name, transform in global_transforms.items():
            preview_node = None
            if model is not None and hasattr(model, "find_node"):
                try:
                    preview_node = model.find_node(str(node_name))
                except Exception:
                    preview_node = None
            position = self._source_clip_pose_delta(preview_node, str(node_name), global_transforms, transform)
            pose.nodes[str(node_name).lower()] = NodePose(
                name=str(node_name),
                position=tuple(float(v) for v in (position or (0.0, 0.0, 0.0))[:3]),
                rotation=(0.0, 0.0, 0.0, 1.0),
                scale=1.0,
            )
        self.source_viewport.set_animation_pose(
            pose,
            name=str(getattr(clip, "clip_name", "") or "Source Clip"),
            time=pose.time,
            length=float(getattr(clip, "duration_seconds", 0.0) or 0.0),
        )

    def _source_clip_pose_delta(self, preview_node, node_name: str, global_transforms: dict, transform) -> tuple[float, float, float]:
        position = tuple(float(v) for v in getattr(transform, "position", (0.0, 0.0, 0.0))[:3])
        parent_name = None
        parent = getattr(preview_node, "parent", None)
        if parent is not None and not getattr(parent, "_gr_source_clip_preview_root", False):
            parent_name = str(getattr(parent, "name", "") or "")
        parent_transform = global_transforms.get(parent_name) if parent_name else None
        if parent_transform is None:
            return position
        parent_position = tuple(float(v) for v in getattr(parent_transform, "position", (0.0, 0.0, 0.0))[:3])
        return (
            position[0] - parent_position[0],
            position[1] - parent_position[1],
            position[2] - parent_position[2],
        )

    def _tick_source_clip_playback(self) -> None:
        clip = self._source_clip_preview_clip
        if clip is None:
            self._source_clip_play_timer.stop()
            return
        duration = float(getattr(clip, "duration_seconds", 0.0) or 0.0)
        if duration <= 0.0:
            self._source_clip_play_timer.stop()
            return
        elapsed = max(0.0, self._source_clip_play_clock.elapsed() / 1000.0)
        self._set_source_clip_pose(clip, elapsed % duration)

    def _source_animation_play_requested(self, animation_name: str) -> None:
        clip = self._source_clip_preview_clip
        current_name = str(getattr(clip, "clip_name", "") or "") if clip is not None else ""
        if clip is not None and (not animation_name or animation_name == current_name):
            self.play_source_clip_animation(animation_name)
        else:
            self.statusBar().showMessage(f"Loading source animation: {animation_name}")
        self.sourceAnimationPlayRequested.emit(animation_name)

    def _pause_requested(self) -> None:
        self.pause_source_clip_animation()
        self.pauseRequested.emit()

    def _stop_requested(self) -> None:
        self.clear_poses()
        self.statusBar().showMessage("Preview stopped")
        self.stopRequested.emit()

    def _tool_mode_changed(self) -> None:
        active = self.tool_action_group.checkedAction()
        self.statusBar().showMessage(f"Tool: {active.text()}" if active else "Tools: Ready")

    def _show_cloth_tool(self) -> None:
        if not hasattr(self, "_cloth_tool"):
            self._cloth_tool = QtClothRetargetDialog(self)
        self._refresh_cloth_tool()
        self._cloth_tool.show()
        self._cloth_tool.raise_()
        self._cloth_tool.activateWindow()

    def _refresh_cloth_tool(self) -> None:
        tool = getattr(self, "_cloth_tool", None)
        if tool is not None:
            tool.set_models(self.panel._source_model, self.panel._target_model)


class QtClothRetargetDialog(QtWidgets.QDialog):
    """Manual source-cloth to target-cloth assignment helper."""

    def __init__(self, workbench: QtAnimationRetargetWindow):
        super().__init__(workbench)
        self.workbench = workbench
        self.source_model = None
        self.target_model = None
        self.setWindowTitle("Cloth Rigging")
        self.resize(620, 360)
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        self.source_combo = QtWidgets.QComboBox()
        self.target_combo = QtWidgets.QComboBox()
        self.attach_combo = QtWidgets.QComboBox()
        form.addRow("Source cloth", self.source_combo)
        form.addRow("Target cloth mesh", self.target_combo)
        form.addRow("Attach bone", self.attach_combo)
        root.addLayout(form)

        options = QtWidgets.QGroupBox("Cloth Settings")
        opt = QtWidgets.QGridLayout(options)
        self.preset_combo = QtWidgets.QComboBox()
        try:
            from src.autorig.cloth_rig import ClothRigPreset

            self.preset_combo.addItems(ClothRigPreset.names())
        except Exception:
            self.preset_combo.addItems(["Robe (Loose / K2 default)", "Cape (Light)", "Cape (Heavy)", "Belt / Loin-cloth"])
        self.copy_source_box = QtWidgets.QCheckBox("Copy source cloth parameters")
        self.copy_source_box.setChecked(True)
        self.attach_box = QtWidgets.QCheckBox("Re-parent target mesh to attach bone")
        opt.addWidget(QtWidgets.QLabel("Preset"), 0, 0)
        opt.addWidget(self.preset_combo, 0, 1)
        opt.addWidget(self.copy_source_box, 1, 0, 1, 2)
        opt.addWidget(self.attach_box, 2, 0, 1, 2)
        root.addWidget(options)

        self.summary = QtWidgets.QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMinimumHeight(92)
        root.addWidget(self.summary, 1)

        buttons = QtWidgets.QHBoxLayout()
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        self.apply_button = QtWidgets.QPushButton("Apply Cloth")
        self.remove_button = QtWidgets.QPushButton("Remove Cloth")
        self.close_button = QtWidgets.QPushButton("Close")
        self.refresh_button.clicked.connect(lambda: self.set_models(self.source_model, self.target_model))
        self.apply_button.clicked.connect(self._apply_cloth)
        self.remove_button.clicked.connect(self._remove_cloth)
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.refresh_button)
        buttons.addStretch(1)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.remove_button)
        buttons.addWidget(self.close_button)
        root.addLayout(buttons)

    def set_models(self, source_model, target_model) -> None:
        self.source_model = source_model
        self.target_model = target_model
        self._fill_combo(self.source_combo, self._cloth_nodes(source_model, include_candidates=True))
        self._fill_combo(self.target_combo, self._cloth_nodes(target_model, include_candidates=True))
        self._fill_combo(self.attach_combo, self._bone_nodes(target_model))
        self._update_summary()

    def _fill_combo(self, combo: QtWidgets.QComboBox, nodes: list) -> None:
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        for node in nodes:
            label = f"{getattr(node, 'name', '?')}  ({getattr(node, 'type_label', 'node')})"
            combo.addItem(label, node)
        idx = combo.findText(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def _cloth_nodes(self, model, *, include_candidates: bool) -> list:
        if model is None or not hasattr(model, "all_nodes"):
            return []
        try:
            from src.autorig.cloth_rig import ClothRigger

            patterns = tuple(ClothRigger.CLOTH_NAME_PATTERNS)
        except Exception:
            patterns = ("cloth", "cloak", "cape", "robe", "sash", "skirt", "belt")
        nodes = []
        for node in model.all_nodes():
            if not getattr(node, "is_mesh", False) or getattr(node, "is_skin", False):
                continue
            name = str(getattr(node, "name", "")).lower()
            is_cloth = bool(getattr(node, "is_dangly", False)) or any(part in name for part in patterns)
            if is_cloth or include_candidates:
                nodes.append(node)
        nodes.sort(key=lambda n: (not bool(getattr(n, "is_dangly", False)), str(getattr(n, "name", "")).lower()))
        return nodes

    def _bone_nodes(self, model) -> list:
        if model is None or not hasattr(model, "all_nodes"):
            return []
        nodes = [
            node for node in model.all_nodes()
            if not getattr(node, "is_mesh", False)
            and not getattr(node, "is_skin", False)
        ]
        nodes.sort(key=lambda n: str(getattr(n, "name", "")).lower())
        return nodes

    def _selected_node(self, combo: QtWidgets.QComboBox):
        return combo.currentData()

    def _apply_cloth(self) -> None:
        target = self._selected_node(self.target_combo)
        if target is None:
            self.summary.setPlainText("Select a target cloth mesh first.")
            return
        try:
            from src.autorig.cloth_rig import ClothRigConfig, ClothRigPreset, ClothRigger

            source = self._selected_node(self.source_combo)
            if self.copy_source_box.isChecked() and source is not None and getattr(source, "is_dangly", False):
                cfg = ClothRigConfig(
                    displacement=float(getattr(source, "dangly_displacement", 0.5) or 0.5),
                    tightness=float(getattr(source, "dangly_tightness", 0.5) or 0.5),
                    period=float(getattr(source, "dangly_period", 1.0) or 1.0),
                    constraint_mode="manual",
                )
            else:
                cfg = ClothRigPreset.get(self.preset_combo.currentText())
            rigger = ClothRigger()
            ok = rigger.apply_cloth_to_node(target, cfg)
            if ok and source is not None and len(getattr(source, "dangly_constraints", []) or []) == len(getattr(target, "vertices", []) or []):
                target.dangly_constraints = list(getattr(source, "dangly_constraints", []) or [])
            if ok and self.attach_box.isChecked():
                self._reparent_target(target, self._selected_node(self.attach_combo))
            self.workbench.target_viewport.refresh_node_transform(target)
            self.set_models(self.source_model, self.target_model)
            self.summary.setPlainText(f"Applied cloth rigging to {getattr(target, 'name', '?')}.")
            self.workbench.statusBar().showMessage(f"Cloth rigged: {getattr(target, 'name', '?')}")
        except Exception as exc:
            self.summary.setPlainText(f"Cloth rigging failed: {exc}")

    def _remove_cloth(self) -> None:
        target = self._selected_node(self.target_combo)
        if target is None:
            self.summary.setPlainText("Select a target cloth mesh first.")
            return
        try:
            from src.autorig.cloth_rig import ClothRigger

            removed = ClothRigger().remove_cloth_from_node(target)
            self.workbench.target_viewport.refresh_node_transform(target)
            self.set_models(self.source_model, self.target_model)
            self.summary.setPlainText(
                f"Removed cloth rigging from {getattr(target, 'name', '?')}." if removed else "Target was not a cloth/dangly mesh."
            )
        except Exception as exc:
            self.summary.setPlainText(f"Remove cloth failed: {exc}")

    def _reparent_target(self, target, bone) -> None:
        if target is None or bone is None or target is bone:
            return
        old_parent = getattr(target, "parent", None)
        if old_parent is not None and target in getattr(old_parent, "children", []):
            old_parent.children.remove(target)
        target.parent = bone
        if target not in getattr(bone, "children", []):
            bone.children.append(target)

    def _update_summary(self) -> None:
        src_count = self.source_combo.count()
        dst_count = self.target_combo.count()
        bone_count = self.attach_combo.count()
        self.summary.setPlainText(
            f"Source cloth candidates: {src_count}\n"
            f"Target cloth candidates: {dst_count}\n"
            f"Target attach bones: {bone_count}\n"
            "Pick matching source and target cloth pieces, then apply cloth settings to the target."
        )


class QtRetargetApplyDialog(QtWidgets.QDialog):
    """Confirm how a retargeted animation should be added to the target model."""

    def __init__(self, source_anim, target_model, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.source_anim = source_anim
        self.target_model = target_model
        self._existing_names = {
            str(getattr(anim, "name", "") or "").lower()
            for anim in (getattr(target_model, "animations", []) or [])
        }
        self.setWindowTitle("Apply Retargeted Animation")
        self.resize(460, 230)
        self._build()
        self._update_state()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        details = QtWidgets.QPlainTextEdit()
        details.setReadOnly(True)
        details.setMaximumHeight(76)
        details.setPlainText(
            f"Source animation: {getattr(self.source_anim, 'name', '')}\n"
            f"Target model: {getattr(self.target_model, 'name', '')}\n"
            f"Length: {float(getattr(self.source_anim, 'length', 0.0) or 0.0):.3f} s"
        )
        root.addWidget(details)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        self.name_edit = QtWidgets.QLineEdit(self._default_name())
        self.name_edit.textChanged.connect(self._update_state)
        form.addRow("Animation name", self.name_edit)
        root.addLayout(form)

        self.replace_box = QtWidgets.QCheckBox("Replace existing animation with this name")
        self.replace_box.toggled.connect(self._update_state)
        root.addWidget(self.replace_box)

        self.message = QtWidgets.QLabel("")
        self.message.setWordWrap(True)
        root.addWidget(self.message)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.ok_button = buttons.button(QtWidgets.QDialogButtonBox.Ok)
        self.ok_button.setText("Add Animation")
        root.addWidget(buttons)

    def _default_name(self) -> str:
        base = str(getattr(self.source_anim, "name", "") or "animation").strip() or "animation"
        if base.lower() not in self._existing_names:
            return base
        suffix_base = f"{base}_retarget"
        if suffix_base.lower() not in self._existing_names:
            return suffix_base
        index = 2
        while f"{suffix_base}{index}".lower() in self._existing_names:
            index += 1
        return f"{suffix_base}{index}"

    def _update_state(self) -> None:
        name = self.name_edit.text().strip()
        exists = name.lower() in self._existing_names if name else False
        valid = bool(name) and (not exists or self.replace_box.isChecked())
        self.replace_box.setEnabled(bool(name and exists))
        self.ok_button.setEnabled(valid)
        if not name:
            self.message.setText("Enter a name for the animation.")
        elif exists and not self.replace_box.isChecked():
            self.message.setText("That animation already exists on the target model.")
        elif exists:
            self.message.setText("The existing animation will be replaced on the target model.")
        else:
            self.message.setText("The animation will be added to the target model.")

    def values(self) -> dict:
        name = self.name_edit.text().strip()
        return {
            "name": name,
            "replace": name.lower() in self._existing_names and self.replace_box.isChecked(),
        }
