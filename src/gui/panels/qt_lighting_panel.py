"""Dockable lighting controls for the Qt viewport."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets


class QtLightingPanel(QtWidgets.QWidget):
    lightingModeChanged = QtCore.Signal(str)
    mapToggled = QtCore.Signal(str, bool)
    lightmapSettingsChanged = QtCore.Signal(float, str)
    lightChanged = QtCore.Signal()
    lightSelected = QtCore.Signal(object)

    _TYPE_LABELS = ("Point", "Spot", "Directional", "Area")
    _TYPE_VALUES = ("point", "spot", "directional", "area")

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._model = None
        self._lights: list[object] = []
        self._selected = None
        self._updating = False
        self._icons = {
            "point": self._icon("#ffe36b", "point"),
            "spot": self._icon("#7bdcff", "spot"),
            "directional": self._icon("#96ff8f", "directional"),
            "area": self._icon("#ff9f7b", "area"),
        }
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        top = QtWidgets.QHBoxLayout()
        top.setSpacing(6)
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("Scene Lit", "scene")
        self.mode_combo.addItem("Unlit", "unlit")
        self.mode_combo.addItem("Studio", "studio")
        self.mode_combo.setToolTip("Viewport lighting mode")
        self.mode_combo.currentIndexChanged.connect(lambda _index=0: self._emit_mode())
        top.addWidget(self.mode_combo, 1)
        root.addLayout(top)

        maps = QtWidgets.QGroupBox("Maps")
        maps_layout = QtWidgets.QGridLayout(maps)
        maps_layout.setContentsMargins(8, 8, 8, 8)
        maps_layout.setHorizontalSpacing(10)
        maps_layout.setVerticalSpacing(4)
        self.map_checks: dict[str, QtWidgets.QCheckBox] = {}
        for idx, (key, label) in enumerate((
            ("diffuse", "Diffuse"),
            ("lightmap", "Lightmap"),
            ("environment", "Environment"),
            ("specular", "Specular"),
            ("normal", "Normal"),
        )):
            check = QtWidgets.QCheckBox(label)
            check.setChecked(True)
            check.toggled.connect(lambda state, k=key: self.mapToggled.emit(k, bool(state)))
            self.map_checks[key] = check
            maps_layout.addWidget(check, idx // 2, idx % 2)
        maps_layout.addWidget(QtWidgets.QLabel("LM Intensity"), 3, 0)
        self.lightmap_intensity_spin = QtWidgets.QDoubleSpinBox()
        self.lightmap_intensity_spin.setRange(0.0, 4.0)
        self.lightmap_intensity_spin.setDecimals(2)
        self.lightmap_intensity_spin.setSingleStep(0.05)
        self.lightmap_intensity_spin.setValue(0.55)
        self.lightmap_intensity_spin.setToolTip("Blend strength for baked lightmaps")
        self.lightmap_intensity_spin.valueChanged.connect(lambda _value=0.0: self._emit_lightmap_settings())
        maps_layout.addWidget(self.lightmap_intensity_spin, 3, 1)
        maps_layout.addWidget(QtWidgets.QLabel("LM Mode"), 4, 0)
        self.lightmap_mode_combo = QtWidgets.QComboBox()
        self.lightmap_mode_combo.addItem("Baked", "baked")
        self.lightmap_mode_combo.addItem("Phong", "phong")
        self.lightmap_mode_combo.addItem("Emissive", "emissive")
        self.lightmap_mode_combo.setToolTip("How lightmaps contribute to module materials")
        self.lightmap_mode_combo.currentIndexChanged.connect(lambda _index=0: self._emit_lightmap_settings())
        maps_layout.addWidget(self.lightmap_mode_combo, 4, 1)
        root.addWidget(maps)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["", "Name", "Type", "Radius"])
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree.setIconSize(QtCore.QSize(16, 16))
        self.tree.itemSelectionChanged.connect(self._on_tree_selection)
        self.tree.setMinimumHeight(160)
        self.tree.setColumnWidth(0, 26)
        self.tree.setColumnWidth(1, 150)
        root.addWidget(self.tree, 1)

        editor = QtWidgets.QGroupBox("Selected Light")
        form = QtWidgets.QFormLayout(editor)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(6)
        self.enabled_check = QtWidgets.QCheckBox("Enabled")
        self.enabled_check.toggled.connect(lambda _state=False: self._apply_editor())
        form.addRow("", self.enabled_check)
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(self._TYPE_LABELS)
        self.type_combo.currentIndexChanged.connect(lambda _index=0: self._apply_editor())
        form.addRow("Type", self.type_combo)
        self.radius_spin = QtWidgets.QDoubleSpinBox()
        self.radius_spin.setRange(0.01, 500.0)
        self.radius_spin.setDecimals(2)
        self.radius_spin.setSingleStep(0.25)
        self.radius_spin.valueChanged.connect(lambda _value=0.0: self._apply_editor())
        form.addRow("Radius", self.radius_spin)
        self.intensity_spin = QtWidgets.QDoubleSpinBox()
        self.intensity_spin.setRange(0.0, 25.0)
        self.intensity_spin.setDecimals(2)
        self.intensity_spin.setSingleStep(0.1)
        self.intensity_spin.valueChanged.connect(lambda _value=0.0: self._apply_editor())
        form.addRow("Intensity", self.intensity_spin)
        self.cone_spin = QtWidgets.QDoubleSpinBox()
        self.cone_spin.setRange(1.0, 179.0)
        self.cone_spin.setDecimals(1)
        self.cone_spin.setSingleStep(1.0)
        self.cone_spin.valueChanged.connect(lambda _value=0.0: self._apply_editor())
        form.addRow("Cone", self.cone_spin)
        self.area_spin = QtWidgets.QDoubleSpinBox()
        self.area_spin.setRange(0.0, 25.0)
        self.area_spin.setDecimals(2)
        self.area_spin.setSingleStep(0.1)
        self.area_spin.valueChanged.connect(lambda _value=0.0: self._apply_editor())
        form.addRow("Area", self.area_spin)
        self.ambient_check = QtWidgets.QCheckBox("Ambient only")
        self.ambient_check.toggled.connect(lambda _state=False: self._apply_editor())
        form.addRow("", self.ambient_check)
        root.addWidget(editor)

        self.setStyleSheet(
            "QGroupBox { color:#d7dde6; border:1px solid #26362e; margin-top:8px; padding-top:7px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:6px; padding:0 4px; }"
            "QTreeWidget, QComboBox, QDoubleSpinBox { background:#101713; color:#e8f0ec; border:1px solid #26362e; }"
            "QTreeWidget::item:selected { background:#284f3d; color:#ffffff; }"
            "QCheckBox { color:#d7dde6; }"
        )
        self._set_editor_enabled(False)

    def _icon(self, color: str, kind: str) -> QtGui.QIcon:
        pix = QtGui.QPixmap(16, 16)
        pix.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtGui.QPen(QtGui.QColor(color), 1.5))
        painter.setBrush(QtGui.QColor(color))
        if kind == "directional":
            painter.drawLine(3, 12, 12, 3)
            painter.drawLine(12, 3, 12, 8)
            painter.drawLine(12, 3, 7, 3)
        elif kind == "spot":
            painter.drawEllipse(3, 3, 5, 5)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawLine(6, 8, 2, 14)
            painter.drawLine(6, 8, 14, 14)
        elif kind == "area":
            painter.drawRect(3, 3, 10, 10)
        else:
            painter.drawEllipse(4, 4, 8, 8)
        painter.end()
        return QtGui.QIcon(pix)

    def set_model(self, model) -> None:
        self._model = model
        self._lights = [
            node for node in (model.all_nodes() if model is not None and hasattr(model, "all_nodes") else [])
            if bool(getattr(node, "is_light", False))
        ]
        self.refresh()

    def refresh(self) -> None:
        previous = self._selected
        self._updating = True
        self.tree.clear()
        selected_item = None
        for node in self._lights:
            kind = str(getattr(node, "light_kind", "point") or "point").lower()
            item = QtWidgets.QTreeWidgetItem([
                "",
                str(getattr(node, "name", "") or "AuroraLight"),
                kind.title(),
                f"{float(getattr(node, 'light_radius', 0.0) or 0.0):.2f}",
            ])
            item.setIcon(0, self._icons.get(kind, self._icons["point"]))
            item.setData(0, QtCore.Qt.UserRole, node)
            if not bool(getattr(node, "light_enabled", True)):
                item.setForeground(1, QtGui.QBrush(QtGui.QColor("#7a8790")))
            self.tree.addTopLevelItem(item)
            if node is previous:
                selected_item = item
        self._updating = False
        if selected_item is not None:
            self.tree.setCurrentItem(selected_item)
            self._load_editor(previous)
        elif self._lights and previous is None:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        else:
            self._selected = None
            self._set_editor_enabled(False)

    def _set_editor_enabled(self, enabled: bool) -> None:
        for widget in (
            self.enabled_check, self.type_combo, self.radius_spin,
            self.intensity_spin, self.cone_spin, self.area_spin,
            self.ambient_check,
        ):
            widget.setEnabled(enabled)

    def select_light(self, node) -> None:
        if node is not None and not bool(getattr(node, "is_light", False)):
            return
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item.data(0, QtCore.Qt.UserRole) is node:
                was_updating = self._updating
                self._updating = True
                self.tree.setCurrentItem(item)
                self._selected = node
                self._load_editor(node)
                self._updating = was_updating
                return
        if node is None:
            was_updating = self._updating
            self._updating = True
            self._selected = None
            self.tree.clearSelection()
            self._load_editor(None)
            self._updating = was_updating

    def _on_tree_selection(self) -> None:
        if self._updating:
            return
        items = self.tree.selectedItems()
        node = items[0].data(0, QtCore.Qt.UserRole) if items else None
        self._selected = node
        self._load_editor(node)
        self.lightSelected.emit(node)

    def _load_editor(self, node) -> None:
        self._updating = True
        self._set_editor_enabled(node is not None)
        if node is not None:
            kind = str(getattr(node, "light_kind", "point") or "point").lower()
            self.enabled_check.setChecked(bool(getattr(node, "light_enabled", True)))
            self.type_combo.setCurrentIndex(max(0, self._TYPE_VALUES.index(kind) if kind in self._TYPE_VALUES else 0))
            self.radius_spin.setValue(float(getattr(node, "light_radius", 5.0) or 5.0))
            self.intensity_spin.setValue(float(getattr(node, "light_multiplier", 1.0) or 1.0))
            self.cone_spin.setValue(float(getattr(node, "light_cone_degrees", 45.0) or 45.0))
            self.area_spin.setValue(float(getattr(node, "light_area_size", 1.0) or 1.0))
            self.ambient_check.setChecked(bool(getattr(node, "light_ambient_only", False)))
        self._updating = False

    def _apply_editor(self) -> None:
        if self._updating or self._selected is None:
            return
        node = self._selected
        node.light_enabled = self.enabled_check.isChecked()
        node.light_kind = self._TYPE_VALUES[self.type_combo.currentIndex()]
        node.light_radius = float(self.radius_spin.value())
        node.light_multiplier = float(self.intensity_spin.value())
        node.light_cone_degrees = float(self.cone_spin.value())
        node.light_area_size = float(self.area_spin.value())
        node.light_ambient_only = bool(self.ambient_check.isChecked())
        self.refresh()
        self.lightChanged.emit()

    def _emit_mode(self) -> None:
        self.lightingModeChanged.emit(str(self.mode_combo.currentData() or "scene"))

    def _emit_lightmap_settings(self) -> None:
        self.lightmapSettingsChanged.emit(
            float(self.lightmap_intensity_spin.value()),
            str(self.lightmap_mode_combo.currentData() or "baked"),
        )
