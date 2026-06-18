"""Viewport host and scene-state preview for the Module Editor."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.level import KMapProject
from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget


class ModuleEditorViewportPanel(QtWidgets.QWidget):
    itemSelected = QtCore.Signal(str)
    transformEdited = QtCore.Signal(str, object)

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
        self.grid_box.setChecked(True)
        self.snap_box = QtWidgets.QCheckBox("Snap")
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
        self.splitter.addWidget(self.viewport)
        self.splitter.addWidget(self.scene_table)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([900, 90])
        root.addWidget(self.splitter, 1)
        self._row_ids: list[str] = []
        self._placement_markers: dict[str, object] = {}
        self._placement_marker_geometry: object | None = None

    def set_project(
        self,
        project: KMapProject,
        authored_gameplay_placements=(),
        authored_gameplay_markers=(),
        authored_gameplay_marker_geometry=None,
    ) -> None:
        self.scene_table.setRowCount(0)
        self._row_ids.clear()
        self._placement_marker_geometry = authored_gameplay_marker_geometry
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
        self._update_marker_summary(authored_gameplay_markers, authored_gameplay_marker_geometry)
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
        toolbar_scroll = getattr(self.viewport, "viewport_toolbar_scroll", None)
        if watched is toolbar_scroll and event.type() in {
            QtCore.QEvent.Resize,
            QtCore.QEvent.Show,
            QtCore.QEvent.LayoutRequest,
        }:
            QtCore.QTimer.singleShot(0, self._ensure_embedded_viewport_toolbar_gap)
        return super().eventFilter(watched, event)

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
        for column, value in enumerate(values):
            item = QtWidgets.QTableWidgetItem(value)
            item.setData(QtCore.Qt.UserRole, item_id)
            self.scene_table.setItem(row, column, item)
        self._row_ids.append(item_id)

    def _update_marker_summary(self, authored_gameplay_markers, authored_gameplay_marker_geometry=None) -> None:
        markers = tuple(authored_gameplay_markers or ())
        if not markers:
            self.marker_summary_label.setText("Gameplay markers: none")
            return
        counts: dict[str, int] = {}
        warnings = 0
        for marker in markers:
            kind = str(getattr(marker, "kind", "object") or "object")
            counts[kind] = counts.get(kind, 0) + 1
            if getattr(marker, "warning", ""):
                warnings += 1
        parts = ", ".join(f"{kind} {count}" for kind, count in sorted(counts.items()))
        geometry_suffix = ""
        if authored_gameplay_marker_geometry is not None:
            footprints = len(tuple(getattr(authored_gameplay_marker_geometry, "footprints", ()) or ()))
            lines = len(tuple(getattr(authored_gameplay_marker_geometry, "lines", ()) or ()))
            if footprints or lines:
                geometry_suffix = f" | {footprints} footprint(s), {lines} guide line(s)"
        suffix = f" | {warnings} marker warning(s)" if warnings else ""
        self.marker_summary_label.setText(f"Gameplay markers: {parts}{geometry_suffix}{suffix}")

    def _sync_marker_geometry_overlay(self, authored_gameplay_marker_geometry=None) -> None:
        setter = getattr(self.viewport, "set_map_studio_marker_geometry", None)
        clearer = getattr(self.viewport, "clear_map_studio_marker_geometry", None)
        footprints = tuple(getattr(authored_gameplay_marker_geometry, "footprints", ()) or ())
        lines = tuple(getattr(authored_gameplay_marker_geometry, "lines", ()) or ())
        if authored_gameplay_marker_geometry is not None and (footprints or lines) and callable(setter):
            setter(authored_gameplay_marker_geometry)
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
