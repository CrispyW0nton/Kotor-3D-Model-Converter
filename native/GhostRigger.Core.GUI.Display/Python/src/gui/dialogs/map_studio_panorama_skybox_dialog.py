"""Compact authoring options for panorama/HDR to KOTOR skybox conversion."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtWidgets


class MapStudioPanoramaSkyboxDialog(QtWidgets.QDialog):
    """Collect deterministic offline projection and tone-mapping settings."""

    def __init__(self, source_path: str | Path, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.source_path = str(Path(source_path).resolve())
        self.setObjectName("mapStudioPanoramaSkyboxDialog")
        self.setWindowTitle("Create KOTOR Skybox from Panorama / HDR")
        self.setModal(True)

        root = QtWidgets.QVBoxLayout(self)
        source = QtWidgets.QLabel(f"<b>{Path(self.source_path).name}</b>")
        source.setObjectName("mapStudioPanoramaSourceLabel")
        source.setWordWrap(True)
        root.addWidget(source)
        explanation = QtWidgets.QLabel(
            "Map Studio projects the equirectangular image into north, east, south, west, and top panels. "
            "HDR/EXR light values are tone-mapped offline into ordinary 8-bit sRGB TGA textures because KOTOR "
            "does not load modern HDR environment maps directly."
        )
        explanation.setObjectName("mapStudioPanoramaToneMapExplanation")
        explanation.setWordWrap(True)
        root.addWidget(explanation)

        form = QtWidgets.QFormLayout()
        self.face_size_combo = QtWidgets.QComboBox()
        self.face_size_combo.setObjectName("mapStudioPanoramaFaceSizeComboBox")
        for size, label in (
            (256, "256 px — draft / fastest"),
            (512, "512 px — compact"),
            (1024, "1024 px — recommended"),
            (2048, "2048 px — maximum authoring size"),
        ):
            self.face_size_combo.addItem(label, size)
        self.face_size_combo.setCurrentIndex(self.face_size_combo.findData(1024))
        self.face_size_combo.setToolTip(
            "Power-of-two face size. Map Studio caps this workflow at 2048; use 1024 by default and record retail "
            "KOTOR visual proof for the exported module."
        )
        form.addRow("Face size", self.face_size_combo)

        self.exposure_spin = QtWidgets.QDoubleSpinBox()
        self.exposure_spin.setObjectName("mapStudioPanoramaExposureSpinBox")
        self.exposure_spin.setRange(-10.0, 10.0)
        self.exposure_spin.setDecimals(2)
        self.exposure_spin.setSingleStep(0.25)
        self.exposure_spin.setSuffix(" EV")
        self.exposure_spin.setToolTip("Applied in linear light before tone mapping.")
        form.addRow("Exposure", self.exposure_spin)

        self.yaw_spin = QtWidgets.QDoubleSpinBox()
        self.yaw_spin.setObjectName("mapStudioPanoramaYawSpinBox")
        self.yaw_spin.setRange(-180.0, 180.0)
        self.yaw_spin.setDecimals(1)
        self.yaw_spin.setSingleStep(5.0)
        self.yaw_spin.setSuffix("°")
        self.yaw_spin.setToolTip("Rotate the panorama around KOTOR's Z-up horizon before projection.")
        form.addRow("Yaw", self.yaw_spin)

        self.tone_mapper_combo = QtWidgets.QComboBox()
        self.tone_mapper_combo.setObjectName("mapStudioPanoramaToneMapperComboBox")
        self.tone_mapper_combo.addItem("ACES — filmic highlight rolloff", "aces")
        self.tone_mapper_combo.addItem("Reinhard — neutral compression", "reinhard")
        form.addRow("Tone mapping", self.tone_mapper_combo)
        root.addLayout(form)

        self.storage_label = QtWidgets.QLabel()
        self.storage_label.setObjectName("mapStudioPanoramaStorageEstimateLabel")
        self.storage_label.setWordWrap(True)
        root.addWidget(self.storage_label)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.setObjectName("mapStudioPanoramaButtonBox")
        self.create_button = self.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.create_button.setText("Convert & Create Skybox")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        root.addWidget(self.button_box)

        self.face_size_combo.currentIndexChanged.connect(self._refresh_storage_estimate)
        self._refresh_storage_estimate()

    def settings(self) -> dict[str, object]:
        return {
            "face_size": int(self.face_size_combo.currentData() or 1024),
            "exposure_ev": float(self.exposure_spin.value()),
            "longitude_offset_degrees": float(self.yaw_spin.value()),
            "tone_mapper": str(self.tone_mapper_combo.currentData() or "aces"),
        }

    def _refresh_storage_estimate(self, _index: int = -1) -> None:
        size = int(self.face_size_combo.currentData() or 1024)
        mib = 5 * size * size * 4 / float(1024 ** 2)
        self.storage_label.setText(
            f"Five uncompressed project TGAs will use about {mib:.0f} MiB before module packaging. "
            "The panorama path and conversion settings remain lightweight KMAP metadata."
        )

    def apply_ghost_theme(self, _theme: object) -> None:
        self.update()

    def apply_ghost_layout(self, _layout: object) -> None:
        self.updateGeometry()


__all__ = ["MapStudioPanoramaSkyboxDialog"]
