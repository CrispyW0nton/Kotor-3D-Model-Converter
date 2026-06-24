"""Viewport host and scene-state preview for the Module Editor."""

from __future__ import annotations

import math

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.level import KMapProject, LevelTransform
from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget


class ModuleEditorViewportPanel(QtWidgets.QWidget):
    itemSelected = QtCore.Signal(str)
    transformEdited = QtCore.Signal(str, object)
    roomOutlinePointEdited = QtCore.Signal(str, int, object)
    roomOutlinePointSnapPreviewRequested = QtCore.Signal(str, int)
    roomOutlinePointSnapped = QtCore.Signal(str, int, int, str)
    roomOutlineEdgeSelected = QtCore.Signal(str, int)
    roomPrimitiveSelected = QtCore.Signal(str, str)
    roomPrimitiveMoved = QtCore.Signal(str, str, object)
    roomPrimitiveRotated = QtCore.Signal(str, str, float)
    roomPrimitiveScaled = QtCore.Signal(str, str, object)
    terrainBrushFrameRequested = QtCore.Signal(str, str, object)
    terrainBrushStrokeCommitted = QtCore.Signal(str, str)
    terrainBrushOptionsChanged = QtCore.Signal(int, float)
    modeMarkingMenuRequested = QtCore.Signal(QtCore.QPoint)
    toolMarkingMenuRequested = QtCore.Signal(QtCore.QPoint)
    transformGizmoModeChanged = QtCore.Signal(str)
    undoShortcutRequested = QtCore.Signal()
    redoShortcutRequested = QtCore.Signal()
    deleteShortcutRequested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModuleEditorViewportPanel")
        self._current_theme = None
        root = QtWidgets.QVBoxLayout(self)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        root.setContentsMargins(4, 4, 4, 0)
        root.setSpacing(4)
        self.viewport_toolbar_frame = QtWidgets.QFrame(self)
        self.viewport_toolbar_frame.setObjectName("ModuleViewportTopTools")
        toolbar_frame_layout = QtWidgets.QVBoxLayout(self.viewport_toolbar_frame)
        toolbar_frame_layout.setContentsMargins(4, 4, 4, 6)
        toolbar_frame_layout.setSpacing(5)
        self.viewport_toolbar = QtWidgets.QHBoxLayout()
        self.viewport_toolbar.setContentsMargins(0, 0, 0, 0)
        self.viewport_toolbar.setSpacing(6)
        self.focus_button = QtWidgets.QPushButton("Focus")
        self.grid_box = QtWidgets.QCheckBox("Grid")
        self.grid_box.setObjectName("mapStudioViewportGridCheckBox")
        self.grid_box.setChecked(True)
        self.snap_box = QtWidgets.QCheckBox("Snap")
        self.snap_box.setObjectName("mapStudioViewportSnapCheckBox")
        self.snap_box.setToolTip(
            "Snap authored room and gameplay marker drags to the viewport grid. "
            "Hold V while dragging a room outline point to snap it to another vertex. "
            "Hold J with transform active to align selected vertices or edges to one level."
        )
        self.terrain_brush_box = QtWidgets.QCheckBox("Terrain Brush")
        self.terrain_brush_box.setObjectName("mapStudioViewportTerrainBrushCheckBox")
        self.terrain_brush_box.setToolTip("Paint the selected terrain heightfield brush directly in the viewport.")
        self.transform_gizmo_group = QtWidgets.QButtonGroup(self)
        self.transform_gizmo_group.setObjectName("mapStudioTransformGizmoModeButtonGroup")
        self.transform_gizmo_group.setExclusive(True)
        self.translate_gizmo_button = self._make_transform_gizmo_button(
            "Translate",
            "mapStudioViewportTranslateGizmoButton",
            "translate",
            "W",
            "Move selected authored objects in KMAP world space.",
        )
        self.rotate_gizmo_button = self._make_transform_gizmo_button(
            "Rotate",
            "mapStudioViewportRotateGizmoButton",
            "rotate",
            "E",
            "Rotate the selected authored object around its primitive pivot.",
        )
        self.scale_gizmo_button = self._make_transform_gizmo_button(
            "Scale",
            "mapStudioViewportScaleGizmoButton",
            "scale",
            "R",
            "Scale/transform the selected authored object without changing its stable KMAP identity.",
        )
        self.viewport_toolbar.addWidget(self.focus_button)
        self.viewport_toolbar.addWidget(self.grid_box)
        self.viewport_toolbar.addWidget(self.snap_box)
        self.viewport_toolbar.addWidget(self.terrain_brush_box)
        self.viewport_toolbar.addWidget(self.translate_gizmo_button)
        self.viewport_toolbar.addWidget(self.rotate_gizmo_button)
        self.viewport_toolbar.addWidget(self.scale_gizmo_button)
        self.viewport_toolbar.addStretch(1)
        toolbar_frame_layout.addLayout(self.viewport_toolbar)
        self.marker_summary_label = QtWidgets.QLabel("Gameplay markers: none")
        self.marker_summary_label.setObjectName("mapStudioPlacementMarkerSummaryLabel")
        self.marker_summary_label.setWordWrap(True)
        toolbar_frame_layout.addWidget(self.marker_summary_label)
        root.addWidget(self.viewport_toolbar_frame)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.viewport = QtViewportWidget(self)
        self.viewport.setObjectName("MapStudioViewportWidget")
        self.viewport.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.viewport.setMinimumHeight(320)
        self.viewport.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self._configure_map_studio_viewport_quality()
        self._ensure_embedded_viewport_toolbar_gap()
        self._marker_pick_filter_ids: set[int] = set()
        self._install_marker_pick_filters()
        toolbar_scroll = getattr(self.viewport, "viewport_toolbar_scroll", None)
        if toolbar_scroll is not None:
            toolbar_scroll.installEventFilter(self)
        self.scene_table = QtWidgets.QTableWidget(0, 8)
        self.scene_table.setHorizontalHeaderLabels(["Type", "Name", "X", "Y", "Z", "Marker", "Facing", "Visible"])
        self.scene_table.horizontalHeader().setStretchLastSection(True)
        self.scene_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.scene_table.setMinimumHeight(46)
        self.scene_table.setMaximumHeight(76)
        self.scene_table.itemSelectionChanged.connect(self._table_selection)
        self.scene_table.itemChanged.connect(self._table_item_changed)
        self.splitter.addWidget(self.viewport)
        self.splitter.addWidget(self.scene_table)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([980, 54])
        root.addWidget(self.splitter, 1)
        self._row_ids: list[str] = []
        self._placement_markers: dict[str, object] = {}
        self._placement_marker_geometry: object | None = None
        self._room_preview_model: object | None = None
        self._room_preview_model_key = ""
        self._terrain_walkability_overlay: object | None = None
        self._universal_transform_overlay: object | None = None
        self._marker_drag: dict[str, object] | None = None
        self._room_outline_point_drag: dict[str, object] | None = None
        self._room_outline_vertex_snap_candidates: dict[tuple[str, int], tuple[object, ...]] = {}
        self._vertex_snap_modifier_active = False
        self._transform_snap_modifier_active = False
        self._transform_gizmo_mode = "translate"
        self._room_primitive_drag: dict[str, object] | None = None
        self._terrain_brush_drag: dict[str, object] | None = None
        self._terrain_brush_option_drag: dict[str, object] | None = None
        self._terrain_brush_context: dict[str, object] = {
            "enabled": False,
            "room_resref": "",
            "brush": "",
            "row_count": 0,
            "column_count": 0,
            "radius": 0,
            "hardness": 0.5,
        }
        self._table_updating = False
        self.terrain_brush_box.toggled.connect(self._toggle_terrain_brush_interaction)
        self.set_transform_gizmo_mode("translate", announce=False)
        self._sync_clean_viewport_presentation()

    def _make_transform_gizmo_button(
        self,
        label: str,
        object_name: str,
        mode_key: str,
        hotkey: str,
        tooltip: str,
    ) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton(self)
        button.setObjectName(object_name)
        button.setText(label)
        button.setCheckable(True)
        button.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        button.setMinimumWidth(72)
        button.setToolTip(f"{tooltip} Shortcut: {hotkey}.")
        self.transform_gizmo_group.addButton(button)
        button.clicked.connect(lambda _checked=False, key=mode_key: self.set_transform_gizmo_mode(key))
        return button

    def set_project(
        self,
        project: KMapProject,
        authored_gameplay_placements=(),
        authored_room_lights=(),
        authored_gameplay_markers=(),
        authored_gameplay_marker_geometry=None,
        authored_room_outline_geometry=None,
        authored_terrain_walkability_overlay=None,
        authored_room_preview_model=None,
    ) -> None:
        self._table_updating = True
        try:
            self.scene_table.setRowCount(0)
            self._row_ids.clear()
            self._placement_marker_geometry = authored_gameplay_marker_geometry
            self._room_outline_geometry = authored_room_outline_geometry
            self._terrain_walkability_overlay = authored_terrain_walkability_overlay
            self._room_preview_model = authored_room_preview_model
            self._placement_markers = {
                str(getattr(marker, "placement_id", "") or ""): marker
                for marker in authored_gameplay_markers or ()
                if str(getattr(marker, "placement_id", "") or "")
            }
            for module in project.modules:
                pos = module.transform.position
                self._add_row("Module", module.module_name, module.module_id, pos, module.visible)
            for room in project.rooms:
                pos = room.transform.position
                self._add_row("Room", room.name, room.room_id, pos, room.visible)
            for blueprint in project.blueprints:
                self._add_row("Blueprint", blueprint.name, blueprint.blueprint_id, blueprint.position, True)
            for placement in authored_gameplay_placements or ():
                if not bool(getattr(placement, "is_spatial", True)):
                    continue
                label = str(getattr(placement, "tag", "") or getattr(placement, "template_resref", "") or getattr(placement, "placement_id", ""))
                kind = f"Authored {str(getattr(placement, 'kind', 'object')).title()}"
                placement_id = str(getattr(placement, "placement_id", ""))
                marker = self._placement_markers.get(placement_id)
                marker_label = str(getattr(marker, "shape", "") or "")
                transition_summary = str(getattr(placement, "transition_summary", "") or "")
                if transition_summary:
                    marker_label = f"{marker_label}; {transition_summary}" if marker_label else transition_summary
                bearing = float(getattr(marker, "bearing", getattr(placement, "bearing", 0.0)) or 0.0)
                self._add_row(
                    kind,
                    label,
                    placement_id,
                    getattr(placement, "position", (0.0, 0.0, 0.0)),
                    True,
                    marker=marker_label,
                    facing=f"{bearing:.2f} rad",
                )
            for light in authored_room_lights or ():
                light_id = str(getattr(light, "light_id", "") or "")
                label = str(getattr(light, "name", "") or light_id)
                marker_label = str(getattr(light, "light_type", "point") or "point")
                self._add_row(
                    "Authored Room Light",
                    label,
                    light_id,
                    getattr(light, "position", (0.0, 0.0, 0.0)),
                    True,
                    marker=marker_label,
                    facing=f"R {float(getattr(light, 'radius', 0.0) or 0.0):.2f}",
                )
        finally:
            self._table_updating = False
        self._update_marker_summary(
            authored_gameplay_markers,
            authored_gameplay_marker_geometry,
            authored_room_outline_geometry,
            authored_terrain_walkability_overlay,
        )
        self._sync_room_preview_model(authored_room_preview_model)
        self._sync_room_outline_overlay(authored_room_outline_geometry)
        self._sync_marker_geometry_overlay(authored_gameplay_marker_geometry)
        self._sync_terrain_walkability_overlay(authored_terrain_walkability_overlay)
        self._sync_clean_viewport_presentation()

    def select_id(self, item_id: str) -> None:
        for row, row_id in enumerate(self._row_ids):
            if row_id == item_id:
                blocked = self.scene_table.blockSignals(True)
                self.scene_table.selectRow(row)
                self.scene_table.blockSignals(blocked)
                break

    def set_view_mode(self, mode: str) -> None:
        renderer = getattr(self.viewport, "_renderer", None)
        if renderer is None:
            return
        lower = mode.lower()
        if "wire" in lower:
            setattr(renderer, "wireframe", True)
        if "textured" in lower:
            setattr(renderer, "show_texture", True)
        if "walkmesh" in lower and hasattr(self.viewport, "walkmesh_button"):
            self.viewport.walkmesh_button.setChecked(True)
        request = getattr(self.viewport, "_request_render", None)
        if callable(request):
            request()

    def focus_selected(self) -> None:
        if hasattr(self.viewport, "frame_all"):
            self.viewport.frame_all()

    def set_navigation_profile(self, profile: object) -> None:
        if hasattr(self.viewport, "set_navigation_profile"):
            self.viewport.set_navigation_profile(profile)

    def set_renderer_settings(self, settings: object) -> None:
        if hasattr(self.viewport, "set_renderer_settings"):
            self.viewport.set_renderer_settings(settings)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802 - Qt API
        if self._is_marker_pick_event_source(watched):
            event_type = event.type()
            if event_type in {QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease}:
                key = getattr(event, "key", lambda: None)()
                if event_type == QtCore.QEvent.KeyPress and self._handle_map_studio_shortcut_key(event):
                    return True
                if key == QtCore.Qt.Key_V:
                    self.set_map_studio_modifier_active("vertex_snap", event_type == QtCore.QEvent.KeyPress)
                    return False
                if key == QtCore.Qt.Key_J:
                    self.set_map_studio_modifier_active("transform_snap_level", event_type == QtCore.QEvent.KeyPress)
                    return False
            if event_type == QtCore.QEvent.MouseButtonPress:
                if getattr(event, "button", lambda: None)() == QtCore.Qt.RightButton:
                    modifiers = getattr(event, "modifiers", lambda: QtCore.Qt.NoModifier)()
                    if (
                        self._terrain_brush_context_enabled()
                        and bool(modifiers & QtCore.Qt.AltModifier)
                    ):
                        focus = getattr(watched, "setFocus", None)
                        if callable(focus):
                            focus()
                        return self._begin_terrain_brush_option_drag(event)
                    focus = getattr(watched, "setFocus", None)
                    if callable(focus):
                        focus()
                    if bool(modifiers & QtCore.Qt.ShiftModifier):
                        self.toolMarkingMenuRequested.emit(self._event_global_position(event, watched))
                    else:
                        self.modeMarkingMenuRequested.emit(self._event_global_position(event, watched))
                    return True
                if getattr(event, "button", lambda: None)() == QtCore.Qt.LeftButton:
                    focus = getattr(watched, "setFocus", None)
                    if callable(focus):
                        focus()
                    if self._terrain_brush_context_enabled():
                        terrain_sample = self._terrain_sample_at_event(event)
                        if terrain_sample is not None:
                            self._begin_terrain_brush_drag(terrain_sample, event)
                        return True
                    placement_id = self._marker_at_event(event)
                    if placement_id:
                        self.select_id(placement_id)
                        self.itemSelected.emit(placement_id)
                        self._begin_marker_drag(placement_id, event)
                        return True
                    room_primitive = self._room_primitive_at_event(event)
                    if room_primitive is not None:
                        self._begin_room_primitive_drag(room_primitive, event)
                        return True
                    room_point = self._room_outline_point_at_event(event)
                    if room_point is not None:
                        self._begin_room_outline_point_drag(room_point, event)
                        return True
                    room_edge = self._room_outline_edge_at_event(event)
                    if room_edge is not None:
                        self._select_room_outline_edge(room_edge)
                        return True
            if event_type == QtCore.QEvent.MouseMove and self._marker_drag is not None:
                buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                if not (buttons & QtCore.Qt.LeftButton):
                    return self._finish_marker_drag(event)
                self._update_marker_drag(event)
                return True
            if event_type == QtCore.QEvent.MouseMove and self._room_outline_point_drag is not None:
                buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                if not (buttons & QtCore.Qt.LeftButton):
                    return self._finish_room_outline_point_drag(event)
                self._update_room_outline_point_drag(event)
                return True
            if event_type == QtCore.QEvent.MouseMove and self._room_primitive_drag is not None:
                buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                if not (buttons & QtCore.Qt.LeftButton):
                    return self._finish_room_primitive_drag(event)
                self._update_room_primitive_drag(event)
                return True
            if event_type == QtCore.QEvent.MouseMove and self._terrain_brush_option_drag is not None:
                buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                if not (buttons & QtCore.Qt.RightButton):
                    return self._finish_terrain_brush_option_drag(event)
                self._update_terrain_brush_option_drag(event)
                return True
            if event_type == QtCore.QEvent.MouseMove and self._terrain_brush_drag is not None:
                buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                if not (buttons & QtCore.Qt.LeftButton):
                    return self._finish_terrain_brush_drag(event)
                self._update_terrain_brush_drag(event)
                return True
            if event_type == QtCore.QEvent.MouseMove and self._terrain_brush_context_enabled():
                buttons = getattr(event, "buttons", lambda: QtCore.Qt.NoButton)()
                if buttons & QtCore.Qt.LeftButton:
                    terrain_sample = self._terrain_sample_at_event(event)
                    if terrain_sample is not None:
                        self._begin_terrain_brush_drag(terrain_sample, event)
                    return True
                self._terrain_sample_at_event(event)
            if event_type == QtCore.QEvent.MouseButtonRelease and self._marker_drag is not None:
                return self._finish_marker_drag(event)
            if event_type == QtCore.QEvent.MouseButtonRelease and self._room_outline_point_drag is not None:
                return self._finish_room_outline_point_drag(event)
            if event_type == QtCore.QEvent.MouseButtonRelease and self._room_primitive_drag is not None:
                return self._finish_room_primitive_drag(event)
            if event_type == QtCore.QEvent.MouseButtonRelease and self._terrain_brush_option_drag is not None:
                return self._finish_terrain_brush_option_drag(event)
            if event_type == QtCore.QEvent.MouseButtonRelease and self._terrain_brush_drag is not None:
                return self._finish_terrain_brush_drag(event)
            if event_type == QtCore.QEvent.MouseButtonRelease and self._terrain_brush_context_enabled():
                return True
        toolbar_scroll = getattr(self.viewport, "viewport_toolbar_scroll", None)
        if watched is toolbar_scroll and event.type() in {
            QtCore.QEvent.Resize,
            QtCore.QEvent.Show,
            QtCore.QEvent.LayoutRequest,
        }:
            QtCore.QTimer.singleShot(0, self._ensure_embedded_viewport_toolbar_gap)
        return super().eventFilter(watched, event)

    def active_map_studio_modifier(self) -> str:
        """Return the currently held Maya-style Map Studio viewport modifier."""

        if bool(self._vertex_snap_modifier_active):
            return "vertex_snap"
        if bool(self._transform_snap_modifier_active):
            return "transform_snap_level"
        return ""

    def set_map_studio_modifier_active(self, action_key: str, active: bool) -> None:
        """Set the current hold-style viewport modifier without owning command policy."""

        key = str(action_key or "").strip()
        enabled = bool(active)
        if key == "vertex_snap":
            self._vertex_snap_modifier_active = enabled
            if self._room_outline_point_drag is not None:
                if enabled:
                    self._request_room_outline_snap_preview_for_drag()
                else:
                    self._clear_room_outline_snap_highlight()
            self._sync_clean_viewport_presentation()
            return
        if key == "transform_snap_level":
            self._transform_snap_modifier_active = enabled
            if enabled:
                self.marker_summary_label.setText(
                    "Transform Level Snap active: selected vertices/edges will align to one level when the transform is committed."
                )
            else:
                self._restore_marker_summary_after_transform_snap()
            self._sync_clean_viewport_presentation()

    def _install_marker_pick_filters(self) -> None:
        viewport = getattr(self, "viewport", None)
        if viewport is not None:
            setattr(viewport, "_gr_map_studio_viewport_input_handler", self._handle_map_studio_viewport_input_event)
        candidates = [viewport, getattr(viewport, "canvas", None)]
        canvas = getattr(getattr(self, "viewport", None), "canvas", None)
        current_surface = getattr(canvas, "current_surface", lambda: None)() if canvas is not None else None
        candidates.append(current_surface)
        for root in (viewport, canvas, current_surface):
            if isinstance(root, QtWidgets.QWidget):
                candidates.extend(root.findChildren(QtWidgets.QWidget))
        for candidate in candidates:
            if candidate is None:
                continue
            key = id(candidate)
            if key in self._marker_pick_filter_ids:
                continue
            try:
                candidate.installEventFilter(self)
                if hasattr(candidate, "setFocusPolicy"):
                    candidate.setFocusPolicy(QtCore.Qt.StrongFocus)
            except Exception:
                continue
            self._marker_pick_filter_ids.add(key)

    def _is_marker_pick_event_source(self, watched: QtCore.QObject) -> bool:
        canvas = getattr(self.viewport, "canvas", None)
        if watched is self.viewport or watched is canvas:
            return True
        current_surface = getattr(canvas, "current_surface", lambda: None)() if canvas is not None else None
        if watched is current_surface:
            return True
        if isinstance(watched, QtWidgets.QWidget):
            for root in (self.viewport, canvas, current_surface):
                if isinstance(root, QtWidgets.QWidget) and watched is not root and root.isAncestorOf(watched):
                    return True
        return False

    def _handle_map_studio_viewport_input_event(
        self,
        event: QtCore.QEvent,
        watched: QtCore.QObject | None = None,
    ) -> bool:
        """Allow the embedded shared viewport to delegate Map Studio-only input first."""

        return bool(self.eventFilter(watched or getattr(self.viewport, "canvas", None), event))

    def _marker_at_event(self, event: QtCore.QEvent) -> str:
        marker_at_screen = getattr(self.viewport, "map_studio_marker_at_screen", None)
        if not callable(marker_at_screen):
            return ""
        pos_fn = getattr(event, "position", None)
        pos = pos_fn() if callable(pos_fn) else getattr(event, "pos", lambda: None)()
        if pos is None:
            return ""
        return str(marker_at_screen(float(pos.x()), float(pos.y())) or "")

    def _room_outline_point_at_event(self, event: QtCore.QEvent) -> tuple[str, int, tuple[float, float, float]] | None:
        point_at_screen = getattr(self.viewport, "map_studio_room_outline_point_at_screen", None)
        if not callable(point_at_screen):
            return None
        pos_fn = getattr(event, "position", None)
        pos = pos_fn() if callable(pos_fn) else getattr(event, "pos", lambda: None)()
        if pos is None:
            return None
        hit = point_at_screen(float(pos.x()), float(pos.y()))
        if not hit or len(hit) < 3:
            return None
        room_resref = str(hit[0] or "")
        point_index = int(hit[1])
        world_point = tuple(float(value) for value in tuple(hit[2])[:3])
        if not room_resref or point_index < 0 or len(world_point) < 3:
            return None
        return (room_resref, point_index, world_point)

    def _room_outline_edge_at_event(
        self,
        event: QtCore.QEvent,
    ) -> tuple[str, int, tuple[float, float, float], tuple[float, float, float]] | None:
        edge_at_screen = getattr(self.viewport, "map_studio_room_outline_edge_at_screen", None)
        if not callable(edge_at_screen):
            return None
        pos_fn = getattr(event, "position", None)
        pos = pos_fn() if callable(pos_fn) else getattr(event, "pos", lambda: None)()
        if pos is None:
            return None
        hit = edge_at_screen(float(pos.x()), float(pos.y()))
        if not hit or len(hit) < 4:
            return None
        room_resref = str(hit[0] or "")
        edge_index = int(hit[1])
        world_start = tuple(float(value) for value in tuple(hit[2])[:3])
        world_end = tuple(float(value) for value in tuple(hit[3])[:3])
        if not room_resref or edge_index < 0 or len(world_start) < 3 or len(world_end) < 3:
            return None
        return (room_resref, edge_index, world_start, world_end)

    def _room_primitive_at_event(self, event: QtCore.QEvent) -> tuple[str, str, tuple[float, float, float]] | None:
        primitive_at_screen = getattr(self.viewport, "map_studio_room_primitive_at_screen", None)
        if not callable(primitive_at_screen):
            return None
        pos_fn = getattr(event, "position", None)
        pos = pos_fn() if callable(pos_fn) else getattr(event, "pos", lambda: None)()
        if pos is None:
            return None
        hit = primitive_at_screen(float(pos.x()), float(pos.y()))
        if not hit or len(hit) < 3:
            return None
        room_resref = str(hit[0] or "")
        primitive_name = str(hit[1] or "")
        world_center = tuple(float(value) for value in tuple(hit[2])[:3])
        if not room_resref or not primitive_name or len(world_center) < 3:
            return None
        return (room_resref, primitive_name, world_center)

    def set_terrain_brush_interaction(
        self,
        *,
        enabled: bool | None = None,
        room_resref: str = "",
        brush: str = "",
        row_count: int = 0,
        column_count: int = 0,
        radius: int = 0,
        hardness: float | None = None,
    ) -> None:
        """Update the viewport terrain brush context from the Builder controls."""

        current_enabled = bool(self._terrain_brush_context.get("enabled", False))
        if enabled is None:
            enabled = current_enabled
        self._terrain_brush_context = {
            "enabled": bool(enabled),
            "room_resref": str(room_resref or "").strip(),
            "brush": str(brush or "").strip(),
            "row_count": max(0, int(row_count)),
            "column_count": max(0, int(column_count)),
            "radius": max(0, int(radius)),
            "hardness": self._clamp_terrain_brush_hardness(
                self._terrain_brush_context.get("hardness", 0.5) if hardness is None else hardness
            ),
        }
        blocked = self.terrain_brush_box.blockSignals(True)
        self.terrain_brush_box.setChecked(bool(enabled))
        self.terrain_brush_box.blockSignals(blocked)
        if bool(enabled):
            self._install_marker_pick_filters()
        if not self._terrain_brush_context_enabled():
            self._clear_terrain_brush_cursor()
        self._sync_clean_viewport_presentation()

    def set_terrain_walkability_overlay(self, authored_terrain_walkability_overlay=None) -> None:
        """Refresh only the terrain overlay during live sculpting."""

        self._terrain_walkability_overlay = authored_terrain_walkability_overlay
        self._sync_terrain_walkability_overlay(authored_terrain_walkability_overlay)
        self._sync_clean_viewport_presentation()

    def set_universal_transform_overlay(self, overlay=None) -> None:
        """Refresh the Universal Manipulator overlay for the selected primitive."""

        self._universal_transform_overlay = overlay
        self._sync_universal_transform_overlay(overlay)
        self._sync_clean_viewport_presentation()

    def _toggle_terrain_brush_interaction(self, enabled: bool) -> None:
        self._terrain_brush_context["enabled"] = bool(enabled)
        if not enabled and self._terrain_brush_drag is not None:
            self._finish_terrain_brush_drag(None)
        if not enabled:
            self._clear_terrain_brush_cursor()
        self._sync_clean_viewport_presentation()

    def _terrain_brush_context_enabled(self) -> bool:
        context = self._terrain_brush_context
        return (
            bool(context.get("enabled", False))
            and bool(str(context.get("room_resref", "") or "").strip())
            and bool(str(context.get("brush", "") or "").strip())
            and int(context.get("row_count", 0) or 0) > 1
            and int(context.get("column_count", 0) or 0) > 1
        )

    def _terrain_sample_at_event(self, event: QtCore.QEvent) -> tuple[int, int, float] | None:
        screen = self._event_position(event)
        if screen is None:
            return None
        world = self._terrain_world_at_screen(screen[0], screen[1])
        if world is None:
            self._clear_terrain_brush_cursor()
            return None
        sample = self._terrain_world_to_sample(world)
        if sample is None:
            self._clear_terrain_brush_cursor()
            return None
        self._set_terrain_brush_cursor(world, sample)
        return sample

    def _terrain_world_at_screen(self, screen_x: float, screen_y: float) -> tuple[float, float, float] | None:
        overlay = self._terrain_walkability_overlay
        if overlay is None:
            return None
        project = getattr(getattr(self.viewport, "_renderer", None), "_proj", None)
        if not callable(project):
            return None
        wanted = str(self._terrain_brush_context.get("room_resref", "") or "").strip().lower()
        w, h = self._viewport_canvas_size()
        nearest: tuple[float, tuple[float, float, float]] | None = None
        for triangle in tuple(getattr(overlay, "triangles", ()) or ()):
            room_resref = str(getattr(triangle, "room_resref", "") or "").strip().lower()
            if wanted and room_resref != wanted:
                continue
            points = tuple(getattr(triangle, "points", ()) or ())
            if len(points) < 3:
                continue
            projected: list[tuple[float, float]] = []
            world_points: list[tuple[float, float, float]] = []
            for point in points[:3]:
                try:
                    wx, wy, wz = (float(point[0]), float(point[1]), float(point[2]))
                    sx, sy = project(wx, wy, wz, w, h)[:2]
                except Exception:
                    projected = []
                    break
                projected.append((float(sx), float(sy)))
                world_points.append((wx, wy, wz))
            if len(projected) < 3 or len(world_points) < 3:
                continue
            bary = self._screen_triangle_barycentric((screen_x, screen_y), projected)
            if bary is not None and min(bary) >= -0.025:
                return (
                    world_points[0][0] * bary[0] + world_points[1][0] * bary[1] + world_points[2][0] * bary[2],
                    world_points[0][1] * bary[0] + world_points[1][1] * bary[1] + world_points[2][1] * bary[2],
                    world_points[0][2] * bary[0] + world_points[1][2] * bary[1] + world_points[2][2] * bary[2],
                )
            center_x = sum(point[0] for point in projected) / 3.0
            center_y = sum(point[1] for point in projected) / 3.0
            distance_sq = (float(screen_x) - center_x) ** 2 + (float(screen_y) - center_y) ** 2
            center_world = (
                sum(point[0] for point in world_points) / 3.0,
                sum(point[1] for point in world_points) / 3.0,
                sum(point[2] for point in world_points) / 3.0,
            )
            if nearest is None or distance_sq < nearest[0]:
                nearest = (distance_sq, center_world)
        if nearest is not None and nearest[0] <= 900.0:
            return nearest[1]
        return None

    def _screen_triangle_barycentric(
        self,
        point: tuple[float, float],
        triangle: list[tuple[float, float]],
    ) -> tuple[float, float, float] | None:
        (px, py) = point
        (ax, ay), (bx, by), (cx, cy) = triangle[:3]
        denominator = ((by - cy) * (ax - cx)) + ((cx - bx) * (ay - cy))
        if abs(denominator) <= 1.0e-6:
            return None
        u = (((by - cy) * (px - cx)) + ((cx - bx) * (py - cy))) / denominator
        v = (((cy - ay) * (px - cx)) + ((ax - cx) * (py - cy))) / denominator
        w = 1.0 - u - v
        return (float(u), float(v), float(w))

    def _terrain_world_to_sample(self, world: tuple[float, float, float]) -> tuple[int, int, float] | None:
        bounds = self._terrain_room_world_bounds()
        if bounds is None:
            return None
        min_x, max_x, min_y, max_y = bounds
        context = self._terrain_brush_context
        row_count = int(context.get("row_count", 0) or 0)
        column_count = int(context.get("column_count", 0) or 0)
        if row_count <= 1 or column_count <= 1:
            return None
        width = max(1.0e-6, max_x - min_x)
        depth = max(1.0e-6, max_y - min_y)
        column = round(((float(world[0]) - min_x) / width) * float(column_count - 1))
        row = round(((float(world[1]) - min_y) / depth) * float(row_count - 1))
        return (
            max(0, min(row_count - 1, int(row))),
            max(0, min(column_count - 1, int(column))),
            1.0,
        )

    def _terrain_world_brush_radius(self) -> float:
        bounds = self._terrain_room_world_bounds()
        if bounds is None:
            return 1.0
        min_x, max_x, min_y, max_y = bounds
        context = self._terrain_brush_context
        row_count = max(2, int(context.get("row_count", 0) or 0))
        column_count = max(2, int(context.get("column_count", 0) or 0))
        radius_samples = max(0, int(context.get("radius", 0) or 0))
        cell_width = abs(float(max_x) - float(min_x)) / float(max(1, column_count - 1))
        cell_depth = abs(float(max_y) - float(min_y)) / float(max(1, row_count - 1))
        return max(cell_width, cell_depth, 0.25) * float(radius_samples + 0.65)

    def _set_terrain_brush_cursor(self, world: tuple[float, float, float], sample: tuple[int, int, float]) -> None:
        setter = getattr(self.viewport, "set_map_studio_terrain_brush_cursor", None)
        if not callable(setter):
            return
        radius = self._terrain_world_brush_radius()
        room_resref = str(self._terrain_brush_context.get("room_resref", "") or "")
        brush = str(self._terrain_brush_context.get("brush", "") or "")
        setter(
            {
                "room_resref": room_resref,
                "brush": brush,
                "sample": (int(sample[0]), int(sample[1])),
                "world_position": (float(world[0]), float(world[1]), float(world[2]) + 0.035),
                "world_radius_position": (float(world[0]) + radius, float(world[1]), float(world[2]) + 0.035),
                "radius_samples": max(0, int(self._terrain_brush_context.get("radius", 0) or 0)),
                "hardness": self._clamp_terrain_brush_hardness(self._terrain_brush_context.get("hardness", 0.5)),
                "color": "#00ff7a" if brush not in {"lower"} else "#55a7ff",
            }
        )

    def _clear_terrain_brush_cursor(self) -> None:
        clearer = getattr(self.viewport, "clear_map_studio_terrain_brush_cursor", None)
        if callable(clearer):
            clearer()

    def _terrain_room_world_bounds(self) -> tuple[float, float, float, float] | None:
        overlay = self._terrain_walkability_overlay
        if overlay is None:
            return None
        wanted = str(self._terrain_brush_context.get("room_resref", "") or "").strip().lower()
        xs: list[float] = []
        ys: list[float] = []
        for triangle in tuple(getattr(overlay, "triangles", ()) or ()):
            room_resref = str(getattr(triangle, "room_resref", "") or "").strip().lower()
            if wanted and room_resref != wanted:
                continue
            for point in tuple(getattr(triangle, "points", ()) or ()):
                if len(point) < 2:
                    continue
                xs.append(float(point[0]))
                ys.append(float(point[1]))
        if not xs or not ys:
            return None
        return (min(xs), max(xs), min(ys), max(ys))

    def _begin_terrain_brush_drag(self, sample: tuple[int, int, float], event: QtCore.QEvent) -> bool:
        room_resref = str(self._terrain_brush_context.get("room_resref", "") or "").strip()
        brush = str(self._terrain_brush_context.get("brush", "") or "").strip()
        if not room_resref or not brush:
            return False
        self._terrain_brush_drag = {
            "room_resref": room_resref,
            "brush": brush,
            "points": [sample],
            "last_sample": sample[:2],
            "active": True,
        }
        self.terrainBrushFrameRequested.emit(brush, room_resref, (sample,))
        return True

    def _begin_terrain_brush_option_drag(self, event: QtCore.QEvent) -> bool:
        start = self._event_position(event)
        if start is None:
            return False
        self._terrain_brush_option_drag = {
            "start_screen": start,
            "start_radius": max(0, int(self._terrain_brush_context.get("radius", 0) or 0)),
            "start_hardness": self._clamp_terrain_brush_hardness(self._terrain_brush_context.get("hardness", 0.5)),
        }
        self._update_terrain_brush_option_drag(event)
        return True

    def _update_terrain_brush_option_drag(self, event: QtCore.QEvent) -> bool:
        if self._terrain_brush_option_drag is None:
            return False
        current = self._event_position(event)
        if current is None:
            return True
        start = self._terrain_brush_option_drag.get("start_screen", current)
        dx = float(current[0]) - float(start[0])
        dy = float(current[1]) - float(start[1])
        start_radius = int(self._terrain_brush_option_drag.get("start_radius", 0) or 0)
        start_hardness = self._clamp_terrain_brush_hardness(self._terrain_brush_option_drag.get("start_hardness", 0.5))
        radius = max(0, min(64, start_radius + int(round(dx / 16.0))))
        hardness = self._clamp_terrain_brush_hardness(start_hardness - (dy / 180.0))
        self._terrain_brush_context["radius"] = radius
        self._terrain_brush_context["hardness"] = hardness
        self.marker_summary_label.setText(f"Terrain brush: size {radius}, hardness {hardness:.2f}")
        self.terrainBrushOptionsChanged.emit(radius, hardness)
        return True

    def _finish_terrain_brush_option_drag(self, event: QtCore.QEvent | None = None) -> bool:
        if self._terrain_brush_option_drag is None:
            return False
        if event is not None:
            self._update_terrain_brush_option_drag(event)
        self._terrain_brush_option_drag = None
        return True

    @staticmethod
    def _clamp_terrain_brush_hardness(value: object) -> float:
        try:
            hardness = float(value)
        except (TypeError, ValueError):
            hardness = 0.5
        if not math.isfinite(hardness):
            hardness = 0.5
        return max(0.0, min(1.0, hardness))

    def _update_terrain_brush_drag(self, event: QtCore.QEvent) -> bool:
        if self._terrain_brush_drag is None:
            return False
        sample = self._terrain_sample_at_event(event)
        if sample is None:
            return True
        key = sample[:2]
        points = list(self._terrain_brush_drag.get("points", []) or [])
        if key != self._terrain_brush_drag.get("last_sample"):
            points.append(sample)
        elif points:
            points[-1] = sample
        points = points[-32:]
        self._terrain_brush_drag["points"] = points
        self._terrain_brush_drag["last_sample"] = key
        brush = str(self._terrain_brush_drag.get("brush", "") or "")
        room_resref = str(self._terrain_brush_drag.get("room_resref", "") or "")
        self.terrainBrushFrameRequested.emit(brush, room_resref, tuple(points))
        return True

    def _finish_terrain_brush_drag(self, event: QtCore.QEvent | None = None) -> bool:
        if self._terrain_brush_drag is None:
            return False
        if event is not None:
            self._update_terrain_brush_drag(event)
        drag = self._terrain_brush_drag
        self._terrain_brush_drag = None
        if bool(drag.get("active", False)):
            self.terrainBrushStrokeCommitted.emit(
                str(drag.get("brush", "") or ""),
                str(drag.get("room_resref", "") or ""),
            )
        return True

    def _event_position(self, event: QtCore.QEvent) -> tuple[float, float] | None:
        pos_fn = getattr(event, "position", None)
        pos = pos_fn() if callable(pos_fn) else getattr(event, "pos", lambda: None)()
        if pos is None:
            return None
        return (float(pos.x()), float(pos.y()))

    def _event_global_position(self, event: QtCore.QEvent, watched: QtCore.QObject | None = None) -> QtCore.QPoint:
        global_position = getattr(event, "globalPosition", None)
        if callable(global_position):
            pos = global_position()
            try:
                return pos.toPoint()
            except Exception:
                return QtCore.QPoint(int(pos.x()), int(pos.y()))
        global_pos = getattr(event, "globalPos", None)
        if callable(global_pos):
            return global_pos()
        local = self._event_position(event)
        mapper = getattr(watched, "mapToGlobal", None)
        if local is not None and callable(mapper):
            return mapper(QtCore.QPoint(int(round(local[0])), int(round(local[1]))))
        return self.mapToGlobal(QtCore.QPoint(0, 0))

    def _begin_marker_drag(self, placement_id: str, event: QtCore.QEvent) -> bool:
        marker = self._placement_markers.get(str(placement_id))
        start_screen = self._event_position(event)
        if marker is None or start_screen is None:
            self._marker_drag = None
            return False
        self._marker_drag = {
            "placement_id": str(placement_id),
            "start_screen": start_screen,
            "start_position": self._marker_position(marker),
            "bearing": float(getattr(marker, "bearing", 0.0) or 0.0),
            "active": False,
            "pending_position": self._marker_position(marker),
        }
        self._sync_clean_viewport_presentation()
        return True

    def _update_marker_drag(self, event: QtCore.QEvent) -> bool:
        if self._marker_drag is None:
            return False
        current = self._event_position(event)
        if current is None:
            return False
        start = self._marker_drag.get("start_screen", current)
        screen_dx = float(current[0]) - float(start[0])
        screen_dy = float(current[1]) - float(start[1])
        if screen_dx * screen_dx + screen_dy * screen_dy < 9.0:
            return True
        pending = self._drag_marker_position(screen_dx, screen_dy)
        if pending is not None:
            self._marker_drag["active"] = True
            self._marker_drag["pending_position"] = pending
        return True

    def _finish_marker_drag(self, event: QtCore.QEvent | None = None) -> bool:
        if self._marker_drag is None:
            return False
        if event is not None:
            self._update_marker_drag(event)
        drag = self._marker_drag
        self._marker_drag = None
        self._sync_clean_viewport_presentation()
        if not bool(drag.get("active", False)):
            return True
        position = tuple(float(v) for v in tuple(drag.get("pending_position", drag.get("start_position", (0.0, 0.0, 0.0))))[:3])
        if len(position) < 3:
            return True
        bearing = float(drag.get("bearing", 0.0) or 0.0)
        self.transformEdited.emit(
            str(drag.get("placement_id", "") or ""),
            LevelTransform(position=position, rotation=(0.0, 0.0, bearing), scale=(1.0, 1.0, 1.0)),
        )
        return True

    def _begin_room_outline_point_drag(self, hit: tuple[str, int, tuple[float, float, float]], event: QtCore.QEvent) -> bool:
        start_screen = self._event_position(event)
        if start_screen is None:
            self._room_outline_point_drag = None
            return False
        room_resref, point_index, world_point = hit
        self._room_outline_point_drag = {
            "room_resref": room_resref,
            "point_index": int(point_index),
            "start_screen": start_screen,
            "start_position": world_point,
            "active": False,
            "pending_position": world_point,
        }
        self._request_room_outline_snap_preview_for_drag()
        self._sync_clean_viewport_presentation()
        return True

    def _update_room_outline_point_drag(self, event: QtCore.QEvent) -> bool:
        if self._room_outline_point_drag is None:
            return False
        current = self._event_position(event)
        if current is None:
            return False
        start = self._room_outline_point_drag.get("start_screen", current)
        screen_dx = float(current[0]) - float(start[0])
        screen_dy = float(current[1]) - float(start[1])
        if screen_dx * screen_dx + screen_dy * screen_dy < 9.0:
            return True
        start_position = tuple(self._room_outline_point_drag.get("start_position", (0.0, 0.0, 0.0)))
        if len(start_position) < 3:
            return False
        world_dx, world_dy = self._screen_delta_to_floor_delta(start_position, screen_dx, screen_dy)
        pending = self._snap_map_studio_position(
            (float(start_position[0]) + world_dx, float(start_position[1]) + world_dy, float(start_position[2]))
        )
        candidate = self._active_room_outline_snap_candidate()
        if candidate is not None:
            candidate_position = self._candidate_world_position(candidate)
            if candidate_position is not None:
                pending = candidate_position
                self._room_outline_point_drag["pending_snap_candidate"] = candidate
                self._set_room_outline_snap_highlight_for_candidate(candidate)
        else:
            self._room_outline_point_drag.pop("pending_snap_candidate", None)
            self._clear_room_outline_snap_highlight()
        self._room_outline_point_drag["active"] = True
        self._room_outline_point_drag["pending_position"] = pending
        return True

    def _finish_room_outline_point_drag(self, event: QtCore.QEvent | None = None) -> bool:
        if self._room_outline_point_drag is None:
            return False
        if event is not None:
            self._update_room_outline_point_drag(event)
        drag = self._room_outline_point_drag
        self._room_outline_point_drag = None
        self._clear_room_outline_snap_highlight()
        self._sync_clean_viewport_presentation()
        if not bool(drag.get("active", False)):
            return True
        snap_candidate = drag.get("pending_snap_candidate") if bool(self._vertex_snap_modifier_active) else None
        if snap_candidate is not None:
            target_room = str(getattr(snap_candidate, "room_resref", "") or "")
            target_point = int(getattr(snap_candidate, "point_index", -1) or -1)
            if target_room and target_point >= 0:
                self.roomOutlinePointSnapped.emit(
                    str(drag.get("room_resref", "") or ""),
                    int(drag.get("point_index", -1)),
                    target_point,
                    target_room,
                )
                return True
        position = tuple(float(v) for v in tuple(drag.get("pending_position", drag.get("start_position", (0.0, 0.0, 0.0))))[:3])
        if len(position) < 3:
            return True
        self.roomOutlinePointEdited.emit(
            str(drag.get("room_resref", "") or ""),
            int(drag.get("point_index", -1)),
            position,
        )
        return True

    def _request_room_outline_snap_preview_for_drag(self) -> None:
        if self._room_outline_point_drag is None:
            return
        room_resref = str(self._room_outline_point_drag.get("room_resref", "") or "")
        point_index = int(self._room_outline_point_drag.get("point_index", -1))
        if room_resref and point_index >= 0:
            self.roomOutlinePointSnapPreviewRequested.emit(room_resref, point_index)

    def set_room_outline_vertex_snap_candidates(self, room_resref: str, point_index: int, candidates) -> None:
        """Cache controller-provided snap targets for the active outline drag."""

        key = (str(room_resref or "").strip(), int(point_index))
        items = tuple(candidates or ())
        self._room_outline_vertex_snap_candidates[key] = items
        if self._room_outline_point_drag is not None and self._active_room_outline_snap_candidate() is not None:
            nearest = self._active_room_outline_snap_candidate()
            target_room = str(getattr(nearest, "room_resref", "") or "")
            target_point = int(getattr(nearest, "point_index", -1) or -1)
            distance = float(getattr(nearest, "distance", 0.0) or 0.0)
            self._set_room_outline_snap_highlight_for_candidate(nearest)
            self.marker_summary_label.setText(
                f"Vertex snap target: {target_room} point {target_point} ({distance:.3f} m). Release while holding V to commit."
            )
        else:
            self._clear_room_outline_snap_highlight()

    def _active_room_outline_snap_candidate(self):
        if not bool(self._vertex_snap_modifier_active) or self._room_outline_point_drag is None:
            return None
        room_resref = str(self._room_outline_point_drag.get("room_resref", "") or "")
        point_index = int(self._room_outline_point_drag.get("point_index", -1))
        candidates = self._room_outline_vertex_snap_candidates.get((room_resref, point_index), ())
        return candidates[0] if candidates else None

    @staticmethod
    def _candidate_world_position(candidate) -> tuple[float, float, float] | None:
        position = tuple(getattr(candidate, "world_position", ()) or ())
        if len(position) < 3:
            return None
        return (float(position[0]), float(position[1]), float(position[2]))

    def _set_room_outline_snap_highlight_for_candidate(self, candidate) -> None:
        position = self._candidate_world_position(candidate)
        setter = getattr(self.viewport, "set_map_studio_room_outline_snap_highlight", None)
        if position is None or not callable(setter):
            self._clear_room_outline_snap_highlight()
            return
        target_room = str(getattr(candidate, "room_resref", "") or "")
        target_point = int(getattr(candidate, "point_index", -1) or -1)
        distance = float(getattr(candidate, "distance", 0.0) or 0.0)
        setter(
            {
                "world_position": position,
                "room_resref": target_room,
                "point_index": target_point,
                "label": f"Snap {target_room}:{target_point} ({distance:.3f} m)",
                "color": "#ffd84a",
            }
        )

    def _clear_room_outline_snap_highlight(self) -> None:
        clearer = getattr(self.viewport, "clear_map_studio_room_outline_snap_highlight", None)
        setter = getattr(self.viewport, "set_map_studio_room_outline_snap_highlight", None)
        if callable(clearer):
            clearer()
        elif callable(setter):
            setter(None)

    def transform_snap_modifier_active(self) -> bool:
        """Return whether Map Studio's hold-J transform snap modifier is active."""

        return bool(self._transform_snap_modifier_active)

    def _restore_marker_summary_after_transform_snap(self) -> None:
        count = len(self._placement_markers)
        self.marker_summary_label.setText(f"Gameplay markers: {count}" if count else "Gameplay markers: none")

    def set_transform_gizmo_mode(self, mode_key: str, *, announce: bool = True) -> None:
        """Set the visible Map Studio transform gizmo mode and sync the shared viewport."""

        key = str(mode_key or "translate").strip().lower()
        if key in {"move", "translate"}:
            key = "translate"
            gimbal_mode = 1
        elif key in {"rotate", "rotation"}:
            key = "rotate"
            gimbal_mode = 2
        elif key in {"scale", "transform"}:
            key = "scale"
            gimbal_mode = 3
        else:
            key = "translate"
            gimbal_mode = 1
        self._transform_gizmo_mode = key
        for button, button_key in (
            (getattr(self, "translate_gizmo_button", None), "translate"),
            (getattr(self, "rotate_gizmo_button", None), "rotate"),
            (getattr(self, "scale_gizmo_button", None), "scale"),
        ):
            if button is None:
                continue
            blocked = button.blockSignals(True)
            button.setChecked(button_key == key)
            button.blockSignals(blocked)
        viewport = getattr(self, "viewport", None)
        if viewport is not None:
            setattr(viewport, "_map_studio_transform_gizmo_mode", key)
            setter = getattr(viewport, "set_gimbal_mode", None)
            if callable(setter):
                setter(gimbal_mode)
            else:
                request = getattr(viewport, "_request_render", None)
                if callable(request):
                    request(fast=True)
        self._sync_clean_viewport_presentation()
        if announce:
            label = {"translate": "Translate", "rotate": "Rotate", "scale": "Scale"}[key]
            self.marker_summary_label.setText(f"Map Studio {label} gimbal active. W/E/R switches Translate, Rotate, and Scale.")
            self.transformGizmoModeChanged.emit(key)

    def transform_gizmo_mode(self) -> str:
        return str(getattr(self, "_transform_gizmo_mode", "translate") or "translate")

    def _handle_map_studio_shortcut_key(self, event: QtCore.QEvent) -> bool:
        modifiers = getattr(event, "modifiers", lambda: QtCore.Qt.NoModifier)()
        key = getattr(event, "key", lambda: None)()
        ctrl = bool(modifiers & QtCore.Qt.ControlModifier)
        alt = bool(modifiers & QtCore.Qt.AltModifier)
        shift = bool(modifiers & QtCore.Qt.ShiftModifier)
        if ctrl and not alt and key == QtCore.Qt.Key_Z:
            self.undoShortcutRequested.emit()
            return True
        if ctrl and not alt and key == QtCore.Qt.Key_R:
            self.redoShortcutRequested.emit()
            return True
        if ctrl or alt or shift:
            return False
        if key == QtCore.Qt.Key_Delete:
            self.deleteShortcutRequested.emit()
            return True
        if key == QtCore.Qt.Key_W:
            self.set_transform_gizmo_mode("translate")
            return True
        if key == QtCore.Qt.Key_E:
            self.set_transform_gizmo_mode("rotate")
            return True
        if key == QtCore.Qt.Key_R:
            self.set_transform_gizmo_mode("scale")
            return True
        return False

    def _select_room_outline_edge(
        self,
        hit: tuple[str, int, tuple[float, float, float], tuple[float, float, float]],
    ) -> bool:
        room_resref, edge_index, world_start, world_end = hit
        room = str(room_resref or "").strip()
        edge = int(edge_index)
        if not room or edge < 0:
            return False
        setter = getattr(self.viewport, "set_map_studio_room_outline_edge_highlight", None)
        if callable(setter):
            setter(
                {
                    "room_resref": room,
                    "edge_index": edge,
                    "world_start": tuple(float(value) for value in world_start[:3]),
                    "world_end": tuple(float(value) for value in world_end[:3]),
                    "label": f"{room} edge {edge}",
                    "color": "#00e5ff",
                }
            )
        self.marker_summary_label.setText(
            f"Selected floor-plan edge {edge} in {room}. Use Bridge, Wall Opening, or Edge Extrude for KOTOR room seams."
        )
        self.roomOutlineEdgeSelected.emit(room, edge)
        return True

    def _begin_room_primitive_drag(self, hit: tuple[str, str, tuple[float, float, float]], event: QtCore.QEvent) -> bool:
        start_screen = self._event_position(event)
        if start_screen is None:
            self._room_primitive_drag = None
            return False
        room_resref, primitive_name, world_center = hit
        self._room_primitive_drag = {
            "room_resref": room_resref,
            "primitive_name": primitive_name,
            "start_screen": start_screen,
            "start_center": world_center,
            "start_center_screen": self._project_world_to_screen(world_center),
            "mode": self.transform_gizmo_mode(),
            "active": False,
            "pending_delta": (0.0, 0.0, 0.0),
            "pending_rotation_delta_degrees": 0.0,
            "pending_scale_multiplier": (1.0, 1.0, 1.0),
        }
        self.roomPrimitiveSelected.emit(room_resref, primitive_name)
        self._sync_clean_viewport_presentation()
        return True

    def _update_room_primitive_drag(self, event: QtCore.QEvent) -> bool:
        if self._room_primitive_drag is None:
            return False
        current = self._event_position(event)
        if current is None:
            return False
        start = self._room_primitive_drag.get("start_screen", current)
        screen_dx = float(current[0]) - float(start[0])
        screen_dy = float(current[1]) - float(start[1])
        if screen_dx * screen_dx + screen_dy * screen_dy < 9.0:
            return True
        mode = str(self._room_primitive_drag.get("mode") or "translate")
        if mode == "rotate":
            angle_delta = self._screen_rotation_delta_degrees(
                tuple(self._room_primitive_drag.get("start_center_screen") or ()),
                tuple(start),
                tuple(current),
            )
            self._room_primitive_drag["active"] = True
            self._room_primitive_drag["pending_rotation_delta_degrees"] = angle_delta
            self.marker_summary_label.setText(f"Rotate gimbal: {angle_delta:+.1f} deg around selected primitive pivot.")
            return True
        if mode == "scale":
            multiplier = self._screen_scale_multiplier(screen_dx, screen_dy)
            self._room_primitive_drag["active"] = True
            self._room_primitive_drag["pending_scale_multiplier"] = (multiplier, multiplier, multiplier)
            self.marker_summary_label.setText(f"Scale gimbal: {multiplier:.3f}x selected primitive transform.")
            return True
        start_center = tuple(self._room_primitive_drag.get("start_center", (0.0, 0.0, 0.0)))
        if len(start_center) < 3:
            return False
        world_dx, world_dy = self._screen_delta_to_floor_delta(start_center, screen_dx, screen_dy)
        pending_center = self._snap_map_studio_position(
            (float(start_center[0]) + world_dx, float(start_center[1]) + world_dy, float(start_center[2]))
        )
        delta = (
            float(pending_center[0]) - float(start_center[0]),
            float(pending_center[1]) - float(start_center[1]),
            float(pending_center[2]) - float(start_center[2]),
        )
        self._room_primitive_drag["active"] = True
        self._room_primitive_drag["pending_delta"] = delta
        return True

    def _finish_room_primitive_drag(self, event: QtCore.QEvent | None = None) -> bool:
        if self._room_primitive_drag is None:
            return False
        if event is not None:
            self._update_room_primitive_drag(event)
        drag = self._room_primitive_drag
        self._room_primitive_drag = None
        self._sync_clean_viewport_presentation()
        if not bool(drag.get("active", False)):
            return True
        mode = str(drag.get("mode") or "translate")
        if mode == "rotate":
            self.roomPrimitiveRotated.emit(
                str(drag.get("room_resref", "") or ""),
                str(drag.get("primitive_name", "") or ""),
                float(drag.get("pending_rotation_delta_degrees", 0.0) or 0.0),
            )
            return True
        if mode == "scale":
            self.roomPrimitiveScaled.emit(
                str(drag.get("room_resref", "") or ""),
                str(drag.get("primitive_name", "") or ""),
                tuple(float(value) for value in tuple(drag.get("pending_scale_multiplier", (1.0, 1.0, 1.0)))[:3]),
            )
            return True
        delta = tuple(float(v) for v in tuple(drag.get("pending_delta", (0.0, 0.0, 0.0)))[:3])
        if len(delta) < 3:
            return True
        self.roomPrimitiveMoved.emit(
            str(drag.get("room_resref", "") or ""),
            str(drag.get("primitive_name", "") or ""),
            delta,
        )
        return True

    def _project_world_to_screen(self, position: object) -> tuple[float, float] | None:
        project = getattr(getattr(self.viewport, "_renderer", None), "_proj", None)
        if not callable(project):
            return None
        point = tuple(position or ())
        if len(point) < 3:
            return None
        w, h = self._viewport_canvas_size()
        try:
            projected = project(float(point[0]), float(point[1]), float(point[2]), w, h)
        except Exception:
            return None
        if projected is None or len(projected) < 2:
            return None
        return (float(projected[0]), float(projected[1]))

    @staticmethod
    def _screen_rotation_delta_degrees(
        center_screen: tuple[object, ...],
        start_screen: tuple[object, ...],
        current_screen: tuple[object, ...],
    ) -> float:
        if len(center_screen) >= 2 and len(start_screen) >= 2 and len(current_screen) >= 2:
            try:
                cx, cy = float(center_screen[0]), float(center_screen[1])
                sx, sy = float(start_screen[0]) - cx, float(start_screen[1]) - cy
                ex, ey = float(current_screen[0]) - cx, float(current_screen[1]) - cy
                if abs(sx) + abs(sy) > 1.0e-6 and abs(ex) + abs(ey) > 1.0e-6:
                    start_angle = math.atan2(sy, sx)
                    end_angle = math.atan2(ey, ex)
                    delta = math.degrees(end_angle - start_angle)
                    while delta > 180.0:
                        delta -= 360.0
                    while delta < -180.0:
                        delta += 360.0
                    return delta
            except Exception:
                pass
        if len(start_screen) >= 2 and len(current_screen) >= 2:
            return (float(current_screen[0]) - float(start_screen[0])) * 0.5
        return 0.0

    @staticmethod
    def _screen_scale_multiplier(screen_dx: float, screen_dy: float) -> float:
        raw = 1.0 + ((float(screen_dx) - float(screen_dy)) / 160.0)
        return max(0.05, min(20.0, raw))

    def _marker_position(self, marker: object) -> tuple[float, float, float]:
        value = tuple(getattr(marker, "position", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))
        if len(value) < 3:
            return (0.0, 0.0, 0.0)
        return (float(value[0]), float(value[1]), float(value[2]))

    def _drag_marker_position(self, screen_dx: float, screen_dy: float) -> tuple[float, float, float] | None:
        if self._marker_drag is None:
            return None
        start_position = tuple(self._marker_drag.get("start_position", (0.0, 0.0, 0.0)))
        if len(start_position) < 3:
            return None
        world_dx, world_dy = self._screen_delta_to_floor_delta(start_position, screen_dx, screen_dy)
        return self._snap_map_studio_position(
            (
                float(start_position[0]) + world_dx,
                float(start_position[1]) + world_dy,
                float(start_position[2]),
            )
        )

    def _screen_delta_to_floor_delta(self, position, screen_dx: float, screen_dy: float) -> tuple[float, float]:
        renderer = getattr(self.viewport, "_renderer", None)
        project = getattr(renderer, "_proj", None)
        if not callable(project):
            return self._fallback_screen_delta_to_floor_delta(screen_dx, screen_dy)
        w, h = self._viewport_canvas_size()
        try:
            x, y, z = (float(position[0]), float(position[1]), float(position[2]))
            base = project(x, y, z, w, h)
            x_axis = project(x + 1.0, y, z, w, h)
            y_axis = project(x, y + 1.0, z, w, h)
            ax = float(x_axis[0]) - float(base[0])
            ay = float(x_axis[1]) - float(base[1])
            bx = float(y_axis[0]) - float(base[0])
            by = float(y_axis[1]) - float(base[1])
            determinant = ax * by - ay * bx
            if abs(determinant) <= 1.0e-6:
                return self._fallback_screen_delta_to_floor_delta(screen_dx, screen_dy)
            world_dx = (float(screen_dx) * by - float(screen_dy) * bx) / determinant
            world_dy = (ax * float(screen_dy) - ay * float(screen_dx)) / determinant
            if not math.isfinite(world_dx) or not math.isfinite(world_dy):
                return self._fallback_screen_delta_to_floor_delta(screen_dx, screen_dy)
            return self._clamp_floor_delta(world_dx, world_dy)
        except Exception:
            return self._fallback_screen_delta_to_floor_delta(screen_dx, screen_dy)

    def _viewport_canvas_size(self) -> tuple[int, int]:
        canvas = getattr(self.viewport, "canvas", None)
        if canvas is not None:
            return (max(8, int(canvas.width())), max(8, int(canvas.height())))
        return (max(8, int(self.viewport.width())), max(8, int(self.viewport.height())))

    def _fallback_screen_delta_to_floor_delta(self, screen_dx: float, screen_dy: float) -> tuple[float, float]:
        return self._clamp_floor_delta(float(screen_dx) * 0.05, -float(screen_dy) * 0.05)

    def _clamp_floor_delta(self, world_dx: float, world_dy: float) -> tuple[float, float]:
        limit = 250.0
        return (
            max(-limit, min(limit, float(world_dx))),
            max(-limit, min(limit, float(world_dy))),
        )

    def _snap_map_studio_position(self, position: tuple[float, float, float]) -> tuple[float, float, float]:
        if not bool(self.snap_box.isChecked()):
            return (float(position[0]), float(position[1]), float(position[2]))
        spacing = self._map_studio_grid_spacing()
        return (
            round(float(position[0]) / spacing) * spacing,
            round(float(position[1]) / spacing) * spacing,
            float(position[2]),
        )

    def _map_studio_grid_spacing(self) -> float:
        settings = getattr(self.viewport, "measurement_settings", None)
        spacing = getattr(settings, "minor_grid_spacing", 10.0)
        try:
            value = float(spacing)
        except (TypeError, ValueError):
            value = 10.0
        if not math.isfinite(value) or value <= 0.0:
            return 10.0
        return value

    def _configure_map_studio_viewport_quality(self) -> None:
        self.viewport.setProperty("_gr_suppress_renderer_diagnostics", True)
        self.viewport.setProperty("_gr_map_studio_clean_viewport", True)
        self.viewport.setProperty("_gr_map_studio_hide_embedded_toolbar", True)
        renderer = getattr(self.viewport, "_renderer", None)
        if renderer is not None:
            setattr(renderer, "wireframe", False)
            setattr(renderer, "show_texture", True)
        set_chrome = getattr(self.viewport, "set_viewport_chrome_visible", None)
        if callable(set_chrome):
            set_chrome(toolbar=False, transform_typein=False)
        tabs = getattr(self.viewport, "viewport_map_studio_modeling_tabs", None)
        if tabs is not None:
            tabs.setVisible(False)
            tabs.setMaximumHeight(0)
        canvas = getattr(self.viewport, "canvas", None)
        clear_text = getattr(canvas, "clear_diagnostics_text", None)
        if callable(clear_text):
            clear_text()
        surface = getattr(canvas, "current_surface", lambda: None)()
        if isinstance(surface, QtWidgets.QLabel):
            surface.setText("")
            surface.setToolTip("Map Studio viewport")

    def _sync_clean_viewport_presentation(self) -> None:
        viewport = getattr(self, "viewport", None)
        if viewport is None:
            return
        viewport.setProperty("_gr_map_studio_clean_viewport", True)
        terrain_active = self._terrain_brush_context_enabled()
        room_edit_active = (
            self._room_outline_point_drag is not None
            or bool(self._vertex_snap_modifier_active)
            or bool(self._transform_snap_modifier_active)
        )
        primitive_drag_active = self._room_primitive_drag is not None
        preview_model_loaded = self._room_preview_model is not None
        render_geometry_edit_active = room_edit_active or primitive_drag_active
        presentation = {
            "clean_display": True,
            "preview_model_loaded": preview_model_loaded,
            "show_render_geometry_overlay": render_geometry_edit_active if preview_model_loaded else True,
            "show_room_mesh_fill_overlay": not preview_model_loaded,
            "subtle_room_outlines": True,
            "show_room_guides": room_edit_active,
            "show_room_vertex_handles": room_edit_active,
            "show_primitive_handles": render_geometry_edit_active if preview_model_loaded else True,
            "subtle_primitive_handles": True,
            "show_primitive_labels": False,
            "show_transform_dimensions": primitive_drag_active or self.transform_gizmo_mode() == "scale",
            "show_gimbal_labels": False,
            "show_terrain_walkability": terrain_active,
            "show_terrain_brush": terrain_active,
            "show_placement_guides": self._marker_drag is not None,
        }
        setter = getattr(viewport, "set_map_studio_viewport_presentation", None)
        if callable(setter):
            setter(presentation)
        else:
            setattr(viewport, "_map_studio_viewport_presentation", presentation)
        canvas = getattr(viewport, "canvas", None)
        clear_diagnostics = getattr(canvas, "clear_diagnostics_text", None)
        if callable(clear_diagnostics):
            clear_diagnostics()
        surface = getattr(canvas, "current_surface", lambda: None)() if canvas is not None else None
        if isinstance(surface, QtWidgets.QLabel):
            surface.setText("")

    def _sync_room_preview_model(self, authored_room_preview_model=None) -> None:
        viewport = getattr(self, "viewport", None)
        if viewport is None:
            return
        load_model = getattr(viewport, "load_model", None)
        if authored_room_preview_model is None:
            current_model = getattr(viewport, "model", None)
            if getattr(current_model, "_gr_map_studio_preview_model", False) and callable(load_model):
                load_model(None)
            self._room_preview_model_key = ""
            viewport.setProperty("_gr_map_studio_preview_model_loaded", False)
            return

        key = str(getattr(authored_room_preview_model, "_gr_map_studio_preview_key", "") or id(authored_room_preview_model))
        if key == self._room_preview_model_key and getattr(viewport, "model", None) is not None:
            viewport.setProperty("_gr_map_studio_preview_model_loaded", True)
            return
        if callable(load_model):
            load_model(authored_room_preview_model)
            self._room_preview_model_key = key
            viewport.setProperty("_gr_map_studio_preview_model_loaded", True)
            renderer = getattr(viewport, "_renderer", None)
            if renderer is not None:
                setattr(renderer, "wireframe", False)
            request_render = getattr(viewport, "_request_render", None)
            if callable(request_render):
                request_render(fast=True, reason="map studio preview model changed", resources=True, overlay=True, hud=True)

    def _ensure_embedded_viewport_toolbar_gap(self, gap_height: int = 6) -> None:
        toolbar_scroll = getattr(self.viewport, "viewport_toolbar_scroll", None)
        root_layout = getattr(self.viewport, "_root_layout", None) or self.viewport.layout()
        if toolbar_scroll is None or root_layout is None:
            return
        if bool(self.viewport.property("_gr_map_studio_hide_embedded_toolbar")):
            toolbar_scroll.setVisible(False)
            toolbar_scroll.setFixedHeight(0)
            tabs = getattr(self.viewport, "viewport_map_studio_modeling_tabs", None)
            if tabs is not None:
                tabs.setVisible(False)
                tabs.setMaximumHeight(0)
            gap = getattr(self, "_viewport_toolbar_gap", None)
            if gap is not None:
                gap.setVisible(False)
                gap.setFixedHeight(0)
            return

        target_height = self._embedded_viewport_toolbar_height(toolbar_scroll)
        toolbar_scroll.setContentsMargins(0, 0, 0, 0)
        toolbar_scroll.setViewportMargins(0, 0, 0, 0)
        toolbar_scroll.setFixedHeight(target_height)

        toolbar = getattr(self.viewport, "viewport_toolbar", None)
        if toolbar is not None and toolbar.layout() is not None:
            toolbar.layout().setContentsMargins(6, 4, 6, 4)

        gap = getattr(self, "_viewport_toolbar_gap", None)
        if gap is None:
            gap = QtWidgets.QWidget(self.viewport)
            gap.setObjectName("ModuleViewportToolbarGap")
            gap.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            self._viewport_toolbar_gap = gap
            index = root_layout.indexOf(toolbar_scroll)
            root_layout.insertWidget(index + 1 if index >= 0 else 1, gap)
        gap.setFixedHeight(max(4, int(gap_height)))
        self._apply_viewport_toolbar_theme()

    def _embedded_viewport_toolbar_height(self, toolbar_scroll: QtWidgets.QScrollArea) -> int:
        minimum_height = 64
        toolbar = getattr(self.viewport, "viewport_toolbar", None)
        if toolbar is None:
            return minimum_height
        layout = toolbar.layout()
        width = max(1, toolbar_scroll.viewport().width() or toolbar_scroll.width() or toolbar.width())
        layout_height = layout.heightForWidth(width) if layout is not None and layout.hasHeightForWidth() else toolbar.sizeHint().height()
        scrollbar_height = toolbar_scroll.horizontalScrollBar().sizeHint().height() if toolbar_scroll.horizontalScrollBarPolicy() != QtCore.Qt.ScrollBarAlwaysOff else 0
        target_height = max(minimum_height, int(layout_height) + int(scrollbar_height) + 2)
        toolbar.setMinimumHeight(max(minimum_height - scrollbar_height, int(layout_height)))
        toolbar.adjustSize()
        return min(120, target_height)

    def _add_row(self, kind: str, name: str, item_id: str, position, visible: bool, *, marker: str = "", facing: str = "") -> None:
        row = self.scene_table.rowCount()
        self.scene_table.insertRow(row)
        values = [
            kind,
            name,
            f"{float(position[0]):.3f}",
            f"{float(position[1]):.3f}",
            f"{float(position[2]):.3f}",
            marker,
            facing,
            "yes" if visible else "no",
        ]
        editable_authored_columns = {2, 3, 4, 6}
        authored = str(item_id).startswith("authored:")
        for column, value in enumerate(values):
            item = QtWidgets.QTableWidgetItem(value)
            item.setData(QtCore.Qt.UserRole, item_id)
            flags = item.flags()
            if authored and column in editable_authored_columns:
                item.setFlags(flags | QtCore.Qt.ItemIsEditable)
                item.setToolTip("Edit authored gameplay placement position or bearing.")
            else:
                item.setFlags(flags & ~QtCore.Qt.ItemIsEditable)
            self.scene_table.setItem(row, column, item)
        self._row_ids.append(item_id)

    def _update_marker_summary(
        self,
        authored_gameplay_markers,
        authored_gameplay_marker_geometry=None,
        authored_room_outline_geometry=None,
        authored_terrain_walkability_overlay=None,
    ) -> None:
        markers = tuple(authored_gameplay_markers or ())
        room_count = int(getattr(authored_room_outline_geometry, "room_count", 0) or 0)
        terrain_triangles = tuple(getattr(authored_terrain_walkability_overlay, "triangles", ()) or ())
        clean_display = bool(getattr(self, "viewport", None) is not None and self.viewport.property("_gr_map_studio_clean_viewport"))
        preview_model_loaded = self._room_preview_model is not None
        if not markers and room_count <= 0 and not terrain_triangles:
            self.marker_summary_label.setText(
                "Map Studio clean view: no authored geometry yet" if clean_display else "Gameplay markers: none"
            )
            return
        counts: dict[str, int] = {}
        warnings = 0
        for marker in markers:
            kind = str(getattr(marker, "kind", "object") or "object")
            counts[kind] = counts.get(kind, 0) + 1
            if getattr(marker, "warning", ""):
                warnings += 1
        parts_list = [f"{kind} {count}" for kind, count in sorted(counts.items())]
        if room_count > 0:
            parts_list.insert(0, f"room mesh {room_count}" if preview_model_loaded else f"room outline {room_count}")
        parts = ", ".join(parts_list)
        if not parts and terrain_triangles:
            parts = "terrain overlay"
        geometry_suffix = ""
        if authored_gameplay_marker_geometry is not None:
            footprints = len(tuple(getattr(authored_gameplay_marker_geometry, "footprints", ()) or ()))
            lines = len(tuple(getattr(authored_gameplay_marker_geometry, "lines", ()) or ()))
            if footprints or lines:
                geometry_suffix = f" | {footprints} footprint(s), {lines} guide line(s)"
        if authored_room_outline_geometry is not None:
            polygons = len(tuple(getattr(authored_room_outline_geometry, "polygons", ()) or ()))
            room_lines = len(tuple(getattr(authored_room_outline_geometry, "lines", ()) or ()))
            primitive_handles = len(tuple(getattr(authored_room_outline_geometry, "primitive_handles", ()) or ()))
            if polygons or room_lines or primitive_handles:
                geometry_suffix = (
                    f"{geometry_suffix} | {polygons} room outline polygon(s), "
                    f"{room_lines} wall/opening guide(s), {primitive_handles} primitive handle(s)"
                )
        if terrain_triangles:
            walkable = int(getattr(authored_terrain_walkability_overlay, "walkable_triangle_count", 0) or 0)
            blocked = int(getattr(authored_terrain_walkability_overlay, "non_walk_triangle_count", 0) or 0)
            max_slope = float(getattr(authored_terrain_walkability_overlay, "max_slope_degrees", 0.0) or 0.0)
            geometry_suffix = f"{geometry_suffix} | terrain walkability {walkable} walk / {blocked} blocked, max slope {max_slope:.1f} deg"
        suffix = f" | {warnings} marker warning(s)" if warnings else ""
        if clean_display:
            clean_parts = []
            if room_count > 0:
                clean_parts.append(f"{room_count} authored room mesh(es)" if preview_model_loaded else f"{room_count} authored room outline(s)")
            if terrain_triangles:
                clean_parts.append(f"{len(terrain_triangles)} terrain triangle(s)")
            marker_count = sum(counts.values())
            if marker_count:
                clean_parts.append(f"{marker_count} gameplay marker(s)")
            if warnings:
                clean_parts.append(f"{warnings} warning(s)")
            self.marker_summary_label.setText(f"Map Studio clean view: {', '.join(clean_parts)}")
            return
        self.marker_summary_label.setText(f"Gameplay markers: {parts}{geometry_suffix}{suffix}")

    def _sync_room_outline_overlay(self, authored_room_outline_geometry=None) -> None:
        setter = getattr(self.viewport, "set_map_studio_room_outline_geometry", None)
        clearer = getattr(self.viewport, "clear_map_studio_room_outline_geometry", None)
        polygons = tuple(getattr(authored_room_outline_geometry, "polygons", ()) or ())
        lines = tuple(getattr(authored_room_outline_geometry, "lines", ()) or ())
        if authored_room_outline_geometry is not None and (polygons or lines) and callable(setter):
            setter(authored_room_outline_geometry)
            self._install_marker_pick_filters()
            return
        if callable(clearer):
            clearer()
        elif callable(setter):
            setter(None)
        self._install_marker_pick_filters()

    def _sync_marker_geometry_overlay(self, authored_gameplay_marker_geometry=None) -> None:
        setter = getattr(self.viewport, "set_map_studio_marker_geometry", None)
        clearer = getattr(self.viewport, "clear_map_studio_marker_geometry", None)
        footprints = tuple(getattr(authored_gameplay_marker_geometry, "footprints", ()) or ())
        lines = tuple(getattr(authored_gameplay_marker_geometry, "lines", ()) or ())
        if authored_gameplay_marker_geometry is not None and (footprints or lines) and callable(setter):
            setter(authored_gameplay_marker_geometry)
            self._install_marker_pick_filters()
            return
        if callable(clearer):
            clearer()
        elif callable(setter):
            setter(None)
        self._install_marker_pick_filters()

    def _sync_terrain_walkability_overlay(self, authored_terrain_walkability_overlay=None) -> None:
        setter = getattr(self.viewport, "set_map_studio_terrain_walkability_overlay", None)
        clearer = getattr(self.viewport, "clear_map_studio_terrain_walkability_overlay", None)
        triangles = tuple(getattr(authored_terrain_walkability_overlay, "triangles", ()) or ())
        if authored_terrain_walkability_overlay is not None and triangles and callable(setter):
            setter(authored_terrain_walkability_overlay)
            return
        if callable(clearer):
            clearer()
        elif callable(setter):
            setter(None)

    def _sync_universal_transform_overlay(self, overlay=None) -> None:
        setter = getattr(self.viewport, "set_map_studio_universal_transform_overlay", None)
        clearer = getattr(self.viewport, "clear_map_studio_universal_transform_overlay", None)
        lines = tuple(getattr(overlay, "edge_lines", ()) or ())
        handles = tuple(getattr(overlay, "handles", ()) or ())
        labels = tuple(getattr(overlay, "dimension_labels", ()) or ())
        if overlay is not None and (lines or handles or labels) and callable(setter):
            setter(overlay)
            return
        if callable(clearer):
            clearer()
        elif callable(setter):
            setter(None)

    def _table_selection(self) -> None:
        rows = self.scene_table.selectionModel().selectedRows() if self.scene_table.selectionModel() else []
        if not rows:
            return
        row = rows[0].row()
        if 0 <= row < len(self._row_ids):
            self.itemSelected.emit(self._row_ids[row])

    def _table_item_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        if self._table_updating or item is None:
            return
        row = item.row()
        column = item.column()
        if column not in {2, 3, 4, 6} or row < 0 or row >= len(self._row_ids):
            return
        item_id = self._row_ids[row]
        if not str(item_id).startswith("authored:"):
            return
        try:
            position = (
                self._table_float(row, 2),
                self._table_float(row, 3),
                self._table_float(row, 4),
            )
            bearing = self._table_float(row, 6)
        except ValueError:
            return
        self.transformEdited.emit(
            item_id,
            LevelTransform(position=position, rotation=(0.0, 0.0, bearing), scale=(1.0, 1.0, 1.0)),
        )

    def _table_float(self, row: int, column: int) -> float:
        item = self.scene_table.item(row, column)
        text = item.text() if item is not None else ""
        text = text.strip().lower().replace("rad", "").strip()
        return float(text)

    def apply_ghost_theme(self, theme) -> None:
        if theme is not None and getattr(theme, "is_native", lambda: False)():
            self.apply_native_theme()
            return
        self._current_theme = theme
        viewport_hook = getattr(self.viewport, "apply_ghost_theme", None)
        if callable(viewport_hook):
            viewport_hook(theme)
        self._apply_viewport_toolbar_theme()

    def _apply_viewport_toolbar_theme(self) -> None:
        theme = getattr(self, "_current_theme", None)
        if theme is None:
            return
        toolbar_bg = theme.color("viewportToolbar.background", theme.color("toolbar.background"))
        toolbar_border = theme.color("viewportToolbar.border", theme.color("toolbar.border"))
        panel_bg = theme.color("window.background")
        self.viewport_toolbar_frame.setStyleSheet(
            "QFrame#ModuleViewportTopTools { "
            f"background:{panel_bg}; "
            f"border:1px solid {toolbar_border}; "
            "}"
        )
        toolbar_scroll = getattr(self.viewport, "viewport_toolbar_scroll", None)
        if toolbar_scroll is not None:
            toolbar_scroll.setStyleSheet(
                "QScrollArea#ViewportToolbarScroll { "
                f"background:{toolbar_bg}; "
                "border:0; "
                "}"
            )
            toolbar_scroll.viewport().setStyleSheet(f"background:{toolbar_bg};")
        toolbar = getattr(self.viewport, "viewport_toolbar", None)
        if toolbar is not None:
            toolbar.setStyleSheet(
                "QFrame#ViewportToolbar { "
                f"background:{toolbar_bg}; "
                f"border:1px solid {toolbar_border}; "
                "}"
            )
        gap = getattr(self, "_viewport_toolbar_gap", None)
        if gap is not None:
            gap.setStyleSheet(f"background:{panel_bg};")

    def apply_native_theme(self) -> None:
        self._current_theme = None
        palette = QtWidgets.QApplication.palette()
        toolbar_bg = palette.color(QtGui.QPalette.ColorRole.Window).name()
        toolbar_border = palette.color(QtGui.QPalette.ColorRole.Mid).name()
        self.viewport_toolbar_frame.setStyleSheet(
            "QFrame#ModuleViewportTopTools { "
            f"background:{toolbar_bg}; "
            f"border:1px solid {toolbar_border}; "
            "}"
        )
        toolbar_scroll = getattr(self.viewport, "viewport_toolbar_scroll", None)
        if toolbar_scroll is not None:
            toolbar_scroll.setStyleSheet(
                "QScrollArea#ViewportToolbarScroll { "
                f"background:{toolbar_bg}; "
                "border:0; "
                "}"
            )
            toolbar_scroll.viewport().setStyleSheet(f"background:{toolbar_bg};")
        toolbar = getattr(self.viewport, "viewport_toolbar", None)
        if toolbar is not None:
            toolbar.setStyleSheet(
                "QFrame#ViewportToolbar { "
                f"background:{toolbar_bg}; "
                f"border:1px solid {toolbar_border}; "
                "}"
            )
        gap = getattr(self, "_viewport_toolbar_gap", None)
        if gap is not None:
            gap.setStyleSheet(f"background:{toolbar_bg};")
        viewport_hook = getattr(self.viewport, "apply_native_theme", None)
        if callable(viewport_hook):
            viewport_hook()
        self._apply_native_toolbar_palette()

    def _apply_native_toolbar_palette(self) -> None:
        palette = QtWidgets.QApplication.palette()
        toolbar_bg = palette.color(QtGui.QPalette.ColorRole.Window).name()
        toolbar_border = palette.color(QtGui.QPalette.ColorRole.Mid).name()
        toolbar_scroll = getattr(self.viewport, "viewport_toolbar_scroll", None)
        if toolbar_scroll is not None:
            toolbar_scroll.setStyleSheet(
                "QScrollArea#ViewportToolbarScroll { "
                f"background:{toolbar_bg}; "
                "border:0; "
                "}"
            )
            toolbar_scroll.viewport().setStyleSheet(f"background:{toolbar_bg};")
        toolbar = getattr(self.viewport, "viewport_toolbar", None)
        if toolbar is not None:
            toolbar.setStyleSheet(
                "QFrame#ViewportToolbar { "
                f"background:{toolbar_bg}; "
                f"border:1px solid {toolbar_border}; "
                "}"
            )

    def apply_ghost_layout(self, layout) -> None:
        self.splitter.setHandleWidth(layout.spacing_value("splitterHandleWidth", 6))
        self.viewport.setMinimumWidth(layout.viewport.min_width)
        margin = max(4, layout.spacing_value("panelSpacing", 4))
        self.layout().setContentsMargins(margin, margin + 6, margin, 0)
        self.viewport_toolbar.setSpacing(max(5, layout.spacing_value("toolbarSpacing", 4)))
        self._ensure_embedded_viewport_toolbar_gap(max(5, layout.spacing_value("panelSpacing", 4) + 1))
        self._apply_viewport_toolbar_theme()
        self.scene_table.verticalHeader().setDefaultSectionSize(layout.spacing_value("tableRowHeight", 22))
        self.scene_table.setMaximumHeight(max(80, min(128, layout.spacing_value("tableRowHeight", 22) * 4 + 34)))
