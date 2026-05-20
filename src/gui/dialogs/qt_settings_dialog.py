"""Qt settings dialog for GhostRigger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from src.gui.qt_lib.assets.qt_theme import C
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

    def __init__(self, settings: Optional[dict] = None, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = dict(settings or {})
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
        self._build_measurement_group(root)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

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
            "measurement": measurement.to_dict(),
        }

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

