"""First-pass numeric curve editor."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.assets.qt_theme import C


class SequenceCurveEditor(QtWidgets.QWidget):
    interpolationChanged = QtCore.Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.track = None
        self.setMinimumHeight(150)

    def set_track(self, track) -> None:
        self.track = track
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(C["bg"]))
        painter.setPen(QtGui.QColor(C["border"]))
        for i in range(1, 4):
            y = int(self.height() * i / 4)
            painter.drawLine(0, y, self.width(), y)
        if self.track is None or not getattr(self.track, "keyframes", None):
            painter.setPen(QtGui.QColor(C["text2"]))
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, "Select a numeric track to edit curves")
            return
        keys = sorted(self.track.keyframes, key=lambda key: key.frame)
        values = []
        for key in keys:
            value = key.value
            if isinstance(value, dict):
                value = value.get("location", value.get("scale", (0.0, 0.0, 0.0)))
            if isinstance(value, (tuple, list)) and value:
                value = value[0]
            if isinstance(value, (int, float)):
                values.append(float(value))
        if not values:
            painter.setPen(QtGui.QColor(C["text2"]))
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, "No numeric channel in selected track")
            return
        min_frame, max_frame = keys[0].frame, keys[-1].frame
        min_value, max_value = min(values), max(values)
        if abs(max_value - min_value) < 1e-6:
            max_value += 1.0
            min_value -= 1.0
        points = []
        for key, value in zip(keys, values):
            frame_t = 0.0 if max_frame == min_frame else (key.frame - min_frame) / (max_frame - min_frame)
            value_t = (value - min_value) / (max_value - min_value)
            x = int(12 + frame_t * max(1, self.width() - 24))
            y = int(self.height() - 12 - value_t * max(1, self.height() - 24))
            points.append(QtCore.QPoint(x, y))
        painter.setPen(QtGui.QPen(QtGui.QColor(C["accent2"]), 2))
        if len(points) > 1:
            painter.drawPolyline(QtGui.QPolygon(points))
        painter.setBrush(QtGui.QColor(C["accent"]))
        for point in points:
            painter.drawEllipse(point, 4, 4)
