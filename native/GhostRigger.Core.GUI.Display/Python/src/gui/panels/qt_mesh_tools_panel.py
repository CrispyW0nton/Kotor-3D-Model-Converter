"""Dockable 3ds Max-style Mesh Tools panel."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from src.gui.qt_lib.assets.qt_theme import C, heading
from src.gui.libtheme.collapsible_group import CollapsibleGroupBox
from src.gui.qt_lib.panels.qt_mesh_operation_options import QtMeshOperationOptionsWidget
from src.gui.qt_lib.panels.qt_mesh_selection_toolbar import QtMeshSelectionToolbar
from src.mesh_tools.command_service import execute_mesh_tool_command
from src.mesh_tools.mesh_edit_types import MeshOperationResult, MeshSelectionMode
from src.mesh_tools.mesh_validation import validate_mesh


PRIMITIVES = ("Floor", "Wall", "Cube", "Cylinder", "Arch", "Ramp", "Stairs")
PIVOT_PRESETS = ("Center", "Base", "Origin", "Selected Element", "Selected Face", "Selected Vertex", "Custom")
REFERENCE_MODES = ("World", "Local", "Parent", "Object")


class QtMeshToolsPanel(QtWidgets.QWidget):
    """Dock widget body for GhostRigger editable mesh operations."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("MeshToolsPanel")
        self.setProperty("panelId", "mesh_tools")
        self._viewport = None
        self._status_labels: dict[str, QtWidgets.QLabel] = {}
        self._build()

    def set_viewport(self, viewport) -> None:
        self._viewport = viewport
        viewport.meshSelectionChanged.connect(lambda _nodes: self.refresh())
        viewport.meshSubobjectSelectionChanged.connect(lambda _state: self.refresh())
        self.refresh()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)
        root.addWidget(heading("Mesh Tools"))

        self.selection_toolbar = QtMeshSelectionToolbar(self)
        self.selection_toolbar.modeRequested.connect(self._set_mode)
        root.addWidget(self.selection_toolbar)
        root.addWidget(self._primitive_section())
        root.addWidget(self._selection_tools_section())
        root.addWidget(self._geometry_tools_section())
        self.options_widget = QtMeshOperationOptionsWidget(self)
        root.addWidget(self.options_widget)
        root.addWidget(self._snap_section())
        root.addWidget(self._transform_section())
        root.addWidget(self._pivot_section())
        root.addWidget(self._material_section())
        root.addWidget(self._status_section())
        root.addStretch(1)

    def apply_ghost_theme(self, theme) -> None:
        for value in self._status_labels.values():
            value.setStyleSheet(f"color:{theme.color('text.secondary')};")

    def apply_ghost_layout(self, layout) -> None:
        margin = layout.spacing_value("margin", 4)
        spacing = layout.spacing_value("panelSpacing", 4)
        if self.layout() is not None:
            self.layout().setContentsMargins(margin, margin, margin, margin)
            self.layout().setSpacing(spacing)
        for group in self.findChildren(QtWidgets.QGroupBox):
            group_layout = group.layout()
            if group_layout is not None:
                group_layout.setContentsMargins(
                    layout.spacing_value("groupboxMargin", margin + 4),
                    layout.spacing_value("groupboxMargin", margin + 4),
                    layout.spacing_value("groupboxMargin", margin + 4),
                    layout.spacing_value("groupboxMargin", margin + 4),
                )
                group_layout.setSpacing(layout.spacing_value("groupboxSpacing", spacing))
        button_height = max(22, layout.toolbar("viewport").height - 8)
        for button in self.findChildren(QtWidgets.QPushButton):
            button.setMinimumHeight(button_height)
        for widget in [*self.findChildren(QtWidgets.QSpinBox), *self.findChildren(QtWidgets.QDoubleSpinBox), *self.findChildren(QtWidgets.QComboBox)]:
            widget.setMinimumHeight(layout.spacing_value("inputHeight", 24))

    def _selection_tools_section(self) -> QtWidgets.QGroupBox:
        box = CollapsibleGroupBox("Selection Tools")
        grid = QtWidgets.QGridLayout(box)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(4)
        actions = [
            ("Select All", self._select_all),
            ("Clear Selection", self._clear_selection),
            ("Invert Selection", self._invert_selection),
            ("Grow", self._grow),
            ("Shrink", self._shrink),
            ("Loop", lambda: self._result(self._viewport.mesh_tool_loop_selection() if self._viewport else None)),
            ("Ring", lambda: self._result(self._viewport.mesh_tool_ring_selection() if self._viewport else None)),
            ("Convert To Vertex", lambda: self._convert(MeshSelectionMode.VERTEX)),
            ("Convert To Edge", lambda: self._convert(MeshSelectionMode.EDGE)),
            ("Convert To Border", lambda: self._convert(MeshSelectionMode.BORDER)),
            ("Convert To Face", lambda: self._convert(MeshSelectionMode.FACE)),
            ("Convert To Polygon", lambda: self._convert(MeshSelectionMode.POLYGON)),
            ("Convert To Element", lambda: self._convert(MeshSelectionMode.ELEMENT)),
        ]
        for index, (label, callback) in enumerate(actions):
            button = QtWidgets.QPushButton(label)
            button.setProperty("compact", True)
            button.clicked.connect(callback)
            grid.addWidget(button, index // 2, index % 2)
        return box

    def _primitive_section(self) -> QtWidgets.QGroupBox:
        box = CollapsibleGroupBox("Create")
        box.setObjectName("MeshToolsCreateGroup")
        form = QtWidgets.QFormLayout(box)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(4)
        self.primitive_combo = QtWidgets.QComboBox()
        self.primitive_combo.setObjectName("MeshToolsPrimitiveType")
        self.primitive_combo.addItems(PRIMITIVES)
        self.primitive_name = QtWidgets.QLineEdit()
        self.primitive_name.setObjectName("MeshToolsPrimitiveName")
        self.primitive_name.setPlaceholderText("Name")
        self.primitive_dims = tuple(self._double_spin(1.0, 0.001, 10000.0, 3) for _ in range(3))
        dims = QtWidgets.QHBoxLayout()
        for axis, spin in zip(("X", "Y", "Z"), self.primitive_dims):
            spin.setObjectName(f"MeshToolsDimension{axis}")
            spin.setToolTip(f"{axis} dimension")
            dims.addWidget(spin)
        self.primitive_segments = self._int_spin(12, 1, 128)
        self.primitive_segments.setObjectName("MeshToolsPrimitiveSegments")
        self.primitive_position = tuple(self._double_spin(0.0, -100000.0, 100000.0, 3) for _ in range(3))
        pos = QtWidgets.QHBoxLayout()
        for axis, spin in zip(("X", "Y", "Z"), self.primitive_position):
            spin.setObjectName(f"MeshToolsPosition{axis}")
            spin.setToolTip(f"{axis} position")
            pos.addWidget(spin)
        self.primitive_rotation = tuple(self._double_spin(0.0, -3600.0, 3600.0, 2) for _ in range(3))
        rot = QtWidgets.QHBoxLayout()
        for axis, spin in zip(("X", "Y", "Z"), self.primitive_rotation):
            spin.setObjectName(f"MeshToolsRotation{axis}")
            spin.setToolTip(f"{axis} rotation")
            rot.addWidget(spin)
        self.primitive_scale = tuple(self._double_spin(1.0, 0.001, 1000.0, 3) for _ in range(3))
        scale = QtWidgets.QHBoxLayout()
        for axis, spin in zip(("X", "Y", "Z"), self.primitive_scale):
            spin.setObjectName(f"MeshToolsScale{axis}")
            spin.setToolTip(f"{axis} scale")
            scale.addWidget(spin)
        self.primitive_pivot = QtWidgets.QComboBox()
        self.primitive_pivot.setObjectName("MeshToolsPrimitivePivotPreset")
        self.primitive_pivot.addItems(PIVOT_PRESETS)
        self.primitive_material = QtWidgets.QLineEdit()
        self.primitive_material.setObjectName("MeshToolsPrimitiveMaterial")
        self.primitive_material.setPlaceholderText("default")
        self.primitive_grid_snap = QtWidgets.QCheckBox()
        self.primitive_grid_snap.setObjectName("MeshToolsPrimitiveGridSnap")
        self.primitive_grid_snap.setToolTip("Snap new primitive position to the active grid")
        create_button = QtWidgets.QPushButton("Create Primitive")
        create_button.setObjectName("MeshToolsCreatePrimitiveButton")
        create_button.clicked.connect(self._create_primitive)
        form.addRow("Primitive", self.primitive_combo)
        form.addRow("Name", self.primitive_name)
        form.addRow("Dimensions", dims)
        form.addRow("Segments/Steps", self.primitive_segments)
        form.addRow("Position", pos)
        form.addRow("Rotation", rot)
        form.addRow("Scale", scale)
        form.addRow("Pivot", self.primitive_pivot)
        form.addRow("Material", self.primitive_material)
        form.addRow("Grid Snap", self.primitive_grid_snap)
        form.addRow(create_button)
        return box

    def _geometry_tools_section(self) -> QtWidgets.QGroupBox:
        box = CollapsibleGroupBox("Geometry Tools")
        box.setObjectName("MeshToolsGeometryGroup")
        grid = QtWidgets.QGridLayout(box)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(4)
        actions = [
            ("Attach / Combine", "attach"),
            ("Detach Selection", "detach"),
            ("Weld", "weld"),
            ("Target Weld", "target_weld"),
            ("Bridge", "bridge"),
            ("Connect", "connect"),
            ("Extrude", "extrude"),
            ("Bevel", "bevel"),
            ("Inset", "inset"),
            ("Boolean Cut", "boolean_cut"),
            ("Boolean Union", "boolean_union"),
            ("Boolean Difference", "boolean_difference"),
            ("Cap Border", "cap"),
            ("Delete", "delete"),
            ("Remove Isolated Vertices", "remove_isolated"),
            ("Flip Normals", "flip_normals"),
            ("Recalculate Normals", "recalculate_normals"),
            ("Validate Mesh", "validate_mesh"),
            ("Undo Mesh Edit", "undo"),
            ("Redo Mesh Edit", "redo"),
        ]
        for index, (label, op) in enumerate(actions):
            button = QtWidgets.QPushButton(label)
            button.setObjectName("MeshTools" + "".join(part.title() for part in op.split("_")) + "Button")
            button.setProperty("compact", True)
            button.clicked.connect(lambda _checked=False, operation=op: self._operation(operation))
            grid.addWidget(button, index // 2, index % 2)
        return box

    def _snap_section(self) -> QtWidgets.QGroupBox:
        box = CollapsibleGroupBox("Snap / Grid")
        box.setObjectName("MeshToolsSnapGroup")
        form = QtWidgets.QFormLayout(box)
        form.setContentsMargins(8, 8, 8, 8)
        self.grid_enabled = self._checked_box(True)
        self.grid_enabled.setObjectName("MeshToolsGridEnabled")
        self.grid_size = self._double_spin(1.0, 0.001, 10000.0, 3)
        self.grid_size.setObjectName("MeshToolsGridSize")
        axes = QtWidgets.QHBoxLayout()
        self.snap_x = self._checked_box(True)
        self.snap_y = self._checked_box(True)
        self.snap_z = self._checked_box(True)
        for label, widget in (("X", self.snap_x), ("Y", self.snap_y), ("Z", self.snap_z)):
            widget.setObjectName(f"MeshToolsSnapAxis{label}")
            widget.setText(label)
            axes.addWidget(widget)
        set_grid = QtWidgets.QPushButton("Set Grid")
        set_grid.setObjectName("MeshToolsSetGridButton")
        set_grid.clicked.connect(self._set_grid)
        snap_selected = QtWidgets.QPushButton("Snap Selection")
        snap_selected.setObjectName("MeshToolsSnapSelectionButton")
        snap_selected.clicked.connect(lambda: self._command("snap_to_grid", self._snap_options()))
        form.addRow("Enabled", self.grid_enabled)
        form.addRow("Size", self.grid_size)
        form.addRow("Axes", axes)
        form.addRow(set_grid, snap_selected)
        return box

    def _transform_section(self) -> QtWidgets.QGroupBox:
        box = CollapsibleGroupBox("Transform")
        box.setObjectName("MeshToolsTransformGroup")
        form = QtWidgets.QFormLayout(box)
        form.setContentsMargins(8, 8, 8, 8)
        self.reference_mode = QtWidgets.QComboBox()
        self.reference_mode.setObjectName("MeshToolsReferenceMode")
        self.reference_mode.addItems(REFERENCE_MODES)
        self.transform_position = tuple(self._double_spin(0.0, -100000.0, 100000.0, 3) for _ in range(3))
        self.transform_rotation = tuple(self._double_spin(0.0, -3600.0, 3600.0, 2) for _ in range(3))
        self.transform_scale = tuple(self._double_spin(1.0, 0.001, 1000.0, 3) for _ in range(3))
        apply_button = QtWidgets.QPushButton("Apply Transform")
        apply_button.setObjectName("MeshToolsApplyTransformButton")
        apply_button.clicked.connect(self._apply_transform)
        form.addRow("Reference", self.reference_mode)
        form.addRow("Move", self._axis_row(self.transform_position, "TransformMove"))
        form.addRow("Rotate", self._axis_row(self.transform_rotation, "TransformRotate"))
        form.addRow("Scale", self._axis_row(self.transform_scale, "TransformScale"))
        form.addRow(apply_button)
        return box

    def _pivot_section(self) -> QtWidgets.QGroupBox:
        box = CollapsibleGroupBox("Pivot")
        box.setObjectName("MeshToolsPivotGroup")
        form = QtWidgets.QFormLayout(box)
        form.setContentsMargins(8, 8, 8, 8)
        self.pivot_preset = QtWidgets.QComboBox()
        self.pivot_preset.setObjectName("MeshToolsPivotPreset")
        self.pivot_preset.addItems(PIVOT_PRESETS)
        self.pivot_position = tuple(self._double_spin(0.0, -100000.0, 100000.0, 3) for _ in range(3))
        apply_button = QtWidgets.QPushButton("Apply Pivot")
        apply_button.setObjectName("MeshToolsApplyPivotButton")
        apply_button.clicked.connect(self._apply_pivot)
        form.addRow("Preset", self.pivot_preset)
        form.addRow("Custom", self._axis_row(self.pivot_position, "PivotPosition"))
        form.addRow(apply_button)
        return box

    def _material_section(self) -> QtWidgets.QGroupBox:
        box = CollapsibleGroupBox("Material")
        box.setObjectName("MeshToolsMaterialGroup")
        form = QtWidgets.QFormLayout(box)
        form.setContentsMargins(8, 8, 8, 8)
        self.material_slot = self._int_spin(0, 0, 255)
        self.material_slot.setObjectName("MeshToolsMaterialSlot")
        self.material_name = QtWidgets.QLineEdit()
        self.material_name.setObjectName("MeshToolsMaterialName")
        self.material_name.setPlaceholderText("texture/material resref")
        self.material_slot_count = QtWidgets.QLabel("-")
        self.material_slot_count.setObjectName("MeshToolsMaterialSlotCount")
        assign = QtWidgets.QPushButton("Assign Material")
        assign.setObjectName("MeshToolsAssignMaterialButton")
        assign.clicked.connect(self._assign_material)
        form.addRow("Slots", self.material_slot_count)
        form.addRow("Slot", self.material_slot)
        form.addRow("Material", self.material_name)
        form.addRow(assign)
        return box

    def _status_section(self) -> QtWidgets.QGroupBox:
        box = CollapsibleGroupBox("Status")
        box.setObjectName("MeshToolsStatusGroup")
        form = QtWidgets.QFormLayout(box)
        form.setContentsMargins(8, 8, 8, 8)
        for label, key in [
            ("Active Mesh", "active"),
            ("Selection Mode", "mode"),
            ("Selected Vertices", "vertices"),
            ("Selected Edges", "edges"),
            ("Selected Borders", "borders"),
            ("Selected Faces", "faces"),
            ("Selected Polygons", "polygons"),
            ("Selected Elements", "elements"),
            ("Topology Warnings", "warnings"),
        ]:
            value = QtWidgets.QLabel("-")
            value.setWordWrap(True)
            value.setStyleSheet(f"color:{C['text2']};")
            self._status_labels[key] = value
            form.addRow(label + ":", value)
        return box

    def refresh(self) -> None:
        state = getattr(self._viewport, "mesh_selection_state", None) if self._viewport is not None else None
        mode = getattr(state, "mode", MeshSelectionMode.OBJECT)
        self.selection_toolbar.set_active_mode(mode)
        counts = state.counts() if state is not None else {}
        self._status_labels["active"].setText(str(getattr(state, "active_mesh_id", None) or "-"))
        self._status_labels["mode"].setText(mode.label)
        for key in ("vertices", "edges", "borders", "faces", "polygons", "elements"):
            self._status_labels[key].setText(str(counts.get(key, 0)))
        self._status_labels["warnings"].setText(self._topology_warning_text())

    def _topology_warning_text(self) -> str:
        mesh = self._viewport._active_edit_mesh() if self._viewport is not None and hasattr(self._viewport, "_active_edit_mesh") else None
        if mesh is None:
            return "-"
        report = validate_mesh(mesh)
        parts = []
        if report.non_manifold_edges:
            parts.append(f"{len(report.non_manifold_edges)} non-manifold edge(s)")
        if report.border_edges:
            parts.append(f"{len(report.border_edges)} border edge(s)")
        if report.degenerate_faces:
            parts.append(f"{len(report.degenerate_faces)} degenerate face(s)")
        if report.isolated_vertices:
            parts.append(f"{len(report.isolated_vertices)} isolated vertex/vertices")
        if not parts:
            parts.append("None")
        state = getattr(self._viewport, "mesh_selection_state", None)
        if state is not None and getattr(state, "status_message", ""):
            parts.append(str(state.status_message))
        return "; ".join(parts)

    def _options(self) -> dict:
        return self.options_widget.options()

    def _context(self):
        return self.window() if self.window() is not None else self._viewport

    def _snap_options(self) -> dict:
        return {
            "enabled": bool(self.grid_enabled.isChecked()),
            "grid_size": float(self.grid_size.value()),
            "axes": [axis for axis, widget in (("x", self.snap_x), ("y", self.snap_y), ("z", self.snap_z)) if widget.isChecked()],
        }

    def _primitive_options(self) -> dict:
        primitive = self.primitive_combo.currentText().strip().lower()
        return {
            "name": self.primitive_name.text().strip() or primitive.title(),
            "dimensions": [spin.value() for spin in self.primitive_dims],
            "segments": int(self.primitive_segments.value()),
            "steps": int(self.primitive_segments.value()),
            "position": [spin.value() for spin in self.primitive_position],
            "rotation": [spin.value() for spin in self.primitive_rotation],
            "scale": [spin.value() for spin in self.primitive_scale],
            "pivot_preset": self.primitive_pivot.currentText().strip().lower().replace(" ", "_"),
            "material": self.primitive_material.text().strip(),
            "grid_snap": bool(self.primitive_grid_snap.isChecked()),
            **self._snap_options(),
        }

    def _axis_row(self, widgets, prefix: str) -> QtWidgets.QWidget:
        row = QtWidgets.QWidget(self)
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        for axis, widget in zip(("X", "Y", "Z"), widgets):
            widget.setObjectName(f"MeshTools{prefix}{axis}")
            widget.setToolTip(f"{axis} value")
            layout.addWidget(widget)
        return row

    def _set_mode(self, mode: MeshSelectionMode) -> None:
        if self._viewport is not None:
            self._viewport.set_mesh_selection_mode(mode)

    def _select_all(self) -> None:
        if self._viewport is not None:
            self._viewport.mesh_tool_select_all()

    def _clear_selection(self) -> None:
        if self._viewport is not None:
            self._viewport.mesh_tool_clear_selection()

    def _invert_selection(self) -> None:
        if self._viewport is not None:
            self._viewport.mesh_tool_invert_selection()

    def _grow(self) -> None:
        if self._viewport is not None:
            self._viewport.mesh_tool_grow_selection()

    def _shrink(self) -> None:
        if self._viewport is not None:
            self._viewport.mesh_tool_shrink_selection()

    def _convert(self, mode: MeshSelectionMode) -> None:
        if self._viewport is not None:
            self._result(self._viewport.mesh_tool_convert_selection(mode))

    def _operation(self, operation: str) -> None:
        if operation == "undo":
            if self._viewport is not None and hasattr(self._viewport, "mesh_tool_undo"):
                self._viewport.mesh_tool_undo()
            self.refresh()
            return
        if operation == "redo":
            if self._viewport is not None and hasattr(self._viewport, "mesh_tool_redo"):
                self._viewport.mesh_tool_redo()
            self.refresh()
            return
        if operation == "validate_mesh":
            self._show_command_result(execute_mesh_tool_command(self._context(), {"command": "validate_mesh"}))
            return
        if self._viewport is not None:
            self._result(self._viewport.mesh_tool_operation(operation, self._options()))

    def _command(self, command: str, options: dict | None = None) -> dict:
        result = execute_mesh_tool_command(self._context(), {"command": command, "options": options or {}})
        self._show_command_result(result)
        self.refresh()
        return result

    def _create_primitive(self) -> None:
        primitive = self.primitive_combo.currentText().strip().lower()
        self._command(f"create_{primitive}", self._primitive_options())

    def _set_grid(self) -> None:
        self._command("set_grid", self._snap_options())

    def _apply_transform(self) -> None:
        self._command(
            "set_transform",
            {
                "reference_mode": self.reference_mode.currentText().strip().lower(),
                "position": [spin.value() for spin in self.transform_position],
                "rotation": [spin.value() for spin in self.transform_rotation],
                "scale": [spin.value() for spin in self.transform_scale],
            },
        )

    def _apply_pivot(self) -> None:
        self._command(
            "set_pivot",
            {
                "preset": self.pivot_preset.currentText().strip().lower().replace(" ", "_"),
                "position": [spin.value() for spin in self.pivot_position],
            },
        )

    def _assign_material(self) -> None:
        result = self._command(
            "assign_material",
            {
                "slot": int(self.material_slot.value()),
                "material": self.material_name.text().strip(),
            },
        )
        slot_count = result.get("result", {}).get("material_slot_count")
        if slot_count is not None:
            self.material_slot_count.setText(str(slot_count))

    def _show_command_result(self, result: dict | None) -> None:
        if not isinstance(result, dict):
            return
        if result.get("status") == "error":
            message = str(result.get("message") or "Mesh tool command failed.")
            details = "; ".join(str(item) for item in (result.get("errors") or []))
            QtWidgets.QMessageBox.warning(self, "Mesh Tools", details or message)
        else:
            self._status_labels.get("warnings", QtWidgets.QLabel()).setText(str(result.get("message") or "OK"))

    def _result(self, result: MeshOperationResult | None) -> None:
        if result is not None and not result.success:
            QtWidgets.QMessageBox.warning(self, "Mesh Tools", result.message)
        self.refresh()

    @staticmethod
    def _double_spin(value: float, minimum: float, maximum: float, decimals: int) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setValue(value)
        spin.setSingleStep(10 ** -decimals)
        return spin

    @staticmethod
    def _int_spin(value: int, minimum: int, maximum: int) -> QtWidgets.QSpinBox:
        spin = QtWidgets.QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    @staticmethod
    def _checked_box(value: bool) -> QtWidgets.QCheckBox:
        box = QtWidgets.QCheckBox()
        box.setChecked(value)
        return box
