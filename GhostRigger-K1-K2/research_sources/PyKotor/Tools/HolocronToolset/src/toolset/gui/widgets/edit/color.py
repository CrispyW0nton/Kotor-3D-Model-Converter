"""Color edit widget: RGBA spin and color picker dialog for PyKotor Color."""

from __future__ import annotations

from typing import ClassVar

from qtpy.QtCore import Signal  # pyright: ignore[reportPrivateImportUsage]
from qtpy.QtGui import QColor, QImage, QPixmap
from qtpy.QtWidgets import QColorDialog, QWidget

from pykotor.common.misc import Color


class ColorEdit(QWidget):
    sig_color_changed: ClassVar[Signal] = Signal(object)  # Color

    def __init__(self, parent: QWidget):
        super().__init__(parent)

        self._color: Color = Color(255, 255, 255)
        self.allow_alpha: bool = False

        from toolset.uic.qtpy.widgets.color_edit import Ui_Form

        self.ui = Ui_Form()
        self.ui.setupUi(self)

        self.ui.editButton.clicked.connect(self.open_color_dialog)
        self.ui.colorSpin.sig_value_changed.connect(self._on_color_change)

    def open_color_dialog(self):
        init_color: Color = Color.from_rgba_integer(self.ui.colorSpin.value())
        init_qcolor: QColor = QColor(int(init_color.r * 255), int(init_color.g * 255), int(init_color.b * 255), int(init_color.a * 255))

        dialog: QColorDialog = QColorDialog(QColor(init_qcolor.red(), init_qcolor.green(), init_qcolor.blue(), init_qcolor.alpha()))
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, on=self.allow_alpha)

        if dialog.exec():
            qcolor = dialog.selectedColor()
            color: Color = Color(qcolor.redF(), qcolor.greenF(), qcolor.blueF())
            if self.allow_alpha:
                self.ui.colorSpin.setValue(color.rgb_integer() + (qcolor.alpha() << 24))
            else:
                self.ui.colorSpin.setValue(color.rgb_integer())
            # Sync _color and emit (setValue may not trigger signal if unchanged)
            self._color.r, self._color.g, self._color.b = color.r, color.g, color.b
            self._color.a = qcolor.alphaF() if self.allow_alpha else 0.0
            self.sig_color_changed.emit(self._color)

    def _on_color_change(
        self,
        value: int,
    ):
        color: Color = Color.from_rgba_integer(value)
        self._color.r, self._color.g, self._color.b, self._color.a = color.r, color.g, color.b, color.a
        if not self.allow_alpha:
            self._color.a = 0.0
        r, g, b = int(color.r * 255), int(color.g * 255), int(color.b * 255)
        data = bytes([b, g, r] * 16 * 16)
        pixmap: QPixmap = QPixmap.fromImage(QImage(data, 16, 16, QImage.Format.Format_BGR888))
        self.ui.colorLabel.setPixmap(pixmap)
        self.sig_color_changed.emit(self._color)

    def set_color(self, color: Color):
        self._color: Color = color
        self.ui.colorSpin.setValue(color.rgba_integer() if self.allow_alpha else color.rgb_integer())

    def color(self) -> Color:
        return self._color
