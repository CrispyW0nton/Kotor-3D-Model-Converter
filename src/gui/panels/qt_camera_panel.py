"""Dockable camera explorer and properties panel."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.camera.camera_manager import CameraManager
from src.core.camera.camera_model import CAMERA_TYPES, GhostRiggerCamera
from src.core.camera.camera_presets import FRAMING_PRESETS, LENS_PRESETS, LETTERBOX_PRESETS, RESOLUTION_PRESETS, SENSOR_PRESETS
from src.math.camera_math import euler_degrees_to_quat, quat_to_euler_degrees
from src.gui.libtheme.collapsible_group import CollapsibleGroupBox
from src.gui.qt_lib.assets import qt_icon_manager


class QtCameraPanel(QtWidgets.QWidget):
    cameraSelected = QtCore.Signal(object)
    cameraChanged = QtCore.Signal()
    activeCameraRequested = QtCore.Signal(str)
    clearActiveCameraRequested = QtCore.Signal()
    createCameraRequested = QtCore.Signal(str)
    createFromViewRequested = QtCore.Signal()
    alignCameraToViewRequested = QtCore.Signal(str)
    alignViewToCameraRequested = QtCore.Signal(str)
    deleteCameraRequested = QtCore.Signal(str)
    duplicateCameraRequested = QtCore.Signal(str)
    renderFrameRequested = QtCore.Signal()

    _COLUMNS = ("Enabled", "Name", "Type", "Focal", "FOV", "Resolution", "Aspect", "Locked", "Active")
    _CAMERA_ICONS = {
        "Free Camera": qt_icon_manager.I.CAMERA_FREE,
        "Target Camera": qt_icon_manager.I.CAMERA_TARGET,
        "Cinematic Camera": qt_icon_manager.I.CAMERA_CINEMATIC,
        "Orthographic Camera": qt_icon_manager.I.CAMERAS,
    }
    _AXES = ("x", "y", "z")

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("CameraPanel")
        self.manager = CameraManager()
        self._model = None
        self._selected: GhostRiggerCamera | None = None
        self._updating = False
        self._theme = None
        self._selection_buttons: list[QtWidgets.QAbstractButton] = []
        self._axis_badges: list[QtWidgets.QLabel] = []
        self._axis_strips: list[QtWidgets.QFrame] = []
        self._section_labels: list[QtWidgets.QLabel] = []
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        action_group = QtWidgets.QGroupBox("Camera Actions")
        action_layout = QtWidgets.QGridLayout(action_group)
        action_layout.setContentsMargins(6, 9, 6, 6)
        action_layout.setHorizontalSpacing(4)
        action_layout.setVerticalSpacing(4)
        for column, (label, camera_type, icon_name) in enumerate((
            ("Free", "Free Camera", qt_icon_manager.I.CAMERA_FREE),
            ("Target", "Target Camera", qt_icon_manager.I.CAMERA_TARGET),
            ("Cine", "Cinematic Camera", qt_icon_manager.I.CAMERA_CINEMATIC),
        )):
            button = self._camera_action_button(label, icon_name, f"Create {camera_type}")
            button.clicked.connect(lambda _checked=False, t=camera_type: self.createCameraRequested.emit(t))
            action_layout.addWidget(button, 0, column)
        from_view = self._camera_action_button(
            "From View",
            qt_icon_manager.I.VIEWPORT_SELECT_CAMERAS,
            "Create a camera from the current viewport view",
        )
        from_view.clicked.connect(self.createFromViewRequested.emit)
        action_layout.addWidget(from_view, 0, 3)
        render = self._camera_action_button("Render", qt_icon_manager.I.CAMERAS, "Render a still frame from the active camera")
        render.clicked.connect(self.renderFrameRequested.emit)
        action_layout.addWidget(render, 0, 4)
        for column in range(5):
            action_layout.setColumnStretch(column, 1)
        root.addWidget(action_group)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setObjectName("CameraPanelTree")
        self.tree.setHeaderLabels(list(self._COLUMNS))
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree.setAlternatingRowColors(True)
        self.tree.setAllColumnsShowFocus(True)
        self.tree.setIconSize(QtCore.QSize(16, 16))
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemDoubleClicked.connect(lambda item, _col=0: self._emit_align_view(item))
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        for index, width in enumerate((54, 128, 112, 62, 58, 92, 62, 54, 52)):
            self.tree.setColumnWidth(index, width)
        self.tree.header().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(1, QtCore.Qt.AscendingOrder)
        root.addWidget(self.tree, 1)

        editor = CollapsibleGroupBox("Selected Camera")
        editor_grid = QtWidgets.QGridLayout(editor)
        editor_grid.setContentsMargins(7, 10, 7, 7)
        editor_grid.setHorizontalSpacing(6)
        editor_grid.setVerticalSpacing(4)
        for column in (1, 3, 5, 7):
            editor_grid.setColumnStretch(column, 1)

        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.editingFinished.connect(self._apply_editor)
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(CAMERA_TYPES)
        self.type_combo.currentIndexChanged.connect(lambda _index=0: self._apply_editor())
        self.enabled_check = QtWidgets.QCheckBox("Enabled")
        self.visible_check = QtWidgets.QCheckBox("Visible")
        self.locked_check = QtWidgets.QCheckBox("Locked")
        for check in (self.enabled_check, self.visible_check, self.locked_check):
            check.toggled.connect(lambda _state=False: self._apply_editor())
        flags = QtWidgets.QHBoxLayout()
        flags.setSpacing(10)
        flags.addWidget(self.enabled_check)
        flags.addWidget(self.visible_check)
        flags.addWidget(self.locked_check)
        flags.addStretch(1)
        editor_grid.addWidget(self._field_label("Name"), 0, 0)
        editor_grid.addWidget(self.name_edit, 0, 1, 1, 3)
        editor_grid.addWidget(self._field_label("Type"), 0, 4)
        editor_grid.addWidget(self.type_combo, 0, 5, 1, 3)
        editor_grid.addLayout(flags, 1, 1, 1, 7)

        self.pos_spins = [self._double_spin(-100000.0, 100000.0, 0.1, 3) for _ in range(3)]
        self.rot_spins = [self._double_spin(-360.0, 360.0, 1.0, 2) for _ in range(3)]
        self._mark_axis_spins(self.pos_spins, "Position")
        self._mark_axis_spins(self.rot_spins, "Rotation")
        editor_grid.addWidget(self._section_label("Transform"), 2, 0, 1, 8)
        self._add_axis_row(editor_grid, 3, "Position", self.pos_spins)
        self._add_axis_row(editor_grid, 4, "Rotation", self.rot_spins)
        self.target_enabled_check = QtWidgets.QCheckBox("Target Enabled")
        self.target_enabled_check.toggled.connect(lambda _state=False: self._apply_editor())
        self.follow_target_check = QtWidgets.QCheckBox("Follow")
        self.follow_target_check.setToolTip("Move the camera with the bound target object while preserving the camera offset")
        self.follow_target_check.toggled.connect(lambda _state=False: self._apply_editor())
        self.target_object_combo = QtWidgets.QComboBox()
        self.target_object_combo.setToolTip("Use a scene object as this camera's look-at target")
        self.target_object_combo.currentIndexChanged.connect(lambda _index=0: self._apply_editor())
        self.target_spins = [self._double_spin(-100000.0, 100000.0, 0.1, 3) for _ in range(3)]
        self._mark_axis_spins(self.target_spins, "Target")
        editor_grid.addWidget(self.target_enabled_check, 5, 1, 1, 2)
        editor_grid.addWidget(self.follow_target_check, 5, 3)
        editor_grid.addWidget(self._field_label("Target Object"), 5, 4)
        editor_grid.addWidget(self.target_object_combo, 5, 5, 1, 3)
        self._add_axis_row(editor_grid, 6, "Target", self.target_spins)
        self.focus_spin = self._double_spin(0.0, 1000000.0, 1.0, 2)
        editor_grid.addWidget(self._field_label("Focus"), 7, 4)
        editor_grid.addWidget(self.focus_spin, 7, 5, 1, 3)

        self.lens_combo = QtWidgets.QComboBox()
        self.lens_combo.addItems([*LENS_PRESETS.keys(), "Custom"])
        self.lens_combo.currentTextChanged.connect(self._apply_lens_preset)
        self.focal_spin = self._double_spin(0.1, 1000.0, 1.0, 2)
        self.fov_spin = self._double_spin(1.0, 179.0, 1.0, 2)
        self.sensor_combo = QtWidgets.QComboBox()
        self.sensor_combo.addItems([*SENSOR_PRESETS.keys(), "Custom"])
        self.sensor_combo.currentTextChanged.connect(self._apply_sensor_preset)
        self.sensor_w_spin = self._double_spin(0.1, 200.0, 0.1, 2)
        self.sensor_h_spin = self._double_spin(0.1, 200.0, 0.1, 2)
        self.aperture_spin = self._double_spin(0.1, 64.0, 0.1, 1)
        self.near_spin = self._double_spin(0.001, 100000.0, 0.1, 3)
        self.far_spin = self._double_spin(0.01, 10000000.0, 100.0, 1)
        editor_grid.addWidget(self._section_label("Optics"), 8, 0, 1, 8)
        editor_grid.addWidget(self._field_label("Lens"), 9, 0)
        editor_grid.addWidget(self.lens_combo, 9, 1, 1, 3)
        editor_grid.addWidget(self._field_label("Focal / FOV"), 9, 4)
        editor_grid.addLayout(self._row([self.focal_spin, self.fov_spin]), 9, 5, 1, 3)
        editor_grid.addWidget(self._field_label("Sensor"), 10, 0)
        editor_grid.addWidget(self.sensor_combo, 10, 1, 1, 3)
        editor_grid.addWidget(self._field_label("Sensor W/H"), 10, 4)
        editor_grid.addLayout(self._row([self.sensor_w_spin, self.sensor_h_spin]), 10, 5, 1, 3)
        editor_grid.addWidget(self._field_label("Aperture"), 11, 0)
        editor_grid.addWidget(self.aperture_spin, 11, 1, 1, 3)
        editor_grid.addWidget(self._field_label("Near / Far"), 11, 4)
        editor_grid.addLayout(self._row([self.near_spin, self.far_spin]), 11, 5, 1, 3)

        self.resolution_combo = QtWidgets.QComboBox()
        self.resolution_combo.addItems([*RESOLUTION_PRESETS.keys(), "Custom"])
        self.resolution_combo.currentTextChanged.connect(self._apply_resolution_preset)
        self.res_w_spin = self._int_spin(1, 16384, 1)
        self.res_h_spin = self._int_spin(1, 16384, 1)
        self.aspect_w_spin = self._int_spin(1, 1000, 1)
        self.aspect_h_spin = self._int_spin(1, 1000, 1)
        self.safe_check = QtWidgets.QCheckBox("Safe Frame")
        self.letterbox_check = QtWidgets.QCheckBox("Letterbox")
        for check in (self.safe_check, self.letterbox_check):
            check.toggled.connect(lambda _state=False: self._apply_editor())
        self.letterbox_combo = QtWidgets.QComboBox()
        self.letterbox_combo.addItems([*LETTERBOX_PRESETS.keys(), "Custom"])
        self.letterbox_combo.currentTextChanged.connect(self._apply_letterbox_preset)
        self.letterbox_spin = self._double_spin(0.1, 10.0, 0.01, 2)
        self.framing_combo = QtWidgets.QComboBox()
        self.framing_combo.addItems([*FRAMING_PRESETS.keys(), "Custom"])
        self.framing_combo.currentTextChanged.connect(self._apply_framing_preset)
        frame_flags = QtWidgets.QHBoxLayout()
        frame_flags.setSpacing(10)
        frame_flags.addWidget(self.safe_check)
        frame_flags.addWidget(self.letterbox_check)
        frame_flags.addStretch(1)
        editor_grid.addWidget(self._section_label("Frame"), 12, 0, 1, 8)
        editor_grid.addWidget(self._field_label("Resolution"), 13, 0)
        editor_grid.addWidget(self.resolution_combo, 13, 1, 1, 3)
        editor_grid.addWidget(self._field_label("Width / Height"), 13, 4)
        editor_grid.addLayout(self._row([self.res_w_spin, self.res_h_spin]), 13, 5, 1, 3)
        editor_grid.addWidget(self._field_label("Aspect W/H"), 14, 0)
        editor_grid.addLayout(self._row([self.aspect_w_spin, self.aspect_h_spin]), 14, 1, 1, 3)
        editor_grid.addWidget(self._field_label("Preset"), 14, 4)
        editor_grid.addWidget(self.framing_combo, 14, 5, 1, 3)
        editor_grid.addLayout(frame_flags, 15, 1, 1, 3)
        editor_grid.addWidget(self._field_label("Letterbox"), 15, 4)
        editor_grid.addLayout(self._row([self.letterbox_combo, self.letterbox_spin]), 15, 5, 1, 3)

        action_row = QtWidgets.QHBoxLayout()
        action_row.setSpacing(5)
        self.active_button = self._editor_button("Set Active", qt_icon_manager.I.CAMERA_CINEMATIC, "Use the selected camera as the active render/view camera")
        self.active_button.clicked.connect(lambda: self._selected and self.activeCameraRequested.emit(self._selected.id))
        clear_active = self._editor_button("Perspective", qt_icon_manager.I.VIEWPORT_SELECT_CAMERAS, "Return the viewport to perspective view")
        clear_active.clicked.connect(self.clearActiveCameraRequested.emit)
        align_to_view = self._editor_button("Align To View", qt_icon_manager.I.VIEWPORT_LOCK_CAMERA, "Align the selected camera to the current viewport")
        align_to_view.clicked.connect(lambda: self._selected and self.alignCameraToViewRequested.emit(self._selected.id))
        view_to = self._editor_button("View", qt_icon_manager.I.CAMERAS, "Look through the selected camera")
        view_to.clicked.connect(lambda: self._selected and self.alignViewToCameraRequested.emit(self._selected.id))
        for button in (self.active_button, clear_active, align_to_view, view_to):
            action_row.addWidget(button)
        self._selection_buttons = [self.active_button, align_to_view, view_to]
        editor_grid.addLayout(action_row, 16, 1, 1, 7)
        root.addWidget(editor)

        self._set_editor_enabled(False)

    def apply_ghost_theme(self, theme) -> None:
        self._theme = theme
        self.setStyleSheet("")
        self._apply_camera_theme_accents(theme)
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            camera = self._camera_from_item(item)
            if camera is not None:
                self._tone_item(item, camera, self.manager.active_camera_id)

    def apply_native_theme(self) -> None:
        theme = self._resolve_active_theme()
        if theme is not None:
            self.apply_ghost_theme(theme)
        else:
            self.setStyleSheet("")

    def _resolve_active_theme(self):
        widget: QtWidgets.QWidget | None = self
        while widget is not None:
            manager = getattr(widget, "theme_manager", None)
            if manager is not None:
                try:
                    return manager.current_theme or manager.get_theme()
                except Exception:
                    return None
            widget = widget.parentWidget()
        return None

    def apply_ghost_layout(self, layout) -> None:
        margin = layout.spacing_value("margin", 4)
        spacing = layout.spacing_value("panelSpacing", 4)
        if self.layout() is not None:
            self.layout().setContentsMargins(margin, margin, margin, margin)
            self.layout().setSpacing(spacing)
        row_height = layout.spacing_value("treeRowHeight", 22)
        self.tree.setUniformRowHeights(True)
        self.tree.header().setMinimumSectionSize(max(36, row_height + 14))
        input_height = layout.spacing_value("inputHeight", 24)
        for widget in [
            *self.findChildren(QtWidgets.QLineEdit),
            *self.findChildren(QtWidgets.QComboBox),
            *self.findChildren(QtWidgets.QSpinBox),
            *self.findChildren(QtWidgets.QDoubleSpinBox),
        ]:
            widget.setMinimumHeight(input_height)
        for button in [*self.findChildren(QtWidgets.QPushButton), *self.findChildren(QtWidgets.QToolButton)]:
            button.setMinimumHeight(max(22, layout.toolbar("viewport").height - 8))

    def set_model(self, model) -> None:
        self._model = model
        self.manager.set_model(model)
        self.refresh()

    def refresh(self) -> None:
        active_id = self.manager.active_camera_id
        sort_enabled = self.tree.isSortingEnabled()
        sort_column = self.tree.sortColumn()
        sort_order = self.tree.header().sortIndicatorOrder()
        self._updating = True
        self.tree.setSortingEnabled(False)
        self.tree.clear()
        selected_items = []
        for camera in self.manager.get_all_cameras():
            item = self._make_item(camera, active_id)
            self.tree.addTopLevelItem(item)
            if camera.selected or (self._selected and camera.id == self._selected.id):
                selected_items.append(item)
        for item in selected_items:
            item.setSelected(True)
            self.tree.setCurrentItem(item)
        self.tree.setSortingEnabled(sort_enabled)
        if sort_enabled:
            self.tree.sortItems(sort_column, sort_order)
        self._updating = False
        if selected_items:
            self._load_editor(self._camera_from_item(selected_items[-1]))
        else:
            self._load_editor(None)

    def select_camera_object(self, node) -> None:
        camera = self.manager.find_by_original(node)
        if camera is None:
            self._load_editor(None)
            return
        self.manager.select_camera(camera.id)
        self._selected = camera
        self.refresh()

    def _make_item(self, camera: GhostRiggerCamera, active_id: str) -> QtWidgets.QTreeWidgetItem:
        aspect = f"{camera.aspect_ratio_width}:{camera.aspect_ratio_height}"
        item = QtWidgets.QTreeWidgetItem([
            "",
            camera.name,
            camera.camera_type,
            f"{camera.focal_length_mm:.1f}mm",
            f"{camera.field_of_view_degrees:.1f}",
            f"{camera.resolution_width}x{camera.resolution_height}",
            aspect,
            "Yes" if camera.locked else "No",
            "Yes" if camera.id == active_id else "",
        ])
        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(0, QtCore.Qt.Checked if camera.enabled else QtCore.Qt.Unchecked)
        item.setData(0, QtCore.Qt.UserRole, camera.id)
        item.setIcon(1, self._camera_icon(camera.camera_type))
        item.setToolTip(1, camera.name)
        item.setToolTip(2, camera.camera_type)
        item.setToolTip(5, f"{camera.resolution_width} x {camera.resolution_height}")
        for col in (3, 4, 6, 7, 8):
            item.setTextAlignment(col, QtCore.Qt.AlignCenter)
        self._tone_item(item, camera, active_id)
        return item

    def _camera_from_item(self, item: QtWidgets.QTreeWidgetItem | None) -> GhostRiggerCamera | None:
        if item is None:
            return None
        return self.manager.get_camera(str(item.data(0, QtCore.Qt.UserRole) or ""))

    def _on_tree_selection(self) -> None:
        if self._updating:
            return
        cameras = [self._camera_from_item(item) for item in self.tree.selectedItems()]
        clean = [camera for camera in cameras if camera is not None]
        active = self._camera_from_item(self.tree.currentItem()) or (clean[-1] if clean else None)
        self.manager.select_many(clean, active=active)
        self._selected = active
        self._load_editor(active)
        self.cameraSelected.emit(active.original_ref if active else None)

    def _on_item_changed(self, item: QtWidgets.QTreeWidgetItem, column: int) -> None:
        if self._updating or column != 0:
            return
        camera = self._camera_from_item(item)
        if camera is None:
            return
        camera.enabled = item.checkState(0) == QtCore.Qt.Checked
        camera.apply_to_original()
        self.manager._store_on_model()
        self.cameraChanged.emit()

    def _load_editor(self, camera: GhostRiggerCamera | None) -> None:
        self._updating = True
        self._selected = camera
        self._set_editor_enabled(camera is not None)
        if camera is None:
            self._updating = False
            return
        self.name_edit.setText(camera.name)
        self.type_combo.setCurrentIndex(max(0, self.type_combo.findText(camera.camera_type)))
        self.enabled_check.setChecked(camera.enabled)
        self.visible_check.setChecked(camera.visible)
        self.locked_check.setChecked(camera.locked)
        for idx, spin in enumerate(self.pos_spins):
            spin.setValue(float(camera.position[idx]))
        rotation = quat_to_euler_degrees(camera.rotation)
        for idx, spin in enumerate(self.rot_spins):
            spin.setValue(float(rotation[idx]))
        self.target_enabled_check.setChecked(camera.target_enabled)
        self.follow_target_check.setChecked(bool(getattr(camera, "target_follow_enabled", False)))
        self._populate_target_object_combo(camera)
        for idx, spin in enumerate(self.target_spins):
            spin.setValue(float(camera.target_position[idx]))
        self.focus_spin.setValue(float(camera.focus_distance))
        self.focal_spin.setValue(float(camera.focal_length_mm))
        self.fov_spin.setValue(float(camera.field_of_view_degrees))
        self.sensor_w_spin.setValue(float(camera.sensor_width_mm))
        self.sensor_h_spin.setValue(float(camera.sensor_height_mm))
        self.aperture_spin.setValue(float(camera.aperture_f_stop))
        self.near_spin.setValue(float(camera.near_clip))
        self.far_spin.setValue(float(camera.far_clip))
        self.res_w_spin.setValue(int(camera.resolution_width))
        self.res_h_spin.setValue(int(camera.resolution_height))
        self.aspect_w_spin.setValue(int(camera.aspect_ratio_width))
        self.aspect_h_spin.setValue(int(camera.aspect_ratio_height))
        self.safe_check.setChecked(bool(camera.show_safe_frame))
        self.letterbox_check.setChecked(bool(camera.show_letterbox))
        self.letterbox_spin.setValue(float(camera.letterbox_ratio))
        self._updating = False

    def _apply_editor(self, source: object | None = None) -> None:
        if self._updating or self._selected is None:
            return
        camera = self._selected
        camera.name = self.name_edit.text().strip() or camera.name
        camera.camera_type = self.type_combo.currentText()
        camera.enabled = self.enabled_check.isChecked()
        camera.visible = self.visible_check.isChecked()
        camera.locked = self.locked_check.isChecked()
        camera.position = tuple(float(spin.value()) for spin in self.pos_spins)
        camera.rotation = euler_degrees_to_quat(tuple(float(spin.value()) for spin in self.rot_spins))
        camera.target_enabled = self.target_enabled_check.isChecked()
        camera.target_follow_enabled = self.follow_target_check.isChecked()
        camera.target_position = tuple(float(spin.value()) for spin in self.target_spins)
        source = source or self.sender()
        if source in self.target_spins:
            camera.target_object_id = ""
        else:
            camera.target_object_id = self._selected_target_object_id()
            bound_target = self._target_object_position(camera.target_object_id)
            if bound_target is not None:
                camera.target_enabled = True
                camera.target_position = bound_target
                self._updating = True
                self.target_enabled_check.setChecked(True)
                for idx, spin in enumerate(self.target_spins):
                    spin.setValue(float(bound_target[idx]))
                self._updating = False
        camera.focus_distance = float(self.focus_spin.value())
        if abs(camera.sensor_width_mm - float(self.sensor_w_spin.value())) > 1e-6 or abs(camera.sensor_height_mm - float(self.sensor_h_spin.value())) > 1e-6:
            camera.set_sensor(float(self.sensor_w_spin.value()), float(self.sensor_h_spin.value()))
        if source is self.fov_spin:
            camera.set_field_of_view(float(self.fov_spin.value()))
        else:
            camera.set_focal_length(float(self.focal_spin.value()))
        camera.aperture_f_stop = float(self.aperture_spin.value())
        camera.near_clip = float(self.near_spin.value())
        camera.far_clip = float(self.far_spin.value())
        camera.resolution_width = int(self.res_w_spin.value())
        camera.resolution_height = int(self.res_h_spin.value())
        camera.aspect_ratio_width = int(self.aspect_w_spin.value())
        camera.aspect_ratio_height = int(self.aspect_h_spin.value())
        camera.show_safe_frame = self.safe_check.isChecked()
        camera.show_letterbox = self.letterbox_check.isChecked()
        camera.letterbox_ratio = float(self.letterbox_spin.value())
        camera.validate()
        camera.apply_to_original()
        self.manager._store_on_model()
        self._sync_linked_spins(camera)
        self.refresh()
        self.cameraChanged.emit()

    def _sync_linked_spins(self, camera: GhostRiggerCamera) -> None:
        self._updating = True
        self.focal_spin.setValue(float(camera.focal_length_mm))
        self.fov_spin.setValue(float(camera.field_of_view_degrees))
        self._updating = False

    def _populate_target_object_combo(self, camera: GhostRiggerCamera) -> None:
        current = str(getattr(camera, "target_object_id", "") or "")
        self.target_object_combo.blockSignals(True)
        self.target_object_combo.clear()
        self.target_object_combo.addItem("Manual Target", "")
        for object_id, label, _node in self._target_object_rows(camera):
            self.target_object_combo.addItem(label, object_id)
        index = self.target_object_combo.findData(current)
        self.target_object_combo.setCurrentIndex(index if index >= 0 else 0)
        self.target_object_combo.blockSignals(False)

    def _selected_target_object_id(self) -> str:
        return str(self.target_object_combo.currentData() or "")

    def _target_object_rows(self, camera: GhostRiggerCamera) -> list[tuple[str, str, object]]:
        model = self._model or self.manager.model
        try:
            nodes = list(model.all_nodes()) if model is not None and hasattr(model, "all_nodes") else []
        except Exception:
            nodes = []
        rows: list[tuple[str, str, object]] = []
        seen: set[str] = set()
        for node in nodes:
            object_id = str(getattr(node, "_gr_scene_object_id", "") or "")
            if not object_id or object_id in seen or object_id == camera.id:
                continue
            if bool(getattr(node, "_gr_camera_target_handle", False)):
                continue
            if not bool(getattr(node, "_gr_scene_object_root", False)):
                continue
            seen.add(object_id)
            label = str(getattr(node, "_gr_scene_object_name", "") or getattr(node, "name", "") or object_id)
            rows.append((object_id, label, node))
        rows.sort(key=lambda item: item[1].lower())
        return rows

    def _target_object_position(self, object_id: str) -> tuple[float, float, float] | None:
        target_id = str(object_id or "")
        if not target_id or self._selected is None:
            return None
        for row_id, _label, node in self._target_object_rows(self._selected):
            if row_id != target_id:
                continue
            try:
                return tuple(float(v) for v in getattr(node, "position", (0.0, 0.0, 0.0))[:3])
            except Exception:
                return None
        return None

    def _apply_lens_preset(self, label: str) -> None:
        if self._updating or label not in LENS_PRESETS:
            return
        self.focal_spin.setValue(LENS_PRESETS[label])
        self._apply_editor()

    def _apply_sensor_preset(self, label: str) -> None:
        if self._updating or label not in SENSOR_PRESETS:
            return
        w, h = SENSOR_PRESETS[label]
        self.sensor_w_spin.setValue(w)
        self.sensor_h_spin.setValue(h)
        self._apply_editor()

    def _apply_resolution_preset(self, label: str) -> None:
        if self._updating or label not in RESOLUTION_PRESETS:
            return
        w, h = RESOLUTION_PRESETS[label]
        self.res_w_spin.setValue(w)
        self.res_h_spin.setValue(h)
        self._apply_editor()

    def _apply_letterbox_preset(self, label: str) -> None:
        if self._updating or label not in LETTERBOX_PRESETS:
            return
        self.letterbox_spin.setValue(LETTERBOX_PRESETS[label])
        self._apply_editor()

    def _apply_framing_preset(self, label: str) -> None:
        if self._updating or self._selected is None or label not in FRAMING_PRESETS:
            return
        for key, value in FRAMING_PRESETS[label].items():
            setattr(self._selected, key, value)
        self._selected.apply_to_original()
        self.manager._store_on_model()
        self._load_editor(self._selected)
        self.cameraChanged.emit()

    def _emit_align_view(self, item: QtWidgets.QTreeWidgetItem) -> None:
        camera = self._camera_from_item(item)
        if camera is not None:
            self.alignViewToCameraRequested.emit(camera.id)

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self.tree.itemAt(pos)
        selected = self._context_targets_for_item(item)
        camera = selected[-1] if selected else None
        menu = QtWidgets.QMenu(self)
        menu.setObjectName("CameraPanelContextMenu")
        actions: dict[str, QtGui.QAction] = {}
        if camera is not None:
            title = menu.addAction(self._camera_icon(camera.camera_type), camera.name)
            title.setEnabled(False)
            menu.addSeparator()
            actions["active"] = self._menu_action(menu, "Set Active Camera", qt_icon_manager.I.CAMERA_CINEMATIC)
            actions["view_to"] = self._menu_action(menu, "View Through Camera", qt_icon_manager.I.CAMERAS)
            actions["align_to"] = self._menu_action(menu, "Align Camera To Current View", qt_icon_manager.I.VIEWPORT_LOCK_CAMERA)
            menu.addSeparator()
            actions["rename"] = self._menu_action(menu, "Rename Camera", qt_icon_manager.I.PROPS)
            actions["duplicate"] = self._menu_action(menu, "Duplicate Camera", qt_icon_manager.I.PROPS)
            actions["delete"] = self._menu_action(menu, "Delete Camera", qt_icon_manager.I.CLOSE)
            menu.addSeparator()
            actions["lock"] = self._menu_action(menu, "Lock Camera", qt_icon_manager.I.VIEWPORT_LOCK_CAMERA)
            actions["unlock"] = self._menu_action(menu, "Unlock Camera", qt_icon_manager.I.VIEWPORT_LOCK_CAMERA)
            actions["show"] = self._menu_action(menu, "Show Camera Helper", qt_icon_manager.I.VIEWPORT_SELECT_CAMERAS)
            actions["hide"] = self._menu_action(menu, "Hide Camera Helper", qt_icon_manager.I.VIEWPORT_SELECT_CAMERAS)
            menu.addSeparator()
        actions["from_view"] = self._menu_action(menu, "Create Camera From Current View", qt_icon_manager.I.VIEWPORT_SELECT_CAMERAS)
        actions["clear"] = self._menu_action(menu, "Clear Active Camera", qt_icon_manager.I.CAMERAS)
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is actions.get("active") and camera:
            self.activeCameraRequested.emit(camera.id)
        elif chosen is actions["clear"]:
            self.clearActiveCameraRequested.emit()
        elif chosen is actions.get("rename") and camera:
            text, ok = QtWidgets.QInputDialog.getText(self, "Rename Camera", "Name", text=camera.name)
            if ok and text.strip():
                self.manager.rename_camera(camera.id, text.strip())
                self.cameraChanged.emit()
        elif chosen is actions.get("duplicate") and camera:
            self.duplicateCameraRequested.emit(camera.id)
        elif chosen is actions.get("delete") and camera:
            self.deleteCameraRequested.emit(camera.id)
        elif chosen is actions["from_view"]:
            self.createFromViewRequested.emit()
        elif chosen is actions.get("align_to") and camera:
            self.alignCameraToViewRequested.emit(camera.id)
        elif chosen is actions.get("view_to") and camera:
            self.alignViewToCameraRequested.emit(camera.id)
        elif chosen is actions.get("lock"):
            for cam in selected:
                cam.locked = True
                cam.apply_to_original()
            self.cameraChanged.emit()
        elif chosen is actions.get("unlock"):
            for cam in selected:
                cam.locked = False
                cam.apply_to_original()
            self.cameraChanged.emit()
        elif chosen is actions.get("show"):
            for cam in selected:
                cam.visible = True
                cam.apply_to_original()
            self.cameraChanged.emit()
        elif chosen is actions.get("hide"):
            for cam in selected:
                cam.visible = False
                cam.apply_to_original()
            self.cameraChanged.emit()
        self.refresh()

    def _context_targets_for_item(self, item: QtWidgets.QTreeWidgetItem | None) -> list[GhostRiggerCamera]:
        if item is None:
            return []
        camera = self._camera_from_item(item)
        if camera is None:
            return []
        if not item.isSelected():
            self.tree.clearSelection()
            item.setSelected(True)
        self.tree.setCurrentItem(item)
        selected = self.manager.selected_cameras()
        if camera not in selected:
            self.manager.select_many([camera], active=camera)
            selected = [camera]
        return selected

    def _menu_action(self, menu: QtWidgets.QMenu, label: str, icon_name: str) -> QtGui.QAction:
        action = menu.addAction(qt_icon_manager.get(icon_name, 16), label)
        action.setToolTip(label)
        return action

    def _set_editor_enabled(self, enabled: bool) -> None:
        widgets = [
            self.name_edit, self.type_combo, self.enabled_check, self.visible_check, self.locked_check,
            *self.pos_spins, *self.rot_spins, self.target_enabled_check, self.follow_target_check,
            self.target_object_combo, *self.target_spins,
            self.focus_spin, self.lens_combo, self.focal_spin, self.fov_spin, self.sensor_combo,
            self.sensor_w_spin, self.sensor_h_spin, self.aperture_spin, self.near_spin, self.far_spin,
            self.resolution_combo, self.res_w_spin, self.res_h_spin, self.aspect_w_spin, self.aspect_h_spin,
            self.safe_check, self.letterbox_check, self.letterbox_combo, self.letterbox_spin,
            self.framing_combo, self.active_button, *self._selection_buttons,
        ]
        for widget in widgets:
            widget.setEnabled(enabled)

    def _double_spin(self, minimum: float, maximum: float, step: float, decimals: int) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.valueChanged.connect(lambda _value=0.0, source=spin: self._apply_editor(source=source))
        return spin

    def _int_spin(self, minimum: int, maximum: int, step: int) -> QtWidgets.QSpinBox:
        spin = QtWidgets.QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.valueChanged.connect(lambda _value=0, source=spin: self._apply_editor(source=source))
        return spin

    def _row(self, widgets) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        for widget in widgets:
            row.addWidget(widget)
        return row

    def _camera_action_button(self, label: str, icon_name: str, tooltip: str) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setObjectName("CameraPanelActionButton")
        button.setIcon(qt_icon_manager.get(icon_name, 18))
        button.setIconSize(QtCore.QSize(18, 18))
        button.setText(label)
        button.setProperty("_gr_full_text", label)
        button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        button.setAutoRaise(False)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setToolTip(tooltip)
        button.setMinimumWidth(74)
        button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        return button

    def _editor_button(self, label: str, icon_name: str, tooltip: str) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(label)
        button.setObjectName("CameraPanelEditorButton")
        button.setIcon(qt_icon_manager.get(icon_name, 18))
        button.setIconSize(QtCore.QSize(16, 16))
        button.setToolTip(tooltip)
        button.setProperty("compact", True)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        return button

    def _field_label(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        return label

    def _section_label(self, text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setProperty("section", True)
        self._section_labels.append(label)
        return label

    def _mark_axis_spins(self, spins: list[QtWidgets.QDoubleSpinBox], prefix: str) -> None:
        for axis, spin in zip(self._AXES, spins):
            spin.setProperty("axis", axis)
            spin.setToolTip(f"{prefix} {axis.upper()} axis")

    def _axis_widget(self, axis: str, spin: QtWidgets.QDoubleSpinBox) -> QtWidgets.QWidget:
        wrapper = QtWidgets.QWidget()
        wrapper.setObjectName("CameraPanelAxisField")
        layout = QtWidgets.QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        badge = QtWidgets.QLabel(axis.upper())
        badge.setProperty("axisBadge", True)
        badge.setProperty("axis", axis)
        badge.setFixedSize(18, 18)
        badge.setAlignment(QtCore.Qt.AlignCenter)
        badge.setToolTip(f"{axis.upper()} axis")
        strip = QtWidgets.QFrame()
        strip.setObjectName("CameraPanelAxisStrip")
        strip.setProperty("axis", axis)
        strip.setFixedWidth(3)
        strip.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
        self._axis_badges.append(badge)
        self._axis_strips.append(strip)
        layout.addWidget(badge)
        layout.addWidget(strip)
        layout.addWidget(spin, 1)
        return wrapper

    def _add_axis_row(self, layout: QtWidgets.QGridLayout, row: int, label: str, spins: list[QtWidgets.QDoubleSpinBox]) -> None:
        layout.addWidget(self._field_label(label), row, 0)
        for index, (axis, spin) in enumerate(zip(self._AXES, spins)):
            layout.addWidget(self._axis_widget(axis, spin), row, 1 + index * 2, 1, 2)

    def _camera_icon(self, camera_type: str) -> QtGui.QIcon:
        return qt_icon_manager.get(self._CAMERA_ICONS.get(camera_type, qt_icon_manager.I.CAMERAS), 16)

    def _apply_camera_theme_accents(self, theme) -> None:
        axis_text = theme.color("axis.text")
        for label in self._section_labels:
            font = label.font()
            font.setBold(True)
            label.setFont(font)
            palette = label.palette()
            palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(theme.color("text.secondary")))
            label.setPalette(palette)
        for badge in self._axis_badges:
            axis = str(badge.property("axis") or "")
            color = theme.color(f"axis.{axis}")
            badge.setStyleSheet(
                f"background-color:{color}; color:{axis_text}; border-radius:2px; font-weight:bold; padding:0px;"
            )
        for strip in self._axis_strips:
            axis = str(strip.property("axis") or "")
            strip.setStyleSheet(f"background-color:{theme.color(f'axis.{axis}')}; border:0px;")

    def _tone_item(self, item: QtWidgets.QTreeWidgetItem, camera: GhostRiggerCamera, active_id: str) -> None:
        default_brush = QtGui.QBrush()
        disabled = QtGui.QBrush(QtGui.QColor(self._theme.color("text.disabled") if self._theme is not None else "#777777"))
        active = QtGui.QBrush(QtGui.QColor(self._theme.color("viewport.helper.cameraSelected") if self._theme is not None else "#FFD658"))
        for col in range(self.tree.columnCount()):
            item.setForeground(col, disabled if (not camera.enabled or not camera.visible) else default_brush)
        if camera.id == active_id and camera.enabled and camera.visible:
            item.setForeground(1, active)
            item.setForeground(8, active)
