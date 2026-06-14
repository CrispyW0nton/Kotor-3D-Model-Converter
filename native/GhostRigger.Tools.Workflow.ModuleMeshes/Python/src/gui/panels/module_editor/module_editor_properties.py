"""Selection properties panel for KMAP objects."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from src.core.level import KMapProject, LevelTransform


class ModuleEditorPropertiesPanel(QtWidgets.QWidget):
    transformChanged = QtCore.Signal(str, object)
    visibilityChanged = QtCore.Signal(str, bool)
    lockChanged = QtCore.Signal(str, bool)
    propertyChanged = QtCore.Signal(str, str, object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModuleEditorPropertiesPanel")
        self._project: KMapProject | None = None
        self._item_id = ""
        root = QtWidgets.QVBoxLayout(self)
        self.title = QtWidgets.QLabel("No Selection")
        self.title.setProperty("heading", True)
        root.addWidget(self.title)
        self.form = QtWidgets.QFormLayout()
        root.addLayout(self.form)
        self.name_edit = QtWidgets.QLineEdit()
        self.form.addRow("Name", self.name_edit)
        self.source_label = QtWidgets.QLabel("")
        self.form.addRow("Source", self.source_label)
        self.visible_box = QtWidgets.QCheckBox("Visible")
        self.locked_box = QtWidgets.QCheckBox("Locked")
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.visible_box)
        row.addWidget(self.locked_box)
        self.form.addRow("State", row)
        self.position = self._vector_row("Position")
        self.rotation = self._vector_row("Rotation")
        self.scale = self._vector_row("Scale")
        root.addStretch(1)
        self.name_edit.editingFinished.connect(self._name_changed)
        self.visible_box.toggled.connect(lambda value: self.visibilityChanged.emit(self._item_id, value))
        self.locked_box.toggled.connect(lambda value: self.lockChanged.emit(self._item_id, value))
        for spin in (*self.position, *self.rotation, *self.scale):
            spin.valueChanged.connect(lambda _value: self._transform_changed())

    def set_project(self, project: KMapProject) -> None:
        self._project = project

    def set_selection(self, item_id: str) -> None:
        self._item_id = item_id
        project = self._project
        item = (project.find_room(item_id) or project.find_module(item_id) or project.find_blueprint(item_id)) if project else None
        self.setEnabled(item is not None)
        if item is None:
            self.title.setText("No Selection")
            return
        self.blockSignals(True)
        kind = "Blueprint" if hasattr(item, "blueprint_id") else "Room" if hasattr(item, "room_id") else "Module"
        self.title.setText(f"{kind} Properties")
        self.name_edit.setText(getattr(item, "name", getattr(item, "module_name", "")))
        self.source_label.setText(getattr(item, "source_path", getattr(item, "source_module", getattr(item, "template_resref", ""))) or "")
        self.visible_box.setChecked(bool(getattr(item, "visible", True)))
        self.locked_box.setChecked(bool(getattr(item, "locked", False)))
        transform = getattr(item, "transform", None)
        if transform is None:
            transform = LevelTransform(position=getattr(item, "position", (0.0, 0.0, 0.0)), rotation=getattr(item, "rotation", (0.0, 0.0, 0.0)))
        self._set_vector(self.position, transform.position)
        self._set_vector(self.rotation, transform.rotation)
        self._set_vector(self.scale, transform.scale)
        self.blockSignals(False)

    def _vector_row(self, label: str) -> tuple[QtWidgets.QDoubleSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QDoubleSpinBox]:
        boxes = tuple(QtWidgets.QDoubleSpinBox() for _ in range(3))
        row = QtWidgets.QHBoxLayout()
        for box in boxes:
            box.setRange(-1000000.0, 1000000.0)
            box.setDecimals(3)
            box.setSingleStep(1.0)
            row.addWidget(box)
        self.form.addRow(label, row)
        return boxes

    @staticmethod
    def _set_vector(boxes, values) -> None:
        for box, value in zip(boxes, values):
            box.setValue(float(value))

    def _vector(self, boxes) -> tuple[float, float, float]:
        return tuple(float(box.value()) for box in boxes)  # type: ignore[return-value]

    def _transform_changed(self) -> None:
        if self.signalsBlocked() or not self._item_id:
            return
        self.transformChanged.emit(
            self._item_id,
            LevelTransform(position=self._vector(self.position), rotation=self._vector(self.rotation), scale=self._vector(self.scale)),
        )

    def _name_changed(self) -> None:
        if self._item_id:
            self.propertyChanged.emit(self._item_id, "name", self.name_edit.text().strip())
