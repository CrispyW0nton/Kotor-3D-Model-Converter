from __future__ import annotations

import copy
import sys
from pathlib import Path
from types import MethodType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
DISPLAY = ROOT / "native/GhostRigger.Core.GUI.Display/Python/src"
TOOLS = ROOT / "native/GhostRigger.Core.Tools/Python/src"


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


class _Signal:
    def __init__(self) -> None:
        self.rows: list[tuple[object, ...]] = []

    def emit(self, *values: object) -> None:
        self.rows.append(tuple(values))


class _Label:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, value: object) -> None:  # noqa: N802 - Qt-shaped test double
        self.text = str(value)


class _Viewport:
    def __init__(self) -> None:
        self.payloads: list[object] = []
        self.clear_count = 0

    def set_map_studio_modeling_points_overlay(self, payload: object) -> None:
        self.payloads.append(copy.deepcopy(payload))

    def clear_map_studio_modeling_points_overlay(self) -> None:
        self.clear_count += 1


def _context(point: tuple[float, float, float]):
    return SimpleNamespace(
        is_hit=True,
        component_type="face",
        room_resref="qd_room",
        mesh_role="live_surface",
        face_index=0,
        vertex_index=-1,
        edge_indices=(-1, -1),
        mesh_vertex_index=-1,
        mesh_edge_indices=(-1, -1),
        world_point=point,
    )


def _quad_draw_owner():
    _configure_native_python_roots()
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    owner = SimpleNamespace(
        viewport=_Viewport(),
        _active_map_studio_modeling_tool={
            "key": "quad_draw",
            "picks": [],
            "points": [],
            "point_entries": [],
        },
        _map_studio_live_surface=("qd_room", "live_surface"),
        _hover_context=None,
        _quad_draw_feedback_payload=None,
        marker_summary_label=_Label(),
        modelingToolGestureCommitted=_Signal(),
        _update_map_studio_hover=lambda _event, force=False: None,
        _map_studio_selection_face_points=lambda _context: (),
    )
    owner._modeling_entry_from_context = MethodType(ModuleEditorViewportPanel._modeling_entry_from_context, owner)
    owner._sync_quad_draw_feedback = MethodType(ModuleEditorViewportPanel._sync_quad_draw_feedback, owner)
    owner._clear_quad_draw_feedback = MethodType(ModuleEditorViewportPanel._clear_quad_draw_feedback, owner)
    return ModuleEditorViewportPanel, owner


