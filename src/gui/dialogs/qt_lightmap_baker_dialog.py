"""Qt dialog for generated lightmap baking."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.lighting.lightmap_bake_job import LightmapBakeJob
from src.gui.lighting.lightmap_bake_settings import LightmapBakeSettings, SUPPORTED_LIGHTMAP_RESOLUTIONS
from src.gui.lighting.lightmap_bake_worker import LightmapBakeWorker
from src.gui.lighting.lightmap_baker import LightmapBaker


class QtLightmapBakerDialog(QtWidgets.QDialog):
    previewRequested = QtCore.Signal(object)
    applyRequested = QtCore.Signal(object)
    revertRequested = QtCore.Signal()

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        model: object | None = None,
        lights: list[object] | None = None,
        selected_meshes: list[object] | None = None,
        visible_meshes: list[object] | None = None,
        texture_cache: object | None = None,
        default_output_dir: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Lightmap Baker")
        self.setMinimumSize(720, 720)
        self.model = model
        self.lights = list(lights or [])
        self.selected_meshes = list(selected_meshes or [])
        self.visible_meshes = list(visible_meshes or [])
        self.texture_cache = texture_cache
        self._thread: QtCore.QThread | None = None
        self._worker: LightmapBakeWorker | None = None
        self._last_result = None
        self._default_output_dir = default_output_dir or str(Path("exports/lightmaps").resolve())
        self._build()
        self._apply_preset("standard")

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        form_root = QtWidgets.QVBoxLayout(content)
        form_root.setSpacing(8)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        target_group = QtWidgets.QGroupBox("Bake Target")
        target_layout = QtWidgets.QVBoxLayout(target_group)
        self.target_entire = QtWidgets.QRadioButton("Entire scene/module")
        self.target_selected = QtWidgets.QRadioButton("Selected meshes only")
        self.target_visible = QtWidgets.QRadioButton("Visible meshes only")
        self.target_visible.setChecked(True)
        for button in (self.target_entire, self.target_selected, self.target_visible):
            target_layout.addWidget(button)
        form_root.addWidget(target_group)

        top_grid = QtWidgets.QGridLayout()
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.addItems(["Draft", "Standard", "High", "Custom"])
        self.preset_combo.currentTextChanged.connect(lambda text: self._apply_preset(text.lower()))
        top_grid.addWidget(QtWidgets.QLabel("Quality"), 0, 0)
        top_grid.addWidget(self.preset_combo, 0, 1)
        self.res_combo = QtWidgets.QComboBox()
        for res in SUPPORTED_LIGHTMAP_RESOLUTIONS:
            self.res_combo.addItem(str(res), res)
        top_grid.addWidget(QtWidgets.QLabel("Resolution"), 0, 2)
        top_grid.addWidget(self.res_combo, 0, 3)
        self.format_combo = QtWidgets.QComboBox()
        self.format_combo.addItems(["PNG", "TGA", "JPG"])
        top_grid.addWidget(QtWidgets.QLabel("Output Format"), 1, 0)
        top_grid.addWidget(self.format_combo, 1, 1)
        self.prefix_edit = QtWidgets.QLineEdit()
        top_grid.addWidget(QtWidgets.QLabel("Filename Prefix"), 1, 2)
        top_grid.addWidget(self.prefix_edit, 1, 3)
        form_root.addLayout(top_grid)

        source_group = QtWidgets.QGroupBox("Lighting Sources")
        source_layout = QtWidgets.QGridLayout(source_group)
        self.aurora_check = self._check("Aurora lights", True)
        self.dynamic_check = self._check("Dynamic lights", True)
        self.rig_check = self._check("Generated rig lights", True)
        self.ambient_check = self._check("Ambient contribution", False)
        for idx, widget in enumerate((self.aurora_check, self.dynamic_check, self.rig_check, self.ambient_check)):
            source_layout.addWidget(widget, idx // 2, idx % 2)
        form_root.addWidget(source_group)

        component_group = QtWidgets.QGroupBox("Bake Components")
        component_layout = QtWidgets.QGridLayout(component_group)
        self.direct_check = self._check("Direct lighting", True)
        self.shadows_check = self._check("Shadows", True)
        self.ao_check = self._check("Ambient occlusion", False)
        self.diffuse_check = self._check("Diffuse contribution", True)
        self.normal_check = self._check("Normal map influence", True)
        self.specular_check = self._check("Specular approximation", False)
        self.environment_check = self._check("Environment approximation", False)
        self.indirect_check = self._check("Indirect Approximation", False)
        for idx, widget in enumerate((
            self.direct_check, self.shadows_check, self.ao_check, self.diffuse_check,
            self.normal_check, self.specular_check, self.environment_check, self.indirect_check,
        )):
            component_layout.addWidget(widget, idx // 2, idx % 2)
        form_root.addWidget(component_group)

        quality_group = QtWidgets.QGroupBox("Quality")
        quality_layout = QtWidgets.QGridLayout(quality_group)
        self.samples_spin = self._spin(1, 64, 1)
        self.shadow_samples_spin = self._spin(1, 64, 1)
        self.padding_spin = self._spin(0, 128, 8)
        self.dilation_spin = self._spin(0, 128, 8)
        self.exposure_spin = self._double_spin(0.01, 16.0, 1.0)
        self.gamma_spin = self._double_spin(0.01, 8.0, 2.2)
        labels = [
            ("Samples per texel", self.samples_spin),
            ("Shadow samples", self.shadow_samples_spin),
            ("Padding pixels", self.padding_spin),
            ("Dilation passes", self.dilation_spin),
            ("Exposure", self.exposure_spin),
            ("Gamma", self.gamma_spin),
        ]
        for idx, (label, widget) in enumerate(labels):
            quality_layout.addWidget(QtWidgets.QLabel(label), idx // 2, (idx % 2) * 2)
            quality_layout.addWidget(widget, idx // 2, (idx % 2) * 2 + 1)
        form_root.addWidget(quality_group)

        output_group = QtWidgets.QGroupBox("Output")
        output_layout = QtWidgets.QGridLayout(output_group)
        self.output_edit = QtWidgets.QLineEdit(self._default_output_dir)
        browse = QtWidgets.QPushButton("Browse...")
        browse.clicked.connect(self._browse_output)
        self.manifest_check = self._check("Generate manifest", True)
        self.preview_check = self._check("Preview after bake", True)
        self.overwrite_check = self._check("Overwrite existing", False)
        output_layout.addWidget(QtWidgets.QLabel("Output directory"), 0, 0)
        output_layout.addWidget(self.output_edit, 0, 1)
        output_layout.addWidget(browse, 0, 2)
        output_layout.addWidget(self.manifest_check, 1, 0)
        output_layout.addWidget(self.preview_check, 1, 1)
        output_layout.addWidget(self.overwrite_check, 1, 2)
        form_root.addWidget(output_group)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        root.addWidget(self.progress)
        self.current_label = QtWidgets.QLabel("Idle")
        root.addWidget(self.current_label)
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(140)
        root.addWidget(self.log)

        buttons = QtWidgets.QHBoxLayout()
        self.validate_btn = QtWidgets.QPushButton("Validate UVs")
        self.validate_btn.clicked.connect(self._validate_uvs)
        self.bake_btn = QtWidgets.QPushButton("Bake")
        self.bake_btn.setProperty("accent", True)
        self.bake_btn.clicked.connect(self._start_bake)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel_bake)
        self.preview_btn = QtWidgets.QPushButton("Preview Result")
        self.preview_btn.clicked.connect(self._preview_result)
        self.apply_btn = QtWidgets.QPushButton("Apply Baked Lightmaps to Scene")
        self.apply_btn.clicked.connect(lambda: self.applyRequested.emit(self._last_result))
        self.revert_btn = QtWidgets.QPushButton("Revert to Original Lightmaps")
        self.revert_btn.clicked.connect(self.revertRequested.emit)
        self.open_btn = QtWidgets.QPushButton("Open Output Folder")
        self.open_btn.clicked.connect(self._open_output_folder)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        for btn in (self.validate_btn, self.bake_btn, self.cancel_btn, self.preview_btn, self.apply_btn, self.revert_btn, self.open_btn, close_btn):
            buttons.addWidget(btn)
        root.addLayout(buttons)

    def _check(self, text: str, checked: bool) -> QtWidgets.QCheckBox:
        check = QtWidgets.QCheckBox(text)
        check.setChecked(checked)
        return check

    def _spin(self, minimum: int, maximum: int, value: int) -> QtWidgets.QSpinBox:
        spin = QtWidgets.QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.valueChanged.connect(lambda _value=0: self.preset_combo.setCurrentText("Custom"))
        return spin

    def _double_spin(self, minimum: float, maximum: float, value: float) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(2)
        spin.setSingleStep(0.05)
        spin.setValue(value)
        spin.valueChanged.connect(lambda _value=0.0: self.preset_combo.setCurrentText("Custom"))
        return spin

    def _apply_preset(self, preset: str) -> None:
        if preset == "custom":
            return
        settings = LightmapBakeSettings.for_quality(preset)
        self.preset_combo.blockSignals(True)
        self._set_combo_data(self.res_combo, settings.resolution)
        self.samples_spin.setValue(settings.samples_per_texel)
        self.shadow_samples_spin.setValue(settings.shadow_samples)
        self.padding_spin.setValue(settings.padding_pixels)
        self.dilation_spin.setValue(settings.dilation_passes)
        self.preset_combo.blockSignals(False)
        self.preset_combo.setCurrentText(preset.title())

    def _settings(self) -> LightmapBakeSettings:
        fmt = str(self.format_combo.currentText()).lower()
        return LightmapBakeSettings(
            resolution=int(self.res_combo.currentData()),
            output_format=fmt,
            output_directory=self.output_edit.text().strip(),
            filename_prefix=self.prefix_edit.text().strip(),
            bake_selected_only=self.target_selected.isChecked(),
            bake_visible_only=self.target_visible.isChecked(),
            include_aurora_lights=self.aurora_check.isChecked(),
            include_generated_rig_lights=self.rig_check.isChecked(),
            include_dynamic_lights=self.dynamic_check.isChecked(),
            include_ambient=self.ambient_check.isChecked(),
            include_diffuse=self.diffuse_check.isChecked(),
            include_normal_maps=self.normal_check.isChecked(),
            include_specular=self.specular_check.isChecked(),
            include_environment=self.environment_check.isChecked(),
            use_shadows=self.shadows_check.isChecked(),
            use_ambient_occlusion=self.ao_check.isChecked(),
            use_direct_lighting=self.direct_check.isChecked(),
            use_indirect_approximation=self.indirect_check.isChecked(),
            samples_per_texel=int(self.samples_spin.value()),
            shadow_samples=int(self.shadow_samples_spin.value()),
            padding_pixels=int(self.padding_spin.value()),
            dilation_passes=int(self.dilation_spin.value()),
            exposure=float(self.exposure_spin.value()),
            gamma=float(self.gamma_spin.value()),
            overwrite_existing=self.overwrite_check.isChecked(),
            generate_manifest=self.manifest_check.isChecked(),
            preview_after_bake=self.preview_check.isChecked(),
            quality_preset=str(self.preset_combo.currentText()).lower(),
        ).normalized()

    def _make_job(self) -> LightmapBakeJob:
        return LightmapBakeJob(
            model=self.model,
            lights=self.lights,
            settings=self._settings(),
            selected_meshes=self.selected_meshes,
            visible_meshes=self.visible_meshes,
            texture_cache=self.texture_cache,
        )

    def _validate_uvs(self) -> None:
        baker = LightmapBaker()
        result = baker.collect_bakeable_meshes(self._make_job())
        self.log.clear()
        if not result:
            self._log("No bakeable meshes found.")
            return
        for entry in result:
            validation = baker.uv_validator.validate_mesh_uvs(entry.node, entry.uv_channel)
            status = "BLOCKED" if validation.severity == "blocked" else "WARN" if validation.severity == "warning" or entry.warnings else "OK"
            self._log(f"{entry.name}: {status}, UV channel {entry.uv_channel}")
            for message in [*entry.warnings, *validation.warnings, *validation.errors]:
                self._log(f"  {message}")

    def _start_bake(self) -> None:
        if self._thread is not None:
            return
        settings = self._settings()
        if not settings.output_directory:
            QtWidgets.QMessageBox.warning(self, "Lightmap Baker", "Choose an output directory before baking.")
            return
        self.log.clear()
        self.progress.setValue(0)
        self.bake_btn.setEnabled(False)
        self._thread = QtCore.QThread(self)
        self._worker = LightmapBakeWorker(self._make_job())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_thread)
        self._thread.start()

    def _cancel_bake(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._log("Cancellation requested.")

    def _on_progress(self, stage: str, value: int, total: int, detail: str) -> None:
        pct = int((float(value) / max(float(total), 1.0)) * 100.0)
        self.progress.setValue(max(0, min(100, pct)))
        self.current_label.setText(f"{stage}: {detail}" if detail else stage)
        self._log(f"{stage} {value}/{total} {detail}".strip())

    def _on_finished(self, result) -> None:
        self._last_result = result
        self.bake_btn.setEnabled(True)
        if result.cancelled:
            self._log("Bake cancelled.")
        for message in result.warnings:
            self._log(f"Warning: {message}")
        for message in result.errors:
            self._log(f"Error: {message}")
        for bake in result.bakes:
            label = bake.output_path or bake.mesh_name
            self._log(f"Bake: {label}")
            for message in bake.warnings:
                self._log(f"  Warning: {message}")
            for message in bake.errors:
                self._log(f"  Error: {message}")
        if result.manifest_path:
            self._log(f"Manifest: {result.manifest_path}")
        if result.ok and self.preview_check.isChecked():
            self.previewRequested.emit(result)

    def _clear_thread(self) -> None:
        self._thread = None
        self._worker = None

    def _preview_result(self) -> None:
        if self._last_result is not None:
            self.previewRequested.emit(self._last_result)

    def _browse_output(self) -> None:
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Lightmap Output", self.output_edit.text().strip())
        if chosen:
            self.output_edit.setText(chosen)

    def _open_output_folder(self) -> None:
        path = self.output_edit.text().strip()
        if path:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))

    def _log(self, text: str) -> None:
        self.log.appendPlainText(text)

    def _set_combo_data(self, combo: QtWidgets.QComboBox, data: object) -> None:
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)
