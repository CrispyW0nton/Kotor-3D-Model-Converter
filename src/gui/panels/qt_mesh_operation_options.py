"""Operation option controls for the Mesh Tools dock."""

from __future__ import annotations

from dataclasses import asdict

from PySide6 import QtWidgets

from src.gui.libtheme.collapsible_group import CollapsibleGroupBox
from src.mesh_tools.mesh_edit_types import MeshOperationOptions


class QtMeshOperationOptionsWidget(CollapsibleGroupBox):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__("Operation Options", parent)
        self._build()

    def _build(self) -> None:
        form = QtWidgets.QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        self.weld_threshold = self._double_spin(0.001, 0.0, 1000.0, 4)
        self.bridge_segments = self._int_spin(1, 1, 64)
        self.bridge_twist = self._int_spin(0, -256, 256)
        self.bridge_smooth = QtWidgets.QCheckBox()
        self.connect_segments = self._int_spin(1, 1, 64)
        self.connect_pinch = self._double_spin(0.0, -1.0, 1.0, 3)
        self.connect_slide = self._double_spin(0.0, -1.0, 1.0, 3)
        self.preserve_uvs = self._checked_box(True)
        self.preserve_materials = self._checked_box(True)
        self.preserve_normals = self._checked_box(True)
        self.preserve_aurora_metadata = self._checked_box(True)
        for label, widget in [
            ("Weld Threshold", self.weld_threshold),
            ("Bridge Segments", self.bridge_segments),
            ("Bridge Twist", self.bridge_twist),
            ("Bridge Smooth", self.bridge_smooth),
            ("Connect Segments", self.connect_segments),
            ("Connect Pinch", self.connect_pinch),
            ("Connect Slide", self.connect_slide),
            ("Preserve UVs", self.preserve_uvs),
            ("Preserve Materials", self.preserve_materials),
            ("Preserve Normals", self.preserve_normals),
            ("Preserve Aurora Metadata", self.preserve_aurora_metadata),
        ]:
            form.addRow(label, widget)

    def options(self) -> dict:
        return asdict(MeshOperationOptions(
            weld_threshold=float(self.weld_threshold.value()),
            bridge_segments=int(self.bridge_segments.value()),
            bridge_twist=int(self.bridge_twist.value()),
            bridge_smooth=bool(self.bridge_smooth.isChecked()),
            connect_segments=int(self.connect_segments.value()),
            connect_pinch=float(self.connect_pinch.value()),
            connect_slide=float(self.connect_slide.value()),
            preserve_uvs=bool(self.preserve_uvs.isChecked()),
            preserve_materials=bool(self.preserve_materials.isChecked()),
            preserve_normals=bool(self.preserve_normals.isChecked()),
            preserve_aurora_metadata=bool(self.preserve_aurora_metadata.isChecked()),
        ))

    @staticmethod
    def _double_spin(value: float, minimum: float, maximum: float, decimals: int) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setValue(value)
        spin.setSingleStep(10 ** -decimals)
        return spin

    @staticmethod
    def _int_spin(value: int, minimum: int, maximum: int) -> QtWidgets.QSpinBox:
        spin = QtWidgets.QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    @staticmethod
    def _checked_box(value: bool) -> QtWidgets.QCheckBox:
        box = QtWidgets.QCheckBox()
        box.setChecked(value)
        return box
