"""Dockable camera explorer and properties panel."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.camera.camera_manager import CameraManager
from src.core.camera.camera_model import CAMERA_TYPES, GhostRiggerCamera
from src.core.camera.camera_presets import FRAMING_PRESETS, LENS_PRESETS, LETTERBOX_PRESETS, RESOLUTION_PRESETS, SENSOR_PRESETS


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

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.manager = CameraManager()
        self._model = None
        self._selected: GhostRiggerCamera | None = None
        self._updating = False
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(7)

        create_row = QtWidgets.QHBoxLayout()
        for label, camera_type in (
            ("Free", "Free Camera"),
            ("Target", "Target Camera"),
            ("Cine", "Cinematic Camera"),
        ):
            button = QtWidgets.QPushButton(label)
            button.setToolTip(f"Create {camera_type}")
            button.clicked.connect(lambda _checked=False, t=camera_type: self.createCameraRequested.emit(t))
            create_row.addWidget(button)
        from_view = QtWidgets.QPushButton("From View")
        from_view.clicked.connect(self.createFromViewRequested.emit)
        create_row.addWidget(from_view)
        render = QtWidgets.QPushButton("Render")
        render.clicked.connect(self.renderFrameRequested.emit)
        create_row.addWidget(render)
        root.addLayout(create_row)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(list(self._COLUMNS))
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemDoubleClicked.connect(lambda item, _col=0: self._emit_align_view(item))
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        for index, width in enumerate((64, 142, 120, 70, 64, 100, 74, 58, 58)):
            self.tree.setColumnWidth(index, width)
        root.addWidget(self.tree, 1)

        editor = QtWidgets.QGroupBox("Selected Camera")
        form = QtWidgets.QFormLayout(editor)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(5)

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
        flags.addWidget(self.enabled_check)
        flags.addWidget(self.visible_check)
        flags.addWidget(self.locked_check)
        form.addRow("Name", self.name_edit)
        form.addRow("Type", self.type_combo)
        form.addRow("", flags)

        self.pos_spins = [self._double_spin(-100000.0, 100000.0, 0.1, 3) for _ in range(3)]
        self.rot_spins = [self._double_spin(-360.0, 360.0, 1.0, 2) for _ in range(3)]
        form.addRow("Position", self._row(self.pos_spins))
        form.addRow("Rotation", self._row(self.rot_spins))
        self.target_enabled_check = QtWidgets.QCheckBox("Target Enabled")
        self.target_enabled_check.toggled.connect(lambda _state=False: self._apply_editor())
        self.target_spins = [self._double_spin(-100000.0, 100000.0, 0.1, 3) for _ in range(3)]
        form.addRow("", self.target_enabled_check)
        form.addRow("Target", self._row(self.target_spins))
        self.focus_spin = self._double_spin(0.0, 1000000.0, 1.0, 2)
        form.addRow("Focus Distance", self.focus_spin)

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
        form.addRow("Lens Preset", self.lens_combo)
        form.addRow("Focal / FOV", self._row([self.focal_spin, self.fov_spin]))
        form.addRow("Sensor Preset", self.sensor_combo)
        form.addRow("Sensor W/H", self._row([self.sensor_w_spin, self.sensor_h_spin]))
        form.addRow("Aperture", self.aperture_spin)
        form.addRow("Near / Far", self._row([self.near_spin, self.far_spin]))

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
        frame_flags.addWidget(self.safe_check)
        frame_flags.addWidget(self.letterbox_check)
        form.addRow("Resolution", self.resolution_combo)
        form.addRow("Width / Height", self._row([self.res_w_spin, self.res_h_spin]))
        form.addRow("Aspect W/H", self._row([self.aspect_w_spin, self.aspect_h_spin]))
        form.addRow("Frame Preset", self.framing_combo)
        form.addRow("", frame_flags)
        form.addRow("Letterbox", self._row([self.letterbox_combo, self.letterbox_spin]))

        action_row = QtWidgets.QHBoxLayout()
        self.active_button = QtWidgets.QPushButton("Set Active")
        self.active_button.clicked.connect(lambda: self._selected and self.activeCameraRequested.emit(self._selected.id))
        clear_active = QtWidgets.QPushButton("Perspective")
        clear_active.clicked.connect(self.clearActiveCameraRequested.emit)
        align_to_view = QtWidgets.QPushButton("Align To View")
        align_to_view.clicked.connect(lambda: self._selected and self.alignCameraToViewRequested.emit(self._selected.id))
        view_to = QtWidgets.QPushButton("View")
        view_to.clicked.connect(lambda: self._selected and self.alignViewToCameraRequested.emit(self._selected.id))
        for button in (self.active_button, clear_active, align_to_view, view_to):
            action_row.addWidget(button)
        form.addRow("", action_row)
        root.addWidget(editor)

        self._set_editor_enabled(False)

    def apply_ghost_theme(self, theme) -> None:
        self.setStyleSheet("")
        disabled = QtGui.QBrush(QtGui.QColor(theme.color("text.disabled")))
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            camera = self._camera_from_item(item)
            if camera is not None and (not camera.enabled or not camera.visible):
                for col in range(self.tree.columnCount()):
                    item.setForeground(col, disabled)

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
        for button in self.findChildren(QtWidgets.QPushButton):
            button.setMinimumHeight(max(22, layout.toolbar("viewport").height - 8))

    def set_model(self, model) -> None:
        self._model = model
        self.manager.set_model(model)
        self.refresh()

    def refresh(self) -> None:
        active_id = self.manager.active_camera_id
        self._updating = True
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
        if not camera.enabled or not camera.visible:
            muted = item.foreground(0)
            muted.setColor(QtCore.Qt.gray)
            for col in range(self.tree.columnCount()):
                item.setForeground(col, muted)
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
        for spin in self.rot_spins:
            spin.setValue(0.0)
        self.target_enabled_check.setChecked(camera.target_enabled)
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

    def _apply_editor(self) -> None:
        if self._updating or self._selected is None:
            return
        camera = self._selected
        camera.name = self.name_edit.text().strip() or camera.name
        camera.camera_type = self.type_combo.currentText()
        camera.enabled = self.enabled_check.isChecked()
        camera.visible = self.visible_check.isChecked()
        camera.locked = self.locked_check.isChecked()
        camera.position = tuple(float(spin.value()) for spin in self.pos_spins)
        camera.target_enabled = self.target_enabled_check.isChecked()
        camera.target_position = tuple(float(spin.value()) for spin in self.target_spins)
        camera.focus_distance = float(self.focus_spin.value())
        if abs(camera.sensor_width_mm - float(self.sensor_w_spin.value())) > 1e-6 or abs(camera.sensor_height_mm - float(self.sensor_h_spin.value())) > 1e-6:
            camera.set_sensor(float(self.sensor_w_spin.value()), float(self.sensor_h_spin.value()))
        if self.sender() is self.fov_spin:
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
        selected = self.manager.selected_cameras()
        active = self.manager.active_camera_id
        menu = QtWidgets.QMenu(self)
        actions = {
            "active": menu.addAction("Set Active Camera"),
            "clear": menu.addAction("Clear Active Camera"),
            "rename": menu.addAction("Rename Camera"),
            "duplicate": menu.addAction("Duplicate Camera"),
            "delete": menu.addAction("Delete Camera"),
            "from_view": menu.addAction("Create Camera From Current View"),
            "align_to": menu.addAction("Align Camera To Current View"),
            "view_to": menu.addAction("Align View To Camera"),
            "lock": menu.addAction("Lock Camera"),
            "unlock": menu.addAction("Unlock Camera"),
            "show": menu.addAction("Show Camera Helper"),
            "hide": menu.addAction("Hide Camera Helper"),
        }
        for key in ("active", "rename", "duplicate", "delete", "align_to", "view_to", "lock", "unlock", "show", "hide"):
            actions[key].setEnabled(bool(selected))
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        camera = selected[-1] if selected else None
        if chosen is actions["active"] and camera:
            self.activeCameraRequested.emit(camera.id)
        elif chosen is actions["clear"]:
            self.clearActiveCameraRequested.emit()
        elif chosen is actions["rename"] and camera:
            text, ok = QtWidgets.QInputDialog.getText(self, "Rename Camera", "Name", text=camera.name)
            if ok and text.strip():
                self.manager.rename_camera(camera.id, text.strip())
                self.cameraChanged.emit()
        elif chosen is actions["duplicate"] and camera:
            self.duplicateCameraRequested.emit(camera.id)
        elif chosen is actions["delete"] and camera:
            self.deleteCameraRequested.emit(camera.id)
        elif chosen is actions["from_view"]:
            self.createFromViewRequested.emit()
        elif chosen is actions["align_to"] and camera:
            self.alignCameraToViewRequested.emit(camera.id)
        elif chosen is actions["view_to"] and camera:
            self.alignViewToCameraRequested.emit(camera.id)
        elif chosen is actions["lock"]:
            for cam in selected:
                cam.locked = True
                cam.apply_to_original()
            self.cameraChanged.emit()
        elif chosen is actions["unlock"]:
            for cam in selected:
                cam.locked = False
                cam.apply_to_original()
            self.cameraChanged.emit()
        elif chosen is actions["show"]:
            for cam in selected:
                cam.visible = True
                cam.apply_to_original()
            self.cameraChanged.emit()
        elif chosen is actions["hide"]:
            for cam in selected:
                cam.visible = False
                cam.apply_to_original()
            self.cameraChanged.emit()
        self.refresh()

    def _set_editor_enabled(self, enabled: bool) -> None:
        widgets = [
            self.name_edit, self.type_combo, self.enabled_check, self.visible_check, self.locked_check,
            *self.pos_spins, *self.rot_spins, self.target_enabled_check, *self.target_spins,
            self.focus_spin, self.lens_combo, self.focal_spin, self.fov_spin, self.sensor_combo,
            self.sensor_w_spin, self.sensor_h_spin, self.aperture_spin, self.near_spin, self.far_spin,
            self.resolution_combo, self.res_w_spin, self.res_h_spin, self.aspect_w_spin, self.aspect_h_spin,
            self.safe_check, self.letterbox_check, self.letterbox_combo, self.letterbox_spin,
            self.framing_combo, self.active_button,
        ]
        for widget in widgets:
            widget.setEnabled(enabled)

    def _double_spin(self, minimum: float, maximum: float, step: float, decimals: int) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.valueChanged.connect(lambda _value=0.0: self._apply_editor())
        return spin

    def _int_spin(self, minimum: int, maximum: int, step: int) -> QtWidgets.QSpinBox:
        spin = QtWidgets.QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.valueChanged.connect(lambda _value=0: self._apply_editor())
        return spin

    def _row(self, widgets) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        for widget in widgets:
            row.addWidget(widget)
        return row