def test_quad_draw_first_three_clicks_publish_feedback_and_fourth_clears_without_scene_mutation() -> None:
    panel, owner = _quad_draw_owner()
    scene_sentinel = {"kmap_revision": 12, "rooms": ("qd_room",)}
    original_scene = copy.deepcopy(scene_sentinel)
    points = (
        (0.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        (2.0, 2.0, 0.0),
        (0.0, 2.0, 0.0),
    )

    for point in points[:3]:
        owner._hover_context = _context(point)
        assert panel._handle_active_modeling_tool_click(owner, object()) is True

    assert [len(payload["points"]) for payload in owner.viewport.payloads] == [1, 2, 3]
    assert owner.viewport.payloads[-1]["close_preview"] is False
    assert owner.viewport.payloads[-1]["preview_point"] == ()

    # Moving toward a prospective fourth point adds the two closing preview
    # segments, still without committing or mutating the scene.
    owner._hover_context = _context(points[3])
    owner._sync_quad_draw_feedback()
    assert owner.viewport.payloads[-1]["close_preview"] is True
    assert owner.viewport.payloads[-1]["preview_point"] == points[3]

    assert panel._handle_active_modeling_tool_click(owner, object()) is True
    assert owner.viewport.clear_count == 1
    assert owner._active_map_studio_modeling_tool["points"] == []
    assert owner._active_map_studio_modeling_tool["point_entries"] == []
    assert owner._active_map_studio_modeling_tool["picks"] == []
    assert len(owner.modelingToolGestureCommitted.rows) == 1
    tool, payload = owner.modelingToolGestureCommitted.rows[0]
    assert tool == "quad_draw"
    assert tuple(payload["points"]) == points
    assert scene_sentinel == original_scene, "feedback clicks must not mutate KMAP/scene state"


def test_quad_draw_escape_exits_and_clears_feedback_exactly_once() -> None:
    _configure_native_python_roots()
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel
    from src.gui.panels.module_editor import module_editor_viewport_panel as viewport_module

    QtCore = viewport_module.QtCore

    _, owner = _quad_draw_owner()
    owner._active_map_studio_modeling_tool["points"] = [(1.0, 2.0, 3.0)]
    owner._quad_draw_feedback_payload = {"tool": "quad_draw", "points": ((1.0, 2.0, 3.0),)}
    owner._placement_context = {"enabled": False}
    owner._component_extrude_armed = None
    owner._component_bevel_armed = None
    event = SimpleNamespace(
        modifiers=lambda: QtCore.Qt.NoModifier,
        key=lambda: QtCore.Qt.Key_Escape,
    )

    handled = ModuleEditorViewportPanel._handle_map_studio_shortcut_key(owner, event)

    assert handled is True
    assert owner._active_map_studio_modeling_tool is None
    assert owner.viewport.clear_count == 1
    assert owner._quad_draw_feedback_payload is None
    assert owner.marker_summary_label.text == "Quad Draw exited."


def test_quad_draw_overlay_uses_theme_anchor_dots_polyline_and_closing_preview() -> None:
    _configure_native_python_roots()
    from src.gui.viewports.viewport_core.widgets.overlay_layers import ViewportOverlayLayersMixin

    class Draw:
        def __init__(self) -> None:
            self.lines: list[tuple[object, object, object]] = []
            self.ellipses: list[tuple[object, object, object]] = []
            self.texts: list[tuple[object, object, object]] = []

        def line(self, points, *, fill, width) -> None:
            self.lines.append((tuple(points), fill, width))

        def ellipse(self, bounds, *, fill=None, outline=None, width=1) -> None:
            self.ellipses.append((tuple(bounds), fill, outline))

        def text(self, point, value, *, fill) -> None:
            self.texts.append((tuple(point), str(value), fill))

    theme = SimpleNamespace(
        color=lambda token, fallback: {
            "accent.secondary": "#123456",
            "accent.primary": "#f08020",
        }.get(token, fallback)
    )
    owner = SimpleNamespace(
        _current_theme=theme,
        _renderer=SimpleNamespace(_proj=lambda x, y, z, _w, _h: (x * 10.0, y * 10.0, z + 1.0)),
        _map_studio_modeling_points_overlay={
            "tool": "quad_draw",
            "points": ((1.0, 1.0, 0.0), (3.0, 1.0, 0.0), (3.0, 3.0, 0.0)),
            "preview_point": (1.0, 3.0, 0.0),
            "close_preview": True,
        },
    )
    owner._map_studio_marker_rgba = MethodType(ViewportOverlayLayersMixin._map_studio_marker_rgba, owner)
    owner._map_studio_theme_rgba = MethodType(ViewportOverlayLayersMixin._map_studio_theme_rgba, owner)
    owner._map_studio_project_point = MethodType(ViewportOverlayLayersMixin._map_studio_project_point, owner)
    owner._map_studio_draw_dashed_line = ViewportOverlayLayersMixin._map_studio_draw_dashed_line
    draw = Draw()

    ViewportOverlayLayersMixin._draw_map_studio_modeling_points_overlay(owner, draw, 640, 480)

    themed_anchor = (0x12, 0x34, 0x56, 255)
    assert any(fill == themed_anchor for _bounds, fill, _outline in draw.ellipses)
    assert len(draw.ellipses) == 8, "three two-layer anchors plus the two-layer prospective fourth dot"
    assert any(len(points) == 3 and fill == themed_anchor for points, fill, _width in draw.lines)
    assert len(draw.lines) >= 6, "polyline plus dashed next and closing segments must be visible"
    assert [value for _point, value, _fill in draw.texts] == ["1", "2", "3"]


def test_quad_draw_feedback_sources_are_mirrored_and_wired_into_overlay_pipeline() -> None:
    relative = Path("gui/panels/module_editor/module_editor_viewport_panel.py")
    assert (DISPLAY / relative).read_bytes() == (TOOLS / relative).read_bytes()

    scene_models = (DISPLAY / "gui/viewports/viewport_core/widgets/scene_models.py").read_text(encoding="utf-8")
    overlay = (DISPLAY / "gui/viewports/viewport_core/widgets/overlay_layers.py").read_text(encoding="utf-8")
    pipeline = (DISPLAY / "gui/viewports/viewport_core/widgets/rendering_pipeline.py").read_text(encoding="utf-8")
    panel = (DISPLAY / relative).read_text(encoding="utf-8")

    assert "def set_map_studio_modeling_points_overlay" in scene_models
    assert "def clear_map_studio_modeling_points_overlay" in scene_models
    assert "def _draw_map_studio_modeling_points_overlay" in overlay
    assert "self._draw_map_studio_modeling_points_overlay(draw, w, h)" in pipeline
    assert '"close_preview": len(points) == 3 and len(preview_point) == 3' in panel
    assert "self._clear_quad_draw_feedback()" in panel
