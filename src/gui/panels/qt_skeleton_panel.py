"""Qt Skeleton / Nodes browser panel."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.qt_lib.assets.qt_theme import C, heading


class _NodeTreeDelegate(QtWidgets.QStyledItemDelegate):
    """Gives the node browser enough vertical air for icons and dense labels."""

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex) -> QtCore.QSize:  # noqa: N802
        size = super().sizeHint(option, index)
        font_height = option.fontMetrics.height()
        size.setHeight(max(size.height(), font_height + 10, 24))
        return size


class QtSkeletonPanel(QtWidgets.QWidget):
    nodeSelected = QtCore.Signal(object)
    nodesSelected = QtCore.Signal(list)

    _COLUMNS = ("Node", "Role", "Mesh", "Verts", "Faces", "Children", "Attach")

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._all_items: dict[QtWidgets.QTreeWidgetItem, object] = {}
        self._item_icons: dict[str, QtGui.QIcon] = {}
        self._suppress_selection_emit = False
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(heading("Skeleton / Nodes"))
        self.count_label = QtWidgets.QLabel("")
        self.count_label.setStyleSheet(f"color:{C['text2']}; font-size:8pt;")
        self.count_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        header.addWidget(self.count_label)
        root.addLayout(header)

        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(6)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search nodes")
        self.search_edit.textChanged.connect(self._filter)
        self.search_edit.setClearButtonEnabled(True)
        clear = QtWidgets.QToolButton()
        clear.setToolTip("Clear search")
        clear.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_LineEditClearButton))
        clear.clicked.connect(self.search_edit.clear)
        search_row.addWidget(self.search_edit)
        search_row.addWidget(clear, 0)
        root.addLayout(search_row)

        action_row = QtWidgets.QHBoxLayout()
        action_row.setSpacing(6)
        select_all = QtWidgets.QPushButton("Select All Bones")
        select_all.setProperty("compact", True)
        select_all.clicked.connect(self.select_all_nodes)
        clear_sel = QtWidgets.QPushButton("Clear")
        clear_sel.setProperty("compact", True)
        clear_sel.clicked.connect(self.clear_selection)
        expand_all = QtWidgets.QToolButton()
        expand_all.setText("+")
        expand_all.setToolTip("Expand all nodes")
        expand_all.clicked.connect(self.tree_expand_all)
        collapse_all = QtWidgets.QToolButton()
        collapse_all.setText("-")
        collapse_all.setToolTip("Collapse to roots")
        collapse_all.clicked.connect(self.tree_collapse_to_roots)
        self.selection_label = QtWidgets.QLabel("")
        self.selection_label.setStyleSheet(f"color:{C['gold']}; font-size:8pt;")
        action_row.addWidget(select_all)
        action_row.addWidget(clear_sel)
        action_row.addWidget(expand_all)
        action_row.addWidget(collapse_all)
        action_row.addStretch(1)
        action_row.addWidget(self.selection_label)
        root.addLayout(action_row)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(len(self._COLUMNS))
        self.tree.setHeaderLabels(list(self._COLUMNS))
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(False)
        self.tree.setIndentation(20)
        self.tree.setIconSize(QtCore.QSize(18, 18))
        self.tree.setItemDelegate(_NodeTreeDelegate(self.tree))
        self.tree.setTextElideMode(QtCore.Qt.ElideMiddle)
        self.tree.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.tree.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        header_view = self.tree.header()
        header_view.setStretchLastSection(False)
        header_view.setSectionsMovable(True)
        header_view.setDefaultAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        header_view.setMinimumSectionSize(42)
        header_view.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for column in range(1, len(self._COLUMNS)):
            header_view.setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeToContents)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self.tree, 1)

    def load_model(self, model) -> None:
        self._current_model = model
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
        self._resize_columns_to_content()

    def _insert_node_iterative(self, root_node) -> None:
        stack = [(root_node, None)]
        while stack:
            node, parent_item = stack.pop()
            node_type = str(getattr(node, "type_label", "") or "node")
            role = self._node_role(node, node_type)
            mesh_label = self._mesh_label(node, node_type)
            verts = len(getattr(node, "vertices", []) or []) if getattr(node, "is_mesh", False) else ""
            faces = len(getattr(node, "faces", []) or []) if getattr(node, "is_mesh", False) else ""
            children = len(getattr(node, "children", []) or [])
            attachments = self._attachment_count(node)
            item = QtWidgets.QTreeWidgetItem([
                str(getattr(node, "name", "") or "(unnamed)"),
                role,
                mesh_label,
                str(verts),
                str(faces),
                str(children) if children else "",
                str(attachments) if attachments else "",
            ])
            item.setIcon(0, self._icon_for_role(role, node_type))
            item.setToolTip(0, self._node_tooltip(node, node_type, role, children, attachments))
            item.setData(0, QtCore.Qt.UserRole, node)
            for numeric_column in (3, 4, 5, 6):
                item.setTextAlignment(numeric_column, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
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
        if self._suppress_selection_emit:
            return
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
        for index in range(self.tree.topLevelItemCount()):
            self._filter_item(self.tree.topLevelItem(index), needle)

    def tree_expand_all(self) -> None:
        self.tree.expandAll()
        self._resize_columns_to_content()

    def tree_collapse_to_roots(self) -> None:
        self.tree.collapseAll()
        self.tree.expandToDepth(0)
        self._resize_columns_to_content()

    def select_all_nodes(self) -> None:
        self.tree.selectAll()

    def clear_selection(self) -> None:
        self.tree.clearSelection()

    def select_node(self, node, *, emit: bool = True) -> None:
        self._suppress_selection_emit = not emit
        try:
            self.tree.clearSelection()
            if node is None:
                self.selection_label.setText("")
                return
            for item, candidate in self._all_items.items():
                if candidate is node:
                    self.tree.setCurrentItem(item)
                    item.setSelected(True)
                    self.tree.scrollToItem(item)
                    break
        finally:
            self._suppress_selection_emit = False

    def get_selected_nodes(self) -> list:
        return [self._all_items[item] for item in self.tree.selectedItems() if item in self._all_items]

    def _filter_item(self, item: QtWidgets.QTreeWidgetItem, needle: str) -> bool:
        node = self._all_items.get(item)
        own_text = " ".join(item.text(column) for column in range(self.tree.columnCount())).lower()
        if node is not None:
            own_text = f"{own_text} {getattr(node, 'name', '')}".lower()
        child_match = False
        for child_index in range(item.childCount()):
            child_match = self._filter_item(item.child(child_index), needle) or child_match
        own_match = needle in own_text
        visible = own_match or child_match
        item.setHidden(not visible)
        if child_match:
            item.setExpanded(True)
        return visible

    def _resize_columns_to_content(self) -> None:
        for column in range(1, self.tree.columnCount()):
            self.tree.resizeColumnToContents(column)

    def _node_role(self, node, node_type: str) -> str:
        if getattr(node, "is_light", False) or node_type == "light":
            return "Light"
        if getattr(node, "is_emitter", False) or node_type == "emitter":
            return "Emitter"
        if getattr(node, "is_skin", False) or node_type == "skin":
            return "Skin"
        if getattr(node, "is_mesh", False):
            return "Mesh"
        name = str(getattr(node, "name", "") or "").lower()
        if name.endswith("hook") or "hook" in name:
            return "Hook"
        if node_type == "dummy":
            return "Bone"
        return node_type[:1].upper() + node_type[1:] if node_type else "Node"

    def _mesh_label(self, node, node_type: str) -> str:
        if not getattr(node, "is_mesh", False):
            return ""
        if getattr(node, "is_skin", False) or node_type == "skin":
            return "skinned"
        if node_type:
            return node_type
        return "mesh"

    def _attachment_count(self, node) -> int:
        attachments = getattr(node, "_gr_attachments", None)
        if attachments is None:
            attachments = getattr(node, "attachments", None)
        try:
            return len(attachments or [])
        except TypeError:
            return 1 if attachments else 0

    def _node_tooltip(self, node, node_type: str, role: str, children: int, attachments: int) -> str:
        parent = getattr(getattr(node, "parent", None), "name", "")
        parts = [
            f"Name: {getattr(node, 'name', '')}",
            f"Role: {role}",
            f"Type: {node_type}",
        ]
        if parent:
            parts.append(f"Parent: {parent}")
        parts.append(f"Children: {children}")
        if attachments:
            parts.append(f"Attachments: {attachments}")
        return "\n".join(parts)

    def _icon_for_role(self, role: str, node_type: str) -> QtGui.QIcon:
        key = role.lower() or node_type.lower() or "node"
        cached = self._item_icons.get(key)
        if cached is not None:
            return cached
        color_map = {
            "bone": C["accent2"],
            "mesh": C["gold"],
            "skin": C["success"],
            "hook": C["error"],
            "light": C["warning"],
            "emitter": C["accent2"],
        }
        icon = self._draw_node_icon(color_map.get(key, C["text2"]), key)
        self._item_icons[key] = icon
        return icon

    def _draw_node_icon(self, color: str, key: str) -> QtGui.QIcon:
        pix = QtGui.QPixmap(18, 18)
        pix.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        qcolor = QtGui.QColor(color)
        painter.setPen(QtGui.QPen(qcolor, 1.4))
        painter.setBrush(QtGui.QBrush(qcolor))
        if key == "mesh":
            painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(9, 2), QtCore.QPoint(15, 6), QtCore.QPoint(13, 15), QtCore.QPoint(4, 15), QtCore.QPoint(2, 6)]))
        elif key == "skin":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(3, 3, 12, 12)
            painter.drawLine(9, 3, 9, 15)
            painter.drawLine(3, 9, 15, 9)
        elif key == "hook":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawArc(4, 3, 10, 10, 210 * 16, 250 * 16)
            painter.drawLine(10, 12, 14, 16)
        elif key == "light":
            painter.drawEllipse(5, 3, 8, 8)
            painter.drawLine(9, 12, 9, 16)
            painter.drawLine(6, 15, 12, 15)
        elif key == "emitter":
            painter.drawEllipse(7, 7, 4, 4)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(4, 4, 10, 10)
            painter.drawEllipse(1, 1, 16, 16)
        else:
            painter.drawEllipse(6, 3, 6, 6)
            painter.drawLine(9, 9, 9, 15)
            painter.drawLine(5, 12, 13, 12)
        painter.end()
        return QtGui.QIcon(pix)
