"""Detachable animation retargeting workbench."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.qt_lib.panels.qt_animation_panel import QtAnimationRetargetPanel
from src.gui.qt_lib.rendering.qt_gpu_renderer import GpuRenderer
from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget
from src.gui.qt_lib.rendering.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE


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
        self._navigation_profile = DEFAULT_VIEWPORT_NAVIGATION_PROFILE
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
        view_menu = self.menuBar().addMenu("View")
        view_menu.addAction(self.frame_source_action)
        view_menu.addAction(self.frame_target_action)
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
        root = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        root.setChildrenCollapsible(False)
        self.source_viewport = QtViewportWidget(self)
        self.target_viewport = QtViewportWidget(self)
        self._shared_gpu_renderer = GpuRenderer()
        self.source_viewport.set_shared_gpu_renderer(self._shared_gpu_renderer)
        self.target_viewport.set_shared_gpu_renderer(self._shared_gpu_renderer)
        self.source_viewport.set_dual_viewport_mode(True)
        self.target_viewport.set_dual_viewport_mode(True)
        self.source_viewport.set_navigation_profile(self._navigation_profile)
        self.target_viewport.set_navigation_profile(self._navigation_profile)

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

    def set_navigation_profile(self, profile: object) -> None:
        self._navigation_profile = profile or DEFAULT_VIEWPORT_NAVIGATION_PROFILE
        if hasattr(self, "source_viewport"):
            self.source_viewport.set_navigation_profile(self._navigation_profile)
        if hasattr(self, "target_viewport"):
            self.target_viewport.set_navigation_profile(self._navigation_profile)

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
        self._refresh_cloth_tool()
        self.statusBar().showMessage(f"Source: {getattr(model, 'name', 'None') if model else 'None'}")

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

    def config_kwargs(self) -> dict:
        return self.panel.config_kwargs()

    def selected_animation(self) -> str:
        return self.panel.selected_animation()

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
        self.source_viewport.clear_animation_pose()
        self.target_viewport.clear_animation_pose()

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
