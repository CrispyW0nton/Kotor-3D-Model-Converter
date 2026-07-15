"""Texture-paint workflow controls for Map Studio.

Presentation only: the window/controller own target assignment and persistence,
while the viewport owns pointer gestures and the headless painter owns pixels.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.modules.map_studio_texture_paint import TexturePaintBrush


class MapStudioTexturePaintTab(QtWidgets.QWidget):
    paintEnabledChanged = QtCore.Signal(bool)
    applyRequested = QtCore.Signal()
    targetChanged = QtCore.Signal(str)
    importRequested = QtCore.Signal()
    assignRequested = QtCore.Signal(str)
    brushChanged = QtCore.Signal(object)
    brushSourceRequested = QtCore.Signal()
    brushSourceCleared = QtCore.Signal()
    makeUsedEditableRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mapStudioTexturePaintTab")
        self._color = QtGui.QColor(255, 255, 255, 255)
        self._syncing = False
        self._has_unapplied_changes = False
        self._pending_resrefs: tuple[str, ...] = ()
        self._used_materials: tuple[str, ...] = ()
        self._project = None

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QtWidgets.QLabel("Texture Paint")
        title.setObjectName("mapStudioTexturePaintTitle")
        root.addWidget(title)

        help_label = QtWidgets.QLabel(
            "Paint project-owned room diffuse textures directly on the nearest visible room face. "
            "Brush strokes use diffuse UV0; lightmaps, gameplay models, and source game textures remain untouched."
        )
        help_label.setObjectName("mapStudioTexturePaintHelpLabel")
        help_label.setWordWrap(True)
        root.addWidget(help_label)

        target_group = QtWidgets.QGroupBox("Room Diffuse Target")
        target_group.setObjectName("mapStudioTexturePaintTargetGroup")
        target_layout = QtWidgets.QVBoxLayout(target_group)
        self.target_combo = QtWidgets.QComboBox()
        self.target_combo.setObjectName("mapStudioTexturePaintTargetComboBox")
        self.target_combo.setToolTip(
            "Project-owned room diffuse TGA that receives paint and is bundled with module export."
        )
        self.target_combo.currentIndexChanged.connect(self._target_changed)
        self.target_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.target_combo.setMinimumContentsLength(8)
        self.target_combo.setMinimumWidth(0)
        target_layout.addWidget(self.target_combo)

        target_buttons = QtWidgets.QVBoxLayout()
        target_buttons.setSpacing(4)
        self.make_used_editable_button = QtWidgets.QPushButton("Clone Room Textures")
        self.make_used_editable_button.setObjectName("mapStudioTexturePaintMakeUsedEditableButton")
        self.make_used_editable_button.setToolTip(
            "Clone the diffuse textures used by loaded room geometry into project-owned TGA overrides. "
            "Placeables, creatures, doors, and lightmaps are outside this batch."
        )
        self.make_used_editable_button.clicked.connect(self.makeUsedEditableRequested.emit)
        self.import_button = QtWidgets.QPushButton("Import Texture…")
        self.import_button.setObjectName("mapStudioTexturePaintImportButton")
        self.import_button.setToolTip("Import a PNG/TGA/DDS/JPG/BMP/WEBP/TIFF as a unique project TGA.")
        self.import_button.clicked.connect(self.importRequested.emit)
        self.assign_button = QtWidgets.QPushButton("Assign to Face")
        self.assign_button.setObjectName("mapStudioTexturePaintAssignButton")
        self.assign_button.setToolTip("Assign the selected project TGA to the nearest visible room face.")
        self.assign_button.clicked.connect(lambda: self.assignRequested.emit(self.selected_texture_id()))
        for button in (self.make_used_editable_button, self.import_button, self.assign_button):
            button.setMinimumWidth(0)
            button.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        target_buttons.addWidget(self.make_used_editable_button)
        target_buttons.addWidget(self.import_button)
        target_buttons.addWidget(self.assign_button)
        target_layout.addLayout(target_buttons)
        root.addWidget(target_group)

        brush_group = QtWidgets.QGroupBox("Brush")
        brush_group.setObjectName("mapStudioTexturePaintBrushGroup")
        brush_form = QtWidgets.QFormLayout(brush_group)
        brush_form.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        brush_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)

        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.setObjectName("mapStudioTexturePaintPresetComboBox")
        for label, key in (
            ("Basic Paint", "basic"),
            ("Soft Blend", "soft"),
            ("Fine Detail", "detail"),
            ("Stamp Scatter", "scatter"),
        ):
            self.preset_combo.addItem(label, key)
        self.preset_combo.setToolTip("Choose a practical starting brush; every setting remains editable.")
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)

        self.brush_source_button = QtWidgets.QPushButton("Solid Color")
        self.brush_source_button.setObjectName("mapStudioTexturePaintBrushSourceButton")
        self.brush_source_button.setToolTip("Choose any K1/K2 or imported project texture as a brush stamp.")
        self.brush_source_button.clicked.connect(self.brushSourceRequested.emit)
        self.brush_source_clear_button = QtWidgets.QToolButton()
        self.brush_source_clear_button.setObjectName("mapStudioTexturePaintBrushSourceClearButton")
        self.brush_source_clear_button.setText("×")
        self.brush_source_clear_button.setToolTip("Return to a solid-color brush.")
        self.brush_source_clear_button.clicked.connect(self.brushSourceCleared.emit)
        source_row = QtWidgets.QWidget()
        source_layout = QtWidgets.QHBoxLayout(source_row)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(self.brush_source_button, 1)
        source_layout.addWidget(self.brush_source_clear_button)

        self.size_spin = QtWidgets.QDoubleSpinBox()
        self.size_spin.setObjectName("mapStudioTexturePaintSizeSpinBox")
        self.size_spin.setRange(1.0, 2048.0)
        self.size_spin.setValue(48.0)
        self.size_spin.setSuffix(" px")
        self.size_spin.setToolTip("Radius in authored texture pixels; viewport zoom does not change texel size.")

        self.opacity_spin = self._percent_spin("mapStudioTexturePaintOpacitySpinBox", 100)
        self.flow_spin = self._percent_spin("mapStudioTexturePaintFlowSpinBox", 100)
        self.opacity_spin.setToolTip("Maximum coverage reached by one drag, even when dabs overlap.")
        self.flow_spin.setToolTip("Paint deposited by each dab; lower values build up gradually while dragging.")
        self.hardness_spin = self._percent_spin("mapStudioTexturePaintHardnessSpinBox", 75)
        self.spacing_spin = self._percent_spin("mapStudioTexturePaintSpacingSpinBox", 20)
        self.spacing_spin.setRange(1, 400)
        self.rotation_spin = QtWidgets.QDoubleSpinBox()
        self.rotation_spin.setObjectName("mapStudioTexturePaintRotationSpinBox")
        self.rotation_spin.setRange(0.0, 359.9)
        self.rotation_spin.setSuffix("°")
        self.rotation_spin.setToolTip("Rotate a texture stamp around the brush center.")
        self.jitter_spin = self._percent_spin("mapStudioTexturePaintJitterSpinBox", 0)
        self.jitter_spin.setToolTip("Deterministic positional scatter within the brush radius.")
        self.pressure_size_box = QtWidgets.QCheckBox("Pressure → size")
        self.pressure_size_box.setObjectName("mapStudioTexturePaintPressureSizeCheckBox")
        self.pressure_size_box.setChecked(True)
        self.pressure_size_box.setToolTip("Tablet pressure scales brush size.")
        self.pressure_flow_box = QtWidgets.QCheckBox("Pressure → flow")
        self.pressure_flow_box.setObjectName("mapStudioTexturePaintPressureFlowCheckBox")
        self.pressure_flow_box.setChecked(True)
        self.pressure_flow_box.setToolTip("Tablet pressure scales paint flow.")

        self.color_button = QtWidgets.QToolButton()
        self.color_button.setObjectName("mapStudioTexturePaintColorButton")
        self.color_button.setText("Choose...")
        self.color_button.clicked.connect(self._choose_color)
        self._refresh_color_icon()

        brush_form.addRow("Preset", self.preset_combo)
        brush_form.addRow("Source", source_row)
        brush_form.addRow("Size", self.size_spin)
        brush_form.addRow("Opacity", self.opacity_spin)
        brush_form.addRow("Flow", self.flow_spin)
        brush_form.addRow("Color", self.color_button)

        self.advanced_button = QtWidgets.QToolButton()
        self.advanced_button.setObjectName("mapStudioTexturePaintAdvancedButton")
        self.advanced_button.setText("Advanced")
        self.advanced_button.setCheckable(True)
        self.advanced_button.setArrowType(QtCore.Qt.RightArrow)
        self.advanced_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        brush_form.addRow(self.advanced_button)
        self.advanced_widget = QtWidgets.QWidget()
        advanced_form = QtWidgets.QFormLayout(self.advanced_widget)
        advanced_form.setContentsMargins(0, 0, 0, 0)
        advanced_form.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        advanced_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        advanced_form.addRow("Hardness", self.hardness_spin)
        advanced_form.addRow("Spacing", self.spacing_spin)
        advanced_form.addRow("Stamp Rotation", self.rotation_spin)
        advanced_form.addRow("Jitter", self.jitter_spin)
        advanced_form.addRow(self.pressure_size_box)
        advanced_form.addRow(self.pressure_flow_box)
        self.advanced_widget.setVisible(False)
        brush_form.addRow(self.advanced_widget)
        self.advanced_button.toggled.connect(self._advanced_toggled)
        for widget in (
            self.size_spin,
            self.opacity_spin,
            self.flow_spin,
            self.hardness_spin,
            self.spacing_spin,
            self.rotation_spin,
            self.jitter_spin,
        ):
            widget.valueChanged.connect(self._emit_brush)
        self.pressure_size_box.toggled.connect(self._emit_brush)
        self.pressure_flow_box.toggled.connect(self._emit_brush)
        root.addWidget(brush_group)

        material_group = QtWidgets.QGroupBox("Room Materials")
        material_group.setObjectName("mapStudioTexturePaintMaterialsGroup")
        material_layout = QtWidgets.QVBoxLayout(material_group)
        self.material_list = QtWidgets.QListWidget()
        self.material_list.setObjectName("mapStudioTexturePaintMaterialList")
        self.material_list.setMinimumHeight(96)
        self.material_list.setMaximumHeight(160)
        self.material_list.setMinimumWidth(0)
        self.material_list.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
        self.material_list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.material_list.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.material_list.setToolTip(
            "Diffuse textures used by loaded room geometry. Click a checkmarked row to make it the paint target; "
            "open-circle rows must first be made editable."
        )
        self.material_list.itemClicked.connect(self._activate_material_row)
        self.material_list.itemActivated.connect(self._activate_material_row)
        material_layout.addWidget(self.material_list)
        root.addWidget(material_group)

        self.paint_button = QtWidgets.QPushButton("Start Painting")
        self.paint_button.setObjectName("mapStudioTexturePaintEnableButton")
        self.paint_button.setCheckable(True)
        self.paint_button.toggled.connect(self._paint_toggled)
        root.addWidget(self.paint_button)

        self.apply_button = QtWidgets.QPushButton("Apply Textures")
        self.apply_button.setObjectName("mapStudioTexturePaintApplyButton")
        self.apply_button.setToolTip(
            "Finalize every painted room diffuse texture together and make that set eligible for module export."
        )
        self.apply_button.clicked.connect(self.applyRequested.emit)
        self.apply_button.setMinimumWidth(0)
        self.apply_button.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        root.addWidget(self.apply_button)

        self.status_label = QtWidgets.QLabel(
            "Choose an editable room diffuse material, or import and assign a project texture, then start painting."
        )
        self.status_label.setObjectName("mapStudioTexturePaintStatusLabel")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        root.addStretch(1)
        self.set_project(None)

    @staticmethod
    def _percent_spin(name: str, value: int) -> QtWidgets.QSpinBox:
        spin = QtWidgets.QSpinBox()
        spin.setObjectName(name)
        spin.setRange(0, 100)
        spin.setValue(value)
        spin.setSuffix("%")
        return spin

    def selected_texture_id(self) -> str:
        return str(self.target_combo.currentData(QtCore.Qt.UserRole) or "")

    def selected_resref(self) -> str:
        return str(self.target_combo.currentData(QtCore.Qt.UserRole + 1) or "")

    def current_brush(self) -> TexturePaintBrush:
        rgba = self._color.getRgb()
        return TexturePaintBrush(
            radius_px=float(self.size_spin.value()),
            opacity=float(self.opacity_spin.value()) / 100.0,
            flow=float(self.flow_spin.value()) / 100.0,
            hardness=float(self.hardness_spin.value()) / 100.0,
            spacing=float(self.spacing_spin.value()) / 100.0,
            rotation_degrees=float(self.rotation_spin.value()),
            jitter=float(self.jitter_spin.value()) / 100.0,
            pressure_size=bool(self.pressure_size_box.isChecked()),
            pressure_flow=bool(self.pressure_flow_box.isChecked()),
            color=(int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3])),
        )

    def set_project(self, project) -> None:
        self._project = project
        selected = self.selected_texture_id()
        was_unapplied = bool(self._has_unapplied_changes)
        authored_payload = dict(
            (getattr(project, "extra_sections", {}) or {}).get("authored_module") or {}
        ) if project is not None else {}
        self._has_unapplied_changes = bool(
            authored_payload.get("texture_paint_unapplied", False)
            or authored_payload.get("texture_paint_dirty", False)
        )
        self._pending_resrefs = tuple(
            dict.fromkeys(
                str(value or "").strip().lower()
                for value in tuple(authored_payload.get("texture_paint_pending_resrefs") or ())
                if str(value or "").strip()
            )
        )
        self._syncing = True
        try:
            self.target_combo.clear()
            for texture in tuple(getattr(project, "textures", ()) or ()):
                texture_id = str(getattr(texture, "texture_id", "") or "")
                resref = str(getattr(texture, "resref", "") or "")
                path = str(getattr(texture, "path", "") or "").strip()
                # Stock/game-library texture references are valid brush
                # sources, but never writable paint targets.  Only an
                # explicit project-owned sidecar belongs in this combo.
                metadata = dict(getattr(texture, "metadata", {}) or {})
                if (
                    not texture_id
                    or not resref
                    or not path
                    or Path(path).suffix.lower() != ".tga"
                    or str(metadata.get("format") or "tga").strip().lower() != "tga"
                    or str(metadata.get("asset_kind") or "").strip().lower() == "map_studio_lightmap"
                ):
                    continue
                self.target_combo.addItem(resref)
                index = self.target_combo.count() - 1
                self.target_combo.setItemData(index, texture_id, QtCore.Qt.UserRole)
                self.target_combo.setItemData(index, resref, QtCore.Qt.UserRole + 1)
                self.target_combo.setItemData(
                    index,
                    path,
                    QtCore.Qt.ItemDataRole.ToolTipRole,
                )
            if selected:
                for index in range(self.target_combo.count()):
                    if str(self.target_combo.itemData(index, QtCore.Qt.UserRole) or "") == selected:
                        self.target_combo.setCurrentIndex(index)
                        break
        finally:
            self._syncing = False
        available = self.target_combo.count() > 0
        self.assign_button.setEnabled(available)
        self.paint_button.setEnabled(available)
        self._refresh_material_list(project)
        self._refresh_apply_button()
        if not available:
            self.paint_button.setChecked(False)
            self.status_label.setText(
                "No editable room diffuse textures yet. Make loaded room textures editable or import a unique target."
            )
        elif self._has_unapplied_changes:
            self.status_label.setText(
                "Room diffuse preview has unapplied changes. Click Apply Textures before export."
            )
        elif was_unapplied:
            self.status_label.setText("Texture changes are applied and eligible for the next module export.")

    def has_unapplied_changes(self) -> bool:
        return bool(self._has_unapplied_changes)

    def set_unapplied_changes(self, unapplied: bool, resref: str = "") -> None:
        """Refresh the apply gate without rebuilding the active paint target."""

        self._has_unapplied_changes = bool(unapplied)
        clean_resref = str(resref or "").strip().lower()
        if unapplied and clean_resref:
            self._pending_resrefs = tuple(dict.fromkeys((*self._pending_resrefs, clean_resref)))
        elif not unapplied:
            self._pending_resrefs = ()
        self._refresh_material_list(self._project)
        self._refresh_apply_button()

    def set_apply_state(self, required: bool, pending_resrefs: object = ()) -> None:
        """Refresh Apply from controller truth, including changed sidecars."""

        self._has_unapplied_changes = bool(required)
        self._pending_resrefs = tuple(
            dict.fromkeys(
                str(value or "").strip().lower()
                for value in tuple(pending_resrefs or ())
                if str(value or "").strip()
            )
        )
        self._refresh_material_list(self._project)
        self._refresh_apply_button()
        if required:
            count = len(self._pending_resrefs)
            detail = f" ({count} texture{'s' if count != 1 else ''})" if count else ""
            self.status_label.setText(
                f"Room diffuse changes{detail} need Apply Textures before export."
            )

    def set_material_inventory(self, resrefs: object, project=None) -> None:
        """Show loaded-room diffuse materials without exposing lightmaps as paint targets."""

        lightmaps = {
            str(getattr(texture, "resref", "") or "").strip().lower()
            for texture in tuple(getattr(project if project is not None else self._project, "textures", ()) or ())
            if str(dict(getattr(texture, "metadata", {}) or {}).get("asset_kind") or "").lower()
            == "map_studio_lightmap"
        }

        self._used_materials = tuple(
            dict.fromkeys(
                str(value or "").strip().lower()
                for value in tuple(resrefs or ())
                if str(value or "").strip()
                and str(value or "").strip().lower() not in {"null", *lightmaps}
            )
        )
        self._refresh_material_list(project if project is not None else self._project)

    def set_status(self, message: str) -> None:
        self.status_label.setText(str(message or ""))

    def set_brush_source(self, name: str = "") -> None:
        clean = str(name or "").strip()
        self.brush_source_button.setText(clean if clean else "Solid Color")
        self.brush_source_button.setToolTip(
            f"Texture stamp: {clean}" if clean else "Choose any K1/K2 or imported project texture as a brush stamp."
        )

    def stop_painting(self) -> None:
        self.paint_button.setChecked(False)

    def _refresh_apply_button(self) -> None:
        count = len(self._pending_resrefs)
        self.apply_button.setText(
            f"Apply Textures ({count})" if count else "Apply Textures"
        )
        self.apply_button.setEnabled(
            self.target_combo.count() > 0
            and not self.paint_button.isChecked()
        )
        self.apply_button.setToolTip(
            "Apply pending room diffuse sidecars and recheck externally changed editable textures before export."
            if self._has_unapplied_changes
            else "Recheck editable room diffuse sidecars and apply any external changes before export."
        )

    def _refresh_material_list(self, project=None) -> None:
        textures = tuple(getattr(project, "textures", ()) or ()) if project is not None else ()
        editable = {
            str(getattr(texture, "resref", "") or "").strip().lower(): texture
            for texture in textures
            if str(getattr(texture, "path", "") or "").strip()
            and Path(str(getattr(texture, "path", "") or "")).suffix.lower() == ".tga"
            and str(dict(getattr(texture, "metadata", {}) or {}).get("asset_kind") or "").lower()
            != "map_studio_lightmap"
        }
        rows = self._used_materials or tuple(editable)
        self.material_list.clear()
        for resref in rows:
            is_editable = resref in editable
            is_pending = resref in self._pending_resrefs
            state = "Painted • apply" if is_pending else "Editable" if is_editable else "Game • read-only"
            marker = "✓" if is_editable else "○"
            item = QtWidgets.QListWidgetItem(f"{marker} {resref}  —  {state}")
            item.setData(QtCore.Qt.UserRole, resref)
            item.setData(
                QtCore.Qt.UserRole + 1,
                str(getattr(editable.get(resref), "texture_id", "") or "") if is_editable else "",
            )
            item.setToolTip(
                f"Click to paint room diffuse material {resref}."
                if is_editable
                else f"{resref} is a read-only game room diffuse; use Clone Room Textures first."
            )
            self.material_list.addItem(item)
        self.make_used_editable_button.setEnabled(bool(rows) and any(row not in editable for row in rows))

    def _activate_material_row(self, item: QtWidgets.QListWidgetItem) -> None:
        """Promote an editable inventory row to the active paint target."""

        resref = str(item.data(QtCore.Qt.UserRole) or "").strip().lower()
        texture_id = str(item.data(QtCore.Qt.UserRole + 1) or "")
        if not texture_id:
            self.status_label.setText(
                f"{resref or 'This material'} is a read-only game room diffuse. "
                "Click Clone Room Textures before painting it."
            )
            return
        for index in range(self.target_combo.count()):
            if str(self.target_combo.itemData(index, QtCore.Qt.UserRole) or "") != texture_id:
                continue
            changed = index != self.target_combo.currentIndex()
            self.target_combo.setCurrentIndex(index)
            if not changed:
                self.paint_button.setChecked(False)
                self.targetChanged.emit(texture_id)
            self.status_label.setText(
                f"Room diffuse {resref} is the paint target. Start Painting, then drag over its visible room faces."
            )
            self.target_combo.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
            return
        self.status_label.setText(
            f"Room diffuse {resref} is marked editable but its project target is unavailable; refresh the project."
        )

    def _advanced_toggled(self, expanded: bool) -> None:
        self.advanced_widget.setVisible(bool(expanded))
        self.advanced_button.setArrowType(QtCore.Qt.DownArrow if expanded else QtCore.Qt.RightArrow)

    def _apply_preset(self, _index: int) -> None:
        if self._syncing:
            return
        key = str(self.preset_combo.currentData() or "basic")
        values = {
            "basic": (48.0, 100, 100, 75, 20, 0),
            "soft": (96.0, 45, 20, 15, 12, 0),
            "detail": (12.0, 100, 80, 90, 15, 0),
            "scatter": (64.0, 70, 35, 65, 35, 30),
        }[key]
        controls = (self.size_spin, self.opacity_spin, self.flow_spin, self.hardness_spin, self.spacing_spin, self.jitter_spin)
        for control, value in zip(controls, values):
            blocker = QtCore.QSignalBlocker(control)
            control.setValue(value)
            del blocker
        self._emit_brush()

    def _target_changed(self, _index: int) -> None:
        if self._syncing:
            return
        self.paint_button.setChecked(False)
        if self.selected_resref():
            self.status_label.setText(
                f"Room diffuse {self.selected_resref()} is the paint target. Start Painting when ready."
            )
        self.targetChanged.emit(self.selected_texture_id())

    def _paint_toggled(self, enabled: bool) -> None:
        self.paint_button.setText("Stop Painting" if enabled else "Start Painting")
        self.target_combo.setEnabled(not enabled)
        self.import_button.setEnabled(not enabled)
        self.assign_button.setEnabled(not enabled and self.target_combo.count() > 0)
        self._refresh_apply_button()
        if enabled:
            self.status_label.setText(
                "Painting active: drag LMB over the nearest visible room face using this diffuse material. "
                "Ctrl+Z undoes one full stroke."
            )
        self.paintEnabledChanged.emit(bool(enabled))

    def _choose_color(self) -> None:
        color = QtWidgets.QColorDialog.getColor(
            self._color,
            self,
            "Texture Paint Brush Color",
            QtWidgets.QColorDialog.ShowAlphaChannel,
        )
        if not color.isValid():
            return
        self._color = color
        self._refresh_color_icon()
        self._emit_brush()

    def _refresh_color_icon(self) -> None:
        pixmap = QtGui.QPixmap(24, 16)
        pixmap.fill(self._color)
        self.color_button.setIcon(QtGui.QIcon(pixmap))
        self.color_button.setIconSize(QtCore.QSize(24, 16))

    def _emit_brush(self, *_args) -> None:
        self.brushChanged.emit(self.current_brush())


__all__ = ["MapStudioTexturePaintTab"]
