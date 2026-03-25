"""Shared marquee selection constants and drawing for 2D flat renderers.

Used by IndoorMapRenderer, WalkmeshRenderer (GITEditor, ModuleDesigner 2D, BWMEditor, etc.)
so marquee selection looks and behaves consistently across editors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from qtpy.QtCore import QRectF, Qt
from qtpy.QtGui import QColor, QPen

if TYPE_CHECKING:
    from qtpy.QtGui import QPainter

    from utility.common.geometry import Vector2

# Minimum drag distance (pixels) before treating as marquee rather than click
MARQUEE_MOVE_THRESHOLD_PIXELS: Final[float] = 5.0

# Visual style (RGBA)
MARQUEE_FILL_COLOR: Final[tuple[int, int, int, int]] = (100, 150, 255, 50)
MARQUEE_BORDER_COLOR: Final[tuple[int, int, int, int]] = (100, 150, 255, 255)


def draw_marquee_rect(
    painter: QPainter,
    start: Vector2,
    end: Vector2,
) -> None:
    """Draw the marquee selection rectangle in screen coordinates.

    Call with painter in screen space (e.g. after resetTransform).
    """
    x1, y1 = start.x, start.y
    x2, y2 = end.x, end.y
    rect = QRectF(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
    painter.setBrush(
        QColor(
            MARQUEE_FILL_COLOR[0],
            MARQUEE_FILL_COLOR[1],
            MARQUEE_FILL_COLOR[2],
            MARQUEE_FILL_COLOR[3],
        ),
    )
    painter.setPen(
        QPen(
            QColor(
                MARQUEE_BORDER_COLOR[0],
                MARQUEE_BORDER_COLOR[1],
                MARQUEE_BORDER_COLOR[2],
                MARQUEE_BORDER_COLOR[3],
            ),
            1,
            Qt.PenStyle.DashLine,
        ),
    )
    painter.drawRect(rect)
