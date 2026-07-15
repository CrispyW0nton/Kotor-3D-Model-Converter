"""Map Studio hover picker + ZModeler radial marking-menu scaffold tests (T2905/M29).

Covers the read-only slice: hover-context classification, marking-menu
registry trees, payload mirror identity, and the radial widget scaffold.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import MethodType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> bytes:
    return (ROOT / rel).read_bytes()


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def test_hover_context_payload_copies_are_byte_identical() -> None:
    for name in ("map_studio_hover_context.py", "map_studio_marking_menu_registry.py"):
        scene = _read(f"native/GhostRigger.Core.Scene/Python/src/core/modules/{name}")
        tools = _read(f"native/GhostRigger.Core.Tools/Python/src/core/modules/{name}")
        assert scene == tools, f"{name} diverged between Scene and Tools payloads"
    for panel_name in ("component_marking_menu.py", "gmodeler_marking_menu.py"):
        panel = f"gui/panels/module_editor/{panel_name}"
        tools_panel = _read(f"native/GhostRigger.Core.Tools/Python/src/{panel}")
        display_panel = _read(f"native/GhostRigger.Core.GUI.Display/Python/src/{panel}")
        assert tools_panel == display_panel, f"{panel_name} diverged between Tools and Display payloads"
    viewport = "gui/panels/module_editor/module_editor_viewport_panel.py"
    tools_vp = _read(f"native/GhostRigger.Core.Tools/Python/src/{viewport}")
    display_vp = _read(f"native/GhostRigger.Core.GUI.Display/Python/src/{viewport}")
    assert tools_vp == display_vp, "viewport panel diverged between Tools and Display payloads"


def _tri(
    face_index: int,
    sp,
    wp,
    *,
    room="grtest01",
    role="render",
    walkable=None,
    depth=10.0,
    view_depths=(),
    uv_points=(),
    material="wall_tex",
    vertex_indices=(-1, -1, -1),
):
    _configure_native_python_roots()
    from src.core.modules.map_studio_hover_context import MapStudioHoverCandidateFace

    return MapStudioHoverCandidateFace(
        room_resref=room,
        mesh_role=role,
        face_index=face_index,
        screen_points=tuple(sp),
        world_points=tuple(wp),
        view_depths=tuple(view_depths),
        uv_points=tuple(uv_points),
        vertex_indices=tuple(vertex_indices),
        material=material,
        walkable=walkable,
        depth=depth,
    )


_SCREEN = ((100.0, 100.0), (200.0, 100.0), (150.0, 200.0))
_WORLD = ((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (2.0, 4.0, 0.0))


def test_hover_picker_classifies_vertex_edge_face_and_walkmesh() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_hover_context import pick_map_studio_hover_context

    render = _tri(3, _SCREEN, _WORLD)
    wok = _tri(7, _SCREEN, _WORLD, role="walkmesh", walkable=True, depth=11.0)
    candidates = (render, wok)

    vertex_hit = pick_map_studio_hover_context(candidates, 101.0, 101.0)
    assert vertex_hit.component_type == "vertex"
    assert vertex_hit.vertex_index == 0
    assert vertex_hit.room_resref == "grtest01"
    assert vertex_hit.face_index == 3

    edge_hit = pick_map_studio_hover_context(candidates, 150.0, 98.0)
    assert edge_hit.component_type == "edge"
    assert edge_hit.edge_indices == (0, 1)

    face_hit = pick_map_studio_hover_context(candidates, 150.0, 140.0)
    assert face_hit.component_type == "face"
    assert face_hit.walkable is None
    assert face_hit.material == "wall_tex"

    wok_hit = pick_map_studio_hover_context(candidates, 150.0, 140.0, prefer_walkmesh=True)
    assert wok_hit.component_type == "walkmesh_face"
    assert wok_hit.walkable is True
    assert wok_hit.face_index == 7

    miss = pick_map_studio_hover_context(candidates, 400.0, 400.0)
    assert miss.component_type == "none"
    assert not miss.is_hit


def test_hover_picker_walkmesh_only_candidates_never_classify_vertices() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_hover_context import pick_map_studio_hover_context

    wok_only = (_tri(0, _SCREEN, _WORLD, role="walkmesh", walkable=False),)
    hit = pick_map_studio_hover_context(wok_only, 101.0, 101.0)
    assert hit.component_type == "walkmesh_face"
    assert hit.walkable is False


def test_hover_picker_prefers_nearer_depth_between_stacked_faces() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_hover_context import pick_map_studio_hover_context

    near = _tri(1, _SCREEN, _WORLD, depth=5.0)
    far = _tri(2, _SCREEN, _WORLD, depth=50.0)
    hit = pick_map_studio_hover_context((far, near), 150.0, 140.0)
    assert hit.face_index == 1


def test_hover_picker_uses_cursor_depth_instead_of_triangle_average() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_hover_context import pick_map_studio_hover_context

    screen = ((0.0, 0.0), (100.0, 0.0), (0.0, 100.0))
    world = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0))
    # The near triangle's average depth is 14, but it is about 2.44 units
    # deep at this cursor.  The legacy average-depth comparison incorrectly
    # chose the constant-depth face at 6.
    near_at_cursor = _tri(11, screen, world, depth=14.0, view_depths=(2.0, 20.0, 20.0))
    farther_at_cursor = _tri(12, screen, world, depth=6.0, view_depths=(6.0, 6.0, 6.0))

    hit = pick_map_studio_hover_context(
        (farther_at_cursor, near_at_cursor),
        10.0,
        10.0,
        tolerance_px=0.0,
    )

    assert hit.component_type == "face"
    assert hit.face_index == 11
    assert hit.view_depth == pytest.approx(1.0 / 0.41)


@pytest.mark.parametrize(
    "hidden_screen",
    (
        ((80.0, 80.0), (105.0, 90.0), (85.0, 120.0)),  # vertex exactly under cursor
        ((60.0, 80.0), (100.0, 80.0), (80.0, 120.0)),  # edge exactly under cursor
    ),
)
def test_hover_picker_rejects_components_hidden_by_nearer_face(hidden_screen) -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_hover_context import pick_map_studio_hover_context

    front = _tri(
        20,
        ((0.0, 0.0), (200.0, 0.0), (0.0, 200.0)),
        ((0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (0.0, 20.0, 0.0)),
        room="front_room",
        role="stock_room_0",
        depth=5.0,
        view_depths=(5.0, 5.0, 5.0),
    )
    hidden = _tri(
        21,
        hidden_screen,
        ((0.0, 0.0, -10.0), (2.0, 0.0, -10.0), (0.0, 2.0, -10.0)),
        room="rear_room",
        role="stock_room_1",
        depth=20.0,
        view_depths=(20.0, 20.0, 20.0),
    )

    hit = pick_map_studio_hover_context((hidden, front), 80.0, 80.0)

    assert hit.component_type == "face"
    assert hit.face_index == 20
    assert hit.room_resref == "front_room"
    assert hit.mesh_role == "stock_room_0"


def test_hover_picker_interpolates_world_and_uv_perspective_correctly() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_hover_context import pick_map_studio_hover_context

    candidate = _tri(
        30,
        ((0.0, 0.0), (100.0, 0.0), (0.0, 100.0)),
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)),
        room="koq200_01f",
        role="stock_room_0",
        view_depths=(1.0, 2.0, 2.0),
        uv_points=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
    )

    hit = pick_map_studio_hover_context((candidate,), 25.0, 25.0, tolerance_px=0.0)

    assert hit.component_type == "face"
    assert hit.room_resref == "koq200_01f"
    assert hit.mesh_role == "stock_room_0"
    assert hit.world_point == pytest.approx((1.0 / 3.0, 1.0 / 3.0, 0.0))
    assert hit.uv == pytest.approx((1.0 / 6.0, 1.0 / 6.0))
    assert hit.view_depth == pytest.approx(4.0 / 3.0)


def test_hover_picker_reports_stable_mesh_identity_adjacency_and_edge_selector() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_hover_context import pick_map_studio_hover_context

    first = _tri(
        4,
        ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0)),
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)),
        vertex_indices=(10, 11, 12),
    )
    second = _tri(
        9,
        ((0.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
        ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)),
        vertex_indices=(10, 12, 13),
    )

    shared_edge = pick_map_studio_hover_context((first, second), 50.0, 50.0)
    assert shared_edge.component_type == "edge"
    assert shared_edge.mesh_edge_indices == (10, 12)
    assert shared_edge.adjacent_face_indices == (4, 9)
    assert shared_edge.is_border is False

    vertex = pick_map_studio_hover_context((first, second), 3.0, 1.0)
    assert vertex.component_type == "vertex"
    assert vertex.vertex_index == 0  # compatibility corner for geometry ops
    assert vertex.mesh_vertex_index == 10  # stable identity across both faces
    assert vertex.adjacent_face_indices == (4, 9)
    assert vertex.is_border is True
    assert vertex.selector_world_point != vertex.selector_origin_world_point

    face = pick_map_studio_hover_context((first, second), 50.0, 20.0)
    assert face.component_type == "face"
    assert face.selector_edge_corners == (0, 1)
    assert face.selector_world_point == (0.5, 0.0, 0.0)
    assert face.edge_direction != (0.0, 0.0, 0.0)


def test_marking_menu_registry_builds_context_sensitive_trees() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_hover_context import MapStudioHoverContext
    from src.core.modules.map_studio_marking_menu_registry import (
        available_map_studio_marking_menu_trees,
        map_studio_marking_menu_action,
        map_studio_marking_menu_tree_for_hover,
    )

    trees = {tree.hover_context: tree for tree in available_map_studio_marking_menu_trees()}
    assert set(trees) == {"face", "edge", "vertex", "walkmesh_face"}

    face_tree = map_studio_marking_menu_tree_for_hover("face")
    assert face_tree is not None
    assert "face_extrude" in face_tree.action_keys
    assert "walkmesh_toggle_walkable" not in face_tree.action_keys

    wok_tree = map_studio_marking_menu_tree_for_hover(
        MapStudioHoverContext(component_type="walkmesh_face", room_resref="grtest01", face_index=1, walkable=True)
    )
    assert wok_tree is not None
    assert "walkmesh_toggle_walkable" in wok_tree.action_keys
    assert "face_extrude" not in wok_tree.action_keys

    assert map_studio_marking_menu_tree_for_hover(MapStudioHoverContext()) is None
    assert map_studio_marking_menu_tree_for_hover(None) is None

    # Implemented actions are wired to real geometry ops; everything else
    # stays read-only scaffold. All actions keep a KOTOR guardrail.
    wired = {
        "face_delete",
        "face_set_texture",
        "face_extrude",
        "face_inset",
        "face_move",
        "face_flat",
        "face_flip",
        "face_split",
            "edge_move",
            "edge_extrude",
            "edge_bevel",
            "edge_split",
        "edge_collapse",
        "edge_delete",
        "vertex_move",
        "vertex_weld",
        "vertex_delete",
    }
    for tree in trees.values():
        assert len(tree.action_keys) == len(set(tree.action_keys)), f"duplicate action key in {tree.hover_context} menu"
        for action in tree.actions:
            expected = action.key in wired
            assert action.implemented is expected, (
                f"{action.key} implemented={action.implemented}; only {sorted(wired)} are wired to geometry"
            )
            assert action.default_target in action.targets
            assert action.kotor_guardrail, f"{action.key} missing KOTOR guardrail"
    assert map_studio_marking_menu_action("face_extrude").targets[0] == "Single Face"
    assert map_studio_marking_menu_action("does_not_exist") is None


def test_gmodeler_marking_menu_sectioned_panel_runtime() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.core.modules.map_studio_marking_menu_registry import map_studio_marking_menu_tree_for_hover
    from src.gui.panels.module_editor.gmodeler_marking_menu import MapStudioGModelerMarkingMenu

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MapStudioGModelerMarkingMenu._sticky_action.clear()
    MapStudioGModelerMarkingMenu._sticky_target.clear()

    # Face context: the panel shows every registry action plus Do Nothing and
    # the TARGET grid for the current (first) action — all at once.
    tree = map_studio_marking_menu_tree_for_hover("face")
    menu = MapStudioGModelerMarkingMenu(tree)
    try:
        assert menu.action_keys() == tuple(action.key for action in tree.actions)
        cell_kinds = {cell.kind for cell in menu.cells()}
        assert {"action", "target", "do_nothing"} <= cell_kinds
        assert menu.current_action_key() == tree.actions[0].key
        assert menu.current_target() == tree.actions[0].default_target
        target_labels = [cell.label for cell in menu.cells() if cell.kind == "target"]
        assert target_labels == list(tree.actions[0].targets)

        # Selecting a target re-targets without executing (sticky, panel open).
        selections: list[tuple[str, str]] = []
        menu.actionSelected.connect(lambda key, target: selections.append((key, target)))
        other_target = tree.actions[0].targets[1]
        menu.select_target(other_target)
        assert selections == []
        assert menu.current_target() == other_target

        # Activating the action executes with the sticky target and closes.
        menu.activate_action(tree.actions[0].key)
        assert selections == [(tree.actions[0].key, other_target)]
    finally:
        menu.close()
        app.processEvents()


    # Sticky state survives reopening (ZModeler keeps the current action).
    menu2 = MapStudioGModelerMarkingMenu(tree)
    try:
        assert menu2.current_action_key() == tree.actions[0].key
        assert menu2.current_target() == tree.actions[0].targets[1]
        menu2.set_current_action("face_delete")
        assert menu2.current_action_key() == "face_delete"
    finally:
        menu2.close()
        app.processEvents()

    # Vertex context: single-target action executes with its default target.
    vertex_tree = map_studio_marking_menu_tree_for_hover("vertex")
    vertex_menu = MapStudioGModelerMarkingMenu(vertex_tree)
    try:
        vertex_selections: list[tuple[str, str]] = []
        vertex_menu.actionSelected.connect(lambda key, target: vertex_selections.append((key, target)))
        vertex_menu.activate_action("vertex_move")
        assert vertex_selections == [("vertex_move", "Single Vertex")]
    finally:
        vertex_menu.close()
        app.processEvents()


def test_component_marking_menu_neutral_identity_and_compatibility_alias() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtGui, QtWidgets
    from src.core.modules.map_studio_marking_menu_registry import map_studio_marking_menu_tree_for_hover
    from src.gui.panels.module_editor.component_marking_menu import (
        BRAND_LABEL,
        MapStudioComponentMarkingMenu,
    )
    from src.gui.panels.module_editor.gmodeler_marking_menu import (
        MapStudioGModelerMarkingMenu,
    )

    component_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/component_marking_menu.py"
    ).lower()
    assert b"gmodeler" not in component_source
    assert MapStudioGModelerMarkingMenu is MapStudioComponentMarkingMenu
    assert BRAND_LABEL == "MODELING"

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    menu = MapStudioComponentMarkingMenu(map_studio_marking_menu_tree_for_hover("face"))
    try:
        visible_identity = " ".join(
            (
                BRAND_LABEL,
                menu.accessibleName(),
                menu._header_text(),
                *(cell.label for cell in menu.cells()),
            )
        ).lower()
        assert menu.objectName() == "mapStudioComponentMarkingMenu"
        assert "gmodeler" not in visible_identity
        assert "zmodeler" not in visible_identity

        image = QtGui.QImage(menu.size(), QtGui.QImage.Format_ARGB32_Premultiplied)
        image.fill(QtGui.QColor(0, 0, 0, 0))
        menu.render(image)
        assert not image.isNull()
    finally:
        menu.close()
        app.processEvents()


def test_viewport_panel_hover_probe_wiring_source() -> None:
    panel = _read("native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py").decode("utf-8")
    assert "hoverContextChanged = QtCore.Signal(object)" in panel
    assert "def set_map_studio_hover_probe" in panel
    assert "def _map_studio_hover_candidates" in panel
    assert "pick_map_studio_hover_context(" in panel
    assert 'face_uvs = getattr(mesh_node, "face_uvs", ()) or ()' in panel
    assert 'uvs = getattr(mesh_node, "uvs", ()) or ()' in panel
    assert "_map_studio_face_uv_points(mesh_node, face_index, face_vertex_indices)" in panel
    assert "view_depths=tuple(view_depths)" in panel
    assert "uv_points=uv_points" in panel
    assert "key == QtCore.Qt.Key_Space" in panel
    assert "self.modeMarkingMenuRequested.emit(QtGui.QCursor.pos())" in panel

    window = _read("native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py").decode("utf-8")
    assert "hoverContextChanged.connect(self._handle_map_studio_hover_context_changed)" in window
    assert "def _open_map_studio_component_marking_menu" in window
    assert "MapStudioComponentMarkingMenu" in window
    assert "def _open_map_studio_gmodeler_marking_menu" not in window
    assert "MapStudioRadialMarkingMenu" not in window, "deprecated radial pie must stay unwired"
    # Flat-QMenu fallback preserved for T2600 contract.
    assert "def _build_map_studio_mode_marking_menu" in window
    assert "def _build_map_studio_tool_marking_menu" in window

    display = _read("native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/scene_models.py").decode("utf-8")
    assert "def set_map_studio_hover_highlight" in display
    overlay = _read("native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/overlay_layers.py").decode("utf-8")
    assert "def _draw_map_studio_hover_highlight" in overlay
    pipeline = _read("native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/rendering_pipeline.py").decode("utf-8")
    assert "self._draw_map_studio_hover_highlight(draw, w, h)" in pipeline


def test_viewport_projected_candidate_preserves_depth_and_uv_channels() -> None:
    _configure_native_python_roots()
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    owner = SimpleNamespace(_map_studio_face_normal=lambda _points: (0.0, 0.0, 1.0))

    def project(x, y, z, _width, _height):
        return (x * 10.0, y * 10.0, z + 10.0)

    candidate = ModuleEditorViewportPanel._map_studio_projected_candidate(
        owner,
        project,
        640,
        480,
        ((0.0, 0.0, 1.0), (2.0, 0.0, 2.0), (0.0, 2.0, 4.0)),
        room_resref="koq200_01f",
        mesh_role="stock_room_0",
        material="LKA_wall01",
        face_index=7,
        walkable=None,
        vertex_indices=(4, 9, 12),
        uv_points=((0.0, 0.0), (1.0, 0.0), (0.25, 1.0)),
    )

    assert candidate is not None
    assert candidate.room_resref == "koq200_01f"
    assert candidate.mesh_role == "stock_room_0"
    assert candidate.face_index == 7
    assert candidate.vertex_indices == (4, 9, 12)
    assert candidate.view_depths == pytest.approx((11.0, 12.0, 14.0))
    assert tuple(candidate.uv_points[0]) == pytest.approx((0.0, 0.0))
    assert tuple(candidate.uv_points[1]) == pytest.approx((1.0, 0.0))
    assert tuple(candidate.uv_points[2]) == pytest.approx((0.25, 1.0))


def test_viewport_hover_candidates_use_seam_expanded_per_corner_uvs() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_hover_context import pick_map_studio_hover_context
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    # Geometry vertices 0..2 deliberately point at a different UV triangle.
    # The rendered face instead uses seam-expanded tverts 3..5.
    mesh = SimpleNamespace(
        vertices=((0.0, 0.0, 1.0), (100.0, 0.0, 2.0), (0.0, 100.0, 2.0)),
        faces=((0, 1, 2),),
        uvs=(
            (0.02, 0.03),
            (0.11, 0.07),
            (0.09, 0.19),
            (0.61, 0.17),
            (0.94, 0.23),
            (0.72, 0.91),
        ),
        face_uvs=((3, 4, 5),),
        texture="asym_seam",
        _gr_map_studio_mesh_role="stock_room_0",
        _gr_map_studio_backdrop=False,
    )
    room = SimpleNamespace(
        children=(mesh,),
        position=(0.0, 0.0, 0.0),
        _gr_map_studio_room_resref="koq200_01f",
        _gr_map_studio_backdrop=False,
    )
    owner = SimpleNamespace(
        viewport=SimpleNamespace(_renderer=SimpleNamespace(_proj=lambda x, y, z, _w, _h: (x, y, z))),
        _room_preview_model=SimpleNamespace(root_node=SimpleNamespace(children=(room,))),
        _terrain_walkability_overlay=None,
        _hover_component_mode="face",
        _viewport_canvas_size=lambda: (640, 480),
    )
    owner._map_studio_face_normal = ModuleEditorViewportPanel._map_studio_face_normal
    owner._map_studio_face_uv_points = ModuleEditorViewportPanel._map_studio_face_uv_points
    owner._map_studio_projected_candidate = MethodType(
        ModuleEditorViewportPanel._map_studio_projected_candidate,
        owner,
    )

    candidates = ModuleEditorViewportPanel._map_studio_hover_candidates(owner)

    assert len(candidates) == 1
    assert tuple(candidates[0].uv_points[0]) == pytest.approx((0.61, 0.17))
    assert tuple(candidates[0].uv_points[1]) == pytest.approx((0.94, 0.23))
    assert tuple(candidates[0].uv_points[2]) == pytest.approx((0.72, 0.91))
    hit = pick_map_studio_hover_context(candidates, 25.0, 25.0, tolerance_px=0.0)
    assert hit.component_type == "face"
    # Perspective weights at this cursor are (2/3, 1/6, 1/6), not the
    # screen-space (1/2, 1/4, 1/4) weights.
    assert hit.uv == pytest.approx((0.6833333333, 0.3033333333))


def test_viewport_face_uv_resolution_falls_back_per_invalid_corner() -> None:
    _configure_native_python_roots()
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    mesh = SimpleNamespace(
        faces=((0, 1, 2),),
        uvs=((0.01, 0.02), (0.12, 0.24), (0.31, 0.48), (0.77, 0.13), (0.88, 0.79)),
        face_uvs=((3, 999, 4),),
    )

    points = ModuleEditorViewportPanel._map_studio_face_uv_points(mesh, 0, (0, 1, 2))

    assert tuple(points[0]) == pytest.approx((0.77, 0.13))
    assert tuple(points[1]) == pytest.approx((0.12, 0.24))
    assert tuple(points[2]) == pytest.approx((0.88, 0.79))


def test_hover_candidate_generation_skips_skybox_and_backdrop_nodes() -> None:
    _configure_native_python_roots()
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    def mesh(role: str, *, backdrop: bool = False):
        return SimpleNamespace(
            vertices=((0.0, 0.0, 1.0), (100.0, 0.0, 1.0), (0.0, 100.0, 1.0)),
            faces=((0, 1, 2),),
            uvs=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
            texture="LKA_wall01",
            _gr_map_studio_mesh_role=role,
            _gr_map_studio_backdrop=backdrop,
        )

    editable_mesh = mesh("stock_room_0")
    nested_backdrop = mesh("backdrop", backdrop=True)
    editable_room = SimpleNamespace(
        children=(editable_mesh, nested_backdrop),
        position=(0.0, 0.0, 0.0),
        _gr_map_studio_room_resref="koq200_01f",
        _gr_map_studio_backdrop=False,
    )
    backdrop_room = SimpleNamespace(
        children=(mesh("skybox"),),
        position=(0.0, 0.0, 0.0),
        _gr_map_studio_room_resref="skybox",
        _gr_map_studio_backdrop=True,
    )
    renderer = SimpleNamespace(_proj=lambda x, y, z, _w, _h: (x, y, z))
    owner = SimpleNamespace(
        viewport=SimpleNamespace(_renderer=renderer),
        _room_preview_model=SimpleNamespace(root_node=SimpleNamespace(children=(backdrop_room, editable_room))),
        _terrain_walkability_overlay=None,
        _hover_component_mode="face",
        _viewport_canvas_size=lambda: (640, 480),
    )
    owner._map_studio_face_normal = ModuleEditorViewportPanel._map_studio_face_normal
    owner._map_studio_face_uv_points = ModuleEditorViewportPanel._map_studio_face_uv_points
    owner._map_studio_projected_candidate = MethodType(
        ModuleEditorViewportPanel._map_studio_projected_candidate,
        owner,
    )

    candidates = ModuleEditorViewportPanel._map_studio_hover_candidates(owner)

    assert len(candidates) == 1
    assert candidates[0].room_resref == "koq200_01f"
    assert candidates[0].mesh_role == "stock_room_0"


def test_viewport_hover_candidates_batch_project_each_mesh_once() -> None:
    _configure_native_python_roots()
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    calls: list[tuple] = []

    def project_batch(points, width, height):
        calls.append((tuple(points), width, height))
        return [(point[0], point[1], point[2]) for point in points]

    def scalar_project(*_args):
        raise AssertionError("batch-capable hover generation must not project every face corner")

    mesh = SimpleNamespace(
        vertices=((0.0, 0.0, 5.0), (100.0, 0.0, 5.0), (100.0, 100.0, 5.0), (0.0, 100.0, 5.0)),
        faces=((0, 1, 2), (0, 2, 3)),
        uvs=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        texture="floor",
        _gr_map_studio_mesh_role="stock_room_0",
        _gr_map_studio_backdrop=False,
    )
    room = SimpleNamespace(
        children=(mesh,),
        position=(10.0, 20.0, 0.0),
        _gr_map_studio_room_resref="207tel_1",
        _gr_map_studio_backdrop=False,
    )
    owner = SimpleNamespace(
        viewport=SimpleNamespace(_renderer=SimpleNamespace(_proj=scalar_project, _proj_batch=project_batch)),
        _room_preview_model=SimpleNamespace(root_node=SimpleNamespace(children=(room,))),
        _terrain_walkability_overlay=None,
        _hover_component_mode="face",
        _viewport_canvas_size=lambda: (1280, 720),
    )
    owner._map_studio_face_normal = ModuleEditorViewportPanel._map_studio_face_normal
    owner._map_studio_face_uv_points = ModuleEditorViewportPanel._map_studio_face_uv_points
    owner._map_studio_projected_candidate = MethodType(
        ModuleEditorViewportPanel._map_studio_projected_candidate,
        owner,
    )

    candidates = ModuleEditorViewportPanel._map_studio_hover_candidates(owner)

    assert len(calls) == 1
    assert len(calls[0][0]) == 4
    assert len(candidates) == 2
    assert tuple(candidates[0].world_points[0]) == pytest.approx((10.0, 20.0, 5.0))


def test_hover_cache_signature_uses_stable_camera_state_not_visible_probes() -> None:
    _configure_native_python_roots()
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    camera = SimpleNamespace(fov=45.0, _near=0.01)
    renderer = SimpleNamespace(
        _cam_view_matrix=lambda: (
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 1.0, 0.0),
            (0.0, -500.0, 20.0),
        ),
        # The legacy signature called this and returned None when a fixed
        # origin probe was behind the near plane.
        _proj=lambda *_args: None,
    )
    owner = SimpleNamespace(
        viewport=SimpleNamespace(_renderer=renderer, camera=camera),
        _room_preview_model=object(),
        _terrain_walkability_overlay=object(),
        _hover_component_mode="face",
        _viewport_canvas_size=lambda: (1280, 720),
    )

    signature = ModuleEditorViewportPanel._map_studio_hover_cache_signature(owner)

    assert signature is not None
    assert signature[-1]


def test_map_studio_hover_defers_navigation_and_flushes_latest_pointer_once() -> None:
    _configure_native_python_roots()
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    class Timer:
        active = False

        def start(self, _delay=0):
            self.active = True

        def stop(self):
            self.active = False

        def isActive(self):
            return self.active

    timer = Timer()
    cleared: list[bool] = []
    refreshed: list[tuple[float, float]] = []
    viewport = SimpleNamespace(_nav_dragging="orbit")
    owner = SimpleNamespace(
        viewport=viewport,
        _hover_probe_enabled=True,
        _hover_refresh_deferred=False,
        _queued_hover_screen=None,
        _hover_update_timer=timer,
        _event_position=lambda event, _watched=None: event.screen,
        _clear_map_studio_hover=lambda: cleared.append(True),
        _update_map_studio_hover_at_screen=lambda screen: refreshed.append(screen),
    )
    owner._map_studio_hover_navigation_active = MethodType(
        ModuleEditorViewportPanel._map_studio_hover_navigation_active,
        owner,
    )
    first = SimpleNamespace(
        screen=(100.0, 200.0),
        buttons=lambda: 0,
        modifiers=lambda: 0,
    )
    latest = SimpleNamespace(
        screen=(320.0, 240.0),
        buttons=lambda: 0,
        modifiers=lambda: 0,
    )

    ModuleEditorViewportPanel._queue_map_studio_hover(owner, first)
    ModuleEditorViewportPanel._queue_map_studio_hover(owner, latest)

    assert refreshed == []
    assert cleared == [True]
    assert owner._queued_hover_screen == latest.screen
    viewport._nav_dragging = ""
    ModuleEditorViewportPanel._flush_queued_map_studio_hover(owner)
    assert refreshed == [latest.screen]
    assert owner._queued_hover_screen is None


def test_map_studio_camera_navigation_uses_lean_overlay_lod_source_contract() -> None:
    pipeline = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/rendering_pipeline.py"
    ).decode("utf-8")
    overlays = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/overlay_layers.py"
    ).decode("utf-8")

    assert 'map_interaction_lod = bool(' in pipeline
    assert 'getattr(self, "_map_studio_authoring_chrome_enabled", False)' in pipeline
    assert 'and getattr(self, "_nav_dragging", "")' in pipeline
    assert 'if not map_interaction_lod and not bool(self.property("_gr_suppress_renderer_diagnostics"))' in pipeline
    assert "self._draw_map_studio_placement_markers(draw, w, h)" in pipeline
    assert "if not map_interaction_lod:\n                self._draw_wgpu_helper_markers" in pipeline
    assert 'getattr(self, "_map_studio_authoring_chrome_enabled", False)' in overlays
    assert 'and getattr(self, "_nav_dragging", "")' in overlays
