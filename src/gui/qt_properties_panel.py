"""Qt skeleton and properties panels for the GhostRigger migration."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from .qt_theme import C, heading


class QtSkeletonPanel(QtWidgets.QWidget):
    nodeSelected = QtCore.Signal(object)
    nodesSelected = QtCore.Signal(list)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._all_items: dict[QtWidgets.QTreeWidgetItem, object] = {}
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        header = QtWidgets.QHBoxLayout()
        header.addWidget(heading("Skeleton / Nodes"))
        self.count_label = QtWidgets.QLabel("")
        self.count_label.setStyleSheet(f"color:{C['text2']}; font-size:8pt;")
        header.addWidget(self.count_label)
        root.addLayout(header)

        search_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search nodes")
        self.search_edit.textChanged.connect(self._filter)
        clear = QtWidgets.QPushButton("x")
        clear.setProperty("compact", True)
        clear.clicked.connect(self.search_edit.clear)
        search_row.addWidget(self.search_edit)
        search_row.addWidget(clear)
        root.addLayout(search_row)

        action_row = QtWidgets.QHBoxLayout()
        select_all = QtWidgets.QPushButton("Select All Bones")
        select_all.setProperty("compact", True)
        select_all.clicked.connect(self.select_all_nodes)
        clear_sel = QtWidgets.QPushButton("Clear")
        clear_sel.setProperty("compact", True)
        clear_sel.clicked.connect(self.clear_selection)
        self.selection_label = QtWidgets.QLabel("")
        self.selection_label.setStyleSheet(f"color:{C['gold']}; font-size:8pt;")
        action_row.addWidget(select_all)
        action_row.addWidget(clear_sel)
        action_row.addStretch(1)
        action_row.addWidget(self.selection_label)
        root.addLayout(action_row)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Type", "Verts", "Faces"])
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self.tree, 1)

    def load_model(self, model) -> None:
        self.tree.clear()
        self._all_items.clear()
        if not model or not getattr(model, "root_node", None):
            self.count_label.setText("")
            return
        n_nodes = model.node_count() if hasattr(model, "node_count") else 0
        n_mesh = len(model.mesh_nodes()) if hasattr(model, "mesh_nodes") else 0
        self.count_label.setText(f"{n_nodes} nodes  {n_mesh} mesh")
        self._insert_node_iterative(model.root_node)
        self.tree.expandToDepth(0)

    def _insert_node_iterative(self, root_node) -> None:
        icon_map = {
            "trimesh": "[M]",
            "skin": "[S]",
            "danglymesh": "[D]",
            "dummy": "[.]",
            "light": "[L]",
            "emitter": "[E]",
            "lightsaber": "[B]",
            "reference": "[R]",
        }
        stack = [(root_node, None)]
        while stack:
            node, parent_item = stack.pop()
            node_type = getattr(node, "type_label", "")
            icon = icon_map.get(node_type, "*")
            verts = len(getattr(node, "vertices", []) or []) if getattr(node, "is_mesh", False) else ""
            faces = len(getattr(node, "faces", []) or []) if getattr(node, "is_mesh", False) else ""
            item = QtWidgets.QTreeWidgetItem([
                f"{icon} {getattr(node, 'name', '')}",
                str(node_type),
                str(verts),
                str(faces),
            ])
            if parent_item is None:
                self.tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)
            self._all_items[item] = node
            for child in reversed(getattr(node, "children", []) or []):
                stack.append((child, item))

    def _on_selection_changed(self) -> None:
        selected = self.tree.selectedItems()
        self.selection_label.setText(f"{len(selected)} selected" if len(selected) > 1 else "")
        nodes = [self._all_items[item] for item in selected if item in self._all_items]
        if nodes:
            self.nodeSelected.emit(nodes[0])
        if len(nodes) > 1:
            self.nodesSelected.emit(nodes)

    def _filter(self, text: str) -> None:
        needle = text.lower().strip()
        if not needle:
            for item in self._all_items:
                item.setHidden(False)
            return
        for item, node in self._all_items.items():
            name = getattr(node, "name", "").lower()
            item.setHidden(needle not in name)

    def select_all_nodes(self) -> None:
        self.tree.selectAll()

    def clear_selection(self) -> None:
        self.tree.clearSelection()

    def select_node(self, node) -> None:
        for item, candidate in self._all_items.items():
            if candidate is node:
                self.tree.setCurrentItem(item)
                item.setSelected(True)
                break

    def get_selected_nodes(self) -> list:
        return [self._all_items[item] for item in self.tree.selectedItems() if item in self._all_items]


class QtPropertiesPanel(QtWidgets.QWidget):
    positionApplied = QtCore.Signal(object, float, float, float)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._current_node = None
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)
        root.addWidget(heading("Properties"))

        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText("No model loaded.")
        root.addWidget(self.text, 1)

        transform = QtWidgets.QGroupBox("Node Transform (editable)")
        transform.setStyleSheet(f"QGroupBox {{ color:{C['gold']}; }}")
        form = QtWidgets.QGridLayout(transform)
        form.addWidget(QtWidgets.QLabel("Pos:"), 0, 0)
        self.x_spin = self._spin()
        self.y_spin = self._spin()
        self.z_spin = self._spin()
        for col, (label, spin) in enumerate((("X", self.x_spin), ("Y", self.y_spin), ("Z", self.z_spin)), start=1):
            box = QtWidgets.QHBoxLayout()
            box.addWidget(QtWidgets.QLabel(f"{label}:"))
            box.addWidget(spin)
            form.addLayout(box, 0, col)
        apply_button = QtWidgets.QPushButton("Apply Position")
        apply_button.clicked.connect(self._apply_transform)
        form.addWidget(apply_button, 1, 0, 1, 4)
        root.addWidget(transform)

    def _spin(self) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(-100000.0, 100000.0)
        spin.setDecimals(5)
        spin.setSingleStep(0.05)
        return spin

    def _apply_transform(self) -> None:
        node = self._current_node
        if not node:
            return
        x, y, z = self.x_spin.value(), self.y_spin.value(), self.z_spin.value()
        try:
            node.position = (x, y, z)
        finally:
            self.positionApplied.emit(node, x, y, z)

    def show_model(self, model) -> None:
        if not model:
            self.text.setPlainText("No model loaded.")
            return
        mesh_nodes = model.mesh_nodes() if hasattr(model, "mesh_nodes") else []
        all_nodes = model.all_nodes() if hasattr(model, "all_nodes") else []
        bone_nodes = model.bone_nodes() if hasattr(model, "bone_nodes") else []
        textures = model.texture_list() if hasattr(model, "texture_list") else []
        total_verts = sum(len(getattr(node, "vertices", []) or []) for node in mesh_nodes)
        total_faces = sum(len(getattr(node, "faces", []) or []) for node in mesh_nodes)
        lines = [
            f"Model: {getattr(model, 'name', '')}",
            f"Game:  {getattr(getattr(model, 'game_version', ''), 'name', getattr(model, 'game_version', ''))}",
            f"Super: {getattr(model, 'supermodel', '')}",
            f"Type:  {getattr(model, 'classification', '')}",
            "",
            "-- Hierarchy --",
            f"Nodes: {len(all_nodes) if all_nodes else getattr(model, 'node_count', lambda: 0)()}",
            f"Mesh:  {len(mesh_nodes)}",
            f"Bones: {len(bone_nodes)}",
            f"Anims: {len(getattr(model, 'animations', []) or [])}",
            "",
            "-- Geometry --",
            f"Verts: {total_verts:,}",
            f"Faces: {total_faces:,}",
            f"Texs:  {len(textures)}",
            "",
            "-- Textures --",
            *[f"  {tex}" for tex in textures],
        ]
        self.text.setPlainText("\n".join(lines))

    def show_node(self, node) -> None:
        self._current_node = node
        pos = getattr(node, "position", (0.0, 0.0, 0.0))
        rot = getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))
        self.x_spin.setValue(float(pos[0]))
        self.y_spin.setValue(float(pos[1]))
        self.z_spin.setValue(float(pos[2]))
        lines = [
            f"Node:  {getattr(node, 'name', '')}",
            f"Type:  {getattr(node, 'type_label', '')}",
            f"Pos:   ({pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f})",
            f"Rot:   ({rot[0]:.3f}, {rot[1]:.3f}, {rot[2]:.3f}, {rot[3]:.3f})",
        ]
        parent = getattr(node, "parent", None)
        if parent:
            lines.append(f"Parent:{getattr(parent, 'name', '')}")
        if getattr(node, "is_mesh", False):
            lines += [
                "",
                "-- Mesh --",
                f"Verts: {len(getattr(node, 'vertices', []) or []):,}",
                f"Faces: {len(getattr(node, 'faces', []) or []):,}",
                f"Texture: {getattr(node, 'texture', '')}",
            ]
        self.text.setPlainText("\n".join(lines))
