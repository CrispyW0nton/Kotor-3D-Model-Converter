"""Dockable 3ds Max-style Mesh Tools panel."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from src.gui.qt_lib.assets.qt_theme import C, heading
from src.gui.qt_lib.panels.qt_mesh_operation_options import QtMeshOperationOptionsWidget
from src.gui.qt_lib.panels.qt_mesh_selection_toolbar import QtMeshSelectionToolbar
from src.mesh_tools.mesh_edit_types import MeshOperationResult, MeshSelectionMode
from src.mesh_tools.mesh_validation import validate_mesh


class QtMeshToolsPanel(QtWidgets.QWidget):
    """Dock widget body for GhostRigger editable mesh operations."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
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
        root.addWidget(self._selection_tools_section())
        root.addWidget(self._geometry_tools_section())
        self.options_widget = QtMeshOperationOptionsWidget(self)
        root.addWidget(self.options_widget)
        root.addWidget(self._status_section(), 1)

    def _selection_tools_section(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Selection Tools")
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

    def _geometry_tools_section(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Geometry Tools")
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
            ("Cap Border", "cap"),
            ("Delete", "delete"),
            ("Remove Isolated Vertices", "remove_isolated"),
            ("Flip Normals", "flip_normals"),
            ("Recalculate Normals", "recalculate_normals"),
        ]
        for index, (label, op) in enumerate(actions):
            button = QtWidgets.QPushButton(label)
            button.setProperty("compact", True)
            button.clicked.connect(lambda _checked=False, operation=op: self._operation(operation))
            grid.addWidget(button, index // 2, index % 2)
        return box

    def _status_section(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox("Status")
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
        if self._viewport is not None:
            self._result(self._viewport.mesh_tool_operation(operation, self._options()))

    def _result(self, result: MeshOperationResult | None) -> None:
        if result is not None and not result.success:
            QtWidgets.QMessageBox.warning(self, "Mesh Tools", result.message)
        self.refresh()
