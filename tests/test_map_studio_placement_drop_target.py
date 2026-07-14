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

            drop_event = DropEvent(QtCore.QEvent.Drop, local_point)
            assert panel._handle_map_placement_drop_event(drop_event, watched) is True
            assert drop_event.accepted is True
            assert drop_event.ignored is False

        assert len(emitted) == 2
        assert all(request["room_resref"] == "grdrop01" for request in emitted)
        assert all(request["surface_role"] == "authored_floor" for request in emitted)
        assert all(len(request["position"]) == 3 for request in emitted)
    finally:
        nested.close()
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
