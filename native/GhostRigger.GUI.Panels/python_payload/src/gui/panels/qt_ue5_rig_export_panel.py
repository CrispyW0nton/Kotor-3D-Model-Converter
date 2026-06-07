"""Qt panel for Sprint 1.5 UE5 Rig Export."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.qt_lib.assets.qt_theme import heading
from src.workbench.ue5_rig_export import (
    DEFAULT_OUTPUT_DIR,
    UE5RigExportRequest,
    UE5RigExportResult,
    available_animations,
    available_characters,
    export_ue5_rig,
)


class QtUE5RigExportPanel(QtWidgets.QWidget):
    """One-click Day 4.5 v6 export surface for the Unreal Workbench."""

    exportCompleted = QtCore.Signal(object)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._last_result: UE5RigExportResult | None = None
        self._build()
        self.refresh_options()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)
        root.addWidget(heading("UE5 Rig Export"))

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignLeft)
        self.character_combo = QtWidgets.QComboBox()
        self.character_combo.currentTextChanged.connect(self._refresh_animations)
        self.animation_combo = QtWidgets.QComboBox()
        form.addRow("Character", self.character_combo)
        form.addRow("Animation", self.animation_combo)
        root.addLayout(form)

        output_row = QtWidgets.QHBoxLayout()
        self.output_dir_edit = QtWidgets.QLineEdit(str(DEFAULT_OUTPUT_DIR))
        self.output_dir_edit.setMinimumWidth(120)
        self.browse_button = QtWidgets.QPushButton("Browse")
        self.browse_button.clicked.connect(self._browse_output_dir)
        output_row.addWidget(self.output_dir_edit, 1)
        output_row.addWidget(self.browse_button)
        root.addWidget(QtWidgets.QLabel("Output Directory"))
        root.addLayout(output_row)

        self.export_button = QtWidgets.QPushButton("Export UE5 FBX")
        self.export_button.setProperty("accent", True)
        self.export_button.clicked.connect(self._run_export)
        root.addWidget(self.export_button)

        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setWordWrap(True)
        self.status_label.setProperty("meta", True)
        root.addWidget(self.status_label)

        metrics_box = QtWidgets.QGroupBox("Validation")
        metrics_layout = QtWidgets.QFormLayout(metrics_box)
        self.pass_label = QtWidgets.QLabel("-")
        self.height_label = QtWidgets.QLabel("-")
        self.width_label = QtWidgets.QLabel("-")
        self.silhouette_label = QtWidgets.QLabel("-")
        self.missing_bones_label = QtWidgets.QLabel("-")
        self.roundtrip_label = QtWidgets.QLabel("-")
        self.missing_bones_label.setWordWrap(True)
        metrics_layout.addRow("Status", self.pass_label)
        metrics_layout.addRow("Height", self.height_label)
        metrics_layout.addRow("Width", self.width_label)
        metrics_layout.addRow("Silhouette", self.silhouette_label)
        metrics_layout.addRow("Missing Bones", self.missing_bones_label)
        metrics_layout.addRow("Roundtrip", self.roundtrip_label)
        root.addWidget(metrics_box)

        artifacts_box = QtWidgets.QGroupBox("Artifacts")
        artifacts_layout = QtWidgets.QVBoxLayout(artifacts_box)
        self.artifact_text = QtWidgets.QPlainTextEdit()
        self.artifact_text.setReadOnly(True)
        self.artifact_text.setMaximumBlockCount(80)
        artifacts_layout.addWidget(self.artifact_text, 1)
        self.open_folder_button = QtWidgets.QPushButton("Open Containing Folder")
        self.open_folder_button.clicked.connect(self._open_containing_folder)
        self.open_folder_button.setEnabled(False)
        artifacts_layout.addWidget(self.open_folder_button)
        root.addWidget(artifacts_box, 1)
        root.addStretch(1)

    def refresh_options(self) -> None:
        current = self.character_combo.currentText()
        self.character_combo.blockSignals(True)
        self.character_combo.clear()
        self.character_combo.addItems(available_characters())
        if current:
            idx = self.character_combo.findText(current)
            if idx >= 0:
                self.character_combo.setCurrentIndex(idx)
        self.character_combo.blockSignals(False)
        self._refresh_animations(self.character_combo.currentText())

    def selected_request(self) -> UE5RigExportRequest:
        return UE5RigExportRequest(
            character_name=self.character_combo.currentText(),
            animation_name=self.animation_combo.currentText(),
            output_dir=Path(self.output_dir_edit.text().strip() or DEFAULT_OUTPUT_DIR),
        )

    def show_result(self, result: UE5RigExportResult) -> None:
        self._last_result = result
        metrics = result.validation_metrics or {}
        self.pass_label.setText("PASS" if result.success else "HALT")
        self.pass_label.setStyleSheet("color:#74ff9b;font-weight:700;" if result.success else "color:#ff7474;font-weight:700;")
        self.height_label.setText(_fmt_ratio(metrics.get("height_ratio")))
        self.width_label.setText(_fmt_ratio(metrics.get("width_ratio")))
        self.silhouette_label.setText(_fmt_ratio(metrics.get("silhouette_proxy")))
        missing = metrics.get("missing_humanoid_bones", [])
        self.missing_bones_label.setText(", ".join(missing) if missing else "None")
        roundtrip = metrics.get("roundtrip", {})
        self.roundtrip_label.setText(
            f"bones {roundtrip.get('bones', '-')}, "
            f"verts {roundtrip.get('vertices', '-')}, "
            f"frames {roundtrip.get('frames', '-')}"
        )
        if result.success:
            self.status_label.setText("UE5 Rig Export passed validation.")
        else:
            self.status_label.setText(result.halt_reason or "UE5 Rig Export failed.")
        self.artifact_text.setPlainText(self._artifact_summary(result))
        self.open_folder_button.setEnabled(bool(result.fbx_path))
        self.exportCompleted.emit(result)

    def _refresh_animations(self, character_name: str) -> None:
        current = self.animation_combo.currentText()
        self.animation_combo.clear()
        self.animation_combo.addItems(available_animations(character_name))
        if current:
            idx = self.animation_combo.findText(current)
            if idx >= 0:
                self.animation_combo.setCurrentIndex(idx)

    def _browse_output_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select UE5 Rig Export Directory",
            self.output_dir_edit.text().strip() or str(DEFAULT_OUTPUT_DIR),
        )
        if directory:
            self.output_dir_edit.setText(directory)

    def _run_export(self) -> None:
        self.export_button.setEnabled(False)
        self.status_label.setText("Exporting UE5 FBX...")
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            self.show_result(export_ue5_rig(self.selected_request()))
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.export_button.setEnabled(True)

    def _open_containing_folder(self) -> None:
        path = self._last_result.fbx_path if self._last_result else None
        if path is None:
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(Path(path).parent)))

    @staticmethod
    def _artifact_summary(result: UE5RigExportResult) -> str:
        lines: list[str] = []
        for label, path in (
            ("FBX", result.fbx_path),
            ("Manifest", result.manifest_path),
            ("Visual Gate", result.visual_gate_path),
            ("UE5 Setup Notes", result.ue5_setup_notes_path),
        ):
            if path:
                lines.append(f"{label}: {path}")
        if result.fbx_sha256:
            lines.append(f"SHA-256: {result.fbx_sha256}")
        if result.halt_reason:
            lines.append(f"HALT: {result.halt_reason}")
        return "\n".join(lines) if lines else "(No artifacts yet)"


def _fmt_ratio(value: object) -> str:
    try:
        return f"{float(value):.6f}"
    except Exception:
        return "-"


__all__ = ["QtUE5RigExportPanel"]
