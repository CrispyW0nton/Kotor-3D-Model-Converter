"""Track hierarchy tree for the Sequence Editor."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from src.sequence.sequence_binding import SequenceTargetType
from src.sequence.sequence_model import GhostRiggerLevelSequence


class SequenceTrackListWidget(QtWidgets.QTreeWidget):
    trackSelected = QtCore.Signal(object)
    bindingSelected = QtCore.Signal(object)
    addSelectedObjectRequested = QtCore.Signal()
    addTrackRequested = QtCore.Signal(str)
    addCameraCutRequested = QtCore.Signal()
    deleteSelectionRequested = QtCore.Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.sequence: GhostRiggerLevelSequence | None = None
        self.setHeaderLabels(["Sequence", "Type"])
        self.setAlternatingRowColors(True)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def set_sequence(self, sequence: GhostRiggerLevelSequence | None) -> None:
        self.sequence = sequence
        self.refresh()

    def refresh(self) -> None:
        self.clear()
        if self.sequence is None:
            return
        master = QtWidgets.QTreeWidgetItem(["Master Tracks", ""])
        master.setExpanded(True)
        self.addTopLevelItem(master)
        for track in self.sequence.master_tracks:
            item = QtWidgets.QTreeWidgetItem([track.name, track.track_type])
            item.setData(0, QtCore.Qt.UserRole, ("track", track.track_id))
            master.addChild(item)
        for binding in self.sequence.bindings:
            warning = " ! Missing" if binding.missing else ""
            target_type = binding.target_type.value if isinstance(binding.target_type, SequenceTargetType) else str(binding.target_type)
            item = QtWidgets.QTreeWidgetItem([f"{binding.display_name}{warning}", target_type])
            item.setData(0, QtCore.Qt.UserRole, ("binding", binding.binding_id))
            item.setExpanded(bool(not binding.missing))
            self.addTopLevelItem(item)
            for track in binding.tracks:
                track_item = QtWidgets.QTreeWidgetItem([track.name, track.track_type])
                track_item.setData(0, QtCore.Qt.UserRole, ("track", track.track_id))
                item.addChild(track_item)
        self.resizeColumnToContents(0)

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
        for track_type in ("Transform", "Camera Property", "Light Property", "Visibility", "Material", "Event", "Rig Control", "Character", "Sub Sequence"):
            action = track_menu.addAction(track_type)
            action.setData(track_type)
        track_menu.setEnabled(binding is not None or item is None or not is_track)
        if is_track or is_binding:
            menu.addSeparator()
        delete_action = menu.addAction("Delete Track" if is_track else "Delete Object Binding")
        delete_action.setEnabled(is_track or is_binding)
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is add_object:
            self.addSelectedObjectRequested.emit()
        elif chosen is add_cut:
            self.addCameraCutRequested.emit()
        elif chosen is delete_action:
            self.deleteSelectionRequested.emit()
        elif chosen in track_menu.actions():
            track_type = str(chosen.data() or "")
            if track_type:
                self.addTrackRequested.emit(track_type)
