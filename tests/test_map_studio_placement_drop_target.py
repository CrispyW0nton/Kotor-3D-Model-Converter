"""Focused runtime proof for Map Studio placeable drop and transform proxies."""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def test_viewport_accepts_typed_placeable_payload() -> None:
    _configure_native_python_roots()
    from PySide6 import QtCore
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    mime = QtCore.QMimeData()
    payload = {
        "schema": "ghostrigger.map-placement/v1",
        "game": "K2",
        "kind": "door",
        "template_resref": "door_airlock",
        "library_source": "placeable_builder",
        "tag": "airlock_instance",
        "bearing": math.pi / 2.0,
        "snap_to_walkmesh": True,
        "keep_placing": False,
    }
    mime.setData(ModuleEditorViewportPanel.MAP_PLACEMENT_MIME_TYPE, json.dumps(payload).encode("utf-8"))
    event = SimpleNamespace(mimeData=lambda: mime)

    assert ModuleEditorViewportPanel._map_placement_drop_payload(event) == payload


def test_placement_browser_uses_thumbnail_tiles_and_one_shot_drag_payload() -> None:
    """The primary placement gesture is an Unreal-style asset-tile drag."""

    _configure_native_python_roots()
    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.panels.module_editor.placement_tab import (
        MAP_PLACEMENT_MIME_TYPE,
        PlacementTab,
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    tab = PlacementTab()
    requested: list[object] = []
    tab.thumbnailRequested.connect(requested.append)
    entry = SimpleNamespace(
        game="K2",
        kind="placeable",
        authoring_family="placeable",
        template_resref="plc_bench",
        label="Bench",
        category="Furniture",
        source="KOTOR library",
        metadata={},
    )
    try:
        tab.set_placement_kinds(("placeable",))
        tab.set_palette_entries((entry,))
        tab.resize(520, 720)
        tab.show()
        app.processEvents()

        assert tab.asset_list.viewMode() == QtWidgets.QListView.ViewMode.IconMode
        assert tab.asset_list.dragEnabled() is True
        assert tab.asset_list.gridSize().width() <= 142
        assert tab.asset_thumbnail_label.isHidden() is True
        assert tab.place_button.isHidden() is True
        assert tab.keep_placing_box.isHidden() is True
        index = tab._asset_proxy_model.index(0, 0)
        assert index.isValid()
        icon = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
        assert isinstance(icon, QtGui.QIcon)
        assert icon.isNull() is False

        tab.asset_list.setCurrentIndex(index)
        mime = tab.asset_list.placement_mime_data(index)
        assert mime is not None and mime.hasFormat(MAP_PLACEMENT_MIME_TYPE)
        payload = json.loads(bytes(mime.data(MAP_PLACEMENT_MIME_TYPE)).decode("utf-8"))
        assert payload["template_resref"] == "plc_bench"
        assert payload["snap_to_walkmesh"] is True
        assert payload["keep_placing"] is False

        thumbnail = QtGui.QPixmap(192, 192)
        thumbnail.fill(tab.palette().color(QtGui.QPalette.ColorRole.Highlight))
        tab.set_asset_thumbnail(entry, thumbnail, "Bench thumbnail ready")
        rendered_icon = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
        assert isinstance(rendered_icon, QtGui.QIcon)
        assert rendered_icon.isNull() is False
        assert requested
    finally:
        tab.close()
        tab.deleteLater()
        app.processEvents()


def test_environment_kit_browser_exposes_typed_thumbnail_drag_cards() -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.core.modules.map_studio_environment_kits import (
        ENVIRONMENT_KIT_MIME_TYPE,
        environment_kit_piece_rows,
    )
    from src.gui.panels.module_editor.environment_kit_browser import EnvironmentKitBrowser

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    browser = EnvironmentKitBrowser()
    rows = environment_kit_piece_rows(game="K1")
    try:
        browser.set_assets(rows)
        browser.resize(620, 720)
        browser.show()
        app.processEvents()

        assert browser.asset_list.dragEnabled() is True
        assert browser.collection_combo.count() >= 2
        assert browser.class_combo.count() >= 2
        assert 0 < browser._model.rowCount() < len(rows)
        index = browser._proxy.index(0, 0)
        assert index.isValid()
        browser.asset_list.setCurrentIndex(index)
        mime = browser.asset_list.placement_mime_data(index)
        assert mime is not None and mime.hasFormat(ENVIRONMENT_KIT_MIME_TYPE)
        payload = json.loads(bytes(mime.data(ENVIRONMENT_KIT_MIME_TYPE)).decode("utf-8"))
        assert payload["piece_id"] in {row["piece_id"] for row in rows}
        assert payload["snap_to_magnets"] is True
    finally:
        browser.close()
        browser.deleteLater()
        app.processEvents()


def test_map_studio_content_browser_workflow_is_floatable_and_redockable() -> None:
    """The whole workflow rail can leave the editor like Unreal's Content Browser."""

    _configure_native_python_roots()
    from PySide6 import QtCore, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    try:
        dock = window.workflow_dock
        assert isinstance(dock, QtWidgets.QDockWidget)
        assert dock.objectName() == "mapStudioWorkflowContentBrowserDock"
        assert dock.widget().findChild(type(window.placement_tab)) is window.placement_tab
        assert bool(dock.features() & QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable)
        assert bool(dock.features() & QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        assert dock.allowedAreas() == QtCore.Qt.DockWidgetArea.AllDockWidgetAreas
        assert window.validation_output_dock.isHidden() is True
        assert window.validation_action.text() == "Show Validation / Output"
        assert window.validation_action.isChecked() is False
        assert window.builder_tab.buildingSettingsContainer.isHidden() is True
        assert window.environment_kit_browser._model.rowCount() < len(
            window.controller.available_map_studio_environment_kit_pieces()
        )

        window.show()
        app.processEvents()
        window.validation_action.setChecked(True)
        app.processEvents()
        assert window.validation_output_dock.isVisible() is True
        window.validation_action.setChecked(False)
        app.processEvents()
        assert window.validation_output_dock.isHidden() is True
        dock.setFloating(True)
        app.processEvents()
        assert dock.isFloating() is True
        dock.setFloating(False)
        window.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        app.processEvents()
        assert dock.isFloating() is False
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


def test_drag_coordinates_from_outer_and_nested_widgets_are_normalized_to_canvas() -> None:
    """A drop hit must use canvas coordinates regardless of the watched widget."""

    _configure_native_python_roots()
    from PySide6 import QtCore, QtWidgets
    from src.core.modules.map_studio_hover_context import MapStudioHoverCandidateFace
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorViewportPanel()
    panel.resize(900, 700)
    panel.show()
    app.processEvents()

    canvas = panel.viewport.canvas
    canvas_point = QtCore.QPoint(96, 80)
    candidate = MapStudioHoverCandidateFace(
        room_resref="grdrop01",
        mesh_role="authored_floor",
        face_index=0,
        screen_points=((64.0, 48.0), (128.0, 48.0), (96.0, 112.0)),
        world_points=((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (2.0, 4.0, 0.0)),
        depth=4.0,
    )
    panel._cached_map_studio_hover_candidates = lambda _screen=None: [candidate]
    panel._map_studio_hover_candidates_near = lambda _x, _y: [candidate]

    mime = QtCore.QMimeData()
    mime.setData(
        ModuleEditorViewportPanel.MAP_PLACEMENT_MIME_TYPE,
        json.dumps(
            {
                "schema": "ghostrigger.map-placement/v1",
                "game": "K2",
                "kind": "placeable",
                "template_resref": "plc_test",
                "snap_to_walkmesh": True,
            }
        ).encode("utf-8"),
    )

    class DropEvent:
        def __init__(self, event_type, local_point):
            self._event_type = event_type
            self._local_point = QtCore.QPointF(local_point)
            self.accepted = False
            self.ignored = False

        def type(self):
            return self._event_type

        def position(self):
            return self._local_point

        def mimeData(self):  # noqa: N802 - Qt event API
            return mime

        def acceptProposedAction(self):  # noqa: N802 - Qt event API
            self.accepted = True

        def ignore(self):
            self.ignored = True

    nested = QtWidgets.QWidget(canvas)
    nested.setGeometry(31, 27, 180, 160)
    nested.show()
    app.processEvents()

    watched_cases = (
        panel.viewport,
        nested,
    )
    emitted: list[dict[str, object]] = []
    panel.placementRequested.connect(emitted.append)
    try:
        for watched in watched_cases:
            local_point = watched.mapFromGlobal(canvas.mapToGlobal(canvas_point))
            drag_event = DropEvent(QtCore.QEvent.DragMove, local_point)

            normalized = panel._event_position(drag_event, watched)
            assert normalized == (float(canvas_point.x()), float(canvas_point.y()))
            assert panel._handle_map_placement_drop_event(drag_event, watched) is True
            assert drag_event.accepted is True
            assert drag_event.ignored is False
            assert panel._hover_context.is_hit is True
            assert panel._hover_context.room_resref == "grdrop01"
            assert panel._map_placement_drag_payload["template_resref"] == "plc_test"
            drop_highlight = panel.viewport._map_studio_hover_highlight
            assert drop_highlight["placement_drop"] is True
            assert drop_highlight["placement_label"] == "plc_test"
            assert len(drop_highlight["world_point"]) == 3

            drop_event = DropEvent(QtCore.QEvent.Drop, local_point)
            assert panel._handle_map_placement_drop_event(drop_event, watched) is True
            assert drop_event.accepted is True
            assert drop_event.ignored is False
            assert panel._map_placement_drag_payload is None
            assert panel.viewport._map_studio_hover_highlight is None

        assert len(emitted) == 2
        assert all(request["room_resref"] == "grdrop01" for request in emitted)
        assert all(request["surface_role"] == "authored_floor" for request in emitted)
        assert all(len(request["position"]) == 3 for request in emitted)
    finally:
        nested.close()
        panel.close()
        panel.deleteLater()
        app.processEvents()


def test_terrain_kit_drag_survives_empty_viewport_entry_then_previews_and_commits_snap() -> None:
    """The ordinary browser-to-viewport gesture may enter over toolbar/empty pixels."""

    _configure_native_python_roots()
    from PySide6 import QtCore, QtWidgets
    from src.core.modules.map_studio_hover_context import MapStudioHoverCandidateFace
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorViewportPanel()
    panel.resize(900, 700)
    panel.show()
    app.processEvents()

    candidate = MapStudioHoverCandidateFace(
        room_resref="grterrain",
        mesh_role="authored_floor",
        face_index=0,
        screen_points=((64.0, 48.0), (128.0, 48.0), (96.0, 112.0)),
        world_points=((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (2.0, 4.0, 0.0)),
        depth=4.0,
    )
    candidates: list[object] = []
    panel._cached_map_studio_hover_candidates = lambda _screen=None: list(candidates)
    panel._map_studio_hover_candidates_near = lambda _x, _y: list(candidates)

    mime = QtCore.QMimeData()
    mime.setData(
        ModuleEditorViewportPanel.MAP_TERRAIN_KIT_MIME_TYPE,
        json.dumps(
            {
                "schema": "ghostrigger.map-terrain-kit/v1",
                "asset_id": "dantooine_far_bluff",
                "label": "Far Bluff",
                "rotation_degrees_z": 15.0,
                "scale": 1.25,
            }
        ).encode("utf-8"),
    )

    class DropEvent:
        def __init__(self, event_type, point):
            self._event_type = event_type
            self._point = QtCore.QPointF(point)
            self.accepted = False
            self.ignored = False

        def type(self):
            return self._event_type

        def position(self):
            return self._point

        def mimeData(self):  # noqa: N802
            return mime

        def acceptProposedAction(self):  # noqa: N802
            self.accepted = True

        def ignore(self):
            self.ignored = True

    previews: list[dict[str, object]] = []
    committed: list[dict[str, object]] = []

    def resolve_preview(payload: object) -> None:
        values = dict(payload)
        previews.append(values)
        panel.set_terrain_kit_snap_preview(
            {
                **values,
                "magnet_snapped": True,
                "position": (8.0, 9.0, 1.0),
                "rotation_degrees_z": 90.0,
                "scale": 1.25,
                "target_room_resref": "grterrain",
            }
        )

    panel.terrainKitSnapPreviewRequested.connect(resolve_preview)
    panel.terrainKitRequested.connect(committed.append)
    watched = panel.viewport
    canvas = panel.viewport.canvas
    try:
        enter = DropEvent(QtCore.QEvent.DragEnter, QtCore.QPoint(8, 8))
        assert panel._handle_map_placement_drop_event(enter, watched) is True
        assert enter.accepted is True
        assert enter.ignored is False

        candidates.append(candidate)
        canvas_point = QtCore.QPoint(96, 80)
        local_point = watched.mapFromGlobal(canvas.mapToGlobal(canvas_point))
        move = DropEvent(QtCore.QEvent.DragMove, local_point)
        assert panel._handle_map_placement_drop_event(move, watched) is True
        assert move.accepted is True
        assert previews and previews[-1]["asset_id"] == "dantooine_far_bluff"
        assert panel._terrain_kit_snap_preview["magnet_snapped"] is True

        drop = DropEvent(QtCore.QEvent.Drop, local_point)
        assert panel._handle_map_placement_drop_event(drop, watched) is True
        assert drop.accepted is True
        assert len(committed) == 1
        assert committed[0]["position"] == (8.0, 9.0, 1.0)
        assert committed[0]["rotation_degrees_z"] == 90.0
        assert committed[0]["scale"] == 1.25
    finally:
        panel.close()
        panel.deleteLater()
        app.processEvents()


def test_environment_kit_drag_routes_live_magnet_preview_and_commit() -> None:
    _configure_native_python_roots()
    from PySide6 import QtCore, QtWidgets
    from src.core.modules.map_studio_hover_context import MapStudioHoverCandidateFace
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorViewportPanel()
    panel.resize(900, 700)
    panel.show()
    app.processEvents()

    candidate = MapStudioHoverCandidateFace(
        room_resref="grfloor",
        mesh_role="authored_floor",
        face_index=0,
        screen_points=((64.0, 48.0), (128.0, 48.0), (96.0, 112.0)),
        world_points=((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (2.0, 4.0, 0.0)),
        depth=4.0,
    )
    panel._cached_map_studio_hover_candidates = lambda _screen=None: [candidate]
    panel._map_studio_hover_candidates_near = lambda _x, _y: [candidate]
    mime = QtCore.QMimeData()
    mime.setData(
        ModuleEditorViewportPanel.MAP_ENVIRONMENT_KIT_MIME_TYPE,
        json.dumps(
            {
                "schema": "ghostrigger.map-environment-kit/v1",
                "piece_id": "k1_test_room",
                "asset_id": "k1_test_room",
                "label": "Test straight corridor",
                "game": "K1",
                "rotation_degrees_z": 0.0,
                "scale": 1.0,
            }
        ).encode("utf-8"),
    )

    class DropEvent:
        def __init__(self, event_type, point):
            self._event_type = event_type
            self._point = QtCore.QPointF(point)
            self.accepted = False

        def type(self):
            return self._event_type

        def position(self):
            return self._point

        def mimeData(self):  # noqa: N802
            return mime

        def acceptProposedAction(self):  # noqa: N802
            self.accepted = True

        def ignore(self):
            self.accepted = False

    previews: list[dict[str, object]] = []
    commits: list[dict[str, object]] = []

    def resolve_preview(payload: object) -> None:
        values = dict(payload)
        previews.append(values)
        panel.set_terrain_kit_snap_preview(
            {
                **values,
                "magnet_snapped": True,
                "position": (12.0, 4.0, 0.0),
                "rotation_degrees_z": 180.0,
                "target_room_resref": "grkit0001",
            }
        )

    panel.environmentKitSnapPreviewRequested.connect(resolve_preview)
    panel.environmentKitRequested.connect(commits.append)
    watched = panel.viewport
    canvas_point = QtCore.QPoint(96, 80)
    local_point = watched.mapFromGlobal(panel.viewport.canvas.mapToGlobal(canvas_point))
    try:
        move = DropEvent(QtCore.QEvent.DragMove, local_point)
        assert panel._handle_map_placement_drop_event(move, watched) is True
        assert move.accepted is True
        assert previews and previews[-1]["piece_id"] == "k1_test_room"

        drop = DropEvent(QtCore.QEvent.Drop, local_point)
        assert panel._handle_map_placement_drop_event(drop, watched) is True
        assert drop.accepted is True
        assert len(commits) == 1
        assert commits[0]["position"] == (12.0, 4.0, 0.0)
        assert commits[0]["rotation_degrees_z"] == 180.0
    finally:
        panel.close()
        panel.deleteLater()
        app.processEvents()


def test_resolved_model_is_selected_by_real_gizmo_and_commits_git_transform() -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.core.geometry import model_data as md
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorViewportPanel()
    placement_id = "authored:placeable:0"
    marker = SimpleNamespace(placement_id=placement_id, position=(1.0, 2.0, 0.0), bearing=0.25)
    root = md.ModelNode(name="map_root", flags=int(md.NodeFlags.HEADER))
    group = md.ModelNode(name="placeable", flags=int(md.NodeFlags.HEADER), position=marker.position)
    group.parent = root
    setattr(group, "_gr_map_studio_placement_id", placement_id)
    root.children.append(group)
    panel._room_preview_model = md.KotorModel(name="preview", root_node=root)
    panel._placement_markers = {placement_id: marker}
    emitted: list[tuple[str, object]] = []
    panel.transformEdited.connect(lambda item_id, transform: emitted.append((item_id, transform)))

    try:
        panel._sync_placement_transform_capabilities(placement_id)
        assert panel.viewport._renderer.selected_node is group
        assert panel.scale_gizmo_button.isEnabled() is False
        assert getattr(group, "_gr_map_studio_git_placement") is True

        delta = 0.5
        group.position = (4.0, 5.0, 0.75)
        group.rotation = (0.0, 0.0, math.sin(delta / 2.0), math.cos(delta / 2.0))
        panel._handle_viewport_placement_node_moved(group)

        assert len(emitted) == 1
        item_id, transform = emitted[0]
        assert item_id == placement_id
        assert transform.position == (4.0, 5.0, 0.75)
        assert math.isclose(transform.rotation[2], marker.bearing + delta, abs_tol=1.0e-6)
        assert transform.scale == (1.0, 1.0, 1.0)

        setattr(group, "_gr_transform_previewing", True)
        panel._handle_viewport_placement_node_moved(group)
        assert len(emitted) == 1
    finally:
        panel.close()
        panel.deleteLater()
        app.processEvents()


def test_player_start_model_is_selectable_and_commits_ifo_transform() -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.core.geometry import model_data as md
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorViewportPanel()
    marker = SimpleNamespace(
        placement_id="entry_point",
        kind="entry_point",
        tag="Player Start",
        position=(0.0, -3.0, 0.0),
        bearing=0.0,
        is_spatial=True,
    )
    root = md.ModelNode(name="map_root", flags=int(md.NodeFlags.HEADER))
    player = md.ModelNode(name="entry_point_pmbam", flags=int(md.NodeFlags.HEADER), position=marker.position)
    player.parent = root
    setattr(player, "_gr_map_studio_placement_id", "entry_point")
    root.children.append(player)
    panel._room_preview_model = md.KotorModel(name="preview", root_node=root)
    panel._placement_markers = {"entry_point": marker}
    emitted: list[tuple[str, object]] = []
    panel.transformEdited.connect(lambda item_id, transform: emitted.append((item_id, transform)))

    try:
        panel._sync_placement_transform_capabilities("entry_point")
        assert panel.viewport._renderer.selected_node is player
        assert panel.viewport._transform_gizmo.selected_object is player
        assert panel.scale_gizmo_button.isEnabled() is False
        assert "player start" in panel.scale_gizmo_button.toolTip().lower()

        player.position = (2.0, 1.0, 0.25)
        player.rotation = (0.0, 0.0, math.sin(0.25), math.cos(0.25))
        panel._handle_viewport_placement_node_moved(player)

        assert len(emitted) == 1
        item_id, transform = emitted[0]
        assert item_id == "entry_point"
        assert transform.position == (2.0, 1.0, 0.25)
        assert math.isclose(transform.rotation[2], 0.5, abs_tol=1.0e-6)
    finally:
        panel.close()
        panel.deleteLater()
        app.processEvents()


def test_maya_shift_and_alt_click_share_selection_between_kit_piece_and_player_start() -> None:
    _configure_native_python_roots()
    from PySide6 import QtCore, QtWidgets
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    class _Click:
        def __init__(self, modifier):
            self._modifier = modifier

        def modifiers(self):
            return self._modifier

        def position(self):
            return QtCore.QPointF(10.0, 10.0)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorViewportPanel()
    marker = SimpleNamespace(placement_id="entry_point", position=(0.0, 0.0, 0.0), bearing=0.0)
    primitive_id = "authored_primitive:grmixed_room01:terrain_rock"
    emitted: list[tuple[str, ...]] = []
    panel.itemsSelected.connect(lambda values: emitted.append(tuple(values)))
    try:
        panel._placement_markers = {"entry_point": marker}
        panel.set_map_studio_scene_selection_ids((primitive_id,))

        assert panel._begin_marker_drag("entry_point", _Click(QtCore.Qt.ShiftModifier)) is True
        assert emitted[-1] == (primitive_id, "entry_point")
        assert panel.map_studio_scene_selection_ids() == [primitive_id, "entry_point"]

        assert panel._begin_marker_drag("entry_point", _Click(QtCore.Qt.AltModifier)) is True
        assert emitted[-1] == (primitive_id,)
        assert panel.map_studio_scene_selection_ids() == [primitive_id]
    finally:
        panel.close()
        panel.deleteLater()
        app.processEvents()


def test_outliner_shift_adds_and_alt_removes_without_selecting_a_range() -> None:
    _configure_native_python_roots()
    from PySide6 import QtCore, QtTest, QtWidgets
    from src.gui.panels.module_editor.module_editor_outliner import ModuleEditorOutliner

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    outliner = ModuleEditorOutliner()
    floor = outliner._item("Floor", "authored_primitive:room01:floor", "authored_primitive")
    wall = outliner._item("Wall", "authored_primitive:room01:wall", "authored_primitive")
    player = outliner._item("Player Start", "entry_point", "authored_entry_point")
    outliner.addTopLevelItems((floor, wall, player))
    emitted: list[tuple[str, ...]] = []
    outliner.itemsSelected.connect(lambda values: emitted.append(tuple(values)))
    try:
        outliner.resize(360, 240)
        outliner.show()
        app.processEvents()
        viewport = outliner.viewport()
        QtTest.QTest.mouseClick(viewport, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, outliner.visualItemRect(floor).center())
        QtTest.QTest.mouseClick(viewport, QtCore.Qt.LeftButton, QtCore.Qt.ShiftModifier, outliner.visualItemRect(player).center())

        assert set(emitted[-1]) == {"authored_primitive:room01:floor", "entry_point"}
        assert wall.isSelected() is False

        QtTest.QTest.mouseClick(viewport, QtCore.Qt.LeftButton, QtCore.Qt.AltModifier, outliner.visualItemRect(player).center())

        assert emitted[-1] == ("authored_primitive:room01:floor",)
        assert floor.isSelected() is True
        assert player.isSelected() is False
    finally:
        outliner.close()
        outliner.deleteLater()
        app.processEvents()


def test_outliner_light_selection_binds_gizmo_and_commits_position() -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.core.geometry import model_data as md
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorViewportPanel()
    light_id = "authored_light:light_1"
    root = md.ModelNode(name="map_root", flags=int(md.NodeFlags.HEADER))
    light = md.ModelNode(name="key_light", flags=int(md.NodeFlags.LIGHT), position=(1.0, 2.0, 3.0))
    light.parent = root
    setattr(light, "_gr_map_studio_authored_light", True)
    setattr(light, "_gr_light_id", light_id)
    root.children.append(light)
    panel._room_preview_model = md.KotorModel(name="preview", root_node=root)
    emitted: list[tuple[str, object]] = []
    panel.transformEdited.connect(lambda item_id, transform: emitted.append((item_id, transform)))

    try:
        panel.set_transform_gizmo_mode("scale", announce=False)
        panel._sync_placement_transform_capabilities(light_id)

        assert panel.viewport._renderer.selected_node is light
        assert panel.viewport._transform_gizmo.selected_object is light
        assert panel.transform_gizmo_mode() == "translate"
        assert panel.rotate_gizmo_button.isEnabled() is False
        assert panel.scale_gizmo_button.isEnabled() is False
        assert tuple(getattr(light, "_gr_gizmo_world_position")) == (1.0, 2.0, 3.0)

        light.position = (4.5, -1.25, 6.0)
        panel._handle_viewport_placement_node_moved(light)

        assert len(emitted) == 1
        item_id, transform = emitted[0]
        assert item_id == light_id
        assert transform.position == (4.5, -1.25, 6.0)
    finally:
        panel.close()
        panel.deleteLater()
        app.processEvents()


def test_outliner_selection_change_clears_stale_room_geometry_handles() -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorViewportPanel()
    try:
        panel._map_studio_component_selection = [{"room_resref": "grdev01_room01", "kind": "edge"}]
        panel.set_selected_room_primitives((("grdev01_room01", "floor"),))
        panel._universal_transform_overlay = object()
        panel.viewport.set_map_studio_universal_transform_overlay(panel._universal_transform_overlay)
        panel.viewport.set_map_studio_room_outline_edge_highlight(
            {
                "room_resref": "grdev01_room01",
                "edge_index": 2,
                "world_start": (0.0, 0.0, 0.0),
                "world_end": (1.0, 0.0, 0.0),
            }
        )

        panel.clear_map_studio_room_geometry_selection()

        assert panel.map_studio_component_selection() == []
        assert panel.selected_room_primitives() == []
        assert panel._universal_transform_overlay is None
        assert panel.viewport._map_studio_universal_transform_overlay is None
        assert panel.viewport._map_studio_room_outline_edge_highlight is None
    finally:
        panel.close()
        panel.deleteLater()
        app.processEvents()


def test_resolved_model_drag_updates_preview_without_full_refresh() -> None:
    _configure_native_python_roots()
    from src.core.geometry import model_data as md
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    node = md.ModelNode(name="placeable", flags=int(md.NodeFlags.HEADER), position=(0.0, 0.0, 0.0))
    renders: list[dict[str, object]] = []
    fake = SimpleNamespace(
        _marker_drag={
            "mode": "translate",
            "preview_node": node,
            "pending_position": (3.0, -2.0, 1.0),
            "preview_start_position": (0.0, 0.0, 0.0),
        },
        _hover_candidate_cache_key=("stale",),
        _mark_room_preview_model_promoted=lambda: None,
        viewport=SimpleNamespace(_request_render=lambda **kwargs: renders.append(kwargs)),
        _quat_multiply_xyzw=ModuleEditorViewportPanel._quat_multiply_xyzw,
    )

    ModuleEditorViewportPanel._preview_marker_drag_transform(fake)

    assert node.position == (3.0, -2.0, 1.0)
    assert fake._hover_candidate_cache_key is None
    assert renders and renders[-1]["fast"] is True


def test_end_key_routes_selected_placement_to_downward_ground_snap() -> None:
    _configure_native_python_roots()
    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorViewportPanel()
    requested: list[bool] = []
    panel.groundSnapShortcutRequested.connect(lambda: requested.append(True))
    try:
        event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_End, QtCore.Qt.NoModifier)
        assert panel._handle_map_studio_shortcut_key(event) is True
        assert requested == [True]
    finally:
        panel.close()
        panel.deleteLater()
        app.processEvents()

    window_source = (
        ROOT
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")
    assert 'setObjectName("mapStudioGroundSnapShortcut")' in window_source
    assert "snap_map_studio_selected_placement_to_ground" in window_source
    assert "downward_only=True" in window_source
    assert 'snap_to_walkmesh=bool(values.get("snap_to_walkmesh", True))' in window_source
