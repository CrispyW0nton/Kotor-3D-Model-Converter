"""Compact viewport reference coordinate-system control."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from src.core.scene.axis_mode import AxisMode


class AxisModeControl(QtWidgets.QWidget):
    """Small toolbar widget for choosing the active transform axis mode."""

    axisModeChanged = QtCore.Signal(object)
    TOOLBAR_HEIGHT = 22
    TOOLBAR_VERTICAL_NUDGE = 0

    def __init__(self, parent: QtWidgets.QWidget | None = None, *, compact: bool = False) -> None:
        super().__init__(parent)
        self._compact = bool(compact)
        self._build()

    def _build(self) -> None:
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(
            0,
            self.TOOLBAR_VERTICAL_NUDGE,
            0,
            -self.TOOLBAR_VERTICAL_NUDGE,
        )
        row.setSpacing(3)
        self.label = QtWidgets.QLabel("Axis" if self._compact else "Reference Coordinate System")
        self.combo = QtWidgets.QComboBox()
        self.combo.setObjectName("AxisModeComboBox")
        self.combo.setToolTip("Choose the transform reference coordinate system.")
        self.combo.setFixedHeight(self.TOOLBAR_HEIGHT)
        self.combo.setMinimumWidth(72 if self._compact else 112)
        self.combo.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.setFixedHeight(self.TOOLBAR_HEIGHT)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        for mode in AxisMode:
            self.combo.addItem(mode.label, mode.value)
        self.combo.currentIndexChanged.connect(self._emit_mode)
        row.addWidget(self.label)
        row.addWidget(self.combo)

    def axis_mode(self) -> AxisMode:
        return AxisMode.from_value(self.combo.currentData())

    def set_axis_mode(self, mode: AxisMode | str, *, label: str | None = None) -> None:
        resolved = AxisMode.from_value(mode)
        index = self.combo.findData(resolved.value)
        if index >= 0:
            self.combo.blockSignals(True)
            self.combo.setCurrentIndex(index)
            if label:
                self.combo.setItemText(index, label)
            else:
                self.combo.setItemText(index, resolved.label)
            self.combo.blockSignals(False)

    def _emit_mode(self, _index: int) -> None:
        mode = self.axis_mode()
        if mode is not AxisMode.PICK:
            index = self.combo.findData(AxisMode.PICK.value)
            if index >= 0:
                self.combo.setItemText(index, AxisMode.PICK.label)
        self.axisModeChanged.emit(mode)

    def apply_ghost_theme(self, theme) -> None:
        if theme is None:
            return
        self.label.setStyleSheet(f"color:{theme.color('text.secondary')};")
        self.combo.setStyleSheet(
            f"QComboBox#AxisModeComboBox {{ background:{theme.color('input.background')}; "
            f"color:{theme.color('input.text')}; "
            f"border:1px solid {theme.color('viewportToolbar.border', theme.color('input.border'))}; "
            "border-radius:2px; min-height:22px; max-height:22px; padding:1px 18px 1px 7px; }"
            f"QComboBox#AxisModeComboBox:hover {{ border-color:{theme.color('accent.secondary')}; }}"
            "QComboBox#AxisModeComboBox::drop-down { border:0; width:16px; }"
            f"QComboBox#AxisModeComboBox QAbstractItemView {{ background:{theme.color('panel.background')}; "
            f"color:{theme.color('text.primary')}; selection-background-color:{theme.color('selection.background')}; }}"
        )

    def apply_ghost_layout(self, layout) -> None:
        toolbar = layout.toolbar("viewport")
        combo_height = max(20, min(toolbar.height - 10, self.TOOLBAR_HEIGHT))
        self.combo.setFixedHeight(combo_height)
        self.setFixedHeight(combo_height)
        if self.layout() is not None:
            self.layout().setSpacing(layout.spacing_value("toolbarSpacing", 3))
