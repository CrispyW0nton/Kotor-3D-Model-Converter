"""Texture-paint workflow controls for Map Studio.

Presentation only: the window/controller own target assignment and persistence,
while the viewport owns pointer gestures and the headless painter owns pixels.
"""

from __future__ import annotations

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

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mapStudioTexturePaintTab")
        self._color = QtGui.QColor(255, 255, 255, 255)
        self._syncing = False
        self._has_unapplied_changes = False

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QtWidgets.QLabel("Texture Paint")
        title.setObjectName("mapStudioTexturePaintTitle")
        root.addWidget(title)

        help_label = QtWidgets.QLabel(
            "Paint a unique project texture directly on the nearest visible face. "
            "Brush strokes use diffuse UV0; lightmap UVs and source game textures remain untouched."
        )
        help_label.setObjectName("mapStudioTexturePaintHelpLabel")
        help_label.setWordWrap(True)
        root.addWidget(help_label)

        target_group = QtWidgets.QGroupBox("Target")
        target_group.setObjectName("mapStudioTexturePaintTargetGroup")
        target_layout = QtWidgets.QVBoxLayout(target_group)
        self.target_combo = QtWidgets.QComboBox()
        self.target_combo.setObjectName("mapStudioTexturePaintTargetComboBox")
        self.target_combo.setToolTip("Unique project TGA that receives paint and is bundled with module export.")
        self.target_combo.currentIndexChanged.connect(self._target_changed)
        target_layout.addWidget(self.target_combo)

        target_buttons = QtWidgets.QHBoxLayout()
        self.import_button = QtWidgets.QPushButton("Import...")
        self.import_button.setObjectName("mapStudioTexturePaintImportButton")
        self.import_button.setToolTip("Import a PNG/TGA/DDS/JPG/BMP/WEBP/TIFF as a unique project TGA.")
        self.import_button.clicked.connect(self.importRequested.emit)
        self.assign_button = QtWidgets.QPushButton("Assign to Hovered Face")
        self.assign_button.setObjectName("mapStudioTexturePaintAssignButton")
        self.assign_button.setToolTip("Assign the selected unique texture to the nearest visible Multi-Component face.")
        self.assign_button.clicked.connect(lambda: self.assignRequested.emit(self.selected_texture_id()))
        target_buttons.addWidget(self.import_button)
        target_buttons.addWidget(self.assign_button)
        target_layout.addLayout(target_buttons)
        root.addWidget(target_group)

        brush_group = QtWidgets.QGroupBox("Brush")
        brush_group.setObjectName("mapStudioTexturePaintBrushGroup")
        brush_form = QtWidgets.QFormLayout(brush_group)

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
        self.hardness_spin = self._percent_spin("mapStudioTexturePaintHardnessSpinBox", 75)
        self.spacing_spin = self._percent_spin("mapStudioTexturePaintSpacingSpinBox", 20)
        self.spacing_spin.setRange(1, 400)

        self.color_button = QtWidgets.QToolButton()
        self.color_button.setObjectName("mapStudioTexturePaintColorButton")
        self.color_button.setText("Choose...")
        self.color_button.clicked.connect(self._choose_color)
        self._refresh_color_icon()

        brush_form.addRow("Source", source_row)
        brush_form.addRow("Size", self.size_spin)
        brush_form.addRow("Opacity", self.opacity_spin)
        brush_form.addRow("Flow", self.flow_spin)
        brush_form.addRow("Hardness", self.hardness_spin)
        brush_form.addRow("Spacing", self.spacing_spin)
        brush_form.addRow("Color", self.color_button)
        for widget in (
            self.size_spin,
            self.opacity_spin,
            self.flow_spin,
            self.hardness_spin,
            self.spacing_spin,
        ):
            widget.valueChanged.connect(self._emit_brush)
        root.addWidget(brush_group)

        layer_group = QtWidgets.QGroupBox("Layers")
        layer_group.setObjectName("mapStudioTexturePaintLayersGroup")
        layer_layout = QtWidgets.QVBoxLayout(layer_group)
        self.layer_list = QtWidgets.QListWidget()
        self.layer_list.setObjectName("mapStudioTexturePaintLayerList")
        layer = QtWidgets.QListWidgetItem("Paint Layer 1")
        layer.setToolTip("One undoable stroke transaction at a time; flattened to the unique TGA on commit.")
        self.layer_list.addItem(layer)
        self.layer_list.setCurrentRow(0)
        layer_layout.addWidget(self.layer_list)
        root.addWidget(layer_group)

        self.paint_button = QtWidgets.QPushButton("Start Painting")
        self.paint_button.setObjectName("mapStudioTexturePaintEnableButton")
        self.paint_button.setCheckable(True)
        self.paint_button.toggled.connect(self._paint_toggled)
        root.addWidget(self.paint_button)

        self.apply_button = QtWidgets.QPushButton("Apply Texture Changes")
        self.apply_button.setObjectName("mapStudioTexturePaintApplyButton")
        self.apply_button.setToolTip(
            "Finalize the current live-painted project texture sidecars and make them eligible for module export."
        )
        self.apply_button.clicked.connect(self.applyRequested.emit)
        root.addWidget(self.apply_button)

        self.status_label = QtWidgets.QLabel(
            "Import or choose a project texture, assign it to a visible face, then start painting."
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
            color=(int(rgba[0]), int(rgba[1]), int(rgba[2]), int(rgba[3])),
        )

    def set_project(self, project) -> None:
        selected = self.selected_texture_id()
        was_unapplied = bool(self._has_unapplied_changes)
        authored_payload = dict(
            (getattr(project, "extra_sections", {}) or {}).get("authored_module") or {}
        ) if project is not None else {}
        self._has_unapplied_changes = bool(
            authored_payload.get("texture_paint_unapplied", False)
            or authored_payload.get("texture_paint_dirty", False)
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
                if not texture_id or not resref or not path:
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
        self._refresh_apply_button()
        if not available:
            self.paint_button.setChecked(False)
            self.status_label.setText("No project textures yet. Click Import to create a unique paint target.")
        elif self._has_unapplied_changes:
            self.status_label.setText(
                "Live preview has unapplied texture changes. Click Apply Texture Changes before export."
            )
        elif was_unapplied:
            self.status_label.setText("Texture changes are applied and eligible for the next module export.")

    def has_unapplied_changes(self) -> bool:
        return bool(self._has_unapplied_changes)

    def set_unapplied_changes(self, unapplied: bool) -> None:
        """Refresh the apply gate without rebuilding the active paint target."""

        self._has_unapplied_changes = bool(unapplied)
        self._refresh_apply_button()

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
        self.apply_button.setEnabled(
            bool(self._has_unapplied_changes)
            and self.target_combo.count() > 0
            and not self.paint_button.isChecked()
        )

    def _target_changed(self, _index: int) -> None:
        if self._syncing:
            return
        self.paint_button.setChecked(False)
        self.targetChanged.emit(self.selected_texture_id())

    def _paint_toggled(self, enabled: bool) -> None:
        self.paint_button.setText("Stop Painting" if enabled else "Start Painting")
        self.target_combo.setEnabled(not enabled)
        self.import_button.setEnabled(not enabled)
        self.assign_button.setEnabled(not enabled and self.target_combo.count() > 0)
        self._refresh_apply_button()
        if enabled:
            self.status_label.setText(
                "Painting active: drag LMB over the nearest visible face. Ctrl+Z undoes one full stroke."
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
