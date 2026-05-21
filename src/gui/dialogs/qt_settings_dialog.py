"""Qt settings dialog for GhostRigger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.qt_lib.assets.qt_theme import C
from src.gui.libtheme import LayoutManager, ThemeManager
from src.gui.libtheme.style_tokens import VALID_BUTTON_MODES
from src.gui.libtheme.theme_settings import ThemeLayoutSettings
from src.gui.qt_lib.rendering.viewport_navigation import (
    DEFAULT_VIEWPORT_NAVIGATION_PROFILE,
    VIEWPORT_NAVIGATION_PROFILES,
    normalize_viewport_navigation_profile,
)
from src.gui.qt_lib.dialogs.qt_dialogs import show_viewport_navigation_reference
from src.measurement.unit_settings import MeasurementSettings
from src.measurement.unit_system import CANONICAL_UNITS, UNIT_SYMBOLS


class QtSettingsDialog(QtWidgets.QDialog):
    settingsSaved = QtCore.Signal(dict)

    def __init__(
        self,
        settings: Optional[dict] = None,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        theme_manager: ThemeManager | None = None,
        layout_manager: LayoutManager | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = dict(settings or {})
        self.theme_manager = theme_manager
        self.layout_manager = layout_manager
        self.theme_layout_settings = ThemeLayoutSettings.from_settings(self.settings)
        self._build()
        self._load_values()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.k1_dir = QtWidgets.QLineEdit()
        self.k2_dir = QtWidgets.QLineEdit()
        self.texture_dir = QtWidgets.QLineEdit()
        self.mdlops_path = QtWidgets.QLineEdit()
        self.viewport_navigation_profile = QtWidgets.QComboBox()
        for key, profile in VIEWPORT_NAVIGATION_PROFILES.items():
            self.viewport_navigation_profile.addItem(profile.label, key)
        for label, edit in (
            ("KotOR 1 Directory:", self.k1_dir),
            ("KotOR 2 Directory:", self.k2_dir),
            ("Texture Directory:", self.texture_dir),
            ("MDLOps Path:", self.mdlops_path),
        ):
            row = QtWidgets.QHBoxLayout()
            row.addWidget(edit, 1)
            browse = QtWidgets.QPushButton("Browse")
            browse.clicked.connect(lambda _checked=False, e=edit, l=label: self._browse(e, l))
            row.addWidget(browse)
            form.addRow(label, row)
        viewport_controls_row = QtWidgets.QHBoxLayout()
        viewport_controls_row.addWidget(self.viewport_navigation_profile, 1)
        controls_help = QtWidgets.QPushButton("Controls...")
        controls_help.clicked.connect(lambda _checked=False: show_viewport_navigation_reference(self))
        viewport_controls_row.addWidget(controls_help)
        form.addRow("Viewport Controls:", viewport_controls_row)
        root.addLayout(form)

        self.autoscan_check = QtWidgets.QCheckBox("Scan library on startup")
        self.matrix_check = QtWidgets.QCheckBox("Enable Matrix background")
        root.addWidget(self.autoscan_check)
        root.addWidget(self.matrix_check)
        self._build_theme_layout_group(root)
        self._build_measurement_group(root)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_theme_layout_group(self, root: QtWidgets.QVBoxLayout) -> None:
        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("ThemeLayoutSettingsTabs")

        theme_page = QtWidgets.QWidget()
        theme_form = QtWidgets.QFormLayout(theme_page)
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
        theme_buttons = QtWidgets.QHBoxLayout()
        preview_theme = QtWidgets.QPushButton("Preview Theme")
        preview_theme.clicked.connect(self._preview_theme)
        validate_themes = QtWidgets.QPushButton("Validate Theme Files")
        validate_themes.clicked.connect(self._show_theme_diagnostics)
        open_themes = QtWidgets.QPushButton("Open Themes Folder")
        open_themes.clicked.connect(lambda: self._open_folder(self.theme_manager.user_theme_dir if self.theme_manager else Path("config/themes/themes")))
        theme_buttons.addWidget(preview_theme)
        theme_buttons.addWidget(validate_themes)
        theme_buttons.addWidget(open_themes)
        theme_form.addRow("", theme_buttons)
        tabs.addTab(theme_page, "Theme")

        layout_page = QtWidgets.QWidget()
        layout_form = QtWidgets.QFormLayout(layout_page)
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
        layout_buttons = QtWidgets.QHBoxLayout()
        preview_layout = QtWidgets.QPushButton("Apply Layout")
        preview_layout.clicked.connect(self._preview_layout)
        reset_layout = QtWidgets.QPushButton("Reset Layout")
        reset_layout.clicked.connect(self._reset_layout)
        save_custom_layout = QtWidgets.QPushButton("Save Current Layout as Custom")
        save_custom_layout.clicked.connect(self._save_current_layout_as_custom)
        validate_layouts = QtWidgets.QPushButton("Validate Layout Files")
        validate_layouts.clicked.connect(self._show_layout_diagnostics)
        open_layouts = QtWidgets.QPushButton("Open Layouts Folder")
        open_layouts.clicked.connect(lambda: self._open_folder(self.layout_manager.user_layout_dir if self.layout_manager else Path("config/themes/layouts")))
        layout_buttons.addWidget(preview_layout)
        layout_buttons.addWidget(reset_layout)
        layout_buttons.addWidget(save_custom_layout)
        layout_buttons.addWidget(validate_layouts)
        layout_buttons.addWidget(open_layouts)
        layout_form.addRow("", layout_buttons)
        tabs.addTab(layout_page, "Layout")

        advanced_page = QtWidgets.QWidget()
        advanced_root = QtWidgets.QVBoxLayout(advanced_page)
        self.hot_reload_check = QtWidgets.QCheckBox("Hot reload theme and layout XML during development")
        advanced_root.addWidget(self.hot_reload_check)
        advanced_root.addStretch(1)
        tabs.addTab(advanced_page, "Advanced")
        root.addWidget(tabs)

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
        self.matrix_check.setChecked(bool(self.settings.get("matrix_background", True)))
        self._set_combo_data(self.theme_mode_combo, self.theme_layout_settings.theme_mode)
        self._set_combo_data(self.theme_combo, self.theme_layout_settings.selected_theme)
        self._set_combo_data(self.light_theme_combo, self.theme_layout_settings.os_light_theme)
        self._set_combo_data(self.dark_theme_combo, self.theme_layout_settings.os_dark_theme)
        self._set_combo_data(self.layout_combo, self.theme_layout_settings.selected_layout)
        self._set_combo_data(self.button_mode_combo, self.theme_layout_settings.button_mode_override)
        self.icon_size_spin.setValue(int(self.theme_layout_settings.icon_size_override or 0))
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
        return {
            **self.settings,
            "k1_dir": self.k1_dir.text().strip(),
            "k2_dir": self.k2_dir.text().strip(),
            "texture_dir": self.texture_dir.text().strip(),
            "mdlops_path": self.mdlops_path.text().strip(),
            "viewport_navigation_profile": self.viewport_navigation_profile.currentData(),
            "autoscan": self.autoscan_check.isChecked(),
            "matrix_background": self.matrix_check.isChecked(),
            "theme_layout": {
                "theme_mode": self.theme_mode_combo.currentData(),
                "selected_theme": self.theme_combo.currentData(),
                "os_light_theme": self.light_theme_combo.currentData(),
                "os_dark_theme": self.dark_theme_combo.currentData(),
                "selected_layout": self.layout_combo.currentData(),
                "button_mode_override": self.button_mode_combo.currentData() or "",
                "icon_size_override": self.icon_size_spin.value(),
                "hot_reload_enabled": self.hot_reload_check.isChecked(),
                "last_known_os_theme": self.theme_layout_settings.last_known_os_theme,
                "panel_sizes": dict(self.theme_layout_settings.panel_sizes),
                "splitter_sizes": dict(self.theme_layout_settings.splitter_sizes),
            },
            "measurement": measurement.to_dict(),
        }

    @staticmethod
    def _set_combo_data(combo: QtWidgets.QComboBox, value: object) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(max(index, 0))

    def _preview_theme(self) -> None:
        if self.theme_manager is None:
            return
        if self.theme_mode_combo.currentData() == "follow_os":
            self.theme_manager.settings.os_light_theme = str(self.light_theme_combo.currentData() or "light")
            self.theme_manager.settings.os_dark_theme = str(self.dark_theme_combo.currentData() or "dark")
            self.theme_manager.set_follow_os(True, target=self.parentWidget())
        else:
            self.theme_manager.select_theme(str(self.theme_combo.currentData() or "matrix"), target=self.parentWidget())

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

