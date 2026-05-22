"""Simple KMAX scene outliner panel."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from src.core.scene.scene_object_instance import SceneObjectInstance
from src.gui.qt_lib.assets.qt_theme import heading


class QtSceneOutlinerPanel(QtWidgets.QWidget):
    objectSelected = QtCore.Signal(str)
    objectDeleteRequested = QtCore.Signal(str)
    objectDuplicateRequested = QtCore.Signal(str)
    objectFocusRequested = QtCore.Signal(str)
    objectVisibilityChanged = QtCore.Signal(str, bool)
    objectLockedChanged = QtCore.Signal(str, bool)
    objectRenamed = QtCore.Signal(str, str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._objects: dict[str, SceneObjectInstance] = {}
        self._item_to_id: dict[QtWidgets.QTreeWidgetItem, str] = {}
        self._suppress = False
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(5)
        root.addWidget(heading("Scene Outliner"))

        self.scene_label = QtWidgets.QLabel("Untitled Scene")
        root.addWidget(self.scene_label)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Object", "Type", "Visible", "Locked"])
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
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
            self.tree.clear()
            self.scene_label.setText(scene.display_name if hasattr(scene, "display_name") else getattr(scene, "name", "Scene"))
            root_item = QtWidgets.QTreeWidgetItem(["Scene", "", "", ""])
            root_item.setExpanded(True)
            self.tree.addTopLevelItem(root_item)

            buckets = {
                "Models": [obj for obj in scene.objects if obj.object_type == "model"],
                "Lights": [obj for obj in scene.objects if obj.object_type == "light"],
                "Cameras": [obj for obj in scene.objects if obj.object_type == "camera"],
                "Helpers": [obj for obj in scene.objects if obj.object_type not in {"model", "light", "camera"}],
            }
            for label, objects in buckets.items():
                bucket = QtWidgets.QTreeWidgetItem([label, "", "", ""])
                bucket.setExpanded(True)
                root_item.addChild(bucket)
                for obj in objects:
                    item = QtWidgets.QTreeWidgetItem([
                        obj.name,
                        obj.object_type,
                        "yes" if obj.visible else "no",
                        "yes" if obj.locked else "no",
                    ])
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
                    item.setData(0, QtCore.Qt.UserRole, obj.id)
                    bucket.addChild(item)
                    self._item_to_id[item] = obj.id
                    if obj.selected:
                        self.tree.setCurrentItem(item)
            for column in range(self.tree.columnCount()):
                self.tree.resizeColumnToContents(column)
        finally:
            self._suppress = False

    def _selected_item(self) -> QtWidgets.QTreeWidgetItem | None:
        item = self.tree.currentItem()
        return item if item in self._item_to_id else None

    def _on_selection_changed(self) -> None:
        if self._suppress:
            return
        item = self._selected_item()
        if item is not None:
            self.objectSelected.emit(self._item_to_id[item])

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
