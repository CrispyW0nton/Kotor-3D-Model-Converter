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

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModuleEditorViewportPanel")
        self._current_theme = None
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 8, 6, 0)
        root.setSpacing(6)
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
        self.snap_box.setToolTip("Snap authored room and gameplay marker drags to the viewport grid.")
        self.viewport_toolbar.addWidget(self.focus_button)
        self.viewport_toolbar.addWidget(self.grid_box)
        self.viewport_toolbar.addWidget(self.snap_box)
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
        self.viewport.setMinimumHeight(520)
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
        self.scene_table.setMinimumHeight(58)
        self.scene_table.setMaximumHeight(118)
        self.scene_table.itemSelectionChanged.connect(self._table_selection)
        self.scene_table.itemChanged.connect(self._table_item_changed)
        self.splitter.addWidget(self.viewport)
        self.splitter.addWidget(self.scene_table)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([900, 90])
        root.addWidget(self.splitter, 1)
        self._row_ids: list[str] = []
        self._placement_markers: dict[str, object] = {}
        self._placement_marker_geometry: object | None = None
        self._marker_drag: dict[str, object] | None = None
        self._room_outline_point_drag: dict[str, object] | None = None
        self._table_updating = False

    def set_project(
        self,
        project: KMapProject,
        authored_gameplay_placements=(),
        authored_gameplay_markers=(),
        authored_gameplay_marker_geometry=None,
        authored_room_outline_geometry=None,
    ) -> None:
        self._table_updating = True
        try:
            self.scene_table.setRowCount(0)
            self._row_ids.clear()
            self._placement_marker_geometry = authored_gameplay_marker_geometry
            self._room_outline_geometry = authored_room_outline_geometry
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
                label = str(getattr(placement, "tag", "") or getattr(placement, "template_resref", "") or getattr(placement, "placement_id", ""))
                kind = f"Authored {str(getattr(placement, 'kind', 'object')).title()}"
                placement_id = str(getattr(placement, "placement_id", ""))
                marker = self._placement_markers.get(placement_id)
                marker_label = str(getattr(marker, "shape", "") or "")
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
        finally:
            self._table_updating = False
        self._update_marker_summary(authored_gameplay_markers, authored_gameplay_marker_geometry, authored_room_outline_geometry)
        self._sync_room_outline_overlay(authored_room_outline_geometry)
        self._sync_marker_geometry_overlay(authored_gameplay_marker_geometry)

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
            if event_type == QtCore.QEvent.MouseButtonPress:
                if getattr(event, "button", lambda: None)() == QtCore.Qt.LeftButton:
                    placement_id = self._marker_at_event(event)
                    if placement_id:
                        self.select_id(placement_id)
                        self.itemSelected.emit(placement_id)
                        self._begin_marker_drag(placement_id, event)
                        return True
                    room_point = self._room_outline_point_at_event(event)
                    if room_point is not None:
                        self._begin_room_outline_point_drag(room_point, event)
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
            if event_type == QtCore.QEvent.MouseButtonRelease and self._marker_drag is not None:
                return self._finish_marker_drag(event)
            if event_type == QtCore.QEvent.MouseButtonRelease and self._room_outline_point_drag is not None:
                return self._finish_room_outline_point_drag(event)
        toolbar_scroll = getattr(self.viewport, "viewport_toolbar_scroll", None)
        if watched is toolbar_scroll and event.type() in {
            QtCore.QEvent.Resize,
            QtCore.QEvent.Show,
            QtCore.QEvent.LayoutRequest,
        }:
            QtCore.QTimer.singleShot(0, self._ensure_embedded_viewport_toolbar_gap)
        return super().eventFilter(watched, event)

    def _install_marker_pick_filters(self) -> None:
        candidates = [getattr(self, "viewport", None), getattr(getattr(self, "viewport", None), "canvas", None)]
        canvas = getattr(getattr(self, "viewport", None), "canvas", None)
        current_surface = getattr(canvas, "current_surface", lambda: None)() if canvas is not None else None
        candidates.append(current_surface)
        for candidate in candidates:
            if candidate is None:
                continue
            key = id(candidate)
            if key in self._marker_pick_filter_ids:
                continue
            try:
                candidate.installEventFilter(self)
            except Exception:
                continue
            self._marker_pick_filter_ids.add(key)

    def _is_marker_pick_event_source(self, watched: QtCore.QObject) -> bool:
        canvas = getattr(self.viewport, "canvas", None)
        if watched is self.viewport or watched is canvas:
            return True
        current_surface = getattr(canvas, "current_surface", lambda: None)() if canvas is not None else None
        return watched is current_surface

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

    def _event_position(self, event: QtCore.QEvent) -> tuple[float, float] | None:
        pos_fn = getattr(event, "position", None)
        pos = pos_fn() if callable(pos_fn) else getattr(event, "pos", lambda: None)()
        if pos is None:
            return None
        return (float(pos.x()), float(pos.y()))

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
        if not bool(drag.get("active", False)):
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

    def _ensure_embedded_viewport_toolbar_gap(self, gap_height: int = 6) -> None:
        toolbar_scroll = getattr(self.viewport, "viewport_toolbar_scroll", None)
        root_layout = getattr(self.viewport, "_root_layout", None) or self.viewport.layout()
        if toolbar_scroll is None or root_layout is None:
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

    def _update_marker_summary(self, authored_gameplay_markers, authored_gameplay_marker_geometry=None, authored_room_outline_geometry=None) -> None:
        markers = tuple(authored_gameplay_markers or ())
        room_count = int(getattr(authored_room_outline_geometry, "room_count", 0) or 0)
        if not markers and room_count <= 0:
            self.marker_summary_label.setText("Gameplay markers: none")
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
            parts_list.insert(0, f"room outline {room_count}")
        parts = ", ".join(parts_list)
        geometry_suffix = ""
        if authored_gameplay_marker_geometry is not None:
            footprints = len(tuple(getattr(authored_gameplay_marker_geometry, "footprints", ()) or ()))
            lines = len(tuple(getattr(authored_gameplay_marker_geometry, "lines", ()) or ()))
            if footprints or lines:
                geometry_suffix = f" | {footprints} footprint(s), {lines} guide line(s)"
        if authored_room_outline_geometry is not None:
            polygons = len(tuple(getattr(authored_room_outline_geometry, "polygons", ()) or ()))
            room_lines = len(tuple(getattr(authored_room_outline_geometry, "lines", ()) or ()))
            if polygons or room_lines:
                geometry_suffix = f"{geometry_suffix} | {polygons} room outline polygon(s), {room_lines} wall/opening guide(s)"
        suffix = f" | {warnings} marker warning(s)" if warnings else ""
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
