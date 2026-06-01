"""Standalone GhostRigger Sequence Editor window."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.assets.qt_theme import C, apply_theme, update_legacy_palette
from src.sequence.sequence_binding import SequenceTargetType
from src.sequence.sequence_clipboard import SequenceClipboard
from src.sequence.sequence_evaluator import SequenceEvaluator, quat_to_euler_degrees
from src.sequence.sequence_manager import SequenceManager, ensure_sequence_object_id, infer_target_type
from src.sequence.sequence_model import GhostRiggerLevelSequence, SequenceMarker
from src.sequence.sequence_playback import SequencePlaybackController
from src.sequence.sequence_render import SequenceRenderSettings, SequenceRenderer
from src.sequence.tracks.camera_cut_track import CameraCutTrack
from src.sequence.tracks.camera_property_track import CameraPropertyTrack
from src.sequence.tracks.character_track import CharacterTrack
from src.sequence.tracks.event_track import EventTrack
from src.sequence.tracks.light_property_track import LightPropertyTrack
from src.sequence.tracks.material_track import MaterialTrack
from src.sequence.tracks.rig_track import RigTrack
from src.sequence.tracks.sub_sequence_track import SubSequenceTrack
from src.sequence.tracks.transform_track import TransformTrack
from src.sequence.tracks.visibility_track import VisibilityTrack

from .sequence_curve_editor import SequenceCurveEditor
from .sequence_outliner import SequenceOutliner
from .sequence_property_panel import SequencePropertyPanel
from .sequence_timeline_widget import SequenceTimelineWidget
from .sequence_toolbar import SequenceToolbar
from .sequence_transport_bar import SequenceTransportBar
from .sequence_viewport_panel import SequenceViewportPanel


class SequenceEditorWindow(QtWidgets.QMainWindow):
    """Professional, native GhostRigger cinematic timeline editor."""

    sequenceSaved = QtCore.Signal(str)

    def __init__(
        self,
        main_window=None,
        viewport=None,
        app_root: str | Path | None = None,
        parent=None,
        *,
        docked: bool = False,
    ) -> None:
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.source_viewport = viewport or getattr(main_window, "viewport", None)
        self.docked_preview = bool(docked)
        self.app_root = Path(app_root or getattr(main_window, "app_root", Path.cwd()))
        self.settings_path = self.app_root / "config" / "sequence_editor_settings.json"
        self.manager = SequenceManager(self.app_root / "sequences")
        self.evaluator = SequenceEvaluator(None)
        self.playback = SequencePlaybackController()
        self.clipboard = SequenceClipboard()
        self.sequence: GhostRiggerLevelSequence | None = None
        self.auto_key_enabled = False
        self.fire_events_while_scrubbing = False
        self._settings = self._load_settings()
        self._last_evaluated_frame = 0
        self.setWindowTitle("GhostRigger Sequence Editor")
        self.resize(1360, 820)
        self._build_actions()
        self._build_ui()
        self._sync_preview_target()
        self._connect()
        self._install_shortcuts()
        theme_manager = getattr(main_window, "theme_manager", None)
        layout_manager = getattr(main_window, "layout_manager", None)
        if theme_manager is not None:
            theme_manager.register_theme_aware_widget(self)
            theme = theme_manager.current_theme or theme_manager.get_theme()
            update_legacy_palette(theme)
            self.apply_ghost_theme(theme)
        else:
            apply_theme(self)
        if layout_manager is not None:
            self.apply_ghost_layout(layout_manager.current_layout or layout_manager.get_layout())
        self._new_sequence(initial=True)
        self._load_persisted_settings()
        self._play_timer = QtCore.QTimer(self)
        self._play_timer.setInterval(8)
        self._play_timer.timeout.connect(self._tick_playback)
        if self.source_viewport is not None and hasattr(self.source_viewport, "nodeMoved"):
            self.source_viewport.nodeMoved.connect(self._on_scene_object_changed)

    def apply_ghost_theme(self, theme) -> None:
        update_legacy_palette(theme)
        self.status.setStyleSheet(f"color:{theme.color('text.secondary')}; padding:3px 8px;")
        for widget_name in ("timeline", "curve_editor", "outliner", "properties_panel", "transport", "toolbar"):
            widget = getattr(self, widget_name, None)
            hook = getattr(widget, "apply_ghost_theme", None)
            if callable(hook):
                hook(theme)
            elif widget is not None:
                widget.update()

    def apply_ghost_layout(self, layout) -> None:
        toolbar = layout.toolbar("viewport")
        for button in self.findChildren(QtWidgets.QPushButton):
            button.setMinimumHeight(max(22, toolbar.height - 8))
            button.setIconSize(QtCore.QSize(toolbar.icon_size, toolbar.icon_size))
        self.main_splitter.setHandleWidth(layout.spacing_value("splitterHandleWidth", 6))
        self.outliner.setMinimumWidth(layout.panel("animationLibrary").min_width)
        self.properties_panel.setMinimumWidth(layout.panel("properties").min_width)
        if hasattr(self.timeline, "apply_ghost_layout"):
            self.timeline.apply_ghost_layout(layout)
        if hasattr(self.transport, "apply_ghost_layout"):
            self.transport.apply_ghost_layout(layout)

    def _build_actions(self) -> None:
        self.new_action = QtGui.QAction("New Sequence", self)
        self.open_action = QtGui.QAction("Open Sequence...", self)
        self.save_action = QtGui.QAction("Save Sequence", self)
        self.save_as_action = QtGui.QAction("Save Sequence As...", self)
        self.render_action = QtGui.QAction("Render Sequence...", self)
        self.restore_action = QtGui.QAction("Restore Original State", self)
        self.keep_action = QtGui.QAction("Keep Current State", self)
        self.apply_frame_action = QtGui.QAction("Apply Sequence at Current Frame", self)
        self.add_marker_action = QtGui.QAction("Add Marker", self)

    def _build_ui(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        for action in (self.new_action, self.open_action, self.save_action, self.save_as_action, self.render_action):
            file_menu.addAction(action)
        edit_menu = self.menuBar().addMenu("Edit")
        edit_menu.addAction(self.add_marker_action)
        preview_menu = self.menuBar().addMenu("Preview")
        preview_menu.addAction(self.restore_action)
        preview_menu.addAction(self.keep_action)
        preview_menu.addAction(self.apply_frame_action)

        root = QtWidgets.QWidget(self)
        outer = QtWidgets.QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.toolbar = SequenceToolbar(self)
        outer.addWidget(self.toolbar)

        selector_row = QtWidgets.QHBoxLayout()
        selector_row.setContentsMargins(6, 4, 6, 4)
        self.sequence_combo = QtWidgets.QComboBox()
        self.sequence_combo.setToolTip("Available GhostRigger Level Sequence assets")
        self.refresh_library_btn = QtWidgets.QPushButton("Refresh")
        self.layout_combo = QtWidgets.QComboBox()
        self.layout_combo.addItems(
            [
                "Timeline Only",
                "Timeline + Viewport",
                "Dual Viewport + Timeline",
                "Curve Editor",
                "Curve Editor + Viewport",
                "Camera Cut Review",
                "Camera Cut Review + Viewport",
            ]
        )
        selector_row.addWidget(QtWidgets.QLabel("Sequence"))
        selector_row.addWidget(self.sequence_combo, 1)
        selector_row.addWidget(self.refresh_library_btn)
        selector_row.addWidget(QtWidgets.QLabel("Layout"))
        selector_row.addWidget(self.layout_combo)
        outer.addLayout(selector_row)

        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.outliner = SequenceOutliner(self)
        self.outliner.setMinimumWidth(260)
        self.timeline = SequenceTimelineWidget(self)
        self.timeline_scroll = QtWidgets.QScrollArea(self)
        self.timeline_scroll.setWidgetResizable(True)
        self.timeline_scroll.setWidget(self.timeline)
        self.viewport_panel = SequenceViewportPanel(self.source_viewport, self)
        self.properties_panel = SequencePropertyPanel(self)

        center_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.center_stack = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.center_stack.addWidget(self.viewport_panel)
        self.center_stack.addWidget(self.timeline_scroll)
        self.center_stack.setStretchFactor(0, 1)
        self.center_stack.setStretchFactor(1, 2)
        self.curve_editor = SequenceCurveEditor(self)
        center_splitter.addWidget(self.center_stack)
        center_splitter.addWidget(self.curve_editor)
        center_splitter.setStretchFactor(0, 4)
        center_splitter.setStretchFactor(1, 1)

        self.main_splitter.addWidget(self.outliner)
        self.main_splitter.addWidget(center_splitter)
        self.main_splitter.addWidget(self.properties_panel)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)
        self.main_splitter.setSizes([310, 820, 300])
        outer.addWidget(self.main_splitter, 1)

        self.transport = SequenceTransportBar(self)
        outer.addWidget(self.transport)
        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet(f"color:{C['text2']}; padding:3px 8px;")
        outer.addWidget(self.status)
        self.setCentralWidget(root)
        self._refresh_sequence_combo()

    def set_docked_preview(self, docked: bool, viewport=None) -> None:
        self.docked_preview = bool(docked)
        if viewport is not None:
            self.source_viewport = viewport
            self.viewport_panel.source_viewport = viewport
        self._sync_preview_target()
        self._apply_layout_mode(self.layout_combo.currentText())

    def set_renderer_settings(self, settings: object) -> None:
        panel = getattr(self, "viewport_panel", None)
        if panel is not None and hasattr(panel, "set_renderer_settings"):
            panel.set_renderer_settings(settings)

    def _preview_viewport(self):
        if self.docked_preview:
            return self.source_viewport
        return getattr(self.viewport_panel, "viewport", None)

    def _sync_preview_target(self) -> None:
        if not self.docked_preview:
            self.viewport_panel.sync_from_source()
        self.evaluator.set_viewport(self._preview_viewport())

    def _connect(self) -> None:
        self.new_action.triggered.connect(self._new_sequence)
        self.open_action.triggered.connect(self._open_sequence)
        self.save_action.triggered.connect(self._save_sequence)
        self.save_as_action.triggered.connect(self._save_sequence_as)
        self.render_action.triggered.connect(self._render_sequence)
        self.restore_action.triggered.connect(self._restore_original_state)
        self.keep_action.triggered.connect(lambda: self._set_status("Current preview state kept."))
        self.apply_frame_action.triggered.connect(self._apply_current_frame_state)
        self.add_marker_action.triggered.connect(self._add_marker)
        self.toolbar.newSequence.connect(self._new_sequence)
        self.toolbar.openSequence.connect(self._open_sequence)
        self.toolbar.saveSequence.connect(self._save_sequence)
        self.toolbar.saveAsSequence.connect(self._save_sequence_as)
        self.toolbar.renderSequence.connect(self._render_sequence)
        self.toolbar.addSelectedObject.connect(self._add_selected_object)
        self.toolbar.createCamera.connect(self._create_and_bind_camera)
        self.toolbar.createLight.connect(self._create_and_bind_light)
        self.toolbar.addTrack.connect(self._add_track)
        self.toolbar.addCameraCut.connect(self._add_camera_cut)
        self.toolbar.setKey.connect(self._set_key)
        self.toolbar.autoKeyChanged.connect(self._set_auto_key)
        self.timeline.frameChanged.connect(self._set_frame)
        self.timeline.keySelectionChanged.connect(self._refresh_properties)
        self.timeline.keyMoved.connect(self._sequence_changed)
        self.timeline.contextMenuRequested.connect(self._timeline_context_menu)
        self.transport.goStart.connect(lambda: self._set_frame(self.playback.go_to_start()))
        self.transport.goEnd.connect(lambda: self._set_frame(self.playback.go_to_end()))
        self.transport.previousKey.connect(self._previous_key)
        self.transport.nextKey.connect(self._next_key)
        self.transport.playPause.connect(self._toggle_play)
        self.transport.frameEdited.connect(self._set_frame)
        self.transport.loopChanged.connect(self._set_loop)
        self.transport.speedChanged.connect(self.playback.set_speed)
        self.outliner.track_list.trackSelected.connect(self._on_track_selected)
        self.outliner.track_list.bindingSelected.connect(self._on_binding_selected)
        self.outliner.track_list.addSelectedObjectRequested.connect(self._add_selected_object)
        self.outliner.track_list.addTrackRequested.connect(self._add_track)
        self.outliner.track_list.addCameraCutRequested.connect(self._add_camera_cut)
        self.outliner.track_list.deleteSelectionRequested.connect(self._delete_selected_outliner_item)
        self.properties_panel.sequenceChanged.connect(self._sequence_changed)
        self.refresh_library_btn.clicked.connect(self._refresh_sequence_combo)
        self.sequence_combo.activated.connect(self._load_selected_combo_sequence)
        self.layout_combo.currentTextChanged.connect(self._apply_layout_mode)

    def _install_shortcuts(self) -> None:
        QtGui.QShortcut(QtGui.QKeySequence.Delete, self, activated=self.timeline.delete_selected_keys)
        QtGui.QShortcut(QtGui.QKeySequence.Copy, self, activated=self._copy_keys)
        QtGui.QShortcut(QtGui.QKeySequence.Paste, self, activated=self._paste_keys)
        QtGui.QShortcut(QtGui.QKeySequence("I"), self, activated=self._set_key)
        QtGui.QShortcut(QtGui.QKeySequence("K"), self, activated=self._set_key)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Space), self, activated=self._toggle_play)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Home), self, activated=lambda: self._set_frame(self.playback.go_to_start()))
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_End), self, activated=lambda: self._set_frame(self.playback.go_to_end()))

    def _new_sequence(self, checked: bool = False, *, initial: bool = False) -> None:
        module_name = str(getattr(getattr(self.source_viewport, "model", None), "name", "") or "")
        self.sequence = self.manager.new_sequence("intro_cutscene" if initial else "New Sequence", scene_module_name=module_name)
        self._set_sequence(self.sequence)

    def _set_sequence(self, sequence: GhostRiggerLevelSequence) -> None:
        self.sequence = sequence
        self.playback.set_sequence(sequence)
        self.evaluator.capture_original_state(sequence)
        self.timeline.set_sequence(sequence)
        self.outliner.set_sequence(sequence)
        self.properties_panel.set_sequence(sequence)
        self.transport.set_frame_range(sequence.start_frame, sequence.end_frame)
        self.transport.set_frame(sequence.current_frame)
        self.viewport_panel.sync_from_source()
        self._sync_preview_target()
        self._last_evaluated_frame = sequence.current_frame
        self._evaluate_current(scrubbing=True)
        self._set_status(f"{sequence.name} | {sequence.start_frame}-{sequence.end_frame} @ {sequence.frame_rate:g} fps")

    def _open_sequence(self) -> None:
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(self, "Open GhostRigger Level Sequence", str(self.manager.root), "GhostRigger Level Sequence (*.grseq)")
        if not path:
            return
        self._load_sequence_path(path)

    def _load_selected_combo_sequence(self) -> None:
        path = str(self.sequence_combo.currentData() or "")
        if path:
            self._load_sequence_path(path)

    def _load_sequence_path(self, path: str) -> None:
        try:
            sequence = self.manager.load(path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Cannot Load Sequence", str(exc))
            return
        self._set_sequence(sequence)
        self._resolve_missing_bindings()
        self._refresh_sequence_combo()

    def _save_sequence(self) -> None:
        if self.sequence is None:
            return
        if not self.sequence.asset_path:
            self._save_sequence_as()
            return
        try:
            path = self.manager.save(self.sequence)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Cannot Save Sequence", str(exc))
            return
        self.sequenceSaved.emit(str(path))
        self._refresh_sequence_combo()
        self._persist_settings()
        self._set_status(f"Saved {path}")

    def _save_sequence_as(self) -> None:
        if self.sequence is None:
            return
        path, _filter = QtWidgets.QFileDialog.getSaveFileName(self, "Save GhostRigger Level Sequence", str(self.manager.default_asset_path(self.sequence.name)), "GhostRigger Level Sequence (*.grseq)")
        if not path:
            return
        try:
            saved = self.manager.save(self.sequence, path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Cannot Save Sequence", str(exc))
            return
        self.sequenceSaved.emit(str(saved))
        self._refresh_sequence_combo()
        self._persist_settings()
        self._set_status(f"Saved {saved}")

    def _refresh_sequence_combo(self) -> None:
        current = str(getattr(self.sequence, "asset_path", "") or "")
        self.sequence_combo.blockSignals(True)
        self.sequence_combo.clear()
        self.sequence_combo.addItem("Current Unsaved Sequence", "")
        for info in self.manager.list_assets():
            self.sequence_combo.addItem(f"{info.name}  ({info.frame_rate:g} fps, {info.bindings} bindings)", info.path)
        if current:
            index = self.sequence_combo.findData(current)
            if index >= 0:
                self.sequence_combo.setCurrentIndex(index)
        self.sequence_combo.blockSignals(False)

    def _selected_scene_object(self):
        viewport = self.source_viewport
        if viewport is None:
            return None
        meshes = viewport.get_selected_meshes() if hasattr(viewport, "get_selected_meshes") else []
        if meshes:
            return meshes[-1]
        renderer = getattr(viewport, "_renderer", None)
        node = getattr(renderer, "selected_node", None)
        return node

    def _add_selected_object(self) -> None:
        if self.sequence is None:
            return
        obj = self._selected_scene_object()
        if obj is None:
            QtWidgets.QMessageBox.information(self, "Add Selected Object", "No scene object is selected.")
            return
        binding = self.manager.add_object_binding(self.sequence, obj)
        self._sequence_changed()
        self.outliner.track_list.setCurrentItem(self._find_binding_item(binding.binding_id))
        self._set_status(f"Bound {binding.display_name}")

    def _create_and_bind_camera(self, camera_type: str) -> None:
        if self.sequence is None or self.main_window is None:
            return
        creator = getattr(self.main_window, "_create_scene_camera_object", None)
        if not callable(creator):
            return
        scene_obj = creator(str(camera_type or "Cinematic Camera"))
        if scene_obj is None:
            return
        binding = self.manager.add_object_binding(self.sequence, scene_obj)
        self._sequence_changed()
        self.outliner.track_list.setCurrentItem(self._find_binding_item(binding.binding_id))
        self._set_status(f"Created and bound {binding.display_name}")

    def _create_and_bind_light(self, light_type: str) -> None:
        if self.sequence is None or self.main_window is None:
            return
        creator = getattr(self.main_window, "_create_scene_light_object", None)
        if not callable(creator):
            return
        scene_obj = creator(str(light_type or "point"))
        if scene_obj is None:
            return
        binding = self.manager.add_object_binding(self.sequence, scene_obj)
        self._sequence_changed()
        self.outliner.track_list.setCurrentItem(self._find_binding_item(binding.binding_id))
        self._set_status(f"Created and bound {binding.display_name}")

    def _add_track(self, track_type: str) -> None:
        if self.sequence is None:
            return
        binding = self.outliner.track_list.selected_binding()
        if binding is None:
            obj = self._selected_scene_object()
            binding = self.manager.add_object_binding(self.sequence, obj) if obj is not None else None
        master_track_types = {"Camera Cut", "Sub Sequence", "Event"}
        if binding is None and track_type not in master_track_types:
            QtWidgets.QMessageBox.information(self, "Add Track", "Select or bind an object first.")
            return
        track = self._make_track(track_type, binding)
        if isinstance(track, CameraCutTrack) or (binding is None and isinstance(track, (SubSequenceTrack, EventTrack))):
            self.sequence.master_tracks.append(track)
        elif binding is not None:
            binding.add_track(track)
        self._sequence_changed()
        self._set_status(f"Added {track.track_type} track")

    def _delete_selected_outliner_item(self) -> None:
        if self.sequence is None:
            return
        track = self.outliner.track_list.selected_track()
        binding = self.outliner.track_list.selected_binding()
        if track is not None:
            removed = False
            if track in self.sequence.master_tracks:
                self.sequence.master_tracks = [item for item in self.sequence.master_tracks if item.track_id != track.track_id]
                removed = True
            elif binding is not None:
                before = len(binding.tracks)
                binding.tracks = [item for item in binding.tracks if item.track_id != track.track_id]
                removed = len(binding.tracks) != before
            if removed:
                self._sequence_changed()
                self._set_status(f"Deleted {track.track_type} track")
            return
        if binding is not None and self.sequence.remove_binding(binding.binding_id):
            self._sequence_changed()
            self._set_status(f"Deleted binding {binding.display_name}")

    def _make_track(self, track_type: str, binding) -> Any:
        if track_type == "Transform":
            return TransformTrack(parent_binding_id=getattr(binding, "binding_id", ""))
        if track_type == "Camera Property":
            return CameraPropertyTrack(parent_binding_id=binding.binding_id, property_name="focal_length_mm")
        if track_type == "Light Property":
            return LightPropertyTrack(parent_binding_id=binding.binding_id, property_name="intensity")
        if track_type == "Visibility":
            return VisibilityTrack(parent_binding_id=binding.binding_id)
        if track_type == "Material":
            return MaterialTrack(parent_binding_id=binding.binding_id, property_name="opacity")
        if track_type == "Event":
            return EventTrack(parent_binding_id=getattr(binding, "binding_id", ""))
        if track_type == "Rig Control":
            return RigTrack(parent_binding_id=binding.binding_id)
        if track_type == "Character":
            return CharacterTrack(parent_binding_id=binding.binding_id)
        if track_type == "Sub Sequence":
            return SubSequenceTrack()
        return TransformTrack(parent_binding_id=getattr(binding, "binding_id", ""))

    def _add_camera_cut(self) -> None:
        if self.sequence is None:
            return
        camera_binding = self._first_camera_binding()
        if camera_binding is None:
            obj = self._selected_scene_object()
            if obj is not None and infer_target_type(obj) == SequenceTargetType.CAMERA:
                camera_binding = self.manager.add_object_binding(self.sequence, obj)
        if camera_binding is None:
            QtWidgets.QMessageBox.warning(self, "Add Camera Cut", "Bind a camera before adding a camera cut.")
            return
        cut_track = next((track for track in self.sequence.master_tracks if isinstance(track, CameraCutTrack)), None)
        if cut_track is None:
            cut_track = CameraCutTrack()
            self.sequence.master_tracks.append(cut_track)
        start = self.sequence.current_frame
        end = min(self.sequence.end_frame, start + 120)
        cut_track.add_cut(camera_binding.binding_id, start, end, camera_binding.display_name)
        self._sequence_changed()
        self._set_status(f"Camera cut: {camera_binding.display_name} {start}-{end}")

    def _set_key(self) -> None:
        if self.sequence is None:
            return
        track = self.outliner.track_list.selected_track()
        binding = self.outliner.track_list.selected_binding()
        if track is None:
            if binding is None:
                obj = self._selected_scene_object()
                binding = self.manager.add_object_binding(self.sequence, obj) if obj is not None else None
            if binding is None:
                return
            track = next((item for item in binding.tracks if isinstance(item, TransformTrack)), None)
            if track is None:
                track = TransformTrack(parent_binding_id=binding.binding_id)
                binding.add_track(track)
        obj = self.evaluator.resolver.resolve(binding) if binding is not None else self._selected_scene_object()
        self._key_track(track, obj)
        self._sequence_changed()

    def _key_track(self, track, obj) -> None:
        if self.sequence is None:
            return
        frame = self.sequence.current_frame
        if isinstance(track, TransformTrack) and obj is not None:
            track.add_transform_key(
                frame,
                location=getattr(obj, "position", (0.0, 0.0, 0.0)),
                rotation=quat_to_euler_degrees(getattr(obj, "rotation", (0.0, 0.0, 0.0, 1.0))),
                scale=getattr(obj, "_gr_scale", getattr(obj, "scale", (1.0, 1.0, 1.0))),
                select=True,
            )
        elif isinstance(track, VisibilityTrack) and obj is not None:
            visible = not bool(getattr(obj, "_gr_hidden", getattr(obj, "_gr_light_hidden", getattr(obj, "_gr_camera_hidden", False))))
            track.add_keyframe(frame, visible, select=True)
        elif isinstance(track, CameraPropertyTrack) and obj is not None:
            camera = self.evaluator.resolver.camera_for_binding(self.sequence.binding_by_id(track.parent_binding_id))
            target = camera if camera is not None else obj
            track.add_keyframe(frame, getattr(target, track.property_name, 0.0), select=True)
        elif isinstance(track, LightPropertyTrack) and obj is not None:
            attr = {
                "enabled": "light_enabled",
                "visible": "_gr_light_hidden",
                "color": "light_color",
                "intensity": "light_multiplier",
                "radius": "light_radius",
                "cone_angle": "light_cone_degrees",
                "area_size": "light_area_size",
                "ambient_only": "light_ambient_only",
                "casts_shadows": "light_shadow",
                "affects_diffuse": "light_affects_diffuse",
                "affects_specular": "light_affects_specular",
                "affects_lightmap": "light_affects_lightmap",
                "affects_environment": "light_affects_environment",
            }.get(track.property_name, track.property_name)
            value = getattr(obj, attr, 0.0)
            if track.property_name == "visible":
                value = not bool(value)
            track.add_keyframe(frame, value, select=True)
        elif isinstance(track, MaterialTrack) and obj is not None:
            attr = {"opacity": "alpha", "material_color": "diffuse"}.get(track.property_name, track.property_name)
            track.add_keyframe(frame, getattr(obj, attr, 0.0), select=True)
        elif isinstance(track, EventTrack):
            track.add_event_key(frame, "Custom Event", {})
        else:
            track.add_keyframe(frame, None, select=True)

    def _set_frame(self, frame: int) -> None:
        if self.sequence is None:
            return
        previous = self.sequence.current_frame
        self.sequence.set_current_frame(frame)
        self.transport.set_frame(self.sequence.current_frame)
        self.timeline.update()
        self._evaluate_current(scrubbing=True, previous_frame=previous)

    def _evaluate_current(self, *, scrubbing: bool, previous_frame: int | None = None) -> None:
        if self.sequence is None:
            return
        self.evaluator.evaluate(
            self.sequence,
            self.sequence.current_frame,
            scrubbing=scrubbing,
            previous_frame=previous_frame,
            fire_events=(not scrubbing or self.fire_events_while_scrubbing),
        )
        self.viewport_panel.set_warning(self.evaluator.last_warning)
        self._last_evaluated_frame = self.sequence.current_frame
        self.transport.set_frame(self.sequence.current_frame)
        self._set_status(f"Frame {self.sequence.current_frame} | {self.sequence.name}")

    def _tick_playback(self) -> None:
        if self.sequence is None:
            return
        previous = self.sequence.current_frame
        tick = self.playback.tick()
        self.transport.set_playing(tick.playing)
        self.timeline.update()
        self._evaluate_current(scrubbing=False, previous_frame=previous)
        if not tick.playing:
            self._play_timer.stop()

    def _toggle_play(self) -> None:
        self.playback.toggle_play()
        self.transport.set_playing(self.playback.playing)
        if self.playback.playing:
            self._play_timer.start()
        else:
            self._play_timer.stop()

    def _previous_key(self) -> None:
        if self.sequence is None:
            return
        frames = sorted({key.frame for track in self.sequence.all_tracks() for key in track.keyframes if key.frame < self.sequence.current_frame})
        if frames:
            self._set_frame(frames[-1])

    def _next_key(self) -> None:
        if self.sequence is None:
            return
        frames = sorted({key.frame for track in self.sequence.all_tracks() for key in track.keyframes if key.frame > self.sequence.current_frame})
        if frames:
            self._set_frame(frames[0])

    def _set_loop(self, enabled: bool) -> None:
        self.playback.loop = bool(enabled)
        self._persist_settings()

    def _set_auto_key(self, enabled: bool) -> None:
        self.auto_key_enabled = bool(enabled)
        self.toolbar.auto_key.setStyleSheet("QCheckBox { color: #FFAA00; font-weight: bold; }" if enabled else "")
        self._persist_settings()

    def _on_scene_object_changed(self, obj) -> None:
        if not self.auto_key_enabled or self.sequence is None or obj is None:
            return
        object_id = ensure_sequence_object_id(obj)
        binding = next((item for item in self.sequence.bindings if item.target_object_id == object_id), None)
        if binding is None:
            return
        for track in binding.tracks:
            if isinstance(track, TransformTrack):
                self._key_track(track, obj)
                self._sequence_changed()
                break

    def _copy_keys(self) -> None:
        if self.sequence is not None:
            count = self.clipboard.copy_selected(self.sequence.all_tracks())
            self._set_status(f"Copied {count} key(s)")

    def _paste_keys(self) -> None:
        if self.sequence is not None:
            count = self.clipboard.paste(self.sequence.all_tracks(), self.sequence.current_frame)
            if count:
                self._sequence_changed()
            self._set_status(f"Pasted {count} key(s)")

    def _timeline_context_menu(self, point: QtCore.QPoint) -> None:
        menu = QtWidgets.QMenu(self)
        add_key = menu.addAction("Add Key")
        delete_key = menu.addAction("Delete Key")
        copy = menu.addAction("Copy")
        paste = menu.addAction("Paste")
        menu.addSeparator()
        marker = menu.addAction("Add Marker")
        mute_track = menu.addAction("Mute Track")
        lock_track = menu.addAction("Lock Track")
        chosen = menu.exec(point)
        track = self.outliner.track_list.selected_track()
        if chosen is add_key:
            self._set_key()
        elif chosen is delete_key:
            self.timeline.delete_selected_keys()
            self._sequence_changed()
        elif chosen is copy:
            self._copy_keys()
        elif chosen is paste:
            self._paste_keys()
        elif chosen is marker:
            self._add_marker()
        elif chosen is mute_track and track is not None:
            track.muted = not track.muted
            self._sequence_changed()
        elif chosen is lock_track and track is not None:
            track.locked = not track.locked
            self._sequence_changed()

    def _add_marker(self) -> None:
        if self.sequence is None:
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "Add Marker", "Marker name:", text=f"Marker {len(self.sequence.markers) + 1}")
        if not ok:
            return
        self.sequence.markers.append(SequenceMarker(frame=self.sequence.current_frame, name=name or "Marker"))
        self._sequence_changed()

    def _render_sequence(self) -> None:
        if self.sequence is None:
            return
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Render Sequence To", str(self.app_root / "exports" / "sequences"))
        if not directory:
            return
        settings = SequenceRenderSettings.for_sequence(self.sequence)
        settings.output_directory = directory
        settings.output_format = "PNG"
        settings.overwrite_existing = True
        progress = QtWidgets.QProgressDialog("Rendering sequence...", "Cancel", 0, max(1, settings.end_frame - settings.start_frame + 1), self)
        progress.setWindowModality(QtCore.Qt.WindowModal)

        def on_progress(index: int, total: int, path: str) -> bool:
            progress.setMaximum(total)
            progress.setValue(index)
            progress.setLabelText(f"Frame {index}/{total}\n{path}")
            QtWidgets.QApplication.processEvents()
            return not progress.wasCanceled()

        try:
            written = SequenceRenderer(self._preview_viewport(), self.evaluator).render(self.sequence, settings, progress=on_progress)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Render Sequence Failed", str(exc))
            return
        self._set_status(f"Rendered {len(written)} frame(s) to {directory}")

    def _restore_original_state(self) -> None:
        if self.sequence is not None:
            self.evaluator.restore_original_state(self.sequence)
            self._set_status("Original scene state restored.")

    def _apply_current_frame_state(self) -> None:
        if self.sequence is not None:
            self.evaluator._captured.clear()
            self._set_status(f"Applied sequence frame {self.sequence.current_frame} to scene.")

    def _resolve_missing_bindings(self) -> None:
        if self.sequence is None:
            return
        self.manager.resolve_missing_bindings(self.sequence, self.evaluator.resolver.all_objects())
        self.outliner.set_sequence(self.sequence)

    def _first_camera_binding(self):
        if self.sequence is None:
            return None
        return next((binding for binding in self.sequence.bindings if binding.target_type == SequenceTargetType.CAMERA), None)

    def _on_track_selected(self, track) -> None:
        self.curve_editor.set_track(track)
        self.properties_panel.set_target(track)

    def _on_binding_selected(self, binding) -> None:
        self.properties_panel.set_target(binding)

    def _refresh_properties(self) -> None:
        self.properties_panel.refresh_info()

    def _sequence_changed(self) -> None:
        if self.sequence is None:
            return
        self.sequence.touch()
        self.timeline.set_sequence(self.sequence)
        self.outliner.set_sequence(self.sequence)
        self.properties_panel.refresh()
        self.transport.set_frame_range(self.sequence.start_frame, self.sequence.end_frame)
        self._evaluate_current(scrubbing=True)

    def _apply_layout_mode(self, mode: str) -> None:
        wants_viewport = mode in {"Timeline + Viewport", "Dual Viewport + Timeline", "Curve Editor + Viewport", "Camera Cut Review + Viewport"}
        show_viewport = bool(wants_viewport and not self.docked_preview)
        show_curve = mode in {"Curve Editor", "Curve Editor + Viewport", "Camera Cut Review", "Camera Cut Review + Viewport"}
        self.viewport_panel.setVisible(show_viewport)
        self.curve_editor.setVisible(show_curve)
        if self.docked_preview and wants_viewport:
            self.viewport_panel.set_warning("Previewing through the main viewport.")
        self._settings["selected_layout_mode"] = mode
        self._persist_settings()

    def _find_binding_item(self, binding_id: str):
        tree = self.outliner.track_list
        for index in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(index)
            data = item.data(0, QtCore.Qt.UserRole)
            if data == ("binding", binding_id):
                return item
        return None

    def _load_settings(self) -> dict[str, Any]:
        try:
            if self.settings_path.exists():
                return json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _load_persisted_settings(self) -> None:
        settings = self._settings
        self.timeline.set_zoom(float(settings.get("timeline_zoom", self.timeline.pixels_per_frame)))
        self.playback.loop = bool(settings.get("loop_playback", False))
        self.transport.loop_check.setChecked(self.playback.loop)
        self._set_auto_key(bool(settings.get("auto_key_enabled", False)))
        mode = str(settings.get("selected_layout_mode") or "Timeline + Viewport")
        index = self.layout_combo.findText(mode)
        self.layout_combo.setCurrentIndex(index if index >= 0 else 1)
        self._apply_layout_mode(self.layout_combo.currentText())

    def _persist_settings(self) -> None:
        self._settings.update(
            {
                "last_opened_sequence": str(getattr(self.sequence, "asset_path", "") or ""),
                "timeline_zoom": float(self.timeline.pixels_per_frame),
                "selected_layout_mode": self.layout_combo.currentText(),
                "show_curve_editor": bool(self.curve_editor.isVisible()),
                "show_viewport": bool(self.viewport_panel.isVisible()),
                "loop_playback": bool(self.playback.loop),
                "playback_speed": float(self.playback.playback_speed),
                "auto_key_enabled": bool(self.auto_key_enabled),
                "snap_keys_enabled": bool(self.timeline.snap_keys),
                "recent_sequences": list(self.manager.recent_sequences),
            }
        )
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(json.dumps(self._settings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except OSError:
            pass

    def _set_status(self, text: str) -> None:
        self.status.setText(text)

    def closeEvent(self, event):  # noqa: N802
        self._persist_settings()
        if self.sequence is not None and self.evaluator._captured:
            answer = QtWidgets.QMessageBox.question(
                self,
                "Close Sequence Editor",
                "Restore original scene state before closing?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.Yes,
            )
            if answer == QtWidgets.QMessageBox.Cancel:
                event.ignore()
                return
            if answer == QtWidgets.QMessageBox.Yes:
                self.evaluator.restore_original_state(self.sequence)
            else:
                self.evaluator._captured.clear()
        super().closeEvent(event)
