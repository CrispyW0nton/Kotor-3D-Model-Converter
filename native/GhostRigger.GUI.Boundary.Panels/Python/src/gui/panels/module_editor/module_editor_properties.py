"""Selection properties panel for KMAP objects."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from src.core.level import KMapProject, LevelTransform


class ModuleEditorPropertiesPanel(QtWidgets.QWidget):
    transformChanged = QtCore.Signal(str, object)
    visibilityChanged = QtCore.Signal(str, bool)
    lockChanged = QtCore.Signal(str, bool)
    propertyChanged = QtCore.Signal(str, str, object)
    transitionChanged = QtCore.Signal(str, str, str, int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModuleEditorPropertiesPanel")
        self._project: KMapProject | None = None
        self._authored_placements: dict[str, object] = {}
        self._authored_room_lights: dict[str, object] = {}
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
        self.transition_group = QtWidgets.QGroupBox("Transition")
        self.transition_group.setObjectName("mapStudioTransitionPropertiesGroup")
        transition_layout = QtWidgets.QFormLayout(self.transition_group)
        self.transition_linked_to_edit = QtWidgets.QLineEdit()
        self.transition_linked_to_edit.setObjectName("mapStudioTransitionLinkedToLineEdit")
        self.transition_linked_to_edit.setPlaceholderText("destination tag or waypoint")
        self.transition_module_edit = QtWidgets.QLineEdit()
        self.transition_module_edit.setObjectName("mapStudioTransitionLinkedModuleLineEdit")
        self.transition_module_edit.setPlaceholderText("optional module resref")
        self.transition_destination_spin = QtWidgets.QSpinBox()
        self.transition_destination_spin.setObjectName("mapStudioTransitionDestinationSpinBox")
        self.transition_destination_spin.setRange(0, 32767)
        transition_layout.addRow("Linked To", self.transition_linked_to_edit)
        transition_layout.addRow("Module", self.transition_module_edit)
        transition_layout.addRow("Destination", self.transition_destination_spin)
        root.addWidget(self.transition_group)
        root.addStretch(1)
        self.name_edit.editingFinished.connect(self._name_changed)
        self.visible_box.toggled.connect(lambda value: self.visibilityChanged.emit(self._item_id, value))
        self.locked_box.toggled.connect(lambda value: self.lockChanged.emit(self._item_id, value))
        for spin in (*self.position, *self.rotation, *self.scale):
            spin.valueChanged.connect(lambda _value: self._transform_changed())
        self.transition_linked_to_edit.editingFinished.connect(self._transition_changed)
        self.transition_module_edit.editingFinished.connect(self._transition_changed)
        self.transition_destination_spin.valueChanged.connect(lambda _value: self._transition_changed())
        self.transition_group.setVisible(False)

    def set_project(self, project: KMapProject, authored_gameplay_placements=(), authored_room_lights=()) -> None:
        self._project = project
        self._authored_placements = {
            str(getattr(row, "placement_id", "") or ""): row
            for row in authored_gameplay_placements or ()
            if str(getattr(row, "placement_id", "") or "")
        }
        self._authored_room_lights = {
            str(getattr(row, "light_id", "") or ""): row
            for row in authored_room_lights or ()
            if str(getattr(row, "light_id", "") or "")
        }

    def set_selection(self, item_id: str) -> None:
        self._item_id = item_id
        project = self._project
        item = (project.find_room(item_id) or project.find_module(item_id) or project.find_blueprint(item_id)) if project else None
        authored = self._authored_placements.get(item_id)
        authored_light = self._authored_room_lights.get(item_id)
        self.setEnabled(item is not None or authored is not None or authored_light is not None)
        if item is None and authored is None and authored_light is None:
            self.title.setText("No Selection")
            self.transition_group.setVisible(False)
            return
        self.blockSignals(True)
        for widget in (self.name_edit, self.visible_box, self.locked_box, *self.position, *self.rotation, *self.scale):
            widget.setEnabled(True)
        self.transition_group.setVisible(False)
        if authored is not None:
            kind = str(getattr(authored, "kind", "object") or "object").title()
            tag = str(getattr(authored, "tag", "") or getattr(authored, "template_resref", "") or item_id)
            is_spatial = bool(getattr(authored, "is_spatial", True))
            self.title.setText(f"Authored {kind} Placement")
            self.name_edit.setText(tag)
            self.name_edit.setEnabled(True)
            scope = "spatial placement" if is_spatial else "module-level resource"
            self.source_label.setText(
                f"{str(getattr(authored, 'template_resref', '') or '(no template)')} "
                f"[{str(getattr(authored, 'kind', 'object') or 'object')}; {scope}]"
            )
            self.visible_box.setChecked(True)
            self.locked_box.setChecked(False)
            self.visible_box.setEnabled(False)
            self.locked_box.setEnabled(False)
            self._set_vector(self.position, getattr(authored, "position", (0.0, 0.0, 0.0)))
            self._set_vector(self.rotation, (0.0, 0.0, float(getattr(authored, "bearing", 0.0) or 0.0)))
            self._set_vector(self.scale, (1.0, 1.0, 1.0))
            for spin in (*self.position, *self.rotation):
                spin.setEnabled(is_spatial)
            for spin in self.scale:
                spin.setEnabled(False)
            transition_capable = bool(getattr(authored, "transition_capable", False))
            self.transition_group.setVisible(transition_capable)
            self.transition_linked_to_edit.setText(str(getattr(authored, "linked_to", "") or ""))
            self.transition_module_edit.setText(str(getattr(authored, "linked_to_module", "") or ""))
            self.transition_destination_spin.setValue(int(getattr(authored, "transition_destination", 0) or 0))
            self.blockSignals(False)
            return
        if authored_light is not None:
            self.title.setText("Authored Room Light")
            self.name_edit.setText(str(getattr(authored_light, "name", "") or item_id))
            self.name_edit.setEnabled(True)
            self.source_label.setText(
                f"{getattr(authored_light, 'light_type', 'point')} in {getattr(authored_light, 'room_resref', '')}; "
                f"radius {float(getattr(authored_light, 'radius', 0.0) or 0.0):.2f}, "
                f"intensity {float(getattr(authored_light, 'intensity', 0.0) or 0.0):.2f}"
            )
            self.visible_box.setChecked(True)
            self.locked_box.setChecked(False)
            self.visible_box.setEnabled(False)
            self.locked_box.setEnabled(False)
            self._set_vector(self.position, getattr(authored_light, "position", (0.0, 0.0, 0.0)))
            self._set_vector(self.rotation, (0.0, 0.0, 0.0))
            self._set_vector(self.scale, (1.0, 1.0, 1.0))
            for spin in (*self.rotation, *self.scale):
                spin.setEnabled(False)
            self.blockSignals(False)
            return
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
        self.transition_group.setVisible(False)
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

    def _transition_changed(self) -> None:
        if self.signalsBlocked() or not self._item_id or not self.transition_group.isVisible():
            return
        self.transitionChanged.emit(
            self._item_id,
            self.transition_linked_to_edit.text().strip(),
            self.transition_module_edit.text().strip(),
            int(self.transition_destination_spin.value()),
        )
