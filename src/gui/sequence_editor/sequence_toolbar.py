"""Top toolbar for the Sequence Editor."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class SequenceToolbar(QtWidgets.QWidget):
    newSequence = QtCore.Signal()
    openSequence = QtCore.Signal()
    saveSequence = QtCore.Signal()
    saveAsSequence = QtCore.Signal()
    renderSequence = QtCore.Signal()
    addSelectedObject = QtCore.Signal()
    addTrack = QtCore.Signal(str)
    addCameraCut = QtCore.Signal()
    setKey = QtCore.Signal()
    autoKeyChanged = QtCore.Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(4)
        buttons = [
            ("New", "Create a new GhostRigger Level Sequence", self.newSequence),
            ("Open", "Open a .grseq sequence", self.openSequence),
            ("Save", "Save sequence", self.saveSequence),
            ("Save As", "Save sequence as", self.saveAsSequence),
            ("Render", "Render image sequence", self.renderSequence),
            ("Add Selected Object", "Bind the selected scene object", self.addSelectedObject),
            ("Add Camera Cut", "Add a camera cut section", self.addCameraCut),
            ("Key", "Set key at current frame", self.setKey),
        ]
        for label, tip, signal in buttons:
            btn = QtWidgets.QPushButton(label)
            btn.setToolTip(tip)
            btn.clicked.connect(signal.emit)
            if label in {"Save", "Key"}:
                btn.setProperty("accent", True)
            row.addWidget(btn)
        self.track_combo = QtWidgets.QComboBox()
        for track_type in ("Transform", "Camera Property", "Light Property", "Visibility", "Material", "Event", "Rig Control", "Character", "Sub Sequence"):
            self.track_combo.addItem(track_type)
        self.add_track_btn = QtWidgets.QPushButton("Add Track")
        self.add_track_btn.setToolTip("Add selected track type to the current binding")
        self.add_track_btn.clicked.connect(lambda: self.addTrack.emit(str(self.track_combo.currentText())))
        self.auto_key = QtWidgets.QCheckBox("Auto Key")
        self.auto_key.setToolTip("Automatically key changed selected properties")
        self.auto_key.toggled.connect(self.autoKeyChanged.emit)
        row.addWidget(self.track_combo)
        row.addWidget(self.add_track_btn)
        row.addWidget(self.auto_key)
        row.addStretch(1)
