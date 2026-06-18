"""Builder workflow tab."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class BuilderTab(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)
    primitivePresetRequested = QtCore.Signal(str, str)

    ACTIONS = (
        "Create grdev01 Dev Room",
        "Generate Module Files",
        "Validate Module",
        "Open Output",
        "Build ERF/RIM Preview",
        "Build Loose Override Package",
        "Generate Manifest",
    )

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        primitive_box = QtWidgets.QGroupBox("Authored Room Primitive")
        primitive_layout = QtWidgets.QFormLayout(primitive_box)
        self.moduleRootLineEdit = QtWidgets.QLineEdit("grdev01")
        self.moduleRootLineEdit.setObjectName("mapStudioModuleRootLineEdit")
        self.moduleRootLineEdit.setPlaceholderText("module resref, e.g. grdev01")
        self.roomPrimitivePresetComboBox = QtWidgets.QComboBox()
        self.roomPrimitivePresetComboBox.setObjectName("mapStudioRoomPrimitivePresetComboBox")
        self.roomPrimitiveDescriptionLabel = QtWidgets.QLabel("Choose a primitive room preset to seed a new authored module.")
        self.roomPrimitiveDescriptionLabel.setObjectName("mapStudioRoomPrimitiveDescriptionLabel")
        self.roomPrimitiveDescriptionLabel.setWordWrap(True)
        self.createPrimitiveButton = QtWidgets.QPushButton("Create Authored Room Primitive")
        self.createPrimitiveButton.setObjectName("mapStudioCreatePrimitiveRoomButton")
        primitive_layout.addRow("Module:", self.moduleRootLineEdit)
        primitive_layout.addRow("Primitive:", self.roomPrimitivePresetComboBox)
        primitive_layout.addRow(self.roomPrimitiveDescriptionLabel)
        primitive_layout.addRow(self.createPrimitiveButton)
        layout.addWidget(primitive_box)
        for label in self.ACTIONS:
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self.actionRequested.emit(text))
            layout.addWidget(button)
        self.note = QtWidgets.QLabel("KOTOR archive writing is experimental; preview manifests are generated first.")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        layout.addStretch(1)
        self.roomPrimitivePresetComboBox.currentIndexChanged.connect(self._update_preset_description)
        self.createPrimitiveButton.clicked.connect(self._emit_primitive_preset)

    def set_primitive_presets(self, presets) -> None:
        """Populate the primitive preset selector from the controller."""

        self.roomPrimitivePresetComboBox.clear()
        for preset in presets or ():
            preset_id = str(getattr(preset, "preset_id", "") or "")
            label = str(getattr(preset, "label", "") or preset_id)
            description = str(getattr(preset, "description", "") or "")
            self.roomPrimitivePresetComboBox.addItem(label, {"preset_id": preset_id, "description": description})
        self._update_preset_description()

    def _current_preset_data(self) -> dict:
        data = self.roomPrimitivePresetComboBox.currentData()
        return dict(data) if isinstance(data, dict) else {}

    def _update_preset_description(self) -> None:
        data = self._current_preset_data()
        description = data.get("description") or "Choose a primitive room preset to seed a new authored module."
        self.roomPrimitiveDescriptionLabel.setText(str(description))

    def _emit_primitive_preset(self) -> None:
        data = self._current_preset_data()
        preset_id = str(data.get("preset_id") or "").strip()
        module_root = self.moduleRootLineEdit.text().strip() or "grdev01"
        if preset_id:
            self.primitivePresetRequested.emit(preset_id, module_root)
