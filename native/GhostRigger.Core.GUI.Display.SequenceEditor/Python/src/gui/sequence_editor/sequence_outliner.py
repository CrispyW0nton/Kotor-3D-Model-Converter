"""Sequence outliner wrapper."""

from __future__ import annotations

from PySide6 import QtWidgets

from .sequence_track_list_widget import SequenceTrackListWidget


class SequenceOutliner(QtWidgets.QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.track_list = SequenceTrackListWidget(self)
        layout.addWidget(self.track_list)

    def set_sequence(self, sequence) -> None:
        self.track_list.set_sequence(sequence)

    def apply_ghost_layout(self, layout) -> None:
        self.track_list.apply_ghost_layout(layout)
