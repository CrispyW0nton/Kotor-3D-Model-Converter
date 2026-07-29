"""Qt settings dialog for GhostRigger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.qt_lib.assets.qt_theme import C
from src.gui.libtheme import LayoutManager, ThemeManager
from src.gui.libtheme.style_tokens import VALID_BUTTON_MODES
from src.gui.libtheme.theme_editor_window import ThemeEditorWindow
from src.gui.libtheme.theme_settings import ThemeLayoutSettings
from src.core.rendering.viewport_navigation import (
    DEFAULT_VIEWPORT_NAVIGATION_PROFILE,
    VIEWPORT_NAVIGATION_PROFILES,
    normalize_viewport_navigation_profile,
)
from src.core.rendering.renderer_backend import (
    RendererBackend,
    SUPPORTED_RENDERER_BACKENDS,
    renderer_backend_label,
    supported_renderer_backend,
)
from src.core.rendering.renderer_capabilities import RendererCapabilities
from src.core.rendering.hardware_info import HardwareDiagnostics
from src.core.rendering.renderer_settings import RendererSettings
from src.gui.qt_lib.dialogs.qt_dialogs import show_viewport_navigation_reference
from src.measurement.unit_settings import MeasurementSettings
from src.measurement.unit_system import CANONICAL_UNITS, UNIT_SYMBOLS


_WGPU_BACKEND_TYPES = {
    RendererBackend.WGPU_D3D12.value: "D3D12",
    RendererBackend.PYGFX_WGPU.value: "D3D12",
}


def _wgpu_backend_type(backend_id: object) -> str:
    return _WGPU_BACKEND_TYPES.get(str(backend_id or ""), "")


class QtSettingsDialog(QtWidgets.QDialog):
    settingsSaved = QtCore.Signal(dict)
    autoDetectRequested = QtCore.Signal()

    def __init__(
        self,
        settings: Optional[dict] = None,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        theme_manager: ThemeManager | None = None,
        layout_manager: LayoutManager | None = None,
        hardware_diagnostics: dict | HardwareDiagnostics | None = None,
        renderer_capabilities: list[dict] | list[RendererCapabilities] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(False)
        self.setWindowModality(QtCore.Qt.NonModal)
        self.settings = dict(settings or {})
        self.theme_manager = theme_manager
        self.layout_manager = layout_manager
        self.theme_layout_settings = ThemeLayoutSettings.from_settings(self.settings)
        self._hardware_diagnostics = self._coerce_hardware_diagnostics(hardware_diagnostics)
        self._renderer_capabilities = self._coerce_renderer_capabilities(renderer_capabilities)
        self._renderer_caps_by_id = {caps.backend_id: caps for caps in self._renderer_capabilities}
        self._build()
        self._load_values()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        self.resize(720, 500)
        self.setMinimumSize(620, 420)

        self.settings_tabs = QtWidgets.QTabWidget()
        self.settings_tabs.setObjectName("SettingsSectionsTabs")
        root.addWidget(self.settings_tabs, 1)

        paths_page = QtWidgets.QWidget()
        paths_root = QtWidgets.QVBoxLayout(paths_page)
        paths_root.setContentsMargins(8, 8, 8, 8)
        paths_root.setSpacing(6)
        form = QtWidgets.QFormLayout()
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        self.k1_dir = QtWidgets.QLineEdit()
        self.k2_dir = QtWidgets.QLineEdit()
        self.texture_dir = QtWidgets.QLineEdit()
        self.mdlops_path = QtWidgets.QLineEdit()
        for label, edit, button_text in (
            ("KotOR 1 Directory:", self.k1_dir, "Set K1 Dir"),
            ("KotOR 2 Directory:", self.k2_dir, "Set K2 Dir"),
            ("Texture Directory:", self.texture_dir, "Browse"),
            ("MDLOps Path:", self.mdlops_path, "Browse"),
        ):
            row = QtWidgets.QHBoxLayout()
            row.addWidget(edit, 1)
            browse = QtWidgets.QPushButton(button_text)
            browse.clicked.connect(lambda _checked=False, e=edit, l=label: self._browse(e, l))
            row.addWidget(browse)
            form.addRow(label, row)
        paths_root.addLayout(form)
        path_actions = QtWidgets.QHBoxLayout()
        self.auto_detect_paths_button = QtWidgets.QPushButton("Auto-detect")
        self.auto_detect_paths_button.setToolTip("Find installed KotOR 1 and KotOR 2 directories.")
        self.auto_detect_paths_button.clicked.connect(self.autoDetectRequested.emit)
        path_actions.addStretch(1)
        path_actions.addWidget(self.auto_detect_paths_button)
        paths_root.addLayout(path_actions)
        paths_root.addStretch(1)
        self.settings_tabs.addTab(self._scroll_tab_page(paths_page), "Paths")

        general_page = QtWidgets.QWidget()
        general_root = QtWidgets.QVBoxLayout(general_page)
        general_root.setContentsMargins(8, 8, 8, 8)
        general_root.setSpacing(6)
        general_form = QtWidgets.QFormLayout()
        general_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        general_form.setHorizontalSpacing(8)
        general_form.setVerticalSpacing(6)
        self.viewport_navigation_profile = QtWidgets.QComboBox()
        for key, profile in VIEWPORT_NAVIGATION_PROFILES.items():
            self.viewport_navigation_profile.addItem(profile.label, key)
        viewport_controls_row = QtWidgets.QHBoxLayout()
        viewport_controls_row.addWidget(self.viewport_navigation_profile, 1)
        controls_help = QtWidgets.QPushButton("Controls...")
        controls_help.clicked.connect(lambda _checked=False: show_viewport_navigation_reference(self))
        viewport_controls_row.addWidget(controls_help)
        general_form.addRow("Viewport Controls:", viewport_controls_row)
        general_root.addLayout(general_form)

        self.autoscan_check = QtWidgets.QCheckBox("Scan library on startup")
        general_root.addWidget(self.autoscan_check)
        renderer_group = QtWidgets.QGroupBox("Renderer")
        renderer_form = QtWidgets.QFormLayout(renderer_group)
        renderer_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        renderer_form.setHorizontalSpacing(8)
        renderer_form.setVerticalSpacing(6)
        self.renderer_backend_combo = QtWidgets.QComboBox()
        self._renderer_capability_text: dict[str, str] = {}
        for caps in self._renderer_capabilities:
            backend = supported_renderer_backend(caps.backend_id)
            label = renderer_backend_label(backend)
            status = caps.status_text()
            self._renderer_capability_text[backend.value] = status
            self.renderer_backend_combo.addItem(f"{label} - {status}", backend.value)
        self.renderer_fallback_check = QtWidgets.QCheckBox("Allow renderer fallback")
        self.renderer_diagnostics_check = QtWidgets.QCheckBox("Show renderer diagnostics")
        self.renderer_safe_mode_check = QtWidgets.QCheckBox("Force safe mode")
        self.renderer_performance_profile_combo = QtWidgets.QComboBox()
        self.renderer_performance_profile_combo.addItem("Auto for this computer (Recommended)", "auto")
        self.renderer_performance_profile_combo.addItem("Balanced", "balanced")
        self.renderer_performance_profile_combo.addItem("Low power", "low_power")
        self.renderer_performance_profile_combo.addItem("Quality", "quality")
        self.renderer_performance_profile_combo.addItem("Custom", "custom")
        self.renderer_performance_profile_combo.setToolTip(
            "Auto detects integrated graphics and entry-level CPUs, then reduces expensive "
            "effects and upload bursts while preserving authoring features."
        )
        self.renderer_performance_profile_status = QtWidgets.QLabel()
        self.renderer_performance_profile_status.setWordWrap(True)
        self.renderer_target_fps_spin = QtWidgets.QSpinBox()
        self.renderer_target_fps_spin.setRange(15, 240)
        self.renderer_target_fps_spin.setSingleStep(5)
        self.renderer_idle_mode_combo = QtWidgets.QComboBox()
        self.renderer_idle_mode_combo.addItem("Dirty only", "dirty_only")
        self.renderer_idle_mode_combo.addItem("Continuous", "continuous")
        self.renderer_throttle_diagnostics_check = QtWidgets.QCheckBox("Throttle diagnostics")
        self.renderer_diagnostics_hz_spin = QtWidgets.QDoubleSpinBox()
        self.renderer_diagnostics_hz_spin.setRange(0.1, 30.0)
        self.renderer_diagnostics_hz_spin.setDecimals(1)
        self.renderer_diagnostics_hz_spin.setSingleStep(0.5)
        self.renderer_overlay_dirty_check = QtWidgets.QCheckBox("Dirty overlay rendering")
        self.renderer_bloom_check = QtWidgets.QCheckBox("Enable bloom glow")
        self.renderer_bloom_check.setToolTip(
            "Adds a restrained glow around genuinely bright pixels in the ModernGL viewport."
        )
        self.renderer_bloom_threshold_spin = QtWidgets.QDoubleSpinBox()
        self.renderer_bloom_threshold_spin.setRange(0.0, 2.0)
        self.renderer_bloom_threshold_spin.setDecimals(2)
        self.renderer_bloom_threshold_spin.setSingleStep(0.05)
        self.renderer_bloom_threshold_spin.setToolTip(
            "Higher values protect cyan hologram detail; lower values glow more of the image."
        )
        self.renderer_bloom_strength_spin = QtWidgets.QDoubleSpinBox()
        self.renderer_bloom_strength_spin.setRange(0.0, 1.0)
        self.renderer_bloom_strength_spin.setDecimals(2)
        self.renderer_bloom_strength_spin.setSingleStep(0.05)
        self.renderer_bloom_strength_spin.setToolTip(
            "Controls the glow accent without changing the underlying KOTOR particle colours."
        )
        self.renderer_status_label = QtWidgets.QLabel()
        self.renderer_status_label.setWordWrap(True)
        self.renderer_backend_combo.currentIndexChanged.connect(self._update_renderer_status)
        self.renderer_performance_profile_combo.currentIndexChanged.connect(
            self._update_performance_profile_status
        )
        self.renderer_bloom_check.toggled.connect(self._update_bloom_controls)
        renderer_form.addRow("Renderer:", self.renderer_backend_combo)
        renderer_form.addRow("", self.renderer_fallback_check)
        renderer_form.addRow("", self.renderer_diagnostics_check)
        renderer_form.addRow("", self.renderer_safe_mode_check)
        renderer_form.addRow("Performance:", self.renderer_performance_profile_combo)
        renderer_form.addRow("", self.renderer_performance_profile_status)
        renderer_form.addRow("Target FPS:", self.renderer_target_fps_spin)
        renderer_form.addRow("Idle Rendering:", self.renderer_idle_mode_combo)
        renderer_form.addRow("", self.renderer_throttle_diagnostics_check)
        renderer_form.addRow("Diagnostics Hz:", self.renderer_diagnostics_hz_spin)
        renderer_form.addRow("", self.renderer_overlay_dirty_check)
        renderer_form.addRow("", self.renderer_bloom_check)
        renderer_form.addRow("Bloom Threshold:", self.renderer_bloom_threshold_spin)
        renderer_form.addRow("Bloom Strength:", self.renderer_bloom_strength_spin)
        renderer_form.addRow("Status:", self.renderer_status_label)
        general_root.addWidget(renderer_group)
        general_root.addStretch(1)
        self.settings_tabs.addTab(self._scroll_tab_page(general_page), "General")

        hardware_page = QtWidgets.QWidget()
        hardware_root = QtWidgets.QVBoxLayout(hardware_page)
        hardware_root.setContentsMargins(8, 8, 8, 8)
        hardware_root.setSpacing(6)
        self.hardware_text = QtWidgets.QPlainTextEdit()
        self.hardware_text.setReadOnly(True)
        self.hardware_text.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        hardware_root.addWidget(self.hardware_text, 1)
        self.settings_tabs.addTab(self._scroll_tab_page(hardware_page), "Hardware")

        theme_layout_page = QtWidgets.QWidget()
        theme_layout_root = QtWidgets.QVBoxLayout(theme_layout_page)
        theme_layout_root.setContentsMargins(8, 8, 8, 8)
        theme_layout_root.setSpacing(6)
        self._build_theme_layout_group(theme_layout_root)
        self.settings_tabs.addTab(self._scroll_tab_page(theme_layout_page), "Theme / Layout")

        measurement_page = QtWidgets.QWidget()
        measurement_root = QtWidgets.QVBoxLayout(measurement_page)
        measurement_root.setContentsMargins(8, 8, 8, 8)
        measurement_root.setSpacing(6)
        self._build_measurement_group(measurement_root)
        self.settings_tabs.addTab(self._scroll_tab_page(measurement_page), "Measurement")

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _scroll_tab_page(self, page: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
        scroll = QtWidgets.QScrollArea()
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        page.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        scroll.setWidget(page)
        return scroll

    def _build_theme_layout_group(self, root: QtWidgets.QVBoxLayout) -> None:
        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("ThemeLayoutSettingsTabs")

        theme_page = QtWidgets.QWidget()
        theme_form = QtWidgets.QFormLayout(theme_page)
        theme_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        theme_form.setHorizontalSpacing(8)
        theme_form.setVerticalSpacing(6)
        self.theme_mode_combo = QtWidgets.QComboBox()
        self.theme_mode_combo.addItem("Manual", "manual")
        self.theme_mode_combo.addItem("Follow OS", "follow_os")
        self.theme_combo = QtWidgets.QComboBox()
        self.light_theme_combo = QtWidgets.QComboBox()
        self.dark_theme_combo = QtWidgets.QComboBox()
        self._populate_theme_combos()
        theme_form.addRow("Theme Mode:", self.theme_mode_combo)
        theme_form.addRow("Theme:", self.theme_combo)
        theme_form.addRow("OS Light Theme:", self.light_theme_combo)
        theme_form.addRow("OS Dark Theme:", self.dark_theme_combo)
        theme_buttons = QtWidgets.QGridLayout()
        theme_buttons.setHorizontalSpacing(6)
        theme_buttons.setVerticalSpacing(4)
        preview_theme = QtWidgets.QPushButton("Apply Theme")
        preview_theme.setObjectName("ApplyThemeButton")
        preview_theme.setToolTip("Apply the selected theme to the application.")
        preview_theme.clicked.connect(self._preview_theme)
        theme_editor = QtWidgets.QPushButton("Theme Editor...")
        theme_editor.clicked.connect(self._open_theme_editor)
        validate_themes = QtWidgets.QPushButton("Validate Theme Files")
        validate_themes.clicked.connect(self._show_theme_diagnostics)
        open_themes = QtWidgets.QPushButton("Open Themes Folder")
        open_themes.clicked.connect(lambda: self._open_folder(self.theme_manager.user_theme_dir if self.theme_manager else Path("config/themes/themes")))
        theme_buttons.addWidget(preview_theme, 0, 0)
        theme_buttons.addWidget(theme_editor, 0, 1)
        theme_buttons.addWidget(validate_themes, 1, 0)
        theme_buttons.addWidget(open_themes, 1, 1)
        theme_form.addRow("", theme_buttons)
        tabs.addTab(theme_page, "Theme")

        layout_page = QtWidgets.QWidget()
        layout_form = QtWidgets.QFormLayout(layout_page)
        layout_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        layout_form.setHorizontalSpacing(8)
        layout_form.setVerticalSpacing(6)
        self.layout_combo = QtWidgets.QComboBox()
        self._populate_layout_combo()
        self.button_mode_combo = QtWidgets.QComboBox()
        self.button_mode_combo.addItem("Use layout default", "")
        for mode in sorted(VALID_BUTTON_MODES):
            self.button_mode_combo.addItem(mode, mode)
        self.icon_size_spin = QtWidgets.QSpinBox()
        self.icon_size_spin.setRange(0, 96)
        self.icon_size_spin.setSpecialValueText("Layout default")
        layout_form.addRow("Layout:", self.layout_combo)
        layout_form.addRow("Button Mode Override:", self.button_mode_combo)
        layout_form.addRow("Icon Size Override:", self.icon_size_spin)
        layout_buttons = QtWidgets.QGridLayout()
        layout_buttons.setHorizontalSpacing(6)
        layout_buttons.setVerticalSpacing(4)
        preview_layout = QtWidgets.QPushButton("Apply Layout")
        preview_layout.clicked.connect(self._preview_layout)
        reset_layout = QtWidgets.QPushButton("Reset Layout")
        reset_layout.clicked.connect(self._reset_layout)
        save_custom_layout = QtWidgets.QPushButton("Save Custom")
        save_custom_layout.setToolTip("Save the current window sizes as a custom layout.")
        save_custom_layout.clicked.connect(self._save_current_layout_as_custom)
        validate_layouts = QtWidgets.QPushButton("Validate Layout Files")
        validate_layouts.clicked.connect(self._show_layout_diagnostics)
        open_layouts = QtWidgets.QPushButton("Open Layouts Folder")
        open_layouts.clicked.connect(lambda: self._open_folder(self.layout_manager.user_layout_dir if self.layout_manager else Path("config/themes/layouts")))
        layout_buttons.addWidget(preview_layout, 0, 0)
        layout_buttons.addWidget(reset_layout, 0, 1)
        layout_buttons.addWidget(save_custom_layout, 0, 2)
        layout_buttons.addWidget(validate_layouts, 1, 0)
        layout_buttons.addWidget(open_layouts, 1, 1)
        layout_form.addRow("", layout_buttons)
        tabs.addTab(layout_page, "Layout")

        advanced_page = QtWidgets.QWidget()
        advanced_root = QtWidgets.QVBoxLayout(advanced_page)
        advanced_guidance = QtWidgets.QLabel(
            "These options expose development and diagnostics features that are not needed for normal authoring."
        )
        advanced_guidance.setWordWrap(True)
        advanced_root.addWidget(advanced_guidance)
        self.developer_mode_check = QtWidgets.QCheckBox("Enable Developer Mode")
        self.developer_mode_check.setToolTip(
            "Show the Developer menu with IPC server and integration diagnostics."
        )
        advanced_root.addWidget(self.developer_mode_check)
        self.hot_reload_check = QtWidgets.QCheckBox("Hot reload theme and layout XML during development")
        self.hot_reload_check.setToolTip(
            "Reload edited theme and layout XML while GhostStudio is running."
        )
        advanced_root.addWidget(self.hot_reload_check)
        advanced_root.addStretch(1)
        tabs.addTab(advanced_page, "Advanced")
        root.addWidget(tabs, 1)

    def _populate_theme_combos(self) -> None:
        themes = self.theme_manager.available_themes() if self.theme_manager is not None else []
        if not themes:
            for combo in (self.theme_combo, self.light_theme_combo, self.dark_theme_combo):
                combo.addItem("Matrix", "matrix")
            return
        for theme in themes:
            for combo in (self.theme_combo, self.light_theme_combo, self.dark_theme_combo):
                combo.addItem(theme.name, theme.id)

    def _populate_layout_combo(self) -> None:
        layouts = self.layout_manager.available_layouts() if self.layout_manager is not None else []
        if not layouts:
            self.layout_combo.addItem("Default", "default")
            return
        for layout in layouts:
            self.layout_combo.addItem(layout.name, layout.id)

    def _build_measurement_group(self, root: QtWidgets.QVBoxLayout) -> None:
        self.measurement_group = QtWidgets.QGroupBox("Measurement")
        form = QtWidgets.QFormLayout(self.measurement_group)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        self.system_unit_combo = QtWidgets.QComboBox()
        self.display_unit_combo = QtWidgets.QComboBox()
        for combo in (self.system_unit_combo, self.display_unit_combo):
            for unit in CANONICAL_UNITS:
                combo.addItem(f"{unit} ({UNIT_SYMBOLS[unit]})", unit)
        self.distance_precision_spin = QtWidgets.QSpinBox()
        self.distance_precision_spin.setRange(0, 6)
        self.show_grid_measurements_check = QtWidgets.QCheckBox("Show grid measurements")
        self.show_dimensions_check = QtWidgets.QCheckBox("Show selected object dimensions")
        self.snap_enabled_check = QtWidgets.QCheckBox("Enable snap")
        self.angle_snap_enabled_check = QtWidgets.QCheckBox("Enable angle snap")
        self.angle_snap_increment_combo = QtWidgets.QComboBox()
        self.angle_snap_increment_combo.setEditable(True)
        self.angle_snap_increment_combo.addItems(["1°", "2.5°", "5°", "10°", "15°", "30°", "45°", "90°"])
        self.percent_snap_enabled_check = QtWidgets.QCheckBox("Enable percent snap")
        self.percent_snap_increment_combo = QtWidgets.QComboBox()
        self.percent_snap_increment_combo.setEditable(True)
        self.percent_snap_increment_combo.addItems(["1%", "2.5%", "5%", "10%", "25%", "50%", "100%"])
        form.addRow("System Unit:", self.system_unit_combo)
        form.addRow("Display Unit:", self.display_unit_combo)
        form.addRow("Distance Precision:", self.distance_precision_spin)
        form.addRow("", self.show_grid_measurements_check)
        form.addRow("", self.show_dimensions_check)
        form.addRow("", self.snap_enabled_check)
        form.addRow("", self.angle_snap_enabled_check)
        form.addRow("Angle Snap Degrees:", self.angle_snap_increment_combo)
        form.addRow("", self.percent_snap_enabled_check)
        form.addRow("Percent Snap:", self.percent_snap_increment_combo)
        root.addWidget(self.measurement_group)

    def _load_values(self) -> None:
        self.k1_dir.setText(str(self.settings.get("k1_dir", "")))
        self.k2_dir.setText(str(self.settings.get("k2_dir", "")))
        self.texture_dir.setText(str(self.settings.get("texture_dir", "")))
        self.mdlops_path.setText(str(self.settings.get("mdlops_path", "")))
        profile_key = normalize_viewport_navigation_profile(
            self.settings.get("viewport_navigation_profile", DEFAULT_VIEWPORT_NAVIGATION_PROFILE)
        )
        index = self.viewport_navigation_profile.findData(profile_key)
        self.viewport_navigation_profile.setCurrentIndex(max(index, 0))
        self.autoscan_check.setChecked(bool(self.settings.get("autoscan", False)))
        renderer_settings = RendererSettings.from_settings(self.settings)
        self._set_combo_data(self.renderer_backend_combo, renderer_settings.backend.value)
        self.renderer_fallback_check.setChecked(renderer_settings.allow_fallback)
        self.renderer_diagnostics_check.setChecked(renderer_settings.show_renderer_diagnostics)
        self.renderer_safe_mode_check.setChecked(renderer_settings.force_safe_mode)
        self._set_combo_data(
            self.renderer_performance_profile_combo,
            renderer_settings.performance_profile,
        )
        self.renderer_target_fps_spin.setValue(int(renderer_settings.target_fps))
        self._set_combo_data(self.renderer_idle_mode_combo, renderer_settings.idle_render_mode)
        self.renderer_throttle_diagnostics_check.setChecked(renderer_settings.throttle_diagnostics)
        self.renderer_diagnostics_hz_spin.setValue(float(renderer_settings.diagnostics_hz))
        self.renderer_overlay_dirty_check.setChecked(renderer_settings.overlay_dirty_rendering)
        self.renderer_bloom_check.setChecked(renderer_settings.bloom_enabled)
        self.renderer_bloom_threshold_spin.setValue(float(renderer_settings.bloom_threshold))
        self.renderer_bloom_strength_spin.setValue(float(renderer_settings.bloom_strength))
        self._update_bloom_controls()
        self._update_performance_profile_status()
        self._update_renderer_status()
        self._load_cached_hardware_text()
        self._set_combo_data(self.theme_mode_combo, self.theme_layout_settings.theme_mode)
        self._set_combo_data(self.theme_combo, self.theme_layout_settings.selected_theme)
        self._set_combo_data(self.light_theme_combo, self.theme_layout_settings.os_light_theme)
        self._set_combo_data(self.dark_theme_combo, self.theme_layout_settings.os_dark_theme)
        self._set_combo_data(self.layout_combo, self.theme_layout_settings.selected_layout)
        self._set_combo_data(self.button_mode_combo, self.theme_layout_settings.button_mode_override)
        self.icon_size_spin.setValue(int(self.theme_layout_settings.icon_size_override or 0))
        self.developer_mode_check.setChecked(bool(self.settings.get("developer_mode", False)))
        self.hot_reload_check.setChecked(bool(self.theme_layout_settings.hot_reload_enabled))
        measurement = MeasurementSettings.from_dict(self.settings.get("measurement", {}))
        for combo, unit in (
            (self.system_unit_combo, measurement.system_unit),
            (self.display_unit_combo, measurement.display_unit),
        ):
            index = combo.findData(unit)
            combo.setCurrentIndex(max(index, 0))
        self.distance_precision_spin.setValue(measurement.distance_precision)
        self.show_grid_measurements_check.setChecked(measurement.show_grid_measurements)
        self.show_dimensions_check.setChecked(measurement.show_selected_object_dimensions)
        self.snap_enabled_check.setChecked(measurement.snap_enabled)
        self.angle_snap_enabled_check.setChecked(measurement.angle_snap_enabled)
        self.angle_snap_increment_combo.setCurrentText(f"{measurement.angle_snap_increment_degrees:g}°")
        self.percent_snap_enabled_check.setChecked(measurement.percent_snap_enabled)
        self.percent_snap_increment_combo.setCurrentText(f"{measurement.percent_snap_increment_percent:g}%")

    def _load_cached_hardware_text(self) -> None:
        if self._hardware_diagnostics is None:
            self.hardware_text.setPlainText(
                "Hardware diagnostics were not captured during startup.\n"
                "Restart GhostRigger to refresh the pre-start hardware snapshot."
            )
            return
        self.hardware_text.setPlainText("\n".join(self._hardware_diagnostics.lines()))

    @staticmethod
    def _coerce_hardware_diagnostics(value: dict | HardwareDiagnostics | None) -> HardwareDiagnostics | None:
        if isinstance(value, HardwareDiagnostics):
            return value
        if isinstance(value, dict) and value:
            return HardwareDiagnostics.from_dict(value)
        return None

    @staticmethod
    def _coerce_renderer_capabilities(
        value: list[dict] | list[RendererCapabilities] | None,
    ) -> list[RendererCapabilities]:
        if value:
            caps_by_backend: dict[RendererBackend, RendererCapabilities] = {}
            for entry in value:
                if isinstance(entry, RendererCapabilities):
                    caps = entry
                elif isinstance(entry, dict):
                    caps = RendererCapabilities.from_dict(entry)
                else:
                    continue
                try:
                    backend = RendererBackend(caps.backend_id)
                except ValueError:
                    backend = supported_renderer_backend(caps.backend_id)
                if backend in SUPPORTED_RENDERER_BACKENDS and backend not in caps_by_backend:
                    caps_by_backend[backend] = RendererCapabilities(
                        **{**caps.to_dict(), "backend_id": backend.value, "name": renderer_backend_label(backend)}
                    )
            if caps_by_backend:
                for backend in SUPPORTED_RENDERER_BACKENDS:
                    caps_by_backend.setdefault(
                        backend,
                        RendererCapabilities(
                            backend_id=backend.value,
                            name=renderer_backend_label(backend),
                            available=True,
                            reason="Cached renderer availability was not captured during startup",
                            supports_hot_switch=True,
                        ),
                    )
                return [caps_by_backend[backend] for backend in SUPPORTED_RENDERER_BACKENDS]
        return [
            RendererCapabilities(
                backend_id=backend.value,
                name=renderer_backend_label(backend),
                available=True,
                reason="Cached renderer availability was not captured during startup",
                supports_hot_switch=True,
            )
            for backend in SUPPORTED_RENDERER_BACKENDS
        ]

    def values(self) -> dict:
        measurement = MeasurementSettings.from_dict(
            {
                "system_unit": self.system_unit_combo.currentData(),
                "display_unit": self.display_unit_combo.currentData(),
                "distance_precision": self.distance_precision_spin.value(),
                "show_grid_measurements": self.show_grid_measurements_check.isChecked(),
                "show_selected_object_dimensions": self.show_dimensions_check.isChecked(),
                "snap_enabled": self.snap_enabled_check.isChecked(),
                "angle_snap_enabled": self.angle_snap_enabled_check.isChecked(),
                "angle_snap_increment_degrees": self._angle_snap_increment_value(),
                "percent_snap_enabled": self.percent_snap_enabled_check.isChecked(),
                "percent_snap_increment_percent": self._percent_snap_increment_value(),
            }
        )
        current_renderer = RendererSettings.from_settings(self.settings)
        return {
            **self.settings,
            "k1_dir": self.k1_dir.text().strip(),
            "k2_dir": self.k2_dir.text().strip(),
            "texture_dir": self.texture_dir.text().strip(),
            "mdlops_path": self.mdlops_path.text().strip(),
            "viewport_navigation_profile": self.viewport_navigation_profile.currentData(),
            "autoscan": self.autoscan_check.isChecked(),
            "developer_mode": self.developer_mode_check.isChecked(),
            "renderer": {
                "backend": self.renderer_backend_combo.currentData(),
                "preferred_windows_backend": RendererBackend.WGPU_D3D12.value,
                "allow_fallback": self.renderer_fallback_check.isChecked(),
                "show_renderer_diagnostics": self.renderer_diagnostics_check.isChecked(),
                "force_safe_mode": self.renderer_safe_mode_check.isChecked(),
                "performance_profile": self.renderer_performance_profile_combo.currentData(),
                "target_fps": self.renderer_target_fps_spin.value(),
                "idle_render_mode": self.renderer_idle_mode_combo.currentData(),
                "throttle_diagnostics": self.renderer_throttle_diagnostics_check.isChecked(),
                "diagnostics_hz": self.renderer_diagnostics_hz_spin.value(),
                "overlay_dirty_rendering": self.renderer_overlay_dirty_check.isChecked(),
                "bloom_enabled": self.renderer_bloom_check.isChecked(),
                "bloom_threshold": self.renderer_bloom_threshold_spin.value(),
                "bloom_strength": self.renderer_bloom_strength_spin.value(),
                "wgpu": {
                    "enable_batching": current_renderer.wgpu_enable_batching,
                    "enable_instancing": current_renderer.wgpu_enable_instancing,
                    "enable_frustum_culling": current_renderer.wgpu_enable_frustum_culling,
                    "enable_lazy_upload": current_renderer.wgpu_enable_lazy_upload,
                    "enable_texture_arrays": current_renderer.wgpu_enable_texture_arrays,
                    "enable_texture_atlas": current_renderer.wgpu_enable_texture_atlas,
                    "pick_on_demand_only": current_renderer.wgpu_pick_on_demand_only,
                    "cache_render_queue": current_renderer.wgpu_cache_render_queue,
                    "cache_draw_items": current_renderer.wgpu_cache_draw_items,
                    "profile_cpu_frames": current_renderer.wgpu_profile_frames,
                    "profile_gpu_frames": current_renderer.wgpu_profile_gpu_frames,
                    "dynamic_quality": current_renderer.wgpu_dynamic_quality,
                    "max_texture_memory_mb": current_renderer.wgpu_max_texture_memory_mb,
                    "max_uploads_per_frame": current_renderer.wgpu_max_uploads_per_frame,
                },
            },
            "theme_layout": {
                "theme_mode": self.theme_mode_combo.currentData(),
                "selected_theme": self.theme_combo.currentData(),
                "os_light_theme": self.light_theme_combo.currentData(),
                "os_dark_theme": self.dark_theme_combo.currentData(),
                "selected_layout": self.layout_combo.currentData(),
                "button_mode_override": self.button_mode_combo.currentData() or "",
                "icon_size_override": self.icon_size_spin.value(),
                "density_override": self.theme_layout_settings.density_override,
                "hot_reload_enabled": self.hot_reload_check.isChecked(),
                "last_known_os_theme": self.theme_layout_settings.last_known_os_theme,
                "last_theme_editor_section": self.theme_layout_settings.last_theme_editor_section,
                "user_theme_dir": self.theme_layout_settings.user_theme_dir,
                "user_layout_dir": self.theme_layout_settings.user_layout_dir,
                "panel_sizes": dict(self.theme_layout_settings.panel_sizes),
                "splitter_sizes": dict(self.theme_layout_settings.splitter_sizes),
            },
            "measurement": measurement.to_dict(),
        }

    def set_game_dirs(self, k1_dir: str, k2_dir: str) -> None:
        self.k1_dir.setText(k1_dir)
        self.k2_dir.setText(k2_dir)

    @staticmethod
    def _set_combo_data(combo: QtWidgets.QComboBox, value: object) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(max(index, 0))

    def _update_renderer_status(self) -> None:
        backend_id = str(self.renderer_backend_combo.currentData() or RendererBackend.MODERNGL_GL330.value)
        self._update_bloom_controls()
        status = self._renderer_capability_text.get(backend_id, "Available")
        current_settings = RendererSettings.from_settings(self.settings)
        candidate = self.values()
        candidate.setdefault("renderer", {})
        candidate["renderer"]["backend"] = backend_id
        restart_needed = self._renderer_restart_required(current_settings, RendererSettings.from_settings(candidate))
        if restart_needed:
            suffix = " Restart required to apply this WGPU backend."
        else:
            suffix = " Restart may be required for a real backend switch."
        self.renderer_status_label.setText(f"{status}.{suffix}")

    def _update_bloom_controls(self, *_args) -> None:
        modern_gl = str(self.renderer_backend_combo.currentData() or "") == RendererBackend.MODERNGL_GL330.value
        custom_profile = str(self.renderer_performance_profile_combo.currentData() or "auto") == "custom"
        self.renderer_bloom_check.setEnabled(modern_gl and custom_profile)
        enabled = modern_gl and custom_profile and self.renderer_bloom_check.isChecked()
        self.renderer_bloom_threshold_spin.setEnabled(enabled)
        self.renderer_bloom_strength_spin.setEnabled(enabled)

    def _update_performance_profile_status(self, *_args) -> None:
        requested = str(self.renderer_performance_profile_combo.currentData() or "auto")
        custom_profile = requested == "custom"
        self.renderer_target_fps_spin.setEnabled(custom_profile)
        self.renderer_diagnostics_hz_spin.setEnabled(custom_profile)
        self._update_bloom_controls()
        probe = {
            **self.settings,
            "renderer": {
                **dict(self.settings.get("renderer") or {}),
                "performance_profile": requested,
            },
        }
        effective = RendererSettings.from_settings(
            probe,
            hardware=(
                self._hardware_diagnostics.to_dict()
                if self._hardware_diagnostics is not None
                else None
            ),
        ).effective_performance_profile
        descriptions = {
            "low_power": "45 FPS cap, bloom disabled, smaller texture/upload budgets.",
            "balanced": "Standard visual quality with dirty-only idle rendering.",
            "quality": "At least 60 FPS, bloom enabled, and larger GPU budgets.",
            "custom": "Uses the detailed renderer controls below without profile overrides.",
        }
        prefix = f"Auto selected {effective.replace('_', ' ')}. " if requested == "auto" else ""
        suffix = "" if custom_profile else " Choose Custom to edit FPS and effects."
        self.renderer_performance_profile_status.setText(
            prefix + descriptions.get(effective, descriptions["balanced"]) + suffix
        )

    def _renderer_restart_required(self, old_settings: RendererSettings, new_settings: RendererSettings) -> bool:
        old_type = _wgpu_backend_type(old_settings.backend.value)
        new_type = _wgpu_backend_type(new_settings.backend.value)
        return bool(old_type and new_type and old_type != new_type)

    def _preview_theme(self) -> None:
        if self.theme_manager is None:
            return
        self.setUpdatesEnabled(False)
        try:
            if self.theme_mode_combo.currentData() == "follow_os":
                self.theme_manager.settings.os_light_theme = str(self.light_theme_combo.currentData() or "default_light")
                self.theme_manager.settings.os_dark_theme = str(self.dark_theme_combo.currentData() or "default_dark")
                self.theme_manager.set_follow_os(True, target=self)
            else:
                self.theme_manager.select_theme(str(self.theme_combo.currentData() or "default"), target=self)
            values = self.values()
            self.theme_layout_settings = ThemeLayoutSettings.from_settings(values)
            self.settingsSaved.emit(values)
        finally:
            QtCore.QTimer.singleShot(0, self._restore_after_theme_apply)
            QtCore.QTimer.singleShot(90, self._restore_after_theme_apply)

    def _restore_after_theme_apply(self) -> None:
        if not self.isVisible():
            self.show()
        self.setUpdatesEnabled(True)
        self.updateGeometry()
        self.update()
        self.repaint()
        self.raise_()
        self.activateWindow()

    def _open_theme_editor(self) -> None:
        if self.theme_manager is None or self.layout_manager is None:
            return
        editor = getattr(self, "_theme_editor_window", None)
        if editor is None:
            editor = ThemeEditorWindow(
                self.theme_manager,
                self.layout_manager,
                self.parentWidget(),
                matrix_bar_settings=dict(self.settings.get("matrix_bar", {})),
                matrix_background_enabled=bool(self.settings.get("matrix_background", True)),
            )
            self._theme_editor_window = editor
        editor.show()
        editor.raise_()
        editor.activateWindow()

    def _preview_layout(self) -> None:
        if self.layout_manager is None or not isinstance(self.parentWidget(), QtWidgets.QMainWindow):
            return
        self.layout_manager.set_button_override(
            str(self.button_mode_combo.currentData() or ""),
            self.icon_size_spin.value(),
        )
        self.layout_manager.select_layout(str(self.layout_combo.currentData() or "default"), window=self.parentWidget())

    def _reset_layout(self) -> None:
        if self.layout_manager is not None and isinstance(self.parentWidget(), QtWidgets.QMainWindow):
            self.layout_manager.reset_layout(self.parentWidget())

    def _save_current_layout_as_custom(self) -> None:
        if self.layout_manager is None:
            return
        parent = self.parentWidget()
        layout = self.layout_manager.get_layout(str(self.layout_combo.currentData() or "default"))
        custom_id = f"{layout.id}_custom"
        path = self.layout_manager.user_layout_dir / f"{custom_id}.xml"
        path.parent.mkdir(parents=True, exist_ok=True)
        main_width = parent.width() if isinstance(parent, QtWidgets.QWidget) else layout.main_width
        main_height = parent.height() if isinstance(parent, QtWidgets.QWidget) else layout.main_height
        main_sizes = parent.main_splitter.sizes() if hasattr(parent, "main_splitter") else []
        bottom_sizes = parent.vertical_splitter.sizes() if hasattr(parent, "vertical_splitter") else []
        library_width = main_sizes[0] if len(main_sizes) > 0 else layout.panel("library").preferred_width
        viewport_width = main_sizes[1] if len(main_sizes) > 1 else layout.viewport.preferred_width
        properties_width = main_sizes[2] if len(main_sizes) > 2 else layout.panel("properties").preferred_width
        output_height = bottom_sizes[1] if len(bottom_sizes) > 1 else layout.panel("outputLog").preferred_height
        text = f'''<layout id="{custom_id}" name="{layout.name} Custom" version="1">
    <mainWindow width="{main_width}" height="{main_height}" maximized="false"/>
    <toolbars>
        <toolbar id="main" visible="true" buttonMode="{self.button_mode_combo.currentData() or layout.toolbar("main").button_mode}" iconSize="{self.icon_size_spin.value() or layout.toolbar("main").icon_size}" height="{layout.toolbar("main").height}"/>
        <toolbar id="viewport" visible="true" buttonMode="{layout.viewport.toolbar_button_mode}" iconSize="{layout.toolbar("viewport").icon_size}" height="{layout.toolbar("viewport").height}"/>
    </toolbars>
    <panels>
        <panel id="library" region="left" visible="true" minWidth="{layout.panel("library").min_width}" preferredWidth="{library_width}"/>
        <panel id="properties" region="right" visible="true" minWidth="{layout.panel("properties").min_width}" preferredWidth="{properties_width}"/>
        <panel id="meshTools" region="farRight" visible="{str(layout.panel("meshTools").visible).lower()}" minWidth="{layout.panel("meshTools").min_width}" preferredWidth="{layout.panel("meshTools").preferred_width}"/>
        <panel id="outputLog" region="bottom" visible="true" minHeight="{layout.panel("outputLog").min_height}" preferredHeight="{output_height}"/>
        <panel id="pythonTerminal" region="bottom" visible="true" minHeight="{layout.panel("pythonTerminal").min_height}" preferredHeight="{output_height}"/>
    </panels>
    <viewport>
        <region id="mainViewport" minWidth="{layout.viewport.min_width}" preferredWidth="{viewport_width}"/>
        <toolbar visible="{str(layout.viewport.toolbar_visible).lower()}" buttonMode="{layout.viewport.toolbar_button_mode}" compact="{str(layout.viewport.toolbar_compact).lower()}"/>
    </viewport>
    <spacing>
        <margin value="{layout.spacing_value("margin", 4)}"/>
        <panelSpacing value="{layout.spacing_value("panelSpacing", 4)}"/>
        <toolbarSpacing value="{layout.spacing_value("toolbarSpacing", 2)}"/>
        <splitterHandleWidth value="{layout.spacing_value("splitterHandleWidth", 6)}"/>
    </spacing>
</layout>
'''
        path.write_text(text, encoding="utf-8")
        self.layout_manager.reload()
        self.layout_combo.clear()
        self._populate_layout_combo()
        self._set_combo_data(self.layout_combo, custom_id)
        QtWidgets.QMessageBox.information(self, "Layout Saved", f"Saved custom layout:\n{path}")

    def _show_theme_diagnostics(self) -> None:
        if self.theme_manager is not None:
            self.theme_manager.reload()
            lines = self.theme_manager.diagnostics or ["All packaged theme files are valid."]
        else:
            lines = ["Theme manager is not available."]
        QtWidgets.QMessageBox.information(self, "Theme Validation", "\n".join(lines[:60]))

    def _show_layout_diagnostics(self) -> None:
        if self.layout_manager is not None:
            self.layout_manager.reload()
            lines = self.layout_manager.diagnostics or ["All packaged layout files are valid."]
        else:
            lines = ["Layout manager is not available."]
        QtWidgets.QMessageBox.information(self, "Layout Validation", "\n".join(lines[:60]))

    def _open_folder(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def _angle_snap_increment_value(self) -> float:
        try:
            return float(str(self.angle_snap_increment_combo.currentText()).replace("deg", "").replace("°", "").strip())
        except ValueError:
            return 15.0

    def _percent_snap_increment_value(self) -> float:
        try:
            return float(str(self.percent_snap_increment_combo.currentText()).replace("%", "").strip())
        except ValueError:
            return 10.0

    def _browse(self, edit: QtWidgets.QLineEdit, label: str) -> None:
        if "Path" in label:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, label)
        else:
            path = QtWidgets.QFileDialog.getExistingDirectory(self, label)
        if path:
            edit.setText(path)

    def _save(self) -> None:
        values = self.values()
        old_settings = RendererSettings.from_settings(self.settings)
        new_settings = RendererSettings.from_settings(values)
        restart_after_save = False
        if self._renderer_restart_required(old_settings, new_settings):
            old_label = renderer_backend_label(old_settings.backend)
            new_label = renderer_backend_label(new_settings.backend)
            QtWidgets.QMessageBox.information(
                self,
                "Restart Required",
                (
                    "GhostRigger must be restarted before this renderer change can be enabled.\n\n"
                    f"Current renderer: {old_label}\n"
                    f"Selected renderer: {new_label}\n\n"
                    "WGPU_BACKEND_TYPE is read before the first WGPU device is created, "
                    "so switching WGPU D3D12, Vulkan, or OpenGL backends cannot be applied live. "
                    "The setting will be saved and GhostRigger will restart now."
                ),
            )
            restart_after_save = True
        if restart_after_save:
            values["__restart_after_save"] = True
        self.settingsSaved.emit(values)
        self.accept()


def load_settings(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_settings(path: Path, values: dict) -> None:
    path.write_text(json.dumps(values, indent=2), encoding="utf-8")
