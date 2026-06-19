"""Sequence properties panel."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class SequencePropertyPanel(QtWidgets.QWidget):
    sequenceChanged = QtCore.Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.sequence = None
        self.target = None
        form = QtWidgets.QFormLayout(self)
        self.name_edit = QtWidgets.QLineEdit()
        self.desc_edit = QtWidgets.QPlainTextEdit()
        self.desc_edit.setMaximumHeight(70)
        self.start_spin = QtWidgets.QSpinBox()
        self.end_spin = QtWidgets.QSpinBox()
        self.rate_combo = QtWidgets.QComboBox()
        for rate in (12, 15, 23.976, 24, 25, 29.97, 30, 48, 50, 59.94, 60):
            self.rate_combo.addItem(str(rate), float(rate))
        for spin in (self.start_spin, self.end_spin):
            spin.setRange(-100000, 1000000)
        form.addRow("Name", self.name_edit)
        form.addRow("Description", self.desc_edit)
        form.addRow("Start", self.start_spin)
        form.addRow("End", self.end_spin)
        form.addRow("Frame Rate", self.rate_combo)
        self.info_label = QtWidgets.QLabel("")
        self.info_label.setWordWrap(True)
        form.addRow("Selection", self.info_label)
        self.name_edit.editingFinished.connect(self.apply)
        self.desc_edit.textChanged.connect(self.apply)
        self.start_spin.valueChanged.connect(lambda _v: self.apply())
        self.end_spin.valueChanged.connect(lambda _v: self.apply())
        self.rate_combo.currentIndexChanged.connect(lambda _v: self.apply())

    def set_sequence(self, sequence) -> None:
        self.sequence = sequence
        self.target = sequence
        self.refresh()

    def set_target(self, target) -> None:
        self.target = target
        self.refresh_info()

    def refresh(self) -> None:
        sequence = self.sequence
        enabled = sequence is not None
        self.setEnabled(enabled)
        if sequence is None:
            return
        with QtCore.QSignalBlocker(self.name_edit), QtCore.QSignalBlocker(self.desc_edit), QtCore.QSignalBlocker(self.start_spin), QtCore.QSignalBlocker(self.end_spin), QtCore.QSignalBlocker(self.rate_combo):
            self.name_edit.setText(sequence.name)
            self.desc_edit.setPlainText(sequence.description)
            self.start_spin.setValue(sequence.start_frame)
            self.end_spin.setValue(sequence.end_frame)
            index = self.rate_combo.findData(float(sequence.frame_rate))
            self.rate_combo.setCurrentIndex(index if index >= 0 else self.rate_combo.findText(str(sequence.frame_rate)))
        self.refresh_info()

    def refresh_info(self) -> None:
        target = self.target
        if target is None:
            self.info_label.setText("")
            return
        pieces = []
        for attr in ("display_name", "name", "track_type", "target_type", "property_name"):
            if hasattr(target, attr):
                value = getattr(target, attr)
                pieces.append(f"{attr}: {getattr(value, 'value', value)}")
        self.info_label.setText("\n".join(pieces))

    def apply(self) -> None:
        sequence = self.sequence
        if sequence is None or not self.isEnabled():
            return
        sequence.name = self.name_edit.text().strip() or "New Sequence"
        sequence.description = self.desc_edit.toPlainText()
        sequence.set_frame_range(int(self.start_spin.value()), int(self.end_spin.value()))
        sequence.frame_rate = float(self.rate_combo.currentData())
        sequence.display_rate = sequence.frame_rate
        sequence.set_current_frame(sequence.current_frame)
        sequence.touch()
        self.sequenceChanged.emit()
