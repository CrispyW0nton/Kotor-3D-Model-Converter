"""Playback transport controls."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class SequenceTransportBar(QtWidgets.QWidget):
    goStart = QtCore.Signal()
    previousKey = QtCore.Signal()
    playPause = QtCore.Signal()
    nextKey = QtCore.Signal()
    goEnd = QtCore.Signal()
    frameEdited = QtCore.Signal(int)
    loopChanged = QtCore.Signal(bool)
    speedChanged = QtCore.Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(4)
        self.start_btn = self._button("|<", "Go to start", self.goStart)
        self.prev_btn = self._button("<K", "Previous key", self.previousKey)
        self.play_btn = self._button("Play", "Play or pause sequence", self.playPause)
        self.next_btn = self._button("K>", "Next key", self.nextKey)
        self.end_btn = self._button(">|", "Go to end", self.goEnd)
        self.loop_check = QtWidgets.QCheckBox("Loop")
        self.loop_check.setToolTip("Loop playback")
        self.loop_check.toggled.connect(self.loopChanged.emit)
        self.frame_spin = QtWidgets.QSpinBox()
        self.frame_spin.setRange(-1000000, 1000000)
        self.frame_spin.setToolTip("Current frame")
        self.frame_spin.valueChanged.connect(self.frameEdited.emit)
        self.speed_combo = QtWidgets.QComboBox()
        for speed in (0.25, 0.5, 1.0, 2.0):
            self.speed_combo.addItem(f"{speed:g}x", speed)
        self.speed_combo.setCurrentIndex(2)
        self.speed_combo.currentIndexChanged.connect(lambda _i: self.speedChanged.emit(float(self.speed_combo.currentData())))
        for widget in (self.start_btn, self.prev_btn, self.play_btn, self.next_btn, self.end_btn, self.loop_check, QtWidgets.QLabel("Frame"), self.frame_spin, self.speed_combo):
            row.addWidget(widget)
        row.addStretch(1)

    def _button(self, label: str, tooltip: str, signal) -> QtWidgets.QPushButton:
        btn = QtWidgets.QPushButton(label)
        btn.setToolTip(tooltip)
        btn.setFixedHeight(26)
        btn.clicked.connect(signal.emit)
        return btn

    def set_frame_range(self, start: int, end: int) -> None:
        self.frame_spin.setRange(int(start), int(end))

    def set_frame(self, frame: int) -> None:
        with QtCore.QSignalBlocker(self.frame_spin):
            self.frame_spin.setValue(int(frame))

    def set_playing(self, playing: bool) -> None:
        self.play_btn.setText("Pause" if playing else "Play")
