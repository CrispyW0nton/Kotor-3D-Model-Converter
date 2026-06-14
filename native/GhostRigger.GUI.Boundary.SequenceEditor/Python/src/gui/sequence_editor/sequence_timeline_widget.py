"""Dope-sheet timeline widget for GhostRigger sequences."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.assets.qt_theme import C
from src.sequence.sequence_model import GhostRiggerLevelSequence
from src.sequence.tracks.camera_cut_track import CameraCutTrack


class SequenceTimelineWidget(QtWidgets.QWidget):
    frameChanged = QtCore.Signal(int)
    keySelectionChanged = QtCore.Signal()
    keyMoved = QtCore.Signal()
    contextMenuRequested = QtCore.Signal(QtCore.QPoint)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.sequence: GhostRiggerLevelSequence | None = None
        self.pixels_per_frame = 8.0
        self.row_height = 26
        self.ruler_height = 24
        self.left_margin = 8
        self.snap_keys = True
        self._dragging_playhead = False
        self._dragging_keys = False
        self._drag_start_frame = 0
        self._drag_last_frame = 0
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMinimumHeight(260)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

    def apply_ghost_theme(self, theme) -> None:
        self.update()

    def apply_ghost_layout(self, layout) -> None:
        self.row_height = max(18, layout.spacing_value("tableRowHeight", self.row_height))
        self.ruler_height = max(22, layout.spacing_value("panelHeaderHeight", self.ruler_height))
        self.setMinimumHeight(max(180, self.row_height * 8 + self.ruler_height))
        self._sync_min_width()
        self.update()

    def set_sequence(self, sequence: GhostRiggerLevelSequence | None) -> None:
        self.sequence = sequence
        self._sync_min_width()
        self.update()

    def visible_tracks(self):
        if self.sequence is None:
            return []
        tracks = list(self.sequence.master_tracks)
        for binding in self.sequence.bindings:
            tracks.extend(binding.tracks)
        return tracks

    def tracks_with_rows(self):
        if self.sequence is None:
            return []
        rows = []
        rows.append(("master", None, None))
        if bool(self.sequence.metadata.get("master_tracks_expanded", True)):
            for track in self.sequence.master_tracks:
                rows.append(("track", None, track))
        for binding in self.sequence.bindings:
            rows.append(("binding", binding, None))
            if bool(binding.metadata.get("expanded", not binding.missing)):
                for track in binding.tracks:
                    rows.append(("track", binding, track))
        return rows

    def set_row_metrics(self, *, row_height: int | None = None, ruler_height: int | None = None) -> None:
        if row_height is not None:
            self.row_height = max(18, int(row_height))
        if ruler_height is not None:
            self.ruler_height = max(20, int(ruler_height))
        self.setMinimumHeight(max(180, self.row_height * 8 + self.ruler_height))
        self.update()

    def frame_to_x(self, frame: int) -> int:
        if self.sequence is None:
            return self.left_margin
        return int(self.left_margin + (int(frame) - int(self.sequence.start_frame)) * self.pixels_per_frame)

    def x_to_frame(self, x: int) -> int:
        if self.sequence is None:
            return 0
        frame = int(round((int(x) - self.left_margin) / self.pixels_per_frame)) + int(self.sequence.start_frame)
        return self.sequence.clamp_frame(frame)

    def row_at(self, y: int) -> int:
        return int((int(y) - self.ruler_height) // self.row_height)

    def set_zoom(self, value: float) -> None:
        self.pixels_per_frame = max(2.0, min(64.0, float(value)))
        self._sync_min_width()
        self.update()

    def selected_key_count(self) -> int:
        if self.sequence is None:
            return 0
        return sum(1 for track in self.sequence.all_tracks() for key in track.keyframes if key.selected)

    def clear_key_selection(self) -> None:
        if self.sequence is None:
            return
        for track in self.sequence.all_tracks():
            track.clear_selection()
        self.keySelectionChanged.emit()
        self.update()

    def select_key_at(self, frame: int, track, additive: bool = False) -> bool:
        if self.sequence is None:
            return False
        if not additive:
            self.clear_key_selection()
        hit = False
        for key in track.keyframes:
            if abs(int(key.frame) - int(frame)) <= 1:
                key.selected = True
                hit = True
                break
        if hit:
            self.keySelectionChanged.emit()
            self.update()
        return hit

    def delete_selected_keys(self) -> int:
        if self.sequence is None:
            return 0
        count = sum(track.delete_selected_keyframes() for track in self.sequence.all_tracks())
        if count:
            self.keySelectionChanged.emit()
            self.update()
        return count

    def paintEvent(self, event):  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor(C["bg2"]))
        if self.sequence is None:
            painter.setPen(QtGui.QColor(C["text2"]))
            painter.drawText(self.rect(), QtCore.Qt.AlignCenter, "No sequence")
            return
        self._draw_ruler(painter)
        self._draw_rows(painter)
        self._draw_markers(painter)
        self._draw_playhead(painter)

    def _draw_ruler(self, painter: QtGui.QPainter) -> None:
        assert self.sequence is not None
        painter.fillRect(0, 0, self.width(), self.ruler_height, QtGui.QColor(C["panel"]))
        painter.setPen(QtGui.QColor(C["border"]))
        painter.drawLine(0, self.ruler_height - 1, self.width(), self.ruler_height - 1)
        step = max(1, int(round(48 / self.pixels_per_frame)))
        for frame in range(self.sequence.start_frame, self.sequence.end_frame + 1, step):
            x = self.frame_to_x(frame)
            painter.setPen(QtGui.QColor(C["border"]))
            painter.drawLine(x, self.ruler_height - 8, x, self.height())
            painter.setPen(QtGui.QColor(C["text2"]))
            painter.drawText(x + 3, 18, str(frame))

    def _draw_rows(self, painter: QtGui.QPainter) -> None:
        for row, (kind, _binding, track) in enumerate(self.tracks_with_rows()):
            y = self.ruler_height + row * self.row_height
            bg = QtGui.QColor(C["panel"] if kind in {"master", "binding"} else (C["panel2"] if row % 2 else C["bg2"]))
            painter.fillRect(0, y, self.width(), self.row_height, bg)
            painter.setPen(QtGui.QColor(C["border"]))
            painter.drawLine(0, y + self.row_height - 1, self.width(), y + self.row_height - 1)
            if track is None:
                continue
            if isinstance(track, CameraCutTrack):
                for cut in track.cuts:
                    x1 = self.frame_to_x(cut.start_frame)
                    x2 = self.frame_to_x(cut.end_frame)
                    painter.fillRect(x1, y + 4, max(3, x2 - x1), self.row_height - 8, QtGui.QColor(cut.color))
                    painter.setPen(QtGui.QColor(C["text"]))
                    painter.drawText(x1 + 6, y + 18, cut.display_name)
            for key in track.keyframes:
                x = self.frame_to_x(key.frame)
                points = [
                    QtCore.QPoint(x, y + 5),
                    QtCore.QPoint(x + 7, y + self.row_height // 2),
                    QtCore.QPoint(x, y + self.row_height - 5),
                    QtCore.QPoint(x - 7, y + self.row_height // 2),
                ]
                painter.setBrush(QtGui.QColor(C["accent"] if key.selected else track.color))
                painter.setPen(QtGui.QColor(C["text"] if key.selected else C["border"]))
                painter.drawPolygon(QtGui.QPolygon(points))

    def _draw_markers(self, painter: QtGui.QPainter) -> None:
        assert self.sequence is not None
        for marker in self.sequence.markers:
            x = self.frame_to_x(marker.frame)
            painter.setPen(QtGui.QColor(marker.color))
            painter.drawLine(x, 0, x, self.height())
            painter.drawText(x + 4, self.ruler_height - 10, marker.name)

    def _draw_playhead(self, painter: QtGui.QPainter) -> None:
        assert self.sequence is not None
        x = self.frame_to_x(self.sequence.current_frame)
        painter.setPen(QtGui.QPen(QtGui.QColor(C["warning"]), 2))
        painter.drawLine(x, 0, x, self.height())
        painter.setBrush(QtGui.QColor(C["warning"]))
        painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(x - 6, 0), QtCore.QPoint(x + 6, 0), QtCore.QPoint(x, 10)]))

    def mousePressEvent(self, event):  # noqa: N802
        if self.sequence is None:
            return
        frame = self.x_to_frame(int(event.position().x()))
        if event.button() == QtCore.Qt.RightButton:
            self.contextMenuRequested.emit(event.globalPosition().toPoint())
            return
        if int(event.position().y()) <= self.ruler_height:
            self._dragging_playhead = True
            self.sequence.set_current_frame(frame)
            self.frameChanged.emit(frame)
            self.update()
            return
        row = self.row_at(int(event.position().y()))
        rows = self.tracks_with_rows()
        if 0 <= row < len(rows):
            _kind, _binding, track = rows[row]
            if track is not None and self.select_key_at(frame, track, additive=bool(event.modifiers() & QtCore.Qt.ControlModifier)):
                self._dragging_keys = True
                self._drag_start_frame = frame
                self._drag_last_frame = frame
                return
        self.sequence.set_current_frame(frame)
        self.frameChanged.emit(frame)
        self.update()

    def mouseMoveEvent(self, event):  # noqa: N802
        if self.sequence is None:
            return
        frame = self.x_to_frame(int(event.position().x()))
        if self._dragging_playhead:
            self.sequence.set_current_frame(frame)
            self.frameChanged.emit(frame)
            self.update()
        elif self._dragging_keys:
            delta = frame - self._drag_last_frame
            if delta:
                for track in self.sequence.all_tracks():
                    track.move_selected_keys(delta)
                self._drag_last_frame = frame
                self.keyMoved.emit()
                self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._dragging_playhead = False
        self._dragging_keys = False

    def wheelEvent(self, event):  # noqa: N802
        if event.modifiers() & QtCore.Qt.ControlModifier:
            direction = 1 if event.angleDelta().y() > 0 else -1
            self.set_zoom(self.pixels_per_frame * (1.15 if direction > 0 else 0.85))
            event.accept()
            return
        super().wheelEvent(event)

    def _sync_min_width(self) -> None:
        if self.sequence is None:
            self.setMinimumWidth(400)
        else:
            self.setMinimumWidth(max(640, self.frame_to_x(self.sequence.end_frame) + 80))
