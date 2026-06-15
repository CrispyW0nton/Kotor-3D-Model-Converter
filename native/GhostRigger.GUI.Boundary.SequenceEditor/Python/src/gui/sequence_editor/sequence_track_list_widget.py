"""Track hierarchy tree for the Sequence Editor."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from src.sequence.sequence_binding import SequenceTargetType
from src.sequence.sequence_model import GhostRiggerLevelSequence
from src.sequence.tracks.camera_property_track import CAMERA_PROPERTIES
from src.sequence.tracks.character_track import CharacterTrack
from src.sequence.tracks.light_property_track import LIGHT_PROPERTIES
from src.sequence.tracks.transform_property_track import TRANSFORM_PROPERTY_LABELS


class SequenceTrackListWidget(QtWidgets.QTreeWidget):
    trackSelected = QtCore.Signal(object)
    bindingSelected = QtCore.Signal(object)
    addSelectedObjectRequested = QtCore.Signal()
    addTrackRequested = QtCore.Signal(str)
    addCameraCutRequested = QtCore.Signal()
    addAnimationClipRequested = QtCore.Signal()
    addOverlappingAnimationRequested = QtCore.Signal()
    deleteSelectionRequested = QtCore.Signal()
    hierarchyChanged = QtCore.Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.sequence: GhostRiggerLevelSequence | None = None
        self._row_height = 26
        self._header_height = 24
        self._expanded_item_keys: set[tuple[str, str]] = set()
        self._refreshing = False
        self.setHeaderLabels(["Sequence", "Type"])
        self.setAlternatingRowColors(True)
        self.setUniformRowHeights(True)
        self._apply_row_height()
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemExpanded.connect(lambda item: self._on_item_expanded_changed(item, True))
        self.itemCollapsed.connect(lambda item: self._on_item_expanded_changed(item, False))

    def apply_ghost_layout(self, layout) -> None:
        self._row_height = max(18, layout.spacing_value("tableRowHeight", self._row_height))
        self._header_height = max(20, layout.spacing_value("panelHeaderHeight", self._header_height))
        self._apply_row_height()

    def _apply_row_height(self) -> None:
        self.setStyleSheet(f"QTreeWidget::item {{ height: {int(self._row_height)}px; }}")
        self.header().setFixedHeight(int(self._header_height))

    def set_sequence(self, sequence: GhostRiggerLevelSequence | None) -> None:
        self.sequence = sequence
        self.refresh()

    def refresh(self) -> None:
        self._capture_expanded_item_keys()
        self._refreshing = True
        self.clear()
        if self.sequence is None:
            self._refreshing = False
            return
        master = QtWidgets.QTreeWidgetItem(["Master Tracks", ""])
        master.setData(0, QtCore.Qt.UserRole, ("master", "master"))
        self._configure_item(master)
        master_expanded = bool(self.sequence.metadata.get("master_tracks_expanded", ("master", "master") in self._expanded_item_keys or True))
        self.addTopLevelItem(master)
        for track in self.sequence.master_tracks:
            item = QtWidgets.QTreeWidgetItem([track.name, self._track_type_label(track)])
            item.setData(0, QtCore.Qt.UserRole, ("track", track.track_id))
            self._configure_item(item)
            master.addChild(item)
        master.setExpanded(master_expanded)
        for binding in self.sequence.bindings:
            warning = " ! Missing" if binding.missing else ""
            target_type = binding.target_type.value if isinstance(binding.target_type, SequenceTargetType) else str(binding.target_type)
            item = QtWidgets.QTreeWidgetItem([f"{binding.display_name}{warning}", target_type])
            item.setData(0, QtCore.Qt.UserRole, ("binding", binding.binding_id))
            self._configure_item(item)
            binding_key = ("binding", binding.binding_id)
            expanded = bool(binding.metadata.get("expanded", binding_key in self._expanded_item_keys or not binding.missing))
            self.addTopLevelItem(item)
            for track in binding.tracks:
                track_item = QtWidgets.QTreeWidgetItem([track.name, self._track_type_label(track)])
                track_item.setData(0, QtCore.Qt.UserRole, ("track", track.track_id))
                self._configure_item(track_item)
                item.addChild(track_item)
            item.setExpanded(expanded)
        self.resizeColumnToContents(0)
        self._refreshing = False

    def header_height(self) -> int:
        return int(self._header_height)

    @staticmethod
    def _track_type_label(track) -> str:
        track_type = str(getattr(track, "track_type", "") or "")
        return "Animation" if track_type == "Character" else track_type

    def row_height(self) -> int:
        return int(self._row_height)

    def _configure_item(self, item: QtWidgets.QTreeWidgetItem) -> None:
        size = QtCore.QSize(0, int(self._row_height))
        item.setSizeHint(0, size)
        item.setSizeHint(1, size)

    def _capture_expanded_item_keys(self) -> None:
        keys: set[tuple[str, str]] = set()
        root = self.invisibleRootItem()
        stack = [root.child(i) for i in range(root.childCount())]
        while stack:
            item = stack.pop()
            data = item.data(0, QtCore.Qt.UserRole)
            if isinstance(data, tuple) and len(data) == 2 and item.isExpanded():
                keys.add((str(data[0]), str(data[1])))
            stack.extend(item.child(i) for i in range(item.childCount()))
        self._expanded_item_keys = keys

    def _on_item_expanded_changed(self, item: QtWidgets.QTreeWidgetItem, expanded: bool) -> None:
        if self._refreshing or self.sequence is None:
            return
        data = item.data(0, QtCore.Qt.UserRole)
        if not isinstance(data, tuple) or len(data) != 2:
            return
        kind, value = str(data[0]), str(data[1])
        key = (kind, value)
        if expanded:
            self._expanded_item_keys.add(key)
        else:
            self._expanded_item_keys.discard(key)
        if kind == "master":
            self.sequence.metadata["master_tracks_expanded"] = bool(expanded)
        elif kind == "binding":
            binding = self.sequence.binding_by_id(value)
            if binding is not None:
                binding.metadata["expanded"] = bool(expanded)
        self.hierarchyChanged.emit()

    def selected_track(self):
        if self.sequence is None:
            return None
        item = self.currentItem()
        if item is None:
            return None
        kind_id = item.data(0, QtCore.Qt.UserRole)
        if not kind_id or kind_id[0] != "track":
            return None
        track_id = kind_id[1]
        return next((track for track in self.sequence.all_tracks() if track.track_id == track_id), None)

    def selected_binding(self):
        if self.sequence is None:
            return None
        item = self.currentItem()
        if item is None:
            return None
        kind_id = item.data(0, QtCore.Qt.UserRole)
        if not kind_id:
            return None
        if kind_id[0] == "binding":
            return self.sequence.binding_by_id(kind_id[1])
        if kind_id[0] == "track":
            track = self.selected_track()
            return self.sequence.binding_by_id(track.parent_binding_id) if track is not None else None
        return None

    def _on_selection_changed(self) -> None:
        track = self.selected_track()
        binding = self.selected_binding()
        if track is not None:
            self.trackSelected.emit(track)
        if binding is not None:
            self.bindingSelected.emit(binding)

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        if self.sequence is None:
            return
        item = self.itemAt(pos)
        if item is not None:
            self.setCurrentItem(item)
        kind_id = item.data(0, QtCore.Qt.UserRole) if item is not None else None
        is_binding = bool(kind_id and kind_id[0] == "binding")
        is_track = bool(kind_id and kind_id[0] == "track")
        binding = self.selected_binding()
        menu = QtWidgets.QMenu(self)
        add_object = menu.addAction("Add Selected Scene Object")
        add_cut = menu.addAction("Add Camera Cut")
        track_menu = menu.addMenu("Add Track")
        for track_type in ("Transform", "Visibility", "Material", "Event", "Rig Control", "Animation", "Sub Sequence"):
            action = track_menu.addAction(track_type)
            action.setData(track_type)
        transform_menu = menu.addMenu("Add Transform Lane")
        for property_name, label in TRANSFORM_PROPERTY_LABELS.items():
            action = transform_menu.addAction(label)
            action.setData(f"Transform Property:{property_name}")
        camera_menu = menu.addMenu("Add Camera Lane")
        for property_name in sorted(CAMERA_PROPERTIES):
            action = camera_menu.addAction(property_name.replace("_", " ").title())
            action.setData(f"Camera Property:{property_name}")
        light_menu = menu.addMenu("Add Light Lane")
        for property_name in sorted(LIGHT_PROPERTIES):
            action = light_menu.addAction(property_name.replace("_", " ").title())
            action.setData(f"Light Property:{property_name}")
        target_type = getattr(binding, "target_type", None)
        target_value = target_type.value if hasattr(target_type, "value") else str(target_type or "")
        transform_menu.setEnabled(binding is not None)
        camera_menu.setEnabled(binding is not None and target_value == SequenceTargetType.CAMERA.value)
        light_menu.setEnabled(binding is not None and target_value == SequenceTargetType.LIGHT.value)
        track_menu.setEnabled(binding is not None or item is None or not is_track)
        if is_track or is_binding:
            menu.addSeparator()
        add_clip_action = menu.addAction("Add Animation Clip...")
        selected_track = self.selected_track()
        add_clip_action.setEnabled(isinstance(selected_track, CharacterTrack))
        add_overlap_action = menu.addAction("Add Overlapping Animation...")
        add_overlap_action.setEnabled(isinstance(selected_track, CharacterTrack))
        delete_action = menu.addAction("Delete Track" if is_track else "Delete Object Binding")
        delete_action.setEnabled(is_track or is_binding)
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is add_object:
            self.addSelectedObjectRequested.emit()
        elif chosen is add_cut:
            self.addCameraCutRequested.emit()
        elif chosen is add_clip_action:
            self.addAnimationClipRequested.emit()
        elif chosen is add_overlap_action:
            self.addOverlappingAnimationRequested.emit()
        elif chosen is delete_action:
            self.deleteSelectionRequested.emit()
        elif chosen in track_menu.actions():
            track_type = str(chosen.data() or "")
            if track_type:
                self.addTrackRequested.emit(track_type)
        elif chosen in transform_menu.actions() or chosen in camera_menu.actions() or chosen in light_menu.actions():
            track_type = str(chosen.data() or "")
            if track_type:
                self.addTrackRequested.emit(track_type)
