"""Custom progress bar with optional shimmer animation and style-safe content rect."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy import QtCore
from qtpy.QtCore import QRectF, QTimer
from qtpy.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPalette
from qtpy.QtWidgets import QApplication, QProgressBar, QStyle, QStyleOptionProgressBar

if TYPE_CHECKING:
    from qtpy.QtCore import QRect
    from qtpy.QtGui import QPaintEvent


def _content_rect(progress_bar: QProgressBar) -> QRect:
    """Return the progress bar groove/content rect in widget coordinates.

    Uses the style's subElementRect so the shimmer is drawn exactly where the
    bar is drawn, avoiding misalignment (e.g. animation in top-left vs bar in center).
    """
    option = QStyleOptionProgressBar()
    progress_bar.initStyleOption(option)
    style = progress_bar.style()
    if style is None:
        return progress_bar.rect()

    # qtpy can expose enums either namespaced (Qt6-style) or flat (Qt5-style).
    sub_element_enum = getattr(QStyle, "SubElement", QStyle)
    se_contents = getattr(sub_element_enum, "SE_ProgressBarContents", None)
    se_groove = getattr(sub_element_enum, "SE_ProgressBarGroove", None)

    if se_contents is not None:
        content = style.subElementRect(se_contents, option, progress_bar)
        if not content.isEmpty():
            return content
    if se_groove is not None:
        groove = style.subElementRect(se_groove, option, progress_bar)
        if not groove.isEmpty():
            return groove
    return progress_bar.rect()


class AnimatedProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer: QTimer = QTimer(self)
        self._timer.timeout.connect(self.update_animation)
        self._timer.start(50)  # Update every 50 ms
        self._offset: int = 0

    def update_animation(self):
        content = _content_rect(self)
        if content.width() <= 0:
            return
        if self.maximum() == self.minimum():
            # Indeterminate: sweep across full content width
            self._offset = (self._offset + 1) % content.width()
        else:
            filled_width = int(
                content.width() * (self.value() - self.minimum()) / (self.maximum() - self.minimum()),
            )
            if filled_width == 0:
                return
            self._offset = (self._offset + 1) % filled_width
        self.update()

    def paintEvent(
        self,
        event: QPaintEvent,
    ):
        super().paintEvent(event)

        content: QRect = _content_rect(self)
        if content.isEmpty():
            return

        painter: QPainter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # pyright: ignore[reportAttributeAccessIssue]

        chunk_height: int = content.height()
        chunk_radius: float = min(chunk_height / 2, content.width() / 2)

        if self.maximum() == self.minimum():
            filled_width = content.width()
        else:
            filled_width = int(
                content.width() * (self.value() - self.minimum()) / (self.maximum() - self.minimum()),
            )
        filled_width = max(filled_width, chunk_height)

        if filled_width <= 0:
            painter.end()
            return

        # Shimmer rect in widget coordinates, constrained to the content (groove) rect
        light_width = chunk_height * 2
        light_left = content.left() + self._offset - light_width / 2
        light_rect = QRectF(
            float(light_left),
            float(content.top()),
            float(light_width),
            float(chunk_height),
        )
        if light_rect.left() < content.left():
            light_rect.moveLeft(float(content.left()))
        if light_rect.right() > content.right():
            light_rect.moveRight(float(content.right()))

        app = QApplication.instance()
        if app is not None and isinstance(app, QApplication):
            palette = app.palette()
        else:
            palette = QPalette()

        shimmer_base_color = palette.color(QPalette.ColorRole.BrightText)
        if shimmer_base_color.lightness() < 128:
            shimmer_base_color = palette.color(QPalette.ColorRole.Light)
        if shimmer_base_color.lightness() < 180:
            shimmer_base_color = QColor(shimmer_base_color)
            shimmer_base_color = shimmer_base_color.lighter(150)

        shimmer_gradient = QLinearGradient(
            light_rect.left(),
            0,
            light_rect.right(),
            0,
        )
        shimmer_gradient.setColorAt(
            0,
            QColor(
                shimmer_base_color.red(),
                shimmer_base_color.green(),
                shimmer_base_color.blue(),
                0,
            ),
        )
        shimmer_gradient.setColorAt(
            0.5,
            QColor(
                shimmer_base_color.red(),
                shimmer_base_color.green(),
                shimmer_base_color.blue(),
                150,
            ),
        )
        shimmer_gradient.setColorAt(
            1,
            QColor(
                shimmer_base_color.red(),
                shimmer_base_color.green(),
                shimmer_base_color.blue(),
                0,
            ),
        )

        painter.setBrush(QBrush(shimmer_gradient))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)  # pyright: ignore[reportAttributeAccessIssue]
        painter.drawRoundedRect(light_rect, chunk_radius, chunk_radius)

        painter.end()
