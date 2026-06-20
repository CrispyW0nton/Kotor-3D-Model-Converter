"""Top toolbar for the Sequence Editor."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from src.gui.qt_lib.assets import qt_icon_manager


class SequenceToolbar(QtWidgets.QWidget):
    newSequence = QtCore.Signal()
    openSequence = QtCore.Signal()
    saveSequence = QtCore.Signal()
    saveAsSequence = QtCore.Signal()
    renderSequence = QtCore.Signal()
    addSelectedObject = QtCore.Signal()
    createCamera = QtCore.Signal(str)
    createLight = QtCore.Signal(str)
    addTrack = QtCore.Signal(str)
    addCameraCut = QtCore.Signal()
    setKey = QtCore.Signal()
    addAnimationClip = QtCore.Signal()
    autoKeyChanged = QtCore.Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(4)
        buttons = [
            ("New", "Create a new GhostRigger Level Sequence", self.newSequence, qt_icon_manager.I.NEW_SCENE),
            ("Open", "Open a .grseq sequence", self.openSequence, qt_icon_manager.I.OPEN),
            ("Save", "Save sequence", self.saveSequence, qt_icon_manager.I.SAVE),
            ("Save As", "Save sequence as", self.saveAsSequence, qt_icon_manager.I.SAVE),
            ("Render", "Render image sequence", self.renderSequence, qt_icon_manager.I.CAMERAS),
            ("Add Selected Object", "Bind the selected scene object", self.addSelectedObject, qt_icon_manager.I.SELECTALL),
            ("Add Camera Cut", "Add a camera cut section", self.addCameraCut, qt_icon_manager.I.CAMERA_CINEMATIC),
            ("Key", "Set key at current frame", self.setKey, qt_icon_manager.I.SEQUENCE),
            ("Add Clip", "Add an animation clip key to the selected Animation track", self.addAnimationClip, qt_icon_manager.I.ANIMS),
        ]
        for label, tip, signal, icon_name in buttons:
            btn = QtWidgets.QPushButton(label)
            btn.setIcon(qt_icon_manager.get(icon_name, 18))
            btn.setToolTip(tip)
            btn.clicked.connect(signal.emit)
            if label in {"Save", "Key", "Add Clip"}:
                btn.setProperty("accent", True)
            row.addWidget(btn)
        self.create_camera_btn = QtWidgets.QToolButton()
        self.create_camera_btn.setIcon(qt_icon_manager.get(qt_icon_manager.I.CAMERA_CINEMATIC, 18))
        self.create_camera_btn.setText("Camera")
        self.create_camera_btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.create_camera_btn.setToolTip("Create and bind a scene camera")
        camera_menu = QtWidgets.QMenu(self.create_camera_btn)
        for label, camera_type, icon_name in (
            ("Free Camera", "Free Camera", qt_icon_manager.I.CAMERA_FREE),
            ("Target Camera", "Target Camera", qt_icon_manager.I.CAMERA_TARGET),
            ("Cinematic Camera", "Cinematic Camera", qt_icon_manager.I.CAMERA_CINEMATIC),
        ):
            action = camera_menu.addAction(qt_icon_manager.get(icon_name, 18), label)
            action.triggered.connect(lambda _checked=False, t=camera_type: self.createCamera.emit(t))
        self.create_camera_btn.setMenu(camera_menu)
        self.create_camera_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        row.addWidget(self.create_camera_btn)
        self.create_light_btn = QtWidgets.QToolButton()
        self.create_light_btn.setIcon(qt_icon_manager.get(qt_icon_manager.I.LIGHT_POINT, 18))
        self.create_light_btn.setText("Light")
        self.create_light_btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.create_light_btn.setToolTip("Create and bind a scene light")
        light_menu = QtWidgets.QMenu(self.create_light_btn)
        for label, light_type, icon_name in (
            ("Point Light", "point", qt_icon_manager.I.LIGHT_POINT),
            ("Spot Light", "spot", qt_icon_manager.I.LIGHT_SPOT),
            ("Directional Light", "directional", qt_icon_manager.I.LIGHT_DIRECTIONAL),
            ("Area Light", "area", qt_icon_manager.I.LIGHT_AREA),
            ("Ambient Light", "ambient", qt_icon_manager.I.LIGHT_AMBIENT),
        ):
            action = light_menu.addAction(qt_icon_manager.get(icon_name, 18), label)
            action.triggered.connect(lambda _checked=False, t=light_type: self.createLight.emit(t))
        self.create_light_btn.setMenu(light_menu)
        self.create_light_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        row.addWidget(self.create_light_btn)
        self.track_combo = QtWidgets.QComboBox()
        for track_type in ("Transform", "Camera Property", "Light Property", "Visibility", "Material", "Event", "Rig Control", "Animation", "Sub Sequence"):
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

    def apply_ghost_layout(self, layout) -> None:
        toolbar = layout.toolbar("viewport")
        if self.layout() is not None:
            spacing = layout.spacing_value("toolbarSpacing", 4)
            self.layout().setSpacing(spacing)
            self.layout().setContentsMargins(spacing, spacing, spacing, spacing)
        for button in self.findChildren(QtWidgets.QPushButton):
            button.setMinimumHeight(max(22, toolbar.height - 8))
            button.setIconSize(QtCore.QSize(toolbar.icon_size, toolbar.icon_size))
        for combo in self.findChildren(QtWidgets.QComboBox):
            combo.setMinimumHeight(layout.spacing_value("comboHeight", max(22, toolbar.height - 10)))
