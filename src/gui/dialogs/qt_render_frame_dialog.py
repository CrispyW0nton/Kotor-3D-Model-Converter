"""Render-still dialog for cinematic cameras."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from src.core.camera.camera_render_settings import RenderSettings


class QtRenderFrameDialog(QtWidgets.QDialog):
    renderRequested = QtCore.Signal(object, str)
    previewRequested = QtCore.Signal(object, str)

    def __init__(self, cameras=None, active_camera_id: str = "", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Render Frame")
        self.resize(430, 420)
        self._cameras = list(cameras or [])
        self._active_camera_id = str(active_camera_id or "")
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.camera_combo = QtWidgets.QComboBox()
        self.camera_combo.addItem("Active Viewport", "")
        for camera in self._cameras:
            self.camera_combo.addItem(camera.name, camera.id)
        if self._active_camera_id:
            idx = self.camera_combo.findData(self._active_camera_id)
            if idx >= 0:
                self.camera_combo.setCurrentIndex(idx)
        form.addRow("Camera", self.camera_combo)

        self.resolution_combo = QtWidgets.QComboBox()
        self.resolution_combo.addItem("Use Camera Resolution", "camera")
        self.resolution_combo.addItem("Use Viewport Resolution", "viewport")
        self.resolution_combo.addItem("Custom", "custom")
        form.addRow("Resolution", self.resolution_combo)
        self.width_spin = self._int_spin(1, 16384, 1920)
        self.height_spin = self._int_spin(1, 16384, 1080)
        res_row = QtWidgets.QHBoxLayout()
        res_row.addWidget(self.width_spin)
        res_row.addWidget(self.height_spin)
        form.addRow("Width / Height", res_row)

        self.format_combo = QtWidgets.QComboBox()
        self.format_combo.addItems(["PNG", "JPG", "TGA"])
        form.addRow("Format", self.format_combo)
        self.output_edit = QtWidgets.QLineEdit(str(Path("exports") / "renders"))
        browse = QtWidgets.QPushButton("...")
        browse.clicked.connect(self._choose_output_dir)
        out_row = QtWidgets.QHBoxLayout()
        out_row.addWidget(self.output_edit)
        out_row.addWidget(browse)
        form.addRow("Output", out_row)
        self.prefix_edit = QtWidgets.QLineEdit()
        form.addRow("Filename Prefix", self.prefix_edit)
        self.quality_spin = self._int_spin(1, 100, 95)
        form.addRow("JPG Quality", self.quality_spin)
        self.overwrite_check = QtWidgets.QCheckBox("Overwrite Existing")
        form.addRow("", self.overwrite_check)

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["Viewport Preview", "Lit", "Unlit", "Lightmap Preview", "Cinematic Preview", "Shader Complexity"])
        self.mode_combo.setCurrentText("Cinematic Preview")
        form.addRow("Render Mode", self.mode_combo)

        overlays = QtWidgets.QGroupBox("Overlays")
        overlay_grid = QtWidgets.QGridLayout(overlays)
        self.letterbox_check = QtWidgets.QCheckBox("Include Letterbox")
        self.letterbox_check.setChecked(True)
        self.safe_check = QtWidgets.QCheckBox("Include Safe Frame")
        self.guides_check = QtWidgets.QCheckBox("Include Camera Guides")
        self.grid_check = QtWidgets.QCheckBox("Include Grid")
        self.helpers_check = QtWidgets.QCheckBox("Include Helpers")
        for idx, check in enumerate((self.letterbox_check, self.safe_check, self.guides_check, self.grid_check, self.helpers_check)):
            overlay_grid.addWidget(check, idx // 2, idx % 2)

        root.addLayout(form)
        root.addWidget(overlays)
        self.status_label = QtWidgets.QLabel("")
        root.addWidget(self.status_label)
        buttons = QtWidgets.QHBoxLayout()
        preview = QtWidgets.QPushButton("Preview Render")
        preview.clicked.connect(lambda: self.previewRequested.emit(self.settings(), self.camera_id()))
        render = QtWidgets.QPushButton("Render Still")
        render.setProperty("accent", True)
        render.clicked.connect(lambda: self.renderRequested.emit(self.settings(), self.camera_id()))
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(preview)
        buttons.addWidget(render)
        buttons.addWidget(cancel)
        root.addLayout(buttons)

    def settings(self) -> RenderSettings:
        return RenderSettings(
            output_format=self.format_combo.currentText(),
            output_directory=self.output_edit.text().strip() or str(Path("exports") / "renders"),
            filename_prefix=self.prefix_edit.text().strip(),
            resolution_width=int(self.width_spin.value()),
            resolution_height=int(self.height_spin.value()),
            resolution_source=str(self.resolution_combo.currentData() or "camera"),
            render_mode=self.mode_combo.currentText(),
            include_letterbox=self.letterbox_check.isChecked(),
            include_safe_frame=self.safe_check.isChecked(),
            include_camera_guides=self.guides_check.isChecked(),
            include_grid=self.grid_check.isChecked(),
            include_helpers=self.helpers_check.isChecked(),
            jpg_quality=int(self.quality_spin.value()),
            overwrite_existing=self.overwrite_check.isChecked(),
        )

    def camera_id(self) -> str:
        return str(self.camera_combo.currentData() or "")

    def report_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _choose_output_dir(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Output Directory", self.output_edit.text())
        if path:
            self.output_edit.setText(path)

    def _int_spin(self, minimum: int, maximum: int, value: int) -> QtWidgets.QSpinBox:
        spin = QtWidgets.QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin
