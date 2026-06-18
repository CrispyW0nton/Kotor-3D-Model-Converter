"""Builder workflow tab."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class BuilderTab(QtWidgets.QWidget):
    actionRequested = QtCore.Signal(str)
    primitivePresetRequested = QtCore.Signal(str, str)
    roomOperationRequested = QtCore.Signal(str, float, float, float, float, float)

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
        operation_box = QtWidgets.QGroupBox("Shape Current Room")
        operation_layout = QtWidgets.QFormLayout(operation_box)
        self.roomOperationComboBox = QtWidgets.QComboBox()
        self.roomOperationComboBox.setObjectName("mapStudioRoomOperationComboBox")
        self.roomOperationComboBox.addItem("Bevel corners", "bevel")
        self.roomOperationComboBox.addItem("Inset footprint", "inset")
        self.roomOperationComboBox.addItem("Rectangular cut", "rectangular_cut")
        self.operationDistanceSpinBox = QtWidgets.QDoubleSpinBox()
        self.operationDistanceSpinBox.setObjectName("mapStudioRoomOperationDistanceSpinBox")
        self.operationDistanceSpinBox.setRange(0.05, 100.0)
        self.operationDistanceSpinBox.setSingleStep(0.05)
        self.operationDistanceSpinBox.setValue(0.25)
        self.operationDistanceSpinBox.setSuffix(" m")
        self.cutCenterXSpinBox = QtWidgets.QDoubleSpinBox()
        self.cutCenterXSpinBox.setObjectName("mapStudioRoomCutCenterXSpinBox")
        self.cutCenterYSpinBox = QtWidgets.QDoubleSpinBox()
        self.cutCenterYSpinBox.setObjectName("mapStudioRoomCutCenterYSpinBox")
        self.cutWidthSpinBox = QtWidgets.QDoubleSpinBox()
        self.cutWidthSpinBox.setObjectName("mapStudioRoomCutWidthSpinBox")
        self.cutDepthSpinBox = QtWidgets.QDoubleSpinBox()
        self.cutDepthSpinBox.setObjectName("mapStudioRoomCutDepthSpinBox")
        for spin in (self.cutCenterXSpinBox, self.cutCenterYSpinBox):
            spin.setRange(-100.0, 100.0)
            spin.setSingleStep(0.25)
            spin.setSuffix(" m")
        for spin in (self.cutWidthSpinBox, self.cutDepthSpinBox):
            spin.setRange(0.05, 100.0)
            spin.setSingleStep(0.25)
            spin.setValue(1.0)
            spin.setSuffix(" m")
        self.applyRoomOperationButton = QtWidgets.QPushButton("Apply Room Operation")
        self.applyRoomOperationButton.setObjectName("mapStudioApplyRoomOperationButton")
        operation_layout.addRow("Operation:", self.roomOperationComboBox)
        operation_layout.addRow("Distance:", self.operationDistanceSpinBox)
        operation_layout.addRow("Cut X:", self.cutCenterXSpinBox)
        operation_layout.addRow("Cut Y:", self.cutCenterYSpinBox)
        operation_layout.addRow("Cut Width:", self.cutWidthSpinBox)
        operation_layout.addRow("Cut Depth:", self.cutDepthSpinBox)
        operation_layout.addRow(self.applyRoomOperationButton)
        layout.addWidget(operation_box)
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
        self.roomOperationComboBox.currentIndexChanged.connect(self._update_operation_controls)
        self.applyRoomOperationButton.clicked.connect(self._emit_room_operation)
        self._update_operation_controls()

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

    def _update_operation_controls(self) -> None:
        operation = str(self.roomOperationComboBox.currentData() or "")
        is_cut = operation == "rectangular_cut"
        for widget in (self.cutCenterXSpinBox, self.cutCenterYSpinBox, self.cutWidthSpinBox, self.cutDepthSpinBox):
            widget.setEnabled(is_cut)
        self.operationDistanceSpinBox.setEnabled(operation in {"bevel", "inset"})

    def _emit_room_operation(self) -> None:
        operation = str(self.roomOperationComboBox.currentData() or "").strip()
        if operation:
            self.roomOperationRequested.emit(
                operation,
                float(self.operationDistanceSpinBox.value()),
                float(self.cutCenterXSpinBox.value()),
                float(self.cutCenterYSpinBox.value()),
                float(self.cutWidthSpinBox.value()),
                float(self.cutDepthSpinBox.value()),
            )
