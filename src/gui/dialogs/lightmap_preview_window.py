"""Live lightmap preview and comparison window."""

from __future__ import annotations

from PIL import Image
from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.qt_lib.lighting.lightmap_compare import COMPARISON_MODES, LightmapCompare


class LightmapPreviewWindow(QtWidgets.QDialog):
    def __init__(self, mesh: object, parent: QtWidgets.QWidget | None = None, *, texture_cache: object | None = None) -> None:
        super().__init__(parent)
        self.mesh = mesh
        self.texture_cache = texture_cache
        self.compare = LightmapCompare()
        self.new_image: Image.Image | None = None
        self.setWindowTitle("Lightmap Preview")
        self.resize(780, 620)
        root = QtWidgets.QVBoxLayout(self)
        row = QtWidgets.QHBoxLayout()
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(COMPARISON_MODES)
        self.mode_combo.currentTextChanged.connect(lambda _text: self.render())
        row.addWidget(QtWidgets.QLabel("Comparison"))
        row.addWidget(self.mode_combo, 1)
        root.addLayout(row)
        self.warning = QtWidgets.QLabel()
        root.addWidget(self.warning)
        self.image_label = QtWidgets.QLabel("No preview bake yet")
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(420, 420)
        self.image_label.setStyleSheet("background:#101018; border:1px solid #343446; color:#d7d7e8;")
        self.image_label.installEventFilter(self)
        root.addWidget(self.image_label, 1)

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.image_label and event.type() == QtCore.QEvent.Resize:
            self.render()
        return super().eventFilter(obj, event)

    def set_preview_image(self, image: Image.Image | None) -> None:
        self.new_image = image
        self.render()

    def render(self) -> None:
        if self.new_image is None:
            return
        original = self.compare.load_original_lightmap(self.mesh, self.texture_cache)
        comparison = self.compare.compare(self.new_image, original, str(self.mode_combo.currentText()))
        self.warning.setText(comparison.warning)
        if comparison.image is None:
            return
        img = comparison.image.convert("RGBA")
        qimg = QtGui.QImage(img.tobytes("raw", "RGBA"), img.width, img.height, img.width * 4, QtGui.QImage.Format_RGBA8888).copy()
        pix = QtGui.QPixmap.fromImage(qimg)
        self.image_label.setPixmap(
            pix.scaled(self.image_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        )
