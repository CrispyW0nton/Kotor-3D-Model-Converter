"""KMAX scene outliner panel."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.scene.scene_object_instance import SceneObjectInstance
from src.gui.qt_lib.assets.qt_theme import C, heading


class _SceneOutlinerDelegate(QtWidgets.QStyledItemDelegate):
    """Keeps outliner rows readable when icons and state labels are present."""

    def sizeHint(self, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex) -> QtCore.QSize:  # noqa: N802
        size = super().sizeHint(option, index)
        size.setHeight(max(size.height(), option.fontMetrics.height() + 10, 24))
        return size


class QtSceneOutlinerPanel(QtWidgets.QWidget):
    objectSelected = QtCore.Signal(str)
    helperNodeSelected = QtCore.Signal(object)
    lightNodeSelected = QtCore.Signal(object)
    objectDeleteRequested = QtCore.Signal(str)
    objectDuplicateRequested = QtCore.Signal(str)
    objectFocusRequested = QtCore.Signal(str)
    objectVisibilityChanged = QtCore.Signal(str, bool)
    objectLockedChanged = QtCore.Signal(str, bool)
    objectRenamed = QtCore.Signal(str, str)

    _COLUMNS = ("Object", "Kind", "State", "Children", "Source", "ID")

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._objects: dict[str, SceneObjectInstance] = {}
        self._item_to_id: dict[QtWidgets.QTreeWidgetItem, str] = {}
        self._helper_item_to_node: dict[QtWidgets.QTreeWidgetItem, object] = {}
        self._light_item_to_node: dict[QtWidgets.QTreeWidgetItem, object] = {}
        self._icons: dict[str, QtGui.QIcon] = {}
        self._suppress = False
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(heading("Scene Outliner"))
        self.count_label = QtWidgets.QLabel("")
        self.count_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.count_label.setStyleSheet(f"color:{C['text2']}; font-size:8pt;")
        header.addWidget(self.count_label, 1)
        root.addLayout(header)

        scene_row = QtWidgets.QHBoxLayout()
        scene_row.setSpacing(6)
        self.scene_label = QtWidgets.QLabel("Untitled Scene")
        self.scene_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        scene_row.addWidget(self.scene_label, 1)
        expand_all = QtWidgets.QToolButton()
        expand_all.setText("+")
        expand_all.setToolTip("Expand scene")
        expand_all.clicked.connect(self.tree_expand_all)
        collapse = QtWidgets.QToolButton()
        collapse.setText("-")
        collapse.setToolTip("Collapse to object groups")
        collapse.clicked.connect(self.tree_collapse_to_groups)
        scene_row.addWidget(expand_all)
        scene_row.addWidget(collapse)
        root.addLayout(scene_row)

        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(6)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search scene")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter)
        clear = QtWidgets.QToolButton()
        clear.setToolTip("Clear search")
        clear.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_LineEditClearButton))
        clear.clicked.connect(self.search_edit.clear)
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(clear)
        root.addLayout(search_row)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(len(self._COLUMNS))
        self.tree.setHeaderLabels(list(self._COLUMNS))
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree.setAlternatingRowColors(True)
        self.tree.setIconSize(QtCore.QSize(18, 18))
        self.tree.setIndentation(20)
        self.tree.setItemDelegate(_SceneOutlinerDelegate(self.tree))
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
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        root.addWidget(self.tree, 1)

    def set_scene(self, scene) -> None:
        self._suppress = True
        try:
            self._objects = {obj.id: obj for obj in scene.objects}
            self._item_to_id.clear()
            self._helper_item_to_node.clear()
            self._light_item_to_node.clear()
            self.tree.clear()
            self.scene_label.setText(scene.display_name if hasattr(scene, "display_name") else getattr(scene, "name", "Scene"))
            scene_objects = list(getattr(scene, "objects", []) or [])
            counts = self._scene_counts(scene_objects)
            self.count_label.setText(
                f"{counts['model']} models  {counts['light']} lights  "
                f"{counts['camera']} cameras  {counts['helper']} helpers"
            )
            root_item = QtWidgets.QTreeWidgetItem([
                scene.display_name if hasattr(scene, "display_name") else getattr(scene, "name", "Scene"),
                "Scene",
                "dirty" if bool(getattr(scene, "dirty", False)) else "clean",
                str(len(scene_objects)) if scene_objects else "",
                str(getattr(scene, "game", "") or ""),
                str(getattr(scene, "id", "") or "")[:8],
            ])
            root_item.setIcon(0, self._icon_for_kind("scene"))
            root_item.setExpanded(True)
            self.tree.addTopLevelItem(root_item)

            model_helpers = self._scene_model_helper_nodes(scene_objects)
            model_lights = self._scene_model_light_nodes(scene_objects)
            buckets = {
                "Models": [obj for obj in scene_objects if obj.object_type == "model"],
                "Lights": [obj for obj in scene_objects if obj.object_type == "light"],
                "Cameras": [obj for obj in scene_objects if obj.object_type == "camera"],
                "Helpers": [obj for obj in scene_objects if obj.object_type not in {"model", "light", "camera"}],
            }
            for label, objects in buckets.items():
                bucket_kind = label[:-1].lower() if label.endswith("s") else label.lower()
                bucket = QtWidgets.QTreeWidgetItem([
                    label,
                    "Group",
                    "",
                    str(
                        len(objects)
                        + (len(model_helpers) if label == "Helpers" else 0)
                        + (len(model_lights) if label == "Lights" else 0)
                    ) if objects or (label == "Helpers" and model_helpers) or (label == "Lights" and model_lights) else "",
                    "",
                    "",
                ])
                bucket.setIcon(0, self._icon_for_kind(bucket_kind))
                bucket.setExpanded(True)
                root_item.addChild(bucket)
                for obj in objects:
                    state = self._state_label(obj)
                    child_count = self._object_child_count(obj)
                    item = QtWidgets.QTreeWidgetItem([
                        obj.name,
                        self._kind_label(obj.object_type),
                        state,
                        str(child_count) if child_count else "",
                        self._source_label(obj),
                        obj.id[:8],
                    ])
                    item.setIcon(0, self._icon_for_kind(obj.object_type))
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
                    item.setData(0, QtCore.Qt.UserRole, obj.id)
                    item.setToolTip(0, self._object_tooltip(obj))
                    for column in (3,):
                        item.setTextAlignment(column, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                    if not obj.visible:
                        self._tone_item(item, C["text2"])
                    if obj.locked:
                        item.setForeground(2, QtGui.QBrush(QtGui.QColor(C["warning"])))
                    bucket.addChild(item)
                    self._item_to_id[item] = obj.id
                    if obj.selected:
                        self.tree.setCurrentItem(item)
                if label == "Lights":
                    self._add_model_light_nodes(bucket, model_lights)
                if label == "Helpers":
                    self._add_model_helper_nodes(bucket, model_helpers)
            self._filter(self.search_edit.text())
            self._resize_columns_to_content()
        finally:
            self._suppress = False

    def _selected_item(self) -> QtWidgets.QTreeWidgetItem | None:
        item = self.tree.currentItem()
        return item if item in self._item_to_id else None

    def _on_selection_changed(self) -> None:
        if self._suppress:
            return
        item = self.tree.currentItem()
        if item is None:
            return
        object_id = self._item_to_id.get(item)
        if object_id is None:
            light_node = self._light_item_to_node.get(item)
            if light_node is not None:
                self.lightNodeSelected.emit(light_node)
                return
            helper_node = self._helper_item_to_node.get(item)
            if helper_node is not None:
                self.helperNodeSelected.emit(helper_node)
            return
        if object_id:
            self.objectSelected.emit(object_id)

    def _on_item_changed(self, item: QtWidgets.QTreeWidgetItem, column: int) -> None:
        if self._suppress or item not in self._item_to_id or column != 0:
            return
        name = item.text(0).strip()
        if name:
            self.objectRenamed.emit(self._item_to_id[item], name)

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self.tree.itemAt(pos)
        if item is not None:
            self.tree.setCurrentItem(item)
        selected = self._selected_item()
        if selected is None:
            return
        object_id = self._item_to_id[selected]
        obj = self._objects.get(object_id)
        menu = QtWidgets.QMenu(self)
        focus_action = menu.addAction("Focus in Viewport")
        duplicate_action = menu.addAction("Duplicate")
        visible_action = menu.addAction("Hide" if obj and obj.visible else "Show")
        lock_action = menu.addAction("Unlock" if obj and obj.locked else "Lock")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        chosen = menu.exec(self.tree.mapToGlobal(pos))
        if chosen is focus_action:
            self.objectFocusRequested.emit(object_id)
        elif chosen is duplicate_action:
            self.objectDuplicateRequested.emit(object_id)
        elif chosen is visible_action and obj is not None:
            self.objectVisibilityChanged.emit(object_id, not obj.visible)
        elif chosen is lock_action and obj is not None:
            self.objectLockedChanged.emit(object_id, not obj.locked)
        elif chosen is delete_action:
            self.objectDeleteRequested.emit(object_id)

    def apply_ghost_theme(self, theme) -> None:
        self.scene_label.setStyleSheet(f"color:{theme.color('text.secondary', theme.color('panel.text'))};")
        self.count_label.setStyleSheet(f"color:{theme.color('text.secondary', theme.color('panel.text'))}; font-size:8pt;")
        self.tree.setAlternatingRowColors(True)

    def tree_expand_all(self) -> None:
        self.tree.expandAll()
        self._resize_columns_to_content()

    def tree_collapse_to_groups(self) -> None:
        self.tree.collapseAll()
        self.tree.expandToDepth(1)
        self._resize_columns_to_content()

    def _filter(self, text: str) -> None:
        needle = text.lower().strip()
        if not needle:
            for index in range(self.tree.topLevelItemCount()):
                self._set_item_tree_hidden(self.tree.topLevelItem(index), False)
            return
        for index in range(self.tree.topLevelItemCount()):
            self._filter_item(self.tree.topLevelItem(index), needle)

    def _filter_item(self, item: QtWidgets.QTreeWidgetItem, needle: str) -> bool:
        own_text = " ".join(item.text(column) for column in range(self.tree.columnCount())).lower()
        child_match = False
        for child_index in range(item.childCount()):
            child_match = self._filter_item(item.child(child_index), needle) or child_match
        visible = needle in own_text or child_match
        item.setHidden(not visible)
        if child_match:
            item.setExpanded(True)
        return visible

    def _set_item_tree_hidden(self, item: QtWidgets.QTreeWidgetItem, hidden: bool) -> None:
        item.setHidden(hidden)
        for child_index in range(item.childCount()):
            self._set_item_tree_hidden(item.child(child_index), hidden)

    def _resize_columns_to_content(self) -> None:
        for column in range(1, self.tree.columnCount()):
            self.tree.resizeColumnToContents(column)

    def _scene_counts(self, objects: list[SceneObjectInstance]) -> dict[str, int]:
        counts = {"model": 0, "light": 0, "camera": 0, "helper": 0}
        for obj in objects:
            if obj.object_type in {"model", "light", "camera"}:
                counts[obj.object_type] += 1
            else:
                counts["helper"] += 1
            if obj.object_type == "model":
                counts["helper"] += len(self._model_helper_nodes(obj))
                counts["light"] += len(self._model_light_nodes(obj))
        return counts

    def _kind_label(self, object_type: str) -> str:
        labels = {
            "model": "Model",
            "light": "Light",
            "camera": "Camera",
            "helper": "Helper",
        }
        return labels.get(str(object_type or "").lower(), str(object_type or "Object").title())

    def _state_label(self, obj: SceneObjectInstance) -> str:
        parts = ["visible" if obj.visible else "hidden"]
        if obj.locked:
            parts.append("locked")
        if obj.selected:
            parts.append("selected")
        return ", ".join(parts)

    def _source_label(self, obj: SceneObjectInstance) -> str:
        ref = getattr(obj, "source_ref", None)
        if ref is None:
            return ""
        for attr in ("resref", "original_name", "source_module", "source_archive", "source_path"):
            value = str(getattr(ref, attr, "") or "")
            if value:
                return value
        return str(getattr(ref, "resource_type", "") or "")

    def _object_child_count(self, obj: SceneObjectInstance) -> int:
        metadata = getattr(obj, "metadata", {}) or {}
        for key in ("child_count", "node_count", "children"):
            value = metadata.get(key)
            if isinstance(value, (list, tuple, set, dict)):
                return len(value)
            try:
                if value is not None:
                    return max(0, int(value))
            except (TypeError, ValueError):
                continue
        return 0

    def _object_tooltip(self, obj: SceneObjectInstance) -> str:
        parts = [
            f"Name: {obj.name}",
            f"Kind: {self._kind_label(obj.object_type)}",
            f"State: {self._state_label(obj)}",
        ]
        source = self._source_label(obj)
        if source:
            parts.append(f"Source: {source}")
        if obj.group_id:
            parts.append(f"Group: {obj.group_id}")
        parts.append(f"ID: {obj.id}")
        return "\n".join(parts)

    def _add_model_helper_nodes(
        self,
        helper_bucket: QtWidgets.QTreeWidgetItem,
        helpers: list[tuple[SceneObjectInstance, object]],
    ) -> None:
        for obj, node in helpers:
            child_count = len(getattr(node, "children", []) or [])
            item = QtWidgets.QTreeWidgetItem([
                str(getattr(node, "name", "") or "(unnamed)"),
                "Helper",
                str(getattr(node, "type_label", "") or getattr(node, "node_type", "") or "node"),
                str(child_count) if child_count else "",
                self._source_label(obj),
                str(getattr(node, "index", "") if getattr(node, "index", None) is not None else ""),
            ])
            item.setIcon(0, self._icon_for_kind("helper"))
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
            item.setData(0, QtCore.Qt.UserRole, node)
            item.setToolTip(0, self._helper_tooltip(node, obj))
            item.setTextAlignment(3, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            helper_bucket.addChild(item)
            self._helper_item_to_node[item] = node

    def _add_model_light_nodes(
        self,
        light_bucket: QtWidgets.QTreeWidgetItem,
        lights: list[tuple[SceneObjectInstance, object]],
    ) -> None:
        for obj, node in lights:
            item = QtWidgets.QTreeWidgetItem([
                str(getattr(node, "name", "") or "(unnamed)"),
                "Light",
                self._light_state_label(node),
                "",
                self._source_label(obj),
                str(getattr(node, "index", "") if getattr(node, "index", None) is not None else ""),
            ])
            item.setIcon(0, self._icon_for_kind("light"))
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
            item.setData(0, QtCore.Qt.UserRole, node)
            item.setToolTip(0, self._light_tooltip(node, obj))
            light_bucket.addChild(item)
            self._light_item_to_node[item] = node

    def _scene_model_helper_nodes(self, objects: list[SceneObjectInstance]) -> list[tuple[SceneObjectInstance, object]]:
        helpers: list[tuple[SceneObjectInstance, object]] = []
        for obj in objects:
            if str(getattr(obj, "object_type", "") or "").lower() != "model":
                continue
            helpers.extend((obj, node) for node in self._model_helper_nodes(obj))
        return helpers

    def _scene_model_light_nodes(self, objects: list[SceneObjectInstance]) -> list[tuple[SceneObjectInstance, object]]:
        lights: list[tuple[SceneObjectInstance, object]] = []
        for obj in objects:
            if str(getattr(obj, "object_type", "") or "").lower() != "model":
                continue
            lights.extend((obj, node) for node in self._model_light_nodes(obj))
        return lights

    def _model_helper_nodes(self, obj: SceneObjectInstance) -> list[object]:
        return [node for node in self._model_runtime_nodes(obj) if self._is_helper_node(node)]

    def _model_light_nodes(self, obj: SceneObjectInstance) -> list[object]:
        return [node for node in self._model_runtime_nodes(obj) if self._is_light_node(node)]

    def _model_runtime_nodes(self, obj: SceneObjectInstance) -> list[object]:
        model = (getattr(obj, "metadata", {}) or {}).get("_runtime_model")
        if model is None:
            return []
        root = getattr(model, "root_node", None)
        if hasattr(model, "all_nodes"):
            try:
                nodes = list(model.all_nodes() or [])
            except Exception:
                nodes = []
        else:
            nodes = self._walk_model_nodes(root)
        return [node for node in nodes if node is not root]

    def _walk_model_nodes(self, root) -> list[object]:
        if root is None:
            return []
        nodes: list[object] = []
        stack = [root]
        while stack:
            node = stack.pop()
            nodes.append(node)
            stack.extend(reversed(list(getattr(node, "children", []) or [])))
        return nodes

    def _is_helper_node(self, node) -> bool:
        if (
            bool(getattr(node, "is_mesh", False))
            or bool(getattr(node, "is_skin", False))
            or bool(getattr(node, "is_light", False))
            or bool(getattr(node, "is_camera", False))
        ):
            return False
        type_label = str(getattr(node, "type_label", "") or getattr(node, "node_type", "") or "").strip().lower()
        if type_label in {"dummy", "emitter", "reference", "locator", "helper", "sound", "waypoint", "trigger"}:
            return True
        name = str(getattr(node, "name", "") or "").strip().lower()
        return name.endswith(("_dummy", "_dum", "_helper", "_locator", "_emit", "_emitter", "hook"))

    def _is_light_node(self, node) -> bool:
        if bool(getattr(node, "is_light", False)):
            return True
        type_label = str(getattr(node, "type_label", "") or getattr(node, "node_type", "") or "").strip().lower()
        return type_label == "light"

    def _helper_tooltip(self, node, obj: SceneObjectInstance) -> str:
        parent_name = str(getattr(getattr(node, "parent", None), "name", "") or "")
        parts = [
            f"Name: {getattr(node, 'name', '')}",
            "Kind: Helper",
            f"Type: {getattr(node, 'type_label', getattr(node, 'node_type', 'node'))}",
            f"Owner: {obj.name}",
        ]
        if parent_name:
            parts.append(f"Parent: {parent_name}")
        return "\n".join(parts)

    def _light_state_label(self, node) -> str:
        parts = []
        if bool(getattr(node, "enabled", getattr(node, "light_enabled", True))):
            parts.append("enabled")
        else:
            parts.append("disabled")
        if bool(getattr(node, "visible", True)):
            parts.append("visible")
        else:
            parts.append("hidden")
        return ", ".join(parts)

    def _light_tooltip(self, node, obj: SceneObjectInstance) -> str:
        parts = [
            f"Name: {getattr(node, 'name', '')}",
            "Kind: Light",
            f"Type: {getattr(node, 'light_kind', getattr(node, 'type_label', 'light'))}",
            f"Owner: {obj.name}",
        ]
        radius = getattr(node, "light_radius", getattr(node, "radius", None))
        if radius is not None:
            parts.append(f"Radius: {radius}")
        return "\n".join(parts)

    def _tone_item(self, item: QtWidgets.QTreeWidgetItem, color: str) -> None:
        brush = QtGui.QBrush(QtGui.QColor(color))
        for column in range(self.tree.columnCount()):
            item.setForeground(column, brush)

    def _icon_for_kind(self, kind: str) -> QtGui.QIcon:
        key = str(kind or "object").lower()
        cached = self._icons.get(key)
        if cached is not None:
            return cached
        color_map = {
            "scene": C["accent"],
            "model": C["gold"],
            "light": C["warning"],
            "camera": C["accent2"],
            "helper": C["text2"],
        }
        icon = self._draw_icon(color_map.get(key, C["text2"]), key)
        self._icons[key] = icon
        return icon

    def _draw_icon(self, color: str, key: str) -> QtGui.QIcon:
        pix = QtGui.QPixmap(18, 18)
        pix.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        qcolor = QtGui.QColor(color)
        painter.setPen(QtGui.QPen(qcolor, 1.4))
        painter.setBrush(QtGui.QBrush(qcolor))
        if key == "scene":
            painter.drawRect(3, 4, 12, 10)
            painter.drawLine(3, 7, 15, 7)
        elif key == "model":
            painter.drawPolygon(QtGui.QPolygon([
                QtCore.QPoint(9, 2),
                QtCore.QPoint(15, 6),
                QtCore.QPoint(15, 13),
                QtCore.QPoint(9, 16),
                QtCore.QPoint(3, 13),
                QtCore.QPoint(3, 6),
            ]))
        elif key == "light":
            painter.drawEllipse(5, 3, 8, 8)
            painter.drawLine(9, 12, 9, 16)
            painter.drawLine(6, 15, 12, 15)
        elif key == "camera":
            painter.drawRoundedRect(3, 5, 9, 8, 1, 1)
            painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(12, 8), QtCore.QPoint(16, 5), QtCore.QPoint(16, 13)]))
        else:
            painter.drawEllipse(6, 3, 6, 6)
            painter.drawLine(9, 9, 9, 15)
            painter.drawLine(5, 12, 13, 12)
        painter.end()
        return QtGui.QIcon(pix)
