"""KMAP/Level outliner tree."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from src.core.level import KMapProject


class ModuleEditorOutliner(QtWidgets.QTreeWidget):
    itemSelected = QtCore.Signal(str)
    actionRequested = QtCore.Signal(str, str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModuleEditorOutliner")
        self.setHeaderLabels(["KMAP Project"])
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.itemSelectionChanged.connect(self._selection_changed)
        self.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked | QtWidgets.QAbstractItemView.EditKeyPressed)
        self.itemChanged.connect(self._item_changed)
        self._project: KMapProject | None = None

    def set_project(self, project: KMapProject, authored_gameplay_placements=(), authored_room_lights=()) -> None:
        self._project = project
        self.blockSignals(True)
        self.clear()
        root = self._item(project.name, project.project_id, "project")
        root.setExpanded(True)
        self.addTopLevelItem(root)
        modules = self._category("Modules")
        root.addChild(modules)
        for module in project.modules:
            mod_item = self._item(module.module_name, module.module_id, "module")
            modules.addChild(mod_item)
            rooms = self._category("Rooms")
            mod_item.addChild(rooms)
            for room_id in module.rooms:
                room = project.find_room(room_id)
                if room is not None:
                    rooms.addChild(self._item(room.name, room.room_id, "room"))
            woks = self._category("Walkmeshes")
            mod_item.addChild(woks)
            for wok_id in module.walkmeshes:
                wok = project.find_walkmesh(wok_id)
                if wok is not None:
                    woks.addChild(self._item(PathText(wok.source_path, wok.wok_id), wok.wok_id, "walkmesh"))
        loose_rooms = self._category("Loose Rooms")
        root.addChild(loose_rooms)
        module_room_ids = {room_id for module in project.modules for room_id in module.rooms}
        for room in project.rooms:
            if room.room_id not in module_room_ids:
                loose_rooms.addChild(self._item(room.name, room.room_id, "room"))
        for label, rows, kind, key in (
            ("Blueprints", project.blueprints, "blueprint", "blueprint_id"),
            ("Lights", project.lights, "light", "id"),
            ("Cameras", project.cameras, "camera", "id"),
            ("Sequences", project.sequences, "sequence", "id"),
            ("Materials", project.materials, "material", "material_id"),
            ("Textures", project.textures, "texture", "texture_id"),
        ):
            cat = self._category(label)
            root.addChild(cat)
            for row in rows:
                item_id = getattr(row, key, "") if not isinstance(row, dict) else str(row.get(key) or row.get("id") or "")
                name = getattr(row, "name", "") if not isinstance(row, dict) else str(row.get("name") or row.get("resref") or item_id)
                cat.addChild(self._item(name or item_id, item_id, kind))
        authored = self._category("Authored Gameplay")
        root.addChild(authored)
        for placement in authored_gameplay_placements or ():
            placement_id = str(getattr(placement, "placement_id", "") or "")
            kind = str(getattr(placement, "kind", "object") or "object")
            tag = str(getattr(placement, "tag", "") or getattr(placement, "template_resref", "") or placement_id)
            authored.addChild(self._item(f"{kind}: {tag}", placement_id, "authored_gameplay"))
        authored_lights = self._category("Authored Room Lights")
        root.addChild(authored_lights)
        for light in authored_room_lights or ():
            light_id = str(getattr(light, "light_id", "") or "")
            name = str(getattr(light, "name", "") or light_id)
            room = str(getattr(light, "room_resref", "") or "")
            authored_lights.addChild(self._item(f"{name} ({room})", light_id, "authored_room_light"))
        root.addChild(self._category("Validation Issues"))
        self.expandToDepth(1)
        self.blockSignals(False)

    def select_id(self, item_id: str) -> None:
        matches = self.findItems("*", QtCore.Qt.MatchWildcard | QtCore.Qt.MatchRecursive)
        for item in matches:
            if item.data(0, QtCore.Qt.UserRole) == item_id:
                blocked = self.blockSignals(True)
                self.setCurrentItem(item)
                self.blockSignals(blocked)
                break

    def _item(self, text: str, item_id: str, kind: str) -> QtWidgets.QTreeWidgetItem:
        item = QtWidgets.QTreeWidgetItem([text])
        item.setData(0, QtCore.Qt.UserRole, item_id)
        item.setData(0, QtCore.Qt.UserRole + 1, kind)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        return item

    def _category(self, text: str) -> QtWidgets.QTreeWidgetItem:
        item = QtWidgets.QTreeWidgetItem([text])
        item.setData(0, QtCore.Qt.UserRole + 1, "category")
        return item

    def _selection_changed(self) -> None:
        item = self.currentItem()
        if item is None:
            return
        item_id = str(item.data(0, QtCore.Qt.UserRole) or "")
        if item_id:
            self.itemSelected.emit(item_id)

    def _item_changed(self, item: QtWidgets.QTreeWidgetItem, _column: int) -> None:
        item_id = str(item.data(0, QtCore.Qt.UserRole) or "")
        kind = str(item.data(0, QtCore.Qt.UserRole + 1) or "")
        if item_id and kind != "category":
            self.actionRequested.emit("rename", item_id)

    def _context_menu(self, pos: QtCore.QPoint) -> None:
        item = self.itemAt(pos)
        item_id = str(item.data(0, QtCore.Qt.UserRole) or "") if item else ""
        menu = QtWidgets.QMenu(self)
        for action in ("Add Module", "Add Room", "Add Blueprint", "Add Camera", "Add Light", "Duplicate", "Delete", "Focus in Viewport", "Validate Selected", "Reveal Source File"):
            qaction = menu.addAction(action)
            qaction.triggered.connect(lambda _checked=False, text=action: self.actionRequested.emit(text.lower().replace(" ", "_"), item_id))
        menu.exec(self.viewport().mapToGlobal(pos))


def PathText(source_path: str, fallback: str) -> str:
    if not source_path:
        return fallback
    return source_path.replace("\\", "/").rsplit("/", 1)[-1]
