from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WINDOW_PATH = (
    ROOT
    / "native"
    / "GhostRigger.Core.Tools"
    / "Python"
    / "src/gui/windows/module_editor_window.py"
)
CONSTRUCTION_PATH = (
    ROOT
    / "native"
    / "GhostRigger.Core.GUI.Display"
    / "Python"
    / "src/gui/viewports/viewport_core/widgets/construction.py"
)
VIEWPORT_PANEL_PATH = (
    ROOT
    / "native"
    / "GhostRigger.Core.GUI.Display"
    / "Python"
    / "src/gui/panels/module_editor/module_editor_viewport_panel.py"
)
COMPONENT_MENU_PATH = (
    ROOT
    / "native"
    / "GhostRigger.Core.GUI.Display"
    / "Python"
    / "src/gui/panels/module_editor/component_marking_menu.py"
)
COMPATIBILITY_MENU_PATH = (
    ROOT
    / "native"
    / "GhostRigger.Core.GUI.Display"
    / "Python"
    / "src/gui/panels/module_editor/gmodeler_marking_menu.py"
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _method_source(path: Path, class_name: str, method_name: str) -> str:
    source = _source(path)
    tree = ast.parse(source)
    owner = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    method = next(
        node
        for node in owner.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name
    )
    segment = ast.get_source_segment(source, method)
    assert segment is not None
    return segment


def test_module_editor_uses_neutral_component_marking_menu_identity() -> None:
    window = _source(WINDOW_PATH)
    menu = _source(COMPONENT_MENU_PATH)
    compatibility = _source(COMPATIBILITY_MENU_PATH)

    assert (
        "from src.gui.panels.module_editor.component_marking_menu import "
        "MapStudioComponentMarkingMenu"
    ) in window
    assert "MapStudioComponentMarkingMenu(" in window
    assert "def _open_map_studio_component_marking_menu" in window
    assert "MapStudioGModelerMarkingMenu" not in window

    assert "class MapStudioComponentMarkingMenu" in menu
    assert 'BRAND_LABEL = "MODELING"' in menu
    assert "GMODELER" not in menu.upper()
    assert "MapStudioGModelerMarkingMenu = MapStudioComponentMarkingMenu" in compatibility

    # The old lower-case tutorial route remains readable for saved tutorial
    # state, but no title, label, status message, or class in the window may
    # expose the retired product name to a user.
    assert "GModeler" not in window


def test_maya_shortcuts_are_exact_and_scoped_to_the_map_studio_viewport() -> None:
    connect = _method_source(WINDOW_PATH, "ModuleEditorWindow", "_connect")
    maya_block = connect.split("# Maya shelf parity.", 1)[1].split(
        "self.toolbar.actionRequested.connect", 1
    )[0]

    expected = (
        ("mapStudioMayaExtrudeShortcut", "Ctrl+E"),
        ("mapStudioMayaBevelShortcut", "Ctrl+B"),
        ("mapStudioMayaMultiCutShortcut", "Ctrl+X"),
        ("mapStudioMayaQuadDrawShortcut", "Ctrl+Q"),
        ("mapStudioMayaDuplicateSpecialShortcut", "Ctrl+Shift+D"),
        ("mapStudioMayaBridgeOrFillShortcut", "Ctrl+/"),
        ("mapStudioMayaRepeatLastShortcut", "G"),
    )
    actual = tuple(re.findall(r'\("([^"]+)",\s*"([^"]+)"\s*,', maya_block))

    assert actual == expected
    assert 'maya_shortcut_parent = getattr(self.viewport_panel, "viewport", self.viewport_panel)' in maya_block
    assert "QtGui.QShortcut(QtGui.QKeySequence(sequence), maya_shortcut_parent)" in maya_block
    assert "shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)" in maya_block
    assert "self._map_studio_maya_shortcuts.append(shortcut)" in maya_block
    assert "QtCore.Qt.ApplicationShortcut" not in maya_block
    assert "QtCore.Qt.WindowShortcut" not in maya_block


def test_contextual_bridge_fill_shortcut_keeps_closed_loops_reachable() -> None:
    method = _method_source(
        WINDOW_PATH,
        "ModuleEditorWindow",
        "_run_map_studio_bridge_or_fill_shortcut",
    )

    assert '"bridge" if len(edges) == 2 else "fill_hole"' in method
    assert '"bridge" if len(edges) >= 2 else "fill_hole"' not in method


def test_multi_component_mode_selects_the_exact_maya_modeling_preset() -> None:
    method = _method_source(
        WINDOW_PATH,
        "ModuleEditorWindow",
        "_sync_map_studio_tool_belt_preset_for_edit_mode",
    )

    assert '"multi-component": "maya_modeling"' in method
    assert "findData(preset_key)" in method
    assert "self._refresh_map_studio_tool_belt()" in method
    assert 'if current_preset == "custom":' in method


def test_viewport_shelf_routes_commands_and_tool_options_to_the_window() -> None:
    make_tabs = _method_source(
        CONSTRUCTION_PATH,
        "ViewportConstructionMixin",
        "_make_map_studio_modeling_tabs",
    )
    command_route = _method_source(
        CONSTRUCTION_PATH,
        "ViewportConstructionMixin",
        "_run_map_studio_command_from_toolbar",
    )
    options_route = _method_source(
        CONSTRUCTION_PATH,
        "ViewportConstructionMixin",
        "_open_map_studio_tool_options_from_toolbar",
    )

    assert "MapStudioModelingShelf(modeling_content)" in make_tabs
    assert (
        "self.map_studio_modeling_shelf.commandRequested.connect("
        "self._run_map_studio_command_from_toolbar)"
    ) in make_tabs
    assert (
        "self.map_studio_modeling_shelf.optionsRequested.connect("
        "self._open_map_studio_tool_options_from_toolbar)"
    ) in make_tabs
    assert 'getattr(window, "_run_map_studio_viewport_modeling_command", None)' in command_route
    assert "handler(str(action_key or \"\").strip())" in command_route
    assert 'getattr(window, "_open_map_studio_modeling_tool_options", None)' in options_route
    assert "handler(str(action_key or \"\").strip())" in options_route


def test_viewport_panel_does_not_steal_shelf_button_context_menus() -> None:
    build_ui = _method_source(WINDOW_PATH, "ModuleEditorWindow", "_build_ui")
    connect = _method_source(WINDOW_PATH, "ModuleEditorWindow", "_connect")

    assert "self.viewport_panel.setContextMenuPolicy(QtCore.Qt.DefaultContextMenu)" in build_ui
    assert "self.viewport_panel.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)" not in build_ui
    assert "self.viewport_panel.customContextMenuRequested.connect" not in connect


def test_window_routes_persistent_tools_and_selection_helpers_to_the_viewport() -> None:
    method = _method_source(
        WINDOW_PATH,
        "ModuleEditorWindow",
        "_run_map_studio_viewport_modeling_command",
    )

    assert (
        'if key in {"select_triangles", "select_quads", "convert_contained_faces"}:'
        in method
    )
    assert "selector = getattr(self.viewport_panel, key, None)" in method
    assert (
        'if key in {"multi_cut", "target_weld", "make_hole", '
        '"connect_components", "make_live", "quad_draw"}:'
        in method
    )
    assert 'getattr(self.viewport_panel, "activate_map_studio_modeling_tool", None)' in method
    assert "self._last_map_studio_modeling_action_key = key" in method


def test_invalid_imported_component_tools_do_not_fall_through_to_floor_plan_commands() -> None:
    method = _method_source(
        WINDOW_PATH,
        "ModuleEditorWindow",
        "_apply_map_studio_component_shelf_action",
    )

    assert "cannot mix components from different KOTOR rooms" in method
    assert "needs components from one editable mesh surface" in method
    assert '"fill_hole": "Fill Hole needs one complete closed border-edge loop."' in method
    assert '"merge_components": (' in method
    assert "at least two selected vertices or exactly two selected border edges" in method
    assert "return True" in method.split("if kwargs is None:", 1)[1]


def test_merge_routes_all_selected_vertices_or_exactly_two_border_edges() -> None:
    method = _method_source(
        WINDOW_PATH,
        "ModuleEditorWindow",
        "_apply_map_studio_component_shelf_action",
    )
    options = _method_source(
        WINDOW_PATH,
        "ModuleEditorWindow",
        "_edit_map_studio_baked_modeling_options",
    )

    assert '"op": "merge_components"' in method
    assert '"merge_vertex_indices": tuple(' in method
    assert '"merge_edge_vertex_indices": edge_indices' in method
    assert '"merge_threshold": float(options["threshold"])' in method
    assert '"merge_components": "Merge Options"' in options
    assert "Exactly two selected" in options
    assert "border edges merge by their nearest endpoint pairing" in options


def test_delete_history_is_reachable_for_an_imported_room_selection() -> None:
    method = _method_source(
        WINDOW_PATH,
        "ModuleEditorWindow",
        "_run_map_studio_viewport_modeling_command",
    )

    assert 'if key == "delete_history":' in method
    assert "self.controller.delete_authored_room_primitive_history(" in method
    assert "evaluated geometry and export provenance were retained" in method


def test_connect_never_silently_ignores_extra_selected_vertices() -> None:
    panel = _method_source(
        VIEWPORT_PANEL_PATH,
        "ModuleEditorViewportPanel",
        "activate_map_studio_modeling_tool",
    )
    window = _method_source(
        WINDOW_PATH,
        "ModuleEditorWindow",
        "_commit_map_studio_modeling_tool_gesture",
    )

    assert 'key == "connect_components" and len(selected) == 2' in panel
    assert 'key == "connect_components" and len(selected) > 2' in panel
    assert "Connect needs exactly two selected vertices" in panel
    assert "if len(vertices) != 2:" in window


def test_viewport_owns_persistent_tool_activation_and_face_selection_methods() -> None:
    panel = _source(VIEWPORT_PANEL_PATH)
    for method_name in (
        "select_triangles",
        "select_quads",
        "convert_contained_faces",
        "activate_map_studio_modeling_tool",
    ):
        assert f"def {method_name}(" in panel

    activation = _method_source(
        VIEWPORT_PANEL_PATH,
        "ModuleEditorViewportPanel",
        "activate_map_studio_modeling_tool",
    )
    expected_modes = {
        "multi_cut": "face",
        "target_weld": "vertex",
        "make_hole": "face",
        "connect_components": "vertex",
        "make_live": "object",
        "quad_draw": "face",
    }
    parsed = ast.parse(activation)
    modes_assignment = next(
        node
        for node in ast.walk(parsed)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "modes" for target in node.targets)
    )

    assert ast.literal_eval(modes_assignment.value) == expected_modes
    # Tools may add focused gesture state (for example Quad Draw's projected
    # point entries), but every persistent context keeps these common fields.
    assert '"key": key' in activation
    assert '"picks": []' in activation
    assert '"points": []' in activation
    assert "self.set_map_studio_hover_probe(True, modes[key])" in activation
    assert 'if key == "quad_draw"' in activation
    assert "self._map_studio_live_surface" in activation
