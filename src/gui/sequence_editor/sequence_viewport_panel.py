"""Embedded sequence viewport panel."""

from __future__ import annotations

from PySide6 import QtWidgets

from src.gui.qt_lib.viewports.qt_viewport import QtMainViewportWidget


class SequenceViewportPanel(QtWidgets.QWidget):
    MODES = ("Cinematic Camera View", "Director Preview", "Free Preview", "Split View")

    def __init__(self, source_viewport=None, parent=None) -> None:
        super().__init__(parent)
        self.source_viewport = source_viewport
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        top = QtWidgets.QHBoxLayout()
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(self.MODES)
        self.warning_label = QtWidgets.QLabel("")
        top.addWidget(self.mode_combo)
        top.addWidget(self.warning_label, 1)
        layout.addLayout(top)
        self.viewport = QtMainViewportWidget(self, compact_controls=True)
        self.viewport.setMinimumHeight(220)
        layout.addWidget(self.viewport, 1)
        self.sync_from_source()

    def sync_from_source(self) -> None:
        if self.source_viewport is None:
            return
        model = getattr(self.source_viewport, "model", None)
        if model is not None:
            self.viewport.set_model(model)
        settings = getattr(self.source_viewport, "measurement_settings", None)
        if settings is not None:
            self.viewport.set_measurement_settings(settings)

    def set_warning(self, text: str) -> None:
        self.warning_label.setText(text or "")
