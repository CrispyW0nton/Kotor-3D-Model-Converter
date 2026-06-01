"""Qt dialog for generated lightmap baking."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.lighting.lightmap_bake_job import LightmapBakeJob
from src.core.lighting.lightmap_bake_settings import LightmapBakeSettings, SUPPORTED_LIGHTMAP_RESOLUTIONS
from src.gui.lighting.lightmap_bake_worker import LightmapBakeWorker, LightmapPreviewBakeWorker
from src.gui.lighting.lightmap_baker import LightmapBaker
from src.gui.qt_lib.dialogs.lightmap_preview_window import LightmapPreviewWindow
from src.gui.qt_lib.dialogs.uv_geometry_preview_window import UVGeometryPreviewWindow
from src.gui.qt_lib.dialogs.uv_preview_window import UVPreviewWindow


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
        self._preview_thread: QtCore.QThread | None = None
        self._preview_worker: LightmapPreviewBakeWorker | None = None
        self._preview_timer = QtCore.QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(450)
        self._preview_timer.timeout.connect(self._start_preview_bake)
        self._preview_window: LightmapPreviewWindow | None = None
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

        mesh_group = QtWidgets.QGroupBox("Selected Mesh UVs")
        mesh_layout = QtWidgets.QGridLayout(mesh_group)
        self.selected_mesh_label = QtWidgets.QLabel(self._selected_mesh_name())
        self.uv_combo = QtWidgets.QComboBox()
        self.uv_combo.currentIndexChanged.connect(lambda _index=0: self._on_uv_changed())
        self.uv_status = QtWidgets.QLabel("")
        self.preview_uv_btn = QtWidgets.QPushButton("Preview UVs")
        self.preview_uv_btn.clicked.connect(self._open_uv_preview)
        self.preview_geo_btn = QtWidgets.QPushButton("Preview Geometry in UVs")
        self.preview_geo_btn.clicked.connect(self._open_uv_geometry_preview)
        self.generate_uv_btn = QtWidgets.QPushButton("Generate Lightmap UVs")
        self.generate_uv_btn.clicked.connect(self._generate_lightmap_uvs)
        mesh_layout.addWidget(QtWidgets.QLabel("Mesh"), 0, 0)
        mesh_layout.addWidget(self.selected_mesh_label, 0, 1, 1, 3)
        mesh_layout.addWidget(QtWidgets.QLabel("Lightmap UV"), 1, 0)
        mesh_layout.addWidget(self.uv_combo, 1, 1)
        mesh_layout.addWidget(self.preview_uv_btn, 1, 2)
        mesh_layout.addWidget(self.preview_geo_btn, 1, 3)
        mesh_layout.addWidget(self.uv_status, 2, 0, 1, 3)
        mesh_layout.addWidget(self.generate_uv_btn, 2, 3)
        form_root.addWidget(mesh_group)

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
        self.gpu_check = self._check("GPU acceleration", True)
        self.gpu_check.setToolTip("Uses an offscreen ModernGL shader for direct lighting. Shadows still use CPU rays.")
        self.shadows_check = self._check("Shadows", False)
        self.shadows_check.setToolTip("Optional CPU shadow rays. Leave off for the GPU direct-light bake path.")
        self.ao_check = self._check("Ambient occlusion", False)
        self.diffuse_check = self._check("Diffuse contribution", True)
        self.normal_check = self._check("Normal map influence", True)
        self.specular_check = self._check("Specular approximation", False)
        self.environment_check = self._check("Environment approximation", False)
        self.indirect_check = self._check("Indirect Approximation", False)
        for idx, widget in enumerate((
            self.direct_check, self.gpu_check, self.shadows_check, self.ao_check, self.diffuse_check,
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
        self.ambient_strength_spin = self._double_spin(0.0, 4.0, 1.0)
        self.diffuse_strength_spin = self._double_spin(0.0, 4.0, 1.0)
        self.indirect_strength_spin = self._double_spin(0.0, 4.0, 1.0)
        self.shadow_strength_spin = self._double_spin(0.0, 1.0, 1.0)
        self.normal_bias_spin = self._double_spin(0.0, 0.1, 0.002)
        self.normal_bias_spin.setDecimals(4)
        self.falloff_spin = self._double_spin(0.01, 10.0, 1.0)
        self.ambient_strength_control = self._slider_control(self.ambient_strength_spin, 100)
        self.diffuse_strength_control = self._slider_control(self.diffuse_strength_spin, 100)
        self.indirect_strength_control = self._slider_control(self.indirect_strength_spin, 100)
        self.shadow_strength_control = self._slider_control(self.shadow_strength_spin, 100)
        self.falloff_control = self._slider_control(self.falloff_spin, 100)
        labels = [
            ("Samples per texel", self.samples_spin),
            ("Shadow samples", self.shadow_samples_spin),
            ("Padding pixels", self.padding_spin),
            ("Dilation passes", self.dilation_spin),
            ("Exposure", self.exposure_spin),
            ("Gamma", self.gamma_spin),
            ("Ambient strength", self.ambient_strength_control),
            ("Diffuse strength", self.diffuse_strength_control),
            ("Indirect strength", self.indirect_strength_control),
            ("Shadow strength", self.shadow_strength_control),
            ("Normal bias", self.normal_bias_spin),
            ("Light falloff", self.falloff_control),
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
        self.live_preview_check = self._check("Live Preview", False)
        self.compare_original_check = self._check("Compare Original", False)
        self.overwrite_check = self._check("Overwrite existing", False)
        output_layout.addWidget(QtWidgets.QLabel("Output directory"), 0, 0)
        output_layout.addWidget(self.output_edit, 0, 1)
        output_layout.addWidget(browse, 0, 2)
        output_layout.addWidget(self.manifest_check, 1, 0)
        output_layout.addWidget(self.preview_check, 1, 1)
        output_layout.addWidget(self.overwrite_check, 1, 2)
        output_layout.addWidget(self.live_preview_check, 2, 0)
        output_layout.addWidget(self.compare_original_check, 2, 1)
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
        self.bake_preview_btn = QtWidgets.QPushButton("Bake Preview")
        self.bake_preview_btn.clicked.connect(self._start_preview_bake)
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
        for btn in (self.validate_btn, self.bake_preview_btn, self.bake_btn, self.cancel_btn, self.preview_btn, self.apply_btn, self.revert_btn, self.open_btn, close_btn):
            buttons.addWidget(btn)
        root.addLayout(buttons)
        for widget in (
            self.res_combo,
            self.ambient_strength_spin,
            self.diffuse_strength_spin,
            self.indirect_strength_spin,
            self.shadow_strength_spin,
            self.normal_bias_spin,
            self.falloff_spin,
        ):
            signal = widget.currentIndexChanged if isinstance(widget, QtWidgets.QComboBox) else widget.valueChanged
            signal.connect(lambda *_args: self._schedule_live_preview())
        self._refresh_uv_channels()

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

    def _slider_control(self, spin: QtWidgets.QDoubleSpinBox, scale: int) -> QtWidgets.QWidget:
        box = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(int(spin.minimum() * scale), int(spin.maximum() * scale))
        slider.setValue(int(spin.value() * scale))
        slider.valueChanged.connect(lambda value: spin.setValue(float(value) / float(scale)))
        spin.valueChanged.connect(lambda value: slider.setValue(int(float(value) * scale)))
        row.addWidget(slider, 1)
        row.addWidget(spin)
        return box

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
            bake_resolution=int(self.res_combo.currentData()),
            selected_uv_channel=int(self.uv_combo.currentData() if self.uv_combo.count() else 1),
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
            use_gpu_acceleration=self.gpu_check.isChecked(),
            use_shadows=self.shadows_check.isChecked(),
            use_ambient_occlusion=self.ao_check.isChecked(),
            use_direct_lighting=self.direct_check.isChecked(),
            use_indirect_approximation=self.indirect_check.isChecked(),
            samples_per_texel=int(self.samples_spin.value()),
            ambient_strength=float(self.ambient_strength_spin.value()),
            diffuse_strength=float(self.diffuse_strength_spin.value()),
            indirect_strength=float(self.indirect_strength_spin.value()),
            shadow_strength=float(self.shadow_strength_spin.value()),
            normal_bias=float(self.normal_bias_spin.value()),
            light_falloff_multiplier=float(self.falloff_spin.value()),
            use_aurora_lights=self.aurora_check.isChecked(),
            use_original_lightmap_as_reference=self.compare_original_check.isChecked(),
            preview_resolution=128,
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

    def _selected_mesh(self) -> object | None:
        if self.selected_meshes:
            return self.selected_meshes[0]
        if self.visible_meshes:
            return self.visible_meshes[0]
        return None

    def _selected_mesh_name(self) -> str:
        mesh = self._selected_mesh()
        if mesh is None:
            return "No mesh selected"
        return str(getattr(mesh, "name", "mesh") or "mesh")

    def _refresh_uv_channels(self) -> None:
        mesh = self._selected_mesh()
        self.uv_combo.blockSignals(True)
        self.uv_combo.clear()
        if mesh is None:
            self.uv_combo.addItem("UV2 (missing)", 1)
            self.uv_status.setText("No mesh selected.")
            self.uv_combo.blockSignals(False)
            return
        baker = LightmapBaker()
        infos = baker.uv_validator.inspect_mesh_uv_channels(mesh, 3)
        for info in infos:
            label = f"{info.display_name} - {'OK' if info.has_uvs else 'missing'}"
            if info.recommended_for_lightmap:
                label += " (recommended)"
            self.uv_combo.addItem(label, info.channel_index)
        preferred = 1 if any(info.channel_index == 1 and info.has_uvs for info in infos) else 0
        idx = self.uv_combo.findData(preferred)
        if idx >= 0:
            self.uv_combo.setCurrentIndex(idx)
        self.uv_combo.blockSignals(False)
        self._update_uv_status()

    def _update_uv_status(self) -> None:
        mesh = self._selected_mesh()
        if mesh is None:
            self.uv_status.setText("No mesh selected.")
            return
        channel = int(self.uv_combo.currentData() if self.uv_combo.count() else 1)
        info = LightmapBaker().uv_validator.inspect_mesh_uv_channels(mesh, max_channels=channel + 1)[channel]
        notes = "; ".join(info.notes[:2])
        state = "safe for baking" if info.recommended_for_lightmap else "review before baking"
        if not info.has_uvs:
            state = "missing"
        self.uv_status.setText(f"{info.display_name}: {state}, coverage {info.coverage_ratio:.1%}. {notes}".strip())

    def _on_uv_changed(self) -> None:
        self._update_uv_status()
        self._schedule_live_preview()

    def _open_uv_preview(self) -> None:
        mesh = self._selected_mesh()
        if mesh is None:
            QtWidgets.QMessageBox.information(self, "UV Preview", "Select a mesh before previewing UVs.")
            return
        win = UVPreviewWindow(mesh, self, channel=int(self.uv_combo.currentData()))
        win.show()

    def _open_uv_geometry_preview(self) -> None:
        mesh = self._selected_mesh()
        if mesh is None:
            QtWidgets.QMessageBox.information(self, "Geometry in UVs", "Select a mesh before previewing UV geometry.")
            return
        win = UVGeometryPreviewWindow(mesh, self, channel=int(self.uv_combo.currentData()))
        win.show()

    def _generate_lightmap_uvs(self) -> None:
        mesh = self._selected_mesh()
        if mesh is None:
            QtWidgets.QMessageBox.information(self, "Lightmap UVs", "Select a mesh before generating lightmap UVs.")
            return
        channel = 1
        baker = LightmapBaker()
        existing = bool(baker.uv_validator._uvs(mesh, channel))
        replace = False
        if existing:
            choice = QtWidgets.QMessageBox.question(
                self,
                "Generate Lightmap UVs",
                "UV2 already exists. Replace UV2?\nChoose No to create UV3 instead.",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.No,
            )
            if choice == QtWidgets.QMessageBox.Cancel:
                return
            replace = choice == QtWidgets.QMessageBox.Yes
            if not replace:
                channel = baker.uv_generator.choose_free_channel(mesh, preferred=2)
        result = baker.generate_lightmap_uvs(mesh, target_channel=channel, replace_existing=replace, settings=self._settings())
        for message in [*result.messages, *result.warnings, *result.errors]:
            self._log(message)
        if result.success:
            self._refresh_uv_channels()
            self._set_combo_data(self.uv_combo, result.channel_index)
            self._schedule_live_preview()

    def _schedule_live_preview(self) -> None:
        if self.live_preview_check.isChecked():
            self._preview_timer.start()

    def _start_preview_bake(self) -> None:
        mesh = self._selected_mesh()
        if mesh is None:
            self._log("No mesh selected for preview.")
            return
        if self._preview_worker is not None:
            self._preview_worker.cancel()
        if self._preview_thread is not None:
            self._preview_thread.quit()
            self._preview_thread.wait(100)
        self._preview_thread = QtCore.QThread(self)
        self._preview_worker = LightmapPreviewBakeWorker(mesh, self.lights, self._settings())
        self._preview_worker.moveToThread(self._preview_thread)
        self._preview_thread.started.connect(self._preview_worker.run)
        self._preview_worker.finished.connect(self._on_preview_finished)
        self._preview_worker.finished.connect(self._preview_thread.quit)
        self._preview_worker.finished.connect(self._preview_worker.deleteLater)
        self._preview_thread.finished.connect(self._preview_thread.deleteLater)
        self._preview_thread.finished.connect(self._clear_preview_thread)
        self._preview_thread.start()

    def _on_preview_finished(self, result) -> None:
        for message in getattr(result, "messages", []):
            self._log(f"Preview: {message}")
        for message in getattr(result, "warnings", []):
            self._log(f"Preview warning: {message}")
        for message in getattr(result, "errors", []):
            self._log(f"Preview error: {message}")
        if getattr(result, "preview_image", None) is not None:
            if self._preview_window is None:
                self._preview_window = LightmapPreviewWindow(self._selected_mesh(), self, texture_cache=self.texture_cache)
            self._preview_window.set_preview_image(result.preview_image)
            self._preview_window.show()

    def _clear_preview_thread(self) -> None:
        self._preview_thread = None
        self._preview_worker = None

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
        if self._preview_worker is not None:
            self._preview_worker.cancel()
            self._log("Preview cancellation requested.")

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
        for message in getattr(result, "messages", []):
            self._log(f"Info: {message}")
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
